"""Thin Microsoft Graph client: just the mailbox reads this tool needs."""
from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx

from .analyze import ReceivedMessage, SentMessage

GRAPH = "https://graph.microsoft.com/v1.0"
# PR_MESSAGE_CLASS — tells us if a message is an NDR, delivery receipt, read receipt, …
MSG_CLASS = "String 0x001A"


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _addr(r: dict) -> str:
    return (r.get("emailAddress", {}).get("address") or "").strip().lower()


class Graph:
    def __init__(self, token: str):
        self.client = httpx.Client(
            headers={
                "Authorization": f"Bearer {token}",
                "Prefer": 'outlook.body-content-type="text"',
            },
            timeout=60,
        )

    def _get(self, url: str, params: dict | None = None) -> dict:
        for attempt in range(6):
            resp = self.client.get(url, params=params)
            if resp.status_code in (429, 503, 504):
                time.sleep(int(resp.headers.get("Retry-After", 2 ** attempt)))
                continue
            if resp.status_code >= 400:
                raise RuntimeError(f"Graph {resp.status_code}: {resp.text[:500]}")
            return resp.json()
        raise RuntimeError("Graph kept throttling the request; try again later.")

    def _paged(self, url: str, params: dict):
        data = self._get(url, params)
        while True:
            yield from data.get("value", [])
            nxt = data.get("@odata.nextLink")
            if not nxt:
                return
            data = self._get(nxt)

    def my_addresses(self) -> set[str]:
        me = self._get(f"{GRAPH}/me", {"$select": "mail,userPrincipalName,proxyAddresses"})
        addrs = {a.lower() for a in (me.get("mail"), me.get("userPrincipalName")) if a}
        for p in me.get("proxyAddresses") or []:
            if p.lower().startswith("smtp:"):
                addrs.add(p[5:].lower())
        return addrs

    def sent_items(self, since: datetime) -> list[SentMessage]:
        return self._folder_messages("sentitems", since, "sentDateTime")

    def outbox_items(self) -> list[SentMessage]:
        """Messages still sitting in the Outbox, i.e. never actually sent."""
        return self._folder_messages("outbox", None, "createdDateTime")

    def _folder_messages(self, folder: str, since: datetime | None, date_field: str) -> list[SentMessage]:
        params = {
            "$select": f"id,subject,toRecipients,ccRecipients,bccRecipients,conversationId,{date_field}",
            "$top": "100",
        }
        if since:
            params["$filter"] = f"{date_field} ge {_iso(since)}"
            params["$orderby"] = f"{date_field} desc"
        out = []
        for m in self._paged(f"{GRAPH}/me/mailFolders/{folder}/messages", params):
            recips = [
                _addr(r)
                for key in ("toRecipients", "ccRecipients", "bccRecipients")
                for r in m.get(key) or []
            ]
            out.append(
                SentMessage(
                    id=m["id"],
                    subject=m.get("subject") or "",
                    sent_at=_dt(m[date_field]),
                    recipients=[r for r in dict.fromkeys(recips) if r],
                    conversation_id=m.get("conversationId"),
                )
            )
        return out

    def received_since(self, since: datetime) -> list[ReceivedMessage]:
        """Every message received since `since`, across ALL folders (incl. Junk/Deleted)."""
        params = {
            "$select": "id,subject,from,sender,receivedDateTime,conversationId,bodyPreview",
            "$filter": f"receivedDateTime ge {_iso(since)}",
            "$expand": f"singleValueExtendedProperties($filter=id eq '{MSG_CLASS}')",
            "$top": "100",
        }
        out = []
        for m in self._paged(f"{GRAPH}/me/messages", params):
            props = m.get("singleValueExtendedProperties") or []
            msg_class = next((p.get("value", "") for p in props), "")
            out.append(
                ReceivedMessage(
                    id=m["id"],
                    subject=m.get("subject") or "",
                    sender=_addr(m.get("from") or m.get("sender") or {}),
                    received_at=_dt(m["receivedDateTime"]),
                    conversation_id=m.get("conversationId"),
                    message_class=msg_class or "",
                    body=m.get("bodyPreview") or "",
                )
            )
        return out

    def full_body(self, message_id: str) -> str:
        data = self._get(f"{GRAPH}/me/messages/{message_id}", {"$select": "body"})
        return (data.get("body") or {}).get("content") or ""

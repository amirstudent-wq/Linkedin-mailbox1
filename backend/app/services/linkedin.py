"""
LinkedIn service — wraps the unofficial linkedin-api library.

⚠  The linkedin-api library uses unofficial, reverse-engineered endpoints.
   LinkedIn may rate-limit or block access. Use at your own discretion and
   ensure you comply with LinkedIn's Terms of Service.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import settings
from ..schemas import Participant

logger = logging.getLogger(__name__)

_linkedin_client: Optional[Any] = None


def _get_client() -> Any:
    """Return a lazily-initialised Linkedin client."""
    global _linkedin_client
    if _linkedin_client is None:
        if not settings.linkedin_email or not settings.linkedin_password:
            raise RuntimeError(
                "LINKEDIN_EMAIL and LINKEDIN_PASSWORD must be set in the environment."
            )
        try:
            from linkedin_api import Linkedin  # type: ignore
            _linkedin_client = Linkedin(
                settings.linkedin_email,
                settings.linkedin_password,
                authenticate=True,
            )
            logger.info("LinkedIn client authenticated as %s", settings.linkedin_email)
        except Exception as exc:
            logger.error("LinkedIn authentication failed: %s", exc)
            raise RuntimeError(f"LinkedIn authentication failed: {exc}") from exc
    return _linkedin_client


def _safe_text(event: Dict) -> str:
    """Extract plain-text body from a conversation event."""
    try:
        return event["eventContent"]["com.linkedin.voyager.messaging.event.MessageEvent"]["attributedBody"]["text"]
    except (KeyError, TypeError):
        return ""


def _safe_ts(ms: Optional[int]) -> Optional[datetime]:
    return datetime.utcfromtimestamp(ms / 1000) if ms else None


def _participant_from_raw(raw: Dict) -> Participant:
    """Convert a raw messaging participant dict to a Participant schema."""
    try:
        member = raw["com.linkedin.voyager.messaging.MessagingMember"]
        mini = member.get("miniProfile", {})
        first = mini.get("firstName", "")
        last = mini.get("lastName", "")
        name = f"{first} {last}".strip() or "Unknown"
        profile_id = mini.get("publicIdentifier", "")
        headline = mini.get("occupation", "")
        picture = mini.get("picture", {})
        # Grab the largest available thumbnail
        artifacts = (
            picture.get("com.linkedin.common.VectorImage", {})
            .get("artifacts", [])
        )
        avatar_url = ""
        root_url = (
            picture.get("com.linkedin.common.VectorImage", {})
            .get("rootUrl", "")
        )
        if artifacts:
            avatar_url = root_url + artifacts[-1].get("fileIdentifyingUrlPathSegment", "")
        return Participant(
            profile_id=profile_id,
            name=name,
            headline=headline,
            avatar_url=avatar_url,
        )
    except Exception:
        return Participant(profile_id="unknown", name="Unknown")


def _own_profile_id() -> str:
    """Return the profile ID of the authenticated user."""
    try:
        profile = _get_client().get_user_profile()
        return profile.get("miniProfile", {}).get("publicIdentifier", "me")
    except Exception:
        return "me"


# ── Public interface ─────────────────────────────────────────────────────────

def is_connected() -> bool:
    """Check if LinkedIn credentials are configured and working."""
    try:
        _get_client()
        return True
    except Exception:
        return False


def fetch_conversations(limit: int = 40) -> List[Dict]:
    """
    Fetch conversations from LinkedIn and normalise them into a list of dicts
    ready to be stored in the database.
    """
    client = _get_client()
    own_id = _own_profile_id()

    raw = client.get_conversations()
    elements = raw.get("elements", []) if isinstance(raw, dict) else []

    results: List[Dict] = []
    for elem in elements[:limit]:
        try:
            conversation_id = elem.get("entityUrn", "")

            # Participants
            raw_participants = elem.get("participants", [])
            participants = [_participant_from_raw(p) for p in raw_participants]

            # Last activity
            last_activity_ms = elem.get("lastActivityAt")
            last_message_at = _safe_ts(last_activity_ms)

            # Latest event
            events = elem.get("events", [])
            last_event = events[0] if events else {}
            last_message_text = _safe_text(last_event)
            last_sender_id = (
                last_event.get("from", {})
                .get("com.linkedin.voyager.messaging.MessagingMember", {})
                .get("miniProfile", {})
                .get("publicIdentifier", "")
            )
            last_message_is_mine = last_sender_id == own_id

            is_read = elem.get("read", True)
            # Awaiting reply: the other party sent the last message
            awaiting_reply = (not last_message_is_mine) and bool(last_message_text)

            results.append(
                {
                    "id": conversation_id,
                    "participants": [p.model_dump() for p in participants],
                    "last_message_at": last_message_at,
                    "last_message_text": last_message_text,
                    "is_read": is_read,
                    "last_message_is_mine": last_message_is_mine,
                    "awaiting_reply": awaiting_reply,
                    "message_count": elem.get("totalEventCount", len(events)),
                }
            )
        except Exception as exc:
            logger.warning("Skipping conversation due to parse error: %s", exc)

    return results


def fetch_messages(conversation_id: str) -> List[Dict]:
    """
    Fetch all messages for a given conversation URN and normalise them.
    """
    client = _get_client()
    own_id = _own_profile_id()

    raw = client.get_conversation(conversation_id)
    elements = raw.get("elements", []) if isinstance(raw, dict) else []

    results: List[Dict] = []
    for event in reversed(elements):  # oldest first
        try:
            text = _safe_text(event)
            if not text:
                continue
            event_id = event.get("entityUrn", "")
            sender_raw = event.get("from", {})
            sender_member = sender_raw.get("com.linkedin.voyager.messaging.MessagingMember", {})
            mini = sender_member.get("miniProfile", {})
            sender_id = mini.get("publicIdentifier", "")
            first = mini.get("firstName", "")
            last = mini.get("lastName", "")
            sender_name = f"{first} {last}".strip() or "Unknown"
            sent_ms = event.get("createdAt")
            sent_at = _safe_ts(sent_ms)
            is_mine = sender_id == own_id

            results.append(
                {
                    "id": event_id or hashlib.md5(f"{conversation_id}{sent_ms}".encode()).hexdigest(),
                    "conversation_id": conversation_id,
                    "sender_id": sender_id,
                    "sender_name": sender_name,
                    "sender_avatar": "",
                    "body": text,
                    "sent_at": sent_at,
                    "is_mine": is_mine,
                }
            )
        except Exception as exc:
            logger.warning("Skipping message event due to parse error: %s", exc)

    return results


def send_message(conversation_id: str, body: str) -> bool:
    """
    Send a reply to a conversation. Returns True on success.
    conversation_id is the full URN string.
    """
    client = _get_client()
    try:
        client.send_message(body, conversation_urn_id=conversation_id)
        logger.info("Message sent to conversation %s", conversation_id)
        return True
    except Exception as exc:
        logger.error("Failed to send message: %s", exc)
        return False

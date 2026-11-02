"""Match bounces, receipts, auto-replies and replies back to the mail you sent.

Pure logic, no network — everything here is unit-tested.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+'=-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
PREFIX_RE = re.compile(
    r"^\s*(?:undeliverable|undelivered mail returned to sender|undelivered|delivered|not read|read|"
    r"delivery delayed|delayed|automatic reply|auto(?:matic)?[- ]?reply|out of office|"
    r"re|fw|fwd|aw|wg|sv|antw|tr|rv)\s*:\s*",
    re.I,
)
# Enhanced SMTP status, e.g. "550 5.1.1 User unknown" or "Remote server returned '550 5.7.1 …'"
SMTP_RE = re.compile(r"\b([45]\d\d)[ \-#]+([45]\.\d{1,3}\.\d{1,3})\b[^\n]{0,180}")
SMTP_ENHANCED_ONLY_RE = re.compile(r"#?\b([45]\.\d{1,3}\.\d{1,3})\b[^\n]{0,180}")

# Status, from strongest proof of delivery to weakest.
REPLIED, READ, DELIVERED, BOUNCED, DELAYED, NO_SIGNAL = (
    "replied", "read", "delivered", "bounced", "delayed", "no_signal",
)
RANK = {REPLIED: 6, READ: 5, DELIVERED: 4, BOUNCED: 3, DELAYED: 2, NO_SIGNAL: 1}
LABEL = {
    REPLIED: "Replied",
    READ: "Opened (read receipt)",
    DELIVERED: "Delivered (confirmed)",
    BOUNCED: "Bounced",
    DELAYED: "Delayed",
    NO_SIGNAL: "Sent, no bounce",
}


@dataclass
class SentMessage:
    id: str
    subject: str
    sent_at: datetime
    recipients: list[str]
    conversation_id: str | None = None


@dataclass
class ReceivedMessage:
    id: str
    subject: str
    sender: str
    received_at: datetime
    conversation_id: str | None = None
    message_class: str = ""
    body: str = ""


@dataclass
class RecipientResult:
    address: str
    status: str = NO_SIGNAL
    detail: str = ""
    at: datetime | None = None

    def apply(self, status: str, detail: str, at: datetime) -> None:
        if RANK[status] > RANK[self.status]:
            self.status, self.detail, self.at = status, detail, at


@dataclass
class MessageResult:
    sent: SentMessage
    recipients: dict[str, RecipientResult]
    notes: list[str] = field(default_factory=list)

    @property
    def worst(self) -> str:
        statuses = {r.status for r in self.recipients.values()}
        for s in (BOUNCED, DELAYED, NO_SIGNAL, DELIVERED, READ, REPLIED):
            if s in statuses:
                return s
        return NO_SIGNAL


# ─── Classification ──────────────────────────────────────────────────────────

NDR_SUBJECTS = (
    "undeliverable", "undelivered", "delivery has failed", "mail delivery failed",
    "delivery status notification (failure)", "returned mail", "failure notice",
    "mail delivery subsystem", "delivery failure", "message not delivered",
)
DELAY_SUBJECTS = ("delivery delayed", "delivery status notification (delay)", "delayed mail", "warning: message")
AUTO_REPLY_SUBJECTS = ("automatic reply", "auto reply", "autoreply", "auto-reply", "out of office")
BOUNCE_SENDERS = ("postmaster@", "mailer-daemon@", "microsoftexchange", "mail-daemon@")


def classify(msg: ReceivedMessage) -> str | None:
    """Return 'ndr' | 'delay' | 'delivery_receipt' | 'read_receipt' | 'not_read' | 'auto_reply' | None."""
    mc = msg.message_class.upper()
    if mc.startswith("REPORT."):
        if mc.endswith(".NDR"):
            return "ndr"
        if mc.endswith(".DR"):
            return "delivery_receipt"
        if mc.endswith(".IPNRN"):
            return "read_receipt"
        if mc.endswith(".IPNNRN"):
            return "not_read"
        if "DELAYED" in mc:
            return "delay"
    if mc.startswith("IPM.NOTE.RULES.OOFTEMPLATE") or mc.startswith("IPM.NOTE.RULES.REPLYTEMPLATE"):
        return "auto_reply"

    subj = msg.subject.strip().lower()
    if subj.startswith(DELAY_SUBJECTS):
        return "delay"
    if subj.startswith(NDR_SUBJECTS):
        return "ndr"
    if subj.startswith("delivered:"):
        return "delivery_receipt"
    if subj.startswith("not read:"):
        return "not_read"
    if subj.startswith("read:"):
        return "read_receipt"
    if subj.startswith(AUTO_REPLY_SUBJECTS):
        return "auto_reply"
    if any(msg.sender.startswith(s) or s in msg.sender for s in BOUNCE_SENDERS):
        return "ndr"
    return None


def normalize_subject(subject: str) -> str:
    s = subject or ""
    while True:
        new = PREFIX_RE.sub("", s, count=1)
        if new == s:
            break
        s = new
    return " ".join(s.split()).casefold()


def extract_emails(text: str) -> set[str]:
    return {e.lower().rstrip(".") for e in EMAIL_RE.findall(text or "")}


def bounce_reason(body: str) -> tuple[str, str]:
    """(category, raw line) for an NDR body."""
    m = SMTP_RE.search(body or "")
    code = m.group(2) if m else None
    if not m:
        m = SMTP_ENHANCED_ONLY_RE.search(body or "")
        code = m.group(1) if m else None
    raw = " ".join(m.group(0).split())[:200] if m else ""
    return categorize_code(code), raw


def categorize_code(code: str | None) -> str:
    if not code:
        return "Bounced (reason not stated)"
    if code.startswith("4."):
        return "Temporary failure (server will retry)"
    if code in ("5.1.1", "5.1.10", "5.1.0", "5.1.2", "5.1.3", "5.4.1", "5.4.4", "5.1.6"):
        return "Address does not exist"
    if code in ("5.2.2", "5.2.3"):
        return "Mailbox full / message too large"
    if code.startswith("5.7."):
        return "Blocked by recipient server (spam filter, reputation or SPF/DKIM/DMARC)"
    return f"Permanent failure ({code})"


# ─── Matching ────────────────────────────────────────────────────────────────

def _match(
    msg: ReceivedMessage,
    sent: list[SentMessage],
    addrs: set[str],
    max_age: timedelta,
    addr_fallback: bool = True,
) -> SentMessage | None:
    prior = [
        s for s in sent
        if s.sent_at <= msg.received_at + timedelta(minutes=5)
        and msg.received_at - s.sent_at <= max_age
    ]
    cands = [s for s in prior if msg.conversation_id and s.conversation_id == msg.conversation_id]
    if not cands:
        ns = normalize_subject(msg.subject)
        if ns:
            cands = [s for s in prior if normalize_subject(s.subject) == ns]
    if not cands and addrs and addr_fallback:
        # e.g. Gmail's "Delivery Status Notification (Failure)" — no original subject.
        cands = [s for s in prior if addrs & set(s.recipients) and msg.received_at - s.sent_at <= timedelta(days=7)]
    if not cands:
        return None
    overlap = [s for s in cands if addrs & set(s.recipients)]
    return max(overlap or cands, key=lambda s: s.sent_at)


def analyze(
    sent: list[SentMessage],
    received: list[ReceivedMessage],
    my_addresses: set[str],
    body_loader=None,
) -> tuple[list[MessageResult], list[ReceivedMessage]]:
    """Returns (per-message results, reports we could not tie to a sent message)."""
    mine = {a.lower() for a in my_addresses}
    results = {
        s.id: MessageResult(s, {r: RecipientResult(r) for r in s.recipients if r})
        for s in sent
    }
    unmatched: list[ReceivedMessage] = []

    for msg in sorted(received, key=lambda m: m.received_at):
        if msg.sender in mine:
            continue
        kind = classify(msg)

        if kind in ("ndr", "delay", "delivery_receipt") and body_loader:
            try:
                msg.body = body_loader(msg.id) or msg.body
            except Exception:  # keep going with the preview
                pass

        if kind is None:
            # A normal message: is it a reply from someone we emailed?
            target = _match(msg, sent, {msg.sender}, timedelta(days=60), addr_fallback=False)
            if target and msg.sender in results[target.id].recipients:
                results[target.id].recipients[msg.sender].apply(REPLIED, "Replied", msg.received_at)
            continue

        addrs = (extract_emails(msg.body) | {msg.sender}) - mine
        target = _match(msg, sent, addrs, timedelta(days=30))
        if not target:
            if kind in ("ndr", "delay"):
                unmatched.append(msg)
            continue
        res = results[target.id]
        hits = addrs & set(res.recipients)
        if not hits and len(res.recipients) == 1:
            hits = set(res.recipients)

        if kind == "ndr":
            category, raw = bounce_reason(msg.body)
            detail = category + (f" — {raw}" if raw else "")
            if not hits:
                res.notes.append(f"Bounce received but recipient not identified: {detail}")
            for a in hits:
                res.recipients[a].apply(BOUNCED, detail, msg.received_at)
        elif kind == "delay":
            for a in hits:
                res.recipients[a].apply(DELAYED, "Delivery delayed — server still retrying", msg.received_at)
        elif kind == "delivery_receipt":
            for a in hits:
                res.recipients[a].apply(DELIVERED, "Delivery receipt", msg.received_at)
        elif kind == "read_receipt":
            for a in hits:
                res.recipients[a].apply(READ, "Read receipt", msg.received_at)
        elif kind == "not_read":
            for a in hits:
                res.recipients[a].apply(DELIVERED, "Delivered, but deleted without being read", msg.received_at)
        elif kind == "auto_reply":
            for a in hits:
                res.recipients[a].apply(DELIVERED, "Auto-reply / out-of-office received", msg.received_at)

    return sorted(results.values(), key=lambda r: r.sent.sent_at, reverse=True), unmatched


# ─── Summary ─────────────────────────────────────────────────────────────────

def summarize(results: list[MessageResult]) -> dict:
    counts = defaultdict(int)
    by_domain: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    bounce_reasons = defaultdict(int)
    for r in results:
        for rr in r.recipients.values():
            counts[rr.status] += 1
            domain = rr.address.split("@")[-1]
            by_domain[domain]["total"] += 1
            by_domain[domain][rr.status] += 1
            if rr.status == BOUNCED:
                bounce_reasons[rr.detail.split(" — ")[0]] += 1
    total = sum(counts.values())

    def pct(n):
        return round(100 * n / total, 1) if total else 0.0

    bounced = counts[BOUNCED]
    confirmed = counts[REPLIED] + counts[READ] + counts[DELIVERED]
    warnings = []
    if total and pct(bounced) >= 5:
        warnings.append(f"Bounce rate is {pct(bounced)}% — above ~2% hurts sender reputation and pushes mail to spam.")
    elif total and pct(bounced) >= 2:
        warnings.append(f"Bounce rate is {pct(bounced)}% — keep it under 2%. Verify addresses before sending.")
    blocked = sum(n for k, n in bounce_reasons.items() if k.startswith("Blocked"))
    if blocked:
        warnings.append(
            f"{blocked} recipient(s) were blocked by spam/policy filters (5.7.x). "
            "That is a strong sign of a reputation or SPF/DKIM/DMARC problem."
        )
    for domain, d in by_domain.items():
        if d["total"] >= 3 and d[BOUNCED] / d["total"] >= 0.5:
            warnings.append(f"{d[BOUNCED]}/{d['total']} messages to {domain} bounced — that provider may be blocking you.")

    return {
        "recipients": total,
        "messages": len(results),
        "counts": dict(counts),
        "bounce_rate": pct(bounced),
        "confirmed_rate": pct(confirmed),
        "reply_rate": pct(counts[REPLIED]),
        "by_domain": {k: dict(v) for k, v in sorted(by_domain.items(), key=lambda kv: -kv[1]["total"])},
        "bounce_reasons": dict(bounce_reasons),
        "warnings": warnings,
    }

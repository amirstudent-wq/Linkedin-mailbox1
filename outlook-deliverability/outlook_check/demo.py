"""Sample mailbox used by --demo and the tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .analyze import ReceivedMessage, SentMessage


def demo_data():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    t = lambda days, hours=0: now - timedelta(days=days, hours=hours)  # noqa: E731
    me = {"you@example.com"}

    sent = [
        SentMessage("s1", "Partnership proposal", t(5), ["dana@acme.com"], "c1"),
        SentMessage("s2", "Q4 media plan", t(4), ["typo@acme.com", "lee@acme.com"], "c2"),
        SentMessage("s3", "Quick intro", t(3), ["sam@gmail.com"], "c3"),
        SentMessage("s4", "Following up", t(2), ["ops@bigcorp.io"], "c4"),
        SentMessage("s5", "Deck attached", t(2), ["kim@startup.co"], "c5"),
        SentMessage("s6", "Coffee next week?", t(1), ["alex@agency.net"], "c6"),
        SentMessage("s7", "Invoice #1042", t(1), ["billing@vendor.com"], "c7"),
    ]
    received = [
        ReceivedMessage("r1", "RE: Partnership proposal", "dana@acme.com", t(4, 20), "c1"),
        ReceivedMessage(
            "r2", "Undeliverable: Q4 media plan", "postmaster@example.com", t(4, -1), "c2",
            "REPORT.IPM.Note.NDR",
            "Your message to typo@acme.com couldn't be delivered.\n"
            "Remote server returned '550 5.1.1 RESOLVER.ADR.RecipNotFound; not found'",
        ),
        ReceivedMessage(
            "r3", "Delivery Status Notification (Failure)", "mailer-daemon@googlemail.com", t(3, -1), "zz",
            "",
            "Your message wasn't delivered to sam@gmail.com because the remote server rejected it.\n"
            "550 5.7.26 Unauthenticated email from example.com is not accepted due to domain's DMARC policy.",
        ),
        ReceivedMessage("r4", "Read: Following up", "ops@bigcorp.io", t(1, 12), "c4", "REPORT.IPM.Note.IPNRN"),
        ReceivedMessage("r5", "Automatic reply: Deck attached", "kim@startup.co", t(2, -1), "c5", "IPM.Note.Rules.OofTemplate.Microsoft"),
        ReceivedMessage(
            "r6", "Delivery delayed:Invoice #1042", "postmaster@example.com", t(0, 20), "c7",
            "REPORT.IPM.Note.Delayed",
            "Delivery to these recipients or groups is delayed: billing@vendor.com\n451 4.4.0 DNS query failed",
        ),
        ReceivedMessage("r7", "Weekly newsletter", "news@somewhere.com", t(1), "c99"),
    ]
    outbox = [SentMessage("o1", "Contract draft", t(0, 2), ["legal@acme.com"], "c8")]
    return sent, received, outbox, me

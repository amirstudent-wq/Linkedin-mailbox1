from datetime import datetime, timedelta, timezone

from outlook_check.analyze import (
    BOUNCED, DELAYED, DELIVERED, NO_SIGNAL, READ, REPLIED,
    ReceivedMessage, SentMessage, analyze, bounce_reason, classify, normalize_subject, summarize,
)
from outlook_check.demo import demo_data


def _status(results):
    return {(r.sent.id, a): rr.status for r in results for a, rr in r.recipients.items()}


def test_demo_end_to_end():
    sent, received, _outbox, me = demo_data()
    results, unmatched = analyze(sent, received, me)
    st = _status(results)
    assert st[("s1", "dana@acme.com")] == REPLIED
    assert st[("s2", "typo@acme.com")] == BOUNCED
    assert st[("s2", "lee@acme.com")] == NO_SIGNAL  # bounce only hit the bad address
    assert st[("s3", "sam@gmail.com")] == BOUNCED   # Gmail DSN matched by address
    assert st[("s4", "ops@bigcorp.io")] == READ
    assert st[("s5", "kim@startup.co")] == DELIVERED
    assert st[("s6", "alex@agency.net")] == NO_SIGNAL
    assert st[("s7", "billing@vendor.com")] == DELAYED
    assert unmatched == []

    s3 = next(r for r in results if r.sent.id == "s3")
    assert s3.recipients["sam@gmail.com"].detail.startswith("Blocked")

    summary = summarize(results)
    assert summary["recipients"] == 8
    assert summary["counts"][BOUNCED] == 2
    assert any("5.7" in w for w in summary["warnings"])


def test_classify_by_subject_and_class():
    now = datetime.now(timezone.utc)
    mk = lambda subj, sender="x@y.com", mc="": ReceivedMessage("r", subj, sender, now, None, mc)  # noqa: E731
    assert classify(mk("Undeliverable: hi")) == "ndr"
    assert classify(mk("Mail delivery failed: returning message to sender")) == "ndr"
    assert classify(mk("Delivered: hi")) == "delivery_receipt"
    assert classify(mk("Read: hi")) == "read_receipt"
    assert classify(mk("Not read: hi")) == "not_read"
    assert classify(mk("Out of Office: hi")) == "auto_reply"
    assert classify(mk("hello", "MAILER-DAEMON@x.com".lower())) == "ndr"
    assert classify(mk("Anything", mc="REPORT.IPM.Note.DR")) == "delivery_receipt"
    assert classify(mk("Re: read this")) is None
    assert classify(mk("Readme")) is None


def test_normalize_subject():
    assert normalize_subject("Undeliverable: RE: FW:  Hello   World") == "hello world"
    assert normalize_subject("Read: Re: Hi") == "hi"


def test_bounce_reason_categories():
    assert bounce_reason("550 5.1.1 user unknown")[0] == "Address does not exist"
    assert bounce_reason("552 5.2.2 mailbox full")[0].startswith("Mailbox full")
    assert bounce_reason("Remote server returned '550 5.7.1 Service unavailable; client host blocked'")[0].startswith("Blocked")
    assert bounce_reason("nothing useful")[0] == "Bounced (reason not stated)"
    assert bounce_reason("#5.4.1 Recipient address rejected: Access denied")[0] == "Address does not exist"


def test_reply_from_non_recipient_ignored_and_unrelated_mail_not_a_reply():
    now = datetime.now(timezone.utc)
    sent = [SentMessage("s", "Hello", now - timedelta(days=1), ["a@x.com"], "c")]
    received = [
        ReceivedMessage("r1", "RE: Hello", "stranger@x.com", now, "c"),
        ReceivedMessage("r2", "Totally unrelated", "a@x.com", now, "other"),
    ]
    results, _ = analyze(sent, received, {"me@me.com"})
    assert results[0].recipients["a@x.com"].status == NO_SIGNAL


def test_bounce_before_send_is_not_matched():
    now = datetime.now(timezone.utc)
    sent = [SentMessage("s", "Hello", now, ["a@x.com"], "c")]
    received = [ReceivedMessage("r", "Undeliverable: Hello", "postmaster@me.com", now - timedelta(days=1), "c",
                                "REPORT.IPM.Note.NDR", "a@x.com 550 5.1.1")]
    results, unmatched = analyze(sent, received, {"me@me.com"})
    assert results[0].recipients["a@x.com"].status == NO_SIGNAL
    assert len(unmatched) == 1


def test_positive_proof_beats_bounce():
    now = datetime.now(timezone.utc)
    sent = [SentMessage("s", "Hello", now - timedelta(hours=5), ["a@x.com"], "c")]
    received = [
        ReceivedMessage("r1", "Undeliverable: Hello", "postmaster@me.com", now - timedelta(hours=4), "c",
                        "REPORT.IPM.Note.NDR", "a@x.com 450 4.2.0 try later"),
        ReceivedMessage("r2", "Re: Hello", "a@x.com", now, "c"),
    ]
    results, _ = analyze(sent, received, {"me@me.com"})
    assert results[0].recipients["a@x.com"].status == REPLIED

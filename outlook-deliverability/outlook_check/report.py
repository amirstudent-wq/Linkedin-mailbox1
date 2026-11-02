"""Terminal summary, CSV and a self-contained HTML report."""
from __future__ import annotations

import csv
from datetime import datetime
from html import escape
from pathlib import Path

from .analyze import BOUNCED, DELAYED, DELIVERED, LABEL, NO_SIGNAL, READ, REPLIED, MessageResult, SentMessage

ORDER = [REPLIED, READ, DELIVERED, NO_SIGNAL, DELAYED, BOUNCED]
COLOR = {
    REPLIED: "#15803d", READ: "#16a34a", DELIVERED: "#65a30d",
    NO_SIGNAL: "#64748b", DELAYED: "#d97706", BOUNCED: "#dc2626",
}


def _fmt(dt: datetime | None) -> str:
    return dt.astimezone().strftime("%Y-%m-%d %H:%M") if dt else ""


def print_summary(summary: dict, outbox: list[SentMessage], checks, unmatched_count: int, days: int) -> None:
    c = summary["counts"]
    print()
    print(f"Sent mail, last {days} days: {summary['messages']} messages to {summary['recipients']} recipients")
    print("-" * 64)
    for s in ORDER:
        print(f"  {LABEL[s]:<26} {c.get(s, 0):>5}")
    print("-" * 64)
    print(f"  Bounce rate {summary['bounce_rate']}%   Confirmed delivered {summary['confirmed_rate']}%   Reply rate {summary['reply_rate']}%")
    if outbox:
        print(f"\n  !! {len(outbox)} message(s) are stuck in your Outbox and were never sent:")
        for m in outbox[:10]:
            print(f"     - {m.subject or '(no subject)'}  → {', '.join(m.recipients)}")
    if unmatched_count:
        print(f"\n  {unmatched_count} bounce/delay notice(s) could not be tied to a sent message (see report).")
    for w in summary["warnings"]:
        print(f"\n  !! {w}")
    if checks:
        print("\nSender authentication:")
        for ch in checks:
            print(f"  [{ch.status.upper():^4}] {ch.name}: {ch.detail}")
    print()


def write_csv(path: Path, results: list[MessageResult]) -> None:
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sent_at", "subject", "recipient", "status", "detail", "evidence_at"])
        for r in results:
            for rr in r.recipients.values():
                w.writerow([_fmt(r.sent.sent_at), r.sent.subject, rr.address, LABEL[rr.status], rr.detail, _fmt(rr.at)])


def write_html(path: Path, results, summary, outbox, checks, unmatched, days: int, account: str) -> None:
    c = summary["counts"]
    total = summary["recipients"] or 1
    bar = "".join(
        f'<span style="width:{100 * c.get(s, 0) / total:.2f}%;background:{COLOR[s]}" title="{LABEL[s]}: {c.get(s, 0)}"></span>'
        for s in ORDER if c.get(s)
    )
    cards = "".join(
        f'<div class="card"><div class="n" style="color:{COLOR[s]}">{c.get(s, 0)}</div><div>{LABEL[s]}</div></div>'
        for s in ORDER
    )
    warn = "".join(f'<div class="alert">{escape(w)}</div>' for w in summary["warnings"])
    if outbox:
        items = "".join(f"<li>{escape(m.subject or '(no subject)')} → {escape(', '.join(m.recipients))}</li>" for m in outbox)
        warn = f'<div class="alert"><b>{len(outbox)} message(s) stuck in your Outbox — never sent:</b><ul>{items}</ul></div>' + warn

    auth = ""
    if checks:
        rows = "".join(
            f'<tr><td><span class="pill {ch.status}">{ch.status.upper()}</span></td><td>{ch.name}</td><td>{escape(ch.detail)}</td></tr>'
            for ch in checks
        )
        auth = f"<h2>Sender authentication</h2><table>{rows}</table>"

    dom_rows = "".join(
        f"<tr><td>{escape(d)}</td><td>{v['total']}</td>"
        + "".join(f"<td>{v.get(s, 0) or ''}</td>" for s in ORDER)
        + "</tr>"
        for d, v in list(summary["by_domain"].items())[:40]
    )
    dom_head = "".join(f"<th>{LABEL[s]}</th>" for s in ORDER)

    msg_rows = []
    for r in results:
        recips = "".join(
            f'<div class="rc"><span class="pill" style="background:{COLOR[rr.status]}">{LABEL[rr.status]}</span> '
            f'{escape(rr.address)}{" <small>" + escape(rr.detail) + "</small>" if rr.detail and rr.status != REPLIED else ""}</div>'
            for rr in sorted(r.recipients.values(), key=lambda x: ORDER.index(x.status), reverse=True)
        )
        notes = "".join(f"<div><small>⚠ {escape(n)}</small></div>" for n in r.notes)
        msg_rows.append(
            f'<tr data-s="{r.worst}"><td class="nw">{_fmt(r.sent.sent_at)}</td>'
            f"<td>{escape(r.sent.subject or '(no subject)')}{notes}</td><td>{recips}</td></tr>"
        )

    unmatched_html = ""
    if unmatched:
        items = "".join(f"<li>{_fmt(m.received_at)} — {escape(m.subject)} <small>({escape(m.sender)})</small></li>" for m in unmatched)
        unmatched_html = f"<h2>Bounce notices not matched to a sent message</h2><ul>{items}</ul>"

    filters = "".join(f'<button data-f="{s}">{LABEL[s]}</button>' for s in [BOUNCED, DELAYED, NO_SIGNAL])

    path.write_text(f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Email Deliverability Report</title>
<style>
:root{{--bg:#f8fafc;--fg:#0f172a;--card:#fff;--line:#e2e8f0;--muted:#64748b}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0b1120;--fg:#e2e8f0;--card:#111827;--line:#1f2937;--muted:#94a3b8}}}}
body{{font:14px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:0;padding:24px 16px;max-width:1200px;margin:auto}}
h1{{margin:0 0 4px}} h2{{margin-top:32px}} .muted,small{{color:var(--muted)}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:16px 0}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}} .n{{font-size:28px;font-weight:700}}
.bar{{display:flex;height:14px;border-radius:7px;overflow:hidden;background:var(--line)}}
.alert{{background:#fef2f2;color:#7f1d1d;border:1px solid #fecaca;border-radius:8px;padding:10px 12px;margin:8px 0}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}}
td,th{{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
.nw{{white-space:nowrap}} .rc{{margin:2px 0;word-break:break-all}}
.pill{{display:inline-block;color:#fff;border-radius:999px;padding:0 8px;font-size:12px;white-space:nowrap}}
.pill.ok{{background:#16a34a}} .pill.warn{{background:#d97706}} .pill.fail{{background:#dc2626}}
.scroll{{overflow-x:auto}} button{{margin:0 6px 8px 0;padding:4px 10px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer}}
button.on{{background:var(--fg);color:var(--bg)}}
</style></head><body>
<h1>Email deliverability report</h1>
<div class="muted">{escape(account)} · sent mail from the last {days} days · generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
<div class="cards">{cards}</div>
<div class="bar">{bar}</div>
<p>Bounce rate <b>{summary['bounce_rate']}%</b> · confirmed delivered <b>{summary['confirmed_rate']}%</b> · reply rate <b>{summary['reply_rate']}%</b></p>
{warn}
{auth}
<h2>By recipient domain</h2>
<div class="scroll"><table><tr><th>Domain</th><th>Total</th>{dom_head}</tr>{dom_rows}</table></div>
<h2>Messages</h2>
<div><button data-f="" class="on">All</button>{filters}</div>
<div class="scroll"><table id="msgs"><tr><th>Sent</th><th>Subject</th><th>Recipients</th></tr>{''.join(msg_rows)}</table></div>
{unmatched_html}
<h2>How to read this</h2>
<ul>
<li><b>Replied / Auto-reply / Delivery receipt / Read receipt</b> — proof the message reached that person's mailbox.</li>
<li><b>Sent, no bounce</b> — the recipient's server accepted it. That is normal for most mail, but it can't tell inbox from spam folder.</li>
<li><b>Bounced</b> — it was not delivered. "Blocked by recipient server" (5.7.x) is the one that points to a spam or reputation problem.</li>
<li>Opens can only be seen when the recipient sends a read receipt. Most people and many mail apps don't.</li>
</ul>
<script>
document.querySelectorAll('button[data-f]').forEach(b=>b.onclick=()=>{{
  document.querySelectorAll('button[data-f]').forEach(x=>x.classList.toggle('on',x===b));
  document.querySelectorAll('#msgs tr[data-s]').forEach(tr=>tr.style.display=(!b.dataset.f||tr.dataset.s===b.dataset.f)?'':'none');
}});
</script>
</body></html>""")

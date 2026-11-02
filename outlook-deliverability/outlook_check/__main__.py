"""CLI entry point:  python -m outlook_check [--days 14]"""
from __future__ import annotations

import argparse
import sys
import webbrowser
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .analyze import analyze, summarize
from .report import print_summary, write_csv, write_html


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="outlook_check",
        description="Check what happened to the email you sent from Outlook: bounced, delivered, read, replied.",
    )
    p.add_argument("--days", type=int, default=14, help="How far back to look at Sent Items (default 14)")
    p.add_argument("--client-id", default=None, help="Azure app (client) ID, if your tenant blocks the default")
    p.add_argument("--tenant", default="common", help="Tenant ID/domain, or 'common' (default)")
    p.add_argument("--out", default="reports", help="Directory for the HTML/CSV report (default ./reports)")
    p.add_argument("--domain", default=None, help="Sending domain to check SPF/DKIM/DMARC for (default: your address's domain)")
    p.add_argument("--no-dns", action="store_true", help="Skip the SPF/DKIM/DMARC checks")
    p.add_argument("--no-open", action="store_true", help="Don't open the HTML report in a browser")
    p.add_argument("--demo", action="store_true", help="Run on built-in sample data (no sign-in)")
    p.add_argument("--sign-out", action="store_true", help="Forget the cached Microsoft sign-in and exit")
    args = p.parse_args(argv)

    if args.sign_out:
        from .auth import sign_out
        sign_out()
        print("Signed out.")
        return 0

    since = datetime.now(timezone.utc) - timedelta(days=args.days)

    if args.demo:
        from .demo import demo_data
        sent, received, outbox, me = demo_data()
        body_loader = None
    else:
        from .auth import DEFAULT_CLIENT_ID, get_access_token
        from .graph import Graph
        token = get_access_token(args.client_id or DEFAULT_CLIENT_ID, args.tenant)
        g = Graph(token)
        me = g.my_addresses()
        print(f"Reading Sent Items since {since:%Y-%m-%d}…", file=sys.stderr)
        sent = g.sent_items(since)
        outbox = g.outbox_items()
        print(f"  {len(sent)} sent messages. Reading bounces, receipts and replies…", file=sys.stderr)
        received = g.received_since(since)
        body_loader = g.full_body

    results, unmatched = analyze(sent, received, me, body_loader=body_loader)
    summary = summarize(results)

    checks = []
    if not args.no_dns:
        domain = args.domain
        if not domain:
            # Most common domain we sent from.
            domains = Counter(a.split("@")[-1] for a in me if "@" in a and not a.endswith(".onmicrosoft.com"))
            domain = domains.most_common(1)[0][0] if domains else None
        if domain:
            from .dns_check import check_domain
            try:
                checks = check_domain(domain)
            except Exception as e:  # DNS problems shouldn't kill the report
                print(f"DNS check skipped: {e}", file=sys.stderr)

    account = ", ".join(sorted(me)[:3])
    print_summary(summary, outbox, checks, len(unmatched), args.days)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    html_path = out / f"deliverability-{stamp}.html"
    csv_path = out / f"deliverability-{stamp}.csv"
    write_html(html_path, results, summary, outbox, checks, unmatched, args.days, account)
    write_csv(csv_path, results)
    print(f"Report: {html_path.resolve()}\nCSV:    {csv_path.resolve()}")
    if not args.no_open:
        webbrowser.open(html_path.resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())

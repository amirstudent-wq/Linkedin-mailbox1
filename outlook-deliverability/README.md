# Outlook deliverability checker

Reads your Outlook / Microsoft 365 mailbox (read-only) and reports, for every
recipient of every email you sent in the last N days, whether it:

| Status | Evidence |
|---|---|
| **Replied** | A reply from that recipient in the same thread |
| **Opened (read receipt)** | A read receipt came back |
| **Delivered (confirmed)** | A delivery receipt, an out-of-office/auto-reply, or a "deleted without reading" receipt |
| **Sent, no bounce** | Accepted by the recipient's server; nothing else came back |
| **Delayed** | A "delivery delayed" notice; the server is still retrying |
| **Bounced** | A bounce (NDR) came back, with the reason category and SMTP code |

It also:

- lists anything **stuck in your Outbox** (never actually sent)
- works out your **bounce rate**, and the rate per recipient domain, so you can see if one provider (e.g. Gmail) is blocking you
- flags **5.7.x "blocked" bounces**, which are the bounces caused by spam filters or reputation
- checks your sending domain's **SPF, DKIM and DMARC** DNS records. Missing ones are the most common fixable reason mail goes to spam.

Output: a summary in the terminal, an HTML report (opens in your browser) and a CSV, in `./reports/`.

## What no tool can tell you from your mailbox

- **Inbox vs. spam folder.** Once the recipient's server accepts a message, it
  sends nothing back to say which folder it went to. "Sent, no bounce" means
  delivered to the server, not necessarily to the inbox. To measure inbox
  placement you need **seed testing**: send to test accounts you control at
  Gmail, Outlook and Yahoo and see where the mail lands, or use a service such
  as GlockApps or mail-tester.com.
- **Opens** for mail that has already been sent. You only see an open if the
  recipient sends a read receipt. To track opens for future mail, use a
  tracking pixel tool (e.g. HubSpot Sales or Mailtrack). Apple Mail Privacy
  Protection makes pixel "opens" unreliable too.
- **Server-side delivery logs.** If you're a Microsoft 365 admin, Exchange
  admin center → *Mail flow → Message trace* shows each message's hand-off to
  the recipient server.

## Setup

```bash
cd outlook-deliverability
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

python -m outlook_check --demo        # try it on sample data first
python -m outlook_check               # your mailbox, last 14 days
python -m outlook_check --days 30
```

On the first run it prints a code and a URL (`https://microsoft.com/devicelogin`).
Open the URL, enter the code, and sign in with your Outlook account. The tool
asks only for **Mail.Read**. The sign-in is cached in
`~/.cache/outlook-deliverability/` (`--sign-out` clears it).

### If sign-in is blocked by your organisation

By default the tool signs in through Microsoft's own public "Microsoft Graph
Command Line Tools" app. Some company tenants block it ("Need admin
approval"). In that case, either ask your IT admin to approve it, or register
your own app:

1. Go to Entra admin center → App registrations → **New registration**. Choose "Single tenant".
2. Under **Authentication**, set **Allow public client flows** to *Yes*.
3. Under **API permissions**, add Microsoft Graph → Delegated → `Mail.Read`.
4. Run `python -m outlook_check --client-id <Application (client) ID> --tenant <your-domain.com>`.

## Options

```
--days N          How far back to look (default 14)
--domain D        Domain to check SPF/DKIM/DMARC for (default: your address's domain)
--no-dns          Skip the DNS checks
--out DIR         Where to write reports (default ./reports — git-ignored)
--no-open         Don't open the HTML report in a browser
--client-id/--tenant   Use your own Azure app registration
--demo            Sample data, no sign-in
```

## How matching works

The tool reads every message you received in the window, from all folders,
including Junk and Deleted Items. It classifies each one by its Exchange
message class (`REPORT.IPM.Note.NDR`, `.DR`, `.IPNRN`, …), falling back to the
subject line and sender (`postmaster@`, `mailer-daemon@`). It then ties each
one back to a sent message by thread (conversation ID), then by subject, and
then, for Gmail-style bounces with no original subject, by the recipient
address in the bounce body. It assigns the result to the recipient whose
address appears in the notice. Positive proof (reply, read, delivered)
outranks a bounce or delay for the same recipient.

## Tests

```bash
pip install pytest && python -m pytest tests
```

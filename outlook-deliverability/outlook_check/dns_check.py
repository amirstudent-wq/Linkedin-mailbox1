"""SPF / DKIM / DMARC checks for your sending domain.

Missing or broken authentication is the #1 reason legitimate mail lands in spam,
and it is something you can actually fix.
"""
from __future__ import annotations

from dataclasses import dataclass

import dns.exception
import dns.resolver

CONSUMER_DOMAINS = {"outlook.com", "hotmail.com", "live.com", "msn.com", "gmail.com", "yahoo.com", "icloud.com"}


@dataclass
class Check:
    name: str
    status: str  # ok | warn | fail
    detail: str


class DNSUnavailable(Exception):
    pass


def _txt(name: str) -> list[str]:
    try:
        answers = dns.resolver.resolve(name, "TXT", lifetime=10)
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return []
    except (dns.resolver.NoNameservers, dns.exception.Timeout) as e:
        raise DNSUnavailable(str(e)) from e
    return [b"".join(r.strings).decode(errors="replace") for r in answers]


def _cname(name: str) -> str | None:
    try:
        return str(dns.resolver.resolve(name, "CNAME", lifetime=10)[0].target).rstrip(".")
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return None
    except (dns.resolver.NoNameservers, dns.exception.Timeout) as e:
        raise DNSUnavailable(str(e)) from e


def check_domain(domain: str) -> list[Check]:
    domain = domain.lower()
    if domain in CONSUMER_DOMAINS:
        return [Check("Authentication", "ok", f"{domain} is managed by the provider; SPF/DKIM/DMARC are handled for you.")]

    # Sanity check: a resolver that answers "doesn't exist" for everything would
    # otherwise make every record look missing.
    try:
        if not any(t.lower().startswith("v=spf1") for t in _txt("microsoft.com")):
            raise DNSUnavailable("resolver returned no SPF record for microsoft.com")
        return _check(domain)
    except DNSUnavailable as e:
        return [Check("DNS", "warn", f"Couldn't query DNS from this machine, so SPF/DKIM/DMARC weren't checked ({e}).")]


def _check(domain: str) -> list[Check]:
    checks: list[Check] = []

    # SPF
    spf = [t for t in _txt(domain) if t.lower().startswith("v=spf1")]
    if not spf:
        checks.append(Check("SPF", "fail", "No SPF record. Add a TXT record, e.g. 'v=spf1 include:spf.protection.outlook.com -all'."))
    elif len(spf) > 1:
        checks.append(Check("SPF", "fail", f"{len(spf)} SPF records found — only one is allowed, so SPF fails everywhere."))
    else:
        rec = spf[0]
        notes = []
        if "spf.protection.outlook.com" not in rec.lower():
            notes.append("does not include spf.protection.outlook.com (needed if you send through Microsoft 365)")
        if rec.rstrip().endswith("+all"):
            notes.append("ends in +all, which lets anyone spoof you")
        lookups = sum(rec.lower().count(k) for k in ("include:", "a:", "mx", "ptr", "exists:", "redirect="))
        if lookups > 10:
            notes.append(f"~{lookups} DNS lookups (limit is 10)")
        checks.append(Check("SPF", "warn" if notes else "ok", rec if not notes else f"{rec} — " + "; ".join(notes)))

    # DKIM (Microsoft 365 uses selector1/selector2 CNAMEs)
    selectors = {s: _cname(f"{s}._domainkey.{domain}") for s in ("selector1", "selector2")}
    found = {s: t for s, t in selectors.items() if t}
    if found:
        checks.append(Check("DKIM", "ok", "Microsoft 365 DKIM selectors: " + ", ".join(f"{s} → {t}" for s, t in found.items())))
    else:
        checks.append(Check(
            "DKIM", "warn",
            "No Microsoft 365 DKIM selectors (selector1/selector2._domainkey) found. If you send through "
            "Microsoft 365, enable DKIM in the Defender portal (Email authentication settings). "
            "If you use another provider its selector name will differ.",
        ))

    # DMARC
    dmarc = [t for t in _txt(f"_dmarc.{domain}") if t.lower().startswith("v=dmarc1")]
    if not dmarc:
        checks.append(Check("DMARC", "fail", "No DMARC record. Gmail and Yahoo require one for bulk senders. Start with 'v=DMARC1; p=none; rua=mailto:dmarc@" + domain + "'."))
    else:
        rec = dmarc[0]
        policy = next((p.split("=", 1)[1].strip().lower() for p in rec.split(";") if p.strip().lower().startswith("p=")), "")
        if policy == "none":
            checks.append(Check("DMARC", "warn", f"{rec} — policy is p=none (monitoring only). Fine to start; move to quarantine once SPF/DKIM pass."))
        else:
            checks.append(Check("DMARC", "ok", rec))

    return checks

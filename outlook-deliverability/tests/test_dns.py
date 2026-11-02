from outlook_check import dns_check


def _fake(txt, cname):
    return (lambda n: txt.get(n, [])), (lambda n: cname.get(n))


def test_healthy_m365_domain(monkeypatch):
    t, c = _fake(
        {"microsoft.com": ["v=spf1 include:x -all"],
         "acme.com": ["v=spf1 include:spf.protection.outlook.com -all", "google-site-verification=1"],
         "_dmarc.acme.com": ["v=DMARC1; p=quarantine; rua=mailto:d@acme.com"]},
        {"selector1._domainkey.acme.com": "selector1-acme-com._domainkey.acme.onmicrosoft.com"},
    )
    monkeypatch.setattr(dns_check, "_txt", t)
    monkeypatch.setattr(dns_check, "_cname", c)
    checks = {ch.name: ch.status for ch in dns_check.check_domain("acme.com")}
    assert checks == {"SPF": "ok", "DKIM": "ok", "DMARC": "ok"}


def test_broken_domain(monkeypatch):
    t, c = _fake(
        {"microsoft.com": ["v=spf1 include:x -all"],
         "acme.com": ["v=spf1 a -all", "v=spf1 mx -all"],
         "_dmarc.acme.com": ["v=DMARC1; p=none"]},
        {},
    )
    monkeypatch.setattr(dns_check, "_txt", t)
    monkeypatch.setattr(dns_check, "_cname", c)
    checks = {ch.name: ch.status for ch in dns_check.check_domain("acme.com")}
    assert checks == {"SPF": "fail", "DKIM": "warn", "DMARC": "warn"}


def test_dead_resolver_is_not_reported_as_missing_records(monkeypatch):
    t, c = _fake({}, {})
    monkeypatch.setattr(dns_check, "_txt", t)
    monkeypatch.setattr(dns_check, "_cname", c)
    checks = dns_check.check_domain("acme.com")
    assert [ch.name for ch in checks] == ["DNS"]

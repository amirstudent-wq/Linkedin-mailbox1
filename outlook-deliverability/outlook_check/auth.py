"""Microsoft sign-in via the device-code flow, with a local token cache."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import msal

# Microsoft's own public client ("Microsoft Graph Command Line Tools"). Works
# for most work/school and personal accounts without registering an app. If
# your tenant blocks it, register your own app (see README) and pass
# --client-id.
DEFAULT_CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"
SCOPES = ["Mail.Read"]
CACHE_PATH = Path.home() / ".cache" / "outlook-deliverability" / "token_cache.json"


def get_access_token(client_id: str = DEFAULT_CLIENT_ID, tenant: str = "common") -> str:
    cache = msal.SerializableTokenCache()
    if CACHE_PATH.exists():
        cache.deserialize(CACHE_PATH.read_text())

    app = msal.PublicClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant}",
        token_cache=cache,
    )

    result = None
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])

    if not result:
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(f"Could not start sign-in: {flow.get('error_description', flow)}")
        print(flow["message"], file=sys.stderr, flush=True)
        result = app.acquire_token_by_device_flow(flow)

    if "access_token" not in result:
        raise RuntimeError(f"Sign-in failed: {result.get('error_description', result.get('error'))}")

    if cache.has_state_changed:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(CACHE_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(cache.serialize())

    return result["access_token"]


def sign_out() -> None:
    if CACHE_PATH.exists():
        CACHE_PATH.unlink()

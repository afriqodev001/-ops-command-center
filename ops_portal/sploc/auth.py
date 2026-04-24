"""
SPLOC authentication check — verifies the browser has an active SignalFx session.

SignalFx uses enterprise SSO (Okta / ADFS / Azure AD etc.). When the session
is valid, loading the base URL stays on `*.signalfx.com`. When expired, the
IdP takes over and the URL changes to a different host (e.g. okta.com,
login.microsoftonline.com). We rely on that domain change as the signal.

Note: we intentionally do NOT probe a REST API endpoint here — the SignalFx
REST API lives on `api.<realm>.signalfx.com`, not the UI host, so any probe
against the UI host returns 404 / login redirect and gives false negatives
even for a fully authenticated session.
"""
from __future__ import annotations

import time
from urllib.parse import urlparse

from django.conf import settings


def sploc_auth_check(driver, origin_url: str = '') -> bool:
    """Return True if the browser is authenticated to SignalFx."""
    base = (origin_url or getattr(
        settings, 'SPLOC_BASE', 'https://your-org.signalfx.com'
    )).rstrip('/')

    try:
        current = driver.current_url or ''

        # If we're not on the SignalFx domain, navigate there and let SSO settle.
        if 'signalfx.com' not in urlparse(current).netloc.lower():
            driver.get(base)
            time.sleep(3)
            current = driver.current_url or ''

        current_host = urlparse(current).netloc.lower()

        # Authed: we're on the SignalFx domain.
        # Unauthed: IdP redirected us elsewhere (okta, microsoftonline, adfs, pingone…).
        return 'signalfx.com' in current_host
    except Exception:
        return False

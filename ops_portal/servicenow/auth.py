from __future__ import annotations
from django.conf import settings

from servicenow.urls_builders import build_auth_probe_url
from servicenow.services.servicenow_fetch import fetch_json_in_browser


def servicenow_auth_check(driver, origin_url: str) -> bool:
    """
    Stateless auth probe for SeleniumRunner.
    Must:
    - Ensure correct origin is loaded
    - Make one lightweight API call
    - Return True/False only
    """
    try:
        origin = getattr(settings, "SERVICENOW_BASE", origin_url).rstrip("/")
        if not (driver.current_url or "").startswith(origin):
            driver.get(origin)

        url = build_auth_probe_url()
        res = fetch_json_in_browser(driver, method="GET", url=url)
        return bool(res.get("ok") and res.get("status") == 200)
    except Exception:
        return False

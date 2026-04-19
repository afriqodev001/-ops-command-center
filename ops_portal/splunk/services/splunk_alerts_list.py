from __future__ import annotations

from typing import Dict, Any, List
from urllib.parse import urlencode, quote
from django.conf import settings

from splunk.services.splunk_fetch import fetch_json_in_browser


def _base() -> str:
    return getattr(settings, "SPLUNK_BASE", "https://wf-1p.splunkcloud.com").rstrip("/")


def _app() -> str:
    return getattr(settings, "SPLUNK_APP", "wf_ui_app_ctulms").strip()


def build_saved_searches_list_url(
    *,
    namespace_user: str,
    count: int = 200,
    offset: int = 0,
) -> str:
    user_enc = quote(namespace_user, safe="")
    base = f"{_base()}/en-US/splunkd/__raw/servicesNS/{user_enc}/{_app()}/saved/searches"

    params = {
        "output_mode": "json",
        "count": str(int(count)),
        "offset": str(int(offset)),
    }

    return base + "?" + urlencode(params)


def list_saved_searches(
    driver,
    *,
    namespace_user: str,
) -> Dict[str, Any]:
    url = build_saved_searches_list_url(namespace_user=namespace_user)

    headers = {
        "accept": "application/json",
        "x-requested-with": "XMLHttpRequest",
    }

    res = fetch_json_in_browser(
        driver,
        method="GET",
        url=url,
        headers=headers,
    )

    if res.get("error"):
        return res

    data = res.get("data") or {}
    entries = data.get("entry") or []

    alerts: List[Dict[str, Any]] = []

    for e in entries:
        content = e.get("content") or {}

        alerts.append({
            "name": e.get("name"),
            "owner": e.get("acl", {}).get("owner"),
            "app": e.get("acl", {}).get("app"),
            "disabled": bool(content.get("disabled")),
            "is_scheduled": bool(content.get("is_scheduled")),
            "cron_schedule": content.get("cron_schedule"),
            "description": content.get("description"),
        })

    return {
        "ok": True,
        "alerts": alerts,
    }

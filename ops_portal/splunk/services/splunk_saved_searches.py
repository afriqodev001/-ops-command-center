from __future__ import annotations
from typing import Dict, Any, Optional
from urllib.parse import urlencode, quote
from django.conf import settings

from splunk.services.splunk_fetch import fetch_json_in_browser


def _base() -> str:
    return getattr(settings, "SPLUNK_BASE", "https://your-splunk.splunkcloud.com").rstrip("/")


def _app() -> str:
    return getattr(settings, "SPLUNK_APP", "search").strip()


def build_saved_searches_url(
    *,
    namespace_user: str,
    name: str,
    count: int = 1,
    offset: int = 0,
    output_mode: str = "json",
) -> str:
    """
    Query saved searches by exact name.

    Endpoint:
      /servicesNS/<user>/<app>/saved/searches?search=(name="...")
    """
    user_enc = quote(namespace_user, safe="")
    base = f"{_base()}/en-US/splunkd/__raw/servicesNS/{user_enc}/{_app()}/saved/searches"

    # Splunk REST 'search=' filter language
    search_filter = f'(name="{name}")'
    params = {
        "output_mode": output_mode,
        "count": str(int(count)),
        "offset": str(int(offset)),
        "search": search_filter,
    }
    return base + "?" + urlencode(params)


def get_saved_search_by_name(
    driver,
    *,
    namespace_user: str,
    name: str,
) -> Dict[str, Any]:
    """
    Return saved search entry (content) for an exact saved-search name.
    """
    url = build_saved_searches_url(namespace_user=namespace_user, name=name)

    headers = {
        "accept": "application/json",
        "x-requested-with": "XMLHttpRequest",
    }

    res = fetch_json_in_browser(driver, method="GET", url=url, headers=headers)

    if res.get("error"):
        return res

    data = res.get("data") or {}
    entry = data.get("entry") if isinstance(data, dict) else None
    if not isinstance(entry, list) or not entry:
        return {"error": "not_found", "detail": f"Saved search not found: {name}"}

    e0 = entry[0] or {}
    content = e0.get("content") or {}

    return {"ok": True, "entry": e0, "content": content}


def extract_spl_from_saved_search(content: Dict[str, Any]) -> Optional[str]:
    """
    Extract SPL string from saved-search content. Splunk commonly uses 'search'.
    """
    if not isinstance(content, dict):
        return None

    # Most common
    spl = content.get("search")
    if isinstance(spl, str) and spl.strip():
        return spl.strip()

    # Fallbacks seen in some configs
    for k in ("qualifiedSearch", "eai:search", "dispatch.search"):
        v = content.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    return None


def extract_time_bounds_from_saved_search(content: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """
    Best-effort extraction of earliest/latest from saved search.
    """
    earliest = content.get("dispatch.earliest_time") or content.get("dispatch_earliest_time")
    latest = content.get("dispatch.latest_time") or content.get("dispatch_latest_time")

    earliest = earliest.strip() if isinstance(earliest, str) else None
    latest = latest.strip() if isinstance(latest, str) else None

    return earliest or None, latest or None

# splunk/services/splunk_jobs.py
from __future__ import annotations

import re
from typing import Dict, Any, Optional
from urllib.parse import urlencode, quote

from django.conf import settings

from splunk.services.splunk_fetch import fetch_json_in_browser


# ----------------------------
# Helpers: base + app
# ----------------------------

def _base() -> str:
    return getattr(settings, "SPLUNK_BASE", "https://wf-1p.splunkcloud.com").rstrip("/")


def _app() -> str:
    return getattr(settings, "SPLUNK_APP", "wf_ui_app_ctulms").strip()


# ----------------------------
# Helpers: Splunk form key
# ----------------------------

def _get_splunk_form_key(driver) -> Optional[str]:
    """
    Splunk Web CSRF token (x-splunk-form-key).

    In Splunk Web, this is typically available via:
      Splunk.util.getFormKey()
    """
    try:
        return driver.execute_script(
            "return (window.Splunk && Splunk.util && Splunk.util.getFormKey) ? Splunk.util.getFormKey() : null;"
        )
    except Exception:
        return None


def _extract_sid_from_response(raw_text: str, data: Any) -> Optional[str]:
    """
    Extract sid from output_mode=json response (preferred).
    Fallback to parsing <sid>...</sid> from raw text if needed.
    """
    if isinstance(data, dict):
        # Sometimes sid is returned directly
        sid = data.get("sid")
        if isinstance(sid, str) and sid:
            return sid

        # Sometimes nested under entry[0].content
        entry = data.get("entry")
        if isinstance(entry, list) and entry:
            content = (entry[0] or {}).get("content") or {}
            sid2 = content.get("sid") or content.get("search_id")
            if isinstance(sid2, str) and sid2:
                return sid2

    if raw_text:
        m = re.search(r"<sid>([^<]+)</sid>", raw_text)
        if m:
            return m.group(1)

    return None


# ----------------------------
# URL Builders (consolidated)
# ----------------------------

def build_jobs_create_url(*, namespace_user: str) -> str:
    """
    Create job endpoint (POST):
      /servicesNS/<user>/<app>/search/v2/jobs
    """
    user_enc = quote(namespace_user, safe="")
    return f"{_base()}/en-US/splunkd/__raw/servicesNS/{user_enc}/{_app()}/search/v2/jobs"


def build_job_status_url(*, sid: str, namespace_user: str = "nobody") -> str:
    """
    Job status endpoint (GET):
      /servicesNS/<user>/<app>/search/v2/jobs/<sid>?output_mode=json
    """
    user_enc = quote(namespace_user, safe="")
    sid_enc = quote(sid, safe="")
    base = f"{_base()}/en-US/splunkd/__raw/servicesNS/{user_enc}/{_app()}/search/v2/jobs/{sid_enc}"
    return base + "?" + urlencode({"output_mode": "json"})


def build_job_events_url(
    *,
    sid: str,
    namespace_user: str = "nobody",
    offset: int = 0,
    count: int = 20,
    segmentation: str = "full",
    max_lines: int = 5,
    field_list: str = (
        "host,source,sourcetype,_raw,_time,_audit,_decoration,eventtype,"
        "_eventtype_color,linecount,_fulllinecount,_icon,tag*,index"
    ),
    truncation_mode: str = "abstract",
    output_mode: str = "json",
) -> str:
    """
    Events tab endpoint (GET):
      /servicesNS/<user>/<app>/search/v2/jobs/<sid>/events?...output_mode=json...
    """
    user_enc = quote(namespace_user, safe="")
    sid_enc = quote(sid, safe="")
    base = f"{_base()}/en-US/splunkd/__raw/servicesNS/{user_enc}/{_app()}/search/v2/jobs/{sid_enc}/events"

    params = {
        "output_mode": output_mode,
        "offset": str(int(offset)),
        "count": str(int(count)),
        "segmentation": segmentation,
        "max_lines": str(int(max_lines)),
        "field_list": field_list,
        "truncation_mode": truncation_mode,
    }
    return base + "?" + urlencode(params)


def build_job_results_preview_url(
    *,
    sid: str,
    namespace_user: str = "nobody",
    offset: int = 0,
    count: int = 20,
    show_metadata: bool = True,
    add_summary_to_metadata: bool = False,
    output_mode: str = "json_rows",
) -> str:
    """
    Statistics tab preview endpoint (GET):
      /servicesNS/<user>/<app>/search/v2/jobs/<sid>/results_preview?...output_mode=json_rows...
    """
    user_enc = quote(namespace_user, safe="")
    sid_enc = quote(sid, safe="")
    base = f"{_base()}/en-US/splunkd/__raw/servicesNS/{user_enc}/{_app()}/search/v2/jobs/{sid_enc}/results_preview"

    params = {
        "output_mode": output_mode,
        "count": str(int(count)),
        "offset": str(int(offset)),
        "show_metadata": "true" if show_metadata else "false",
        "add_summary_to_metadata": "true" if add_summary_to_metadata else "false",
    }
    return base + "?" + urlencode(params)


# ----------------------------
# Default headers
# ----------------------------

_DEFAULT_GET_HEADERS = {
    "accept": "text/javascript, text/html, application/xml, text/xml, */*",
    "x-requested-with": "XMLHttpRequest",
}

_DEFAULT_POST_HEADERS = {
    "accept": "text/javascript, text/html, application/xml, text/xml, */*",
    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    "x-requested-with": "XMLHttpRequest",
}


# ----------------------------
# Step 1: Create search job -> SID
# ----------------------------

def create_search_job(
    driver,
    *,
    namespace_user: str,
    search: str,
    earliest_time: str = "-10m",
    latest_time: str = "now",
    preview: bool = True,
    adhoc_search_level: str = "verbose",
    extra_params: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Create a Splunk search job and return its SID.

    Uses browser SSO cookies. Auth is determined by HTTP status (401/403).
    """
    url = build_jobs_create_url(namespace_user=namespace_user)

    # Splunk REST typically expects search=search <SPL...>
    s = (search or "").strip()
    if s and not s.lower().startswith("search "):
        s = "search " + s

    headers = dict(_DEFAULT_POST_HEADERS)

    # Pull x-splunk-form-key from Splunk Web if available
    form_key = _get_splunk_form_key(driver)
    if form_key:
        headers["x-splunk-form-key"] = form_key

    params: Dict[str, Any] = {
        "output_mode": "json",
        "search": s,
        "earliest_time": earliest_time,
        "latest_time": latest_time,
        "preview": "1" if preview else "0",
        "adhoc_search_level": adhoc_search_level,
        # Common UI defaults (safe)
        "rf": "*",
        "status_buckets": "300",
    }

    if extra_params:
        for k, v in extra_params.items():
            if v is None:
                continue
            params[str(k)] = str(v)

    body = urlencode(params)

    res = fetch_json_in_browser(
        driver,
        method="POST",
        url=url,
        headers=headers,
        body=body,
    )

    if res.get("error"):
        return res

    sid = _extract_sid_from_response(res.get("raw", "") or "", res.get("data"))
    if not sid:
        return {
            "error": "sid_not_found",
            "detail": "Job created but SID could not be parsed from response",
            "raw": res.get("raw"),
        }

    return {
        "ok": True,
        "sid": sid,
        "response": res.get("data"),
    }


# ----------------------------
# Step 2: Poll job status
# ----------------------------

def get_job_status(
    driver,
    *,
    sid: str,
    namespace_user: str = "nobody",
) -> Dict[str, Any]:
    """
    Fetch job status for a SID.

    Returns normalized status fields plus full `content` for debugging/UI.
    """
    url = build_job_status_url(sid=sid, namespace_user=namespace_user)

    res = fetch_json_in_browser(
        driver,
        method="GET",
        url=url,
        headers=_DEFAULT_GET_HEADERS,
    )

    if res.get("error"):
        return res

    data = res.get("data") or {}
    entry = data.get("entry") if isinstance(data, dict) else None
    content: Dict[str, Any] = {}

    if isinstance(entry, list) and entry:
        content = (entry[0] or {}).get("content") or {}

    is_done = content.get("isDone")
    dispatch_state = content.get("dispatchState")
    done_progress = content.get("doneProgress")

    if isinstance(is_done, str):
        is_done_norm = is_done.lower() in ("1", "true", "yes")
    else:
        is_done_norm = bool(is_done)

    return {
        "ok": True,
        "sid": sid,
        "status": {
            "isDone": is_done_norm,
            "dispatchState": dispatch_state,
            "doneProgress": done_progress,
        },
        "content": content,
    }


# ----------------------------
# Step 3a: Fetch raw events (Events tab)
# ----------------------------

def get_job_events(
    driver,
    *,
    sid: str,
    namespace_user: str = "nobody",
    offset: int = 0,
    count: int = 20,
    segmentation: str = "full",
    max_lines: int = 5,
    field_list: str | None = None,
    truncation_mode: str = "abstract",
) -> Dict[str, Any]:
    url = build_job_events_url(
        sid=sid,
        namespace_user=namespace_user,
        offset=offset,
        count=count,
        segmentation=segmentation,
        max_lines=max_lines,
        field_list=field_list or (
            "host,source,sourcetype,_raw,_time,_audit,_decoration,eventtype,"
            "_eventtype_color,linecount,_fulllinecount,_icon,tag*,index"
        ),
        truncation_mode=truncation_mode,
    )

    return fetch_json_in_browser(
        driver,
        method="GET",
        url=url,
        headers=_DEFAULT_GET_HEADERS,
    )


# ----------------------------
# Step 3b: Fetch results preview (Statistics tab)
# ----------------------------

def get_job_results_preview(
    driver,
    *,
    sid: str,
    namespace_user: str = "nobody",
    offset: int = 0,
    count: int = 20,
    show_metadata: bool = True,
    add_summary_to_metadata: bool = False,
) -> Dict[str, Any]:
    url = build_job_results_preview_url(
        sid=sid,
        namespace_user=namespace_user,
        offset=offset,
        count=count,
        show_metadata=show_metadata,
        add_summary_to_metadata=add_summary_to_metadata,
    )

    return fetch_json_in_browser(
        driver,
        method="GET",
        url=url,
        headers=_DEFAULT_GET_HEADERS,
    )

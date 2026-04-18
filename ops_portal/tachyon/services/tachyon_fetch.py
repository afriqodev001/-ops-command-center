# tachyon/services/tachyon_fetch.py

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from django.conf import settings


def _req_headers(wf_client_id: str = "mlops", wf_api_key: str = "") -> Dict[str, str]:
    corr_id = str(uuid.uuid4())
    req_date = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "x-correlation-id": corr_id,
        "x-request-id": corr_id,
        "x-wf-api-key": wf_api_key or "",
        "x-wf-client-id": wf_client_id,
        "x-wf-request-date": req_date,
    }


def _browser_origin(driver) -> str:
    """
    Return the actual origin of the currently authenticated Tachyon Studio tab.
    """
    try:
        origin = driver.execute_script("return window.location.origin;")
        if origin and isinstance(origin, str):
            return origin.rstrip("/")
    except Exception:
        pass

    base = getattr(settings, "TACHYON_BASE", "https://your-tachyon-instance.net")
    return base.rstrip("/")


def fetch_json_in_browser(
    driver,
    *,
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    body_obj: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generic fetch wrapper executed in browser context.
    Returns { ok, status, statusText, data, raw }.
    """

    timeout_ms = int(getattr(settings, "TACHYON_FETCH_TIMEOUT_MS", 60000))

    script = """
    const method = arguments[0];
    const url = arguments[1];
    const headers = arguments[2] || {};
    const bodyObj = arguments[3];
    const timeoutMs = arguments[4];
    const done = arguments[5];

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    const opts = {
        method: method,
        headers: headers,
        credentials: "include",
        mode: "cors",
        signal: controller.signal
    };

    if (bodyObj !== null && bodyObj !== undefined) {
        opts.body = JSON.stringify(bodyObj);
    }

    fetch(url, opts)
        .then(async resp => {
            const text = await resp.text();
            let data = null;
            try { data = JSON.parse(text); } catch(e) {}
            clearTimeout(timer);
            done({ ok: resp.ok, status: resp.status, statusText: resp.statusText, data: data, raw: text });
        })
        .catch(err => {
            clearTimeout(timer);
            done({ ok: false, status: 0, statusText: "timeout_or_network_error", error: String(err) });
        });
    """

    return driver.execute_async_script(
        script,
        method.upper(),
        url,
        headers or {},
        body_obj,
        timeout_ms,
    )


def get_file_count(driver, user_id: str) -> Dict[str, Any]:
    """
    GET {origin}/file_count_per_user/<userId>
    """

    origin = _browser_origin(driver)
    url = f"{origin}/file_count_per_user/{user_id}"

    res = fetch_json_in_browser(
        driver,
        method="GET",
        url=url,
        headers={"accept": "application/json"},
        body_obj=None,
    )

    if not res.get("ok"):
        raise RuntimeError(f"file_count_per_user failed: {res}")

    return res["data"]


def run_llm(
    driver,
    *,
    body: Dict[str, Any],
    wf_client_id: str = "mlops",
    wf_api_key: str = "",
) -> Dict[str, Any]:
    """
    POST {origin}/playground_document_llm
    """

    origin = _browser_origin(driver)
    url = f"{origin}/playground_document_llm"

    headers = _req_headers(wf_client_id=wf_client_id, wf_api_key=wf_api_key)

    res = fetch_json_in_browser(
        driver,
        method="POST",
        url=url,
        headers=headers,
        body_obj=body,
    )

    if not res.get("ok"):
        return {
            "error": "tachyon_llm_failed",
            "detail": res.get("data") or res.get("error") or res.get("raw"),
            "status": res.get("status"),
            "statusText": res.get("statusText"),
            "origin_used": origin,
        }

    return res["data"]

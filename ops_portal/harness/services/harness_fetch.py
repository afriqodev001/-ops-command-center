# harness/services/harness_fetch.py

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from django.conf import settings


def _req_headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    corr_id = str(uuid.uuid4())
    req_date = datetime.now(timezone.utc).isoformat(timespec="milliseconds")

    hdrs = {
        "accept": "*/*",
        "content-type": "application/json",
        "x-correlation-id": corr_id,
        "x-request-id": corr_id,
        "x-wf-request-date": req_date,
    }

    if extra:
        hdrs.update(extra)

    return hdrs


def browser_fetch(
    driver,
    *,
    url: str,
    method: str = "POST",
    headers: Optional[Dict[str, str]] = None,
    body_obj: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Executes fetch() within the authenticated browser context.

    Returns:
        {
            ok,
            status,
            statusText,
            data,
            raw,
            error?
        }
    """

    timeout_ms = int(getattr(settings, "HARNESS_FETCH_TIMEOUT_MS", 60000))

    script = r"""
    const url = arguments[0];
    const method = arguments[1];
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

            try {
                data = JSON.parse(text);
            } catch (e) {}

            clearTimeout(timer);

            done({
                ok: resp.ok,
                status: resp.status,
                statusText: resp.statusText || "",
                data: data,
                raw: text
            });
        })
        .catch(err => {
            clearTimeout(timer);

            done({
                ok: false,
                status: 0,
                statusText: "timeout_or_network_error",
                error: String(err)
            });
        });
    """

    return driver.execute_async_script(
        script,
        url,
        method.upper(),
        _req_headers(headers),
        body_obj,
        timeout_ms,
    )
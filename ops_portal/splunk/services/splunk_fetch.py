from __future__ import annotations
from typing import Dict, Any
import json


def fetch_json_in_browser(
    driver,
    *,
    method: str,
    url: str,
    headers: Dict[str, str] | None = None,
    body: str | None = None,
) -> Dict[str, Any]:
    """
    Execute a fetch() call inside the browser context.

    Safe version:
    - No JS string interpolation
    - No syntax errors
    - Works reliably in Edge / Chromium
    - Supports GET and POST (with body)
    - Auth determined ONLY by HTTP status (401 / 403)
    """

    headers = headers or {}

    res = driver.execute_async_script(
        """
        const callback = arguments[arguments.length - 1];
        const url = arguments[0];
        const method = arguments[1];
        const headers = arguments[2];
        const body = arguments[3];

        (async () => {
            try {
                const options = {
                    method: method,
                    headers: headers,
                    credentials: "include"
                };

                // Only attach body when provided (POST / PUT etc.)
                if (body !== null && body !== undefined) {
                    options.body = body;
                }

                const response = await fetch(url, options);
                const text = await response.text();

                callback({
                    ok: response.ok,
                    status: response.status,
                    text: text
                });
            } catch (e) {
                callback({
                    ok: false,
                    status: 0,
                    error: String(e)
                });
            }
        })();
        """,
        url,
        method,
        headers,
        body,
    )

    status = res.get("status")

    # --------------------------------------------
    # Unauthorized = authoritative auth signal (Splunk SSO)
    # --------------------------------------------
    if status in (401, 403):
        return {
            "error": "unauthorized",
            "status": status,
            "detail": res.get("text"),
        }

    # --------------------------------------------
    # Success
    # --------------------------------------------
    if res.get("ok"):
        text = res.get("text", "")
        try:
            data = json.loads(text) if text else None
        except Exception:
            data = None

        return {
            "ok": True,
            "status": status,
            "data": data,
            "raw": text,
        }

    # --------------------------------------------
    # Other failure
    # --------------------------------------------
    return {
        "error": "fetch_failed",
        "status": status,
        "detail": res.get("error") or res.get("text"),
    }
from __future__ import annotations
from typing import Any, Dict, Optional
from django.conf import settings


def _sn_user_token(driver) -> Optional[str]:
    """
    Best-effort extraction of ServiceNow user token.
    In classic UI contexts this is often window.g_ck.
    """
    try:
        return driver.execute_script(
            r"""
            return (
                window.g_ck ||
                window.NOW?.user?.token ||
                window.NOW?.user_token ||
                null
            );
            """
        )
    except Exception:
        return None


def fetch_json_in_browser(
    driver,
    *,
    method: str,
    url: str,
    body_obj: Optional[Dict[str, Any]] = None,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Generic fetch() wrapper executed INSIDE the authenticated browser.
    Returns {ok,status,statusText,data,raw,error?} and NEVER throws.
    """
    # Ensure we have at least one same-origin tab loaded so cookies apply
    origin = getattr(settings, "SERVICENOW_BASE", "https://now.wf.com").rstrip("/")
    try:
        cur = driver.current_url or ""
    except Exception:
        cur = ""

    if not cur.startswith(origin):
        driver.get(origin)

    user_token = _sn_user_token(driver)
    hdrs = {"Accept": "application/json"}
    if extra_headers:
        hdrs.update(extra_headers)

    script = r"""
    const method = arguments[0];
    const url = arguments[1];
    const bodyObj = arguments[2];
    const headersIn = arguments[3] || {};
    const userToken = arguments[4];
    const done = arguments[5];

    const headers = { ...(headersIn || {}) };

    // Add content-type for methods with a body
    if (bodyObj !== null && bodyObj !== undefined) {
      headers["Content-Type"] = "application/json";
    }

    if (userToken) {
      headers["X-UserToken"] = userToken;
    }

    const opts = {
      method: method,
      headers: headers,
      credentials: "include",
    };

    if (bodyObj !== null && bodyObj !== undefined) {
      opts.body = JSON.stringify(bodyObj);
    }

    fetch(url, opts)
      .then(async resp => {
        const text = await resp.text();
        let data = null;
        try { data = JSON.parse(text); } catch(e) {}
        done({
          ok: resp.ok,
          status: resp.status,
          statusText: resp.statusText || "",
          data: data,
          raw: text
        });
      })
      .catch(err => done({ ok: false, status: 0, statusText: "network_error", error: String(err) }));
    """

    try:
        res = driver.execute_async_script(script, method.upper(), url, body_obj, hdrs, user_token)
        return res if isinstance(res, dict) else {"ok": False, "status": 0, "error": "bad_result_shape"}
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e)}


def fetch_binary_in_browser(
    driver,
    *,
    method: str,
    url: str,
    raw_bytes: bytes,
    content_type: str,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Send a raw-binary body through the authenticated browser session.

    Used for the ServiceNow attachment endpoint, which rejects JSON wrappers.
    We base64-encode the bytes in Python, decode them back into a Uint8Array
    inside the browser, and post the Uint8Array as the fetch body.

    Returns the same shape as fetch_json_in_browser.
    """
    import base64

    origin = getattr(settings, "SERVICENOW_BASE", "https://now.wf.com").rstrip("/")
    try:
        cur = driver.current_url or ""
    except Exception:
        cur = ""
    if not cur.startswith(origin):
        driver.get(origin)

    user_token = _sn_user_token(driver)
    hdrs = {"Accept": "application/json", "Content-Type": content_type}
    if extra_headers:
        hdrs.update(extra_headers)

    body_b64 = base64.b64encode(raw_bytes or b"").decode("ascii")

    script = r"""
    const method = arguments[0];
    const url = arguments[1];
    const bodyB64 = arguments[2];
    const headersIn = arguments[3] || {};
    const userToken = arguments[4];
    const done = arguments[5];

    const bin = atob(bodyB64);
    const buf = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) {
        buf[i] = bin.charCodeAt(i);
    }

    const headers = { ...(headersIn || {}) };
    if (userToken) {
        headers["X-UserToken"] = userToken;
    }

    fetch(url, {
        method: method,
        headers: headers,
        credentials: "include",
        body: buf,
    })
      .then(async resp => {
        const text = await resp.text();
        let data = null;
        try { data = JSON.parse(text); } catch(e) {}
        done({
            ok: resp.ok,
            status: resp.status,
            statusText: resp.statusText || "",
            data: data,
            raw: text
        });
      })
      .catch(err => done({ ok: false, status: 0, statusText: "network_error", error: String(err) }));
    """

    try:
        res = driver.execute_async_script(script, method.upper(), url, body_b64, hdrs, user_token)
        return res if isinstance(res, dict) else {"ok": False, "status": 0, "error": "bad_result_shape"}
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e)}

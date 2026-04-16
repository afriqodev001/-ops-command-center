from __future__ import annotations

from typing import Any, Dict
from django.conf import settings

from servicenow.services.servicenow_fetch import fetch_json_in_browser


def create_incident_via_table_api(driver, *, fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create an Incident using the ServiceNow Table API.

    Uses the authenticated browser session (cookies/SSO) via fetch_json_in_browser(),
    so no credentials are stored and ServiceNow governance/business rules still apply.

    Endpoint:
        POST {SERVICENOW_BASE}/api/now/table/{SERVICENOW_INCIDENT_TABLE}

    Notes:
    - Required fields may vary depending on instance configuration and business rules.
    - This function does NOT guess required fields. It posts what you provide.
    - On failure, returns a structured error with HTTP status + response detail.
    """
    table = getattr(settings, "SERVICENOW_INCIDENT_TABLE", "incident")
    base = getattr(settings, "SERVICENOW_BASE", "https://now.wf.com").rstrip("/")
    url = f"{base}/api/now/table/{table}"

    payload = dict(fields or {})

    # Optional defaults (safe) — keep minimal to avoid workflow conflicts.
    # You can remove these if you prefer fully explicit inputs only.
    payload.setdefault("active", "true")

    res = fetch_json_in_browser(driver, method="POST", url=url, body_obj=payload)

    if not res.get("ok"):
        return {
            "error": "servicenow_create_failed",
            "status": res.get("status"),
            "detail": res.get("data") or res.get("raw"),
        }

    data = res.get("data") or {}
    result = data.get("result") if isinstance(data, dict) else None

    return {
        "result": result,
        "raw": res,
    }

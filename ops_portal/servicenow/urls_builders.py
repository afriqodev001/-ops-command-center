from __future__ import annotations
from urllib.parse import urlencode
from django.conf import settings


def _base() -> str:
    return settings.SERVICENOW_BASE.rstrip("/")


def build_table_record_url(
    table: str,
    sys_id: str,
    *,
    fields: str = "",
    display_value: bool | None = None,
) -> str:
    """
    Builds:
      {SERVICENOW_BASE}/api/now/table/<table>/<sys_id>?sysparm_fields=...&sysparm_display_value=true
    """
    base = f"{_base()}/api/now/table/{table}/{sys_id}"

    params = {}
    if fields:
        params["sysparm_fields"] = fields
    if display_value is True:
        params["sysparm_display_value"] = "true"

    return base + ("?" + urlencode(params) if params else "")


def build_table_list_url(
    table: str,
    *,
    query: str = "",
    fields: str = "",
    limit: int = 20,
    display_value: bool | None = None,
) -> str:
    """
    Builds:
      {SERVICENOW_BASE}/api/now/table/<table>?sysparm_query=...&sysparm_fields=...&sysparm_limit=...
    """
    base = f"{_base()}/api/now/table/{table}"

    params = {"sysparm_limit": str(int(limit))}
    if query:
        params["sysparm_query"] = query
    if fields:
        params["sysparm_fields"] = fields
    if display_value is True:
        params["sysparm_display_value"] = "true"

    return base + "?" + urlencode(params)


def build_auth_probe_url() -> str:
    """
    Lightweight auth probe that should be allowed for authenticated users.
    """
    return f"{_base()}/api/now/table/sys_user?sysparm_limit=1"


def build_change_create_url(kind: str) -> str:
    """
    Build URL for creating a Normal or Emergency change.
    Uses sys_id=-1 (new record) and relies on SN defaults.
    """
    base = f"{_base()}/now/nav/ui/classic/params/target/change_request.do"

    kind = (kind or "normal").lower()
    if kind not in ("normal", "emergency"):
        kind = "normal"

    params = {
        "sys_id": "-1",
        "sysparm_query": f"type={kind}^chg_model={kind}",
        "sysparm_use_polaris": "true",
    }
    return base + "?" + urlencode(params)


def build_standard_change_template_url(template_cfg: dict) -> str:
    """
    Build URL for creating a Standard change from a template.
    """
    base = f"{_base()}/now/nav/ui/classic/params/target/change_request.do"

    params = {
        "sys_id": "-1",
        "sysparm_query": (
            f"chg_model={template_cfg['chg_model']}"
            f"^std_change_producer_version={template_cfg['std_change_producer_version']}"
        ),
        "sysparm_use_polaris": "true",
        "sysparm_view_forced": "true",
    }
    return base + "?" + urlencode(params)

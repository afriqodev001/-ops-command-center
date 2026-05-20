from __future__ import annotations
from urllib.parse import urlencode
from django.conf import settings


def _base() -> str:
    return settings.SERVICENOW_BASE.rstrip("/")


def _normalize_display_value(dv) -> str | None:
    """Translate the various display_value inputs callers may pass into the
    sysparm_display_value query value.

    Accepts True/False, the strings "true"/"false"/"all", or None. Returns
    None to signal "do not include the param at all" (server default).
    """
    if dv is None:
        return None
    if dv is True:
        return "true"
    if dv is False:
        return "false"
    if isinstance(dv, str):
        s = dv.strip().lower()
        if s in ("true", "false", "all"):
            return s
    return None


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
    dv = _normalize_display_value(display_value)
    if dv is not None:
        params["sysparm_display_value"] = dv

    return base + ("?" + urlencode(params) if params else "")


def build_table_list_url(
    table: str,
    *,
    query: str = "",
    fields: str = "",
    limit: int = 20,
    display_value: bool | None = None,
    suppress_pagination_header: bool = False,
) -> str:
    """
    Builds:
      {SERVICENOW_BASE}/api/now/table/<table>?sysparm_query=...&sysparm_fields=...&sysparm_limit=...

    suppress_pagination_header: when True, adds
      sysparm_suppress_pagination_header=true. ServiceNow builds Link
      response headers that embed the full sysparm_query; a long query
      makes those header URLs exceed an internal limit and the request
      fails. Suppressing them sidesteps that — safe when the caller
      doesn't paginate (the response body is unaffected).
    """
    base = f"{_base()}/api/now/table/{table}"

    params = {"sysparm_limit": str(int(limit))}
    if query:
        params["sysparm_query"] = query
    if fields:
        params["sysparm_fields"] = fields
    dv = _normalize_display_value(display_value)
    if dv is not None:
        params["sysparm_display_value"] = dv
    if suppress_pagination_header:
        params["sysparm_suppress_pagination_header"] = "true"

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

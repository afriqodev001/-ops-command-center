from __future__ import annotations

from typing import Any, Dict, Optional
from django.conf import settings

from servicenow.urls_builders import build_table_record_url, build_table_list_url
from servicenow.services.servicenow_fetch import fetch_json_in_browser


def _unwrap_result(res: Dict[str, Any]) -> Any:
    """
    Table API usually returns { "result": {...} } or { "result": [...] }.
    """
    data = res.get("data")
    if isinstance(data, dict) and "result" in data:
        return data["result"]
    return data


# ============================
# CHANGE REQUESTS
# ============================

def get_change(driver, *, sys_id: str, fields: Optional[str] = None, display_value: bool | None = None) -> Dict[str, Any]:
    table = getattr(settings, "SERVICENOW_CHANGE_TABLE", "change_request")
    fields = fields or getattr(settings, "SERVICENOW_CHANGE_FIELDS", "")
    url = build_table_record_url(table, sys_id, fields=fields, display_value=display_value)

    res = fetch_json_in_browser(driver, method="GET", url=url)
    if not res.get("ok"):
        return {"error": "servicenow_get_failed", "status": res.get("status"), "detail": res.get("data") or res.get("raw")}

    return {"result": _unwrap_result(res), "raw": res}


def patch_change(driver, *, sys_id: str, fields_to_patch: Dict[str, Any]) -> Dict[str, Any]:
    table = getattr(settings, "SERVICENOW_CHANGE_TABLE", "change_request")
    url = build_table_record_url(table, sys_id)

    res = fetch_json_in_browser(driver, method="PATCH", url=url, body_obj=fields_to_patch)
    if not res.get("ok"):
        return {"error": "servicenow_patch_failed", "status": res.get("status"), "detail": res.get("data") or res.get("raw")}

    return {"result": _unwrap_result(res), "raw": res}


# ============================
# INCIDENTS
# ============================

def get_incident(driver, *, sys_id: str, fields: Optional[str] = None, display_value: bool | None = None) -> Dict[str, Any]:
    table = getattr(settings, "SERVICENOW_INCIDENT_TABLE", "incident")
    fields = fields or getattr(settings, "SERVICENOW_INCIDENT_FIELDS", "")
    url = build_table_record_url(table, sys_id, fields=fields, display_value=display_value)

    res = fetch_json_in_browser(driver, method="GET", url=url)
    if not res.get("ok"):
        return {"error": "servicenow_get_failed", "status": res.get("status"), "detail": res.get("data") or res.get("raw")}

    return {"result": _unwrap_result(res), "raw": res}


def patch_incident(driver, *, sys_id: str, fields_to_patch: Dict[str, Any]) -> Dict[str, Any]:
    table = getattr(settings, "SERVICENOW_INCIDENT_TABLE", "incident")
    url = build_table_record_url(table, sys_id)

    res = fetch_json_in_browser(driver, method="PATCH", url=url, body_obj=fields_to_patch)
    if not res.get("ok"):
        return {"error": "servicenow_patch_failed", "status": res.get("status"), "detail": res.get("data") or res.get("raw")}

    return {"result": _unwrap_result(res), "raw": res}


# ============================
# GENERIC TABLE LIST
# ============================

def list_records(
    driver,
    *,
    table: str,
    query: str = "",
    fields: str = "",
    limit: int = 20,
    display_value: bool | None = None,
) -> Dict[str, Any]:
    url = build_table_list_url(
        table,
        query=query,
        fields=fields,
        limit=limit,
        display_value=display_value,
    )

    res = fetch_json_in_browser(driver, method="GET", url=url)
    if not res.get("ok"):
        return {"error": "servicenow_list_failed", "status": res.get("status"), "detail": res.get("data") or res.get("raw")}

    return {"result": _unwrap_result(res), "raw": res}


# ============================
# GENERIC LOOKUPS
# ============================

def _safe_field_name(name: str) -> bool:
    """
    Very small guardrail to avoid arbitrary query injection via field names.
    Allows alphanum + underscore only.
    """
    if not name or not isinstance(name, str):
        return False
    return all(c.isalnum() or c == "_" for c in name)


def get_record_by_field(
    driver,
    *,
    table: str,
    field: str,
    value: str,
    fields: str = "",
    display_value: bool | None = None,
    extra_query: str = "",
):
    """
    Returns the first matching record for `field=value` (limit=1).
    """
    if not _safe_field_name(field):
        return {"error": "invalid_parameter", "detail": f"Invalid field name: {field}"}

    base_query = f"{field}={value}"
    query = base_query if not extra_query else f"{base_query}^{extra_query}"

    url = build_table_list_url(
        table,
        query=query,
        fields=fields,
        limit=1,
        display_value=display_value,
    )

    res = fetch_json_in_browser(driver, method="GET", url=url)
    if not res.get("ok"):
        return {"error": "servicenow_get_failed", "status": res.get("status"), "detail": res.get("data") or res.get("raw")}

    result = _unwrap_result(res) or []
    if not result:
        return {"error": "not_found", "detail": f"No record found for {table}.{field}={value}"}

    return {"result": result[0], "raw": res}


def resolve_sys_id_by_field(
    driver,
    *,
    table: str,
    field: str,
    value: str,
    extra_query: str = "",
):
    """
    Returns sys_id for the first matching record.
    """
    out = get_record_by_field(
        driver,
        table=table,
        field=field,
        value=value,
        fields="sys_id",
        display_value=None,
        extra_query=extra_query,
    )

    if out.get("error"):
        return out

    rec = out.get("result") or {}
    sys_id = rec.get("sys_id")
    if not sys_id:
        return {"error": "not_found", "detail": f"sys_id not returned for {table}.{field}={value}"}

    return {"result": sys_id, "raw": out.get("raw")}


def bulk_get_records_by_field(
    driver,
    *,
    table: str,
    field: str,
    values: list[str],
    fields: str = "",
    limit: int | None = None,
    display_value: bool | None = None,
    extra_query: str = "",
):
    """
    Bulk lookup using ServiceNow IN operator:
        fieldINa,b,c
    """
    if not _safe_field_name(field):
        return {"error": "invalid_parameter", "detail": f"Invalid field name: {field}"}

    values = [v for v in (values or []) if v not in (None, "")]
    if not values:
        return {"error": "missing_parameter", "detail": "values must be a non-empty list"}

    in_clause = f"{field}IN{','.join(values)}"
    query = in_clause if not extra_query else f"{in_clause}^{extra_query}"

    eff_limit = int(limit) if limit is not None else min(len(values), 200)

    url = build_table_list_url(
        table,
        query=query,
        fields=fields,
        limit=eff_limit,
        display_value=display_value,
    )

    res = fetch_json_in_browser(driver, method="GET", url=url)
    if not res.get("ok"):
        return {"error": "servicenow_list_failed", "status": res.get("status"), "detail": res.get("data") or res.get("raw")}

    records = _unwrap_result(res) or []

    by_value = {}
    for r in records:
        key = (r or {}).get(field)
        if key:
            by_value[key] = r

    not_found = [v for v in values if v not in by_value]

    return {
        "result": {
            "found": records,
            "not_found": not_found,
            "by_value": by_value,
        },
        "raw": res,
    }


# ============================
# ATTACHMENTS + CHANGE TASKS
# ============================

def list_attachments_for_record(
    driver,
    *,
    table_name: str,
    table_sys_id: str,
    fields: str = "sys_id,file_name,content_type,size_bytes,download_link,sys_created_on,sys_created_by",
    limit: int = 200,
):
    """
    List attachments metadata for any record.
    """
    query = f"table_name={table_name}^table_sys_id={table_sys_id}^ORDERBYDESCsys_created_on"

    return list_records(
        driver,
        table="sys_attachment",
        query=query,
        fields=fields,
        limit=limit,
        display_value=False,
    )


def list_tasks_for_change(
    driver,
    *,
    change_sys_id: str,
    fields: str = "sys_id,number,short_description,state,assignment_group,assigned_to,sys_updated_on",
    limit: int = 200,
):
    """
    List change_task records related to a Change Request.
    """
    table = getattr(settings, "SERVICENOW_CTASK_TABLE", "change_task")
    query = f"change_request={change_sys_id}^ORDERBY"

    return list_records(
        driver,
        table=table,
        query=query,
        fields=fields,
        limit=limit,
        display_value=True,
    )
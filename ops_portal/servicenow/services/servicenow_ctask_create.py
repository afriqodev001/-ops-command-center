"""
Create a change_task (CTASK) record linked to a parent change_request.

The plan locks the decision: assignment_group is explicitly copied
from the parent CR fields, not left to a business rule. The caller
should include it in `fields` when creating the CTASK.
"""
from __future__ import annotations

from django.conf import settings

from servicenow.services.servicenow_fetch import fetch_json_in_browser


def create_change_task_via_table_api(
    driver,
    *,
    parent_change_sys_id: str,
    fields: dict,
):
    """POST /api/now/table/change_task with change_request link + fields."""
    base = getattr(settings, "SERVICENOW_BASE", "").rstrip("/")
    table = getattr(settings, "SERVICENOW_CTASK_TABLE", "change_task")

    payload = {
        "change_request": parent_change_sys_id,
        "state": "open",
        **(fields or {}),
    }

    url = f"{base}/api/now/table/{table}?sysparm_input_display_value=true"
    return fetch_json_in_browser(
        driver,
        method="POST",
        url=url,
        body_obj=payload,
    )

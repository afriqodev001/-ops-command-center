from __future__ import annotations

# Django / Celery plumbing
from django.conf import settings
from celery import shared_task

# Core browser/session primitives
from core.browser import BrowserLoginRequired
from core.browser.registry import get_or_create_session

# ServiceNow runner (attaches to authenticated Edge session)
from servicenow.runners.servicenow_runner import ServiceNowRunner

# ServiceNow table-level operations (pure data access)
from servicenow.services.servicenow_table import (
    get_change,
    patch_change,
    get_incident,
    patch_incident,
    list_records,
    get_record_by_field,
    bulk_get_records_by_field,
    resolve_sys_id_by_field,
    list_tasks_for_change,
)

# Preset / template support for Ops Command Center UI
from servicenow.services.query_presets import list_presets, render_preset
from servicenow.services.servicenow_incident_create import create_incident_via_table_api

from servicenow.services.servicenow_change_create import (
    create_change_via_table_api,
)

from servicenow.services.servicenow_incident_relations import (
    list_tasks_for_incident,
    list_attachments_for_record,
)


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _user_key(body: dict) -> str:
    """
    Resolves the user_key used to scope browser sessions.
    Falls back to 'localuser' for local/dev usage.
    """
    return (body or {}).get("user_key") or "localuser"


def _strip_raw(obj):
    """Recursively remove 'raw' keys from task results before Celery stores them.

    Every ServiceNow service function returns {"result": ..., "raw": <full HTTP response>}.
    The 'raw' key duplicates the entire response payload (often megabytes for list queries)
    and is never consumed by the async poll renderers. Stripping it keeps the serialized
    result small enough for the django-db result backend to store reliably.
    """
    if isinstance(obj, dict):
        obj.pop('raw', None)
        for v in obj.values():
            if isinstance(v, (dict, list)):
                _strip_raw(v)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                _strip_raw(item)
    return obj


def with_servicenow_auth_retry(
    *,
    body: dict,
    operation,
    retry_once: bool = True,
):
    """
    Executes a ServiceNow operation with automatic login recovery.

    - Catches BrowserLoginRequired
    - Opens login (headed)
    - Optionally retries the operation once
    - Returns structured response instead of crashing task
    """
    user_key = (body or {}).get("user_key") or "localuser"
    runner = ServiceNowRunner(user_key)

    try:
        driver = runner.get_driver()
        return _strip_raw(operation(driver))

    except BrowserLoginRequired as e:
        # Step 1: Open login UI
        try:
            runner.open_login()
        except BrowserLoginRequired:
            # This is expected - login UI opened
            pass

        session = get_or_create_session("servicenow", user_key)

        if not retry_once:
            return {
                "error": "login_required",
                "detail": str(e),
                "action": "login_opened",
                "profile_dir": session.get("profile_dir"),
                "debug_port": session.get("debug_port"),
            }

        # Step 2: Retry once after login
        try:
            driver = runner.get_driver()
            return _strip_raw(operation(driver))
        except BrowserLoginRequired:
            return {
                "error": "login_required",
                "detail": "Login required even after retry",
                "action": "login_opened",
                "profile_dir": session.get("profile_dir"),
                "debug_port": session.get("debug_port"),
            }


# ------------------------------------------------------------
# Login / session bootstrap
# ------------------------------------------------------------
@shared_task(bind=True)
def servicenow_login_open_task(self, body: dict):
    """
    Opens headed ServiceNow login. Returns {profile_dir, debug_port} snapshot from registry.
    """
    from core.browser.registry import get_or_create_session  # your registry source of truth

    body = body or {}
    user_key = _user_key(body)
    runner = ServiceNowRunner(user_key)

    try:
        runner.open_login()
    except BrowserLoginRequired:
        pass

    session = get_or_create_session("servicenow", user_key)
    return {
        "status": "login_opened",
        "profile_dir": session["profile_dir"],
        "debug_port": session["debug_port"],
        "mode": session.get("mode") or "headed",
        "pid": session.get("pid"),
    }


# ------------------------------------------------------------
# Change Requests (sys_id based)
# ------------------------------------------------------------
@shared_task(bind=True)
def changes_get_task(self, body: dict):
    body = body or {}
    sys_id = body.get("sys_id")

    if not sys_id:
        return {
            "error": "missing_parameter",
            "detail": "sys_id is required",
            "example": {"sys_id": "<change_sys_id>"},
        }

    def op(driver):
        return get_change(
            driver,
            sys_id=sys_id,
            fields=body.get("fields"),
            display_value=body.get("display_value"),
        )

    return with_servicenow_auth_retry(
        body=body,
        operation=op,
        retry_once=True,
    )


@shared_task(bind=True)
def changes_patch_task(self, body: dict):
    body = body or {}
    sys_id = body.get("sys_id")
    fields_to_patch = body.get("fields_to_patch")

    if not sys_id:
        return {
            "error": "missing_parameter",
            "detail": "sys_id is required",
            "example": {"sys_id": "<change_sys_id>"},
        }

    if not isinstance(fields_to_patch, dict) or not fields_to_patch:
        return {
            "error": "missing_parameter",
            "detail": "fields_to_patch (non-empty dict) is required",
            "example": {
                "sys_id": "<change_sys_id>",
                "fields_to_patch": {"assignment_group": "<sys_id>"},
            },
        }

    def op(driver):
        return patch_change(
            driver,
            sys_id=sys_id,
            fields_to_patch=fields_to_patch,
        )

    return with_servicenow_auth_retry(
        body=body,
        operation=op,
        retry_once=True,  # ✅ retry is safe; PATCH is idempotent at field level
    )


# ------------------------------------------------------------
# Generic table listing
# ------------------------------------------------------------
@shared_task(bind=True)
def table_list_task(self, body: dict):
    body = body or {}
    table = body.get("table")

    if not table:
        return {
            "error": "missing_parameter",
            "detail": "table is required",
            "example": {"table": "change_request"},
        }

    def op(driver):
        return list_records(
            driver,
            table=table,
            query=body.get("query", ""),
            fields=body.get("fields", ""),
            limit=int(body.get("limit", 20)),
            display_value=body.get("display_value"),
        )

    return with_servicenow_auth_retry(
        body=body,
        operation=op,
        retry_once=True,
    )


# ------------------------------------------------------------
# Change Requests (number based)
# ------------------------------------------------------------
@shared_task(bind=True)
def changes_get_by_number_task(self, body: dict):
    body = body or {}
    number = body.get("number")

    if not number:
        return {
            "error": "missing_parameter",
            "detail": "number is required",
            "example": {"number": "CHG0034567"},
        }

    table = getattr(settings, "SERVICENOW_CHANGE_TABLE", "change_request")

    def op(driver):
        resolved = resolve_sys_id_by_field(
            driver,
            table=table,
            field="number",
            value=number,
        )
        if resolved.get("error"):
            return resolved

        sys_id = resolved["result"]
        return get_change(
            driver,
            sys_id=sys_id,
            fields=body.get("fields"),
            display_value=body.get("display_value"),
        )

    return with_servicenow_auth_retry(
        body=body,
        operation=op,
        retry_once=True,
    )


@shared_task(bind=True)
def changes_bulk_get_by_number_task(self, body: dict):
    body = body or {}
    numbers = body.get("numbers")

    if not isinstance(numbers, list) or not numbers:
        return {
            "error": "missing_parameter",
            "detail": "numbers (non-empty list) is required",
            "example": {"numbers": ["CHG001", "CHG002"]},
        }

    table = getattr(settings, "SERVICENOW_CHANGE_TABLE", "change_request")

    def op(driver):
        return bulk_get_records_by_field(
            driver,
            table=table,
            field="number",
            values=numbers,
            fields=body.get("fields", "")
            or getattr(settings, "SERVICENOW_CHANGE_FIELDS", ""),
            display_value=body.get("display_value"),
            limit=body.get("limit"),
            extra_query=body.get("extra_query", ""),
        )

    return with_servicenow_auth_retry(
        body=body,
        operation=op,
        retry_once=True,
    )


# ------------------------------------------------------------
# Generic get-by-field helpers
# ------------------------------------------------------------
@shared_task(bind=True)
def table_get_by_field_task(self, body: dict):
    body = body or {}
    table = body.get("table")
    field = body.get("field")
    value = body.get("value")

    if not table:
        return {
            "error": "missing_parameter",
            "detail": "table is required",
            "example": {"table": "change_request"},
        }
    if not field:
        return {
            "error": "missing_parameter",
            "detail": "field is required",
            "example": {"field": "number"},
        }
    if value in (None, ""):
        return {
            "error": "missing_parameter",
            "detail": "value is required",
            "example": {"value": "CHG0034567"},
        }

    def op(driver):
        return get_record_by_field(
            driver,
            table=table,
            field=field,
            value=value,
            fields=body.get("fields", ""),
            display_value=body.get("display_value"),
            extra_query=body.get("extra_query", ""),
        )

    return with_servicenow_auth_retry(
        body=body,
        operation=op,
        retry_once=True,
    )


@shared_task(bind=True)
def table_bulk_get_by_field_task(self, body: dict):
    body = body or {}
    table = body.get("table")
    field = body.get("field")
    values = body.get("values")

    if not table:
        return {
            "error": "missing_parameter",
            "detail": "table is required",
            "example": {"table": "change_request"},
        }
    if not field:
        return {
            "error": "missing_parameter",
            "detail": "field is required",
            "example": {"field": "number"},
        }
    if not isinstance(values, list) or not values:
        return {
            "error": "missing_parameter",
            "detail": "values (non-empty list) is required",
            "example": {"values": ["CHG001", "CHG002"]},
        }

    def op(driver):
        return bulk_get_records_by_field(
            driver,
            table=table,
            field=field,
            values=values,
            fields=body.get("fields", ""),
            limit=body.get("limit"),
            display_value=body.get("display_value"),
            extra_query=body.get("extra_query", ""),
        )

    return with_servicenow_auth_retry(
        body=body,
        operation=op,
        retry_once=True,
    )


# ------------------------------------------------------------
# Presets (Ops Command Center UI)
# ------------------------------------------------------------
@shared_task(bind=True)
def presets_list_task(self, body: dict):
    return {"result": list_presets()}


@shared_task(bind=True)
def presets_run_task(self, body: dict):
    body = body or {}
    preset = body.get("preset")
    params = body.get("params") or {}

    if not preset:
        return {
            "error": "missing_parameter",
            "detail": "preset is required",
            "example": {
                "preset": "change_by_number",
                "params": {"number": "CHG0034567"},
            },
        }

    def op(driver):
        try:
            rendered = render_preset(preset, params)
        except Exception as e:
            return {"error": "invalid_preset", "detail": str(e)}

        return list_records(
            driver,
            table=rendered["table"],
            query=rendered["query"],
            fields=body.get("fields", "") or rendered["fields"],
            limit=int(body.get("limit", rendered["limit"])),
            display_value=body.get(
                "display_value", rendered["display_value"]
            ),
        )

    return with_servicenow_auth_retry(
        body=body,
        operation=op,
        retry_once=True,
    )


# ------------------------------------------------------------
# Incidents
# ------------------------------------------------------------
@shared_task(bind=True)
def incidents_get_task(self, body: dict):
    body = body or {}
    sys_id = body.get("sys_id")

    if not sys_id:
        return {
            "error": "missing_parameter",
            "detail": "sys_id is required",
            "example": {"sys_id": "<incident_sys_id>"},
        }

    def op(driver):
        return get_incident(
            driver,
            sys_id=sys_id,
            fields=body.get("fields"),
            display_value=body.get("display_value"),
        )

    return with_servicenow_auth_retry(
        body=body,
        operation=op,
        retry_once=True,
    )


@shared_task(bind=True)
def incidents_patch_task(self, body: dict):
    body = body or {}
    sys_id = body.get("sys_id")
    fields_to_patch = body.get("fields_to_patch")

    if not sys_id:
        return {
            "error": "missing_parameter",
            "detail": "sys_id is required",
            "example": {"sys_id": "<incident_sys_id>"},
        }

    if not isinstance(fields_to_patch, dict) or not fields_to_patch:
        return {
            "error": "missing_parameter",
            "detail": "fields_to_patch (non-empty dict) is required",
            "example": {
                "sys_id": "<incident_sys_id>",
                "fields_to_patch": {"assignment_group": "<sys_id>"},
            },
        }

    def op(driver):
        return patch_incident(
            driver,
            sys_id=sys_id,
            fields_to_patch=fields_to_patch,
        )

    return with_servicenow_auth_retry(
        body=body,
        operation=op,
        retry_once=True,
    )


##
@shared_task(bind=True)
def incident_context_task(self, body: dict):
    """
    Unified Incident Context:
    - Incident
    - Incident attachments
    - Incident tasks + their attachments
    """
    body = body or {}
    incident_sys_id = body.get("incident_sys_id") or body.get("sys_id")
    incident_number = body.get("incident_number")

    if not incident_sys_id and not incident_number:
        return {
            "error": "missing_parameter",
            "detail": "incident_sys_id or incident_number is required",
            "example": {
                "incident_sys_id": "<incident_sys_id>",
                "incident_number": "INC0012345",
            },
        }


    def op(driver):
        # ------------------------------------------------------------
        # 1) Resolve sys_id if incident_number provided
        # ------------------------------------------------------------
        resolved_sys_id = incident_sys_id
        if not resolved_sys_id:
            resolved = resolve_sys_id_by_field(
                driver,
                table=settings.SERVICENOW_INCIDENT_TABLE,
                field="number",
                value=incident_number,
            )
            if resolved.get("error"):
                return resolved
            resolved_sys_id = resolved["result"]

        # ------------------------------------------------------------
        # 2) Fetch Incident
        # ------------------------------------------------------------
        incident_out = get_incident(
            driver,
            sys_id=resolved_sys_id,
            fields=body.get("incident_fields")
            or settings.SERVICENOW_INCIDENT_FIELDS,
            display_value=body.get("display_value"),
        )
        if incident_out.get("error"):
            return incident_out

        # ------------------------------------------------------------
        # 3) Incident attachments
        # ------------------------------------------------------------
        incident_attachments_out = list_attachments_for_record(
            driver,
            table_name=settings.SERVICENOW_INCIDENT_TABLE,
            table_sys_id=resolved_sys_id,
            fields=body.get("attachment_fields")
            or settings.SERVICENOW_ATTACHMENT_FIELDS,
        )

        # ------------------------------------------------------------
        # 4) Incident tasks
        # ------------------------------------------------------------
        tasks_out = list_tasks_for_incident(
            driver,
            incident_sys_id=resolved_sys_id,
            fields=body.get("task_fields")
            or settings.SERVICENOW_INCIDENT_TASK_FIELDS,
        )

        tasks = tasks_out.get("result") or []

        # ------------------------------------------------------------
        # 5) Attachments per task
        # ------------------------------------------------------------
        tasks_with_attachments = []
        for task in tasks:
            task_sys_id = task.get("sys_id")
            if not task_sys_id:
                continue

            task_attachments_out = list_attachments_for_record(
                driver,
                table_name=settings.SERVICENOW_INCIDENT_TASK_TABLE,
                table_sys_id=task_sys_id,
                fields=body.get("attachment_fields")
                or settings.SERVICENOW_ATTACHMENT_FIELDS,
            )

            tasks_with_attachments.append({
                "task": task,
                "attachments": task_attachments_out.get("result") or [],
            })

        # ------------------------------------------------------------
        # 6) Final shape
        # ------------------------------------------------------------
        return {
            "result": {
                "incident": incident_out.get("result"),
                "incident_attachments": incident_attachments_out.get("result") or [],
                "tasks": tasks_with_attachments,
            },
            "meta": {
                "resolved_sys_id": resolved_sys_id,
                "input": {
                    "incident_sys_id": incident_sys_id,
                    "incident_number": incident_number,
                },
            },
        }

    return with_servicenow_auth_retry(
        body=body,
        operation=op,
        retry_once=True,
    )


##
@shared_task(bind=True)
def incidents_create_task(self, body: dict):
    """
    Create an Incident (Table API).

    Request body:
    {
        "user_key": "...",
        "fields": {
            "short_description": "...",
            "description": "...",
            "impact": "3",
            "urgency": "3",
            "assignment_group": "<sys_id>",
            ...
        }
    }

    Returns:
    - { "result": {sys_id, number, ...}, "raw": ... } on success
    - { "error": "...", "status": <http>, "detail": ... } on ServiceNow API failure
    - { "error": "login_required", ... } if auth expired (auto login open handled)
    """
    body = body or {}
    fields = body.get("fields")

    if not isinstance(fields, dict) or not fields:
        return {
            "error": "missing_parameter",
            "detail": "fields (non-empty dict) is required",
            "example": {
                "fields": {
                    "short_description": "Example incident",
                    "description": "What happened, impact, troubleshooting performed",
                    "impact": "3",
                    "urgency": "3",
                }
            },
        }

    def op(driver):
        return create_incident_via_table_api(driver, fields=fields)

    return with_servicenow_auth_retry(
        body=body,
        operation=op,
        retry_once=True,
    )


@shared_task(bind=True)
def incident_get_by_field_task(self, body: dict):
    body = body or {}
    table = getattr(settings, "SERVICENOW_INCIDENT_TABLE", "incident")
    field = body.get("field")
    value = body.get("value")

    if not field:
        return {
            "error": "missing_parameter",
            "detail": "field is required",
            "example": {"field": "number"},
        }
    if value in (None, ""):
        return {
            "error": "missing_parameter",
            "detail": "value is required",
            "example": {"value": "INC0012345"},
        }

    def op(driver):
        resolved = resolve_sys_id_by_field(
            driver,
            table=table,
            field=field,
            value=value,
        )
        if resolved.get("error"):
            return resolved

        return get_incident(
            driver,
            sys_id=resolved["result"],
            fields=body.get("fields")
            or settings.SERVICENOW_INCIDENT_FIELDS,
            display_value=body.get("display_value"),
        )

    return with_servicenow_auth_retry(
        body=body,
        operation=op,
        retry_once=True,
    )


@shared_task(bind=True)
def incident_bulk_get_by_field_task(self, body: dict):
    body = body or {}
    table = getattr(settings, "SERVICENOW_INCIDENT_TABLE", "incident")
    field = body.get("field")
    values = body.get("values")

    if not field:
        return {
            "error": "missing_parameter",
            "detail": "field is required",
            "example": {"field": "number"},
        }
    if not isinstance(values, list) or not values:
        return {
            "error": "missing_parameter",
            "detail": "values (non-empty list) is required",
            "example": {"values": ["INC001", "INC002"]},
        }

    def op(driver):
        return bulk_get_records_by_field(
            driver,
            table=table,
            field=field,
            values=values,
            fields=body.get("fields")
            or settings.SERVICENOW_INCIDENT_FIELDS,
            display_value=body.get("display_value"),
            limit=body.get("limit"),
        )

    return with_servicenow_auth_retry(
        body=body,
        operation=op,
        retry_once=True,
    )


@shared_task(bind=True)
def incident_presets_list_task(self, body: dict):
    return {
        "result": list_presets().get("incident", {})
    }


@shared_task(bind=True)
def incident_presets_run_task(self, body: dict):
    body = body or {}
    preset = body.get("preset")
    params = body.get("params") or {}

    if not preset:
        return {
            "error": "missing_parameter",
            "detail": "preset is required",
            "example": {
                "preset": "incident_by_number",
                "params": {"number": "INC0012345"},
            },
        }

    def op(driver):
        try:
            rendered = render_preset(preset, params)
        except Exception as e:
            return {"error": "invalid_preset", "detail": str(e)}

        return list_records(
            driver,
            table=rendered["table"],
            query=rendered["query"],
            fields=rendered["fields"],
            limit=int(body.get("limit", rendered["limit"])),
            display_value=rendered["display_value"],
        )

    return with_servicenow_auth_retry(
        body=body,
        operation=op,
        retry_once=True,
    )


# ------------------------------------------------------------
# list attachments for any record
# ------------------------------------------------------------
@shared_task(bind=True)
def attachments_list_task(self, body: dict):
    body = body or {}
    table_name = body.get("table_name")
    table_sys_id = body.get("table_sys_id")

    if not table_name:
        return {
            "error": "missing_parameter",
            "detail": "table_name is required",
            "example": {"table_name": "change_request"},
        }
    if not table_sys_id:
        return {
            "error": "missing_parameter",
            "detail": "table_sys_id is required",
            "example": {"table_sys_id": "<parent_sys_id>"},
        }

    def op(driver):
        return list_attachments_for_record(
            driver,
            table_name=table_name,
            table_sys_id=table_sys_id,
            fields=body.get("fields") or getattr(settings, "SERVICENOW_ATTACHMENT_FIELDS", ""),
            limit=int(body.get("limit", 200)),
        )

    return with_servicenow_auth_retry(body=body, operation=op, retry_once=True)


# ------------------------------------------------------------
# list CTASKs for a Change Request
# ------------------------------------------------------------
@shared_task(bind=True)
def ctasks_list_for_change_task(self, body: dict):
    body = body or {}
    change_sys_id = body.get("change_sys_id")

    if not change_sys_id:
        return {
            "error": "missing_parameter",
            "detail": "change_sys_id is required",
            "example": {"change_sys_id": "<change_sys_id>"},
        }

    def op(driver):
        return list_tasks_for_change(
            driver,
            change_sys_id=change_sys_id,
            fields=body.get("fields") or getattr(settings, "SERVICENOW_CTASK_FIELDS", ""),
            limit=int(body.get("limit", 200)),
        )

    return with_servicenow_auth_retry(body=body, operation=op, retry_once=True)


# ------------------------------------------------------------
# change context task: change + ctasks + attachments
# ------------------------------------------------------------
@shared_task(bind=True)
def change_context_task(self, body: dict):
    body = body or {}

    change_sys_id = body.get("change_sys_id") or body.get("sys_id")
    change_number = body.get("change_number")

    if not change_sys_id and not change_number:
        return {
            "error": "missing_parameter",
            "detail": "change_sys_id or change_number is required",
            "example": {
                "change_sys_id": "<change_sys_id>",
                "change_number": "CHG0034567",
            },
        }

    change_table = getattr(settings, "SERVICENOW_CHANGE_TABLE", "change_request")

    def op(driver):
        # ------------------------------------------------------------
        # 1) Resolve change sys_id (number or sys_id input)
        # ------------------------------------------------------------
        resolved_sys_id = change_sys_id

        if not resolved_sys_id:
            resolved = resolve_sys_id_by_field(
                driver,
                table=change_table,
                field="number",
                value=change_number,
            )
            if resolved.get("error"):
                return resolved
            resolved_sys_id = resolved["result"]

        # ------------------------------------------------------------
        # 2) Fetch Change
        # ------------------------------------------------------------
        change_out = get_change(
            driver,
            sys_id=resolved_sys_id,
            fields=body.get("change_fields")
            or getattr(settings, "SERVICENOW_CHANGE_FIELDS", ""),
            display_value=body.get("display_value"),
        )
        if change_out.get("error"):
            return change_out

        # ------------------------------------------------------------
        # 3) Fetch CTASKs
        # ------------------------------------------------------------
        ctasks_out = list_tasks_for_change(
            driver,
            change_sys_id=resolved_sys_id,
            fields=body.get("ctask_fields")
            or getattr(settings, "SERVICENOW_CTASK_FIELDS", ""),
            limit=int(body.get("ctask_limit", 200)),
        )

        ctasks = ctasks_out.get("result") or []

        # ------------------------------------------------------------
        # 4) Fetch attachments on Change
        # ------------------------------------------------------------
        change_attachments_out = list_attachments_for_record(
            driver,
            table_name=change_table,
            table_sys_id=resolved_sys_id,
            fields=body.get("attachment_fields")
            or getattr(settings, "SERVICENOW_ATTACHMENT_FIELDS", ""),
            limit=int(body.get("attachment_limit", 200)),
        )

        # ------------------------------------------------------------
        # 5) Fetch attachments for each CTASK
        # ------------------------------------------------------------
        ctasks_with_attachments = []

        for task in ctasks:
            ctask_sys_id = task.get("sys_id")
            if not ctask_sys_id:
                continue

            attachments_out = list_attachments_for_record(
                driver,
                table_name="change_task",
                table_sys_id=ctask_sys_id,
                fields=body.get("attachment_fields")
                or getattr(settings, "SERVICENOW_ATTACHMENT_FIELDS", ""),
                limit=int(body.get("attachment_limit", 200)),
            )

            ctasks_with_attachments.append({
                **task,
                "attachments": attachments_out.get("result") or [],
            })

        # ------------------------------------------------------------
        # 6) Final response shape
        # ------------------------------------------------------------
        return {
            "result": {
                "change": change_out.get("result"),
                "change_attachments": change_attachments_out.get("result") or [],
                "ctasks": ctasks_with_attachments,
            },
            "meta": {
                "resolved_sys_id": resolved_sys_id,
                "input": {
                    "change_sys_id": change_sys_id,
                    "change_number": change_number,
                },
            },
        }

    return with_servicenow_auth_retry(
        body=body,
        operation=op,
        retry_once=True,
    )


# ------------------------------------------------------------
# Create Change
# ------------------------------------------------------------
@shared_task(bind=True)
def changes_create_task(self, body: dict):
    """
    Create a Normal or Emergency Change via Table API.

    Request body:
    {
        "user_key": "...",
        "kind": "normal" | "emergency",
        "fields": {
            "short_description": "...",
            "description": "...",
            "assignment_group": "<sys_id>",
            ...
        }
    }
    """
    body = body or {}
    kind = (body.get("kind") or "normal").lower()
    fields = body.get("fields")

    if kind not in ("normal", "emergency"):
        return {
            "error": "invalid_parameter",
            "detail": "kind must be 'normal' or 'emergency'",
        }

    if not isinstance(fields, dict) or not fields:
        return {
            "error": "missing_parameter",
            "detail": "fields (non-empty dict) is required",
            "example": {
                "kind": "normal",
                "fields": {
                    "short_description": "Example change",
                    "assignment_group": "<sys_id>",
                },
            },
        }

    def op(driver):
        return create_change_via_table_api(driver, kind=kind, fields=fields)

    return with_servicenow_auth_retry(body=body, operation=op, retry_once=True)


# ============================================================
# Oncall change review — batch AI review task
# ============================================================

@shared_task(bind=True)
def oncall_run_ai_batch_task(self, body: dict):
    """
    Run the oncall AI review for a list of changes, sequentially, persisting
    each result to its OncallChangeReview row before moving to the next so
    the UI sees progressive updates.

    Body:
      {
        "change_numbers": ["CHG0034567", ...],
        "user_key": "localuser",
        "force": bool,                 # re-run even if already ai_reviewed
      }

    Returns:
      {
        "total": N,
        "ok": [...],
        "skipped": [...],
        "errors": [{"change_number": "...", "detail": "..."}]
      }
    """
    from servicenow.models import OncallChangeReview
    from servicenow.services import oncall_review as orsvc

    body = body or {}
    numbers: list = body.get("change_numbers") or []
    force: bool = bool(body.get("force"))

    out = {
        "total": len(numbers),
        "ok": [],
        "skipped": [],
        "errors": [],
    }

    if not numbers:
        return {**out, "error": "missing_parameter",
                "detail": "change_numbers is required (list of CHG numbers)"}

    for number in numbers:
        review = (
            OncallChangeReview.objects
            .filter(change_number=number)
            .order_by('-window_end', '-updated_at')
            .first()
        )
        if not review:
            out["errors"].append({
                "change_number": number,
                "detail": "no oncall review row for this change — pull it first",
            })
            continue

        if review.ai_run_at and not force:
            out["skipped"].append(number)
            continue

        # Fetch the change record (with description / plans / type) for the prompt.
        ctx_body = {
            "change_number": number,
            "user_key": _user_key(body),
            "display_value": "all",
        }
        ctx_result = change_context_task.apply(args=(ctx_body,)).result or {}
        if isinstance(ctx_result, dict) and ctx_result.get("error"):
            out["errors"].append({
                "change_number": number,
                "detail": ctx_result.get("detail") or ctx_result.get("error"),
            })
            continue

        change_record = (
            (ctx_result.get("change") or {}).get("result")
            if isinstance(ctx_result, dict) else {}
        ) or {}

        try:
            parsed = orsvc.run_ai_review_for(review, change_record)
        except Exception as e:
            out["errors"].append({"change_number": number, "detail": f"AI review failed: {e}"})
            continue

        if parsed.get("_ai_error"):
            out["errors"].append({
                "change_number": number,
                "detail": parsed["_ai_error"],
            })
        else:
            out["ok"].append(number)

    return out


# ============================================================
# Oncall change-review — AI content summary (track 2)
# ============================================================

@shared_task(bind=True)
def oncall_run_cr_briefing_task(self, body: dict):
    """
    Run the change-briefing AI for a single change and persist the
    output as a feedback-log entry on the OncallChangeReview row.
    Reuses the existing 'briefing_review' prompt for parity with the
    bulk-review page.
    """
    from servicenow.models import OncallChangeReview
    from servicenow.services import oncall_review as orsvc

    body = body or {}
    number = (body.get("change_number") or "").strip()
    if not number:
        return {"error": "missing_parameter", "detail": "change_number is required"}

    review = (
        OncallChangeReview.objects
        .filter(change_number=number)
        .order_by("-window_end", "-updated_at")
        .first()
    )
    if not review:
        return {"error": "not_found", "detail": f"No oncall review row for {number}"}

    # Fetch the full change context so the AI sees plans + CTASKs
    ctx_body = {
        "change_number": number,
        "user_key": _user_key(body),
        "display_value": "all",
    }
    ctx_result = change_context_task.apply(args=(ctx_body,)).result or {}
    if isinstance(ctx_result, dict) and ctx_result.get("error"):
        return {
            "error": "change_fetch_failed",
            "detail": ctx_result.get("detail") or ctx_result.get("error"),
        }

    change_record = (
        (ctx_result.get("change") or {}).get("result")
        if isinstance(ctx_result, dict) else {}
    ) or {}

    try:
        result = orsvc.run_cr_briefing_for(review, change_record)
    except Exception as e:
        return {"error": "ai_failed", "detail": str(e)}

    return {"ok": True, "change_number": number, "output_chars": len(result.get("output") or "")}


@shared_task(bind=True)
def oncall_run_content_summary_task(self, body: dict):
    """
    Run the AI content summary for one change. Persists summary text +
    structured payload to OncallChangeReview.
    """
    from servicenow.models import OncallChangeReview
    from servicenow.services import oncall_review as orsvc

    body = body or {}
    number = (body.get("change_number") or "").strip()
    if not number:
        return {"error": "missing_parameter", "detail": "change_number is required"}

    review = (
        OncallChangeReview.objects
        .filter(change_number=number)
        .order_by("-window_end", "-updated_at")
        .first()
    )
    if not review:
        return {"error": "not_found", "detail": f"No oncall review row for {number}"}

    # Fetch full change context for the prompt.
    ctx_body = {
        "change_number": number,
        "user_key": _user_key(body),
        "display_value": "all",
    }
    ctx_result = change_context_task.apply(args=(ctx_body,)).result or {}
    if isinstance(ctx_result, dict) and ctx_result.get("error"):
        return {
            "error": "change_fetch_failed",
            "detail": ctx_result.get("detail") or ctx_result.get("error"),
        }

    change_record = (
        (ctx_result.get("change") or {}).get("result")
        if isinstance(ctx_result, dict) else {}
    ) or {}

    try:
        parsed = orsvc.run_content_summary_for(review, change_record)
    except Exception as e:
        return {"error": "ai_failed", "detail": str(e)}

    if parsed.get("_ai_error"):
        return {"error": "ai_error", "detail": parsed["_ai_error"]}

    return {"ok": True, "change_number": number}


# ============================================================
# Oncall management report — windowed AI narrative
# ============================================================

@shared_task(bind=True)
def oncall_management_report_task(self, body: dict):
    """
    Build a management-facing report for a window. Pulls from existing
    OncallChangeReview rows; does not re-fetch ServiceNow. Returns
    {stats, narrative, headline, top_risks, changes_with_outage,
     recommendations, changes: [...]}.
    """
    from servicenow.models import OncallChangeReview
    from servicenow.services.ai_assist import _call_llm, _extract_json_dict
    from servicenow.services.prompt_store import get_prompt
    from servicenow.services import oncall_review as orsvc
    from datetime import datetime, timezone

    body = body or {}
    start_iso = body.get("window_start") or ""
    end_iso = body.get("window_end") or ""
    label = (body.get("label") or "window").strip()
    is_retrospective = bool(body.get("retrospective"))
    change_numbers = body.get("change_numbers") or []

    def _to_dt(s):
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None

    # Two modes:
    #   1. By change numbers — explicit list, ignores the window
    #   2. By window — scheduled_start in [start, end)
    if isinstance(change_numbers, list) and change_numbers:
        qs = OncallChangeReview.objects.filter(
            change_number__in=change_numbers
        ).order_by("scheduled_start", "change_number")
        win_start = None
        win_end = None
    else:
        win_start = _to_dt(start_iso)
        win_end = _to_dt(end_iso)
        if not win_start or not win_end:
            return {"error": "missing_window",
                    "detail": "window_start and window_end (or change_numbers) is required"}

        qs = OncallChangeReview.objects.filter(
            scheduled_start__gte=win_start,
            scheduled_start__lt=win_end,
        ).order_by("scheduled_start")

    rows = list(qs)

    # If user asked for specific changes, warn about ones not in the DB
    not_found = []
    if isinstance(change_numbers, list) and change_numbers:
        present = {r.change_number for r in rows}
        not_found = [n for n in change_numbers if n not in present]

    # Aggregate stats
    stats = {
        "total": len(rows),
        "by_outcome": {},
        "by_outage_verdict": {},
        "outages_declared": 0,
        "with_issues": 0,
    }
    for r in rows:
        oc = r.actual_outcome or "pending"
        stats["by_outcome"][oc] = stats["by_outcome"].get(oc, 0) + 1
        v = r.ai_outage_likely or "unknown"
        stats["by_outage_verdict"][v] = stats["by_outage_verdict"].get(v, 0) + 1
        if r.outage_declared:
            stats["outages_declared"] += 1
        if (r.issues_summary or "").strip():
            stats["with_issues"] += 1

    # Build the AI prompt input
    changes_payload = []
    for r in rows:
        item = {
            "change_number": r.change_number,
            "short_description": r.short_description,
            "risk": r.risk,
            "assignment_group": r.assignment_group,
            "scheduled_start": r.scheduled_start.isoformat() if r.scheduled_start else None,
            "scheduled_end": r.scheduled_end.isoformat() if r.scheduled_end else None,
            "ai_outage_likely": r.ai_outage_likely,
            "ai_summary_short": (r.ai_summary or "")[:400],
            "content_one_liner": (r.content_summary or "")[:300],
            "outage_declared": r.outage_declared,
            "outage_record": r.outage_record_number,
        }
        if is_retrospective:
            item["actual_outcome"] = r.actual_outcome or ""
            item["issues_summary"] = (r.issues_summary or "")[:400]
        changes_payload.append(item)

    user_prompt = json.dumps({
        "scope_label": label,
        "scope_kind": "by_changes" if (change_numbers and not win_start) else "window",
        "window_start": start_iso,
        "window_end": end_iso,
        "is_retrospective": is_retrospective,
        "stats": stats,
        "changes": changes_payload,
        "change_numbers_not_found": not_found,
    }, indent=2, default=str)

    system = get_prompt("oncall_management_report")
    raw = _call_llm(system, user_prompt) or ""
    parsed = _extract_json_dict(raw) or {}

    return {
        "ok": True,
        "label": label,
        "window_start": start_iso,
        "window_end": end_iso,
        "is_retrospective": is_retrospective,
        "scope_kind": "by_changes" if (change_numbers and not win_start) else "window",
        "requested_change_numbers": change_numbers if isinstance(change_numbers, list) else [],
        "not_found": not_found,
        "stats": stats,
        "headline": parsed.get("headline") or f"Report: {label}",
        "narrative_markdown": parsed.get("narrative_markdown") or "",
        "top_risks": parsed.get("top_risks") or [],
        "changes_with_outage": parsed.get("changes_with_outage") or [],
        "recommendations": parsed.get("recommendations") or [],
        "ai_error": parsed.get("_ai_error"),
        # Plain list for the table on the report page
        "changes": [
            {
                "change_number": r.change_number,
                "short_description": r.short_description,
                "risk": r.risk,
                "assignment_group": r.assignment_group,
                "scheduled_start": r.scheduled_start.isoformat() if r.scheduled_start else None,
                "scheduled_end": r.scheduled_end.isoformat() if r.scheduled_end else None,
                "ai_outage_likely": r.ai_outage_likely,
                "actual_outcome": r.actual_outcome or "",
                "outage_declared": r.outage_declared,
                "outage_record": r.outage_record_number,
                "issues_summary": (r.issues_summary or "")[:300],
                "content_one_liner": (r.content_summary or "")[:200],
            }
            for r in rows
        ],
    }
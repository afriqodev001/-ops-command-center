# harness/tasks.py

from celery import shared_task
from django.conf import settings

from harness.runners.harness_runner import HarnessRunner
from core.browser import BrowserLoginRequired

from harness.services.harness_calls import (
    get_environments,
    get_pipeline_exec_summary,
    get_pipeline_exec_summary_filtered,
    get_inputset_v2,
    get_active_service_instances,
    get_projects,
    get_pipelines_list,
    get_last_success_with_inputset_filtered,
    get_last_successful_execution_filtered,
    get_last_success_by_infra,
)

from core.browser.registry import get_or_create_session


def _user_key(body: dict) -> str:
    # Must match the user_key the sidebar widget uses (session_views.py).
    # When the UI dispatches tasks without an explicit user_key, fall back
    # to 'localuser' so the runner attaches to the existing browser session
    # instead of creating a brand-new (harness, default) session and
    # launching a fresh Edge instance.
    return (body or {}).get("user_key") or "localuser"


def _allow_project_override() -> bool:
    return bool(getattr(settings, "HARNESS_ALLOW_PROJECT_OVERRIDE", False))


def _validate_list_str(val, field: str):
    if val is None:
        return None
    if not isinstance(val, list) or any(not isinstance(x, str) for x in val):
        return {"error": "invalid_parameter", "detail": f"{field} must be a list of strings"}
    return val


# ---------------------------
# LOGIN
# ---------------------------

@shared_task(bind=True)
def open_harness_login_task(self, body: dict):
    user_key = (body or {}).get("user_key") or "localuser"
    runner = HarnessRunner(user_key=user_key)

    try:
        runner.open_login()
    except BrowserLoginRequired:
        pass

    session = get_or_create_session("harness", user_key)

    return {
        "status": "login_opened",
        "profile_dir": session["profile_dir"],
        "debug_port": session["debug_port"],
        "mode": session.get("mode") or "headed",
        "pid": session.get("pid"),
    }


# ---------------------------
# BASIC FETCHES
# ---------------------------

@shared_task(bind=True)
def environments_list_task(self, body: dict):
    runner = HarnessRunner(user_key=_user_key(body))
    driver = runner.get_driver()
    return get_environments(driver)


@shared_task(bind=True)
def pipeline_execution_summary_task(self, body: dict):
    runner = HarnessRunner(user_key=_user_key(body))
    driver = runner.get_driver()

    return get_pipeline_exec_summary(
        driver,
        pipeline_id=body.get("pipeline_id"),
        page=int(body.get("page", 0)),
        size=int(body.get("size", 20)),
    )


# ---------------------------
# FILTERED EXECUTION SUMMARY
# ---------------------------

@shared_task(bind=True)
def pipeline_execution_summary_filtered_task(self, body: dict):
    """
    Exposes Harness UI filters for execution summary.
    """

    body = body or {}

    pipeline_identifier = (
        body.get("pipeline_identifier")
        or body.get("pipeline_id")
        or getattr(settings, "HARNESS_PIPELINE_ID", None)
    )

    if not pipeline_identifier:
        return {"error": "missing_parameter", "detail": "pipeline_identifier is required"}

    service_identifiers = _validate_list_str(body.get("service_identifiers"), "service_identifiers")
    if isinstance(service_identifiers, dict):
        return service_identifiers

    env_identifiers = _validate_list_str(body.get("env_identifiers"), "env_identifiers")
    if isinstance(env_identifiers, dict):
        return env_identifiers

    project_identifier = body.get("project_identifier")
    if project_identifier and not _allow_project_override():
        return {
            "error": "project_override_not_allowed",
            "detail": "Set HARNESS_ALLOW_PROJECT_OVERRIDE=True to allow project_identifier in requests",
        }

    headers = body.get("headers") if isinstance(body.get("headers"), dict) else None

    runner = HarnessRunner(user_key=_user_key(body))
    driver = runner.get_driver()

    return get_pipeline_exec_summary_filtered(
        driver,
        pipeline_identifier=str(pipeline_identifier),
        page=int(body.get("page", 0)),
        size=int(body.get("size", 20)),
        time_range_filter_type=str(body.get("time_range_filter_type", "LAST_30_DAYS")),
        service_identifiers=service_identifiers,
        env_identifiers=env_identifiers,
        project_identifier=project_identifier,
        headers=headers,
    )


# ---------------------------
# INPUTSET
# ---------------------------

@shared_task(bind=True)
def execution_inputset_v2_task(self, body: dict):
    body = body or {}

    execution_id = body.get("execution_id")
    if not execution_id:
        return {
            "error": "missing_parameter",
            "detail": "execution_id is required",
            "example": {"execution_id": "NgExecution_abc123"},
        }

    runner = HarnessRunner(user_key=_user_key(body))
    driver = runner.get_driver()

    return get_inputset_v2(driver, execution_id=execution_id)


# ---------------------------
# ACTIVE INSTANCES
# ---------------------------

@shared_task(bind=True)
def active_service_instances_task(self, body: dict):
    """
    Active service instances for a (project, env) pair.

    project_identifier is intentionally NOT gated by HARNESS_ALLOW_PROJECT_OVERRIDE
    here — Active Instances is a discovery view and the UI form is the
    primary caller, so explicit per-request project selection is the expected
    flow. Falls back to settings.HARNESS_PROJECT_ID when the request omits it.
    """
    body = body or {}

    runner = HarnessRunner(user_key=_user_key(body))
    driver = runner.get_driver()

    return get_active_service_instances(
        driver,
        env_id=body.get("env_id"),
        project_identifier=body.get("project_identifier"),
    )


# ---------------------------
# PROJECTS
# ---------------------------

@shared_task(bind=True)
def projects_list_task(self, body: dict):
    body = body or {}

    runner = HarnessRunner(user_key=_user_key(body))
    driver = runner.get_driver()

    headers = body.get("headers") if isinstance(body.get("headers"), dict) else None

    return get_projects(
        driver,
        page_index=int(body.get("page_index", 0)),
        page_size=int(body.get("page_size", 20)),
        sort_orders=str(body.get("sort_orders", "lastModifiedAt,DESC")),
        only_favorites=bool(body.get("only_favorites", False)),
        headers=headers,
    )


# ---------------------------
# PIPELINES
# ---------------------------

@shared_task(bind=True)
def pipelines_list_task(self, body: dict):
    body = body or {}

    runner = HarnessRunner(user_key=_user_key(body))
    driver = runner.get_driver()

    headers = body.get("headers") if isinstance(body.get("headers"), dict) else None

    return get_pipelines_list(
        driver,
        org_identifier=body.get("org_identifier"),
        project_identifier=body.get("project_identifier"),
        page=int(body.get("page", 0)),
        size=int(body.get("size", 20)),
        sort=str(body.get("sort", "lastUpdatedAt,DESC")),
        filter_type=str(body.get("filter_type", "PipelineSetup")),
        method=str(body.get("method", "POST")).upper(),
        headers=headers,
    )


# ---------------------------
# LAST SUCCESS + INPUTSET
# ---------------------------

@shared_task(bind=True)
def last_success_execution_with_inputset_filtered_task(self, body: dict):
    """
    Body (matches Harness UI filters):
    {
        "pipeline_identifier": "...",
        "time_range_filter_type": "LAST_12_MONTHS",
        "service_identifiers": [...],
        "env_identifiers": [...],
        "project_identifier": "...",
        "headers": {...},
        "user_key": "localuser"
    }
    """

    body = body or {}

    pipeline_identifier = body.get("pipeline_identifier")
    if not pipeline_identifier:
        return {"error": "missing_parameter", "detail": "pipeline_identifier is required"}

    service_identifiers = _validate_list_str(body.get("service_identifiers"), "service_identifiers")
    if isinstance(service_identifiers, dict):
        return service_identifiers

    env_identifiers = _validate_list_str(body.get("env_identifiers"), "env_identifiers")
    if isinstance(env_identifiers, dict):
        return env_identifiers

    project_identifier = body.get("project_identifier")
    if project_identifier and not _allow_project_override():
        return {
            "error": "project_override_not_allowed",
            "detail": "Set HARNESS_ALLOW_PROJECT_OVERRIDE=True to allow project_identifier in requests",
        }

    headers = body.get("headers") if isinstance(body.get("headers"), dict) else None

    runner = HarnessRunner(user_key=_user_key(body))
    driver = runner.get_driver()

    return get_last_success_with_inputset_filtered(
        driver,
        pipeline_identifier=str(pipeline_identifier),
        time_range_filter_type=str(body.get("time_range_filter_type", "LAST_30_DAYS")),
        service_identifiers=service_identifiers,
        env_identifiers=env_identifiers,
        project_identifier=project_identifier,
        headers=headers,
        # include_raw=bool(body.get("include_raw", False)),
    )


# ---------------------------
# PLAN FETCH (COMBINED)
# ---------------------------

@shared_task(bind=True)
def fetch_plan_task(self, body: dict):
    body = body or {}

    runner = HarnessRunner(user_key=_user_key(body))
    driver = runner.get_driver()

    out = {}

    out["environments_listV2"] = get_environments(driver)

    out["pipeline_execution_summary"] = get_pipeline_exec_summary(
        driver,
        pipeline_id=body.get("pipeline_id"),
        page=int(body.get("page", 0)),
        size=int(body.get("size", 20)),
    )

    if body.get("execution_id"):
        out["execution_inputsetV2"] = get_inputset_v2(
            driver,
            execution_id=body["execution_id"],
        )

    out["active_service_instances"] = get_active_service_instances(
        driver,
        env_id=body.get("env_id"),
        project_identifier=body.get("project_identifier"),
    )

    return out


# ---------------------------
# LAST SUCCESS BY INFRA
# ---------------------------

@shared_task(bind=True)
def last_success_by_infra_task(self, body: dict):
    body = body or {}

    pipeline_identifier = body.get("pipeline_identifier")
    if not pipeline_identifier:
        return {"error": "missing_parameter", "detail": "pipeline_identifier is required"}

    project_identifier = body.get("project_identifier")
    infra_identifiers = body.get("infra_identifiers")

    runner = HarnessRunner(user_key=_user_key(body))
    driver = runner.get_driver()

    if not infra_identifiers:
        return {
            "error": "missing_parameter",
            "detail": "infra_identifiers is required (or set discover_infrastructure=true)",
        }

    return get_last_success_by_infra(
        driver,
        pipeline_identifier=pipeline_identifier,
        project_identifier=project_identifier,
        service_identifiers=body.get("service_identifiers"),
        env_identifiers=body.get("env_identifiers"),
        infra_identifiers=infra_identifiers,
        time_range_filter_type=body.get("time_range_filter_type", "LAST_30_DAYS"),
    )
# harness/urls_builders.py

from urllib.parse import quote
from django.conf import settings


def _base():
    return settings.HARNESS_BASE.rstrip("/")


def _acct():
    return settings.HARNESS_ACCOUNT_ID


def _org():
    return settings.HARNESS_ORG_ID


def _proj():
    return settings.HARNESS_PROJECT_ID


def _allow_project_override() -> bool:
    return bool(getattr(settings, "HARNESS_ALLOW_PROJECT_OVERRIDE", False))


def _resolve_project(project_identifier: str | None) -> str:
    """
    Project override is gated by settings.HARNESS_ALLOW_PROJECT_OVERRIDE.
    Tasks will validate and return a structured error if override is not allowed.
    """
    return project_identifier or _proj()


# ---------------------------
# ENVIRONMENTS
# ---------------------------

def build_env_list():
    url = (
        f"{_base()}/gateway/ng/api/environmentsV2/listV2"
        f"?routingId={_acct()}"
        f"&accountIdentifier={_acct()}"
        f"&orgIdentifier={_org()}"
        f"&projectIdentifier={_proj()}"
        f"&size=100"
        f"&includeAllAccessibleAtScope=true"
    )
    body = {"filterType": "Environment"}
    return url, body


# ---------------------------
# PIPELINE EXEC SUMMARY (LEGACY WRAPPER)
# ---------------------------

def build_pipeline_exec_summary(
    pipeline_id: str | None = None,
    page: int = 0,
    size: int = 20,
):
    """
    Backward-compatible default summary call used by existing code.
    """
    pipeline = pipeline_id or settings.HARNESS_PIPELINE_ID

    return build_pipeline_exec_summary_filtered(
        pipeline_identifier=pipeline,
        page=page,
        size=size,
        sort="startTs,DESC",
        my_deployments=False,
        search_term="",
        time_range_filter_type="LAST_30_DAYS",
        service_identifiers=None,
        env_identifiers=[settings.HARNESS_ENV_ID, "account.prod"],
        statuses=None,
        project_identifier=None,
    )


# ---------------------------
# PIPELINE EXEC SUMMARY (FILTERED)
# ---------------------------

def build_pipeline_exec_summary_filtered(
    *,
    pipeline_identifier: str,
    page: int = 0,
    size: int = 20,
    sort: str = "startTs,DESC",
    my_deployments: bool = False,
    search_term: str = "",
    time_range_filter_type: str = "LAST_30_DAYS",
    service_identifiers: list[str] | None = None,
    env_identifiers: list[str] | None = None,
    infra_identifiers: list[str] | None = None,
    statuses: list[str] | None = None,
    project_identifier: str | None = None,
):
    """
    Matches the Harness UI execution summary POST with filters.
    """

    proj = _resolve_project(project_identifier)
    sort_q = quote(sort, safe="")

    url = (
        f"{_base()}/gateway/pipeline/api/pipelines/execution/summary"
        f"?routingId={_acct()}"
        f"&accountIdentifier={_acct()}"
        f"&projectIdentifier={proj}"
        f"&orgIdentifier={_org()}"
        f"&pipelineIdentifier={pipeline_identifier}"
        f"&page={int(page)}"
        f"&size={int(size)}"
        f"&sort={sort_q}"
        f"&myDeployments={'true' if my_deployments else 'false'}"
        f"&searchTerm={quote(search_term or '', safe='')}"
    )

    cd_props: dict = {}

    if service_identifiers:
        cd_props["serviceIdentifiers"] = service_identifiers

    if env_identifiers:
        cd_props["envIdentifiers"] = env_identifiers

    if infra_identifiers:
        cd_props["infrastructureIdentifiers"] = infra_identifiers

    body: dict = {
        "filterType": "PipelineExecution",
        "myDeployments": bool(my_deployments),
        "timeRange": {"timeRangeFilterType": time_range_filter_type},
        "moduleProperties": {"ci": {}, "cd": cd_props},
    }

    if statuses:
        body["statuses"] = statuses

    return url, body


# ---------------------------
# LAST SUCCESS (FILTER BUILDER)
# ---------------------------

def build_last_success_filtered(
    *,
    pipeline_identifier: str,
    time_range_filter_type: str = "LAST_30_DAYS",
    service_identifiers: list[str] | None = None,
    env_identifiers: list[str] | None = None,
    infra_identifiers: list[str] | None = None,
    project_identifier: str | None = None,
):
    """
    Latest SUCCESS execution for a pipeline under given filters.
    """
    return build_pipeline_exec_summary_filtered(
        pipeline_identifier=pipeline_identifier,
        page=0,
        size=1,
        sort="startTs,DESC",
        my_deployments=False,
        search_term="",
        time_range_filter_type=time_range_filter_type,
        service_identifiers=service_identifiers,
        env_identifiers=env_identifiers,
        infra_identifiers=infra_identifiers,
        statuses=["SUCCESS"],
        project_identifier=project_identifier,
    )


# ---------------------------
# INPUTSET
# ---------------------------

def build_inputset_v2(execution_id: str):
    url = (
        f"{_base()}/gateway/pipeline/api/pipelines/execution/{execution_id}/inputsetV2"
        f"?routingId={_acct()}"
        f"&orgIdentifier={_org()}"
        f"&resolveExpressions=true"
        f"&projectIdentifier={_proj()}"
        f"&accountIdentifier={_acct()}"
    )
    return url


# ---------------------------
# ACTIVE SERVICE INSTANCES
# ---------------------------

def build_active_service_instances(env_id: str | None = None):
    env = env_id or settings.HARNESS_ENV_ID

    url = (
        f"{_base()}/gateway/ng/api/environmentsV2/getActiveServiceInstancesForEnvironment"
        f"?routingId={_acct()}"
        f"&accountIdentifier={_acct()}"
        f"&orgIdentifier={_org()}"
        f"&projectIdentifier={_proj()}"
        f"&environmentIdentifier={env}"
    )

    return url


# ---------------------------
# PROJECTS (AGGREGATE)
# ---------------------------

def build_projects_aggregate(
    *,
    page_index: int = 0,
    page_size: int = 20,
    sort_orders: str = "lastModifiedAt,DESC",
    only_favorites: bool = False,
):
    sort_q = quote(sort_orders, safe="")
    fav_q = "true" if only_favorites else "false"

    url = (
        f"{_base()}/gateway/ng/api/aggregate/projects"
        f"?routingId={_acct()}"
        f"&accountIdentifier={_acct()}"
        f"&pageIndex={int(page_index)}"
        f"&pageSize={int(page_size)}"
        f"&sortOrders={sort_q}"
        f"&onlyFavorites={fav_q}"
    )

    return url


# ---------------------------
# PIPELINES LIST
# ---------------------------

def build_pipelines_list(
    *,
    org_identifier: str | None = None,
    project_identifier: str | None = None,
    page: int = 0,
    size: int = 20,
    sort: str = "lastUpdatedAt,DESC",
):
    org = org_identifier or _org()
    proj = project_identifier or _proj()
    sort_q = quote(sort, safe="")

    url = (
        f"{_base()}/gateway/pipeline/api/pipelines/list"
        f"?routingId={_acct()}"
        f"&accountIdentifier={_acct()}"
        f"&projectIdentifier={proj}"
        f"&orgIdentifier={org}"
        f"&page={int(page)}"
        f"&sort={sort_q}"
        f"&size={int(size)}"
    )

    return url
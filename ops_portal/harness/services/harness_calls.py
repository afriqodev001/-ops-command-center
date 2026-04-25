# harness/services/harness_calls.py
import html
import json
from typing import Any, Dict, Optional, List

from harness.services.harness_fetch import browser_fetch
from harness import urls_builders


def get_environments(driver) -> Dict[str, Any]:
    url, body = urls_builders.build_env_list()
    return browser_fetch(driver, url=url, method="POST", body_obj=body)


def get_pipeline_exec_summary(
    driver,
    *,
    pipeline_id: Optional[str] = None,
    page: int = 0,
    size: int = 20,
) -> Dict[str, Any]:
    """
    Backward-compatible existing call (no service/env filters exposed).
    """
    url, body = urls_builders.build_pipeline_exec_summary(
        pipeline_id=pipeline_id,
        page=page,
        size=size,
    )
    return browser_fetch(driver, url=url, method="POST", body_obj=body)


def get_pipeline_exec_summary_filtered(
    driver,
    *,
    pipeline_identifier: str,
    page: int = 0,
    size: int = 20,
    time_range_filter_type: str = "LAST_30_DAYS",
    service_identifiers: Optional[List[str]] = None,
    env_identifiers: Optional[List[str]] = None,
    project_identifier: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Execution summary using Harness UI filters (service/env/timeRange).
    """
    url, body = urls_builders.build_pipeline_exec_summary_filtered(
        pipeline_identifier=pipeline_identifier,
        page=page,
        size=size,
        time_range_filter_type=time_range_filter_type,
        service_identifiers=service_identifiers,
        env_identifiers=env_identifiers,
        statuses=None,
        project_identifier=project_identifier,
    )

    raw = browser_fetch(
        driver,
        url=url,
        method="POST",
        headers=headers,
        body_obj=body,
    )

    return _extract_meaningful_pipeline_exec_summary_filtered(
        raw,
        pipeline_identifier=pipeline_identifier,
        project_identifier=project_identifier,
        page=page,
        size=size,
    )


def _safe_json_loads(maybe_json: Any) -> dict:
    """Parse JSON if it's a string; otherwise return {} safely."""
    if not maybe_json or not isinstance(maybe_json, str):
        return {}
    try:
        return json.loads(maybe_json)
    except Exception:
        return {}


def _extract_vars_from_service_inputs(node: dict) -> Dict[str, Any]:
    """
    Extract variables like imageTag/githubBranch from the serviceInputs JSON string
    located under node.strategyMetadata.matrixMetadata.matrixValues.serviceInputs.
    """
    matrixvalues = (
        (node.get("strategyMetadata") or {})
        .get("matrixMetadata", {})
        .get("matrixValues", {})
    )

    service_inputs_raw = matrixvalues.get("serviceInputs")
    service_inputs = _safe_json_loads(service_inputs_raw)

    spec = (
        (service_inputs.get("serviceDefinition") or {})
        .get("spec") or {}
    )

    variables_list = spec.get("variables") or []

    out: Dict[str, Any] = {}
    for v in variables_list:
        if isinstance(v, dict) and v.get("name"):
            out[str(v["name"])] = v.get("value")

    return out


def _extract_meaningful_pipeline_exec_summary_filtered(
    raw: dict,
    *,
    pipeline_identifier: str,
    project_identifier: Optional[str] = None,
    page: Optional[int] = None,
    size: Optional[int] = None,
) -> dict:
    """
    Reduce Harness execution/summary (filtered) payload to meaningful execution + deployment info.
    """

    data = (raw.get("data") or {}).get("data") or {}
    content = data.get("content") or []

    executions: List[dict] = []

    for ex in content:
        # execution-level essentials
        plan_execution_id = ex.get("planExecutionId")
        run_sequence = ex.get("runSequence")
        status = ex.get("status")
        start_ts = ex.get("startTs")
        end_ts = ex.get("endTs")

        trigger_info = ex.get("executionTriggerInfo") or {}
        triggered_by = trigger_info.get("triggeredBy") or {}
        triggered_extra = triggered_by.get("extraInfo") or {}

        exec_error = ex.get("executionErrorInfo") or {}
        failure_info = ex.get("failureInfo") or {}
        failure_msg = (
            exec_error.get("message")
            or failure_info.get("message")
        )

        # deployment extraction
        deployments: List[dict] = []
        layout = ex.get("layoutNodeMap") or {}

        for node in layout.values():
            if (node.get("module") or "").lower() != "cd":
                continue
            if (node.get("nodeType") or "").lower() != "deployment":
                continue

            cd = (node.get("moduleInfo") or {}).get("cd") or {}
            infra_sum = cd.get("infraExecutionSummary") or {}
            svc_info = cd.get("serviceInfo") or {}

            matrixvalues = (
                (node.get("strategyMetadata") or {})
                .get("matrixMetadata", {})
                .get("matrixValues", {})
            )

            service_ref = (
                matrixvalues.get("serviceRef")
                or svc_info.get("identifier")
            )

            artifacts = svc_info.get("artifacts") or {}
            primary = artifacts.get("primary") or {}
            artifact_version = primary.get("version")

            vars_from_inputs = _extract_vars_from_service_inputs(node)
            image_tag = vars_from_inputs.get("imageTag")
            github_branch = vars_from_inputs.get("githubBranch")

            manifest = svc_info.get("manifestInfo") or {}
            manifest_repo = manifest.get("repoName")
            manifest_branch = manifest.get("branch")
            chart_name = manifest.get("chartName")
            chart_version = manifest.get("chartVersion")

            deployments.append({
                "node_execution_id": node.get("nodeExecutionId"),
                "node_status": node.get("status"),
                "node_start_ts": node.get("startTs"),
                "node_end_ts": node.get("endTs"),

                "service_ref": service_ref,
                "artifact_version": artifact_version,
                "image_tag": image_tag,
                "github_branch": github_branch,

                "environment": infra_sum.get("identifier"),
                "environment_group": (
                    infra_sum.get("envGroupName")
                    or infra_sum.get("envGroupId")
                ),
                "infrastructure_identifier": infra_sum.get("infrastructureIdentifier"),
                "infrastructure_name": infra_sum.get("infrastructureName"),

                "repo_name": manifest_repo,
                "repo_branch": manifest_branch,
                "chart_name": chart_name,
                "chart_version": chart_version,
            })

        executions.append({
            "pipeline_identifier": ex.get("pipelineIdentifier") or pipeline_identifier,
            "project_identifier": ex.get("projectIdentifier") or project_identifier,

            "execution_id": plan_execution_id,
            "run_sequence": run_sequence,
            "status": status,
            "start_ts": start_ts,
            "end_ts": end_ts,

            "trigger_type": trigger_info.get("triggerType"),
            "triggered_by": {
                "identifier": triggered_by.get("identifier"),
                "email": triggered_extra.get("email"),
                "username": triggered_by.get("identifier") or triggered_by.get("uuid"),
            },

            "failure_message": failure_msg,
            "deployments": deployments,
        })

    return {
        "pipeline_identifier": pipeline_identifier,
        "project_identifier": project_identifier,
        "page": data.get("number", page),
        "size": data.get("size", size),
        "total_elements": data.get("totalElements"),
        "total_pages": data.get("totalPages"),
        "executions": executions,
    }


def extract_service_deployments_from_execution(raw_execution: dict) -> list[dict]:
    """
    Extract per-service deployment parameters directly from execution summary.

    Returns:
    [
        {
            "serviceRef": "...",
            "environment": "PROD",
            "infrastructure": "...",
            "variables": {
                "imageTag": "...",
                "githubBranch": "...",
                ...
            }
        },
        ...
    ]
    """
    results = []
    layout = raw_execution.get("layoutNodeMap") or {}

    for node in layout.values():
        strategy = node.get("strategyMetadata") or {}
        matrix = strategy.get("matrixMetadata") or {}
        matrix_values = matrix.get("matrixValues") or {}

        service_ref = matrix_values.get("serviceRef")
        service_inputs_raw = matrix_values.get("serviceInputs")

        if not service_ref or not service_inputs_raw:
            continue

        try:
            service_inputs = json.loads(service_inputs_raw)
        except Exception:
            continue

        spec = (
            service_inputs
            .get("serviceDefinition", {})
            .get("spec", {})
        )

        variables_list = spec.get("variables") or []
        variables = {
            v.get("name"): v.get("value")
            for v in variables_list
            if isinstance(v, dict) and v.get("name")
        }

        results.append({
            "serviceRef": service_ref,
            "environment": matrix_values.get("environmentRef") or matrix_values.get("environment"),
            "infrastructure": matrix_values.get("identifier"),
            "variables": variables,
        })

    return results


def _thin_execution(raw: dict) -> dict:
    """
    Return only operator-meaningful fields from the huge execution summary object.
    """
    cd = ((raw.get("moduleInfo") or {}).get("cd") or {})
    triggered = ((raw.get("executionTriggerInfo") or {}).get("triggeredBy") or {})
    triggered_extra = (triggered.get("extraInfo") or {})

    return {
        # Identity
        "planExecutionId": raw.get("planExecutionId"),
        "pipelineIdentifier": raw.get("pipelineIdentifier"),
        "projectIdentifier": raw.get("projectIdentifier"),
        "orgIdentifier": raw.get("orgIdentifier"),
        "runSequence": raw.get("runSequence"),

        # Status/timing
        "status": raw.get("status"),
        "startTs": raw.get("startTs"),
        "endTs": raw.get("endTs"),

        # Who/trigger
        "triggerType": (raw.get("executionTriggerInfo") or {}).get("triggerType"),
        "triggeredBy": {
            "identifier": triggered.get("identifier"),
            "email": triggered_extra.get("email"),
            "uuid": triggered.get("uuid"),
        },

        # Filters-relevant CD info
        "cd": {
            "serviceIdentifiers": cd.get("serviceIdentifiers") or [],
            "envIdentifiers": cd.get("envIdentifiers") or [],
            "environmentTypes": cd.get("environmentTypes") or [],
            "infrastructureNames": cd.get("infrastructureNames") or [],
            "helmChartVersions": cd.get("helmChartVersions") or [],
        },
    }


def get_last_successful_execution_filtered(
    driver,
    *,
    pipeline_identifier: str,
    time_range_filter_type: str = "LAST_30_DAYS",
    service_identifiers: Optional[list[str]] = None,
    env_identifiers: Optional[list[str]] = None,
    infra_identifiers: Optional[list[str]] = None,
    project_identifier: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    include_raw: bool = False,
) -> Dict[str, Any]:
    """
    Latest SUCCESS execution under the given UI filters (service/env/timeRange).
    Returns a thin/meaningful execution summary by default.
    """
    url, body = urls_builders.build_last_success_filtered(
        pipeline_identifier=pipeline_identifier,
        time_range_filter_type=time_range_filter_type,
        service_identifiers=service_identifiers,
        env_identifiers=env_identifiers,
        infra_identifiers=infra_identifiers,
        project_identifier=project_identifier,
    )

    res = browser_fetch(driver, url=url, method="POST", headers=headers, body_obj=body)

    payload = (res.get("data") or {}).get("data") or {}
    content = payload.get("content") or payload.get("executions") or []

    if not isinstance(content, list) or not content or not isinstance(content[0], dict):
        return {
            "error": "no_successful_execution",
            "detail": "No successful executions found under the provided filters",
            "filters": {
                "pipeline_identifier": pipeline_identifier,
                "time_range_filter_type": time_range_filter_type,
                "service_identifiers": service_identifiers or [],
                "env_identifiers": env_identifiers or [],
                "project_identifier": project_identifier,
            },
            "raw": res if include_raw else None,
        }

    latest = content[0]

    execution_id = (
        latest.get("planExecutionId")
        or latest.get("executionId")
        or latest.get("execution_id")
        or latest.get("id")
    )

    service_deployments = extract_service_deployments_from_execution(latest)

    out = {
        "pipeline_identifier": pipeline_identifier,
        "execution_id": execution_id,
        "status": latest.get("status"),
        "startTs": latest.get("startTs"),
        "execution": _thin_execution(latest),
        "service_deployments": service_deployments,
    }

    if include_raw:
        out["raw"] = latest

    return out


import yaml
import html


def get_inputset_v2(driver, *, execution_id: str) -> Dict[str, Any]:
    url = urls_builders.build_inputset_v2(execution_id)
    res = browser_fetch(driver, url=url, method="GET", body_obj=None)

    # Unwrap envelopes
    cur = res
    for _ in range(4):
        if not isinstance(cur, dict):
            break
        if "result" in cur:
            cur = cur["result"]
        elif "ok" in cur and "data" in cur:
            cur = cur["data"]
        elif set(cur.keys()) == {"data"}:
            cur = cur["data"]
        else:
            break

    data = (cur or {}).get("data") or {}
    correlation_id = cur.get("correlationId")

    template_yaml = data.get("inputSetTemplateYaml")
    inputset_yaml = data.get("inputSetYaml")

    if isinstance(template_yaml, str):
        template_yaml = html.unescape(template_yaml)

    if isinstance(inputset_yaml, str):
        inputset_yaml = html.unescape(inputset_yaml)

    services = []
    infrastructures = set()
    variables = {}

    try:
        parsed = yaml.safe_load(inputset_yaml) or {}
        pipeline = parsed.get("pipeline", {})

        template_inputs = (
            pipeline
            .get("template", {})
            .get("templateInputs", {})
        )

        stages = template_inputs.get("stages", [])

        for stage in stages:
            spec = (
                stage.get("stage", {})
                .get("template", {})
                .get("templateInputs", {})
                .get("spec", {})
            )

            # Infra extraction
            env_group = spec.get("environmentGroup")
            if env_group:
                for env in env_group.get("environments", []):
                    for infra in env.get("infrastructureDefinitions", []):
                        if infra.get("identifier"):
                            infrastructures.add(infra["identifier"])

            # Services extraction
            services_block = spec.get("services", {})
            for svc in services_block.get("values", []):
                svc_ref = svc.get("serviceRef")
                vars_ = (
                    svc.get("serviceInputs", {})
                    .get("serviceDefinition", {})
                    .get("spec", {})
                    .get("variables", [])
                )

                image_tag = None
                github_branch = None

                for v in vars_:
                    if v.get("name") == "imageTag":
                        image_tag = v.get("value")
                    elif v.get("name") == "githubBranch":
                        github_branch = v.get("value")

                services.append({
                    "service_ref": svc_ref,
                    "imageTag": image_tag,
                    "githubBranch": github_branch,
                })

        # CR variables
        for v in template_inputs.get("variables", []):
            variables[v.get("name")] = v.get("value")

    except Exception:
        pass

    return {
        "execution_id": execution_id,
        "correlation_id": correlation_id,
        "inputset_template_yaml": template_yaml,
        "inputset_yaml": inputset_yaml,
        "services": services,
        "infrastructures": sorted(infrastructures),
        "variables": variables,
    }

def get_active_service_instances(
    driver,
    *,
    env_id: Optional[str] = None,
    project_identifier: Optional[str] = None,
) -> Dict[str, Any]:
    url = urls_builders.build_active_service_instances(
        env_id=env_id,
        project_identifier=project_identifier,
    )
    raw = browser_fetch(driver, url=url, method="GET", body_obj=None)
    return _extract_meaningful_active_services(raw)


def _extract_meaningful_active_services(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize Harness /environments/active-service-instances response.

    Output model:
    - One entry per (service, artifactVersion, environment, infra)
    - Preserves artifactVersion
    - Preserves per-infra deployment timing
    """

    def _unwrap(obj):
        cur = obj
        for _ in range(4):
            if not isinstance(cur, dict):
                break
            if "result" in cur:
                cur = cur["result"]
            elif "ok" in cur and "data" in cur:
                cur = cur["data"]
            elif set(cur.keys()) == {"data"}:
                cur = cur["data"]
            else:
                break
        return cur

    root = _unwrap(raw)
    data = (root or {}).get("data", {})
    services_raw = data.get("instanceGroupedByServiceList", [])

    rows = []

    for svc in services_raw:
        service_id = svc.get("serviceId")
        service_name = svc.get("serviceName") or service_id

        for art in svc.get("instanceGroupedByArtifactList", []):
            artifact_version = art.get("artifactVersion") or ""

            for env in art.get("instanceGroupedByEnvironmentList", []):
                env_name = env.get("envName") or env.get("envId")

                for infra in env.get("instanceGroupedByInfraList", []):
                    infra_id = infra.get("infraIdentifier")
                    infra_name = infra.get("infraName") or infra_id
                    last_deployed_at = infra.get("lastDeployedAt")

                    pe_list = infra.get("instanceGroupedByPipelineExecutionList", [])
                    pe = pe_list[0] if pe_list else {}

                    rows.append({
                        "service_id": service_id,
                        "service_name": service_name,
                        "artifact_version": artifact_version,
                        "environment": env_name,
                        "infra_identifier": infra_id,
                        "infra_name": infra_name,
                        "last_deployed_at": last_deployed_at,
                        "instance_count": pe.get("count", 0),
                        "pipeline_execution_id": pe.get("lastPipelineExecutionId"),
                        "pipeline_name": pe.get("lastPipelineExecutionName"),
                    })

    return {
        "services": sorted(
            rows,
            key=lambda r: (
                r["service_id"],
                r["artifact_version"],
                r["environment"],
                r["infra_identifier"],
            ),
        )
    }


# --- captured call: projects ---
def get_projects(
    driver,
    *,
    page_index: int = 0,
    page_size: int = 20,
    sort_orders: str = "lastModifiedAt,DESC",
    only_favorites: bool = False,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:

    url = urls_builders.build_projects_aggregate(
        page_index=page_index,
        page_size=page_size,
        sort_orders=sort_orders,
        only_favorites=only_favorites,
    )

    raw = browser_fetch(
        driver,
        url=url,
        method="GET",
        headers=headers,
        body_obj=None,
    )

    return _extract_meaningful_projects(raw)


def _extract_meaningful_projects(raw: dict) -> dict:
    """
    Reduce Harness projects/list payload to meaningful, de-duplicated project info.
    """
    seen = {}
    content = (
        raw
        .get("data", {})
        .get("data", {})
        .get("content", [])
    )

    for item in content:
        project = (
            item
            .get("projectResponse", {})
            .get("project", {})
        )
        if not project:
            continue

        modules = project.get("modules", [])
        if "CD" not in modules:
            continue

        identifier = project.get("identifier")
        if not identifier:
            continue

        org = project.get("orgIdentifier")

        if identifier in seen and seen[identifier]["org"] == "wf":
            continue

        tags = project.get("tags", {}) or {}

        seen[identifier] = {
            "identifier": identifier,
            "name": project.get("name"),
            "org": org,
            "appID": tags.get("appID"),
            "caID": tags.get("caID"),
            "isPAA": tags.get("isPAA"),
        }

    return {
        "projects": sorted(
            seen.values(),
            key=lambda p: p["identifier"],
        )
    }


# --- captured call: pipelines list ---
def get_pipelines_list(
    driver,
    *,
    org_identifier: Optional[str] = None,
    project_identifier: Optional[str] = None,
    page: int = 0,
    size: int = 20,
    sort: str = "lastUpdatedAt,DESC",
    filter_type: str = "PipelineSetup",
    headers: Optional[Dict[str, str]] = None,
    method: str = "POST",
) -> Dict[str, Any]:

    url = urls_builders.build_pipelines_list(
        org_identifier=org_identifier,
        project_identifier=project_identifier,
        page=page,
        size=size,
        sort=sort,
    )

    body = {"filterType": filter_type} if filter_type else None

    raw = browser_fetch(
        driver,
        url=url,
        method=method,
        headers=headers,
        body_obj=body,
    )

    return _extract_meaningful_pipelines(
        raw,
        project_identifier=project_identifier,
    )


def _extract_meaningful_pipelines(
    raw: dict,
    *,
    project_identifier: Optional[str] = None,
) -> dict:
    """
    Reduce Harness pipelines/list payload to meaningful, deployment-focused pipeline info.
    """
    pipelines = []

    content = (
        raw
        .get("data", {})
        .get("data", {})
        .get("content", [])
    )

    for p in content:
        identifier = p.get("identifier")
        if not identifier:
            continue

        modules = p.get("modules", [])
        if "pms" not in modules:
            continue

        name = p.get("name")
        exec_info = p.get("executionSummaryInfo", {}) or {}
        tags = p.get("tags", {}) or {}

        pipelines.append({
            "identifier": identifier,
            "name": name,
            "last_status": exec_info.get("lastExecutionStatus"),
            "last_execution_ts": exec_info.get("lastExecutionTs"),
            "appID": tags.get("appID"),
        })

    return {
        "project_identifier": project_identifier,
        "pipelines": sorted(
            pipelines,
            key=lambda x: x["identifier"],
        ),
    }


def get_last_success_with_inputset_filtered(
    driver,
    *,
    pipeline_identifier: str,
    time_range_filter_type: str = "LAST_30_DAYS",
    service_identifiers: Optional[list[str]] = None,
    env_identifiers: Optional[list[str]] = None,
    project_identifier: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    One-call operator primitive:
    - select last SUCCESS execution using Harness UI filters
    - return that execution + inputset v2
    """

    latest = get_last_successful_execution_filtered(
        driver,
        pipeline_identifier=pipeline_identifier,
        time_range_filter_type=time_range_filter_type,
        service_identifiers=service_identifiers,
        env_identifiers=env_identifiers,
        project_identifier=project_identifier,
        headers=headers,
    )

    if latest.get("error") or not latest.get("execution_id"):
        return latest

    inputset_raw = get_inputset_v2(driver, execution_id=latest["execution_id"])

    return {
        "filters": {
            "pipeline_identifier": pipeline_identifier,
            "time_range_filter_type": time_range_filter_type,
            "service_identifiers": service_identifiers or [],
            "env_identifiers": env_identifiers or [],
            "project_identifier": project_identifier,
        },
        "execution": latest,
        # "inputset": inputset_raw,  # CLEAN + MEANINGFUL
    }


def get_last_success_by_infra(
    driver,
    *,
    pipeline_identifier: str,
    project_identifier: Optional[str],
    service_identifiers: Optional[list[str]],
    env_identifiers: Optional[list[str]],
    infra_identifiers: list[str],
    time_range_filter_type: str = "LAST_30_DAYS",
    size: int = 20,
    max_pages: int = 3,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Returns the latest successful *deployment node* per infra across recent SUCCESS executions.
    Handles cases where Manassas is a separate execution from the multi-DC matrix run.
    """

    remaining = set(infra_identifiers)
    out: Dict[str, Any] = {}

    for page in range(max_pages):
        url, body = urls_builders.build_pipeline_exec_summary_filtered(
            pipeline_identifier=pipeline_identifier,
            page=page,
            size=size,
            time_range_filter_type=time_range_filter_type,
            service_identifiers=service_identifiers,
            env_identifiers=env_identifiers,
            statuses=["SUCCESS"],
            project_identifier=project_identifier,
        )

        res = browser_fetch(driver, url=url, method="POST", headers=headers, body_obj=body)

        payload = (res.get("data") or {}).get("data") or {}
        content = payload.get("content") or []
        if not isinstance(content, list) or not content:
            break

        for exec_item in content:
            if not remaining:
                break

            matches = extract_success_deployments_by_infra_from_execution_item(
                exec_item,
                list(remaining),
            )

            for k, v in matches.items():
                # first hit wins because we scan newest -> oldest
                out[k] = v
                remaining.discard(k)

        if not remaining:
            break

    return {
        "pipeline_identifier": pipeline_identifier,
        "time_range_filter_type": time_range_filter_type,
        "service_identifiers": service_identifiers or [],
        "env_identifiers": env_identifiers or [],
        "requested_infra_identifiers": infra_identifiers,
        "missing_infra_identifiers": sorted(list(remaining)),
        "by_infrastructure": out,
    }


# ---------------------------------------------------------------------

def extract_last_successful_deployment_node_per_infra(
    execution_result: dict,
    infra_identifiers: list[str],
) -> dict:
    """
    Returns the last successful deployment node per infrastructure
    from a pipeline execution summary.
    """

    out = {}

    layout = (
        execution_result
        .get("execution", {})
        .get("execution", {})
        .get("layoutNodeMap", {})
    )

    for node in layout.values():
        if node.get("module") != "cd":
            continue
        if node.get("nodeType") != "Deployment":
            continue
        if node.get("status") != "Success":
            continue

        cd_info = (node.get("moduleInfo") or {}).get("cd") or {}
        infra = (
            cd_info
            .get("infraExecutionSummary", {})
            .get("infrastructureIdentifier")
        )

        if infra not in infra_identifiers:
            continue

        out[infra] = {
            "planExecutionId": execution_result["execution"].get("execution_id"),
            "nodeExecutionId": node.get("nodeExecutionId"),
            "status": node.get("status"),
            "startTs": node.get("startTs"),
            "deployment": {
                "serviceRef": cd_info.get("identifier"),
                "environment": (
                    cd_info
                    .get("infraExecutionSummary", {})
                    .get("identifier")
                ),
                "infrastructure": infra,
                "variables": extract_service_inputs_from_node(node),
            },
        }

    return out


def extract_service_inputs_from_node(node: dict) -> Dict[str, Any]:
    """
    Pulls deployment parameters (imageTag, githubBranch, etc.) from a deployment node.

    These are stored as a JSON STRING at:
    node["strategyMetadata"]["matrixMetadata"]["matrixValues"]["serviceInputs"]
    """
    try:
        matrix_values = (
            (node.get("strategyMetadata") or {})
            .get("matrixMetadata", {})
            .get("matrixValues", {})
        )

        raw = matrix_values.get("serviceInputs")
        if not raw:
            return {}

        service_inputs = json.loads(raw)

        spec = (
            (service_inputs.get("serviceDefinition") or {})
            .get("spec") or {}
        )

        variables_list = spec.get("variables") or []
        out: Dict[str, Any] = {}

        for v in variables_list:
            if isinstance(v, dict) and v.get("name"):
                out[str(v.get("name"))] = v.get("value")

        # Optional artifact pointer
        artifacts = spec.get("artifacts") or {}
        if artifacts:
            out["_artifacts"] = artifacts

        return out

    except Exception:
        return {}


# ---------------------------------------------------------------------

import re

def _norm_infra(value: str | None) -> str:
    if not value:
        return ""

    v = value.lower()
    v = re.sub(r"[-_]", "", v)   # remove hyphens/underscores
    v = re.sub(r"p$", "", v)     # strip trailing 'p'
    return v


def extract_success_deployments_by_infra_from_execution_item(
    execution_item: dict,
    infra_targets: list[str],
) -> Dict[str, dict]:
    """
    From ONE execution summary item, return deployments keyed by infra (matching targets).
    """

    targets_norm = {_norm_infra(x): x for x in infra_targets}
    found: Dict[str, dict] = {}

    layout = execution_item.get("layoutNodeMap") or {}

    for node in layout.values():
        if node.get("module") != "cd":
            continue
        if node.get("nodeType") != "Deployment":
            continue
        if (node.get("status") or "").lower() != "success":
            continue

        cd = (node.get("moduleInfo") or {}).get("cd") or {}
        infra_sum = cd.get("infraExecutionSummary") or {}

        infra_id = infra_sum.get("infrastructureIdentifier")
        infra_name = infra_sum.get("infrastructureName")

        key_norm = _norm_infra(infra_id) or _norm_infra(infra_name)
        if key_norm not in targets_norm:
            continue

        req_key = targets_norm[key_norm]

        found[req_key] = {
            "planExecutionId": execution_item.get("planExecutionId"),
            "status": node.get("status"),
            "startTs": node.get("startTs"),
            "endTs": node.get("endTs"),
            "nodeExecutionId": node.get("nodeExecutionId"),
            "serviceRef": (
                (node.get("strategyMetadata") or {})
                .get("matrixMetadata", {})
                .get("matrixValues", {})
                .get("serviceRef")
            ),
            "environment": infra_sum.get("identifier"),
            "infrastructureIdentifier": infra_id,
            "infrastructureName": infra_name,
            "variables": extract_service_inputs_from_node(node),
        }

    return found



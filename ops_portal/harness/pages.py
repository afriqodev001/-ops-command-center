"""
Harness UI pages — HTML views + HTMX partials.
"""
from __future__ import annotations
import json

from django.conf import settings as dj_settings
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .services import workspace as ws


def _ws_context():
    """Workspace data for autocomplete + pinned chips on filter pages."""
    return {
        'ws_projects': ws.list_projects(),
        'ws_pipelines': ws.list_pipelines(),
        'ws_services': ws.list_services(),
        'ws_pinned_projects': ws.pinned_projects(),
        'ws_pinned_pipelines': ws.pinned_pipelines(),
        'ws_pinned_services': ws.pinned_services(),
    }


# ─── Full Pages ─────────────────────────────────────────────

def harness_home(request):
    return render(request, 'harness/index.html', {
        'default_pipeline': getattr(dj_settings, 'HARNESS_PIPELINE_ID', ''),
        'default_project': getattr(dj_settings, 'HARNESS_PROJECT_ID', ''),
        'default_env': getattr(dj_settings, 'HARNESS_ENV_ID', ''),
        'default_org': getattr(dj_settings, 'HARNESS_ORG_ID', ''),
        **_ws_context(),
    })


def harness_pipelines_page(request):
    return render(request, 'harness/pipelines.html', {
        'default_project': getattr(dj_settings, 'HARNESS_PROJECT_ID', ''),
        'default_org': getattr(dj_settings, 'HARNESS_ORG_ID', ''),
        **_ws_context(),
    })


def harness_executions_page(request):
    return render(request, 'harness/executions.html', {
        'prefill_pipeline': request.GET.get('pipeline_id', '').strip()
            or getattr(dj_settings, 'HARNESS_PIPELINE_ID', ''),
        'prefill_time_range': request.GET.get('time_range', 'LAST_30_DAYS'),
        'default_env': getattr(dj_settings, 'HARNESS_ENV_ID', ''),
        **_ws_context(),
    })


def harness_instances_page(request):
    return render(request, 'harness/instances.html', {
        'prefill_env': request.GET.get('env_id', '').strip()
            or getattr(dj_settings, 'HARNESS_ENV_ID', ''),
        **_ws_context(),
    })


def harness_projects_page(request):
    return render(request, 'harness/projects.html', _ws_context())


def harness_environments_page(request):
    return render(request, 'harness/environments.html', _ws_context())


def harness_service_explorer(request):
    """Service-first drill-down — pick a service, see everything about it."""
    name = request.GET.get('name', '').strip()
    service = ws.get_service(name) if name else None
    pinned_pipelines_for_svc = ws.pipelines_for_service(name) if name else []

    return render(request, 'harness/service.html', {
        'service_name': name,
        'service': service,
        'service_pipelines': pinned_pipelines_for_svc,
        'autorun': request.GET.get('autorun', '1') == '1',
        **_ws_context(),
    })


# ─── Service Explorer fan-out (HTMX) ───────────────────────

@csrf_exempt
@require_POST
def service_now_running(request):
    """Fan-out tile #1 — active instances filtered to this service."""
    alive, err = _session_or_error(request, 'service-now-running')
    if not alive:
        return err

    name = request.POST.get('service_name', '').strip()
    env_id = request.POST.get('env_id', '').strip() or None
    if not name:
        return render(request, 'harness/partials/error.html', {
            'error': 'Service name is required.',
        })

    from .tasks import active_service_instances_task
    task = active_service_instances_task.delay({'env_id': env_id})

    return render(request, 'harness/partials/running.html', {
        'task_id': task.id,
        'poll_url': f'/harness/ui/service/now-running/poll/{task.id}/?service_name={name}',
        'target_id': 'svc-now-running',
        'description': 'Looking up running instances…',
    })


def service_now_running_poll(request, task_id):
    from celery.result import AsyncResult
    ar = AsyncResult(task_id)

    name = request.GET.get('service_name', '').strip()

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'harness/partials/running.html', {
            'task_id': task_id,
            'poll_url': f'/harness/ui/service/now-running/poll/{task_id}/?service_name={name}',
            'target_id': 'svc-now-running',
            'description': 'Looking up running instances…',
        })

    if ar.state == 'FAILURE':
        return render(request, 'harness/partials/error.html', {
            'error': str(ar.result),
        })

    result = ar.result or {}
    if isinstance(result, dict) and result.get('error'):
        return render(request, 'harness/partials/error.html', {
            'error': result.get('detail') or result.get('error'),
        })

    services = result.get('services') or []
    matching = [s for s in services if s.get('service_id') == name]
    return render(request, 'harness/partials/svc_now_running.html', {
        'service_name': name,
        'rows': matching,
    })


@csrf_exempt
@require_POST
def service_recent_runs(request):
    """Fan-out tile #2 — recent executions filtered to this service."""
    alive, err = _session_or_error(request, 'service-recent-runs')
    if not alive:
        return err

    name = request.POST.get('service_name', '').strip()
    pipeline_id = request.POST.get('pipeline_identifier', '').strip()
    if not pipeline_id:
        return render(request, 'harness/partials/error.html', {
            'error': 'Pipeline identifier is required to fetch executions for this service.',
        })

    from .tasks import pipeline_execution_summary_filtered_task
    body = {
        'pipeline_identifier': pipeline_id,
        'time_range_filter_type': request.POST.get('time_range_filter_type', 'LAST_30_DAYS'),
        'page': 0,
        'size': 10,
    }
    if name:
        body['service_identifiers'] = [name]
    task = pipeline_execution_summary_filtered_task.delay(body)

    return render(request, 'harness/partials/running.html', {
        'task_id': task.id,
        'poll_url': f'/harness/ui/service/recent-runs/poll/{task.id}/?service_name={name}',
        'target_id': 'svc-recent-runs',
        'description': 'Loading recent executions…',
    })


def service_recent_runs_poll(request, task_id):
    from celery.result import AsyncResult
    ar = AsyncResult(task_id)

    name = request.GET.get('service_name', '').strip()

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'harness/partials/running.html', {
            'task_id': task_id,
            'poll_url': f'/harness/ui/service/recent-runs/poll/{task_id}/?service_name={name}',
            'target_id': 'svc-recent-runs',
            'description': 'Loading recent executions…',
        })

    if ar.state == 'FAILURE':
        return render(request, 'harness/partials/error.html', {
            'error': str(ar.result),
        })

    result = ar.result or {}
    if isinstance(result, dict) and result.get('error'):
        return render(request, 'harness/partials/error.html', {
            'error': result.get('detail') or result.get('error'),
        })

    executions = result.get('executions') or []
    return render(request, 'harness/partials/svc_recent_runs.html', {
        'service_name': name,
        'executions': executions,
        'pipeline_identifier': result.get('pipeline_identifier') or '',
    })


@csrf_exempt
@require_POST
def service_last_success_per_env(request):
    """Fan-out tile #3 — last success per infrastructure for this service."""
    alive, err = _session_or_error(request, 'service-last-success')
    if not alive:
        return err

    name = request.POST.get('service_name', '').strip()
    pipeline_id = request.POST.get('pipeline_identifier', '').strip()
    infras_raw = request.POST.get('infra_identifiers', '').strip()
    infras = _split_csv(infras_raw)

    if not pipeline_id or not infras or not name:
        return render(request, 'harness/partials/error.html', {
            'error': 'Pipeline identifier, service name, and at least one infrastructure are required.',
        })

    from .tasks import last_success_by_infra_task
    body = {
        'pipeline_identifier': pipeline_id,
        'infra_identifiers': infras,
        'service_identifiers': [name],
        'time_range_filter_type': request.POST.get('time_range_filter_type', 'LAST_30_DAYS'),
    }
    task = last_success_by_infra_task.delay(body)

    return render(request, 'harness/partials/running.html', {
        'task_id': task.id,
        'poll_url': f'/harness/ui/service/last-success/poll/{task.id}/?service_name={name}',
        'target_id': 'svc-last-success',
        'description': 'Locating last success per infrastructure…',
    })


def service_last_success_per_env_poll(request, task_id):
    from celery.result import AsyncResult
    ar = AsyncResult(task_id)

    name = request.GET.get('service_name', '').strip()

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'harness/partials/running.html', {
            'task_id': task_id,
            'poll_url': f'/harness/ui/service/last-success/poll/{task_id}/?service_name={name}',
            'target_id': 'svc-last-success',
            'description': 'Locating last success per infrastructure…',
        })

    if ar.state == 'FAILURE':
        return render(request, 'harness/partials/error.html', {
            'error': str(ar.result),
        })

    result = ar.result or {}
    if isinstance(result, dict) and result.get('error'):
        return render(request, 'harness/partials/error.html', {
            'error': result.get('detail') or result.get('error'),
        })

    by_infra = result.get('by_infrastructure') or {}
    rows = []
    for infra_id, info in by_infra.items():
        rows.append({'infra_id': infra_id, **info})
    rows.sort(key=lambda r: (r.get('infra_id') or '').lower())

    return render(request, 'harness/partials/svc_last_success.html', {
        'service_name': name,
        'rows': rows,
        'requested': result.get('requested_infra_identifiers') or [],
        'missing': result.get('missing_infra_identifiers') or [],
    })


# ─── Helpers ────────────────────────────────────────────────

def _session_or_error(request, area: str):
    """Returns (alive, error_html) — if alive is False, the caller should return error_html."""
    from .session_views import is_session_alive
    if not is_session_alive():
        return False, render(request, 'harness/partials/error.html', {
            'error': 'Harness session is not connected. Use Connect Harness in the sidebar to open the browser and sign in.',
        })
    return True, None


def _split_csv(raw: str):
    if not raw:
        return None
    items = [x.strip() for x in raw.split(',') if x.strip()]
    return items or None


# ─── Pipelines (HTMX) ───────────────────────────────────────

@csrf_exempt
@require_POST
def run_pipelines_list(request):
    alive, err = _session_or_error(request, 'pipelines')
    if not alive:
        return err

    from .tasks import pipelines_list_task
    org = request.POST.get('org_identifier', '').strip() or None
    project = request.POST.get('project_identifier', '').strip() or None
    task = pipelines_list_task.delay({
        'org_identifier': org,
        'project_identifier': project,
        'page': int(request.POST.get('page', 0) or 0),
        'size': int(request.POST.get('size', 50) or 50),
    })
    return render(request, 'harness/partials/running.html', {
        'task_id': task.id,
        'poll_url': f'/harness/ui/pipelines/poll/{task.id}/',
        'target_id': 'harness-results',
        'description': 'Listing pipelines…',
        'detail': f'Project: {project or "default"}',
    })


def poll_pipelines_list(request, task_id):
    from celery.result import AsyncResult
    ar = AsyncResult(task_id)

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'harness/partials/running.html', {
            'task_id': task_id,
            'poll_url': f'/harness/ui/pipelines/poll/{task_id}/',
            'target_id': 'harness-results',
            'description': 'Listing pipelines…',
        })

    if ar.state == 'FAILURE':
        return render(request, 'harness/partials/error.html', {
            'error': str(ar.result),
        })

    result = ar.result or {}
    if isinstance(result, dict) and result.get('error'):
        return render(request, 'harness/partials/error.html', {
            'error': result.get('detail') or result.get('error'),
        })

    return render(request, 'harness/partials/pipelines_results.html', {
        'result': result,
        'result_json': json.dumps(result, default=str, indent=2),
        'pipelines': result.get('pipelines') or [],
        'project_identifier': result.get('project_identifier') or '',
    })


# ─── Executions (HTMX) ──────────────────────────────────────

@csrf_exempt
@require_POST
def run_executions(request):
    alive, err = _session_or_error(request, 'executions')
    if not alive:
        return err

    pipeline_id = request.POST.get('pipeline_identifier', '').strip()
    if not pipeline_id:
        return render(request, 'harness/partials/error.html', {
            'error': 'Pipeline identifier is required.',
        })

    service_identifiers = _split_csv(request.POST.get('service_identifiers', ''))
    env_identifiers = _split_csv(request.POST.get('env_identifiers', ''))

    from .tasks import pipeline_execution_summary_filtered_task
    body = {
        'pipeline_identifier': pipeline_id,
        'time_range_filter_type': request.POST.get('time_range_filter_type', 'LAST_30_DAYS'),
        'page': int(request.POST.get('page', 0) or 0),
        'size': int(request.POST.get('size', 20) or 20),
    }
    if service_identifiers:
        body['service_identifiers'] = service_identifiers
    if env_identifiers:
        body['env_identifiers'] = env_identifiers

    task = pipeline_execution_summary_filtered_task.delay(body)

    return render(request, 'harness/partials/running.html', {
        'task_id': task.id,
        'poll_url': f'/harness/ui/executions/poll/{task.id}/',
        'target_id': 'harness-results',
        'description': 'Fetching executions…',
        'detail': f'Pipeline: {pipeline_id}',
    })


def poll_executions(request, task_id):
    from celery.result import AsyncResult
    ar = AsyncResult(task_id)

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'harness/partials/running.html', {
            'task_id': task_id,
            'poll_url': f'/harness/ui/executions/poll/{task_id}/',
            'target_id': 'harness-results',
            'description': 'Fetching executions…',
        })

    if ar.state == 'FAILURE':
        return render(request, 'harness/partials/error.html', {
            'error': str(ar.result),
        })

    result = ar.result or {}
    if isinstance(result, dict) and result.get('error'):
        return render(request, 'harness/partials/error.html', {
            'error': result.get('detail') or result.get('error'),
        })

    executions = result.get('executions') or []
    return render(request, 'harness/partials/executions_results.html', {
        'result': result,
        'result_json': json.dumps(result, default=str, indent=2),
        'executions': executions,
        'pipeline_identifier': result.get('pipeline_identifier') or '',
        'total_elements': result.get('total_elements'),
        'page': result.get('page'),
        'size': result.get('size'),
    })


# ─── Last success (HTMX) ───────────────────────────────────

@csrf_exempt
@require_POST
def run_last_success(request):
    alive, err = _session_or_error(request, 'last-success')
    if not alive:
        return err

    pipeline_id = request.POST.get('pipeline_identifier', '').strip()
    if not pipeline_id:
        return render(request, 'harness/partials/error.html', {
            'error': 'Pipeline identifier is required.',
        })

    body = {
        'pipeline_identifier': pipeline_id,
        'time_range_filter_type': request.POST.get('time_range_filter_type', 'LAST_30_DAYS'),
    }
    svcs = _split_csv(request.POST.get('service_identifiers', ''))
    envs = _split_csv(request.POST.get('env_identifiers', ''))
    if svcs:
        body['service_identifiers'] = svcs
    if envs:
        body['env_identifiers'] = envs

    from .tasks import last_success_execution_with_inputset_filtered_task
    task = last_success_execution_with_inputset_filtered_task.delay(body)

    return render(request, 'harness/partials/running.html', {
        'task_id': task.id,
        'poll_url': f'/harness/ui/last-success/poll/{task.id}/',
        'target_id': 'harness-results',
        'description': 'Locating last successful execution…',
        'detail': f'Pipeline: {pipeline_id}',
    })


def poll_last_success(request, task_id):
    from celery.result import AsyncResult
    ar = AsyncResult(task_id)

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'harness/partials/running.html', {
            'task_id': task_id,
            'poll_url': f'/harness/ui/last-success/poll/{task_id}/',
            'target_id': 'harness-results',
            'description': 'Locating last successful execution…',
        })

    if ar.state == 'FAILURE':
        return render(request, 'harness/partials/error.html', {
            'error': str(ar.result),
        })

    result = ar.result or {}
    if isinstance(result, dict) and result.get('error'):
        return render(request, 'harness/partials/error.html', {
            'error': result.get('detail') or result.get('error'),
        })

    return render(request, 'harness/partials/last_success_results.html', {
        'result': result,
        'result_json': json.dumps(result, default=str, indent=2),
    })


# ─── Last success by infra (HTMX) ──────────────────────────

@csrf_exempt
@require_POST
def run_last_success_by_infra(request):
    alive, err = _session_or_error(request, 'last-success-by-infra')
    if not alive:
        return err

    pipeline_id = request.POST.get('pipeline_identifier', '').strip()
    if not pipeline_id:
        return render(request, 'harness/partials/error.html', {
            'error': 'Pipeline identifier is required.',
        })

    infras = _split_csv(request.POST.get('infra_identifiers', ''))
    if not infras:
        return render(request, 'harness/partials/error.html', {
            'error': 'At least one infrastructure identifier is required (comma-separated).',
        })

    body = {
        'pipeline_identifier': pipeline_id,
        'infra_identifiers': infras,
        'time_range_filter_type': request.POST.get('time_range_filter_type', 'LAST_30_DAYS'),
    }
    svcs = _split_csv(request.POST.get('service_identifiers', ''))
    envs = _split_csv(request.POST.get('env_identifiers', ''))
    if svcs:
        body['service_identifiers'] = svcs
    if envs:
        body['env_identifiers'] = envs

    from .tasks import last_success_by_infra_task
    task = last_success_by_infra_task.delay(body)

    return render(request, 'harness/partials/running.html', {
        'task_id': task.id,
        'poll_url': f'/harness/ui/last-success-by-infra/poll/{task.id}/',
        'target_id': 'harness-results',
        'description': 'Locating last success per infrastructure…',
        'detail': f'Pipeline: {pipeline_id} · {len(infras)} infra',
    })


def poll_last_success_by_infra(request, task_id):
    from celery.result import AsyncResult
    ar = AsyncResult(task_id)

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'harness/partials/running.html', {
            'task_id': task_id,
            'poll_url': f'/harness/ui/last-success-by-infra/poll/{task_id}/',
            'target_id': 'harness-results',
            'description': 'Locating last success per infrastructure…',
        })

    if ar.state == 'FAILURE':
        return render(request, 'harness/partials/error.html', {
            'error': str(ar.result),
        })

    result = ar.result or {}
    if isinstance(result, dict) and result.get('error'):
        return render(request, 'harness/partials/error.html', {
            'error': result.get('detail') or result.get('error'),
        })

    by_infra = result.get('by_infrastructure') or {}
    rows = []
    for infra_id, info in by_infra.items():
        rows.append({
            'infra_id': infra_id,
            **info,
        })
    rows.sort(key=lambda r: (r.get('infra_id') or '').lower())

    return render(request, 'harness/partials/last_success_by_infra_results.html', {
        'result': result,
        'result_json': json.dumps(result, default=str, indent=2),
        'rows': rows,
        'requested': result.get('requested_infra_identifiers') or [],
        'missing': result.get('missing_infra_identifiers') or [],
        'pipeline_identifier': result.get('pipeline_identifier') or '',
    })


# ─── Active Instances (HTMX) ───────────────────────────────

@csrf_exempt
@require_POST
def run_instances(request):
    alive, err = _session_or_error(request, 'instances')
    if not alive:
        return err

    env_id = request.POST.get('env_id', '').strip() or None

    from .tasks import active_service_instances_task
    task = active_service_instances_task.delay({'env_id': env_id})

    return render(request, 'harness/partials/running.html', {
        'task_id': task.id,
        'poll_url': f'/harness/ui/instances/poll/{task.id}/',
        'target_id': 'harness-results',
        'description': 'Fetching active service instances…',
        'detail': f'Environment: {env_id or "default"}',
    })


def poll_instances(request, task_id):
    from celery.result import AsyncResult
    ar = AsyncResult(task_id)

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'harness/partials/running.html', {
            'task_id': task_id,
            'poll_url': f'/harness/ui/instances/poll/{task_id}/',
            'target_id': 'harness-results',
            'description': 'Fetching active service instances…',
        })

    if ar.state == 'FAILURE':
        return render(request, 'harness/partials/error.html', {
            'error': str(ar.result),
        })

    result = ar.result or {}
    if isinstance(result, dict) and result.get('error'):
        return render(request, 'harness/partials/error.html', {
            'error': result.get('detail') or result.get('error'),
        })

    services = result.get('services') or []
    # Group by (service_id, artifact_version) for a compact view
    groups = {}
    for row in services:
        key = (row.get('service_id'), row.get('artifact_version'))
        groups.setdefault(key, []).append(row)

    grouped = []
    for (svc, artifact), rows in groups.items():
        total_instances = sum(int(r.get('instance_count') or 0) for r in rows)
        grouped.append({
            'service_id': svc,
            'service_name': rows[0].get('service_name') if rows else svc,
            'artifact_version': artifact,
            'rows': rows,
            'total_instances': total_instances,
        })

    grouped.sort(key=lambda g: (g['service_id'] or '', g['artifact_version'] or ''))

    return render(request, 'harness/partials/instances_results.html', {
        'result': result,
        'result_json': json.dumps(result, default=str, indent=2),
        'services': services,
        'grouped': grouped,
    })


# ─── Projects (HTMX) ───────────────────────────────────────

@csrf_exempt
@require_POST
def run_projects(request):
    alive, err = _session_or_error(request, 'projects')
    if not alive:
        return err

    from .tasks import projects_list_task
    task = projects_list_task.delay({
        'page_index': int(request.POST.get('page_index', 0) or 0),
        'page_size': int(request.POST.get('page_size', 50) or 50),
        'only_favorites': bool(request.POST.get('only_favorites')),
    })

    return render(request, 'harness/partials/running.html', {
        'task_id': task.id,
        'poll_url': f'/harness/ui/projects/poll/{task.id}/',
        'target_id': 'harness-results',
        'description': 'Listing projects…',
    })


def poll_projects(request, task_id):
    from celery.result import AsyncResult
    ar = AsyncResult(task_id)

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'harness/partials/running.html', {
            'task_id': task_id,
            'poll_url': f'/harness/ui/projects/poll/{task_id}/',
            'target_id': 'harness-results',
            'description': 'Listing projects…',
        })

    if ar.state == 'FAILURE':
        return render(request, 'harness/partials/error.html', {
            'error': str(ar.result),
        })

    result = ar.result or {}
    if isinstance(result, dict) and result.get('error'):
        return render(request, 'harness/partials/error.html', {
            'error': result.get('detail') or result.get('error'),
        })

    return render(request, 'harness/partials/projects_results.html', {
        'result': result,
        'result_json': json.dumps(result, default=str, indent=2),
        'projects': result.get('projects') or [],
    })


# ─── Environments (HTMX) ───────────────────────────────────

@csrf_exempt
@require_POST
def run_environments(request):
    alive, err = _session_or_error(request, 'environments')
    if not alive:
        return err

    from .tasks import environments_list_task
    task = environments_list_task.delay({})

    return render(request, 'harness/partials/running.html', {
        'task_id': task.id,
        'poll_url': f'/harness/ui/environments/poll/{task.id}/',
        'target_id': 'harness-results',
        'description': 'Listing environments…',
    })


def poll_environments(request, task_id):
    from celery.result import AsyncResult
    ar = AsyncResult(task_id)

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'harness/partials/running.html', {
            'task_id': task_id,
            'poll_url': f'/harness/ui/environments/poll/{task_id}/',
            'target_id': 'harness-results',
            'description': 'Listing environments…',
        })

    if ar.state == 'FAILURE':
        return render(request, 'harness/partials/error.html', {
            'error': str(ar.result),
        })

    result = ar.result or {}
    if isinstance(result, dict) and result.get('error'):
        return render(request, 'harness/partials/error.html', {
            'error': result.get('detail') or result.get('error'),
        })

    # The raw environments endpoint returns data.data.content = [{environment: {...}}, ...]
    data = (result.get('data') or {}).get('data') or {}
    content = data.get('content') or []
    envs = []
    for item in content:
        env = (item or {}).get('environment') or item or {}
        envs.append({
            'identifier': env.get('identifier'),
            'name': env.get('name') or env.get('identifier'),
            'type': env.get('type'),
            'orgIdentifier': env.get('orgIdentifier'),
            'projectIdentifier': env.get('projectIdentifier'),
            'description': env.get('description'),
        })
    envs.sort(key=lambda e: (e.get('identifier') or ''))

    return render(request, 'harness/partials/environments_results.html', {
        'result': result,
        'result_json': json.dumps(result, default=str, indent=2),
        'environments': envs,
        'total': data.get('totalElements', len(envs)),
    })


# ─── Export JSON ───────────────────────────────────────────

@csrf_exempt
@require_POST
def export_json(request):
    data = request.POST.get('result_data', '{}')
    filename = request.POST.get('filename', 'harness_result.json')
    resp = HttpResponse(data, content_type='application/json')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp

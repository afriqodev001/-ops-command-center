"""
Splunk UI pages — HTML views + HTMX partials.
"""
from __future__ import annotations
import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .services.splunk_presets import list_presets, PRESETS


def splunk_home(request):
    presets = list_presets()
    return render(request, 'splunk/index.html', {
        'presets': presets,
        'presets_json': json.dumps(presets),
    })


@csrf_exempt
@require_POST
def run_search(request):
    """HTMX endpoint: dispatch a search and return a polling card."""
    from .session_views import is_session_alive
    if not is_session_alive():
        return render(request, 'splunk/partials/search_error.html', {
            'error': 'Splunk session is not connected. Use the Connect button in the sidebar.',
        })

    spl = request.POST.get('spl', '').strip()
    earliest = request.POST.get('earliest', '-10m').strip() or '-10m'
    latest = request.POST.get('latest', 'now').strip() or 'now'

    if not spl:
        return render(request, 'splunk/partials/search_error.html', {
            'error': 'Search query (SPL) is required.',
        })

    from .tasks import splunk_search_run_task
    task = splunk_search_run_task.delay({
        'search': spl,
        'earliest_time': earliest,
        'latest_time': latest,
        'include_preview': True,
        'include_events': True,
        'preview_count': 50,
        'events_count': 50,
    })

    return render(request, 'splunk/partials/search_running.html', {
        'task_id': task.id,
        'spl': spl,
        'earliest': earliest,
        'latest': latest,
    })


@csrf_exempt
@require_POST
def run_preset(request):
    """HTMX endpoint: dispatch a preset search."""
    from .session_views import is_session_alive
    if not is_session_alive():
        return render(request, 'splunk/partials/search_error.html', {
            'error': 'Splunk session is not connected. Use the Connect button in the sidebar.',
        })

    preset_name = request.POST.get('preset', '').strip()
    if not preset_name or preset_name not in PRESETS:
        return render(request, 'splunk/partials/search_error.html', {
            'error': f'Unknown preset: {preset_name}',
        })

    params = {}
    for key in request.POST:
        if key not in ('preset', 'csrfmiddlewaretoken'):
            params[key] = request.POST[key].strip()

    from .tasks import splunk_presets_run_task
    task = splunk_presets_run_task.delay({
        'preset': preset_name,
        'params': params,
    })

    return render(request, 'splunk/partials/search_running.html', {
        'task_id': task.id,
        'spl': f'Preset: {preset_name}',
        'earliest': params.get('earliest_time', ''),
        'latest': params.get('latest_time', ''),
    })


@csrf_exempt
@require_POST
def run_saved_search(request):
    """HTMX endpoint: find and run a saved search by name."""
    from .session_views import is_session_alive
    if not is_session_alive():
        return render(request, 'splunk/partials/search_error.html', {
            'error': 'Splunk session is not connected. Use the Connect button in the sidebar.',
        })

    name = request.POST.get('name', '').strip()
    if not name:
        return render(request, 'splunk/partials/search_error.html', {
            'error': 'Saved search name is required.',
        })

    from .tasks import splunk_alert_run_task
    task = splunk_alert_run_task.delay({
        'name': name,
        'include_preview': True,
        'include_events': True,
        'preview_count': 50,
        'events_count': 50,
    })

    return render(request, 'splunk/partials/search_running.html', {
        'task_id': task.id,
        'spl': f'Saved: {name}',
    })


def poll_search(request, task_id):
    """HTMX polling endpoint for search results."""
    from celery.result import AsyncResult
    ar = AsyncResult(task_id)

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'splunk/partials/search_running.html', {
            'task_id': task_id,
            'spl': '',
        })

    if ar.state == 'FAILURE':
        return render(request, 'splunk/partials/search_error.html', {
            'error': str(ar.result),
        })

    result = ar.result or {}
    if result.get('error'):
        return render(request, 'splunk/partials/search_error.html', {
            'error': result.get('detail') or result.get('error'),
        })

    return render(request, 'splunk/partials/search_results.html', {
        'result': result,
        'result_json': json.dumps(result, default=str),
    })

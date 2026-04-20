"""
Splunk UI pages — HTML views + HTMX partials.
"""
from __future__ import annotations
import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from django.conf import settings as dj_settings

from .services.splunk_presets import (
    list_presets, get_preset, save_preset, delete_preset,
    export_presets, import_presets, render_preset,
)


def _namespace_user():
    return getattr(dj_settings, 'SPLUNK_NAMESPACE_USER', 'nobody')


def splunk_home(request):
    presets = list_presets()
    preset_names = list(presets.keys())[:5]
    quick_presets = {k: presets[k] for k in preset_names}

    prefill_spl = request.GET.get('spl', '')
    prefill_earliest = request.GET.get('earliest', '')
    prefill_latest = request.GET.get('latest', '')
    autorun = request.GET.get('autorun', '')

    return render(request, 'splunk/index.html', {
        'quick_presets': quick_presets,
        'total_presets': len(presets),
        'prefill_spl': prefill_spl,
        'prefill_earliest': prefill_earliest,
        'prefill_latest': prefill_latest,
        'autorun': autorun,
    })


def splunk_saved_searches(request):
    return render(request, 'splunk/saved_searches.html')


def saved_searches_list(request):
    """HTMX: dispatch task to fetch saved searches, return polling partial."""
    from .session_views import is_session_alive
    if not is_session_alive():
        return render(request, 'splunk/partials/search_error.html', {
            'error': 'Splunk session is not connected. Use the Connect button in the sidebar.',
        })

    search_term = request.GET.get('q', '').strip()

    if search_term:
        from .tasks import splunk_alerts_search_task
        task = splunk_alerts_search_task.delay({
            'search_term': search_term,
            'count': 50,
        })
    else:
        from .tasks import splunk_alerts_list_task
        task = splunk_alerts_list_task.delay({
            'namespace_user': request.GET.get('namespace_user', '') or _namespace_user(),
        })
    return render(request, 'splunk/partials/saved_searches_loading.html', {
        'task_id': task.id,
    })


def saved_searches_poll(request, task_id):
    """HTMX polling for saved searches list result."""
    from celery.result import AsyncResult
    ar = AsyncResult(task_id)

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'splunk/partials/saved_searches_loading.html', {
            'task_id': task_id,
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

    # alerts_list_task returns {'alerts': [...]}
    # alerts_search_task returns raw Splunk response {'data': {'entry': [...]}}
    alerts = result.get('alerts') or []
    if not alerts:
        data = result.get('data') or {}
        entries = data.get('entry') or []
        for e in entries:
            content = e.get('content') or {}
            alerts.append({
                'name': e.get('name', ''),
                'owner': (e.get('acl') or {}).get('owner', ''),
                'app': (e.get('acl') or {}).get('app', ''),
                'disabled': bool(content.get('disabled')),
                'is_scheduled': bool(content.get('is_scheduled')),
                'cron_schedule': content.get('cron_schedule', ''),
                'description': content.get('description', ''),
            })
    return render(request, 'splunk/partials/saved_searches_list.html', {
        'alerts': alerts,
    })


def splunk_presets_page(request):
    presets = list_presets()
    return render(request, 'splunk/presets.html', {
        'presets': presets,
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
        'namespace_user': _namespace_user(),
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
    if not preset_name or not get_preset(preset_name):
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
        'namespace_user': _namespace_user(),
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
        'namespace_user': _namespace_user(),
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

    # Django templates can't access underscore-prefixed keys (_time, _raw).
    # Pre-process events to rename them.
    events_data = ((result.get('events') or {}).get('data') or {}).get('results') or []
    cleaned_events = []
    for evt in events_data:
        clean = {}
        for k, v in evt.items():
            clean[k.lstrip('_') if k.startswith('_') else k] = v
        cleaned_events.append(clean)

    return render(request, 'splunk/partials/search_results.html', {
        'result': result,
        'result_json': json.dumps(result, default=str),
        'cleaned_events': cleaned_events,
    })


# ─── Preset management ──────────────────────────────────────

def presets_list_partial(request):
    presets = list_presets()
    return render(request, 'splunk/partials/presets_list.html', {
        'presets': presets,
    })


@csrf_exempt
@require_POST
def preset_save_view(request):
    name = request.POST.get('name', '').strip()
    if not name:
        return render(request, 'splunk/partials/presets_list.html', {
            'presets': list_presets(), 'error': 'Preset name is required.',
        })

    preset = {
        'description': request.POST.get('description', '').strip(),
        'spl': request.POST.get('spl', '').strip(),
        'required_params': [p.strip() for p in request.POST.get('required_params', '').split(',') if p.strip()],
        'defaults': {
            'earliest_time': request.POST.get('earliest_time', '-10m').strip(),
            'latest_time': request.POST.get('latest_time', 'now').strip(),
            'include_preview': bool(request.POST.get('include_preview')),
            'include_events': bool(request.POST.get('include_events')),
        },
        'tags': request.POST.get('tags', '').strip(),
    }
    save_preset(name, preset)
    presets = list_presets()
    response = render(request, 'splunk/partials/presets_list.html', {
        'presets': presets, 'saved_name': name,
    })
    return response


@csrf_exempt
@require_POST
def preset_delete_view(request):
    name = request.POST.get('name', '').strip()
    if name:
        delete_preset(name)
    return render(request, 'splunk/partials/presets_list.html', {
        'presets': list_presets(),
    })


def preset_editor(request):
    name = request.GET.get('name', '').strip()
    preset = get_preset(name) if name else None
    return render(request, 'splunk/partials/preset_editor.html', {
        'name': name,
        'preset': preset,
    })


def preset_export_all(request):
    from django.http import HttpResponse
    data = json.dumps(export_presets(), indent=2, default=str)
    resp = HttpResponse(data, content_type='application/json')
    resp['Content-Disposition'] = 'attachment; filename="splunk_presets.json"'
    return resp


def preset_export_one(request, name):
    from django.http import HttpResponse
    data = json.dumps(export_presets([name]), indent=2, default=str)
    safe = name[:40].replace(' ', '_')
    resp = HttpResponse(data, content_type='application/json')
    resp['Content-Disposition'] = f'attachment; filename="splunk_preset_{safe}.json"'
    return resp


def preset_import_form(request):
    return render(request, 'splunk/partials/preset_import_form.html')


@csrf_exempt
@require_POST
def preset_import_preview(request):
    upload = request.FILES.get('file')
    if not upload:
        return render(request, 'splunk/partials/preset_import_preview.html', {
            'error': 'No file selected.',
        })
    try:
        raw = upload.read()
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8-sig', errors='replace')
        data = json.loads(raw)
    except Exception as e:
        return render(request, 'splunk/partials/preset_import_preview.html', {
            'error': f'Invalid JSON: {e}',
        })

    incoming = data.get('presets') or {}
    if not incoming:
        return render(request, 'splunk/partials/preset_import_preview.html', {
            'error': 'No presets found in file.',
        })

    existing = list_presets()
    preview = []
    for name, cfg in incoming.items():
        preview.append({
            'name': name,
            'description': cfg.get('description', ''),
            'spl_preview': (cfg.get('spl', '')[:100] + '…') if len(cfg.get('spl', '')) > 100 else cfg.get('spl', ''),
            'exists': name in existing,
        })

    return render(request, 'splunk/partials/preset_import_preview.html', {
        'preview': preview,
        'presets_json': json.dumps(data),
    })


@csrf_exempt
@require_POST
def preset_import_confirm(request):
    try:
        data = json.loads(request.POST.get('presets_json', '{}'))
    except json.JSONDecodeError:
        data = {}
    mode = request.POST.get('conflict_mode', 'skip')
    imported = import_presets(data, mode)
    presets = list_presets()
    response = render(request, 'splunk/partials/presets_list.html', {
        'presets': presets, 'import_count': imported,
    })
    return response


# ─── AI Features ─────────────────────────────────────────────

@csrf_exempt
@require_POST
def ai_analyze_results(request):
    """Analyze search results with AI."""
    from servicenow.services.prompt_store import get_prompt
    from servicenow.services.ai_assist import _call_llm, _extract_json_dict

    result_data = request.POST.get('result_data', '').strip()
    spl = request.POST.get('spl', '').strip()

    if not result_data:
        return render(request, 'splunk/partials/ai_analysis.html', {
            'ai_error': 'No result data to analyze.',
        })

    system = get_prompt('splunk_results_analysis')
    user_prompt = f"SPL Query: {spl}\n\nSearch Results:\n{result_data[:8000]}"

    raw = _call_llm(system, user_prompt)

    ai_error = None
    ai_response = None
    parsed = _extract_json_dict(raw)
    if parsed and '_ai_error' in parsed:
        ai_error = parsed['_ai_error']
    else:
        ai_response = raw

    return render(request, 'splunk/partials/ai_analysis.html', {
        'ai_response': ai_response,
        'ai_error': ai_error,
    })


@csrf_exempt
@require_POST
def ai_natural_to_spl(request):
    """Generate SPL from natural language description."""
    from servicenow.services.prompt_store import get_prompt
    from servicenow.services.ai_assist import _call_llm, _extract_json_dict

    description = request.POST.get('description', '').strip()
    if not description:
        return JsonResponse({'error': 'Description is required.'})

    system = get_prompt('splunk_natural_language_to_spl')
    raw = _call_llm(system, description)

    parsed = _extract_json_dict(raw)
    if not parsed:
        return JsonResponse({'error': f'AI returned unparseable response: {raw[:200]}'})
    if '_ai_error' in parsed:
        return JsonResponse({'error': parsed['_ai_error']})

    return JsonResponse({
        'spl': parsed.get('spl', ''),
        'earliest': parsed.get('earliest', '-1h'),
        'latest': parsed.get('latest', 'now'),
        'explanation': parsed.get('explanation', ''),
    })


@csrf_exempt
@require_POST
def ai_generate_preset(request):
    """Generate a preset definition from raw SPL."""
    from servicenow.services.prompt_store import get_prompt
    from servicenow.services.ai_assist import _call_llm, _extract_json_dict

    spl = request.POST.get('spl', '').strip()
    if not spl:
        return JsonResponse({'error': 'SPL query is required.'})

    system = get_prompt('splunk_preset_generator')
    raw = _call_llm(system, f"Generate a preset for this SPL query:\n\n{spl}")

    parsed = _extract_json_dict(raw)
    if not parsed:
        return JsonResponse({'error': f'AI returned unparseable response: {raw[:200]}'})
    if '_ai_error' in parsed:
        return JsonResponse({'error': parsed['_ai_error']})

    return JsonResponse({
        'name': parsed.get('name', ''),
        'description': parsed.get('description', ''),
        'spl': parsed.get('spl', spl),
        'required_params': parsed.get('required_params', []),
        'tags': parsed.get('tags', ''),
        'earliest_time': parsed.get('earliest_time', '-10m'),
        'latest_time': parsed.get('latest_time', 'now'),
    })

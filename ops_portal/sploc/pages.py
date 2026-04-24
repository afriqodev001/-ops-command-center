"""
SPLOC UI pages — HTML views + HTMX partials.
"""
from __future__ import annotations
import json

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from django.conf import settings as dj_settings

from .url_builders import build_apm_url
from .services.prompt_packs import (
    list_packs, get_pack, save_pack, delete_pack,
    export_packs, import_packs,
)
from .services.trace_history import (
    add_recent, list_recent, delete_recent, clear_recent,
)


# ─── Full Pages ─────────────────────────────────────────────

def sploc_home(request):
    return render(request, 'sploc/index.html')


def sploc_traces(request):
    return render(request, 'sploc/traces.html', {
        'prefill_trace_id': request.GET.get('trace_id', '').strip(),
        'prefill_service_name': request.GET.get('service_name', '').strip(),
        'autorun': request.GET.get('autorun', '').strip(),
        'recents': list_recent(limit=10),
    })


def sploc_ai_page(request):
    packs = list_packs()
    use_name = request.GET.get('use', '').strip()
    prefill = packs.get(use_name) if use_name else None
    return render(request, 'sploc/ai.html', {
        'packs': packs,
        'total_packs': len(packs),
        'prefill_prompt': prefill.get('prompt', '') if prefill else '',
        'prefill_start_new_chat': bool(prefill.get('defaults', {}).get('start_new_chat')) if prefill else False,
        'prefill_use_page_filters': bool(prefill.get('defaults', {}).get('use_page_filters')) if prefill else False,
        'prefill_close_panel': bool(prefill.get('defaults', {}).get('close_panel_at_end', True)) if prefill else True,
    })


def sploc_prompts_page(request):
    return render(request, 'sploc/prompts.html', {
        'packs': list_packs(),
    })


# ─── Trace Scraping (HTMX) ─────────────────────────────────

@csrf_exempt
@require_POST
def run_trace_scrape(request):
    """HTMX endpoint: dispatch a trace scrape and return a polling card."""
    from .session_views import is_session_alive
    if not is_session_alive():
        return render(request, 'sploc/partials/error.html', {
            'error': 'SPLOC session is not connected. Use the Connect button in the sidebar.',
        })

    trace_id = request.POST.get('trace_id', '').strip()
    service_name = request.POST.get('service_name', '').strip()

    if not trace_id:
        return render(request, 'sploc/partials/error.html', {
            'error': 'Trace ID is required.',
        })

    if not service_name:
        return render(request, 'sploc/partials/error.html', {
            'error': 'Service name is required.',
        })

    from .tasks import sploc_trace_scrape_task
    task = sploc_trace_scrape_task.delay({
        'trace_id': trace_id,
        'service_name': service_name,
        'max_spans': int(request.POST.get('max_spans', 0)),
    })

    return render(request, 'sploc/partials/running.html', {
        'task_id': task.id,
        'poll_url': f'/sploc/ui/trace/poll/{task.id}/',
        'description': f'Scraping trace {trace_id[:12]}…',
        'detail': f'Service: {service_name}',
    })


def poll_trace_scrape(request, task_id):
    """HTMX polling endpoint for trace scrape results."""
    from celery.result import AsyncResult
    ar = AsyncResult(task_id)

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'sploc/partials/running.html', {
            'task_id': task_id,
            'poll_url': f'/sploc/ui/trace/poll/{task_id}/',
            'description': 'Scraping trace waterfall…',
        })

    if ar.state == 'FAILURE':
        return render(request, 'sploc/partials/error.html', {
            'error': str(ar.result),
        })

    result = ar.result or {}
    if result.get('error'):
        return render(request, 'sploc/partials/error.html', {
            'error': result.get('detail') or result.get('error'),
        })

    rows = result.get('rows') or []
    services = sorted(set(r.get('service', '') for r in rows if r.get('service')))

    # Persist to recents on successful scrape
    trace_id = result.get('trace_id', '')
    service_name = result.get('service_name', '')
    if trace_id and service_name:
        add_recent(trace_id, service_name, total_spans=result.get('total_spans', len(rows)))

    return render(request, 'sploc/partials/trace_results.html', {
        'result': result,
        'result_json': json.dumps(result, default=str),
        'rows': rows,
        'services': services,
        'total_spans': result.get('total_spans', len(rows)),
        'trace_id': result.get('trace_id', ''),
        'trace_url': result.get('trace_url', ''),
    })


# ─── AI Assistant (HTMX) ───────────────────────────────────

@csrf_exempt
@require_POST
def run_ai_ask(request):
    """HTMX endpoint: dispatch an AI assistant query and return a polling card."""
    from .session_views import is_session_alive
    if not is_session_alive():
        return render(request, 'sploc/partials/error.html', {
            'error': 'SPLOC session is not connected. Use the Connect button in the sidebar.',
        })

    prompt = request.POST.get('prompt', '').strip()

    if not prompt:
        return render(request, 'sploc/partials/error.html', {
            'error': 'A prompt is required.',
        })

    from .tasks import sploc_ai_ask_task
    task = sploc_ai_ask_task.delay({
        'prompt': prompt,
        'navigate_to_apm': bool(request.POST.get('navigate_to_apm', True)),
        'use_page_filters': request.POST.get('use_page_filters'),
        'start_new_chat': bool(request.POST.get('start_new_chat')),
        'close_panel_at_end': bool(request.POST.get('close_panel_at_end', True)),
    })

    return render(request, 'sploc/partials/running.html', {
        'task_id': task.id,
        'poll_url': f'/sploc/ui/ai/poll/{task.id}/',
        'description': 'Asking AI Assistant…',
        'detail': prompt[:100],
    })


def poll_ai_ask(request, task_id):
    """HTMX polling endpoint for AI assistant results."""
    from celery.result import AsyncResult
    ar = AsyncResult(task_id)

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'sploc/partials/running.html', {
            'task_id': task_id,
            'poll_url': f'/sploc/ui/ai/poll/{task_id}/',
            'description': 'Waiting for AI response…',
        })

    if ar.state == 'FAILURE':
        return render(request, 'sploc/partials/error.html', {
            'error': str(ar.result),
        })

    result = ar.result or {}
    if result.get('error'):
        return render(request, 'sploc/partials/error.html', {
            'error': result.get('detail') or result.get('error'),
        })

    return render(request, 'sploc/partials/ai_results.html', {
        'result': result,
        'prompt': result.get('prompt', ''),
        'markdown': result.get('markdown', ''),
        'timestamp': result.get('timestamp', ''),
        'url': result.get('url', ''),
    })


# ─── Export trace data ──────────────────────────────────────

@csrf_exempt
@require_POST
def export_trace_json(request):
    """Export trace results as a downloadable JSON file."""
    data = request.POST.get('result_data', '{}')
    resp = HttpResponse(data, content_type='application/json')
    resp['Content-Disposition'] = 'attachment; filename="sploc_trace_spans.json"'
    return resp


# ─── AI Analysis (HTMX) ────────────────────────────────────

@csrf_exempt
@require_POST
def ai_analyze_trace(request):
    """Analyze trace results with AI — uploads trace JSON as a file attachment."""
    import uuid
    from pathlib import Path
    from servicenow.services.prompt_store import get_prompt

    result_data = request.POST.get('result_data', '').strip()
    user_context = request.POST.get('user_context', '').strip()

    if not result_data:
        return render(request, 'sploc/partials/ai_analysis.html', {
            'ai_error': 'No trace data to analyze.',
        })

    system = get_prompt('sploc_trace_analysis')
    user_prompt = "Analyze the SignalFx trace waterfall in the attached file."
    if user_context:
        user_prompt += f"\n\nUser's question/context: {user_context}"
    user_prompt += "\n\nThe full trace data is in the attached file. Analyze it thoroughly."

    tmp_dir = Path(getattr(dj_settings, 'MEDIA_ROOT', 'media')) / 'sploc_ai_tmp'
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f'{uuid.uuid4().hex}_trace.json'
    tmp_path.write_text(result_data, encoding='utf-8')

    from tachyon.tasks import run_tachyon_llm_with_file_task
    from servicenow.services.ai_assist import _get_ai_config

    cfg = _get_ai_config()
    task = run_tachyon_llm_with_file_task.delay(
        user_key='localuser',
        preset_slug=cfg.get('tachyon_preset_slug', 'default'),
        query=user_prompt,
        file_path=str(tmp_path),
        folder_name='sploc_analysis',
        folder_id=None,
        reuse_if_exists=False,
        overrides={
            'systemInstruction': system,
            **(({'modelId': cfg['model']} if cfg.get('model') else {})),
        },
    )

    return render(request, 'sploc/partials/ai_analysis_polling.html', {
        'task_id': task.id,
        'ai_system_prompt': system,
        'ai_user_prompt': user_prompt,
    })


def ai_analyze_poll(request, task_id):
    """Poll for AI trace analysis result."""
    from celery.result import AsyncResult
    from servicenow.services.ai_assist import _extract_json_dict

    ar = AsyncResult(task_id)

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'sploc/partials/ai_analysis_polling.html', {
            'task_id': task_id,
        })

    if ar.state == 'FAILURE':
        return render(request, 'sploc/partials/ai_analysis.html', {
            'ai_error': str(ar.result),
        })

    result = ar.result or {}
    if result.get('error'):
        return render(request, 'sploc/partials/ai_analysis.html', {
            'ai_error': result.get('detail') or result.get('error'),
        })

    raw = ''
    data = result.get('data') or result
    if isinstance(data, dict):
        raw = data.get('answer') or data.get('response') or data.get('text') or ''
    if not raw and isinstance(result, dict):
        raw = result.get('answer') or result.get('response') or result.get('text') or ''
    if not raw:
        raw = str(result)

    ai_response = raw
    ai_error = None
    parsed = _extract_json_dict(raw)
    if parsed and '_ai_error' in parsed:
        ai_error = parsed['_ai_error']
        ai_response = None
    elif parsed:
        ai_response = (
            parsed.get('answer')
            or parsed.get('response')
            or parsed.get('text')
            or parsed.get('content')
            or raw
        )

    return render(request, 'sploc/partials/ai_analysis.html', {
        'ai_response': ai_response,
        'ai_error': ai_error,
    })


@csrf_exempt
@require_POST
def export_trace_tsv(request):
    """Export trace results as a downloadable TSV file."""
    try:
        result = json.loads(request.POST.get('result_data', '{}'))
    except json.JSONDecodeError:
        result = {}

    rows = result.get('rows') or []
    cols = ["index", "span_id", "service", "operation", "duration", "indent_px"]

    lines = ["\t".join(cols)]
    for r in rows:
        lines.append("\t".join("" if r.get(c) is None else str(r.get(c)) for c in cols))

    tsv_content = "\n".join(lines)
    resp = HttpResponse(tsv_content, content_type='text/tab-separated-values')
    resp['Content-Disposition'] = 'attachment; filename="sploc_trace_spans.tsv"'
    return resp


# ─── Prompt pack management ────────────────────────────────

def packs_list_partial(request):
    """HTMX: refresh the management grid."""
    return render(request, 'sploc/partials/packs_list.html', {
        'packs': list_packs(),
    })


def packs_quick_partial(request):
    """HTMX: refresh the quick-prompts sidebar list on the AI page."""
    return render(request, 'sploc/partials/packs_quick.html', {
        'packs': list_packs(),
    })


def pack_editor(request):
    """Return create/edit form fragment."""
    name = request.GET.get('name', '').strip()
    pack = get_pack(name) if name else None
    return render(request, 'sploc/partials/pack_editor.html', {
        'name': name,
        'pack': pack,
    })


@csrf_exempt
@require_POST
def pack_save_view(request):
    name = request.POST.get('name', '').strip()
    if not name:
        return render(request, 'sploc/partials/packs_list.html', {
            'packs': list_packs(),
            'error': 'Pack name is required.',
        })

    pack = {
        'description': request.POST.get('description', '').strip(),
        'prompt': request.POST.get('prompt', '').strip(),
        'tags': request.POST.get('tags', '').strip(),
        'defaults': {
            'use_page_filters': bool(request.POST.get('use_page_filters')),
            'start_new_chat': bool(request.POST.get('start_new_chat')),
            'close_panel_at_end': bool(request.POST.get('close_panel_at_end', True)),
        },
    }
    save_pack(name, pack)
    return render(request, 'sploc/partials/packs_list.html', {
        'packs': list_packs(),
        'saved_name': name,
    })


@csrf_exempt
@require_POST
def pack_delete_view(request):
    name = request.POST.get('name', '').strip()
    if name:
        delete_pack(name)
    return render(request, 'sploc/partials/packs_list.html', {
        'packs': list_packs(),
    })


def pack_export_all(request):
    data = json.dumps(export_packs(), indent=2, default=str)
    resp = HttpResponse(data, content_type='application/json')
    resp['Content-Disposition'] = 'attachment; filename="sploc_prompt_packs.json"'
    return resp


def pack_export_one(request, name):
    data = json.dumps(export_packs([name]), indent=2, default=str)
    safe = name[:40].replace(' ', '_')
    resp = HttpResponse(data, content_type='application/json')
    resp['Content-Disposition'] = f'attachment; filename="sploc_pack_{safe}.json"'
    return resp


def pack_import_form(request):
    return render(request, 'sploc/partials/pack_import_form.html')


@csrf_exempt
@require_POST
def pack_import_preview(request):
    upload = request.FILES.get('file')
    if not upload:
        return render(request, 'sploc/partials/pack_import_preview.html', {
            'error': 'No file selected.',
        })
    try:
        raw = upload.read()
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8-sig', errors='replace')
        data = json.loads(raw)
    except Exception as e:
        return render(request, 'sploc/partials/pack_import_preview.html', {
            'error': f'Invalid JSON: {e}',
        })

    incoming = data.get('packs') or data.get('presets') or {}
    if not incoming:
        return render(request, 'sploc/partials/pack_import_preview.html', {
            'error': 'No packs found in file.',
        })

    existing = list_packs()
    preview = []
    for name, cfg in incoming.items():
        prompt = cfg.get('prompt', '')
        preview.append({
            'name': name,
            'description': cfg.get('description', ''),
            'prompt_preview': (prompt[:120] + '…') if len(prompt) > 120 else prompt,
            'exists': name in existing,
        })

    return render(request, 'sploc/partials/pack_import_preview.html', {
        'preview': preview,
        'packs_json': json.dumps(data),
    })


@csrf_exempt
@require_POST
def pack_import_confirm(request):
    try:
        data = json.loads(request.POST.get('packs_json', '{}'))
    except json.JSONDecodeError:
        data = {}
    mode = request.POST.get('conflict_mode', 'skip')
    imported = import_packs(data, mode)
    return render(request, 'sploc/partials/packs_list.html', {
        'packs': list_packs(),
        'import_count': imported,
    })


# ─── Trace history (recents) ───────────────────────────────

def recents_partial(request):
    """HTMX: re-render the recents panel (after add/delete/clear)."""
    return render(request, 'sploc/partials/recents_panel.html', {
        'recents': list_recent(limit=10),
    })


@csrf_exempt
@require_POST
def recent_delete(request):
    trace_id = request.POST.get('trace_id', '').strip()
    service_name = request.POST.get('service_name', '').strip()
    if trace_id and service_name:
        delete_recent(trace_id, service_name)
    return render(request, 'sploc/partials/recents_panel.html', {
        'recents': list_recent(limit=10),
    })


@csrf_exempt
@require_POST
def recents_clear(request):
    clear_recent()
    return render(request, 'sploc/partials/recents_panel.html', {
        'recents': list_recent(limit=10),
    })

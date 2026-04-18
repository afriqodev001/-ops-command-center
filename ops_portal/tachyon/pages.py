"""
Tachyon Playground UI views — HTML pages + HTMX partials.

Separated from views.py (JSON API endpoints) following the servicenow
app pattern: pages.py for HTML, views.py for JSON.
"""

from __future__ import annotations
import json

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods

from .models import TachyonPreset


# ─── Tachyon session management ───────────────────────────────

import time
import urllib.request

_INTEGRATION = 'tachyon'


def _tachyon_base():
    from django.conf import settings as s
    return getattr(s, 'TACHYON_BASE', 'https://your-tachyon-instance.net')


def _is_tachyon_browser_alive(port) -> bool:
    if not port:
        return False
    try:
        with urllib.request.urlopen(
            f'http://127.0.0.1:{port}/json/version', timeout=1.5
        ) as resp:
            return getattr(resp, 'status', 200) == 200
    except Exception:
        return False


def _format_age(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s ago"
    if seconds < 3600:
        return f"{int(seconds / 60)}m ago"
    if seconds < 86400:
        return f"{int(seconds / 3600)}h ago"
    return f"{int(seconds / 86400)}d ago"


def _build_tachyon_session_context():
    from core.browser.registry import load_session, all_sessions

    session = load_session(_INTEGRATION, 'localuser')
    if not session:
        all_ = all_sessions(_INTEGRATION)
        if all_:
            key, session = next(iter(all_.items()))

    if not session:
        return {
            'tachyon_status': 'none',
            'tachyon_status_label': 'No session',
            'tachyon_session': None,
        }

    port = session.get('debug_port')
    last_used = session.get('last_used')
    last_used_ago = _format_age(time.time() - last_used) if last_used else 'unknown'
    alive = _is_tachyon_browser_alive(port)

    if alive:
        status, label = 'active', 'Connected'
    elif port or session.get('pid'):
        status, label = 'disconnected', 'Session saved'
    else:
        status, label = 'pending', 'Session created'

    return {
        'tachyon_status': status,
        'tachyon_status_label': label,
        'tachyon_session': session,
        'tachyon_port': port,
        'tachyon_last_used_ago': last_used_ago,
    }


def tachyon_session_widget(request):
    ctx = _build_tachyon_session_context()
    return render(request, 'tachyon/partials/session_widget.html', ctx)


@csrf_exempt
@require_POST
def tachyon_session_connect(request):
    from core.browser import get_or_create_session, launch_edge, update_runtime_info

    session = get_or_create_session(_INTEGRATION, 'localuser')
    result = launch_edge(
        profile_dir=session['profile_dir'],
        debug_port=session['debug_port'],
        url=_tachyon_base(),
        headless=False,
    )
    update_runtime_info(
        _INTEGRATION, 'localuser',
        pid=result.get('pid'),
        mode=result.get('status'),
        origin=_tachyon_base(),
    )

    ctx = _build_tachyon_session_context()
    ctx['connecting'] = result.get('status') != 'failed'
    return render(request, 'tachyon/partials/session_widget.html', ctx)


@csrf_exempt
@require_POST
def tachyon_session_close_browser(request):
    from core.browser.registry import load_session
    from core.browser.shutdown import shutdown_browser

    session = load_session(_INTEGRATION, 'localuser')
    if session:
        shutdown_browser(
            debug_port=session.get('debug_port') or 0,
            pid=session.get('pid'),
        )
    ctx = _build_tachyon_session_context()
    return render(request, 'tachyon/partials/session_widget.html', ctx)


@csrf_exempt
@require_POST
def tachyon_session_disconnect(request):
    from core.browser.registry import load_session, clear_session
    from core.browser.shutdown import shutdown_browser

    session = load_session(_INTEGRATION, 'localuser')
    if session:
        shutdown_browser(
            debug_port=session.get('debug_port') or 0,
            pid=session.get('pid'),
        )
    clear_session(_INTEGRATION, 'localuser')
    ctx = _build_tachyon_session_context()
    return render(request, 'tachyon/partials/session_widget.html', ctx)


# ─── Main playground page ────────────────────────────────────

def playground(request):
    # Seed a default preset on first visit so the page is not empty
    if not TachyonPreset.objects.exists():
        TachyonPreset.objects.create(
            slug="default",
            title="Default (GPT 5.1)",
            description="General-purpose LLM preset",
            preset_id="default",
            default_model_id="gpt5.1",
            parameters={"temperature": 0.3, "maxTokens": 4096},
            system_instruction="You are a helpful assistant. Answer questions clearly and concisely.",
        )

    presets = list(TachyonPreset.objects.filter(enabled=True).order_by('title').values(
        'id', 'slug', 'title', 'description', 'preset_id',
        'default_model_id', 'parameters', 'system_instruction',
        'version', 'owner_team',
    ))
    # Ensure UUIDs serialize as strings
    for p in presets:
        p['id'] = str(p['id'])
    presets_json = json.dumps(presets, default=str)
    return render(request, 'tachyon/playground.html', {
        'presets': presets,
        'presets_json': presets_json,
    })


# ─── Preset CRUD ─────────────────────────────────────────────

def preset_list_partial(request):
    presets = TachyonPreset.objects.filter(enabled=True).order_by('title')
    return render(request, 'tachyon/partials/preset_list.html', {
        'presets': presets,
    })


@csrf_exempt
@require_POST
def preset_save(request):
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    slug = (data.get('slug') or '').strip()
    if not slug:
        return JsonResponse({'error': 'slug is required'}, status=400)

    preset, created = TachyonPreset.objects.update_or_create(
        slug=slug,
        defaults={
            'title':              data.get('title', slug),
            'description':        data.get('description', ''),
            'preset_id':          data.get('preset_id', ''),
            'default_model_id':   data.get('default_model_id', 'gpt5.1'),
            'parameters':         data.get('parameters') or {},
            'system_instruction': data.get('system_instruction', ''),
            'version':            int(data.get('version', 1)),
            'owner_team':         data.get('owner_team', ''),
            'enabled':            bool(data.get('enabled', True)),
        },
    )
    return JsonResponse({
        'ok': True,
        'created': created,
        'slug': preset.slug,
        'id': str(preset.id),
    })


@csrf_exempt
@require_POST
def preset_delete(request):
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    slug = (data.get('slug') or '').strip()
    deleted, _ = TachyonPreset.objects.filter(slug=slug).delete()
    return JsonResponse({'ok': True, 'deleted': bool(deleted)})


# ─── Run query (dispatches Celery task, returns task_id) ─────

@csrf_exempt
@require_POST
def run_query(request):
    """Unified run endpoint for the playground UI.
    Accepts JSON with mode='single' | 'with-file' | 'with-upload'.
    Dispatches the appropriate Celery task and returns {task_id}.
    """
    content_type = request.content_type or ''

    if 'multipart' in content_type:
        # File upload mode
        preset_slug = request.POST.get('preset', '')
        query = request.POST.get('query', '')
        model_id = request.POST.get('model_id', '')
        params_raw = request.POST.get('parameters', '')
        system_inst = request.POST.get('system_instruction', '')

        if not preset_slug or not query:
            return JsonResponse({'error': 'preset and query are required'}, status=400)

        overrides = {}
        if model_id:
            overrides['modelId'] = model_id
        if params_raw:
            try:
                overrides['parameters'] = json.loads(params_raw)
            except json.JSONDecodeError:
                return JsonResponse({'error': 'parameters must be valid JSON'}, status=400)
        if system_inst:
            overrides['systemInstruction'] = system_inst

        up = request.FILES.get('file')
        if up:
            import uuid
            from pathlib import Path
            from django.conf import settings as dj_settings

            tmp_dir = Path(getattr(dj_settings, 'TACHYON_UPLOAD_TMP_DIR', 'media/tachyon_uploads'))
            tmp_dir.mkdir(parents=True, exist_ok=True)
            safe_name = up.name.replace('\\', '_').replace('/', '_')
            tmp_path = tmp_dir / f'{uuid.uuid4().hex}_{safe_name}'
            with open(tmp_path, 'wb') as f:
                for chunk in up.chunks():
                    f.write(chunk)

            from .tasks import run_tachyon_llm_with_file_task
            task = run_tachyon_llm_with_file_task.delay(
                user_key='localuser',
                preset_slug=preset_slug,
                query=query,
                file_path=str(tmp_path),
                folder_name='uploads',
                folder_id=None,
                reuse_if_exists=True,
                overrides=overrides,
            )
            return JsonResponse({'task_id': task.id, 'mode': 'with-upload'})

        # No file — single mode
        from .tasks import run_tachyon_llm_task
        task = run_tachyon_llm_task.delay(
            user_key='localuser',
            preset_slug=preset_slug,
            query=query,
            overrides=overrides,
        )
        return JsonResponse({'task_id': task.id, 'mode': 'single'})

    # JSON body
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    preset_slug = data.get('preset', '')
    query = data.get('query', '')
    if not preset_slug or not query:
        return JsonResponse({'error': 'preset and query are required'}, status=400)

    overrides = {}
    if data.get('model_id'):
        overrides['modelId'] = data['model_id']
    if data.get('parameters'):
        overrides['parameters'] = data['parameters']
    if data.get('system_instruction'):
        overrides['systemInstruction'] = data['system_instruction']

    from .tasks import run_tachyon_llm_task
    task = run_tachyon_llm_task.delay(
        user_key='localuser',
        preset_slug=preset_slug,
        query=query,
        overrides=overrides,
    )
    return JsonResponse({'task_id': task.id, 'mode': 'single'})

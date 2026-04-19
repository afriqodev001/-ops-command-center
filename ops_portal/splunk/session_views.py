"""
Splunk browser session management — sidebar widget + connect/disconnect.
Same pattern as ServiceNow, Tachyon, and Copilot.
"""
from __future__ import annotations
import time
import urllib.request

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

_INTEGRATION = 'splunk'


def _splunk_base():
    from django.conf import settings as s
    return getattr(s, 'SPLUNK_BASE', 'https://your-splunk.splunkcloud.com')


def _is_browser_alive(port) -> bool:
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


def _build_session_context():
    from core.browser.registry import load_session, all_sessions

    session = load_session(_INTEGRATION, 'localuser')
    if not session:
        all_ = all_sessions(_INTEGRATION)
        if all_:
            key, session = next(iter(all_.items()))

    if not session:
        return {
            'splunk_status': 'none',
            'splunk_status_label': 'No session',
            'splunk_session': None,
        }

    port = session.get('debug_port')
    last_used = session.get('last_used')
    last_used_ago = _format_age(time.time() - last_used) if last_used else 'unknown'
    alive = _is_browser_alive(port)

    if alive:
        status, label = 'active', 'Connected'
    elif port or session.get('pid'):
        status, label = 'disconnected', 'Session saved'
    else:
        status, label = 'pending', 'Session created'

    return {
        'splunk_status': status,
        'splunk_status_label': label,
        'splunk_session': session,
        'splunk_port': port,
        'splunk_last_used_ago': last_used_ago,
    }


def is_session_alive() -> bool:
    from core.browser.registry import load_session
    session = load_session(_INTEGRATION, 'localuser')
    if not session:
        return False
    return _is_browser_alive(session.get('debug_port'))


def session_status_json(request):
    return JsonResponse({'alive': is_session_alive()})


def session_widget(request):
    ctx = _build_session_context()
    return render(request, 'splunk/partials/session_widget.html', ctx)


@csrf_exempt
@require_POST
def session_connect(request):
    from core.browser import get_or_create_session, launch_edge, update_runtime_info

    session = get_or_create_session(_INTEGRATION, 'localuser')
    result = launch_edge(
        profile_dir=session['profile_dir'],
        debug_port=session['debug_port'],
        url=_splunk_base(),
        headless=False,
    )
    update_runtime_info(
        _INTEGRATION, 'localuser',
        pid=result.get('pid'),
        mode=result.get('status'),
        origin=_splunk_base(),
    )

    ctx = _build_session_context()
    ctx['connecting'] = result.get('status') != 'failed'
    return render(request, 'splunk/partials/session_widget.html', ctx)


@csrf_exempt
@require_POST
def session_close_browser(request):
    from core.browser.registry import load_session
    from core.browser.shutdown import shutdown_browser

    session = load_session(_INTEGRATION, 'localuser')
    if session:
        shutdown_browser(
            debug_port=session.get('debug_port') or 0,
            pid=session.get('pid'),
        )
    ctx = _build_session_context()
    return render(request, 'splunk/partials/session_widget.html', ctx)


@csrf_exempt
@require_POST
def session_disconnect(request):
    from core.browser.registry import load_session, clear_session
    from core.browser.shutdown import shutdown_browser

    session = load_session(_INTEGRATION, 'localuser')
    if session:
        shutdown_browser(
            debug_port=session.get('debug_port') or 0,
            pid=session.get('pid'),
        )
    clear_session(_INTEGRATION, 'localuser')
    ctx = _build_session_context()
    return render(request, 'splunk/partials/session_widget.html', ctx)

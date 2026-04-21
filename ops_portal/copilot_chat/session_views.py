"""
Copilot browser session management — sidebar widget + connect/disconnect.

Mirrors the tachyon/pages.py session pattern exactly:
- Widget polls every 20s via HTMX
- Connect opens a headed Edge browser to Teams
- Close browser sends CDP close (cookies saved)
- Disconnect closes browser + clears session
"""

from __future__ import annotations
import time
import urllib.request

from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from django.http import JsonResponse

_INTEGRATION = 'copilot'


def _copilot_teams_url():
    from django.conf import settings as s
    return getattr(s, 'COPILOT_TEAMS_URL', 'https://teams.microsoft.com/v2/')


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
            'copilot_status': 'none',
            'copilot_status_label': 'No session',
            'copilot_session': None,
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
        'copilot_status': status,
        'copilot_status_label': label,
        'copilot_session': session,
        'copilot_port': port,
        'copilot_last_used_ago': last_used_ago,
    }


def is_session_alive() -> bool:
    """Quick check — is the Copilot browser session's CDP port responding?"""
    from core.browser.registry import load_session
    session = load_session(_INTEGRATION, 'localuser')
    if not session:
        return False
    return _is_browser_alive(session.get('debug_port'))


def session_status_json(request):
    """GET: returns {"alive": true/false} for frontend gating."""
    return JsonResponse({'alive': is_session_alive()})


def session_widget(request):
    ctx = _build_session_context()
    return render(request, 'copilot_chat/partials/session_widget.html', ctx)


@csrf_exempt
@require_POST
def session_connect(request):
    from core.browser import get_or_create_session, launch_edge, update_runtime_info
    from core.browser.shutdown import shutdown_browser

    session = get_or_create_session(_INTEGRATION, 'localuser')
    if _is_browser_alive(session.get('debug_port')):
        shutdown_browser(
            debug_port=session.get('debug_port') or 0,
            pid=session.get('pid'),
        )
        import time; time.sleep(1)

    result = launch_edge(
        profile_dir=session['profile_dir'],
        debug_port=session['debug_port'],
        url=_copilot_teams_url(),
        headless=False,
    )
    update_runtime_info(
        _INTEGRATION, 'localuser',
        pid=result.get('pid'),
        mode=result.get('status'),
        origin=_copilot_teams_url(),
    )

    ctx = _build_session_context()
    ctx['connecting'] = result.get('status') != 'failed'
    return render(request, 'copilot_chat/partials/session_widget.html', ctx)


@csrf_exempt
@require_POST
def session_reset(request):
    from core.browser.registry import reset_session
    reset_session(_INTEGRATION, 'localuser')
    ctx = _build_session_context()
    return render(request, 'copilot_chat/partials/session_widget.html', ctx)


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
    return render(request, 'copilot_chat/partials/session_widget.html', ctx)


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
    return render(request, 'copilot_chat/partials/session_widget.html', ctx)

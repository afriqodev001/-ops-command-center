import json
import time
import urllib.request
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render

from core.browser.registry import load_session, clear_session, all_sessions


# ─────────────────────────────────────────────────────────────
# Session status helpers
# ─────────────────────────────────────────────────────────────

_INTEGRATION = 'servicenow'


def _is_browser_alive(port) -> bool:
    """Liveness probe for the Edge CDP endpoint.

    Preferred over a PID check because the PID we stash at launch is often a
    launcher/wrapper that exits immediately; the real Edge window then runs
    under a child PID we never saw. What actually matters for automation is
    whether the CDP port still responds, so treat that as truth.
    """
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


def _resolve_session():
    """
    Find the best available servicenow session.
    Tries 'localuser' first, then falls back to any session in the integration dir.
    """
    session = load_session(_INTEGRATION, 'localuser')
    if session:
        return session, 'localuser'
    # scan for any session in this integration
    all_ = all_sessions(_INTEGRATION)
    if all_:
        key, session = next(iter(all_.items()))
        user_key = key.split('/', 1)[-1]
        return session, user_key
    return None, 'localuser'


def _build_session_context():
    """Return a dict describing the current session state for templates."""
    session, user_key = _resolve_session()

    if not session:
        return {
            'status': 'none',
            'status_label': 'No session',
            'user_key': user_key,
            'session': None,
        }

    pid = session.get('pid')
    port = session.get('debug_port')
    last_used = session.get('last_used')
    last_used_ago = _format_age(time.time() - last_used) if last_used else 'unknown'
    browser_alive = _is_browser_alive(port)

    # Auto-close the browser after idle to reclaim memory on laptops.
    if browser_alive and last_used:
        try:
            from servicenow.services.user_preferences import load_preferences
            idle_min = int(load_preferences().get('browser_idle_timeout_minutes', 30) or 30)
        except Exception:
            idle_min = 30
        idle_seconds = time.time() - last_used
        if idle_min > 0 and idle_seconds > idle_min * 60:
            from core.browser.shutdown import shutdown_browser
            shutdown_browser(debug_port=port or 0, pid=pid)
            browser_alive = False

    if browser_alive:
        status = 'active'
        status_label = 'Connected'
    elif port or pid:
        # We have a record of a session that isn't reachable right now.
        status = 'disconnected'
        status_label = 'Browser offline'
    else:
        status = 'pending'
        status_label = 'Session created'

    return {
        'status': status,
        'status_label': status_label,
        'user_key': user_key,
        'session': session,
        'pid': pid,
        'port': port,
        'last_used_ago': last_used_ago,
        'process_alive': browser_alive,   # kept key for backward compat
    }


# ─────────────────────────────────────────────────────────────
# Session UI views
# ─────────────────────────────────────────────────────────────

@require_http_methods(['GET'])
def session_widget(request):
    """HTMX-polled endpoint — returns just the sidebar widget HTML."""
    ctx = _build_session_context()
    return render(request, 'servicenow/partials/session_widget.html', ctx)


@require_http_methods(['GET'])
def session_modal_content(request):
    """Returns the modal body content for the session manager."""
    ctx = _build_session_context()
    return render(request, 'servicenow/partials/session_modal.html', ctx)


@csrf_exempt
@require_POST
def session_connect(request):
    """
    Launch the browser and open the ServiceNow login page.
    Delegates to the existing servicenow_login_open_task.
    Returns an HTMX-friendly response that refreshes the widget.
    """
    task = servicenow_login_open_task.delay({'headed': True})
    ctx = _build_session_context()
    ctx['task_id'] = task.id
    ctx['connecting'] = True
    _push_session_activity(request, 'session_connecting',
                           'Opening ServiceNow session…', 'info')
    resp = render(request, 'servicenow/partials/session_widget.html', ctx)
    resp['HX-Trigger'] = 'activity-updated'
    return resp


@csrf_exempt
@require_POST
def session_disconnect(request):
    """Clear the session file and return a refreshed widget."""
    _, user_key = _resolve_session()
    clear_session(_INTEGRATION, user_key)
    ctx = _build_session_context()
    _push_session_activity(request, 'session_disconnected',
                           'Cleared ServiceNow session', 'warning')
    resp = render(request, 'servicenow/partials/session_widget.html', ctx)
    resp['HX-Trigger'] = 'activity-updated'
    return resp


@csrf_exempt
@require_POST
def session_reset(request):
    """Full reset: close browser, delete profile directory, clear session."""
    from core.browser.registry import reset_session
    _, user_key = _resolve_session()
    reset_session(_INTEGRATION, user_key)
    ctx = _build_session_context()
    _push_session_activity(request, 'session_reset',
                           'Reset ServiceNow session (profile deleted)', 'warning')
    resp = render(request, 'servicenow/partials/session_widget.html', ctx)
    resp['HX-Trigger'] = 'activity-updated'
    return resp


@csrf_exempt
@require_POST
def session_close_browser(request):
    """Kill the Edge process but keep the session profile (cookies persist).
    The next Table API task will auto-launch a headless instance using the
    same profile, so cookies carry over."""
    session, user_key = _resolve_session()
    if session:
        from core.browser.shutdown import shutdown_browser
        port = session.get('debug_port')
        pid = session.get('pid')
        if port or pid:
            shutdown_browser(debug_port=port or 0, pid=pid)
    _push_session_activity(request, 'session_browser_closed',
                           'Closed browser (cookies saved)', 'info')
    ctx = _build_session_context()
    resp = render(request, 'servicenow/partials/session_widget.html', ctx)
    resp['HX-Trigger'] = 'activity-updated'
    return resp


def _push_session_activity(request, event_type: str, title: str, severity: str):
    """Local wrapper — session views live in this file; keep the import lazy."""
    try:
        from .services.activity import push
        if hasattr(request, 'session'):
            push(request.session, type=event_type, title=title, severity=severity)
    except Exception:
        pass

from servicenow.tasks import (
    servicenow_login_open_task,
    changes_get_task, changes_patch_task,
    incidents_get_task, incidents_patch_task,
    table_list_task,
    table_get_by_field_task,
    table_bulk_get_by_field_task,
    changes_get_by_number_task,
    changes_bulk_get_by_number_task,
    presets_list_task,
    presets_run_task,
    attachments_list_task,
    ctasks_list_for_change_task,
    change_context_task,
    changes_create_task,
    incident_context_task,
    incidents_create_task,
    incident_get_by_field_task,
    incident_bulk_get_by_field_task,
    incident_presets_list_task,
    incident_presets_run_task,
)


def _body(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return {}


@csrf_exempt
@require_POST
def servicenow_login_open(request):
    task = servicenow_login_open_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def changes_get(request):
    task = changes_get_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def changes_patch(request):
    task = changes_patch_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def incidents_get(request):
    task = incidents_get_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def incidents_patch(request):
    task = incidents_patch_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def table_list(request):
    task = table_list_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def table_get_by_field(request):
    task = table_get_by_field_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def table_bulk_get_by_field(request):
    task = table_bulk_get_by_field_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def changes_get_by_number(request):
    task = changes_get_by_number_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def changes_bulk_get_by_number(request):
    task = changes_bulk_get_by_number_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def presets_list(request):
    task = presets_list_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def presets_run(request):
    task = presets_run_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def attachments_list(request):
    task = attachments_list_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def ctasks_list_for_change(request):
    task = ctasks_list_for_change_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def changes_context(request):
    task = change_context_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def changes_create(request):
    task = changes_create_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def incidents_context(request):
    task = incident_context_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def incidents_create(request):
    task = incidents_create_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def incidents_get_by_field(request):
    task = incident_get_by_field_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def incidents_bulk_get_by_field(request):
    task = incident_bulk_get_by_field_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def incidents_presets_list(request):
    task = incident_presets_list_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def incidents_presets_run(request):
    task = incident_presets_run_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)
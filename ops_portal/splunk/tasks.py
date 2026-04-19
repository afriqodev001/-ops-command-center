from celery import shared_task
from splunk.runners.splunk_runner import SplunkRunner
from splunk.services.splunk_alerts import search_alerts
from core.browser import BrowserLoginRequired
from core.browser.registry import get_or_create_session

from splunk.services.splunk_jobs import (
    create_search_job,
    get_job_status,
    get_job_events,
    get_job_results_preview,
)

from splunk.services.splunk_presets import list_presets, render_preset
from splunk.services.splunk_saved_searches import (
    get_saved_search_by_name,
    extract_spl_from_saved_search,
    extract_time_bounds_from_saved_search,
)

from django.conf import settings
import time

from splunk.services.splunk_alerts_list import list_saved_searches

from splunk.services.formatters.job_events_formatter import prune_splunk_events_payload
from splunk.services.formatters.job_status_formatter import prune_splunk_job_status
from splunk.services.formatters.task_response_formatter import prune_splunk_task_response


def _user_key(body: dict) -> str:
    return (body or {}).get("user_key") or "localuser"


@shared_task(bind=True)
def splunk_login_open_task(self, body: dict):
    """
    Open Splunk login (headed browser) so user can complete SSO.

    Safe to call multiple times.
    Returns session snapshot for UI.
    """
    body = body or {}
    user_key = _user_key(body)

    runner = SplunkRunner(user_key)

    try:
        # This intentionally opens a headed browser
        return runner.open_login()

    except BrowserLoginRequired:
        # Expected path: login UI opened
        session = get_or_create_session("splunk", user_key)
        return {
            "status": "login_opened",
            "integration": "splunk",
            "profile_dir": session.get("profile_dir"),
            "debug_port": session.get("debug_port"),
        }


@shared_task(bind=True)
def splunk_alerts_search_task(self, body: dict):
    """
    Search Splunk saved searches (Alerts tab) by name fragment.

    Splunk-specific behavior:
    - Splunk Cloud uses enforced enterprise SSO
    - There is no reliable interactive login state
    - Authentication is determined ONLY by fetch() response

    Therefore:
    - No BrowserLoginRequired handling here
    - No forced login opens
    - Treat 401/403 from fetch as auth failure
    """
    body = body or {}
    search_term = body.get("search_term")

    if not search_term:
        return {
            "error": "missing_parameter",
            "detail": "search_term is required",
            "example": {"search_term": "blend"},
        }

    runner = SplunkRunner(_user_key(body))

    # Always get a driver; auth is not checked here
    driver = runner.get_driver()

    result = search_alerts(
        driver,
        search_term=search_term,
        count=int(body.get("count", 20)),
        offset=int(body.get("offset", 0)),
    )

    # Auth handling (authoritative via fetch response)
    if result.get("error") == "unauthorized":
        return {
            "error": "login_required",
            "integration": "splunk",
            "detail": "Splunk SSO session expired. Refresh browser session.",
        }

    return result


@shared_task(bind=True)
def splunk_job_create_task(self, body: dict):
    """
    Create a Splunk search job and return its SID.
    """
    body = body or {}
    search = body.get("search")
    namespace_user = body.get("namespace_user")

    if not search:
        return {
            "error": "missing_parameter",
            "detail": "search is required",
            "example": {"search": 'index=pldcs sourcetype="hec:ocp:app" | stats count'},
        }

    if not namespace_user:
        return {
            "error": "missing_parameter",
            "detail": "namespace_user is required for job creation (servicesNS/<user>/<app>/...)",
            "example": {"namespace_user": "joshua.kanani@wellsfargo.com"},
        }

    runner = SplunkRunner((body or {}).get("user_key") or "localuser")
    driver = runner.get_driver()

    result = create_search_job(
        driver,
        namespace_user=namespace_user,
        search=search,
        earliest_time=body.get("earliest_time", "-10m"),
        latest_time=body.get("latest_time", "now"),
        preview=bool(body.get("preview", True)),
        adhoc_search_level=body.get("adhoc_search_level", "verbose"),
        extra_params=body.get("extra_params") or None,
    )

    if result.get("error") == "unauthorized":
        return {
            "error": "login_required",
            "integration": "splunk",
            "detail": "Splunk SSO session expired. Refresh browser session.",
        }

    return result


@shared_task(bind=True)
def splunk_job_status_task(self, body: dict):
    """
    Fetch status for a Splunk job SID.
    """
    body = body or {}
    sid = body.get("sid")

    if not sid:
        return {
            "error": "missing_parameter",
            "detail": "sid is required",
            "example": {"sid": "1775090335.82002_80F3CA82-909C-49D2-9026-EB015359C393"},
        }

    runner = SplunkRunner((body or {}).get("user_key") or "localuser")
    driver = runner.get_driver()

    result = get_job_status(
        driver,
        sid=sid,
        namespace_user=body.get("namespace_user", "nobody"),
    )

    if result.get("error") == "unauthorized":
        return {
            "error": "login_required",
            "integration": "splunk",
            "detail": "Splunk SSO session expired. Refresh browser session.",
        }

    return prune_splunk_job_status(result)


@shared_task(bind=True)
def splunk_job_events_task(self, body: dict):
    """
    Get raw events for a Splunk search job SID (Events tab).
    """
    body = body or {}
    sid = body.get("sid")

    if not sid:
        return {
            "error": "missing_parameter",
            "detail": "sid is required",
            "example": {"sid": "1775090335.82002_80F3CA82-909C-49D2-9026-EB015359C393"},
        }

    runner = SplunkRunner(_user_key(body))
    driver = runner.get_driver()

    result = get_job_events(
        driver,
        sid=sid,
        offset=int(body.get("offset", 0)),
        count=int(body.get("count", 20)),
        segmentation=body.get("segmentation", "full"),
        max_lines=int(body.get("max_lines", 5)),
        field_list=body.get("field_list"),
        truncation_mode=body.get("truncation_mode", "abstract"),
    )

    if result.get("error") == "unauthorized":
        return {
            "error": "login_required",
            "integration": "splunk",
            "detail": "Splunk SSO session expired. Refresh browser session.",
        }

    return prune_splunk_events_payload(result)


@shared_task(bind=True)
def splunk_job_results_preview_task(self, body: dict):
    """
    Get results preview for a Splunk search job SID (Statistics tab).
    """
    body = body or {}
    sid = body.get("sid")

    if not sid:
        return {
            "error": "missing_parameter",
            "detail": "sid is required",
            "example": {"sid": "1775090335.82002_80F3CA82-909C-49D2-9026-EB015359C393"},
        }

    runner = SplunkRunner(_user_key(body))
    driver = runner.get_driver()

    result = get_job_results_preview(
        driver,
        sid=sid,
        offset=int(body.get("offset", 0)),
        count=int(body.get("count", 20)),
        show_metadata=bool(body.get("show_metadata", True)),
        add_summary_to_metadata=bool(body.get("add_summary_to_metadata", False)),
    )

    if result.get("error") == "unauthorized":
        return {
            "error": "login_required",
            "integration": "splunk",
            "detail": "Splunk SSO session expired. Refresh browser session.",
        }

    return result


@shared_task(bind=True)
def splunk_search_run_task(self, body: dict):
    """
    /api/splunk/search/run/  (single-call convenience endpoint)

    Flow:
      1) Create Splunk search job -> sid
      2) Poll job status until done OR bounded max_polls reached
      3) Fetch results_preview (Statistics tab) and/or events (Events tab)
      4) Return unified payload

    Notes:
    - Polling happens inside Celery (so the API thread stays fast).
    - Bounded polling prevents worker exhaustion.
    - If job isn't done yet, we still return sid + latest status and
      (optionally) preview data if Splunk provides it.
    """
    body = body or {}

    search = (body.get("search") or "").strip()
    namespace_user = (body.get("namespace_user") or "").strip()

    if not search:
        return {
            "error": "missing_parameter",
            "detail": "search is required",
            "example": {
                "search": 'index=pldcs sourcetype="hec:ocp:app" | stats count'
            },
        }

    if not namespace_user:
        return {
            "error": "missing_parameter",
            "detail": "namespace_user is required (servicesNS/<user>/<app>/...) for job creation",
            "example": {"namespace_user": "xx.xx@kuku.com"},
        }

    # Output selection
    include_preview = bool(body.get("include_preview", True))
    include_events = bool(body.get("include_events", False))

    # Polling controls (bounded)
    max_polls = int(body.get("max_polls", 12))
    poll_interval = float(body.get("poll_interval", 1))

    # Result paging controls
    preview_count = int(body.get("preview_count", 20))
    preview_offset = int(body.get("preview_offset", 0))

    events_count = int(body.get("events_count", 20))
    events_offset = int(body.get("events_offset", 0))
    events_max_lines = int(body.get("events_max_lines", 5))

    # Search time range
    earliest_time = body.get("earliest_time", "-10m")
    latest_time = body.get("latest_time", "now")

    runner = SplunkRunner(_user_key(body))
    driver = runner.get_driver()

    created = create_search_job(
        driver,
        namespace_user=namespace_user,
        search=search,
        earliest_time=earliest_time,
        latest_time=latest_time,
        preview=bool(body.get("preview", True)),
        adhoc_search_level=body.get("adhoc_search_level", "verbose"),
        extra_params=body.get("extra_params") or None,
    )

    if created.get("error") == "unauthorized":
        return {
            "error": "login_required",
            "integration": "splunk",
            "detail": "Splunk SSO session expired. Refresh browser session.",
        }

    if created.get("error"):
        return created

    sid = created["sid"]

    status_payload = None
    polls_used = 0
    done = False

    status_namespace_user = body.get("status_namespace_user", "nobody")

    for i in range(max_polls):
        polls_used = i + 1

        status_payload = get_job_status(
            driver,
            sid=sid,
            namespace_user=status_namespace_user,
        )

        if status_payload.get("error") == "unauthorized":
            return {
                "error": "login_required",
                "integration": "splunk",
                "detail": "Splunk SSO session expired. Refresh browser session.",
            }

        if status_payload.get("error"):
            return {
                "error": "status_failed",
                "sid": sid,
                "detail": status_payload,
            }

        done = bool((status_payload.get("status") or {}).get("isDone"))
        if done:
            break

        time.sleep(poll_interval)

    out_preview = None
    out_events = None

    results_namespace_user = body.get("results_namespace_user", "nobody")

    if include_preview:
        out_preview = get_job_results_preview(
            driver,
            sid=sid,
            namespace_user=results_namespace_user,
            offset=preview_offset,
            count=preview_count,
            show_metadata=bool(body.get("show_metadata", True)),
            add_summary_to_metadata=bool(body.get("add_summary_to_metadata", False)),
        )
        if out_preview.get("error") == "unauthorized":
            return {
                "error": "login_required",
                "integration": "splunk",
                "detail": "Splunk SSO session expired. Refresh browser session.",
            }

    if include_events:
        out_events = get_job_events(
            driver,
            sid=sid,
            namespace_user=results_namespace_user,
            offset=events_offset,
            count=events_count,
            max_lines=events_max_lines,
            segmentation=body.get("segmentation", "full"),
            field_list=body.get("field_list"),
            truncation_mode=body.get("truncation_mode", "abstract"),
        )
        if out_events.get("error") == "unauthorized":
            return {
                "error": "login_required",
                "integration": "splunk",
                "detail": "Splunk SSO session expired. Refresh browser session.",
            }

    return {
        "ok": True,
        "sid": sid,
        "job_created": created.get("response"),
        "status": status_payload,
        "done": done,
        "polls_used": polls_used,
        "preview": out_preview,
        "events": out_events,
    }


@shared_task(bind=True)
def splunk_search_run_async_task(self, body: dict):
    """
    Create a search job and return SID immediately (no polling).
    """
    body = body or {}
    search = (body.get("search") or "").strip()
    namespace_user = (body.get("namespace_user") or "").strip()

    if not search:
        return {"error": "missing_parameter", "detail": "search is required"}

    if not namespace_user:
        return {
            "error": "missing_parameter",
            "detail": "namespace_user is required (servicesNS/<user>/<app>/...)",
            "example": {"namespace_user": "joshua.kanani@wellsfargo.com"},
        }

    runner = SplunkRunner(_user_key(body))
    driver = runner.get_driver()

    created = create_search_job(
        driver,
        namespace_user=namespace_user,
        search=search,
        earliest_time=body.get(
            "earliest_time", getattr(settings, "SPLUNK_DEFAULT_EARLIEST", "-10m")
        ),
        latest_time=body.get(
            "latest_time", getattr(settings, "SPLUNK_DEFAULT_LATEST", "now")
        ),
        preview=bool(body.get("preview", True)),
        adhoc_search_level=body.get("adhoc_search_level", "verbose"),
        extra_params=body.get("extra_params") or None,
    )

    if created.get("error") == "unauthorized":
        return {
            "error": "login_required",
            "integration": "splunk",
            "detail": "Splunk SSO session expired.",
        }

    return created


# Alert → run search shortcut
# /api/splunk/alerts/run/  (bounded polling like search/run)
# /api/splunk/alerts/run_async/ (returns sid immediately)
@shared_task(bind=True)
def splunk_alert_run_task(self, body: dict):
    """
    Alert -> run search shortcut (sync mode with bounded polling).
    Steps:
      1) lookup saved search by alert_name
      2) extract SPL + time bounds
      3) call splunk_search_run_task-like flow (create + poll + fetch)
    """
    body = body or {}
    alert_name = (body.get("alert_name") or "").strip()
    namespace_user = (body.get("namespace_user") or "").strip()

    if not alert_name:
        return {"error": "missing_parameter", "detail": "alert_name is required"}

    if not namespace_user:
        return {
            "error": "missing_parameter",
            "detail": "namespace_user is required to lookup saved search",
            "example": {"namespace_user": "joshua.kanani@wellsfargo.com"},
        }

    include_preview = bool(body.get("include_preview", True))
    include_events = bool(body.get("include_events", False))

    max_polls = int(body.get("max_polls", getattr(settings, "SPLUNK_RUN_MAX_POLLS", 12)))
    poll_interval = float(
        body.get("poll_interval", getattr(settings, "SPLUNK_RUN_POLL_INTERVAL", 1.0))
    )

    runner = SplunkRunner(_user_key(body))
    driver = runner.get_driver()

    looked_up = get_saved_search_by_name(
        driver, namespace_user=namespace_user, name=alert_name
    )
    if looked_up.get("error") == "unauthorized":
        return {
            "error": "login_required",
            "integration": "splunk",
            "detail": "Splunk SSO session expired.",
        }
    if looked_up.get("error"):
        return looked_up

    content = looked_up.get("content") or {}
    spl = extract_spl_from_saved_search(content)
    if not spl:
        return {
            "error": "spl_not_found",
            "detail": f"Could not extract SPL for alert: {alert_name}",
        }

    # best-effort defaults; request overrides win
    earliest_default, latest_default = extract_time_bounds_from_saved_search(content)
    earliest_time = (
        body.get("earliest_time")
        or earliest_default
        or getattr(settings, "SPLUNK_DEFAULT_EARLIEST", "-10m")
    )
    latest_time = (
        body.get("latest_time")
        or latest_default
        or getattr(settings, "SPLUNK_DEFAULT_LATEST", "now")
    )

    created = create_search_job(
        driver,
        namespace_user=namespace_user,
        search=spl,
        earliest_time=earliest_time,
        latest_time=latest_time,
        preview=bool(body.get("preview", True)),
        adhoc_search_level=body.get("adhoc_search_level", "verbose"),
        extra_params=body.get("extra_params") or None,
    )

    if created.get("error"):
        return created

    sid = created["sid"]

    # poll
    status_namespace_user = body.get("status_namespace_user", "nobody")
    status_payload = None
    done = False
    for _ in range(max_polls):
        status_payload = get_job_status(
            driver, sid=sid, namespace_user=status_namespace_user
        )
        if status_payload.get("error"):
            return {"error": "status_failed", "sid": sid, "detail": status_payload}
        done = bool((status_payload.get("status") or {}).get("isDone"))
        if done:
            break
        time.sleep(poll_interval)

    # fetch outputs
    results_namespace_user = body.get("results_namespace_user", "nobody")
    preview_out = None
    events_out = None

    if include_preview:
        preview_out = get_job_results_preview(
            driver,
            sid=sid,
            namespace_user=results_namespace_user,
            offset=int(body.get("preview_offset", 0)),
            count=int(body.get("preview_count", 20)),
            show_metadata=bool(body.get("show_metadata", True)),
            add_summary_to_metadata=bool(body.get("add_summary_to_metadata", False)),
        )

    if include_events:
        events_out = get_job_events(
            driver,
            sid=sid,
            namespace_user=results_namespace_user,
            offset=int(body.get("events_offset", 0)),
            count=int(body.get("events_count", 20)),
            max_lines=int(body.get("events_max_lines", 5)),
            segmentation=body.get("segmentation", "full"),
            field_list=body.get("field_list"),
            truncation_mode=body.get("truncation_mode", "abstract"),
        )

    response = {
        "ok": True,
        "alert_name": alert_name,
        "sid": sid,
        "done": done,
        "status": status_payload,
        "preview": preview_out,
        "events": events_out,
        "saved_search": {"content": content},
    }

    return prune_splunk_task_response(response)


@shared_task(bind=True)
def splunk_alert_run_async_task(self, body: dict):
    """
    Alert -> run search shortcut (async mode: returns SID only).
    """
    body = body or {}
    alert_name = (body.get("alert_name") or "").strip()
    namespace_user = (body.get("namespace_user") or "").strip()

    if not alert_name:
        return {"error": "missing_parameter", "detail": "alert_name is required"}
    if not namespace_user:
        return {"error": "missing_parameter", "detail": "namespace_user is required"}

    runner = SplunkRunner(_user_key(body))
    driver = runner.get_driver()

    looked_up = get_saved_search_by_name(
        driver, namespace_user=namespace_user, name=alert_name
    )
    if looked_up.get("error"):
        return looked_up

    content = looked_up.get("content") or {}
    spl = extract_spl_from_saved_search(content)
    if not spl:
        return {
            "error": "spl_not_found",
            "detail": f"Could not extract SPL for alert: {alert_name}",
        }

    earliest_default, latest_default = extract_time_bounds_from_saved_search(content)
    earliest_time = (
        body.get("earliest_time")
        or earliest_default
        or getattr(settings, "SPLUNK_DEFAULT_EARLIEST", "-10m")
    )
    latest_time = (
        body.get("latest_time")
        or latest_default
        or getattr(settings, "SPLUNK_DEFAULT_LATEST", "now")
    )

    created = create_search_job(
        driver,
        namespace_user=namespace_user,
        search=spl,
        earliest_time=earliest_time,
        latest_time=latest_time,
        preview=bool(body.get("preview", True)),
        adhoc_search_level=body.get("adhoc_search_level", "verbose"),
        extra_params=body.get("extra_params") or None,
    )
    return created


# Run presets endpoints
# /api/splunk/presets/list/
# /api/splunk/presets/run/  (bounded polling like search/run)
# /api/splunk/presets/run_async/ (create job + sid)
@shared_task(bind=True)
def splunk_presets_list_task(self, body: dict):
    return {"result": list_presets()}


@shared_task(bind=True)
def splunk_presets_run_async_task(self, body: dict):
    body = body or {}
    preset = (body.get("preset") or "").strip()
    params = body.get("params") or {}
    namespace_user = (body.get("namespace_user") or "").strip()

    if not preset:
        return {"error": "missing_parameter", "detail": "preset is required"}
    if not namespace_user:
        return {"error": "missing_parameter", "detail": "namespace_user is required"}

    try:
        rendered = render_preset(preset, params)
    except Exception as e:
        return {"error": "invalid_preset", "detail": str(e)}

    defaults = rendered["defaults"]
    search = rendered["search"]

    runner = SplunkRunner(_user_key(body))
    driver = runner.get_driver()

    created = create_search_job(
        driver,
        namespace_user=namespace_user,
        search=search,
        earliest_time=body.get("earliest_time") or defaults.get("earliest_time", "-10m"),
        latest_time=body.get("latest_time") or defaults.get("latest_time", "now"),
        preview=bool(body.get("preview", True)),
        adhoc_search_level=body.get("adhoc_search_level", "verbose"),
        extra_params=body.get("extra_params") or None,
    )
    return {"preset": preset, "rendered": rendered, "created": created}


@shared_task(bind=True)
def splunk_presets_run_task(self, body: dict):
    """
    Preset run (sync): creates job + bounded poll + returns preview/events depending on defaults/overrides.
    """
    body = body or {}
    preset = (body.get("preset") or "").strip()
    params = body.get("params") or {}
    namespace_user = (body.get("namespace_user") or "").strip()

    if not preset:
        return {"error": "missing_parameter", "detail": "preset is required"}
    if not namespace_user:
        return {"error": "missing_parameter", "detail": "namespace_user is required"}

    try:
        rendered = render_preset(preset, params)
    except Exception as e:
        return {"error": "invalid_preset", "detail": str(e)}

    defaults = rendered["defaults"]
    search = rendered["search"]

    # defaults drive output selection unless overridden
    include_preview = bool(body.get("include_preview", defaults.get("include_preview", True)))
    include_events = bool(body.get("include_events", defaults.get("include_events", False)))

    max_polls = int(body.get("max_polls", getattr(settings, "SPLUNK_RUN_MAX_POLLS", 12)))
    poll_interval = float(
        body.get("poll_interval", getattr(settings, "SPLUNK_RUN_POLL_INTERVAL", 1.0))
    )

    runner = SplunkRunner(_user_key(body))
    driver = runner.get_driver()

    created = create_search_job(
        driver,
        namespace_user=namespace_user,
        search=search,
        earliest_time=body.get("earliest_time") or defaults.get("earliest_time", "-10m"),
        latest_time=body.get("latest_time") or defaults.get("latest_time", "now"),
        preview=bool(body.get("preview", True)),
        adhoc_search_level=body.get("adhoc_search_level", "verbose"),
        extra_params=body.get("extra_params") or None,
    )
    if created.get("error"):
        return created

    sid = created["sid"]

    status_namespace_user = body.get("status_namespace_user", "nobody")
    status_payload = None
    done = False
    for _ in range(max_polls):
        status_payload = get_job_status(driver, sid=sid, namespace_user=status_namespace_user)
        if status_payload.get("error"):
            return {"error": "status_failed", "sid": sid, "detail": status_payload}
        done = bool((status_payload.get("status") or {}).get("isDone"))
        if done:
            break
        time.sleep(poll_interval)

    results_namespace_user = body.get("results_namespace_user", "nobody")
    preview_out = None
    events_out = None

    if include_preview:
        preview_out = get_job_results_preview(
            driver,
            sid=sid,
            namespace_user=results_namespace_user,
            offset=int(body.get("preview_offset", defaults.get("preview_offset", 0))),
            count=int(body.get("preview_count", defaults.get("preview_count", 20))),
            show_metadata=bool(body.get("show_metadata", True)),
            add_summary_to_metadata=bool(body.get("add_summary_to_metadata", False)),
        )

    if include_events:
        events_out = get_job_events(
            driver,
            sid=sid,
            namespace_user=results_namespace_user,
            offset=int(body.get("events_offset", defaults.get("events_offset", 0))),
            count=int(body.get("events_count", defaults.get("events_count", 20))),
            max_lines=int(body.get("events_max_lines", defaults.get("events_max_lines", 5))),
            segmentation=body.get("segmentation", "full"),
            field_list=body.get("field_list"),
            truncation_mode=body.get("truncation_mode", "abstract"),
        )

    return {
        "ok": True,
        "preset": preset,
        "rendered": rendered,
        "sid": sid,
        "done": done,
        "status": status_payload,
        "preview": preview_out,
        "events": events_out,
    }


@shared_task(bind=True)
def splunk_alerts_list_task(self, body: dict):
    body = body or {}

    namespace_user = body.get("namespace_user", "nobody")

    runner = SplunkRunner((body or {}).get("user_key") or "localuser")
    driver = runner.get_driver()

    result = list_saved_searches(
        driver,
        namespace_user=namespace_user,
    )

    if result.get("error") == "unauthorized":
        return {
            "error": "login_required",
            "integration": "splunk",
            "detail": "Splunk SSO session expired.",
        }

    return result

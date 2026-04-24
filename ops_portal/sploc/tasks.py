from celery import shared_task
from sploc.runners.sploc_runner import SplocRunner
from core.browser import BrowserLoginRequired
from core.browser.registry import get_or_create_session

from sploc.services.trace_scraper import scrape_trace_waterfall
from sploc.services.ai_assistant import ask_ai_assistant
from sploc.url_builders import build_apm_url

from django.conf import settings


def _user_key(body: dict) -> str:
    return (body or {}).get("user_key") or "localuser"


@shared_task(bind=True)
def sploc_login_open_task(self, body: dict):
    """Open SignalFx login (headed browser) so user can complete SSO."""
    body = body or {}
    user_key = _user_key(body)
    runner = SplocRunner(user_key)

    try:
        return runner.open_login()
    except BrowserLoginRequired:
        session = get_or_create_session("sploc", user_key)
        return {
            "status": "login_opened",
            "integration": "sploc",
            "profile_dir": session.get("profile_dir"),
            "debug_port": session.get("debug_port"),
        }


@shared_task(bind=True)
def sploc_trace_scrape_task(self, body: dict):
    """
    Scrape trace waterfall spans from SignalFx.

    Required body params:
        trace_id: str
        service_name: str

    Optional:
        max_spans: int (0 = no limit)
    """
    body = body or {}
    trace_id = (body.get("trace_id") or "").strip()
    service_name = (body.get("service_name") or "").strip()

    if not trace_id:
        return {
            "error": "missing_parameter",
            "detail": "trace_id is required",
            "example": {"trace_id": "ec5b3fa0339376af5bb4930e02be596c"},
        }

    if not service_name:
        return {
            "error": "missing_parameter",
            "detail": "service_name is required",
            "example": {"service_name": "my-service"},
        }

    runner = SplocRunner(_user_key(body))
    driver = runner.get_driver()

    result = scrape_trace_waterfall(
        driver,
        trace_id=trace_id,
        service_name=service_name,
        max_spans=int(body.get("max_spans", 0)),
        scroll_step_factor=float(body.get(
            "scroll_step_factor",
            getattr(settings, 'SPLOC_SCROLL_STEP_FACTOR', 0.85),
        )),
        no_new_limit=int(body.get(
            "no_new_limit",
            getattr(settings, 'SPLOC_NO_NEW_LIMIT', 6),
        )),
    )

    return result


@shared_task(bind=True)
def sploc_ai_ask_task(self, body: dict):
    """
    Send a prompt to SignalFx's AI Assistant and return the response.

    Required body params:
        prompt: str

    Optional:
        navigate_url: str (defaults to APM page)
        use_page_filters: bool
        start_new_chat: bool
        close_panel_at_end: bool (default True)
    """
    body = body or {}
    prompt = (body.get("prompt") or "").strip()

    if not prompt:
        return {
            "error": "missing_parameter",
            "detail": "prompt is required",
            "example": {"prompt": "List error traces from the past 8 minutes."},
        }

    runner = SplocRunner(_user_key(body))
    driver = runner.get_driver()

    navigate_url = body.get("navigate_url", "")
    if not navigate_url and body.get("navigate_to_apm", True):
        navigate_url = build_apm_url()

    use_page_filters = body.get("use_page_filters")
    if isinstance(use_page_filters, str):
        use_page_filters = use_page_filters.lower() in ('true', '1', 'yes')

    result = ask_ai_assistant(
        driver,
        prompt=prompt,
        navigate_url=navigate_url,
        use_page_filters=use_page_filters,
        start_new_chat=bool(body.get("start_new_chat", False)),
        close_panel_at_end=bool(body.get("close_panel_at_end", True)),
        response_timeout=int(body.get(
            "response_timeout",
            getattr(settings, 'SPLOC_RESPONSE_TIMEOUT', 120),
        )),
        stable_window=float(body.get(
            "stable_window",
            getattr(settings, 'SPLOC_STABLE_WINDOW', 1.25),
        )),
    )

    return result

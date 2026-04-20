# splunk/runners/splunk_runner.py
from __future__ import annotations

from django.conf import settings

from core.runners.selenium_base import SeleniumRunner
from splunk.auth import splunk_auth_check


SPLUNK_BASE = getattr(
    settings,
    "SPLUNK_BASE",
    "https://your-splunk.splunkcloud.com",
).rstrip("/")


class SplunkRunner(SeleniumRunner):
    """
    Selenium runner for Splunk.

    - Inherits all Mode B behavior from SeleniumRunner:
    - Headed login once
    - Headless reuse
    - Safe relaunch if Edge was closed
    - Registry-backed profile + port

    This runner is responsible ONLY for:
    - Ensuring authenticated browser state
    - Opening login when required
    - Providing a driver for tasks
    """

    def __init__(self, user_key: str):
        super().__init__(
            integration="splunk",
            user_key=user_key or "localuser",
            origin_url=SPLUNK_BASE,
            auth_check=splunk_auth_check,
        )

    # ------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------
    def open_login(self):
        """
        Force headed browser open so user can complete Splunk SSO.

        Called by:
            POST /api/splunk/login/open/
        """
        # This intentionally raises BrowserLoginRequired
        # after opening a headed browser.
        self.ensure_browser(headless=False)

        # If we got here without exception, something is off,
        # but return a safe snapshot anyway.
        session = self._session_snapshot()
        return {
            "status": "login_opened",
            "integration": "splunk",
            "profile_dir": session["profile_dir"],
            "debug_port": session["debug_port"],
        }

    def get_driver(self):
        """
        Convenience wrapper used by Celery tasks.
        """
        return self.ensure_browser(headless=True)

    # ------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------
    def _session_snapshot(self):
        """
        Lightweight helper to read current registry state
        without mutating anything.
        """
        from core.browser.registry import get_or_create_session

        return get_or_create_session(self.integration, self.user_key)

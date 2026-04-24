from __future__ import annotations

from django.conf import settings

from core.runners.selenium_base import SeleniumRunner
from harness.auth import harness_auth_check


HARNESS_BASE = getattr(
    settings,
    "HARNESS_BASE",
    "https://xxx-prod.harness.io",
).rstrip("/")


class HarnessRunner(SeleniumRunner):
    """
    Selenium runner for Harness.

    Inherits all Mode behavior from SeleniumRunner:
    - Headed login once
    - Headless reuse
    - Safe relaunch if Edge was closed
    - Registry-backed profile + port
    """

    def __init__(self, user_key: str):
        super().__init__(
            integration="harness",
            user_key=user_key or "localuser",
            origin_url=HARNESS_BASE,
            auth_check=harness_auth_check,
        )

    # ============================================
    # Public API
    # ============================================

    def open_login(self):
        """
        Force headed browser open so user can complete SSO.

        Called by:
        POST /api/harness/login/open/
        """

        # This intentionally raises BrowserLoginRequired
        # after opening a headed browser.
        self.ensure_browser(headless=False)

        # If we got here without exception, something is wrong,
        # but return a safe payload anyway.
        session = self._session_snapshot()
        return {
            "status": "login_opened",
            "integration": "harness",
            "profile_dir": session["profile_dir"],
            "debug_port": session["debug_port"],
        }

    def get_driver(self):
        """
        Convenience wrapper used by tasks.
        """
        return self.ensure_browser(headless=False)

    # ============================================
    # Internal helpers
    # ============================================

    def _session_snapshot(self):
        """
        Lightweight helper to read current registry state
        without mutating anything.
        """
        from core.browser.registry import get_or_create_session

        return get_or_create_session(self.integration, self.user_key)
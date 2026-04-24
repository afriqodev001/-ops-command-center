from __future__ import annotations

from django.conf import settings

from core.runners.selenium_base import SeleniumRunner
from sploc.auth import sploc_auth_check


SPLOC_BASE = getattr(
    settings,
    "SPLOC_BASE",
    "https://your-org.signalfx.com",
).rstrip("/")


class SplocRunner(SeleniumRunner):
    """
    Selenium runner for SPLOC (Splunk Observability Cloud / SignalFx).

    Inherits Mode B behavior from SeleniumRunner:
    - Headed login once (SSO)
    - Headless reuse for automation tasks
    - Safe relaunch if Edge was closed
    - Registry-backed profile + port
    """

    def __init__(self, user_key: str):
        super().__init__(
            integration="sploc",
            user_key=user_key or "localuser",
            origin_url=SPLOC_BASE,
            auth_check=sploc_auth_check,
        )

    def open_login(self):
        """Force headed browser open so user can complete SignalFx SSO."""
        self.ensure_browser(headless=False)

        session = self._session_snapshot()
        return {
            "status": "login_opened",
            "integration": "sploc",
            "profile_dir": session["profile_dir"],
            "debug_port": session["debug_port"],
        }

    def get_driver(self):
        """Convenience wrapper used by Celery tasks."""
        return self.ensure_browser(headless=True)

    def _session_snapshot(self):
        from core.browser.registry import get_or_create_session
        return get_or_create_session(self.integration, self.user_key)

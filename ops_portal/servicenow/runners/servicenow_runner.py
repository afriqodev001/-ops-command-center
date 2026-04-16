from __future__ import annotations
from django.conf import settings

from core.runners.selenium_base import SeleniumRunner
from servicenow.auth import servicenow_auth_check

from servicenow.urls_builders import build_change_create_url
from servicenow.services.servicenow_change_create import open_standard_change_template


class ServiceNowRunner(SeleniumRunner):
    def __init__(self, user_key: str):
        super().__init__(
            integration="servicenow",
            user_key=(user_key or "localuser"),
            origin_url=getattr(settings, "SERVICENOW_BASE", "https://now.wf.com").rstrip("/"),
            auth_check=servicenow_auth_check,
        )

    def get_driver(self):
        return self.ensure_browser(headless=True)

    def open_login(self):
        # opens headed and raises BrowserLoginRequired as “success path”
        self.ensure_browser(headless=False)

    def open_change_create_ui(self, *, kind: str, template_key: str | None = None):
        """
        Opens the appropriate Change creation UI.
        """
        driver = self.ensure_browser(headless=False)

        if kind == "standard":
            return open_standard_change_template(driver, template_key=template_key)

        url = build_change_create_url(kind)
        driver.get(url)
        return {
            "status": "change_create_ui_opened",
            "kind": kind,
            "url": url,
        }

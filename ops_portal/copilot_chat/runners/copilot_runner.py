# copilot_chat/runners/copilot_runner.py

from django.conf import settings
from core.runners.selenium_base import SeleniumRunner


class CopilotRunner(SeleniumRunner):
    """
    Copilot browser session runner.

    Uses SeleniumRunner Mode-B behavior:
    - headed login once
    - headless reuse via same profile/port
    """

    def __init__(self, user_key: str):
        super().__init__(
            integration="copilot",  # reuse existing copilot band/profile isolation
            user_key=user_key or "localuser",
            origin_url=getattr(
                settings,
                "COPILOT_TEAMS_URL",
                "https://teams.microsoft.com/v2/",
            ),
            auth_check=None,  # Copilot DOM is iframe-heavy; validated elsewhere
        )

    def get_driver(self):
        return self.ensure_browser(headless=True)

    def open_login(self):
        # will open headed and raise BrowserLoginRequired as expected
        self.ensure_browser(headless=False)

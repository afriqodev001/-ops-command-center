import os
from django.conf import settings
from core.browser.registry import get_or_create_session

from copilot_chat.services.copilot_client import TeamsCopilotClient, CopilotConfig


def build_client_for_user(user_key: str) -> TeamsCopilotClient:
    """
    Build a TeamsCopilotClient bound to the user's Copilot browser session (debug port).
    We intentionally reuse your existing client implementation.
    """

    sess = get_or_create_session("copilot", user_key)

    cfg = CopilotConfig(
        debugger_addr=f"localhost:{sess['debug_port']}",
        teams_url=getattr(settings, "COPILOT_TEAMS_URL", "https://teams.microsoft.com/v2/"),
        open_teams_in_new_tab=True,
        response_max_wait_sec=int(getattr(settings, "COPILOT_RESPONSE_MAX_WAIT_SEC", 180)),
    )
    return TeamsCopilotClient(cfg)


def run_prompt(user_key: str, prompt: str) -> dict:
    """
    Run a single prompt and return structured result.
    """

    client = build_client_for_user(user_key)
    client.attach()
    client.ensure_ready()

    res = client.run_prompt(prompt)
    return {
        "prompt": res.prompt,
        "answer": res.answer,
        "status": res.status,
        "timestamp_utc": res.timestamp_utc,
        "guid": res.guid,
        "run_id": res.run_id,
        "error": res.error,
    }

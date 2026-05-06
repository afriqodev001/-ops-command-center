# harness/auth.py

from django.conf import settings

from harness.services.harness_fetch import browser_fetch
from harness.urls_builders import build_projects_aggregate


def harness_auth_check(driver, origin_url: str) -> bool:
    """
    Harness auth probe.

    Uses the account-scoped aggregate/projects endpoint so the probe answers
    "is the Harness session valid?" without also requiring the user's
    HARNESS_ORG_ID / HARNESS_PROJECT_ID to be set and accessible. The previous
    environmentsV2/listV2 probe was project-scoped and would return non-200
    (failing the probe) for any user whose configured project was empty,
    wrong, or unauthorized — even though their browser session was fine.

    IMPORTANT:
    - Must run from Harness origin so cookies apply.
    - HARNESS_ACCOUNT_ID is required; if missing, the probe fails fast.
    """
    try:
        if not getattr(settings, "HARNESS_ACCOUNT_ID", "").strip():
            return False

        if not (driver.current_url or "").startswith(origin_url):
            driver.get(origin_url)

        url = build_projects_aggregate(page_index=0, page_size=1)

        res = browser_fetch(
            driver,
            url=url,
            method="GET",
            body_obj=None,
        )

        return bool(res.get("ok") and res.get("status") == 200)

    except Exception:
        return False
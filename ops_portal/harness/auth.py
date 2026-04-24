# harness/auth.py

from harness.services.harness_fetch import browser_fetch
from harness.urls_builders import build_env_list


def harness_auth_check(driver, origin_url: str) -> bool:
    """
    Harness auth probe.

    IMPORTANT:
    - Must run from Harness origin so cookies apply
    - Uses environmentsV2/listV2 as the auth signal
    """
    try:
        # ✅ ENSURE correct origin FIRST
        if not (driver.current_url or "").startswith(origin_url):
            driver.get(origin_url)

        env_url, env_body = build_env_list()

        res = browser_fetch(
            driver,
            url=env_url,
            method="POST",
            body_obj=env_body,
        )

        return bool(res.get("ok") and res.get("status") == 200)

    except Exception:
        return False
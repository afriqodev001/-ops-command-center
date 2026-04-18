def tachyon_auth_check(driver, origin: str) -> bool:
    """
    Auth check for Tachyon Studio (SPA).

    IMPORTANT:
    - Do NOT call driver.get() here
    - Browser is already on the correct origin
    - Reloading can invalidate an otherwise valid session
    """
    try:
        url = (driver.current_url or "").lower()

        # If we are clearly on an auth / login / sso page, fail
        if "login" in url or "sso" in url or "authenticate" in url:
            return False

        # Basic DOM sanity: SPA has mounted
        return bool(
            driver.execute_script(
                "return document.readyState === 'complete' && "
                "document.body && document.body.innerText.length > 0"
            )
        )
    except Exception:
        return False
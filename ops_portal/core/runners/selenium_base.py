# core/runners/selenium_base.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from core.browser import (
    BrowserLoginRequired,
    BrowserStartupFailed,
    get_or_create_session,
    update_runtime_info,
    touch_session,
    is_debug_alive,
    launch_edge,
    attach_to_edge,
)
from .base import BaseRunner

# Signature: auth_check(driver, origin_url) -> bool
AuthCheckFn = Callable[[Any, str], bool]


@dataclass
class SeleniumRunner(BaseRunner):
    """
    Shared Selenium runner base (core).

    Mode B behavior:
    - Login MUST be headed at least once
    - If profile exists but Edge is closed:
      - headless=True  -> relaunch Edge headless with same profile
      - headless=False -> relaunch Edge headed (user logs in)
    - Background tasks NEVER pop UI
    """

    origin_url: str = ""
    auth_check: Optional[AuthCheckFn] = field(default=None, compare=False)

    def ensure_browser(self, *, headless: bool = True):
        """
        Ensure an Edge session exists and return an attached Selenium WebDriver.
        """
        user_key = (self.user_key or "").strip() or "localuser"

        session = get_or_create_session(self.integration, user_key)
        profile_dir = session["profile_dir"]
        debug_port = session["debug_port"]

        # ----------------------------------------------------
        # STEP 1: Ensure Edge is running (Mode B)
        # ----------------------------------------------------
        if not is_debug_alive(debug_port):
            result = launch_edge(
                profile_dir=profile_dir,
                debug_port=debug_port,
                url=self.origin_url,
                headless=headless,
            )

            update_runtime_info(
                self.integration,
                user_key,
                pid=result.get("pid"),
                mode=result.get("status"),
                origin=self.origin_url,
            )

            if result.get("status") == "failed":
                raise BrowserStartupFailed(
                    f"Failed to start Edge browser for {self.integration}."
                )

            # If we launched headed, user must authenticate
            if not headless:
                raise BrowserLoginRequired(
                    "Login required; headed browser opened for authentication."
                )

        # ----------------------------------------------------
        # STEP 2: Attach Selenium to Edge
        # ----------------------------------------------------
        try:
            driver = attach_to_edge(debug_port)
        except Exception as e:
            raise BrowserStartupFailed(
                f"Failed to attach to Edge on port {debug_port}: {e}"
            )

        # ----------------------------------------------------
        # STEP 3: Ensure correct origin is loaded
        # ----------------------------------------------------
        try:
            cur = driver.current_url or ""
        except Exception:
            cur = ""

        if self.origin_url and not cur.startswith(self.origin_url):
            driver.get(self.origin_url)

        # ----------------------------------------------------
        # STEP 4: Auth check (ONLY reason to block)
        # ----------------------------------------------------
        if self.auth_check is not None:
            try:
                ok = bool(self.auth_check(driver, self.origin_url))
            except Exception as e:
                raise BrowserStartupFailed(
                    f"Auth check raised an exception: {e}"
                )

            if not ok:
                raise BrowserLoginRequired(
                    f"Login required; call /api/{self.integration}/login/open/ to authenticate."
                )

        # ----------------------------------------------------
        # STEP 5: Touch session for idle cleanup
        # ----------------------------------------------------
        touch_session(self.integration, user_key)

        return driver

    def run(self, **kwargs) -> Dict[str, Any]:
        """
        Concrete integrations override this method.
        """
        raise NotImplementedError("SeleniumRunner child must implement run().")

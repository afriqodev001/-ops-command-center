# tachyon/runners/tachyon_runner.py
from __future__ import annotations

from django.conf import settings
from selenium.webdriver.support.ui import WebDriverWait

from core.runners.selenium_base import SeleniumRunner
from tachyon.auth import tachyon_auth_check
from tachyon.services.tachyon_fetch import run_llm, get_file_count
from tachyon.services.tachyon_upload import (
    upload_file,
    extract_ids_from_upload_response,
)


TACHYON_BASE = getattr(settings, "TACHYON_BASE", "https://your-tachyon-instance.net")


class TachyonRunner(SeleniumRunner):
    def __init__(self, user_key: str):
        super().__init__(
            integration="tachyon",
            user_key=user_key,
            origin_url=TACHYON_BASE,
            auth_check=tachyon_auth_check,
        )

    # ------------------------------------------------------------
    # 🔐 Ensure Tachyon origin is loaded
    # ------------------------------------------------------------
    def _ensure_tachyon_origin_loaded(self, driver) -> None:
        try:
            cur = driver.current_url or ""
        except Exception:
            cur = ""

        if not cur.startswith(TACHYON_BASE):
            driver.get(TACHYON_BASE)

    # ------------------------------------------------------------
    # ✅ CRITICAL: wait for Playground SPA to bootstrap
    # ------------------------------------------------------------
    def _wait_playground_ready(self, driver, timeout: int = 30) -> None:
        """
        Wait until Tachyon Playground SPA is fully initialized.
        Mirrors wait_dom_ready() from the working standalone script.
        """
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script(
                "return document.readyState === 'complete' && "
                "document.body && document.body.innerText.length > 0"
            )
        )

    # ------------------------------------------------------------
    # Public APIs
    # ------------------------------------------------------------
    def file_count(self, user_id: str) -> dict:
        driver = self.ensure_browser(headless=True)

        try:
            driver.set_script_timeout(
                int(getattr(settings, "TACHYON_SCRIPT_TIMEOUT_SECONDS", 90))
            )
        except Exception:
            pass

        self._ensure_tachyon_origin_loaded(driver)
        self._wait_playground_ready(driver)

        return get_file_count(driver, user_id)

    def llm(
        self,
        body: dict,
        wf_client_id: str = "mlops",
        wf_api_key: str = "",
    ) -> dict:
        driver = self.ensure_browser(headless=True)

        try:
            driver.set_script_timeout(
                int(getattr(settings, "TACHYON_SCRIPT_TIMEOUT_SECONDS", 90))
            )
        except Exception:
            pass

        # ✅ Match working script behavior
        self._ensure_tachyon_origin_loaded(driver)
        self._wait_playground_ready(driver)

        return run_llm(
            driver,
            body=body,
            wf_client_id=wf_client_id,
            wf_api_key=wf_api_key,
        )

    def upload_and_llm(
        self,
        *,
        body: dict,
        file_path: str,
        folder_name: str,
        folder_id=None,
        wf_client_id: str = "mlops",
        wf_api_key: str = "",
    ) -> dict:
        driver = self.ensure_browser(headless=True)

        try:
            driver.set_script_timeout(
                int(getattr(settings, "TACHYON_SCRIPT_TIMEOUT_SECONDS", 90))
            )
        except Exception:
            pass

        # ✅ Match working script behavior
        self._ensure_tachyon_origin_loaded(driver)
        self._wait_playground_ready(driver)

        up = upload_file(
            driver,
            user_id=body["userId"],
            preset_id=body["presetId"],
            local_file_path=file_path,
            folder_name=folder_name,
            folder_id=folder_id,
        )

        folder_id2, file_id2, info_obj = extract_ids_from_upload_response(
            up.get("data")
        )

        if not folder_id2 and folder_id:
            folder_id2 = folder_id

        if not folder_id2 or not file_id2:
            raise RuntimeError(
                f"Could not extract folderId/fileId from upload response: {up}"
            )

        body["folderIdList"] = [folder_id2]
        body["fileIdList"] = [file_id2]

        return run_llm(
            driver,
            body=body,
            wf_client_id=wf_client_id,
            wf_api_key=wf_api_key,
        )
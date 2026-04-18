# copilot_chat/services/copilot_attachments.py

import os
import time
from typing import List

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# DOM selectors (from your script)
FILE_INPUT_ID = "upload-file-button"
ATTACHMENT_ITEM_SELECTOR = ".fai-Attachment"
ATTACHMENT_REMOVE_BUTTON_SELECTOR = "button[aria-label^='Remove attachment']"


def remove_all_attachments(driver, wait_sec: int = 30):
    """
    Click "Remove attachment" buttons until none remain.
    """
    end = time.time() + wait_sec

    while time.time() < end:
        buttons = driver.find_elements(By.CSS_SELECTOR, ATTACHMENT_REMOVE_BUTTON_SELECTOR)
        if not buttons:
            return

        for b in buttons:
            try:
                b.click()
                time.sleep(0.1)
            except Exception:
                pass

        time.sleep(0.2)


def wait_for_uploads_complete(driver, file_paths: List[str], timeout: int = 180):
    """
    Wait until each uploaded filename appears as finished.
    """
    end = time.time() + timeout
    base_names = [os.path.basename(p).lower() for p in file_paths]

    script = r"""
    const names = arguments[0];
    const sel = arguments[1];

    function norm(s){
        if(!s) return "";
        return s.replace(/\u00A0/g," ").replace(/\s+/g," ").trim().toLowerCase();
    }

    const items = Array.from(document.querySelectorAll(sel));
    const statusByName = {};

    for (const it of items) {
        const txt = norm(it.innerText);
        for (const n of names) {
            if (n && txt.includes(n)) statusByName[n] = txt;
        }
    }

    const out = {done:true, missing:[], incomplete:[], failed:[]};

    for (const n of names) {
        const st = statusByName[n];
        if (!st) {
            out.done = false;
            out.missing.push(n);
            continue;
        }
        if (st.includes("upload failed") || st.includes("failed")) {
            out.done = false;
            out.failed.push(n);
            continue;
        }
        if (!st.includes("upload finished") && !st.includes("finished")) {
            out.done = false;
            out.incomplete.push(n);
        }
    }

    return out;
    """

    last = None
    while time.time() < end:
        last = driver.execute_script(script, base_names, ATTACHMENT_ITEM_SELECTOR)
        if last and last.get("done"):
            return
        time.sleep(0.4)

    raise TimeoutException(f"Upload did not finish: {last}")


def attach_files(driver, file_paths: List[str]) -> List[str]:
    """
    Attach local files using the hidden <input type=file id=upload-file-button>.
    """
    if not file_paths:
        return []

    file_input = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.ID, FILE_INPUT_ID))
    )

    # Make visible (prevents ElementNotInteractable in some builds)
    driver.execute_script(
        """
        arguments[0].style.display='block';
        arguments[0].style.visibility='visible';
        arguments[0].style.height='1px';
        arguments[0].style.width='1px';
        arguments[0].style.opacity=0;
        """,
        file_input,
    )

    payload = "\n".join(file_paths)
    file_input.send_keys(payload)

    wait_for_uploads_complete(driver, file_paths, timeout=180)
    return file_paths
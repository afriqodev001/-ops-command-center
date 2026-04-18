# copilot_chat/services/copilot_client.py
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple, Callable, Dict, Any

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException


# -----------------------------
# Data structures (lean)
# -----------------------------
@dataclass
class CopilotRunResult:
    prompt: str
    answer: str
    timestamp_utc: str
    guid: Optional[str] = None
    status: str = "ok"  # ok | timeout | error
    error: Optional[str] = None
    run_id: Optional[str] = None
    answer_copy_text: Optional[str] = None
    answer_copy_html: Optional[str] = None


@dataclass
class CopilotConfig:
    """
    Lean config for Django-based Copilot automation.

    This is distilled from your larger copilot_client.py:
    - attach to Edge debuggerAddress
    - navigate Teams
    - locate Copilot left rail + iframe
    - send prompt + capture answer robustly
    """

    debugger_addr: str = "localhost:9444"
    teams_url: str = "https://teams.microsoft.com/v2/"
    open_teams_in_new_tab: bool = True

    wait_timeout_sec: int = 30
    copilot_load_timeout_sec: int = 60

    response_max_wait_sec: int = 180
    response_stable_seconds: float = 1.5

    # Input + send
    input_selector: str = "#m365-chat-editor-target-element"
    send_button_selectors: Tuple[str, ...] = (
        "button[aria-label='Send']",
        "button[type='submit'][aria-label='Send']",
    )

    # Copilot left rail (multiple candidates)
    copilot_left_rail_selectors: Tuple[str, ...] = (
        "div[data-testid='list-item-metaos-copilot']",
        "div[data-inp='slice-switch-copilot']",
        "div[data-fui-tree-item-value^='OneGQL_BizChatMetaOSConversation|']",
    )

    # iframe discovery
    copilot_iframe_prefix_selector: str = "iframe[id^='cacheable-iframe:']"

    # message extraction
    turn_selector: str = "div[data-testid='m365-chat-llm-web-ui-chat-message']"
    answer_text_selector: str = "div[data-testid='copilot-message-div'] div[data-testid='markdown-reply']"
    busy_selector: str = "div.fai-CopilotMessage[aria-busy='true'], [aria-busy='true']"

    # Copy button (preferred capture path)
    copy_button_selector: str = "button[data-testid='CopyButtonTestId']"

    # Prefer JS injection (more reliable in background/headless)
    prefer_js_input: bool = True


# -----------------------------
# Client (lean)
# -----------------------------
class TeamsCopilotClient:
    """
    Lean Teams Copilot automation client for Django tasks.

    Key capabilities reused from your existing copilot_client.py:
    - attach() to Edge debuggerAddress
    - ensure_ready(): Teams open -> click left rail -> switch iframe
    - run_prompt(): anchored response capture + copy hook
    """

    GUID_RE = re.compile(r"OneGQL_BizChatMetaOSConversation\|([0-9a-fA-F-]{36})")

    def __init__(self, config: CopilotConfig, logger: Optional[Callable[[str], None]] = None):
        self.cfg = config
        self._driver: Optional[webdriver.Edge] = None
        self._logger = logger
        self._last_guid: Optional[str] = None

    # ---- logging
    def _log(self, msg: str):
        if self._logger:
            self._logger(msg)
        else:
            # keep it quiet by default; callers can pass a logger
            pass

    # ---- lifecycle
    def attach(self) -> webdriver.Edge:
        if self._driver:
            return self._driver
        options = webdriver.EdgeOptions()
        options.add_experimental_option("debuggerAddress", self.cfg.debugger_addr)
        self._driver = webdriver.Edge(options=options)
        self._driver.set_script_timeout(self.cfg.response_max_wait_sec + 30)
        self._driver.set_page_load_timeout(120)
        return self._driver

    @property
    def driver(self) -> webdriver.Edge:
        return self._driver or self.attach()

    # ---- utility
    def wait_dom_ready(self, timeout: Optional[int] = None) -> None:
        t = timeout or self.cfg.wait_timeout_sec
        WebDriverWait(self.driver, t).until(
            lambda d: d.execute_script("return document.readyState") in ("interactive", "complete")
        )

    def safe_find(self, css: str) -> bool:
        try:
            return len(self.driver.find_elements(By.CSS_SELECTOR, css)) > 0
        except Exception:
            return False

    # ---- navigation
    def ensure_teams_open(self) -> None:
        cur = ""
        try:
            cur = self.driver.current_url or ""
        except Exception:
            pass

        if "teams.microsoft.com" in cur:
            return

        if self.cfg.open_teams_in_new_tab:
            before = self.driver.window_handles[:]
            self.driver.execute_script("window.open(arguments[0], '_blank');", self.cfg.teams_url)

            end = time.time() + 10
            while time.time() < end:
                now = self.driver.window_handles
                new_list = [h for h in now if h not in before]
                if new_list:
                    self.driver.switch_to.window(new_list[-1])
                    break
                time.sleep(0.25)
        else:
            self.driver.get(self.cfg.teams_url)

        self.wait_dom_ready()

    # ---- Copilot left rail + GUID
    def _get_copilot_guid_from_dom(self) -> Optional[str]:
        self.driver.switch_to.default_content()
        for sel in self.cfg.copilot_left_rail_selectors:
            try:
                val = self.driver.execute_script(
                    "const el=document.querySelector(arguments[0]);"
                    "return el?el.getAttribute('data-fui-tree-item-value'):null;",
                    sel,
                )
                if not val:
                    continue
                m = self.GUID_RE.search(val)
                if m:
                    return m.group(1)
            except Exception:
                continue
        return None

    def click_copilot_left_rail(self) -> Optional[str]:
        guid = self._get_copilot_guid_from_dom()
        self.driver.switch_to.default_content()
        self.wait_dom_ready()

        last_err = None
        for sel in self.cfg.copilot_left_rail_selectors:
            try:
                el = WebDriverWait(self.driver, self.cfg.wait_timeout_sec).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                )
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                    time.sleep(0.05)
                except Exception:
                    pass
                el.click()
                self._last_guid = guid
                return guid
            except Exception as e:
                last_err = e
                continue

        raise TimeoutException(f"Could not click Copilot in left rail. Last error: {last_err}")

    # ---- iframe switching
    def _switch_to_iframe_and_check_input(self, iframe_el) -> bool:
        try:
            self.driver.switch_to.default_content()
            self.driver.switch_to.frame(iframe_el)
        except Exception:
            return False

        if self.safe_find(self.cfg.input_selector):
            return True

        # nested iframe scan
        try:
            inner = self.driver.find_elements(By.TAG_NAME, "iframe")
            for fr in inner:
                try:
                    self.driver.switch_to.frame(fr)
                    if self.safe_find(self.cfg.input_selector):
                        return True
                    self.driver.switch_to.parent_frame()
                except Exception:
                    try:
                        self.driver.switch_to.parent_frame()
                    except Exception:
                        pass
                    continue
        except Exception:
            pass

        return False

    def switch_to_copilot_context(self, guid: Optional[str]) -> None:
        end = time.time() + self.cfg.copilot_load_timeout_sec
        expected_iframe_id = f"cacheable-iframe:{guid}" if guid else None

        while time.time() < end:
            self.driver.switch_to.default_content()

            # already in correct context?
            if self.safe_find(self.cfg.input_selector):
                return

            # try expected iframe by ID
            if expected_iframe_id:
                try:
                    iframe = self.driver.find_element(By.ID, expected_iframe_id)
                    if self._switch_to_iframe_and_check_input(iframe):
                        return
                except Exception:
                    pass

            # cacheable scan
            try:
                cacheables = self.driver.find_elements(By.CSS_SELECTOR, self.cfg.copilot_iframe_prefix_selector)
                for fr in cacheables:
                    if self._switch_to_iframe_and_check_input(fr):
                        return
            except Exception:
                pass

            # full scan fallback
            try:
                all_iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                for fr in all_iframes:
                    if self._switch_to_iframe_and_check_input(fr):
                        return
            except Exception:
                pass

            time.sleep(0.5)

        raise TimeoutException("Copilot chat input not found after waiting/polling.")

    def ensure_ready(self) -> Optional[str]:
        self.ensure_teams_open()
        guid = self.click_copilot_left_rail()
        self.switch_to_copilot_context(guid)
        WebDriverWait(self.driver, self.cfg.wait_timeout_sec).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, self.cfg.input_selector))
        )
        return guid

    # ----------------------------------------------------------
    # Prompt send + response capture (anchored)
    # ----------------------------------------------------------
    def _get_turn_count(self) -> int:
        try:
            return int(self.driver.execute_script(
                "return document.querySelectorAll(arguments[0]).length;",
                self.cfg.turn_selector,
            ) or 0)
        except Exception:
            return 0

    def _get_latest_answer_text_since(self, start_index: int) -> str:
        script = r"""
        function norm(s){
            if(!s) return "";
            return s.replace(/\u00A0/g," ")
                    .replace(/[ \t]+\n/g,"\n")
                    .replace(/\n{3,}/g,"\n\n")
                    .replace(/[ \t]{2,}/g," ")
                    .trim();
        }
        const TURN_SEL = arguments[0];
        const A_SEL = arguments[1];
        const startIndex = arguments[2];
        const turns = Array.from(document.querySelectorAll(TURN_SEL));
        if (!turns.length) return "";

        for (let i = turns.length - 1; i >= startIndex; i--) {
            const t = turns[i];
            const lastChat = t.querySelector("div[data-testid='lastChatMessage']");
            const aEl = (lastChat && lastChat.querySelector("div[data-testid='markdown-reply']"))
                        || t.querySelector(A_SEL);
            const txt = aEl ? norm(aEl.innerText) : "";
            if (txt) return txt;
        }
        return "";
        """
        try:
            return self.driver.execute_script(
                script,
                self.cfg.turn_selector,
                self.cfg.answer_text_selector,
                int(start_index),
            ) or ""
        except Exception:
            return ""

    def is_generating(self) -> bool:
        try:
            cnt = self.driver.execute_script(
                "return document.querySelectorAll(arguments[0]).length;",
                self.cfg.busy_selector,
            )
            return bool(cnt and cnt > 0)
        except Exception:
            return False

    def _set_editor_text_js(self, text: str) -> bool:
        try:
            input_el = WebDriverWait(self.driver, self.cfg.wait_timeout_sec).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.cfg.input_selector))
            )
            script = r"""
            const el = arguments[0];
            const text = arguments[1];
            try { el.scrollIntoView({block:'center'}); } catch(e) {}
            try { el.focus(); } catch(e) {}
            el.textContent = text;
            try {
                el.dispatchEvent(new InputEvent('input', {bubbles:true, data:text, inputType:'insertText'}));
            } catch(e) {
                el.dispatchEvent(new Event('input', {bubbles:true}));
            }
            el.dispatchEvent(new Event('change', {bubbles:true}));
            try {
                const range = document.createRange();
                range.selectNodeContents(el);
                range.collapse(false);
                const sel = window.getSelection();
                sel.removeAllRanges();
                sel.addRange(range);
            } catch(e) {}
            return true;
            """
            self.driver.execute_script(script, input_el, text or "")
            return True
        except Exception:
            return False

    def _set_editor_text_sendkeys(self, text: str) -> None:
        input_el = WebDriverWait(self.driver, self.cfg.wait_timeout_sec).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, self.cfg.input_selector))
        )
        input_el.click()
        time.sleep(0.05)
        input_el.send_keys(Keys.CONTROL, "a")
        time.sleep(0.02)
        input_el.send_keys(Keys.BACKSPACE)
        time.sleep(0.05)

        lines = (text or "").splitlines()
        for i, line in enumerate(lines):
            if line:
                input_el.send_keys(line)
            if i < len(lines) - 1:
                input_el.send_keys(Keys.SHIFT, Keys.ENTER)
                time.sleep(0.02)

    def _set_editor_text(self, text: str) -> None:
        if self.cfg.prefer_js_input and self._set_editor_text_js(text):
            return
        self._set_editor_text_sendkeys(text)

    def _try_click_send(self) -> bool:
        for sel in self.cfg.send_button_selectors:
            try:
                btn = self.driver.find_element(By.CSS_SELECTOR, sel)
                aria_disabled = (btn.get_attribute("aria-disabled") or "").lower()
                disabled_attr = btn.get_attribute("disabled")
                if disabled_attr or aria_disabled == "true":
                    continue
                btn.click()
                return True
            except Exception:
                continue
        return False

    def send_prompt(self, prompt: str) -> None:
        self._set_editor_text(prompt)
        if not self._try_click_send():
            raise TimeoutException("Send button not clickable (cannot safely submit).")

    # ---- clipboard capture (preferred)
    def ensure_clipboard_hook(self) -> None:
        hook_js = r"""
        (function () {
            if (window.__copilotClipboardHookInstalled) return true;
            window.__copilotLastCopied = { text: "", html: "", ts: 0, method: "" };
            function setLast(text, html, method) {
                window.__copilotLastCopied = { text: text||"", html: html||"", ts: Date.now(), method: method||"" };
            }
            if (navigator.clipboard && navigator.clipboard.writeText) {
                const _writeText = navigator.clipboard.writeText.bind(navigator.clipboard);
                navigator.clipboard.writeText = async function (text) {
                    setLast(text, "", "writeText");
                    return _writeText(text);
                };
            }
            if (navigator.clipboard && navigator.clipboard.write) {
                const _write = navigator.clipboard.write.bind(navigator.clipboard);
                navigator.clipboard.write = async function (items) {
                    try {
                        let plain = "", html = "";
                        if (items && items.length) {
                            const it = items[0];
                            if (it.types && it.types.includes("text/plain")) {
                                const blob = await it.getType("text/plain");
                                plain = await blob.text();
                            }
                            if (it.types && it.types.includes("text/html")) {
                                const blob = await it.getType("text/html");
                                html = await blob.text();
                            }
                        }
                        setLast(plain, html, "write");
                    } catch (e) {}
                    return _write(items);
                };
            }
            window.__copilotClipboardHookInstalled = true;
            return true;
        })();
        """
        self.driver.execute_script(hook_js)

    def get_last_copied(self) -> Dict[str, Any]:
        js = r"""
        const d = window.__copilotLastCopied;
        if (!d || !d.ts) return {text:"", html:"", ok:false, ts:0};
        return {text:d.text||"", html:d.html||"", ok:true, ts:d.ts||0};
        """
        out = self.driver.execute_script(js)
        return out or {"text": "", "html": "", "ok": False, "ts": 0}

    def wait_for_copy_capture(self, min_ts: int, timeout_sec: float = 6.0) -> Dict[str, Any]:
        start = time.time()
        while time.time() - start < timeout_sec:
            d = self.get_last_copied()
            if d.get("ok") and int(d.get("ts") or 0) > int(min_ts):
                if d.get("text") or d.get("html"):
                    return d
            time.sleep(0.15)
        return self.get_last_copied()

    def click_copy_for_new_turns(self, start_index: int) -> bool:
        js = r"""
        const TURN_SEL = arguments[0];
        const COPY_SEL = arguments[1];
        const startIndex = arguments[2];
        const turns = Array.from(document.querySelectorAll(TURN_SEL));
        if (!turns.length) return false;
        for (let i = turns.length - 1; i >= startIndex; i--) {
            const btn = turns[i].querySelector(COPY_SEL);
            if (btn) { btn.click(); return true; }
        }
        return false;
        """
        try:
            return bool(self.driver.execute_script(
                js,
                self.cfg.turn_selector,
                self.cfg.copy_button_selector,
                int(start_index),
            ))
        except Exception:
            return False

    def wait_for_response_done(self, start_index: int) -> str:
        start = time.time()
        last_text = ""
        last_change = time.time()

        # wait for some new answer text in new turns
        while time.time() - start < self.cfg.response_max_wait_sec:
            txt = self._get_latest_answer_text_since(start_index)
            if txt:
                last_text = txt
                last_change = time.time()
                break
            time.sleep(0.5)

        # wait for stability + not generating
        while time.time() - start < self.cfg.response_max_wait_sec:
            txt = self._get_latest_answer_text_since(start_index)
            if txt != last_text:
                last_text = txt
                last_change = time.time()

            if (not self.is_generating()) and ((time.time() - last_change) >= self.cfg.response_stable_seconds) and last_text:
                return last_text

            if ((time.time() - last_change) >= max(self.cfg.response_stable_seconds * 2, 3.0)) and last_text:
                return last_text

            time.sleep(0.6)

        return last_text.strip()

    # ---- public API
    def run_prompt(self, prompt: str) -> CopilotRunResult:
        run_id = str(uuid.uuid4())
        prompt_to_send = (prompt or "").rstrip() + f"\n\n<!-- RUN_ID:{run_id} -->"

        guid = None
        try:
            # ensure we are in correct iframe context
            guid = self._last_guid or self.ensure_ready()  # stays in iframe
            turns_before = self._get_turn_count()
            self.send_prompt(prompt_to_send)

            
            _ = self.wait_for_response_done(start_index=turns_before)

            # prefer clipboard capture via Copy button
            self.ensure_clipboard_hook()
            before = self.get_last_copied()
            before_ts = int(before.get("ts") or 0)

            clicked = self.click_copy_for_new_turns(start_index=turns_before)
            copied = (
                self.wait_for_copy_capture(min_ts=before_ts)
                if clicked
                else {"text": "", "html": "", "ok": False, "ts": 0}
            )

            copy_text = (copied.get("text") or "").strip()
            copy_html = (copied.get("html") or "").strip()

            # fallback to DOM text if copy hook fails
            answer = copy_text or self._get_latest_answer_text_since(turns_before) or ""

            return CopilotRunResult(
                prompt=prompt.strip(),
                answer=answer.strip(),
                answer_copy_text=copy_text or None,
                answer_copy_html=copy_html or None,
                timestamp_utc=datetime.utcnow().isoformat(),
                guid=guid,
                status="ok",
                run_id=run_id,
            )

        except StaleElementReferenceException:
            # one retry: re-enter context
            try:
                self.ensure_ready()
                return self.run_prompt(prompt)
            except Exception as e:
                return CopilotRunResult(
                    prompt=prompt,
                    answer="",
                    timestamp_utc=datetime.utcnow().isoformat(),
                    guid=guid,
                    status="error",
                    error=str(e),
                    run_id=run_id,
                )

        except TimeoutException as te:
            return CopilotRunResult(
                prompt=prompt,
                answer="",
                timestamp_utc=datetime.utcnow().isoformat(),
                guid=guid,
                status="timeout",
                error=str(te),
                run_id=run_id,
            )

        except Exception as e:
            return CopilotRunResult(
                prompt=prompt,
                answer="",
                timestamp_utc=datetime.utcnow().isoformat(),
                guid=guid,
                status="error",
                error=str(e),
                run_id=run_id,
            )
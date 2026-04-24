"""
SPLOC AI Assistant — interacts with SignalFx's AI side panel.

Accepts a Selenium WebDriver (managed by SplocRunner) and returns AI responses.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, Any, Optional

from django.conf import settings


# ─── Selectors ──────────────────────────────────────────────
AI_BTN = 'button[data-test="ai-assistant-btn"]'
AI_PANEL = 'div[data-test="side-panel"][role="dialog"]'

TEXTBOX = 'div[data-test="side-panel"] textarea[data-test="textbox"]'
SEND_BTN = 'div[data-test="side-panel"] button[data-test="ai-chat-input-submit-button"]'

RESP_MSGS = 'div[data-test="side-panel"] div[data-test="response"]'
RESP_MD_SEL = 'div[data-test="markdown"]'
COPY_BTN_SEL = 'button[data-test="message-action-button-Copy"]'

PAGE_FILTERS_TOGGLE = 'div[data-test="ai-current-page-filters"] button[data-test="toggle"][role="switch"]'

NEW_CHAT_BTN = 'div[data-test="side-panel"] button[data-test="ai-assistant-new-chat"]'
NEW_CHAT_MODAL = 'div[data-test="ai-assistant-new-chat-confirmation-modal"]'
NEW_CHAT_PROCEED_BTN = 'button[data-test="ai-assistant-new-chat-confirmation-modal-proceed-btn"]'
NEW_CHAT_CANCEL = 'button[data-test="ai-assistant-new-chat-confirmation-modal-cancel-btn"]'

CLOSE_PANEL_BTN = 'div[data-test="side-panel"] button[data-test="ai-assistant-close"]'


def _sploc_base():
    return getattr(settings, 'SPLOC_BASE', 'https://your-org.signalfx.com').rstrip('/')


def _wait_until(driver, predicate_js: str, timeout=30, poll=0.25) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if driver.execute_script(predicate_js):
            return True
        time.sleep(poll)
    return False


# ─── Panel Control ──────────────────────────────────────────
def _ensure_ai_panel_open(driver):
    already_open = driver.execute_script(f"return !!document.querySelector('{AI_PANEL}');")
    if already_open:
        return

    ok = _wait_until(driver, f"return !!document.querySelector('{AI_BTN}');")
    if not ok:
        raise RuntimeError("AI Assistant button not found")

    driver.execute_script(f"document.querySelector('{AI_BTN}').click();")

    opened = _wait_until(driver, f"return !!document.querySelector('{AI_PANEL}');")
    if not opened:
        raise RuntimeError("AI panel did not open")


def _ensure_page_filters_state(driver, desired: Optional[bool]):
    if desired is None:
        return

    current = driver.execute_script("""
        const b = document.querySelector(arguments[0]);
        if (!b) return null;
        const v = (b.getAttribute('aria-checked') || '').toLowerCase();
        if (v === 'true') return true;
        if (v === 'false') return false;
        return null;
    """, PAGE_FILTERS_TOGGLE)

    if current is None or current == desired:
        return

    driver.execute_script(f"document.querySelector('{PAGE_FILTERS_TOGGLE}').click();")


def _maybe_start_new_chat(driver, enabled: bool, proceed: bool = True):
    if not enabled:
        return

    ok = _wait_until(driver, f"return !!document.querySelector('{NEW_CHAT_BTN}');")
    if not ok:
        return

    driver.execute_script(f"document.querySelector('{NEW_CHAT_BTN}').click();")

    modal_ok = _wait_until(driver, f"return !!document.querySelector('{NEW_CHAT_MODAL}');")
    if not modal_ok:
        return

    if proceed:
        driver.execute_script(f"document.querySelector('{NEW_CHAT_PROCEED_BTN}').click();")
    else:
        driver.execute_script(f"document.querySelector('{NEW_CHAT_CANCEL}').click();")

    _wait_until(driver, f"return !document.querySelector('{NEW_CHAT_MODAL}');")
    time.sleep(0.35)


# ─── Input ──────────────────────────────────────────────────
def _set_textarea_value(driver, css_selector: str, value: str):
    ok = _wait_until(driver, f"return !!document.querySelector('{css_selector}');")
    if not ok:
        raise RuntimeError("Textbox not found")

    driver.execute_script("""
        const sel = arguments[0];
        const val = arguments[1];
        const ta = document.querySelector(sel);
        if (!ta) return;

        const setter = Object.getOwnPropertyDescriptor(
            window.HTMLTextAreaElement.prototype, 'value'
        ).set;

        setter.call(ta, '');
        ta.dispatchEvent(new Event('input', { bubbles: true }));
        ta.dispatchEvent(new Event('change', { bubbles: true }));

        setter.call(ta, val);
        ta.dispatchEvent(new Event('input', { bubbles: true }));
        ta.dispatchEvent(new Event('change', { bubbles: true }));
    """, css_selector, value)


def _click_send(driver, wait_sec=30):
    ok = _wait_until(driver, f"return !!document.querySelector('{SEND_BTN}');")
    if not ok:
        raise RuntimeError("Send button not found")

    start = time.time()
    while time.time() - start < wait_sec:
        enabled = driver.execute_script("""
            const btn = document.querySelector(arguments[0]);
            if (!btn) return false;
            const aria = (btn.getAttribute('aria-disabled') || '').toLowerCase();
            const disabled = btn.hasAttribute('disabled');
            return !disabled && aria !== 'true';
        """, SEND_BTN)
        if enabled:
            break
        time.sleep(0.2)
    else:
        raise RuntimeError("Send button never enabled")

    driver.execute_script(f"document.querySelector('{SEND_BTN}').click();")


# ─── Response Handling ──────────────────────────────────────
def _count_responses(driver):
    return driver.execute_script("""
        const nodes = document.querySelectorAll(arguments[0]);
        return nodes ? nodes.length : 0;
    """, RESP_MSGS) or 0


def _get_last_response_text(driver):
    return driver.execute_script("""
        const responses = document.querySelectorAll(arguments[0]);
        if (!responses || responses.length === 0) return "";
        const last = responses[responses.length - 1];
        return (last.innerText || "").trim();
    """, RESP_MSGS) or ""


def _wait_for_new_response(driver, before_count: int, response_timeout=120, stable_window=1.25, poll=0.25):
    start = time.time()

    while time.time() - start < response_timeout:
        if _count_responses(driver) > before_count:
            break
        time.sleep(poll)

    last = ""
    last_change = time.time()

    while time.time() - start < response_timeout:
        cur = _get_last_response_text(driver)
        if cur != last:
            last = cur
            last_change = time.time()
        elif time.time() - last_change >= stable_window:
            return last
        time.sleep(poll)

    return last


def _get_markdown_via_copy(driver):
    return driver.execute_script("""
        const responses = document.querySelectorAll(arguments[0]);
        if (!responses || responses.length === 0) return "";

        const last = responses[responses.length - 1];
        const btn = last.querySelector(arguments[1]);
        if (!btn) return "";

        let copied = "";
        const orig = navigator.clipboard.writeText;
        navigator.clipboard.writeText = (txt) => { copied = txt; return Promise.resolve(); };

        btn.click();
        navigator.clipboard.writeText = orig;

        return copied;
    """, RESP_MSGS, COPY_BTN_SEL) or ""


def _close_ai_panel(driver):
    is_open = driver.execute_script(f"return !!document.querySelector('{AI_PANEL}');")
    if not is_open:
        return

    exists = driver.execute_script(f"return !!document.querySelector('{CLOSE_PANEL_BTN}');")
    if not exists:
        return

    driver.execute_script(f"document.querySelector('{CLOSE_PANEL_BTN}').click();")
    _wait_until(driver, f"return !document.querySelector('{AI_PANEL}');")


# ─── Public API ─────────────────────────────────────────────
def ask_ai_assistant(
    driver,
    *,
    prompt: str,
    navigate_url: str = '',
    use_page_filters: Optional[bool] = None,
    start_new_chat: bool = False,
    close_panel_at_end: bool = True,
    response_timeout: int = 0,
    stable_window: float = 0,
) -> Dict[str, Any]:
    """
    Send a prompt to SignalFx's AI Assistant and return the response.

    Args:
        driver: Authenticated Selenium WebDriver on SignalFx.
        prompt: The question to ask the AI.
        navigate_url: Optional URL to navigate to before asking (e.g., APM page).
        use_page_filters: Toggle page context filter (True/False/None=leave as-is).
        start_new_chat: Start a fresh conversation before asking.
        close_panel_at_end: Close the AI panel when done.
        response_timeout: Max seconds to wait for response (0 = use settings default).
        stable_window: Seconds of stable text before considering response complete.

    Returns:
        {"ok": True, "prompt": ..., "markdown": ..., "timestamp": ...}
    """
    response_timeout = response_timeout or int(getattr(settings, 'SPLOC_RESPONSE_TIMEOUT', 120))
    stable_window = stable_window or float(getattr(settings, 'SPLOC_STABLE_WINDOW', 1.25))

    if navigate_url:
        driver.get(navigate_url)
        time.sleep(2)

    _ensure_ai_panel_open(driver)
    _ensure_page_filters_state(driver, use_page_filters)
    _maybe_start_new_chat(driver, start_new_chat)

    before = _count_responses(driver)

    _set_textarea_value(driver, TEXTBOX, prompt)
    _click_send(driver)

    response_text = _wait_for_new_response(
        driver, before,
        response_timeout=response_timeout,
        stable_window=stable_window,
    )

    markdown = _get_markdown_via_copy(driver)
    if not markdown.strip():
        markdown = response_text

    if close_panel_at_end:
        _close_ai_panel(driver)

    return {
        "ok": True,
        "timestamp": datetime.now().isoformat(),
        "prompt": prompt,
        "markdown": markdown,
        "url": navigate_url or driver.current_url,
    }

"""
SPLOC trace waterfall scraper — extracts span data from SignalFx trace detail pages.

Accepts a Selenium WebDriver (managed by SplocRunner) and returns structured data.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, Any, List
from urllib.parse import quote

from django.conf import settings
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait


SCROLL_CONTAINER_SELECTORS = [
    'div[data-test="waterfall v2"] div[class*="Tracestyles__ScrollContainer"]',
    'div[class*="Tracestyles__TraceRows"] div[class*="Tracestyles__ScrollContainer"]',
]


def _sploc_base():
    return getattr(settings, 'SPLOC_BASE', 'https://your-org.signalfx.com').rstrip('/')


def build_trace_url(trace_id: str, service: str) -> str:
    base = _sploc_base()
    matchers_json = f'[{{"key":"Service","values":["{service}"],"isNot":false}}]'
    return f"{base}/#/apm/traces/{trace_id}?matchers={quote(matchers_json, safe='')}"


def _wait_dom_ready(driver, timeout: int = 25):
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") in ("interactive", "complete")
    )


def _ensure_waterfall_tab(driver):
    driver.execute_script("""
        const input = document.querySelector("input[type='radio'][name='tab'][value='waterfall']");
        if (input && !input.checked) {
            const label = input.closest("label");
            if (label) label.click();
            else input.click();
        }
    """)


def _wait_for_scroll_container(driver, timeout: int = 25) -> str:
    start = time.time()
    while time.time() - start < timeout:
        for sel in SCROLL_CONTAINER_SELECTORS:
            found = driver.execute_script("return !!document.querySelector(arguments[0]);", sel)
            if found:
                return sel
        time.sleep(0.25)
    raise TimeoutException(f"Could not find scroll container: {SCROLL_CONTAINER_SELECTORS}")


def _extract_visible_rows(driver, container_css: str) -> List[Dict[str, Any]]:
    return driver.execute_script("""
        const container = document.querySelector(arguments[0]);
        if (!container) return [];

        function norm(s){ return (s||"").replace(/\\u00A0/g," ").replace(/\\s+/g," ").trim(); }

        function getPx(str){
            const m = /(-?\\d+(?:\\.\\d+)?)px/.exec(str || "");
            return m ? parseFloat(m[1]) : null;
        }

        const rows = Array.from(container.querySelectorAll("div[data-index][data-measure-key]"));
        const out = [];

        for (const r of rows) {
            const index = parseInt(r.getAttribute("data-index"), 10);
            const span_id = r.getAttribute("data-measure-key");

            const svc = r.querySelector(".service-hover-service-name span");
            const op = r.querySelector(".service-hover-operation-name span");
            const dur = r.querySelector(".labelsContainer .linkIcon");

            const indicator = r.querySelector("[class*='ServiceIndicator']");
            let indent = null;
            if (indicator) indent = getPx(indicator.getAttribute("style"));

            out.push({
                index,
                span_id,
                service: norm(svc ? svc.textContent : ""),
                operation: norm(op ? op.textContent : ""),
                duration: norm(dur ? dur.textContent : ""),
                indent_px: indent,
            });
        }

        return out;
    """, container_css)


def _scroll_container_step(driver, container_css, step_factor):
    return driver.execute_script("""
        const sel = arguments[0];
        const factor = arguments[1];
        const c = document.querySelector(sel);
        if (!c) return {found:false};

        const before = c.scrollTop;
        const max = c.scrollHeight - c.clientHeight;
        const step = Math.floor(c.clientHeight * factor);
        const after = Math.min(max, before + step);
        c.scrollTop = after;

        return {
            found:true,
            before,
            after,
            max,
            atBottom: after >= max - 2
        };
    """, container_css, step_factor)


def scrape_trace_waterfall(
    driver,
    *,
    trace_id: str,
    service_name: str,
    max_spans: int = 0,
    scroll_step_factor: float = 0.85,
    no_new_limit: int = 6,
    sleep_between_scrolls: float = 0.25,
    wait_timeout: int = 25,
) -> Dict[str, Any]:
    """
    Navigate to a trace and scrape all waterfall spans.

    Returns:
        {"ok": True, "trace_id": ..., "total_spans": N, "rows": [...], ...}
    """
    max_spans = max_spans or int(getattr(settings, 'SPLOC_MAX_SPANS', 0))
    scroll_step_factor = scroll_step_factor or float(getattr(settings, 'SPLOC_SCROLL_STEP_FACTOR', 0.85))
    no_new_limit = no_new_limit or int(getattr(settings, 'SPLOC_NO_NEW_LIMIT', 6))

    trace_url = build_trace_url(trace_id, service_name)
    driver.get(trace_url)

    _wait_dom_ready(driver, timeout=wait_timeout)
    _ensure_waterfall_tab(driver)

    container_sel = _wait_for_scroll_container(driver, timeout=wait_timeout)

    seen_ids = set()
    all_rows = []
    no_new = 0

    while True:
        visible = _extract_visible_rows(driver, container_sel)

        added = 0
        for r in visible:
            sid = r.get("span_id")
            if sid and sid not in seen_ids:
                seen_ids.add(sid)
                all_rows.append(r)
                added += 1
                if max_spans and len(all_rows) >= max_spans:
                    break

        if max_spans and len(all_rows) >= max_spans:
            break

        no_new = no_new + 1 if added == 0 else 0
        if no_new >= no_new_limit:
            break

        metrics = _scroll_container_step(driver, container_sel, scroll_step_factor)
        time.sleep(sleep_between_scrolls)

        if metrics.get("atBottom"):
            break

    all_rows.sort(key=lambda x: (x.get("index") is None, x.get("index") or 0))

    return {
        "ok": True,
        "captured_at": datetime.now().isoformat(),
        "trace_id": trace_id,
        "service_name": service_name,
        "trace_url": trace_url,
        "total_spans": len(all_rows),
        "rows": all_rows,
    }

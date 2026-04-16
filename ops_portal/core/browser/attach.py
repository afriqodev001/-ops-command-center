from __future__ import annotations

from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions


def attach_to_edge(debug_port: int, *, command_timeout_seconds: int = 240):
    """
    Attach Selenium to an existing Microsoft Edge instance started with:
    --remote-debugging-port=<debug_port>

    Important:
    - Selenium's underlying HTTP client has a default read timeout (~120s).
    - Long execute_async_script calls (Grafana/Splunk polling) can exceed that.
    - We raise the command executor timeout so the driver doesn't error at 120s.
    """
    debug_port = int(debug_port)

    opts = EdgeOptions()
    opts.use_chromium = True
    opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")

    driver = webdriver.Edge(options=opts)

    # Basic timeouts (safe defaults)
    try:
        driver.set_page_load_timeout(60)
    except Exception:
        pass

    try:
        driver.set_script_timeout(command_timeout_seconds)
    except Exception:
        pass

    # Critical: increase HTTP read timeout to WebDriver
    try:
        driver.command_executor.set_timeout(command_timeout_seconds)  # type: ignore[attr-defined]
    except Exception:
        try:
            # Workaround for Selenium 4 client_config timeout
            driver.command_executor._client_config.timeout = command_timeout_seconds  # type: ignore[attr-defined]
        except Exception:
            pass

    try:
        driver.implicitly_wait(2)
    except Exception:
        pass

    return driver

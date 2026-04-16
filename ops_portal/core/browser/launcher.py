import os
import socket
import subprocess
import time
from typing import Dict, Optional

from django.conf import settings

from .health import is_debug_alive


def _edge_exe() -> str:
    return getattr(
        settings,
        "EDGE_EXE_PATH",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    )


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", int(port))) == 0


def _wait_for_port(port: int, timeout: int = 12) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if _port_open(port):
            return True
        time.sleep(0.25)
    return False


def _popen_headed_windows(args: list) -> subprocess.Popen:
    """
    Force visible window using cmd start.
    """
    cmd = ["cmd", "/c", "start", ""] + args
    return subprocess.Popen(cmd, shell=False)


def launch_edge(
    profile_dir: str,
    debug_port: int,
    url: str,
    *,
    headless: bool = True,
    startup_timeout: int = 12,
) -> Dict[str, Optional[object]]:
    """
    Launch Edge with remote debugging.

    Returns:
        {"status": "reused"|"headless"|"headed"|"failed", "port": int, "pid": int|None}
    """

    os.makedirs(profile_dir, exist_ok=True)

    # Reuse if already alive
    if is_debug_alive(debug_port):
        return {"status": "reused", "port": int(debug_port), "pid": None}

    base_args = [
        _edge_exe(),
        f"--remote-debugging-port={int(debug_port)}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-notifications",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-features=TranslateUI",
    ]

    # 1) Headless automation
    if headless:
        headless_args = base_args + [
            "--headless=new",
            "--disable-gpu",
            "--window-size=1400,900",
            url,
        ]
        p = subprocess.Popen(headless_args, shell=False)
        if _wait_for_port(debug_port, timeout=startup_timeout):
            return {"status": "headless", "port": int(debug_port), "pid": p.pid}
        # fall through to headed (SSO/cookies may require UI)

    # 2) Headed login
    headed_args = base_args + [
        "--new-window",
        "--start-maximized",
        url,
    ]
    p2 = _popen_headed_windows(headed_args)
    if _wait_for_port(debug_port, timeout=startup_timeout):
        return {"status": "headed", "port": int(debug_port), "pid": p2.pid}

    return {"status": "failed", "port": int(debug_port), "pid": None}

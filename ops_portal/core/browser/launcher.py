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


def _kill_orphan_edge_for_profile(profile_dir: str) -> int:
    """
    Find any msedge.exe process that has --user-data-dir pointing at this
    profile_dir and kill it. Returns the number of processes killed.

    Why: Edge keeps a `lockfile` in the user-data-dir while running; if a prior
    Edge crashed (or was killed without releasing the file), that lockfile stays
    and new launches against the same profile silently fail. The session
    registry's debug_port may also drift between runs, so the standard
    is_debug_alive() check on the registry's port misses the orphan.

    Windows-only. No-op if WMI is unavailable.
    """
    if os.name != "nt":
        return 0
    try:
        norm = os.path.normcase(os.path.normpath(profile_dir))
        # Use WMIC to list msedge processes with their command line.
        out = subprocess.run(
            ["wmic", "process", "where", "name='msedge.exe'", "get", "ProcessId,CommandLine", "/format:csv"],
            capture_output=True, text=True, timeout=8,
        ).stdout
    except Exception:
        return 0

    killed = 0
    for line in out.splitlines():
        # CSV format: Node,CommandLine,ProcessId
        if not line or "msedge" not in line.lower():
            continue
        parts = line.split(",")
        if len(parts) < 3:
            continue
        cmdline = parts[1] or ""
        try:
            pid = int(parts[-1].strip())
        except ValueError:
            continue
        if os.path.normcase(norm) not in os.path.normcase(cmdline):
            continue
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5,
            )
            killed += 1
        except Exception:
            pass

    if killed:
        # Give Windows a beat to release the lockfile.
        time.sleep(0.75)
    return killed


def _clear_profile_lockfiles(profile_dir: str) -> None:
    """Best-effort removal of stale Chromium lockfiles."""
    for name in ("lockfile", "SingletonLock", "SingletonCookie", "SingletonSocket"):
        p = os.path.join(profile_dir, name)
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass


def launch_edge(
    profile_dir: str,
    debug_port: int,
    url: str,
    *,
    headless: bool = True,
    startup_timeout: int | None = None,
) -> Dict[str, Optional[object]]:
    """
    Launch Edge with remote debugging.

    Returns:
        {"status": "reused"|"headless"|"headed"|"failed", "port": int, "pid": int|None}
    """

    if startup_timeout is None:
        startup_timeout = int(getattr(settings, 'BROWSER_STARTUP_TIMEOUT', 30))

    os.makedirs(profile_dir, exist_ok=True)

    # Reuse if already alive
    if is_debug_alive(debug_port):
        return {"status": "reused", "port": int(debug_port), "pid": None}

    # Profile may be locked by an orphan Edge from an earlier session whose
    # debug_port has drifted out of the registry. Kill any msedge process that
    # has this profile_dir in its command line, then clear stale lockfiles.
    _kill_orphan_edge_for_profile(profile_dir)
    _clear_profile_lockfiles(profile_dir)

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

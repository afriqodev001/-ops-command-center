import subprocess
from typing import Optional


def shutdown_browser(debug_port: int, pid: Optional[int] = None) -> None:
    """
    Shut down an Edge instance started with remote debugging.

    Strategy:
    1) Kill by PID if known (precise — won't affect other Edge windows).
    2) Fallback: force-kill all msedge.exe processes (Windows).
    """

    # 1) Targeted kill by PID
    if pid:
        result = subprocess.run(
            ["taskkill", "/F", "/PID", str(pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            return

    # 2) Fallback: kill all Edge processes
    subprocess.run(
        ["taskkill", "/F", "/IM", "msedge.exe"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

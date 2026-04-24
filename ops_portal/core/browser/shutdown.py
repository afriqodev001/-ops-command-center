import subprocess
import time
import urllib.request
from typing import Optional


def shutdown_browser(debug_port: int, pid: Optional[int] = None) -> None:
    """
    Shut down the Edge instance we control, WITHOUT killing other Edge windows.

    Strategy (in order of preference):
    1) CDP Browser.close via WebSocket — clean shutdown of ONLY this instance.
       Works regardless of PID provenance. Verifies by checking the debug
       port is no longer alive before returning.
    2) Targeted PID kill (Windows taskkill /F /T) — fallback when CDP fails
       or websocket-client isn't installed. Also verified via port check.
    3) No global fallback — we never kill all msedge.exe. If both methods
       fail, the browser stays running; the auth-retry wrapper handles this
       gracefully on the next task.

    Each strategy runs even if an earlier one "returned" without raising —
    we verify by checking whether the debug port is dead, since the CDP
    close call can silently no-op (e.g. if websocket-client is missing or
    the browser ignored the message).
    """
    # Strategy 1: CDP Browser.close via WebSocket
    if debug_port and _is_port_alive(debug_port):
        ws_url = _get_browser_ws(debug_port)
        if ws_url:
            _send_cdp_close(ws_url)
            if _wait_port_dead(debug_port, timeout=3.0):
                return

    # Strategy 2: targeted PID kill
    if pid:
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except Exception:
            pass

        # Verify the kill actually worked if we have a port to check
        if debug_port:
            if _wait_port_dead(debug_port, timeout=3.0):
                return
        else:
            # No port to verify — trust taskkill
            return

    # Strategy 3: nothing — we never kill all msedge.exe globally


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------
def _is_port_alive(debug_port: int) -> bool:
    try:
        with urllib.request.urlopen(
            f'http://127.0.0.1:{int(debug_port)}/json/version',
            timeout=1.5,
        ) as resp:
            return getattr(resp, 'status', 200) == 200
    except Exception:
        return False


def _wait_port_dead(debug_port: int, timeout: float = 3.0) -> bool:
    """Poll until the debug port stops responding. Returns True if it died."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _is_port_alive(debug_port):
            return True
        time.sleep(0.25)
    return False


def _get_browser_ws(debug_port: int) -> Optional[str]:
    """Get the browser-level WebSocket URL from the CDP endpoint."""
    try:
        with urllib.request.urlopen(
            f'http://127.0.0.1:{int(debug_port)}/json/version',
            timeout=2,
        ) as resp:
            import json
            data = json.loads(resp.read())
            return data.get('webSocketDebuggerUrl')
    except Exception:
        return None


def _send_cdp_close(ws_url: str) -> None:
    """Send Browser.close via WebSocket to cleanly shut down the browser."""
    try:
        import websocket
        import json
        ws = websocket.create_connection(ws_url, timeout=3)
        try:
            ws.send(json.dumps({'id': 1, 'method': 'Browser.close'}))
            # Give the browser a moment to acknowledge before we drop the socket
            try:
                ws.settimeout(1.5)
                ws.recv()
            except Exception:
                pass
        finally:
            try:
                ws.close()
            except Exception:
                pass
    except ImportError:
        pass
    except Exception:
        pass

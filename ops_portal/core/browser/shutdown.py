import subprocess
import urllib.request
from typing import Optional


def shutdown_browser(debug_port: int, pid: Optional[int] = None) -> None:
    """
    Shut down the Edge instance we control, WITHOUT killing other Edge windows.

    Strategy (in order of preference):
    1) CDP close — send Browser.close via the debug port. This cleanly shuts
       down ONLY the instance listening on that port, regardless of PID.
    2) PID kill — targeted taskkill by the stored PID. May fail if the PID
       is the launcher wrapper rather than the actual Edge process.
    3) NO FALLBACK — we never kill all msedge.exe. If both methods fail, the
       browser stays running until the user closes it manually. The auth-retry
       wrapper handles this gracefully on the next task.
    """

    # 1) CDP close — most reliable, only affects our instance
    if debug_port:
        try:
            # PUT to /json/close on the debug port asks Edge to shut itself down
            req = urllib.request.Request(
                f'http://127.0.0.1:{int(debug_port)}/json/close',
                method='PUT',
            )
            urllib.request.urlopen(req, timeout=3)
            return
        except Exception:
            pass

        # Alternative: the Browser.close DevTools protocol method
        try:
            import json
            ws_url = _get_browser_ws(debug_port)
            if ws_url:
                _send_cdp_close(ws_url)
                return
        except Exception:
            pass

    # 2) Targeted PID kill (Windows only)
    if pid:
        try:
            result = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                return
        except Exception:
            pass

    # 3) No fallback — do NOT kill all msedge.exe


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
        ws = websocket.create_connection(ws_url, timeout=3)
        import json
        ws.send(json.dumps({'id': 1, 'method': 'Browser.close'}))
        ws.close()
    except ImportError:
        # websocket-client not installed — fall through to PID kill
        pass
    except Exception:
        pass

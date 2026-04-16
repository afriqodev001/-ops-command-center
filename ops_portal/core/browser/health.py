import requests


def is_debug_alive(debug_port: int) -> bool:
    """
    True if a Chromium DevTools endpoint is responding.
    """
    try:
        r = requests.get(f"http://127.0.0.1:{int(debug_port)}/json/version", timeout=2)
        return r.status_code == 200
    except Exception:
        return False

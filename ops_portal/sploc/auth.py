"""
SPLOC authentication check — verifies the browser has valid SignalFx session.
"""
from __future__ import annotations
from django.conf import settings


def sploc_auth_check(driver, origin_url: str = '') -> bool:
    """Return True if the browser is authenticated to SignalFx."""
    base = (origin_url or getattr(settings, 'SPLOC_BASE', 'https://your-org.signalfx.com')).rstrip('/')
    try:
        current = driver.current_url or ''
        if not current.startswith(base):
            driver.get(base)

        result = driver.execute_script("""
            try {
                const resp = await fetch(arguments[0], {
                    credentials: 'include',
                    headers: { 'Accept': 'application/json' }
                });
                return { status: resp.status, ok: resp.ok };
            } catch(e) {
                return { status: 0, ok: false, error: e.message };
            }
        """, f'{base}/v2/organization')

        if isinstance(result, dict):
            return result.get('ok', False)
        return False
    except Exception:
        return False

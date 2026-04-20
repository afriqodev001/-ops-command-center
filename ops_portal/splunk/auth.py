"""
Splunk authentication check — verifies the browser has valid SSO cookies.
"""
from __future__ import annotations
from django.conf import settings


def splunk_auth_check(driver, origin_url: str = '') -> bool:
    """Return True if the browser is authenticated to Splunk."""
    base = (origin_url or getattr(settings, 'SPLUNK_BASE', 'https://your-splunk.splunkcloud.com')).rstrip('/')
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
        """, f'{base}/en-US/splunkd/__raw/services/authentication/current-context?output_mode=json')

        if isinstance(result, dict):
            return result.get('ok', False)
        return False
    except Exception:
        return False

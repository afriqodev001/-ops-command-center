"""
SPLOC URL builders — construct SignalFx APM URLs.
"""
from __future__ import annotations
from urllib.parse import quote

from django.conf import settings


def _sploc_base():
    return getattr(settings, 'SPLOC_BASE', 'https://your-org.signalfx.com').rstrip('/')


def build_apm_url() -> str:
    apm_path = getattr(settings, 'SPLOC_APM_PATH', '/#/apm')
    return f"{_sploc_base()}{apm_path}"


def build_trace_url(trace_id: str, service_name: str = '') -> str:
    base = _sploc_base()
    if service_name:
        matchers_json = f'[{{"key":"Service","values":["{service_name}"],"isNot":false}}]'
        return f"{base}/#/apm/traces/{trace_id}?matchers={quote(matchers_json, safe='')}"
    return f"{base}/#/apm/traces/{trace_id}"


def build_service_url(service_name: str) -> str:
    return f"{_sploc_base()}/#/apm/services/{quote(service_name)}"

"""
Simple file-backed store for named Standard Change template URLs.

Entries look like:
    {
        "os_patching": {
            "label": "OS Patching — monthly",
            "url":   "https://INSTANCE.service-now.com/nav_to.do?uri=change_request.do?sys_id=-1&sysparm_template=OS_Patching"
        },
        ...
    }

Mirrors the user_presets.json pattern.
"""

from __future__ import annotations
from typing import Dict, Any
from pathlib import Path
import json

_STORE_FILE = Path(__file__).parent.parent / 'standard_change_templates.json'


def load_templates() -> Dict[str, Dict[str, str]]:
    if not _STORE_FILE.exists():
        return {}
    try:
        return json.loads(_STORE_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def save_template(key: str, label: str, url: str) -> None:
    data = load_templates()
    data[key] = {'label': label, 'url': url}
    _STORE_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')


def delete_template(key: str) -> None:
    data = load_templates()
    if key in data:
        del data[key]
        _STORE_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')


def build_standard_change_url(template_url: str, row: Dict[str, Any]) -> str:
    """
    Append the row's editable fields as ServiceNow sysparm_query params so the
    form pre-populates. Caller handles the case where template_url is empty.
    """
    from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse

    if not template_url:
        return ''

    parsed = urlparse(template_url)
    existing = dict(parse_qsl(parsed.query, keep_blank_values=True))

    # Compose the ^-delimited sysparm_query that ServiceNow uses for pre-fill.
    prefill = []
    for field in ('short_description', 'assignment_group', 'start_date', 'end_date', 'description', 'risk'):
        val = (row.get(field) or '').strip()
        if val:
            prefill.append(f"{field}={val}")
    if prefill:
        # Merge with any existing sysparm_query on the template URL
        prior = existing.get('sysparm_query', '')
        combined = f"{prior}^{'^'.join(prefill)}" if prior else '^'.join(prefill)
        existing['sysparm_query'] = combined

    new_query = urlencode(existing)
    return urlunparse(parsed._replace(query=new_query))

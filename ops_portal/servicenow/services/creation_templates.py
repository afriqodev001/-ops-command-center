"""
Unified creation-template store.

A single JSON file (creation_templates.json) holds templates for creating
records across four kinds:

    standard_change  — URL-based (opens ServiceNow UI pre-populated)
    normal_change    — Table API payload
    emergency_change — Table API payload
    incident         — Table API payload

Entry shape:

    {
        "ssl_renewal": {
            "kind":  "standard_change",
            "label": "SSL certificate renewal",
            "url":   "https://INSTANCE.service-now.com/..."
        },
        "db_patching": {
            "kind":  "normal_change",
            "label": "Database patching",
            "fields": {
                "short_description": "Monthly DB patching",
                "assignment_group":  "Database Ops",
                "risk":              "moderate"
            }
        },
        "p1_bridge": {
            "kind":  "incident",
            "label": "P1 bridge call",
            "fields": {
                "short_description": "P1 - ",
                "priority":          "1",
                "assignment_group":  "Platform"
            }
        }
    }

On first read, if creation_templates.json is missing but the legacy
standard_change_templates.json exists, entries are migrated in-place with
kind="standard_change".
"""

from __future__ import annotations
from typing import Dict, Any, List
from pathlib import Path
import json

_STORE_FILE  = Path(__file__).parent.parent / 'creation_templates.json'
_LEGACY_FILE = Path(__file__).parent.parent / 'standard_change_templates.json'

VALID_KINDS = ('standard_change', 'normal_change', 'emergency_change', 'incident')

KIND_LABELS = {
    'standard_change':  'Standard change',
    'normal_change':    'Normal change',
    'emergency_change': 'Emergency change',
    'incident':         'Incident',
}

# Fields each API-based kind renders in the create form, in display order.
KIND_FIELDS: Dict[str, List[str]] = {
    'standard_change':  ['short_description', 'assignment_group', 'start_date', 'end_date', 'description'],
    'normal_change':    ['short_description', 'assignment_group', 'start_date', 'end_date', 'risk', 'description'],
    'emergency_change': ['short_description', 'assignment_group', 'start_date', 'end_date', 'risk', 'description'],
    'incident':         ['caller', 'category', 'subcategory', 'service',
                         'short_description', 'description', 'assignment_group',
                         'impact', 'urgency'],
}

# Default field values injected into new incident templates.
# Impact 3 + Urgency 3 → Priority 5 (Very Low) in standard SN config.
INCIDENT_FIELD_DEFAULTS: Dict[str, str] = {
    'impact':  '3',
    'urgency': '3',
}


def _migrate_legacy_if_needed() -> None:
    if _STORE_FILE.exists() or not _LEGACY_FILE.exists():
        return
    try:
        legacy = json.loads(_LEGACY_FILE.read_text(encoding='utf-8'))
    except Exception:
        return
    migrated: Dict[str, Dict[str, Any]] = {}
    for key, entry in (legacy or {}).items():
        if not isinstance(entry, dict):
            continue
        migrated[key] = {
            'kind':  'standard_change',
            'label': entry.get('label', key),
            'url':   entry.get('url', ''),
        }
    if migrated:
        _STORE_FILE.write_text(json.dumps(migrated, indent=2), encoding='utf-8')


def load_templates() -> Dict[str, Dict[str, Any]]:
    """Return all templates keyed by key."""
    _migrate_legacy_if_needed()
    if not _STORE_FILE.exists():
        return {}
    try:
        return json.loads(_STORE_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def load_templates_by_kind(kind: str) -> Dict[str, Dict[str, Any]]:
    return {k: v for k, v in load_templates().items() if v.get('kind') == kind}


def load_templates_grouped() -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Return {kind: {key: entry}} for display in grouped lists."""
    out: Dict[str, Dict[str, Dict[str, Any]]] = {k: {} for k in VALID_KINDS}
    for key, entry in load_templates().items():
        kind = entry.get('kind', 'standard_change')
        out.setdefault(kind, {})[key] = entry
    return out


def save_template(key: str, kind: str, label: str, url: str = '', fields: Dict[str, str] | None = None) -> None:
    data = load_templates()
    entry: Dict[str, Any] = {'kind': kind, 'label': label}
    if kind == 'standard_change':
        entry['url'] = url
    else:
        entry['fields'] = fields or {}
    data[key] = entry
    _STORE_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')


def delete_template(key: str) -> None:
    data = load_templates()
    if key in data:
        del data[key]
        _STORE_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')


def build_standard_change_url(template_url: str, row: Dict[str, Any]) -> str:
    """
    Append the given field values to a standard change URL as ServiceNow
    sysparm_query parameters. Kept here so bulk-create + single-create share
    one implementation.
    """
    from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse
    if not template_url:
        return ''
    parsed = urlparse(template_url)
    existing = dict(parse_qsl(parsed.query, keep_blank_values=True))

    prefill = []
    for field in ('short_description', 'assignment_group', 'start_date', 'end_date', 'description', 'risk'):
        val = (row.get(field) or '').strip()
        if val:
            prefill.append(f"{field}={val}")
    if prefill:
        prior = existing.get('sysparm_query', '')
        combined = f"{prior}^{'^'.join(prefill)}" if prior else '^'.join(prefill)
        existing['sysparm_query'] = combined

    return urlunparse(parsed._replace(query=urlencode(existing)))

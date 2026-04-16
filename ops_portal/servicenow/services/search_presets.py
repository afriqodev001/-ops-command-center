"""
File-backed store for Search-page filter presets.

Entry shape (stored in `search_presets.json`):

    {
        "pdly_prod": {
            "app_id":           "PDLY",
            "label":            "Production ledger",
            "cmdb_ci":          "prod-pdly-app-cluster-eu-01",
            "requested_by":     "",
            "assignment_group": "Financial Platform"
        },
        ...
    }

The point: map a short `app_id` (+ friendly `label`) to a long real
`cmdb_ci` value, plus optional defaults for the other search filters.
"""

from __future__ import annotations
from typing import Dict, Any
from pathlib import Path
import json

_STORE_FILE = Path(__file__).parent.parent / 'search_presets.json'


def load_presets() -> Dict[str, Dict[str, Any]]:
    if not _STORE_FILE.exists():
        return {}
    try:
        return json.loads(_STORE_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def save_preset(key: str, data: Dict[str, Any]) -> None:
    presets = load_presets()
    presets[key] = {
        'app_id':           (data.get('app_id') or '').strip(),
        'label':            (data.get('label') or '').strip(),
        'cmdb_ci':          (data.get('cmdb_ci') or '').strip(),
        'requested_by':     (data.get('requested_by') or '').strip(),
        'assignment_group': (data.get('assignment_group') or '').strip(),
    }
    _STORE_FILE.write_text(json.dumps(presets, indent=2), encoding='utf-8')


def delete_preset(key: str) -> None:
    presets = load_presets()
    if key in presets:
        del presets[key]
        _STORE_FILE.write_text(json.dumps(presets, indent=2), encoding='utf-8')

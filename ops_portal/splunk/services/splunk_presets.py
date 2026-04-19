"""
Splunk search presets — file-backed store with built-in defaults.

Each preset defines:
- description: what it does
- spl: SPL template string with {placeholder} params
- defaults: earliest/latest, include_preview/events, paging
- required_params: list of required template placeholders
- tags: comma-separated tags for filtering
"""
from __future__ import annotations
from typing import Dict, Any, List
from pathlib import Path
import json

from django.conf import settings

_STORE_FILE = Path(__file__).parent.parent / 'splunk_presets.json'

BUILT_IN_PRESETS: Dict[str, Dict[str, Any]] = {
    "pldcs_takeapp_submission_started_count": {
        "description": 'PLDCS TakeApp: count of "application submission started" events.',
        "spl": (
            'index=pldcs sourcetype="hec:ocp:app" component=ct_app_logs '
            '"kubernetes.namespace_name"="{namespace}" {service} '
            '"application submission started" | stats count'
        ),
        "defaults": {
            "earliest_time": getattr(settings, "SPLUNK_DEFAULT_EARLIEST", "-10m"),
            "latest_time": getattr(settings, "SPLUNK_DEFAULT_LATEST", "now"),
            "include_preview": True,
            "include_events": False,
            "preview_count": 20,
            "preview_offset": 0,
        },
        "required_params": ["namespace", "service"],
        "tags": "pldcs, count",
    },
    "pldcs_recent_errors_raw_events": {
        "description": "PLDCS: Raw error events for a term in last N minutes.",
        "spl": (
            'index=pldcs sourcetype="hec:ocp:app" component=ct_app_logs '
            '"kubernetes.namespace_name"="{namespace}" "{term}" '
            '| head {limit}'
        ),
        "defaults": {
            "earliest_time": "-30m",
            "latest_time": "now",
            "include_preview": False,
            "include_events": True,
            "events_count": 50,
            "events_offset": 0,
            "events_max_lines": 5,
        },
        "required_params": ["namespace", "term"],
        "tags": "pldcs, errors, raw",
    },
}


def _load_store() -> Dict[str, Dict[str, Any]]:
    if not _STORE_FILE.exists():
        return {}
    try:
        return json.loads(_STORE_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _save_store(data: Dict[str, Dict[str, Any]]) -> None:
    _STORE_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')


def list_presets() -> Dict[str, Dict[str, Any]]:
    stored = _load_store()
    merged = dict(BUILT_IN_PRESETS)
    merged.update(stored)
    result = {}
    for name, cfg in merged.items():
        result[name] = {
            "description": cfg.get("description", ""),
            "spl": cfg.get("spl", ""),
            "required_params": cfg.get("required_params", []),
            "defaults": cfg.get("defaults", {}),
            "tags": cfg.get("tags", ""),
            "is_builtin": name in BUILT_IN_PRESETS and name not in stored,
        }
    return result


def get_preset(name: str) -> Dict[str, Any] | None:
    all_presets = list_presets()
    return all_presets.get(name)


def save_preset(name: str, preset: Dict[str, Any]) -> None:
    stored = _load_store()
    stored[name] = preset
    _save_store(stored)


def delete_preset(name: str) -> None:
    stored = _load_store()
    stored.pop(name, None)
    _save_store(stored)


def render_preset(name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    preset = get_preset(name)
    if not preset:
        raise ValueError(f"Unknown preset: {name}")

    required: List[str] = preset.get("required_params", [])
    missing = [k for k in required if params.get(k) in (None, "")]
    if missing:
        raise ValueError(f"Missing required params: {', '.join(missing)}")

    defaults = dict(preset.get("defaults") or {})
    rendered_spl = (preset.get("spl") or "").format(**params)

    return {
        "search": rendered_spl,
        "defaults": defaults,
    }


def export_presets(names: List[str] | None = None) -> Dict:
    all_presets = list_presets()
    if names:
        filtered = {k: v for k, v in all_presets.items() if k in names}
    else:
        filtered = all_presets
    for v in filtered.values():
        v.pop('is_builtin', None)
    return {"presets": filtered}


def import_presets(data: Dict, mode: str = 'skip') -> int:
    presets = data.get('presets') or {}
    if not isinstance(presets, dict):
        return 0
    stored = _load_store()
    imported = 0
    for name, cfg in presets.items():
        if not name or not isinstance(cfg, dict):
            continue
        if name in stored or name in BUILT_IN_PRESETS:
            if mode == 'skip':
                continue
        stored[name] = cfg
        imported += 1
    _save_store(stored)
    return imported

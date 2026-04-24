"""
SPLOC AI prompt packs — file-backed store with built-in defaults.

Each pack defines:
- name: display title (button label)
- description: short subtitle
- prompt: the text sent to SignalFx's AI Assistant
- defaults: { use_page_filters, start_new_chat, close_panel_at_end }
- tags: comma-separated tags for filtering
"""
from __future__ import annotations
from typing import Dict, Any, List
from pathlib import Path
import json


_STORE_FILE = Path(__file__).parent.parent / 'prompt_packs.json'


BUILT_IN_PACKS: Dict[str, Dict[str, Any]] = {
    "recent_errors_15m": {
        "description": "Error traces in the past 15 minutes",
        "prompt": "List error traces from the past 15 minutes.",
        "defaults": {
            "use_page_filters": False,
            "start_new_chat": False,
            "close_panel_at_end": True,
        },
        "tags": "errors, recent",
    },
    "high_latency_now": {
        "description": "Services with highest latency right now",
        "prompt": "What services have the highest latency right now?",
        "defaults": {
            "use_page_filters": False,
            "start_new_chat": False,
            "close_panel_at_end": True,
        },
        "tags": "latency, performance",
    },
    "error_hotspots_1h": {
        "description": "Top error-producing services in the past hour",
        "prompt": "Show me the top error-producing services in the past hour.",
        "defaults": {
            "use_page_filters": False,
            "start_new_chat": False,
            "close_panel_at_end": True,
        },
        "tags": "errors, hotspots",
    },
    "anomalies_30m": {
        "description": "Unusual patterns in the past 30 minutes",
        "prompt": "Are there any anomalies or unusual patterns in the past 30 minutes?",
        "defaults": {
            "use_page_filters": False,
            "start_new_chat": False,
            "close_panel_at_end": True,
        },
        "tags": "anomalies, monitoring",
    },
    "service_health_summary": {
        "description": "Overall service health overview",
        "prompt": "Summarize the health of all services.",
        "defaults": {
            "use_page_filters": False,
            "start_new_chat": False,
            "close_panel_at_end": True,
        },
        "tags": "health, summary",
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


def list_packs() -> Dict[str, Dict[str, Any]]:
    """Return all visible packs (built-ins + user, minus hidden ones)."""
    stored = _load_store()
    hidden = set(stored.get('_hidden', []))
    merged = dict(BUILT_IN_PACKS)
    merged.update({k: v for k, v in stored.items() if k != '_hidden'})
    result = {}
    for name, cfg in merged.items():
        if name in hidden:
            continue
        result[name] = {
            "description": cfg.get("description", ""),
            "prompt": cfg.get("prompt", ""),
            "defaults": cfg.get("defaults", {}),
            "tags": cfg.get("tags", ""),
            "is_builtin": name in BUILT_IN_PACKS and name not in stored,
        }
    return result


def get_pack(name: str) -> Dict[str, Any] | None:
    return list_packs().get(name)


def save_pack(name: str, pack: Dict[str, Any]) -> None:
    stored = _load_store()
    stored[name] = pack
    hidden = stored.get('_hidden', [])
    if name in hidden:
        hidden.remove(name)
        stored['_hidden'] = hidden
    _save_store(stored)


def delete_pack(name: str) -> None:
    """Delete user pack, or hide built-in pack."""
    stored = _load_store()
    if name in stored and name != '_hidden':
        del stored[name]
    if name in BUILT_IN_PACKS:
        hidden = stored.get('_hidden', [])
        if name not in hidden:
            hidden.append(name)
            stored['_hidden'] = hidden
    _save_store(stored)


def export_packs(names: List[str] | None = None) -> Dict:
    all_packs = list_packs()
    if names:
        filtered = {k: v for k, v in all_packs.items() if k in names}
    else:
        filtered = all_packs
    for v in filtered.values():
        v.pop('is_builtin', None)
    return {"packs": filtered}


def import_packs(data: Dict, mode: str = 'skip') -> int:
    """Import packs. Mode: 'skip' (don't overwrite) or 'overwrite'."""
    packs = data.get('packs') or data.get('presets') or {}
    if not isinstance(packs, dict):
        return 0
    stored = _load_store()
    imported = 0
    for name, cfg in packs.items():
        if not name or not isinstance(cfg, dict):
            continue
        if name in stored or name in BUILT_IN_PACKS:
            if mode == 'skip':
                continue
        stored[name] = cfg
        imported += 1
    _save_store(stored)
    return imported

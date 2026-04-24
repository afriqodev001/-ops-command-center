"""
SPLOC service catalog — file-backed list of SignalFx service names.

Each entry defines:
- description: short one-liner about the service
- tags: comma-separated tags for filtering
- added_at: epoch timestamp of first insertion (preserved across edits)

Seeded by import from JSON only — no built-in defaults, no auto-capture.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Any, List


_STORE_FILE = Path(__file__).parent.parent / 'service_catalog.json'


def _load_store() -> Dict[str, Dict[str, Any]]:
    if not _STORE_FILE.exists():
        return {}
    try:
        data = json.loads(_STORE_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_store(data: Dict[str, Dict[str, Any]]) -> None:
    _STORE_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')


def list_catalog() -> Dict[str, Dict[str, Any]]:
    """Return all services alphabetically by name."""
    stored = _load_store()
    result = {}
    for name in sorted(stored.keys()):
        cfg = stored[name] or {}
        result[name] = {
            "description": cfg.get("description", ""),
            "tags": cfg.get("tags", ""),
            "added_at": cfg.get("added_at"),
        }
    return result


def get_service(name: str) -> Dict[str, Any] | None:
    return list_catalog().get(name)


def save_service(name: str, meta: Dict[str, Any]) -> None:
    """Upsert; stamps added_at on first insert, preserves it on update."""
    if not name:
        return
    stored = _load_store()
    existing = stored.get(name) or {}
    entry = {
        "description": meta.get("description", "").strip(),
        "tags": meta.get("tags", "").strip(),
        "added_at": existing.get("added_at") or time.time(),
    }
    stored[name] = entry
    _save_store(stored)


def delete_service(name: str) -> None:
    stored = _load_store()
    if name in stored:
        del stored[name]
        _save_store(stored)


def export_catalog(names: List[str] | None = None) -> Dict:
    all_services = list_catalog()
    if names:
        filtered = {k: v for k, v in all_services.items() if k in names}
    else:
        filtered = all_services
    return {"services": filtered}


def import_catalog(data: Dict, mode: str = 'skip') -> int:
    """Import services. Mode: 'skip' (don't overwrite) or 'overwrite'.

    Accepts `{"services": {...}}` (preferred) or `{"catalog": {...}}` (alias).
    Intentionally does NOT accept `{"packs": {...}}` — a prompt-pack file
    cross-imported into the service catalog would be a data-model mistake;
    let the 'no services found' error flag it instead.
    """
    services = data.get('services') or data.get('catalog') or {}
    if not isinstance(services, dict):
        return 0
    stored = _load_store()
    imported = 0
    for name, cfg in services.items():
        if not name or not isinstance(cfg, dict):
            continue
        if name in stored and mode == 'skip':
            continue
        existing = stored.get(name) or {}
        stored[name] = {
            "description": cfg.get("description", ""),
            "tags": cfg.get("tags", ""),
            "added_at": existing.get("added_at") or cfg.get("added_at") or time.time(),
        }
        imported += 1
    _save_store(stored)
    return imported

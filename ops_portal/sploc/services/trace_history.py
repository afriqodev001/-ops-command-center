"""
SPLOC trace scrape history — file-backed list of recently scraped traces.

Each entry: { trace_id, service_name, total_spans?, last_used (epoch) }
Newest first; deduplicated by (trace_id, service_name); capped at MAX_ENTRIES.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List, Dict, Optional


_STORE_FILE = Path(__file__).parent.parent / 'trace_history.json'
MAX_ENTRIES = 30


def _load() -> List[Dict]:
    if not _STORE_FILE.exists():
        return []
    try:
        data = json.loads(_STORE_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(entries: List[Dict]) -> None:
    _STORE_FILE.write_text(json.dumps(entries, indent=2), encoding='utf-8')


def add_recent(trace_id: str, service_name: str, total_spans: Optional[int] = None) -> None:
    """Insert (or move to top) a recent trace entry."""
    if not trace_id or not service_name:
        return
    entries = _load()
    entries = [
        e for e in entries
        if not (e.get('trace_id') == trace_id and e.get('service_name') == service_name)
    ]
    entries.insert(0, {
        'trace_id': trace_id,
        'service_name': service_name,
        'total_spans': total_spans,
        'last_used': time.time(),
    })
    _save(entries[:MAX_ENTRIES])


def list_recent(limit: int = 10) -> List[Dict]:
    return _load()[:limit]


def delete_recent(trace_id: str, service_name: str) -> None:
    entries = _load()
    entries = [
        e for e in entries
        if not (e.get('trace_id') == trace_id and e.get('service_name') == service_name)
    ]
    _save(entries)


def clear_recent() -> None:
    _save([])

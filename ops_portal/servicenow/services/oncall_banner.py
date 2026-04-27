"""
Persistent global banner shown above the existing live-mode banner in
base.html. Set by an oncall reviewer when a change requires portal-wide
visibility (e.g. "Auth deploy in progress — login may be intermittent").

Storage: oncall_banner_state.json (gitignored, next to the app dir).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional


_STORE_FILE = Path(__file__).parent.parent / 'oncall_banner_state.json'


def _load() -> Dict[str, Any]:
    if not _STORE_FILE.exists():
        return {}
    try:
        data = json.loads(_STORE_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save(data: Dict[str, Any]) -> None:
    _STORE_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')


def get_active() -> Optional[Dict[str, Any]]:
    """Return active banner dict, or None. Auto-clears expired banners."""
    data = _load()
    if not data or not data.get('active'):
        return None

    expires_at = data.get('expires_at')
    if expires_at and float(expires_at) < time.time():
        _save({})
        return None

    return data


def post(
    *,
    message: str,
    change_number: str = '',
    severity: str = 'warn',
    expires_at: Optional[float] = None,
    posted_by: str = '',
) -> Dict[str, Any]:
    """Post (or update) the active banner."""
    payload = {
        'active': True,
        'message': str(message or '').strip(),
        'change_number': str(change_number or '').strip(),
        'severity': severity if severity in ('info', 'warn', 'danger', 'ok') else 'warn',
        'posted_at': time.time(),
        'expires_at': float(expires_at) if expires_at else None,
        'posted_by': str(posted_by or '').strip(),
    }
    _save(payload)
    return payload


def clear() -> None:
    _save({})

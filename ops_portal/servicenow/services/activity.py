"""
Session-backed activity log.

Collects recent write events (preset saves, template changes, bulk submits,
session transitions, mode flips…) and surfaces them through the header bell.
Events are stored in the user's Django session as a rolling list; no DB.

Event shape:
    {
        'id':       '<timestamp-int>',
        'type':     '<short_type_slug>',
        'title':    '<one-line human summary>',
        'detail':   '<optional extra line>',   # may be ''
        'link':     '<URL>' | '',
        'severity': 'info' | 'success' | 'warning' | 'danger',
        'at':       '<ISO-8601 timestamp>',
        'read':     bool,
    }
"""

from __future__ import annotations
from datetime import datetime
from typing import List, Dict, Any

SESSION_KEY = 'activity'
MAX_EVENTS  = 50

VALID_SEVERITIES = ('info', 'success', 'warning', 'danger')


def _now_iso() -> str:
    return datetime.now().isoformat(timespec='seconds')


def _now_id() -> str:
    return str(int(datetime.now().timestamp() * 1000))


def _list(session) -> List[Dict[str, Any]]:
    return list(session.get(SESSION_KEY, []) or [])


def push(session, *, type: str, title: str, detail: str = '',
         link: str = '', severity: str = 'info') -> None:
    """Prepend a new event to the log (newest first) and trim to MAX_EVENTS."""
    if not hasattr(session, 'get'):
        return
    if severity not in VALID_SEVERITIES:
        severity = 'info'
    event = {
        'id':       _now_id(),
        'type':     type,
        'title':    title,
        'detail':   detail,
        'link':     link,
        'severity': severity,
        'at':       _now_iso(),
        'read':     False,
    }
    events = _list(session)
    events.insert(0, event)
    session[SESSION_KEY] = events[:MAX_EVENTS]
    session.modified = True


def list_all(session) -> List[Dict[str, Any]]:
    return _list(session)


def unread_count(session) -> int:
    return sum(1 for e in _list(session) if not e.get('read'))


def mark_all_read(session) -> None:
    events = _list(session)
    for e in events:
        e['read'] = True
    session[SESSION_KEY] = events
    session.modified = True


def clear(session) -> None:
    session[SESSION_KEY] = []
    session.modified = True

"""
Tiny file-backed user preferences store.

Stores settings the user sets from the Preferences panel. Today that's just
the default data mode, but the shape is ready to grow.
"""

from __future__ import annotations
from typing import Dict, Any
from pathlib import Path
import json

_STORE_FILE = Path(__file__).parent.parent / 'user_preferences.json'

DEFAULTS = {
    'default_data_mode': 'demo',            # 'demo' or 'live'
    'default_group_filter': '',             # assignment_group.parent name applied to list pages
    'browser_idle_timeout_minutes': 30,     # auto-close browser after N minutes of no task activity
    # AI provider config — set once in Preferences, used by all AI features
    'ai_provider': 'tachyon',               # 'none' | 'tachyon' | 'claude' | 'openai'
    'ai_tachyon_preset_slug': 'default',   # which TachyonPreset to use (slug from DB)
    'ai_model': 'gpt5.1',                  # model override (empty = use preset/settings default)
}


def load_preferences() -> Dict[str, Any]:
    if not _STORE_FILE.exists():
        return dict(DEFAULTS)
    try:
        stored = json.loads(_STORE_FILE.read_text(encoding='utf-8'))
    except Exception:
        return dict(DEFAULTS)
    # Merge over defaults so older files get new keys transparently
    return {**DEFAULTS, **(stored or {})}


def save_preferences(new_values: Dict[str, Any]) -> Dict[str, Any]:
    prefs = load_preferences()
    prefs.update(new_values or {})
    _STORE_FILE.write_text(json.dumps(prefs, indent=2), encoding='utf-8')
    return prefs

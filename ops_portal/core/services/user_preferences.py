"""
Tiny file-backed user preferences store.

Portal-wide settings the user sets from the Preferences panel: default data
mode, AI provider config, browser idle timeout. This lives in `core` because
it is cross-cutting infrastructure — multiple feature apps read it.

The JSON file sits at BASE_DIR/user_preferences.json. If only the legacy
location (servicenow/user_preferences.json, from before this store moved into
core) exists, it is read transparently; the next save writes the new path.
"""

from __future__ import annotations
from typing import Dict, Any
from pathlib import Path
import json

# core/services/user_preferences.py -> parents[2] is BASE_DIR (manage.py dir).
_BASE_DIR = Path(__file__).resolve().parents[2]
_STORE_FILE = _BASE_DIR / 'user_preferences.json'
_LEGACY_FILE = _BASE_DIR / 'servicenow' / 'user_preferences.json'

DEFAULTS = {
    'default_data_mode': 'demo',            # 'demo' or 'live'
    'default_group_filter': '',             # assignment_group.parent name applied to list pages
    'browser_idle_timeout_minutes': 30,     # auto-close browser after N minutes of no task activity
    # AI provider config — set once in Preferences, used by all AI features
    'ai_provider': 'tachyon',               # 'none' | 'tachyon' | 'claude' | 'openai'
    'ai_tachyon_preset_slug': 'default',   # which TachyonPreset to use (slug from DB)
    'ai_model': 'gpt5.1',                  # model override (empty = use preset/settings default)
}


def _read_file() -> Dict[str, Any]:
    """Read the prefs JSON, preferring the canonical path and falling back to
    the legacy servicenow location. Returns {} if neither exists or is valid."""
    for path in (_STORE_FILE, _LEGACY_FILE):
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
    return {}


def load_preferences() -> Dict[str, Any]:
    # Merge over defaults so older files get new keys transparently
    return {**DEFAULTS, **_read_file()}


def save_preferences(new_values: Dict[str, Any]) -> Dict[str, Any]:
    prefs = load_preferences()
    prefs.update(new_values or {})
    _STORE_FILE.write_text(json.dumps(prefs, indent=2), encoding='utf-8')
    return prefs

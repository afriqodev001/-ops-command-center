"""
Template context processors.

Injects info available on every page: OS user identity and a snapshot of the
user's saved preferences. Kept minimal — anything view-specific should be
passed in via the view's context instead.
"""

from __future__ import annotations
import getpass
import os


def _os_user_name() -> str:
    try:
        name = getpass.getuser()
    except Exception:
        name = os.environ.get('USERNAME') or os.environ.get('USER') or 'user'
    return name or 'user'


def _initials(name: str) -> str:
    """Two-letter badge from the user name. 'owner' -> 'OW', 'john.doe' -> 'JD'."""
    parts = [p for p in name.replace('_', '.').replace('-', '.').split('.') if p]
    if not parts:
        return (name[:2] or '??').upper()
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def ui_context(request):
    """Available in every template:
        - os_user: { 'name': 'owner', 'initials': 'OW' }
        - user_prefs: dict from user_preferences.json (defaults applied)
    """
    from servicenow.services.user_preferences import load_preferences

    name = _os_user_name()
    try:
        prefs = load_preferences()
    except Exception:
        prefs = {'default_data_mode': 'demo'}

    # AI config visibility (API key presence from settings, provider from preferences)
    from django.conf import settings as dj_settings
    prefs['ai_configured'] = bool(getattr(dj_settings, 'AI_API_KEY', ''))
    # Don't overwrite ai_model from preferences — settings.AI_MODEL is the fallback,
    # prefs['ai_model'] is the user's override (set in Preferences panel)

    # Oncall banner (servicenow app) — None on every page that doesn't have one.
    try:
        from servicenow.services.oncall_banner import get_active as _oncall_banner_active
        oncall_banner = _oncall_banner_active()
    except Exception:
        oncall_banner = None

    return {
        'os_user':       {'name': name, 'initials': _initials(name)},
        'user_prefs':    prefs,
        'oncall_banner': oncall_banner,
    }

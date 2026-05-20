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
        - installed_features: set of feature-app labels in the active profile
          (drives which sidebar sections render — see ops_portal/profiles.py)
        - plus anything feature apps contribute via registered context
          providers (e.g. servicenow's oncall_banner) — see core/extensions.py
    """
    from core.services.user_preferences import load_preferences
    from core.extensions import collect_context

    name = _os_user_name()
    prefs = load_preferences()

    # AI config visibility (API key presence from settings, provider from preferences)
    from django.conf import settings as dj_settings
    prefs['ai_configured'] = bool(getattr(dj_settings, 'AI_API_KEY', ''))
    # Don't overwrite ai_model from preferences — settings.AI_MODEL is the fallback,
    # prefs['ai_model'] is the user's override (set in Preferences panel)

    # Which feature apps the active profile loaded — the sidebar nav renders
    # an app's section only when its label is in this set.
    from django.apps import apps as _django_apps
    installed_features = {
        label for label in (
            'servicenow', 'tachyon', 'copilot_chat',
            'harness', 'splunk', 'sploc',
        )
        if _django_apps.is_installed(label)
    }

    ctx = {
        'os_user':            {'name': name, 'initials': _initials(name)},
        'user_prefs':         prefs,
        'installed_features': installed_features,
    }
    # Feature apps inject extra page context (e.g. servicenow's oncall banner)
    # via providers registered in their AppConfig.ready().
    ctx.update(collect_context(request))
    return ctx

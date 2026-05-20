"""
Deployment profiles — control which feature apps load per coworker.

Everyone runs the same codebase; the OPS_PROFILE env var selects which
feature apps are active. Django apps are the unit of modularity: dropping
an app drops its URLs, Celery tasks, admin, models/migrations, templates
and static files automatically.

  - 'core' is the shared base (browser/Selenium registry, runners, task
    status views). It always loads and is added directly in settings.py,
    so it is NOT listed in the profiles below.
  - Feature apps depend on core, never the reverse.

Dependency notes — keep profiles valid:
  - servicenow's AI assist (servicenow/services/ai_assist.py) routes to the
    tachyon and copilot_chat apps. Include both whenever a profile has
    servicenow and expects AI features to work.
  - tachyon, copilot_chat, harness, splunk, sploc depend only on core.

Add a profile by adding a key here; no other code change is needed.
"""
from __future__ import annotations

DEFAULT_PROFILE = 'full'

# Feature apps per profile. Order is the INSTALLED_APPS order.
FEATURE_PROFILES: dict[str, list[str]] = {
    # Everything — the maintainer / full install.
    'full': [
        'servicenow',
        'tachyon',
        'copilot_chat',
        'harness',
        'splunk',
        'sploc',
    ],
    # Change-management coworker: ServiceNow + the AI providers it uses.
    'change_mgmt': [
        'servicenow',
        'tachyon',
        'copilot_chat',
    ],
}


def resolve_profile(name: str | None) -> str:
    """Normalise a profile name to a known profile, falling back to default."""
    return name if name in FEATURE_PROFILES else DEFAULT_PROFILE


def feature_apps(name: str | None = None) -> list[str]:
    """Return the feature-app list for a profile. Unknown / empty names
    fall back to DEFAULT_PROFILE."""
    return list(FEATURE_PROFILES[resolve_profile(name)])

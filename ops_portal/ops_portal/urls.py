"""
URL configuration for the ops_portal project.

Feature-app routes are mounted only when the app is part of the active
OPS_PROFILE (see ops_portal/profiles.py). 'core' (dashboard + task status)
always mounts. Admin always mounts.
"""
from django.apps import apps
from django.contrib import admin
from django.urls import include, path

# (url prefix, app label, urlconf module) — mounted only if the app is
# installed in the active profile.
_FEATURE_URLCONFS = [
    ('servicenow/', 'servicenow',   'servicenow.urls'),
    ('tachyon/',    'tachyon',      'tachyon.urls'),
    ('copilot/',    'copilot_chat', 'copilot_chat.urls'),
    ('splunk/',     'splunk',       'splunk.urls'),
    ('sploc/',      'sploc',        'sploc.urls'),
    ('harness/',    'harness',      'harness.urls'),
]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
]

for _prefix, _app_label, _urlconf in _FEATURE_URLCONFS:
    if apps.is_installed(_app_label):
        urlpatterns.append(path(_prefix, include(_urlconf)))

# Local-only URL includes (gitignored). See ops_portal/local_urls.py.
try:
    from .local_urls import urlpatterns as _local_urlpatterns
    urlpatterns += _local_urlpatterns
except ImportError:
    pass

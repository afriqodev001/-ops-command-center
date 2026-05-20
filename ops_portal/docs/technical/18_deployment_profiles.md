# Deployment Profiles

Profiles control **which feature apps load**, so each coworker can run a
tailored subset of the portal from one shared codebase. A teammate who only
does change management runs ServiceNow + the AI apps; they never see Splunk,
SPLOC or Harness.

One repo, one codebase — bug fixes and features propagate to everyone. The
"split" is configuration, not forked code.

## How it works

- The `OPS_PROFILE` env var selects a profile (default `full`).
- `ops_portal/profiles.py` defines `FEATURE_PROFILES` — a profile name → list
  of feature apps.
- `settings.py` builds `INSTALLED_APPS` from the active profile.
- `ops_portal/urls.py` mounts an app's routes only when the app is installed.
- `core/context_processors.py` exposes `installed_features` to templates;
  `base.html` renders a sidebar section only for installed apps.
- Celery task discovery, migrations, admin, templates and static files all
  follow `INSTALLED_APPS` — dropping an app drops all of it automatically.

`core` is the shared base (browser/Selenium registry, runners, task-status
views, dashboard shell). It **always loads**. Feature apps depend on core,
never the reverse.

## Built-in profiles

| Profile       | Feature apps |
|---------------|--------------|
| `full`        | servicenow, tachyon, copilot_chat, harness, splunk, sploc |
| `change_mgmt` | servicenow, tachyon, copilot_chat |

## Running a profile

Set `OPS_PROFILE` in `.env` (repo root) or the environment:

```
OPS_PROFILE=change_mgmt
```

Then, as normal:

```bash
python manage.py migrate      # only the active profile's tables get created
python manage.py runserver
celery -A ops_portal worker -P solo -l info
```

A coworker on `change_mgmt` sees only Change Management + the AI providers.
Splunk/SPLOC/Harness routes return 404, their sidebar sections don't render,
their Celery tasks aren't registered, and their DB tables never exist.

## Adding a profile

Add one key to `FEATURE_PROFILES` in `ops_portal/profiles.py` — nothing else:

```python
FEATURE_PROFILES = {
    ...
    'observability': ['splunk', 'sploc'],
}
```

## Dependency rules

Keep profiles valid:

- `servicenow`'s AI assist (`servicenow/services/ai_assist.py`) routes to the
  `tachyon` and `copilot_chat` apps. Include **both** in any profile that has
  `servicenow` and expects AI features to work.
- `tachyon`, `copilot_chat`, `harness`, `splunk`, `sploc` depend only on `core`.
- The rich dashboard currently lives in the `servicenow` app. A profile
  without `servicenow` falls back to a minimal `core` landing page
  (`core/templates/core/fallback_dashboard.html`).

## Adding a new app (profile-aware)

When you add an integration (see `16_adding_integration.md`), also wire it
into the profile system:

1. Add the app label to the relevant entries in `FEATURE_PROFILES`
   (`ops_portal/profiles.py`).
2. Add a `(prefix, app_label, urlconf)` row to `_FEATURE_URLCONFS`
   in `ops_portal/urls.py`.
3. Add the app label to the `installed_features` set in
   `core/context_processors.py`.
4. Wrap the app's `base.html` sidebar section in
   `{% if '<app_label>' in installed_features %}` … `{% endif %}`.

## Verifying

```bash
python manage.py check
OPS_PROFILE=change_mgmt python manage.py check
```

Both must pass. To see which routes a profile mounts:

```bash
OPS_PROFILE=change_mgmt python manage.py show_urls   # if django-extensions
```

## Checklist (new profile)

- [ ] Key added to `FEATURE_PROFILES`
- [ ] Dependency rules respected (AI apps included where servicenow uses AI)
- [ ] `manage.py check` passes with `OPS_PROFILE=<new>`
- [ ] Sidebar shows only the intended sections

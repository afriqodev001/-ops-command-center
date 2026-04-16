# Project Structure

## Top-level layout

```
ops-command-center/
├── .venv/                       # Python virtualenv
├── requirements.txt
└── ops_portal/                  # Django BASE_DIR (manage.py here)
    ├── manage.py
    ├── db.sqlite3
    ├── staticfiles/             # collectstatic output (gitignored)
    ├── static/                  # project-level static assets
    ├── templates/               # project-level templates
    │   └── base.html            # ⟵ every page extends this
    ├── docs/
    │   ├── user_guide/          # end-user docs
    │   └── technical/           # this directory
    ├── ops_portal/              # Django project config
    │   ├── settings.py
    │   ├── urls.py
    │   └── ...
    ├── core/                    # Shared infra (browser registry, task views)
    │   ├── browser/
    │   │   └── registry.py      # Session persistence
    │   ├── runners/
    │   │   └── task_views.py    # /tasks/<id>/status|result/
    │   └── urls.py
    └── servicenow/              # The main app
        ├── urls.py
        ├── pages.py             # HTML views (UI pages + HTMX partials)
        ├── views.py             # JSON API views (→ Celery tasks)
        ├── tasks.py             # All @shared_task definitions
        ├── services/            # Pure-Python services (no Django)
        │   ├── query_presets.py
        │   ├── creation_templates.py
        │   ├── bulk_change_parser.py
        │   └── standard_change_templates.py  # legacy, migrated
        ├── user_presets.json    # User-authored presets
        ├── creation_templates.json  # User-authored templates
        └── templates/
            └── servicenow/
                ├── incidents.html, changes.html, ...  # full pages
                └── partials/     # HTMX swap fragments
```

## Naming conventions

### URL path segments
- Feature root: `/servicenow/<feature>/`
- Sub-actions: `/servicenow/<feature>/<action>/` (e.g. `/presets/save/`, `/templates/delete/`)
- HTMX partial endpoints: typically live under the same feature root; discriminated by verb or path segment (`/changes/bulk-create/preview/`).
- **Fixed-segment routes must come before `<str:number>` catch-alls.** See `urls.py` — `changes/bulk-review/` and `changes/bulk-create/` appear before `changes/<str:number>/`.

### View names
| View type              | Location     | Suffix / form                        |
| ---------------------- | ------------ | ------------------------------------ |
| Full-page GET          | `pages.py`   | `<feature>_page` or `<feature>`      |
| HTMX partial POST      | `pages.py`   | `<feature>_<action>` (`preset_save`) |
| JSON API → Celery      | `views.py`   | `<feature>_<action>` (`changes_create`) |
| Celery task            | `tasks.py`   | `<feature>_<action>_task`            |

### Template names
| Kind                  | Location                              |
| --------------------- | ------------------------------------- |
| Full page             | `templates/servicenow/<feature>.html` |
| HTMX swap partial     | `templates/servicenow/partials/<name>.html` |
| Result/status partial | `templates/servicenow/partials/<feature>_result.html` or similar |

### Django blocks (defined in `base.html`)
| Block                | Purpose |
| -------------------- | ------- |
| `title`              | Document title |
| `page_title`         | H1 in the top bar |
| `page_subtitle`      | Gray subtitle below the H1 |
| `header_actions`     | Right-side buttons in the top bar |
| `content`            | Main page body |
| `modals`             | Page-specific dialogs (appended to body) |
| `extra_head`         | Extra `<head>` content |
| `extra_js`           | Extra end-of-body JS |

## Service layer (`servicenow/services/`)

Pure-Python modules — no Django imports at module scope. Used by both `pages.py` and `views.py` / `tasks.py`.

| Service file                 | Role |
| ---------------------------- | ---- |
| `query_presets.py`           | Built-in preset registry + user preset load/save; `render_preset()` turns a preset into a concrete Table API operation. |
| `creation_templates.py`      | Unified write-side template store (4 kinds), URL builder for standard changes. |
| `bulk_change_parser.py`      | CSV/paste parser + validator for Bulk Change Create. |
| `search_presets.py`          | Shortcuts for the Search page — long CI values behind a short App ID + optional group/requester defaults. |
| `user_preferences.py`        | File-backed user preferences (currently: default data mode). |
| `activity.py`                | Session-backed activity log (rolling 50 events): `push`, `list_all`, `unread_count`, `mark_all_read`, `clear`. |
| `standard_change_templates.py` | Legacy — kept for the migration read on first load of the unified store. |

### Template context processor

`core/context_processors.py` → `ui_context(request)` is registered in `settings.TEMPLATES.OPTIONS.context_processors`. It injects two globals on every template render:

- `os_user` → `{'name': 'owner', 'initials': 'OW'}` — from `getpass.getuser()` with env-var fallback.
- `user_prefs` → merged `DEFAULTS` + contents of `user_preferences.json`.

Use these in `base.html` for the sidebar user block and in any partial that wants to display the current defaults without threading a view-side context.

Rule of thumb: anything you'd want to unit-test *without* spinning up Django belongs here.

## File-backed stores

Two JSON files hold user-authored content:

| File                                          | Shape                      | Written by                          |
| --------------------------------------------- | -------------------------- | ----------------------------------- |
| `servicenow/user_presets.json`                | `{ name: {cfg} }`          | `query_presets.save_user_preset`    |
| `servicenow/creation_templates.json`          | `{ key: {kind, label, ...} }` | `creation_templates.save_template`  |
| `servicenow/search_presets.json`              | `{ key: {app_id, label, cmdb_ci, ...} }` | `search_presets.save_preset` |
| `servicenow/user_preferences.json`            | `{ default_data_mode: "demo" | "live", ... }` | `user_preferences.save_preferences` |

All four are safe to diff, commit (optionally), and edit by hand. No locking — these are single-user files today.

## Demo data

List pages currently render from inline constants in `pages.py`:

```python
DEMO_INCIDENTS = [ {...} for each incident ]
DEMO_CHANGES   = [ {...} for each change ]
```

An enrichment block immediately below those adds fields used by newer features (`cmdb_ci`, `opened_by`) via `setdefault` so the original dicts aren't touched. See [Demo Data](10_demo_data.md).

## Where to put new code

| You want to add…                                    | Put it in |
| --------------------------------------------------- | --------- |
| A new UI page                                       | `pages.py` view + `templates/servicenow/<feature>.html` |
| A new HTMX partial endpoint                         | `pages.py` view + `templates/servicenow/partials/<name>.html` |
| A new write/create call to ServiceNow               | `tasks.py` (as Celery task) + `views.py` (JSON trigger) |
| Parsing / validation / pure business logic          | `services/<feature>.py` |
| A new user-authored content store                   | New JSON file next to existing ones + a service module |

## See also
- [Architecture](01_architecture.md)
- [Adding a Feature](11_adding_a_feature.md)

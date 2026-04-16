# Ops Command Center — Technical Guide

Developer-oriented documentation covering architecture, patterns, and feature internals. Pair this with the [User Guide](../user_guide/index.md) for the end-user-facing view.

## Contents

**Foundations**
1. [Architecture](01_architecture.md) — stack, layers, and request lifecycle
2. [Project Structure](02_project_structure.md) — where things live and why
3. [Frontend Patterns](03_frontend_patterns.md) — HTMX + Alpine + Tailwind conventions and pitfalls

**Backend layers**
4. [Session Management](04_session_management.md) — ServiceNow browser registry, PID tracking
5. [Celery Tasks](05_celery_tasks.md) — async task layer conventions
6. [Table API Integration](06_table_api.md) — how we talk to ServiceNow

**Feature deep-dives**
7. [Presets](07_feature_presets.md) — query preset system
8. [Creation Templates](08_feature_templates.md) — unified template store + create flow
9. [Bulk and Search Flows](09_feature_bulk_and_search.md) — bulk review, bulk create, search, fetch
10. [Demo Data](10_demo_data.md) — seeded records and enrichment

**Playbooks**
11. [Adding a Feature](11_adding_a_feature.md) — end-to-end walkthrough

## Terminology

| Term           | Meaning |
| -------------- | ------- |
| **Session**    | A persistent ServiceNow browser connection owned by the user, tracked by PID + profile dir. |
| **Data mode**  | Per-user flag (`demo` or `live`) stored in Django session. Governs whether read views return seeded demo records or hit live ServiceNow. See [Demo Data](10_demo_data.md#data-mode-toggle-demo-vs-live). |
| **Table API**  | ServiceNow's `/api/now/table/<table>` REST endpoint — our primary write path. |
| **Preset**     | A *read* (list) query saved in `user_presets.json` or shipped built-in. |
| **Template**   | A *write* (create) payload saved in `creation_templates.json`. |
| **Search preset** | A filter-value shortcut for the Search page, saved in `search_presets.json`. Different from a query preset — see the note on [Presets](07_feature_presets.md). |
| **Activity log** | Session-backed rolling list of recent write events surfaced by the header bell. See `services/activity.py` and the `_push_activity` wrapper in `pages.py`. |
| **hx-boost**   | HTMX attribute that intercepts navigation and swaps `<body>` content. Several Alpine gotchas stem from this. |
| **Partial**    | A template fragment returned for HTMX swaps — lives in `templates/servicenow/partials/`. |

## Conventions referenced throughout

- All file paths in these docs are relative to the project root: `ops-command-center/ops_portal/`.
- URL patterns use the `/servicenow/…` namespace; routes are registered in `servicenow/urls.py`.
- Alpine components register via `Alpine.data('name', factory)` inside an `alpine:init` listener — never as plain inline functions (see [Frontend Patterns](03_frontend_patterns.md)).

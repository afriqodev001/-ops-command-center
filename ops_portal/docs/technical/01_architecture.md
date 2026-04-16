# Architecture

## Stack

| Layer       | Tech                                                     |
| ----------- | -------------------------------------------------------- |
| Backend     | Django 6.0.4 (Python)                                    |
| Async       | Celery (task broker + worker)                            |
| Browser     | Selenium/Playwright session registry (`core/browser/`)   |
| UI shell    | Server-rendered Django templates                         |
| Interactivity | HTMX 2.x (partial swaps) + Alpine.js 3.x (local state) |
| Styling     | Tailwind CSS (CDN runtime)                               |
| Data store  | File-backed JSON stores (`user_presets.json`, `creation_templates.json`) for user-authored content; demo data inlined in `pages.py` |
| External    | ServiceNow REST Table API via authenticated browser session |

No React, no SPA routing, no WebSockets. Every interactive surface is a partial HTML fragment returned from a Django view and swapped into place by HTMX.

## Layered diagram

```
┌──────────────────────────────────────────────────────────────┐
│  Browser                                                     │
│   ┌────────────────────┐  ┌───────────────────┐              │
│   │ HTMX (navigation,  │  │ Alpine.js (local  │              │
│   │ partial swaps)     │  │ reactive state)   │              │
│   └─────────┬──────────┘  └─────────┬─────────┘              │
│             │                       │                        │
│             └─────────┬─────────────┘                        │
└───────────────────────┼──────────────────────────────────────┘
                        │ HTTP (form / JSON / multipart)
                        ▼
┌──────────────────────────────────────────────────────────────┐
│  Django — servicenow/                                        │
│   ┌──────────────────┐   ┌──────────────────┐                │
│   │ pages.py         │   │ views.py         │                │
│   │ (HTML + HTMX)    │   │ (JSON API)       │                │
│   └────┬─────────────┘   └────┬─────────────┘                │
│        │                       │                             │
│        ▼                       ▼                             │
│   ┌──────────────────┐   ┌──────────────────┐                │
│   │ services/        │   │ tasks.py         │                │
│   │ (parsers, stores)│   │ (Celery async)   │                │
│   └──────────────────┘   └────┬─────────────┘                │
└─────────────────────────────────┼────────────────────────────┘
                                  │ via session + auth retry
                                  ▼
┌──────────────────────────────────────────────────────────────┐
│  ServiceNow Table API                                        │
└──────────────────────────────────────────────────────────────┘
```

## Typical request shapes

### 1. HTML page (GET)
```
Browser ── hx-boost nav ──▶ Django URL route
                              ▼
                            pages.py view
                              ▼
                            render(template)
                              ▼
                         Full HTML body (swapped by HTMX,
                         scripts re-executed, Alpine re-inits)
```

### 2. Partial swap (HTMX POST/GET)
```
Browser ── hx-post ──▶ URL route
                          ▼
                       pages.py view
                          ▼
                       render(partial)
                          ▼
                    <div> fragment swapped into hx-target
```

### 3. Async write (JSON API)
```
Browser ── fetch POST ──▶ views.py view
                              ▼
                          task.delay(body)
                              ▼
                    JsonResponse({ task_id })
                              │
                              ▼
Browser polls /tasks/<id>/result/ every 2s
                              │
                              ▼
               ┌─ Celery worker completes
               │         ▼
               │   Selenium driver + session auth
               │         ▼
               │   ServiceNow Table API
               │         ▼
               └── result.result = { record: {...} }
                              ▼
                  Browser updates run-details UI
```

## Two view modules

The codebase splits views by response type:

| File            | Response | Typical usage |
| --------------- | -------- | ------------- |
| `pages.py`      | HTML (full page or partial fragment) | All UI routes — list pages, detail pages, HTMX partials, modal fragments |
| `views.py`      | JSON (202 Accepted with task id, or 200 with result) | API endpoints the frontend calls with `fetch()` (e.g. bulk submit, task dispatch) |

Keep this separation strict — mixing HTML and JSON in one view quickly gets confusing, especially with HTMX's response-header conventions (`HX-Redirect`, `HX-Retarget`).

## Data flow: demo mode vs. live mode

Every user has a **data mode** flag in their Django session: `demo` (default) or `live`. A chip in the top bar of every page toggles between them; `POST /servicenow/mode/toggle/` flips the flag and issues an `HX-Refresh` so every template re-renders with the new mode.

### Read paths
Go through mode-aware helpers in `pages.py` — `_incidents_source(request)`, `_changes_source(request)`, `_get_incident_modal(request, number)`, `_get_change_modal(request, number)`. Today:

- **demo** → returns the inline `DEMO_INCIDENTS` / `DEMO_CHANGES` constants
- **live** → returns empty (the sync Table API wrapper isn't wired yet); a global banner in `base.html` explains this to the user

When you're ready, wire live reads by editing only the helper bodies — every read view already calls through them and threads `request` through. See [Demo Data](10_demo_data.md#migrating-off-demo-data) for the walkthrough.

### Write paths
Go to the Table API via Celery tasks (`changes_create_task`, `incidents_create_task`). These do **not** respect the mode toggle — they always hit ServiceNow if a session is connected. The rationale: create flows are used in real workflows even during UI demos, and the session widget is the right gate for "are we connected?"

## Key architectural decisions

| Decision                                      | Why |
| --------------------------------------------- | --- |
| HTMX + Alpine over SPA                        | Keeps server as source of truth; avoids duplicating domain logic in JS. Alpine provides enough local reactivity for modals, toggles, and form state. |
| File-backed JSON (not DB) for user content    | Presets and templates are few-to-dozens, rarely written. File storage is diffable, exportable, trivially auditable. |
| Celery for write operations                   | Table API calls can be slow or stall on auth — returning a task id lets the UI show progress without blocking. |
| Split `pages.py` / `views.py`                 | Keeps HTML-returning and JSON-returning handlers from tangling their response conventions. |
| `Alpine.data('name', factory)` registration   | Survives `hx-boost` re-navigation cleanly; plain `function presetsPage()` inline definitions race with Alpine's MutationObserver. |
| `json_script` over raw `{{ json_dump }}`      | Prevents Django auto-escape from corrupting JSON inside `<script>` tags (raw-text elements don't decode entities). |

## See also
- [Project Structure](02_project_structure.md)
- [Frontend Patterns](03_frontend_patterns.md)
- [Celery Tasks](05_celery_tasks.md)

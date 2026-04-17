# Celery Tasks

All ServiceNow write operations and any operation that might block (attachments, bulk reads) run through Celery.

## Why async
- Table API calls go through a browser session that may need to re-auth (seconds to tens of seconds).
- A blocked HTTP handler is a frozen UI.
- We want per-row progress in bulk flows.
- In live mode, **every read page** also dispatches tasks via `.delay()` — the view renders a loading placeholder instantly and polls via HTMX until the task completes. This keeps pages responsive even on slow instances.

## Task catalog

All tasks live in `servicenow/tasks.py`. Naming: `<feature>_<action>_task`.

| Task                              | Trigger                          | Purpose |
| --------------------------------- | -------------------------------- | ------- |
| `servicenow_login_open_task`      | `views.servicenow_login_open`    | Open headed ServiceNow login |
| `changes_get_task`                | `views.changes_get`              | Fetch a change by sys_id |
| `changes_patch_task`              | `views.changes_patch`            | PATCH a change |
| `changes_create_task`             | `views.changes_create` (bulk-create, create-from-template) | Create normal/emergency change |
| `changes_get_by_number_task`      | `views.changes_get_by_number`    | Look up change by CHG number |
| `changes_bulk_get_by_number_task` | `views.changes_bulk_get_by_number` | Batch look-up |
| `incidents_get_task`              | `views.incidents_get`            | Fetch incident by sys_id |
| `incidents_patch_task`            | `views.incidents_patch`          | PATCH incident |
| `incidents_create_task`           | `views.incidents_create` (create-from-template) | Create incident |
| `incident_get_by_field_task`      | `views.incidents_get_by_field`   | Find incident by arbitrary field |
| `incident_bulk_get_by_field_task` | `views.incidents_bulk_get_by_field` | Batch |
| `table_list_task`                 | `views.table_list`               | Generic Table API list query |
| `table_get_by_field_task`         | `views.table_get_by_field`       | Generic single lookup |
| `table_bulk_get_by_field_task`    | `views.table_bulk_get_by_field`  | Generic bulk lookup |
| `attachments_list_task`           | `views.attachments_list`         | List attachments for a record |
| `ctasks_list_for_change_task`     | `views.ctasks_list_for_change`   | List CTASKs for a change |
| `change_context_task`             | `views.changes_context`          | Build change review context |
| `incident_context_task`           | `views.incidents_context`        | Build incident context |
| `presets_list_task`               | `views.presets_list`             | List available presets (API) |
| `presets_run_task`                | `views.presets_run`              | Execute a preset by name |
| `incident_presets_list_task`      | `views.incidents_presets_list`   | Incident-only presets list |
| `incident_presets_run_task`       | `views.incidents_presets_run`    | Incident-only preset run |

## Task body shape

Every task takes a single `body: dict` and returns a dict. Common shape:

```python
{
    "user_key": "localuser",            # selects session
    "kind":     "normal" | "emergency", # for polymorphic tasks
    "sys_id":   "<record sys_id>",      # for *_get / *_patch
    "fields":   { ... },                # payload for create/patch
    # ...
}
```

Return shape:

```python
# success
{ "status": "ok", "record": { ... } }   # or just the record fields

# error
{ "error": "missing_parameter",
  "detail": "human-readable",
  "example": { ... } }
```

Errors are **returned values**, not exceptions — the caller (`views.py`) just passes them to the client via `task_result`. This keeps Celery state as SUCCESS with a machine-readable error payload.

## Task skeleton

```python
from celery import shared_task
from ._auth import with_servicenow_auth_retry
from ._ops import some_operation_that_uses_driver

@shared_task(bind=True)
def my_feature_task(self, body: dict):
    body = body or {}
    # ── validate inputs, early-return error dicts ──────────
    if not body.get('required_field'):
        return {
            "error":   "missing_parameter",
            "detail":  "required_field is required",
            "example": {"required_field": "<value>"},
        }

    # ── the actual operation, wrapped in auth-retry ────────
    def op(driver):
        return some_operation_that_uses_driver(driver, body)

    return with_servicenow_auth_retry(body=body, operation=op, retry_once=True)
```

Key points:
- `bind=True` gives access to `self.request.id` etc. if needed.
- Validate and early-return *before* touching a driver — bad inputs shouldn't burn a Selenium session.
- Always wrap driver-facing work in `with_servicenow_auth_retry`.

## Dispatching from a view

### JSON API (frontend polls via `task_result`)

```python
# views.py
@csrf_exempt
@require_POST
def changes_create(request):
    task = changes_create_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)
```

The frontend keeps the task id and polls:

```javascript
const resp  = await fetch(`/tasks/${taskId}/result/`);
const data  = await resp.json();
// data = { task_id, state, ready, result?: {...}, error?: "..." }
```

### From a page view — live-mode read (HTMX live_poll flow)

```python
# pages.py — e.g. incidents_list (live branch)
from .tasks import table_list_task

task = table_list_task.delay({...query...})
return render(request, 'servicenow/incidents.html', {
    'live_task_id': task.id,
    ...filters for the form...
})
```

The template renders a `live_loading.html` placeholder div; HTMX polls `/servicenow/live/poll/incidents-list/<task_id>/` every 2s. The endpoint returns `204` while pending, the rendered rows partial on success, or an error partial on failure.

### From a page view — write (Alpine polling)

```python
# pages.py — e.g. create_from_template_submit
from .tasks import changes_create_task

task = changes_create_task.delay({'kind': 'normal', 'fields': fields})
return render(request, 'servicenow/partials/create_from_template_result.html', {
    'task_id': task.id,
    'kind':    kind,
}, status=200)
```

The result partial contains an Alpine `taskWatcher` component that polls `/tasks/<id>/result/` and updates the UI in place.

## Task polling endpoints

Defined in `core/runners/task_views.py`:

| Route                           | Returns |
| ------------------------------- | ------- |
| `GET /tasks/<id>/status/`       | `{ task_id, state, ready }` — cheap liveness check |
| `GET /tasks/<id>/result/`       | Same plus `result` (if ready) or `error` (if FAILURE) |

State values match Celery's: `PENDING`, `STARTED`, `SUCCESS`, `FAILURE`.

## Error handling convention

The JS polling pattern recognizes three failure shapes:

```javascript
// Celery task raised — result.state === 'FAILURE'
if (data.state === 'FAILURE') { /* show data.error */ }

// Task succeeded but the operation returned an error dict
const result = data.result || {};
if (result.error) { /* show result.detail || result.error */ }

// Normal success
// result has { record: {...} } or similar
```

Keep `result.error` + `result.detail` + `result.example` consistent across tasks so the UI can show human-readable errors without special-casing.

## Adding a new task

1. Add the operation function in the appropriate module (if new).
2. Add the `@shared_task` in `tasks.py` with validation + auth retry.
3. Export it at module scope so `views.py` can import.
4. Add an import in `views.py`'s big `from .tasks import (...)` block.
5. Add a thin `@csrf_exempt @require_POST` view that dispatches the task.
6. Add the URL route in `servicenow/urls.py`.
7. Frontend: use the polling pattern in [Frontend Patterns](03_frontend_patterns.md#polling-for-celery-task-results).

## Gotchas

- **Return, don't raise, for user-facing errors.** Raising causes `state=FAILURE` with a stringified traceback, which is ugly in UI. Reserve exceptions for genuine bugs.
- **`task.delay()` needs the Celery worker to be running.** If the UI shows perpetual "pending," the worker is probably down.
- **`bind=True` is required if you need task metadata**, but unused otherwise. No harm in always setting it.
- **Body dicts must be JSON-serializable.** No datetimes, no custom classes. Pass strings and convert inside the task.

## See also
- [Session Management](04_session_management.md) — session resolution + auth retry
- [Table API](06_table_api.md) — where tasks ultimately land

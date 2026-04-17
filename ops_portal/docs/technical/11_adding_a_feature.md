# Adding a Feature — Playbook

A step-by-step checklist for adding a new feature to the Ops Command Center, illustrated with a concrete example.

## Example feature: "Problem Records" page

Let's say we want to add a list + search view for ServiceNow problem records — similar to Incidents but pointed at the `problem` table.

## Checklist

- [ ] 1. Sketch the UI + data flow (don't skip this)
- [ ] 2. Add demo data if running offline
- [ ] 3. Create view(s) in `pages.py`
- [ ] 4. Add URL route(s)
- [ ] 5. Create the page template
- [ ] 6. Create HTMX partials (if any)
- [ ] 7. Add sidebar nav entry in `base.html`
- [ ] 8. For write operations: add `tasks.py` task, `views.py` dispatcher, frontend polling
- [ ] 9. Update docs (both user + technical)

## 1. Sketch the flow

Problems list page:
- Filters: state, priority, search
- Rows link to detail page (`/problems/<number>/`)
- Detail shows summary + related incidents

Keep it consistent with incidents/changes. Reuse whatever patterns work.

## 2. Demo data

In `pages.py`, next to `DEMO_INCIDENTS` and `DEMO_CHANGES`:

```python
DEMO_PROBLEMS = [
    {
        'sys_id': 'prb001',
        'number': 'PRB0012345',
        'short_description': 'Recurring DB connection pool exhaustion',
        'state': 'Open',
        'priority': '2',
        'assignment_group': 'Database Ops',
        'related_incidents': ['INC0045231', 'INC0045228'],
    },
    # ...
]
```

Add any enrichment (CI, requester) if the Search page should cover problems too:

```python
for _p in DEMO_PROBLEMS:
    _p.setdefault('cmdb_ci', '')
    _p.setdefault('opened_by', '')
```

## 3. View(s) in `pages.py`

```python
def problems_list(request):
    state_filter = request.GET.get('state', '')
    search = request.GET.get('q', '').lower()

    records = DEMO_PROBLEMS
    if state_filter:
        records = [r for r in records if r['state_code'] == state_filter]
    if search:
        records = [r for r in records
                   if search in r['short_description'].lower()
                   or search in r['number'].lower()]

    return render(request, 'servicenow/problems.html', {
        'problems':      records,
        'state_filter':  state_filter,
        'search':        search,
        'total':         len(records),
    })


def problem_detail(request, number):
    prob = next((p for p in DEMO_PROBLEMS if p['number'] == number), None)
    if not prob:
        from django.http import Http404
        raise Http404
    return render(request, 'servicenow/problem_detail.html', {'problem': prob})
```

## 4. URL routes

In `servicenow/urls.py` — **fixed segments before `<str:number>` catch-alls**:

```python
path("problems/",                 pages.problems_list,    name="problems-list"),
path("problems/<str:number>/",    pages.problem_detail,   name="problem-detail"),
```

If you add any HTMX partial endpoints (e.g. `problems/search/preview/`), put them under the same feature root and register them before the `<str:number>` line.

## 5. Page template

`servicenow/templates/servicenow/problems.html`:

```django
{% extends 'base.html' %}
{% block title %}Problems — Ops Center{% endblock %}
{% block page_title %}Problems{% endblock %}
{% block page_subtitle %}ServiceNow · {{ total }} record{{ total|pluralize }}{% endblock %}

{% block header_actions %}
  <!-- optional: buttons -->
{% endblock %}

{% block content %}
<div class="space-y-4 animate-fade-in">
  <!-- state tabs + search -->
  <!-- results table -->
</div>
{% endblock %}
```

Copy incidents.html as a starting point — same block structure, swap the fields.

## 6. Partials

If the page has any HTMX swaps (e.g. an inline search that doesn't reload the page), add partials under `partials/`:

```
servicenow/templates/servicenow/partials/problem_search_results.html
```

## 7. Sidebar nav

In `templates/base.html`, inside the ServiceNow section:

```html
<a href="/servicenow/problems/"
   class="{% if '/servicenow/problems' in request.path %}nav-item-active{% else %}nav-item{% endif %}">
  <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
          d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
  </svg>
  Problems
</a>
```

## 8. Write paths (only if the feature creates/edits)

1. **Task** in `tasks.py`:
```python
@shared_task(bind=True)
def problems_create_task(self, body: dict):
    body = body or {}
    fields = body.get('fields')
    if not fields:
        return {"error": "missing_parameter", "detail": "fields required"}

    def op(driver):
        return create_problem_via_table_api(driver, fields=fields)
    return with_servicenow_auth_retry(body=body, operation=op, retry_once=True)
```

2. **Dispatcher** in `views.py`:
```python
@csrf_exempt
@require_POST
def problems_create(request):
    task = problems_create_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)
```

3. **URL route**:
```python
path("problems/create/", views.problems_create),
```

4. **Frontend** — use the polling pattern from [Frontend Patterns](03_frontend_patterns.md#polling-for-celery-task-results).

## 9. Docs

Two entries:

- **User guide** — `docs/user_guide/<NN>_problems.md`. Follow the skeleton of existing guides (path, when to use, layout diagram, how to use, examples, tips, see-also).
- **Technical guide** — if the feature warrants its own deep-dive, add `docs/technical/<NN>_feature_problems.md`. If it's just another list page, a note in an existing guide is enough.

Update both index files (`index.md`) to link to new entries.

### Adding a live-mode read surface

Every new read page needs a live branch. The pattern:

1. **Extract the body partial** — move the content block's data-rendering markup into `partials/<feature>_body.html`. The parent template includes it (demo) or shows a placeholder (live).
2. **Dispatch the task** — in the view, `if _is_live(request): task = table_list_task.delay({...}); render page with live_task_id`.
3. **Register a shape renderer** — add a function to `LIVE_POLL_RENDERERS` in `pages.py` that adapts the task payload and renders the body partial.
4. **Template conditional** — `{% if live_task_id %}{% include 'live_loading.html' with shape='...' %}{% else %}{% include 'partials/..._body.html' %}{% endif %}`.

The generic `live_poll` endpoint handles everything else (pending → 204, failure → error partial, success → your renderer).

## Common traps

### Forgetting URL order
Adding `problems/<str:number>/` before `problems/search/` will route `search` to the detail handler. Always put fixed paths first.

### Using inline `<script>` definitions for Alpine components
See [Frontend Patterns](03_frontend_patterns.md#component-registration-pattern). Always register via `Alpine.data('name', factory)` inside `alpine:init`.

### Rendering raw JSON with `{{ }}`
Use `{{ data|json_script:"id" }}` when embedding JSON in `<script>`. Direct `{{ data }}` gets HTML-escaped and fails JSON.parse.

### Duplicating create guards
The session guard (`open-create-incident` listener in `base.html`) stops creates when no session. If you add a new create flow, either reuse one of the existing event names or add a matching listener.

### Status-code confusion
Return `status=200` for user-level validation errors in HTMX flows — HTMX drops 4xx responses by default. Reserve 4xx for genuine protocol failures.

## Minimal viable scaffold

Copy these files as a starting point for a new list feature:

- `templates/servicenow/incidents.html` → strip columns, rename variables
- `pages.incidents_list` / `pages.incident_detail` → copy + rename
- `urls.py` entries for incidents → copy + rename

About 80% of a new list feature is boilerplate you can lift from the adjacent feature.

## See also
- [Architecture](01_architecture.md)
- [Project Structure](02_project_structure.md)
- [Frontend Patterns](03_frontend_patterns.md)
- [Celery Tasks](05_celery_tasks.md)

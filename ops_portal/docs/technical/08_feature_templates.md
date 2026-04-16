# Feature: Creation Templates

Reusable payloads for *creating* records. Unified across four kinds; consumed from multiple list pages.

## Files

| File | Role |
| ---- | ---- |
| `servicenow/services/creation_templates.py`              | Storage, grouping, URL builder |
| `servicenow/creation_templates.json`                     | User-authored templates |
| `servicenow/services/standard_change_templates.py`       | **Legacy** — read-only for migration |
| `servicenow/pages.py`                                    | Views: manager, save/delete, picker, form, submit |
| `servicenow/templates/servicenow/templates_manage.html`  | Full-page manager |
| `servicenow/templates/servicenow/partials/`              | List, errors, picker, form, result partials |
| `templates/base.html`                                    | Shared `create-from-template-modal` used on incidents/changes list pages |

## Data model

```json
{
    "ssl_renewal": {
        "kind":  "standard_change",
        "label": "SSL certificate renewal",
        "url":   "https://INSTANCE.service-now.com/..."
    },
    "db_patching": {
        "kind":  "normal_change",
        "label": "Monthly DB patching",
        "fields": {
            "short_description": "Monthly DB patching",
            "assignment_group":  "Database Ops",
            "risk":              "moderate"
        }
    },
    "p1_bridge": {
        "kind":  "incident",
        "label": "P1 bridge",
        "fields": {
            "short_description": "P1 - ",
            "priority":          "1",
            "assignment_group":  "Platform"
        }
    }
}
```

Top-level key is the unique template `key`. `kind` discriminates storage + render.

### Kinds

```python
VALID_KINDS = ('standard_change', 'normal_change', 'emergency_change', 'incident')
```

### Per-kind field lists

```python
KIND_FIELDS = {
    'standard_change':  ['short_description', 'assignment_group', 'start_date', 'end_date', 'description'],
    'normal_change':    ['short_description', 'assignment_group', 'start_date', 'end_date', 'risk', 'description'],
    'emergency_change': ['short_description', 'assignment_group', 'start_date', 'end_date', 'risk', 'description'],
    'incident':         ['short_description', 'assignment_group', 'priority',   'category',  'description'],
}
```

These drive what the create-from-template form renders for each kind.

## Service API

| Function                                 | Purpose |
| ---------------------------------------- | ------- |
| `load_templates()`                       | All templates |
| `load_templates_by_kind(kind)`           | Filtered by kind |
| `load_templates_grouped()`               | `{kind: {key: entry}}` — for display |
| `save_template(key, kind, label, url='', fields=None)` | Create/update |
| `delete_template(key)`                   | Remove |
| `build_standard_change_url(template_url, row)` | Append field values as `sysparm_query` |

## Legacy migration

On first read, if `creation_templates.json` doesn't exist *and* `standard_change_templates.json` does, the service auto-copies entries with `kind: "standard_change"` added:

```python
def _migrate_legacy_if_needed():
    if _STORE_FILE.exists() or not _LEGACY_FILE.exists():
        return
    # read legacy, add kind, write new file
```

Idempotent and safe — called from `load_templates()`.

## View surface

| View                             | Route                                           | Purpose |
| -------------------------------- | ----------------------------------------------- | ------- |
| `creation_templates_page`        | `GET /templates/`                                | Full-page manager |
| `creation_template_save`         | `POST /templates/save/`                          | Create/update; uses `HX-Retarget` on success |
| `creation_template_delete`       | `POST /templates/delete/`                        | Remove |
| `create_from_template_picker`    | `GET /templates/picker/<kind>/`                  | Picker partial for one kind |
| `create_from_template_form`      | `GET /templates/form/<key>/`                     | Form partial pre-filled from template |
| `create_from_template_submit`    | `POST /templates/submit/`                        | Dispatches per-kind action |

### Submit dispatch

```python
# pages.create_from_template_submit
if kind == 'standard_change':
    target = build_standard_change_url(tpl['url'], fields)
    return render('...result.html', {'kind', 'url': target, 'label'})

if kind in ('normal_change', 'emergency_change'):
    task = changes_create_task.delay({
        'kind':   'emergency' if kind == 'emergency_change' else 'normal',
        'fields': fields,
    })
    return render('...result.html', {'kind', 'task_id', 'label'})

if kind == 'incident':
    task = incidents_create_task.delay({'fields': fields})
    return render('...result.html', {'kind', 'task_id', 'label'})
```

## Result partial

`create_from_template_result.html` handles three shapes:

1. `{error}` — validation or config error, danger box.
2. `{url}` — standard change; `x-init` opens the URL in a new tab automatically.
3. `{task_id, kind}` — API task; Alpine `taskWatcher` component polls `/tasks/<id>/result/` and shows the created record number with a link.

The `taskWatcher` component registers once (`window._taskWatcherRegistered` guard) so multiple result partials in one session don't re-register.

## Shared modal (`create-from-template-modal`)

Lives in `base.html` so it's available from any page. Component:

```javascript
Alpine.data('createFromTemplateModal', () => ({
  isChange: false,
  currentKind: 'incident',
  handleOpen(detail) {
    const kind = detail && detail.kind;       // 'incident' | 'change'
    this.isChange = (kind === 'change');
    const initial = this.isChange ? 'standard_change' : 'incident';
    document.getElementById('create-from-template-modal').showModal();
    this.loadKind(initial);
  },
  loadKind(kind) {
    this.currentKind = kind;
    window.htmx.ajax('GET', `/servicenow/templates/picker/${kind}/`, {
      target: '#create-template-body', swap: 'innerHTML',
    });
  },
}));
```

Incidents list dispatches `open-from-template` with `{ kind: 'incident' }`. Changes list dispatches `{ kind: 'change' }` — the modal then shows Standard/Normal/Emergency tabs, loading each kind's picker on tab click.

## End-to-end flows

### Creating a normal change from a template

```
Changes list → "New from template" button → $dispatch('open-from-template', {kind:'change'})
  → modal opens, tab defaults to Standard
  → user clicks "Normal" tab → htmx loads /templates/picker/normal_change/
  → user clicks a template → htmx loads /templates/form/<key>/
  → form pre-fills from template.fields
  → user tweaks + submits → /templates/submit/ dispatches changes_create_task
  → result partial polls /tasks/<id>/result/ every 2s
  → on success: CHG number + link to detail page
```

### Creating a standard change from a template

```
... same until form submit ...
  → /templates/submit/ builds sysparm_query URL
  → result partial x-inits and calls window.open(url, '_blank')
  → user completes + saves in ServiceNow tab
  → (no verification — we trust tab close)
```

## Gotchas

### Template form uses pre-zipped fields
Django can't subscript a dict with a variable key (`values[fname]` doesn't work). The view builds `fields_with_values = [(f, defaults.get(f, '')) for f in KIND_FIELDS[kind]]` and the template iterates `{% for fname, fval in fields %}`.

### Keys are global across kinds
`db_patching` can't be both a normal-change and an incident template — `save_template` overwrites in place. Namespace if you need variants (`chg_db_patching`, `inc_db_outage`).

### Popup blockers
The standard-change result partial auto-opens the URL via `x-init="window.open(...)"`. Browsers generally allow this when triggered by a user action (the submit click), but some strict setups will block it. User must allow popups for the site.

### Short-description always required
Enforced in `create_from_template_submit` — regardless of whether the template provides a default. Prevents creating untitled records.

## See also
- [Presets](07_feature_presets.md) — the read-side counterpart
- [Bulk Change Create](09_feature_bulk_and_search.md#bulk-change-create) — reuses standard-change templates per row
- [Celery Tasks](05_celery_tasks.md) — task dispatch mechanics

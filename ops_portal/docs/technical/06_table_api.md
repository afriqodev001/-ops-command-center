# Table API Integration

How the application talks to ServiceNow. The Table API (`/api/now/table/<table>`) is our write path and the primary read path for anything needing live data.

## Request flow

```
pages.py / views.py
    │
    ▼
tasks.py task  ─── body dict ───▶ with_servicenow_auth_retry()
                                       │
                                       ▼
                                 driver fetched from session
                                       │
                                       ▼
                                 operation(driver) runs
                                       │
                                       ▼
                                 Selenium → browser tab → Table API call
                                       │
                                       ▼
                                 Return dict → Celery result
```

## Operations by kind

### List / read (`GET /api/now/table/<table>?sysparm_query=...`)

Backed by `table_list_task`. Body shape:

```python
{
    "table":         "incident" | "change_request" | ...,
    "query":         "encoded query (e.g. priority=1^stateNOT IN6,7)",
    "fields":        "number,short_description,state,...",
    "limit":         25,
    "display_value": True   # return display values instead of sys_ids
}
```

### Get by sys_id (`GET /api/now/table/<table>/<sys_id>`)

Backed by `changes_get_task` / `incidents_get_task`.

### Get by arbitrary field

Backed by `table_get_by_field_task`:

```python
{
    "table":  "change_request",
    "field":  "number",
    "value":  "CHG0034567",
    "fields": "...",
    "display_value": True
}
```

Bulk variant: `table_bulk_get_by_field_task` takes `values: [...]`.

### Create (`POST /api/now/table/<table>`)

Backed by `changes_create_task` / `incidents_create_task`:

```python
{
    "kind":   "normal" | "emergency",   # changes only
    "fields": {
        "short_description": "...",
        "assignment_group":  "<sys_id or name>",
        "start_date":        "YYYY-MM-DD HH:MM",
        "end_date":          "YYYY-MM-DD HH:MM",
        "risk":              "moderate",
        ...
    }
}
```

ServiceNow happily accepts additional fields we haven't listed — pass anything.

### Patch (`PATCH /api/now/table/<table>/<sys_id>`)

Backed by `changes_patch_task` / `incidents_patch_task`:

```python
{
    "sys_id": "<record sys_id>",
    "fields_to_patch": {
        "state": "in_progress",
        "work_notes": "Starting implementation",
    }
}
```

## Encoded query syntax (the `query` field)

ServiceNow's encoded query format. Key operators:

| Operator        | Example                              | Meaning |
| --------------- | ------------------------------------ | ------- |
| `^`             | `a=1^b=2`                            | AND |
| `^OR`           | `a=1^ORa=2`                          | OR |
| `^ORDERBY`      | `...^ORDERBYopened_at`               | Sort ASC |
| `^ORDERBYDESC`  | `...^ORDERBYDESCsys_updated_on`      | Sort DESC |
| `IN`            | `stateIN1,2,3`                       | IN list |
| `NOT IN`        | `stateNOT IN6,7`                     | NOT IN |
| `LIKE`          | `short_descriptionLIKEDB`            | Substring |
| `STARTSWITH`    | `numberSTARTSWITHCHG`                | Prefix |
| `javascript:`   | `sla_due<javascript:gs.now()`        | Server-side JS |

Examples from the shipped preset registry:

```
state=implement^ORDERBYDESCsys_updated_on
priority=1^stateNOT IN6,7^ORDERBYopened_at
state=scheduled^ORstart_dateBETWEENjavascript:gs.beginningOfToday()@javascript:gs.endOfTomorrow()^ORDERBYstart_date
```

Build these by hand from the preset UI or ServiceNow's own list-view breadcrumb copy button.

## Standard change URLs

For standard changes we don't hit the Table API — we open the ServiceNow UI in a new tab. URL builder lives at `creation_templates.build_standard_change_url(template_url, row)`:

```python
def build_standard_change_url(template_url, row):
    # parse template_url
    # merge any existing sysparm_query with a new one built from row fields
    # e.g. short_description=Foo^assignment_group=Bar^start_date=...
    # return re-encoded URL
```

Result:
```
https://INSTANCE.service-now.com/nav_to.do?uri=change_request.do?sys_id=-1
  &sysparm_template=TemplateName
  &sysparm_query=short_description=Foo^assignment_group=Bar^start_date=2026-05-01%2022%3A00
```

Any additional field values are appended with `^` as the separator. Values that are empty strings are dropped.

## display_value convention

Pass `display_value: True` for human-readable output (`"Database Ops"` instead of a sys_id). `False` returns raw sys_ids (useful for downstream API calls). Default through the stack is `True`.

## Response shape

Raw Table API returns:

```json
{
  "result": [ { "sys_id": "...", "number": "...", "...": "..." }, ... ]
}
```

Our operation wrappers typically return `{ "record": result["result"][0] }` for single lookups or `{ "records": result["result"] }` for lists. Check each task's wrapper function for its specific shape.

## Gotchas

### Dates and timezones
Pass strings; ServiceNow interprets them in the instance's timezone. If your users are spread, normalize to UTC on the way out or expose a TZ selector in the UI.

### 160-character short_description limit
Enforced by the validator in `bulk_change_parser.py`. The Table API accepts longer strings but the field truncates — better to reject client-side.

### Assignment group by name vs sys_id
Either works — the API does its own resolution. Names are friendlier for CSV input; sys_ids are unambiguous. If a name resolves to multiple groups, ServiceNow picks one (non-deterministic).

### Empty fields overwrite
When patching, omitting a field leaves it untouched. Sending `""` (empty string) sets it to empty — different semantic. Our `changes_patch_task` takes `fields_to_patch` (explicit dict), so you only pass fields you intend to change.

## See also
- [Celery Tasks](05_celery_tasks.md) — task skeleton + validation patterns
- [Session Management](04_session_management.md) — driver acquisition
- [Feature: Presets](07_feature_presets.md) — how presets render into Table API operations

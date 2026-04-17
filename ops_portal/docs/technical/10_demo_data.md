# Demo Data

The read-side pages (Dashboard, Incidents list/detail, Changes list/detail, Search, Fetch by Number) currently render from inline Python constants in `pages.py`. This lets the whole UI be exercised without a live ServiceNow connection.

## Where it lives

```python
# servicenow/pages.py
DEMO_INCIDENTS = [ {sys_id, number, short_description, priority, state, ...}, ... ]
DEMO_CHANGES   = [ {sys_id, number, short_description, type, state, risk, ctasks, ...}, ... ]
DEMO_STATS     = { open_p1, open_p2, open_incidents, pending_changes, ... }
```

Current count: 6 incidents, 5 changes.

## Record shapes

### Incident
| Field               | Example                                   |
| ------------------- | ----------------------------------------- |
| `sys_id`            | `'inc001'`                                |
| `number`            | `'INC0045231'`                            |
| `short_description` | `'DB connection pool exhausted...'`       |
| `priority`          | `'1'`                                     |
| `priority_label`    | `'P1'`                                    |
| `state`             | `'In Progress'`                           |
| `state_code`        | `'in_progress'`                           |
| `assignment_group`  | `'Database Ops'`                          |
| `assigned_to`       | `'J. Smith'`                              |
| `opened`            | `'2026-04-15 14:32'`                      |
| `age`               | `'1h 23m'`                                |
| `sla_warning`       | `True`                                    |
| `work_notes`        | `[{by, at, text}, ...]`                   |
| `tasks`             | `[{number, description, state, assigned_to}, ...]` |
| `attachments`       | `[{name, size, by, at}, ...]`             |
| `cmdb_ci`           | (added by enrichment) `'prod-db-01'`      |
| `opened_by`         | (added by enrichment) `'Monitoring Bot'`  |
| `_opened_dt`        | (added by enrichment) parsed `datetime` from `opened` — used by the time-range filter |

### Change
| Field               | Example                                      |
| ------------------- | -------------------------------------------- |
| `sys_id`            | `'chg001'`                                   |
| `number`            | `'CHG0034567'`                               |
| `short_description` | `'Monthly OS patching...'`                   |
| `type`              | `'Normal'`                                   |
| `state`             | `'Implement'`                                |
| `state_code`        | `'implement'`                                |
| `risk`              | `'Moderate'`                                 |
| `assignment_group`  | `'Platform'`                                 |
| `assigned_to`       | `'J. Smith'`                                 |
| `scheduled`         | `'2026-04-15 22:00 UTC'`                     |
| `ctasks`            | `[{number, description, state, assigned_to}, ...]` |
| `attachments`       | `[...]`                                      |
| `work_notes`        | `[...]`                                      |
| `cmdb_ci`           | (added by enrichment) `'prod-app-cluster'`   |
| `opened_by`         | (added by enrichment) `'J. Smith'`           |
| `_scheduled_dt`     | (added by enrichment) parsed `datetime` from `scheduled` (strips `UTC` suffix) — used by the time-range filter |

## Enrichment block

Right after the two main constants, a small block injects `cmdb_ci` and `opened_by`:

```python
_INCIDENT_EXTRAS = {
    'inc001': {'cmdb_ci': 'prod-db-01', 'opened_by': 'Monitoring Bot'},
    ...
}
for _i in DEMO_INCIDENTS:
    _ex = _INCIDENT_EXTRAS.get(_i['sys_id'], {})
    _i.setdefault('cmdb_ci',   _ex.get('cmdb_ci', ''))
    _i.setdefault('opened_by', _ex.get('opened_by', ''))
```

Same for `_CHANGE_EXTRAS`. Uses `setdefault` so if the main dict already has these keys they aren't overwritten.

A second enrichment block follows to parse the display-string dates (`opened`, `scheduled`) into `datetime` objects stored under `_opened_dt` / `_scheduled_dt`:

```python
def _parse_demo_dt(raw):
    if not raw: return None
    s = raw.replace(' UTC', '').strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try: return datetime.strptime(s, fmt)
        except ValueError: continue
    return None

for _i in DEMO_INCIDENTS:  _i['_opened_dt']    = _parse_demo_dt(_i.get('opened', ''))
for _c in DEMO_CHANGES:    _c['_scheduled_dt'] = _parse_demo_dt(_c.get('scheduled', ''))
```

These are what `_filter_by_days` compares against when the user picks a time range.

### Why enrich separately?
When we added Search, we needed two new fields on every demo record. Rather than sprawling the already-long literal, the enrichment block keeps the original demo literal focused on "operational" fields and lets us add search-relevant attributes beside it. If we ever add more fields, follow the same pattern.

## Helper functions

```python
def _get_incident(number):
    return next((i for i in DEMO_INCIDENTS if i["number"] == number), None)

def _get_change(number):
    return next((c for c in DEMO_CHANGES if c["number"] == number), None)

def _annotate_ctask_pct(changes):
    # Adds ctask_closed + ctask_pct to each change dict
    for c in changes: ...
    return changes

def _parse_numbers(raw):
    # Lenient separator-tolerant number extraction
    import re
    return [n.strip().upper() for n in re.split(r'[\s,;|/]+', raw) if n.strip()]
```

## Data mode toggle (demo vs live)

Read views no longer touch `DEMO_INCIDENTS` / `DEMO_CHANGES` directly — they go through a small indirection layer that checks the user's data mode. The mode is stored per-user in the Django session and toggled from a chip in the header.

### Helpers (`pages.py`)

```python
def _data_mode(request) -> str:
    m = request.session.get('data_mode', 'demo')
    return 'live' if m == 'live' else 'demo'

def _is_live(request) -> bool:
    return _data_mode(request) == 'live'

def _incidents_source(request):
    return [] if _is_live(request) else DEMO_INCIDENTS

def _changes_source(request):
    return [] if _is_live(request) else DEMO_CHANGES

def _get_incident_modal(request, number):
    return None if _is_live(request) else _get_incident(number)

def _get_change_modal(request, number):
    return None if _is_live(request) else _get_change(number)
```

In **live** mode today the helpers return empty results — the real ServiceNow read path (sync wrapper over `table_*` tasks) isn't wired yet. The UI surfaces this via a global warning banner rendered from `base.html` when `request.session.data_mode == 'live'`.

### Toggle endpoint + chip

```python
def data_mode_toggle(request):
    current = request.session.get('data_mode', 'demo')
    request.session['data_mode'] = 'live' if current == 'demo' else 'demo'
    resp = HttpResponse(status=200)
    resp['HX-Refresh'] = 'true'   # reload so every template picks up the new mode
    return resp
```

Route: `POST /servicenow/mode/toggle/`. The chip in `base.html`'s header is a single-button HTMX form with `hx-swap="none"` — the server's `HX-Refresh: true` response header does a full reload.

### Live mode is fully async

Live-mode views no longer call through the `_incidents_source` / `_changes_source` helpers at all. Instead, each view dispatches its own Celery task via `.delay()`, renders a placeholder div that polls `/servicenow/live/poll/<shape>/<task_id>/`, and the poll endpoint's shape renderer adapts the task result into the same partial the demo path uses.

The `_incidents_source` / `_changes_source` / `_get_incident` / `_get_change` helpers are now demo-only — they exist inside `else:` branches that only run when `_is_live(request)` is `False`.

The live-mode banner in `base.html` confirms the user is on real data and reminds them the session pill must be green.

## Who reads the demo data

All of these now go through the mode-aware helpers:

| Consumer                           | Uses                                           |
| ---------------------------------- | ---------------------------------------------- |
| `dashboard`                        | `_incidents_source` + `_changes_source` + `DEMO_STATS` (zeroed in live) |
| `incidents_list`                   | `_incidents_source` + filter pipeline          |
| `incident_detail`                  | `_get_incident_modal`                          |
| `changes_list`                     | `_changes_source` + filter pipeline            |
| `change_detail`                    | `_get_change_modal`                            |
| `change_briefing`                  | `_get_change_modal` + `_build_briefing_prompt` |
| `bulk_change_review` + `_item`     | `_get_change_modal` per row                    |
| `record_lookup`                    | `_get_incident_modal` + `_get_change_modal`    |
| `search_records`                   | `_incidents_source` / `_changes_source` + `_filter_records` |
| `_run_preset_for_display`          | Returns empty rows when `_is_live(request)`; otherwise `_preset_demo_incidents` / `_preset_demo_changes` |

## Migrating off demo data

Thanks to the mode-toggle indirection layer, going live is now localised to the helper bodies — views don't need editing.

1. **Build a sync Table API wrapper.** Either run `table_list_task`'s body inline, or call the operation function directly (no Celery). See [Table API](06_table_api.md).
2. **Replace the empty returns** in `_incidents_source`, `_changes_source`, `_get_incident_modal`, `_get_change_modal` with calls to that wrapper.
3. **Adapt the response** — Table API returns raw shapes (`priority=1`, `state=in_progress`, ISO dates, no nested ctasks). Write a tiny `_normalise_incident(raw)` / `_normalise_change(raw)` that produces the same dict shape the templates already expect (`priority_label`, `state_code`, `age`, `opened`, `_opened_dt`, etc.). No template changes required.
4. **Keep the demo data** as the default mode — users explicitly opt into live via the chip.
5. **Dashboard tile counts** — `DEMO_STATS` is hard-coded and only used in demo mode. In live mode, either issue count-only Table API queries or leave the zeros until someone asks.

The write paths (create, patch) already use Celery tasks and don't need the indirection layer — they read session credentials directly and are unaffected by the mode toggle.

## Gotchas

### Enrichment must run before any function that reads the fields
The enrichment block sits immediately after `DEMO_STATS`, before any helper function. Keep it there — moving it below the functions would cause AttributeError-style misses if module import order surprised us.

### `setdefault` vs direct assignment
Using `setdefault` means the canonical values win if you ever put `cmdb_ci` into the main literal. If you want to force-override from enrichment, switch to `i['cmdb_ci'] = _ex.get(...)`.

### Demo record sys_ids
We use readable sys_ids like `inc001`, `chg002`. Real ServiceNow sys_ids are 32-char hex. Any code that assumes hex format will break on demo data — avoid that assumption.

## See also
- [Feature: Bulk and Search](09_feature_bulk_and_search.md) — consumers of the enrichment fields
- [Adding a Feature](11_adding_a_feature.md) — when new fields are needed, use the same enrichment pattern

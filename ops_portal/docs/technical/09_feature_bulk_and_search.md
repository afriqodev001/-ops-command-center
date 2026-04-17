# Feature: Bulk + Search + Fetch Flows

Four related but distinct features all live at the list-operation layer:

1. [Bulk Change Review](#bulk-change-review) — paste CHG numbers → heuristic review cards
2. [Bulk Change Create](#bulk-change-create) — paste/CSV → create N changes
3. [Search](#search) — filter records by CI / requester / assignment group
4. [Fetch by Number](#fetch-by-number) — resolve pasted numbers to records

## Bulk Change Review

### Files
- `pages.bulk_change_review` — GET page + POST initial queue
- `pages.bulk_change_review_item` — HTMX endpoint per-row
- `pages._heuristic_review` — rule-based review (placeholder for AI)
- `pages._parse_numbers` — lenient separator-tolerant number extraction
- Templates: `bulk_change_review.html`, `partials/bulk_review_queue.html`, `partials/bulk_review_card.html`

### Progressive rendering
The initial POST returns a queue of pending cards (one per parsed CHG number), each with a `delay_ms` offset:

```python
items.append({'number': num, 'delay_ms': i * 700})
```

Each card's template fires its own `hx-trigger="load delay:{{ delay_ms }}ms"` request to `/changes/bulk-review/item/`. Staggering by 700ms prevents thundering-herd and gives a pleasant progressive reveal.

### Heuristic review logic
See `_heuristic_review(change, ctask_pct, ctask_closed, ctask_total)`:

```
Signal                                  Effect
─────────────────────────────────────── ──────────────
All CTASKs closed + non-High risk + 
  has notes + has attachments           APPROVE
0% CTASKs complete OR 3+ flags          HOLD
High/Critical risk at < 100% CTASKs     HOLD
Otherwise                                REVIEW
```

Returns `{recommendation, flags, positives, is_heuristic}`.

### AI integration point
When wiring Claude / GPT:
- `_build_briefing_prompt()` in `pages.py` already produces the structured prompt.
- Replace the `_heuristic_review` call with a task dispatch: POST the prompt to the LLM API, wait for response, parse verdict.
- Add a new Celery task so the bulk review loop polls asynchronously.

## Bulk Change Create

### Files
- `pages.bulk_change_create` — GET page
- `pages.bulk_change_preview` — POST parse + validate
- `pages.bulk_change_submit` — POST dispatch creates
- `pages.bulk_change_template_save` / `_delete` — standard-change template manager (unified store, kind=standard_change)
- `services/bulk_change_parser.py` — parse + validate
- Templates: `bulk_change_create.html`, `partials/bulk_change_preview.html`, `partials/bulk_change_template_list.html`, `partials/bulk_change_template_errors.html`

### Parser (`bulk_change_parser.py`)

| Function                                  | Purpose |
| ----------------------------------------- | ------- |
| `parse_text(raw)`                         | TSV/CSV text → list of dicts |
| `parse_csv_file(file)`                    | UploadedFile → list of dicts (UTF-8-BOM safe) |
| `_detect_delimiter(sample)`               | Prefer tab if present, else comma |
| `_normalise_rows(reader)`                 | Lowercase/strip header names; drop empty rows |
| `validate_rows(rows, known_template_keys)`| Per-row error/warning dicts |
| `summarise(validated)`                    | Totals by type + valid/invalid |

Validation rules:
- `type` in `{normal, emergency, standard}`
- `short_description` non-empty, ≤ 160 chars
- `assignment_group` non-empty
- `start_date`, `end_date` parse via one of several accepted formats
- `end_date > start_date`
- For `standard`: `template_key` warning (not error) if missing or unknown

Date formats accepted:
```
%Y-%m-%d %H:%M:%S
%Y-%m-%d %H:%M
%Y-%m-%dT%H:%M:%S
%Y-%m-%dT%H:%M
%Y-%m-%d
%d/%m/%Y %H:%M
%m/%d/%Y %H:%M
```

### Submit flow (`bulk_change_submit`)

Input (JSON body): `{rows: [rawRowDict, ...]}`.

Output: `{items: [...]}` where each item is one of:

```json
// Normal or emergency
{ "row_index": 0, "kind": "normal", "task_id": "...", "short_description": "..." }

// Standard
{ "row_index": 1, "kind": "standard", "url": "https://...", "template_label": "...", "short_description": "..." }

// Invalid (skipped)
{ "row_index": 2, "kind": "standard", "short_description": "...", "error": "..." }
```

Client behavior after submit:
- Normal/emergency items → poll `/tasks/<task_id>/result/` in parallel.
- Standard items → **sequentially** open `window.open(url)`, poll `popup.closed`, advance on close.

Both groups run via `Promise.all([this._runAllTaskPolls(), this._runStandardSequentially()])` — normal/emergency polls don't block standard-tab progression and vice versa.

### Template manager (in bulk-create page)

Inline modal talks to the unified store filtered to `kind=standard_change`:

- Save: POSTs to `/changes/bulk-create/templates/save/` → calls `save_template(key, kind='standard_change', label, url)`
- Delete: POSTs to `/changes/bulk-create/templates/delete/` → `delete_template(key)`

The full-page Templates manager (`/templates/`) shows the same entries plus the three API-kind templates.

## Search

### Files
- `pages.search_records` — GET page + POST filter
- `pages._filter_records` / `_match` — case-insensitive substring AND filter
- `pages._filter_by_days` — time-range filter (shared with Incidents / Changes lists)
- `services/search_presets.py` — storage for saved filter-value shortcuts
- Templates: `search.html`, `partials/search_results.html`, `partials/search_preset_list.html`, `partials/search_preset_errors.html`

### Filter logic

```python
def _match(haystack, needle):
    if not needle: return True
    return needle.lower().strip() in (haystack or '').lower()

def _filter_records(records, ci, requested_by, assignment_group):
    return [r for r in records
            if _match(r.get('cmdb_ci'),         ci)
            and _match(r.get('opened_by'),      requested_by)
            and _match(r.get('assignment_group'), assignment_group)]
```

Simple substring, AND-combined. Empty filter = pass through. Domain selection routes to either `DEMO_INCIDENTS` or `DEMO_CHANGES`.

### Time range
Every Search POST applies `_filter_by_days(records, dt_field, days)` *before* the CI / requester / group filters (so the cheap datetime filter runs first). `dt_field` is `_opened_dt` for incidents and `_scheduled_dt` for changes; both are populated by the demo-data enrichment block. Default `days='30'`, configurable per-request via the form. Results are capped at `DEFAULT_LIST_LIMIT` (200) — the pre-cap count is exposed as `matched` so the template can render "Showing X of Y — capped at 200."

### Search presets

A parallel, lightweight feature that stores named shortcuts for filter values — intended for long or hard-to-remember CI names behind a short `app_id`.

**Storage** — `servicenow/search_presets.json`:

```json
{
  "pdly_prod": {
    "app_id":           "PDLY",
    "label":            "Production ledger",
    "cmdb_ci":          "prod-pdly-app-cluster-eu-01",
    "requested_by":     "",
    "assignment_group": "Financial Platform"
  }
}
```

**Service API (`services/search_presets.py`)**:

| Function                     | Purpose |
| ---------------------------- | ------- |
| `load_presets()`             | Returns full dict |
| `save_preset(key, data)`     | Overwrite / insert |
| `delete_preset(key)`         | Remove by key |

**Views**:

| Route                                    | View                       | Purpose |
| ---------------------------------------- | -------------------------- | ------- |
| `POST /servicenow/search/presets/save/`  | `search_preset_save`       | Validate + save; returns list partial with `HX-Retarget: #search-preset-list` + `HX-Trigger: search-presets-changed` |
| `POST /servicenow/search/presets/delete/`| `search_preset_delete`     | Remove; same trigger |
| `GET /servicenow/search/presets/json/`   | `search_presets_json`      | Tiny `JsonResponse(load_presets())` — used by Alpine to refresh the in-memory presets after changes |

**Frontend pattern**:

- Page context includes `search_presets` (serialized via `{{ search_presets|json_script:"search-presets-json" }}`).
- `searchPage()` Alpine component reads the JSON blob on init, listens for `search-presets-changed` on window, and refetches via `/search/presets/json/`. That's why a dedicated JSON endpoint exists — otherwise the in-memory presets go stale after add/delete without a page reload.
- Selecting a preset calls `applyPreset()` which writes the stored values directly into the form inputs (`document.querySelector('[name="cmdb_ci"]').value = ...`). No Alpine `x-model` on those inputs, because we want the existing HTMX form behaviour unchanged.
- Manage modal lives in `{% block modals %}`. Opening the modal pre-fills the save form with the *current* filter values so "save current as preset" is one click.

**Validation rules** (in `search_preset_save`):
- `key` matches `^[a-z][a-z0-9_]*$`
- `app_id` non-empty
- `cmdb_ci` non-empty (entire point of the preset — shortcutting the long CI)
- `label` optional; `requested_by` / `assignment_group` optional

### Demo-data dependency
The `cmdb_ci`, `opened_by`, `_opened_dt`, `_scheduled_dt` fields on demo records are populated via the enrichment blocks after the demo-data declarations (see [Demo Data](10_demo_data.md)).

### Live mode — fully async

In live mode, `search_records` dispatches `table_list_task.delay()` with a query built by `_build_incident_search_query` or `_build_change_search_query`. The view returns a `live_loading.html` placeholder that polls `/servicenow/live/poll/search-results/<task_id>/`. Filter state is encoded into the poll URL's query string so the renderer can echo filter chips correctly.

`record_lookup` (Fetch by Number) dispatches at most two bulk tasks (`incident_bulk_get_by_field_task`, `changes_bulk_get_by_number_task`) — one for INC numbers, one for CHG numbers. Each section has its own polling placeholder.

## Fetch by Number

### Files
- `pages.record_lookup` — GET page + POST resolve
- `pages._parse_numbers` — reusable parser (shared with bulk review)
- Templates: `lookup.html`, `partials/lookup_results.html`

### Flow
1. Parse numbers from textarea (comma / whitespace / slash / pipe / semicolon separators).
2. Route by prefix: `INC*` → incidents table, `CHG*` → changes table, other → not_found.
3. Render each bucket in the results panel.

Currently hits `_get_incident(num)` / `_get_change(num)` (demo lookups). To go live, replace with `changes_get_by_number_task` + `table_get_by_field_task` calls — but do both serially wrapped into a single Celery `bulk_get` task to avoid N round-trips.

## Cross-cutting patterns

### Sequential vs parallel
| Operation                    | Ordering       | Why |
| ---------------------------- | -------------- | --- |
| Normal/emergency create tasks| Parallel       | No UI interaction; just API calls |
| Standard change popups       | **Sequential** | User must complete each in ServiceNow |
| Bulk review cards            | Staggered (700ms) | Progressive reveal without overwhelming |
| Fetch-by-number lookups      | (Demo: all at once) | Would be bulk-batched at API layer |

### CSRF for JSON POSTs
`bulk_change_submit` expects a JSON body. Django CSRF middleware accepts the token via `X-CSRFToken` header:

```javascript
const resp = await fetch('/servicenow/changes/bulk-create/submit/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken':  document.querySelector('input[name="csrfmiddlewaretoken"]').value,
  },
  body: JSON.stringify({rows}),
});
```

No `@csrf_exempt` needed.

### Number-parsing helper
`_parse_numbers` in `pages.py` is the canonical lenient separator-tolerant parser. Reused by bulk review, fetch by number, and (should be reused by) any future "paste a list of identifiers" feature.

## See also
- [Creation Templates](08_feature_templates.md) — where standard-change URLs are stored
- [Presets](07_feature_presets.md) — the query/filter counterpart for finding records
- [Celery Tasks](05_celery_tasks.md) — task dispatch and polling

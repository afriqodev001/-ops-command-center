# Feature: Presets

Saved *read* queries for ServiceNow. The largest feature surface in the app today.

> **Not to be confused with [Search Presets](09_feature_bulk_and_search.md#search-presets)** — those live in their own `search_presets.json` store and exist purely to shortcut long CI names on the Search page. This doc covers *query* presets: table + encoded query + fields, rendered into real Table API operations.

## Files

| File | Role |
| ---- | ---- |
| `servicenow/services/query_presets.py`             | Built-in registry, user-preset load/save, merge logic, `render_preset()` |
| `servicenow/user_presets.json`                     | User-authored preset storage |
| `servicenow/pages.py`                              | Views: page, run UI, save/delete, export/import |
| `servicenow/templates/servicenow/presets.html`     | Full page + embedded modals |
| `servicenow/templates/servicenow/partials/`        | Preset result, form errors, import result partials |

## Data model

Canonical preset:

```python
{
    "description":     "...",
    "table":           "change_request" | "incident" | ...,
    "query":           "encoded query with optional {placeholders}",
    "fields":          "comma,separated,field,list",
    "defaults":        { "limit": 25, "display_value": True },
    "required_params": ["assignment_group_sys_id", ...],  # auto-detected from query
    "domain":          "change" | "incident",
}
```

Keys:
- **Built-in presets** live as `BUILT_IN_PRESETS` in `query_presets.py`.
- **User presets** live in `user_presets.json`, keyed the same way.
- Merging: `get_all_presets()` returns `{**BUILT_IN_PRESETS, **load_user_presets()}` — user overrides win on name collision.

## Service API (`query_presets.py`)

| Function                    | Purpose |
| --------------------------- | ------- |
| `get_all_presets()`         | Merged dict (built-in + user) |
| `load_user_presets()`       | Just the user dict |
| `save_user_preset(name, cfg)` | Write/overwrite one entry |
| `delete_user_preset(name)`  | Remove user entry (built-ins untouched) |
| `list_presets()`            | Grouped-by-domain view for menus |
| `render_preset(name, params)` | Turn a preset into a concrete Table API op: `{table, query, fields, limit, display_value}` |

### Render semantics

`render_preset(name, params)`:

1. Looks up the preset in `get_all_presets()` (user-overriding).
2. Checks each name in `required_params` is present in `params`; missing → `ValueError`.
3. Substitutes placeholders via `.format(**params)` — so `query` treats `{name}` as a `str.format` placeholder.
4. Returns the resolved op dict.

Placeholders are auto-detected at save time in `pages.preset_save` via `re.findall(r'\{(\w+)\}', query)` if the user didn't supply `required_params` manually.

## View surface (`pages.py`)

| View                   | Route                         | Purpose |
| ---------------------- | ----------------------------- | ------- |
| `presets_page`         | `GET /presets/`               | Render the main page; serializes presets via `json_script` into `window.PRESET_CONFIGS` |
| `preset_run_ui`        | `POST /presets/run/ui/`       | Run a preset and return the result partial |
| `preset_save`          | `POST /presets/save/`         | Create / edit / clone → save user preset |
| `preset_delete`        | `POST /presets/delete/`       | Remove user preset |
| `presets_export`       | `GET /presets/export/`        | Download all merged presets as JSON |
| `presets_import`       | `POST /presets/import/`       | Bulk import (file or paste) |

Note the preset **list + run API** endpoints still exist in `views.py` (`presets_list`, `presets_run`) as the JSON API — `pages.py` covers the HTML/HTMX surface.

## Frontend surface

### Page (`presets.html`)
Alpine component `presetsPage(defaultPreset)` manages:
- `selectedPreset`, `search`, `paramValues`
- `cfg()` — reads `window.PRESET_CONFIGS[selectedPreset]` (no Alpine reactivity on that dict — fine because we recompute on `selectedPreset` change)
- `injectParams()` — synthesizes hidden inputs before HTMX submit

Registered via:
```javascript
Alpine.data('presetsPage', (defaultPreset) => ({ ... }));
```

Data bridge: `{{ presets_data|json_script:"preset-configs-json" }}` → `window.PRESET_CONFIGS = JSON.parse(...)`.

### Preset form modal
Alpine component `presetFormData()` manages:
- `mode`: `create` | `edit` | `clone`
- `form`: all editable fields
- `is_builtin`: locks name field, changes save button label
- `jsonPaneOpen`, `jsonText`, `jsonError`, `jsonApplied`, `copyStatus` (for copy/paste JSON)
- `confirmingDelete`, `deleteTarget` (for the delete confirmation flow)

Opens via `$dispatch('open-preset-form', { mode, name, cfg })` from the list, right panel, or header button.

Special modes:
- **clone** — name is suggested as `<orig>_copy` (de-duped), `is_builtin` forced to `false`.
- **edit** of a built-in — `is_builtin=true`, name is readonly, save button says "Save as custom override."

### Import modal
Separate `<dialog id="preset-import-modal">`. Simple form with file + textarea inputs. Response is the import result partial which shows counts and validation errors.

## Export / import format

Export produces a dict keyed by name:
```json
{
  "my_preset": {
    "description": "...",
    "table": "incident",
    "domain": "incident",
    "query": "...",
    "fields": "...",
    "required_params": [],
    "defaults": { "limit": 25, "display_value": true }
  }
}
```

Import accepts either that shape OR an array of flat entries:
```json
[{ "name": "my_preset", "description": "...", ... }]
```

Validation per entry:
- `name` matches `^[a-z][a-z0-9_]*$`
- `description`, `table`, `query`, `fields`, `domain` non-empty
- `domain ∈ {change, incident}`

Invalid entries are skipped; valid entries saved as user presets (overriding built-ins of the same name). Results partial lists saved names and error reasons.

## Copy/paste JSON per preset

Inside the form modal:

- **Copy JSON** — serialises current form state (`form` → object) and calls `navigator.clipboard.writeText(...)`.
- **Paste JSON** — toggles a textarea; clicking "Apply to form ↑" parses and overwrites form fields.

Paste accepts both flat (`{name, description, ...}`) and wrapped (`{"preset_name": {cfg}}`) shapes. Respects readonly name for built-in overrides.

## Running a preset (end-to-end)

```
User selects preset in sidebar  →  selectedPreset state updates
                                ↓
Required params inputs appear (if any)
                                ↓
User clicks "Run preset"        →  form @submit="injectParams($event)"
                                ↓
injectParams() creates hidden <input> for each paramValues entry
                                ↓
HTMX hx-post="/presets/run/ui/" submits the form
                                ↓
preset_run_ui validates + calls _run_preset_for_display
                                ↓
Currently: filters DEMO_INCIDENTS / DEMO_CHANGES in Python
Future:    dispatch presets_run_task → poll → swap result
                                ↓
Response = preset_result.html partial
                                ↓
HTMX swaps into #preset-results
```

## Gotchas

### `json_script` is mandatory for the configs blob
`{{ presets_json }}` (raw) inside `<script>` gets HTML-escaped and breaks `JSON.parse`. Use `{{ presets_data|json_script:"..." }}` (pass the raw dict, not a pre-serialized string).

### Script order inside `{% block modals %}`
The `<script>` defining `presetFormData()` must be *before* the `<dialog x-data="presetFormData()">` element in the rendered HTML, or the `Alpine.data()` registration via `alpine:init` must handle first-load timing. We do both: script first in DOM order, *and* `Alpine.data` registration (survives `hx-boost`).

### Built-in vs override shadowing
`get_all_presets()` merges with user winning. Deleting a user entry restores the built-in. Editing a built-in creates a same-name user entry — the UI shows a `custom` badge when this happens.

### Required params auto-detection
If the user leaves the `required_params` text field blank, `preset_save` auto-detects `{placeholders}` from the query. If the user types their own list, it's respected as-is — useful for parameters that are referenced via `{name}` indirectly or intentionally excluded.

## See also
- [Creation Templates](08_feature_templates.md) — the write-side counterpart
- [Frontend Patterns](03_frontend_patterns.md) — especially `json_script` and `Alpine.data`
- [Table API](06_table_api.md) — where rendered presets eventually hit

# Presets

**Path:** `/servicenow/presets/`

Saved ServiceNow list queries. Built-ins live in code; user presets live in `user_presets.json` and can override built-ins of the same name. You can create, edit, clone, delete, export, import, and copy/paste preset JSON.

## When to use it

- Run a common query without rebuilding filters every time.
- Share tailored queries across the team via export / import.
- Prototype a query inline and save once it's useful.

For ad-hoc filter-based searches, use [Search](07_search.md). For by-number lookup, [Fetch by Number](06_fetch_by_number.md).

## Page layout

```
┌──────────────────────────────────────────────────────────┐
│ Header:  [Export]  [Import]  [New preset]                │
├──────────────────────────────┬───────────────────────────┤
│  LEFT — preset list          │  RIGHT — selected preset  │
│  [ Filter presets… ]         │                           │
│                              │  Table · Domain · custom  │
│  ── Changes                  │  Description heading      │
│  · Implementing now  [3]     │                           │
│  · Awaiting review   [1]     │  Required params          │
│  · High risk changes [ready] │  (if any, form appears)   │
│                              │                           │
│  ── Incidents                │  [ Run preset ]  [Edit]   │
│  · P1 open           [1]     │  [Clone] [Details ▾]      │
│  · P1+P2 open        [3]     │                           │
│  · Unassigned        [2]     │  (Details panel: query,   │
│                              │   fields, params)         │
├──────────────────────────────┴───────────────────────────┤
│  RESULTS (swapped in by HTMX)                            │
└──────────────────────────────────────────────────────────┘
```

## Preset anatomy

Each preset has:

| Field             | Purpose |
| ----------------- | ------- |
| `name`            | Slug (lowercase, digits, underscores). Unique. |
| `description`     | Human-readable label shown in the list. |
| `domain`          | `change` or `incident`. Governs grouping. |
| `table`           | ServiceNow table name (`change_request`, `incident`, …). |
| `query`           | Encoded ServiceNow query (`state=implement^ORDERBYDESCsys_updated_on`). May contain `{placeholders}`. |
| `fields`          | Comma-separated fields to return (`number,short_description,state,...`). |
| `required_params` | List of placeholder names the query needs at run time. |
| `defaults`        | `{ "limit": 25, "display_value": true }` |

Built-in presets are shipped in code. User presets live at `servicenow/user_presets.json`.

## Workflows

### Run a preset
1. Click a preset in the left list. The right panel updates with its description + metadata.
2. If **params required**, fill the yellow input(s) that appear.
3. Click **Run preset**. Results swap into the bottom panel.

### Create a new preset
1. Click **New preset** (header).
2. Fill name, description, domain, table, query, fields.
3. Optionally click **Auto-detect params** — scans the query for `{placeholder}` and populates the Required parameters field.
4. Click **Save preset**.

### Edit a preset
1. Hover a preset in the list; click the pencil icon. OR open it first and click **Edit** in the right panel.
2. Built-in presets show "Saving will create a custom override" — the name is locked so the override shadows the built-in.
3. User presets are fully editable (including name).
4. Save.

### Clone a preset
1. Hover a preset; click the copy-squares icon (or click **Clone** in the right panel).
2. The form opens pre-filled. Name is suggested as `<orig>_copy` (or `_copy2`, `_copy3` if taken); description has `(copy)` appended.
3. `is_builtin` is forced to `false` so the clone is a fresh user preset.
4. Edit any field, then **Save preset**.

### Delete a user preset
1. Hover the user preset; click the trash icon.
2. Confirm deletion in the modal.
3. Built-ins cannot be deleted (they're in code), only overridden.

## Export / import

### Export
Click **Export** in the header → downloads `presets.json` containing every currently-effective preset (built-ins merged with user overrides) in dict form:

```json
{
  "p1_open_incidents": {
    "description": "All open P1 incidents...",
    "table": "incident",
    "domain": "incident",
    "query": "priority=1^stateNOT IN6,7^ORDERBYopened_at",
    "fields": "number,short_description,priority,state,...",
    "required_params": [],
    "defaults": { "limit": 50, "display_value": true }
  },
  ...
}
```

### Import
Click **Import** in the header → modal opens.
- Upload a `.json` file, OR paste JSON directly.
- Accepts either dict form (`{name: cfg}`) or array form (`[{name, ...cfg}]`).
- Each entry is validated; the result panel shows how many saved and which were skipped (with reason).
- On success, click **Reload presets page** to see new presets in the list.

### Per-preset copy / paste JSON (within the edit modal)

Two buttons in the modal footer:
- **Copy JSON** — puts the current form state on the clipboard as a single object.
- **Paste JSON** — toggles a textarea; paste a preset JSON blob and click **Apply to form ↑**. Accepts flat (`{name, description, ...}`) or wrapped (`{"preset_name": {cfg}}`) shapes. Respects readonly name for built-in overrides.

## Examples

**Example 1 — Run `p1_open_incidents`**
1. Click it in the left list under Incidents.
2. No params required → click **Run preset**.
3. Results table appears below.

**Example 2 — Build an "Emergency changes by group" preset**
1. Click **New preset**.
2. Fields:
   - name: `emergency_changes_by_group`
   - description: "Active emergency changes for a group"
   - domain: change
   - table: change_request
   - query: `type=emergency^active=true^assignment_group={assignment_group_sys_id}^ORDERBYDESCsys_updated_on`
   - fields: `number,short_description,state,assignment_group,risk,sys_id`
3. Click **Auto-detect params** → fills `assignment_group_sys_id`.
4. Save.
5. Run it — the form now asks for the group sys_id before running.

**Example 3 — Share a preset with a colleague**
- You: open the preset in the edit modal, click **Copy JSON**.
- Them: open **New preset**, click **Paste JSON**, paste, click **Apply to form**, save.

**Example 4 — Backup all presets**
Click **Export**, commit the downloaded `presets.json` to a repo. To restore, use **Import** with the file.

## Tips

- The count badge on each preset (e.g. `[3]`) is the demo-data record count for no-param presets — a quick signal of whether a preset will return anything.
- The **ready** vs **params** badge tells you whether a preset runs immediately or needs input.
- Custom presets get a blue **custom** badge; built-ins don't.
- Use `Auto-detect params` after editing a query — keeps `required_params` in sync.
- Overrides shadow built-ins at runtime. Delete the user preset entry to revert to the built-in.

## See also
- [Templates](09_templates.md) — the write-side counterpart (creation payloads)
- [Search](07_search.md) — for ad-hoc filter-driven finding

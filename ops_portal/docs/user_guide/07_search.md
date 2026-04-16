# Search

**Path:** `/servicenow/search/`

Find incidents or changes by attribute — configuration item, requester, or assignment group. Filters AND together.

## When to use it

- "Show me all incidents on `prod-db-01`".
- "What's the change history for Database Ops?"
- "Did Jane open anything recently?"

For specific numbers, use [Fetch by Number](06_fetch_by_number.md). For saved queries, use [Presets](08_presets.md).

## Page layout

```
┌─────────────────────────────────────────────────────────────┐
│ Load preset: [ — choose — ▾ ]          [ Manage presets ]   │
├─────────────────────────────────────────────────────────────┤
│ [ Incidents ]  [ Changes ]              Leave blank...      │
│                                                             │
│ Config. item      Requested by   Assign. grp    Time range  │
│ [ prod-db-01   ]  [ J. Smith  ]  [ DB Ops   ]   [ Last 30 ▾]│
│                                                             │
│ [ Search ]  [ Clear ]                                       │
├─────────────────────────────────────────────────────────────┤
│ Showing 3 of 3 · CI: prod-db-01 · Last 30 days              │
│ ┌────────────────────────────────────────────────────────┐  │
│ │ INC0045231  P1  WIP    prod-db-01   DB Ops    ...      │  │
│ │ ...                                                    │  │
│ └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Controls

| Control         | Notes |
| --------------- | ----- |
| **Load preset** | Dropdown of saved filter presets. Picking one fills the CI / requester / group fields below. See [Saved search presets](#saved-search-presets). |
| **Manage presets** | Opens the preset manager modal — add, save-from-current, delete. |
| **Incidents / Changes** | Domain toggle. Pick one. |
| **Configuration item**  | Case-insensitive substring match on `cmdb_ci`. |
| **Requested by**        | Case-insensitive substring match on `opened_by` (the creator / caller). |
| **Assignment group**    | Case-insensitive substring match on `assignment_group`. |
| **Time range**          | Defaults to **Last 30 days** (`opened_at` for incidents, `start_date` for changes). Options: 7 / 30 / 90 / 365 / All time. |
| **Search**              | Runs the filter via HTMX; results swap below. |
| **Clear**               | Resets all inputs and wipes the results panel. |

## How filters combine

All filters **AND** together. An empty filter is skipped. So:

- `CI: prod-db-01` alone → every record touching that CI
- `CI: prod-db-01` + `Group: Database Ops` → only records where **both** match
- All blank → a friendly "Enter at least one filter" message

## Examples

**Example 1 — Incidents on a specific server**
1. Leave **Incidents** selected.
2. Type `prod-db-01` in Configuration item.
3. Click **Search**. Filter chips appear above the results confirming the active filter.

**Example 2 — Changes by a person**
1. Switch to **Changes**.
2. Type `J. Smith` in Requested by.
3. Search. You'll see every change J. Smith has raised.

**Example 3 — Narrowing by group and CI**
1. Switch to **Changes**.
2. `Platform` in Assignment group, `auth-service` in CI.
3. Search. Filters combine — only Platform's auth-service changes show.

## Results table

Columns adapt to the domain:

**Incidents**
| Column      | Source field            |
| ----------- | ----------------------- |
| Number      | `number` (links to detail) |
| Description | `short_description`     |
| Priority    | `priority` (badge)      |
| State       | `state`                 |
| CI          | `cmdb_ci`               |
| Group       | `assignment_group`      |
| Requested by| `opened_by`             |
| Assignee    | `assigned_to`           |

**Changes**
| Column      | Source field            |
| ----------- | ----------------------- |
| Number      | `number` (links to detail) |
| Description | `short_description`     |
| Type        | `type`                  |
| State       | `state`                 |
| Risk        | `risk` (badge if High/Critical) |
| CI          | `cmdb_ci`               |
| Group       | `assignment_group`      |
| Requested by| `opened_by`             |
| Assignee    | `assigned_to`           |

## Saved search presets

The dropdown above the filter row lets you save and re-use filter sets keyed by a short **App ID** + optional friendly **label**. Useful for applications with long or hard-to-remember CI names (the original motivating case: an app with App ID `PDLY` and a long CI like `prod-pdly-app-cluster-eu-01`).

Each preset stores:

| Field               | Required | Notes |
| ------------------- | -------- | ----- |
| `key`               | ✅        | Internal slug: lowercase, digits, underscores. Unique. |
| `app_id`            | ✅        | Short, uppercase code (e.g. `PDLY`). |
| `label`             | —        | Friendly name ("Production ledger"). Falls back to `key` if blank. |
| `cmdb_ci`           | ✅        | The long real CI value you want to shortcut. |
| `requested_by`      | —        | Default value for the Requested by filter. |
| `assignment_group`  | —        | Default value for the Assignment group filter. |

### Workflows

**Load an existing preset**
1. Pick an entry from the "Load preset" dropdown.
2. The CI / requester / group fields populate from the preset.
3. Click **Search**.

**Save your current filters as a preset**
1. Fill the CI / requester / group fields as you'd normally search.
2. Click **Manage presets**. The save form at the top pre-fills from the current filters.
3. Enter a **Key**, **App ID**, and optional **Friendly name**.
4. Click **Save preset**. The list below updates; the new preset appears in the dropdown immediately.

**Delete a preset**
1. Open **Manage presets**.
2. Click the trash icon next to the entry.

Presets are stored in `servicenow/search_presets.json` and survive restarts.

### Example

App `PDLY` runs on a CI named `prod-pdly-app-cluster-eu-01`, owned by the "Financial Platform" group. Save it once:

```
key:              pdly_prod
app_id:           PDLY
label:            Production ledger
cmdb_ci:          prod-pdly-app-cluster-eu-01
assignment_group: Financial Platform
```

After that, picking **[PDLY] Production ledger** from the dropdown gives you a two-click search instead of remembering and typing the full CI string.

## Tips

- Substring matching means partial terms work: `Database` matches "Database Ops", "Database Engineering", etc. Use specific strings to narrow.
- Case doesn't matter (`j. smith` == `J. Smith`).
- Filter chips echo what's active — useful as confirmation that the search actually ran with your inputs. The time range shows as a chip too (e.g. "Last 30 days") unless you chose All time.
- Empty-result vs no-filter are different states with different messages. If you see "Enter at least one filter," none of the inputs had a value.
- Records missing a CI or requester are shown with `—` in that column.
- Results are capped at 200 rows. If your filter matches more, the count chip reads **"Showing 200 of Y — capped at 200"**; narrow a filter or shorten the time range.

## Search presets vs Query presets

Two similar-sounding but different features:

| Feature | Stored in | For |
| ------- | --------- | --- |
| **Search presets** (this page) | `search_presets.json` | Shortcutting long CI values + filter defaults on the Search page |
| **[Query presets](08_presets.md)** | `user_presets.json` | Saved ServiceNow list queries with table/query/fields — run against the Table API |

Pick Search presets when you have a recurring **set of Search-page filter values** to recall. Pick Query presets when you have a recurring **full ServiceNow query** to run (parameterised or not).

## See also
- [Fetch by Number](06_fetch_by_number.md) — when you know the number
- [Presets](08_presets.md) — for saved ServiceNow list queries (different concept — see note above)

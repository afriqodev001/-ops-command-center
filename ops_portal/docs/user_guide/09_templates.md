# Templates

**Path:** `/servicenow/templates/`

Reusable payloads for creating records. Four kinds are supported:

| Kind                | Creates via        | Use for |
| ------------------- | ------------------ | ------- |
| `standard_change`   | ServiceNow UI (URL) | Standard changes with ServiceNow templates — opens the form pre-populated. |
| `normal_change`     | Table API          | Normal changes created headlessly. |
| `emergency_change`  | Table API          | Emergency changes — same flow, different `kind`. |
| `incident`          | Table API          | Incidents with default priority / group / category. |

All templates live in one file: `servicenow/creation_templates.json`.

## Where templates surface

1. **This page** (`/servicenow/templates/`) — full CRUD on every template across all kinds.
2. **Incidents list** header → "New from template" button — opens a picker scoped to `incident` templates.
3. **Changes list** header → "New from template" button — opens a picker with tabs for Standard / Normal / Emergency.
4. **Bulk Change Create** → the Standard Templates modal reads from the same store (kind `standard_change` only).

## Page layout

```
┌──────────────────────────────┬──────────────────────────────┐
│  LEFT — saved templates (4)  │  RIGHT — new template        │
│                              │                              │
│  ── Standard change (2)      │  Kind: [Std] [Norm] [Em] [Inc]│
│   ssl_renewal  SSL cert...   │                              │
│   nginx_restart  Restart...  │  Key         Label            │
│                              │  [ssl_renew] [SSL cert renew] │
│  ── Normal change (1)        │                              │
│   db_patching  Monthly DB... │  (Kind-specific fields...)    │
│                              │                              │
│  ── Incident (1)             │  [ Save template ]            │
│   p1_bridge  P1 bridge call  │                              │
└──────────────────────────────┴──────────────────────────────┘
```

## Template anatomy

Common fields:
| Field   | Purpose |
| ------- | ------- |
| `key`   | Slug — lowercase, digits, underscores. Unique across all kinds. |
| `kind`  | One of the four kinds. |
| `label` | Human-readable name. |

**Standard-change** also has:
| Field | Purpose |
| ----- | ------- |
| `url` | ServiceNow URL to open. Typically `https://INSTANCE.service-now.com/nav_to.do?uri=change_request.do?sys_id=-1&sysparm_template=TEMPLATE_NAME`. |

**Normal / emergency change** also has `fields`:
| Field              | Notes |
| ------------------ | ----- |
| `short_description`| Default title |
| `assignment_group` | Sys_id or name |
| `start_date`       | Default start |
| `end_date`         | Default end |
| `risk`             | `low`, `moderate`, `high`, … |
| `description`      | Full description |

**Incident** also has `fields`:
| Field              | Notes |
| ------------------ | ----- |
| `short_description`| Default title (often a prefix like `"P1 - "`) |
| `assignment_group` |       |
| `priority`         | `1` / `2` / `3` / `4` |
| `category`         | e.g. `network`, `database` |
| `description`      | Full description |

Any field left blank in the template stays blank by default — the end user fills it in the create form.

## Workflows

### Create a template
1. On `/servicenow/templates/`, pick a **Kind** in the radio row.
2. Enter a unique `key` and a `label`.
3. Fill the kind-specific fields (URL for standard_change; default fields for the others).
4. Click **Save template**. The left list refreshes.

### Delete a template
Click the trash icon beside an entry on the left. Immediate delete (no confirm modal — the CRUD is intentionally fast).

### Use a template (create a record)
1. Go to the Incidents or Changes list page.
2. Click **New from template** in the header.
3. (Changes only) Click the kind tab — Standard / Normal / Emergency.
4. Click the template card for the one you want. The form slides in with your defaults.
5. Edit any field. `short_description` is always required.
6. Click **Create** (Table API kinds) or **Open in ServiceNow** (standard_change).

### Standard change flow vs API kinds

- **standard_change** → clicking the Create button builds a URL with your field values appended as `sysparm_query` parameters. The URL opens in a new browser tab; you complete and save in ServiceNow. The result panel shows the URL for reference.
- **normal_change / emergency_change / incident** → clicking Create dispatches a Celery task that POSTs to the Table API. A watcher polls `/tasks/<id>/result/` every 2s and shows the created record's number (with a link to its detail page) when ready.

## Examples

**Example 1 — DB patching normal-change template**
Kind: `normal_change`, key: `db_patching`, label: `Monthly DB patching`
- short_description: `Monthly DB patching`
- assignment_group: `Database Ops`
- risk: `moderate`
- description: `Apply latest OS and DB patches per runbook DBOPS-014.`

**Example 2 — P1 bridge incident template**
Kind: `incident`, key: `p1_bridge`, label: `P1 bridge call incident`
- short_description: `P1 - ` (agent types the rest)
- priority: `1`
- assignment_group: `Platform`
- category: `availability`

**Example 3 — SSL renewal standard-change template**
Kind: `standard_change`, key: `ssl_renewal`, label: `SSL certificate renewal`
- url: `https://myco.service-now.com/nav_to.do?uri=change_request.do?sys_id=-1&sysparm_template=SSL_Renewal`

When used, the URL gets `sysparm_query=short_description=...^start_date=...` appended with the agent's inputs.

## Tips

- **One store, many entry points.** The template you add here is visible on every page that surfaces templates of that kind (Incidents list, Changes list, Bulk Change Create).
- **Migration from older setup.** If you previously used the inline standard-change templates modal on the Bulk Change Create page, those entries auto-migrated into this unified store on first load of the Templates page — no manual action needed.
- **Keys must be unique across kinds.** `db_patching` can't be both a normal-change and an incident template. Namespace your keys (e.g. `chg_db_patching`, `inc_db_outage`) if you need variants.
- **Popups blocked?** The standard-change flow opens `window.open(url, '_blank')`. Allow popups for this site or the Create button will fail silently.

## See also
- [Presets](08_presets.md) — the read-side counterpart (list queries)
- [Bulk Change Create](05_bulk_change_create.md) — multi-record creation using standard-change templates per row
- [Incidents](02_incidents.md) · [Changes](03_changes.md) — where "New from template" buttons live

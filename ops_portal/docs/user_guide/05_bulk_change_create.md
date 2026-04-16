# Bulk Change Create

**Path:** `/servicenow/changes/bulk-create/`

Create multiple change records from paste or CSV upload. Normal and emergency changes go through the Table API; standard changes open in ServiceNow tabs one at a time.

## When to use it

- Spinning up N changes from a planning spreadsheet (e.g. quarterly patching wave).
- Converting a runbook of standard changes into actual records.
- Templating a batch from another tool's export.

## Page layout

```
┌─────────────────────────────────────────────────────────────┐
│  [ Paste ]  [ CSV upload ]    Required headers: type, ...   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ type,short_description,assignment_group,start_date,...│  │
│  │ normal,DB index rebuild,Database Ops,2026-05-01 22:00.│  │
│  │ standard,SSL renewal,Security,2026-05-02 10:00,...    │  │
│  └───────────────────────────────────────────────────────┘  │
│  [ Parse & validate ]                                       │
├─────────────────────────────────────────────────────────────┤
│  PREVIEW — 3 rows · 3 valid · 1 normal · 1 emergency · 1 std│
│  (validation table with per-row errors and warnings)        │
│  [ Submit 3 changes ]                                       │
├─────────────────────────────────────────────────────────────┤
│  RUN DETAILS — live per-row status                          │
│  # Type       Description       Status         Result       │
│  1 normal     DB index rebuild  Created        CHG0034600   │
│  2 emergency  DNS hotfix        Creating…      ——           │
│  3 standard   SSL renewal       Tab open…      (link)       │
└─────────────────────────────────────────────────────────────┘
```

## Required columns (headers, case-insensitive)

| Column            | Required | Notes |
| ----------------- | -------- | ----- |
| `type`            | ✅       | `normal`, `emergency`, or `standard` |
| `short_description` | ✅     | Max 160 chars |
| `assignment_group` | ✅      | Sys_id or name — ServiceNow resolves |
| `start_date`      | ✅       | Parsed formats below |
| `end_date`        | ✅       | Must be after start_date |
| `template_key`    | ⚠️       | Required for `standard` rows if you want a ServiceNow template to open |
| `risk`            | —        | e.g. low / moderate / high |
| `description`     | —        | Full description |

### Accepted date formats
```
2026-05-01 22:00
2026-05-01 22:00:00
2026-05-01T22:00
2026-05-01
01/05/2026 22:00
05/01/2026 22:00
```

## How to use it

### Paste mode
1. Click the **Paste** tab.
2. Paste tab-separated (from Excel) or comma-separated text with a header row.
3. Click **Parse & validate**.
4. Review the preview. Fix any red-flagged rows in the source, re-paste, re-validate.
5. Click **Submit N changes**.

### CSV upload mode
1. Click **CSV upload**.
2. Choose a `.csv` file.
3. Click **Parse & validate**. Same preview flow.

### Submit flow per type

- **Normal / Emergency** — each row dispatches a Celery task that POSTs to the ServiceNow Table API. The run-details panel polls every 2 seconds per row until the task completes. On success, the created CHG number is shown and linked to the detail page.
- **Standard** — rows run **sequentially**. For each:
  1. A new browser tab opens at the template URL (pre-filled with the row's short_description, assignment_group, dates as `sysparm_query` params).
  2. You complete and save the change in ServiceNow.
  3. Close the tab.
  4. The next row's tab opens automatically.

## Examples

**Example 1 — 3-row minimal CSV**
```csv
type,short_description,assignment_group,start_date,end_date
normal,DB index rebuild,Database Ops,2026-05-01 22:00,2026-05-01 23:00
emergency,DNS hotfix,Network Ops,2026-05-01 15:00,2026-05-01 16:00
standard,SSL cert renewal,Security,2026-05-02 10:00,2026-05-02 11:00
```
The standard row above has no `template_key` → a blank ServiceNow form will open (you can still save it manually).

**Example 2 — With template keys**
```csv
type,short_description,assignment_group,start_date,end_date,template_key
standard,SSL cert renewal,Security,2026-05-02 10:00,2026-05-02 11:00,ssl_renewal
standard,Nginx restart,Platform,2026-05-02 11:30,2026-05-02 12:00,nginx_restart
```
Each standard row opens the URL stored in the matching template.

**Example 3 — Excel paste**
Copy a range from Excel (header row included) and paste straight into the textarea — tab-separated is auto-detected.

## Managing standard-change templates

Click **Standard templates** in the header to open the modal:
- Add: enter `key` (e.g. `ssl_renewal`), `label`, and a ServiceNow URL like
  `https://INSTANCE.service-now.com/nav_to.do?uri=change_request.do?sys_id=-1&sysparm_template=SSL_Renewal`.
- Delete: trash icon next to each entry.

Templates managed here are the same store used by the [Templates](09_templates.md) page (kind `standard_change`).

## Tips

- **Popup blocker** — the first time you submit a standard-change batch, your browser may block the popup. Allow popups for this site and resubmit.
- **End-to-start** is always validated (end_date must be strictly after start_date) — a 30-second guard rail against date typos.
- **Validation is client-preview + server-authoritative**. Invalid rows show up in the preview and can't be submitted; you'll have to fix source and re-parse.
- **Atomicity** — each row is an independent task. If row 2 fails, rows 1 and 3 still complete. The run-details panel shows per-row success/error.
- **Standard-change "success"** just means you closed the ServiceNow tab. We can't verify you actually saved; if you closed without saving, re-run that row.

## See also
- [Templates](09_templates.md) — the unified template manager (includes standard-change URLs)
- [Changes](03_changes.md) — to verify created changes
- [Bulk Change Review](04_bulk_change_review.md) — for the reviewing-batch companion flow

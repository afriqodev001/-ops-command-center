# On-Call Automation Ideas

## Context

These are practical, immediately buildable automations using the existing ServiceNow APIs.
The goal is to remove every unnecessary click, form, and context-switch from an on-call
engineer's workflow — so they can focus on fixing the problem, not managing the ticket.

All ideas below map directly to existing endpoints. Each one is a thin wrapper,
a management command, or a small script.

---

## Creating Records

### 1. One-liner incident creator
The most common on-call task. Pass a description, get a number back. No browser, no form.

```bash
python manage.py create_incident \
  --desc "DB connection pool exhausted on prod-db-01" \
  --group "Database Ops" \
  --impact 2 \
  --urgency 2
# → INC0045231 created
```

**Uses:** `POST /servicenow/incidents/create/`

---

### 2. Emergency change fast-path
When something is on fire and you need a change record open immediately.
Minimum viable fields only — description, group, and reason.

```bash
python manage.py emergency_change \
  --desc "Hotfix: revert auth service to v1.4.2" \
  --group "Platform" \
  --reason "Production outage — users unable to authenticate"
# → CHG0087654 created (Emergency)
```

**Uses:** `POST /servicenow/changes/create/` with `kind=emergency`

---

### 3. Change from a local template file
Store your team's common change types as JSON files checked into the repo.
Pass the file, it creates the change. No copy-pasting from last month's record.

```bash
python manage.py create_change --template templates/monthly_patching.json
# → CHG0087655 created
```

**Uses:** `POST /servicenow/changes/create/`

**Example template (`monthly_patching.json`):**
```json
{
  "kind": "normal",
  "fields": {
    "short_description": "Monthly OS patching — prod-app-cluster",
    "description": "Apply OS security patches per patch schedule.",
    "assignment_group": "<group_sys_id>",
    "risk": "2",
    "impact": "2"
  }
}
```

---

### 4. Incident from a monitoring alert payload
Pipe an alert payload directly into an incident. Useful when a Grafana or Splunk
alert fires and you want the ServiceNow record open before you even join the bridge.

```bash
cat alert_payload.json | python manage.py incident_from_alert
# → INC0045232 created with alert context in description
```

**Uses:** `POST /servicenow/incidents/create/`

---

## Retrieving Records

### 5. Look up any record by number
The single most common ops task. One command, any number type.

```bash
python manage.py sn_get CHG0034567
python manage.py sn_get INC0012345
```

**Uses:**
- `POST /servicenow/changes/get-by-number/`
- `POST /servicenow/incidents/get-by-field/` with `field=number`

---

### 6. Bulk lookup from a list
When you have a list of tickets from a handover, email, or spreadsheet.
Pass them all at once instead of looking up each one individually.

```bash
python manage.py sn_bulk_get CHG001,CHG002,CHG003
python manage.py sn_bulk_get --file numbers.txt
```

**Uses:**
- `POST /servicenow/changes/bulk-get-by-number/`
- `POST /servicenow/incidents/bulk-get-by-field/`

---

### 7. My team's open incidents
Instant snapshot of what your group is currently dealing with.

```bash
python manage.py my_incidents --group "Network Operations"
# → Lists open incidents sorted by priority and age
```

**Uses:** `POST /servicenow/table/list/`
**Query:** `assignment_group=<sys_id>^active=true^ORDERBYDESCpriority`

---

### 8. Today's scheduled changes
All changes your group has in the current or next maintenance window.
Run this before going on-call to know what's coming.

```bash
python manage.py todays_changes --group "Platform"
```

**Uses:** `POST /servicenow/presets/run/` with `recent_open_changes_by_group`

---

## Full Context Retrieval

These are the highest-value commands for on-call. One call, everything you need.

---

### 9. Change briefing
Full picture of a change before a maintenance call —
the change record, every CTASK and its status, and all attachments (runbooks, evidence).

```bash
python manage.py change_briefing CHG0034567
```

**Output:**
```
CHG0034567 — Monthly OS patching — prod-app-cluster
State:       Implement
Group:       Platform
Scheduled:   2026-04-15 22:00 UTC

CTASKs (4):
  ✓ CTASK001  Pre-change health check        Closed Complete
  ✓ CTASK002  Apply patches                  Closed Complete
  ✗ CTASK003  Post-patch validation          Open
  ✗ CTASK004  Stakeholder sign-off           Open

Attachments (2):
  runbook_v3.pdf         uploaded by j.smith
  pre_change_screenshot  uploaded by j.smith
```

**Uses:** `POST /servicenow/changes/context/`
Already returns change + CTASKs + attachments in one call — just needs formatted output.

---

### 10. Incident briefing
Everything about an incident when you're picking up someone else's P1.
Record details, all tasks, all attachments — in one command.

```bash
python manage.py incident_briefing INC0012345
```

**Output:**
```
INC0012345 — DB connection pool exhausted on prod-db-01
Priority:    P2 (Impact 2 / Urgency 2)
State:       In Progress
Assigned:    j.smith → Database Ops
Opened:      2026-04-15 14:32 UTC (1h 12m ago)

Tasks (2):
  ITASK001  Restart connection pool service   In Progress
  ITASK002  Notify affected teams             Closed Complete

Attachments (1):
  error_logs_14_32.txt   uploaded by monitoring-bot
```

**Uses:** `POST /servicenow/incidents/context/`

---

### 11. CAB prep pack
Pull the full context for every change on the CAB agenda and write it to a single file.
Run this before the CAB call instead of opening each change one by one.

```bash
python manage.py cab_pack --numbers CHG001,CHG002,CHG003 --output cab_2026_04_15.json
```

**Uses:** `POST /servicenow/changes/context/` called once per number, merged into one output file.

---

## Updating Records

On-call engineers update records constantly — acknowledging work, adding notes,
reassigning, changing state. These commands remove the UI entirely.

---

### 12. Add a work note
The most frequent update during an incident. No browser needed.

```bash
python manage.py sn_note INC0012345 "Identified root cause: connection pool config misconfigured after last deployment. Rolling back."
```

**Uses:** `POST /servicenow/incidents/patch/` with `fields_to_patch: {work_notes: "..."}`

---

### 13. Reassign a record
Reassign an incident or change to a different group or individual without opening the form.

```bash
python manage.py sn_reassign INC0012345 --group "Database Ops"
python manage.py sn_reassign INC0012345 --user "b.doe"
```

**Uses:** `POST /servicenow/incidents/patch/` with `assignment_group` or `assigned_to`

---

### 14. Change priority
Escalate or de-escalate an incident's priority when the situation changes.

```bash
python manage.py sn_priority INC0012345 --impact 1 --urgency 1
# → Priority updated to P1
```

**Uses:** `POST /servicenow/incidents/patch/` with `impact` and `urgency`

---

### 15. Bulk add work note to multiple records
During a major incident that affects multiple tickets, add the same status note to all of them at once.

```bash
python manage.py sn_bulk_note \
  --numbers INC001,INC002,INC003 \
  --note "Related to major incident INC0012345. Investigation in progress."
```

**Uses:** `POST /servicenow/incidents/patch/` called once per number

---

### 16. Progress a change state
Move a change to the next state (Implement → Review, etc.) from the command line.
Useful during a maintenance window when you don't want to tab away from your terminal.

```bash
python manage.py change_state CHG0034567 --state implement
python manage.py change_state CHG0034567 --state review
```

**Uses:** `POST /servicenow/changes/patch/` with `fields_to_patch: {state: "..."}`

---

### 17. Complete a CTASK
Mark a specific CTASK as closed complete with an optional completion note.

```bash
python manage.py close_ctask CTASK0001234 --note "Validation passed. No errors observed."
```

**Uses:** `POST /servicenow/table/get-by-field/` to resolve sys_id, then
`POST /servicenow/changes/patch/` on the change_task table

---

### 18. Bulk complete all CTASKs on a change
Mark every CTASK on a change as Closed Complete in one command.
Run this at the end of a successful maintenance window.

```bash
python manage.py complete_all_ctasks CHG0034567 --note "All steps completed successfully."
```

**Uses:**
1. `POST /servicenow/ctasks/list-for-change/` to get all CTASK sys_ids
2. `POST /servicenow/changes/patch/` on each CTASK to close it

---

## Closing Records

Getting records properly closed is often delayed because engineers are
already on to the next problem. These make closure a one-second operation.

---

### 19. Close an incident
Resolve and close an incident with a resolution code and note.

```bash
python manage.py close_incident INC0012345 \
  --resolution "Rolled back deployment v2.3.1. Connection pool recovered." \
  --code "Solved (Permanently)"
```

**Uses:** `POST /servicenow/incidents/patch/` with:
```json
{
  "state": "6",
  "close_code": "Solved (Permanently)",
  "close_notes": "..."
}
```

---

### 20. Resolve and close multiple incidents
When a major incident resolves and you have 5 child incidents to close, do them all at once.

```bash
python manage.py bulk_close_incidents \
  --numbers INC001,INC002,INC003 \
  --resolution "Resolved by fix to MajorInc INC0012345. Root cause: misconfigured connection pool."
```

**Uses:** `POST /servicenow/incidents/patch/` called once per number

---

### 21. Close a change after successful implementation
Close a change through Review to Closed in one command, adding the closure note.

```bash
python manage.py close_change CHG0034567 \
  --note "Implementation successful. All validation checks passed. No issues observed post-change."
```

**Uses:** Two sequential `POST /servicenow/changes/patch/` calls:
1. Move to Review with close note
2. Move to Closed

---

## Cancelling Records

---

### 22. Cancel a change
Cancel a change that is no longer needed, with a reason.
Catches the case where a maintenance window is abandoned mid-execution.

```bash
python manage.py cancel_change CHG0034567 \
  --reason "Postponed due to unrelated P1 incident during window. Rescheduled for next week."
```

**Uses:** `POST /servicenow/changes/patch/` with:
```json
{
  "state": "-5",
  "close_notes": "..."
}
```

---

### 23. Cancel and auto-note multiple changes
Cancel a batch of changes — useful when a release freeze is declared and
a whole sprint's worth of changes need to be pulled.

```bash
python manage.py bulk_cancel_changes \
  --numbers CHG001,CHG002,CHG003 \
  --reason "Release freeze declared 2026-04-15. Changes rescheduled post-freeze."
```

**Uses:** `POST /servicenow/changes/patch/` called once per number

---

## On-Call Handover

### 24. Incoming shift briefing
Run this when you come on-call. Pulls everything currently open for your group
— incidents by priority, changes in progress, and CTASKs due today.

```bash
python manage.py oncall_briefing --group "Platform"
```

**Output:**
```
=== ON-CALL BRIEFING — Platform — 2026-04-15 06:00 UTC ===

OPEN INCIDENTS (3)
  P1  INC0045230  Auth service degraded — 2h 10m open — assigned: j.smith
  P2  INC0045228  Slow queries on reporting DB — 4h 30m open — unassigned
  P3  INC0045201  Disk usage warning on log01 — 1d 2h open — assigned: b.doe

CHANGES IN PROGRESS (1)
  CHG0034567  Monthly OS patching  State: Implement  CTASKs: 2/4 complete

NO CHANGES SCHEDULED IN NEXT 4 HOURS
```

**Uses:**
- `POST /servicenow/table/list/` for open incidents
- `POST /servicenow/presets/run/` for changes in window
- `POST /servicenow/changes/context/` for CTASK completion counts

---

### 25. Outgoing shift handover note
Generates a structured handover note and adds it as a work note to every
active P1/P2 incident, so the incoming engineer sees it immediately on the ticket.

```bash
python manage.py handover_note \
  --group "Platform" \
  --note "Auth service: monitoring since 04:00, no further degradation observed. Awaiting dev team RCA."
```

**Uses:**
- `POST /servicenow/table/list/` to find open P1/P2 incidents
- `POST /servicenow/incidents/patch/` to add work note to each

---

## Suggested Build Order

Based on frequency of use during an on-call shift:

| Priority | Command | Why |
|----------|---------|-----|
| 1 | `incident_briefing` / `change_briefing` | Used immediately when picking up any ticket |
| 2 | `sn_note` | Most frequent action during an active incident |
| 3 | `sn_get` | Constant lookups throughout a shift |
| 4 | `close_incident` / `close_change` | End-of-incident hygiene |
| 5 | `oncall_briefing` | First thing run at shift start |
| 6 | `create_incident` | Fast record creation when an alert fires |
| 7 | `sn_reassign` | Delegation and escalation |
| 8 | `bulk_close_incidents` | Post-major-incident cleanup |
| 9 | `cancel_change` | Maintenance window abandonment |
| 10 | `cab_pack` | Pre-CAB preparation |

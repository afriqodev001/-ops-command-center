# ServiceNow Automation Ideas

## Context

Most corporate environments restrict direct ServiceNow REST API access to approved integrations only. This app bypasses that constraint by executing all API calls from inside an authenticated Edge browser session — meaning the calls arrive at ServiceNow with the user's own SSO credentials, subject to their normal permissions, and indistinguishable from browser traffic.

This opens up automation that would otherwise require a dedicated integration account, API key provisioning, firewall exceptions, or an approved ITSM integration project. Any operations team member can run these automations immediately, without IT involvement.

The ideas below are grouped by domain. Each one is buildable with the existing `SeleniumRunner`, `fetch_json_in_browser`, and Table API infrastructure already in place.

---

## 1. Incident Management

### Triage & Assignment
- **Auto-assign by keyword** — Scan `short_description` and `description` for keywords (e.g. "database", "network", "login") and auto-assign to the correct group, removing the triage queue bottleneck
- **Bulk reassignment** — Reassign all open incidents from one group/person to another in a single operation (handles team restructuring, departures, role changes)
- **Auto-escalate by age** — Escalate incidents that have been open beyond a threshold without activity (e.g. P2 unacknowledged for 30 minutes)
- **Round-robin assignment** — Distribute unassigned incidents evenly across available team members within a group
- **On-call routing** — Query an on-call schedule (from another system or a ServiceNow table) and auto-assign incoming P1/P2 incidents to the current on-call engineer

### Enrichment
- **Auto-fill missing fields** — Scan open incidents for missing required fields (category, subcategory, business service, impact/urgency) and fill them based on existing patterns or keyword matching
- **Duplicate detection** — Identify incidents with near-identical `short_description` values opened in the same window and prompt to merge or link them
- **Auto-link related incidents** — When a major incident is created, automatically find all open incidents with matching keywords and link them as children
- **Suggest CI (Configuration Item)** — Match incident description against known CI names and auto-populate the affected CI field

### Lifecycle
- **Bulk close resolved incidents** — Close all incidents in "Resolved" state older than N days that have had no customer response
- **Auto-reopen on activity** — Monitor resolved incidents for new inbound emails or notes and automatically reopen them
- **Stale ticket nagger** — Add a work note to any incident with no update in X days, prompting the assignee to provide a status
- **Auto-acknowledge P1s** — Set state to "In Progress" and add a standard acknowledgment note the moment a P1 is created, satisfying SLA acknowledgment timers
- **SLA breach pre-warning** — 30 minutes before SLA breach, add a work note, change priority, and/or notify the assignee's manager via a separate channel

### Reporting
- **On-call handover report** — Pull all incidents opened, updated, and resolved in the last 12 hours for a specific group and format into a handover summary
- **Daily team briefing** — Every morning, generate a digest of each team member's open incidents with age, priority, and last update
- **MTTR tracker** — Calculate Mean Time to Resolve per team, per category, per month, pulling raw data from ServiceNow and outputting to a report
- **SLA compliance report** — For a given group and time period, calculate what percentage of incidents met SLA targets
- **Incident volume trending** — Pull incident counts by day/week, grouped by category or service, to identify recurring problem areas

---

## 2. Change Management

### Creation & Templating
- **Clone recurring change** — Copy a previously approved standard change (fields, CTASKs, attachments) and create a new one for the next maintenance window, with date/time updated
- **Bulk change creation** — Given a list of systems and a maintenance template, create one change per system automatically (useful for patching campaigns)
- **Change from deployment pipeline** — Triggered by a CI/CD pipeline event, auto-create a Normal or Emergency change with commit details, affected services, and rollback plan pre-filled
- **Standard change auto-opener** — Open the correct standard change template UI in a headed browser with all known fields pre-filled, so the engineer just reviews and submits

### Validation & Risk
- **Pre-submission checklist** — Before a change moves to "Review", validate that all mandatory fields are populated, all CTASKs exist, and at least one attachment (runbook/evidence) is present
- **Change collision detection** — Query all approved changes in a given maintenance window and flag overlapping assignment groups or shared CIs
- **CAB pack generator** — For all changes scheduled for the next CAB, pull full details (description, risk, affected CIs, group, attachments) and assemble into a structured summary document
- **Freeze period enforcer** — During release freeze windows, detect new Normal/Emergency changes being submitted and add a warning work note with the freeze policy

### Evidence & Closure
- **Post-change evidence collector** — After a change moves to "Review" state, automatically gather all work notes, attachments, and CTASK completion statuses into a single evidence bundle
- **CTASK bulk completion** — Mark all CTASKs on a change as "Closed Complete" once the parent change is confirmed successful, avoiding manual closure of 10-20 individual tasks
- **Auto-close implemented changes** — Changes that have been in "Implement" state for more than the expected window, with all CTASKs closed, can be automatically moved to "Review" with a completion note
- **Change metrics report** — Track change success/failure rates, emergency change frequency, and lead time per team over a rolling 90-day window

### CTASK Automation
- **CTASK creation from template** — Given a change type and a CTASK template library, auto-create the standard set of CTASKs (pre-checks, execution, validation, rollback readiness) on every new change
- **CTASK assignment routing** — Auto-assign CTASKs to specific sub-teams based on their short_description (e.g. "DB validation" → DBA team, "firewall rule" → network team)
- **CTASK dependency sequencing** — Add work notes indicating which CTASKs must be completed before others can begin, enforcing an ordered execution checklist
- **Parallel CTASK status board** — Poll all in-progress CTASKs for a change and display a live completion board, so the change coordinator sees real-time progress during the maintenance window

---

## 3. Workflow & Approval Automation

- **Standard change auto-approval** — For pre-approved standard changes with a matching template, skip manual CAB review and move directly to "Approved" state with a note referencing the approval authority
- **Approval reminder escalation** — If a change has been in "Review" (awaiting approval) for more than N hours, add a work note and notify the approver group
- **Bulk approve low-risk changes** — For changes meeting specific criteria (standard type, same group, same CI, no conflicts), approve a batch in one operation before CAB
- **State machine enforcer** — Detect changes or incidents stuck in invalid state transitions and either fix them or flag them for manual review
- **Auto-progress P1 incident workflow** — When a P1 is created: acknowledge → assign on-call → create bridge work note → notify stakeholder group, all as a single triggered sequence

---

## 4. Reporting & Intelligence

### Operational Dashboards
- **Group workload snapshot** — For any assignment group, show count of open incidents by priority, open changes by state, and CTASKs due today
- **Engineer workload comparison** — Compare open ticket counts and age across all members of a group to identify overloaded or underloaded engineers
- **Stale work report** — All tickets (incidents, changes, CTASKs) with no update in the last 7 days, grouped by owner
- **Upcoming maintenance window report** — All approved changes scheduled in the next 48 hours, with their group, CIs, and CTASK counts

### Trend Analysis
- **Recurring incident detector** — Find incidents with the same short_description or CI that have been opened more than N times in 90 days — candidates for Problem records
- **Change failure rate by group** — Track which groups have the highest rate of changes moved to "Cancelled" or "Failed" for management review
- **Incident-to-change correlation** — For a given time period, identify CIs that appear in both incident and change records frequently, suggesting instability linked to changes
- **Peak volume analysis** — Break down incident creation by hour of day and day of week to identify staffing gaps

### Audit & Compliance
- **Change evidence audit** — For a completed change, verify that all required evidence attachments exist, all CTASKs are closed, and work notes contain expected keywords
- **SOX/compliance change report** — For a given date range, pull all changes touching regulated systems with approver names and timestamps
- **Orphaned record finder** — Find CTASKs with no parent change, incidents with no assignment group, or changes with no scheduled window
- **Field change audit trail** — Track changes to specific sensitive fields (e.g. assignment_group changes on P1 incidents) over a time period

---

## 5. Integration & Cross-Tool Automation

### Inbound (other tools → ServiceNow)
- **Grafana alert → Incident** — When Grafana fires an alert, auto-create a ServiceNow incident with the alert name, dashboard link, and affected service pre-filled
- **Splunk alert → Incident** — Same pattern for Splunk SIEM alerts, with the search query and event count included in the description
- **Deployment pipeline → Change** — A successful or failed deployment triggers creation or update of the associated Change Request with deployment metadata
- **Git commit → Change work note** — When a commit is merged to a release branch, add a work note to the associated change with the commit hash, author, and summary
- **PagerDuty/OpsGenie alert → Incident** — Translate an alerting platform event into a ServiceNow incident and keep both systems in sync

### Outbound (ServiceNow → other tools)
- **P1 incident → Teams/Slack alert** — When a P1 is created, post a formatted message to the ops channel with number, description, assignee, and a direct link
- **Change approved → Teams notification** — Notify the change owner's channel when their change moves to Approved state
- **SLA breach → email escalation** — When SLA is breached, send a formatted email to the team lead with incident details and the current assignee
- **Change scheduled → calendar invite** — Create a calendar event for the change window with all stakeholders, using change details as the description
- **Daily digest → email/Teams** — A scheduled job that generates and delivers the ops team's daily briefing to a Teams channel or email distribution list

---

## 6. Data Quality & Hygiene

- **Missing CI fixer** — Find all open incidents with no Configuration Item set and attempt to match one from the description text against the CMDB
- **Category normaliser** — Detect incidents categorised as "Other" or with no subcategory and re-categorise based on keyword rules
- **Duplicate group name resolver** — Identify incidents where assignment_group names are inconsistent (e.g. "Network Ops" vs "Network Operations") and standardise
- **Stale change cleanup** — Identify changes that missed their maintenance window (scheduled date in the past, state still "Approved") and move them to "Cancelled" with a note
- **Work note quality checker** — Flag tickets where the only work notes are automated system updates (no human notes), indicating the assignee has not engaged
- **Short description length enforcer** — Flag incidents or changes where `short_description` is fewer than 15 characters (e.g. "issue", "broken", "help") and prompt for a better description

---

## 7. On-Call & Scheduling

- **On-call schedule sync** — Pull on-call rotation from PagerDuty/OpsGenie and update a ServiceNow on-call table or group membership accordingly
- **Shift handover automation** — At shift change time, generate a handover pack (open P1/P2 incidents, pending changes, active CTASKs) and deliver it to the incoming team
- **After-hours P1 auto-escalation** — Outside of business hours, if a P1 is not acknowledged within 5 minutes, automatically escalate to the on-call manager
- **Weekend change freeze check** — On Fridays before a freeze period, scan for any approved Normal changes scheduled over the weekend and add a warning note

---

## 8. Knowledge & Resolution

- **Similar incident finder** — When a new incident is created, query for historical incidents with matching keywords and add the top 3 most relevant as related records
- **Auto-link KB articles** — Search the ServiceNow Knowledge Base for articles matching the incident's category and keywords, and attach the top result as a related link
- **Resolution template suggester** — Based on the category and CI of a new incident, add a work note with a pre-formatted resolution template pulled from a local library
- **Post-incident review generator** — For closed P1 incidents, automatically compile a structured post-mortem template (timeline, impact, root cause placeholder, action items) from the incident's work notes and timestamps

---

## 9. UI & Browser Automation (headless or headed)

These require direct browser interaction rather than Table API calls — the headed browser capability makes them possible even when no API equivalent exists.

- **Form pre-filler** — Open any ServiceNow form (change, incident, request) with fields pre-populated from a local data source, so engineers just review and submit
- **Screenshot evidence capture** — Navigate to a specific incident or change record and take a timestamped screenshot for audit evidence
- **Record printer/exporter** — Open a change or incident in print view and save it as a PDF, automatically naming the file with the record number
- **Approval click automation** — For standard changes where the approver criteria are always met, automatically click the Approve button in the UI (for instances where the Table API PATCH to approval state is restricted)
- **Bulk form navigation** — Open a list of record numbers in sequence, apply a standard UI action to each, and close — useful for operations that have no API equivalent
- **Tabular data scraper** — When the Table API returns restricted fields, scrape the rendered HTML table view of a record set instead, returning the same structured data

---

## 10. Scheduling & Periodic Jobs (Celery Beat)

These become periodic background jobs once Celery Beat is configured:

- **Hourly SLA sweep** — Every hour, check all P1/P2 incidents for approaching SLA breaches and send pre-warnings
- **Daily hygiene sweep** — Every morning at 07:00, run data quality checks and deliver a hygiene report to the ops lead
- **Weekly metrics report** — Every Monday, generate and deliver the previous week's incident and change metrics
- **Nightly stale ticket sweep** — Every night, flag or close tickets matching staleness criteria
- **Change window reminder** — 2 hours before any scheduled change window, notify the change owner with a checklist
- **On-call sync** — Every 15 minutes, sync the current on-call engineer from the alerting platform to the ServiceNow on-call table

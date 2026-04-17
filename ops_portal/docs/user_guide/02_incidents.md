# Incidents

**Paths:**
- List: `/servicenow/incidents/`
- Detail: `/servicenow/incidents/<INC_NUMBER>/`

Browse and triage incidents. The list supports priority, state, and free-text filters; each row links to a detail view with work notes, tasks, and attachments.

## When to use it

- Find an incident by priority or state for bridge calls / triage.
- Look at the full context of a specific incident — history, attachments, related tasks.
- Launch a create action for a new incident from a known template.

## List page layout

```
┌─────────────────────────────────────────────────────────┐
│ Priority:  [All] [P1] [P2] [P3] [P4]                    │
│ State:     [All] [Open] [In Progress] [Resolved]        │
│ Search:    [ free text matches number or description ]  │
├─────────────────────────────────────────────────────────┤
│ Number      Description        Priority  State   Group  │
│ INC0045231  DB pool exhausted  P1        WIP     DB Ops │
│ INC0045228  Slow queries       P2        WIP     DB Ops │
│ ...                                                     │
└─────────────────────────────────────────────────────────┘
```

### Header actions
| Button             | What it does |
| ------------------ | ------------ |
| **New from template** | Opens the shared create-from-template modal scoped to `incident` templates. See [Templates](09_templates.md). |
| **New Incident**      | Opens the blank-form create dialog (Alpine event `open-create-incident`). |

### Filters
Filters combine with AND. Empty filters match all.

- **Priority** — P1..P4 or All
- **State** — Open, In Progress, Resolved, or All
- **Search** — case-insensitive substring match on `number` and `short_description`
- **Time range** — defaults to **Last 30 days** (filters by `opened_at`). Options: 7 / 30 / 90 / 365 days or All time. Picking a wider range matters when you're troubleshooting older issues.

### Default group filter
If a **default group filter** is set in Preferences (e.g. `CTULMS - Retail Services`), the list is automatically scoped to records whose `assignment_group.parent` matches. A visible chip above the table shows the active filter; click **×** or **clear** to remove it for the current page without changing the saved preference.

### Result cap
The list is capped at 200 rows to stay responsive on large ServiceNow instances. A banner under the filter row shows **"Showing X of Y matches — capped at 200"** when your filter set matched more. Narrow filters (or shorten the time range) to see the rest.

## How to use it

1. **Pick a priority** (e.g. P1) to narrow the list.
2. **Optionally refine** with a state or search term.
3. **Click a row** (the Number column) to open the detail page.

## Detail page

Shows for the selected incident:

| Section         | Contents |
| --------------- | -------- |
| Header          | Number, priority badge, state badge, age, SLA warning dot |
| Summary         | Short description, assignment group, assignee |
| Work notes      | Reverse chronological feed of updates |
| Tasks           | Child tasks (ITASK*) with state + assignee |
| Attachments     | File name, size, uploader, timestamp |

## Examples

**Example 1 — Find all open P1s**
1. Click **P1** in Priority filter.
2. Click **Open** and **In Progress** in State.
3. List now shows only open P1s ordered oldest first.

**Example 2 — Jump to a known incident**
- If you know the number, the [Fetch by Number](06_fetch_by_number.md) page is faster than scrolling the list.
- Otherwise paste keywords into the search box (e.g. `pool`) to narrow.

**Example 3 — Create a new P1 incident from a template**
1. Click **New from template** in the header.
2. Pick an `incident` template from the list (e.g. `p1_bridge`).
3. Edit the pre-filled fields (short_description is required).
4. Click **Create**. A task watcher shows progress; on success you get a clickable INC number.

## Tips

- If the list feels empty after filtering, one of the filters is too narrow — clear them one at a time.
- The SLA-warning dot on a row is purely visual; the source of truth is still ServiceNow's SLA view.
- The detail page is read-only today. To edit, click through to the ServiceNow record (not yet wired as a single-click action).

## See also
- [Search](07_search.md) for CI / requester / assignment-group filtering
- [Templates](09_templates.md) for saved incident creation payloads
- [Fetch by Number](06_fetch_by_number.md) when you already know the INC number

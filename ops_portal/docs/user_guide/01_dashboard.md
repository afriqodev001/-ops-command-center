# Dashboard

**Path:** `/`

The first page you see on login. A compact operational snapshot designed to surface what needs attention right now.

## When to use it

- Start of shift — quick read of open incident load and in-flight changes.
- After an alert — sanity check whether the broader picture has anything new.
- Handover — point at the page during a stand-up to show current state.

## Page layout

```
┌─────────────────────────────────────────────────────────────┐
│  STATS                                                      │
│  [ Open P1 · 1 ]  [ Open P2 · 2 ]  [ Implementing · 1 ]     │
│  [ Open incidents · 5 ]  [ Awaiting review · 1 ]            │
├─────────────────────────────────────────────────────────────┤
│  RECENT INCIDENTS           │  TODAY'S CHANGES              │
│  INC0045231  DB pool...     │  CHG0034567  OS patching 60%  │
│  INC0045228  Slow queries.. │  CHG0034560  Firewall update  │
│  INC0045225  Auth 401s...   │  CHG0034558  Index rebuild    │
│  INC0045220  High CPU...    │                               │
└─────────────────────────────────────────────────────────────┘
```

### Stats row
Five tiles:
| Tile              | Source                                |
| ----------------- | ------------------------------------- |
| Open P1           | Incidents with `priority=1` and state ∉ Resolved/Closed |
| Open P2           | Incidents with `priority=2`           |
| Open incidents    | All non-resolved incidents            |
| Implementing      | Changes with `state=Implement`        |
| Awaiting review   | Changes with `state=Review`           |

### Recent incidents panel
Up to 4 most-recent non-resolved incidents. Each row links to the incident detail page.

### Today's changes panel
Up to 3 changes scheduled today, with CTASK completion progress bar (closed / total %).

## How to use it

1. **Drill in** — click any incident or change number to open its detail page.
2. **Focus on fires** — if the Open P1 tile is ≥ 1, expand the incidents list below; otherwise triage normally.
3. **Refresh** — the dashboard is static per page-load. Navigate away and back (or hit ⟳) to re-read.

## Examples

**Example 1 — "Am I on fire?"**
Look at the top-left Open P1 tile. If it's `0`, breathe. If it's ≥ `1`, the most recent P1 incident appears in the Recent Incidents panel below.

**Example 2 — "What's happening tonight?"**
Right-side panel shows today's scheduled changes. Progress bar tells you how far along each one is — 100% means all CTASKs closed, so post-implementation review is likely the next step.

## Tips

- Counts reflect demo data today. Once wired to real ServiceNow, they'll reflect
  your instance totals within the widget's refresh window.
- If a change is missing from today's list, it's either scheduled for another day
  or sliced out by the top-3 cap. Use the Changes page to see the full list.

## See also
- [Incidents](02_incidents.md) for the full filterable list
- [Changes](03_changes.md) for change detail and CTASK progress

# Fetch by Number

**Path:** `/servicenow/lookup/`
**Sidebar label:** "Fetch by number"

Paste a list of INC/CHG numbers and get the full record for each. This is a resolve/fetch operation — when you already know the number.

## When to use it

- A colleague sent you a list of ticket numbers; you want the full context without manually opening each one.
- You're auditing a cluster of related tickets and want them side-by-side.
- You have a CSV of identifiers and want to batch-check status.

For *filter-based* finding ("all changes for Database Ops"), use [Search](07_search.md) instead.

## Page layout

```
┌─────────────────────────────────────────────────────────┐
│  Paste INC / CHG numbers                                │
│  ┌───────────────────────────────────────────────────┐  │
│  │ INC0045231                                        │  │
│  │ CHG0034567, CHG0034560                            │  │
│  │ INC0045228                                        │  │
│  └───────────────────────────────────────────────────┘  │
│  [ Fetch ]  [ Clear ]                                   │
├─────────────────────────────────────────────────────────┤
│  RESULTS                                                │
│  Not found: ABC123                                      │
│                                                         │
│  ── Incidents (2)                                       │
│  INC0045231  P1 · DB pool · DB Ops · J. Smith           │
│  INC0045228  P2 · Slow queries · DB Ops · (unassigned)  │
│                                                         │
│  ── Changes (2)                                         │
│  CHG0034567  Normal · Implement · Platform · 60% CTASKs │
│  CHG0034560  Normal · Scheduled · Network Ops · 33%     │
└─────────────────────────────────────────────────────────┘
```

## How to use it

1. **Paste numbers** into the textarea. Any whitespace, comma, semicolon, slash, or pipe works as a separator.
2. Click **Fetch**. Results swap in below without a page reload.
3. Numbers are routed by prefix:
   - `INC…` → looked up in the incidents table.
   - `CHG…` → looked up in the changes table.
   - Anything else (or a miss) lands in the **Not found** chip list.

## Examples

**Example 1 — Mixed paste**
Input:
```
INC0045231
CHG0034567
CHG0034560
ABC123
```
Result:
- 1 incident and 2 changes in the results section
- `ABC123` shown in Not found

**Example 2 — Paste from a chat message**
```
Hey, can you check CHG0034567 and CHG0034558?
Also INC0045228 (P2, still open).
```
The parser strips the surrounding prose and finds all three numbers.

**Example 3 — Single number**
Paste just one number and click **Fetch** for a quick one-off resolve.

## Tips

- Numbers are case-insensitive and whitespace-insensitive — `  chg0034567  ` works.
- The **Clear** button resets both the textarea and the results panel.
- If the results scroll is long, the page auto-scrolls to show the first result after fetch.
- This page resolves exact numbers only — partial matches or free-text goes on the [Search](07_search.md) page.

## Difference from Search

| Task                                         | Use                        |
| -------------------------------------------- | -------------------------- |
| I have specific INC/CHG numbers              | **Fetch by Number** (this) |
| I need records by CI / group / requester     | [Search](07_search.md)     |
| I want a saved, named ServiceNow query       | [Presets](08_presets.md)   |

## See also
- [Search](07_search.md) — filter-driven finding
- [Bulk Change Review](04_bulk_change_review.md) — paste CHG numbers and get heuristic reviews

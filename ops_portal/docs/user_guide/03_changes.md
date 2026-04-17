# Changes

**Paths:**
- List: `/servicenow/changes/`
- Detail: `/servicenow/changes/<CHG_NUMBER>/`
- Briefing: `/servicenow/changes/<CHG_NUMBER>/briefing/`

Browse change requests, inspect a single change's details and CTASK progress, and generate an AI-ready briefing prompt for review.

## When to use it

- Find changes in a particular state (Implement / Scheduled / Review).
- Check CTASK completion before approving.
- Generate a structured prompt to feed into Claude / GPT for change-review assistance.

## List page layout

```
┌─────────────────────────────────────────────────────────┐
│ State: [All] [Scheduled] [Implement] [Review] [...]     │
│ Search: [ free text matches number or description ]     │
├─────────────────────────────────────────────────────────┤
│ Number      Description       Type    State   CTASK %   │
│ CHG0034567  OS patching       Normal  Imp.    3/5 · 60% │
│ CHG0034560  Firewall update   Normal  Sched.  1/3 · 33% │
│ ...                                                     │
└─────────────────────────────────────────────────────────┘
```

### Header actions
| Button                | What it does |
| --------------------- | ------------ |
| **Bulk Review**       | Go to the [Bulk Change Review](04_bulk_change_review.md) page. |
| **New from template** | Opens the shared create-from-template modal scoped to change templates (tabs: Standard / Normal / Emergency). |
| **New Change**        | Blank-form create dialog. |

### Filters
- **State tabs** — All / Scheduled / Implementing / Review / Approved. Selecting a tab preserves the time range.
- **Search box** — case-insensitive substring on `number` and `short_description`.
- **Time range** — defaults to **Last 30 days** (filters by `start_date`). Options: 7 / 30 / 90 / 365 / All time.

### Default group filter
If a **default group filter** is set in Preferences (e.g. `CTULMS - Retail Services`), the list is automatically scoped to records whose `assignment_group.parent` matches. A chip above the table shows the active filter with a **×** clear button. The filter is preserved across state-tab clicks.

### Result cap
Capped at 200 rows. A banner below the filter row reads **"Showing X of Y matches — capped at 200"** when the underlying match set is larger. Narrow the state tab, add a search term, or shorten the time range.

## Detail page

Shows for the selected change:

| Section        | Contents |
| -------------- | -------- |
| Header         | Number, type, state, risk, assignment group |
| Schedule       | Scheduled start time, assignee |
| CTASK progress | Progress bar + per-task list with state |
| Work notes     | Reverse chronological feed |
| Attachments    | Files uploaded to the change |
| **AI briefing**| Button to open the briefing page |

## Briefing page

Generates a structured prompt an LLM can use to produce a change-review assessment.

### Prompt structure

The prompt (fixed 64-char section dividers) contains:
1. **Instructions** — role (experienced IT change management reviewer), what to assess (readiness, risk, recommendation).
2. **CHANGE RECORD** — number, type, risk, state, group, assignee, start, description.
3. **IMPLEMENTATION TASKS** — all CTASKs with status markers `[DONE]` / `[WIP]` / `[OPEN]`.
4. **WORK NOTES** — reverse chronological.
5. **ATTACHMENTS** — name, size, uploader, time.
6. **Final instruction** — "Provide your change review assessment now."

### Actions on the briefing page

| Action            | Effect |
| ----------------- | ------ |
| **Copy prompt**   | Copies the full prompt to your clipboard (paste into Claude, ChatGPT, etc.). |
| **Generate**      | HTMX POST to `/changes/<n>/briefing/generate/` — returns the AI response panel. Currently a placeholder until the AI backend is wired. |
| **Back to change**| Returns to the change detail page. |

## Examples

**Example 1 — Find all changes currently implementing**
1. Click **Implement** in the state tabs on the list page.
2. Review the CTASK % column. Any change at < 100% is still in progress.

**Example 2 — Review a change for CAB approval**
1. Open the change detail page.
2. Click **Briefing** to view the structured prompt.
3. Click **Copy prompt** and paste it into your LLM of choice.
4. Paste the LLM's response back to your team / ticket.

**Example 3 — Create an emergency change from a saved template**
1. On the list page, click **New from template**.
2. In the modal, click the **Emergency** tab.
3. Pick a template like `dns_hotfix`.
4. Tweak fields, click **Create**. Watcher shows the CHG number once the Table API task completes.

## Tips

- CTASK % is computed as `closed_complete_tasks / total_tasks`. A change with zero tasks shows 0% — not a bug, but a signal the change has no defined steps.
- The briefing page generates the prompt server-side on every load, so the content reflects the change's current state (not a cached snapshot).
- Risk badge coloring: `Low` (gray) → `Moderate` (yellow) → `High` / `Critical` (red). Use as a visual filter when scanning.

## See also
- [Bulk Change Review](04_bulk_change_review.md) for reviewing N changes at once
- [Bulk Change Create](05_bulk_change_create.md) for creating N changes at once
- [Templates](09_templates.md) for reusable change payloads

# Bulk Change Review

**Path:** `/servicenow/changes/bulk-review/`

Paste a list of CHG numbers, get a review card for each with heuristic checks (CTASK completeness, risk, evidence of work). Designed for batch CAB preparation.

## When to use it

- Pre-CAB triage — sort a list of 10–30 pending changes into APPROVE / HOLD / REVIEW buckets in minutes.
- Handoff preparation — give the next shift a pre-digested summary of in-flight work.
- Exception hunting — quickly find changes that look risky or incomplete.

## Page layout

```
┌─────────────────────────────────────────────────────────┐
│  Paste change numbers (comma, space, or line-separated) │
│  ┌───────────────────────────────────────────────────┐  │
│  │ CHG0034567                                        │  │
│  │ CHG0034560, CHG0034558                            │  │
│  │ CHG0034550                                        │  │
│  └───────────────────────────────────────────────────┘  │
│  [ Review ]                                             │
├─────────────────────────────────────────────────────────┤
│  Review cards (one per CHG, rendered progressively)     │
│  ┌───────────────────────────────────────────────────┐  │
│  │ CHG0034567  Normal · Implement · Moderate risk    │  │
│  │ RECOMMENDATION: REVIEW                            │  │
│  │ ✅ 3 work notes recorded                          │  │
│  │ ⚠ 2 task(s) still open (60% done)                 │  │
│  │ ...                                               │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## How it works

1. **Paste numbers** — free-form. Any whitespace, comma, pipe, slash, or semicolon is treated as a separator.
2. **Click Review**. The page returns a queue of pending cards (one per CHG).
3. Each card fires its own HTMX request to `/changes/bulk-review/item/` to fetch the full review. They render progressively — staggered by 700 ms — so you see results as they finish instead of waiting for the slowest.
4. Each card shows a **recommendation** (APPROVE / HOLD / REVIEW) computed from heuristics.

## Heuristic recommendation logic

The current heuristic reviewer (placeholder until AI is wired) applies these rules:

| Signal                        | Effect |
| ----------------------------- | ------ |
| All CTASKs closed, non-High risk, has notes + attachments | APPROVE |
| 0% CTASKs complete OR 3+ flags | HOLD |
| High/Critical risk at <100% CTASKs | HOLD |
| Everything else | REVIEW |

Flags raised per card (examples):
- `No CTASKs defined — scope unclear`
- `Only 40% of tasks complete (2/5)`
- `High risk — requires thorough review`
- `No work notes — no evidence of activity documented`
- `No attachments — runbook or evidence not uploaded`

Positives shown per card:
- `All 5 task(s) closed`
- `3 work note(s) recorded`
- `2 attachment(s) present`

## Examples

**Example 1 — Weekly CAB prep**
1. Copy the list of pending CHG numbers from your CAB tracker.
2. Paste into the textarea, click **Review**.
3. Scan the recommendation badge on each card. APPROVE cards can be batched; HOLD cards go back to owners.

**Example 2 — Not-found numbers**
Numbers that don't resolve to a change appear in a "Not found" chip list at the top. Typos and wrong prefixes (e.g. `CH0034567` instead of `CHG0034567`) show up here.

**Example 3 — Just paste from email**
The parser is lenient — paste directly from an email:
```
Please review:
• CHG0034567
• CHG0034560 / CHG0034558
Thanks,
```
The parser extracts all three numbers and ignores the bullets/text.

## Tips

- You can review up to a few dozen at once; staggering prevents overwhelming the API.
- Recommendation is a **signal, not an authority** — still read the flags and open the change detail for anything non-obvious.
- The AI-backed reviewer is planned; when wired, the recommendation comes from the same prompt the [Briefing](03_changes.md) page generates.
- If a card stays in pending state, the underlying fetch failed — refresh the page to retry.

## See also
- [Changes](03_changes.md) for the detail view and briefing page of a single change
- [Bulk Change Create](05_bulk_change_create.md) for the other-direction bulk flow

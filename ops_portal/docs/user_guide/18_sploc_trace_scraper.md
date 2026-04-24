# SPLOC Trace Scraper

Extract the full waterfall span list from any SignalFx trace — service, operation, duration, parent-child depth — and optionally run AI analysis on it.

## Page: `/sploc/traces/`

## Layout

- **Left panel** — **Recent Traces** (one-click re-run of past scrapes), **How it works** steps, AI tip
- **Center** — scrape form + results area

## Running a Scrape

1. Paste a **Trace ID** (32-char hex from SignalFx, e.g. `ec5b3fa0339376af5bb4930e02be596c`)
2. Enter the **Service Name** — starts typing pulls from your [Service Catalog](21_sploc_service_catalog.md) as an autocomplete dropdown. Free-typing a service not in the catalog still works.
3. (Optional) **Advanced options** → set a **Max Spans** safety cap
4. Click **Scrape Trace**

The app drives your authenticated Edge session, navigates to the trace, opens the Waterfall tab, and scrolls through the full list capturing every span.

## Results

Results render in three tabs:

- **Waterfall** — sortable table (`#`, Service, Operation, Duration, Depth) with an inline filter box. Service appears as a colored chip; depth shows as an indent value.
- **Services** — unique service list with counts. Quick overview of who's in this trace.
- **Raw JSON** — full response payload with copy-to-clipboard

### Actions

- **Export JSON** — full result as a pretty-printed JSON file
- **Export TSV** — spreadsheet-friendly rows, one span per line
- **Search Splunk for this trace** — opens `/splunk/` with `index=* "<trace_id>"` pre-populated and auto-running (default `-1h`). Click **Custom range** first to pick a different time window.
- **Analyze with AI** — see below

## AI Trace Analysis

The **AI Actions** section below the results lets you run a structured analysis:

1. (Optional) add a **context question** in the textarea ("Why is auth-service so slow?")
2. Click **Analyze with AI**
3. The app uploads the full trace JSON to your AI provider (Tachyon by default) with the `sploc_trace_analysis` system prompt

The AI returns markdown with these sections:
- **Trace Summary** — total spans, services, call graph shape
- **Critical Path & Bottlenecks** — slowest operations with ⚠️ on anomalies
- **Service Breakdown** — span counts, repeated-operation patterns (N+1)
- **Errors & Concerns** — unusual patterns, missing data, outliers
- **Recommendations** — actionable next steps referencing specific span IDs

### Preflight

Before dispatching, the app verifies:
- Tachyon is connected (browser alive on debug port)
- The configured Tachyon preset exists and is enabled

If either check fails, you get an immediate red error card with a one-click link to fix it (**Open Tachyon** or **Manage presets**). No more watching a spinner for 30 seconds before the task times out.

## Recent Traces

Every successful scrape is saved to a local JSON file (`trace_history.json`) — newest first, dedup'd by `(trace_id, service_name)`, capped at 30.

- Click a recent entry → form is prefilled and auto-submits
- Hover → small × appears for per-item delete
- **Clear** at the top of the panel wipes all history

## Session Requirement

Scraping requires an active SPLOC browser session (green widget). The button is disabled otherwise.

## Tips

- **Service names are case-sensitive** — paste exactly what SignalFx displays. Add frequently-used ones to your [Service Catalog](21_sploc_service_catalog.md) so the autocomplete handles typos for you.
- **Long traces (>500 spans)** can take 15+ seconds — the scroll loop waits for new spans to load
- **Max spans = 0** means unlimited; set a cap if you just want a sample
- **Cross-app flow** — from a Splunk search result that contains a trace_id, the SPLOC link under the event raw auto-detects the ID and prefills the scrape form for you

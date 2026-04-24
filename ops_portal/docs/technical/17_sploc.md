# SPLOC (Splunk Observability Cloud / SignalFx)

Browser-authenticated trace waterfall scraping and AI Assistant querying for SignalFx APM. Mirrors the Splunk integration pattern: runner + services + Celery tasks + HTMX UI + session widget.

## Architecture

```
UI (pages.py) → Celery task → SplocRunner → Selenium driver → SignalFx UI DOM
```

Unlike Splunk (REST API calls via browser fetch), SPLOC **scrapes the DOM** of the SignalFx SPA — the trace waterfall and AI Assistant panel don't have stable public REST endpoints we can hit, so we drive the UI via Selenium JavaScript execution.

## Key Files

```
sploc/
├── pages.py                 # HTML views + HTMX partials (trace + AI flows, preset CRUD, recents)
├── views.py                 # JSON API endpoints (login/open, trace scrape, AI ask)
├── tasks.py                 # 3 Celery tasks: login, trace scrape, AI ask
├── session_views.py         # sidebar widget, connect/close/reset
├── auth.py                  # URL-based auth check (on signalfx.com = authed)
├── urls.py                  # all routes
├── url_builders.py          # APM / trace / service URL construction
├── runners/
│   └── sploc_runner.py      # SeleniumRunner subclass, Mode B
└── services/
    ├── trace_scraper.py     # scrape_trace_waterfall(driver, trace_id, service_name)
    ├── ai_assistant.py      # ask_ai_assistant(driver, prompt, ...)
    ├── prompt_packs.py      # file-backed prompt pack store with built-ins
    ├── trace_history.py     # file-backed recent traces (dedup, cap 30)
    └── service_catalog.py   # file-backed SignalFx service name list (no built-ins)
```

## Settings

```python
SPLOC_BASE = 'https://your-org.signalfx.com'
SPLOC_APM_PATH = '/#/apm'
SPLOC_RESPONSE_TIMEOUT = 120          # max seconds to wait for AI response
SPLOC_STABLE_WINDOW = 1.25            # seconds of stable text = response done
SPLOC_SCROLL_STEP_FACTOR = 0.85       # waterfall scroll step (fraction of viewport)
SPLOC_NO_NEW_LIMIT = 6                # stop scrolling after N scrolls with no new spans
SPLOC_MAX_SPANS = 0                   # safety cap (0 = unlimited)
```

## Auth Check

SignalFx uses enterprise SSO (Okta, ADFS, Azure AD). Rather than probing a REST endpoint (the SignalFx REST API lives on `api.<realm>.signalfx.com`, not the UI host — probes return 404), we check the post-navigation URL:

- Authed → URL stays on `signalfx.com`
- Unauthed → IdP takes over, URL changes to `okta.com`, `microsoftonline.com`, etc.

See `sploc/auth.py`.

## Trace Scraping Flow

1. `run_trace_scrape` view dispatches `sploc_trace_scrape_task`
2. Task: `SplocRunner.get_driver()` → `scrape_trace_waterfall(driver, trace_id, service_name)`
3. Scraper navigates to trace URL, clicks Waterfall tab, finds the scroll container, extracts visible rows, scrolls, repeats until `no_new_limit` consecutive empty scrolls
4. Returns `{ok, trace_id, service_name, trace_url, total_spans, rows: [{index, span_id, service, operation, duration, indent_px}]}`
5. `poll_trace_scrape` appends to `trace_history.json` on success
6. Template renders Waterfall / Services / Raw JSON tabs with export JSON/TSV

Span rows are dedup'd by `span_id` across scrolls.

## AI Assistant Flow

1. `run_ai_ask` view dispatches `sploc_ai_ask_task`
2. Task: `ask_ai_assistant(driver, prompt, navigate_url, use_page_filters, start_new_chat, close_panel_at_end)`
3. Service navigates to APM page, opens AI panel, (optionally) starts new chat, sets textarea via React-safe setter, clicks send
4. Waits for a new response message, then waits for text to stabilize (`SPLOC_STABLE_WINDOW`)
5. Extracts markdown by overriding `navigator.clipboard.writeText`, clicking the response's Copy button, capturing the captured text
6. Returns `{ok, prompt, markdown, timestamp, url}`

## AI Trace Analysis (Tachyon-backed)

On a scraped trace result, clicking **Analyze with AI** runs `ai_analyze_trace`:

1. **Preflight** — checks Tachyon debug port is alive AND the configured `TachyonPreset` exists. Fails fast with an actionable red error card if either is missing (button links to `/tachyon/` or `/admin/tachyon/tachyonpreset/`).
2. Writes the trace JSON to `MEDIA_ROOT/sploc_ai_tmp/<uuid>_trace.json`
3. Dispatches `run_tachyon_llm_with_file_task` with the `sploc_trace_analysis` prompt (from the ServiceNow prompt store)
4. Poll view maps `BrowserLoginRequired` / `preset_not_found` to the same actionable error UI

Preflight is important because without it the Celery worker would try to start a Tachyon browser and block for 30s+ while the UI just spins.

## Prompt Packs

File-backed (`sploc/prompt_packs.json`) with built-in defaults in `services/prompt_packs.py`. Same pattern as Splunk presets — hidden list for "deleted" built-ins, export/import as JSON, full CRUD via `/sploc/prompts/`.

Pack shape:
```python
{
  "name": {
    "description": "...",
    "prompt": "Text sent to SignalFx AI...",
    "defaults": {"use_page_filters": bool, "start_new_chat": bool, "close_panel_at_end": bool},
    "tags": "comma, separated"
  }
}
```

Management UI has: search (with `/` shortcut), All/Custom/Built-in tabs with live counts, sort (name / custom-first), keyboard shortcuts (`n` = new pack, `Esc` = close modals).

## Cross-App Linking

**SPLOC → Splunk** — trace results have a **Search Splunk for this trace** button that opens `/splunk/?spl=index%3D*+%22<trace_id>%22&earliest=-1h&latest=now&autorun=1`. Custom range dropdown lets user override the time window before jumping.

**Splunk → SPLOC** — `splunk/templates/splunk/partials/search_results.html` has a post-render script that scans each event's raw `<pre>` for 32-hex strings (W3C trace_id format) and injects a banner above the raw text with clickable links to `/sploc/traces/?trace_id=<id>`. Up to 3 IDs per event; dedup'd; idempotent.

## Trace History (Recents)

`sploc/trace_history.json` — list of `{trace_id, service_name, total_spans, last_used}`, newest first, dedup'd by `(trace_id, service_name)`, capped at 30. Written on successful scrape (in `poll_trace_scrape`). Sidebar panel shows 10 most recent — click to prefill the form + auto-submit. Per-item delete, Clear all. Auto-refreshes via `hx-on::after-swap` on `#sploc-results`.

URL prefill: `/sploc/traces/?trace_id=X&service_name=Y&autorun=1` populates the form and auto-submits if session is alive.

## Service Catalog

File-backed (`sploc/service_catalog.json`) user-curated list of SignalFx service names. **No built-in defaults** — populated via the UI or JSON import only. Entry shape: `{description, tags, added_at}` keyed by service name.

The Trace Scraper's Service Name input uses an HTML5 `<input list="sploc-service-catalog">` + `<datalist>` combo — native browser autocomplete with no JS dependency. Typing a service not in the catalog is still valid; the catalog is purely an aid, not a constraint.

Management page at `/sploc/services/` mirrors the prompt-pack management shell (search with `/`, keyboard shortcuts `n`/`Esc`, sort by name or added-date, modal editor, import with skip/overwrite). Differences from prompt packs:

- No Custom/Built-in filter tabs (no built-ins to distinguish)
- No `_hidden` list in storage (no soft-delete needed)
- Editor has only 3 fields: name, description, tags (no `defaults` block)
- `save_service` preserves `added_at` on edits so timestamps stay meaningful
- Name pattern is permissive (`[a-zA-Z0-9_\-\.]+`) — SignalFx service names commonly contain hyphens and dots
- Import accepts `{"services": {...}}` or `{"catalog": {...}}` (alias). Does NOT accept `{"packs": {...}}` — cross-importing a prompt-pack file would be a data-model mistake.

Deferred: auto-capture on scrape, "add this service?" prompt post-scrape, built-in defaults, usage-count tracking.

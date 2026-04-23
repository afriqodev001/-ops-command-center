# Splunk Integration

Browser-authenticated Splunk search with AI analysis, presets, and saved search management.

## Architecture

```
UI (pages.py) → Celery task → SplunkRunner → fetch_json_in_browser() → Splunk REST API
```

All API calls execute `fetch()` inside the authenticated Edge browser — SSO cookies are never extracted.

## Key Files

```
splunk/
├── pages.py              # HTML views + HTMX partials
├── views.py              # JSON API endpoints
├── tasks.py              # 15+ Celery tasks
├── session_views.py      # sidebar widget, connect/reset
├── auth.py               # SSO auth check
├── urls.py               # all routes
├── urls_builders.py      # Splunk REST URL construction
├── runners/
│   └── splunk_runner.py  # SeleniumRunner subclass
└── services/
    ├── splunk_fetch.py       # browser fetch() wrapper
    ├── splunk_jobs.py        # create, poll, fetch results
    ├── splunk_presets.py     # file-backed preset store
    ├── splunk_alerts.py      # search saved searches
    ├── splunk_alerts_list.py # list all saved searches
    ├── splunk_saved_searches.py # saved search lookup
    └── formatters/           # response pruning
```

## Settings

```python
SPLUNK_BASE = 'https://your-splunk.splunkcloud.com'
SPLUNK_APP = 'search'
SPLUNK_NAMESPACE_USER = 'nobody'
SPLUNK_RUN_MAX_POLLS = 30
SPLUNK_RUN_POLL_INTERVAL = 2.0
```

## Search Flow

1. `run_search` view dispatches `splunk_search_run_task`
2. Task: create job → poll until done (30×2s) → fetch preview + events
3. If not done: UI auto-dispatches `splunk_job_continue_task` (60×3s more)
4. View normalizes response: strips `_` prefixes, extracts rows/fields
5. Template renders Statistics/Events/Raw JSON tabs

## Presets

File-backed (`splunk_presets.json`) with built-in defaults in code. Hidden list for "deleted" built-ins. SPL templates use `{placeholder}` syntax. Client-side parameter rendering.

## AI Features

- **NL→SPL**: `ai_natural_to_spl` — prompt → JSON with `spl`, `earliest`, `latest`, `explanation`
- **Results Analysis**: `ai_analyze_results` — saves full results to temp file, uploads to Tachyon
- **Preset Generator**: `ai_generate_preset` — SPL → preset definition JSON

## Saved Searches

Server-side search via `splunk_alerts_search_task` — queries `servicesNS/-/<app>/saved/searches` with name wildcard. Returns name, owner, app, SPL, schedule, enabled/disabled.

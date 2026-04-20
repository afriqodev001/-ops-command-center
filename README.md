# Ops Command Center

A Django-based operations portal that unifies ServiceNow, Splunk, Microsoft Copilot, and Tachyon AI into a single command center for IT operations engineers.

Each integration uses browser-based authentication (Selenium + Edge CDP) so SSO credentials are never stored. Read and write operations go through Celery tasks that hit real APIs asynchronously — the UI never blocks.

## Stack

- **Django 6** — server-rendered templates, file-backed JSON stores for user content
- **HTMX 2** — partial swaps, async polling, no SPA
- **Alpine.js 3** — local reactive state in modals and forms
- **Tailwind CSS 3** — pre-built from source, custom component classes
- **Celery** — filesystem broker, django-db results backend, solo pool on Windows
- **Selenium** (headed Edge via CDP) — authenticated sessions per integration
- **AI Providers** — Tachyon Playground, Claude (Anthropic), or OpenAI for AI-assisted features

## Apps

### ServiceNow (`/servicenow/`)
ITSM operations hub for incidents and changes.

- **Incidents / Changes** — action hub pages with time-range, priority/state filters
- **Search** — find records by CI, requester, or assignment group (with saved presets)
- **Fetch by Number** — paste any mix of INC/CHG numbers, get full records
- **Create Records** — incidents and changes with AI-powered field generation from plain-text descriptions
- **Creation Templates** — reusable payloads for all change types and incidents
- **Bulk Change Create** — paste or CSV-upload with validation; category/reason constrained to allowed values
- **Bulk Change Review** — heuristic CAB pre-check with progressive card rendering
- **Change Briefing** — AI-generated readiness review with markdown rendering
- **Query Presets** — saved list queries with parameter substitution; export/import as JSON
- **Demo / Live mode toggle** — switch data source per session

### Splunk (`/splunk/`)
Search, analyze, and manage Splunk queries.

- **Search** — run SPL queries with earliest/latest time controls and async result polling
- **Natural Language → SPL** — describe what you want in plain English, AI generates the query
- **AI Results Analysis** — upload full results as a file to AI for structured analysis with markdown output
- **Search Presets** — parameterized SPL templates with export/import; dedicated presets page with CRUD
- **Saved Searches** — server-side search across all saved searches (handles 2600+), run directly or save as preset
- **Smart Preset Generator** — AI analyzes raw SPL and generates a clean preset with parameters and defaults
- **Auto-continue polling** — searches that take longer than 60s automatically continue polling until complete

### Copilot Chat (`/copilot/`)
Microsoft Teams Copilot automation via browser.

- **Single Prompt** — execute prompts with optional file attachments (thumbnails + individual remove)
- **Batch Execution** — run multiple prompts sequentially with progress tracking
- **Prompt Packs** — reusable prompt collections with tags, multi-prompt support, and situation filtering
- **Pack Management** — create, edit, delete, export/import packs as JSON
- **Live Run** — real-time result display with markdown rendering and copy
- **Run History** — recent runs with status, click to review, export as CSV/JSON
- **Session gating** — 3-layer protection prevents running without an active connection

### Tachyon Playground (`/tachyon/`)
LLM playground for the enterprise Tachyon AI platform.

- **Preset Management** — create, edit, clone presets with model/parameter configuration
- **Query Execution** — run prompts against Tachyon with async Celery polling
- **File Upload** — attach files to queries for document-aware AI responses
- **Session Management** — connect/disconnect browser sessions for Tachyon authentication

### Core Infrastructure (`core/`)
Shared services used by all apps.

- **Browser Registry** — per-integration Edge profile and CDP port management
- **Session Lifecycle** — headed login → headless reuse → CDP close (cookies saved)
- **Task Polling** — `/tasks/<id>/result/` endpoint for async Celery result polling
- **Context Processor** — OS user identity, preferences, AI provider status in every template
- **AI Provider Routing** — unified `_call_llm()` dispatches to Tachyon/Claude/OpenAI
- **Prompt Store** — file-backed editable prompts for all AI features (Preferences → AI Prompts)

## Features Across Apps

- **Unified session management** — sidebar widgets for ServiceNow, Tachyon, Copilot, and Splunk with connect/disconnect/status polling
- **AI-powered creation** — describe issues or changes in plain English, AI fills structured fields
- **Editable AI prompts** — all system prompts editable via Preferences → AI Prompts
- **Export/Import** — presets, prompt packs, and search configurations are portable as JSON
- **Activity log** — header bell surfaces recent events with deep links
- **Preferences panel** — data mode, group filter, browser timeout, AI provider config
- **Dark theme** — glass-card design with Tailwind CSS custom components
- **Mobile responsive** — grid layouts adapt to screen size

## Quick Start

```bash
# 1. Clone and enter the repo
git clone https://github.com/afriqodev001/ops-command-center.git
cd ops-command-center

# 2. Create a virtualenv
python -m venv .venv
source .venv/Scripts/activate      # Windows (Git Bash)
# or: .venv\Scripts\activate       # Windows (cmd/PowerShell)
# or: source .venv/bin/activate    # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — set your instance URLs and credentials

# 5. Set up the database
cd ops_portal
python manage.py migrate

# 6. Run the dev server
python manage.py runserver
```

Open http://localhost:8000/. The app starts in **Demo mode** with seeded ServiceNow data. Click the "Mode" chip to switch to Live.

### Running Celery

In a second terminal:

```bash
cd ops_portal
celery -A ops_portal worker -P solo -l info
```

`-P solo` is recommended on Windows. The filesystem broker writes under `celery_data/` (git-ignored). Task results auto-expire after 1 hour.

### For Production

```bash
cd ops_portal
python manage.py collectstatic --noinput
waitress-serve --port=8000 ops_portal.wsgi:application
```

Static files served by `whitenoise` middleware — no nginx needed.

### Rebuilding Tailwind CSS

After adding new Tailwind classes to templates:

```bash
npm install -D tailwindcss@3       # one-time
npx tailwindcss -i ops_portal/static/css/input.css \
                -o ops_portal/static/css/tailwind.min.css --minify
```

## Configuration

All environment variables documented in [`.env.example`](.env.example):

| Variable | Purpose |
|----------|---------|
| `DJANGO_SECRET_KEY` | Session signing key — rotate for production |
| `DJANGO_DEBUG` | `True` for dev, `False` for prod |
| `SERVICENOW_BASE` | Your ServiceNow instance URL |
| `TACHYON_BASE` | Tachyon Playground instance URL |
| `TACHYON_DEFAULT_USER_ID` | Tachyon user ID |
| `SPLUNK_BASE` | Splunk Cloud/Enterprise URL |
| `SPLUNK_APP` | Splunk app namespace (default: `search`) |
| `SPLUNK_NAMESPACE_USER` | Splunk API namespace user |
| `COPILOT_TEAMS_URL` | Microsoft Teams URL for Copilot |
| `AI_API_KEY` | API key for Claude or OpenAI (if not using Tachyon) |
| `AI_MODEL` | LLM model override |
| `EDGE_EXE_PATH` | Path to Microsoft Edge (Windows) |

## Local Stores

User-authored content stored as flat JSON files (all git-ignored):

| File | App | Content |
|------|-----|---------|
| `user_presets.json` | ServiceNow | Saved query presets |
| `creation_templates.json` | ServiceNow | Record creation payloads |
| `search_presets.json` | ServiceNow | Search page filter shortcuts |
| `user_preferences.json` | ServiceNow | User preferences |
| `field_options.json` | ServiceNow | Category/reason options, combobox values |
| `prompts.json` | ServiceNow | Editable AI system prompts |
| `splunk_presets.json` | Splunk | Search preset definitions |

## Project Layout

```
ops-command-center/
├── .venv/                    # virtualenv (gitignored)
├── requirements.txt
├── .env.example              # copy to .env locally
├── tailwind.config.js        # Tailwind CSS configuration
└── ops_portal/               # Django BASE_DIR
    ├── manage.py
    ├── docs/                 # user + technical guides
    ├── ops_portal/           # Django project config
    ├── core/                 # shared infra (browser, tasks, runners)
    ├── servicenow/           # ServiceNow ITSM app
    ├── tachyon/              # Tachyon AI playground app
    ├── copilot_chat/         # Microsoft Copilot chat app
    ├── splunk/               # Splunk search & analysis app
    ├── harness/              # Harness CI/CD app (scaffold)
    ├── templates/            # project-level base templates
    └── static/               # shared static assets (CSS, JS)
```

## Documentation

Detailed guides in [`ops_portal/docs/`](ops_portal/docs/):

- [User guide](ops_portal/docs/user_guide/index.md) — one page per feature
- [Technical guide](ops_portal/docs/technical/index.md) — architecture, patterns, internals

## License

TBD — add a `LICENSE` file before sharing beyond your team.

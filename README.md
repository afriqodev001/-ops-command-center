# Ops Command Center

A Django-based operations portal for ServiceNow-backed workflows: browse incidents and changes, run saved queries, create records in bulk from CSV, launch standard changes from saved URL templates, and review CABs.

Designed as a thin, fast UI over a Selenium-driven ServiceNow session — write paths (create / patch) hit the real Table API via Celery tasks; read paths currently show seeded demo data (togglable to Live from the top bar).

## Stack

- **Django 6** — server-rendered templates, file-backed JSON stores for user content
- **HTMX 2** — partial swaps, no SPA
- **Alpine.js 3** — local reactive state in modals and forms
- **Tailwind CSS** — via CDN, custom utility classes in `base.html`
- **Celery** — filesystem broker, async write tasks against ServiceNow
- **Selenium** (headed Edge) — authenticated ServiceNow session via user profile

## Features

- **Incidents / Changes** list pages with time-range, priority/state, and substring filters
- **Search** page — find records by CI / Requester / Assignment group (with saved search presets for long CI names)
- **Fetch by Number** — paste any mix of INC/CHG numbers, get full records
- **Query Presets** — saved ServiceNow list queries with parameter substitution; export / import as JSON
- **Creation Templates** — reusable payloads for creating changes (standard / normal / emergency) and incidents
- **Bulk Change Create** — paste or CSV-upload; normal/emergency go through the Table API, standard changes open in browser tabs sequentially
- **Bulk Change Review** — heuristic CAB pre-check over N pasted CHGs; progressive card rendering
- **Change Briefing** — structured prompt generator for AI-assisted change review
- **Demo / Live mode toggle** — switch the data source per user without editing code
- **Preferences panel** — OS user identity, default data mode, reset local stores
- **Activity log** — header bell surfaces recent write events with deep links

## Documentation

Detailed guides live in [`ops_portal/docs/`](ops_portal/docs/):

- [User guide](ops_portal/docs/user_guide/index.md) — one page per feature, with examples
- [Technical guide](ops_portal/docs/technical/index.md) — architecture, frontend patterns, service internals, adding a feature

## Quick start

```bash
# 1. Clone and enter the repo
git clone https://github.com/afriqodev001/ops-command-center.git
cd ops-command-center

# 2. Create a virtualenv
python -m venv .venv
source .venv/Scripts/activate      # on Windows (Git Bash)
# or: .venv\Scripts\activate       # on Windows (cmd/PowerShell)
# or: source .venv/bin/activate    # on macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — at minimum set SERVICENOW_BASE to your instance

# 5. Set up the database
cd ops_portal
python manage.py migrate

# 6. Run the dev server
python manage.py runserver
```

Open http://localhost:8000/ in your browser. The app starts in **Demo mode** with seeded records — click the "Mode" chip in the header to switch to Live when you wire real ServiceNow reads.

### Running Celery (for create/patch operations)

In a second terminal:

```bash
cd ops_portal
celery -A ops_portal worker -P solo -l info
```

The `-P solo` flag runs the worker in a single process. It's the recommended
pool on Windows — the default prefork pool relies on `fork()` and frequently
hits "access denied" errors in corporate environments where AV/EDR blocks
child-process spawning. `solo` handles one task at a time, which is fine
for this app since most tasks drive an interactive browser anyway.

The filesystem broker writes under `celery_data/` (git-ignored).

## Configuration

All environment variables are documented in [`.env.example`](.env.example). The most important:

| Variable          | Purpose                                              |
| ----------------- | ---------------------------------------------------- |
| `DJANGO_SECRET_KEY` | Django session signing key — rotate for production |
| `DJANGO_DEBUG`    | `True` for dev, `False` for prod                    |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated host list                       |
| `SERVICENOW_BASE` | Your ServiceNow instance URL                        |
| `EDGE_EXE_PATH`   | Path to Microsoft Edge (Windows)                    |

`settings.py` also tries to import `ops_portal/local_settings.py` at the bottom — drop any local overrides there (git-ignored).

## Local stores

User-authored content is stored as flat JSON files next to the `servicenow/` app:

- `user_presets.json` — saved query presets (overrides built-ins)
- `creation_templates.json` — creation payloads for the 4 record kinds
- `search_presets.json` — Search-page filter shortcuts
- `user_preferences.json` — user preferences (default data mode, etc.)

All four are git-ignored by default so company-specific data doesn't leak into the repo. The Preferences panel (click the user block in the sidebar) has a "Reset" button per store.

## Project layout

```
ops-command-center/
├── .venv/                    # virtualenv (gitignored)
├── requirements.txt
├── .env.example              # copy to .env locally
└── ops_portal/               # Django BASE_DIR
    ├── manage.py
    ├── docs/                 # user + technical guides
    ├── ops_portal/           # Django project config
    ├── core/                 # shared infra (browser registry, task polling)
    └── servicenow/           # main app
        ├── pages.py          # HTML views
        ├── views.py          # JSON API views
        ├── tasks.py          # Celery tasks
        ├── services/         # pure-Python services
        └── templates/
```

See the [technical guide](ops_portal/docs/technical/02_project_structure.md) for the full layout and conventions.

## License

TBD — add a `LICENSE` file before sharing beyond your team.

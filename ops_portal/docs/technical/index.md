# Ops Command Center — Technical Guide

Developer-oriented documentation covering architecture, patterns, and feature internals.

## Contents

**Foundations**
1. [Architecture](01_architecture.md) — stack, layers, and request lifecycle
2. [Project Structure](02_project_structure.md) — directory layout and conventions
3. [Frontend Patterns](03_frontend_patterns.md) — HTMX + Alpine + Tailwind conventions

**Backend layers**
4. [Session Management](04_session_management.md) — browser registry, CDP ports, profile lifecycle
5. [Celery Tasks](05_celery_tasks.md) — async task layer conventions
6. [Table API Integration](06_table_api.md) — how we talk to ServiceNow

**ServiceNow features**
7. [Presets](07_feature_presets.md) — query preset system
8. [Creation Templates](08_feature_templates.md) — unified template store + create flow
9. [Bulk and Search Flows](09_feature_bulk_and_search.md) — bulk review, bulk create, search
10. [Demo Data](10_demo_data.md) — seeded records and enrichment
11. [Adding a Feature](11_adding_a_feature.md) — end-to-end walkthrough

**Multi-app systems**
12. [AI Provider System](12_ai_provider.md) — unified LLM routing, prompt store, file uploads
13. [Splunk Integration](13_splunk.md) — search, presets, saved searches, AI analysis
14. [Copilot Chat](14_copilot_chat.md) — Teams automation, prompt packs, session gating
15. [Tachyon](15_tachyon.md) — LLM playground, preset management
16. [Adding a New Integration](16_adding_integration.md) — session widget, runner, tasks pattern

## Terminology

| Term | Meaning |
|------|---------|
| **Session** | Browser connection per integration (PID + profile dir + CDP port) |
| **CDP** | Chrome DevTools Protocol — how we control Edge browsers |
| **AI Provider** | Tachyon, Claude, or OpenAI — configured in Preferences |
| **Prompt Store** | File-backed editable AI prompts (`prompts.json`) |
| **Preset** | Saved query/search template (ServiceNow or Splunk) |
| **Template** | Write (create) payload for ServiceNow records |
| **Prompt Pack** | Reusable collection of Copilot Chat prompts |
| **Partial** | Template fragment for HTMX swaps |
| **hx-boost** | HTMX SPA-like nav — causes Alpine/JS re-execution issues |

## Conventions

- Paths relative to `ops-command-center/ops_portal/`
- Each app: `pages.py` (HTML), `views.py` (JSON API), `tasks.py` (Celery), `services/`, `session_views.py`
- Alpine: `Alpine.data()` registration, never inline functions
- JSON stores: gitignored, user-specific data stays local

# Ops Command Center — User Guide

Quick reference for every page in the Ops Command Center. Each guide covers what the page does, how to use it, and concrete examples.

## Contents

1. [Dashboard](01_dashboard.md) — at-a-glance operational view
2. [Incidents](02_incidents.md) — list, filter, and inspect incident records
3. [Changes](03_changes.md) — list, inspect, and review change requests (includes AI briefing)
4. [Bulk Change Review](04_bulk_change_review.md) — pre-approve many changes at once
5. [Bulk Change Create](05_bulk_change_create.md) — create N changes from paste or CSV
6. [Fetch by Number](06_fetch_by_number.md) — resolve pasted INC/CHG numbers to full records
7. [Search](07_search.md) — find records by CI, requester, or assignment group
8. [Presets](08_presets.md) — saved ServiceNow list queries
9. [Templates](09_templates.md) — reusable payloads for creating records

## Conventions used in these guides

- **Session widget** (top-right of every page) — a green dot means you're
  connected to ServiceNow, red means you need to connect before write actions
  will succeed. Click the pill to open the session manager.
- **Mode chip** (next to the session widget) — shows either **Demo** (yellow
  dot) or **Live** (green dot). Click to flip between them:
  - **Demo** — every read page renders the built-in seeded dataset. Safe for
    exploring, training, and screenshots. This is the default.
  - **Live** — read pages clear out and wait for real ServiceNow API wiring
    (a banner at the top of the page explains this while you're in Live mode).
    Write actions (bulk create, create-from-template) already call the real
    API whenever a session is connected, regardless of the mode chip.
- **HTMX swaps** — most actions update part of the page without a full reload.
  A small purple bar at the top flashes while a request is in flight.
- **Preferences panel** — click the user block at the bottom of the sidebar to
  open it. Shows the OS user, the ServiceNow session status, and lets you set
  the **default data mode** (used on next Django session), plus reset any of
  the local JSON stores (query presets, creation templates, search presets).
- **Activity log** — the bell icon (top right) opens a log of recent write
  actions: preset / template saves & deletes, bulk-change submits,
  create-from-template dispatches, mode flips, session connect / disconnect.
  A red badge shows unread count. Opening the log marks everything read.
  Click "Clear all" to empty it.

## Keyboard-friendly tips
- `/` focuses the first search box on any page that has one.
- Clicking outside a dialog dismisses it (backdrop click).
- All list tables support horizontal scroll on narrow screens.

## Getting help
If a page behaves unexpectedly, check the session widget first — most
"nothing happens when I click" issues are a dropped session.

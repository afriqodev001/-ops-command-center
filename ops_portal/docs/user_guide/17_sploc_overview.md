# SPLOC Overview

The SPLOC app (`/sploc/`) connects the Ops Command Center to **Splunk Observability Cloud** (SignalFx). It gives you two main workflows, plus prompt pack management.

## Pages

- **Overview** (`/sploc/`) — landing page with feature cards
- **Trace Scraper** (`/sploc/traces/`) — scrape waterfall spans from a specific SignalFx trace
- **AI Assistant** (`/sploc/ai/`) — query SignalFx's built-in AI Assistant panel
- **Prompt Packs** (`/sploc/prompts/`) — manage reusable AI prompts

## Session Model

SPLOC uses a dedicated Edge browser profile just like Splunk and Copilot:

- **Connect SPLOC** in the sidebar opens Edge headed at your SignalFx URL → complete SSO once
- After login, the widget turns green ("Connected"). Future tasks reuse this session headlessly
- **Close browser** (green state) — kills the browser but keeps cookies on disk
- **Reset** (either state) — kills browser + wipes the entire profile (fresh login next time); use this when "Connected" is lying (expired auth, stuck state)

## What SPLOC is *not*

- Not a full APM replacement — we don't draw service maps, dependency graphs, or latency histograms
- Not a detector/alert manager — use SignalFx UI for those
- Not a real-time monitor — each trace scrape is on-demand

SPLOC's sweet spot is: you already have a trace ID (from an alert, Splunk log, or SignalFx UI), and you want fast, structured analysis without clicking around.

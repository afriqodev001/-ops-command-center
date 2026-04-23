# Splunk Search

The Splunk Search page (`/splunk/`) is the primary interface for running SPL queries against your Splunk instance.

## Layout

- **Left panel**: Quick Presets (top 5) + link to Saved Searches page
- **Center**: Natural Language → SPL input + SPL search form + results

## Natural Language → SPL

Type what you want in plain English (e.g. "Show me all 500 errors from the API gateway in the last 2 hours grouped by host"). Click **Generate** — the AI creates a valid SPL query, populates the search form, and shows an explanation.

## Running a Search

1. Enter SPL in the search box (or use NL→SPL / preset to populate it)
2. Set **Earliest** and **Latest** time range (defaults: `-10m` → `now`)
3. Click **Run Search**
4. Results appear below with three tabs:
   - **Statistics** — tabular data with sticky headers, row numbers, scrollable
   - **Events** — collapsible event cards with metadata + auto-formatted JSON
   - **Raw JSON** — full response with copy button

## AI Analysis

After results load, the **AI Actions** section appears:
- Optional **context textarea** — add a question like "Why are errors spiking on host-03?"
- **Analyze with AI** — uploads full results as a file to the AI provider for structured analysis (Summary, Key Findings, Anomalies, Recommendations)
- **Save as Preset** — AI generates a clean preset definition from your SPL

## Quick Presets

The left panel shows the top 5 presets. No-param presets run directly; parameterized ones link to the full Presets page.

## Session Requirement

All searches require an active Splunk browser session (sidebar widget). The search button is disabled when not connected.

## Auto-Continue

If a search takes longer than 60 seconds, the app automatically continues polling the Splunk job until it completes (up to ~4 minutes total).

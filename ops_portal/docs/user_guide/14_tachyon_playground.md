# Tachyon Playground

Enterprise LLM playground using the Tachyon AI platform (`/tachyon/playground/`).

## Presets

Presets define LLM configurations: model, parameters (temperature, max tokens), and system instruction. The "Default (GPT 5.1)" preset is auto-created on first visit.

- **Select** a preset from the dropdown
- **View/edit** configuration in the collapsible config panel
- **Manage presets**: create, edit, clone, delete via the modal

## Running Queries

1. Select a preset
2. Type your query
3. Optionally attach a file (for document-aware responses)
4. Click **Run** — result appears below with async Celery polling

## Session

Tachyon requires a browser session for authentication. Connect via the sidebar widget. The session is also used by AI features in other apps (ServiceNow field suggestions, Splunk analysis) when Tachyon is selected as the AI provider.

## AI Provider Role

Tachyon serves as the default AI provider for all AI-powered features across the app:
- ServiceNow: field suggestions, change briefing review
- Splunk: results analysis, NL→SPL, preset generation
- Configure in Preferences → AI Provider

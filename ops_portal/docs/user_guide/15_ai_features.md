# AI Features

AI is woven throughout the Ops Command Center. All features use a unified provider and editable prompts.

## AI Provider Configuration

Open **Preferences** (sidebar user block) → **AI Provider**:
- **Tachyon** (default) — uses the enterprise Tachyon platform via browser session
- **Claude** — direct Anthropic API (set `AI_API_KEY` in `.env`)
- **OpenAI** — direct OpenAI API (set `AI_API_KEY` in `.env`)
- **None** — disables all AI features

## Editable Prompts

All system prompts are editable: **Preferences** → **AI Prompts** → **Edit prompts**.

Each prompt has a label, description, and the full text. Changes take effect immediately. Reset to default available per prompt.

### Available Prompts

| Prompt | Used by |
|--------|---------|
| Field Suggestion | ServiceNow: suggest empty fields based on filled ones |
| Incident from Description | ServiceNow: generate all incident fields from plain text |
| Change from Description | ServiceNow: generate all change fields from plain text |
| Change Briefing Review | ServiceNow: AI review of change readiness |
| Change Briefing Preamble | ServiceNow: instructions for briefing data |
| Splunk Results Analysis | Splunk: analyze search results |
| Natural Language → SPL | Splunk: generate SPL from English description |
| Smart Preset Generator | Splunk: generate preset from raw SPL |

## AI Features by App

### ServiceNow
- **"Describe the issue/change"** — free-text box generates all form fields (category, description, assignment group, etc.) constrained to valid values
- **AI field suggestions** — fill short_description, click Suggest to auto-fill remaining fields
- **Change briefing review** — AI assesses readiness with markdown output (Readiness, Risk, Planning, Recommendation)

### Splunk
- **Natural Language → SPL** — describe what you want, AI generates the query
- **Analyze with AI** — uploads full results as a file for structured analysis
- **Smart Preset Generator** — AI creates a clean preset from raw SPL
- **Show prompt** — expand to see what was sent to the AI

### Copilot Chat
- Uses the browser-automated Copilot directly (not the AI provider)

## File Upload for Analysis

Splunk AI analysis saves full results to a temp file and uploads it to Tachyon as an attachment, avoiding the 8000-char truncation limit. The AI gets the complete dataset.

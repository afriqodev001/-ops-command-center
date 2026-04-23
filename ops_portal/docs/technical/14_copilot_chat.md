# Copilot Chat Integration

Microsoft Teams Copilot automation via Selenium browser control.

## Architecture

Unlike ServiceNow/Splunk (which use REST APIs via browser fetch), Copilot uses **DOM automation**:

```
UI → Celery task → CopilotRunner → TeamsCopilotClient → DOM manipulation in Teams iframe
```

The client types into a contenteditable div, clicks Send, and watches for response turns in the DOM.

## Key Files

```
copilot_chat/
├── views.py              # UI + API endpoints
├── session_views.py      # sidebar widget, connect/reset
├── tasks.py              # auth check, single run, batch, file upload
├── forms.py              # RunPromptForm, BatchRunForm
├── models.py             # PromptPack, Prompt, CopilotRun, CopilotBatch, CopilotDownload
├── runners/
│   └── copilot_runner.py
└── services/
    ├── copilot_client.py     # TeamsCopilotClient (626 lines)
    ├── copilot_ops.py        # build_client_for_user, run_prompt
    ├── copilot_attachments.py # file upload to Copilot
    ├── copilot_downloads.py  # capture blob downloads
    ├── export_utils.py       # CSV/JSON export
    └── prompt_packs_store.py # DB-backed prompt packs
```

## Session Gating (3 layers)

1. **Frontend**: Alpine polls `/copilot/session/status/` every 15s, disables Run button
2. **Backend**: `is_session_alive()` check before dispatching tasks
3. **Task**: step-by-step error handling (browser → attach → Teams → Copilot rail → iframe → input)

## Auth Check Task

Does NOT create browsers. Only checks if one exists and tests readiness at each step:
1. Browser running? (registry + CDP port probe)
2. WebDriver can attach?
3. Teams loaded?
4. Copilot left rail clickable?
5. Chat input found inside iframe?

## Prompt Packs (DB-backed)

- `PromptPack`: name, description, tags, enabled
- `Prompt`: text, order, FK to pack
- Multi-prompt support: use individual prompts or run all as batch
- Export/Import as JSON: `{"packs": [{"name": "...", "prompts": [...]}]}`

## Response Capture

The client uses two strategies:
1. **Copy button capture**: injects clipboard hook, clicks Copy, reads clipboard
2. **DOM text extraction**: reads innerText from the response turn elements

Responses rendered as markdown via marked.js in the Live Run card.

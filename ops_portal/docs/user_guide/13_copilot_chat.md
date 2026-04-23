# Copilot Chat

Automate Microsoft Teams Copilot interactions (`/copilot/`).

## Layout

- **Left**: Prompt Packs (searchable, filterable by tags)
- **Center**: Run Prompt form + Batch Execution
- **Right**: Live Run display + Recent Runs history

## Connecting

1. Click **Connect Copilot** in the sidebar
2. Complete Teams SSO login in the browser that opens
3. Navigate to Copilot in the Teams left rail
4. Click **Check** in the readiness bar to verify

The readiness check tests each step: browser → Teams loaded → Copilot selected → chat input visible.

## Running a Single Prompt

1. Type your prompt in the textarea
2. Optionally attach files (thumbnails shown, individually removable)
3. Check "Clear existing" to remove prior attachments in Copilot
4. Click **Run Prompt** — button shows spinner, result appears in Live Run

## Batch Execution

1. Expand the Batch section
2. Enter one prompt per line (or use "Run all as batch" from a prompt pack)
3. Click **Start Batch** — prompts execute sequentially

## Prompt Packs

Reusable prompt collections with tags for filtering:
- **Single-prompt packs**: "Use" fills the prompt field directly
- **Multi-prompt packs**: "Pick prompt" opens viewer to choose one, or "Run all as batch"
- **Search**: filter by name/description
- **Tags**: click tag chips to filter
- **Export/Import**: share packs as JSON files between users

## Live Run & History

- **Live Run**: shows the current/last result with markdown rendering + copy
- **Recent Runs**: click any past run to view it. Export as CSV/JSON.

## Session Gating

All prompts require an active Copilot session. Three layers:
1. Frontend: button disabled + warning banner
2. Backend: pre-flight CDP check before dispatching task
3. Task: step-by-step error handling with actionable messages

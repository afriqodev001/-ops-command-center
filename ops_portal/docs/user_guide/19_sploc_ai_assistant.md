# SPLOC AI Assistant

Send prompts to **SignalFx's built-in AI Assistant** (the side panel on the APM page) and get the response back as markdown.

## Page: `/sploc/ai/`

## Layout

- **Left panel** — Prompt Packs (reusable one-click prompts)
- **Center** — prompt form + response area

## Sending a Prompt

1. Type your question in the **Prompt** textarea, or click a pack on the left to prefill
2. (Optional) expand **Options**:
   - **Start new chat** — clears the previous SignalFx AI conversation before sending
   - **Use current page filters for context** — tells the AI to use the filters currently set in the SignalFx UI
   - **Close AI panel when done** — tidies up after the response is captured (on by default)
3. Click **Ask AI**

The app drives your SignalFx session: opens the AI panel, optionally starts a new chat, types your prompt, clicks send, waits for the response to finish streaming, and extracts the markdown by simulating a Copy-button click.

## Button Disabled While Loading

The **Ask AI** button is disabled from the moment you click it until the actual response lands — not just until the form submits. You can't accidentally fire a second query while the first is in flight.

## Response

You get a card with:
- The original prompt (for context)
- The AI's response rendered as markdown (with code blocks, lists, tables)
- Timestamp + URL the query was run against
- **Copy** button for the full response

## Prompt Packs Sidebar

The left panel shows your Prompt Packs (up to ~10). Clicking a pack:
- Pre-fills the prompt textarea
- Toggles the option checkboxes to match the pack's defaults (`start_new_chat`, `use_page_filters`, `close_panel_at_end`)

Built-in packs include:
- **Recent errors** — error traces in the last 15 min
- **High latency** — services with highest latency right now
- **Error hotspots** — top error-producing services in the last hour
- **Anomalies** — unusual patterns in the last 30 min
- **Health summary** — overall service health overview

Click **Manage (N) →** at the top of the sidebar to open the full Prompt Packs management page.

## Session Requirement

Requires an active SPLOC browser session (green sidebar widget). Unsent prompts are preserved if the session drops.

## Tips

- **Response stabilization** — the app watches for the AI's text to stop changing for 1.25s before considering the response complete. Short responses finish in seconds; long streaming ones can take up to 2 minutes (`SPLOC_RESPONSE_TIMEOUT`).
- **Use page filters** can help when the AI needs the context you've set in the SignalFx UI (e.g. a specific service or environment filter)
- **Start new chat** is useful when the previous conversation's context would confuse the new query

## Troubleshooting

- **"SPLOC not connected"** → click Connect SPLOC in the sidebar and complete SSO
- **AI response is empty or truncated** → the response may not have stabilized within the timeout; retry. Or the Copy-button extraction failed; we fall back to reading the rendered text, which should still have content.
- **Keeps spinning forever** → hit **Reset** on the SPLOC session widget and reconnect. The stale session may be preventing the task from attaching.

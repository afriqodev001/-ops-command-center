# SPLOC Prompt Packs

Reusable AI Assistant prompts with full management: create, edit, delete, export, import, one-click launch.

## Page: `/sploc/prompts/`

## What's a Prompt Pack?

A prompt pack is a saved prompt you can send to SignalFx's AI Assistant in one click. Each pack has:

- **Name** — snake_case identifier (`recent_5xx_errors`)
- **Description** — short subtitle shown on the button
- **Prompt** — the text sent to the AI
- **Tags** — comma-separated, for filtering
- **Defaults** — checkbox state for `start_new_chat`, `use_page_filters`, `close_panel_at_end`

## Page Layout

**Header** — live stats (Total / Built-in / Custom counts) + Export / Import / New Pack actions.

**Filter toolbar** — search box, filter tabs (All / Custom / Built-in), sort dropdown.

**Grid** — one card per pack with:
- Name, built-in/custom badge
- Description
- Tag chips (one per comma-separated tag)
- Prompt preview (expandable if >3 lines)
- Default option indicators (new chat · page filters · auto-close)
- Action toolbar: **Use**, **Copy prompt**, **Edit**, **Export**, **Delete**

## Keyboard Shortcuts

- **`/`** — focus the search box
- **`n`** — open New Pack modal
- **`Esc`** — close any open modal

Shortcuts are suppressed when you're typing in an input or textarea.

## Creating a Pack

Click **New Pack** (or press **n**) → fill in the editor modal:

| Field | Required | Notes |
|-------|----------|-------|
| Name | ✓ | Lowercase + numbers + underscores only, `pattern="[a-z0-9_]+"` |
| Description | ✓ | Short subtitle |
| Prompt | ✓ | The text sent to SignalFx AI |
| Tags | | Comma-separated |
| Defaults | | Checkboxes for start_new_chat / use_page_filters / close_panel_at_end |

Save → the grid updates in place (HTMX swap); a toast banner confirms.

## Editing

Click the edit icon on any pack → same modal, prefilled. Built-in packs can have their name edited as a new custom pack (fork).

## Deleting

Click the trash icon. Custom packs are fully deleted. **Built-in packs are hidden** (added to `_hidden` in the JSON) — they can be restored by re-importing the default pack set.

## Using a Pack

Three ways:

1. **Manage page** — click **Use** on a card → opens `/sploc/ai/?use=<name>` with the prompt + defaults prefilled, ready to submit
2. **AI Assistant sidebar** — click a pack in the Prompt Packs panel → fills the form in place
3. **URL deep-link** — share `/sploc/ai/?use=<pack_name>` with a teammate

## Import / Export

**Export all** — downloads `sploc_prompt_packs.json` with everything (built-ins + custom, minus hidden).

**Export one** — the ⤓ icon on a card exports just that pack.

**Import** — upload a pack file → preview table shows existing vs new → pick conflict mode (**Skip existing** or **Overwrite existing**) → **Import**. Counts are shown after.

Pack file format:
```json
{
  "packs": {
    "error_5xx_recent": {
      "description": "5xx errors in the last hour",
      "prompt": "List traces with 5xx errors in the past hour, grouped by service.",
      "tags": "errors, recent",
      "defaults": {
        "start_new_chat": false,
        "use_page_filters": false,
        "close_panel_at_end": true
      }
    }
  }
}
```

## Storage

`ops_portal/sploc/prompt_packs.json` — gitignored. Built-in packs live in code (`services/prompt_packs.py`). Custom packs and a `_hidden` list for hidden built-ins live in this JSON file.

## Tips

- **Use the `n` shortcut** — fastest way to capture a prompt you just iterated on
- **Tags are search-matched** too — add tags like `triage`, `latency`, `errors` to make filtering useful as you build up your library
- **Share packs** by exporting the pack file and committing it to your team's shared repo — teammates import to get the same one-click library

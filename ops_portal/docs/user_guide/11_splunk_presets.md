# Splunk Presets

Dedicated page (`/splunk/presets/`) for managing parameterized search templates.

## Preset Cards

Each preset shows: name, description, tags, time range, stats/events flags, required parameters, and SPL template. Cards are expandable — click to see full details.

## Running a Preset

- **No parameters**: Click **Run** — executes directly and shows results on the search page
- **With parameters**: Click **Run** → fill in the parameter form → click **Run** or **Copy to search**

## Creating Presets

Click **+ New Preset** in the header. Fill in:
- **Name** (snake_case identifier)
- **Description**
- **SPL template** — use `{placeholder}` for parameters
- **Required params** — comma-separated placeholder names
- **Tags** — for filtering
- **Default earliest/latest**
- **Include statistics/events** toggles

## Smart Preset Generator

On the search results page, click **Save as Preset** — the AI analyzes your SPL and generates a clean preset with auto-detected parameters.

## Export / Import

- **Export all**: download icon in header → `splunk_presets.json`
- **Export single**: download icon on each preset card
- **Import**: upload icon → preview with new/exists badges → skip or overwrite

## Deleting Presets

All presets can be deleted including built-in defaults. Built-in presets are "hidden" rather than truly deleted and can be restored by clearing the hidden list in `splunk_presets.json`.

## Search Filter

Type in the filter bar to find presets by name, description, or tags.

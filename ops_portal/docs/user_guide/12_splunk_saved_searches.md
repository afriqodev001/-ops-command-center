# Splunk Saved Searches

Browse and run Splunk saved searches (`/splunk/saved-searches/`). Searches by name directly against Splunk's API — handles 2600+ searches efficiently.

## Finding Searches

Type a name fragment (min 2 characters) and click **Search**. Results are fetched server-side from Splunk — no need to load all searches first.

## Search Results

Each saved search shows:
- **Status dot**: green pulse (scheduled), blue (active), gray (disabled)
- **Name**, owner, app, cron schedule
- Click to **expand**: full description, time range, SPL query

## Enabled/Disabled Toggle

Checkbox in the header hides disabled searches by default. Toggle to show them.

## Actions per Search

- **Run** — executes the saved search's SPL. Button shows spinner while running.
- **Copy to search** — opens the search page with SPL + time range pre-filled
- **Save as preset** — sends SPL to AI preset generator, redirects to Presets page

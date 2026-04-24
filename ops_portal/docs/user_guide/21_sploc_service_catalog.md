# SPLOC Service Catalog

A user-curated list of SignalFx service names that autocompletes the Trace Scraper's Service Name field. Share the catalog across machines via JSON export/import.

## Page: `/sploc/services/`

## Why a catalog?

SignalFx service names are long, case-sensitive, and easy to mistype (`PLDCS_takeapp-service`, `api.v2-gateway`, etc.). The catalog gives the Trace Scraper's Service Name input a native HTML5 autocomplete dropdown — start typing, pick from the list, done. The trace form still accepts any service name (free-text fallback), so the catalog is help, not a constraint.

## Page Layout

**Header** — live total count + actions:
- **Export** — download the whole catalog as `sploc_service_catalog.json`
- **Import** — upload a catalog JSON with skip/overwrite conflict handling
- **New Service** — opens the editor modal (or press `n`)

**Filter toolbar** — search input (`/` to focus) + sort dropdown (A→Z, Z→A, or recently added).

**Grid** — one card per service:
- Service name (monospace, prominent)
- Description (or "No description")
- Tag chips (comma-separated tags render as individual chips)
- Actions: **Edit**, **Export** one, **Delete** (with confirm)

## Keyboard Shortcuts

- **`/`** — focus the search box
- **`n`** — open New Service modal
- **`Esc`** — close any open modal

Suppressed while you're typing in a field.

## Adding a Service

Click **New Service** (or `n`) → fill in the editor:

| Field | Required | Notes |
|-------|----------|-------|
| Service name | ✓ | Must match the exact SignalFx service name. Permissive pattern: letters, numbers, hyphens, dots, underscores. Not editable after creation (delete + re-add to rename). |
| Description | | One-liner shown as a hover hint in the Trace Scraper dropdown. |
| Tags | | Comma-separated. Used by the search filter. |

Save → grid updates in place via HTMX; toast confirms.

## Editing

The service **name** is readonly during edit — this preserves the `added_at` timestamp so "recently added" sort stays meaningful. Only description and tags can be changed.

To rename a service: delete it and re-add under the new name (bad — loses history). Or just add the new name alongside the old one.

## Deleting

Click the trash icon → confirm → the entry is removed from the JSON file. Gone.

## Using the Catalog

Go to **`/sploc/traces/`** → the Service Name field now shows:
- `N services in catalog · manage` (when you have entries)
- `No catalog yet — add services` (when empty)

Start typing in the field — the browser shows matching catalog entries as a dropdown. Pick one → the name is filled in. Descriptions appear as secondary hints in Chrome/Edge (Firefox ignores them, harmlessly).

You can also type a service not in the catalog — the input accepts any value. The catalog is an aid, not a gatekeeper.

## Import / Export

**Export all** — downloads `sploc_service_catalog.json` with every entry (minus internal `added_at` timestamps won't cause issues on re-import).

**Export one** — the ⤓ icon on a card exports just that service.

**Import** — upload a catalog file → preview table shows new vs. existing entries → pick **Skip existing** (default) or **Overwrite existing** → Import.

Pack file format:
```json
{
  "services": {
    "api-gateway": {
      "description": "Main ingress / routing layer",
      "tags": "infra, ingress"
    },
    "payment-service": {
      "description": "Handles Stripe + PayPal integrations",
      "tags": "backend, payment"
    }
  }
}
```

The importer accepts `{"services": {...}}` or `{"catalog": {...}}` (alias) but explicitly rejects `{"packs": {...}}` — the "No services found" error here is intentional, catching accidental cross-imports of prompt-pack files.

## Storage

`ops_portal/sploc/service_catalog.json` — gitignored. User-specific; each machine maintains its own unless you share via export/import.

## Tips

- **Seed from a teammate's file** — ask someone who's already built their catalog to export theirs, then import with overwrite. Instant productivity.
- **Tag by ownership** — add tags like `team-payments`, `team-infra` so each person can filter to their surface area.
- **Less is more** — the datalist dropdown can feel cluttered with 100+ services. Curate to the ones you actually investigate.
- **Not shared across apps** — this is separate from Splunk's preset store, ServiceNow's search presets, and SPLOC's prompt packs. The file formats are distinct on purpose.

# Session Management

All integrations use browser-based authentication via Microsoft Edge with Chrome DevTools Protocol (CDP).

## How It Works

1. **Connect** opens a headed Edge browser to the service's login page
2. You complete SSO/login manually in the browser
3. The app reuses the authenticated session for API calls via `fetch()` inside the browser
4. **Close browser** saves cookies to disk — next task auto-launches headless
5. **Disconnect** closes browser + clears the session registry
6. **Reset** closes browser + deletes the entire profile directory (nuclear option)

## Session Widget

Each integration has a sidebar widget (visible on that integration's pages):

| Status | Dot | Meaning |
|--------|-----|---------|
| Connected | Green pulse | Browser running, authenticated |
| Session saved | Blue | Browser closed, cookies on disk |
| No session | Red | Never connected or reset |

## Integrations

| Integration | Port Base | Login URL |
|-------------|-----------|-----------|
| ServiceNow | 9400+ | `SERVICENOW_BASE` |
| Tachyon | varies | `TACHYON_BASE` |
| Copilot | 9700+ | `COPILOT_TEAMS_URL` |
| Splunk | 9800+ | `SPLUNK_BASE` |

## Reconnect vs Reset

- **Reconnect** — closes the existing browser and opens a new headed one for re-authentication. Use when cookies expire.
- **Reset** — deletes the profile directory entirely (all cookies, cache, local storage). Use when reconnect loops or the profile is corrupted. You'll need to log in from scratch.

## Troubleshooting

**"Reconnect keeps going back to Session saved"**
The old headless browser had stale cookies and was being reused. Fixed: Reconnect now closes the existing browser before opening headed. If still stuck, click Reset.

**Browser opens but stays loading**
Corporate environments may have slow SSO. Wait up to 30 seconds (configurable via `BROWSER_STARTUP_TIMEOUT`).

**Multiple Edge windows**
Each integration uses its own profile directory and port. They don't interfere with each other or your personal Edge.

# Session Management

ServiceNow doesn't expose a simple API key model for the write operations we need. Instead we drive a headed browser (Selenium/Playwright) authenticated with the user's SSO credentials, and keep that browser + profile alive across requests.

## Components

### `core/browser/registry.py`
The source of truth for browser sessions. Key functions:

| Function                           | Purpose |
| ---------------------------------- | ------- |
| `get_or_create_session(integration, user_key)` | Returns existing session dict or creates a fresh profile+port entry |
| `load_session(integration, user_key)`          | Fetch without creating |
| `all_sessions(integration)`                    | Dict of all sessions for an integration |
| `clear_session(integration, user_key)`         | Remove the session entry |

A session dict looks roughly like:

```python
{
    "profile_dir":  "/path/to/chrome-profile",
    "debug_port":   9222,
    "pid":          12345,
    "last_used":    1713300000.12,
    "mode":         "headed",
}
```

### `servicenow/views.py` session helpers

| Helper                    | Returns |
| ------------------------- | ------- |
| `_resolve_session()`      | `(session, user_key)` — tries `'localuser'` first, then any session in the integration dir |
| `_build_session_context()`| Dict with `status`, `status_label`, `user_key`, `session`, `pid`, `port`, `last_used_ago`, `process_alive` — used by every template that renders the session widget |
| `_is_pid_running(pid)`    | Windows-only non-blocking PID check via `tasklist` |

### Status states

```
none          — No session at all
pending       — Session record exists but no PID / browser not yet started
active        — PID alive, last_used recent → good to go
disconnected  — PID dead but record remains → browser was closed
```

## Session widget (UI)

Rendered by `servicenow/templates/servicenow/partials/session_widget.html`. Appears in two places:

1. Bottom of the sidebar (`base.html` → `hx-get="/servicenow/session/widget/"` with `every 20s` poll).
2. Top-right "Session" pill in the header — same endpoint, but JS reads the response HTML to update a tiny status dot.

### Endpoints

| Route                              | View                          | Purpose |
| ---------------------------------- | ----------------------------- | ------- |
| `GET  /servicenow/session/widget/`    | `views.session_widget`         | Sidebar widget HTML (polled) |
| `GET  /servicenow/session/modal/`     | `views.session_modal_content`  | Body of the session manager dialog |
| `POST /servicenow/session/connect/`   | `views.session_connect`        | Dispatches `servicenow_login_open_task` (opens headed browser to login page) |
| `POST /servicenow/session/disconnect/`| `views.session_disconnect`     | Clears the session record |

### Session dialog

Defined in `base.html` as `<dialog id="session-modal">`. Its body is HTMX-loaded on open via a `dialog-open` event:

```html
<dialog id="session-modal" ...>
  <div id="session-modal-body"
       hx-get="/servicenow/session/modal/"
       hx-trigger="dialog-open from:#session-modal"
       hx-swap="innerHTML"></div>
</dialog>
```

Opening the `<dialog>` dispatches a `toggle` event; we forward it as a custom `dialog-open` event that HTMX's `hx-trigger` listens for.

## Auth retry wrapper

Celery tasks that hit the Table API use `with_servicenow_auth_retry(body, operation, retry_once=True)`. The wrapper:

1. Resolves the current session by `user_key`.
2. Runs the `operation(driver)` callable.
3. If the call fails with an auth error (session expired, 401, etc.), optionally retries once after re-auth.

Example (from `changes_create_task`):

```python
def op(driver):
    return create_change_via_table_api(driver, kind=kind, fields=fields)

return with_servicenow_auth_retry(body=body, operation=op, retry_once=True)
```

The `body` dict carries `user_key` — defaults to `'localuser'` if not provided.

## Session guard for create actions

In `base.html`, capture-phase listeners guard `open-create-incident` / `open-create-change` dispatches:

```javascript
document.addEventListener('open-create-incident', (e) => {
  const dot = document.getElementById('header-session-dot');
  if (dot && dot.className.includes('bg-danger')) {
    e.stopImmediatePropagation();
    window.dispatchEvent(new CustomEvent('show-toast', {
      detail: { message: 'No active session — connect ServiceNow first', type: 'warning' }
    }));
    document.getElementById('session-modal').showModal();
  }
}, true); // capture phase — fires before Alpine
```

If the session pill is red (`bg-danger`), the event is stopped, a toast shown, and the session modal opened.

### Applying the guard to a new create action

Either reuse `open-create-incident` / `open-create-change` if semantically appropriate, or add a new event name and a matching capture-phase listener in `base.html`.

## Gotchas

### Stale PIDs on Windows
`_is_pid_running` uses `tasklist` and checks for the PID in output. If `tasklist` isn't in PATH or times out (3s), the function returns False — session will show as disconnected even when the browser is alive. If this becomes a problem, widen the timeout.

### The `localuser` convention
We run single-user today. `user_key='localuser'` is the default everywhere. Multi-user support would need a real auth layer and per-request user_key derivation.

### Session widget polling frequency
Every 20s by default. Faster polling catches changes sooner but adds load. Widget is cheap, so tuning is safe if needed.

### Browser lifecycle and memory management

The headed Edge browser (200-500 MB) is only needed for SSO login. After authentication, cookies persist in the Edge profile directory. The lifecycle:

1. **Connect** — headed browser opens for SSO/MFA login.
2. **Close browser** — user clicks "Close browser" in the session widget, or the auto-idle timer fires. Edge process is killed but the profile directory (with cookies) is preserved.
3. **Session saved** — widget shows "Session saved · cookies on disk · tasks auto-launch headless".
4. **Next task** — `with_servicenow_auth_retry` calls `get_driver()` with `headless=True`. Edge launches headless using the same profile; cookies are valid → auth check passes → task runs.
5. **Cookies expired** — headless auth check fails → wrapper automatically opens headed browser for re-login → cycle repeats.

**Auto-idle shutdown:** `_build_session_context` (called every 20s via the widget poll) checks `last_used` against `browser_idle_timeout_minutes` from user preferences (default 30). If idle exceeds the threshold, `shutdown_browser()` is called automatically.

**Close browser endpoint:** `POST /servicenow/session/close-browser/` calls `shutdown_browser(port, pid)` without calling `clear_session` — the session JSON and profile directory persist. This is different from "Disconnect" which wipes everything.

## See also
- [Celery Tasks](05_celery_tasks.md)
- [Table API](06_table_api.md)

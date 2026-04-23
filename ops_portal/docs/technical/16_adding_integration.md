# Adding a New Integration

Pattern for adding a new browser-authenticated service (like Harness, Grafana, etc.).

## 1. Create the Django App

```bash
python manage.py startapp myapp
```

Add to `INSTALLED_APPS` in `settings.py`. Set `default_auto_field` in `apps.py`.

## 2. Add Port Base

In `settings.py`:
```python
EDGE_PORT_BASES = {
    ...
    "myapp": 9900,
}
```

## 3. Create Session Views

Copy `splunk/session_views.py` as template. Change `_INTEGRATION = 'myapp'` and URL references. Provides:
- `session_widget()` — HTMX-polled sidebar widget
- `session_connect()` — close existing + open headed browser
- `session_close_browser()` — CDP close, cookies saved
- `session_disconnect()` — close + clear session
- `session_reset()` — close + delete profile directory
- `is_session_alive()` — quick CDP port check
- `session_status_json()` — JSON endpoint for Alpine polling

## 4. Create Session Widget Template

Copy any `templates/<app>/partials/session_widget.html`. Change URL paths and variable names. States: connecting, active, disconnected, none.

## 5. Add to Sidebar

In `templates/base.html`:
- Add nav items under a new section header
- Add session widget (conditional: `{% if '/myapp/' in request.path %}`)

## 6. Wire URLs

```python
# myapp/urls.py
path("session/widget/",   session_views.session_widget),
path("session/connect/",  session_views.session_connect),
path("session/close-browser/", session_views.session_close_browser),
path("session/disconnect/", session_views.session_disconnect),
path("session/reset/",    session_views.session_reset),
path("session/status/",   session_views.session_status_json),
```

Mount in `ops_portal/urls.py`:
```python
path('myapp/', include('myapp.urls')),
```

## 7. Add Settings

```python
MYAPP_BASE = os.environ.get('MYAPP_BASE', 'https://...')
```

Add to `.env.example`.

## 8. Create Runner (if using Selenium tasks)

```python
class MyAppRunner(SeleniumRunner):
    def __init__(self, user_key):
        super().__init__(
            integration="myapp",
            user_key=user_key,
            origin_url=settings.MYAPP_BASE,
            auth_check=myapp_auth_check,  # (driver, origin_url) -> bool
        )
```

## 9. Add fetch wrapper (if using browser-based API calls)

Copy `splunk/services/splunk_fetch.py` pattern — `fetch()` inside the browser with SSO cookies.

## Checklist

- [ ] App created + registered in INSTALLED_APPS
- [ ] Port base in EDGE_PORT_BASES
- [ ] session_views.py with all 6 endpoints
- [ ] Session widget template (4 states)
- [ ] Sidebar nav + conditional session widget in base.html
- [ ] URLs mounted
- [ ] Settings + .env.example
- [ ] Runner class (if needed)
- [ ] Auth check function: `(driver, origin_url) -> bool`

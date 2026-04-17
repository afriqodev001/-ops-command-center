# Frontend Patterns

This document is the catalog of UI patterns we use and the gotchas we've hit. Internalize this before writing new pages.

## The three libraries

### HTMX 2.x
Declarative attribute-driven AJAX. Every interactive request either:
- **Full-body swap** via `hx-boost="true"` on `<body>` (nav-link clicks intercepted).
- **Partial swap** via `hx-get` / `hx-post` targeting a specific `#id` with `hx-swap="innerHTML"` (default).

### Alpine.js 3.x
Local reactive state. We use it for modal open/close, tab selection, form state, and client-side polling. Components register via `Alpine.data('name', factory)` — see [Registration pattern](#component-registration-pattern) below.

### Tailwind (CDN runtime)
Play-CDN Tailwind compiles on page load. Custom utility classes are defined in `base.html`'s `<style type="text/tailwindcss">` block (`.glass-card`, `.btn-primary`, `.input-dark`, etc.). Use those shortcuts instead of re-stating the same `@apply` chains.

## Component registration pattern

### The problem
When you navigate to a page via `hx-boost`, HTMX swaps the body. Alpine's `MutationObserver` fires on the new DOM. If your component uses `x-data="presetFormData()"` but `presetFormData` is defined in a `<script>` later in the swapped body, Alpine may hit the element before the script executes → `presetFormData is not defined`.

### The fix
Register Alpine components via `Alpine.data()` inside an `alpine:init` handler. Registrations persist across `hx-boost` navigations (Alpine itself isn't reloaded; only the body is).

```html
<script>
function _definePresetsPage() {
  Alpine.data('presetsPage', (defaultPreset) => ({
    selectedPreset: defaultPreset || '',
    search: '',
    cfg() { return window.PRESET_CONFIGS[this.selectedPreset] || {}; },
    ...
  }));
}
if (window.Alpine) _definePresetsPage();
else document.addEventListener('alpine:init', _definePresetsPage);
</script>
```

Two reasons for the `if/else` branch:
- **First page load** — Alpine hasn't loaded yet (`defer` script). Register via `alpine:init`.
- **hx-boost re-navigation** — Alpine is already running. Register directly.

Re-registering with the same name overwrites; that's fine.

## Passing data to JS via `json_script`

### The problem
Writing `{{ data }}` inside `<script type="application/json">` gets HTML-escaped by Django (`"` → `&quot;`). `<script>` is a *raw text* element, so `textContent` returns the literal `&quot;` — `JSON.parse` fails.

### The fix
Use Django's `{{ data|json_script:"element-id" }}` tag, which escapes `<`, `>`, `&` as JSON unicode escapes (`\u003c`, `\u003e`, `\u0026`) — valid JSON that parses cleanly.

```django
{{ presets_data|json_script:"preset-configs-json" }}
<script>
  window.PRESET_CONFIGS = JSON.parse(document.getElementById('preset-configs-json').textContent);
</script>
```

## Modal patterns

We use the native `<dialog>` element + `showModal()` / `close()`. Benefits: native focus trap, ESC to close, proper backdrop.

### Boilerplate

```html
<dialog id="my-modal"
        class="bg-transparent p-0 m-auto w-full max-w-xl backdrop:bg-black/70 backdrop:backdrop-blur-sm"
        x-data="myModal()"
        @my-event.window="handleOpen($event.detail)">
  <div class="glass-card p-6 animate-slide-up max-h-[90vh] overflow-y-auto">
    <!-- header with X button -->
    <button onclick="document.getElementById('my-modal').close()">×</button>
    ...
  </div>
</dialog>
```

### Opening / closing

```javascript
document.getElementById('my-modal').showModal();    // open
document.getElementById('my-modal').close();        // close
```

### Backdrop click to close

Native `<dialog>` doesn't do this by default. Bind it once:

```javascript
function _bindBackdrop() {
  const m = document.getElementById('my-modal');
  if (m && !m._backdropBound) {
    m.addEventListener('click', e => { if (e.target === m) m.close(); });
    m._backdropBound = true;
  }
}
document.addEventListener('DOMContentLoaded', _bindBackdrop);
document.addEventListener('htmx:afterSettle', _bindBackdrop);
```

Binding on both `DOMContentLoaded` (fresh page) and `htmx:afterSettle` (hx-boost nav) covers both entry paths. The `_backdropBound` guard prevents duplicate listeners.

### Cross-component modal open

When page A wants to open a modal defined in page B (or in `base.html`), use Alpine's `$dispatch`:

```html
<!-- Trigger button anywhere -->
<button @click="$dispatch('open-from-template', { kind: 'incident' })">New from template</button>

<!-- Listener on the dialog -->
<dialog ... x-data="createFromTemplateModal()"
            @open-from-template.window="handleOpen($event.detail)">
```

`$dispatch` fires a `CustomEvent` that bubbles to `window`; `@<event>.window` listens there.

## HTMX form patterns

### Partial swap on submit

```html
<form hx-post="/feature/action/"
      hx-target="#result"
      hx-swap="innerHTML"
      hx-indicator="#spinner">
  {% csrf_token %}
  ...
</form>
<div id="result"></div>
<div id="spinner" class="htmx-indicator">Working…</div>
```

### Retarget response on success vs error

Our save endpoints often return an **error partial** on validation failure and a **list partial** on success. The form's `hx-target` points at the error slot; the server retargets on success using the `HX-Retarget` response header.

```python
if errors:
    return render(request, 'errors_partial.html', {...}, status=200)
# Success:
response = render(request, 'list_partial.html', {...})
response['HX-Retarget'] = '#template-list'
response['HX-Reswap']   = 'innerHTML'
return response
```

Client-side, detect this to reset the form:

```html
<form hx-post="..."
      hx-target="#errors"
      hx-on::after-request="if (event.detail.xhr.getResponseHeader('HX-Retarget')) { this.reset(); document.getElementById('errors').innerHTML = ''; }">
```

### Why status=200 for validation errors

HTMX only swaps 2xx responses by default; 4xx responses are dropped. If you return `422 Unprocessable` with an error partial, the user sees nothing. Use `status=200` for user-level validation errors (still a successful HTTP round-trip) and reserve 4xx for genuine protocol errors.

### `HX-Redirect`

To redirect the browser after an HTMX action:

```python
resp = HttpResponse(status=200)
resp['HX-Redirect'] = '/servicenow/presets/'
return resp
```

HTMX performs a full-page navigation to the given URL.

## Polling for Celery task results

### Server-side polling (live-mode read pages)

Every read page in live mode dispatches a Celery task via `.delay()` and renders a placeholder div. The placeholder polls a generic endpoint; the endpoint routes the result to a shape-specific renderer that returns the final partial.

```html
<!-- Placeholder — included by the page template when live_task_id is set -->
<div hx-get="/servicenow/live/poll/{{ shape }}/{{ task_id }}/"
     hx-trigger="load delay:400ms, every 2s"
     hx-swap="outerHTML"
     class="glass-card p-10 text-center">
  <div class="spinner…"></div>
  Fetching from ServiceNow…
</div>
```

The poll endpoint (`live_poll` in `pages.py`):
- **Task pending** → `204 No Content` (HTMX keeps the existing element in place, polling continues)
- **Task succeeded** → shape renderer returns the final partial (HTMX swaps it in via `outerHTML`, polling stops because the new element has no `hx-trigger`)
- **Task failed** → error partial with a terminal message

Shape registry (`LIVE_POLL_RENDERERS` dict in `pages.py`) maps shape names to renderer functions. Current shapes: `fetch-incidents`, `fetch-changes`, `incidents-list`, `changes-list`, `search-results`, `incident-context`, `change-context`, `change-briefing`, `bulk-review-card`, `preset-result`, `dashboard-recent-incidents`, `dashboard-today-changes`.

### Client-side polling (write operations)

Used by bulk-create and create-from-template flows where the client manages the polling in JS:

```javascript
async _pollTask(item) {
  for (let i = 0; i < 60; i++) {                 // ~2 min ceiling
    await new Promise(r => setTimeout(r, 2000));
    const resp = await fetch(`/tasks/${item.task_id}/result/`);
    const data = await resp.json();
    if (!data.ready) continue;
    if (data.state === 'FAILURE') { item.status = 'error'; return; }
    const result = data.result || {};
    if (result.error) { item.status = 'error'; return; }
    item.status = 'success';
    item.result_number = result.record?.number || '';
    return;
  }
  item.status = 'error';           // timed out
}
```

Two seconds is a reasonable default — faster is noisy, slower feels sluggish.

## Popup window pattern (sequential)

For standard-change tabs that need to be opened one at a time and advance when the user closes them:

```javascript
async function runSequentially(items) {
  for (const item of items) {
    const popup = window.open(item.url, '_blank');
    if (!popup) { item.status = 'error'; item.error = 'popup blocked'; continue; }
    await new Promise(resolve => {
      const iv = setInterval(() => {
        if (popup.closed) { clearInterval(iv); resolve(); }
      }, 500);
    });
    item.status = 'success';
  }
}
```

`popup.closed` works cross-origin — that's the one bit of state the browser will share.

## Gotchas

### `<script>` inside swapped content
HTMX re-executes inline `<script>` tags inside swapped fragments. If you define a function, re-execution redefines it (fine). If you use `const X = …`, the second swap throws a SyntaxError. Use `window.X = …` or function declarations instead.

### Alpine `x-data` with dynamic parameters
`x-data="presetsPage('{{ default_preset }}')"` evaluates the string as JS. For the factory to exist when Alpine processes the element, register via `Alpine.data('presetsPage', factory)` (see above).

### `x-collapse` requires the Alpine Collapse plugin
Which we include in `base.html`:
```html
<script defer src="https://cdn.jsdelivr.net/npm/@alpinejs/collapse@3.x.x/dist/cdn.min.js"></script>
```

### Nested `x-data`
Alpine v3 *merges* nested `x-data` scopes via prototype chain — child can read parent methods. But: the child gets its own reactive proxies for its *own* keys. If you're relying on parent reactivity, call parent methods explicitly rather than reading parent state into a child key.

### `hx-boost` re-execution
Every inline `<script>` inside the swapped body re-runs. Two consequences:
1. Duplicate listener registration — guard with `if (!el._boundOnce) { ...; el._boundOnce = true; }`.
2. Top-level `const` / `let` declarations will error on re-run. Use `window.X = …` for anything that persists.

## See also
- [Architecture](01_architecture.md)
- [Feature: Presets](07_feature_presets.md) — concrete example of these patterns together

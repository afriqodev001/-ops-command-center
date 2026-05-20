"""
Extension points that let feature apps plug into `core` without `core`
importing them — this keeps the dependency arrow pointing feature-app -> core.

Feature apps register in their AppConfig.ready() (see servicenow/apps.py).
`core` never names a feature app.
"""
from __future__ import annotations

from typing import Callable, Optional

# ── Template context providers ──────────────────────────────
# Each provider is fn(request) -> dict; the dict is merged into every
# template context by core.context_processors.ui_context.
_CONTEXT_PROVIDERS: list[Callable] = []


def register_context_provider(fn: Callable) -> None:
    """Register fn(request) -> dict to contribute to every page's context."""
    _CONTEXT_PROVIDERS.append(fn)


def collect_context(request) -> dict:
    """Merge every registered provider's output. A failing provider is
    skipped rather than breaking page rendering."""
    ctx: dict = {}
    for fn in _CONTEXT_PROVIDERS:
        try:
            ctx.update(fn(request) or {})
        except Exception:
            pass
    return ctx


# ── Landing-page (/) dashboard view ─────────────────────────
_dashboard_view: Optional[Callable] = None


def register_dashboard_view(view: Callable) -> None:
    """Let a feature app own the landing page (/). Last registration wins."""
    global _dashboard_view
    _dashboard_view = view


def get_dashboard_view() -> Callable:
    """The registered dashboard view, or core's minimal fallback."""
    if _dashboard_view is not None:
        return _dashboard_view
    from core.views import fallback_dashboard
    return fallback_dashboard

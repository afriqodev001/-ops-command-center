import json
import os
import time
from pathlib import Path
from typing import Dict, Optional, Any

from django.conf import settings


# ============================================================
# Registry location
# ============================================================
def _registry_dir() -> Path:
    """Resolved lazily so mkdir() never runs at import time."""
    d = Path(getattr(settings, "BROWSER_SESSION_DIR", ".browser_sessions"))
    d.mkdir(parents=True, exist_ok=True)
    return d


# ============================================================
# Defaults (safe for future integrations)
# ============================================================
DEFAULT_PORT_BASES = {
    "grafana": 9400,
    "harness": 9500,
    "sploc": 9600,
    "copilot": 9700,
}

DEFAULT_PORT_RANGE = 50  # avoids collisions per integration


# ============================================================
# Internals
# ============================================================
def _safe_user_key(user_key: str) -> str:
    return (user_key or "").strip() or "localuser"


def _integration_dir(integration: str) -> Path:
    d = _registry_dir() / integration
    d.mkdir(exist_ok=True)
    return d


def _registry_path(integration: str, user_key: str) -> Path:
    user_key = _safe_user_key(user_key)
    return _integration_dir(integration) / f"{user_key}.json"


# ============================================================
# Deterministic derivations
# ============================================================
def derive_debug_port(integration: str, user_key: str) -> int:
    """
    Deterministic debug port by integration + user_key.

    Uses:
        settings.EDGE_PORT_BASES
        settings.EDGE_PORT_RANGE

    Falls back safely for unknown integrations.
    """
    bases = getattr(settings, "EDGE_PORT_BASES", DEFAULT_PORT_BASES)
    port_range = int(getattr(settings, "EDGE_PORT_RANGE", DEFAULT_PORT_RANGE))

    base = int(bases.get(integration, 9400))
    return base + (abs(hash(_safe_user_key(user_key))) % port_range)


def derive_profile_dir(integration: str, user_key: str) -> str:
    """
    Deterministic profile directory:
    <PROFILE_BASE>/<integration>/<user_key>
    """
    user_key = _safe_user_key(user_key)

    # Preferred base
    base = getattr(settings, "BROWSER_PROFILE_BASE", None)

    if not base:
        # Windows-friendly fallback
        local = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        base = os.path.join(local, "CopilotOps", "EdgeProfiles")

    return os.path.join(base, integration, user_key)


# ============================================================
# CRUD
# ============================================================
def save_session(integration: str, user_key: str, session: Dict[str, Any]) -> None:
    p = _registry_path(integration, user_key)
    p.write_text(json.dumps(session, indent=2))


def load_session(integration: str, user_key: str) -> Optional[Dict[str, Any]]:
    p = _registry_path(integration, user_key)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        # corrupted session; remove it
        p.unlink(missing_ok=True)
        return None


def clear_session(integration: str, user_key: str) -> None:
    p = _registry_path(integration, user_key)
    if p.exists():
        p.unlink()


def touch_session(integration: str, user_key: str) -> None:
    s = load_session(integration, user_key)
    if not s:
        return
    s["last_used"] = time.time()
    save_session(integration, user_key, s)


# ============================================================
# Session lifecycle helpers
# ============================================================
def get_or_create_session(integration: str, user_key: str) -> Dict[str, Any]:
    """
    Returns an existing session or creates a new one
    with derived profile_dir + debug_port.
    """
    user_key = _safe_user_key(user_key)

    s = load_session(integration, user_key)
    if s:
        return s

    profile_dir = derive_profile_dir(integration, user_key)
    debug_port = derive_debug_port(integration, user_key)

    s = {
        "integration": integration,
        "user_key": user_key,
        "profile_dir": profile_dir,
        "debug_port": debug_port,
        "created_at": time.time(),
        "last_used": time.time(),
        "pid": None,

        # NEW (optional, non-breaking)
        "mode": None,    # "headed" / "headless"
        "origin": None,  # grafana / harness base URL
    }

    save_session(integration, user_key, s)
    return s


def update_runtime_info(
    integration: str,
    user_key: str,
    *,
    pid: Optional[int] = None,
    mode: Optional[str] = None,
    origin: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update runtime-only fields after Edge launch.
    Safe to call repeatedly.
    """
    s = get_or_create_session(integration, user_key)

    if pid is not None:
        s["pid"] = pid
    if mode is not None:
        s["mode"] = mode
    if origin is not None:
        s["origin"] = origin

    s["last_used"] = time.time()
    save_session(integration, user_key, s)
    return s


# ============================================================
# Introspection
# ============================================================
def all_sessions(integration: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    Returns all sessions.
    If integration is provided, only returns those.
    """
    sessions: Dict[str, Dict[str, Any]] = {}

    if integration:
        dirs = [_integration_dir(integration)]
    else:
        dirs = [p for p in _registry_dir().iterdir() if p.is_dir()]

    for d in dirs:
        for p in d.glob("*.json"):
            try:
                sessions[f"{d.name}/{p.stem}"] = json.loads(p.read_text())
            except Exception:
                continue

    return sessions

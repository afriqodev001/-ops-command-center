from __future__ import annotations
from typing import Dict, Any, List
from django.conf import settings

"""
Splunk Run Presets

Goal: UI should run a named preset rather than shipping raw SPL.

Each preset defines:
- description
- spl (template string; Python format placeholders)
- defaults: earliest/latest, include_preview/events, preview/events paging
- required_params: list of required template params
"""

PRESETS: Dict[str, Dict[str, Any]] = {
    "pldcs_takeapp_submission_started_count": {
        "description": 'PLDCS TakeApp: count of "application submission started" events.',
        "spl": (
            'index=pldcs sourcetype="hec:ocp:app" component=ct_app_logs '
            '"kubernetes.namespace_name"="{namespace}" {service} '
            '"application submission started" | stats count'
        ),
        "defaults": {
            "earliest_time": getattr(settings, "SPLUNK_DEFAULT_EARLIEST", "-10m"),
            "latest_time": getattr(settings, "SPLUNK_DEFAULT_LATEST", "now"),
            "include_preview": True,
            "include_events": False,
            "preview_count": 20,
            "preview_offset": 0,
        },
        "required_params": ["namespace", "service"],
    },

    "pldcs_recent_errors_raw_events": {
        "description": "PLDCS: Raw error events for a term in last N minutes.",
        "spl": (
            'index=pldcs sourcetype="hec:ocp:app" component=ct_app_logs '
            '"kubernetes.namespace_name"="{namespace}" "{term}" '
            '| head {limit}'
        ),
        "defaults": {
            "earliest_time": "-30m",
            "latest_time": "now",
            "include_preview": False,
            "include_events": True,
            "events_count": 50,
            "events_offset": 0,
            "events_max_lines": 5,
        },
        "required_params": ["namespace", "term"],
    },
}


def list_presets() -> Dict[str, Dict[str, Any]]:
    """
    Return UI-friendly preset list.
    """
    return {
        name: {
            "description": cfg.get("description", ""),
            "required_params": cfg.get("required_params", []),
            "defaults": cfg.get("defaults", {}),
        }
        for name, cfg in PRESETS.items()
    }


def render_preset(name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Render preset into a concrete SPL string + merged defaults.
    """
    if name not in PRESETS:
        raise ValueError(f"Unknown preset: {name}")

    cfg = PRESETS[name]
    required: List[str] = cfg.get("required_params", [])
    missing = [k for k in required if params.get(k) in (None, "")]
    if missing:
        raise ValueError(f"Missing required params: {', '.join(missing)}")

    # merge defaults with request overrides (request wins)
    defaults = dict(cfg.get("defaults") or {})
    rendered_spl = (cfg.get("spl") or "").format(**params)

    return {
        "search": rendered_spl,
        "defaults": defaults,
    }

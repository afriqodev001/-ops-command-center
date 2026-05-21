from __future__ import annotations
from typing import Dict, Any, List
import json
from pathlib import Path

"""
Preset registry for ServiceNow list/search operations.

Presets resolve in three layers — later layers override earlier ones on a
name collision:
  1. BUILT_IN_PRESETS below       — ship with the code.
  2. team_presets.json            — committed to the repo, shared with the team.
  3. user_presets.json            — machine-local (gitignored), created via the UI.

To share presets with teammates, edit team_presets.json and commit it: it
ships with the app, so teammates get the presets on install — no manual import.

Use get_all_presets() to get the merged registry at runtime.
"""

# team_presets.json is committed to the repo so curated presets ship with the
# app. user_presets.json is machine-local (gitignored) — per-user UI presets.
_TEAM_PRESETS_FILE = Path(__file__).parent.parent / 'team_presets.json'
_USER_PRESETS_FILE = Path(__file__).parent.parent / 'user_presets.json'


def load_team_presets() -> Dict[str, Dict[str, Any]]:
    """Curated presets committed to the repo and shared across the team."""
    if not _TEAM_PRESETS_FILE.exists():
        return {}
    try:
        data = json.loads(_TEAM_PRESETS_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_user_presets() -> Dict[str, Dict[str, Any]]:
    if not _USER_PRESETS_FILE.exists():
        return {}
    try:
        data = json.loads(_USER_PRESETS_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_user_preset(name: str, cfg: Dict[str, Any]) -> None:
    user = load_user_presets()
    user[name] = {**cfg, 'is_user_defined': True}
    _USER_PRESETS_FILE.write_text(json.dumps(user, indent=2), encoding='utf-8')


def delete_user_preset(name: str) -> None:
    user = load_user_presets()
    if name in user:
        del user[name]
        _USER_PRESETS_FILE.write_text(json.dumps(user, indent=2), encoding='utf-8')


def get_all_presets() -> Dict[str, Dict[str, Any]]:
    """Return built-in, team, and user presets merged into one registry.
    Later layers win on a name collision:
    built-ins < team_presets.json < user_presets.json."""
    return {**BUILT_IN_PRESETS, **load_team_presets(), **load_user_presets()}


# =========================================================
# Change + Incident Presets (single registry)
# =========================================================

BUILT_IN_PRESETS: Dict[str, Dict[str, Any]] = {

    # ─────────────────────────────────────────────
    # Change presets
    # ─────────────────────────────────────────────

    "changes_implementing_now": {
        "description": "All changes currently in the Implement state.",
        "table": "change_request",
        "query": "state=implement^ORDERBYDESCsys_updated_on",
        "fields": "number,short_description,state,assignment_group,assigned_to,start_date,end_date,risk,sys_id",
        "defaults": {"limit": 50, "display_value": True},
        "required_params": [],
        "domain": "change",
    },

    "changes_awaiting_review": {
        "description": "Changes waiting for CAB or peer review.",
        "table": "change_request",
        "query": "state=review^ORDERBYDESCsys_updated_on",
        "fields": "number,short_description,state,assignment_group,assigned_to,start_date,risk,sys_id",
        "defaults": {"limit": 50, "display_value": True},
        "required_params": [],
        "domain": "change",
    },

    "changes_scheduled_next_24h": {
        "description": "Approved or scheduled changes starting in the next 24 hours.",
        "table": "change_request",
        "query": (
            "state=scheduled^ORplanned_start_dateBETWEENjavascript:gs.beginningOfToday()"
            "@javascript:gs.endOfTomorrow()^ORDERBYplanned_start_date"
        ),
        "fields": "number,short_description,state,assignment_group,assigned_to,planned_start_date,planned_end_date,risk,sys_id",
        "defaults": {"limit": 25, "display_value": True},
        "required_params": [],
        "domain": "change",
    },

    # ── Oncall review presets — drive the time-window picker on /servicenow/oncall/
    "oncall_changes_today": {
        "description": "Oncall: changes scheduled to start today.",
        "table": "change_request",
        "query": (
            "planned_start_dateBETWEENjavascript:gs.beginningOfToday()"
            "@javascript:gs.endOfToday()^ORDERBYplanned_start_date"
        ),
        "fields": "number,short_description,state,assignment_group,assigned_to,planned_start_date,planned_end_date,risk,type,cmdb_ci,sys_id",
        "defaults": {"limit": 100, "display_value": True},
        "required_params": [],
        "domain": "change",
    },

    "oncall_changes_this_week": {
        "description": "Oncall: changes scheduled to start this week (default).",
        "table": "change_request",
        "query": (
            "planned_start_dateBETWEENjavascript:gs.beginningOfWeek()"
            "@javascript:gs.endOfWeek()^ORDERBYplanned_start_date"
        ),
        "fields": "number,short_description,state,assignment_group,assigned_to,planned_start_date,planned_end_date,risk,type,cmdb_ci,sys_id",
        "defaults": {"limit": 250, "display_value": True},
        "required_params": [],
        "domain": "change",
    },

    "oncall_changes_this_month": {
        "description": "Oncall: changes scheduled to start this month.",
        "table": "change_request",
        "query": (
            "planned_start_dateBETWEENjavascript:gs.beginningOfMonth()"
            "@javascript:gs.endOfMonth()^ORDERBYplanned_start_date"
        ),
        "fields": "number,short_description,state,assignment_group,assigned_to,planned_start_date,planned_end_date,risk,type,cmdb_ci,sys_id",
        "defaults": {"limit": 500, "display_value": True},
        "required_params": [],
        "domain": "change",
    },

    "oncall_changes_next_week": {
        "description": "Oncall: changes scheduled to start next week (default for CR approval review).",
        "table": "change_request",
        "query": (
            "planned_start_dateBETWEENjavascript:gs.beginningOfNextWeek()"
            "@javascript:gs.endOfNextWeek()^ORDERBYplanned_start_date"
        ),
        "fields": "number,short_description,state,assignment_group,assigned_to,planned_start_date,planned_end_date,risk,type,cmdb_ci,sys_id",
        "defaults": {"limit": 250, "display_value": True},
        "required_params": [],
        "domain": "change",
    },

    "change_by_number": {
        "description": "Look up a single change by its CHG number.",
        "table": "change_request",
        "query": "number={number}",
        "fields": "number,short_description,state,assignment_group,assigned_to,start_date,end_date,risk,type,sys_id",
        "defaults": {"limit": 1, "display_value": True},
        "required_params": ["number"],
        "domain": "change",
    },

    "recent_open_changes_by_group": {
        "description": "Open changes for a specific assignment group (requires group sys_id).",
        "table": "change_request",
        "query": "active=true^assignment_group={assignment_group_sys_id}^ORDERBYDESCsys_updated_on",
        "fields": "number,short_description,state,assignment_group,assigned_to,start_date,risk,sys_id",
        "defaults": {"limit": 25, "display_value": True},
        "required_params": ["assignment_group_sys_id"],
        "domain": "change",
    },

    "high_risk_changes": {
        "description": "High or critical risk changes that are active.",
        "table": "change_request",
        "query": "riskIN3,4^active=true^ORDERBYDESCsys_updated_on",
        "fields": "number,short_description,state,assignment_group,assigned_to,start_date,risk,sys_id",
        "defaults": {"limit": 25, "display_value": True},
        "required_params": [],
        "domain": "change",
    },

    "emergency_changes": {
        "description": "Emergency change requests (active).",
        "table": "change_request",
        "query": "type=emergency^active=true^ORDERBYDESCsys_updated_on",
        "fields": "number,short_description,state,assignment_group,assigned_to,start_date,risk,sys_id",
        "defaults": {"limit": 25, "display_value": True},
        "required_params": [],
        "domain": "change",
    },

    # ─────────────────────────────────────────────
    # Incident presets
    # ─────────────────────────────────────────────

    "p1_open_incidents": {
        "description": "All open P1 (Critical) incidents — ordered oldest first.",
        "table": "incident",
        "query": "priority=1^stateNOT IN6,7^ORDERBYopened_at",
        "fields": "number,short_description,priority,state,assignment_group,assigned_to,opened_at,sys_updated_on,sys_id",
        "defaults": {"limit": 50, "display_value": True},
        "required_params": [],
        "domain": "incident",
    },

    "p1_p2_open_incidents": {
        "description": "All open P1 and P2 incidents — for bridge calls and war rooms.",
        "table": "incident",
        "query": "priorityIN1,2^stateNOT IN6,7^ORDERBYpriority^ORDERBYDESCsys_updated_on",
        "fields": "number,short_description,priority,state,assignment_group,assigned_to,opened_at,sys_id",
        "defaults": {"limit": 50, "display_value": True},
        "required_params": [],
        "domain": "incident",
    },

    "incident_by_number": {
        "description": "Look up a single incident by its INC number.",
        "table": "incident",
        "query": "number={number}",
        "fields": "sys_id,number,short_description,state,priority,assignment_group,assigned_to,opened_at,sys_updated_on",
        "defaults": {"limit": 1, "display_value": True},
        "required_params": ["number"],
        "domain": "incident",
    },

    "open_incidents_for_group": {
        "description": "All open incidents assigned to a group (requires group sys_id).",
        "table": "incident",
        "query": "assignment_group={assignment_group_sys_id}^stateNOT IN6,7^ORDERBYpriority",
        "fields": "sys_id,number,short_description,state,priority,assigned_to,opened_at,sys_updated_on",
        "defaults": {"limit": 50, "display_value": True},
        "required_params": ["assignment_group_sys_id"],
        "domain": "incident",
    },

    "unassigned_open_incidents": {
        "description": "Open incidents with no assignee — useful for triage.",
        "table": "incident",
        "query": "assigned_to=NULL^stateNOT IN6,7^ORDERBYpriority^ORDERBYopened_at",
        "fields": "number,short_description,priority,state,assignment_group,opened_at,sys_id",
        "defaults": {"limit": 50, "display_value": True},
        "required_params": [],
        "domain": "incident",
    },

    "recent_open_incidents_by_service": {
        "description": "Open incidents for a business service (requires service sys_id).",
        "table": "incident",
        "query": "active=true^business_service={business_service_sys_id}^ORDERBYDESCsys_updated_on",
        "fields": "number,short_description,priority,state,assignment_group,sys_updated_on,sys_id",
        "defaults": {"limit": 25, "display_value": True},
        "required_params": ["business_service_sys_id"],
        "domain": "incident",
    },

    "sla_breaching_incidents": {
        "description": "Incidents where SLA has already been breached.",
        "table": "incident",
        "query": "sla_due<javascript:gs.now()^stateNOT IN6,7^ORDERBYsla_due",
        "fields": "number,short_description,priority,state,assignment_group,assigned_to,sla_due,sys_id",
        "defaults": {"limit": 25, "display_value": True},
        "required_params": [],
        "domain": "incident",
    },
}


# Backwards-compat alias — prefer get_all_presets() at runtime
PRESETS = BUILT_IN_PRESETS


# =========================================================
# Public helpers
# =========================================================

def list_presets() -> Dict[str, Dict[str, Any]]:
    """
    Return all presets grouped by domain (change / incident).

    Used by Ops Command Center to build menus.
    """
    out: Dict[str, Dict[str, Any]] = {}

    all_presets = get_all_presets()
    for name, cfg in all_presets.items():
        domain = cfg.get("domain", "general")
        out.setdefault(domain, {})

        out[domain][name] = {
            "description": cfg.get("description", ""),
            "required_params": cfg.get("required_params", []),
        }

    return out


def render_preset(name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Render a preset into a concrete Table API list operation.

    Returns:
    {
        table,
        query,
        fields,
        limit,
        display_value
    }
    """
    all_presets = get_all_presets()
    if name not in all_presets:
        raise ValueError(f"Unknown preset: {name}")

    cfg = all_presets[name]

    required: List[str] = cfg.get("required_params", [])
    missing = [k for k in required if params.get(k) in (None, "")]

    if missing:
        raise ValueError(f"Missing required params: {', '.join(missing)}")

    rendered_query = cfg.get("query", "").format(**params)
    defaults = cfg.get("defaults") or {}

    return {
        "table": cfg["table"],
        "query": rendered_query,
        "fields": cfg.get("fields", ""),
        "limit": int(defaults.get("limit", 20)),
        "display_value": defaults.get("display_value"),
    }
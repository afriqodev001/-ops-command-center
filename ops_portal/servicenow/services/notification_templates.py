"""
Oncall outage-notification meeting templates.

File-backed JSON store; keyed by template name. Built-in defaults plus
user overrides (same dual-default pattern as prompts.json /
splunk_presets.json).

Each template has a subject (meeting title), location, and body. They use
Python str.format() placeholders:
  {change_number}      e.g. CHG0034567
  {short_description}  change short description
  {risk}               low/moderate/high
  {assignment_group}   change assignment group
  {scheduled_start}    formatted scheduled start (with timezone)
  {scheduled_end}      formatted scheduled end (with timezone)
  {application}        app performing the change (from matrix)
  {impact_app_names}   comma-joined downstream app names (from matrix outage_impact)
  {impact}             impact text from matrix
  {recipients}         joined recipient list (informational only)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


_STORE_FILE = Path(__file__).parent.parent / 'oncall_email_templates.json'


# Default template — engineers can edit / add more via the UI
DEFAULTS: Dict[str, Dict[str, str]] = {
    'outage_notification': {
        'label': 'Outage Notification (default)',
        'description': 'Outlook meeting invite sent to downstream apps when an oncall reviewer flags a change as outage-likely.',
        'subject': 'Notice of {change_number} affecting Personal lending applications / technology partners',
        'location': (
            'This meeting invite is only a placeholder on your calendar. '
            'No one from Personal Lending platform team is hosting a call'
        ),
        'body': (
            'This meeting is for awareness that {application} will be performing a '
            'Change Request which could impact {impact_app_names} service(s). '
            '{application} will be performing {short_description}.  \n'
            'PLL group is expecting impact. The following are impacts if errors occur:\n'
            '{impact}\n'
            '\n'
            '\n'
            'CR Start time: {scheduled_start}\n'
            'CR End time: {scheduled_end}'
        ),
    },
}


def _load_store() -> Dict[str, Dict[str, str]]:
    if not _STORE_FILE.exists():
        return {}
    try:
        data = json.loads(_STORE_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_store(data: Dict[str, Dict[str, str]]) -> None:
    _STORE_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')


def list_templates() -> Dict[str, Dict[str, str]]:
    """Merged view: built-in defaults + user overrides."""
    user = _load_store()
    merged: Dict[str, Dict[str, str]] = {}
    for name, cfg in DEFAULTS.items():
        merged[name] = dict(cfg)
    for name, cfg in user.items():
        if isinstance(cfg, dict):
            base = dict(merged.get(name) or {})
            base.update(cfg)
            base['is_user_defined'] = True
            merged[name] = base
    return merged


def get_template(name: str) -> Optional[Dict[str, str]]:
    return list_templates().get(name)


def save_template(name: str, cfg: Dict[str, str]) -> None:
    if not name:
        return
    user = _load_store()
    user[name] = {
        'label': str(cfg.get('label', name)).strip(),
        'description': str(cfg.get('description', '')).strip(),
        'subject': str(cfg.get('subject', '')),
        'location': str(cfg.get('location', '')),
        'body': str(cfg.get('body', '')),
    }
    _save_store(user)


def delete_template(name: str) -> None:
    """Removes a user override; built-in defaults cannot be deleted."""
    user = _load_store()
    if name in user:
        del user[name]
        _save_store(user)


def render_template(name: str, ctx: Dict[str, Any]) -> Dict[str, str]:
    """Render subject/location/body via str.format with the provided context.

    Missing placeholders are left bracketed so the engineer notices. Returns
    {'subject', 'location', 'body', 'recipients'}; recipients is populated
    only if ctx['recipients_list'] is provided as a list.
    """
    tpl = get_template(name) or DEFAULTS['outage_notification']

    safe_ctx = _SafeFormatDict(ctx or {})
    subject = (tpl.get('subject') or '').format_map(safe_ctx)
    location = (tpl.get('location') or '').format_map(safe_ctx)
    body = (tpl.get('body') or '').format_map(safe_ctx)

    recipients = ctx.get('recipients_list') or []
    if isinstance(recipients, list):
        recipients_str = '; '.join(recipients)
    else:
        recipients_str = str(recipients)

    return {
        'subject': subject,
        'location': location,
        'body': body,
        'recipients': recipients_str,
    }


class _SafeFormatDict(dict):
    """Treat missing keys as bracketed placeholders so output is obvious."""

    def __missing__(self, key):
        return '{' + str(key) + '}'

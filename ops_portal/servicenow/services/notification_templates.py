"""
Oncall notification email templates.

File-backed JSON store; keyed by template name. Built-in defaults plus
user overrides (same dual-default pattern as prompts.json /
splunk_presets.json).

Templates use Python str.format() placeholders:
  {change_number}      e.g. CHG0034567
  {short_description}  change short description
  {risk}               low/moderate/high
  {assignment_group}   change assignment group
  {scheduled_start}    formatted scheduled start
  {scheduled_end}      formatted scheduled end
  {application}        from matrix
  {impact}             impact_description from matrix
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
        'description': 'Sent to downstream apps when an oncall reviewer flags a change as outage-likely.',
        'subject': '[Heads-up] {change_number} — {short_description} may impact {application}',
        'body': (
            'Hi team,\n\n'
            'Heads-up that a change is going in that we expect to impact {application}:\n\n'
            'Change:        {change_number}\n'
            'Description:   {short_description}\n'
            'Risk:          {risk}\n'
            'Assignment:    {assignment_group}\n'
            'Scheduled:     {scheduled_start} → {scheduled_end}\n\n'
            'Expected impact:\n{impact}\n\n'
            'Please plan accordingly. Reply to this thread if you need '
            'additional details or want to raise concerns.\n\n'
            'Thanks,\nOncall'
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
    """Render subject/body via str.format with the provided context.

    Missing placeholders are left bracketed so the engineer notices. Returns
    {'subject': str, 'body': str, 'recipients': '...'}; recipients is
    populated only if ctx['recipients_list'] is provided as a list.
    """
    tpl = get_template(name) or DEFAULTS['outage_notification']

    safe_ctx = _SafeFormatDict(ctx or {})
    subject = (tpl.get('subject') or '').format_map(safe_ctx)
    body = (tpl.get('body') or '').format_map(safe_ctx)

    recipients = ctx.get('recipients_list') or []
    if isinstance(recipients, list):
        recipients_str = '; '.join(recipients)
    else:
        recipients_str = str(recipients)

    return {
        'subject': subject,
        'body': body,
        'recipients': recipients_str,
    }


class _SafeFormatDict(dict):
    """Treat missing keys as bracketed placeholders so output is obvious."""

    def __missing__(self, key):
        return '{' + str(key) + '}'

"""
AI-assisted field suggestion for incident and change creation.

Builds structured prompts from partial user input (short_description, CI, kind)
and returns suggested values for the remaining fields. The actual LLM call is
a stub today — replace `_call_llm()` with a real API call when ready.

Prompt design:
 - System message sets the role (experienced ServiceNow operations engineer)
 - User message includes the record kind, what the user has filled in so far,
   and which fields need suggestions
 - Response is requested as JSON so we can parse and populate the form

The prompts are intentionally verbose and instructive — they work better with
LLMs than terse ones. The response schema is fixed so the frontend can rely
on the field names.
"""

from __future__ import annotations
from typing import Dict, Any, List
import json

from .creation_templates import KIND_FIELDS, FIELD_LABELS


# ─── Prompt templates ────────────────────────────────────────

from .prompt_store import get_prompt


def _build_user_prompt(kind: str, filled: Dict[str, str], empty_fields: List[str]) -> str:
    """Build the user-facing prompt from what the user has provided so far."""
    kind_label = kind.replace('_', ' ').title()

    lines = [
        f"I am creating a new {kind_label} in ServiceNow.",
        "",
        "Here is what I have filled in so far:",
    ]
    for k, v in filled.items():
        label = FIELD_LABELS.get(k, k.replace('_', ' ').title())
        lines.append(f"  - {label}: {v}")

    lines.append("")
    lines.append("Please suggest values for these empty fields:")
    for f in empty_fields:
        label = FIELD_LABELS.get(f, f.replace('_', ' ').title())
        lines.append(f"  - {f} ({label})")

    lines.append("")
    lines.append("Respond with a JSON object like:")
    example = {f: f"<suggested {f}>" for f in empty_fields[:3]}
    lines.append(json.dumps(example, indent=2))

    return "\n".join(lines)


def _build_incident_from_description_prompt(
    issue_text: str,
    filled: Dict[str, str],
    categories: Dict[str, List[str]],
    target_fields: List[str],
    service_options: List[str] | None = None,
    group_options: List[str] | None = None,
) -> str:
    """Build a prompt that generates incident fields from a free-text issue description."""
    lines = [
        f"The user described this issue:\n\"{issue_text}\"",
        "",
    ]

    if filled:
        lines.append("They have already filled in:")
        for k, v in filled.items():
            label = FIELD_LABELS.get(k, k.replace('_', ' ').title())
            lines.append(f"  - {label}: {v}")
        lines.append("")

    lines.append("Available categories and their subcategories:")
    for cat, subs in sorted(categories.items()):
        lines.append(f"  {cat}: {', '.join(subs)}")

    if service_options:
        lines.append("")
        lines.append("Available services (pick from this list ONLY, or use empty string if none fit):")
        for s in service_options:
            lines.append(f"  - {s}")

    if group_options:
        lines.append("")
        lines.append("Available assignment groups (pick from this list ONLY, or use empty string if none fit):")
        for g in group_options:
            lines.append(f"  - {g}")

    lines.append("")
    lines.append("Generate values for these fields:")
    for f in target_fields:
        label = FIELD_LABELS.get(f, f.replace('_', ' ').title())
        lines.append(f"  - {f} ({label})")

    lines.append("")
    lines.append("Respond with a JSON object:")
    example = {f: f"<value>" for f in target_fields[:4]}
    lines.append(json.dumps(example, indent=2))

    return "\n".join(lines)


def _build_change_from_description_prompt(
    change_text: str,
    kind: str,
    filled: Dict[str, str],
    categories: Dict[str, str],
    reasons: Dict[str, str],
    target_fields: List[str],
    group_options: List[str] | None = None,
    cmdb_ci_options: List[str] | None = None,
) -> str:
    """Build a prompt that generates change fields from a free-text description."""
    kind_label = 'Emergency Change' if kind == 'emergency_change' else 'Normal Change'
    lines = [
        f"The user is creating a {kind_label} and described it as:\n\"{change_text}\"",
        "",
    ]

    if filled:
        lines.append("They have already filled in:")
        for k, v in filled.items():
            label = FIELD_LABELS.get(k, k.replace('_', ' ').title())
            lines.append(f"  - {label}: {v}")
        lines.append("")

    lines.append("Available categories (pick the value, description is for context):")
    for cat, desc in sorted(categories.items()):
        lines.append(f"  - {cat} ({desc})")

    lines.append("")
    lines.append("Available reasons (pick the value, description is for context):")
    for r, desc in sorted(reasons.items()):
        if desc:
            lines.append(f"  - {r} ({desc})")
        else:
            lines.append(f"  - {r}")

    if cmdb_ci_options:
        lines.append("")
        lines.append("Available configuration items (pick from this list ONLY, or empty string if none fit):")
        for ci in cmdb_ci_options:
            lines.append(f"  - {ci}")

    if group_options:
        lines.append("")
        lines.append("Available assignment groups (pick from this list ONLY, or empty string if none fit):")
        for g in group_options:
            lines.append(f"  - {g}")

    lines.append("")
    lines.append("Generate values for these fields:")
    for f in target_fields:
        label = FIELD_LABELS.get(f, f.replace('_', ' ').title())
        lines.append(f"  - {f} ({label})")

    lines.append("")
    lines.append("Respond with a JSON object:")
    example = {f: "<value>" for f in target_fields[:4]}
    lines.append(json.dumps(example, indent=2))

    return "\n".join(lines)


# ─── Unified LLM call — routes to the configured provider ────

AI_PROVIDERS = ('none', 'tachyon', 'claude', 'openai')


def _get_ai_config() -> Dict:
    """Read the active AI provider config from user preferences."""
    try:
        from .user_preferences import load_preferences
        prefs = load_preferences()
    except Exception:
        prefs = {}
    return {
        'provider':             prefs.get('ai_provider', 'none'),
        'tachyon_preset_slug':  prefs.get('ai_tachyon_preset_slug', ''),
        'model':                prefs.get('ai_model', ''),
    }


def _call_llm(system: str, user: str) -> str:
    """Route the LLM call to the configured provider.

    Returns the raw response text (expected to be JSON for field suggestion,
    or free-text for briefing review).
    """
    cfg = _get_ai_config()
    provider = cfg['provider']

    if provider == 'tachyon':
        return _call_tachyon(system, user, cfg)
    elif provider == 'claude':
        return _call_claude(system, user, cfg)
    elif provider == 'openai':
        return _call_openai(system, user, cfg)
    else:
        return json.dumps({'_ai_error': 'No AI provider configured. Open Preferences → AI Provider to set one up.'})


def _check_tachyon_session() -> str:
    """Check if a Tachyon browser session is active.
    Returns '' if OK, or an error message string if not."""
    try:
        from core.browser.registry import load_session
        from core.browser.health import is_debug_alive
        session = load_session('tachyon', 'localuser')
        if not session:
            return 'no_session'
        port = session.get('debug_port')
        if not port or not is_debug_alive(port):
            return 'session_offline'
        return ''
    except Exception:
        return 'check_failed'


def _call_tachyon(system: str, user: str, cfg: Dict) -> str:
    """Call Tachyon Playground via the existing Celery task infrastructure.
    Runs synchronously via .apply() since we need the result inline."""
    preset_slug = cfg.get('tachyon_preset_slug', '')
    if not preset_slug:
        return json.dumps({'_ai_error': 'No Tachyon preset configured. Open Preferences → AI Provider → set the preset slug.'})

    # Check session before dispatching — fail fast with a helpful message
    session_issue = _check_tachyon_session()
    if session_issue:
        msgs = {
            'no_session': 'Tachyon session not found. Click "Connect Tachyon" in the sidebar to log in.',
            'session_offline': 'Tachyon browser is offline. Click "Reconnect" in the sidebar or connect a new session.',
            'check_failed': 'Could not check Tachyon session status.',
        }
        return json.dumps({'_ai_error': msgs.get(session_issue, 'Tachyon session issue.')})

    try:
        from tachyon.tasks import run_tachyon_llm_task
        result = run_tachyon_llm_task.apply(kwargs={
            'user_key': 'localuser',
            'preset_slug': preset_slug,
            'query': user,
            'overrides': {
                'systemInstruction': system,
                **(({'modelId': cfg['model']} if cfg.get('model') else {})),
            },
        }).result

        if isinstance(result, dict):
            if result.get('error'):
                detail = result.get('detail') or result.get('message') or str(result.get('error'))
                return json.dumps({'_ai_error': f'Tachyon error: {detail}'})
            # Tachyon returns nested response shapes
            data = result.get('data') or result
            if isinstance(data, dict):
                text = data.get('answer') or data.get('response') or data.get('text')
                if text:
                    return text
                return json.dumps(data)
            return str(data)
        if not result:
            return json.dumps({'_ai_error': 'Tachyon returned empty response.'})
        return str(result)
    except Exception as e:
        return json.dumps({'_ai_error': f'Tachyon call failed: {e}'})


def _call_claude(system: str, user: str, cfg: Dict) -> str:
    """Call Anthropic Claude API directly."""
    from django.conf import settings as dj_settings
    api_key = getattr(dj_settings, 'AI_API_KEY', '')
    if not api_key:
        return json.dumps({'_ai_error': 'Claude API key not set. Add AI_API_KEY to your .env file.'})
    model = cfg.get('model') or getattr(dj_settings, 'AI_MODEL', 'claude-sonnet-4-20250514')
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=system,
            messages=[{'role': 'user', 'content': user}],
        )
        return response.content[0].text
    except ImportError:
        return json.dumps({'_ai_error': 'anthropic package not installed. Run: pip install anthropic'})
    except Exception as e:
        return json.dumps({'_ai_error': f'Claude API error: {e}'})


def _call_openai(system: str, user: str, cfg: Dict) -> str:
    """Call OpenAI API directly."""
    from django.conf import settings as dj_settings
    api_key = getattr(dj_settings, 'AI_API_KEY', '')
    if not api_key:
        return json.dumps({'_ai_error': 'OpenAI API key not set. Add AI_API_KEY to your .env file.'})
    model = cfg.get('model') or 'gpt-4o'
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user},
            ],
            max_tokens=2048,
        )
        return response.choices[0].message.content
    except ImportError:
        return json.dumps({'_ai_error': 'openai package not installed. Run: pip install openai'})
    except Exception as e:
        return json.dumps({'_ai_error': f'OpenAI API error: {e}'})


# ─── Response parsing helpers ───────────────────────────────

import re

def _extract_json_dict(raw: str) -> Dict | None:
    """Try to parse a JSON dict from an LLM response.

    Handles: raw JSON, markdown code fences, JSON embedded in text.
    Returns the parsed dict, or None if nothing parseable was found.
    """
    if not raw or not raw.strip():
        return None
    text = raw.strip()

    # 1. Direct parse
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # 2. Extract from markdown code fences: ```json ... ``` or ``` ... ```
    fence = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if fence:
        try:
            obj = json.loads(fence.group(1).strip())
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    # 3. Find first { ... } block
    start = text.find('{')
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start:i + 1])
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        pass
                    break

    return None


# ─── Public API ──────────────────────────────────────────────

def suggest_fields(kind: str, filled: Dict[str, str]) -> Dict[str, str]:
    """Given a record kind and the fields the user has already filled,
    return AI-suggested values for the remaining fields.

    Returns a dict of {field_name: suggested_value}. Empty dict if the
    LLM call fails or returns unparseable output.
    """
    all_fields = KIND_FIELDS.get(kind, [])
    if not all_fields:
        return {}

    # Determine which fields are empty and worth suggesting.
    # Skip fields the user already filled + fields that are dropdowns
    # (impact/urgency — those have explicit defaults).
    skip = {'impact', 'urgency'}
    empty_fields = [f for f in all_fields
                    if f not in skip and not (filled.get(f) or '').strip()]

    if not empty_fields:
        return {}

    # Build the prompt
    system = get_prompt('field_suggest')
    user = _build_user_prompt(kind, filled, empty_fields)

    raw = _call_llm(system, user)
    suggestions = _extract_json_dict(raw)
    if suggestions is None:
        return {'_ai_error': f'AI returned unparseable response: {raw[:200]}'}
    if '_ai_error' in suggestions:
        return {'_ai_error': suggestions['_ai_error']}
    return {k: str(v) for k, v in suggestions.items()
            if k in empty_fields and v}


def suggest_from_description(
    issue_text: str,
    filled: Dict[str, str],
    categories: Dict[str, List[str]],
) -> Dict[str, str]:
    """Generate all incident fields from a free-text issue description.

    Loads saved service/group options and constrains the AI to pick from them.
    Returns a dict of {field_name: suggested_value}. Empty dict on failure.
    """
    from .creation_templates import load_combobox_options

    skip = {'impact', 'urgency', 'caller'}
    all_fields = KIND_FIELDS.get('incident', [])
    target_fields = [f for f in all_fields
                     if f not in skip and not (filled.get(f) or '').strip()]

    if not target_fields:
        return {}

    service_options = load_combobox_options('service')
    group_options = load_combobox_options('assignment_group')

    system = get_prompt('incident_from_description')
    user = _build_incident_from_description_prompt(
        issue_text, filled, categories, target_fields,
        service_options=service_options,
        group_options=group_options,
    )

    raw = _call_llm(system, user)
    suggestions = _extract_json_dict(raw)
    if suggestions is None:
        return {'_ai_error': f'AI returned unparseable response: {raw[:200]}'}
    if '_ai_error' in suggestions:
        return {'_ai_error': suggestions['_ai_error']}
    # Validate category/subcategory against allowed values
    if 'category' in suggestions:
        if suggestions['category'] not in categories:
            suggestions['category'] = ''
    if 'subcategory' in suggestions and 'category' in suggestions:
        cat = suggestions['category']
        allowed_subs = categories.get(cat, [])
        if suggestions['subcategory'] not in allowed_subs:
            suggestions['subcategory'] = ''
    # Validate service/assignment_group against saved options
    if 'service' in suggestions and service_options:
        if suggestions['service'] not in service_options:
            suggestions['service'] = ''
    if 'assignment_group' in suggestions and group_options:
        if suggestions['assignment_group'] not in group_options:
            suggestions['assignment_group'] = ''
    return {k: str(v) for k, v in suggestions.items()
            if k in target_fields and v}


def suggest_change_from_description(
    change_text: str,
    kind: str,
    filled: Dict[str, str],
    categories: Dict[str, str],
    reasons: Dict[str, str],
) -> Dict[str, str]:
    """Generate change fields from a free-text description.

    Loads saved group/CI options and constrains the AI to pick from them.
    """
    from .creation_templates import load_combobox_options

    all_fields = KIND_FIELDS.get(kind, [])
    target_fields = [f for f in all_fields
                     if not (filled.get(f) or '').strip()]

    if not target_fields:
        return {}

    group_options = load_combobox_options('assignment_group')
    cmdb_ci_options = load_combobox_options('cmdb_ci')

    system = get_prompt('change_from_description')
    user = _build_change_from_description_prompt(
        change_text, kind, filled, categories, reasons, target_fields,
        group_options=group_options,
        cmdb_ci_options=cmdb_ci_options,
    )

    raw = _call_llm(system, user)
    suggestions = _extract_json_dict(raw)
    if suggestions is None:
        return {'_ai_error': f'AI returned unparseable response: {raw[:200]}'}
    if '_ai_error' in suggestions:
        return {'_ai_error': suggestions['_ai_error']}
    # Validate constrained fields
    if 'category' in suggestions:
        if suggestions['category'] not in categories:
            suggestions['category'] = ''
    if 'reason' in suggestions:
        if suggestions['reason'] not in reasons:
            suggestions['reason'] = ''
    if 'assignment_group' in suggestions and group_options:
        if suggestions['assignment_group'] not in group_options:
            suggestions['assignment_group'] = ''
    if 'cmdb_ci' in suggestions and cmdb_ci_options:
        if suggestions['cmdb_ci'] not in cmdb_ci_options:
            suggestions['cmdb_ci'] = ''
    return {k: str(v) for k, v in suggestions.items()
            if k in target_fields and v}


def build_suggest_prompt(kind: str, filled: Dict[str, str]) -> Dict[str, str]:
    """Return the raw prompt components for debugging / display.
    Useful for the UI to show what would be sent to the LLM."""
    all_fields = KIND_FIELDS.get(kind, [])
    skip = {'impact', 'urgency'}
    empty_fields = [f for f in all_fields
                    if f not in skip and not (filled.get(f) or '').strip()]
    return {
        'system': get_prompt('field_suggest'),
        'user': _build_user_prompt(kind, filled, empty_fields),
        'empty_fields': empty_fields,
    }

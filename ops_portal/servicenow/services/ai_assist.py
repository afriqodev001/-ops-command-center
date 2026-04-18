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

SYSTEM_PROMPT = """You are an experienced IT operations engineer who creates ServiceNow records daily.
Given partial information about a new record, suggest appropriate values for the remaining fields.
Respond ONLY with a JSON object mapping field names to suggested string values.
Do not include fields the user has already filled in.
If you are unsure about a field, use an empty string rather than guessing incorrectly.
For text fields like description, justification, implementation_plan, backout_plan, and test_plan,
provide practical, concise content that an operations team would actually use."""


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
        return '{}'


def _call_tachyon(system: str, user: str, cfg: Dict) -> str:
    """Call Tachyon Playground via the existing Celery task infrastructure.
    Runs synchronously via .apply() since we need the result inline."""
    preset_slug = cfg.get('tachyon_preset_slug', '')
    if not preset_slug:
        return '{}'
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
                return '{}'
            # Tachyon returns nested response shapes
            data = result.get('data') or result
            if isinstance(data, dict):
                return data.get('response') or data.get('text') or json.dumps(data)
            return str(data)
        return str(result) if result else '{}'
    except Exception:
        return '{}'


def _call_claude(system: str, user: str, cfg: Dict) -> str:
    """Call Anthropic Claude API directly."""
    from django.conf import settings as dj_settings
    api_key = getattr(dj_settings, 'AI_API_KEY', '')
    if not api_key:
        return '{}'
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
        return '{}'
    except Exception:
        return '{}'


def _call_openai(system: str, user: str, cfg: Dict) -> str:
    """Call OpenAI API directly."""
    from django.conf import settings as dj_settings
    api_key = getattr(dj_settings, 'AI_API_KEY', '')
    if not api_key:
        return '{}'
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
        return '{}'
    except Exception:
        return '{}'


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
    system = SYSTEM_PROMPT
    user = _build_user_prompt(kind, filled, empty_fields)

    # Call LLM
    try:
        raw = _call_llm(system, user)
        suggestions = json.loads(raw)
        if not isinstance(suggestions, dict):
            return {}
        # Only return fields we actually asked for
        return {k: str(v) for k, v in suggestions.items()
                if k in empty_fields and v}
    except (json.JSONDecodeError, Exception):
        return {}


def build_suggest_prompt(kind: str, filled: Dict[str, str]) -> Dict[str, str]:
    """Return the raw prompt components for debugging / display.
    Useful for the UI to show what would be sent to the LLM."""
    all_fields = KIND_FIELDS.get(kind, [])
    skip = {'impact', 'urgency'}
    empty_fields = [f for f in all_fields
                    if f not in skip and not (filled.get(f) or '').strip()]
    return {
        'system': SYSTEM_PROMPT,
        'user': _build_user_prompt(kind, filled, empty_fields),
        'empty_fields': empty_fields,
    }

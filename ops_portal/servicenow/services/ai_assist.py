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


# ─── LLM call (stub) ────────────────────────────────────────

def _call_llm(system: str, user: str) -> str:
    """Stub — replace with a real API call to Claude, OpenAI, etc.

    Expected to return a JSON string like:
        {"category": "Network", "assignment_group": "Network Ops", ...}

    When wiring the real call:
        from anthropic import Anthropic
        client = Anthropic(api_key=settings.AI_API_KEY)
        response = client.messages.create(
            model=settings.AI_MODEL,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text

    For now, returns empty JSON so the UI flow works end-to-end
    without an API key.
    """
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

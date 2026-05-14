"""
Tiny template engine used by long-form field extractors.

Placeholders:
  {Bnn}          → cell value from the first sheet (parsed.cells[Bnn])
  {Annn} etc     → same; any single column letter followed by digits
  {sheet:Name}   → joined text of the named sheet (parsed.sheets[Name])
  <human input>  → left in place verbatim — submit refuses if any remain

Templates live in the prompt store under keys like:
  change_intake_template_description
  change_intake_template_justification
  change_intake_template_implementation_plan
  change_intake_template_backout_plan

So engineers can edit them at /servicenow/prompts/ without touching code.
"""
from __future__ import annotations

import re

from .mapping_spec import ParsedPayload


HUMAN_INPUT_MARKER = '<human input>'
TODO_MARKER_PREFIX = '[TODO:'

_CELL_RE = re.compile(r'\{([A-Z]+\d+)\}')
_SHEET_RE = re.compile(r'\{sheet:([^}]+)\}')


def _substitute_cells(template: str, parsed: ParsedPayload) -> str:
    def repl(match: re.Match) -> str:
        key = match.group(1)
        return (parsed.cells.get(key) or '').strip()
    return _CELL_RE.sub(repl, template)


def _substitute_sheets(template: str, parsed: ParsedPayload) -> str:
    def repl(match: re.Match) -> str:
        name = match.group(1).strip()
        return (parsed.sheets.get(name) or '').strip()
    return _SHEET_RE.sub(repl, template)


def render_template(template_key: str, parsed: ParsedPayload) -> str:
    """Look up `template_key` in the prompt store and render against
    `parsed`. Cell + sheet placeholders are substituted; `<human input>`
    markers are preserved for the engineer to fill in."""
    try:
        from servicenow.services.prompt_store import get_prompt
        template = get_prompt(template_key) or ''
    except Exception:
        template = ''
    if not template:
        return ''
    template = _substitute_cells(template, parsed)
    template = _substitute_sheets(template, parsed)
    return template.strip()


def find_unfilled_markers(text: str) -> bool:
    """True if `text` still contains an unfilled `<human input>` or `[TODO:` marker."""
    if not text:
        return False
    return HUMAN_INPUT_MARKER in text or TODO_MARKER_PREFIX in text

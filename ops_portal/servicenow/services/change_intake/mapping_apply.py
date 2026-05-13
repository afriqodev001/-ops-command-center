"""
Apply a VendorMapping to a parsed payload, producing the list of
FieldProposals the wizard renders + edits.

`build_description` re-assembles the combined ServiceNow `description`
field from a structured template at submit time, using whatever the
engineer has edited. Empty `<human input>` sub-sections render as
visible `[TODO: <name>]` placeholders so they're flagged to reviewers
in ServiceNow.
"""
from __future__ import annotations

from typing import Dict, List

from .mapping_spec import ParsedPayload, VendorMapping


def apply_mapping(parsed: ParsedPayload, mapping: VendorMapping) -> List[Dict]:
    """Run each FieldRule's extractor against the parsed payload and return
    a list of proposal dicts ready to be serialised into JSON."""
    out: List[Dict] = []
    for rule in mapping.rules:
        try:
            value = rule.extractor(parsed) or ''
        except Exception as e:
            value = f'[extractor error: {e}]'
        out.append({
            'target_field': rule.target_field,
            'label':        rule.label or rule.target_field,
            'source_rule':  rule.source_rule,
            'kind':         rule.kind,
            'group':        rule.group,
            'value':        value,
        })
    return out


# ── Description assembly ──────────────────────────────────────────

_DESCRIPTION_SECTIONS = [
    # (proposal field key, section heading shown in CR description)
    ('_executive_summary',         'Executive summary'),
    ('_benefit',                   'Benefit / business justification'),
    ('_why_now',                   'Why now'),
    ('_impacts_if_not_installed',  'Impacts if not installed'),
    ('u_outage',                   'Outage'),
    ('test_plan',                  'Testing strategy'),
    ('_install_steps',             'Install steps'),
    ('_install_duration',          'Install duration'),
    ('u_who_will_install',         'Who will install'),
    ('u_implementation_strategy',  'Implementation strategy'),
    ('u_implementation_approach',  'Implementation approach'),
    ('u_who_will_validate',        'Who will validate'),
    ('_backout_steps',             'Backout steps'),
]


def build_description(proposals_by_field: Dict[str, str]) -> str:
    """Assemble the combined `description` from the per-section proposal
    values. Empty sections render as `[TODO: <name>]` placeholders."""
    out_lines: List[str] = []
    for key, heading in _DESCRIPTION_SECTIONS:
        value = (proposals_by_field.get(key) or '').strip()
        out_lines.append(f'== {heading} ==')
        if value:
            out_lines.append(value)
        else:
            out_lines.append(f'[TODO: {heading}]')
        out_lines.append('')
    return '\n'.join(out_lines).strip()


# ── Helpers for views/tasks ───────────────────────────────────────

def fields_for_servicenow(proposals: List[Dict]) -> Dict[str, str]:
    """Project the editable proposals down to the dict we pass to
    `create_change_via_table_api(fields=...)`. Hidden helper fields
    (those starting with '_') are folded into the combined description
    rather than sent to ServiceNow directly."""
    by_field = {p['target_field']: (p.get('value') or '').strip() for p in proposals}

    # Build the final description from sub-sections + replace whatever
    # was previously stored under 'description'.
    by_field['description'] = build_description(by_field)

    return {
        k: v for k, v in by_field.items()
        if not k.startswith('_') and v
    }

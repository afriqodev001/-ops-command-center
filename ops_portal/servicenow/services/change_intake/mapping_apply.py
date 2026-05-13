"""
Apply a VendorMapping to a parsed payload, producing the list of
FieldProposals the wizard renders + edits.

`build_description` assembles the combined ServiceNow `description` from
whichever sections the active ChangeIntakeTemplate (in template_store)
references. Empty sub-section values render as `[TODO: <heading>]`
placeholders so they're flagged in the final CR.
"""
from __future__ import annotations

from typing import Dict, List, Set

from .mapping_spec import ParsedPayload, VendorMapping
from .template_store import load_template


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


def build_description(proposals_by_field: Dict[str, str], vendor_slug: str) -> str:
    """Assemble the combined `description` for `vendor_slug` from the per-section
    proposal values using whichever template is active in template_store.

    Empty sections render as `[TODO: <heading>]` (or the section's overridden
    placeholder text, if set)."""
    template = load_template(vendor_slug) or {}
    sections = template.get('sections') or []

    if not sections:
        # Fall back to a single dump of the description proposal value, if any.
        return (proposals_by_field.get('description') or '').strip()

    lines: List[str] = []
    intro = (template.get('intro') or '').strip()
    if intro:
        lines.append(intro)
        lines.append('')

    for section in sections:
        heading = section.get('heading') or section.get('field') or ''
        field_key = section.get('field') or ''
        placeholder = section.get('placeholder') or f'[TODO: {heading}]'

        value = (proposals_by_field.get(field_key) or '').strip()
        lines.append(f'== {heading} ==')
        lines.append(value if value else placeholder)
        lines.append('')

    outro = (template.get('outro') or '').strip()
    if outro:
        lines.append(outro)

    return '\n'.join(lines).strip()


def fields_for_servicenow(proposals: List[Dict], vendor_slug: str) -> Dict[str, str]:
    """Project the editable proposals down to the dict we pass to
    `create_change_via_table_api(fields=...)`.

    - Fields whose names start with '_' are hidden helpers folded into the
      combined description by build_description.
    - The combined `description` is rebuilt at submit time from the current
      sub-section values + the active template.
    """
    by_field = {p['target_field']: (p.get('value') or '').strip() for p in proposals}

    by_field['description'] = build_description(by_field, vendor_slug)

    return {
        k: v for k, v in by_field.items()
        if not k.startswith('_') and v
    }


def description_field_keys(vendor_slug: str) -> Set[str]:
    """The set of proposal fields the active template assembles into the
    combined description. Useful for the UI to render the description-only
    sections as a separate accordion."""
    template = load_template(vendor_slug) or {}
    return {s.get('field') for s in (template.get('sections') or []) if s.get('field')}

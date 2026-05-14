"""
Apply a VendorMapping to a parsed payload, producing the list of
FieldProposals the wizard renders + edits.

Each FieldRule's extractor pulls a value from the parsed payload.
For vendor-default fields the extractor returns empty and
`apply_vendor_defaults` fills it in from the VendorConfig row.
For template-rendered fields (description, justification, etc.) the
extractor calls `render_template(<key>, parsed)` which substitutes
{Bnn} / {sheet:Name} placeholders against the parsed payload and
leaves `<human input>` markers in place.
"""
from __future__ import annotations

import json
from typing import Dict, List, Tuple

from .mapping_spec import ParsedPayload, VendorMapping
from .template_render import find_unfilled_markers


def apply_mapping(parsed: ParsedPayload, mapping: VendorMapping) -> List[Dict]:
    """Run each FieldRule's extractor against the parsed payload."""
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


def apply_vendor_defaults(proposals: List[Dict], vendor_template: str) -> List[Dict]:
    """Overlay vendor defaults onto any proposal whose value is blank.

    Engineer edits (non-blank values) are preserved. If no VendorConfig
    exists for the vendor, the proposals come back untouched.
    """
    try:
        from servicenow.models import VendorConfig
        cfg = VendorConfig.objects.filter(vendor_template=vendor_template).first()
    except Exception:
        cfg = None
    if not cfg:
        return proposals
    defaults = cfg.defaults()
    if not defaults:
        return proposals
    for p in proposals:
        if (p.get('value') or '').strip():
            continue
        value = defaults.get(p['target_field'])
        if value:
            p['value'] = value
    return proposals


def fields_for_servicenow(proposals: List[Dict]) -> Dict[str, str]:
    """Project the editable proposals down to the dict we pass to
    `create_change_via_table_api(fields=...)`. Drops underscore-prefixed
    helper fields and blank values."""
    return {
        p['target_field']: (p.get('value') or '').strip()
        for p in proposals
        if not p['target_field'].startswith('_')
        and (p.get('value') or '').strip()
    }


def find_unfilled_proposals(proposals: List[Dict]) -> List[Tuple[str, str]]:
    """Return [(target_field, label), …] for any proposal that still
    contains a `<human input>` or `[TODO:` marker. Used by the submit
    endpoint to refuse dispatch until the engineer fills them in."""
    out: List[Tuple[str, str]] = []
    for p in proposals:
        if find_unfilled_markers(p.get('value') or ''):
            out.append((p['target_field'], p.get('label') or p['target_field']))
    return out

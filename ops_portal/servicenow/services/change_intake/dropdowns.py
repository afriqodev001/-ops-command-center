"""
Fixed-list dropdown options for the change-intake mapping form.

Keyed by ServiceNow target_field. A field that appears here renders as a
`<select>` in the mapping form (and the per-field AI suggestion swap)
instead of a free-text textarea. AI suggestions that don't match the
allowed list are dropped, otherwise the dropdown would silently fall
back to its empty option.

Category and Reason live elsewhere (servicenow.services.creation_templates)
because they're sourced from the existing change-creation lists and carry
descriptions per option.
"""
from __future__ import annotations

from typing import Dict, List

DROPDOWN_OPTIONS: Dict[str, List[str]] = {
    'u_outage': [
        'Full',
        'None Expected',
        'Partial',
    ],
    'u_testing_approach': [
        'Fully Automated',
        'Manual',
        'Partially Automated',
        'Risk Mitigation',
    ],
    'u_implementation_strategy': [
        'Big Bang',
        'Blue/Green',
        'Canary',
        'Feature Toggling',
        'Hybrid',
        'Phased',
        'Pilot',
    ],
    'u_implementation_approach': [
        'Fully Automated',
        'manual',
        'Partially Automated',
    ],
    'u_backout_approach': [
        'Fail Forward',
        'Fully Automated',
        'Manual',
        'Partially Automated',
    ],
    'u_backout_duration': [
        '< 30 minutes',
        '31 - 60 minutes',
        '61 - 120 minutes',
        '120+ minutes',
    ],
}


def options_for(target_field: str) -> List[str]:
    """Return the dropdown options for a target_field, or an empty list."""
    return list(DROPDOWN_OPTIONS.get(target_field, ()))


def is_dropdown(target_field: str) -> bool:
    return target_field in DROPDOWN_OPTIONS

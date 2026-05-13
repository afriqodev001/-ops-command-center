"""
JSON-backed editable description template per vendor.

The vendor mapping decides which proposal fields exist; the *template*
decides how those fields are stitched together into the combined CR
`description`. Engineers can edit the template at runtime via the UI
without code changes (mirrors the prompt_store pattern at
servicenow/services/prompt_store.py).

Schema per vendor:
{
  "name":     "<display name>",
  "intro":    "<optional preamble — e.g. 'CT Template - Version 3.1'>",
  "outro":    "<optional footer>",
  "sections": [
    {
      "heading":           "Executive summary",
      "field":             "_executive_summary",
      "placeholder":       ""     # optional override for empty value, default '[TODO: <heading>]'
    },
    ...
  ]
}
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Dict, List

_STORE_FILE = Path(__file__).parent.parent.parent / 'change_intake_templates.json'


DEFAULTS: Dict[str, Dict] = {
    'epsilon': {
        'name': 'Epsilon — CT description template',
        'intro': (
            "CT Template - Version 3.1\n"
            "Template Guide: see internal wiki page (Planning Tab).\n"
            "— do not remove pre-generated headings; add responses on the next line —"
        ),
        'outro': '',
        'sections': [
            {'heading': 'Executive summary',
             'field': '_executive_summary',
             'placeholder': ''},
            {'heading': 'Benefit / business justification',
             'field': '_benefit',
             'placeholder': ''},
            {'heading': 'Why now',
             'field': '_why_now',
             'placeholder': ''},
            {'heading': 'Impacts if not installed',
             'field': '_impacts_if_not_installed',
             'placeholder': ''},
            {'heading': 'Outage',
             'field': 'u_outage',
             'placeholder': ''},
            {'heading': 'Alert configuration / monitoring',
             'field': '_alert_monitoring',
             'placeholder': ''},
            {'heading': 'Error handling',
             'field': '_error_handling',
             'placeholder': ''},
            {'heading': 'Environment predecessors',
             'field': '_env_predecessors',
             'placeholder': ''},
            {'heading': 'Pre-prod testing overview',
             'field': '_testing_overview',
             'placeholder': ''},
            {'heading': 'Components / impacted items',
             'field': '_components',
             'placeholder': ''},
            {'heading': 'Impact assessment',
             'field': '_impact_assessment',
             'placeholder': ''},
            {'heading': 'Install steps',
             'field': '_install_steps',
             'placeholder': ''},
            {'heading': 'Install duration / window',
             'field': '_install_duration',
             'placeholder': ''},
            {'heading': 'Who will install',
             'field': 'u_who_will_install',
             'placeholder': ''},
            {'heading': 'Implementation strategy',
             'field': 'u_implementation_strategy',
             'placeholder': ''},
            {'heading': 'Implementation approach',
             'field': 'u_implementation_approach',
             'placeholder': ''},
            {'heading': 'Validation steps',
             'field': '_validation_steps',
             'placeholder': ''},
            {'heading': 'Who will validate',
             'field': 'u_who_will_validate',
             'placeholder': ''},
            {'heading': 'Backout steps',
             'field': '_backout_steps',
             'placeholder': ''},
            {'heading': 'Approval / release notes',
             'field': '_notes',
             'placeholder': ''},
        ],
    },
}


def _read_file() -> Dict[str, Dict]:
    if not _STORE_FILE.exists():
        return {}
    try:
        with _STORE_FILE.open('r', encoding='utf-8') as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_file(data: Dict[str, Dict]) -> None:
    _STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _STORE_FILE.open('w', encoding='utf-8') as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def list_vendors() -> List[str]:
    return sorted(set(list(DEFAULTS.keys()) + list(_read_file().keys())))


def load_template(vendor_slug: str) -> Dict:
    """Return the active template for a vendor. Persisted edits win over defaults."""
    persisted = _read_file().get(vendor_slug)
    if persisted:
        return copy.deepcopy(persisted)
    default = DEFAULTS.get(vendor_slug)
    return copy.deepcopy(default) if default else {}


def save_template(vendor_slug: str, template: Dict) -> None:
    data = _read_file()
    data[vendor_slug] = template
    _write_file(data)


def reset_template(vendor_slug: str) -> None:
    data = _read_file()
    data.pop(vendor_slug, None)
    _write_file(data)


def is_customised(vendor_slug: str) -> bool:
    return vendor_slug in _read_file()

"""
Unified creation-template store.

A single JSON file (creation_templates.json) holds templates for creating
records across four kinds:

    standard_change  — URL-based (opens ServiceNow UI pre-populated)
    normal_change    — Table API payload
    emergency_change — Table API payload
    incident         — Table API payload

Entry shape:

    {
        "ssl_renewal": {
            "kind":  "standard_change",
            "label": "SSL certificate renewal",
            "url":   "https://INSTANCE.service-now.com/..."
        },
        "db_patching": {
            "kind":  "normal_change",
            "label": "Database patching",
            "fields": {
                "short_description": "Monthly DB patching",
                "assignment_group":  "Database Ops",
                "risk":              "moderate"
            }
        },
        "p1_bridge": {
            "kind":  "incident",
            "label": "P1 bridge call",
            "fields": {
                "short_description": "P1 - ",
                "priority":          "1",
                "assignment_group":  "Platform"
            }
        }
    }

On first read, if creation_templates.json is missing but the legacy
standard_change_templates.json exists, entries are migrated in-place with
kind="standard_change".
"""

from __future__ import annotations
from typing import Dict, Any, List
from pathlib import Path
import json

_STORE_FILE  = Path(__file__).parent.parent / 'creation_templates.json'
_LEGACY_FILE = Path(__file__).parent.parent / 'standard_change_templates.json'

VALID_KINDS = ('standard_change', 'normal_change', 'emergency_change', 'incident')

KIND_LABELS = {
    'standard_change':  'Standard change',
    'normal_change':    'Normal change',
    'emergency_change': 'Emergency change',
    'incident':         'Incident',
}

# Fields each API-based kind renders in the create form, in display order.
KIND_FIELDS: Dict[str, List[str]] = {
    'standard_change':  [],  # No form fields — opens in ServiceNow UI via template URL
    'normal_change':    ['cmdb_ci', 'short_description', 'category', 'reason',
                         'description', 'assignment_group', 'start_date', 'end_date',
                         'justification', 'implementation_plan', 'backout_plan'],
    'emergency_change': ['cmdb_ci', 'short_description', 'assignment_group',
                         'category', 'reason', 'description',
                         'start_date', 'end_date',
                         'justification', 'implementation_plan', 'backout_plan', 'test_plan'],
    'incident':         ['caller', 'category', 'subcategory', 'service',
                         'short_description', 'description', 'assignment_group',
                         'impact', 'urgency'],
}

# Fields that are mandatory per kind (UI marks them with a red asterisk).
KIND_REQUIRED: Dict[str, List[str]] = {
    'standard_change':  [],
    'normal_change':    ['cmdb_ci', 'short_description', 'category', 'reason',
                         'description', 'assignment_group'],
    'emergency_change': ['cmdb_ci', 'short_description', 'assignment_group',
                         'category', 'reason', 'description'],
    'incident':         ['caller', 'category', 'subcategory', 'service',
                         'short_description', 'description', 'assignment_group'],
}

# Default field values injected into new templates of each kind.
# Impact 3 + Urgency 3 → Priority 5 (Very Low) in standard SN config.
INCIDENT_FIELD_DEFAULTS: Dict[str, str] = {
    'impact':  '3',
    'urgency': '3',
}

# Human-readable labels for fields that don't self-describe well.
FIELD_LABELS: Dict[str, str] = {
    'cmdb_ci':              'Configuration item',
    'short_description':    'Short description',
    'std_change_template':  'Standard change template name',
    'assignment_group':     'Assignment group',
    'start_date':           'Planned start date',
    'end_date':             'Planned end date',
    'implementation_plan':  'Implementation plan',
    'backout_plan':         'Backout plan',
    'test_plan':            'Test plan',
    'caller':               'Caller',
    'category':             'Category',
    'subcategory':          'Subcategory',
    'service':              'Service',
    'description':          'Description',
    'reason':               'Reason',
    'justification':        'Justification',
    'impact':               'Impact',
    'urgency':              'Urgency',
}

# Fields that render as <textarea> instead of <input>.
TEXTAREA_FIELDS = {
    'description', 'justification', 'implementation_plan',
    'backout_plan', 'test_plan',
}

# ── Incident category → subcategory tree ───────────────────────
# Configurable via incident_field_options.json; these are the defaults.

INCIDENT_CATEGORIES: Dict[str, List[str]] = {
    'Data Center Migration': [
        'Configuration and Software Issues', 'Data Integrity and Loss',
        'Infrastructure Failures', 'Performance Degradation', 'Security Breaches',
    ],
    'Data Integrity': [
        'Inaccessible data', 'Incorrect Data', 'Missing Data',
    ],
    'Hardware': [
        'Peripheral Failures', 'Server Failures', 'Workstation Failures',
    ],
    'Network': [
        'Bandwidth and Performance Issues', 'Connectivity Problems', 'DNS Issues',
    ],
    'SACM Data Quality': [
        'Data Discrepancy', 'Unauthorized Install', 'Validation Discrepancy',
    ],
    'Software and Application': [
        'Application Crashes', 'Installation/Update Failures', 'Licensing Issues',
    ],
    'Technology Faults': [
        'Error/Fault Message', 'Major Alert/Alarm', 'Unexpected Behavior',
    ],
    'Technology Performance': [
        'Capacity Management', 'Down/Unreachable', 'Frozen/Unresponsive',
        'Jammed/Blocked', 'Slow/Times Out',
    ],
    'Technology Processing': [
        'Incompatibility', 'Non-Compliant', 'Order/Request Issue', 'User Complaint',
    ],
    'Technology Security': [
        'Access Issue', 'Equipment Theft/Loss', 'Other Security Concern',
    ],
    'Vendor/Third-Party': [
        'Error/Fault Message', 'Major Alert/Alarm', 'Unexpected Behavior',
    ],
}

# ── Change category + reason options ───────────────────────────
# Category value is the word before the hyphen; description is for display.

CHANGE_CATEGORIES: Dict[str, str] = {
    'Application Software': 'Change to custom code, no code, or COTS software',
    'Database':             'Change to data and database configuration',
    'Data Center':          'Change to Data center hardware',
    'Facilities':           'Change to facilities',
    'Hardware':             'Change to infrastructure hardware',
    'Network':              'Change to network configuration',
    'Service':              'Change to company services',
    'System Software':      'Change to Operating System or layered Product software',
    'Telecom':              'Change to Telecommunications configuration',
}

CHANGE_REASONS: List[str] = [
    'Commission', 'Configuration', 'Data Updates', 'DCMS', 'DCMS - Prod Staged',
    'Decommission', 'Defect Fix', 'Diagnostics', 'Divestiture',
    'Elevated Access Request', 'Enhancement', 'Facilities Maintenance',
    'Hardware Update', 'Patching', 'Resiliency Exercise',
    'Restart/Reboot/Restore', 'Software Install / Uninstall',
    'Software Update', 'Trace and Validate',
]


# ── Combobox options (service, assignment_group, cmdb_ci) ─────
# Stored in field_options.json so users can add their own values.

_OPTIONS_FILE = Path(__file__).parent.parent / 'field_options.json'


_LEGACY_OPTIONS_FILE = Path(__file__).parent.parent / 'incident_field_options.json'


def _load_field_options() -> Dict[str, Any]:
    # Migrate from old filename if needed
    if not _OPTIONS_FILE.exists() and _LEGACY_OPTIONS_FILE.exists():
        try:
            data = json.loads(_LEGACY_OPTIONS_FILE.read_text(encoding='utf-8'))
            _OPTIONS_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')
            return data
        except Exception:
            pass
    if not _OPTIONS_FILE.exists():
        return {}
    try:
        return json.loads(_OPTIONS_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _save_field_options(data: Dict[str, Any]) -> None:
    _OPTIONS_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')


def load_incident_categories() -> Dict[str, List[str]]:
    opts = _load_field_options()
    return opts.get('categories', INCIDENT_CATEGORIES)


def load_change_categories() -> Dict[str, str]:
    opts = _load_field_options()
    return opts.get('change_categories', CHANGE_CATEGORIES)


def load_change_reasons() -> List[str]:
    opts = _load_field_options()
    return opts.get('change_reasons', CHANGE_REASONS)


def save_change_categories(categories: Dict[str, str]) -> None:
    opts = _load_field_options()
    opts['change_categories'] = categories
    _save_field_options(opts)


def save_change_reasons(reasons: List[str]) -> None:
    opts = _load_field_options()
    opts['change_reasons'] = sorted(set(reasons))
    _save_field_options(opts)


def load_combobox_options(field: str) -> List[str]:
    opts = _load_field_options()
    return opts.get(f'{field}_options', [])


def save_combobox_options(field: str, values: List[str]) -> None:
    opts = _load_field_options()
    opts[f'{field}_options'] = sorted(set(values))
    _save_field_options(opts)


def add_combobox_option(field: str, value: str) -> None:
    if not value.strip():
        return
    opts = _load_field_options()
    current = opts.get(f'{field}_options', [])
    if value.strip() not in current:
        current.append(value.strip())
        current.sort()
        opts[f'{field}_options'] = current
        _save_field_options(opts)


def save_incident_categories(categories: Dict[str, List[str]]) -> None:
    opts = _load_field_options()
    opts['categories'] = categories
    _save_field_options(opts)


def _migrate_legacy_if_needed() -> None:
    if _STORE_FILE.exists() or not _LEGACY_FILE.exists():
        return
    try:
        legacy = json.loads(_LEGACY_FILE.read_text(encoding='utf-8'))
    except Exception:
        return
    migrated: Dict[str, Dict[str, Any]] = {}
    for key, entry in (legacy or {}).items():
        if not isinstance(entry, dict):
            continue
        migrated[key] = {
            'kind':  'standard_change',
            'label': entry.get('label', key),
            'url':   entry.get('url', ''),
        }
    if migrated:
        _STORE_FILE.write_text(json.dumps(migrated, indent=2), encoding='utf-8')


def load_templates() -> Dict[str, Dict[str, Any]]:
    """Return all templates keyed by key."""
    _migrate_legacy_if_needed()
    if not _STORE_FILE.exists():
        return {}
    try:
        return json.loads(_STORE_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def load_templates_by_kind(kind: str) -> Dict[str, Dict[str, Any]]:
    return {k: v for k, v in load_templates().items() if v.get('kind') == kind}


def load_templates_grouped() -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Return {kind: {key: entry}} for display in grouped lists."""
    out: Dict[str, Dict[str, Dict[str, Any]]] = {k: {} for k in VALID_KINDS}
    for key, entry in load_templates().items():
        kind = entry.get('kind', 'standard_change')
        out.setdefault(kind, {})[key] = entry
    return out


def save_template(key: str, kind: str, label: str, url: str = '', fields: Dict[str, str] | None = None) -> None:
    data = load_templates()
    entry: Dict[str, Any] = {'kind': kind, 'label': label}
    if kind == 'standard_change':
        entry['url'] = url
    else:
        entry['fields'] = fields or {}
    data[key] = entry
    _STORE_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')


def delete_template(key: str) -> None:
    data = load_templates()
    if key in data:
        del data[key]
        _STORE_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')


def build_standard_change_url(template_url: str, row: Dict[str, Any]) -> str:
    """
    Append the given field values to a standard change URL as ServiceNow
    sysparm_query parameters. Kept here so bulk-create + single-create share
    one implementation.
    """
    from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse
    if not template_url:
        return ''
    parsed = urlparse(template_url)
    existing = dict(parse_qsl(parsed.query, keep_blank_values=True))

    prefill = []
    for field in ('short_description', 'assignment_group', 'start_date', 'end_date',
                  'description', 'cmdb_ci', 'std_change_producer_version',
                  'category', 'reason'):
        val = (row.get(field) or '').strip()
        if val:
            prefill.append(f"{field}={val}")
    if prefill:
        prior = existing.get('sysparm_query', '')
        combined = f"{prior}^{'^'.join(prefill)}" if prior else '^'.join(prefill)
        existing['sysparm_query'] = combined

    return urlunparse(parsed._replace(query=urlencode(existing)))

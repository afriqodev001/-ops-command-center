"""
Bulk change parser + validator.

Accepts either pasted text or uploaded CSV content, normalises to a list of
row dicts keyed by our canonical field names, and runs per-row validation.

Required columns (header row required, case-insensitive, order-free):
    type, short_description, assignment_group, start_date, end_date,
    category, reason

Optional:
    cmdb_ci, template_key, risk, description, justification,
    implementation_plan, backout_plan, test_plan

Delimiter is auto-detected (tab or comma). Rows with all-empty cells are skipped.
"""

from __future__ import annotations
from typing import Dict, Any, List
from datetime import datetime
import csv
import io


VALID_TYPES = ('normal', 'emergency', 'standard')

REQUIRED_FIELDS = (
    'type', 'short_description', 'assignment_group',
    'start_date', 'end_date', 'category', 'reason',
)
OPTIONAL_FIELDS = (
    'cmdb_ci', 'template_key', 'risk', 'description',
    'justification', 'implementation_plan', 'backout_plan', 'test_plan',
)
ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS

_DATE_FORMATS = (
    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%d %H:%M',
    '%Y-%m-%dT%H:%M:%S',
    '%Y-%m-%dT%H:%M',
    '%Y-%m-%d',
    '%d/%m/%Y %H:%M',
    '%m/%d/%Y %H:%M',
)

SAMPLE_ROWS = [
    {
        'type': 'normal',
        'short_description': 'Database patching - DBPROD01',
        'assignment_group': 'Database Ops',
        'start_date': '2026-04-25 22:00',
        'end_date': '2026-04-25 23:30',
        'category': 'Database',
        'reason': 'Patching',
        'cmdb_ci': 'DBPROD01',
        'description': 'Apply Oracle security patch Oct 2026',
        'justification': 'Critical security vulnerability',
        'implementation_plan': '1. Backup DB\n2. Apply patch\n3. Verify services',
        'backout_plan': '1. Restore from backup\n2. Restart services',
        'test_plan': '',
    },
    {
        'type': 'emergency',
        'short_description': 'Hotfix: Auth service memory leak',
        'assignment_group': 'Platform Engineering',
        'start_date': '2026-04-20 14:00',
        'end_date': '2026-04-20 15:00',
        'category': 'Application Software',
        'reason': 'Defect Fix',
        'cmdb_ci': 'AUTH-SVC-PROD',
        'description': 'Deploy memory leak fix to auth service',
        'justification': 'Service degrading under load, OOM kills every 4h',
        'implementation_plan': '1. Deploy v2.3.1\n2. Monitor memory',
        'backout_plan': '1. Rollback to v2.3.0',
        'test_plan': '1. Monitor memory usage for 1h\n2. Run load test',
    },
    {
        'type': 'standard',
        'short_description': 'SSL cert renewal - api.example.com',
        'assignment_group': 'Network Ops',
        'start_date': '2026-04-22 10:00',
        'end_date': '2026-04-22 10:30',
        'category': 'Network',
        'reason': 'Configuration',
        'cmdb_ci': '',
        'template_key': 'ssl_renewal',
        'description': 'Renew SSL certificate for api.example.com',
        'justification': '',
        'implementation_plan': '',
        'backout_plan': '',
        'test_plan': '',
    },
]


def generate_sample_csv() -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(ALL_FIELDS))
    writer.writeheader()
    for row in SAMPLE_ROWS:
        writer.writerow({f: row.get(f, '') for f in ALL_FIELDS})
    return output.getvalue()


def _parse_date(raw: str):
    raw = (raw or '').strip()
    if not raw:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _detect_delimiter(sample: str) -> str:
    first_line = sample.splitlines()[0] if sample else ''
    return '\t' if '\t' in first_line else ','


def parse_text(raw_text: str) -> List[Dict[str, str]]:
    raw_text = (raw_text or '').strip()
    if not raw_text:
        return []
    delim = _detect_delimiter(raw_text)
    reader = csv.DictReader(io.StringIO(raw_text), delimiter=delim)
    return _normalise_rows(reader)


def parse_csv_file(file_obj) -> List[Dict[str, str]]:
    data = file_obj.read()
    if isinstance(data, bytes):
        data = data.decode('utf-8-sig', errors='replace')
    return parse_text(data)


def _normalise_rows(reader) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for raw in reader:
        if not raw:
            continue
        normalised = {}
        for k, v in raw.items():
            if k is None:
                continue
            key = k.strip().lower().replace(' ', '_')
            if key in ALL_FIELDS:
                normalised[key] = (v or '').strip()
        if not any(normalised.values()):
            continue
        rows.append(normalised)
    return rows


def validate_rows(
    rows: List[Dict[str, str]],
    known_template_keys: List[str] | None = None,
    valid_categories: List[str] | None = None,
    valid_reasons: List[str] | None = None,
) -> List[Dict[str, Any]]:
    known_template_keys = known_template_keys or []
    results = []

    for idx, row in enumerate(rows):
        errors: List[str] = []
        warnings: List[str] = []

        change_type = (row.get('type') or '').strip().lower()
        if not change_type:
            errors.append('type is required')
        elif change_type not in VALID_TYPES:
            errors.append(f"type must be one of {', '.join(VALID_TYPES)}")

        short_desc = (row.get('short_description') or '').strip()
        if not short_desc:
            errors.append('short_description is required')
        elif len(short_desc) > 160:
            errors.append(f'short_description too long ({len(short_desc)} > 160)')

        if not (row.get('assignment_group') or '').strip():
            errors.append('assignment_group is required')

        start_dt = _parse_date(row.get('start_date', ''))
        if not row.get('start_date'):
            errors.append('start_date is required')
        elif start_dt is None:
            errors.append(f"start_date '{row.get('start_date')}' not recognised")

        end_dt = _parse_date(row.get('end_date', ''))
        if not row.get('end_date'):
            errors.append('end_date is required')
        elif end_dt is None:
            errors.append(f"end_date '{row.get('end_date')}' not recognised")

        if start_dt and end_dt and end_dt <= start_dt:
            errors.append('end_date must be after start_date')

        # Category validation (required for normal/emergency)
        category = (row.get('category') or '').strip()
        if change_type in ('normal', 'emergency'):
            if not category:
                errors.append('category is required')
            elif valid_categories and category not in valid_categories:
                errors.append(f"category '{category}' is not valid. Options: {', '.join(valid_categories)}")

        # Reason validation (required for normal/emergency)
        reason = (row.get('reason') or '').strip()
        if change_type in ('normal', 'emergency'):
            if not reason:
                errors.append('reason is required')
            elif valid_reasons and reason not in valid_reasons:
                errors.append(f"reason '{reason}' is not valid")

        template_key = (row.get('template_key') or '').strip()
        if change_type == 'standard':
            if not template_key:
                warnings.append('standard change has no template_key — a blank ServiceNow form will open')
            elif known_template_keys and template_key not in known_template_keys:
                warnings.append(f"template_key '{template_key}' is not in the saved templates")
        elif template_key:
            warnings.append('template_key is only used for standard changes — will be ignored')

        results.append({
            'row_index': idx,
            'raw': row,
            'type': change_type,
            'short_description': short_desc,
            'assignment_group': (row.get('assignment_group') or '').strip(),
            'start_date': row.get('start_date', ''),
            'end_date': row.get('end_date', ''),
            'start_dt': start_dt,
            'end_dt': end_dt,
            'category': category,
            'reason': reason,
            'cmdb_ci': (row.get('cmdb_ci') or '').strip(),
            'template_key': template_key,
            'risk': (row.get('risk') or '').strip(),
            'description': (row.get('description') or '').strip(),
            'justification': (row.get('justification') or '').strip(),
            'implementation_plan': (row.get('implementation_plan') or '').strip(),
            'backout_plan': (row.get('backout_plan') or '').strip(),
            'test_plan': (row.get('test_plan') or '').strip(),
            'errors': errors,
            'warnings': warnings,
            'is_valid': not errors,
        })
    return results


def summarise(validated: List[Dict[str, Any]]) -> Dict[str, int]:
    return {
        'total': len(validated),
        'valid': sum(1 for r in validated if r['is_valid']),
        'invalid': sum(1 for r in validated if not r['is_valid']),
        'warnings': sum(1 for r in validated if r['warnings']),
        'normal': sum(1 for r in validated if r['type'] == 'normal' and r['is_valid']),
        'emergency': sum(1 for r in validated if r['type'] == 'emergency' and r['is_valid']),
        'standard': sum(1 for r in validated if r['type'] == 'standard' and r['is_valid']),
    }

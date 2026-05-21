"""
Oncall change suppression matrix.

Curated by engineers, keyed by ServiceNow CI / application name.
Tells the oncall workflow:
- whether to notify partners (Yes/No)
- per-application outage impact (with optional extra emails for that app)
- the base notification recipients
- alert suppression need + details (notification / Basemon rule IDs)
- whether to put up a portal banner

Storage: oncall_suppression_matrix.json (gitignored, next to the app dir).
Upload accepts either CSV or JSON; both convert to the same canonical shape.
"""
from __future__ import annotations

import csv
import io
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


_STORE_FILE = Path(__file__).parent.parent / 'oncall_suppression_matrix.json'


# Canonical key set on a row.  CSV headers are mapped to these via HEADER_ALIASES
# (case-insensitive, with space→underscore as the first-pass normalisation).
#
# Important: notify_partners and suppression are *free text*, not booleans —
# they contain the reasoning + conditional rules ("PMT is Active/Active and
# we should not send communication, Yes for BCP event"). The oncall engineer
# (and the AI) reads them and judges. Don't coerce to bool.
CANONICAL_COLUMNS = (
    'application',
    'ci',
    'notes',                   # free text — extra notes / description for the row
    'outage_impact',           # list of {"app": str, "description": str, "additional_emails": [str]}
    'outage_guidelines',       # free text — things to watch out for; NOT included in emails
    'notify_partners',         # free text (guidance, may include conditions)
    'notification_emails',     # list of str
    'suppression',             # free text (guidance)
    'suppression_details',     # free text — what gets suppressed, scope, conditions
    'notification_id',         # str — downstream notification reference
    'basemon_rule_id',         # str — Basemon monitoring rule reference
    'banner',                  # bool
    # JSON-only optional sibling — freeform banner notes (actual banner text is set on Post Banner)
    'banner_message',
)

# Headers we accept on CSV input. Each entry maps an alias (post space→underscore
# lowercase normalisation) to the canonical key.
HEADER_ALIASES: Dict[str, str] = {
    # Application
    'application': 'application',
    'app': 'application',
    'app_name': 'application',
    # CI
    'ci': 'ci',
    'ci_name': 'ci',
    'cmdb_ci': 'ci',
    # Notes / description
    'notes': 'notes',
    'note': 'notes',
    'description': 'notes',
    'extra_notes': 'notes',
    # Outage impact
    'outage_impact': 'outage_impact',
    'impact': 'outage_impact',
    'impact_description': 'outage_impact',
    # Notify partners (Yes/No)
    'notify_partners': 'notify_partners',
    'notification_to_partners_for_outage': 'notify_partners',
    'notification_to_partners': 'notify_partners',
    'notify_for_outage': 'notify_partners',
    'outage_likely': 'notify_partners',
    # Notification emails
    'notification_emails': 'notification_emails',
    'emails': 'notification_emails',
    'recipient_emails': 'notification_emails',
    # Suppression Yes/No
    'suppression': 'suppression',
    'suppression_required': 'suppression',
    'suppress': 'suppression',
    # Suppression details (free text) — replaces the old 'suppression records' list
    'suppression_details': 'suppression_details',
    'suppression_records': 'suppression_details',
    'suppression_ids': 'suppression_details',
    'alert_suppression_ids': 'suppression_details',
    'alert_ids': 'suppression_details',
    # Notification + Basemon rule IDs
    'notification_id': 'notification_id',
    'notif_id': 'notification_id',
    'basemon_rule_id': 'basemon_rule_id',
    'basemon_id': 'basemon_rule_id',
    'basemon': 'basemon_rule_id',
    # Outage guidelines — things to watch out for (not emailed)
    'outage_guidelines': 'outage_guidelines',
    'guidelines': 'outage_guidelines',
    'things_to_watch': 'outage_guidelines',
    # Banner
    'banner': 'banner',
    'banner_required': 'banner',
    # JSON-only
    'banner_message': 'banner_message',
}

ARRAY_FIELDS = ('notification_emails',)
BOOL_FIELDS = ('banner',)
TEXT_GUIDANCE_FIELDS = ('notify_partners', 'suppression')

# ─── IO ────────────────────────────────────────────────────

def _empty_store() -> Dict[str, Any]:
    return {'version': 2, 'updated_at': None, 'rows': []}


def _load_store() -> Dict[str, Any]:
    if not _STORE_FILE.exists():
        return _empty_store()
    try:
        data = json.loads(_STORE_FILE.read_text(encoding='utf-8'))
    except Exception:
        return _empty_store()
    if not isinstance(data, dict):
        return _empty_store()
    if 'rows' not in data or not isinstance(data['rows'], list):
        return _empty_store()
    return data


def _save_store(rows: List[Dict[str, Any]]) -> None:
    payload = {
        'version': 2,
        'updated_at': time.time(),
        'rows': rows,
    }
    _STORE_FILE.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def load_matrix() -> List[Dict[str, Any]]:
    return list(_load_store().get('rows') or [])


def matrix_meta() -> Dict[str, Any]:
    """Lightweight info for UI: row count, last-updated timestamp."""
    store = _load_store()
    return {
        'row_count': len(store.get('rows') or []),
        'updated_at': store.get('updated_at'),
        'has_file': _STORE_FILE.exists(),
    }


def save_matrix(rows: List[Dict[str, Any]]) -> None:
    _save_store(rows)


def clear_matrix() -> None:
    if _STORE_FILE.exists():
        _STORE_FILE.unlink()


# ─── Single-row CRUD (UI form-driven editor) ──────────────

def get_row(ci: str) -> Optional[Dict[str, Any]]:
    """Return the row whose `ci` matches (case-insensitive), or None."""
    if not ci:
        return None
    needle = str(ci).strip().lower()
    for row in load_matrix():
        if (row.get('ci') or '').strip().lower() == needle:
            return row
    return None


def upsert_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Insert (or update by `ci`) a single row. Returns the canonical row.

    Lookup key is `ci` (case-insensitive). If the canonical key changes
    on edit, pass the original CI separately via row['_original_ci'].
    """
    canonical = _normalise_row(row, source='form')
    new_ci = (canonical.get('ci') or '').strip().lower()
    if not new_ci:
        raise ValueError('CI is required.')

    original_ci = (row.get('_original_ci') or '').strip().lower() or new_ci

    rows = load_matrix()
    out: List[Dict[str, Any]] = []
    replaced = False
    for existing in rows:
        existing_ci = (existing.get('ci') or '').strip().lower()
        if existing_ci == original_ci or (existing_ci == new_ci and not replaced):
            if not replaced:
                out.append(canonical)
                replaced = True
            # drop the old row(s) keyed on either original_ci or new_ci
        else:
            out.append(existing)
    if not replaced:
        out.append(canonical)

    save_matrix(out)
    return canonical


def delete_row(ci: str) -> bool:
    """Delete row by CI (case-insensitive). Returns True if a row was removed."""
    if not ci:
        return False
    needle = str(ci).strip().lower()
    rows = load_matrix()
    kept = [r for r in rows if (r.get('ci') or '').strip().lower() != needle]
    if len(kept) == len(rows):
        return False
    save_matrix(kept)
    return True


# ─── Upload parsing ───────────────────────────────────────

def parse_upload(file_obj, filename: str = '') -> List[Dict[str, Any]]:
    """
    Accept either CSV or JSON upload; return canonical rows.

    Detection: `.json` extension OR content starts with `{` / `[` → JSON path.
    Otherwise → CSV path (delimiter auto-detected: tab vs comma).
    """
    raw = file_obj.read()
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8-sig', errors='replace')

    name_lower = (filename or '').lower()
    stripped = raw.lstrip()

    is_json = (
        name_lower.endswith('.json')
        or stripped.startswith('{')
        or stripped.startswith('[')
    )

    if is_json:
        return _parse_json(raw)
    return _parse_csv(raw)


def _parse_json(raw: str) -> List[Dict[str, Any]]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f'Invalid JSON: {e}')

    rows = None
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        if isinstance(data.get('rows'), list):
            rows = data['rows']
        elif isinstance(data.get('matrix'), list):
            rows = data['matrix']

    if rows is None:
        raise ValueError(
            "JSON shape not recognised — expected a list of row dicts, or "
            "an object with a 'rows' (or 'matrix') key holding the list."
        )

    return [_normalise_row(r, source='json') for r in rows if isinstance(r, dict)]


def _detect_delimiter(sample: str) -> str:
    first_line = sample.splitlines()[0] if sample else ''
    return '\t' if '\t' in first_line else ','


def _parse_csv(raw: str) -> List[Dict[str, Any]]:
    raw = (raw or '').strip()
    if not raw:
        return []
    delim = _detect_delimiter(raw)
    reader = csv.DictReader(io.StringIO(raw), delimiter=delim)
    out: List[Dict[str, Any]] = []
    for raw_row in reader:
        if not raw_row:
            continue
        row: Dict[str, Any] = {}
        extras: Dict[str, Any] = {}
        for header, v in raw_row.items():
            if header is None:
                continue
            slug = header.strip().lower().replace(' ', '_')
            canonical = HEADER_ALIASES.get(slug)
            if canonical:
                row[canonical] = (v or '').strip() if isinstance(v, str) else v
            else:
                extras[header.strip()] = (v or '').strip() if isinstance(v, str) else v
        if not any(v for v in row.values() if v not in (None, '', [])):
            continue
        if extras:
            row['_extra'] = extras
        out.append(_normalise_row(row, source='csv'))
    return out


def _to_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in ('true', 'yes', 'y', '1', 't')


def _to_array(v: Any) -> List[str]:
    """Accept array, semicolon-separated string, or comma-fallback string."""
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if v is None:
        return []
    s = str(v).strip()
    if not s:
        return []
    sep = ';' if ';' in s else ','
    return [p.strip() for p in s.split(sep) if p.strip()]


def _normalise_outage_impact(v: Any) -> List[Dict[str, Any]]:
    """
    Canonical shape: [{app, description, additional_emails: [str]}].

    JSON path may already give the array shape — pass through with field
    coercions. CSV path always supplies a single text cell — wrap as one
    entry with no app/additional_emails.
    """
    if v is None:
        return []
    if isinstance(v, list):
        out = []
        for item in v:
            if isinstance(item, dict):
                out.append({
                    'app': str(item.get('app') or '').strip(),
                    'description': str(item.get('description') or '').strip(),
                    'additional_emails': _to_array(item.get('additional_emails')),
                })
            elif isinstance(item, str) and item.strip():
                out.append({
                    'app': '',
                    'description': item.strip(),
                    'additional_emails': [],
                })
        return [e for e in out if e.get('description') or e.get('app')]
    if isinstance(v, dict):
        return _normalise_outage_impact([v])
    s = str(v).strip()
    if not s:
        return []
    return [{'app': '', 'description': s, 'additional_emails': []}]


def _suppression_details_text(row: Dict[str, Any]) -> str:
    """`suppression_details` is free text. Older matrices stored a
    `suppression_records` list — fold that into the text so curated data
    survives the first load after the schema change."""
    v = row.get('suppression_details')
    if v in (None, ''):
        v = row.get('suppression_records')
    if isinstance(v, list):
        return '; '.join(str(x).strip() for x in v if str(x).strip())
    return str(v or '').strip()


def _normalise_row(row: Dict[str, Any], *, source: str = 'json') -> Dict[str, Any]:
    """Coerce a row dict (from either CSV or JSON) into the canonical shape."""
    out: Dict[str, Any] = {}

    # Direct field mappings
    out['application'] = str(row.get('application') or '').strip()
    out['ci'] = str(row.get('ci') or '').strip()
    out['notes'] = str(row.get('notes') or '').strip()
    out['outage_impact'] = _normalise_outage_impact(row.get('outage_impact'))
    out['outage_guidelines'] = str(row.get('outage_guidelines') or '').strip()
    # free-text guidance fields — preserve whatever the engineer wrote
    out['notify_partners'] = str(row.get('notify_partners') or '').strip()
    out['notification_emails'] = _to_array(row.get('notification_emails'))
    out['suppression'] = str(row.get('suppression') or '').strip()
    out['suppression_details'] = _suppression_details_text(row)
    out['notification_id'] = str(row.get('notification_id') or '').strip()
    out['basemon_rule_id'] = str(row.get('basemon_rule_id') or '').strip()
    out['banner'] = _to_bool(row.get('banner'))
    out['banner_message'] = str(row.get('banner_message') or '').strip()

    extras = row.get('_extra')
    if isinstance(extras, dict) and extras:
        out['_extra'] = extras

    return out


# ─── Lookup ────────────────────────────────────────────────

def lookup(change: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Find the matrix row that best matches a change record.

    Match priority:
      1. exact (case-insensitive) match on ServiceNow `cmdb_ci` value vs row.ci
      2. exact match on display_value vs row.ci
      3. case-insensitive contains on either CI value/display vs row.ci or row.application
      4. None
    """
    rows = load_matrix()
    if not rows or not change:
        return None

    cmdb = change.get('cmdb_ci') or change.get('cmdb_ci.value') or ''
    if isinstance(cmdb, dict):
        cmdb_value = (cmdb.get('value') or '').strip()
        cmdb_display = (cmdb.get('display_value') or '').strip()
    else:
        cmdb_value = str(cmdb).strip()
        cmdb_display = str(change.get('cmdb_ci.display_value') or cmdb_value).strip()

    lc_value = cmdb_value.lower()
    lc_display = cmdb_display.lower()

    for row in rows:
        ci = (row.get('ci') or '').strip().lower()
        if ci and (ci == lc_value or ci == lc_display):
            return row

    needles = [n for n in (lc_value, lc_display) if n]
    for row in rows:
        ci = (row.get('ci') or '').strip().lower()
        app = (row.get('application') or '').strip().lower()
        for needle in needles:
            if (ci and ci in needle) or (app and app in needle):
                return row
            if needle and (needle in ci or needle in app):
                return row

    return None


def all_recipients_for(row: Dict[str, Any]) -> List[str]:
    """
    Compute the union of base notification_emails + every impact entry's
    additional_emails. Deduplicates while preserving first-seen order.
    """
    seen = []
    seen_set = set()
    for e in (row.get('notification_emails') or []):
        e = (e or '').strip()
        if e and e.lower() not in seen_set:
            seen.append(e); seen_set.add(e.lower())
    for entry in (row.get('outage_impact') or []):
        for e in (entry.get('additional_emails') or []):
            e = (e or '').strip()
            if e and e.lower() not in seen_set:
                seen.append(e); seen_set.add(e.lower())
    return seen


def impact_text_for(row: Dict[str, Any]) -> str:
    """Render the matrix row's outage_impact array as a human-readable string."""
    entries = row.get('outage_impact') or []
    if not entries:
        return ''
    out_lines = []
    for e in entries:
        app = (e.get('app') or '').strip()
        desc = (e.get('description') or '').strip()
        if app and desc:
            out_lines.append(f'{app}: {desc}')
        elif desc:
            out_lines.append(desc)
        elif app:
            out_lines.append(f'{app}: (impact noted)')
    return '\n'.join(out_lines)


def impact_app_names_for(row: Dict[str, Any]) -> str:
    """Comma-joined list of distinct downstream app names from the row's
    outage_impact entries. Skips generic entries that have no app name."""
    seen: List[str] = []
    for e in (row.get('outage_impact') or []):
        app = (e.get('app') or '').strip()
        if app and app not in seen:
            seen.append(app)
    return ', '.join(seen)


# ─── Export ────────────────────────────────────────────────

# CSV column order = the user's declared header set.
CSV_HEADERS = (
    ('Application',                           'application'),
    ('CI',                                    'ci'),
    ('Notes',                                 'notes'),
    ('Outage Impact',                         'outage_impact'),
    ('Outage Guidelines',                     'outage_guidelines'),
    ('Notification to Partners for Outage',  'notify_partners'),
    ('Notification Emails',                   'notification_emails'),
    ('Suppression',                           'suppression'),
    ('Suppression Details',                   'suppression_details'),
    ('Notification ID',                       'notification_id'),
    ('Basemon Rule ID',                       'basemon_rule_id'),
    ('Banner',                                'banner'),
)


def export_json() -> str:
    return json.dumps(_load_store(), indent=2)


def export_csv() -> str:
    """Flatten arrays back to '; '-joined strings; bools to Yes/No.

    For outage_impact, prefer 'description' lines joined with newlines —
    if a row has per-app entries with additional_emails, those are dropped
    in CSV (round-trip via JSON to preserve them).
    """
    rows = load_matrix()
    output = io.StringIO()
    headers = [h for h, _ in CSV_HEADERS]
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    for row in rows:
        out = {}
        for header, key in CSV_HEADERS:
            v = row.get(key)
            if key == 'outage_impact':
                out[header] = impact_text_for(row)
            elif key in ARRAY_FIELDS:
                out[header] = '; '.join(v) if isinstance(v, list) else (v or '')
            elif key in BOOL_FIELDS:
                out[header] = 'Yes' if bool(v) else 'No'
            else:
                # text fields — preserve verbatim
                out[header] = '' if v is None else str(v)
        writer.writerow(out)
    return output.getvalue()


def canonical_columns() -> List[str]:
    """Public-facing canonical column names (excludes JSON-only banner_message)."""
    return [k for k, _ in CSV_HEADERS]

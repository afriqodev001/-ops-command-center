"""
Oncall change suppression matrix.

Curated by engineers, keyed by ServiceNow CI / application name.
Tells the oncall workflow:
- whether a change on this CI is likely to cause an outage
- the impact text to put in notification emails
- recipient emails for downstream comms
- alert suppression IDs to surface for the engineer
- whether (and what) to put on the global banner

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


# Canonical column / key set. CSV headers normalise to these
# (case-insensitive, space->underscore). Same names work in JSON.
CANONICAL_COLUMNS = (
    'ci_name',
    'application',
    'outage_likely',
    'impact_description',
    'notification_emails',
    'alert_suppression_ids',
    'banner_required',
    'banner_message',
    'owner_team',
)

# Fields that are arrays in JSON / semicolon lists in CSV
ARRAY_FIELDS = ('notification_emails', 'alert_suppression_ids')

# Fields that are booleans
BOOL_FIELDS = ('banner_required',)

# Fields that are kept as-is (strings); outage_likely is "yes"/"no"/"maybe" string
STRING_FIELDS = tuple(
    c for c in CANONICAL_COLUMNS if c not in ARRAY_FIELDS and c not in BOOL_FIELDS
)


# ─── IO ────────────────────────────────────────────────────

def _empty_store() -> Dict[str, Any]:
    return {'version': 1, 'updated_at': None, 'rows': []}


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
        'version': 1,
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
    """Replace the whole matrix wholesale. Caller has already validated."""
    _save_store(rows)


def clear_matrix() -> None:
    if _STORE_FILE.exists():
        _STORE_FILE.unlink()


# ─── Upload parsing ───────────────────────────────────────

def parse_upload(file_obj, filename: str = '') -> List[Dict[str, Any]]:
    """
    Accept either CSV or JSON upload; return list of canonical rows.

    Detection:
    - .json extension OR content starts with `{` / `[`  -> JSON path
    - otherwise (.csv, .tsv, etc)                      -> CSV path

    Raises ValueError on unparseable input or schema mismatch.
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

    return [_normalise_row(r) for r in rows if isinstance(r, dict)]


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
        # normalise headers — case-insensitive, space→underscore
        row: Dict[str, Any] = {}
        for k, v in raw_row.items():
            if k is None:
                continue
            key = k.strip().lower().replace(' ', '_')
            row[key] = (v or '').strip() if isinstance(v, str) else v
        if not any(v for v in row.values() if v not in (None, '', [])):
            continue
        out.append(_normalise_row(row, from_csv=True))
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


def _normalise_row(row: Dict[str, Any], from_csv: bool = False) -> Dict[str, Any]:
    """Coerce a raw row dict into the canonical shape."""
    out: Dict[str, Any] = {}
    extra: Dict[str, Any] = {}

    for k, v in (row or {}).items():
        if k in ARRAY_FIELDS:
            out[k] = _to_array(v)
        elif k in BOOL_FIELDS:
            out[k] = _to_bool(v)
        elif k in STRING_FIELDS:
            out[k] = '' if v is None else str(v).strip()
        elif k == 'extra' and isinstance(v, dict):
            # JSON path may pre-pack extras
            extra.update(v)
        else:
            extra[k] = v

    # ensure all canonical keys exist with sensible defaults
    for col in CANONICAL_COLUMNS:
        if col in out:
            continue
        if col in ARRAY_FIELDS:
            out[col] = []
        elif col in BOOL_FIELDS:
            out[col] = False
        else:
            out[col] = ''

    if extra:
        out['extra'] = extra

    return out


# ─── Lookup ────────────────────────────────────────────────

def lookup(change: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Find the matrix row that best matches a change record.

    Match priority:
      1. exact match on cmdb_ci value vs row.ci_name (case-insensitive)
      2. case-insensitive contains on cmdb_ci.display_value vs ci_name / application
      3. None
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

    # 1. exact CI match
    if lc_value or lc_display:
        for row in rows:
            ci = (row.get('ci_name') or '').strip().lower()
            if ci and (ci == lc_value or ci == lc_display):
                return row

    # 2. contains match
    needles = [n for n in (lc_value, lc_display) if n]
    for row in rows:
        ci = (row.get('ci_name') or '').strip().lower()
        app = (row.get('application') or '').strip().lower()
        for needle in needles:
            if (ci and ci in needle) or (app and app in needle):
                return row
            if needle and (needle in ci or needle in app):
                return row

    return None


# ─── Export ────────────────────────────────────────────────

def export_json() -> str:
    """Return canonical JSON store, pretty-printed."""
    store = _load_store()
    return json.dumps(store, indent=2)


def export_csv() -> str:
    """Flatten arrays back to '; '-joined strings; bools to Yes/No."""
    rows = load_matrix()
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(CANONICAL_COLUMNS))
    writer.writeheader()
    for row in rows:
        flat = {}
        for col in CANONICAL_COLUMNS:
            v = row.get(col)
            if col in ARRAY_FIELDS:
                flat[col] = '; '.join(v) if isinstance(v, list) else (v or '')
            elif col in BOOL_FIELDS:
                flat[col] = 'Yes' if bool(v) else 'No'
            else:
                flat[col] = '' if v is None else str(v)
        writer.writerow(flat)
    return output.getvalue()


def canonical_columns() -> List[str]:
    return list(CANONICAL_COLUMNS)

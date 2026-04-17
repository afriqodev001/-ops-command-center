from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404

# ─────────────────────────────────────────────
# Demo data (replace with real API calls later)
# ─────────────────────────────────────────────

DEMO_INCIDENTS = [
    {
        "sys_id": "inc001",
        "number": "INC0045231",
        "short_description": "DB connection pool exhausted on prod-db-01",
        "priority": "1", "priority_label": "P1",
        "state": "In Progress", "state_code": "in_progress",
        "assignment_group": "Database Ops", "assigned_to": "J. Smith",
        "opened": "2026-04-15 14:32", "age": "1h 23m", "sla_warning": True,
        "work_notes": [
            {"by": "J. Smith", "at": "14:45", "text": "Restarting connection pool service on prod-db-01. Monitoring."},
            {"by": "Monitoring Bot", "at": "14:32", "text": "Alert fired: connection pool exhausted. Pool size: 0/100."},
        ],
        "tasks": [],
        "attachments": [
            {"name": "error_logs_1432.txt", "size": "24 KB", "by": "monitoring-bot", "at": "14:32"},
        ],
    },
    {
        "sys_id": "inc002",
        "number": "INC0045228",
        "short_description": "Slow queries on reporting DB — response times >30s",
        "priority": "2", "priority_label": "P2",
        "state": "In Progress", "state_code": "in_progress",
        "assignment_group": "Database Ops", "assigned_to": "",
        "opened": "2026-04-15 10:05", "age": "4h 50m", "sla_warning": True,
        "work_notes": [
            {"by": "B. Doe", "at": "11:00", "text": "Identified missing index on reporting_events table. Rebuild in progress."},
        ],
        "tasks": [
            {"number": "ITASK0011", "description": "Rebuild index on reporting_events", "state": "In Progress", "assigned_to": "B. Doe"},
            {"number": "ITASK0012", "description": "Notify affected report consumers", "state": "Open", "assigned_to": ""},
        ],
        "attachments": [],
    },
    {
        "sys_id": "inc003",
        "number": "INC0045225",
        "short_description": "Auth service returning intermittent 401s for SSO users",
        "priority": "2", "priority_label": "P2",
        "state": "In Progress", "state_code": "in_progress",
        "assignment_group": "Platform", "assigned_to": "B. Doe",
        "opened": "2026-04-15 12:20", "age": "2h 35m", "sla_warning": False,
        "work_notes": [],
        "tasks": [],
        "attachments": [],
    },
    {
        "sys_id": "inc004",
        "number": "INC0045220",
        "short_description": "High CPU on worker-cluster-03 — sustained 92%",
        "priority": "3", "priority_label": "P3",
        "state": "In Progress", "state_code": "in_progress",
        "assignment_group": "Infrastructure", "assigned_to": "A. Patel",
        "opened": "2026-04-15 08:45", "age": "6h 10m", "sla_warning": False,
        "work_notes": [],
        "tasks": [],
        "attachments": [],
    },
    {
        "sys_id": "inc005",
        "number": "INC0045218",
        "short_description": "SSL certificate expiring in 5 days — api.internal",
        "priority": "3", "priority_label": "P3",
        "state": "Open", "state_code": "open",
        "assignment_group": "Security", "assigned_to": "",
        "opened": "2026-04-14 09:00", "age": "1d 5h", "sla_warning": False,
        "work_notes": [],
        "tasks": [],
        "attachments": [],
    },
    {
        "sys_id": "inc006",
        "number": "INC0045210",
        "short_description": "Disk usage at 85% on log-server-01",
        "priority": "3", "priority_label": "P3",
        "state": "Resolved", "state_code": "resolved",
        "assignment_group": "Infrastructure", "assigned_to": "J. Smith",
        "opened": "2026-04-13 06:00", "age": "2d 8h", "sla_warning": False,
        "work_notes": [
            {"by": "J. Smith", "at": "2026-04-13 08:30", "text": "Archived 60GB of logs older than 90 days. Disk now at 42%."},
        ],
        "tasks": [],
        "attachments": [],
    },
]

DEMO_CHANGES = [
    {
        "sys_id": "chg001",
        "number": "CHG0034567",
        "short_description": "Monthly OS patching — prod-app-cluster",
        "type": "Normal", "state": "Implement", "state_code": "implement",
        "assignment_group": "Platform", "assigned_to": "J. Smith",
        "scheduled": "2026-04-15 22:00 UTC", "risk": "Moderate",
        "ctasks": [
            {"number": "CTASK0001234", "description": "Pre-change health check", "state": "Closed Complete", "assigned_to": "J. Smith"},
            {"number": "CTASK0001235", "description": "Apply patches to node-01", "state": "Closed Complete", "assigned_to": "J. Smith"},
            {"number": "CTASK0001236", "description": "Apply patches to node-02", "state": "In Progress", "assigned_to": "B. Doe"},
            {"number": "CTASK0001237", "description": "Post-patch validation", "state": "Open", "assigned_to": ""},
            {"number": "CTASK0001238", "description": "Stakeholder sign-off", "state": "Open", "assigned_to": ""},
        ],
        "attachments": [
            {"name": "runbook_os_patching_v3.pdf", "size": "1.2 MB", "by": "j.smith", "at": "2026-04-15 10:00"},
            {"name": "pre_change_health_check.png", "size": "340 KB", "by": "j.smith", "at": "2026-04-15 22:05"},
        ],
        "work_notes": [
            {"by": "J. Smith", "at": "22:05", "text": "Pre-change health check completed. All services healthy. Proceeding."},
            {"by": "J. Smith", "at": "22:01", "text": "Change window open. Starting pre-checks."},
        ],
    },
    {
        "sys_id": "chg002",
        "number": "CHG0034560",
        "short_description": "Firewall rule update — DMZ to internal segment",
        "type": "Normal", "state": "Scheduled", "state_code": "scheduled",
        "assignment_group": "Network Ops", "assigned_to": "A. Patel",
        "scheduled": "2026-04-16 02:00 UTC", "risk": "Low",
        "ctasks": [
            {"number": "CTASK0001240", "description": "Review current ruleset", "state": "Closed Complete", "assigned_to": "A. Patel"},
            {"number": "CTASK0001241", "description": "Apply firewall rules", "state": "Open", "assigned_to": "A. Patel"},
            {"number": "CTASK0001242", "description": "Validate connectivity", "state": "Open", "assigned_to": "A. Patel"},
        ],
        "attachments": [
            {"name": "firewall_rule_change_request.pdf", "size": "280 KB", "by": "a.patel", "at": "2026-04-15 09:00"},
        ],
        "work_notes": [],
    },
    {
        "sys_id": "chg003",
        "number": "CHG0034558",
        "short_description": "Database index rebuild — reporting DB",
        "type": "Normal", "state": "Scheduled", "state_code": "scheduled",
        "assignment_group": "Database Ops", "assigned_to": "B. Doe",
        "scheduled": "2026-04-16 04:00 UTC", "risk": "Low",
        "ctasks": [
            {"number": "CTASK0001250", "description": "Backup reporting DB", "state": "Open", "assigned_to": "B. Doe"},
            {"number": "CTASK0001251", "description": "Rebuild indexes", "state": "Open", "assigned_to": "B. Doe"},
            {"number": "CTASK0001252", "description": "Validate query performance", "state": "Open", "assigned_to": "B. Doe"},
        ],
        "attachments": [],
        "work_notes": [],
    },
    {
        "sys_id": "chg004",
        "number": "CHG0034550",
        "short_description": "Deploy auth-service v2.4.1 — SSO token refresh fix",
        "type": "Normal", "state": "Review", "state_code": "review",
        "assignment_group": "Platform", "assigned_to": "B. Doe",
        "scheduled": "2026-04-17 20:00 UTC", "risk": "Moderate",
        "ctasks": [
            {"number": "CTASK0001260", "description": "Deploy to staging", "state": "Closed Complete", "assigned_to": "B. Doe"},
            {"number": "CTASK0001261", "description": "Smoke test staging", "state": "Closed Complete", "assigned_to": "B. Doe"},
            {"number": "CTASK0001262", "description": "Deploy to production", "state": "Open", "assigned_to": "B. Doe"},
            {"number": "CTASK0001263", "description": "Production smoke test", "state": "Open", "assigned_to": "B. Doe"},
        ],
        "attachments": [
            {"name": "staging_test_results.pdf", "size": "512 KB", "by": "b.doe", "at": "2026-04-15 11:00"},
        ],
        "work_notes": [
            {"by": "B. Doe", "at": "11:05", "text": "Staging deploy successful. All smoke tests passing. Ready for CAB approval."},
        ],
    },
    {
        "sys_id": "chg005",
        "number": "CHG0034545",
        "short_description": "SSL certificate renewal — api.internal",
        "type": "Standard", "state": "Approved", "state_code": "approved",
        "assignment_group": "Security", "assigned_to": "A. Patel",
        "scheduled": "2026-04-18 10:00 UTC", "risk": "Low",
        "ctasks": [
            {"number": "CTASK0001270", "description": "Generate new certificate", "state": "Open", "assigned_to": "A. Patel"},
            {"number": "CTASK0001271", "description": "Deploy and verify", "state": "Open", "assigned_to": "A. Patel"},
        ],
        "attachments": [],
        "work_notes": [],
    },
]

DEMO_STATS = {
    "open_p1": 1,
    "open_p2": 2,
    "open_incidents": 5,
    "pending_changes": 2,
    "implementing": 1,
    "awaiting_review": 1,
}

# ─── Enrich demo records with fields used by the Search page ─────────
# These would come from ServiceNow in production; baked in here so the
# demo UI can filter by CI and requester without extra infrastructure.
_INCIDENT_EXTRAS = {
    'inc001': {'cmdb_ci': 'prod-db-01',        'opened_by': 'Monitoring Bot'},
    'inc002': {'cmdb_ci': 'reporting-db',      'opened_by': 'B. Doe'},
    'inc003': {'cmdb_ci': 'auth-service',      'opened_by': 'L. Chen'},
    'inc004': {'cmdb_ci': 'worker-cluster-03', 'opened_by': 'A. Patel'},
    'inc005': {'cmdb_ci': 'api.internal',      'opened_by': 'Security Scanner'},
    'inc006': {'cmdb_ci': 'log-server-01',     'opened_by': 'J. Smith'},
}
for _i in DEMO_INCIDENTS:
    _ex = _INCIDENT_EXTRAS.get(_i['sys_id'], {})
    _i.setdefault('cmdb_ci',   _ex.get('cmdb_ci', ''))
    _i.setdefault('opened_by', _ex.get('opened_by', ''))

_CHANGE_EXTRAS = {
    'chg001': {'cmdb_ci': 'prod-app-cluster', 'opened_by': 'J. Smith'},
    'chg002': {'cmdb_ci': 'dmz-firewall',     'opened_by': 'A. Patel'},
    'chg003': {'cmdb_ci': 'reporting-db',     'opened_by': 'B. Doe'},
    'chg004': {'cmdb_ci': 'auth-service',     'opened_by': 'B. Doe'},
    'chg005': {'cmdb_ci': 'api.internal',     'opened_by': 'A. Patel'},
}
for _c in DEMO_CHANGES:
    _ex = _CHANGE_EXTRAS.get(_c['sys_id'], {})
    _c.setdefault('cmdb_ci',   _ex.get('cmdb_ci', ''))
    _c.setdefault('opened_by', _ex.get('opened_by', ''))


# ─── Parse demo-data date strings into datetime objects ──────────
# Used by the time-range filter on list + search pages. In production the
# equivalent ServiceNow query is `opened_at>=javascript:gs.daysAgo(N)` etc.
def _parse_demo_dt(raw: str):
    if not raw:
        return None
    s = raw.replace(' UTC', '').strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


for _i in DEMO_INCIDENTS:
    _i['_opened_dt'] = _parse_demo_dt(_i.get('opened', ''))

for _c in DEMO_CHANGES:
    _c['_scheduled_dt'] = _parse_demo_dt(_c.get('scheduled', ''))


# ─── Time-range filter shared by incidents / changes / search ───
TIME_RANGES = [
    ('7',   'Last 7 days'),
    ('30',  'Last 30 days'),
    ('90',  'Last 90 days'),
    ('365', 'Last year'),
    ('all', 'All time'),
]
DEFAULT_DAYS = '30'
DEFAULT_LIST_LIMIT = 200


def _filter_by_days(records, dt_field: str, days_str: str):
    """
    Keep records whose `dt_field` is within the last N days (or whose
    `dt_field` is None — we don't drop unparseable rows silently).
    Returns a new list.
    """
    if not days_str or days_str == 'all':
        return list(records)
    try:
        days = int(days_str)
    except (TypeError, ValueError):
        return list(records)
    cutoff = datetime.now() - timedelta(days=days)
    return [r for r in records if not r.get(dt_field) or r[dt_field] >= cutoff]


def _get_incident(number):
    return next((i for i in DEMO_INCIDENTS if i["number"] == number), None)


def _get_change(number):
    return next((c for c in DEMO_CHANGES if c["number"] == number), None)


# ─── Data mode (demo vs live) ────────────────────────────────────
# Stored per-user in the Django session. Defaults to 'demo' so a fresh
# visitor always sees seeded data rather than empty pages.
DATA_MODES = ('demo', 'live')


def _data_mode(request) -> str:
    if hasattr(request, 'session'):
        m = request.session.get('data_mode')
        if m in DATA_MODES:
            return m
    # No session-level override → fall back to saved user preference
    try:
        from .services.user_preferences import load_preferences
        m = load_preferences().get('default_data_mode', 'demo')
    except Exception:
        m = 'demo'
    return 'live' if m == 'live' else 'demo'


def _is_live(request) -> bool:
    return _data_mode(request) == 'live'


def _incidents_source(request):
    """Return the incidents list for the current data mode.
    Live mode returns [] today — the live ServiceNow read path isn't wired yet
    on list pages. The UI surfaces this via a global banner in base.html."""
    return [] if _is_live(request) else DEMO_INCIDENTS


def _changes_source(request):
    return [] if _is_live(request) else DEMO_CHANGES


def _sla_is_at_risk(sla_due_display: str) -> bool:
    """Cheap heuristic — mark SLA at-risk if the display value suggests breach.

    ServiceNow's sla_due display varies by instance (duration string, timestamp,
    'Breached'). We only light the warning when the display value strongly
    signals a problem; anything ambiguous stays unhighlighted.
    """
    if not sla_due_display:
        return False
    s = str(sla_due_display).lower().strip()
    return 'breach' in s or s.startswith('-') or s == '0' or s.startswith('0 ')


def _unwrap_record(response):
    """Drill past common wrappers from ServiceNow/task responses to the flat record dict."""
    if not response or not isinstance(response, dict):
        return None
    if response.get('error'):
        return None
    # Looks like a flat record already
    if 'number' in response or 'sys_id' in response:
        return response
    # Common wrappers returned by our task helpers
    for key in ('record', 'result'):
        inner = response.get(key)
        if isinstance(inner, dict):
            return _unwrap_record(inner)
        if isinstance(inner, list) and inner:
            return _unwrap_record(inner[0])
    return None


def _adapt_live_incident(rec):
    """Shape a live ServiceNow incident record to the dict our templates expect."""
    if not rec:
        return None
    state_display = str(rec.get('state', '') or '')
    priority     = str(rec.get('priority', '') or '')
    sla_due      = str(rec.get('sla_due', '') or '')
    return {
        'sys_id':            rec.get('sys_id', ''),
        'number':            rec.get('number', ''),
        'short_description': rec.get('short_description', ''),
        'priority':          priority,
        'priority_label':    f'P{priority}' if priority else '',
        'state':             state_display,
        'state_code':        state_display.lower().replace(' ', '_'),
        'assignment_group':  rec.get('assignment_group', ''),
        'assigned_to':       rec.get('assigned_to', ''),
        'opened':            rec.get('opened_at', '') or rec.get('sys_created_on', ''),
        'age':               rec.get('sys_updated_on', '') or '',
        'sla_due':           sla_due,
        'sla_warning':       _sla_is_at_risk(sla_due),
        'cmdb_ci':           rec.get('cmdb_ci', ''),
        'opened_by':         rec.get('opened_by', ''),
        # Parse work_notes inline from the record's own field (available when
        # the fetch includes it). Deeper history would need a sys_journal_field
        # query we don't currently issue.
        'work_notes':        _parse_sn_journal(rec.get('work_notes', '')),
        '_raw_work_notes':   rec.get('work_notes', '') or '',
        'tasks':             [], 'attachments': [],
    }


def _adapt_live_change(rec):
    """Shape a live ServiceNow change record to the dict our templates expect."""
    if not rec:
        return None
    state_display = str(rec.get('state', '') or '')
    return {
        'sys_id':            rec.get('sys_id', ''),
        'number':            rec.get('number', ''),
        'short_description': rec.get('short_description', ''),
        'type':              rec.get('type', '') or 'Normal',
        'state':             state_display,
        'state_code':        state_display.lower().replace(' ', '_'),
        'risk':              rec.get('risk', ''),
        'assignment_group':  rec.get('assignment_group', ''),
        'assigned_to':       rec.get('assigned_to', ''),
        'scheduled':         rec.get('start_date', ''),
        'cmdb_ci':           rec.get('cmdb_ci', ''),
        'opened_by':         rec.get('opened_by', ''),
        'ctasks':            [],          # populated by _get_change_context_live on detail pages
        'ctask_closed':      0,
        'ctask_pct':         0,
        'work_notes':        _parse_sn_journal(rec.get('work_notes', '')),
        '_raw_work_notes':   rec.get('work_notes', '') or '',
        'attachments':       [],
    }


def _get_incident_modal(request, number):
    if not _is_live(request):
        return _get_incident(number)
    # Live mode — run the task synchronously in-process via .apply()
    try:
        from .tasks import incident_get_by_field_task
        resp = incident_get_by_field_task.apply(args=[{
            'field':         'number',
            'value':         number,
            'display_value': True,
        }]).result
        return _adapt_live_incident(_unwrap_record(resp))
    except Exception:
        return None


def _get_change_modal(request, number):
    if not _is_live(request):
        return _get_change(number)
    try:
        from .tasks import changes_get_by_number_task
        resp = changes_get_by_number_task.apply(args=[{
            'number':        number,
            'display_value': True,
        }]).result
        return _adapt_live_change(_unwrap_record(resp))
    except Exception:
        return None


# ─── Live fetch — list-oriented helpers ──────────────────────────

def _unwrap_list(response):
    """Peel wrappers off a list-shaped task response, returning [] on any error."""
    if not response or not isinstance(response, dict):
        return []
    if response.get('error'):
        return []
    for key in ('records', 'result'):
        inner = response.get(key)
        if isinstance(inner, list):
            return inner
    return []


def _live_list(table: str, query: str, fields: str, limit: int):
    """Run table_list_task synchronously and return [] on any error.
    Kept as a thin, error-suppressing wrapper so call-sites stay readable."""
    try:
        from .tasks import table_list_task
        resp = table_list_task.apply(args=[{
            'table':         table,
            'query':         query,
            'fields':        fields,
            'limit':         limit,
            'display_value': True,
        }]).result
        return _unwrap_list(resp)
    except Exception:
        return []


# Minimal fieldsets the templates need. Keep to what's actually rendered
# so we don't waste bytes on ServiceNow's huge default row.
_INCIDENT_LIST_FIELDS = (
    'sys_id,number,short_description,priority,state,assignment_group,'
    'assigned_to,opened_at,sys_updated_on,cmdb_ci,opened_by,sla_due'
)
_CHANGE_LIST_FIELDS = (
    'sys_id,number,short_description,type,state,risk,assignment_group,'
    'assigned_to,start_date,end_date,sys_updated_on,cmdb_ci,opened_by'
)


# Best-effort state-code → encoded-query mapping. Instance-specific —
# tweak to match your own ServiceNow state choices.
_INCIDENT_STATE_QUERY = {
    'open':        'stateIN1,2,3',   # New / In Progress / On Hold
    'in_progress': 'state=2',
    'resolved':    'state=6',
}
_CHANGE_STATE_QUERY = {
    'scheduled': 'state=-2',
    'implement': 'state=-1',
    'review':    'state=0',
    'approved':  'state=-3',
}


def _days_clause(days: str, date_field: str) -> str:
    """Return an encoded-query clause for 'last N days' using gs.daysAgoStart."""
    if not days or days == 'all':
        return ''
    try:
        n = int(days)
    except (TypeError, ValueError):
        return ''
    return f'{date_field}>=javascript:gs.daysAgoStart({n})'


def _build_incident_list_query(priority, state_code, search, days) -> str:
    parts = []
    if priority:
        parts.append(f'priority={priority}')
    clause = _INCIDENT_STATE_QUERY.get(state_code)
    if clause:
        parts.append(clause)
    if search:
        parts.append(f'short_descriptionLIKE{search}^ORnumberLIKE{search}')
    d = _days_clause(days, 'opened_at')
    if d:
        parts.append(d)
    parts.append('ORDERBYDESCopened_at')
    return '^'.join(parts)


def _build_change_list_query(state_code, search, days) -> str:
    parts = []
    clause = _CHANGE_STATE_QUERY.get(state_code)
    if clause:
        parts.append(clause)
    if search:
        parts.append(f'short_descriptionLIKE{search}^ORnumberLIKE{search}')
    d = _days_clause(days, 'start_date')
    if d:
        parts.append(d)
    parts.append('ORDERBYDESCsys_updated_on')
    return '^'.join(parts)


def _build_incident_search_query(ci, requested_by, group, days) -> str:
    parts = []
    if ci:
        parts.append(f'cmdb_ci.nameLIKE{ci}')
    if requested_by:
        parts.append(f'opened_by.nameLIKE{requested_by}')
    if group:
        parts.append(f'assignment_group.nameLIKE{group}')
    d = _days_clause(days, 'opened_at')
    if d:
        parts.append(d)
    parts.append('ORDERBYDESCopened_at')
    return '^'.join(parts)


def _build_change_search_query(ci, requested_by, group, days) -> str:
    parts = []
    if ci:
        parts.append(f'cmdb_ci.nameLIKE{ci}')
    if requested_by:
        parts.append(f'opened_by.nameLIKE{requested_by}')
    if group:
        parts.append(f'assignment_group.nameLIKE{group}')
    d = _days_clause(days, 'start_date')
    if d:
        parts.append(d)
    parts.append('ORDERBYDESCsys_updated_on')
    return '^'.join(parts)


# ─── Live enrichment — sub-resources for detail pages ────────────

def _parse_sn_journal(raw) -> list:
    """Split a ServiceNow journal string (work_notes / comments) into entries.

    Shape expected by templates: [{'at': <time>, 'by': <user>, 'text': <body>}, …]
    ServiceNow's display_value for journal fields is typically a blob like:
        2024-01-15 14:32:00 - John Doe (Work notes)
        The note text here
        can span multiple lines.

        2024-01-15 13:00:00 - Jane Smith (Work notes)
        ...

    Falls back to emitting a single entry with just the raw text if the header
    can't be parsed — better than dropping the note entirely.
    """
    if not raw or not isinstance(raw, str):
        return []
    import re
    entries = []
    for block in re.split(r'\n\s*\n', raw.strip()):
        block = block.strip()
        if not block:
            continue
        first, _, rest = block.partition('\n')
        m = re.match(r'^(\S.*?)\s*-\s*(.*?)\s*\(.*?\)\s*$', first)
        if m:
            entries.append({
                'at':   m.group(1).strip(),
                'by':   m.group(2).strip(),
                'text': rest.strip(),
            })
        else:
            entries.append({'at': '', 'by': '', 'text': block})
    return entries


def _adapt_live_ctask(rec) -> dict:
    return {
        'sys_id':      rec.get('sys_id', ''),
        'number':      rec.get('number', ''),
        'description': rec.get('short_description', '') or rec.get('description', ''),
        'state':       str(rec.get('state', '') or ''),
        'assigned_to': rec.get('assigned_to', '') or '',
    }


def _adapt_live_incident_task(rec) -> dict:
    """Child incident_task records (shown on incident detail page)."""
    return {
        'sys_id':      rec.get('sys_id', ''),
        'number':      rec.get('number', ''),
        'description': rec.get('short_description', '') or '',
        'state':       str(rec.get('state', '') or ''),
        'assigned_to': rec.get('assigned_to', '') or '',
    }


def _adapt_live_attachment(rec) -> dict:
    """Translate SN sys_attachment fields to the template's attachment shape."""
    size = rec.get('size_bytes', '') or rec.get('size', '')
    try:
        n = int(size)
        if n >= 1024 * 1024:
            size_str = f'{n / (1024 * 1024):.1f} MB'
        elif n >= 1024:
            size_str = f'{n / 1024:.0f} KB'
        else:
            size_str = f'{n} B'
    except (ValueError, TypeError):
        size_str = str(size or '')
    return {
        'sys_id':        rec.get('sys_id', ''),
        'name':          rec.get('file_name', '') or rec.get('name', ''),
        'size':          size_str,
        'by':            rec.get('sys_created_by', '') or rec.get('by', ''),
        'at':            rec.get('sys_created_on', '') or rec.get('at', ''),
        'download_link': rec.get('download_link', ''),
    }


# ─── Live async polling ──────────────────────────────────────────
# Each read view in live mode dispatches a Celery task via .delay(),
# renders the page with a placeholder that polls live_poll, and the
# poll endpoint dispatches to a shape-specific renderer that returns
# the final swap-in HTML. Shapes are small and explicit — easier to
# reason about than a generic dispatcher.

def _render_live_error(request, title, detail='', hint=''):
    from django.http import HttpResponse
    resp = render(request, 'servicenow/partials/live_error.html', {
        'title':  title,
        'detail': detail,
        'hint':   hint,
    })
    # Returning 200 stops HTMX polling; the element is replaced with the error.
    return resp


def _render_fetch_incidents(request, payload, extras):
    """Bulk incident lookup result → render as the incidents section of lookup_results."""
    rows = _unwrap_list(payload)
    incidents = [_adapt_live_incident(r) for r in rows if r]
    requested = _csv_to_list(extras.get('numbers', ''))
    found_numbers = {i.get('number', '').upper() for i in incidents}
    not_found = [n for n in requested if n and n.upper() not in found_numbers]
    return render(request, 'servicenow/partials/lookup_section_incidents.html', {
        'incident_results': incidents,
        'not_found':        not_found,
    })


def _render_fetch_changes(request, payload, extras):
    rows = _unwrap_list(payload)
    changes_raw = [_adapt_live_change(r) for r in rows if r]
    changes = _annotate_ctask_pct(list(changes_raw))
    requested = _csv_to_list(extras.get('numbers', ''))
    found_numbers = {c.get('number', '').upper() for c in changes}
    not_found = [n for n in requested if n and n.upper() not in found_numbers]
    return render(request, 'servicenow/partials/lookup_section_changes.html', {
        'change_results': changes,
        'not_found':      not_found,
    })


def _render_incidents_list_body(request, payload, extras):
    raw = _unwrap_list(payload)
    incidents = [_adapt_live_incident(r) for r in raw if r]
    matched = len(incidents)
    incidents = incidents[:DEFAULT_LIST_LIMIT]
    return render(request, 'servicenow/partials/incidents_list_body.html', {
        'incidents': incidents,
        'matched':   matched,
        'limit':     DEFAULT_LIST_LIMIT,
        'truncated': matched > DEFAULT_LIST_LIMIT,
        'total':     len(incidents),
    })


def _render_changes_list_body(request, payload, extras):
    raw = _unwrap_list(payload)
    changes = [_adapt_live_change(r) for r in raw if r]
    matched = len(changes)
    changes = changes[:DEFAULT_LIST_LIMIT]
    changes = _annotate_ctask_pct(list(changes))
    return render(request, 'servicenow/partials/changes_list_body.html', {
        'changes':   changes,
        'matched':   matched,
        'limit':     DEFAULT_LIST_LIMIT,
        'truncated': matched > DEFAULT_LIST_LIMIT,
        'total':     len(changes),
    })


def _render_search_results(request, payload, extras):
    raw = _unwrap_list(payload)
    domain = extras.get('domain', 'incident')
    if domain == 'change':
        results = [_adapt_live_change(r) for r in raw if r]
        matched = len(results)
        results = results[:DEFAULT_LIST_LIMIT]
        results = _annotate_ctask_pct(list(results))
    else:
        results = [_adapt_live_incident(r) for r in raw if r]
        matched = len(results)
        results = results[:DEFAULT_LIST_LIMIT]
    return render(request, 'servicenow/partials/search_results.html', {
        'domain':           domain,
        'results':          results,
        'searched':         True,
        'any_filters':      True,
        'total':            len(results),
        'matched':          matched,
        'truncated':        matched > DEFAULT_LIST_LIMIT,
        'limit':            DEFAULT_LIST_LIMIT,
        'cmdb_ci':          extras.get('cmdb_ci', ''),
        'requested_by':     extras.get('requested_by', ''),
        'assignment_group': extras.get('assignment_group', ''),
        'days':             extras.get('days', DEFAULT_DAYS),
    })


def _render_incident_context(request, payload, extras):
    incident = _shape_incident_from_context(payload)
    if not incident:
        return _render_live_error(request, 'Incident not found',
                                  'The task finished but no incident record came back.')
    return render(request, 'servicenow/partials/incident_detail_body.html', {
        'incident': incident,
    })


def _render_change_context(request, payload, extras):
    change = _shape_change_from_context(payload)
    if not change:
        return _render_live_error(request, 'Change not found',
                                  'The task finished but no change record came back.')
    closed = sum(1 for t in change['ctasks'] if t.get('state') == 'Closed Complete')
    total = len(change['ctasks'])
    pct = int((closed / total) * 100) if total else 0
    return render(request, 'servicenow/partials/change_detail_body.html', {
        'change':       change,
        'ctask_closed': closed,
        'ctask_total':  total,
        'ctask_pct':    pct,
    })


def _render_change_briefing(request, payload, extras):
    change = _shape_change_from_context(payload)
    if not change:
        return _render_live_error(request, 'Change not found',
                                  'The task finished but no change record came back.')
    closed = sum(1 for t in change['ctasks'] if t.get('state') == 'Closed Complete')
    total = len(change['ctasks'])
    pct = int((closed / total) * 100) if total else 0
    prompt = _build_briefing_prompt(change, closed, total, pct)
    return render(request, 'servicenow/partials/change_briefing_body.html', {
        'change':       change,
        'ctask_closed': closed,
        'ctask_total':  total,
        'ctask_pct':    pct,
        'prompt':       prompt,
        'prompt_lines': len(prompt.splitlines()),
        'prompt_chars': len(prompt),
    })


def _render_bulk_review_card(request, payload, extras):
    change = _shape_change_from_context(payload)
    if not change:
        number = extras.get('number', '')
        return render(request, 'servicenow/partials/bulk_review_card.html', {
            'not_found': True,
            'number':    number,
        })
    closed = sum(1 for t in change['ctasks'] if t.get('state') == 'Closed Complete')
    total = len(change['ctasks'])
    pct = int((closed / total) * 100) if total else 0
    review = _heuristic_review(change, pct, closed, total)
    prompt = _build_briefing_prompt(change, closed, total, pct)
    return render(request, 'servicenow/partials/bulk_review_card.html', {
        'change':       change,
        'ctask_closed': closed,
        'ctask_total':  total,
        'ctask_pct':    pct,
        'review':       review,
        'prompt':       prompt,
        'not_found':    False,
    })


# Shape name → renderer function. Keep the strings stable; they appear
# in URLs rendered into templates (live/poll/<shape>/<task_id>/).
LIVE_POLL_RENDERERS = {
    'fetch-incidents':   _render_fetch_incidents,
    'fetch-changes':     _render_fetch_changes,
    'incidents-list':    _render_incidents_list_body,
    'changes-list':      _render_changes_list_body,
    'search-results':    _render_search_results,
    'incident-context':  _render_incident_context,
    'change-context':    _render_change_context,
    'change-briefing':   _render_change_briefing,
    'bulk-review-card':  _render_bulk_review_card,
    # 'preset-result' — registered when preset refactor lands
}


def _csv_to_list(s: str) -> list:
    return [p for p in (x.strip() for x in (s or '').split(',')) if p]


def _shape_change_from_context(payload):
    """Adapt a change_context_task result into the shape templates expect."""
    if not payload or not isinstance(payload, dict) or payload.get('error'):
        return None
    bundle = payload.get('result') or {}
    raw = bundle.get('change')
    if not raw:
        return None
    change = _adapt_live_change(raw)
    if not change:
        return None
    ctasks = []
    for ct in bundle.get('ctasks') or []:
        adapted = _adapt_live_ctask(ct)
        adapted['attachments'] = [_adapt_live_attachment(a) for a in (ct.get('attachments') or [])]
        ctasks.append(adapted)
    change['ctasks'] = ctasks
    change['attachments'] = [_adapt_live_attachment(a) for a in (bundle.get('change_attachments') or [])]
    return change


def _shape_incident_from_context(payload):
    """Adapt an incident_context_task result into the shape templates expect."""
    if not payload or not isinstance(payload, dict) or payload.get('error'):
        return None
    bundle = payload.get('result') or {}
    raw = bundle.get('incident')
    if not raw:
        return None
    incident = _adapt_live_incident(raw)
    if not incident:
        return None
    tasks = []
    for tw in bundle.get('tasks') or []:
        task_rec = tw.get('task') or {}
        adapted = _adapt_live_incident_task(task_rec)
        adapted['attachments'] = [_adapt_live_attachment(a) for a in (tw.get('attachments') or [])]
        tasks.append(adapted)
    incident['tasks'] = tasks
    incident['attachments'] = [
        _adapt_live_attachment(a) for a in (bundle.get('incident_attachments') or [])
    ]
    return incident


def live_poll(request, shape, task_id):
    """Generic poll endpoint.
    - task pending → 204 (HTMX keeps the existing polling element in place)
    - task failed  → error partial
    - task ready   → shape-specific renderer (swaps out the polling element)
    """
    from celery.result import AsyncResult
    from django.http import HttpResponse
    if shape not in LIVE_POLL_RENDERERS:
        return HttpResponse(f'Unknown shape: {shape}', status=404)

    result = AsyncResult(task_id)
    if not result.ready():
        return HttpResponse(status=204)  # no-swap: existing placeholder continues polling
    if result.failed():
        return _render_live_error(request, 'Task failed', detail=str(result.result)[:400])

    payload = result.result
    if isinstance(payload, dict) and payload.get('error'):
        return _render_live_error(
            request,
            title=str(payload.get('error', 'Error')),
            detail=str(payload.get('detail', '')),
            hint='Session required — check the pill up top.',
        )

    renderer = LIVE_POLL_RENDERERS[shape]
    return renderer(request, payload, request.GET)


def _get_change_context_live(number: str) -> dict | None:
    """Fetch a change + its ctasks (with attachments) + change attachments in ONE task.

    change_context_task runs all three fetches inside a single op(driver) call, so
    we pay one auth-retry / driver-acquisition overhead instead of three. Returns
    a dict shaped like the rest of the app expects, or None on failure.
    """
    if not number:
        return None
    try:
        from .tasks import change_context_task
        resp = change_context_task.apply(args=[{
            'change_number': number,
            'display_value': True,
        }]).result
    except Exception:
        return None

    if not resp or not isinstance(resp, dict) or resp.get('error'):
        return None

    bundle = resp.get('result') or {}
    change_raw = bundle.get('change')
    if not change_raw:
        return None

    change = _adapt_live_change(change_raw)
    if not change:
        return None

    # CTASKs already arrive bundled with their per-task attachments attached.
    ctasks = []
    for ct in bundle.get('ctasks') or []:
        adapted = _adapt_live_ctask(ct)
        adapted['attachments'] = [_adapt_live_attachment(a) for a in (ct.get('attachments') or [])]
        ctasks.append(adapted)
    change['ctasks'] = ctasks

    # Change-level attachments
    change['attachments'] = [
        _adapt_live_attachment(a) for a in (bundle.get('change_attachments') or [])
    ]
    return change


def _get_incident_context_live(number: str) -> dict | None:
    """Fetch an incident + its child tasks (with attachments) + incident attachments
    in ONE task via incident_context_task. Note the task wraps each child task as
    {'task': {...}, 'attachments': [...]} — unpacked here."""
    if not number:
        return None
    try:
        from .tasks import incident_context_task
        resp = incident_context_task.apply(args=[{
            'incident_number': number,
            'display_value': True,
        }]).result
    except Exception:
        return None

    if not resp or not isinstance(resp, dict) or resp.get('error'):
        return None

    bundle = resp.get('result') or {}
    inc_raw = bundle.get('incident')
    if not inc_raw:
        return None

    incident = _adapt_live_incident(inc_raw)
    if not incident:
        return None

    tasks = []
    for tw in bundle.get('tasks') or []:
        task_rec = tw.get('task') or {}
        adapted = _adapt_live_incident_task(task_rec)
        adapted['attachments'] = [_adapt_live_attachment(a) for a in (tw.get('attachments') or [])]
        tasks.append(adapted)
    incident['tasks'] = tasks

    incident['attachments'] = [
        _adapt_live_attachment(a) for a in (bundle.get('incident_attachments') or [])
    ]
    return incident


def _parse_numbers(raw):
    """Split a free-text block of record numbers into a clean list."""
    import re
    return [n.strip().upper() for n in re.split(r'[\s,;|/]+', raw) if n.strip()]


# ─────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────

def _annotate_ctask_pct(changes):
    """Attach ctask_pct and ctask_closed to each change dict."""
    for c in changes:
        total = len(c.get('ctasks', []))
        closed = sum(1 for t in c.get('ctasks', []) if t['state'] == 'Closed Complete')
        c['ctask_closed'] = closed
        c['ctask_pct'] = int((closed / total) * 100) if total else 0
    return changes


def dashboard(request):
    if _is_live(request):
        from django.conf import settings as dj_settings
        inc_table = getattr(dj_settings, 'SERVICENOW_INCIDENT_TABLE', 'incident')
        chg_table = getattr(dj_settings, 'SERVICENOW_CHANGE_TABLE', 'change_request')

        # Active slices — bounded so dashboard stays snappy on large instances.
        inc_raw = _live_list(
            inc_table,
            'active=true^ORDERBYDESCsys_updated_on',
            _INCIDENT_LIST_FIELDS,
            50,
        )
        chg_raw = _live_list(
            chg_table,
            'active=true^ORDERBYstart_date',
            _CHANGE_LIST_FIELDS,
            25,
        )
        incidents_src = [_adapt_live_incident(r) for r in inc_raw if r]
        changes_src   = [_adapt_live_change(r)   for r in chg_raw if r]

        stats = {
            'open_p1':         sum(1 for i in incidents_src if i.get('priority') == '1'),
            'open_p2':         sum(1 for i in incidents_src if i.get('priority') == '2'),
            'open_incidents':  len(incidents_src),
            'pending_changes': len(changes_src),
            'implementing':    sum(1 for c in changes_src if c.get('state_code') == 'implement'),
            'awaiting_review': sum(1 for c in changes_src if c.get('state_code') == 'review'),
        }
    else:
        incidents_src = _incidents_source(request)
        changes_src = _changes_source(request)
        stats = DEMO_STATS

    recent_incidents = [i for i in incidents_src if i.get('state_code') != 'resolved'][:4]
    todays_changes = _annotate_ctask_pct(list(changes_src[:3]))
    return render(request, 'core/index.html', {
        'stats': stats,
        'recent_incidents': recent_incidents,
        'todays_changes': todays_changes,
    })


def incidents_list(request):
    priority_filter = request.GET.get('priority', '')
    state_filter = request.GET.get('state', '')
    search = request.GET.get('q', '').lower()
    days = request.GET.get('days', DEFAULT_DAYS)

    live_task_id = ''
    if _is_live(request):
        # Async live-mode: dispatch task, render page with a polling placeholder.
        from django.conf import settings as dj_settings
        from .tasks import table_list_task
        table = getattr(dj_settings, 'SERVICENOW_INCIDENT_TABLE', 'incident')
        query = _build_incident_list_query(priority_filter, state_filter, search, days)
        task = table_list_task.delay({
            'table':         table,
            'query':         query,
            'fields':        _INCIDENT_LIST_FIELDS,
            'limit':         DEFAULT_LIST_LIMIT + 1,
            'display_value': True,
        })
        live_task_id = task.id
        incidents, matched = [], 0
    else:
        incidents = _filter_by_days(_incidents_source(request), '_opened_dt', days)
        if priority_filter:
            incidents = [i for i in incidents if i['priority'] == priority_filter]
        if state_filter:
            incidents = [i for i in incidents if i['state_code'] == state_filter]
        if search:
            incidents = [i for i in incidents if search in i['short_description'].lower() or search in i['number'].lower()]
        matched = len(incidents)
        incidents = incidents[:DEFAULT_LIST_LIMIT]

    return render(request, 'servicenow/incidents.html', {
        'incidents':       incidents,
        'priority_filter': priority_filter,
        'state_filter':    state_filter,
        'search':          search,
        'days':            days,
        'time_ranges':     TIME_RANGES,
        'limit':           DEFAULT_LIST_LIMIT,
        'total':           len(incidents),
        'matched':         matched,
        'truncated':       matched > DEFAULT_LIST_LIMIT,
        'live_task_id':    live_task_id,
    })


def incident_detail(request, number):
    if _is_live(request):
        from .tasks import incident_context_task
        task = incident_context_task.delay({
            'incident_number': number,
            'display_value':   True,
        })
        # Render page with polling placeholder; live_poll will swap in the body.
        return render(request, 'servicenow/incident_detail.html', {
            'incident':     None,
            'live_task_id': task.id,
        })
    incident = _get_incident(number)
    if not incident:
        from django.http import Http404
        raise Http404
    return render(request, 'servicenow/incident_detail.html', {'incident': incident})


def changes_list(request):
    state_filter = request.GET.get('state', '')
    search = request.GET.get('q', '').lower()
    days = request.GET.get('days', DEFAULT_DAYS)

    live_task_id = ''
    if _is_live(request):
        from django.conf import settings as dj_settings
        from .tasks import table_list_task
        table = getattr(dj_settings, 'SERVICENOW_CHANGE_TABLE', 'change_request')
        query = _build_change_list_query(state_filter, search, days)
        task = table_list_task.delay({
            'table':         table,
            'query':         query,
            'fields':        _CHANGE_LIST_FIELDS,
            'limit':         DEFAULT_LIST_LIMIT + 1,
            'display_value': True,
        })
        live_task_id = task.id
        changes, matched = [], 0
    else:
        changes = _filter_by_days(_changes_source(request), '_scheduled_dt', days)
        if state_filter:
            changes = [c for c in changes if c['state_code'] == state_filter]
        if search:
            changes = [c for c in changes if search in c['short_description'].lower() or search in c['number'].lower()]
        matched = len(changes)
        changes = changes[:DEFAULT_LIST_LIMIT]
    changes = _annotate_ctask_pct(list(changes))

    return render(request, 'servicenow/changes.html', {
        'changes':      changes,
        'state_filter': state_filter,
        'search':       search,
        'days':         days,
        'time_ranges':  TIME_RANGES,
        'limit':        DEFAULT_LIST_LIMIT,
        'total':        len(changes),
        'matched':      matched,
        'truncated':    matched > DEFAULT_LIST_LIMIT,
        'live_task_id': live_task_id,
    })


def change_detail(request, number):
    if _is_live(request):
        from .tasks import change_context_task
        task = change_context_task.delay({
            'change_number': number,
            'display_value': True,
        })
        return render(request, 'servicenow/change_detail.html', {
            'change':       None,
            'live_task_id': task.id,
        })
    change = _get_change(number)
    if not change:
        from django.http import Http404
        raise Http404
    closed = sum(1 for t in change['ctasks'] if t.get('state') == 'Closed Complete')
    total = len(change['ctasks'])
    pct = int((closed / total) * 100) if total else 0
    return render(request, 'servicenow/change_detail.html', {
        'change': change,
        'ctask_closed': closed,
        'ctask_total': total,
        'ctask_pct': pct,
    })


# ─────────────────────────────────────────────────────────────
# Change Briefing / AI Review
# ─────────────────────────────────────────────────────────────

def _build_briefing_prompt(change, ctask_closed, ctask_total, ctask_pct):
    """
    Produce a structured, AI-readable briefing for a change record.
    Includes a system instruction preamble so the prompt is ready to send.
    """
    W = 64  # column width for section dividers
    SEP = "─" * W

    def section(title):
        return f"\n{SEP}\n{title}\n{SEP}"

    lines = [
        "You are an experienced IT change management reviewer.",
        "Review the change request below and provide a concise assessment covering:",
        "  1. Readiness — are all pre-conditions and CTASKs in the expected state?",
        "  2. Risk assessment — any concerns given the risk level and scope?",
        "  3. Recommendation — APPROVE / HOLD / REJECT with a one-paragraph justification.",
        "",
        "Keep the response brief and actionable. Flag anything that looks incomplete or risky.",
        "",
    ]

    lines.append(section("CHANGE RECORD"))
    lines += [
        f"  Number          : {change['number']}",
        f"  Type            : {change['type']}",
        f"  Risk Level      : {change.get('risk', 'Unknown')}",
        f"  Current State   : {change['state']}",
        f"  Assignment Group: {change['assignment_group']}",
        f"  Assignee        : {change.get('assigned_to') or 'Unassigned'}",
        f"  Scheduled Start : {change['scheduled']}",
        "",
        f"  Description: {change['short_description']}",
    ]

    ctasks = change.get('ctasks', [])
    if ctasks:
        lines.append(section(f"IMPLEMENTATION TASKS  ({ctask_closed}/{ctask_total} closed · {ctask_pct}% complete)"))
        for t in ctasks:
            if t['state'] == 'Closed Complete':
                marker = '[DONE] '
            elif t['state'] == 'In Progress':
                marker = '[WIP]  '
            else:
                marker = '[OPEN] '
            assignee = f"  ← {t['assigned_to']}" if t.get('assigned_to') else ''
            lines.append(f"  {marker}{t['number']}  {t['description']}{assignee}")
            lines.append(f"          Status: {t['state']}")

    work_notes = change.get('work_notes', [])
    if work_notes:
        lines.append(section("WORK NOTES  (most recent first)"))
        for note in work_notes:
            lines.append(f"  [{note['at']}  {note['by']}]")
            lines.append(f"  {note['text']}")
            lines.append("")

    attachments = change.get('attachments', [])
    if attachments:
        lines.append(section("ATTACHMENTS"))
        for att in attachments:
            lines.append(f"  • {att['name']}  ({att['size']})  — {att['by']}  @ {att['at']}")

    lines.append(f"\n{'═' * W}")
    lines.append("Provide your change review assessment now.")

    return "\n".join(lines)


def change_briefing(request, number):
    if _is_live(request):
        from .tasks import change_context_task
        task = change_context_task.delay({
            'change_number': number,
            'display_value': True,
        })
        return render(request, 'servicenow/change_briefing.html', {
            'change':       None,
            'live_task_id': task.id,
        })
    change = _get_change(number)
    if not change:
        from django.http import Http404
        raise Http404

    closed = sum(1 for t in change['ctasks'] if t.get('state') == 'Closed Complete')
    total = len(change['ctasks'])
    pct = int((closed / total) * 100) if total else 0
    prompt = _build_briefing_prompt(change, closed, total, pct)

    return render(request, 'servicenow/change_briefing.html', {
        'change': change,
        'ctask_closed': closed,
        'ctask_total': total,
        'ctask_pct': pct,
        'prompt': prompt,
        'prompt_lines': len(prompt.splitlines()),
        'prompt_chars': len(prompt),
    })


def change_briefing_generate(request, number):
    """
    HTMX endpoint — generates the AI response panel.
    Replace the body of this function with a real AI API call later.
    """
    from django.http import HttpResponse
    if request.method != 'POST':
        return HttpResponse(status=405)

    if _is_live(request):
        change = _get_change_context_live(number)
    else:
        change = _get_change(number)
    if not change:
        from django.http import Http404
        raise Http404

    # ── Placeholder until AI is wired in ──────────────────────
    # To integrate: POST the prompt to Claude / OpenAI and stream
    # the response back here. Replace everything below with the
    # actual API call and return the rendered partial.
    ctx = {'change': change, 'ai_pending': True}
    return render(request, 'servicenow/partials/briefing_ai_response.html', ctx)


# ─────────────────────────────────────────────────────────────
# Bulk Change Review
# ─────────────────────────────────────────────────────────────

def _heuristic_review(change, ctask_pct, ctask_closed, ctask_total):
    """
    Rule-based pre-check while AI integration is pending.
    Returns a recommendation dict that the template renders.
    """
    flags = []
    positives = []

    # CTASK completeness
    if ctask_total == 0:
        flags.append("No CTASKs defined — scope unclear")
    elif ctask_pct == 100:
        positives.append(f"All {ctask_total} task(s) closed")
    elif ctask_pct >= 60:
        flags.append(f"{ctask_total - ctask_closed} task(s) still open ({ctask_pct}% done)")
    else:
        flags.append(f"Only {ctask_pct}% of tasks complete ({ctask_closed}/{ctask_total})")

    # Risk level
    risk = change.get('risk', '')
    if risk in ('High', 'Critical'):
        flags.append(f"{risk} risk — requires thorough review before approval")
    elif risk == 'Moderate':
        flags.append("Moderate risk — verify task completion and evidence")
    else:
        positives.append(f"{risk} risk level" if risk else "Risk level not set")

    # Work notes
    notes = change.get('work_notes', [])
    if not notes:
        flags.append("No work notes — no evidence of activity documented")
    else:
        positives.append(f"{len(notes)} work note(s) recorded")

    # Attachments
    attachments = change.get('attachments', [])
    if not attachments:
        flags.append("No attachments — runbook or evidence not uploaded")
    else:
        positives.append(f"{len(attachments)} attachment(s) present")

    # Determine recommendation
    critical_flags = [f for f in flags if any(w in f.lower() for w in ('only', 'no ctask', 'no work', 'no attach', '0%'))]
    if ctask_pct == 100 and not critical_flags and risk not in ('High', 'Critical'):
        recommendation = 'APPROVE'
    elif ctask_pct == 0 or len(flags) >= 3:
        recommendation = 'HOLD'
    elif risk in ('High', 'Critical') and ctask_pct < 100:
        recommendation = 'HOLD'
    else:
        recommendation = 'REVIEW'

    return {
        'recommendation': recommendation,
        'flags': flags,
        'positives': positives,
        'is_heuristic': True,
    }


def bulk_change_review(request):
    numbers_input = ''
    items = []       # [{number, delay_ms}] — fed to HTMX pending cards
    not_found = []
    searched = False

    if request.method == 'POST':
        searched = True
        numbers_input = request.POST.get('numbers', '')
        parsed = _parse_numbers(numbers_input)

        for i, num in enumerate(parsed):
            if num.startswith('CHG'):
                rec = _get_change_modal(request, num)
                if rec:
                    items.append({'number': num, 'delay_ms': i * 700})
                else:
                    not_found.append(num)
            else:
                not_found.append(num)

    ctx = {
        'numbers_input': numbers_input,
        'items': items,
        'not_found': not_found,
        'searched': searched,
        'total': len(items),
    }
    if request.method == 'POST' and request.headers.get('HX-Request'):
        return render(request, 'servicenow/partials/bulk_review_queue.html', ctx)
    return render(request, 'servicenow/bulk_change_review.html', ctx)


def bulk_change_review_item(request):
    """
    HTMX endpoint called per-change by the pending card.
    Returns the full review card for one change record.
    """
    from django.http import HttpResponse
    if request.method != 'POST':
        return HttpResponse(status=405)

    number = request.POST.get('number', '').strip().upper()
    if _is_live(request):
        # Async: dispatch the bundled context task, return a polling
        # placeholder. The poll endpoint renders the full bulk-review card
        # (including heuristic review + prompt) when the task completes.
        from urllib.parse import urlencode
        from .tasks import change_context_task
        task = change_context_task.delay({
            'change_number': number,
            'display_value': True,
        })
        return render(request, 'servicenow/partials/live_loading.html', {
            'shape':          'bulk-review-card',
            'task_id':        task.id,
            'extras':         urlencode({'number': number}),
            'label':          f'Reviewing {number}…',
            'placeholder_id': f'bulk-card-{number}',
        })

    change = _get_change(number)
    if not change:
        return render(request, 'servicenow/partials/bulk_review_card.html', {
            'not_found': True,
            'number': number,
        })

    closed = sum(1 for t in change['ctasks'] if t.get('state') == 'Closed Complete')
    total = len(change['ctasks'])
    pct = int((closed / total) * 100) if total else 0
    review = _heuristic_review(change, pct, closed, total)
    prompt = _build_briefing_prompt(change, closed, total, pct)

    return render(request, 'servicenow/partials/bulk_review_card.html', {
        'change': change,
        'ctask_closed': closed,
        'ctask_total': total,
        'ctask_pct': pct,
        'review': review,
        'prompt': prompt,
        'not_found': False,
    })


# ─────────────────────────────────────────────────────────────
# Presets Browser
# ─────────────────────────────────────────────────────────────

def _preset_demo_incidents(preset_name, params):
    """Return filtered DEMO_INCIDENTS matching the preset intent."""
    items = DEMO_INCIDENTS
    if preset_name == 'p1_open_incidents':
        items = [i for i in items if i['priority'] == '1' and i['state_code'] != 'resolved']
    elif preset_name == 'p1_p2_open_incidents':
        items = [i for i in items if i['priority'] in ('1', '2') and i['state_code'] != 'resolved']
    elif preset_name == 'incident_by_number':
        num = params.get('number', '').upper()
        items = [i for i in items if i['number'] == num]
    elif preset_name == 'open_incidents_for_group':
        items = [i for i in items if i['state_code'] != 'resolved']
    elif preset_name == 'unassigned_open_incidents':
        items = [i for i in items if not i.get('assigned_to') and i['state_code'] != 'resolved']
    elif preset_name == 'recent_open_incidents_by_service':
        items = [i for i in items if i['state_code'] != 'resolved']
    elif preset_name == 'sla_breaching_incidents':
        items = [i for i in items if i.get('sla_warning')]
    return items


def _preset_demo_changes(preset_name, params):
    """Return filtered DEMO_CHANGES matching the preset intent."""
    items = DEMO_CHANGES
    if preset_name == 'changes_implementing_now':
        items = [c for c in items if c['state_code'] == 'implement']
    elif preset_name == 'changes_awaiting_review':
        items = [c for c in items if c['state_code'] == 'review']
    elif preset_name == 'changes_scheduled_next_24h':
        items = [c for c in items if c['state_code'] in ('scheduled', 'approved')]
    elif preset_name == 'change_by_number':
        num = params.get('number', '').upper()
        items = [c for c in items if c['number'] == num]
    elif preset_name == 'recent_open_changes_by_group':
        items = [c for c in items if c['state_code'] not in ('closed', 'cancelled')]
    elif preset_name == 'high_risk_changes':
        items = [c for c in items if c.get('risk') in ('High', 'Critical')]
    elif preset_name == 'emergency_changes':
        items = [c for c in items if c.get('type', '').lower() == 'emergency']
    return items


def _count_preset_demo(name, cfg):
    """Return demo record count for no-param presets (used for sidebar badges)."""
    if cfg.get('required_params'):
        return None  # can't pre-count parameterised presets
    domain = cfg.get('domain', '')
    if domain == 'incident':
        return len(_preset_demo_incidents(name, {}))
    if domain == 'change':
        return len(_preset_demo_changes(name, {}))
    return 0


def _run_preset_for_display(preset_name, params=None, request=None):
    """
    Render a preset and return the full context dict needed by preset_result.html.
    Used by presets_page to server-render the initial/default result.
    """
    from .services.query_presets import render_preset, get_all_presets
    params = params or {}
    all_presets = get_all_presets()
    if preset_name not in all_presets:
        return None
    try:
        rendered = render_preset(preset_name, params)
    except ValueError:
        return None

    preset_cfg = all_presets[preset_name]
    domain = preset_cfg.get('domain', '')
    columns = [f.strip() for f in rendered['fields'].split(',') if f.strip()]
    live = bool(request and _is_live(request))

    if live:
        # Run the preset through its Celery task body synchronously.
        # presets_run_task internally calls render_preset + list_records,
        # so it respects user overrides and parameters exactly like demo.
        try:
            from .tasks import presets_run_task
            resp = presets_run_task.apply(args=[{
                'preset': preset_name,
                'params': params,
            }]).result
            raw_results = _unwrap_list(resp)
        except Exception:
            raw_results = []
    elif domain == 'incident':
        raw_results = _preset_demo_incidents(preset_name, params)
    elif domain == 'change':
        raw_results = _preset_demo_changes(preset_name, params)
    else:
        raw_results = []

    FIELD_MAP = {
        'priority': 'priority_label', 'opened_at': 'opened',
        'sys_updated_on': 'age', 'start_date': 'scheduled', 'end_date': 'scheduled',
        'sla_due': lambda r: 'Breached' if r.get('sla_warning') else '—',
    }

    def get_field(record, field):
        # Live records use the raw SN field names directly — the FIELD_MAP
        # is only for the demo-data shape (priority_label, age, scheduled, …).
        if live:
            return record.get(field, '—') or '—'
        mapping = FIELD_MAP.get(field)
        if mapping is None:
            return record.get(field, '—') or '—'
        if callable(mapping):
            return mapping(record)
        return record.get(mapping, '—') or '—'

    header_labels = {
        'number': 'Number', 'short_description': 'Description', 'priority': 'Priority',
        'state': 'State', 'assignment_group': 'Group', 'assigned_to': 'Assignee',
        'opened_at': 'Opened', 'sys_updated_on': 'Updated', 'sla_due': 'SLA Due',
        'start_date': 'Start', 'end_date': 'End', 'risk': 'Risk', 'type': 'Type',
        'sys_id': 'Sys ID',
    }
    display_cols = [(col, header_labels.get(col, col.replace('_', ' ').title()))
                    for col in columns if col != 'sys_id']

    rows = []
    for rec in raw_results:
        cells = []
        for col, _label in display_cols:
            cells.append({
                'col': col,
                'val': get_field(rec, col),
                'number_val': rec.get('number', '') if col == 'number' else '',
            })
        rows.append(cells)

    return {
        'preset_name': preset_name,
        'preset_cfg': preset_cfg,
        'rendered': rendered,
        'display_cols': display_cols,
        'rows': rows,
        'total': len(rows),
        'is_demo': True,
    }


def presets_page(request):
    from .services.query_presets import get_all_presets, load_user_presets

    DEFAULT_PRESET = 'p1_p2_open_incidents'
    all_presets = get_all_presets()
    user_preset_names = set(load_user_presets().keys())

    grouped = {}
    for name, cfg in all_presets.items():
        domain = cfg.get('domain', 'general')
        grouped.setdefault(domain, [])
        grouped[domain].append({
            'name': name,
            'description': cfg.get('description', ''),
            'required_params': cfg.get('required_params', []),
            'table': cfg.get('table', ''),
            'fields': cfg.get('fields', ''),
            'demo_count': _count_preset_demo(name, cfg),
            'is_user_defined': name in user_preset_names,
        })

    presets_data = {
        name: {
            'description': cfg.get('description', ''),
            'required_params': cfg.get('required_params', []),
            'table': cfg.get('table', ''),
            'domain': cfg.get('domain', ''),
            'query': cfg.get('query', ''),
            'fields': cfg.get('fields', ''),
            'is_user_defined': name in user_preset_names,
        }
        for name, cfg in all_presets.items()
    }

    initial_result_ctx = _run_preset_for_display(DEFAULT_PRESET, request=request)
    initial_result_html = ''
    if initial_result_ctx:
        from django.template.loader import render_to_string
        initial_result_html = render_to_string(
            'servicenow/partials/preset_result.html',
            initial_result_ctx,
            request=request,
        )

    return render(request, 'servicenow/presets.html', {
        'grouped': grouped,
        'presets_data': presets_data,
        'domain_order': ['change', 'incident'],
        'default_preset': DEFAULT_PRESET,
        'initial_result_html': initial_result_html,
    })


def preset_run_ui(request):
    from django.http import HttpResponse
    if request.method != 'POST':
        return HttpResponse(status=405)

    from .services.query_presets import get_all_presets

    preset_name = request.POST.get('preset_name', '').strip()
    params = {k: v for k, v in request.POST.items()
              if k not in ('csrfmiddlewaretoken', 'preset_name') and v}

    all_presets = get_all_presets()
    if not preset_name or preset_name not in all_presets:
        return render(request, 'servicenow/partials/preset_result.html', {
            'error': f'Unknown preset "{preset_name}".',
        })

    required = all_presets[preset_name].get('required_params', [])
    missing = [p for p in required if not params.get(p)]
    if missing:
        return render(request, 'servicenow/partials/preset_result.html', {
            'error': f'Missing required parameter(s): {", ".join(missing)}',
            'preset_name': preset_name,
        })

    ctx = _run_preset_for_display(preset_name, params, request=request)
    if ctx is None:
        return render(request, 'servicenow/partials/preset_result.html', {
            'error': 'Failed to render preset.',
            'preset_name': preset_name,
        })

    return render(request, 'servicenow/partials/preset_result.html', ctx)


def preset_save(request):
    """Create or update a user-defined preset."""
    from django.http import HttpResponse, HttpResponseRedirect
    import re
    if request.method != 'POST':
        return HttpResponse(status=405)

    from .services.query_presets import save_user_preset

    name        = request.POST.get('name', '').strip()
    description = request.POST.get('description', '').strip()
    domain      = request.POST.get('domain', '').strip()
    table       = request.POST.get('table', '').strip()
    query       = request.POST.get('query', '').strip()
    fields      = request.POST.get('fields', '').strip()
    limit_str   = request.POST.get('limit', '25').strip()
    req_params  = request.POST.get('required_params', '').strip()

    errors = []
    if not name:
        errors.append('Preset name (slug) is required.')
    elif not re.match(r'^[a-z][a-z0-9_]*$', name):
        errors.append('Name must start with a letter and contain only lowercase letters, digits, and underscores.')
    if not description:
        errors.append('Description is required.')
    if not table:
        errors.append('Table is required.')
    if not query:
        errors.append('Query is required.')
    if not fields:
        errors.append('Fields are required.')
    if domain not in ('change', 'incident'):
        errors.append('Domain must be "change" or "incident".')

    if errors:
        # Return 200 so HTMX swaps the error partial (4xx responses are dropped by default)
        return render(request, 'servicenow/partials/preset_form_errors.html',
                      {'errors': errors}, status=200)

    if req_params:
        required_params = [p.strip() for p in req_params.split(',') if p.strip()]
    else:
        required_params = sorted(set(re.findall(r'\{(\w+)\}', query)))

    try:
        limit = max(1, int(limit_str))
    except ValueError:
        limit = 25

    save_user_preset(name, {
        'description': description,
        'table': table,
        'query': query,
        'fields': fields,
        'defaults': {'limit': limit, 'display_value': True},
        'required_params': required_params,
        'domain': domain,
    })
    _push_activity(request,
                   type='preset_saved',
                   title=f'Saved preset "{name}"',
                   detail=description,
                   link='/servicenow/presets/',
                   severity='success')

    if request.headers.get('HX-Request'):
        resp = HttpResponse(status=200)
        resp['HX-Redirect'] = '/servicenow/presets/'
        return resp
    return HttpResponseRedirect('/servicenow/presets/')


def presets_export(request):
    """Return all currently-effective presets (built-ins + user overrides) as a JSON download."""
    from .services.query_presets import get_all_presets
    from django.http import HttpResponse
    import json

    export = {}
    for name, cfg in get_all_presets().items():
        export[name] = {
            'description':     cfg.get('description', ''),
            'table':           cfg.get('table', ''),
            'domain':          cfg.get('domain', ''),
            'query':           cfg.get('query', ''),
            'fields':          cfg.get('fields', ''),
            'required_params': cfg.get('required_params', []),
            'defaults':        cfg.get('defaults') or {'limit': 25, 'display_value': True},
        }

    content = json.dumps(export, indent=2)
    resp = HttpResponse(content, content_type='application/json')
    resp['Content-Disposition'] = 'attachment; filename="presets.json"'
    return resp


def presets_import(request):
    """
    Accept either a file upload ('import_file') or pasted JSON ('import_json').
    Validates each entry, saves good ones as user presets, reports errors.
    Format: { "name": {cfg} }  OR  [ { "name": ..., ...cfg } ]
    """
    from django.http import HttpResponse
    from .services.query_presets import save_user_preset
    import json
    import re
    if request.method != 'POST':
        return HttpResponse(status=405)

    content = ''
    upload = request.FILES.get('import_file')
    pasted = request.POST.get('import_json', '').strip()
    if upload:
        raw = upload.read()
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8-sig', errors='replace')
        content = raw
    elif pasted:
        content = pasted

    if not content:
        return render(request, 'servicenow/partials/preset_import_result.html', {
            'fatal_error': 'Paste JSON or choose a file before importing.',
        }, status=200)

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return render(request, 'servicenow/partials/preset_import_result.html', {
            'fatal_error': f'Invalid JSON: {e}',
        }, status=200)

    # Normalise to a list of flat entries with 'name' key
    if isinstance(data, dict):
        entries = [{'name': k, **(v or {})} for k, v in data.items()]
    elif isinstance(data, list):
        entries = data
    else:
        return render(request, 'servicenow/partials/preset_import_result.html', {
            'fatal_error': 'Expected a JSON object or array at the top level.',
        }, status=200)

    errors = []
    saved_names = []

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f'Entry #{i + 1}: not a JSON object')
            continue

        name = str(entry.get('name', '')).strip()
        if not name:
            errors.append(f'Entry #{i + 1}: missing name')
            continue
        if not re.match(r'^[a-z][a-z0-9_]*$', name):
            errors.append(f'{name}: invalid name (lowercase letters, digits, underscores only)')
            continue

        missing = [f for f in ('description', 'table', 'query', 'fields', 'domain')
                   if not str(entry.get(f, '')).strip()]
        if missing:
            errors.append(f'{name}: missing required fields: {", ".join(missing)}')
            continue
        if entry.get('domain') not in ('change', 'incident'):
            errors.append(f'{name}: domain must be "change" or "incident"')
            continue

        save_user_preset(name, {
            'description':     entry['description'],
            'table':           entry['table'],
            'query':           entry['query'],
            'fields':          entry['fields'],
            'defaults':        entry.get('defaults') or {'limit': 25, 'display_value': True},
            'required_params': entry.get('required_params') or [],
            'domain':          entry['domain'],
        })
        saved_names.append(name)

    if saved_names:
        _push_activity(request,
                       type='presets_imported',
                       title=f'Imported {len(saved_names)} preset{"s" if len(saved_names) != 1 else ""}',
                       detail=(', '.join(saved_names[:5]) + ('…' if len(saved_names) > 5 else '')),
                       link='/servicenow/presets/',
                       severity='success')

    return render(request, 'servicenow/partials/preset_import_result.html', {
        'success_count': len(saved_names),
        'saved_names':   saved_names,
        'errors':        errors,
        'total':         len(entries),
    }, status=200)


def preset_delete(request):
    """Delete a user-defined preset (built-ins are protected)."""
    from django.http import HttpResponse, HttpResponseRedirect
    if request.method != 'POST':
        return HttpResponse(status=405)

    from .services.query_presets import delete_user_preset, load_user_presets

    name = request.POST.get('name', '').strip()
    if not name or name not in load_user_presets():
        return HttpResponse('Cannot delete a built-in preset.', status=400)

    delete_user_preset(name)
    _push_activity(request,
                   type='preset_deleted',
                   title=f'Deleted preset "{name}"',
                   link='/servicenow/presets/',
                   severity='warning')

    if request.headers.get('HX-Request'):
        resp = HttpResponse(status=200)
        resp['HX-Redirect'] = '/servicenow/presets/'
        return resp
    return HttpResponseRedirect('/servicenow/presets/')


# ─────────────────────────────────────────────────────────────
# Cross-domain Record Search
# ─────────────────────────────────────────────────────────────

def _match(haystack: str, needle: str) -> bool:
    """Case-insensitive substring match. Empty needle matches everything."""
    if not needle:
        return True
    return needle.lower().strip() in (haystack or '').lower()


def _filter_records(records, ci, requested_by, assignment_group):
    return [
        r for r in records
        if _match(r.get('cmdb_ci', ''),          ci)
        and _match(r.get('opened_by', ''),       requested_by)
        and _match(r.get('assignment_group', ''), assignment_group)
    ]


def search_records(request):
    """Cross-domain search by CI, requester, or assignment group (with time range)."""
    domain = request.POST.get('domain') or request.GET.get('domain') or 'incident'
    ci = request.POST.get('cmdb_ci', '').strip()
    requested_by = request.POST.get('requested_by', '').strip()
    assignment_group = request.POST.get('assignment_group', '').strip()
    days = request.POST.get('days') or request.GET.get('days') or DEFAULT_DAYS
    searched = False
    results = []
    matched = 0

    live_task_id = ''
    live_extras = ''

    if request.method == 'POST':
        searched = True
        if _is_live(request):
            # Async: dispatch list task, return a placeholder that polls.
            from django.conf import settings as dj_settings
            from .tasks import table_list_task
            if domain == 'change':
                table = getattr(dj_settings, 'SERVICENOW_CHANGE_TABLE', 'change_request')
                query = _build_change_search_query(ci, requested_by, assignment_group, days)
                fields = _CHANGE_LIST_FIELDS
            else:
                domain = 'incident'
                table = getattr(dj_settings, 'SERVICENOW_INCIDENT_TABLE', 'incident')
                query = _build_incident_search_query(ci, requested_by, assignment_group, days)
                fields = _INCIDENT_LIST_FIELDS
            task = table_list_task.delay({
                'table':         table,
                'query':         query,
                'fields':        fields,
                'limit':         DEFAULT_LIST_LIMIT + 1,
                'display_value': True,
            })
            live_task_id = task.id
            # Propagate filter state to the poll endpoint so the result template
            # can echo the filter chips.
            from urllib.parse import urlencode
            live_extras = urlencode({
                'domain':           domain,
                'cmdb_ci':          ci,
                'requested_by':     requested_by,
                'assignment_group': assignment_group,
                'days':             days,
            })
            results, matched = [], 0
        elif domain == 'change':
            base = _filter_by_days(_changes_source(request), '_scheduled_dt', days)
            results = _filter_records(base, ci, requested_by, assignment_group)
            matched = len(results)
            results = results[:DEFAULT_LIST_LIMIT]
            results = _annotate_ctask_pct(list(results))
        else:
            domain = 'incident'
            base = _filter_by_days(_incidents_source(request), '_opened_dt', days)
            results = _filter_records(base, ci, requested_by, assignment_group)
            matched = len(results)
            results = results[:DEFAULT_LIST_LIMIT]

    ctx = {
        'domain':           domain,
        'cmdb_ci':          ci,
        'requested_by':     requested_by,
        'assignment_group': assignment_group,
        'days':             days,
        'time_ranges':      TIME_RANGES,
        'limit':            DEFAULT_LIST_LIMIT,
        'results':          results,
        'searched':         searched,
        'any_filters':      bool(ci or requested_by or assignment_group),
        'total':            len(results),
        'matched':          matched,
        'truncated':        matched > DEFAULT_LIST_LIMIT,
        'live_task_id':     live_task_id,
        'live_extras':      live_extras,
    }

    # HTMX partial swap — only for POSTs driven by the form, not hx-boost nav
    if request.method == 'POST' and request.headers.get('HX-Request'):
        if live_task_id:
            # Return a placeholder. HTMX swaps it into #search-results; the
            # placeholder's own hx-get then polls and swaps itself on success.
            return render(request, 'servicenow/partials/live_loading.html', {
                'shape':          'search-results',
                'task_id':        live_task_id,
                'extras':         live_extras,
                'label':          'Searching ServiceNow…',
                'placeholder_id': 'search-live-placeholder',
            })
        return render(request, 'servicenow/partials/search_results.html', ctx)

    # Full-page render — include search presets for the dropdown / modal
    from .services.search_presets import load_presets
    ctx['search_presets'] = load_presets()
    return render(request, 'servicenow/search.html', ctx)


def _render_search_preset_list(request):
    from .services.search_presets import load_presets
    return render(request, 'servicenow/partials/search_preset_list.html', {
        'search_presets': load_presets(),
    })


def search_preset_save(request):
    """POST: create or update a search preset."""
    from django.http import HttpResponse
    from .services.search_presets import save_preset
    import re
    if request.method != 'POST':
        return HttpResponse(status=405)

    key              = request.POST.get('key', '').strip()
    app_id           = request.POST.get('app_id', '').strip()
    label            = request.POST.get('label', '').strip()
    cmdb_ci          = request.POST.get('cmdb_ci', '').strip()
    requested_by     = request.POST.get('requested_by', '').strip()
    assignment_group = request.POST.get('assignment_group', '').strip()

    errors = []
    if not key:
        errors.append('Key is required.')
    elif not re.match(r'^[a-z][a-z0-9_]*$', key):
        errors.append('Key must start with a letter; lowercase letters, digits, underscores only.')
    if not app_id:
        errors.append('App ID is required.')
    if not cmdb_ci:
        errors.append('Configuration Item is required (the whole point is to shortcut this value).')

    if errors:
        return render(request, 'servicenow/partials/search_preset_errors.html',
                      {'errors': errors}, status=200)

    save_preset(key, {
        'app_id':           app_id,
        'label':            label,
        'cmdb_ci':          cmdb_ci,
        'requested_by':     requested_by,
        'assignment_group': assignment_group,
    })
    _push_activity(request,
                   type='search_preset_saved',
                   title=f'Saved search preset "{app_id}"' + (f' — {label}' if label else ''),
                   detail=f'key: {key} · CI: {cmdb_ci}',
                   link='/servicenow/search/',
                   severity='success')
    response = _render_search_preset_list(request)
    response['HX-Retarget'] = '#search-preset-list'
    response['HX-Reswap'] = 'innerHTML'
    # Tell the page to refresh presets AND the badge
    response['HX-Trigger'] = 'search-presets-changed, activity-updated'
    return response


def search_preset_delete(request):
    """POST: remove a search preset."""
    from django.http import HttpResponse
    from .services.search_presets import delete_preset, load_presets
    if request.method != 'POST':
        return HttpResponse(status=405)
    key = request.POST.get('key', '').strip()
    if key and key in load_presets():
        delete_preset(key)
        _push_activity(request,
                       type='search_preset_deleted',
                       title=f'Deleted search preset "{key}"',
                       link='/servicenow/search/',
                       severity='warning')
    response = _render_search_preset_list(request)
    response['HX-Trigger'] = 'search-presets-changed, activity-updated'
    return response


def search_presets_json(request):
    """GET: tiny JSON endpoint used by the Search page to refresh its in-memory presets after add/delete."""
    from django.http import JsonResponse
    from .services.search_presets import load_presets
    return JsonResponse(load_presets())


def data_mode_toggle(request):
    """POST: flip the user's data mode between 'demo' and 'live' and refresh the page."""
    from django.http import HttpResponse
    if request.method != 'POST':
        return HttpResponse(status=405)
    current = _data_mode(request)
    new_mode = 'live' if current == 'demo' else 'demo'
    request.session['data_mode'] = new_mode
    _push_activity(request,
                   type='mode_toggled',
                   title=f'Switched data mode to {new_mode.title()}',
                   severity='info')
    resp = HttpResponse(status=200)
    # HTMX refreshes the current page so every template picks up the new mode.
    resp['HX-Refresh'] = 'true'
    return resp


# ─── Preferences panel ───────────────────────────────────────────

def _preferences_context(request):
    """Build the context dict used by the preferences modal body partial."""
    from .services.user_preferences import load_preferences
    from .services.query_presets import load_user_presets
    from .services.creation_templates import load_templates as load_creation_templates
    from .services.search_presets import load_presets as load_search_presets

    # Best-effort ServiceNow session summary (doesn't blow up if session infra absent)
    sn_session = {'status_label': 'Unknown', 'user_key': 'localuser', 'process_alive': False}
    try:
        from . import views as sn_views
        sn_session = sn_views._build_session_context()
    except Exception:
        pass

    return {
        'prefs':            load_preferences(),
        'current_mode':     _data_mode(request),
        'sn_session':       sn_session,
        'query_preset_count':     len(load_user_presets()),
        'creation_template_count': len(load_creation_templates()),
        'search_preset_count':    len(load_search_presets()),
    }


def preferences_modal(request):
    """GET: return the modal body partial (HTMX-loaded when the dialog opens)."""
    return render(request, 'servicenow/partials/preferences_modal.html',
                  _preferences_context(request))


def preferences_save(request):
    """POST: update saved preferences (default data mode). Returns the refreshed modal body."""
    from django.http import HttpResponse
    from .services.user_preferences import save_preferences
    if request.method != 'POST':
        return HttpResponse(status=405)

    updates = {}
    dm = (request.POST.get('default_data_mode') or '').strip()
    if dm in DATA_MODES:
        updates['default_data_mode'] = dm

    if updates:
        save_preferences(updates)

    return render(request, 'servicenow/partials/preferences_modal.html',
                  _preferences_context(request))


def _push_activity(request, **event):
    """Thin wrapper — safe to call from any view; no-ops if session is missing."""
    try:
        from .services.activity import push
        if hasattr(request, 'session'):
            push(request.session, **event)
    except Exception:
        pass


def activity_modal(request):
    """GET: returns the body of the activity dialog. Marks all events read."""
    from .services.activity import list_all, mark_all_read
    events = list_all(request.session)
    if events:
        mark_all_read(request.session)
    return render(request, 'servicenow/partials/activity_modal.html', {
        'events': events,
    })


def activity_badge(request):
    """GET: returns the badge span for HTMX polling."""
    from .services.activity import unread_count
    return render(request, 'servicenow/partials/activity_badge.html', {
        'unread': unread_count(request.session),
    })


def activity_clear(request):
    """POST: empties the activity log and returns the refreshed modal body."""
    from django.http import HttpResponse
    from .services.activity import clear, list_all
    if request.method != 'POST':
        return HttpResponse(status=405)
    clear(request.session)
    resp = render(request, 'servicenow/partials/activity_modal.html', {
        'events': list_all(request.session),
    })
    resp['HX-Trigger'] = 'activity-updated'
    return resp


def preferences_reset_store(request):
    """POST: empty one of the file-backed stores. Returns the refreshed modal body."""
    from django.http import HttpResponse
    from pathlib import Path
    import json
    if request.method != 'POST':
        return HttpResponse(status=405)

    target = request.POST.get('store', '').strip()
    store_map = {
        'query_presets':      Path(__file__).parent / 'user_presets.json',
        'creation_templates': Path(__file__).parent / 'creation_templates.json',
        'search_presets':     Path(__file__).parent / 'search_presets.json',
    }
    path = store_map.get(target)
    if path is not None:
        try:
            path.write_text(json.dumps({}, indent=2), encoding='utf-8')
        except Exception:
            pass
    return render(request, 'servicenow/partials/preferences_modal.html',
                  _preferences_context(request))


# ─────────────────────────────────────────────────────────────
# Bulk Change Creation
# ─────────────────────────────────────────────────────────────

def _render_template_list(request):
    """Render the template manager list partial — used after save/delete."""
    from .services.creation_templates import load_templates_by_kind
    return render(request, 'servicenow/partials/bulk_change_template_list.html', {
        'templates': load_templates_by_kind('standard_change'),
    })


def bulk_change_create(request):
    """GET: render the bulk-create page."""
    from .services.creation_templates import load_templates_by_kind
    return render(request, 'servicenow/bulk_change_create.html', {
        'templates': load_templates_by_kind('standard_change'),
    })


def bulk_change_preview(request):
    """POST: parse + validate pasted text or uploaded CSV, return preview partial."""
    from django.http import HttpResponse
    if request.method != 'POST':
        return HttpResponse(status=405)

    from .services.bulk_change_parser import parse_text, parse_csv_file, validate_rows, summarise
    from .services.creation_templates import load_templates_by_kind

    pasted = request.POST.get('pasted', '')
    upload = request.FILES.get('csv_file')

    if upload:
        rows = parse_csv_file(upload)
        source = f'CSV: {upload.name}'
    elif pasted.strip():
        rows = parse_text(pasted)
        source = 'Pasted text'
    else:
        return render(request, 'servicenow/partials/bulk_change_preview.html', {
            'error': 'Paste some rows or choose a CSV file.',
        })

    templates = load_templates_by_kind('standard_change')
    validated = validate_rows(rows, known_template_keys=list(templates.keys()))
    summary = summarise(validated)

    return render(request, 'servicenow/partials/bulk_change_preview.html', {
        'rows': validated,
        'summary': summary,
        'source': source,
        'templates': templates,
    })


def bulk_change_submit(request):
    """
    POST: kick off creates for valid rows.

    Expected body (JSON): { "rows": [ {row dict}, ... ] }
    For normal/emergency: queue changes_create_task.delay() and return task_id.
    For standard: return the pre-built template URL for the client to open.

    Response:
    {
        "items": [
            {"row_index": 0, "kind": "normal",    "task_id": "abc", "short_description": "..."},
            {"row_index": 1, "kind": "standard",  "url": "https://...",        "short_description": "..."},
            ...
        ]
    }
    """
    from django.http import JsonResponse, HttpResponse
    import json
    if request.method != 'POST':
        return HttpResponse(status=405)

    from .services.bulk_change_parser import validate_rows
    from .services.creation_templates import load_templates_by_kind, build_standard_change_url
    from .tasks import changes_create_task

    try:
        body = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid_json'}, status=400)

    raw_rows = body.get('rows') or []
    templates = load_templates_by_kind('standard_change')
    validated = validate_rows(raw_rows, known_template_keys=list(templates.keys()))

    items = []
    for r in validated:
        if not r['is_valid']:
            items.append({
                'row_index':         r['row_index'],
                'kind':              r['type'] or 'invalid',
                'short_description': r['short_description'],
                'error':             '; '.join(r['errors']) or 'validation failed',
            })
            continue

        short_desc = r['short_description']

        if r['type'] in ('normal', 'emergency'):
            fields = {
                'short_description': short_desc,
                'assignment_group':  r['assignment_group'],
                'start_date':        r['start_date'],
                'end_date':          r['end_date'],
            }
            if r.get('description'):
                fields['description'] = r['description']
            if r.get('risk'):
                fields['risk'] = r['risk']

            task = changes_create_task.delay({'kind': r['type'], 'fields': fields})
            items.append({
                'row_index':         r['row_index'],
                'kind':              r['type'],
                'task_id':           task.id,
                'short_description': short_desc,
            })

        elif r['type'] == 'standard':
            tpl = templates.get(r['template_key']) if r['template_key'] else None
            base_url = (tpl or {}).get('url', '')
            url = build_standard_change_url(base_url, {
                'short_description': short_desc,
                'assignment_group':  r['assignment_group'],
                'start_date':        r['start_date'],
                'end_date':          r['end_date'],
                'description':       r.get('description', ''),
                'risk':              r.get('risk', ''),
            })
            items.append({
                'row_index':         r['row_index'],
                'kind':              'standard',
                'url':               url,
                'template_label':    (tpl or {}).get('label', ''),
                'short_description': short_desc,
            })

    dispatched = [i for i in items if not i.get('error')]
    if dispatched:
        kinds_summary = {}
        for it in dispatched:
            k = it.get('kind', 'unknown')
            kinds_summary[k] = kinds_summary.get(k, 0) + 1
        detail = ' · '.join(f'{n} {k}' for k, n in kinds_summary.items())
        _push_activity(request,
                       type='bulk_submit',
                       title=f'Bulk-submitted {len(dispatched)} change{"s" if len(dispatched) != 1 else ""}',
                       detail=detail,
                       link='/servicenow/changes/bulk-create/',
                       severity='info')

    return JsonResponse({'items': items})


def bulk_change_template_save(request):
    """POST: create or update a standard change template URL."""
    from django.http import HttpResponse
    import re
    if request.method != 'POST':
        return HttpResponse(status=405)

    from .services.creation_templates import save_template

    key = request.POST.get('key', '').strip()
    label = request.POST.get('label', '').strip()
    url = request.POST.get('url', '').strip()

    errors = []
    if not key:
        errors.append('Key is required.')
    elif not re.match(r'^[a-z][a-z0-9_]*$', key):
        errors.append('Key must start with a letter; lowercase letters, digits, underscores only.')
    if not label:
        errors.append('Label is required.')
    if not url:
        errors.append('URL is required.')
    elif not (url.startswith('http://') or url.startswith('https://')):
        errors.append('URL must begin with http:// or https://')

    if errors:
        return render(request, 'servicenow/partials/bulk_change_template_errors.html',
                      {'errors': errors}, status=200)

    save_template(key, kind='standard_change', label=label, url=url)
    _push_activity(request,
                   type='template_saved',
                   title=f'Saved standard change template "{label or key}"',
                   detail=f'key: {key}',
                   link='/servicenow/changes/bulk-create/',
                   severity='success')
    # On success, retarget the response to the list so HTMX swaps the new list
    # into #template-list instead of the error slot the form points at.
    response = _render_template_list(request)
    response['HX-Retarget'] = '#template-list'
    response['HX-Reswap'] = 'innerHTML'
    return response


def bulk_change_template_delete(request):
    """POST: remove a standard change template URL."""
    from django.http import HttpResponse
    if request.method != 'POST':
        return HttpResponse(status=405)

    from .services.creation_templates import delete_template, load_templates_by_kind
    key = request.POST.get('key', '').strip()
    if key and key in load_templates_by_kind('standard_change'):
        delete_template(key)
        _push_activity(request,
                       type='template_deleted',
                       title=f'Deleted standard change template "{key}"',
                       link='/servicenow/changes/bulk-create/',
                       severity='warning')
    return _render_template_list(request)


# ─────────────────────────────────────────────────────────────
# Unified Creation Templates (all kinds)
# ─────────────────────────────────────────────────────────────

def creation_templates_page(request):
    """GET: full-page manager for all creation templates."""
    from .services.creation_templates import load_templates_grouped, KIND_LABELS, KIND_FIELDS, VALID_KINDS
    grouped = load_templates_grouped()
    sections = [(k, KIND_LABELS[k], grouped.get(k, {})) for k in VALID_KINDS]
    total = sum(len(e) for _, _, e in sections)
    return render(request, 'servicenow/templates_manage.html', {
        'sections':    sections,
        'total':       total,
        'kind_labels': KIND_LABELS,
        'kind_fields': KIND_FIELDS,
        'valid_kinds': VALID_KINDS,
    })


def _render_creation_template_list(request):
    from .services.creation_templates import load_templates_grouped, KIND_LABELS, VALID_KINDS
    grouped = load_templates_grouped()
    sections = [(k, KIND_LABELS[k], grouped.get(k, {})) for k in VALID_KINDS]
    total = sum(len(e) for _, _, e in sections)
    return render(request, 'servicenow/partials/creation_template_list.html', {
        'sections': sections,
        'total':    total,
    })


def creation_template_save(request):
    """POST: create or update any-kind template."""
    from django.http import HttpResponse
    from .services.creation_templates import save_template, VALID_KINDS, KIND_FIELDS
    import re
    if request.method != 'POST':
        return HttpResponse(status=405)

    key   = request.POST.get('key', '').strip()
    kind  = request.POST.get('kind', '').strip()
    label = request.POST.get('label', '').strip()
    url   = request.POST.get('url', '').strip()

    errors = []
    if not key:
        errors.append('Key is required.')
    elif not re.match(r'^[a-z][a-z0-9_]*$', key):
        errors.append('Key must start with a letter; lowercase letters, digits, underscores only.')
    if kind not in VALID_KINDS:
        errors.append(f'Kind must be one of: {", ".join(VALID_KINDS)}.')
    if not label:
        errors.append('Label is required.')

    if kind == 'standard_change':
        if not url:
            errors.append('URL is required for standard changes.')
        elif not (url.startswith('http://') or url.startswith('https://')):
            errors.append('URL must begin with http:// or https://')
        fields = {}
    else:
        allowed = KIND_FIELDS.get(kind, [])
        fields = {f: request.POST.get(f, '').strip() for f in allowed}

    if errors:
        return render(request, 'servicenow/partials/creation_template_errors.html',
                      {'errors': errors}, status=200)

    save_template(key, kind=kind, label=label, url=url, fields=fields)
    _push_activity(request,
                   type='template_saved',
                   title=f'Saved {kind.replace("_", " ")} template "{label or key}"',
                   detail=f'key: {key}',
                   link='/servicenow/templates/',
                   severity='success')
    response = _render_creation_template_list(request)
    response['HX-Retarget'] = '#creation-template-list'
    response['HX-Reswap'] = 'innerHTML'
    return response


def creation_template_delete(request):
    """POST: remove a template (any kind)."""
    from django.http import HttpResponse
    from .services.creation_templates import delete_template, load_templates
    if request.method != 'POST':
        return HttpResponse(status=405)
    key = request.POST.get('key', '').strip()
    if key and key in load_templates():
        delete_template(key)
        _push_activity(request,
                       type='template_deleted',
                       title=f'Deleted template "{key}"',
                       link='/servicenow/templates/',
                       severity='warning')
    return _render_creation_template_list(request)


def create_from_template_picker(request, kind: str):
    """
    GET: returns a partial listing templates of the given kind as a picker.
    Used by the "New from template" dropdown on list pages.
    """
    from django.http import HttpResponse
    from .services.creation_templates import load_templates_by_kind, VALID_KINDS
    if kind not in VALID_KINDS:
        return HttpResponse(status=404)
    return render(request, 'servicenow/partials/create_from_template_picker.html', {
        'kind':      kind,
        'templates': load_templates_by_kind(kind),
    })


def create_from_template_form(request, key: str):
    """
    GET: return an inline create form pre-filled from the named template.
    The form is swapped into the create-record modal.
    """
    from django.http import HttpResponse
    from .services.creation_templates import load_templates, KIND_FIELDS
    if request.method != 'GET':
        return HttpResponse(status=405)
    templates = load_templates()
    tpl = templates.get(key)
    if not tpl:
        return HttpResponse(status=404)
    kind = tpl.get('kind', 'standard_change')
    defaults = tpl.get('fields') or {}
    fields_with_values = [(f, defaults.get(f, '')) for f in KIND_FIELDS.get(kind, [])]
    return render(request, 'servicenow/partials/create_from_template_form.html', {
        'key':       key,
        'template':  tpl,
        'kind':      kind,
        'fields':    fields_with_values,
    })


def create_from_template_submit(request):
    """
    POST: submit the pre-filled form.
    For standard_change: return the target URL for the client to open in a popup.
    For normal_change/emergency_change: dispatch changes_create_task.
    For incident: dispatch incidents_create_task.
    Returns a result partial with a task id (or URL) the client can follow.
    """
    from django.http import HttpResponse
    from .services.creation_templates import load_templates, build_standard_change_url, KIND_FIELDS
    from .tasks import changes_create_task, incidents_create_task
    if request.method != 'POST':
        return HttpResponse(status=405)

    key = request.POST.get('template_key', '').strip()
    tpl = load_templates().get(key) if key else None
    if not tpl:
        return render(request, 'servicenow/partials/create_from_template_result.html', {
            'error': 'Template not found.',
        }, status=200)

    kind = tpl.get('kind')
    allowed = KIND_FIELDS.get(kind, [])
    fields = {f: request.POST.get(f, '').strip() for f in allowed if request.POST.get(f, '').strip()}

    if not fields.get('short_description'):
        return render(request, 'servicenow/partials/create_from_template_result.html', {
            'error': 'short_description is required.',
            'kind':  kind,
        }, status=200)

    label = tpl.get('label', '')
    desc = fields.get('short_description', '')

    if kind == 'standard_change':
        target = build_standard_change_url(tpl.get('url', ''), fields)
        _push_activity(request,
                       type='template_used',
                       title=f'Opened standard change from "{label or key}"',
                       detail=desc,
                       link=target,
                       severity='info')
        return render(request, 'servicenow/partials/create_from_template_result.html', {
            'kind':    kind,
            'url':     target,
            'label':   label,
        }, status=200)

    if kind in ('normal_change', 'emergency_change'):
        task = changes_create_task.delay({
            'kind':   'emergency' if kind == 'emergency_change' else 'normal',
            'fields': fields,
        })
        _push_activity(request,
                       type='template_used',
                       title=f'Dispatched {kind.replace("_", " ")} from "{label or key}"',
                       detail=desc,
                       severity='info')
        return render(request, 'servicenow/partials/create_from_template_result.html', {
            'kind':    kind,
            'task_id': task.id,
            'label':   label,
        }, status=200)

    if kind == 'incident':
        task = incidents_create_task.delay({'fields': fields})
        _push_activity(request,
                       type='template_used',
                       title=f'Dispatched incident from "{label or key}"',
                       detail=desc,
                       severity='info')
        return render(request, 'servicenow/partials/create_from_template_result.html', {
            'kind':    kind,
            'task_id': task.id,
            'label':   label,
        }, status=200)

    return render(request, 'servicenow/partials/create_from_template_result.html', {
        'error': f'Unknown template kind: {kind}',
    }, status=200)


def record_lookup(request):
    incident_results = []
    change_results = []
    incident_not_found = []
    change_not_found = []
    unrecognised = []
    numbers_input = ''
    searched = False
    live_incident_task_id = ''
    live_change_task_id = ''
    live_incident_extras = ''
    live_change_extras = ''

    if request.method == 'POST':
        searched = True
        numbers_input = request.POST.get('numbers', '')
        parsed = _parse_numbers(numbers_input)
        inc_numbers = [n for n in parsed if n.startswith('INC')]
        chg_numbers = [n for n in parsed if n.startswith('CHG')]
        unrecognised = [n for n in parsed if not (n.startswith('INC') or n.startswith('CHG'))]

        if _is_live(request):
            # Dispatch bulk tasks; the poll endpoint renders each section when ready.
            from .tasks import incident_bulk_get_by_field_task, changes_bulk_get_by_number_task
            if inc_numbers:
                task = incident_bulk_get_by_field_task.delay({
                    'field':         'number',
                    'values':        inc_numbers,
                    'display_value': True,
                })
                live_incident_task_id = task.id
                live_incident_extras = f"numbers={','.join(inc_numbers)}"
            if chg_numbers:
                task = changes_bulk_get_by_number_task.delay({
                    'numbers':       chg_numbers,
                    'display_value': True,
                })
                live_change_task_id = task.id
                live_change_extras = f"numbers={','.join(chg_numbers)}"
        else:
            # Demo path — synchronous lookup
            for num in inc_numbers:
                rec = _get_incident(num)
                if rec:
                    incident_results.append(rec)
                else:
                    incident_not_found.append(num)
            for num in chg_numbers:
                rec = _get_change(num)
                if rec:
                    change_results.append(dict(rec))
                else:
                    change_not_found.append(num)
            _annotate_ctask_pct(change_results)

    total_found = len(incident_results) + len(change_results)
    ctx = {
        'incident_results':        incident_results,
        'change_results':          change_results,
        'incident_not_found':      incident_not_found,
        'change_not_found':        change_not_found,
        'unrecognised':            unrecognised,
        'numbers_input':           numbers_input,
        'searched':                searched,
        'live_incident_task_id':   live_incident_task_id,
        'live_change_task_id':     live_change_task_id,
        'live_incident_extras':    live_incident_extras,
        'live_change_extras':      live_change_extras,
        'total_found': total_found,
    }
    # HTMX partial swap — only for form POSTs, not hx-boost GET navigations
    if request.method == 'POST' and request.headers.get('HX-Request'):
        return render(request, 'servicenow/partials/lookup_results.html', ctx)
    return render(request, 'servicenow/lookup.html', ctx)

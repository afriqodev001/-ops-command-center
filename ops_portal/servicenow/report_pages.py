"""
HTTP endpoints for the ServiceNow Reports feature.

A Report is a saved, named ServiceNow query plus a set of actions. This
gives engineers a focused alternative to the busy Presets page: pick or
create a report, run it, then act on the rows (view / CSV / email / AI
summary).

Run + AI-summary use the dispatch-then-poll pattern (mirrors
change_intake_pages.py): POST kicks off a Celery task, a GET poll endpoint
swaps in either a polling partial or the final result partial.
"""
from __future__ import annotations

import json

from celery.result import AsyncResult
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from servicenow.models import (
    Report,
    REPORT_ACTION_CHOICES, REPORT_ACTION_VALUES,
    REPORT_DOMAIN_CHOICES, REPORT_DOMAIN_VALUES, REPORT_DOMAIN_TABLE,
)


# Sensible starting column set per domain — prefilled so creating a report
# is mostly just a name + query.
DEFAULT_FIELDS = {
    'incident': ('number,short_description,state,priority,'
                 'assignment_group,assigned_to,sys_updated_on'),
    'change':   ('number,short_description,state,risk,'
                 'assignment_group,assigned_to,start_date,end_date'),
}

_DOMAIN_LABELS = dict(REPORT_DOMAIN_CHOICES)

HEADER_LABELS = {
    'number': 'Number', 'short_description': 'Description', 'priority': 'Priority',
    'state': 'State', 'assignment_group': 'Group', 'assigned_to': 'Assignee',
    'opened_at': 'Opened', 'sys_updated_on': 'Updated', 'sla_due': 'SLA Due',
    'start_date': 'Start', 'end_date': 'End', 'risk': 'Risk', 'type': 'Type',
    'cmdb_ci': 'CI', 'category': 'Category', 'sys_id': 'Sys ID',
}


# ── helpers ─────────────────────────────────────────────────────

def _dv(val):
    """ServiceNow display value — reference fields come back as dicts."""
    if isinstance(val, dict):
        return val.get('display_value') or val.get('value') or ''
    return val if val is not None else ''


def _unwrap_rows(result) -> list:
    """Pull the record list out of a reports_run_task result."""
    if not isinstance(result, dict):
        return []
    inner = result.get('result')
    if isinstance(inner, list):
        return inner
    if isinstance(inner, dict) and isinstance(inner.get('result'), list):
        return inner['result']
    return []


def _unique_slug(name: str) -> str:
    base = slugify(name)[:110] or 'report'
    slug, i = base, 2
    while Report.objects.filter(slug=slug).exists():
        slug = f'{base}-{i}'
        i += 1
    return slug


def _shape_result(report: Report, raw_rows: list) -> dict:
    """Build the display_cols + rows structure report_result.html expects."""
    cols = report.field_list()
    if not cols and raw_rows:
        cols = [k for k in raw_rows[0].keys()]
    display_cols = [
        (c, HEADER_LABELS.get(c, c.replace('_', ' ').title()))
        for c in cols if c != 'sys_id'
    ]
    rows = []
    for rec in raw_rows:
        cells = []
        for col, _label in display_cols:
            cells.append({
                'col': col,
                'val': _dv(rec.get(col)) or '—',
                'number_val': _dv(rec.get('number')) if col == 'number' else '',
            })
        rows.append(cells)
    return {
        'report': report,
        'display_cols': display_cols,
        'rows': rows,
        'total': len(rows),
        'report_actions': report.actions(),
    }


def _form_from_post(request) -> dict:
    return {
        'slug': request.POST.get('slug', '').strip(),
        'name': request.POST.get('name', '').strip(),
        'description': request.POST.get('description', '').strip(),
        'domain': request.POST.get('domain', '').strip(),
        'query': request.POST.get('query', '').strip(),
        'fields': request.POST.get('fields', '').strip(),
        'row_limit': request.POST.get('row_limit', '').strip(),
        'email_recipients': request.POST.get('email_recipients', '').strip(),
        'email_body': request.POST.get('email_body', '').strip(),
    }


def _form_from_report(report: Report) -> dict:
    return {
        'slug': report.slug,
        'name': report.name,
        'description': report.description,
        'domain': report.domain,
        'query': report.query,
        'fields': report.fields,
        'row_limit': str(report.row_limit),
        'email_recipients': report.email_recipients,
        'email_body': report.email_body,
    }


# ── 1. Landing — list reports ───────────────────────────────────

@require_GET
def reports_landing(request):
    """GET /servicenow/reports/ — saved reports, split by domain."""
    return render(request, 'servicenow/reports.html', {
        'change_reports': Report.objects.filter(domain='change'),
        'incident_reports': Report.objects.filter(domain='incident'),
    })


# ── 2. Create / edit form ───────────────────────────────────────

@require_GET
def report_new(request):
    """GET /servicenow/reports/new/?domain=change|incident"""
    domain = request.GET.get('domain', '').strip()
    if domain not in REPORT_DOMAIN_VALUES:
        domain = 'incident'
    return render(request, 'servicenow/report_form.html', {
        'form': {
            'slug': '', 'name': '', 'description': '',
            'domain': domain, 'query': '',
            'fields': DEFAULT_FIELDS[domain], 'row_limit': '100',
            'email_recipients': '', 'email_body': '',
        },
        'selected_actions': ['view'],
        'action_choices': REPORT_ACTION_CHOICES,
        'domain_table': REPORT_DOMAIN_TABLE[domain],
        'domain_label': _DOMAIN_LABELS[domain],
        'errors': [],
        'is_edit': False,
    })


@require_GET
def report_edit(request, slug: str):
    """GET /servicenow/reports/<slug>/edit/"""
    report = get_object_or_404(Report, slug=slug)
    return render(request, 'servicenow/report_form.html', {
        'form': _form_from_report(report),
        'selected_actions': report.actions(),
        'action_choices': REPORT_ACTION_CHOICES,
        'domain_table': REPORT_DOMAIN_TABLE.get(report.domain, report.table),
        'domain_label': report.domain_label(),
        'errors': [],
        'is_edit': True,
    })


@csrf_exempt
@require_POST
def report_save(request):
    """POST /servicenow/reports/save/ — create or update a report."""
    form = _form_from_post(request)
    selected_actions = [a for a in request.POST.getlist('actions')
                        if a in REPORT_ACTION_VALUES]
    domain = form['domain'] if form['domain'] in REPORT_DOMAIN_VALUES else 'incident'

    errors = []
    if not form['name']:
        errors.append('Report name is required.')
    if not form['query']:
        errors.append('ServiceNow query is required.')
    try:
        row_limit = max(1, min(10000, int(form['row_limit'] or 100)))
    except ValueError:
        row_limit = 100

    if errors:
        return render(request, 'servicenow/report_form.html', {
            'form': form,
            'selected_actions': selected_actions or ['view'],
            'action_choices': REPORT_ACTION_CHOICES,
            'domain_table': REPORT_DOMAIN_TABLE[domain],
            'domain_label': _DOMAIN_LABELS[domain],
            'errors': errors,
            'is_edit': bool(form['slug']),
        }, status=200)

    if form['slug']:
        report = get_object_or_404(Report, slug=form['slug'])
    else:
        report = Report(slug=_unique_slug(form['name']))

    report.name = form['name']
    report.description = form['description']
    report.domain = domain
    report.table = REPORT_DOMAIN_TABLE[domain]
    report.query = form['query']
    report.fields = form['fields'] or DEFAULT_FIELDS[domain]
    report.row_limit = row_limit
    report.actions_json = json.dumps(selected_actions or ['view'])
    report.email_recipients = form['email_recipients']
    report.email_body = form['email_body']
    report.save()

    return HttpResponseRedirect(f'/servicenow/reports/{report.slug}/')


@csrf_exempt
@require_POST
def report_delete(request, slug: str):
    """POST /servicenow/reports/<slug>/delete/"""
    get_object_or_404(Report, slug=slug).delete()
    return HttpResponseRedirect('/servicenow/reports/')


# ── 3. Report detail / run page ─────────────────────────────────

@require_GET
def report_detail(request, slug: str):
    """GET /servicenow/reports/<slug>/ — run page."""
    report = get_object_or_404(Report, slug=slug)
    return render(request, 'servicenow/report_detail.html', {
        'report': report,
        'report_actions': report.actions(),
    })


@csrf_exempt
@require_POST
def report_run(request, slug: str):
    """POST /servicenow/reports/<slug>/run/ — dispatch the query task."""
    report = get_object_or_404(Report, slug=slug)
    from .report_tasks import reports_run_task
    task = reports_run_task.delay({'report_id': report.pk})
    return render(request, 'servicenow/partials/report_run_polling.html', {
        'report': report,
        'task_id': task.id,
    })


@require_GET
def report_run_poll(request, slug: str, task_id: str):
    """GET /servicenow/reports/<slug>/run/poll/<task_id>/"""
    report = get_object_or_404(Report, slug=slug)
    ar = AsyncResult(task_id)

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'servicenow/partials/report_run_polling.html', {
            'report': report,
            'task_id': task_id,
        })

    if ar.state == 'FAILURE':
        return render(request, 'servicenow/partials/report_result.html', {
            'report': report,
            'error': f'Report task failed: {ar.result}',
        })

    result = ar.result or {}
    if isinstance(result, dict) and result.get('error'):
        detail = result.get('detail') or result.get('error')
        return render(request, 'servicenow/partials/report_result.html', {
            'report': report,
            'error': f'ServiceNow query failed: {detail}',
        })

    ctx = _shape_result(report, _unwrap_rows(result))
    return render(request, 'servicenow/partials/report_result.html', ctx)


# ── 4. AI summary action ────────────────────────────────────────

@csrf_exempt
@require_POST
def report_ai_summary(request, slug: str):
    """POST /servicenow/reports/<slug>/ai-summary/ — body has the rendered
    rows as CSV text; preflight the AI provider, then dispatch the task."""
    report = get_object_or_404(Report, slug=slug)

    from .services.ai_assist import ai_preflight
    pf = ai_preflight()
    if not pf.get('ok'):
        return render(request, 'servicenow/partials/report_ai_summary.html', {
            'report': report,
            'error': pf.get('error'),
            'action_url': pf.get('action_url'),
            'action_label': pf.get('action_label'),
        })

    csv_text = request.POST.get('csv', '')
    from .report_tasks import reports_ai_summary_task
    task = reports_ai_summary_task.delay({
        'csv': csv_text,
        'report_name': report.name,
    })
    return render(request, 'servicenow/partials/report_ai_summary_polling.html', {
        'report': report,
        'task_id': task.id,
    })


@require_GET
def report_ai_summary_poll(request, slug: str, task_id: str):
    """GET /servicenow/reports/<slug>/ai-summary/poll/<task_id>/"""
    report = get_object_or_404(Report, slug=slug)
    ar = AsyncResult(task_id)

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'servicenow/partials/report_ai_summary_polling.html', {
            'report': report,
            'task_id': task_id,
        })

    if ar.state == 'FAILURE':
        return render(request, 'servicenow/partials/report_ai_summary.html', {
            'report': report,
            'error': f'AI summary task failed: {ar.result}',
        })

    result = ar.result or {}
    if isinstance(result, dict) and result.get('error'):
        return render(request, 'servicenow/partials/report_ai_summary.html', {
            'report': report,
            'error': result.get('detail') or result.get('error'),
        })

    return render(request, 'servicenow/partials/report_ai_summary.html', {
        'report': report,
        'summary': (result or {}).get('summary', ''),
    })

"""
Oncall change-review UI — HTMX views + page handlers.

Endpoints under /servicenow/oncall/.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from celery.result import AsyncResult
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone as dj_tz
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import (
    OncallChangeReview,
    ONCALL_STAGES,
    ONCALL_STAGE_VALUES,
    AI_VERDICT_CHOICES,
)
from .services import suppression_matrix as matrix
from .services import notification_templates as ntpl
from .services import oncall_banner as banner
from .services import oncall_review as orsvc
from .services import outlook
from .services.ai_assist import ai_preflight
from .services.query_presets import get_all_presets


# ─── Helpers ──────────────────────────────────────────────

ONCALL_PRESET_PREFIX = 'oncall_'


def _oncall_presets():
    """All change presets whose key starts with `oncall_` (built-in + user)."""
    out = []
    for name, cfg in get_all_presets().items():
        if not name.startswith(ONCALL_PRESET_PREFIX):
            continue
        if cfg.get('domain') != 'change':
            continue
        out.append({
            'name': name,
            'description': cfg.get('description', ''),
            'is_user_defined': bool(cfg.get('is_user_defined')),
        })
    out.sort(key=lambda x: x['name'])
    return out


def _window_bounds(preset_name: str) -> Dict[str, datetime]:
    """Approximate window_start/end for the preset name we're pulling.

    These are computed locally (UTC, naive-week bounds) just for indexing
    OncallChangeReview rows; the real ServiceNow filter is server-side
    via gs.beginningOf*() in the preset query string.
    """
    now = dj_tz.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if preset_name == 'oncall_changes_today':
        return {
            'window_start': today,
            'window_end': today + timedelta(days=1),
            'label': 'today',
        }
    if preset_name == 'oncall_changes_this_month':
        first = today.replace(day=1)
        # cheap month-end: jump 32 days then back to day 1
        nxt = (first + timedelta(days=32)).replace(day=1)
        return {'window_start': first, 'window_end': nxt, 'label': 'this_month'}
    # default: this week (Mon=start, +7 days)
    monday = today - timedelta(days=today.weekday())
    return {
        'window_start': monday,
        'window_end': monday + timedelta(days=7),
        'label': 'this_week',
    }


def _user_name(request) -> str:
    try:
        return request.user.username if getattr(request.user, 'is_authenticated', False) else ''
    except Exception:
        pass
    try:
        from core.context_processors import _os_user_name
        return _os_user_name()
    except Exception:
        return ''


# ─── Full page handlers ───────────────────────────────────

def oncall_dashboard(request):
    """Outage Triage queue — pulls + reviews scoped to outage_triage / both."""
    from django.db.models import Q
    return render(request, 'servicenow/oncall.html', {
        'presets': _oncall_presets(),
        'default_preset': 'oncall_changes_this_week',
        'default_purpose': 'outage_triage',
        'recent_reviews': OncallChangeReview.objects
            .filter(Q(pull_purpose='outage_triage') | Q(pull_purpose='both'))
            .order_by('-updated_at')[:25],
        'matrix_meta': matrix.matrix_meta(),
    })


def oncall_approvals_page(request):
    """CR Approval queue — pulls + reviews scoped to cr_approval / both."""
    from django.db.models import Q

    qs = (
        OncallChangeReview.objects
        .filter(Q(pull_purpose='cr_approval') | Q(pull_purpose='both'))
        .order_by('cr_approval_status', '-updated_at')[:50]
    )
    reviews = list(qs)

    # Attach outstanding count to each review object (template-friendly)
    for r in reviews:
        r.outstanding = orsvc.approval_outstanding_count(r)

    summary = {
        'total': len(reviews),
        'awaiting': sum(1 for r in reviews if r.cr_approval_status == 'awaiting_requestor'),
        'ready':    sum(1 for r in reviews if r.cr_approval_status == 'ready_to_approve'),
        'approved': sum(1 for r in reviews if r.cr_approval_status == 'approved'),
        'in_review':sum(1 for r in reviews if r.cr_approval_status == 'in_review'),
    }

    return render(request, 'servicenow/oncall_approvals.html', {
        'presets': _oncall_presets(),
        'default_preset': 'oncall_changes_next_week',
        'default_purpose': 'cr_approval',
        'reviews': reviews,
        'summary': summary,
        'matrix_meta': matrix.matrix_meta(),
    })


def oncall_matrix_page(request):
    rows = matrix.load_matrix()
    return render(request, 'servicenow/oncall_matrix.html', {
        'rows': rows,
        'meta': matrix.matrix_meta(),
        'columns': matrix.canonical_columns(),
    })


def oncall_templates_page(request):
    return render(request, 'servicenow/oncall_templates.html', {
        'templates': ntpl.list_templates(),
    })


def oncall_history_page(request):
    return render(request, 'servicenow/oncall_history.html', {
        'stages': ONCALL_STAGES,
        'verdicts': AI_VERDICT_CHOICES,
    })


def oncall_review_detail(request, change_number: str):
    review = get_object_or_404(OncallChangeReview, change_number=change_number)
    matched = matrix.lookup({
        'cmdb_ci': review.cmdb_ci,
        'short_description': review.short_description,
    })
    ai_payload = {}
    if review.ai_payload_json:
        try:
            ai_payload = json.loads(review.ai_payload_json)
        except Exception:
            ai_payload = {}
    return render(request, 'servicenow/oncall_review_detail.html', {
        'review': review,
        'matched': matched,
        'ai_payload': ai_payload,
        'content_summary_payload': orsvc.get_content_summary_payload(review),
        'checklist_items': orsvc.load_checklist(review),
        'checklist_progress': orsvc.checklist_progress(review),
        'feedback_items': orsvc.load_approval_feedback(review),
        'outstanding_count': orsvc.approval_outstanding_count(review),
        'templates': ntpl.list_templates(),
    })


# ─── Pull changes (HTMX) ──────────────────────────────────

@csrf_exempt
@require_POST
def oncall_pull_changes(request):
    purpose = (request.POST.get('pull_purpose') or 'outage_triage').strip()
    if purpose not in ('outage_triage', 'cr_approval'):
        purpose = 'outage_triage'

    # Mode A: explicit list of change numbers (most common for CR approvals —
    # requestors ping the engineer to review CHG-X). Takes priority over preset.
    raw_numbers = (request.POST.get('change_numbers') or '').strip()
    if raw_numbers:
        import re
        numbers = [n.strip().upper() for n in re.split(r'[\s,;]+', raw_numbers) if n.strip()]
        seen = set()
        deduped = []
        for n in numbers:
            if n not in seen:
                seen.add(n)
                deduped.append(n)

        if not deduped:
            return render(request, 'servicenow/partials/oncall_error.html', {
                'error': 'Paste at least one change number.',
            })

        from .tasks import changes_bulk_get_by_number_task
        task = changes_bulk_get_by_number_task.delay({
            'numbers': deduped,
            'fields': 'number,short_description,state,assignment_group,assigned_to,start_date,end_date,risk,type,cmdb_ci,sys_id',
            'display_value': 'all',
        })

        return render(request, 'servicenow/partials/oncall_pull_polling.html', {
            'task_id': task.id,
            'preset': '',
            'change_numbers': ','.join(deduped),
            'pull_purpose': purpose,
            'window_label': f'{len(deduped)} hand-picked change{"s" if len(deduped) != 1 else ""}',
        })

    # Mode B: time-window preset
    preset = (request.POST.get('preset') or '').strip()
    if not preset:
        preset = 'oncall_changes_next_week' if purpose == 'cr_approval' else 'oncall_changes_this_week'

    win = _window_bounds(preset)

    from .tasks import presets_run_task
    task = presets_run_task.delay({
        'preset': preset,
        'params': {},
    })

    return render(request, 'servicenow/partials/oncall_pull_polling.html', {
        'task_id': task.id,
        'preset': preset,
        'pull_purpose': purpose,
        'window_label': win['label'],
    })


def oncall_pull_poll(request, task_id: str):
    preset = request.GET.get('preset', '')
    purpose = (request.GET.get('pull_purpose') or 'outage_triage').strip()
    change_numbers_raw = (request.GET.get('change_numbers') or '').strip()
    if purpose not in ('outage_triage', 'cr_approval'):
        purpose = 'outage_triage'

    # Decide window bounds based on which mode this poll came from.
    # By-numbers mode pins the row to "now"; the window range is just an
    # index — actual scheduled_start on the row comes from the change record.
    if change_numbers_raw:
        from datetime import timedelta
        now = dj_tz.now()
        win = {
            'window_start': now,
            'window_end': now + timedelta(seconds=1),
            'label': f'{len(change_numbers_raw.split(","))} hand-picked',
        }
    else:
        if not preset:
            preset = 'oncall_changes_next_week' if purpose == 'cr_approval' else 'oncall_changes_this_week'
        win = _window_bounds(preset)
    ar = AsyncResult(task_id)

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'servicenow/partials/oncall_pull_polling.html', {
            'task_id': task_id,
            'preset': preset,
            'change_numbers': change_numbers_raw,
            'pull_purpose': purpose,
            'window_label': win['label'],
        })

    if ar.state == 'FAILURE':
        return render(request, 'servicenow/partials/oncall_error.html', {
            'error': str(ar.result),
        })

    result = ar.result or {}
    if isinstance(result, dict) and result.get('error'):
        return render(request, 'servicenow/partials/oncall_error.html', {
            'error': result.get('detail') or result.get('error'),
        })

    rows = []
    if isinstance(result, dict) and isinstance(result.get('result'), list):
        rows = result['result']
    elif isinstance(result, list):
        rows = result

    # Detect missing change numbers (by-numbers mode only)
    not_found = []
    if change_numbers_raw:
        def _num(row):
            n = (row or {}).get('number') if isinstance(row, dict) else None
            if isinstance(n, dict):
                n = n.get('display_value') or n.get('value') or ''
            return str(n or '').strip().upper()
        requested = [n for n in change_numbers_raw.split(',') if n]
        present = {_num(r) for r in rows}
        not_found = [n for n in requested if n.upper() not in present]

    reviews = orsvc.upsert_pulled_changes(
        rows,
        window_start=win['window_start'],
        window_end=win['window_end'],
        window_label=win['label'],
        pull_purpose=purpose,
    )

    return render(request, 'servicenow/partials/oncall_pull_results.html', {
        'reviews': reviews,
        'preset': preset,
        'change_numbers': change_numbers_raw,
        'not_found': not_found,
        'pull_purpose': purpose,
        'window_label': win['label'],
        'pulled_count': len(reviews),
    })


# ─── AI review (HTMX) ─────────────────────────────────────

@csrf_exempt
@require_POST
def oncall_run_ai_for_change(request, change_number: str):
    pre = ai_preflight()
    if not pre.get('ok'):
        return render(request, 'servicenow/partials/oncall_error.html', {
            'error': pre.get('error'),
            'action_url': pre.get('action_url'),
            'action_label': pre.get('action_label'),
        })

    review = get_object_or_404(OncallChangeReview, change_number=change_number)

    from .tasks import oncall_run_ai_batch_task
    task = oncall_run_ai_batch_task.delay({
        'change_numbers': [change_number],
        'force': bool(request.POST.get('force')),
    })

    return render(request, 'servicenow/partials/oncall_ai_polling.html', {
        'task_id': task.id,
        'change_number': change_number,
        'mode': 'single',
    })


@csrf_exempt
@require_POST
def oncall_run_ai_batch(request):
    pre = ai_preflight()
    if not pre.get('ok'):
        return render(request, 'servicenow/partials/oncall_error.html', {
            'error': pre.get('error'),
            'action_url': pre.get('action_url'),
            'action_label': pre.get('action_label'),
        })

    raw = request.POST.get('change_numbers', '').strip()
    numbers = [n.strip() for n in raw.replace(',', '\n').splitlines() if n.strip()]
    if not numbers:
        # fall back: all "pulled" reviews under the most recent window
        latest = OncallChangeReview.objects.order_by('-window_end').first()
        if latest:
            numbers = list(
                OncallChangeReview.objects
                .filter(window_start=latest.window_start, window_end=latest.window_end)
                .values_list('change_number', flat=True)
            )

    if not numbers:
        return render(request, 'servicenow/partials/oncall_error.html', {
            'error': 'No changes selected. Pull a window first or pick rows.',
        })

    from .tasks import oncall_run_ai_batch_task
    task = oncall_run_ai_batch_task.delay({
        'change_numbers': numbers,
        'force': bool(request.POST.get('force')),
    })

    return render(request, 'servicenow/partials/oncall_ai_polling.html', {
        'task_id': task.id,
        'change_number': '',
        'mode': 'batch',
        'pending_count': len(numbers),
    })


def oncall_poll_ai(request, task_id: str):
    ar = AsyncResult(task_id)
    change_number = request.GET.get('change_number', '').strip()
    mode = request.GET.get('mode', 'single')

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'servicenow/partials/oncall_ai_polling.html', {
            'task_id': task_id,
            'change_number': change_number,
            'mode': mode,
        })

    if ar.state == 'FAILURE':
        return render(request, 'servicenow/partials/oncall_error.html', {
            'error': str(ar.result),
        })

    result = ar.result or {}

    # Re-fetch the (possibly multiple) reviews from DB now that the task wrote them
    if mode == 'single' and change_number:
        reviews = list(OncallChangeReview.objects.filter(change_number=change_number))
    else:
        ok_numbers = (result or {}).get('ok') or []
        err_numbers = [e.get('change_number') for e in (result or {}).get('errors') or []]
        nums = ok_numbers + err_numbers
        reviews = list(OncallChangeReview.objects.filter(change_number__in=nums))

    return render(request, 'servicenow/partials/oncall_ai_results.html', {
        'reviews': reviews,
        'result': result,
        'mode': mode,
    })


# ─── Stage actions ────────────────────────────────────────

@csrf_exempt
@require_POST
def oncall_mark_stage(request, change_number: str):
    review = get_object_or_404(OncallChangeReview, change_number=change_number)
    target = request.POST.get('stage', '').strip()
    comments = request.POST.get('comments', None)

    if target and target in ONCALL_STAGE_VALUES:
        orsvc.advance_stage(review, target, by=_user_name(request))
    if comments is not None:
        review.comments = comments.strip()
        review.save(update_fields=['comments', 'updated_at'])

    return render(request, 'servicenow/partials/oncall_review_summary.html', {
        'oncall_review': review,
    })


# ─── Email draft ─────────────────────────────────────────

@csrf_exempt
@require_POST
def oncall_draft_email(request, change_number: str):
    review = get_object_or_404(OncallChangeReview, change_number=change_number)
    template_name = request.POST.get('template', 'outage_notification')

    matched = matrix.lookup({
        'cmdb_ci': review.cmdb_ci,
        'short_description': review.short_description,
    }) or {}

    if matched:
        recipients_list = matrix.all_recipients_for(matched)
        impact = matrix.impact_text_for(matched)
        application = matched.get('application') or ''
    else:
        recipients_list = [
            e.strip() for e in (review.matched_emails or '').split(';') if e.strip()
        ]
        impact = review.matched_impact or ''
        application = review.matched_app or ''

    rendered = ntpl.render_template(template_name, {
        'change_number': review.change_number,
        'short_description': review.short_description,
        'risk': review.risk,
        'assignment_group': review.assignment_group,
        'scheduled_start': review.scheduled_start.strftime('%Y-%m-%d %H:%M UTC') if review.scheduled_start else 'TBD',
        'scheduled_end': review.scheduled_end.strftime('%Y-%m-%d %H:%M UTC') if review.scheduled_end else 'TBD',
        'application': application or '(no matrix entry)',
        'impact': impact or '(no impact details on file)',
        'recipients_list': recipients_list,
    })

    result = outlook.open_draft(
        recipients='; '.join(recipients_list),
        subject=rendered['subject'],
        body=rendered['body'],
    )

    if result.get('ok'):
        orsvc.advance_stage(review, 'comms_drafted', by=_user_name(request))
        return render(request, 'servicenow/partials/oncall_action_result.html', {
            'review': review,
            'message': 'Outlook draft opened. Review and send manually.',
            'severity': 'ok',
        })
    return render(request, 'servicenow/partials/oncall_action_result.html', {
        'review': review,
        'message': result.get('error', 'Outlook draft failed'),
        'severity': 'danger',
    })


# ─── Suppression matrix UI ───────────────────────────────

@csrf_exempt
@require_POST
def oncall_matrix_upload(request):
    upload = request.FILES.get('file')
    if not upload:
        return render(request, 'servicenow/partials/oncall_matrix_preview.html', {
            'error': 'No file selected.',
        })

    try:
        rows = matrix.parse_upload(upload, filename=upload.name or '')
    except ValueError as e:
        return render(request, 'servicenow/partials/oncall_matrix_preview.html', {
            'error': str(e),
        })

    return render(request, 'servicenow/partials/oncall_matrix_preview.html', {
        'preview_rows': rows,
        'rows_json': json.dumps(rows, default=str),
        'columns': matrix.canonical_columns(),
        'count': len(rows),
        'source': 'parser',
    })


@csrf_exempt
@require_POST
def oncall_matrix_ai_format(request):
    """
    Take an uploaded CSV / text file with potentially-messy headers and use
    the LLM to extract canonical rows. Useful when the source spreadsheet
    doesn't quite match the expected schema and the engineer doesn't want
    to clean it up by hand.
    """
    pre = ai_preflight()
    if not pre.get('ok'):
        return render(request, 'servicenow/partials/oncall_matrix_preview.html', {
            'error': pre.get('error') + ' (AI format requires Tachyon)',
        })

    upload = request.FILES.get('file')
    if not upload:
        return render(request, 'servicenow/partials/oncall_matrix_preview.html', {
            'error': 'No file selected.',
        })

    raw = upload.read()
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8-sig', errors='replace')

    # Cap raw input to keep prompt size reasonable for inline LLM call
    snippet = raw[:30000]
    if len(raw) > 30000:
        snippet += "\n\n[... truncated ...]"

    from .services.ai_assist import _call_llm, _extract_json_dict
    from .services.prompt_store import get_prompt

    system = get_prompt('oncall_matrix_format')
    user_prompt = (
        "Here is the source data — extract canonical rows and return "
        "{\"rows\": [...]}.\n\n"
        f"FILENAME: {upload.name}\n\n"
        f"CONTENT:\n{snippet}"
    )

    try:
        raw_response = _call_llm(system, user_prompt) or ''
    except Exception as e:
        return render(request, 'servicenow/partials/oncall_matrix_preview.html', {
            'error': f'AI call failed: {e}',
        })

    parsed = _extract_json_dict(raw_response) or {}
    if parsed.get('_ai_error'):
        return render(request, 'servicenow/partials/oncall_matrix_preview.html', {
            'error': f"AI: {parsed['_ai_error']}",
        })

    rows = parsed.get('rows') or parsed.get('matrix') or []
    if not isinstance(rows, list) or not rows:
        return render(request, 'servicenow/partials/oncall_matrix_preview.html', {
            'error': 'AI did not return any usable rows. Try the plain Preview button instead.',
            'ai_raw': (raw_response or '')[:1000],
        })

    # Run the AI output through our own normaliser so it lands in canonical shape
    normalised = [matrix._normalise_row(r, source='ai') for r in rows if isinstance(r, dict)]

    return render(request, 'servicenow/partials/oncall_matrix_preview.html', {
        'preview_rows': normalised,
        'rows_json': json.dumps(normalised, default=str),
        'columns': matrix.canonical_columns(),
        'count': len(normalised),
        'source': 'ai',
    })


@csrf_exempt
@require_POST
def oncall_matrix_apply(request):
    raw = request.POST.get('rows_json', '[]')
    try:
        rows = json.loads(raw)
    except Exception:
        rows = []
    if not isinstance(rows, list):
        rows = []
    matrix.save_matrix(rows)
    return render(request, 'servicenow/partials/oncall_matrix_table.html', {
        'rows': matrix.load_matrix(),
        'meta': matrix.matrix_meta(),
        'columns': matrix.canonical_columns(),
        'just_applied': True,
        'applied_count': len(rows),
    })


@csrf_exempt
@require_POST
def oncall_matrix_clear(request):
    matrix.clear_matrix()
    return render(request, 'servicenow/partials/oncall_matrix_table.html', {
        'rows': [],
        'meta': matrix.matrix_meta(),
        'columns': matrix.canonical_columns(),
    })


# ─── Single-row CRUD (form-driven editor) ─────────────────

def oncall_matrix_row_editor(request):
    """GET — return the editor partial. ?ci=... to edit, omit to create."""
    ci = (request.GET.get('ci') or '').strip()
    row = matrix.get_row(ci) if ci else None
    return render(request, 'servicenow/partials/oncall_matrix_row_editor.html', {
        'row': row,
        'is_new': row is None,
        'row_json': json.dumps(row, default=str) if row else 'null',
    })


@csrf_exempt
@require_POST
def oncall_matrix_row_save(request):
    """POST — upsert a single row from the form."""
    # Multi-entry outage_impact comes in as parallel arrays:
    apps = request.POST.getlist('impact_app[]')
    descs = request.POST.getlist('impact_description[]')
    extra_emails = request.POST.getlist('impact_additional_emails[]')
    impact_entries = []
    for i in range(max(len(apps), len(descs), len(extra_emails))):
        app = (apps[i] if i < len(apps) else '').strip()
        desc = (descs[i] if i < len(descs) else '').strip()
        emails_raw = (extra_emails[i] if i < len(extra_emails) else '').strip()
        emails = [e.strip() for e in emails_raw.replace(',', ';').split(';') if e.strip()]
        if app or desc or emails:
            impact_entries.append({
                'app': app,
                'description': desc,
                'additional_emails': emails,
            })

    payload = {
        'application': request.POST.get('application', ''),
        'ci': request.POST.get('ci', ''),
        'outage_impact': impact_entries,
        'notify_partners': request.POST.get('notify_partners', ''),
        'notification_emails': request.POST.get('notification_emails', ''),
        'suppression': request.POST.get('suppression', ''),
        'suppression_records': request.POST.get('suppression_records', ''),
        'banner': bool(request.POST.get('banner')),
        'banner_message': request.POST.get('banner_message', ''),
        '_original_ci': request.POST.get('_original_ci', ''),
    }

    try:
        matrix.upsert_row(payload)
    except ValueError as e:
        # Re-render the form with an error
        return render(request, 'servicenow/partials/oncall_matrix_row_editor.html', {
            'row': payload,
            'is_new': not payload['_original_ci'],
            'error': str(e),
        })

    return render(request, 'servicenow/partials/oncall_matrix_table.html', {
        'rows': matrix.load_matrix(),
        'meta': matrix.matrix_meta(),
        'columns': matrix.canonical_columns(),
        'just_applied': True,
        'applied_count': 1,
    })


# ─── Content summary (track 2) ────────────────────────────

@csrf_exempt
@require_POST
def oncall_run_content_summary(request, change_number: str):
    pre = ai_preflight()
    if not pre.get('ok'):
        return render(request, 'servicenow/partials/oncall_error.html', {
            'error': pre.get('error'),
            'action_url': pre.get('action_url'),
            'action_label': pre.get('action_label'),
        })

    review = get_object_or_404(OncallChangeReview, change_number=change_number)

    from .tasks import oncall_run_content_summary_task
    task = oncall_run_content_summary_task.delay({'change_number': change_number})

    return render(request, 'servicenow/partials/oncall_content_summary_polling.html', {
        'task_id': task.id,
        'change_number': change_number,
    })


def oncall_poll_content_summary(request, task_id: str):
    ar = AsyncResult(task_id)
    change_number = (request.GET.get('change_number') or '').strip()

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'servicenow/partials/oncall_content_summary_polling.html', {
            'task_id': task_id,
            'change_number': change_number,
        })

    if ar.state == 'FAILURE':
        return render(request, 'servicenow/partials/oncall_error.html', {
            'error': str(ar.result),
        })

    result = ar.result or {}
    if isinstance(result, dict) and result.get('error'):
        return render(request, 'servicenow/partials/oncall_error.html', {
            'error': result.get('detail') or result.get('error'),
        })

    review = OncallChangeReview.objects.filter(change_number=change_number).first()
    payload = orsvc.get_content_summary_payload(review) if review else {}

    return render(request, 'servicenow/partials/oncall_content_summary.html', {
        'review': review,
        'payload': payload,
    })


# ─── Checklist + outage + outcome ──────────────────────────

@csrf_exempt
@require_POST
def oncall_save_checklist(request, change_number: str):
    review = get_object_or_404(OncallChangeReview, change_number=change_number)

    # Form sends parallel arrays: keys[], labels[], checked[] (only for ticked items), notes[]
    keys = request.POST.getlist('chk_key[]')
    labels = request.POST.getlist('chk_label[]')
    notes = request.POST.getlist('chk_note[]')
    checked_keys = set(request.POST.getlist('chk_checked[]'))

    items = []
    for i, k in enumerate(keys):
        k = (k or '').strip()
        if not k:
            continue
        items.append({
            'key': k,
            'label': labels[i].strip() if i < len(labels) else k,
            'checked': k in checked_keys,
            'note': notes[i].strip() if i < len(notes) else '',
        })

    orsvc.save_checklist(review, items)

    return render(request, 'servicenow/partials/oncall_checklist.html', {
        'review': review,
        'items': orsvc.load_checklist(review),
        'progress': orsvc.checklist_progress(review),
        'just_saved': True,
    })


@csrf_exempt
@require_POST
def oncall_save_outage(request, change_number: str):
    review = get_object_or_404(OncallChangeReview, change_number=change_number)
    review.outage_declared = bool(request.POST.get('outage_declared'))
    review.outage_record_number = request.POST.get('outage_record_number', '').strip()
    review.save(update_fields=['outage_declared', 'outage_record_number', 'updated_at'])

    return render(request, 'servicenow/partials/oncall_outage_panel.html', {
        'review': review,
        'just_saved': True,
    })


@csrf_exempt
@require_POST
def oncall_save_outcome(request, change_number: str):
    review = get_object_or_404(OncallChangeReview, change_number=change_number)
    review.actual_outcome = request.POST.get('actual_outcome', '').strip()
    review.issues_summary = request.POST.get('issues_summary', '').strip()
    review.save(update_fields=['actual_outcome', 'issues_summary', 'updated_at'])

    return render(request, 'servicenow/partials/oncall_outcome_panel.html', {
        'review': review,
        'just_saved': True,
    })


# ─── CR Approval Review (track 3) ─────────────────────────

@csrf_exempt
@require_POST
def oncall_save_approval_status(request, change_number: str):
    review = get_object_or_404(OncallChangeReview, change_number=change_number)

    status = (request.POST.get('cr_approval_status') or '').strip()
    valid_statuses = [s[0] for s in __import__('servicenow.models', fromlist=['CR_APPROVAL_STATUS_CHOICES']).CR_APPROVAL_STATUS_CHOICES]
    if status in valid_statuses:
        review.cr_approval_status = status
    review.cr_review_ctask_number = (request.POST.get('cr_review_ctask_number') or '').strip()

    closed_at_raw = (request.POST.get('cr_review_ctask_closed_at') or '').strip()
    if closed_at_raw:
        from datetime import datetime, timezone
        try:
            d = datetime.fromisoformat(closed_at_raw)
            if not d.tzinfo:
                d = d.replace(tzinfo=timezone.utc)
            review.cr_review_ctask_closed_at = d
        except Exception:
            pass
    elif closed_at_raw == '':
        # Allow clearing the field
        review.cr_review_ctask_closed_at = None

    if status == 'approved' and not review.approved_at:
        review.approved_at = dj_tz.now()
        review.approved_by = _user_name(request)
    elif status != 'approved':
        # Allow un-approving by switching status away
        pass

    review.save()

    return render(request, 'servicenow/partials/oncall_cr_review_panel.html', {
        'review': review,
        'feedback_items': orsvc.load_approval_feedback(review),
        'outstanding_count': orsvc.approval_outstanding_count(review),
        'just_saved': True,
    })


@csrf_exempt
@require_POST
def oncall_add_approval_feedback(request, change_number: str):
    review = get_object_or_404(OncallChangeReview, change_number=change_number)
    message = (request.POST.get('message') or '').strip()
    type_ = (request.POST.get('type') or 'note').strip()

    if not message:
        return render(request, 'servicenow/partials/oncall_cr_review_panel.html', {
            'review': review,
            'feedback_items': orsvc.load_approval_feedback(review),
            'outstanding_count': orsvc.approval_outstanding_count(review),
            'error': 'Message is required.',
        })

    orsvc.add_approval_feedback(review, message=message, type=type_, by=_user_name(request))
    review.refresh_from_db()

    return render(request, 'servicenow/partials/oncall_cr_review_panel.html', {
        'review': review,
        'feedback_items': orsvc.load_approval_feedback(review),
        'outstanding_count': orsvc.approval_outstanding_count(review),
    })


@csrf_exempt
@require_POST
def oncall_resolve_approval_feedback(request, change_number: str):
    review = get_object_or_404(OncallChangeReview, change_number=change_number)
    try:
        idx = int(request.POST.get('idx') or '-1')
    except ValueError:
        idx = -1
    resolved = bool(request.POST.get('resolved', 'true') in ('true', 'on', '1'))
    orsvc.resolve_approval_feedback(review, idx, resolved=resolved)

    return render(request, 'servicenow/partials/oncall_cr_review_panel.html', {
        'review': review,
        'feedback_items': orsvc.load_approval_feedback(review),
        'outstanding_count': orsvc.approval_outstanding_count(review),
    })


@csrf_exempt
@require_POST
def oncall_delete_approval_feedback(request, change_number: str):
    review = get_object_or_404(OncallChangeReview, change_number=change_number)
    try:
        idx = int(request.POST.get('idx') or '-1')
    except ValueError:
        idx = -1
    orsvc.delete_approval_feedback(review, idx)

    return render(request, 'servicenow/partials/oncall_cr_review_panel.html', {
        'review': review,
        'feedback_items': orsvc.load_approval_feedback(review),
        'outstanding_count': orsvc.approval_outstanding_count(review),
    })


def _build_cr_ctask_description(plan_dates: dict) -> str:
    """Format the standard CR Review CTASK description body.

    plan_dates: dict like {'implementation': '2026-04-29', 'validation': '...', ...}
    Missing keys render as the literal placeholder so engineers can fill in by hand.
    """
    def _d(key):
        v = (plan_dates or {}).get(key) or ''
        v = v.strip()
        return v or '<date>'
    return (
        "CR Review and Approval\n"
        f"Implementation Plan - {_d('implementation')}\n"
        f"Validation Plan - {_d('validation')}\n"
        f"Testing Plan - {_d('testing')}\n"
        f"Recovery Plan - {_d('recovery')}"
    )


@csrf_exempt
@require_POST
def oncall_save_cr_ctask(request, change_number: str):
    """Save (and optionally close) the CR Review CTASK on the linked record."""
    review = get_object_or_404(OncallChangeReview, change_number=change_number)

    ctask_number = (request.POST.get('ctask_number') or review.cr_review_ctask_number or '').strip()
    if not ctask_number:
        return render(request, 'servicenow/partials/oncall_cr_ctask_result.html', {
            'severity': 'danger',
            'message': 'CR Review CTASK number is required. Set it on the review first.',
        })

    # Allow either a single description textarea OR per-plan date fields
    description = (request.POST.get('description') or '').strip()
    if not description:
        description = _build_cr_ctask_description({
            'implementation': request.POST.get('plan_implementation', ''),
            'validation':     request.POST.get('plan_validation', ''),
            'testing':        request.POST.get('plan_testing', ''),
            'recovery':       request.POST.get('plan_recovery', ''),
        })

    assigned_to = (request.POST.get('assigned_to') or '').strip()
    work_notes = (request.POST.get('work_notes') or '').strip()
    do_close = bool(request.POST.get('close'))
    close_code = (request.POST.get('close_code') or 'Successful').strip()
    close_notes = (request.POST.get('close_notes') or 'CR Review was completed successfully').strip()

    # Persist the CTASK number on the review row if it was just typed
    if review.cr_review_ctask_number != ctask_number:
        review.cr_review_ctask_number = ctask_number
        review.save(update_fields=['cr_review_ctask_number', 'updated_at'])

    from .tasks import oncall_update_cr_review_ctask_task
    result = oncall_update_cr_review_ctask_task.apply(args=({
        'ctask_number': ctask_number,
        'description': description,
        'assigned_to': assigned_to,
        'work_notes': work_notes,
        'close': do_close,
        'close_code': close_code,
        'close_notes': close_notes,
    },)).result or {}

    if not isinstance(result, dict) or result.get('error'):
        detail = (result or {}).get('detail') or (result or {}).get('error') or 'Unknown ServiceNow error'
        return render(request, 'servicenow/partials/oncall_cr_ctask_result.html', {
            'severity': 'danger',
            'message': f'ServiceNow update failed: {detail}',
        })

    # If closed, also stamp the review row
    if do_close and not review.cr_review_ctask_closed_at:
        review.cr_review_ctask_closed_at = dj_tz.now()
        review.save(update_fields=['cr_review_ctask_closed_at', 'updated_at'])

    msg = (
        f'CTASK {ctask_number} saved + closed in ServiceNow.'
        if do_close else
        f'CTASK {ctask_number} saved in ServiceNow. Close it manually in ServiceNow when ready.'
    )
    return render(request, 'servicenow/partials/oncall_cr_ctask_result.html', {
        'severity': 'ok',
        'message': msg,
        'ctask_number': ctask_number,
        'closed': do_close,
    })


@csrf_exempt
@require_POST
def oncall_run_cr_briefing(request, change_number: str):
    pre = ai_preflight()
    if not pre.get('ok'):
        return render(request, 'servicenow/partials/oncall_error.html', {
            'error': pre.get('error'),
            'action_url': pre.get('action_url'),
            'action_label': pre.get('action_label'),
        })

    review = get_object_or_404(OncallChangeReview, change_number=change_number)

    from .tasks import oncall_run_cr_briefing_task
    task = oncall_run_cr_briefing_task.delay({'change_number': change_number})

    return render(request, 'servicenow/partials/oncall_cr_briefing_polling.html', {
        'task_id': task.id,
        'change_number': change_number,
    })


def oncall_poll_cr_briefing(request, task_id: str):
    ar = AsyncResult(task_id)
    change_number = (request.GET.get('change_number') or '').strip()

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'servicenow/partials/oncall_cr_briefing_polling.html', {
            'task_id': task_id,
            'change_number': change_number,
        })

    if ar.state == 'FAILURE':
        return render(request, 'servicenow/partials/oncall_error.html', {
            'error': str(ar.result),
        })

    result = ar.result or {}
    if isinstance(result, dict) and result.get('error'):
        return render(request, 'servicenow/partials/oncall_error.html', {
            'error': result.get('detail') or result.get('error'),
        })

    review = OncallChangeReview.objects.filter(change_number=change_number).first()
    return render(request, 'servicenow/partials/oncall_cr_review_panel.html', {
        'review': review,
        'feedback_items': orsvc.load_approval_feedback(review) if review else [],
        'outstanding_count': orsvc.approval_outstanding_count(review) if review else 0,
        'just_briefed': True,
    })


# ─── Management report ────────────────────────────────────

REPORT_PRESETS = {
    'today':       {'label': 'Today', 'retrospective': False, 'days_offset': 0, 'span_days': 1},
    'tonight':     {'label': 'Tonight (8PM → 8AM ET)', 'retrospective': False, 'shift': 'tonight'},
    'last_night':  {'label': 'Last night (8PM → 8AM ET)', 'retrospective': True, 'shift': 'last_night'},
    'last_week':   {'label': 'Last 7 days', 'retrospective': True, 'days_offset': -7, 'span_days': 7},
    'next_week':   {'label': 'Next 7 days', 'retrospective': False, 'days_offset': 0, 'span_days': 7},
}


def _et_overnight_window(anchor_date_today_et: bool):
    """Return (start, end) for an ET-anchored 8PM→8AM overnight shift.

    anchor_date_today_et=True  → tonight (today's 8PM → tomorrow's 8AM)
    anchor_date_today_et=False → last night (yesterday's 8PM → today's 8AM)
    """
    from datetime import datetime, timedelta, time
    try:
        from zoneinfo import ZoneInfo
        ET = ZoneInfo('America/New_York')
    except Exception:
        # Fallback: treat as UTC if zoneinfo / tzdata isn't available
        from datetime import timezone
        ET = timezone.utc

    now_et = dj_tz.now().astimezone(ET)
    today_et = now_et.date()
    anchor = today_et if anchor_date_today_et else (today_et - timedelta(days=1))
    start = datetime.combine(anchor, time(20, 0), tzinfo=ET)
    end = datetime.combine(anchor + timedelta(days=1), time(8, 0), tzinfo=ET)
    return start, end


def _resolve_report_window(preset: str, custom_start: str = '', custom_end: str = ''):
    """Return (start, end, label, is_retrospective)."""
    from datetime import datetime, timezone, timedelta
    now = dj_tz.now()

    if preset == 'custom' and custom_start and custom_end:
        try:
            s = datetime.fromisoformat(custom_start)
            e = datetime.fromisoformat(custom_end)
            # `datetime-local` posts naive ISO strings (no tz). Treat as the
            # browser's local time → UTC by attaching the local offset; if
            # we're running on a naive deploy just attach UTC.
            if not s.tzinfo: s = s.replace(tzinfo=timezone.utc)
            if not e.tzinfo: e = e.replace(tzinfo=timezone.utc)
            return s, e, f'{custom_start} → {custom_end}', e < now
        except Exception:
            pass

    cfg = REPORT_PRESETS.get(preset) or REPORT_PRESETS['today']

    # ET-anchored overnight shifts (Tonight / Last night)
    if cfg.get('shift') == 'tonight':
        start, end = _et_overnight_window(anchor_date_today_et=True)
        return start, end, cfg['label'], False
    if cfg.get('shift') == 'last_night':
        start, end = _et_overnight_window(anchor_date_today_et=False)
        return start, end, cfg['label'], True

    # Day-aligned windows (Today / Last 7 / Next 7)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = today + timedelta(days=cfg['days_offset'])
    end = start + timedelta(days=cfg.get('span_days', 1))
    return start, end, cfg['label'], bool(cfg.get('retrospective'))


def oncall_report_page(request):
    return render(request, 'servicenow/oncall_report.html', {
        'presets': [
            {'value': k, 'label': v['label'], 'retrospective': v.get('retrospective', False)}
            for k, v in REPORT_PRESETS.items()
        ],
        'default_preset': 'tonight',
    })


@csrf_exempt
@require_POST
def oncall_report_run(request):
    pre = ai_preflight()
    if not pre.get('ok'):
        return render(request, 'servicenow/partials/oncall_error.html', {
            'error': pre.get('error'),
            'action_url': pre.get('action_url'),
            'action_label': pre.get('action_label'),
        })

    preset = request.POST.get('preset', 'tonight').strip()
    custom_start = request.POST.get('custom_start', '').strip()
    custom_end = request.POST.get('custom_end', '').strip()
    change_numbers_raw = request.POST.get('change_numbers', '').strip()

    from .tasks import oncall_management_report_task

    # Mode: by-change-numbers — explicit curated list
    if preset == 'by_changes' or change_numbers_raw:
        # Accept newlines, commas, or whitespace as separators
        import re
        numbers = [n for n in re.split(r'[\s,;]+', change_numbers_raw) if n]
        # Normalise to upper-case (CHG numbers are case-insensitive)
        numbers = [n.strip().upper() for n in numbers]
        # Dedupe while preserving order
        seen = set()
        deduped = []
        for n in numbers:
            if n not in seen:
                seen.add(n)
                deduped.append(n)

        if not deduped:
            return render(request, 'servicenow/partials/oncall_error.html', {
                'error': 'Paste at least one change number (one per line, or comma-separated).',
            })

        label = (
            deduped[0] if len(deduped) == 1
            else f'{len(deduped)} hand-picked changes'
        )

        # Decide retrospective flag from the rows themselves: if every
        # found row has a non-empty actual_outcome, treat as retrospective.
        from .models import OncallChangeReview
        existing = OncallChangeReview.objects.filter(change_number__in=deduped)
        outcomes = [r.actual_outcome for r in existing]
        is_retro = bool(outcomes) and all(o for o in outcomes)

        task = oncall_management_report_task.delay({
            'change_numbers': deduped,
            'label': label,
            'retrospective': is_retro,
        })
        return render(request, 'servicenow/partials/oncall_report_polling.html', {
            'task_id': task.id,
            'label': label,
        })

    # Mode: time-window
    start, end, label, is_retro = _resolve_report_window(preset, custom_start, custom_end)

    task = oncall_management_report_task.delay({
        'window_start': start.isoformat(),
        'window_end': end.isoformat(),
        'label': label,
        'retrospective': is_retro,
    })

    return render(request, 'servicenow/partials/oncall_report_polling.html', {
        'task_id': task.id,
        'label': label,
    })


def oncall_report_poll(request, task_id: str):
    ar = AsyncResult(task_id)

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'servicenow/partials/oncall_report_polling.html', {
            'task_id': task_id,
            'label': request.GET.get('label', 'window'),
        })

    if ar.state == 'FAILURE':
        return render(request, 'servicenow/partials/oncall_error.html', {
            'error': str(ar.result),
        })

    result = ar.result or {}
    if isinstance(result, dict) and result.get('error'):
        return render(request, 'servicenow/partials/oncall_error.html', {
            'error': result.get('detail') or result.get('error'),
        })

    return render(request, 'servicenow/partials/oncall_report_results.html', {
        'report': result,
    })


@csrf_exempt
@require_POST
def oncall_report_email(request):
    """Render the report into an Outlook draft email."""
    recipients = request.POST.get('recipients', '').strip()
    subject = request.POST.get('subject', '').strip()
    body = request.POST.get('body', '').strip()

    if not body:
        return render(request, 'servicenow/partials/oncall_action_result.html', {
            'message': 'No report body — generate a report first.',
            'severity': 'danger',
        })

    result = outlook.open_draft(
        recipients=recipients,
        subject=subject or 'Change window summary',
        body=body,
    )

    if result.get('ok'):
        return render(request, 'servicenow/partials/oncall_action_result.html', {
            'message': 'Outlook draft opened. Review recipients + body, then send.',
            'severity': 'ok',
        })
    return render(request, 'servicenow/partials/oncall_action_result.html', {
        'message': result.get('error', 'Outlook draft failed'),
        'severity': 'danger',
    })


# ─── Matrix row delete (existing) ─────────────────────────

@csrf_exempt
@require_POST
def oncall_matrix_row_delete(request):
    """POST — delete one row by CI."""
    ci = (request.POST.get('ci') or '').strip()
    if ci:
        matrix.delete_row(ci)
    return render(request, 'servicenow/partials/oncall_matrix_table.html', {
        'rows': matrix.load_matrix(),
        'meta': matrix.matrix_meta(),
        'columns': matrix.canonical_columns(),
    })


def oncall_matrix_export_json(request):
    body = matrix.export_json()
    resp = HttpResponse(body, content_type='application/json')
    resp['Content-Disposition'] = 'attachment; filename="oncall_suppression_matrix.json"'
    return resp


def oncall_matrix_export_csv(request):
    body = matrix.export_csv()
    resp = HttpResponse(body, content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename="oncall_suppression_matrix.csv"'
    return resp


# ─── Banner ──────────────────────────────────────────────

@csrf_exempt
@require_POST
def oncall_banner_post(request):
    message = request.POST.get('message', '').strip()
    severity = request.POST.get('severity', 'warn').strip()
    change_number = request.POST.get('change_number', '').strip()
    expires_minutes = request.POST.get('expires_minutes', '').strip()

    if not message:
        banner.clear()
    else:
        expires_at = None
        if expires_minutes.isdigit():
            expires_at = (dj_tz.now() + timedelta(minutes=int(expires_minutes))).timestamp()
        banner.post(
            message=message,
            change_number=change_number,
            severity=severity,
            expires_at=expires_at,
            posted_by=_user_name(request),
        )
        if change_number:
            review = OncallChangeReview.objects.filter(change_number=change_number).first()
            if review:
                orsvc.advance_stage(review, 'banner_posted', by=_user_name(request))

    return render(request, 'servicenow/partials/oncall_banner_status.html', {
        'banner': banner.get_active(),
    })


@csrf_exempt
@require_POST
def oncall_banner_clear(request):
    banner.clear()
    return render(request, 'servicenow/partials/oncall_banner_status.html', {
        'banner': None,
    })


# ─── Templates editor ────────────────────────────────────

@csrf_exempt
@require_POST
def oncall_template_save(request):
    name = request.POST.get('name', '').strip()
    if not name:
        return render(request, 'servicenow/partials/oncall_templates_list.html', {
            'templates': ntpl.list_templates(),
            'error': 'Template name is required.',
        })
    ntpl.save_template(name, {
        'label': request.POST.get('label', ''),
        'description': request.POST.get('description', ''),
        'subject': request.POST.get('subject', ''),
        'body': request.POST.get('body', ''),
    })
    return render(request, 'servicenow/partials/oncall_templates_list.html', {
        'templates': ntpl.list_templates(),
        'saved_name': name,
    })


# ─── History list (filtered) ─────────────────────────────

def oncall_history_partial(request):
    qs = OncallChangeReview.objects.all()

    stage = request.GET.get('stage', '').strip()
    verdict = request.GET.get('verdict', '').strip()
    q = request.GET.get('q', '').strip()
    group = request.GET.get('assignment_group', '').strip()
    purpose = request.GET.get('pull_purpose', '').strip()

    if stage and stage in ONCALL_STAGE_VALUES:
        qs = qs.filter(stage=stage)
    if verdict and verdict in [v[0] for v in AI_VERDICT_CHOICES]:
        qs = qs.filter(ai_outage_likely=verdict)
    if group:
        qs = qs.filter(assignment_group__icontains=group)
    if purpose in ('outage_triage', 'cr_approval', 'both'):
        qs = qs.filter(pull_purpose=purpose)
    if q:
        qs = qs.filter(change_number__icontains=q) | qs.filter(short_description__icontains=q)

    qs = qs.order_by('-updated_at')[:200]

    return render(request, 'servicenow/partials/oncall_history_table.html', {
        'reviews': qs,
        'count': qs.count() if hasattr(qs, 'count') else len(list(qs)),
    })

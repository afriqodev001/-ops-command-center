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
    return render(request, 'servicenow/oncall.html', {
        'presets': _oncall_presets(),
        'default_preset': 'oncall_changes_this_week',
        'recent_reviews': OncallChangeReview.objects.order_by('-updated_at')[:25],
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
        'templates': ntpl.list_templates(),
    })


# ─── Pull changes (HTMX) ──────────────────────────────────

@csrf_exempt
@require_POST
def oncall_pull_changes(request):
    preset = request.POST.get('preset', '').strip() or 'oncall_changes_this_week'
    win = _window_bounds(preset)

    from .tasks import presets_run_task
    task = presets_run_task.delay({
        'preset': preset,
        'params': {},
    })

    return render(request, 'servicenow/partials/oncall_pull_polling.html', {
        'task_id': task.id,
        'preset': preset,
        'window_label': win['label'],
    })


def oncall_pull_poll(request, task_id: str):
    preset = request.GET.get('preset', 'oncall_changes_this_week')
    win = _window_bounds(preset)
    ar = AsyncResult(task_id)

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'servicenow/partials/oncall_pull_polling.html', {
            'task_id': task_id,
            'preset': preset,
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

    reviews = orsvc.upsert_pulled_changes(
        rows,
        window_start=win['window_start'],
        window_end=win['window_end'],
        window_label=win['label'],
    )

    return render(request, 'servicenow/partials/oncall_pull_results.html', {
        'reviews': reviews,
        'preset': preset,
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

    if stage and stage in ONCALL_STAGE_VALUES:
        qs = qs.filter(stage=stage)
    if verdict and verdict in [v[0] for v in AI_VERDICT_CHOICES]:
        qs = qs.filter(ai_outage_likely=verdict)
    if group:
        qs = qs.filter(assignment_group__icontains=group)
    if q:
        qs = qs.filter(change_number__icontains=q) | qs.filter(short_description__icontains=q)

    qs = qs.order_by('-updated_at')[:200]

    return render(request, 'servicenow/partials/oncall_history_table.html', {
        'reviews': qs,
        'count': qs.count() if hasattr(qs, 'count') else len(list(qs)),
    })

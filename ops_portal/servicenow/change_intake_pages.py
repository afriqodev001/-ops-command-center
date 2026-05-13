"""
HTTP endpoints for the Vendor Spreadsheet → ServiceNow Change intake wizard.

Mirrors the dispatch + polling pattern used by oncall_run_content_summary
(see oncall_pages.py:777) so the front-end behaviour is identical:
POST kicks off a Celery task, GET poll endpoint swaps in either a polling
partial or the final result partial.
"""
from __future__ import annotations

import json
from typing import Dict, List

from celery.result import AsyncResult
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from servicenow.models import ChangeIntakeRequest
from servicenow.services.change_intake.mapping_spec import get_mapping, VENDORS
from servicenow.services.change_intake.excel_parser import parse_xlsx
from servicenow.services.change_intake.mapping_apply import apply_mapping, build_description
from servicenow.services.change_intake import template_store


# ── helpers ─────────────────────────────────────────────────────

def _load_json_field(text: str, default):
    if not text:
        return default
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return default


def _proposals_for_render(intake: ChangeIntakeRequest) -> List[Dict]:
    proposals = _load_json_field(intake.proposals_json, [])
    # Sort by group so the UI groups by section.
    order = {'Identity': 0, 'Schedule': 1, 'Description': 2,
             'Planning': 3, 'People': 4, '': 9}
    proposals.sort(key=lambda p: (order.get(p.get('group', ''), 99),
                                  p.get('target_field', '')))
    return proposals


def _render_mapping_form(request, intake: ChangeIntakeRequest):
    completeness = _load_json_field(intake.ai_completeness_json, {})
    completeness_debug = completeness.pop('_debug', {}) if isinstance(completeness, dict) else {}
    return render(request, 'servicenow/partials/change_intake_mapping_form.html', {
        'intake': intake,
        'proposals': _proposals_for_render(intake),
        'completeness': completeness,
        'completeness_debug': completeness_debug,
    })


# ── 1. Wizard shell ─────────────────────────────────────────────

@require_GET
def change_intake_upload_page(request):
    """GET /servicenow/change-intake/ — the wizard shell."""
    recent = ChangeIntakeRequest.objects.order_by('-created_at')[:10]
    return render(request, 'servicenow/change_intake_upload.html', {
        'recent': recent,
    })


# ── 2. Upload + parse + create intake row ───────────────────────

@csrf_exempt
@require_POST
def change_intake_upload_submit(request):
    """POST /servicenow/change-intake/upload/ — multipart xlsx upload."""
    vendor = (request.POST.get('vendor_template') or 'epsilon').strip()
    uploaded = request.FILES.get('xlsx_file')
    if not uploaded:
        return render(request, 'servicenow/partials/change_intake_error.html', {
            'error': 'No file was uploaded. Select a .xlsx and try again.',
        })

    mapping = get_mapping(vendor)
    if mapping is None:
        return render(request, 'servicenow/partials/change_intake_error.html', {
            'error': f"Unknown vendor template '{vendor}'. Available: epsilon.",
        })

    intake = ChangeIntakeRequest.objects.create(
        vendor_template=vendor,
        uploaded_file=uploaded,
        original_filename=uploaded.name,
    )

    try:
        parsed = parse_xlsx(intake.uploaded_file.path)
    except Exception as e:
        intake.submit_status = 'error'
        intake.submit_error = f'Could not parse spreadsheet: {e}'
        intake.save(update_fields=['submit_status', 'submit_error', 'updated_at'])
        return render(request, 'servicenow/partials/change_intake_error.html', {
            'error': intake.submit_error,
            'intake': intake,
        })

    proposals = apply_mapping(parsed, mapping)

    intake.parsed_payload_json = json.dumps({
        'cells': parsed.cells,
        'sheets': parsed.sheets,
    })
    intake.proposals_json = json.dumps(proposals)
    intake.save(update_fields=[
        'parsed_payload_json', 'proposals_json', 'updated_at',
    ])

    return _render_mapping_form(request, intake)


# ── 3. Autosave edits ───────────────────────────────────────────

@csrf_exempt
@require_POST
def change_intake_mapping_save(request, intake_id: int):
    """POST /servicenow/change-intake/<id>/mapping/save/"""
    intake = get_object_or_404(ChangeIntakeRequest, pk=intake_id)
    proposals = _load_json_field(intake.proposals_json, [])

    # Form posts each editable value under name="field__<target_field>".
    prefix = 'field__'
    edits = {
        key[len(prefix):]: value
        for key, value in request.POST.items()
        if key.startswith(prefix)
    }

    for p in proposals:
        if p['target_field'] in edits:
            p['value'] = edits[p['target_field']]

    intake.proposals_json = json.dumps(proposals)
    intake.save(update_fields=['proposals_json', 'updated_at'])

    return render(request, 'servicenow/partials/change_intake_saved_indicator.html', {
        'saved_at': timezone.now(),
    })


# ── 4. AI completeness check ────────────────────────────────────

@csrf_exempt
@require_POST
def change_intake_completeness_run(request, intake_id: int):
    """POST /servicenow/change-intake/<id>/completeness/run/"""
    intake = get_object_or_404(ChangeIntakeRequest, pk=intake_id)

    from .change_intake_tasks import change_intake_ai_completeness_task
    task = change_intake_ai_completeness_task.delay({'intake_id': intake.pk})

    intake.completeness_task_id = task.id
    intake.save(update_fields=['completeness_task_id', 'updated_at'])

    return render(request, 'servicenow/partials/change_intake_completeness_polling.html', {
        'intake': intake,
        'task_id': task.id,
    })


@require_GET
def change_intake_completeness_poll(request, intake_id: int, task_id: str):
    """GET /servicenow/change-intake/<id>/completeness/poll/<task_id>/"""
    intake = get_object_or_404(ChangeIntakeRequest, pk=intake_id)
    ar = AsyncResult(task_id)

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'servicenow/partials/change_intake_completeness_polling.html', {
            'intake': intake,
            'task_id': task_id,
        })

    if ar.state == 'FAILURE':
        return render(request, 'servicenow/partials/change_intake_error.html', {
            'error': str(ar.result),
        })

    completeness = _load_json_field(intake.ai_completeness_json, {})
    debug = completeness.pop('_debug', {}) if isinstance(completeness, dict) else {}
    return render(request, 'servicenow/partials/change_intake_completeness.html', {
        'intake': intake,
        'completeness': completeness,
        'debug': debug,
    })


# ── 5. Per-field "Generate with AI" ─────────────────────────────

@csrf_exempt
@require_POST
def change_intake_field_generate(request, intake_id: int, target_field: str):
    """POST /servicenow/change-intake/<id>/field/<field>/generate/"""
    intake = get_object_or_404(ChangeIntakeRequest, pk=intake_id)

    from .change_intake_tasks import change_intake_ai_field_generate_task
    task = change_intake_ai_field_generate_task.delay({
        'intake_id': intake.pk,
        'target_field': target_field,
    })

    return render(request, 'servicenow/partials/change_intake_field_polling.html', {
        'intake': intake,
        'target_field': target_field,
        'task_id': task.id,
    })


@require_GET
def change_intake_field_poll(request, intake_id: int, target_field: str, task_id: str):
    """GET /servicenow/change-intake/<id>/field/<field>/poll/<task_id>/"""
    intake = get_object_or_404(ChangeIntakeRequest, pk=intake_id)
    ar = AsyncResult(task_id)

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'servicenow/partials/change_intake_field_polling.html', {
            'intake': intake,
            'target_field': target_field,
            'task_id': task_id,
        })

    if ar.state == 'FAILURE':
        return render(request, 'servicenow/partials/change_intake_error.html', {
            'error': str(ar.result),
        })

    result = ar.result or {}
    suggested = (result.get('suggested_value') or '').strip()
    error = result.get('error') or ''

    # Apply the suggestion to the stored proposals (so a reload reflects it
    # and a subsequent submit uses the new value).
    if suggested and not error:
        proposals = _load_json_field(intake.proposals_json, [])
        for p in proposals:
            if p['target_field'] == target_field:
                p['value'] = suggested
                break
        intake.proposals_json = json.dumps(proposals)
        intake.save(update_fields=['proposals_json', 'updated_at'])

    debug = _load_json_field(intake.ai_field_debug_json, {}).get(target_field, {})

    return render(request, 'servicenow/partials/change_intake_field_suggestion.html', {
        'intake': intake,
        'target_field': target_field,
        'suggested_value': suggested,
        'error': error,
        'debug': debug,
    })


# ── 6. Submit (CR + attachment + CTASK) ─────────────────────────

@csrf_exempt
@require_POST
def change_intake_submit(request, intake_id: int):
    """POST /servicenow/change-intake/<id>/submit/"""
    intake = get_object_or_404(ChangeIntakeRequest, pk=intake_id)

    # Pick up any in-flight edits posted with the submit (the upload page form
    # serialises the full set of editable values).
    proposals = _load_json_field(intake.proposals_json, [])
    prefix = 'field__'
    edits = {
        key[len(prefix):]: value
        for key, value in request.POST.items()
        if key.startswith(prefix)
    }
    if edits:
        for p in proposals:
            if p['target_field'] in edits:
                p['value'] = edits[p['target_field']]
        intake.proposals_json = json.dumps(proposals)

    from .change_intake_tasks import change_intake_submit_task
    task = change_intake_submit_task.delay({'intake_id': intake.pk})

    intake.submit_task_id = task.id
    intake.submit_status = 'submitting'
    intake.submit_error = ''
    intake.save(update_fields=[
        'proposals_json', 'submit_task_id', 'submit_status',
        'submit_error', 'updated_at',
    ])

    return render(request, 'servicenow/partials/change_intake_submit_polling.html', {
        'intake': intake,
        'task_id': task.id,
    })


# ── 7. Description template editor ──────────────────────────────

@require_GET
def change_intake_template_list(request):
    """GET /servicenow/change-intake/templates/ — pick which vendor template to edit."""
    vendors = []
    for slug in template_store.list_vendors():
        tpl = template_store.load_template(slug) or {}
        vendors.append({
            'slug': slug,
            'name': tpl.get('name') or slug,
            'section_count': len(tpl.get('sections') or []),
            'customised': template_store.is_customised(slug),
        })
    return render(request, 'servicenow/change_intake_templates.html', {
        'vendors': vendors,
    })


@require_GET
def change_intake_template_edit(request, vendor_slug: str):
    """GET /servicenow/change-intake/templates/<vendor>/ — edit one vendor's template."""
    template = template_store.load_template(vendor_slug)
    if not template:
        return render(request, 'servicenow/partials/change_intake_error.html', {
            'error': f"No template exists for vendor '{vendor_slug}'.",
        })

    mapping = get_mapping(vendor_slug)
    available_fields = []
    if mapping:
        for rule in mapping.rules:
            if rule.target_field == 'description':
                continue
            available_fields.append({
                'field': rule.target_field,
                'label': rule.label or rule.target_field,
                'kind': rule.kind,
            })

    return render(request, 'servicenow/change_intake_template_edit.html', {
        'vendor_slug': vendor_slug,
        'template': template,
        'sections_json': json.dumps(template.get('sections') or []),
        'available_fields': available_fields,
        'available_fields_json': json.dumps(available_fields),
        'is_customised': template_store.is_customised(vendor_slug),
    })


@csrf_exempt
@require_POST
def change_intake_template_save(request, vendor_slug: str):
    """POST /servicenow/change-intake/templates/<vendor>/save/"""
    current = template_store.load_template(vendor_slug) or {}

    name = (request.POST.get('name') or current.get('name') or vendor_slug).strip()
    intro = request.POST.get('intro', current.get('intro', ''))
    outro = request.POST.get('outro', current.get('outro', ''))

    try:
        sections = json.loads(request.POST.get('sections_json') or '[]')
        if not isinstance(sections, list):
            sections = []
    except (ValueError, TypeError):
        return render(request, 'servicenow/partials/change_intake_error.html', {
            'error': 'sections_json was not valid JSON.',
        })

    # Normalise each section.
    cleaned = []
    for s in sections:
        if not isinstance(s, dict):
            continue
        heading = (s.get('heading') or '').strip()
        field = (s.get('field') or '').strip()
        placeholder = (s.get('placeholder') or '').strip()
        if not (heading and field):
            continue
        cleaned.append({
            'heading': heading,
            'field': field,
            'placeholder': placeholder,
        })

    template_store.save_template(vendor_slug, {
        'name': name,
        'intro': intro,
        'outro': outro,
        'sections': cleaned,
    })

    return redirect(reverse('change-intake-template-edit', kwargs={'vendor_slug': vendor_slug}) + '?saved=1')


@csrf_exempt
@require_POST
def change_intake_template_reset(request, vendor_slug: str):
    """POST /servicenow/change-intake/templates/<vendor>/reset/"""
    template_store.reset_template(vendor_slug)
    return redirect(reverse('change-intake-template-edit', kwargs={'vendor_slug': vendor_slug}) + '?reset=1')


@require_GET
def change_intake_template_preview(request, vendor_slug: str):
    """GET /servicenow/change-intake/templates/<vendor>/preview/ — HTMX preview
    of the assembled description using sample data drawn from in-progress
    intakes for this vendor (or empty values if none)."""
    # Pull the latest intake's proposal values for this vendor, if any, so the
    # preview shows the template against realistic content.
    intake = (ChangeIntakeRequest.objects
              .filter(vendor_template=vendor_slug)
              .order_by('-updated_at')
              .first())
    proposals = _load_json_field(intake.proposals_json, []) if intake else []
    by_field = {p['target_field']: (p.get('value') or '') for p in proposals}

    preview = build_description(by_field, vendor_slug)
    return render(request, 'servicenow/partials/change_intake_template_preview.html', {
        'vendor_slug': vendor_slug,
        'preview': preview,
        'has_sample': bool(intake),
    })


@require_GET
def change_intake_submit_poll(request, intake_id: int, task_id: str):
    """GET /servicenow/change-intake/<id>/submit/poll/<task_id>/"""
    intake = get_object_or_404(ChangeIntakeRequest, pk=intake_id)
    ar = AsyncResult(task_id)

    # Refresh the intake so we see status updates the task wrote between steps.
    intake.refresh_from_db()

    if intake.submit_status in ('done', 'error'):
        return render(request, 'servicenow/partials/change_intake_submit_result.html', {
            'intake': intake,
        })

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'servicenow/partials/change_intake_submit_polling.html', {
            'intake': intake,
            'task_id': task_id,
        })

    if ar.state == 'FAILURE':
        intake.submit_status = 'error'
        intake.submit_error = f'Submit task crashed: {ar.result}'
        intake.save(update_fields=['submit_status', 'submit_error', 'updated_at'])
        return render(request, 'servicenow/partials/change_intake_submit_result.html', {
            'intake': intake,
        })

    return render(request, 'servicenow/partials/change_intake_submit_result.html', {
        'intake': intake,
    })

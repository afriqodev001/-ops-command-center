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

from servicenow.models import ChangeIntakeRequest, VendorConfig
from servicenow.services.change_intake.mapping_spec import get_mapping, VENDORS
from servicenow.services.change_intake.excel_parser import parse_xlsx
from servicenow.services.change_intake.mapping_apply import (
    apply_mapping,
    apply_vendor_defaults,
    find_unfilled_proposals,
)


# ── helpers ─────────────────────────────────────────────────────

def _load_json_field(text: str, default):
    if not text:
        return default
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return default


# Explicit display order (per the engineer's spec). Anything outside this
# list falls to the end of its group in alphabetical order.
FIELD_ORDER: List[str] = [
    # Identity (no umbrella header — these render flat)
    'category',
    'reason',
    'cmdb_ci',
    'assignment_group',
    'short_description',
    'description',
    'u_code_change',
    # Planning umbrella
    'justification',
    'u_outage',
    'test_plan',
    'implementation_plan',
    'u_implementation_strategy',
    'u_implementation_approach',
    'backout_plan',
    # Schedule umbrella
    'start_date',
    'end_date',
]

GROUP_ORDER = {'Identity': 0, 'Planning': 1, 'Schedule': 2, '': 9}


def _proposals_for_render(intake: ChangeIntakeRequest) -> List[Dict]:
    proposals = _load_json_field(intake.proposals_json, [])
    field_index = {f: i for i, f in enumerate(FIELD_ORDER)}
    proposals.sort(key=lambda p: (
        GROUP_ORDER.get(p.get('group', ''), 99),
        field_index.get(p.get('target_field', ''), 999),
        p.get('target_field', ''),
    ))
    return proposals


def _render_mapping_form(request, intake: ChangeIntakeRequest):
    from .services.creation_templates import (
        load_change_categories, load_change_reasons,
    )
    completeness = _load_json_field(intake.ai_completeness_json, {})
    completeness_debug = completeness.pop('_debug', {}) if isinstance(completeness, dict) else {}
    return render(request, 'servicenow/partials/change_intake_mapping_form.html', {
        'intake': intake,
        'proposals': _proposals_for_render(intake),
        'completeness': completeness,
        'completeness_debug': completeness_debug,
        'change_categories': load_change_categories(),
        'change_reasons': load_change_reasons(),
    })


# ── 1. Wizard shell ─────────────────────────────────────────────

@require_GET
def change_intake_upload_page(request):
    """GET /servicenow/change-intake/ — the wizard shell."""
    recent = ChangeIntakeRequest.objects.order_by('-created_at')[:10]
    return render(request, 'servicenow/change_intake_upload.html', {
        'recent': recent,
    })


# ── Vendor defaults config page ─────────────────────────────────

@require_GET
def change_intake_config_page(request):
    """GET /servicenow/change-intake/config/ — edit per-vendor defaults."""
    vendor_rows = []
    for slug, mapping in VENDORS.items():
        cfg = VendorConfig.objects.filter(vendor_template=slug).first()
        defaults = cfg.defaults() if cfg else {}
        # Surface every target_field on the mapping so the engineer can set
        # a default for any of them, not just the three Epsilon-seeded ones.
        rows = []
        for rule in mapping.rules:
            if rule.target_field.startswith('_'):
                continue
            rows.append({
                'target_field': rule.target_field,
                'label': rule.label or rule.target_field,
                'kind': rule.kind,
                'source_rule': rule.source_rule,
                'value': defaults.get(rule.target_field, ''),
            })
        vendor_rows.append({
            'slug': slug,
            'name': mapping.name,
            'rows': rows,
            'updated_at': cfg.updated_at if cfg else None,
        })
    return render(request, 'servicenow/change_intake_config.html', {
        'vendors': vendor_rows,
    })


@csrf_exempt
@require_POST
def change_intake_config_save(request, vendor_slug: str):
    """POST /servicenow/change-intake/config/<vendor>/save/"""
    if vendor_slug not in VENDORS:
        return render(request, 'servicenow/partials/change_intake_error.html', {
            'error': f'Unknown vendor: {vendor_slug}',
        })
    prefix = 'default__'
    edits = {
        key[len(prefix):]: (value or '').strip()
        for key, value in request.POST.items()
        if key.startswith(prefix)
    }
    # Drop empty values so the dict stays compact.
    defaults = {k: v for k, v in edits.items() if v}

    cfg, _ = VendorConfig.objects.update_or_create(
        vendor_template=vendor_slug,
        defaults={'defaults_json': json.dumps(defaults, indent=2)},
    )
    return render(request, 'servicenow/partials/change_intake_saved_indicator.html', {
        'saved_at': timezone.now(),
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
    proposals = apply_vendor_defaults(proposals, vendor)

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


# ── 4b. Bulk AI extraction ──────────────────────────────────────

@csrf_exempt
@require_POST
def change_intake_extract_run(request, intake_id: int):
    """POST /servicenow/change-intake/<id>/extract/run/"""
    intake = get_object_or_404(ChangeIntakeRequest, pk=intake_id)

    # Pick up any in-flight edits posted alongside the trigger so we don't
    # overwrite them when the task merges suggestions back in.
    prefix = 'field__'
    edits = {
        key[len(prefix):]: value
        for key, value in request.POST.items()
        if key.startswith(prefix)
    }
    if edits:
        proposals = _load_json_field(intake.proposals_json, [])
        for p in proposals:
            if p['target_field'] in edits:
                p['value'] = edits[p['target_field']]
        intake.proposals_json = json.dumps(proposals)
        intake.save(update_fields=['proposals_json', 'updated_at'])

    from .change_intake_tasks import change_intake_ai_extract_task
    task = change_intake_ai_extract_task.delay({'intake_id': intake.pk})

    return render(request, 'servicenow/partials/change_intake_extract_polling.html', {
        'intake': intake,
        'task_id': task.id,
    })


@require_GET
def change_intake_extract_poll(request, intake_id: int, task_id: str):
    """GET /servicenow/change-intake/<id>/extract/poll/<task_id>/"""
    intake = get_object_or_404(ChangeIntakeRequest, pk=intake_id)
    ar = AsyncResult(task_id)

    if ar.state in ('PENDING', 'RECEIVED', 'STARTED'):
        return render(request, 'servicenow/partials/change_intake_extract_polling.html', {
            'intake': intake,
            'task_id': task_id,
        })

    if ar.state == 'FAILURE':
        return render(request, 'servicenow/partials/change_intake_error.html', {
            'error': str(ar.result),
        })

    # Re-render the whole mapping form so the new suggestions show in the
    # textareas. The wrapping wizard panel swaps this in via hx-target.
    return _render_mapping_form(request, intake)


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

    # Category / reason render as <select>; pass options for those cases.
    from .services.creation_templates import (
        load_change_categories, load_change_reasons,
    )
    return render(request, 'servicenow/partials/change_intake_field_suggestion.html', {
        'intake': intake,
        'target_field': target_field,
        'suggested_value': suggested,
        'error': error,
        'debug': debug,
        'change_categories': load_change_categories(),
        'change_reasons': load_change_reasons(),
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
        intake.save(update_fields=['proposals_json', 'updated_at'])

    # Block submit if any template-rendered field still has <human input>
    # or [TODO:] markers — the engineer must fill them in first.
    unfilled = find_unfilled_proposals(proposals)
    if unfilled:
        return render(request, 'servicenow/partials/change_intake_submit_blocked.html', {
            'intake': intake,
            'unfilled': unfilled,
        })

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

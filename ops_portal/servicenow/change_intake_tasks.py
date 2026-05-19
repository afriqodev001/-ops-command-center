"""
Celery tasks for the Vendor Spreadsheet → Change intake wizard.

Three tasks:
  - change_intake_ai_completeness_task   AI-checks parsed payload + proposals
  - change_intake_ai_field_generate_task per-field "Generate with AI"
  - change_intake_submit_task            orchestrator: CR → attachment → CTASK

All tasks return a serialisable dict; the per-step persistence happens
inside the task body so the polling endpoint can render progress from
the model rather than the Celery result alone.
"""
from __future__ import annotations

import json
import mimetypes
from typing import Dict, List

from celery import shared_task
from django.utils import timezone

from servicenow.services.ai_assist import _call_llm, _extract_json_dict
from servicenow.services.prompt_store import get_prompt
from servicenow.services.change_intake.mapping_apply import (
    fields_for_servicenow,
)
from servicenow.services.servicenow_change_create import (
    create_change_via_table_api,
)
from servicenow.services.servicenow_attachment_upload import (
    upload_attachment_to_record,
)
from servicenow.services.servicenow_ctask_create import (
    create_change_task_via_table_api,
)
from servicenow.services.servicenow_table import (
    list_tasks_for_change,
    patch_change_task,
)
from servicenow.tasks import with_servicenow_auth_retry


# ── Helpers ─────────────────────────────────────────────────────

def _load(text: str) -> dict | list:
    if not text:
        return {}
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return {}


def _unwrap_sn_record(result) -> dict | list:
    """Return the inner ServiceNow record from any of the response shapes
    we've seen across the codebase. Drills past `data`, `result`, and `record`
    wrappers (in any order, possibly nested) until it finds either a flat
    record (has `sys_id`/`number`) or a list. Returns {} if nothing matches.

    Known shapes:
      - raw fetch_json_in_browser:  {ok, status, data: {result: <record>}}
      - servicenow_table helpers:   {result: <record-or-list>}
      - doubly-wrapped (rare):      {result: {result: <record>}}
      - flat record:                <record>
    """
    seen = set()

    def _drill(obj):
        if obj is None:
            return None
        obj_id = id(obj)
        if obj_id in seen:
            return None
        seen.add(obj_id)
        if isinstance(obj, list):
            return obj
        if not isinstance(obj, dict):
            return None
        if obj.get('sys_id') or obj.get('number'):
            return obj
        for key in ('result', 'record', 'data'):
            inner = obj.get(key)
            if inner is None:
                continue
            found = _drill(inner)
            if found is not None:
                return found
        return None

    found = _drill(result)
    if isinstance(found, (dict, list)):
        return found
    return {}


def _diagnose_shape(obj, depth: int = 0) -> str:
    """Return a short, human-readable summary of a response shape (no values,
    just keys + types) so we can debug unexpected ServiceNow responses without
    leaking record contents into submit_error."""
    if depth > 4:
        return '…'
    if obj is None:
        return 'None'
    if isinstance(obj, bool):
        return f'bool={obj}'
    if isinstance(obj, (int, float)):
        return f'{type(obj).__name__}'
    if isinstance(obj, str):
        return f'str(len={len(obj)})'
    if isinstance(obj, list):
        if not obj:
            return 'list(empty)'
        return f'list(len={len(obj)}, [0]={_diagnose_shape(obj[0], depth + 1)})'
    if isinstance(obj, dict):
        parts = []
        for k in list(obj.keys())[:8]:
            parts.append(f'{k}: {_diagnose_shape(obj[k], depth + 1)}')
        return '{' + ', '.join(parts) + '}'
    return type(obj).__name__


def _sn_error_detail(result) -> str:
    """Extract a human-readable error from either response shape."""
    if not isinstance(result, dict):
        return 'no response'
    if result.get('detail'):
        return str(result.get('detail'))
    data = result.get('data') if isinstance(result.get('data'), dict) else {}
    if isinstance(data, dict) and data.get('error'):
        err = data['error']
        if isinstance(err, dict):
            return err.get('message') or err.get('detail') or json.dumps(err)[:300]
        return str(err)
    return (
        result.get('error')
        or result.get('statusText')
        or f"HTTP {result.get('status', '?')}"
    )


def _summarise_proposals(proposals: List[Dict]) -> str:
    """Render the current proposal list as a compact text block for the AI."""
    lines = []
    for p in proposals:
        value = (p.get('value') or '').replace('\n', ' ')
        if len(value) > 240:
            value = value[:240] + '…'
        lines.append(
            f"- [{p.get('kind')}] {p.get('target_field')} "
            f"(source: {p.get('source_rule')}) = {value or '<blank>'}"
        )
    return '\n'.join(lines)


def _summarise_parsed(parsed: dict, max_sheet_chars: int = 800) -> str:
    cells = parsed.get('cells', {}) or {}
    sheets = parsed.get('sheets', {}) or {}
    out = ['parsed_cells:']
    for k, v in sorted(cells.items()):
        v_short = (v or '').replace('\n', ' ')
        if len(v_short) > 200:
            v_short = v_short[:200] + '…'
        out.append(f"  {k}: {v_short}")
    out.append('')
    out.append('parsed_sheets:')
    for name, text in sheets.items():
        head = (text or '')[:max_sheet_chars]
        out.append(f"  --- {name} ---")
        out.append(head)
    return '\n'.join(out)


# ── 1. AI completeness check ────────────────────────────────────

@shared_task(bind=True)
def change_intake_ai_completeness_task(self, body: dict):
    """Run the AI completeness check against the current proposals + parsed payload."""
    from servicenow.models import ChangeIntakeRequest

    intake_id = (body or {}).get('intake_id')
    if not intake_id:
        return {'error': 'missing_intake_id'}

    try:
        intake = ChangeIntakeRequest.objects.get(pk=intake_id)
    except ChangeIntakeRequest.DoesNotExist:
        return {'error': 'intake_not_found', 'intake_id': intake_id}

    parsed = _load(intake.parsed_payload_json) or {}
    proposals = _load(intake.proposals_json) or []

    system = get_prompt('change_intake_completeness')
    user = (
        f"Vendor template: {intake.vendor_template}\n\n"
        f"{_summarise_parsed(parsed)}\n\n"
        f"proposals:\n{_summarise_proposals(proposals)}"
    )

    raw = _call_llm(system, user) or ''
    parsed_result = _extract_json_dict(raw) or {}

    # Defensive: if the AI returned a structural _ai_error, wrap it as a single issue.
    if '_ai_error' in parsed_result:
        result = {
            'ok': False,
            'issues': [{
                'field': 'general',
                'severity': 'error',
                'message': parsed_result['_ai_error'],
            }],
            'suggestions': [],
        }
    else:
        result = {
            'ok': bool(parsed_result.get('ok')),
            'issues': parsed_result.get('issues') or [],
            'suggestions': parsed_result.get('suggestions') or [],
        }

    result['_debug'] = {
        'prompt_system': system,
        'prompt_user': user,
        'raw_response': raw,
        'ran_at': timezone.now().isoformat(),
    }

    intake.ai_completeness_json = json.dumps(result)
    intake.save(update_fields=['ai_completeness_json', 'updated_at'])

    return {'ok': result['ok'], 'intake_id': intake_id}


# ── 1b. Bulk AI extraction (fills all empty non-auto fields) ────

@shared_task(bind=True)
def change_intake_ai_extract_task(self, body: dict):
    """One-shot AI pass over the parsed spreadsheet that proposes values
    for every editable (non-auto) field — particularly useful for parsing
    B7+B8 into ISO start/end dates and inferring category/reason.
    """
    from servicenow.models import ChangeIntakeRequest

    intake_id = (body or {}).get('intake_id')
    if not intake_id:
        return {'error': 'missing_intake_id'}

    try:
        intake = ChangeIntakeRequest.objects.get(pk=intake_id)
    except ChangeIntakeRequest.DoesNotExist:
        return {'error': 'intake_not_found', 'intake_id': intake_id}

    parsed = _load(intake.parsed_payload_json) or {}
    proposals = _load(intake.proposals_json) or []

    editable = [p for p in proposals if p.get('kind') != 'auto']
    editable_summary = [
        {
            'target_field': p.get('target_field'),
            'label': p.get('label'),
            'source_rule': p.get('source_rule'),
            'kind': p.get('kind'),
            'current_value': p.get('value') or '',
        }
        for p in editable
    ]

    # Constrain category + reason to the existing change-creation lists
    # so the AI returns values that match the dropdown options exactly.
    from servicenow.services.creation_templates import (
        load_change_categories, load_change_reasons,
    )
    from servicenow.services.change_intake.dropdowns import DROPDOWN_OPTIONS
    allowed_categories = list(load_change_categories().keys())
    allowed_reasons = list(load_change_reasons().keys())

    system = get_prompt('change_intake_ai_extract')
    user = (
        f"Vendor template: {intake.vendor_template}\n\n"
        f"{_summarise_parsed(parsed)}\n\n"
        f"allowed_categories (use one of these exactly, or empty string):\n"
        f"{json.dumps(allowed_categories)}\n\n"
        f"allowed_reasons (use one of these exactly, or empty string):\n"
        f"{json.dumps(allowed_reasons)}\n\n"
        f"allowed_values_by_field (for these fields, use one of the listed values exactly or an empty string):\n"
        f"{json.dumps(DROPDOWN_OPTIONS, indent=2)}\n\n"
        f"editable_fields:\n{json.dumps(editable_summary, indent=2)}"
    )

    raw = _call_llm(system, user) or ''
    parsed_resp = _extract_json_dict(raw) or {}

    error = ''
    suggested = {}
    if '_ai_error' in parsed_resp:
        error = parsed_resp['_ai_error']
    else:
        raw_fields = parsed_resp.get('fields') or {}
        if isinstance(raw_fields, dict):
            for k, v in raw_fields.items():
                if isinstance(v, str):
                    suggested[k] = v.strip()
                elif v is not None:
                    suggested[k] = str(v).strip()

    # Drop AI category / reason if they don't match the allowed lists —
    # we'd rather leave the field blank than poison the dropdown with a
    # value that won't appear among the options.
    if 'category' in suggested and suggested['category'] not in allowed_categories:
        suggested.pop('category', None)
    if 'reason' in suggested and suggested['reason'] not in allowed_reasons:
        suggested.pop('reason', None)
    # Same defence for the fixed-list dropdowns (outage, testing approach,
    # implementation strategy/approach, backout approach/duration).
    for field_name, allowed in DROPDOWN_OPTIONS.items():
        if field_name in suggested and suggested[field_name] not in allowed:
            suggested.pop(field_name, None)

    # Apply: only fill empty non-auto fields. Don't clobber engineer edits.
    editable_field_names = {p['target_field'] for p in editable}
    applied = []
    for p in proposals:
        if p.get('kind') == 'auto':
            continue
        if p['target_field'] not in suggested:
            continue
        if (p.get('value') or '').strip():
            continue  # engineer (or seed extractor) already provided a value
        if p['target_field'] not in editable_field_names:
            continue
        p['value'] = suggested[p['target_field']]
        applied.append(p['target_field'])

    intake.proposals_json = json.dumps(proposals)

    debug = _load(intake.ai_field_debug_json) or {}
    debug['_ai_extract'] = {
        'prompt_system': system,
        'prompt_user': user,
        'raw_response': raw,
        'suggested': suggested,
        'applied': applied,
        'error': error,
        'ran_at': timezone.now().isoformat(),
    }
    intake.ai_field_debug_json = json.dumps(debug)
    intake.save(update_fields=[
        'proposals_json', 'ai_field_debug_json', 'updated_at',
    ])

    return {
        'ok': not bool(error),
        'applied': applied,
        'suggested_count': len(suggested),
        'error': error,
        'intake_id': intake_id,
    }


# ── 2. Per-field "Generate with AI" ─────────────────────────────

@shared_task(bind=True)
def change_intake_ai_field_generate_task(self, body: dict):
    """Generate (or suggest) a single field value via AI."""
    from servicenow.models import ChangeIntakeRequest

    intake_id = (body or {}).get('intake_id')
    target_field = (body or {}).get('target_field')
    if not (intake_id and target_field):
        return {'error': 'missing_parameter'}

    try:
        intake = ChangeIntakeRequest.objects.get(pk=intake_id)
    except ChangeIntakeRequest.DoesNotExist:
        return {'error': 'intake_not_found', 'intake_id': intake_id}

    parsed = _load(intake.parsed_payload_json) or {}
    proposals = _load(intake.proposals_json) or []

    # Pick a field-specific prompt if registered, otherwise the generic fallback.
    field_key = f'change_intake_field_{target_field}'
    try:
        system = get_prompt(field_key)
    except Exception:
        system = get_prompt('change_intake_field_generic')

    # Two ai-candidates have their own dedicated suggestion prompts.
    if target_field == 'category':
        system = get_prompt('change_intake_category_suggest')
    elif target_field == 'reason':
        system = get_prompt('change_intake_reason_suggest')
    elif target_field in ('start_date', 'end_date'):
        system = get_prompt('change_intake_dates_suggest')

    user = (
        f"target_field: {target_field}\n\n"
        f"{_summarise_parsed(parsed)}\n\n"
        f"current proposals:\n{_summarise_proposals(proposals)}"
    )

    raw = _call_llm(system, user) or ''
    parsed_resp = _extract_json_dict(raw) or {}

    # For the dates prompt the AI returns start_date + end_date together.
    if target_field in ('start_date', 'end_date'):
        suggested_value = (parsed_resp.get(target_field) or '').strip()
    else:
        suggested_value = (parsed_resp.get('value') or '').strip()

    if '_ai_error' in parsed_resp:
        error = parsed_resp['_ai_error']
        suggested_value = ''
    else:
        error = ''

    # Validate category / reason against the existing dropdown lists —
    # otherwise the AI suggestion won't match any <option> and the dropdown
    # silently falls back to blank.
    if target_field == 'category' and suggested_value:
        from servicenow.services.creation_templates import load_change_categories
        if suggested_value not in load_change_categories():
            suggested_value = ''
    elif target_field == 'reason' and suggested_value:
        from servicenow.services.creation_templates import load_change_reasons
        if suggested_value not in load_change_reasons():
            suggested_value = ''
    else:
        from servicenow.services.change_intake.dropdowns import DROPDOWN_OPTIONS
        if target_field in DROPDOWN_OPTIONS and suggested_value:
            if suggested_value not in DROPDOWN_OPTIONS[target_field]:
                suggested_value = ''

    debug = _load(intake.ai_field_debug_json) or {}
    debug[target_field] = {
        'prompt_system': system,
        'prompt_user': user,
        'raw_response': raw,
        'suggested_value': suggested_value,
        'error': error,
        'ran_at': timezone.now().isoformat(),
    }
    intake.ai_field_debug_json = json.dumps(debug)
    intake.save(update_fields=['ai_field_debug_json', 'updated_at'])

    return {
        'target_field': target_field,
        'suggested_value': suggested_value,
        'error': error,
        'intake_id': intake_id,
    }


# ── 3. Submit orchestrator: CR → attachment → CTASK ─────────────

def _content_type_for(filename: str) -> str:
    guess, _ = mimetypes.guess_type(filename)
    if guess:
        return guess
    if filename.lower().endswith('.xlsx'):
        return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    return 'application/octet-stream'


@shared_task(bind=True)
def change_intake_submit_task(self, body: dict):
    """Create CR → attach xlsx → create CTASK, persisting status between steps."""
    from django.conf import settings as dj_settings
    from servicenow.models import ChangeIntakeRequest

    intake_id = (body or {}).get('intake_id')
    if not intake_id:
        return {'error': 'missing_intake_id'}

    try:
        intake = ChangeIntakeRequest.objects.get(pk=intake_id)
    except ChangeIntakeRequest.DoesNotExist:
        return {'error': 'intake_not_found', 'intake_id': intake_id}

    proposals = _load(intake.proposals_json) or []
    if not proposals:
        intake.submit_status = 'error'
        intake.submit_error = 'No proposals to submit. Re-upload the spreadsheet.'
        intake.save(update_fields=['submit_status', 'submit_error', 'updated_at'])
        return {'error': 'no_proposals'}

    cr_fields = fields_for_servicenow(proposals)

    intake.submit_status = 'submitting'
    intake.submit_error = ''
    intake.save(update_fields=['submit_status', 'submit_error', 'updated_at'])

    # ── Step 1: create the CR ──
    def op_create_change(driver):
        return create_change_via_table_api(driver, kind='normal', fields=cr_fields)

    cr_result = with_servicenow_auth_retry(
        body=body, operation=op_create_change, retry_once=True,
    )
    if cr_result.get('error') or cr_result.get('ok') is False:
        intake.submit_status = 'error'
        intake.submit_error = f"CR create failed: {_sn_error_detail(cr_result)}"
        intake.save(update_fields=['submit_status', 'submit_error', 'updated_at'])
        return {'error': 'cr_create_failed', 'detail': intake.submit_error}

    cr_record = _unwrap_sn_record(cr_result)
    if not isinstance(cr_record, dict):
        cr_record = {}
    cr_sys_id = cr_record.get('sys_id') or ''
    cr_number = cr_record.get('number') or ''

    intake.created_chg_sys_id = cr_sys_id
    intake.created_chg_number = cr_number
    intake.submit_status = 'cr_created'
    intake.save(update_fields=[
        'created_chg_sys_id', 'created_chg_number', 'submit_status', 'updated_at',
    ])

    if not cr_sys_id:
        intake.submit_status = 'error'
        intake.submit_error = (
            'CR was created but ServiceNow did not return a sys_id; '
            'cannot continue with attachment/CTASK. '
            f'response shape: {_diagnose_shape(cr_result)}'
        )
        intake.save(update_fields=['submit_status', 'submit_error', 'updated_at'])
        return {'error': 'cr_no_sys_id', 'shape': _diagnose_shape(cr_result)}

    # ── Step 2: upload the xlsx as an attachment ──
    table_name = getattr(dj_settings, 'SERVICENOW_CHANGE_TABLE', 'change_request')
    try:
        with intake.uploaded_file.open('rb') as fh:
            file_bytes = fh.read()
    except Exception as e:
        intake.submit_status = 'error'
        intake.submit_error = f'Could not read uploaded spreadsheet: {e}'
        intake.save(update_fields=['submit_status', 'submit_error', 'updated_at'])
        return {'error': 'read_xlsx_failed'}

    filename = intake.original_filename or 'change_intake.xlsx'
    content_type = _content_type_for(filename)

    def op_attach(driver):
        return upload_attachment_to_record(
            driver,
            table_name=table_name,
            table_sys_id=cr_sys_id,
            file_name=filename,
            file_bytes=file_bytes,
            content_type=content_type,
        )

    attach_result = with_servicenow_auth_retry(
        body=body, operation=op_attach, retry_once=True,
    )
    if attach_result.get('error') or not attach_result.get('ok', True):
        intake.submit_status = 'error'
        intake.submit_error = (
            f"CR {cr_number} was created but spreadsheet attachment failed: "
            f"{attach_result.get('detail') or attach_result.get('error') or attach_result.get('statusText')}"
        )
        intake.save(update_fields=['submit_status', 'submit_error', 'updated_at'])
        return {'error': 'attachment_failed', 'cr_number': cr_number}

    intake.submit_status = 'xlsx_attached'
    intake.save(update_fields=['submit_status', 'updated_at'])

    # ── Step 3: update an auto-created CTASK if one exists, otherwise create. ──
    # Per the locked decision: explicitly copy assignment_group + the inherited
    # short_description / description / planned dates from the CR fields.
    ctask_fields = {
        'short_description': cr_fields.get('short_description', ''),
        'description': cr_fields.get('description', ''),
    }
    if cr_fields.get('assignment_group'):
        ctask_fields['assignment_group'] = cr_fields['assignment_group']
    if cr_fields.get('start_date'):
        ctask_fields['planned_start_date'] = cr_fields['start_date']
    if cr_fields.get('end_date'):
        ctask_fields['planned_end_date'] = cr_fields['end_date']

    def op_list_ctasks(driver):
        return list_tasks_for_change(driver, change_sys_id=cr_sys_id)

    list_result = with_servicenow_auth_retry(
        body=body, operation=op_list_ctasks, retry_once=True,
    )
    existing = []
    if isinstance(list_result, dict) and not list_result.get('error'):
        existing = _unwrap_sn_record(list_result)
        if not isinstance(existing, list):
            existing = []

    if existing:
        first = existing[0] or {}
        existing_sys_id = first.get('sys_id') or ''

        def op_patch_ctask(driver):
            return patch_change_task(
                driver,
                sys_id=existing_sys_id,
                fields_to_patch=ctask_fields,
            )

        ctask_result = with_servicenow_auth_retry(
            body=body, operation=op_patch_ctask, retry_once=True,
        )
        ctask_action = 'updated'
    else:
        def op_ctask(driver):
            return create_change_task_via_table_api(
                driver,
                parent_change_sys_id=cr_sys_id,
                fields=ctask_fields,
            )

        ctask_result = with_servicenow_auth_retry(
            body=body, operation=op_ctask, retry_once=True,
        )
        ctask_action = 'created'

    if ctask_result.get('error') or ctask_result.get('ok') is False:
        intake.submit_status = 'error'
        intake.submit_error = (
            f"CR {cr_number} created and spreadsheet attached, but CTASK {ctask_action} failed: "
            f"{_sn_error_detail(ctask_result)}"
        )
        intake.save(update_fields=['submit_status', 'submit_error', 'updated_at'])
        return {'error': f'ctask_{ctask_action}_failed', 'cr_number': cr_number}

    ctask_record = _unwrap_sn_record(ctask_result)
    if not isinstance(ctask_record, dict):
        ctask_record = {}
    intake.created_ctask_sys_id = ctask_record.get('sys_id') or (existing[0].get('sys_id') if existing else '')
    intake.created_ctask_number = ctask_record.get('number') or (existing[0].get('number') if existing else '')
    intake.submit_status = 'done'
    intake.save(update_fields=[
        'created_ctask_sys_id', 'created_ctask_number',
        'submit_status', 'updated_at',
    ])

    return {
        'ok': True,
        'cr_number': intake.created_chg_number,
        'ctask_number': intake.created_ctask_number,
        'ctask_action': ctask_action,  # 'updated' or 'created'
        'intake_id': intake_id,
    }

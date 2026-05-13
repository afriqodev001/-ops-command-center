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
from servicenow.tasks import with_servicenow_auth_retry


# ── Helpers ─────────────────────────────────────────────────────

def _load(text: str) -> dict | list:
    if not text:
        return {}
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return {}


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

    cr_fields = fields_for_servicenow(proposals, intake.vendor_template)

    intake.submit_status = 'submitting'
    intake.submit_error = ''
    intake.save(update_fields=['submit_status', 'submit_error', 'updated_at'])

    # ── Step 1: create the CR ──
    def op_create_change(driver):
        return create_change_via_table_api(driver, kind='normal', fields=cr_fields)

    cr_result = with_servicenow_auth_retry(
        body=body, operation=op_create_change, retry_once=True,
    )
    if cr_result.get('error'):
        intake.submit_status = 'error'
        intake.submit_error = f"CR create failed: {cr_result.get('detail') or cr_result.get('error')}"
        intake.save(update_fields=['submit_status', 'submit_error', 'updated_at'])
        return {'error': 'cr_create_failed', 'detail': intake.submit_error}

    cr_record = (cr_result.get('result') or {}).get('result') or cr_result.get('result') or {}
    # ServiceNow's table API typically returns {result: {sys_id, number, ...}}; handle both shapes.
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
            'cannot continue with attachment/CTASK.'
        )
        intake.save(update_fields=['submit_status', 'submit_error', 'updated_at'])
        return {'error': 'cr_no_sys_id'}

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

    # ── Step 3: create the CTASK ──
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

    def op_ctask(driver):
        return create_change_task_via_table_api(
            driver,
            parent_change_sys_id=cr_sys_id,
            fields=ctask_fields,
        )

    ctask_result = with_servicenow_auth_retry(
        body=body, operation=op_ctask, retry_once=True,
    )
    if ctask_result.get('error'):
        intake.submit_status = 'error'
        intake.submit_error = (
            f"CR {cr_number} created and spreadsheet attached, but CTASK create failed: "
            f"{ctask_result.get('detail') or ctask_result.get('error')}"
        )
        intake.save(update_fields=['submit_status', 'submit_error', 'updated_at'])
        return {'error': 'ctask_create_failed', 'cr_number': cr_number}

    ctask_record = (ctask_result.get('result') or {}).get('result') or ctask_result.get('result') or {}
    if not isinstance(ctask_record, dict):
        ctask_record = {}
    intake.created_ctask_sys_id = ctask_record.get('sys_id') or ''
    intake.created_ctask_number = ctask_record.get('number') or ''
    intake.submit_status = 'done'
    intake.save(update_fields=[
        'created_ctask_sys_id', 'created_ctask_number',
        'submit_status', 'updated_at',
    ])

    return {
        'ok': True,
        'cr_number': intake.created_chg_number,
        'ctask_number': intake.created_ctask_number,
        'intake_id': intake_id,
    }

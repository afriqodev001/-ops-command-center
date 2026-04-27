"""
Oncall change review — orchestration layer.

Stitches together:
- ServiceNow change fetch (servicenow.tasks.change_context_task)
- Suppression matrix lookup (services.suppression_matrix.lookup)
- AI review (services.ai_assist._call_llm + prompt_store.get_prompt('oncall_outage_review'))

…and persists everything onto OncallChangeReview rows.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from django.utils import timezone as dj_tz

from ..models import (
    OncallChangeReview,
    ONCALL_STAGES,
    ONCALL_STAGE_INDEX,
    ONCALL_STAGE_VALUES,
)
from . import suppression_matrix as matrix
from .ai_assist import _call_llm, _extract_json_dict
from .prompt_store import get_prompt


# ─── Reads (used by cross-surface partials) ───────────────

def get_for_change(change_number: str) -> Optional[OncallChangeReview]:
    """Most-recent review for a change number, or None.

    A change can be reviewed in multiple windows; we surface the latest
    one because that's the one that's actually current for oncall.
    """
    if not change_number:
        return None
    return (
        OncallChangeReview.objects
        .filter(change_number=change_number)
        .order_by('-window_end', '-updated_at')
        .first()
    )


# ─── Helpers ──────────────────────────────────────────────

def _iso_to_dt(raw: Any) -> Optional[datetime]:
    """ServiceNow returns 'YYYY-MM-DD HH:MM:SS' (UTC) or already-formatted strings."""
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    s = str(raw).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _val(field) -> str:
    """ServiceNow returns either a flat string or {'value': ..., 'display_value': ...}."""
    if field is None:
        return ''
    if isinstance(field, dict):
        return str(field.get('display_value') or field.get('value') or '').strip()
    return str(field).strip()


# ─── Pull → upsert into DB ────────────────────────────────

def upsert_pulled_changes(
    rows: List[Dict[str, Any]],
    *,
    window_start: datetime,
    window_end: datetime,
    window_label: str = '',
) -> List[OncallChangeReview]:
    """
    Insert (or refresh-pull-fields) rows from a ServiceNow query result.

    Engineer-set fields (stage, comments, AI verdict, action timestamps)
    are NEVER overwritten on re-pull — only identity / scheduling fields.
    """
    out: List[OncallChangeReview] = []

    for row in rows or []:
        number = _val(row.get('number'))
        if not number:
            continue

        defaults_on_create = {
            'window_start': window_start,
            'window_end': window_end,
            'window_label': window_label,
        }

        review, created = OncallChangeReview.objects.get_or_create(
            change_number=number,
            window_start=window_start,
            window_end=window_end,
            defaults=defaults_on_create,
        )

        # Always refresh these fields from the source — they reflect the
        # current ServiceNow state, not engineer state.
        review.sys_id = _val(row.get('sys_id'))
        review.short_description = _val(row.get('short_description'))[:512]
        review.risk = _val(row.get('risk'))
        review.assignment_group = _val(row.get('assignment_group'))[:128]
        review.cmdb_ci = _val(row.get('cmdb_ci'))[:128]
        review.scheduled_start = _iso_to_dt(row.get('start_date'))
        review.scheduled_end = _iso_to_dt(row.get('end_date'))
        review.window_label = window_label or review.window_label

        # First time we've seen this change — apply matrix snapshot now so
        # the engineer sees the matched info even before AI runs.
        if created:
            apply_matrix_match(review, row=row, save=False)

        review.save()
        out.append(review)

    return out


def apply_matrix_match(
    review: OncallChangeReview,
    *,
    row: Optional[Dict[str, Any]] = None,
    save: bool = True,
) -> Optional[Dict[str, Any]]:
    """Look up suppression matrix entry, store snapshot on review.

    Denormalises the structured matrix row onto OncallChangeReview so the
    review record stays meaningful even if the matrix changes later.
    matched_emails reflects the full union (base + per-app additional).
    """
    lookup_input = row or {
        'cmdb_ci': review.cmdb_ci,
        'short_description': review.short_description,
    }
    match = matrix.lookup(lookup_input)
    if match:
        review.matched_app = (match.get('application') or '')[:256]
        review.matched_impact = matrix.impact_text_for(match)
        review.matched_emails = '; '.join(matrix.all_recipients_for(match))
        review.matched_suppr_ids = '; '.join(match.get('suppression_records') or [])
        review.matched_banner = bool(match.get('banner'))
        review.matched_banner_msg = match.get('banner_message') or ''
    else:
        review.matched_app = ''
        review.matched_impact = ''
        review.matched_emails = ''
        review.matched_suppr_ids = ''
        review.matched_banner = False
        review.matched_banner_msg = ''

    if save:
        review.save(update_fields=[
            'matched_app', 'matched_impact', 'matched_emails',
            'matched_suppr_ids', 'matched_banner', 'matched_banner_msg',
            'updated_at',
        ])
    return match


# ─── AI review ────────────────────────────────────────────

def build_review_prompt(review: OncallChangeReview, change_record: Dict[str, Any]) -> str:
    """Compose the user-prompt sent to the LLM."""
    matched = matrix.lookup(change_record) or matrix.lookup({
        'cmdb_ci': review.cmdb_ci,
        'short_description': review.short_description,
    })

    sections: List[str] = []

    sections.append(f'CHANGE RECORD:')
    sections.append(json.dumps({
        'number': review.change_number,
        'short_description': review.short_description,
        'risk': review.risk,
        'assignment_group': review.assignment_group,
        'cmdb_ci': review.cmdb_ci,
        'scheduled_start': str(review.scheduled_start) if review.scheduled_start else None,
        'scheduled_end': str(review.scheduled_end) if review.scheduled_end else None,
        'description': _val((change_record or {}).get('description')),
        'justification': _val((change_record or {}).get('justification')),
        'implementation_plan': _val((change_record or {}).get('implementation_plan')),
        'backout_plan': _val((change_record or {}).get('backout_plan')),
        'test_plan': _val((change_record or {}).get('test_plan')),
        'type': _val((change_record or {}).get('type')),
    }, default=str, indent=2))

    sections.append('')
    sections.append('SUPPRESSION MATRIX ENTRY:')
    if matched:
        sections.append(json.dumps(matched, indent=2, default=str))
    else:
        sections.append('(none — no matrix entry matched this CI / application)')

    return '\n'.join(sections)


def run_ai_review_for(review: OncallChangeReview, change_record: Dict[str, Any]) -> Dict[str, Any]:
    """Run the AI review synchronously and persist the result to the row.

    Returns the parsed AI payload for the caller to use, or
    {'_ai_error': '...'} on failure.
    """
    system = get_prompt('oncall_outage_review')
    user_prompt = build_review_prompt(review, change_record)

    raw = _call_llm(system, user_prompt) or ''
    parsed = _extract_json_dict(raw) or {}

    if parsed.get('_ai_error'):
        review.ai_summary = parsed['_ai_error']
        review.ai_run_at = dj_tz.now()
        review.save(update_fields=['ai_summary', 'ai_run_at', 'updated_at'])
        return parsed

    verdict = (parsed.get('outage_likely') or 'unknown').lower()
    if verdict not in ('yes', 'no', 'maybe'):
        verdict = 'unknown'

    review.ai_outage_likely = verdict
    review.ai_summary = (parsed.get('summary_markdown') or parsed.get('reasoning') or raw or '').strip()
    review.ai_payload_json = json.dumps(parsed, default=str)
    review.ai_run_at = dj_tz.now()

    if review.stage == 'pulled':
        review.stage = 'ai_reviewed'

    review.save(update_fields=[
        'ai_outage_likely', 'ai_summary', 'ai_payload_json',
        'ai_run_at', 'stage', 'updated_at',
    ])
    return parsed


# ─── Stage advancement ────────────────────────────────────

def advance_stage(review: OncallChangeReview, target: str, *, by: str = '') -> OncallChangeReview:
    """Set stage, never moving backwards. Updates `reviewed_by` + timestamps."""
    if target not in ONCALL_STAGE_VALUES:
        return review
    cur_idx = review.stage_order
    new_idx = ONCALL_STAGE_INDEX[target]
    if new_idx > cur_idx:
        review.stage = target
    if by:
        review.reviewed_by = by

    now = dj_tz.now()
    if target == 'comms_drafted' and not review.email_drafted_at:
        review.email_drafted_at = now
    elif target == 'comms_sent' and not review.email_sent_at:
        review.email_sent_at = now
    elif target == 'suppressions_done' and not review.suppressions_done_at:
        review.suppressions_done_at = now
    elif target == 'banner_posted' and not review.banner_posted_at:
        review.banner_posted_at = now

    review.save()
    return review

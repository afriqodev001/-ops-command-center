"""
Epsilon vendor mapping — cells/tabs from the standard Epsilon spreadsheet
mapped to ServiceNow change_request fields.

Cells (Sheet1):
  B5   vendor name
  B7   date
  B8   install duration / timing window (free-text)
  B9   environment
  B10  event description / reason
  B12  event type
  B13  outage yes/no
  B15  executive summary
  B18  impacts
  B27  implementation plan ref
  B29  rollback ref
  B32  why now

Tabs:
  'Implementation Plan'  full text → install steps
  'Roll Back Plan'       full text → backout steps
"""
from __future__ import annotations

from ..mapping_spec import FieldRule, VendorMapping, ParsedPayload, register


def _cell(p: ParsedPayload, key: str) -> str:
    return (p.cells.get(key) or '').strip()


def _sheet(p: ParsedPayload, name: str) -> str:
    return (p.sheets.get(name) or '').strip()


def _short_description(p: ParsedPayload) -> str:
    env = _cell(p, 'B9')
    vendor = _cell(p, 'B5')
    event = _cell(p, 'B12')
    parts = [x for x in (env, vendor, event) if x]
    return ' - '.join(parts)


def _outage_summary(p: ParsedPayload) -> str:
    raw = _cell(p, 'B13').lower()
    if not raw:
        return ''
    if any(w in raw for w in ('full', 'partial', 'yes')):
        return 'Full outage'
    if 'no' in raw:
        return 'None expected'
    return raw


EPSILON_MAPPING = VendorMapping(
    name='Epsilon',
    rules=[
        # ── Auto fields ────────────────────────────────────────
        FieldRule(
            target_field='short_description',
            label='Short description',
            source_rule='B9 (Environment) - B5 (Vendor) - B12 (Event Type)',
            kind='auto',
            group='Identity',
            extractor=_short_description,
        ),
        FieldRule(
            target_field='implementation_plan',
            label='Implementation plan',
            source_rule="Sheet 'Implementation Plan' — full text",
            kind='auto',
            group='Planning',
            extractor=lambda p: _sheet(p, 'Implementation Plan'),
        ),
        FieldRule(
            target_field='backout_plan',
            label='Backout plan',
            source_rule="Sheet 'Roll Back Plan' — full text",
            kind='auto',
            group='Planning',
            extractor=lambda p: _sheet(p, 'Roll Back Plan'),
        ),
        FieldRule(
            target_field='u_outage',
            label='Outage status',
            source_rule='B13 (Outage yes/no)',
            kind='auto',
            group='Planning',
            extractor=_outage_summary,
        ),
        # The combined `description` field is special — it is assembled
        # from many sub-sections (including human-input ones) inside
        # mapping_apply.build_description AFTER the engineer edits
        # individual section values. The extractor here returns the
        # initial assembly from auto sources only.
        FieldRule(
            target_field='description',
            label='Description (combined)',
            source_rule=(
                'Structured template: Executive Summary (B15) + Impacts (B18) + '
                'Why now (B32) + Outage (B13) + Implementation Plan + Backout Plan '
                '+ TODO placeholders for empty human-input sections'
            ),
            kind='auto',
            group='Description',
            extractor=lambda p: '',  # filled in by mapping_apply.build_description
        ),

        # ── AI-candidate fields ────────────────────────────────
        FieldRule(
            target_field='category',
            label='Category',
            source_rule='Depends on change — AI suggestion from B10 + B12',
            kind='ai-candidate',
            group='Identity',
            extractor=lambda p: '',
        ),
        FieldRule(
            target_field='reason',
            label='Reason',
            source_rule='Depends on change — AI suggestion from B10 + B12',
            kind='ai-candidate',
            group='Identity',
            extractor=lambda p: '',
        ),
        FieldRule(
            target_field='start_date',
            label='Planned start',
            source_rule='B7 (date) + B8 (duration / start time) — engineer reviews',
            kind='ai-candidate',
            group='Schedule',
            extractor=lambda p: '',
        ),
        FieldRule(
            target_field='end_date',
            label='Planned end',
            source_rule='B7 + B8 (computed end) — engineer reviews',
            kind='ai-candidate',
            group='Schedule',
            extractor=lambda p: '',
        ),

        # ── Human-input fields ─────────────────────────────────
        FieldRule(
            target_field='cmdb_ci',
            label='Configuration item',
            source_rule='Depends on vendor — usually B9 (Environment)',
            kind='human-input',
            group='Identity',
            extractor=lambda p: _cell(p, 'B9'),
        ),
        FieldRule(
            target_field='assignment_group',
            label='Assignment group',
            source_rule='Depends on change (e.g. EPSLN-VSS / Loyalty Platform Support)',
            kind='human-input',
            group='Identity',
            extractor=lambda p: '',
        ),
        FieldRule(
            target_field='test_plan',
            label='Testing strategy',
            source_rule='<human input> — depends on the change',
            kind='human-input',
            group='Planning',
            extractor=lambda p: '',
        ),
        FieldRule(
            target_field='u_implementation_strategy',
            label='Implementation strategy',
            source_rule='<human input> — depends on the change',
            kind='human-input',
            group='Planning',
            extractor=lambda p: '',
        ),
        FieldRule(
            target_field='u_implementation_approach',
            label='Implementation approach',
            source_rule='<human input> — depends on the change',
            kind='human-input',
            group='Planning',
            extractor=lambda p: '',
        ),
        FieldRule(
            target_field='u_who_will_install',
            label='Who will install',
            source_rule='<human input> — individual or group',
            kind='human-input',
            group='People',
            extractor=lambda p: _cell(p, 'B5'),
        ),
        FieldRule(
            target_field='u_who_will_validate',
            label='Who will validate',
            source_rule='<human input> — individual or group',
            kind='human-input',
            group='People',
            extractor=lambda p: '',
        ),

        # ── Hidden helper fields used only by the description builder.
        # Kept as human-input so engineers can edit them inline; their
        # values are folded into the combined `description` at submit.
        FieldRule(
            target_field='_executive_summary',
            label='Executive summary',
            source_rule='B15',
            kind='auto',
            group='Description',
            extractor=lambda p: _cell(p, 'B15'),
        ),
        FieldRule(
            target_field='_benefit',
            label='Benefit / advantage',
            source_rule='<human input> — business/customer perspective',
            kind='human-input',
            group='Description',
            extractor=lambda p: '',
        ),
        FieldRule(
            target_field='_why_now',
            label='Why now',
            source_rule='B32',
            kind='auto',
            group='Description',
            extractor=lambda p: _cell(p, 'B32'),
        ),
        FieldRule(
            target_field='_impacts_if_not_installed',
            label='Impacts if not installed',
            source_rule='B18 (and B13 for outage context)',
            kind='auto',
            group='Description',
            extractor=lambda p: _cell(p, 'B18'),
        ),
        FieldRule(
            target_field='_install_steps',
            label='Install steps',
            source_rule="Sheet 'Implementation Plan' + B27",
            kind='auto',
            group='Description',
            extractor=lambda p: _sheet(p, 'Implementation Plan') or _cell(p, 'B27'),
        ),
        FieldRule(
            target_field='_install_duration',
            label='Install duration',
            source_rule='B8',
            kind='auto',
            group='Description',
            extractor=lambda p: _cell(p, 'B8'),
        ),
        FieldRule(
            target_field='_backout_steps',
            label='Backout steps',
            source_rule="Sheet 'Roll Back Plan' + B29",
            kind='auto',
            group='Description',
            extractor=lambda p: _sheet(p, 'Roll Back Plan') or _cell(p, 'B29'),
        ),
    ],
)


register('epsilon', EPSILON_MAPPING)

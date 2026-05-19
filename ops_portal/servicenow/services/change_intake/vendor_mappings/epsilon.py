"""
Epsilon vendor mapping — cells/tabs from the standard Epsilon spreadsheet
mapped to ServiceNow change_request fields.

The first sheet is named 'Change Details'. Column A holds labels,
column B holds values, column C is example/hint text we ignore.

Cells used (Change Details):
  B5   Vendor Name                                 ("Epsilon")
  B7   Change Date                                 ("5/12/2026 - 5/13/2026")
  B8   Time (ET)                                   ("11:30 PM - 7:00 AM ET")
  B9   Environment                                 ("PROD/DR")
  B10  Event Description/Reason*                   ("Certificate Renewal (wfsaml2ping)")
  B12  Event Type*                                 ("Certificate Renewal")
  B13  Outage                                      ("Yes" / "No")
  B15  Scope of the changes / functionalities impacted
  B18  Error Handling
  B27  Plan for Production Validation
  B29  Rollback strategy/playbook and MTTR
  B32  Why Now?

Tabs (besides 'Change Details'):
  'List of Components'
  'Impact Assessment'
  'Implementation Plan'    full install steps
  'Roll Back Plan'         full backout steps
  'Validation Plan'

Long-form fields (`description`, `justification`, `implementation_plan`,
`backout_plan`) are built from editable templates stored in the prompt
store (keys: `change_intake_template_<field>`) using a tiny template
engine that substitutes `{Bnn}` and `{sheet:Name}` placeholders and
leaves `<human input>` markers in place for the engineer to fill in.
"""
from __future__ import annotations

from ..mapping_spec import FieldRule, VendorMapping, ParsedPayload, register
from ..template_render import render_template


def _cell(p: ParsedPayload, key: str) -> str:
    return (p.cells.get(key) or '').strip()


def _short_description(p: ParsedPayload) -> str:
    """Short description = B9 - B5 - B12 - B10 per the mapping notes."""
    parts = [_cell(p, k) for k in ('B9', 'B5', 'B12', 'B10')]
    return ' - '.join(x for x in parts if x)


def _outage_value(p: ParsedPayload) -> str:
    """B13 → one of the Outage dropdown values."""
    raw = _cell(p, 'B13').lower()
    if not raw:
        return ''
    if 'partial' in raw:
        return 'Partial'
    if 'yes' in raw or 'full' in raw:
        return 'Full'
    if 'no' in raw:
        return 'None Expected'
    return ''


EPSILON_MAPPING = VendorMapping(
    name='Epsilon',
    rules=[
        # ── Auto fields (from cells) ───────────────────────────
        FieldRule(
            target_field='short_description',
            label='Short description',
            source_rule='B9 (Environment) - B5 (Vendor) - B12 (Event Type) - B10 (Event Description)',
            kind='auto',
            group='Identity',
            extractor=_short_description,
        ),
        FieldRule(
            target_field='u_outage',
            label='Outage',
            source_rule="B13 → 'Full' if Yes, 'None Expected' if No",
            kind='auto',
            group='Planning',
            extractor=_outage_value,
        ),

        # ── Auto fields (template-rendered, editable via prompt store) ─
        # These render with `<human input>` markers when the spreadsheet
        # doesn't provide content for those sub-questions. The engineer
        # replaces the marker text in the textarea before submit; the
        # submit endpoint refuses to dispatch if any markers remain.
        FieldRule(
            target_field='description',
            label='Description',
            source_rule="Template (edit at /servicenow/prompts/ → 'change_intake_template_description')",
            kind='auto',
            group='Identity',
            extractor=lambda p: render_template('change_intake_template_description', p),
        ),
        FieldRule(
            target_field='justification',
            label='Justification',
            source_rule="Template (edit at /servicenow/prompts/ → 'change_intake_template_justification')",
            kind='auto',
            group='Planning',
            extractor=lambda p: render_template('change_intake_template_justification', p),
        ),
        FieldRule(
            target_field='implementation_plan',
            label='Implementation plan',
            source_rule="Template (edit at /servicenow/prompts/ → 'change_intake_template_implementation_plan')",
            kind='auto',
            group='Planning',
            extractor=lambda p: render_template('change_intake_template_implementation_plan', p),
        ),
        FieldRule(
            target_field='backout_plan',
            label='Backout plan',
            source_rule="Template (edit at /servicenow/prompts/ → 'change_intake_template_backout_plan')",
            kind='auto',
            group='Planning',
            extractor=lambda p: render_template('change_intake_template_backout_plan', p),
        ),

        # ── Auto fields (vendor defaults from VendorConfig) ────
        # Extractors return empty strings; values come from the per-vendor
        # config (Change Intake → Vendor Defaults). Engineer can override
        # by editing the textarea.
        FieldRule(
            target_field='cmdb_ci',
            label='Configuration item',
            source_rule='Vendor default (e.g. Epsilon → "Epsilon - EPSLN - VSS")',
            kind='auto',
            group='Identity',
            extractor=lambda p: '',
        ),
        FieldRule(
            target_field='assignment_group',
            label='Assignment group',
            source_rule='Vendor default (e.g. Epsilon → "CTUMLS:Loyalty Platform Support")',
            kind='auto',
            group='Identity',
            extractor=lambda p: '',
        ),
        FieldRule(
            target_field='u_code_change',
            label='Code change',
            source_rule="Vendor default (Epsilon → 'No')",
            kind='auto',
            group='Identity',
            extractor=lambda p: '',
        ),

        # ── AI-candidate fields (filled by Extract with AI) ────
        FieldRule(
            target_field='category',
            label='Category',
            source_rule='AI-inferred from B10 (Event Description) + B12 (Event Type)',
            kind='ai-candidate',
            group='Identity',
            extractor=lambda p: '',
        ),
        FieldRule(
            target_field='reason',
            label='Reason',
            source_rule='AI-inferred from B10 + B12',
            kind='ai-candidate',
            group='Identity',
            extractor=lambda p: '',
        ),
        FieldRule(
            target_field='start_date',
            label='Planned start',
            source_rule='AI-parsed from B7 (date range) + B8 (time window in ET)',
            kind='ai-candidate',
            group='Schedule',
            extractor=lambda p: '',
        ),
        FieldRule(
            target_field='end_date',
            label='Planned end',
            source_rule='AI-parsed from B7 (date range) + B8 (time window in ET)',
            kind='ai-candidate',
            group='Schedule',
            extractor=lambda p: '',
        ),

        # ── Human-input fields ─────────────────────────────────
        FieldRule(
            target_field='u_testing_approach',
            label='Testing approach',
            source_rule='<human input> — engineer fills in',
            kind='human-input',
            group='Planning',
            extractor=lambda p: '',
        ),
        FieldRule(
            target_field='u_implementation_strategy',
            label='Implementation strategy',
            source_rule='<human input> — engineer fills in',
            kind='human-input',
            group='Planning',
            extractor=lambda p: '',
        ),
        FieldRule(
            target_field='u_implementation_approach',
            label='Implementation approach',
            source_rule='<human input> — engineer fills in',
            kind='human-input',
            group='Planning',
            extractor=lambda p: '',
        ),
        FieldRule(
            target_field='u_backout_approach',
            label='Backout approach',
            source_rule='<human input> — engineer fills in',
            kind='human-input',
            group='Planning',
            extractor=lambda p: '',
        ),
        FieldRule(
            target_field='u_backout_duration',
            label='Backout duration',
            source_rule='<human input> — engineer fills in',
            kind='human-input',
            group='Planning',
            extractor=lambda p: '',
        ),
    ],
)


register('epsilon', EPSILON_MAPPING)

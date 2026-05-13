"""
Epsilon vendor mapping — based on the actual Epsilon change spreadsheet.

The spreadsheet has six tabs:
  'Change Details'       labels in col A, values in col B, format hints in col C
  'List of Components'   inventory / CIs touched
  'Impact Assessment'    free-form impact analysis
  'Implementation Plan'  numbered install steps
  'Roll Back Plan'       numbered rollback steps
  'Validation Plan'      numbered validation steps

Change Details rows used (verified from screenshots):
  B5   Vendor Name                                      (e.g. Epsilon)
  B6   Date of Change Notification                      (MM/DD/YYYY)
  B7   Change Date                                      (MM/DD/YYYY [- MM/DD/YYYY])
  B8   Time (ET)                                        (HH:MM AM - HH:MM AM ET)
  B9   Environment                                      (PROD/DR)
  B10  Event Description/Reason *                       (free text)
  B11  Content Only *                                   (Yes/No)
  B12  Event Type *                                     (Cert Renewal / Patching / Upgrades / Defect Fix)
  B13  Outage                                           (Yes/No)
  B14  Risk Level                                       (L / M / H)
  B15  Scope of changes (customer perspective)          (long text)
  B16  Sign-off received from all impacted teams        (Yes/No)
  B17  Alert configuration                              (monitoring + manual testing notes)
  B18  Error Handling                                   (free text)
  B19  DB Change                                        (Yes/No)
  B20  FSD Attached?                                    (Yes/No/NA)
  B21  Testing document attached?                       (Yes/No/NA)
  B22  Environment Predecessors                         (free text — where else has this run)
  B23  Overview of Pre-Prod Tests Completed             (free text)
  B24  UAT Testing and Signoff                          (Yes/No)
  B25  Regression Testing                               (Yes/No/NA)
  B26  Performance Testing                              (Yes/No/NA)
  B27  Plan for Production Validation                   (long text — references Validation Plan tab)
  B28  Roll-back Plan Attached                          (Yes/No)
  B29  Rollback strategy/playbook and MTTR              (free text — references Roll Back Plan tab)
  B30  Product Team Owner/Sign-Off                      (name)
  B31  List of Components                               (refs List of Components tab)
  B32  Why Now?                                         (free text)
  B34  Note                                             (approval/release prerequisites)
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
    event_type = _cell(p, 'B12')
    event_desc = _cell(p, 'B10')

    head = ' - '.join(x for x in (env, vendor, event_type) if x)
    if event_desc and event_desc.lower() != (event_type or '').lower():
        return f'{head}: {event_desc}' if head else event_desc
    return head


def _outage_summary(p: ParsedPayload) -> str:
    raw = _cell(p, 'B13').lower()
    if not raw:
        return ''
    if 'full' in raw or 'partial' in raw or raw.startswith('yes'):
        return 'Full outage'
    if raw.startswith('no'):
        return 'None expected'
    return _cell(p, 'B13')


def _risk_level(p: ParsedPayload) -> str:
    """Map L/M/H to ServiceNow risk values."""
    raw = _cell(p, 'B14').lower()
    if raw.startswith('h'):
        return 'High'
    if raw.startswith('m'):
        return 'Moderate'
    if raw.startswith('l'):
        return 'Low'
    return ''


def _testing_overview(p: ParsedPayload) -> str:
    """Combine the Pre-Prod Tests Completed (B23) row + the individual
    UAT/Regression/Performance lines into a single test-overview block."""
    parts = []
    pre_prod = _cell(p, 'B23')
    if pre_prod:
        parts.append(pre_prod)
    flags = []
    if _cell(p, 'B24'):
        flags.append(f"UAT testing: {_cell(p, 'B24')}")
    if _cell(p, 'B25'):
        flags.append(f"Regression: {_cell(p, 'B25')}")
    if _cell(p, 'B26'):
        flags.append(f"Performance: {_cell(p, 'B26')}")
    if flags:
        parts.append(' | '.join(flags))
    return '\n'.join(parts)


def _validation_plan(p: ParsedPayload) -> str:
    """Validation steps come from B27 + the 'Validation Plan' tab."""
    b27 = _cell(p, 'B27')
    tab = _sheet(p, 'Validation Plan')
    parts = [x for x in (b27, tab) if x]
    return '\n\n'.join(parts)


def _backout_steps(p: ParsedPayload) -> str:
    b29 = _cell(p, 'B29')
    tab = _sheet(p, 'Roll Back Plan')
    parts = [x for x in (b29, tab) if x]
    return '\n\n'.join(parts)


def _impacts_if_not_installed(p: ParsedPayload) -> str:
    """The 'impacts if this change doesn't install' question is best answered
    from B32 (why now — explains the consequence of NOT doing the change)
    plus B15 (scope / customer perspective)."""
    parts = []
    if _cell(p, 'B32'):
        parts.append(_cell(p, 'B32'))
    if _cell(p, 'B15'):
        parts.append(_cell(p, 'B15'))
    return '\n\n'.join(parts)


def _planned_window(p: ParsedPayload) -> str:
    """Just the raw B7 + B8 strings, joined. Engineers verify and edit this
    before submit; we don't parse it heuristically."""
    parts = []
    if _cell(p, 'B7'):
        parts.append(_cell(p, 'B7'))
    if _cell(p, 'B8'):
        parts.append(_cell(p, 'B8'))
    return ' / '.join(parts)


EPSILON_MAPPING = VendorMapping(
    name='Epsilon',
    rules=[
        # ── Identity ───────────────────────────────────────────
        FieldRule(
            target_field='short_description',
            label='Short description',
            source_rule="B9 (Environment) - B5 (Vendor) - B12 (Event Type): B10 (Event Description)",
            kind='auto',
            group='Identity',
            extractor=_short_description,
        ),
        FieldRule(
            target_field='risk',
            label='Risk level',
            source_rule='B14 (Risk Level) — L/M/H → Low/Moderate/High',
            kind='auto',
            group='Identity',
            extractor=_risk_level,
        ),
        FieldRule(
            target_field='category',
            label='Category',
            source_rule='AI suggestion from B10 + B12 + B19 (DB Change flag)',
            kind='ai-candidate',
            group='Identity',
            extractor=lambda p: '',
        ),
        FieldRule(
            target_field='reason',
            label='Reason',
            source_rule='AI suggestion from B12 (Event Type) — e.g. Patching, Defect Fix',
            kind='ai-candidate',
            group='Identity',
            extractor=lambda p: '',
        ),
        FieldRule(
            target_field='cmdb_ci',
            label='Configuration item',
            source_rule="B9 (Environment) + List of Components tab — engineer picks",
            kind='human-input',
            group='Identity',
            extractor=lambda p: _cell(p, 'B9'),
        ),
        FieldRule(
            target_field='assignment_group',
            label='Assignment group',
            source_rule='Depends on vendor (Epsilon → EPSLN-VSS / Loyalty Platform Support)',
            kind='human-input',
            group='Identity',
            extractor=lambda p: '',
        ),

        # ── Schedule ───────────────────────────────────────────
        FieldRule(
            target_field='start_date',
            label='Planned start',
            source_rule='B7 (Change Date) + B8 (Time ET) — engineer reviews + sets ISO format',
            kind='ai-candidate',
            group='Schedule',
            extractor=lambda p: '',
        ),
        FieldRule(
            target_field='end_date',
            label='Planned end',
            source_rule='B7 + B8 — engineer reviews + sets ISO format',
            kind='ai-candidate',
            group='Schedule',
            extractor=lambda p: '',
        ),

        # ── People ─────────────────────────────────────────────
        FieldRule(
            target_field='u_who_will_install',
            label='Who will install',
            source_rule='B5 (Vendor) + B30 (Product Team Owner) — engineer confirms',
            kind='human-input',
            group='People',
            extractor=lambda p: ' / '.join(x for x in (_cell(p, 'B5'), _cell(p, 'B30')) if x),
        ),
        FieldRule(
            target_field='u_who_will_validate',
            label='Who will validate',
            source_rule='B30 (Product Team Owner) — engineer confirms',
            kind='human-input',
            group='People',
            extractor=lambda p: _cell(p, 'B30'),
        ),

        # ── Planning (top-level SN fields) ─────────────────────
        FieldRule(
            target_field='implementation_plan',
            label='Implementation plan',
            source_rule="Sheet 'Implementation Plan' — full text (numbered steps)",
            kind='auto',
            group='Planning',
            extractor=lambda p: _sheet(p, 'Implementation Plan'),
        ),
        FieldRule(
            target_field='backout_plan',
            label='Backout plan',
            source_rule="B29 + Sheet 'Roll Back Plan' — full text",
            kind='auto',
            group='Planning',
            extractor=_backout_steps,
        ),
        FieldRule(
            target_field='test_plan',
            label='Test / validation plan',
            source_rule="B27 + Sheet 'Validation Plan' — full text",
            kind='auto',
            group='Planning',
            extractor=_validation_plan,
        ),
        FieldRule(
            target_field='u_outage',
            label='Outage status',
            source_rule='B13 (Outage Yes/No)',
            kind='auto',
            group='Planning',
            extractor=_outage_summary,
        ),

        # ── Description (combined SN field, assembled at submit) ──
        # These '_'-prefixed hidden fields are sub-sections of the combined
        # description and are folded together in mapping_apply.build_description
        # using whatever ChangeIntakeTemplate row is active for this vendor.
        FieldRule(
            target_field='description',
            label='Description (combined)',
            source_rule='Assembled from sub-sections below using the editable description template',
            kind='auto',
            group='Description',
            extractor=lambda p: '',  # filled by mapping_apply.build_description
        ),
        FieldRule(
            target_field='_executive_summary',
            label='Executive summary',
            source_rule='B15 (Scope of changes — customer perspective)',
            kind='auto',
            group='Description',
            extractor=lambda p: _cell(p, 'B15'),
        ),
        FieldRule(
            target_field='_benefit',
            label='Benefit / business justification',
            source_rule='<human input> — business/customer perspective',
            kind='human-input',
            group='Description',
            extractor=lambda p: '',
        ),
        FieldRule(
            target_field='_why_now',
            label='Why now',
            source_rule='B32 (Why Now?)',
            kind='auto',
            group='Description',
            extractor=lambda p: _cell(p, 'B32'),
        ),
        FieldRule(
            target_field='_impacts_if_not_installed',
            label='Impacts if not installed',
            source_rule='B32 (Why Now) + B15 (Scope) — consequence of skipping',
            kind='auto',
            group='Description',
            extractor=_impacts_if_not_installed,
        ),
        FieldRule(
            target_field='_alert_monitoring',
            label='Alert configuration / monitoring',
            source_rule='B17 (Alert configuration)',
            kind='auto',
            group='Description',
            extractor=lambda p: _cell(p, 'B17'),
        ),
        FieldRule(
            target_field='_error_handling',
            label='Error handling',
            source_rule='B18 (Error Handling)',
            kind='auto',
            group='Description',
            extractor=lambda p: _cell(p, 'B18'),
        ),
        FieldRule(
            target_field='_env_predecessors',
            label='Environment predecessors',
            source_rule='B22 (Environment Predecessors)',
            kind='auto',
            group='Description',
            extractor=lambda p: _cell(p, 'B22'),
        ),
        FieldRule(
            target_field='_testing_overview',
            label='Pre-prod testing overview',
            source_rule='B23 + B24/B25/B26 (UAT/Regression/Performance summary)',
            kind='auto',
            group='Description',
            extractor=_testing_overview,
        ),
        FieldRule(
            target_field='_install_steps',
            label='Install steps',
            source_rule="Sheet 'Implementation Plan' — full numbered steps",
            kind='auto',
            group='Description',
            extractor=lambda p: _sheet(p, 'Implementation Plan'),
        ),
        FieldRule(
            target_field='_install_duration',
            label='Install duration / window',
            source_rule='B7 (Change Date) + B8 (Time ET)',
            kind='auto',
            group='Description',
            extractor=_planned_window,
        ),
        FieldRule(
            target_field='_validation_steps',
            label='Validation steps',
            source_rule="B27 + Sheet 'Validation Plan'",
            kind='auto',
            group='Description',
            extractor=_validation_plan,
        ),
        FieldRule(
            target_field='_backout_steps',
            label='Backout steps',
            source_rule="B29 + Sheet 'Roll Back Plan'",
            kind='auto',
            group='Description',
            extractor=_backout_steps,
        ),
        FieldRule(
            target_field='_components',
            label='Components / impacted items',
            source_rule="B31 + Sheet 'List of Components' — full text",
            kind='auto',
            group='Description',
            extractor=lambda p: '\n\n'.join(x for x in (_cell(p, 'B31'), _sheet(p, 'List of Components')) if x),
        ),
        FieldRule(
            target_field='_impact_assessment',
            label='Impact assessment',
            source_rule="Sheet 'Impact Assessment' — full text",
            kind='auto',
            group='Description',
            extractor=lambda p: _sheet(p, 'Impact Assessment'),
        ),
        FieldRule(
            target_field='_notes',
            label='Approval / release notes',
            source_rule='B34 (Note — pre-approval/release prerequisites)',
            kind='auto',
            group='Description',
            extractor=lambda p: _cell(p, 'B34'),
        ),

        # ── Human-input description sub-sections (from the CT template) ──
        FieldRule(
            target_field='u_implementation_strategy',
            label='Implementation strategy',
            source_rule='<human input> — depends on the change',
            kind='human-input',
            group='Description',
            extractor=lambda p: '',
        ),
        FieldRule(
            target_field='u_implementation_approach',
            label='Implementation approach',
            source_rule='<human input> — depends on the change',
            kind='human-input',
            group='Description',
            extractor=lambda p: '',
        ),
    ],
)


register('epsilon', EPSILON_MAPPING)

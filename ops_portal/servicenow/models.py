from django.db import models


# Stage progression for an oncall review
ONCALL_STAGES = (
    ('pulled', 'Pulled'),
    ('ai_reviewed', 'AI reviewed'),
    ('decided', 'Decided'),
    ('comms_drafted', 'Comms drafted'),
    ('comms_sent', 'Comms sent'),
    ('suppressions_done', 'Suppressions done'),
    ('banner_posted', 'Banner posted'),
    ('closed', 'Closed'),
)

ONCALL_STAGE_VALUES = [s[0] for s in ONCALL_STAGES]

# Order index for sorting / "is past stage X" checks
ONCALL_STAGE_INDEX = {s: i for i, s in enumerate(ONCALL_STAGE_VALUES)}


AI_VERDICT_CHOICES = (
    ('unknown', 'Unknown'),
    ('yes', 'Outage likely'),
    ('no', 'No outage'),
    ('maybe', 'Possible outage'),
)

ACTUAL_OUTCOME_CHOICES = (
    ('', 'Not yet (in-flight or upcoming)'),
    ('success', 'Successful'),
    ('partial', 'Successful with issues'),
    ('failed', 'Failed'),
    ('rolled_back', 'Rolled back'),
    ('aborted', 'Aborted / cancelled'),
)

# Why this row was pulled — outage triage looks at THIS week's changes
# (current/imminent risk); CR approval looks at NEXT week's changes
# (proactive sign-off). They mostly cover different cohorts; "both" is set
# automatically when a change appears in both pulls.
PULL_PURPOSE_CHOICES = (
    ('outage_triage', 'Outage triage'),
    ('cr_approval',   'CR approval'),
    ('both',          'Both'),
)


# Engineer's CR-approval review state — independent of outage triage
CR_APPROVAL_STATUS_CHOICES = (
    ('not_started',       'Not started'),
    ('in_review',         'In review'),
    ('awaiting_requestor','Awaiting requestor'),
    ('ready_to_approve',  'Ready to approve'),
    ('approved',          'Approved'),
    ('rejected',          'Rejected'),
)

# Feedback-log entry types (stored inside approval_feedback_json)
APPROVAL_FEEDBACK_TYPES = (
    'note',           # plain note from the engineer
    'concern',        # flagged but not blocking yet
    'request_change', # asked the requestor to update something
    'resolved_by',    # engineer notes the requestor's response
    'ai_briefing',    # captured AI briefing output
)


class OncallChangeReview(models.Model):
    """
    One row per change reviewed in the oncall workflow.

    Re-pulling the same change in the same window reuses the same row
    (idempotent upsert keyed on change_number + window_start + window_end)
    so engineer-set fields (stage, comments, AI verdict, action timestamps)
    are preserved across pulls.
    """

    # Change identity
    change_number = models.CharField(max_length=32, db_index=True)
    sys_id = models.CharField(max_length=64, blank=True)
    short_description = models.CharField(max_length=512, blank=True)
    risk = models.CharField(max_length=32, blank=True)
    assignment_group = models.CharField(max_length=128, blank=True)
    cmdb_ci = models.CharField(max_length=128, blank=True, db_index=True)
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)

    # Time-window the change was pulled under
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    window_label = models.CharField(max_length=64, blank=True)

    # Why the engineer pulled this change.
    pull_purpose = models.CharField(
        max_length=32,
        choices=PULL_PURPOSE_CHOICES,
        default='outage_triage',
        db_index=True,
    )

    # AI outage-impact review (track 1)
    ai_outage_likely = models.CharField(
        max_length=16,
        choices=AI_VERDICT_CHOICES,
        default='unknown',
    )
    ai_summary = models.TextField(blank=True)
    ai_run_at = models.DateTimeField(null=True, blank=True)
    ai_payload_json = models.TextField(blank=True)

    # AI content summary (track 2) — what is this change actually doing?
    content_summary = models.TextField(blank=True)
    content_summary_run_at = models.DateTimeField(null=True, blank=True)

    # Outage declaration (per ServiceNow change record / outage records)
    outage_declared = models.BooleanField(default=False)
    outage_record_number = models.CharField(max_length=64, blank=True)
    outage_started_at = models.DateTimeField(null=True, blank=True)
    outage_ended_at = models.DateTimeField(null=True, blank=True)

    # Engineer review checklist — flexible JSON store of {key, label, checked, note}
    checklist_json = models.TextField(blank=True)

    # Post-window status — captured for retrospective management reports
    actual_outcome = models.CharField(
        max_length=32,
        choices=ACTUAL_OUTCOME_CHOICES,
        blank=True,
        default='',
    )
    issues_summary = models.TextField(blank=True)

    # CR Approval Review — the day-to-day "is this CR ready to approve?"
    # workflow with continuity across days. Distinct from outage triage.
    cr_approval_status = models.CharField(
        max_length=32,
        choices=CR_APPROVAL_STATUS_CHOICES,
        default='not_started',
        db_index=True,
    )
    cr_review_ctask_number = models.CharField(max_length=64, blank=True)
    cr_review_ctask_closed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.CharField(max_length=128, blank=True)
    # Chronological feedback log: list of {at, by, type, message, resolved}
    approval_feedback_json = models.TextField(blank=True)

    # Matrix snapshot — denormalised so it survives matrix edits later
    matched_app = models.CharField(max_length=256, blank=True)
    matched_impact = models.TextField(blank=True)
    matched_emails = models.TextField(blank=True)
    matched_suppr_ids = models.TextField(blank=True)
    matched_banner = models.BooleanField(default=False)
    matched_banner_msg = models.TextField(blank=True)
    # Free-text guidance fields snapshotted from the matrix — these explain
    # the *conditions* under which to notify / suppress (e.g. "Active/Active,
    # Yes for BCP event"), not a yes/no decision.
    matched_notify_partners = models.TextField(blank=True)
    matched_suppression = models.TextField(blank=True)

    # Engineer actions
    stage = models.CharField(
        max_length=32,
        choices=ONCALL_STAGES,
        default='pulled',
        db_index=True,
    )
    comments = models.TextField(blank=True)
    email_drafted_at = models.DateTimeField(null=True, blank=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    suppressions_done_at = models.DateTimeField(null=True, blank=True)
    banner_posted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.CharField(max_length=128, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_start', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['change_number', 'window_start', 'window_end'],
                name='uniq_change_per_window',
            )
        ]
        indexes = [
            models.Index(fields=['stage']),
            models.Index(fields=['ai_outage_likely']),
            models.Index(fields=['scheduled_start']),
        ]

    def __str__(self):
        return f'{self.change_number} [{self.stage}]'

    @property
    def stage_order(self) -> int:
        return ONCALL_STAGE_INDEX.get(self.stage, 0)

    def at_or_past(self, target_stage: str) -> bool:
        return self.stage_order >= ONCALL_STAGE_INDEX.get(target_stage, 0)


# ────────────────────────────────────────────────────────────────
# Vendor spreadsheet → ServiceNow Change intake wizard
# ────────────────────────────────────────────────────────────────

CHANGE_INTAKE_STATUS_CHOICES = (
    ('draft',          'Draft'),
    ('submitting',     'Submitting'),
    ('cr_created',     'CR created'),
    ('xlsx_attached',  'Spreadsheet attached'),
    ('ctask_created',  'CTASK created'),
    ('done',           'Done'),
    ('error',          'Error'),
)


class ChangeIntakeRequest(models.Model):
    """
    One row per uploaded vendor spreadsheet → Normal Change workflow.

    Persists every state of the wizard so the engineer can navigate back
    to the result page later. JSON-as-TextField matches the rest of this
    app (see OncallChangeReview.ai_payload_json).
    """

    vendor_template = models.CharField(
        max_length=64,
        default='epsilon',
        db_index=True,
    )

    uploaded_file = models.FileField(upload_to='servicenow_excel_uploads/')
    original_filename = models.CharField(max_length=255, blank=True)

    # Full parsed payload from excel_parser: {cells: {...}, sheets: {...}}
    parsed_payload_json = models.TextField(blank=True)

    # Current edited proposal list:
    # [{target_field, label, source_rule, kind, group, value}, ...]
    proposals_json = models.TextField(blank=True)

    # AI completeness check result + debug:
    # {ok, issues:[{field, severity, message}], suggestions:[{field, suggested_value}],
    #  _debug:{prompt_system, prompt_user, raw_response}}
    ai_completeness_json = models.TextField(blank=True)

    # Per-field AI-generate debug, keyed by target_field:
    # {<field>: {prompt_system, prompt_user, raw_response, suggested_value}}
    ai_field_debug_json = models.TextField(blank=True)

    submit_status = models.CharField(
        max_length=32,
        choices=CHANGE_INTAKE_STATUS_CHOICES,
        default='draft',
        db_index=True,
    )
    submit_error = models.TextField(blank=True)

    created_chg_number = models.CharField(max_length=32, blank=True)
    created_chg_sys_id = models.CharField(max_length=64, blank=True)
    created_ctask_number = models.CharField(max_length=32, blank=True)
    created_ctask_sys_id = models.CharField(max_length=64, blank=True)

    submit_task_id = models.CharField(max_length=64, blank=True)
    completeness_task_id = models.CharField(max_length=64, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        suffix = self.created_chg_number or f'(draft {self.pk})'
        return f'{self.vendor_template} → {suffix}'


class VendorConfig(models.Model):
    """
    Per-vendor default values for change-intake fields that don't come from
    the spreadsheet (Configuration Item, Assignment Group, Assigned To,
    Code Change flag, etc.).

    Stored as a flat JSON dict of {target_field: default_value} so the set
    of overridable fields can evolve without schema changes. Empty values
    fall through to whatever the extractor returned.
    """

    vendor_template = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
    )
    defaults_json = models.TextField(
        blank=True,
        default='{}',
        help_text='JSON dict {target_field: default_value}',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['vendor_template']

    def __str__(self) -> str:
        return self.vendor_template

    def defaults(self) -> dict:
        try:
            import json
            data = json.loads(self.defaults_json or '{}')
            return data if isinstance(data, dict) else {}
        except (ValueError, TypeError):
            return {}


# ────────────────────────────────────────────────────────────────
# Reports — saved ServiceNow query + actions
# ────────────────────────────────────────────────────────────────

REPORT_ACTION_CHOICES = (
    ('view',       'View on screen'),
    ('csv',        'Download CSV'),
    ('email',      'Email (Outlook draft)'),
    ('ai_summary', 'AI summary'),
)

REPORT_ACTION_VALUES = [a[0] for a in REPORT_ACTION_CHOICES]


class Report(models.Model):
    """A saved, named ServiceNow query plus the actions that can be run on
    its results.

    Powers the focused Reports UI — a friendlier alternative to the full
    Presets page: an engineer picks or creates a report, runs it, and acts
    on the rows (view / CSV / email / AI summary).
    """

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    # ServiceNow Table API query
    table = models.CharField(max_length=80, default='incident')
    query = models.TextField(blank=True, help_text='ServiceNow encoded query.')
    fields = models.TextField(
        blank=True,
        help_text='Comma-separated ServiceNow field names to return.',
    )
    row_limit = models.PositiveIntegerField(default=100)

    # JSON list of action keys (subset of REPORT_ACTION_VALUES)
    actions_json = models.TextField(blank=True, default='[]')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name

    def actions(self) -> list:
        """Parsed action-key list, filtered to known actions."""
        try:
            import json
            data = json.loads(self.actions_json or '[]')
        except (ValueError, TypeError):
            return []
        if not isinstance(data, list):
            return []
        return [a for a in data if a in REPORT_ACTION_VALUES]

    def field_list(self) -> list:
        return [f.strip() for f in (self.fields or '').split(',') if f.strip()]

    def action_labels(self) -> list:
        """Human-readable labels for this report's actions."""
        labels = dict(REPORT_ACTION_CHOICES)
        return [labels.get(a, a) for a in self.actions()]

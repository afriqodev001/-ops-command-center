from django.urls import path
from . import views
from . import pages
from . import oncall_pages

urlpatterns = [

    # ─── Oncall change-review workflow ──────────
    path("oncall/",                               oncall_pages.oncall_dashboard,        name="oncall-dashboard"),
    path("oncall/approvals/",                     oncall_pages.oncall_approvals_page,   name="oncall-approvals"),
    path("oncall/pull/",                          oncall_pages.oncall_pull_changes,     name="oncall-pull"),
    path("oncall/pull/poll/<str:task_id>/",       oncall_pages.oncall_pull_poll,        name="oncall-pull-poll"),
    path("oncall/review/<str:change_number>/",    oncall_pages.oncall_review_detail,    name="oncall-review-detail"),
    path("oncall/review/<str:change_number>/run-ai/",
         oncall_pages.oncall_run_ai_for_change,                                          name="oncall-run-ai"),
    path("oncall/review/<str:change_number>/draft-email/",
         oncall_pages.oncall_draft_email,                                                name="oncall-draft-email"),
    path("oncall/review/<str:change_number>/mark/",
         oncall_pages.oncall_mark_stage,                                                 name="oncall-mark-stage"),
    path("oncall/review/<str:change_number>/run-summary/",
         oncall_pages.oncall_run_content_summary,                                        name="oncall-run-content-summary"),
    path("oncall/review/<str:change_number>/poll-summary/<str:task_id>/",
         oncall_pages.oncall_poll_content_summary,                                       name="oncall-poll-content-summary"),
    path("oncall/review/<str:change_number>/checklist/",
         oncall_pages.oncall_save_checklist,                                             name="oncall-save-checklist"),
    path("oncall/review/<str:change_number>/outage/",
         oncall_pages.oncall_save_outage,                                                name="oncall-save-outage"),
    path("oncall/review/<str:change_number>/outcome/",
         oncall_pages.oncall_save_outcome,                                               name="oncall-save-outcome"),
    path("oncall/review/<str:change_number>/cr-status/",
         oncall_pages.oncall_save_approval_status,                                       name="oncall-save-cr-status"),
    path("oncall/review/<str:change_number>/cr-feedback/add/",
         oncall_pages.oncall_add_approval_feedback,                                      name="oncall-add-cr-feedback"),
    path("oncall/review/<str:change_number>/cr-feedback/resolve/",
         oncall_pages.oncall_resolve_approval_feedback,                                  name="oncall-resolve-cr-feedback"),
    path("oncall/review/<str:change_number>/cr-feedback/delete/",
         oncall_pages.oncall_delete_approval_feedback,                                   name="oncall-delete-cr-feedback"),
    path("oncall/review/<str:change_number>/cr-briefing/run/",
         oncall_pages.oncall_run_cr_briefing,                                            name="oncall-run-cr-briefing"),
    path("oncall/review/<str:change_number>/cr-briefing/poll/<str:task_id>/",
         oncall_pages.oncall_poll_cr_briefing,                                           name="oncall-poll-cr-briefing"),
    path("oncall/review/<str:change_number>/cr-ctask/save/",
         oncall_pages.oncall_save_cr_ctask,                                              name="oncall-save-cr-ctask"),
    path("oncall/report/",                        oncall_pages.oncall_report_page,      name="oncall-report"),
    path("oncall/report/run/",                    oncall_pages.oncall_report_run,       name="oncall-report-run"),
    path("oncall/report/poll/<str:task_id>/",     oncall_pages.oncall_report_poll,      name="oncall-report-poll"),
    path("oncall/report/email/",                  oncall_pages.oncall_report_email,     name="oncall-report-email"),
    path("oncall/run-ai-batch/",                  oncall_pages.oncall_run_ai_batch,     name="oncall-run-ai-batch"),
    path("oncall/poll-ai/<str:task_id>/",         oncall_pages.oncall_poll_ai,          name="oncall-poll-ai"),
    path("oncall/matrix/",                        oncall_pages.oncall_matrix_page,      name="oncall-matrix"),
    path("oncall/matrix/upload/",                 oncall_pages.oncall_matrix_upload,    name="oncall-matrix-upload"),
    path("oncall/matrix/ai-format/",              oncall_pages.oncall_matrix_ai_format, name="oncall-matrix-ai-format"),
    path("oncall/matrix/apply/",                  oncall_pages.oncall_matrix_apply,     name="oncall-matrix-apply"),
    path("oncall/matrix/clear/",                  oncall_pages.oncall_matrix_clear,     name="oncall-matrix-clear"),
    path("oncall/matrix/row/editor/",             oncall_pages.oncall_matrix_row_editor, name="oncall-matrix-row-editor"),
    path("oncall/matrix/row/save/",               oncall_pages.oncall_matrix_row_save,   name="oncall-matrix-row-save"),
    path("oncall/matrix/row/delete/",             oncall_pages.oncall_matrix_row_delete, name="oncall-matrix-row-delete"),
    path("oncall/matrix/export/json/",            oncall_pages.oncall_matrix_export_json,name="oncall-matrix-export-json"),
    path("oncall/matrix/export/csv/",             oncall_pages.oncall_matrix_export_csv, name="oncall-matrix-export-csv"),
    path("oncall/templates/",                     oncall_pages.oncall_templates_page,   name="oncall-templates"),
    path("oncall/templates/save/",                oncall_pages.oncall_template_save,    name="oncall-template-save"),
    path("oncall/banner/post/",                   oncall_pages.oncall_banner_post,      name="oncall-banner-post"),
    path("oncall/banner/clear/",                  oncall_pages.oncall_banner_clear,     name="oncall-banner-clear"),
    path("oncall/history/",                       oncall_pages.oncall_history_page,     name="oncall-history"),
    path("oncall/history/partial/",               oncall_pages.oncall_history_partial,  name="oncall-history-partial"),


    # ─── UI pages ───────────────────────────────
    path("incidents/",                 pages.incidents_list,   name="incidents-list"),
    path("incidents/<str:number>/",    pages.incident_detail,  name="incident-detail"),
    path("changes/",                               pages.changes_list,              name="changes-list"),
    # fixed-segment routes BEFORE the parameterised <str:number> catch-all
    path("changes/bulk-review/",                   pages.bulk_change_review,        name="bulk-change-review"),
    path("changes/bulk-review/item/",              pages.bulk_change_review_item,   name="bulk-change-review-item"),
    path("changes/bulk-create/",                   pages.bulk_change_create,        name="bulk-change-create"),
    path("changes/bulk-create/sample-csv/",        pages.bulk_change_sample_csv,     name="bulk-change-sample-csv"),
    path("changes/bulk-create/preview/",           pages.bulk_change_preview,       name="bulk-change-preview"),
    path("changes/bulk-create/submit/",            pages.bulk_change_submit,        name="bulk-change-submit"),
    path("changes/bulk-create/templates/save/",    pages.bulk_change_template_save,   name="bulk-change-template-save"),
    path("changes/bulk-create/templates/delete/",  pages.bulk_change_template_delete, name="bulk-change-template-delete"),
    path("changes/<str:number>/",                  pages.change_detail,             name="change-detail"),
    path("changes/<str:number>/briefing/",         pages.change_briefing,           name="change-briefing"),
    path("changes/<str:number>/briefing/generate/",pages.change_briefing_generate,  name="change-briefing-generate"),
    path("lookup/",                                pages.record_lookup,             name="record-lookup"),
    path("search/",                                pages.search_records,            name="search-records"),
    path("search/presets/save/",                   pages.search_preset_save,        name="search-preset-save"),
    path("search/presets/delete/",                 pages.search_preset_delete,      name="search-preset-delete"),
    path("search/presets/json/",                   pages.search_presets_json,       name="search-presets-json"),

    # ─── Creation Templates ────────────────────
    path("templates/",                             pages.creation_templates_page,      name="creation-templates"),
    path("templates/save/",                        pages.creation_template_save,       name="creation-template-save"),
    path("templates/delete/",                      pages.creation_template_delete,     name="creation-template-delete"),
    path("templates/picker/<str:kind>/",           pages.create_from_template_picker,  name="create-from-template-picker"),
    path("templates/form/<str:key>/",              pages.create_from_template_form,    name="create-from-template-form"),
    path("templates/submit/",                      pages.create_from_template_submit,  name="create-from-template-submit"),

    # ─── Data mode toggle ───────────────────────
    path("mode/toggle/",           pages.data_mode_toggle,      name="data-mode-toggle"),

    # ─── Live-mode async polling ────────────────
    path("live/poll/<str:shape>/<str:task_id>/", pages.live_poll, name="live-poll"),

    # ─── AI-assisted creation ───────────────────
    path("ai/suggest/",            pages.ai_suggest_fields,     name="ai-suggest"),

    # ─── Preferences panel ──────────────────────
    path("preferences/",           pages.preferences_modal,     name="preferences-modal"),
    path("preferences/save/",      pages.preferences_save,      name="preferences-save"),
    path("preferences/reset/",     pages.preferences_reset_store, name="preferences-reset"),

    # ─── AI Prompt Editor ───────────────────
    path("prompts/",               pages.prompts_editor,        name="prompts-editor"),
    path("prompts/save/",          pages.prompt_save,           name="prompt-save"),
    path("prompts/reset/",         pages.prompt_reset,          name="prompt-reset"),

    # ─── Activity log ───────────────────────────
    path("activity/",              pages.activity_modal,        name="activity-modal"),
    path("activity/badge/",        pages.activity_badge,        name="activity-badge"),
    path("activity/clear/",        pages.activity_clear,        name="activity-clear"),

    # ─── Session management ─────────────────────
    path("session/widget/",        views.session_widget,        name="session-widget"),
    path("session/modal/",         views.session_modal_content, name="session-modal"),
    path("session/connect/",       views.session_connect,       name="session-connect"),
    path("session/disconnect/",    views.session_disconnect,    name="session-disconnect"),
    path("session/reset/",         views.session_reset,         name="session-reset"),
    path("session/close-browser/", views.session_close_browser, name="session-close-browser"),

    # ─── API endpoints ──────────────────────────
    path("login/open/", views.servicenow_login_open),

    # Changes by sys_id
    path("changes/get/", views.changes_get),
    path("changes/patch/", views.changes_patch),

    # Incidents
    path("incidents/get/", views.incidents_get),
    path("incidents/patch/", views.incidents_patch),

    # Generic list (optional but very handy)
    path("table/list/", views.table_list),

    # Generic get-by-field
    path("table/get-by-field/", views.table_get_by_field),
    path("table/bulk-get-by-field/", views.table_bulk_get_by_field),

    # Changes by number
    path("changes/get-by-number/", views.changes_get_by_number),
    path("changes/bulk-get-by-number/", views.changes_bulk_get_by_number),

    #
    path("attachments/list/", views.attachments_list),
    path("ctasks/list-for-change/", views.ctasks_list_for_change),
    path("changes/context/", views.changes_context),

    # Presets UI page (must be before API presets/list/ and presets/run/)
    path("presets/",          pages.presets_page,   name="presets-page"),
    path("presets/run/ui/",   pages.preset_run_ui,  name="preset-run-ui"),
    path("presets/save/",     pages.preset_save,    name="preset-save"),
    path("presets/delete/",   pages.preset_delete,  name="preset-delete"),
    path("presets/email/",    pages.preset_email_outlook, name="preset-email"),
    path("presets/export/",   pages.presets_export, name="presets-export"),
    path("presets/import/",   pages.presets_import, name="presets-import"),

    # Presets API
    path("presets/list/", views.presets_list),
    path("presets/run/", views.presets_run),

    #
    path("changes/create/", views.changes_create),

    #
    path("incidents/context/", views.incidents_context),

    #
    path("incidents/create/", views.incidents_create),

    #
    path("incidents/get-by-field/", views.incidents_get_by_field),
    path("incidents/bulk-get-by-field/", views.incidents_bulk_get_by_field),
    path("incidents/presets/list/", views.incidents_presets_list),
    path("incidents/presets/run/", views.incidents_presets_run),
]

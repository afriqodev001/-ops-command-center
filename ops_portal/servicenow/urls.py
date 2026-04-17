from django.urls import path
from . import views
from . import pages

urlpatterns = [

    # ─── UI pages ───────────────────────────────
    path("incidents/",                 pages.incidents_list,   name="incidents-list"),
    path("incidents/<str:number>/",    pages.incident_detail,  name="incident-detail"),
    path("changes/",                               pages.changes_list,              name="changes-list"),
    # fixed-segment routes BEFORE the parameterised <str:number> catch-all
    path("changes/bulk-review/",                   pages.bulk_change_review,        name="bulk-change-review"),
    path("changes/bulk-review/item/",              pages.bulk_change_review_item,   name="bulk-change-review-item"),
    path("changes/bulk-create/",                   pages.bulk_change_create,        name="bulk-change-create"),
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

    # ─── Preferences panel ──────────────────────
    path("preferences/",           pages.preferences_modal,     name="preferences-modal"),
    path("preferences/save/",      pages.preferences_save,      name="preferences-save"),
    path("preferences/reset/",     pages.preferences_reset_store, name="preferences-reset"),

    # ─── Activity log ───────────────────────────
    path("activity/",              pages.activity_modal,        name="activity-modal"),
    path("activity/badge/",        pages.activity_badge,        name="activity-badge"),
    path("activity/clear/",        pages.activity_clear,        name="activity-clear"),

    # ─── Session management ─────────────────────
    path("session/widget/",        views.session_widget,        name="session-widget"),
    path("session/modal/",         views.session_modal_content, name="session-modal"),
    path("session/connect/",       views.session_connect,       name="session-connect"),
    path("session/disconnect/",    views.session_disconnect,    name="session-disconnect"),
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

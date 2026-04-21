from django.urls import path
from . import views
from . import session_views

urlpatterns = [
    # ─── Session management (sidebar widget) ───
    path("session/widget/",        session_views.session_widget,        name="copilot-session-widget"),
    path("session/connect/",       session_views.session_connect,       name="copilot-session-connect"),
    path("session/close-browser/", session_views.session_close_browser, name="copilot-session-close"),
    path("session/disconnect/",    session_views.session_disconnect,    name="copilot-session-disconnect"),
    path("session/reset/",         session_views.session_reset,         name="copilot-session-reset"),
    path("session/status/",        session_views.session_status_json,   name="copilot-session-status"),

    # UI
    path("", views.copilot_home, name="copilot_home"),
    path("partials/packs/", views.packs_list_partial, name="copilot_packs_list_partial"),
    # path("partials/packs/<slug:pack_slug>/", views.pack_detail_partial, name="copilot_pack_detail_partial"),

    path("ui/login/open/", views.ui_login_open, name="copilot_ui_login_open"),
    path("ui/run/", views.ui_run_prompt, name="copilot_ui_run_prompt"),
    path("ui/poll/<str:task_id>/", views.ui_poll_run, name="copilot_ui_poll_run"),

    path("ui/batch/run/", views.ui_run_batch, name="copilot_ui_run_batch"),
    path("ui/batch/poll/<str:task_id>/", views.ui_poll_batch, name="copilot_ui_poll_batch"),

    path("partials/runs/", views.runs_list_partial, name="copilot_runs_list_partial"),

    path(
        "partials/runs/<int:run_id>/",
        views.copilot_run_detail_partial,
        name="copilot_run_detail_partial",
    ),

    path("export/", views.export_runs, name="copilot_export_runs"),

    path("ui/auth/check/", views.ui_auth_check, name="copilot_ui_auth_check"),
    path("ui/auth/poll/<str:task_id>/", views.ui_auth_poll, name="copilot_ui_auth_poll"),

    # Prompt Pack editor UX (HTMX)
    path("partials/prompt-packs/new/", views.prompt_pack_editor, name="copilot_prompt_pack_new"),
    path(
        "partials/prompt-packs/<int:pack_id>/view/",
        views.prompt_pack_view_modal,
        name="prompt_pack_view_modal",
    ),
    path("partials/prompt-packs/<int:pk>/edit/", views.prompt_pack_editor, name="copilot_prompt_pack_edit"),
    path("partials/prompt-packs/save/", views.prompt_pack_save, name="copilot_prompt_pack_save"),

    # Add a new prompt row in the editor (HTMX append)
    path("partials/prompt-packs/prompt-row/", views.prompt_pack_prompt_row, name="copilot_prompt_pack_prompt_row"),

    # Prompt pack export / import
    path("packs/export/", views.prompt_pack_export_all, name="copilot_packs_export_all"),
    path("packs/export/<int:pk>/", views.prompt_pack_export_one, name="copilot_packs_export_one"),
    path("packs/import/", views.prompt_pack_import_form, name="copilot_packs_import_form"),
    path("packs/import/preview/", views.prompt_pack_import_preview, name="copilot_packs_import_preview"),
    path("packs/import/confirm/", views.prompt_pack_import_confirm, name="copilot_packs_import_confirm"),

    # API (existing)
    path("login/open/", views.copilot_login_open),
    path("run/", views.copilot_run),
    path("run-with-files/", views.copilot_run_with_files),
    path("downloads/<str:user_key>/<str:filename>/", views.copilot_download),
]
from django.urls import path
from sploc import views, pages, session_views

app_name = 'sploc'

urlpatterns = [
    # ─── Session management (sidebar widget) ───
    path("session/widget/",        session_views.session_widget,        name="sploc-session-widget"),
    path("session/connect/",       session_views.session_connect,       name="sploc-session-connect"),
    path("session/close-browser/", session_views.session_close_browser, name="sploc-session-close"),
    path("session/disconnect/",    session_views.session_disconnect,    name="sploc-session-disconnect"),
    path("session/reset/",         session_views.session_reset,         name="sploc-session-reset"),
    path("session/status/",        session_views.session_status_json,   name="sploc-session-status"),

    # ─── UI pages ──────────────────────────────
    path("",                       pages.sploc_home,        name="sploc-home"),
    path("traces/",                pages.sploc_traces,      name="sploc-traces"),
    path("ai/",                    pages.sploc_ai_page,     name="sploc-ai"),
    path("prompts/",               pages.sploc_prompts_page, name="sploc-prompts"),

    # ─── HTMX partials: trace scraping ─────────
    path("ui/trace/run/",                    pages.run_trace_scrape,   name="sploc-run-trace"),
    path("ui/trace/poll/<str:task_id>/",     pages.poll_trace_scrape,  name="sploc-poll-trace"),

    # ─── Trace history (recents) ───────────────
    path("ui/recents/partial/",              pages.recents_partial,    name="sploc-recents"),
    path("ui/recents/delete/",               pages.recent_delete,      name="sploc-recent-delete"),
    path("ui/recents/clear/",                pages.recents_clear,      name="sploc-recents-clear"),

    # ─── HTMX partials: AI assistant ──────────
    path("ui/ai/run/",                       pages.run_ai_ask,         name="sploc-run-ai"),
    path("ui/ai/poll/<str:task_id>/",        pages.poll_ai_ask,        name="sploc-poll-ai"),

    # ─── AI analysis ───────────────────────────
    path("ai/analyze/",                      pages.ai_analyze_trace,   name="sploc-ai-analyze"),
    path("ai/analyze/poll/<str:task_id>/",   pages.ai_analyze_poll,    name="sploc-ai-analyze-poll"),

    # ─── Export ────────────────────────────────
    path("export/trace/json/",               pages.export_trace_json,  name="sploc-export-json"),
    path("export/trace/tsv/",                pages.export_trace_tsv,   name="sploc-export-tsv"),

    # ─── Service catalog management ────────────
    path("services/",                      pages.sploc_services_page,    name="sploc-services"),
    path("services/list/partial/",         pages.services_list_partial,  name="sploc-services-list"),
    path("services/editor/",               pages.service_editor,         name="sploc-service-editor"),
    path("services/save/",                 pages.service_save_view,      name="sploc-service-save"),
    path("services/delete/",               pages.service_delete_view,    name="sploc-service-delete"),
    path("services/export/",               pages.service_export_all,     name="sploc-services-export"),
    path("services/export/<str:name>/",    pages.service_export_one,     name="sploc-service-export-one"),
    path("services/import/",               pages.service_import_form,    name="sploc-services-import"),
    path("services/import/preview/",       pages.service_import_preview, name="sploc-services-import-preview"),
    path("services/import/confirm/",       pages.service_import_confirm, name="sploc-services-import-confirm"),

    # ─── Prompt pack management ────────────────
    path("prompts/list/partial/",          pages.packs_list_partial,  name="sploc-packs-list"),
    path("prompts/quick/partial/",         pages.packs_quick_partial, name="sploc-packs-quick"),
    path("prompts/editor/",                pages.pack_editor,         name="sploc-pack-editor"),
    path("prompts/save/",                  pages.pack_save_view,      name="sploc-pack-save"),
    path("prompts/delete/",                pages.pack_delete_view,    name="sploc-pack-delete"),
    path("prompts/export/",                pages.pack_export_all,     name="sploc-packs-export"),
    path("prompts/export/<str:name>/",     pages.pack_export_one,     name="sploc-pack-export-one"),
    path("prompts/import/",                pages.pack_import_form,    name="sploc-packs-import"),
    path("prompts/import/preview/",        pages.pack_import_preview, name="sploc-packs-import-preview"),
    path("prompts/import/confirm/",        pages.pack_import_confirm, name="sploc-packs-import-confirm"),

    # ─── API endpoints ────────────────────────
    path("api/login/open/",                  views.sploc_login_open),
    path("api/trace/scrape/",                views.trace_scrape),
    path("api/ai/ask/",                      views.ai_ask),
]

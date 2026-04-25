# harness/urls.py
from django.urls import path
from . import views, pages, session_views, workspace_pages

app_name = 'harness'

urlpatterns = [
    # ─── Session management (sidebar widget) ───
    path("session/widget/",        session_views.session_widget,        name="session-widget"),
    path("session/connect/",       session_views.session_connect,       name="session-connect"),
    path("session/close-browser/", session_views.session_close_browser, name="session-close"),
    path("session/disconnect/",    session_views.session_disconnect,    name="session-disconnect"),
    path("session/reset/",         session_views.session_reset,         name="session-reset"),
    path("session/status/",        session_views.session_status_json,   name="session-status"),

    # ─── UI pages ──────────────────────────────
    path("",                       pages.harness_home,             name="home"),
    path("pipelines/",             pages.harness_pipelines_page,   name="pipelines"),
    path("executions/",            pages.harness_executions_page,  name="executions"),
    path("instances/",             pages.harness_instances_page,   name="instances"),
    path("projects/",              pages.harness_projects_page,    name="projects"),
    path("environments/",          pages.harness_environments_page, name="environments"),

    # ─── HTMX partials: Pipelines ──────────────
    path("ui/pipelines/run/",              pages.run_pipelines_list,    name="ui-pipelines-run"),
    path("ui/pipelines/poll/<str:task_id>/", pages.poll_pipelines_list, name="ui-pipelines-poll"),

    # ─── HTMX partials: Executions ─────────────
    path("ui/executions/run/",              pages.run_executions,    name="ui-executions-run"),
    path("ui/executions/poll/<str:task_id>/", pages.poll_executions, name="ui-executions-poll"),

    # ─── HTMX partials: Last success ───────────
    path("ui/last-success/run/",              pages.run_last_success,    name="ui-last-success-run"),
    path("ui/last-success/poll/<str:task_id>/", pages.poll_last_success, name="ui-last-success-poll"),

    # ─── HTMX partials: Last success per infra ─
    path("ui/last-success-by-infra/run/",              pages.run_last_success_by_infra,    name="ui-last-success-by-infra-run"),
    path("ui/last-success-by-infra/poll/<str:task_id>/", pages.poll_last_success_by_infra, name="ui-last-success-by-infra-poll"),

    # ─── HTMX partials: Active instances ───────
    path("ui/instances/run/",              pages.run_instances,    name="ui-instances-run"),
    path("ui/instances/poll/<str:task_id>/", pages.poll_instances, name="ui-instances-poll"),

    # ─── HTMX partials: Projects ───────────────
    path("ui/projects/run/",              pages.run_projects,    name="ui-projects-run"),
    path("ui/projects/poll/<str:task_id>/", pages.poll_projects, name="ui-projects-poll"),

    # ─── HTMX partials: Environments ───────────
    path("ui/environments/run/",              pages.run_environments,    name="ui-environments-run"),
    path("ui/environments/poll/<str:task_id>/", pages.poll_environments, name="ui-environments-poll"),

    # ─── Service Explorer (Track B) ────────────
    path("service/",                                     pages.harness_service_explorer,         name="service-explorer"),
    path("ui/service/now-running/run/",                  pages.service_now_running,              name="ui-svc-now-running-run"),
    path("ui/service/now-running/poll/<str:task_id>/",   pages.service_now_running_poll,         name="ui-svc-now-running-poll"),
    path("ui/service/recent-runs/run/",                  pages.service_recent_runs,              name="ui-svc-recent-runs-run"),
    path("ui/service/recent-runs/poll/<str:task_id>/",   pages.service_recent_runs_poll,         name="ui-svc-recent-runs-poll"),
    path("ui/service/last-success/run/",                 pages.service_last_success_per_env,     name="ui-svc-last-success-run"),
    path("ui/service/last-success/poll/<str:task_id>/",  pages.service_last_success_per_env_poll, name="ui-svc-last-success-poll"),

    # ─── Workspace (curated identifiers) ───────
    path("workspace/",                            workspace_pages.workspace_page,         name="workspace"),
    # Projects
    path("workspace/projects/list/",              workspace_pages.projects_list_partial,  name="ws-projects-list"),
    path("workspace/projects/editor/",            workspace_pages.project_editor,         name="ws-project-editor"),
    path("workspace/projects/save/",              workspace_pages.project_save,           name="ws-project-save"),
    path("workspace/projects/delete/",            workspace_pages.project_delete,         name="ws-project-delete"),
    # Pipelines
    path("workspace/pipelines/list/",             workspace_pages.pipelines_list_partial, name="ws-pipelines-list"),
    path("workspace/pipelines/editor/",           workspace_pages.pipeline_editor,        name="ws-pipeline-editor"),
    path("workspace/pipelines/save/",             workspace_pages.pipeline_save,          name="ws-pipeline-save"),
    path("workspace/pipelines/delete/",           workspace_pages.pipeline_delete,        name="ws-pipeline-delete"),
    # Services
    path("workspace/services/list/",              workspace_pages.services_list_partial,  name="ws-services-list"),
    path("workspace/services/editor/",            workspace_pages.service_editor,         name="ws-service-editor"),
    path("workspace/services/save/",              workspace_pages.service_save,           name="ws-service-save"),
    path("workspace/services/delete/",            workspace_pages.service_delete,         name="ws-service-delete"),
    # Import / Export
    path("workspace/export/",                     workspace_pages.export_all,             name="ws-export"),
    path("workspace/import/",                     workspace_pages.import_form,            name="ws-import"),
    path("workspace/import/preview/",             workspace_pages.import_preview,         name="ws-import-preview"),
    path("workspace/import/confirm/",             workspace_pages.import_confirm,         name="ws-import-confirm"),

    # ─── Export ────────────────────────────────
    path("export/json/",           pages.export_json,        name="export-json"),

    # ─── API endpoints (existing, kept under /api/) ───
    path("api/login/open/",                         views.harness_login_open),
    path("api/environments/list/",                  views.harness_environments),
    path("api/environments/active-service-instances/", views.harness_active_service_instances),
    path("api/executions/summary/",                 views.harness_pipeline_execution_summary),
    path("api/executions/summary/filtered/",        views.harness_pipeline_execution_summary_filtered),
    path("api/executions/inputset-v2/",             views.harness_execution_inputset_v2),
    path("api/projects/list/",                      views.harness_projects),
    path("api/pipelines/list/",                     views.harness_pipelines_list),
    path("api/executions/last-success/filtered/",   views.harness_last_success_execution_filtered),
    path(
        "api/executions/last-success/by-infra/",
        views.harness_last_success_by_infra,
        name="api-last-success-by-infra",
    ),
    path("api/fetch/plan/",                         views.harness_fetch_plan),
]

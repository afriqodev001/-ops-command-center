# harness/urls.py
from django.urls import path
from . import views, pages, session_views

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

    # ─── HTMX partials: Active instances ───────
    path("ui/instances/run/",              pages.run_instances,    name="ui-instances-run"),
    path("ui/instances/poll/<str:task_id>/", pages.poll_instances, name="ui-instances-poll"),

    # ─── HTMX partials: Projects ───────────────
    path("ui/projects/run/",              pages.run_projects,    name="ui-projects-run"),
    path("ui/projects/poll/<str:task_id>/", pages.poll_projects, name="ui-projects-poll"),

    # ─── HTMX partials: Environments ───────────
    path("ui/environments/run/",              pages.run_environments,    name="ui-environments-run"),
    path("ui/environments/poll/<str:task_id>/", pages.poll_environments, name="ui-environments-poll"),

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

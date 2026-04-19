from django.urls import path
from splunk import views, pages, session_views

urlpatterns = [
    # ─── Session management (sidebar widget) ───
    path("session/widget/",        session_views.session_widget,        name="splunk-session-widget"),
    path("session/connect/",       session_views.session_connect,       name="splunk-session-connect"),
    path("session/close-browser/", session_views.session_close_browser, name="splunk-session-close"),
    path("session/disconnect/",    session_views.session_disconnect,    name="splunk-session-disconnect"),
    path("session/status/",        session_views.session_status_json,   name="splunk-session-status"),

    # ─── UI pages ───────────────────────────────
    path("",                       pages.splunk_home,      name="splunk-home"),
    path("ui/search/run/",         pages.run_search,       name="splunk-run-search"),
    path("ui/preset/run/",         pages.run_preset,       name="splunk-run-preset"),
    path("ui/saved/run/",          pages.run_saved_search, name="splunk-run-saved"),
    path("ui/poll/<str:task_id>/", pages.poll_search,      name="splunk-poll"),

    # ─── API endpoints ─────────────────────────
    path("api/login/open/",             views.splunk_login_open),
    path("api/alerts/search/",          views.alerts_search),
    path("api/alerts/list/",            views.alerts_list),
    path("api/alerts/run/",             views.alerts_run),
    path("api/alerts/run_async/",       views.alerts_run_async),
    path("api/jobs/create/",            views.job_create),
    path("api/jobs/status/",            views.job_status),
    path("api/jobs/events/",            views.job_events),
    path("api/jobs/results_preview/",   views.job_results_preview),
    path("api/search/run/",             views.search_run),
    path("api/search/run_async/",       views.search_run_async),
    path("api/presets/list/",           views.presets_list),
    path("api/presets/run/",            views.presets_run),
    path("api/presets/run_async/",      views.presets_run_async),
]

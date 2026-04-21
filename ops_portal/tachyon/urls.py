# tachyon/urls.py

from django.urls import path
from . import views
from . import pages

urlpatterns = [
    # ─── Session management ─────────────────────
    path("session/widget/",         pages.tachyon_session_widget,       name="tachyon-session-widget"),
    path("session/connect/",        pages.tachyon_session_connect,      name="tachyon-session-connect"),
    path("session/close-browser/",  pages.tachyon_session_close_browser, name="tachyon-session-close"),
    path("session/disconnect/",     pages.tachyon_session_disconnect,   name="tachyon-session-disconnect"),
    path("session/reset/",          pages.tachyon_session_reset,        name="tachyon-session-reset"),

    # ─── UI pages ───────────────────────────────
    path("playground/",             pages.playground,           name="tachyon-playground"),
    path("playground/presets/",     pages.preset_list_partial,  name="tachyon-preset-list"),
    path("playground/presets/save/", pages.preset_save,         name="tachyon-preset-save"),
    path("playground/presets/delete/", pages.preset_delete,     name="tachyon-preset-delete"),
    path("playground/run/",         pages.run_query,            name="tachyon-run"),

    # ─── API endpoints (JSON) ──────────────────
    path("login/open/",             views.open_tachyon_login),
    path("presets/",                views.list_presets),
    path("run/",                    views.run_single),
    path("run-with-file/",          views.run_with_file),
    path("run-with-upload/",        views.run_with_upload),
    path("batch/run/",              views.run_batch),
]

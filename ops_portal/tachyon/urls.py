# tachyon/urls.py

from django.urls import path
from . import views
from . import pages

urlpatterns = [
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

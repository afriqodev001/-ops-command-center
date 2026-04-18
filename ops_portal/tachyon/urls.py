# tachyon/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path("login/open/", views.open_tachyon_login),
    path("presets/", views.list_presets),
    path("run/", views.run_single),
    path("run-with-file/", views.run_with_file),
    path("run-with-upload/", views.run_with_upload),
    path("batch/run/", views.run_batch),
]

from django.urls import path
from .runners.task_views import task_status, task_result
from servicenow.pages import dashboard

urlpatterns = [

    # ── Dashboard ─────────────────────────────────────────────
    path("", dashboard, name="dashboard"),

    # ── Task status / results ──────────────────────────────────
    path("tasks/<str:task_id>/status/", task_status),
    path("tasks/<str:task_id>/result/", task_result),

]

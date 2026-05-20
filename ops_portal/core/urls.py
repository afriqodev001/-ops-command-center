from django.urls import path
from .views import dashboard
from .runners.task_views import task_status, task_result

urlpatterns = [

    # ── Dashboard ─────────────────────────────────────────────
    # `dashboard` dispatches to whichever view a feature app registered
    # (see core/extensions.py); falls back to core's minimal landing page.
    path("", dashboard, name="dashboard"),

    # ── Task status / results ──────────────────────────────────
    path("tasks/<str:task_id>/status/", task_status),
    path("tasks/<str:task_id>/result/", task_result),

]

from django.urls import path
from .runners.task_views import task_status, task_result

# The rich dashboard currently lives in the servicenow app. When servicenow
# isn't part of the active OPS_PROFILE, fall back to a minimal core dashboard
# so the site still has a working landing page.
try:
    from servicenow.pages import dashboard
except Exception:
    from .views import fallback_dashboard as dashboard

urlpatterns = [

    # ── Dashboard ─────────────────────────────────────────────
    path("", dashboard, name="dashboard"),

    # ── Task status / results ──────────────────────────────────
    path("tasks/<str:task_id>/status/", task_status),
    path("tasks/<str:task_id>/result/", task_result),

]

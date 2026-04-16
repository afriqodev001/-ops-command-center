from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST

from ops_portal.celery import app as celery_app
from celery.result import AsyncResult


# ============================================================
# TASK STATUS / RESULTS
# ============================================================

@require_http_methods(["GET"])
def task_status(request, task_id: str):
    """
    GET /api/grafana/tasks/<task_id>/status/
    """
    res = AsyncResult(task_id, app=celery_app)

    return JsonResponse(
        {
            "task_id": task_id,
            "state": res.state,
            "ready": res.ready(),
            "successful": res.successful() if res.ready() else False,
            "failed": res.failed() if res.ready() else False,
        }
    )


@require_http_methods(["GET"])
def task_result(request, task_id: str):
    """
    GET /api/grafana/tasks/<task_id>/result/
    """
    res = AsyncResult(task_id, app=celery_app)

    if not res.ready():
        return JsonResponse(
            {
                "task_id": task_id,
                "state": res.state,
                "ready": False,
            },
            status=202,
        )

    return JsonResponse(
        {
            "task_id": task_id,
            "state": res.state,
            "ready": True,
            "result": res.result,
        }
    )

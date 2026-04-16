#Use this to globalize the task status and results

from celery.result import AsyncResult
from django.http import JsonResponse


def task_status(request, task_id):
    result = AsyncResult(task_id)

    return JsonResponse({
        "task_id": task_id,
        "state": result.state,
        "ready": result.ready(),
    })


def task_result(request, task_id):
    result = AsyncResult(task_id)

    if not result.ready():
        return JsonResponse({
            "task_id": task_id,
            "state": result.state,
            "ready": False,
        })

    if result.failed():
        return JsonResponse({
            "task_id": task_id,
            "state": "FAILURE",
            "error": str(result.result),
        })

    return JsonResponse({
        "task_id": task_id,
        "state": "SUCCESS",
        "ready": True,
        "result": result.result,
    })

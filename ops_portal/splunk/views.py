from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from splunk.tasks import (
    splunk_login_open_task,
    splunk_alerts_search_task,
    splunk_job_create_task,
    splunk_job_status_task,
    splunk_job_events_task,
    splunk_job_results_preview_task,
    splunk_search_run_task,
    splunk_search_run_async_task,
    splunk_alert_run_task,
    splunk_alert_run_async_task,
    splunk_presets_list_task,
    splunk_presets_run_task,
    splunk_presets_run_async_task,
    splunk_alerts_list_task,
)

import json


def _body(request):
    try:
        return json.loads(request.body or "{}")
    except Exception:
        return {}


@csrf_exempt
@require_POST
def splunk_login_open(request):
    """
    POST /api/splunk/login/open/

    Opens headed browser for Splunk SSO.
    """
    task = splunk_login_open_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def alerts_search(request):
    task = splunk_alerts_search_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def job_create(request):
    task = splunk_job_create_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def job_status(request):
    task = splunk_job_status_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def job_events(request):
    task = splunk_job_events_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def job_results_preview(request):
    task = splunk_job_results_preview_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def search_run(request):
    """
    POST /api/splunk/search/run/
    Enqueues a single Celery task that:
      create job -> poll -> return preview/events
    """
    task = splunk_search_run_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def search_run_async(request):
    task = splunk_search_run_async_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def alerts_run(request):
    task = splunk_alert_run_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def alerts_run_async(request):
    task = splunk_alert_run_async_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def presets_list(request):
    task = splunk_presets_list_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def presets_run(request):
    task = splunk_presets_run_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def presets_run_async(request):
    task = splunk_presets_run_async_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def alerts_list(request):
    task = splunk_alerts_list_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)

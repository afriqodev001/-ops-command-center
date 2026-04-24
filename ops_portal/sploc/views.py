from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from sploc.tasks import (
    sploc_login_open_task,
    sploc_trace_scrape_task,
    sploc_ai_ask_task,
)

import json


def _body(request):
    try:
        return json.loads(request.body or "{}")
    except Exception:
        return {}


@csrf_exempt
@require_POST
def sploc_login_open(request):
    task = sploc_login_open_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def trace_scrape(request):
    task = sploc_trace_scrape_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def ai_ask(request):
    task = sploc_ai_ask_task.delay(_body(request))
    return JsonResponse({"task_id": task.id}, status=202)

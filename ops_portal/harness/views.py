from django.shortcuts import render

# Create your views here.
# harness/views.py
import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from harness.tasks import (
    open_harness_login_task,
    environments_list_task,
    pipeline_execution_summary_task,
    pipeline_execution_summary_filtered_task,
    execution_inputset_v2_task,
    active_service_instances_task,
    fetch_plan_task,
    projects_list_task,
    pipelines_list_task,
    last_success_execution_with_inputset_filtered_task,
    last_success_by_infra_task,
)


@csrf_exempt
@require_POST
def harness_login_open(request):
    body = json.loads(request.body.decode() or "{}")
    task = open_harness_login_task.delay(body)
    return JsonResponse({"task_id": task.id})


@csrf_exempt
@require_POST
def harness_environments(request):
    body = json.loads(request.body.decode() or "{}")
    task = environments_list_task.delay(body)
    return JsonResponse({"task_id": task.id})


@csrf_exempt
@require_POST
def harness_pipeline_execution_summary(request):
    body = json.loads(request.body.decode() or "{}")
    task = pipeline_execution_summary_task.delay(body)
    return JsonResponse({"task_id": task.id})


@csrf_exempt
@require_POST
def harness_pipeline_execution_summary_filtered(request):
    body = json.loads(request.body.decode() or "{}")
    task = pipeline_execution_summary_filtered_task.delay(body)
    return JsonResponse({"task_id": task.id})


@csrf_exempt
@require_POST
def harness_execution_inputset_v2(request):
    body = json.loads(request.body.decode() or "{}")
    task = execution_inputset_v2_task.delay(body)
    return JsonResponse({"task_id": task.id})


@csrf_exempt
@require_POST
def harness_active_service_instances(request):
    body = json.loads(request.body.decode() or "{}")
    task = active_service_instances_task.delay(body)
    return JsonResponse({"task_id": task.id})


@csrf_exempt
@require_POST
def harness_projects(request):
    body = json.loads(request.body.decode() or "{}")
    task = projects_list_task.delay(body)
    return JsonResponse({"task_id": task.id})


@csrf_exempt
@require_POST
def harness_pipelines_list(request):
    body = json.loads(request.body.decode() or "{}")
    task = pipelines_list_task.delay(body)
    return JsonResponse({"task_id": task.id})


# NEW
@csrf_exempt
@require_POST
def harness_last_success_execution_filtered(request):
    body = json.loads(request.body.decode() or "{}")
    task = last_success_execution_with_inputset_filtered_task.delay(body)
    return JsonResponse({"task_id": task.id})


@csrf_exempt
@require_POST
def harness_fetch_plan(request):
    body = json.loads(request.body.decode() or "{}")
    task = fetch_plan_task.delay(body)
    return JsonResponse({"task_id": task.id})


@csrf_exempt
@require_POST
def harness_last_success_by_infra(request):
    """
    Returns last successful execution per infrastructure (DC).

    Supports:
    - explicit infra_identifiers
    - auto-discovery via discover_infrastructure=true
    """
    try:
        body = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "invalid_json", "detail": "Request body must be valid JSON"},
            status=400,
        )

    task = last_success_by_infra_task.delay(body)
    return JsonResponse({"task_id": task.id})
# tachyon/views.py

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from core.browser import (
    get_or_create_session,
    is_debug_alive,
    shutdown_browser,
    clear_session,
    launch_edge,
)

from tachyon.models import TachyonPreset
from tachyon.tasks import (
    run_tachyon_llm_task,
    run_tachyon_llm_with_file_task,
    run_tachyon_batch_task,
)

TACHYON_BASE = getattr(settings, "TACHYON_BASE", "https://your-tachyon-instance.net")


@csrf_exempt
@require_POST
def open_tachyon_login(request):
    user_key = request.user.username or "localuser"
    session = get_or_create_session("tachyon", user_key)

    if is_debug_alive(session["debug_port"]):
        shutdown_browser(session["debug_port"])
        clear_session("tachyon", user_key)
        session = get_or_create_session("tachyon", user_key)

    result = launch_edge(
        profile_dir=session["profile_dir"],
        debug_port=session["debug_port"],
        url=TACHYON_BASE,
        headless=False,
    )

    if result.get("status") == "failed":
        return JsonResponse({"error": "browser_start_failed"}, status=500)

    return JsonResponse(
        {
            "status": "login_opened",
            "profile_dir": session["profile_dir"],
            "debug_port": session["debug_port"],
            "mode": "headed",
        }
    )


@require_http_methods(["GET"])
def list_presets(request):
    presets = TachyonPreset.objects.filter(enabled=True).order_by("title")
    return JsonResponse(
        {
            "presets": [
                {
                    "slug": p.slug,
                    "title": p.title,
                    "description": p.description,
                    "preset_id": p.preset_id,
                    "default_model_id": p.default_model_id,
                    "parameters": p.parameters,
                    "system_instruction": p.system_instruction,
                    "version": p.version,
                }
                for p in presets
            ]
        }
    )


@csrf_exempt
@require_POST
def run_single(request):
    payload = json.loads(request.body or "{}")
    user_key = request.user.username or "localuser"

    preset_slug = payload.get("preset")
    query = payload.get("query")
    overrides = payload.get("overrides") or {}

    if not preset_slug or not query:
        return JsonResponse({"error": "preset and query are required"}, status=400)

    task = run_tachyon_llm_task.delay(
        user_key=user_key,
        preset_slug=preset_slug,
        query=query,
        overrides=overrides,
    )

    return JsonResponse({"task_id": task.id, "mode": "single"})


@csrf_exempt
@require_POST
def run_with_file(request):
    payload = json.loads(request.body or "{}")
    user_key = request.user.username or "localuser"

    preset_slug = payload.get("preset")
    query = payload.get("query")
    file_spec = payload.get("file") or {}
    overrides = payload.get("overrides") or {}
    reuse_if_exists = bool(payload.get("reuse_if_exists", True))

    if not preset_slug or not query:
        return JsonResponse({"error": "preset and query are required"}, status=400)

    if not isinstance(file_spec, dict) or not file_spec.get("path"):
        return JsonResponse({"error": "file.path is required"}, status=400)

    task = run_tachyon_llm_with_file_task.delay(
        user_key=user_key,
        preset_slug=preset_slug,
        query=query,
        file_path=file_spec["path"],
        folder_name=file_spec.get("folder_name", "uploads"),
        folder_id=file_spec.get("folder_id"),
        reuse_if_exists=reuse_if_exists,
        overrides=overrides,
    )

    return JsonResponse({"task_id": task.id, "mode": "with-file"})


@csrf_exempt
@require_POST
def run_with_upload(request):
    user_key = request.user.username or "localuser"

    preset_slug = request.POST.get("preset")
    query = request.POST.get("query")
    folder_name = request.POST.get("folder_name", "uploads")
    reuse_if_exists = request.POST.get("reuse_if_exists", "true").lower() == "true"

    overrides_raw = request.POST.get("overrides", "")
    overrides = {}
    if overrides_raw:
        try:
            overrides = json.loads(overrides_raw)
        except Exception:
            return JsonResponse({"error": "overrides must be valid JSON"}, status=400)

    if not preset_slug or not query:
        return JsonResponse({"error": "preset and query are required"}, status=400)

    up = request.FILES.get("file")
    if not up:
        return JsonResponse({"error": "file is required"}, status=400)

    max_bytes = int(getattr(settings, "TACHYON_UPLOAD_MAX_BYTES", 10 * 1024 * 1024))
    if up.size > max_bytes:
        return JsonResponse({"error": f"file exceeds max size {max_bytes} bytes"}, status=400)

    tmp_dir = Path(getattr(settings, "TACHYON_UPLOAD_TMP_DIR", "media/tachyon_uploads"))
    tmp_dir.mkdir(parents=True, exist_ok=True)

    safe_name = up.name.replace("\\", "_").replace("/", "_")
    tmp_name = f"{uuid.uuid4().hex}_{safe_name}"
    tmp_path = tmp_dir / tmp_name

    with open(tmp_path, "wb") as f:
        for chunk in up.chunks():
            f.write(chunk)

    task = run_tachyon_llm_with_file_task.delay(
        user_key=user_key,
        preset_slug=preset_slug,
        query=query,
        file_path=str(tmp_path),
        folder_name=folder_name,
        folder_id=None,
        reuse_if_exists=reuse_if_exists,
        overrides=overrides,
    )

    return JsonResponse(
        {
            "task_id": task.id,
            "mode": "with-upload",
            "tmp_file": str(tmp_path),
        }
    )


@csrf_exempt
@require_POST
def run_batch(request):
    payload = json.loads(request.body or "{}")
    user_key = request.user.username or "localuser"
    items = payload.get("items") or []

    if not isinstance(items, list) or not items:
        return JsonResponse({"error": "items must be a non-empty list"}, status=400)

    task = run_tachyon_batch_task.delay(user_key=user_key, items=items)

    return JsonResponse(
        {
            "task_id": task.id,
            "mode": "batch",
            "count": len(items),
        }
    )

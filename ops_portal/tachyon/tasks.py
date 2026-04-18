# tachyon/tasks.py

from __future__ import annotations

import copy
from django.conf import settings
from celery import shared_task

from tachyon.models import TachyonPreset
from tachyon.runners.tachyon_runner import TachyonRunner
from tachyon.services.tachyon_cache import (
    load_cache,
    save_cache,
    cache_lookup,
    cache_upsert,
)
from tachyon.services.tachyon_upload import sanitize_filename


@shared_task(bind=True)
def run_tachyon_llm_task(self, *, user_key: str, preset_slug: str, query: str, overrides: dict | None = None):
    overrides = overrides or {}
    try:
        preset = TachyonPreset.objects.get(slug=preset_slug, enabled=True)
    except TachyonPreset.DoesNotExist:
        return {"error": "preset_not_found", "detail": f"No enabled preset with slug '{preset_slug}'"}

    body = {
        "userId": overrides.get("userId") or getattr(settings, "TACHYON_DEFAULT_USER_ID", user_key),
        "presetId": preset.preset_id,
        "modelId": overrides.get("modelId") or preset.default_model_id,
        "parameters": overrides.get("parameters") or preset.parameters,
        "query": query,
        "systemInstruction": overrides.get("systemInstruction") or preset.system_instruction,
        "folderIdList": overrides.get("folderIdList", []),
        "fileIdList": overrides.get("fileIdList", []),
        "history": overrides.get("history", ""),
        "useRawFileContent": bool(overrides.get("useRawFileContent", False)),
    }

    runner = TachyonRunner(user_key)
    return runner.llm(body)


@shared_task
def cleanup_tachyon_tmp_file(path: str):
    import os
    try:
        if path and os.path.exists(path):
            os.remove(path)
            return {"deleted": True, "path": path}
    except Exception as e:
        return {"deleted": False, "path": path, "error": str(e)}
    return {"deleted": False, "path": path}


@shared_task(bind=True)
def run_tachyon_llm_with_file_task(
    self,
    *,
    user_key: str,
    preset_slug: str,
    query: str,
    file_path: str,
    folder_name: str = "uploads",
    folder_id: str | None = None,
    reuse_if_exists: bool = True,
    overrides: dict | None = None,
):
    overrides = overrides or {}
    try:
        preset = TachyonPreset.objects.get(slug=preset_slug, enabled=True)
    except TachyonPreset.DoesNotExist:
        return {"error": "preset_not_found", "detail": f"No enabled preset with slug '{preset_slug}'"}

    body = {
        "userId": overrides.get("userId") or getattr(settings, "TACHYON_DEFAULT_USER_ID", user_key),
        "presetId": preset.preset_id,
        "modelId": overrides.get("modelId") or preset.default_model_id,
        "parameters": overrides.get("parameters") or preset.parameters,
        "query": query,
        "systemInstruction": overrides.get("systemInstruction") or preset.system_instruction,
        "folderIdList": [],
        "fileIdList": [],
        "history": overrides.get("history", ""),
        "useRawFileContent": bool(overrides.get("useRawFileContent", False)),
    }

    safe_file_name = sanitize_filename(file_path.split("/")[-1].split("\\")[-1])

    cache = load_cache()
    cached_folder_id = None
    cached_file_id = None

    if reuse_if_exists:
        cached_folder_id, cached_file_id = cache_lookup(
            cache,
            user_id=body["userId"],
            preset_id=body["presetId"],
            folder_name=folder_name,
            file_name=safe_file_name,
            folder_id=folder_id,
        )

    runner = TachyonRunner(user_key)

    try:
        if cached_file_id:
            body["folderIdList"] = [cached_folder_id]
            body["fileIdList"] = [cached_file_id]

            out = runner.llm(body)
            return {
                "cache": {
                    "reused": True,
                    "folderId": cached_folder_id,
                    "fileId": cached_file_id,
                },
                "result": out,
            }

        body_copy = copy.deepcopy(body)
        out = runner.upload_and_llm(
            body=body_copy,
            file_path=file_path,
            folder_name=folder_name,
            folder_id=folder_id,
        )

        # upload_and_llm mutates the body it receives (adds folderIdList/fileIdList)
        folder_id2 = (body_copy.get("folderIdList") or [None])[0]
        file_id2 = (body_copy.get("fileIdList") or [None])[0]

        if folder_id2 and file_id2:
            cache_upsert(
                cache,
                user_id=body["userId"],
                preset_id=body["presetId"],
                folder_name=folder_name,
                file_name=safe_file_name,
                folder_id=folder_id2,
                file_id=file_id2,
                info_obj=None,
            )
            save_cache(cache)

        return {
            "cache": {
                "reused": False,
                "folderId": folder_id2,
                "fileId": file_id2,
            },
            "result": out,
        }

    finally:
        cleanup_tachyon_tmp_file.delay(file_path)


@shared_task(bind=True)
def run_tachyon_batch_task(self, *, user_key: str, items: list):
    runner = TachyonRunner(user_key)
    cache = load_cache()

    results = []

    for idx, item in enumerate(items or []):
        try:
            preset_slug = item.get("preset")
            query = item.get("query", "")
            overrides = item.get("overrides") or {}

            if not preset_slug or not query:
                raise ValueError("Each item must include preset and query")

            try:
                preset = TachyonPreset.objects.get(slug=preset_slug, enabled=True)
            except TachyonPreset.DoesNotExist:
                results.append({"index": idx, "ok": False, "error": "preset_not_found", "detail": f"No enabled preset '{preset_slug}'"})
                continue

            body = {
                "userId": overrides.get("userId") or getattr(settings, "TACHYON_DEFAULT_USER_ID", user_key),
                "presetId": preset.preset_id,
                "modelId": overrides.get("modelId") or preset.default_model_id,
                "parameters": overrides.get("parameters") or preset.parameters,
                "query": query,
                "systemInstruction": overrides.get("systemInstruction") or preset.system_instruction,
                "folderIdList": overrides.get("folderIdList", []),
                "fileIdList": overrides.get("fileIdList", []),
                "history": overrides.get("history", ""),
                "useRawFileContent": bool(overrides.get("useRawFileContent", False)),
            }

            file_spec = item.get("file")
            reuse = bool(item.get("reuse_if_exists", True))

            if file_spec:
                file_path = file_spec.get("path")
                folder_name = file_spec.get("folder_name", "uploads")
                folder_id = file_spec.get("folder_id")

                safe_file_name = sanitize_filename(file_path.split("/")[-1].split("\\")[-1])

                cached_folder_id, cached_file_id = (None, None)

                if reuse:
                    cached_folder_id, cached_file_id = cache_lookup(
                        cache,
                        user_id=body["userId"],
                        preset_id=body["presetId"],
                        folder_name=folder_name,
                        file_name=safe_file_name,
                        folder_id=folder_id,
                    )

                if cached_file_id:
                    body["folderIdList"] = [cached_folder_id]
                    body["fileIdList"] = [cached_file_id]
                    out = runner.llm(body)
                    results.append({"index": idx, "ok": True, "cache_reused": True, "result": out})
                else:
                    body_copy = copy.deepcopy(body)
                    out = runner.upload_and_llm(
                        body=body_copy,
                        file_path=file_path,
                        folder_name=folder_name,
                        folder_id=folder_id,
                    )

                    folder_id2 = (body_copy.get("folderIdList") or [None])[0]
                    file_id2 = (body_copy.get("fileIdList") or [None])[0]

                    if folder_id2 and file_id2:
                        cache_upsert(
                            cache,
                            user_id=body["userId"],
                            preset_id=body["presetId"],
                            folder_name=folder_name,
                            file_name=safe_file_name,
                            folder_id=folder_id2,
                            file_id=file_id2,
                            info_obj=None,
                        )

                    results.append({"index": idx, "ok": True, "cache_reused": False, "result": out})
            else:
                out = runner.llm(body)
                results.append({"index": idx, "ok": True, "result": out})

        except Exception as e:
            results.append({"index": idx, "ok": False, "error": "tachyon_batch_item_failed", "detail": str(e)})

    save_cache(cache)

    return {"mode": "batch", "count": len(results), "results": results}

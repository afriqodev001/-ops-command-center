from __future__ import annotations
import os

from celery import shared_task
from celery.result import AsyncResult
from django.utils import timezone

from core.browser import BrowserLoginRequired
from core.browser.registry import get_or_create_session

from copilot_chat.runners.copilot_runner import CopilotRunner
from copilot_chat.services.copilot_ops import build_client_for_user
from copilot_chat.services.copilot_attachments import (
    remove_all_attachments,
    attach_files,
)
from copilot_chat.services.copilot_downloads import save_latest_turn_downloads

from copilot_chat.models import CopilotRun, CopilotDownload, CopilotBatch

from selenium.common.exceptions import TimeoutException


def _user_key(body: dict) -> str:
    return (body or {}).get("user_key") or "localuser"


def _persist_run(task_id: str, user_key: str, payload: dict) -> CopilotRun:
    run, _ = CopilotRun.objects.get_or_create(
        task_id=task_id,
        defaults={
            "user_key": user_key,
            "prompt": payload.get("prompt", ""),
            "status": "running",
        },
    )
    return run


def _finalize_run(run: CopilotRun, result: dict) -> CopilotRun:
    run.status = result.get("status") or run.status
    run.answer = result.get("answer") or ""
    run.guid = result.get("guid") or ""
    run.run_id = result.get("run_id") or ""
    run.timestamp_utc = result.get("timestamp_utc") or ""
    run.error = result.get("error") or ""
    run.uploaded_files = result.get("uploaded_files") or result.get("upload_paths") or []
    run.save()

    # downloads
    for d in (result.get("downloads") or []):
        disk_filename = os.path.basename(d.get("saved_path", ""))
        try:
            CopilotDownload.objects.create(
                run=run,
                filename=d.get("filename") or disk_filename,
                disk_filename=disk_filename,
            )
        except Exception:
            continue

    return run


@shared_task(bind=True)
def copilot_auth_check_task(self, body: dict):
    body = body or {}
    user_key = _user_key(body)

    try:
        runner = CopilotRunner(user_key)
        _ = runner.get_driver()

        client = build_client_for_user(user_key)
        client.attach()

        guid = client.ensure_ready()

        return {
            "authed": True,
            "status": "ok",
            "detail": "Copilot is ready (chat input detected).",
            "user_key": user_key,
            "guid": guid,
        }

    except TimeoutException as te:
        return {
            "authed": False,
            "status": "login_required",
            "detail": "Copilot not ready. Complete login then retry.",
            "user_key": user_key,
            "error": str(te),
        }

    except Exception as e:
        return {
            "authed": False,
            "status": "error",
            "detail": "Auth check failed.",
            "user_key": user_key,
            "error": str(e),
        }


@shared_task(bind=True)
def copilot_login_open_task(self, body: dict):
    user_key = _user_key(body)
    runner = CopilotRunner(user_key)

    try:
        runner.open_login()
    except BrowserLoginRequired:
        pass

    session = get_or_create_session("copilot", user_key)

    return {
        "status": "login_opened",
        "profile_dir": session["profile_dir"],
        "debug_port": session["debug_port"],
        "mode": session.get("mode") or "headed",
        "pid": session.get("pid"),
    }


@shared_task(bind=True)
def copilot_run_prompt_task(self, body: dict):
    body = body or {}
    user_key = _user_key(body)
    prompt = (body.get("prompt") or "").strip()

    if not prompt:
        return {"error": "missing_parameter", "detail": "prompt is required"}

    run = _persist_run(self.request.id, user_key, {"prompt": prompt})

    runner = CopilotRunner(user_key)
    _ = runner.get_driver()

    client = build_client_for_user(user_key)
    client.attach()
    client.ensure_ready()

    res = client.run_prompt(prompt)
    downloads = save_latest_turn_downloads(client.driver, user_key)

    result = {
        "prompt": res.prompt,
        "answer": res.answer,
        "status": res.status,
        "timestamp_utc": res.timestamp_utc,
        "guid": res.guid,
        "run_id": res.run_id,
        "error": res.error,
        "downloads": downloads,
    }

    _finalize_run(run, result)
    return result


@shared_task(bind=True)
def copilot_run_prompt_with_files_task(self, body: dict):
    body = body or {}
    user_key = _user_key(body)
    prompt = (body.get("prompt") or "").strip()
    upload_paths = body.get("upload_paths") or []
    clear_first = bool(body.get("clear_attachments", True))

    if not prompt:
        return {"error": "missing_parameter", "detail": "prompt is required"}
    if not upload_paths:
        return {"error": "missing_parameter", "detail": "upload_paths is required"}

    run = _persist_run(self.request.id, user_key, {"prompt": prompt})

    runner = CopilotRunner(user_key)
    _ = runner.get_driver()

    client = build_client_for_user(user_key)
    client.attach()
    client.ensure_ready()

    if clear_first:
        remove_all_attachments(client.driver)

    attached = attach_files(client.driver, upload_paths)

    res = client.run_prompt(prompt)
    downloads = save_latest_turn_downloads(client.driver, user_key)

    result = {
        "prompt": res.prompt,
        "answer": res.answer,
        "status": res.status,
        "timestamp_utc": res.timestamp_utc,
        "guid": res.guid,
        "run_id": res.run_id,
        "error": res.error,
        "uploaded_files": attached,
        "downloads": downloads,
    }

    _finalize_run(run, result)
    return result


@shared_task(bind=True)
def copilot_run_batch_task(self, body: dict):
    body = body or {}
    user_key = _user_key(body)
    prompts = body.get("prompts") or []
    name = (body.get("name") or "").strip()

    batch = CopilotBatch.objects.create(
        user_key=user_key,
        task_id=self.request.id,
        name=name,
        status="running",
        prompts=prompts,
    )

    results = []

    try:
        runner = CopilotRunner(user_key)
        _ = runner.get_driver()

        client = build_client_for_user(user_key)
        client.attach()
        client.ensure_ready()

        for p in prompts:
            p2 = (p or "").strip()
            if not p2:
                continue

            res = client.run_prompt(p2)
            downloads = save_latest_turn_downloads(client.driver, user_key)

            run = CopilotRun.objects.create(
                user_key=user_key,
                task_id=f"{self.request.id}:{len(results)+1}",
                prompt=res.prompt,
                status=res.status,
                timestamp_utc=res.timestamp_utc,
                guid=res.guid or "",
                run_id=res.run_id or "",
                answer=res.answer or "",
                error=res.error or "",
            )

            for d in (downloads or []):
                disk_filename = os.path.basename(d.get("saved_path", ""))
                try:
                    CopilotDownload.objects.create(
                        run=run,
                        filename=d.get("filename") or disk_filename,
                        disk_filename=disk_filename,
                    )
                except Exception:
                    continue

            results.append({
                "prompt": res.prompt,
                "status": res.status,
                "timestamp_utc": res.timestamp_utc,
                "guid": res.guid,
                "run_id": res.run_id,
                "answer": res.answer,
                "error": res.error,
                "downloads": downloads,
            })

        batch.status = "ok"
        batch.save()

        return {"status": "ok", "count": len(results), "results": results}

    except Exception as e:
        batch.status = "error"
        batch.error = str(e)
        batch.save()
        return {"status": "error", "error": str(e), "results": results}
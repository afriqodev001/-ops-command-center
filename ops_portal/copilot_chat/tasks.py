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
    """Step-by-step readiness check with detailed status at each phase."""
    body = body or {}
    user_key = _user_key(body)

    # Step 1: Check if browser is already running (don't create one)
    from core.browser.registry import load_session
    from core.browser.health import is_debug_alive
    session = load_session('copilot', user_key)
    if not session or not is_debug_alive(session.get('debug_port')):
        return {
            "authed": False, "status": "error", "user_key": user_key,
            "detail": "Browser not running. Click Connect Copilot in the sidebar to open the browser first.",
            "step": "browser",
        }

    # Step 2: Attach to browser
    try:
        client = build_client_for_user(user_key)
        client.attach()
    except Exception as e:
        return {
            "authed": False, "status": "error", "user_key": user_key,
            "detail": "Could not attach to browser. Try Reset Session then Connect again.",
            "step": "attach", "error": str(e),
        }

    # Step 3: Teams loaded?
    try:
        client.ensure_teams_open()
    except Exception as e:
        return {
            "authed": False, "status": "login_required", "user_key": user_key,
            "detail": "Teams is not loaded. Make sure you're logged into Teams in the browser.",
            "step": "teams", "error": str(e),
        }

    # Step 4: Click Copilot in left rail
    try:
        guid = client.click_copilot_left_rail()
    except TimeoutException:
        return {
            "authed": False, "status": "login_required", "user_key": user_key,
            "detail": "Copilot not found in the Teams left rail. Make sure Copilot is enabled for your account and visible in the sidebar. Try clicking it manually, then check status again.",
            "step": "copilot_rail",
        }
    except Exception as e:
        return {
            "authed": False, "status": "error", "user_key": user_key,
            "detail": f"Failed to click Copilot: {e}",
            "step": "copilot_rail", "error": str(e),
        }

    # Step 5: Switch to Copilot iframe and find input
    try:
        client.switch_to_copilot_context(guid)
    except TimeoutException:
        return {
            "authed": False, "status": "login_required", "user_key": user_key,
            "detail": "Copilot was clicked but the chat interface didn't load. This can happen if Copilot is still loading — wait a few seconds and check again.",
            "step": "iframe", "guid": guid,
        }
    except Exception as e:
        return {
            "authed": False, "status": "error", "user_key": user_key,
            "detail": f"Copilot iframe error: {e}",
            "step": "iframe", "error": str(e),
        }

    return {
        "authed": True,
        "status": "ok",
        "detail": "Copilot is ready (chat input detected).",
        "user_key": user_key,
        "guid": guid,
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

    try:
        runner = CopilotRunner(user_key)
        _ = runner.get_driver()
    except Exception as e:
        result = {"prompt": prompt, "status": "error", "answer": "",
                  "error": f"Browser session failed: {e}. Reconnect via the sidebar."}
        _finalize_run(run, result)
        return result

    try:
        client = build_client_for_user(user_key)
        client.attach()
        client.ensure_ready()
    except TimeoutException:
        result = {"prompt": prompt, "status": "error", "answer": "",
                  "error": "Copilot is not ready — the chat input was not found. "
                           "Make sure Teams is open, Copilot is selected in the left rail, "
                           "and the chat interface has fully loaded."}
        _finalize_run(run, result)
        return result
    except Exception as e:
        result = {"prompt": prompt, "status": "error", "answer": "",
                  "error": f"Copilot attach failed: {e}"}
        _finalize_run(run, result)
        return result

    try:
        res = client.run_prompt(prompt)
        downloads = save_latest_turn_downloads(client.driver, user_key)
    except TimeoutException:
        result = {"prompt": prompt, "status": "timeout", "answer": "",
                  "error": "Copilot did not respond within the timeout period. "
                           "The prompt may be too complex, or Copilot may be unresponsive."}
        _finalize_run(run, result)
        return result
    except Exception as e:
        result = {"prompt": prompt, "status": "error", "answer": "",
                  "error": f"Prompt execution failed: {e}"}
        _finalize_run(run, result)
        return result

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

    try:
        runner = CopilotRunner(user_key)
        _ = runner.get_driver()
    except Exception as e:
        result = {"prompt": prompt, "status": "error", "answer": "",
                  "error": f"Browser session failed: {e}. Reconnect via the sidebar."}
        _finalize_run(run, result)
        return result

    try:
        client = build_client_for_user(user_key)
        client.attach()
        client.ensure_ready()
    except TimeoutException:
        result = {"prompt": prompt, "status": "error", "answer": "",
                  "error": "Copilot is not ready — the chat input was not found. "
                           "Make sure Teams is open and Copilot is selected."}
        _finalize_run(run, result)
        return result
    except Exception as e:
        result = {"prompt": prompt, "status": "error", "answer": "",
                  "error": f"Copilot attach failed: {e}"}
        _finalize_run(run, result)
        return result

    try:
        if clear_first:
            remove_all_attachments(client.driver)
        attached = attach_files(client.driver, upload_paths)
        res = client.run_prompt(prompt)
        downloads = save_latest_turn_downloads(client.driver, user_key)
    except TimeoutException:
        result = {"prompt": prompt, "status": "timeout", "answer": "",
                  "error": "Copilot did not respond within the timeout period."}
        _finalize_run(run, result)
        return result
    except Exception as e:
        result = {"prompt": prompt, "status": "error", "answer": "",
                  "error": f"Prompt execution failed: {e}"}
        _finalize_run(run, result)
        return result

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
    except Exception as e:
        batch.status = "error"
        batch.error = f"Browser session failed: {e}. Reconnect via the sidebar."
        batch.save()
        return {"status": "error", "error": batch.error, "results": []}

    try:
        client = build_client_for_user(user_key)
        client.attach()
        client.ensure_ready()
    except TimeoutException:
        batch.status = "error"
        batch.error = ("Copilot is not ready — the chat input was not found. "
                       "Make sure Teams is open and Copilot is selected.")
        batch.save()
        return {"status": "error", "error": batch.error, "results": []}
    except Exception as e:
        batch.status = "error"
        batch.error = f"Copilot attach failed: {e}"
        batch.save()
        return {"status": "error", "error": batch.error, "results": []}

    try:

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
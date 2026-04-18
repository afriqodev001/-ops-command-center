from __future__ import annotations

import os
import json
import uuid

from celery.result import AsyncResult
from django.conf import settings
from django.http import JsonResponse, FileResponse, Http404, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction

from copilot_chat.forms import RunPromptForm, BatchRunForm
from copilot_chat.models import CopilotRun, CopilotBatch, PromptPack, Prompt
from copilot_chat.services.prompt_packs_store import load_all_packs
from copilot_chat.services.export_utils import runs_to_csv_bytes, runs_to_json_bytes

from copilot_chat.tasks import (
    copilot_login_open_task,
    copilot_run_prompt_task,
    copilot_run_prompt_with_files_task,
    copilot_run_batch_task,
    copilot_auth_check_task,
)

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _json_body(request):
    return json.loads(request.body or "{}")


PRIMARY_SITUATIONS = {
    "All": None,
    "Alert / Incident": ["alert", "incident"],
    "Vendor / External": ["vendor", "external-dependency"],
    "Customer Impact": ["customer-impact", "loan-flow", "ui"],
    "Platform / Infrastructure": ["platform", "ocp", "logging", "mq", "integration"],
    "Ownership / Process": ["ownership", "handoff", "assignment", "sla"],
    "Shift / Awareness": ["on-call", "shift-start", "shift-end", "situational-awareness"],
    "Communication / Status": ["communication", "summary", "leadership", "mim"],
}


def _filter_packs_by_situation(packs, situation):
    if situation == "All":
        return packs
    required = set(PRIMARY_SITUATIONS.get(situation) or [])
    out = []
    for p in packs:
        if required.intersection(set(p.tags or [])):
            out.append(p)
    return out


# -------------------------------------------------------------------
# AUTH CHECK (HTMX polling)
# -------------------------------------------------------------------

@require_POST
def ui_auth_check(request):
    user_key = (request.POST.get("user_key") or "localuser").strip() or "localuser"
    task = copilot_auth_check_task.delay({"user_key": user_key})

    return render(request, "copilot_chat/partials/_auth_status.html", {
        "user_key": user_key,
        "state": "checking",
        "task_id": task.id,
        "detail": "Checking Copilot session...",
    })


@require_GET
def ui_auth_poll(request, task_id: str):
    ar = AsyncResult(task_id)

    if ar.state in ("PENDING", "RECEIVED", "STARTED"):
        return render(request, "copilot_chat/partials/_auth_status.html", {
            "state": "checking",
            "task_id": task_id,
            "detail": "Checking Copilot session...",
        })

    if ar.state == "FAILURE":
        return render(request, "copilot_chat/partials/_auth_status.html", {
            "state": "error",
            "detail": "Auth check task failed.",
            "error": str(ar.result),
        })

    result = ar.result or {}
    return render(request, "copilot_chat/partials/_auth_status.html", {
        "state": result.get("status") or "error",
        "detail": result.get("detail") or "",
        "user_key": result.get("user_key") or "localuser",
        "guid": result.get("guid"),
        "error": result.get("error"),
    })


# -------------------------------------------------------------------
# MAIN UI
# -------------------------------------------------------------------

@require_GET
def copilot_home(request):
    packs = load_all_packs()
    situation = request.GET.get("situation", "All")
    filtered = _filter_packs_by_situation(packs, situation)

    recent_runs = CopilotRun.objects.order_by("-created_at")[:10]

    ctx = {
        "run_form": RunPromptForm(),
        "batch_form": BatchRunForm(),
        "packs": filtered,
        "all_situations": list(PRIMARY_SITUATIONS.keys()),
        "situation": situation,
        "recent_runs": recent_runs,
    }
    return render(request, "copilot_chat/index.html", ctx)


# -------------------------------------------------------------------
# PROMPT PACKS
# -------------------------------------------------------------------

@require_GET
def packs_list_partial(request):
    raw = (request.GET.get("situation") or "").strip().lower()

    if raw in ("", "all", "all situations"):
        situation = ""
    else:
        situation = raw

    packs = PromptPack.objects.all()

    if hasattr(PromptPack, "enabled"):
        packs = packs.filter(enabled=True)

    if situation:
        packs = packs.filter(tags__icontains=situation)

    packs = packs.order_by("name")

    situation_set = set()
    for tags in PromptPack.objects.values_list("tags", flat=True):
        for part in (tags or "").split(","):
            part = part.strip().lower()
            if part:
                situation_set.add(part)

    return render(request, "copilot_chat/partials/_packs_list.html", {
        "packs": packs,
        "all_situations": sorted(situation_set),
        "situation": situation,
    })

@require_GET
def copilot_run_detail_partial(request, run_id):
    run = get_object_or_404(CopilotRun, id=run_id)
    
    # reuse the existing run UI 
    return render(
        request,
        "copilot_chat/partials/_run_detail_shell.html",
        {
            "run": run,
            "disable_polling": True,
            "force_open": True,
        
        },
    )

@require_GET
def prompt_pack_view_modal(request, pack_id):
    pack = get_object_or_404(PromptPack, id=pack_id)
    prompts = pack.prompts.order_by("order")

    return render(request, "copilot_chat/partials/prompt_pack_view_modal.html", {
        "pack": pack,
        "prompts": prompts,
    })


@require_GET
def prompt_pack_editor(request, pk=None):
    pack = None
    prompts = []

    if pk:
        pack = get_object_or_404(PromptPack, pk=pk)
        prompts = list(pack.prompts.order_by("order"))

    next_order = (max([p.order for p in prompts], default=0) + 1)

    return render(request, "copilot_chat/partials/prompt_pack_editor_modal.html", {
        "pack": pack,
        "prompts": prompts,
        "next_order": next_order,
    })


@require_GET
def prompt_pack_prompt_row(request):
    try:
        order = int(request.GET.get("order", "1"))
    except ValueError:
        order = 1

    return render(request, "copilot_chat/partials/_prompt_pack_prompt_row.html", {
        "prompt": None,
        "order": order,
    })


def _normalize_tags(tags_str: str) -> str:
    tags = []
    for t in (tags_str or "").split(","):
        t = (t or "").strip()
        if t:
            tags.append(t.lower())

    seen = set()
    out = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)

    return ", ".join(out)


@require_POST
@transaction.atomic
def prompt_pack_save(request):
    pack_id = request.POST.get("pack_id", "").strip()

    if pack_id:
        pack = get_object_or_404(PromptPack, pk=pack_id)
    else:
        pack = PromptPack()

    pack.name = (request.POST.get("name") or "").strip() or "Untitled Pack"
    pack.description = (request.POST.get("description") or "").strip()
    pack.tags = _normalize_tags(request.POST.get("tags") or "")

    if hasattr(pack, "enabled"):
        pack.enabled = (request.POST.get("enabled") == "on")

    pack.save()

    prompt_ids = request.POST.getlist("prompt_id")
    prompt_orders = request.POST.getlist("prompt_order")
    prompt_texts = request.POST.getlist("prompt_text")
    prompt_deletes = request.POST.getlist("prompt_delete")

    existing = {str(p.id): p for p in pack.prompts.all()}

    for i in range(len(prompt_texts)):
        pid = (prompt_ids[i] or "").strip()
        text = (prompt_texts[i] or "").strip()
        order_raw = (prompt_orders[i] or "").strip()
        delete_flag = (prompt_deletes[i] or "").strip()

        if not text and not pid:
            continue

        try:
            order = int(order_raw) if order_raw else (i + 1)
        except ValueError:
            order = (i + 1)

        if delete_flag == "1" and pid and pid in existing:
            existing[pid].delete()
            continue

        if pid and pid in existing:
            p = existing[pid]
            p.text = text
            p.order = order
            p.save(update_fields=["text", "order"])
            continue

        if text:
            Prompt.objects.create(pack=pack, order=order, text=text)

    if pack.prompts.count() == 0:
        Prompt.objects.create(pack=pack, order=1, text="")

    for idx, p in enumerate(pack.prompts.order_by("order", "id"), start=1):
        if p.order != idx:
            p.order = idx
            p.save(update_fields=["order"])

    packs = PromptPack.objects.all().order_by("name")

    all_situations = set()
    for t in PromptPack.objects.values_list("tags", flat=True):
        for part in (t or "").split(","):
            part = part.strip()
            if part:
                all_situations.add(part)

    response = render(request, "copilot_chat/partials/_packs_list.html", {
        "packs": packs,
        "all_situations": sorted(all_situations),
        "situation": "",
    })

    response["HX-Trigger"] = json.dumps({
        "prompt-pack-saved": {
            "id": pack.id,
            "message": f"Prompt pack '{pack.name}' saved successfully"
        }
    })

    return response


# -------------------------------------------------------------------
# RUN PROMPT
# -------------------------------------------------------------------

@require_POST
def ui_login_open(request):
    user_key = (request.POST.get("user_key") or "localuser").strip() or "localuser"
    task = copilot_login_open_task.delay({"user_key": user_key})

    return render(request, "copilot_chat/partials/_toast.html", {
        "kind": "info",
        "message": f"Opened login task. task_id={task.id}. Complete Teams/Copilot login.",
    })


@require_POST
def ui_run_prompt(request):
    form = RunPromptForm(request.POST)

    if not form.is_valid():
        return render(request, "copilot_chat/partials/_toast.html", {
            "kind": "error",
            "message": "Prompt is required.",
        }, status=400)

    user_key = (form.cleaned_data.get("user_key") or "localuser").strip()
    prompt = (form.cleaned_data.get("prompt") or "").strip()
    clear_attachments = bool(form.cleaned_data.get("clear_attachments"))

    files = request.FILES.getlist("files")
    file_names = [f.name for f in files]

    if files:
        base_dir = getattr(settings, "COPILOT_UPLOAD_TMP_DIR", "copilot_uploads_tmp")
        out_dir = os.path.join(base_dir, user_key)
        os.makedirs(out_dir, exist_ok=True)

        upload_paths = []
        for f in files:
            safe_name = f.name.replace("/", "_").replace("\\", "_")
            out_path = os.path.abspath(
                os.path.join(out_dir, f"{uuid.uuid4().hex}_{safe_name}")
            )
            with open(out_path, "wb") as fp:
                for chunk in f.chunks():
                    fp.write(chunk)
            upload_paths.append(out_path)

        payload = {
            "user_key": user_key,
            "prompt": prompt,
            "upload_paths": upload_paths,
            "clear_attachments": clear_attachments,
        }

        task = copilot_run_prompt_with_files_task.delay(payload)
    else:
        task = copilot_run_prompt_task.delay({
            "user_key": user_key,
            "prompt": prompt,
        })

    run = CopilotRun.objects.create(
        user_key=user_key,
        task_id=task.id,
        prompt=prompt,
        status="queued",
    )

    return render(request, "copilot_chat/partials/_run_card.html", {
        "run": run,
        "file_names": file_names,
    })


@require_GET
def ui_poll_run(request, task_id: str):
    run = get_object_or_404(CopilotRun, task_id=task_id)
    ar = AsyncResult(task_id)

    if ar.state in ("PENDING", "RECEIVED", "STARTED"):
        if run.status not in ("running", "queued"):
            run.status = "running"
            run.save(update_fields=["status"])
        return render(request, "copilot_chat/partials/_run_card.html", {"run": run})

    if ar.state == "FAILURE":
        run.status = "error"
        run.error = str(ar.result)
        run.save(update_fields=["status", "error"])
        return render(request, "copilot_chat/partials/_run_card.html", {"run": run})

    if ar.state == "SUCCESS":
        result = ar.result or {}
        run.status = result.get("status") or "ok"
        run.answer = result.get("answer") or ""
        run.guid = result.get("guid") or ""
        run.run_id = result.get("run_id") or ""
        run.timestamp_utc = result.get("timestamp_utc") or ""
        run.error = result.get("error") or ""
        run.uploaded_files = result.get("uploaded_files") or []
        run.save()

    return render(request, "copilot_chat/partials/_run_card.html", {"run": run})


# -------------------------------------------------------------------
# BATCH
# -------------------------------------------------------------------

@require_POST
def ui_run_batch(request):
    form = BatchRunForm(request.POST)

    if not form.is_valid():
        return render(request, "copilot_chat/partials/_toast.html", {
            "kind": "error",
            "message": "Batch text is required.",
        }, status=400)

    user_key = (form.cleaned_data.get("user_key") or "localuser").strip()
    name = (form.cleaned_data.get("name") or "").strip()
    raw = form.cleaned_data.get("batch_text") or ""

    prompts = []
    seen = set()
    for ln in raw.splitlines():
        p = ln.strip()
        if p and p not in seen:
            seen.add(p)
            prompts.append(p)

    if not prompts:
        return render(request, "copilot_chat/partials/_toast.html", {
            "kind": "error",
            "message": "No prompts found.",
        }, status=400)

    task = copilot_run_batch_task.delay({
        "user_key": user_key,
        "name": name,
        "prompts": prompts,
    })

    batch = CopilotBatch.objects.create(
        user_key=user_key,
        task_id=task.id,
        name=name,
        prompts=prompts,
        status="queued",
    )

    return render(request, "copilot_chat/partials/_batch_card.html", {"batch": batch})


@require_GET
def ui_poll_batch(request, task_id: str):
    batch = get_object_or_404(CopilotBatch, task_id=task_id)
    ar = AsyncResult(task_id)

    if ar.state in ("PENDING", "RECEIVED", "STARTED"):
        if batch.status not in ("running", "queued"):
            batch.status = "running"
            batch.save(update_fields=["status"])
        return render(request, "copilot_chat/partials/_batch_card.html", {"batch": batch})

    if ar.state == "FAILURE":
        batch.status = "error"
        batch.error = str(ar.result)
        batch.save(update_fields=["status", "error"])
        return render(request, "copilot_chat/partials/_batch_card.html", {"batch": batch})

    if ar.state == "SUCCESS":
        result = ar.result or {}
        batch.status = result.get("status") or "ok"
        batch.save()

    return render(request, "copilot_chat/partials/_batch_card.html", {"batch": batch})

@require_GET
def runs_list_partial(request):
    recent_runs = CopilotRun.objects.order_by("-created_at")[:25]
    return render(
        request,
        "copilot_chat/partials/_runs_list.html",
        {"recent_runs": recent_runs},
    )


@require_GET
def export_runs(request):
    """
    Export last N runs as CSV or JSON.
    Mirrors Streamlit export behavior.
    """
    fmt = (request.GET.get("fmt") or "csv").lower()
    limit = int(request.GET.get("limit") or "200")
    runs = CopilotRun.objects.order_by("-created_at")[:limit]

    if fmt == "json":
        data = runs_to_json_bytes(runs)
        resp = HttpResponse(data, content_type="application/json")
        resp["Content-Disposition"] = 'attachment; filename="copilot_runs.json"'
        return resp

    data = runs_to_csv_bytes(runs)
    resp = HttpResponse(data, content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="copilot_runs.csv"'
    return resp


# -------------------------------------------------------------------
# Existing API endpoints (kept)
# -------------------------------------------------------------------

@csrf_exempt
@require_POST
def copilot_login_open(request):
    task = copilot_login_open_task.delay(_json_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def copilot_run(request):
    task = copilot_run_prompt_task.delay(_json_body(request))
    return JsonResponse({"task_id": task.id}, status=202)


@csrf_exempt
@require_POST
def copilot_run_with_files(request):
    user_key = (request.POST.get("user_key") or "localuser").strip() or "localuser"
    prompt = (request.POST.get("prompt") or "").strip()
    if not prompt:
        return JsonResponse(
            {"error": "missing_parameter", "detail": "prompt is required"},
            status=400,
        )

    files = request.FILES.getlist("files")
    if not files:
        return JsonResponse(
            {"error": "missing_parameter", "detail": "files[] is required"},
            status=400,
        )

    base_dir = getattr(settings, "COPILOT_UPLOAD_TMP_DIR", "copilot_uploads_tmp")
    out_dir = os.path.join(base_dir, user_key)
    os.makedirs(out_dir, exist_ok=True)

    upload_paths = []
    for f in files:
        safe_name = f.name.replace("/", "_").replace("\\", "_")
        out_path = os.path.abspath(
            os.path.join(out_dir, f"{uuid.uuid4().hex}_{safe_name}")
        )

        with open(out_path, "wb") as fp:
            for chunk in f.chunks():
                fp.write(chunk)

        upload_paths.append(out_path)

    payload = {
        "user_key": user_key,
        "prompt": prompt,
        "upload_paths": upload_paths,
        "clear_attachments": True,
    }
    task = copilot_run_prompt_with_files_task.delay(payload)
    return JsonResponse({"task_id": task.id}, status=202)


@require_GET
def copilot_download(request, user_key: str, filename: str):
    base_dir = getattr(settings, "COPILOT_DOWNLOAD_DIR", "copilot_downloads")
    path = os.path.join(base_dir, user_key, filename)
    if not os.path.isfile(path):
        raise Http404("File not found")
    return FileResponse(open(path, "rb"), as_attachment=True, filename=filename)
"""
Harness workspace UI pages — CRUD + import/export for engineer-curated
projects / pipelines / services identifiers.

Three independent collections under one page (`/harness/workspace/`) with
tab navigation, identical action surface for each (list / editor / save /
delete / export / import).
"""
from __future__ import annotations

import json

from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .services import workspace as ws


def workspace_page(request):
    """Main /harness/workspace/ page — tabs for projects, pipelines, services."""
    initial_tab = request.GET.get('tab', 'projects')
    if initial_tab not in ('projects', 'pipelines', 'services'):
        initial_tab = 'projects'
    return render(request, 'harness/workspace.html', {
        'initial_tab': initial_tab,
        'projects': ws.list_projects(),
        'pipelines': ws.list_pipelines(),
        'services': ws.list_services(),
    })


# ─── Projects CRUD ─────────────────────────────────────────

def projects_list_partial(request):
    return render(request, 'harness/partials/ws_projects_list.html', {
        'projects': ws.list_projects(),
    })


def project_editor(request):
    ident = request.GET.get('identifier', '').strip()
    project = ws.get_project(ident) if ident else None
    return render(request, 'harness/partials/ws_project_editor.html', {
        'identifier': ident,
        'project': project,
    })


@csrf_exempt
@require_POST
def project_save(request):
    ident = request.POST.get('identifier', '').strip()
    if not ident:
        return render(request, 'harness/partials/ws_projects_list.html', {
            'projects': ws.list_projects(),
            'error': 'Project identifier is required.',
        })
    ws.save_project(ident, {
        'name': request.POST.get('name', ''),
        'org': request.POST.get('org', ''),
        'label': request.POST.get('label', ''),
        'default': bool(request.POST.get('default')),
    })
    return render(request, 'harness/partials/ws_projects_list.html', {
        'projects': ws.list_projects(),
        'saved_name': ident,
    })


@csrf_exempt
@require_POST
def project_delete(request):
    ident = request.POST.get('identifier', '').strip()
    if ident:
        ws.delete_project(ident)
    return render(request, 'harness/partials/ws_projects_list.html', {
        'projects': ws.list_projects(),
    })


# ─── Pipelines CRUD ────────────────────────────────────────

def pipelines_list_partial(request):
    return render(request, 'harness/partials/ws_pipelines_list.html', {
        'pipelines': ws.list_pipelines(),
        'projects': ws.list_projects(),
    })


def pipeline_editor(request):
    ident = request.GET.get('identifier', '').strip()
    pipeline = ws.get_pipeline(ident) if ident else None
    return render(request, 'harness/partials/ws_pipeline_editor.html', {
        'identifier': ident,
        'pipeline': pipeline,
        'projects': ws.list_projects(),
    })


@csrf_exempt
@require_POST
def pipeline_save(request):
    ident = request.POST.get('identifier', '').strip()
    if not ident:
        return render(request, 'harness/partials/ws_pipelines_list.html', {
            'pipelines': ws.list_pipelines(),
            'projects': ws.list_projects(),
            'error': 'Pipeline identifier is required.',
        })
    ws.save_pipeline(ident, {
        'name': request.POST.get('name', ''),
        'project': request.POST.get('project', ''),
        'services': request.POST.get('services', ''),
        'label': request.POST.get('label', ''),
        'default': bool(request.POST.get('default')),
    })
    return render(request, 'harness/partials/ws_pipelines_list.html', {
        'pipelines': ws.list_pipelines(),
        'projects': ws.list_projects(),
        'saved_name': ident,
    })


@csrf_exempt
@require_POST
def pipeline_delete(request):
    ident = request.POST.get('identifier', '').strip()
    if ident:
        ws.delete_pipeline(ident)
    return render(request, 'harness/partials/ws_pipelines_list.html', {
        'pipelines': ws.list_pipelines(),
        'projects': ws.list_projects(),
    })


# ─── Services CRUD ─────────────────────────────────────────

def services_list_partial(request):
    return render(request, 'harness/partials/ws_services_list.html', {
        'services': ws.list_services(),
        'projects': ws.list_projects(),
    })


def service_editor(request):
    name = request.GET.get('name', '').strip()
    service = ws.get_service(name) if name else None
    return render(request, 'harness/partials/ws_service_editor.html', {
        'name': name,
        'service': service,
        'projects': ws.list_projects(),
        'pipelines': ws.list_pipelines(),
    })


@csrf_exempt
@require_POST
def service_save(request):
    name = request.POST.get('name', '').strip()
    if not name:
        return render(request, 'harness/partials/ws_services_list.html', {
            'services': ws.list_services(),
            'projects': ws.list_projects(),
            'error': 'Service name is required.',
        })
    ws.save_service(name, {
        'project': request.POST.get('project', ''),
        'pipelines': request.POST.get('pipelines', ''),
        'envs': request.POST.get('envs', ''),
        'infras': request.POST.get('infras', ''),
        'notes': request.POST.get('notes', ''),
        'default': bool(request.POST.get('default')),
    })
    return render(request, 'harness/partials/ws_services_list.html', {
        'services': ws.list_services(),
        'projects': ws.list_projects(),
        'saved_name': name,
    })


@csrf_exempt
@require_POST
def service_delete(request):
    name = request.POST.get('name', '').strip()
    if name:
        ws.delete_service(name)
    return render(request, 'harness/partials/ws_services_list.html', {
        'services': ws.list_services(),
        'projects': ws.list_projects(),
    })


# ─── Export / Import ───────────────────────────────────────

def export_all(request):
    data = json.dumps(ws.export_workspace(), indent=2, default=str)
    resp = HttpResponse(data, content_type='application/json')
    resp['Content-Disposition'] = 'attachment; filename="harness_workspace.json"'
    return resp


def import_form(request):
    return render(request, 'harness/partials/ws_import_form.html')


@csrf_exempt
@require_POST
def import_preview(request):
    upload = request.FILES.get('file')
    if not upload:
        return render(request, 'harness/partials/ws_import_preview.html', {
            'error': 'No file selected.',
        })
    try:
        raw = upload.read()
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8-sig', errors='replace')
        data = json.loads(raw)
    except Exception as e:
        return render(request, 'harness/partials/ws_import_preview.html', {
            'error': f'Invalid JSON: {e}',
        })

    incoming_projects = data.get('projects') or {}
    incoming_pipelines = data.get('pipelines') or {}
    incoming_services = data.get('services') or {}

    if not (incoming_projects or incoming_pipelines or incoming_services):
        return render(request, 'harness/partials/ws_import_preview.html', {
            'error': 'No projects, pipelines, or services found in file.',
        })

    existing = ws._load_store()
    preview = {
        'projects': [
            {'identifier': k, 'name': (v or {}).get('name', ''), 'exists': k in existing['projects']}
            for k, v in (incoming_projects or {}).items()
        ],
        'pipelines': [
            {'identifier': k, 'name': (v or {}).get('name', ''), 'project': (v or {}).get('project', ''), 'exists': k in existing['pipelines']}
            for k, v in (incoming_pipelines or {}).items()
        ],
        'services': [
            {'name': k, 'project': (v or {}).get('project', ''), 'exists': k in existing['services']}
            for k, v in (incoming_services or {}).items()
        ],
    }
    return render(request, 'harness/partials/ws_import_preview.html', {
        'preview': preview,
        'workspace_json': json.dumps(data),
    })


@csrf_exempt
@require_POST
def import_confirm(request):
    try:
        data = json.loads(request.POST.get('workspace_json', '{}'))
    except json.JSONDecodeError:
        data = {}
    mode = request.POST.get('conflict_mode', 'skip')
    counts = ws.import_workspace(data, mode)
    # Re-render whichever tab the user is in (default projects)
    # Caller passes tab in form; default to projects
    tab = request.POST.get('tab', 'projects')
    if tab == 'pipelines':
        return render(request, 'harness/partials/ws_pipelines_list.html', {
            'pipelines': ws.list_pipelines(),
            'projects': ws.list_projects(),
            'import_counts': counts,
        })
    if tab == 'services':
        return render(request, 'harness/partials/ws_services_list.html', {
            'services': ws.list_services(),
            'projects': ws.list_projects(),
            'import_counts': counts,
        })
    return render(request, 'harness/partials/ws_projects_list.html', {
        'projects': ws.list_projects(),
        'import_counts': counts,
    })

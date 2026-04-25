"""
Harness workspace — file-backed store for engineer-curated identifiers.

Holds three independent collections:
- projects:  identifier (key) → {name, org, label, default, added_at}
- pipelines: identifier (key) → {name, project, services[], label, default, added_at}
- services:  name (key) → {project, pipelines[], envs[], notes, default, added_at}

Each collection's `default` flag marks an entry as a "pin" — surfaced first in
quick-pick chips on Pipelines / Executions / Instances pages.

Mirrors the SPLOC service catalog pattern. Engineer-maintained via the UI
(import/export of a JSON file) — no auto-discovery, no built-in defaults.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Any, List


_STORE_FILE = Path(__file__).parent.parent / 'harness_workspace.json'


def _empty() -> Dict[str, Dict[str, Any]]:
    return {"projects": {}, "pipelines": {}, "services": {}}


def _load_store() -> Dict[str, Dict[str, Any]]:
    if not _STORE_FILE.exists():
        return _empty()
    try:
        data = json.loads(_STORE_FILE.read_text(encoding='utf-8'))
    except Exception:
        return _empty()
    if not isinstance(data, dict):
        return _empty()
    base = _empty()
    for key in base.keys():
        section = data.get(key)
        if isinstance(section, dict):
            base[key] = section
    return base


def _save_store(data: Dict[str, Dict[str, Any]]) -> None:
    _STORE_FILE.write_text(json.dumps(data, indent=2, sort_keys=True), encoding='utf-8')


def _split_csv(raw: Any) -> List[str]:
    """Accept list or CSV string; return clean list."""
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str):
        return [x.strip() for x in raw.split(',') if x.strip()]
    return []


# ─── Projects ──────────────────────────────────────────────

def list_projects() -> Dict[str, Dict[str, Any]]:
    items = _load_store()['projects']
    out = {}
    for ident in sorted(items.keys()):
        cfg = items[ident] or {}
        out[ident] = {
            'identifier': ident,
            'name': cfg.get('name', ''),
            'org': cfg.get('org', ''),
            'label': cfg.get('label', ''),
            'default': bool(cfg.get('default')),
            'added_at': cfg.get('added_at'),
        }
    return out


def get_project(identifier: str) -> Dict[str, Any] | None:
    return list_projects().get(identifier)


def save_project(identifier: str, meta: Dict[str, Any]) -> None:
    if not identifier:
        return
    store = _load_store()
    existing = (store['projects'].get(identifier) or {})
    store['projects'][identifier] = {
        'name': str(meta.get('name', '')).strip(),
        'org': str(meta.get('org', '')).strip(),
        'label': str(meta.get('label', '')).strip(),
        'default': bool(meta.get('default')),
        'added_at': existing.get('added_at') or time.time(),
    }
    _save_store(store)


def delete_project(identifier: str) -> None:
    store = _load_store()
    if identifier in store['projects']:
        del store['projects'][identifier]
        _save_store(store)


# ─── Pipelines ─────────────────────────────────────────────

def list_pipelines() -> Dict[str, Dict[str, Any]]:
    items = _load_store()['pipelines']
    out = {}
    for ident in sorted(items.keys()):
        cfg = items[ident] or {}
        out[ident] = {
            'identifier': ident,
            'name': cfg.get('name', ''),
            'project': cfg.get('project', ''),
            'services': cfg.get('services') or [],
            'label': cfg.get('label', ''),
            'default': bool(cfg.get('default')),
            'added_at': cfg.get('added_at'),
        }
    return out


def get_pipeline(identifier: str) -> Dict[str, Any] | None:
    return list_pipelines().get(identifier)


def save_pipeline(identifier: str, meta: Dict[str, Any]) -> None:
    if not identifier:
        return
    store = _load_store()
    existing = (store['pipelines'].get(identifier) or {})
    store['pipelines'][identifier] = {
        'name': str(meta.get('name', '')).strip(),
        'project': str(meta.get('project', '')).strip(),
        'services': _split_csv(meta.get('services')),
        'label': str(meta.get('label', '')).strip(),
        'default': bool(meta.get('default')),
        'added_at': existing.get('added_at') or time.time(),
    }
    _save_store(store)


def delete_pipeline(identifier: str) -> None:
    store = _load_store()
    if identifier in store['pipelines']:
        del store['pipelines'][identifier]
        _save_store(store)


def pipelines_for_service(service_name: str) -> List[Dict[str, Any]]:
    """Return all pinned pipelines that list this service."""
    if not service_name:
        return []
    out = []
    for p in list_pipelines().values():
        if service_name in (p.get('services') or []):
            out.append(p)
    return out


def pipelines_for_project(project_identifier: str) -> List[Dict[str, Any]]:
    if not project_identifier:
        return []
    return [p for p in list_pipelines().values() if p.get('project') == project_identifier]


# ─── Services ──────────────────────────────────────────────

def list_services() -> Dict[str, Dict[str, Any]]:
    items = _load_store()['services']
    out = {}
    for name in sorted(items.keys()):
        cfg = items[name] or {}
        out[name] = {
            'name': name,
            'project': cfg.get('project', ''),
            'pipelines': cfg.get('pipelines') or [],
            'envs': cfg.get('envs') or [],
            'infras': cfg.get('infras') or [],
            'notes': cfg.get('notes', ''),
            'default': bool(cfg.get('default')),
            'added_at': cfg.get('added_at'),
        }
    return out


def get_service(name: str) -> Dict[str, Any] | None:
    return list_services().get(name)


def save_service(name: str, meta: Dict[str, Any]) -> None:
    if not name:
        return
    store = _load_store()
    existing = (store['services'].get(name) or {})
    store['services'][name] = {
        'project': str(meta.get('project', '')).strip(),
        'pipelines': _split_csv(meta.get('pipelines')),
        'envs': _split_csv(meta.get('envs')),
        'infras': _split_csv(meta.get('infras')),
        'notes': str(meta.get('notes', '')).strip(),
        'default': bool(meta.get('default')),
        'added_at': existing.get('added_at') or time.time(),
    }
    _save_store(store)


def delete_service(name: str) -> None:
    store = _load_store()
    if name in store['services']:
        del store['services'][name]
        _save_store(store)


def services_for_project(project_identifier: str) -> List[Dict[str, Any]]:
    if not project_identifier:
        return []
    return [s for s in list_services().values() if s.get('project') == project_identifier]


# ─── Pinned helpers (default=True items first) ──────────────

def pinned_projects() -> List[Dict[str, Any]]:
    return [p for p in list_projects().values() if p.get('default')]


def pinned_pipelines() -> List[Dict[str, Any]]:
    return [p for p in list_pipelines().values() if p.get('default')]


def pinned_services() -> List[Dict[str, Any]]:
    return [s for s in list_services().values() if s.get('default')]


# ─── Import / Export ───────────────────────────────────────

def export_workspace(
    project_idents: List[str] | None = None,
    pipeline_idents: List[str] | None = None,
    service_names: List[str] | None = None,
) -> Dict:
    projects = list_projects()
    pipelines = list_pipelines()
    services = list_services()
    if project_idents:
        projects = {k: v for k, v in projects.items() if k in project_idents}
    if pipeline_idents:
        pipelines = {k: v for k, v in pipelines.items() if k in pipeline_idents}
    if service_names:
        services = {k: v for k, v in services.items() if k in service_names}
    return {
        'projects': projects,
        'pipelines': pipelines,
        'services': services,
    }


def import_workspace(data: Dict, mode: str = 'skip') -> Dict[str, int]:
    """Import projects/pipelines/services. Mode: 'skip' or 'overwrite'."""
    counts = {'projects': 0, 'pipelines': 0, 'services': 0}
    if not isinstance(data, dict):
        return counts

    store = _load_store()

    incoming_projects = data.get('projects') or {}
    if isinstance(incoming_projects, dict):
        for ident, cfg in incoming_projects.items():
            if not ident or not isinstance(cfg, dict):
                continue
            if ident in store['projects'] and mode == 'skip':
                continue
            existing = store['projects'].get(ident) or {}
            store['projects'][ident] = {
                'name': cfg.get('name', ''),
                'org': cfg.get('org', ''),
                'label': cfg.get('label', ''),
                'default': bool(cfg.get('default')),
                'added_at': existing.get('added_at') or cfg.get('added_at') or time.time(),
            }
            counts['projects'] += 1

    incoming_pipelines = data.get('pipelines') or {}
    if isinstance(incoming_pipelines, dict):
        for ident, cfg in incoming_pipelines.items():
            if not ident or not isinstance(cfg, dict):
                continue
            if ident in store['pipelines'] and mode == 'skip':
                continue
            existing = store['pipelines'].get(ident) or {}
            store['pipelines'][ident] = {
                'name': cfg.get('name', ''),
                'project': cfg.get('project', ''),
                'services': _split_csv(cfg.get('services')),
                'label': cfg.get('label', ''),
                'default': bool(cfg.get('default')),
                'added_at': existing.get('added_at') or cfg.get('added_at') or time.time(),
            }
            counts['pipelines'] += 1

    incoming_services = data.get('services') or {}
    if isinstance(incoming_services, dict):
        for name, cfg in incoming_services.items():
            if not name or not isinstance(cfg, dict):
                continue
            if name in store['services'] and mode == 'skip':
                continue
            existing = store['services'].get(name) or {}
            store['services'][name] = {
                'project': cfg.get('project', ''),
                'pipelines': _split_csv(cfg.get('pipelines')),
                'envs': _split_csv(cfg.get('envs')),
                'infras': _split_csv(cfg.get('infras')),
                'notes': cfg.get('notes', ''),
                'default': bool(cfg.get('default')),
                'added_at': existing.get('added_at') or cfg.get('added_at') or time.time(),
            }
            counts['services'] += 1

    _save_store(store)
    return counts

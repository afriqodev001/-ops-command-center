# tachyon/services/tachyon_cache.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from django.conf import settings


def _cache_path() -> Path:
    """
    Where to store the Tachyon fileId cache.

    Defaults to: <BASE_DIR>/tachyon_out/file_cache.json
    Override via settings.TACHYON_CACHE_PATH if desired.
    """
    p = getattr(settings, "TACHYON_CACHE_PATH", None)
    if p:
        return Path(p).expanduser().resolve()

    base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
    out_dir = base_dir / "tachyon_out"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "file_cache.json"


def _cache_key(
    user_id: str,
    preset_id: str,
    folder_name: str,
    file_name: str,
    folder_id: Optional[str],
) -> str:
    fid = folder_id or ""
    return f"{user_id}|{preset_id}|{folder_name}|{file_name}|{fid}"


def _lock_path() -> Path:
    return _cache_path().with_suffix('.lock')


def _acquire_lock(lock_file):
    """Platform-safe file lock."""
    import sys
    if sys.platform == 'win32':
        import msvcrt
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _release_lock(lock_file):
    import sys
    if sys.platform == 'win32':
        import msvcrt
        try:
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        except Exception:
            pass
    else:
        import fcntl
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def load_cache() -> Dict[str, Any]:
    path = _cache_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_cache(cache: Dict[str, Any]) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = _lock_path()
    lock.touch(exist_ok=True)
    with open(lock, 'r+') as lf:
        try:
            _acquire_lock(lf)
            path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
        finally:
            _release_lock(lf)


def cache_lookup(
    cache: Dict[str, Any],
    *,
    user_id: str,
    preset_id: str,
    folder_name: str,
    file_name: str,
    folder_id: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (folderId, fileId) if found, else (None, None)
    """
    k1 = _cache_key(user_id, preset_id, folder_name, file_name, folder_id)
    rec = cache.get(k1)
    if isinstance(rec, dict) and rec.get("folderId") and rec.get("fileId"):
        return rec["folderId"], rec["fileId"]

    # If folder_id isn't specified, try any match for this filename (latest wins)
    if not folder_id:
        prefix = f"{user_id}|{preset_id}|{folder_name}|{file_name}|"
        candidates = []
        for k, v in cache.items():
            if (
                k.startswith(prefix)
                and isinstance(v, dict)
                and v.get("folderId")
                and v.get("fileId")
            ):
                candidates.append(v)

        def sort_key(v):
            return v.get("lastUsedTimestamp") or v.get("lastUpdatedTimestamp") or ""

        if candidates:
            candidates.sort(key=sort_key, reverse=True)
            return candidates[0].get("folderId"), candidates[0].get("fileId")

    return None, None


def cache_upsert(
    cache: Dict[str, Any],
    *,
    user_id: str,
    preset_id: str,
    folder_name: str,
    file_name: str,
    folder_id: str,
    file_id: str,
    info_obj: Optional[Dict[str, Any]] = None,
) -> None:
    rec = {
        "userId": user_id,
        "presetId": preset_id,
        "folderName": folder_name,
        "fileName": file_name,
        "folderId": folder_id,
        "fileId": file_id,
        "lastUpdatedTimestamp": None,
        "lastUsedTimestamp": None,
        "mimeType": None,
        "status": None,
        "id": None,
        "processedChunks": None,
        "totalChunks": None,
        "numOfTokens": None,
    }
    if isinstance(info_obj, dict):
        rec["lastUpdatedTimestamp"] = info_obj.get("lastUpdatedTimestamp")
        rec["lastUsedTimestamp"] = info_obj.get("lastUsedTimestamp")
        rec["mimeType"] = info_obj.get("mimeType")
        rec["status"] = info_obj.get("status")
        rec["id"] = info_obj.get("id")
        rec["processedChunks"] = info_obj.get("processedChunks")
        rec["totalChunks"] = info_obj.get("totalChunks")
        rec["numOfTokens"] = info_obj.get("numOfTokens")

    k = _cache_key(user_id, preset_id, folder_name, file_name, folder_id)
    cache[k] = rec
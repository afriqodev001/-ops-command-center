from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from django.conf import settings

def _upload_endpoint():
    base = getattr(settings, "TACHYON_BASE", "https://your-tachyon-instance.net")
    return f"{base.rstrip('/')}/upload_file"


MAX_PLAYGROUND_FILE_BYTES = int(getattr(settings, "TACHYON_MAX_FILE_BYTES", 10 * 1024 * 1024))
MIN_FILE_BYTES = int(getattr(settings, "TACHYON_MIN_FILE_BYTES", 5))


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name or "file")


def canonical_mime_type(path: str) -> str:
    suf = Path(path).suffix.lower()
    if suf == ".csv":
        return "text/csv"
    if suf == ".tsv":
        return "text/tab-separated-values"
    if suf == ".txt":
        return "text/plain"
    if suf == ".json":
        return "application/json"
    if suf == ".pdf":
        return "application/pdf"
    if suf == ".xlsx":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if suf == ".xls":
        return "application/vnd.ms-excel"
    if suf in (".png", ".jpg", ".jpeg"):
        return f"image/{suf.lstrip('.')}".replace("jpg", "jpeg")
    mt, _ = mimetypes.guess_type(path)
    return mt or "application/octet-stream"


def extract_ids_from_upload_response(data: Any) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]]]:
    """
    Tachyon upload response sometimes returns:
    - list[dict] wrapper
    - {"data": {"Info": {...}}}
    - {"Info": {...}}
    """
    if data is None:
        return None, None, None
    if isinstance(data, list) and data:
        data = data[0]
    if not isinstance(data, dict):
        return None, None, None

    info = None
    if isinstance(data.get("data"), dict) and isinstance(data["data"].get("Info"), dict):
        info = data["data"]["Info"]
    elif isinstance(data.get("Info"), dict):
        info = data["Info"]

    if not info:
        return None, None, None

    return info.get("folderId"), info.get("fileId"), info


def upload_file(
    driver,
    *,
    user_id: str,
    preset_id: str,
    local_file_path: str,
    folder_name: str,
    folder_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Uploads a local file into Tachyon Playground using the authenticated browser session.

    Returns the full fetch result:
    { ok, status, statusText, data, raw }
    """
    p = Path(local_file_path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")

    size = p.stat().st_size
    if size < MIN_FILE_BYTES:
        raise RuntimeError(f"File empty or too small ({size} bytes): {p}")
    if size > MAX_PLAYGROUND_FILE_BYTES:
        raise RuntimeError(
            f"File is {size/1024/1024:.2f} MB which exceeds configured limit "
            f"({MAX_PLAYGROUND_FILE_BYTES/1024/1024:.2f} MB)."
        )

    safe_name = sanitize_filename(p.name)
    mime_type = canonical_mime_type(str(p))
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")

    headers = {"accept": "application/json, text/plain, */*"}

    script = r"""
    const url = arguments[0];
    const headers = arguments[1] || {};
    const payload = arguments[2];
    const done = arguments[3];

    function b64ToBytes(b64) {
      const bin = atob(b64);
      const len = bin.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) bytes[i] = bin.charCodeAt(i);
      return bytes;
    }

    try {
      const bytes = b64ToBytes(payload.b64);
      const blob = new Blob([bytes], { type: payload.mimeType || "application/octet-stream" });
      const file = new File([blob], payload.fileName, { type: payload.mimeType || "application/octet-stream" });

      const fd = new FormData();
      fd.append("userId", payload.userId);
      fd.append("presetId", payload.presetId);
      fd.append("folderName", payload.folderName);
      fd.append("fileName", payload.fileName);
      fd.append("contentType", file, payload.fileName);
      fd.append("mimeType", payload.mimeType);

      if (payload.folderId) {
        fd.append("folderId", payload.folderId);
      }

      fetch(url, {
        method: "POST",
        headers: headers,
        body: fd,
        credentials: "include",
        mode: "cors",
      })
        .then(async resp => {
          const text = await resp.text();
          let data = null;
          try { data = JSON.parse(text); } catch(e) {}
          done({ ok: resp.ok, status: resp.status, statusText: resp.statusText, data: data, raw: text });
        })
        .catch(err => done({ ok: false, status: 0, error: String(err) }));
    } catch (e) {
      done({ ok: false, status: 0, error: String(e) });
    }
    """

    payload = {
        "userId": user_id,
        "presetId": preset_id,
        "folderName": folder_name,
        "fileName": safe_name,
        "mimeType": mime_type,
        "folderId": folder_id,
        "b64": b64,
    }

    res = driver.execute_async_script(script, _upload_endpoint(), headers, payload)
    if not res.get("ok"):
        raise RuntimeError(f"Upload failed: {res}")
    return res

import os
import base64
from typing import List, Dict, Any

from django.conf import settings


DOWNLOAD_LINK_SELECTOR = 'a[download][href^="blob:"]'


def _ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)


def _sanitize_filename(name: str) -> str:
    name = (name or "").strip().replace("\u00A0", "")
    bad = '<>:"/\\|?*\x00'
    for ch in bad:
        name = name.replace(ch, "_")
    return name or "download.bin"


def find_blob_links_in_latest_turn(driver) -> List[Dict[str, str]]:
    """
    Look for blob download links in the newest chat turn.
    """
    script = r"""
    function norm(s){
      if(!s) return "";
      return s.replace(/\u00A0/g," ").replace(/\s+/g," ").trim();
    }

    const turns = Array.from(document.querySelectorAll("div[data-testid='m365-chat-llm-web-ui-chat-message']"));
    if (!turns.length) return [];
    const t = turns[turns.length - 1];

    const links = Array.from(t.querySelectorAll(arguments[0])).map(a => {
      const filename = a.getAttribute("download") || a.getAttribute("aria-label") || a.textContent || "download.bin";
      return { filename: norm(filename), href: a.href };
    });
    return links;
    """
    return driver.execute_script(script, DOWNLOAD_LINK_SELECTOR) or []


def download_blob_to_file(driver, blob_url: str, out_path: str):
    script = r"""
    const url = arguments[0];
    const callback = arguments[arguments.length - 1];

    fetch(url)
      .then(r => r.blob())
      .then(blob => {
        const reader = new FileReader();
        reader.onloadend = () => callback({ ok: true, dataUrl: reader.result, mime: blob.type || "" });
        reader.onerror = () => callback({ ok: false, error: "FileReader error" });
        reader.readAsDataURL(blob);
      })
      .catch(err => callback({ ok: false, error: String(err) }));
    """
    result = driver.execute_async_script(script, blob_url)
    if not result or not result.get("ok"):
        raise RuntimeError(f"Blob download failed: {result.get('error') if result else 'unknown'}")

    data_url = result.get("dataUrl") or ""
    if "," not in data_url:
        raise RuntimeError("Unexpected dataUrl format")
    _, b64 = data_url.split(",", 1)
    raw = base64.b64decode(b64)

    _ensure_dir(os.path.dirname(out_path) or ".")
    with open(out_path, "wb") as f:
        f.write(raw)


def save_latest_turn_downloads(driver, user_key: str) -> List[Dict[str, Any]]:
    """
    Save any blob downloads from latest turn into COPILOT_DOWNLOAD_DIR/<user_key>/...
    Returns metadata list: [{filename, saved_path}]
    """
    links = find_blob_links_in_latest_turn(driver)
    if not links:
        return []

    base_dir = getattr(settings, "COPILOT_DOWNLOAD_DIR", "copilot_downloads")
    out_dir = os.path.join(base_dir, user_key)
    _ensure_dir(out_dir)

    saved = []
    for idx, d in enumerate(links, start=1):
        fname = _sanitize_filename(d.get("filename"))
        href = d.get("href") or ""
        out_name = f"{idx:02d}_{fname}"
        out_path = os.path.join(out_dir, out_name)
        download_blob_to_file(driver, href, out_path)
        saved.append({"filename": fname, "saved_path": out_path})
    return saved

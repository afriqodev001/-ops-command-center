"""
Attachment text extraction for AI briefings.

Fetches attachment binaries from ServiceNow's attachment API and
extracts readable text from supported formats. The extracted text
is included inline in the briefing prompt so the AI can review
runbooks, test results, and other documentation.

Supported formats:
 - .txt, .csv, .log, .json, .xml, .yaml, .yml, .md — read as UTF-8
 - .pdf — extracted via pdfplumber (optional dependency)
 - Everything else — skipped (metadata-only in the prompt)

The fetch uses the same browser-session Selenium mechanism as the
rest of the app (fetch_json_in_browser with arraybuffer response).
"""

from __future__ import annotations
from typing import Dict, List, Optional
import base64
import io
import os
import re

TEXT_EXTENSIONS = {
    '.txt', '.csv', '.log', '.json', '.xml', '.yaml', '.yml',
    '.md', '.conf', '.cfg', '.ini', '.sh', '.ps1', '.bat',
    '.sql', '.html', '.htm',
}
PDF_EXTENSIONS = {'.pdf'}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB cap per file


def _extension(filename: str) -> str:
    idx = filename.rfind('.')
    return filename[idx:].lower() if idx >= 0 else ''


def _is_text_file(filename: str) -> bool:
    return _extension(filename) in TEXT_EXTENSIONS


def _is_pdf_file(filename: str) -> bool:
    return _extension(filename) in PDF_EXTENSIONS


def _is_extractable(filename: str) -> bool:
    return _is_text_file(filename) or _is_pdf_file(filename)


def _extract_pdf_text(binary: bytes) -> str:
    """Extract text from PDF bytes using pdfplumber. Returns '' if not installed."""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(binary)) as pdf:
            pages = []
            for page in pdf.pages[:20]:  # Cap at 20 pages
                text = page.extract_text()
                if text:
                    pages.append(text)
            return '\n\n'.join(pages)
    except ImportError:
        return '[PDF text extraction unavailable — pip install pdfplumber]'
    except Exception as e:
        return f'[PDF extraction failed: {e}]'


def _extract_text(filename: str, binary: bytes) -> str:
    """Extract readable text from an attachment binary."""
    if _is_text_file(filename):
        try:
            return binary.decode('utf-8', errors='replace')
        except Exception:
            return ''
    if _is_pdf_file(filename):
        return _extract_pdf_text(binary)
    return ''


def fetch_attachment_binary(driver, download_link: str) -> Optional[bytes]:
    """Fetch attachment binary content via the authenticated browser session.

    Uses JavaScript fetch() inside the browser to download the file as an
    ArrayBuffer, then base64-encodes it for transfer back to Python.
    """
    if not download_link:
        return None

    js = """
    return await (async () => {
        try {
            const resp = await fetch(arguments[0], {
                credentials: 'same-origin',
                headers: { 'Accept': '*/*' }
            });
            if (!resp.ok) return { ok: false, status: resp.status };
            const buf = await resp.arrayBuffer();
            const bytes = new Uint8Array(buf);
            let binary = '';
            for (let i = 0; i < bytes.length; i++) {
                binary += String.fromCharCode(bytes[i]);
            }
            return { ok: true, b64: btoa(binary), size: bytes.length };
        } catch (e) {
            return { ok: false, error: e.message };
        }
    })();
    """
    try:
        result = driver.execute_async_script(f"""
            const callback = arguments[arguments.length - 1];
            (async () => {{
                try {{
                    const resp = await fetch(arguments[0], {{
                        credentials: 'same-origin',
                        headers: {{ 'Accept': '*/*' }}
                    }});
                    if (!resp.ok) {{ callback({{ ok: false, status: resp.status }}); return; }}
                    const buf = await resp.arrayBuffer();
                    const bytes = new Uint8Array(buf);
                    let binary = '';
                    for (let i = 0; i < bytes.length; i++) {{
                        binary += String.fromCharCode(bytes[i]);
                    }}
                    callback({{ ok: true, b64: btoa(binary), size: bytes.length }});
                }} catch (e) {{
                    callback({{ ok: false, error: e.message }});
                }}
            }})();
        """, download_link)

        if not result or not result.get('ok'):
            return None
        b64 = result.get('b64', '')
        if not b64:
            return None
        return base64.b64decode(b64)
    except Exception:
        return None


_UNSAFE_FILENAME_RX = re.compile(r'[^A-Za-z0-9._\-]+')


def _safe_filename(name: str) -> str:
    """Sanitise a filename for cross-platform local storage."""
    name = (name or 'attachment').strip().replace(' ', '_')
    safe = _UNSAFE_FILENAME_RX.sub('_', name)
    return safe[:120] or 'attachment'


def download_attachments_to_disk(
    change,
    driver,
    dest_dir: str,
    max_files: int = 30,
) -> List[str]:
    """Download every attachment on the change and its CTASKs to dest_dir.

    Args:
        change: shaped change dict with 'attachments' and 'ctasks' (with their
            own 'attachments') — same shape produced by _shape_change_from_context.
        driver: Selenium WebDriver authenticated to ServiceNow.
        dest_dir: existing directory to write files into. Caller manages cleanup.
        max_files: hard cap so a runaway change with hundreds of attachments
            doesn't blow up the AI provider's upload limit or our network budget.

    Returns:
        List of absolute file paths written. Skips attachments missing a
        download_link, attachments that fail to fetch, and duplicates by sys_id.
    """
    if not change or not driver or not dest_dir:
        return []

    saved_paths: List[str] = []
    seen_sys_ids = set()
    used_names = set()

    def _save(att):
        if len(saved_paths) >= max_files:
            return
        sys_id = att.get('sys_id')
        if sys_id and sys_id in seen_sys_ids:
            return
        link = att.get('download_link')
        name = att.get('name') or att.get('file_name')
        if not link or not name:
            return

        binary = fetch_attachment_binary(driver, link)
        if not binary:
            return
        if len(binary) > MAX_FILE_SIZE:
            return

        base = _safe_filename(name)
        # Disambiguate name collisions across change + ctasks.
        candidate = base
        n = 1
        while candidate in used_names:
            stem, _, ext = base.rpartition('.')
            if stem and ext:
                candidate = f"{stem}_{n}.{ext}"
            else:
                candidate = f"{base}_{n}"
            n += 1
        used_names.add(candidate)
        if sys_id:
            seen_sys_ids.add(sys_id)

        path = os.path.join(dest_dir, candidate)
        try:
            with open(path, 'wb') as f:
                f.write(binary)
            saved_paths.append(path)
        except OSError:
            return

    for att in (change.get('attachments') or []):
        _save(att)
    for ct in (change.get('ctasks') or []):
        for att in (ct.get('attachments') or []):
            _save(att)

    return saved_paths


def extract_attachment_texts(
    attachments: list,
    driver=None,
) -> Dict[str, str]:
    """Extract text from all extractable attachments.

    Args:
        attachments: list of attachment dicts (with 'name', 'download_link', etc.)
        driver: Selenium WebDriver for fetching binaries (None = skip fetch, metadata only)

    Returns:
        Dict mapping filename → extracted text (only for successfully extracted files)
    """
    texts = {}
    if not driver:
        return texts

    for att in (attachments or []):
        name = att.get('name', '')
        link = att.get('download_link', '')
        if not name or not link or not _is_extractable(name):
            continue

        binary = fetch_attachment_binary(driver, link)
        if not binary:
            continue
        if len(binary) > MAX_FILE_SIZE:
            texts[name] = f'[File too large: {len(binary)} bytes, cap is {MAX_FILE_SIZE}]'
            continue

        text = _extract_text(name, binary)
        if text:
            texts[name] = text

    return texts

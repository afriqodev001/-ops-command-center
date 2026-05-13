"""
Upload a file as a ServiceNow attachment on an existing record.

POST /api/now/attachment/file?table_name=&table_sys_id=&file_name=
Body: raw bytes of the file
Content-Type: the file's MIME type
"""
from __future__ import annotations

from urllib.parse import quote

from django.conf import settings

from servicenow.services.servicenow_fetch import fetch_binary_in_browser


def upload_attachment_to_record(
    driver,
    *,
    table_name: str,
    table_sys_id: str,
    file_name: str,
    file_bytes: bytes,
    content_type: str,
):
    """Attach `file_bytes` to ServiceNow record (table_name, table_sys_id)."""
    base = getattr(settings, "SERVICENOW_BASE", "").rstrip("/")
    url = (
        f"{base}/api/now/attachment/file"
        f"?table_name={quote(table_name)}"
        f"&table_sys_id={quote(table_sys_id)}"
        f"&file_name={quote(file_name)}"
    )
    return fetch_binary_in_browser(
        driver,
        method="POST",
        url=url,
        raw_bytes=file_bytes,
        content_type=content_type,
    )

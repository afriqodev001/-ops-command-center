"""
Outlook desktop draft helper (Windows-only, pywin32).

Used by both the existing ServiceNow preset CSV email and the new oncall
notification draft. Creates a draft and opens it in Outlook for the user
to review and send manually — never auto-sends.
"""
from __future__ import annotations

import os
import tempfile
import threading
import time
from typing import Dict, Optional


def open_draft(
    *,
    recipients: str = '',
    subject: str = '',
    body: str = '',
    attachment_path: Optional[str] = None,
    cleanup_attachment: bool = False,
) -> Dict[str, object]:
    """
    Open an Outlook desktop draft (does NOT send).

    Args:
        recipients: semicolon-separated string of email addresses.
        subject: email subject line.
        body: plain-text body.
        attachment_path: optional path to an existing file to attach.
        cleanup_attachment: if True, schedule a delayed delete of the
            attachment file (used when caller wrote a temp file just for this draft).

    Returns:
        {'ok': True} on success, {'error': '<message>'} on failure.
    """
    try:
        import win32com.client  # type: ignore
    except ImportError:
        return {'error': 'Outlook not available (pywin32 not installed).'}

    try:
        outlook = win32com.client.Dispatch('Outlook.Application')
        mail = outlook.CreateItem(0)  # olMailItem = 0
        if recipients:
            mail.To = recipients
        mail.Subject = subject or ''
        mail.Body = body or ''
        if attachment_path:
            mail.Attachments.Add(attachment_path)
        mail.Display()  # opens the draft window; does NOT send
    except Exception as e:
        return {'error': f'Outlook error: {e}'}
    finally:
        if attachment_path and cleanup_attachment:
            _schedule_cleanup(attachment_path)

    return {'ok': True}


def write_temp_attachment(content: str, filename: str) -> str:
    """Write content to a temp file and return its absolute path."""
    tmp_dir = tempfile.mkdtemp()
    path = os.path.join(tmp_dir, filename)
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        f.write(content)
    return path


def _schedule_cleanup(path: str, delay_seconds: int = 10) -> None:
    def _cleanup():
        time.sleep(delay_seconds)
        try:
            os.remove(path)
            os.rmdir(os.path.dirname(path))
        except Exception:
            pass

    try:
        threading.Thread(target=_cleanup, daemon=True).start()
    except Exception:
        pass

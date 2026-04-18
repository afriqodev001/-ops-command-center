from __future__ import annotations

import csv
import io
import json
from typing import Iterable

from copilot_chat.models import CopilotRun


def runs_to_json_bytes(runs: Iterable[CopilotRun]) -> bytes:
    payload = []
    for r in runs:
        payload.append({
            "timestamp_utc": r.timestamp_utc,
            "status": r.status,
            "guid": r.guid,
            "run_id": r.run_id,
            "prompt": r.prompt,
            "answer": r.answer,
            "error": r.error,
        })
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


def runs_to_csv_bytes(runs: Iterable[CopilotRun]) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["timestamp_utc", "status", "guid", "prompt", "answer", "error"]
    )
    writer.writeheader()
    for r in runs:
        writer.writerow({
            "timestamp_utc": r.timestamp_utc,
            "status": r.status,
            "guid": r.guid,
            "prompt": r.prompt,
            "answer": r.answer,
            "error": r.error,
        })
    return output.getvalue().encode("utf-8")

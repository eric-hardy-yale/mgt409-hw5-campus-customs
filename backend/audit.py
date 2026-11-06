"""Append-only audit trail: output/audit_trail.json.

The file is one JSON list. Every agent-loop step adds an entry to the end; earlier
entries (and earlier runs) are never removed or rewritten. A file lock keeps parallel
agents from clobbering each other, and the write goes through a temp file so a crash
can't leave half a file behind.
"""

from __future__ import annotations

import fcntl
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import AUDIT_TRAIL
from .models import AuditEvent

_thread_lock = threading.Lock()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def append_event(event: AuditEvent, path: Path = AUDIT_TRAIL) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    with _thread_lock, open(lock_path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            entries: list[Any] = []
            if path.exists() and path.stat().st_size > 0:
                entries = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(entries, list):
                    # Never wipe someone else's file: stop instead.
                    raise RuntimeError(f"{path} is not a JSON list; not touching it")
            entries.append(event.model_dump(mode="json"))
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(tmp, path)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)

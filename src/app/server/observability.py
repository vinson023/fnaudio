from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid

from file_permissions import secure_directory, secure_file

SENSITIVE_MARKERS = ("token", "password", "secret", "authorization", "cookie")


def request_id(value=""):
    value = str(value or "").strip()
    if re.fullmatch(r"[A-Za-z0-9._:-]{8,96}", value):
        return value
    return uuid.uuid4().hex


def redact(value):
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if any(marker in str(key).lower() for marker in SENSITIVE_MARKERS) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


class Observability:
    def __init__(self):
        self._lock = threading.RLock()
        self._counters = {}

    def count(self, name, amount=1):
        with self._lock:
            self._counters[str(name)] = int(self._counters.get(str(name), 0)) + int(amount)

    def snapshot(self):
        with self._lock:
            return dict(self._counters)

    def write(self, path, event, max_bytes=5 * 1024 * 1024, **fields):
        if not path:
            return
        payload = redact({"ts": round(time.time(), 3), "event": event, **fields})
        try:
            secure_directory(os.path.dirname(os.path.abspath(path)))
            with self._lock:
                if os.path.isfile(path) and os.path.getsize(path) >= max_bytes:
                    os.replace(path, path + ".1")
                    secure_file(path + ".1")
                with open(path, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
                secure_file(path)
        except OSError:
            self.count("log_write_errors")


OBSERVABILITY = Observability()

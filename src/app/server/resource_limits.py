from __future__ import annotations

import os
import shutil
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict


class ResourceLimitError(RuntimeError):
    pass


class ConcurrencyGate:
    def __init__(self, name: str):
        self.name = name
        self._condition = threading.Condition()
        self._active = 0
        self._peak = 0

    @contextmanager
    def slot(self, limit: int, timeout: float = 5.0):
        limit = max(1, int(limit))
        deadline = time.monotonic() + max(0.0, float(timeout))
        with self._condition:
            while self._active >= limit:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ResourceLimitError("%s concurrency limit reached" % self.name)
                self._condition.wait(remaining)
            self._active += 1
            self._peak = max(self._peak, self._active)
        try:
            yield
        finally:
            with self._condition:
                self._active = max(0, self._active - 1)
                self._condition.notify()

    def snapshot(self) -> Dict[str, int]:
        with self._condition:
            return {"active": self._active, "peak": self._peak}


def disk_has_reserve(path: str, minimum_free_bytes: int, incoming_bytes: int = 0) -> bool:
    target = os.path.abspath(path or ".")
    while not os.path.exists(target):
        parent = os.path.dirname(target)
        if parent == target:
            break
        target = parent
    try:
        free = int(shutil.disk_usage(target).free)
    except OSError:
        return False
    return free - max(0, int(incoming_bytes)) >= max(0, int(minimum_free_bytes))


def bounded_int(config: Dict[str, Any], key: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(config.get(key, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


FFMPEG_GATE = ConcurrencyGate("ffmpeg")


@contextmanager
def ffmpeg_slot(config: Dict[str, Any], timeout: float = 5.0):
    limit = bounded_int(config, "ffmpeg_max_concurrency", 2, 1, 8)
    with FFMPEG_GATE.slot(limit, timeout):
        yield


__all__ = [
    "FFMPEG_GATE",
    "ResourceLimitError",
    "bounded_int",
    "disk_has_reserve",
    "ffmpeg_slot",
]

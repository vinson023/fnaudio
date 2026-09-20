from __future__ import annotations

import os
import shutil
import threading
import time
import math
from contextlib import contextmanager
from typing import Any, Dict


class ResourceLimitError(RuntimeError):
    pass


MAX_WAIT_SECONDS = 10**9
MAX_COUNTER_VALUE = 10**12
MAX_RESOURCE_NAME_CHARS = 256
MAX_RESOURCE_PATH_CHARS = 4096


def _increment_counter(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 1
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return 1
    return min(MAX_COUNTER_VALUE, max(0, number) + 1)


def _safe_int(value, default, minimum=0, maximum=10**6):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    try:
        number = float(value)
    except (OverflowError, ValueError, TypeError):
        return default
    if not math.isfinite(number):
        return default
    return max(minimum, min(maximum, int(number)))


def _safe_timeout(value, default=5.0):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    try:
        number = float(value)
    except (OverflowError, ValueError, TypeError):
        return default
    return max(0.0, min(3600.0, number)) if math.isfinite(number) else default


def _safe_counter(value, default=0):
    """Project internal gate counters before exposing diagnostics."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not math.isfinite(number):
        return default
    return max(0, min(MAX_COUNTER_VALUE, int(number)))


def _safe_wait_seconds(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return round(max(0.0, min(MAX_WAIT_SECONDS, number)), 3) if math.isfinite(number) else 0.0


class ConcurrencyGate:
    def __init__(self, name: str, max_waiters: int = 64):
        if isinstance(name, str) and name:
            self.name = name[:MAX_RESOURCE_NAME_CHARS]
        else:
            self.name = "resource"
        self.max_waiters = _safe_int(max_waiters, 64, 0, 256)
        self._condition = threading.Condition()
        self._active = 0
        self._peak = 0
        self._acquired = 0
        self._rejected = 0
        self._waiter_rejected = 0
        self._timed_out = 0
        self._waited = 0
        self._waiting = 0
        self._peak_waiting = 0
        self._wait_seconds = 0.0

    def _add_wait_seconds(self, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return
        try:
            number = float(value)
        except (OverflowError, ValueError, TypeError):
            return
        if math.isfinite(number):
            current = _safe_wait_seconds(self._wait_seconds)
            self._wait_seconds = min(MAX_WAIT_SECONDS, current + max(0.0, number))

    @contextmanager
    def slot(self, limit: int, timeout: float = 5.0, max_waiters: int | None = None):
        limit = _safe_int(limit, 1, 1, 256)
        waiter_limit = self.max_waiters if max_waiters is None else _safe_int(max_waiters, self.max_waiters, 0, 256)
        started = time.monotonic()
        deadline = started + _safe_timeout(timeout)
        with self._condition:
            did_wait = False
            while self._active >= limit:
                # A waiter already admitted to the queue must be allowed to
                # re-check the active slot after a spurious wake-up.  Count
                # the queue bound only when admitting a new waiter; otherwise
                # the waiter can reject itself while still occupying its slot.
                if not did_wait and self._waiting >= waiter_limit:
                    self._rejected = _increment_counter(self._rejected)
                    self._waiter_rejected = _increment_counter(self._waiter_rejected)
                    raise ResourceLimitError("%s waiting queue is full" % self.name)
                if not did_wait:
                    did_wait = True
                    self._waited = _increment_counter(self._waited)
                    self._waiting += 1
                    self._peak_waiting = max(self._peak_waiting, self._waiting)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._rejected = _increment_counter(self._rejected)
                    self._timed_out = _increment_counter(self._timed_out)
                    self._add_wait_seconds(time.monotonic() - started)
                    self._waiting = max(0, self._waiting - 1)
                    raise ResourceLimitError("%s concurrency limit reached" % self.name)
                self._condition.wait(remaining)
            if did_wait:
                self._waiting = max(0, self._waiting - 1)
            self._active += 1
            self._peak = max(self._peak, self._active)
            self._acquired = _increment_counter(self._acquired)
            self._add_wait_seconds(time.monotonic() - started)
        try:
            yield
        finally:
            with self._condition:
                self._active = max(0, self._active - 1)
                self._condition.notify()

    def try_acquire(self, limit: int) -> bool:
        """Acquire immediately without creating a waiter.

        This is used by the HTTP accept path, where creating another thread
        just to wait for a worker slot would defeat the resource bound.
        """
        limit = _safe_int(limit, 1, 1, 256)
        with self._condition:
            if self._active >= limit:
                self._rejected = _increment_counter(self._rejected)
                return False
            self._active += 1
            self._peak = max(self._peak, self._active)
            self._acquired = _increment_counter(self._acquired)
            return True

    def release(self):
        """Release an immediate acquisition and wake observability waiters."""
        with self._condition:
            self._active = max(0, _safe_counter(self._active) - 1)
            self._condition.notify()

    def snapshot(self) -> Dict[str, Any]:
        with self._condition:
            return {
                "active": _safe_counter(self._active),
                "peak": _safe_counter(self._peak),
                "acquired": _safe_counter(self._acquired),
                "waited": _safe_counter(self._waited),
                "waiting": _safe_counter(self._waiting),
                "peak_waiting": _safe_counter(self._peak_waiting),
                "rejected": _safe_counter(self._rejected),
                "waiter_rejected": _safe_counter(self._waiter_rejected),
                "timed_out": _safe_counter(self._timed_out),
                "waiter_limit": _safe_counter(self.max_waiters),
                "wait_seconds": _safe_wait_seconds(self._wait_seconds),
            }


def disk_has_reserve(path: str, minimum_free_bytes: int, incoming_bytes: int = 0) -> bool:
    if (
        not isinstance(path, str)
        or len(path) > MAX_RESOURCE_PATH_CHARS
        or "\x00" in path
    ):
        return False
    minimum = _safe_int(minimum_free_bytes, -1, 0, 10**18)
    incoming = _safe_int(incoming_bytes, -1, 0, 10**18)
    if minimum < 0 or incoming < 0:
        return False
    try:
        target = os.path.abspath(path or ".")
        while not os.path.exists(target):
            parent = os.path.dirname(target)
            if parent == target:
                break
            target = parent
        free = int(shutil.disk_usage(target).free)
    except (OSError, ValueError, TypeError):
        return False
    return free - incoming >= minimum


def bounded_int(config: Dict[str, Any], key: str, default: int, minimum: int, maximum: int) -> int:
    if not isinstance(config, dict) or not isinstance(key, str):
        if isinstance(default, bool) or not isinstance(default, (int, float)):
            return minimum
        return max(minimum, min(maximum, int(default)))
    try:
        value = config.get(key, default)
    except Exception:
        value = default
    safe_default = default if isinstance(default, (int, float)) and not isinstance(default, bool) else minimum
    return _safe_int(value, safe_default, minimum, maximum)


FFMPEG_GATE = ConcurrencyGate("ffmpeg", max_waiters=32)


@contextmanager
def ffmpeg_slot(config: Dict[str, Any], timeout: float = 5.0):
    limit = bounded_int(config, "ffmpeg_max_concurrency", 2, 1, 8)
    max_waiters = bounded_int(config, "ffmpeg_max_waiters", 32, 0, 256)
    with FFMPEG_GATE.slot(limit, timeout, max_waiters=max_waiters):
        yield


__all__ = [
    "FFMPEG_GATE",
    "ResourceLimitError",
    "bounded_int",
    "disk_has_reserve",
    "ffmpeg_slot",
]

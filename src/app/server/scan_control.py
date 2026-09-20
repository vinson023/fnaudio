"""Small, testable cancellation and progress-deadline primitives for library scans."""

from __future__ import annotations

import time
import math


class ScanCancelled(RuntimeError):
    """Raised when a running library scan is cancelled by the caller."""


class ScanTimedOut(ScanCancelled):
    """Raised when a library scan has made no observable progress in time."""


def _timeout_seconds(value, default=1.0):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return default
    if isinstance(value, str) and len(value) > 64:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(1.0, number) if math.isfinite(number) else default


class ScanDeadline:
    """Abort only after the scanner makes no observable progress."""

    def __init__(self, timeout, state=None):
        self.timeout = _timeout_seconds(timeout)
        self.expires_at = time.monotonic() + self.timeout
        self._state = state

    def check_and_touch(self):
        now = time.monotonic()
        if now >= self.expires_at:
            raise ScanTimedOut("library scan made no progress for %s seconds" % int(self.timeout))
        self.expires_at = now + self.timeout
        if self._state is not None:
            self._state["deadline"] = int(time.time() + self.timeout)


def check_scan_deadline(deadline=None, cancel_event=None):
    """Check cancellation first, then refresh a progress deadline when present."""
    if cancel_event is not None and cancel_event.is_set():
        raise ScanCancelled("library scan cancelled")
    if isinstance(deadline, ScanDeadline):
        deadline.check_and_touch()
        return
    if deadline is not None:
        if isinstance(deadline, bool) or not isinstance(deadline, (int, float, str)):
            return
        if isinstance(deadline, str) and len(deadline) > 64:
            return
        try:
            value = float(deadline)
        except (TypeError, ValueError, OverflowError):
            return
        if math.isfinite(value) and time.monotonic() >= value:
            raise ScanTimedOut("library scan timed out")

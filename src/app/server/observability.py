from __future__ import annotations

import json
import math
import os
import re
import threading
import time
import uuid

import file_permissions
from file_permissions import secure_file
from http_request_policy import HTTP_LATENCY_ROUTES, http_latency_route, should_write_http_request
from observability_snapshot import build_observability_snapshot

SENSITIVE_MARKERS = ("token", "password", "secret", "authorization", "cookie")
HTTP_SLOW_REQUEST_SECONDS = 1.0
MAX_LOG_RECORD_BYTES = 64 * 1024
MAX_LOG_FILE_BYTES = 100 * 1024 * 1024
DEFAULT_LOG_FILE_BYTES = 5 * 1024 * 1024
MAX_REDACT_DEPTH = 16
MAX_REDACT_ITEMS = 256
MAX_REDACT_STRING = 8192
MAX_REDACT_KEY = 256
MAX_COUNTER_INCREMENT = 1000000
MAX_COUNTER_VALUE = 10**12
MAX_LATENCY_TOTAL_MS = 10**15
OBSERVABILITY_COUNTERS = frozenset({
    "http_requests_total",
    "http_status_1xx",
    "http_status_2xx",
    "http_status_3xx",
    "http_status_4xx",
    "http_status_5xx",
    "log_write_errors",
})


def finite_nonnegative(value, default=0.0):
    """Accept only ordinary finite numeric metrics."""
    if isinstance(default, bool) or not isinstance(default, (int, float)):
        default = 0.0
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return float(default)
    try:
        normalized = float(value)
    except (OverflowError, ValueError, TypeError):
        return float(default)
    return max(0.0, normalized) if math.isfinite(normalized) else float(default)


def positive_threshold(value, default=HTTP_SLOW_REQUEST_SECONDS):
    """Normalize a slow-request threshold; non-positive values use default."""
    normalized = finite_nonnegative(value, default)
    fallback = finite_nonnegative(default, HTTP_SLOW_REQUEST_SECONDS)
    return normalized if normalized > 0 else (fallback if fallback > 0 else HTTP_SLOW_REQUEST_SECONDS)


def bounded_counter_increment(value, default=1):
    """Normalize internal counter deltas without coercing arbitrary objects."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return int(default)
    try:
        number = float(value)
    except (OverflowError, ValueError, TypeError):
        return int(default)
    if not math.isfinite(number):
        return int(default)
    return max(0, min(MAX_COUNTER_INCREMENT, int(number)))


def bounded_counter_value(value, default=0):
    """Project an internal counter total without coercing arbitrary objects."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return int(default)
    try:
        number = float(value)
    except (OverflowError, ValueError, TypeError):
        return int(default)
    if not math.isfinite(number):
        return int(default)
    return max(0, min(MAX_COUNTER_VALUE, int(number)))


def bounded_log_file_bytes(value, default=DEFAULT_LOG_FILE_BYTES):
    """Keep log rotation thresholds finite and within a practical bound."""
    if isinstance(default, bool) or not isinstance(default, (int, float)):
        default = DEFAULT_LOG_FILE_BYTES
    try:
        safe_default = int(default) if math.isfinite(float(default)) else DEFAULT_LOG_FILE_BYTES
    except (OverflowError, ValueError, TypeError):
        safe_default = DEFAULT_LOG_FILE_BYTES
    safe_default = max(1, min(MAX_LOG_FILE_BYTES, safe_default))
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return safe_default
    try:
        number = float(value)
    except (OverflowError, ValueError, TypeError):
        return safe_default
    if not math.isfinite(number):
        return safe_default
    return max(1, min(MAX_LOG_FILE_BYTES, int(number)))


def request_id(value=""):
    # Request headers are text; do not stringify arbitrary objects supplied by
    # an embedding caller because their __str__ may be expensive or unsafe.
    value = value.strip() if isinstance(value, str) else ""
    if re.fullmatch(r"[A-Za-z0-9._:-]{8,96}", value):
        return value
    return uuid.uuid4().hex


def redact(value, _depth=0):
    if _depth >= MAX_REDACT_DEPTH:
        return "[TRUNCATED_DEPTH]"
    if isinstance(value, dict):
        result = {}
        try:
            items = iter(value.items())
        except Exception:
            return "[UNAVAILABLE_MAPPING]"
        for index in range(MAX_REDACT_ITEMS):
            try:
                key, item = next(items)
            except StopIteration:
                break
            except Exception:
                return result or "[UNAVAILABLE_MAPPING]"
            if isinstance(key, str):
                # Do not lower-case an unbounded external key.  Treat an
                # overlong key conservatively as sensitive and only retain a
                # bounded prefix in the diagnostic output.
                sensitive_key = "[OVERSIZED_KEY]" if len(key) > MAX_REDACT_KEY else key.lower()
                safe_key = key[:MAX_REDACT_KEY]
            else:
                sensitive_key = ""
                safe_key = "[NON_TEXT_KEY:%d]" % index
            if isinstance(key, str) and len(key) > MAX_REDACT_KEY:
                safe_key += "...[TRUNCATED_KEY]"
            result[safe_key] = (
                "[REDACTED]"
                if (isinstance(key, str) and len(key) > MAX_REDACT_KEY)
                or any(marker in sensitive_key for marker in SENSITIVE_MARKERS)
                else redact(item, _depth + 1)
            )
        try:
            value_length = len(value)
        except Exception:
            value_length = None
        if value_length is not None and value_length > MAX_REDACT_ITEMS:
            result["_truncated_items"] = value_length - MAX_REDACT_ITEMS
        return result
    if isinstance(value, (list, tuple)):
        result = []
        try:
            iterator = iter(value)
        except Exception:
            return "[UNAVAILABLE_SEQUENCE]"
        for _ in range(MAX_REDACT_ITEMS):
            try:
                item = next(iterator)
            except StopIteration:
                break
            except Exception:
                return result or "[UNAVAILABLE_SEQUENCE]"
            result.append(redact(item, _depth + 1))
        try:
            value_length = len(value)
        except Exception:
            value_length = None
        if value_length is not None and value_length > MAX_REDACT_ITEMS:
            result.append("[TRUNCATED_ITEMS:%d]" % (value_length - MAX_REDACT_ITEMS))
        return result
    if isinstance(value, str) and len(value) > MAX_REDACT_STRING:
        return value[:MAX_REDACT_STRING] + "...[TRUNCATED_STRING]"
    return value


class Observability:
    def __init__(self):
        self._lock = threading.RLock()
        # write() does file I/O (stat, rotate, append, chmod).  It used to run
        # inside self._lock, which every request thread also needs for count()
        # and record_http_latency_route(), and which the health and diagnostics
        # snapshots read, so one slow log write stalled the whole server.  Log
        # writes keep their own serialization instead.
        self._log_lock = threading.RLock()
        self._counters = {}
        self._http_latency = {
            route: {"count": 0, "total_ms": 0.0, "max_ms": 0.0, "slow": 0}
            for route in HTTP_LATENCY_ROUTES
        }

    def count(self, name, amount=1):
        if not isinstance(name, str):
            return False
        # Counter names are an internal fixed vocabulary.  Refuse arbitrary
        # caller input so a malformed route/event cannot grow diagnostics
        # memory without bound.
        if name not in OBSERVABILITY_COUNTERS:
            return False
        with self._lock:
            current = bounded_counter_value(self._counters.get(name, 0))
            self._counters[name] = min(MAX_COUNTER_VALUE, current + bounded_counter_increment(amount))
        return True

    def record_http_latency(self, path, seconds, slow_seconds=HTTP_SLOW_REQUEST_SECONDS):
        """Record aggregate latency in a bounded, privacy-safe route bucket."""
        return self.record_http_latency_route(http_latency_route(path), seconds, slow_seconds)

    def record_http_latency_route(self, route, seconds, slow_seconds=HTTP_SLOW_REQUEST_SECONDS):
        """Record latency for an already-projected fixed route bucket."""
        if route not in HTTP_LATENCY_ROUTES:
            route = "static"
        # Bound the per-request contribution before updating any aggregate.
        # This keeps ``max_ms`` consistent with ``total_ms`` when a malformed
        # or extreme duration reaches the metrics boundary.
        elapsed_ms = min(MAX_LATENCY_TOTAL_MS, finite_nonnegative(seconds) * 1000.0)
        slow_ms = min(MAX_LATENCY_TOTAL_MS, positive_threshold(slow_seconds) * 1000.0)
        with self._lock:
            summary = self._http_latency[route]
            count = bounded_counter_value(summary.get("count", 0))
            total_ms = min(MAX_LATENCY_TOTAL_MS, finite_nonnegative(summary.get("total_ms", 0.0)) + elapsed_ms)
            max_ms = max(finite_nonnegative(summary.get("max_ms", 0.0)), elapsed_ms)
            slow = bounded_counter_value(summary.get("slow", 0))
            summary["count"] = min(MAX_COUNTER_VALUE, count + 1)
            summary["total_ms"] = total_ms
            summary["max_ms"] = max_ms
            if elapsed_ms >= slow_ms:
                summary["slow"] = min(MAX_COUNTER_VALUE, slow + 1)
        return route

    def snapshot(self):
        with self._lock:
            return build_observability_snapshot(self._counters, self._http_latency)

    def write(self, path, event, max_bytes=DEFAULT_LOG_FILE_BYTES, **fields):
        if not path:
            return
        try:
            max_bytes = bounded_log_file_bytes(max_bytes)
            payload = redact({"ts": round(time.time(), 3), "event": event, **fields})
            encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
            if len(encoded.encode("utf-8")) > MAX_LOG_RECORD_BYTES:
                encoded = json.dumps({
                    "ts": payload.get("ts") if isinstance(payload, dict) else round(time.time(), 3),
                    "event": event[:160] if isinstance(event, str) else "[NON_TEXT_EVENT]",
                    "truncated": True,
                    "record_limit_bytes": MAX_LOG_RECORD_BYTES,
                }, ensure_ascii=False, separators=(",", ":")) + "\n"
            # One lstat per line instead of a full hardening pass: the mode is what this
            # call is guarding, and it almost never differs between two writes.
            file_permissions.secure_directory_on_drift(os.path.dirname(os.path.abspath(path)))
            with self._log_lock:
                if os.path.isfile(path) and os.path.getsize(path) >= max_bytes:
                    os.replace(path, path + ".1")
                    secure_file(path + ".1")
                with open(path, "a", encoding="utf-8") as handle:
                    handle.write(encoded)
                # The rotated `.1` keeps the full pass: it is created by `os.replace` from a
                # file whose mode we have been maintaining, and it happens once per
                # MAX_LOG_FILE_BYTES rather than once per line.
                file_permissions.secure_file_on_drift(path)
        except Exception:
            # Diagnostics must never become a request failure when a caller
            # accidentally supplies a non-JSON value, malformed path, or a
            # hostile mapping that fails while being redacted.
            self.count("log_write_errors")


OBSERVABILITY = Observability()

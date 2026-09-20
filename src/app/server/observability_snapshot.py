"""Pure, bounded projection of observability counters and latency buckets."""

from __future__ import annotations

import math

from http_request_policy import HTTP_LATENCY_ROUTES


MAX_SNAPSHOT_ITEMS = 256
MAX_COUNTER_KEY_LENGTH = 256
MAX_COUNTER_VALUE = 10**12
MAX_LATENCY_TOTAL_MS = 10**15


def _safe_get(source, key, default=None):
    if not isinstance(source, dict):
        return default
    try:
        return source.get(key, default)
    except Exception:
        return default


def _count(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    try:
        number = int(value)
    except (OverflowError, ValueError, TypeError):
        return 0
    return max(0, min(MAX_COUNTER_VALUE, number))


def _milliseconds(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    try:
        number = float(value)
    except (OverflowError, ValueError, TypeError):
        return 0.0
    return max(0.0, min(MAX_LATENCY_TOTAL_MS, number)) if math.isfinite(number) else 0.0


def build_observability_snapshot(counters, http_latency):
    """Build a serializable snapshot from internal metric containers."""
    result = {}
    if isinstance(counters, dict):
        try:
            iterator = iter(counters.items())
        except Exception:
            iterator = iter(())
        for _ in range(MAX_SNAPSHOT_ITEMS):
            try:
                key, value = next(iterator)
            except StopIteration:
                break
            except Exception:
                break
            if isinstance(key, str) and 0 < len(key) <= MAX_COUNTER_KEY_LENGTH:
                result[key] = _count(value)

    latency_result = {}
    for route in HTTP_LATENCY_ROUTES:
        summary = _safe_get(http_latency, route, {})
        count = _count(_safe_get(summary, "count"))
        total_ms = _milliseconds(_safe_get(summary, "total_ms"))
        maximum = _milliseconds(_safe_get(summary, "max_ms"))
        # ``slow`` is a long-lived saturated counter.  It may legitimately
        # exceed the current bucket count after counter rollover/recovery, so
        # preserve the established saturation contract here.
        slow = _count(_safe_get(summary, "slow"))
        latency_result[route] = {
            "count": count,
            "avg_ms": round(total_ms / count, 2) if count else 0.0,
            "max_ms": round(maximum, 2),
            "slow": slow,
        }
    result["http_latency"] = latency_result
    return result


__all__ = ["build_observability_snapshot"]

"""Pure presentation helpers for the bounded library query cache."""

from __future__ import annotations

import math


MAX_CACHE_COUNTER = 10**12


def counter_value(value, default=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    try:
        number = float(value)
    except (OverflowError, ValueError, TypeError):
        return default
    if not math.isfinite(number):
        return default
    return max(0, min(MAX_CACHE_COUNTER, int(number)))


def hit_rate(hits, misses):
    hit_count = counter_value(hits)
    miss_count = counter_value(misses)
    total = hit_count + miss_count
    if total <= 0:
        return 0.0
    return round(hit_count / total, 4)


def project_snapshot_counters(result):
    """Normalize public cache counters in-place and return the same mapping."""

    if not isinstance(result, dict):
        return {}
    for field in (
        "entries", "limit", "weight", "weight_limit", "hits", "misses",
        "evictions", "expired", "invalidations", "oversized", "uncacheable",
    ):
        if field in result:
            result[field] = counter_value(result[field])
    nested = result.get("snapshot")
    if isinstance(nested, dict):
        for field in ("ttl_ms", "age_ms", "hits", "misses"):
            if field in nested:
                nested[field] = counter_value(nested[field])
    return result

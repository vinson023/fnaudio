"""Bounded, privacy-safe library state shared by health and diagnostics."""

from __future__ import annotations

from summary_values import nonnegative_int, strict_bool
import math


_PREWARM_FIELDS = ("workers", "queued", "inflight", "limit", "page_size", "accepted", "completed", "failed", "dropped", "root_limit", "root_rejected")
_QUERY_CACHE_FIELDS = ("entries", "limit", "capacity", "weight", "weight_limit", "oversized", "uncacheable", "hits", "misses", "evictions", "expired", "invalidations")
_QUERY_CACHE_SNAPSHOT_FIELDS = ("ttl_ms", "age_ms", "hits", "misses")
_COVER_CACHE_FIELDS = ("entries", "limit", "inflight", "inflight_limit")
_CACHE_FAILURE_FIELDS = ("load", "save")
_STORAGE_FIELDS = ("database_bytes", "wal_bytes", "shm_bytes", "total_bytes")
_CONNECTION_POOL_FIELDS = ("idle", "databases", "reuses", "creations", "closures", "max_idle_per_database", "max_idle_total")
_MISSING = object()


def _safe_get(source, key, default=None):
    if not isinstance(source, dict):
        return default
    try:
        return source.get(key, default)
    except Exception:
        return default


def _safe_len(value):
    try:
        return max(0, min(2_147_483_647, int(len(value))))
    except Exception:
        return 0


def _bounded_prewarm(snapshot):
    """Keep support output to the fixed pressure schema from cover_cache."""
    source = snapshot if isinstance(snapshot, dict) else {}
    result = {}
    for name in ("interactive", "library"):
        section = _safe_get(source, name)
        if not isinstance(section, dict):
            continue
        result[name] = {}
        for field in _PREWARM_FIELDS:
            value = _safe_get(section, field, _MISSING)
            if value is _MISSING:
                continue
            result[name][field] = nonnegative_int(value)
    return result


def _bounded_query_cache(snapshot):
    source = snapshot if isinstance(snapshot, dict) else {}
    result = {}
    for field in _QUERY_CACHE_FIELDS:
        value = _safe_get(source, field, _MISSING)
        if value is _MISSING:
            continue
        result[field] = nonnegative_int(value)
    raw_hit_rate = _safe_get(source, "hit_rate", _MISSING)
    if isinstance(raw_hit_rate, (int, float)) and not isinstance(raw_hit_rate, bool):
        try:
            if math.isfinite(raw_hit_rate):
                result["hit_rate"] = max(0.0, min(1.0, float(raw_hit_rate)))
        except (OverflowError, ValueError, TypeError):
            pass
    raw_saturated = _safe_get(source, "saturated", _MISSING)
    if isinstance(raw_saturated, bool):
        result["saturated"] = raw_saturated
    raw_snapshot = _safe_get(source, "snapshot")
    if isinstance(raw_snapshot, dict):
        result["snapshot"] = {
            field: nonnegative_int(_safe_get(raw_snapshot, field))
            for field in _QUERY_CACHE_SNAPSHOT_FIELDS
        }
    return result


def _bounded_search_index(snapshot):
    source = snapshot if isinstance(snapshot, dict) else {}
    raw_mode = _safe_get(source, "mode")
    # Do not stringify arbitrary containers here: an untrusted diagnostics
    # payload could otherwise allocate a very large temporary representation
    # before the length cap is applied.
    mode = raw_mode[:32] if isinstance(raw_mode, str) and raw_mode else "like"
    minimum = nonnegative_int(_safe_get(source, "substring_minimum_chars"))
    return {"mode": mode, "substring_minimum_chars": minimum}

def _bounded_cover_cache(snapshot):
    source = snapshot if isinstance(snapshot, dict) else {}
    return {field: nonnegative_int(_safe_get(source, field)) for field in _COVER_CACHE_FIELDS}


def _bounded_cache_failures(snapshot):
    source = snapshot if isinstance(snapshot, dict) else {}
    return {field: nonnegative_int(_safe_get(source, field)) for field in _CACHE_FAILURE_FIELDS}


def _bounded_storage(snapshot):
    source = snapshot if isinstance(snapshot, dict) else {}
    return {field: nonnegative_int(_safe_get(source, field)) for field in _STORAGE_FIELDS}


def _bounded_connection_pool(snapshot):
    source = snapshot if isinstance(snapshot, dict) else {}
    return {field: nonnegative_int(_safe_get(source, field)) for field in _CONNECTION_POOL_FIELDS}


def library_component(scan_state, *, query_cache=None, search_index=None, thumbnail_prewarm=None, cover_cache=None, cache_failures=None, storage=None, connection_pool=None):
    """Return operational library pressure only, never paths or media rows."""
    state = scan_state if isinstance(scan_state, dict) else {}
    return {
        "scanning": strict_bool(_safe_get(state, "running")),
        "cancelled": strict_bool(_safe_get(state, "cancelled")),
        "timed_out": strict_bool(_safe_get(state, "timed_out")),
        "errors": _safe_len(_safe_get(state, "errors")),
        "query_cache": _bounded_query_cache(query_cache),
        "search_index": _bounded_search_index(search_index),
        "thumbnail_prewarm": _bounded_prewarm(thumbnail_prewarm),
        "cover_cache": _bounded_cover_cache(cover_cache),
        "cache_failures": _bounded_cache_failures(cache_failures),
        "storage": _bounded_storage(storage),
        "connection_pool": _bounded_connection_pool(connection_pool),
    }


__all__ = ["library_component"]

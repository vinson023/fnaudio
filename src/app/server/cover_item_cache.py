"""Bounded, single-flight cache for extracting an item's local artwork."""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, MutableMapping, Optional, Tuple


CoverValue = Tuple[Any, Any]
MAX_ITEM_ID_CHARS = 512


def _safe_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return 0
    try:
        return int(value, 10) if isinstance(value, str) else value
    except (TypeError, ValueError, OverflowError):
        return 0


def _bounded_limit(value: Any, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return max(minimum, min(maximum, value))


def cached_cover_for_item(
    item: Any,
    config: Any,
    *,
    cache: MutableMapping[Tuple[str, int], CoverValue],
    cache_lock: threading.RLock,
    inflight: MutableMapping[Tuple[str, int], threading.Event],
    reader: Callable[[Dict[str, Any], Any], CoverValue],
    max_entries: int = 512,
    max_path_chars: int = 4096,
    inflight_limit: int = 64,
) -> CoverValue:
    if not isinstance(item, dict):
        return (None, None)
    try:
        raw_id = item.get("id")
        raw_path = item.get("path")
        raw_modified_ns = item.get("modified_ns")
        raw_modified = item.get("modified")
    except Exception:
        return (None, None)
    item_id = raw_id if isinstance(raw_id, str) and 0 < len(raw_id) <= MAX_ITEM_ID_CHARS else ""
    path = raw_path if isinstance(raw_path, str) else ""
    path = path[:_bounded_limit(max_path_chars, 4096, 0, 16384)]
    # Incomplete page rows can arrive before path hydration. Do not let every
    # such row alias the same ("", 0) cache entry; use its bounded ID as the
    # fallback identity, and refuse to cache a row with no stable identity.
    identity = path or ("id:" + item_id if item_id else "")
    if not identity:
        return (None, None)
    modified_ns = _safe_int(raw_modified_ns)
    key = (path, modified_ns if modified_ns else _safe_int(raw_modified))
    if not path:
        key = (identity, key[1])
    with cache_lock:
        cached = cache.get(key)
        if cached is not None:
            cache.pop(key, None)
            cache[key] = cached
            return cached
        waiter = inflight.get(key)
        leader = waiter is None
        if leader and len(inflight) < _bounded_limit(inflight_limit, 64, 0, 256):
            waiter = threading.Event()
            inflight[key] = waiter
        elif leader:
            # Never run an untracked extraction when every single-flight slot
            # is occupied. The caller can retry after an existing extraction
            # completes; starting here would defeat the configured bound.
            return (None, None)
    if not leader:
        waiter.wait(timeout=5.0)
        with cache_lock:
            cached = cache.get(key)
            if cached is not None:
                cache.pop(key, None)
                cache[key] = cached
                return cached
        # A stuck leader must not cause every waiter to become a new reader.
        # Return a temporary miss and leave the original owner responsible for
        # publishing or releasing its slot.
        return (None, None)
    try:
        value = reader(item, config)
        with cache_lock:
            cache.pop(key, None)
            entry_limit = _bounded_limit(max_entries, 512, 0, 4096)
            if len(cache) >= entry_limit and cache:
                cache.pop(next(iter(cache)), None)
            if entry_limit > 0:
                cache[key] = value
        return value
    finally:
        if waiter is not None:
            with cache_lock:
                inflight.pop(key, None)
                waiter.set()


def cache_snapshot(cache: Any, inflight: Any, *, entry_limit: Any = 512, inflight_limit: Any = 64) -> Dict[str, int]:
    """Return bounded cache pressure without exposing cache keys or values."""
    def length(value: Any) -> int:
        try:
            return max(0, min(4096, len(value)))
        except Exception:
            return 0
    return {
        "entries": length(cache),
        "limit": _bounded_limit(entry_limit, 512, 0, 4096),
        "inflight": length(inflight),
        "inflight_limit": _bounded_limit(inflight_limit, 64, 0, 256),
    }


__all__ = ["cached_cover_for_item", "cache_snapshot"]

"""Bounded, file-versioned local lyrics cache shared by metadata lanes."""

from __future__ import annotations

import os
import sys
import threading
from collections import OrderedDict


DEFAULT_LIMIT = 256
MAX_LIMIT = 4096
MAX_COUNTER = 1000000
# A lyric document is already capped at 2 MiB by the reader, so an entry count is
# not a resource bound on its own: at the configurable maximum of 4096 entries
# this cache could retain up to 8 GiB inside a phone-sized process. Retained
# bytes is the real budget; the entry limit only bounds how many documents stay
# pinned, and the smaller of the two always wins.
DEFAULT_MAX_BYTES = 8 * 1024 * 1024
MIN_MAX_BYTES = 64 * 1024
MAX_MAX_BYTES = 64 * 1024 * 1024
# Byte totals need a ceiling of their own. Reusing MAX_COUNTER (one million)
# would report an 8 MiB cache as a clamped 1 MB one.
MAX_BYTES_COUNTER = 1024 * 1024 * 1024


def _bounded_limit(value):
    if isinstance(value, bool) or not isinstance(value, int):
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, value))


def _bounded_bytes(value):
    if isinstance(value, bool) or not isinstance(value, int):
        return DEFAULT_MAX_BYTES
    return max(MIN_MAX_BYTES, min(MAX_MAX_BYTES, value))


def _retained_bytes(value):
    """Return the process memory one cached document occupies.

    Deliberately ``sys.getsizeof`` rather than a UTF-8 length: the budget
    protects the running process, and PEP 393 stores one, two or four bytes per
    character, so neither the encoded size nor the character count is the
    number that matters. The result is an estimate of a live object, so two
    caches holding distinct copies each pay for their own.
    """
    return sys.getsizeof(value)


def _version_key(path, version_hint, stat_func):
    if isinstance(version_hint, (tuple, list)) and len(version_hint) >= 2:
        mtime, size = version_hint[0], version_hint[1]
        if (isinstance(mtime, int) and not isinstance(mtime, bool) and mtime >= 0
                and isinstance(size, int) and not isinstance(size, bool) and size >= 0):
            return path, mtime, size
    try:
        stat = stat_func(path)
        return path, int(stat.st_mtime_ns), int(stat.st_size)
    except (OSError, TypeError, ValueError):
        # Virtual/custom readers can still resolve a path without a stat-able
        # backing file. Cache that result separately but retain reader truth.
        return path, 0, 0


class LocalLyricsCache:
    def __init__(self, reader, limit=DEFAULT_LIMIT, max_bytes=DEFAULT_MAX_BYTES, stat_func=os.stat):
        self._reader = reader
        self._limit = _bounded_limit(limit)
        self._bytes_limit = _bounded_bytes(max_bytes)
        self._stat = stat_func
        self._entries = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._bytes = 0

    def _release(self, key):
        """Drop one entry and the bytes it was counted for, as a unit."""
        entry = self._entries.pop(key, None)
        if entry is not None:
            self._bytes -= entry[1]

    def _enforce_budget(self):
        # A single small insert can overshoot the budget by less than one
        # document, so this has to keep evicting, not just drop the oldest.
        # ``self._entries`` cannot be reached while empty because oversized
        # documents are refused before insertion; the guard only keeps a future
        # accounting mistake from raising on a request path.
        while self._entries and (
                len(self._entries) > self._limit or self._bytes > self._bytes_limit):
            _, (_, size) = self._entries.popitem(last=False)
            self._bytes -= size

    def read(self, path, version_hint=None):
        if not isinstance(path, str) or not path:
            return ""
        key = _version_key(path, version_hint, self._stat)
        with self._lock:
            cached = self._entries.get(key)
            if cached is not None:
                self._hits = min(MAX_COUNTER, self._hits + 1)
                self._entries.move_to_end(key)
                return cached[0]
            self._misses = min(MAX_COUNTER, self._misses + 1)
            for old_key in tuple(self._entries):
                if old_key[0] == path and old_key != key:
                    self._release(old_key)
            try:
                value = self._reader(path)
            except (OSError, TypeError, ValueError):
                value = ""
            value = value if isinstance(value, str) else ""
            # Do not retain empty results. The reader may inspect sidecar or
            # embedded metadata whose version is not represented by a caller
            # supplied media-file hint; caching the miss could hide a newly
            # created/updated lyrics file until the media itself changes.
            if not value:
                return ""
            size = _retained_bytes(value)
            if size > self._bytes_limit:
                # A document bigger than the whole budget is served but never
                # kept: retaining it would evict everything else on every read,
                # which is worse than re-reading this one file.
                return value
            self._entries[key] = (value, size)
            self._bytes += size
            self._enforce_budget()
            return value

    def snapshot(self):
        """Return bounded counters without exposing paths or cached lyrics."""
        with self._lock:
            return {
                "entries": min(self._limit, len(self._entries)),
                "limit": self._limit,
                # Reported without an upper clamp on purpose. If the accounting
                # ever drifted above the budget, clamping here would hide the
                # exact leak this field exists to reveal.
                "bytes": max(0, self._bytes),
                "bytes_limit": self._bytes_limit,
                "hits": min(MAX_COUNTER, max(0, self._hits)),
                "misses": min(MAX_COUNTER, max(0, self._misses)),
            }


# Per-field ceilings for the aggregate projection. Field order is the reported
# key order so this matches ``LocalLyricsCache.snapshot()``.
SNAPSHOT_CEILINGS = {
    "entries": MAX_COUNTER,
    "limit": MAX_COUNTER,
    "bytes": MAX_BYTES_COUNTER,
    "bytes_limit": MAX_BYTES_COUNTER,
    "hits": MAX_COUNTER,
    "misses": MAX_COUNTER,
}


def combined_snapshot(*snapshots):
    """Aggregate cache pressure without retaining any cache identity data.

    Each argument is untrusted mapping data, so every field is clamped. The
    single-cache ``snapshot()`` above reports its own accounting instead.
    """
    result = {field: 0 for field in SNAPSHOT_CEILINGS}
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue
        for field, ceiling in SNAPSHOT_CEILINGS.items():
            value = snapshot.get(field)
            if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                result[field] = min(ceiling, result[field] + value)
    result["entries"] = min(result["entries"], result["limit"])
    result["bytes"] = min(result["bytes"], result["bytes_limit"])
    return result


__all__ = [
    "DEFAULT_LIMIT", "DEFAULT_MAX_BYTES", "MAX_LIMIT", "MAX_BYTES_COUNTER",
    "MAX_COUNTER", "MAX_MAX_BYTES", "MIN_MAX_BYTES", "LocalLyricsCache",
    "combined_snapshot",
]
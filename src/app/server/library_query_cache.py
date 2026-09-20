"""Bounded, invalidation-aware cache for read-only music-library pages.

The SQLite database remains fnAudio's authority.  This cache only absorbs
short bursts of identical list requests while users switch between library
views, and callers must invalidate it immediately after an index write.
"""

from __future__ import annotations

import copy
import math
import threading
import time
from collections import OrderedDict

from library_query_cache_presentation import counter_value, hit_rate, project_snapshot_counters

from library_query_cache_key import (
    MAX_CACHE_KEY_TEXT,
    MAX_CACHE_KEY_VALUES,
    build_cache_key,
    normalize_database_path,
)

MAX_CACHE_TTL_SECONDS = 3600.0
MAX_CACHE_ENTRIES = 4096
MAX_CACHE_RESULT_WEIGHT = 200000
SNAPSHOT_TTL_SECONDS = 0.75
MAX_CACHE_COUNTER = 10**12
# Databases whose last whole-database invalidation is remembered, so a page
# whose deep copy straddled that index write is not admitted afterwards.
MAX_INVALIDATED_DATABASES = 16


def _finite_number(value, default):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    try:
        number = float(value)
    except (OverflowError, ValueError):
        return default
    return number if math.isfinite(number) else default


class LibraryQueryCache:
    def __init__(self, ttl_seconds=20.0, limit=160, weight_limit=6000):
        ttl = _finite_number(ttl_seconds, 20.0)
        self.ttl_seconds = max(0.1, min(MAX_CACHE_TTL_SECONDS, ttl))
        capacity = int(_finite_number(limit, 160))
        self.limit = max(1, min(MAX_CACHE_ENTRIES, capacity))
        weight_capacity = int(_finite_number(weight_limit, 6000))
        self.weight_limit = max(1, min(MAX_CACHE_RESULT_WEIGHT, weight_capacity))
        # Keep hot library pages resident while users move between views.
        # A plain dict would evict by insertion age even after a page is read.
        self._entries = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expired = 0
        self._invalidations = 0
        self._weight = 0
        self._oversized = 0
        self._uncacheable = 0
        self._last_invalidations = OrderedDict()
        self._snapshot = None
        self._snapshot_at = 0.0
        self._snapshot_hits = 0
        self._snapshot_misses = 0

    def _bump(self, name, amount=1):
        current = counter_value(getattr(self, name, 0))
        delta = counter_value(amount, 0)
        setattr(self, name, min(MAX_CACHE_COUNTER, current + delta))

    def _invalidate_snapshot(self):
        self._snapshot = None
        self._snapshot_at = 0.0

    def _record_invalidation(self, database, now):
        """Remember when a database was last dropped, bounded by database count."""
        self._last_invalidations[database] = now
        self._last_invalidations.move_to_end(database)
        while len(self._last_invalidations) > MAX_INVALIDATED_DATABASES:
            self._last_invalidations.popitem(last=False)

    def _hit_rate(self):
        return hit_rate(self._hits, self._misses)

    def _is_saturated(self):
        try:
            entry_count = len(self._entries)
        except Exception:
            entry_count = 0
        weight = counter_value(self._weight, 0)
        return entry_count >= self.limit or weight >= self.weight_limit

    @staticmethod
    def _key(database_path, namespace, values, database_identity=None):
        return build_cache_key(database_path, namespace, values, database_identity)

    @staticmethod
    def _result_weight(result):
        if isinstance(result, dict):
            total = 0
            for name in ("items", "groups", "folders"):
                try:
                    value = result.get(name)
                except Exception:
                    return 1
                if isinstance(value, (list, tuple)):
                    try:
                        total += len(value)
                    except Exception:
                        return 1
            return max(1, total)
        if isinstance(result, (list, tuple)):
            try:
                return len(result)
            except Exception:
                return 1
        return 1

    def _remove(self, key):
        entry = self._entries.pop(key, None)
        if entry:
            try:
                weight = counter_value(entry[2], 0) if isinstance(entry, (tuple, list)) and len(entry) >= 3 else 0
            except Exception:
                weight = 0
            self._weight = max(0, counter_value(self._weight, 0) - weight)
            self._invalidate_snapshot()
        return entry

    @staticmethod
    def _entry_timestamp(entry):
        """Return a finite cache timestamp, or None for a corrupt entry."""
        try:
            if not isinstance(entry, (tuple, list)) or len(entry) < 3:
                return None
            return _finite_number(entry[0], None)
        except Exception:
            return None

    def _purge_expired(self, now):
        expired = []
        try:
            entries = list(self._entries.items())
        except Exception:
            entries = []
        for key, entry in entries:
            stale = False
            try:
                timestamp = entry[0] if isinstance(entry, (tuple, list)) and len(entry) >= 3 else None
                timestamp = _finite_number(timestamp, None)
                stale = timestamp is None or now - timestamp >= self.ttl_seconds
            except Exception:
                stale = True
            if stale:
                expired.append(key)
        for key in expired:
            self._remove(key)
        self._bump("_expired", len(expired))
        return len(expired)

    def get(self, database_path, namespace, values, database_identity=None):
        key = self._key(database_path, namespace, values, database_identity)
        now = time.monotonic()
        with self._lock:
            if key is None:
                self._bump("_misses")
                return None
            entry = self._entries.get(key)
            timestamp = self._entry_timestamp(entry)
            if timestamp is None or now - timestamp >= self.ttl_seconds:
                if entry:
                    self._remove(key)
                    self._bump("_expired" if timestamp is not None else "_uncacheable")
                self._bump("_misses")
                return None
            # Responses are enriched by a few callers.  Never hand a mutable
            # cache value back to them directly. The stored result is private
            # to this cache after put(), so take its stable reference while
            # locked but copy it after releasing the hot shared lock.
            self._entries.move_to_end(key)
            cached_result = entry[1]
        try:
            result = copy.deepcopy(cached_result)
        except Exception:
            with self._lock:
                # Do not evict a newer value written while deepcopy ran.
                if self._entries.get(key) is entry:
                    self._remove(key)
                self._bump("_uncacheable")
                self._bump("_misses")
            return None
        with self._lock:
            # The copy intentionally happens outside the lock, so an index
            # write can invalidate or replace this key while deepcopy runs.
            # Never return that obsolete snapshot as a cache hit.
            if self._entries.get(key) is not entry:
                self._bump("_misses")
                return None
            self._bump("_hits")
        return result

    def put(self, database_path, namespace, values, result, database_identity=None, read_at=None):
        key = self._key(database_path, namespace, values, database_identity)
        now = time.monotonic()
        # ``read_at`` is the instant the caller pinned this page's database
        # identity, which is always at or before the SQL read that produced the
        # result.  Admitting the entry under ``now`` instead would let an index
        # commit that lands between the read and this call look younger than the
        # data it just dropped, so the stale page would survive the whole TTL.
        admitted_at = _finite_number(read_at, now)
        if not 0 < admitted_at <= now:
            admitted_at = now
        with self._lock:
            if key is None:
                return result
            # Opportunistically remove stale pages before admitting a new one;
            # this preserves capacity for live hot pages after idle periods.
            self._purge_expired(now)
            weight = self._result_weight(result)
            if weight > self.weight_limit:
                self._remove(key)
                self._bump("_oversized")
                self._invalidate_snapshot()
                return result
            database = key[0]
        # A page can carry up to weight_limit rows, and deep-copying that much
        # data inside the shared lock stalls every other request thread plus
        # each index invalidation.  get() already copies after releasing this
        # lock; put() has to honour the same contract.
        try:
            cached_result = copy.deepcopy(result)
        except Exception:
            with self._lock:
                self._bump("_uncacheable")
                self._invalidate_snapshot()
            return result
        with self._lock:
            # An invalidation during the copy means this page may predate the
            # index write, so admitting it would resurrect dropped rows for a
            # whole TTL.  The read itself is still returned; only caching is
            # skipped, and the next request repopulates from current data.
            invalidated_at = self._last_invalidations.get(database)
            if invalidated_at is not None and invalidated_at >= admitted_at:
                return result
            self._remove(key)
            self._entries[key] = (admitted_at, cached_result, weight)
            self._weight += weight
            self._entries.move_to_end(key)
            while len(self._entries) > self.limit or self._weight > self.weight_limit:
                self._remove(next(iter(self._entries)))
                self._bump("_evictions")
            self._invalidate_snapshot()
        return result

    def invalidate_database(self, database_path):
        database = normalize_database_path(database_path)
        if database is None:
            return 0
        with self._lock:
            removed = []
            try:
                keys = list(self._entries)
            except Exception:
                keys = []
            for key in keys:
                try:
                    matches = isinstance(key, (tuple, list)) and len(key) >= 1 and key[0] == database
                except Exception:
                    matches = False
                if matches:
                    removed.append(key)
            for key in removed:
                self._remove(key)
            self._bump("_invalidations", len(removed))
            self._record_invalidation(database, time.monotonic())
            self._invalidate_snapshot()
        return len(removed)

    def snapshot(self):
        now = time.monotonic()
        with self._lock:
            if self._snapshot is not None and now - self._snapshot_at < SNAPSHOT_TTL_SECONDS:
                self._bump("_snapshot_hits")
                result = dict(self._snapshot)
                result["hits"] = self._hits
                result["misses"] = self._misses
                result["evictions"] = self._evictions
                result["expired"] = self._expired
                result["invalidations"] = self._invalidations
                result["oversized"] = self._oversized
                result["uncacheable"] = self._uncacheable
                result["hit_rate"] = self._hit_rate()
                result["saturated"] = self._is_saturated()
                result["snapshot"] = dict(result["snapshot"])
                result["snapshot"]["age_ms"] = int(max(0.0, now - self._snapshot_at) * 1000)
                result["snapshot"]["hits"] = self._snapshot_hits
                project_snapshot_counters(result)
                return result
            self._bump("_snapshot_misses")
            self._purge_expired(now)
            self._snapshot = {
                "entries": len(self._entries), "limit": self.limit,
                "weight": self._weight, "weight_limit": self.weight_limit,
                "ttl_seconds": self.ttl_seconds, "hits": self._hits,
                "misses": self._misses, "evictions": self._evictions,
                "expired": self._expired,
                "invalidations": self._invalidations,
                "oversized": self._oversized,
                "uncacheable": self._uncacheable,
                "hit_rate": self._hit_rate(),
                "saturated": self._is_saturated(),
                "snapshot": {
                    "ttl_ms": int(SNAPSHOT_TTL_SECONDS * 1000),
                    "age_ms": 0,
                    "hits": self._snapshot_hits,
                    "misses": self._snapshot_misses,
                },
            }
            self._snapshot_at = now
            result = dict(self._snapshot)
            result["snapshot"] = dict(result["snapshot"])
            project_snapshot_counters(result)
            return result

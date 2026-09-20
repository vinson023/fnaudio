import unittest
import copy
import threading
import time
from unittest.mock import patch

import sys

sys.path.insert(0, "app/server")

from library_query_cache import MAX_CACHE_KEY_TEXT, MAX_CACHE_KEY_VALUES, MAX_CACHE_COUNTER, LibraryQueryCache
from library_query_cache_key import MAX_CACHE_KEY_TEXT as KEY_MAX_CACHE_KEY_TEXT, MAX_CACHE_KEY_VALUES as KEY_MAX_CACHE_KEY_VALUES


class LibraryQueryCacheTests(unittest.TestCase):
    def test_invalidation_isolates_corrupt_cache_keys(self):
        class BrokenKey(tuple):
            def __getitem__(self, index):
                raise RuntimeError("broken key")

        cache = LibraryQueryCache(ttl_seconds=30, limit=3)
        cache.put("/tmp/db", "tracks", ("ok",), {"id": "ok"})
        cache._entries[BrokenKey(("/tmp/db", "tracks", ("bad",)))] = (10.0, {"id": "bad"}, 1)
        self.assertEqual(cache.invalidate_database("/tmp/db"), 1)
        self.assertEqual(len(cache._entries), 1)

    def test_expiry_cleanup_isolates_corrupt_internal_entries(self):
        cache = LibraryQueryCache(ttl_seconds=30, limit=2)
        cache._entries["broken"] = object()
        cache._entries["short"] = (0.0, {"id": "short"})
        cache._entries["live"] = (100.0, {"id": "live"}, 1)
        with patch("library_query_cache.time.monotonic", return_value=100.0):
            status = cache.snapshot()
        self.assertEqual(status["entries"], 1)
        self.assertEqual(status["expired"], 2)
        self.assertIsNone(cache.get("/tmp/db", "missing", ()))

    def test_direct_lookup_isolates_corrupt_entry_shape(self):
        cache = LibraryQueryCache(ttl_seconds=30, limit=2)
        cache.put("/tmp/db", "page", (1,), {"id": 1})
        key = cache._key("/tmp/db", "page", (1,))
        cache._entries[key] = ("not-a-time", {"id": 1}, 1)
        self.assertIsNone(cache.get("/tmp/db", "page", (1,)))
        status = cache.snapshot()
        self.assertEqual(status["uncacheable"], 1)
        self.assertEqual(status["misses"], 1)

    def test_corrupt_internal_counters_are_isolated(self):
        class Explosive:
            def __float__(self):
                raise AssertionError("cache counters must not coerce custom values")

        cache = LibraryQueryCache()
        cache._hits = Explosive()
        cache._misses = float("nan")
        cache._invalidations = -4
        cache._snapshot_hits = Explosive()
        cache._snapshot_misses = MAX_CACHE_COUNTER + 100
        cache.put("/tmp/db", "page", (1,), {"id": 1})
        self.assertIsNotNone(cache.get("/tmp/db", "page", (1,)))
        snapshot = cache.snapshot()
        self.assertEqual(snapshot["hits"], 1)
        self.assertGreaterEqual(snapshot["misses"], 0)
        self.assertEqual(snapshot["invalidations"], 0)
        self.assertLessEqual(snapshot["snapshot"]["hits"], MAX_CACHE_COUNTER)

    def test_snapshot_is_safe_before_any_counter_recovery_path(self):
        class Explosive:
            def __add__(self, other):
                raise AssertionError("cache counters must not be added directly")

        cache = LibraryQueryCache()
        cache._hits = Explosive()
        cache._misses = float("nan")
        snapshot = cache.snapshot()
        self.assertEqual(snapshot["hits"], 0)
        self.assertEqual(snapshot["misses"], 0)
        self.assertEqual(snapshot["hit_rate"], 0.0)
    def test_cache_key_limits_have_one_authoritative_source(self):
        self.assertEqual(MAX_CACHE_KEY_TEXT, KEY_MAX_CACHE_KEY_TEXT)
        self.assertEqual(MAX_CACHE_KEY_VALUES, KEY_MAX_CACHE_KEY_VALUES)

    def test_returns_a_copy_and_invalidates_only_the_requested_database(self):
        cache = LibraryQueryCache(ttl_seconds=30, limit=2)
        first_database = "/tmp/first.sqlite3"
        second_database = "/tmp/second.sqlite3"
        result = {"items": [{"id": "one"}]}
        cache.put(first_database, "tracks", ("all", 0), result)
        cache.put(second_database, "tracks", ("all", 0), result)

        cached = cache.get(first_database, "tracks", ("all", 0))
        cached["items"][0]["id"] = "changed"
        self.assertEqual(cache.get(first_database, "tracks", ("all", 0))["items"][0]["id"], "one")

        cache.invalidate_database(first_database)
        self.assertIsNone(cache.get(first_database, "tracks", ("all", 0)))
        self.assertIsNotNone(cache.get(second_database, "tracks", ("all", 0)))

    def test_entry_count_is_bounded(self):
        cache = LibraryQueryCache(ttl_seconds=30, limit=2)
        for index in range(3):
            cache.put("/tmp/library.sqlite3", "tracks", (index,), {"id": index})
        self.assertEqual(cache.snapshot()["entries"], 2)
        self.assertIsNone(cache.get("/tmp/library.sqlite3", "tracks", (0,)))
        self.assertEqual(cache.snapshot()["evictions"], 1)

    def test_recently_read_page_is_retained_when_cache_reaches_capacity(self):
        cache = LibraryQueryCache(ttl_seconds=30, limit=2)
        database = "/tmp/library.sqlite3"
        cache.put(database, "tracks", ("first",), {"id": "first"})
        cache.put(database, "tracks", ("second",), {"id": "second"})
        self.assertEqual(cache.get(database, "tracks", ("first",))["id"], "first")
        cache.put(database, "tracks", ("third",), {"id": "third"})
        self.assertIsNotNone(cache.get(database, "tracks", ("first",)))
        self.assertIsNone(cache.get(database, "tracks", ("second",)))
        self.assertIsNotNone(cache.get(database, "tracks", ("third",)))

    def test_status_exposes_hits_misses_and_invalidations(self):
        cache = LibraryQueryCache(ttl_seconds=30, limit=2)
        cache.put("/tmp/library.sqlite3", "tracks", (0,), {"id": 0})
        self.assertIsNotNone(cache.get("/tmp/library.sqlite3", "tracks", (0,)))
        self.assertIsNone(cache.get("/tmp/library.sqlite3", "tracks", (1,)))
        cache.invalidate_database("/tmp/library.sqlite3")
        status = cache.snapshot()
        self.assertEqual(status["hits"], 1)
        self.assertEqual(status["misses"], 1)
        self.assertEqual(status["invalidations"], 1)
        self.assertEqual(status["hit_rate"], 0.5)

    def test_repeated_page_read_uses_cache_and_preserves_the_response(self):
        cache = LibraryQueryCache(ttl_seconds=30, limit=2)
        database = "/tmp/library.sqlite3"
        response = {"items": [{"id": "one"}], "count": 1, "paged": True}
        cache.put(database, "tracks", ("all", 120, 0), response)
        first = cache.get(database, "tracks", ("all", 120, 0))
        second = cache.get(database, "tracks", ("all", 120, 0))
        self.assertEqual(first, response)
        self.assertEqual(second, response)
        self.assertIsNot(first, second)
        self.assertEqual(cache.snapshot()["hits"], 2)

    def test_cache_copy_does_not_hold_the_shared_lock(self):
        cache = LibraryQueryCache(ttl_seconds=30, limit=2)
        cache.put("/tmp/library.sqlite3", "tracks", ("page",), {"items": [{"id": "one"}]})
        entered = threading.Event()
        release = threading.Event()
        real_deepcopy = copy.deepcopy

        def blocked_deepcopy(value):
            entered.set()
            release.wait(2)
            return real_deepcopy(value)

        with patch("library_query_cache.copy.deepcopy", side_effect=blocked_deepcopy):
            reader = threading.Thread(target=lambda: cache.get("/tmp/library.sqlite3", "tracks", ("page",)))
            reader.start()
            self.assertTrue(entered.wait(1))
            started = time.monotonic()
            self.assertEqual(cache.invalidate_database("/tmp/other.sqlite3"), 0)
            self.assertLess(time.monotonic() - started, 0.25)
            release.set()
            reader.join(2)
            self.assertFalse(reader.is_alive())

    def test_cache_copy_does_not_return_entry_invalidated_during_copy(self):
        cache = LibraryQueryCache(ttl_seconds=30, limit=2)
        database = "/tmp/library.sqlite3"
        cache.put(database, "tracks", ("page",), {"items": [{"id": "old"}]})
        entered = threading.Event()
        release = threading.Event()
        real_deepcopy = copy.deepcopy

        def blocked_deepcopy(value):
            entered.set()
            release.wait(2)
            return real_deepcopy(value)

        result = []
        with patch("library_query_cache.copy.deepcopy", side_effect=blocked_deepcopy):
            reader = threading.Thread(
                target=lambda: result.append(cache.get(database, "tracks", ("page",)))
            )
            reader.start()
            self.assertTrue(entered.wait(1))
            cache.invalidate_database(database)
            release.set()
            reader.join(2)
        self.assertFalse(reader.is_alive())
        self.assertEqual(result, [None])
        self.assertEqual(cache.snapshot()["hits"], 0)

    def test_put_copy_does_not_hold_the_shared_lock(self):
        cache = LibraryQueryCache(ttl_seconds=30, limit=4)
        database = "/tmp/library.sqlite3"
        cache.put(database, "tracks", ("page",), {"items": [{"id": "one"}]})
        entered = threading.Event()
        release = threading.Event()
        real_deepcopy = copy.deepcopy

        def blocked_deepcopy(value):
            entered.set()
            release.wait(2)
            return real_deepcopy(value)

        with patch("library_query_cache.copy.deepcopy", side_effect=blocked_deepcopy):
            writer = threading.Thread(
                target=lambda: cache.put(database, "folders", ("page",), {"items": [{"id": "two"}]})
            )
            writer.start()
            self.assertTrue(entered.wait(1))
            started = time.monotonic()
            self.assertEqual(cache.invalidate_database("/tmp/other.sqlite3"), 0)
            self.assertLess(time.monotonic() - started, 0.25)
            started = time.monotonic()
            self.assertEqual(cache.snapshot()["misses"], 0)
            self.assertLess(time.monotonic() - started, 0.25)
            release.set()
            writer.join(2)
            self.assertFalse(writer.is_alive())
        self.assertEqual(cache.get(database, "folders", ("page",)), {"items": [{"id": "two"}]})

    def test_put_is_dropped_when_the_database_is_invalidated_during_the_copy(self):
        cache = LibraryQueryCache(ttl_seconds=30, limit=4)
        database = "/tmp/library.sqlite3"
        cache.put(database, "tracks", ("earlier",), {"items": [{"id": "earlier"}]})
        entered = threading.Event()
        release = threading.Event()
        real_deepcopy = copy.deepcopy
        removed = []

        def blocked_deepcopy(value):
            entered.set()
            release.wait(2)
            return real_deepcopy(value)

        with patch("library_query_cache.copy.deepcopy", side_effect=blocked_deepcopy):
            writer = threading.Thread(
                target=lambda: cache.put(database, "tracks", ("page",), {"items": [{"id": "page"}]})
            )
            writer.start()
            self.assertTrue(entered.wait(1))
            # The invalidation has to observe the pre-insert state: the copy is
            # no longer inside the lock, so only the earlier page can be found.
            removed.append(cache.invalidate_database(database))
            release.set()
            writer.join(2)
        self.assertFalse(writer.is_alive())
        self.assertEqual(removed, [1])
        self.assertIsNone(cache.get(database, "tracks", ("page",)))
        self.assertIsNone(cache.get(database, "tracks", ("earlier",)))
        self.assertEqual(cache.snapshot()["invalidations"], 1)

    def test_put_fences_against_the_read_instant_not_the_call_instant(self):
        cache = LibraryQueryCache(ttl_seconds=30, limit=4)
        database = "/tmp/library.sqlite3"
        cache.put(database, "tracks", ("earlier",), {"items": [{"id": "earlier"}]})
        # The page was read at t=105, the index commit dropped the cache at
        # t=110, and put() only gets called at t=112.  Judging the fence
        # against 112 admits pre-commit rows under a post-commit key.
        with patch("library_query_cache.time.monotonic", side_effect=[110.0, 112.0, 112.0]):
            self.assertEqual(cache.invalidate_database(database), 1)
            cache.put(
                database,
                "tracks",
                ("page",),
                {"items": [{"id": "pre-commit"}]},
                read_at=105.0,
            )
            self.assertIsNone(cache.get(database, "tracks", ("page",)))

    def test_read_at_ages_the_entry_from_the_database_read(self):
        cache = LibraryQueryCache(ttl_seconds=30, limit=4)
        database = "/tmp/library.sqlite3"
        with patch("library_query_cache.time.monotonic", side_effect=[140.0, 140.0]):
            cache.put(
                database,
                "tracks",
                ("page",),
                {"items": [{"id": "one"}]},
                read_at=110.0,
            )
            # The rows are already 30 seconds old, so the TTL must not restart
            # just because the write happened later.
            self.assertIsNone(cache.get(database, "tracks", ("page",)))

    def test_out_of_range_read_at_falls_back_to_the_call_instant(self):
        cache = LibraryQueryCache(ttl_seconds=30, limit=4)
        database = "/tmp/library.sqlite3"
        for read_at in (None, 0.0, -5.0, float("nan"), float("inf"), "105", 1000.0):
            with self.subTest(read_at=read_at):
                # t=90 invalidation stays behind the patched clock so only the
                # clamped read instant can decide whether the page is admitted.
                with patch("library_query_cache.time.monotonic", side_effect=[90.0, 100.0, 120.0]):
                    cache.invalidate_database(database)
                    cache.put(
                        database,
                        "tracks",
                        ("page",),
                        {"items": [{"id": "one"}]},
                        read_at=read_at,
                    )
                    self.assertEqual(
                        cache.get(database, "tracks", ("page",)),
                        {"items": [{"id": "one"}]},
                    )

    def test_status_reports_entry_or_weight_budget_saturation(self):
        cache = LibraryQueryCache(ttl_seconds=30, limit=2, weight_limit=3)
        cache.put("/tmp/db", "tracks", (1,), {"items": [{"id": 1}]})
        self.assertFalse(cache.snapshot()["saturated"])
        cache.put("/tmp/db", "tracks", (2,), {"items": [{"id": 2}, {"id": 3}]})
        self.assertTrue(cache.snapshot()["saturated"])

    def test_saturation_projection_is_safe_with_corrupt_weight(self):
        class Explosive:
            def __float__(self):
                raise AssertionError("saturation must not coerce corrupt weight")

        cache = LibraryQueryCache()
        cache._weight = Explosive()
        self.assertFalse(cache.snapshot()["saturated"])

    def test_empty_cache_reports_zero_hit_rate(self):
        cache = LibraryQueryCache()
        self.assertEqual(cache.snapshot()["hit_rate"], 0.0)

    def test_put_purges_expired_entries_before_eviction(self):
        cache = LibraryQueryCache(ttl_seconds=1, limit=2)
        with patch("library_query_cache.time.monotonic", side_effect=[0.0, 2.0, 2.1, 2.1, 2.1]):
            cache.put("/tmp/db", "page", (1,), {"items": [1]})
            cache.put("/tmp/db", "page", (2,), {"items": [2]})
            cache.put("/tmp/db", "page", (3,), {"items": [3]})
            self.assertEqual(cache.snapshot()["entries"], 2)
            self.assertEqual(cache.get("/tmp/db", "page", (1,)), None)

    def test_snapshot_does_not_report_expired_entries(self):
        cache = LibraryQueryCache(ttl_seconds=1, limit=2)
        with patch("library_query_cache.time.monotonic", side_effect=[0.0, 2.0, 2.0]):
            cache.put("/tmp/db", "page", (1,), {"items": [1]})
            snapshot = cache.snapshot()
            self.assertEqual(snapshot["entries"], 0)
            self.assertEqual(snapshot["expired"], 1)

    def test_snapshot_coalesces_expiry_walks_until_cache_changes(self):
        cache = LibraryQueryCache(ttl_seconds=30, limit=4)
        cache.put("/tmp/db", "page", (1,), {"items": [1]})
        with patch.object(cache, "_purge_expired", wraps=cache._purge_expired) as purge:
            first = cache.snapshot()
            second = cache.snapshot()
        self.assertEqual(purge.call_count, 1)
        self.assertEqual(first["snapshot"]["ttl_ms"], 750)
        self.assertEqual(first["snapshot"]["age_ms"], 0)
        self.assertGreaterEqual(second["snapshot"]["hits"], 1)
        self.assertGreaterEqual(second["snapshot"]["age_ms"], 0)

    def test_query_reads_do_not_invalidate_status_snapshot(self):
        cache = LibraryQueryCache(ttl_seconds=30, limit=4)
        cache.put("/tmp/db", "page", (1,), {"items": [1]})
        cache.snapshot()
        with patch.object(cache, "_purge_expired", wraps=cache._purge_expired) as purge:
            self.assertIsNotNone(cache.get("/tmp/db", "page", (1,)))
            cache.snapshot()
        self.assertEqual(purge.call_count, 0)

    def test_constructor_bounds_ttl_and_capacity(self):
        cache = LibraryQueryCache(ttl_seconds=-10, limit=999999, weight_limit=999999)
        self.assertEqual(cache.ttl_seconds, 0.1)
        self.assertEqual(cache.limit, 4096)
        self.assertEqual(cache.weight_limit, 200000)

    def test_constructor_rejects_non_finite_and_custom_numeric_inputs(self):
        class Explosive:
            def __float__(self):
                raise AssertionError("cache configuration must not coerce objects")
            def __int__(self):
                raise AssertionError("cache configuration must not coerce objects")

        cache = LibraryQueryCache(ttl_seconds=float("nan"), limit=float("inf"), weight_limit=Explosive())
        self.assertEqual(cache.ttl_seconds, 20.0)
        self.assertEqual(cache.limit, 160)
        self.assertEqual(cache.weight_limit, 6000)

    def test_constructor_rejects_huge_integer_without_float_overflow(self):
        huge = 10 ** 10000
        cache = LibraryQueryCache(ttl_seconds=huge, limit=huge, weight_limit=huge)
        self.assertEqual(cache.ttl_seconds, 20.0)
        self.assertEqual(cache.limit, 160)
        self.assertEqual(cache.weight_limit, 6000)

    def test_direct_expired_lookup_increments_expired_counter(self):
        cache = LibraryQueryCache(ttl_seconds=1, limit=2)
        with patch("library_query_cache.time.monotonic", side_effect=[0.0, 2.0, 2.0]):
            cache.put("/tmp/db", "page", (1,), {"items": [1]})
            self.assertIsNone(cache.get("/tmp/db", "page", (1,)))
            self.assertEqual(cache.snapshot()["expired"], 1)

    def test_cache_key_is_bounded_and_never_stringifies_custom_input(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("cache keys must not stringify arbitrary values")

        class LimitedValues:
            def __iter__(self):
                for index in range(MAX_CACHE_KEY_VALUES):
                    yield index

        cache = LibraryQueryCache(ttl_seconds=30, limit=2)
        cache.put(Explosive(), "tracks", (), {"id": "invalid"})
        self.assertEqual(cache.snapshot()["entries"], 0)
        self.assertIsNone(cache.get(Explosive(), "tracks", ()))
        long_value = "x" * (MAX_CACHE_KEY_TEXT + 100)
        cache.put("/tmp/library.sqlite3", "tracks", LimitedValues(), {"id": "bounded"})
        self.assertEqual(cache.get("/tmp/library.sqlite3", "tracks", tuple(range(MAX_CACHE_KEY_VALUES)))["id"], "bounded")
        cache.put("/tmp/long.sqlite3", "tracks", (long_value, Explosive()), {"id": "text"})
        self.assertIsNone(cache.get("/tmp/long.sqlite3", "tracks", (long_value, Explosive())))
        cache.put("/tmp/numbers.sqlite3", "tracks", (float("nan"),), {"id": "nan"})
        self.assertIsNone(cache.get("/tmp/numbers.sqlite3", "tracks", (float("nan"),)))

    def test_cache_key_isolates_broken_iterators(self):
        class BrokenIterator:
            def __iter__(self):
                return self

            def __next__(self):
                raise RuntimeError("broken iterator")

        class BrokenIterable:
            def __iter__(self):
                raise RuntimeError("broken iterable")

        cache = LibraryQueryCache(ttl_seconds=30, limit=2)
        cache.put("/tmp/library.sqlite3", "tracks", BrokenIterator(), {"id": "iterator"})
        cache.put("/tmp/library.sqlite3", "tracks", BrokenIterable(), {"id": "iterable"})
        self.assertEqual(cache.snapshot()["entries"], 0)
        self.assertIsNone(cache.get("/tmp/library.sqlite3", "tracks", BrokenIterator()))

    def test_result_weight_bounds_cached_lists_without_evicting_for_an_oversized_page(self):
        cache = LibraryQueryCache(ttl_seconds=30, limit=4, weight_limit=3)
        database = "/tmp/library.sqlite3"
        cache.put(database, "tracks", ("one",), {"items": [{"id": 1}, {"id": 2}]})
        cache.put(database, "groups", ("two",), {"groups": [{"name": "A"}, {"name": "B"}]})
        self.assertIsNone(cache.get(database, "tracks", ("one",)))
        self.assertIsNotNone(cache.get(database, "groups", ("two",)))
        self.assertEqual(cache.snapshot()["weight"], 2)

        cache.put(database, "tracks", ("huge",), {"items": [{}] * 4})
        status = cache.snapshot()
        self.assertEqual(status["weight"], 2)
        self.assertEqual(status["oversized"], 1)
        self.assertIsNone(cache.get(database, "tracks", ("huge",)))
        self.assertIsNotNone(cache.get(database, "groups", ("two",)))

    def test_uncopyable_results_are_not_allowed_to_break_cache_callers(self):
        class Uncopyable:
            def __deepcopy__(self, memo):
                raise RuntimeError("copy blocked")

        cache = LibraryQueryCache(ttl_seconds=30, limit=2)
        database = "/tmp/library.sqlite3"
        result = {"items": [Uncopyable()]}
        self.assertIs(cache.put(database, "tracks", ("bad",), result), result)
        self.assertIsNone(cache.get(database, "tracks", ("bad",)))
        self.assertEqual(cache.snapshot()["uncacheable"], 1)

    def test_result_weight_isolates_broken_mapping_access(self):
        class BrokenMapping(dict):
            def get(self, key, default=None):
                raise RuntimeError("mapping broken")

        cache = LibraryQueryCache(ttl_seconds=30, limit=2)
        result = BrokenMapping(items=[1, 2])
        self.assertIs(cache.put("/tmp/library.sqlite3", "tracks", ("broken",), result), result)
        self.assertEqual(cache.get("/tmp/library.sqlite3", "tracks", ("broken",)), result)


if __name__ == "__main__":
    unittest.main()

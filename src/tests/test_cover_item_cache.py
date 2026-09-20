import threading
import time
import unittest
from unittest import mock
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "server"))

from cover_item_cache import cache_snapshot, cached_cover_for_item


class CoverItemCacheTests(unittest.TestCase):
    def test_single_flight_and_lru_are_bounded(self):
        cache = {}
        inflight = {}
        lock = threading.RLock()
        started = threading.Event()
        release = threading.Event()
        calls = []

        def reader(item, _config):
            calls.append(item["path"])
            started.set()
            release.wait(2)
            return ("image/jpeg", b"x")

        item = {"path": "cover", "modified": 1}
        results = []
        first = threading.Thread(target=lambda: results.append(cached_cover_for_item(item, {}, cache=cache, cache_lock=lock, inflight=inflight, reader=reader, max_entries=1)))
        second = threading.Thread(target=lambda: results.append(cached_cover_for_item(item, {}, cache=cache, cache_lock=lock, inflight=inflight, reader=reader, max_entries=1)))
        first.start()
        self.assertTrue(started.wait(1))
        second.start()
        time.sleep(0.02)
        release.set()
        first.join(2)
        second.join(2)
        self.assertEqual(calls, ["cover"])
        self.assertEqual(results, [("image/jpeg", b"x"), ("image/jpeg", b"x")])
        self.assertLessEqual(len(cache), 1)

    def test_invalid_limits_fall_back_without_coercing_custom_objects(self):
        class Hostile:
            def __int__(self):
                raise AssertionError("must not coerce custom limits")

        cache = {}
        inflight = {}
        value = cached_cover_for_item(
            {"path": "p" * 5000, "modified": 1},
            {},
            cache=cache,
            cache_lock=threading.RLock(),
            inflight=inflight,
            reader=lambda _item, _config: ("image/jpeg", b"x"),
            max_entries=Hostile(),
            max_path_chars=Hostile(),
            inflight_limit=Hostile(),
        )
        self.assertEqual(value, ("image/jpeg", b"x"))
        self.assertEqual(len(next(iter(cache))[0]), 4096)

    def test_cache_key_rejects_hostile_version_fields_without_interrupting_reader(self):
        class Hostile:
            def __bool__(self):
                raise AssertionError("version must not use implicit truthiness")

            def __int__(self):
                raise AssertionError("version must not coerce custom objects")

        cache = {}
        value = cached_cover_for_item(
            {"path": "cover", "modified_ns": Hostile(), "modified": Hostile()},
            {}, cache=cache, cache_lock=threading.RLock(), inflight={},
            reader=lambda _item, _config: ("image/jpeg", b"x"),
        )
        self.assertEqual(value, ("image/jpeg", b"x"))
        self.assertIn(("cover", 0), cache)

    def test_incomplete_rows_with_distinct_ids_do_not_share_cover_cache_entry(self):
        cache = {}
        lock = threading.RLock()
        inflight = {}
        calls = []

        def reader(item, _config):
            calls.append(item["id"])
            return ("image/jpeg", item["id"].encode("ascii"))

        first = {"id": "first", "modified": 1}
        second = {"id": "second", "modified": 1}
        self.assertEqual(
            cached_cover_for_item(first, {}, cache=cache, cache_lock=lock,
                                  inflight=inflight, reader=reader),
            ("image/jpeg", b"first"),
        )
        self.assertEqual(
            cached_cover_for_item(second, {}, cache=cache, cache_lock=lock,
                                  inflight=inflight, reader=reader),
            ("image/jpeg", b"second"),
        )
        self.assertEqual(calls, ["first", "second"])

    def test_row_without_path_or_id_is_not_cached_or_read(self):
        cache = {}
        reader = mock.Mock(return_value=("image/jpeg", b"x"))
        self.assertEqual(
            cached_cover_for_item({}, {}, cache=cache, cache_lock=threading.RLock(),
                                  inflight={}, reader=reader),
            (None, None),
        )
        reader.assert_not_called()
        self.assertEqual(cache, {})

    def test_saturated_or_timed_out_single_flight_never_runs_an_untracked_reader(self):
        cache = {}
        lock = threading.RLock()
        calls = []
        reader = lambda _item, _config: calls.append(True) or ("image/jpeg", b"x")
        blocked = threading.Event()
        inflight = {("other", 1): blocked}

        self.assertEqual(
            cached_cover_for_item(
                {"path": "new", "modified": 1}, {}, cache=cache, cache_lock=lock,
                inflight=inflight, reader=reader, inflight_limit=1,
            ),
            (None, None),
        )

        same_key = ("same", 1)
        inflight = {same_key: threading.Event()}
        with mock.patch.object(inflight[same_key], "wait", return_value=False):
            self.assertEqual(
                cached_cover_for_item(
                    {"path": "same", "modified": 1}, {}, cache=cache, cache_lock=lock,
                    inflight=inflight, reader=reader,
                ),
                (None, None),
            )
        self.assertEqual(calls, [])

    def test_snapshot_is_bounded_and_isolates_broken_containers(self):
        class Broken:
            def __len__(self):
                raise RuntimeError("broken length")
        class Hostile:
            def __int__(self):
                raise AssertionError("must not coerce limit")
        self.assertEqual(
            cache_snapshot(Broken(), Broken(), entry_limit=Hostile(), inflight_limit=Hostile()),
            {"entries": 0, "limit": 512, "inflight": 0, "inflight_limit": 64},
        )


if __name__ == "__main__":
    unittest.main()

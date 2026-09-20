import unittest

from app.server.playback_command_cache import cache_snapshot, cached_result, store_result


class PlaybackCommandCacheTests(unittest.TestCase):
    def test_reads_a_defensive_copy_and_prunes_expired_values(self):
        cache = {
            "old": (2.0, {"ok": True}, 200),
            "live": (4.0, {"ok": True}, 201),
        }
        response, status = cached_result(cache, "live", 3.0)
        response["ok"] = False
        self.assertEqual(status, 201)
        self.assertEqual(cache, {"live": (4.0, {"ok": True}, 201)})

    def test_bad_entries_are_removed_without_breaking_the_cache(self):
        cache = {"bad": (object(), {}, 200), "shape": (3.0,), "live": (4.0, {}, 200)}
        self.assertEqual(cached_result(cache, "live", 3.0), ({}, 200))
        self.assertEqual(cache, {"live": (4.0, {}, 200)})

    def test_store_evicts_oldest_entry_at_the_bound(self):
        cache = {}
        for key in ("a", "b", "c"):
            store_result(cache, key, {"key": key}, 200, 10.0, 2)
        self.assertEqual(list(cache), ["b", "c"])

    def test_store_copies_response_and_bounds_invalid_limit(self):
        cache = {}
        response = {"ok": True}
        store_result(cache, "a", response, 200, 10.0, object())
        response["ok"] = False
        self.assertEqual(cache["a"][1], {"ok": True})

    def test_invalid_arguments_do_not_mutate_cache(self):
        cache = {"live": (9.0, {}, 200)}
        store_result(cache, "bad", [], 200, 10.0, 2)
        self.assertEqual(cache, {"live": (9.0, {}, 200)})

    def test_snapshot_exposes_only_bounded_pressure(self):
        self.assertEqual(cache_snapshot({"a": (), "b": ()}, 2), {"entries": 2, "limit": 2, "saturated": True})
        self.assertEqual(cache_snapshot(object(), object()), {"entries": 0, "limit": 1, "saturated": False})


if __name__ == "__main__":
    unittest.main()

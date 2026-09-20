import sys
import unittest

sys.path.insert(0, "app/server")

from library_snapshot import library_component


class LibrarySnapshotTests(unittest.TestCase):
    def test_snapshot_exposes_pressure_without_paths_or_items(self):
        snapshot = library_component(
            {"running": True, "cancelled": False, "timed_out": True, "errors": ["one", "two"], "path": "/vol1/music"},
            query_cache={"entries": 2, "hits": 4},
            search_index={"mode": "fts5-trigram", "substring_minimum_chars": 3},
            thumbnail_prewarm={"interactive": {"queued": 1}},
        )
        self.assertTrue(snapshot["scanning"])
        self.assertTrue(snapshot["timed_out"])
        self.assertEqual(snapshot["errors"], 2)
        self.assertEqual(snapshot["search_index"]["mode"], "fts5-trigram")
        self.assertEqual(snapshot["thumbnail_prewarm"]["interactive"]["queued"], 1)
        self.assertNotIn("path", str(snapshot))
        self.assertNotIn("items", snapshot)

    def test_snapshot_keeps_only_bounded_prewarm_pressure_fields(self):
        snapshot = library_component(None, thumbnail_prewarm={
            "interactive": {"queued": "2", "private_path": "/secret"},
            "library": {"limit": 5000, "root_rejected": 1, "items": list(range(100))},
            "unexpected": {"payload": "ignored"},
        })
        self.assertEqual(snapshot["thumbnail_prewarm"]["interactive"]["queued"], 2)
        self.assertEqual(snapshot["thumbnail_prewarm"]["library"]["limit"], 5000)
        self.assertNotIn("private_path", str(snapshot))
        self.assertNotIn("items", str(snapshot))
        self.assertNotIn("unexpected", snapshot["thumbnail_prewarm"])

    def test_snapshot_has_stable_defaults(self):
        snapshot = library_component(None)
        self.assertFalse(snapshot["scanning"])
        self.assertEqual(snapshot["errors"], 0)
        self.assertEqual(snapshot["connection_pool"], {
            "idle": 0, "databases": 0, "reuses": 0, "creations": 0, "closures": 0,
            "max_idle_per_database": 0, "max_idle_total": 0,
        })

    def test_snapshot_bounds_connection_pool_counters_without_paths(self):
        snapshot = library_component(None, connection_pool={
            "idle": "2", "databases": 1, "reuses": 40, "creations": 3, "closures": 5,
            "max_idle_per_database": 9, "max_idle_total": 99,
            "database": "/vol1/music/cache/library.sqlite3",
            "borrowed": ["a", "b"],
        })
        self.assertEqual(snapshot["connection_pool"], {
            "idle": 2, "databases": 1, "reuses": 40, "creations": 3, "closures": 5,
            "max_idle_per_database": 9, "max_idle_total": 99,
        })
        self.assertNotIn("vol1", str(snapshot))
        self.assertNotIn("borrowed", str(snapshot))
        self.assertEqual(snapshot["search_index"], {"mode": "like", "substring_minimum_chars": 0})

    def test_snapshot_bounds_cache_and_search_index_fields(self):
        snapshot = library_component(
            None,
            query_cache={"hits": "4", "entries": 2, "limit": 160, "weight": 120, "weight_limit": 6000, "oversized": 1, "uncacheable": 3, "saturated": True, "snapshot": {"ttl_ms": 750, "age_ms": 12, "hits": 2, "private": "/secret"}, "token": "secret", "huge": list(range(50))},
            search_index={"mode": "x" * 200, "substring_minimum_chars": "3", "private": "/secret"},
        )
        self.assertEqual(snapshot["query_cache"], {"entries": 2, "limit": 160, "weight": 120, "weight_limit": 6000, "oversized": 1, "uncacheable": 3, "hits": 4, "saturated": True, "snapshot": {"ttl_ms": 750, "age_ms": 12, "hits": 2, "misses": 0}})
        self.assertNotIn("token", str(snapshot))
        self.assertEqual(len(snapshot["search_index"]["mode"]), 32)
        self.assertNotIn("private", str(snapshot))

    def test_snapshot_bounds_cache_hit_rate_without_coercion(self):
        snapshot = library_component(None, query_cache={"hit_rate": 2.5})
        self.assertEqual(snapshot["query_cache"]["hit_rate"], 1.0)
        class Explosive:
            def __float__(self):
                raise AssertionError("must not coerce arbitrary hit rate")
        snapshot = library_component(None, query_cache={"hit_rate": Explosive()})
        self.assertNotIn("hit_rate", snapshot["query_cache"])

    def test_snapshot_does_not_stringify_arbitrary_search_mode_objects(self):
        class ExplodingString:
            def __str__(self):
                raise AssertionError("must not stringify")

        snapshot = library_component(None, search_index={"mode": ExplodingString()})
        self.assertEqual(snapshot["search_index"]["mode"], "like")

    def test_snapshot_exposes_bounded_cache_failure_counters(self):
        snapshot = library_component(None, cache_failures={"load": 4, "save": "9", "private": "/secret"})
        self.assertEqual(snapshot["cache_failures"], {"load": 4, "save": 9})
        self.assertNotIn("private", str(snapshot))

    def test_snapshot_exposes_only_bounded_sqlite_storage_pressure(self):
        snapshot = library_component(None, storage={
            "database_bytes": 100, "wal_bytes": "20", "shm_bytes": 3,
            "total_bytes": 123, "path": "/secret/library.sqlite3",
        })
        self.assertEqual(snapshot["storage"], {"database_bytes": 100, "wal_bytes": 20, "shm_bytes": 3, "total_bytes": 123})
        self.assertNotIn("secret", str(snapshot))

    def test_snapshot_rejects_untrusted_cache_failure_values(self):
        class Explosive:
            def __int__(self):
                raise AssertionError("must not coerce")
        snapshot = library_component(None, cache_failures={"load": Explosive(), "save": True})
        self.assertEqual(snapshot["cache_failures"], {"load": 0, "save": 0})


if __name__ == "__main__":
    unittest.main()

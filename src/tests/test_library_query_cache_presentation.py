import unittest

import sys

sys.path.insert(0, "app/server")

from library_query_cache_presentation import hit_rate, project_snapshot_counters


class LibraryQueryCachePresentationTests(unittest.TestCase):
    def test_hit_rate_is_bounded_and_safe(self):
        self.assertEqual(hit_rate(3, 1), 0.75)
        self.assertEqual(hit_rate(float("nan"), 1), 0.0)
        self.assertEqual(hit_rate(True, 1), 0.0)

    def test_snapshot_projection_normalizes_nested_counters(self):
        payload = {
            "hits": 4,
            "misses": float("inf"),
            "snapshot": {"ttl_ms": -4, "age_ms": 2**100},
        }
        self.assertIs(project_snapshot_counters(payload), payload)
        self.assertEqual(payload["hits"], 4)
        self.assertEqual(payload["misses"], 0)
        self.assertEqual(payload["snapshot"]["ttl_ms"], 0)


if __name__ == "__main__":
    unittest.main()

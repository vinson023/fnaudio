import sys
import unittest

sys.path.insert(0, "app/server")

from observability_snapshot import build_observability_snapshot


class ObservabilitySnapshotTests(unittest.TestCase):
    def test_snapshot_preserves_counter_and_latency_contract(self):
        snapshot = build_observability_snapshot(
            {"http_requests_total": 3, "private": object()},
            {"library_page": {"count": 2, "total_ms": 125.0, "max_ms": 100.0, "slow": 1}},
        )
        self.assertEqual(snapshot["http_requests_total"], 3)
        self.assertEqual(snapshot["http_latency"]["library_page"], {"count": 2, "avg_ms": 62.5, "max_ms": 100.0, "slow": 1})
        self.assertEqual(snapshot["private"], 0)

    def test_snapshot_isolates_broken_metric_mappings_and_values(self):
        class BrokenDict(dict):
            def items(self):
                raise RuntimeError("broken items")

            def get(self, key, default=None):
                raise RuntimeError("broken get")

        snapshot = build_observability_snapshot(BrokenDict(), {"library_page": BrokenDict()})
        self.assertEqual(snapshot["http_latency"]["library_page"], {"count": 0, "avg_ms": 0.0, "max_ms": 0.0, "slow": 0})

    def test_snapshot_bounds_counter_key_text(self):
        snapshot = build_observability_snapshot(
            {"": 1, "x" * 257: 2, "ok": 3},
            {},
        )
        self.assertNotIn("", snapshot)
        self.assertNotIn("x" * 257, snapshot)
        self.assertEqual(snapshot["ok"], 3)

if __name__ == "__main__":
    unittest.main()

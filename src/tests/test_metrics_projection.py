import sys
import unittest

sys.path.insert(0, "app/server")

from metrics_projection import project_metrics


class MetricsProjectionTests(unittest.TestCase):
    def test_projects_nested_values_without_stringifying_objects(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("metrics must not stringify arbitrary objects")

        projected = project_metrics({"ok": {"text": "x" * 5000, "bad": Explosive()}})
        self.assertEqual(len(projected["ok"]["text"]), 4096)
        self.assertEqual(projected["ok"]["bad"], "[UNAVAILABLE]")

    def test_rejects_invalid_keys_and_non_mapping_sources(self):
        projected = project_metrics({"": 1, "x" * 257: 2, "ok": 3})
        self.assertEqual(projected, {"ok": 3})
        self.assertEqual(project_metrics([]), {})


if __name__ == "__main__":
    unittest.main()

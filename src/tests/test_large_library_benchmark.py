import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "tools")))

from benchmark_large_library import run_benchmark


class LargeLibraryBenchmarkTests(unittest.TestCase):
    def test_benchmark_enforces_bounded_sqlite_pagination(self):
        with tempfile.TemporaryDirectory() as root:
            result = run_benchmark(root, track_count=2500, page_size=120)
        self.assertTrue(result["bounded_pagination"])
        self.assertEqual(result["tracks"], 2500)
        self.assertEqual([page["returned"] for page in result["pages"]], [120, 120, 120])
        self.assertTrue(all(page["count"] == 2500 for page in result["pages"]))
        self.assertLess(result["query_peak_python_bytes"], 64 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()

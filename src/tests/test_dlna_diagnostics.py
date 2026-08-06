import sys
import unittest

sys.path.insert(0, "app/server")

from dlna.diagnostics import DlnaDiagnostics


class DlnaDiagnosticsTests(unittest.TestCase):
    def test_keeps_a_bounded_reverse_chronological_snapshot(self):
        diagnostics = DlnaDiagnostics(limit=2)
        diagnostics.record("description", user_agent="Controller A")
        diagnostics.record("media", user_agent="Controller B", range="bytes=0-")
        diagnostics.record("soap", user_agent="Controller A")
        snapshot = diagnostics.snapshot()
        self.assertEqual(snapshot["count"], 2)
        self.assertEqual(snapshot["entries"][0]["event"], "soap")
        self.assertEqual(snapshot["entries"][1]["event"], "media")
        self.assertEqual(snapshot["clients"]["Controller A"], 1)
        self.assertEqual(snapshot["clients"]["Controller B"], 1)


if __name__ == "__main__":
    unittest.main()

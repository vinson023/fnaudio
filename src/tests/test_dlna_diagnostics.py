import sys
import unittest

sys.path.insert(0, "app/server")

from dlna.diagnostics import DlnaDiagnostics, MAX_DIAGNOSTIC_ENTRIES


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

    def test_record_ignores_untrusted_values_without_stringifying(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("diagnostics must not stringify arbitrary objects")

        diagnostics = DlnaDiagnostics(limit=2)
        diagnostics.record(Explosive(), user_agent=Explosive(), range="ok")
        entry = diagnostics.snapshot()["entries"][0]
        self.assertEqual(entry["event"], "")
        self.assertNotIn("user_agent", entry)
        self.assertEqual(entry["range"], "ok")

    def test_limit_is_bounded_without_coercing_untrusted_values(self):
        class Explosive:
            def __int__(self):
                raise AssertionError("diagnostic limit must not be coerced")

        self.assertEqual(DlnaDiagnostics(10**12).snapshot()["limit"], MAX_DIAGNOSTIC_ENTRIES)
        self.assertEqual(DlnaDiagnostics(Explosive()).snapshot()["limit"], 200)


if __name__ == "__main__":
    unittest.main()

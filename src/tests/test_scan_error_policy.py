import sys
import unittest

sys.path.insert(0, "app/server")

from scan_error_policy import MAX_SCAN_ERRORS, MAX_SCAN_ERROR_TEXT, append_scan_error, scan_error_text, snapshot_scan_errors


class ScanErrorPolicyTests(unittest.TestCase):
    def test_errors_keep_only_newest_bounded_text_records(self):
        errors = []
        for index in range(MAX_SCAN_ERRORS + 3):
            append_scan_error(errors, "p%d" % index + ("x" * MAX_SCAN_ERROR_TEXT), "m" * (MAX_SCAN_ERROR_TEXT + 1))
        self.assertEqual(len(errors), MAX_SCAN_ERRORS)
        self.assertTrue(errors[0]["path"].startswith("p3"))
        self.assertEqual(len(errors[-1]["message"]), MAX_SCAN_ERROR_TEXT)

    def test_non_text_values_do_not_invoke_string_conversion(self):
        class ExplodingString:
            def __str__(self):
                raise AssertionError("must not stringify")

        errors = append_scan_error([], ExplodingString(), ExplodingString())
        self.assertEqual(errors, [{"path": "", "message": ""}])

    def test_error_text_projection_is_bounded_and_safe(self):
        class ExplodingString:
            def __str__(self):
                raise AssertionError("must not stringify")
        self.assertEqual(scan_error_text(ExplodingString()), "")
        self.assertEqual(len(scan_error_text("x" * 1000)), MAX_SCAN_ERROR_TEXT)

    def test_snapshot_is_bounded_and_isolates_broken_iterables(self):
        class Broken(list):
            def __iter__(self):
                yield {"path": "ok", "message": "fine"}
                raise RuntimeError("broken")

        self.assertEqual(snapshot_scan_errors(Broken()), [{"path": "ok", "message": "fine"}])
        self.assertEqual(snapshot_scan_errors(object()), [])


if __name__ == "__main__":
    unittest.main()

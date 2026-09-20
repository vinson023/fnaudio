import sys
import unittest
sys.path.insert(0, "app/server")
from process_error_policy import MAX_PROCESS_ERROR_TEXT, process_error_text

class ProcessErrorPolicyTests(unittest.TestCase):
    def test_text_is_trimmed_and_bounded(self):
        self.assertEqual(process_error_text("  failed  "), "failed")
        self.assertEqual(len(process_error_text("x" * (MAX_PROCESS_ERROR_TEXT + 20))), MAX_PROCESS_ERROR_TEXT)

    def test_non_text_and_empty_values_use_safe_fallback(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("must not stringify arbitrary errors")
        self.assertEqual(process_error_text(Explosive()), "process operation failed")
        self.assertEqual(process_error_text("", default=None), "process operation failed")
        self.assertEqual(process_error_text(RuntimeError("launch failed")), "launch failed")
        self.assertEqual(process_error_text("x" * 600, default=""), "x" * MAX_PROCESS_ERROR_TEXT)

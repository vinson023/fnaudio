import sys
import unittest

sys.path.insert(0, "app/server")
from scan_numeric_policy import MAX_SCAN_COUNTER, safe_counter, safe_float, safe_int


class ScanNumericPolicyTests(unittest.TestCase):
    def test_accepts_finite_numbers_and_rejects_non_finite(self):
        self.assertEqual(safe_float(1.25), 1.25)
        self.assertEqual(safe_float(float("nan")), 0.0)
        self.assertEqual(safe_float(float("inf"), 2.0), 2.0)
        self.assertEqual(safe_int(3.9), 3)
        self.assertEqual(safe_int(float("-inf"), 7), 7)

    def test_does_not_coerce_custom_objects_or_booleans(self):
        class Explosive:
            def __int__(self):
                raise AssertionError("must not coerce")
            def __float__(self):
                raise AssertionError("must not coerce")

        self.assertEqual(safe_float(Explosive(), 4.0), 4.0)
        self.assertEqual(safe_int(Explosive(), 5), 5)
        self.assertEqual(safe_int(True, 6), 6)

    def test_counter_is_non_negative_and_bounded(self):
        self.assertEqual(safe_counter(-3), 0)
        self.assertEqual(safe_counter(MAX_SCAN_COUNTER + 1), MAX_SCAN_COUNTER)
        self.assertEqual(safe_counter(True, 6), 6)
        self.assertEqual(safe_counter(9, maximum=3), 3)

    def test_extremely_long_numeric_text_falls_back_safely(self):
        self.assertEqual(safe_int("9" * 5000, 12), 12)
        self.assertEqual(safe_counter("9" * 5000, 13), 13)

    def test_extremely_large_numeric_objects_fall_back_safely(self):
        huge = 10 ** 10000
        self.assertEqual(safe_float(huge, 4.0), 4.0)
        self.assertEqual(safe_int(huge, 5), 5)
        self.assertEqual(safe_counter(huge, 6), 6)


if __name__ == "__main__":
    unittest.main()

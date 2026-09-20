import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "server"))
from metadata_numeric_policy import bounded_epoch, finite_confidence, strict_nonnegative_int


class MetadataNumericPolicyTests(unittest.TestCase):
    def test_accepts_scalar_json_values_and_rejects_bad_numbers(self):
        self.assertEqual(finite_confidence("0.75"), 0.75)
        self.assertEqual(finite_confidence(1), 1.0)
        self.assertEqual(finite_confidence(float("nan")), 0.0)
        self.assertEqual(finite_confidence(float("inf")), 0.0)
        self.assertEqual(finite_confidence(True), 0.0)

    def test_does_not_invoke_custom_numeric_conversion(self):
        class Explosive:
            def __float__(self):
                raise AssertionError("must not coerce arbitrary objects")

        self.assertEqual(finite_confidence(Explosive()), 0.0)

    def test_bounded_epoch_rejects_invalid_and_negative_values(self):
        self.assertEqual(bounded_epoch("12.8"), 12)
        self.assertEqual(bounded_epoch(-3), 0)
        self.assertEqual(bounded_epoch(float("nan")), 0)
        self.assertEqual(bounded_epoch(True), 0)

    def test_strict_nonnegative_int_rejects_coercion_and_bounds_input(self):
        self.assertEqual(strict_nonnegative_int(0), 0)
        self.assertEqual(strict_nonnegative_int("12"), 12)
        self.assertIsNone(strict_nonnegative_int(1.5))
        self.assertIsNone(strict_nonnegative_int(True))
        self.assertIsNone(strict_nonnegative_int(""))
        self.assertIsNone(strict_nonnegative_int("１２"))
        self.assertIsNone(strict_nonnegative_int(1000001))

    def test_strict_nonnegative_int_does_not_coerce_custom_objects(self):
        class Explosive:
            def __int__(self):
                raise AssertionError("must not coerce arbitrary objects")

        self.assertIsNone(strict_nonnegative_int(Explosive()))


if __name__ == "__main__":
    unittest.main()

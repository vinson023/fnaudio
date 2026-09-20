import sys
import unittest

sys.path.insert(0, "app/server")

from metadata_track_id_policy import MAX_TRACK_ID_LENGTH, normalize_track_id


class MetadataTrackIdPolicyTests(unittest.TestCase):
    def test_normalizes_bounded_text_and_integer_compatibility(self):
        self.assertEqual(normalize_track_id("  track-1 "), "track-1")
        self.assertEqual(normalize_track_id(42), "42")
        self.assertEqual(normalize_track_id("x" * MAX_TRACK_ID_LENGTH), "x" * MAX_TRACK_ID_LENGTH)

    def test_rejects_untrusted_types_and_oversized_values(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("must not stringify")

        self.assertEqual(normalize_track_id(Explosive()), "")
        self.assertEqual(normalize_track_id(True), "")
        self.assertEqual(normalize_track_id("x" * (MAX_TRACK_ID_LENGTH + 1)), "")
        self.assertEqual(normalize_track_id(None), "")

    def test_honors_a_smaller_explicit_limit_without_raising_global_budget(self):
        self.assertEqual(normalize_track_id("abc", 3), "abc")
        self.assertEqual(normalize_track_id("abcd", 3), "")
        self.assertEqual(normalize_track_id("x" * MAX_TRACK_ID_LENGTH, MAX_TRACK_ID_LENGTH + 100), "x" * MAX_TRACK_ID_LENGTH)


if __name__ == "__main__":
    unittest.main()

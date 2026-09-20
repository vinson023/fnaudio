import sys
import unittest

sys.path.insert(0, "app/server")

from state_count_policy import (
    CHILD_INTEGRITY_VERIFIED,
    MAX_PERSISTED_COUNT,
    child_integrity_is_recorded,
    children_are_within_budget,
    normalize_count,
)


class StateCountPolicyTests(unittest.TestCase):
    def test_persisted_counts_are_read_without_trusting_the_row(self):
        self.assertEqual(normalize_count(0), 0)
        self.assertEqual(normalize_count(4), 4)
        # SQLite returns TEXT for anything a damaged writer stored, and an
        # integer column can still hold a numeric string.
        self.assertEqual(normalize_count("7"), 7)
        self.assertEqual(normalize_count(MAX_PERSISTED_COUNT), MAX_PERSISTED_COUNT)

    def test_unusable_counts_read_as_unknown_rather_than_as_a_number(self):
        for value in (None, True, False, 1.5, -1, "", "gone", MAX_PERSISTED_COUNT + 1, [], {}, b"3"):
            self.assertIsNone(normalize_count(value), "normalize_count accepted %r" % (value,))

    def test_the_missing_count_never_means_an_empty_playlist(self):
        # A database created before the column exists reads back None.  Treating
        # that as 0 would let the next save believe the whole library was empty.
        self.assertIsNone(normalize_count(None))
        self.assertFalse(children_are_within_budget([3, None, 3], 4, 7))

    def test_marker_row_is_read_without_trusting_its_shape(self):
        self.assertTrue(child_integrity_is_recorded({"value": CHILD_INTEGRITY_VERIFIED}))
        self.assertTrue(child_integrity_is_recorded({"value": "1", "key": "x"}))
        for row in (None, {}, {"value": 1}, {"value": "0"}, {"value": ""}, [], {"value": None}):
            self.assertFalse(child_integrity_is_recorded(row), "marker accepted %r" % (row,))

    def test_playlist_cap_is_inclusive(self):
        self.assertTrue(children_are_within_budget([4, 4], 4, 50))
        self.assertFalse(children_are_within_budget([5], 4, 50))

    def test_total_cap_is_cumulative_and_inclusive(self):
        self.assertTrue(children_are_within_budget([3, 4], 50, 7))
        self.assertFalse(children_are_within_budget([3, 5], 50, 7))
        self.assertFalse(children_are_within_budget([4, 4, 4], 50, 7))

    def test_a_keep_set_with_nothing_to_keep_needs_no_trim(self):
        self.assertTrue(children_are_within_budget([], 4, 7))

    def test_unusable_caps_cannot_be_trusted_into_a_fast_path(self):
        for caps in ((None, 7), (4, None), (4, -1), (True, 7), (4, True), (4.0, 7), ("4", 7)):
            self.assertFalse(
                children_are_within_budget([1], caps[0], caps[1]),
                "budget accepted caps %r" % (caps,),
            )

    def test_a_generator_of_counts_is_consumed_only_once(self):
        # The caller hands over a list built from the rows it already read; the
        # predicate must not need it twice, or the fast path would re-scan.
        self.assertTrue(children_are_within_budget(iter([3, 4]), 4, 7))


if __name__ == "__main__":
    unittest.main()

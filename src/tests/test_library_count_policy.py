import sys
import unittest

sys.path.insert(0, "app/server")

from library_count_policy import (
    GROUP_COUNT_KEYS,
    MAX_SAVED_COUNT,
    browse_page_total,
    group_count_key,
    project_saved_count,
    saved_count_key,
)


class LibraryCountPolicyTests(unittest.TestCase):
    def test_unfiltered_hot_views_use_saved_summary_keys(self):
        self.assertEqual(saved_count_key("all", "", ""), "track_count")
        self.assertEqual(saved_count_key("recent", "", ""), "track_count")
        self.assertEqual(saved_count_key("random100", "", ""), "track_count")
        self.assertEqual(saved_count_key("dsd", "", ""), "dsd_count")

    def test_filtered_or_grouped_views_fall_back_to_live_count(self):
        self.assertIsNone(saved_count_key("all", "jay", ""))
        self.assertEqual(saved_count_key("dsd", "", " WHERE is_dsd = 1"), "dsd_count")
        self.assertIsNone(saved_count_key("dsd", "term", " WHERE is_dsd = 1"))
        self.assertIsNone(saved_count_key("albums", "", ""))

    def test_count_policy_does_not_coerce_untrusted_inputs(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("count policy must not stringify")

        self.assertIsNone(saved_count_key(Explosive(), "", ""))
        self.assertIsNone(saved_count_key("all", Explosive(), ""))

    def test_project_saved_count_bounds_and_isolates_broken_rows(self):
        class BrokenRow:
            def __getitem__(self, key):
                raise RuntimeError("broken row")

        self.assertIsNone(project_saved_count(BrokenRow()))
        self.assertIsNone(project_saved_count({"value": True}))
        self.assertIsNone(project_saved_count({"value": MAX_SAVED_COUNT + 1}))
        self.assertEqual(project_saved_count({"value": "12"}), 12)

    def test_unfiltered_group_views_use_their_own_persisted_keys(self):
        self.assertEqual(group_count_key("albums", ""), "group_count_albums")
        self.assertEqual(group_count_key("artists", ""), "group_count_artists")
        self.assertEqual(group_count_key("composers", ""), "group_count_composers")
        self.assertEqual(group_count_key("genres", ""), "group_count_genres")
        self.assertEqual(len(GROUP_COUNT_KEYS), 4)

    def test_narrowed_group_views_never_use_a_persisted_total(self):
        # A search page counts a JOIN, not the whole table, so reusing the
        # table total would report a number no row on the page can support.
        self.assertIsNone(group_count_key("albums", "jay"))
        self.assertIsNone(group_count_key("albums", "   "))
        self.assertIsNone(group_count_key("tracks", ""))
        self.assertIsNone(group_count_key("", ""))
        self.assertIsNone(group_count_key(None, ""))
        self.assertIsNone(group_count_key("albums", None))

    def test_a_short_group_page_proves_the_exact_total_and_repairs_a_large_count(self):
        # Reaching the end of the table with rows left over is proof enough:
        # the rows seen are the whole table, so a count that drifted high gets
        # replaced rather than believed.
        self.assertEqual(browse_page_total(99, 0, 2, 50), (2, False))
        self.assertEqual(browse_page_total(99, 98, 1, 50), (99, False))
        self.assertEqual(browse_page_total(99, 0, 5, 5), (5, False))

    def test_a_full_group_page_only_repairs_a_count_that_drifted_small(self):
        # A full look-ahead row proves the table is bigger than the page but
        # says nothing about how much bigger, so a count above it survives.
        self.assertEqual(browse_page_total(100, 0, 51, 50), (100, False))
        self.assertEqual(browse_page_total(10, 0, 11, 10), (None, True))
        self.assertEqual(browse_page_total(4, 0, 51, 50), (None, True))

    def test_a_group_page_refuses_an_unusable_persisted_count(self):
        self.assertEqual(browse_page_total(5, 0, 0, 50), (None, True))
        self.assertEqual(browse_page_total(5, 0, 52, 50), (None, True))
        self.assertEqual(browse_page_total(MAX_SAVED_COUNT + 1, 0, 2, 50), (None, True))
        for saved in (None, True, "12", -1, 1.0):
            self.assertEqual(browse_page_total(saved, 0, 2, 50), (None, True))
        for value in (None, True, -1, 1.5):
            self.assertEqual(browse_page_total(5, value, 2, 50), (None, True))
            self.assertEqual(browse_page_total(5, 0, value, 50), (None, True))
            self.assertEqual(browse_page_total(5, 0, 2, value), (None, True))


if __name__ == "__main__":
    unittest.main()

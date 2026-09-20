import sys
import unittest

sys.path.insert(0, "app/server")
from library_group_policy import MAX_GROUP_VALUE_TEXT, group_match_condition


class LibraryGroupPolicyTests(unittest.TestCase):
    def test_unclassified_matches_blank_and_null(self):
        condition, args = group_match_condition("t.album", "未分类")
        self.assertIn("t.album IS NULL", condition)
        self.assertEqual(args, ["未分类"])

    def test_unknown_columns_are_rejected_without_coercion(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("must not stringify")
        with self.assertRaises(ValueError):
            group_match_condition(Explosive(), "album")

    def test_group_value_is_bounded_before_becoming_a_sql_parameter(self):
        condition, args = group_match_condition("album", "x" * (MAX_GROUP_VALUE_TEXT + 100))
        self.assertEqual(condition, "album = ?")
        self.assertEqual(args, ["x" * MAX_GROUP_VALUE_TEXT])

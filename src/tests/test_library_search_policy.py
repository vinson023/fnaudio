import sys
import unittest

sys.path.insert(0, "app/server")
from library_search_policy import track_search_condition

class LibrarySearchPolicyTests(unittest.TestCase):
    def test_like_search_keeps_columns_and_parameters(self):
        condition, args = track_search_condition("  Hello ", "t")
        self.assertIn("t.title", condition)
        self.assertEqual(len(args), 9)
        self.assertEqual(args[0], "%hello%")

    def test_fts_escapes_quotes_and_rejects_objects(self):
        condition, args = track_search_condition('a"b', use_fts=True)
        self.assertIn("tracks_search MATCH", condition)
        self.assertEqual(args, ['"a""b"'])
        self.assertEqual(track_search_condition(object()), ("", []))

    def test_direct_search_input_is_bounded(self):
        condition, args = track_search_condition("x" * 10000)
        self.assertEqual(len(args[0]), 4098)
        self.assertNotIn("x" * 4097, args[0])

    def test_sql_identifiers_are_bounded(self):
        condition, _ = track_search_condition("song", "t" * 1000, use_fts=True, rowid_column="r" * 1000)
        self.assertLessEqual(len(condition), 300)

    def test_sql_identifiers_reject_injection_characters(self):
        condition, _ = track_search_condition("song", "t;DROP", use_fts=True, rowid_column="t.rowid OR 1=1")
        self.assertIn("rowid IN", condition)
        self.assertNotIn("DROP", condition)

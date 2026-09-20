import json
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, "app/server")

from library_cursor_policy import decode_track_cursor
from library_page_result_policy import decode_track_cursor_page_rows, track_page_result, track_page_select
from library_rows import MAX_ITEM_JSON_BYTES


class LibraryPageResultPolicyTests(unittest.TestCase):
    def test_decoder_skips_bad_rows_and_keeps_last_database_anchor(self):
        rows = [
            {"item_json": json.dumps({"id": "one"}), "_cursor_primary": 1, "_cursor_title": "One", "_cursor_id": "one"},
            {"item_json": "not-json", "_cursor_primary": 2, "_cursor_title": "Bad", "_cursor_id": "bad"},
            {"item_json": "x" * MAX_ITEM_JSON_BYTES, "_cursor_primary": 3, "_cursor_title": "Large", "_cursor_id": "large"},
            {"item_json": json.dumps({"id": "two"}), "_cursor_primary": 4, "_cursor_title": "Two", "_cursor_id": "two"},
        ]
        items, anchor, has_more = decode_track_cursor_page_rows(rows, 4)
        self.assertEqual(items, [{"id": "one"}, {"id": "two"}])
        self.assertEqual(anchor, {"primary": 4, "title": "Two", "id": "two"})
        self.assertFalse(has_more)
        self.assertEqual(decode_track_cursor_page_rows(None, 2), ([], None, False))

    def test_the_page_decoder_rejects_multibyte_json_over_the_shared_byte_limit(self):
        prefix = "{\"title\":\""
        suffix = "\"}"
        payload = prefix + ("音" * (MAX_ITEM_JSON_BYTES // 2 - len(prefix) - len(suffix))) + suffix
        row = {"item_json": payload, "_cursor_primary": 1, "_cursor_title": "bad", "_cursor_id": "bad"}
        self.assertEqual(decode_track_cursor_page_rows([row], 1), ([], None, False))

    def test_select_has_optional_window_total(self):
        query = SimpleNamespace(sql_order="added_ns ASC")
        self.assertIn("_cursor_primary", track_page_select(query))
        self.assertIn("COUNT(*) OVER() AS total_count", track_page_select(query, window=True))

    def test_cursor_decoder_keeps_displayed_last_row_as_anchor(self):
        rows = [
            {"item_json": json.dumps({"id": "one"}), "_cursor_primary": 1, "_cursor_title": "One", "_cursor_id": "one"},
            {"item_json": json.dumps({"id": "two"}), "_cursor_primary": 2, "_cursor_title": "Two", "_cursor_id": "two"},
        ]
        items, anchor, has_more = decode_track_cursor_page_rows(rows, 1)
        self.assertEqual(items, [{"id": "one"}])
        self.assertEqual(anchor, {"primary": 1, "title": "One", "id": "one"})
        self.assertTrue(has_more)

    def test_cursor_decoder_uses_a_bounded_fallback_for_untrusted_limits(self):
        rows = [{"item_json": json.dumps({"id": "one"}), "_cursor_primary": 1, "_cursor_title": "One", "_cursor_id": "one"}]
        self.assertEqual(decode_track_cursor_page_rows(rows, "1.5")[0], [{"id": "one"}])
        self.assertEqual(decode_track_cursor_page_rows(rows, True)[0], [{"id": "one"}])

        class Explosive:
            def __int__(self):
                raise AssertionError("limit must not be coerced")

        self.assertEqual(decode_track_cursor_page_rows(rows, Explosive())[0], [{"id": "one"}])

    def test_result_uses_sql_anchor_and_bounded_sort_normalization(self):
        query = SimpleNamespace(sort_key="track_no", sort_dir="asc", sql_order="track_no ASC")
        result = track_page_result(
            [{"id": "one", "title": "display title", "track_no": "bad"}],
            3,
            1,
            0,
            query,
            {"primary": 7, "title": "SQL title", "id": "sql-id"},
        )
        cursor = decode_track_cursor(result["next_cursor"])
        self.assertEqual(cursor["primary"], 7)
        self.assertEqual(cursor["title"], "SQL title")
        self.assertEqual(cursor["id"], "sql-id")
        self.assertTrue(result["has_more"])

    def test_result_marks_short_page_complete_and_omits_invalid_cursor(self):
        query = SimpleNamespace(sort_key="title", sort_dir="asc", sql_order="title COLLATE NOCASE ASC")
        short = track_page_result([{"id": "one", "title": "One"}], 2, 2, 0, query)
        self.assertFalse(short["has_more"])
        invalid = track_page_result([{"id": "one"}], 1, 1, 0, query)
        self.assertNotIn("next_cursor", invalid)

    def test_a_null_anchor_continues_from_its_look_ahead_row(self):
        # A legacy library keeps SQL NULL for an untagged row, and no comparison
        # predicate can express NULL, so the page anchors on the row after the NULL
        # group instead. That row has not been served, hence the inclusive flag.
        rows = [
            {"item_json": json.dumps({"id": "one"}), "_cursor_primary": None, "_cursor_title": None, "_cursor_id": "one"},
            {"item_json": json.dumps({"id": "two"}), "_cursor_primary": "Adele", "_cursor_title": "Two", "_cursor_id": "two"},
        ]
        items, anchor, has_more = decode_track_cursor_page_rows(rows, 1)
        self.assertEqual(items, [{"id": "one"}])
        self.assertTrue(has_more)
        self.assertEqual(anchor, {"primary": "Adele", "title": "Two", "id": "two", "inclusive": True})
        query = SimpleNamespace(sort_key="artist", sort_dir="asc", sql_order="artist COLLATE NOCASE ASC")
        result = track_page_result(items, 100, 1, 0, query, anchor, has_more)
        cursor = decode_track_cursor(result["next_cursor"])
        self.assertTrue(cursor["inclusive"])
        self.assertEqual((cursor["primary"], cursor["title"], cursor["id"]), ("Adele", "Two", "two"))

    def test_a_usable_anchor_is_never_replaced_by_the_look_ahead_row(self):
        # The substitution exists to rescue a page that cannot name its own last
        # row. Where the served row can anchor, the look-ahead row has already been
        # displayed as nothing, and re-serving it would duplicate a track.
        rows = [
            {"item_json": json.dumps({"id": "one"}), "_cursor_primary": "Adele", "_cursor_title": "One", "_cursor_id": "one"},
            {"item_json": json.dumps({"id": "two"}), "_cursor_primary": "Adele", "_cursor_title": "Two", "_cursor_id": "two"},
        ]
        items, anchor, has_more = decode_track_cursor_page_rows(rows, 1)
        self.assertEqual(anchor, {"primary": "Adele", "title": "One", "id": "one"})
        self.assertNotIn("inclusive", anchor)
        query = SimpleNamespace(sort_key="artist", sort_dir="asc", sql_order="artist COLLATE NOCASE ASC")
        result = track_page_result(items, 100, 1, 0, query, anchor, has_more)
        self.assertFalse(decode_track_cursor(result["next_cursor"])["inclusive"])

    def test_a_look_ahead_row_inside_the_same_null_group_gives_no_cursor(self):
        # NULL values sort as one contiguous block, so a NULL look-ahead row means
        # the group is not finished. Continuing past it would drop its remaining
        # rows, which is worse than the offset fallback this page still gets.
        rows = [
            {"item_json": json.dumps({"id": "one"}), "_cursor_primary": None, "_cursor_title": None, "_cursor_id": "one"},
            {"item_json": json.dumps({"id": "two"}), "_cursor_primary": None, "_cursor_title": None, "_cursor_id": "two"},
        ]
        items, anchor, has_more = decode_track_cursor_page_rows(rows, 1)
        self.assertTrue(has_more)
        self.assertEqual(anchor, {"primary": None, "title": None, "id": "one"})
        query = SimpleNamespace(sort_key="artist", sort_dir="asc", sql_order="artist COLLATE NOCASE ASC")
        result = track_page_result(items, 100, 1, 0, query, anchor, has_more)
        self.assertTrue(result["has_more"])
        self.assertNotIn("next_cursor", result)

    def test_a_look_ahead_row_without_cursor_columns_is_not_an_anchor(self):
        # The projection is shared with callers that do not ask for a key, so a
        # missing column must leave the old answer in place instead of raising.
        rows = [
            {"item_json": json.dumps({"id": "one"}), "_cursor_primary": None, "_cursor_title": None, "_cursor_id": "one"},
            {"item_json": json.dumps({"id": "two"})},
        ]
        items, anchor, has_more = decode_track_cursor_page_rows(rows, 1)
        self.assertTrue(has_more)
        self.assertEqual(anchor, {"primary": None, "title": None, "id": "one"})

    def test_an_offset_page_can_anchor_an_empty_id_but_never_inclusively(self):
        # An offset page has no look-ahead row, so whatever it anchors on has been
        # served and must be excluded. The empty id is still a real key.
        query = SimpleNamespace(sort_key="artist", sort_dir="asc", sql_order="artist COLLATE NOCASE ASC")
        result = track_page_result([{"id": "", "artist": "Adele", "title": "One"}], 3, 1, 0, query)
        cursor = decode_track_cursor(result["next_cursor"])
        self.assertEqual(cursor["id"], "")
        self.assertFalse(cursor["inclusive"])

    def test_explicit_continuation_decision_overrides_total_count(self):
        query = SimpleNamespace(sort_key="title", sort_dir="asc", sql_order="title COLLATE NOCASE ASC")
        result = track_page_result(
            [{"id": "one", "title": "One"}], 100, 1, 0, query,
            {"primary": "One", "title": "One", "id": "one"}, False,
        )
        self.assertFalse(result["has_more"])
        self.assertNotIn("next_cursor", result)


if __name__ == "__main__":
    unittest.main()

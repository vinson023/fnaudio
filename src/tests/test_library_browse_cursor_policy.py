import sys
import unittest

sys.path.insert(0, "app/server")

from library_browse_cursor_policy import (
    browse_cursor_group_tail_where,
    browse_cursor_next_group_where,
    browse_cursor_page,
    decode_browse_cursor,
    encode_browse_cursor,
)

NAME = "name COLLATE NOCASE"


def cursor(kind="group", sort_dir="asc", name="B", tie="B"):
    return decode_browse_cursor(encode_browse_cursor(kind, sort_dir, name, tie))


class LibraryBrowseCursorPolicyTests(unittest.TestCase):
    def test_round_trip_keeps_kind_direction_and_tie(self):
        token = encode_browse_cursor("folder", "desc", "Album", "/music/Album")
        self.assertEqual(
            decode_browse_cursor(token),
            {"kind": "folder", "sort_dir": "desc", "name": "Album", "tie": "/music/Album"},
        )

    def test_the_pair_reads_the_cursor_group_tail_then_the_following_groups(self):
        # Browse rows order by the case-insensitive name and break ties on the
        # literal name *ascending* in both directions, so the tail predicate
        # deliberately ignores sort_dir while the range predicate does not.
        for sort_dir, operator in (("asc", ">"), ("desc", "<")):
            decoded = cursor(sort_dir=sort_dir)
            self.assertEqual(
                browse_cursor_group_tail_where(decoded, "group", sort_dir, NAME, "name"),
                ("%s = ? AND name > ?" % NAME, ["B", "B"]),
                sort_dir,
            )
            self.assertEqual(
                browse_cursor_next_group_where(decoded, "group", sort_dir, NAME),
                ("%s %s ?" % (NAME, operator), ["B"]),
                sort_dir,
            )

    def test_the_folder_tie_uses_the_path_and_stays_direction_independent(self):
        for sort_dir in ("asc", "desc"):
            decoded = cursor("folder", sort_dir, "Album", "/music/Album")
            self.assertEqual(
                browse_cursor_group_tail_where(decoded, "folder", sort_dir, "f.name COLLATE NOCASE", "f.path"),
                ("f.name COLLATE NOCASE = ? AND f.path > ?", ["Album", "/music/Album"]),
                sort_dir,
            )

    def test_neither_statement_widens_into_an_or(self):
        # An OR of the two comparisons is logically identical and was the shape
        # this replaced, but SQLite cannot seek on it: it turns the page back
        # into a scan of every earlier group.
        for sort_dir in ("asc", "desc"):
            decoded = cursor(sort_dir=sort_dir)
            for predicate, _args in (
                browse_cursor_group_tail_where(decoded, "group", sort_dir, NAME, "name"),
                browse_cursor_next_group_where(decoded, "group", sort_dir, NAME),
            ):
                self.assertNotIn(" OR ", predicate, sort_dir)
                self.assertEqual(predicate.count("?"), 2 if "=" in predicate else 1, sort_dir)

    def test_the_adoption_gate_rejects_a_cursor_from_another_view_or_direction(self):
        decoded = cursor("group", "asc")
        self.assertIs(browse_cursor_page(decoded, "group", "asc"), decoded)
        self.assertIsNone(browse_cursor_page(decoded, "folder", "asc"))
        self.assertIsNone(browse_cursor_page(decoded, "group", "desc"))
        self.assertIsNone(browse_cursor_page(None, "group", "asc"))
        for guard in (
            lambda value: browse_cursor_group_tail_where(value, "group", "asc", NAME, "name"),
            lambda value: browse_cursor_next_group_where(value, "group", "asc", NAME),
        ):
            self.assertEqual(guard(browse_cursor_page(decoded, "folder", "asc")), ("", []))
            self.assertEqual(guard(browse_cursor_page(decoded, "group", "desc")), ("", []))
            self.assertEqual(guard(None), ("", []))

    def test_a_missing_tie_falls_back_to_the_name(self):
        decoded = cursor("group", "asc", "Album", "")
        self.assertEqual(decoded["tie"], "Album")
        self.assertEqual(
            browse_cursor_group_tail_where(decoded, "group", "asc", NAME, "name"),
            ("%s = ? AND name > ?" % NAME, ["Album", "Album"]),
        )

    def test_untrusted_values_are_ignored_without_coercion(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("must not stringify")

        self.assertEqual(encode_browse_cursor("group", "asc", Explosive()), "")
        self.assertIsNone(decode_browse_cursor(Explosive()))
        self.assertIsNone(decode_browse_cursor("!!!!"))


if __name__ == "__main__":
    unittest.main()

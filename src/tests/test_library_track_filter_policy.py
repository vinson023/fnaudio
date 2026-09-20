import unittest
from types import SimpleNamespace

from library_track_filter_policy import build_track_filters


class LibraryTrackFilterPolicyTests(unittest.TestCase):
    def test_builds_group_album_and_search_filters_in_order(self):
        query = SimpleNamespace(view="artists", group="A", album="Record", search="live", group_column="artist")

        def group(column, value):
            return f"{column} = ?", [value]

        def search(value, *, use_fts):
            return ("fts MATCH ?" if use_fts else "title LIKE ?"), [value]

        where, args = build_track_filters(query, search_condition=search, group_condition=group)
        self.assertEqual(where, ["artist = ?", "album = ?", "title LIKE ?"])
        self.assertEqual(args, ["A", "Record", "live"])

    def test_folder_root_and_invalid_shape_are_safe(self):
        query = SimpleNamespace(view="folders", folder="Disc 1", root="/music", search="")
        where, args = build_track_filters(query, search_condition=lambda *a, **k: ("x", []), group_condition=lambda *a: ("x", []))
        self.assertEqual(where, ["root = ?", "folder = ?"])
        self.assertEqual(args, ["/music", "Disc 1"])
        self.assertEqual(build_track_filters(None, search_condition=lambda *a, **k: ("x", []), group_condition=lambda *a: ("x", [])), ([], []))

    def test_broken_query_attributes_fall_back_without_raising(self):
        class Broken:
            @property
            def view(self):
                raise RuntimeError("broken")

        self.assertEqual(
            build_track_filters(Broken(), search_condition=lambda *a, **k: ("x", []), group_condition=lambda *a: ("x", [])),
            ([], []),
        )


if __name__ == "__main__":
    unittest.main()

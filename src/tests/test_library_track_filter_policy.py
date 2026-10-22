import unittest
from types import SimpleNamespace

from library_track_filter_policy import build_track_filters

FOLDER_CLAUSE = "(folder = ? OR (folder > ? AND folder < ?))"


def _filters(query):
    return build_track_filters(
        query,
        search_condition=lambda value, **kwargs: ("title LIKE ?", [value]),
        group_condition=lambda column, value: (f"{column} = ?", [value]),
    )


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

    def test_folder_scope_selects_the_container_and_its_subtree(self):
        # ``tracks.folder`` stores the leaf directory, so an exact ``folder = ?``
        # answered zero rows for every container that holds subdirectories.
        where, args = _filters(SimpleNamespace(view="folders", folder="Disc 1", root="/music", search=""))
        self.assertEqual(where, ["root = ?", FOLDER_CLAUSE])
        self.assertEqual(args, ["/music", "Disc 1", "Disc 1/", "Disc 10"])

    def test_folder_root_scope_lists_the_whole_root(self):
        # The old ``folder = ''`` rule for a bare root hid every nested file.
        where, args = _filters(SimpleNamespace(view="folders", folder="", root="/music", search=""))
        self.assertEqual(where, ["root = ?"])
        self.assertEqual(args, ["/music"])

    def test_folder_scope_without_root_is_not_widened_to_every_root(self):
        where, args = _filters(SimpleNamespace(view="folders", folder="Live", root="", search=""))
        self.assertEqual(where, [FOLDER_CLAUSE])
        self.assertEqual(args, ["Live", "Live/", "Live0"])

    def test_blank_folder_never_becomes_a_whole_table_predicate(self):
        for folder in ("/", "//", ".", "", None, 7):
            where, args = _filters(SimpleNamespace(view="folders", folder=folder, root="/music", search=""))
            self.assertEqual(where, ["root = ?"], folder)
            self.assertEqual(args, ["/music"], folder)

    def test_traversal_scope_stays_verbatim_instead_of_widening(self):
        where, args = _filters(SimpleNamespace(view="folders", folder="../secret", root="/music", search=""))
        self.assertEqual(where, ["root = ?", FOLDER_CLAUSE])
        self.assertEqual(args, ["/music", "../secret", "../secret/", "../secret0"])

    def test_search_is_still_combined_with_a_folder_scope(self):
        where, args = _filters(SimpleNamespace(view="folders", folder="DSD", root="/music", search="live"))
        self.assertEqual(where, ["root = ?", FOLDER_CLAUSE, "title LIKE ?"])
        self.assertEqual(args, ["/music", "DSD", "DSD/", "DSD0", "live"])

    def test_group_view_is_untouched_by_the_folder_scope(self):
        where, args = _filters(SimpleNamespace(view="albums", group="Record", album="", folder="DSD", root="/music", search="", group_column="album"))
        self.assertEqual(where, ["album = ?"])
        self.assertEqual(args, ["Record"])

    def test_dsd_view_keeps_the_dsd_predicate_in_the_common_paged_path(self):
        where, args = _filters(SimpleNamespace(view="dsd", group="", album="", folder="", root="", search=""))
        self.assertEqual(where, ["is_dsd = 1"])
        self.assertEqual(args, [])

    def test_folder_root_and_invalid_shape_are_safe(self):
        self.assertEqual(_filters(None), ([], []))

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

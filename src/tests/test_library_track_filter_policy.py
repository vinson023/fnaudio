import unittest
from types import SimpleNamespace

from library_track_filter_policy import build_track_filters

FOLDER_CLAUSE = "folder = ?"
SUBTREE_CLAUSE = "(folder = ? OR (folder > ? AND folder < ?))"


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

    def test_folder_scope_selects_only_the_opened_directory(self):
        # ``tracks.folder`` stores the leaf directory and the page shows the
        # container's subdirectories as their own rows, so the predicate is an
        # exact match -- a subtree range listed those files a second time.
        where, args = _filters(SimpleNamespace(view="folders", folder="Disc 1", root="/music", search=""))
        self.assertEqual(where, ["root = ?", FOLDER_CLAUSE])
        self.assertEqual(args, ["/music", "Disc 1"])

    def test_folder_root_scope_lists_the_files_sitting_in_the_root(self):
        # An empty scope is the root itself, where files carry ``folder = ''``.
        # Dropping the predicate instead listed every nested file as well.
        where, args = _filters(SimpleNamespace(view="folders", folder="", root="/music", search=""))
        self.assertEqual(where, ["root = ?", FOLDER_CLAUSE])
        self.assertEqual(args, ["/music", ""])

    def test_folder_scope_without_root_is_not_widened_to_every_root(self):
        where, args = _filters(SimpleNamespace(view="folders", folder="Live", root="", search=""))
        self.assertEqual(where, [FOLDER_CLAUSE])
        self.assertEqual(args, ["Live"])

    def test_blank_folder_never_becomes_a_whole_table_predicate(self):
        for folder in ("/", "//", ".", "", None, 7):
            where, args = _filters(SimpleNamespace(view="folders", folder=folder, root="/music", search=""))
            self.assertEqual(where, ["root = ?", FOLDER_CLAUSE], folder)
            self.assertEqual(args, ["/music", ""], folder)

    def test_traversal_scope_stays_verbatim_instead_of_widening(self):
        where, args = _filters(SimpleNamespace(view="folders", folder="../secret", root="/music", search=""))
        self.assertEqual(where, ["root = ?", FOLDER_CLAUSE])
        self.assertEqual(args, ["/music", "../secret"])

    def test_search_is_still_combined_with_a_folder_scope(self):
        where, args = _filters(SimpleNamespace(view="folders", folder="DSD", root="/music", search="live"))
        self.assertEqual(where, ["root = ?", FOLDER_CLAUSE, "title LIKE ?"])
        self.assertEqual(args, ["/music", "DSD", "live"])

    def test_queueing_a_folder_row_asks_for_its_subtree(self):
        # Selecting a folder row means the whole container, so that one request
        # widens back to the subtree range the page itself no longer uses.
        where, args = _filters(
            SimpleNamespace(view="folders", folder="DSD", root="/music", search="", subtree=True))
        self.assertEqual(where, ["root = ?", SUBTREE_CLAUSE])
        self.assertEqual(args, ["/music", "DSD", "DSD/", "DSD0"])

    def test_queueing_the_root_row_asks_for_the_whole_root(self):
        # An empty scope has no narrower form to widen: it is the root itself.
        where, args = _filters(
            SimpleNamespace(view="folders", folder="", root="/music", search="", subtree=True))
        self.assertEqual(where, ["root = ?"])
        self.assertEqual(args, ["/music"])

    def test_the_subtree_flag_is_ignored_by_every_other_view(self):
        where, _args = _filters(SimpleNamespace(view="all", folder="DSD", root="/music", search="", subtree=True))
        self.assertEqual(where, [])

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

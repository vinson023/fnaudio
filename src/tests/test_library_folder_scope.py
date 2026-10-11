"""Folder browse scope: one subtree rule for SQLite and memory, no memory fallback on empty scopes.

A folder row in the browser is a container and its ``track_count`` covers the
whole subtree, while ``tracks.folder`` only stores the leaf directory of a file.
Exact equality therefore answered "0 tracks" for every container that holds
subdirectories, and each of those legitimate empty results used to be re-answered
by filtering and sorting the entire library in Python -- several seconds per
click on a 60,000-track collection.  These tests pin the subtree semantics, the
agreement between the two query engines, and the closed fallback.
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, "app/server")

import library
from library import query_library_folders, query_library_page, save_items_to_sqlite
from library_folder_scope import folder_in_subtree, folder_scope, folder_subtree_clause
from library_memory_query import filter_memory_page

# '' is a file that sits directly in the library root.
FOLDER_CORPUS = [
    "",
    "DSD",
    "DSD/自然",
    "DSD/自然/天地的回声",
    "DSD/自然/天地的回声/live",
    "DSD2/album",
    "DSD!x",
    "DSD-x",
    "DSD.txt",
    "DSD0zero",
    "DS",
    "x/DSD",
    "未整理",
    "未整理/HIRES/DSD/album",
]

FOLDER_CLAUSE = "(folder = ? OR (folder > ? AND folder < ?))"


def _path_under(path, root):
    return path.startswith(root + "/") or path == root


class FolderScopeNormalizationTests(unittest.TestCase):
    def test_separator_noise_is_stripped_to_the_stored_form(self):
        # ``relative_folder_for_path()`` never stores an empty or '.' segment,
        # so a scope carrying them still addresses the same container.
        self.assertEqual(folder_scope("/DSD/"), "DSD")
        self.assertEqual(folder_scope("DSD//自然"), "DSD/自然")
        self.assertEqual(folder_scope("./DSD"), "DSD")
        self.assertEqual(folder_scope("DSD"), "DSD")

    def test_blank_and_unusable_scopes_collapse_to_empty(self):
        for value in ("", "/", "//", ".", "./", None, 7, ["DSD"], b"DSD"):
            self.assertEqual(folder_scope(value), "", repr(value))

    def test_whitespace_and_unicode_segment_names_survive(self):
        self.assertEqual(folder_scope("D 盘/ 单曲 /x"), "D 盘/ 单曲 /x")
        self.assertEqual(folder_scope("未整理/HIRES"), "未整理/HIRES")

    def test_traversal_scope_is_kept_verbatim_and_never_widened(self):
        # A '..' segment cannot exist in the index; passing it through matches
        # nothing, while dropping it would leak the whole root.
        self.assertEqual(folder_scope("../secret"), "../secret")
        self.assertEqual(folder_scope("DSD/../DSD2"), "DSD/../DSD2")

    def test_empty_scope_is_rejected_by_the_clause_builder(self):
        for value in ("", "/", "."):
            with self.assertRaises(ValueError):
                folder_subtree_clause(value)

    def test_clause_arguments_are_the_bounded_range(self):
        clause, args = folder_subtree_clause("DSD/自然")
        self.assertEqual(clause, FOLDER_CLAUSE)
        self.assertEqual(args, ["DSD/自然", "DSD/自然/", "DSD/自然0"])


class FolderPredicateParityTests(unittest.TestCase):
    """The SQLite range and the Python prefix must select exactly the same rows."""

    def _sql_ids(self, scope):
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute("CREATE TABLE tracks (id TEXT PRIMARY KEY, folder TEXT)")
            for index, folder in enumerate(FOLDER_CORPUS):
                conn.execute("INSERT INTO tracks VALUES (?, ?)", ("t%02d" % index, folder))
            clause, args = folder_subtree_clause(scope)
            rows = conn.execute("SELECT id FROM tracks WHERE %s ORDER BY id" % clause, args).fetchall()
            return sorted(row[0] for row in rows)
        finally:
            conn.close()

    def _memory_ids(self, scope):
        rows = [
            {
                "id": "t%02d" % index,
                "title": "T%02d" % index,
                "folder": folder,
                "path": "/music/" + folder + "/file.flac",
            }
            for index, folder in enumerate(FOLDER_CORPUS)
        ]
        query = SimpleNamespace(
            view="folders", group="", album="", search="", folder=scope, root="/music",
            sort_key="title", sort_dir="asc", group_column="album", limit=len(FOLDER_CORPUS), offset=0,
        )
        page, count = filter_memory_page(
            rows, query, ["/music"], "未分类", _path_under, lambda value: 0
        )
        self.assertEqual(count, len(page), scope)
        return sorted(item["id"] for item in page)

    def test_both_engines_select_the_same_rows_for_every_scope(self):
        for scope in ("DSD", "DS", "x", "未整理", "DSD/自然", "DSD.txt", "DSD2"):
            with self.subTest(scope=scope):
                expected = [
                    "t%02d" % index
                    for index, folder in enumerate(FOLDER_CORPUS)
                    if folder_in_subtree(folder, scope)
                ]
                self.assertEqual(self._sql_ids(scope), sorted(expected), scope)
                self.assertEqual(self._memory_ids(scope), sorted(expected), scope)

    def test_container_itself_and_only_real_descendants_match(self):
        self.assertEqual(
            self._sql_ids("DSD"),
            sorted(["t%02d" % FOLDER_CORPUS.index(folder) for folder in (
                "DSD", "DSD/自然", "DSD/自然/天地的回声", "DSD/自然/天地的回声/live",
            )]),
        )

    def test_sibling_directories_that_sort_next_to_the_prefix_never_leak(self):
        for sibling in ("DSD!x", "DSD-x", "DSD.txt", "DSD0zero", "DSD2/album", "DS", "x/DSD", "未整理/HIRES/DSD/album"):
            self.assertFalse(folder_in_subtree(sibling, "DSD"), sibling)
            self.assertNotIn("t%02d" % FOLDER_CORPUS.index(sibling), self._sql_ids("DSD"))

    def test_memory_predicate_treats_an_empty_scope_as_unfiltered(self):
        self.assertTrue(folder_in_subtree("DSD/自然", ""))
        self.assertTrue(folder_in_subtree("", ""))
        self.assertFalse(folder_in_subtree(None, "DSD"))


class FolderSubtreePageTests(unittest.TestCase):
    """End to end: what one click on a folder row actually asks and gets."""

    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.addCleanup(library.close_library_connections)
        self.music = os.path.join(self.root.name, "music")
        self.other = os.path.join(self.root.name, "other")
        os.makedirs(self.music, exist_ok=True)
        os.makedirs(self.other, exist_ok=True)
        self.config = {"cache_dir": os.path.join(self.root.name, "cache"), "library_paths": [self.music, self.other]}
        self.old_items = library.MUSIC_CACHE["items"]
        self.addCleanup(self._restore_memory_cache)
        # A hydrated cache is exactly the condition that used to turn a legal
        # empty scope into a full Python scan, so it stays populated throughout.
        library.MUSIC_CACHE["items"] = [
            {"id": "ghost-%d" % index, "path": os.path.join(self.music, "ghost%d.flac" % index), "title": "Ghost"}
            for index in range(120)
        ]

    def _restore_memory_cache(self):
        library.MUSIC_CACHE["items"] = self.old_items

    def _item(self, item_id, folder, title, track_no=1, root=None):
        parts = [part for part in (folder or "").split("/") if part]
        directory = os.path.join(*(root or self.music, *parts)) if parts else (root or self.music)
        if not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, "%s.flac" % title)
        return {
            "id": item_id,
            "path": path,
            "title": title,
            "artist": "Artist",
            "album": "Album",
            "track_no": track_no,
            "format": "FLAC",
            "mime": "audio/flac",
            "duration": 180,
        }

    def _build(self):
        items = [
            self._item("root-file", "", "Root", 1),
            self._item("album-own", "Album", "Own", 2),
            self._item("album-live-1", "Album/Live", "Live One", 3),
            self._item("album-live-2", "Album/Live", "Live Two", 4),
            self._item("album-live-deep", "Album/Live/Backstage", "Deep", 5),
            self._item("album-sibling", "AlbumX", "Sibling", 6),
            self._item("album-bang", "Album!x", "Bang", 7),
            self._item("other-root", "", "Other Root", 1, root=self.other),
            self._item("other-child", "Album/Live", "Other Child", 2, root=self.other),
        ]
        save_items_to_sqlite(self.config, items, "folder-scope")
        return items

    def test_container_page_returns_its_own_files_and_every_descendant(self):
        self._build()
        page = query_library_page(self.config, {"view": "folders", "root": self.music, "folder": "Album", "limit": "50"})
        self.assertEqual(page["count"], 4, page)
        self.assertEqual(
            sorted(item["id"] for item in page["items"]),
            ["album-live-1", "album-live-2", "album-live-deep", "album-own"],
        )
        self.assertNotIn("fallback", page)

    def test_container_count_equals_the_browsed_folder_track_count(self):
        self._build()
        listing = query_library_folders(self.config, "", self.music, "asc", 50, 0)
        container = [row for row in listing["folders"] if row["path"] == "Album"]
        self.assertEqual(len(container), 1, listing)
        page = query_library_page(self.config, {"view": "folders", "root": self.music, "folder": "Album", "limit": "50"})
        self.assertEqual(page["count"], container[0]["track_count"])

    def test_deep_container_is_scoped_to_its_branch(self):
        self._build()
        page = query_library_page(self.config, {"view": "folders", "root": self.music, "folder": "Album/Live", "limit": "50"})
        self.assertEqual(sorted(item["id"] for item in page["items"]), ["album-live-1", "album-live-2", "album-live-deep"])
        self.assertEqual(page["count"], 3)

    def test_sibling_directory_that_sorts_next_to_the_prefix_is_not_included(self):
        self._build()
        for folder in ("AlbumX", "Album!x"):
            page = query_library_page(self.config, {"view": "folders", "root": self.music, "folder": folder, "limit": "50"})
            self.assertEqual([item["id"] for item in page["items"]], ["album-sibling" if folder == "AlbumX" else "album-bang"], folder)

    def test_root_scope_lists_the_whole_root_subtree(self):
        self._build()
        page = query_library_page(self.config, {"view": "folders", "root": self.music, "folder": "", "limit": "50"})
        self.assertEqual(page["count"], 7, page)
        self.assertNotIn("other-root", [item["id"] for item in page["items"]])
        self.assertNotIn("other-child", [item["id"] for item in page["items"]])

    def test_absolute_and_slash_wrapped_scopes_address_the_same_container(self):
        self._build()
        # The nested form is a different container, not a noisier spelling.
        expected = {"/Album/": 4, "Album/": 4, "./Album": 4, "Album//Live": 3}
        for folder, want in expected.items():
            page = query_library_page(self.config, {"view": "folders", "root": self.music, "folder": folder, "limit": "50"})
            self.assertEqual(page["count"], want, folder)

    def test_missing_container_answers_empty_without_touching_the_memory_scan(self):
        self._build()
        page = query_library_page(self.config, {"view": "folders", "root": self.music, "folder": "Ghost", "limit": "50"})
        self.assertEqual(page["count"], 0, page)
        self.assertEqual(page["items"], [])
        self.assertNotIn("fallback", page)
        self.assertNotIn("Album", [item.get("title") for item in page["items"]])

    def test_blank_folder_scope_does_not_list_the_whole_table(self):
        self._build()
        page = query_library_page(self.config, {"view": "folders", "root": self.music, "folder": "//", "limit": "50"})
        self.assertEqual(page["count"], 7, page)

    def test_search_combined_with_a_folder_scope_stays_in_the_subtree(self):
        self._build()
        page = query_library_page(self.config, {"view": "folders", "root": self.music, "folder": "Album", "search": "live", "limit": "50"})
        self.assertEqual(sorted(item["id"] for item in page["items"]), ["album-live-1", "album-live-2", "album-live-deep"], page)
        self.assertEqual(page["count"], 3)

    def test_cursor_pagination_walks_the_subtree_without_gaps_or_repeats(self):
        self._build()
        seen = []
        cursor = ""
        for _ in range(10):
            params = {"view": "folders", "root": self.music, "folder": "Album", "sort": "title", "dir": "asc", "limit": "1"}
            if cursor:
                params["cursor"] = cursor
            page = query_library_page(self.config, params)
            for item in page["items"]:
                seen.append(item["id"])
            if not page.get("has_more"):
                break
            cursor = page.get("next_cursor", "")
            self.assertTrue(cursor, page)
        else:
            self.fail("cursor walk did not terminate")
        self.assertEqual(sorted(seen), ["album-live-1", "album-live-2", "album-live-deep", "album-own"])
        self.assertEqual(len(seen), len(set(seen)), seen)

    def test_genuinely_empty_index_still_falls_back_to_the_memory_library(self):
        save_items_to_sqlite(self.config, [], "empty-index")
        page = query_library_page(self.config, {"view": "all", "limit": "500"})
        self.assertEqual(page.get("fallback"), "memory", page)
        self.assertEqual(page["count"], 120)

    def test_unfiltered_folder_view_keeps_the_empty_index_rescue(self):
        save_items_to_sqlite(self.config, [], "empty-index-two")
        page = query_library_page(self.config, {"view": "folders", "root": "", "folder": "", "limit": "500"})
        self.assertEqual(page.get("fallback"), "memory", page)

    def test_folder_page_counts_beside_the_page_instead_of_over_the_subtree(self):
        self._build()
        calls = []
        real_counted = library.counted_page_rows
        real_window = library.paged_rows_with_total

        def counted(*args, **kwargs):
            calls.append("counted")
            return real_counted(*args, **kwargs)

        def window(*args, **kwargs):
            calls.append("window")
            return real_window(*args, **kwargs)

        with mock.patch.object(library, "counted_page_rows", counted), \
             mock.patch.object(library, "paged_rows_with_total", window):
            del calls[:]
            page = query_library_page(self.config, {"view": "folders", "root": self.music, "folder": "Album", "limit": "2"})
            self.assertEqual(calls, ["counted"], page)
            self.assertEqual(page["count"], 4)
            del calls[:]
            group = query_library_page(self.config, {"view": "artists", "group": "Artist", "limit": "2"})
            self.assertEqual(calls, ["window"], group)

    def test_a_recent_view_with_a_missing_search_term_does_not_rescan_the_memory_library(self):
        # The recent branch carries its own copy of the empty-result rescue.  A
        # term that matches nothing is a legal empty SQLite answer while the
        # index is healthy, so it must not be re-answered by filtering the 120
        # hydrated cache items in Python.
        self._build()
        page = query_library_page(
            self.config, {"view": "recent", "search": "zznomatchzz", "limit": "50"})
        self.assertNotIn("fallback", page, page)
        self.assertEqual(page["count"], 0, page)

    def test_a_random_view_with_a_missing_search_term_does_not_rescan_the_memory_library(self):
        # random100 filters through the same rescue; a term that matches nothing
        # has to stay an empty SQLite answer while the index itself is healthy.
        self._build()
        page = query_library_page(
            self.config, {"view": "random100", "search": "zznomatchzz", "limit": "50"})
        self.assertNotIn("fallback", page, page)
        self.assertEqual(page["count"], 0, page)


    def test_the_emptiness_probe_only_reports_a_table_with_no_rows(self):
        # This is what keeps a legal empty folder scope out of the Python scan.
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute("CREATE TABLE tracks (folder TEXT)")
            self.assertTrue(library._library_index_is_empty(conn))
            conn.execute("INSERT INTO tracks VALUES ('DSD/自然')")
            self.assertFalse(library._library_index_is_empty(conn))
        finally:
            conn.close()

        class Broken:
            def execute(self, *args):
                raise sqlite3.OperationalError("table tracks is gone")

        self.assertTrue(library._library_index_is_empty(Broken()))


if __name__ == "__main__":
    unittest.main()

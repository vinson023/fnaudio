"""Folder browse scope: one directory page lists only the files that sit in it.

A folder row in the browser is a container whose ``track_count`` covers the
whole subtree, but opening it shows its subdirectories as separate rows on the
same page.  Widening the track predicate to the subtree therefore listed every
descendant file twice -- once under its own folder row and once inside the page
-- and a small album looked like it held everything its subfolders held.  These
tests pin the one-directory rule, the agreement between the SQLite and memory
engines, and the closed empty-result fallback.
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
from library_folder_scope import folder_scope
from library_memory_query import filter_memory_page
from library_track_filter_policy import build_track_filters

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


class FolderFilterClauseTests(unittest.TestCase):
    def _query(self, **overrides):
        values = {
            "view": "folders", "group": "", "album": "", "search": "",
            "folder": "", "root": "", "group_column": "album",
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def _filters(self, **overrides):
        return build_track_filters(
            self._query(**overrides),
            search_condition=lambda *args, **kwargs: ("", []),
            group_condition=lambda *args: ("", []),
        )

    def test_a_folder_page_matches_the_leaf_directory_exactly(self):
        where, args = self._filters(folder="/DSD/自然/", root="/music")
        self.assertEqual(where, ["root = ?", "folder = ?"])
        self.assertEqual(args, ["/music", "DSD/自然"])

    def test_the_root_scope_matches_files_sitting_in_the_root_itself(self):
        # An empty scope is the library root, not "everything": the files there
        # carry ``folder = ''`` and their subdirectories are separate rows.
        where, args = self._filters(folder="", root="/music")
        self.assertEqual(where, ["root = ?", "folder = ?"])
        self.assertEqual(args, ["/music", ""])

    def test_a_traversal_scope_still_adds_a_predicate_that_matches_nothing(self):
        where, args = self._filters(folder="../secret")
        self.assertEqual(where, ["folder = ?"])
        self.assertEqual(args, ["../secret"])

    def test_other_views_are_untouched(self):
        self.assertEqual(self._filters(view="all")[0], [])
        self.assertEqual(self._filters(view="dsd")[0], ["is_dsd = 1"])


class FolderPredicateParityTests(unittest.TestCase):
    """The SQLite predicate and the Python mirror must select the same rows."""

    def _sql_ids(self, scope):
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute("CREATE TABLE tracks (id TEXT PRIMARY KEY, folder TEXT)")
            for index, folder in enumerate(FOLDER_CORPUS):
                conn.execute("INSERT INTO tracks VALUES (?, ?)", ("t%02d" % index, folder))
            where, args = build_track_filters(
                SimpleNamespace(view="folders", folder=scope, root="", group="", album="", search="", group_column="album"),
                search_condition=lambda *a, **k: ("", []),
                group_condition=lambda *a: ("", []),
            )
            rows = conn.execute(
                "SELECT id FROM tracks WHERE %s ORDER BY id" % " AND ".join(where), args
            ).fetchall()
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
        for scope in ("DSD", "DS", "x", "未整理", "DSD/自然", "DSD.txt", "DSD2", "", "DSD/自然/天地的回声/live"):
            with self.subTest(scope=scope):
                expected = [
                    "t%02d" % index
                    for index, folder in enumerate(FOLDER_CORPUS)
                    if folder == folder_scope(scope)
                ]
                self.assertEqual(self._sql_ids(scope), sorted(expected), scope)
                self.assertEqual(self._memory_ids(scope), sorted(expected), scope)

    def test_only_the_directory_itself_matches(self):
        self.assertEqual(self._sql_ids("DSD"), ["t01"])
        self.assertEqual(self._memory_ids("DSD"), ["t01"])
        self.assertEqual(self._sql_ids(""), ["t00"])
        self.assertEqual(self._memory_ids(""), ["t00"])

    def test_a_directory_whose_name_prefixes_another_never_leaks_into_it(self):
        # 'DSD' must not drag in 'DSD2/album', 'DSD!x', 'DSD-x', 'DSD.txt',
        # 'DSD0zero' or 'x/DSD', and 'DS' must not drag in 'DSD'.
        for sibling in ("DSD2/album", "DSD!x", "DSD-x", "DSD.txt", "DSD0zero", "x/DSD", "未整理/HIRES/DSD/album"):
            with self.subTest(sibling=sibling):
                self.assertNotIn(
                    "t%02d" % FOLDER_CORPUS.index(sibling), self._sql_ids("DSD")
                )
        self.assertNotIn("t01", self._sql_ids("DS"))

    def _subtree_sql_ids(self, scope):
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute("CREATE TABLE tracks (id TEXT PRIMARY KEY, folder TEXT)")
            for index, folder in enumerate(FOLDER_CORPUS):
                conn.execute("INSERT INTO tracks VALUES (?, ?)", ("t%02d" % index, folder))
            where, args = build_track_filters(
                SimpleNamespace(view="folders", folder=scope, root="", group="", album="", search="", subtree=True),
                search_condition=lambda *a, **k: ("", []),
                group_condition=lambda *a: ("", []),
            )
            rows = conn.execute(
                "SELECT id FROM tracks WHERE %s ORDER BY id" % " AND ".join(where), args
            ).fetchall()
            return sorted(row[0] for row in rows)
        finally:
            conn.close()

    def _subtree_memory_ids(self, scope):
        rows = [
            {"id": "t%02d" % index, "title": "T%02d" % index, "folder": folder,
             "path": "/music/" + folder + "/file.flac"}
            for index, folder in enumerate(FOLDER_CORPUS)
        ]
        query = SimpleNamespace(
            view="folders", group="", album="", search="", folder=scope, root="/music", subtree=True,
            sort_key="title", sort_dir="asc", group_column="album", limit=len(FOLDER_CORPUS), offset=0,
        )
        page, count = filter_memory_page(rows, query, ["/music"], "未分类", _path_under, lambda value: 0)
        self.assertEqual(count, len(page), scope)
        return sorted(item["id"] for item in page)

    def test_the_subtree_request_agrees_between_both_engines(self):
        for scope in ("DSD", "DS", "未整理", "DSD/自然", "DSD.txt"):
            with self.subTest(scope=scope):
                expected = [
                    "t%02d" % index
                    for index, folder in enumerate(FOLDER_CORPUS)
                    if folder == scope or folder.startswith(scope + "/")
                ]
                self.assertEqual(self._subtree_sql_ids(scope), sorted(expected), scope)
                self.assertEqual(self._subtree_memory_ids(scope), sorted(expected), scope)


class FolderPageTests(unittest.TestCase):
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
        # empty answer into a full Python scan, so it stays populated throughout.
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

    def test_container_page_returns_only_its_own_files(self):
        self._build()
        page = query_library_page(self.config, {"view": "folders", "root": self.music, "folder": "Album", "limit": "50"})
        self.assertEqual(page["count"], 1, page)
        self.assertEqual([item["id"] for item in page["items"]], ["album-own"])
        self.assertNotIn("fallback", page)

    def test_a_container_holding_only_subdirectories_answers_empty_not_its_subtree(self):
        self._build()
        page = query_library_page(
            self.config, {"view": "folders", "root": self.music, "folder": "Album/Live/Backstage", "limit": "50"})
        self.assertEqual([item["id"] for item in page["items"]], ["album-live-deep"])
        page = query_library_page(
            self.config, {"view": "folders", "root": self.music, "folder": "Album/Live/Backstage/none", "limit": "50"})
        self.assertEqual(page["count"], 0, page)
        self.assertEqual(page["items"], [])

    def test_child_counts_and_the_page_add_up_to_the_container_total(self):
        # This is what keeps the row's "N 首" honest once the page stopped
        # folding the subtree in: every child folder's count plus the files that
        # sit directly in the container is exactly what the row promises.
        self._build()
        listing = query_library_folders(self.config, "", self.music, "asc", 50, 0)
        container = {row["path"]: row for row in listing["folders"]}
        self.assertEqual(container["Album"]["track_count"], 4, listing)
        children = query_library_folders(self.config, "Album", self.music, "asc", 50, 0)
        child_total = sum(row["track_count"] for row in children["folders"])
        self.assertEqual([row["path"] for row in children["folders"]], ["Album/Live"])
        page = query_library_page(self.config, {"view": "folders", "root": self.music, "folder": "Album", "limit": "50"})
        self.assertEqual(child_total + page["count"], container["Album"]["track_count"])

    def test_root_scope_lists_only_the_files_sitting_in_the_root(self):
        self._build()
        page = query_library_page(self.config, {"view": "folders", "root": self.music, "folder": "", "limit": "50"})
        self.assertEqual(page["count"], 1, page)
        self.assertEqual([item["id"] for item in page["items"]], ["root-file"])

    def test_absolute_and_slash_wrapped_scopes_address_the_same_container(self):
        self._build()
        expected = {"/Album/": 1, "Album/": 1, "./Album": 1, "Album//Live": 2}
        for folder, want in expected.items():
            page = query_library_page(self.config, {"view": "folders", "root": self.music, "folder": folder, "limit": "50"})
            self.assertEqual(page["count"], want, folder)

    def test_sibling_directory_that_sorts_next_to_the_name_is_not_included(self):
        self._build()
        for folder, item_id in (("AlbumX", "album-sibling"), ("Album!x", "album-bang")):
            page = query_library_page(self.config, {"view": "folders", "root": self.music, "folder": folder, "limit": "50"})
            self.assertEqual([item["id"] for item in page["items"]], [item_id], folder)

    def test_queueing_a_folder_row_still_covers_its_subtree(self):
        # The page lists one directory, but the row itself stands for the whole
        # container: queueing it must not silently drop the subfolders.
        self._build()
        page = query_library_page(
            self.config, {"view": "folders", "root": self.music, "folder": "Album", "subtree": "1", "limit": "50"})
        self.assertEqual(page["count"], 4, page)
        self.assertEqual(
            sorted(item["id"] for item in page["items"]),
            ["album-live-1", "album-live-2", "album-live-deep", "album-own"],
        )

    def test_queueing_a_root_row_covers_every_file_of_that_root(self):
        self._build()
        page = query_library_page(
            self.config, {"view": "folders", "root": self.music, "folder": "", "subtree": "1", "limit": "50"})
        self.assertEqual(page["count"], 7, page)
        self.assertNotIn("other-root", [item["id"] for item in page["items"]])
        self.assertNotIn("other-child", [item["id"] for item in page["items"]])

    def test_the_page_and_the_subtree_request_never_share_a_cache_entry(self):
        # Both answers come from the same folder scope and differ only by the
        # flag, so a cache key that forgot it would replay whichever arrived
        # first -- and queueing a folder would silently copy the page.
        self._build()
        params = {"view": "folders", "root": self.music, "folder": "Album", "limit": "50"}
        first = query_library_page(self.config, params)
        self.assertEqual(first["count"], 1, first)
        subtree = query_library_page(self.config, dict(params, subtree="1"))
        self.assertEqual(subtree["count"], 4, subtree)
        again = query_library_page(self.config, params)
        self.assertEqual(again["count"], 1, again)

    def test_missing_container_answers_empty_without_touching_the_memory_scan(self):
        self._build()
        page = query_library_page(self.config, {"view": "folders", "root": self.music, "folder": "Ghost", "limit": "50"})
        self.assertEqual(page["count"], 0, page)
        self.assertEqual(page["items"], [])
        self.assertNotIn("fallback", page)
        self.assertNotIn("Album", [item.get("title") for item in page["items"]])

    def test_search_stays_inside_the_opened_directory(self):
        self._build()
        page = query_library_page(
            self.config, {"view": "folders", "root": self.music, "folder": "Album", "search": "live", "limit": "50"})
        self.assertEqual(page["items"], [], page)
        self.assertEqual(page["count"], 0)
        page = query_library_page(
            self.config, {"view": "folders", "root": self.music, "folder": "Album/Live", "search": "live", "limit": "50"})
        self.assertEqual(sorted(item["id"] for item in page["items"]), ["album-live-1", "album-live-2"])
        self.assertEqual(page["count"], 2)

    def test_cursor_pagination_walks_the_directory_without_gaps_or_repeats(self):
        self._build()
        seen = []
        cursor = ""
        for _ in range(10):
            params = {"view": "folders", "root": self.music, "folder": "Album/Live", "sort": "title", "dir": "asc", "limit": "1"}
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
        self.assertEqual(sorted(seen), ["album-live-1", "album-live-2"])
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

    def test_folder_page_counts_beside_the_page_instead_of_over_the_directory(self):
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
            page = query_library_page(self.config, {"view": "folders", "root": self.music, "folder": "Album/Live", "limit": "1"})
            self.assertEqual(calls, ["counted"], page)
            self.assertEqual(page["count"], 2)
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
        # This is what keeps a legal empty folder page out of the Python scan.
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

"""The album list can be read in three orders, and each one has to hold.

The order is decided in SQL, not in the browser: the rows on screen were paged
under one ORDER BY, so re-sorting them client-side would only rearrange the
current page.  That makes these assertions about the query, and they run against
a real index rather than a mocked cursor.
"""

import contextlib
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, "app/server")

import library
from library import query_library_groups, save_items_to_sqlite
from library_query_spec import GROUP_SORT_ALIASES, GROUP_SORT_COLUMNS, GROUP_SORT_KEYS, parse_library_group_query


class AlbumSortKeyTests(unittest.TestCase):
    """The whitelist is the only thing standing between a query string and SQL."""

    def test_three_keys_and_name_is_the_default(self):
        self.assertEqual(GROUP_SORT_KEYS, ("name", "artist", "release_date"))
        self.assertEqual(parse_library_group_query("albums").sort_key, "name")
        for key in GROUP_SORT_KEYS:
            self.assertEqual(parse_library_group_query("albums", sort_key=key).sort_key, key)

    def test_unknown_key_falls_back_instead_of_reaching_sql(self):
        for value in ("year", "name; DROP TABLE tracks", "", None, "release_date ASC"):
            self.assertEqual(parse_library_group_query("albums", sort_key=value).sort_key, "name")

    def test_key_is_canonicalised_before_it_becomes_a_cache_identity(self):
        self.assertEqual(parse_library_group_query("albums", sort_key="  Artist  ").sort_key, "artist")

    def test_the_album_lists_own_name_for_the_name_order_resolves_to_name(self):
        # The album list's column headers carry the track table's option id, so
        # the browser says `album`.  It has to land on the canonical `name` --
        # both because that is the column and because two spellings of one order
        # must not fill the page cache twice.
        self.assertEqual(parse_library_group_query("albums", sort_key="album").sort_key, "name")
        self.assertEqual(parse_library_group_query("albums", sort_key="ALBUM").sort_key, "name")
        self.assertEqual(GROUP_SORT_ALIASES, {"album": "name"})

    def test_every_key_names_a_column(self):
        self.assertEqual(set(GROUP_SORT_COLUMNS), set(GROUP_SORT_KEYS))
        self.assertIn("release_year", GROUP_SORT_COLUMNS["release_date"])


class AlbumSortQueryTests(unittest.TestCase):
    """End to end against a temporary index, so the SQL actually runs."""

    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.addCleanup(library.close_library_connections)
        self.music_root = os.path.join(self.root.name, "music")
        os.makedirs(self.music_root, exist_ok=True)
        self.config = {"cache_dir": os.path.join(self.root.name, "cache"), "library_paths": [self.music_root]}

    def _item(self, item_id, album, artist, year=0, album_artist=""):
        return {
            "id": item_id,
            "path": os.path.join(self.music_root, item_id + ".flac"),
            "title": item_id,
            "artist": artist,
            "album": album,
            "album_artist": album_artist,
            "track_no": 1,
            "year": year,
            "format": "FLAC",
            "mime": "audio/flac",
            "duration": 180,
        }

    def _index(self):
        save_items_to_sqlite(self.config, [
            self._item("t1", "Zebra", "Beta", 2001),
            self._item("t2", "Apple", "Beta", 1999),
            self._item("t3", "Mango", "Alpha", 2010),
            # No date tag anywhere: release_year stays 0 and the album belongs
            # at the end of the release-date order, not the front.
            self._item("t4", "Anon", "Gamma", 0),
            # Same year as Zebra, so the tie-break is exercised.
            self._item("t5", "Banana", "Alpha", 2001),
        ], "test")

    def _names(self, **kwargs):
        result = query_library_groups(self.config, "albums", **kwargs)
        groups = result["groups"] if isinstance(result, dict) else result
        return [group["name"] for group in groups]

    def test_default_order_is_album_name(self):
        self._index()
        self.assertEqual(self._names(), ["Anon", "Apple", "Banana", "Mango", "Zebra"])

    def test_artist_order_breaks_ties_on_album_name(self):
        self._index()
        self.assertEqual(self._names(sort_key="artist"), ["Banana", "Mango", "Apple", "Zebra", "Anon"])
        # Descending reverses the whole order, tie-break included: that is what
        # makes it the reversed index scan rather than a temporary B-tree.
        self.assertEqual(
            self._names(sort_key="artist", sort_dir="desc"),
            ["Anon", "Zebra", "Apple", "Mango", "Banana"],
        )

    def test_release_date_order_parks_undated_albums_at_the_end(self):
        self._index()
        self.assertEqual(self._names(sort_key="release_date"), ["Apple", "Banana", "Zebra", "Mango", "Anon"])
        self.assertEqual(
            self._names(sort_key="release_date", sort_dir="desc"),
            ["Mango", "Banana", "Zebra", "Apple", "Anon"],
        )

    def test_rows_carry_the_year_they_sorted_on(self):
        self._index()
        result = query_library_groups(self.config, "albums", sort_key="release_date")
        groups = result["groups"] if isinstance(result, dict) else result
        self.assertEqual([group.get("release_year") for group in groups], [1999, 2001, 2001, 2010, 0])

    def test_artist_scoped_branch_also_orders_by_release_date(self):
        # This branch aggregates the tracks itself, so it does not read the
        # albums table and has to carry the year through its own GROUP BY.
        self._index()
        self.assertEqual(
            self._names(sort_key="release_date", artist="Beta"),
            ["Apple", "Zebra"],
        )

    def test_paged_and_unpaged_agree(self):
        self._index()
        for key in GROUP_SORT_KEYS:
            full = self._names(sort_key=key)
            paged = []
            offset = 0
            while True:
                page = query_library_groups(self.config, "albums", limit=2, offset=offset, sort_key=key)
                names = [group["name"] for group in page["groups"]]
                if not names:
                    break
                paged.extend(names)
                offset += len(names)
            self.assertEqual(paged, full, "paged %s order diverged from the full read" % key)

    def test_artist_scoped_paging_does_not_skip_or_repeat(self):
        self._index()
        full = self._names(sort_key="release_date", artist="Beta")
        paged = []
        offset = 0
        while True:
            page = query_library_groups(
                self.config, "albums", limit=1, offset=offset, sort_key="release_date", artist="Beta"
            )
            names = [group["name"] for group in page["groups"]]
            if not names:
                break
            paged.extend(names)
            offset += len(names)
        self.assertEqual(paged, full)


class AlbumYearMigrationTests(unittest.TestCase):
    """An index built before this column existed must gain it, not fail."""

    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.addCleanup(library.close_library_connections)
        self.music_root = os.path.join(self.root.name, "music")
        os.makedirs(self.music_root, exist_ok=True)
        self.config = {"cache_dir": os.path.join(self.root.name, "cache"), "library_paths": [self.music_root]}

    def test_old_albums_table_is_migrated_and_filled_by_the_rebuild(self):
        path = library.library_db_path(self.config)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # The pre-release_date shape of the table.  `with sqlite3.connect(...)`
        # commits but does not close, and an open handle keeps the temporary
        # directory from being removed on Windows, so closing is explicit.
        with contextlib.closing(sqlite3.connect(path)) as conn:
            conn.execute(
                "CREATE TABLE albums (name TEXT PRIMARY KEY, artist TEXT, track_count INTEGER NOT NULL DEFAULT 0, cover_track_id TEXT)"
            )
            conn.execute("INSERT INTO albums(name,artist,track_count,cover_track_id) VALUES ('Old','Someone',1,'x')")
            conn.commit()
        library._forget_library_schema(self.config)
        save_items_to_sqlite(self.config, [{
            "id": "t1",
            "path": os.path.join(self.music_root, "t1.flac"),
            "title": "t1",
            "artist": "Beta",
            "album": "Fresh",
            "track_no": 1,
            "year": 1994,
            "format": "FLAC",
            "mime": "audio/flac",
            "duration": 180,
        }], "test")
        with library.library_db_connect(self.config) as conn:
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(albums)")}
            self.assertIn("release_year", columns)
            rows = {row["name"]: row["release_year"] for row in conn.execute("SELECT name, release_year FROM albums")}
        self.assertEqual(rows, {"Fresh": 1994})


if __name__ == "__main__":
    unittest.main()

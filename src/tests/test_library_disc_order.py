"""R591: an album's order is disc, then track.

Audio Station models ``disc`` as its own tag field, and a multi-disc set is the
case where that matters: sorting a two-disc album by ``track_no`` alone
interleaves the discs (1, 1, 2, 2, ...) and the second disc's track 1 lands
before the first disc's track 2.

The keyset cursor compares ONE expression (``library_cursor_policy`` reads
``page_query.sql_order`` into ``(%s) AS _cursor_primary`` and every continuation
predicate is built against that single value), so widening the ORDER BY to
``disc, track_no`` would have meant a composite cursor key through the cursor
policy, the page-result projection and both expression indexes.  Instead the pair
is folded into one integer, ``disc*1000 + track_no``, by
``library_write.track_sort_value``.

This file pins the fold and the order it produces.  It also pins the upgrade
case: a row written by an older build has ``track_sort = 0``, and the SQL has to
keep reading its plain ``track_no`` so "sort by track" does not break between the
upgrade and the next scan.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, "app/server")

import library
from library import library_db_connect, query_library_page, save_items_to_sqlite
from library_query_spec import TRACK_SORT_COLUMNS
from library_write import track_sort_value


def item(item_id, path, title, track_no, disc_no=None):
    record = {
        "id": item_id,
        "path": path,
        "title": title,
        "artist": "Artist",
        "album": "Set",
        "track_no": track_no,
        "format": "FLAC",
        "mime": "audio/flac",
        "duration": 180,
    }
    if disc_no is not None:
        record["disc_no"] = disc_no
    return record


class TrackSortValueTests(unittest.TestCase):
    def test_disc_and_track_fold_into_one_integer(self):
        self.assertEqual(track_sort_value(1, 1), 1001)
        self.assertEqual(track_sort_value(1, 12), 1012)
        self.assertEqual(track_sort_value(2, 1), 2001)
        # The whole point: disc 2 track 1 sorts after disc 1 track 12.
        self.assertGreater(track_sort_value(2, 1), track_sort_value(1, 12))

    def test_no_disc_tag_keeps_the_plain_track_number(self):
        # This is what makes an untagged single-disc album behave exactly as it
        # did before the column existed.
        self.assertEqual(track_sort_value(0, 7), 7)
        self.assertEqual(track_sort_value(None, 7), 7)

    def test_an_unusable_track_number_folds_to_zero(self):
        self.assertEqual(track_sort_value(1, 0), 0)
        self.assertEqual(track_sort_value(1, -3), 0)
        self.assertEqual(track_sort_value(1, 1000), 0, "the fold must not overflow the track slot")
        self.assertEqual(track_sort_value("x", "y"), 0)

    def test_an_out_of_range_disc_falls_back_to_the_track_number(self):
        # A disc number that would collide with the next disc's slot (or come
        # from a broken tag) must not reorder anything.
        self.assertEqual(track_sort_value(100, 5), 5)
        self.assertEqual(track_sort_value(-1, 5), 5)


class DiscOrderTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.addCleanup(library.close_library_connections)
        self.music_root = os.path.join(self.root.name, "music")
        os.makedirs(self.music_root, exist_ok=True)
        self.config = {"cache_dir": os.path.join(self.root.name, "cache"), "library_paths": [self.music_root]}

    def _save(self, items):
        save_items_to_sqlite(self.config, items, "test")

    def _order(self, **query):
        params = {"view": "all", "sort": "track_no", "dir": "asc", "limit": "50"}
        params.update(query)
        page = query_library_page(self.config, params)
        return [entry["id"] for entry in page["items"]]

    def test_a_two_disc_album_orders_by_disc_then_track(self):
        items = [
            item("d1t1", os.path.join(self.music_root, "d1t1.flac"), "One", 1, 1),
            item("d1t2", os.path.join(self.music_root, "d1t2.flac"), "Two", 2, 1),
            item("d2t1", os.path.join(self.music_root, "d2t1.flac"), "Three", 1, 2),
            item("d2t2", os.path.join(self.music_root, "d2t2.flac"), "Four", 2, 2),
        ]
        self._save(items)
        self.assertEqual(self._order(), ["d1t1", "d1t2", "d2t1", "d2t2"])

    def test_the_disc_order_survives_a_descending_page(self):
        items = [
            item("d1t1", os.path.join(self.music_root, "d1t1.flac"), "One", 1, 1),
            item("d2t1", os.path.join(self.music_root, "d2t1.flac"), "Two", 1, 2),
        ]
        self._save(items)
        self.assertEqual(self._order(dir="desc"), ["d2t1", "d1t1"])

    def test_a_row_written_before_the_column_existed_still_sorts_by_track(self):
        # An upgrade keeps the old rows until the next scan fills track_sort in.
        # Reading 0 as "no album order" would have parked every one of them at
        # the end of the list, which is a visible regression on first launch.
        items = [
            item("a", os.path.join(self.music_root, "a.flac"), "A", 1),
            item("b", os.path.join(self.music_root, "b.flac"), "B", 2),
        ]
        self._save(items)
        with library_db_connect(self.config) as conn:
            conn.execute("UPDATE tracks SET track_sort = 0")
            conn.commit()
        self.assertEqual(self._order(), ["a", "b"])

    def test_a_track_without_a_track_number_sorts_last(self):
        items = [
            item("none", os.path.join(self.music_root, "none.flac"), "None", 0),
            item("one", os.path.join(self.music_root, "one.flac"), "One", 1),
        ]
        self._save(items)
        self.assertEqual(self._order(), ["one", "none"])

    def test_the_sort_expression_names_the_folded_column(self):
        # The expression, its two indexes and this query have to stay in step:
        # an index built on a different expression is silently unused, which is
        # how a page that used to be an index seek becomes a temp B-tree sort.
        expression = TRACK_SORT_COLUMNS["track_no"]
        self.assertIn("track_sort", expression)
        self.assertIn("track_no", expression, "the pre-R591 fallback must stay in the expression")
        with library_db_connect(self.config) as conn:
            names = {row[1] for row in conn.execute("PRAGMA index_list(tracks)")}
        self.assertIn("idx_tracks_track_sort_title_id_asc", names)
        self.assertIn("idx_tracks_track_sort_title_id_desc", names)
        self.assertNotIn("idx_tracks_track_no_title_id_asc", names, "the old expression index must be dropped")
        self.assertNotIn("idx_tracks_root_folder_track_no", names, "the old folder index must be dropped")


if __name__ == "__main__":
    unittest.main()

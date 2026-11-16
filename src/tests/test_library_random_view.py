"""The 随机 100 首 view is a fixed sample, not a page.

Reported symptom: the view showed "50-something" tracks on a phone, and playing
it stopped at the end of that page -- "点下一首都没有反应". Both came from the
sample size being ``min(100, limit)``: the caller's page size (96 desktop, 60
phone) silently became the size of the random view, so the queue built from it
ended where the page ended.

``count`` is pinned to the sample the client can actually play. Reporting the
library total instead made the pager believe a second page existed, and paging a
random draw hands out a fresh sample (duplicate tracks, half a sample).
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, "app/server")

import library
from library import query_library_page, save_items_to_sqlite


def item(item_id, root, title, track_no):
    return {
        "id": item_id,
        "path": os.path.join(root, title + ".flac"),
        "title": title,
        "artist": "Artist",
        "album": "Album",
        "track_no": track_no,
        "format": "FLAC",
        "mime": "audio/flac",
        "duration": 180,
    }


class RandomViewSampleTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.addCleanup(library.close_library_connections)
        self.music_root = os.path.join(self.root.name, "music")
        os.makedirs(self.music_root, exist_ok=True)
        self.config = {
            "cache_dir": os.path.join(self.root.name, "cache"),
            "library_paths": [self.music_root],
        }

    def index(self, count):
        save_items_to_sqlite(
            self.config,
            [item("t%03d" % index, self.music_root, "Track %03d" % index, index) for index in range(count)],
            "random-sample-test",
        )

    def page(self, **params):
        query = {"view": "random100", "page": "1"}
        query.update({key: str(value) for key, value in params.items()})
        return query_library_page(self.config, query)

    def test_a_small_page_size_does_not_shrink_the_sample(self):
        self.index(140)
        for limit in (60, 96):
            with self.subTest(limit=limit):
                result = self.page(limit=limit)
                self.assertEqual(len(result["items"]), library.RANDOM_VIEW_SAMPLE_SIZE)
                self.assertEqual(result["count"], library.RANDOM_VIEW_SAMPLE_SIZE)

    def test_the_sample_is_unique_and_inside_the_library(self):
        self.index(140)
        result = self.page(limit=60)
        ids = [row["id"] for row in result["items"]]
        self.assertEqual(len(ids), len(set(ids)), "a sample may not repeat a track")

    def test_a_library_smaller_than_the_sample_returns_all_of_it(self):
        self.index(7)
        result = self.page(limit=60)
        self.assertEqual(len(result["items"]), 7)
        self.assertEqual(result["count"], 7, "the pager must not promise rows that do not exist")

    def test_the_view_reports_itself_as_one_draw(self):
        self.index(140)
        result = self.page()
        self.assertFalse(result.get("paged", True), "a random draw has no second page")
        self.assertEqual(result["offset"], 0)

    def test_an_empty_library_stays_empty(self):
        result = self.page()
        self.assertEqual(result["items"], [])
        self.assertEqual(result["count"], 0)


if __name__ == "__main__":
    unittest.main()

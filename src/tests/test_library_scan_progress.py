"""Discriminating tests for showing tracks while a first scan is still running.

The owner's report: on a fresh install of a library with tens of thousands of
tracks, the interface showed nothing at all until the walk finished.  The scan
accumulated into a sink and published only at the end, so every page request
read an empty index and answered zero rows.

The fix publishes the accumulator to ``MUSIC_CACHE`` while the walk runs.
``query_library_page`` already falls back to the in-memory page when the SQLite
index holds no row, so nothing else had to change on the read path.  These tests
pin the three things that make that safe: the walk publishes before it ends, a
populated library is never replaced by a partial one, and the published list is
what a page request actually answers.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "app/server")

import library


def write_tracks(root, count):
    os.makedirs(root, exist_ok=True)
    for index in range(count):
        with open(os.path.join(root, "track-%02d.flac" % index), "wb") as handle:
            handle.write(b"fnaudio-test-track")
    return root


class ScanProgressPublishTests(unittest.TestCase):
    def setUp(self):
        self._saved_items = library.MUSIC_CACHE["items"]
        self._saved_stamp = library.MUSIC_CACHE["stamp"]
        library.MUSIC_CACHE["items"] = []
        library.MUSIC_CACHE["stamp"] = 0.0

    def tearDown(self):
        library.MUSIC_CACHE["items"] = self._saved_items
        library.MUSIC_CACHE["stamp"] = self._saved_stamp

    def test_p1_the_walk_publishes_a_prefix_before_it_finishes(self):
        """The first publish must happen mid-walk, not after the last file."""
        with tempfile.TemporaryDirectory() as root:
            music = write_tracks(os.path.join(root, "music"), 4)
            published = []
            with patch.object(library, "read_probe_metadata", return_value=({}, {})):
                items, _signature = library.scan_library(
                    music, config={}, progress=published.append,
                )
        self.assertEqual(len(items), 4)
        self.assertTrue(published, "a first scan published nothing while it ran")
        # A publish after the last file would not help the owner at all: what
        # matters is that a strict prefix was handed over while the walk went on.
        self.assertLess(len(published[0]), len(items))
        self.assertEqual(published[0][0]["path"], items[0]["path"])

    def test_p1_the_publish_is_throttled_to_one_per_interval(self):
        """A fast walk must not rebuild the list once per file."""
        with tempfile.TemporaryDirectory() as root:
            music = write_tracks(os.path.join(root, "music"), 6)
            published = []
            with patch.object(library, "read_probe_metadata", return_value=({}, {})):
                library.scan_library(music, config={}, progress=published.append)
        self.assertEqual(len(published), 1)

    def test_p1_a_populated_library_never_gets_a_partial_list(self):
        """Rescanning must not shrink what the owner can already see."""
        self.assertIsNone(library.scan_progress_publisher([{"id": "kept"}]))
        self.assertIs(library.scan_progress_publisher([]), library.publish_scan_progress)

    def test_p1_publishing_replaces_the_list_readers_see(self):
        items = [{"id": "a", "path": "/music/a.flac", "title": "A"}]
        self.assertTrue(library.publish_scan_progress(items))
        self.assertEqual(library.MUSIC_CACHE["items"], items)
        self.assertGreater(library.MUSIC_CACHE["stamp"], 0.0)

    def test_p1_an_empty_accumulator_is_not_published(self):
        """Publishing ``[]`` would wipe a list the walk has not reached yet."""
        library.MUSIC_CACHE["items"] = [{"id": "kept"}]
        self.assertFalse(library.publish_scan_progress([]))
        self.assertEqual(library.MUSIC_CACHE["items"], [{"id": "kept"}])

    def test_p1_a_page_request_answers_from_the_published_progress(self):
        """The point of publishing: a page request stops answering zero rows."""
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": os.path.join(root, "cache"), "library_path": os.path.join(root, "music")}
            published = [
                {
                    "id": "track-01",
                    "path": os.path.join(root, "music", "track-01.flac"),
                    "title": "Track 01",
                    "artist": "artist",
                    "album": "album",
                    "folder": "",
                    "root": config["library_path"],
                }
            ]
            library.publish_scan_progress(published)
            # No SQLite file exists yet: this is the fresh-install read path.
            page = library.query_library_page(config, {"paged": ["1"], "limit": ["10"]})
        self.assertEqual([item["id"] for item in page["items"]], ["track-01"])

    def test_p1_publishing_drops_the_empty_page_cached_before_it(self):
        """An index that exists but holds no row caches its zero-row answer.

        Measured on a 10,880-track host: the first publish happened at 1.5s, but
        the page kept replaying the cached empty result until the query cache
        expired at 20.1s.  Publishing has to drop those pages, or the owner still
        stares at "no music" for the cache TTL.
        """
        with tempfile.TemporaryDirectory() as root:
            music = write_tracks(os.path.join(root, "music"), 2)
            config = {"cache_dir": os.path.join(root, "cache"), "library_path": music}
            os.makedirs(config["cache_dir"], exist_ok=True)
            # An existing database with an empty tracks table: the read path
            # answers from SQL, and that answer is cacheable.
            library.save_items_to_sqlite(config, [], "")
            params = {"paged": ["1"], "limit": ["10"]}
            self.assertEqual(library.query_library_page(config, params).get("items"), [])
            published = [
                {
                    "id": "track-00",
                    "path": os.path.join(music, "track-00.flac"),
                    "title": "Track 00",
                    "artist": "artist",
                    "album": "album",
                    "folder": "",
                    "root": music,
                }
            ]
            library.publish_scan_progress(published, config)
            page = library.query_library_page(config, params)
        self.assertEqual([item["id"] for item in page["items"]], ["track-00"])


if __name__ == "__main__":
    unittest.main()

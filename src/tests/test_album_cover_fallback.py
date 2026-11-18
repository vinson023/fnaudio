"""R591: an album cover must not be decided by whichever track has the smallest id.

``albums.cover_track_id`` is ``MIN(s.id)`` (library.py), so the cover a client
asks for is the alphabetically smallest track of the album -- not the first one
that actually carries artwork.  On an album whose covers are embedded per track
and only on some of them, that track often has none, and the album then showed no
cover at all even though a neighbour had one.  Audio Station resolves an album
cover by album name, so it never had this hole.

The fallback is deliberately lazy and bounded: it runs only when a cover request
is about to miss, tries a handful of neighbours on the same album and folder, and
the answer is cached (including "still nothing") under the requesting item's key.
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

import library
import server
from library import album_cover_fallback_paths, save_items_to_sqlite


class AlbumCoverFallbackQueryTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.addCleanup(library.close_library_connections)
        self.music_root = os.path.join(self.scratch.name, "music")
        os.makedirs(self.music_root, exist_ok=True)
        self.config = {"cache_dir": os.path.join(self.scratch.name, "cache"), "library_paths": [self.music_root]}

    def path(self, name, folder="disc1"):
        return os.path.join(self.music_root, folder, name)

    def track(self, item_id, track_no, album="Set", folder="disc1"):
        return {
            "id": item_id,
            "path": self.path(item_id + ".flac", folder),
            # A stored row takes ``root`` from ``_index_root``; the scanner sets it
            # and ``item_json`` never carries it, so a fixture has to set it the
            # same way or the root column stays empty and every lookup misses.
            "_index_root": self.music_root,
            "folder": folder,
            "title": item_id,
            "artist": "Artist",
            "album": album,
            "track_no": track_no,
            "format": "FLAC",
            "mime": "audio/flac",
            "duration": 180,
        }

    def _save(self, items):
        save_items_to_sqlite(self.config, items, "test")

    def _lookup(self, item_id, album="Set", folder="disc1"):
        item = {"id": item_id, "album": album, "folder": folder, "path": self.path(item_id + ".flac", folder)}
        return album_cover_fallback_paths(self.config, item)

    def test_neighbours_come_back_in_album_order_without_the_item_itself(self):
        self._save([self.track("a01", 1), self.track("a02", 2), self.track("a03", 3)])
        self.assertEqual(self._lookup("a02"), [self.path("a01.flac"), self.path("a03.flac")])

    def test_another_album_is_never_borrowed(self):
        self._save([self.track("a01", 1, album="Set"), self.track("b01", 1, album="Other")])
        self.assertEqual(self._lookup("a01"), [])

    def test_another_folder_is_never_borrowed(self):
        # Two albums can share a name across folders; borrowing across them would
        # put one album's art on another.
        self._save([self.track("a01", 1, folder="disc1"), self.track("a02", 2, folder="disc2")])
        self.assertEqual(self._lookup("a01"), [])

    def test_the_lookup_is_bounded(self):
        self._save([self.track("t%02d" % index, index) for index in range(1, 21)])
        self.assertEqual(len(self._lookup("t01")), library.ALBUM_COVER_FALLBACK_LIMIT)

    def test_an_untagged_album_borrows_nothing(self):
        self._save([self.track("a01", 1, album=""), self.track("a02", 2, album="")])
        self.assertEqual(self._lookup("a01", album=""), [])
        self.assertEqual(album_cover_fallback_paths(self.config, None), [])

    def test_a_path_outside_every_configured_root_borrows_nothing(self):
        # ``folder`` is relative, so a path under no root has no trustworthy
        # album identity; answering empty is better than guessing.
        self._save([self.track("a01", 1), self.track("a02", 2)])
        outside = {"id": "a01", "album": "Set", "folder": "disc1", "path": "/elsewhere/disc1/a01.flac"}
        self.assertEqual(album_cover_fallback_paths(self.config, outside), [])

    def test_a_missing_index_answers_empty_instead_of_raising(self):
        self.assertEqual(self._lookup("a01"), [])


class CoverReaderFallbackTests(unittest.TestCase):
    def test_a_track_without_art_borrows_the_neighbour(self):
        item = {"id": "a02", "album": "Set", "folder": "disc1", "path": "/music/disc1/a02.flac"}
        with mock.patch.object(server, "album_cover_fallback_paths", return_value=["/music/disc1/a01.flac"]), mock.patch.object(
            server,
            "read_cover_for_item",
            side_effect=lambda entry, config: (("image/jpeg", b"ART")) if entry.get("path") == "/music/disc1/a01.flac" else (None, None),
        ):
            mime, body = server.read_cover_with_album_fallback(item, {})
        self.assertEqual(mime, "image/jpeg")
        self.assertEqual(body, b"ART")

    def test_its_own_art_wins_and_no_neighbour_is_read(self):
        item = {"id": "a02", "album": "Set", "folder": "disc1", "path": "/music/disc1/a02.flac"}
        neighbour = mock.Mock(return_value=["/music/disc1/a01.flac"])
        with mock.patch.object(server, "album_cover_fallback_paths", neighbour), mock.patch.object(
            server, "read_cover_for_item", return_value=("image/png", b"OWN")
        ):
            mime, body = server.read_cover_with_album_fallback(item, {})
        self.assertEqual((mime, body), ("image/png", b"OWN"))
        neighbour.assert_not_called()

    def test_no_neighbour_with_art_still_reports_nothing(self):
        item = {"id": "a02", "album": "Set", "folder": "disc1", "path": "/music/disc1/a02.flac"}
        with mock.patch.object(server, "album_cover_fallback_paths", return_value=["/music/disc1/a01.flac"]), mock.patch.object(
            server, "read_cover_for_item", return_value=(None, None)
        ):
            self.assertEqual(server.read_cover_with_album_fallback(item, {}), (None, None))


if __name__ == "__main__":
    unittest.main()

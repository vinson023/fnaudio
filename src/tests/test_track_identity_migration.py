"""The identity migration has to move the references with the ids.

Switching track ids to content fingerprints is only safe if the favorites,
playlists and the saved queue move in the same round. A half-migrated state looks
exactly like the bug that started this: rows that point at ids the library cannot
serve.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, "app/server")

import library
from library import rebuild_track_identity, save_items_to_sqlite
from state_store import (load_user_state, remap_track_ids, save_playback_session,
                         save_user_state)
from track_identity import content_track_id, fallback_track_id


def item(item_id, path, title, track_no):
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


class IdentityMigrationTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.addCleanup(library.close_library_connections)
        self.music = os.path.join(self.root.name, "music")
        os.makedirs(self.music, exist_ok=True)
        self.config = {
            "cache_dir": os.path.join(self.root.name, "cache"),
            "library_paths": [self.music],
        }
        # Two real files, each with its own bytes.
        self.paths = []
        for index, payload in enumerate((b"FLAC-one" + b"\x00" * 2048, b"FLAC-two" + b"\x01" * 2048)):
            path = os.path.join(self.music, "track%d.flac" % index)
            with open(path, "wb") as handle:
                handle.write(payload)
            self.paths.append(path)

    def index_with_path_ids(self):
        """Write an index the way the old scanner did: id = sha1(path)."""
        rows = [
            item(fallback_track_id(path), path, "Track %d" % index, index + 1)
            for index, path in enumerate(self.paths)
        ]
        save_items_to_sqlite(self.config, rows, "identity-migration-test")
        return {row["id"]: row["path"] for row in rows}

    def test_migration_moves_favorites_playlists_and_the_queue(self):
        old_by_path = self.index_with_path_ids()
        old_ids = list(old_by_path)
        save_user_state(self.config, {
            "favorites": old_ids,
            "playlists": [{"id": "pl-1", "name": "Road", "trackIds": [old_ids[0]]}],
        })
        save_playback_session(self.config, {"queue": old_ids, "current_id": old_ids[1]})

        report = rebuild_track_identity(self.config)
        self.assertEqual(report["rekeyed"], 2)
        moved = remap_track_ids(self.config, report["mapping"])
        self.assertEqual(moved["favorites"], 2)
        self.assertEqual(moved["playlist_tracks"], 1)
        self.assertEqual(moved["sessions"], 1)

        expected = sorted(content_track_id(path) for path in self.paths)
        state = load_user_state(self.config)
        self.assertEqual(sorted(state["favorites"]), expected)
        self.assertEqual(state["playlists"][0]["trackIds"], [content_track_id(self.paths[0])])
        self.assertEqual(state["playback"]["queue"], [content_track_id(path) for path in self.paths])
        self.assertEqual(state["playback"]["current_id"], content_track_id(self.paths[1]))

    def test_the_new_ids_are_the_content_ids(self):
        self.index_with_path_ids()
        report = rebuild_track_identity(self.config)
        mapping = report["mapping"]
        for index, path in enumerate(self.paths):
            self.assertEqual(mapping[fallback_track_id(path)], content_track_id(path))

    def test_migration_is_idempotent(self):
        self.index_with_path_ids()
        rebuild_track_identity(self.config)
        second = rebuild_track_identity(self.config)
        self.assertEqual(second["rekeyed"], 0, "a second run has nothing left to move")

    def test_duplicate_content_keeps_both_rows_with_a_stable_suffix(self):
        # A byte-identical copy: one row keeps the plain id, the other gets a
        # path-derived suffix so it stays addressable instead of overwriting.
        with open(self.paths[0], "rb") as source:
            payload = source.read()
        with open(self.paths[1], "wb") as handle:
            handle.write(payload)
        self.index_with_path_ids()
        report = rebuild_track_identity(self.config)
        self.assertEqual(report["duplicates"], 1)
        self.assertEqual(len(report["mapping"]), 2)
        new_ids = sorted(report["mapping"].values())
        base = content_track_id(self.paths[0])
        self.assertIn(base, new_ids)
        self.assertTrue(any(value.startswith(base + "-") for value in new_ids))

    def test_a_missing_file_keeps_its_old_id(self):
        old_by_path = self.index_with_path_ids()
        os.remove(self.paths[0])
        report = rebuild_track_identity(self.config)
        self.assertEqual(report["unreadable"], 1)
        self.assertNotIn(fallback_track_id(self.paths[0]), report["mapping"],
                         "an unreadable file must keep the id it already has")

    def test_remap_does_not_create_a_duplicate_favorite(self):
        self.index_with_path_ids()
        report = rebuild_track_identity(self.config)
        new_id = content_track_id(self.paths[0])
        # Already favorited under the new id by another client.
        save_user_state(self.config, {"favorites": [new_id]})
        remap_track_ids(self.config, report["mapping"])
        state = load_user_state(self.config)
        self.assertEqual(state["favorites"].count(new_id), 1)


if __name__ == "__main__":
    unittest.main()

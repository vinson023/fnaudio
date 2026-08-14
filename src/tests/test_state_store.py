import sys
import tempfile
import threading
import unittest

sys.path.insert(0, "app/server")

from state_store import StateConflict, load_user_state, save_playback_session, save_user_state, state_db_path


class StateStoreTests(unittest.TestCase):
    def test_state_round_trip_preserves_order(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root}
            self.assertFalse(load_user_state(config)["initialized"])
            saved = save_user_state(
                config,
                {
                    "favorites": ["track-2", "track-1", "track-2"],
                    "playlists": [
                        {"id": "night", "name": "Night", "trackIds": ["track-3", "track-1"]},
                        {"id": "work", "name": "Work", "trackIds": ["track-2"]},
                    ],
                    "playback": {"queue": ["track-3", "track-1"], "current_id": "track-3", "repeat": "all", "shuffle": False},
                },
            )
            self.assertEqual(saved["favorites"], ["track-2", "track-1"])
            self.assertTrue(saved["initialized"])
            self.assertEqual(saved["playlists"][0]["trackIds"], ["track-3", "track-1"])
            self.assertEqual(load_user_state(config)["playback"]["current_id"], "track-3")
            self.assertTrue(state_db_path(config).endswith("state.sqlite3"))

    def test_ui_column_preferences_survive_state_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root}
            save_user_state(
                config,
                {
                    "favorites": [],
                    "playlists": [],
                    "playback": {"queue": ["track-1"]},
                    "ui": {
                        "track_columns": {
                            "all": ["track_no", "format"],
                            "artists:tracks:Artist:Album": ["album", "added"],
                            "folders:%2Fvol1%2Fmusic:Jazz%2F2026": ["quality", "artist", "duration"],
                        }
                    },
                },
            )
            save_playback_session(config, {"queue": ["track-2"], "current_id": "track-2"})
            state = load_user_state(config)
            self.assertEqual(state["ui"]["track_columns"]["all"], ["track_no", "format"])
            self.assertEqual(state["ui"]["track_columns"]["artists:tracks:Artist:Album"], ["album", "added"])
            self.assertEqual(state["ui"]["track_columns"]["folders:%2Fvol1%2Fmusic:Jazz%2F2026"], ["quality", "artist", "duration"])

    def test_playback_session_can_be_saved_without_replacing_media_lists(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root}
            save_user_state(config, {"favorites": ["track-1"], "playlists": [], "playback": {}})
            save_playback_session(config, {"queue": ["track-2", "track-1"], "current_id": "track-2", "repeat": "all", "shuffle": True, "target_id": "mpd:hw:3,0"})
            state = load_user_state(config)
            self.assertEqual(state["favorites"], ["track-1"])
            self.assertEqual(state["playback"]["queue"], ["track-2", "track-1"])
            self.assertEqual(state["playback"]["target_id"], "mpd:hw:3,0")

    def test_stale_state_revision_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root}
            first = save_user_state(config, {"favorites": ["track-1"], "playlists": [], "playback": {}})
            save_user_state(config, {"favorites": ["track-2"], "playlists": [], "playback": {}}, first["revision"])
            with self.assertRaises(StateConflict):
                save_user_state(config, {"favorites": ["track-3"], "playlists": [], "playback": {}}, first["revision"])

    def test_stale_client_changes_merge_favorite_deletions_and_playlist_edits(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root}
            initial = save_user_state(
                config,
                {
                    "favorites": ["keep", "remove-a", "remove-b"],
                    "playlists": [
                        {"id": "delete-me", "name": "Delete", "trackIds": ["one"]},
                        {"id": "remote-edit", "name": "Before", "trackIds": ["one"]},
                    ],
                    "playback": {"current_id": "one"},
                },
            )
            remote = save_user_state(
                config,
                {
                    "favorites": ["keep", "remove-b", "remote-add"],
                    "playlists": [
                        {"id": "delete-me", "name": "Delete", "trackIds": ["one"]},
                        {"id": "remote-edit", "name": "Remote", "trackIds": ["one", "two"]},
                        {"id": "remote-only", "name": "Remote only", "trackIds": ["three"]},
                    ],
                    "playback": {"current_id": "two"},
                },
                initial["revision"],
            )
            merged = save_user_state(
                config,
                {
                    "favorites": ["keep", "remove-a", "local-add"],
                    "playlists": [{"id": "local-only", "name": "Local", "trackIds": ["four"]}],
                    "playback": {"current_id": "stale"},
                    "changes": {
                        "favorites_add": ["local-add"],
                        "favorites_remove": ["remove-b"],
                        "playlist_upserts": [{"id": "local-only", "name": "Local", "trackIds": ["four"]}],
                        "playlist_delete": ["delete-me"],
                    },
                },
                initial["revision"],
            )

            self.assertEqual(set(merged["favorites"]), {"keep", "remote-add", "local-add"})
            playlists = {entry["id"]: entry for entry in merged["playlists"]}
            self.assertNotIn("delete-me", playlists)
            self.assertEqual(playlists["remote-edit"]["name"], "Remote")
            self.assertEqual(playlists["remote-only"]["trackIds"], ["three"])
            self.assertEqual(playlists["local-only"]["trackIds"], ["four"])
            self.assertEqual(merged["playback"], remote["playback"])

    def test_parallel_playback_session_saves_are_serialized(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root}
            failures = []

            def save(index):
                try:
                    save_playback_session(config, {"queue": ["track-%s" % index], "current_id": "track-%s" % index})
                except Exception as exc:
                    failures.append(exc)

            threads = [threading.Thread(target=save, args=(index,)) for index in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(failures, [])
            self.assertEqual(load_user_state(config)["revision"], 8)


if __name__ == "__main__":
    unittest.main()

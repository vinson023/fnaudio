import sys
import os
import io
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

import state_store
from state_count_policy import CHILD_INTEGRITY_VERIFIED
from state_store import StateConflict, load_user_state, save_playback_session, save_user_state, state_db_path


class StateStoreTests(unittest.TestCase):
    def test_state_db_connect_preserves_body_failure_when_rollback_fails(self):
        conn = mock.MagicMock()
        conn.rollback.side_effect = RuntimeError("rollback failed")
        with mock.patch.object(state_store, "secure_directory"), \
             mock.patch.object(state_store, "secure_sqlite_files"), \
             mock.patch.object(state_store.sqlite3, "connect", return_value=conn):
            with self.assertRaisesRegex(ValueError, "body failed"):
                with state_store.state_db_connect({"cache_dir": "."}):
                    raise ValueError("body failed")
        conn.rollback.assert_called_once()
        conn.close.assert_called_once()

    def test_state_db_connect_preserves_body_failure_when_failed_cleanup_fails(self):
        conn = mock.MagicMock()
        conn.close.side_effect = RuntimeError("close failed")
        secure_files = mock.MagicMock(side_effect=[None, None, RuntimeError("permission failed")])
        with mock.patch.object(state_store, "secure_directory"), \
             mock.patch.object(state_store, "secure_sqlite_files", secure_files), \
             mock.patch.object(state_store.sqlite3, "connect", return_value=conn):
            with self.assertRaisesRegex(ValueError, "body failed"):
                with state_store.state_db_connect({"cache_dir": "."}):
                    raise ValueError("body failed")
        conn.rollback.assert_called_once()
        conn.close.assert_called_once()

    def test_state_db_connect_does_not_turn_committed_state_into_cleanup_failure(self):
        conn = mock.MagicMock()
        secure_files = mock.MagicMock(side_effect=[None, None, RuntimeError("permission failed")])
        with mock.patch.object(state_store, "secure_directory"), \
             mock.patch.object(state_store, "secure_sqlite_files", secure_files), \
             mock.patch.object(state_store.sqlite3, "connect", return_value=conn):
            with state_store.state_db_connect({"cache_dir": "."}):
                pass
        conn.commit.assert_called_once()
        conn.close.assert_called_once()

    def test_save_user_state_handles_non_mapping_payload(self):
        with tempfile.TemporaryDirectory() as root:
            saved = save_user_state({"cache_dir": root}, None)
            self.assertTrue(saved["initialized"])
            self.assertEqual(saved["favorites"], [])

    def test_save_user_state_handles_broken_payload_mapping(self):
        class Broken(dict):
            def get(self, key, default=None):
                raise RuntimeError("broken payload")

        with tempfile.TemporaryDirectory() as root:
            saved = save_user_state({"cache_dir": root}, Broken())
            self.assertTrue(saved["initialized"])
            self.assertEqual(saved["playlists"], [])
    def test_revision_projection_is_bounded_and_isolates_broken_rows(self):
        class BrokenRow:
            def __getitem__(self, key):
                raise RuntimeError("broken row")

        class Conn:
            def __init__(self, row):
                self.row = row

            def execute(self, *_args):
                class Cursor:
                    def __init__(self, row):
                        self.row = row

                    def fetchone(self):
                        return self.row

                return Cursor(self.row)

        self.assertEqual(state_store._revision(Conn(BrokenRow())), 0)
        self.assertEqual(state_store._revision(Conn({"value": 10**30})), state_store.MAX_STATE_REVISION)

    def test_next_revision_saturates_at_the_bounded_maximum(self):
        class Conn:
            def __init__(self):
                self.writes = []

            def execute(self, sql, params):
                if sql.startswith("SELECT"):
                    class Cursor:
                        def fetchone(self):
                            return {"value": str(state_store.MAX_STATE_REVISION)}
                    return Cursor()
                self.writes.append(params)

        conn = Conn()
        self.assertEqual(state_store._next_revision(conn), state_store.MAX_STATE_REVISION)
        self.assertEqual(conn.writes[-1][1], str(state_store.MAX_STATE_REVISION))
    def test_state_db_path_uses_safe_default_for_missing_or_invalid_cache_dir(self):
        self.assertTrue(state_db_path({}).endswith("state.sqlite3"))
        self.assertTrue(state_db_path({"cache_dir": object()}).endswith("state.sqlite3"))
        self.assertTrue(state_db_path({"cache_dir": "x" * 5000}).endswith("state.sqlite3"))
    def test_broken_string_iterable_keeps_items_read_before_failure(self):
        class BrokenList(list):
            def __iter__(self):
                yield "first"
                raise RuntimeError("broken iterator")

        self.assertEqual(state_store._strings(BrokenList(), 10), ["first"])

    def test_ui_preferences_reject_untrusted_object_keys(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("must not stringify UI keys")

        result = state_store._ui_preferences({"track_columns": {Explosive(): ["title"], "ok": ["artist"]}})
        self.assertEqual(result["track_columns"], {"ok": ["artist"]})

    def test_broken_ui_mapping_falls_back_to_empty_preferences(self):
        class Broken(dict):
            def get(self, key, default=None):
                raise RuntimeError("broken mapping")

        self.assertEqual(state_store._ui_preferences(Broken()), {"track_columns": {}, "track_column_widths": {}})

    def test_broken_state_changes_mapping_is_ignored(self):
        class Broken(dict):
            def get(self, key, default=None):
                raise RuntimeError("broken changes")

        self.assertIsNone(state_store._state_changes(Broken()))

    def test_broken_playlist_mapping_is_skipped(self):
        class Broken(dict):
            def get(self, key, default=None):
                raise RuntimeError("broken mapping")

        self.assertEqual(state_store._playlists([Broken(), {"id": "ok", "name": "OK", "trackIds": ["a"]}])[0]["id"], "ok")

    def test_oversized_persisted_json_is_ignored_before_decode(self):
        oversized = "{\"x\":\"" + ("a" * state_store.MAX_STATE_PAYLOAD_BYTES) + "\"}"
        self.assertEqual(state_store._load_json_bounded(oversized), {})
        self.assertEqual(state_store._load_json_bounded("{\"ok\":true}"), {"ok": True})

    def test_persisted_playlist_reads_have_sql_limits(self):
        class Cursor:
            def __iter__(self):
                return iter(())

            def fetchall(self):
                return []

            def fetchone(self):
                return None

        class Connection:
            def __init__(self):
                self.calls = []

            def execute(self, statement, args=()):
                self.calls.append((statement, tuple(args)))
                return Cursor()

        conn = Connection()
        context = mock.MagicMock()
        context.__enter__.return_value = conn
        context.__exit__.return_value = False
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.object(state_store, "state_db_connect", return_value=context):
                state_store.load_user_state({"cache_dir": root})
        playlist_call = next(call for call in conn.calls if "FROM playlists" in call[0])
        self.assertEqual(playlist_call[1], (state_store.MAX_PERSISTED_PLAYLISTS,))
        favorites_call = next(call for call in conn.calls if "FROM favorites" in call[0])
        self.assertEqual(favorites_call[1], (state_store.MAX_PERSISTED_FAVORITES,))

    def test_persisted_playlist_reads_share_a_total_track_id_budget(self):
        class Cursor:
            def __init__(self, rows):
                self.rows = rows

            def __iter__(self):
                return iter(self.rows)

            def fetchall(self):
                return list(self.rows)

            def fetchone(self):
                return None

        class Connection:
            def __init__(self):
                self.calls = []

            def execute(self, sql, values=()):
                self.calls.append((sql, values))
                if "FROM favorites" in sql:
                    return Cursor([])
                if "FROM playlists" in sql:
                    return Cursor([{"id": "first", "name": "First"}, {"id": "second", "name": "Second"}])
                if "FROM playlist_tracks" in sql:
                    limit = values[1]
                    return Cursor([{"track_id": "track-%d" % index} for index in range(limit)])
                return Cursor([])

            def commit(self):
                return None

            def rollback(self):
                return None

            def close(self):
                return None

        conn = Connection()
        context = mock.MagicMock()
        context.__enter__.return_value = conn
        context.__exit__.return_value = False
        original_budget = state_store.MAX_PERSISTED_PLAYLIST_TRACK_IDS_TOTAL
        try:
            state_store.MAX_PERSISTED_PLAYLIST_TRACK_IDS_TOTAL = state_store.MAX_PERSISTED_TRACK_IDS + 3
            with mock.patch.object(state_store, "state_db_connect", return_value=context):
                state = state_store.load_user_state({"cache_dir": "."})
            self.assertEqual([len(entry["trackIds"]) for entry in state["playlists"]], [state_store.MAX_PERSISTED_TRACK_IDS, 3])
        finally:
            state_store.MAX_PERSISTED_PLAYLIST_TRACK_IDS_TOTAL = original_budget

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

    def test_oversized_playback_save_is_rejected_without_overwriting_previous_state(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root}
            save_playback_session(config, {"queue": ["keep"], "current_id": "keep"})
            with self.assertRaises(ValueError):
                save_playback_session(config, {"queue": ["x" * state_store.MAX_STATE_PAYLOAD_BYTES]})
            state = load_user_state(config)
            self.assertEqual(state["playback"]["queue"], ["keep"])

    def test_direct_playback_save_applies_queue_and_boolean_projection(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root}
            save_playback_session(config, {
                "queue": ["track-%d" % index for index in range(50010)],
                "current_id": 123,
                "playing": "false",
                "shuffle": "true",
                "repeat": "invalid",
            })
            playback = load_user_state(config)["playback"]
            self.assertEqual(len(playback["queue"]), 50000)
            self.assertEqual(playback["current_id"], "")
            self.assertFalse(playback["playing"])
            self.assertFalse(playback["shuffle"])
            self.assertEqual(playback["repeat"], "off")

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

    def test_stale_delta_batch_favorite_add_keeps_client_order(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root}
            initial = save_user_state(config, {"favorites": ["older"], "playlists": [], "playback": {}})
            save_user_state(
                config,
                {"favorites": ["newest", "older"], "playlists": [], "playback": {}},
                initial["revision"],
            )

            merged = save_user_state(
                config,
                {
                    "favorites": ["older", "a", "b", "c"],
                    "playlists": [],
                    "playback": {},
                    "changes": {
                        "favorites_add": ["a", "b", "c"],
                        "favorites_remove": [],
                        "playlist_upserts": [],
                        "playlist_delete": [],
                    },
                },
                initial["revision"],
            )

            self.assertEqual(merged["favorites"], ["a", "b", "c", "newest", "older"])

    def test_stale_delta_trims_historical_playlist_table_overflow(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root}
            limits = (
                state_store.MAX_PERSISTED_PLAYLISTS,
                state_store.MAX_PERSISTED_TRACK_IDS,
                state_store.MAX_PERSISTED_PLAYLIST_TRACK_IDS_TOTAL,
            )
            try:
                state_store.MAX_PERSISTED_PLAYLISTS = 2
                state_store.MAX_PERSISTED_TRACK_IDS = 2
                state_store.MAX_PERSISTED_PLAYLIST_TRACK_IDS_TOTAL = 3
                with state_store.state_db_connect(config) as conn:
                    conn.executemany(
                        "INSERT INTO playlists(id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                        [("first", "First", 1, 1), ("second", "Second", 2, 2), ("overflow", "Overflow", 3, 3)],
                    )
                    conn.executemany(
                        "INSERT INTO playlist_tracks(playlist_id, track_id, position) VALUES (?, ?, ?)",
                        [
                            ("first", "one", 0), ("first", "two", 1), ("first", "three", 2),
                            ("second", "four", 0), ("second", "five", 1),
                            ("overflow", "six", 0),
                        ],
                    )
                    state_store._next_revision(conn)

                saved = save_user_state(
                    config,
                    {
                        "favorites": [], "playlists": [], "playback": {},
                        "changes": {"favorites_add": ["local"], "favorites_remove": [], "playlist_upserts": [], "playlist_delete": []},
                    },
                    expected_revision=0,
                )
                self.assertEqual([entry["id"] for entry in saved["playlists"]], ["first", "second"])
                self.assertEqual([len(entry["trackIds"]) for entry in saved["playlists"]], [2, 1])
                with state_store.state_db_connect(config) as conn:
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM playlists").fetchone()[0], 2)
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM playlist_tracks").fetchone()[0], 3)
            finally:
                (
                    state_store.MAX_PERSISTED_PLAYLISTS,
                    state_store.MAX_PERSISTED_TRACK_IDS,
                    state_store.MAX_PERSISTED_PLAYLIST_TRACK_IDS_TOTAL,
                ) = limits

    def test_stale_delta_saves_cannot_grow_the_favorites_table(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root}
            original = state_store.MAX_PERSISTED_FAVORITES
            try:
                state_store.MAX_PERSISTED_FAVORITES = 4
                save_user_state(config, {"favorites": ["seed"], "playlists": [], "playback": {}}, expected_revision=0)
                for batch in range(3):
                    saved = save_user_state(
                        config,
                        {
                            "changes": {
                                "favorites_add": ["%d-a" % batch, "%d-b" % batch],
                                "favorites_remove": [],
                                "playlist_upserts": [],
                                "playlist_delete": [],
                            }
                        },
                        expected_revision=0,   # stale on purpose: this is the merge-with-disk path
                    )
                    with state_store.state_db_connect(config) as conn:
                        stored = conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0]
                    self.assertLessEqual(stored, 4, "delta save grew the table past the cap")
                    self.assertEqual(len(saved["favorites"]), (3, 4, 4)[batch], "reader-visible list must stay at the cap")
                    self.assertEqual(saved["favorites"][0], "%d-a" % batch, "newest-first order must survive the trim")
                with state_store.state_db_connect(config) as conn:
                    ids = sorted(row["track_id"] for row in conn.execute("SELECT track_id FROM favorites"))
                self.assertEqual(ids, sorted(["1-a", "1-b", "2-a", "2-b"]))
            finally:
                state_store.MAX_PERSISTED_FAVORITES = original

    def test_favorites_trim_keeps_exactly_what_the_reader_returns(self):
        shapes = [
            ([("f%d" % index, 10 - index) for index in range(4)], 4),
            ([("f%d" % index, 10 - index) for index in range(5)], 4),
            ([("f%d" % index, 7) for index in range(6)], 4),
            ([("a", 1), ("b", 3), ("c", 2), ("d", 3), ("e", 1)], 3),
            ([], 4),
            ([("only", 1)], 4),
        ]
        original = state_store.MAX_PERSISTED_FAVORITES
        try:
            for rows, cap in shapes:
                with self.subTest(rows=[entry[0] for entry in rows], cap=cap):
                    state_store.MAX_PERSISTED_FAVORITES = cap
                    with tempfile.TemporaryDirectory() as root:
                        config = {"cache_dir": root}
                        with state_store.state_db_connect(config) as conn:
                            conn.executemany(
                                "INSERT INTO favorites(track_id, created_at) VALUES (?, ?)", rows)
                            expected = [row["track_id"] for row in conn.execute(
                                "SELECT track_id FROM favorites ORDER BY created_at DESC, rowid DESC LIMIT ?",
                                (cap,),
                            )]
                            state_store._trim_persisted_favorites(conn)
                            stored = [row["track_id"] for row in conn.execute(
                                "SELECT track_id FROM favorites ORDER BY created_at DESC, rowid DESC")]
                        self.assertEqual(stored, expected)
                        self.assertEqual(load_user_state(config)["favorites"], expected)
        finally:
            state_store.MAX_PERSISTED_FAVORITES = original

    def test_favorites_trim_issues_no_delete_within_the_cap(self):
        original = state_store.MAX_PERSISTED_FAVORITES
        try:
            state_store.MAX_PERSISTED_FAVORITES = 4
            with tempfile.TemporaryDirectory() as root:
                config = {"cache_dir": root}
                with state_store.state_db_connect(config) as conn:
                    conn.executemany(
                        "INSERT INTO favorites(track_id, created_at) VALUES (?, ?)",
                        [("f%d" % index, index) for index in range(4)],
                    )
                with state_store.state_db_connect(config) as conn:
                    counted = _CountingConnection(conn)
                    state_store._trim_persisted_favorites(counted)
                    self.assertEqual(counted.deletes, [])
                    self.assertEqual(counted.execute("SELECT COUNT(*) FROM favorites").fetchone()[0], 4)
        finally:
            state_store.MAX_PERSISTED_FAVORITES = original

    def test_favorites_request_bound_is_independent_of_the_storage_cap(self):
        """Drift guard, not a behavior test.

        ``_strings`` bounds how many ids one save may carry, and
        ``MAX_PERSISTED_FAVORITES`` bounds what stays on disk.  Both are 50000
        today, so ordinary behavior tests cannot tell them apart: raising either
        one still yields a 50000-row table.  Lifting the storage cap above the
        request cap here is what makes the request bound observable, and that
        bound is a memory/CPU guard for the save itself, so it must not drift
        silently with the storage number.
        """
        original = state_store.MAX_PERSISTED_FAVORITES
        try:
            state_store.MAX_PERSISTED_FAVORITES = 50001
            with tempfile.TemporaryDirectory() as root:
                config = {"cache_dir": root}
                requested = ["track-%06d" % index for index in range(50002)]
                saved = save_user_state(config, {"favorites": requested, "playlists": [], "playback": {}}, None)
                self.assertEqual(len(saved["favorites"]), 50000)
                self.assertEqual(saved["favorites"], requested[:50000])
        finally:
            state_store.MAX_PERSISTED_FAVORITES = original

    def test_the_favorites_request_bound_reads_its_own_name(self):
        """The bound a request is checked against is now a name, not a shared literal.

        R76's drift guard above could only show that the request bound and the retention
        bound happen to coincide: it moved the storage cap and watched the request path
        truncate anyway.  This moves the request bound alone.  A save that carries 20 ids
        keeps 10 while the retention cap stays at its ordinary 50000, so the eleven that
        never reached the table were dropped by the request guard, and an implementation
        that aliases the two constants cannot pass.
        """
        original_request = state_store.MAX_REQUEST_FAVORITES
        original_storage = state_store.MAX_PERSISTED_FAVORITES
        original_deletions = state_store.MAX_REQUEST_PLAYLIST_DELETIONS
        requested = ["track-%06d" % index for index in range(20)]
        try:
            state_store.MAX_REQUEST_FAVORITES = 10
            changes = state_store._state_changes({"favorites_add": requested,
                                                  "favorites_remove": requested})
            self.assertEqual(changes["favorites_add"], requested[:10])
            self.assertEqual(changes["favorites_remove"], requested[:10])
            with tempfile.TemporaryDirectory() as root:
                config = {"cache_dir": root}
                saved = save_user_state(config, {"favorites": requested, "playlists": [],
                                                 "playback": {}}, None)
                self.assertEqual(saved["favorites"], requested[:10])
                self.assertEqual(state_store.MAX_PERSISTED_FAVORITES, original_storage)
            # The delete batch is a third promise with its own number: it is bounded at
            # 1000, so a list of 1001 ids cannot be answered with the favorites bound.
            state_store.MAX_REQUEST_FAVORITES = original_request
            deletions = ["playlist-%05d" % index for index in range(1001)]
            batch = state_store._state_changes({"playlist_delete": deletions})
            self.assertEqual(batch["playlist_delete"], deletions[:1000])
            state_store.MAX_REQUEST_PLAYLIST_DELETIONS = 4
            batch = state_store._state_changes({"playlist_delete": deletions})
            self.assertEqual(batch["playlist_delete"], deletions[:4])
        finally:
            state_store.MAX_REQUEST_FAVORITES = original_request
            state_store.MAX_REQUEST_PLAYLIST_DELETIONS = original_deletions

    def test_connecting_while_a_writer_holds_the_database_does_not_wait(self):
        """The per-connect schema script is not a write transaction, and must stay that way.

        R76 called it one and priced a steady-state connection at the busy timeout.  Measured
        against a writer holding `BEGIN IMMEDIATE`: the connect completes in 2.8 ms while the
        same code path costs 2.087 s the moment the schema really is incomplete (a dropped
        table), because *that* script does have to write.  So the expensive case is the repair
        it exists to perform, not the normal one.  The assertion worth keeping is the tripwire:
        if anyone makes the steady path actually write, say a data backfill added to the
        script, every connection turns into the 2 s case and this test catches it without
        depending on absolute timings.
        """
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root}
            with state_store.state_db_connect(config) as connection:
                connection.execute("INSERT INTO state_meta(key, value) VALUES('seed', '1')")
            path = str(state_db_path(config))
            writer = sqlite3.connect(path, timeout=15)
            try:
                writer.execute("BEGIN IMMEDIATE")
                writer.execute("INSERT INTO state_meta(key, value) VALUES('uncommitted', '1')")
                started = time.monotonic()
                with state_store.state_db_connect(config) as connection:
                    visible = connection.execute(
                        "SELECT COUNT(*) FROM state_meta WHERE key = 'uncommitted'").fetchone()[0]
                    row_count = connection.execute(
                        "SELECT COUNT(*) FROM favorites").fetchone()[0]
                elapsed = time.monotonic() - started
                self.assertEqual(visible, 0, "the writer's transaction is not visible yet, so it "
                                             "still held the database while this connected")
                self.assertGreaterEqual(row_count, 0)
                self.assertLess(elapsed, 1.0,
                                "a steady-state connection waited %.3f s behind a writer; the "
                                "schema path stopped being read-only" % elapsed)
                writer.commit()
            finally:
                writer.close()
            with state_store.state_db_connect(config) as connection:
                repaired = connection.execute(
                    "SELECT COUNT(*) FROM state_meta WHERE key = 'uncommitted'").fetchone()[0]
            self.assertEqual(repaired, 1, "the writer's row should survive its commit")

    def test_repeated_trim_cycles_reuse_pages_instead_of_growing_the_file(self):
        """The rows are bounded and so is the file, which is why no VACUUM is needed.

        R70's open question was whether the file, unlike the table, keeps creeping.  It
        does not: SQLite reuses the pages the trim frees, so the database stays at the size
        of one full table however many trim cycles pass.  That is exactly the property that
        makes a whole-file rebuild unnecessary, so it must fail loudly if the trim ever
        stops reusing pages.  The two reclaim mechanisms the item considered are pinned
        here too, because both measured out unusable or pointless on an existing database.
        """
        cap = state_store.MAX_PERSISTED_FAVORITES
        half = cap // 2
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root}
            path = state_store.state_db_path(config)

            def facts():
                connection = sqlite3.connect(path)
                try:
                    return (connection.execute("PRAGMA page_size").fetchone()[0],
                            connection.execute("PRAGMA page_count").fetchone()[0],
                            connection.execute("PRAGMA freelist_count").fetchone()[0],
                            connection.execute("PRAGMA auto_vacuum").fetchone()[0])
                finally:
                    connection.close()

            save_user_state(config, {"favorites": ["peak-%06d" % index for index in range(cap)],
                                     "playlists": [], "playback": {}}, None)
            page_size, peak_pages, peak_free, auto_vacuum = facts()
            self.assertEqual(peak_free, 0, "a table at its cap has nothing free to reuse")
            self.assertGreater(peak_pages, 100, "the fixture must be big enough to hold pages")

            for cycle in range(3):
                for letter in ("a", "b"):
                    save_user_state(config, {"favorites": ["%s%d-%06d" % (letter, cycle, index)
                                                           for index in range(half)],
                                             "playlists": [], "playback": {}}, None)
            page_size, pages, freelist, auto_vacuum_after = facts()
            self.assertEqual((pages, page_size), (peak_pages, page_size),
                             "trim cycles extended the database instead of reusing its pages")
            self.assertGreater(freelist, 10, "the cycles left nothing free, so the equality above "
                                              "would be measuring an idle database")
            self.assertLessEqual(freelist * page_size, pages * page_size,
                                 "the whole reclaim ceiling is the one table already accounted for")
            self.assertEqual(auto_vacuum, 0, "incremental vacuum is not enabled on this database")
            self.assertEqual(auto_vacuum_after, auto_vacuum)
            connection = sqlite3.connect(path)
            try:
                connection.execute("PRAGMA incremental_vacuum")
            finally:
                connection.close()
            self.assertEqual(facts()[1], peak_pages,
                             "incremental_vacuum cannot return pages on an auto_vacuum=0 database")
            size_before = os.path.getsize(path)
            self.assertEqual(size_before, peak_pages * page_size,
                             "the file should be exactly its pages once the WAL is checkpointed")

    def test_state_database_enforces_playlist_track_cascade(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root}
            with state_store.state_db_connect(config) as conn:
                self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
                conn.execute(
                    "INSERT INTO playlists(id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    ("playlist", "Playlist", 1, 1),
                )
                conn.execute(
                    "INSERT INTO playlist_tracks(playlist_id, track_id, position) VALUES (?, ?, ?)",
                    ("playlist", "track", 0),
                )
                conn.execute("DELETE FROM playlists WHERE id = ?", ("playlist",))
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM playlist_tracks").fetchone()[0], 0)

    def test_playlist_trim_does_not_depend_on_sqlite_large_variable_limits(self):
        # R89 measured the alternative R65 left open - keying the parent delete on the
        # `keep_ids` already computed above it - and declined it: 0.58 ms saved at the
        # 1000-playlist cap, 0.78 ms at double the cap, 0.026 ms for a dozen playlists, so
        # nothing on the path a real user takes. The shape this test guards is also why the
        # merge stays declined: both deletes re-derive the keep-set inside SQLite and bind
        # one parameter each, whereas a merged form would bind one per kept playlist and
        # couple a sub-millisecond saving to a cap R65 expects to raise.
        class VariableLimitConnection:
            def __init__(self, conn):
                self.conn = conn

            def execute(self, sql, parameters=()):
                if len(parameters) > 999:
                    raise AssertionError("playlist trim exceeded SQLite's common variable limit")
                return self.conn.execute(sql, parameters)

        original_limit = state_store.MAX_PERSISTED_PLAYLISTS
        raw = None
        try:
            state_store.MAX_PERSISTED_PLAYLISTS = 1000
            raw = sqlite3.connect(":memory:")
            raw.row_factory = sqlite3.Row
            state_store.ensure_state_schema(raw)
            for index in range(1001):
                raw.execute(
                    "INSERT INTO playlists(id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    ("playlist-%04d" % index, "Playlist", index, index),
                )
            state_store._trim_persisted_playlists(VariableLimitConnection(raw))
            self.assertEqual(raw.execute("SELECT COUNT(*) FROM playlists").fetchone()[0], 1000)
        finally:
            state_store.MAX_PERSISTED_PLAYLISTS = original_limit
            if raw is not None:
                raw.close()

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

    def _trim_database(self, counts, orphans=0):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        state_store.ensure_state_schema(conn)
        for index, tracks in enumerate(counts):
            conn.execute(
                "INSERT INTO playlists(id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                ("playlist-%03d" % index, "Playlist %d" % index, index + 1, index + 1),
            )
            conn.executemany(
                "INSERT INTO playlist_tracks(playlist_id, track_id, position) VALUES (?, ?, ?)",
                [("playlist-%03d" % index, "track-%05d" % position, position) for position in range(tracks)],
            )
        if orphans:
            # A database written before the foreign key existed can hold track
            # rows whose playlist is gone.  Creating the parent, turning the
            # constraint off and deleting it is how such a row survives in the
            # wild; the pragma has no effect inside an open transaction, so the
            # committed rows have to be flushed first.
            conn.execute("INSERT INTO playlists(id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                         ("gone", "Gone", 900, 900))
            conn.executemany(
                "INSERT INTO playlist_tracks(playlist_id, track_id, position) VALUES (?, ?, ?)",
                [("gone", "orphan-%03d" % position, position) for position in range(orphans)],
            )
            conn.commit()
            conn.execute("PRAGMA foreign_keys = OFF")
            self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 0)
            conn.execute("DELETE FROM playlists WHERE id = ?", ("gone",))
            conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        return conn

    def _reference_trim(self, conn):
        """The pre-R65 algorithm: one DELETE plus one COUNT per stored playlist."""
        keep_rows = conn.execute(
            "SELECT id FROM playlists ORDER BY created_at ASC, id ASC LIMIT ?",
            (state_store.MAX_PERSISTED_PLAYLISTS,),
        ).fetchall()
        keep_ids = [row["id"] for row in keep_rows]
        if not keep_ids:
            conn.execute("DELETE FROM playlist_tracks")
            conn.execute("DELETE FROM playlists")
            return
        conn.execute(
            "DELETE FROM playlist_tracks WHERE playlist_id NOT IN ("
            "SELECT id FROM playlists ORDER BY created_at ASC, id ASC LIMIT ?"
            ")",
            (state_store.MAX_PERSISTED_PLAYLISTS,),
        )
        conn.execute(
            "DELETE FROM playlists WHERE id NOT IN ("
            "SELECT id FROM playlists ORDER BY created_at ASC, id ASC LIMIT ?"
            ")",
            (state_store.MAX_PERSISTED_PLAYLISTS,),
        )
        remaining = state_store.MAX_PERSISTED_PLAYLIST_TRACK_IDS_TOTAL
        for playlist_id in keep_ids:
            keep_count = min(state_store.MAX_PERSISTED_TRACK_IDS, remaining)
            conn.execute(
                "DELETE FROM playlist_tracks WHERE playlist_id = ? AND rowid NOT IN ("
                "SELECT rowid FROM playlist_tracks WHERE playlist_id = ? "
                "ORDER BY position ASC, rowid ASC LIMIT ?"
                ")",
                (playlist_id, playlist_id, keep_count),
            )
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM playlist_tracks WHERE playlist_id = ?",
                (playlist_id,),
            ).fetchone()
            count = int(row["count"] or 0) if row else 0
            remaining = max(0, remaining - min(keep_count, count))

    def _database_contents(self, conn):
        return (
            [tuple(row) for row in conn.execute("SELECT id, name, created_at, updated_at FROM playlists ORDER BY id")],
            [tuple(row) for row in conn.execute(
                "SELECT playlist_id, track_id, position FROM playlist_tracks ORDER BY playlist_id, position, track_id")],
        )

    def test_playlist_trim_matches_the_statement_per_playlist_reference(self):
        caps = (
            state_store.MAX_PERSISTED_PLAYLISTS,
            state_store.MAX_PERSISTED_TRACK_IDS,
            state_store.MAX_PERSISTED_PLAYLIST_TRACK_IDS_TOTAL,
        )
        shapes = [
            ([], 0),                   # nothing stored
            ([0], 0),                  # an empty playlist survives
            ([1, 1, 1], 0),            # comfortably within budget
            ([1] * 6, 0),              # too many playlists, none too long
            ([9, 1], 0),               # one playlist over its own cap
            ([4, 4, 4], 0),            # the grand total is what bites first
            ([6, 6, 6, 1, 1, 1], 0),   # both caps bite at once
            ([1, 1], 5),               # orphan rows from a pre-foreign-key database
            ([2] * 7, 3),              # overflow plus orphans
            ([0, 4, 4], 0),            # an empty playlist must not spend the budget
            ([4, 0, 4, 4], 0),         # ... in any position
            ([3, 3, 3], 0),            # under every per-playlist cap, over the total
        ]
        try:
            state_store.MAX_PERSISTED_PLAYLISTS = 3
            state_store.MAX_PERSISTED_TRACK_IDS = 4
            state_store.MAX_PERSISTED_PLAYLIST_TRACK_IDS_TOTAL = 7
            for counts, orphans in shapes:
                label = "counts=%s orphans=%d" % (counts, orphans)
                current = self._trim_database(counts, orphans)
                reference = self._trim_database(counts, orphans)
                try:
                    state_store._trim_persisted_playlists(current)
                    self._reference_trim(reference)
                    self.assertEqual(
                        self._database_contents(current),
                        self._database_contents(reference),
                        "trim outcome differs for %s" % label,
                    )
                finally:
                    current.close()
                    reference.close()
        finally:
            (
                state_store.MAX_PERSISTED_PLAYLISTS,
                state_store.MAX_PERSISTED_TRACK_IDS,
                state_store.MAX_PERSISTED_PLAYLIST_TRACK_IDS_TOTAL,
            ) = caps

    def test_playlist_trim_statement_count_does_not_grow_with_the_library(self):
        counters = {}
        for playlists in (20, 60, 100):
            conn = self._trim_database([3] * playlists)
            counter = _CountingConnection(conn)
            try:
                state_store._trim_persisted_playlists(counter)
            finally:
                counters[playlists] = counter
                conn.close()
        # Nothing here exceeds any cap, so the trim must be a fixed handful of
        # statements.  The old shape issued two per playlist, 42/122/202.
        for playlists, counter in counters.items():
            self.assertLessEqual(len(counter.statements), 8, "%d playlists issued %d statements" % (playlists, len(counter.statements)))
            per_playlist = [sql for sql in counter.deletes if "rowid NOT IN" in sql]
            self.assertEqual(per_playlist, [], "a within-budget library must not be trimmed playlist by playlist")
        self.assertEqual(len(counters[20].statements), len(counters[100].statements),
                         "the trim still scales with the number of playlists")


class PersistedPlaylistCountTests(unittest.TestCase):
    """R115: playlists.track_count replaces the per-save scan of the child table."""

    SOURCE = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), os.pardir, "app", "server", "state_store.py"
    )
    SERVER_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), os.pardir, "app"
    )
    PRISTINE_CAPS = (
        state_store.MAX_PERSISTED_PLAYLISTS,
        state_store.MAX_PERSISTED_TRACK_IDS,
        state_store.MAX_PERSISTED_PLAYLIST_TRACK_IDS_TOTAL,
    )

    def setUp(self):
        # These tests shrink the caps to exercise the trim cheaply.  A cap that
        # leaks into a later test rewrites its expectations silently, so every
        # test starts by proving nobody leaked, and ends by putting them back.
        self.assertEqual(
            self._caps(), self.PRISTINE_CAPS,
            "a previous test leaked its trim caps into the module",
        )

    def tearDown(self):
        (
            state_store.MAX_PERSISTED_PLAYLISTS,
            state_store.MAX_PERSISTED_TRACK_IDS,
            state_store.MAX_PERSISTED_PLAYLIST_TRACK_IDS_TOTAL,
        ) = self.PRISTINE_CAPS

    def _source(self):
        with io.open(self.SOURCE, encoding="utf-8") as handle:
            return handle.read()

    def _database(self, counts, orphans=0, stamp=None, verified=False):
        """Build a stored state database the way the writer leaves it behind.

        ``stamp`` is what the parent row claims about its children, None meaning
        the unknown value an upgraded database carries.
        """
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        state_store.ensure_state_schema(conn)
        for index, tracks in enumerate(counts):
            playlist_id = "playlist-%03d" % index
            conn.execute(
                "INSERT INTO playlists(id, name, created_at, updated_at, track_count)"
                " VALUES (?, ?, ?, ?, ?)",
                (playlist_id, "Playlist %d" % index, index + 1, index + 1, stamp),
            )
            conn.executemany(
                "INSERT INTO playlist_tracks(playlist_id, track_id, position) VALUES (?, ?, ?)",
                [(playlist_id, "track-%05d" % position, position) for position in range(tracks)],
            )
        if orphans:
            # Child rows outliving their parent is legacy damage: reach it by
            # deleting a parent with the constraint off, after committing.
            conn.execute(
                "INSERT INTO playlists(id, name, created_at, updated_at, track_count)"
                " VALUES (?, ?, ?, ?, ?)",
                ("gone", "Gone", 900, 900, orphans),
            )
            conn.executemany(
                "INSERT INTO playlist_tracks(playlist_id, track_id, position) VALUES (?, ?, ?)",
                [("gone", "orphan-%03d" % position, position) for position in range(orphans)],
            )
            conn.commit()
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("DELETE FROM playlists WHERE id = ?", ("gone",))
            conn.execute("PRAGMA foreign_keys = ON")
        if verified:
            conn.execute(
                "INSERT OR REPLACE INTO state_meta(key, value) VALUES (?, ?)",
                (state_store._CHILD_INTEGRITY_KEY, CHILD_INTEGRITY_VERIFIED),
            )
        conn.commit()
        return conn

    def _stored_counts(self, conn):
        return {row["id"]: row["track_count"] for row in conn.execute("SELECT id, track_count FROM playlists")}

    def _true_counts(self, conn):
        # Every parent row is asked, including the ones with no children: a
        # playlist that legitimately holds zero rows still owns a zero count,
        # and leaving it out would hide a count that never got repaired.
        return {
            row["id"]: int(row["count"])
            for row in conn.execute(
                "SELECT p.id, (SELECT COUNT(*) FROM playlist_tracks t"
                " WHERE t.playlist_id = p.id) AS count FROM playlists p"
            )
        }

    def _child_rows(self, conn):
        return [tuple(row) for row in conn.execute(
            "SELECT playlist_id, track_id, position FROM playlist_tracks"
            " ORDER BY playlist_id, position, track_id"
        )]

    def _parent_rows(self, conn):
        return [tuple(row) for row in conn.execute(
            "SELECT id, name, created_at, updated_at FROM playlists ORDER BY id"
        )]

    def _caps(self):
        return (
            state_store.MAX_PERSISTED_PLAYLISTS,
            state_store.MAX_PERSISTED_TRACK_IDS,
            state_store.MAX_PERSISTED_PLAYLIST_TRACK_IDS_TOTAL,
        )

    def _use_tiny_caps(self):
        self._caps_are(3, 4, 7)

    def _caps_are(self, playlists, per_playlist, total):
        # tearDown() puts the real caps back, so a test may set them freely.
        state_store.MAX_PERSISTED_PLAYLISTS = playlists
        state_store.MAX_PERSISTED_TRACK_IDS = per_playlist
        state_store.MAX_PERSISTED_PLAYLIST_TRACK_IDS_TOTAL = total

    def _legacy_database_without_the_column(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE playlists (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
            CREATE TABLE playlist_tracks (
                playlist_id TEXT NOT NULL,
                track_id TEXT NOT NULL,
                position INTEGER NOT NULL,
                PRIMARY KEY (playlist_id, track_id)
            );
            """
        )
        conn.execute(
            "INSERT INTO playlists(id, name, created_at, updated_at) VALUES ('a', 'A', 1, 1)"
        )
        conn.executemany(
            "INSERT INTO playlist_tracks(playlist_id, track_id, position) VALUES (?, ?, ?)",
            [("a", "track-%d" % position, position) for position in range(3)],
        )
        conn.commit()
        return conn

    def test_upgrade_adds_the_count_as_unknown_not_as_zero(self):
        conn = self._legacy_database_without_the_column()
        try:
            state_store.ensure_state_schema(conn)
            self.assertEqual(self._stored_counts(conn), {"a": None})
            self.assertEqual(list(self._stored_counts(conn).values()), [None])
            # Unknown has to mean "ask the child table", never "this playlist is
            # empty": the first save after an upgrade must still trim correctly.
            self._use_tiny_caps()
            try:
                state_store._trim_persisted_playlists(conn)
            finally:
                (
                    state_store.MAX_PERSISTED_PLAYLISTS,
                    state_store.MAX_PERSISTED_TRACK_IDS,
                    state_store.MAX_PERSISTED_PLAYLIST_TRACK_IDS_TOTAL,
                ) = self._caps()
            self.assertEqual(self._stored_counts(conn), {"a": 3})
            self.assertEqual(conn.execute(
                "SELECT value FROM state_meta WHERE key = ?",
                (state_store._CHILD_INTEGRITY_KEY,),
            ).fetchone()[0], CHILD_INTEGRITY_VERIFIED)
        finally:
            conn.close()
        # A second connect re-runs the schema guard without duplicating it.
        fresh = self._legacy_database_without_the_column()
        try:
            state_store.ensure_state_schema(fresh)
            state_store.ensure_state_schema(fresh)
            self.assertEqual(self._stored_counts(fresh), {"a": None})
        finally:
            fresh.close()

    def test_the_first_trim_repairs_every_count_and_removes_legacy_orphans(self):
        conn = self._database([3, 2, 5], orphans=4)
        try:
            state_store._trim_persisted_playlists(conn)
            truth = self._true_counts(conn)
            self.assertNotIn("gone", truth, "the orphan sweep left parentless rows behind")
            self.assertEqual(self._stored_counts(conn), truth)
            self.assertEqual(truth, {"playlist-000": 3, "playlist-001": 2, "playlist-002": 5})
        finally:
            conn.close()

    def test_a_trusted_within_budget_library_issues_no_child_table_statement(self):
        conn = self._database([3, 2, 1])
        try:
            # The first pass is what a fresh or upgraded database pays: sweep,
            # marker, and one authoritative re-count.
            state_store._trim_persisted_playlists(conn)
            rows = self._child_rows(conn)
            # The second pass is what every later save pays.
            counter = _CountingConnection(conn)
            state_store._trim_persisted_playlists(counter)
            self.assertEqual([sql for sql in counter.statements if "playlist_tracks" in sql], [],
                             "the trim still reads the child table it claims to skip")
            self.assertEqual(len(counter.statements), 2, "%r" % counter.statements)
            self.assertEqual(counter.deletes, [])
            self.assertEqual(self._child_rows(conn), rows)
        finally:
            conn.close()

    def test_a_trusted_playlist_still_rechecks_its_own_cap(self):
        # Every parent row is marked verified and the total is nowhere near the
        # budget, so only the per-playlist arm of the predicate can notice that
        # this library needs trimming.
        conn = self._database([9, 1, 1], stamp=9, verified=True)
        try:
            self._caps_are(10, 4, 1000000)
            state_store._trim_persisted_playlists(conn)
            self.assertEqual(len(self._child_rows(conn)), 6,
                             "a playlist over its own cap was trusted into staying whole")
            self.assertEqual(self._stored_counts(conn), self._true_counts(conn))
            self.assertEqual(self._stored_counts(conn),
                             {"playlist-000": 4, "playlist-001": 1, "playlist-002": 1})
        finally:
            conn.close()

    def test_a_trusted_library_still_rechecks_the_total_budget(self):
        conn = self._database([4, 4], stamp=4, verified=True)
        try:
            # Two playlists each exactly at the per-playlist cap, but together one
            # row over the shared budget: only the cumulative arm can see it.
            self._caps_are(10, 4, 7)
            state_store._trim_persisted_playlists(conn)
            self.assertEqual(len(self._child_rows(conn)), 7,
                             "the shared track-id budget stopped being checked")
            self.assertEqual(self._stored_counts(conn),
                             {"playlist-000": 4, "playlist-001": 3})
            self.assertEqual(self._stored_counts(conn), self._true_counts(conn))
        finally:
            conn.close()

    def test_an_unknown_count_never_reads_as_an_empty_playlist(self):
        conn = self._database([3, 0, 5], stamp=None, verified=True)
        try:
            counter = _CountingConnection(conn)
            state_store._trim_persisted_playlists(counter)
            self.assertEqual(self._stored_counts(conn),
                             {"playlist-000": 3, "playlist-001": 0, "playlist-002": 5})
            self.assertTrue(
                any("SET track_count = (" in sql for sql in counter.statements),
                "an unknown count was believed instead of re-derived: %r" % counter.statements,
            )
        finally:
            conn.close()

    def test_surplus_playlists_never_take_the_fast_path(self):
        conn = self._database([1, 1, 1, 1, 1], stamp=1, verified=True)
        try:
            # The counts say there is nothing to do; only the look-ahead row
            # proves that the table still holds playlists past the cap.
            self._caps_are(3, 4, 7)
            state_store._trim_persisted_playlists(conn)
            kept = [row[0] for row in self._parent_rows(conn)]
            self.assertEqual(kept, ["playlist-000", "playlist-001", "playlist-002"],
                             "playlists beyond the retention cap survived the trim")
            self.assertEqual(len(self._child_rows(conn)), 3)
        finally:
            conn.close()

    def test_a_library_without_the_marker_is_never_trusted(self):
        # Every stored count here is small, correct, and inside both budgets, so
        # the only thing that can hold this library on the slow path is the
        # marker saying nobody has looked for parentless child rows yet.
        conn = self._database([2, 2], stamp=2)
        try:
            counter = _CountingConnection(conn)
            state_store._trim_persisted_playlists(counter)
            self.assertTrue(
                any("NOT IN" in sql for sql in counter.statements),
                "an unverified library took the fast path: %r" % counter.statements,
            )
            settled = self._child_rows(conn)
            second = _CountingConnection(conn)
            state_store._trim_persisted_playlists(second)
            self.assertEqual([sql for sql in second.statements if "playlist_tracks" in sql], [],
                             "the sweep repeated after it had been recorded")
            self.assertEqual(self._child_rows(conn), settled)
        finally:
            conn.close()

    def test_trim_matches_the_reference_whatever_the_parent_row_claimed(self):
        shapes = [
            ([3, 2, 5], None),   # an upgraded database knows nothing
            ([3, 2, 5], 1),      # counts far below the rows on disk
            ([3, 2, 5], 9),      # counts far above them
            ([1, 4, 4], None),   # the total cap is what bites
            ([0, 4, 4], 4),      # an empty playlist must not spend the budget
            ([9, 1, 1], 2),      # one playlist over its own cap
        ]
        original = self._caps()
        try:
            self._use_tiny_caps()
            for counts, stamp in shapes:
                label = "counts=%s stamp=%r" % (counts, stamp)
                current = self._database(counts, stamp=stamp)
                reference = self._database(counts, stamp=stamp)
                try:
                    state_store._trim_persisted_playlists(current)
                    self._reference_trim(reference)
                    self.assertEqual(self._child_rows(current), self._child_rows(reference),
                                     "child rows differ for %s" % label)
                    self.assertEqual(self._parent_rows(current), self._parent_rows(reference),
                                     "playlists differ for %s" % label)
                    self.assertEqual(self._stored_counts(current), self._true_counts(current),
                                     "a count survived the trim without being repaired for %s" % label)
                    settled = self._child_rows(current)
                    counter = _CountingConnection(current)
                    state_store._trim_persisted_playlists(counter)
                    self.assertEqual(self._child_rows(current), settled,
                                     "a second trim changed the library for %s" % label)
                    self.assertEqual([sql for sql in counter.statements if "playlist_tracks" in sql], [],
                                     "the second trim still scanned for %s" % label)
                finally:
                    current.close()
                    reference.close()
        finally:
            (
                state_store.MAX_PERSISTED_PLAYLISTS,
                state_store.MAX_PERSISTED_TRACK_IDS,
                state_store.MAX_PERSISTED_PLAYLIST_TRACK_IDS_TOTAL,
            ) = original

    def test_an_overstated_count_cannot_delete_a_single_row(self):
        conn = self._database([1, 1, 1], stamp=9)
        original = self._caps()
        try:
            self._use_tiny_caps()
            before = self._child_rows(conn)
            state_store._trim_persisted_playlists(conn)
            self.assertEqual(self._child_rows(conn), before)
            self.assertEqual(self._stored_counts(conn), self._true_counts(conn))
        finally:
            (
                state_store.MAX_PERSISTED_PLAYLISTS,
                state_store.MAX_PERSISTED_TRACK_IDS,
                state_store.MAX_PERSISTED_PLAYLIST_TRACK_IDS_TOTAL,
            ) = original
            conn.close()

    def test_the_orphan_sweep_is_paid_once(self):
        first = self._database([2], orphans=3)
        try:
            counter = _CountingConnection(first)
            state_store._trim_persisted_playlists(counter)
            self.assertIn("playlist_tracks", " ".join(counter.deletes))
            self.assertNotIn("gone", self._true_counts(first))
            second = _CountingConnection(first)
            state_store._trim_persisted_playlists(second)
            self.assertEqual(second.deletes, [], "the sweep repeated: %r" % second.statements)
        finally:
            first.close()

    def test_both_save_paths_record_their_own_child_row_count(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root}
            saved = save_user_state(config, {
                "favorites": [],
                "playlists": [
                    {"id": "night", "name": "Night", "trackIds": ["a", "b", "c"]},
                    {"id": "empty", "name": "Empty", "trackIds": []},
                ],
                "playback": {},
                "ui": {},
            })
            with state_store.state_db_connect(config) as conn:
                conn.row_factory = sqlite3.Row
                self.assertEqual(
                    {row["id"]: row["track_count"] for row in conn.execute("SELECT id, track_count FROM playlists")},
                    {"night": 3, "empty": 0},
                )
                self.assertEqual(
                    {row["playlist_id"]: int(row["count"]) for row in conn.execute(
                        "SELECT playlist_id, COUNT(*) AS count FROM playlist_tracks GROUP BY playlist_id")},
                    {"night": 3},
                )
            save_user_state(config, {
                "favorites": [],
                "playlists": [],
                "playback": {},
                "ui": {},
                "changes": {
                    "favorites_add": [],
                    "favorites_remove": [],
                    "playlist_upserts": [{"id": "night", "name": "Night", "trackIds": ["a", "b", "d", "e"]}],
                    "playlist_delete": ["empty"],
                },
            }, saved["revision"] + 99)
            with state_store.state_db_connect(config) as conn:
                conn.row_factory = sqlite3.Row
                self.assertEqual(
                    {row["id"]: row["track_count"] for row in conn.execute("SELECT id, track_count FROM playlists")},
                    {"night": 4},
                )

    def test_a_second_save_cannot_understate_its_own_rows(self):
        # The fast path believes the number a writer recorded, so the writer has
        # to record it truthfully: a second full save that claimed fewer rows
        # than it inserted would keep the library over its cap forever.
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root}
            self._caps_are(10, 4, 100)
            save_user_state(config, {
                "favorites": [],
                "playlists": [{"id": "night", "name": "Night", "trackIds": ["a", "b"]}],
                "playback": {},
                "ui": {},
            })
            save_user_state(config, {
                "favorites": [],
                "playlists": [{"id": "night", "name": "Night",
                               "trackIds": ["a", "b", "c", "d", "e", "f"]}],
                "playback": {},
                "ui": {},
            })
            with state_store.state_db_connect(config) as conn:
                conn.row_factory = sqlite3.Row
                self.assertEqual(self._stored_counts(conn), self._true_counts(conn))
                self.assertEqual(self._stored_counts(conn), {"night": 4})
                self.assertEqual(int(conn.execute("SELECT COUNT(*) FROM playlist_tracks").fetchone()[0]), 4)

    def test_a_stale_delta_cannot_understate_its_own_rows(self):
        # Same rule on the merge path, which is the one that runs on every
        # ordinary client edit while the marker is already set.
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root}
            self._caps_are(10, 4, 100)
            saved = save_user_state(config, {
                "favorites": [],
                "playlists": [{"id": "night", "name": "Night", "trackIds": ["a", "b"]}],
                "playback": {},
                "ui": {},
            })
            save_user_state(config, {
                "favorites": [],
                "playlists": [],
                "playback": {},
                "ui": {},
                "changes": {
                    "favorites_add": [],
                    "favorites_remove": [],
                    "playlist_upserts": [{"id": "night", "name": "Night",
                                          "trackIds": ["a", "b", "c", "d", "e", "f"]}],
                    "playlist_delete": [],
                },
            }, saved["revision"] + 99)
            with state_store.state_db_connect(config) as conn:
                conn.row_factory = sqlite3.Row
                self.assertEqual(self._stored_counts(conn), self._true_counts(conn))
                self.assertEqual(self._stored_counts(conn), {"night": 4})
                self.assertEqual(int(conn.execute("SELECT COUNT(*) FROM playlist_tracks").fetchone()[0]), 4)

    def test_no_count_is_saved_when_a_save_fails(self):
        # A rolled back write must not leave a parent claiming rows it does not
        # have; the count travels in the same transaction as the child rows.
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root}
            save_user_state(config, {
                "favorites": [],
                "playlists": [{"id": "keep", "name": "Keep", "trackIds": ["a", "b"]}],
                "playback": {},
                "ui": {},
            })
            original = state_store._trim_persisted_favorites
            try:
                def boom(conn):
                    raise RuntimeError("trim failed")
                state_store._trim_persisted_favorites = boom
                with self.assertRaises(RuntimeError):
                    save_user_state(config, {
                        "favorites": [],
                        "playlists": [{"id": "keep", "name": "Keep", "trackIds": ["a"]}],
                        "playback": {},
                        "ui": {},
                    })
            finally:
                state_store._trim_persisted_favorites = original
            with state_store.state_db_connect(config) as conn:
                conn.row_factory = sqlite3.Row
                self.assertEqual(
                    {row["id"]: row["track_count"] for row in conn.execute("SELECT id, track_count FROM playlists")},
                    {"keep": 2},
                )

    def test_the_grouped_count_scan_is_gone_from_the_writer(self):
        source = self._source()
        self.assertNotIn("GROUP BY playlist_id", source,
                         "the trim counts every child row on each save again")
        self.assertIn("UPDATE playlists SET track_count = (", source,
                      "the authoritative repair statement disappeared")

    def test_only_state_store_writes_child_rows_and_both_maintain_the_count(self):
        source = self._source()
        self.assertEqual(source.count("INSERT INTO playlist_tracks"), 2,
                         "a new writer path appeared without a review of the count rule")
        self.assertEqual(source.count("INSERT INTO playlists("), 2)
        for statement in source.split("INSERT INTO playlists(")[1:]:
            self.assertIn("track_count", statement.splitlines()[0],
                          "a playlist insert stopped recording its own row count")
        writers = []
        for directory, _, names in os.walk(self.SERVER_DIR):
            for name in names:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(directory, name)
                with io.open(path, encoding="utf-8") as handle:
                    if "INSERT INTO playlist_tracks" in handle.read():
                        writers.append(os.path.basename(path))
        self.assertEqual(writers, ["state_store.py"],
                         "%r add playlist_tracks rows outside the counted writer" % writers)

    def _reference_trim(self, conn):
        """The pre-R65 algorithm: one DELETE plus one COUNT per stored playlist."""
        keep_rows = conn.execute(
            "SELECT id FROM playlists ORDER BY created_at ASC, id ASC LIMIT ?",
            (state_store.MAX_PERSISTED_PLAYLISTS,),
        ).fetchall()
        keep_ids = [row["id"] for row in keep_rows]
        if not keep_ids:
            conn.execute("DELETE FROM playlist_tracks")
            conn.execute("DELETE FROM playlists")
            return
        conn.execute(
            "DELETE FROM playlist_tracks WHERE playlist_id NOT IN ("
            "SELECT id FROM playlists ORDER BY created_at ASC, id ASC LIMIT ?"
            ")",
            (state_store.MAX_PERSISTED_PLAYLISTS,),
        )
        conn.execute(
            "DELETE FROM playlists WHERE id NOT IN ("
            "SELECT id FROM playlists ORDER BY created_at ASC, id ASC LIMIT ?"
            ")",
            (state_store.MAX_PERSISTED_PLAYLISTS,),
        )
        remaining = state_store.MAX_PERSISTED_PLAYLIST_TRACK_IDS_TOTAL
        for playlist_id in keep_ids:
            keep_count = min(state_store.MAX_PERSISTED_TRACK_IDS, remaining)
            conn.execute(
                "DELETE FROM playlist_tracks WHERE playlist_id = ? AND rowid NOT IN ("
                "SELECT rowid FROM playlist_tracks WHERE playlist_id = ? "
                "ORDER BY position ASC, rowid ASC LIMIT ?"
                ")",
                (playlist_id, playlist_id, keep_count),
            )
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM playlist_tracks WHERE playlist_id = ?",
                (playlist_id,),
            ).fetchone()
            count = int(row["count"] or 0) if row else 0
            remaining = max(0, remaining - min(keep_count, count))


class _ReplayCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows

    def __iter__(self):
        return iter(self._rows)


class _CountingConnection:
    """Proxy that records every statement the trim issues, without changing it."""

    def __init__(self, conn):
        self.conn = conn
        self.statements = []

    @property
    def deletes(self):
        return [sql for sql in self.statements if sql.lstrip().upper().startswith("DELETE")]

    def execute(self, sql, parameters=()):
        self.statements.append(sql)
        cursor = self.conn.execute(sql, parameters)
        if cursor.description is None:
            return cursor
        return _ReplayCursor(cursor.fetchall())


if __name__ == "__main__":
    unittest.main()

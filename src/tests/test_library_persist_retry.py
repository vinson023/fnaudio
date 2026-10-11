"""R201 - a locked index write parks its snapshot instead of losing the scan.

Device evidence: 62,684 tracks, and one
``sqlite3.OperationalError: database is locked`` at the end of a multi-minute
scan.  The old code raised, the finished scan was thrown away, ``scanning``
stayed true and the next watcher tick re-walked the whole tree - which is why a
folder click kept waiting behind a scan that never ended.
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "app/server")

import cover_cache
import library
import library_persist_retry as retry_model


class TransientLockTests(unittest.TestCase):
    def test_only_lock_texts_are_worth_waiting_for(self):
        self.assertTrue(retry_model.is_transient_lock(sqlite3.OperationalError("database is locked")))
        self.assertTrue(retry_model.is_transient_lock("sqlite3.OperationalError: database is locked"))
        self.assertTrue(retry_model.is_transient_lock("cannot begin deferred transaction: database table is locked"))
        self.assertFalse(retry_model.is_transient_lock(OSError("readonly database")))
        self.assertFalse(retry_model.is_transient_lock("attempt to write a readonly database"))
        self.assertFalse(retry_model.is_transient_lock(None))
        self.assertFalse(retry_model.is_transient_lock(""))


class PersistRetrySlotTests(unittest.TestCase):
    def make_slot(self, limit=3, base_delay=60.0, max_delay=300.0):
        return retry_model.PersistRetrySlot(limit=limit, base_delay=base_delay, max_delay=max_delay)

    def test_empty_snapshots_and_unknown_signatures_are_refused(self):
        slot = self.make_slot()
        self.assertFalse(slot.stage([], "sig", 1000.0))
        self.assertFalse(slot.stage([{"id": "a"}], "", 1000.0))
        self.assertFalse(slot.stage([{"id": "a"}], None, 1000.0))
        self.assertFalse(slot.stage(None, "sig", 1000.0))
        self.assertFalse(slot.pending())

    def test_a_parked_snapshot_waits_for_its_base_delay(self):
        slot = self.make_slot()
        self.assertTrue(slot.stage([{"id": "a"}], "sig", 1000.0))
        self.assertFalse(slot.due(1059.0))
        self.assertTrue(slot.due(1060.0))
        self.assertEqual(slot.snapshot(), ([{"id": "a"}], "sig"))

    def test_the_same_signature_does_not_grant_a_fresh_budget(self):
        slot = self.make_slot()
        slot.stage([{"id": "a"}], "sig", 1000.0)
        slot.note_failure(1060.0)
        slot.stage([{"id": "a"}], "sig", 1060.0)
        self.assertEqual(slot.attempts, 1)
        slot.stage([{"id": "b"}], "newer-signature", 1060.0)
        self.assertEqual(slot.attempts, 0)
        self.assertEqual(slot.due_at, 1120.0)

    def test_the_backoff_grows_and_is_capped(self):
        slot = self.make_slot(limit=9)
        slot.stage([{"id": "a"}], "sig", 1000.0)
        delays = []
        now = 1000.0
        for _ in range(6):
            slot.note_failure(now)
            if not slot.pending():
                break
            delays.append(round(slot.due_at - now, 3))
            now = slot.due_at
        # stage() already granted the first base wait, so the ladder starts at
        # two base intervals and then sticks to the cap.
        self.assertEqual(delays, [120.0, 240.0, 300.0, 300.0, 300.0, 300.0])

    def test_the_budget_is_bounded(self):
        slot = self.make_slot()
        slot.stage([{"id": "a"}], "sig", 1000.0)
        self.assertTrue(slot.note_failure(1060.0))
        self.assertTrue(slot.note_failure(1120.0))
        self.assertFalse(slot.note_failure(1180.0))
        self.assertFalse(slot.pending())
        self.assertTrue(slot.gave_up)
        self.assertFalse(slot.due(9999.0))

    def test_status_reports_the_countdown(self):
        slot = self.make_slot()
        slot.stage([{"id": "a"}], "sig", 1000.0)
        status = slot.status(1030.0)
        self.assertEqual(
            status,
            {"pending": True, "attempts": 0, "limit": 3, "next_in": 30, "gave_up": False},
        )
        slot.note_success(1060.0)
        self.assertEqual(slot.status(1060.0)["pending"], False)


class LibraryPersistRetryTests(unittest.TestCase):
    def setUp(self):
        self.slot = library.LIBRARY_PERSIST_RETRY
        self.saved_state = (self.slot.items, self.slot.signature, self.slot.attempts,
                            self.slot.due_at, self.slot.gave_up)
        self.items = [{"id": "track-1", "path": "/music/a.flac", "folder": "A"}]
        self.counters = dict(library.LIBRARY_CACHE_FAILURES)
        self.details = dict(library.LIBRARY_CACHE_FAILURE_DETAILS)
        self.cache_items = list(library.MUSIC_CACHE["items"])
        self.signature = library.FS_CACHE["signature"]
        self.running = library.SCAN_STATE.get("running", False)

    def tearDown(self):
        (items, signature, attempts, due_at, gave_up) = self.saved_state
        self.slot.items, self.slot.signature = items, signature
        self.slot.attempts, self.slot.due_at, self.slot.gave_up = attempts, due_at, gave_up
        library.LIBRARY_CACHE_FAILURES.clear()
        library.LIBRARY_CACHE_FAILURES.update(self.counters)
        library.LIBRARY_CACHE_FAILURE_DETAILS.clear()
        library.LIBRARY_CACHE_FAILURE_DETAILS.update(self.details)
        library.MUSIC_CACHE["items"] = self.cache_items
        library.FS_CACHE["signature"] = self.signature
        library.SCAN_STATE["running"] = self.running

    def config(self, root):
        return {"cache_dir": os.path.join(root, "cache"), "library_paths": [os.path.join(root, "music")]}

    def stage(self, exc):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(library, "secure_directory"), \
                 patch.object(library, "save_items_to_sqlite", side_effect=exc):
                self.assertFalse(library.save_library_cache(self.config(root), self.items, "sig"))

    def test_a_lost_write_race_parks_the_snapshot(self):
        self.stage(sqlite3.OperationalError("database is locked"))
        self.assertTrue(self.slot.pending())
        self.assertEqual(self.slot.signature, "sig")
        self.assertEqual(library.library_cache_failure_status()["save"], self.counters["save"] + 1)
        self.assertIn("database is locked", library.library_cache_failure_detail("save"))

    def test_a_permission_error_parks_nothing(self):
        self.stage(sqlite3.OperationalError("attempt to write a readonly database"))
        self.assertFalse(self.slot.pending())

    def test_a_parked_snapshot_is_not_replayed_early(self):
        self.stage(sqlite3.OperationalError("database is locked"))
        with tempfile.TemporaryDirectory() as root:
            with patch.object(library, "save_items_to_sqlite") as write:
                self.assertFalse(library.retry_pending_library_persist(self.config(root)))
            write.assert_not_called()

    def replay_ok(self, config):
        with patch.object(library, "save_items_to_sqlite") as write, \
             patch.object(library, "secure_directory"), \
             patch.object(library, "atomic_write_json"), \
             patch.object(cover_cache, "prewarm_library_thumbnails"):
            result = library.retry_pending_library_persist(config)
        return result, write

    def test_a_due_snapshot_is_replayed_and_cleared(self):
        self.stage(sqlite3.OperationalError("database is locked"))
        with tempfile.TemporaryDirectory() as root:
            config = self.config(root)
            library.FS_CACHE["signature"] = "sig"
            self.slot.due_at = 0.0
            result, write = self.replay_ok(config)
            self.assertTrue(result)
            self.assertEqual(write.call_count, 1)
            self.assertFalse(self.slot.pending())
            self.assertEqual(self.slot.attempts, 0)

    def test_a_scan_in_flight_defers_the_replay(self):
        self.stage(sqlite3.OperationalError("database is locked"))
        with tempfile.TemporaryDirectory() as root:
            config = self.config(root)
            library.FS_CACHE["signature"] = "sig"
            library.SCAN_STATE["running"] = True
            self.slot.due_at = 0.0
            with patch.object(library, "save_items_to_sqlite") as write:
                self.assertFalse(library.retry_pending_library_persist(config))
            write.assert_not_called()
            self.assertTrue(self.slot.pending())

    def test_a_superseded_snapshot_is_dropped(self):
        self.stage(sqlite3.OperationalError("database is locked"))
        with tempfile.TemporaryDirectory() as root:
            library.FS_CACHE["signature"] = "a-newer-scan-already-won"
            self.slot.due_at = 0.0
            with patch.object(library, "save_items_to_sqlite") as write:
                self.assertFalse(library.retry_pending_library_persist(self.config(root)))
            write.assert_not_called()
            self.assertFalse(self.slot.pending())

    def test_a_still_locked_retry_consumes_the_budget(self):
        self.stage(sqlite3.OperationalError("database is locked"))
        attempts = 0
        with tempfile.TemporaryDirectory() as root:
            config = self.config(root)
            library.FS_CACHE["signature"] = "sig"
            with patch.object(library, "save_items_to_sqlite",
                              side_effect=sqlite3.OperationalError("database is locked")) as write:
                while self.slot.pending():
                    self.slot.due_at = 0.0
                    self.assertFalse(library.retry_pending_library_persist(config))
                    attempts += 1
                    self.assertLessEqual(attempts, self.slot.limit + 2)
            self.assertEqual(write.call_count, attempts)
        self.assertTrue(self.slot.gave_up)
        self.assertEqual(self.slot.limit, attempts)

    def test_nothing_parked_means_no_replay(self):
        self.slot.clear()
        with tempfile.TemporaryDirectory() as root:
            with patch.object(library, "save_items_to_sqlite") as write:
                self.assertFalse(library.retry_pending_library_persist(self.config(root)))
            write.assert_not_called()

    def test_the_status_endpoint_reports_the_parked_snapshot(self):
        self.stage(sqlite3.OperationalError("database is locked"))
        status = library.library_persist_retry_status()
        self.assertTrue(status["pending"])
        self.assertGreater(status["next_in"], 0)
        with tempfile.TemporaryDirectory() as root:
            payload = library.library_status(self.config(root))
        self.assertEqual(payload["index_persist"]["pending"], True)


if __name__ == "__main__":
    unittest.main()

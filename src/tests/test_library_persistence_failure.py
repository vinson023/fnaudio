"""R201 - a failed index save has to say which error it was and must not lose the scan.

The device logged ``fnAudio library scan failed: library index persistence
failed`` ninety-eight times in a row.  ``save_library_cache`` swallowed the
exception class and message, so nobody could tell a SQLite write-lock timeout
from a permission error, and every retry of the loop stayed undiagnosable.
"""

import os
import sqlite3
import sys
import unittest

sys.path.insert(0, "app/server")

import library


class PersistenceFailureDetailTests(unittest.TestCase):
    def setUp(self):
        original = dict(library.LIBRARY_CACHE_FAILURE_DETAILS)
        counters = dict(library.LIBRARY_CACHE_FAILURES)

        def restore():
            library.LIBRARY_CACHE_FAILURE_DETAILS.clear()
            library.LIBRARY_CACHE_FAILURE_DETAILS.update(original)
            library.LIBRARY_CACHE_FAILURES.clear()
            library.LIBRARY_CACHE_FAILURES.update(counters)

        self.addCleanup(restore)
        library.LIBRARY_CACHE_FAILURE_DETAILS.update({"load": "", "save": ""})

    def test_the_reason_is_kept_per_kind(self):
        library._record_library_cache_failure("save", sqlite3.OperationalError("database is locked"))
        library._record_library_cache_failure("load", OSError("cache unreadable"))
        self.assertEqual(
            library.library_cache_failure_detail("save"),
            "sqlite3.OperationalError: database is locked",
        )
        self.assertEqual(library.library_cache_failure_detail("load"), "OSError: cache unreadable")
        self.assertEqual(library.library_cache_failure_status(), {"load": 1, "save": 1})

    def test_the_persistence_message_carries_the_reason(self):
        library._record_library_cache_failure("save", sqlite3.OperationalError("database is locked"))
        message = library.library_persistence_failure_message()
        self.assertTrue(message.startswith("library index persistence failed: "))
        self.assertIn("sqlite3.OperationalError", message)

    def test_the_persistence_message_stays_honest_without_a_reason(self):
        self.assertEqual(
            library.library_persistence_failure_message(),
            "library index persistence failed",
        )

    def test_unknown_kinds_are_rejected_on_both_sides(self):
        library._record_library_cache_failure("private", RuntimeError("/vol1/secret"))
        self.assertEqual(library.library_cache_failure_detail("private"), "")
        self.assertEqual(library.library_cache_failure_status(), {"load": 0, "save": 0})

    def test_the_detail_never_leaks_the_library_path(self):
        library._record_library_cache_failure(
            "save", OSError("unable to write /vol2/1000/music/../conf/library.sqlite3")
        )
        message = library.library_persistence_failure_message()
        self.assertNotIn("/vol2", message)
        self.assertIn("<path>", message)


class SourceWiringTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join("app", "server", "library.py"), encoding="utf-8") as handle:
            self.source = handle.read()

    def test_the_save_failure_passes_the_exception_through(self):
        body = self.source.split("def _save_library_cache_locked(")[1].split("def ")[0]
        self.assertIn('except (OSError, sqlite3.Error) as exc:', body)
        self.assertIn('_record_library_cache_failure("save", exc)', body)
        self.assertIn("_stage_library_persist_retry(exc, snapshot_items, snapshot_signature)", body)

    def test_snapshot_writers_are_serialized(self):
        wrapper = self.source.split("def save_library_cache(")[1].split("def ")[0]
        self.assertIn("with LIBRARY_PERSIST_SAVE_LOCK:", wrapper)
        self.assertIn("return _save_library_cache_locked(config, items, signature)", wrapper)

    def test_the_reason_is_still_reported_without_sacrificing_the_scan(self):
        self.assertIn("library_persistence_failure_message()", self.source)
        self.assertNotIn(
            "raise OSError(library_persistence_failure_message())", self.source,
            "raising here discarded a finished scan and re-walked the whole tree",
        )
        self.assertNotIn(
            'raise OSError("library index persistence failed")', self.source,
            "the bare message is what made ninety-eight lines useless",
        )
        scan_block = self.source.split('"\u4fdd\u5b58\u97f3\u4e50\u5e93\u7d22\u5f15"')[1].split("MUSIC_CACHE")[0]
        self.assertIn("if not save_library_cache(config, items, signature):", scan_block)
        self.assertIn("will be retried", scan_block)

    def test_the_watcher_replays_a_parked_snapshot(self):
        loop = self.source.split("def watch_library(")[1]
        self.assertIn("retry_pending_library_persist(config)", loop)
        self.assertIn('"index_persist": library_persist_retry_status(),', self.source)


if __name__ == "__main__":
    unittest.main()

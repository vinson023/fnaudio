"""R201 - the metadata writer must report its own writes, and a saturated queue
must not be prodded every fifteen seconds.

``library_self_write`` only helps if the writer actually records.  These checks
run the real methods (bound straight onto a stub, so no threads or database are
started) and keep the source-level wiring honest.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, "app/server")

import library_self_write
import metadata_queue_backlog_policy
from metadata_service import MetadataService


class _Writer:
    """Host for the unbound methods under test: no service, no threads."""

    def __init__(self):
        self._observed_queue_pressure = (0, 0)

    _note_self_write = MetadataService._note_self_write
    _note_queue_pressure = MetadataService._note_queue_pressure
    _queue_pressure = MetadataService._queue_pressure
    _queue_is_backlogged = MetadataService._queue_is_backlogged


class SelfWriteAccountingTests(unittest.TestCase):
    def setUp(self):
        library_self_write.clear()
        self.addCleanup(library_self_write.clear)
        self.writer = _Writer()

    def test_the_revision_written_by_us_is_recorded(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "song.flac")
            with open(path, "wb") as handle:
                handle.write(b"x" * 8)
            self.assertTrue(self.writer._note_self_write(path))
            stat = os.stat(path)
            self.assertTrue(library_self_write.matches(path, stat.st_mtime_ns, stat.st_size))

    def test_a_second_write_replaces_the_ledger_entry(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "song.flac")
            with open(path, "wb") as handle:
                handle.write(b"x" * 8)
            self.writer._note_self_write(path)
            first = os.stat(path).st_mtime_ns
            with open(path, "wb") as handle:
                handle.write(b"y" * 20)
            # Two writes can land inside one clock tick on a fast filesystem;
            # the ledger entry, not the timestamp, is what the test is about.
            os.utime(path, ns=(first + 10 ** 9, first + 10 ** 9))
            self.writer._note_self_write(path)
            stat = os.stat(path)
            self.assertNotEqual(stat.st_mtime_ns, first)
            self.assertTrue(library_self_write.matches(path, stat.st_mtime_ns, stat.st_size))
            self.assertFalse(library_self_write.matches(path, first, 8))

    def test_missing_or_empty_paths_are_ignored(self):
        self.assertFalse(self.writer._note_self_write(""))
        self.assertFalse(self.writer._note_self_write(None))
        self.assertFalse(self.writer._note_self_write(os.path.join(tempfile.gettempdir(), "r201-absent.flac")))
        self.assertEqual(library_self_write.tracked_count(), 0)


class QueuePressureTests(unittest.TestCase):
    def setUp(self):
        self.writer = _Writer()

    def test_unknown_pressure_fails_open_to_the_old_cadence(self):
        self.assertEqual(self.writer._queue_pressure(), (0, 0))
        self.assertFalse(self.writer._queue_is_backlogged())
        self.assertTrue(policy_allows_requeue(self.writer))

    def test_the_observed_ceiling_is_remembered(self):
        self.writer._note_queue_pressure(19988, 20000)
        self.assertEqual(self.writer._queue_pressure(), (19988, 20000))
        self.assertTrue(self.writer._queue_is_backlogged())
        self.assertFalse(policy_allows_requeue(self.writer))

    def test_garbage_counters_never_replace_a_good_reading(self):
        self.writer._note_queue_pressure(19988, 20000)
        for pending, limit in ((None, 20000), ("x", 20000), (5, 0), (-1, 20000), (5, None)):
            with self.subTest(pending=pending, limit=limit):
                self.writer._note_queue_pressure(pending, limit)
                self.assertEqual(self.writer._queue_pressure(), (19988, 20000))

    def test_the_counter_is_capped_not_trusted(self):
        self.writer._note_queue_pressure(10 ** 40, 20000)
        pending, limit = self.writer._queue_pressure()
        self.assertEqual(pending, metadata_queue_backlog_policy.MAX_QUEUE_COUNTER)
        self.assertEqual(limit, 20000)

    def test_a_reading_survives_a_mangled_attribute(self):
        self.writer._observed_queue_pressure = "corrupted"
        self.assertEqual(self.writer._queue_pressure(), (0, 0))


def policy_allows_requeue(writer):
    pending, limit = writer._queue_pressure()
    return metadata_queue_backlog_policy.requeue_allowed(pending, limit)


class SourceWiringTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join("app", "server", "metadata_service.py"), encoding="utf-8") as handle:
            self.source = handle.read()

    def test_both_success_returns_record_the_self_write(self):
        body = self.source.split("def _write_track_tags(self, track_id):")[1]
        body = body.split("def _write_track_tags_ffmpeg")[0]
        self.assertEqual(
            body.count("self._note_self_write(source)"), 2,
            "the native in-place save and the os.replace path are two different writers",
        )
        self.assertIn("os.replace(temporary, source)\n            self._note_self_write(source)", body)
        self.assertIn(
            "self._write_track_tags_native(source, extension, data):\n            self._note_self_write(source)",
            body,
        )

    def test_the_reconcile_cadence_comes_from_the_policy(self):
        self.assertIn(
            "due = metadata_queue_backlog_policy.should_run_reconcile(", self.source
        )
        self.assertIn("backlogged=self._queue_is_backlogged(),", self.source)
        self.assertNotIn(
            "time.monotonic() - self._last_reconcile_monotonic > 15", self.source,
            "the fifteen-second literal would re-open the saturated queue again",
        )

    def test_a_saturated_queue_does_not_reopen_terminal_jobs(self):
        self.assertIn(
            "if metadata_queue_backlog_policy.requeue_allowed(*self._queue_pressure()):\n"
            "                    self._requeue_expired(conn, now)",
            self.source,
        )

    def test_pressure_is_read_from_counters_already_in_hand(self):
        self.assertIn("self._note_queue_pressure(queue_state[\"pending\"], queue_state[\"limit\"])", self.source)
        self.assertIn("self._note_queue_pressure(pending, queue_limit)", self.source)


if __name__ == "__main__":
    unittest.main()

"""R204 - a folder click must not queue behind a rescan that never ends.

Device evidence on the NAS running 0.2.47 (7,387 directories, 75,662 files):
``change_detection`` reported ``polling`` with ``watched_directories`` 0, because
the fixed 4,096 watch ceiling made ``start()`` raise ENOSPC and the monitor threw
away every watch it already had.  Every 180 s tick therefore re-walked the whole
tree, and 28 of 30 samples of ``/api/library/status`` said ``scanning``: the
process spent 93 per cent of its time rescanning, and each pass ended in an index
save that failed with ``database is locked`` because a deferred transaction
upgrades without ever consulting ``busy_timeout``.  The requests behind a folder
click were queued behind exactly that loop, which is why it felt like half a
beat.

Each assertion below kills one link of the chain.
"""

import errno
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

import library
import library_self_write
from library_scan_file_policy import classify_filename

SERVER_DIR = os.path.dirname(os.path.abspath(library.__file__))


def source(name):
    with open(os.path.join(SERVER_DIR, name), "r", encoding="utf-8") as handle:
        return handle.read()


def function_body(text, marker):
    start = text.index(marker)
    rest = text[start + len(marker):]
    lines = rest.splitlines(True)
    body = []
    for line in lines:
        if line.strip() and not line.startswith((" ", "\t")):
            break
        body.append(line)
    return "".join(body)


class WatchBudgetTests(unittest.TestCase):
    def test_a_real_library_fits_inside_the_kernel_quota(self):
        self.assertGreaterEqual(library.inotify_watch_budget(216_508), 7_387)

    def test_the_budget_leaves_room_for_every_other_process(self):
        kernel = 216_508
        budget = library.inotify_watch_budget(kernel)
        self.assertLess(budget, kernel)
        self.assertGreaterEqual(kernel - budget, library.INOTIFY_WATCH_RESERVE_MINIMUM)
        self.assertEqual(budget, kernel - kernel // library.INOTIFY_WATCH_RESERVE_DIVISOR)

    def test_an_unreadable_quota_degrades_instead_of_truncating_the_tree(self):
        default = library.INOTIFY_KERNEL_WATCHES_DEFAULT
        for unusable in (0, -1, None, "many", True, 12.5):
            self.assertEqual(library.inotify_watch_budget(unusable), default)

    def test_the_hard_ceiling_still_clamps_a_generous_quota(self):
        self.assertEqual(
            library.inotify_watch_budget(10_000_000), library.MAX_LIBRARY_INOTIFY_WATCHES
        )
        self.assertEqual(library.inotify_watch_budget(216_508, ceiling=1_000), 1_000)

    def test_a_bogus_ceiling_falls_back_to_the_constant(self):
        self.assertEqual(
            library.inotify_watch_budget(216_508, ceiling=0),
            library.inotify_watch_budget(216_508),
        )

    def test_a_quota_smaller_than_the_reserve_watches_nothing(self):
        self.assertEqual(library.inotify_watch_budget(1_000), 0)

    def test_kernel_quota_reader(self):
        with tempfile.TemporaryDirectory() as workdir:
            path = os.path.join(workdir, "max_user_watches")
            with open(path, "w", encoding="ascii") as handle:
                handle.write("216508\n")
            self.assertEqual(library.read_kernel_inotify_watches(path), 216_508)
            with open(path, "w", encoding="ascii") as handle:
                handle.write("not-a-number")
            self.assertEqual(library.read_kernel_inotify_watches(path), 0)
        self.assertEqual(library.read_kernel_inotify_watches("/no/such/file"), 0)


class PartialWatchTests(unittest.TestCase):
    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.tree = self.workdir.name
        nested = self.tree
        for depth in range(3):
            nested = os.path.join(nested, "album-%d" % depth)
            os.mkdir(nested)

    def build_monitor(self, budget):
        monitor = library.LibraryChangeMonitor([self.tree])
        monitor._watch_budget = budget
        return monitor

    def test_running_out_of_watches_keeps_every_watch_already_taken(self):
        monitor = self.build_monitor(2)
        calls = []

        def add(path):
            calls.append(path)
            if len(calls) > 2:
                raise OSError(errno.ENOSPC, "no space left on device", path)

        monitor._watch_path = add
        monitor._add_tree(self.tree)
        self.assertTrue(monitor._partial)
        self.assertTrue(monitor.needs_scan())
        self.assertEqual(len(calls), 3)

    def test_a_different_watch_error_is_not_swallowed(self):
        monitor = self.build_monitor(100)

        def add(path):
            raise OSError(errno.EACCES, "permission denied", path)

        monitor._watch_path = add
        with self.assertRaises(OSError):
            monitor._add_tree(self.tree)
        self.assertFalse(monitor._partial)

    def test_a_runtime_enospc_degrades_without_disabling_the_monitor(self):
        monitor = self.build_monitor(10)
        monitor.available = True
        monitor._dirty = False
        monitor._watches[3] = "/music"
        monitor._add_tree = mock.Mock(
            side_effect=OSError(errno.ENOSPC, "limit", "/music/new")
        )
        encoded = b"new-album\0"
        payload = monitor.EVENT_HEADER.pack(
            3, monitor.IN_CREATE | monitor.IN_MOVED_TO | monitor.IN_ISDIR, 0, len(encoded)
        ) + encoded
        monitor._handle_events(payload)
        self.assertTrue(monitor.needs_scan())
        self.assertTrue(monitor._partial)
        self.assertTrue(monitor.available)

    def test_a_partial_tree_keeps_the_periodic_check_after_cleaning(self):
        monitor = self.build_monitor(10)
        monitor.available = True
        monitor._mark_partial()
        monitor.mark_clean(monitor.generation())
        self.assertFalse(monitor._dirty)
        self.assertTrue(monitor.needs_scan())

    def test_status_reports_the_degradation_and_the_budget(self):
        monitor = self.build_monitor(4096)
        status = monitor.status()
        self.assertFalse(status["partial"])
        self.assertEqual(status["watch_budget"], 4096)
        monitor._mark_partial()
        self.assertTrue(monitor.status()["partial"])


class OwnWriteEventTests(unittest.TestCase):
    def setUp(self):
        library_self_write.clear()
        self.addCleanup(library_self_write.clear)
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.music = os.path.join(self.workdir.name, "music")
        os.mkdir(self.music)
        self.monitor = library.LibraryChangeMonitor([self.music])
        self.monitor.available = True
        self.monitor._watches[3] = self.music

    def event(self, mask, name):
        encoded = name.encode("utf-8") + b"\0"
        return self.monitor.EVENT_HEADER.pack(
            3, mask, 0, len(encoded)
        ) + encoded

    def dirty_after(self, name, mask=0x00000008):
        self.monitor._dirty = False
        self.monitor._handle_events(self.event(mask, name))
        return self.monitor._dirty

    def test_the_staging_copy_is_not_a_library_change(self):
        self.assertFalse(self.dirty_after("song.flac.fnaudio-tagging.flac"))

    def test_a_revision_this_process_recorded_is_not_a_library_change(self):
        track = os.path.join(self.music, "song.flac")
        with open(track, "wb") as handle:
            handle.write(b"written by fnAudio")
        self.assertTrue(library_self_write.record_from_stat(track, os.stat(track)))
        self.assertFalse(self.dirty_after("song.flac"))

    def test_a_change_nobody_recorded_still_dirty_the_monitor(self):
        track = os.path.join(self.music, "other.flac")
        with open(track, "wb") as handle:
            handle.write(b"external edit")
        self.assertTrue(self.dirty_after("other.flac"))

    def test_a_removal_still_dirty_the_monitor(self):
        self.assertTrue(self.dirty_after("gone.flac", 0x00000200))

    def test_staging_files_are_never_indexed(self):
        supported = {".flac": "audio/flac", ".dsf": "audio/x-dsf"}
        self.assertEqual(classify_filename("a.flac.fnaudio-tagging.flac", supported), "ignore")
        self.assertEqual(classify_filename("a.flac", supported), "audio")
        self.assertEqual(classify_filename("a.dsf", supported), "audio")

    def test_the_staging_marker_is_matched_without_case(self):
        supported = {".flac": "audio/flac"}
        self.assertEqual(classify_filename("A.FLAC.FNAUDIO-TAGGING.FLAC", supported), "ignore")


class IndexPersistenceTests(unittest.TestCase):
    def test_the_writer_asks_for_the_write_lock_first(self):
        body = function_body(source("library.py"), "def library_db_writer(config):")
        self.assertIn("BEGIN IMMEDIATE", body)
        self.assertIn("if not conn.in_transaction:", body)
        self.assertLess(body.index("BEGIN IMMEDIATE"), body.index("yield conn"))

    def test_the_transaction_is_immediate_on_a_real_database(self):
        with tempfile.TemporaryDirectory() as workdir:
            config = {"cache_dir": workdir}
            with mock.patch.object(library, "_prepare_library_connection"):
                with library.library_db_writer(config) as conn:
                    self.assertTrue(conn.in_transaction)

    def test_the_tick_replays_a_parked_snapshot_before_it_walks_again(self):
        body = function_body(source("library.py"), "def watch_library(config, _stop_event=None):")
        self.assertLess(
            body.index("retry_pending_library_persist(config)"),
            body.index("refresh_library_if_changed(config, change_monitor=monitor)"),
        )


class TagWriterYieldTests(unittest.TestCase):
    def tearDown(self):
        library.SCAN_STATE["running"] = False

    def test_scan_running_is_readable_from_outside(self):
        library.SCAN_STATE["running"] = True
        self.assertTrue(library.library_scan_is_running())
        library.SCAN_STATE["running"] = False
        self.assertFalse(library.library_scan_is_running())

    def test_the_writer_checks_before_claiming_a_job(self):
        text = source("metadata_service.py")
        self.assertIn("library_scan_is_running,", text)
        body = function_body(text, "    def _run_tag_writer(self):")
        self.assertIn("if library_scan_is_running():", body)
        self.assertLess(
            body.index("if library_scan_is_running():"),
            body.index("self._claim_job(tag_writes_only=True)"),
        )


if __name__ == "__main__":
    unittest.main()

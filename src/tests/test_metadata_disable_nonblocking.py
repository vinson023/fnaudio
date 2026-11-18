"""Discriminating tests for a config save that must not wait on a tag write.

The owner's report: unchecking 「允许写入歌曲 Tag」 and pressing save took several
seconds before it succeeded.  The save path stopped the metadata lanes
synchronously, and stopping them joins whatever is in flight -- a tag write is a
synchronous file rewrite, so the HTTP response waited for that file.

``shutdown(wait=False)`` now signals the stop and hands the join to a reaper.
These tests pin the three halves of that: the save stops blocking, the reaper
really does finish the job, and ``start()`` still refuses to clear ``stop_event``
while the old generation is leaving (the reason the join exists at all).
"""

import os
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, "app/server")

import metadata_service
import server as server_module
from metadata_service import MetadataService


class BusyWorkerTests(unittest.TestCase):
    def setUp(self):
        self._root = tempfile.TemporaryDirectory()
        self.service = MetadataService({"cache_dir": self._root.name})
        self.release = threading.Event()
        self.worker = threading.Thread(
            target=lambda: self.release.wait(5.0),
            name="test-busy-tag-writer",
            daemon=True,
        )
        self.worker.start()
        self.service.tag_thread = self.worker

    def tearDown(self):
        self.release.set()
        self.worker.join(3.0)
        self.service.stop_event.clear()
        self._root.cleanup()

    def test_p1_the_save_path_returns_while_a_tag_write_is_still_running(self):
        started = time.monotonic()
        self.assertTrue(self.service.shutdown(wait=False))
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 0.5, "shutdown(wait=False) waited for the writer")
        self.assertTrue(self.worker.is_alive(), "the busy worker was joined anyway")

    def test_p1_the_reaper_finishes_the_join_after_the_writer_returns(self):
        self.service.shutdown(wait=False)
        reaper = self.service._shutdown_thread
        self.assertIsNotNone(reaper)
        self.assertTrue(reaper.is_alive())
        self.release.set()
        reaper.join(5.0)
        self.assertFalse(reaper.is_alive(), "the reaper never finished")
        self.assertFalse(self.worker.is_alive(), "the reaper left the worker running")

    def test_p1_a_new_generation_waits_for_the_leaving_one(self):
        """Without this wait ``start()`` clears ``stop_event`` under the old worker."""
        self.service.shutdown(wait=False)
        finished = threading.Event()

        def wait_for_it():
            self.service._await_pending_shutdown()
            finished.set()

        waiter = threading.Thread(target=wait_for_it, daemon=True)
        waiter.start()
        self.assertFalse(finished.wait(0.3), "_await_pending_shutdown returned early")
        self.release.set()
        self.assertTrue(finished.wait(5.0), "_await_pending_shutdown never returned")
        self.assertFalse(self.worker.is_alive())

    def test_p1_the_blocking_form_still_waits(self):
        """The flag has to be the difference, not a slower join everywhere."""
        timer = threading.Timer(0.3, self.release.set)
        timer.start()
        started = time.monotonic()
        self.service.shutdown()
        elapsed = time.monotonic() - started
        timer.cancel()
        self.assertGreaterEqual(elapsed, 0.25, "shutdown() no longer waits for the join")
        self.assertFalse(self.worker.is_alive())


class StartWiringTests(unittest.TestCase):
    def test_p1_start_consults_the_pending_reaper_before_rebuilding(self):
        """The guard is only real if ``start()`` actually calls it."""
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root})
            service.stop_event.set()
            calls = []
            service._await_pending_shutdown = lambda: calls.append(True)
            service._start_workers = lambda: None
            service.start()
        self.assertEqual(calls, [True], "start() rebuilt without waiting for the reaper")


class WorkerSyncTests(unittest.TestCase):
    class RecordingService:
        def __init__(self):
            self.calls = []

        def _has_live_workers(self):
            return True

        def shutdown(self, wait=True):
            self.calls.append(wait)
            return True

    def test_p1_turning_the_switch_off_asks_for_the_non_blocking_stop(self):
        service = self.RecordingService()
        server_module.sync_metadata_workers(service, {"metadata_enabled": False, "metadata_tag_write_enabled": False})
        self.assertEqual(service.calls, [False])

    def test_p1_turning_it_on_never_stops_the_lanes(self):
        service = self.RecordingService()
        started = []
        service.start = lambda: started.append(True)
        server_module.sync_metadata_workers(service, {"metadata_enabled": False, "metadata_tag_write_enabled": True})
        self.assertEqual(started, [True])
        self.assertEqual(service.calls, [])


if __name__ == "__main__":
    unittest.main()

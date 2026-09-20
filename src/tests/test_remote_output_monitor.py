import sys
import threading
import unittest
from types import SimpleNamespace
from unittest import mock
from unittest.mock import patch

sys.path.insert(0, "app/server")

from server import (DLNA_MONITOR_GUARD, _dlna_stalled_track_expired,
                    _dlna_stop_is_suppressed, _upnp_track_id_from_uri,
                    dlna_output_open, start_remote_output_monitor,
                    stop_remote_output_monitor)
import server


class RemoteOutputMonitorTests(unittest.TestCase):
    def test_remote_monitor_start_failure_clears_published_handles(self):
        original_stop = server.REMOTE_OUTPUT_MONITOR_STOP
        original_thread = server.REMOTE_OUTPUT_MONITOR_THREAD
        try:
            with patch("server.threading.Thread", side_effect=RuntimeError("no threads")):
                with self.assertRaises(RuntimeError):
                    start_remote_output_monitor(SimpleNamespace(config={}))
            self.assertIsNone(server.REMOTE_OUTPUT_MONITOR_STOP)
            self.assertIsNone(server.REMOTE_OUTPUT_MONITOR_THREAD)
        finally:
            server.REMOTE_OUTPUT_MONITOR_STOP = original_stop
            server.REMOTE_OUTPUT_MONITOR_THREAD = original_thread

    def test_remote_monitor_stop_sets_event_and_joins_thread(self):
        original_stop = server.REMOTE_OUTPUT_MONITOR_STOP
        original_thread = server.REMOTE_OUTPUT_MONITOR_THREAD
        try:
            stop_event = mock.Mock()
            thread = mock.Mock()
            thread.is_alive.return_value = True
            server.REMOTE_OUTPUT_MONITOR_STOP = stop_event
            server.REMOTE_OUTPUT_MONITOR_THREAD = thread
            stop_remote_output_monitor(timeout=1.5)
            stop_event.set.assert_called_once_with()
            thread.join.assert_called_once_with(timeout=1.5)
            self.assertIsNone(server.REMOTE_OUTPUT_MONITOR_STOP)
            self.assertIsNone(server.REMOTE_OUTPUT_MONITOR_THREAD)
            stop_remote_output_monitor()
        finally:
            server.REMOTE_OUTPUT_MONITOR_STOP = original_stop
            server.REMOTE_OUTPUT_MONITOR_THREAD = original_thread

    def test_remote_monitor_stop_uses_safe_timeout_for_non_finite_values(self):
        original_stop = server.REMOTE_OUTPUT_MONITOR_STOP
        original_thread = server.REMOTE_OUTPUT_MONITOR_THREAD
        try:
            server.REMOTE_OUTPUT_MONITOR_STOP = mock.Mock()
            server.REMOTE_OUTPUT_MONITOR_THREAD = mock.Mock()
            stop_remote_output_monitor(timeout=float("nan"))
            server.REMOTE_OUTPUT_MONITOR_THREAD = mock.Mock()
            server.REMOTE_OUTPUT_MONITOR_STOP = mock.Mock()
            stop_remote_output_monitor(timeout=float("inf"))
        finally:
            server.REMOTE_OUTPUT_MONITOR_STOP = original_stop
            server.REMOTE_OUTPUT_MONITOR_THREAD = original_thread

    def test_remote_monitor_does_not_restart_while_previous_thread_ignores_stop(self):
        original_stop = server.REMOTE_OUTPUT_MONITOR_STOP
        original_thread = server.REMOTE_OUTPUT_MONITOR_THREAD
        try:
            old_stop = mock.Mock()
            old_thread = mock.Mock()
            old_thread.is_alive.return_value = True
            server.REMOTE_OUTPUT_MONITOR_STOP = old_stop
            server.REMOTE_OUTPUT_MONITOR_THREAD = old_thread
            with patch("server.threading.Thread") as thread:
                with self.assertRaisesRegex(RuntimeError, "still stopping"):
                    start_remote_output_monitor(SimpleNamespace(config={}))
            thread.assert_not_called()
            old_stop.set.assert_called_once_with()
            old_thread.join.assert_called_once()
        finally:
            server.REMOTE_OUTPUT_MONITOR_STOP = original_stop
            server.REMOTE_OUTPUT_MONITOR_THREAD = original_thread

    def test_remote_monitor_generation_rejects_a_stopped_or_replaced_monitor(self):
        original_stop = server.REMOTE_OUTPUT_MONITOR_STOP
        original_generation = server.REMOTE_OUTPUT_MONITOR_GENERATION
        try:
            active = threading.Event()
            server.REMOTE_OUTPUT_MONITOR_STOP = active
            server.REMOTE_OUTPUT_MONITOR_GENERATION = 9
            self.assertTrue(server._remote_output_monitor_is_current(active, 9))
            active.set()
            self.assertFalse(server._remote_output_monitor_is_current(active, 9))
            active.clear()
            server.REMOTE_OUTPUT_MONITOR_GENERATION = 10
            self.assertFalse(server._remote_output_monitor_is_current(active, 9))
        finally:
            server.REMOTE_OUTPUT_MONITOR_STOP = original_stop
            server.REMOTE_OUTPUT_MONITOR_GENERATION = original_generation

    def test_concurrent_remote_monitor_start_leaves_one_published_monitor(self):
        original_stop = server.REMOTE_OUTPUT_MONITOR_STOP
        original_thread = server.REMOTE_OUTPUT_MONITOR_THREAD
        real_thread = threading.Thread
        entered = threading.Event()
        release = threading.Event()
        created = []

        class DelayedThread:
            def __init__(self, **_kwargs):
                created.append(self)

            def start(self):
                entered.set()
                release.wait(1)

            def join(self, **_kwargs):
                return None

        try:
            server.REMOTE_OUTPUT_MONITOR_STOP = None
            server.REMOTE_OUTPUT_MONITOR_THREAD = None
            with patch.object(server.threading, "Thread", DelayedThread):
                first = real_thread(target=start_remote_output_monitor, args=(SimpleNamespace(config={}),))
                first.start()
                self.assertTrue(entered.wait(1))
                second = real_thread(target=start_remote_output_monitor, args=(SimpleNamespace(config={}),))
                second.start()
                release.set()
                first.join(1)
                second.join(1)
            self.assertEqual(len(created), 2)
            self.assertIs(server.REMOTE_OUTPUT_MONITOR_THREAD, created[-1])
        finally:
            server.REMOTE_OUTPUT_MONITOR_STOP = original_stop
            server.REMOTE_OUTPUT_MONITOR_THREAD = original_thread

    def test_extracts_queue_track_id_from_renderer_uri(self):
        uri = "http://198.51.100.2:5666/upnp/media/abc%201/song.flac"
        self.assertEqual(_upnp_track_id_from_uri(uri), "abc 1")

    def test_ignores_unrelated_renderer_uri(self):
        self.assertEqual(_upnp_track_id_from_uri("http://example.test/music.flac"), "")

    def test_manual_stop_suppresses_renderer_auto_advance_race(self):
        original = dict(DLNA_MONITOR_GUARD)
        try:
            DLNA_MONITOR_GUARD.update({"target_id": "renderer-1", "suppress_stop_until": 50.0})
            self.assertTrue(_dlna_stop_is_suppressed("renderer-1", "STOPPED", now=49.0))
            self.assertFalse(_dlna_stop_is_suppressed("renderer-2", "STOPPED", now=49.0))
            self.assertFalse(_dlna_stop_is_suppressed("renderer-1", "STOPPED", now=51.0))
        finally:
            DLNA_MONITOR_GUARD.clear()
            DLNA_MONITOR_GUARD.update(original)

    def test_stalled_renderer_advances_only_after_known_track_duration(self):
        args = ("track-1", "track-1", "PLAYING", 0, 0, 100.0, 12.0)
        self.assertFalse(_dlna_stalled_track_expired(*args, now=113.9))
        self.assertTrue(_dlna_stalled_track_expired(*args, now=114.0))

    def test_stalled_renderer_guard_ignores_progress_pause_and_foreign_uri(self):
        self.assertFalse(_dlna_stalled_track_expired("track-1", "track-1", "PAUSED_PLAYBACK", 0, 0, 100, 12, now=120))
        self.assertFalse(_dlna_stalled_track_expired("track-1", "track-1", "PLAYING", 1, 0, 100, 12, now=120))
        self.assertFalse(_dlna_stalled_track_expired("track-1", "track-2", "PLAYING", 0, 0, 100, 12, now=120))

    def test_dlna_open_does_not_preload_next_uri(self):
        track = SimpleNamespace(track_id="track-1", item={"id": "track-1"})
        state = SimpleNamespace(target_id="renderer-1")
        pushed = []

        def capture_push(device, item, handler, next_item=None):
            pushed.append(next_item)
            return True, "started"

        with patch("server.find_upnp_device", return_value={"id": "renderer-1"}), patch(
            "server.soap_push", side_effect=capture_push
        ):
            result = dlna_output_open(track, state, {"handler": object()})

        self.assertTrue(result["ok"])
        self.assertEqual(pushed, [None])

    def test_dlna_open_seeks_after_loading_a_requested_position(self):
        track = SimpleNamespace(track_id="track-1", item={"id": "track-1"})
        state = SimpleNamespace(target_id="renderer-1")
        with patch("server.find_upnp_device", return_value={"id": "renderer-1"}), patch(
            "server.soap_push", return_value=(True, "started")
        ), patch("server.upnp_control", return_value=(True, "ok")) as control:
            result = dlna_output_open(track, state, {"handler": object(), "position": 12.5})

        self.assertTrue(result["ok"])
        control.assert_called_once_with({"id": "renderer-1"}, "seek", 12.5)


if __name__ == "__main__":
    unittest.main()

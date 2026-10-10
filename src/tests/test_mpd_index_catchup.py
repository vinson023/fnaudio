import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

from playback.models import PlaybackState, TrackRef
from playback.mpd_client import mpd_library_state_message, mpd_update_job_id
from playback.mpd_output import MpdOutput
from services.mpd_service import (
    MPD_INDEX_CATCHUP_POLL_SECONDS,
    MPD_INDEX_CATCHUP_TIMEOUT_SECONDS,
    MpdService,
)

ACK_AT_0 = "ACK [50@0] {addid} No such song"

# Measured on the fnOS host: MPD's own database held 23,483 songs while the
# fnAudio index held 62,684, and ``auto_update "no"`` meant nothing was ever
# going to close that gap by itself.
MPD_INDEXED = 23483
LIBRARY_SONGS = 62684


def make_service():
    temp = tempfile.TemporaryDirectory()
    config = {
        "library_paths": ["/vol2/1000/music"],
        "mpd_port": 56660,
        "cache_dir": temp.name,
    }
    with mock.patch.object(MpdService, "_select_port", return_value=56660), mock.patch.object(
        MpdService, "_find_binary", return_value="/usr/bin/mpd"
    ), mock.patch.object(MpdService, "_data_root", return_value=temp.name):
        service = MpdService(config)
    service._cleanup_temp = temp
    return service


class MpdUpdateJobIdTests(unittest.TestCase):
    def test_job_id_is_read_from_the_update_reply(self):
        self.assertEqual(mpd_update_job_id(["updating_db: 42"]), "42")

    def test_a_reply_that_names_no_job_or_is_not_a_reply_names_no_job(self):
        self.assertEqual(mpd_update_job_id([]), "")
        self.assertEqual(mpd_update_job_id(None), "")
        self.assertEqual(mpd_update_job_id(["state: stop"]), "")
        self.assertEqual(mpd_update_job_id(42), "")


class MpdIndexCatchupTests(unittest.TestCase):
    def test_a_catchup_runs_the_update_and_records_the_counters(self):
        service = make_service()
        self.addCleanup(service._cleanup_temp.cleanup)
        result = {
            "ok": True, "updated": True, "scope": "all", "timed_out": False, "job": "5",
            "indexed_before": MPD_INDEXED, "indexed_after": LIBRARY_SONGS,
        }
        with mock.patch.object(service.supervisor, "status", return_value={"running": True}), \
             mock.patch("services.mpd_service.mpd_update_and_wait", return_value=result) as waiter:
            accepted = service.request_index_catchup(reason="missing-entry")
            self.assertTrue(accepted["accepted"])
            thread = service._index_thread
            thread.join(timeout=2.0)
        self.assertFalse(thread.is_alive())
        state = service.index_status()
        self.assertEqual(waiter.call_args.kwargs["path"], "")
        self.assertEqual(state["reason"], "missing-entry")
        self.assertEqual(state["scope"], "all")
        self.assertEqual(state["job"], "5")
        self.assertEqual(state["indexed_before"], MPD_INDEXED)
        self.assertEqual(state["indexed_after"], LIBRARY_SONGS)
        self.assertTrue(state["updated"])
        self.assertFalse(state["running"])
        self.assertEqual(state["requests"], 1)

    def test_progress_is_visible_while_the_scan_runs(self):
        """The status endpoint has to be able to show a scan in flight."""
        service = make_service()
        self.addCleanup(service._cleanup_temp.cleanup)
        gate = threading.Event()
        release = threading.Event()

        def fake_wait(**kwargs):
            kwargs["on_progress"]({"available": True, "indexed": 900, "updating": True, "job": "9"})
            gate.set()
            release.wait(2.0)
            return {
                "ok": True, "updated": True, "scope": "all", "timed_out": False, "job": "9",
                "indexed_before": 0, "indexed_after": LIBRARY_SONGS,
            }

        with mock.patch.object(service.supervisor, "status", return_value={"running": True}), \
             mock.patch("services.mpd_service.mpd_update_and_wait", side_effect=fake_wait):
            service.request_index_catchup(reason="missing-entry")
            self.assertTrue(gate.wait(2.0))
            mid = service.index_status()
            release.set()
            thread = service._index_thread
            thread.join(timeout=2.0)
        self.assertEqual(mid["indexed_after"], 900)
        self.assertEqual(mid["job"], "9")
        self.assertTrue(mid["running"])
        self.assertEqual(service.index_status()["indexed_after"], LIBRARY_SONGS)

    def test_a_second_full_scan_is_refused_while_one_is_running(self):
        service = make_service()
        self.addCleanup(service._cleanup_temp.cleanup)
        gate = threading.Event()
        release = threading.Event()

        def fake_wait(**_kwargs):
            gate.set()
            release.wait(2.0)
            return {"ok": True, "updated": True, "scope": "all", "timed_out": False,
                    "job": "", "indexed_before": 0, "indexed_after": 0}

        with mock.patch.object(service.supervisor, "status", return_value={"running": True}), \
             mock.patch("services.mpd_service.mpd_update_and_wait", side_effect=fake_wait):
            first = service.request_index_catchup(reason="missing-entry")
            self.assertTrue(gate.wait(2.0))
            second = service.request_index_catchup(reason="missing-entry")
            release.set()
            service._index_thread.join(timeout=2.0)
        self.assertTrue(first["accepted"])
        self.assertFalse(second["accepted"])
        self.assertEqual(second["reason"], "already-running")
        self.assertEqual(service.index_status()["requests"], 1)

    def test_the_guard_is_taken_before_the_worker_can_start(self):
        """Two play failures in one second must queue one scan, not two.

        The flag is set before the thread is started, so a request landing in
        that window still sees the job as taken.  Guarding on thread liveness
        instead would queue a second full scan of a 60,000-file library while
        the first one is still starting.
        """
        service = make_service()
        self.addCleanup(service._cleanup_temp.cleanup)
        started = []

        class SlowThread:
            def __init__(self, target=None, args=(), name=None, daemon=None):
                self._target = target
                self._args = args
                self.name = name

            def start(self):
                started.append(self)

            def is_alive(self):
                return False

            def join(self, timeout=None):
                return None

        with mock.patch.object(service.supervisor, "status", return_value={"running": True}), \
             mock.patch("services.mpd_service.threading.Thread", SlowThread), \
             mock.patch("services.mpd_service.mpd_update_and_wait") as waiter:
            first = service.request_index_catchup(reason="missing-entry")
            second = service.request_index_catchup(reason="missing-entry")
        self.assertTrue(first["accepted"])
        self.assertFalse(second["accepted"])
        self.assertEqual(second["reason"], "already-running")
        self.assertEqual(len(started), 1)
        waiter.assert_not_called()
        self.assertEqual(service.index_status()["requests"], 1)

    def test_no_scan_is_queued_while_mpd_is_down(self):
        service = make_service()
        self.addCleanup(service._cleanup_temp.cleanup)
        with mock.patch.object(service.supervisor, "status", return_value={"running": False}), \
             mock.patch("services.mpd_service.mpd_update_and_wait") as waiter:
            result = service.request_index_catchup(reason="missing-entry")
        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"], "mpd-not-running")
        waiter.assert_not_called()
        self.assertFalse(service.index_status()["running"])

    def test_a_failed_update_is_recorded_as_an_error_not_a_success(self):
        service = make_service()
        self.addCleanup(service._cleanup_temp.cleanup)
        with mock.patch.object(service.supervisor, "status", return_value={"running": True}), \
             mock.patch("services.mpd_service.mpd_update_and_wait", side_effect=OSError("connection refused")):
            service.request_index_catchup(reason="missing-entry")
            service._index_thread.join(timeout=2.0)
        state = service.index_status()
        self.assertFalse(state["running"])
        self.assertFalse(state["updated"])
        self.assertTrue(state["timed_out"])
        self.assertIn("connection refused", state["error"])

    def test_a_worker_that_never_reports_back_still_releases_the_job(self):
        """A status read that raises must not strand every later catch-up."""
        service = make_service()
        self.addCleanup(service._cleanup_temp.cleanup)
        result = {"ok": True, "updated": True, "scope": "all", "timed_out": False,
                  "job": "1", "indexed_before": 0, "indexed_after": 0}
        with mock.patch.object(service.supervisor, "status", return_value={"running": True}), \
             mock.patch("services.mpd_service.mpd_update_and_wait", return_value=result), \
             mock.patch("services.mpd_service.nonnegative_int", side_effect=RuntimeError("boom")):
            service._index_loop("missing-entry", "")
        state = service.index_status()
        self.assertFalse(state["running"])
        # The counters are reported field by field, so the ones that did not
        # need the broken conversion still reach the status endpoint.
        self.assertTrue(state["updated"])
        self.assertEqual(state["job"], "1")
        retry = None
        with mock.patch.object(service.supervisor, "status", return_value={"running": True}), \
             mock.patch("services.mpd_service.mpd_update_and_wait", return_value=result) as waiter:
            retry = service.request_index_catchup(reason="missing-entry")
            service._index_thread.join(timeout=2.0)
        self.assertTrue(retry["accepted"])
        waiter.assert_called_once()

    def test_stop_cancels_the_index_worker(self):
        service = make_service()
        self.addCleanup(service._cleanup_temp.cleanup)
        gate = threading.Event()
        release = threading.Event()

        def fake_wait(**_kwargs):
            gate.set()
            release.wait(2.0)
            return {"ok": True, "updated": False, "scope": "all", "timed_out": True,
                    "job": "", "indexed_before": 0, "indexed_after": 0}

        with mock.patch.object(service.supervisor, "status", return_value={"running": True}), \
             mock.patch("services.mpd_service.mpd_update_and_wait", side_effect=fake_wait):
            service.request_index_catchup(reason="missing-entry")
            self.assertTrue(gate.wait(2.0))
            service._stop_index_catchup()
            self.assertTrue(service._index_stop.is_set())
            release.set()

    def test_a_cold_index_is_converged_and_a_populated_one_is_left_alone(self):
        service = make_service()
        self.addCleanup(service._cleanup_temp.cleanup)
        cases = [
            ({"available": True, "indexed": 0, "updating": False, "job": ""}, True),
            ({"available": True, "indexed": MPD_INDEXED, "updating": False, "job": ""}, False),
            ({"available": True, "indexed": 1775, "updating": True, "job": "4"}, False),
            ({"available": False, "indexed": 0, "updating": False, "job": ""}, False),
        ]
        for state, expected in cases:
            with mock.patch("services.mpd_service.mpd_library_state", return_value=state), \
                 mock.patch.object(service, "request_index_catchup") as request:
                service._maybe_converge_mpd_index("mpd-start")
            self.assertEqual(request.called, expected, state)
        # Disk-thrash guard: only the provably empty database may re-scan.
        with mock.patch("services.mpd_service.mpd_library_state",
                        return_value={"available": True, "indexed": 0, "updating": False, "job": ""}), \
             mock.patch.object(service, "request_index_catchup") as request:
            service._maybe_converge_mpd_index()
        self.assertEqual(request.call_args.kwargs["reason"], "mpd-start")

    def test_the_catchup_timeout_clears_the_measured_full_scan(self):
        """A bounded worker whose bound is below the scan it waits for is a lie.

        Measured on the fnOS host: the pathless ``update`` that this worker
        issues committed 580 seconds after it was issued, and it is the only
        command that mounts directories MPD has never seen.
        """
        self.assertGreaterEqual(MPD_INDEX_CATCHUP_TIMEOUT_SECONDS, 1200.0)
        self.assertLess(MPD_INDEX_CATCHUP_POLL_SECONDS, MPD_INDEX_CATCHUP_TIMEOUT_SECONDS)

    def test_no_second_convergence_is_queued_while_the_worker_is_running(self):
        """MPD's own flag is not the guard: a queued job is invisible until it starts."""
        service = make_service()
        self.addCleanup(service._cleanup_temp.cleanup)
        service._index_state["running"] = True
        with mock.patch("services.mpd_service.mpd_library_state",
                        return_value={"available": True, "indexed": 0, "updating": False, "job": ""}), \
             mock.patch.object(service, "request_index_catchup") as request:
            result = service._maybe_converge_mpd_index("mpd-start")
        self.assertFalse(request.called)
        self.assertEqual(result["reason"], "already-running")

    def test_status_publishes_the_index_job(self):
        service = make_service()
        self.addCleanup(service._cleanup_temp.cleanup)
        service._index_state.update({"running": True, "reason": "missing-entry",
                                     "indexed_after": 900})
        with mock.patch.object(service, "_cached_probe",
                               return_value={"available": True, "running": True, "status": {}}), \
             mock.patch.object(service, "_binary_version", return_value="0.23.12"), \
             mock.patch.object(service, "output_capabilities", return_value={}), \
             mock.patch.object(service, "_selected_alsa_output", return_value={}), \
             mock.patch.object(service, "idle_status", return_value={}):
            result = service.status(light=True)
        self.assertEqual(result["index_catchup"]["reason"], "missing-entry")
        self.assertEqual(result["index_catchup"]["indexed_after"], 900)


class MpdMissingEntryEscalationTests(unittest.TestCase):
    class EscalatingService:
        host = "127.0.0.1"
        port = 56660

        def __init__(self, accepted=True, running=False, raises=False):
            self.reasons = []
            self.accepted = accepted
            self.running = running
            self.raises = raises

        def request_index_catchup(self, reason="", path=""):
            self.reasons.append((reason, path))
            if self.raises:
                raise RuntimeError("worker cannot start")
            return {"accepted": self.accepted, "state": {"running": self.running}}

        def index_status(self):
            return {"running": self.running}

    def _message(self, service):
        output = MpdOutput(service)
        with mock.patch("playback.mpd_output.mpd_library_state",
                        return_value={"available": True, "indexed": MPD_INDEXED, "updating": False}):
            error = output._missing_entry_error(
                "未整理/春野/a b.flac",
                Exception(ACK_AT_0),
                {"ok": True, "updated": True, "scope": "未整理/春野"},
                Exception(ACK_AT_0),
            )
        return str(error)

    def test_a_refused_song_asks_mpd_for_the_whole_library_and_says_so(self):
        service = self.EscalatingService()
        message = self._message(service)
        self.assertEqual(service.reasons, [("missing-entry", "")])
        self.assertIn("MPD 索引落后于 fnAudio 曲库，当前已收录 23483 首", message)
        self.assertIn("已请求 MPD 收录整个曲库", message)
        self.assertIn("已请求 MPD 收录 未整理/春野 后重试仍失败", message)
        self.assertLess(message.index("MPD 索引落后"), message.index(ACK_AT_0))

    def test_an_already_running_catchup_is_reported_as_pending(self):
        service = self.EscalatingService(accepted=False, running=True)
        message = self._message(service)
        self.assertIn("MPD 索引落后于 fnAudio 曲库", message)

    def test_a_service_that_refuses_or_raises_keeps_the_old_diagnosis(self):
        refused = self._message(self.EscalatingService(accepted=False))
        self.assertIn("MPD 索引已完成，当前收录 23483 首，请确认文件仍存在", refused)
        broken = self._message(self.EscalatingService(raises=True))
        self.assertIn("MPD 索引已完成", broken)
        self.assertNotIn("worker cannot start", broken)


class MpdIndexWiringTests(unittest.TestCase):
    """The convergence must be attached to the lifecycle, not only to failures."""

    def _source(self):
        import io
        import os

        path = os.path.join(os.path.dirname(__file__), "..", "app", "server", "services", "mpd_service.py")
        with io.open(path, encoding="utf-8-sig") as handle:
            return handle.read()

    def test_mpd_start_and_restart_converge_the_index(self):
        source = self._source()
        self.assertEqual(source.count('self._maybe_converge_mpd_index("mpd-start")'), 1)
        self.assertEqual(source.count('self._maybe_converge_mpd_index("mpd-restart")'), 1)

    def test_stop_and_shutdown_cancel_the_index_worker(self):
        source = self._source()
        self.assertEqual(source.count("self._stop_index_catchup()"), 2)

    def test_the_configured_mpd_still_never_self_updates(self):
        """Convergence is fnAudio's job: ``auto_update`` stays off by design."""
        source = self._source()
        self.assertEqual(source.count('\'auto_update "no"\''), 1)


if __name__ == "__main__":
    unittest.main()

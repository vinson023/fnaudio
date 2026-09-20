import sys
import io
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

import server


class FakeMpdService:
    host = "127.0.0.1"
    port = 56660

    def __init__(self):
        self.calls = []

    def sync_playback_queue(self, tracks, current, **kwargs):
        self.calls.append((list(tracks), current, kwargs))
        return {"ok": True, "queue_count": len(tracks)}


class FailingMpdService(FakeMpdService):
    def sync_playback_queue(self, tracks, current, **kwargs):
        self.calls.append((list(tracks), current, kwargs))
        raise RuntimeError("MPD database is not ready")


class StoppedMpdService(FakeMpdService):
    def refresh_status(self):
        return {"status": {"transport": {"state": "STOPPED"}}}


class PlaybackRestoreTests(unittest.TestCase):
    def setUp(self):
        # Playback mutations cancel startup restore retries; reset that
        # process-global lifecycle flag between tests.
        server.enable_playback_restore_retry()

    def test_server_start_does_not_materialize_full_sqlite_library_for_thumbnail_warmup(self):
        with open("app/server/server.py", encoding="utf-8") as source_file:
            source = source_file.read()
        self.assertIn('startup_items[:STARTUP_THUMBNAIL_PREWARM_LIMIT]', source)
        self.assertIn('prewarm_library_thumbnails(startup_items[:STARTUP_THUMBNAIL_PREWARM_LIMIT], config, cached_cover_for_item)', source)
        self.assertNotIn('warm_items = MUSIC_CACHE["items"] or (load_items_from_sqlite(config) or {}).get("items", [])', source)

    def test_playback_control_rejects_non_text_action_without_mutating_restore(self):
        handler = mock.Mock()
        handler.server.config = {}
        fake_core = mock.Mock()
        fake_core.snapshot.return_value = {"target_id": "local", "transport": "STOPPED"}
        with mock.patch.object(server, "PLAYBACK_CORE", fake_core), \
             mock.patch.object(server, "cancel_playback_restore_retry") as cancel:
            response, status = server.playback_control(
                handler,
                {"target_id": "local", "action": ["play"]},
            )
        self.assertEqual(status, 400)
        self.assertEqual(response["message"], "action must be text")
        cancel.assert_not_called()
        fake_core.set_session_identity.assert_not_called()

    def test_cue_auto_advance_requires_explicit_success_from_output(self):
        with open("app/server/server.py", encoding="utf-8") as source_file:
            source = source_file.read()
        self.assertIn('if result.get("ok") is True and output_result.get("ok") is True:', source)

    def test_remote_output_string_false_is_not_reported_as_success(self):
        handler = mock.Mock()
        handler.server.config = {}
        item = {"id": "track-1", "path": "/music/one.flac"}
        fake_core = mock.Mock()
        fake_core.snapshot.return_value = {"target_id": "mpd:test", "transport": "STOPPED"}
        fake_core.dispatch.return_value = {
            "ok": True,
            "result": {"ok": "false", "message": "rejected"},
            "state": {"current": "track-1"},
        }
        with mock.patch.object(server, "PLAYBACK_CORE", fake_core), \
             mock.patch.object(server, "find_library_item", return_value=item), \
             mock.patch.object(server, "find_upnp_device", return_value=None), \
             mock.patch.object(server, "save_current_playback_session") as save:
            response, status = server.playback_control(
                handler,
                {"target_id": "mpd:test", "action": "play", "track_id": "track-1"},
            )
        self.assertEqual(status, 502)
        self.assertFalse(response["ok"])
        save.assert_called_once_with(handler.server.config)

    def test_outer_string_false_is_not_reported_as_success(self):
        handler = mock.Mock()
        handler.server.config = {}
        fake_core = mock.Mock()
        fake_core.snapshot.return_value = {"target_id": "local", "transport": "STOPPED"}
        fake_core.dispatch.return_value = {"ok": "false", "result": {}, "state": {}}
        with mock.patch.object(server, "PLAYBACK_CORE", fake_core), \
             mock.patch.object(server, "save_current_playback_session") as save:
            response, status = server.playback_control(
                handler,
                {"target_id": "local", "action": "stop"},
            )
        self.assertEqual(status, 502)
        self.assertFalse(response["ok"])
        save.assert_called_once_with(handler.server.config)

    def test_restore_promotes_current_track_metadata_before_transport_restore(self):
        with open("app/server/server.py", encoding="utf-8") as source_file:
            source = source_file.read()
        restore = source[source.index("def restore_playback_session"):source.index("def playback_queue", source.index("def restore_playback_session"))]
        self.assertIn("METADATA_SERVICE.prioritize_track(current)", restore)

    def test_playback_event_endpoint_writes_an_initial_sse_snapshot(self):
        class FakeCore:
            def snapshot_with_item(self):
                return self.snapshot(), getattr(self, "cue_item", {})

            def current_item(self):
                return getattr(self, "cue_item", {})

            def wait_for_version(self, version, timeout):
                return 7

            def snapshot(self):
                return {
                    "state_version": 7,
                    "target_id": "mpd:test-dac",
                    "target_kind": "mpd",
                    "transport": "PLAYING",
                    "position": 3.5,
                    "duration": 120.0,
                }

        class DisconnectingBuffer(io.BytesIO):
            def flush(self):
                raise BrokenPipeError()

        handler = object.__new__(server.Handler)
        handler.send_response = lambda status: None
        handler.send_header = lambda name, value: None
        handler.end_headers = lambda: None
        handler.wfile = DisconnectingBuffer()
        with mock.patch.object(server, "PLAYBACK_CORE", FakeCore()):
            handler.stream_playback_events({"target_id": ["mpd:test-dac"]})

        frame = handler.wfile.getvalue().decode("utf-8")
        self.assertIn("id: 7", frame)
        self.assertIn("event: playback", frame)
        self.assertIn('"target_id":"mpd:test-dac"', frame)

    def test_playback_event_endpoint_treats_closed_writer_value_error_as_disconnect(self):
        class FakeCore:
            def snapshot_with_item(self):
                return self.snapshot(), getattr(self, "cue_item", {})

            def current_item(self):
                return getattr(self, "cue_item", {})

            def wait_for_version(self, version, timeout):
                return 7

            def snapshot(self):
                return {"state_version": 7, "target_id": "local", "target_kind": "browser", "transport": "PLAYING"}

        class ClosedWriter(io.BytesIO):
            def flush(self):
                raise ValueError("I/O operation on closed file")

        handler = object.__new__(server.Handler)
        handler.send_response = lambda status: None
        handler.send_header = lambda name, value: None
        handler.end_headers = lambda: None
        handler.wfile = ClosedWriter()
        with mock.patch.object(server, "PLAYBACK_CORE", FakeCore()):
            handler.stream_playback_events({})

        self.assertIn(b"event: playback", handler.wfile.getvalue())

    def test_playback_event_endpoint_uses_bounded_target_policy(self):
        class FakeCore:
            def snapshot_with_item(self):
                return self.snapshot(), getattr(self, "cue_item", {})

            def current_item(self):
                return getattr(self, "cue_item", {})

            def wait_for_version(self, version, timeout):
                raise BrokenPipeError()

            def snapshot(self):
                return {"state_version": 1, "target_id": "local", "target_kind": "browser", "transport": "STOPPED", "position": 0, "duration": 0}

        handler = object.__new__(server.Handler)
        handler.send_response = lambda status: None
        handler.send_header = lambda name, value: None
        handler.end_headers = lambda: None
        handler.wfile = io.BytesIO()
        with mock.patch.object(server, "PLAYBACK_CORE", FakeCore()):
            handler.stream_playback_events({"target_id": ["x" * 1000]})
        self.assertNotIn(b"x" * 129, handler.wfile.getvalue())

    def test_playback_event_endpoint_rejects_when_event_stream_share_is_full(self):
        class FakeGate:
            def __init__(self):
                self.released = False

            def try_acquire(self, limit):
                return False

            def release(self):
                self.released = True

        handler = object.__new__(server.Handler)
        handler.server = type("Server", (), {"event_stream_gate": FakeGate(), "event_stream_limit": 1})()
        handler.send_json = mock.Mock()
        handler.stream_playback_events({})
        handler.send_json.assert_called_once_with(
            {"ok": False, "error": "playback event stream busy"}, 503, {"Retry-After": "1"}
        )

    def test_playback_event_endpoint_releases_event_share_when_headers_disconnect(self):
        class FakeGate:
            def __init__(self):
                self.released = False

            def try_acquire(self, limit):
                return True

            def release(self):
                self.released = True

        gate = FakeGate()
        handler = object.__new__(server.Handler)
        handler.server = type("Server", (), {"event_stream_gate": gate, "event_stream_limit": 1})()
        handler.send_response = mock.Mock(side_effect=BrokenPipeError())
        handler.stream_playback_events({})
        self.assertTrue(gate.released)

    def test_playback_event_payload_uses_core_as_the_authoritative_snapshot(self):
        core = {
            "target_id": "mpd:usb-dac",
            "target_kind": "mpd",
            "transport": "PLAYING",
            "position": 12.25,
            "duration": 245.5,
            "state_version": 42,
        }

        payload = server.playback_event_payload(core, "mpd:usb-dac")

        self.assertEqual(payload["state_version"], 42)
        self.assertEqual(payload["target_id"], "mpd:usb-dac")
        self.assertEqual(payload["transport"]["state"], "PLAYING")
        self.assertEqual(payload["position"], {"rel_seconds": 12.25, "duration_seconds": 245.5})
        self.assertIs(payload["core"], core)

    def test_playback_control_command_id_is_idempotent_for_retry_safe_transport(self):
        handler = mock.Mock()
        handler.server.config = {}
        handler.server.config_path = "fnaudio.json"
        response = {"ok": True, "core": {"state_version": 9, "transport": "PLAYING"}}
        server.PLAYBACK_COMMAND_RESULTS.clear()
        with mock.patch.object(server, "playback_control", return_value=(response, 200)) as control:
            first, first_status = server.playback_control_idempotent(handler, {"command_id": "same-gesture", "action": "next"})
            second, second_status = server.playback_control_idempotent(handler, {"command_id": "same-gesture", "action": "next"})

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertEqual(first["command_id"], "same-gesture")
        self.assertEqual(second["state_version"], 9)
        control.assert_called_once()

    def test_same_command_id_concurrent_retries_share_one_control_execution(self):
        handler = mock.Mock()
        handler.server.config = {}
        entered = threading.Event()
        release = threading.Event()
        results = []
        errors = []

        def control(_handler, _payload):
            entered.set()
            self.assertTrue(release.wait(2.0))
            return {"ok": True, "core": {"state_version": 10}}, 200

        def invoke():
            try:
                results.append(server.playback_control_idempotent(handler, {"command_id": "one", "action": "next"}))
            except Exception as error:
                errors.append(error)

        server.PLAYBACK_COMMAND_RESULTS.clear()
        server.PLAYBACK_COMMAND_INFLIGHT.clear()
        try:
            with mock.patch.object(server, "playback_control", side_effect=control) as mocked_control:
                first = threading.Thread(target=invoke)
                second = threading.Thread(target=invoke)
                first.start()
                self.assertTrue(entered.wait(1.0))
                second.start()
                release.set()
                first.join(2.0)
                second.join(2.0)
                self.assertFalse(first.is_alive())
                self.assertFalse(second.is_alive())
                mocked_control.assert_called_once()
        finally:
            release.set()
            server.PLAYBACK_COMMAND_RESULTS.clear()
            server.PLAYBACK_COMMAND_INFLIGHT.clear()

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0][1], 200)
        self.assertEqual(results[1][1], 200)
        self.assertEqual(results[0][0]["command_id"], "one")
        self.assertEqual(results[1][0]["command_id"], "one")

    def test_different_command_ids_do_not_wait_for_an_unrelated_slow_command(self):
        handler = mock.Mock()
        handler.server.config = {}
        entered = threading.Event()
        release = threading.Event()
        slow_result = []
        fast_result = []

        def control(_handler, payload):
            if payload["command_id"] == "slow":
                entered.set()
                self.assertTrue(release.wait(2.0))
            return {"ok": True, "core": {"state_version": 11}}, 200

        server.PLAYBACK_COMMAND_RESULTS.clear()
        server.PLAYBACK_COMMAND_INFLIGHT.clear()
        try:
            with mock.patch.object(server, "playback_control", side_effect=control):
                slow = threading.Thread(target=lambda: slow_result.append(server.playback_control_idempotent(handler, {"command_id": "slow", "action": "next"})))
                slow.start()
                self.assertTrue(entered.wait(1.0))
                fast = threading.Thread(target=lambda: fast_result.append(server.playback_control_idempotent(handler, {"command_id": "fast", "action": "pause"})))
                fast.start()
                fast.join(1.0)
                self.assertFalse(fast.is_alive())
                release.set()
                slow.join(2.0)
                self.assertFalse(slow.is_alive())
        finally:
            release.set()
            server.PLAYBACK_COMMAND_RESULTS.clear()
            server.PLAYBACK_COMMAND_INFLIGHT.clear()

        self.assertEqual(fast_result[0][1], 200)
        self.assertEqual(slow_result[0][1], 200)

    def test_failed_leader_releases_command_ticket_for_a_later_retry(self):
        handler = mock.Mock()
        handler.server.config = {}
        server.PLAYBACK_COMMAND_RESULTS.clear()
        server.PLAYBACK_COMMAND_INFLIGHT.clear()
        try:
            with mock.patch.object(server, "playback_control", side_effect=[RuntimeError("offline"), ({"ok": True, "core": {"state_version": 12}}, 200)]) as control:
                with self.assertRaisesRegex(RuntimeError, "offline"):
                    server.playback_control_idempotent(handler, {"command_id": "recover", "action": "play"})
                response, status = server.playback_control_idempotent(handler, {"command_id": "recover", "action": "play"})
                self.assertEqual(status, 200)
                self.assertEqual(response["command_id"], "recover")
                self.assertEqual(control.call_count, 2)
        finally:
            server.PLAYBACK_COMMAND_RESULTS.clear()
            server.PLAYBACK_COMMAND_INFLIGHT.clear()

    def test_waiting_retry_returns_pending_without_releasing_the_leader_ticket(self):
        handler = mock.Mock()
        handler.server.config = {}
        original_wait = server.PLAYBACK_COMMAND_WAIT_SECONDS

        server.PLAYBACK_COMMAND_RESULTS.clear()
        server.PLAYBACK_COMMAND_INFLIGHT.clear()
        server.PLAYBACK_COMMAND_WAIT_SECONDS = 0.01
        try:
            leader_ticket = threading.Event()
            server.PLAYBACK_COMMAND_INFLIGHT["pending"] = leader_ticket
            response, status = server.playback_control_idempotent(handler, {"command_id": "pending", "action": "play"})
            self.assertEqual(status, 202)
            self.assertTrue(response["pending"])
            self.assertIs(server.PLAYBACK_COMMAND_INFLIGHT["pending"], leader_ticket)
        finally:
            server.PLAYBACK_COMMAND_WAIT_SECONDS = original_wait
            server.PLAYBACK_COMMAND_RESULTS.clear()
            server.PLAYBACK_COMMAND_INFLIGHT.clear()

    def test_playback_command_id_cache_is_bounded(self):
        server.PLAYBACK_COMMAND_RESULTS.clear()
        original_limit = server.PLAYBACK_COMMAND_RESULT_LIMIT
        try:
            server.PLAYBACK_COMMAND_RESULT_LIMIT = 2
            handler = mock.Mock()
            handler.server.config = {}
            with mock.patch.object(server, "playback_control", return_value=({"ok": True, "core": {"state_version": 1}}, 200)):
                for index in range(3):
                    server.playback_control_idempotent(handler, {"command_id": "id-%d" % index, "action": "pause"})
            self.assertEqual(len(server.PLAYBACK_COMMAND_RESULTS), 2)
            self.assertNotIn("id-0", server.PLAYBACK_COMMAND_RESULTS)
        finally:
            server.PLAYBACK_COMMAND_RESULT_LIMIT = original_limit
            server.PLAYBACK_COMMAND_RESULTS.clear()

    def test_playback_command_diagnostics_include_bounded_inflight_pressure(self):
        server.PLAYBACK_COMMAND_RESULTS.clear()
        server.PLAYBACK_COMMAND_INFLIGHT.clear()
        original_limit = server.PLAYBACK_COMMAND_RESULT_LIMIT
        try:
            server.PLAYBACK_COMMAND_RESULT_LIMIT = 2
            server.PLAYBACK_COMMAND_INFLIGHT.update({
                "one": threading.Event(),
                "two": threading.Event(),
                "unexpected": threading.Event(),
            })
            self.assertEqual(server.playback_command_cache_status(), {
                "entries": 0,
                "limit": 2,
                "saturated": False,
                "inflight": 2,
                "inflight_limit": 2,
            })
        finally:
            server.PLAYBACK_COMMAND_RESULT_LIMIT = original_limit
            server.PLAYBACK_COMMAND_RESULTS.clear()
            server.PLAYBACK_COMMAND_INFLIGHT.clear()

    def test_targets_marks_stale_renderer_as_unavailable_without_losing_local_target(self):
        fake_core = mock.Mock()
        fake_core.snapshot.return_value = {"target_id": "stale-renderer"}
        fake_plugin = mock.Mock()
        fake_plugin.capabilities.return_value = {}
        fake_core.registry.get.return_value = fake_plugin
        fake_core.registry.describe.return_value = []
        with mock.patch.object(server, "PLAYBACK_CORE", fake_core), mock.patch.object(
            server.MPD_OUTPUT, "status", return_value={"available": False, "output_capabilities": {"devices": []}}
        ), mock.patch.object(server, "cached_upnp_devices", return_value=[]), mock.patch.object(
            server, "upnp_cache_needs_refresh", return_value=False
        ), mock.patch.object(
            server, "upmpdcli_probe", return_value={}
        ), mock.patch.object(server, "airplay_probe", return_value={}):
            payload = server.playback_targets_payload()

        self.assertEqual(payload["current_target"], "stale-renderer")
        self.assertFalse(payload["current_target_available"])
        self.assertEqual(payload["targets"][0]["id"], "local")

    def test_forced_target_refresh_rebuilds_mpd_output_capabilities(self):
        class CapabilityService:
            def __init__(self):
                self.calls = []

            def output_capabilities(self, force=False):
                self.calls.append(force)
                return {"devices": []}

        service = CapabilityService()
        output = mock.Mock()
        output.service = service
        output.status.return_value = {"available": False, "output_capabilities": {"devices": []}}
        fake_core = mock.Mock()
        fake_core.snapshot.return_value = {"target_id": "local"}
        fake_plugin = mock.Mock()
        fake_plugin.capabilities.return_value = {}
        fake_core.registry.get.return_value = fake_plugin
        fake_core.registry.describe.return_value = []
        with mock.patch.object(server, "PLAYBACK_CORE", fake_core), mock.patch.object(
            server, "MPD_OUTPUT", output
        ), mock.patch.object(server, "cached_upnp_devices", return_value=[]), mock.patch.object(
            server, "refresh_upnp_cache_background", return_value=False
        ), mock.patch.object(
            server, "upmpdcli_probe", return_value={}
        ), mock.patch.object(server, "airplay_probe", return_value={}):
            server.playback_targets_payload(force_refresh=True)

        self.assertEqual(service.calls, [True])

    def test_playback_control_persists_stop_state_for_restart(self):
        handler = mock.Mock()
        handler.server.config = {}
        handler.server.config_path = "fnaudio.json"
        fake_core = mock.Mock()
        fake_core.snapshot.return_value = {"playing": False, "transport": "STOPPED"}
        fake_core.dispatch.return_value = {"result": {}, "state": {}}
        with mock.patch.object(server, "PLAYBACK_CORE", fake_core), mock.patch.object(
            server, "playback_target_kind", return_value="browser"
        ), mock.patch.object(server, "save_current_playback_session", return_value=27) as save_session:
            response, status = server.playback_control(handler, {"target_id": "local", "action": "stop"})
        self.assertEqual(status, 200)
        self.assertEqual(response["revision"], 27)
        save_session.assert_called_once_with(handler.server.config)

    def test_playback_control_reports_persistence_failure_instead_of_success(self):
        handler = mock.Mock()
        handler.server.config = {}
        handler.server.config_path = "fnaudio.json"
        fake_core = mock.Mock()
        fake_core.snapshot.return_value = {"playing": False, "transport": "STOPPED"}
        fake_core.dispatch.return_value = {"result": {}, "state": {}}
        with mock.patch.object(server, "PLAYBACK_CORE", fake_core), mock.patch.object(
            server, "playback_target_kind", return_value="browser"
        ), mock.patch.object(server, "save_current_playback_session", return_value=None):
            response, status = server.playback_control(handler, {"target_id": "local", "action": "stop"})
        self.assertEqual(status, 503)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"], "playback_state_persistence_failed")


    def test_playback_queue_reports_persistence_failure_instead_of_success(self):
        config = {}
        fake_state = mock.Mock()
        fake_state.to_dict.return_value = {"queue": [{"id": "track-1"}]}
        fake_state.current_track_id = "track-1"
        fake_state.playing = False
        fake_state.repeat = "off"
        fake_state.shuffle = False
        fake_core = mock.Mock()
        fake_core.set_queue.return_value = fake_state
        fake_core.state.target_id = "local"
        with mock.patch.object(server, "PLAYBACK_CORE", fake_core), mock.patch.object(
            server, "save_current_playback_session", return_value=None
        ), mock.patch.object(server, "cancel_playback_restore_retry"):
            response, status = server.playback_queue(
                config,
                {"queue": [{"id": "track-1"}], "current_id": "track-1"},
            )

        self.assertEqual(status, 503)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"], "playback_state_persistence_failed")

    def test_accepted_playback_command_cancels_pending_restore_retry(self):
        handler = mock.Mock()
        handler.server.config = {}
        handler.server.config_path = "fnaudio.json"
        fake_core = mock.Mock()
        fake_core.snapshot.return_value = {"generation": 0, "engine_epoch": 0, "transport": "STOPPED"}
        fake_core.dispatch.return_value = {"result": {}, "state": {}}
        with mock.patch.object(server, "PLAYBACK_CORE", fake_core), mock.patch.object(
            server, "save_current_playback_session", return_value=1
        ), mock.patch.object(server, "cancel_playback_restore_retry") as cancel:
            response, status = server.playback_control(handler, {"target_id": "local", "action": "stop"})

        self.assertEqual(status, 200)
        self.assertTrue(response["ok"])
        cancel.assert_called_once_with()

    def test_playback_control_load_resolves_the_requested_track_for_any_output(self):
        handler = mock.Mock()
        handler.server.config = {}
        item = {"id": "track-2", "path": "/music/two.flac"}
        with mock.patch.object(server, "find_library_item", return_value=item), mock.patch.object(
            server, "find_upnp_device", return_value={"id": "renderer-1"}
        ), mock.patch.object(server, "playback_load_selected", return_value=({"ok": True}, 200)) as load_selected:
            response, status = server.playback_control(
                handler,
                {"target_id": "renderer-1", "action": "load", "track_id": "track-2", "position": 12.5},
            )

        self.assertEqual((response, status), ({"ok": True}, 200))
        load_selected.assert_called_once_with(handler, "renderer-1", item, 12.5)

    def test_legacy_playback_load_uses_the_idempotent_control_contract(self):
        handler = mock.Mock()
        payload = {"target_id": "renderer-1", "track_id": "track-2", "command_id": "load-1"}
        with mock.patch.object(server, "playback_control_idempotent", return_value=({"ok": True}, 200)) as control:
            response, status = server.playback_load(handler, payload)

        self.assertEqual((response, status), ({"ok": True}, 200))
        forwarded = control.call_args.args[1]
        self.assertEqual(forwarded["action"], "load")
        self.assertEqual(forwarded["track_id"], "track-2")
        self.assertEqual(forwarded["command_id"], "load-1")

    def test_invalid_playback_action_does_not_switch_or_close_the_active_target(self):
        handler = mock.Mock()
        handler.server.config = {}
        fake_core = mock.Mock()
        fake_core.snapshot.return_value = {"target_id": "mpd:active", "transport": "PLAYING"}
        with mock.patch.object(server, "PLAYBACK_CORE", fake_core):
            response, status = server.playback_control(
                handler,
                {"target_id": "local", "action": ""},
            )

        self.assertEqual(status, 400)
        self.assertFalse(response["ok"])
        fake_core.set_target.assert_not_called()
        fake_core.dispatch.assert_not_called()

    def test_invalid_explicit_repeat_or_shuffle_does_not_toggle_state(self):
        handler = mock.Mock()
        handler.server.config = {}
        fake_core = mock.Mock()
        fake_core.snapshot.return_value = {"target_id": "local", "repeat": "off", "shuffle": False}
        with mock.patch.object(server, "PLAYBACK_CORE", fake_core):
            repeat_response, repeat_status = server.playback_control(
                handler, {"target_id": "local", "action": "repeat", "repeat": "invalid"}
            )
            shuffle_response, shuffle_status = server.playback_control(
                handler, {"target_id": "local", "action": "shuffle", "shuffle": "false"}
            )

        self.assertEqual(repeat_status, 400)
        self.assertEqual(shuffle_status, 400)
        self.assertFalse(repeat_response["ok"])
        self.assertFalse(shuffle_response["ok"])
        fake_core.set_target.assert_not_called()
        fake_core.dispatch.assert_not_called()

    def test_rejected_future_session_commands_do_not_replace_active_identity(self):
        handler = mock.Mock()
        handler.server.config = {}
        fake_core = mock.Mock()
        fake_core.snapshot.return_value = {
            "generation": 5,
            "engine_epoch": 2,
            "target_id": "mpd:active",
        }
        with mock.patch.object(server, "PLAYBACK_CORE", fake_core), mock.patch.object(
            server, "find_library_item", return_value=None
        ):
            unsupported, unsupported_status = server.playback_control(
                handler,
                {"target_id": "local", "action": "invalid", "generation": 6, "engine_epoch": 1},
            )
            missing, missing_status = server.playback_control(
                handler,
                {"target_id": "local", "action": "load", "track_id": "gone", "generation": 6, "engine_epoch": 1},
            )

        self.assertEqual(unsupported_status, 400)
        self.assertFalse(unsupported["ok"])
        self.assertEqual(missing_status, 404)
        self.assertFalse(missing["ok"])
        fake_core.set_session_identity.assert_not_called()

    def test_stale_session_is_rejected_without_mutating_core(self):
        handler = mock.Mock()
        handler.server.config = {}
        handler.server.config_path = "fnaudio.json"
        fake_core = mock.Mock()
        fake_core.snapshot.return_value = {
            "generation": 9,
            "engine_epoch": 3,
            "target_id": "mpd:active",
            "transport": "PLAYING",
        }
        with mock.patch.object(server, "PLAYBACK_CORE", fake_core), mock.patch.object(
            server.OBSERVABILITY, "write"
        ) as write_log:
            response, status = server.playback_control(
                handler,
                {"target_id": "local", "action": "pause", "generation": 8, "engine_epoch": 3},
            )
        self.assertEqual(status, 409)
        self.assertEqual(response["error"], "stale_session")
        fake_core.set_target.assert_not_called()
        fake_core.dispatch.assert_not_called()
        self.assertEqual(write_log.call_args.args[1], "playback_stale_session")

    def test_stale_session_logging_failure_does_not_change_rejection(self):
        handler = mock.Mock()
        handler.server.config = {}
        handler.server.config_path = "fnaudio.json"
        fake_core = mock.Mock()
        fake_core.snapshot.return_value = {"generation": 4, "engine_epoch": 2}
        with mock.patch.object(server, "PLAYBACK_CORE", fake_core), mock.patch.object(
            server.OBSERVABILITY, "write", side_effect=RuntimeError("log unavailable")
        ):
            response, status = server.playback_control(
                handler,
                {"target_id": "local", "action": "play", "generation": 3, "engine_epoch": 2},
            )
        self.assertEqual(status, 409)
        self.assertEqual(response["error"], "stale_session")
        fake_core.dispatch.assert_not_called()

    def test_missing_dlna_target_does_not_replace_the_active_target(self):
        handler = mock.Mock()
        handler.server.config = {}
        fake_core = mock.Mock()
        fake_core.snapshot.return_value = {"target_id": "mpd:active", "transport": "PLAYING"}
        with mock.patch.object(server, "PLAYBACK_CORE", fake_core), mock.patch.object(
            server, "find_upnp_device", return_value=None
        ):
            response, status = server.playback_control(
                handler,
                {"target_id": "uuid:offline-renderer", "action": "play"},
            )

        self.assertEqual(status, 404)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"], "playback_target_not_found")
        fake_core.set_target.assert_not_called()

    def test_missing_dlna_target_rejects_direct_load_before_core_mutation(self):
        handler = mock.Mock()
        handler.server.config = {}
        fake_core = mock.Mock()
        fake_core.snapshot.return_value = {"target_id": "mpd:active", "transport": "PLAYING"}
        with mock.patch.object(server, "PLAYBACK_CORE", fake_core), mock.patch.object(
            server, "find_upnp_device", return_value=None
        ), mock.patch.object(server, "playback_load_selected") as load_selected:
            response, status = server.playback_control(
                handler,
                {"target_id": "uuid:offline-renderer", "action": "load", "track_id": "track-1"},
            )

        self.assertEqual(status, 404)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"], "playback_target_not_found")
        fake_core.set_target.assert_not_called()
        load_selected.assert_not_called()

    def test_failed_config_write_leaves_the_runtime_config_unchanged(self):
        runtime_config = {"metadata_enabled": True, "nested": {"value": 1}}
        owner = mock.Mock(config=runtime_config, config_path="config.json")
        with mock.patch.object(server, "save_config", return_value=False):
            committed = server.commit_config_update(
                owner,
                lambda candidate: candidate.update({"metadata_enabled": False}),
            )

        self.assertFalse(committed)
        self.assertIs(owner.config, runtime_config)
        self.assertEqual(owner.config, {"metadata_enabled": True, "nested": {"value": 1}})

    def test_successful_config_write_commits_in_place(self):
        runtime_config = {"metadata_enabled": True}
        owner = mock.Mock(config=runtime_config, config_path="config.json")
        with mock.patch.object(server, "save_config", return_value=True) as save:
            committed = server.commit_config_update(
                owner,
                lambda candidate: candidate.update({"metadata_enabled": False}),
            )

        self.assertTrue(committed)
        self.assertIs(owner.config, runtime_config)
        self.assertFalse(owner.config["metadata_enabled"])
        self.assertIsNot(save.call_args.args[1], runtime_config)

    def test_restore_mirrors_saved_mpd_queue_and_position(self):
        with tempfile.TemporaryDirectory() as root:
            fake = FakeMpdService()
            saved = {
                "playback": {
                    "queue": ["a", "b"],
                    "current_id": "b",
                    "position": 17.5,
                    "playing": True,
                    "repeat": "all",
                    "shuffle": False,
                    "target_id": "mpd:usb:dac",
                }
            }
            items = [
                {"id": "a", "path": "/music/a.flac", "duration": 30},
                {"id": "b", "path": "/music/b.flac", "duration": 40},
            ]
            old_service = server.MPD_SERVICE
            try:
                server.MPD_SERVICE = fake
                with mock.patch.object(server, "load_user_state", return_value=saved), mock.patch.object(
                    server, "query_library_items_by_ids", return_value=items
                ), mock.patch.object(server, "mpd_control") as control:
                    server.restore_playback_session({"cache_dir": root})
                self.assertGreaterEqual(len(fake.calls), 1)
                tracks, current, options = fake.calls[-1]
                self.assertEqual([track.track_id for track in tracks], ["a", "b"])
                self.assertEqual(current, "b")
                self.assertEqual(options["start"], 17.5)
                self.assertEqual(options["repeat"], "all")
                control.assert_called_once_with("stop", host=fake.host, port=fake.port)
                self.assertEqual(server.PLAYBACK_CORE.state.current_track_id, "b")
                self.assertEqual(server.PLAYBACK_CORE.state.position, 17.5)
                self.assertFalse(server.PLAYBACK_CORE.state.playing)
                self.assertFalse(options["play"])
            finally:
                server.MPD_SERVICE = old_service

    def test_restore_mirrors_stopped_session_then_stops_mpd(self):
        with tempfile.TemporaryDirectory() as root:
            fake = FakeMpdService()
            saved = {
                "playback": {
                    "queue": ["a"],
                    "current_id": "a",
                    "position": 3,
                    "playing": False,
                    "target_id": "mpd:usb:dac",
                }
            }
            old_service = server.MPD_SERVICE
            try:
                server.MPD_SERVICE = fake
                with mock.patch.object(server, "load_user_state", return_value=saved), mock.patch.object(
                    server, "query_library_items_by_ids", return_value=[{"id": "a", "path": "/music/a.flac"}]
                ), mock.patch.object(server, "mpd_control") as control:
                    server.restore_playback_session({"cache_dir": root})
                control.assert_called_once_with("stop", host=fake.host, port=fake.port)
                self.assertFalse(server.PLAYBACK_CORE.state.playing)
                self.assertEqual(server.PLAYBACK_CORE.state.transport, "STOPPED")
            finally:
                server.MPD_SERVICE = old_service

    def test_restore_retries_after_transient_mpd_startup_failure(self):
        with tempfile.TemporaryDirectory() as root:
            fake = FailingMpdService()
            saved = {
                "playback": {
                    "queue": ["a"],
                    "current_id": "a",
                    "target_id": "mpd:usb:dac",
                }
            }
            old_service = server.MPD_SERVICE
            try:
                server.MPD_SERVICE = fake
                server.enable_playback_restore_retry()
                timer = mock.Mock()
                with mock.patch.object(server, "load_user_state", return_value=saved), mock.patch.object(
                    server, "query_library_items_by_ids", return_value=[{"id": "a", "path": "/music/a.flac"}]
                ), mock.patch.object(server.threading, "Timer") as timer_factory:
                    timer_factory.return_value = timer
                    server.restore_playback_session({"cache_dir": root})
                timer_factory.assert_called_once_with(
                    2.0,
                    server.restore_playback_session,
                    args=({"cache_dir": root}, 1, server.PLAYBACK_RESTORE_RETRY_GENERATION),
                )
                timer.start.assert_called_once_with()
                self.assertEqual(len(fake.calls), 1)
            finally:
                server.cancel_playback_restore_retry()
                server.MPD_SERVICE = old_service

    def test_restore_does_not_schedule_retry_after_runtime_shutdown(self):
        with tempfile.TemporaryDirectory() as root:
            fake = FailingMpdService()
            old_service = server.MPD_SERVICE
            try:
                server.MPD_SERVICE = fake
                server.cancel_playback_restore_retry()
                with mock.patch.object(server, "load_user_state", return_value={"playback": {"queue": ["a"], "current_id": "a", "target_id": "mpd:usb:dac"}}), \
                     mock.patch.object(server, "query_library_items_by_ids", return_value=[{"id": "a", "path": "/music/a.flac"}]), \
                     mock.patch.object(server.threading, "Timer") as timer_factory:
                    server.restore_playback_session({"cache_dir": root})
                timer_factory.assert_not_called()
            finally:
                server.enable_playback_restore_retry()
                server.MPD_SERVICE = old_service

    def test_stale_restore_retry_cannot_mutate_a_new_runtime_generation(self):
        with tempfile.TemporaryDirectory() as root:
            old_generation = server.enable_playback_restore_retry()
            new_generation = server.enable_playback_restore_retry()
            self.assertNotEqual(old_generation, new_generation)
            fake_core = mock.Mock()
            with mock.patch.object(server, "PLAYBACK_CORE", fake_core), \
                 mock.patch.object(server, "load_user_state") as load_state:
                server.restore_playback_session({"cache_dir": root}, 1, old_generation)
            load_state.assert_not_called()
            fake_core.set_queue.assert_not_called()
            fake_core.set_target.assert_not_called()

    def test_restore_does_not_publish_playing_when_mpd_stops_on_open(self):
        with tempfile.TemporaryDirectory() as root:
            fake = StoppedMpdService()
            saved = {
                "playback": {
                    "queue": ["a"],
                    "current_id": "a",
                    "playing": True,
                    "target_id": "mpd:usb:dac",
                }
            }
            old_service = server.MPD_SERVICE
            try:
                server.MPD_SERVICE = fake
                with mock.patch.object(server, "load_user_state", return_value=saved), mock.patch.object(
                    server, "query_library_items_by_ids", return_value=[{"id": "a", "path": "/music/a.flac"}]
                ), mock.patch.object(server, "mpd_control"), mock.patch.object(server, "save_current_playback_session") as save_session:
                    server.restore_playback_session({"cache_dir": root})
                self.assertFalse(server.PLAYBACK_CORE.state.playing)
                self.assertEqual(server.PLAYBACK_CORE.state.transport, "STOPPED")
                save_session.assert_called_once()
            finally:
                server.MPD_SERVICE = old_service

    def _restore_mpd_cue_session(self, item_path):
        """Restore an MPD session whose current track is a CUE segment.

        The saved position is in client units (seconds inside the segment) while
        MPD's native queue mirror is driven in source-file seconds, so for a
        native segment the two numbers must differ by the segment offset.
        """
        with tempfile.TemporaryDirectory() as root:
            fake = FakeMpdService()
            saved = {
                "playback": {
                    "queue": ["a", "cue"],
                    "current_id": "cue",
                    "position": 17.5,
                    "playing": True,
                    "repeat": "off",
                    "shuffle": False,
                    "target_id": "mpd:usb:dac",
                }
            }
            items = [
                {"id": "a", "path": "/music/a.flac", "duration": 30},
                {
                    "id": "cue",
                    "path": item_path,
                    "cue_track": True,
                    "cue_start": 100.0,
                    "cue_end": 130.0,
                    "duration": 30.0,
                },
            ]
            old_service = server.MPD_SERVICE
            try:
                server.MPD_SERVICE = fake
                with mock.patch.object(server, "load_user_state", return_value=saved), mock.patch.object(
                    server, "query_library_items_by_ids", return_value=items
                ), mock.patch.object(server, "mpd_control") as control:
                    server.restore_playback_session({"cache_dir": root})
                self.assertGreaterEqual(len(fake.calls), 1)
                tracks, current, options = fake.calls[-1]
                self.assertEqual([track.track_id for track in tracks], ["a", "cue"])
                self.assertEqual(current, "cue")
                self.assertIs(options["current_item"], items[1])
                control.assert_called_once_with("stop", host=fake.host, port=fake.port)
                return options, server.PLAYBACK_CORE.state.position
            finally:
                server.MPD_SERVICE = old_service

    def test_restore_drives_mpd_in_source_seconds_for_a_native_cue_segment(self):
        options, core_position = self._restore_mpd_cue_session("/music/disc.flac")
        self.assertEqual(options["start"], 117.5)
        # The authoritative state keeps the client unit, otherwise the progress
        # bar jumps by the offset the moment the session is restored.
        self.assertEqual(core_position, 17.5)

    def test_restore_leaves_a_transcoded_segment_in_its_own_seconds(self):
        options, core_position = self._restore_mpd_cue_session("/music/disc.ape")
        self.assertEqual(options["start"], 17.5)
        self.assertEqual(core_position, 17.5)

    def test_the_mpd_listener_folds_the_seconds_before_publishing_them(self):
        """Wiring pin for the one transport writer that runs without any client request.

        ``on_mpd_transport`` lives inside the bootstrap function, so no unit test
        can call it: every other test reaches the fold through
        :func:`project_mpd_transport_position` directly and cannot see the fold
        disappear at its only call site.  Were it to drop back to forwarding raw
        numbers, the authoritative state, the persisted session and the polling
        route would publish three different units, so the shape is pinned here and
        labelled a wiring guard rather than behaviour coverage.
        """
        with open("app/server/server.py", encoding="utf-8") as source_file:
            source = source_file.read()
        start = source.index("def on_mpd_transport(")
        end = source.index("MPD_SERVICE.set_status_listener(on_mpd_transport)", start)
        listener = source[start:end]
        self.assertEqual(listener.count("project_mpd_transport_position("), 1, listener)
        self.assertIn("PLAYBACK_CORE.current_item()", listener)
        self.assertEqual(
            listener.count("transport_rel,\n                transport_duration,"),
            2,
            listener,
        )
        self.assertNotIn('safe_float(position.get("rel_seconds"))', listener)
        self.assertNotIn('safe_float(position.get("duration_seconds"))', listener)

    def test_transport_projection_folds_mpd_seconds_once(self):
        flac = {
            "cue_track": True,
            "path": "/music/disc.flac",
            "cue_start": 100.0,
            "cue_end": 130.0,
            "duration": 30.0,
        }
        self.assertEqual(
            server.project_mpd_transport_position({"rel_seconds": 112.5, "duration_seconds": 210.0}, flac),
            {"rel_seconds": 12.5, "duration_seconds": 30.0},
        )
        ape = dict(flac, path="/music/disc.ape")
        self.assertEqual(
            server.project_mpd_transport_position({"rel_seconds": 12.5, "duration_seconds": 210.0}, ape),
            {"rel_seconds": 12.5, "duration_seconds": 30.0},
        )
        self.assertEqual(
            server.project_mpd_transport_position({"rel_seconds": 12.5, "duration_seconds": 210.0}, None),
            {"rel_seconds": 12.5, "duration_seconds": 210.0},
        )
        # A payload that is not a mapping still yields exactly the two client keys.
        self.assertEqual(
            server.project_mpd_transport_position("not-a-status", {}),
            {"rel_seconds": 0.0, "duration_seconds": 0.0},
        )
        self.assertEqual(
            server.project_mpd_transport_position(None, flac),
            {"rel_seconds": 0.0, "duration_seconds": 30.0},
        )



if __name__ == "__main__":
    unittest.main()

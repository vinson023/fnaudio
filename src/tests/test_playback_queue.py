import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

import server
from state_store import load_user_state


class PlaybackQueueTests(unittest.TestCase):
    def test_compact_track_ids_are_accepted_and_persisted(self):
        with tempfile.TemporaryDirectory() as root:
            response, status = server.playback_queue(
                {"cache_dir": root},
                {
                    "queue": ["track-1", "", "track-2"],
                    "current_id": "track-2",
                    "repeat": "all",
                    "shuffle": True,
                },
            )

            self.assertEqual(status, 200)
            self.assertTrue(response["ok"])
            self.assertEqual(response["core"]["queue"], ["track-1", "track-2"])
            self.assertEqual(response["core"]["current"], "track-2")
            playback = load_user_state({"cache_dir": root})["playback"]
            self.assertEqual(playback["queue"], ["track-1", "track-2"])
            self.assertEqual(playback["current_id"], "track-2")

    def test_legacy_track_objects_remain_supported(self):
        with tempfile.TemporaryDirectory() as root:
            response, status = server.playback_queue(
                {"cache_dir": root},
                {"queue": [{"id": "legacy", "title": "Legacy", "duration": 12.5}], "current_id": "legacy"},
            )

            self.assertEqual(status, 200)
            self.assertEqual(response["core"]["queue"], ["legacy"])
            self.assertEqual(response["core"]["duration"], 12.5)

    def test_queue_selection_prioritizes_current_metadata_without_affecting_save(self):
        class Metadata:
            def __init__(self):
                self.track_ids = []

            def prioritize_track(self, track_id):
                self.track_ids.append(track_id)

        with tempfile.TemporaryDirectory() as root:
            metadata = Metadata()
            previous = server.METADATA_SERVICE
            server.METADATA_SERVICE = metadata
            try:
                response, status = server.playback_queue(
                    {"cache_dir": root},
                    {"queue": ["current"], "current_id": "current"},
                )
            finally:
                server.METADATA_SERVICE = previous

            self.assertEqual(status, 200)
            self.assertTrue(response["ok"])
            self.assertEqual(metadata.track_ids, ["current"])


class LocalLoadSupersedesCastTests(unittest.TestCase):
    """Starting a library track here must end an incoming DLNA cast.

    The renderer shares this device's output, so a cast that is left registered
    after local playback starts keeps claiming the transport row on every
    status poll: the UI then repaints the pushed song over the track the user
    just chose, and stops the local element with it.
    """

    def _load(self, target_id):
        events = []

        class Renderer:
            def supersede(self, reason=""):
                events.append(("supersede", reason))
                return True

        class Protocol:
            renderer = Renderer()

        class Core:
            def set_target(self, target, kind):
                events.append(("target", target, kind))

            def dispatch(self, command):
                return {"ok": True, "state": {"queue": [], "current": ""}, "result": {"ok": True}}

            def snapshot(self):
                return {"queue": [], "current": ""}

        with tempfile.TemporaryDirectory() as root:
            handler = types.SimpleNamespace(server=types.SimpleNamespace(config={"cache_dir": root}))
            previous_protocol, previous_core = server.DLNA_PROTOCOL, server.PLAYBACK_CORE
            server.DLNA_PROTOCOL, server.PLAYBACK_CORE = Protocol(), Core()
            try:
                with mock.patch.object(server, "save_current_playback_session", return_value=7):
                    response, status = server.playback_load_selected(
                        handler, target_id, {"id": "track-1", "title": "Track"}, 0
                    )
            finally:
                server.DLNA_PROTOCOL, server.PLAYBACK_CORE = previous_protocol, previous_core

        self.assertEqual(status, 200)
        self.assertTrue(response["ok"])
        return events

    def test_a_local_load_supersedes_the_cast_before_the_core_switches_target(self):
        events = self._load("local")

        self.assertEqual(events[0][0], "supersede", "the cast must end before the target moves")
        self.assertTrue(events[0][1])
        self.assertEqual(events[1][0], "target")

    def test_a_load_on_a_usb_dac_supersedes_the_cast(self):
        events = self._load("mpd")

        self.assertEqual([event[0] for event in events], ["supersede", "target"])

    def test_pushing_to_another_device_leaves_the_incoming_cast_alone(self):
        # A dlna_push load drives a remote renderer, not this device's output, so
        # cutting a local cast there would silence playback the user never touched.
        events = self._load("dlna_push:uuid:remote-speaker")

        self.assertEqual([event[0] for event in events], ["target"])


if __name__ == "__main__":
    unittest.main()

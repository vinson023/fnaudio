import sys
import unittest

sys.path.insert(0, "app/server")

from playback_event_presentation import playback_event_payload


class PlaybackEventPresentationTests(unittest.TestCase):
    def test_projects_copy_and_normalizes_event_fields(self):
        core = {"target_id": "browser", "state_version": "4", "position": "2.5", "duration": 10, "transport": "playing"}
        payload = playback_event_payload(core, "mpd:usb")
        self.assertEqual(payload["target_id"], "local")
        self.assertEqual(payload["state_version"], 4)
        self.assertEqual(payload["position"], {"rel_seconds": 2.5, "duration_seconds": 10.0})
        self.assertEqual(payload["requested_target"], "mpd:usb")
        self.assertIs(payload["core"], core)

    def test_rejects_untrusted_values_without_object_stringification(self):
        payload = playback_event_payload({"state_version": object(), "position": object(), "duration": object(), "transport": object()}, object())
        self.assertEqual(payload["state_version"], 0)
        self.assertEqual(payload["position"], {"rel_seconds": 0.0, "duration_seconds": 0.0})
        self.assertEqual(payload["requested_target"], "")
        self.assertEqual(payload["transport"], {"state": "STOPPED"})

    def test_projects_session_identity_for_native_reconciliation(self):
        payload = playback_event_payload({
            "generation": 17,
            "engine_epoch": 3,
            "command_ticket": "ticket-1",
        })
        self.assertEqual(payload["generation"], 17)
        self.assertEqual(payload["engine_epoch"], 3)
        self.assertEqual(payload["command_ticket"], "ticket-1")

    def test_identity_projection_is_bounded(self):
        payload = playback_event_payload({
            "generation": 2**99,
            "engine_epoch": -4,
            "command_ticket": "x" * 1000,
        })
        self.assertEqual(payload["generation"], 2**31 - 1)
        self.assertEqual(payload["engine_epoch"], 0)
        self.assertEqual(len(payload["command_ticket"]), 128)

    def test_rejects_boolean_and_nonfinite_numeric_values(self):
        payload = playback_event_payload({
            "state_version": True,
            "generation": False,
            "engine_epoch": True,
            "position": float("nan"),
            "duration": float("inf"),
        })
        self.assertEqual(payload["state_version"], 0)
        self.assertEqual(payload["generation"], 0)
        self.assertEqual(payload["engine_epoch"], 0)
        self.assertEqual(payload["position"], {"rel_seconds": 0.0, "duration_seconds": 0.0})

    def test_declares_segment_units_without_refolding_the_authoritative_position(self):
        core = {"position": 42, "duration": 30, "state_version": 8}
        item = {"cue_track": True, "path": "/music/disc.flac", "cue_start": 100.0, "duration": 30}
        payload = playback_event_payload(core, "mpd:usb", item)
        self.assertIs(payload["cue_segment"], True)
        # Core seconds are already client units: adding cue_start here would move
        # the progress bar by the offset a second time.
        self.assertEqual(payload["position"], {"rel_seconds": 42.0, "duration_seconds": 30.0})

    def test_cue_declaration_falls_closed_for_every_unusable_item(self):
        for item in (None, "x", 1, {}, {"cue_track": False}, {"cue_track": 0}):
            payload = playback_event_payload({"position": 1}, "", item)
            self.assertIs(payload["cue_segment"], False, repr(item))

    def test_a_transcoded_segment_declares_the_same_units(self):
        payload = playback_event_payload(
            {"position": 7.5, "duration": 30},
            "mpd:usb",
            {"cue_track": True, "path": "/music/disc.ape", "cue_start": 100.0},
        )
        self.assertIs(payload["cue_segment"], True)
        self.assertEqual(payload["position"]["rel_seconds"], 7.5)


    def test_the_event_stream_publishes_the_snapshot_and_item_as_a_pair(self):
        """Wiring pin for the SSE route, which no unit test can reach.

        ``stream_playback_events`` lives inside the request handler, so the
        behaviour tests above cannot watch the declaration vanish at its only
        call site. Were that loop to go back to ``snapshot()`` or drop the third
        argument, every CUE frame would declare segment units as false and the
        client would fold an already folded position twice. It is labelled a
        wiring guard rather than behaviour coverage.
        """
        with open("app/server/server.py", encoding="utf-8") as source_file:
            source = source_file.read()
        start = source.index("def stream_playback_events(self, query):")
        end = source.index("self.wfile.write(keepalive_frame())", start)
        route = source[start:end]
        self.assertEqual(route.count("PLAYBACK_CORE.snapshot_with_item()"), 1, route)
        self.assertNotIn("core = PLAYBACK_CORE.snapshot()", route)
        self.assertEqual(
            route.count("playback_event_payload(core, requested_target, core_item)"),
            1,
            route,
        )


if __name__ == "__main__":
    unittest.main()

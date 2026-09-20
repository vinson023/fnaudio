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


if __name__ == "__main__":
    unittest.main()

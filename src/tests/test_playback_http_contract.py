import sys
import unittest

sys.path.insert(0, "app/server")

from playback.http_contract import (
    apply_legacy_player_state,
    legacy_control_payload,
    legacy_load_payload,
    legacy_response_headers,
    normalize_queue_tracks,
    normalize_target_id,
    playback_event_payload,
    target_kind,
)
from playback_queue_policy import queue_request, should_sync_mpd_queue


class FakeCoreState:
    def to_dict(self):
        return {"state_version": 7}


class FakeCore:
    def __init__(self):
        self.payload = None

    def sync_frontend(self, payload):
        self.payload = payload
        return FakeCoreState()


class PlaybackHttpContractTests(unittest.TestCase):
    def test_target_contract_normalizes_only_browser_aliases(self):
        self.assertEqual(target_kind("browser"), "browser")
        self.assertEqual(target_kind("mpd:usb:test"), "mpd")
        self.assertEqual(target_kind("mpd"), "mpd")
        self.assertEqual(target_kind("dac:usb:test"), "alsa")
        self.assertEqual(target_kind("alsa"), "alsa")
        self.assertEqual(target_kind("renderer-1"), "dlna_push")
        self.assertEqual(normalize_target_id("browser"), "local")
        self.assertEqual(normalize_target_id("renderer-1"), "renderer-1")

    def test_target_contract_rejects_non_text_identity_values(self):
        self.assertEqual(target_kind({"target": "mpd:bad"}), "browser")
        self.assertEqual(normalize_target_id(["mpd:bad"]), "local")
        self.assertEqual(normalize_target_id(" x " + "y" * 300), "x " + "y" * 126)

    def test_queue_contract_accepts_compact_and_legacy_items(self):
        legacy = {"track_id": "legacy", "title": "Legacy"}
        self.assertEqual(
            normalize_queue_tracks(["one", "", None, legacy, {"title": "missing id"}]),
            [{"id": "one"}, legacy],
        )

    def test_queue_contract_rejects_non_textual_object_ids(self):
        self.assertEqual(
            normalize_queue_tracks([{"id": ["one"]}, {"id": object()}, {"id": 7}]),
            [{"id": 7}],
        )
        self.assertEqual(
            normalize_queue_tracks([{"id": 0, "track_id": "fallback"}]),
            [{"id": 0, "track_id": "fallback"}],
        )

    def test_legacy_aliases_translate_to_canonical_payloads(self):
        payload = {"device_id": "dac:one", "track_id": "track", "position": 5, "action": "seek"}
        self.assertEqual(
            legacy_load_payload(payload),
            {"target_id": "dac:one", "track_id": "track", "position": 5},
        )
        self.assertEqual(
            legacy_control_payload(payload),
            {"target_id": "dac:one", "track_id": "track", "position": 5, "action": "seek"},
        )
        self.assertEqual(legacy_control_payload({}, "dac:fallback")["target_id"], "dac:fallback")

    def test_legacy_routes_advertise_their_successor(self):
        headers = legacy_response_headers("/api/upnp/push")
        self.assertEqual(headers["Deprecation"], "true")
        self.assertIn("/api/playback/load", headers["Link"])
        self.assertEqual(legacy_response_headers("/api/playback/load"), {})

        class ExplosiveString:
            def __str__(self):
                raise AssertionError("legacy path must not be stringified")

        self.assertEqual(legacy_response_headers(ExplosiveString()), {})

    def test_legacy_player_state_updates_compatibility_state_and_core(self):
        core = FakeCore()
        state = {"queue": [], "current": None, "playing": False}
        result = apply_legacy_player_state(
            {"queue": ["one"], "current": "one", "playing": True},
            state,
            core,
        )
        self.assertEqual(result["state"]["current"], "one")
        self.assertEqual(result["core"]["state_version"], 7)
        self.assertEqual(core.payload["queue"], ["one"])

    def test_legacy_player_state_does_not_store_non_boolean_playing(self):
        core = FakeCore()
        state = {"queue": [], "current": None, "playing": True}
        result = apply_legacy_player_state(
            {"playing": "false"},
            state,
            core,
        )
        self.assertIs(result["state"]["playing"], True)
        self.assertIs(core.payload["playing"], "false")

    def test_event_contract_is_target_neutral_and_bounded(self):
        core = {
            "target_id": "browser",
            "target_kind": "browser",
            "transport": "playing",
            "position": -3,
            "duration": "20",
            "state_version": "9",
        }
        payload = playback_event_payload(core, "browser")
        self.assertEqual(payload["target_id"], "local")
        self.assertEqual(payload["transport"]["state"], "PLAYING")
        self.assertEqual(payload["position"], {"rel_seconds": 0.0, "duration_seconds": 20.0})
        self.assertEqual(payload["state_version"], 9)

    def test_queue_request_is_safe_for_invalid_payloads_and_current_objects(self):
        self.assertEqual(queue_request(None), {
            "tracks": [], "current_id": "", "repeat": None, "shuffle": None,
        })
        result = queue_request({"queue": ["one"], "current": {"id": "one"}, "shuffle": False})
        self.assertEqual(result["tracks"], [{"id": "one"}])
        self.assertEqual(result["current_id"], "one")
        self.assertFalse(result["shuffle"])

        self.assertEqual(queue_request({"current_id": 0, "current": "fallback"})["current_id"], "0")

        class ExplosiveString:
            def __str__(self):
                raise AssertionError("current ID must not be stringified")

        self.assertEqual(queue_request({"current": ExplosiveString()})["current_id"], "")

    def test_queue_sync_policy_requires_mpd_and_nonempty_tracks(self):
        self.assertTrue(should_sync_mpd_queue("mpd", [{"id": "one"}]))
        self.assertFalse(should_sync_mpd_queue("mpd", []))
        self.assertFalse(should_sync_mpd_queue("alsa", [{"id": "one"}]))

        class ExplosiveValue:
            def __str__(self):
                raise AssertionError("target kind must not be stringified")

            def __bool__(self):
                raise AssertionError("tracks must not use arbitrary truthiness")

        self.assertFalse(should_sync_mpd_queue(ExplosiveValue(), [{"id": "one"}]))
        self.assertFalse(should_sync_mpd_queue("mpd", ExplosiveValue()))


if __name__ == "__main__":
    unittest.main()

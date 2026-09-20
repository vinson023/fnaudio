import unittest

import sys

sys.path.insert(0, "app/server")

from playback_status_response import (
    alsa_response,
    backend_error_response,
    browser_response,
    device_not_found_response,
    mpd_error_response,
    mpd_response,
    upnp_response,
)


class PlaybackStatusResponseTests(unittest.TestCase):
    def test_browser_and_alsa_shapes_are_stable(self):
        self.assertEqual(browser_response({"current": "a"}), {"kind": "browser", "status": {"current": "a"}})
        self.assertEqual(alsa_response({"available": True}, {"current": "a"})["kind"], "alsa")
        self.assertEqual(alsa_response(None, None)["core"], {})

    def test_mpd_response_uses_safe_transport_projection(self):
        payload = mpd_response({"running": True}, {"transport": {"state": "playing"}, "position": {"rel_seconds": 4}}, {"current": "a"})
        self.assertEqual(payload["transport"]["state"], "PLAYING")
        self.assertEqual(payload["position"]["rel_seconds"], 4.0)
        self.assertEqual(payload["core"]["current"], "a")

    def test_error_shapes_do_not_stringify_arbitrary_values(self):
        self.assertEqual(mpd_error_response(None, None)["error"], "MPD is not running")
        self.assertEqual(device_not_found_response(), {"error": "device not found"})
        self.assertEqual(backend_error_response(object())["error"], "backend status unavailable")
        self.assertEqual(upnp_response(None, None, None)["kind"], "upnp")

    def test_every_pollable_projection_carries_the_shared_version(self):
        core = {"state_version": 41, "current": "a"}
        payloads = (
            alsa_response({"available": True}, core),
            mpd_response({"running": True}, {}, core),
            upnp_response("PLAYING", {"rel_seconds": 1}, core),
        )
        for payload in payloads:
            self.assertEqual(payload["state_version"], 41, payload["kind"])
            self.assertIs(payload["cue_segment"], False, payload["kind"])
        # The browser lane answers with core state only, so it keeps its shape.
        self.assertEqual(set(browser_response({"state_version": 41})), {"kind", "status"})

    def test_state_version_coercion_never_leaks_arbitrary_values(self):
        cases = {
            41: 41,
            True: 0,
            False: 0,
            None: 0,
            "7": 7,
            -3: 0,
            2 ** 99: 2 ** 31 - 1,
        }
        for raw, expected in cases.items():
            self.assertEqual(alsa_response({}, {"state_version": raw})["state_version"], expected, repr(raw))
        for raw in (float("nan"), float("inf"), object(), []):
            self.assertEqual(alsa_response({}, {"state_version": raw})["state_version"], 0, repr(raw))
        self.assertEqual(alsa_response({}, None)["state_version"], 0)
        self.assertEqual(upnp_response(None, None, {"state_version": "x"})["state_version"], 0)

    def test_cue_segment_declaration_is_a_strict_boolean(self):
        self.assertIs(alsa_response({}, {}, cue_segment=True)["cue_segment"], True)
        for value in (1, "true", [True], None, object()):
            self.assertIs(alsa_response({}, {}, cue_segment=value)["cue_segment"], False, repr(value))
        self.assertIs(mpd_response({"running": True}, {}, {}, cue_segment=True)["cue_segment"], True)
        self.assertIs(upnp_response("PLAYING", {}, {}, cue_segment=True)["cue_segment"], True)
        # An error reply describes no position, so it must not claim units.
        self.assertNotIn("cue_segment", mpd_error_response("down", {}))
        self.assertNotIn("state_version", mpd_error_response("down", {}))


if __name__ == "__main__":
    unittest.main()

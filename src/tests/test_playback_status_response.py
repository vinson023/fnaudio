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


if __name__ == "__main__":
    unittest.main()

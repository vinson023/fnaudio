import sys
import unittest

sys.path.insert(0, "app/server")

from dlna.profiles import MAX_MIME_CHARS, device_supports_native_dsd, mime_for_item, protocol_info


class DlnaProfilesTests(unittest.TestCase):
    def test_mime_projection_keeps_valid_audio_types(self):
        self.assertEqual(mime_for_item({"mime": "audio/x-dsf"}), "audio/x-dsf")
        self.assertEqual(protocol_info({"mime": "audio/flac"}, {}), "http-get:*:audio/flac:*")

    def test_mime_projection_rejects_non_text_and_wire_unsafe_values(self):
        class Exploding:
            def __str__(self):
                raise AssertionError("MIME projection must not stringify arbitrary values")

        for value in (Exploding(), "audio/flac\r\nX-Injected: 1", "audio/" + "x" * MAX_MIME_CHARS):
            self.assertEqual(mime_for_item({"mime": value}), "application/octet-stream")
            self.assertEqual(protocol_info({"mime": value}, {}), "http-get:*:application/octet-stream:*")

    def test_mime_projection_uses_only_a_valid_text_fallback(self):
        self.assertEqual(mime_for_item({}, "audio/mpeg"), "audio/mpeg")
        self.assertEqual(mime_for_item({}, "bad fallback"), "application/octet-stream")

    def test_dsd_capability_does_not_coerce_text_values(self):
        self.assertFalse(device_supports_native_dsd({"supports_dsd": "false"}))
        self.assertFalse(device_supports_native_dsd({"supports_dsd": 1}))
        self.assertTrue(device_supports_native_dsd({"supports_dsd": True}))


if __name__ == "__main__":
    unittest.main()

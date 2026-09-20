import sys
import unittest

sys.path.insert(0, "app/server")

from dlna.event_payload import MAX_EVENT_BODY_BYTES, MAX_EVENT_METADATA_CHARS, MAX_EVENT_URI_CHARS, renderer_event_body


class DlnaEventPayloadTests(unittest.TestCase):
    def test_avtransport_event_bounds_untrusted_text_without_object_coercion(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("event payload must not stringify arbitrary state")

        body = renderer_event_body("avtransport", {
            "transport": Explosive(),
            "uri": "u" * (MAX_EVENT_URI_CHARS + 100),
            "metadata": "m" * (MAX_EVENT_METADATA_CHARS + 100),
            "position": Explosive(),
        })
        text = body.decode("utf-8")
        self.assertIn("TransportState val=&quot;STOPPED&quot;", text)
        self.assertLessEqual(len(body), MAX_EVENT_BODY_BYTES)
        self.assertIn("m" * 1024, text)
        self.assertNotIn("m" * (MAX_EVENT_METADATA_CHARS + 1), text)

    def test_rendering_event_is_safe_for_non_mapping_state(self):
        self.assertIn(b"<Volume", renderer_event_body("rendering", None))

    def test_rendering_event_does_not_coerce_malformed_mute_values(self):
        body = renderer_event_body("rendering", {"volume": 20, "muted": "false"})
        self.assertIn(b'<Mute channel="Master">0</Mute>', body)
        body = renderer_event_body("rendering", {"volume": 20, "muted": True})
        self.assertIn(b'<Mute channel="Master">1</Mute>', body)

    def test_escape_heavy_metadata_stays_within_body_budget(self):
        body = renderer_event_body("avtransport", {
            "uri": '"' * (MAX_EVENT_URI_CHARS + 20),
            "metadata": '"' * (MAX_EVENT_METADATA_CHARS + 20),
        })
        self.assertTrue(body)
        self.assertLessEqual(len(body), MAX_EVENT_BODY_BYTES)

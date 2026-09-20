import sys
import unittest

sys.path.insert(0, "app/server")

from xml_response_policy import MAX_XML_RESPONSE_BYTES, serialize_xml_response


class XmlResponsePolicyTests(unittest.TestCase):
    def test_accepts_text_and_bytes(self):
        self.assertEqual(serialize_xml_response("<ok/>"), (b"<ok/>", True))
        self.assertEqual(serialize_xml_response(b"<ok/>"), (b"<ok/>", True))

    def test_rejects_oversized_payload_without_partial_body(self):
        body, valid = serialize_xml_response(b"x" * 33, maximum=32)
        self.assertFalse(valid)
        self.assertNotIn(b"x" * 33, body)
        self.assertLess(len(body), MAX_XML_RESPONSE_BYTES)

    def test_rejects_untrusted_types_without_coercion(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("XML policy must not stringify arbitrary values")
        body, valid = serialize_xml_response(Explosive())
        self.assertFalse(valid)
        self.assertIn(b"response unavailable", body)

    def test_invalid_limit_uses_default(self):
        body, valid = serialize_xml_response("<ok/>", maximum=True)
        self.assertTrue(valid)
        self.assertLess(len(body), MAX_XML_RESPONSE_BYTES)

    def test_custom_limit_cannot_raise_global_response_budget(self):
        body, valid = serialize_xml_response(b"x" * (MAX_XML_RESPONSE_BYTES + 1), maximum=MAX_XML_RESPONSE_BYTES * 2)
        self.assertFalse(valid)
        self.assertIn(b"response unavailable", body)

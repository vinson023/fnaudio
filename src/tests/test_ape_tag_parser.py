import sys
import unittest

sys.path.insert(0, "app/server")

from ape_tag_parser import parse_ape_body, parse_ape_items


class ApeTagParserTests(unittest.TestCase):
    @staticmethod
    def item(key, value, flags=b"\x00\x00\x00\x00"):
        return len(value).to_bytes(4, "little") + flags + key.encode() + b"\x00" + value

    def test_parses_valid_footer_and_preserves_audio_prefix(self):
        audio = b"audio-body"
        payload = self.item("Title", b"Song")
        footer = b"APETAGEX" + b"2000" + (32 + len(payload)).to_bytes(4, "little") + (1).to_bytes(4, "little") + b"\x00" * 12
        prefix, items = parse_ape_body(audio + payload + footer)
        self.assertEqual(prefix, audio)
        self.assertEqual(items, [("Title", b"\x00\x00\x00\x00", b"Song")])

    def test_malformed_and_non_binary_inputs_are_safe(self):
        self.assertEqual(parse_ape_body("not-bytes"), (b"", []))
        body = b"audio" + b"APETAGEX" + b"\x00" * 24
        self.assertEqual(parse_ape_body(body), (body, []))

    def test_item_parser_rejects_truncation_and_untrusted_count(self):
        payload = self.item("Title", b"Song")
        self.assertIsNone(parse_ape_items(payload[:-1], 1))
        self.assertIsNone(parse_ape_items(payload, True))


if __name__ == "__main__":
    unittest.main()

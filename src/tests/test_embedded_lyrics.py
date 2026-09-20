import sys
import unittest

sys.path.insert(0, "app/server")

from embedded_lyrics import extract_embedded_lyrics


class EmbeddedLyricsTests(unittest.TestCase):
    def test_prefers_format_or_stream_lyrics_and_normalizes_keys(self):
        payload = {
            "format": {"tags": {"title": "Song"}},
            "streams": [{"tags": {"UNSYNCEDLYRICS": "  line one  "}}],
        }
        self.assertEqual(extract_embedded_lyrics(payload), "line one")

    def test_malformed_payload_and_non_text_values_are_safe(self):
        self.assertEqual(extract_embedded_lyrics(None), "")
        self.assertEqual(extract_embedded_lyrics({"format": {"tags": {"lyrics": 123}}}), "")
        self.assertEqual(extract_embedded_lyrics({"streams": [None, {"tags": "bad"}]}), "")

    def test_ignores_non_text_tag_keys_without_stringifying_them(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("tag keys must not be stringified")

        self.assertEqual(
            extract_embedded_lyrics({"format": {"tags": {Explosive(): "lyrics"}}}),
            "",
        )


if __name__ == "__main__":
    unittest.main()

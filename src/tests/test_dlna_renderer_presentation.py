import sys
import unittest

sys.path.insert(0, "app/server")

from dlna.renderer_presentation import (
    MAX_RENDERER_DISPLAY_CHARS,
    MAX_RENDERER_METADATA_CHARS,
    MAX_RENDERER_URI_CHARS,
    metadata_fields,
    normalize_renderer_media,
)


class DlnaRendererPresentationTests(unittest.TestCase):
    def test_state_media_is_bounded_without_object_coercion(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("renderer state must not stringify input")

        uri, metadata = normalize_renderer_media("u" * (MAX_RENDERER_URI_CHARS + 1), Explosive())
        self.assertEqual(len(uri), MAX_RENDERER_URI_CHARS)
        self.assertEqual(metadata, "")

    def test_didl_fields_are_display_bounded_and_fall_back_to_uri(self):
        metadata = '<DIDL-Lite><item><title>%s</title><artist>Artist</artist></item></DIDL-Lite>' % ("x" * (MAX_RENDERER_DISPLAY_CHARS + 20))
        title, artist, art = metadata_fields(metadata, "http://example.test/fallback.flac")
        self.assertEqual(len(title), MAX_RENDERER_DISPLAY_CHARS)
        self.assertEqual(artist, "Artist")
        self.assertEqual(art, "")
        title, artist, art = metadata_fields("x" * (MAX_RENDERER_METADATA_CHARS + 1), "http://example.test/fallback.flac")
        self.assertEqual((title, artist, art), ("fallback.flac", "", ""))

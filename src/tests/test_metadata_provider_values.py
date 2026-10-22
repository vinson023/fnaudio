import sys
import unittest

sys.path.insert(0, "app/server")

from metadata_provider_values import provider_display_text, provider_int, provider_text


class MetadataProviderValuesTests(unittest.TestCase):
    def test_text_projection_removes_nul_and_bounds_values(self):
        self.assertEqual(provider_text("  a\x00b  "), "ab")
        self.assertEqual(provider_text("abcdef", 3), "abc")
        self.assertEqual(provider_text("abcdef", True), "abcdef")

    def test_text_projection_rejects_malformed_limits_without_coercion(self):
        class Explosive:
            def __int__(self):
                raise AssertionError("limit must not be coerced")

        self.assertEqual(provider_text("safe", Explosive()), "safe")
        self.assertEqual(provider_text("safe", -1), "safe")
        self.assertEqual(provider_text(object()), "")

    def test_display_text_removes_kugou_highlight_markup_without_coercing_values(self):
        self.assertEqual(provider_display_text("<em>Song</em>"), "Song")
        self.assertEqual(provider_display_text('<em class="keyword">歌名</em>'), "歌名")
        self.assertEqual(provider_display_text("&lt;em&gt;Title&lt;/em&gt;"), "Title")
        self.assertEqual(provider_display_text("A < B"), "A < B")
        self.assertEqual(provider_display_text(object()), "")

    def test_numeric_projection_keeps_legacy_supported_values(self):
        self.assertEqual(provider_int("42"), 42)
        self.assertEqual(provider_int(4.9, minimum=5, maximum=8), 5)
        self.assertEqual(provider_int(True, default=7), 7)
        self.assertEqual(provider_int("bad", default=7), 7)


if __name__ == "__main__":
    unittest.main()

"""Regression tests for the artwork media type that leaves the service.

A cover's declared MIME string is tagger-controlled free text: an ID3 APIC frame
and a FLAC PICTURE block both carry it, and provider artwork carries it in an
HTTP response header. All three are answered on the service origin, so the type
has to be resolved from pixels, never echoed.
"""

import sys
import unittest

sys.path.insert(0, "app/server")

from cover_media_type import (
    ALLOWED_IMAGE_MEDIA_TYPES,
    MAX_MEDIA_TYPE_CHARS,
    SNIFF_PREFIX_BYTES,
    normalize_media_type,
    safe_image_media_type,
    sniff_image_media_type,
)


JPEG = b"\xff\xd8\xff\xe0jpeg-payload"
PNG = b"\x89PNG\r\n\x1a\npng-payload"
GIF = b"GIF89a\x01\x00\x01\x00gif-payload"
BMP = b"BM\x00\x00\x00\x00bmp-payload"
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"webp-payload"
AVIF = b"\x00\x00\x00\x18ftypavif\x00\x00\x00\x00avif-payload"
HEIC = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00heic-payload"
TIFF = b"II*\x00little-tiff-payload"
HTML = b"<script>alert(document.domain)</script>"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>'


class SniffImageMediaTypeTests(unittest.TestCase):
    def test_proves_every_format_the_allowlist_claims(self):
        for body, expected in (
            (JPEG, "image/jpeg"),
            (PNG, "image/png"),
            (GIF, "image/gif"),
            (BMP, "image/bmp"),
            (WEBP, "image/webp"),
            (AVIF, "image/avif"),
            (HEIC, "image/heic"),
            (TIFF, "image/tiff"),
        ):
            self.assertEqual(sniff_image_media_type(body), expected, expected)

    def test_the_reach_it_needs_is_twelve_bytes(self):
        # WEBP and the ISO-BMFF brands are provable only at offset 8..12, so the
        # sniff window has a real lower bound; shrinking it silently loses types.
        self.assertLessEqual(12, SNIFF_PREFIX_BYTES)
        self.assertEqual(sniff_image_media_type(WEBP[:11]), "")
        self.assertEqual(sniff_image_media_type(WEBP[:12]), "image/webp")
        self.assertEqual(sniff_image_media_type(AVIF[:11]), "")
        self.assertEqual(sniff_image_media_type(AVIF[:12]), "image/avif")

    def test_accepts_every_buffer_shape_a_route_can_hand_it(self):
        self.assertEqual(sniff_image_media_type(bytearray(PNG)), "image/png")
        self.assertEqual(sniff_image_media_type(memoryview(PNG)), "image/png")

    def test_returns_unknown_for_non_binary_input_and_short_or_foreign_payloads(self):
        self.assertEqual(sniff_image_media_type("image/png"), "")
        self.assertEqual(sniff_image_media_type(None), "")
        self.assertEqual(sniff_image_media_type(b""), "")
        self.assertEqual(sniff_image_media_type(b"BM"), "")
        self.assertEqual(sniff_image_media_type(b"RIFF\x00\x00\x00\x00AVI "), "")
        self.assertEqual(sniff_image_media_type(b"\x00\x00\x00\x00ftypqt  "), "")
        self.assertEqual(sniff_image_media_type(HTML), "")

    def test_reads_no_further_than_the_declared_sniff_window(self):
        marker = b"\x00" * (SNIFF_PREFIX_BYTES + 1) + JPEG
        self.assertEqual(len(marker), SNIFF_PREFIX_BYTES + 1 + len(JPEG))
        self.assertEqual(sniff_image_media_type(marker), "")


class NormalizeMediaTypeTests(unittest.TestCase):
    def test_canonicalizes_case_padding_and_parameters(self):
        self.assertEqual(normalize_media_type("IMAGE/JPEG "), "image/jpeg")
        self.assertEqual(normalize_media_type(" image/png;charset=utf-8 "), "image/png")
        self.assertEqual(normalize_media_type("image/svg+xml"), "image/svg+xml")

    def test_maps_the_aliases_taggers_actually_write(self):
        self.assertEqual(normalize_media_type("image/jpg"), "image/jpeg")
        self.assertEqual(normalize_media_type("image/pjpeg"), "image/jpeg")
        self.assertEqual(normalize_media_type("image/x-png"), "image/png")
        self.assertEqual(normalize_media_type("image/x-ms-bmp"), "image/bmp")
        self.assertEqual(normalize_media_type("image/x-bitmap"), "image/bmp")
        self.assertEqual(normalize_media_type("image/x-icon"), "image/png")

    def test_refuses_text_that_cannot_appear_in_a_response_header(self):
        self.assertEqual(normalize_media_type("image/png\r\nSet-Cookie: a=b"), "")
        self.assertEqual(normalize_media_type("image/png\nX-Injected: 1"), "")
        self.assertEqual(normalize_media_type('image/png"; q=1'), "")
        self.assertEqual(normalize_media_type("image/png image/gif"), "")
        self.assertEqual(normalize_media_type("image/png\x00"), "")

    def test_refuses_non_images_non_strings_and_overlong_values(self):
        self.assertEqual(normalize_media_type("text/html"), "")
        self.assertEqual(normalize_media_type("application/octet-stream"), "")
        self.assertEqual(normalize_media_type("image"), "")
        self.assertEqual(normalize_media_type(""), "")
        self.assertEqual(normalize_media_type("   "), "")
        self.assertEqual(normalize_media_type(b"image/png"), "")
        self.assertEqual(normalize_media_type(None), "")
        self.assertEqual(normalize_media_type("image/" + "x" * MAX_MEDIA_TYPE_CHARS), "")
        self.assertEqual(normalize_media_type("image/" + "x" * (MAX_MEDIA_TYPE_CHARS - 6)), "image/" + "x" * (MAX_MEDIA_TYPE_CHARS - 6))


class SafeImageMediaTypeTests(unittest.TestCase):
    def test_bytes_beat_a_wrong_declaration(self):
        self.assertEqual(safe_image_media_type("image/png", JPEG), "image/jpeg")
        self.assertEqual(safe_image_media_type("text/html", PNG), "image/png")
        self.assertEqual(safe_image_media_type("image/svg+xml", GIF), "image/gif")

    def test_honours_an_allowlisted_declaration_for_pixels_it_cannot_read(self):
        self.assertEqual(safe_image_media_type("image/webp", b"\x00\x01\x02\x03opaque"), "image/webp")
        self.assertEqual(safe_image_media_type("IMAGE/JPEG", None), "image/jpeg")

    def test_refuses_a_declaration_that_is_not_an_allowed_raster_type(self):
        self.assertEqual(safe_image_media_type("text/html", b"\x00\x01\x02\x03opaque"), "")
        self.assertEqual(safe_image_media_type("image/svg+xml", b"\x00\x01\x02\x03opaque"), "")
        self.assertEqual(safe_image_media_type("image/evil\r\nX: 1", b"\x00\x01\x02\x03"), "")
        self.assertEqual(safe_image_media_type("", b"\x00\x01\x02\x03"), "")
        self.assertEqual(safe_image_media_type(None, None), "")

    def test_refuses_a_document_under_a_raster_declaration(self):
        # The dangerous combination: an embedded HTML or SVG payload that the tag
        # labels image/jpeg, which the permissive fallback would otherwise serve.
        self.assertEqual(safe_image_media_type("image/jpeg", HTML), "")
        self.assertEqual(safe_image_media_type("image/jpeg", SVG), "")
        self.assertEqual(safe_image_media_type("image/png", b"  " + HTML), "")
        self.assertEqual(safe_image_media_type("image/png", b'{"json": true}'), "")

    def test_svg_is_not_an_allowed_type_anywhere_in_the_policy(self):
        self.assertNotIn("image/svg+xml", ALLOWED_IMAGE_MEDIA_TYPES)
        for media_type in ALLOWED_IMAGE_MEDIA_TYPES:
            self.assertEqual(normalize_media_type(media_type), media_type)


if __name__ == "__main__":
    unittest.main()
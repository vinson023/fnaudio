import base64
import gzip
import sys
import unittest

sys.path.insert(0, "app/server")

from metadata_provider_response import (
    MAX_PROVIDER_LYRICS_BYTES,
    MAX_PROVIDER_RESPONSE_BYTES,
    MAX_PROVIDER_LYRICS_BASE64_CHARS,
    decode_base64_lyrics,
    decode_lyrics_text,
    lyrics_document,
    decode_provider_json,
    decompress_gzip_limited,
    read_response_limited,
)


class MetadataProviderResponseTests(unittest.TestCase):
    def test_json_decoder_handles_mislabeled_utf8_and_bounded_jsonp(self):
        self.assertEqual(
            decode_provider_json('{"title":"周杰伦"}'.encode(), "application/json; charset=latin-1"),
            {"title": "周杰伦"},
        )
        self.assertEqual(
            decode_provider_json(b"cb({\"title\":\"Song\"});", "application/javascript"),
            {"title": "Song"},
        )

    def test_lyrics_decoder_preserves_supported_encodings_and_base64(self):
        lyric = "[00:01.00]晴天"
        self.assertEqual(decode_lyrics_text(lyric.encode("gb18030")), lyric)
        self.assertEqual(decode_base64_lyrics(base64.b64encode(lyric.encode()).decode()), lyric)
        with self.assertRaisesRegex(ValueError, "replacement"):
            decode_lyrics_text("晴\ufffd天".encode())

    def test_gzip_and_response_reads_are_bounded(self):
        compressed = gzip.compress(b"provider")
        self.assertEqual(decompress_gzip_limited(compressed, 32), b"provider")
        with self.assertRaisesRegex(ValueError, "exceeds limit"):
            decompress_gzip_limited(gzip.compress(b"x" * 33), 32)

        class Response:
            def read(self, size):
                return b"x" * (size + 1)

        with self.assertRaisesRegex(ValueError, "exceeds limit"):
            read_response_limited(Response(), 8)

        class ShortResponse:
            def __init__(self):
                self.payload = b"provider"

            def read(self, size):
                if not self.payload:
                    return b""
                chunk, self.payload = self.payload[:2], self.payload[2:]
                return chunk

        self.assertEqual(read_response_limited(ShortResponse(), 32), b"provider")

    def test_lyric_limit_is_enforced_before_decode(self):
        with self.assertRaisesRegex(ValueError, "exceeds limit"):
            decode_lyrics_text(b"x" * (MAX_PROVIDER_LYRICS_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "exceeds limit"):
            decode_base64_lyrics("A" * (MAX_PROVIDER_LYRICS_BASE64_CHARS + 1))


    def test_base64_lyric_budget_is_checked_before_the_decode(self):
        # Decoding first would allocate the oversized copy that is about to be
        # refused, so the encoded length has to settle the budget on its own.
        calls = []
        original = base64.b64decode
        base64.b64decode = lambda *args, **kwargs: calls.append(args) or b""
        try:
            with self.assertRaisesRegex(ValueError, "exceeds limit"):
                decode_base64_lyrics("A" * (MAX_PROVIDER_LYRICS_BASE64_CHARS + 4))
        finally:
            base64.b64decode = original
        self.assertEqual(calls, [], "the over-budget field was decoded before being refused")

    def test_base64_lyric_ceiling_is_the_expansion_of_the_document_budget(self):
        # The ceiling is four characters per decoded byte trio, not the byte
        # budget itself: a document that fills the budget has to survive.
        document = "a" * MAX_PROVIDER_LYRICS_BYTES
        encoded = base64.b64encode(document.encode()).decode()
        self.assertEqual(len(encoded), MAX_PROVIDER_LYRICS_BASE64_CHARS)
        self.assertEqual(decode_base64_lyrics(encoded), document)
        with self.assertRaisesRegex(ValueError, "exceeds limit"):
            decode_base64_lyrics(encoded + "AAAA")

    def test_base64_lyric_decodes_the_text_it_just_checked_for_emptiness(self):
        # Providers pad this field; validate=True rejects whitespace, so a lane
        # that strips for the emptiness test and decodes the raw value loses the
        # lyric entirely instead of returning it.
        lyric = "[00:01.00]晴天"
        encoded = base64.b64encode(lyric.encode()).decode()
        for padded in (encoded + "\n", " " + encoded, "\r\n" + encoded + "\t"):
            with self.subTest(padded=padded[:3]):
                self.assertEqual(decode_base64_lyrics(padded), lyric)
        self.assertEqual(decode_base64_lyrics("   \n"), "")

    def test_base64_lyric_survives_mime_folding(self):
        # RFC 2045 folds a base64 field with CRLF every 76 characters.  Those line
        # breaks carry no information, yet refusing them dropped the whole lyric.
        lyric = "[00:01.00]稻香\n[00:04.00]词：周杰伦"
        encoded = base64.b64encode(lyric.encode()).decode()
        folded = "\r\n".join(encoded[index:index + 4] for index in range(0, len(encoded), 4))
        self.assertNotEqual(folded, encoded)
        self.assertEqual(decode_base64_lyrics(folded), lyric)
        spaced = " ".join(encoded[index:index + 3] for index in range(0, len(encoded), 3))
        self.assertEqual(decode_base64_lyrics(spaced), lyric)

    def test_folding_cannot_smuggle_payload_past_the_encoded_ceiling(self):
        # The ceiling has to be measured on the normalized text: otherwise a field
        # padded with line breaks either fails while it fits, or the padding itself
        # becomes the way past the budget.
        document = "a" * MAX_PROVIDER_LYRICS_BYTES
        encoded = base64.b64encode(document.encode()).decode()
        folded = "\r\n".join(encoded[index:index + 76] for index in range(0, len(encoded), 76))
        self.assertGreater(len(folded), len(encoded))
        self.assertEqual(decode_base64_lyrics(folded), document)
        with self.assertRaisesRegex(ValueError, "exceeds limit"):
            decode_base64_lyrics(folded + "\r\nAAAA")

    def test_only_ascii_whitespace_is_normalized_inside_a_base64_field(self):
        # Deleting U+00A0 or U+0085 as well (what `"".join(value.split())` would do)
        # launders payloads the provider really corrupted into accepted lyrics, and
        # replacement-free mojibake is the one outcome this decoder exists to stop.
        encoded = base64.b64encode("[00:00.00]ok".encode()).decode()
        for junk in ("\x00", "\xa0", "\x85", "!"):
            with self.subTest(junk=repr(junk)):
                damaged = encoded[:4] + junk + encoded[4:]
                self.assertEqual(decode_base64_lyrics(damaged.replace(junk, "")), "[00:00.00]ok")
                with self.assertRaisesRegex(ValueError, "invalid"):
                    decode_base64_lyrics(damaged)

    def test_decoder_does_not_coerce_untrusted_content_type_or_limits(self):
        class Explosive:
            def __bool__(self):
                raise AssertionError("decoder must not evaluate arbitrary truthiness")

            def __str__(self):
                raise AssertionError("decoder must not stringify arbitrary objects")

        self.assertEqual(decode_provider_json(b'{"ok":true}', Explosive()), {"ok": True})
        self.assertEqual(decode_lyrics_text(b"safe", Explosive()), "safe")
        self.assertEqual(decompress_gzip_limited(gzip.compress(b"safe"), Explosive()), b"safe")
        self.assertEqual(decode_base64_lyrics("c2FmZQ==", Explosive()), "safe")
        for drifted in ({"content": 1}, ["a"], 7, None, b"c2FmZQ=="):
            with self.subTest(value=type(drifted).__name__):
                self.assertEqual(decode_base64_lyrics(drifted), "")


class LyricsDocumentBudgetTests(unittest.TestCase):
    """`lyrics_document` is the one byte budget every lyric reader shares."""

    CJK = chr(0x4e2d)

    def test_non_text_documents_carry_nothing(self):
        for unusable in (None, b"lyrics", ["a"], 12, True, object()):
            with self.subTest(value=type(unusable).__name__):
                self.assertEqual(lyrics_document(unusable), "")

    def test_nul_bytes_are_dropped_and_the_document_is_trimmed(self):
        self.assertEqual(lyrics_document(chr(0) + " [00:01]hi" + chr(0) + chr(10)), "[00:01]hi")
        self.assertEqual(lyrics_document("   " + chr(0) + "  "), "")

    def test_the_budget_is_measured_in_bytes_not_characters(self):
        # Three CJK characters cost nine bytes, so a character count of three
        # would accept this against a budget of eight.
        self.assertEqual(lyrics_document(self.CJK * 3, limit=8), "")
        self.assertEqual(lyrics_document(self.CJK * 2 + "xx", limit=8), self.CJK * 2 + "xx")
        self.assertEqual(lyrics_document(self.CJK * 3, limit=9), self.CJK * 3)

    def test_a_caller_cannot_raise_the_budget(self):
        # The limit argument only ever tightens the module budget.
        self.assertEqual(lyrics_document("x" * 9, limit=8), "")
        self.assertEqual(lyrics_document("x" * 8, limit=8), "x" * 8)
        self.assertEqual(lyrics_document("x" * 8, limit=8 * 4), "x" * 8)
        self.assertEqual(lyrics_document("x" * (MAX_PROVIDER_LYRICS_BYTES + 1),
                                         limit=MAX_PROVIDER_RESPONSE_BYTES * 4), "")

    def test_the_early_out_agrees_with_the_exact_measurement(self):
        # Both branches must refuse the same nine-byte document: one by
        # arithmetic on the character count, the other by measuring UTF-8.
        self.assertEqual(lyrics_document("x" * 9, limit=8), "")
        self.assertEqual(lyrics_document(self.CJK * 3, limit=8), "")
        self.assertEqual(lyrics_document(self.CJK * 2 + "xx", limit=9), self.CJK * 2 + "xx")

    def test_hostile_limits_fall_back_to_the_module_budget(self):
        for limit in (0, -1, True, "8", None, 1.5):
            with self.subTest(limit=repr(limit)):
                self.assertEqual(lyrics_document("[00:01]hi", limit=limit), "[00:01]hi")

    def test_the_module_budget_boundary_is_exact(self):
        self.assertEqual(len(lyrics_document("x" * MAX_PROVIDER_LYRICS_BYTES)), MAX_PROVIDER_LYRICS_BYTES)
        self.assertEqual(lyrics_document("x" * (MAX_PROVIDER_LYRICS_BYTES + 1)), "")


if __name__ == "__main__":
    unittest.main()

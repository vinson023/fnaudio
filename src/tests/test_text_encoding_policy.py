"""R591: the legacy-text decoding must actually reach Big5 and Shift-JIS.

The old chain was ``utf-8-sig -> gb18030 -> big5 -> latin1``.  It could not work:
``gb18030`` accepts almost every byte pair, so it never raised, ``big5`` was
unreachable, and ``latin1`` accepts *everything* -- which is how a Big5 sheet's
「晴天」 came out as 「锤ぱ」 with no error reported anywhere.

These tests use the three encodings a Chinese-language library actually meets.
Each fixture is a realistic CUE sheet rather than a two-character sample, because
the scorer's script markers need real text to fire: a two-character title is
genuinely ambiguous between GBK and Big5, and the module says so instead of
guessing.
"""

import sys
import unittest

sys.path.insert(0, "app/server")

from text_encoding_policy import (
    LEGACY_CANDIDATES,
    decode_lines,
    decode_text,
    normalize_encoding_setting,
)

CUE = 'FILE "CDImage.ape" WAVE\n  TRACK 01 AUDIO\n    TITLE "%s"\n    PERFORMER "%s"\n    INDEX 01 00:00:00\n'

# Traditional, Simplified and Japanese sheets with the same shape.  The markers
# the scorer keys on are 倫/樂/團 (traditional only) and 这/时/团 (simplified only)
# and the kana run in the Japanese one.
FIXTURES = {
    "big5": ("晴天", "周杰倫樂團", "big5"),
    "gb18030": ("晴天", "周杰伦乐队", "gb18030"),
    "shift_jis": ("夜に駆ける", "ヨルシカ", "shift_jis"),
}


def cue_bytes(title, performer, encoding):
    return (CUE % (title, performer)).encode(encoding)


class DecodeTextTests(unittest.TestCase):
    def test_each_legacy_encoding_round_trips_through_its_own_bytes(self):
        for expected, (title, performer, encoding) in FIXTURES.items():
            with self.subTest(encoding=expected):
                raw = cue_bytes(title, performer, encoding)
                text, used = decode_text(raw)
                self.assertEqual(text, CUE % (title, performer), "decoded text is wrong for %s" % expected)
                self.assertEqual(used, expected, "picked %s for %s bytes" % (used, expected))

    def test_the_big5_sheet_no_longer_decodes_as_mojibake(self):
        # The exact reported shape: gb18030 swallows these bytes and produces
        # 「锤ぱ」, which is what the old chain returned.
        raw = cue_bytes("晴天", "周杰倫樂團", "big5")
        text, used = decode_text(raw)
        self.assertEqual(used, "big5")
        self.assertIn("周杰倫", text)
        self.assertNotIn("锤ぱ", text)

    def test_utf8_is_settled_before_any_heuristic(self):
        # A byte sequence valid as strict UTF-8 is almost certainly UTF-8, so it
        # must not be scored against the legacy candidates.
        raw = (CUE % ("晴天", "周杰倫")).encode("utf-8")
        text, used = decode_text(raw)
        self.assertEqual(used, "utf-8-sig")
        self.assertIn("周杰倫", text)

    def test_a_byte_order_mark_outranks_the_configured_setting(self):
        raw = (CUE % ("晴天", "周杰倫")).encode("utf-16")
        text, used = decode_text(raw, explicit="big5")
        self.assertEqual(used, "utf-16")
        self.assertIn("晴天", text)

    def test_an_explicit_setting_wins_over_the_heuristic(self):
        # Two characters carry no script marker, so the scorer cannot separate
        # GBK from Big5 -- this is exactly the case the setting exists for.
        raw = "晴天".encode("big5")
        _text, auto = decode_text(raw)
        text, used = decode_text(raw, explicit="big5")
        self.assertEqual(used, "big5")
        self.assertEqual(text, "晴天")
        self.assertIn(auto, LEGACY_CANDIDATES, "auto must still land on a legacy candidate")

    def test_an_unknown_setting_is_treated_as_auto(self):
        self.assertEqual(normalize_encoding_setting("nonsense"), "")
        self.assertEqual(normalize_encoding_setting("  GBK "), "gb18030")
        self.assertEqual(normalize_encoding_setting("cp950"), "big5")
        self.assertEqual(normalize_encoding_setting("Shift-JIS"), "shift_jis")
        self.assertEqual(normalize_encoding_setting(None), "")
        # A setting that cannot decode the file must not hide it.
        raw = cue_bytes("晴天", "周杰倫樂團", "big5")
        text, used = decode_text(raw, explicit="shift_jis")
        self.assertIn(used, LEGACY_CANDIDATES)
        self.assertIn("周杰倫", text)

    def test_undecodable_and_empty_payloads_report_nothing(self):
        self.assertEqual(decode_text(b""), (None, ""))
        self.assertEqual(decode_text(None), (None, ""))
        self.assertEqual(decode_text("not bytes"), (None, ""))

    def test_decode_lines_keeps_the_crlf_handling(self):
        raw = "TITLE \"A\"\r\nTRACK 01 AUDIO\r\n".encode("utf-8")
        self.assertEqual(decode_lines(raw), ['TITLE "A"', "TRACK 01 AUDIO"])


class CueReaderIntegrationTests(unittest.TestCase):
    def test_the_cue_reader_uses_the_policy_and_honours_the_config(self):
        import os
        import tempfile

        from cue_reader import read_cue_lines

        with tempfile.TemporaryDirectory() as scratch:
            path = os.path.join(scratch, "album.cue")
            with open(path, "wb") as handle:
                handle.write(cue_bytes("晴天", "周杰倫樂團", "big5"))
            auto = read_cue_lines(path)
            self.assertTrue(any('TITLE "晴天"' in line for line in auto), auto)
            self.assertTrue(any('PERFORMER "周杰倫樂團"' in line for line in auto), auto)
            # The explicit setting is read from the library config, and a wrong
            # one still has to leave readable text rather than raising.
            configured = read_cue_lines(path, {"text_encoding": "big5"})
            self.assertEqual(configured, auto)


if __name__ == "__main__":
    unittest.main()

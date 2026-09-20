import sys
import unittest
import zlib

sys.path.insert(0, "app/server")

from id3_parser import (
    decode_id3_text,
    decode_id3v1_field,
    id3_frame_region,
    id3_tag_is_readable,
    iter_id3_frames,
    parse_id3_cover,
    parse_id3_tags,
)


def _syncsafe(value):
    return bytes(((value >> 21) & 0x7F, (value >> 14) & 0x7F, (value >> 7) & 0x7F, value & 0x7F))


def _frame(frame_id, payload, major=3, flags=0):
    size = len(payload)
    if major == 4:
        encoded = bytes(((size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F))
    else:
        encoded = size.to_bytes(4, "big")
    return frame_id.encode("ascii") + encoded + flags.to_bytes(2, "big") + payload


class Id3ParserTests(unittest.TestCase):
    def test_reads_text_and_track_number_frames(self):
        data = _frame("TIT2", b"\x03Song") + _frame("TPE1", b"\x03Artist") + _frame("TRCK", b"\x033/12")
        self.assertEqual(parse_id3_tags(data), {"title": "Song", "artist": "Artist", "track_no": 3})

    def test_reads_syncsafe_v24_frames(self):
        data = _frame("TALB", b"\x03Album", major=4)
        self.assertEqual(parse_id3_tags(data, major=4), {"album": "Album"})

    def test_truncated_frame_is_ignored_without_reading_past_input(self):
        data = b"TIT2" + (1024).to_bytes(4, "big") + b"\0\0short"
        self.assertEqual(parse_id3_tags(data), {})

    def test_parses_apic_image_and_ignores_broken_header(self):
        image = b"\x89PNG\r\nfixture"
        apic = b"\x03image/png\0\x03\0" + image
        self.assertEqual(parse_id3_cover(_frame("APIC", apic)), ("image/png", image))
        self.assertEqual(parse_id3_cover(_frame("APIC", b"\x03image/png")), (None, None))

    def test_cover_type_comes_from_the_picture_not_the_declaration(self):
        jpeg = b"\xff\xd8\xff\xe0cover"
        apic = b"\x03text/html\0\x03\0" + jpeg
        self.assertEqual(parse_id3_cover(_frame("APIC", apic)), ("image/jpeg", jpeg))

    def test_cover_declaration_cannot_smuggle_a_response_header(self):
        injected = b"\x03image/png\r\nSet-Cookie: a=b\0\x03\0" + b"not-an-image"
        self.assertEqual(parse_id3_cover(_frame("APIC", injected)), (None, None))

    def test_unusable_cover_frame_falls_through_to_the_next_picture(self):
        html = b"<script>alert(document.domain)</script>"
        jpeg = b"\xff\xd8\xff\xe0cover"
        data = (_frame("APIC", b"\x03text/html\0\x03\0" + html)
                + _frame("APIC", b"\x03image/jpeg\0\x03\0" + jpeg))
        self.assertEqual(parse_id3_cover(data), ("image/jpeg", jpeg))

    def test_scriptable_picture_is_rejected_even_when_labelled_raster(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>'
        apic = b"\x03image/jpeg\0\x03\0" + svg
        self.assertEqual(parse_id3_cover(_frame("APIC", apic)), (None, None))

    def test_tag_level_unsynchronisation_is_removed_before_frames_are_read(self):
        # A picture is full of 0xFF, so a tagger that sets the tag-level
        # unsynchronisation flag stuffs a 0x00 after every marker.  Ignoring
        # that byte used to lose every frame behind the picture and return the
        # stuffed bytes as if they were the image.
        jpeg = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"J" * 40 + bytes([0xFF, 0xD9])
        frames = (_frame("APIC", b"\x03image/jpeg\0\x03\0" + jpeg)
                  + _frame("TALB", b"\x03Chopin"))
        stuffed = frames.replace(b"\xff", b"\xff\x00")
        self.assertNotEqual(stuffed, frames)
        self.assertEqual([fid for fid, _ in iter_id3_frames(stuffed, 3, 0x80)], ["APIC", "TALB"])
        self.assertEqual(parse_id3_tags(stuffed, 3, 0x80), {"album": "Chopin"})
        self.assertEqual(parse_id3_cover(stuffed, 3, 0x80), ("image/jpeg", jpeg))

    def test_frame_bytes_are_only_de_stuffed_when_the_flag_says_so(self):
        # The flag byte, not the content, decides.  A clean tag that happens to
        # contain FF 00 must survive untouched.
        raw = b"\x03a\xff\x00b"
        frame = _frame("TALB", raw)
        self.assertEqual(id3_frame_region(frame, 3, 0x00), frame)
        self.assertEqual(id3_frame_region(frame, 3, 0x80), frame.replace(b"\xff\x00", b"\xff"))

    def test_v24_frame_level_unsynchronisation_is_undone(self):
        # Stuffing writes FF 00 wherever the body itself holds FF, so the text
        # only exists once those pad bytes come back out.  UTF-16 is used here
        # because it is the encoding whose own bytes can legitimately contain
        # FF 00, which is exactly what an ignored flag would corrupt.
        body = b"\x01\xff\xfea\x00\xff\x00b\x00"
        stuffed = body.replace(b"\xff", b"\xff\x00")
        frame = _frame("TALB", stuffed, major=4, flags=0x0002)
        self.assertEqual(list(iter_id3_frames(frame, major=4)), [("TALB", body)])
        self.assertEqual(parse_id3_tags(frame, major=4), {"album": "a\xffb"})

    def test_v24_data_length_indicator_precedes_the_body(self):
        # The indicator is four extra bytes in front of the text, so a reader
        # that ignores it returns the length prefix as part of the title.
        body = b"\x03Song"
        frame = _frame(
            "TIT2", len(body).to_bytes(4, "big") + body, major=4, flags=0x0001
        )
        self.assertEqual(
            list(iter_id3_frames(frame, major=4)), [("TIT2", body)]
        )
        self.assertEqual(parse_id3_tags(frame, major=4), {"title": "Song"})

    def test_v24_indicator_and_unsync_are_both_undone(self):
        # A frame can declare both transforms at once.  The indicator belongs to
        # the frame header, so it comes off before the body behind it is
        # expanded; expanding first would spend four of the indicator bytes and
        # then swallow four real text bytes to make up the difference.
        body = b"\x01\xff\xfea\x00\xff\x00b\x00"
        stuffed = body.replace(b"\xff", b"\xff\x00")
        frame = _frame(
            "TALB",
            len(stuffed).to_bytes(4, "big") + stuffed,
            major=4,
            flags=0x0003,
        )
        self.assertEqual(list(iter_id3_frames(frame, major=4)), [("TALB", body)])
        self.assertEqual(parse_id3_tags(frame, major=4), {"album": "a\xffb"})

    def test_truncated_indicator_refuses_the_frame_without_stopping_the_walk(self):
        # An indicator with nothing behind it, and one whose own four bytes are
        # the whole frame, are both malformed; a one-byte body behind a real
        # indicator is not.  Only those four header bytes may come off, and the
        # walk has to keep running through either outcome.
        good = _frame("TALB", b"\x03Album", major=4)
        for payload in (b"\x00\x00", b"\x00\x00\x00\x00"):
            with self.subTest(payload=payload):
                bad = _frame("TIT2", payload, major=4, flags=0x0001)
                self.assertEqual(
                    list(iter_id3_frames(bad + good, major=4)),
                    [("TALB", b"\x03Album")],
                )
        bare = _frame("TIT2", b"\x00\x00\x00\x01" + b"\x03", major=4, flags=0x0001)
        self.assertEqual(
            list(iter_id3_frames(bare + good, major=4)),
            [("TIT2", b"\x03"), ("TALB", b"\x03Album")],
        )

    def test_unundoable_frame_flags_skip_the_frame_and_not_the_tag(self):
        # v2.4 compression is 0x0008 and encryption 0x0004; v2.3 uses 0x0080
        # and 0x0040. Grouping and the reserved v2.4 bit are equally unreadable.
        opaque = b"z\x9c\xab\xe6R\x80\x00"
        cases = (
            (4, 0x0008), (4, 0x0004), (4, 0x0040), (4, 0x0010),
            (3, 0x0080), (3, 0x0040), (3, 0x0020),
        )
        for major, flag in cases:
            with self.subTest(major=major, flag=flag):
                data = _frame("TIT2", opaque, major=major, flags=flag)
                data += _frame("TALB", b"\x03Album", major=major)
                self.assertEqual(
                    list(iter_id3_frames(data, major=major)),
                    [("TALB", b"\x03Album")],
                )
                self.assertEqual(
                    parse_id3_tags(data, major=major), {"album": "Album"}
                )

    def test_v23_does_not_borrow_the_v24_undoable_bits(self):
        # 0x0002/0x0001 are v2.4 format bits; the v2.3 format byte leaves them
        # undefined, so reading the body as text there would be a guess.
        frame = _frame("TALB", b"\x03a\xff\x00b", major=3, flags=0x0002)
        self.assertEqual(list(iter_id3_frames(frame, major=3)), [])

    def test_a_later_version_is_not_read_with_the_v24_rule_book(self):
        # Only v2.2 is turned away at the door, so a v2.5 tag reaches this code.
        # Nothing promises the v2.4 bit meanings there, so a declared format bit
        # is refused rather than undone using the v2.4 rule book.
        frame = _frame("TALB", b"\x03a\xff\x00b", major=5, flags=0x0002)
        self.assertEqual(list(iter_id3_frames(frame, major=5)), [])
        plain = _frame("TALB", b"\x03Album", major=5)
        self.assertEqual(
            list(iter_id3_frames(plain, major=5)), [("TALB", b"\x03Album")]
        )

    def test_indicator_bytes_are_header_bytes_even_when_they_hold_ff_00(self):
        # The indicator is four header bytes whose value stays advisory, so the
        # frame size alone bounds the body.  Expanding the unsynchronisation
        # first would shrink this header to two bytes and then swallow two real
        # text bytes to make up the four it promised to remove.
        frame = _frame("TIT2", b"\xff\x00\x00\x01\x03", major=4, flags=0x0003)
        self.assertEqual(
            list(iter_id3_frames(frame, major=4)), [("TIT2", b"\x03")]
        )

    def test_frame_status_bits_never_cost_a_readable_frame(self):
        # The first flag byte is preservation advice and read-only/discard
        # guidance, not a claim about the bytes, so it must never lose a frame.
        cases = (
            (3, 0x8000), (3, 0x4000), (3, 0x2000),
            (4, 0x8000), (4, 0x4000), (4, 0x2000), (4, 0x1000),
        )
        for major, flag in cases:
            with self.subTest(major=major, flag=flag):
                frame = _frame("TALB", b"\x03Album", major=major, flags=flag)
                self.assertEqual(
                    list(iter_id3_frames(frame, major=major)),
                    [("TALB", b"\x03Album")],
                )

    def test_compressed_frame_cannot_reach_the_title_field(self):
        # This is the mis-read the item described: zlib bytes decoded as latin1
        # produced a plausible-looking non-empty title for the library.
        body = zlib.compress(b"\x03Never Gonna Give You Up")
        frame = _frame("TIT2", body, major=3, flags=0x0080)
        self.assertEqual(parse_id3_tags(frame, major=3), {})
        self.assertNotIn("Never", parse_id3_tags(frame + _frame("TALB", b"\x03Album"), 3).get("title", ""))

    def test_extended_headers_are_skipped_for_both_versions(self):
        frames = _frame("TALB", b"\x03Chopin") + _frame("TCON", b"\x03Classical")
        # v2.3: plain length that excludes its own size field (flags + padding).
        v23 = (6).to_bytes(4, "big") + b"\x00\x08\x00\x00\x00\x00" + frames
        self.assertEqual(parse_id3_tags(v23, 3, 0x40), {"album": "Chopin", "genre": "Classical"})
        # v2.4: synchsafe length that includes its own size field.
        v24 = (10).to_bytes(4, "big") + b"\x06" + b"\x00" * 5 + _frame("TALB", b"\x03Chopin", major=4)
        self.assertEqual(parse_id3_tags(v24, major=4, flags=0x40), {"album": "Chopin"})
        # A length that only reads correctly as synchsafe: 128 is stored as
        # 00 00 01 00, which a plain 32-bit read turns into 256.
        wide = _syncsafe(128) + b"\x06" + b"\x00" * 123 + _frame("TALB", b"\x03Chopin", major=4)
        self.assertEqual(len(wide) - len(_frame("TALB", b"\x03Chopin", major=4)), 128)
        self.assertEqual(parse_id3_tags(wide, major=4, flags=0x40), {"album": "Chopin"})
        # Without the flag byte the same payload is unreadable, which is what
        # makes passing header[5] through the readers the fix.
        self.assertEqual(parse_id3_tags(v23, 3), {})

    def test_bogus_extended_header_length_refuses_the_payload(self):
        frames = _frame("TALB", b"\x03Chopin")
        too_long = (9999).to_bytes(4, "big") + frames
        too_short = (1).to_bytes(4, "big") + frames
        missing = b"\x00\x00"
        for payload in (too_long, too_short, missing):
            self.assertEqual(id3_frame_region(payload, 3, 0x40), b"")
            self.assertEqual(parse_id3_tags(payload, 3, 0x40), {})
        # v2.4 counts its own size field, so a declared six bytes below the
        # minimum is refused rather than trusted to land on a frame edge.
        v24_short = (2).to_bytes(4, "big") + b"12" + frames
        self.assertEqual(id3_frame_region(v24_short, 4, 0x40), b"")
        self.assertEqual(parse_id3_tags(v24_short, 4, 0x40), {})

    def test_id3_tag_is_readable_gates_the_unsupported_v22_layout(self):
        self.assertFalse(id3_tag_is_readable(b"ID3\x02\x00\x00\x00\x00\x00\x00"))
        self.assertTrue(id3_tag_is_readable(b"ID3\x03\x00\x00\x00\x00\x00\x00"))
        self.assertTrue(id3_tag_is_readable(b"ID3\x04\x00\x00\x00\x00\x00\x00"))
        self.assertFalse(id3_tag_is_readable(b"ID3"))
        self.assertFalse(id3_tag_is_readable(b"ID3\x03\x00\x00"))
        self.assertFalse(id3_tag_is_readable(None))
        self.assertEqual(list(iter_id3_frames(_frame("TALB", b"\x03x"), major=2)), [])

    def test_apic_frame_without_a_mime_terminator_falls_through(self):
        # The docstring promises the scan continues; a return here used to lose
        # the usable cover that followed a tagger-broken frame.
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
        broken = _frame("APIC", b"\x03image/png-no-terminator")
        usable = _frame("APIC", b"\x03image/png\0\x03\0" + png)
        self.assertEqual(parse_id3_cover(broken + usable), ("image/png", png))
    def test_rejects_non_binary_text_payload(self):
        self.assertEqual(decode_id3_text("not-bytes"), "")

    def test_decodes_fixed_width_id3v1_fields_with_legacy_fallbacks(self):
        self.assertEqual(decode_id3v1_field("not-bytes"), "")
        self.assertEqual(decode_id3v1_field("标题".encode("gb18030") + b"\0"), "标题")


if __name__ == "__main__":
    unittest.main()

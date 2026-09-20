import os
import io
import sys
import tempfile
import unittest
import wave
from unittest.mock import patch

sys.path.insert(0, "app/server")

from dlna.media_server import upnp_resource_mime
from library import MAX_COVER_FILE_BYTES, MAX_PROBE_OUTPUT_BYTES, parse_cue_tracks, read_audio_info, read_cover, read_cover_for_item, read_id3, read_id3_cover, read_m4a_cover, read_native_audio_info, scan_library
from cover_readers import read_ape_cover as read_ape_cover_module, read_flac_cover as read_flac_cover_module
from id3_container import MAX_ID3_PAYLOAD_BYTES, read_id3_header_at
from id3_parser import parse_id3_cover
from server import parse_single_byte_range
from media_range import parse_single_byte_range as parse_range_module
from media_naming import safe_filename


def dff_chunk(chunk_id, payload):
    body = chunk_id + len(payload).to_bytes(8, "big") + payload
    return body + (b"\x00" if len(payload) % 2 else b"")


def write_dff(path, sample_rate=2822400, channels=2, seconds=1):
    properties = b"SND " + dff_chunk(b"FS  ", sample_rate.to_bytes(4, "big")) + dff_chunk(b"CHNL", channels.to_bytes(2, "big") + b"SLFTSRGT")
    samples = b"\xaa" * int(sample_rate * channels * seconds / 8)
    form = b"DSD " + dff_chunk(b"PROP", properties) + dff_chunk(b"DSD ", samples)
    with open(path, "wb") as handle:
        handle.write(b"FRM8" + len(form).to_bytes(8, "big") + form)


def flac_picture_block(mime, body, last, mime_len=None, description_len=None, image_len=None):
    """One METADATA_BLOCK_PICTURE, laid out per RFC 9639 section 8.8.

    The field order is: u(32) picture type, u(32) media type length, media type,
    u(32) description length, description, u(32) width, height, depth, colours-used,
    u(32) image length, image. The three `*_len` overrides exist to write a block whose
    declared lengths lie about its payload, which is a tagger bug this reader has to
    survive without giving up on the rest of the file.
    """
    picture = (3).to_bytes(4, "big")
    picture += (len(mime) if mime_len is None else mime_len).to_bytes(4, "big") + mime
    picture += (0 if description_len is None else description_len).to_bytes(4, "big")
    picture += (0).to_bytes(4, "big") * 4
    picture += (len(body) if image_len is None else image_len).to_bytes(4, "big") + body
    # Bit 7 flags the final block; the low seven bits are the block type.
    return bytes([0x86 if last else 0x06]) + len(picture).to_bytes(3, "big") + picture


def write_flac_picture(path, mime, body, **corruption):
    with open(path, "wb") as handle:
        handle.write(b"fLaC")
        handle.write(flac_picture_block(mime, body, last=True, **corruption))


class MediaFormatTests(unittest.TestCase):
    def test_cue_disappearing_after_read_does_not_abort_scan(self):
        import library

        with tempfile.TemporaryDirectory() as root:
            cue_path = os.path.join(root, "album.cue")
            with open(cue_path, "w", encoding="utf-8") as handle:
                handle.write('FILE "album.flac" WAVE\n  TRACK 01 AUDIO\n')

            real_stat = os.stat

            def stat_without_cue(path):
                if path == cue_path:
                    raise FileNotFoundError(cue_path)
                return real_stat(path)

            with patch.object(library, "read_cue_lines", return_value=["FILE \\\"album.flac\\\" WAVE", "TRACK 01 AUDIO"]), \
                 patch.object(library.os, "stat", side_effect=stat_without_cue):
                self.assertEqual(parse_cue_tracks(cue_path, root, config={}), [])

    def test_cue_segment_ends_keep_the_three_boundary_states(self):
        import library

        # The scanner has to carry the parser's distinction all the way into the
        # value it stores, so one sheet is walked end to end: TRACK 01 stops where
        # TRACK 02 starts, TRACK 02 is followed only by a track that starts earlier
        # and so has no stated end, and TRACK 03 is the file's last entry and stops
        # where the file does.  Only that last case may borrow the probed duration.
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, "disc.flac"), "wb") as handle:
                handle.write(b"fLaC")
            cue_path = os.path.join(root, "album.cue")
            with open(cue_path, "w", encoding="utf-8") as handle:
                handle.write(
                    'FILE "disc.flac" FLAC\n'
                    "  TRACK 01 AUDIO\n    INDEX 01 00:00:00\n"
                    "  TRACK 02 AUDIO\n    INDEX 01 04:00:00\n"
                    "  TRACK 03 AUDIO\n    INDEX 01 02:00:00\n"
                )
            with patch.object(library, "read_probe_metadata",
                              return_value=({}, {"duration": 300.0})):
                items = parse_cue_tracks(cue_path, root, config={})

        self.assertEqual([item["cue_track"] for item in items], [True, True, True])
        self.assertEqual([item["cue_start"] for item in items], [0.0, 240.0, 120.0])
        self.assertEqual([item["cue_end"] for item in items], [240.0, 0.0, 300.0])
        self.assertEqual([item["duration"] for item in items], [240.0, 0.0, 180.0])

    def test_library_uses_isolated_container_cover_readers(self):

        import library

        self.assertIs(library.read_ape_cover, read_ape_cover_module)
        self.assertIs(library.read_flac_cover, read_flac_cover_module)

    def test_id3_container_rejects_oversized_declared_payload(self):
        declared = MAX_ID3_PAYLOAD_BYTES + 1
        syncsafe = bytes((declared >> shift) & 0x7F for shift in (21, 14, 7, 0))
        header = b"ID3" + bytes([4, 0, 0]) + syncsafe
        self.assertEqual(read_id3_header_at(io.BytesIO(header), 0), (None, b""))

    def test_id3_container_rejects_truncated_header(self):
        self.assertEqual(read_id3_header_at(io.BytesIO(b"ID3"), 0), (None, b""))

    def test_id3_container_rejects_truncated_declared_payload(self):
        header = b"ID3" + bytes([4, 0, 0, 0, 0, 0, 4])
        self.assertEqual(read_id3_header_at(io.BytesIO(header + b"x"), 0), (None, b""))

    def test_id3_container_rejects_invalid_syncsafe_length_and_offset(self):
        header = b"ID3" + bytes([4, 0, 0, 0x80, 0, 0, 0])
        self.assertEqual(read_id3_header_at(io.BytesIO(header), 0), (None, b""))
        self.assertEqual(read_id3_header_at(io.BytesIO(header), -1), (None, b""))

    def test_id3_cover_rejects_image_larger_than_shared_cover_budget(self):
        frame = b"\x00image/jpeg\x00\x03\x00\xff\xd8\xff" + b"x" * MAX_COVER_FILE_BYTES
        tag = b"APIC" + len(frame).to_bytes(4, "big") + b"\x00\x00" + frame
        self.assertEqual(parse_id3_cover(tag, 3), (None, None))

    @staticmethod
    def _write_id3_file(path, payload, major=3, flags=0, trailing=b""):
        size = len(payload)
        header = b"ID3" + bytes([major, 0, flags]) + bytes(((size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F))
        with open(path, "wb") as handle:
            handle.write(header + payload + trailing)

    def test_read_id3_follows_the_tag_flag_byte_end_to_end(self):
        # The flag byte is the only place an extended header and tag-level
        # unsynchronisation are declared.  A file like this reads as an untitled
        # track with no cover until the readers honour it.
        jpeg = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"J" * 40 + bytes([0xFF, 0xD9])
        talb = b"\x03Chopin"
        apic = b"\x03image/jpeg\x00\x03\x00" + jpeg
        frames = (b"TALB" + len(talb).to_bytes(4, "big") + b"\x00\x00" + talb
                  + b"APIC" + len(apic).to_bytes(4, "big") + b"\x00\x00" + apic)
        stuffed = frames.replace(b"\xff", b"\xff\x00")
        payload = (6).to_bytes(4, "big") + b"\x00\x08\x00\x00\x00\x00" + stuffed
        self.assertNotEqual(stuffed, frames)
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "flagged.mp3")
            self._write_id3_file(path, payload, flags=0xC0, trailing=b"\xff\xfb\x90\x00")
            self.assertEqual(read_id3(path), {"album": "Chopin"})
            self.assertEqual(read_id3_cover(path), ("image/jpeg", jpeg))
            # A reader that ignores header[5] still gets nothing, which is what
            # keeps this assertion pair honest.
            self.assertEqual(parse_id3_cover(payload, 3), (None, None))

    def test_unsupported_v22_tag_falls_back_to_the_id3v1_block(self):
        v1 = (b"TAG" + b"Song".ljust(30, b"\x00") + b"Artist".ljust(30, b"\x00")
              + b"Album".ljust(30, b"\x00") + b"1998".ljust(4, b"\x00")
              + b"\x00" * 30 + bytes([0xFF]))
        self.assertEqual(len(v1), 128)
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "legacy.mp3")
            # v2.2 frames have three-byte ids and three-byte sizes; reading that
            # as v2.3 produced no tags and hid the ID3v1 record at the end.
            self._write_id3_file(path, b"TT2" + b"\x00\x00\x05" + b"\x03nope", major=2, trailing=b"\xff\xfb\x90\x00" + v1)
            self.assertEqual(read_id3(path), {"title": "Song", "artist": "Artist", "album": "Album"})
            self.assertEqual(read_id3_cover(path), (None, None))
    def test_mp4_cover_reader_bounds_nested_atom_depth(self):
        payload = b""
        for _ in range(40):
            payload = (8 + len(payload)).to_bytes(4, "big") + b"moov" + payload
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "deep.m4a")
            with open(path, "wb") as handle:
                handle.write(payload)
            self.assertEqual(read_cover(path), (None, None))

    def test_mp4_cover_reader_rejects_oversized_covr_data_atom(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "large-covr.m4a")
            payload = b"\x00" * 8 + b"\xff\xd8\xff" + b"x" * MAX_COVER_FILE_BYTES
            atom = (8 + len(payload)).to_bytes(4, "big") + b"data" + payload
            with open(path, "wb") as handle:
                handle.write((8 + len(atom)).to_bytes(4, "big") + b"covr" + atom)
            self.assertEqual(read_cover(path), (None, None))

    def test_ffmpeg_cover_extraction_passes_output_size_limit(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "cover.m4a")
            with open(path, "wb") as handle:
                handle.write(b"not-an-mp4")

            captured = []

            def fake_run(command, **_kwargs):
                captured.extend(command)
                with open(command[-1], "wb") as handle:
                    handle.write(b"\xff\xd8\xff\xd9")

            with patch("library.find_ffmpeg", return_value="ffmpeg"), patch("library.subprocess.run", side_effect=fake_run):
                self.assertEqual(read_m4a_cover(path), ("image/jpeg", b"\xff\xd8\xff\xd9"))
            self.assertEqual(captured[captured.index("-fs") + 1], str(MAX_COVER_FILE_BYTES))

    def test_ffmpeg_cover_extraction_rechecks_output_bound_after_read(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "cover.m4a")
            with open(path, "wb") as handle:
                handle.write(b"not-an-mp4")

            def fake_run(command, **_kwargs):
                with open(command[-1], "wb") as handle:
                    handle.write(b"x" * (MAX_COVER_FILE_BYTES + 1))

            with patch("library.find_ffmpeg", return_value="ffmpeg"), patch("library.subprocess.run", side_effect=fake_run):
                self.assertEqual(read_m4a_cover(path), (None, None))

    def test_ffmpeg_cover_extraction_rejects_nonzero_real_process_result(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "cover.m4a")
            with open(path, "wb") as handle:
                handle.write(b"not-an-mp4")

            class Process:
                returncode = 1
                pid = 123
                def wait(self, timeout=None):
                    return self.returncode
                def poll(self):
                    return self.returncode

            marker = lambda *_args, **_kwargs: None
            with patch("library.find_ffmpeg", return_value="ffmpeg"), \
                 patch("library.subprocess.run", marker), \
                 patch("ffmpeg_cover.subprocess.Popen", return_value=Process()):
                self.assertEqual(read_m4a_cover(path), (None, None))

    def test_ffmpeg_cover_extraction_stops_when_output_grows_past_limit(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "cover.m4a")
            with open(path, "wb") as handle:
                handle.write(b"not-an-mp4")

            class Process:
                returncode = 0
                pid = 456
                def __init__(self, target):
                    self.target = target
                    self.calls = 0
                def poll(self):
                    self.calls += 1
                    if self.calls == 1:
                        with open(self.target, "wb") as handle:
                            handle.write(b"x" * (MAX_COVER_FILE_BYTES + 1))
                        return None
                    return 0
                def wait(self, timeout=None):
                    return self.returncode
                def kill(self):
                    self.returncode = -9

            process = None
            def make_process(command, **_kwargs):
                nonlocal process
                process = Process(command[-1])
                return process

            with patch("library.find_ffmpeg", return_value="ffmpeg"), \
                 patch("library.subprocess.run", lambda *_args, **_kwargs: None), \
                 patch("ffmpeg_cover.subprocess.Popen", side_effect=make_process), \
                 patch("ffmpeg_cover.os.killpg", create=True) as killpg:
                self.assertEqual(read_m4a_cover(path), (None, None))
            if os.name != "nt":
                killpg.assert_called_once_with(456, ffmpeg_cover.signal.SIGKILL)

    def test_audio_info_probe_rejects_oversized_json_output(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "track.flac")
            with open(path, "wb") as handle:
                handle.write(b"fLaC")
            result = type("Result", (), {"stdout": b"{" + b"x" * MAX_PROBE_OUTPUT_BYTES + b"}"})()
            with patch("library.find_ffprobe", return_value="ffprobe"), patch("library.subprocess.run", return_value=result):
                self.assertEqual(read_audio_info(path), {})

    def test_byte_range_parser_is_exposed_as_a_pure_module(self):
        self.assertIs(parse_single_byte_range, parse_range_module)

    def test_safe_filename_is_bounded_and_portable(self):
        self.assertEqual(safe_filename('a:/b\\c*?'), "a_b_c_")
        self.assertEqual(len(safe_filename("x" * 200)), 120)
        self.assertEqual(safe_filename("   "), "track")

    def test_safe_filename_does_not_stringify_arbitrary_values(self):
        class ExplodingString:
            def __str__(self):
                raise AssertionError("must not stringify")

        self.assertEqual(safe_filename(ExplodingString()), "track")
    def test_ape_files_are_indexed_as_audio_library_items(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "fixture.ape")
            with open(path, "wb") as handle:
                handle.write(b"MAC ")

            items, _signature = scan_library(root, config={})

            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["format"], "APE")
            self.assertEqual(items[0]["mime"], "audio/ape")
    def test_wav_fixture_has_duration_seek_shape_and_sidecar_cover(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "fixture.wav")
            with wave.open(path, "wb") as handle:
                handle.setnchannels(2)
                handle.setsampwidth(2)
                handle.setframerate(48000)
                handle.writeframes(b"\x00\x00\x00\x00" * 12000)
            with open(os.path.join(root, "cover.jpg"), "wb") as handle:
                handle.write(b"\xff\xd8\xff\xd9")

            info = read_native_audio_info(path)
            self.assertEqual(info["sample_rate"], 48000)
            self.assertEqual(info["bit_depth"], 16)
            self.assertAlmostEqual(info["duration"], 0.25, places=3)
            self.assertEqual(upnp_resource_mime({"path": path, "mime": "audio/wav"}), "audio/wav")
            mime, cover = read_cover_for_item({"path": path})
            self.assertEqual(mime, "image/jpeg")
            self.assertEqual(cover, b"\xff\xd8\xff\xd9")

    def test_uncompressed_dff_fixture_preserves_native_dsd_properties(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "fixture.dff")
            write_dff(path)

            info = read_native_audio_info(path)
            self.assertEqual(info["sample_rate"], 2822400)
            self.assertEqual(info["bit_depth"], 1)
            self.assertEqual(info["bit_rate"], 5644800)
            self.assertAlmostEqual(info["duration"], 1.0, places=3)
            self.assertEqual(upnp_resource_mime({"path": path, "is_dsd": True}), "audio/x-dff")
        self.assertEqual(read_cover_for_item({"path": path}), (None, None))

    def test_flac_cover_reader_skips_oversized_metadata_blocks(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "oversized.flac")
            block_size = 8 * 1024 * 1024 + 1
            with open(path, "wb") as handle:
                handle.write(b"fLaC")
                handle.write(bytes([0x86]) + block_size.to_bytes(3, "big"))
                handle.seek(block_size, os.SEEK_CUR)
            self.assertEqual(read_cover(path), (None, None))

    def test_flac_cover_reader_rejects_truncated_metadata_block(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "truncated.flac")
            with open(path, "wb") as handle:
                handle.write(b"fLaC")
                handle.write(bytes([6]) + (32).to_bytes(3, "big"))
                handle.write(b"x")
            self.assertEqual(read_cover(path), (None, None))

    def test_flac_cover_type_comes_from_the_picture_not_the_declaration(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "mislabelled.flac")
            jpeg = b"\xff\xd8\xff\xe0cover"
            write_flac_picture(path, b"text/html", jpeg)
            self.assertEqual(read_cover(path), ("image/jpeg", jpeg))

    def test_flac_cover_reader_rejects_a_scriptable_picture(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>'
        for declared in (b"image/svg+xml", b"image/jpeg", b"text/html"):
            with self.subTest(declared=declared):
                with tempfile.TemporaryDirectory() as root:
                    path = os.path.join(root, "svg.flac")
                    write_flac_picture(path, declared, svg)
                    self.assertEqual(read_cover(path), (None, None))

    def test_flac_cover_reader_continues_past_an_unusable_picture(self):
        html = b"<script>alert(document.domain)</script>"
        jpeg = b"\xff\xd8\xff\xe0cover"
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "second-picture.flac")
            with open(path, "wb") as handle:
                handle.write(b"fLaC")
                handle.write(flac_picture_block(b"text/html", html, last=False))
                handle.write(flac_picture_block(b"UNKNOWN", jpeg, last=True))
            self.assertEqual(read_cover(path), ("image/jpeg", jpeg))

    def test_flac_cover_reader_survives_picture_fields_that_lie_about_their_size(self):
        # The test above covers a well-formed block holding unusable bytes. This one covers
        # the other failure mode: a block whose declared lengths are bigger than what the
        # block actually holds. Those four checks used to `return None, None` out of
        # `read_flac_cover` itself, so a single lying field hid every picture block after
        # it, and the function docstring several lines above already claimed the opposite
        # (TODO.md:92). The declared *block* length stays truthful, so the scan can still
        # walk to the next block; that is the whole point of skipping instead of aborting.
        jpeg = b"\xff\xd8\xff\xe0cover"
        lies = (
            ("media type length", {"mime_len": 10 ** 6}),
            ("description length", {"description_len": 10 ** 6}),
            ("image length", {"image_len": 10 ** 6}),
            ("media type length past the end", {"mime_len": 4_000_000_000}),
        )
        for label, corruption in lies:
            with self.subTest(field=label):
                with tempfile.TemporaryDirectory() as root:
                    path = os.path.join(root, "lying-picture.flac")
                    with open(path, "wb") as handle:
                        handle.write(b"fLaC")
                        handle.write(flac_picture_block(b"image/jpeg", jpeg, last=False, **corruption))
                        handle.write(flac_picture_block(b"image/jpeg", jpeg, last=True))
                    self.assertEqual(read_cover(path), ("image/jpeg", jpeg), label)
        # Nothing good after it either: refused, not crashed, and no garbage returned.
        for label, corruption in lies:
            with self.subTest(solo=label):
                with tempfile.TemporaryDirectory() as root:
                    path = os.path.join(root, "solo-lying.flac")
                    write_flac_picture(path, b"image/jpeg", jpeg, **corruption)
                    self.assertEqual(read_cover(path), (None, None), label)
        # The shared per-image budget is enforced here too, not only in the ID3 path. It is
        # patched down rather than grown into a multi-megabyte fixture: a PICTURE block
        # declaring more than MAX_COVER_BLOCK_BYTES is seeked past before it gets here.
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "over-budget.flac")
            write_flac_picture(path, b"image/jpeg", jpeg)
            with patch("cover_readers.MAX_COVER_FILE_BYTES", len(jpeg) - 1):
                self.assertEqual(read_cover(path), (None, None))
            with patch("cover_readers.MAX_COVER_FILE_BYTES", len(jpeg)):
                self.assertEqual(read_cover(path), ("image/jpeg", jpeg))

    def test_ape_cover_reader_does_not_load_oversized_tags(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "oversized.ape")
            footer = bytearray(32)
            footer[:8] = b"APETAGEX"
            footer[12:16] = (16 * 1024 * 1024 + 1).to_bytes(4, "little")
            footer[16:20] = (1).to_bytes(4, "little")
            with open(path, "wb") as handle:
                handle.write(b"MAC ")
                handle.write(footer)
            self.assertEqual(read_cover(path), (None, None))

    def test_ape_cover_reader_rejects_truncated_declared_tag(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "truncated.ape")
            footer = bytearray(32)
            footer[:8] = b"APETAGEX"
            footer[12:16] = (64).to_bytes(4, "little")
            footer[16:20] = (0).to_bytes(4, "little")
            with open(path, "wb") as handle:
                handle.write(b"MAC ")
                handle.write(footer)
            self.assertEqual(read_cover(path), (None, None))

    def test_single_byte_ranges_cover_seek_and_suffix_requests(self):
        self.assertEqual(parse_single_byte_range(1000, ""), (200, 0, 999))
        self.assertEqual(parse_single_byte_range(1000, "bytes=100-199"), (206, 100, 199))
        self.assertEqual(parse_single_byte_range(1000, "bytes=900-"), (206, 900, 999))
        self.assertEqual(parse_single_byte_range(1000, "bytes=-128"), (206, 872, 999))
        with self.assertRaises(ValueError):
            parse_single_byte_range(1000, "bytes=1000-")
        with self.assertRaises(ValueError):
            parse_single_byte_range(1000, "bytes=0-1,4-5")

    def test_range_parser_does_not_coerce_untrusted_objects(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("range parser must not stringify objects")

            def __int__(self):
                raise AssertionError("range parser must not coerce objects")

        with self.assertRaises(ValueError):
            parse_single_byte_range(Explosive(), "")
        with self.assertRaises(ValueError):
            parse_single_byte_range(1000, Explosive())


if __name__ == "__main__":
    unittest.main()

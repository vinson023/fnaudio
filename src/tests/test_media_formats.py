import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, "app/server")

from dlna.media_server import upnp_resource_mime
from library import read_cover_for_item, read_native_audio_info, scan_library
from server import parse_single_byte_range


def dff_chunk(chunk_id, payload):
    body = chunk_id + len(payload).to_bytes(8, "big") + payload
    return body + (b"\x00" if len(payload) % 2 else b"")


def write_dff(path, sample_rate=2822400, channels=2, seconds=1):
    properties = b"SND " + dff_chunk(b"FS  ", sample_rate.to_bytes(4, "big")) + dff_chunk(b"CHNL", channels.to_bytes(2, "big") + b"SLFTSRGT")
    samples = b"\xaa" * int(sample_rate * channels * seconds / 8)
    form = b"DSD " + dff_chunk(b"PROP", properties) + dff_chunk(b"DSD ", samples)
    with open(path, "wb") as handle:
        handle.write(b"FRM8" + len(form).to_bytes(8, "big") + form)


class MediaFormatTests(unittest.TestCase):
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

    def test_single_byte_ranges_cover_seek_and_suffix_requests(self):
        self.assertEqual(parse_single_byte_range(1000, ""), (200, 0, 999))
        self.assertEqual(parse_single_byte_range(1000, "bytes=100-199"), (206, 100, 199))
        self.assertEqual(parse_single_byte_range(1000, "bytes=900-"), (206, 900, 999))
        self.assertEqual(parse_single_byte_range(1000, "bytes=-128"), (206, 872, 999))
        with self.assertRaises(ValueError):
            parse_single_byte_range(1000, "bytes=1000-")
        with self.assertRaises(ValueError):
            parse_single_byte_range(1000, "bytes=0-1,4-5")


if __name__ == "__main__":
    unittest.main()

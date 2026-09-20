import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, "app/server")

from native_audio_info import read_native_audio_info


class NativeAudioInfoTests(unittest.TestCase):
    def test_wav_is_read_without_external_probe(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "sample.wav")
            with wave.open(path, "wb") as handle:
                handle.setnchannels(2)
                handle.setsampwidth(2)
                handle.setframerate(48000)
                handle.writeframes(b"\0" * 48000 * 2 * 2)
            info = read_native_audio_info(path)
        self.assertEqual(info["sample_rate"], 48000)
        self.assertEqual(info["bit_depth"], 16)
        self.assertEqual(info["bit_rate"], 1536000)
        self.assertAlmostEqual(info["duration"], 1.0)

    def test_unknown_or_invalid_container_is_empty(self):
        self.assertEqual(read_native_audio_info("/no/such/file.wav"), {})
        self.assertEqual(read_native_audio_info("/no/such/file.flac"), {})

    def test_untrusted_path_is_rejected_without_string_conversion(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("audio parser must not stringify arbitrary paths")

        self.assertEqual(read_native_audio_info(Explosive()), {})

    def test_truncated_dff_chunk_header_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "broken.dff")
            form = b"DSD " + b"PROP" + b"\x00\x00\x00\x00\x00\x00\x00\x20"
            with open(path, "wb") as handle:
                handle.write(b"FRM8" + len(form).to_bytes(8, "big") + form[:16])
            self.assertEqual(read_native_audio_info(path), {})


if __name__ == "__main__":
    unittest.main()

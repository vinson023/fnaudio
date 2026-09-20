import importlib.util
import ctypes
import pathlib
import sys
import unittest
from unittest import mock


MODULE_PATH = pathlib.Path(__file__).resolve().parent / "unwired" / "alsa_player.py"
SPEC = importlib.util.spec_from_file_location("fnaudio_alsa_player", MODULE_PATH)
alsa_player = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(alsa_player)


class AlsaPlayerTests(unittest.TestCase):
    def assert_rejects(self, args):
        with mock.patch.object(sys, "argv", ["alsa_player.py"] + args), \
                mock.patch.object(alsa_player, "load_alsa") as load_alsa:
            with self.assertRaises(SystemExit) as raised:
                alsa_player.main()
        self.assertEqual(raised.exception.code, 2)
        load_alsa.assert_not_called()

    def test_cli_rejects_oversized_channels_before_loading_alsa(self):
        self.assert_rejects(["--device", "default", "--rate", "44100", "--channels", "33"])

    def test_cli_rejects_invalid_rate_before_loading_alsa(self):
        self.assert_rejects(["--device", "default", "--rate", "0"])

    def test_cli_rejects_oversized_device_before_loading_alsa(self):
        self.assert_rejects(["--device", "x" * (alsa_player.MAX_DEVICE_CHARS + 1), "--rate", "44100"])

    def test_short_alsa_write_continues_at_next_frame(self):
        calls = []

        class FakeAlsa:
            def snd_pcm_writei(self, _pcm, pointer, frames):
                calls.append((ctypes.string_at(pointer, frames * 2), frames))
                return 2 if len(calls) == 1 else frames

            def snd_pcm_prepare(self, _pcm):
                raise AssertionError("prepare must not be needed")

            def snd_strerror(self, _code):
                return b"error"

        data = b"abcd" + b"efgh" + b"ijkl" + b"mnop"
        alsa_player.write_pcm_buffer(FakeAlsa(), object(), data, 2)

        self.assertEqual(calls, [(data, 8), (data[4:], 6)])

    def test_zero_alsa_write_is_rejected_instead_of_looping(self):
        class FakeAlsa:
            def snd_pcm_writei(self, _pcm, _pointer, _frames):
                return 0

            def snd_strerror(self, _code):
                return b"error"

        with self.assertRaisesRegex(RuntimeError, "no progress"):
            alsa_player.write_pcm_buffer(FakeAlsa(), object(), b"abcd", 2)

    def test_transient_alsa_errors_recover_and_finish_the_buffer(self):
        calls = []

        class FakeAlsa:
            def snd_pcm_writei(self, _pcm, _pointer, frames):
                calls.append(frames)
                return alsa_player.EPIPE if len(calls) == 1 else frames

            def snd_pcm_recover(self, _pcm, error, _silent):
                self.recovered = error
                return 0

            def snd_strerror(self, _code):
                return b"error"

        fake = FakeAlsa()
        alsa_player.write_pcm_buffer(fake, object(), b"abcdefgh", 2)

        self.assertEqual(fake.recovered, alsa_player.EPIPE)
        self.assertEqual(calls, [4, 4])

    def test_repeated_transient_alsa_errors_stop_instead_of_spinning(self):
        calls = []

        class FakeAlsa:
            def snd_pcm_writei(self, _pcm, _pointer, _frames):
                calls.append(1)
                return alsa_player.EAGAIN

            def snd_pcm_recover(self, _pcm, _error, _silent):
                return 0

            def snd_strerror(self, _code):
                return b"error"

        with self.assertRaisesRegex(RuntimeError, "write"): 
            alsa_player.write_pcm_buffer(FakeAlsa(), object(), b"abcd", 2)

        self.assertEqual(
            len(calls),
            alsa_player.MAX_ALSA_RECOVERY_ATTEMPTS + 1,
        )

    def test_partial_frames_carry_into_the_next_read(self):
        reads = iter([b"abc", b"defghi", b"jkl", b""])

        chunks = list(alsa_player.iter_pcm_chunks(lambda _size: next(reads), 4, 8))

        self.assertEqual(b"".join(chunks), b"abcdefghijkl")
        for chunk in chunks:
            self.assertEqual(len(chunk) % 4, 0)

    def test_incomplete_frame_at_end_of_stream_is_dropped(self):
        reads = iter([b"abcdef", b""])

        chunks = list(alsa_player.iter_pcm_chunks(lambda _size: next(reads), 4, 8))

        self.assertEqual(chunks, [b"abcd"])

    def test_read_size_smaller_than_one_frame_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least one audio frame"):
            list(alsa_player.iter_pcm_chunks(lambda _size: b"", 4, 2))


if __name__ == "__main__":
    unittest.main()

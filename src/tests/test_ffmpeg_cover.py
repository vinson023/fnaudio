import os
import tempfile
import unittest
from unittest.mock import patch

from ffmpeg_cover import MAX_COVER_FILE_BYTES, extract_cover


class FfmpegCoverTests(unittest.TestCase):
    def test_rejects_untrusted_inputs_without_resolver_call(self):
        called = []
        self.assertEqual(extract_cover(None, {}, lambda _config: called.append(1), lambda *_args, **_kwargs: None), (None, None))
        self.assertEqual(called, [])

    def test_exports_shared_cover_limit(self):
        self.assertEqual(MAX_COVER_FILE_BYTES, 8 * 1024 * 1024)

    def test_temp_file_is_removed_when_initial_descriptor_close_fails(self):
        with tempfile.TemporaryDirectory() as root:
            target = os.path.join(root, "cover.jpg")
            descriptor = os.open(target, os.O_CREAT | os.O_WRONLY)
            real_close = os.close
            close_calls = []

            def fail_once(value):
                close_calls.append(value)
                if len(close_calls) == 1:
                    raise OSError("close failed")
                return real_close(value)

            with patch("ffmpeg_cover.tempfile.mkstemp", return_value=(descriptor, target)), patch(
                "ffmpeg_cover.os.close", side_effect=fail_once
            ):
                self.assertEqual(
                    extract_cover("track.flac", {}, lambda _config: "ffmpeg", lambda *_args, **_kwargs: None),
                    (None, None),
                )
            self.assertEqual(close_calls, [descriptor, descriptor])
            self.assertFalse(os.path.exists(target))


if __name__ == "__main__":
    unittest.main()

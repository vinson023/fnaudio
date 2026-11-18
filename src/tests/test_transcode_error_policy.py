"""R598: a transcode failure has to say which kind of failure it was.

``transcode.py`` used to raise a bare ``RuntimeError`` with ffmpeg's stderr tail for
everything, so the caller could not tell "this file is not decodable" (retrying is
pure waste, and the track deserves the unplayable list) from "the box is out of
disk" or "the worker lane was busy" (retrying is exactly right, and blacklisting
the track would punish the file for the machine).

The page never sees the server's verdict directly -- an ``<audio>`` error carries
neither a status nor a body -- so the classification is recorded as a marker next
to the cache target and read back through ``/api/transcode/status``.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, "app/server")

import transcode
from transcode_error_policy import (
    CODE_BUSY,
    CODE_DECODER_UNAVAILABLE,
    CODE_DISK_FULL,
    CODE_FAILED,
    CODE_FFMPEG_MISSING,
    CODE_TIMEOUT,
    CODE_UNSUPPORTED_FORMAT,
    classify_ffmpeg_detail,
    http_status,
    is_permanent,
    public_message,
)


class ClassifyTests(unittest.TestCase):
    def test_ffmpeg_wording_for_an_undecodable_file(self):
        for detail in (
            "Invalid data found when processing input",
            "Could not find codec parameters for stream 0",
            "Output file does not contain any stream",
            "moov atom not found",
            "Invalid frame size",
        ):
            with self.subTest(detail=detail):
                self.assertEqual(classify_ffmpeg_detail(detail), CODE_UNSUPPORTED_FORMAT)

    def test_ffmpeg_wording_for_a_missing_decoder_blames_the_build(self):
        # R599: these describe the ffmpeg binary, not the bytes.  ``find_ffmpeg``
        # reads ffmpeg from config and PATH, so the reader's fix is "install a
        # fuller build", not "throw the file away" -- and nothing may be recorded
        # against the file, or the marker would outlive the upgrade.
        for detail in (
            "Unsupported codec with id 1234",
            "Unsupported audio codec",
            "Unknown decoder 'foo'",
            "No decoder found for stream 0",
            "Decoder not found",
            "Decoder (codec wmalossless) not found for input stream #0:0",
            "Protocol not found",
        ):
            with self.subTest(detail=detail):
                self.assertEqual(classify_ffmpeg_detail(detail), CODE_DECODER_UNAVAILABLE)

    def test_the_match_is_case_insensitive(self):
        self.assertEqual(
            classify_ffmpeg_detail("INVALID DATA FOUND WHEN PROCESSING INPUT"),
            CODE_UNSUPPORTED_FORMAT,
        )

    def test_a_full_disk_outranks_the_undecodable_wording(self):
        # ffmpeg prints "Output file does not contain any stream" when the write
        # fails, so checking the permanent markers first would blacklist the file
        # because the cache volume was full.
        self.assertEqual(
            classify_ffmpeg_detail("av_interleaved_write_frame(): No space left on device\n"
                                   "Output file does not contain any stream"),
            CODE_DISK_FULL,
        )

    def test_unrecognised_output_is_a_generic_transient_failure(self):
        self.assertEqual(classify_ffmpeg_detail("Conversion failed!"), CODE_FAILED)
        self.assertEqual(classify_ffmpeg_detail(""), CODE_FAILED)
        self.assertEqual(classify_ffmpeg_detail(None), CODE_FAILED)
        self.assertEqual(classify_ffmpeg_detail(object()), CODE_FAILED)

    def test_only_an_undecodable_file_is_permanent(self):
        self.assertTrue(is_permanent(CODE_UNSUPPORTED_FORMAT))
        for code in (
            CODE_DISK_FULL, CODE_TIMEOUT, CODE_BUSY, CODE_FAILED, CODE_FFMPEG_MISSING,
            # R599: a missing decoder is fixable on this machine, so it must not be
            # written into the marker -- the marker would survive the upgrade.
            CODE_DECODER_UNAVAILABLE, "nonsense", "",
        ):
            with self.subTest(code=code):
                self.assertFalse(is_permanent(code))

    def test_a_full_disk_also_outranks_a_missing_decoder(self):
        # A full cache volume can make ffmpeg report the codec as unsupported, and
        # the reader should be told to free space, not to install ffmpeg.
        self.assertEqual(
            classify_ffmpeg_detail("Could not open output: No space left on device\n"
                                   "Unsupported audio codec"),
            CODE_DISK_FULL,
        )

    def test_the_status_separates_unsupported_media_from_a_bad_moment(self):
        self.assertEqual(http_status(CODE_UNSUPPORTED_FORMAT), 415)
        # 415 is "the request carried something I will never process".  A missing
        # decoder is our side of the fence, so it answers 503 like the rest.
        for code in (CODE_DISK_FULL, CODE_TIMEOUT, CODE_BUSY, CODE_FAILED, CODE_DECODER_UNAVAILABLE):
            self.assertEqual(http_status(code), 503)

    def test_every_code_says_something_different(self):
        messages = {code: public_message(code) for code in (
            CODE_UNSUPPORTED_FORMAT, CODE_DECODER_UNAVAILABLE, CODE_DISK_FULL, CODE_TIMEOUT,
            CODE_BUSY, CODE_FFMPEG_MISSING, CODE_FAILED,
        )}
        self.assertEqual(len(set(messages.values())), len(messages), "each code needs its own sentence")
        self.assertIn("格式", messages[CODE_UNSUPPORTED_FORMAT])
        self.assertIn("空间", messages[CODE_DISK_FULL])
        # The two verdicts ask the reader to do different things, so they cannot
        # share a sentence: one is "this file is gone", the other is "your ffmpeg".
        self.assertIn("解码器", messages[CODE_DECODER_UNAVAILABLE])
        self.assertIn("ffmpeg", messages[CODE_DECODER_UNAVAILABLE])
        self.assertNotIn("解码器", messages[CODE_UNSUPPORTED_FORMAT])
        self.assertEqual(public_message("nonsense"), public_message(CODE_FAILED), "an unknown code still says something")


class TranscodeErrorTests(unittest.TestCase):
    def test_the_error_carries_its_classification(self):
        error = transcode.TranscodeError(CODE_UNSUPPORTED_FORMAT, "音频转码失败: Invalid data")
        self.assertIsInstance(error, RuntimeError, "existing `except RuntimeError` callers must keep working")
        self.assertEqual(error.code, CODE_UNSUPPORTED_FORMAT)
        self.assertTrue(error.permanent)
        self.assertEqual(error.status, 415)
        self.assertEqual(error.public_message, public_message(CODE_UNSUPPORTED_FORMAT))

    def test_a_transient_error_is_not_permanent(self):
        error = transcode.TranscodeError(CODE_TIMEOUT)
        self.assertFalse(error.permanent)
        self.assertEqual(error.status, 503)
        self.assertIn("超时", str(error), "the message falls back to the public sentence")


class FailureMarkerTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.cache_dir = os.path.join(self.scratch.name, "cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.source = os.path.join(self.scratch.name, "song.ape")
        with open(self.source, "wb") as handle:
            handle.write(b"not really an ape")
        self.config = {"cache_dir": self.cache_dir}
        self.item = {"id": "t1", "path": self.source}

    def _target(self):
        return transcode.transcode_cache_target(self.item, self.config, "mp3")[0]

    def test_a_permanent_failure_is_recorded_and_read_back(self):
        target = self._target()
        transcode._record_transcode_failure(target, CODE_UNSUPPORTED_FORMAT, transcode._transcode_source_mtime(self.item))
        failure = transcode.transcode_failure(self.item, self.config, "mp3")
        self.assertIsNotNone(failure)
        self.assertEqual(failure["code"], CODE_UNSUPPORTED_FORMAT)
        self.assertTrue(failure["permanent"])
        self.assertEqual(failure["status"], 415)
        self.assertIn("格式", failure["message"])

    def test_a_transient_failure_is_never_recorded(self):
        # The whole point: a busy lane or a full disk says nothing about the file.
        target = self._target()
        transcode._record_transcode_failure(target, CODE_DISK_FULL, transcode._transcode_source_mtime(self.item))
        self.assertIsNone(transcode.transcode_failure(self.item, self.config, "mp3"))

    def test_a_missing_decoder_writes_no_marker(self):
        # R599: this verdict is about the ffmpeg binary.  A marker would outlive the
        # upgrade that fixes it, and the source mtime never changes to clear it.
        target = self._target()
        transcode._record_transcode_failure(
            target, CODE_DECODER_UNAVAILABLE, transcode._transcode_source_mtime(self.item),
        )
        self.assertFalse(os.path.isfile(target + ".failed"))
        self.assertIsNone(transcode.transcode_failure(self.item, self.config, "mp3"))

    def test_a_newer_source_invalidates_the_verdict(self):
        target = self._target()
        transcode._record_transcode_failure(target, CODE_UNSUPPORTED_FORMAT, transcode._transcode_source_mtime(self.item))
        # The file was replaced: the verdict was about the old bytes.
        os.utime(self.source, (1, 1))
        self.assertIsNone(transcode.transcode_failure(self.item, self.config, "mp3"))
        self.assertFalse(os.path.isfile(target + ".failed"), "the stale marker is removed, not left to linger")

    def test_a_corrupt_marker_is_ignored(self):
        target = self._target()
        with open(target + ".failed", "w", encoding="utf-8") as handle:
            handle.write("{not json")
        self.assertIsNone(transcode.transcode_failure(self.item, self.config, "mp3"))

    def test_no_marker_means_no_verdict(self):
        self.assertIsNone(transcode.transcode_failure(self.item, self.config, "mp3"))
        self.assertIsNone(transcode.transcode_failure(None, self.config))

    def test_a_marker_is_written_only_for_a_permanent_code(self):
        target = self._target()
        transcode._record_transcode_failure(target, CODE_TIMEOUT, 1.0)
        self.assertFalse(os.path.isfile(target + ".failed"))
        transcode._record_transcode_failure(target, CODE_UNSUPPORTED_FORMAT, 1.0)
        with open(target + ".failed", "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(payload["code"], CODE_UNSUPPORTED_FORMAT)


if __name__ == "__main__":
    unittest.main()

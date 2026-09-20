import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

import audio_fingerprint
from audio_fingerprint import capability, fingerprint
from fingerprint_policy import bounded_duration, bounded_timeout


class AudioFingerprintTests(unittest.TestCase):
    def test_fingerprint_policy_is_pure_and_bounded(self):
        self.assertEqual(bounded_timeout(object()), 120)
        self.assertEqual(bounded_timeout(9999), 300)
        self.assertEqual(bounded_duration(True), 0)
        self.assertEqual(bounded_duration(999999), 86400)

    def test_invalid_timeout_and_payload_values_use_safe_fallbacks(self):
        with tempfile.TemporaryDirectory() as root:
            executable = os.path.join(root, "fpcalc")
            audio = os.path.join(root, "track.flac")
            open(executable, "wb").close()
            open(audio, "wb").close()
            with mock.patch("audio_fingerprint.os.access", return_value=True), mock.patch(
                "audio_fingerprint.subprocess.run", return_value=mock.Mock(returncode=0, stdout='{"duration": true, "fingerprint": "abc"}', stderr="")
            ) as run:
                self.assertEqual(fingerprint(audio, {"metadata_fpcalc_path": executable}, timeout_seconds=10**1000)["duration"], 0)
            self.assertEqual(run.call_args.kwargs["timeout"], 300)

    def test_capability_is_disabled_without_opt_in_and_key(self):
        self.assertFalse(capability({"metadata_fingerprint_enabled": False}, {})["available"])

    def test_capability_does_not_coerce_untrusted_enabled_values(self):
        for value in ("false", "true", 1, object()):
            self.assertFalse(capability({"metadata_fingerprint_enabled": value}, {})["enabled"])

    def test_capability_does_not_stringify_untrusted_environment_values(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("environment values must not be stringified")

        self.assertFalse(capability({"metadata_fingerprint_enabled": True}, {
            "FNAUDIO_ACOUSTID_CLIENT_KEY": Explosive(),
        })["available"])

    def test_fingerprint_rejects_invalid_paths_before_filesystem_access(self):
        class Explosive:
            def __fspath__(self):
                raise AssertionError("path must be validated as text")

        with self.assertRaisesRegex(ValueError, "路径无效"):
            fingerprint(Explosive())

        with self.assertRaisesRegex(ValueError, "路径无效"):
            fingerprint("x" * (audio_fingerprint.MAX_FPCALC_PATH_CHARS + 1))

    def test_fpcalc_path_rejects_untrusted_objects_without_stringifying(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("fpcalc path must not stringify arbitrary objects")
        self.assertEqual(audio_fingerprint.find_fpcalc({"metadata_fpcalc_path": Explosive()}), "")

    def test_fingerprint_uses_a_configured_fpcalc_json_contract(self):
        with tempfile.TemporaryDirectory() as root:
            executable = os.path.join(root, "fpcalc")
            audio = os.path.join(root, "track.flac")
            with open(audio, "wb") as handle:
                handle.write(b"audio")
            with open(executable, "wb") as handle:
                handle.write(b"fixture")
            with mock.patch("audio_fingerprint.os.access", return_value=True), mock.patch(
                "audio_fingerprint.subprocess.run", return_value=mock.Mock(returncode=0, stdout='{"duration": 12, "fingerprint": "abc"}', stderr="")
            ) as run:
                self.assertEqual(fingerprint(audio, {"metadata_fpcalc_path": executable}), {"duration": 12, "fingerprint": "abc"})
            self.assertEqual(run.call_args.args[0][1:], ["-json", audio])

    def test_fingerprint_rejects_non_text_or_oversized_json_values(self):
        with tempfile.TemporaryDirectory() as root:
            executable = os.path.join(root, "fpcalc")
            audio = os.path.join(root, "track.flac")
            open(executable, "wb").close()
            open(audio, "wb").close()
            for value in ('["not-a-fingerprint"]', 'null'):
                payload = '{"duration": 12, "fingerprint": %s}' % value
                with mock.patch("audio_fingerprint.os.access", return_value=True), mock.patch(
                    "audio_fingerprint.subprocess.run", return_value=mock.Mock(returncode=0, stdout=payload, stderr="")
                ):
                    with self.assertRaisesRegex(RuntimeError, "未返回指纹"):
                        fingerprint(audio, {"metadata_fpcalc_path": executable})
            oversized = '{"duration": 12, "fingerprint": "' + ("x" * (512 * 1024)) + '"}'
            with mock.patch("audio_fingerprint.os.access", return_value=True), mock.patch(
                "audio_fingerprint.subprocess.run", return_value=mock.Mock(returncode=0, stdout=oversized, stderr="")
            ):
                    with self.assertRaisesRegex(RuntimeError, "输出过大"):
                        fingerprint(audio, {"metadata_fpcalc_path": executable})

    def test_fingerprint_bounds_compatibility_stderr_output(self):
        with tempfile.TemporaryDirectory() as root:
            executable = os.path.join(root, "fpcalc")
            audio = os.path.join(root, "track.flac")
            open(executable, "wb").close()
            open(audio, "wb").close()
            with mock.patch("audio_fingerprint.os.access", return_value=True), mock.patch(
                "audio_fingerprint.subprocess.run",
                return_value=mock.Mock(
                    returncode=1,
                    stdout="",
                    stderr="x" * (audio_fingerprint.MAX_FPCALC_OUTPUT_BYTES + 1),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "输出过大"):
                    fingerprint(audio, {"metadata_fpcalc_path": executable})

    def test_real_execution_uses_an_isolated_process_session(self):
        with tempfile.TemporaryDirectory() as root:
            executable = os.path.join(root, "fpcalc")
            audio = os.path.join(root, "track.flac")
            open(executable, "wb").close()
            open(audio, "wb").close()
            process = mock.Mock(returncode=0, pid=123)
            process.wait.return_value = 0
            with mock.patch("audio_fingerprint.os.access", return_value=True), \
                 mock.patch("audio_fingerprint.subprocess.run", new=lambda *_args, **_kwargs: None), \
                 mock.patch("audio_fingerprint.subprocess.Popen", return_value=process) as popen:
                with self.assertRaisesRegex(RuntimeError, "无效 JSON"):
                    fingerprint(audio, {"metadata_fpcalc_path": executable})

        self.assertEqual(popen.call_args.args[0], [executable, "-json", audio])
        self.assertEqual(popen.call_args.kwargs["start_new_session"], os.name != "nt")

    def test_real_execution_reaps_process_when_wait_fails(self):
        with tempfile.TemporaryDirectory() as root:
            executable = os.path.join(root, "fpcalc")
            audio = os.path.join(root, "track.flac")
            open(executable, "wb").close()
            open(audio, "wb").close()
            process = mock.Mock(returncode=0, pid=123)
            process.wait.side_effect = [RuntimeError("wait failed"), 0]
            with mock.patch("audio_fingerprint.os.access", return_value=True), \
                 mock.patch("audio_fingerprint.subprocess.run", new=lambda *_args, **_kwargs: None), \
                 mock.patch("audio_fingerprint.subprocess.Popen", return_value=process), \
                 mock.patch("audio_fingerprint.os.killpg", create=True) as killpg:
                with self.assertRaisesRegex(RuntimeError, "wait failed"):
                    fingerprint(audio, {"metadata_fpcalc_path": executable})
            if os.name != "nt":
                killpg.assert_called_once_with(123, audio_fingerprint.signal.SIGKILL)
            else:
                process.kill.assert_called_once_with()
            self.assertEqual(process.wait.call_count, 2)


if __name__ == "__main__":
    unittest.main()

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

from audio_fingerprint import capability, fingerprint


class AudioFingerprintTests(unittest.TestCase):
    def test_capability_is_disabled_without_opt_in_and_key(self):
        self.assertFalse(capability({"metadata_fingerprint_enabled": False}, {})["available"])

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


if __name__ == "__main__":
    unittest.main()

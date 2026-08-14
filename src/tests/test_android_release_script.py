from pathlib import Path
import unittest


class AndroidReleaseScriptTests(unittest.TestCase):
    def test_release_script_requires_signing_and_validates_the_artifact(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "build_android_release.ps1").read_text(encoding="utf-8")

        for expected in (
            "FNAUDIO_RELEASE_STORE_FILE",
            "FNAUDIO_RELEASE_STORE_PASSWORD",
            "FNAUDIO_RELEASE_KEY_ALIAS",
            "FNAUDIO_RELEASE_KEY_PASSWORD",
            ":app:assembleRelease",
            "apksigner.bat",
            "aapt.exe",
            "apksigner verify --verbose --print-certs",
            "aapt dump badging",
            "Release APK versionName does not match VERSION",
            "SHA256SUMS",
            "fnaudio-android-$version-release.apk",
        ):
            self.assertIn(expected, script)


if __name__ == "__main__":
    unittest.main()

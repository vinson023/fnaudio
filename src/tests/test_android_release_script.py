from pathlib import Path
import unittest


class AndroidReleaseScriptTests(unittest.TestCase):
    def test_auth_session_owns_and_cancels_timeout_runnable(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "FnOsAuthClient.java").read_text(encoding="utf-8")
        self.assertIn("private final Runnable timeoutRunnable", source)
        self.assertIn("mainHandler.postDelayed(timeoutRunnable, 20000)", source)
        self.assertGreaterEqual(source.count("mainHandler.removeCallbacks(timeoutRunnable)"), 4)

    def test_tpps_tunnel_cancels_pending_ready_poll_on_generation_change(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "TppsTunnel.java").read_text(encoding="utf-8")
        self.assertIn("private Runnable pendingReadyPoll", source)
        self.assertIn("main.removeCallbacks(pendingReadyPoll)", source)
        self.assertIn("clearReadyPoll();", source)

    def test_tpps_tunnel_stops_native_session_on_post_start_failure(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "TppsTunnel.java").read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count("stopNativeSession();"), 5)
        self.assertGreaterEqual(source.count("activePort = 0;"), 3)
        self.assertGreaterEqual(source.count("activeServerId = \"\";"), 3)
        self.assertIn("if (isCurrent(requestGeneration)) {", source)

    def test_tpps_start_snapshots_mutable_config_before_worker_handoff(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "android-client" / "app" / "src" / "main" / "java" / "com" /
                  "fnaudio" / "client" / "network" / "TppsTunnel.java").read_text(encoding="utf-8")
        self.assertIn("new JSONObject(config.toString())", source)
        self.assertIn("startOnWorker(configSnapshot, requestGeneration, callback)", source)

    def test_tpps_ready_and_timeout_paths_recheck_generation(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "TppsTunnel.java").read_text(encoding="utf-8")
        ready_block = source[source.index('if (Tpps.getConnectStatus() == 1)'):source.index('} catch (Throwable error)', source.index('if (Tpps.getConnectStatus() == 1)'))]
        timeout_block = source[source.index('if (attempt >= 48)'):source.index('Runnable poll =', source.index('if (attempt >= 48)'))]
        self.assertIn('if (!isCurrent(requestGeneration)) return;', ready_block)
        self.assertIn('if (isCurrent(requestGeneration)) {', timeout_block)

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
            "(Get-Item -LiteralPath $builtApk).Length -gt 1GB",
            "Built APK exceeds the 1 GiB artifact limit.",
            "ANDROID_SHA256SUMS",
            "fnaudio-android-$version-release.apk",
            "Refusing to overwrite a same-version APK",
        ):
            self.assertIn(expected, script)

        self.assertNotIn("Copy-Item -LiteralPath $builtApk -Destination $artifactPath -Force", script)
        self.assertIn("$temporaryArtifact = Join-Path $destination", script)
        self.assertIn("Copy-Item -LiteralPath $builtApk -Destination $temporaryArtifact", script)
        self.assertIn("$hash = Get-Sha256Hex -Path $temporaryArtifact", script)
        self.assertIn("Move-Item -LiteralPath $temporaryArtifact -Destination $artifactPath", script)
        self.assertIn("Remove-Item -LiteralPath $temporaryArtifact -Force", script)
        self.assertIn("$artifactMoved = $false", script)
        self.assertIn("if ($artifactMoved)", script)

    def test_release_script_rejects_existing_artifact_before_gradle_and_supports_hash_fallback(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "build_android_release.ps1").read_text(encoding="utf-8")

        self.assertIn("function Get-Sha256Hex", script)
        self.assertIn("Get-Command -Name Get-FileHash", script)
        self.assertIn("Security.Cryptography.SHA256", script)
        existing_check = script.index("Refusing to overwrite a same-version APK")
        gradle_build = script.index(":app:assembleRelease")
        self.assertLess(existing_check, gradle_build)
        self.assertIn("$hash = Get-Sha256Hex -Path $temporaryArtifact", script)
        self.assertIn("(Test-Path -LiteralPath $artifactPath) -or (Test-Path -LiteralPath $hashPath)", script)
        self.assertIn("(Test-Path -LiteralPath $artifactPath) -or (Test-Path -LiteralPath $hashPath)", script)

    def test_release_script_selects_build_tools_by_numeric_version(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "build_android_release.ps1").read_text(encoding="utf-8")
        self.assertIn("[version]::new", script)
        self.assertNotIn("Sort-Object Name -Descending", script)


if __name__ == "__main__":
    unittest.main()

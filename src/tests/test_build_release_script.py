from pathlib import Path
import unittest


class BuildReleaseScriptTests(unittest.TestCase):
    def test_script_uses_a_temporary_copy_of_the_authoritative_source_tree(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "build_release.ps1").read_text(encoding="utf-8")

        self.assertIn('Join-Path $repoRoot "src"', script)
        self.assertIn('& $FnpackPath build --directory $stageRoot', script)
        self.assertIn('/XD tests __pycache__ /XF fnaudio.fpk *.pyc', script)
        self.assertIn('Remove-Item -LiteralPath $temporaryRoot -Recurse -Force', script)

    def test_script_checks_all_release_version_surfaces_and_the_payload(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "build_release.ps1").read_text(encoding="utf-8")

        for expected in (
            'src/manifest',
            'src/app/server/server.py',
            'src/app/server/version.py',
            'src/app/ui/index.html',
            'android-client/app/build.gradle',
            'must define a positive integer versionCode',
            'versionCode must be positive',
            'Packaged manifest version differs from VERSION.',
            'packaged server/server.py',
            'packaged server/version.py',
            'packaged ui/index.html',
            'FPK payload unexpectedly contains test sources.',
            '__FNAUDIO_ASSET_BUILD__',
            'content-derived cache key',
        ):
            self.assertIn(expected, script)

    def test_script_checks_fpk_lifecycle_config_wizards_and_runtime_payload(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "build_release.ps1").read_text(encoding="utf-8")

        for command in (
            "config_callback",
            "config_init",
            "install_callback",
            "install_init",
            "main",
            "uninstall_callback",
            "uninstall_init",
            "upgrade_callback",
            "upgrade_init",
        ):
            self.assertIn(f'"{command}"', script)

        for expected in (
            '"config\\privilege"',
            '"config\\resource"',
            'defaults.run-as=root',
            '"fnaudio/music"',
            '"fnaudio/data"',
            '"wizard_library_path"',
            '"wizard_uninstall_mode"',
            '"ui\\index.cgi"',
            '"ui\\cgi_proxy.py"',
            '"ui\\service_port.json"',
            '"target\\bin\\mpd"',
        ):
            self.assertIn(expected, script)


if __name__ == "__main__":
    unittest.main()

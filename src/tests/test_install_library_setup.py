import json
import os
from pathlib import Path
import shutil
import subprocess
import socket
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class InstallLibrarySetupTests(unittest.TestCase):
    def run_complete_callback(self, previous=None):
        bash = shutil.which("bash")
        if not bash and os.name == "nt":
            candidate = Path("C:/Program Files/Git/bin/bash.exe")
            bash = str(candidate) if candidate.is_file() else None
        if not bash:
            self.skipTest("bash is unavailable")
        with tempfile.TemporaryDirectory(prefix="fnaudio-install-contract-") as directory:
            fixture = Path(directory)
            config_dir = fixture / "etc"
            config_dir.mkdir()
            app_dir = fixture / "apps/fnaudio"
            ui = app_dir / "target/ui"
            ui.mkdir(parents=True)
            config = config_dir / "config.json"
            if previous is not None:
                paths = [str(fixture / "music-a"), str(fixture / "music-b")]
                previous = dict(previous, library_path="\n".join(paths), library_paths=paths)
                config.write_text(json.dumps(previous), encoding="utf8")
            source = (ROOT / "src/cmd/install_callback").read_text(encoding="utf8")
            source = source.replace('PYTHON_BIN="/var/apps/python312/target/bin/python3"', 'PYTHON_BIN="' + Path(sys.executable).as_posix() + '"')
            # The fnOS compatibility symlink must also remain inside the fixture.
            source = source.replace('/var/apps/fnaudio/target', (fixture / "compat-target").as_posix())
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            env = {key: value for key, value in os.environ.items() if not key.startswith("wizard_library_path")}
            env.update(TRIM_APPDEST=app_dir.as_posix(), TRIM_PKGETC=config_dir.as_posix(), TRIM_PKGVAR=(fixture / "var").as_posix(), wizard_server_port=str(port))
            result = subprocess.run([bash, "--noprofile", "--norc"], input=source, env=env, text=True, encoding="utf8", errors="replace", capture_output=True, timeout=25)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            saved = json.loads(config.read_text(encoding="utf8"))
            self.assertEqual(saved["server_port"], port)
            self.assertEqual(json.loads((ui / "service_port.json").read_text(encoding="utf8"))["server_port"], port)
            if previous is not None:
                self.assertEqual(saved["library_paths"], previous["library_paths"])
                self.assertEqual(saved["renderer_name"], previous["renderer_name"])
            return saved

    def test_complete_fresh_install_writes_empty_roots(self):
        saved = self.run_complete_callback()
        self.assertEqual(saved["library_path"], "")
        self.assertEqual(saved["library_paths"], [])

    def test_complete_upgrade_preserves_roots_and_preferences(self):
        self.run_complete_callback({"renderer_name": "Living room", "metadata_enabled": False})

    def test_release_package_requires_runtime_port_and_rejects_install_library_field(self):
        script = (ROOT / "tools/build_release.ps1").read_text(encoding="utf8")
        self.assertIn('"install" = @("wizard_server_port")', script)
        self.assertIn('$wizardName -eq "install" -and $wizardFields -contains "wizard_library_path"', script)
        self.assertIn('Packaged install wizard must configure music directories after installation.', script)

    def test_installer_only_asks_for_runtime_port(self):
        wizard = json.loads((ROOT / "src/wizard/install").read_text(encoding="utf8"))
        fields = [item["field"] for step in wizard for item in step["items"]]
        self.assertEqual(fields, ["wizard_server_port"])

    def test_picker_scope_is_declared_for_the_micro_app(self):
        resource = json.loads((ROOT / "src/config/resource").read_text(encoding="utf8"))
        self.assertIn("trim.file.userAccess", resource["api-scope"])

    def install_path(self, existing="", wizard=""):
        bash = shutil.which("bash")
        if not bash and os.name == "nt":
            candidate = Path("C:/Program Files/Git/bin/bash.exe")
            bash = str(candidate) if candidate.is_file() else None
        if not bash:
            self.skipTest("bash is unavailable")
        source = (ROOT / "src/cmd/install_callback").read_text(encoding="utf8")
        first = source[source.index('library_path="${wizard_library_paths'):source.index('server_port="${wizard_server_port')]
        second = source[source.index('if [ -n "${existing_library_path}" ]'):source.index('if ! mkdir -p "${UI_ROOT}"')]
        env = dict(os.environ, existing_library_path=existing, wizard_library_path=wizard, TRIM_APPDEST="/var/apps/fnaudio")
        env.pop("wizard_library_paths", None)
        result = subprocess.run([bash, "--noprofile", "--norc"], input=first + second + '\nprintf "%s" "$library_path"\n', env=env, text=True, encoding="utf8", errors="replace", capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_fresh_install_does_not_invent_a_music_directory(self):
        self.assertEqual(self.install_path(), "")

    def test_upgrade_keeps_existing_multiple_directories(self):
        paths = "/vol1/music\n/vol2/music"
        self.assertEqual(self.install_path(paths), paths)

    def test_legacy_wizard_input_is_still_honoured(self):
        self.assertEqual(self.install_path("", "/vol2/selected"), "/vol2/selected")

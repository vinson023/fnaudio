import json
import pathlib
import tempfile
import unittest


class AppLifecycleScriptTests(unittest.TestCase):
    def test_install_callback_merges_existing_config_instead_of_replacing_it(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        script = (root / "src" / "cmd" / "install_callback").read_text(encoding="utf-8")
        self.assertIn("json.load(fh)", script)
        self.assertIn("payload.update({", script)
        self.assertIn("Only fields owned by the install wizard", script)
        self.assertNotIn('payload = {"library_path"', script)

    def test_install_callback_prefers_wizard_port_and_rejects_conflicts(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        script = (root / "src" / "cmd" / "install_callback").read_text(encoding="utf-8")
        self.assertIn('${wizard_server_port:-${existing_server_port:-53199}}', script)
        self.assertIn("服务端口 %s 已被占用", script)

    def test_uninstall_defaults_to_keep_and_supports_explicit_purge(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        script = (root / "src" / "cmd" / "uninstall_callback").read_text(encoding="utf-8")
        self.assertIn('wizard_uninstall_mode:-keep', script)
        self.assertIn('wizard_uninstall_mode:-keep', script)
        self.assertIn('FNAUDIO_PURGE:-0', script)
        self.assertIn("safe_remove_app_data", script)
        self.assertIn('readlink -f -- "${target}"', script)
        self.assertIn('rm -rf -- "${resolved}"', script)
        self.assertIn('@appdata/fnaudio(/(etc|var|data))?', script)
        self.assertNotIn('@appdata/fnaudio/*', script)
        self.assertNotIn('rm -rf "${TRIM_PKGETC}"', script)

    def test_lifecycle_scripts_resolve_flat_and_targeted_ui_roots(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        for name in ("install_callback", "upgrade_callback", "config_callback"):
            script = (root / "src" / "cmd" / name).read_text(encoding="utf-8")
            self.assertIn('UI_ROOT="${TRIM_APPDEST}/target/ui"', script)
            self.assertIn('UI_ROOT="${TRIM_APPDEST}/ui"', script)
            self.assertIn('service_port.json', script)
            self.assertNotIn('${TRIM_APPDEST}/target/ui/service_port.json', script)

    def test_app_center_reservation_port_is_not_rewritten_from_backend_port(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        for name in ("install_callback", "upgrade_callback", "config_callback", "main"):
            script = (root / "src" / "cmd" / name).read_text(encoding="utf-8")
            self.assertIn("manifest.service_port", script)
            self.assertNotIn('for manifest in /var/apps/fnaudio/manifest', script)
        manifest = (root / "src" / "manifest").read_text(encoding="utf-8")
        self.assertIn("checkport=false", manifest)

    def test_main_rejects_busy_configured_backend_port(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        main = (root / "src" / "cmd" / "main").read_text(encoding="utf-8")
        self.assertIn("configured_port_available", main)
        self.assertIn("persist_backend_port", main)
        self.assertNotIn("choose_available_port", main)
        self.assertIn("is already in use", main)

    def test_lifecycle_scripts_apply_private_runtime_and_public_ui_modes(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        for name in ("install_callback", "upgrade_callback", "config_callback", "main"):
            script = (root / "src" / "cmd" / name).read_text(encoding="utf-8")
            self.assertIn("umask 077", script)
            self.assertIn('chmod 600', script)
            self.assertIn('chmod 644 "${UI_ROOT}/service_port.json"', script)
        main = (root / "src" / "cmd" / "main").read_text(encoding="utf-8")
        self.assertIn('install -d -m 700 "${TRIM_PKGETC}" "${TRIM_PKGVAR}"', main)
        self.assertIn('chmod 600 "${PID_FILE}"', main)

        config_init = (root / "src" / "cmd" / "config_init").read_text(encoding="utf-8")
        self.assertIn("umask 077", config_init)
        self.assertIn("os.chmod(target, 0o644)", config_init)

    def test_backend_port_is_an_app_center_wizard_option(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        for relative in ("src/wizard/install", "src/wizard/config", "src/cmd/config_init"):
            content = (root / relative).read_text(encoding="utf-8")
            self.assertIn("wizard_server_port", content)
            self.assertIn("53199", content)

    def test_library_settings_never_rewrite_app_center_manifest_port(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        server = (root / "src" / "app" / "server" / "server.py").read_text(encoding="utf-8")
        config = (root / "src" / "app" / "server" / "config.py").read_text(encoding="utf-8")
        self.assertNotIn("save_manifest_port", server)
        self.assertNotIn("save_manifest_port", config)


if __name__ == "__main__":
    unittest.main()

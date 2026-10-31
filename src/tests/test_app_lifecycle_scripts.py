import json
import pathlib
import tempfile
import unittest


class AppLifecycleScriptTests(unittest.TestCase):
    @staticmethod
    def project_root():
        return pathlib.Path(__file__).resolve().parents[2]

    @staticmethod
    def manifest_values(content):
        return dict(
            line.split("=", 1)
            for line in content.splitlines()
            if line and not line.startswith("#") and "=" in line
        )

    def test_manifest_and_wizards_share_one_backend_port_default(self):
        root = self.project_root()
        manifest = self.manifest_values((root / "src" / "manifest").read_text(encoding="utf-8"))
        install = json.loads((root / "src" / "wizard" / "install").read_text(encoding="utf-8"))
        config = json.loads((root / "src" / "wizard" / "config").read_text(encoding="utf-8"))

        def port_item(wizard):
            return next(item for step in wizard for item in step["items"] if item.get("field") == "wizard_server_port")

        self.assertEqual(manifest["service_port"], "53199")
        self.assertEqual(port_item(install)["initValue"], manifest["service_port"])
        self.assertEqual(port_item(config)["initValue"], manifest["service_port"])
        self.assertEqual(manifest["checkport"], "false")

    def test_install_callback_merges_existing_config_instead_of_replacing_it(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        script = (root / "src" / "cmd" / "install_callback").read_text(encoding="utf-8")
        self.assertIn("json.load(fh)", script)
        self.assertIn("payload.update({", script)
        self.assertIn("Only fields owned by the install wizard", script)
        self.assertNotIn('payload = {"library_path"', script)

    def test_lifecycle_config_migrations_reject_non_object_configs_and_non_text_paths(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        config_callback = (root / "src" / "cmd" / "config_callback").read_text(encoding="utf-8")
        self.assertIn('if not isinstance(payload, dict):', config_callback)
        for name in ("install_callback", "upgrade_callback"):
            script = (root / "src" / "cmd" / name).read_text(encoding="utf-8")
            self.assertIn('def paths_from(payload):', script)
            self.assertIn('isinstance(value, str) and value.strip()', script)
            self.assertNotIn('str(value or "").strip()', script)

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

    def test_upgrade_migrates_legacy_library_path_as_structured_json(self):
        root = self.project_root()
        script = (root / "src" / "cmd" / "upgrade_callback").read_text(encoding="utf-8")
        self.assertIn('json.load(handle)', script)
        self.assertIn('payload["library_paths"] = migrated', script)
        self.assertIn('os.path.normpath(value) == old', script)
        self.assertNotIn('grep -q "\\\"library_path\\\"', script)
        self.assertNotIn('sed -i "s#\\\"library_path', script)

    def test_install_and_upgrade_restore_standard_fnos_target_link(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        for name in ("install_callback", "upgrade_callback"):
            script = (root / "src" / "cmd" / name).read_text(encoding="utf-8")
            self.assertIn("RUNTIME_TARGET=", script)
            self.assertIn("[ ! -e /var/apps/fnaudio/target ]", script)
            self.assertIn("ln -s", script)
            self.assertIn("/var/apps/fnaudio/target", script)

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

    def test_main_starts_server_without_second_shell_parsing(self):
        root = self.project_root()
        main = (root / "src" / "cmd" / "main").read_text(encoding="utf-8")
        self.assertIn('cmd=(env "TRIM_API_TOKEN=${TRIM_API_TOKEN:-}"', main)
        self.assertIn('nohup "${cmd[@]}" >> "${LOG_FILE}" 2>&1 &', main)
        self.assertNotIn('CMD="TRIM_API_TOKEN=', main)
        self.assertNotIn('nohup bash -c "${CMD}"', main)

    def test_main_reports_startup_timeout_as_failure_and_checks_port_persistence(self):
        root = self.project_root()
        main = (root / "src" / "cmd" / "main").read_text(encoding="utf-8")
        self.assertIn('if ! persist_backend_port; then', main)
        self.assertIn('Unable to persist configured backend port', main)
        self.assertIn('return 1\n}', main)
        self.assertIn('stop_pid "$!" 5', main)
        self.assertIn('rm -f "${PID_FILE}"\n  return 1', main)
        self.assertNotIn('server started but TCP port ${SERVER_PORT} is not ready yet\n}', main)

    def test_main_persists_backend_port_with_atomic_config_replacement(self):
        root = self.project_root()
        main = (root / "src" / "cmd" / "main").read_text(encoding="utf-8")
        self.assertIn("tempfile.mkstemp", main)
        self.assertIn("os.replace(temporary, path)", main)
        self.assertIn("os.fsync(fh.fileno())", main)
        self.assertIn("os.fchmod(fd, mode)", main)

    def test_main_validates_pid_file_process_identity_before_status_or_stop(self):
        root = self.project_root()
        main = (root / "src" / "cmd" / "main").read_text(encoding="utf-8")
        self.assertIn("valid_pid()", main)
        self.assertIn("''|*[!0-9]*|0|0*|1|\"$$\") return 1", main)
        self.assertIn('valid_pid "$1" || return 1', main)
        self.assertIn('valid_pid "${candidate}" || return 1', main)
        self.assertIn('valid_pid "${candidate}" || return 0', main)
        self.assertIn("is_fnaudio_server_pid()", main)
        self.assertIn('check_process "${pid}" && is_fnaudio_server_pid "${pid}"', main)
        self.assertIn('if is_fnaudio_server_pid "${pid}"; then', main)
        self.assertIn('*"${APP_ROOT}/server.py"*"--port"*)', main)
        # A path-qualified legacy match is intentional; reject only the
        # unqualified server.py pattern that could terminate an unrelated app.
        self.assertNotIn('\n    *"server.py"*"--port"*) return 0', main)
        sweep = main.split("cleanup_stale_servers()")[1]
        self.assertIn(
            '*"@appcenter/fnaudio/"*"server.py"*"--port"*|'
            '*"/var/apps/fnaudio/"*"server.py"*"--port"*|'
            '*"${APP_ROOT}/server.py"*"--port"*)',
            sweep,
        )
        self.assertNotIn('"server.py"*)', sweep)

    def test_main_cleans_legacy_fnaudio_server_paths_after_reinstall(self):
        root = self.project_root()
        main = (root / "src" / "cmd" / "main").read_text(encoding="utf-8")
        self.assertIn('*"/var/apps/fnaudio/"*"server.py"*"--port"*', main)
        self.assertIn('*"/usr/local/apps/@appcenter/fnaudio/"*"server.py"*"--port"*', main)

    def test_main_validates_mpd_pid_file_process_identity_before_stop(self):
        root = self.project_root()
        main = (root / "src" / "cmd" / "main").read_text(encoding="utf-8")
        self.assertIn("is_fnaudio_mpd_pid()", main)
        self.assertIn('if is_fnaudio_mpd_pid "${mpd_pid}"; then', main)
        self.assertIn("valid_pid()", main)
        self.assertIn("''|*[!0-9]*|0|0*|1|\"$$\") return 1", main)
        self.assertIn('"${TRIM_APPDEST}/share/mpd/mpd.conf"', main)
        self.assertNotIn('stop_pid "${mpd_pid}" 5\n  fi', main)

    def test_lifecycle_scripts_normalize_corrupt_backend_ports(self):
        root = self.project_root()
        main = (root / "src" / "cmd" / "main").read_text(encoding="utf-8")
        upgrade = (root / "src" / "cmd" / "upgrade_callback").read_text(encoding="utf-8")
        config_init = (root / "src" / "cmd" / "config_init").read_text(encoding="utf-8")
        self.assertIn('SERVER_PORT="53199"', main)
        self.assertIn('[ "${SERVER_PORT}" -lt 1024 ]', main)
        self.assertIn('???????*) SERVER_PORT="53199"', main)
        self.assertIn('[ "${configured_port}" -lt 1024 ]', upgrade)
        self.assertIn('isinstance(candidate, int) and not isinstance(candidate, bool)', config_init)
        for name in ("install_callback", "config_callback"):
            script = (root / "src" / "cmd" / name).read_text(encoding="utf-8")
            self.assertIn('1024 <= candidate <= 65535', script)
            self.assertIn('not isinstance(candidate, bool)', script)

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
        self.assertIn("os.fchmod(fd, 0o644)", config_init)

    def test_service_port_projection_fails_closed_and_uses_atomic_replacement(self):
        root = self.project_root()
        for name in ("install_callback", "upgrade_callback", "config_callback"):
            script = (root / "src" / "cmd" / name).read_text(encoding="utf-8")
            self.assertIn('service_port.json.tmp.$$"', script)
            self.assertIn('mv -f -- "${service_port_tmp}" "${UI_ROOT}/service_port.json"', script)
            self.assertIn('echo "无法写入 service_port.json。" >&2', script)
            self.assertNotIn('service_port.json" 2>/dev/null || true', script)

    def test_all_lifecycle_config_writes_are_atomic(self):
        root = self.project_root()
        for name in ("install_callback", "upgrade_callback", "config_callback"):
            script = (root / "src" / "cmd" / name).read_text(encoding="utf-8")
            self.assertIn("tempfile.mkstemp", script)
            self.assertIn("os.replace(temporary", script)
            self.assertIn("os.fsync", script)
            self.assertNotIn('open(config_path, "w", encoding="utf-8")', script)

    def test_config_init_fails_closed_and_atomically_refreshes_wizard_files(self):
        root = self.project_root()
        script = (root / "src" / "cmd" / "config_init").read_text(encoding="utf-8")
        self.assertIn('raise RuntimeError("fnAudio runtime paths are unavailable")', script)
        self.assertIn('tempfile.mkstemp(prefix=".config.", dir=directory)', script)
        self.assertIn("os.replace(temporary, target)", script)
        self.assertIn("os.fsync(fh.fileno())", script)
        self.assertIn("exit $?", script)
        self.assertNotIn("except Exception:\n        pass", script)

    def test_lifecycle_python_migrations_fail_closed(self):
        root = self.project_root()
        for name in ("install_callback", "upgrade_callback", "config_callback"):
            script = (root / "src" / "cmd" / name).read_text(encoding="utf-8")
            self.assertIn('if ! "${PYTHON_BIN}" -', script)
            self.assertIn('echo "无法', script)
            self.assertIn('exit 1', script)

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

from pathlib import Path
import unittest


class FastDeployScriptTests(unittest.TestCase):
    def test_supports_default_lan_and_explicit_sudo_ssh_paths(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "install_test_host_fast.ps1").read_text(encoding="utf-8")
        self.assertIn("[int]$SshPort = 22", script)
        self.assertIn("[switch]$UseSudo", script)
        self.assertIn("[string]$RemotePackageDirectory = '/vol1/1000/fnaudio'", script)
        self.assertIn("RemotePackageDirectory must be an absolute POSIX path", script)
        self.assertIn("containing only safe path segments", script)
        self.assertIn("^/(?:[A-Za-z0-9._-]+/)*[A-Za-z0-9._-]+$", script)
        self.assertIn('"mkdir -p -- \'$remotePackageDirectory\'"', script)
        self.assertIn("ToBase64String([Text.Encoding]::UTF8.GetBytes($Password))", script)
        self.assertIn("$directoryCommand =", script)
        self.assertIn("sudo -S -p ''", script)
        self.assertNotIn("printf '%s\\n' '$Password' | sudo", script)
        self.assertLess(script.index('mkdir -p --'), script.index('& $pscp'))
        self.assertIn("-P $SshPort", script)
        self.assertIn("if ($UseSudo)", script)
        self.assertIn("-m $remoteCommandFile", script)
        self.assertIn("did not return its completion marker", script)
        self.assertIn('mkdir -p "$RUN_ROOT"', script)
        self.assertIn('STAMP="$(date +%Y%m%d-%H%M%S)"', script)
        self.assertIn('BACKUP_DIR="$(mktemp -d "$BACKUP_ROOT/${STAMP}.XXXXXX")"', script)
        self.assertIn('if [ -n "${RUN_DIR:-}" ] && [ -d "$RUN_DIR" ]; then', script)
        self.assertIn('rm -rf "$RUN_DIR"', script)
        self.assertLess(script.index('rm -rf "$RUN_DIR"'), script.index('exit "$status"'))
        self.assertIn('COMMITTED=1\nif [ -d "$RUN_DIR" ]; then rm -rf "$RUN_DIR"; fi', script)
        self.assertIn("fast deploy failed; restoring previous application", script)
        self.assertIn("Package filename contains unsupported shell characters", script)
        self.assertIn("$packageName -notmatch '^[A-Za-z0-9._-]+\\.fpk$'", script)


if __name__ == "__main__":
    unittest.main()

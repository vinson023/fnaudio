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
        self.assertIn("-P $SshPort", script)
        self.assertIn("if ($UseSudo)", script)
        self.assertIn('mkdir -p "$RUN_ROOT"', script)
        self.assertIn("fast deploy failed; restoring previous application", script)


if __name__ == "__main__":
    unittest.main()

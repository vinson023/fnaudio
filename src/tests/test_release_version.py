from pathlib import Path
import importlib.util
import re
import unittest
from unittest.mock import mock_open, patch


class ReleaseVersionTests(unittest.TestCase):
    def test_release_version_is_consistent_across_runtime_and_ui(self):
        root = Path(__file__).resolve().parents[2]
        version = (root / "VERSION").read_text(encoding="utf-8").strip()
        manifest = (root / "src" / "manifest").read_text(encoding="utf-8")
        server = (root / "src" / "app" / "server" / "server.py").read_text(encoding="utf-8")
        version_module_path = root / "src" / "app" / "server" / "version.py"
        index = (root / "src" / "app" / "ui" / "index.html").read_text(encoding="utf-8")
        gradle = (root / "android-client" / "app" / "build.gradle").read_text(encoding="utf-8")

        self.assertRegex(manifest, rf"(?m)^version={re.escape(version)}$")
        spec = importlib.util.spec_from_file_location("fnaudio_version", version_module_path)
        version_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(version_module)
        self.assertEqual(version_module.APP_VERSION, version)
        self.assertEqual(version_module.APP_USER_AGENT, f"fnAudio/{version}")
        self.assertIn("/var/apps/fnaudio/manifest", version_module._manifest_paths())
        with patch.object(version_module, "_manifest_paths", return_value=["/installed/manifest"]), patch(
            "builtins.open", mock_open(read_data="version=9.8.7\n")
        ):
            self.assertEqual(version_module._manifest_version(), "9.8.7")
        self.assertIn("server_version = APP_USER_AGENT", server)
        self.assertIn("app.css?v=__FNAUDIO_ASSET_BUILD__", index)
        self.assertIn("view_presentation.js?v=__FNAUDIO_ASSET_BUILD__", index)
        self.assertIn("app.js?v=__FNAUDIO_ASSET_BUILD__", index)
        self.assertIn(f'versionName "{version}"', gradle)
        version_code = re.search(r"(?m)^\s*versionCode\s+(\d+)\s*$", gradle)
        self.assertIsNotNone(version_code)
        self.assertGreater(int(version_code.group(1)), 0)


if __name__ == "__main__":
    unittest.main()

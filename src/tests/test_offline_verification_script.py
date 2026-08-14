from pathlib import Path
import unittest


class OfflineVerificationScriptTests(unittest.TestCase):
    def test_script_runs_the_full_offline_regression_set(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "test_offline.ps1").read_text(encoding="utf-8")
        self.assertIn("unittest discover -s tests -v", script)
        self.assertIn("node --check app\\ui\\app.js", script)
        for name in (
            "test_ui_android_bridge.js",
            "test_ui_mobile_layout.js",
            "test_ui_queue_columns.js",
            "test_ui_lyrics_priority.js",
            "test_ui_user_state.js",
        ):
            self.assertIn(name, script)
        self.assertIn("git diff --check", script)
        self.assertIn("build_release.ps1", script)


if __name__ == "__main__":
    unittest.main()

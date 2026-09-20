from pathlib import Path
import json
import unittest


class FnosMicroAppLaunchTests(unittest.TestCase):
    """Keep fnAudio on the fnOS micro-app iframe launch path."""

    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]

    def test_manifest_uses_micro_app_not_native_app(self):
        manifest = (self.root / "src" / "manifest").read_text(encoding="utf-8")
        self.assertIn("micro_app=true", manifest)
        self.assertNotIn("native_app=true", manifest)

    def test_desktop_entry_is_iframe_url(self):
        config = json.loads((self.root / "src" / "app" / "ui" / "config").read_text(encoding="utf-8"))
        entry = config[".url"]["fnaudio.Application"]
        self.assertEqual(entry["type"], "iframe")
        self.assertEqual(entry["url"], "/cgi/ThirdParty/fnaudio/index.cgi/")


if __name__ == "__main__":
    unittest.main()

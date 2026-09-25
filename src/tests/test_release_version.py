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
        readme = (root / "README.md").read_text(encoding="utf-8")
        android_readme = (root / "android-client" / "README.md").read_text(encoding="utf-8")

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
        self.assertIn("track_presentation.js?v=__FNAUDIO_ASSET_BUILD__", index)
        self.assertIn("ui_sync_scheduler.js?v=__FNAUDIO_ASSET_BUILD__", index)
        self.assertIn("library_pager_visibility.js?v=__FNAUDIO_ASSET_BUILD__", index)
        self.assertIn("library_pager_presentation.js?v=__FNAUDIO_ASSET_BUILD__", index)
        self.assertIn("library_track_filter_policy.js?v=__FNAUDIO_ASSET_BUILD__", index)
        self.assertIn("library_root_label_policy.js?v=__FNAUDIO_ASSET_BUILD__", index)
        self.assertLess(index.index("library_track_filter_policy.js"), index.index("app.js?v=__FNAUDIO_ASSET_BUILD__"))
        self.assertLess(index.index("library_root_label_policy.js"), index.index("app.js?v=__FNAUDIO_ASSET_BUILD__"))
        self.assertIn("app.js?v=__FNAUDIO_ASSET_BUILD__", index)
        self.assertIn(f'versionName "{version}"', gradle)
        self.assertRegex(readme, rf"当前发布基线为 `?{re.escape(version)}`?")
        self.assertIn(f"fnAudio `{version}`", android_readme)
        self.assertIn(f"配套服务端版本基线为 `{version}`", android_readme)
        version_code = re.search(r"(?m)^\s*versionCode\s+(\d+)\s*$", gradle)
        self.assertIsNotNone(version_code)
        self.assertGreater(int(version_code.group(1)), 0)

    def test_manuals_state_the_release_version_wherever_they_claim_current(self):
        """Every "current version" sentence in the manuals is answered from VERSION.

        A release bump moves VERSION, src/manifest, the Gradle block and several
        sentences that restate the same fact by hand.  Until now the guard checked
        exactly one of those sentences ("当前发布基线为"), so the 0.2.35 bump left
        README, ARCHITECTURE and the source inventory still naming 0.2.34: a second,
        older record of the current version, which is the rot RECOVERY.md already has
        a dedicated guard against.  The loop below derives the expected value from
        VERSION instead of repeating a number here, and it scans for any sentence that
        claims a current version rather than for a fixed list, so a coordinate nobody
        thought to pin is covered as well.
        """
        root = Path(__file__).resolve().parents[2]
        version = (root / "VERSION").read_text(encoding="utf-8").strip()
        current_claims = re.compile(r"当前[^。\n]*`([0-9]+\.[0-9]+\.[0-9]+)`")
        for relative in ("README.md", "ARCHITECTURE.md", "docs/SOURCE_INVENTORY.md", "android-client/README.md"):
            text = (root / relative).read_text(encoding="utf-8").replace("\r\n", "\n")
            claims = current_claims.findall(text)
            self.assertTrue(
                claims,
                relative + " must keep at least one sentence naming the current version",
            )
            self.assertEqual(
                sorted(set(claims)),
                [version],
                relative + " states a version that is not the current VERSION: " + repr(claims),
            )
        # The summary table row is the only current-version coordinate that never
        # says "当前", so it is pinned on its own shape instead of by the sweep.
        readme = (root / "README.md").read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertEqual(
            re.findall(r"(?m)^\| 版本 \| `([^`]*)` \|$", readme),
            [version],
            "README.md must state the current version in exactly one summary row",
        )
        # The artifact directory named in the manual is the same claim seen from the
        # other side: README sends a maintainer to artifacts/<VERSION>/, and a stale
        # path there points at the previous package. It sits in a sentence without
        # the "current" wording, so the sweep above cannot see it and it is pinned
        # on its own.
        self.assertEqual(
            re.findall(r"产物位于 `artifacts/([^/`]*)/`", readme),
            [version],
            "README.md must point at the artifact directory of the current version",
        )


if __name__ == "__main__":
    unittest.main()

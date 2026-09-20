import hashlib
import re
import unittest
from pathlib import Path


class SourceManifestTests(unittest.TestCase):
    def test_root_manifest_matches_authoritative_source_tree(self):
        repo_root = Path(__file__).resolve().parents[2]
        manifest_path = repo_root / "SOURCE_MANIFEST.sha256"
        excluded_segments = {".gradle", ".media3-inspect", ".idea", "build", "__pycache__"}
        excluded_names = {"local.properties"}
        excluded_extensions = {".apk", ".aab", ".aar", ".class", ".fpk", ".pyc"}
        files = []
        for source_root in (repo_root / "src", repo_root / "android-client"):
            for path in source_root.rglob("*"):
                if not path.is_file():
                    continue
                relative = path.relative_to(repo_root).as_posix()
                if any(segment in excluded_segments for segment in relative.split("/")):
                    continue
                if path.name in excluded_names or path.suffix.lower() in excluded_extensions:
                    continue
                files.append(path)
        expected = []
        for path in sorted(files, key=lambda value: str(value).lower()):
            digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
            expected.append(f"{digest}  {path.relative_to(repo_root).as_posix()}")
        actual = manifest_path.read_text(encoding="ascii").splitlines()
        self.assertEqual(len(actual), len(set(actual)), "SOURCE_MANIFEST.sha256 contains duplicate records")
        self.assertEqual(sorted(actual), sorted(expected), "SOURCE_MANIFEST.sha256 is stale; run tools/update_source_manifest.ps1")

    def test_index_declared_local_assets_exist_and_are_cache_stamped(self):
        repo_root = Path(__file__).resolve().parents[2]
        index = (repo_root / "src/app/ui/index.html").read_text(encoding="utf-8")
        assets = re.findall(r'(?:src|href)="([^"?]+)\?v=__FNAUDIO_ASSET_BUILD__"', index)
        self.assertTrue(assets)
        self.assertEqual(len(assets), len(set(assets)), "index.html declares duplicate stamped assets")
        for relative in assets:
            self.assertNotIn("..", Path(relative).parts)
            self.assertTrue((repo_root / "src/app/ui" / relative).is_file(), relative)

    def test_index_references_every_local_ui_asset_with_the_build_stamp(self):
        """A stable JS/CSS URL survives an in-place upgrade as stale cached bytes."""
        repo_root = Path(__file__).resolve().parents[2]
        index = (repo_root / "src/app/ui/index.html").read_text(encoding="utf-8")
        references = re.findall(
            r'(?i)<(?:script[^>]+src|link[^>]+href)="(?P<target>[^"]+)"', index
        )
        self.assertTrue(references)
        for target in references:
            if target.startswith("data:") or "://" in target:
                continue
            if not re.search(r'\.(?:css|js)(?:\?|$)', target):
                continue
            self.assertIn(
                "?v=__FNAUDIO_ASSET_BUILD__",
                target,
                "local UI asset must be cache-stamped in index.html: " + target,
            )

        stamped_scripts = re.findall(
            r'(?i)<script src="(?P<target>[^"?]+)\?v=__FNAUDIO_ASSET_BUILD__"', index
        )
        self.assertIn("app.js", stamped_scripts)


    def test_manifest_script_has_a_minimal_powershell_hash_fallback(self):
        repo_root = Path(__file__).resolve().parents[2]
        script = (repo_root / "tools/update_source_manifest.ps1").read_text(encoding="utf-8")
        self.assertIn("function Get-Sha256Hex", script)
        self.assertIn("Get-Command -Name Get-FileHash", script)
        self.assertIn("Security.Cryptography.SHA256", script)
        self.assertIn("Get-Sha256Hex -Path $file.FullName", script)


if __name__ == "__main__":
    unittest.main()

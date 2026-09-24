"""Cover the PowerShell helper that discovers the UI scripts to syntax check.

The offline gate checks exactly the modules that ``index.html`` declares, so a
discovery pattern that stops matching would drop the whole UI from the release
gate while still reporting success. These tests run the real helper against
fixtures and pin the invariant that the UI scripts on disk and the scripts
declared by the HTML agree with each other.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER = REPO_ROOT / "tools" / "ui_asset_gate.ps1"
UI_ROOT = REPO_ROOT / "src" / "app" / "ui"
INDEX_HTML = UI_ROOT / "index.html"
STAMP = "?v=__FNAUDIO_ASSET_BUILD__"
SCRIPT_SRC = r'<script\b[^>]*\bsrc="([^"]+)"'


@unittest.skipIf(shutil.which("powershell") is None, "PowerShell is unavailable")
class UiAssetGateTests(unittest.TestCase):
    def discover(self, index_text):
        """Return the helper's stdout, exit code and stderr for one fixture."""
        with tempfile.TemporaryDirectory() as work:
            fixture = Path(work) / "index.html"
            fixture.write_text(index_text, encoding="utf-8")
            command = (
                "$ErrorActionPreference = 'Stop';"
                + " . '" + str(HELPER) + "';"
                + " $text = Get-Content -LiteralPath '" + str(fixture) + "' -Raw -Encoding UTF8;"
                + " @(Get-DeclaredUiScriptPaths -IndexText $text) -join '|'"
            )
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True,
                text=True,
                timeout=180,
            )
        return completed.stdout.strip(), completed.returncode, completed.stderr

    def test_matches_any_attribute_order_and_ignores_the_build_stamp(self):
        index_text = "\n".join([
            '<script src="a.js%s"></script>' % STAMP,
            "<script defer src=" + chr(34) + "b.js" + chr(34) + "></script>",
            '<script src="c.js%s" defer></script>' % STAMP,
            '<script type="text/javascript" src="d.js"></script>',
            '<script src="app.js%s"></script>' % STAMP,
        ])
        output, code, stderr = self.discover(index_text)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(output, "a.js|b.js|c.js|d.js")

    def test_skips_remote_scripts_and_de_dupes_repeats(self):
        index_text = "\n".join([
            '<script src="https://cdn.example/vendor.js"></script>',
            '<script src="//cdn.example/vendor2.js"></script>',
            '<script src="only.js%s"></script>' % STAMP,
            '<script src="only.js"></script>',
        ])
        output, code, stderr = self.discover(index_text)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(output, "only.js")

    def test_rejects_a_declaration_that_escapes_the_ui_root(self):
        output, code, stderr = self.discover('<script src="../app/server/evil.js"></script>')
        self.assertNotEqual(code, 0)
        self.assertIn("outside the UI root", output + stderr)

    def test_empty_html_yields_no_scripts_for_the_gate_to_reject(self):
        output, code, stderr = self.discover("<html><body></body></html>")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(output, "")


class UiDeclarationInvariants(unittest.TestCase):
    """index.html is the only list the release gate trusts, so keep it exact."""

    def declared(self):
        return set(re.findall(SCRIPT_SRC, INDEX_HTML.read_text(encoding="utf-8")))

    def test_every_ui_script_is_declared_in_index(self):
        declared = {src.split("?")[0] for src in self.declared()}
        on_disk = {path.name for path in UI_ROOT.glob("*.js")}
        self.assertEqual(
            sorted(on_disk - declared),
            [],
            "an undeclared UI script ships in the package but escapes every gate",
        )

    def test_app_script_is_declared_last(self):
        """app.js calls its policy modules directly, so every module must precede it.

        The wrappers added for the creator-view and user-media faces use no
        optional chaining, so a script declared after app.js would still pass
        the declaration gate above yet be missing on the first render.
        """
        order = [src.split("?")[0] for src in re.findall(SCRIPT_SRC, INDEX_HTML.read_text(encoding="utf-8"))]
        self.assertTrue(order, "index.html declares no scripts at all")
        self.assertEqual(
            order[-1],
            "app.js",
            "a UI script is declared after app.js, which its unguarded policy calls depend on",
        )

    def test_every_declaration_exists_and_carries_the_build_stamp(self):
        for src in self.declared():
            name, _, query = src.partition("?")
            with self.subTest(script=name):
                self.assertTrue((UI_ROOT / name).is_file(), "declared UI script is missing")
                # A stable URL across releases lets an in-place upgrade serve stale JS.
                self.assertIn("__FNAUDIO_ASSET_BUILD__", query)


if __name__ == "__main__":
    unittest.main()

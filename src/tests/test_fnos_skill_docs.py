"""Structure guards for the repository copy of the fnOS ``trim-cli`` skill.

``tools/skill`` is a vendor tool drop: a WebSocket client for the NAS plus the
markdown that documents every module it speaks to.  The roughly fifty megabytes
of platform binaries stay out of this repository, but the markdown decides how
device behaviour is read and how real-device rounds are run, so it is mirrored
byte for byte under ``references/fnos-skill`` by ``tools/sync_fnos_skill_docs.py``.

The repository already carried an older hand-written copy of part of that
documentation, and it had drifted exactly the way hand copies drift: the
application-centre module documented a third of the commands the tool ships,
four whole modules were missing, and no tracked file linked to it any more.  So
these tests hold three things at once: the mirror must equal the tool, the
documents must cross-link inside the layout that makes those links resolve, and
the superseded hand copy must stay gone.
"""

import importlib.util
from pathlib import Path
import json
import re
import shutil
import sys
import tempfile
import unittest


_MODULE_PATH = Path(__file__).resolve().parents[2] / "tools" / "sync_fnos_skill_docs.py"
_SPEC = importlib.util.spec_from_file_location("fnaudio_sync_fnos_skill_docs", _MODULE_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPO_ROOT / "tools" / "skill"
MIRROR_ROOT = REPO_ROOT / "references" / "fnos-skill"

# Counts the vendor drop ships today.  They are change detectors on purpose:
# when the tool is updated the sync has to be re-run and the record re-filed.
ROOT_DOCUMENTS = ("SKILL.md", "manifest.json")
ENTRY_COUNT = 13
REFERENCE_COUNT = 15
WORKFLOW_COUNT = 6


class FixtureTestCase(unittest.TestCase):
    """Builds a miniature skill drop so the sync logic is testable anywhere."""

    def setUp(self):
        self.workspace = Path(tempfile.mkdtemp(prefix="fnaudio-skill-sync-"))
        self.addCleanup(shutil.rmtree, str(self.workspace), True)
        self.skill = self.workspace / "skill"
        self.mirror = self.workspace / "mirror"
        self._write(self.skill / "SKILL.md", "# skill\n\nsee [app](./reference/app-center.md)\n")
        self._write(self.skill / "manifest.json", '{"name": "trim-cli", "version": "0.1.0"}\n')
        self._write(self.skill / "entries" / "trim-app.md", "read [app centre](../reference/app-center.md)\n")
        self._write(self.skill / "reference" / "app-center.md", "body\n")
        self._write(self.skill / "reference" / "workflows" / "device-validation.md", "steps\n")
        # Everything below exists in a tool drop but must never be mirrored.
        self._write(self.skill / "bin" / "trim-cli-windows-x64.exe", "MZ\x00not a text file\n")
        self._write(self.skill / "scripts" / "trim-cli.ps1", r"& ..\bin")
        self._write(self.skill / "reference" / "notes.txt", "not markdown\n")
        self._write(self.skill / "reference" / "bin" / "hidden.md", "inside an excluded dir\n")

    @staticmethod
    def _write(path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")

    def read(self, path):
        return path.read_text(encoding="utf-8")


class SyncLogicTests(FixtureTestCase):
    def test_only_text_documents_of_the_owned_layout_are_collected(self):
        self.assertEqual(
            _MODULE.relative_paths(str(self.skill)),
            [
                "SKILL.md",
                "entries/trim-app.md",
                "manifest.json",
                "reference/app-center.md",
                "reference/workflows/device-validation.md",
            ],
        )

    def test_compare_reports_each_kind_of_divergence_separately(self):
        self.mirror.mkdir()
        self._write(self.mirror / "SKILL.md", "stale hand edit\n")
        self._write(self.mirror / "reference" / "gone.md", "the tool no longer ships this\n")
        result = _MODULE.compare(str(self.skill), str(self.mirror))
        self.assertEqual(result["missing"], ["entries/trim-app.md", "manifest.json",
                                            "reference/app-center.md",
                                            "reference/workflows/device-validation.md"])
        self.assertEqual(result["changed"], ["SKILL.md"])
        self.assertEqual(result["extra"], ["reference/gone.md"])

    def test_writing_copies_refreshes_and_deletes_and_then_proves_clean(self):
        result = _MODULE.compare(str(self.skill), str(self.mirror))
        _MODULE.apply_diff(str(self.skill), str(self.mirror), result)
        self.assertEqual(self.read(self.mirror / "SKILL.md"), self.read(self.skill / "SKILL.md"))
        after = _MODULE.compare(str(self.skill), str(self.mirror))
        for key in ("missing", "changed", "extra"):
            self.assertEqual(after[key], [], key)

    def test_documents_the_tool_drops_do_not_survive_as_orphans(self):
        self.mirror.mkdir()
        self._write(self.mirror / "reference" / "workflows" / "obsolete.md", "gone upstream\n")
        _MODULE.apply_diff(str(self.skill), str(self.mirror),
                           _MODULE.compare(str(self.skill), str(self.mirror)))
        self.assertFalse((self.mirror / "reference" / "workflows" / "obsolete.md").exists())
        self.assertTrue((self.mirror / "reference" / "workflows" / "device-validation.md").exists())

    def test_the_command_line_exit_codes_distinguish_clean_drift_and_absent_tool(self):
        self.assertEqual(_MODULE.main(["--skill-root", str(self.skill),
                                       "--mirror-root", str(self.mirror), "--write"]), 0)
        self.assertEqual(_MODULE.main(["--skill-root", str(self.skill),
                                       "--mirror-root", str(self.mirror), "--check"]), 0)
        (self.mirror / "manifest.json").write_text('{"version": "tampered"}\n', encoding="utf-8")
        self.assertEqual(_MODULE.main(["--skill-root", str(self.skill),
                                       "--mirror-root", str(self.mirror), "--check"]), 1)
        self.assertEqual(_MODULE.main(["--skill-root", str(self.workspace / "absent"),
                                       "--mirror-root", str(self.mirror), "--check"]), 2)


@unittest.skipUnless(SKILL_ROOT.is_dir(), "the vendor tool drop is not on disk")
class MirrorMatchesToolTests(unittest.TestCase):
    def test_the_committed_mirror_has_drifted_zero_from_the_tool(self):
        result = _MODULE.compare(str(SKILL_ROOT), str(MIRROR_ROOT))
        for key in ("missing", "changed", "extra"):
            self.assertEqual(result[key], [], key)

    def test_the_mirror_excludes_every_binary_and_wrapper(self):
        for path in MIRROR_ROOT.rglob("*"):
            with self.subTest(path=str(path)):
                if path.is_dir():
                    continue
                self.assertIn(path.suffix, (".md", ".json"))
                self.assertNotIn("bin", path.parts)
                self.assertNotIn("scripts", path.parts)
                self.assertLess(path.stat().st_size, 1024 * 1024)


class MirrorLayoutTests(unittest.TestCase):
    def documents(self, *parts):
        root = MIRROR_ROOT.joinpath(*parts)
        return sorted(path.name for path in root.glob("*.md"))

    def test_the_document_set_is_the_shape_the_skill_entries_promise(self):
        for name in ROOT_DOCUMENTS:
            self.assertTrue((MIRROR_ROOT / name).is_file(), name)
        self.assertEqual(len(self.documents("entries")), ENTRY_COUNT)
        self.assertEqual(len(self.documents("reference")), REFERENCE_COUNT)
        self.assertEqual(len(self.documents("reference", "workflows")), WORKFLOW_COUNT)

    def test_every_relative_link_lands_on_a_mirrored_document(self):
        # The tree is mirrored with its layout on purpose: the documents point at
        # each other with ../reference/... and ./entries/..., which only resolves
        # if nothing was flattened.
        pattern = re.compile(r"\]\(([^)\s#]+)(?:#[^)\s]*)?\)")
        checked = 0
        for path in sorted(MIRROR_ROOT.rglob("*.md")):
            for match in pattern.finditer(path.read_text(encoding="utf-8")):
                target = match.group(1)
                if target.startswith(("http://", "https://", "mailto:", "/")):
                    continue
                checked += 1
                resolved = (path.parent / target).resolve()
                self.assertTrue(resolved.is_file(), "%s -> %s" % (path.name, target))
        self.assertGreaterEqual(checked, 50, "the mirror lost its cross links")

    def test_the_vendor_version_travels_with_the_mirror(self):
        manifest = json.loads((MIRROR_ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "trim-cli")
        self.assertTrue(manifest["version"])

    def test_the_superseded_hand_copy_stays_removed(self):
        self.assertFalse((REPO_ROOT / "references" / "SKILL.md").exists())
        self.assertFalse((REPO_ROOT / "references" / "fnos-api").exists())

    def test_the_references_readme_says_where_the_tool_and_mirror_live(self):
        text = (REPO_ROOT / "references" / "README.md").read_text(encoding="utf-8")
        for needle in ("tools/skill", "references/fnos-skill", "sync_fnos_skill_docs.py"):
            self.assertIn(needle, text, needle)


if __name__ == "__main__":
    unittest.main()

"""R110: the takeover comparison itself has to be tested, not re-run by hand.

The rule this tool encodes comes from a real interrupted round: the documents
said one thing, the tree said another, and only comparing
SOURCE_MANIFEST.sha256 with the working tree showed which files had never been
through a gate. So the comparison gets the same treatment as any other helper:
a fixture repo whose mtime and bytes are set on purpose, one assertion per
answer, and one test that runs it against this repository.
"""

import contextlib
from pathlib import Path
import hashlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest


_MODULE_PATH = Path(__file__).resolve().parents[2] / "tools" / "takeover_forensics.py"
_SPEC = importlib.util.spec_from_file_location("fnaudio_takeover_forensics", _MODULE_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_MTIME = 1_700_000_000
NEWER_MTIME = MANIFEST_MTIME + 600
OLDER_MTIME = MANIFEST_MTIME - 60
NL = chr(10)


def paths(root, relative):
    return Path(root) / Path(*relative.split("/"))


def stamp(path, mtime):
    os.utime(path, (mtime, mtime))


def write_file(root, relative, text, mtime=NEWER_MTIME):
    target = paths(root, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(text.encode("utf-8"))
    stamp(target, mtime)
    return target


def digest_of(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def make_manifest(root, entries):
    """Write what the release helper writes: HASH, two spaces, path, CRLF."""
    line_end = chr(13) + chr(10)
    body = line_end.join("%s  %s" % (digest, relative) for digest, relative in entries) + line_end
    manifest = paths(root, "SOURCE_MANIFEST.sha256")
    manifest.write_bytes(body.encode("ascii"))
    stamp(manifest, MANIFEST_MTIME)
    return str(manifest)


class TakeoverForensicsTests(unittest.TestCase):
    LISTED = (
        "src/app/server/mod.py",
        "src/tests/test_mod.py",
        "android-client/app/Main.java",
    )

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.root = self._directory.name
        self.addCleanup(self._directory.cleanup)
        for relative in self.LISTED:
            write_file(self.root, relative, "# seeded" + NL, mtime=OLDER_MTIME)
        entries = [(digest_of(paths(self.root, relative)), relative) for relative in self.LISTED]
        self.manifest = make_manifest(self.root, entries)

    def report(self, **kwargs):
        return _MODULE.inspect_repo(self.root, self.manifest, **kwargs)

    def run_main(self, *extra):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = _MODULE.main(["--repo-root", self.root, "--manifest", self.manifest] + list(extra))
        return code, buffer.getvalue()

    def paths_in(self, group, report):
        return [item["path"] for item in report[group]]

    def test_a_touched_file_with_matching_bytes_is_drift_and_not_stale(self):
        write_file(self.root, "src/app/server/mod.py", "# seeded" + NL)
        report = self.report()
        self.assertEqual(self.paths_in("stale", report), [])
        self.assertEqual(self.paths_in("drift", report), ["src/app/server/mod.py"])
        self.assertEqual(report["unverified"], ["src/app/server/mod.py"])
        self.assertEqual(report["suggested_tests"]["src/app/server/mod.py"][0], "src/tests/test_mod.py")
        code, text = self.run_main()
        self.assertEqual(code, 0, text)
        self.assertTrue("run first: src/app/server/mod.py -> src/tests/test_mod.py" in text)

    def test_rewriting_the_body_makes_the_file_stale_and_fails_the_tool(self):
        write_file(self.root, "src/app/server/mod.py", "# edited" + NL)
        report = self.report()
        self.assertEqual(self.paths_in("stale", report), ["src/app/server/mod.py"])
        self.assertEqual(self.paths_in("drift", report), [])
        code, text = self.run_main("--quiet")
        self.assertEqual(code, 1, text)
        self.assertTrue(text.startswith("listed=3 drift=0 stale=1 unlisted=0"), text)

    def test_only_drifted_files_are_hashed_unless_a_full_sweep_is_asked_for(self):
        write_file(self.root, "src/app/server/mod.py", "# edited" + NL)
        self.assertEqual(self.paths_in("stale", self.report(full=True)), ["src/app/server/mod.py"])
        stamp(paths(self.root, "src/app/server/mod.py"), OLDER_MTIME)
        self.assertEqual(self.paths_in("stale", self.report()), [])
        self.assertEqual(self.paths_in("stale", self.report(full=True)), ["src/app/server/mod.py"])

    def test_a_source_file_the_manifest_never_listed_counts_as_unverified(self):
        write_file(self.root, "src/app/server/fresh.py", "NEW = 1" + NL)
        report = self.report()
        self.assertEqual(report["unlisted"], ["src/app/server/fresh.py"])
        self.assertTrue("src/app/server/fresh.py" in report["unverified"])
        code, _text = self.run_main()
        self.assertEqual(code, 1)

    def test_build_and_cache_junk_never_looks_like_an_unverified_source(self):
        for junk in (
            "src/app/__pycache__/mod.pyc",
            "src/app/build/generated.o",
            "android-client/build/output.apk",
            "android-client/local.properties",
            "android-client/.gradle/caches.lock",
        ):
            write_file(self.root, junk, "junk" + NL)
        self.assertEqual(self.report()["unlisted"], [])
        write_file(self.root, "src/app/server/real.py", "REAL = 1" + NL)
        self.assertEqual(self.report()["unlisted"], ["src/app/server/real.py"])

    def test_a_listed_file_that_disappeared_is_stale_even_after_the_manifest(self):
        paths(self.root, "android-client/app/Main.java").unlink()
        stamp(self.manifest, NEWER_MTIME)
        report = self.report()
        self.assertEqual(self.paths_in("stale", report), ["android-client/app/Main.java"])
        self.assertEqual(self.paths_in("drift", report), [])

    def test_a_manifest_line_without_the_hash_separator_is_rejected(self):
        paths(self.root, "SOURCE_MANIFEST.sha256").write_bytes(
            ("HASH" + chr(32) + "src/app/server/mod.py" + NL).encode("ascii")
        )
        with self.assertRaises(ValueError):
            self.report()

    def test_suggestions_prefer_the_exact_name_and_say_how_many_were_dropped(self):
        write_file(self.root, "src/app/server/mod.py", "# edited" + NL)
        for index in range(14):
            write_file(self.root, "src/tests/test_mod_family_%02d.py" % index, "pass" + NL)
        report = self.report()
        suggested = report["suggested_tests"]["src/app/server/mod.py"]
        self.assertEqual(suggested[0], "src/tests/test_mod.py")
        self.assertEqual(len(suggested), _MODULE.SUGGESTED_TEST_LIMIT)
        self.assertEqual(report["suggested_total"]["src/app/server/mod.py"], 15)

    def test_the_json_answer_is_the_same_report_the_cli_prints(self):
        write_file(self.root, "src/app/server/mod.py", "# edited" + NL)
        code, text = self.run_main("--json")
        self.assertEqual(code, 1)
        payload = json.loads(text)
        self.assertEqual(self.paths_in("stale", payload), ["src/app/server/mod.py"])
        self.assertEqual(payload["listed"], 3)
        self.assertEqual(payload["manifest"], "SOURCE_MANIFEST.sha256")

    def test_the_real_manifest_and_the_real_tree_agree_right_now(self):
        """The live tripwire: a source touched after the manifest was refreshed,
        or a covered source the refresh never picked up, fails the offline gate.
        """
        report = _MODULE.inspect_repo(str(REPO_ROOT))
        self.assertEqual(report["stale"], [], "SOURCE_MANIFEST.sha256 is behind the working tree")
        self.assertEqual(report["unlisted"], [], "a covered source file is missing from SOURCE_MANIFEST.sha256")
        self.assertGreater(report["listed"], 690)
        listed = _MODULE.listed_entries(str(paths(REPO_ROOT, _MODULE.MANIFEST_NAME)))
        self.assertTrue("src/tests/test_takeover_forensics.py" in listed)
        self.assertTrue(listed["src/tests/test_takeover_forensics.py"].isupper())
        self.assertTrue(_MODULE.suggest_tests(str(REPO_ROOT), "src/app/server/library.py"))


if __name__ == "__main__":
    unittest.main()

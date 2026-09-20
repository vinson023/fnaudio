"""R119: two modules under app/server had no production consumer, so they stopped shipping.

TODO L84 recorded that ``src/app/server/alsa_player.py`` and
``src/app/server/playback_session_contract.py`` were loaded by nothing except their own
tests, and that before touching either file a round had to prove whether the fpk
packaging or a device-side script invoked them by name. Three outcomes were allowed:
wire the module back in, move it out of the packaging directory, or delete it together
with its tests.

The evidence (CHANGELOG_AI.md, R119) is that neither name is referenced by a single
production file -- a 400-file reference corpus across ``src/app``, ``src/cmd``,
``src/wizard``, ``src/config``, ``src/manifest``, the top-level ``tools`` scripts and
``android-client/app/src/main``, plus the whole-tree scan and the committed history.
``build_release.ps1`` never names them: it stages ``src`` recursively and asserts only
eight named payload files. Neither module was ever *wired* anywhere, so "wire it back"
would mean inventing a caller, and both files hold work that git cannot restore
(``alsa_player.py`` carries uncommitted changes; the contract is the asset the open
``Android equivalent MediaSession`` items still wait on). So the middle outcome was
taken: the modules moved to ``src/tests/unwired/`` unchanged, byte for byte. That
directory is excluded from the payload by ``/XD tests`` and still hashed by
``tools/update_source_manifest.ps1``.

The assertions stay two-sided. They fail if an unreferenced module reappears under
``app/``, and they fail if the move reached too far: the live ``playback_session_policy``
and ``playback_session_projection`` imports, the packaging exclusions, the manifest
coverage and the manual CLI shape of the moved file all have to survive.
"""

import importlib.util
import os
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = REPO_ROOT / "src" / "app"
TESTS_ROOT = REPO_ROOT / "src" / "tests"
UNWIRED = TESTS_ROOT / "unwired"
BUILD_RELEASE = REPO_ROOT / "tools" / "build_release.ps1"
MANIFEST = REPO_ROOT / "SOURCE_MANIFEST.sha256"
SERVER = APP_ROOT / "server" / "server.py"
RETIRED_NAMES = ("alsa_player.py", "playback_session_contract.py")
RETIRED_STEMS = tuple(Path(name).stem for name in RETIRED_NAMES)
OLD_PATHS = tuple("src/app/server/%s" % name for name in RETIRED_NAMES)
NEW_PATHS = tuple("src/tests/unwired/%s" % name for name in RETIRED_NAMES)
LIVE_SESSION_MODULES = ("playback_session_policy", "playback_session_projection")
SKIP_DIRS = {
    "__pycache__",
    "build",
    ".gradle",
    ".media3-inspect",
    ".idea",
    "node_modules",
    "dist",
    "vendor",
    "apk-analysis",
    "runtime",
}
MAX_CORPUS_FILE_BYTES = 3_000_000


def walk_files(root, top_level_only=False):
    if root.is_file():
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        if top_level_only:
            dirnames[:] = []
        for filename in sorted(filenames):
            yield Path(dirpath) / filename


def reference_corpus():
    """Every file that could plausibly load a packaged module, tests excluded."""
    roots = [APP_ROOT, REPO_ROOT / "src" / "cmd", REPO_ROOT / "src" / "wizard"]
    paths = []
    for root in roots:
        paths.extend(walk_files(root))
    paths.extend(
        path
        for path in walk_files(REPO_ROOT / "tools", top_level_only=True)
        if path.suffix.lower() in {".py", ".ps1", ".sh"}
    )
    paths.append(REPO_ROOT / "src" / "manifest")
    paths.extend(walk_files(REPO_ROOT / "android-client" / "app" / "src" / "main"))
    seen, corpus = set(), []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen or not path.is_file():
            continue
        if path.name.startswith("test_"):
            continue
        if path.stat().st_size > MAX_CORPUS_FILE_BYTES:
            continue
        seen.add(resolved)
        corpus.append(path)
    return corpus


def package_modules():
    return sorted(path for path in walk_files(APP_ROOT) if path.suffix == ".py")


def body(path):
    return path.read_text(encoding="utf-8", errors="replace")


def unreferenced_modules(corpus_bodies, modules):
    orphans = []
    for module in modules:
        if module.stem == "__init__":
            continue
        pattern = re.compile(r"\b%s\b" % re.escape(module.stem))
        module_path = module.resolve()
        if any(
            path != module_path and pattern.search(text)
            for path, text in corpus_bodies.items()
        ):
            continue
        orphans.append(module.relative_to(REPO_ROOT).as_posix())
    return orphans


def load(name, path):
    spec = importlib.util.spec_from_file_location("fnaudio_retired_%s" % name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UnwiredModuleRetirementTests(unittest.TestCase):
    def setUp(self):
        self.corpus = reference_corpus()
        self.bodies = {path.resolve(): body(path) for path in self.corpus}

    def test_the_reference_corpus_reaches_every_loader_that_could_name_a_module(self):
        self.assertGreaterEqual(len(self.corpus), 300)
        required = [
            SERVER,
            APP_ROOT / "ui" / "cgi_proxy.py",
            APP_ROOT / "ui" / "index.cgi",
            REPO_ROOT / "src" / "cmd" / "main",
            REPO_ROOT / "tools" / "build_release.ps1",
        ]
        for path in required:
            self.assertIn(path.resolve(), self.bodies, path)
        for path in self.corpus:
            self.assertFalse(path.name.startswith("test_"), path)
            self.assertNotIn("unwired", path.parts, path)

    def test_no_module_under_the_package_tree_is_left_without_a_consumer(self):
        self.assertEqual(unreferenced_modules(self.bodies, package_modules()), [])

    def test_both_retired_modules_are_out_of_the_packaged_tree(self):
        for relative in OLD_PATHS:
            self.assertFalse((REPO_ROOT / relative).exists(), relative)
        present = {
            path.relative_to(REPO_ROOT).as_posix() for path in package_modules()
        }
        self.assertEqual(present.intersection(OLD_PATHS), set())
        for relative in NEW_PATHS:
            self.assertTrue((REPO_ROOT / relative).is_file(), relative)

    def test_the_moved_alsa_player_is_still_the_manual_cli_it_was(self):
        path = UNWIRED / "alsa_player.py"
        text = body(path)
        self.assertTrue(text.startswith("#!/usr/bin/env python3"), "shebang")
        for live in (
            "import argparse",
            "if __name__ == \"__main__\":",
            "MAX_DEVICE_CHARS",
            "MAX_ALSA_RECOVERY_ATTEMPTS",
        ):
            self.assertIn(live, text)
        compile(text, str(path), "exec")
        for name in ("load_alsa", "write_pcm_buffer", "iter_pcm_chunks", "main"):
            self.assertTrue(re.search(r"^def %s\(" % name, text, re.M), name)

    def test_the_moved_contract_still_declares_the_host_equivalent_protocol(self):
        contract = load("contract", UNWIRED / "playback_session_contract.py")
        for name in (
            "PlaybackParticipant",
            "PlaybackSessionSnapshot",
            "KeepAliveLease",
            "CommandTicket",
        ):
            self.assertTrue(hasattr(contract, name), name)
        self.assertEqual(contract.MAX_COUNTER, 2 ** 31 - 1)
        player = load("player", UNWIRED / "alsa_player.py")
        self.assertEqual(list(player.iter_pcm_chunks(lambda size: b"", 4, 4)), [])
        reads = iter([b"abcdef", b""])
        self.assertEqual(
            list(player.iter_pcm_chunks(lambda size: next(reads), 4, 4)), [b"abcd"]
        )

    def test_the_two_test_modules_follow_their_module_and_not_the_package(self):
        for name in ("test_alsa_player.py", "test_playback_session_contract.py"):
            text = body(TESTS_ROOT / name)
            self.assertIn("unwired", text, name)
            self.assertNotIn('"app" / "server"', text, name)

    def test_packaging_excludes_any_tests_directory_and_still_names_no_retired_file(self):
        script = body(BUILD_RELEASE)
        match = re.search(r"/XD[^\r\n]*", script)
        self.assertIsNotNone(match, "robocopy directory exclusions vanished")
        self.assertIn("tests", match.group(0))
        self.assertIn("__pycache__", match.group(0))
        self.assertIn(
            'if (Test-Path -LiteralPath (Join-Path $payloadRoot "tests"))', script
        )
        self.assertIn("unexpectedly contains test sources", script)
        for stem in RETIRED_STEMS:
            self.assertNotIn(stem, script)

    def test_no_packaging_or_device_script_references_the_retired_names(self):
        offenders = []
        for stem in RETIRED_STEMS:
            pattern = re.compile(r"\b%s\b" % re.escape(stem))
            for path, text in self.bodies.items():
                if pattern.search(text):
                    offenders.append(
                        "%s names %s"
                        % (path.relative_to(REPO_ROOT).as_posix(), stem)
                    )
        self.assertEqual(offenders, [])

    def test_the_live_session_modules_are_untouched_by_the_retirement(self):
        server = body(SERVER)
        for name in LIVE_SESSION_MODULES:
            self.assertRegex(server, r"\b%s\b" % name)
            self.assertTrue((APP_ROOT / "server" / ("%s.py" % name)).is_file(), name)

    def test_the_manifest_hashes_the_new_paths_and_drops_the_old_ones(self):
        listed = {
            line.split("  ", 1)[1]
            for line in MANIFEST.read_text(encoding="ascii").splitlines()
            if "  " in line
        }
        for relative in NEW_PATHS:
            self.assertIn(relative, listed)
        for relative in OLD_PATHS:
            self.assertNotIn(relative, listed)
        self.assertIn("src/tests/unwired/README.md", listed)


if __name__ == "__main__":
    unittest.main()

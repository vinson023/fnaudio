import hashlib
import re
import unittest
from pathlib import Path


# ``tools/update_source_manifest.ps1`` hashes the bytes that are *in the working
# tree*, walking exactly ``src`` and ``android-client`` with the exclusions below.
# ``.gitattributes`` declares ``* text=auto eol=lf``, so a checkout of this
# repository always writes Unix endings -- but a tool that rewrites one of these
# files in place can leave it with CRLF, and ``git diff`` then still reports the
# file as unchanged because git normalises the endings away on read.  The manifest
# is the only thing that notices: it records the CRLF hash, which no fresh checkout
# can reproduce.  R130 measured eight such files and normalised them, so both
# checks below share one walk -- the first keeps the manifest current, the second
# keeps it reproducible.
MANIFEST_SCOPE_ROOTS = ("src", "android-client")
EXCLUDED_SEGMENTS = {".gradle", ".media3-inspect", ".idea", "build", "Python", "__pycache__"}
EXCLUDED_NAMES = {"local.properties"}
EXCLUDED_EXTENSIONS = {".apk", ".aab", ".aar", ".class", ".fpk", ".pyc"}


def manifest_scoped_files(repo_root):
    """Yield ``(relative path, absolute path)`` for every hashed file."""
    for name in MANIFEST_SCOPE_ROOTS:
        for path in (repo_root / name).rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(repo_root).as_posix()
            if any(segment in EXCLUDED_SEGMENTS for segment in relative.split("/")):
                continue
            if path.name in EXCLUDED_NAMES or path.suffix.lower() in EXCLUDED_EXTENSIONS:
                continue
            yield relative, path


class SourceManifestTests(unittest.TestCase):
    def test_root_manifest_matches_authoritative_source_tree(self):
        repo_root = Path(__file__).resolve().parents[2]
        manifest_path = repo_root / "SOURCE_MANIFEST.sha256"
        files = [found for _relative, found in manifest_scoped_files(repo_root)]
        expected = []
        for path in sorted(files, key=lambda value: str(value).lower()):
            digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
            expected.append(f"{digest}  {path.relative_to(repo_root).as_posix()}")
        actual = manifest_path.read_text(encoding="ascii").splitlines()
        self.assertEqual(len(actual), len(set(actual)), "SOURCE_MANIFEST.sha256 contains duplicate records")
        self.assertEqual(sorted(actual), sorted(expected), "SOURCE_MANIFEST.sha256 is stale; run tools/update_source_manifest.ps1")

    def test_the_manifest_rows_are_written_in_ordinal_path_order(self):
        """A culture-dependent row order makes the release manifest shell-dependent."""
        # Sort-Object compares strings with the current culture, and the culture decides
        # where a dot and an underscore fall.  R148 ran the pre-fix tool over one
        # unchanged tree under Windows PowerShell 5.1 and under pwsh 7 - the shell CI
        # uses - and got two orderings of the same 710 records with 117 line positions
        # moved between them.  The guard above compared the rows only as a set, so
        # nothing noticed, while the CI job closes with
        #     git diff --exit-code -- SOURCE_MANIFEST.sha256
        # A refresh from the wrong shell therefore rewrites 117 rows and fails a build
        # whose content is byte-for-byte correct.  Ordinal comparison of the
        # repo-relative path matches git path order and reproduces from any shell, so
        # row order is now part of what this file guarantees.
        repo_root = Path(__file__).resolve().parents[2]
        rows = (repo_root / "SOURCE_MANIFEST.sha256").read_text(encoding="ascii").splitlines()
        self.assertTrue(rows, "SOURCE_MANIFEST.sha256 is empty")
        paths = []
        for row in rows:
            self.assertRegex(row, r"^[0-9A-F]{64}  [^ ]", "manifest row is not HASH  PATH: " + row)
            paths.append(row.split("  ", 1)[1])
        self.assertEqual(
            paths,
            sorted(paths),
            "SOURCE_MANIFEST.sha256 rows are not in ordinal path order; regenerate it with "
            "tools/update_source_manifest.ps1 - a row order that depends on the shell is the "
            "drift that made the manifest non-reproducible",
        )
        script = (repo_root / "tools" / "update_source_manifest.ps1").read_text(encoding="utf-8")
        # The tool explains the defect in a comment that names Sort-Object, so the ban
        # is on the code, not on the prose.
        code = "\n".join(line for line in script.splitlines() if not line.lstrip().startswith("#"))
        self.assertNotIn(
            "Sort-Object",
            code,
            "the manifest tool sorts row order by culture again, which is what made "
            "SOURCE_MANIFEST.sha256 shell-dependent (see the note above)",
        )
        self.assertIn(
            "[StringComparer]::Ordinal",
            script,
            "the manifest tool no longer sorts row order by code point",
        )
    def test_the_guard_walks_the_same_scope_as_the_manifest_tool(self):
        """The scope lists are a copy, so the copy has to be checked against its source."""
        repo_root = Path(__file__).resolve().parents[2]
        script = (repo_root / "tools" / "update_source_manifest.ps1").read_text(encoding="utf-8")
        walk = [line for line in script.splitlines() if "Get-ChildItem -LiteralPath" in line]
        self.assertEqual(len(walk), 1, "the manifest tool's walk is no longer one line")
        self.assertEqual(
            tuple(re.findall(r'Join-Path \$repoRoot "([^"]+)"', walk[0])),
            MANIFEST_SCOPE_ROOTS,
            "the guard and the manifest tool walk different directories",
        )
        for variable, expected in (
            ("excludedSegments", EXCLUDED_SEGMENTS),
            ("excludedNames", EXCLUDED_NAMES),
            ("excludedExtensions", EXCLUDED_EXTENSIONS),
        ):
            declaration = [
                line
                for line in script.splitlines()
                if line.strip().startswith("$" + variable + " = @(")
            ]
            self.assertEqual(len(declaration), 1, variable)
            self.assertEqual(
                set(re.findall(r'"([^"]*)"', declaration[0])),
                set(expected),
                "the guard and the manifest tool exclude different files: " + variable,
            )

    def test_manifest_scoped_text_files_keep_unix_line_endings(self):
        """CRLF in the working tree makes the release manifest unreproducible."""
        repo_root = Path(__file__).resolve().parents[2]
        offenders = []
        scanned = 0
        for relative, found in manifest_scoped_files(repo_root):
            scanned += 1
            payload = found.read_bytes()
            # A NUL byte is the same signal git uses to call a file binary: those
            # payloads (shared libraries, PNGs, JARs) carry carriage returns as
            # data, so their endings are not a line-ending question at all.
            if b"\x00" in payload or b"\r" not in payload:
                continue
            offenders.append(relative)
        # A guard that walks nothing must not report success: the scope lists above
        # are a second copy of the manifest tool's, and drift between the two would
        # otherwise look like a clean run.
        self.assertGreater(
            scanned,
            600,
            "the manifest-scope walk found only %d files; its exclusion lists no "
            "longer match tools/update_source_manifest.ps1" % scanned,
        )
        self.assertEqual(
            offenders,
            [],
            "these files keep Unix endings in git but not on disk, so "
            "SOURCE_MANIFEST.sha256 hashes bytes no checkout produces: %s" % offenders,
        )

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

from pathlib import Path
import json
import re
import unittest


# The recovery manual and the release tools describe the same command line twice, and a
# hand-copied second copy is how a document and its assertions start disagreeing: the
# tool gains a parameter, the test keeps passing, the manual keeps saying nothing about
# it. These helpers read the expectation out of the tool itself (its top-level param()
# block) or out of the authoritative VERSION file, so both kinds of drift fail loudly.
TOP_LEVEL_PARAM_BLOCK = re.compile(r"^param\(\n(.*?)^\)", re.MULTILINE | re.DOTALL)
PARAMETER_DECLARATION = re.compile(r"^\s*\[[A-Za-z][^\]]*\][ \t]*\$([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
RECOVERY_COMMAND_BLOCK = re.compile(r"```powershell\n(.*?)```", re.DOTALL)
PS1_INVOCATION = re.compile(r"tools[\\/]([A-Za-z0-9_.-]+\.ps1)(.*)$")


def script_parameters(root, relative):
    """Return the names in the top-level param() block of a PowerShell helper.

    Only a param() starting at column zero counts, so parameter lists belonging to
    functions inside the script stay out of this contract.
    """
    text = (root / relative).read_text(encoding="utf-8").replace("\r\n", "\n")
    blocks = TOP_LEVEL_PARAM_BLOCK.findall(text)
    assert len(blocks) == 1, relative + " must declare exactly one top-level param() block"
    return PARAMETER_DECLARATION.findall(blocks[0])


def recovery_manual_text(root):
    return (root / "RECOVERY.md").read_text(encoding="utf-8").replace("\r\n", "\n")


def recovery_command_parameters(recovery):
    """Map each script run by a fenced powershell command to its used parameters.

    Tokens before the script path belong to powershell.exe, so only the text after it
    counts as the parameter surface of the tool. Backtick continuations are joined
    first, because the manual splits its longer example across several lines.
    """
    used = {}
    for block in RECOVERY_COMMAND_BLOCK.findall(recovery):
        for line in re.sub(r"`\n[ \t]*", " ", block).splitlines():
            match = PS1_INVOCATION.search(line)
            if match is None:
                continue
            # A switch starts a word; a dash inside a path such as
            # release-evidence-index-latest.json must not be read as one.
            found = set(re.findall(r"(?<![\w.\\/-])-(\w+)", match.group(2)))
            used.setdefault(match.group(1), set()).update(found)
    return used


class OfflineVerificationScriptTests(unittest.TestCase):
    def test_script_runs_the_full_offline_regression_set(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "test_offline.ps1").read_text(encoding="utf-8")
        self.assertIn("unittest discover -s tests -v", script)
        self.assertIn("PYTHONPATH", script)
        self.assertIn("$sourceRoot\\app\\server", script)
        self.assertIn("Remove-Item Env:PYTHONPATH", script)
        # Bytecode caching: -B does not stop a stale in-tree __pycache__ entry
        # from being read, and CPython only compares whole-second mtime and
        # size, so a same-length source edit could be verified against the
        # previous bytecode. The gate must read caches from a throwaway prefix
        # and put the caller's environment back.
        self.assertIn("$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP", script)
        self.assertIn("fnaudio-offline-pycache-", script)
        self.assertIn("Remove-Item Env:PYTHONPYCACHEPREFIX -ErrorAction SilentlyContinue", script)
        # Creating the prefix is only half of the contract: the gate owns that
        # directory and must delete it once the run is over, or every round leaks
        # another compiled tree into %TEMP%. The order checks keep the cleanup past
        # the unittest run and inside the finally that restores the environment.
        self.assertIn("$offlinePycachePrefix = $env:PYTHONPYCACHEPREFIX", script)
        cleanup = script.index("Remove-Item -LiteralPath $offlinePycachePrefix -Recurse -Force")
        self.assertGreater(cleanup, script.index("python -B -m unittest discover"))
        self.assertLess(cleanup, script.index("Pop-Location"))
        self.assertIn('Invoke-NodeSyntaxCheck "app\\ui\\app.js"', script)
        self.assertIn("function Invoke-NodeSyntaxCheck", script)
        # A hand-maintained per-file list silently skips a newly split UI module,
        # so the gate now discovers every module straight from index.html through a
        # shared helper whose pattern tolerates any attribute order.
        self.assertIn(". (Join-Path $PSScriptRoot \"ui_asset_gate.ps1\")", script)
        self.assertIn("Get-DeclaredUiScriptPaths -IndexText $indexText", script)
        self.assertIn("the Node syntax gate lost its discovery list", script)
        self.assertNotIn("[regex]::Matches($indexText", script)
        self.assertNotIn('Invoke-NodeSyntaxCheck "app\\ui\\library_page_merge.js"', script)
        self.assertNotIn("node --check app\\ui\\library_page_merge.js\n    node --check", script)
        self.assertIn("declaredScripts", script)
        self.assertIn("JavaScript syntax check failed: $Label", script)
        self.assertIn('Invoke-NodeSyntaxCheck (Join-Path "app\\ui" $script)', script)
        self.assertIn('Get-ChildItem -LiteralPath "tests" -Filter "test_*.js" -File', script)
        self.assertIn("Node regression failed: $($test.Name)", script)
        self.assertIn("[System.Management.Automation.Language.Parser]::ParseFile", script)
        self.assertIn('Get-ChildItem -LiteralPath $PSScriptRoot -Filter "*.ps1" -File', script)
        self.assertIn("PowerShell syntax check failed:", script)
        self.assertIn("git diff --check", script)
        self.assertIn("build_release.ps1", script)

    def test_release_verifier_supports_strict_recovery_mode(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "verify_release_evidence.ps1").read_text(encoding="utf-8")
        self.assertIn("RequireCompleteEvidence", script)
        self.assertIn("Complete release evidence is required", script)

    def test_release_verifier_rejects_half_complete_source_evidence(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "verify_release_evidence.ps1").read_text(encoding="utf-8")
        self.assertIn("manifestPresent", script)
        self.assertIn("provenancePresent", script)
        self.assertIn("must be present together", script)

    def test_release_index_is_bounded_and_machine_readable(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "index_release_evidence.ps1").read_text(encoding="utf-8")
        self.assertIn("MaxEntries", script)
        self.assertIn("ValidateRange(1, 256)", script)
        self.assertIn("List[object]", script)
        self.assertIn("$directories.RemoveAt($directories.Count - 1)", script)
        self.assertIn("if ($_.Name -notmatch", script)
        self.assertIn("^\\d+\\.\\d+\\.\\d+$", script)
        self.assertIn("[version]$_.Name", script)
        self.assertIn("$directories.Insert($position, $entry)", script)
        self.assertIn("verify_release_evidence.ps1", script)
        self.assertIn("-Json", script)
        self.assertIn("entry_count", script)
        self.assertIn("source_manifest_sha256", script)
        self.assertIn("Get-FileHash", script)
        self.assertIn("Security.Cryptography.SHA256", script)
        self.assertIn("Get-Command -Name Get-FileHash", script)
        self.assertIn("$scriptRoot = if ($PSScriptRoot)", script)
        self.assertIn("if (-not $ArtifactRoot)", script)
        self.assertIn("tools\\verify_release_evidence.ps1", script)
        self.assertIn("OutputPath", script)
        self.assertIn("Move-Item -LiteralPath $temporaryOutput", script)
        self.assertIn('recovery_note = "Validation failed"', script)
        self.assertIn("Get-BoundedArtifactName", script)
        self.assertIn("Get-BoundedSha256", script)
        self.assertIn("Get-BoundedRecoveryNote", script)
        self.assertIn("Get-BoundedBoolean", script)
        self.assertIn("android_validated", script)
        self.assertIn("^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$", script)
        self.assertIn("^[0-9a-f]{64}$", script)
        self.assertIn("$text.Length -gt 512", script)

    def test_release_verifier_bounds_checksum_record_before_reading(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "verify_release_evidence.ps1").read_text(encoding="utf-8")
        self.assertIn("SHA256SUMS exceeds the 64 KiB evidence limit", script)
        self.assertIn("$shaFile.Length -gt 64KB", script)
        self.assertIn("$shaLines.Count -gt 128", script)

    def test_release_verifier_bounds_artifact_before_hashing(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "verify_release_evidence.ps1").read_text(encoding="utf-8")
        self.assertIn("$recordFile.Length -gt $MaxArtifactBytes", script)
        self.assertIn("Release artifact exceeds the $MaxArtifactBytes byte artifact limit", script)
        self.assertIn("$androidArtifact.Length -gt $MaxAndroidArtifactBytes", script)
        # The purpose of these guards is that a huge artifact is never read, so
        # their *position* relative to the hashing calls is the contract.  Text
        # presence alone would keep passing if somebody moved the check after the
        # hash.
        self.assertLess(script.index("$recordFile.Length -gt $MaxArtifactBytes"),
                        script.index("$recordHash = Get-Sha256Hex -Path $recordPath"))
        self.assertLess(script.index("$androidArtifact.Length -gt $MaxAndroidArtifactBytes"),
                        script.index("Get-Sha256Hex -Path $androidArtifactPath"))
        # The ceilings are injectable so a test can exercise them in bytes; the
        # defaults remain the release policy, and the limits are validated before
        # any artifact is opened.
        self.assertIn("[long]$MaxArtifactBytes = 10GB", script)
        self.assertIn("[long]$MaxAndroidArtifactBytes = 1GB", script)
        self.assertIn("if ($MaxArtifactBytes -lt 1 -or $MaxAndroidArtifactBytes -lt 1)", script)
        self.assertLess(script.index('$MaxArtifactBytes -lt 1'),
                        script.index("foreach ($record in $checksumRecords)"))

    def test_release_verifier_rejects_a_non_directory_artifact_path(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "verify_release_evidence.ps1").read_text(encoding="utf-8")
        self.assertIn("Test-Path -LiteralPath $resolvedArtifact.Path -PathType Container", script)
        self.assertIn("Release evidence path must be a directory", script)

    def test_release_verifier_binds_artifact_name_to_provenance_version(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "verify_release_evidence.ps1").read_text(encoding="utf-8")
        self.assertIn("provenance.version", script)
        self.assertIn("expectedArtifactName", script)
        self.assertIn("does not match provenance version", script)

    def test_release_verifier_binds_manifest_count_and_asset_build_to_provenance(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "verify_release_evidence.ps1").read_text(encoding="utf-8")
        self.assertIn("staged file count does not match SOURCE_MANIFEST.sha256", script)
        self.assertIn("Get-StrictJsonInteger", script)
        self.assertIn("-is [bool]", script)
        self.assertIn("invalid UI asset build", script)
        self.assertIn("UI asset build does not match its version", script)

    def test_release_verifier_rejects_rooted_and_traversal_manifest_paths(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "verify_release_evidence.ps1").read_text(encoding="utf-8")
        self.assertIn("IsPathRooted", script)
        self.assertIn("contains '..'", script)
        self.assertIn("unsafe path", script)

    def test_release_verifier_can_rebind_manifest_to_a_source_directory(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "verify_release_evidence.ps1").read_text(encoding="utf-8")
        # The parameter is named by the tool itself through its param() block rather than
        # copied into this test, so renaming or dropping the rebinding switch fails here
        # instead of quietly retiring a capability the release procedure assumes.
        self.assertIn(
            "SourceDirectory",
            script_parameters(root, "tools/verify_release_evidence.ps1"),
        )
        self.assertIn("names a missing source file", script)
        self.assertIn("SOURCE_MANIFEST.sha256 hash mismatch", script)

    def test_recovery_manual_baseline_follows_the_version_file(self):
        root = Path(__file__).resolve().parents[2]
        recovery = recovery_manual_text(root)
        current = (root / "VERSION").read_text(encoding="utf-8").strip()
        # The manual may state a baseline exactly once, and that statement has to come
        # from VERSION. Copying the number into this test is what let the sentence rot
        # into a second, older record of the version every time VERSION moved.
        self.assertEqual(
            re.findall(r"当前源码基线为 `([^`]*)`", recovery),
            [current],
            "RECOVERY.md must state the current baseline exactly once",
        )
        self.assertNotIn("当前配套版本为", recovery)

    def test_generated_release_index_is_semver_descending_and_bounded(self):
        root = Path(__file__).resolve().parents[2]
        index = root / "artifacts" / "release-evidence-index-latest.json"
        if not index.is_file():
            self.skipTest("release evidence index is not present in this checkout")
        payload = json.loads(index.read_text(encoding="utf-8-sig"))
        self.assertEqual(payload.get("schema"), 1)
        releases = payload.get("releases", [])
        self.assertLessEqual(len(releases), int(payload.get("entry_limit", 256)))
        versions = [tuple(int(part) for part in str(row["directory"]).split(".")) for row in releases]
        self.assertEqual(versions, sorted(versions, reverse=True))
        expected_latest = (root / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(releases[0]["directory"], expected_latest)
        self.assertRegex(str(payload.get("source_manifest_sha256", "")), r"^[0-9a-f]{64}$")
        self.assertIn("android_validated", releases[0])

    def test_recovery_manual_documents_the_parameters_of_the_tools_it_runs(self):
        root = Path(__file__).resolve().parents[2]
        recovery = recovery_manual_text(root)
        invocations = recovery_command_parameters(recovery)
        # A manual whose fenced commands all disappeared would make both loops below
        # pass by saying nothing, so the inventory itself is part of the assertion.
        self.assertGreaterEqual(
            len(invocations), 3, "the recovery commands are no longer in the manual"
        )
        for script_name, used_parameters in sorted(invocations.items()):
            declared = script_parameters(root, "tools/" + script_name)
            self.assertTrue(
                declared, script_name + " declares no parameters; the param() parser broke"
            )
            # Every switch the recovery flow can reach has to be explained somewhere in
            # the manual, so adding a parameter to a recovery tool cannot ship as an
            # undocumented part of the restore procedure.
            for parameter in declared:
                self.assertIn(
                    "-" + parameter,
                    recovery,
                    "tools/%s exposes -%s, which the recovery manual never mentions"
                    % (script_name, parameter),
                )
            # And the manual must not advertise a switch the tool stopped accepting.
            for parameter in sorted(used_parameters):
                self.assertIn(
                    parameter, declared,
                    "the manual runs tools/%s with -%s, which that script does not accept"
                    % (script_name, parameter),
                )

    def test_recovery_manual_shows_how_to_persist_the_release_index(self):
        root = Path(__file__).resolve().parents[2]
        recovery = recovery_manual_text(root)
        invocations = recovery_command_parameters(recovery)
        declared = script_parameters(root, "tools/index_release_evidence.ps1")
        # The scan is only a recovery attachment if the manual shows the switch that
        # writes it. The name is taken from the script, so a rename is caught by both
        # sides of the contract rather than leaving a command nobody can run.
        self.assertIn("OutputPath", declared)
        self.assertIn("OutputPath", invocations.get("index_release_evidence.ps1", set()))


    def test_whitespace_check_names_a_missing_repository_separately(self):
        """The whitespace step must not be able to blame the tree for the checkout.

        round274 turned the whole gate red on a clean tree: on a UNC-mapped
        checkout the ownership check makes git print its usage text instead of a
        diff, and a bare `git diff --check` reports that the same way a real
        trailing-space finding does. The law is therefore about the two failure
        modes, not the command name: a repository probe has to run first, it has to
        fail with its own message, and the trust override has to name this checkout
        instead of every path on the machine.
        """
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "test_offline.ps1").read_text(encoding="utf-8")
        probe = script.index("rev-parse --show-toplevel")
        checked = script.index("diff --check")
        self.assertLess(probe, checked, "the repository probe must run before the whitespace check")
        self.assertIn(
            "git cannot read the repository at $projectRoot", script,
            "an unreadable checkout must be reported as itself, not as a whitespace failure",
        )
        self.assertIn(
            "git diff --check failed", script,
            "a real whitespace finding must keep its own message",
        )
        self.assertIn(chr(34) + "safe.directory=$projectRoot" + chr(34), script)
        # The scope has to reach the diff itself: a probe that is trusted while the
        # whitespace call stays bare reproduces the round274 abort verbatim.
        self.assertIn("git @gitScope diff --check", script)
        self.assertNotIn("safe.directory=*", script, "trusting every path turns a gate fix into a policy change")


if __name__ == "__main__":
    unittest.main()

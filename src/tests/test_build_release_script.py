from pathlib import Path
import base64
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unittest


class _ScenarioResult:
    """The three facts a fresh `powershell -File` run used to expose to these tests."""

    def __init__(self, returncode, stdout, stderr):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


# One interpreter start for several verifier scenarios.  Starting `powershell.exe` costs
# ~0.94 s on this host while the script's own work costs ~0.45 s, and this module used to
# pay the start eighteen separate times.  Each scenario still runs
# `verify_release_evidence.ps1` end to end, in order, and a `throw` inside one scenario is
# reported for that scenario alone, so no rejection reason is folded into another.
# Fixture changes between scenarios are declared as `pre` writes (base64 bytes, or
# `delete`) rather than mutated from Python, which is what makes the order explicit.
_SCENARIO_DRIVER = r'''
param([Parameter(Mandatory = $true)][string]$Verifier,
      [Parameter(Mandatory = $true)][string]$ScenarioFile)
$index = -1
foreach ($line in Get-Content -LiteralPath $ScenarioFile) {
    if (-not $line.Trim()) { continue }
    $index = $index + 1
    $scenario = $line | ConvertFrom-Json
    foreach ($write in @($scenario.pre)) {
        if ($null -eq $write) { continue }
        $target = [IO.Path]::GetFullPath([string]$write.path)
        $parent = Split-Path -Parent $target
        if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent | Out-Null }
        if ($write.delete) {
            if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Force }
            continue
        }
        [IO.File]::WriteAllBytes($target, [Convert]::FromBase64String([string]$write.bytes))
    }
    $splat = [ordered]@{}
    foreach ($property in $scenario.args.PSObject.Properties) {
        $splat[[string]$property.Name] = $property.Value
    }
    $report = [ordered]@{ marker = 'fnaudio-scenario'; index = $index; returncode = 0; stdout = ''; stderr = '' }
    try {
        $report.stdout = (& $Verifier @splat 2>&1 | Out-String -Width 4096)
    } catch {
        $report.returncode = 1
        $report.stderr = [string]$_.Exception.Message
    }
    (ConvertTo-Json -InputObject $report -Compress -Depth 4)
}
'''


class BuildReleaseScriptTests(unittest.TestCase):
    @staticmethod
    def _powershell():
        return shutil.which("powershell.exe") or shutil.which("powershell") or shutil.which("pwsh")

    def _run_evidence_verifiers(self, scenarios):
        """Run ``[{"args": {...}, "pre": [(path, bytes | None)]}, ...]`` in one process."""
        powershell = self._powershell()
        if not powershell:
            self.skipTest("PowerShell is required to exercise the release evidence verifier")
        verifier = str(Path(__file__).resolve().parents[2] / "tools" / "verify_release_evidence.ps1")
        spec = []
        for scenario in scenarios:
            spec.append(json.dumps({
                "args": dict(scenario.get("args", {})),
                "pre": [
                    {"path": str(path),
                     "bytes": base64.b64encode(payload).decode("ascii") if payload is not None else None,
                     "delete": payload is None}
                    for path, payload in scenario.get("pre", ())
                ],
            }))
        with tempfile.TemporaryDirectory() as temporary:
            driver = Path(temporary) / "scenarios.ps1"
            driver.write_text(_SCENARIO_DRIVER, encoding="ascii")
            scenario_file = Path(temporary) / "scenarios.jsonl"
            scenario_file.write_text("\n".join(spec) + "\n", encoding="utf-8")
            process = subprocess.run(
                [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(driver),
                 "-Verifier", verifier, "-ScenarioFile", str(scenario_file)],
                text=True, errors="replace", capture_output=True, check=False, timeout=30 + 30 * len(scenarios),
            )
        results = []
        for line in (process.stdout or "").splitlines():
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except ValueError:
                continue
            if payload.get("marker") != "fnaudio-scenario":
                continue
            results.append((payload.get("index"), _ScenarioResult(payload.get("returncode"),
                                                                  payload.get("stdout", ""),
                                                                  payload.get("stderr", ""))))
        if len(results) != len(scenarios):
            # A driver that quietly produced fewer scenarios would otherwise let a test
            # assert about the wrong run, so the mismatch is the failure.
            raise AssertionError("scenario driver returned %d of %d runs: %s" % (
                len(results), len(scenarios), ((process.stdout or "") + (process.stderr or ""))[:400]))
        if [index for index, _result in results] != list(range(len(scenarios))):
            # The order is part of the contract: a scenario's `pre` writes build on the
            # previous one, so a report that arrives shuffled would be attributed to the
            # wrong assertion while every individual message still looks plausible.
            raise AssertionError("scenario driver reported indexes %s for %d scenarios" % (
                [index for index, _result in results], len(scenarios)))
        return [result for _index, result in results]

    def _run_evidence_verifier(self, directory, strict=False, extra=()):
        args = {"ArtifactDirectory": str(directory)}
        if strict:
            args["RequireCompleteEvidence"] = True
        pairs = iter(extra)
        for name in pairs:
            args[str(name).lstrip("-")] = next(pairs, True)
        return self._run_evidence_verifiers([{"args": args}])[0]

    def test_release_script_rejects_a_real_existing_publication_before_invoking_fnpack(self):
        """Exercise the collision gate against the real script, not a text fixture."""
        powershell = self._powershell()
        if not powershell:
            self.skipTest("PowerShell is required to exercise the release collision gate")
        root = Path(__file__).resolve().parents[2]
        version = (root / "VERSION").read_text(encoding="utf-8").strip()
        artifact_name = f"fnaudio-{version}-fnpack.fpk"
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            output_root = temporary_root / "artifacts"
            destination = output_root / version
            destination.mkdir(parents=True)
            (destination / artifact_name).write_bytes(b"existing publication")
            fake_fnpack = temporary_root / "must-not-run.fnpack"
            fake_fnpack.write_bytes(b"not executable")
            result = subprocess.run(
                [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                 str(root / "tools" / "build_release.ps1"),
                 "-OutputRoot", str(output_root), "-FnpackPath", str(fake_fnpack)],
                text=True, errors="replace", capture_output=True, check=False, timeout=30,
            )
            self.assertNotEqual(result.returncode, 0)
            output = (result.stdout or "") + (result.stderr or "")
            self.assertIn("Release output already exists", output)
            self.assertIn("Refusing to overwrite", output)

    def test_release_evidence_verifier_exercises_complete_fixture_and_detects_tampering(self):
        """Use real files so recovery checks cannot regress into text-only contracts."""
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            artifact = directory / "fnaudio-9.8.7-fnpack.fpk"
            artifact.write_bytes(b"fixture fpk bytes")
            artifact_hash = hashlib.sha256(artifact.read_bytes()).hexdigest().upper()
            (directory / "SHA256SUMS").write_text(
                f"{artifact_hash}  {artifact.name}\n", encoding="ascii"
            )
            manifest = directory / "SOURCE_MANIFEST.sha256"
            manifest.write_text(
                f"{hashlib.sha256(b'source').hexdigest()}  app/server/example.py\n",
                encoding="ascii",
            )
            manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest().upper()
            provenance = {
                "schema": 1,
                "version": "9.8.7",
                "asset_build": "9.8.7-0123456789ab",
                "staged_file_count": 1,
                "source_manifest_sha256": manifest_hash,
                "artifact_sha256": artifact_hash,
                "fnpack_sha256": "a" * 64,
            }
            (directory / "SOURCE_PROVENANCE.json").write_text(
                json.dumps(provenance), encoding="utf-8"
            )

            provenance_path = directory / "SOURCE_PROVENANCE.json"
            tampered_count = dict(provenance, staged_file_count=2)
            boolean_count = dict(provenance, staged_file_count=True)
            verified, rejected, rejected_boolean = self._run_evidence_verifiers([
                {"args": {"ArtifactDirectory": str(directory), "RequireCompleteEvidence": True}},
                {"args": {"ArtifactDirectory": str(directory), "RequireCompleteEvidence": True},
                 "pre": [(provenance_path, json.dumps(tampered_count).encode("utf-8"))]},
                {"args": {"ArtifactDirectory": str(directory), "RequireCompleteEvidence": True},
                 "pre": [(provenance_path, json.dumps(boolean_count).encode("utf-8"))]},
            ])
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertIn("EvidenceComplete", verified.stdout)
            self.assertIn("True", verified.stdout)

            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("staged file count does not match", rejected.stderr)

            self.assertNotEqual(rejected_boolean.returncode, 0)
            self.assertIn("invalid staged file count", rejected_boolean.stderr)

    def test_release_evidence_verifier_checks_checksum_and_provenance(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "verify_release_evidence.ps1").read_text(encoding="utf-8")

        for expected in (
            'SHA256SUMS',
            'SOURCE_MANIFEST.sha256',
            'SOURCE_PROVENANCE.json',
            'function Get-Sha256Hex',
            'function Get-StrictJsonInteger',
            'Get-FileHash -LiteralPath $Path -Algorithm SHA256',
            'Security.Cryptography.SHA256',
            'Get-Sha256Hex -Path $recordPath',
            'source_manifest_sha256',
            'artifact_sha256',
            'fnpack_sha256',
            'EvidenceComplete',
            'Legacy artifact',
            'must contain exactly one FPK checksum record',
            'contains duplicate artifact records',
            'contains an invalid checksum record',
            'Artifact SHA-256 does not match SHA256SUMS:',
            "(?<name>[A-Za-z0-9][A-Za-z0-9._-]{0,254})",
            'contains duplicate records',
            'contains duplicate paths',
            'ToLowerInvariant',
            'IsNullOrWhiteSpace($relativeManifestPath)',
            '$relativeManifestPath.Length -gt 4096',
            '$segments -contains \'\'',
            '$segments -contains \'.\'',
            '$relativeManifestPath = ($Matches.path -replace',
            '$manifestHash = Get-Sha256Hex -Path $manifestPath',
            '$manifestFile.Length -gt 64MB',
            '$recordFile.Length -gt $MaxArtifactBytes',
            'Release artifact exceeds the $MaxArtifactBytes byte artifact limit:',
            '[long]$MaxArtifactBytes = 10GB',
            '[long]$MaxAndroidArtifactBytes = 1GB',
            '$provenanceFile.Length -gt 1MB',
            'SOURCE_PROVENANCE.json exceeds the 1 MiB evidence limit',
            'SOURCE_PROVENANCE.json must contain a JSON object.',
            'exceeds the 200000-record evidence limit',
            'unsupported schema',
            'staged file count does not match SOURCE_MANIFEST.sha256',
            'invalid $FieldName',
            'invalid UI asset build',
            'UI asset build does not match its version',
            '[switch]$Json',
            'ConvertTo-Json -Depth 4 -Compress',
            'if ($Json)',
        ):
            self.assertIn(expected, script)

    def test_build_script_supports_hash_fallback_on_minimal_powershell(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "build_release.ps1").read_text(encoding="utf-8")
        self.assertIn("function Get-Sha256Hex", script)
        self.assertIn("Get-Command -Name Get-FileHash", script)
        self.assertIn("Security.Cryptography.SHA256", script)
        self.assertNotIn("$fnpackSha256 = (Get-FileHash", script)

    def test_release_evidence_verifier_supports_machine_readable_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            artifact = directory / "fnaudio-9.8.7-fnpack.fpk"
            artifact.write_bytes(b"fixture fpk bytes")
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest().upper()
            (directory / "SHA256SUMS").write_text(f"{digest}  {artifact.name}\n", encoding="ascii")
            verified, json_result = self._run_evidence_verifiers([
                {"args": {"ArtifactDirectory": str(directory)}},
                {"args": {"ArtifactDirectory": str(directory), "Json": True}},
            ])
            self.assertEqual(verified.returncode, 0, verified.stderr)

            self.assertEqual(json_result.returncode, 0, json_result.stderr)
            payload = json.loads(json_result.stdout)
            self.assertTrue(payload["Validated"])
            self.assertEqual(payload["Artifact"], artifact.name)
            self.assertFalse(payload["EvidenceComplete"])

    def test_release_evidence_verifier_accepts_and_checks_android_sidecar_checksum(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            artifact = directory / "fnaudio-9.8.7-fnpack.fpk"
            android = directory / "fnaudio-android-9.8.7-debug.apk"
            artifact.write_bytes(b"fixture fpk bytes")
            android.write_bytes(b"fixture apk bytes")
            artifact_hash = hashlib.sha256(artifact.read_bytes()).hexdigest().upper()
            android_hash = hashlib.sha256(android.read_bytes()).hexdigest().upper()
            (directory / "SHA256SUMS").write_text(
                f"{artifact_hash}  {artifact.name}\n{android_hash}  {android.name}\n",
                encoding="ascii",
            )

            verified, rejected = self._run_evidence_verifiers([
                {"args": {"ArtifactDirectory": str(directory)}},
                {"args": {"ArtifactDirectory": str(directory)},
                 "pre": [(android, b"tampered apk bytes")]},
            ])
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertIn("Legacy artifact", verified.stdout)

            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("fnaudio-android-9.8.7-debug.apk", rejected.stderr)

    def test_release_evidence_verifier_checks_android_release_sidecar(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            artifact = directory / "fnaudio-9.8.7-fnpack.fpk"
            android = directory / "fnaudio-android-9.8.7-release.apk"
            artifact.write_bytes(b"fixture fpk bytes")
            android.write_bytes(b"fixture release apk bytes")
            artifact_hash = hashlib.sha256(artifact.read_bytes()).hexdigest().upper()
            android_hash = hashlib.sha256(android.read_bytes()).hexdigest().upper()
            (directory / "SHA256SUMS").write_text(
                f"{artifact_hash}  {artifact.name}\n", encoding="ascii"
            )
            (directory / "ANDROID_SHA256SUMS").write_text(
                f"{android_hash}  {android.name}\n", encoding="ascii"
            )

            verified, rejected = self._run_evidence_verifiers([
                {"args": {"ArtifactDirectory": str(directory)}},
                {"args": {"ArtifactDirectory": str(directory)},
                 "pre": [(android, b"tampered release apk bytes")]},
            ])
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertIn("AndroidValidated", verified.stdout)
            self.assertRegex(verified.stdout, r"AndroidValidated\s*: True")

            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("ANDROID_SHA256SUMS", rejected.stderr)

    def test_release_evidence_index_bounds_untrusted_verifier_json_fields(self):
        powershell = self._powershell()
        if not powershell:
            self.skipTest("PowerShell is required to exercise the release evidence index")
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            tools = temporary_root / "tools"
            artifacts = temporary_root / "artifacts"
            tools.mkdir()
            (artifacts / "9.8.7").mkdir(parents=True)
            shutil.copy2(root / "tools" / "index_release_evidence.ps1", tools / "index_release_evidence.ps1")
            (tools / "verify_release_evidence.ps1").write_text(
                """param([string]$ArtifactDirectory, [switch]$Json)
$payload = [pscustomobject]@{
    Validated = $true
    EvidenceComplete = $true
    Artifact = '../unsafe.fpk'
    SHA256 = 'not-a-sha256'
    RecoveryNote = ('x' * 513) + "`nignored"
}
$payload | ConvertTo-Json -Compress
""",
                encoding="utf-8",
            )
            output = temporary_root / "index.json"
            indexed = subprocess.run(
                [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                 str(tools / "index_release_evidence.ps1"),
                 "-ArtifactRoot", str(artifacts), "-OutputPath", str(output)],
                text=True, errors="replace", capture_output=True, check=False, timeout=15,
            )
            self.assertEqual(indexed.returncode, 0, indexed.stderr)
            payload = json.loads(output.read_text(encoding="utf-8-sig"))
            row = payload["releases"][0]
            self.assertTrue(row["validated"])
            self.assertFalse(row["android_validated"])
            self.assertTrue(row["evidence_complete"])
            self.assertEqual(row["artifact"], "")
            self.assertEqual(row["sha256"], "")
            self.assertEqual(len(row["recovery_note"]), 512)
            self.assertNotIn("\n", row["recovery_note"])
            self.assertFalse(row["android_validated"])

    def test_release_evidence_verifier_rejects_half_complete_source_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            artifact = directory / "fnaudio-9.8.7-fnpack.fpk"
            artifact.write_bytes(b"fixture fpk bytes")
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest().upper()
            (directory / "SHA256SUMS").write_text(f"{digest}  {artifact.name}\n", encoding="ascii")
            (directory / "SOURCE_MANIFEST.sha256").write_text(
                f"{hashlib.sha256(b'source').hexdigest()}  app/server/example.py\n",
                encoding="ascii",
            )
            rejected = self._run_evidence_verifier(directory)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("must be present together", rejected.stderr)

    def test_script_uses_a_temporary_copy_of_the_authoritative_source_tree(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "build_release.ps1").read_text(encoding="utf-8")

        self.assertIn('Join-Path $repoRoot "src"', script)
        self.assertIn('& $FnpackPath build --directory $stageRoot', script)
        self.assertIn('/XD tests __pycache__ /XF fnaudio.fpk *.pyc', script)
        self.assertIn('Remove-Item -LiteralPath $temporaryRoot -Recurse -Force', script)

    def test_release_script_treats_any_existing_artifact_path_as_a_collision(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "build_release.ps1").read_text(encoding="utf-8")
        self.assertIn("$publicationNames", script)
        self.assertIn("$publicationName", script)
        self.assertIn("if (Test-Path -LiteralPath $publicationPath)", script)
        self.assertNotIn("Test-Path -LiteralPath $artifactPath -PathType Leaf", script)

    def test_release_script_treats_existing_evidence_sidecars_as_collisions_and_rolls_back_publish(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "build_release.ps1").read_text(encoding="utf-8")
        for expected in (
            '"SHA256SUMS"',
            '"SOURCE_MANIFEST.sha256"',
            '"SOURCE_PROVENANCE.json"',
            '$publicationNames',
            'if (Test-Path -LiteralPath $publicationPath)',
            '$publishedPaths = [System.Collections.Generic.List[string]]::new()',
            '$publicationBackups = [System.Collections.Generic.List[object]]::new()',
            'if ($AllowExistingArtifact)',
            'previous-publication',
            'Copy-Item -LiteralPath $publicationBackup.Backup -Destination $publicationBackup.Original -Force',
            'catch {',
            'Remove-Item -LiteralPath $publishedPath -Force -ErrorAction SilentlyContinue',
        ):
            self.assertIn(expected, script)

    def test_staged_manifest_normalizes_windows_path_separators(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "build_release.ps1").read_text(encoding="utf-8")

        self.assertIn('.Replace("\\", "/")', script)
        self.assertNotIn('.Replace("\\\\", "/")', script)

    def test_script_checks_all_release_version_surfaces_and_the_payload(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "build_release.ps1").read_text(encoding="utf-8")

        for expected in (
            'src/manifest',
            'src/app/server/server.py',
            'src/app/server/version.py',
            'src/app/ui/index.html',
            'android-client/app/build.gradle',
            'must define a positive integer versionCode',
            'versionCode must be positive',
            'Packaged manifest version differs from VERSION.',
            'packaged server/server.py',
            'packaged server/version.py',
            'packaged ui/index.html',
            'FPK payload unexpectedly contains test sources.',
            '__FNAUDIO_ASSET_BUILD__',
            'content-derived cache key',
            'Get-StampedUiAssetPaths',
            'Staged UI asset set differs from the authoritative index.html.',
            'Packaged stamped UI asset',
            'has no stamped local CSS/JS assets',
            'without the build stamp: $relative',

            'SOURCE_MANIFEST.sha256',
            'SOURCE_PROVENANCE.json',
            'Get-SourceManifestLines',
            'Get-GitProvenance',
            'staged_file_count',
            'source_manifest_sha256',
            'fnpack_sha256',
            'artifact_sha256',
            'Release SHA256SUMS does not match the final FPK.',
            'git_provenance_status',
            '--untracked-files=no -- $Scope',
            '--exclude-standard -- $Scope',
            'git_provenance_scope = ($gitProvenance.scope',
            '"commit_only"',
            '"unavailable"',
            'invalid Git provenance status',
            'Get-Sha256Hex -Path $FnpackPath',
            "TrimEnd([char]'\\', [char]'/' )",
            'AllowExistingArtifact',
            'Refusing to overwrite',
            '(Get-Item -LiteralPath $builtPackage).Length -gt 10GB',
            'Built FPK exceeds the 10 GiB artifact limit.',
            '$packageStream = [System.IO.File]::OpenRead($temporaryArtifactPath)',
            '$packageStream.Read($packageHeader, 0, $packageHeader.Length)',
            '$publishRoot = Join-Path $temporaryRoot "publish"',
            'Move-Item -LiteralPath $temporaryArtifactPath -Destination $artifactPath -Force',
        ):
            self.assertIn(expected, script)
        self.assertNotIn('[System.IO.File]::ReadAllBytes($artifactPath)', script)

    def test_the_build_side_ceiling_stays_in_step_with_the_verifier_default(self):
        """R71 left the build side as literals on purpose; agreement is what must hold.

        The verifier takes injected ceilings so the gate can exercise the guard with a
        4 KiB fixture, while the build scripts guard a file they just produced and need no
        injection.  What cannot be allowed to drift is the pair agreeing: a release that
        builds under a looser ceiling would then fail its own evidence check, and one under
        a tighter ceiling hides an artifact the policy considers valid.
        """
        root = Path(__file__).resolve().parents[2]
        verifier = (root / "tools" / "verify_release_evidence.ps1").read_text(encoding="utf-8")
        fpk_build = (root / "tools" / "build_release.ps1").read_text(encoding="utf-8")
        apk_build = (root / "tools" / "build_android_release.ps1").read_text(encoding="utf-8")

        def default_of(name):
            match = re.search(r"\[long\]\$%s = (\d+)GB" % name, verifier)
            self.assertIsNotNone(match, "the verifier must keep a literal default for $%s" % name)
            return int(match.group(1))

        fpk_ceiling = default_of("MaxArtifactBytes")
        apk_ceiling = default_of("MaxAndroidArtifactBytes")
        self.assertEqual((fpk_ceiling, apk_ceiling), (10, 1),
                         "measured release policy; move it together with both build guards")
        self.assertIn("-gt %dGB" % fpk_ceiling, fpk_build,
                      "build_release.ps1 no longer allows exactly what the verifier allows")
        self.assertIn("-gt %dGB" % apk_ceiling, apk_build,
                      "build_android_release.ps1 no longer allows exactly what the verifier allows")
        # R71's naming promise: one pair of parameter names, never a third spelling.
        self.assertEqual(sorted(set(re.findall(r"\$Max\w*Bytes", verifier))),
                         ["$MaxAndroidArtifactBytes", "$MaxArtifactBytes"])

    def test_release_evidence_verifier_rejects_oversized_artifact_before_hashing(self):
        """The size guard must fire before the checksum is computed.

        The ceiling is injected rather than approached with a real file: the
        previous shape sparse-extended an artifact past 10 GiB, so a tight
        temporary volume turned this test into ``OSError: [Errno 28] No space left
        on device``, which reads in a gate log exactly like a product defect.
        """
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            artifact = directory / "fnaudio-9.8.7-fnpack.fpk"
            artifact.write_bytes(b"x" * 4096)
            # A deliberately wrong checksum: if the size guard did not run first,
            # the failure message would be the mismatch below, so the two
            # messages together pin the order, not merely the rejection.
            (directory / "SHA256SUMS").write_text(
                f"{'0' * 64}  {artifact.name}\n", encoding="ascii"
            )
            artifact_hash = hashlib.sha256(artifact.read_bytes()).hexdigest().upper()
            rejected, accepted = self._run_evidence_verifiers([
                {"args": {"ArtifactDirectory": str(directory), "MaxArtifactBytes": "4095"}},
                {"args": {"ArtifactDirectory": str(directory), "MaxArtifactBytes": "4096"},
                 "pre": [(directory / "SHA256SUMS",
                          ("%s  %s\n" % (artifact_hash, artifact.name)).encode("ascii"))]},
            ])
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("exceeds the 4095 byte artifact limit", rejected.stderr)
            self.assertNotIn("does not match SHA256SUMS", rejected.stderr)

            # A file exactly at the ceiling is accepted: the guard is "exceeds",
            # and the release policy measures a 10 GiB artifact as valid.
            self.assertEqual(accepted.returncode, 0, accepted.stderr)

    def test_release_evidence_verifier_applies_the_injected_android_artifact_limit(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            artifact = directory / "fnaudio-9.8.7-fnpack.fpk"
            android = directory / "fnaudio-android-9.8.7-release.apk"
            artifact.write_bytes(b"fixture fpk bytes")
            android.write_bytes(b"y" * 16)
            (directory / "SHA256SUMS").write_text(
                "%s  %s\n" % (hashlib.sha256(artifact.read_bytes()).hexdigest().upper(), artifact.name),
                encoding="ascii",
            )
            (directory / "ANDROID_SHA256SUMS").write_text(
                "%s  %s\n" % (hashlib.sha256(android.read_bytes()).hexdigest().upper(), android.name),
                encoding="ascii",
            )
            accepted, rejected = self._run_evidence_verifiers([
                {"args": {"ArtifactDirectory": str(directory)}},
                {"args": {"ArtifactDirectory": str(directory), "MaxAndroidArtifactBytes": "15"}},
            ])
            self.assertEqual(accepted.returncode, 0, accepted.stderr)

            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("Android artifact exceeds the 15 byte artifact limit", rejected.stderr)
            self.assertIn(android.name, rejected.stderr)

    def test_release_evidence_verifier_rejects_a_non_positive_artifact_limit(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            artifact = directory / "fnaudio-9.8.7-fnpack.fpk"
            artifact.write_bytes(b"fixture fpk bytes")
            (directory / "SHA256SUMS").write_text(
                "%s  %s\n" % (hashlib.sha256(artifact.read_bytes()).hexdigest().upper(), artifact.name),
                encoding="ascii",
            )
            # Zero is enough to pin the `-lt 1` bound: with `-lt 0` the guard
            # would accept a zero ceiling and let any artifact through, so this
            # case fails on that mutant.  A negative value is avoided because the
            # PowerShell argument parser reads a leading `-` as a switch name.
            limits = ("MaxArtifactBytes", "MaxAndroidArtifactBytes")
            scenarios = []
            for name in limits:
                scenarios.append({"args": {"ArtifactDirectory": str(directory), name: "0"}})
                scenarios.append({"args": {"ArtifactDirectory": str(directory)}})
            results = self._run_evidence_verifiers(scenarios)
            for index, name in enumerate(limits):
                with self.subTest(limit=name):
                    rejected, accepted = results[2 * index], results[2 * index + 1]
                    self.assertNotEqual(rejected.returncode, 0)
                    self.assertIn("artifact size limit is invalid", rejected.stderr)
                    self.assertEqual(accepted.returncode, 0, accepted.stderr)

    def test_script_checks_fpk_lifecycle_config_wizards_and_runtime_payload(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "build_release.ps1").read_text(encoding="utf-8")

        for command in (
            "config_callback",
            "config_init",
            "install_callback",
            "install_init",
            "main",
            "uninstall_callback",
            "uninstall_init",
            "upgrade_callback",
            "upgrade_init",
        ):
            self.assertIn(f'"{command}"', script)

        for expected in (
            '"config\\privilege"',
            '"config\\resource"',
            'defaults.run-as=root',
            '"fnaudio/music"',
            '"fnaudio/data"',
            '"wizard_library_path"',
            '"wizard_uninstall_mode"',
            '"ui\\index.cgi"',
            '"ui\\cgi_proxy.py"',
            '"ui\\service_port.json"',
            '"target\\bin\\mpd"',
        ):
            self.assertIn(expected, script)

    def test_release_script_checks_both_tar_extraction_exit_codes(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "build_release.ps1").read_text(encoding="utf-8")
        self.assertIn("Unable to inspect the built FPK with tar", script)
        self.assertIn("Unable to inspect the packaged app payload with tar", script)
        self.assertGreaterEqual(script.count("if ($LASTEXITCODE -ne 0)"), 3)

    def test_script_gates_the_packaged_identity_against_the_source_manifest(self):
        """R178: appname and the four identity roles must survive into the FPK.

        Packaging copies src/ verbatim today, so nothing *was* rewriting the
        identity; the release script simply never looked at it.  A version check
        alone let a package whose developer/publisher had drifted ship green.
        """
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "build_release.ps1").read_text(encoding="utf-8")

        self.assertIn(
            '@("appname", "developer", "publisher", "maintainer", "distributor")', script
        )
        self.assertIn(
            "Get-ManifestValue $packagedManifest $identityKey", script
        )
        # The prefix is part of the assertion: a gate that only warns about a wrong
        # identity still ships the package, so "is the message present" proves nothing.
        q = chr(39)
        self.assertIn("throw \"Packaged manifest " + q + "$identityKey" + q, script)
        # install_type decides the install partition, so the package has to carry the
        # source's declaration. Presence alone was the first cut and it still passed a
        # package that renamed the target, so the value is compared as well.
        self.assertIn(
            "Assert-PackagedInstallTarget $manifest $packagedManifest", script
        )
        self.assertIn(
            "Packaged manifest install_type presence differs from src/manifest.", script
        )
        self.assertIn(
            'throw "Packaged manifest install_type differs from src/manifest."', script
        )
        # An unguarded value read throws for a legitimate unset build (R177 lesson), so
        # the read has to stay behind the presence test.
        self.assertIn("if ($sourceDeclared) {", script)
        # These are only text checks. The shapes that used to break the real build are
        # pinned by test_install_target_gate_accepts_the_shapes_the_packager_writes.

    def test_manifest_reader_does_not_cross_line_boundaries(self):
        """Runs the shipped reader over the shapes that used to silently lie.

        Every class matcher used \\s around the key, the equals sign and the end of
        the line, and \\s covers newlines.  On a key with a blank value the match
        resumed on the NEXT line, so the reader returned that neighbour's value;
        with the equals sign on the next line it read the key as if it had a value.
        Both have to fail closed now rather than answer with somebody else's data.
        """
        powershell = self._powershell()
        if powershell is None:
            self.skipTest("no PowerShell available to run the reader")
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "build_release.ps1").read_text(encoding="utf-8")
        start = script.index("function Get-ManifestKeyPattern(")
        stop = script.index("function Assert-Contains(")
        helper = script[start:stop]
        self.assertTrue(helper.strip().endswith("}"), "the reader slice lost its body")

        driver = (
            "$ErrorActionPreference = 'Stop'\n"
            "function Read-It([string]$label, [string]$text, [string]$name) {\n"
            "    try { Write-Output ($label + '=[' + (Get-ManifestValue $text $name) + ']') }\n"
            "    catch { Write-Output ($label + '=THREW') }\n"
            "}\n"
            "Read-It 'PLAIN' \"appname=fnaudio`nversion=0.2.35`n\" 'appname'\n"
            "Read-It 'TRAILING' \"appname=fnaudio   `nversion=0.2.35`n\" 'appname'\n"
            "Read-It 'INDENTED' \"  appname=fnaudio`n\" 'appname'\n"
            "Read-It 'COMMENTED' \"# appname=decoy`nappname=fnaudio`n\" 'appname'\n"
            "Read-It 'BLANK_VALUE' \"appname=fnaudio`ninstall_type=`nversion=0.2.35`n\" 'install_type'\n"
            "Read-It 'SPLIT_ASSIGN' \"install_type`n=root`nversion=0.2.35`n\" 'install_type'\n"
            "Read-It 'ABSENT' \"appname=fnaudio`n\" 'install_type'\n"
            "Read-It 'ALIGNED' \"install_type          = root`n\" 'install_type'\n"
            "Read-It 'ALIGNED_CRLF' \"version               = 0.2.35`r`n\" 'version'\n"
        )
        with tempfile.TemporaryDirectory() as workdir:
            probe = Path(workdir) / "reader-driver.ps1"
            probe.write_text(helper + driver, encoding="ascii", newline="\n")
            completed = subprocess.run(
                [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(probe)],
                capture_output=True,
                text=True, errors="replace",
            )
        self.assertEqual(completed.returncode, 0,
                         (completed.stdout or "") + (completed.stderr or ""))
        rows = dict(
            line.partition("=")[0::2][:2]
            for line in completed.stdout.splitlines()
            if line.startswith(("PLAIN", "TRAILING", "INDENTED", "COMMENTED", "BLANK_VALUE", "SPLIT_ASSIGN", "ABSENT", "ALIGNED", "ALIGNED_CRLF"))
        )
        self.assertEqual(rows.get("PLAIN"), "[fnaudio]")
        self.assertEqual(rows.get("TRAILING"), "[fnaudio]")
        self.assertEqual(rows.get("INDENTED"), "[fnaudio]")
        self.assertEqual(rows.get("COMMENTED"), "[fnaudio]")
        # The two traps: the old reader answered 'version=0.2.35' for both.  The
        # probe only brackets a value it actually managed to read, so a failure to
        # read reports bare THREW.
        self.assertEqual(rows.get("BLANK_VALUE"), "THREW")
        self.assertEqual(rows.get("SPLIT_ASSIGN"), "THREW")
        self.assertEqual(rows.get("ABSENT"), "THREW")
        # fnpack column-aligns every key it writes into a package, so the reader has to
        # tolerate whitespace on both sides of the equals sign or the packaged manifest reads
        # as an empty file to it.
        self.assertEqual(rows.get("ALIGNED"), "[root]")
        # A packed FPK writes its manifest with CRLF line endings, so the value has
        # to stop at the carriage return instead of failing the line-end assertion.
        self.assertEqual(rows.get("ALIGNED_CRLF"), "[0.2.35]")


    def test_gradle_version_code_gate_does_not_cross_line_boundaries(self):
        r"""Runs the shipped gradle pattern over the shapes it has to reject.

        This gate is the only thing standing between a drifted build.gradle and a
        release whose android versionCode is whatever the file failed to say.  The old
        pattern matched with \s on both sides of the number, and \s covers newlines, so
        a bare "versionCode" line answered with its neighbour's digits and passed.
        Every case below is a shape a real gradle file, or a hand edit of one, gives.
        """
        powershell = self._powershell()
        if powershell is None:
            self.skipTest("no PowerShell available to run the gate")
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "build_release.ps1").read_text(encoding="utf-8")
        start = script.index("function Get-GradleVersionCodePattern(")
        stop = script.index("function Assert-Contains(")
        helper = script[start:stop]
        self.assertTrue(helper.strip().endswith("}"), "the gate slice lost its body")
        gradle = (root / "android-client" / "app" / "build.gradle").as_posix()

        driver = (
            "$ErrorActionPreference = 'Stop'\n"
            "function Read-It([string]$label, [string]$text) {\n"
            "    if ($text -match (Get-GradleVersionCodePattern)) {\n"
            "        Write-Output ($label + '=[' + [int]$Matches[1] + ']')\n"
            "    } else {\n"
            "        Write-Output ($label + '=NOMATCH')\n"
            "    }\n"
            "}\n"
            "Read-It 'PLAIN' \"        versionCode 303`n\"\n"
            "Read-It 'TWO_SPACES' \"        versionCode  303`n\"\n"
            "Read-It 'TRAILING_WS' \"        versionCode 303   `n\"\n"
            "Read-It 'TAB' \"        versionCode`t303`n\"\n"
            "Read-It 'CRLF' \"        versionCode 303`r`n\"\n"
            "Read-It 'COMMENTED_DECOY' \"        // versionCode 99`n        versionCode 303`n\"\n"
            "Read-It 'NEIGHBOUR_DIGITS' \"        versionCode`n        303`n\"\n"
            "Read-It 'NEIGHBOUR_WORD' \"        versionCode`n        targetSdk 36`n\"\n"
            "Read-It 'TRAILING_COMMENT' \"        versionCode 303 // bump me`n\"\n"
            "Read-It 'ABSENT' \"    defaultConfig {`n        versionName 0.2.35`n    }`n\"\n"
            "Read-It 'REALFILE' ([IO.File]::ReadAllText('%s'))\n" % gradle
        )
        with tempfile.TemporaryDirectory() as workdir:
            probe = Path(workdir) / "gradle-driver.ps1"
            probe.write_text(helper + driver, encoding="ascii", newline="\n")
            completed = subprocess.run(
                [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(probe)],
                capture_output=True,
                text=True, errors="replace",
            )
        self.assertEqual(completed.returncode, 0,
                         (completed.stdout or "") + (completed.stderr or ""))
        labels = ("PLAIN", "TWO_SPACES", "TRAILING_WS", "TAB", "CRLF", "COMMENTED_DECOY",
                  "NEIGHBOUR_DIGITS", "NEIGHBOUR_WORD", "TRAILING_COMMENT", "ABSENT", "REALFILE")
        rows = dict(
            line.partition("=")[0::2][:2]
            for line in completed.stdout.splitlines()
            if line.partition("=")[0] in labels
        )
        self.assertEqual(sorted(rows), sorted(labels), "a gradle shape never reported")
        # The shapes a real tree produces keep working, in either line-ending style,
        # and a commented-out decoy must never be the line that answers.
        for label in ("PLAIN", "TWO_SPACES", "TRAILING_WS", "TAB", "CRLF", "COMMENTED_DECOY"):
            self.assertEqual(rows[label], "[303]", label)
        # The trap the old pattern fell into: no number on the key's own line, so
        # there is nothing to read, and the gate has to say so instead of borrowing.
        self.assertEqual(rows["NEIGHBOUR_DIGITS"], "NOMATCH")
        self.assertEqual(rows["NEIGHBOUR_WORD"], "NOMATCH")
        self.assertEqual(rows["ABSENT"], "NOMATCH")
        # Prose after the number is not a declared versionCode either: failing closed
        # here is what keeps a half-edited gradle file out of a release.
        self.assertEqual(rows["TRAILING_COMMENT"], "NOMATCH")
        # And the file the release actually ships still satisfies its own gate, so
        # tightening the pattern cannot be what breaks the next build (R178 lesson).
        self.assertTrue(rows["REALFILE"].startswith("[3"),
                        "the shipped build.gradle no longer satisfies its own gate: %r" % rows["REALFILE"])

    def test_no_multiline_pattern_in_tools_reads_across_line_boundaries(self):
        r"""Keeps the whole \s family shut, not just the two sites that already broke.

        A pattern carrying (?m) is read line by line, which is exactly when \s turns
        dangerous: it also matches the newline, so a key that lost its value or its
        equals sign keeps matching onto the following line.  build_beta_fpk.ps1 lost
        the readers this way in R177 and build_release.ps1 lost the gradle gate in
        R179.  A new (?m)...\s site in tools/ therefore has to be a deliberate choice
        somebody wrote down, not something that slipped in.
        """
        root = Path(__file__).resolve().parents[2]
        offenders = []
        for script in sorted((root / "tools").glob("*.ps1")):
            text = script.read_text(encoding="utf-8", errors="replace")
            for number, line in enumerate(text.splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue
                if "(?m)" in line and "\\s" in line:
                    offenders.append("%s:%d" % (script.name, number))
        self.assertEqual(offenders, [],
                         "a multiline pattern still matches whitespace across lines: "
                         + "; ".join(offenders))

    def test_install_target_gate_accepts_the_shapes_the_packager_writes(self):
        """Runs the shipped install-target gate over the manifests it really receives.

        The first version of this gate matched "install_type=" on both sides of the
        packaging boundary. fnpack rewrites the manifest it packs with column-aligned
        keys -- "install_type          = root" -- so the packaged side never matched and
        the 0.2.35 release build died on its own gate six seconds in. Text assertions
        could not catch that: they only repeated the wrong pattern back. Every case
        below is a shape either the packager or the platform actually produces.
        """
        powershell = self._powershell()
        if powershell is None:
            self.skipTest("no PowerShell available to run the gate")
        root = Path(__file__).resolve().parents[2]
        script = (root / "tools" / "build_release.ps1").read_text(encoding="utf-8")
        start = script.index("function Get-ManifestKeyPattern(")
        stop = script.index("function Assert-Contains(")
        helper = script[start:stop]
        self.assertTrue(helper.strip().endswith("}"), "the gate slice lost its body")

        driver = (
            "$ErrorActionPreference = 'Stop'\n"
            "function Check-It([string]$label, [string]$source, [string]$packaged) {\n"
            "    try {\n"
            "        Assert-PackagedInstallTarget $source $packaged\n"
            "        Write-Output ($label + '=OK')\n"
            "    } catch {\n"
            "        Write-Output ($label + '=THREW:' + $_.Exception.Message)\n"
            "    }\n"
            "}\n"
            "$SRC_ROOT = \"install_type=root`n\"\n"
            "$SRC_UNSET = \"appname=fnaudio`n\"\n"
            "$SRC_BLANK = \"install_type=`n\"\n"
            "$PKG_ALIGNED = \"appname               = fnaudio`ninstall_type          = root`nchecksum              = 0123456789abcdef`n\"\n"
            "$PKG_UNSET = \"appname               = fnaudio`nchecksum              = 0123456789abcdef`n\"\n"
            "$PKG_BLANK = \"install_type=`n\"\n"
            "$PKG_PADDED_BLANK = \"appname               = fnaudio`ninstall_type          = `n\"\n"
            "$PKG_DROPPED = \"appname               = fnaudio`nchecksum              = 0123456789abcdef`n\"\n"
            "$PKG_COMMENT_ONLY = \"# install_type=root asks for the system partition`nchecksum              = 0123456789abcdef`n\"\n"
            "$PKG_DRIFT = \"install_type          = volume`n\"\n"
            "$PKG_CRLF = \"appname               = fnaudio`r`ninstall_type          = root`r`nchecksum              = 0123456789abcdef`r`n\"\n"
            "$SRC_VOLUME = \"install_type=volume`n\"\n"
            "Check-It 'ALIGNED_PAIR' $SRC_ROOT $PKG_ALIGNED\n"
            "Check-It 'UNSET_PAIR' $SRC_UNSET $PKG_UNSET\n"
            "Check-It 'BLANK_PAIR' $SRC_BLANK $PKG_BLANK\n"
            "Check-It 'PADDED_BLANK_PAIR' $SRC_BLANK $PKG_PADDED_BLANK\n"
            "Check-It 'BLANK_VS_ROOT' $SRC_BLANK $PKG_ALIGNED\n"
            "Check-It 'PACKAGED_DROPPED' $SRC_ROOT $PKG_DROPPED\n"
            "Check-It 'PACKAGED_COMMENT_ONLY' $SRC_ROOT $PKG_COMMENT_ONLY\n"
            "Check-It 'SOURCE_UNSET' $SRC_UNSET $PKG_ALIGNED\n"
            "Check-It 'VALUE_DRIFT' $SRC_ROOT $PKG_DRIFT\n"
            "Check-It 'CRLF_PAIR' $SRC_ROOT $PKG_CRLF\n"
            "Check-It 'CRLF_UNSET' $SRC_UNSET $PKG_CRLF\n"
            "Check-It 'CRLF_VALUE_DRIFT' $SRC_VOLUME $PKG_CRLF\n"
        )
        with tempfile.TemporaryDirectory() as workdir:
            probe = Path(workdir) / "gate-driver.ps1"
            probe.write_text(helper + driver, encoding="ascii", newline="\n")
            completed = subprocess.run(
                [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(probe)],
                capture_output=True,
                text=True, errors="replace",
            )
        self.assertEqual(completed.returncode, 0,
                         (completed.stdout or "") + (completed.stderr or ""))
        rows = dict(
            line.partition("=")[0::2][:2]
            for line in completed.stdout.splitlines()
            if line.startswith(("ALIGNED_PAIR", "UNSET_PAIR", "BLANK_PAIR",
                               "PADDED_BLANK_PAIR", "BLANK_VS_ROOT",
                               "PACKAGED_DROPPED", "PACKAGED_COMMENT_ONLY",
                               "SOURCE_UNSET", "VALUE_DRIFT",
                               "CRLF_PAIR", "CRLF_UNSET", "CRLF_VALUE_DRIFT"))
        )
        self.assertEqual(len(rows), 12, completed.stdout)
        # The pair that killed the real build, plus the two legitimate "no target"
        # builds: a blank value is still a declaration, on either side of the boundary.
        self.assertEqual(rows["ALIGNED_PAIR"], "OK")
        self.assertEqual(rows["UNSET_PAIR"], "OK")
        self.assertEqual(rows["BLANK_PAIR"], "OK")
        # The padded shape is what a packager writes for an empty value; treating it
        # as "absent" while treating the compact blank as "present" was the first cut of
        # this helper, and it disagreed with itself across the packaging boundary.
        self.assertEqual(rows["PADDED_BLANK_PAIR"], "OK")
        self.assertTrue(rows["BLANK_VS_ROOT"].startswith("THREW:"), rows["BLANK_VS_ROOT"])
        self.assertIn("install_type differs", rows["BLANK_VS_ROOT"])
        # Anything that changes the partition the app lands on has to fail closed.
        for label in ("PACKAGED_DROPPED", "PACKAGED_COMMENT_ONLY", "SOURCE_UNSET"):
            self.assertTrue(rows[label].startswith("THREW:"), rows[label])
            self.assertIn("presence differs", rows[label])
        self.assertTrue(rows["VALUE_DRIFT"].startswith("THREW:"), rows["VALUE_DRIFT"])
        self.assertIn("install_type differs", rows["VALUE_DRIFT"])
        # The package the packager actually produces: aligned keys AND CRLF lines.
        # Reading it wrong used to look like "the package has no install_target".
        self.assertEqual(rows["CRLF_PAIR"], "OK")
        self.assertTrue(rows["CRLF_UNSET"].startswith("THREW:"), rows["CRLF_UNSET"])
        self.assertIn("presence differs", rows["CRLF_UNSET"])
        self.assertTrue(rows["CRLF_VALUE_DRIFT"].startswith("THREW:"), rows["CRLF_VALUE_DRIFT"])
        self.assertIn("install_type differs", rows["CRLF_VALUE_DRIFT"])


class GitProvenanceScopeTests(unittest.TestCase):
    """`Get-GitProvenance` must measure the release input scopes, not the tree.

    The rule it replaces counted every untracked line `git status` reported for the
    whole repository.  This repository keeps hundreds of intentional untracked paths
    (artifacts/, _external/, music/, cached toolchains under tools/), so that count
    was never zero and `git_worktree_dirty` read "dirty" for every release ever
    built -- a constant masquerading as evidence.  Each scenario below builds a
    scratch repository whose noise lives outside the release scopes and runs the
    shipped function text, sliced out of tools/build_release.ps1 rather than
    re-typed, over it.
    """

    REPO = Path(__file__).resolve().parents[2]
    POWERSHELL = next((exe for exe in ("powershell", "pwsh") if shutil.which(exe)), None)
    GIT = shutil.which("git")
    SCOPED_SOURCES = ("src/app/server.py", "android-client/app/build.gradle")
    NOISE = ("artifacts/0.9.9/fnaudio-0.9.9-fnpack.fpk", "_external/cache.bin", "music/sample.flac")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workdir = Path(self.tmp.name) / "repo"
        self.workdir.mkdir(parents=True)
        for relative in self.SCOPED_SOURCES:
            self._file(relative)
        self.git("init", "-q")
        self.git("config", "user.email", "provenance@example.invalid")
        self.git("config", "user.name", "provenance")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        # The noise is committed *after* the baseline, so it stays untracked -- that
        # is the state the old whole-tree rule could never distinguish from real drift.
        for relative in self.NOISE:
            self._file(relative)

    def _file(self, relative):
        target = self.workdir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("payload\n", encoding="utf-8")

    def git(self, *args, **kwargs):
        cwd = kwargs.pop("cwd", None) or str(self.workdir)
        return subprocess.run([self.GIT, *args], cwd=cwd, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def shipped_probe_source(self):
        script = (self.REPO / "tools" / "build_release.ps1").read_text(encoding="utf-8")
        block = script[script.index("function Get-GitProvenance"):script.index("$manifestPath = Join-Path")]
        self.assertIn("function Get-GitProvenance([string]$Root", script)
        self.assertIn("--untracked-files=no -- $Scope", block)
        self.assertIn("--exclude-standard -- $Scope", block)
        return block

    def run_probe(self, repo_path, scope=None, preference="Stop"):
        quoted = str(repo_path).replace("'", "''")
        driver = ["$ErrorActionPreference = '%s'" % preference]
        driver.append(self.shipped_probe_source())
        call = "Get-GitProvenance -Root '%s'" % quoted
        if scope is not None:
            call += " -Scope %s" % scope
        driver.append("$p = " + call)
        for key in ("status", "worktree_dirty", "tracked_edits", "untracked_inputs"):
            driver.append("Write-Output ('%s=' + $p.%s)" % (key.upper(), key))
        # Test instrumentation only: outside Stop so a non-repo can still be counted.
        driver.append("$ErrorActionPreference = 'Continue'")
        driver.append("$w = @(& git -C '%s' status --porcelain=v1 --untracked-files=normal 2>$null)" % quoted)
        driver.append("Write-Output ('WHOLE=' + $w.Count)")
        script_path = Path(self.tmp.name) / "probe.ps1"
        script_path.write_text("\n".join(driver) + "\n", encoding="utf-8")
        done = subprocess.run([self.POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass",
                               "-File", str(script_path)], stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT)
        output = done.stdout.decode("utf-8", "replace")
        self.assertEqual(done.returncode, 0, output)
        rows = {}
        for line in output.splitlines():
            if "=" in line:
                name, _, value = line.partition("=")
                if name.isupper():
                    rows[name] = value.strip()
        return rows

    def test_untracked_noise_outside_the_release_scopes_keeps_the_record_clean(self):
        rows = self.run_probe(self.workdir)
        # The old rule read WHOLE > 0 as dirty; the scopes are untouched here.
        self.assertGreater(int(rows["WHOLE"]), 0)
        self.assertEqual(rows["STATUS"], "clean")
        self.assertEqual(rows["WORKTREE_DIRTY"], "False")
        self.assertEqual(rows["TRACKED_EDITS"], "0")
        self.assertEqual(rows["UNTRACKED_INPUTS"], "0")

    def test_a_tracked_edit_inside_a_release_scope_marks_the_record_dirty(self):
        (self.workdir / "src" / "app" / "server.py").write_text("tampered\n", encoding="utf-8")
        rows = self.run_probe(self.workdir)
        self.assertEqual(rows["STATUS"], "dirty")
        self.assertEqual(rows["TRACKED_EDITS"], "1")

    def test_an_untracked_file_inside_a_release_scope_marks_the_record_dirty(self):
        stray = self.workdir / "src" / "app" / "server" / "untracked.py"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_text("smuggled\n", encoding="utf-8")
        rows = self.run_probe(self.workdir)
        self.assertEqual(rows["STATUS"], "dirty")
        self.assertEqual(rows["UNTRACKED_INPUTS"], "1")

    def test_the_android_scope_counts_as_much_as_the_payload_scope(self):
        (self.workdir / "android-client" / "app" / "build.gradle").write_text("drifted\n", encoding="utf-8")
        rows = self.run_probe(self.workdir)
        self.assertEqual(rows["STATUS"], "dirty")
        self.assertEqual(rows["TRACKED_EDITS"], "1")

    def test_a_narrower_scope_is_honoured_rather_than_hardcoded(self):
        # Only src staged: an android-client edit must then read clean.  Proves the
        # scopes arrive as a parameter and are not decoration inside the function.
        (self.workdir / "android-client" / "app" / "build.gradle").write_text("drifted\n", encoding="utf-8")
        rows = self.run_probe(self.workdir, scope="@('src')")
        self.assertEqual(rows["STATUS"], "clean")
        self.assertEqual(rows["TRACKED_EDITS"], "0")

    def test_a_tree_without_git_stays_unavailable_instead_of_reading_clean(self):
        plain = Path(self.tmp.name) / "export"
        plain.mkdir()
        (plain / "src").mkdir()
        (plain / "src" / "server.py").write_text("payload\n", encoding="utf-8")
        rows = self.run_probe(plain)
        self.assertEqual(rows["STATUS"], "unavailable")
        self.assertEqual(rows["WORKTREE_DIRTY"], "")
        self.assertEqual(rows["TRACKED_EDITS"], "")

    def test_git_probes_that_fail_without_throwing_never_read_clean(self):
        # A scope git refuses to parse exits non-zero and says so only on stderr.
        # Under Continue that reaches the guard instead of the catch, and the guard is
        # what keeps an unreadable tree from being reported as a clean release input.
        rows = self.run_probe(self.workdir, scope="@(':(bogus')", preference="Continue")
        self.assertEqual(rows["STATUS"], "commit_only")
        self.assertEqual(rows["TRACKED_EDITS"], "")
        self.assertEqual(rows["UNTRACKED_INPUTS"], "")

    def test_the_shipped_default_scopes_cover_both_release_inputs(self):
        script = (self.REPO / "tools" / "build_release.ps1").read_text(encoding="utf-8")
        signature = script[script.index("function Get-GitProvenance"):]
        signature = signature[:signature.index("\n")]
        self.assertIn("'src'", signature)
        self.assertIn("'android-client'", signature)

    def test_the_real_release_tree_is_judged_by_the_scopes_it_ships(self):
        whole_status = self.git("status", "--porcelain=v1", "--untracked-files=normal", cwd=str(self.REPO))
        whole = [line for line in whole_status.stdout.decode("utf-8", "replace").splitlines() if line.strip()]
        edits = self.git("status", "--porcelain=v1", "--untracked-files=no", "--", "src", "android-client",
                         cwd=str(self.REPO))
        strays = self.git("ls-files", "--others", "--exclude-standard", "--", "src", "android-client",
                          cwd=str(self.REPO))
        scoped = [line for line in edits.stdout.decode("utf-8", "replace").splitlines() if line.strip()]
        stray_lines = [line for line in strays.stdout.decode("utf-8", "replace").splitlines() if line.strip()]
        expected = "dirty" if (scoped or stray_lines) else "clean"
        # The hundred-line constant below is a property of *this* checkout: artifacts/,
        # _external/, music/ and the cached toolchains live untracked in the working
        # tree.  A fresh clone has none of them, so only the whole-tree comparison is
        # conditional; the scoped verdicts still run everywhere, and the discriminating
        # "noise outside the scopes" case is covered unconditionally by the scratch
        # repository above.
        if len(whole) <= 100:
            self.skipTest("whole-tree untracked noise is absent outside the source checkout")
        rows = self.run_probe(self.REPO, scope="@('src', 'android-client')")
        self.assertEqual(rows["STATUS"], expected)
        self.assertEqual(rows["TRACKED_EDITS"], str(len(scoped)))
        self.assertEqual(rows["UNTRACKED_INPUTS"], str(len(stray_lines)))
        # The whole-repo line count is a constant here, so agreeing with the scoped
        # verdict can only come from actually using the scopes.
        self.assertGreater(len(whole), 100)


if __name__ == "__main__":
    unittest.main()

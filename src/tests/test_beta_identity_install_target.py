"""Identity and install-target guards for the fnAudio packages.

The two facts this file pins down came out of operator instructions: the
package ships under the maintainer's own account, and the app must land on the
system partition.  R177 moved the identity to the platform vendor name and R178
moved it back, so the vendor name is now the token that must NOT appear.  Both live in ``src/manifest``, and the beta
packaging script is the only other place that can rewrite them, so every check
below is either a byte-level read of the manifest or a read of the packaging
logic that has to survive into the built package.
"""

import io
import json
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import unittest

REPO_ROOT = str(Path(__file__).resolve().parents[2])
MANIFEST = os.path.join(REPO_ROOT, "src", "manifest")
PACKAGER = os.path.join(REPO_ROOT, "tools", "build_beta_fpk.ps1")
ARTIFACT_ROOT = os.path.join(REPO_ROOT, "artifacts")

# The forbidden token as a literal: this file is UTF-8, so a glyph here means
# exactly what it says.  IDENTITY_OWNER has to survive as a literal too, which it
# can because R178 moved the identity back onto an ASCII account name.
VENDOR_NAME = "飞牛"
IDENTITY_OWNER = "vinson023"
FORBIDDEN_IDENTITY_TOKENS = (VENDOR_NAME,)
IDENTITY_KEYS = ("developer", "publisher", "maintainer", "distributor")


def read_bytes(path):
    with io.open(path, "rb") as handle:
        return handle.read()


def manifest_values(text):
    values = {}
    for line in text.split("\n"):
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        name, _, value = line.partition("=")
        values.setdefault(name.strip(), value.strip())
    return values


class ManifestIdentityTests(unittest.TestCase):
    def setUp(self):
        self.raw = read_bytes(MANIFEST)
        self.text = self.raw.decode("utf-8")
        self.values = manifest_values(self.text)

    def test_every_identity_role_carries_the_maintainer_account(self):
        for key in IDENTITY_KEYS:
            self.assertIn(key, self.values, key)
            self.assertEqual(self.values[key], IDENTITY_OWNER, key)

    def test_no_vendor_identity_token_survives_in_the_manifest(self):
        for key in IDENTITY_KEYS:
            for token in FORBIDDEN_IDENTITY_TOKENS:
                self.assertNotIn(token, self.values[key], "%s still says %s" % (key, token))

    def test_the_manifest_asks_for_the_system_partition(self):
        self.assertIn("install_type", self.values, "the install target is undeclared")
        self.assertEqual(self.values["install_type"], "root")

    def test_the_manifest_is_utf8_without_bom_and_bare_lf(self):
        self.assertFalse(self.raw.startswith(b"\xef\xbb\xbf"), "a BOM would ride into the package")
        self.assertNotIn(b"\r", self.raw, "the manifest must stay LF-only")
        body = self.raw.decode("utf-8")
        self.assertEqual(body.count(IDENTITY_OWNER), len(IDENTITY_KEYS))
        self.assertEqual(body.count(VENDOR_NAME), 0, "the vendor name must be gone from the manifest")

    def test_the_production_app_account_is_the_unsuffixed_one(self):
        # The beta line owns the "-beta" suffix and the release keeps the plain
        # name, which is what keeps two App Center entries apart.  R177 built a
        # beta under a first-party-looking account; reverting the identity must not
        # revert the account as well.
        self.assertEqual(self.values["appname"], "fnaudio")
        self.assertNotIn("-beta", self.values["appname"])

    def test_the_reserved_first_party_account_stays_out_of_the_sources(self):
        # The account belongs to the platform itself, so src/ must never name it;
        # only the beta packager may, and only as a rejected value.  The needle is
        # spelled as two adjacent literals so this file, which lives under src/,
        # does not report itself as a hit.
        needle = "trim" ".music"
        root = Path(__file__).resolve().parents[2]
        hits = []
        for path in sorted((root / "src").rglob("*")):
            if not path.is_file():
                continue
            try:
                body = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if needle in body:
                hits.append(str(path.relative_to(root).as_posix()))
        self.assertEqual(hits, [], "src/ references the reserved first-party account")

    def test_the_install_target_documentation_is_contiguous_with_its_key(self):
        # Remove-ManifestKey deletes a key together with the comment run above it,
        # so the comment has to be the line directly above the assignment.
        lines = self.text.split("\n")
        at = next(i for i, line in enumerate(lines) if line.startswith("install_type="))
        self.assertTrue(lines[at - 1].startswith("#"), "the comment run broke away from install_type")


class PackagerIdentityTests(unittest.TestCase):
    def setUp(self):
        self.raw = read_bytes(PACKAGER)
        self.text = self.raw.decode("utf-8")

    def test_the_packaging_script_stays_pure_ascii(self):
        # A BOM-less .ps1 is decoded as ANSI by Windows PowerShell 5.1, so a literal
        # vendor name in this file would reach the manifest mangled.  The script keeps
        # to code points instead, which only works while the file is ASCII.
        offending = [i for i, byte in enumerate(self.raw) if byte > 127]
        self.assertEqual(offending, [], "non-ASCII bytes at %r" % offending[:5])

    def test_the_identity_defaults_are_plain_literals_of_the_owner_account(self):
        # R177 built these two defaults from [char]0xNNNN code points only because
        # the value then had to be a vendor name, which a BOM-less .ps1 cannot carry.
        # The account name is ASCII, so the indirection now only serves to hide the
        # value from a grep; the literal is the honest shape.
        for role in ("Developer", "Publisher"):
            self.assertRegex(
                self.text,
                r"\[string\]\$" + role + r" = '" + IDENTITY_OWNER + r"'",
                role,
            )
        # The one legitimate code-point use left is the bracket pair around BETA.
        self.assertEqual(2, self.text.count("[char]0x"), "unexpected code-point indirection grew back")

    def test_the_script_accepts_only_the_two_contracted_install_targets(self):
        self.assertIn("$InstallType -ceq 'root'", self.text)
        self.assertIn("$InstallType -ceq 'unset'", self.text)
        self.assertIn("[string]$InstallType = 'root'", self.text)

    def test_the_staged_manifest_must_still_declare_the_install_target(self):
        presence = re.search(r"foreach \(\$key in @\('appname'.*?\)\) \{", self.text, re.S)
        self.assertIsNotNone(presence, "the staged-manifest key list moved")
        self.assertIn("'install_type'", presence.group(0))

    def test_the_unset_branch_deletes_the_key_rather_than_blanking_it(self):
        self.assertEqual(1, len(re.findall(r"function Remove-ManifestKey \{", self.text)))
        self.assertIn("Remove-ManifestKey -Text $nextManifest -Name 'install_type'", self.text)

    def test_the_package_gate_asserts_the_install_target(self):
        # The check lives in its own helper so the gate can be exercised without a
        # staged tree; asserting the call, not the message wording, is what keeps a
        # renamed or bypassed helper from passing.
        self.assertEqual(1, len(re.findall(r"function Get-ManifestInstallTypeViolations \{", self.text)))
        self.assertIn(
            "Get-ManifestInstallTypeViolations -Text $checkedManifest -Expected $InstallType -Label $Label",
            self.text,
        )
        # Reverting to a table lookup would throw on a missing key instead of
        # reporting which tree failed, so the throwing read must stay out.
        self.assertNotIn("Get-ManifestValue -Text $checkedManifest -Name 'install_type'", self.text)

    def test_the_report_and_the_provenance_carry_the_install_target(self):
        self.assertEqual(2, self.text.count("install_type    = $InstallType")
                         + self.text.count("install_type     = $InstallType"))

    def test_the_identity_gate_still_checks_the_four_roles(self):
        for key in IDENTITY_KEYS:
            self.assertIn("        %s " % key, self.text, key)
            self.assertIn("$manifestExpectations[$key]", self.text)


class ManifestHelperBehaviourTests(unittest.TestCase):
    """Runs the real PowerShell helpers against the real manifest text."""

    POWERSHELL = next((exe for exe in ("powershell", "pwsh") if shutil.which(exe)), None)
    # Class level on purpose: the slicing below has to read the shipped script, and a
    # per-instance setUp would let a typo quietly turn the slice into an empty string.
    text = read_bytes(PACKAGER).decode("utf-8")

    def helper_source(self):
        # The three manifest helpers sit in one contiguous block ahead of
        # Assert-Condition, so the block is sliced rather than re-typed: a re-typed
        # copy would keep passing while the shipped script rotted.
        start = self.text.index("function Get-ManifestValue {")
        stop = self.text.index("function Assert-Condition {")
        return self.text[start:stop]

    @unittest.skipUnless(POWERSHELL, "no PowerShell available to run the helpers")
    def test_setting_and_removing_the_install_target_behave_as_the_platform_spells_them(self):
        driver = (
            "$ErrorActionPreference = 'Stop'\n"
            "$text = [IO.File]::ReadAllText('%s')\n"
            "$rooted = Set-ManifestValue -Text $text -Name 'install_type' -Value 'root'\n"
            "$gone = Remove-ManifestKey -Text $text -Name 'install_type'\n"
            "Write-Output ('SET=' + (Get-ManifestValue -Text $rooted -Name 'install_type'))\n"
            "Write-Output ('KEPT=' + (Get-ManifestValue -Text $gone -Name 'appname'))\n"
            "Write-Output ('KEY_GONE=' + [string](-not ($gone -cmatch '(?m)^\\s*install_type\\s*=')))\n"
            "Write-Output ('COMMENT_GONE=' + [string](-not ($gone -cmatch 'system partition')))\n"
        ) % MANIFEST.replace(os.sep, "/")
        with tempfile.TemporaryDirectory() as workdir:
            script = os.path.join(workdir, "driver.ps1")
            with io.open(script, "w", encoding="ascii", newline="\n") as handle:
                handle.write(self.helper_source() + driver)
            completed = subprocess.run(
                [self.POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script],
                capture_output=True,
                text=True, errors="replace",
            )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        rows = dict(line.split("=", 1) for line in completed.stdout.splitlines() if "=" in line)
        self.assertEqual(rows.get("SET"), "root")
        self.assertEqual(rows.get("KEPT"), "fnaudio")
        self.assertEqual(rows.get("KEY_GONE"), "True")
        self.assertEqual(rows.get("COMMENT_GONE"), "True")


    @unittest.skipUnless(POWERSHELL, "no PowerShell available to run the gate helper")
    def test_the_gate_reports_every_shape_of_the_install_target(self):
        # Four shapes the packager can produce plus a case-only misspelling, all run
        # through the shipped helper: the platform accepts an absent key and rejects
        # nothing else, so "expected root" has to be reported for each of the other
        # three without ever raising an exception out of the gate.
        driver = (
            "$ErrorActionPreference = 'Stop'\n"
            "$text = [IO.File]::ReadAllText('%s')\n"
            "$missing = Remove-ManifestKey -Text $text -Name 'install_type'\n"
            "$blanked = Set-ManifestValue -Text $text -Name 'install_type' -Value ''\n"
            "$wrongcase = Set-ManifestValue -Text $text -Name 'install_type' -Value 'ROOT'\n"
            "Write-Output ('BLANK_READ=[' + (Get-ManifestValue -Text $blanked -Name 'install_type') + ']')\n"
            "$rewrote = Set-ManifestValue -Text $blanked -Name 'install_type' -Value 'root'\n"
            "Write-Output ('ROUNDTRIP=' + [string]($rewrote -ceq $text))\n"
            "Write-Output ('DEPS_KEPT=' + [string]($rewrote.Contains('install_dep_apps=python312')))\n"
            "$shapes = [ordered]@{\n"
            "    ROOT_DECLARED = @($text, 'root')\n"
            "    ROOT_MISSING = @($missing, 'root')\n"
            "    ROOT_BLANKED = @($blanked, 'root')\n"
            "    ROOT_WRONGCASE = @($wrongcase, 'root')\n"
            "    UNSET_DECLARED = @($text, 'unset')\n"
            "    UNSET_MISSING = @($missing, 'unset')\n"
            "}\n"
            "foreach ($shape in $shapes.Keys) {\n"
            "    $found = @(Get-ManifestInstallTypeViolations -Text $shapes[$shape][0] "
            "-Expected $shapes[$shape][1] -Label 'probe')\n"
            "    Write-Output ($shape + '=' + $found.Count + '|' + ($found -join ';'))\n"
            "}\n"
        ) % MANIFEST.replace(os.sep, "/")
        with tempfile.TemporaryDirectory() as workdir:
            script = os.path.join(workdir, "gate-driver.ps1")
            with io.open(script, "w", encoding="ascii", newline="\n") as handle:
                handle.write(self.helper_source() + driver)
            completed = subprocess.run(
                [self.POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script],
                capture_output=True,
                text=True, errors="replace",
            )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        # A blank value has to read back blank, and writing over it has to land on
        # that key's own line.  All three helpers matched the whitespace around "="
        # with \s, which also covers newlines, so on a key with an empty value the
        # match resumed on the NEXT line: the reader returned that line, the writer
        # replaced it, and the remover deleted it.  DEPS_KEPT is the line that used
        # to be destroyed, and ROUNDTRIP is the byte-for-byte shape the package needs.
        self.assertIn("BLANK_READ=[]", completed.stdout)
        self.assertIn("ROUNDTRIP=True", completed.stdout)
        self.assertIn("DEPS_KEPT=True", completed.stdout)
        rows = {}
        for line in completed.stdout.splitlines():
            if "|" in line:
                name, _, payload = line.partition("=")
                count, _, messages = payload.partition("|")
                rows[name] = (int(count), messages)
        self.assertEqual(sorted(rows), sorted(
            "ROOT_DECLARED ROOT_MISSING ROOT_BLANKED ROOT_WRONGCASE UNSET_DECLARED UNSET_MISSING".split()))
        # A good package is silent, and a bad one says so once, with the label that
        # names which of the three trees the gate was looking at.
        self.assertEqual(rows["ROOT_DECLARED"], (0, ""))
        self.assertEqual(rows["UNSET_MISSING"], (0, ""))
        for name in ("ROOT_MISSING", "ROOT_BLANKED", "ROOT_WRONGCASE", "UNSET_DECLARED"):
            count, messages = rows[name]
            self.assertEqual(count, 1, "%s reported %r" % (name, messages))
            self.assertTrue(messages.startswith("[probe] "), "%s lost its label: %r" % (name, messages))
        self.assertIn("does not declare install_type", rows["ROOT_MISSING"][1])
        self.assertIn("is '', expected 'root'", rows["ROOT_BLANKED"][1])
        self.assertIn("is 'ROOT', expected 'root'", rows["ROOT_WRONGCASE"][1])
        self.assertIn("still declares install_type", rows["UNSET_DECLARED"][1])


    @unittest.skipUnless(POWERSHELL, "no PowerShell available to run the presence check")
    def test_the_presence_check_does_not_count_a_broken_key_line(self):
        # The staged manifest is asserted key by key before the identity rewrite runs.
        # That check used to match with \s around the equals sign -- and \s covers
        # newlines -- so a key whose "=" had fallen onto the next line was still called
        # present, while the Set-ManifestValue right below it uses [ \t] and died later
        # under its own message, on a tree the operator had just been assured was whole.
        # The REAL_* rows pin the other direction: the shipped manifest must keep
        # declaring every key this loop asks about.
        driver = (
            "$ErrorActionPreference = 'Stop'\n"
            "function Check-It([string]$label, [string]$text) {\n"
            "    Write-Output ($label + '=' + [string](Test-ManifestKeyPresent -Text $text -Name 'install_type'))\n"
            "}\n"
            "Check-It 'COMPACT' \"appname=fnaudio`ninstall_type=root`n\"\n"
            "Check-It 'ALIGNED' \"install_type          = root`n\"\n"
            "Check-It 'SPACED' \"install_type =root`n\"\n"
            "Check-It 'BLANK_VALUE' \"install_type=`n\"\n"
            "Check-It 'CRLF' \"install_type=root`r`n\"\n"
            "Check-It 'SPLIT_ASSIGN' \"install_type`n=root`n\"\n"
            "Check-It 'STRANDED' \"install_type`nappname=fnaudio`n\"\n"
            "Check-It 'ABSENT' \"appname=fnaudio`n\"\n"
            "Check-It 'LONGER_KEY' \"install_type_extra=root`n\"\n"
            "$real = [IO.File]::ReadAllText('%s')\n"
            "foreach ($key in @('appname', 'version', 'display_name', 'desc', 'developer', "
            "'publisher', 'maintainer', 'distributor', 'install_type')) {\n"
            "    Write-Output ('REAL_' + $key + '=' + [string](Test-ManifestKeyPresent -Text $real -Name $key))\n"
            "}\n"
        ) % MANIFEST.replace(os.sep, "/")
        with tempfile.TemporaryDirectory() as workdir:
            script = os.path.join(workdir, "presence-driver.ps1")
            with io.open(script, "w", encoding="ascii", newline="\n") as handle:
                handle.write(self.helper_source() + driver)
            completed = subprocess.run(
                [self.POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script],
                capture_output=True,
                text=True, errors="replace",
            )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        rows = dict(line.split("=", 1) for line in completed.stdout.splitlines() if "=" in line)
        for label in ("COMPACT", "ALIGNED", "SPACED", "BLANK_VALUE", "CRLF"):
            self.assertEqual(rows.get(label), "True", label)
        # The trap: the old check answered True for a key with no equals sign of its
        # own, which is the one manifest shape this loop exists to catch.
        self.assertEqual(rows.get("SPLIT_ASSIGN"), "False")
        self.assertEqual(rows.get("STRANDED"), "False")
        self.assertEqual(rows.get("ABSENT"), "False")
        self.assertEqual(rows.get("LONGER_KEY"), "False")
        real = {name: value for name, value in rows.items() if name.startswith("REAL_")}
        self.assertEqual(len(real), 9, "the staged-manifest key list stopped being reported")
        self.assertEqual([name for name, value in sorted(real.items()) if value != "True"], [],
                         "src/manifest no longer satisfies its own presence check")


class BuiltPackageTests(unittest.TestCase):
    """The beta provenance file is the only record of what went into a package."""

    def latest_provenance(self):
        if not os.path.isdir(ARTIFACT_ROOT):
            return None
        found = []
        for dirpath, _dirnames, filenames in os.walk(ARTIFACT_ROOT):
            if "BETA_PROVENANCE.json" in filenames:
                found.append(os.path.join(dirpath, "BETA_PROVENANCE.json"))
        if not found:
            return None
        return max(found, key=os.path.getmtime)

    def test_the_newest_beta_reports_the_reviewed_identity(self):
        # src/manifest is the single source of truth: asserting a literal here would
        # pin this test to whichever identity happened to be current when it was
        # written, which is exactly how R178 found itself contradicted by its own
        # green gate.  The beta rewrites appname, so that key stays out of the loop.
        #
        # The schema (BETA_PROVENANCE.json, schema=1) records the two roles the
        # platform shows in App Center plus the install target.  It carries no
        # maintainer/distributor because the packager already compares all four
        # against the manifest inside the built package, which is a stronger claim
        # than a self-reported summary line could be.
        path = self.latest_provenance()
        if path is None:
            self.skipTest("no beta package has been built locally")
        expected = manifest_values(read_bytes(MANIFEST).decode("utf-8"))
        with io.open(path, "r", encoding="utf-8") as handle:
            provenance = json.load(handle)
        for key in ("developer", "publisher", "install_type"):
            self.assertEqual(provenance.get(key), expected[key], "%s: %s" % (key, path))
        self.assertEqual(provenance.get("production_base"), expected["version"], path)


if __name__ == "__main__":
    unittest.main()
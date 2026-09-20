[CmdletBinding()]
param(
    [string]$ArtifactRoot = "",
    [string]$OutputPath = "",
    [ValidateRange(1, 256)]
    [int]$MaxEntries = 256
)

function Get-BoundedArtifactName {
    param([object]$Value)

    $text = [string]$Value
    if ($text.Length -gt 128 -or $text -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$') {
        return ""
    }
    return $text
}

function Get-BoundedSha256 {
    param([object]$Value)

    $text = ([string]$Value).ToLowerInvariant()
    if ($text -notmatch '^[0-9a-f]{64}$') {
        return ""
    }
    return $text
}

function Get-BoundedRecoveryNote {
    param([object]$Value)

    $text = [string]$Value
    $text = $text -replace '[\r\n\t]+', ' '
    if ($text.Length -gt 512) {
        return $text.Substring(0, 512)
    }
    return $text
}

function Get-BoundedBoolean {
    param([object]$Value)

    return ($Value -is [bool] -and [bool]$Value)
}

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else {
    $currentRoot = (Get-Location).Path
    if (Test-Path -LiteralPath (Join-Path $currentRoot "verify_release_evidence.ps1") -PathType Leaf) {
        $currentRoot
    } elseif (Test-Path -LiteralPath (Join-Path $currentRoot "tools\verify_release_evidence.ps1") -PathType Leaf) {
        Join-Path $currentRoot "tools"
    } else {
        $currentRoot
    }
}
if (-not $ArtifactRoot) {
    $ArtifactRoot = Join-Path $scriptRoot "..\artifacts"
}

$resolvedRoot = Resolve-Path -LiteralPath $ArtifactRoot
if (-not (Test-Path -LiteralPath $resolvedRoot.Path -PathType Container)) {
    throw "Artifact root must be a directory: $ArtifactRoot"
}
$verifier = Join-Path $scriptRoot "verify_release_evidence.ps1"
if (-not (Test-Path -LiteralPath $verifier -PathType Leaf)) {
    throw "Release evidence verifier is missing: $verifier"
}
$projectRoot = Split-Path -Parent $scriptRoot
$manifestPath = Join-Path $projectRoot "SOURCE_MANIFEST.sha256"
$manifestSha256 = ""
if (Test-Path -LiteralPath $manifestPath -PathType Leaf) {
    $getFileHash = Get-Command -Name Get-FileHash -ErrorAction SilentlyContinue
    if ($getFileHash) {
        $manifestSha256 = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    } else {
        $stream = [IO.File]::OpenRead($manifestPath)
        $algorithm = [Security.Cryptography.SHA256]::Create()
        try {
            $manifestSha256 = ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace("-", "").ToLowerInvariant()
        } finally {
            $algorithm.Dispose()
            $stream.Dispose()
        }
    }
}

# Keep only the newest bounded window while enumerating.  Large artifact
# stores may contain thousands of historical versions; materializing and
# sorting them all makes an index run consume memory unrelated to its output.
$directories = [System.Collections.Generic.List[object]]::new()
Get-ChildItem -LiteralPath $resolvedRoot.Path -Directory | ForEach-Object {
    if ($_.Name -notmatch '^\d+\.\d+\.\d+$') { return }
    try { $version = [version]$_.Name } catch { return }
    $entry = [pscustomobject]@{ directory = $_; version = $version }
    $position = 0
    while ($position -lt $directories.Count -and $directories[$position].version -ge $version) { $position++ }
    $directories.Insert($position, $entry)
    if ($directories.Count -gt $MaxEntries) { $directories.RemoveAt($directories.Count - 1) }
}
$releases = @()
foreach ($candidate in $directories) {
    $directory = $candidate.directory
    try {
        $raw = & $verifier -ArtifactDirectory $directory.FullName -Json 2>$null
        $payload = ($raw -join "`n") | ConvertFrom-Json
        $releases += [pscustomobject]@{
            directory = $directory.Name
            validated = Get-BoundedBoolean $payload.Validated
            android_validated = if ($payload.PSObject.Properties.Name -contains "AndroidValidated") {
                Get-BoundedBoolean $payload.AndroidValidated
            } else { $false }
            evidence_complete = Get-BoundedBoolean $payload.EvidenceComplete
            artifact = Get-BoundedArtifactName $payload.Artifact
            sha256 = Get-BoundedSha256 $payload.SHA256
            recovery_note = Get-BoundedRecoveryNote $payload.RecoveryNote
        }
    }
    catch {
        $releases += [pscustomobject]@{
            directory = $directory.Name
            validated = $false
            android_validated = $false
            evidence_complete = $false
            artifact = ""
            sha256 = ""
            # Keep generated JSON ASCII-stable across PowerShell hosts whose
            # pipeline encoding may be OEM/GBK; localized detail belongs in
            # the human release notes, not the recovery index.
            recovery_note = "Validation failed"
        }
    }
}

$indexPayload = [pscustomobject]@{
    schema = 1
    generated_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    artifact_root = $resolvedRoot.Path
    source_manifest_present = [bool]$manifestSha256
    source_manifest_sha256 = $manifestSha256
    entry_limit = $MaxEntries
    entry_count = $releases.Count
    releases = $releases
}
$indexJson = $indexPayload | ConvertTo-Json -Depth 6
if ($OutputPath) {
    $resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
    $outputParent = Split-Path -Parent $resolvedOutput
    if (-not (Test-Path -LiteralPath $outputParent -PathType Container)) {
        throw "Output directory must exist: $outputParent"
    }
    $temporaryOutput = "$resolvedOutput.tmp.$([guid]::NewGuid().ToString('N'))"
    try {
        Set-Content -LiteralPath $temporaryOutput -Value $indexJson -Encoding UTF8
        Move-Item -LiteralPath $temporaryOutput -Destination $resolvedOutput -Force
    }
    finally {
        if (Test-Path -LiteralPath $temporaryOutput -PathType Leaf) {
            Remove-Item -LiteralPath $temporaryOutput -Force -ErrorAction SilentlyContinue
        }
    }
}
$indexJson

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ArtifactDirectory,
    [string]$SourceDirectory,
    [switch]$RequireCompleteEvidence,
    [switch]$Json,
    # Artifact ceilings are policy, not source code: keeping them as explicit
    # parameters with these defaults lets a test fixture exercise "reject before
    # hashing" in bytes instead of building a ten-gigabyte file.  The old shape
    # (sparse `truncate(10GiB + 1)`) aborted with "No space left on device" on a
    # tight temporary volume, which reads in a gate log exactly like a product
    # defect.
    [long]$MaxArtifactBytes = 10GB,
    [long]$MaxAndroidArtifactBytes = 1GB
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($MaxArtifactBytes -lt 1 -or $MaxAndroidArtifactBytes -lt 1) {
    throw "Release verification artifact size limit is invalid."
}

function Get-Sha256Hex {
    param([Parameter(Mandatory = $true)][string]$Path)

    # `Get-FileHash` is present in supported desktop PowerShell releases, but
    # a few stripped-down embedded hosts omit it. Recovery verification must
    # still be executable there, so retain a streaming .NET fallback.
    $getFileHash = Get-Command -Name Get-FileHash -ErrorAction SilentlyContinue
    if ($getFileHash) {
        return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
    }
    $stream = [IO.File]::OpenRead($Path)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace("-", "")
    }
    finally {
        $algorithm.Dispose()
        $stream.Dispose()
    }
}

function Get-StrictJsonInteger {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string]$FieldName
    )

    # Do not let PowerShell coerce JSON booleans or arbitrary objects to an
    # integer.  Provenance counters are evidence, not user-facing settings.
    if ($null -eq $Value -or $Value -is [bool] -or
        ($Value -isnot [byte] -and $Value -isnot [int16] -and
         $Value -isnot [int32] -and $Value -isnot [int64] -and
         $Value -isnot [single] -and $Value -isnot [double] -and
         $Value -isnot [decimal])) {
        throw "Release provenance has an invalid $FieldName."
    }
    try {
        $number = [decimal]$Value
        if ($number -ne [decimal]::Truncate($number) -or
            $number -lt 0 -or $number -gt [int]::MaxValue) {
            throw "not a bounded integer"
        }
        return [int]$number
    }
    catch {
        throw "Release provenance has an invalid $FieldName."
    }
}

$resolvedArtifact = Resolve-Path -LiteralPath $ArtifactDirectory
if (-not (Test-Path -LiteralPath $resolvedArtifact.Path -PathType Container)) {
    throw "Release evidence path must be a directory: $ArtifactDirectory"
}
$directory = $resolvedArtifact.Path
$shaPath = Join-Path $directory "SHA256SUMS"
if (-not (Test-Path -LiteralPath $shaPath -PathType Leaf)) {
    throw "Release evidence is missing SHA256SUMS: $shaPath"
}
$shaFile = Get-Item -LiteralPath $shaPath
if ($shaFile.Length -gt 64KB) {
    throw "SHA256SUMS exceeds the 64 KiB evidence limit."
}
$shaLines = @(Get-Content -LiteralPath $shaPath -Encoding ASCII)
if ($shaLines.Count -lt 1 -or $shaLines.Count -gt 128) {
    throw "SHA256SUMS must contain between one and 128 checksum records."
}
$checksumRecords = [System.Collections.Generic.List[object]]::new()
$checksumNames = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
foreach ($shaLine in $shaLines) {
    $record = $shaLine.Trim()
    if ($record -notmatch '^(?<hash>[A-Fa-f0-9]{64})\s{2}(?<name>[A-Za-z0-9][A-Za-z0-9._-]{0,254})$') {
        throw "SHA256SUMS contains an invalid checksum record."
    }
    $name = $Matches.name
    if (-not $checksumNames.Add($name)) {
        throw "SHA256SUMS contains duplicate artifact records."
    }
    $checksumRecords.Add([pscustomobject]@{
        Name = $name
        Hash = $Matches.hash.ToUpperInvariant()
    })
}
$fpkRecords = @($checksumRecords | Where-Object { $_.Name -match '(?i)\.fpk$' })
if ($fpkRecords.Count -ne 1) {
    throw "SHA256SUMS must contain exactly one FPK checksum record."
}
$actualHash = ""
foreach ($record in $checksumRecords) {
    $recordPath = Join-Path $directory $record.Name
    if (-not (Test-Path -LiteralPath $recordPath -PathType Leaf)) {
        throw "Release artifact named by SHA256SUMS is missing: $recordPath"
    }
    $recordFile = Get-Item -LiteralPath $recordPath
    # Keep every checksum record bounded before hashing. Historical releases
    # include both the FPK and Android APK, so only bounding the FPK would
    # leave recovery verification vulnerable to an arbitrarily large sidecar.
    if ($recordFile.Length -gt $MaxArtifactBytes) {
        throw "Release artifact exceeds the $MaxArtifactBytes byte artifact limit: $($record.Name)"
    }
    $recordHash = Get-Sha256Hex -Path $recordPath
    if ($recordHash -ne $record.Hash) {
        throw "Artifact SHA-256 does not match SHA256SUMS: $($record.Name)"
    }
    if ($record.Name -eq $fpkRecords[0].Name) {
        $actualHash = $recordHash
    }
}
$artifactPath = Join-Path $directory $fpkRecords[0].Name

# Android releases publish their checksum separately so an APK can coexist
# with the FPK without changing the latter's one-FPK SHA256SUMS contract.
# Validate that sidecar whenever it is present; legacy directories that predate
# Android evidence remain readable and are still marked by their FPK evidence.
$androidShaPath = Join-Path $directory "ANDROID_SHA256SUMS"
$androidValidated = $false
if (Test-Path -LiteralPath $androidShaPath -PathType Leaf) {
    $androidShaFile = Get-Item -LiteralPath $androidShaPath
    if ($androidShaFile.Length -gt 64KB) {
        throw "ANDROID_SHA256SUMS exceeds the 64 KiB evidence limit."
    }
    $androidShaLines = @(Get-Content -LiteralPath $androidShaPath -Encoding ASCII)
    if ($androidShaLines.Count -ne 1) {
        throw "ANDROID_SHA256SUMS must contain exactly one checksum record."
    }
    $androidRecord = $androidShaLines[0].Trim()
    if ($androidRecord -notmatch '^(?<hash>[A-Fa-f0-9]{64})\s{2}(?<name>fnaudio-android-[0-9]+\.[0-9]+\.[0-9]+-release\.apk)$') {
        throw "ANDROID_SHA256SUMS contains an invalid checksum record."
    }
    $androidArtifactPath = Join-Path $directory $Matches.name
    if (-not (Test-Path -LiteralPath $androidArtifactPath -PathType Leaf)) {
        throw "Android artifact named by ANDROID_SHA256SUMS is missing: $androidArtifactPath"
    }
    $androidArtifact = Get-Item -LiteralPath $androidArtifactPath
    if ($androidArtifact.Length -gt $MaxAndroidArtifactBytes) {
        throw "Android artifact exceeds the $MaxAndroidArtifactBytes byte artifact limit: $($Matches.name)"
    }
    if ((Get-Sha256Hex -Path $androidArtifactPath) -ne $Matches.hash.ToUpperInvariant()) {
        throw "Android artifact SHA-256 does not match ANDROID_SHA256SUMS: $($Matches.name)"
    }
    $androidValidated = $true
}

$manifestPath = Join-Path $directory "SOURCE_MANIFEST.sha256"
$provenancePath = Join-Path $directory "SOURCE_PROVENANCE.json"
$manifestPresent = Test-Path -LiteralPath $manifestPath -PathType Leaf
$provenancePresent = Test-Path -LiteralPath $provenancePath -PathType Leaf
if ($manifestPresent -xor $provenancePresent) {
    throw "Release source evidence is incomplete: SOURCE_MANIFEST.sha256 and SOURCE_PROVENANCE.json must be present together."
}
$evidenceComplete = $manifestPresent -and $provenancePresent
if ($evidenceComplete) {
    if ($SourceDirectory) {
        $resolvedSource = Resolve-Path -LiteralPath $SourceDirectory
        if (-not (Test-Path -LiteralPath $resolvedSource.Path -PathType Container)) {
            throw "Source directory must be a directory: $SourceDirectory"
        }
    }
    $manifestFile = Get-Item -LiteralPath $manifestPath
    if ($manifestFile.Length -gt 64MB) {
        throw "SOURCE_MANIFEST.sha256 exceeds the 64 MiB evidence limit."
    }
    $manifestLines = Get-Content -LiteralPath $manifestPath -Encoding ASCII
    if (@($manifestLines).Count -gt 200000) {
        throw "SOURCE_MANIFEST.sha256 exceeds the 200000-record evidence limit."
    }
    if (-not $manifestLines -or @($manifestLines | Where-Object { $_ -notmatch '^[A-Fa-f0-9]{64}\s{2}.+$' }).Count) {
        throw "SOURCE_MANIFEST.sha256 contains an invalid record."
    }
    if (@($manifestLines | Select-Object -Unique).Count -ne @($manifestLines).Count) {
        throw "SOURCE_MANIFEST.sha256 contains duplicate records."
    }
    $manifestNames = @($manifestLines | ForEach-Object {
        if ($_ -match '^[A-Fa-f0-9]{64}\s{2}(?<path>.+)$') {
            $relativeManifestPath = ($Matches.path -replace '\\', '/')
            $segments = $relativeManifestPath.Split('/')
            if ([string]::IsNullOrWhiteSpace($relativeManifestPath) -or $relativeManifestPath.Length -gt 4096 -or [IO.Path]::IsPathRooted($relativeManifestPath) -or $segments -contains '' -or $segments -contains '.' -or $segments -contains '..' -or $relativeManifestPath.StartsWith('/')) {
                throw "SOURCE_MANIFEST.sha256 contains an unsafe path: $($Matches.path)"
            }
            $relativeManifestPath.ToLowerInvariant()
        }
    })
    if (@($manifestNames | Select-Object -Unique).Count -ne $manifestNames.Count) {
        throw "SOURCE_MANIFEST.sha256 contains duplicate paths."
    }
    if ($SourceDirectory) {
        $sourceRoot = $resolvedSource.Path.TrimEnd([char]'\', [char]'/' )
        foreach ($manifestLine in $manifestLines) {
            $manifestLine -match '^[A-Fa-f0-9]{64}\s{2}(?<path>.+)$' | Out-Null
            $relativePath = $Matches.path.Replace('/', '\')
            $sourcePath = Join-Path $sourceRoot $relativePath
            if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
                throw "SOURCE_MANIFEST.sha256 names a missing source file: $($Matches.path)"
            }
            $sourceFile = Get-Item -LiteralPath $sourcePath
            if ((Get-Sha256Hex -Path $sourcePath) -ne $Matches[0].Substring(0, 64).ToUpperInvariant()) {
                throw "SOURCE_MANIFEST.sha256 hash mismatch: $($Matches.path)"
            }
        }
    }
    try {
        $provenanceFile = Get-Item -LiteralPath $provenancePath
        if ($provenanceFile.Length -gt 1MB) {
            throw "SOURCE_PROVENANCE.json exceeds the 1 MiB evidence limit."
        }
        $provenance = Get-Content -LiteralPath $provenancePath -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        throw "SOURCE_PROVENANCE.json is not valid JSON: $($_.Exception.Message)"
    }
    if ($null -eq $provenance -or $provenance -is [System.Array] -or $provenance -is [string] -or $provenance -is [ValueType]) {
        throw "SOURCE_PROVENANCE.json must contain a JSON object."
    }
    $schema = Get-StrictJsonInteger -Value $provenance.schema -FieldName "schema"
    if ($schema -ne 1) {
        throw "Release provenance has an unsupported schema."
    }
    $stagedFileCount = Get-StrictJsonInteger -Value $provenance.staged_file_count -FieldName "staged file count"
    if ($stagedFileCount -ne @($manifestLines).Count) {
        throw "Release provenance staged file count does not match SOURCE_MANIFEST.sha256."
    }
    $assetBuild = [string]$provenance.asset_build
    if ($assetBuild -notmatch '^(?<version>\d+\.\d+\.\d+)-[a-f0-9]{12}$') {
        throw "Release provenance has an invalid UI asset build."
    }
    $assetBuildVersion = $Matches.version
    $manifestHash = Get-Sha256Hex -Path $manifestPath
    if ([string]$provenance.source_manifest_sha256 -ne $manifestHash) {
        throw "Release provenance does not match SOURCE_MANIFEST.sha256."
    }
    if ([string]$provenance.artifact_sha256 -ne $actualHash) {
        throw "Release provenance does not match the final FPK SHA-256."
    }
    if ([string]$provenance.fnpack_sha256 -notmatch '^[A-Fa-f0-9]{64}$') {
        throw "Release provenance is missing a valid fnpack SHA-256."
    }
    $provenanceVersion = [string]$provenance.version
    if ($provenanceVersion -notmatch '^\d+\.\d+\.\d+$') {
        throw "Release provenance has an invalid version."
    }
    if ($assetBuildVersion -ne $provenanceVersion) {
        throw "Release provenance UI asset build does not match its version."
    }
    $expectedArtifactName = "fnaudio-$provenanceVersion-fnpack.fpk"
    if ((Split-Path -Leaf $artifactPath) -ne $expectedArtifactName) {
        throw "Release artifact name does not match provenance version."
    }
    if ($androidValidated -and (Split-Path -Leaf $androidArtifactPath) -ne "fnaudio-android-$provenanceVersion-release.apk") {
        throw "Android artifact name does not match provenance version."
    }
}
if ($RequireCompleteEvidence -and -not $evidenceComplete) {
    throw "Complete release evidence is required, but staged source provenance is unavailable."
}

$result = [pscustomobject]@{
    ArtifactDirectory = $directory
    Artifact = (Split-Path -Leaf $artifactPath)
    SHA256 = $actualHash
    Validated = $true
    AndroidValidated = $androidValidated
    EvidenceComplete = $evidenceComplete
    RecoveryNote = if ($evidenceComplete) { "FPK, staged source manifest, and provenance agree." } else { "Legacy artifact: FPK checksum is valid, but staged source provenance is unavailable." }
}
if ($Json) {
    # Keep recovery automation independent from PowerShell formatting/version
    # differences.  The validation path above remains identical; only the
    # final representation changes.
    $result | ConvertTo-Json -Depth 4 -Compress
}
else {
    $result | Format-List
}

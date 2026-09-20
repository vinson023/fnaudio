[CmdletBinding()]
param(
    [string]$OutputRoot,
    [string]$AndroidSdkRoot
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Get-Sha256Hex {
    param([Parameter(Mandatory = $true)][string]$Path)
    $getFileHash = Get-Command -Name Get-FileHash -ErrorAction SilentlyContinue
    if ($getFileHash) {
        return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
    }
    $stream = [IO.File]::OpenRead($Path)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace("-", "").ToUpperInvariant()
    } finally {
        $algorithm.Dispose()
        $stream.Dispose()
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$androidRoot = Join-Path $repoRoot "android-client"
$version = (Get-Content -LiteralPath (Join-Path $repoRoot "VERSION") -Raw -Encoding UTF8).Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') {
    throw "VERSION must be a numeric semantic version; got '$version'."
}
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $repoRoot "artifacts"
}
$destination = Join-Path $OutputRoot $version
$artifactName = "fnaudio-android-$version-release.apk"
$artifactPath = Join-Path $destination $artifactName
$hashPath = Join-Path $destination "ANDROID_SHA256SUMS"
if ((Test-Path -LiteralPath $artifactPath) -or (Test-Path -LiteralPath $hashPath)) {
    throw "Android release artifact already exists: $artifactPath. Refusing to overwrite a same-version APK."
}

$requiredSigningVariables = @(
    "FNAUDIO_RELEASE_STORE_FILE",
    "FNAUDIO_RELEASE_STORE_PASSWORD",
    "FNAUDIO_RELEASE_KEY_ALIAS",
    "FNAUDIO_RELEASE_KEY_PASSWORD"
)
$missing = @($requiredSigningVariables | Where-Object { [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($_)) })
if ($missing.Count -gt 0) {
    throw "Release signing is required. Missing environment variables: $($missing -join ', ')."
}
$keystore = [Environment]::GetEnvironmentVariable("FNAUDIO_RELEASE_STORE_FILE")
if (-not (Test-Path -LiteralPath $keystore -PathType Leaf)) {
    throw "Release keystore does not exist: $keystore"
}

if (-not $AndroidSdkRoot) {
    $AndroidSdkRoot = [Environment]::GetEnvironmentVariable("ANDROID_SDK_ROOT")
}
if (-not $AndroidSdkRoot) {
    $propertiesPath = Join-Path $androidRoot "local.properties"
    if (Test-Path -LiteralPath $propertiesPath) {
        $sdkLine = Get-Content -LiteralPath $propertiesPath | Where-Object { $_ -match '^sdk\.dir=' } | Select-Object -First 1
        if ($sdkLine) { $AndroidSdkRoot = ($sdkLine -replace '^sdk\.dir=', '').Replace('\\', '\') }
    }
}
if (-not $AndroidSdkRoot -or -not (Test-Path -LiteralPath $AndroidSdkRoot -PathType Container)) {
    throw "Android SDK is required; set ANDROID_SDK_ROOT or pass -AndroidSdkRoot."
}

$buildToolsRoot = Join-Path $AndroidSdkRoot "build-tools"
$buildTools = Get-ChildItem -LiteralPath $buildToolsRoot -Directory -ErrorAction Stop |
    Sort-Object @{ Expression = {
        $parts = $_.Name -split '\.'
        try {
            [version]::new(
                [int]$parts[0],
                $(if ($parts.Count -gt 1) { [int]$parts[1] } else { 0 }),
                $(if ($parts.Count -gt 2) { [int]$parts[2] } else { 0 }),
                0)
        } catch {
            [version]::new(0, 0, 0, 0)
        }
    } } -Descending
$apksigner = $buildTools | ForEach-Object { Join-Path $_.FullName "apksigner.bat" } | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
$aapt = $buildTools | ForEach-Object { Join-Path $_.FullName "aapt.exe" } | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $apksigner -or -not $aapt) {
    throw "Android build-tools with apksigner.bat and aapt.exe are required."
}

Push-Location -LiteralPath $androidRoot
try {
    & .\gradlew.bat :app:assembleRelease
    if ($LASTEXITCODE -ne 0) { throw "Android release build failed with exit code $LASTEXITCODE." }
}
finally {
    Pop-Location
}

$builtApk = Join-Path $androidRoot "app\build\outputs\apk\release\app-release.apk"
if (-not (Test-Path -LiteralPath $builtApk -PathType Leaf)) {
    throw "Gradle completed without producing a release APK: $builtApk"
}
if ((Get-Item -LiteralPath $builtApk).Length -gt 1GB) {
    throw "Built APK exceeds the 1 GiB artifact limit."
}
& $apksigner verify --verbose --print-certs $builtApk
if ($LASTEXITCODE -ne 0) { throw "APK signature verification failed." }
$badging = & $aapt dump badging $builtApk
if ($LASTEXITCODE -ne 0) { throw "Unable to inspect APK manifest." }
$badgingText = $badging -join "`n"
if ($badgingText -notmatch "versionName='$([regex]::Escape($version))'") {
    throw "Release APK versionName does not match VERSION $version."
}

New-Item -ItemType Directory -Force -Path $destination | Out-Null
$temporaryArtifact = Join-Path $destination (".$artifactName.tmp-{0}" -f [guid]::NewGuid().ToString("N"))
$temporaryHashPath = Join-Path $destination ".ANDROID_SHA256SUMS.tmp-$([guid]::NewGuid().ToString('N'))"
$artifactMoved = $false
try {
    Copy-Item -LiteralPath $builtApk -Destination $temporaryArtifact
    $hash = Get-Sha256Hex -Path $temporaryArtifact
    Move-Item -LiteralPath $temporaryArtifact -Destination $artifactPath
    $artifactMoved = $true
    "$hash  $artifactName" | Set-Content -LiteralPath $temporaryHashPath -Encoding ASCII -NoNewline
    Move-Item -LiteralPath $temporaryHashPath -Destination $hashPath
}
catch {
    Remove-Item -LiteralPath $temporaryArtifact -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $temporaryHashPath -Force -ErrorAction SilentlyContinue
    if ($artifactMoved) {
        Remove-Item -LiteralPath $artifactPath -Force -ErrorAction SilentlyContinue
    }
    throw
}
# Keep the Android evidence separate from the FPK SHA256SUMS contract. Both
# release types can then live under the same version directory without making
# either verifier see an ambiguous checksum manifest.

[pscustomobject]@{
    Version = $version
    Artifact = $artifactPath
    SHA256 = $hash
    Signed = $true
    Validated = $true
}

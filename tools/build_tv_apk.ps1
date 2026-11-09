[CmdletBinding()]
param(
    [string]$OutputRoot,
    [string]$AndroidSdkRoot
)

# Builds the standalone television APKs: one per ARM ABI.
#
# Why a second script instead of a flag on build_android_release.ps1: the phone
# artifact and the TV artifacts are different products with different
# validation. The phone package must expose the launcher client; the TV package
# must expose ONLY the television entry, must carry exactly one ABI, and must be
# named so a viewer can tell which box it belongs to. Mixing those contracts in
# one script is how a phone APK ends up on a TV with the touch UI.
#
# Everything here is ASCII on purpose: Windows PowerShell 5.1 reads BOM-less
# files as ANSI.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\load_signing_env.ps1 -ThenBuildTv
#   ... or, with the four FNAUDIO_RELEASE_* variables already set in this process:
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_tv_apk.ps1

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
$hashPath = Join-Path $destination "TV_ANDROID_SHA256SUMS"

$variants = @(
    [pscustomobject]@{
        Task = ":app:assembleTvArm64"
        Directory = "tvArm64"
        BuiltApk = "app-tvArm64.apk"
        Abi = "arm64-v8a"
        ArtifactName = "fnaudio-tv-$version-arm64-v8a.apk"
    },
    [pscustomobject]@{
        Task = ":app:assembleTvArm32"
        Directory = "tvArm32"
        BuiltApk = "app-tvArm32.apk"
        Abi = "armeabi-v7a"
        ArtifactName = "fnaudio-tv-$version-armeabi-v7a.apk"
    }
)

foreach ($variant in $variants) {
    $artifactPath = Join-Path $destination $variant.ArtifactName
    if (Test-Path -LiteralPath $artifactPath) {
        throw "TV artifact already exists: $artifactPath. Refusing to overwrite a same-version APK."
    }
}
if (Test-Path -LiteralPath $hashPath) {
    throw "TV checksum manifest already exists: $hashPath. Refusing to overwrite it."
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
    $gradleArguments = @("--console=plain") + @($variants | ForEach-Object { $_.Task })
    & .\gradlew.bat @gradleArguments
    if ($LASTEXITCODE -ne 0) { throw "TV build failed with exit code $LASTEXITCODE." }
}
finally {
    Pop-Location
}

New-Item -ItemType Directory -Force -Path $destination | Out-Null
$results = @()
$hashRows = @()
$copied = @()
try {
    foreach ($variant in $variants) {
        $builtApk = Join-Path $androidRoot "app\build\outputs\apk\$($variant.Directory)\$($variant.BuiltApk)"
        if (-not (Test-Path -LiteralPath $builtApk -PathType Leaf)) {
            throw "Gradle completed without producing the expected TV APK: $builtApk"
        }
        & $apksigner verify --verbose --print-certs $builtApk
        if ($LASTEXITCODE -ne 0) { throw "APK signature verification failed for $($variant.Abi)." }

        $badgingText = (& $aapt dump badging $builtApk) -join "`n"
        if ($LASTEXITCODE -ne 0) { throw "Unable to inspect APK manifest: $builtApk" }
        if ($badgingText -notmatch "versionName='$([regex]::Escape($version))-tv'") {
            throw "TV APK versionName does not match $version-tv ($($variant.Abi))."
        }
        # The whole point of the standalone package: exactly one launcher entry,
        # and it is the television login. A phone entry here would put the touch
        # UI back on the screen the package exists to avoid.
        if ($badgingText -notmatch "launchable-activity: name='com\.fnaudio\.client\.tv\.TvLoginActivity'") {
            throw "TV APK does not expose the television launcher ($($variant.Abi))."
        }
        if ($badgingText -match "com\.fnaudio\.client\.ui\.LoginActivity") {
            throw "TV APK still exposes the phone launcher ($($variant.Abi))."
        }
        if ($badgingText -notmatch "native-code: '$($variant.Abi)'") {
            throw "TV APK does not carry the expected native ABI $($variant.Abi)."
        }
        foreach ($other in @($variants | Where-Object { $_.Abi -ne $variant.Abi })) {
            if ($badgingText -match [regex]::Escape("native-code: '$($other.Abi)'")) {
                throw "TV APK for $($variant.Abi) also carries $($other.Abi)."
            }
        }

        $artifactPath = Join-Path $destination $variant.ArtifactName
        Copy-Item -LiteralPath $builtApk -Destination $artifactPath
        $copied += $artifactPath
        $hash = Get-Sha256Hex -Path $artifactPath
        $size = (Get-Item -LiteralPath $artifactPath).Length
        $hashRows += "$hash  $($variant.ArtifactName)"
        $results += [pscustomobject]@{
            Abi = $variant.Abi
            Artifact = $artifactPath
            Bytes = $size
            SHA256 = $hash
        }
    }
    $temporaryHashPath = Join-Path $destination ".TV_ANDROID_SHA256SUMS.tmp-$([guid]::NewGuid().ToString('N'))"
    ($hashRows -join "`n") | Set-Content -LiteralPath $temporaryHashPath -Encoding ASCII -NoNewline
    Move-Item -LiteralPath $temporaryHashPath -Destination $hashPath
}
catch {
    foreach ($path in $copied) {
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    }
    throw
}

$results

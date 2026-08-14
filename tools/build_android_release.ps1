[CmdletBinding()]
param(
    [string]$OutputRoot,
    [string]$AndroidSdkRoot
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$androidRoot = Join-Path $repoRoot "android-client"
$version = (Get-Content -LiteralPath (Join-Path $repoRoot "VERSION") -Raw -Encoding UTF8).Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') {
    throw "VERSION must be a numeric semantic version; got '$version'."
}
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $repoRoot "artifacts"
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
$buildTools = Get-ChildItem -LiteralPath $buildToolsRoot -Directory -ErrorAction Stop | Sort-Object Name -Descending
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
& $apksigner verify --verbose --print-certs $builtApk
if ($LASTEXITCODE -ne 0) { throw "APK signature verification failed." }
$badging = & $aapt dump badging $builtApk
if ($LASTEXITCODE -ne 0) { throw "Unable to inspect APK manifest." }
$badgingText = $badging -join "`n"
if ($badgingText -notmatch "versionName='$([regex]::Escape($version))'") {
    throw "Release APK versionName does not match VERSION $version."
}

$destination = Join-Path $OutputRoot $version
New-Item -ItemType Directory -Force -Path $destination | Out-Null
$artifactName = "fnaudio-android-$version-release.apk"
$artifactPath = Join-Path $destination $artifactName
Copy-Item -LiteralPath $builtApk -Destination $artifactPath -Force
$hash = (Get-FileHash -LiteralPath $artifactPath -Algorithm SHA256).Hash
$hashPath = Join-Path $destination "SHA256SUMS"
$existing = if (Test-Path -LiteralPath $hashPath) { Get-Content -LiteralPath $hashPath -Encoding ASCII | Where-Object { $_ -notmatch "\s+$([regex]::Escape($artifactName))$" } } else { @() }
@($existing + "$hash  $artifactName") | Set-Content -LiteralPath $hashPath -Encoding ASCII

[pscustomobject]@{
    Version = $version
    Artifact = $artifactPath
    SHA256 = $hash
    Signed = $true
    Validated = $true
}

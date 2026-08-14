[CmdletBinding()]
param(
    [string]$OutputRoot,
    [string]$FnpackPath,
    [switch]$KeepStage
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$sourceRoot = Join-Path $repoRoot "src"
$version = (Get-Content -LiteralPath (Join-Path $repoRoot "VERSION") -Raw -Encoding UTF8).Trim()

if ($version -notmatch '^\d+\.\d+\.\d+$') {
    throw "VERSION must be a numeric semantic version; got '$version'."
}
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $repoRoot "artifacts"
}
if (-not $FnpackPath) {
    $FnpackPath = Join-Path $repoRoot "tools\fnpack.exe"
}
$FnpackPath = (Resolve-Path -LiteralPath $FnpackPath).Path

function Get-ManifestValue([string]$Text, [string]$Name) {
    $match = [regex]::Match($Text, "(?m)^\s*$([regex]::Escape($Name))\s*=\s*(.+?)\s*$")
    if (-not $match.Success) {
        throw "Missing '$Name' in src/manifest."
    }
    return $match.Groups[1].Value.Trim()
}

function Assert-Contains([string]$Text, [string]$Expected, [string]$File) {
    if (-not $Text.Contains($Expected)) {
        throw "$File does not contain expected value '$Expected'."
    }
}

function Assert-NonEmptyFile([string]$Path, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label is missing: $Path"
    }
    if ((Get-Item -LiteralPath $Path).Length -le 0) {
        throw "$Label is empty: $Path"
    }
}

function Read-JsonFile([string]$Path, [string]$Label) {
    Assert-NonEmptyFile $Path $Label
    try {
        return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        throw "$Label is not valid JSON: $Path ($($_.Exception.Message))"
    }
}

$manifestPath = Join-Path $sourceRoot "manifest"
$serverPath = Join-Path $sourceRoot "app\server\server.py"
$versionModulePath = Join-Path $sourceRoot "app\server\version.py"
$indexPath = Join-Path $sourceRoot "app\ui\index.html"
$gradlePath = Join-Path $repoRoot "android-client\app\build.gradle"
foreach ($path in @($sourceRoot, $manifestPath, $serverPath, $versionModulePath, $indexPath, $gradlePath)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required release input is missing: $path"
    }
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8
if ((Get-ManifestValue $manifest "appname") -ne "fnaudio") {
    throw "src/manifest appname must be fnaudio."
}
if ((Get-ManifestValue $manifest "version") -ne $version) {
    throw "VERSION and src/manifest version differ."
}
$serverSource = Get-Content -LiteralPath $serverPath -Raw -Encoding UTF8
Assert-Contains $serverSource "from version import APP_USER_AGENT" "src/app/server/server.py"
Assert-Contains $serverSource "server_version = APP_USER_AGENT" "src/app/server/server.py"
Assert-Contains (Get-Content -LiteralPath $versionModulePath -Raw -Encoding UTF8) 'APP_USER_AGENT = "fnAudio/%s" % APP_VERSION' "src/app/server/version.py"
$index = Get-Content -LiteralPath $indexPath -Raw -Encoding UTF8
Assert-Contains $index "app.css?v=__FNAUDIO_ASSET_BUILD__" "src/app/ui/index.html"
Assert-Contains $index "view_presentation.js?v=__FNAUDIO_ASSET_BUILD__" "src/app/ui/index.html"
Assert-Contains $index "app.js?v=__FNAUDIO_ASSET_BUILD__" "src/app/ui/index.html"

$gradle = Get-Content -LiteralPath $gradlePath -Raw -Encoding UTF8
if ($gradle -notmatch '(?m)^\s*versionCode\s+(\d+)\s*$') {
    throw "android-client/app/build.gradle must define a positive integer versionCode."
}
$versionCode = [int]$Matches[1]
if ($versionCode -lt 1) {
    throw "android-client/app/build.gradle versionCode must be positive."
}
Assert-Contains $gradle "versionName `"$version`"" "android-client/app/build.gradle"

$destination = Join-Path $OutputRoot $version
New-Item -ItemType Directory -Force -Path $destination | Out-Null
$artifactName = "fnaudio-$version-fnpack.fpk"
$artifactPath = Join-Path $destination $artifactName
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("fnaudio-release-" + [guid]::NewGuid().ToString("N"))
$stageRoot = Join-Path $temporaryRoot "src"
$inspectionRoot = Join-Path $temporaryRoot "inspect"

try {
    New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null
    # Build only from the authoritative source tree, omitting local bytecode, tests, and prior packages.
    & robocopy $sourceRoot $stageRoot /E /XD tests __pycache__ /XF fnaudio.fpk *.pyc | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "Failed to stage release source; robocopy exit code $LASTEXITCODE."
    }

    # Stamp the staged UI with a content-derived cache key. The authoritative
    # source retains a marker so a same-version rebuild cannot ship stale JS.
    $stageCssPath = Join-Path $stageRoot "app\ui\app.css"
    $stageJsPath = Join-Path $stageRoot "app\ui\app.js"
    $stagePresentationPath = Join-Path $stageRoot "app\ui\view_presentation.js"
    $stageIndexPath = Join-Path $stageRoot "app\ui\index.html"
    $assetHash = ((Get-FileHash -LiteralPath $stageCssPath -Algorithm SHA256).Hash + (Get-FileHash -LiteralPath $stagePresentationPath -Algorithm SHA256).Hash + (Get-FileHash -LiteralPath $stageJsPath -Algorithm SHA256).Hash).Substring(0, 12).ToLowerInvariant()
    $assetBuild = "$version-$assetHash"
    $stageIndex = Get-Content -LiteralPath $stageIndexPath -Raw -Encoding UTF8
    $stageIndex = $stageIndex.Replace("__FNAUDIO_ASSET_BUILD__", $assetBuild)
    if ($stageIndex.Contains("__FNAUDIO_ASSET_BUILD__")) {
        throw "Unable to stamp the staged UI asset build identifier."
    }
    Set-Content -LiteralPath $stageIndexPath -Value $stageIndex -Encoding UTF8 -NoNewline

    Push-Location -LiteralPath $stageRoot
    try {
        & $FnpackPath build --directory $stageRoot
        if ($LASTEXITCODE -ne 0) {
            throw "fnpack build failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
    $builtPackage = Join-Path $stageRoot "fnaudio.fpk"
    if (-not (Test-Path -LiteralPath $builtPackage)) {
        throw "fnpack completed without producing $builtPackage."
    }
    # Keep fnpack as the sole FPK producer. fnOS validates details of its
    # gzip container that must not be changed by a secondary archiver.
    Copy-Item -LiteralPath $builtPackage -Destination $artifactPath -Force

    New-Item -ItemType Directory -Force -Path $inspectionRoot | Out-Null
    tar -xf $artifactPath -C $inspectionRoot
    $requiredCommands = @(
        "config_callback",
        "config_init",
        "install_callback",
        "install_init",
        "main",
        "uninstall_callback",
        "uninstall_init",
        "upgrade_callback",
        "upgrade_init"
    )
    foreach ($commandName in $requiredCommands) {
        $commandPath = Join-Path $inspectionRoot "cmd\$commandName"
        Assert-NonEmptyFile $commandPath "Packaged lifecycle command '$commandName'"
        $commandText = Get-Content -LiteralPath $commandPath -Raw -Encoding UTF8
        if (-not $commandText.StartsWith("#!/bin/bash")) {
            throw "Packaged lifecycle command '$commandName' does not start with #!/bin/bash."
        }
    }
    $packageHeader = [System.IO.File]::ReadAllBytes($artifactPath)
    if ($packageHeader.Length -lt 2 -or $packageHeader[0] -ne 0x1f -or $packageHeader[1] -ne 0x8b) {
        throw "Packaged FPK must retain the gzip container required by fnOS."
    }

    $privilegePath = Join-Path $inspectionRoot "config\privilege"
    $privilege = Read-JsonFile $privilegePath "Packaged privilege config"
    if ($privilege.defaults.'run-as' -ne "root") {
        throw "Packaged config/privilege must declare defaults.run-as=root."
    }
    $resourcePath = Join-Path $inspectionRoot "config\resource"
    $resource = Read-JsonFile $resourcePath "Packaged resource config"
    $shareNames = @($resource.'data-share'.shares | ForEach-Object { $_.name })
    foreach ($requiredShare in @("fnaudio/music", "fnaudio/data")) {
        if ($shareNames -notcontains $requiredShare) {
            throw "Packaged config/resource is missing data share '$requiredShare'."
        }
    }

    $wizardRequirements = @{
        "install" = @("wizard_library_path", "wizard_server_port")
        "config" = @("wizard_server_port")
        "uninstall" = @("wizard_uninstall_mode")
    }
    foreach ($wizardName in $wizardRequirements.Keys) {
        $wizardPath = Join-Path $inspectionRoot "wizard\$wizardName"
        $wizard = Read-JsonFile $wizardPath "Packaged '$wizardName' wizard"
        if ($wizardName -ne "config" -and @($wizard).Count -eq 0) {
            throw "Packaged '$wizardName' wizard has no steps."
        }
        $wizardFields = @($wizard | ForEach-Object { $_.items } | ForEach-Object { $_.field })
        foreach ($requiredField in $wizardRequirements[$wizardName]) {
            if ($wizardFields -notcontains $requiredField) {
                throw "Packaged '$wizardName' wizard is missing field '$requiredField'."
            }
        }
    }

    $packagedManifest = Get-Content -LiteralPath (Join-Path $inspectionRoot "manifest") -Raw -Encoding UTF8
    if ((Get-ManifestValue $packagedManifest "version") -ne $version) {
        throw "Packaged manifest version differs from VERSION."
    }
    $payload = Join-Path $inspectionRoot "app.tgz"
    if (-not (Test-Path -LiteralPath $payload)) {
        throw "FPK payload app.tgz is missing."
    }
    $payloadRoot = Join-Path $inspectionRoot "app"
    New-Item -ItemType Directory -Force -Path $payloadRoot | Out-Null
    tar -xf $payload -C $payloadRoot
    foreach ($payloadRelativePath in @(
        "server\server.py",
        "server\version.py",
        "ui\index.html",
        "ui\index.cgi",
        "ui\cgi_proxy.py",
        "ui\config",
        "ui\service_port.json",
        "target\bin\mpd"
    )) {
        Assert-NonEmptyFile (Join-Path $payloadRoot $payloadRelativePath) "Packaged app payload"
    }
    $packagedServer = Get-Content -LiteralPath (Join-Path $payloadRoot "server\server.py") -Raw -Encoding UTF8
    Assert-Contains $packagedServer "server_version = APP_USER_AGENT" "packaged server/server.py"
    Assert-Contains (Get-Content -LiteralPath (Join-Path $payloadRoot "server\version.py") -Raw -Encoding UTF8) 'APP_USER_AGENT = "fnAudio/%s" % APP_VERSION' "packaged server/version.py"
    $packagedIndex = Get-Content -LiteralPath (Join-Path $payloadRoot "ui\index.html") -Raw -Encoding UTF8
    Assert-Contains $packagedIndex "app.css?v=$assetBuild" "packaged ui/index.html"
    Assert-Contains $packagedIndex "view_presentation.js?v=$assetBuild" "packaged ui/index.html"
    Assert-Contains $packagedIndex "app.js?v=$assetBuild" "packaged ui/index.html"
    if (Test-Path -LiteralPath (Join-Path $payloadRoot "tests")) {
        throw "FPK payload unexpectedly contains test sources."
    }
    if (Get-ChildItem -LiteralPath $payloadRoot -Recurse -Filter "*.pyc" -Force | Select-Object -First 1) {
        throw "FPK payload unexpectedly contains Python bytecode."
    }

    $sha256 = (Get-FileHash -LiteralPath $artifactPath -Algorithm SHA256).Hash.ToUpperInvariant()
    $shaPath = Join-Path $destination "SHA256SUMS"
    "$sha256  $artifactName" | Set-Content -LiteralPath $shaPath -Encoding ASCII
    [pscustomobject]@{
        Version = $version
        Artifact = $artifactPath
        SHA256 = $sha256
        Validated = $true
    } | Format-List
}
finally {
    if ($KeepStage) {
        Write-Host "Retained temporary release stage: $temporaryRoot"
    }
    elseif (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

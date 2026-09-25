[CmdletBinding()]
param(
    [string]$OutputRoot,
    [string]$FnpackPath,
    [switch]$KeepStage,
    [switch]$AllowExistingArtifact
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
$fnpackSha256 = Get-Sha256Hex -Path $FnpackPath

function Get-ManifestKeyPattern([string]$Name) {
    # The one key shape every reader below shares. Two rules are baked in here, and
    # both come from a build that broke:
    #  * [ \t] rather than \s, because \s also matches newlines: a blank-valued key
    #    made the old match resume on the NEXT line and answer with that neighbour
    #    (build_beta_fpk.ps1 lost this in R177).
    #  * whitespace on BOTH sides of the equals sign, because fnpack rewrites every
    #    manifest it packs with column-aligned keys ("install_type          = root").
    #    A compact "key=" pattern matches the source tree and never finds the key in
    #    the package, which is what killed the 0.2.35 release build.
    return "(?m)^[ \t]*$([regex]::Escape($Name))[ \t]*="
}

function Find-ManifestValue([string]$Text, [string]$Name) {
    # Extends the shared key shape with a value group that cannot cross the line.
    # The value stops at the line, and the optional carriage return lets it stop
    # cleanly there: the manifest inside a packed FPK ends its lines with CRLF, so a
    # bare end-of-line assertion matched nothing and the build reported a missing
    # version key it could plainly see in the package.
    return [regex]::Match($Text, ((Get-ManifestKeyPattern $Name) + "[ \t]*([^\r\n]*?)[ \t]*\r?$"))
}

function Get-ManifestValue([string]$Text, [string]$Name) {
    $match = Find-ManifestValue $Text $Name
    if (-not $match.Success -or $match.Groups[1].Value.Trim() -eq '') {
        throw "Missing '$Name' in src/manifest."
    }
    return $match.Groups[1].Value.Trim()
}

function Test-ManifestKey([string]$Text, [string]$Name) {
    # A key line counts even when its value is blank: padding a blank value with the
    # spaces fnpack aligns with must not turn a declaration into an absence.
    return [regex]::IsMatch($Text, (Get-ManifestKeyPattern $Name))
}

function Assert-PackagedInstallTarget([string]$SourceText, [string]$PackagedText) {
    # install_type decides which partition fnOS puts the app on, so a package that
    # quietly loses or gains it is not the application the source tree describes.
    $sourceDeclared = Test-ManifestKey $SourceText "install_type"
    $packagedDeclared = Test-ManifestKey $PackagedText "install_type"
    if ($sourceDeclared -ne $packagedDeclared) {
        throw "Packaged manifest install_type presence differs from src/manifest."
    }
    # The value is only compared once both sides have a key line, and it is read with
    # the blank-tolerant finder: Get-ManifestValue would throw for a legitimate unset
    # or blank-valued build (R177 lesson).
    if ($sourceDeclared) {
        $sourceTarget = (Find-ManifestValue $SourceText "install_type").Groups[1].Value.Trim()
        $packagedTarget = (Find-ManifestValue $PackagedText "install_type").Groups[1].Value.Trim()
        if ($packagedTarget -ne $sourceTarget) {
            throw "Packaged manifest install_type differs from src/manifest."
        }
    }
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

function Get-SourceManifestLines([string]$Root) {
    $baseLength = $Root.TrimEnd([char]'\', [char]'/' ).Length + 1
    return @(
        Get-ChildItem -LiteralPath $Root -Recurse -File -Force |
            Where-Object { $_.Name -ne "fnaudio.fpk" } |
            Sort-Object FullName |
            ForEach-Object {
                $relative = $_.FullName.Substring($baseLength).Replace("\", "/")
                $hash = Get-Sha256Hex -Path $_.FullName
                "$hash  $relative"
            }
    )
}

function Get-StampedUiAssetPaths([string]$IndexText, [string]$UiRoot) {
    # The HTML template is the source of truth for hashed local CSS/JS.
    # Keeping this discovery dynamic prevents a newly split presentation
    # module from silently escaping a same-version cache-busting build.
    $root = (Resolve-Path -LiteralPath $UiRoot).Path
    $assets = [System.Collections.Generic.List[string]]::new()
    foreach ($match in [regex]::Matches($IndexText, '(?i)(?:src|href)="([^"]+)\?v=__FNAUDIO_ASSET_BUILD__"')) {
        $relative = $match.Groups[1].Value.Replace("\", "/")
        if ($relative -notmatch '^[A-Za-z0-9][A-Za-z0-9._/-]*\.(?:css|js)$' -or $relative.Split("/") -contains "..") {
            throw "Invalid stamped UI asset path in index.html: $relative"
        }
        $path = Join-Path $root ($relative.Replace("/", "\"))
        Assert-NonEmptyFile $path "Stamped UI asset '$relative'"
        $assets.Add($relative)
    }
    $result = @($assets | Sort-Object -Unique)
    if ($result.Count -eq 0) {
        throw "src/app/ui/index.html has no stamped local CSS/JS assets."
    }
    # A local stylesheet or script referenced without the asset-build stamp keeps
    # a stable URL across releases, so an in-place upgrade can serve cached, stale
    # JS/CSS. Staging copies the whole UI tree, so packaging alone cannot notice
    # the omission; fail the build here instead.
    foreach ($reference in [regex]::Matches($IndexText, '(?i)(?:src|href)="([^"?#]+\.(?:css|js))"')) {
        $relative = $reference.Groups[1].Value.Replace("\", "/")
        if ($relative -match '^(?:[A-Za-z][A-Za-z0-9+.-]*:)?//') { continue }
        throw "index.html references local UI asset without the build stamp: $relative"
    }

    return $result
}

function Get-GitProvenance([string]$Root) {
    # Keep the release recovery record explicit when an exported source tree
    # is built outside a Git checkout.  An empty commit plus a null boolean
    # was technically sufficient, but indistinguishable from an interrupted
    # Git probe once the original build session had been deleted.
    $result = [ordered]@{ commit = ""; worktree_dirty = $null; status = "unavailable" }
    try {
        $commit = (& git -C $Root rev-parse HEAD 2>$null).Trim()
        if ($LASTEXITCODE -eq 0 -and $commit) {
            $result.commit = $commit
            $result.status = "commit_only"
        }
        $status = @(& git -C $Root status --porcelain=v1 --untracked-files=normal 2>$null)
        if ($LASTEXITCODE -eq 0) {
            $result.worktree_dirty = $status.Count -gt 0
            $result.status = if ($result.worktree_dirty) { "dirty" } else { "clean" }
        }
    }
    catch {
        # A source export can be packaged outside Git. The staged manifest
        # remains authoritative even when commit metadata is unavailable.
    }
    return $result
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
$sourceStampedAssets = Get-StampedUiAssetPaths $index (Join-Path $sourceRoot "app\ui")

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
$publicationNames = @(
    $artifactName,
    "SHA256SUMS",
    "SOURCE_MANIFEST.sha256",
    "SOURCE_PROVENANCE.json"
)
if (-not $AllowExistingArtifact) {
    foreach ($publicationName in $publicationNames) {
        $publicationPath = Join-Path $destination $publicationName
        # A sidecar without its artifact is still a release collision. Allowing
        # the build to proceed would publish a misleading half-old/half-new
        # evidence set if a later Move-Item happened to succeed.
        if (Test-Path -LiteralPath $publicationPath) {
            throw "Release output already exists: $publicationPath. Refusing to overwrite; pass -AllowExistingArtifact only for an intentional rebuild."
        }
    }
}
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("fnaudio-release-" + [guid]::NewGuid().ToString("N"))
$stageRoot = Join-Path $temporaryRoot "src"
$inspectionRoot = Join-Path $temporaryRoot "inspect"
$publishRoot = Join-Path $temporaryRoot "publish"
$publishedPaths = [System.Collections.Generic.List[string]]::new()
$publicationBackups = [System.Collections.Generic.List[object]]::new()

try {
    New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null
    # Build only from the authoritative source tree, omitting local bytecode, tests, and prior packages.
    & robocopy $sourceRoot $stageRoot /E /XD tests __pycache__ /XF fnaudio.fpk *.pyc | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "Failed to stage release source; robocopy exit code $LASTEXITCODE."
    }

    # Stamp the staged UI with a content-derived cache key. The authoritative
    # source retains a marker so a same-version rebuild cannot ship stale JS.
    $stageUiRoot = Join-Path $stageRoot "app\ui"
    $stageIndexPath = Join-Path $stageRoot "app\ui\index.html"
    $stageIndex = Get-Content -LiteralPath $stageIndexPath -Raw -Encoding UTF8
    $stagedStampedAssets = Get-StampedUiAssetPaths $stageIndex $stageUiRoot
    if ((@($sourceStampedAssets) -join "`n") -ne (@($stagedStampedAssets) -join "`n")) {
        throw "Staged UI asset set differs from the authoritative index.html."
    }
    $assetHashInput = @($stagedStampedAssets | ForEach-Object {
        Get-Sha256Hex -Path (Join-Path $stageUiRoot ($_.Replace("/", "\")))
    }) -join ""
    $assetHash = $assetHashInput.Substring(0, 12).ToLowerInvariant()
    $assetBuild = "$version-$assetHash"
    $stageIndex = $stageIndex.Replace("__FNAUDIO_ASSET_BUILD__", $assetBuild)
    if ($stageIndex.Contains("__FNAUDIO_ASSET_BUILD__")) {
        throw "Unable to stamp the staged UI asset build identifier."
    }
    Set-Content -LiteralPath $stageIndexPath -Value $stageIndex -Encoding UTF8 -NoNewline
    # The FPK is built from this temporary staged tree, not directly from the
    # developer worktree. Record exact staged inputs beside the release so a
    # deleted session or an old NAS artifact can be reproduced without
    # guessing which uncommitted source files participated in the build.
    $sourceManifestLines = Get-SourceManifestLines $stageRoot
    $sourceManifestText = (($sourceManifestLines -join "`n") + "`n")
    # Keep all evidence and the package outside the final version directory
    # until every inspection below has succeeded. A failed build must not
    # leave an unvalidated artifact that blocks or misleads a later retry.
    New-Item -ItemType Directory -Force -Path $publishRoot | Out-Null
    $sourceManifestPath = Join-Path $publishRoot "SOURCE_MANIFEST.sha256"
    Set-Content -LiteralPath $sourceManifestPath -Value $sourceManifestText -Encoding ASCII -NoNewline
    $sourceManifestSha256 = Get-Sha256Hex -Path $sourceManifestPath
    $gitProvenance = Get-GitProvenance $repoRoot
    $provenancePath = Join-Path $publishRoot "SOURCE_PROVENANCE.json"
    [ordered]@{
        schema = 1
        version = $version
        generated_utc = [DateTime]::UtcNow.ToString("o")
        asset_build = $assetBuild
        staged_file_count = $sourceManifestLines.Count
        source_manifest_sha256 = $sourceManifestSha256
        fnpack_sha256 = $fnpackSha256
        artifact_sha256 = ""
        git_commit = $gitProvenance.commit
        git_worktree_dirty = $gitProvenance.worktree_dirty
        git_provenance_status = $gitProvenance.status
    } | ConvertTo-Json | Set-Content -LiteralPath $provenancePath -Encoding UTF8

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
    # Keep generated packages within the App Center remote-package limit
    # before copying, unpacking, or hashing the artifact for provenance.
    if ((Get-Item -LiteralPath $builtPackage).Length -gt 10GB) {
        throw "Built FPK exceeds the 10 GiB artifact limit."
    }
    # Keep fnpack as the sole FPK producer. fnOS validates details of its
    # gzip container that must not be changed by a secondary archiver.
    $temporaryArtifactPath = Join-Path $publishRoot $artifactName
    Copy-Item -LiteralPath $builtPackage -Destination $temporaryArtifactPath

    New-Item -ItemType Directory -Force -Path $inspectionRoot | Out-Null
    tar -xf $temporaryArtifactPath -C $inspectionRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect the built FPK with tar; exit code $LASTEXITCODE."
    }
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
    $packageHeader = New-Object byte[] 2
    $packageStream = [System.IO.File]::OpenRead($temporaryArtifactPath)
    try {
        $packageHeaderRead = $packageStream.Read($packageHeader, 0, $packageHeader.Length)
    }
    finally {
        $packageStream.Dispose()
    }
    if ($packageHeaderRead -lt 2 -or $packageHeader[0] -ne 0x1f -or $packageHeader[1] -ne 0x8b) {
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

    # The package must carry the identity the source declares.  Comparing against
    # $manifest instead of literals keeps src/manifest the single source of truth, so
    # an identity change is made in exactly one place and every tree is still pinned.
    foreach ($identityKey in @("appname", "developer", "publisher", "maintainer", "distributor")) {
        if ((Get-ManifestValue $packagedManifest $identityKey) -ne (Get-ManifestValue $manifest $identityKey)) {
            throw "Packaged manifest '$identityKey' differs from src/manifest."
        }
    }
    # install_type decides the install partition, so the package has to carry the same
    # declaration the source tree makes, in whichever shape the packager rewrites it to.
    Assert-PackagedInstallTarget $manifest $packagedManifest
    $payload = Join-Path $inspectionRoot "app.tgz"
    if (-not (Test-Path -LiteralPath $payload)) {
        throw "FPK payload app.tgz is missing."
    }
    $payloadRoot = Join-Path $inspectionRoot "app"
    New-Item -ItemType Directory -Force -Path $payloadRoot | Out-Null
    tar -xf $payload -C $payloadRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect the packaged app payload with tar; exit code $LASTEXITCODE."
    }
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
    foreach ($assetRelativePath in $stagedStampedAssets) {
        Assert-NonEmptyFile (Join-Path $payloadRoot ("ui\" + $assetRelativePath.Replace("/", "\"))) "Packaged stamped UI asset '$assetRelativePath'"
        Assert-Contains $packagedIndex "${assetRelativePath}?v=$assetBuild" "packaged ui/index.html"
    }
    if (Test-Path -LiteralPath (Join-Path $payloadRoot "tests")) {
        throw "FPK payload unexpectedly contains test sources."
    }
    if (Get-ChildItem -LiteralPath $payloadRoot -Recurse -Filter "*.pyc" -Force | Select-Object -First 1) {
        throw "FPK payload unexpectedly contains Python bytecode."
    }

    $sha256 = Get-Sha256Hex -Path $temporaryArtifactPath
    $shaPath = Join-Path $publishRoot "SHA256SUMS"
    "$sha256  $artifactName" | Set-Content -LiteralPath $shaPath -Encoding ASCII
    if ((Get-Content -LiteralPath $shaPath -Raw -Encoding ASCII).Trim() -ne "$sha256  $artifactName") {
        throw "Release SHA256SUMS does not match the final FPK."
    }
    $provenance = Read-JsonFile $provenancePath "Release source provenance"
    $provenance.artifact_sha256 = $sha256
    $provenance | ConvertTo-Json | Set-Content -LiteralPath $provenancePath -Encoding UTF8
    Assert-NonEmptyFile $sourceManifestPath "Release source manifest"
    $provenance = Read-JsonFile $provenancePath "Release source provenance"
    if ([int]$provenance.schema -ne 1 -or $provenance.version -ne $version -or [int]$provenance.staged_file_count -lt 1) {
        throw "Release source provenance is incomplete or has the wrong version."
    }
    if ($provenance.source_manifest_sha256 -ne $sourceManifestSha256) {
        throw "Release source provenance does not match the staged source manifest."
    }
    if ([string]$provenance.fnpack_sha256 -notmatch '^[A-F0-9]{64}$') {
        throw "Release source provenance is missing a valid fnpack SHA-256."
    }
    if ([string]$provenance.artifact_sha256 -notmatch '^[A-F0-9]{64}$' -or $provenance.artifact_sha256 -ne $sha256) {
        throw "Release source provenance does not match the final FPK SHA-256."
    }
    if ([string]$provenance.git_provenance_status -notin @("clean", "dirty", "commit_only", "unavailable")) {
        throw "Release source provenance has an invalid Git provenance status."
    }
    # Publish only after package structure, payload, checksum, and provenance
    # have all been verified in the isolated temporary directory.
    if ($AllowExistingArtifact) {
        $backupRoot = Join-Path $temporaryRoot "previous-publication"
        New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
        foreach ($publicationName in $publicationNames) {
            $existingPath = Join-Path $destination $publicationName
            if (Test-Path -LiteralPath $existingPath) {
                $backupPath = Join-Path $backupRoot $publicationName
                Copy-Item -LiteralPath $existingPath -Destination $backupPath -Force
                $publicationBackups.Add([pscustomobject]@{
                    Original = $existingPath
                    Backup = $backupPath
                })
            }
        }
    }
    Move-Item -LiteralPath $temporaryArtifactPath -Destination $artifactPath -Force
    $publishedPaths.Add($artifactPath)
    $publishedManifestPath = Join-Path $destination "SOURCE_MANIFEST.sha256"
    $publishedShaPath = Join-Path $destination "SHA256SUMS"
    $publishedProvenancePath = Join-Path $destination "SOURCE_PROVENANCE.json"
    Move-Item -LiteralPath $sourceManifestPath -Destination $publishedManifestPath -Force
    $publishedPaths.Add($publishedManifestPath)
    Move-Item -LiteralPath $shaPath -Destination $publishedShaPath -Force
    $publishedPaths.Add($publishedShaPath)
    Move-Item -LiteralPath $provenancePath -Destination $publishedProvenancePath -Force
    $publishedPaths.Add($publishedProvenancePath)
    [pscustomobject]@{
        Version = $version
        Artifact = $artifactPath
        SHA256 = $sha256
        SourceManifest = $publishedManifestPath
        Provenance = $publishedProvenancePath
        Validated = $true
    } | Format-List
}
catch {
    # With the normal collision policy these paths did not exist before this
    # build. Remove only files moved by this invocation so a failed publish
    # cannot leave an artifact that blocks a clean retry or misleads recovery.
    if ($publishedPaths) {
        foreach ($publishedPath in $publishedPaths) {
            Remove-Item -LiteralPath $publishedPath -Force -ErrorAction SilentlyContinue
        }
    }
    if ($publicationBackups) {
        foreach ($publicationBackup in $publicationBackups) {
            Copy-Item -LiteralPath $publicationBackup.Backup -Destination $publicationBackup.Original -Force -ErrorAction SilentlyContinue
        }
    }
    throw
}
finally {
    if ($KeepStage) {
        Write-Host "Retained temporary release stage: $temporaryRoot"
    }
    elseif (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

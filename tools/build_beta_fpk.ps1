[CmdletBinding()]
param(
    # The beta keeps its own App Center identity. ``fnaudio-beta`` is a proven
    # legal appname shape (docker-xunlei, trim.text-editor are installed with
    # hyphens/dots), and it never resolves to /var/apps/fnaudio or to the
    # reserved official @appconf/trim.music namespace.
    [string]$AppName = 'fnaudio-beta',
    # fnOS derives the service account from manifest.appname unless config
    # /privilege overrides it; that override is what "the application account"
    # means on the platform, so the requested name lands here.
    [string]$AppUser = 'trim.music',
    # Developer and publisher are Chinese text that only travels inside the
    # manifest, never inside this script: a BOM-less .ps1 is read as ANSI by
    # Windows PowerShell 5.1, so a literal here would arrive mangled. The name is
    # built from its code points instead, the same trick $betaTag uses below.
    [string]$Developer = ([string][char]0x98DE + [string][char]0x725B),
    [string]$Publisher = ([string][char]0x98DE + [string][char]0x725B),
    # Install target, matching the platform manifest contract:
    #   root   -> manifest keeps install_type=root (system partition)
    #   unset  -> the key is dropped, so fnOS asks for a storage volume
    [string]$InstallType = 'root',
    [string]$DisplayName = 'fnAudio BETA',
    [int]$ServicePort = 53299,
    [string]$SharePrefix = 'fnaudio-beta',
    [string]$BetaSuffix = 'beta.1',
    [string]$LibraryPath = '/vol1/1000/fnaudio-beta-music',
    [string]$OutputRoot,
    [string]$FnpackPath,
    [switch]$KeepStage,
    [switch]$AllowExistingArtifact,
    [switch]$NoBadge
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Get-Sha256Hex {
    param([Parameter(Mandatory = $true)][string]$Path)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try {
        return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-', '').ToUpperInvariant()
    }
    finally {
        $stream.Dispose()
        $algorithm.Dispose()
    }
}

function Read-TextFile {
    param([string]$Path)
    $bytes = [IO.File]::ReadAllBytes($Path)
    $hasBom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
    $offset = 0
    if ($hasBom) { $offset = 3 }
    return [pscustomobject]@{
        Text   = [Text.Encoding]::UTF8.GetString($bytes, $offset, $bytes.Length - $offset)
        HasBom = $hasBom
        Bytes  = $bytes
    }
}

function Write-TextFile {
    param([string]$Path, [string]$Text, [bool]$HasBom)
    $encoding = New-Object Text.UTF8Encoding($HasBom)
    [IO.File]::WriteAllText($Path, $Text, $encoding)
}

function Test-BinaryFile {
    param([string]$Path)
    $stream = [IO.File]::OpenRead($Path)
    try {
        $length = [Math]::Min(8192, $stream.Length)
        $buffer = New-Object byte[] $length
        if ($length -gt 0) { $stream.Read($buffer, 0, $length) | Out-Null }
        return ($buffer -contains 0)
    }
    finally {
        $stream.Dispose()
    }
}

function Get-ManifestValue {
    param([string]$Text, [string]$Name)
    # Whitespace around the assignment is matched as [ \t], not \s: \s also covers
    # newlines, so a key with an empty value let the match resume on the NEXT line and
    # this reader handed back an unrelated key instead of the blank value that is
    # actually there.  The value itself stops at the line break for the same reason.
    $match = [regex]::Match($Text, "(?m)^[ \t]*$([regex]::Escape($Name))[ \t]*=[ \t]*([^\r\n]*)")
    if (-not $match.Success) { throw "manifest is missing the '$Name' key." }
    return $match.Groups[1].Value.Trim().Trim('"')
}

function Set-ManifestValue {
    param([string]$Text, [string]$Name, [string]$Value)
    $pattern = "(?m)^([ \t]*$([regex]::Escape($Name))[ \t]*=[ \t]*)(.*)([ \t]*)$"
    if ($Text -notmatch $pattern) { throw "manifest is missing the '$Name' key; refusing to guess where to add it." }
    $evaluator = { param($match) $match.Groups[1].Value + $Value + $match.Groups[4].Value }
    return [regex]::Replace($Text, $pattern, $evaluator)
}

function Remove-ManifestKey {
    param([string]$Text, [string]$Name)
    # The comment run directly above the key belongs to it: deleting only the
    # assignment would leave prose standing in a package that no longer declares it.
    # As in the reader, the whitespace around '=' is horizontal only, so an empty value
    # cannot make the match reach onto the following line.
    $pattern = '(?m)(?:^#[^\r\n]*\r?\n)*^' + [regex]::Escape($Name) + '[ \t]*=[^\r\n]*\r?\n?'
    return [regex]::Replace($Text, $pattern, '')
}

function Get-ManifestInstallTypeViolations {
    param([string]$Text, [string]$Expected, [string]$Label)
    # The platform spells "let the user pick a storage volume" by leaving the key
    # out, so this check cannot ride on the expectation table below: Get-ManifestValue
    # turns a missing key into an exception, and an exception here would lose the
    # [$Label] prefix that says which of the three trees failed while skipping every
    # remaining check of that tree. An empty assignment is reported too: the platform
    # accepts it, but this packager only ever writes 'root' or deletes the key, so
    # seeing one means the deletion path stopped removing something.
    $violations = [System.Collections.Generic.List[string]]::new()
    $declared = [regex]::Match($Text, '(?m)^[ \t]*install_type[ \t]*=[ \t]*([^\r\n]*)')
    if ($Expected -ceq 'root') {
        if (-not $declared.Success) { $violations.Add("[$Label] manifest does not declare install_type although -InstallType is 'root'") | Out-Null }
        elseif ($declared.Groups[1].Value.Trim() -cne 'root') { $violations.Add("[$Label] manifest install_type is '$($declared.Groups[1].Value.Trim())', expected 'root'") | Out-Null }
    }
    elseif ($declared.Success) { $violations.Add("[$Label] manifest still declares install_type although -InstallType is '$Expected'") | Out-Null }
    return $violations
}

function Assert-Condition {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}
# ---------------------------------------------------------------------------
# Parameter validation. Every check below protects the "never mix the beta
# with the production release" requirement, so they are hard failures rather
# than warnings.
# ---------------------------------------------------------------------------
Assert-Condition ($AppName -cmatch '^[A-Za-z][A-Za-z0-9._-]*$') "AppName must look like an fnOS appname; got '$AppName'."
Assert-Condition ($AppName -cne 'fnaudio') "AppName must not be the production appname 'fnaudio'."
Assert-Condition ($AppName -cne 'trim.music') "AppName must not squat the reserved first-party namespace trim.music (the NAS already carries @appconf/trim.music)."
Assert-Condition ($AppUser -cne 'fnaudio') "AppUser must not be the production service account 'fnaudio'."
Assert-Condition ($AppUser -cmatch '^[A-Za-z][A-Za-z0-9._-]*$') "AppUser must look like a Linux account name; got '$AppUser'."
Assert-Condition ($SharePrefix -cmatch '^[A-Za-z][A-Za-z0-9._-]*$') "SharePrefix must be a plain share name; got '$SharePrefix'."
Assert-Condition ($SharePrefix -cnotmatch 'fnaudio$') "SharePrefix must differ from the production share root."
Assert-Condition ($ServicePort -ge 1024 -and $ServicePort -le 65535) "ServicePort must stay within 1024-65535; got $ServicePort."
Assert-Condition ($ServicePort.ToString() -cne '53199') "ServicePort must differ from the production port 53199."
# cmd/main rejects any persisted port that is seven characters or longer, so a
# beta port that rewrites into a longer literal would silently fall back to the
# production default.
Assert-Condition ($ServicePort.ToString().Length -lt 7) "ServicePort must stay below seven digits so the cmd/main length guard keeps it."
# The wizard pre-fills the music directory, so a beta that keeps the
# production default would index (and re-tag) the very same library.
Assert-Condition ($LibraryPath -cmatch '^/vol[0-9]+/[A-Za-z0-9._/-]+$') "LibraryPath must be an absolute NAS volume path; got '$LibraryPath'."
Assert-Condition ($LibraryPath -cne '/vol1/1000/music') "LibraryPath must differ from the production default music directory."

foreach ($name in @($Developer, $Publisher, $DisplayName)) {
    Assert-Condition ($name.Trim().Length -gt 0) 'Developer, Publisher and DisplayName must not be blank.'
}
# The platform only knows two install targets, and the empty one is spelled by
# omitting the key, so the accepted set is written out instead of passing text on.
Assert-Condition ($InstallType -ceq 'root' -or $InstallType -ceq 'unset') "InstallType must be 'root' (system partition) or 'unset' (ask for a volume); got '$InstallType'."

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$sourceRoot = Join-Path $repoRoot 'src'
$productionVersion = (Get-Content -LiteralPath (Join-Path $repoRoot 'VERSION') -Raw -Encoding UTF8).Trim()
$betaVersion = "$productionVersion-$BetaSuffix"
Assert-Condition ($betaVersion -match '^\d+\.\d+\.\d+-[A-Za-z0-9.]+(-\d+)?$') "Beta version '$betaVersion' must stay recognisable to fnOS."
if (-not $OutputRoot) { $OutputRoot = Join-Path $repoRoot 'artifacts' }
if (-not $FnpackPath) { $FnpackPath = Join-Path $repoRoot 'tools\fnpack.exe' }
$FnpackPath = (Resolve-Path -LiteralPath $FnpackPath).Path
$betaTag = [string][char]0x3010 + 'BETA' + [string][char]0x3011

foreach ($required in @($sourceRoot, (Join-Path $sourceRoot 'manifest'), (Join-Path $sourceRoot 'app\ui\index.html'), (Join-Path $sourceRoot 'app\server\server.py'))) {
    Assert-Condition (Test-Path -LiteralPath $required) "Required build input is missing: $required"
}

# ---------------------------------------------------------------------------
# Identity rewrite table. Patterns are boundary aware on purpose: the beta
# appname itself starts with the production token, so an unanchored search
# would either loop or report a false leftover.
# ---------------------------------------------------------------------------
$displayScope = @(
    'cmd/config_callback', 'cmd/config_init', 'cmd/install_callback', 'cmd/main',
    'cmd/uninstall_callback', 'cmd/upgrade_callback',
    'wizard/config', 'wizard/install', 'wizard/uninstall', 'app/ui/config'
)
$identityRules = @(
    [pscustomobject]@{ Name = 'runtime-path';        Pattern = '/var/apps/fnaudio(?![\-A-Za-z0-9_.])';        Replacement = "/var/apps/$AppName";        Scope = '*' }
    [pscustomobject]@{ Name = 'legacy-package-path'; Pattern = '/var/packages/fnaudio(?![\-A-Za-z0-9_.])';    Replacement = "/var/packages/$AppName";    Scope = '*' }
    [pscustomobject]@{ Name = 'app-registration';    Pattern = '(@app(?:conf|data|center)/)fnaudio(?![\-A-Za-z0-9_.])'; Replacement = "`${1}$AppName"; Scope = '*' }
    [pscustomobject]@{ Name = 'cgi-entrypoint';      Pattern = '(ThirdParty\\?/)fnaudio(?![\-A-Za-z0-9_.])';  Replacement = "`${1}$AppName";           Scope = '*' }
    [pscustomobject]@{ Name = 'launch-entry-id';     Pattern = '\bfnaudio(?=\.Application)';                  Replacement = $AppName;                  Scope = '*' }
    [pscustomobject]@{ Name = 'process-sweep';       Pattern = '"fnaudio"';                                   Replacement = "`"$AppName`"";             Scope = @('cmd/main') }
    [pscustomobject]@{ Name = 'data-share';          Pattern = '"fnaudio/';                                   Replacement = "`"$SharePrefix/";           Scope = @('config/resource') }
    [pscustomobject]@{ Name = 'library-default';       Pattern = '/vol1/1000/music(?![\w./-])';                     Replacement = $LibraryPath;               Scope = @('wizard/install', 'app/ui/app.js') }
    [pscustomobject]@{ Name = 'display-name';        Pattern = 'fnAudio';                                     Replacement = $DisplayName;              Scope = $displayScope }
    [pscustomobject]@{ Name = 'service-port';        Pattern = '(?<![0-9])53199(?![0-9])';                    Replacement = "$ServicePort";            Scope = '*' }
)
function Get-StampedUiAssetPaths {
    param([string]$IndexText, [string]$UiRoot)
    $root = (Resolve-Path -LiteralPath $UiRoot).Path
    $assets = [System.Collections.Generic.List[string]]::new()
    foreach ($match in [regex]::Matches($IndexText, '(?i)(?:src|href)="([^"]+)\?v=__FNAUDIO_ASSET_BUILD__"')) {
        $relative = $match.Groups[1].Value.Replace('\', '/')
        if ($relative -notmatch '^[A-Za-z0-9][A-Za-z0-9._/-]*\.(?:css|js)$' -or $relative.Split('/') -contains '..') {
            throw "Invalid stamped UI asset path in index.html: $relative"
        }
        $path = Join-Path $root ($relative.Replace('/', '\'))
        Assert-Condition ((Test-Path -LiteralPath $path -PathType Leaf) -and ((Get-Item -LiteralPath $path).Length -gt 0)) "Stamped UI asset is missing or empty: $relative"
        $assets.Add($relative)
    }
    $result = @($assets | Sort-Object -Unique)
    Assert-Condition ($result.Count -gt 0) 'app/ui/index.html has no stamped local CSS/JS assets.'
    foreach ($reference in [regex]::Matches($IndexText, '(?i)(?:src|href)="([^"?#]+\.(?:css|js))"')) {
        $relative = $reference.Groups[1].Value.Replace('\', '/')
        if ($relative -match '^(?:[A-Za-z][A-Za-z0-9+.-]*:)?//') { continue }
        throw "index.html references a local UI asset without the build stamp: $relative"
    }
    return $result
}

function Apply-IdentityRules {
    param([string]$StageRoot, [string[]]$AllowedChanges)
    # Each rule runs as one Regex.Replace pass over the whole file, so a
    # replacement that itself begins with the production token (fnaudio-beta)
    # is never rescanned by the rule that produced it.
    $changed = [System.Collections.Generic.List[object]]::new()
    foreach ($file in Get-ChildItem -LiteralPath $StageRoot -Recurse -File -Force) {
        $relative = $file.FullName.Substring($StageRoot.Length + 1).Replace('\', '/')
        if (Test-BinaryFile -Path $file.FullName) { continue }
        $original = Read-TextFile -Path $file.FullName
        $text = $original.Text
        $applied = [System.Collections.Generic.List[string]]::new()
        foreach ($rule in $identityRules) {
            if ($rule.Scope -ne '*' -and @($rule.Scope) -notcontains $relative) { continue }
            $next = [regex]::Replace($text, $rule.Pattern, $rule.Replacement)
            if ($next -cne $text) {
                $applied.Add($rule.Name) | Out-Null
                $text = $next
            }
        }
        if ($text -cne $original.Text) {
            Assert-Condition (@($AllowedChanges) -contains $relative) "Unexpected staged file would be rewritten: $relative"
            Write-TextFile -Path $file.FullName -Text $text -HasBom $original.HasBom
            $changed.Add([pscustomobject]@{ Relative = $relative; Rules = @($applied) }) | Out-Null
        }
    }
    return @($changed)
}

function Set-JsonTextValue {
    # Rewrite one string member of a tiny JSON document without reformatting it,
    # so the packaged config/privilege and config/resource stay byte-shaped like
    # the reviewed source and remain diffable.
    param([string]$Text, [string]$Name, [string]$Value)
    $pattern = '(?s)("' + [regex]::Escape($Name) + '"\s*:\s*")(?:[^"\\]|\\.)*(")'
    if ($Text -notmatch $pattern) { return $null }
    $evaluator = { param($match) $match.Groups[1].Value + $Value.Replace('$', '$$') + $match.Groups[2].Value }
    return [regex]::Replace($Text, $pattern, $evaluator)
}
# ---------------------------------------------------------------------------
# Gate patterns. These are asserted three times: on the staged tree, on the
# unpacked FPK and on the unpacked app payload, because a rewrite that only
# survives until fnpack repacks the tree proves nothing.
# ---------------------------------------------------------------------------
$forbiddenPatterns = @(
    [pscustomobject]@{ Name = 'production runtime path';  Pattern = '/var/apps/fnaudio(?![\-A-Za-z0-9_.])' }
    [pscustomobject]@{ Name = 'production package path';  Pattern = '/var/packages/fnaudio(?![\-A-Za-z0-9_.])' }
    [pscustomobject]@{ Name = 'production registration';  Pattern = '@app(?:conf|data|center)/fnaudio(?![\-A-Za-z0-9_.])' }
    [pscustomobject]@{ Name = 'production CGI entry';     Pattern = 'ThirdParty\\?/fnaudio(?![\-A-Za-z0-9_.])' }
    [pscustomobject]@{ Name = 'production launch entry';  Pattern = '\bfnaudio\.Application' }
    [pscustomobject]@{ Name = 'production process sweep';  Pattern = '"fnaudio"' }
    [pscustomobject]@{ Name = 'production share root';    Pattern = '"fnaudio/' }
    [pscustomobject]@{ Name = 'production port';          Pattern = '(?<![0-9])53199(?![0-9])' }
)

function Get-GateViolations {
    param([string]$Root, [string]$Label)
    $violations = [System.Collections.Generic.List[string]]::new()
    foreach ($file in Get-ChildItem -LiteralPath $Root -Recurse -File -Force) {
        $relative = $file.FullName.Substring($Root.Length + 1).Replace('\', '/')
        if ($file.Length -eq 0) { continue }
        # A compressed payload is scanned after it has been unpacked, never as
        # an opaque byte blob that could hide or fake a match.
        if (@('.fpk', '.tgz', '.gz', '.zip') -contains $file.Extension.ToLowerInvariant()) { continue }
        $text = [Text.Encoding]::UTF8.GetString([IO.File]::ReadAllBytes($file.FullName))
        foreach ($probe in $forbiddenPatterns) {
            foreach ($match in [regex]::Matches($text, $probe.Pattern)) {
                $violations.Add("[$Label] $relative still contains $($probe.Name): '$($match.Value)'") | Out-Null
            }
        }
    }
    return @($violations)
}

function Get-CountOf {
    param([string]$Root, [string]$Pattern)
    $total = 0
    foreach ($file in Get-ChildItem -LiteralPath $Root -Recurse -File -Force) {
        if ($file.Length -eq 0) { continue }
        if (@('.fpk', '.tgz', '.gz', '.zip') -contains $file.Extension.ToLowerInvariant()) { continue }
        $text = [Text.Encoding]::UTF8.GetString([IO.File]::ReadAllBytes($file.FullName))
        $total += ([regex]::Matches($text, $Pattern)).Count
    }
    return $total
}

function Set-BetaBadge {
    # A beta that looks identical to the release in App Center is one careless
    # click away from being mistaken for it, so the shipped icons are badged.
    param([string]$StageRoot)
    $targets = @('ICON.PNG', 'ICON_256.PNG', 'app/ui/images/icon_64.png', 'app/ui/images/icon_256.png')
    $badged = [System.Collections.Generic.List[string]]::new()
    $warnings = [System.Collections.Generic.List[string]]::new()
    try {
        Add-Type -AssemblyName System.Drawing
    }
    catch {
        $warnings.Add('System.Drawing is unavailable; packaged icons keep the release artwork.') | Out-Null
        return [pscustomobject]@{ Badged = @($badged); Warnings = @($warnings) }
    }
    foreach ($relative in $targets) {
        $path = Join-Path $StageRoot ($relative.Replace('/', '\'))
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
        try {
            # Load through a memory copy: Image::FromFile keeps the source file
            # locked, which makes an in-place Save fail with a bare GDI+ error.
            # New-Object spreads an array argument, so a byte[] turns into thousands
            # of constructor arguments; build the stream and bitmap with ::new().
            $iconStream = [IO.MemoryStream]::new([IO.File]::ReadAllBytes($path))
            $source = [Drawing.Bitmap]::new($iconStream)
            $canvas = New-Object Drawing.Bitmap($source.Width, $source.Height, [Drawing.Imaging.PixelFormat]::Format32bppArgb)
            $graphics = [Drawing.Graphics]::FromImage($canvas)
            try {
                $graphics.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
                $graphics.SmoothingMode = [Drawing.Drawing2D.SmoothingMode]::AntiAlias
                $graphics.TextRenderingHint = [Drawing.Text.TextRenderingHint]::AntiAlias
                $graphics.DrawImage($source, 0, 0, $source.Width, $source.Height)
                $width = $source.Width
                $height = $source.Height
                $fontSize = [Math]::Max(8, [int][Math]::Round($width * 0.14))
                $font = New-Object Drawing.Font('Segoe UI', $fontSize, [Drawing.FontStyle]::Bold)
                try {
                    $measured = $graphics.MeasureString('BETA', $font)
                    $padding = [Math]::Max(2, [int][Math]::Round($width * 0.035))
                    $halo = [Math]::Max(1, [int][Math]::Round($width * 0.015))
                    $boxWidth = [int][Math]::Ceiling($measured.Width) + ($padding * 2)
                    $boxHeight = [int][Math]::Ceiling($measured.Height) + ($padding * 2)
                    $boxLeft = $width - $boxWidth - [Math]::Max(2, [int][Math]::Round($width * 0.05))
                    $boxTop = $height - $boxHeight - [Math]::Max(2, [int][Math]::Round($height * 0.05))
                    # A light halo keeps the tag readable over both the white and the
                    # saturated artwork the release ships at these sizes.
                    $haloBrush = New-Object Drawing.SolidBrush([Drawing.Color]::White)
                    $graphics.FillRectangle($haloBrush, ($boxLeft - $halo), ($boxTop - $halo), ($boxWidth + ($halo * 2)), ($boxHeight + ($halo * 2)))
                    $haloBrush.Dispose()
                    $badgeBrush = New-Object Drawing.SolidBrush([Drawing.Color]::FromArgb(235, 198, 40, 40))
                    $graphics.FillRectangle($badgeBrush, $boxLeft, $boxTop, $boxWidth, $boxHeight)
                    $badgeBrush.Dispose()
                    $graphics.DrawString('BETA', $font, [Drawing.Brushes]::White, ($boxLeft + $padding), ($boxTop + $padding))
                }
                finally { $font.Dispose() }
                $canvas.Save($path, [Drawing.Imaging.ImageFormat]::Png)
            }
            finally {
                $graphics.Dispose()
                $canvas.Dispose()
                $source.Dispose()
                $iconStream.Dispose()
            }
            $badged.Add($relative) | Out-Null
        }
        catch {
            $warnings.Add("Unable to badge $relative ($($_.Exception.Message)); the packaged icon keeps the release artwork.") | Out-Null
        }
    }
    return [pscustomobject]@{ Badged = @($badged); Warnings = @($warnings) }
}
function Read-JsonFile {
    param([string]$Path, [string]$Label)
    Assert-Condition (Test-Path -LiteralPath $Path -PathType Leaf) "$Label is missing: $Path"
    try {
        return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        throw "$Label is not valid JSON: $Path ($($_.Exception.Message))"
    }
}
# ---------------------------------------------------------------------------
# One identity gate, applied to the staged tree, to the unpacked FPK and
# to the unpacked app payload.
# ---------------------------------------------------------------------------
function Assert-Identity {
    # One identity gate, applied to the staged tree, to the unpacked FPK and
    # (content only) to the unpacked app payload.
    param([string]$Root, [string]$Label, [switch]$ContentOnly)
    $violations = [System.Collections.Generic.List[string]]::new()
    foreach ($violation in Get-GateViolations -Root $Root -Label $Label) { $violations.Add($violation) | Out-Null }
    if (-not $ContentOnly) {
        # The positive minimums describe the whole package (manifest, cmd, wizard and the
        # app payload), so they are asserted on the staged tree and the unpacked
        # FPK. The payload alone legitimately carries fewer of them.
        foreach ($pattern in $requiredPatterns) {
            $found = Get-CountOf -Root $Root -Pattern $pattern.Pattern
            if ($found -lt $pattern.Minimum) { $violations.Add("[$Label] expected at least $($pattern.Minimum) occurrences of $($pattern.Name), found $found") | Out-Null }
        }
    }
    if ($ContentOnly) {
        Assert-Condition (@($violations).Count -eq 0) ("Beta identity gate failed ([$Label]):`n" + (($violations | ForEach-Object { "  - $_" }) -join "`n"))
        return
    }
    $privilegeCheck = Read-JsonFile -Path (Join-Path $Root 'config\privilege') -Label "[$Label] config/privilege"
    if ($privilegeCheck.defaults.'run-as' -ne 'root') { $violations.Add("[$Label] config/privilege must keep run-as=root") | Out-Null }
    if ($privilegeCheck.username -ne $AppUser) { $violations.Add("[$Label] config/privilege username is '$($privilegeCheck.username)', expected '$AppUser'") | Out-Null }
    if ($privilegeCheck.groupname -ne $AppUser) { $violations.Add("[$Label] config/privilege groupname is '$($privilegeCheck.groupname)', expected '$AppUser'") | Out-Null }
    $resourceCheck = Read-JsonFile -Path (Join-Path $Root 'config\resource') -Label "[$Label] config/resource"
    $shareNames = @($resourceCheck.'data-share'.shares | ForEach-Object { $_.name })
    foreach ($requiredShare in @("$SharePrefix/music", "$SharePrefix/data")) {
        if ($shareNames -notcontains $requiredShare) { $violations.Add("[$Label] config/resource is missing data share '$requiredShare'") | Out-Null }
    }
    $checkedManifest = Get-Content -LiteralPath (Join-Path $Root 'manifest') -Raw -Encoding UTF8
    $manifestExpectations = [ordered]@{
        appname               = $AppName
        version               = $betaVersion
        display_name          = $DisplayName
        developer             = $Developer
        publisher             = $Publisher
        maintainer            = $Developer
        distributor           = $Publisher
        desktop_applaunchname = "$AppName.Application"
        service_port          = "$ServicePort"
        install_dep_apps      = 'python312'
        checkport             = 'false'
        micro_app             = 'true'
        ctl_stop              = 'true'
    }
    foreach ($key in $manifestExpectations.Keys) {
        $actual = Get-ManifestValue -Text $checkedManifest -Name $key
        if ($actual -ne $manifestExpectations[$key]) { $violations.Add("[$Label] manifest $key is '$actual', expected '$($manifestExpectations[$key])'") | Out-Null }
    }
    # install_type is asserted outside the expectation table, in a helper that can
    # be executed on its own, because the platform spells "ask the user" by the
    # absence of the key rather than by a value.
    foreach ($installTypeViolation in Get-ManifestInstallTypeViolations -Text $checkedManifest -Expected $InstallType -Label $Label) {
        $violations.Add($installTypeViolation) | Out-Null
    }
    if (-not (Get-ManifestValue -Text $checkedManifest -Name 'desc').StartsWith($betaTag)) { $violations.Add("[$Label] manifest desc must carry the beta tag") | Out-Null }
    foreach ($command in @('config_callback', 'config_init', 'install_callback', 'install_init', 'main', 'uninstall_callback', 'uninstall_init', 'upgrade_callback', 'upgrade_init')) {
        $commandText = Read-TextFile -Path (Join-Path $Root "cmd\$command")
        if (-not $commandText.Text.StartsWith('#!/bin/bash')) { $violations.Add("[$Label] cmd/$command no longer starts with #!/bin/bash") | Out-Null }
        if ($commandText.HasBom) { $violations.Add("[$Label] cmd/$command gained a byte-order mark") | Out-Null }
        if ($commandText.Text.Contains("`r")) { $violations.Add("[$Label] cmd/$command gained CRLF line endings") | Out-Null }
    }
    Assert-Condition (@($violations).Count -eq 0) ("Beta identity gate failed ([$Label]):`n" + (($violations | ForEach-Object { "  - $_" }) -join "`n"))
}

# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------
$stagedFiles = Get-ChildItem -LiteralPath $sourceRoot -Recurse -File -Force | Where-Object {
    $_.FullName -notmatch '\\tests\\' -and $_.FullName -notmatch '__pycache__' -and $_.Name -ne 'fnaudio.fpk' -and $_.Extension -cne '.pyc'
}
$destination = Join-Path (Join-Path $OutputRoot 'beta') (Join-Path $AppName $betaVersion)
$artifactName = "$AppName-$betaVersion.fpk"
$publicationNames = @($artifactName, 'SHA256SUMS', 'PACKAGE_CONTENTS.txt', 'VALIDATION.md', 'INSTALL.env', 'BETA_PROVENANCE.json')
if (-not $AllowExistingArtifact) {
    foreach ($publicationName in $publicationNames) {
        $publicationPath = Join-Path $destination $publicationName
        Assert-Condition (-not (Test-Path -LiteralPath $publicationPath)) "Beta output already exists: $publicationPath. Pass -AllowExistingArtifact only for an intentional rebuild."
    }
}

$allowedChanges = @(
    'manifest',
    'config/resource',
    'cmd/config_callback', 'cmd/config_init', 'cmd/install_callback', 'cmd/main',
    'cmd/uninstall_callback', 'cmd/upgrade_callback',
    'wizard/config', 'wizard/install', 'wizard/uninstall',
    'app/ui/app.js', 'app/ui/cgi_proxy.py', 'app/ui/config', 'app/ui/service_port.json',
    'app/server/audio_fingerprint.py', 'app/server/config.py', 'app/server/library_paths.py',
    'app/server/public_url.py', 'app/server/version.py'
)
$requiredPatterns = @(
    [pscustomobject]@{ Name = 'beta runtime path';   Pattern = ('/var/apps/' + [regex]::Escape($AppName));                       Minimum = 1 }
    [pscustomobject]@{ Name = 'beta registration';   Pattern = ('@appcenter/' + [regex]::Escape($AppName) + '/');                 Minimum = 1 }
    [pscustomobject]@{ Name = 'beta CGI entry';      Pattern = ('ThirdParty\\?/' + [regex]::Escape($AppName));                    Minimum = 4 }
    [pscustomobject]@{ Name = 'beta launch entry';   Pattern = ([regex]::Escape($AppName) + '\.Application');                     Minimum = 2 }
    [pscustomobject]@{ Name = 'beta library';        Pattern = ('(?<![\w/])' + [regex]::Escape($LibraryPath));                         Minimum = 1 }
    [pscustomobject]@{ Name = 'beta port';           Pattern = ('(?<!\d)' + $ServicePort + '(?!\d)');                             Minimum = 20 }
)

$reported = [ordered]@{
    appname         = $AppName
    account         = $AppUser
    display_name    = $DisplayName
    version         = $betaVersion
    production_base = $productionVersion
    service_port    = $ServicePort
    share_prefix    = $SharePrefix
    library_path    = $LibraryPath
    developer       = $Developer
    publisher       = $Publisher
    install_type    = $InstallType
}
$validationNotes = [System.Collections.Generic.List[string]]::new()
$changedReports = @()
$badgedIcons = @()
$badgeWarnings = @()
$stagedFileCount = 0
$assetBuild = ''
$packageSha256 = ''

$temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) ('fnaudio-beta-' + [guid]::NewGuid().ToString('N'))
$stageRoot = Join-Path $temporaryRoot 'src'
$inspectionRoot = Join-Path $temporaryRoot 'inspect'
$payloadRoot = ''   # set to the unpacked app payload inside $inspectionRoot once the FPK exists
$publishRoot = Join-Path $temporaryRoot 'publish'
$publishedPaths = [System.Collections.Generic.List[string]]::new()
try {
New-Item -ItemType Directory -Force -Path $publishRoot | Out-Null
robocopy $sourceRoot $stageRoot /E /XD tests __pycache__ /XF fnaudio.fpk *.pyc /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "Failed to stage the beta source; robocopy exit code $LASTEXITCODE." }
$LASTEXITCODE = 0
$validationNotes.Add("staged $(@($stagedFiles).Count) source files (tests, __pycache__ and the checked-in fpk excluded)")
    # Snapshot every staged file first so "only the reviewed text files moved"
    # is a proof rather than an assumption: the shipped mpd binary, the vendored
    # libraries and the third-party JavaScript must survive byte for byte.
    $preHashes = @{}
    foreach ($file in Get-ChildItem -LiteralPath $stageRoot -Recurse -File -Force) {
        $preHashes[$file.FullName.Substring($stageRoot.Length + 1).Replace('\', '/')] = Get-Sha256Hex -Path $file.FullName
    }
    $stagedFileCount = $preHashes.Count

    # The release build stamps the UI with a content-derived cache key; the beta
    # stamps with its own version so a browser that has both open on one fnOS
    # origin can never reuse a cached module across the two installs.
    $stageUiRoot = Join-Path $stageRoot 'app\ui'
    $stageIndexPath = Join-Path $stageUiRoot 'index.html'
    $stageIndex = Read-TextFile -Path $stageIndexPath
    $stagedStampedAssets = Get-StampedUiAssetPaths -IndexText $stageIndex.Text -UiRoot $stageUiRoot
    $assetHashInput = @($stagedStampedAssets | ForEach-Object { Get-Sha256Hex -Path (Join-Path $stageUiRoot ($_.Replace('/', '\'))) }) -join ''
    $assetHash = $assetHashInput.Substring(0, 12).ToLowerInvariant()
    $assetBuild = "$betaVersion-$assetHash"
    $stampedIndex = $stageIndex.Text.Replace('__FNAUDIO_ASSET_BUILD__', $assetBuild)
    Assert-Condition (-not $stampedIndex.Contains('__FNAUDIO_ASSET_BUILD__')) 'Unable to stamp the staged UI asset build identifier.'
    Write-TextFile -Path $stageIndexPath -Text $stampedIndex -HasBom $stageIndex.HasBom
    $validationNotes.Add("stamped UI assets with build key '$assetBuild'")

    $changedReports = Apply-IdentityRules -StageRoot $stageRoot -AllowedChanges $allowedChanges
    Assert-Condition (@($changedReports).Count -gt 0) 'The identity rewrite changed nothing; the source tree or the rule table has drifted.'
    foreach ($change in $changedReports) {
        $validationNotes.Add("rewrote $($change.Relative) [$($change.Rules -join ', ')]")
    }

    $manifestPath = Join-Path $stageRoot 'manifest'
    $manifestText = Read-TextFile -Path $manifestPath
    $productionDescription = Get-ManifestValue -Text $manifestText.Text -Name 'desc'
    foreach ($key in @('appname', 'version', 'display_name', 'desc', 'developer', 'publisher', 'maintainer', 'distributor', 'install_type')) {
        Assert-Condition ($manifestText.Text -match "(?m)^\s*$key\s*=") "staged manifest lost the '$key' key."
    }
    $nextManifest = $manifestText.Text
    $nextManifest = Set-ManifestValue -Text $nextManifest -Name 'appname' -Value $AppName
    $nextManifest = Set-ManifestValue -Text $nextManifest -Name 'version' -Value $betaVersion
    $nextManifest = Set-ManifestValue -Text $nextManifest -Name 'display_name' -Value $DisplayName
    $nextManifest = Set-ManifestValue -Text $nextManifest -Name 'desc' -Value "$betaTag $productionDescription"
    $nextManifest = Set-ManifestValue -Text $nextManifest -Name 'developer' -Value $Developer
    $nextManifest = Set-ManifestValue -Text $nextManifest -Name 'publisher' -Value $Publisher
    $nextManifest = Set-ManifestValue -Text $nextManifest -Name 'maintainer' -Value $Developer
    $nextManifest = Set-ManifestValue -Text $nextManifest -Name 'distributor' -Value $Publisher
    if ($InstallType -ceq 'root') {
        $nextManifest = Set-ManifestValue -Text $nextManifest -Name 'install_type' -Value 'root'
    }
    else {
        $nextManifest = Remove-ManifestKey -Text $nextManifest -Name 'install_type'
    }
    Write-TextFile -Path $manifestPath -Text $nextManifest -HasBom $manifestText.HasBom
    $validationNotes.Add('manifest identity keys set (appname/version/display_name/desc/developer/publisher/maintainer/distributor)')
    $validationNotes.Add(('manifest install_type is ''{0}''' -f $InstallType))

    # config/privilege carries no username today, so fnOS would derive the
    # service account from the appname. The requested account is written
    # explicitly instead, while run-as stays root exactly as reviewed.
    $privilegePath = Join-Path $stageRoot 'config\privilege'
    $privilegeOriginal = Read-TextFile -Path $privilegePath
    Assert-Condition ($privilegeOriginal.Text -match '"run-as"\s*:\s*"root"') 'staged config/privilege no longer declares run-as=root.'
    $privilegeText = '{' + "`n" + '  "defaults": {' + "`n" + '    "run-as": "root"' + "`n" + '  },' + "`n" + "  `"username`": `"$AppUser`"," + "`n" + "  `"groupname`": `"$AppUser`"" + "`n" + '}' + "`n"
    Write-TextFile -Path $privilegePath -Text $privilegeText -HasBom $false
    $validationNotes.Add("config/privilege now pins username/groupname to '$AppUser'")

    if ($NoBadge) {
        $validationNotes.Add('icon badge skipped by request')
    }
    else {
        $badgeResult = Set-BetaBadge -StageRoot $stageRoot
        $badgedIcons = @($badgeResult.Badged)
        $badgeWarnings = @($badgeResult.Warnings)
        foreach ($warning in $badgeWarnings) { $validationNotes.Add("WARNING $warning") }
        if ($badgedIcons.Count -gt 0) { $validationNotes.Add("badged icons: $($badgedIcons -join ', ')") }
    }
    # Prove the rewrite had exactly the intended blast radius.
    $expectedTouch = [System.Collections.Generic.List[string]]::new()
    foreach ($name in @($changedReports.Relative)) { $expectedTouch.Add($name) | Out-Null }
    foreach ($name in @('app/ui/index.html', 'manifest', 'config/privilege')) { if (-not $expectedTouch.Contains($name)) { $expectedTouch.Add($name) | Out-Null } }
    foreach ($name in $badgedIcons) { if (-not $expectedTouch.Contains($name)) { $expectedTouch.Add($name) | Out-Null } }
    $postFiles = Get-ChildItem -LiteralPath $stageRoot -Recurse -File -Force
    Assert-Condition (@($postFiles).Count -eq $stagedFileCount) "The staged file count changed from $stagedFileCount to $(@($postFiles).Count)."
    foreach ($file in $postFiles) {
        $relative = $file.FullName.Substring($stageRoot.Length + 1).Replace('\', '/')
        Assert-Condition ($preHashes.ContainsKey($relative)) "Staged file disappeared during the rewrite: $relative"
        if (@($expectedTouch) -notcontains $relative) {
            Assert-Condition ((Get-Sha256Hex -Path $file.FullName) -ceq $preHashes[$relative]) "Non reviewed staged file changed: $relative"
        }
    }
    $validationNotes.Add("blast radius held to $(@($expectedTouch).Count) staged files; every other file kept its hash")

    Assert-Identity -Root $stageRoot -Label 'staged'
    # -------------------------------------------------------------------
    # fnpack is the only packager: fnOS validates details of the container it
    # produces, so the beta must not be repacked by a second archiver.
    # -------------------------------------------------------------------
    $fnpackSha256 = Get-Sha256Hex -Path $FnpackPath
    Push-Location -LiteralPath $stageRoot
    try {
        $fnpackOutput = & $FnpackPath build --directory $stageRoot 2>&1
        $fnpackExit = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
    Assert-Condition ($fnpackExit -eq 0) ("fnpack build failed with exit code $fnpackExit." + [string][char]10 + (@($fnpackOutput | ForEach-Object { [string]$_ }) -join [string][char]10))
    $builtPackages = @(Get-ChildItem -LiteralPath $stageRoot -Filter '*.fpk' -File)
    Assert-Condition (@($builtPackages).Count -eq 1) "fnpack produced $(@($builtPackages).Count) fpk files; exactly one was expected."
    $builtPackage = $builtPackages[0]
    Assert-Condition ($builtPackage.Name -ceq ($AppName + '.fpk')) "fnpack packaged '$($builtPackage.Name)' instead of '$AppName.fpk'; the staged manifest appname never reached the packer."
    Assert-Condition ($builtPackage.Length -gt 1048576) "Built fpk is implausibly small: $($builtPackage.Length) bytes."
    Assert-Condition ($builtPackage.Length -le 10737418240) 'Built fpk exceeds the 10 GiB artifact limit.'
    $temporaryArtifactPath = Join-Path $publishRoot $artifactName
    Move-Item -LiteralPath $builtPackage.FullName -Destination $temporaryArtifactPath
    $validationNotes.Add("fnpack built $($builtPackage.Name) ($($builtPackage.Length) bytes)")

    # The gate must run on the shipped bytes, not on the tree that went in.
    $packageHeader = New-Object byte[] 2
    $packageStream = [IO.File]::OpenRead($temporaryArtifactPath)
    try {
        $packageHeaderRead = $packageStream.Read($packageHeader, 0, 2)
    }
    finally {
        $packageStream.Dispose()
    }
    Assert-Condition ($packageHeaderRead -eq 2 -and $packageHeader[0] -eq 0x1f -and $packageHeader[1] -eq 0x8b) 'The built fpk must keep the gzip container fnOS expects.'
    New-Item -ItemType Directory -Force -Path $inspectionRoot | Out-Null
    tar -xf $temporaryArtifactPath -C $inspectionRoot
    Assert-Condition ($LASTEXITCODE -eq 0) "Unable to unpack the built fpk for verification; tar exit code $LASTEXITCODE."
    $payloadArchive = Join-Path $inspectionRoot 'app.tgz'
    Assert-Condition (Test-Path -LiteralPath $payloadArchive -PathType Leaf) 'Built fpk has no app.tgz payload.'
    $payloadRoot = Join-Path $inspectionRoot 'app'
    New-Item -ItemType Directory -Force -Path $payloadRoot | Out-Null
    tar -xf $payloadArchive -C $payloadRoot
    Assert-Condition ($LASTEXITCODE -eq 0) "Unable to unpack the fpk payload for verification; tar exit code $LASTEXITCODE."

    Assert-Identity -Root $inspectionRoot -Label 'fpk'
    Assert-Identity -Root $payloadRoot -Label 'payload' -ContentOnly
    $validationNotes.Add('identity gate passed on the staged tree, the unpacked fpk and the unpacked payload')

    # Shape checks: the beta must still be the same application, and it must not
    # smuggle test sources or stale bytecode into the package.
    foreach ($payloadRelative in @('server/server.py', 'server/version.py', 'ui/index.html', 'ui/index.cgi', 'ui/cgi_proxy.py', 'ui/config', 'ui/service_port.json', 'target/bin/mpd')) {
        $payloadPath = Join-Path $payloadRoot ($payloadRelative.Replace('/', '\'))
        Assert-Condition ((Test-Path -LiteralPath $payloadPath -PathType Leaf) -and ((Get-Item -LiteralPath $payloadPath).Length -gt 0)) "Packaged payload file is missing or empty: $payloadRelative"
    }
    if (Test-Path -LiteralPath (Join-Path $payloadRoot 'tests')) { throw 'FPK payload unexpectedly contains test sources.' }
    $staleBytecode = @(Get-ChildItem -LiteralPath $payloadRoot -Recurse -Filter '*.pyc' -Force)
    Assert-Condition (@($staleBytecode).Count -eq 0) "FPK payload unexpectedly contains $(@($staleBytecode).Count) Python bytecode files."
    $packagedIndex = Read-TextFile -Path (Join-Path $payloadRoot ('ui' + [IO.Path]::DirectorySeparatorChar + 'index.html'))
    foreach ($assetRelative in $stagedStampedAssets) {
        Assert-Condition ($packagedIndex.Text.Contains($assetRelative + '?v=' + $assetBuild)) "Packaged ui/index.html lost the beta asset stamp for $assetRelative."
    }
    $validationNotes.Add("payload shape verified: $(@($stagedStampedAssets).Count) beta-stamped UI assets, no test sources, no bytecode")

    # -------------------------------------------------------------------
    # Evidence, written beside the artifact. Publication is the last step, so a
    # failed gate never leaves a half-built beta behind.
    # -------------------------------------------------------------------
    $packageSha256 = Get-Sha256Hex -Path $temporaryArtifactPath
    $lineFeed = [string][char]10
    Write-TextFile -Path (Join-Path $publishRoot 'SHA256SUMS') -Text ($packageSha256 + '  ' + $artifactName + $lineFeed) -HasBom $false
    $packageContents = [System.Collections.Generic.List[string]]::new()
    foreach ($file in Get-ChildItem -LiteralPath $stageRoot -Recurse -File -Force | Sort-Object FullName) {
        $stagedRelative = $file.FullName.Substring($stageRoot.Length + 1).Replace('\', '/')
        $packageContents.Add((Get-Sha256Hex -Path $file.FullName) + '  ' + $stagedRelative) | Out-Null
    }
    Write-TextFile -Path (Join-Path $publishRoot 'PACKAGE_CONTENTS.txt') -Text (($packageContents -join $lineFeed) + $lineFeed) -HasBom $false
    Write-TextFile -Path (Join-Path $publishRoot 'INSTALL.env') -Text ('wizard_library_path=' + $LibraryPath + $lineFeed + 'wizard_server_port=' + $ServicePort + $lineFeed) -HasBom $false

    $gitCommit = ''
    $gitWorktree = ''
    try {
        # -c safe.directory keeps the probe working when the checkout is owned by
        # a different account than the one running the build. Without it git exits
        # 128, that code is never consumed, and a successful beta build reports a
        # failing exit code to its caller.
        $gitProbe = @(& git -c "safe.directory=$repoRoot" -C $repoRoot rev-parse HEAD 2>&1)
        $probeStatus = $LASTEXITCODE
        $LASTEXITCODE = 0
        if ($probeStatus -eq 0 -and @($gitProbe).Count -eq 1) { $gitCommit = ([string]$gitProbe[0]).Trim() }
        $dirtyProbe = @(& git -c "safe.directory=$repoRoot" -C $repoRoot status --porcelain -uno 2>&1)
        $probeStatus = $LASTEXITCODE
        $LASTEXITCODE = 0
        if ($probeStatus -eq 0) { $gitWorktree = $(if (@($dirtyProbe).Count -eq 0) { 'clean' } else { 'dirty' }) }
    }
    catch {
        $validationNotes.Add("WARNING git provenance unavailable: $($_.Exception.Message)")
    }
    if (-not $gitCommit) {
        $validationNotes.Add('WARNING git commit unavailable; this beta is not tied to a revision.')
    }
    $provenance = [ordered]@{
        schema             = 1
        kind             = 'beta'
        appname          = $AppName
        account          = $AppUser
        display_name     = $DisplayName
        version          = $betaVersion
        production_base  = $productionVersion
        service_port     = $ServicePort
        share_prefix     = $SharePrefix
        library_path     = $LibraryPath
        developer        = $Developer
        publisher        = $Publisher
        install_type     = $InstallType
        git_commit       = $gitCommit
        git_worktree     = $gitWorktree
        staged_file_count = $stagedFileCount
        package_file_count = @($packageContents).Count
        asset_build      = $assetBuild
        fnpack_sha256    = $fnpackSha256
        artifact_name    = $artifactName
        artifact_sha256  = $packageSha256
        artifact_bytes   = (Get-Item -LiteralPath $temporaryArtifactPath).Length
        badged_icons     = @($badgedIcons)
        built_utc        = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    }
    Write-TextFile -Path (Join-Path $publishRoot 'BETA_PROVENANCE.json') -Text (($provenance | ConvertTo-Json -Depth 4) + $lineFeed) -HasBom $false
    Assert-Condition ((Read-JsonFile -Path (Join-Path $publishRoot 'BETA_PROVENANCE.json') -Label 'beta provenance').artifact_sha256 -ceq $packageSha256) 'Beta provenance does not carry the built artifact digest.'

    $validationReport = [System.Collections.Generic.List[string]]::new()
    $validationReport.Add('# fnAudio beta build report')
    $validationReport.Add('')
    $validationReport.Add('Built by tools/build_beta_fpk.ps1. This package installs beside the release build; it is not the release build and it is never installed over it.')
    $validationReport.Add('')
    $validationReport.Add('## Identity')
    $validationReport.Add('')
    foreach ($key in $reported.Keys) { $validationReport.Add('- ' + $key + ': ' + [string]$reported[$key]) }
    $validationReport.Add('- git_commit: ' + $gitCommit)
    $validationReport.Add('- artifact: ' + $artifactName)
    $validationReport.Add('- artifact_sha256: ' + $packageSha256)
    $validationReport.Add('- fnpack_sha256: ' + $fnpackSha256)
    $validationReport.Add('- staged_files: ' + $stagedFileCount)
    $validationReport.Add('')
    $validationReport.Add('## Checks')
    $validationReport.Add('')
    foreach ($note in $validationNotes) { $validationReport.Add('- ' + $note) }
    $validationReport.Add('')
    $validationReport.Add('## Deliberate leftovers')
    $validationReport.Add('')
    $validationReport.Add('- Internal identifiers that are not a filesystem, CGI, account or port namespace stay untouched on purpose: the fnAudio user agent, fnaudio- thread names, .fnaudio-cover-* classes, fnaudio-transcode, --fnaudio-* CSS custom properties, dataset.fnaudio* keys, window.fnaudioTrimSdk, fnaudio.jsonl log names and the X-Fnaudio-* headers. Forking them would add drift without adding isolation.')
    $validationReport.Add('- The DLNA renderer UDN derives from the base URL, so the beta port already yields a distinct renderer id.')
    $validationReport.Add('- Browser localStorage is shared per origin, so if both builds are opened through the same fnOS origin, UI preferences such as the sort order can be shared. Library data, accounts, runtime paths, shares and ports are not.')
    $validationReport.Add('- android-client/ still points at /cgi/ThirdParty/fnaudio/, so the Android app keeps talking to the release build, not to this beta.')
    if (@($badgeWarnings).Count -gt 0) {
        $validationReport.Add('')
        $validationReport.Add('## Icon warnings')
        $validationReport.Add('')
        foreach ($warning in $badgeWarnings) { $validationReport.Add('- ' + $warning) }
    }
    Write-TextFile -Path (Join-Path $publishRoot 'VALIDATION.md') -Text (($validationReport -join $lineFeed) + $lineFeed) -HasBom $false

    # Every published file must exist before the destination receives any of them.
    foreach ($leaf in $publicationNames) {
        Assert-Condition (Test-Path -LiteralPath (Join-Path $publishRoot $leaf) -PathType Leaf) "Refusing to publish: the evidence file '$leaf' was not produced."
    }
    New-Item -ItemType Directory -Force -Path $destination | Out-Null
    foreach ($leaf in $publicationNames) {
        $targetPath = Join-Path $destination $leaf
        if (Test-Path -LiteralPath $targetPath) { Remove-Item -LiteralPath $targetPath -Force }
        Copy-Item -LiteralPath (Join-Path $publishRoot $leaf) -Destination $targetPath
        $publishedPaths.Add($targetPath) | Out-Null
    }
    $publishedArtifact = Join-Path $destination $artifactName
    Assert-Condition ((Get-Sha256Hex -Path $publishedArtifact) -ceq $packageSha256) 'The published fpk digest differs from the verified build.'
}
catch {
    $parse = $($_.Exception)
    Write-Error ("Beta build aborted: " + $parse.Message)
    throw
}
finally {
    if ($KeepStage) {
        Write-Host "beta stage tree kept at $stageRoot"
    }
    else {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "beta package : $publishedArtifact"
Write-Host "sha256       : $packageSha256"
Write-Host "identity     : appname=$AppName account=$AppUser port=$ServicePort version=$betaVersion"
if (@($badgeWarnings).Count -gt 0) { Write-Host 'icon badge     : NOT applied (see VALIDATION.md)' }

return [pscustomobject]@{
    Package     = $publishedArtifact
    Sha256      = $packageSha256
    Version     = $betaVersion
    AppName     = $AppName
    Account     = $AppUser
    ServicePort = $ServicePort
    LibraryPath = $LibraryPath
    InstallEnv  = (Join-Path $destination 'INSTALL.env')
    Report      = (Join-Path $destination 'VALIDATION.md')
    Published   = @($publishedPaths)
}

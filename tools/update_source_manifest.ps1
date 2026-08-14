[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$output = Join-Path $repoRoot "SOURCE_MANIFEST.sha256"
$excludedSegments = @(".gradle", ".media3-inspect", ".idea", "build", "__pycache__")
$excludedNames = @("local.properties")
$excludedExtensions = @(".apk", ".aab", ".aar", ".class", ".fpk", ".pyc")

$files = Get-ChildItem -LiteralPath (Join-Path $repoRoot "src"), (Join-Path $repoRoot "android-client") -Recurse -File -Force |
    Where-Object {
        $relative = $_.FullName.Substring($repoRoot.Length + 1).Replace("\", "/")
        $segments = $relative.Split("/")
        -not ($segments | Where-Object { $excludedSegments -contains $_ }) -and
        $excludedNames -notcontains $_.Name -and
        $excludedExtensions -notcontains $_.Extension.ToLowerInvariant()
    } |
    Sort-Object FullName

$lines = foreach ($file in $files) {
    $relative = $file.FullName.Substring($repoRoot.Length + 1).Replace("\", "/")
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    "$hash  $relative"
}

$lines | Set-Content -LiteralPath $output -Encoding ASCII
Write-Host "Wrote $($lines.Count) entries to $output"

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Get-Sha256Hex {
    param([Parameter(Mandatory = $true)][string]$Path)
    $getFileHash = Get-Command -Name Get-FileHash -ErrorAction SilentlyContinue
    if ($getFileHash) {
        return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
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

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$output = Join-Path $repoRoot "SOURCE_MANIFEST.sha256"
$excludedSegments = @(".gradle", ".media3-inspect", ".idea", "build", "Python", "__pycache__")
$excludedNames = @("local.properties")
$excludedExtensions = @(".apk", ".aab", ".aar", ".class", ".fpk", ".pyc")

$files = Get-ChildItem -LiteralPath (Join-Path $repoRoot "src"), (Join-Path $repoRoot "android-client") -Recurse -File -Force |
    Where-Object {
        $relative = $_.FullName.Substring($repoRoot.Length + 1).Replace("\", "/")
        $segments = $relative.Split("/")
        -not ($segments | Where-Object { $excludedSegments -contains $_ }) -and
        $excludedNames -notcontains $_.Name -and
        $excludedExtensions -notcontains $_.Extension.ToLowerInvariant()
    }

# The walk below is sorted by hand instead of with ``Sort-Object``.  ``Sort-Object``
# compares strings with the current culture, and the culture decides where "." and
# "_" fall: R148 hashed the same tree under Windows PowerShell 5.1 and under
# ``pwsh`` -- the shell the CI job runs -- and got two orderings of the same 710
# records with 117 line positions moved between them.  The CI step ends in
# ``git diff --exit-code -- SOURCE_MANIFEST.sha256``, so that drift fails the build
# on a manifest that is byte-for-byte complete, and any local refresh can silently
# rewrite 117 lines.  Ordinal comparison of the repo-relative path matches git's
# own path order and is reproducible from any shell.
$paths = [string[]]::new(0)
$lines = [string[]]::new(0)
foreach ($file in $files) {
    $relative = $file.FullName.Substring($repoRoot.Length + 1).Replace("\", "/")
    $hash = Get-Sha256Hex -Path $file.FullName
    $paths += $relative
    $lines += "$hash  $relative"
}
[Array]::Sort($paths, $lines, [StringComparer]::Ordinal)

$temporary = Join-Path $repoRoot (".SOURCE_MANIFEST.{0}.tmp" -f [guid]::NewGuid().ToString("N"))
try {
    $lines | Set-Content -LiteralPath $temporary -Encoding ASCII
    Move-Item -LiteralPath $temporary -Destination $output -Force
}
finally {
    if (Test-Path -LiteralPath $temporary -PathType Leaf) {
        Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
    }
}
Write-Host "Wrote $($lines.Count) entries to $output"

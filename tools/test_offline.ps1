param(
    [switch]$Package,
    [switch]$Browser
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$sourceRoot = Join-Path $projectRoot "src"
# Declared-UI-script discovery lives in its own helper so a gate test can
# exercise the pattern without running the whole regression set.
. (Join-Path $PSScriptRoot "ui_asset_gate.ps1")

function Invoke-NodeSyntaxCheck([string]$Path, [string]$Label) {
    node --check $Path
    if ($LASTEXITCODE -ne 0) {
        throw "JavaScript syntax check failed: $Label"
    }
}

Push-Location $sourceRoot
$previousPythonPath = $env:PYTHONPATH
if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
    $env:PYTHONPATH = "$sourceRoot;$sourceRoot\app\server"
}
else {
    $env:PYTHONPATH = "$sourceRoot;$sourceRoot\app\server;$previousPythonPath"
}
# ``python -B`` below only stops bytecode from being written; a matching entry
# in the source tree's __pycache__ is still read. CPython validates a cache by
# whole-second source mtime plus size, so an edit that leaves a file the same
# length can be verified against the previous bytecode and report a result that
# no longer matches the source. A throwaway prefix makes the gate compile from
# source every run.
$previousPycachePrefix = $env:PYTHONPYCACHEPREFIX
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP ("fnaudio-offline-pycache-" + [Guid]::NewGuid().ToString("N"))
$offlinePycachePrefix = $env:PYTHONPYCACHEPREFIX
try {
    python -B -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Python tests failed" }

    Invoke-NodeSyntaxCheck "app\ui\app.js" "app.js"
    $indexText = Get-Content -LiteralPath "app\ui\index.html" -Raw -Encoding UTF8
    # index.html is the authoritative UI module list, so a newly split module is
    # syntax checked as soon as it is declared. An empty result means the
    # discovery pattern stopped matching, which must fail instead of quietly
    # leaving the whole UI unchecked.
    $declaredScripts = Get-DeclaredUiScriptPaths -IndexText $indexText
    if ($declaredScripts.Count -eq 0) {
        throw "index.html declared no UI scripts; the Node syntax gate lost its discovery list"
    }
    foreach ($script in $declaredScripts) {
        Invoke-NodeSyntaxCheck (Join-Path "app\ui" $script) "Declared UI script $script"
    }
    # Keep the Node gate discovery-based like unittest discovery.  An explicit
    # list silently skips a newly added UI regression until somebody remembers
    # to update this script, which defeats the release gate.
    $nodeTests = Get-ChildItem -LiteralPath "tests" -Filter "test_*.js" -File | Sort-Object -Property Name
    foreach ($test in $nodeTests) {
        node $test.FullName
        if ($LASTEXITCODE -ne 0) { throw "Node regression failed: $($test.Name)" }
    }
}
finally {
    if ($null -eq $previousPythonPath) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTHONPATH = $previousPythonPath
    }
    if ($null -eq $previousPycachePrefix) {
        Remove-Item Env:PYTHONPYCACHEPREFIX -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTHONPYCACHEPREFIX = $previousPycachePrefix
    }
    # The throwaway prefix only exists so this run cannot read a stale in-tree
    # bytecode entry. Nothing reads it once unittest discovery has finished, so
    # keeping it meant every gate run leaked another %TEMP% directory.
    Remove-Item -LiteralPath $offlinePycachePrefix -Recurse -Force -ErrorAction SilentlyContinue
    Pop-Location
}

Push-Location $projectRoot
try {
    # Packaging and deployment scripts are part of the release contract even
    # when this gate deliberately skips a real fnpack build. Parse every
    # tracked PowerShell helper so a syntax error cannot hide until release.
    foreach ($scriptPath in Get-ChildItem -LiteralPath $PSScriptRoot -Filter "*.ps1" -File) {
        $tokens = $null
        $errors = $null
        [System.Management.Automation.Language.Parser]::ParseFile(
            $scriptPath.FullName, [ref]$tokens, [ref]$errors
        ) | Out-Null
        if ($errors.Count -gt 0) {
            throw "PowerShell syntax check failed: $($scriptPath.Name): $($errors[0].Message)"
        }
    }
    git diff --check
    if ($LASTEXITCODE -ne 0) { throw "git diff --check failed" }
    if ($Package) {
        & (Join-Path $PSScriptRoot "build_release.ps1")
        if ($LASTEXITCODE -ne 0) { throw "Release package verification failed" }
    }
    if ($Browser) {
        $browserRoot = Join-Path $PSScriptRoot "browser-e2e"
        if (-not (Test-Path -LiteralPath (Join-Path $browserRoot "node_modules\@playwright\test"))) {
            throw "Browser E2E dependencies are missing; run npm ci in tools/browser-e2e."
        }
        Push-Location $browserRoot
        try {
            npm test
            if ($LASTEXITCODE -ne 0) { throw "Browser E2E failed" }
        }
        finally {
            Pop-Location
        }
    }
}
finally {
    Pop-Location
}

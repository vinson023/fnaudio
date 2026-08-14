param(
    [switch]$Package,
    [switch]$Browser
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$sourceRoot = Join-Path $projectRoot "src"

Push-Location $sourceRoot
try {
    python -B -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Python tests failed" }

    node --check app\ui\app.js
    if ($LASTEXITCODE -ne 0) { throw "JavaScript syntax check failed" }
    node --check app\ui\track_presentation.js
    if ($LASTEXITCODE -ne 0) { throw "Track presentation syntax check failed" }
    foreach ($test in @(
        "tests\test_ui_android_bridge.js",
        "tests\test_ui_mobile_layout.js",
        "tests\test_ui_queue_columns.js",
        "tests\test_ui_lyrics_priority.js",
        "tests\test_ui_user_state.js"
        "tests\test_track_presentation.js"
    )) {
        node $test
        if ($LASTEXITCODE -ne 0) { throw "Node regression failed: $test" }
    }
}
finally {
    Pop-Location
}

Push-Location $projectRoot
try {
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

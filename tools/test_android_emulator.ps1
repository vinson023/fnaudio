[CmdletBinding()]
param(
    [string]$SdkRoot = $(if ($env:ANDROID_SDK_ROOT) { $env:ANDROID_SDK_ROOT } else { "E:\Codex\android-sdk" }),
    [string]$AvdName = "fnaudio-api35-atd",
    [switch]$InstallSdk,
    [switch]$KeepRunning
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$androidRoot = Join-Path $repoRoot "android-client"
$sdkRoot = (Resolve-Path $SdkRoot).Path
$sdkManager = Join-Path $sdkRoot "cmdline-tools\latest\bin\sdkmanager.bat"
$avdManager = Join-Path $sdkRoot "cmdline-tools\latest\bin\avdmanager.bat"
$emulator = Join-Path $sdkRoot "emulator\emulator.exe"
$adb = Join-Path $sdkRoot "platform-tools\adb.exe"
$image = "system-images;android-35;aosp_atd;x86_64"
$avdHome = Join-Path $repoRoot ".android-avd"

foreach ($tool in @($sdkManager, $avdManager, $adb)) {
    if (-not (Test-Path -LiteralPath $tool)) { throw "Android SDK tool is missing: $tool" }
}

$env:ANDROID_SDK_ROOT = $sdkRoot
$env:ANDROID_HOME = $sdkRoot
$env:ANDROID_AVD_HOME = $avdHome
New-Item -ItemType Directory -Path $avdHome -Force | Out-Null

if (-not (Test-Path -LiteralPath $emulator)) {
    if (-not $InstallSdk) { throw "Android Emulator is not installed. Re-run with -InstallSdk." }
    & $sdkManager "emulator" $image
    if ($LASTEXITCODE -ne 0) { throw "sdkmanager failed to install the Android Emulator" }
}

$avdPath = Join-Path $avdHome "$AvdName.avd"
if (-not (Test-Path -LiteralPath $avdPath)) {
    if (-not $InstallSdk) { throw "AVD '$AvdName' is missing. Re-run with -InstallSdk." }
    "no" | & $avdManager create avd --name $AvdName --package $image --force
    if ($LASTEXITCODE -ne 0) { throw "avdmanager failed to create '$AvdName'" }
}

$existing = & $adb devices | Select-String -Pattern "^emulator-[0-9]+\s+device$" | Select-Object -First 1
$startedHere = $false
if ($null -eq $existing) {
    $process = Start-Process -FilePath $emulator -ArgumentList @("-avd", $AvdName, "-no-window", "-no-audio", "-no-snapshot", "-gpu", "swiftshader_indirect") -PassThru -WindowStyle Hidden
    $startedHere = $true
    $deadline = (Get-Date).AddMinutes(5)
    do {
        Start-Sleep -Seconds 2
        $device = & $adb devices | Select-String -Pattern "^(emulator-[0-9]+)\s+device$" | Select-Object -First 1
        $booted = ""
        if ($null -ne $device) {
            $serial = $device.Matches[0].Groups[1].Value
            $booted = (& $adb -s $serial shell getprop sys.boot_completed 2>$null).Trim()
        }
    } while ($booted -ne "1" -and (Get-Date) -lt $deadline)
    if ($booted -ne "1") {
        if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force }
        throw "Android emulator did not finish booting within five minutes"
    }
}

try {
    Push-Location $androidRoot
    & .\gradlew.bat :app:connectedDebugAndroidTest
    $gradleSucceeded = $?
    $gradleExitCode = $LASTEXITCODE
    if (-not $gradleSucceeded -or $gradleExitCode -ne 0) {
        throw "connectedDebugAndroidTest failed (exit code $gradleExitCode)"
    }
    $debugApk = Join-Path $androidRoot "app\build\outputs\apk\debug\app-debug.apk"
    if (-not (Test-Path -LiteralPath $debugApk)) { throw "Debug APK was not built: $debugApk" }
    & $adb install -r $debugApk
    if ($LASTEXITCODE -ne 0) { throw "adb failed to install the Debug APK" }
    $versionMatch = Select-String -LiteralPath "app\build.gradle" -Pattern "versionCode\s+(\d+)" | Select-Object -First 1
    $expectedVersionCode = [int]$versionMatch.Matches[0].Groups[1].Value
    $installedPackage = & $adb shell dumpsys package com.fnaudio.client
    $expectedMarker = "versionCode=$expectedVersionCode"
    if (($installedPackage -join "`n") -notmatch [regex]::Escape($expectedMarker)) {
        throw "The installed Debug APK does not expose $expectedMarker. dumpsys output: $($installedPackage -join ' ')"
    }
} finally {
    Pop-Location
    if ($startedHere -and -not $KeepRunning) {
        & $adb emu kill 2>$null
    }
}

Write-Host "Android emulator tests passed. Report: $androidRoot\app\build\reports\androidTests\connected\debug\index.html"

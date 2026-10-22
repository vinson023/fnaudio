[CmdletBinding()]
param(
    [string]$SdkRoot = $env:ANDROID_SDK_ROOT,
    [string]$AvdName = "fnaudio-api35-atd",
    [switch]$InstallSdk,
    [switch]$KeepRunning
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$androidRoot = Join-Path $repoRoot "android-client"
if (-not $SdkRoot) { $SdkRoot = Join-Path $repoRoot "tools\android-sdk" }
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

if ($null -ne $existing) { $serial = ($existing.Line.Trim() -split "\s+")[0] }
$previousAndroidSerial = $env:ANDROID_SERIAL
$env:ANDROID_SERIAL = $serial
try {
    Push-Location $androidRoot
    & .\gradlew.bat --no-daemon --console=plain -PfnaudioTestBuildType=emulator :app:assembleEmulator :app:assembleEmulatorAndroidTest
    $gradleSucceeded = $?
    $gradleExitCode = $LASTEXITCODE
    if (-not $gradleSucceeded -or $gradleExitCode -ne 0) {
        throw "emulator test APK build failed (exit code $gradleExitCode)"
    }
    $debugApk = Join-Path $androidRoot "app\build\outputs\apk\emulator\app-emulator.apk"
    if (-not (Test-Path -LiteralPath $debugApk)) { throw "Debug APK was not built: $debugApk" }
    & $adb -s $serial install -r $debugApk
    if ($LASTEXITCODE -ne 0) { throw "adb failed to install the Debug APK" }
    $testApk = Join-Path $androidRoot "app\build\outputs\apk\androidTest\emulator\app-emulator-androidTest.apk"
    if (-not (Test-Path -LiteralPath $testApk)) { throw "Instrumentation APK was not built: $testApk" }
    & $adb -s $serial install -r $testApk
    if ($LASTEXITCODE -ne 0) { throw "adb failed to install the instrumentation APK" }
    & $adb -s $serial shell pm grant com.fnaudio.client.emulator android.permission.POST_NOTIFICATIONS
    # Direct adb avoids the Windows UTP testlog-directory failure and retains
    # the isolated emulator app/profile for follow-up manual verification.
    $testOutput = & $adb -s $serial shell am instrument -w com.fnaudio.client.emulator.test/androidx.test.runner.AndroidJUnitRunner 2>&1
    $testExitCode = $LASTEXITCODE
    $testOutput | Write-Output
    $testText = $testOutput -join "`n"
    if ($testExitCode -ne 0 -or $testText -match "FAILURES!!!|INSTRUMENTATION_FAILED|INSTRUMENTATION_RESULT: shortMsg=" -or $testText -notmatch "OK \([0-9]+ tests?\)") {
        throw "Android instrumentation failed; inspect the adb runner output above"
    }
    $versionMatch = Select-String -LiteralPath "app\build.gradle" -Pattern "versionCode\s+(\d+)" | Select-Object -First 1
    $expectedVersionCode = [int]$versionMatch.Matches[0].Groups[1].Value
    $installedPackage = & $adb -s $serial shell dumpsys package com.fnaudio.client.emulator
    $expectedMarker = "versionCode=$expectedVersionCode"
    if (($installedPackage -join "`n") -notmatch [regex]::Escape($expectedMarker)) {
        throw "The installed Debug APK does not expose $expectedMarker. dumpsys output: $($installedPackage -join ' ')"
    }
} finally {
    $env:ANDROID_SERIAL = $previousAndroidSerial
    Pop-Location
    if ($startedHere -and -not $KeepRunning) {
        & $adb -s $serial emu kill 2>$null
    }
}

Write-Host "Android emulator tests passed on $serial (isolated com.fnaudio.client.emulator)."

[CmdletBinding()]
param(
    [string]$Serial = "192.168.5.111:5555",
    [string]$SdkRoot = $env:ANDROID_SDK_ROOT,
    [string]$BuildType = "qaRelease",
    [string]$Package = "com.fnaudio.client",
    [string]$TestClass,
    [string[]]$InstrumentArg = @(),
    [switch]$SkipBuild,
    [switch]$SkipInstall,
    [bool]$PreserveAppState = $true,
    [switch]$NoLog,
    [switch]$RestoreRelease
)

# Runs the Android instrumentation suite on the physical test phone (SM-G965F,
# LineageOS 20 / Android 13) instead of the x86_64 emulator. See D-042.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\test_android_device.ps1
#   ... -TestClass com.fnaudio.client.ui.LoginHistoryInstrumentedTest
#   ... -InstrumentArg fnaudioHost=192.168.5.141,fnaudioUser=admin,fnaudioPassword=***,fnaudioPort=5666
#   ... -SkipBuild            # reuse the APKs from the previous run
#   ... -RestoreRelease       # put the shipped release APK back when done
#   ... -PreserveAppState:$false   # do NOT snapshot/restore shared_prefs
#
# Why qaRelease and not debug: the phone carries the shipped, release-signed
# com.fnaudio.client. A debug APK is signed with the debug key, so adb refuses it
# with INSTALL_FAILED_UPDATE_INCOMPATIBLE, and uninstalling first would throw away
# the login state and the cached library. qaRelease is initWith release (same
# certificate, same applicationId) plus debuggable, so it installs over the
# shipped build and still allows run-as and WebView CDP.
#
# Everything in this file is ASCII on purpose: Windows PowerShell 5.1 reads
# BOM-less files as ANSI, so non-ASCII strings would come out garbled.

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$androidRoot = Join-Path $repoRoot "android-client"
if (-not $SdkRoot) { $SdkRoot = Join-Path $repoRoot "tools\android-sdk" }
if (-not (Test-Path -LiteralPath $SdkRoot)) { throw "Android SDK not found: $SdkRoot" }
$sdkRoot = (Resolve-Path $SdkRoot).Path
$adb = Join-Path $sdkRoot "platform-tools\adb.exe"
if (-not (Test-Path -LiteralPath $adb)) { throw "adb is missing: $adb" }

$buildTools = Get-ChildItem -Path (Join-Path $sdkRoot "build-tools") -Directory -ErrorAction SilentlyContinue |
    Sort-Object { [version]$_.Name } -Descending | Select-Object -First 1
if (-not $buildTools) { throw "No build-tools under $sdkRoot\build-tools" }
$apksigner = Join-Path $buildTools.FullName "apksigner.bat"
if (-not (Test-Path -LiteralPath $apksigner)) { throw "apksigner is missing: $apksigner" }

# adb writes progress and warnings to stderr (e.g. "1 file pulled"), and with
# $ErrorActionPreference = "Stop" a redirected native stderr becomes a terminating
# NativeCommandError. Every adb call goes through here so stderr is collected as
# text instead of aborting the run.
function Invoke-AdbText {
    param([string[]]$AdbArgs)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        return ((& $adb @AdbArgs 2>&1) -join "`n")
    } finally {
        $ErrorActionPreference = $previous
    }
}

function Get-ApkCertDigest {
    param([string]$ApkPath)
    $output = (& $apksigner verify --print-certs $ApkPath 2>&1) -join "`n"
    $match = $output | Select-String -Pattern "certificate SHA-256 digest:\s*([0-9a-fA-F]+)" | Select-Object -First 1
    if ($null -eq $match) { return $null }
    return $match.Matches[0].Groups[1].Value.ToLowerInvariant()
}

# 1. Make sure the phone is reachable. Wireless adb is pinned to 5555 by an init
#    hook on this device, so a plain `adb connect` is enough; if that ever fails,
#    the hint points at the port discovery helper instead of guessing.
$state = Invoke-AdbText @("devices")
if ($state -notmatch [regex]::Escape("$Serial`tdevice")) {
    if ($Serial -match ":") {
        Write-Host "connecting to $Serial"
        Invoke-AdbText @("connect", $Serial) | Out-Null
    }
    $deadline = (Get-Date).AddSeconds(25)
    do {
        Start-Sleep -Milliseconds 800
        $state = Invoke-AdbText @("devices")
    } while ($state -notmatch [regex]::Escape("$Serial`tdevice") -and (Get-Date) -lt $deadline)
    if ($state -notmatch [regex]::Escape("$Serial`tdevice")) {
        throw "Device $Serial is not available. If the wireless port moved, run: python tools/adb_wireless.py connect"
    }
}
$sdkLevelText = (Invoke-AdbText @("-s", $Serial, "shell", "getprop", "ro.build.version.sdk")).Trim()
$sdkLevel = [int]$sdkLevelText
$model = (Invoke-AdbText @("-s", $Serial, "shell", "getprop", "ro.product.model")).Trim()
Write-Host "device: $Serial ($model, SDK $sdkLevel)"

# 2. Build the app + instrumentation APKs for the chosen build type.
$variant = $BuildType.Substring(0, 1).ToUpperInvariant() + $BuildType.Substring(1)
if (-not $SkipBuild) {
    if ($BuildType -match "^(qa|release)") {
        # qaRelease/release are signed with the project keystore; without the four
        # FNAUDIO_RELEASE_* variables Gradle silently produces an unsigned APK.
        & (Join-Path $PSScriptRoot "load_signing_env.ps1")
    }
    Push-Location $androidRoot
    try {
        # Same trap as the adb calls below: javac writes its "deprecated API"
        # notes to stderr, and under the default
        # $ErrorActionPreference = "Stop" PowerShell turns that into a terminating
        # NativeCommandError even though the build succeeded. The exit code is the
        # only signal that means anything here.
        $previous = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            & .\gradlew.bat --no-daemon --console=plain "-PfnaudioTestBuildType=$BuildType" ":app:assemble$variant" ":app:assemble${variant}AndroidTest"
            $gradleExit = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $previous
        }
    } finally {
        Pop-Location
    }
    if ($gradleExit -ne 0) { throw "Gradle build failed for $BuildType (exit code $gradleExit)" }
}

$appApk = Join-Path $androidRoot "app\build\outputs\apk\$BuildType\app-$BuildType.apk"
$testApk = Join-Path $androidRoot "app\build\outputs\apk\androidTest\$BuildType\app-$BuildType-androidTest.apk"
foreach ($apk in @($appApk, $testApk)) {
    if (-not (Test-Path -LiteralPath $apk)) { throw "APK was not built: $apk" }
}

# 3. Signature preflight. This is the step whose absence cost an hour last time:
#    adb only reports "signatures do not match", which says nothing about which
#    side is wrong. Compare certificates before touching the device.
$appCert = Get-ApkCertDigest $appApk
$testCert = Get-ApkCertDigest $testApk
if (-not $appCert) { throw "Could not read the signing certificate of $appApk" }
if ($appCert -ne $testCert) {
    throw "Instrumentation APK is signed with a different key ($testCert) than the app under test ($appCert). am instrument would fail; the androidTest variant needs the same signingConfig."
}

$installedCert = $null
$installedPath = $null
$pmPathOutput = Invoke-AdbText @("-s", $Serial, "shell", "pm", "path", $Package)
$pmPathMatch = [regex]::Match($pmPathOutput, "package:(\S+)")
if ($pmPathMatch.Success) { $installedPath = $pmPathMatch.Groups[1].Value }
if ($installedPath) {
    $tempApk = Join-Path ([IO.Path]::GetTempPath()) ("fnaudio-installed-{0}.apk" -f [guid]::NewGuid().ToString("N"))
    Invoke-AdbText @("-s", $Serial, "pull", $installedPath, $tempApk) | Out-Null
    if (Test-Path -LiteralPath $tempApk) {
        $installedCert = Get-ApkCertDigest $tempApk
        Remove-Item -LiteralPath $tempApk -Force -ErrorAction SilentlyContinue
    }
}
if ($installedCert -and $installedCert -ne $appCert) {
    throw "The APK on the phone is signed with $installedCert but this build is $appCert. Either rebuild with the matching signing config, or uninstall $Package first (this drops the login state)."
}
if ($installedCert) { Write-Host "signature: matches the installed package ($($appCert.Substring(0, 12))...)" }
else { Write-Host "signature: $($appCert.Substring(0, 12))... (package not installed yet)" }

# 4. Install. -r keeps app data, so the logged-in session survives test runs.
if (-not $SkipInstall) {
    foreach ($apk in @($appApk, $testApk)) {
        $installOutput = Invoke-AdbText @("-s", $Serial, "install", "-r", $apk)
        if ($installOutput -notmatch "Success") {
            throw "adb install failed for $apk`n$installOutput"
        }
        Write-Host "installed: $([IO.Path]::GetFileName($apk))"
    }
    if ($sdkLevel -ge 33) {
        Invoke-AdbText @("-s", $Serial, "shell", "pm", "grant", $Package, "android.permission.POST_NOTIFICATIONS") | Out-Null
    }
}

# 5. Snapshot the app's SharedPreferences before the suite runs.
#
#    MainActivityWebViewInstrumentedTest contains a "HTTPS logout" case that signs
#    the active profile out for real: it strips the session tokens and clears
#    activeId. On the emulator that hit a throwaway profile; on this phone it hits
#    the account the owner is using, and the app comes back at the login screen.
#    run-as works because qaRelease/debug are debuggable, so the prefs directory can
#    be copied aside inside the app's own data dir and copied back afterwards.
#    (No binary transfer, no root: both copies happen on the device.)
$prefsBackup = "shared_prefs.fnaudiobak"
$canPreserve = $false
if ($PreserveAppState) {
    $identity = Invoke-AdbText @("-s", $Serial, "shell", "run-as", $Package, "id")
    if ($identity -match "uid=\d+") {
        Invoke-AdbText @("-s", $Serial, "shell", "am", "force-stop", $Package) | Out-Null
        $backup = Invoke-AdbText @("-s", $Serial, "shell", "run-as", $Package, "cp", "-r", "shared_prefs", $prefsBackup)
        $canPreserve = (Invoke-AdbText @("-s", $Serial, "shell", "run-as", $Package, "ls", $prefsBackup)) -notmatch "No such file"
        if ($canPreserve) { Write-Host "app state: shared_prefs snapshotted" }
        else { Write-Warning "Could not snapshot shared_prefs; the suite may sign the active profile out. $backup" }
    } else {
        Write-Warning "Package $Package is not debuggable, so shared_prefs cannot be snapshotted; expect the logout case to sign the profile out."
    }
}

# 6. Run the suite directly through adb. Same reason as the emulator script: the
#    Gradle-managed runner trips over the Windows testlog directory, and a direct
#    run keeps the output readable in the console.
$instrumentArgs = @("-s", $Serial, "shell", "am", "instrument", "-w")
if ($TestClass) { $instrumentArgs += @("-e", "class", $TestClass) }
foreach ($pair in $InstrumentArg) {
    $separator = $pair.IndexOf("=")
    if ($separator -lt 1) { throw "InstrumentArg must be key=value, got: $pair" }
    $instrumentArgs += @("-e", $pair.Substring(0, $separator), $pair.Substring($separator + 1))
}
$instrumentArgs += "$Package.test/androidx.test.runner.AndroidJUnitRunner"
# Echo the command with secrets masked: RealNasPlaybackRestoreInstrumentedTest takes
# fnaudioPassword, and this line is also what a reader copies when reproducing a run.
$displayArgs = @()
for ($i = 0; $i -lt $instrumentArgs.Count; $i++) {
    $displayArgs += $instrumentArgs[$i]
    if ($instrumentArgs[$i] -eq "-e" -and ($i + 2) -lt $instrumentArgs.Count -and $instrumentArgs[$i + 1] -match "password|passwd|pwd") {
        $displayArgs += $instrumentArgs[$i + 1]
        $displayArgs += "***"
        $i += 2
    }
}
Write-Host "running: adb $($displayArgs -join ' ')"
$testText = Invoke-AdbText $instrumentArgs
Write-Output $testText

if (-not $NoLog) {
    $logRoot = Join-Path $repoRoot "artifacts\android-device-tests"
    New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $logPath = Join-Path $logRoot "$stamp-$BuildType.log"
    $header = "device=$Serial model=$model sdk=$sdkLevel buildType=$BuildType package=$Package"
    [IO.File]::WriteAllText($logPath, "$header`n`n$testText`n", (New-Object Text.UTF8Encoding($false)))
    Write-Host "log: $logPath"
}

$failed = $testText -match "FAILURES!!!|INSTRUMENTATION_FAILED|INSTRUMENTATION_RESULT: shortMsg=" -or
    $testText -notmatch "OK \(\d+ tests?\)"

# Put the snapshot back even when the suite failed: a red run must not also cost the
# owner their session. The app has to be stopped first, or its in-memory prefs would
# overwrite the restored file on the next flush.
if ($canPreserve) {
    Invoke-AdbText @("-s", $Serial, "shell", "am", "force-stop", $Package) | Out-Null
    $restore = Invoke-AdbText @("-s", $Serial, "shell", "run-as", $Package, "cp", "-r", "$prefsBackup/.", "shared_prefs")
    Invoke-AdbText @("-s", $Serial, "shell", "run-as", $Package, "rm", "-rf", $prefsBackup) | Out-Null
    if ($restore -match "No such file|Permission denied|error") {
        Write-Warning "Restoring shared_prefs may have failed: $restore"
    } else {
        Write-Host "app state: shared_prefs restored"
    }
}

# 7. Confirm the phone really runs the build that was just compiled, rather than a
#    stale copy that adb silently declined to replace.
#
#    The check and the optional restore share one failure path on purpose: a red
#    run is exactly when the phone must not be left running a debuggable build,
#    and the earlier shape (throw first, restore at the end) skipped the restore
#    whenever the suite failed -- which is most of the runs that matter.
$failure = $null
try {
    if ($failed) { throw "Android instrumentation failed; inspect the output above" }

    $versionMatch = Select-String -LiteralPath (Join-Path $androidRoot "app\build.gradle") -Pattern "versionCode\s+(\d+)" | Select-Object -First 1
    $expectedVersionCode = [int]$versionMatch.Matches[0].Groups[1].Value
    $dumpsys = Invoke-AdbText @("-s", $Serial, "shell", "dumpsys", "package", $Package)
    if ($dumpsys -notmatch [regex]::Escape("versionCode=$expectedVersionCode")) {
        throw "Installed package does not expose versionCode=$expectedVersionCode"
    }
} catch {
    $failure = $_
}

# 8. Optional: put the shipped release APK back, so the phone is not left running a
#    debuggable build after a test session.
if ($RestoreRelease) {
    $versionLine = Select-String -LiteralPath (Join-Path $androidRoot "app\build.gradle") -Pattern 'versionName\s+"([^"]+)"' | Select-Object -First 1
    $versionName = $versionLine.Matches[0].Groups[1].Value
    $releaseApk = Join-Path $repoRoot "artifacts\$versionName\fnaudio-android-$versionName-release.apk"
    if (-not (Test-Path -LiteralPath $releaseApk)) { throw "Release APK to restore was not found: $releaseApk" }
    $restoreOutput = Invoke-AdbText @("-s", $Serial, "install", "-r", $releaseApk)
    if ($restoreOutput -notmatch "Success") { throw "Failed to restore the release APK`n$restoreOutput" }
    Write-Host "restored the release APK: $releaseApk"
}

if ($failure) { throw $failure }

Write-Host "Android device tests passed on $Serial ($Package, $BuildType)."

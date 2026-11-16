# 抓一次登录的取证脚本：官方 App（mitmproxy + 模拟器）或 fnAudio 自己的握手日志。
#
# 目的：下次再出现「访问码验证成功但未取得会话 Cookie」或「过几天就不行」时，
# 不用猜。官方 App 走的是同一套网关，把它的请求路径、请求头、响应头（尤其
# Set-Cookie）与我们的并列，就能分清是协议差异、网关行为变化，还是令牌到期。
#
# 两种模式：
#   -Mode official  （默认）启动 AVD，装 mitmproxy 系统 CA，设代理，装官方 APK，
#                   你登录一次，脚本导出 flows 并生成 login-report.md。
#   -Mode ourApp    不装任何东西，只抓 FnOsAuth / OkHttp 的 logcat，
#                   适合「已经装了 fnAudio、只想看失败在哪一步」。
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File tools/capture_official_login.ps1 -InstallMitm
#   powershell -ExecutionPolicy Bypass -File tools/capture_official_login.ps1 -Mode ourApp
#
# 产物统一落在 _external/apk-analysis/captures/<时间戳>/，不进仓库。

[CmdletBinding()]
param(
    [ValidateSet('official', 'ourApp')]
    [string]$Mode = 'official',

    # 为空则用 emulator -list-avds 的第一个。
    [string]$Avd = '',

    # 官方安装包，默认用 references 里那份。
    [string]$Apk = '',

    [int]$Port = 8080,

    [string]$OutDir = '',

    # 首次使用时由脚本在 _external/tooling 下建 venv 并安装 mitmproxy。
    [switch]$InstallMitm,

    # 抓完保留模拟器代理设置（默认清空，避免之后所有流量都走一个已停的代理）。
    [switch]$KeepProxy,

    # 显式指定 SDK 目录（当 ANDROID_HOME 指向的位置没有 platform-tools 时用）。
    [string]$SdkDir = '',

    # SDK 里缺 platform-tools 时，让脚本下载官方的 platform-tools（约 12 MB）。
    [switch]$InstallAdb,

    # 找不到 adb 时不要自动下载（脚本默认会下，双击入口才能一次跑通）。
    [switch]$NoAutoInstall
)

$ErrorActionPreference = 'Stop'
# 控制台默认按 ANSI 解释中文，重定向到文件时尤其乱；显式设成 UTF-8。
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
if ([string]::IsNullOrWhiteSpace($OutDir)) {
    $OutDir = Join-Path $RepoRoot ('_external/apk-analysis/captures/' + $Stamp)
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# 逐个候选目录找 adb：只看 ANDROID_HOME 会让「装了一半的 SDK」（有 emulator、
# 没有 platform-tools）直接失败，而它其实只差一个 platform-tools 目录。
function Resolve-AndroidTool {
    param([string]$CommandName, [string]$RelativePath)
    $candidates = New-Object System.Collections.ArrayList
    if (-not [string]::IsNullOrWhiteSpace($SdkDir)) { [void]$candidates.Add($SdkDir) }
    if (-not [string]::IsNullOrWhiteSpace($env:ANDROID_HOME)) { [void]$candidates.Add($env:ANDROID_HOME) }
    if (-not [string]::IsNullOrWhiteSpace($env:ANDROID_SDK_ROOT)) { [void]$candidates.Add($env:ANDROID_SDK_ROOT) }
    [void]$candidates.Add((Join-Path $RepoRoot 'tools/android-sdk'))
    if (-not [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        [void]$candidates.Add((Join-Path $env:LOCALAPPDATA 'Android/Sdk'))
    }
    if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
        [void]$candidates.Add((Join-Path $env:USERPROFILE 'AppData/Local/Android/Sdk'))
        [void]$candidates.Add((Join-Path $env:USERPROFILE 'Android/Sdk'))
    }
    $tried = New-Object System.Collections.ArrayList
    foreach ($root in $candidates) {
        if ([string]::IsNullOrWhiteSpace($root)) { continue }
        $normalized = $root.Replace('/', '\').TrimEnd('\')
        $path = Join-Path $normalized $RelativePath
        [void]$tried.Add($path)
        if (Test-Path $path) { return @{ Path = $path; Root = $normalized; Tried = $tried } }
    }
    $onPath = Get-Command $CommandName -ErrorAction SilentlyContinue
    if ($onPath -and $onPath.Source) {
        return @{ Path = $onPath.Source; Root = (Split-Path -Parent (Split-Path -Parent $onPath.Source)); Tried = $tried }
    }
    return @{ Path = ''; Root = ''; Tried = $tried }
}

$adbProbe = Resolve-AndroidTool -CommandName 'adb' -RelativePath 'platform-tools/adb.exe'
if (-not $adbProbe.Path) {
    if ($InstallAdb -or -not $NoAutoInstall) {
        Write-Host '   没找到 adb，正在下载官方 platform-tools（约 12 MB）…' -ForegroundColor Yellow
        Write-Host '   不想自动下载请加 -NoAutoInstall，或用 -SdkDir 指定已有的 SDK。' -ForegroundColor DarkGray
        $sdkTarget = Join-Path $RepoRoot 'tools/android-sdk'
        $zipPath = Join-Path $env:TEMP 'platform-tools-latest-windows.zip'
        try {
            Invoke-WebRequest -UseBasicParsing -Uri 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip' -OutFile $zipPath
            New-Item -ItemType Directory -Force -Path $sdkTarget | Out-Null
            Expand-Archive -Path $zipPath -DestinationPath $sdkTarget -Force
            Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
        } catch {
            throw "下载 platform-tools 失败：$($_.Exception.Message)。也可以手动下载后解压到 $sdkTarget。"
        }
        $adbProbe = Resolve-AndroidTool -CommandName 'adb' -RelativePath 'platform-tools/adb.exe'
    }
}
if (-not $adbProbe.Path) {
    $triedList = ($adbProbe.Tried | ForEach-Object { '     - ' + $_ }) -join [Environment]::NewLine
    $hint = @(
        '找不到 adb.exe。已经找过这些位置：',
        $triedList,
        '',
        '常见原因和对策：',
        '   1) ANDROID_HOME 指向的 SDK 只装了 emulator / cmdline-tools，没有 platform-tools。',
        '      补装（SDK 里有 cmdline-tools 时）：',
        '        sdkmanager "platform-tools"',
        '   2) 另一个磁盘上有完整 SDK：用 -SdkDir "D://path//to//android-sdk" 指定。',
        '   3) 干脆没有 platform-tools：加 -InstallAdb，脚本会下载官方的 platform-tools。'
    ) -join [Environment]::NewLine
    throw $hint
}
$AdbPath = $adbProbe.Path
$Sdk = $adbProbe.Root
# 与 adb 分开找：一台机器完全可能「platform-tools 在仓库里、emulator 在
# ANDROID_HOME 里」，用 adb 的根目录去拼 emulator 会漏掉后者。
$emulatorProbe = Resolve-AndroidTool -CommandName 'emulator' -RelativePath 'emulator/emulator.exe'
$Emulator = $emulatorProbe.Path
Write-Host "   adb：$AdbPath" -ForegroundColor DarkGray
if ($Emulator) { Write-Host "   emulator：$Emulator" -ForegroundColor DarkGray }

# adb 第一次调用会往 stderr 打 "daemon not running"，而 $ErrorActionPreference='Stop'
# 会把它当成终止错误。所有外部命令统一走这里：stderr 合并成文本返回，退出码自己判。
function Invoke-Tool {
    param([string]$Exe, [Parameter(ValueFromRemainingArguments = $true)] [object[]]$Rest)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & $Exe @Rest 2>&1
        return @($output | ForEach-Object {
            if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { [string]$_ }
        })
    } finally {
        $ErrorActionPreference = $previous
    }
}
function Adb { Invoke-Tool -Exe $AdbPath @args }

function Write-Step($text) { Write-Host ''; Write-Host "== $text" -ForegroundColor Cyan }
function Write-Note($text) { Write-Host "   $text" -ForegroundColor DarkGray }

# 不用 adb wait-for-device：没有设备时它会一直阻塞，脚本看起来像卡死。
function Wait-Boot([int]$TimeoutSeconds = 600) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $state = (Adb get-state) -join ''
        if ($state -match 'device') {
            $boot = (Adb shell getprop sys.boot_completed) -join ''
            if ($boot.Trim() -eq '1') { Start-Sleep -Seconds 2; return $true }
        }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Reset-Proxy {
    Adb shell settings put global http_proxy ':0' | Out-Null
    Adb shell settings delete global http_proxy | Out-Null
}

# ---------------------------------------------------------------- ourApp 模式
if ($Mode -eq 'ourApp') {
    Write-Step '抓 fnAudio 自己的登录日志'
    if (-not (Wait-Boot 60)) { throw '没有就绪的设备：先连上手机（adb devices）或让脚本启动模拟器' }
    $LogPath = Join-Path $OutDir 'logcat.txt'
    Adb logcat -c | Out-Null
    $log = Start-Process -FilePath $AdbPath -ArgumentList @('logcat', '-v', 'time', '-s', 'FnOsAuth:V', 'OkHttp:D', 'AndroidRuntime:E') `
        -PassThru -WindowStyle Hidden -RedirectStandardOutput $LogPath
    Write-Note "日志：$LogPath"
    Write-Host '   现在在手机上打开 fnAudio，走一次会失败的登录。' -ForegroundColor Yellow
    Read-Host '   完成后按回车' | Out-Null
    Stop-Process -Id $log.Id -Force -ErrorAction SilentlyContinue
    $report = Join-Path $OutDir 'login-report.md'
    & python (Join-Path $PSScriptRoot 'capture_login_report.py') --logcat $LogPath --out $report
    Write-Host "报告：$report" -ForegroundColor Green
    return
}

# ------------------------------------------------------------- official 模式
Write-Step '准备 mitmproxy'
$Venv = Join-Path $RepoRoot '_external/tooling/mitm-venv'
$Mitm = Join-Path $Venv 'Scripts/mitmdump.exe'
if (-not (Test-Path $Mitm)) {
    if (-not $InstallMitm) {
        throw "没有 mitmproxy。用 -InstallMitm 让脚本在 $Venv 建 venv 安装（约 1-2 分钟），或自己装好后重跑。"
    }
    Write-Note "创建 venv：$Venv"
    & python -m venv $Venv
    & (Join-Path $Venv 'Scripts/python.exe') -m pip install --disable-pip-version-check -q mitmproxy
    if (-not (Test-Path $Mitm)) { throw 'mitmproxy 安装失败' }
}
Write-Note "mitmdump：$Mitm"

# Android 的系统 CA 目录要求文件名为 <subject_hash_old>.<n>，openssl 直接能算。
$OpenSsl = (Get-Command openssl -ErrorAction SilentlyContinue)
if (-not $OpenSsl) {
    $gitOpenSsl = 'C:\Program Files\Git\usr\bin\openssl.exe'
    if (Test-Path $gitOpenSsl) { $OpenSsl = Get-Item $gitOpenSsl } else { throw '找不到 openssl（装 Git for Windows 即可）' }
}
$OpenSslPath = if ($OpenSsl.Source) { $OpenSsl.Source } else { $OpenSsl.FullName }

$ConfDir = Join-Path $RepoRoot '_external/tooling/mitm-conf'
$CertPem = Join-Path $ConfDir 'mitmproxy-ca-cert.pem'
New-Item -ItemType Directory -Force -Path $ConfDir | Out-Null
if (-not (Test-Path $CertPem)) {
    Write-Note '首次生成 mitmproxy CA…'
    $seed = Start-Process -FilePath $Mitm -ArgumentList @('-q', '-p', '0', '--set', "confdir=$ConfDir") -PassThru -WindowStyle Hidden
    for ($i = 0; $i -lt 30; $i++) { if (Test-Path $CertPem) { break }; Start-Sleep -Milliseconds 500 }
    Stop-Process -Id $seed.Id -Force -ErrorAction SilentlyContinue
    if (-not (Test-Path $CertPem)) { throw "mitmproxy 没有生成 CA：$CertPem" }
}
$CaHash = (& $OpenSslPath x509 -inform PEM -subject_hash_old -in $CertPem | Select-Object -First 1).Trim()
if (-not $CaHash) { throw '计算 CA subject_hash_old 失败' }
Write-Note "CA 指纹名：$CaHash.0"

Write-Step '启动模拟器（-writable-system）'
if (-not (Test-Path $Emulator)) {
    throw "找不到 emulator：$Emulator。抓官方 App 需要它；只想看 fnAudio 自己的日志请用 -Mode ourApp。"
}
if ($Avd -eq '') {
    $Avd = (Invoke-Tool -Exe $Emulator -list-avds | Select-Object -First 1)
    if (-not $Avd) { throw '没有可用 AVD（emulator -list-avds 为空）' }
}
Write-Note "AVD：$Avd"
$existing = (Adb devices) -join "`n"
if ($existing -notmatch 'emulator-\d+\s+device') {
    Start-Process -FilePath $Emulator -ArgumentList @('-avd', $Avd, '-writable-system', '-no-snapshot-load', '-no-boot-anim', '-gpu', 'swiftshader_indirect') | Out-Null
}
if (-not (Wait-Boot)) { throw '模拟器没有启动完成' }

Write-Step '把 mitmproxy CA 装成系统证书'
# 系统 CA 才能被 Flutter 的 dart:io 信任；Android 7+ 不再信任用户证书。
Adb root | Out-Null
Start-Sleep -Seconds 2
$remount = (Adb remount) -join ''
if ($remount -notmatch 'succeeded|remount succeeded') {
    Write-Note 'adb remount 未成功：该镜像可能不是 Google APIs（Play 镜像无法 remount）。'
}
Adb push $CertPem "/system/etc/security/cacerts/$CaHash.0" | Out-Null
Adb shell chmod 644 "/system/etc/security/cacerts/$CaHash.0" | Out-Null
Adb reboot | Out-Null
if (-not (Wait-Boot)) { throw '重启后模拟器没有回来' }
$installed = (Adb shell ls "/system/etc/security/cacerts/$CaHash.0") -join ''
if ($installed -notmatch 'No such file') { Write-Note 'CA 已就位' } else { Write-Note 'CA 可能没装上，HTTPS 抓包会失败' }

Write-Step '设置模拟器代理'
# 10.0.2.2 是模拟器里的宿主机地址。
Adb shell settings put global http_proxy "10.0.2.2:$Port" | Out-Null
Write-Note "代理：10.0.2.2:$Port"

Write-Step '开始抓包'
$Flow = Join-Path $OutDir 'login.mitm'
$MitmErr = Join-Path $OutDir 'mitm.err.txt'
$mitm = Start-Process -FilePath $Mitm -ArgumentList @('-q', '-p', "$Port", '--set', "confdir=$ConfDir", '-w', $Flow) `
    -PassThru -WindowStyle Hidden -RedirectStandardError $MitmErr
Start-Sleep -Seconds 2
if ($mitm.HasExited) { throw "mitmdump 启动失败，看 $MitmErr" }
Write-Note "flows：$Flow"

if ([string]::IsNullOrWhiteSpace($Apk)) {
    $Apk = Join-Path $RepoRoot 'references/FNAPP/fnos_1.37.3_1910221535.apk'
}
if (Test-Path $Apk) {
    Write-Step '安装官方 App'
    Adb install -r $Apk | Out-Null
} else {
    Write-Note "没找到官方安装包（$Apk），请在模拟器里自行安装。"
}

Write-Host ''
Write-Host '   请在模拟器里打开飞牛 App，用 FN ID 完整登录一次（外网模式）。' -ForegroundColor Yellow
Write-Host '   成功或失败都按回车，脚本会把 login.mitm 导出成报告。' -ForegroundColor Yellow
Read-Host '   按回车结束抓包' | Out-Null

Stop-Process -Id $mitm.Id -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
if (-not $KeepProxy) { Reset-Proxy }

Write-Step '生成报告'
$dump = Join-Path $OutDir 'flows.txt'
# --flow-detail 3 会把请求头、响应头、正文都打出来，报告脚本只挑登录相关段。
& cmd /c "`"$Mitm`" -nr `"$Flow`" --flow-detail 3 > `"$dump`" 2>&1"
$report = Join-Path $OutDir 'login-report.md'
& python (Join-Path $PSScriptRoot 'capture_login_report.py') --dump $dump --out $report
Write-Host ''
Write-Host "报告：$report" -ForegroundColor Green
Write-Host "原始抓包：$Flow" -ForegroundColor Green

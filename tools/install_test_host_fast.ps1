[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$Package,

    [string]$HostName = '198.51.100.24',

    [string]$UserName = 'root',

    [ValidateRange(1, 65535)]
    [int]$SshPort = 22,

    [switch]$UseSudo,

    [string]$RemotePackageDirectory = '/vol1/1000/fnaudio',

    [Parameter(Mandatory)]
    [string]$Password,

    [string]$HostKey = 'ssh-ed25519 255 SHA256:7PMkKVzFzH7a8/ekqz+eU06StFKg7P1koPpNDi11MmM'
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $Package -PathType Leaf)) {
    throw "Package not found: $Package"
}
if ([IO.Path]::GetExtension($Package).ToLowerInvariant() -ne '.fpk') {
    throw "Package must be an .fpk file: $Package"
}

$plink = 'C:\Program Files\PuTTY\plink.exe'
$pscp = 'C:\Program Files\PuTTY\pscp.exe'
foreach ($tool in @($plink, $pscp)) {
    if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) {
        throw "PuTTY tool not found: $tool"
    }
}

$packageName = [IO.Path]::GetFileName($Package)
if ($packageName -notmatch '^[A-Za-z0-9._-]+\.fpk$') {
    throw "Package filename contains unsupported shell characters: $packageName"
}
$remotePackageDirectory = $RemotePackageDirectory.TrimEnd('/')
if ($remotePackageDirectory -notmatch '^/(?:[A-Za-z0-9._-]+/)*[A-Za-z0-9._-]+$') {
    throw "RemotePackageDirectory must be an absolute POSIX path containing only safe path segments: $RemotePackageDirectory"
}
$remotePackage = "$remotePackageDirectory/$packageName"

# This value is passed to the remote shell more than once. Restrict it to a
# shell-safe POSIX path, then make an explicitly selected destination usable
# before PSCP attempts the upload.
$remoteDirectoryErrorFile = Join-Path ([IO.Path]::GetTempPath()) ("fnaudio-plink-directory-{0}.stderr" -f [Guid]::NewGuid().ToString('N'))
$previousErrorActionPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = 'Continue'
    # PSCP uploads as the SSH account, so this directory must be created by
    # that account even when the later application swap uses sudo.
    $directoryCommand = "mkdir -p -- '$remotePackageDirectory'"
    & $plink -batch -hostkey $HostKey -P $SshPort -l $UserName -pw $Password $HostName $directoryCommand 2> $remoteDirectoryErrorFile
    $directoryExitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorActionPreference
    if ($directoryExitCode -ne 0) {
        $remoteError = (Get-Content -LiteralPath $remoteDirectoryErrorFile -Raw -ErrorAction SilentlyContinue).Trim()
        throw "Unable to create remote package directory with exit code $directoryExitCode$(if ($remoteError) { ": $remoteError" })"
    }
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $remoteDirectoryErrorFile -Force -ErrorAction SilentlyContinue
}

# Keep the full deployment transaction on the NAS. The rollback trap restores
# both fnOS control files and application payload if a post-swap check fails.
$remoteScript = @'
set -euo pipefail

PACKAGE="$1"
APPDEST=/vol1/@appcenter/fnaudio
CONTROL=/var/apps/fnaudio
PKGETC=/vol1/@appconf/fnaudio
PKGVAR=/vol1/@appdata/fnaudio
BACKUP_ROOT=/vol1/1000/fnaudio/fast-deploy-backups
RUN_ROOT=/vol1/1000/fnaudio
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RUN_ROOT"
RUN_DIR="$(mktemp -d "$RUN_ROOT/.fnaudio-fast-deploy.XXXXXX")"
BACKUP_DIR=""
APP_MOVED=0
CONTROL_MOVED=0
COMMITTED=0

rollback() {
  status=$?
  if [ "$COMMITTED" -ne 1 ]; then
    echo "fast deploy failed; restoring previous application" >&2
    if [ -f "$CONTROL/cmd/main" ]; then
      TRIM_APPDEST="$APPDEST" TRIM_PKGETC="$PKGETC" TRIM_PKGVAR="$PKGVAR" bash "$CONTROL/cmd/main" stop || true
    fi
    if [ "$CONTROL_MOVED" -eq 1 ] && [ -d "$BACKUP_DIR/control" ]; then
      rm -rf "$CONTROL"
      mv "$BACKUP_DIR/control" "$CONTROL"
    fi
    if [ "$APP_MOVED" -eq 1 ] && [ -d "$BACKUP_DIR/appcenter" ]; then
      rm -rf "$APPDEST"
      mv "$BACKUP_DIR/appcenter" "$APPDEST"
    fi
    if [ -f "$CONTROL/cmd/main" ]; then
      TRIM_APPDEST="$APPDEST" TRIM_PKGETC="$PKGETC" TRIM_PKGVAR="$PKGVAR" bash "$CONTROL/cmd/main" start || true
    fi
  fi
  if [ -n "${RUN_DIR:-}" ] && [ -d "$RUN_DIR" ]; then
    rm -rf "$RUN_DIR"
  fi
  exit "$status"
}
trap rollback ERR

[ -f "$PACKAGE" ] || { echo "package missing: $PACKAGE" >&2; exit 2; }
mkdir -p "$BACKUP_ROOT"
chmod 700 "$BACKUP_ROOT"
BACKUP_DIR="$(mktemp -d "$BACKUP_ROOT/${STAMP}.XXXXXX")"
chmod 700 "$BACKUP_DIR"
tar -xf "$PACKAGE" -C "$RUN_DIR"
[ -f "$RUN_DIR/manifest" ] && [ -f "$RUN_DIR/app.tgz" ] || { echo "invalid FPK layout" >&2; exit 2; }
# fnOS aligns manifest keys with spaces and Windows-built FPKs retain CRLF.
sed 's/[[:space:]]//g' "$RUN_DIR/manifest" | grep -qx 'appname=fnaudio' || { echo "not an fnAudio FPK" >&2; exit 2; }

PAYLOAD="$RUN_DIR/payload"
CONTROL_STAGE="$RUN_DIR/control"
mkdir -p "$PAYLOAD" "$CONTROL_STAGE"
tar -xzf "$RUN_DIR/app.tgz" -C "$PAYLOAD"
if [ ! -f "$PAYLOAD/server/server.py" ] && [ ! -f "$PAYLOAD/target/server/server.py" ]; then
  echo "FPK payload has no fnAudio server" >&2
  exit 2
fi
cp -a "$RUN_DIR"/cmd "$RUN_DIR"/config "$RUN_DIR"/wizard "$RUN_DIR"/manifest "$RUN_DIR"/ICON.PNG "$RUN_DIR"/ICON_256.PNG "$CONTROL_STAGE/"
# Windows-generated FPK archives can lose POSIX execute bits. fnOS invokes
# cmd/main directly for lifecycle checks, so restore them before the swap.
find "$CONTROL_STAGE/cmd" -type f -exec chmod 755 {} +

if [ -f "$CONTROL/cmd/main" ]; then
  TRIM_APPDEST="$APPDEST" TRIM_PKGETC="$PKGETC" TRIM_PKGVAR="$PKGVAR" bash "$CONTROL/cmd/main" stop
fi

mkdir -p "$BACKUP_DIR"
if [ -d "$APPDEST" ]; then
  mv "$APPDEST" "$BACKUP_DIR/appcenter"
  APP_MOVED=1
fi
mv "$PAYLOAD" "$APPDEST"
if [ -d "$CONTROL" ]; then
  mv "$CONTROL" "$BACKUP_DIR/control"
  CONTROL_MOVED=1
fi
mv "$CONTROL_STAGE" "$CONTROL"

TRIM_APPDEST="$APPDEST" TRIM_PKGETC="$PKGETC" TRIM_PKGVAR="$PKGVAR" bash "$CONTROL/cmd/upgrade_callback"
TRIM_APPDEST="$APPDEST" TRIM_PKGETC="$PKGETC" TRIM_PKGVAR="$PKGVAR" bash "$CONTROL/cmd/main" start
TRIM_APPDEST="$APPDEST" TRIM_PKGETC="$PKGETC" TRIM_PKGVAR="$PKGVAR" bash "$CONTROL/cmd/main" status

VERSION="$(sed -n 's/^version[[:space:]]*=[[:space:]]*//p' "$CONTROL/manifest" | head -n 1)"
PORT="$(/var/apps/python312/target/bin/python3 - "$PKGETC/config.json" <<'PY'
import json, sys
with open(sys.argv[1], encoding='utf-8') as fh:
    print(int(json.load(fh).get('server_port') or 53199))
PY
)"
/var/apps/python312/target/bin/python3 - "$PORT" <<'PY'
import socket, sys
with socket.create_connection(('127.0.0.1', int(sys.argv[1])), timeout=3):
    pass
PY

COMMITTED=1
if [ -d "$RUN_DIR" ]; then rm -rf "$RUN_DIR"; fi
echo "FAST_DEPLOY_OK version=$VERSION port=$PORT backup=$BACKUP_DIR"
'@

$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remoteScript))

& $pscp -batch -hostkey $HostKey -P $SshPort -l $UserName -pw $Password $Package "${HostName}:$remotePackage"
if ($LASTEXITCODE -ne 0) { throw "Package upload failed with exit code $LASTEXITCODE" }

if ($UseSudo) {
    $encodedPassword = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Password))
    $remoteCommand = "echo '$encodedPassword' | base64 -d | sudo -S -p '' bash -c `"echo '$encoded' | base64 -d | bash -s -- '$remotePackage'`""
}
else {
    $remoteCommand = "echo $encoded | base64 -d | bash -s -- '$remotePackage'"
}
$remoteCommandFile = Join-Path ([IO.Path]::GetTempPath()) ("fnaudio-plink-{0}.txt" -f [Guid]::NewGuid().ToString('N'))
$remoteErrorFile = Join-Path ([IO.Path]::GetTempPath()) ("fnaudio-plink-{0}.stderr" -f [Guid]::NewGuid().ToString('N'))
$previousErrorActionPreference = $ErrorActionPreference
try {
    # Passing a quoted bash pipeline as a native PowerShell argument can be
    # silently truncated by Windows argument parsing. Plink's -m option keeps
    # the remote command byte-for-byte and gives us a reliable completion marker.
    [IO.File]::WriteAllText($remoteCommandFile, $remoteCommand + "`n", [Text.UTF8Encoding]::new($false))
    # fnOS prints a harmless missing-home warning for the admin account on
    # stderr. Native stderr is a PowerShell error record under Stop semantics,
    # so defer judgment to Plink's exit code and the explicit remote marker.
    $ErrorActionPreference = 'Continue'
    $deployOutput = & $plink -batch -hostkey $HostKey -P $SshPort -l $UserName -pw $Password -m $remoteCommandFile $HostName 2> $remoteErrorFile
    $deployExitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorActionPreference
    $deployOutput | ForEach-Object { Write-Output $_ }
    if ($deployExitCode -ne 0) {
        $remoteError = (Get-Content -LiteralPath $remoteErrorFile -Raw -ErrorAction SilentlyContinue).Trim()
        throw "Fast deployment failed with exit code $deployExitCode$(if ($remoteError) { ": $remoteError" })"
    }
    if (($deployOutput | Out-String) -notmatch 'FAST_DEPLOY_OK') {
        throw "Fast deployment did not return its completion marker; the package may only have been uploaded."
    }
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $remoteCommandFile -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $remoteErrorFile -Force -ErrorAction SilentlyContinue
}

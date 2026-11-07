"""Deploy an fnAudio FPK to a live fNOS test host over SSH.

Usage:
    python tools/deploy_fpk.py --host 192.168.5.141 --user root --password ... \
        --fpk artifacts/0.2.139/fnaudio-0.2.139-fnpack.fpk [--sudo]

Both plain-root and password-sudo hosts are supported. The remote side keeps the
previous app/control trees under /vol1/1000/fnaudio/upgrade-backups/<stamp> and
rolls back automatically if the new build fails to start.
"""

from __future__ import annotations

import argparse
import hashlib
import posixpath
import sys
import time

import paramiko

REMOTE_ROOT = "/vol1/1000/fnaudio"

DEPLOY = r'''set -uo pipefail
PACKAGE="$1"
STAMP="$2"
APPDEST=/usr/local/apps/@appcenter/fnaudio
CONTROL=/var/apps/fnaudio
CONF=/usr/local/apps/@appconf/fnaudio
DATA=/usr/local/apps/@appdata/fnaudio
ROOT=/vol1/1000/fnaudio
BACKUP="$ROOT/upgrade-backups/$STAMP"
RUN="$ROOT/.fnaudio-upgrade.$STAMP"

say(){ echo ">> $*"; }
fail(){ echo "!! $*" >&2; exit 1; }

start_app(){
  TRIM_APPDEST="$APPDEST" TRIM_PKGETC="$CONF" TRIM_PKGVAR="$DATA" \
    bash "$CONTROL/cmd/main" start
}

rollback(){
  rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "ROLLBACK rc=$rc" >&2
    TRIM_APPDEST="$APPDEST" TRIM_PKGETC="$CONF" TRIM_PKGVAR="$DATA" \
      bash "$CONTROL/cmd/main" stop >/dev/null 2>&1 || true
    if [ -d "$BACKUP/control" ]; then rm -rf "$CONTROL"; mv "$BACKUP/control" "$CONTROL"; fi
    if [ -d "$BACKUP/app" ]; then rm -rf "$APPDEST"; mv "$BACKUP/app" "$APPDEST"; fi
    [ -f "$CONTROL/cmd/main" ] && start_app >/dev/null 2>&1 || true
  fi
  rm -rf "$RUN"
  exit "$rc"
}
trap rollback EXIT

say "whoami=$(id -un) pkg=$PACKAGE"
[ -f "$PACKAGE" ] || fail "package missing"
mkdir -p "$BACKUP" "$RUN" || fail "cannot create work dirs"

say "unpacking"
tar -xf "$PACKAGE" -C "$RUN" || fail "outer tar failed"
[ -f "$RUN/app.tgz" ] || fail "app.tgz missing"
tar -xzf "$RUN/app.tgz" -C "$RUN" || fail "inner tar failed"
find "$RUN/cmd" -type f -exec chmod 755 {} + 2>/dev/null || true

REDEPLOY=0
if [ -f "$CONTROL/cmd/main" ]; then
  REDEPLOY=1
  say "stopping current instance"
  TRIM_APPDEST="$APPDEST" TRIM_PKGETC="$CONF" TRIM_PKGVAR="$DATA" \
    bash "$CONTROL/cmd/main" stop || say "stop returned non-zero (continuing)"
  for i in $(seq 1 20); do
    pgrep -f "fnaudio/server/server.py" >/dev/null 2>&1 || break
    sleep 0.5
  done
  pgrep -f "fnaudio/server/server.py" >/dev/null 2>&1 && fail "old server still running"
fi

say "moving old trees to $BACKUP"
[ -e "$APPDEST" ] && mv "$APPDEST" "$BACKUP/app" || true
[ -e "$CONTROL" ] && mv "$CONTROL" "$BACKUP/control" || true
mkdir -p "$CONTROL" "$APPDEST"

for d in bin server target ui www; do
  [ -d "$RUN/$d" ] && mv "$RUN/$d" "$APPDEST/" || say "warn: $d missing in package"
done
for f in cmd config wizard manifest ICON.PNG ICON_256.PNG; do
  [ -e "$RUN/$f" ] && mv "$RUN/$f" "$CONTROL/" || say "warn: $f missing in package"
done

if [ "$REDEPLOY" -eq 1 ] && [ -f "$CONTROL/cmd/upgrade_callback" ]; then
  say "running upgrade_callback"
  TRIM_APPDEST="$APPDEST" TRIM_PKGETC="$CONF" TRIM_PKGVAR="$DATA" \
    bash "$CONTROL/cmd/upgrade_callback" || say "upgrade_callback failed (continuing)"
fi

say "starting"
if ! TRIM_APPDEST="$APPDEST" TRIM_PKGETC="$CONF" TRIM_PKGVAR="$DATA" \
      bash "$CONTROL/cmd/main" start; then
  echo 'START_FAILED_LOG_BEGIN' >&2
  tail -40 "$DATA/info.log" >&2 || true
  echo 'START_FAILED_LOG_END' >&2
  exit 1
fi

PORT=$(python3 - "$CONF/config.json" <<'PY'
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        print(int(json.load(fh).get("server_port") or 53199))
except Exception:
    print(53199)
PY
)

HEALTH=""
for i in $(seq 1 30); do
  HEALTH=$(curl -fsS --max-time 4 "http://127.0.0.1:${PORT}/api/health" 2>/dev/null) && break
  sleep 1
done
[ -n "$HEALTH" ] || { echo 'HEALTH_FAILED_LOG_BEGIN' >&2; tail -40 "$DATA/info.log" >&2; echo 'HEALTH_FAILED_LOG_END' >&2; exit 1; }

say "verifying"
printf 'VERSION='; sed -n 's/^version[[:space:]]*=[[:space:]]*//p' "$CONTROL/manifest" | head -1
printf 'PORT=%s\n' "$PORT"
printf 'HEALTH=%s\n' "$HEALTH"
printf 'ASSET_STAMP='; grep -o 'v=[0-9][^"&]*' "$APPDEST/ui/index.html" 2>/dev/null | head -1
printf 'INDEX_HAS_LISTTOOLBAR=%s\n' "$(grep -c 'listToolbar' "$APPDEST/ui/index.html" 2>/dev/null || true)"
printf 'APPJS_HAS_FLATPLAYALL=%s\n' "$(grep -c 'FLAT_PLAY_ALL_VIEWS' "$APPDEST/ui/app.js" 2>/dev/null || true)"
printf 'SERVER_PID='; pgrep -f "fnaudio/server/server.py" | head -1
printf 'UI_FILES='; find "$APPDEST/ui" -maxdepth 1 -type f | wc -l
printf 'SERVER_FILES='; find "$APPDEST/server" -type f | wc -l
trap - EXIT
rm -rf "$RUN"
echo "DEPLOY_OK BACKUP=$BACKUP"
'''


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def run_stream(chan) -> str:
    out = b""
    while True:
        if chan.recv_ready():
            out += chan.recv(65536)
        elif chan.exit_status_ready():
            while chan.recv_ready():
                out += chan.recv(65536)
            break
        else:
            time.sleep(0.1)
    return out.decode("utf-8", "replace")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", required=True)
    ap.add_argument("--fpk", required=True)
    ap.add_argument("--sudo", action="store_true", help="run the remote script through password sudo")
    ap.add_argument("--stamp", default="")
    args = ap.parse_args()

    stamp = args.stamp or time.strftime("%Y%m%d-%H%M%S")
    local_sha = sha256_of(args.fpk)
    pkg_name = posixpath.basename(args.fpk)
    remote_pkg = posixpath.join(REMOTE_ROOT, pkg_name)
    print(f"[local] {pkg_name} sha256={local_sha}")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(args.host, 22, args.user, args.password, timeout=15, banner_timeout=20)

    def as_root(cmd: str) -> str:
        chan = client.get_transport().open_session()
        if args.sudo:
            chan.exec_command(f"printf '%s\\n' {params_quote(args.password)} | sudo -S -p '' bash -c {params_quote(cmd)} 2>&1")
        else:
            chan.exec_command(f"bash -c {params_quote(cmd)} 2>&1")
        return run_stream(chan)

    try:
        print(f"[prep] {as_root(f'mkdir -p {REMOTE_ROOT}/upgrade-backups && ls -ld {REMOTE_ROOT}').strip()}")
        sftp = client.open_sftp()
        print(f"[upload] -> {remote_pkg}")
        sftp.put(args.fpk, remote_pkg)
        st = sftp.stat(remote_pkg)
        print(f"[upload] done size={st.st_size}")
        remote_script = f"/tmp/deploy_fpk_{stamp}.sh"
        with sftp.file(remote_script, "w") as fh:
            fh.write(DEPLOY)
        sftp.close()

        if args.sudo:
            cmd = (
                f"printf '%s\\n' {params_quote(args.password)} | "
                f"sudo -S -p '' bash {remote_script} {params_quote(remote_pkg)} {params_quote(stamp)} 2>&1"
            )
        else:
            cmd = f"bash {remote_script} {params_quote(remote_pkg)} {params_quote(stamp)} 2>&1"

        chan = client.get_transport().open_session()
        chan.exec_command(cmd)
        out = run_stream(chan)
        code = chan.recv_exit_status()
        print(out)
        print(f"[remote] exit={code}")

        # remote sha check
        chan2 = client.get_transport().open_session()
        if args.sudo:
            chan2.exec_command(f"printf '%s\\n' {params_quote(args.password)} | sudo -S -p '' sha256sum {remote_pkg} 2>&1")
        else:
            chan2.exec_command(f"sha256sum {remote_pkg} 2>&1")
        sumline = run_stream(chan2).strip()
        print(f"[remote] {sumline}")
        if local_sha not in sumline.upper():
            print("[FAIL] remote package hash mismatch")
            return 3

        chan3 = client.get_transport().open_session()
        chan3.exec_command(f"rm -f {remote_script} 2>/dev/null; echo cleaned")
        run_stream(chan3)
        return 0 if code == 0 else code
    finally:
        client.close()


def params_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


if __name__ == "__main__":
    sys.exit(main())

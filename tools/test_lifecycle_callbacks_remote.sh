#!/bin/sh
set -eu

ROOT="$(mktemp -d /tmp/fnaudio-lifecycle.XXXXXX)"
trap 'rm -rf "$ROOT"' EXIT
APP="$ROOT/app"
ETC="$ROOT/etc"
VAR="$ROOT/var"
mkdir -p "$APP" "$ETC" "$VAR"
printf 'service_port          = 19001\n' > "$APP/manifest"
printf '%s\n' '{"library_path":"/vol1/1000/music","library_paths":["/vol1/1000/music"],"server_name":"custom","server_port":19001,"output":"dac"}' > "$ETC/config.json"

export TRIM_APPDEST="$APP" TRIM_PKGETC="$ETC" TRIM_PKGVAR="$VAR"
export wizard_library_paths="/vol1/1000/music" wizard_server_port=""
/tmp/fnaudio-install_callback

test "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["server_port"])' "$ETC/config.json")" = 19001
test "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["output"])' "$ETC/config.json")" = dac

export wizard_server_port=19002
/tmp/fnaudio-config_callback
test "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["server_port"])' "$ETC/config.json")" = 19002
grep -q 'service_port[[:space:]]*= 19002' "$APP/manifest"

unset wizard_server_port
/tmp/fnaudio-upgrade_callback
grep -q 'service_port[[:space:]]*= 19002' "$APP/manifest"
test -f "$ETC/config.json"

export wizard_uninstall_mode=keep
/tmp/fnaudio-uninstall_callback
test -f "$ETC/config.json"

export wizard_uninstall_mode=purge
/tmp/fnaudio-uninstall_callback
test -e "$ETC" && test -e "$VAR"
printf 'lifecycle-callbacks=pass\n'

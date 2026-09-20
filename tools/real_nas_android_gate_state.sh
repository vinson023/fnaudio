#!/bin/sh
# Prepare/restore a stopped server session around the Android real-NAS gate.
set -eu

MODE="${1:?Usage: real_nas_android_gate_state.sh prepare|restore snapshot.json}"
SNAPSHOT="${2:?Snapshot path is required}"
BASE="${FNAUDIO_BASE_URL:-http://127.0.0.1:53199}"

api() {
  curl -fsS -H 'X-Fnaudio-Internal: 1' "$@"
}

post_json() {
  endpoint="$1"
  api -X POST -H 'Content-Type: application/json' --data-binary @- "$BASE$endpoint"
}

case "$MODE" in
  prepare)
    api "$BASE/api/playback/core" > "$SNAPSHOT"
    python3 - "$SNAPSHOT" <<'PY'
import json
import sys

state = json.load(open(sys.argv[1], encoding="utf-8"))["state"]
if state.get("transport") != "STOPPED":
    raise SystemExit("Android gate requires a stopped pre-test session")
if not state.get("queue") or not state.get("current"):
    raise SystemExit("Android gate requires a restorable queue and current track")
print(f"android_gate_snapshot=1 queue_length={len(state['queue'])} current={state['current']}")
PY
    printf '%s\n' '{"target_id":"local"}' | post_json /api/playback/target
    ;;
  restore)
    [ -f "$SNAPSHOT" ] || { echo "Snapshot not found: $SNAPSHOT" >&2; exit 2; }
    printf '%s\n' '{"action":"stop"}' | post_json /api/playback/control >/dev/null || true
    python3 - "$SNAPSHOT" <<'PY' | post_json /api/playback/queue >/dev/null
import json
import sys

state = json.load(open(sys.argv[1], encoding="utf-8"))["state"]
print(json.dumps({
    "queue": state["queue"],
    "current_id": state.get("current"),
    "repeat": state.get("repeat", "off"),
    "shuffle": bool(state.get("shuffle")),
}, separators=(",", ":")))
PY
    python3 - "$SNAPSHOT" <<'PY' | post_json /api/playback/target >/dev/null
import json
import sys

state = json.load(open(sys.argv[1], encoding="utf-8"))["state"]
print(json.dumps({"target_id": state.get("target_id") or "local"}, separators=(",", ":")))
PY
    python3 - "$SNAPSHOT" <<'PY' | post_json /api/playback/control >/dev/null
import json
import sys

state = json.load(open(sys.argv[1], encoding="utf-8"))["state"]
print(json.dumps({
    "action": "stop",
    "target_id": state.get("target_id") or "local",
}, separators=(",", ":")))
PY
    api "$BASE/api/playback/core" > "${SNAPSHOT}.after.json"
    python3 - "$SNAPSHOT" "${SNAPSHOT}.after.json" <<'PY'
import json
import sys

before = json.load(open(sys.argv[1], encoding="utf-8"))["state"]
after = json.load(open(sys.argv[2], encoding="utf-8"))["state"]
fields = ("queue", "current", "repeat", "shuffle", "transport", "target_id")
mismatch = {key: {"before": before.get(key), "after": after.get(key)} for key in fields if before.get(key) != after.get(key)}
print("android_gate_restore_verified=" + ("1" if not mismatch else "0"))
if mismatch:
    print(json.dumps(mismatch, ensure_ascii=False))
    raise SystemExit(1)
PY
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    exit 2
    ;;
esac

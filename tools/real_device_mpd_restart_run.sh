#!/bin/sh
# Controlled MPD restart acceptance with exact PlaybackCore session recovery.
set -eu

BASE="${FNAUDIO_BASE_URL:-http://127.0.0.1:18080}"
LOG="${1:-/vol1/1000/fnaudio-mpd-restart.log}"
BEFORE="${LOG}.before.json"
AFTER="${LOG}.after.json"

restore() {
  code=$?
  trap - EXIT INT TERM
  [ -f "$BEFORE" ] || exit "$code"
  python3 - "$BEFORE" <<'PY' > "${BEFORE}.restore.jsonl"
import json, sys
s = json.load(open(sys.argv[1], encoding="utf-8"))["state"]
print(json.dumps({"target_id": s.get("target_id", "local")}))
print(json.dumps({"queue": s.get("queue", []), "current_id": s.get("current"), "repeat": s.get("repeat", "off"), "shuffle": bool(s.get("shuffle"))}))
print(json.dumps({"action": "play" if s.get("transport") == "PLAYING" else "stop", "target_id": s.get("target_id", "local")}))
PY
  sed -n '1p' "${BEFORE}.restore.jsonl" | curl -fsS -X POST -H 'Content-Type: application/json' --data-binary @- "$BASE/api/playback/target" >/dev/null || code=1
  sed -n '2p' "${BEFORE}.restore.jsonl" | curl -fsS -X POST -H 'Content-Type: application/json' --data-binary @- "$BASE/api/playback/queue" >/dev/null || code=1
  sed -n '3p' "${BEFORE}.restore.jsonl" | curl -fsS -X POST -H 'Content-Type: application/json' --data-binary @- "$BASE/api/playback/control" >/dev/null || code=1
  rm -f "${BEFORE}.restore.jsonl"
  curl -fsS "$BASE/api/playback/core" > "$AFTER" || code=1
  python3 - "$BEFORE" "$AFTER" >> "$LOG" 2>&1 <<'PY' || code=1
import json, sys
before = json.load(open(sys.argv[1], encoding="utf-8"))["state"]
after = json.load(open(sys.argv[2], encoding="utf-8"))["state"]
fields = ("target_id", "queue", "current", "repeat", "shuffle", "transport")
mismatch = {k: [before.get(k), after.get(k)] for k in fields if before.get(k) != after.get(k)}
print("restore_verified=" + ("1" if not mismatch else "0"))
if mismatch:
    print(json.dumps({"restore_mismatch": mismatch}, ensure_ascii=False))
    raise SystemExit(1)
PY
  exit "$code"
}

trap restore EXIT INT TERM
curl -fsS "$BASE/api/playback/core" > "$BEFORE"
TRACK="$(python3 - "$BEFORE" <<'PY'
import json, sys
s = json.load(open(sys.argv[1], encoding="utf-8"))["state"]
print((s.get("queue") or [""])[0])
PY
)"
TARGET="$(python3 - "$BEFORE" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["state"].get("target_id", "local"))
PY
)"
[ -n "$TRACK" ] || { echo "empty queue" >&2; exit 2; }
printf '{"target_id":"%s","track_id":"%s","position":0}\n' "$TARGET" "$TRACK" \
  | curl -fsS -X POST -H 'Content-Type: application/json' --data-binary @- "$BASE/api/playback/load" >> "$LOG"
sleep 2
PID="$(pgrep -f '/target/bin/mpd --no-daemon' | head -n 1)"
[ -n "$PID" ] || { echo "MPD PID not found" >&2; exit 2; }
printf 'killed_pid=%s\n' "$PID" >> "$LOG"
kill -TERM "$PID"
for sample in $(seq 1 30); do
  sleep 1
  STATUS="$(curl -fsS "$BASE/api/playback/core")"
  printf 'sample=%s %s\n' "$sample" "$STATUS" >> "$LOG"
  printf '%s' "$STATUS" | grep -q '"transport": "PLAYING"' && break
done
printf '%s\n' "$STATUS" > "$AFTER"
python3 - "$AFTER" >> "$LOG" <<'PY'
import json, sys
s = json.load(open(sys.argv[1], encoding="utf-8"))["state"]
print("restart_verified=" + ("1" if s.get("transport") == "PLAYING" else "0"))
PY

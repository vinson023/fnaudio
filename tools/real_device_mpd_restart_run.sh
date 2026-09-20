#!/bin/sh
# Controlled MPD restart acceptance with exact PlaybackCore session recovery.
set -eu

BASE="${FNAUDIO_BASE_URL:-http://127.0.0.1:53199}"
LOG="${1:-/vol1/1000/fnaudio-mpd-restart.log}"
BEFORE="${LOG}.before.json"
AFTER="${LOG}.after.json"

api() {
  curl -fsS -H 'X-Fnaudio-Internal: 1' "$@"
}

restore() {
  code=$?
  trap - EXIT INT TERM
  [ -f "$BEFORE" ] || exit "$code"
  python3 - "$BEFORE" <<'PY' > "${BEFORE}.restore.jsonl"
import json, sys
s = json.load(open(sys.argv[1], encoding="utf-8"))["state"]
shuffle = s.get("shuffle") if isinstance(s.get("shuffle"), bool) else False
print(json.dumps({"target_id": s.get("target_id", "local")}))
print(json.dumps({"queue": s.get("queue", []), "current_id": s.get("current"), "repeat": s.get("repeat", "off"), "shuffle": shuffle}))
print(json.dumps({"action": "play" if s.get("transport") == "PLAYING" else "stop", "target_id": s.get("target_id", "local")}))
PY
  sed -n '1p' "${BEFORE}.restore.jsonl" | api -X POST -H 'Content-Type: application/json' --data-binary @- "$BASE/api/playback/target" >/dev/null || code=1
  sed -n '2p' "${BEFORE}.restore.jsonl" | api -X POST -H 'Content-Type: application/json' --data-binary @- "$BASE/api/playback/queue" >/dev/null || code=1
  sed -n '3p' "${BEFORE}.restore.jsonl" | api -X POST -H 'Content-Type: application/json' --data-binary @- "$BASE/api/playback/control" >/dev/null || code=1
  rm -f "${BEFORE}.restore.jsonl"
  api "$BASE/api/playback/core" > "$AFTER" || code=1
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
api "$BASE/api/playback/core" > "$BEFORE"
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
python3 - "$TARGET" "$TRACK" <<'PY' \
  | api -X POST -H 'Content-Type: application/json' --data-binary @- "$BASE/api/playback/load" >> "$LOG"
import json, sys
print(json.dumps({"target_id": sys.argv[1], "track_id": sys.argv[2], "position": 0}, separators=(",", ":")))
PY
printf '\n' >> "$LOG"
sleep 8
api "$BASE/api/mpd/status" > "${LOG}.playing-before-kill.json"
PID="$(pgrep -f '/target/bin/mpd --no-daemon' | head -n 1)"
[ -n "$PID" ] || { echo "MPD PID not found" >&2; exit 2; }
printf 'killed_pid=%s\n' "$PID" >> "$LOG"
kill -TERM "$PID"
for sample in $(seq 1 30); do
  sleep 1
  STATUS="$(api "$BASE/api/playback/core" 2>/dev/null || true)"
  if [ -z "$STATUS" ]; then
    printf 'sample=%s api_unavailable=1\n' "$sample" >> "$LOG"
    continue
  fi
  printf 'sample=%s %s\n' "$sample" "$STATUS" >> "$LOG"
  NEW_PID="$(pgrep -f '/target/bin/mpd --no-daemon' | head -n 1 || true)"
  if [ -n "$NEW_PID" ] && [ "$NEW_PID" != "$PID" ] && printf '%s' "$STATUS" | grep -q '"transport": "PLAYING"'; then
    break
  fi
done
[ -n "$STATUS" ] || { echo "PlaybackCore did not recover within the sample window" >&2; exit 1; }
printf '%s\n' "$STATUS" > "$AFTER"
api "$BASE/api/mpd/status" > "${LOG}.playing-after-restart.json"
python3 - "$AFTER" "${LOG}.playing-before-kill.json" "${LOG}.playing-after-restart.json" "$TRACK" "$PID" "$NEW_PID" >> "$LOG" <<'PY'
import json, sys
core = json.load(open(sys.argv[1], encoding="utf-8"))["state"]
before = json.load(open(sys.argv[2], encoding="utf-8"))
after = json.load(open(sys.argv[3], encoding="utf-8"))
track, old_pid, new_pid = sys.argv[4:]

def position(payload):
    value = ((payload.get("status") or {}).get("position") or {}).get("rel_seconds")
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return 0.0
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return result if result == result and result not in (float("inf"), float("-inf")) else 0.0

before_position = position(before)
after_position = position(after)
checks = {
    "pid_changed": bool(new_pid and new_pid != old_pid),
    "transport_playing": core.get("transport") == "PLAYING",
    "track_preserved": core.get("current") == track,
    "position_preserved": after_position >= max(0.0, before_position - 2.0),
}
print("old_pid=%s new_pid=%s" % (old_pid, new_pid))
print("before_position=%.3f after_position=%.3f" % (before_position, after_position))
for key, value in checks.items():
    print("%s=%s" % (key, "1" if value else "0"))
print("restart_verified=" + ("1" if all(checks.values()) else "0"))
if not all(checks.values()):
    raise SystemExit(1)
PY

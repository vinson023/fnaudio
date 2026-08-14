#!/bin/sh
# Run a bounded real-DAC queue test and restore the exact pre-test session.
#
# Required: FNAUDIO_TEST_QUEUE='["track-id", ...]'
# Optional: FNAUDIO_DAC_TARGET=mpd:usb:... (otherwise keep the selected MPD target)
set -eu

BASE="${FNAUDIO_BASE_URL:-http://127.0.0.1:18080}"
LOG="${1:-/vol1/1000/fnaudio-dac-queue-run.log}"
SNAPSHOT="${LOG}.before.json"
AFTER="${LOG}.after.json"
TEST_QUEUE="${FNAUDIO_TEST_QUEUE:?Set FNAUDIO_TEST_QUEUE to a JSON array of valid track IDs}"
TARGET="${FNAUDIO_DAC_TARGET:-}"
SAMPLES="${FNAUDIO_QUEUE_SAMPLES:-360}"
INTERVAL="${FNAUDIO_QUEUE_INTERVAL:-5}"

restore() {
  code=$?
  trap - EXIT INT TERM
  if [ -f "$SNAPSHOT" ]; then
    printf 'restore_started=%s\n' "$(date -Iseconds)" >> "$LOG"
    if [ -n "$TARGET" ]; then
      printf '{"action":"stop","target_id":"%s"}\n' "$TARGET" \
        | curl -sS -X POST -H 'Content-Type: application/json' --data-binary @- "$BASE/api/playback/control" >> "$LOG" || true
    else
      printf '{"action":"stop"}\n' \
        | curl -sS -X POST -H 'Content-Type: application/json' --data-binary @- "$BASE/api/playback/control" >> "$LOG" || true
    fi
    printf '\n' >> "$LOG"
    python3 - "$SNAPSHOT" <<'PY' | curl -sS -X POST -H 'Content-Type: application/json' --data-binary @- "$BASE/api/playback/queue" >> "$LOG" || true
import json
import sys
snapshot = json.load(open(sys.argv[1], encoding="utf-8"))
state = snapshot["state"]
print(json.dumps({
    "queue": state["queue"],
    "current_id": state.get("current"),
    "repeat": state.get("repeat", "off"),
    "shuffle": bool(state.get("shuffle")),
}, separators=(",", ":")))
PY
    printf '\n' >> "$LOG"
    curl -fsS "$BASE/api/playback/core" > "$AFTER" || true
    if python3 - "$SNAPSHOT" "$AFTER" >> "$LOG" 2>&1 <<'PY'
import json
import sys
before = json.load(open(sys.argv[1], encoding="utf-8"))["state"]
after = json.load(open(sys.argv[2], encoding="utf-8"))["state"]
fields = ("queue", "current", "repeat", "shuffle", "transport")
mismatch = {key: {"before": before.get(key), "after": after.get(key)} for key in fields if before.get(key) != after.get(key)}
print("restore_verified=" + ("1" if not mismatch else "0"))
if mismatch:
    print(json.dumps({"restore_mismatch": mismatch}, ensure_ascii=False))
    raise SystemExit(1)
PY
    then
      printf 'restore_finished=%s\n' "$(date -Iseconds)" >> "$LOG"
    else
      printf 'restore_failed=%s\n' "$(date -Iseconds)" >> "$LOG"
      code=1
    fi
  fi
  exit "$code"
}

trap restore EXIT INT TERM
printf 'started=%s samples=%s interval_seconds=%s\n' "$(date -Iseconds)" "$SAMPLES" "$INTERVAL" > "$LOG"
curl -fsS "$BASE/api/playback/core" > "$SNAPSHOT"

CURRENT="$(python3 - "$SNAPSHOT" "$TEST_QUEUE" <<'PY'
import json
import sys
snapshot = json.load(open(sys.argv[1], encoding="utf-8"))
queue = json.loads(sys.argv[2])
if not isinstance(queue, list) or not queue or not all(isinstance(item, str) and item for item in queue):
    raise SystemExit("FNAUDIO_TEST_QUEUE must be a non-empty JSON array of track IDs")
if not isinstance(snapshot.get("state", {}).get("queue"), list):
    raise SystemExit("playback core response has no restorable queue")
print(queue[0])
PY
)"

EXPECTED_COUNT="$(python3 - "$TEST_QUEUE" <<'PY'
import json
import sys
queue = json.loads(sys.argv[1])
print(len(queue))
PY
)"

printf '{"queue":%s,"current_id":"%s","repeat":"off","shuffle":false}\n' "$TEST_QUEUE" "$CURRENT" \
  | curl -fsS -X POST -H 'Content-Type: application/json' --data-binary @- "$BASE/api/playback/queue" >> "$LOG"
printf '\n' >> "$LOG"
if [ -n "$TARGET" ]; then
  printf '{"target_id":"%s","track_id":"%s","position":0}\n' "$TARGET" "$CURRENT"
else
  printf '{"track_id":"%s","position":0}\n' "$CURRENT"
fi | curl -fsS -X POST -H 'Content-Type: application/json' --data-binary @- "$BASE/api/playback/load" >> "$LOG"
printf '\n' >> "$LOG"

last=""
changes=0
seen_positions=""
printf 'expected_queue_length=%s expected_track_ids=%s\n' "$EXPECTED_COUNT" "$TEST_QUEUE" >> "$LOG"
for sample in $(seq 1 "$SAMPLES"); do
  status="$(curl -fsS "$BASE/api/mpd/status")"
  printf 'sample=%s at=%s %s\n' "$sample" "$(date -Iseconds)" "$status" >> "$LOG"
  current="$(printf '%s' "$status" | sed -n 's/.*"songid"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
  if [ -n "$current" ] && [ "$current" != "$last" ]; then
    changes=$((changes + 1))
    printf 'song_change=%s id=%s at=%s\n' "$changes" "$current" "$(date -Iseconds)" >> "$LOG"
    last="$current"
  fi
  current_position="$(printf '%s' "$status" | sed -n 's/.*"song"[[:space:]]*:[[:space:]]*"\([0-9][0-9]*\)".*/\1/p')"
  case "$current_position" in
    ''|*[!0-9]*) ;;
    *)
      if [ "$current_position" -lt "$EXPECTED_COUNT" ]; then
        case ",$seen_positions," in
          *",$current_position,"*) ;;
          *) seen_positions="${seen_positions}${current_position}," ;;
        esac
      fi
      ;;
  esac
  if [ -n "$current_position" ]; then
    observed_count="$(printf '%s' "$seen_positions" | tr -cd ',' | wc -c | tr -d ' ')"
    if [ "$observed_count" -eq "$EXPECTED_COUNT" ]; then
      printf 'queue_positions_complete_at_sample=%s\n' "$sample" >> "$LOG"
      break
    fi
  fi
  sleep "$INTERVAL"
done
printf 'finished_sampling=%s song_changes=%s\n' "$(date -Iseconds)" "$changes" >> "$LOG"

# MPD's raw `song` is the zero-based queue position.  Checking every expected
# position proves the complete caller-provided queue was actually traversed;
# a merely nonzero song-change count is not sufficient acceptance evidence.
if python3 - "$LOG" "$EXPECTED_COUNT" >> "$LOG" 2>&1 <<'PY'
import json
import re
import sys

log_path, expected_text = sys.argv[1:]
expected = int(expected_text)
sample_re = re.compile(r"^sample=(\d+) at=[^ ]+ (.+)$")
positions = []
for line in open(log_path, encoding="utf-8", errors="replace"):
    match = sample_re.match(line.rstrip("\n"))
    if not match:
        continue
    try:
        payload = json.loads(match.group(2))
        song = ((payload.get("status") or {}).get("raw") or {}).get("song")
        if song is not None:
            positions.append(int(song))
    except (TypeError, ValueError, json.JSONDecodeError):
        continue

seen = sorted(set(positions))
missing = [position for position in range(expected) if position not in seen]
print("observed_queue_positions=" + json.dumps(seen, separators=(",", ":")))
print("queue_traversal_verified=" + ("1" if not missing else "0"))
if missing:
    print("missing_queue_positions=" + json.dumps(missing, separators=(",", ":")))
    raise SystemExit(1)
PY
then
  printf 'queue_traversal_finished=%s expected_queue_length=%s\n' "$(date -Iseconds)" "$EXPECTED_COUNT" >> "$LOG"
else
  printf 'queue_traversal_failed=%s expected_queue_length=%s\n' "$(date -Iseconds)" "$EXPECTED_COUNT" >> "$LOG"
  exit 1
fi

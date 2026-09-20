#!/bin/sh
# Temporarily add the bounded DAC fixture directory, run the queue acceptance
# test, and restore the exact library-root configuration on every exit path.
set -eu

BASE="${FNAUDIO_BASE_URL:-http://127.0.0.1:53199}"
FIXTURE_ROOT="${FNAUDIO_FIXTURE_ROOT:-/vol1/1000/fnaudio/real-queue-fixtures}"
RUNNER="${FNAUDIO_DAC_RUNNER:-/vol1/1000/fnaudio/real_device_dac_queue_run-0.2.14.sh}"
STABILITY_RUNNER="${FNAUDIO_STABILITY_RUNNER:-/vol1/1000/fnaudio/real_device_pcm_stability_run-0.2.15.py}"
MODE="${FNAUDIO_FIXTURE_MODE:-queue}"
LOG="${1:-/vol1/1000/fnaudio/external-dac-queue-0.2.14-$(date +%Y%m%d-%H%M%S).log}"
TRACK_IDS="${FNAUDIO_TEST_QUEUE:-[\"a24453d3689e8407\",\"b57d176f6c19b828\"]}"
ORIGINAL_STATUS="${LOG}.library-before.json"
RESTORED_STATUS="${LOG}.library-after.json"

api() {
  curl -fsS -H 'X-Fnaudio-Internal: 1' "$@"
}

post_library_paths() {
  python3 - "$1" <<'PY' | api -X POST -H 'Content-Type: application/json' --data-binary @- "$BASE/api/config/library"
import json
import sys

print(json.dumps({"library_path": sys.argv[1]}, ensure_ascii=False, separators=(",", ":")))
PY
}

wait_for_scan() {
  limit="${1:-180}"
  count=0
  while [ "$count" -lt "$limit" ]; do
    status="$(api "$BASE/api/library/status")"
    running="$(python3 -c 'import json,sys; print("1" if json.load(sys.stdin).get("scanning") else "0")' <<EOF
$status
EOF
)"
    [ "$running" = "0" ] && return 0
    count=$((count + 1))
    sleep 1
  done
  return 1
}

restore_library() {
  code=$?
  trap - EXIT INT TERM
  original_paths="$(python3 - "$ORIGINAL_STATUS" <<'PY'
import json
import sys

status = json.load(open(sys.argv[1], encoding="utf-8"))
print("\n".join(str(path) for path in status.get("library_paths", []) if str(path).strip()))
PY
)"
  if [ -n "$original_paths" ]; then
    post_library_paths "$original_paths" >> "$LOG" 2>&1 || code=1
    printf '\n' >> "$LOG"
    api "$BASE/api/library/status?refresh=1" >/dev/null || code=1
    wait_for_scan 300 || code=1
    api "$BASE/api/library/status" > "$RESTORED_STATUS" || code=1
    if python3 - "$ORIGINAL_STATUS" "$RESTORED_STATUS" >> "$LOG" 2>&1 <<'PY'
import json
import sys

before = json.load(open(sys.argv[1], encoding="utf-8"))
after = json.load(open(sys.argv[2], encoding="utf-8"))
expected = before.get("library_paths", [])
actual = after.get("library_paths", [])
print("library_restore_verified=" + ("1" if actual == expected else "0"))
if actual != expected:
    print(json.dumps({"expected": expected, "actual": actual}, ensure_ascii=False))
    raise SystemExit(1)
PY
    then :; else code=1; fi
  else
    printf 'library_restore_verified=0 reason=no_original_paths\n' >> "$LOG"
    code=1
  fi
  exit "$code"
}

api "$BASE/api/library/status" > "$ORIGINAL_STATUS"
trap restore_library EXIT INT TERM

combined_paths="$(python3 - "$ORIGINAL_STATUS" "$FIXTURE_ROOT" <<'PY'
import json
import sys

status = json.load(open(sys.argv[1], encoding="utf-8"))
paths = [str(path) for path in status.get("library_paths", []) if str(path).strip()]
fixture = sys.argv[2]
if fixture not in paths:
    paths.append(fixture)
print("\n".join(paths))
PY
)"
post_library_paths "$combined_paths" >> "$LOG"
printf '\n' >> "$LOG"
api "$BASE/api/library/status?refresh=1" >/dev/null
wait_for_scan 300

count="$(api "$BASE/api/library/items?ids=$(printf '%s' "$TRACK_IDS" | tr -d '[]\" ' | tr ',' ',')" \
  | python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("items", [])))')"
[ "$count" -eq 2 ] || {
  printf 'fixture_index_verified=0 indexed_count=%s\n' "$count" >> "$LOG"
  exit 1
}
printf 'fixture_index_verified=1 indexed_count=%s\n' "$count" >> "$LOG"

case "$MODE" in
  queue)
    FNAUDIO_TEST_QUEUE="$TRACK_IDS" \
    FNAUDIO_DAC_TARGET="${FNAUDIO_DAC_TARGET:-}" \
    FNAUDIO_QUEUE_SAMPLES="${FNAUDIO_QUEUE_SAMPLES:-12}" \
    FNAUDIO_QUEUE_INTERVAL="${FNAUDIO_QUEUE_INTERVAL:-1}" \
    FNAUDIO_BASE_URL="$BASE" \
    sh "$RUNNER" "$LOG"
    ;;
  stability)
    python3 "$STABILITY_RUNNER" \
      --base "$BASE" \
      --target "${FNAUDIO_DAC_TARGET:?Set FNAUDIO_DAC_TARGET for stability mode}" \
      --samples "${FNAUDIO_STABILITY_SAMPLES:-30}" \
      --interval "${FNAUDIO_STABILITY_INTERVAL:-1}" \
      --output "${LOG}.report.json" | tee -a "$LOG"
    ;;
  *)
    echo "Unknown FNAUDIO_FIXTURE_MODE: $MODE" >&2
    exit 2
    ;;
esac

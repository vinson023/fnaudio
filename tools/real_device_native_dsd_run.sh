#!/bin/sh
# Verify the known DSF and DFF library fixtures through the selected native
# DSD MPD target. Each bounded queue run restores the pre-test session.
set -eu

RUNNER="${FNAUDIO_DAC_RUNNER:-/vol1/1000/fnaudio/real_device_dac_queue_run-0.2.14.sh}"
TARGET="${FNAUDIO_DAC_TARGET:?Set FNAUDIO_DAC_TARGET to the native DSD MPD target}"
OUTPUT_DIR="${1:-/vol1/1000/fnaudio}"

verify_log() {
  python3 - "$1" "$2" <<'PY'
import json
import re
import sys

path, label = sys.argv[1:]
sample = None
for line in open(path, encoding="utf-8", errors="replace"):
    match = re.match(r"^sample=\d+ at=[^ ]+ (.+)$", line.rstrip("\n"))
    if match:
        sample = json.loads(match.group(1))
        break
if sample is None:
    raise SystemExit(f"{label}: no MPD status sample")
stream = ((sample.get("status") or {}).get("stream") or {})
expected = {
    "format": "dsd64:2",
    "dsd": True,
    "bitperfect_candidate": True,
}
actual = {key: stream.get(key) for key in expected}
passed = actual == expected
print(json.dumps({
    "fixture": label,
    "native_dsd_verified": passed,
    "stream": actual,
}, ensure_ascii=False, separators=(",", ":")))
if not passed:
    raise SystemExit(f"{label}: native DSD stream mismatch")
PY
}

run_fixture() {
  label="$1"
  track_id="$2"
  log="$OUTPUT_DIR/external-${label}-native-0.2.14.log"
  queue="$(python3 - "$track_id" <<'PY'
import json
import sys
print(json.dumps([sys.argv[1]], separators=(",", ":")))
PY
)"
  FNAUDIO_TEST_QUEUE="$queue" \
  FNAUDIO_DAC_TARGET="$TARGET" \
  FNAUDIO_QUEUE_SAMPLES=3 \
  FNAUDIO_QUEUE_INTERVAL=1 \
  sh "$RUNNER" "$log"
  verify_log "$log" "$label"
}

run_fixture dsf 80562025babebf1f
run_fixture dff 4d158238e962b112

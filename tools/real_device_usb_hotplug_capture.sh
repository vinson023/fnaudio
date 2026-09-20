#!/bin/sh
# Capture an operator-performed physical USB DAC unplug/replug test.
# This script is deliberately read-only with respect to sysfs: it never calls
# unbind/bind and therefore cannot be mistaken for real hot-plug evidence.
set -eu

LOG="${1:-/vol1/1000/fnaudio-usb-hotplug-0.1.205.log}"
BASE="${FNAUDIO_BASE_URL:-http://127.0.0.1:53199}"
SAMPLES="${FNAUDIO_HOTPLUG_SAMPLES:-180}"
INTERVAL="${FNAUDIO_HOTPLUG_INTERVAL:-2}"

api() {
  curl -fsS -H 'X-Fnaudio-Internal: 1' "$@"
}

printf 'started=%s samples=%s interval_seconds=%s\n' "$(date -Iseconds)" "$SAMPLES" "$INTERVAL" > "$LOG"
printf 'instruction=Physically unplug the USB DAC, wait for absence to be recorded, then reconnect it. Do not use sysfs unbind/bind.\n' >> "$LOG"

for sample in $(seq 1 "$SAMPLES"); do
  printf 'sample=%s at=%s\n' "$sample" "$(date -Iseconds)" >> "$LOG"
  printf 'cards=' >> "$LOG"
  tr '\n' '|' </proc/asound/cards 2>/dev/null >> "$LOG" || true
  printf '\nstatus=' >> "$LOG"
  api --max-time 3 "$BASE/api/mpd/status" | base64 -w0 >> "$LOG" || true
  printf '\n' >> "$LOG"
  sleep "$INTERVAL"
done

printf 'finished=%s\n' "$(date -Iseconds)" >> "$LOG"

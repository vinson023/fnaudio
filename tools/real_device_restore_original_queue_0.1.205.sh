#!/bin/sh
set -eu

BASE="${BASE:-http://127.0.0.1:18080}"
DAC="${DAC:-mpd:usb:0644:804a:00160000386ca1d14e45282720120016:dev0}"
LOG="${1:-/vol1/1000/fnaudio-short-queue-recovery-0.1.205.log}"

ORIGINAL_QUEUE='["6d6e5ed0a8c0cf70","676735c3075e949f","3074ec5101f0c8b0","da316cf2d8649c32","df5702643ae3c3a5","b2feef28c42d7070","a42a74e5232023fb","302d829ea32146e3","3d76165d1d64c720","38323e37bdbf9269","656543c542d57326","5b95adee70bc7585","3ff16dc11d2c2450","15db0d446f9655a6","bb81c1f83bd6dfbe","07437485ae9441fd","17dd6b1148a6bf37","f019d3578e9831b5","992b2e65afc28859","df394c51eb4378d6"]'

printf 'started=%s\n' "$(date -Iseconds)" > "$LOG"
python3 - "$DAC" <<'PY' \
  | curl -sS -X POST -H 'Content-Type: application/json' --data-binary @- "$BASE/api/playback/control" >> "$LOG"
import json, sys
print(json.dumps({"action": "stop", "target_id": sys.argv[1]}, separators=(",", ":")))
PY
printf '\n' >> "$LOG"
python3 - "$ORIGINAL_QUEUE" <<'PY' \
  | curl -sS -X POST -H 'Content-Type: application/json' --data-binary @- "$BASE/api/playback/queue" >> "$LOG"
import json, sys
queue = json.loads(sys.argv[1])
print(json.dumps({"queue": queue, "current_id": "df394c51eb4378d6", "repeat": "off", "shuffle": False}, separators=(",", ":")))
PY
printf '\npost_restore_status=%s ' "$(date -Iseconds)" >> "$LOG"
curl -sS "$BASE/api/mpd/status" >> "$LOG"
printf '\nfinished=%s\n' "$(date -Iseconds)" >> "$LOG"

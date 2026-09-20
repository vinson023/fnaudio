#!/bin/sh
set -eu

PID="${1:-110676}"
LOG="${2:-/vol1/1000/fnaudio-short-queue-0.1.205.log}"
BASE="${FNAUDIO_BASE_URL:-http://127.0.0.1:53199}"
DAC="mpd:usb:0644:804a:00160000386ca1d14e45282720120016:dev0"

# Do not overlap the long-run test with another queue mutation.
while kill -0 "$PID" 2>/dev/null; do sleep 30; done

SHORT_QUEUE='["5b95adee70bc7585","656543c542d57326","c1c0b160545cf226","a173b3031b0d1cca","650ad4b34963819a","15626b2345ab49a0","da316cf2d8649c32","4dd125898119f893","b63204c4ec7df257","09ce0073854cc143","77828777fd92ba99","de135a0dc2a0e6fd","7948dcf655570e91","dac3e652c36e753f","7b242ffcd1c50ef6","b6aed4ec841e8ab0","8e8111bb1607c1de","1ce985f90acb6259","051e909ff402f9ce","ba4c457aafa18bcf"]'
ORIGINAL_QUEUE='["6d6e5ed0a8c0cf70","676735c3075e949f","3074ec5101f0c8b0","da316cf2d8649c32","df5702643ae3c3a5","b2feef28c42d7070","a42a74e5232023fb","302d829ea32146e3","3d76165d1d64c720","38323e37bdbf9269","656543c542d57326","5b95adee70bc7585","3ff16dc11d2c2450","15db0d446f9655a6","bb81c1f83bd6dfbe","07437485ae9441fd","17dd6b1148a6bf37","f019d3578e9831b5","992b2e65afc28859","df394c51eb4378d6"]'

printf 'started=%s\n' "$(date -Iseconds)" > "$LOG"
python3 - "$SHORT_QUEUE" <<'PY' \
  | curl -sS -X POST -H 'Content-Type: application/json' --data-binary @- "$BASE/api/playback/queue" >> "$LOG"
import json, sys
queue = json.loads(sys.argv[1])
print(json.dumps({"queue": queue, "current_id": queue[0], "repeat": "off", "shuffle": False}, separators=(",", ":")))
PY
printf '\n' >> "$LOG"
python3 - "$DAC" <<'PY' \
  | curl -sS -X POST -H 'Content-Type: application/json' --data-binary @- "$BASE/api/playback/load" >> "$LOG"
import json, sys
print(json.dumps({"target_id": sys.argv[1], "track_id": "5b95adee70bc7585", "position": 0}, separators=(",", ":")))
PY
printf '\n' >> "$LOG"

last=""
changes=0
# The selected 20 tracks total about 36m 28s.  Keep a bounded 50-minute
# window, but finish early as soon as every queue item has been observed.
for sample in $(seq 1 600); do
  status="$(curl -s "$BASE/api/mpd/status")"
  printf 'sample=%s at=%s %s\n' "$sample" "$(date -Iseconds)" "$status" >> "$LOG"
  # MPD exposes the active queue index as raw.songid; use it as the
  # cross-song transition signal even when the API omits a track UUID.
  current="$(printf '%s' "$status" | sed -n 's/.*"songid"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
  if [ -n "$current" ] && [ "$current" != "$last" ]; then
    changes=$((changes + 1))
    printf 'song_change=%s id=%s at=%s\n' "$changes" "$current" "$(date -Iseconds)" >> "$LOG"
    last="$current"
    if [ "$changes" -ge 20 ]; then
      printf 'all_queue_items_observed=1 at=%s\n' "$(date -Iseconds)" >> "$LOG"
      break
    fi
  fi
  sleep 5
done

python3 - "$DAC" <<'PY' \
  | curl -sS -X POST -H 'Content-Type: application/json' --data-binary @- "$BASE/api/playback/control" >> "$LOG"
import json, sys
print(json.dumps({"action": "stop", "target_id": sys.argv[1]}, separators=(",", ":")))
PY
printf '\n' >> "$LOG"
python3 - "$ORIGINAL_QUEUE" <<'PY' \
  | curl -sS -X POST -H 'Content-Type: application/json' --data-binary @- "$BASE/api/playback/queue" >> "$LOG"
import json, sys
print(json.dumps({"queue": json.loads(sys.argv[1]), "current_id": "df394c51eb4378d6", "repeat": "off", "shuffle": False}, separators=(",", ":")))
PY
printf '\nfinished=%s changes=%s\n' "$(date -Iseconds)" "$changes" >> "$LOG"
sleep 2
printf 'post_restore_status=%s ' "$(date -Iseconds)" >> "$LOG"
curl -sS "$BASE/api/mpd/status" >> "$LOG"
printf '\n' >> "$LOG"

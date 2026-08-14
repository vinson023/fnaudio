#!/usr/bin/env python3
"""Summarize fnAudio real-device MPD test logs without third-party packages.

Supports the base64-encoded 30-second long-run log and the raw JSON short-queue
log.  Exit status is non-zero if no valid status sample can be read.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path
from typing import Any


SAMPLE = re.compile(r"^sample=(\d+) at=([^ ]+) (.+)$")


def decode_status(payload: str) -> dict[str, Any] | None:
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(base64.b64decode(payload, validate=True))
    except (ValueError, json.JSONDecodeError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    args = parser.parse_args()

    samples: list[dict[str, Any]] = []
    for line in args.log.read_text(encoding="utf-8", errors="replace").splitlines():
        match = SAMPLE.match(line)
        if not match:
            continue
        status = decode_status(match.group(3))
        if not isinstance(status, dict):
            continue
        raw = ((status.get("status") or {}).get("raw") or {})
        idle = status.get("idle") or {}
        samples.append(
            {
                "sample": int(match.group(1)),
                "at": match.group(2),
                "songid": raw.get("songid"),
                "song": raw.get("song"),
                "state": raw.get("state"),
                "queue_length": raw.get("playlistlength"),
                "underrun": (idle.get("underrun") or {}).get("count", 0),
                "fault": (idle.get("fault") or {}).get("state"),
            }
        )

    if not samples:
        print("No valid MPD status samples found.", file=sys.stderr)
        return 2

    songids = [str(item["songid"]) for item in samples if item["songid"] is not None]
    changes = sum(1 for before, after in zip(songids, songids[1:]) if after != before)
    underruns = [int(item["underrun"] or 0) for item in samples]
    summary = {
        "samples": len(samples),
        "first_at": samples[0]["at"],
        "last_at": samples[-1]["at"],
        "queue_lengths": sorted({str(item["queue_length"]) for item in samples}),
        "states": sorted({str(item["state"]) for item in samples}),
        "fault_states": sorted({str(item["fault"]) for item in samples}),
        "distinct_songids": list(dict.fromkeys(songids)),
        "song_changes": changes,
        "max_underrun": max(underruns),
        "last": samples[-1],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

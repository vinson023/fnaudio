#!/usr/bin/env python3
"""Run a bounded repeat-all PCM stability gate and restore the prior session."""

import argparse
import json
import time
import urllib.request


def safe_int(value, default=0):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return default
    try:
        number = int(value, 10) if isinstance(value, str) else int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if 0 <= number <= 2**63 - 1 else default


def safe_float(value, default=0.0):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if number == number and number not in (float("inf"), float("-inf")) else default


def safe_bool(value, default=False):
    return value if isinstance(value, bool) else default


def request(base, path, payload=None):
    data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {"X-Fnaudio-Internal": "1"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def restore(base, before):
    state = before["state"]
    target = state.get("target_id") or "local"
    request(base, "/api/playback/control", {"action": "stop", "target_id": target})
    request(base, "/api/playback/queue", {
        "queue": state.get("queue") or [],
        "current_id": state.get("current"),
        "repeat": state.get("repeat", "off"),
        "shuffle": safe_bool(state.get("shuffle")),
    })
    request(base, "/api/playback/target", {"target_id": target})
    request(base, "/api/playback/control", {"action": "stop", "target_id": target})
    after = request(base, "/api/playback/core")
    fields = ("target_id", "queue", "current", "repeat", "shuffle", "transport")
    mismatch = {
        key: {"before": state.get(key), "after": after["state"].get(key)}
        for key in fields if state.get(key) != after["state"].get(key)
    }
    return after, mismatch


def diagnostic_counts(mpd):
    idle = mpd.get("idle") or {}
    return {
        "underrun": safe_int((idle.get("underrun") or {}).get("count")),
        "playback_errors": safe_int((idle.get("playback_errors") or {}).get("count")),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:53199")
    parser.add_argument("--target", required=True)
    parser.add_argument("--first", default="a24453d3689e8407")
    parser.add_argument("--second", default="b57d176f6c19b828")
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    base = args.base.rstrip("/")
    before = request(base, "/api/playback/core")
    if before["state"].get("transport") != "STOPPED":
        raise SystemExit("stability gate requires a stopped pre-test session")
    initial_mpd = request(base, "/api/mpd/status")
    report = {
        "started_at": time.time(),
        "target_id": args.target,
        "samples": [],
        "before": {
            "queue_length": len(before["state"].get("queue") or []),
            "current": before["state"].get("current"),
            "repeat": before["state"].get("repeat"),
            "shuffle": before["state"].get("shuffle"),
            "transport": before["state"].get("transport"),
        },
        "diagnostics_before": diagnostic_counts(initial_mpd),
    }
    failure = None
    try:
        request(base, "/api/playback/queue", {
            "queue": [args.first, args.second],
            "current_id": args.first,
            "repeat": "all",
            "shuffle": False,
        })
        loaded = request(base, "/api/playback/load", {
            "target_id": args.target,
            "track_id": args.first,
            "position": 0,
        })
        if not loaded.get("ok"):
            raise RuntimeError("load failed: " + json.dumps(loaded, ensure_ascii=False))
        last_song = None
        transitions = 0
        for index in range(max(1, args.samples)):
            time.sleep(max(0.1, args.interval))
            mpd = request(base, "/api/mpd/status")
            status = mpd.get("status") or {}
            raw = status.get("raw") or {}
            song = int(raw.get("song")) if str(raw.get("song", "")).isdigit() else -1
            if song >= 0 and song != last_song:
                transitions += 1
                last_song = song
            report["samples"].append({
                "index": index + 1,
                "state": str(raw.get("state") or ""),
                "song": song,
                "position": safe_float((status.get("position") or {}).get("rel_seconds")),
                "sample_rate": safe_int((status.get("stream") or {}).get("sample_rate")),
            })
        final_mpd = request(base, "/api/mpd/status")
        before_counts = report["diagnostics_before"]
        after_counts = diagnostic_counts(final_mpd)
        states = [sample["state"] for sample in report["samples"]]
        positions = sorted({sample["song"] for sample in report["samples"] if sample["song"] >= 0})
        checks = {
            "all_samples_playing": bool(states) and all(state == "play" for state in states),
            "both_queue_positions_seen": positions == [0, 1],
            "multiple_transitions": transitions >= 4,
            "no_new_underrun": after_counts["underrun"] == before_counts["underrun"],
            "no_new_playback_error": after_counts["playback_errors"] == before_counts["playback_errors"],
        }
        report.update({
            "diagnostics_after": after_counts,
            "observed_queue_positions": positions,
            "transitions": transitions,
            "checks": checks,
            "stability_verified": all(checks.values()),
        })
        if not report["stability_verified"]:
            raise RuntimeError("stability checks failed: " + json.dumps(checks, ensure_ascii=False))
    except Exception as exc:
        failure = str(exc)
        report["stability_verified"] = False
        report["error"] = failure
    finally:
        try:
            after, mismatch = restore(base, before)
            report["restore_verified"] = not mismatch
            report["restore_mismatch"] = mismatch
            report["after"] = {
                "queue_length": len(after["state"].get("queue") or []),
                "current": after["state"].get("current"),
                "repeat": after["state"].get("repeat"),
                "shuffle": after["state"].get("shuffle"),
                "transport": after["state"].get("transport"),
            }
        except Exception as exc:
            report["restore_verified"] = False
            report["restore_error"] = str(exc)
        report["finished_at"] = time.time()
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    print(json.dumps({
        "stability_verified": report.get("stability_verified", False),
        "restore_verified": report.get("restore_verified", False),
        "transitions": report.get("transitions", 0),
        "observed_queue_positions": report.get("observed_queue_positions", []),
        "checks": report.get("checks", {}),
        "error": report.get("error", ""),
    }, ensure_ascii=False, separators=(",", ":")))
    if failure or not report.get("restore_verified"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

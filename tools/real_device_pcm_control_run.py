#!/usr/bin/env python3
"""Bounded real-MPD control matrix with exact stopped-session restoration."""

import argparse
import json
import time
import urllib.parse
import urllib.request


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


def wait_for(base, predicate, label, timeout=20):
    deadline = time.monotonic() + timeout
    latest = {}
    while time.monotonic() < deadline:
        latest = request(base, "/api/mpd/status")
        if predicate(latest):
            return latest
        time.sleep(0.25)
    raise RuntimeError(f"timed out waiting for {label}: {json.dumps(latest, ensure_ascii=False)}")


def raw_status(payload):
    return ((payload.get("status") or {}).get("raw") or {})


def stream(payload):
    return ((payload.get("status") or {}).get("stream") or {})


def position(payload):
    return safe_float(((payload.get("status") or {}).get("position") or {}).get("rel_seconds"))


def current_id(base):
    return str((request(base, "/api/playback/core").get("state") or {}).get("current") or "")


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:53199")
    parser.add_argument("--target", required=True)
    parser.add_argument("--first", default="60580483a8134770")
    parser.add_argument("--second", default="676735c3075e949f")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    base = args.base.rstrip("/")
    report = {"started_at": time.time(), "target_id": args.target, "steps": []}
    before = request(base, "/api/playback/core")
    report["before"] = {
        key: before["state"].get(key)
        for key in ("current", "repeat", "shuffle", "transport", "target_id")
    }
    report["before"]["queue_length"] = len(before["state"].get("queue") or [])
    if before["state"].get("transport") != "STOPPED":
        raise SystemExit("PCM control gate requires a stopped pre-test session")
    failure = None
    try:
        request(base, "/api/playback/queue", {
            "queue": [args.first, args.second],
            "current_id": args.first,
            "repeat": "off",
            "shuffle": False,
        })
        loaded = request(base, "/api/playback/load", {
            "target_id": args.target,
            "track_id": args.first,
            "position": 0,
        })
        if not loaded.get("ok"):
            raise RuntimeError("initial load failed: " + json.dumps(loaded, ensure_ascii=False))
        first_play = wait_for(
            base,
            lambda value: raw_status(value).get("state") == "play" and stream(value).get("sample_rate") == 44100,
            "44.1 kHz playback",
        )
        report["steps"].append({"action": "load", "transport": "PLAYING", "sample_rate": stream(first_play).get("sample_rate")})

        request(base, "/api/playback/control", {"action": "pause", "target_id": args.target})
        paused = wait_for(base, lambda value: raw_status(value).get("state") == "pause", "pause")
        report["steps"].append({"action": "pause", "transport": "PAUSED", "position": position(paused)})

        request(base, "/api/playback/control", {"action": "play", "target_id": args.target})
        resumed = wait_for(base, lambda value: raw_status(value).get("state") == "play", "resume")
        report["steps"].append({"action": "play", "transport": "PLAYING", "position": position(resumed)})

        request(base, "/api/playback/control", {"action": "seek", "position": 30, "target_id": args.target})
        sought = wait_for(base, lambda value: raw_status(value).get("state") == "play" and 28 <= position(value) <= 34, "30 second seek")
        report["steps"].append({"action": "seek", "position": position(sought)})

        request(base, "/api/playback/control", {"action": "next", "target_id": args.target})
        second = wait_for(
            base,
            lambda value: current_id(base) == args.second and raw_status(value).get("state") == "play" and stream(value).get("sample_rate") == 96000,
            "next track at 96 kHz",
        )
        report["steps"].append({"action": "next", "current": args.second, "sample_rate": stream(second).get("sample_rate")})

        request(base, "/api/playback/control", {"action": "previous", "target_id": args.target})
        previous = wait_for(
            base,
            lambda value: current_id(base) == args.first and raw_status(value).get("state") == "play" and stream(value).get("sample_rate") == 44100,
            "previous track at 44.1 kHz",
        )
        report["steps"].append({"action": "previous", "current": args.first, "sample_rate": stream(previous).get("sample_rate")})

        request(base, "/api/playback/control", {"action": "stop", "target_id": args.target})
        stopped = wait_for(base, lambda value: raw_status(value).get("state") == "stop", "stop")
        report["steps"].append({"action": "stop", "transport": "STOPPED", "position": position(stopped)})
        report["control_matrix_verified"] = True
    except Exception as exc:
        failure = str(exc)
        report["control_matrix_verified"] = False
        report["error"] = failure
    finally:
        try:
            after, mismatch = restore(base, before)
            report["restore_verified"] = not mismatch
            report["restore_mismatch"] = mismatch
            report["after"] = {
                key: after["state"].get(key)
                for key in ("current", "repeat", "shuffle", "transport", "target_id")
            }
            report["after"]["queue_length"] = len(after["state"].get("queue") or [])
        except Exception as exc:
            report["restore_verified"] = False
            report["restore_error"] = str(exc)
        report["finished_at"] = time.time()
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    print(json.dumps({
        "control_matrix_verified": report.get("control_matrix_verified", False),
        "restore_verified": report.get("restore_verified", False),
        "steps": report.get("steps", []),
        "error": report.get("error", ""),
    }, ensure_ascii=False, separators=(",", ":")))
    if failure or not report.get("restore_verified"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

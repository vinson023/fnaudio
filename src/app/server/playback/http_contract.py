"""Stable HTTP payload rules shared by the playback API and legacy aliases."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, MutableMapping


LEGACY_PLAYBACK_SUCCESSORS = {
    "/api/player/state": "/api/playback/queue",
    "/api/upnp/push": "/api/playback/load",
    "/api/dac/push": "/api/playback/load",
    "/api/upnp/control": "/api/playback/control",
    "/api/dac/control": "/api/playback/control",
}


def target_kind(target_id: Any) -> str:
    value = str(target_id or "local")
    if value in ("", "local", "browser"):
        return "browser"
    if value.startswith("mpd:"):
        return "mpd"
    if value.startswith("dac:"):
        return "alsa"
    return "dlna_push"


def normalize_target_id(target_id: Any) -> str:
    value = str(target_id or "local")
    return "local" if target_kind(value) == "browser" else value


def normalize_queue_tracks(source: Any) -> List[Dict[str, Any]]:
    tracks = []
    for item in source if isinstance(source, list) else []:
        if isinstance(item, dict):
            track_id = str(item.get("id") or item.get("track_id") or "").strip()
            if track_id:
                tracks.append(item)
            continue
        track_id = str(item or "").strip()
        if track_id:
            tracks.append({"id": track_id})
    return tracks


def legacy_load_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "target_id": payload.get("device_id"),
        "track_id": payload.get("track_id"),
        "position": payload.get("position", 0),
    }


def legacy_control_payload(payload: Mapping[str, Any], default_target_id: Any = None) -> Dict[str, Any]:
    return {
        "target_id": payload.get("device_id") or default_target_id,
        "action": payload.get("action"),
        "position": payload.get("position"),
        "track_id": payload.get("track_id"),
    }


def apply_legacy_player_state(payload, legacy_state: MutableMapping[str, Any], playback_core):
    legacy_state.update(
        {
            "queue": payload.get("queue", legacy_state.get("queue", [])),
            "current": payload.get("current", legacy_state.get("current")),
            "playing": payload.get("playing", legacy_state.get("playing", False)),
        }
    )
    core_state = playback_core.sync_frontend(payload)
    return {"ok": True, "state": dict(legacy_state), "core": core_state.to_dict()}


def legacy_response_headers(path: str) -> Dict[str, str]:
    successor = LEGACY_PLAYBACK_SUCCESSORS.get(str(path or ""))
    if not successor:
        return {}
    return {
        "Deprecation": "true",
        "Link": '<%s>; rel="successor-version"' % successor,
        "X-fnAudio-Deprecated-API": str(path),
    }


def playback_event_payload(core: Mapping[str, Any], requested_target: Any = "") -> Dict[str, Any]:
    active_target = str(core.get("target_id") or "local")
    if active_target == "browser":
        active_target = "local"
    try:
        state_version = int(core.get("state_version") or 0)
    except (TypeError, ValueError):
        state_version = 0
    try:
        position = max(0.0, float(core.get("position") or 0))
    except (TypeError, ValueError):
        position = 0.0
    try:
        duration = max(0.0, float(core.get("duration") or 0))
    except (TypeError, ValueError):
        duration = 0.0
    return {
        "type": "playback",
        "state_version": state_version,
        "requested_target": str(requested_target or ""),
        "target_id": active_target,
        "target_kind": str(core.get("target_kind") or "browser"),
        "core": core,
        "transport": {"state": str(core.get("transport") or "STOPPED").upper()},
        "position": {
            "rel_seconds": position,
            "duration_seconds": duration,
        },
    }

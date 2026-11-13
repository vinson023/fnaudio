"""Stable HTTP payload rules shared by the playback API and legacy aliases."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, MutableMapping

from playback_event_presentation import playback_event_payload
from metadata_track_id_policy import normalize_track_id


LEGACY_PLAYBACK_SUCCESSORS = {
    "/api/player/state": "/api/playback/queue",
    "/api/upnp/push": "/api/playback/load",
    "/api/dac/push": "/api/playback/load",
    "/api/upnp/control": "/api/playback/control",
    "/api/dac/control": "/api/playback/control",
}


def target_kind(target_id: Any) -> str:
    value = _target_text(target_id)
    if value in ("", "local", "browser"):
        return "browser"
    if value == "mpd" or value.startswith("mpd:"):
        return "mpd"
    if value == "alsa" or value.startswith("dac:"):
        return "alsa"
    return "dlna_push"


def normalize_target_id(target_id: Any) -> str:
    value = _target_text(target_id)
    return "local" if target_kind(value) == "browser" else value


def _target_text(value: Any) -> str:
    """Keep target identities textual and bounded without coercing objects."""
    if not isinstance(value, str):
        return "local"
    value = value.strip()
    return value[:128] or "local"


def normalize_queue_tracks(source: Any) -> List[Dict[str, Any]]:
    tracks = []
    for item in source if isinstance(source, list) else []:
        if isinstance(item, dict):
            track_id = normalize_track_id(item.get("id"))
            if not track_id:
                track_id = normalize_track_id(item.get("track_id"))
            if track_id:
                tracks.append(item)
            continue
        track_id = normalize_track_id(item)
        if track_id:
            tracks.append({"id": track_id})
    return tracks


def control_track_alignment(
    kind: str,
    action: Any,
    requested_track_id: Any,
    current_track_id: Any,
    queue_ids: Any,
) -> str:
    """Return the track a relative transport command has to advance from.

    A browser target is driven by whichever client is looking at it: that client
    owns the audio element, so it is the only authority on what is audible. The
    core's own position can drift away from it -- a client-side CUE tail walk
    advances without a round trip, a second window loads its own track, an
    earlier cast left the core somewhere else -- and a "previous" pressed after
    that drift stepped from the drifted index and came back with a song the
    listener was never next to. The client already sends its playing track, so
    the core adopts it before stepping when it is a queue member.
    """
    if kind != "browser":
        return ""
    requested_action = action.strip().lower() if isinstance(action, str) else ""
    if requested_action not in ("next", "previous"):
        return ""
    requested = normalize_track_id(requested_track_id)
    if not requested or requested == normalize_track_id(current_track_id):
        return ""
    if not isinstance(queue_ids, (list, tuple)):
        return ""
    members = {normalize_track_id(item) for item in queue_ids}
    return requested if requested in members else ""


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
    playing = payload.get("playing", legacy_state.get("playing", False))
    if not isinstance(playing, bool):
        playing = legacy_state.get("playing", False)
        if not isinstance(playing, bool):
            playing = False
    legacy_state.update(
        {
            "queue": payload.get("queue", legacy_state.get("queue", [])),
            "current": payload.get("current", legacy_state.get("current")),
            "playing": playing,
        }
    )
    core_state = playback_core.sync_frontend(payload)
    return {"ok": True, "state": dict(legacy_state), "core": core_state.to_dict()}


def legacy_response_headers(path: Any) -> Dict[str, str]:
    if not isinstance(path, str):
        return {}
    successor = LEGACY_PLAYBACK_SUCCESSORS.get(path)
    if not successor:
        return {}
    return {
        "Deprecation": "true",
        "Link": '<%s>; rel="successor-version"' % successor,
        "X-fnAudio-Deprecated-API": path,
    }

"""Pure policy helpers for queue update requests.

The HTTP handler still owns persistence and native-output side effects.  This
module only turns an untrusted queue payload into bounded, predictable values
and states when an MPD queue mirror is worth attempting.
"""

from __future__ import annotations

from typing import Any, Mapping

from playback.http_contract import normalize_queue_tracks, normalize_track_id


def queue_request(payload: Any) -> dict[str, Any]:
    """Extract the queue update fields without dereferencing bad payloads."""
    source = payload if isinstance(payload, Mapping) else {}
    current = source.get("current_id")
    if not normalize_track_id(current):
        current = source.get("current")
    if isinstance(current, Mapping):
        current = current.get("id")
    return {
        "tracks": normalize_queue_tracks(source.get("queue")),
        "current_id": normalize_track_id(current),
        "repeat": source.get("repeat"),
        "shuffle": source.get("shuffle"),
    }


def should_sync_mpd_queue(target_kind: Any, tracks: Any) -> bool:
    """Return whether a non-empty logical queue should mirror into MPD."""
    return (
        isinstance(target_kind, str)
        and target_kind == "mpd"
        and isinstance(tracks, (list, tuple))
        and len(tracks) > 0
    )


__all__ = ["queue_request", "should_sync_mpd_queue"]

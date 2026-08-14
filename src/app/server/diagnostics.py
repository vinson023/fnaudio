"""Privacy-safe support snapshot construction."""
from __future__ import annotations

from observability import redact
from version import APP_VERSION


def _int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def support_snapshot(*, server_name, mpd, scan_state, metadata, transcode, dlna_available, renderer_count, metrics, playback):
    """Return bounded diagnostics without credentials, paths or queue metadata."""
    fault = (mpd or {}).get("fault") or {}
    playback_errors = (mpd or {}).get("playback_errors") or {}
    current = (playback or {}).get("current") or {}
    return redact({
        "schema": 1,
        "server": {"name": str(server_name or "fnAudio"), "version": APP_VERSION},
        "playback": {
            "target_id": str((playback or {}).get("target_id") or ""),
            "transport": str((playback or {}).get("transport") or ""),
            "queue_length": _int((playback or {}).get("queue_length")),
            "has_current_track": bool(current),
        },
        "components": {
            "mpd": {
                "running": bool((mpd or {}).get("running")),
                "fault": str(fault.get("state") or ""),
                "error_category": str(playback_errors.get("last_category") or ""),
            },
            "library": {
                "scanning": bool((scan_state or {}).get("running")),
                "cancelled": bool((scan_state or {}).get("cancelled")),
                "timed_out": bool((scan_state or {}).get("timed_out")),
                "errors": len((scan_state or {}).get("errors") or []),
            },
            "metadata": {
                "running": bool((metadata or {}).get("running")),
                "pending": _int((metadata or {}).get("pending")),
                "dropped": _int((metadata or {}).get("dropped")),
            },
            "transcode": {"active": _int((transcode or {}).get("active")), "queued": _int((transcode or {}).get("queued"))},
            "dlna": {"running": bool(dlna_available), "renderers": _int(renderer_count)},
        },
        "metrics": metrics or {},
    })

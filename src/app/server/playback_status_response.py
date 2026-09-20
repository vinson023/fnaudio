"""Pure response-shape composition for playback status routes."""

from __future__ import annotations

from collections.abc import Mapping

from playback_status_presentation import present_position, present_transport


def _mapping(value):
    return value if isinstance(value, Mapping) else {}


def _state_version(core):
    """Clamp the authoritative counter so a poll can be ordered against SSE.

    Both projections share one monotonic version, so a polling frame may carry
    it unchanged instead of being discarded as "no version".  Booleans, text
    that is not a number and out-of-range values fall back to zero, which the
    client reads as "an older server" and handles through its own fallback.
    """
    try:
        raw = _mapping(core).get("state_version")
        if isinstance(raw, bool):
            raise ValueError("boolean state version")
        return max(0, min(int(raw or 0), 2**31 - 1))
    except (TypeError, ValueError, OverflowError):
        return 0


def browser_response(core):
    return {"kind": "browser", "status": _mapping(core)}


def alsa_response(status, core, cue_segment=False):
    payload = _mapping(status)
    return {
        "kind": "alsa",
        **payload,
        "core": _mapping(core),
        "state_version": _state_version(core),
        "cue_segment": cue_segment is True,
    }


def mpd_error_response(message, core):
    return {
        "kind": "mpd",
        "error": message if isinstance(message, str) and message else "MPD is not running",
        "core": _mapping(core),
    }


def mpd_response(probe, status, core, cue_segment=False):
    return {
        "kind": "mpd",
        "transport": present_transport(_mapping(status).get("transport")),
        "position": present_position(_mapping(status).get("position")),
        "mpd": _mapping(probe),
        "core": _mapping(core),
        "state_version": _state_version(core),
        "cue_segment": cue_segment is True,
    }


def upnp_response(transport, position, core, cue_segment=False):
    return {
        "kind": "upnp",
        "transport": present_transport(transport),
        "position": present_position(position),
        "core": _mapping(core),
        "state_version": _state_version(core),
        "cue_segment": cue_segment is True,
    }


def device_not_found_response():
    return {"error": "device not found"}


def backend_error_response(error):
    return {"error": error if isinstance(error, str) else "backend status unavailable"}

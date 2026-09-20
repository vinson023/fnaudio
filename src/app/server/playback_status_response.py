"""Pure response-shape composition for playback status routes."""

from __future__ import annotations

from collections.abc import Mapping

from playback_status_presentation import present_position, present_transport


def _mapping(value):
    return value if isinstance(value, Mapping) else {}


def browser_response(core):
    return {"kind": "browser", "status": _mapping(core)}


def alsa_response(status, core):
    payload = _mapping(status)
    return {"kind": "alsa", **payload, "core": _mapping(core)}


def mpd_error_response(message, core):
    return {
        "kind": "mpd",
        "error": message if isinstance(message, str) and message else "MPD is not running",
        "core": _mapping(core),
    }


def mpd_response(probe, status, core):
    return {
        "kind": "mpd",
        "transport": present_transport(_mapping(status).get("transport")),
        "position": present_position(_mapping(status).get("position")),
        "mpd": _mapping(probe),
        "core": _mapping(core),
    }


def upnp_response(transport, position, core):
    return {
        "kind": "upnp",
        "transport": present_transport(transport),
        "position": present_position(position),
        "core": _mapping(core),
    }


def device_not_found_response():
    return {"error": "device not found"}


def backend_error_response(error):
    return {"error": error if isinstance(error, str) else "backend status unavailable"}

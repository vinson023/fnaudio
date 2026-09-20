"""Pure policy helpers for external DLNA/UPnP renderer monitoring."""

from __future__ import annotations

import math
import urllib.parse

from metadata_track_id_policy import normalize_track_id


MAX_RENDERER_TRACK_URI_CHARS = 8192


def _finite_float(value, default=0.0):
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else default
    return default


def _finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def track_id_from_renderer_uri(uri):
    """Return the fnAudio queue ID embedded in an advertised UPnP media URI."""
    if not isinstance(uri, str) or len(uri) > MAX_RENDERER_TRACK_URI_CHARS:
        return ""
    try:
        path = urllib.parse.urlparse(uri).path
        marker = "/upnp/media/"
        if marker not in path:
            return ""
        return normalize_track_id(urllib.parse.unquote(path.split(marker, 1)[1].split("/", 1)[0]))
    except (TypeError, ValueError):
        return ""


def stop_is_suppressed(guard, target_id, transport, now):
    """Keep a user-requested stop from being mistaken for auto-advance."""
    if not isinstance(guard, dict) or not isinstance(target_id, str) or not isinstance(transport, str):
        return False
    observed_at = _finite_number(now)
    deadline = _finite_number(guard.get("suppress_stop_until"))
    return bool(observed_at is not None and deadline is not None and (
        transport.upper() in ("STOPPED", "NO_MEDIA_PRESENT")
        and guard.get("target_id") == target_id
        and observed_at <= deadline
    ))


def stalled_track_expired(current_track_id, backend_track_id, transport,
                          reported_position, reported_duration,
                          track_started_at, expected_duration, now):
    """Detect a renderer that stays PLAYING without position or stop events."""
    if not isinstance(current_track_id, str) or not current_track_id or backend_track_id != current_track_id:
        return False
    expected = _finite_float(expected_duration)
    if expected < 5.0 or not isinstance(transport, str) or transport.upper() not in ("PLAYING", "TRANSITIONING"):
        return False
    if _finite_float(reported_position) > 0.0 or _finite_float(reported_duration) > 0.0:
        return False
    started = _finite_float(track_started_at)
    return started > 0.0 and _finite_float(now) >= started + expected + 2.0

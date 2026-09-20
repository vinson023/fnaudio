"""Pure, bounded projection for the persisted/current playback session."""

from collections.abc import Mapping

MAX_SESSION_QUEUE_ITEMS = 50000
MAX_SESSION_TEXT = 256


def _text(value):
    if not isinstance(value, str):
        return ""
    try:
        return value.strip()[:MAX_SESSION_TEXT]
    except Exception:
        return ""


def project_playback_session(core, *, safe_float):
    """Return a stable session mapping without exposing mutable core state."""
    source = core if isinstance(core, Mapping) else {}
    try:
        queue = source.get("queue")
    except Exception:
        queue = ()
    if not isinstance(queue, (list, tuple)):
        queue = ()
    try:
        queue = list(queue[:MAX_SESSION_QUEUE_ITEMS])
    except Exception:
        queue = []
    try:
        current = _text(source.get("current"))
        target = _text(source.get("target_id"))
        kind = _text(source.get("target_kind"))
        repeat = _text(source.get("repeat")) or "off"
        playing = source.get("playing") is True
        shuffle = source.get("shuffle") is True
        raw_position = source.get("position")
        position = safe_float(0 if raw_position is None else raw_position)
    except Exception:
        current, target, kind, repeat = "", "", "", "off"
        playing, shuffle, position = False, False, 0.0
    return {
        "queue": queue,
        "current_id": current,
        "position": position,
        "playing": playing,
        "repeat": repeat,
        "shuffle": shuffle,
        "target_id": "local" if target in ("", "browser") else target,
        "target_kind": kind or "browser",
    }


__all__ = ["MAX_SESSION_QUEUE_ITEMS", "MAX_SESSION_TEXT", "project_playback_session"]

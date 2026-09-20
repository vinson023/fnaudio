"""Pure, bounded projection helpers for playback status responses.

Backends are allowed to return richer diagnostic mappings, but HTTP callers
only need stable transport/position objects.  These helpers keep that
projection out of the request handler and make malformed backend payloads
safe to render.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict, Iterable, Tuple


MAX_KEYS = 32
MAX_TEXT = 512


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _pairs(value: Mapping[str, Any]) -> Iterable[Tuple[Any, Any]]:
    """Yield at most MAX_KEYS pairs without unbounded materialization."""
    try:
        iterator = iter(value.items())
    except Exception:
        return ()

    def bounded():
        count = 0
        while count < MAX_KEYS:
            try:
                yield next(iterator)
            except StopIteration:
                return
            except Exception:
                return
            count += 1

    return bounded()


def _text(value: Any, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str):
        return ""
    try:
        return value[:limit]
    except Exception:
        return ""


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if number == number and number not in (float("inf"), float("-inf")) else default


def present_transport(value: Any) -> Dict[str, Any]:
    """Return a bounded transport mapping with a safe state field."""
    source = _mapping(value)
    result: Dict[str, Any] = {}
    for pair in _pairs(source):
        try:
            key, item = pair
        except Exception:
            continue
        if not isinstance(key, str) or len(key) > 80:
            continue
        if isinstance(item, str):
            result[key] = _text(item)
        elif isinstance(item, (bool, int, float)) or item is None:
            result[key] = item
    state = _text(result.get("state") or source.get("transport")) or "STOPPED"
    result["state"] = state.upper()[:64]
    return result


def present_position(value: Any) -> Dict[str, Any]:
    """Return stable non-negative position/duration fields.

    Additional scalar backend fields are retained for compatibility with
    existing clients (for example UPnP time strings).
    """
    source = _mapping(value)
    result: Dict[str, Any] = {}
    for pair in _pairs(source):
        try:
            key, item = pair
        except Exception:
            continue
        if not isinstance(key, str) or len(key) > 80:
            continue
        if isinstance(item, str):
            result[key] = _text(item)
        elif isinstance(item, (bool, int, float)) or item is None:
            result[key] = item
    result["rel_seconds"] = max(0.0, _number(source.get("rel_seconds"), 0.0))
    result["duration_seconds"] = max(0.0, _number(source.get("duration_seconds"), 0.0))
    return result

"""Pure input normalization for playback status requests."""

from __future__ import annotations

def target_id_from_query(payload_or_query):
    """Return one stable target id from query mappings or plain payloads."""
    if not hasattr(payload_or_query, "get"):
        return "local"
    try:
        raw = payload_or_query.get("target_id") or payload_or_query.get("device_id") or ["local"]
    except Exception:
        return "local"
    value = raw[0] if isinstance(raw, (list, tuple)) and raw else raw
    if isinstance(value, str):
        return value.strip()[:128] or "local"
    return "local"


MAX_COMMAND_ID_CHARS = 128


def command_id_from_payload(payload):
    """Return a bounded retry token without coercing arbitrary objects."""
    if not hasattr(payload, "get"):
        return ""
    try:
        value = payload.get("command_id")
    except Exception:
        return ""
    if not isinstance(value, str):
        return ""
    return value.strip()[:MAX_COMMAND_ID_CHARS]

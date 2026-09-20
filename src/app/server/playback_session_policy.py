"""Pure normalization for cross-client playback session identity."""

MAX_SESSION_EPOCH = 2**31 - 1


def _counter(value):
    if isinstance(value, bool):
        return 0
    try:
        value = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(0, min(value, MAX_SESSION_EPOCH))


def session_identity(payload):
    """Return bounded generation/engine epoch supplied by a client."""
    if not hasattr(payload, "get"):
        return {"generation": 0, "engine_epoch": 0}
    try:
        return {
            "generation": _counter(payload.get("generation")),
            "engine_epoch": _counter(payload.get("engine_epoch")),
        }
    except Exception:
        return {"generation": 0, "engine_epoch": 0}


def ticket_matches(ticket, identity):
    if not isinstance(ticket, dict) or not isinstance(identity, dict):
        return False
    return (
        _counter(ticket.get("generation")) == _counter(identity.get("generation"))
        and _counter(ticket.get("engine_epoch")) == _counter(identity.get("engine_epoch"))
    )


def identity_is_stale(candidate, current):
    """Return whether a non-legacy identity is older than the active one."""
    candidate = session_identity(candidate)
    current = session_identity(current)
    if not (candidate["generation"] or candidate["engine_epoch"]):
        return False
    if not (current["generation"] or current["engine_epoch"]):
        return False
    return candidate["generation"] < current["generation"] or (
        candidate["generation"] == current["generation"]
        and candidate["engine_epoch"] < current["engine_epoch"]
    )


__all__ = ["MAX_SESSION_EPOCH", "identity_is_stale", "session_identity", "ticket_matches"]

"""Pure, bounded projections for metadata job queue state."""

from typing import Any, Mapping, Tuple

DEFAULT_QUEUE_LIMIT = 20000
MIN_QUEUE_LIMIT = 1
MAX_QUEUE_LIMIT = 200000
MAX_QUEUE_COUNTER = 10**12


def saturating_counter(value: Any, amount: Any = 1) -> int:
    """Increment a long-running queue counter without allowing unbounded growth."""
    try:
        current = 0 if isinstance(value, bool) else max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        current = 0
    try:
        delta = 0 if isinstance(amount, bool) else max(0, int(amount))
    except (TypeError, ValueError, OverflowError):
        delta = 0
    return min(MAX_QUEUE_COUNTER, current + delta)


def _bounded_limit(value: Any, default: int = DEFAULT_QUEUE_LIMIT) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(MIN_QUEUE_LIMIT, min(MAX_QUEUE_LIMIT, number))


def project_queue_state(state: Any, configured_limit: Any = DEFAULT_QUEUE_LIMIT) -> Tuple[int, int]:
    """Return safe (limit, pending) values without coercing arbitrary objects."""
    limit = _bounded_limit(configured_limit)
    if isinstance(state, Mapping):
        try:
            raw_limit = state.get("limit")
            raw_pending = state.get("pending")
        except Exception:
            raw_limit = raw_pending = None
        if raw_limit not in (None, ""):
            limit = _bounded_limit(raw_limit, limit)
        if isinstance(raw_pending, bool) or not isinstance(raw_pending, (int, str)):
            pending = 0
        else:
            try:
                pending = int(raw_pending)
            except (TypeError, ValueError, OverflowError):
                pending = 0
    else:
        pending = 0
    return limit, max(0, min(limit, pending))


__all__ = ["DEFAULT_QUEUE_LIMIT", "MIN_QUEUE_LIMIT", "MAX_QUEUE_LIMIT", "MAX_QUEUE_COUNTER", "project_queue_state", "saturating_counter"]

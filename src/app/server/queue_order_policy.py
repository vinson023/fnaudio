"""Pure queue navigation rules, shared by the core and the browser client.

R587: shuffle is an *order*, not a coin flip.  The queue a client sends is
already in play order -- turning shuffle on reorders it once and remembers the
original order -- so "next" and "previous" are plain index arithmetic.  The
browser implements the same table in ``queue_order_policy.js``; one test runs
both against one table instead of trusting two hand-written copies to agree.

Keeping the rule here also removes the old ``random.choice`` from
``PlaybackCore.next_track``: with two different randomisers (client and server)
the same button produced three different behaviours depending on which client
owned the transport.
"""

from __future__ import annotations

from typing import Any, Optional

MAX_ITEMS = 50000
REPEAT_MODES = ("off", "all", "one")


def _index(value: Any) -> int:
    """Return a usable cursor; anything else means "nothing is playing"."""
    if isinstance(value, bool) or not isinstance(value, int):
        return -1
    return value


def _length(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return min(value, MAX_ITEMS)


def _repeat(value: Any) -> str:
    return value if value in REPEAT_MODES else "off"


def next_index(index: Any, length: Any, repeat: Any = "off") -> int:
    """Return the row after ``index``, or -1 when the queue has nowhere to go."""
    size = _length(length)
    if size == 0:
        return -1
    current = _index(index)
    mode = _repeat(repeat)
    if mode == "one" and current >= 0:
        return current
    if current < size - 1:
        # No current row (-1) starts at the first row, like a fresh queue.
        return current + 1
    return 0 if mode == "all" else -1


def previous_index(index: Any, length: Any, repeat: Any = "off") -> int:
    """Return the row before ``index``, or -1 when the queue has nowhere to go."""
    size = _length(length)
    if size == 0:
        return -1
    current = _index(index)
    mode = _repeat(repeat)
    if mode == "one" and current >= 0:
        return current
    if current > 0:
        return current - 1
    return size - 1 if mode == "all" else -1


def normalize_repeat(value: Any) -> Optional[str]:
    """Return a repeat mode the core accepts, or None when it must not change."""
    return value if value in REPEAT_MODES else None


__all__ = [
    "MAX_ITEMS",
    "REPEAT_MODES",
    "next_index",
    "normalize_repeat",
    "previous_index",
]

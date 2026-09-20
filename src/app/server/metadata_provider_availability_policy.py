"""Pure availability decisions for one metadata provider invocation."""

from __future__ import annotations

import math
from typing import Any


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def provider_is_available(cooldown_until: Any, deadline: Any, now: Any) -> bool:
    """Return whether a provider may run inside the current bounded job.

    A malformed monotonic timestamp fails closed.  The caller treats a false
    result as an incomplete provider search, never as evidence that a song is
    absent from an external catalog.
    """
    current = _finite_number(now)
    cooldown = _finite_number(cooldown_until)
    if current is None or cooldown is None or current < cooldown:
        return False
    if deadline is None:
        return True
    until = _finite_number(deadline)
    return until is not None and current < until


__all__ = ["provider_is_available"]

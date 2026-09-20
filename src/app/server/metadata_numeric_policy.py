"""Pure numeric projections for untrusted metadata provider fields."""

from __future__ import annotations

import math


MAX_CANDIDATE_INDEX = 1000000


def finite_confidence(value, default=0.0):
    """Accept JSON scalar confidence values, rejecting custom conversions."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return float(default)
    try:
        number = float(value or 0)
    except (TypeError, ValueError, OverflowError):
        return float(default)
    return number if math.isfinite(number) else float(default)


def bounded_epoch(value, default=0):
    """Project cache timestamps without allowing malformed rows to escape."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return int(default)
    try:
        number = int(float(value or 0))
    except (TypeError, ValueError, OverflowError):
        return int(default)
    return max(0, number)


def strict_nonnegative_int(value, default=None, maximum=MAX_CANDIDATE_INDEX):
    """Accept only an integer JSON value or an ASCII decimal string."""
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and value and value.isascii() and value.isdecimal():
        try:
            number = int(value, 10)
        except (TypeError, ValueError, OverflowError):
            return default
    else:
        return default
    if number < 0 or number > maximum:
        return default
    return number


__all__ = ["MAX_CANDIDATE_INDEX", "bounded_epoch", "finite_confidence", "strict_nonnegative_int"]

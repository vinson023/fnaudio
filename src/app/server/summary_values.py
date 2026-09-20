"""Small, side-effect-free normalizers for public status summaries.

Health and diagnostics are called on request paths.  They must not invoke
arbitrary ``__int__``/``__float__``/``__str__`` implementations supplied by a
malformed dependency payload just to format a counter.
"""

from __future__ import annotations

import math
import re


MAX_SUMMARY_COUNT = 2_147_483_647
_INTEGER_TEXT = re.compile(r"^[+-]?\d+$")


def nonnegative_int(value, default=0, maximum=MAX_SUMMARY_COUNT):
    """Return a bounded non-negative integer from ordinary numeric input."""
    if isinstance(default, bool) or not isinstance(default, (int, float)):
        default = 0
    elif isinstance(default, float) and not math.isfinite(default):
        default = 0
    if isinstance(maximum, bool) or not isinstance(maximum, (int, float)):
        maximum = MAX_SUMMARY_COUNT
    elif isinstance(maximum, float) and not math.isfinite(maximum):
        maximum = MAX_SUMMARY_COUNT
    try:
        maximum = max(0, int(maximum))
    except (OverflowError, ValueError, TypeError):
        maximum = MAX_SUMMARY_COUNT
    try:
        default = min(maximum, max(0, int(default)))
    except (OverflowError, ValueError, TypeError):
        default = 0
    if isinstance(value, bool):
        return default
    if isinstance(value, str):
        if not _INTEGER_TEXT.fullmatch(value.strip()):
            return max(0, int(default))
        try:
            value = int(value)
        except (OverflowError, ValueError):
            return max(0, int(default))
    elif not isinstance(value, (int, float)):
        return max(0, int(default))
    if isinstance(value, float) and not math.isfinite(value):
        return default
    return min(maximum, max(0, int(value)))


def bounded_text(value, default="", maximum=160):
    """Accept only text already supplied as text; never stringify objects."""
    if not isinstance(default, str):
        default = ""
    try:
        limit = max(0, int(maximum)) if not isinstance(maximum, bool) else 160
    except (OverflowError, ValueError, TypeError):
        limit = 160
    fallback = default[:limit]
    if not isinstance(value, str):
        return fallback
    return value[:limit] if value else fallback


def strict_bool(value, default=False):
    """Accept only an actual boolean from an untrusted status payload."""
    return value if isinstance(value, bool) else default


__all__ = ["MAX_SUMMARY_COUNT", "bounded_text", "nonnegative_int", "strict_bool"]

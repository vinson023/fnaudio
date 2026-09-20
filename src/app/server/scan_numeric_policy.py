"""Bounded numeric normalization used by scanning and sorting."""

import math
import re

MAX_SCAN_COUNTER = 2_147_483_647


def safe_float(value, default=0.0):
    if isinstance(value, str):
        text = value.strip()
        if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", text):
            return default
        try:
            value = float(text)
        except ValueError:
            return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if math.isfinite(number) else default


def safe_int(value, default=0):
    if isinstance(value, str):
        match = re.match(r"^\s*[+-]?\d+", value)
        if not match:
            return default
        try:
            return int(match.group(0))
        except (ValueError, OverflowError):
            return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not math.isfinite(number):
        return default
    return int(number)


def safe_counter(value, default=0, maximum=MAX_SCAN_COUNTER):
    """Project scan counters to a finite, non-negative bounded integer."""
    number = safe_int(value, default)
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 0:
        maximum = MAX_SCAN_COUNTER
    return max(0, min(maximum, number))

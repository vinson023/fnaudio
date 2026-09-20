"""Pure, bounded normalization for provider release-date values."""

from __future__ import annotations

import math
import time

MAX_RELEASE_DATE_TEXT = 256


def normalize_release_date(value):
    """Return an ISO-like date for epoch values without coercing objects."""
    numeric_input = False
    if isinstance(value, bool):
        return ""
    if isinstance(value, str):
        text = value.strip()[:MAX_RELEASE_DATE_TEXT]
        numeric_input = bool(text) and text.lstrip("+-").isdigit()
    elif isinstance(value, int):
        text = str(value)[:MAX_RELEASE_DATE_TEXT]
        numeric_input = True
    elif isinstance(value, float) and math.isfinite(value):
        text = str(value).strip()[:MAX_RELEASE_DATE_TEXT]
        numeric_input = True
    else:
        return ""
    try:
        timestamp = int(text)
        # A numeric provider value is an epoch only within a bounded range.
        # Do not echo arbitrarily large integers back into metadata rows.
        if abs(timestamp) > 10**14:
            return ""
        if timestamp > 100000000000:
            timestamp //= 1000
        if timestamp > 100000000:
            return time.strftime("%Y-%m-%d", time.localtime(timestamp))
    except (TypeError, ValueError, OverflowError, OSError):
        return "" if numeric_input else text
    return text


__all__ = ["MAX_RELEASE_DATE_TEXT", "normalize_release_date"]

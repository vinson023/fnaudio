"""Pure input/output policies for optional audio fingerprinting."""


def bounded_timeout(value) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return 120
    try:
        return max(1, min(300, int(value)))
    except (TypeError, ValueError, OverflowError):
        return 120


def bounded_duration(value) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return 0
    try:
        return max(0, min(86400, int(value)))
    except (TypeError, ValueError, OverflowError):
        return 0


__all__ = ["bounded_timeout", "bounded_duration"]

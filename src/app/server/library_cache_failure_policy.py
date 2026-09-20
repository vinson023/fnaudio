"""Pure bounds and projection rules for library-cache failure counters."""

from __future__ import annotations

from scan_numeric_policy import safe_counter

MAX_CACHE_FAILURES = 2_147_483_647
FAILURE_KINDS = ("load", "save")


def _read(source, key):
    try:
        return source.get(key, 0) if isinstance(source, dict) else 0
    except Exception:
        return 0


def increment_failure(counters, kind):
    """Return a bounded copy with one failure added for a known kind."""
    result = {name: safe_counter(_read(counters, name)) for name in FAILURE_KINDS}
    if kind in FAILURE_KINDS:
        result[kind] = min(MAX_CACHE_FAILURES, result[kind] + 1)
    return result


def project_failures(counters):
    """Project only the public load/save counters without coercion."""
    source = counters if isinstance(counters, dict) else {}
    return {name: safe_counter(_read(source, name)) for name in FAILURE_KINDS}


__all__ = ["FAILURE_KINDS", "MAX_CACHE_FAILURES", "increment_failure", "project_failures"]

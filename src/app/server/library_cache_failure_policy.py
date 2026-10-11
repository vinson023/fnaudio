"""Pure bounds and projection rules for library-cache failure counters."""

from __future__ import annotations

import re

from scan_numeric_policy import safe_counter

MAX_CACHE_FAILURES = 2_147_483_647
FAILURE_KINDS = ("load", "save")

# Ninety-eight identical "persistence failed" lines in a row told us nothing
# about *why* the index could not be written. One bounded, path-free line per
# kind is enough to name the exception without leaking library paths into the
# support log or growing it without limit.
MAX_FAILURE_DETAIL_CHARS = 180

# Two shapes only: a Windows drive path, or a POSIX/UNC path with at least two
# segments.  A lone "/O" inside a message is prose, not a leaked path, and the
# extra separator requirement keeps it intact.
_ABSOLUTE_PATH_RE = re.compile(
    r"(?:[A-Za-z]:[\\/][^\s'\"<>|]*|[\\/][^\s'\"<>|]*[\\/][^\s'\"<>|]*)"
)
_WHITESPACE_RE = re.compile(r"\s+")


def describe_failure(exc):
    """Reduce an exception to ``Class: message`` with paths collapsed.

    Accepts an exception instance, an exception class, or plain text, and is
    total: whatever comes in, the result is a short single-line string.
    """
    try:
        if isinstance(exc, BaseException):
            name = type(exc).__name__
            if getattr(type(exc), "__module__", "") == "sqlite3":
                name = "sqlite3." + name
            message = str(exc)
            text = "%s: %s" % (name, message) if message else name
        elif isinstance(exc, str):
            text = exc
        else:
            return ""
        text = _ABSOLUTE_PATH_RE.sub("<path>", text)
        text = _WHITESPACE_RE.sub(" ", text).strip()
        if len(text) > MAX_FAILURE_DETAIL_CHARS:
            text = text[: MAX_FAILURE_DETAIL_CHARS - 1].rstrip() + "\u2026"
        return text
    except Exception:
        return ""


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


__all__ = [
    "FAILURE_KINDS",
    "MAX_CACHE_FAILURES",
    "MAX_FAILURE_DETAIL_CHARS",
    "describe_failure",
    "increment_failure",
    "project_failures",
]

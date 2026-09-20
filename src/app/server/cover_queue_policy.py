"""Pure bounded identities for asynchronous cover-prewarm queues."""

from __future__ import annotations

from collections.abc import Mapping
import math


MAX_QUEUE_IDENTITY_CHARS = 4096


def _limit(value, fallback):
    """Normalize a caller-provided text limit without invoking custom casts."""
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int):
        return max(0, min(MAX_QUEUE_IDENTITY_CHARS, value))
    return fallback


def _text(value, limit=MAX_QUEUE_IDENTITY_CHARS):
    if not isinstance(value, str):
        return ""
    return value[:_limit(limit, MAX_QUEUE_IDENTITY_CHARS)]


def item_identity(item, prefer_path=False):
    """Return a stable media identity without coercing arbitrary objects.

    Interactive page requests historically deduplicated by track id first,
    while a scan-wide prewarm uses the path first so duplicate scanner ids do
    not collapse distinct files.  Keep that distinction explicit at the pure
    policy boundary instead of leaking it into queue construction.
    """
    if not isinstance(item, Mapping):
        return ""
    try:
        first = _text(item.get("path")) if prefer_path else _text(item.get("id"))
        second = _text(item.get("id")) if prefer_path else _text(item.get("path"))
        return first or second
    except (AttributeError, KeyError, TypeError):
        return ""


def queue_key(item, version, size, prefer_path=False):
    """Build a bounded FIFO/deduplication key for one cover request."""
    try:
        if isinstance(size, bool) or not isinstance(size, (int, float, str)):
            raise TypeError
        numeric = float(size)
        if not math.isfinite(numeric) or numeric != math.trunc(numeric):
            raise ValueError
        numeric_size = int(numeric)
    except (TypeError, ValueError, OverflowError):
        numeric_size = 0
    return item_identity(item, prefer_path), _text(version, 128), max(0, min(512, numeric_size))


__all__ = ["MAX_QUEUE_IDENTITY_CHARS", "item_identity", "queue_key"]

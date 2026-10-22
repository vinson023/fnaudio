"""Bounded primitive projections for third-party metadata values."""

from __future__ import annotations

import html
import re


_PROVIDER_HIGHLIGHT_TAG = re.compile(r"</?\s*em(?:\s[^>]*)?>", re.IGNORECASE)


def provider_text(value, limit=512):
    """Return bounded provider text, ignoring schema-drift objects."""
    if not isinstance(value, str):
        return ""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        limit = 512
    return value.replace("\x00", "").strip()[:limit]


def provider_display_text(value, limit=512):
    """Project provider display text after removing search-highlight markup."""
    text = provider_text(value, limit)
    if not text:
        return ""
    # Search endpoints such as Kugou return HTML ``<em>`` highlights in song
    # and artist fields. Decode escaped markup first, then remove only the
    # known highlight element so literal angle brackets in a title survive.
    text = html.unescape(text)
    return _PROVIDER_HIGHLIGHT_TAG.sub("", text).strip()[:limit]


def provider_int(value, default=0, minimum=None, maximum=None):
    """Project provider numeric fields without invoking hostile coercions."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return default
    try:
        number = int(float(value)) if isinstance(value, float) else int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if minimum is not None:
        number = max(int(minimum), number)
    if maximum is not None:
        number = min(int(maximum), number)
    return number


__all__ = ["provider_display_text", "provider_text", "provider_int"]

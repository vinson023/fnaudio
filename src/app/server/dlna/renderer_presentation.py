"""Bounded renderer URI/DIDL input and presentation policy."""

from __future__ import annotations

from xml.etree import ElementTree as ET
from .xml_policy import safe_fromstring


MAX_RENDERER_URI_CHARS = 8192
MAX_RENDERER_METADATA_CHARS = 256 * 1024
MAX_RENDERER_DISPLAY_CHARS = 1024


def _text(value, limit):
    return value[:limit] if isinstance(value, str) else ""


def normalize_renderer_media(uri, metadata=""):
    """Retain only bounded ordinary text before it enters Renderer state."""
    return _text(uri, MAX_RENDERER_URI_CHARS), _text(metadata, MAX_RENDERER_METADATA_CHARS)


def metadata_fields(metadata, uri):
    """Extract a small display projection from bounded DIDL without coercion."""
    safe_metadata, safe_uri = normalize_renderer_media(metadata, uri)
    title = ""
    artist = ""
    art_url = ""
    try:
        root = safe_fromstring(safe_metadata)
        for node in root.iter():
            tag = node.tag.split("}")[-1] if isinstance(node.tag, str) else ""
            value = _text(node.text, MAX_RENDERER_DISPLAY_CHARS).strip()
            if tag == "title" and not title:
                title = value
            elif tag in ("creator", "artist") and not artist:
                artist = value
            elif tag == "albumArtURI" and not art_url:
                art_url = value
    except (ET.ParseError, TypeError, ValueError):
        pass
    fallback = safe_uri.rsplit("/", 1)[-1].split("?", 1)[0] or "DLNA input"
    return title or fallback[:MAX_RENDERER_DISPLAY_CHARS], artist, art_url


__all__ = [
    "MAX_RENDERER_DISPLAY_CHARS",
    "MAX_RENDERER_METADATA_CHARS",
    "MAX_RENDERER_URI_CHARS",
    "metadata_fields",
    "normalize_renderer_media",
]

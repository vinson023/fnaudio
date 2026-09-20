from __future__ import annotations

import re
from typing import Union
from xml.etree import ElementTree as ET

MAX_DLNA_XML_PARSE_BYTES = 1024 * 1024
_UNSAFE_DECLARATION = re.compile(br"<!\s*(?:doctype|entity)\b", re.IGNORECASE)


def _declaration_scan_view(payload: bytes) -> bytes:
    """The bytes the declaration pattern is searched in.

    expat selects UTF-16 or UTF-32 from a BOM **or** from NUL padding, so a peer
    can send ``<\\x00!\\x00E\\x00N\\x00T\\x00I\\x00T\\x00Y`` and walk past a scan of the
    raw bytes while the parser still reads a DTD and expands internal entities.
    Dropping NUL bytes folds every one of those encodings back onto the ASCII
    pattern: ASCII markup is one non-zero byte per character in all of them.  The
    same removal un-splits a declaration padded with NULs inside an otherwise byte
    encoded document, and a payload without NULs is scanned unchanged.
    """
    return payload.replace(b"\x00", b"")


def safe_fromstring(raw: Union[bytes, bytearray, str], maximum: int = MAX_DLNA_XML_PARSE_BYTES):
    """Parse peer-provided XML without allowing DTD/entity expansion."""
    if isinstance(raw, str):
        payload = raw.encode("utf-8")
    elif isinstance(raw, (bytes, bytearray)):
        payload = bytes(raw)
    else:
        raise ValueError("DLNA XML must be text or bytes")
    if isinstance(maximum, bool) or not isinstance(maximum, int) or not 1 <= maximum <= MAX_DLNA_XML_PARSE_BYTES:
        raise ValueError("DLNA XML size limit is invalid")
    if len(payload) > maximum:
        raise ValueError("DLNA XML exceeds the parse size limit")
    if _UNSAFE_DECLARATION.search(_declaration_scan_view(payload)):
        raise ValueError("DLNA XML declarations are not allowed")
    return ET.fromstring(payload)


__all__ = ["MAX_DLNA_XML_PARSE_BYTES", "safe_fromstring"]

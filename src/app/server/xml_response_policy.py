"""Bounded XML response serialization for DLNA HTTP handlers."""

from __future__ import annotations

from typing import Any, Tuple


MAX_XML_RESPONSE_BYTES = 1024 * 1024
_ERROR = b'<?xml version="1.0" encoding="utf-8"?><error>response unavailable</error>'


def serialize_xml_response(body: Any, maximum: int = MAX_XML_RESPONSE_BYTES) -> Tuple[bytes, bool]:
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0:
        maximum = MAX_XML_RESPONSE_BYTES
    else:
        maximum = min(MAX_XML_RESPONSE_BYTES, maximum)
    if isinstance(body, bytes):
        encoded = body
    elif isinstance(body, str):
        try:
            encoded = body.encode("utf-8")
        except Exception:
            return _ERROR, False
    else:
        return _ERROR, False
    if len(encoded) > maximum:
        return _ERROR, False
    return encoded, True


__all__ = ["MAX_XML_RESPONSE_BYTES", "serialize_xml_response"]

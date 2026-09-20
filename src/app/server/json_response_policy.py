"""Bounded JSON response serialization for HTTP handlers."""

from __future__ import annotations

import json
from typing import Any, Tuple


MAX_JSON_RESPONSE_BYTES = 8 * 1024 * 1024


def serialize_json_response(payload: Any, maximum: int = MAX_JSON_RESPONSE_BYTES) -> Tuple[bytes, bool]:
    """Serialize a response and report whether it fits the byte budget.

    The handler can replace failures/oversized payloads with a fixed error
    response, keeping malformed state from escaping through the request loop.
    """
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0:
        maximum = MAX_JSON_RESPONSE_BYTES
    else:
        maximum = min(MAX_JSON_RESPONSE_BYTES, maximum)
    try:
        # Compact separators materially reduce repeated field overhead for
        # large library pages while preserving ordinary JSON semantics.
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except Exception:
        return b'{"ok":false,"error":"response serialization failed"}', False
    if len(body) > maximum:
        return b'{"ok":false,"error":"response exceeds size limit"}', False
    return body, True


__all__ = ["MAX_JSON_RESPONSE_BYTES", "serialize_json_response"]

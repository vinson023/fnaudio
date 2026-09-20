from __future__ import annotations

import re
from typing import Any, Dict


DSD_MIME_TYPES = {"audio/dsd", "audio/x-dsd", "audio/dsf", "audio/x-dsf", "audio/x-dff"}
MAX_MIME_CHARS = 128
_MIME_PATTERN = re.compile(r"^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+$")


def _safe_mime(value: Any, fallback: str) -> str:
    candidate = value if isinstance(value, str) else fallback
    if not isinstance(candidate, str) or len(candidate) > MAX_MIME_CHARS:
        return "application/octet-stream"
    return candidate if _MIME_PATTERN.fullmatch(candidate) else "application/octet-stream"


def device_supports_native_dsd(device: Dict[str, Any]) -> bool:
    try:
        value = device.get("supports_dsd") if isinstance(device, dict) else False
    except Exception:
        value = False
    return value if isinstance(value, bool) else False


def mime_for_item(item: Dict[str, Any], fallback: str = "application/octet-stream") -> str:
    try:
        value = item.get("mime") if isinstance(item, dict) else None
    except Exception:
        value = None
    return _safe_mime(value, fallback)


def should_direct_push(item: Dict[str, Any], device: Dict[str, Any]) -> bool:
    # DSD push is intentionally source-direct. The renderer is responsible
    # for advertising native DSD support; fnAudio must not silently change the
    # source format during a push.
    return True


def protocol_info(item: Dict[str, Any], device: Dict[str, Any]) -> str:
    mime = mime_for_item(item)
    return f"http-get:*:{mime}:*"

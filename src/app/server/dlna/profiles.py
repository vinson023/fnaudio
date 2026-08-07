from __future__ import annotations

from typing import Any, Dict


DSD_MIME_TYPES = {"audio/dsd", "audio/x-dsd", "audio/dsf", "audio/x-dsf", "audio/x-dff"}


def device_supports_native_dsd(device: Dict[str, Any]) -> bool:
    return bool(device.get("supports_dsd"))


def mime_for_item(item: Dict[str, Any], fallback: str = "application/octet-stream") -> str:
    return str(item.get("mime") or fallback)


def should_direct_push(item: Dict[str, Any], device: Dict[str, Any]) -> bool:
    # DSD push is intentionally source-direct. The renderer is responsible
    # for advertising native DSD support; fnAudio must not silently change the
    # source format during a push.
    return True


def protocol_info(item: Dict[str, Any], device: Dict[str, Any]) -> str:
    mime = mime_for_item(item)
    return f"http-get:*:{mime}:*"

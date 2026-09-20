"""Pure validation/projection for the legacy library JSON cache."""

from typing import Any

MAX_LEGACY_CACHE_ITEMS = 200_000


def project_legacy_cache(payload: Any, expected_library_path: str):
    if not isinstance(payload, dict) or not isinstance(expected_library_path, str):
        return None
    try:
        if payload.get("library_path") != expected_library_path:
            return None
        items = payload.get("items", [])
        signature = payload.get("signature", "")
    except Exception:
        return None
    if not isinstance(items, list):
        return None
    try:
        item_count = len(items)
    except Exception:
        return None
    if item_count > MAX_LEGACY_CACHE_ITEMS:
        return None
    if not isinstance(signature, str):
        signature = ""
    return {"items": items, "signature": signature}


__all__ = ["MAX_LEGACY_CACHE_ITEMS", "project_legacy_cache"]

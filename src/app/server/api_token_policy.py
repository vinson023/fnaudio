"""Pure helpers for extracting the fnAudio API token from HTTP headers."""

from __future__ import annotations

from typing import Any, Mapping

TOKEN_HEADER_NAMES = ("X-Fnaudio-Trim-Token", "Trim-Token", "X-Trim-Token", "Authorization")
MAX_TOKEN_CHARS = 4096


def trim_api_token(headers: Mapping[str, Any] | None) -> str:
    if headers is None:
        return ""
    getter = headers.get if isinstance(headers, Mapping) else getattr(headers, "get", None)
    if not callable(getter):
        return ""
    for name in TOKEN_HEADER_NAMES:
        try:
            value = getter(name, "")
        except Exception:
            continue
        if not isinstance(value, str):
            continue
        value = value.strip()
        if not value:
            continue
        if value.lower().startswith("bearer "):
            value = value.split(None, 1)[1].strip()
        if len(value) > MAX_TOKEN_CHARS:
            continue
        if any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value):
            continue
        return value
    return ""


__all__ = ["MAX_TOKEN_CHARS", "TOKEN_HEADER_NAMES", "trim_api_token"]

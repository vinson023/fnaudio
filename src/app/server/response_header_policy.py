"""Bounded normalization for optional HTTP response headers."""

from __future__ import annotations

import re
from typing import Any, Dict, Mapping


MAX_HEADERS = 16
MAX_HEADER_NAME = 128
MAX_HEADER_VALUE = 2048
_NAME = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")


def normalize_response_headers(source: Any) -> Dict[str, str]:
    if not isinstance(source, Mapping):
        return {}
    result: Dict[str, str] = {}
    try:
        entries = source.items()
    except Exception:
        return {}
    try:
        for raw_name, raw_value in entries:
            if len(result) >= MAX_HEADERS:
                break
            if not isinstance(raw_name, str) or not isinstance(raw_value, str):
                continue
            name = raw_name.strip()
            value = raw_value.strip()
            if not name or len(name) > MAX_HEADER_NAME or not _NAME.fullmatch(name):
                continue
            if len(value) > MAX_HEADER_VALUE or any(char in value for char in ("\r", "\n")):
                continue
            result[name] = value
    except Exception:
        return result
    return result


__all__ = ["MAX_HEADERS", "MAX_HEADER_NAME", "MAX_HEADER_VALUE", "normalize_response_headers"]

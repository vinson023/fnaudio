"""Bounded text projection for HTTP error pages."""

from __future__ import annotations

from typing import Any, Optional, Tuple

MAX_ERROR_TEXT_CHARS = 1024


def project_error_text(message: Any, explain: Any, maximum: int = MAX_ERROR_TEXT_CHARS) -> Tuple[Optional[str], Optional[str]]:
    """Keep only bounded ordinary strings for BaseHTTPRequestHandler."""
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0:
        maximum = MAX_ERROR_TEXT_CHARS
    safe_message = message[:maximum] if isinstance(message, str) else None
    safe_explain = explain[:maximum] if isinstance(explain, str) else None
    return safe_message, safe_explain


__all__ = ["MAX_ERROR_TEXT_CHARS", "project_error_text"]

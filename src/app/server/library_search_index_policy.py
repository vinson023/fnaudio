"""Pure presentation and decision rules for the SQLite search index."""

from __future__ import annotations

from typing import Any


FTS_MODE = "fts5-trigram"
LIKE_MODE = "like"


def search_index_status(mode: Any) -> dict[str, Any]:
    """Project an internal search mode into the stable public status shape."""
    safe_mode = mode if isinstance(mode, str) and mode in (FTS_MODE, LIKE_MODE) else LIKE_MODE
    return {"mode": safe_mode, "substring_minimum_chars": 3 if safe_mode == FTS_MODE else 0}


def uses_fts(mode: Any, search: Any) -> bool:
    """Decide whether a search term may use the trigram index."""
    return mode == FTS_MODE and isinstance(search, str) and len(search.strip()) >= 3


def cache_token(mode: Any, search: Any) -> str:
    """Identify the actual search execution path for read-cache keys."""
    return FTS_MODE if uses_fts(mode, search) else LIKE_MODE


__all__ = ["FTS_MODE", "LIKE_MODE", "cache_token", "search_index_status", "uses_fts"]

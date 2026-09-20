"""Pure policy for deciding whether a library row needs metadata lookup."""

from library_rows import decode_item_payload


_MAX_ARTWORK_REF = 4096
_SOURCE_FIELDS = ("title", "artist", "album")


def _safe_text(value, *, limit=4096):
    if not isinstance(value, str):
        return ""
    value = value.strip()
    return value[:limit] if len(value) <= limit else value[:limit]


def needs_track_enrichment(row):
    """Return whether filename/placeholder fields warrant provider lookup."""
    try:
        raw = row.get("item_json") if isinstance(row, dict) else row["item_json"]
        sources = (decode_item_payload(raw) or {}).get("metadata_source") or {}
    except (TypeError, KeyError, AttributeError):
        sources = {}
    try:
        return any(_safe_text(sources.get(field), limit=32) != "tag" for field in _SOURCE_FIELDS)
    except (AttributeError, TypeError):
        return True


def has_local_artwork(row):
    """Return whether the scanned row carries a usable local artwork ref."""
    try:
        raw = row.get("item_json") if isinstance(row, dict) else row["item_json"]
        payload = decode_item_payload(raw)
        if payload is None:
            return False
        return any(_safe_text(payload.get(key), limit=_MAX_ARTWORK_REF) for key in (
            "cover_url", "cover_thumbnail_url", "artwork_id", "metadata_artwork_id",
        ))
    except (TypeError, KeyError, AttributeError):
        return False


__all__ = ["has_local_artwork", "needs_track_enrichment"]

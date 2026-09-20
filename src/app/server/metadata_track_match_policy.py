"""Pure normalization policy for persisted provider track matches."""

from __future__ import annotations

import json
import math

from metadata_provider_payload import candidate_mappings
from metadata_track_candidate_policy import project_track_candidate_fields
from metadata_text import parse_track_number
from metadata_artwork_policy import valid_artwork_id


MAX_PERSISTED_TRACK_CANDIDATES = 8
MAX_PERSISTED_CANDIDATE_TEXT = 512
MAX_TRACK_MATCH_JSON_BYTES = 192 * 1024


def _decode_track_match_fields(value):
    if not isinstance(value, str):
        return None
    try:
        if len(value.encode("utf-8")) > MAX_TRACK_MATCH_JSON_BYTES:
            return None
        decoded = json.loads(value)
    except (TypeError, ValueError, UnicodeError, json.JSONDecodeError, RecursionError):
        return None
    return decoded if isinstance(decoded, dict) else None


def decode_track_match_fields(value):
    """Decode one persisted match without accepting an unbounded legacy row."""
    return _decode_track_match_fields(value) or {}


def track_match_fields_are_valid(value):
    """Distinguish a valid empty terminal match from a damaged cache row."""
    return _decode_track_match_fields(value) is not None


def finite_candidate_confidence(value, default=0.0):
    """Project a provider score to a finite float without coercion surprises."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return float(default)
    try:
        number = float(value or 0)
    except (TypeError, ValueError, OverflowError):
        return float(default)
    return number if math.isfinite(number) else float(default)


def normalize_track_candidates(values):
    """Return bounded, detached candidates with finite confidence values.

    Provider adapters are intentionally tolerant, but persistence must receive
    deterministic dictionaries. Non-mapping values are discarded by the
    shared bounded payload policy and each mapping is copied before its score
    is normalized, preventing mutation of adapter-owned objects.
    """
    normalized = []
    for candidate in candidate_mappings(values, MAX_PERSISTED_TRACK_CANDIDATES):
        item = project_track_candidate_fields(
            candidate.get("title"), candidate.get("artist"),
            candidate.get("album"), candidate.get("album_artist"),
            candidate.get("date"), candidate.get("genre"),
            candidate.get("track_no"), candidate.get("image_url"),
            candidate.get("provider_id"), candidate.get("source"),
        )
        for field in ("title", "artist", "album", "album_artist", "genre"):
            item[field] = item[field][:MAX_PERSISTED_CANDIDATE_TEXT]
        item["image_url"] = item["image_url"][:2048]
        item["provider_id"] = item["provider_id"][:128]
        item["disc_no"] = parse_track_number(candidate.get("disc_no"))
        item["confidence"] = finite_candidate_confidence(candidate.get("confidence"))
        normalized.append(item)
    return normalized


__all__ = [
    "MAX_PERSISTED_CANDIDATE_TEXT", "MAX_PERSISTED_TRACK_CANDIDATES",
    "MAX_TRACK_MATCH_JSON_BYTES", "decode_track_match_fields", "finite_candidate_confidence",
    "track_match_fields_are_valid",
    "normalize_track_candidates", "valid_artwork_id",
]

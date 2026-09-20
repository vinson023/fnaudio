"""Bounded payload projection for persisted metadata worker jobs."""

from __future__ import annotations

import math


MAX_JOB_TEXT = 4096
_TEXT_FIELDS = (
    "id", "name", "path", "title", "artist", "album", "album_artist",
    "composer", "genre", "format", "mime", "cue_path",
)
_NUMBER_FIELDS = (
    "duration", "size", "modified_ns", "track_no", "cue_start", "cue_end",
)
_BOOLEAN_FIELDS = ("is_dsd", "cue_track")


def project_metadata_job_payload(payload):
    """Keep only fields consumed by metadata providers and local readers."""
    if not isinstance(payload, dict):
        return {}
    projected = {}
    for field in _TEXT_FIELDS:
        value = payload.get(field)
        if isinstance(value, str):
            projected[field] = value.replace("\x00", "").strip()[:MAX_JOB_TEXT]
    for field in _NUMBER_FIELDS:
        value = payload.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if isinstance(value, float) and not math.isfinite(value):
            continue
        projected[field] = value
    for field in _BOOLEAN_FIELDS:
        value = payload.get(field)
        if isinstance(value, bool):
            projected[field] = value
    return projected


__all__ = ["MAX_JOB_TEXT", "project_metadata_job_payload"]

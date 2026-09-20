"""Pure, bounded projection helpers for cached track metadata overlays."""

from metadata_track_match_policy import decode_track_match_fields


MAX_OVERLAY_TEXT = 4096
TRACK_OVERLAY_FIELDS = (
    "title", "artist", "album", "album_artist", "composer", "genre",
    "date", "track_no", "disc_no",
)


def bounded_overlay_text(value, limit=MAX_OVERLAY_TEXT):
    """Accept only bounded text from a decoded provider cache."""
    if not isinstance(value, str):
        return ""
    value = value.replace("\x00", "").strip()
    return value[:limit] if len(value) > limit else value


def project_match_fields(fields_json):
    """Decode one cached match and expose only bounded text fields."""
    payload = decode_track_match_fields(fields_json)
    if not isinstance(payload, dict) or not isinstance(payload.get("best"), dict):
        return {}
    return {
        field: bounded_overlay_text(payload["best"].get(field))
        for field in TRACK_OVERLAY_FIELDS
        if bounded_overlay_text(payload["best"].get(field))
    }


def visible_match_projection_signature(fields_json, status):
    """Return only the stored-match fields visible in normal library rows.

    Review candidates belong to the manual-selection dialog and are not
    overlaid onto ordinary song rows. Their ranking changes must not clear the
    page cache or cause a list/cover redraw; automatic and confirmed matches
    remain visible and keep their bounded field signature.
    """
    if not isinstance(status, str) or status not in ("auto", "confirmed"):
        return ()
    fields = project_match_fields(fields_json)
    return tuple((field, fields.get(field, "")) for field in TRACK_OVERLAY_FIELDS if fields.get(field))


__all__ = [
    "MAX_OVERLAY_TEXT", "TRACK_OVERLAY_FIELDS", "bounded_overlay_text",
    "project_match_fields", "visible_match_projection_signature",
]

"""Pure, bounded projection for provider track-candidate fields."""

from __future__ import annotations

from metadata_release_date import normalize_release_date
from metadata_text import clean_tag, parse_track_number

MAX_CANDIDATE_SOURCE = 32
MAX_CANDIDATE_URL = 2048
MAX_CANDIDATE_TEXT = 4096


def _bounded_text(value, limit=MAX_CANDIDATE_TEXT):
    if not isinstance(value, str):
        return ""
    return clean_tag(value)[:limit]


def _bounded_identifier(value):
    if isinstance(value, bool):
        return ""
    if isinstance(value, int):
        return str(value)[:MAX_CANDIDATE_SOURCE]
    return _bounded_text(value, MAX_CANDIDATE_SOURCE)


def project_track_candidate_fields(
    title, artist, album="", album_artist="", date="", genre="",
    track_no=0, image_url="", provider_id="", source="",
):
    """Return only safe, bounded candidate fields from an untrusted payload."""

    projected_artist = _bounded_text(artist)
    image = _bounded_text(image_url, MAX_CANDIDATE_URL)
    if image.startswith("//"):
        image = "https:" + image
    return {
        "title": _bounded_text(title),
        "artist": projected_artist,
        "album": _bounded_text(album),
        "album_artist": _bounded_text(album_artist) or projected_artist,
        "date": normalize_release_date(date),
        "genre": _bounded_text(genre),
        "track_no": parse_track_number(track_no),
        "disc_no": 0,
        "image_url": image,
        "provider_id": _bounded_identifier(provider_id),
        "source": _bounded_text(source, MAX_CANDIDATE_SOURCE),
    }


__all__ = ["MAX_CANDIDATE_SOURCE", "MAX_CANDIDATE_URL", "project_track_candidate_fields"]

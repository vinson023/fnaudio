"""Pure query construction for metadata provider searches."""

from __future__ import annotations

import os
import re
import sqlite3
from collections.abc import Mapping

from metadata_text import clean_tag

_PLACEHOLDERS = frozenset({
    "", "未分类", "未知歌曲", "未知专辑", "未知歌手", "未知艺术家", "未知作曲者",
    "unknown song", "unknown album", "unknown artist", "unknown composer",
})
MAX_QUERY_TEXT = 512


def _text(value):
    if not isinstance(value, str):
        return ""
    return clean_tag(value).strip()[:MAX_QUERY_TEXT]


def _field(track, key):
    try:
        if isinstance(track, Mapping):
            return track.get(key)
        return track[key]
    except (KeyError, IndexError, TypeError, AttributeError):
        return None


def track_search_query(track):
    """Build a bounded title/artist/album query, omitting placeholders.

    Album is only an additional provider hint; it never changes the local
    presentation or matching threshold.  Supplying it when already known
    reduces same-title collisions and lets providers return the missing
    release fields more consistently.
    """
    # sqlite3.Row and other bounded mapping views are used by a few server
    # paths before they are materialized into plain dictionaries.  Rejecting
    # those rows made the provider chain silently receive an empty query even
    # though title/artist fields were present.  Accept only Mapping objects;
    # arbitrary objects are still refused so provider URLs never stringify
    # untrusted values.
    if not isinstance(track, (Mapping, sqlite3.Row)):
        return ""
    title = _text(_field(track, "title"))
    artist = _text(_field(track, "artist"))
    album = _text(_field(track, "album"))
    # Even when a scanner recovered a title Tag, the artist may still be
    # missing.  A conventional filename can safely supply just that missing
    # artist hint, provided its right-hand side agrees with the known title.
    if artist.casefold() in _PLACEHOLDERS and title.casefold() not in _PLACEHOLDERS:
        path = _field(track, "path")
        if isinstance(path, str):
            basename = _text(re.sub(r"\.[A-Za-z0-9]{1,8}$", "", os.path.basename(path.replace("\\", "/"))))
            parts = re.split(r"\s*[-–—]\s*", basename, maxsplit=1)
            if len(parts) == 2 and _text(parts[1]).casefold() == title.casefold():
                artist = _text(parts[0])
    # Scanners can expose a blank/placeholder title while the path still
    # contains the only useful identity.  Use the basename strictly as a
    # lookup hint; this never mutates the library Tag or presentation fields.
    if title.casefold() in _PLACEHOLDERS:
        path = _field(track, "path")
        if isinstance(path, str):
            basename = os.path.basename(path.replace("\\", "/"))
            basename = re.sub(r"\.[A-Za-z0-9]{1,8}$", "", basename)
            basename = _text(basename)
            if basename.casefold() not in _PLACEHOLDERS:
                title = basename
                # Common exports use ``artist - title`` as the filename.
                # Split only this filename fallback (never a real Tag) so
                # provider search receives a useful artist hint while the
                # original library presentation remains untouched.
                parts = re.split(r"\s*[-–—]\s*", basename, maxsplit=1)
                if len(parts) == 2 and (not artist or artist.casefold() in _PLACEHOLDERS):
                    artist, title = _text(parts[0]), _text(parts[1])
    if artist.casefold() in _PLACEHOLDERS:
        artist = ""
    if album.casefold() in _PLACEHOLDERS:
        album = ""
    return " ".join(part for part in (title, artist, album) if part)


def filename_track_hint(track):
    """Return a bounded ``(artist, title)`` hint from ``artist - title``.

    This is deliberately presentation-only: callers may expose it as a
    low-confidence candidate when providers are unavailable, but it must not
    mutate the scanned Tag values.  A filename without a separator is kept as
    a title-only hint so completely untagged files still have a useful local
    identity.
    """
    if not isinstance(track, (Mapping, sqlite3.Row)):
        return "", ""
    path = _field(track, "path")
    if not isinstance(path, str) or not path.strip():
        return "", ""
    basename = re.sub(r"\.[A-Za-z0-9]{1,8}$", "", os.path.basename(path.replace("\\", "/")))
    basename = _text(basename)
    if not basename or basename.casefold() in _PLACEHOLDERS:
        return "", ""
    parts = re.split(r"\s*[-–—]\s*", basename, maxsplit=1)
    if len(parts) == 2:
        artist, title = _text(parts[0]), _text(parts[1])
        if artist and title:
            return artist, title
    return "", basename


def filename_track_candidate(track):
    """Build a presentation-only candidate from a conventional filename.

    The result is deliberately low confidence and contains no album guess;
    callers may display it while a provider lookup is pending, but must not
    treat it as confirmed metadata or write it back to the source file.
    """
    artist, title = filename_track_hint(track)
    if not title:
        return None
    return {
        "title": title,
        "artist": artist,
        "album": "",
        "album_artist": "",
        "date": "",
        "genre": "",
        "track_no": 0,
        "composer": "",
        "image_url": "",
        "provider_id": "",
        "source": "filename",
        "confidence": 0.56,
    }


def local_track_candidate(track):
    """Project already-read local tags as an immediate display candidate.

    The provider queue is intentionally asynchronous, but the candidate
    dialog should not look empty while a worker is warming up.  This helper
    copies only bounded, presentation-safe fields from the scanned row; it
    never implies a provider match and therefore must not trigger Tag writes.
    """
    if not isinstance(track, (Mapping, sqlite3.Row)):
        return None
    fields = ("title", "artist", "album", "album_artist", "date", "genre", "composer")
    candidate = {key: _text(_field(track, key)) for key in fields}
    track_no = _field(track, "track_no")
    try:
        if isinstance(track_no, bool):
            track_no = 0
        track_no = int(track_no or 0)
    except (TypeError, ValueError, OverflowError):
        track_no = 0
    candidate["track_no"] = max(0, min(100000, track_no))
    if not any(candidate.get(key) for key in fields) and not candidate["track_no"]:
        return None
    candidate.update({
        "image_url": "", "provider_id": "", "source": "local",
        "confidence": 1.0,
    })
    return candidate


def entity_search_query(name, artist=""):
    """Build a bounded query for album/artist metadata lookups."""
    parts = []
    for value in (name, artist):
        text = _text(value)
        if text.casefold() not in _PLACEHOLDERS and text:
            parts.append(text)
    return " ".join(parts)


__all__ = ["MAX_QUERY_TEXT", "entity_search_query", "filename_track_candidate", "filename_track_hint", "local_track_candidate", "track_search_query"]

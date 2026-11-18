"""Pure text and filename normalization used by scanners and metadata jobs."""

from __future__ import annotations

import os
import re
from itertools import islice

MAX_TAG_TEXT = 4096
MAX_NORMALIZED_TAGS = 256
MAX_TAG_KEY = 256


def clean_tag(value):
    """Normalize a human-readable tag without changing its meaning."""
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value[:MAX_TAG_TEXT].replace("\x00", "")).strip()


def parse_track_number(value):
    """Return the numeric part of common track tags such as ``03/12``."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value if 1 <= value <= 999999 else 0
    text = clean_tag(value)
    if not text:
        return 0
    match = re.match(r"^\s*(\d+)", text)
    if not match:
        return 0
    digits = match.group(1)
    if len(digits) > 6:
        return 0
    try:
        number = int(digits)
    except (TypeError, ValueError, OverflowError):
        return 0
    return number if 1 <= number <= 999999 else 0


def parse_year(value):
    """Return a four-digit year from the shapes date tags actually use.

    ``date``/``TDRC``/``©day`` arrive as ``2020``, ``2020-05-01`` or
    ``2020-05-01T00:00:00``; ``TYER`` as bare digits.  A value that carries no
    four-digit year is not a year, so it yields 0 rather than a guess -- the
    caller stores 0 and the UI simply shows nothing.
    """
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value if 1000 <= value <= 2999 else 0
    text = clean_tag(value)
    if not text:
        return 0
    match = re.search(r"(?<!\d)(\d{4})(?!\d)", text)
    if not match:
        return 0
    year = int(match.group(1))
    return year if 1000 <= year <= 2999 else 0


def parse_date_text(value):
    """Return the tag text of a date tag, keeping its original shape.

    The library's canonical field for the year is ``date`` -- that is what
    ``metadata_service.TRACK_METADATA_FIELDS`` writes back into ``TDRC`` and
    what the candidate dialog compares.  Storing a truncated year here would
    make a round-trip lose ``2019-08-30``.
    """
    if isinstance(value, bool):
        return ""
    if isinstance(value, int):
        return str(value)
    return clean_tag(value)


def artist_title_from_filename(path):
    if not isinstance(path, str):
        return "", ""
    name = os.path.splitext(os.path.basename(path))[0][:MAX_TAG_TEXT]
    name = re.sub(r"^\d{1,3}[\s._-]+", "", name).replace("_", " ").strip()
    for separator in (" - ", " – ", " — ", " -", "- "):
        if separator not in name:
            continue
        left, right = name.split(separator, 1)
        left = clean_tag(left)
        right = clean_tag(right)
        if left and right:
            return left, right
    return "", ""


def display_name(path):
    if not isinstance(path, str):
        return "未知曲目"
    name = os.path.splitext(os.path.basename(path))[0][:MAX_TAG_TEXT]
    name = re.sub(r"^\d{1,3}[\s._-]+", "", name)
    return name.replace("_", " ").strip() or "未知曲目"


def cue_time_seconds(value):
    text = value if isinstance(value, str) else ""
    match = re.match(r"(\d{1,6}):(\d{1,6}):(\d{1,6})$", text)
    if not match:
        return 0.0
    minutes, seconds, frames = [int(x) for x in match.groups()]
    return minutes * 60 + seconds + frames / 75.0


def cue_value(line):
    match = re.search(r'"([^"]*)"', line)
    if match:
        return clean_tag(match.group(1))
    parts = line.split(None, 1)
    return clean_tag(parts[1] if len(parts) > 1 else "")


def normalize_probe_tags(raw_tags):
    """Normalize ffprobe/format tag aliases into the library's fields.

    R591 split ``album_artist`` out of ``artist``.  The two used to share one
    alias list, which meant the key ``album_artist`` was never produced at all:
    a compilation's album artist survived only as long as the file had no
    ``ARTIST`` tag, and ``tracks.album_artist`` -- a column the album grouping
    already prefers over ``artist`` -- stayed empty for every non-CUE track.
    ``artist`` still falls back to ``album_artist`` when the file carries no
    track artist, so a file tagged with only ``ALBUMARTIST`` keeps the name it
    used to show.
    """
    aliases = {
        "title": ("title", "tit2", "\xa9nam"),
        "artist": ("artist", "artists", "performer", "performers", "author", "tpe1", "\xa9art"),
        "album": ("album", "talb", "\xa9alb"),
        "album_artist": ("album_artist", "albumartist", "album artist", "tpe2", "aart", "\xa9aart"),
        "composer": ("composer", "composers", "tcom", "\xa9wrt"),
        "genre": ("genre", "genres", "tcon", "\xa9gen"),
        "track_no": ("track", "tracknumber", "track_number", "trck", "trkn", "\xa9trk", "tracknum", "disktrack"),
        "disc_no": ("disc", "discnumber", "disknumber", "disc_number", "disk_number", "disk", "tpos", "\xa9dis"),
        "date": ("date", "year", "tyer", "tdrc", "tdor", "originaldate", "\xa9day"),
        "comment": ("comment", "comments", "comm", "\xa9cmt"),
    }
    parsers = {
        "track_no": parse_track_number,
        "disc_no": parse_track_number,
        "date": parse_date_text,
    }
    raw_tags = raw_tags if isinstance(raw_tags, dict) else {}
    normalized = {}
    for key, value in islice(raw_tags.items(), MAX_NORMALIZED_TAGS):
        if isinstance(key, str) and len(key) <= MAX_TAG_KEY:
            normalized[key.strip().lower()] = value
    tags = {}
    for field, keys in aliases.items():
        parse = parsers.get(field, clean_tag)
        for key in keys:
            value = normalized.get(key)
            if value:
                parsed = parse(value)
                if parsed:
                    tags[field] = parsed
                    break
    for key, value in islice(raw_tags.items(), MAX_NORMALIZED_TAGS):
        if not isinstance(key, str):
            continue
        name = key.lower()
        if name in ("title", "artist", "album", "album_artist", "composer", "genre", "comment") and value:
            cleaned = clean_tag(value)
            if cleaned:
                tags.setdefault(name, cleaned)
    if not tags.get("artist") and tags.get("album_artist"):
        tags["artist"] = tags["album_artist"]
    # ``year`` is the numeric projection of ``date``: the column needs an
    # integer to sort on, the tag round-trip needs the original text.  Both are
    # derived here so they cannot disagree.
    year = parse_year(tags.get("date"))
    if year:
        tags["year"] = year
    return tags

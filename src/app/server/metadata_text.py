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
    """Normalize ffprobe/format tag aliases into the library's six fields."""
    aliases = {
        "title": ("title", "tit2", "\xa9nam"),
        "artist": ("artist", "artists", "album_artist", "albumartist", "performer", "performers", "author", "tpe1", "\xa9art"),
        "album": ("album", "talb", "\xa9alb"),
        "composer": ("composer", "composers", "tcom", "\xa9wrt"),
        "genre": ("genre", "genres", "tcon", "\xa9gen"),
        "track_no": ("track", "tracknumber", "track_number", "trck", "trkn", "\xa9trk", "tracknum", "disktrack"),
    }
    raw_tags = raw_tags if isinstance(raw_tags, dict) else {}
    normalized = {}
    for key, value in islice(raw_tags.items(), MAX_NORMALIZED_TAGS):
        if isinstance(key, str) and len(key) <= MAX_TAG_KEY:
            normalized[key.strip().lower()] = value
    tags = {}
    for field, keys in aliases.items():
        for key in keys:
            value = normalized.get(key)
            if value:
                parsed = parse_track_number(value) if field == "track_no" else clean_tag(value)
                if parsed:
                    tags[field] = parsed
                    break
    for key, value in islice(raw_tags.items(), MAX_NORMALIZED_TAGS):
        if not isinstance(key, str):
            continue
        name = key.lower()
        if name in ("title", "artist", "album", "composer", "genre") and value:
            cleaned = clean_tag(value)
            if cleaned:
                tags.setdefault(name, cleaned)
    return tags

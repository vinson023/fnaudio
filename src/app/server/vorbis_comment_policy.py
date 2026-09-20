"""Bounded parser for the metadata fields fnAudio needs from Vorbis comments."""

from __future__ import annotations

import re

from metadata_text import clean_tag, parse_track_number


MAX_VORBIS_TAGS = 128
_COMMENT = re.compile(rb"(?i)(TITLE|ARTIST|ALBUM|COMPOSER|GENRE|TRACKNUMBER)=([^\x00\r\n]+)")


def parse_vorbis_comments(data):
    if not isinstance(data, (bytes, bytearray)):
        return {}
    tags = {}
    for index, match in enumerate(_COMMENT.finditer(data)):
        if index >= MAX_VORBIS_TAGS:
            break
        key, value = match.groups()
        name = key.decode("ascii", "ignore").lower()
        text = value.decode("utf-8", "ignore")
        tags["track_no" if name == "tracknumber" else name] = (
            parse_track_number(text) if name == "tracknumber" else clean_tag(text)
        )
    return tags


__all__ = ["MAX_VORBIS_TAGS", "parse_vorbis_comments"]

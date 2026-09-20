"""Pure CUE sheet text parsing used by the library scanner."""

from __future__ import annotations

import re

from metadata_text import cue_time_seconds, cue_value
from cue_numeric_policy import finite_number, track_number

MAX_CUE_LINES = 20000

# A tab and a single-digit index number are both legal CUE, and some taggers
# run two spaces after the keyword. The start of a track must not depend on
# which of those shapes the sheet happens to use, so the separator is not
# pinned to one literal space here.
_INDEX_LINE_RE = re.compile(r"^INDEX[ \t]+(\d{1,2})[ \t]+(\S+)", re.IGNORECASE)


def _attach_track_ends(tracks, observe=None):
    """Give every track the start of the next track that shares its file.

    The end is the start of the nearest *later* track on the same file whose
    start is further in, which is exactly what the previous nested scan produced.
    Keeping one monotonic stack per file reaches that answer in one pass, and the
    nested form was quadratic on two ordinary sheet shapes (one FILE per track,
    and a sheet with no usable INDEX line): the scanner cap of MAX_CUE_LINES lines
    turned a single untrusted CUE into seconds of indexing CPU.

    The answer has three states, because "there is no next track" and "there is
    no usable next track" are different facts and only one of them means the
    track runs to the end of the file:

    * a positive number is where the next track on this file starts;
    * ``0.0`` means the sheet holds no later track for this file at all, so this
      track is the final one and its end is the end of the file;
    * ``None`` means later tracks exist for this file but none of them starts
      further in - a tie, or an out-of-order sheet - so the boundary is unknown.

    Folding the third state into the second is what let ``0.0`` claim both "last
    track" and "no idea" all the way into the stored ``cue_end``; the scanner
    resolves the states with ``cue_segment_end``, which borrows the file duration
    only for a genuine final track.

    "observe" is a seam for that claim, not a feature: it is called exactly
    once per stack comparison, so a caller can count how many candidate starts
    this stage examined. It deliberately counts examinations instead of calls
    to a numeric helper, because the helper is an implementation detail -
    normalisation may move into the main loop or be wrapped differently
    without changing what this stage costs per track.
    """
    stacks: dict[str, list[float]] = {}
    for track in reversed(tracks):
        start = finite_number(track.get("start"))
        name = track.get("file")
        if not isinstance(name, str):
            # The value is used as a dictionary key, which quietly assumes it is a string:
            # `cue_value()` cleans every field it returns, so a parsed CUE always arrives
            # hashable.  A track assembled some other way must degrade into an ungrouped
            # track - a boundary nobody can confirm, sharing no stack with anything -
            # instead of raising TypeError out of a parser whose job is to survive
            # unusable sheets.
            track["end"] = None
            continue
        stack = stacks.setdefault(name, [])
        superseded = False
        while stack:
            if observe is not None:
                observe()
            if not (stack[-1] <= start):
                # Same predicate as the old "while stack and stack[-1] <= start"
                # guard, so the incomparable-value behaviour is unchanged.
                break
            # This candidate sits later in the sheet yet does not start further in,
            # so it cannot bound the track being placed and neither can anything it
            # already shadowed.  Recording that is what separates "final track" from
            # "unknown", and it costs no examination: the pop was already happening.
            superseded = True
            stack.pop()
        track["end"] = stack[-1] if stack else (None if superseded else 0.0)
        stack.append(start)


def parse_cue_structure(lines, fallback_album="", observe_end_stage=None):
    """Return album metadata and track offsets from decoded CUE lines.

    File access and audio-path validation deliberately remain in ``library.py``.
    This parser accepts only text lines so untrusted binary objects cannot cause
    implicit string conversions during a scan.

    observe_end_stage is forwarded to the track-end stage (see
    _attach_track_ends); it is a measurement seam and must not change results.
    """
    album = fallback_album or ""
    album_artist = "未知艺术家"
    current_file = ""
    current = None
    tracks = []
    try:
        source_lines = iter(lines or ())
    except TypeError:
        source_lines = iter(())
    for line_no, raw in enumerate(source_lines):
        if line_no >= MAX_CUE_LINES:
            break
        if not isinstance(raw, str):
            continue
        if len(raw) > 4096:
            continue
        line = raw.strip()
        upper = line.upper()
        if upper.startswith("FILE "):
            current_file = cue_value(line)
        elif upper.startswith("TITLE ") and current is None:
            album = cue_value(line) or album
        elif upper.startswith("PERFORMER ") and current is None:
            album_artist = cue_value(line) or album_artist
        elif upper.startswith("TRACK "):
            if current:
                tracks.append(current)
            numbers = re.findall(r"\d+", line)
            current = {
                "track_no": track_number(numbers[0], len(tracks) + 1) if numbers else len(tracks) + 1,
                "file": current_file,
                "title": "",
                "artist": "",
                "start": 0.0,
            }
        elif current and upper.startswith("TITLE "):
            current["title"] = cue_value(line)
        elif current and upper.startswith("PERFORMER "):
            current["artist"] = cue_value(line)
        elif current and upper.startswith("INDEX"):
            index_line = _INDEX_LINE_RE.match(line)
            # INDEX 01 is where the track starts. INDEX 00 is a pregap marker and
            # any larger index is a cue point, so neither may move the start.
            if index_line and int(index_line.group(1)) == 1:
                current["start"] = cue_time_seconds(index_line.group(2))
    if current:
        tracks.append(current)
    _attach_track_ends(tracks, observe_end_stage)
    return {"album": album, "album_artist": album_artist, "tracks": tracks}

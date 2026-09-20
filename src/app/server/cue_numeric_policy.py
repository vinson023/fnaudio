"""Pure numeric policy for CUE time/offset values."""


def finite_number(value, default=0.0):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return result if result == result and abs(result) != float("inf") else default


def track_number(value, fallback: int) -> int:
    if not isinstance(value, str) or not value or len(value) > 6:
        return fallback
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return fallback
    return number if 1 <= number <= 999999 else fallback


def cue_segment_end(end, file_duration):
    """Resolve the end of a CUE segment into the value a scan stores.

    The parser answers the boundary in three states and only one of them may
    borrow the duration of the source file:

    * a positive number is where the next track on the same file starts;
    * ``0.0`` means nothing follows this track on its file, so the track really
      does run to the end of the file and the file duration is the answer;
    * ``None`` means later tracks exist on the file but none starts further in,
      so the boundary is unknown and must not be invented.

    Collapsing the third state into the second is what made a stored ``cue_end``
    of the file duration ambiguous, so an unknown boundary comes back as ``0.0``
    - the same value the ``cue_end REAL NOT NULL`` column already uses for "no
    known end" - and never as a fabricated full-file segment.
    """
    boundary = finite_number(end, None)
    if boundary is None or boundary < 0.0:
        return 0.0
    if boundary > 0.0:
        return boundary
    return finite_number(file_duration)


__all__ = ["cue_segment_end", "finite_number", "track_number"]

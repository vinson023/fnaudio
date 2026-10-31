"""Remember the file revisions that fnAudio itself produced.

The library signature treats every ``(st_mtime_ns, st_size)`` change as a real
modification, which is correct for a user's collection.  It is wrong for
fnAudio's own metadata writeback: the tag writer replaces the user's audio file
to store artwork, lyrics or matched tags, so the replaced file makes the next
signature differ.  On a 62,684-track library that loop is self-sustaining -
every scan enables more writeback, every writeback defeats the early exit in
``refresh_library_if_changed``, and the process spends a whole CPU core
rescanning forever instead of answering the browser.

This module is the memory-side answer: the writer records the revision it just
installed, and the signature builder asks whether the revision it is looking at
is one of those.  Only an exact ``(mtime_ns, size)`` pair is suppressed, so any
later edit by anybody else - including an edit that restores the original file
size - still produces a real signature token.

Deliberately in-memory and bounded.  A restart therefore sees the files fnAudio
wrote as ordinary changes and performs one real rescan, which is the honest
outcome: the index re-parses those files, absorbs the written tags, and stays
stable afterwards because nothing rewrites them again.  Nothing here decides
whether a rescan should happen; it only answers "was this revision mine?".

Every public function fails safe.  Garbage input means "not a self-write",
because a missed suppression costs one extra scan while a false suppression
would hide a genuine change to the user's library.
"""

import threading
import time
from collections import OrderedDict

# One entry per audio file covers the largest realistic collection, and the LRU
# keeps memory bounded past that.  A displaced entry is not a correctness
# problem: that file simply looks external again and triggers one real rescan.
MAX_TRACKED_REVISIONS = 200_000

# The tag writer stages its output beside the original file before replacing
# it, so that scratch file keeps a supported audio extension on purpose.
SELF_WRITE_TEMP_MARKER = ".fnaudio-tagging"

_LOCK = threading.Lock()
_REVISIONS = OrderedDict()
_RECENT_PATHS = OrderedDict()
SELF_WRITE_EVENT_GRACE_SECONDS = 5.0


def _clean_path(path):
    """Normalise one path to a lookup key, or None when it cannot be one."""
    if not isinstance(path, str):
        return None
    text = path.strip()
    if not text:
        return None
    return os_normpath(text)


def os_normpath(text):
    """Path normalisation kept in one place so writer and scanner agree."""
    import os

    return os.path.normpath(text)


def _clean_revision(mtime_ns, size):
    """Coerce one (mtime_ns, size) pair, or None when either half is unusable."""
    try:
        mtime = int(mtime_ns)
        length = int(size)
    except (TypeError, ValueError, OverflowError):
        return None
    if mtime < 0 or length < 0:
        return None
    return (mtime, length)


def record(path, mtime_ns, size):
    """Remember a revision this process just wrote.  True when stored."""
    key = _clean_path(path)
    revision = _clean_revision(mtime_ns, size)
    if key is None or revision is None:
        return False
    with _LOCK:
        existing = _REVISIONS.get(key)
        _REVISIONS[key] = revision
        _REVISIONS.move_to_end(key)
        _RECENT_PATHS[key] = time.monotonic()
        _RECENT_PATHS.move_to_end(key)
        if existing is None:
            while len(_REVISIONS) > MAX_TRACKED_REVISIONS:
                _REVISIONS.popitem(last=False)
        while len(_RECENT_PATHS) > MAX_TRACKED_REVISIONS:
            _RECENT_PATHS.popitem(last=False)
    return True


def record_from_stat(path, stat_result):
    """Record straight from an ``os.stat_result``.  False on unusable input."""
    if stat_result is None:
        return False
    return record(
        path,
        getattr(stat_result, "st_mtime_ns", None),
        getattr(stat_result, "st_size", None),
    )


def matches(path, mtime_ns, size):
    """True only when this exact revision was written by this process."""
    key = _clean_path(path)
    revision = _clean_revision(mtime_ns, size)
    if key is None or revision is None:
        return False
    with _LOCK:
        stored = _REVISIONS.get(key)
        if stored is None:
            return False
        if stored == revision:
            # Touch the LRU so a hot library does not churn its ledger.
            _REVISIONS.move_to_end(key)
            return True
        return False


def matches_stat(path, stat_result):
    """Convenience form of :func:`matches` for an ``os.stat_result``."""
    if stat_result is None:
        return False
    return matches(
        path,
        getattr(stat_result, "st_mtime_ns", None),
        getattr(stat_result, "st_size", None),
    )


def recent_path(path, max_age=SELF_WRITE_EVENT_GRACE_SECONDS):
    """Return true for a short-lived rename/delete event from our tag writer."""
    key = _clean_path(path)
    try:
        age = float(max_age)
    except (TypeError, ValueError, OverflowError):
        age = SELF_WRITE_EVENT_GRACE_SECONDS
    if key is None or age < 0:
        return False
    now = time.monotonic()
    with _LOCK:
        created = _RECENT_PATHS.get(key)
        if created is None:
            return False
        if now - created <= age:
            _RECENT_PATHS.move_to_end(key)
            return True
        _RECENT_PATHS.pop(key, None)
        return False


def is_self_write_artifact(filename):
    """True for the staging files this process writes next to a track.

    ``_write_track_tags`` builds ``song.flac.fnaudio-tagging.flac`` beside the
    original, so the name ends in a supported extension and the scanner reads
    it as a second copy of the track.  Indexing it costs a ghost track, a
    signature change, and - when the rename finally deletes it - a scan error,
    and on a library that is rewriting tags continuously that is a rescan that
    never ends.
    """
    if not isinstance(filename, str):
        return False
    return SELF_WRITE_TEMP_MARKER in filename.lower()


def tracked_count():
    """Number of remembered revisions.  Used by tests and diagnostics."""
    with _LOCK:
        return len(_REVISIONS)


def clear():
    """Forget every remembered revision."""
    with _LOCK:
        _REVISIONS.clear()
        _RECENT_PATHS.clear()


__all__ = [
    "MAX_TRACKED_REVISIONS",
    "SELF_WRITE_TEMP_MARKER",
    "clear",
    "is_self_write_artifact",
    "matches",
    "matches_stat",
    "recent_path",
    "record",
    "record_from_stat",
    "tracked_count",
]

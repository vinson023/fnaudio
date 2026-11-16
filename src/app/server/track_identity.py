"""Content-derived track identity.

A track id used to be ``sha1(absolute path)[:16]``. Reinstalling the OS, swapping
a disk or mounting the collection somewhere else renamed every track at once, so
every favorite, playlist entry and queued track pointed at an id the library could
never serve again - the stored list kept counting rows that no longer existed, and
favoriting the same song again added a second row beside the ghost.

The identity is now derived from the file's own content, so a rename, a move to
another folder or another disk keeps it. Only the bytes count:

    sha1("fnaudio-id1|" + size + "|" + head + tail)[:16]

Head and tail are bounded samples (16 KiB each). Reading whole files would be
9.6 GiB of IO for a 50k-track library; the head of every supported container
already carries the codec parameters and, for FLAC, the MD5 of the audio stream,
while the tail pins the last frames. Combined with the exact size that is enough
to make an accidental collision effectively impossible, and it costs 32 KiB per
track.

Two byte-identical files (a duplicate copy) deliberately collapse to one id: the
index keeps one row per distinct content, which is also what a listener expects
to see in the list.

The encoder for cuesheet tracks has no file of its own, so its identity is the
cuesheet's content id plus the track number: moving the whole album keeps every
track, and re-splitting does not.
"""

from __future__ import annotations

import hashlib
import os

SAMPLE_BYTES = 16 * 1024
_ID_DOMAIN = b"fnaudio-id1|"
SMALL_FILE_LIMIT = SAMPLE_BYTES * 3
ID_HEX_CHARS = 16


def _sample_hasher(handle, size):
    """Feed the bounded samples of one file into a hash."""
    digest = hashlib.sha1()
    digest.update(_ID_DOMAIN)
    digest.update(str(size).encode("ascii"))
    digest.update(b"|")
    if size <= SMALL_FILE_LIMIT:
        # Small enough to read once: no seams, no repeated windows.
        digest.update(handle.read(SMALL_FILE_LIMIT))
        return digest
    digest.update(handle.read(SAMPLE_BYTES))
    middle = max(SAMPLE_BYTES, size // 2 - SAMPLE_BYTES // 2)
    handle.seek(middle)
    digest.update(handle.read(SAMPLE_BYTES))
    handle.seek(max(0, size - SAMPLE_BYTES))
    digest.update(handle.read(SAMPLE_BYTES))
    return digest


def content_track_id(path, size=None):
    """Return the content id of one file, or an empty string when unreadable.

    An empty result is the caller's signal to fall back to path-based identity for
    that track (a file that cannot be opened cannot be fingerprinted, and refusing
    to index it would drop it from the library over a transient IO error).
    """
    if not isinstance(path, str) or not path:
        return ""
    try:
        stat = os.stat(path) if size is None else None
        total = int(stat.st_size) if stat is not None else int(size)
    except OSError:
        return ""
    if total < 0:
        return ""
    try:
        with open(path, "rb") as handle:
            digest = _sample_hasher(handle, total)
            return digest.hexdigest()[:ID_HEX_CHARS]
    except OSError:
        return ""


def cue_track_id(cue_path, track_no):
    """Identity of one cuesheet track: the sheet's content id plus its number."""
    sheet = content_track_id(cue_path)
    if not sheet:
        # The cuesheet itself could not be read; keep the old path-based rule so
        # the track does not disappear while the storage is temporarily away.
        sheet = hashlib.sha1(cue_path.encode("utf-8", "ignore")).hexdigest()[:ID_HEX_CHARS]
    return hashlib.sha1(("%s:%s" % (sheet, track_no)).encode("utf-8")).hexdigest()[:ID_HEX_CHARS]


def fallback_track_id(path):
    """Path-based id, kept only for files that cannot be read."""
    if not isinstance(path, str) or not path:
        return ""
    return hashlib.sha1(path.encode("utf-8", "ignore")).hexdigest()[:ID_HEX_CHARS]


__all__ = ["SAMPLE_BYTES", "ID_HEX_CHARS", "content_track_id", "cue_track_id", "fallback_track_id"]

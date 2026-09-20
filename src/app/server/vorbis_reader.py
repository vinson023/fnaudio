"""Bounded Vorbis comment file reader."""

from vorbis_comment_policy import parse_vorbis_comments

MAX_VORBIS_READ_BYTES = 1024 * 1024


def read_vorbis_comments(path):
    if not isinstance(path, str) or not path:
        return {}
    try:
        with open(path, "rb") as handle:
            data = handle.read(MAX_VORBIS_READ_BYTES)
    except OSError:
        return {}
    return parse_vorbis_comments(data)


__all__ = ["MAX_VORBIS_READ_BYTES", "read_vorbis_comments"]

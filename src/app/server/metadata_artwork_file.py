"""Bounded file access for persisted metadata artwork assets."""

from __future__ import annotations

import os


def open_bounded_artwork(path, maximum):
    """Return ``(handle, size)`` for a non-empty file within ``maximum``.

    The caller owns the returned handle.  Size is taken from that same open
    descriptor so a replacement between a separate stat and read cannot
    change which file is streamed.
    """
    if not isinstance(path, str) or not isinstance(maximum, int) or isinstance(maximum, bool) or maximum <= 0:
        return None
    handle = None
    try:
        handle = open(path, "rb")
        size = os.fstat(handle.fileno()).st_size
    except (OSError, TypeError, ValueError):
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass
        return None
    if size <= 0 or size > maximum:
        try:
            handle.close()
        except OSError:
            pass
        return None
    return handle, size


def read_bounded_artwork(path, maximum):
    """Read a bounded artwork file without materializing an oversized asset."""
    opened = open_bounded_artwork(path, maximum)
    if not opened:
        return b""
    handle, size = opened
    try:
        body = handle.read(size)
        # The file can be truncated after fstat() and before the read. Never
        # publish a short artwork payload as if it were the bounded asset.
        return body if len(body) == size else b""
    except (TypeError, ValueError):
        return b""
    except OSError:
        return b""
    finally:
        handle.close()


__all__ = ["open_bounded_artwork", "read_bounded_artwork"]

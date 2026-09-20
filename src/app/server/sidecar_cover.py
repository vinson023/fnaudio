"""Bounded sidecar artwork lookup for folder-level covers."""

import mimetypes
import os


MAX_SIDECAR_BYTES = 8 * 1024 * 1024
# Keep the lookup deterministic and bounded, but accept the common names used
# by desktop taggers/NAS music managers.  Folder artwork is local metadata and
# should be available immediately, without waiting for an external provider.
SIDECAR_NAMES = (
    "cover.jpg", "cover.jpeg", "cover.png", "cover.webp",
    "folder.jpg", "folder.jpeg", "folder.png", "folder.webp",
    "front.jpg", "front.jpeg", "front.png", "front.webp",
    "album.jpg", "album.jpeg", "album.png", "album.webp",
    "artwork.jpg", "artwork.jpeg", "artwork.png", "artwork.webp",
)


def _path_under(path, root):
    try:
        path = os.path.realpath(os.path.abspath(path))
        root = os.path.realpath(os.path.abspath(root))
        return os.path.commonpath([path, root]) == root
    except (OSError, ValueError):
        return False


def read_sidecar_cover(*paths):
    """Read the first bounded cover image adjacent to the supplied paths."""
    dirs = []
    for path in paths:
        if not isinstance(path, str) or not path:
            continue
        directory = os.path.dirname(path)
        if directory and directory not in dirs:
            dirs.append(directory)
    for directory in dirs:
        try:
            entries = {name.lower(): name for name in os.listdir(directory)}
        except OSError:
            continue
        for name in SIDECAR_NAMES:
            actual = entries.get(name)
            if not actual:
                continue
            target = os.path.join(directory, actual)
            if not _path_under(target, directory):
                continue
            try:
                if os.path.getsize(target) > MAX_SIDECAR_BYTES:
                    continue
                with open(target, "rb") as fh:
                    # The size check above is inherently racy (a writer may
                    # replace the file between stat and open). Keep the read
                    # bounded as well so a growing/replaced sidecar cannot
                    # create an unbounded allocation.
                    body = fh.read(MAX_SIDECAR_BYTES + 1)
                if len(body) > MAX_SIDECAR_BYTES:
                    continue
                mime = mimetypes.guess_type(target)[0] or ("image/png" if actual.lower().endswith(".png") else "image/jpeg")
                if body:
                    return mime, body
            except OSError:
                continue
    return None, None

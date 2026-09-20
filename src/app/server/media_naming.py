"""Pure naming rules shared by HTTP and DLNA media paths."""

from __future__ import annotations

import re


def safe_filename(value):
    # Tags and file basenames are expected to be text.  Do not stringify an
    # arbitrary object here: this helper is also used while answering DLNA
    # requests, and a hostile or malformed value could allocate a huge
    # representation before the filename length cap is applied.
    raw = value if isinstance(value, str) else ""
    name = re.sub(r'[\\/:*?"<>|]+', "_", raw.strip())
    return name[:120] or "track"


__all__ = ["safe_filename"]

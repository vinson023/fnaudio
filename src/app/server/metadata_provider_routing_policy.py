"""Pure provider routing helpers for metadata entity lookups."""

from __future__ import annotations

import re


def contains_cjk(*values):
    """Return whether bounded text values contain CJK characters.

    Non-text provider fields are deliberately ignored: routing must never
    stringify untrusted objects before an adapter starts.
    """
    text = " ".join(value.strip()[:512] for value in values if isinstance(value, str))
    return bool(re.search(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", text))


__all__ = ["contains_cjk"]

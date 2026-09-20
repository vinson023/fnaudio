"""Pure filename classification used by the library scanner."""

import os


def classify_filename(filename, supported):
    """Return ``cue``, ``audio`` or ``ignore`` without coercing input."""
    if not isinstance(filename, str) or not isinstance(supported, dict):
        return "ignore"
    try:
        extension = os.path.splitext(filename)[1].lower()
    except Exception:
        return "ignore"
    if extension == ".cue":
        return "cue"
    return "audio" if extension in supported else "ignore"


__all__ = ["classify_filename"]

"""Testable orchestration for probe and local tag resolution."""

from __future__ import annotations

import os

from metadata_probe_policy import merge_missing_tags, probe_tags_complete


def resolve_metadata_tags(path, probe_tags, probe_reader, id3_reader, vorbis_reader):
    """Resolve probe tags and use a native container reader only when needed."""
    if probe_tags:
        supplied = probe_tags
    else:
        try:
            supplied = probe_reader(path)
        except Exception:
            supplied = {}
    tags = merge_missing_tags(supplied, {})
    if probe_tags_complete(tags):
        return tags
    try:
        extension = os.path.splitext(path)[1].lower() if isinstance(path, str) else ""
    except (OSError, ValueError):
        extension = ""
    try:
        local_tags = id3_reader(path) if extension in (".mp3", ".dsf", ".dff", ".wav") else vorbis_reader(path)
    except Exception:
        local_tags = {}
    return merge_missing_tags(tags, local_tags)


__all__ = ["resolve_metadata_tags"]

"""Safe presentation projection for music-library root rows."""

from __future__ import annotations

from typing import Iterable, Mapping

from scan_numeric_policy import safe_counter

MAX_ROOT_PRESENTATION = 64
MAX_ROOT_TEXT = 4096


def project_root_rows(roots: Iterable[str], summaries: Mapping | None, matched_roots=None) -> list[dict]:
    """Build bounded root rows without trusting persisted summary values."""
    if not isinstance(summaries, Mapping):
        summaries = {}
    matched = matched_roots if isinstance(matched_roots, set) else None
    result = []
    try:
        iterator = iter(roots or ())
    except Exception:
        iterator = iter(())
    for _ in range(MAX_ROOT_PRESENTATION):
        try:
            root = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        if not isinstance(root, str) or not root or len(root) > MAX_ROOT_TEXT:
            continue
        if matched is not None and root not in matched:
            continue
        try:
            row = summaries.get(root)
        except Exception:
            row = None
        def value(name, default):
            if row is None:
                return default
            try:
                if isinstance(row, Mapping):
                    return row.get(name, default)
                return row[name]
            except Exception:
                return default
        raw_count = value("track_count", 0)
        cover = value("cover_track_id", "")
        if not isinstance(cover, str) or len(cover) > MAX_ROOT_TEXT:
            cover = ""
        result.append({
            "path": root,
            "root": root,
            "parent": "",
            "name": root.rstrip("/\\").rsplit("/", 1)[-1].rsplit("\\", 1)[-1] or root,
            "track_count": safe_counter(raw_count),
            "cover_track_id": cover,
        })
    return result

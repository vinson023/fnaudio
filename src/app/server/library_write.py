"""Pure preparation helpers for persisting a scanned library.

The SQLite writer still owns transactions and side effects; this module keeps
path/root canonicalisation deterministic and independently testable.
"""

from __future__ import annotations

from library_paths import bounded_library_path_text as _bounded_path

# Library configuration already caps the number of roots at 64.  Keep this
# preparation boundary bounded as well so a hostile/infinite iterator cannot
# be fully materialized before scanning begins.
MAX_ROOT_CANDIDATES = 64
MAX_SCAN_TEXT = 4096


def scan_text(value, limit=MAX_SCAN_TEXT):
    """Return bounded scanner text without invoking arbitrary conversions."""
    if not isinstance(value, str):
        return ""
    return value[:limit] if isinstance(limit, int) and limit > 0 else ""

def normalize_scan_items(items, roots, *, is_under, relative_folder, root_label):
    """Return canonical scan rows without mutating the caller's items.

    ``roots`` and the callbacks are injected so this boundary can be tested
    without a filesystem or SQLite connection.
    """
    normalized = []
    root_candidates = []
    try:
        root_iter = iter(roots or ())
    except Exception:
        root_iter = iter(())
    for _ in range(MAX_ROOT_CANDIDATES):
        try:
            root_candidates.append(next(root_iter))
        except StopIteration:
            break
        except Exception:
            break
    try:
        iterator = iter(items or [])
    except Exception:
        iterator = iter(())
    for item in iterator:
        try:
            source = dict(item or {})
        except Exception:
            continue
        path = _bounded_path(source.get("path"))
        root = ""
        for candidate in root_candidates:
            if not path:
                break
            try:
                if is_under(path, candidate):
                    root = candidate
                    break
            except Exception:
                continue
        cue_or_path = _bounded_path(source.get("cue_path")) or path
        folder = source.get("folder")
        if root:
            try:
                source["folder"] = relative_folder(cue_or_path, root)
            except Exception:
                source["folder"] = ""
            try:
                source["library_root"] = root_label(root)
            except Exception:
                source["library_root"] = ""
        else:
            source["folder"] = folder.strip() if isinstance(folder, str) else ""
            source["library_root"] = ""
        source["_index_root"] = root
        normalized.append(source)
    return normalized


def root_index_summary(items, roots=()):
    """Build a compact root-level count/cover summary from scan rows.

    The root browser needs just one count and one stable cover identity per
    configured root. Persisting this tiny summary avoids re-grouping every
    track on each root-page cache miss while retaining a simple SQLite
    fallback for pre-summary indexes.
    """
    summary = {}
    try:
        root_iter = iter(roots or ())
    except Exception:
        root_iter = iter(())
    for _ in range(MAX_ROOT_CANDIDATES):
        try:
            root = next(root_iter)
        except StopIteration:
            break
        except Exception:
            break
        if isinstance(root, str):
            summary[root] = {"track_count": 0, "cover_track_id": ""}
    try:
        item_iter = iter(items or ())
    except Exception:
        item_iter = iter(())
    for item in item_iter:
        if not isinstance(item, dict):
            continue
        root = item.get("_index_root")
        if not isinstance(root, str) or root not in summary:
            continue
        entry = summary[root]
        entry["track_count"] += 1
        track_id = item.get("id")
        if isinstance(track_id, str) and track_id and (not entry["cover_track_id"] or track_id < entry["cover_track_id"]):
            entry["cover_track_id"] = track_id
    return summary


def prepare_track_persistence(item, *, safe_int, safe_float, dumps):
    """Prepare the immutable SQLite track and optional CUE rows.

    Conversion functions are injected because the library module owns its
    compatibility rules for numeric values and JSON encoding.  No database or
    filesystem work occurs here.
    """
    source = dict(item or {})
    source.pop("_index_root", None)
    path = _bounded_path(source.get("path"))
    index_root = _bounded_path(item.get("_index_root")) if isinstance(item, dict) else ""
    track_row = (
        source.get("id", ""), path, index_root,
        _bounded_path(source.get("folder")), source.get("title", ""),
        source.get("artist", ""), source.get("album", ""), safe_int(source.get("track_no")),
        source.get("album_artist", ""), source.get("composer", ""), source.get("genre", ""),
        source.get("format", ""), source.get("mime", ""), 1 if source.get("is_dsd") else 0,
        safe_float(source.get("duration")), safe_int(source.get("size")),
        safe_int(source.get("sample_rate")), safe_int(source.get("bit_depth")),
        safe_int(source.get("bitrate")), safe_int(source.get("added")), safe_int(source.get("added_ns")),
        safe_int(source.get("modified")), safe_int(source.get("modified_ns")),
        _bounded_path(source.get("cue_path")), 1 if source.get("cue_track") else 0,
        safe_float(source.get("cue_start")), safe_float(source.get("cue_end")),
        safe_int(source.get("metadata_version")), dumps(source),
    )
    cue_row = None
    if source.get("cue_track"):
        cue_row = (
            source.get("id", ""), _bounded_path(source.get("cue_path")), path,
            safe_int(source.get("track_no")), safe_float(source.get("cue_start")),
            safe_float(source.get("cue_end")),
        )
    return track_row, cue_row, path, source


def iter_track_persistence_batches(items, batch_size, *, prepare):
    """Yield prepared persistence rows in bounded input order batches.

    The scanner already owns the normalized item list, but building a second
    full list of JSON rows, CUE rows and cover rows doubles peak memory on a
    large library.  This small adapter lets the SQLite writer use
    ``executemany`` without re-materialising the entire scan result.
    """
    if isinstance(batch_size, bool) or not isinstance(batch_size, int):
        return
    if not callable(prepare):
        return
    size = max(1, batch_size)
    batch = []
    try:
        iterator = iter(items or ())
    except Exception:
        iterator = iter(())
    for item in iterator:
        try:
            prepared = prepare(item)
        except Exception:
            continue
        batch.append(prepared)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch

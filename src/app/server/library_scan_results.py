"""Pure finalization helpers for multi-root library scans.

Filesystem walking and metadata probing stay in ``library.py``; this module
keeps de-duplication, deterministic ordering, and signature aggregation
isolated so those policies can be regression-tested without touching disk.
"""

import hashlib


_MAX_SIGNATURES = 200_000
_MAX_SIGNATURE_LENGTH = 4096
_MAX_SORT_TEXT_LENGTH = 4096
_MAX_ID_LENGTH = 4096
_MAX_SORT_ITEMS = 200_000
_MAX_PREVIOUS_ITEMS = 200_000
_MAX_ROOTS = 64
_MAX_PATH_LENGTH = 4096
_MAX_SIGNATURE_TOTAL_LENGTH = 8 * 1024 * 1024


def _text(value):
    return value if isinstance(value, str) else ""


def build_previous_item_index(items):
    """Build a reusable path index while isolating malformed cache entries."""
    previous = {}
    try:
        item_iter = iter(items or ())
    except Exception:
        item_iter = iter(())
    for _ in range(_MAX_SORT_ITEMS):
        try:
            item = next(item_iter)
        except StopIteration:
            break
        except Exception:
            break
        if not isinstance(item, dict):
            continue
        try:
            path = item.get("path")
        except Exception:
            continue
        if isinstance(path, str) and path and len(path) <= _MAX_PATH_LENGTH:
            previous[path] = item
    return previous


def digest_signature_parts(parts):
    """Return a bounded deterministic digest for filesystem signature parts."""
    try:
        part_iter = iter(parts or ())
    except Exception:
        part_iter = iter(())
    normalized_values = []
    total_length = 0
    while len(normalized_values) < _MAX_SIGNATURES:
        try:
            value = next(part_iter)
        except StopIteration:
            break
        except Exception:
            break
        if isinstance(value, str):
            bounded = value[:_MAX_SIGNATURE_LENGTH]
            if total_length + len(bounded) > _MAX_SIGNATURE_TOTAL_LENGTH:
                remaining = _MAX_SIGNATURE_TOTAL_LENGTH - total_length
                if remaining <= 0:
                    break
                bounded = bounded[:remaining]
            normalized_values.append(bounded)
            total_length += len(bounded)
            if total_length >= _MAX_SIGNATURE_TOTAL_LENGTH:
                break
    normalized = sorted(normalized_values)
    return hashlib.sha1("|".join(normalized).encode("utf-8", "ignore")).hexdigest()


def _sort_key(item):
    if not isinstance(item, dict):
        return ("", "", "", "")
    values = []
    for field in ("artist", "album", "title", "id"):
        try:
            value = item.get(field)
        except Exception:
            value = ""
        values.append(_text(value)[:_MAX_SORT_TEXT_LENGTH].casefold())
    return tuple(values)


def sort_scan_items(items):
    """Return scan records in deterministic order without mutating input."""
    item_list = []
    try:
        iterator = iter(items or ())
    except Exception:
        iterator = iter(())
    for _ in range(_MAX_SORT_ITEMS):
        try:
            item_list.append(next(iterator))
        except StopIteration:
            break
        except Exception:
            break
    try:
        return sorted(item_list, key=_sort_key)
    except Exception:
        return item_list


def finalize_scan_results(items, signatures):
    """Return unique, deterministic items and the aggregate scan signature."""
    unique = []
    seen = set()
    try:
        item_iter = iter(items or ())
    except Exception:
        item_iter = iter(())
    for _ in range(_MAX_PREVIOUS_ITEMS):
        try:
            item = next(item_iter)
        except StopIteration:
            break
        except Exception:
            break
        if not isinstance(item, dict):
            continue
        try:
            item_id = item.get("id")
        except Exception:
            continue
        if isinstance(item_id, str) and len(item_id) > _MAX_ID_LENGTH:
            continue
        try:
            hash(item_id)
        except Exception:
            continue
        try:
            already_seen = item_id in seen
        except Exception:
            continue
        if already_seen:
            continue
        try:
            seen.add(item_id)
        except Exception:
            continue
        unique.append(item)
        if len(unique) >= _MAX_SORT_ITEMS:
            break
    unique = sort_scan_items(unique)
    return unique, digest_signature_parts(signatures)


def partition_previous_items(items, roots, path_under):
    """Partition reusable scan records by configured root without coercion."""
    root_list = []
    try:
        root_iter = iter(roots or ())
    except Exception:
        root_iter = iter(())
    for _ in range(_MAX_ROOTS):
        try:
            root = next(root_iter)
        except StopIteration:
            break
        except Exception:
            break
        if isinstance(root, str) and root and len(root) <= _MAX_PATH_LENGTH:
            root_list.append(root)
    buckets = [[] for _ in root_list]
    path_indexes = {}
    try:
        item_iter = iter(items or ())
    except Exception:
        item_iter = iter(())
    for _ in range(_MAX_PREVIOUS_ITEMS):
        try:
            item = next(item_iter)
        except StopIteration:
            break
        except Exception:
            break
        if not isinstance(item, dict):
            continue
        try:
            path = item.get("path")
        except Exception:
            continue
        if not isinstance(path, str) or not path or len(path) > _MAX_PATH_LENGTH:
            continue
        if path in path_indexes:
            index = path_indexes[path]
            if index >= 0:
                buckets[index].append(item)
            continue
        index = -1
        for candidate_index, root in enumerate(root_list):
            try:
                if path_under(path, root):
                    index = candidate_index
                    break
            except Exception:
                continue
        path_indexes[path] = index
        if index >= 0:
            buckets[index].append(item)
    return buckets

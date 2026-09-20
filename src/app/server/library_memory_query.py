"""Pure helpers for the in-memory library query fallback."""

from __future__ import annotations

import random
import heapq

MAX_MEMORY_ITEMS = 200000
MAX_MEMORY_ROOTS = 64
MAX_MEMORY_SEARCH_TEXT = 4096


def _page_bound(value, default=0):
    """Accept only ordinary finite integer page values."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    try:
        if isinstance(value, float) and not value.is_integer():
            return default
        return max(0, min(MAX_MEMORY_ITEMS, int(value)))
    except (OverflowError, TypeError, ValueError):
        return default


def memory_field(item, key, default=None):
    if not isinstance(item, dict) or not isinstance(key, str):
        return default
    try:
        return item.get(key, default)
    except Exception:
        return default


def bounded_memory_items(items):
    """Materialize at most the bounded window used by fallback queries."""
    result = []
    try:
        iterator = iter(items)
    except Exception:
        return result
    for _ in range(MAX_MEMORY_ITEMS):
        try:
            item = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        result.append(item)
    return result


def bounded_memory_roots(roots):
    """Materialize a small, replayable root set for per-item matching."""
    result = []
    try:
        iterator = iter(roots)
    except Exception:
        return result
    for _ in range(MAX_MEMORY_ROOTS):
        try:
            candidate = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        if isinstance(candidate, str):
            result.append(candidate)
    return result


def bounded_random_memory_sample(items, size=100, randrange=None):
    """Draw a fixed-size sample without copying the complete fallback cache."""
    if isinstance(size, bool) or not isinstance(size, int):
        size = 100
    size = max(0, min(100, size))
    if size == 0:
        return []
    choose = randrange if callable(randrange) else random.randrange
    sample = []
    try:
        iterator = iter(items)
    except Exception:
        return sample
    for index in range(MAX_MEMORY_ITEMS):
        try:
            item = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        if len(sample) < size:
            sample.append(item)
            continue
        try:
            replacement = choose(index + 1)
        except Exception:
            replacement = index
        if isinstance(replacement, int) and not isinstance(replacement, bool) and 0 <= replacement < size:
            sample[replacement] = item
    return sample


def memory_text(value):
    """Project a legacy cached value to bounded display text."""
    if isinstance(value, str):
        return value[:4096]
    if value is None:
        return ""
    return ""


def memory_item_root(item, roots, path_under):
    if not isinstance(item, dict):
        return ""
    path = memory_text(memory_field(item, "cue_path") or memory_field(item, "path"))
    try:
        iterator = iter(roots)
    except Exception:
        return ""
    for _ in range(MAX_MEMORY_ROOTS):
        try:
            candidate = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        if not isinstance(candidate, str):
            continue
        try:
            if path and path_under(path, candidate):
                return candidate
        except Exception:
            continue
    return ""


def memory_matches_search(item, search):
    if not isinstance(search, str):
        return True
    search = search[:4096].lower()
    if not search or not isinstance(item, dict):
        return True
    parts = []
    remaining = MAX_MEMORY_SEARCH_TEXT
    for key in ("title", "artist", "album", "album_artist", "composer", "genre", "folder", "path", "format"):
        if remaining <= 0:
            break
        value = memory_text(memory_field(item, key)).lower()
        if parts:
            remaining -= 1
            if remaining <= 0:
                break
        value = value[:remaining]
        parts.append(value)
        remaining -= len(value)
    haystack = " ".join(parts)
    return search in haystack


def memory_sort_key(item, sort_key, safe_int):
    if not isinstance(item, dict):
        item = {}
    if sort_key == "artist":
        return memory_text(memory_field(item, "artist")).lower()
    if sort_key == "album":
        return memory_text(memory_field(item, "album")).lower()
    if sort_key == "format":
        return memory_text(memory_field(item, "format")).lower()
    if sort_key == "added":
        try:
            primary = safe_int(memory_field(item, "added_ns"))
        except Exception:
            primary = 0
        try:
            fallback = safe_int(memory_field(item, "added"))
        except Exception:
            fallback = 0
        return primary or fallback
    if sort_key == "track_no":
        try:
            value = safe_int(memory_field(item, "track_no"))
        except Exception:
            value = 0
        return value or 2147483647
    return memory_text(memory_field(item, "title")).lower()


class _DescendingMemoryKey:
    """Reverse only the primary key while keeping SQL tie-breakers ascending."""

    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        if not isinstance(other, _DescendingMemoryKey):
            return NotImplemented
        return self.value > other.value

    def __eq__(self, other):
        return isinstance(other, _DescendingMemoryKey) and self.value == other.value


def memory_page_sort_key(item, page_query, safe_int):
    """Mirror SQLite's primary-sort/title/id ordering for fallback pages."""
    primary = memory_sort_key(item, page_query.sort_key, safe_int)
    title = memory_text(memory_field(item, "title")).lower()
    item_id = memory_text(memory_field(item, "id"))
    if page_query.sort_dir == "desc":
        primary = _DescendingMemoryKey(primary)
    return primary, title, item_id


def iter_filtered_memory_items(items, page_query, roots, unclassified, path_under):
    """Yield bounded fallback matches without constructing a second full list."""
    try:
        iterator = iter(items)
    except Exception:
        return
    # The same root set is consulted for every item.  Normalize one-shot
    # iterables once so a generator cannot be exhausted by the first row.
    roots = bounded_memory_roots(roots)
    view, group, album = page_query.view, page_query.group, page_query.album
    folder, root, search = page_query.folder, page_query.root, page_query.search
    # Apply all predicates while consuming the bounded iterator.  Do not first
    # materialize every valid item and then allocate a second full-size list.
    for _ in range(MAX_MEMORY_ITEMS):
        try:
            item = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        if not isinstance(item, dict):
            continue
        matches = True
        if view == "dsd":
            matches = memory_field(item, "is_dsd") is True
        elif view in ("albums", "artists", "composers", "genres") and group:
            matches = (memory_text(memory_field(item, page_query.group_column)) or unclassified) == group
        elif view == "folders":
            if root:
                matches = memory_item_root(item, roots, path_under) == root
            if matches and folder:
                matches = memory_text(memory_field(item, "folder")) == folder
        if matches and view in ("artists", "composers") and group and album:
            matches = (memory_text(memory_field(item, "album")) or unclassified) == album
        if matches and not memory_matches_search(item, search):
            matches = False
        if matches:
            yield item


def filter_sort_memory_items(items, page_query, roots, unclassified, path_under, safe_int):
    """Apply fallback view filters and deterministic ordering."""
    filtered = list(iter_filtered_memory_items(items, page_query, roots, unclassified, path_under))
    filtered.sort(key=lambda item: memory_page_sort_key(item, page_query, safe_int))
    return filtered


def filter_memory_page(items, page_query, roots, unclassified, path_under, safe_int):
    """Return one ordered fallback window without sorting every cached item."""
    if not isinstance(items, (list, tuple)):
        filtered = filter_sort_memory_items(items, page_query, roots, unclassified, path_under, safe_int)
        offset = _page_bound(getattr(page_query, "offset", 0))
        limit = _page_bound(getattr(page_query, "limit", 0))
        return filtered[offset:offset + limit], len(filtered)
    try:
        offset = _page_bound(page_query.offset)
        limit = _page_bound(page_query.limit)
    except AttributeError:
        offset, limit = 0, 0
    if not limit:
        count = sum(1 for _ in iter_filtered_memory_items(items, page_query, roots, unclassified, path_under))
        return [], count
    window = min(MAX_MEMORY_ITEMS, offset + limit)
    count_box = [0]

    def counted_matches():
        for item in iter_filtered_memory_items(items, page_query, roots, unclassified, path_under):
            count_box[0] += 1
            yield item

    key = lambda item: memory_page_sort_key(item, page_query, safe_int)
    selected = heapq.nsmallest(window, counted_matches(), key=key)
    selected.sort(key=key)
    return selected[offset:offset + limit], count_box[0]

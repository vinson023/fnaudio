"""Stable, path-safe library API representations.

HTTP handlers may use the result directly, but this module deliberately has
no server/global state dependency so privacy and cache URL rules stay testable.
"""

from collections.abc import Mapping

from cover_cache import cover_is_known_missing, cover_source_version, thumbnail_asset_id_for_item
from metadata_artwork_policy import artwork_url


MAX_PUBLIC_PAGE_ITEMS = 500
MAX_PUBLIC_PAGE_FIELDS = 32
MAX_PUBLIC_ITEM_FIELDS = 128
_REQUIRED_PAGE_FIELDS = ("items", "count", "total", "limit", "offset", "paged", "fallback", "next_cursor", "has_more")


def _bounded_page_copy(page):
    if not isinstance(page, Mapping):
        return {}
    result = {}
    try:
        iterator = iter(page.items())
    except Exception:
        return result
    for _ in range(MAX_PUBLIC_PAGE_FIELDS):
        try:
            key, value = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        if isinstance(key, str) and len(key) <= 80:
            result[key] = value
    # Some adapters append the actual page payload after diagnostic fields.
    # Read only the small, known pagination contract keys directly so an
    # early diagnostic prefix cannot hide ``items``; never materialize the
    # complete mapping.
    for key in _REQUIRED_PAGE_FIELDS:
        if key in result:
            continue
        try:
            value = page[key]
        except (KeyError, IndexError, TypeError, AttributeError):
            continue
        except Exception:
            continue
        result[key] = value
    return result


def public_library_item(item, config=None, allow_cover_disk_lookup=True):
    """Return a client-safe track record without the filesystem path."""
    source = item if isinstance(item, Mapping) else {}
    try:
        raw_metadata_artwork_id = source.get("metadata_artwork_id")
        confirmed_artwork = source.get("metadata_artwork_confirmed") is True
    except Exception:
        raw_metadata_artwork_id = ""
        confirmed_artwork = False
    result = {}
    try:
        iterator = iter(source.items())
    except Exception:
        iterator = iter(())
    for _ in range(MAX_PUBLIC_ITEM_FIELDS):
        try:
            key, value = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        # Do not copy bulky/internal fields only to remove them below.  Large
        # legacy rows may still carry item_json or full cached lyrics; keeping
        # those values out of the temporary projection reduces first-page
        # allocations and JSON work on cold WebViews.
        if isinstance(key, str) and key not in ("path", "item_json", "lyrics", "metadata_artwork_id", "metadata_artwork_confirmed") and len(key) <= 80:
            result[key] = value
    result.pop("path", None)
    try:
        raw_id = source.get("id")
    except Exception:
        raw_id = ""
    item_id = raw_id if isinstance(raw_id, str) else ""
    result["url"] = "media/" + item_id
    result["cover_url"] = "" if not item_id else (
        "" if cover_is_known_missing(source, config or {}, 160, allow_disk=allow_cover_disk_lookup)
        else "cover/%s?v=%s" % (item_id, cover_source_version(source, allow_disk=allow_cover_disk_lookup))
    )
    asset_id = thumbnail_asset_id_for_item(
        source, config or {}, 160, allow_disk=allow_cover_disk_lookup,
    ) if item_id else ""
    result["cover_thumbnail_url"] = ("cover-asset/%s?size=160" % asset_id) if asset_id else ""
    # Metadata artwork is stored independently from the media-file cover
    # cache. Automatic enrichment keeps an existing media thumbnail; an
    # explicit, persisted choice must also replace an older generated image.
    metadata_artwork_id = raw_metadata_artwork_id
    metadata_url = artwork_url(metadata_artwork_id)
    if confirmed_artwork and metadata_url:
        result["cover_url"] = metadata_url
        result["cover_thumbnail_url"] = ""
    elif not result["cover_thumbnail_url"]:
        result["cover_url"] = metadata_url or result["cover_url"]
    # Lyrics are fetched on demand from `/api/lyrics` for the active song.
    # Sending cached full LRC bodies for every row makes an otherwise compact
    # library page balloon after metadata enrichment, delaying first paint and
    # JSON parsing on older WebViews. `item_json` and the raw artwork cache ID
    # are implementation details as well: the public cover URL above is the
    # only representation the client needs.
    result.pop("lyrics", None)
    result.pop("item_json", None)
    result.pop("metadata_artwork_id", None)
    return result


def public_library_page(page, config=None, limit=MAX_PUBLIC_PAGE_ITEMS):
    """Project a paged library response without trusting its item iterable."""
    source = _bounded_page_copy(page)
    if isinstance(limit, bool) or not isinstance(limit, int):
        limit = MAX_PUBLIC_PAGE_ITEMS
    limit = max(0, min(MAX_PUBLIC_PAGE_ITEMS, limit))
    raw_items = source.get("items")
    result = []
    try:
        iterator = iter(raw_items if isinstance(raw_items, (list, tuple)) else ())
    except Exception:
        iterator = iter(())
    scanned = 0
    while len(result) < limit and scanned < max(limit * 2, limit):
        scanned += 1
        try:
            item = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        if not isinstance(item, Mapping):
            continue
        try:
            # Do not synchronously probe a thumbnail alias and a missing
            # marker for every row while serializing a cold library page.
            # The cover prewarm worker has already been scheduled by the
            # route; cached aliases remain instant, while unknown rows use
            # the normal versioned cover endpoint after the first list paint.
            result.append(public_library_item(item, config, allow_cover_disk_lookup=False))
        except Exception:
            continue
    source["items"] = result
    return source


__all__ = ["MAX_PUBLIC_ITEM_FIELDS", "MAX_PUBLIC_PAGE_FIELDS", "MAX_PUBLIC_PAGE_ITEMS", "public_library_item", "public_library_page"]

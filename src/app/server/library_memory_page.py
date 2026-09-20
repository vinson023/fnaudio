"""Pure projection for the bounded in-memory library fallback page."""

from library_memory_query import bounded_random_memory_sample, filter_memory_page


def build_memory_library_page(
    items,
    page_query,
    roots,
    unclassified,
    path_under,
    safe_int,
    shuffle=None,
    randrange=None,
):
    """Filter, sort and window a memory-library view without config/global state."""
    source_items = items
    if getattr(page_query, "view", "") == "random100":
        source_items = bounded_random_memory_sample(items, 100, randrange)
        if callable(shuffle):
            shuffle(source_items)
    page_items, count = filter_memory_page(
        source_items, page_query, roots, unclassified, path_under, safe_int
    )
    return {
        "items": page_items,
        "count": count,
        "limit": page_query.limit,
        "offset": page_query.offset,
        "paged": True,
        "fallback": "memory",
    }


__all__ = ["build_memory_library_page"]

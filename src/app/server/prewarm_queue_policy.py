"""Pure ordering/deduplication policy for deferred thumbnail work."""

from __future__ import annotations


def bounded_unique_items(items, limit, key):
    result = []
    seen = set()
    total = 0
    maximum = max(0, int(limit))
    source = () if items is None else items
    try:
        source_length = len(source)
    except (TypeError, AttributeError):
        source_length = None
    if maximum == 0 and source_length is not None:
        return [], max(0, source_length)
    for item in source:
        total += 1
        # Once every admissible slot is filled, the rest are necessarily
        # dropped.  Do not keep calculating identities or grow ``seen`` for
        # a very large scan merely to report that pressure counter.
        if len(result) >= maximum:
            continue
        identity = key(item)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(item)
        if len(result) >= maximum and source_length is not None:
            total = source_length
            break
    return result, max(0, total - len(result))

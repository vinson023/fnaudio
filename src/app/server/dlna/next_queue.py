"""Bounded state policy for renderer-owned UPnP NextURI hints."""

from __future__ import annotations


MAX_NEXT_QUEUE_ENTRIES = 64
MAX_NEXT_URI_CHARS = 8192
MAX_NEXT_METADATA_CHARS = 256 * 1024


def _valid_entry(value):
    if not isinstance(value, dict):
        return None
    try:
        uri = value.get("uri")
        metadata = value.get("metadata", "")
    except Exception:
        return None
    if not isinstance(uri, str) or not uri or len(uri) > MAX_NEXT_URI_CHARS:
        return None
    if not isinstance(metadata, str) or len(metadata) > MAX_NEXT_METADATA_CHARS:
        return None
    return {"uri": uri, "metadata": metadata}


def bounded_next_queue(entries, uri, metadata, limit=MAX_NEXT_QUEUE_ENTRIES):
    """Return a safe FIFO queue and whether the requested entry was accepted.

    UPnP exposes a single NextURI field, but some controllers pipeline many
    SetNextAVTransportURI calls. Preserve the existing FIFO behavior while
    refusing excess/untrusted payloads before they become retained renderer
    state. An empty URI retains the standard "clear next URI" meaning.
    """
    if isinstance(limit, bool) or not isinstance(limit, int):
        limit = MAX_NEXT_QUEUE_ENTRIES
    limit = max(1, min(MAX_NEXT_QUEUE_ENTRIES, limit))
    queue = []
    try:
        iterator = iter(entries)
    except Exception:
        iterator = iter(())
    for _ in range(limit):
        try:
            item = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        entry = _valid_entry(item)
        if entry:
            queue.append(entry)
    if uri == "":
        return queue[:0], True
    if not isinstance(uri, str) or not uri or len(uri) > MAX_NEXT_URI_CHARS:
        return queue, False
    if not isinstance(metadata, str) or len(metadata) > MAX_NEXT_METADATA_CHARS:
        return queue, False
    if len(queue) >= limit:
        return queue, False
    queue.append({"uri": uri, "metadata": metadata})
    return queue, True


__all__ = [
    "MAX_NEXT_METADATA_CHARS",
    "MAX_NEXT_QUEUE_ENTRIES",
    "MAX_NEXT_URI_CHARS",
    "bounded_next_queue",
]

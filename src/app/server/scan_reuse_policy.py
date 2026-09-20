"""Pure cache-reuse policy for incremental library scans."""

from __future__ import annotations


def can_reuse_cached_item(cached, size, modified_ns, metadata_version):
    if not isinstance(cached, dict):
        return False
    return (
        cached.get("size") == size
        and cached.get("modified_ns") == modified_ns
        and cached.get("metadata_version") == metadata_version
    )

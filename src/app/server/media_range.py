"""Pure HTTP byte-range parsing for media responses."""

from __future__ import annotations


def parse_single_byte_range(size, header=""):
    if isinstance(size, bool) or not isinstance(size, int):
        raise ValueError("invalid resource size")
    if size <= 0:
        return 200, 0, -1
    if header is None:
        value = ""
    elif isinstance(header, str):
        value = header.strip()
    else:
        raise ValueError("invalid byte range")
    if not value:
        return 200, 0, size - 1
    if not value.lower().startswith("bytes=") or "," in value:
        raise ValueError("unsupported byte range")
    spec = value[6:].strip()
    left, separator, right = spec.partition("-")
    if not separator or (not left and not right):
        raise ValueError("invalid byte range")
    try:
        if left:
            start = int(left)
            end = int(right) if right else size - 1
        else:
            suffix = int(right)
            if suffix <= 0:
                raise ValueError("invalid byte range")
            start = max(0, size - suffix)
            end = size - 1
    except (TypeError, ValueError):
        raise ValueError("invalid byte range")
    end = min(end, size - 1)
    if start < 0 or start >= size or start > end:
        raise ValueError("unsatisfiable byte range")
    return 206, start, end


__all__ = ["parse_single_byte_range"]

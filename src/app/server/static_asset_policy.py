"""Pure, bounded policy for serving packaged UI assets."""

MAX_STATIC_ASSET_BYTES = 16 * 1024 * 1024
STATIC_ASSET_IMMUTABLE_MAX_AGE = 30 * 24 * 60 * 60
_IMMUTABLE_EXTENSIONS = frozenset((
    ".css", ".gif", ".ico", ".jpeg", ".jpg", ".js", ".png", ".svg",
    ".webp", ".woff", ".woff2",
))


def static_asset_size_allowed(size, limit=MAX_STATIC_ASSET_BYTES):
    """Return whether a regular static asset can be served safely."""
    if isinstance(size, bool) or not isinstance(size, int):
        return False
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        return False
    return 0 <= size <= limit


def static_asset_etag(size, mtime_ns):
    """Build a cheap weak validator from the stat values of a static file."""
    if (isinstance(size, bool) or not isinstance(size, int) or size < 0
            or isinstance(mtime_ns, bool) or not isinstance(mtime_ns, int) or mtime_ns < 0):
        return None
    # Stat metadata avoids rereading packaged assets, but equal timestamp and
    # size do not prove byte-for-byte equality. Mark the validator weak so its
    # HTTP semantics match what the server can actually establish.
    return 'W/"static-%x-%x"' % (mtime_ns, size)


def static_asset_cache_control(relative_path, versioned=False):
    """Return cache headers that keep entry HTML deployable without reloading assets."""
    if not isinstance(relative_path, str):
        return "no-cache"
    suffix = relative_path.rsplit(".", 1)[-1].lower() if "." in relative_path else ""
    if versioned and ("." + suffix) in _IMMUTABLE_EXTENSIONS:
        return "public, max-age=%s, immutable" % STATIC_ASSET_IMMUTABLE_MAX_AGE
    return "no-cache"


def static_asset_etag_matches(header_value, etag):
    """Return whether an If-None-Match value matches a generated ETag."""
    if not isinstance(header_value, str) or not isinstance(etag, str):
        return False
    expected = etag[2:] if etag.startswith("W/") else etag
    if not expected.startswith('"') or not expected.endswith('"'):
        return False
    for candidate in header_value.split(","):
        candidate = candidate.strip()
        if candidate.startswith("W/"):
            candidate = candidate[2:]
        if candidate == "*" or candidate == expected:
            return True
    return False


__all__ = [
    "MAX_STATIC_ASSET_BYTES",
    "STATIC_ASSET_IMMUTABLE_MAX_AGE",
    "static_asset_cache_control",
    "static_asset_etag",
    "static_asset_etag_matches",
    "static_asset_size_allowed",
]

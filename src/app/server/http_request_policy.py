"""Bounded, side-effect-free HTTP observation policy.

This module deliberately accepts only ordinary request primitives. Request
classification feeds fixed diagnostics buckets and must not stringify custom
objects supplied by a caller before an HTTP handler has validated them.
"""

HTTP_LATENCY_ROUTES = (
    "library_page",
    "library_groups",
    "library_folders",
    "library_roots",
    "cover",
    "playback",
    "static",
    "other",
)
MAX_REQUEST_PATH = 8192
MAX_REQUEST_TARGET = 16384
MAX_REQUEST_BODY_BYTES = 2 * 1024 * 1024


def request_body_length(value, maximum=MAX_REQUEST_BODY_BYTES):
    """Parse Content-Length without coercing attacker-controlled objects.

    Returns ``None`` for malformed/negative values and the bounded integer for
    valid values.  A value above ``maximum`` is returned as ``maximum + 1`` so
    callers can emit a deterministic 413 without allocating or reading it.
    """
    if not isinstance(value, str):
        return 0 if value is None else None
    text = value.strip()
    if not text or not text.isdigit():
        return None
    try:
        number = int(text, 10)
    except (TypeError, ValueError, OverflowError):
        return None
    if number < 0:
        return None
    try:
        limit = int(maximum)
    except (TypeError, ValueError, OverflowError):
        limit = MAX_REQUEST_BODY_BYTES
    if limit < 0:
        limit = MAX_REQUEST_BODY_BYTES
    return number if number <= limit else limit + 1


def request_path(value):
    """Return the path component only for an already-decoded text request."""
    if not isinstance(value, str):
        return ""
    return value.split("?", 1)[0][:MAX_REQUEST_PATH]


def request_target_allowed(value, maximum=MAX_REQUEST_TARGET):
    """Reject oversized request targets before query parsing allocates work."""
    if not isinstance(value, str):
        return False
    try:
        limit = int(maximum)
    except (TypeError, ValueError, OverflowError):
        limit = MAX_REQUEST_TARGET
    return 0 <= limit <= MAX_REQUEST_TARGET and len(value) <= limit


def http_latency_route(path):
    """Return a fixed metric route without retaining user-controlled values."""
    path = request_path(path)
    if path in ("/api/library", "/api/library/items"):
        return "library_page"
    if path == "/api/library/groups":
        return "library_groups"
    if path == "/api/library/folders":
        return "library_folders"
    if path == "/api/library/roots":
        return "library_roots"
    if path.startswith(("/cover/", "/cover-asset/", "/upnp/cover/", "/metadata/artwork/")):
        return "cover"
    if path.startswith(("/api/playback", "/api/player", "/api/dac", "/api/upnp", "/api/airplay")):
        return "playback"
    if path.startswith(("/api/", "/dlna/", "/media/", "/upnp/media/")):
        return "other"
    return "static"


def should_write_http_request(method, path, status):
    """Decide whether a request needs a synchronous structured-log entry."""
    route = request_path(path)
    method = method.upper() if isinstance(method, str) else ""
    status = status if isinstance(status, int) and not isinstance(status, bool) else 0
    if status >= 400 or method not in ("GET", "HEAD"):
        return True
    # Playback status is polled frequently by every visible client. Its
    # aggregate counters/latency remain available, while successful request
    # bodies are intentionally kept out of synchronous JSONL logging.
    if route in ("/api/playback/status", "/api/playback/events"):
        return False
    return route.startswith("/api/")

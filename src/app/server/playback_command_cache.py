"""Bounded, defensive storage helpers for playback command idempotency."""


def cached_result(cache, command_id, now):
    """Prune expired entries and return a defensive ``(response, status)`` copy."""
    if not isinstance(cache, dict) or not isinstance(command_id, str):
        return None
    expired = []
    for key, value in tuple(cache.items()):
        try:
            if not isinstance(value, tuple) or len(value) != 3 or value[0] <= now:
                expired.append(key)
        except Exception:
            expired.append(key)
    for key in expired:
        cache.pop(key, None)
    value = cache.get(command_id)
    if not isinstance(value, tuple) or len(value) != 3:
        return None
    _, response, status = value
    if not isinstance(response, dict) or not isinstance(status, int):
        cache.pop(command_id, None)
        return None
    return dict(response), status


def store_result(cache, command_id, response, status, expires_at, limit):
    """Store one result and evict oldest insertion-order keys above ``limit``."""
    if not isinstance(cache, dict) or not isinstance(command_id, str) or not isinstance(response, dict):
        return
    if not isinstance(status, int) or isinstance(status, bool):
        return
    try:
        limit = int(limit)
    except (TypeError, ValueError, OverflowError):
        limit = 1
    limit = max(1, min(limit, 4096))
    cache[command_id] = (expires_at, dict(response), status)
    while len(cache) > limit:
        try:
            cache.pop(next(iter(cache)))
        except (StopIteration, RuntimeError):
            break


def cache_snapshot(cache, limit):
    """Return a privacy-safe bounded pressure summary for diagnostics."""
    try:
        limit = int(limit)
    except (TypeError, ValueError, OverflowError):
        limit = 1
    limit = max(1, min(limit, 4096))
    entries = len(cache) if isinstance(cache, dict) else 0
    entries = max(0, min(entries if isinstance(entries, int) else 0, limit))
    return {"entries": entries, "limit": limit, "saturated": entries >= limit}

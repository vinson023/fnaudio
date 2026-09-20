"""Small, dependency-free bounds for untrusted metadata-provider payloads."""

MAX_PROVIDER_CANDIDATES = 64
_DISPLAY_FIELDS = ("title", "artist", "album", "album_artist", "image_url", "lyrics")


def candidate_text_is_corrupt(value):
    """Return whether bounded provider text contains Unicode replacement data."""
    return isinstance(value, str) and "\ufffd" in value


def candidate_has_displayable_fields(value):
    """Return whether a provider object contains visible metadata content."""
    if not isinstance(value, dict):
        return False
    if any(candidate_text_is_corrupt(value.get(key)) for key in _DISPLAY_FIELDS):
        return False
    return bool(any(isinstance(value.get(key), str) and value.get(key).strip() for key in _DISPLAY_FIELDS))


def candidate_mappings(values, limit=MAX_PROVIDER_CANDIDATES):
    """Return at most ``limit`` mapping candidates without trusting the payload.

    Provider JSON normally produces lists, but a malformed response, mock, or
    future adapter must not turn a metadata worker into an unbounded iterator.
    Only mappings are useful to the scoring layer, so discard everything else.
    """
    if isinstance(limit, bool):
        limit = MAX_PROVIDER_CANDIDATES
    try:
        limit = int(limit)
    except (TypeError, ValueError, OverflowError):
        limit = MAX_PROVIDER_CANDIDATES
    limit = max(0, min(MAX_PROVIDER_CANDIDATES, limit))
    if limit == 0 or not isinstance(values, (list, tuple)):
        return ()
    result = []
    try:
        for value in values:
            if isinstance(value, dict):
                result.append(value)
                if len(result) >= limit:
                    break
    except (RuntimeError, TypeError, ValueError):
        # Treat a hostile/custom sequence exactly like an unavailable provider.
        return tuple(result)
    return tuple(result)


def candidate_payload_is_sequence(values):
    """Return whether a provider candidate payload has the expected shape.

    Candidate adapters are list-oriented. A mapping here is normally a
    provider schema/error response, not one song. Keeping this decision
    separate from ``candidate_mappings`` preserves its tolerant consumer
    contract while letting the worker classify shape drift as retryable and
    continue with fallback providers.
    """
    return isinstance(values, (list, tuple))


__all__ = [
    "MAX_PROVIDER_CANDIDATES", "candidate_has_displayable_fields",
    "candidate_mappings", "candidate_payload_is_sequence", "candidate_text_is_corrupt",
]

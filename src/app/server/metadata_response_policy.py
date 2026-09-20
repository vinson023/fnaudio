"""Pure response decisions for interactive metadata endpoints."""

from metadata_artwork_policy import is_artwork_url
from metadata_provider_payload import candidate_has_displayable_fields


def is_pending_result(result):
    if not isinstance(result, dict):
        return False
    status = result.get("status")
    return result.get("pending") is True or (isinstance(status, str) and status.lower() == "pending")


def has_cached_track_projection(result):
    """Whether a track response is usable without a live worker."""
    if not isinstance(result, dict) or not result or is_pending_result(result):
        return False
    # A persisted artwork asset is independently useful even when an older
    # match row has sparse/empty candidate JSON. Treat the bounded relative
    # projection as cacheable so the HTTP layer does not hide it behind a
    # worker-liveness check.
    image_url = result.get("image_url")
    if is_artwork_url(image_url):
        return True
    # Status-only failures and empty review projections are not cached
    # metadata.  Treating them as successful here bypasses the worker gate and
    # makes the client stop its bounded recovery loop.  A non-empty best or
    # candidate is a usable presentation projection, including the local
    # filename fallback.
    best = result.get("best")
    if candidate_has_displayable_fields(best):
        return True
    candidates = result.get("candidates")
    return isinstance(candidates, list) and any(candidate_has_displayable_fields(item) for item in candidates)


def has_cached_lyrics(result):
    """Whether lyrics/artwork or a terminal result can be returned directly."""
    if not isinstance(result, dict):
        return False
    # An artwork-only pending response keeps the lyrics view visually useful,
    # but it must not bypass the priority-lane liveness probe: lyrics are
    # still unresolved and a dead worker would otherwise leave it pending.
    if is_pending_result(result):
        return False
    return True


__all__ = ["is_pending_result", "has_cached_track_projection", "has_cached_lyrics"]

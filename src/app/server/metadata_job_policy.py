"""Pure status policy for metadata worker jobs."""

from __future__ import annotations


def result_is_local_fallback(result):
    """Return whether a result contains only the presentation filename fallback."""
    if not isinstance(result, dict):
        return False
    source = result.get("source")
    return isinstance(source, str) and source.strip().casefold() == "filename"


def final_status(result, provider_failed=False):
    """Project a worker result into a bounded persistent job status."""
    if result == "skipped":
        return "skipped"
    if result and not (provider_failed and result_is_local_fallback(result)):
        return "done"
    return "failed" if provider_failed else "no_match"


def worker_status(result, provider_failed=False, initial_provider_failed=False, job_type=""):
    """Project one worker result into a terminal status safely.

    Provider adapters are expected to return mappings, but a malformed
    response must never be treated as a successful empty result.  Lyrics have
    one extra rule: if the lyric chain observed an outage and its bounded
    artwork fallback also produced nothing, keep the job retryable.
    """
    safe_result = result if isinstance(result, dict) else {}
    failed = bool(provider_failed)
    if (
        bool(initial_provider_failed)
        and job_type == "lyrics"
        and not safe_result.get("lyrics")
        and not safe_result.get("image_url")
    ):
        failed = True
    return final_status(safe_result, failed)


def retry_attempt(attempts, maximum=5):
    """Return whether another bounded retry is permitted."""
    try:
        value = int(attempts)
        limit = int(maximum)
    except (TypeError, ValueError, OverflowError):
        return False
    if value < 0 or limit < 1:
        return False
    return value < limit


def retry_delay_seconds(attempts, base=60, maximum=3600):
    """Return exponential backoff without allowing huge exponent work."""
    if isinstance(attempts, bool) or not isinstance(attempts, (int, float)):
        return 0
    if isinstance(base, bool) or not isinstance(base, (int, float)):
        return 0
    if isinstance(maximum, bool) or not isinstance(maximum, (int, float)):
        return 0
    try:
        value = max(0, min(32, int(attempts)))
        floor = max(0, min(3600, int(base)))
        ceiling = max(floor, min(86400, int(maximum)))
    except (TypeError, ValueError, OverflowError):
        return 0
    return min(ceiling, floor * (2 ** value))


__all__ = ["final_status", "result_is_local_fallback", "retry_attempt", "retry_delay_seconds", "worker_status"]

"""Pure, bounded retry decisions for terminal metadata jobs."""

# Interactive metadata requests should recover from transient provider
# outages quickly. This policy is only consulted by user-visible requests,
# so a short cooldown avoids leaving the current song metadata-less for many
# minutes without increasing background crawl pressure.
FAILED_RETRY_AFTER_SECONDS = 60


def should_auto_retry_failed(status, updated_at, now, retry_after=FAILED_RETRY_AFTER_SECONDS):
    """Allow a user-visible request to recover an old failed/no-match lookup.

    ``no_match`` is deliberately included after its cooldown.  A provider can
    transiently return an empty result (rate limiting, regional routing, or a
    schema change) even though the song is searchable later.  The cooldown
    keeps normal polling quiet while allowing a later lyrics/candidate view to
    recover without requiring a manual retry button.
    """
    if status not in ("failed", "no_match"):
        return False
    try:
        updated = int(updated_at)
        current = int(now)
        window = int(retry_after)
    except (TypeError, ValueError, OverflowError):
        # Legacy rows occasionally contain a blank/non-numeric timestamp.
        # They cannot provide a trustworthy cooldown boundary; keeping them
        # permanently negative makes metadata recovery impossible after an
        # upgrade.  The caller still limits this to interactive requests.
        return True
    if updated <= 0:
        # Treat missing legacy timestamps as immediately retryable.  This is
        # safer than pinning a stale failed/no_match row until its long TTL;
        # provider/job budgets remain the actual request guardrails.
        return True
    if current < updated or window < 1:
        return False
    return current - updated >= window


__all__ = ["FAILED_RETRY_AFTER_SECONDS", "should_auto_retry_failed"]

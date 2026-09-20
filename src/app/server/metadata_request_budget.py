"""Pure bounds for one interactive metadata provider chain."""

import math


DEFAULT_REQUEST_TIMEOUT_SECONDS = 10
# MusicBrainz is a useful broad-catalog fallback, but its public endpoint is
# comparatively rate-limited. Keep a slow/unreachable request from consuming
# the entire interactive chain before regional providers can answer.
MUSICBRAINZ_REQUEST_TIMEOUT_SECONDS = 4
DEFAULT_JOB_BUDGET_SECONDS = 15
LYRICS_JOB_BUDGET_SECONDS = 12
MAX_JOB_BUDGET_SECONDS = 30


def bounded_job_budget(value, default=DEFAULT_JOB_BUDGET_SECONDS):
    """Return a finite provider-chain budget without coercing arbitrary input."""
    if isinstance(default, bool) or not isinstance(default, (int, float)):
        default = DEFAULT_JOB_BUDGET_SECONDS
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        value = default
    try:
        seconds = float(value)
    except (TypeError, ValueError, OverflowError):
        seconds = float(default)
    if not math.isfinite(seconds):
        seconds = float(default)
    return max(1.0, min(float(MAX_JOB_BUDGET_SECONDS), seconds))


def provider_timeout(deadline, now, requested=DEFAULT_REQUEST_TIMEOUT_SECONDS):
    """Return the bounded timeout remaining for one request, or zero when spent."""
    if isinstance(requested, bool) or not isinstance(requested, (int, float)):
        requested = DEFAULT_REQUEST_TIMEOUT_SECONDS
    try:
        requested_seconds = float(requested)
    except (TypeError, ValueError, OverflowError):
        requested_seconds = float(DEFAULT_REQUEST_TIMEOUT_SECONDS)
    if not math.isfinite(requested_seconds) or requested_seconds <= 0:
        requested_seconds = float(DEFAULT_REQUEST_TIMEOUT_SECONDS)
    requested_seconds = max(1, int(math.ceil(requested_seconds)))
    if deadline is None:
        return requested_seconds
    if isinstance(now, bool) or not isinstance(now, (int, float)):
        return 0
    try:
        remaining = float(deadline) - float(now)
    except (TypeError, ValueError, OverflowError):
        return 0
    if not math.isfinite(remaining) or remaining <= 0:
        return 0
    return max(1, min(int(math.ceil(remaining)), requested_seconds))


__all__ = [
    "DEFAULT_JOB_BUDGET_SECONDS", "DEFAULT_REQUEST_TIMEOUT_SECONDS", "MUSICBRAINZ_REQUEST_TIMEOUT_SECONDS", "LYRICS_JOB_BUDGET_SECONDS",
    "MAX_JOB_BUDGET_SECONDS", "bounded_job_budget", "provider_timeout",
]

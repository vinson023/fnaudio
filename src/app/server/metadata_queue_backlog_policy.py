"""Pure, bounded decisions for metadata queue pressure.

On the real device a 62,684-track library never converged: the provider chain
answers no_match for most HIRES/DSD files, the negative cache lives for six
hours, and every reconcile sweep therefore re-opened roughly twenty thousand
terminal jobs as pending.  Each sweep rewrote thousands of rows while four
network workers kept re-running doomed provider lookups, so the application
process stayed pinned at about a quarter of a NAS CPU and interactive requests
(folder browsing through the fnOS CGI gateway) started taking seconds.

Queue pressure is a property of two numbers the caller already has, so this
module stays free of SQLite, threads and configuration objects: it turns
(pending, limit) into one yes/no re-queue decision plus the cadence the
background worker should use.  It fails open on garbage input because losing
background metadata recovery is a worse product outcome than one more sweep.
"""

from typing import Any

# Re-queueing is whole-queue work, so it stops a little before the hard ceiling:
# by the time the ceiling is reached the sweep has already rewritten every
# terminal job it was going to rewrite.
REQUEUE_HEADROOM_RATIO = 0.8

# A quiet queue keeps the historical fifteen-second cadence.  A queue with a
# real backlog does not need to be prodded every fifteen seconds -- it is
# already full of work -- so the background sweep backs off to two minutes.
RECONCILE_INTERVAL_SECONDS = 15.0
RECONCILE_BACKLOG_INTERVAL_SECONDS = 120.0

MAX_QUEUE_COUNTER = 10 ** 12


def _bounded_int(value, default=0):
    """Coerce an untrusted counter to a non-negative int, or default."""
    if isinstance(value, bool) or value is None:
        return default
    if not isinstance(value, (int, str)):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if number < 0:
        return default
    return min(MAX_QUEUE_COUNTER, number)


def _bounded_ratio(value, default=REQUEUE_HEADROOM_RATIO):
    """Clamp a headroom fraction into (0.0, 1.0], falling back on garbage."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if number != number or number in (float("inf"), float("-inf")):
        return default
    if number <= 0.0:
        return default
    return min(1.0, number)


def queue_backlog_ratio(pending, limit):
    """Return pending/limit clamped to [0.0, 1.0].

    An unusable limit reports 0.0 (no backlog) instead of raising, because
    every caller uses this to reduce background work and must not be able to
    wedge recovery on a malformed counter.
    """
    bounded_limit = _bounded_int(limit, 0)
    bounded_pending = _bounded_int(pending, 0)
    if bounded_limit <= 0:
        return 0.0
    ratio = bounded_pending / bounded_limit
    if ratio < 0.0:
        return 0.0
    return min(1.0, ratio)


def queue_is_backlogged(pending, limit, headroom=REQUEUE_HEADROOM_RATIO):
    """True when the queue is close enough to its ceiling that a sweep is waste."""
    bounded_limit = _bounded_int(limit, 0)
    if bounded_limit <= 0:
        return False
    return queue_backlog_ratio(pending, limit) >= _bounded_ratio(headroom)


def requeue_allowed(pending, limit, headroom=REQUEUE_HEADROOM_RATIO):
    """Whether terminal jobs may be flipped back to pending this cycle.

    Deliberately fails open: an unreadable pending count must not silently
    disable metadata recovery for the rest of the process lifetime.
    """
    return not queue_is_backlogged(pending, limit, headroom)


def reconcile_interval_seconds(force=False, backlogged=False):
    """Cadence for the background reconcile step.

    force (an explicit user refresh) keeps the interval at zero so the next
    worker iteration reconciles immediately.  A saturated queue slows the
    sweep down instead of multiplying the very work that saturated it.
    """
    if force is True:
        return 0.0
    if backlogged is True:
        return RECONCILE_BACKLOG_INTERVAL_SECONDS
    return RECONCILE_INTERVAL_SECONDS


def should_run_reconcile(elapsed_seconds, force=False, backlogged=False):
    """Combine the cadence decision with the caller's measured idle interval."""
    if force is True:
        return True
    try:
        elapsed = float(elapsed_seconds)
    except (TypeError, ValueError, OverflowError):
        # A missing clock reading cannot establish that enough time has passed;
        # the historical behaviour ran the sweep, so keep that.
        return True
    if elapsed != elapsed or elapsed in (float("inf"), float("-inf")):
        return True
    return elapsed >= reconcile_interval_seconds(False, backlogged)


__all__ = [
    "MAX_QUEUE_COUNTER",
    "RECONCILE_BACKLOG_INTERVAL_SECONDS",
    "RECONCILE_INTERVAL_SECONDS",
    "REQUEUE_HEADROOM_RATIO",
    "queue_backlog_ratio",
    "queue_is_backlogged",
    "reconcile_interval_seconds",
    "requeue_allowed",
    "should_run_reconcile",
]

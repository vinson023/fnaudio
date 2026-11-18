"""What this playback installation can do, for clients that must not guess.

R585 gave the library a ``capabilities`` block so the UI could hide a feature
instead of calling an endpoint that 404s.  The queue needs its own block because
these numbers belong to the *output target*, not to the index: a browser queue
can hold the whole session, a phone's remote snapshot is capped at
``REMOTE_QUEUE_MAX_ITEMS``, and a DLNA renderer has whatever its firmware
accepts.

Every consumer treats a missing block as "no limit known" and leaves the queue
alone -- that is what keeps an older server working with a newer client.
"""

from __future__ import annotations

from typing import Any, Dict

from playback.core import MAX_QUEUE_TRACKS

CAPABILITY_VERSION = 1
# Must stay equal to MAX_REMOTE_QUEUE_ITEMS in
# android-client/.../playback/PlaybackService.java; the test reads that file and
# fails when the two drift, because a client-side slice and a native-side slice
# that disagree mean the queue silently loses different rows depending on which
# layer runs first.
REMOTE_QUEUE_MAX_ITEMS = 500
# A reload must not resume at 0:00, but writing the position every second costs a
# SQLite write per client per second.  30s plus an event on pause/leave is the
# compromise; the client is told the number so both sides cannot drift.
POSITION_REPORT_MIN_INTERVAL_MS = 30000


def playback_capabilities() -> Dict[str, Any]:
    """Return the bounded capability block served at /api/playback/capabilities."""
    return {
        "version": CAPABILITY_VERSION,
        "queue": {
            "max_items": MAX_QUEUE_TRACKS,
            "remote_max_items": REMOTE_QUEUE_MAX_ITEMS,
            "truncation_notice": True,
        },
        "position": {
            "report": True,
            "min_interval_ms": POSITION_REPORT_MIN_INTERVAL_MS,
        },
        "shuffle": {
            # "queue-order": turning shuffle on reorders the queue once; next and
            # previous are then plain index arithmetic.  A client that still
            # randomises per press would disagree with the server about what
            # "next" means.
            "mode": "queue-order",
        },
    }


__all__ = [
    "CAPABILITY_VERSION",
    "POSITION_REPORT_MIN_INTERVAL_MS",
    "REMOTE_QUEUE_MAX_ITEMS",
    "playback_capabilities",
]

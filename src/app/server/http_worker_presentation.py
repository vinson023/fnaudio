"""Shared bounded projection for HTTP worker diagnostics."""

from __future__ import annotations

from summary_values import nonnegative_int

HTTP_WORKER_FIELDS = ("active", "limit", "peak", "acquired", "rejected")
HTTP_EVENT_FIELDS = ("active", "limit", "peak", "acquired", "rejected")


def project_http_workers(value):
    """Return only safe, non-negative HTTP worker pressure fields."""
    source = value if isinstance(value, dict) else {}
    result = {}
    for key in HTTP_WORKER_FIELDS:
        try:
            result[key] = nonnegative_int(source.get(key))
        except Exception:
            result[key] = 0
    try:
        events = source.get("event_streams")
    except Exception:
        events = {}
    events = events if isinstance(events, dict) else {}
    for key in HTTP_EVENT_FIELDS:
        try:
            result["event_stream_" + key] = nonnegative_int(
                source.get("event_stream_limit") if key == "limit" else events.get(key)
            )
        except Exception:
            result["event_stream_" + key] = 0
    return result

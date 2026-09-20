"""Privacy-safe DLNA discovery summary shared by health and diagnostics."""

from __future__ import annotations

from summary_values import nonnegative_int, strict_bool


def _safe_get(source, key, default=None):
    if not isinstance(source, dict):
        return default
    try:
        return source.get(key, default)
    except Exception:
        return default


def dlna_component(running, renderers, discovery=None, eventing=None):
    source = discovery if isinstance(discovery, dict) else {}
    events = eventing if isinstance(eventing, dict) else {}
    return {
        "running": strict_bool(running),
        "renderers": nonnegative_int(renderers),
        "discovery": {
            "refreshing": strict_bool(_safe_get(source, "refreshing")),
            "workers": nonnegative_int(_safe_get(source, "workers")),
            "worker_limit": nonnegative_int(_safe_get(source, "worker_limit")),
            "cached_renderers": nonnegative_int(_safe_get(source, "cached_renderers")),
            "cache_age_seconds": nonnegative_int(_safe_get(source, "cache_age_seconds")),
            "refresh_started": nonnegative_int(_safe_get(source, "refresh_started")),
            "refresh_completed": nonnegative_int(_safe_get(source, "refresh_completed")),
            "refresh_failed": nonnegative_int(_safe_get(source, "refresh_failed")),
            "refresh_skipped": nonnegative_int(_safe_get(source, "refresh_skipped")),
        },
        "eventing": {
            "subscriptions": nonnegative_int(_safe_get(events, "subscriptions")),
            "subscription_limit": nonnegative_int(_safe_get(events, "subscription_limit")),
            "workers": nonnegative_int(_safe_get(events, "workers")),
            "worker_limit": nonnegative_int(_safe_get(events, "worker_limit")),
            "pending": nonnegative_int(_safe_get(events, "pending")),
            "pending_limit": nonnegative_int(_safe_get(events, "pending_limit")),
            "peak_pending": nonnegative_int(_safe_get(events, "peak_pending")),
            "accepted": nonnegative_int(_safe_get(events, "accepted")),
            "dropped": nonnegative_int(_safe_get(events, "dropped")),
        },
    }

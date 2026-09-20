"""Pure metadata pressure projection for support diagnostics."""

from __future__ import annotations

from metadata_provider_failure_policy import provider_activity_snapshot, provider_failure_snapshot
from summary_values import nonnegative_int, strict_bool


def _safe_get(source, key, default=None):
    if not isinstance(source, dict):
        return default
    try:
        return source.get(key, default)
    except Exception:
        return default


def metadata_summary(metadata):
    source = metadata if isinstance(metadata, dict) else {}
    cache = _safe_get(source, "status_cache")
    cache = cache if isinstance(cache, dict) else {}
    candidate_cache = _safe_get(source, "provider_candidate_cache")
    candidate_cache = candidate_cache if isinstance(candidate_cache, dict) else {}
    lyrics_cache = _safe_get(source, "local_lyrics_cache")
    lyrics_cache = lyrics_cache if isinstance(lyrics_cache, dict) else {}
    return {
        "running": strict_bool(_safe_get(source, "running")),
        "pending": nonnegative_int(_safe_get(source, "pending")),
        "dropped": nonnegative_int(_safe_get(source, "dropped")),
        "network_workers_active": nonnegative_int(_safe_get(source, "network_workers_active")),
        "network_worker_limit": nonnegative_int(_safe_get(source, "network_worker_limit")),
        # Provider failures are already redacted and bounded by the metadata
        # service policy. Keeping the same projection in support diagnostics
        # lets an unavailable upstream be distinguished from a genuine
        # no-match result without exposing URLs, paths or raw payloads.
        "provider_failures": provider_failure_snapshot(_safe_get(source, "provider_failures")),
        "provider_activity": provider_activity_snapshot(_safe_get(source, "provider_activity")),
        "status_cache": {
            "ttl_ms": nonnegative_int(_safe_get(cache, "ttl_ms")),
            "age_ms": nonnegative_int(_safe_get(cache, "age_ms")),
            "hits": nonnegative_int(_safe_get(cache, "hits")),
            "misses": nonnegative_int(_safe_get(cache, "misses")),
        },
        "provider_candidate_cache": {
            "entries": nonnegative_int(_safe_get(candidate_cache, "entries")),
            "limit": nonnegative_int(_safe_get(candidate_cache, "limit")),
            "hits": nonnegative_int(_safe_get(candidate_cache, "hits")),
            "misses": nonnegative_int(_safe_get(candidate_cache, "misses")),
            "ttl_ms": nonnegative_int(_safe_get(candidate_cache, "ttl_ms")),
        },
        "local_lyrics_cache": {
            "entries": nonnegative_int(_safe_get(lyrics_cache, "entries")),
            "limit": nonnegative_int(_safe_get(lyrics_cache, "limit")),
            "bytes": nonnegative_int(_safe_get(lyrics_cache, "bytes")),
            "bytes_limit": nonnegative_int(_safe_get(lyrics_cache, "bytes_limit")),
            "hits": nonnegative_int(_safe_get(lyrics_cache, "hits")),
            "misses": nonnegative_int(_safe_get(lyrics_cache, "misses")),
        },
    }


__all__ = ["metadata_summary"]

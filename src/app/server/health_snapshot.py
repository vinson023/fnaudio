"""Pure, bounded health-response construction for the HTTP API."""

from __future__ import annotations

from playback.mpd_errors import health_error_category
from library_snapshot import library_component
from dlna_snapshot import dlna_component
from summary_values import bounded_text, nonnegative_int, strict_bool
from transcode_snapshot import transcode_summary
from metrics_projection import project_metrics
from http_worker_presentation import project_http_workers


def _safe_get(source, key, default=None):
    """Read a known field without trusting mapping subclasses."""
    if not isinstance(source, dict):
        return default
    try:
        return source.get(key, default)
    except Exception:
        return default


def _safe_dict(source, keys):
    """Project a dependency mapping to plain data before composing health."""
    if not isinstance(source, dict):
        return {}
    result = {}
    for key in keys:
        value = _safe_get(source, key)
        if value is not None:
            result[key] = value
    return result


def build_health_payload(*, server_name, request_id, mpd, scan_state, metadata, transcode, dlna_running, renderer_count, metrics, library_query_cache, library_search_index=None, thumbnail_prewarm=None, cover_cache=None, cache_failures=None, library_storage=None, dlna_discovery=None, dlna_eventing=None, http_workers=None, playback_command_cache=None, library_connection_pool=None):
    """Build `/api/health` without coupling its shape to a request handler."""
    mpd_source = _safe_dict(mpd, ("running", "fault", "playback_errors"))
    mpd_fault = _safe_dict(_safe_get(mpd_source, "fault"), ("state",))
    # `health_error_category` reads the per-error `items` list and nothing else.
    # The old whitelist forwarded `count` (never read here) and `last_error` (a
    # key no producer emits), which made this component's error category a
    # permanent empty string even while MPD was logging decoder failures.
    mpd_errors = _safe_dict(_safe_get(mpd_source, "playback_errors"), ("items",))
    metadata_source = _safe_dict(metadata, ("running", "pending", "pending_limit", "dropped", "network_workers_active", "network_worker_limit", "artwork_bytes", "artwork_limit_bytes", "status_cache", "local_lyrics_cache"))
    metadata_cache = _safe_dict(_safe_get(metadata_source, "status_cache"), ("ttl_ms", "age_ms", "hits", "misses"))
    lyrics_cache = _safe_dict(_safe_get(metadata_source, "local_lyrics_cache"), ("entries", "limit", "bytes", "bytes_limit", "hits", "misses"))
    transcode_source = _safe_dict(transcode, ("queued", "tracked", "queue_limit", "ffmpeg"))
    transcode_source["ffmpeg"] = _safe_dict(_safe_get(transcode_source, "ffmpeg"), ("active", "limit", "waiting", "peak", "peak_waiting", "acquired", "waited", "rejected", "waiter_rejected", "timed_out", "waiter_limit", "wait_seconds"))
    return {
        "ok": True,
        "name": bounded_text(server_name, "fnAudio", 160),
        "request_id": bounded_text(request_id, "", 160),
        "components": {
            "mpd": {
                "running": strict_bool(_safe_get(mpd_source, "running")),
                "fault": _safe_get(mpd_fault, "state", ""),
                "error_category": health_error_category(mpd_errors),
            },
            "library": library_component(
                scan_state,
                query_cache=library_query_cache,
                search_index=library_search_index,
                thumbnail_prewarm=thumbnail_prewarm,
                cover_cache=cover_cache,
                cache_failures=cache_failures,
                storage=library_storage,
                connection_pool=library_connection_pool,
            ),
            "metadata": {
                "running": strict_bool(_safe_get(metadata_source, "running")),
                "pending": nonnegative_int(_safe_get(metadata_source, "pending")),
                "pending_limit": nonnegative_int(_safe_get(metadata_source, "pending_limit")),
                "dropped": nonnegative_int(_safe_get(metadata_source, "dropped")),
                "network_workers_active": nonnegative_int(_safe_get(metadata_source, "network_workers_active")),
                "network_worker_limit": nonnegative_int(_safe_get(metadata_source, "network_worker_limit")),
                "artwork_bytes": nonnegative_int(_safe_get(metadata_source, "artwork_bytes")),
                "artwork_limit_bytes": nonnegative_int(_safe_get(metadata_source, "artwork_limit_bytes")),
                "status_cache": {
                    "ttl_ms": nonnegative_int(_safe_get(metadata_cache, "ttl_ms")),
                    "age_ms": nonnegative_int(_safe_get(metadata_cache, "age_ms")),
                    "hits": nonnegative_int(_safe_get(metadata_cache, "hits")),
                    "misses": nonnegative_int(_safe_get(metadata_cache, "misses")),
                },
                "local_lyrics_cache": {
                    "entries": nonnegative_int(_safe_get(lyrics_cache, "entries")),
                    "limit": nonnegative_int(_safe_get(lyrics_cache, "limit")),
                    "bytes": nonnegative_int(_safe_get(lyrics_cache, "bytes")),
                    "bytes_limit": nonnegative_int(_safe_get(lyrics_cache, "bytes_limit")),
                    "hits": nonnegative_int(_safe_get(lyrics_cache, "hits")),
                    "misses": nonnegative_int(_safe_get(lyrics_cache, "misses")),
                },
            },
            "transcode": transcode_summary(transcode_source),
            "playback": {
                "command_cache": _safe_dict(playback_command_cache, ("entries", "limit", "saturated", "inflight", "inflight_limit")),
            },
            "http": project_http_workers(http_workers),
            "dlna": dlna_component(dlna_running, renderer_count, dlna_discovery, dlna_eventing),
        },
        "metrics": project_metrics(metrics),
    }

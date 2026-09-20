"""Privacy-safe support snapshot construction."""
from __future__ import annotations

from observability import redact
from playback.mpd_errors import health_error_category
from library_snapshot import library_component
from dlna_snapshot import dlna_component
from summary_values import bounded_text, nonnegative_int, strict_bool
from transcode_snapshot import transcode_summary
from diagnostics_playback import playback_summary
from diagnostics_metadata import metadata_summary
from version import APP_VERSION
from http_worker_presentation import project_http_workers


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _safe_get(source, key, default=None):
    """Read diagnostic fields without trusting mapping subclasses."""
    if not isinstance(source, dict):
        return default
    try:
        return source.get(key, default)
    except Exception:
        return default


def _safe_dict(source, keys):
    """Project explicitly allowed diagnostic fields from one mapping."""
    if not isinstance(source, dict):
        return {}
    result = {}
    for key in keys:
        value = _safe_get(source, key)
        if value is not None:
            result[key] = value
    return result


def support_snapshot(*, server_name, mpd, scan_state, metadata, transcode, dlna_available, renderer_count, metrics, playback, library_query_cache=None, library_search_index=None, thumbnail_prewarm=None, cover_cache=None, cache_failures=None, library_storage=None, dlna_discovery=None, dlna_eventing=None, http_workers=None, playback_command_cache=None, library_connection_pool=None):
    """Return bounded diagnostics without credentials, paths or queue metadata."""
    mpd = _mapping(mpd)
    scan_state = _mapping(scan_state)
    metadata = _mapping(metadata)
    transcode = _mapping(transcode)
    playback = _mapping(playback)
    metrics = _mapping(metrics)
    fault = _mapping(_safe_get(mpd, "fault"))
    playback_errors = _mapping(_safe_get(mpd, "playback_errors"))
    return redact({
        "schema": 1,
        "server": {"name": bounded_text(server_name, "fnAudio", 160), "version": APP_VERSION},
        "playback": {
            **playback_summary(playback),
        },
        "components": {
            "mpd": {
                "running": strict_bool(_safe_get(mpd, "running")),
                "fault": bounded_text(_safe_get(fault, "state"), "", 64),
                "error_category": health_error_category(playback_errors),
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
            "metadata": metadata_summary(metadata),
            "transcode": transcode_summary(transcode),
            "playback": {
                "command_cache": _safe_dict(playback_command_cache, ("entries", "limit", "saturated", "inflight", "inflight_limit")),
            },
            "http": project_http_workers(http_workers),
            "dlna": dlna_component(dlna_available, renderer_count, dlna_discovery, dlna_eventing),
        },
        "metrics": metrics or {},
    })

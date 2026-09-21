#!/usr/bin/env python3
import argparse
import base64
import copy
import hashlib
import html
import json
import math
import mimetypes
import os
import re
import signal
import shutil
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler

from config import load_config, save_config, save_proxy_port
from library import (
    FS_CACHE,
    MUSIC_CACHE,
    SCAN_LOCK,
    SCAN_STATE,
    cancel_library_refresh,
    apply_library_connection_pool_config,
    # Not a private-access shortcut: this is the *same* predicate the reader path
    # uses to decide whether to borrow a pooled handle, so the settings pane cannot
    # report an enabled state the running pool would not honour.  A second
    # defaulting rule here is exactly the drift that kept the switch hidden.
    _library_connection_pool_enabled as library_connection_pool_enabled,
    stop_library_connections,
    library_items,
    library_query_cache_status,
    invalidate_library_query_cache,
    library_search_index_status,
    library_connection_pool_status,
    library_connection_pool_config_key,
    library_storage_status,
    library_status,
    library_cache_failure_status,
    load_items_from_sqlite,
    is_library_item_path,
    list_music_directories,
    load_library_cache,
    query_library_folders,
    query_library_item_by_id,
    query_library_item_location,
    query_library_items_by_ids,
    query_library_root_folders,
    query_library_groups,
    query_library_page,
    request_library_refresh,
    shutdown_library_refresh,
    start_library_watcher,
    stop_library_watcher,
    read_cover_for_item,
    save_library_cache,
    safe_float,
    safe_int,
    watch_library,
)
from library_paths import (
    MAX_LIBRARY_PATHS,
    apply_library_paths,
    canonical_library_path,
    is_allowed_library_path,
)
from library_query_spec import parse_library_item_ids
from dlna.control_point import (
    cached_upnp_devices,
    configure_local_renderer_identity,
    discover_upnp,
    find_service_url,
    refresh_upnp_cache_background,
    shutdown_upnp_cache_background,
    seconds_to_upnp_time,
    upnp_cache_needs_refresh,
    upnp_cache_status,
    upnp_control,
    upnp_position_info,
    upnp_transport_state,
)
from dlna.diagnostics import DlnaDiagnostics
from dlna.media_server import (
    soap_push as dlna_soap_push,
    upnp_resource_mime,
)
from dlna.renderer import DlnaRenderer
from dlna.service import DlnaProtocolService, scpd as dlna_scpd
from dlna.ssdp import SsdpService
from dlna.upmpdcli_renderer import upmpdcli_probe
from playback import AlsaOutput, DlnaPushOutput, MpdOutput, PlaybackCommand, PlaybackCore, TrackRef
from playback.http_contract import (
    apply_legacy_player_state,
    legacy_control_payload,
    legacy_load_payload,
    legacy_response_headers,
    normalize_target_id,
    playback_event_payload,
    target_kind as playback_target_kind,
)
from playback_event_stream_policy import keepalive_frame, snapshot_changed, snapshot_frame
from playback.mpd_client import mpd_control, mpd_load_uri, mpd_status
from playback.alsa_output import (
    DAC_LOCK,
    DAC_STATE,
    alsa_devices,
    dac_control,
    dac_public_status,
    find_aplay,
    find_libasound,
    start_dac_playback,
)
from services.mpd_service import MpdService
from services.audio_output_lease import AUDIO_OUTPUT_LEASE
from services.airplay_service import AirplayService, airplay_probe
from state_store import StateConflict, load_user_state, save_playback_session, save_user_state
from state_projection import playback_queue_ids
from playback_session_projection import project_playback_session
from metadata_service import MAX_ARTWORK_BYTES, MetadataService
from metadata_numeric_policy import strict_nonnegative_int
# The lyric cache budget is named and bounded in one place. `metadata_service`
# already reads it through `bytes_limit_from_config`, so the HTTP layer imports
# the same helpers instead of inventing a second default or a second range.
from metadata_local_lyrics_cache import (
    CONFIG_BYTES_KEY as LYRICS_CACHE_BYTES_CONFIG_KEY,
    bytes_limit_from_config,
    strict_bytes_limit_from_payload,
)
from metadata_track_id_policy import normalize_track_id
from metadata_artwork_file import open_bounded_artwork
from metadata_lane_policy import lane_workers_alive, service_was_started
from metadata_response_policy import has_cached_lyrics, has_cached_track_projection, is_pending_result
from metadata_unavailable_policy import local_cached_projection, local_lyrics_projection, local_pending_projection, lyrics_pending_projection, merge_pending_projection
from api_auth import authorize_api, requires_resource_auth
from api_token_policy import trim_api_token
from dlna.request_context import request_context
from observability import OBSERVABILITY, request_id
from diagnostics import support_snapshot
from health_snapshot import build_health_payload
from playback_status_spec import command_id_from_payload, target_id_from_query
from playback_session_policy import identity_is_stale, session_identity
from playback_command_cache import cache_snapshot, cached_result, store_result
from playback_queue_policy import queue_request, should_sync_mpd_queue
from playback_status_presentation import present_position, present_transport
from playback_status_response import (
    alsa_response,
    backend_error_response,
    browser_response,
    device_not_found_response,
    mpd_error_response,
    mpd_response,
    upnp_response,
)
from playback_targets_presentation import build_targets
from playback_targets_response import compose_playback_targets_response
from upnp_device_selection import select_upnp_device
from playback_cue_position import cue_segment_declaration, normalize_cue_position, project_cue_seek, public_cue_position
from media_range import parse_single_byte_range
from media_naming import safe_filename
from static_asset_policy import (
    static_asset_cache_control,
    static_asset_etag,
    static_asset_etag_matches,
    static_asset_size_allowed,
)
from http_request_policy import MAX_REQUEST_BODY_BYTES, request_body_length, request_target_allowed
from http_observation import observe_http_request
from json_response_policy import serialize_json_response
from response_header_policy import normalize_response_headers
from http_error_policy import project_error_text
from xml_response_policy import serialize_xml_response
from remote_output_monitor_policy import (
    stalled_track_expired,
    stop_is_suppressed,
    track_id_from_renderer_uri,
)
from port_probe import find_free_tcp_port, is_tcp_port_available
from network_address import local_address
from public_url import build_public_base_url
from cover_item_cache import cached_cover_for_item as cache_cover_for_item, cache_snapshot as cover_cache_snapshot
from cover_media_type import SNIFF_PREFIX_BYTES, safe_image_media_type
from library_presentation import public_library_item, public_library_page
from version import APP_USER_AGENT
from cover_cache import (cached_thumbnail_for_item, cover_is_known_missing, cover_source_version,
                         generate_asset_thumbnail, normalized_cover_size, prewarm_thumbnails,
                         thumbnail_asset_bytes, thumbnail_asset_id_for_item,
                         prewarm_library_thumbnails, shutdown_library_thumbnail_prewarm,
                         thumbnail_prewarm_status)

STATE = {"queue": [], "current": None, "playing": False}
PLAYBACK_CORE = PlaybackCore()
MPD_OUTPUT = MpdOutput()
MPD_SERVICE = None
DLNA_PROTOCOL = None
DLNA_SSDP = None
METADATA_SERVICE = None
STARTUP_THUMBNAIL_PREWARM_LIMIT = 96
AIRPLAY_SERVICE = None
DLNA_DIAGNOSTICS = DlnaDiagnostics()
CUE_AUTO_ADVANCE = {"track_id": "", "at": 0.0}
DLNA_MONITOR_GUARD = {"target_id": "", "suppress_stop_until": 0.0}
REMOTE_OUTPUT_MONITOR_STOP = None
REMOTE_OUTPUT_MONITOR_THREAD = None
REMOTE_OUTPUT_MONITOR_LOCK = threading.RLock()
REMOTE_OUTPUT_MONITOR_GENERATION = 0
PLAYBACK_RESTORE_RETRY_STOP = threading.Event()
PLAYBACK_RESTORE_RETRY_LOCK = threading.Lock()
PLAYBACK_RESTORE_RETRY_TIMER = None
PLAYBACK_RESTORE_RETRY_GENERATION = 0
PLAYBACK_COMMAND_LOCK = threading.RLock()
PLAYBACK_COMMAND_RESULTS = {}
PLAYBACK_COMMAND_INFLIGHT = {}
PLAYBACK_COMMAND_TTL_SECONDS = 30.0
PLAYBACK_COMMAND_RESULT_LIMIT = 1024
PLAYBACK_COMMAND_WAIT_SECONDS = 15.0
PLAYBACK_CONTROL_ACTIONS = frozenset({
    "play", "resume", "pause", "stop", "seek", "load", "next", "previous",
    "repeat", "shuffle", "volume",
})


def metadata_service_available(service, lane="fetch"):
    """Return whether the requested metadata lane has a live worker.

    Lyrics have a dedicated priority worker but can also be handled by the
    regular fetch pool when background enrichment is enabled. Track candidate
    requests require the regular fetch pool. Keeping these checks separate
    prevents a degraded pool from making every metadata endpoint look down.
    """
    if service is None:
        return False
    available = lane_workers_alive(service, lane)
    if available:
        return True
    # A worker can die between status polling and this request. Give the
    # service one serialized, lazy recovery attempt before returning 503.
    ensure = getattr(service, "ensure_workers", None)
    if callable(ensure):
        try:
            try:
                ensure(lane)
            except TypeError:
                # Keep compatibility with lightweight service doubles and
                # older embedded MetadataService implementations.
                ensure()
        except Exception:
            return False
        # Thread.start() returns before the worker necessarily reaches its
        # first scheduling point.  A request arriving in that tiny window
        # used to be reported as a hard 503, making metadata appear broken
        # until the next UI poll.  Keep the recovery wait deliberately tiny
        # and bounded; this is not a provider/network wait, only a local
        # worker-liveness handoff.
        for _ in range(3):
            if lane_workers_alive(service, lane):
                return True
            time.sleep(0.02)
        return lane_workers_alive(service, lane)
    return False


def playback_command_cache_status():
    with PLAYBACK_COMMAND_LOCK:
        snapshot = cache_snapshot(PLAYBACK_COMMAND_RESULTS, PLAYBACK_COMMAND_RESULT_LIMIT)
        inflight_limit = playback_command_inflight_limit()
        snapshot["inflight"] = min(len(PLAYBACK_COMMAND_INFLIGHT), inflight_limit)
        snapshot["inflight_limit"] = inflight_limit
        return snapshot


def playback_command_inflight_limit():
    """Keep client-supplied command tickets from retaining unbounded work."""
    try:
        limit = int(PLAYBACK_COMMAND_RESULT_LIMIT)
    except (TypeError, ValueError, OverflowError):
        limit = 1
    return max(1, min(limit, 4096))
CONFIG_UPDATE_LOCK = threading.RLock()
TRANSPARENT_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lR4YJwAAAABJRU5ErkJggg=="
)
COVER_CACHE_LOCK = threading.RLock()
COVER_CACHE = {}
COVER_CACHE_MAX_ENTRIES = 512
COVER_CACHE_MAX_PATH_CHARS = 4096
COVER_CACHE_INFLIGHT = {}
COVER_CACHE_INFLIGHT_LIMIT = 64


def cached_cover_for_item(item, config):
    """Cache extracted local artwork by its on-disk version.

    Library rows often share one embedded or sidecar cover. Without this
    cache a mobile page can ask the service to parse that same image dozens
    of times concurrently before its HTTP cache has a chance to help.
    """
    return cache_cover_for_item(
        item,
        config,
        cache=COVER_CACHE,
        cache_lock=COVER_CACHE_LOCK,
        inflight=COVER_CACHE_INFLIGHT,
        reader=read_cover_for_item,
        max_entries=COVER_CACHE_MAX_ENTRIES,
        max_path_chars=COVER_CACHE_MAX_PATH_CHARS,
        inflight_limit=COVER_CACHE_INFLIGHT_LIMIT,
    )

def cover_cache_status():
    with COVER_CACHE_LOCK:
        return cover_cache_snapshot(COVER_CACHE, COVER_CACHE_INFLIGHT, entry_limit=COVER_CACHE_MAX_ENTRIES, inflight_limit=COVER_CACHE_INFLIGHT_LIMIT)








































































































from transcode import (
    cleanup_transcode_cache_if_due,
    find_ffmpeg,
    media_mode,
    playback_profile,
    public_access,
    prune_transcode_cache,
    transcode_cache_ready,
    transcode_cache_target,
    transcode_command,
    transcode_to_audio,
    transcode_resource_status,
    shutdown_transcode_cache_worker,
    trusted_forwarded_headers,
    warm_transcode_cache,
)
from resource_limits import ResourceLimitError, ffmpeg_slot
from http_server import BoundedThreadingHTTPServer


def public_base_url(handler):
    forwarded = trusted_forwarded_headers(handler)
    return build_public_base_url(
        (forwarded.get("host") if forwarded else "") or handler.headers.get("Host", ""),
        (forwarded.get("proto") if forwarded else "") or "http",
        local_address=local_address,
        is_private_host=is_private_host,
    )


def upnp_base_url(handler):
    return "http://%s:%s" % (local_address(), handler.server.server_address[1])


def read_complete_request_body(stream, length, chunk_size=64 * 1024):
    """Read exactly one already-bounded HTTP request body or reject it.

    ``BufferedReader.read(n)`` may return early at EOF. A partial payload must
    not become a successful playback/configuration command merely because its
    prefix happens to form valid JSON.
    """
    if isinstance(length, bool) or not isinstance(length, int) or length < 0:
        return None
    if length == 0:
        return b""
    if not hasattr(stream, "read"):
        return None
    try:
        piece_size = max(1, min(64 * 1024, int(chunk_size)))
    except (TypeError, ValueError, OverflowError):
        piece_size = 64 * 1024
    remaining = length
    chunks = []
    while remaining:
        try:
            chunk = stream.read(min(piece_size, remaining))
        except (OSError, ValueError):
            return None
        if not isinstance(chunk, (bytes, bytearray)) or not chunk:
            return None
        if len(chunk) > remaining:
            return None
        chunks.append(bytes(chunk))
        remaining -= len(chunk)
    return b"".join(chunks)


def soap_push(device, item, handler):
    return dlna_soap_push(device, item, handler, safe_filename, upnp_base_url, transcode_to_audio)


def dlna_output_open(track, state, context):
    handler = context.get("handler")
    item = context.get("item") or track.item
    device = find_upnp_device(state.target_id)
    if not handler:
        return {"ok": False, "message": "missing request context"}
    if not device:
        return {"ok": False, "message": "device not found"}
    # Some renderers advance a preloaded NextURI themselves while others
    # expose STOPPED first.  Combining that renderer-owned transition with
    # the monitor's authoritative queue advance can replay the just-finished
    # item.  Keep DLNA progression in one place: the monitor loads exactly
    # one next queue item after it observes a completed track.
    ok, message = soap_push(device, item, handler)
    requested_position = safe_float(context.get("position"))
    if ok and requested_position > 0:
        ok, seek_message = upnp_control(device, "seek", requested_position)
        if not ok:
            message = "播放已开始但无法跳转到指定位置: %s" % seek_message
    return {
        "ok": ok,
        "message": message,
        "target_id": state.target_id,
        "track_id": track.track_id,
        "cue_segment": bool(item.get("cue_track")),
    }


def dlna_output_command(command, state, context):
    device = find_upnp_device(state.target_id)
    if not device:
        return {"ok": False, "message": "device not found"}
    if command.action == "stop":
        DLNA_MONITOR_GUARD.update(
            {"target_id": state.target_id, "suppress_stop_until": time.monotonic() + 5.0}
        )
    ok, message = upnp_control(device, command.action, command.position)
    return {"ok": ok, "message": message, "target_id": state.target_id}


def dlna_output_close(state):
    device = find_upnp_device(state.target_id)
    if not device:
        return
    try:
        DLNA_MONITOR_GUARD.update(
            {"target_id": state.target_id, "suppress_stop_until": time.monotonic() + 5.0}
        )
        upnp_control(device, "stop", None)
    except Exception:
        pass


def alsa_output_open(track, state, context):
    config = context.get("config") or {}
    item = context.get("item") or track.item
    lease = AUDIO_OUTPUT_LEASE.acquire("alsa-direct", state.target_id)
    if not lease.get("ok"):
        return {"ok": False, "message": lease.get("message"), "target_id": state.target_id}
    ok, message = start_dac_playback(state.target_id, item, config, safe_float(context.get("position")))
    if not ok:
        AUDIO_OUTPUT_LEASE.release("alsa-direct")
    with DAC_LOCK:
        strategy = dict(DAC_STATE.get("strategy") or {})
    return {
        "ok": ok,
        "message": message,
        "strategy": strategy,
        "target_id": state.target_id,
        "track_id": track.track_id,
    }


def alsa_output_command(command, state, context):
    config = context.get("config") or {}
    item = context.get("item")
    if not item:
        item_id = str(context.get("track_id") or "")
        if not item_id:
            with DAC_LOCK:
                item_id = str(DAC_STATE.get("item_id") or "")
        item = find_library_item(config, item_id) if item_id else None
    ok, message = dac_control(command.action, command.position, item, config)
    return {"ok": ok, "message": message, "target_id": state.target_id}


def alsa_output_close(state):
    try:
        dac_control("stop", None, None, {})
    except Exception:
        pass
    AUDIO_OUTPUT_LEASE.release("alsa-direct")


PLAYBACK_CORE.registry.register(
    DlnaPushOutput(
        on_open=dlna_output_open,
        on_command=dlna_output_command,
        on_close=dlna_output_close,
    )
)
PLAYBACK_CORE.registry.register(
    AlsaOutput(
        on_open=alsa_output_open,
        on_command=alsa_output_command,
        on_close=alsa_output_close,
    )
)
PLAYBACK_CORE.registry.register(MPD_OUTPUT)


def commit_config_update(server, update):
    """Persist a complete candidate before exposing it to running services."""
    with CONFIG_UPDATE_LOCK:
        candidate = copy.deepcopy(server.config)
        update(candidate)
        if not save_config(server.config_path, candidate):
            return False
        # Long-lived services retain this dictionary, so commit in place only
        # after the atomic disk write succeeds.
        server.config.clear()
        server.config.update(candidate)
        # Committing this dictionary is the only way the pool switch can move while
        # the service runs, so it is also where turning the switch off has to release
        # the handles it leaves behind. Runs after the in-place commit: the applier
        # reads the new value and the path it has to drain.
        apply_library_connection_pool_config(server.config)
        # The lyric cache budget follows the same discipline as the pool switch:
        # the committed dictionary is the only state a running service retrains
        # against, so a save that fails on the way to disk cannot drain entries.
        apply_lyrics_cache_config(server.config)
        return True


def payload_bytes_limit(payload, key, default=None):
    """Read an optional byte budget from a JSON payload without coercing it.

    Absent key means "leave the running value alone", which is what lets the
    pool switch and the cache budget share one endpoint without either wiping
    the other. A present-but-unusable value raises: clamping "4 MiB" or 0 to a
    legal number would save a setting the user never asked for.
    """
    if key not in payload:
        return default
    value = strict_bytes_limit_from_payload(payload.get(key))
    if value is None:
        raise ValueError("%s must be an integer byte count inside the supported range" % key)
    return value


def apply_lyrics_cache_config(config):
    """Retrain the running lyric caches against committed settings.

    A no-op when the metadata service has not been built yet; the budget still
    reaches the caches at construction time through `bytes_limit_from_config`.
    """
    applier = getattr(METADATA_SERVICE, "apply_lyrics_cache_config", None)
    if callable(applier):
        return applier(config)
    return bytes_limit_from_config(config)


def runtime_lyrics_cache_bytes_limit(config):
    """Report the budget the running caches enforce, else what they would start with.

    The service answer is only trusted when it is a plain integer: other suites
    substitute mocks, and a mock answer must not be echoed into JSON or stored
    as the apparent running value.
    """
    reader = getattr(METADATA_SERVICE, "lyrics_cache_bytes_limit", None)
    if callable(reader):
        try:
            value = reader()
        except (TypeError, ValueError):
            value = None
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return bytes_limit_from_config(config)


def payload_bool(payload, key, default=False):
    """Read an optional JSON boolean without truthiness-coercing strings."""
    if key not in payload:
        return default
    value = payload.get(key)
    if not isinstance(value, bool):
        raise ValueError("%s must be a boolean" % key)
    return value


def payload_target_id(payload):
    """Return a bounded target id, or None when an explicit value is invalid."""
    if not isinstance(payload, dict):
        return None
    if "target_id" in payload:
        value = payload.get("target_id")
    elif "device_id" in payload:
        value = payload.get("device_id")
    else:
        return "local"
    if value is None:
        return "local"
    if not isinstance(value, str):
        return None
    return normalize_target_id(value)


def http_worker_status(http_server):
    """Return bounded worker and long-lived event-stream pressure details."""
    worker_gate = getattr(http_server, "worker_gate", None)
    event_gate = getattr(http_server, "event_stream_gate", None)
    workers = worker_gate.snapshot() if worker_gate else {}
    events = event_gate.snapshot() if event_gate else {}
    if isinstance(workers, dict):
        workers = dict(workers)
    else:
        workers = {}
    workers["limit"] = getattr(http_server, "worker_limit", 0)
    workers["event_streams"] = events
    workers["event_stream_limit"] = getattr(http_server, "event_stream_limit", 0)
    return workers


class Handler(BaseHTTPRequestHandler):
    server_version = APP_USER_AGENT

    def log_message(self, fmt, *args):
        return

    def current_request_id(self):
        if not getattr(self, "_request_id", ""):
            self._request_id = request_id(self.headers.get("X-Request-ID"))
        return self._request_id

    def begin_request(self):
        self._request_started_at = time.monotonic()
        self._response_status = None
        self._request_recorded = False

    def send_response(self, code, message=None):
        self._response_status = int(code)
        return super().send_response(code, message)

    def send_error(self, code, message=None, explain=None):
        # Error pages are still HTTP responses: cap untrusted exception text
        # before BaseHTTPRequestHandler renders it into HTML.
        safe_message, safe_explain = project_error_text(message, explain)
        return super().send_error(code, safe_message, safe_explain)

    def finish_request_observation(self):
        if getattr(self, "_request_recorded", False):
            return
        status = getattr(self, "_response_status", None)
        if status is None:
            return
        self._request_recorded = True
        self.record_request(status)

    def run_request(self, callback, *args, **kwargs):
        self.begin_request()
        try:
            return callback(*args, **kwargs)
        finally:
            self.finish_request_observation()

    def record_request(self, status):
        status = int(status)
        started_at = getattr(self, "_request_started_at", time.monotonic())
        observation = observe_http_request(
            self.command,
            self.path,
            status,
            time.monotonic() - started_at,
        )
        OBSERVABILITY.count("http_requests_total")
        OBSERVABILITY.count(observation["status_counter"])
        OBSERVABILITY.record_http_latency_route(observation["latency_route"], observation["elapsed_seconds"])
        if observation["write_log"]:
            config = getattr(self.server, "config", {}) or {}
            OBSERVABILITY.write(
                config.get("structured_log_path") or os.path.join(os.path.dirname(getattr(self.server, "config_path", "") or "."), "fnaudio.jsonl"),
                "http_request",
                request_id=self.current_request_id(),
                method=self.command,
                route=observation["route"],
                latency_route=observation["latency_route"],
                duration_ms=round(observation["elapsed_seconds"] * 1000.0, 2),
                status=status,
            )

    def send_json(self, payload, status=200, extra_headers=None):
        body, valid = serialize_json_response(payload)
        if not valid:
            status = HTTPStatus.INTERNAL_SERVER_ERROR
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("X-Request-ID", self.current_request_id())
        # Dynamic API projections include library status and metadata results.
        # Prevent WebView/proxy HTTP caches from serving an older projection;
        # client-side bounded LRUs remain responsible for intentional reuse.
        if str(getattr(self, "path", "") or "").split("?", 1)[0].startswith("/api/"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
        for name, value in normalize_response_headers(extra_headers).items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command == "HEAD":
            return
        try:
            self.wfile.write(body)
        except (OSError, ValueError):
            # The response framing is already on the wire. Do not let a
            # failed or partial write make this keep-alive connection look
            # reusable to the HTTP server.
            self.close_connection = True

    def do_GET(self):
        return self.run_request(self.handle_get, head_only=False)

    def trim_api_token(self):
        return trim_api_token(self.headers)

    def authorize_api_request(self, method, path):
        # Requests relayed by our own CGI entry point never receive an fnOS
        # token on some fnOS releases. They are still confined to loopback;
        # allow that explicit internal channel for local settings such as
        # manually configured music roots.
        if (self.headers.get("X-Fnaudio-Internal") == "1"
                and self.client_address[0] in ("127.0.0.1", "::1")):
            return True
        scopes = (self.headers.get("X-Fnaudio-Scopes") or "").split(",")
        allowed, status, scope, message = authorize_api(
            self.client_address[0], method, path, self.trim_api_token(), scopes
        )
        if allowed:
            return True
        self.send_json({"ok": False, "error": message, "required_scope": scope}, status)
        return False

    def send_xml(self, body, status=200, content_type="text/xml; charset=utf-8", head_only=False):
        body, valid = serialize_xml_response(body)
        if not valid:
            status = HTTPStatus.INTERNAL_SERVER_ERROR
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            try:
                self.wfile.write(body)
            except (OSError, ValueError):
                self.close_connection = True

    def do_HEAD(self):
        return self.run_request(self.handle_get, head_only=True)

    def record_dlna(self, event, **values):
        try:
            context = request_context(self.headers, self.client_address)
            DLNA_DIAGNOSTICS.record(
                event,
                **context,
                **values,
            )
        except Exception:
            pass

    def handle_get(self, head_only=False):
        if not request_target_allowed(self.path):
            self.close_connection = True
            return self.send_error(414, "Request target too long")
        parsed = urllib.parse.urlparse(self.path)
        try:
            query = urllib.parse.parse_qs(parsed.query, max_num_fields=128)
        except ValueError:
            return self.send_json({"ok": False, "error": "too many query parameters"}, 400)
        path = parsed.path
        if path.startswith("/dlna/"):
            return self.handle_dlna_get(path, head_only)
        if path.startswith("/upnp/cover/"):
            return self.serve_upnp_cover(path.split("/", 3)[3], query, head_only)
        if path.startswith("/api/") and not self.authorize_api_request("HEAD" if head_only else "GET", path):
            return
        if requires_resource_auth(path) and not self.authorize_api_request("HEAD" if head_only else "GET", path):
            return
        if path == "/api/health":
            mpd = MPD_SERVICE.status() if MPD_SERVICE else {}
            metadata = METADATA_SERVICE.status() if METADATA_SERVICE else {}
            transcode = transcode_resource_status(self.server.config)
            return self.send_json(build_health_payload(
                server_name=self.server.config.get("server_name"),
                request_id=self.current_request_id(),
                mpd=mpd,
                scan_state=SCAN_STATE,
                metadata=metadata,
                transcode=transcode,
                dlna_running=bool(DLNA_PROTOCOL),
                renderer_count=len(cached_upnp_devices()),
                metrics=OBSERVABILITY.snapshot(),
                library_query_cache=library_query_cache_status(),
                library_search_index=library_search_index_status(self.server.config),
                thumbnail_prewarm=thumbnail_prewarm_status(),
                cover_cache=cover_cache_status(),
                cache_failures=library_cache_failure_status(),
                library_storage=library_storage_status(self.server.config),
                library_connection_pool=library_connection_pool_status(),
                dlna_discovery=upnp_cache_status(),
                dlna_eventing=DLNA_PROTOCOL.event_status() if DLNA_PROTOCOL else {},
                http_workers=http_worker_status(self.server),
                playback_command_cache=playback_command_cache_status(),
            ))
        if path == "/api/diagnostics":
            mpd = MPD_SERVICE.status() if MPD_SERVICE else {}
            metadata = METADATA_SERVICE.status() if METADATA_SERVICE else {}
            return self.send_json(support_snapshot(
                server_name=self.server.config.get("server_name"),
                mpd=mpd,
                scan_state=SCAN_STATE,
                metadata=metadata,
                transcode=transcode_resource_status(self.server.config),
                dlna_available=bool(DLNA_PROTOCOL),
                renderer_count=len(cached_upnp_devices()),
                metrics=OBSERVABILITY.snapshot(),
                playback=PLAYBACK_CORE.snapshot(),
                library_query_cache=library_query_cache_status(),
                library_search_index=library_search_index_status(self.server.config),
                thumbnail_prewarm=thumbnail_prewarm_status(),
                cover_cache=cover_cache_status(),
                cache_failures=library_cache_failure_status(),
                library_storage=library_storage_status(self.server.config),
                library_connection_pool=library_connection_pool_status(),
                dlna_discovery=upnp_cache_status(),
                dlna_eventing=DLNA_PROTOCOL.event_status() if DLNA_PROTOCOL else {},
                http_workers=http_worker_status(self.server),
                playback_command_cache=playback_command_cache_status(),
            ))
        if path == "/api/config/runtime":
            # The pane has to show what the process actually does right now, so the
            # value is read through the pool's own predicate instead of a default the
            # handler invents; `status` rides along because the drain on the way off
            # is the observable proof the toggle was not a no-op.
            return self.send_json({
                "ok": True,
                "config": {
                    library_connection_pool_config_key(): library_connection_pool_enabled(self.server.config),
                    LYRICS_CACHE_BYTES_CONFIG_KEY: runtime_lyrics_cache_bytes_limit(self.server.config),
                },
                "status": library_connection_pool_status(),
            })
        if path == "/api/access":
            return self.send_json(public_access(self))
        if path == "/api/state/user":
            return self.send_json({"ok": True, "state": load_user_state(self.server.config)})
        if path == "/api/library":
            if query.get("paged") == ["1"]:
                if query.get("refresh") == ["1"]:
                    library_items(self.server.config, True)
                page = query_library_page(self.server.config, query)
                prewarm_thumbnails(page.get("items"), self.server.config, cached_cover_for_item)
                if METADATA_SERVICE:
                    page = METADATA_SERVICE.enrich_track_page(page)
                page = public_library_page(page, self.server.config)
                return self.send_json(page)
            compat_query = dict(query)
            compat_query.setdefault("paged", ["1"])
            compat_query.setdefault("limit", ["120"])
            compat_query.setdefault("offset", ["0"])
            page = query_library_page(self.server.config, compat_query)
            prewarm_thumbnails(page.get("items"), self.server.config, cached_cover_for_item)
            if METADATA_SERVICE:
                page = METADATA_SERVICE.enrich_track_page(page)
            page = public_library_page(page, self.server.config)
            page["message"] = "Use paged=1 for large libraries"
            return self.send_json(page)
        if path == "/api/library/groups":
            view = (query.get("view") or [""])[0]
            search = (query.get("search") or [""])[0]
            artist = (query.get("artist") or [""])[0]
            composer = (query.get("composer") or [""])[0]
            if query.get("paged") == ["1"]:
                limit = query.get("limit", ["100"])[0]
                offset = query.get("offset", ["0"])[0]
                cursor = query.get("cursor", [""])[0]
                sort_dir = (query.get("dir") or ["asc"])[0]
                result = query_library_groups(self.server.config, view, search, limit, offset, sort_dir, artist, composer, cursor)
                return self.send_json(METADATA_SERVICE.enrich_groups(view, result) if METADATA_SERVICE else result)
            sort_dir = (query.get("dir") or ["asc"])[0]
            result = {"groups": query_library_groups(self.server.config, view, search, sort_dir=sort_dir, artist=artist, composer=composer)}
            return self.send_json(METADATA_SERVICE.enrich_groups(view, result) if METADATA_SERVICE else result)
        if path == "/api/library/folders":
            parent = (query.get("parent") or [""])[0]
            root = (query.get("root") or [""])[0]
            search = (query.get("search") or [""])[0]
            sort_dir = (query.get("dir") or ["asc"])[0]
            if query.get("paged") == ["1"]:
                cursor = query.get("cursor", [""])[0]
                return self.send_json(query_library_folders(self.server.config, parent, root, sort_dir, (query.get("limit") or ["100"])[0], (query.get("offset") or ["0"])[0], search, cursor))
            return self.send_json({"folders": query_library_folders(self.server.config, parent, root, sort_dir, search=search)})
        if path == "/api/library/roots":
            search = (query.get("search") or [""])[0]
            return self.send_json({"roots": query_library_root_folders(self.server.config, search)})
        if path == "/api/library/items":
            raw_ids = (query.get("ids") or [""])[0]
            try:
                ids = parse_library_item_ids(raw_ids)
            except ValueError:
                return self.send_json({"ok": False, "error": "too many item ids; request at most 120"}, HTTPStatus.BAD_REQUEST)
            items = query_library_items_by_ids(self.server.config, ids)
            # Queue/favorites restoration uses this bounded hydration route.
            # Apply the same persisted metadata projection as the main page so
            # a restored row does not briefly lose cached artwork/album fields
            # and then get corrected by a second full-library request.
            if METADATA_SERVICE and items:
                try:
                    items = METADATA_SERVICE.enrich_track_page({"items": items}).get("items", items)
                except Exception:
                    # Metadata enrichment is best-effort; hydration must still
                    # return the authoritative library rows on cache errors.
                    pass
            return self.send_json({"items": [public_item(x, self.server.config) for x in items]})
        if path == "/api/library/location":
            item_id = (query.get("id") or [""])[0]
            location = query_library_item_location(self.server.config, item_id)
            if not location:
                return self.send_json({"ok": False, "message": "歌曲文件不存在或不在音乐目录中"}, HTTPStatus.NOT_FOUND)
            return self.send_json({"ok": True, **location})
        if path == "/api/library/status":
            library_items(self.server.config, query.get("refresh") == ["1"])
            return self.send_json(library_status(self.server.config))
        if path == "/api/metadata/status":
            return self.send_json(METADATA_SERVICE.status() if METADATA_SERVICE else {"ok": False, "running": False})
        if path == "/api/metadata/track":
            track_id = normalize_track_id((query.get("track_id") or [""])[0])
            if not track_id:
                return self.send_json({"ok": False, "message": "Missing track_id"}, HTTPStatus.BAD_REQUEST)
            retry = str((query.get("retry") or [""])[0]).strip().lower() in ("1", "true", "yes")
            # Read an already persisted projection before gating on worker
            # liveness.  A short worker restart must not hide usable metadata
            # that is already in SQLite behind a 503 response.  Only a lookup
            # that still needs queueing is considered unavailable.
            cached_result = None
            if METADATA_SERVICE:
                try:
                    cached_result = METADATA_SERVICE.track_match(track_id, retry_failed=retry)
                except Exception:
                    cached_result = None
            else:
                # During cold startup the library can be ready a moment
                # before the metadata worker is constructed. Return local
                # tags immediately instead of making the client treat the
                # track as an empty/failed provider result.
                local_item = find_library_item(self.server.config, track_id) or {}
                local_projection = local_cached_projection(track_id, local_item)
                # An entirely untagged file still needs the normal retryable
                # pending response; an empty ``status: local`` result would
                # make the client stop its provider recovery loop.
                if local_projection.get("best") or local_projection.get("lyrics"):
                    return self.send_json(local_projection)
            if has_cached_track_projection(cached_result):
                return self.send_json(cached_result)
            # A queued interactive lookup is still a usable state even when
            # its worker is between restarts.  Do not turn that transient
            # state into a 503, but still probe the lane once: returning a
            # pending result *before* the lazy-recovery probe left a dead
            # worker pool with jobs that could never run.  That looked like
            # metadata fetching had silently stopped after a service restart.
            if is_pending_result(cached_result):
                metadata_service_available(METADATA_SERVICE, "fetch")
                # Keep authoritative local tags/artwork visible while the
                # provider lane is pending.  Returning an empty ``best``
                # projection here made the UI temporarily erase useful
                # metadata and look as if fetching had stopped.  Merge only
                # presentation-safe local fields; provider status and retry
                # semantics remain unchanged.
                local_item = find_library_item(self.server.config, track_id) or {}
                local_projection = local_cached_projection(track_id, local_item)
                merged = merge_pending_projection(cached_result, local_projection)
                return self.send_json({**merged, "retryable": True})
            if not metadata_service_available(METADATA_SERVICE, "fetch"):
                # Keep an interactive request usable during a short worker
                # outage.  The library row is authoritative for local tags;
                # return those fields as a presentation-only pending result
                # instead of a hard 503 that made the UI look as if metadata
                # had disappeared.  The retryable marker lets the client
                # re-arm the bounded provider lookup once workers recover.
                local_item = find_library_item(self.server.config, track_id) or {}
                return self.send_json(local_pending_projection(
                    track_id, local_item, "后台元数据服务没有启动"
                ))
            # A healthy worker can still race with a freshly-created service
            # and return ``None`` for one request (for example while the
            # library row is being indexed).  Never project that transport
            # shape directly to the UI: it looks like metadata has vanished
            # and stops the client's recovery loop.  Keep the local Tag/file
            # name visible as a bounded, retryable presentation fallback.
            try:
                result = cached_result if cached_result is not None else METADATA_SERVICE.track_match(track_id, retry_failed=retry)
            except Exception:
                # A transient SQLite/worker failure must not turn an
                # interactive metadata request into an opaque HTTP 500. Keep
                # local tags/lyrics/artwork visible and let the bounded client
                # retry lane recover once the service is healthy again.
                local_item = find_library_item(self.server.config, track_id) or {}
                return self.send_json(local_pending_projection(
                    track_id, local_item, "元数据服务暂时不可用"
                ))
            has_projection = isinstance(result, dict) and any(
                key in result for key in ("status", "best", "candidates", "pending", "image_url", "lyrics")
            )
            if not has_projection:
                local_item = find_library_item(self.server.config, track_id) or {}
                return self.send_json(local_pending_projection(
                    track_id, local_item, "元数据正在准备中"
                ))
            return self.send_json(result)
        if path.startswith("/metadata/artwork/"):
            asset_id = path.rsplit("/", 1)[-1]
            return self.serve_metadata_artwork(asset_id, head_only, query)
        if path == "/api/artwork":
            kind = (query.get("kind") or [""])[0]
            q = (query.get("q") or [""])[0]
            if kind not in ("album", "artist"):
                return self.send_json({"image_url": ""})
            return self.send_json(METADATA_SERVICE.cached_entity(kind, q) if METADATA_SERVICE else {"image_url": ""})
        if path == "/api/album-metadata":
            return self.send_json(METADATA_SERVICE.cached_entity("album", (query.get("q") or [""])[0], (query.get("artist") or [""])[0]) if METADATA_SERVICE else {"artist": "", "release_date": ""})
        if path == "/api/lyrics":
            item_id = normalize_track_id((query.get("track_id") or [""])[0])
            if not item_id:
                return self.send_json({"error": "invalid track_id"}, HTTPStatus.BAD_REQUEST)
            item = find_library_item(self.server.config, item_id)
            if not item:
                return self.send_json({"error": "track not found"}, 404)
            retry_failed = (query.get("retry") or [""])[0] == "1"
            if METADATA_SERVICE is None:
                # Embedded lyrics are authoritative and available before the
                # provider workers finish starting. Return them immediately;
                # otherwise preserve the existing retryable pending response.
                local = local_lyrics_projection(item)
                if local:
                    return self.send_json(local)
            # Read local/SQLite lyrics first.  A dead provider worker must not
            # hide embedded lyrics or an already cached response.  Only a
            # genuinely pending lookup needs a live priority lane.
            result = METADATA_SERVICE.lyrics(item_id, retry_failed=retry_failed) if METADATA_SERVICE else None
            if has_cached_lyrics(result):
                return self.send_json(result)
            # Preserve an already queued priority lookup as a normal pending
            # response during the tiny worker-restart window.  Probe the lane
            # first so a dead priority worker is recreated, while retaining
            # the same pending response for the client rather than surfacing
            # a hard error during startup.
            if is_pending_result(result):
                metadata_service_available(METADATA_SERVICE, "lyrics")
                return self.send_json({**result, "retryable": True})
            if not metadata_service_available(METADATA_SERVICE, "lyrics"):
                return self.send_json(lyrics_pending_projection("后台元数据服务正在恢复，将自动重试"))
            return self.send_json(result or {"lyrics": "", "source": "", "pending": False})
        if path == "/api/fs/list":
            dirs = list_music_directories((query.get("path") or [""])[0])
            return self.send_json({"path": (query.get("path") or [""])[0], "dirs": dirs})
        if path == "/api/upnp/devices":
            if upnp_cache_needs_refresh():
                refresh_upnp_cache_background()
            return self.send_json({"devices": cached_upnp_devices()})
        if path == "/api/dac/devices":
            aplay = find_aplay()
            libasound = find_libasound()
            devices = alsa_devices()
            available = bool(aplay or libasound)
            message = "" if available else "未找到 aplay 或 libasound，暂时无法直接输出到 USB DAC"
            return self.send_json({"devices": devices, "available": available, "message": message, "backend": "aplay" if aplay else ("libasound" if libasound else "")})
        if path == "/api/dac/status":
            return self.send_json(dac_public_status())
        if path == "/api/mpd/status":
            return self.send_json(MPD_OUTPUT.status())
        if path == "/api/upmpdcli/status":
            return self.send_json(upmpdcli_probe())
        if path == "/api/airplay/status":
            payload = AIRPLAY_SERVICE.status() if AIRPLAY_SERVICE else airplay_probe(self.server.config, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
            return self.send_json(payload)
        if path == "/api/dlna/renderer/status":
            if not DLNA_PROTOCOL:
                return self.send_json({"available": False, "message": "DLNA renderer is not initialized"}, 503)
            return self.send_json({"available": True, "state": DLNA_PROTOCOL.renderer.snapshot()})
        if path == "/api/dlna/capabilities":
            if not DLNA_PROTOCOL:
                return self.send_json({"available": False, "message": "DLNA service is not initialized"}, 503)
            return self.send_json({
                "available": True,
                "media_server_source": DLNA_PROTOCOL.protocol_info("server"),
                "renderer_sink": DLNA_PROTOCOL.protocol_info("renderer"),
                "mpd_output": (MPD_SERVICE.output_capabilities() if MPD_SERVICE else {}),
            })
        if path == "/api/dlna/diagnostics":
            return self.send_json({
                "available": bool(DLNA_PROTOCOL),
                "eventing": DLNA_PROTOCOL.event_status() if DLNA_PROTOCOL else {},
                **DLNA_DIAGNOSTICS.snapshot(),
            })
        if path == "/api/playback/targets":
            refresh = str((query.get("refresh") or [""])[0]).lower() in ("1", "true", "yes")
            return self.send_json(playback_targets_payload(force_refresh=refresh))
        if path == "/api/playback/status":
            payload, status = playback_status(query)
            return self.send_json(payload, status)
        if path == "/api/playback/events":
            return self.stream_playback_events(query)
        if path == "/api/playback/core":
            return self.send_json(
                {
                    "state": PLAYBACK_CORE.snapshot(),
                    "plugins": PLAYBACK_CORE.registry.describe(),
                }
            )
        if path == "/api/upnp/status":
            device_id = (query.get("device_id") or [""])[0]
            devices = cached_upnp_devices() or discover_upnp()
            device = next((x for x in devices if x["id"] == device_id), None)
            if not device:
                return self.send_json({"error": "device not found"}, 404)
            try:
                payload = {"transport": upnp_transport_state(device), "position": upnp_position_info(device)}
                return self.send_json(payload)
            except Exception as exc:
                return self.send_json({"error": str(exc)}, 502)
        if path == "/api/transcode/status":
            item_id = (query.get("track_id") or [""])[0]
            mode = (query.get("mode") or ["mp3"])[0]
            if mode != "mp3":
                return self.send_json({"error": "unsupported cache mode"}, 400)
            item = find_library_item(self.server.config, item_id)
            if not item:
                return self.send_json({"error": "track not found"}, 404)
            _, mime, ready = transcode_cache_ready(item, self.server.config, mode)
            return self.send_json({"ready": ready, "mode": mode, "mime": mime})
        if path.startswith("/cover/"):
            return self.serve_cover(path.split("/", 2)[2], query, head_only)
        if path.startswith("/cover-asset/"):
            return self.serve_cover_asset(path.split("/", 2)[2], query, head_only)
        if path.startswith("/upnp/media/"):
            return self.serve_upnp_media(path[len("/upnp/media/"):], query, head_only)
        if path.startswith("/media/"):
            return self.serve_media(path.split("/", 2)[2], query, head_only)
        return self.serve_static(path, query, head_only)

    def do_POST(self):
        return self.run_request(self._do_post)

    def _do_post(self):
        try:
            return self.handle_post()
        except Exception as exc:
            config = getattr(self.server, "config", {}) or {}
            OBSERVABILITY.write(
                config.get("structured_log_path")
                or os.path.join(os.path.dirname(getattr(self.server, "config_path", "") or "."), "fnaudio.jsonl"),
                "http_post_error",
                request_id=self.current_request_id(),
                route=urllib.parse.urlparse(self.path).path,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            message = str(exc) or "playback request failed"
            return self.send_json({"ok": False, "message": message, "error": message}, 500)

    def do_SUBSCRIBE(self):
        return self.run_request(self.handle_dlna_subscription, False)

    def do_UNSUBSCRIBE(self):
        return self.run_request(self.handle_dlna_subscription, True)

    def stream_playback_events(self, query):
        """Stream authoritative playback snapshots without polling an output.

        Backend monitors already merge MPD/DAC/renderer changes into
        ``PLAYBACK_CORE``.  This endpoint only waits for that state version to
        change, keeping one output owner even with several Web UIs connected.
        """
        requested_target = target_id_from_query(query)
        http_server = getattr(self, "server", None)
        event_gate = getattr(http_server, "event_stream_gate", None)
        event_limit = getattr(http_server, "event_stream_limit", 0)
        admitted = bool(event_gate and event_gate.try_acquire(event_limit))
        if event_gate and not admitted:
            return self.send_json({"ok": False, "error": "playback event stream busy"}, 503, {"Retry-After": "1"})
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-transform")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            last_version = -1
            while True:
                # ``wait_for_version`` blocks until a backend monitor or
                # control command changes state. A timeout merely emits an
                # SSE heartbeat, so idle clients consume no polling loop.
                PLAYBACK_CORE.wait_for_version(last_version, 15.0)
                core, core_item = PLAYBACK_CORE.snapshot_with_item()
                version = safe_int(core.get("state_version"))
                if snapshot_changed(version, last_version):
                    payload = playback_event_payload(core, requested_target, core_item)
                    self.wfile.write(snapshot_frame(version, payload))
                    self.wfile.flush()
                    last_version = version
                else:
                    self.wfile.write(keepalive_frame())
                    self.wfile.flush()
        # Buffered socket writers may raise ValueError after a peer has
        # disconnected and the handler closes the file object underneath us.
        # It is equivalent to the transport errors above for an SSE stream.
        except (BrokenPipeError, ConnectionResetError, OSError, ValueError):
            return
        finally:
            if admitted:
                event_gate.release()

    def handle_dlna_subscription(self, unsubscribe=False):
        if not request_target_allowed(self.path):
            self.close_connection = True
            return self.send_error(414, "Request target too long")
        # SUBSCRIBE and UNSUBSCRIBE use only headers. BaseHTTPRequestHandler
        # will not consume a body here, so reject one before it can be parsed
        # as the next request on a persistent connection.
        if str(self.headers.get("Transfer-Encoding") or "").strip():
            self.close_connection = True
            return self.send_error(400, "transfer encoding is unsupported")
        body_length = request_body_length(self.headers.get("Content-Length"), 0)
        if body_length is None:
            self.close_connection = True
            return self.send_error(400, "invalid content length")
        if body_length:
            self.close_connection = True
            return self.send_error(400, "DLNA subscriptions do not accept request bodies")
        if not DLNA_PROTOCOL:
            return self.send_error(503, "DLNA service is not initialized")
        path = urllib.parse.urlparse(self.path).path
        parts = [part for part in path.split("/") if part]
        if len(parts) != 4 or parts[0] != "dlna" or parts[1] not in ("renderer", "server") or parts[2] not in ("avtransport", "rendering", "connection", "content") or parts[3] != "event":
            return self.send_error(404)
        sid = str(self.headers.get("SID") or "")
        if unsubscribe:
            self.record_dlna("unsubscribe", path=path)
            if not sid or not DLNA_PROTOCOL.unsubscribe(sid):
                return self.send_error(412, "unknown subscription")
            self.send_response(200)
            self.end_headers()
            return
        try:
            callback = self.headers.get("CALLBACK", "")
            self.record_dlna("subscribe", path=path, callback=callback)
            subscription_id, seconds = DLNA_PROTOCOL.subscribe(parts[1], parts[2], callback, sid, self.headers.get("TIMEOUT", ""))
        except ValueError as exc:
            return self.send_error(412, str(exc))
        self.send_response(200)
        self.send_header("SID", subscription_id)
        self.send_header("TIMEOUT", "Second-%s" % seconds)
        self.send_header("Content-Length", "0")
        self.end_headers()
        # A new subscriber must receive an initial state snapshot.
        DLNA_PROTOCOL.events.notify_renderer(DLNA_PROTOCOL.renderer.snapshot())

    def handle_post(self):
        if not request_target_allowed(self.path):
            self.close_connection = True
            return self.send_error(414, "Request target too long")
        parsed = urllib.parse.urlparse(self.path)
        try:
            urllib.parse.parse_qs(parsed.query, max_num_fields=128)
        except ValueError:
            return self.send_json({"ok": False, "error": "too many query parameters"}, 400)
        # BaseHTTPRequestHandler does not decode chunked request bodies.
        # Refuse Transfer-Encoding explicitly, including requests that also
        # provide Content-Length, so unread chunks cannot poison a reused
        # connection or create a request-smuggling ambiguity.
        if str(self.headers.get("Transfer-Encoding") or "").strip():
            self.close_connection = True
            return self.send_json({"ok": False, "error": "transfer encoding is unsupported"}, 400)
        if parsed.path.startswith("/api/") and not self.authorize_api_request("POST", parsed.path):
            return
        raw_length = self.headers.get("Content-Length")
        length = request_body_length(raw_length, MAX_REQUEST_BODY_BYTES)
        if length is None:
            return self.send_json({"ok": False, "error": "invalid content length"}, 400)
        if length > MAX_REQUEST_BODY_BYTES:
            return self.send_json({"ok": False, "error": "request body is too large"}, 413)
        raw = read_complete_request_body(self.rfile, length) if length else b"{}"
        if raw is None:
            # A peer can close after declaring Content-Length. Do not accept a
            # valid JSON prefix as a complete command, and do not reuse a
            # connection whose framing was incomplete.
            self.close_connection = True
            return self.send_json({"ok": False, "error": "incomplete request body"}, 400)
        if parsed.path.startswith("/dlna/"):
            return self.handle_dlna_post(parsed.path, raw)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError):
            return self.send_json({"error": "invalid json"}, 400)
        # Every JSON API POST below consumes named fields. Reject valid JSON
        # scalars/arrays at the boundary so malformed shapes return a client
        # error instead of falling through to an opaque 500 exception.
        if not isinstance(payload, dict):
            return self.send_json({"ok": False, "error": "invalid payload"}, 400)
        if parsed.path == "/api/player/state":
            return self.send_json(
                apply_legacy_player_state(payload, STATE, PLAYBACK_CORE),
                extra_headers=legacy_response_headers(parsed.path),
            )
        if parsed.path == "/api/state/user":
            try:
                revision = payload.get("revision")
                expected_revision = None
                if revision is not None:
                    expected_revision = strict_nonnegative_int(revision, maximum=10**12)
                    if expected_revision is None:
                        return self.send_json({"ok": False, "error": "revision must be a nonnegative integer"}, 400)
                return self.send_json({"ok": True, "state": save_user_state(self.server.config, payload, expected_revision)})
            except StateConflict:
                return self.send_json({"ok": False, "error": "state conflict", "state": load_user_state(self.server.config)}, 409)
        if parsed.path == "/api/library/scan/cancel":
            cancelled = cancel_library_refresh()
            return self.send_json({"ok": True, "cancelled": cancelled, "status": library_status(self.server.config)})
        if parsed.path == "/api/playback/load":
            response, status = playback_load(self, payload)
            return self.send_json(response, status)
        if parsed.path == "/api/playback/target":
            target_id = payload_target_id(payload)
            if target_id is None:
                return self.send_json({"ok": False, "error": "target_id must be text"}, 400)
            target_kind = playback_target_kind(target_id)
            # Selecting a renderer is already a state transition: set_target
            # closes the previous output and clears transport state. Refuse a
            # disappeared DLNA id here, not only when a later load/control
            # command reaches the output adapter.
            if target_kind == "dlna_push" and not find_upnp_device(target_id):
                return self.send_json({
                    "ok": False,
                    "error": "playback_target_not_found",
                    "message": "playback target not found",
                }, 404)
            normalized = target_id
            previous = PLAYBACK_CORE.snapshot()
            revision = save_playback_target_session(
                self.server.config, previous, normalized, target_kind
            )
            if revision is None:
                # Persist the candidate before closing the current output. A
                # failed write must leave both playback and the durable target
                # untouched.
                return self.send_json(playback_persistence_failure(target_kind)[0], 503)
            try:
                PLAYBACK_CORE.set_target(normalized, target_kind)
            except Exception:
                # The runtime transition is unusual but can fail in a plugin.
                # Restore the durable snapshot so a later restart does not
                # resurrect a target that never became active.
                try:
                    save_playback_session(self.server.config, project_playback_session(previous, safe_float=safe_float))
                except Exception:
                    pass
                return self.send_json({
                    "ok": False,
                    "error": "playback_target_transition_failed",
                    "message": "播放设备切换失败",
                    "core": PLAYBACK_CORE.snapshot(),
                }, 503)
            return self.send_json({
                "ok": True,
                "target_id": normalized,
                "target_kind": target_kind,
                "core": PLAYBACK_CORE.snapshot(),
                "revision": revision,
            })
        if parsed.path == "/api/airplay/control":
            if not AIRPLAY_SERVICE:
                return self.send_json({"ok": False, "message": "AirPlay service is not initialized"}, 503)
            raw_action = payload.get("action")
            action = raw_action.lower() if isinstance(raw_action, str) else ""
            if action == "start":
                result = AIRPLAY_SERVICE.start()
            elif action == "stop":
                result = AIRPLAY_SERVICE.stop()
            elif action == "restart":
                AIRPLAY_SERVICE.stop()
                result = AIRPLAY_SERVICE.start()
            else:
                return self.send_json({"ok": False, "message": "unknown AirPlay action"}, 400)
            return self.send_json(result, 200 if isinstance(result, dict) and result.get("ok") is True else 409)
        if parsed.path == "/api/playback/queue":
            response, status = playback_queue(self.server.config, payload)
            return self.send_json(response, status)
        if parsed.path == "/api/playback/control":
            response, status = playback_control_idempotent(self, payload)
            return self.send_json(response, status)
        if parsed.path == "/api/transcode/warm":
            item_id = normalize_track_id(payload.get("track_id"))
            raw_mode = payload.get("mode", "mp3")
            mode = raw_mode if isinstance(raw_mode, str) else ""
            if mode != "mp3":
                return self.send_json({"ok": False, "message": "unsupported cache mode"}, 400)
            item = find_library_item(self.server.config, item_id)
            if not item:
                return self.send_json({"ok": False, "message": "track not found"}, 404)
            _target, mime, ready = transcode_cache_ready(item, self.server.config, mode)
            queued = False if ready else warm_transcode_cache(item, self.server.config, mode, priority=0)
            return self.send_json({"ok": True, "mode": mode, "mime": mime, "ready": ready, "queued": queued})
        if parsed.path == "/api/upnp/push":
            response, status = playback_load(self, legacy_load_payload(payload))
            return self.send_json(response, status, legacy_response_headers(parsed.path))
        if parsed.path == "/api/dac/push":
            response, status = playback_load(self, legacy_load_payload(payload))
            return self.send_json(response, status, legacy_response_headers(parsed.path))
        if parsed.path == "/api/upnp/control":
            response, status = playback_control(self, legacy_control_payload(payload))
            return self.send_json(response, status, legacy_response_headers(parsed.path))
        if parsed.path == "/api/dac/control":
            dac_target_id = payload.get("device_id")
            if not dac_target_id:
                with DAC_LOCK:
                    dac_target_id = DAC_STATE.get("device_id")
            response, status = playback_control(self, legacy_control_payload(payload, dac_target_id))
            return self.send_json(response, status, legacy_response_headers(parsed.path))
        if parsed.path == "/api/config/metadata":
            try:
                grace_value = strict_nonnegative_int(
                    payload.get("orphan_grace_days", self.server.config.get("metadata_orphan_grace_days", 7)),
                    maximum=90,
                )
                if grace_value is None:
                    raise ValueError("invalid orphan grace days")
                grace_days = grace_value
                metadata_enabled = payload_bool(payload, "enabled", self.server.config.get("metadata_enabled", False))
                tag_write_enabled = payload_bool(
                    payload, "tag_write_enabled", self.server.config.get("metadata_tag_write_enabled", False)
                )
                refresh = payload_bool(payload, "refresh", False)
            except (TypeError, ValueError):
                return self.send_json({"ok": False, "message": "元数据设置包含无效值：宽限天数必须是 0-90 的整数，开关必须是布尔值"}, 400)
            if not commit_config_update(
                self.server,
                lambda candidate: candidate.update({
                    "metadata_enabled": metadata_enabled,
                    "metadata_tag_write_enabled": tag_write_enabled,
                    "metadata_orphan_grace_days": grace_days,
                }),
            ):
                return self.send_json({"ok": False, "message": "保存元数据设置失败"}, 500)
            if METADATA_SERVICE:
                METADATA_SERVICE.wake(force=refresh)
            return self.send_json({"ok": True, "status": METADATA_SERVICE.status() if METADATA_SERVICE else {}})
        if parsed.path == "/api/metadata/refresh":
            if not METADATA_SERVICE:
                return self.send_json({"ok": False, "message": "后台元数据服务没有启动"}, 503)
            METADATA_SERVICE.wake(force=True)
            return self.send_json({"ok": True, "message": "已加入后台补全队列"})
        if parsed.path == "/api/metadata/retry-tag-writes":
            if not METADATA_SERVICE:
                return self.send_json({"ok": False, "message": "Metadata service is not running"}, 503)
            if not self.server.config.get("metadata_tag_write_enabled", False):
                return self.send_json({"ok": False, "message": "请先开启歌曲 Tag 写回"}, 409)
            retried = METADATA_SERVICE.retry_failed_tag_writes()
            return self.send_json({"ok": True, "retried": retried, "status": METADATA_SERVICE.status()})
        if parsed.path == "/api/metadata/track/apply":
            if not METADATA_SERVICE:
                return self.send_json({"ok": False, "message": "Metadata service is not running"}, 503)
            track_id = normalize_track_id(payload.get("track_id"))
            if not track_id:
                return self.send_json({"ok": False, "message": "Missing track_id"}, 400)
            candidate_index = strict_nonnegative_int(payload.get("candidate_index", 0))
            if candidate_index is None:
                return self.send_json({"ok": False, "message": "candidate_index must be a non-negative integer"}, 400)
            if not METADATA_SERVICE.apply_track_match(track_id, candidate_index):
                return self.send_json({"ok": False, "message": "No matching candidate is available for this track"}, 404)
            return self.send_json({"ok": True, "status": METADATA_SERVICE.track_match(track_id)})
        if parsed.path == "/api/config/runtime":
            pool_key = library_connection_pool_config_key()
            try:
                pool_enabled = payload_bool(
                    payload,
                    pool_key,
                    library_connection_pool_enabled(self.server.config),
                )
            except (TypeError, ValueError):
                # Reject, never coerce: `"false"` and `0` must not flip a switch that
                # decides whether the library index stays open on disk.
                return self.send_json(
                    {"ok": False, "message": "运行设置包含无效值：曲库连接池必须是布尔值"}, 400
                )
            try:
                lyrics_budget = payload_bytes_limit(
                    payload,
                    LYRICS_CACHE_BYTES_CONFIG_KEY,
                    bytes_limit_from_config(self.server.config),
                )
            except (TypeError, ValueError):
                # Reject, never clamp: the budget is bounded by what a single
                # lyric document can need as well as by memory.
                return self.send_json(
                    {"ok": False, "message": "运行设置包含无效值：歌词缓存预算必须是范围内的整数字节数"}, 400
                )
            if not commit_config_update(
                self.server,
                lambda candidate: candidate.update({
                    pool_key: pool_enabled,
                    LYRICS_CACHE_BYTES_CONFIG_KEY: lyrics_budget,
                }),
            ):
                return self.send_json({"ok": False, "message": "保存运行设置失败"}, 500)
            # commit_config_update already re-applied the pool switch against the
            # committed dictionary, so a turn-off has drained its idle handles before
            # this response claims success.  No restart is needed for this key; the
            # port in the same pane still is, and that wording stays where it is.
            return self.send_json({
                "ok": True,
                "restart_required": False,
                "config": {
                    pool_key: library_connection_pool_enabled(self.server.config),
                    LYRICS_CACHE_BYTES_CONFIG_KEY: runtime_lyrics_cache_bytes_limit(self.server.config),
                },
                "status": library_connection_pool_status(),
            })
        if parsed.path == "/api/config/library":
            raw_library_path = payload.get("library_path", "")
            if not isinstance(raw_library_path, str):
                return self.send_json({"ok": False, "message": "音乐目录必须是文本"}, 400)
            candidate_paths = []
            # Scan a bounded window larger than the final root limit so empty
            # and duplicate separators do not consume valid directory slots.
            for value in re.split(r"[\r\n;]+", raw_library_path)[:MAX_LIBRARY_PATHS * 4]:
                text = value.strip()
                if not text:
                    continue
                candidate_paths.append(canonical_library_path(text))
                if len(candidate_paths) >= MAX_LIBRARY_PATHS:
                    break
            if not candidate_paths:
                return self.send_json({"ok": False, "message": "请输入音乐目录"}, 400)
            bad_path = next((x for x in candidate_paths if not is_allowed_library_path(x) or not os.path.isdir(x)), "")
            if bad_path:
                return self.send_json({"ok": False, "message": "这个目录不能作为音乐目录：%s" % bad_path}, 400)
            if not commit_config_update(
                self.server,
                lambda candidate: apply_library_paths(candidate, candidate_paths),
            ):
                return self.send_json({"ok": False, "message": "保存设置失败"}, 500)
            # The configured roots are part of the visible root projection.
            # Retire cached pages immediately after the atomic config commit;
            # waiting for the short cache TTL can otherwise show old roots.
            invalidate_library_query_cache(self.server.config)
            return self.send_json({"ok": True, "restart_required": False, "status": library_status(self.server.config)})
        return self.send_json({"error": "not found"}, 404)

    def handle_dlna_get(self, path, head_only=False):
        if not DLNA_PROTOCOL:
            return self.send_error(503, "DLNA service is not initialized")
        parts = [part for part in path.split("/") if part]
        if len(parts) == 3 and parts[0] == "dlna" and parts[2] == "description.xml" and parts[1] in ("renderer", "server"):
            self.record_dlna("description", role=parts[1])
            return self.send_xml(DLNA_PROTOCOL.description(parts[1]), head_only=head_only)
        if len(parts) == 3 and parts[:2] == ["dlna", "scpd"] and parts[2].endswith(".xml"):
            name = parts[2][:-4]
            services = {"avtransport": "urn:schemas-upnp-org:service:AVTransport:1", "rendering": "urn:schemas-upnp-org:service:RenderingControl:1", "connection": "urn:schemas-upnp-org:service:ConnectionManager:1", "content": "urn:schemas-upnp-org:service:ContentDirectory:1"}
            if name in services:
                self.record_dlna("scpd", service=name)
                return self.send_xml(dlna_scpd(services[name]), head_only=head_only)
        return self.send_error(404)

    def handle_dlna_post(self, path, raw):
        if not DLNA_PROTOCOL:
            return self.send_error(503, "DLNA service is not initialized")
        parts = [part for part in path.split("/") if part]
        if len(parts) == 4 and parts[0] == "dlna" and parts[2] in ("avtransport", "rendering", "connection", "content") and parts[3] == "control" and parts[1] in ("renderer", "server"):
            self.record_dlna("soap", role=parts[1], service=parts[2], action=self.headers.get("SOAPACTION", ""))
            status, body = DLNA_PROTOCOL.control(parts[1], parts[2], raw, self.headers.get("SOAPACTION", ""))
            return self.send_xml(body, status=status)
        return self.send_error(404)

    def serve_static(self, path, query=None, head_only=False):
        if path in ("", "/"):
            path = "/index.html"
        relative = urllib.parse.unquote(path.lstrip("/"))
        # URLs can carry Windows separators as either literal or percent-
        # encoded backslashes. Normalize both separator forms and enforce
        # containment after joining so traversal cannot escape web_root.
        relative = relative.replace("\\", "/")
        if not relative or "\x00" in relative:
            return self.send_error(400)
        # Resolve symlinks before containment checking. ``abspath`` alone can
        # approve a link inside web_root whose target is outside the package.
        web_root = os.path.realpath(os.path.abspath(self.server.web_root))
        target = os.path.realpath(os.path.abspath(os.path.join(web_root, relative)))
        try:
            if os.path.commonpath((web_root, target)) != web_root:
                return self.send_error(400)
        except ValueError:
            return self.send_error(400)
        if not os.path.isfile(target):
            return self.send_error(404)
        mime_type = mimetypes.guess_type(target)[0]
        # Windows and some minimal Linux environments do not map .js to a
        # JavaScript MIME type. The fnOS host bridge is loaded as an ES module,
        # which browsers reject when it is served as application/octet-stream.
        if target.lower().endswith(".js"):
            mime_type = "text/javascript"
        query = query if isinstance(query, dict) else {}
        cache_control = static_asset_cache_control(relative, bool(query.get("v", [""])[0]))
        try:
            # Use the opened file's stat data. A package updater can replace a
            # UI asset between pathname inspection and response generation;
            # headers must describe the exact descriptor copied to the client.
            with open(target, "rb") as fh:
                stat_result = os.fstat(fh.fileno())
                content_length = stat_result.st_size
                if not static_asset_size_allowed(content_length):
                    return self.send_error(413, "Static asset exceeds size limit")
                etag = static_asset_etag(content_length, stat_result.st_mtime_ns)
                if static_asset_etag_matches(self.headers.get("If-None-Match"), etag):
                    self.send_response(304)
                    self.send_header("ETag", etag)
                    self.send_header("Cache-Control", cache_control)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", mime_type or "application/octet-stream")
                self.send_header("Content-Length", str(content_length))
                self.send_header("ETag", etag)
                self.send_header("Cache-Control", cache_control)
                self.end_headers()
                if head_only:
                    return
                try:
                    shutil.copyfileobj(fh, self.wfile, length=128 * 1024)
                except (OSError, BrokenPipeError, ConnectionResetError, ValueError):
                    self.close_connection = True
        except OSError:
            return self.send_error(404)

    def serve_cover(self, item_id, query=None, head_only=False, dlna=False):
        # Both callers pass one raw URL path segment.  The browser and the
        # advertised DIDL percent-encode the ID, so decode it before the
        # lookup instead of failing to find a perfectly valid track.
        item_id = urllib.parse.unquote(item_id)
        item = find_library_item(self.server.config, item_id)
        if not item:
            return self.send_error(404)
        size = normalized_cover_size(((query or {}).get("size") or [0])[0])
        # The source version is resolved once and shared by the thumbnail cache
        # key, the ETag and the invalidation rule below.  They deliberately have
        # to agree, so they must not be three separate filesystem probes that a
        # mid-request tag or cover write can pull apart.
        version = cover_source_version(item)
        mime, body = (cached_thumbnail_for_item(item, self.server.config, size, cached_cover_for_item,
                                               version=version)
                      if size else cached_cover_for_item(item, self.server.config))
        if not body:
            return self.send_error(404)
        # The cached MIME may be the free text an APIC or PICTURE block
        # declared, so re-resolve it from the bytes about to go on the wire.
        # This sits before the ETag branch on purpose: a refusal must never
        # be able to answer 304 for an artwork this route cannot describe.
        mime = safe_image_media_type(mime, body)
        if not mime:
            return self.send_error(404)
        # URL version, ETag and thumbnail-cache invalidation deliberately use
        # the same source version. This keeps tag/cover writes from serving a
        # stale 304 response after a library index has not caught up yet.  The
        # value comes from the single resolution above, so the cache that served
        # `body` and the ETag describing it cannot disagree.
        etag = '"cover-%s-%s-%s-%s"' % (
            item.get("id", item_id), version, size or "original", hashlib.sha256(body).hexdigest()[:16])
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "public, max-age=2592000, immutable")
            if dlna:
                self.send_header("transferMode.dlna.org", "Interactive")
                self.send_header("contentFeatures.dlna.org", "DLNA.ORG_PN=JPEG_TN;DLNA.ORG_OP=01;DLNA.ORG_CI=1")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", "public, max-age=2592000, immutable")
        if dlna:
            self.send_header("transferMode.dlna.org", "Interactive")
            self.send_header("contentFeatures.dlna.org", "DLNA.ORG_PN=JPEG_TN;DLNA.ORG_OP=01;DLNA.ORG_CI=1")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            try:
                self.wfile.write(body)
            except (OSError, ValueError):
                self.close_connection = True

    def serve_upnp_cover(self, item_id, query=None, head_only=False):
        """Serve the same thumbnail bytes as DIDL albumArtURI without fnOS auth.

        The UPnP media endpoint is already unauthenticated for LAN DMS
        clients. Matching that scope for its artwork fixes controllers which
        can browse audio but do not forward a web-session token for covers.
        """
        return self.serve_cover(item_id, query, head_only, dlna=True)

    def send_cached_image(self, mime, body, etag, head_only=False):
        """Answer one already-buffered image with the shared cache headers.

        Cover, cover-asset and metadata-artwork routes all describe a stable
        content address, so they must not disagree about ETag or freshness.
        """
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "public, max-age=2592000, immutable")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", "public, max-age=2592000, immutable")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            try:
                self.wfile.write(body)
            except (OSError, ValueError):
                self.close_connection = True

    def serve_cover_asset(self, asset_id, query=None, head_only=False):
        size = normalized_cover_size(((query or {}).get("size") or [160])[0]) or 160
        value = thumbnail_asset_bytes(self.server.config, asset_id, size)
        if not value:
            return self.send_error(404)
        mime, body = value
        mime = safe_image_media_type(mime, body)
        if not mime:
            return self.send_error(404)
        return self.send_cached_image(mime, body, '"cover-asset-%s-%s"' % (asset_id, size), head_only)

    def serve_metadata_artwork(self, asset_id, head_only=False, query=None):
        asset = METADATA_SERVICE.artwork(asset_id) if METADATA_SERVICE else None
        if not asset:
            return self.send_error(404)
        # The interface requests the same 160px tile here that it requests for
        # embedded covers, while this cache holds a provider original of up to
        # MAX_ARTWORK_BYTES.  A sized request is therefore answered from the
        # shared thumbnail store, so cold artwork pays one render instead of
        # every visible row paying one full download.
        size = normalized_cover_size(((query or {}).get("size") or [0])[0])
        source_path = asset.get("path") if isinstance(asset, dict) else None
        if size and isinstance(source_path, str) and source_path:
            thumbnail = generate_asset_thumbnail(
                self.server.config, asset_id, size, source_path, ffmpeg_slot_timeout=1.0
            )
            if thumbnail:
                # The render is our own JPEG, but the type is still re-resolved
                # from the bytes about to go on the wire.
                thumb_mime = safe_image_media_type(thumbnail[0], thumbnail[1])
                if not thumb_mime:
                    return self.send_error(404)
                # A cold render that is unavailable must not answer under the
                # sized tag below, or a later successful render would keep
                # serving the original through a conditional request.
                return self.send_cached_image(
                    thumb_mime, thumbnail[1], '"metadata-%s-%s"' % (asset_id, size), head_only
                )
        try:
            opened = open_bounded_artwork(asset["path"], MAX_ARTWORK_BYTES)
        except (KeyError, TypeError, ValueError):
            return self.send_error(404)
        if not opened:
            return self.send_error(404)
        handle, actual_size = opened
        # A cache row can be migrated or hand-edited and this route is also
        # reachable without a web session, so the stored type is only a hint:
        # the first bytes decide, and an undeclarable asset is not served.
        prefix = handle.read(SNIFF_PREFIX_BYTES)
        mime = safe_image_media_type(asset.get("mime"), prefix)
        if not mime:
            handle.close()
            return self.send_error(404)
        etag = '"metadata-%s"' % asset_id
        if self.headers.get("If-None-Match") == etag:
            handle.close()
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "public, max-age=2592000, immutable")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(actual_size))
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", "public, max-age=2592000, immutable")
        self.end_headers()
        if head_only:
            handle.close()
            return
        try:
            if prefix:
                self.wfile.write(prefix)
            remaining = actual_size - len(prefix)
            while remaining > 0:
                chunk = handle.read(min(128 * 1024, remaining))
                if not chunk:
                    # The descriptor may be truncated after fstat(). The
                    # declared Content-Length is already on the wire, so a
                    # short body must not leave this connection reusable.
                    self.close_connection = True
                    break
                if len(chunk) > remaining:
                    # A nonstandard or replaced descriptor must never send
                    # bytes beyond the declared Content-Length.
                    self.close_connection = True
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)
        except (OSError, BrokenPipeError, ConnectionResetError, ValueError):
            self.close_connection = True
        finally:
            handle.close()

    def serve_media(self, item_id, query, head_only=False):
        item = find_library_item(self.server.config, item_id)
        if not item or not os.path.isfile(item["path"]):
            return self.send_error(404)
        mode = media_mode(item, query, self)
        if mode != "original":
            if mode in ("cue_flac", "ape_flac"):
                try:
                    target, mime = transcode_to_audio(item, self.server.config, mode)
                except RuntimeError as exc:
                    return self.send_error(501, str(exc))
                return self.serve_file_range(target, mime, head_only)
            if mode == "mp3":
                target, mime, ready = transcode_cache_ready(item, self.server.config, mode)
                if ready:
                    return self.serve_file_range(target, mime, head_only)
                warm_transcode_cache(item, self.server.config, mode, priority=100)
                if head_only:
                    self.send_response(200)
                    self.send_header("Content-Type", mime)
                    self.send_header("Accept-Ranges", "none")
                    self.end_headers()
                    return
                return self.serve_transcoded_media(item, mode, query)
            if mode == "dsd_wav":
                try:
                    target, mime = transcode_to_audio(item, self.server.config, mode)
                except RuntimeError as exc:
                    return self.send_error(501, str(exc))
                return self.serve_file_range(target, mime, head_only)
            if head_only:
                mime = "audio/wav" if mode == "dsd_wav" else "audio/mpeg"
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Accept-Ranges", "none")
                self.end_headers()
                return
            return self.serve_transcoded_media(item, mode, query)
        try:
            target, mime = transcode_to_audio(item, self.server.config, mode)
        except RuntimeError as exc:
            return self.send_error(501, str(exc))
        return self.serve_file_range(target, mime, head_only)

    def serve_file_range(self, target, mime, head_only=False, dlna=False):
        try:
            handle = None
            flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            handle = os.fdopen(os.open(target, flags), "rb")
            size = os.fstat(handle.fileno()).st_size
        except OSError:
            if handle is not None:
                handle.close()
            return self.send_error(404)
        if size <= 0:
            if handle is not None:
                handle.close()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", "0")
            self.send_header("Accept-Ranges", "bytes")
            if dlna:
                self.send_header("transferMode.dlna.org", "Streaming")
            self.end_headers()
            return
        try:
            status, start, end = parse_single_byte_range(size, self.headers.get("Range"))
        except ValueError:
            if handle is not None:
                handle.close()
            self.send_response(416)
            self.send_header("Content-Range", "bytes */%s" % size)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if status == 206:
            self.send_response(status)
            self.send_header("Content-Range", "bytes %s-%s/%s" % (start, end, size))
        else:
            self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if dlna:
            self.send_header("transferMode.dlna.org", "Streaming")
        self.end_headers()
        if head_only:
            handle.close()
            return
        try:
            handle.seek(start)
            remaining = end - start + 1
            while remaining:
                chunk = handle.read(min(1024 * 256, remaining))
                if not chunk:
                    # The file may be replaced or truncated after stat() and
                    # before the body is sent.  We cannot change the already
                    # emitted Content-Length, so do not let the HTTP server
                    # reuse this connection for a following response.
                    self.close_connection = True
                    break
                try:
                    self.wfile.write(chunk)
                except (OSError, ValueError):
                    # Content-Length is already committed. Do not reuse a
                    # connection after the client rejected a partial body.
                    self.close_connection = True
                    break
                remaining -= len(chunk)
        finally:
            handle.close()

    def serve_upnp_media(self, item_path, query, head_only=False):
        # Split before decoding: an encoded separator inside the ID must
        # stay one path segment, and the advertised DIDL always encodes it.
        item_id = urllib.parse.unquote(item_path.split("/", 1)[0])
        item = find_library_item(self.server.config, item_id)
        if not item or not os.path.isfile(item["path"]):
            self.record_dlna("media_missing", item_id=item_id)
            return self.send_error(404)
        # DLNA DSD pushes must expose the original DSF/DFF bytes. Browser
        # playback may still request server-side conversion explicitly.
        mode = "original" if item.get("is_dsd") else media_mode(item, query, self)
        if str(item.get("path") or "").lower().endswith(".ape"):
            # Renderers frequently omit source format support in their probe.
            # fnAudio always exposes the APE compatibility resource as FLAC.
            mode = "cue_flac" if item.get("cue_track") else "ape_flac"
        self.record_dlna(
            "media",
            item_id=item_id,
            format=item.get("format", ""),
            mime=upnp_resource_mime(item),
            mode=mode,
            method=self.command,
        )
        if mode == "mp3":
            try:
                target, mime = transcode_to_audio(item, self.server.config, "mp3")
            except RuntimeError as exc:
                return self.send_error(501, str(exc))
        elif mode == "dsd_wav":
            try:
                target, mime = transcode_to_audio(item, self.server.config, "dsd_wav")
            except RuntimeError as exc:
                return self.send_error(501, str(exc))
        elif mode == "ape_flac":
            try:
                target, mime = transcode_to_audio(item, self.server.config, "ape_flac")
            except RuntimeError as exc:
                return self.send_error(501, str(exc))
        elif item.get("cue_track"):
            try:
                target, mime = transcode_to_audio(item, self.server.config, "cue_flac")
            except RuntimeError as exc:
                return self.send_error(501, str(exc))
        else:
            target = item["path"]
            mime = upnp_resource_mime(item)
        return self.serve_file_range(target, mime, head_only, dlna=True)

    def serve_transcoded_media(self, item, mode, query=None):
        try:
            start = safe_float((query or {}).get("start", ["0"])[0])
            command, mime, env = transcode_command(item, self.server.config, mode, start)
        except RuntimeError as exc:
            return self.send_error(501, str(exc))
        try:
            with ffmpeg_slot(self.server.config, timeout=2):
                process = None
                watchdog = None
                killer = None
                try:
                    process = subprocess.Popen(
                        command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        env=env,
                        start_new_session=(os.name != "nt"),
                    )

                    def stop_timed_out_process():
                        nonlocal killer
                        try:
                            if process.poll() is None:
                                if os.name != "nt":
                                    os.killpg(process.pid, signal.SIGTERM)
                                else:
                                    process.terminate()
                        except OSError:
                            pass
                        def kill_if_still_running():
                            try:
                                if process.poll() is None:
                                    if os.name != "nt":
                                        os.killpg(process.pid, signal.SIGKILL)
                                    else:
                                        process.kill()
                            except OSError:
                                pass
                        killer = threading.Timer(2.0, kill_if_still_running)
                        killer.daemon = True
                        killer.start()

                    watchdog = threading.Timer(
                        max(0.1, safe_float(self.server.config.get("ffmpeg_job_timeout_seconds") or 900)),
                        stop_timed_out_process,
                    )
                    watchdog.daemon = True
                    watchdog.start()
                    self.send_response(200)
                    self.send_header("Content-Type", mime)
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-fnAudio-Transcode-Timeout", "%g" % safe_float(self.server.config.get("ffmpeg_job_timeout_seconds") or 900))
                    self.end_headers()
                    while True:
                        chunk = process.stdout.read(1024 * 128)
                        if not chunk:
                            break
                        try:
                            self.wfile.write(chunk)
                            self.wfile.flush()
                        except (OSError, BrokenPipeError, ConnectionResetError, ValueError):
                            # A disconnected client must still reach the
                            # process cleanup below, but a Popen failure must
                            # remain visible to the outer 502 handler.
                            break
                finally:
                    if watchdog is not None:
                        watchdog.cancel()
                    if killer is not None:
                        killer.cancel()
                    if process is not None:
                        if process.poll() is None:
                            if os.name != "nt":
                                os.killpg(process.pid, signal.SIGTERM)
                            else:
                                process.terminate()
                            try:
                                process.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                if os.name != "nt":
                                    os.killpg(process.pid, signal.SIGKILL)
                                else:
                                    process.kill()
                                # A killed child should normally reap immediately,
                                # but cleanup runs after the HTTP 200 headers have
                                # already gone out. Do not turn an unreapable
                                # process into a second, invalid error response.
                                try:
                                    process.wait(timeout=2)
                                except subprocess.TimeoutExpired:
                                    pass
                        else:
                            # A process whose stdout reached EOF has usually
                            # already exited, but it still must be reaped.
                            try:
                                process.wait(timeout=2)
                            except (OSError, subprocess.TimeoutExpired, AttributeError):
                                pass
                    stream = getattr(process, "stdout", None) if process is not None else None
                    close_stream = getattr(stream, "close", None)
                    if callable(close_stream):
                        try:
                            close_stream()
                        except (OSError, AttributeError):
                            pass
        except ResourceLimitError as exc:
            return self.send_error(503, str(exc))
        except OSError as exc:
            return self.send_error(502, "failed to start ffmpeg: %s" % exc)


def public_item(item, config=None):
    # Kept as a compatibility name for existing Handler call sites.
    return public_library_item(item, config)


def playback_targets_payload(force_refresh=False):
    mpd_service = getattr(MPD_OUTPUT, "service", None)
    if force_refresh and mpd_service and hasattr(mpd_service, "output_capabilities"):
        # Target discovery is explicitly user initiated. Do not show a
        # disconnected USB DAC from the normal low-latency status cache.
        mpd_service.output_capabilities(force=True)
    mpd = MPD_OUTPUT.status()
    mpd_caps = mpd.get("output_capabilities") or {}
    core_state = PLAYBACK_CORE.snapshot()
    upmpdcli = upmpdcli_probe()
    if force_refresh or upnp_cache_needs_refresh():
        refresh_upnp_cache_background()
    targets, current_target, current_target_name = build_targets(
        mpd,
        core_state,
        cached_upnp_devices(),
        PLAYBACK_CORE.registry.get("browser").capabilities(),
        PLAYBACK_CORE.registry.get("mpd").capabilities(),
        PLAYBACK_CORE.registry.get("dlna_push").capabilities(),
    )
    # Discovery is asynchronous. Keep the core target untouched while a
    # renderer is temporarily absent, but tell clients when it has no row.
    return compose_playback_targets_response(
        targets=targets,
        current_target=current_target,
        current_target_name=current_target_name,
        plugins=PLAYBACK_CORE.registry.describe(),
        mpd=mpd,
        upmpdcli=upmpdcli,
        airplay=airplay_probe(
            getattr(getattr(MPD_OUTPUT, "service", None), "config", {}) or {},
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        ),
        refreshing=upnp_cache_status().get("refreshing"),
    )


def find_library_item(config, item_id):
    item = query_library_item_by_id(config, item_id)
    return item if item and is_library_item_path(config, item.get("path")) else None


def find_upnp_device(device_id):
    devices = cached_upnp_devices() or discover_upnp()
    return select_upnp_device(devices, device_id)


def playback_load(handler, payload):
    # Keep the legacy load endpoint on the same identity/idempotency path as
    # /api/playback/control. Otherwise a delayed load could bypass a newer
    # generation's stale-session rejection and overwrite the active target.
    request = dict(payload) if isinstance(payload, dict) else {}
    request["action"] = "load"
    return playback_control_idempotent(handler, request)


def current_playback_session():
    return project_playback_session(PLAYBACK_CORE.snapshot(), safe_float=safe_float)


def save_current_playback_session(config):
    try:
        return save_playback_session(config, current_playback_session())
    except Exception:
        return None


def save_playback_target_session(config, snapshot, target_id, target_kind):
    """Persist a target transition without mutating the active output first."""
    try:
        session = project_playback_session(snapshot, safe_float=safe_float)
        normalized_target = target_id if target_kind != "browser" else "local"
        session["target_id"] = normalized_target
        session["target_kind"] = target_kind if isinstance(target_kind, str) else "browser"
        return save_playback_session(config, session)
    except Exception:
        return None


def playback_persistence_failure(kind=""):
    response = {
        "ok": False,
        "error": "playback_state_persistence_failed",
        "message": "播放状态保存失败",
        "core": PLAYBACK_CORE.snapshot(),
    }
    if isinstance(kind, str) and kind:
        response["kind"] = kind
    return response, 503


def enable_playback_restore_retry():
    """Allow one startup generation to schedule bounded restore retries."""
    global PLAYBACK_RESTORE_RETRY_TIMER, PLAYBACK_RESTORE_RETRY_GENERATION
    with PLAYBACK_RESTORE_RETRY_LOCK:
        previous_timer = PLAYBACK_RESTORE_RETRY_TIMER
        PLAYBACK_RESTORE_RETRY_TIMER = None
        PLAYBACK_RESTORE_RETRY_GENERATION += 1
        PLAYBACK_RESTORE_RETRY_STOP.clear()
        generation = PLAYBACK_RESTORE_RETRY_GENERATION
    if previous_timer is not None:
        previous_timer.cancel()
    return generation


def cancel_playback_restore_retry():
    """Prevent delayed restore work from touching a stopped runtime."""
    global PLAYBACK_RESTORE_RETRY_TIMER, PLAYBACK_RESTORE_RETRY_GENERATION
    PLAYBACK_RESTORE_RETRY_STOP.set()
    with PLAYBACK_RESTORE_RETRY_LOCK:
        timer = PLAYBACK_RESTORE_RETRY_TIMER
        PLAYBACK_RESTORE_RETRY_TIMER = None
        PLAYBACK_RESTORE_RETRY_GENERATION += 1
    if timer is not None:
        timer.cancel()


def _playback_restore_generation_is_current(generation):
    with PLAYBACK_RESTORE_RETRY_LOCK:
        return (
            not PLAYBACK_RESTORE_RETRY_STOP.is_set()
            and generation == PLAYBACK_RESTORE_RETRY_GENERATION
        )


def restore_playback_session(config, _retry=0, _generation=None):
    global PLAYBACK_RESTORE_RETRY_TIMER
    if _generation is None:
        with PLAYBACK_RESTORE_RETRY_LOCK:
            _generation = PLAYBACK_RESTORE_RETRY_GENERATION
    if not _playback_restore_generation_is_current(_generation):
        return
    retry_delay = (2.0, 5.0, 12.0)
    try:
        playback = (load_user_state(config).get("playback") or {})
        queue_ids = playback_queue_ids(playback.get("queue"))
        rows = query_library_items_by_ids(config, queue_ids)
        by_id = {str(item.get("id") or ""): item for item in rows}
        queue = [by_id[track_id] for track_id in queue_ids if track_id in by_id]
        current = str(playback.get("current_id") or "")
        if not _playback_restore_generation_is_current(_generation):
            return
        PLAYBACK_CORE.set_queue(queue, current, playback.get("repeat"), playback.get("shuffle"))
        target_id = str(playback.get("target_id") or "local")
        target_kind = playback_target_kind(target_id)
        if not _playback_restore_generation_is_current(_generation):
            return
        PLAYBACK_CORE.set_target("local" if target_kind == "browser" else target_id, target_kind)
        # App/browser restarts restore the logical current track before any
        # client issues a transport command. Promote it immediately so the
        # explicit current-song metadata lane can fetch lyrics/artwork even
        # when whole-library metadata enrichment remains disabled.
        if current and METADATA_SERVICE:
            try:
                METADATA_SERVICE.prioritize_track(current)
            except Exception as exc:
                print("fnAudio metadata restore prioritization skipped: %s" % exc, flush=True)
        # Restoring the logical queue is not enough for MPD: its native
        # execution queue is process-local and is empty after an app restart.
        # Mirror the saved queue back into MPD before the UI tries to control
        # the recovered target.  Older sessions have no `playing` field; they
        # are restored paused/stopped after the queue is mirrored.
        if target_kind == "mpd" and queue and MPD_SERVICE:
            if not _playback_restore_generation_is_current(_generation):
                return
            tracks = [TrackRef.from_mapping(item) for item in queue]
            restored_position = safe_float(playback.get("position") or 0)
            # The session stores client units (seconds inside the CUE segment).
            # The native queue mirror is driven in source-file seconds, the same
            # inverse a seek command uses.
            restored_current = next((item for item in queue if str(item.get("id") or "") == current), None)
            backend_start = project_cue_seek(restored_position, restored_current)
            result = MPD_SERVICE.sync_playback_queue(
                tracks,
                current,
                resolver=lambda track_id: find_library_item(config, track_id),
                current_item=restored_current,
                start=backend_start,
                repeat=str(playback.get("repeat") or "off"),
                shuffle=playback.get("shuffle") if isinstance(playback.get("shuffle"), bool) else False,
                play=False,
            )
            # Session restore deliberately never resumes audio. The saved
            # playing flag is historical state for the UI, not permission to
            # start an output device when fnAudio starts.
            restore_playing = False
            if not restore_playing:
                service_control = getattr(MPD_SERVICE, "control", None)
                if callable(service_control):
                    service_control("stop")
                else:
                    mpd_control("stop", host=MPD_SERVICE.host, port=MPD_SERVICE.port)
                PLAYBACK_CORE.sync_output_status("mpd", "STOPPED", restored_position, 0)
                save_current_playback_session(config)
            else:
                # MPD accepts `playid` before ALSA has actually opened the
                # stream.  A format/rate failure (for example a 384 kHz
                # source on this DAC) therefore needs an authoritative
                # transport check; otherwise the UI can claim PLAYING while
                # MPD has already stopped.
                actual_state = ""
                refresh_status = getattr(MPD_SERVICE, "refresh_status", None)
                if callable(refresh_status):
                    try:
                        probe = refresh_status()
                        actual_state = str(
                            ((probe.get("status") or {}).get("transport") or {}).get("state") or ""
                        ).upper()
                    except Exception:
                        actual_state = ""
                if actual_state and actual_state not in ("PLAYING", "PAUSED"):
                    message = "MPD 未能打开恢复曲目，已停止并保留当前队列"
                    PLAYBACK_CORE.sync_output_status(
                        "mpd", "STOPPED", restored_position, 0, message
                    )
                    save_current_playback_session(config)
                else:
                    # Keep restoration visible to event consumers as well as
                    # the persisted state; direct field writes bypass the
                    # core version/condition used by SSE.
                    PLAYBACK_CORE.sync_output_status("mpd", "PLAYING", restored_position)
            if result.get("ok") is False:
                raise RuntimeError(result.get("message") or "MPD queue restore failed")
    except Exception as exc:
        print("fnAudio playback-session restore skipped: %s" % exc, flush=True)
        # MPD may still be opening its database immediately after process
        # startup.  Keep the logical session, but retry the native queue
        # mirror a few times so a transient startup race cannot leave MPD
        # with playlistlength=0 until the next user action.
        if _retry < len(retry_delay) and _playback_restore_generation_is_current(_generation):
            timer = threading.Timer(
                retry_delay[_retry],
                restore_playback_session,
                args=(config, _retry + 1, _generation),
            )
            timer.daemon = True
            with PLAYBACK_RESTORE_RETRY_LOCK:
                if (
                    PLAYBACK_RESTORE_RETRY_STOP.is_set()
                    or _generation != PLAYBACK_RESTORE_RETRY_GENERATION
                ):
                    return
                PLAYBACK_RESTORE_RETRY_TIMER = timer
            try:
                timer.start()
            except Exception:
                with PLAYBACK_RESTORE_RETRY_LOCK:
                    if PLAYBACK_RESTORE_RETRY_TIMER is timer:
                        PLAYBACK_RESTORE_RETRY_TIMER = None
                raise


def playback_queue(config, payload):
    request = queue_request(payload)
    # A user queue edit supersedes any startup restore retry that may still be
    # waiting on MPD.  Otherwise the delayed retry can reload an older
    # persisted session and overwrite this newly selected queue.
    cancel_playback_restore_retry()
    tracks = request["tracks"]
    current = request["current_id"]
    repeat = request["repeat"]
    shuffle = request["shuffle"]
    state = PLAYBACK_CORE.set_queue(tracks, str(current or ""), repeat, shuffle if shuffle is not None else None)
    # Keep MPD's native execution queue aligned with the logical queue even
    # when the UI only edits the queue while playback is stopped.  Replacing
    # the queue with ``play=False`` prevents an edit from unexpectedly
    # starting audio; the next explicit play/load still uses the fast native
    # queue path.
    target_kind = playback_target_kind(PLAYBACK_CORE.state.target_id)
    service = getattr(MPD_OUTPUT, "service", None)
    if should_sync_mpd_queue(target_kind, tracks) and service:
        try:
            was_playing = bool(state.playing)
            service.sync_playback_queue(
                state.queue,
                state.current_track_id,
                resolver=lambda track_id: find_library_item(config, track_id),
                repeat=state.repeat,
                shuffle=state.shuffle,
                play=was_playing,
            )
            if not was_playing:
                service.refresh_status()
        except Exception as exc:
            state.error = "MPD 队列同步失败: %s" % exc
    revision = save_current_playback_session(config)
    if revision is None:
        return playback_persistence_failure(target_kind)
    # Queue edits are also a user-visible playback selection.  Browser
    # clients commonly persist the queue first and issue the native load a
    # moment later; prioritize the selected track here as well so the lyrics,
    # artwork and candidate workers do not wait for a second transport call.
    if current and METADATA_SERVICE:
        try:
            METADATA_SERVICE.prioritize_track(str(current))
        except Exception as exc:
            # Metadata enrichment must never make a successful queue save
            # fail.  The service exposes the failure through its diagnostics.
            print("fnAudio metadata prioritization skipped: %s" % exc, flush=True)
    return {"ok": True, "core": state.to_dict(), "revision": revision}, 200


def playback_load_selected(handler, target_id, item, position=0):
    # Direct loads are also authoritative user/device actions.  Do not allow a
    # delayed startup restore to write the old persisted session afterward.
    cancel_playback_restore_retry()
    target_kind = playback_target_kind(target_id)
    PLAYBACK_CORE.set_target("local" if target_kind == "browser" else target_id, target_kind)
    context = {
        "handler": handler,
        "config": handler.server.config,
        "item": item,
        "position": safe_float(position),
        "resolve_track": lambda track_id: find_library_item(handler.server.config, track_id),
    }
    core_result = PLAYBACK_CORE.dispatch(
        PlaybackCommand("load", safe_float(position), TrackRef.from_mapping(item), context)
    )
    output_result = core_result.get("result") or {}
    # A direct device load can be initiated by a renderer, Android bridge, or
    # another client without first calling /api/playback/queue.  Persist the
    # authoritative core snapshot here as well, otherwise the next browser
    # refresh can restore an empty/stale queue even though the device is
    # already playing the selected track.
    output_ok = isinstance(output_result, dict) and output_result.get("ok") is True
    revision = None
    if core_result.get("ok") is True and (target_kind == "browser" or output_ok):
        revision = save_current_playback_session(handler.server.config)
        if revision is None:
            return playback_persistence_failure(target_kind)
        if METADATA_SERVICE:
            METADATA_SERVICE.prioritize_track(item["id"])
    if target_kind == "browser":
        return {"ok": True, "kind": target_kind, "target_id": "local", "track_id": item["id"], "core": core_result["state"], "revision": revision}, 200
    ok = output_result.get("ok") is True
    message = output_result.get("message") or ""
    return {
        "ok": ok,
        "kind": target_kind,
        "target_id": target_id,
        "message": message,
        "strategy": output_result.get("strategy"),
        "cue_segment": bool(output_result.get("cue_segment")),
        "core": PLAYBACK_CORE.snapshot(),
        }, 200 if ok else 502


def playback_control_idempotent(handler, payload):
    """Execute a transport command once and return its authoritative result.

    Browser retries, native notification actions, and intermittent mobile
    proxies can submit the same command twice.  A caller-provided command id
    makes next/previous safe to retry without turning one user gesture into
    two queue advances.
    """
    command_id = command_id_from_payload(payload)
    if not command_id:
        return playback_control(handler, payload)
    identity = session_identity(payload)
    cache_key = command_id
    if identity["generation"] or identity["engine_epoch"]:
        cache_key = "%s:%d:%d" % (command_id, identity["generation"], identity["engine_epoch"])
    while True:
        now = time.monotonic()
        with PLAYBACK_COMMAND_LOCK:
            cached = cached_result(PLAYBACK_COMMAND_RESULTS, cache_key, now)
            if cached is not None:
                return cached
            completed = PLAYBACK_COMMAND_INFLIGHT.get(cache_key)
            if completed is None:
                if len(PLAYBACK_COMMAND_INFLIGHT) >= playback_command_inflight_limit():
                    core = PLAYBACK_CORE.snapshot()
                    response = {
                        "ok": False,
                        "error": "playback_command_capacity",
                        "message": "too many playback commands are in progress",
                        "command_id": command_id,
                        "state_version": safe_int(core.get("state_version")),
                        "core": core,
                    }
                    response.update(session_identity(payload))
                    return response, 503
                completed = threading.Event()
                PLAYBACK_COMMAND_INFLIGHT[cache_key] = completed
                leader = True
            else:
                leader = False

        if not leader:
            if not completed.wait(PLAYBACK_COMMAND_WAIT_SECONDS):
                core = PLAYBACK_CORE.snapshot()
                response = {
                    "ok": False,
                    "pending": True,
                    "error": "playback_command_in_progress",
                    "message": "playback command is still in progress",
                    "command_id": command_id,
                    "state_version": safe_int(core.get("state_version")),
                    "core": core,
                }
                response.update(session_identity(payload))
                return response, 202
            # A failed leader does not cache a response. Once it has released
            # the ticket, retry acquisition so a later request can recover.
            continue

        try:
            response, status = playback_control(handler, payload)
            response = dict(response)
            response["command_id"] = command_id
            core = response.get("core") or {}
            response["state_version"] = safe_int(core.get("state_version"))
            response.update(session_identity(payload))
            # Command ids are client supplied retry tokens. Keep the idempotency
            # cache bounded even when a buggy/offline client generates unique ids
            # faster than the TTL can expire them.
            with PLAYBACK_COMMAND_LOCK:
                store_result(
                    PLAYBACK_COMMAND_RESULTS,
                    cache_key,
                    response,
                    status,
                    time.monotonic() + PLAYBACK_COMMAND_TTL_SECONDS,
                    PLAYBACK_COMMAND_RESULT_LIMIT,
                )
            return response, status
        finally:
            with PLAYBACK_COMMAND_LOCK:
                if PLAYBACK_COMMAND_INFLIGHT.get(cache_key) is completed:
                    PLAYBACK_COMMAND_INFLIGHT.pop(cache_key, None)
                    completed.set()


def _playback_command_accepted(result):
    """Accept legacy responses without ``ok`` but reject malformed flags."""
    if not isinstance(result, dict):
        return False
    if "ok" not in result:
        return True
    return result["ok"] is True


def playback_control(handler, payload):
    target_id = payload_target_id(payload)
    if target_id is None:
        return {
            "ok": False,
            "error": "target_id must be text",
            "message": "target_id must be text",
            "core": PLAYBACK_CORE.snapshot(),
        }, 400
    identity = session_identity(payload)
    if identity_is_stale(identity, PLAYBACK_CORE.snapshot()):
        target = target_id
        try:
            config = getattr(handler.server, "config", {}) or {}
            OBSERVABILITY.write(
                config.get("structured_log_path")
                or os.path.join(os.path.dirname(getattr(handler.server, "config_path", "") or "."), "fnaudio.jsonl"),
                "playback_stale_session",
                generation=identity.get("generation", 0),
                engine_epoch=identity.get("engine_epoch", 0),
                target_kind=playback_target_kind(target),
            )
        except Exception:
            pass
        return {
            "ok": False,
            "kind": playback_target_kind(target),
            "error": "stale_session",
            "message": "playback session is older than the active session",
            "core": PLAYBACK_CORE.snapshot(),
        }, 409
    target_kind = playback_target_kind(target_id)
    action_value = payload.get("action")
    if not isinstance(action_value, str):
        return {
            "ok": False,
            "kind": target_kind,
            "message": "action must be text",
            "core": PLAYBACK_CORE.snapshot(),
        }, 400
    action = action_value.strip().lower()
    position = payload.get("position")
    if action not in PLAYBACK_CONTROL_ACTIONS:
        return {
            "ok": False,
            "kind": target_kind,
            "message": "unsupported playback action",
            "core": PLAYBACK_CORE.snapshot(),
        }, 400
    if action == "repeat" and "repeat" in payload:
        if payload.get("repeat") not in ("off", "all", "one"):
            return {
                "ok": False,
                "kind": target_kind,
                "message": "repeat must be off, all, or one",
                "core": PLAYBACK_CORE.snapshot(),
            }, 400
    if action == "shuffle" and "shuffle" in payload:
        if not isinstance(payload.get("shuffle"), bool):
            return {
                "ok": False,
                "kind": target_kind,
                "message": "shuffle must be a boolean",
                "core": PLAYBACK_CORE.snapshot(),
            }, 400
    command_ticket = command_id_from_payload(payload)
    # A direct `load` must not bypass target validation. The load helper sets
    # the core target before dispatching to an output, so allowing a vanished
    # renderer through here could replace a healthy active target with an
    # offline one even though the command ultimately fails.
    if target_kind == "dlna_push" and not find_upnp_device(target_id):
        return {
            "ok": False,
            "kind": target_kind,
            "error": "playback_target_not_found",
            "message": "playback target not found",
            "core": PLAYBACK_CORE.snapshot(),
        }, 404
    if action == "load":
        item_id = normalize_track_id(payload.get("track_id"))
        item = find_library_item(handler.server.config, item_id) if item_id else None
        if not item:
            return {
                "ok": False,
                "kind": target_kind,
                "message": "track not found",
                "core": PLAYBACK_CORE.snapshot(),
            }, 404
        # Bind a participant identity only after the requested track has been
        # validated. A malformed future-generation load must not fence out
        # the active client session.
        if identity.get("generation") or identity.get("engine_epoch") or command_ticket:
            PLAYBACK_CORE.set_session_identity(
                identity.get("generation"),
                identity.get("engine_epoch"),
                command_ticket,
            )
        return playback_load_selected(handler, target_id, item, position)
    # Legacy browser controls deliberately have no participant identity. Do
    # not let those commands erase an active native session's identity while
    # its SSE stream is still reconciling a remote notification action. This
    # must follow all validation: rejected commands are not session owners.
    if identity.get("generation") or identity.get("engine_epoch") or command_ticket:
        PLAYBACK_CORE.set_session_identity(
            identity.get("generation"),
            identity.get("engine_epoch"),
            command_ticket,
        )
    # Any accepted transport command supersedes a pending startup restore. Do
    # this only after command and target validation so malformed requests do
    # not cancel a still-useful recovery attempt.
    cancel_playback_restore_retry()
    PLAYBACK_CORE.set_target("local" if target_kind == "browser" else target_id, target_kind)
    if action in ("next", "previous"):
        result = PLAYBACK_CORE.dispatch(
            PlaybackCommand(
                action,
                context={
                    "handler": handler,
                    "config": handler.server.config,
                    "resolve_track": lambda track_id: find_library_item(handler.server.config, track_id),
                },
            )
        )
        track_id = result.get("state", {}).get("current")
        item = find_library_item(handler.server.config, track_id) if track_id else None
        if not item:
            return {"ok": False, "kind": target_kind, "message": "no next track", "core": PLAYBACK_CORE.snapshot()}, 404
        revision = save_current_playback_session(handler.server.config)
        if revision is None:
            return playback_persistence_failure(target_kind)
        if METADATA_SERVICE:
            METADATA_SERVICE.prioritize_track(item["id"])
        if target_kind == "browser":
            return {"ok": True, "kind": target_kind, "track_id": item["id"], "core": PLAYBACK_CORE.snapshot(), "revision": revision}, 200
        output_result = result.get("result") or {}
        ok = output_result.get("ok") is True
        return {"ok": ok, "kind": target_kind, "track_id": item["id"], "message": output_result.get("message", ""), "core": PLAYBACK_CORE.snapshot(), "revision": revision}, 200 if ok else 502
    if action in ("repeat", "shuffle"):
        context = {}
        if action == "repeat" and payload.get("repeat") in ("off", "all", "one"):
            context["repeat_value"] = payload.get("repeat")
        if action == "shuffle" and isinstance(payload.get("shuffle"), bool):
            context["shuffle_value"] = bool(payload.get("shuffle"))
        result = PLAYBACK_CORE.dispatch(PlaybackCommand(action, context=context))
        revision = save_current_playback_session(handler.server.config)
        if revision is None:
            return playback_persistence_failure(target_kind)
        # Older/test adapters may omit the outer core flag while still
        # accepting the command, but malformed values must not signal success.
        ok = _playback_command_accepted(result)
        return {"ok": ok, "kind": target_kind, "result": result, "core": PLAYBACK_CORE.snapshot(), "revision": revision}, 200 if ok else 502
    if target_kind == "browser":
        result = PLAYBACK_CORE.dispatch(PlaybackCommand(action, safe_float(position) if position is not None else None))
        revision = save_current_playback_session(handler.server.config)
        if revision is None:
            return playback_persistence_failure(target_kind)
        ok = _playback_command_accepted(result)
        return {"ok": ok, "kind": target_kind, "result": result, "core": PLAYBACK_CORE.snapshot(), "revision": revision}, 200 if ok else 502
    if target_kind in ("alsa", "mpd"):
        item_id = normalize_track_id(payload.get("track_id"))
        if target_kind == "alsa" and not item_id:
            with DAC_LOCK:
                item_id = str(DAC_STATE.get("item_id") or "")
        item = find_library_item(handler.server.config, item_id) if item_id else None
        result = PLAYBACK_CORE.dispatch(
            PlaybackCommand(
                action,
                safe_float(position) if position is not None else None,
                TrackRef.from_mapping(item) if item else None,
                {"config": handler.server.config, "item": item, "track_id": item_id},
            )
        )
        output_result = result.get("result") or {}
        ok = output_result.get("ok") is True
        message = output_result.get("message") or ""
        revision = save_current_playback_session(handler.server.config)
        if revision is None:
            return playback_persistence_failure(target_kind)
        return {"ok": ok, "kind": target_kind, "message": message, "core": PLAYBACK_CORE.snapshot(), "revision": revision}, 200 if ok else 502
    result = PLAYBACK_CORE.dispatch(
        PlaybackCommand(
            action,
            safe_float(position) if position is not None else None,
            context={"handler": handler, "config": handler.server.config},
        )
    )
    output_result = result.get("result") or {}
    ok = output_result.get("ok") is True
    message = output_result.get("message") or ""
    revision = save_current_playback_session(handler.server.config)
    if revision is None:
        return playback_persistence_failure(target_kind)
    return {"ok": ok, "kind": target_kind, "message": message, "core": PLAYBACK_CORE.snapshot(), "revision": revision}, 200 if ok else 502


def project_mpd_transport_position(status_position, item):
    """Fold the seconds MPD reports into the units every projection shares.

    MPD reports a native CUE track in source-file seconds.  Folding here, once,
    keeps the authoritative core state, the persisted session, the polling route
    and the SSE stream in the same unit as the seek a client sent; folding later
    would also re-fold the optimistic value a control command already wrote.
    """
    reported = status_position if isinstance(status_position, dict) else {}
    return public_cue_position(
        reported.get("rel_seconds"),
        reported.get("duration_seconds"),
        item,
    )


def playback_status(payload_or_query):
    target_id = target_id_from_query(payload_or_query)
    target_kind = playback_target_kind(target_id)
    if target_kind == "browser":
        return browser_response(PLAYBACK_CORE.snapshot()), 200
    if target_kind == "alsa":
        # The DAC plays the segment as its own stream and is seeked in whole-file
        # seconds, which is also what its status reports: no client-side fold.
        return alsa_response(dac_public_status(), PLAYBACK_CORE.snapshot(), cue_segment=False), 200
    if target_kind == "mpd":
        # The UI polls this endpoint frequently for the progress bar.  Keep
        # it on the lightweight MPD status path so ALSA capability probing and
        # recent-log collection never run in the request thread.
        probe = MPD_OUTPUT.status(light=True)
        if not probe.get("running"):
            return mpd_error_response(probe.get("message"), PLAYBACK_CORE.snapshot()), 404
        status = probe.get("status") or {}
        core_snapshot = PLAYBACK_CORE.snapshot()
        current_id = core_snapshot.get("current") or ""
        current_item = find_library_item(getattr(getattr(MPD_OUTPUT, "service", None), "config", {}) or {}, current_id) if current_id else None
        if current_item and current_item.get("cue_track"):
            status, cue_finished = normalize_cue_position(status, current_item)
            if cue_finished:
                now = time.time()
                if CUE_AUTO_ADVANCE.get("track_id") != current_id or now - safe_float(CUE_AUTO_ADVANCE.get("at")) > 2:
                    CUE_AUTO_ADVANCE.update({"track_id": current_id, "at": now})
                    mpd_config = getattr(getattr(MPD_OUTPUT, "service", None), "config", {}) or {}
                    result = PLAYBACK_CORE.dispatch(
                        PlaybackCommand(
                            "next",
                            context={
                                "config": mpd_config,
                                # Queue state intentionally stores compact track references.
                                # Resolve the selected CUE segment before passing it to MPD.
                                "resolve_track": lambda track_id: find_library_item(mpd_config, track_id),
                            },
                        )
                    )
                    output_result = result.get("result") or {}
                    if result.get("ok") is True and output_result.get("ok") is True:
                        probe = MPD_OUTPUT.status()
                        status = probe.get("status") or status
        return mpd_response(
            probe,
            status,
            PLAYBACK_CORE.snapshot(),
            cue_segment=cue_segment_declaration(current_item),
        ), 200
    device = find_upnp_device(target_id)
    if not device:
        return device_not_found_response(), 404
    try:
        # The renderer receives a trimmed segment, so its seconds are already
        # segment-relative and need no client-side offset.
        return upnp_response(
            upnp_transport_state(device),
            upnp_position_info(device),
            PLAYBACK_CORE.snapshot(),
            cue_segment=cue_segment_declaration(PLAYBACK_CORE.current_item()),
        ), 200
    except Exception as exc:
        return backend_error_response(str(exc)), 502


def _upnp_track_id_from_uri(uri):
    return track_id_from_renderer_uri(uri)


def _dlna_stop_is_suppressed(target_id, transport, now=None):
    return stop_is_suppressed(
        DLNA_MONITOR_GUARD,
        target_id,
        transport,
        time.monotonic() if now is None else now,
    )


def _dlna_stalled_track_expired(current_track_id, backend_track_id, transport,
                                 reported_position, reported_duration,
                                 track_started_at, expected_duration, now=None):
    return stalled_track_expired(
        current_track_id,
        backend_track_id,
        transport,
        reported_position,
        reported_duration,
        track_started_at,
        expected_duration,
        time.monotonic() if now is None else now,
    )


def start_remote_output_monitor(server):
    """Keep external Renderer playback alive without a foreground UI.

    fnAudio deliberately owns queue progression for pushed renderers.  After
    a stable PLAYING->STOPPED transition, it loads one next queue item rather
    than relying on the renderer's optional NextURI state machine.
    """
    global REMOTE_OUTPUT_MONITOR_STOP, REMOTE_OUTPUT_MONITOR_THREAD, REMOTE_OUTPUT_MONITOR_GENERATION
    with REMOTE_OUTPUT_MONITOR_LOCK:
        if not stop_remote_output_monitor():
            # A timed-out monitor may still be blocked in renderer I/O. Do not
            # create a second monitor while that old generation is alive: both
            # could observe the same STOPPED transition and advance the queue.
            raise RuntimeError("DLNA renderer monitor is still stopping")
        stop_event = threading.Event()
        REMOTE_OUTPUT_MONITOR_GENERATION += 1
        return _start_remote_output_monitor_locked(
            server,
            stop_event,
            REMOTE_OUTPUT_MONITOR_GENERATION,
        )


def _remote_output_monitor_is_current(stop_event, generation):
    with REMOTE_OUTPUT_MONITOR_LOCK:
        return (
            REMOTE_OUTPUT_MONITOR_STOP is stop_event
            and REMOTE_OUTPUT_MONITOR_GENERATION == generation
            and not stop_event.is_set()
        )


def _start_remote_output_monitor_locked(server, stop_event, generation):
    """Create one renderer monitor while its lifecycle lock is held."""
    global REMOTE_OUTPUT_MONITOR_STOP, REMOTE_OUTPUT_MONITOR_THREAD
    monitor = {
        "target": "",
        "transport": "",
        "advance_at": 0.0,
        "track": "",
        "managed_key": "",
        "managed_playing": False,
        "start_pending_at": 0.0,
        "track_started_at": 0.0,
        "expected_duration": 0.0,
        "stalled_advance_at": 0.0,
        "missing_count": 0,
    }
    handler = SimpleNamespace(server=server, headers={})

    def loop():
        while not stop_event.wait(1.25):
            snapshot = PLAYBACK_CORE.state
            if not _remote_output_monitor_is_current(stop_event, generation):
                return
            if snapshot.target_kind != "dlna_push" or not snapshot.target_id:
                monitor.update({"target": "", "transport": "", "track": "", "managed_key": "", "managed_playing": False, "start_pending_at": 0.0, "track_started_at": 0.0, "expected_duration": 0.0, "stalled_advance_at": 0.0, "missing_count": 0})
                continue
            device = find_upnp_device(snapshot.target_id)
            if not device:
                monitor["missing_count"] = min(1000000, safe_int(monitor.get("missing_count")) + 1)
                if monitor["missing_count"] >= 3:
                    PLAYBACK_CORE.sync_output_status("dlna_push", "ERROR", error="DLNA renderer is offline")
                continue
            monitor["missing_count"] = 0
            try:
                transport_payload = upnp_transport_state(device) or {}
                position_payload = upnp_position_info(device) or {}
            except Exception as exc:
                if not _remote_output_monitor_is_current(stop_event, generation):
                    return
                PLAYBACK_CORE.sync_output_status("dlna_push", "ERROR", error=str(exc))
                continue
            if not _remote_output_monitor_is_current(stop_event, generation):
                return
            transport = str(transport_payload.get("state") or "UNKNOWN").upper()
            previous = monitor.get("transport") if monitor.get("target") == snapshot.target_id else ""
            monitor["target"] = snapshot.target_id
            monitor["transport"] = transport
            managed_key = "%s:%s" % (snapshot.target_id, snapshot.current_track_id)
            if snapshot.playing and (managed_key != monitor.get("managed_key") or not monitor.get("managed_playing")):
                monitor["managed_key"] = managed_key
                monitor["start_pending_at"] = time.monotonic()
                monitor["track_started_at"] = time.monotonic()
                monitor["expected_duration"] = safe_float(snapshot.duration)
                monitor["stalled_advance_at"] = 0.0
            monitor["managed_playing"] = bool(snapshot.playing)
            if transport in ("PLAYING", "TRANSITIONING", "PAUSED_PLAYBACK"):
                monitor["start_pending_at"] = 0.0

            backend_track_id = _upnp_track_id_from_uri(position_payload.get("track_uri"))
            if backend_track_id and backend_track_id != snapshot.current_track_id:
                if not _remote_output_monitor_is_current(stop_event, generation):
                    return
                before = snapshot.current_track_id
                PLAYBACK_CORE.select_current(backend_track_id)
                if PLAYBACK_CORE.state.current_track_id != before:
                    save_current_playback_session(server.config)

            reported_position = safe_float(position_payload.get("rel_seconds"))
            reported_duration = safe_float(position_payload.get("duration_seconds"))
            # Retain the library duration when a Renderer exposes a valid
            # URI but permanently returns 00:00:00 for both time fields.
            # Otherwise the monitor loses the only reliable end boundary.
            effective_duration = reported_duration or safe_float(monitor.get("expected_duration"))

            ended = previous in ("PLAYING", "TRANSITIONING") and transport in ("STOPPED", "NO_MEDIA_PRESENT")
            managed_playing = bool(snapshot.playing)
            stop_suppressed = _dlna_stop_is_suppressed(snapshot.target_id, transport)
            if stop_suppressed:
                if not _remote_output_monitor_is_current(stop_event, generation):
                    return
                monitor["start_pending_at"] = 0.0
                monitor["managed_playing"] = False
                PLAYBACK_CORE.sync_output_status(
                    "dlna_push",
                    "STOPPED",
                    reported_position,
                    effective_duration,
                )
                continue
            if ended and managed_playing:
                if not _remote_output_monitor_is_current(stop_event, generation):
                    return
                now = time.time()
                guard_track = snapshot.current_track_id
                if monitor.get("track") == guard_track and now - safe_float(monitor.get("advance_at")) < 3.0:
                    continue
                monitor.update({"track": guard_track, "advance_at": now})
                result = PLAYBACK_CORE.dispatch(
                    PlaybackCommand(
                        "next",
                        context={
                            "handler": handler,
                            "config": server.config,
                            "resolve_track": lambda track_id: find_library_item(server.config, track_id),
                        },
                    )
                )
                output = result.get("result") or {}
                if output.get("ok") is False:
                    PLAYBACK_CORE.sync_output_status("dlna_push", "STOPPED", error=str(output.get("message") or ""))
                save_current_playback_session(server.config)
                continue

            # Some TV renderers keep AVTransport at PLAYING and return
            # 00:00:00 for both position fields forever. Their end event is
            # otherwise unobservable, so advance only after the known source
            # duration has elapsed and the reported URI still matches.
            stalled_expired = _dlna_stalled_track_expired(
                snapshot.current_track_id,
                backend_track_id,
                transport,
                reported_position,
                reported_duration,
                safe_float(monitor.get("track_started_at")),
                safe_float(monitor.get("expected_duration")),
            )
            if stalled_expired and managed_playing:
                if not _remote_output_monitor_is_current(stop_event, generation):
                    return
                now = time.time()
                guard_track = snapshot.current_track_id
                if monitor.get("track") == guard_track and now - safe_float(monitor.get("stalled_advance_at")) < 3.0:
                    continue
                monitor.update({"track": guard_track, "stalled_advance_at": now})
                result = PLAYBACK_CORE.dispatch(
                    PlaybackCommand(
                        "next",
                        context={
                            "handler": handler,
                            "config": server.config,
                            "resolve_track": lambda track_id: find_library_item(server.config, track_id),
                        },
                    )
                )
                output = result.get("result") or {}
                if output.get("ok") is False:
                    PLAYBACK_CORE.sync_output_status("dlna_push", "STOPPED", error=str(output.get("message") or ""))
                save_current_playback_session(server.config)
                continue

            if transport in ("STOPPED", "NO_MEDIA_PRESENT") and managed_playing:
                pending_at = safe_float(monitor.get("start_pending_at"))
                if pending_at and time.monotonic() - pending_at < 4.0:
                    # A Renderer may acknowledge Play before it exposes the
                    # new transport state. Preserve the optimistic command
                    # state briefly, then surface a real rejection instead
                    # of silently pretending playback succeeded.
                    continue
                if not _remote_output_monitor_is_current(stop_event, generation):
                    return
                PLAYBACK_CORE.sync_output_status(
                    "dlna_push",
                    "ERROR",
                    reported_position,
                    effective_duration,
                    "Renderer accepted Play but did not enter PLAYING; source format may be unsupported",
                )
                continue

            if not _remote_output_monitor_is_current(stop_event, generation):
                return
            PLAYBACK_CORE.sync_output_status(
                "dlna_push",
                transport,
                reported_position,
                effective_duration,
            )

    thread = threading.Thread(target=loop, name="fnaudio-renderer-monitor", daemon=True)
    REMOTE_OUTPUT_MONITOR_STOP = stop_event
    REMOTE_OUTPUT_MONITOR_THREAD = thread
    try:
        thread.start()
    except Exception:
        # Do not publish a monitor handle that never started.  A later server
        # initialization must be able to retry instead of joining a phantom
        # thread during shutdown.
        REMOTE_OUTPUT_MONITOR_STOP = None
        REMOTE_OUTPUT_MONITOR_THREAD = None
        stop_event.set()
        raise
    return stop_event


def stop_remote_output_monitor(timeout=2.0):
    """Stop the renderer monitor before its HTTP/DLNA dependencies disappear."""
    global REMOTE_OUTPUT_MONITOR_STOP, REMOTE_OUTPUT_MONITOR_THREAD, REMOTE_OUTPUT_MONITOR_GENERATION
    with REMOTE_OUTPUT_MONITOR_LOCK:
        stop_event = REMOTE_OUTPUT_MONITOR_STOP
        thread = REMOTE_OUTPUT_MONITOR_THREAD
        REMOTE_OUTPUT_MONITOR_STOP = None
        REMOTE_OUTPUT_MONITOR_THREAD = None
        REMOTE_OUTPUT_MONITOR_GENERATION += 1
    if stop_event is not None:
        stop_event.set()
    if thread is not None and thread is not threading.current_thread():
        try:
            bounded_timeout = float(timeout)
        except (TypeError, ValueError, OverflowError):
            bounded_timeout = 2.0
        if not math.isfinite(bounded_timeout):
            bounded_timeout = 2.0
        thread.join(timeout=max(0.0, bounded_timeout))
        is_alive = getattr(thread, "is_alive", None)
        if callable(is_alive):
            try:
                return not bool(is_alive())
            except Exception:
                # A test double or an unusual thread implementation without a
                # reliable liveness probe has already received the stop and
                # join request; preserve the historical best-effort contract.
                return True
    return True


def initialize_dlna_services(server):
    """Attach independent DLNA roles after the HTTP listener has a real port."""
    global DLNA_PROTOCOL, DLNA_SSDP

    def base_url():
        return "http://%s:%s" % (local_address(), server.server_address[1])

    def renderer_load(uri, start=0.0):
        if not uri.startswith(("http://", "https://")):
            return {"ok": False, "message": "DLNA renderer only accepts HTTP media URIs"}
        try:
            started = MPD_OUTPUT.start_service()
            if started.get("ok") is False and not started.get("running"):
                return {"ok": False, "message": started.get("message") or "MPD is unavailable"}
            service_load_uri = getattr(MPD_SERVICE, "load_uri", None)
            if callable(service_load_uri):
                return service_load_uri(uri, start=start)
            return mpd_load_uri(uri, host=MPD_SERVICE.host, port=MPD_SERVICE.port, start=start)
        except Exception as exc:
            return {"ok": False, "message": "DLNA renderer playback failed: %s" % exc}

    def renderer_control(action, position=None):
        try:
            if action == "volume" and MPD_SERVICE:
                mixer = MPD_SERVICE.mixer_policy()
                if not mixer.get("available"):
                    return {"ok": False, "message": mixer.get("message") or "renderer volume control is unavailable"}
            service_control = getattr(MPD_SERVICE, "control", None)
            if callable(service_control):
                return service_control(action, position)
            return mpd_control(action, position, host=MPD_SERVICE.host, port=MPD_SERVICE.port)
        except Exception as exc:
            return {"ok": False, "message": "DLNA renderer control failed: %s" % exc}

    def renderer_status():
        try:
            # MpdService is refreshed by its MPD idle listener. Reuse that
            # projection so renderer status checks do not create a second
            # one-second MPD polling loop.
            probe = MPD_SERVICE.status() if MPD_SERVICE else {}
            return probe.get("status") or {"transport": {"state": "STOPPED"}, "position": {"rel_seconds": 0, "duration_seconds": 0}}
        except Exception:
            return {"transport": {"state": "STOPPED"}, "position": {"rel_seconds": 0, "duration_seconds": 0}}

    def page(params):
        return query_library_page(server.config, params)

    # The two browse closures forward the bounded page DLNA asks for, so a
    # container can be read one window at a time instead of materializing every
    # row first. The roots closure stays unbounded: one configured library root
    # is one row, and that read has no paging statement to page through.
    def groups(view, limit=None, offset=0, sort_dir="asc"):
        return query_library_groups(server.config, view, limit=limit, offset=offset, sort_dir=sort_dir) or []

    def roots():
        return query_library_root_folders(server.config) or []

    def folders(parent, root, limit=None, offset=0, sort_dir="asc"):
        return query_library_folders(server.config, parent, root, sort_dir=sort_dir, limit=limit, offset=offset) or []

    def output_capabilities():
        try:
            return MPD_SERVICE.output_capabilities() if MPD_SERVICE else {}
        except Exception:
            return {}

    def library_item(item_id):
        return query_library_item_by_id(server.config, item_id)

    def system_update_id():
        signature = str(FS_CACHE.get("signature") or "empty")
        return int(hashlib.sha256(signature.encode("utf-8")).hexdigest()[:8], 16)

    def renderer_state_changed(state):
        uri = str(state.get("uri") or "")
        title = str(state.get("title") or os.path.basename(urllib.parse.urlparse(uri).path) or "DLNA input")
        PLAYBACK_CORE.sync_external_session(
            "dlna-renderer",
            title,
            uri,
            str(state.get("transport") or "STOPPED"),
            safe_float(state.get("position")),
            safe_float(state.get("duration")),
            error=str(state.get("last_error") or ""),
        )

    renderer = DlnaRenderer(renderer_load, renderer_control, renderer_status, renderer_state_changed)
    DLNA_PROTOCOL = DlnaProtocolService(
        base_url,
        renderer,
        page,
        groups,
        upnp_resource_mime,
        roots,
        folders,
        output_capabilities,
        library_item=library_item,
        system_update_id=system_update_id,
    )
    DLNA_SSDP = SsdpService(base_url)
    configure_local_renderer_identity(
        DLNA_SSDP.location("renderer"),
        DLNA_SSDP.udn("renderer"),
    )
    DLNA_SSDP.start()


def shutdown_runtime(server=None):
    """Release runtime workers and external services after any startup path.

    Startup can fail before ``serve_forever`` is entered (for example when the
    configured HTTP port is already occupied). Keep each cleanup step
    independent so a partially initialized optional service cannot strand the
    remaining workers.
    """
    cleanup_steps = (
        lambda: cancel_playback_restore_retry(),
        lambda: stop_remote_output_monitor(),
        lambda: shutdown_library_refresh(wait=True),
        lambda: stop_library_watcher(wait=True),
        lambda: shutdown_transcode_cache_worker(wait=True),
        lambda: shutdown_library_thumbnail_prewarm(wait=True),
        lambda: shutdown_upnp_cache_background(wait=True),
        lambda: DLNA_SSDP.stop() if DLNA_SSDP else None,
        lambda: DLNA_PROTOCOL.shutdown() if DLNA_PROTOCOL else None,
        lambda: MPD_SERVICE.shutdown() if MPD_SERVICE else None,
        lambda: AIRPLAY_SERVICE.shutdown() if AIRPLAY_SERVICE else None,
        lambda: METADATA_SERVICE.shutdown() if METADATA_SERVICE else None,
        # Every reader above has to be quiesced first: a metadata worker still
        # inside a provider chain can open or hand a library handle back to the
        # pool after the drain, which is exactly what keeps an index file open
        # past shutdown.
        lambda: stop_library_connections(),
    )
    for cleanup in cleanup_steps:
        try:
            cleanup()
        except Exception as exc:
            print("fnAudio runtime cleanup failed: %s" % exc, flush=True)
    if server is not None:
        try:
            server.server_close()
        except Exception as exc:
            print("fnAudio HTTP server cleanup failed: %s" % exc, flush=True)


def main():
    global MPD_SERVICE, DLNA_SSDP, METADATA_SERVICE, AIRPLAY_SERVICE
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()
    if os.name != "nt":
        os.umask(0o077)
    config = load_config(args.config)
    MPD_SERVICE = MpdService(
        config,
        app_root=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        app_config_path=args.config,
    )
    AIRPLAY_SERVICE = AirplayService(config, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    MPD_OUTPUT.configure(MPD_SERVICE)
    mpd_advance_guard = {"at": 0.0, "track_id": ""}

    def on_mpd_transport(previous, current, probe):
        status = dict((probe or {}).get("status") or {})
        position = dict(status.get("position") or {})
        raw = dict(status.get("raw") or {})
        snapshot = PLAYBACK_CORE.state
        backend_track_id = MPD_SERVICE.track_id_for_status(probe)
        if backend_track_id and backend_track_id != snapshot.current_track_id:
            before = snapshot.current_track_id
            PLAYBACK_CORE.select_current(backend_track_id)
            snapshot = PLAYBACK_CORE.state
            if snapshot.current_track_id != before:
                save_current_playback_session(config)
        # Read the item only after the current track has been settled above, so
        # a backend-selected song never borrows the offsets of the previous one.
        transport_position = project_mpd_transport_position(position, PLAYBACK_CORE.current_item())
        transport_rel = transport_position["rel_seconds"]
        transport_duration = transport_position["duration_seconds"]
        managed_track_ended = (
            previous == "PLAYING"
            and current == "STOPPED"
            and snapshot.target_kind == "mpd"
            and snapshot.playing
        )
        if not managed_track_ended:
            PLAYBACK_CORE.sync_output_status(
                "mpd",
                current,
                transport_rel,
                transport_duration,
                str(raw.get("error") or ""),
            )
            return
        now = time.time()
        if mpd_advance_guard["track_id"] == snapshot.current_track_id and now - mpd_advance_guard["at"] < 3.0:
            return
        mpd_advance_guard.update({"track_id": snapshot.current_track_id, "at": now})
        result = PLAYBACK_CORE.dispatch(
            PlaybackCommand(
                "next",
                context={
                    "config": config,
                    "resolve_track": lambda track_id: find_library_item(config, track_id),
                },
            )
        )
        if not (result.get("result") or {}).get("ok", False):
            PLAYBACK_CORE.sync_output_status(
                "mpd",
                "STOPPED",
                transport_rel,
                transport_duration,
                str((result.get("result") or {}).get("message") or raw.get("error") or ""),
            )
        save_current_playback_session(config)

    MPD_SERVICE.set_status_listener(on_mpd_transport)
    try:
        started_mpd = MPD_OUTPUT.start_service()
        if started_mpd.get("ok") is False and not started_mpd.get("running"):
            print("fnAudio MPD optional backend unavailable: %s" % (started_mpd.get("message") or started_mpd), flush=True)
    except Exception as exc:
        print("fnAudio MPD optional backend failed to start: %s" % exc, flush=True)
    if args.port is None:
        args.port = config["server_port"]
    else:
        config["server_port"] = args.port
    if not config.get("cache_dir"):
        config["cache_dir"] = os.path.join(os.path.dirname(os.path.abspath(args.config)), "transcode")
    cleanup_transcode_cache_if_due(config, True)
    # Pooling idle read handles is `config.py`'s default. The first-screen breakdown
    # recorded in CHANGELOG_AI.md (2026-09-17) measured a cold page at 2.67ms with
    # 1.46ms of it spent reopening the index, which is why reuse is the shipped
    # default, and that default now survives `save_config`. Startup must not inject
    # a second copy of it: an injected key is invisible to every other configuration
    # reader and gets dropped from disk on the first settings save.
    load_library_cache(config)
    # Existing indexes may predate thumbnail assets. Warm them after startup
    # as well as after future scans, without delaying the HTTP listener.
    # Do not materialize the whole SQLite library during startup just to warm
    # thumbnails.  When an existing index is authoritative, MUSIC_CACHE may
    # intentionally contain no rows; loading all rows here competed with the
    # first `/api/library` request and made the initial list appear to stall.
    # Scan completion already schedules bounded library prewarm, while visible
    # pages use the interactive cover scheduler on demand.
    # Only seed the first visible window during cold start.  Passing the
    # entire in-memory index still made ``bounded_unique_items`` walk tens of
    # thousands of rows before the listener could accept the first request.
    # Scan completion continues the bounded background warmup for the rest.
    startup_items = MUSIC_CACHE.get("items") if isinstance(MUSIC_CACHE, dict) else []
    if not isinstance(startup_items, (list, tuple)):
        startup_items = []
    prewarm_library_thumbnails(startup_items[:STARTUP_THUMBNAIL_PREWARM_LIMIT], config, cached_cover_for_item)
    METADATA_SERVICE = MetadataService(config)
    METADATA_SERVICE.start()
    enable_playback_restore_retry()
    restore_playback_session(config)
    web_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui"))
    save_proxy_port(web_root, args.port)
    server = None
    try:
        try:
            server = BoundedThreadingHTTPServer((args.host, args.port), Handler, config.get("http_max_workers", 32))
        except OSError as exc:
            save_proxy_port(web_root, args.port)
            print("fnAudio port %s unavailable (%s), service not started" % (args.port, exc), flush=True)
            raise
        server.config = config
        server.config_path = args.config
        server.web_root = web_root
        initialize_dlna_services(server)
        start_remote_output_monitor(server)
        if config.get("airplay_enabled"):
            started_airplay = AIRPLAY_SERVICE.start()
            if not started_airplay.get("ok"):
                print("fnAudio AirPlay optional backend unavailable: %s" % (started_airplay.get("message") or started_airplay), flush=True)
        if not MUSIC_CACHE["stamp"]:
            request_library_refresh(config, False)
        start_library_watcher(config)
        print("fnAudio listening on %s:%s, library=%s" % (args.host, args.port, config["library_path"]), flush=True)
        server.serve_forever()
    finally:
        shutdown_runtime(server)


if __name__ == "__main__":
    main()

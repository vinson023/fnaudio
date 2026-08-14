#!/usr/bin/env python3
import argparse
import base64
import hashlib
import html
import json
import mimetypes
import os
import re
import signal
import socket
import shutil
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from xml.etree import ElementTree as ET

from config import load_config, save_config, save_proxy_port
from library import (
    FS_CACHE,
    MUSIC_CACHE,
    SCAN_LOCK,
    SCAN_STATE,
    apply_library_paths,
    cancel_library_refresh,
    canonical_library_path,
    is_allowed_library_path,
    library_items,
    library_status,
    load_items_from_sqlite,
    is_library_item_path,
    list_music_directories,
    load_library_cache,
    merge_library_paths,
    normalize_library_paths,
    query_library_folders,
    query_library_item_by_id,
    query_library_item_location,
    query_library_items_by_ids,
    query_library_root_folders,
    query_library_groups,
    query_library_page,
    request_library_refresh,
    read_cover_for_item,
    save_library_cache,
    safe_float,
    safe_int,
    watch_library,
)
from dlna.control_point import (
    UPNP_CACHE,
    discover_upnp,
    find_service_url,
    refresh_upnp_cache_background,
    seconds_to_upnp_time,
    upnp_control,
    upnp_position_info,
    upnp_transport_state,
)
from dlna.diagnostics import DlnaDiagnostics
from dlna.media_server import (
    soap_push as dlna_soap_push,
    upnp_media_url as dlna_media_url,
    upnp_resource_mime,
    upnp_resource_size as dlna_resource_size,
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
    normalize_queue_tracks,
    normalize_target_id,
    playback_event_payload,
    target_kind as playback_target_kind,
)
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
from metadata_service import MetadataService
from api_auth import authorize_api, requires_resource_auth
from fnos_api import FnosApiError, call_trim_api
from observability import OBSERVABILITY, request_id
from diagnostics import support_snapshot
from version import APP_USER_AGENT
from cover_cache import (cached_thumbnail_for_item, cover_is_known_missing, cover_source_version,
                         normalized_cover_size, prewarm_thumbnails, thumbnail_asset_bytes,
                         thumbnail_asset_id_for_item, prewarm_library_thumbnails,
                         shutdown_library_thumbnail_prewarm)

STATE = {"queue": [], "current": None, "playing": False}
PLAYBACK_CORE = PlaybackCore()
MPD_OUTPUT = MpdOutput()
MPD_SERVICE = None
DLNA_PROTOCOL = None
DLNA_SSDP = None
METADATA_SERVICE = None
AIRPLAY_SERVICE = None
DLNA_DIAGNOSTICS = DlnaDiagnostics()
CUE_AUTO_ADVANCE = {"track_id": "", "at": 0.0}
DLNA_MONITOR_GUARD = {"target_id": "", "suppress_stop_until": 0.0}
PLAYBACK_COMMAND_LOCK = threading.RLock()
PLAYBACK_COMMAND_RESULTS = {}
PLAYBACK_COMMAND_TTL_SECONDS = 30.0
TRANSPARENT_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lR4YJwAAAABJRU5ErkJggg=="
)
COVER_CACHE_LOCK = threading.RLock()
COVER_CACHE = {}
COVER_CACHE_MAX_ENTRIES = 512


def cached_cover_for_item(item, config):
    """Cache extracted local artwork by its on-disk version.

    Library rows often share one embedded or sidecar cover. Without this
    cache a mobile page can ask the service to parse that same image dozens
    of times concurrently before its HTTP cache has a chance to help.
    """
    path = str((item or {}).get("path") or "")
    modified = safe_int((item or {}).get("modified_ns") or (item or {}).get("modified"))
    key = (path, modified)
    with COVER_CACHE_LOCK:
        cached = COVER_CACHE.get(key)
        if cached is not None:
            return cached
    value = read_cover_for_item(item, config)
    with COVER_CACHE_LOCK:
        if len(COVER_CACHE) >= COVER_CACHE_MAX_ENTRIES:
            COVER_CACHE.pop(next(iter(COVER_CACHE)), None)
        COVER_CACHE[key] = value
    return value


def parse_single_byte_range(size, header=""):
    size = int(size)
    if size <= 0:
        return 200, 0, -1
    value = str(header or "").strip()
    if not value:
        return 200, 0, size - 1
    if not value.lower().startswith("bytes=") or "," in value:
        raise ValueError("unsupported byte range")
    spec = value[6:].strip()
    left, separator, right = spec.partition("-")
    if not separator or (not left and not right):
        raise ValueError("invalid byte range")
    try:
        if left:
            start = int(left)
            end = int(right) if right else size - 1
        else:
            suffix = int(right)
            if suffix <= 0:
                raise ValueError("invalid byte range")
            start = max(0, size - suffix)
            end = size - 1
    except (TypeError, ValueError):
        raise ValueError("invalid byte range")
    end = min(end, size - 1)
    if start < 0 or start >= size or start > end:
        raise ValueError("unsatisfiable byte range")
    return 206, start, end








def is_tcp_port_available(port, current_port=0):
    if int(port) == int(current_port or 0):
        return True
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("0.0.0.0", int(port)))
        return True
    except OSError:
        return False
    finally:
        probe.close()


def find_free_tcp_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("0.0.0.0", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()














































































def local_address():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()






















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
    warm_transcode_cache,
)
from resource_limits import ResourceLimitError, ffmpeg_slot


def public_base_url(handler):
    host = handler.headers.get("X-Forwarded-Host") or handler.headers.get("Host", "")
    proto = handler.headers.get("X-Forwarded-Proto") or "http"
    if not host:
        host = "127.0.0.1:5666"
    hostname, _, port = host.partition(":")
    if not is_private_host(hostname):
        hostname = local_address()
    if not port:
        port = "5666"
    return "%s://%s:%s/cgi/ThirdParty/fnaudio/index.cgi" % (proto, hostname, port)


def upnp_base_url(handler):
    return "http://%s:%s" % (local_address(), handler.server.server_address[1])


def safe_filename(value):
    name = re.sub(r'[\\/:*?"<>|]+', "_", str(value or "").strip())
    return name[:120] or "track"


def upnp_media_url(handler, item):
    return dlna_media_url(handler, item, safe_filename, upnp_base_url)


def upnp_resource_size(item, config):
    return dlna_resource_size(item, config, transcode_to_audio)


def soap_push(device, item, handler, next_item=None):
    return dlna_soap_push(device, item, handler, safe_filename, upnp_base_url, transcode_to_audio, next_item)


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


class Handler(BaseHTTPRequestHandler):
    server_version = APP_USER_AGENT

    def log_message(self, fmt, *args):
        return

    def current_request_id(self):
        if not getattr(self, "_request_id", ""):
            self._request_id = request_id(self.headers.get("X-Request-ID"))
        return self._request_id

    def record_request(self, status):
        status = int(status)
        OBSERVABILITY.count("http_requests_total")
        OBSERVABILITY.count("http_status_%sxx" % max(1, min(5, status // 100)))
        config = getattr(self.server, "config", {}) or {}
        OBSERVABILITY.write(
            config.get("structured_log_path") or os.path.join(os.path.dirname(getattr(self.server, "config_path", "") or "."), "fnaudio.jsonl"),
            "http_request",
            request_id=self.current_request_id(),
            method=self.command,
            route=urllib.parse.urlparse(self.path).path,
            status=status,
        )

    def send_json(self, payload, status=200, extra_headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("X-Request-ID", self.current_request_id())
        for name, value in (extra_headers or {}).items():
            self.send_header(str(name), str(value))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.record_request(status)
        if self.command == "HEAD":
            return
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        return self.handle_get(head_only=False)

    def trim_api_token(self):
        for name in ("X-Fnaudio-Trim-Token", "Trim-Token", "X-Trim-Token", "Authorization"):
            value = (self.headers.get(name) or "").strip()
            if not value:
                continue
            if value.lower().startswith("bearer "):
                value = value.split(None, 1)[1].strip()
            return value
        return ""

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
        body = body if isinstance(body, bytes) else str(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def do_HEAD(self):
        return self.handle_get(head_only=True)

    def record_dlna(self, event, **values):
        try:
            DLNA_DIAGNOSTICS.record(
                event,
                client_ip=(self.headers.get("X-Forwarded-For") or self.headers.get("X-Real-IP") or self.client_address[0]).split(",", 1)[0].strip(),
                user_agent=self.headers.get("User-Agent", ""),
                range=self.headers.get("Range", ""),
                accept=self.headers.get("Accept", ""),
                **values,
            )
        except Exception:
            pass

    def handle_get(self, head_only=False):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        if path.startswith("/dlna/"):
            return self.handle_dlna_get(path, head_only)
        if path.startswith("/api/") and not self.authorize_api_request("HEAD" if head_only else "GET", path):
            return
        if requires_resource_auth(path) and not self.authorize_api_request("HEAD" if head_only else "GET", path):
            return
        if path == "/api/health":
            mpd = MPD_SERVICE.status() if MPD_SERVICE else {}
            metadata = METADATA_SERVICE.status() if METADATA_SERVICE else {}
            transcode = transcode_resource_status(self.server.config)
            return self.send_json({
                "ok": True,
                "name": self.server.config["server_name"],
                "request_id": self.current_request_id(),
                "components": {
                    "mpd": {
                        "running": bool(mpd.get("running")),
                        "fault": (mpd.get("fault") or {}).get("state", ""),
                        "error_category": (mpd.get("playback_errors") or {}).get("last_category", ""),
                    },
                    "library": {
                        "scanning": bool(SCAN_STATE.get("running")),
                        "cancelled": bool(SCAN_STATE.get("cancelled")),
                        "timed_out": bool(SCAN_STATE.get("timed_out")),
                        "errors": len(SCAN_STATE.get("errors") or []),
                    },
                    "metadata": {
                        "running": bool(metadata.get("running")),
                        "pending": int(metadata.get("pending") or 0),
                        "pending_limit": int(metadata.get("pending_limit") or 0),
                        "dropped": int(metadata.get("dropped") or 0),
                        "artwork_bytes": int(metadata.get("artwork_bytes") or 0),
                        "artwork_limit_bytes": int(metadata.get("artwork_limit_bytes") or 0),
                    },
                    "transcode": transcode,
                    "dlna": {"running": bool(DLNA_PROTOCOL), "renderers": len(UPNP_CACHE.get("items") or [])},
                },
                "metrics": OBSERVABILITY.snapshot(),
            })
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
                renderer_count=len(UPNP_CACHE.get("items") or []),
                metrics=OBSERVABILITY.snapshot(),
                playback=PLAYBACK_CORE.snapshot(),
            ))
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
                page["items"] = [public_item(x, self.server.config) for x in page.get("items", [])]
                return self.send_json(page)
            compat_query = dict(query)
            compat_query.setdefault("paged", ["1"])
            compat_query.setdefault("limit", ["120"])
            compat_query.setdefault("offset", ["0"])
            page = query_library_page(self.server.config, compat_query)
            prewarm_thumbnails(page.get("items"), self.server.config, cached_cover_for_item)
            page["items"] = [public_item(x, self.server.config) for x in page.get("items", [])]
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
                sort_dir = (query.get("dir") or ["asc"])[0]
                result = query_library_groups(self.server.config, view, search, limit, offset, sort_dir, artist, composer)
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
                return self.send_json(query_library_folders(self.server.config, parent, root, sort_dir, (query.get("limit") or ["100"])[0], (query.get("offset") or ["0"])[0], search))
            return self.send_json({"folders": query_library_folders(self.server.config, parent, root, sort_dir, search=search)})
        if path == "/api/library/roots":
            search = (query.get("search") or [""])[0]
            return self.send_json({"roots": query_library_root_folders(self.server.config, search)})
        if path == "/api/library/items":
            raw_ids = (query.get("ids") or [""])[0]
            ids = [x.strip() for x in raw_ids.split(",") if x.strip()]
            return self.send_json({"items": [public_item(x, self.server.config) for x in query_library_items_by_ids(self.server.config, ids)]})
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
            track_id = (query.get("track_id") or [""])[0]
            if not track_id:
                return self.send_json({"ok": False, "message": "Missing track_id"}, HTTPStatus.BAD_REQUEST)
            return self.send_json(METADATA_SERVICE.track_match(track_id) if METADATA_SERVICE else {"ok": False, "message": "Metadata service is not running"})
        if path.startswith("/metadata/artwork/"):
            asset_id = path.rsplit("/", 1)[-1]
            return self.serve_metadata_artwork(asset_id, head_only)
        if False and path == "/api/fnos/shared-folders":
            token = self.trim_api_token()
            try:
                paths, raw = get_shared_accessible_folders(token)
                return self.send_json({"ok": True, "paths": paths, "raw": raw, "token_source": "request" if token else "service"})
            except FnosApiError as exc:
                return self.send_json({"ok": False, "paths": [], "message": str(exc), "token_source": "request" if token else "service"})
            except Exception as exc:
                return self.send_json({"ok": False, "paths": [], "message": "读取飞牛授权目录失败：%s" % exc, "token_source": "request" if token else "service"})
        if path == "/api/artwork":
            kind = (query.get("kind") or [""])[0]
            q = (query.get("q") or [""])[0]
            if kind not in ("album", "artist"):
                return self.send_json({"image_url": ""})
            return self.send_json(METADATA_SERVICE.cached_entity(kind, q) if METADATA_SERVICE else {"image_url": ""})
        if path == "/api/album-metadata":
            return self.send_json(METADATA_SERVICE.cached_entity("album", (query.get("q") or [""])[0], (query.get("artist") or [""])[0]) if METADATA_SERVICE else {"artist": "", "release_date": ""})
        if path == "/api/lyrics":
            item_id = (query.get("track_id") or [""])[0]
            item = find_library_item(self.server.config, item_id)
            if not item:
                return self.send_json({"error": "track not found"}, 404)
            result = METADATA_SERVICE.lyrics(item_id) if METADATA_SERVICE else None
            return self.send_json(result or {"lyrics": "", "source": "", "pending": False})
        if path == "/api/fs/list":
            dirs = list_music_directories((query.get("path") or [""])[0])
            return self.send_json({"path": (query.get("path") or [""])[0], "dirs": dirs})
        if path == "/api/upnp/devices":
            if time.time() - UPNP_CACHE["stamp"] > 15:
                refresh_upnp_cache_background()
            return self.send_json({"devices": UPNP_CACHE["items"]})
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
            return self.send_json({"available": bool(DLNA_PROTOCOL), **DLNA_DIAGNOSTICS.snapshot()})
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
            devices = UPNP_CACHE["items"] or discover_upnp()
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
        return self.serve_static(path, head_only)

    def do_POST(self):
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
        return self.handle_dlna_subscription(False)

    def do_UNSUBSCRIBE(self):
        return self.handle_dlna_subscription(True)

    def stream_playback_events(self, query):
        """Stream authoritative playback snapshots without polling an output.

        Backend monitors already merge MPD/DAC/renderer changes into
        ``PLAYBACK_CORE``.  This endpoint only waits for that state version to
        change, keeping one output owner even with several Web UIs connected.
        """
        raw_target = (query.get("target_id") or [""])[0]
        requested_target = str(raw_target or "")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        last_version = -1
        try:
            while True:
                # ``wait_for_version`` blocks until a backend monitor or
                # control command changes state. A timeout merely emits an
                # SSE heartbeat, so idle clients consume no polling loop.
                PLAYBACK_CORE.wait_for_version(last_version, 15.0)
                core = PLAYBACK_CORE.snapshot()
                version = safe_int(core.get("state_version"))
                if version != last_version:
                    payload = playback_event_payload(core, requested_target)
                    wire = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                    self.wfile.write(("id: %s\nevent: playback\ndata: " % version).encode("ascii"))
                    self.wfile.write(wire)
                    self.wfile.write(b"\n\n")
                    self.wfile.flush()
                    last_version = version
                else:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def handle_dlna_subscription(self, unsubscribe=False):
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
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api/") and not self.authorize_api_request("POST", parsed.path):
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length > 2 * 1024 * 1024:
            return self.send_json({"ok": False, "error": "request body is too large"}, 413)
        raw = self.rfile.read(length) if length else b"{}"
        if parsed.path.startswith("/dlna/"):
            return self.handle_dlna_post(parsed.path, raw)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except ValueError:
            return self.send_json({"error": "invalid json"}, 400)
        if parsed.path == "/api/player/state":
            return self.send_json(
                apply_legacy_player_state(payload, STATE, PLAYBACK_CORE),
                extra_headers=legacy_response_headers(parsed.path),
            )
        if parsed.path == "/api/state/user":
            if not isinstance(payload, dict):
                return self.send_json({"ok": False, "error": "invalid state payload"}, 400)
            try:
                revision = payload.get("revision")
                expected_revision = int(revision) if revision is not None else None
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
            target_id = str(payload.get("target_id") or "local")
            target_kind = playback_target_kind(target_id)
            normalized = normalize_target_id(target_id)
            PLAYBACK_CORE.set_target(normalized, target_kind)
            revision = save_current_playback_session(self.server.config)
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
            action = str(payload.get("action") or "").lower()
            if action == "start":
                result = AIRPLAY_SERVICE.start()
            elif action == "stop":
                result = AIRPLAY_SERVICE.stop()
            elif action == "restart":
                AIRPLAY_SERVICE.stop()
                result = AIRPLAY_SERVICE.start()
            else:
                return self.send_json({"ok": False, "message": "unknown AirPlay action"}, 400)
            return self.send_json(result, 200 if result.get("ok", True) else 409)
        if parsed.path == "/api/playback/queue":
            response, status = playback_queue(self.server.config, payload)
            return self.send_json(response, status)
        if parsed.path == "/api/playback/control":
            response, status = playback_control_idempotent(self, payload)
            return self.send_json(response, status)
        if parsed.path == "/api/transcode/warm":
            item_id = str(payload.get("track_id") or "")
            mode = str(payload.get("mode") or "mp3")
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
        if False and parsed.path == "/api/fnos/shared-folders/sync":
            try:
                authorized_paths, _ = get_shared_accessible_folders(self.trim_api_token())
            except FnosApiError as exc:
                return self.send_json({"ok": False, "message": str(exc)}, 400)
            except Exception as exc:
                return self.send_json({"ok": False, "message": "同步飞牛授权目录失败：%s" % exc}, 500)
            allowed_paths = [
                os.path.abspath(os.path.expanduser(path))
                for path in authorized_paths
                if is_allowed_library_path(path) and os.path.isdir(path)
            ]
            if not allowed_paths:
                return self.send_json({"ok": False, "message": "没有可用的飞牛授权音乐目录"}, 400)
            current_paths = normalize_library_paths(self.server.config)
            if not self.server.config.get("library_paths") and str(self.server.config.get("library_path", "")).strip() in ("", "."):
                current_paths = []
            merged_paths = merge_library_paths(current_paths, allowed_paths)
            apply_library_paths(self.server.config, merged_paths)
            if not save_config(self.server.config_path, self.server.config):
                return self.send_json({"ok": False, "message": "保存授权目录失败"}, 500)
            return self.send_json(
                {
                    "ok": True,
                    "paths": merged_paths,
                    "authorized_paths": authorized_paths,
                    "status": library_status(self.server.config),
                    "message": "已同步飞牛授权目录。需要更新时请点击刷新音乐库。",
                }
            )
        if False and parsed.path == "/api/fnos/shared-folders/delete":
            path_to_delete = os.path.realpath(os.path.abspath(os.path.expanduser(str(payload.get("path", "")).strip())))
            if not path_to_delete:
                return self.send_json({"ok": False, "message": "缺少要删除的授权目录"}, 400)
            configured_paths = {os.path.realpath(path) for path in normalize_library_paths(self.server.config)}
            if path_to_delete not in configured_paths or not is_allowed_library_path(path_to_delete):
                return self.send_json({"ok": False, "message": "只能删除当前已配置的授权目录"}, 403)
            try:
                del_shared_accessible_folder(path_to_delete, self.trim_api_token())
            except FnosApiError as exc:
                return self.send_json({"ok": False, "message": str(exc)}, 400)
            except Exception as exc:
                return self.send_json({"ok": False, "message": "删除飞牛授权目录失败：%s" % exc}, 500)
            remaining_paths = [
                path for path in normalize_library_paths(self.server.config)
                if os.path.realpath(path) != path_to_delete
            ]
            apply_library_paths(self.server.config, remaining_paths)
            if not save_config(self.server.config_path, self.server.config):
                return self.send_json({"ok": False, "message": "授权已删除，但本地设置保存失败"}, 500)
            return self.send_json({"ok": True, "paths": remaining_paths, "status": library_status(self.server.config)})
        if parsed.path == "/api/config/metadata":
            try:
                grace_days = max(0, min(90, int(payload.get("orphan_grace_days", self.server.config.get("metadata_orphan_grace_days", 7)))))
            except (TypeError, ValueError):
                return self.send_json({"ok": False, "message": "缓存清理宽限天数必须是 0-90 的整数"}, 400)
            self.server.config["metadata_enabled"] = bool(payload.get("enabled", True))
            self.server.config["metadata_orphan_grace_days"] = grace_days
            if not save_config(self.server.config_path, self.server.config):
                return self.send_json({"ok": False, "message": "保存元数据设置失败"}, 500)
            if METADATA_SERVICE:
                METADATA_SERVICE.wake(force=bool(payload.get("refresh")))
            return self.send_json({"ok": True, "status": METADATA_SERVICE.status() if METADATA_SERVICE else {}})
        if parsed.path == "/api/metadata/refresh":
            if not METADATA_SERVICE:
                return self.send_json({"ok": False, "message": "后台元数据服务没有启动"}, 503)
            METADATA_SERVICE.wake(force=True)
            return self.send_json({"ok": True, "message": "已加入后台补全队列"})
        if parsed.path == "/api/metadata/retry-tag-writes":
            if not METADATA_SERVICE:
                return self.send_json({"ok": False, "message": "Metadata service is not running"}, 503)
            retried = METADATA_SERVICE.retry_failed_tag_writes()
            return self.send_json({"ok": True, "retried": retried, "status": METADATA_SERVICE.status()})
        if parsed.path == "/api/metadata/track/apply":
            if not METADATA_SERVICE:
                return self.send_json({"ok": False, "message": "Metadata service is not running"}, 503)
            track_id = str(payload.get("track_id") or "")
            if not track_id:
                return self.send_json({"ok": False, "message": "Missing track_id"}, 400)
            candidate_index = payload.get("candidate_index", 0)
            if isinstance(candidate_index, bool):
                return self.send_json({"ok": False, "message": "candidate_index must be a non-negative integer"}, 400)
            try:
                candidate_index = int(candidate_index)
            except (TypeError, ValueError):
                return self.send_json({"ok": False, "message": "candidate_index must be a non-negative integer"}, 400)
            if candidate_index < 0:
                return self.send_json({"ok": False, "message": "candidate_index must be a non-negative integer"}, 400)
            if not METADATA_SERVICE.apply_track_match(track_id, candidate_index):
                return self.send_json({"ok": False, "message": "No matching candidate is available for this track"}, 404)
            return self.send_json({"ok": True, "status": METADATA_SERVICE.track_match(track_id)})
        if parsed.path == "/api/config/library":
            raw_library_path = str(payload.get("library_path", ""))
            candidate_paths = [
                canonical_library_path(x.strip())
                for x in re.split(r"[\r\n;]+", raw_library_path)
                if x.strip()
            ]
            if not candidate_paths:
                return self.send_json({"ok": False, "message": "请输入音乐目录"}, 400)
            bad_path = next((x for x in candidate_paths if not is_allowed_library_path(x) or not os.path.isdir(x)), "")
            if bad_path:
                return self.send_json({"ok": False, "message": "这个目录不能作为音乐目录：%s" % bad_path}, 400)
            apply_library_paths(self.server.config, candidate_paths)
            if not save_config(self.server.config_path, self.server.config):
                return self.send_json({"ok": False, "message": "保存设置失败"}, 500)
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

    def serve_static(self, path, head_only=False):
        if path in ("", "/"):
            path = "/index.html"
        relative = urllib.parse.unquote(path.lstrip("/"))
        if ".." in relative.split("/"):
            return self.send_error(400)
        target = os.path.join(self.server.web_root, relative)
        if not os.path.isfile(target):
            return self.send_error(404)
        body = b""
        if not head_only:
            with open(target, "rb") as fh:
                body = fh.read()
        else:
            body = b""
        mime_type = mimetypes.guess_type(target)[0]
        # Windows and some minimal Linux environments do not map .js to a
        # JavaScript MIME type. The fnOS host bridge is loaded as an ES module,
        # which browsers reject when it is served as application/octet-stream.
        if target.lower().endswith(".js"):
            mime_type = "text/javascript"
        self.send_response(200)
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Content-Length", str(os.path.getsize(target) if head_only else len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def serve_cover(self, item_id, query=None, head_only=False):
        item = find_library_item(self.server.config, item_id)
        if not item:
            return self.send_error(404)
        size = normalized_cover_size(((query or {}).get("size") or [0])[0])
        mime, body = (cached_thumbnail_for_item(item, self.server.config, size, cached_cover_for_item)
                      if size else cached_cover_for_item(item, self.server.config))
        if not body:
            return self.send_error(404)
        # URL version, ETag and thumbnail-cache invalidation deliberately use
        # the same source version. This keeps tag/cover writes from serving a
        # stale 304 response after a library index has not caught up yet.
        version = cover_source_version(item)
        etag = '"cover-%s-%s-%s-%s"' % (
            item.get("id", item_id), version, size or "original", hashlib.sha256(body).hexdigest()[:16])
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "public, max-age=2592000, immutable")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", mime or "image/jpeg")
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", "public, max-age=2592000, immutable")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def serve_cover_asset(self, asset_id, query=None, head_only=False):
        size = normalized_cover_size(((query or {}).get("size") or [160])[0]) or 160
        value = thumbnail_asset_bytes(self.server.config, asset_id, size)
        if not value:
            return self.send_error(404)
        mime, body = value
        etag = '"cover-asset-%s-%s"' % (asset_id, size)
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "public, max-age=2592000, immutable")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", mime or "image/jpeg")
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", "public, max-age=2592000, immutable")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def serve_metadata_artwork(self, asset_id, head_only=False):
        asset = METADATA_SERVICE.artwork(asset_id) if METADATA_SERVICE else None
        if not asset:
            return self.send_error(404)
        etag = '"metadata-%s"' % asset_id
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "public, max-age=2592000, immutable")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", asset.get("mime") or "image/jpeg")
        self.send_header("Content-Length", str(asset.get("size") or os.path.getsize(asset["path"])))
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", "public, max-age=2592000, immutable")
        self.end_headers()
        if not head_only:
            try:
                with open(asset["path"], "rb") as fh:
                    shutil.copyfileobj(fh, self.wfile, length=128 * 1024)
            except (OSError, BrokenPipeError, ConnectionResetError):
                pass

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
            size = os.path.getsize(target)
        except OSError:
            return self.send_error(404)
        if size <= 0:
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
            return
        with open(target, "rb") as fh:
            fh.seek(start)
            remaining = end - start + 1
            while remaining:
                chunk = fh.read(min(1024 * 256, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    break
                remaining -= len(chunk)

    def serve_upnp_media(self, item_path, query, head_only=False):
        item_id = item_path.split("/", 1)[0]
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
                timed_out = threading.Event()
                try:
                    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)

                    def stop_timed_out_process():
                        timed_out.set()
                        try:
                            if process.poll() is None:
                                process.terminate()
                        except OSError:
                            pass

                    watchdog = threading.Timer(
                        max(0.1, safe_float(self.server.config.get("ffmpeg_task_timeout_seconds") or 900)),
                        stop_timed_out_process,
                    )
                    watchdog.daemon = True
                    watchdog.start()
                    self.send_response(200)
                    self.send_header("Content-Type", mime)
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-fnAudio-Transcode-Timeout", "%g" % safe_float(self.server.config.get("ffmpeg_task_timeout_seconds") or 900))
                    self.end_headers()
                    while True:
                        chunk = process.stdout.read(1024 * 128)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    if watchdog is not None:
                        watchdog.cancel()
                    if process is not None and process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=2)
        except ResourceLimitError as exc:
            return self.send_error(503, str(exc))
        except OSError as exc:
            return self.send_error(502, "failed to start ffmpeg: %s" % exc)


def public_item(item, config=None):
    result = dict(item)
    result.pop("path", None)
    result["url"] = "media/" + item["id"]
    result["cover_url"] = ("" if cover_is_known_missing(item, config or {}, 160) else
                           "cover/%s?v=%s" % (item["id"], cover_source_version(item)))
    asset_id = thumbnail_asset_id_for_item(item, config or {}, 160)
    result["cover_thumbnail_url"] = ("cover-asset/%s?size=160" % asset_id) if asset_id else ""
    return result


def playback_targets_payload(force_refresh=False):
    mpd = MPD_OUTPUT.status()
    mpd_caps = mpd.get("output_capabilities") or {}
    mpd_devices = mpd_caps.get("devices") or []
    core_state = PLAYBACK_CORE.snapshot()
    current_target = core_state.get("target_id") or "local"
    # The renderer path can retain the generic MPD plugin id. Resolve it to
    # the selected USB output so the target list still has a concrete row to
    # mark as current when the dialog is opened again.
    if current_target == "mpd":
        selected_output = mpd_caps.get("selected_output") or {}
        selected_device_id = str(selected_output.get("stable_id") or selected_output.get("alsa_id") or "").strip()
        if selected_device_id:
            current_target = "mpd:" + urllib.parse.quote(selected_device_id, safe=":,=-_")
    if current_target == "browser":
        current_target = "local"
    current_target_name = ""
    if current_target == "local":
        current_target_name = "当前设备"
    upmpdcli = upmpdcli_probe()
    if force_refresh or time.time() - UPNP_CACHE["stamp"] > 15:
        refresh_upnp_cache_background()
    targets = [
        {
            "id": "local",
            "name": "当前设备",
            "kind": "browser",
            "online": True,
            "selected": current_target == "local",
            "capabilities": PLAYBACK_CORE.registry.get("browser").capabilities(),
        }
    ]
    if mpd_devices:
        for device in mpd_devices:
            alsa_id = str(device.get("alsa_id") or "").strip()
            if not alsa_id or not bool(device.get("is_usb")):
                continue
            name = device.get("name") or alsa_id
            persistent_id = str(device.get("stable_id") or alsa_id).strip()
            target_id = "mpd:" + urllib.parse.quote(persistent_id, safe=":,=-_")
            selected = target_id == current_target
            caps = device.get("caps") or {}
            display_name = "NAS - %s - USB Audio" % name
            targets.append(
                {
                    "id": target_id,
                    "kind": "mpd",
                    "name": display_name,
                    "online": bool(mpd.get("available")),
                    "available": bool(mpd.get("available")),
                    "selected": selected,
                    "message": "当前 USB DAC" if selected else "本机 USB DAC",
                    "caps": caps,
                    "raw_name": device.get("raw_name", ""),
                    "backend": {
                        "mpd": mpd,
                        "upmpdcli": upmpdcli,
                        "alsa_id": alsa_id,
                        "stable_id": device.get("stable_id", ""),
                        "stable_alsa_id": device.get("stable_alsa_id", ""),
                    },
                    "capabilities": PLAYBACK_CORE.registry.get("mpd").capabilities(),
                }
            )
            if selected:
                current_target_name = "USB DAC · " + name
    for device in UPNP_CACHE["items"]:
        selected = device.get("id") == current_target
        targets.append(
            {
                "id": device.get("id"),
                "name": device.get("name") or "DLNA 设备",
                "kind": "dlna_push",
                "online": bool(device.get("online")),
                "selected": selected,
                "capabilities": {
                    **PLAYBACK_CORE.registry.get("dlna_push").capabilities(),
                    **(device.get("capabilities") or {}),
                    "native_dsd": bool(device.get("supports_dsd")),
                },
            }
        )
        if selected:
            current_target_name = device.get("name") or "DLNA 设备"
    # Discovery is asynchronous. Keep the core target untouched while a
    # renderer is temporarily absent, but tell clients when it has no row.
    current_target_available = any(
        str(target.get("id") or "") == str(current_target) for target in targets
    )
    return {
        "targets": targets,
        "current_target": current_target,
        "current_target_name": current_target_name,
        "current_target_available": current_target_available,
        "plugins": PLAYBACK_CORE.registry.describe(),
        "optional_backends": {
            "mpd": mpd,
            "upmpdcli": upmpdcli,
            "airplay": airplay_probe(getattr(getattr(MPD_OUTPUT, "service", None), "config", {}) or {}, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))),
        },
        "refreshing": bool(UPNP_CACHE.get("refreshing")),
    }


def find_library_item(config, item_id):
    item = query_library_item_by_id(config, item_id)
    return item if item and is_library_item_path(config, item.get("path")) else None


def find_upnp_device(device_id):
    devices = UPNP_CACHE["items"] or discover_upnp()
    return next((x for x in devices if x["id"] == device_id), None)


def playback_load(handler, payload):
    target_id = str(payload.get("target_id") or payload.get("device_id") or "local")
    track_id = str(payload.get("track_id") or "")
    item = find_library_item(handler.server.config, track_id)
    if not item:
        return {"error": "track not found"}, 404
    return playback_load_selected(handler, target_id, item, payload.get("position"))


def current_playback_session():
    core = PLAYBACK_CORE.snapshot()
    return {
        "queue": list(core.get("queue") or []),
        "current_id": str(core.get("current") or ""),
        "position": safe_float(core.get("position") or 0),
        "playing": bool(core.get("playing")),
        "repeat": str(core.get("repeat") or "off"),
        "shuffle": bool(core.get("shuffle")),
        "target_id": "local" if core.get("target_id") in ("", "browser") else str(core.get("target_id")),
        "target_kind": str(core.get("target_kind") or "browser"),
    }


def save_current_playback_session(config):
    try:
        return save_playback_session(config, current_playback_session())
    except Exception:
        return None


def restore_playback_session(config, _retry=0):
    retry_delay = (2.0, 5.0, 12.0)
    try:
        playback = (load_user_state(config).get("playback") or {})
        queue_ids = [str(track_id or "").strip() for track_id in playback.get("queue", []) if str(track_id or "").strip()]
        rows = query_library_items_by_ids(config, queue_ids)
        by_id = {str(item.get("id") or ""): item for item in rows}
        queue = [by_id[track_id] for track_id in queue_ids if track_id in by_id]
        current = str(playback.get("current_id") or "")
        PLAYBACK_CORE.set_queue(queue, current, playback.get("repeat"), playback.get("shuffle"))
        target_id = str(playback.get("target_id") or "local")
        target_kind = playback_target_kind(target_id)
        PLAYBACK_CORE.set_target("local" if target_kind == "browser" else target_id, target_kind)
        # Restoring the logical queue is not enough for MPD: its native
        # execution queue is process-local and is empty after an app restart.
        # Mirror the saved queue back into MPD before the UI tries to control
        # the recovered target.  Older sessions have no `playing` field; they
        # are restored paused/stopped after the queue is mirrored.
        if target_kind == "mpd" and queue and MPD_SERVICE:
            tracks = [TrackRef.from_mapping(item) for item in queue]
            restored_position = safe_float(playback.get("position") or 0)
            result = MPD_SERVICE.sync_playback_queue(
                tracks,
                current,
                resolver=lambda track_id: find_library_item(config, track_id),
                current_item=next((item for item in queue if str(item.get("id") or "") == current), None),
                start=restored_position,
                repeat=str(playback.get("repeat") or "off"),
                shuffle=bool(playback.get("shuffle")),
                play=False,
            )
            # Session restore deliberately never resumes audio. The saved
            # playing flag is historical state for the UI, not permission to
            # start an output device when fnAudio starts.
            restore_playing = False
            if not restore_playing:
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
        if _retry < len(retry_delay):
            timer = threading.Timer(
                retry_delay[_retry],
                restore_playback_session,
                args=(config, _retry + 1),
            )
            timer.daemon = True
            timer.start()


def playback_queue(config, payload):
    tracks = normalize_queue_tracks(payload.get("queue"))
    current = payload.get("current_id") or payload.get("current")
    if isinstance(current, dict):
        current = current.get("id")
    repeat = payload.get("repeat")
    shuffle = payload.get("shuffle")
    state = PLAYBACK_CORE.set_queue(tracks, str(current or ""), repeat, shuffle if shuffle is not None else None)
    # Keep MPD's native execution queue aligned with the logical queue even
    # when the UI only edits the queue while playback is stopped.  Replacing
    # the queue with ``play=False`` prevents an edit from unexpectedly
    # starting audio; the next explicit play/load still uses the fast native
    # queue path.
    target_kind = playback_target_kind(PLAYBACK_CORE.state.target_id)
    service = getattr(MPD_OUTPUT, "service", None)
    if target_kind == "mpd" and service and tracks:
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
    return {"ok": True, "core": state.to_dict(), "revision": revision}, 200


def playback_load_selected(handler, target_id, item, position=0):
    target_kind = playback_target_kind(target_id)
    PLAYBACK_CORE.set_target("local" if target_kind == "browser" else target_id, target_kind)
    context = {
        "handler": handler,
        "config": handler.server.config,
        "item": item,
        "position": safe_float(position),
        "resolve_track": lambda track_id: find_library_item(handler.server.config, track_id),
    }
    core_result = PLAYBACK_CORE.dispatch(PlaybackCommand("load", track=TrackRef.from_mapping(item), context=context))
    output_result = core_result.get("result") or {}
    # A direct device load can be initiated by a renderer, Android bridge, or
    # another client without first calling /api/playback/queue.  Persist the
    # authoritative core snapshot here as well, otherwise the next browser
    # refresh can restore an empty/stale queue even though the device is
    # already playing the selected track.
    if core_result.get("ok") and not (isinstance(output_result, dict) and output_result.get("ok") is False):
        save_current_playback_session(handler.server.config)
        if METADATA_SERVICE:
            METADATA_SERVICE.prioritize_track(item["id"])
    if target_kind == "browser":
        return {"ok": True, "kind": target_kind, "target_id": "local", "track_id": item["id"], "core": core_result["state"]}, 200
    ok = bool(output_result.get("ok"))
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
    command_id = str((payload or {}).get("command_id") or "").strip()[:128]
    if not command_id:
        return playback_control(handler, payload)
    now = time.monotonic()
    with PLAYBACK_COMMAND_LOCK:
        expired = [key for key, value in PLAYBACK_COMMAND_RESULTS.items() if value[0] <= now]
        for key in expired:
            PLAYBACK_COMMAND_RESULTS.pop(key, None)
        cached = PLAYBACK_COMMAND_RESULTS.get(command_id)
        if cached:
            response, status = cached[1], cached[2]
            return dict(response), status
        response, status = playback_control(handler, payload)
        response = dict(response)
        response["command_id"] = command_id
        core = response.get("core") or {}
        response["state_version"] = safe_int(core.get("state_version"))
        PLAYBACK_COMMAND_RESULTS[command_id] = (now + PLAYBACK_COMMAND_TTL_SECONDS, dict(response), status)
        return response, status


def playback_control(handler, payload):
    target_id = str(payload.get("target_id") or payload.get("device_id") or "local")
    action = str(payload.get("action") or "").lower()
    position = payload.get("position")
    target_kind = playback_target_kind(target_id)
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
        if METADATA_SERVICE:
            METADATA_SERVICE.prioritize_track(item["id"])
        if target_kind == "browser":
            return {"ok": True, "kind": target_kind, "track_id": item["id"], "core": PLAYBACK_CORE.snapshot(), "revision": revision}, 200
        output_result = result.get("result") or {}
        ok = bool(output_result.get("ok"))
        return {"ok": ok, "kind": target_kind, "track_id": item["id"], "message": output_result.get("message", ""), "core": PLAYBACK_CORE.snapshot(), "revision": revision}, 200 if ok else 502
    if action in ("repeat", "shuffle"):
        context = {}
        if action == "repeat" and payload.get("repeat") in ("off", "all", "one"):
            context["repeat_value"] = payload.get("repeat")
        if action == "shuffle" and isinstance(payload.get("shuffle"), bool):
            context["shuffle_value"] = bool(payload.get("shuffle"))
        result = PLAYBACK_CORE.dispatch(PlaybackCommand(action, context=context))
        revision = save_current_playback_session(handler.server.config)
        return {"ok": True, "kind": target_kind, "result": result, "core": PLAYBACK_CORE.snapshot(), "revision": revision}, 200
    if target_kind == "browser":
        result = PLAYBACK_CORE.dispatch(PlaybackCommand(action, safe_float(position) if position is not None else None))
        revision = save_current_playback_session(handler.server.config)
        return {"ok": True, "kind": target_kind, "result": result, "core": PLAYBACK_CORE.snapshot(), "revision": revision}, 200
    if target_kind in ("alsa", "mpd"):
        item_id = str(payload.get("track_id") or "")
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
        ok = bool(output_result.get("ok"))
        message = output_result.get("message") or ""
        revision = save_current_playback_session(handler.server.config)
        return {"ok": ok, "kind": target_kind, "message": message, "core": PLAYBACK_CORE.snapshot(), "revision": revision}, 200 if ok else 502
    result = PLAYBACK_CORE.dispatch(
        PlaybackCommand(
            action,
            safe_float(position) if position is not None else None,
            context={"handler": handler, "config": handler.server.config},
        )
    )
    output_result = result.get("result") or {}
    ok = bool(output_result.get("ok"))
    message = output_result.get("message") or ""
    revision = save_current_playback_session(handler.server.config)
    return {"ok": ok, "kind": target_kind, "message": message, "core": PLAYBACK_CORE.snapshot(), "revision": revision}, 200 if ok else 502


def playback_status(payload_or_query):
    if hasattr(payload_or_query, "get"):
        raw = payload_or_query.get("target_id") or payload_or_query.get("device_id") or ["local"]
    else:
        raw = "local"
    target_id = raw[0] if isinstance(raw, list) else raw
    target_id = str(target_id or "local")
    target_kind = playback_target_kind(target_id)
    if target_kind == "browser":
        return {"kind": target_kind, "status": PLAYBACK_CORE.snapshot()}, 200
    if target_kind == "alsa":
        return {"kind": target_kind, **dac_public_status(), "core": PLAYBACK_CORE.snapshot()}, 200
    if target_kind == "mpd":
        # The UI polls this endpoint frequently for the progress bar.  Keep
        # it on the lightweight MPD status path so ALSA capability probing and
        # recent-log collection never run in the request thread.
        probe = MPD_OUTPUT.status(light=True)
        if not probe.get("running"):
            return {"kind": target_kind, "error": probe.get("message") or "MPD is not running", "core": PLAYBACK_CORE.snapshot()}, 404
        status = probe.get("status") or {}
        core_snapshot = PLAYBACK_CORE.snapshot()
        current_id = core_snapshot.get("current") or ""
        current_item = find_library_item(getattr(getattr(MPD_OUTPUT, "service", None), "config", {}) or {}, current_id) if current_id else None
        if current_item and current_item.get("cue_track"):
            position = dict(status.get("position") or {})
            whole_seconds = safe_float(position.get("rel_seconds"))
            cue_start = safe_float(current_item.get("cue_start"))
            cue_end = safe_float(current_item.get("cue_end"))
            cue_duration = max(0.0, safe_float(current_item.get("duration")) or (cue_end - cue_start))
            # CUE+APE is rendered as an individual FLAC segment for MPD, so
            # its reported position is already relative to this cue track.
            cue_transcoded = str(current_item.get("path") or "").lower().endswith(".ape")
            rel = max(0.0, whole_seconds if cue_transcoded else whole_seconds - cue_start)
            if cue_duration > 0:
                rel = min(rel, cue_duration)
            position.update({"rel_seconds": rel, "duration_seconds": cue_duration, "cue_start": cue_start, "cue_end": cue_end, "cue_transcoded": cue_transcoded})
            status["position"] = position
            cue_finished = rel >= max(0.0, cue_duration - 0.25) if cue_transcoded else whole_seconds >= max(cue_start, cue_end - 0.25)
            if cue_end > cue_start and cue_finished:
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
                    if result.get("ok") and output_result.get("ok") is not False:
                        probe = MPD_OUTPUT.status()
                        status = probe.get("status") or status
        return {
            "kind": target_kind,
            "transport": status.get("transport") or {"state": "STOPPED"},
            "position": status.get("position") or {"rel_seconds": 0, "duration_seconds": 0},
            "mpd": probe,
            "core": PLAYBACK_CORE.snapshot(),
        }, 200
    device = find_upnp_device(target_id)
    if not device:
        return {"error": "device not found"}, 404
    try:
        return {"kind": target_kind, "transport": upnp_transport_state(device), "position": upnp_position_info(device), "core": PLAYBACK_CORE.snapshot()}, 200
    except Exception as exc:
        return {"error": str(exc)}, 502


def _upnp_track_id_from_uri(uri):
    try:
        path = urllib.parse.urlparse(str(uri or "")).path
        marker = "/upnp/media/"
        if marker not in path:
            return ""
        return urllib.parse.unquote(path.split(marker, 1)[1].split("/", 1)[0])
    except Exception:
        return ""


def _dlna_stop_is_suppressed(target_id, transport, now=None):
    return (
        str(transport or "").upper() in ("STOPPED", "NO_MEDIA_PRESENT")
        and DLNA_MONITOR_GUARD.get("target_id") == str(target_id or "")
        and (time.monotonic() if now is None else float(now))
        <= safe_float(DLNA_MONITOR_GUARD.get("suppress_stop_until"))
    )


def start_remote_output_monitor(server):
    """Keep external Renderer playback alive without a foreground UI.

    fnAudio deliberately owns queue progression for pushed renderers.  After
    a stable PLAYING->STOPPED transition, it loads one next queue item rather
    than relying on the renderer's optional NextURI state machine.
    """
    stop_event = threading.Event()
    monitor = {
        "target": "",
        "transport": "",
        "advance_at": 0.0,
        "track": "",
        "managed_key": "",
        "managed_playing": False,
        "start_pending_at": 0.0,
        "missing_count": 0,
    }
    handler = SimpleNamespace(server=server, headers={})

    def loop():
        while not stop_event.wait(1.25):
            snapshot = PLAYBACK_CORE.state
            if snapshot.target_kind != "dlna_push" or not snapshot.target_id:
                monitor.update({"target": "", "transport": "", "track": "", "managed_key": "", "managed_playing": False, "start_pending_at": 0.0, "missing_count": 0})
                continue
            device = find_upnp_device(snapshot.target_id)
            if not device:
                monitor["missing_count"] = int(monitor.get("missing_count") or 0) + 1
                if monitor["missing_count"] >= 3:
                    PLAYBACK_CORE.sync_output_status("dlna_push", "ERROR", error="DLNA renderer is offline")
                continue
            monitor["missing_count"] = 0
            try:
                transport_payload = upnp_transport_state(device) or {}
                position_payload = upnp_position_info(device) or {}
            except Exception as exc:
                PLAYBACK_CORE.sync_output_status("dlna_push", "ERROR", error=str(exc))
                continue
            transport = str(transport_payload.get("state") or "UNKNOWN").upper()
            previous = monitor.get("transport") if monitor.get("target") == snapshot.target_id else ""
            monitor["target"] = snapshot.target_id
            monitor["transport"] = transport
            managed_key = "%s:%s" % (snapshot.target_id, snapshot.current_track_id)
            if snapshot.playing and (managed_key != monitor.get("managed_key") or not monitor.get("managed_playing")):
                monitor["managed_key"] = managed_key
                monitor["start_pending_at"] = time.monotonic()
            monitor["managed_playing"] = bool(snapshot.playing)
            if transport in ("PLAYING", "TRANSITIONING", "PAUSED_PLAYBACK"):
                monitor["start_pending_at"] = 0.0

            backend_track_id = _upnp_track_id_from_uri(position_payload.get("track_uri"))
            if backend_track_id and backend_track_id != snapshot.current_track_id:
                before = snapshot.current_track_id
                PLAYBACK_CORE.select_current(backend_track_id)
                if PLAYBACK_CORE.state.current_track_id != before:
                    save_current_playback_session(server.config)

            ended = previous in ("PLAYING", "TRANSITIONING") and transport in ("STOPPED", "NO_MEDIA_PRESENT")
            managed_playing = bool(snapshot.playing)
            stop_suppressed = _dlna_stop_is_suppressed(snapshot.target_id, transport)
            if stop_suppressed:
                monitor["start_pending_at"] = 0.0
                monitor["managed_playing"] = False
                PLAYBACK_CORE.sync_output_status(
                    "dlna_push",
                    "STOPPED",
                    safe_float(position_payload.get("rel_seconds")),
                    safe_float(position_payload.get("duration_seconds")),
                )
                continue
            if ended and managed_playing:
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

            if transport in ("STOPPED", "NO_MEDIA_PRESENT") and managed_playing:
                pending_at = safe_float(monitor.get("start_pending_at"))
                if pending_at and time.monotonic() - pending_at < 4.0:
                    # A Renderer may acknowledge Play before it exposes the
                    # new transport state. Preserve the optimistic command
                    # state briefly, then surface a real rejection instead
                    # of silently pretending playback succeeded.
                    continue
                PLAYBACK_CORE.sync_output_status(
                    "dlna_push",
                    "ERROR",
                    safe_float(position_payload.get("rel_seconds")),
                    safe_float(position_payload.get("duration_seconds")),
                    "Renderer accepted Play but did not enter PLAYING; source format may be unsupported",
                )
                continue

            PLAYBACK_CORE.sync_output_status(
                "dlna_push",
                transport,
                safe_float(position_payload.get("rel_seconds")),
                safe_float(position_payload.get("duration_seconds")),
            )

    thread = threading.Thread(target=loop, name="fnaudio-renderer-monitor", daemon=True)
    thread.start()
    return stop_event


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
            return mpd_load_uri(uri, host=MPD_SERVICE.host, port=MPD_SERVICE.port, start=start)
        except Exception as exc:
            return {"ok": False, "message": "DLNA renderer playback failed: %s" % exc}

    def renderer_control(action, position=None):
        try:
            if action == "volume" and MPD_SERVICE:
                mixer = MPD_SERVICE.mixer_policy()
                if not mixer.get("available"):
                    return {"ok": False, "message": mixer.get("message") or "renderer volume control is unavailable"}
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

    def groups(view):
        return query_library_groups(server.config, view) or []

    def roots():
        return query_library_root_folders(server.config) or []

    def folders(parent, root):
        return query_library_folders(server.config, parent, root) or []

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
    DLNA_SSDP.start()


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
                safe_float(position.get("rel_seconds")),
                safe_float(position.get("duration_seconds")),
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
                safe_float(position.get("rel_seconds")),
                safe_float(position.get("duration_seconds")),
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
    config.setdefault("cache_dir", os.path.join(os.path.dirname(os.path.abspath(args.config)), "transcode"))
    cleanup_transcode_cache_if_due(config, True)
    load_library_cache(config)
    # Existing indexes may predate thumbnail assets. Warm them after startup
    # as well as after future scans, without delaying the HTTP listener.
    warm_items = MUSIC_CACHE["items"] or (load_items_from_sqlite(config) or {}).get("items", [])
    prewarm_library_thumbnails(warm_items, config, cached_cover_for_item)
    METADATA_SERVICE = MetadataService(config)
    METADATA_SERVICE.start()
    restore_playback_session(config)
    web_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui"))
    save_proxy_port(web_root, args.port)
    try:
        server = ThreadingHTTPServer((args.host, args.port), Handler)
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
    threading.Thread(target=watch_library, args=(config,), daemon=True).start()
    print("fnAudio listening on %s:%s, library=%s" % (args.host, args.port, config["library_path"]), flush=True)
    try:
        server.serve_forever()
    finally:
        shutdown_library_thumbnail_prewarm(wait=True)
        if DLNA_SSDP:
            DLNA_SSDP.stop()
        if MPD_SERVICE:
            MPD_SERVICE.shutdown()
        if AIRPLAY_SERVICE:
            AIRPLAY_SERVICE.shutdown()
        if METADATA_SERVICE:
            METADATA_SERVICE.shutdown()


if __name__ == "__main__":
    main()

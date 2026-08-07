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
import traceback
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from xml.etree import ElementTree as ET

from config import load_config, save_config, save_proxy_port, save_manifest_port
from fnos_api import FnosApiError, del_shared_accessible_folder, get_shared_accessible_folders
from library import (
    FS_CACHE,
    MUSIC_CACHE,
    SCAN_LOCK,
    SCAN_STATE,
    library_items,
    library_status,
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
from state_store import StateConflict, load_user_state, save_playback_session, save_user_state
from metadata_service import MetadataService

ALLOWED_LIBRARY_PREFIXES = ("/vol", "/volume", "/mnt", "/share", "/var/apps/fnaudio/share")
STATE = {"queue": [], "current": None, "playing": False}
PLAYBACK_CORE = PlaybackCore()
MPD_OUTPUT = MpdOutput()
MPD_SERVICE = None
DLNA_PROTOCOL = None
DLNA_SSDP = None
METADATA_SERVICE = None
DLNA_DIAGNOSTICS = DlnaDiagnostics()
CUE_AUTO_ADVANCE = {"track_id": "", "at": 0.0}
TRANSPARENT_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lR4YJwAAAABJRU5ErkJggg=="
)








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


def is_allowed_library_path(path):
    if os.name == "nt":
        return True
    root = os.path.abspath(os.path.expanduser(path or ""))
    if re.match(r"^/vol\d+(/|$)", root):
        return True
    return any(root == prefix or root.startswith(prefix + os.sep) for prefix in ALLOWED_LIBRARY_PREFIXES)


def normalize_library_paths(config):
    values = []
    raw_paths = config.get("library_paths")
    if isinstance(raw_paths, list):
        values.extend(raw_paths)
    raw = config.get("library_path", "")
    if isinstance(raw, str):
        values.extend(re.split(r"[\r\n;]+", raw))
    paths = []
    seen = set()
    for value in values:
        raw_value = str(value or "").strip()
        if not raw_value:
            continue
        path = os.path.abspath(os.path.expanduser(raw_value))
        if path in seen:
            continue
        seen.add(path)
        paths.append(path)
    return paths or [os.path.abspath(os.path.expanduser(config.get("library_path", ".")))]


def merge_library_paths(current_paths, extra_paths):
    paths = []
    seen = set()
    for value in list(current_paths or []) + list(extra_paths or []):
        raw = str(value or "").strip()
        if not raw:
            continue
        path = os.path.abspath(os.path.expanduser(raw))
        if path in seen:
            continue
        seen.add(path)
        paths.append(path)
    return paths


def apply_library_paths(config, paths):
    config["library_path"] = "\n".join(paths)
    config["library_paths"] = paths








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
    warm_transcode_cache,
)


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
    ok, message = upnp_control(device, command.action, command.position)
    return {"ok": ok, "message": message, "target_id": state.target_id}


def dlna_output_close(state):
    device = find_upnp_device(state.target_id)
    if not device:
        return
    try:
        upnp_control(device, "stop", None)
    except Exception:
        pass


def alsa_output_open(track, state, context):
    config = context.get("config") or {}
    item = context.get("item") or track.item
    ok, message = start_dac_playback(state.target_id, item, config, safe_float(context.get("position")))
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
    server_version = "fnAudio/0.1.14"

    def log_message(self, fmt, *args):
        return

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
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
            return None

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
        if path == "/api/health":
            return self.send_json({"ok": True, "name": self.server.config["server_name"], "fnos_api_token": bool(os.environ.get("TRIM_API_TOKEN"))})
        if path == "/api/access":
            return self.send_json(public_access(self))
        if path == "/api/state/user":
            return self.send_json({"ok": True, "state": load_user_state(self.server.config)})
        if path == "/api/library":
            if query.get("paged") == ["1"]:
                if query.get("refresh") == ["1"]:
                    library_items(self.server.config, True)
                page = query_library_page(self.server.config, query)
                page["items"] = [public_item(x) for x in page.get("items", [])]
                return self.send_json(page)
            compat_query = dict(query)
            compat_query.setdefault("paged", ["1"])
            compat_query.setdefault("limit", ["120"])
            compat_query.setdefault("offset", ["0"])
            page = query_library_page(self.server.config, compat_query)
            page["items"] = [public_item(x) for x in page.get("items", [])]
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
            return self.send_json({"items": [public_item(x) for x in query_library_items_by_ids(self.server.config, ids)]})
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
        if path.startswith("/metadata/artwork/"):
            asset_id = path.rsplit("/", 1)[-1]
            return self.serve_metadata_artwork(asset_id, head_only)
        if path == "/api/fnos/shared-folders":
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
            return self.serve_cover(path.split("/", 2)[2], head_only)
        if path.startswith("/upnp/media/"):
            return self.serve_upnp_media(path[len("/upnp/media/"):], query, head_only)
        if path.startswith("/media/"):
            return self.serve_media(path.split("/", 2)[2], query, head_only)
        return self.serve_static(path, head_only)

    def do_POST(self):
        try:
            return self.handle_post()
        except Exception as exc:
            try:
                with open("/var/log/apps/fnaudio.log", "a", encoding="utf-8") as fh:
                    fh.write("\n[fnAudio] POST %s failed: %s\n%s\n" % (self.path, exc, traceback.format_exc()))
            except Exception:
                pass
            message = str(exc) or "playback request failed"
            return self.send_json({"ok": False, "message": message, "error": message}, 500)

    def do_SUBSCRIBE(self):
        return self.handle_dlna_subscription(False)

    def do_UNSUBSCRIBE(self):
        return self.handle_dlna_subscription(True)

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
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        if parsed.path.startswith("/dlna/"):
            return self.handle_dlna_post(parsed.path, raw)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except ValueError:
            return self.send_json({"error": "invalid json"}, 400)
        if parsed.path == "/api/player/state":
            STATE.update(
                {
                    "queue": payload.get("queue", STATE["queue"]),
                    "current": payload.get("current", STATE["current"]),
                    "playing": payload.get("playing", STATE["playing"]),
                }
            )
            core_state = PLAYBACK_CORE.sync_frontend(payload)
            return self.send_json({"ok": True, "state": STATE, "core": core_state.to_dict()})
        if parsed.path == "/api/state/user":
            if not isinstance(payload, dict):
                return self.send_json({"ok": False, "error": "invalid state payload"}, 400)
            try:
                revision = payload.get("revision")
                expected_revision = int(revision) if revision is not None else None
                return self.send_json({"ok": True, "state": save_user_state(self.server.config, payload, expected_revision)})
            except StateConflict:
                return self.send_json({"ok": False, "error": "state conflict", "state": load_user_state(self.server.config)}, 409)
        if parsed.path == "/api/playback/load":
            response, status = playback_load(self, payload)
            return self.send_json(response, status)
        if parsed.path == "/api/playback/target":
            target_id = str(payload.get("target_id") or "local")
            target_kind = playback_target_kind(target_id)
            normalized = "local" if target_kind == "browser" else target_id
            PLAYBACK_CORE.set_target(normalized, target_kind)
            revision = save_current_playback_session(self.server.config)
            return self.send_json({
                "ok": True,
                "target_id": normalized,
                "target_kind": target_kind,
                "core": PLAYBACK_CORE.snapshot(),
                "revision": revision,
            })
        if parsed.path == "/api/playback/queue":
            response, status = playback_queue(self.server.config, payload)
            return self.send_json(response, status)
        if parsed.path == "/api/playback/control":
            response, status = playback_control(self, payload)
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
            response, status = playback_load(
                self,
                {
                    "target_id": payload.get("device_id"),
                    "track_id": payload.get("track_id"),
                    "position": payload.get("position", 0),
                },
            )
            return self.send_json(response, status)
        if parsed.path == "/api/dac/push":
            response, status = playback_load(
                self,
                {
                    "target_id": payload.get("device_id"),
                    "track_id": payload.get("track_id"),
                    "position": payload.get("position", 0),
                },
            )
            return self.send_json(response, status)
        if parsed.path == "/api/upnp/control":
            response, status = playback_control(
                self,
                {
                    "target_id": payload.get("device_id"),
                    "action": payload.get("action"),
                    "position": payload.get("position"),
                    "track_id": payload.get("track_id"),
                },
            )
            return self.send_json(response, status)
        if parsed.path == "/api/dac/control":
            dac_target_id = payload.get("device_id")
            if not dac_target_id:
                with DAC_LOCK:
                    dac_target_id = DAC_STATE.get("device_id")
            response, status = playback_control(
                self,
                {
                    "target_id": dac_target_id,
                    "action": payload.get("action"),
                    "position": payload.get("position"),
                    "track_id": payload.get("track_id"),
                },
            )
            return self.send_json(response, status)
        if parsed.path == "/api/fnos/shared-folders/sync":
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
        if parsed.path == "/api/fnos/shared-folders/delete":
            path_to_delete = os.path.abspath(os.path.expanduser(str(payload.get("path", "")).strip()))
            if not path_to_delete:
                return self.send_json({"ok": False, "message": "缺少要删除的授权目录"}, 400)
            try:
                del_shared_accessible_folder(path_to_delete, self.trim_api_token())
            except FnosApiError as exc:
                return self.send_json({"ok": False, "message": str(exc)}, 400)
            except Exception as exc:
                return self.send_json({"ok": False, "message": "删除飞牛授权目录失败：%s" % exc}, 500)
            remaining_paths = [path for path in normalize_library_paths(self.server.config) if path != path_to_delete]
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
            if payload.get("clear_spotify"):
                self.server.config["spotify_client_id"] = ""
                self.server.config["spotify_client_secret"] = ""
            else:
                if "spotify_client_id" in payload:
                    self.server.config["spotify_client_id"] = str(payload.get("spotify_client_id") or "").strip()
                secret = str(payload.get("spotify_client_secret") or "").strip()
                if secret:
                    self.server.config["spotify_client_secret"] = secret
            if not save_config(self.server.config_path, self.server.config):
                return self.send_json({"ok": False, "message": "保存元数据设置失败"}, 500)
            if METADATA_SERVICE:
                METADATA_SERVICE.providers.spotify_token = ""
                METADATA_SERVICE.providers.spotify_token_expires = 0
                METADATA_SERVICE.wake(force=bool(payload.get("refresh")))
            return self.send_json({"ok": True, "status": METADATA_SERVICE.status() if METADATA_SERVICE else {}})
        if parsed.path == "/api/metadata/refresh":
            if not METADATA_SERVICE:
                return self.send_json({"ok": False, "message": "后台元数据服务没有启动"}, 503)
            METADATA_SERVICE.wake(force=True)
            return self.send_json({"ok": True, "message": "已加入后台补全队列"})
        if parsed.path == "/api/config/library":
            raw_library_path = str(payload.get("library_path", ""))
            candidate_paths = [os.path.abspath(os.path.expanduser(x.strip())) for x in re.split(r"[\r\n;]+", raw_library_path) if x.strip()]
            if not candidate_paths:
                return self.send_json({"ok": False, "message": "请输入音乐目录"}, 400)
            bad_path = next((x for x in candidate_paths if not is_allowed_library_path(x) or not os.path.isdir(x)), "")
            if bad_path:
                return self.send_json({"ok": False, "message": "这个目录不能作为音乐目录：%s" % bad_path}, 400)
            try:
                server_port = int(payload.get("server_port", self.server.config.get("server_port", 18080)))
            except (TypeError, ValueError):
                return self.send_json({"ok": False, "message": "TCP port must be a number"}, 400)
            if not 1024 <= server_port <= 65535:
                return self.send_json({"ok": False, "message": "TCP 端口必须在 1024-65535 之间"}, 400)
            if not is_tcp_port_available(server_port, self.server.server_address[1]):
                return self.send_json({"ok": False, "message": "TCP 端口 %s 已被占用，请换一个端口" % server_port}, 409)
            apply_library_paths(self.server.config, candidate_paths)
            self.server.config["server_port"] = server_port
            if not save_config(self.server.config_path, self.server.config):
                return self.send_json({"ok": False, "message": "保存设置失败"}, 500)
            if not save_proxy_port(self.server.web_root, server_port):
                return self.send_json({"ok": False, "message": "Unable to update the application proxy port"}, 500)
            manifest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "manifest")
            if os.path.isfile(manifest_path):
                save_manifest_port(os.path.abspath(manifest_path), server_port)
            return self.send_json({"ok": True, "restart_required": server_port != self.server.server_address[1], "status": library_status(self.server.config)})
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
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(os.path.getsize(target) if head_only else len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def serve_cover(self, item_id, head_only=False):
        item = find_library_item(self.server.config, item_id)
        if not item:
            return self.send_error(404)
        mime, body = read_cover_for_item(item, self.server.config)
        if not body:
            return self.send_error(404)
        etag = '"%s-%s"' % (item.get("id", item_id), safe_int(item.get("modified_ns") or item.get("modified")))
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", mime or "image/jpeg")
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", "public, max-age=86400")
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
            if mode == "cue_flac":
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

    def serve_file_range(self, target, mime, head_only=False):
        try:
            size = os.path.getsize(target)
        except OSError:
            return self.send_error(404)
        if size <= 0:
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", "0")
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            return
        range_header = self.headers.get("Range")
        start, end = 0, size - 1
        if range_header and range_header.startswith("bytes="):
            spec = range_header[6:].split(",", 1)[0]
            left, _, right = spec.partition("-")
            try:
                if left:
                    start = int(left)
                elif right:
                    suffix = int(right)
                    if suffix <= 0:
                        return self.send_error(416)
                    start = max(0, size - suffix)
                if left and right:
                    end = int(right)
                end = min(end, size - 1)
            except (TypeError, ValueError):
                return self.send_error(416)
            if start < 0 or start >= size or start > end:
                return self.send_error(416)
            self.send_response(206)
            self.send_header("Content-Range", "bytes %s-%s/%s" % (start, end, size))
        else:
            self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
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
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def serve_upnp_media(self, item_path, query, head_only=False):
        item_id = item_path.split("/", 1)[0]
        item = find_library_item(self.server.config, item_id)
        if not item or not os.path.isfile(item["path"]):
            self.record_dlna("media_missing", item_id=item_id)
            return self.send_error(404)
        mode = media_mode(item, query, self)
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
        elif item.get("cue_track"):
            try:
                target, mime = transcode_to_audio(item, self.server.config, "cue_flac")
            except RuntimeError as exc:
                return self.send_error(501, str(exc))
        else:
            target = item["path"]
            mime = upnp_resource_mime(item)
        try:
            size = os.path.getsize(target)
        except OSError:
            return self.send_error(404)
        if size <= 0:
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", "0")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("transferMode.dlna.org", "Streaming")
            self.end_headers()
            return
        range_header = self.headers.get("Range")
        start, end = 0, size - 1
        if range_header and range_header.startswith("bytes="):
            spec = range_header[6:].split(",", 1)[0]
            left, _, right = spec.partition("-")
            try:
                if left:
                    start = int(left)
                elif right:
                    suffix = int(right)
                    if suffix <= 0:
                        return self.send_error(416)
                    start = max(0, size - suffix)
                if left and right:
                    end = int(right)
                end = min(end, size - 1)
            except (TypeError, ValueError):
                return self.send_error(416)
            if start < 0 or start >= size or start > end:
                return self.send_error(416)
            self.send_response(206)
            self.send_header("Content-Range", "bytes %s-%s/%s" % (start, end, size))
        else:
            self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
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

    def serve_transcoded_media(self, item, mode, query=None):
        try:
            start = safe_float((query or {}).get("start", ["0"])[0])
            command, mime, env = transcode_command(item, self.server.config, mode, start)
        except RuntimeError as exc:
            return self.send_error(501, str(exc))
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        try:
            while True:
                chunk = process.stdout.read(1024 * 128)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            if process.poll() is None:
                process.terminate()


def public_item(item):
    result = dict(item)
    result.pop("path", None)
    result["url"] = "media/" + item["id"]
    result["cover_url"] = "cover/%s?v=%s" % (item["id"], safe_int(item.get("modified_ns") or item.get("modified")))
    return result


def playback_target_kind(target_id):
    target_id = str(target_id or "local")
    if target_id in ("", "local", "browser"):
        return "browser"
    if target_id.startswith("mpd:"):
        return "mpd"
    if target_id.startswith("dac:"):
        return "alsa"
    return "dlna_push"


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
        selected_alsa_id = str(selected_output.get("alsa_id") or "").strip()
        if selected_alsa_id:
            current_target = "mpd:" + urllib.parse.quote(selected_alsa_id, safe=":,")
    if current_target == "browser":
        current_target = "local"
    current_target_name = ""
    if current_target == "local":
        current_target_name = "本机播放"
    upmpdcli = upmpdcli_probe()
    if force_refresh or time.time() - UPNP_CACHE["stamp"] > 15:
        refresh_upnp_cache_background()
    targets = [
        {
            "id": "local",
            "name": "本机播放",
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
            target_id = "mpd:" + urllib.parse.quote(alsa_id, safe=":,")
            selected = target_id == current_target
            caps = device.get("caps") or {}
            display_name = "NAS - %s - USB Audio" % name
            targets.append(
                {
                    "id": target_id,
                    "name": "USB DAC · " + name,
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
                "capabilities": PLAYBACK_CORE.registry.get("dlna_push").capabilities(),
            }
        )
        if selected:
            current_target_name = device.get("name") or "DLNA 设备"
    return {
        "targets": targets,
        "current_target": current_target,
        "current_target_name": current_target_name,
        "plugins": PLAYBACK_CORE.registry.describe(),
        "optional_backends": {
            "mpd": mpd,
            "upmpdcli": upmpdcli,
        },
        "refreshing": bool(UPNP_CACHE.get("refreshing")),
    }


def find_library_item(config, item_id):
    return query_library_item_by_id(config, item_id)


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


def restore_playback_session(config):
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
    except Exception as exc:
        print("fnAudio playback-session restore skipped: %s" % exc, flush=True)


def playback_queue(config, payload):
    source = payload.get("queue") if isinstance(payload.get("queue"), list) else []
    tracks = []
    for item in source:
        if isinstance(item, dict):
            track_id = str(item.get("id") or item.get("track_id") or "").strip()
            if track_id:
                tracks.append(item)
            continue
        track_id = str(item or "").strip()
        if track_id:
            tracks.append({"id": track_id})
    current = payload.get("current_id") or payload.get("current")
    if isinstance(current, dict):
        current = current.get("id")
    repeat = payload.get("repeat")
    shuffle = payload.get("shuffle")
    state = PLAYBACK_CORE.set_queue(tracks, str(current or ""), repeat, shuffle if shuffle is not None else None)
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
    }
    core_result = PLAYBACK_CORE.dispatch(PlaybackCommand("load", track=TrackRef.from_mapping(item), context=context))
    output_result = core_result.get("result") or {}
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
        if target_kind == "browser":
            return {"ok": True, "kind": target_kind, "track_id": item["id"], "core": PLAYBACK_CORE.snapshot()}, 200
        output_result = result.get("result") or {}
        ok = bool(output_result.get("ok"))
        return {"ok": ok, "kind": target_kind, "track_id": item["id"], "message": output_result.get("message", ""), "core": PLAYBACK_CORE.snapshot()}, 200 if ok else 502
    if action in ("repeat", "shuffle"):
        result = PLAYBACK_CORE.dispatch(PlaybackCommand(action))
        return {"ok": True, "kind": target_kind, "result": result, "core": PLAYBACK_CORE.snapshot()}, 200
    if target_kind == "browser":
        result = PLAYBACK_CORE.dispatch(PlaybackCommand(action, safe_float(position) if position is not None else None))
        return {"ok": True, "kind": target_kind, "result": result, "core": PLAYBACK_CORE.snapshot()}, 200
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
        return {"ok": ok, "kind": target_kind, "message": message, "core": PLAYBACK_CORE.snapshot()}, 200 if ok else 502
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
    return {"ok": ok, "kind": target_kind, "message": message, "core": PLAYBACK_CORE.snapshot()}, 200 if ok else 502


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
        probe = MPD_OUTPUT.status()
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
            rel = max(0.0, whole_seconds - cue_start)
            if cue_duration > 0:
                rel = min(rel, cue_duration)
            position.update({"rel_seconds": rel, "duration_seconds": cue_duration, "cue_start": cue_start, "cue_end": cue_end})
            status["position"] = position
            if cue_end > cue_start and whole_seconds >= max(cue_start, cue_end - 0.25):
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
    DLNA_PROTOCOL = DlnaProtocolService(base_url, renderer, page, groups, upnp_resource_mime, roots, folders, output_capabilities)
    DLNA_SSDP = SsdpService(base_url)
    DLNA_SSDP.start()


def main():
    global MPD_SERVICE, DLNA_SSDP, METADATA_SERVICE
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()
    config = load_config(args.config)
    MPD_SERVICE = MpdService(config, app_root=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    MPD_OUTPUT.configure(MPD_SERVICE)
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
    if not MUSIC_CACHE["stamp"]:
        request_library_refresh(config, False)
    threading.Thread(target=watch_library, args=(config,), daemon=True).start()
    print("fnAudio listening on %s:%s, library=%s" % (args.host, args.port, config["library_path"]), flush=True)
    try:
        server.serve_forever()
    finally:
        if DLNA_SSDP:
            DLNA_SSDP.stop()
        if MPD_SERVICE:
            MPD_SERVICE.shutdown()
        if METADATA_SERVICE:
            METADATA_SERVICE.shutdown()


if __name__ == "__main__":
    main()

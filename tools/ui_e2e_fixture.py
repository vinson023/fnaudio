#!/usr/bin/env python3
"""Serve the real fnAudio UI against deterministic browser-E2E API fixtures."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import urllib.parse


TRACKS = [
    {
        "id": "fixture-1",
        "title": "晨光",
        "artist": "测试歌手",
        "album": "离线专辑",
        "track_no": 1,
        "duration": 185,
        "format": "flac",
        "mime": "audio/flac",
        "is_dsd": False,
        "modified": 1,
        "cover_url": "",
        "url": "media/fixture-1",
    },
    {
        "id": "fixture-2",
        "title": "DSD Reference",
        "artist": "Lab Artist",
        "album": "Native DSD",
        "track_no": 2,
        "duration": 242,
        "format": "dsf",
        "mime": "audio/x-dsf",
        "is_dsd": True,
        "modified": 2,
        "cover_url": "",
        "url": "media/fixture-2",
    },
    {
        "id": "fixture-3",
        "title": "No Artwork",
        "artist": "Unknown",
        "album": "Fixture",
        "track_no": 3,
        "duration": 98,
        "format": "mp3",
        "mime": "audio/mpeg",
        "is_dsd": False,
        "modified": 3,
        "cover_url": "",
        "url": "media/fixture-3",
    },
]


def playback_core():
    return {
        "queue": [],
        "current": "",
        "target_id": "local",
        "target_kind": "browser",
        "transport": "STOPPED",
        "playing": False,
        "position": 0,
        "duration": 0,
        "repeat": "off",
        "shuffle": False,
        "state_version": 1,
    }


class FixtureHandler(BaseHTTPRequestHandler):
    server_version = "fnAudio-E2E"

    def log_message(self, _format, *_args):
        return

    def send_json(self, payload, status=200, head_only=False):
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def do_HEAD(self):
        self.handle_get(True)

    def do_GET(self):
        self.handle_get(False)

    def handle_get(self, head_only=False):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        if path == "/api/access":
            return self.send_json({"profile": "lan", "ok": True}, head_only=head_only)
        if path == "/api/state/user":
            return self.send_json({"ok": True, "state": {"initialized": False, "revision": 0}}, head_only=head_only)
        if path == "/api/library":
            search = str((query.get("search") or [""])[0]).casefold()
            rows = [item for item in TRACKS if not search or search in " ".join(str(item.get(key) or "") for key in ("title", "artist", "album")).casefold()]
            view = str((query.get("view") or ["all"])[0])
            group = str((query.get("group") or [""])[0])
            if group and view in ("albums", "artists", "composers", "genres"):
                key = {"albums": "album", "artists": "artist", "composers": "composer", "genres": "genre"}[view]
                rows = [item for item in rows if str(item.get(key) or "未分类") == group]
            offset = max(0, int((query.get("offset") or [0])[0]))
            limit = max(1, min(500, int((query.get("limit") or [120])[0])))
            return self.send_json({"items": rows[offset:offset + limit], "count": len(rows), "limit": limit, "offset": offset}, head_only=head_only)
        if path == "/api/library/items":
            wanted = {value for value in str((query.get("ids") or [""])[0]).split(",") if value}
            return self.send_json({"items": [item for item in TRACKS if item["id"] in wanted]}, head_only=head_only)
        if path == "/api/library/status":
            return self.send_json({"scanning": False, "found": len(TRACKS), "scanned": len(TRACKS), "message": "音乐库已就绪"}, head_only=head_only)
        if path == "/api/library/groups":
            view = str((query.get("view") or ["albums"])[0])
            key = {"artists": "artist", "albums": "album", "genres": "genre", "composers": "composer"}.get(view, "album")
            names = sorted({str(item.get(key) or "未分类") for item in TRACKS})
            return self.send_json({"groups": [{"name": name, "count": sum(1 for item in TRACKS if str(item.get(key) or "未分类") == name)} for name in names], "count": len(names)}, head_only=head_only)
        if path == "/api/library/roots":
            return self.send_json({"roots": [{"root": "/fixture/music", "path": "/fixture/music", "name": "测试音乐"}]}, head_only=head_only)
        if path == "/api/library/folders":
            return self.send_json({"folders": [], "count": 0}, head_only=head_only)
        if path == "/api/playback/targets":
            return self.send_json({"targets": [{"id": "local", "name": "当前设备", "kind": "browser", "online": True, "selected": True}], "current_target": "local", "current_target_name": "当前设备"}, head_only=head_only)
        if path in ("/api/playback/core", "/api/playback/status"):
            core = playback_core()
            return self.send_json({"state": core, "status": core, "core": core, "kind": "browser"}, head_only=head_only)
        if path == "/api/dlna/renderer/status":
            return self.send_json({"available": False, "state": {}}, head_only=head_only)
        if path == "/api/metadata/status":
            return self.send_json({"ok": True, "running": True, "pending": 0}, head_only=head_only)
        if path == "/api/config/library":
            return self.send_json({"library_paths": ["/fixture/music"], "server_port": 18080}, head_only=head_only)
        if path == "/api/fnos/shared-folders":
            return self.send_json({"ok": True, "paths": ["/fixture/music"]}, head_only=head_only)
        if path == "/api/dlna/diagnostics":
            return self.send_json({"available": True, "events": []}, head_only=head_only)
        if path == "/api/lyrics":
            return self.send_json({"lyrics": "[00:00.00]E2E lyric", "source": "fixture", "pending": False}, head_only=head_only)
        if path == "/api/transcode/status":
            return self.send_json({"ready": False, "mode": "mp3", "mime": "audio/mpeg"}, head_only=head_only)
        if path.startswith("/api/"):
            return self.send_json({"ok": True}, head_only=head_only)
        return self.serve_static(path, head_only)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            payload = {}
        core = playback_core()
        if self.path.startswith("/api/playback/queue"):
            core["queue"] = [str(item.get("id") if isinstance(item, dict) else item) for item in payload.get("queue", [])]
            core["current"] = str(payload.get("current_id") or payload.get("current") or "")
        return self.send_json({"ok": True, "core": core, "state": {"initialized": True, "revision": 1}})

    def serve_static(self, path, head_only=False):
        relative = urllib.parse.unquote(path).lstrip("/") or "index.html"
        target = (self.server.ui_root / relative).resolve()
        try:
            target.relative_to(self.server.ui_root)
        except ValueError:
            self.send_error(403)
            return
        if not target.is_file():
            self.send_error(404)
            return
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(str(target))[0] or "application/octet-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--ui-root", default=str(Path(__file__).resolve().parents[1] / "src" / "app" / "ui"))
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), FixtureHandler)
    server.ui_root = Path(args.ui_root).resolve()
    print("http://%s:%s/" % (args.host, server.server_port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

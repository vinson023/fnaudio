"""Local stand-in for the fnOS gateway, used only to exercise the TV client.

The television client authenticates through the fnOS WebSocket (`user.login`)
and then reads the library from the CGI prefix. Neither of those is reachable
from this machine without fnOS credentials, so this script answers both with
synthetic data: a JSON handshake that returns a session token, a library of
generated albums, and generated cover art.

It is a development harness, not part of the product and not shipped. Run it,
then point the TV client at 127.0.0.1 with `adb reverse` in front of it.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import struct
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from PIL import Image, ImageDraw

PREFIX = "/cgi/ThirdParty/fnaudio/index.cgi"
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
TOKEN = "mock-session-token"

ARTISTS = [
    ("余温乐队", ["夜行列车", "海边的信号"]),
    ("林深", ["山谷回声"]),
    ("Nova Drift", ["Orbital", "Slow Light"]),
    ("陈默", ["无声之地"]),
]

COUNT_PER_ALBUM = 4
COVER_CACHE: dict[str, bytes] = {}

# Genre and composer labels exist so the television's genre/composer pages have
# rows to draw. The real library derives them from tags.
GENRES = ("电子", "民谣", "爵士")
COMPOSERS = ("高远", "苏黎")

# Lyrics for the television page: long enough that the highlight has to scroll
# (24 lines at 6s intervals), and timed so the active line moves during a test.
LYRIC_LINES = (
    "灯光落下来 房间只剩呼吸",
    "把音量调低 让夜色更清晰",
    "街角的风 从窗缝里经过",
    "像一段旧旋律 迟迟不肯停",
    "你说过的话 我还记得",
    "隔着这么多年 依旧温热",
    "列车向北 掠过无名小站",
    "每一盏灯 都在替谁说晚安",
    "如果时间可以慢一点",
    "让我把这一句唱完",
    "吉他弦上 余音在打转",
    "而你已经走得那么远",
)


def lyric_document(track_id: str) -> str:
    """Deterministic LRC body so the same track always draws the same page."""
    title = next((row["title"] for row in TRACKS if row["id"] == track_id), "")
    rows = ["[ti:%s]" % title, "[ar:tv-mock]"]
    for index in range(24):
        seconds = index * 6
        rows.append("[%02d:%02d.00]%s" % (seconds // 60, seconds % 60,
                                          LYRIC_LINES[index % len(LYRIC_LINES)]))
    return "\n".join(rows)


def build_library():
    tracks = []
    albums = []
    seq = 0
    for artist, album_names in ARTISTS:
        for album in album_names:
            first_id = None
            for number in range(1, COUNT_PER_ALBUM + 1):
                seq += 1
                track_id = "t%03d" % seq
                if first_id is None:
                    first_id = track_id
                tracks.append({
                    "id": track_id,
                    "title": "%s · 第 %d 首" % (album, number),
                    "artist": artist,
                    "album": album,
                    "duration": 180 + number * 17,
                    # Every fifth row is DSD so the television's DSD page is not
                    # permanently empty, which is what a hand check would
                    # otherwise read as a broken query.
                    "format": "DSD64" if seq % 5 == 0 else "FLAC",
                    "genre": GENRES[seq % len(GENRES)],
                    "composer": COMPOSERS[(seq // COUNT_PER_ALBUM) % len(COMPOSERS)],
                    "track_no": number,
                    "cover_url": "cover/" + track_id,
                })
            albums.append({
                "name": album,
                "artist": artist,
                "track_count": COUNT_PER_ALBUM,
                "cover_track_id": first_id,
            })
    artists = [{"name": artist, "track_count": sum(
        COUNT_PER_ALBUM for _ in names), "cover_track_id": ""}
        for artist, names in ARTISTS]
    return tracks, albums, artists


TRACKS, ALBUMS, ARTISTS_ROWS = build_library()


def creator_rows(field: str):
    """Group tracks by one label column, mirroring the server's group shape."""
    grouped: dict[str, list] = {}
    for row in TRACKS:
        label = row[field]
        grouped.setdefault(label, []).append(row)
    return [{"name": label,
             "track_count": len(rows),
             "cover_track_id": rows[0]["id"]}
            for label, rows in grouped.items()]


def cover_png(track_id: str) -> bytes:
    """Deterministic gradient per track so shelves visibly differ."""
    cached = COVER_CACHE.get(track_id)
    if cached:
        return cached
    digest = hashlib.sha256(track_id.encode("utf-8")).digest()
    hue = digest[0] / 255.0
    top = tuple(int(v) for v in _hsv(hue, 0.55, 0.85))
    bottom = tuple(int(v) for v in _hsv((hue + 0.08) % 1.0, 0.75, 0.35))
    size = 512
    image = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(image)
    for y in range(size):
        ratio = y / (size - 1)
        draw.line([(0, y), (size, y)], fill=tuple(
            int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3)))
    draw.ellipse([size * 0.30, size * 0.30, size * 0.70, size * 0.70],
                 outline=(255, 255, 255), width=10)
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    data = buffer.getvalue()
    COVER_CACHE[track_id] = data
    return data


def _hsv(h, s, v):
    i = int(h * 6)
    f = h * 6 - i
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    r, g, b = [(v, t, p), (q, v, p), (p, v, t),
               (p, q, v), (t, p, v), (v, p, q)][i % 6]
    return r * 255, g * 255, b * 255


def silent_wav(seconds: int = 120) -> bytes:
    # Long enough that a test can seek around the lyrics without the queue
    # advancing underneath it; 8kHz keeps the buffer at ~2 MB.
    rate = 8000
    samples = rate * seconds
    data = b"\x00\x00" * samples
    header = struct.pack("<4sI4s4sIHHIIHH4sI",
                         b"RIFF", 36 + len(data), b"WAVE", b"fmt ",
                         16, 1, 1, rate, rate * 2, 2, 16, b"data", len(data))
    return header + data


WAV = silent_wav()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        print("HTTP " + (fmt % args), flush=True)

    def do_GET(self):
        if self.headers.get("Upgrade", "").lower() == "websocket":
            self.handle_websocket()
            return
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path in ("/websocket", PREFIX + "/websocket"):
            self.send_text(400, "expected upgrade")
            return
        if not path.startswith(PREFIX):
            self.send_text(404, "not found")
            return
        rest = path[len(PREFIX):]
        if not rest.startswith("/"):
            rest = "/" + rest

        if rest == "/api/health":
            self.send_json({"ok": True, "app": "tv-mock"})
            return
        if rest == "/api/library/status":
            self.send_json({"ok": True, "count": len(TRACKS),
                            "album_count": len(ALBUMS),
                            "artist_count": len(ARTISTS_ROWS)})
            return
        if rest == "/api/library/groups":
            view = (query.get("view") or [""])[0]
            if view == "genres":
                rows = creator_rows("genre")
            elif view == "composers":
                rows = creator_rows("composer")
            elif view == "artists":
                rows = ARTISTS_ROWS
            else:
                rows = ALBUMS
            self.send_json({"groups": rows, "count": len(rows),
                            "limit": len(rows), "offset": 0, "paged": True})
            return
        if rest == "/api/library/items":
            wanted = set(filter(None, (query.get("ids") or [""])[0].split(",")))
            rows = [row for row in TRACKS if row["id"] in wanted]
            self.send_json({"items": rows, "total": len(rows), "paged": True})
            return
        if rest == "/api/state/user":
            self.send_json({"state": {
                "initialized": True,
                "revision": 1,
                "favorites": [row["id"] for row in TRACKS[1:5]],
                "playlists": [
                    {"id": "p1", "name": "夜间驾驶",
                     "trackIds": [row["id"] for row in TRACKS[4:9]]},
                    {"id": "p2", "name": "周末清晨",
                     "trackIds": [row["id"] for row in TRACKS[9:13]]},
                ],
            }})
            return
        if rest == "/api/lyrics":
            track_id = (query.get("track_id") or [""])[0]
            if not any(row["id"] == track_id for row in TRACKS):
                self.send_json({"error": "track not found"})
                return
            # The last track answers "no match" on purpose so the television's
            # empty state can be exercised without a real provider.
            if TRACKS and track_id == TRACKS[-1]["id"]:
                self.send_json({"lyrics": "", "status": "no_match", "pending": False})
                return
            self.send_json({"lyrics": lyric_document(track_id),
                            "status": "ok", "pending": False, "source": "tv-mock"})
            return
        if rest == "/api/library":
            self.handle_library(query)
            return
        if rest.startswith("/cover/"):
            track_id = rest[len("/cover/"):]
            self.send_bytes(200, "image/png", cover_png(track_id))
            return
        if rest.startswith("/media/"):
            track_id = rest[len("/media/"):]
            if not any(track["id"] == track_id for track in TRACKS):
                self.send_text(404, "no such track")
                return
            self.send_bytes(200, "audio/wav", WAV)
            return
        self.send_text(404, "unmapped: " + rest)

    def handle_library(self, query):
        album = (query.get("album") or [""])[0]
        search = (query.get("search") or [""])[0].lower()
        group = (query.get("group") or [""])[0]
        view = (query.get("view") or ["all"])[0]
        rows = list(TRACKS)
        if album:
            rows = [row for row in rows if row["album"] == album]
        if group:
            rows = [row for row in rows
                    if group in (row["album"], row["artist"],
                                 row["genre"], row["composer"])]
        if search:
            rows = [row for row in rows if search in row["artist"].lower()
                    or search in row["album"].lower()
                    or search in row["title"].lower()]
        if view == "recent":
            rows = list(reversed(rows))
        elif view == "dsd":
            rows = [row for row in rows if row["format"].startswith("DSD")]
        limit = int((query.get("limit") or ["100"])[0])
        self.send_json({"items": rows[:limit], "total": len(rows),
                        "has_more": False, "paged": True})

    # ------------------------------------------------------------- websocket

    def handle_websocket(self):
        key = self.headers.get("Sec-WebSocket-Key", "")
        print("WS handshake key=%r" % key, flush=True)
        accept = base64.b64encode(hashlib.sha1(
            (key + WS_GUID).encode("ascii")).digest()).decode("ascii")
        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        self.wfile.flush()
        self.ws_loop()

    def ws_loop(self):
        try:
            while True:
                frame = self.read_frame()
                if frame is None:
                    return
                opcode, payload = frame
                if opcode == 0x8:
                    return
                if opcode not in (0x1, 0x2):
                    continue
                try:
                    request = json.loads(payload.decode("utf-8"))
                except Exception:
                    continue
                print("WS req %s" % request.get("req"), flush=True)
                # The client matches the reply by reqid; echoing it is the
                # whole handshake as far as the TV client is concerned.
                reply = {
                    "reqid": request.get("reqid", ""),
                    "result": "succ",
                    "token": TOKEN,
                    "longToken": TOKEN,
                }
                self.write_frame(json.dumps(reply).encode("utf-8"))
        except Exception:
            return
        finally:
            try:
                self.close_connection = True
            except Exception:
                pass

    def read_frame(self):
        header = self.rfile.read(2)
        if len(header) < 2:
            return None
        first, second = header[0], header[1]
        opcode = first & 0x0F
        masked = (second & 0x80) != 0
        length = second & 0x7F
        if length == 126:
            length = struct.unpack(">H", self.rfile.read(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", self.rfile.read(8))[0]
        mask = self.rfile.read(4) if masked else b""
        data = self.rfile.read(length) if length else b""
        if masked and data:
            data = bytes(byte ^ mask[i % 4] for i, byte in enumerate(data))
        return opcode, data

    def write_frame(self, payload: bytes):
        header = bytearray([0x81])
        size = len(payload)
        if size < 126:
            header.append(size)
        elif size < 65536:
            header.append(126)
            header += struct.pack(">H", size)
        else:
            header.append(127)
            header += struct.pack(">Q", size)
        self.wfile.write(bytes(header) + payload)
        self.wfile.flush()

    # ---------------------------------------------------------------- output

    def send_json(self, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_bytes(200, "application/json; charset=utf-8", body)

    def send_bytes(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Accept-Ranges", "none")
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, status, text):
        self.send_bytes(status, "text/plain; charset=utf-8",
                        text.encode("utf-8"))


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 18099), Handler)
    server.daemon_threads = True
    print("tv-mock listening on 127.0.0.1:18099", flush=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import random
import re
import shutil
import sqlite3
import subprocess
import threading
import time
import tempfile
from contextlib import contextmanager
from typing import Any, Dict

from transcode import find_ffmpeg

SUPPORTED = {
    ".flac": "audio/flac", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".aac": "audio/aac",
    ".ogg": "audio/ogg", ".opus": "audio/ogg", ".wav": "audio/wav", ".aiff": "audio/aiff",
    ".aif": "audio/aiff", ".wma": "audio/x-ms-wma", ".dsf": "audio/x-dsf", ".dff": "audio/x-dff", ".cue": "application/x-cue",
}
METADATA_VERSION = 15
UNCLASSIFIED = "未分类"
GROUP_LABEL_VERSION = "3"
MUSIC_CACHE = {"stamp": 0, "items": []}
FS_CACHE = {"signature": ""}
SCAN_STATE = {"running": False, "last_error": "", "last_scan": 0, "current": "", "phase": "", "scanned": 0, "found": 0, "errors": []}
SCAN_LOCK = threading.Lock()
LIBRARY_JSON_CACHE_LIMIT = 5000
ALLOWED_LIBRARY_PREFIXES = ("/vol", "/volume", "/mnt", "/share", "/var/apps/fnaudio/share")


def record_scan_error(path, message):
    errors = SCAN_STATE.setdefault("errors", [])
    errors.append({"path": str(path or ""), "message": str(message or "")})
    if len(errors) > 20:
        del errors[:-20]


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

def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def clean_tag(value):
    return re.sub(r"\s+", " ", str(value or "").replace("\x00", "")).strip()

def safe_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0

def parse_track_number(value):
    """Return the numeric part of common track tags such as 03/12."""
    text = clean_tag(value)
    if not text:
        return 0
    match = re.match(r"^\s*(\d+)", text)
    return int(match.group(1)) if match else 0

def safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0

def display_library_path(config):
    return "\n".join(normalize_library_paths(config))

def library_root_labels(config):
    roots = normalize_library_paths(config)
    if len(roots) <= 1:
        return {}
    base_counts = {}
    for root in roots:
        base = os.path.basename(root.rstrip(os.sep)) or root.strip(os.sep).replace(os.sep, "-") or "音乐目录"
        base_counts[base] = base_counts.get(base, 0) + 1
    labels = {}
    for root in roots:
        base = os.path.basename(root.rstrip(os.sep)) or root.strip(os.sep).replace(os.sep, "-") or "音乐目录"
        if base_counts.get(base, 0) > 1:
            parent = os.path.basename(os.path.dirname(root.rstrip(os.sep))) or "目录"
            labels[os.path.abspath(root)] = "%s/%s" % (parent, base)
        else:
            labels[os.path.abspath(root)] = base
    return labels

def library_root_label(root, config):
    return library_root_labels(config or {}).get(os.path.abspath(root), "")

def relative_folder_for_path(path, root):
    try:
        rel = os.path.dirname(os.path.relpath(os.path.abspath(path), os.path.abspath(root)))
    except (OSError, ValueError):
        return ""
    parts = os.path.normpath(rel).split(os.sep)
    return "/".join(x for x in parts if x and x != ".")

def decode_id3_text(data):
    if not data:
        return ""
    encoding = data[0]
    raw = data[1:]
    try:
        if encoding == 0:
            for codec in ("utf-8", "gb18030", "latin1"):
                try:
                    return raw.decode(codec)
                except UnicodeError:
                    continue
            return raw.decode("latin1", "ignore")
        if encoding == 1:
            return raw.decode("utf-16", "ignore")
        if encoding == 2:
            return raw.decode("utf-16-be", "ignore")
        return raw.decode("utf-8", "ignore")
    except UnicodeError:
        return raw.decode("utf-8", "ignore")

def read_id3_header_at(fh, offset):
    try:
        fh.seek(offset)
        header = fh.read(10)
        if header[:3] != b"ID3":
            return None, b""
        size = 0
        for byte in header[6:10]:
            size = (size << 7) | (byte & 0x7F)
        return header, fh.read(size)
    except OSError:
        return None, b""

def id3_payload(path):
    header, data = id3_tag(path)
    return data

def id3_tag(path):
    try:
        with open(path, "rb") as fh:
            header, data = read_id3_header_at(fh, 0)
            if header:
                return header, data
            ext = os.path.splitext(path)[1].lower()
            if ext != ".dsf":
                return None, b""
            fh.seek(0)
            dsf_header = fh.read(28)
            if dsf_header[:4] != b"DSD " or len(dsf_header) < 28:
                return None, b""
            metadata_offset = int.from_bytes(dsf_header[20:28], "little")
            if metadata_offset <= 0:
                return None, b""
            return read_id3_header_at(fh, metadata_offset)
    except OSError:
        return None, b""

def id3_frame_size(data, offset, major):
    raw = data[offset + 4:offset + 8]
    if major == 4:
        size = 0
        for byte in raw:
            size = (size << 7) | (byte & 0x7F)
        return size
    return int.from_bytes(raw, "big")

def read_id3(path):
    tags = {}
    header, data = id3_tag(path)
    if not data:
        return read_id3v1(path)
    major = header[3] if header else 3
    offset = 0
    while offset + 10 <= len(data):
        frame_id = data[offset:offset + 4].decode("latin1", "ignore")
        frame_size = id3_frame_size(data, offset, major)
        if not frame_id.strip("\x00") or frame_size <= 0:
            break
        frame = data[offset + 10:offset + 10 + frame_size]
        field = {
            "TIT2": "title",
            "TPE1": "artist",
            "TALB": "album",
            "TCOM": "composer",
            "TCON": "genre",
            "TRCK": "track_no",
        }.get(frame_id)
        if field:
            value = decode_id3_text(frame).split("\x00", 1)[0]
            tags[field] = parse_track_number(value) if field == "track_no" else clean_tag(value)
        offset += 10 + frame_size
    return tags

def read_id3_cover(path):
    header, data = id3_tag(path)
    major = header[3] if header else 3
    offset = 0
    while offset + 10 <= len(data):
        frame_id = data[offset:offset + 4].decode("latin1", "ignore")
        frame_size = id3_frame_size(data, offset, major)
        if not frame_id.strip("\x00") or frame_size <= 0:
            break
        frame = data[offset + 10:offset + 10 + frame_size]
        if frame_id == "APIC" and frame:
            encoding = frame[0]
            pos = 1
            mime_end = frame.find(b"\x00", pos)
            if mime_end < 0:
                break
            mime = frame[pos:mime_end].decode("latin1", "ignore") or "image/jpeg"
            pos = mime_end + 2
            if encoding in (1, 2):
                end = frame.find(b"\x00\x00", pos)
                pos = end + 2 if end >= 0 else pos
            else:
                end = frame.find(b"\x00", pos)
                pos = end + 1 if end >= 0 else pos
            image = frame[pos:]
            if image:
                return mime, image
        offset += 10 + frame_size
    return None, None

def read_flac_cover(path):
    try:
        with open(path, "rb") as fh:
            if fh.read(4) != b"fLaC":
                return None, None
            while True:
                header = fh.read(4)
                if len(header) < 4:
                    return None, None
                block_type = header[0] & 0x7F
                last = bool(header[0] & 0x80)
                size = int.from_bytes(header[1:4], "big")
                data = fh.read(size)
                if block_type == 6 and len(data) > 32:
                    mime_len = int.from_bytes(data[4:8], "big")
                    pos = 8
                    mime = data[pos:pos + mime_len].decode("utf-8", "ignore") or "image/jpeg"
                    pos += mime_len
                    desc_len = int.from_bytes(data[pos:pos + 4], "big")
                    pos += 4 + desc_len + 16
                    image_len = int.from_bytes(data[pos:pos + 4], "big")
                    pos += 4
                    return mime, data[pos:pos + image_len]
                if last:
                    return None, None
    except OSError:
        return None, None

def read_m4a_cover(path, config=None):
    cover = read_mp4_covr_cover(path)
    if cover[1]:
        return cover
    ffmpeg = find_ffmpeg(config or {})
    if not ffmpeg:
        return None, None
    fd, target = tempfile.mkstemp(prefix="fnaudio-cover-", suffix=".jpg")
    os.close(fd)
    command = [
        ffmpeg, "-v", "error", "-y", "-i", path,
        "-map", "0:v:0", "-frames:v", "1", "-c:v", "mjpeg", "-q:v", "2",
        "-f", "image2", target,
    ]
    env = os.environ.copy()
    if "/usr/trim/lib/mediasrv/bin" in ffmpeg:
        env["LD_LIBRARY_PATH"] = "/usr/trim/lib/mediasrv/lib:" + env.get("LD_LIBRARY_PATH", "")
    try:
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, env=env, check=False)
        with open(target, "rb") as fh:
            body = fh.read()
    except (OSError, subprocess.SubprocessError):
        body = b""
    finally:
        try:
            os.unlink(target)
        except OSError:
            pass
    if body.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", body
    if body.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", body
    if body.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif", body
    return None, None

def read_mp4_covr_cover(path):
    """Read JPEG/PNG artwork from the MP4/M4A ilst/covr atom."""
    containers = {b"moov", b"udta", b"meta", b"ilst", b"covr"}

    def image_from_bytes(data):
        if data.startswith(b"\xff\xd8\xff"):
            end = data.find(b"\xff\xd9", 3)
            return "image/jpeg", data[:end + 2] if end >= 0 else data
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            end = data.find(b"IEND")
            return "image/png", data[:end + 8] if end >= 0 else data
        if data.startswith((b"GIF87a", b"GIF89a")):
            end = data.rfind(b"\x3b")
            return "image/gif", data[:end + 1] if end >= 0 else data
        return None, None

    def scan_covr_payload(fh, start, limit):
        fh.seek(start)
        data = fh.read(max(0, min(limit - start, 8 * 1024 * 1024)))
        covr_at = data.find(b"covr")
        if covr_at < 0:
            return None, None
        window = data[covr_at:covr_at + 4 * 1024 * 1024]
        markers = [
            (b"\xff\xd8\xff", None),
            (b"\x89PNG\r\n\x1a\n", None),
            (b"GIF87a", None),
            (b"GIF89a", None),
        ]
        positions = [pos for marker, _ in markers for pos in [window.find(marker)] if pos >= 0]
        if not positions:
            return None, None
        image_start = min(positions)
        image = window[image_start:]
        mime, body = image_from_bytes(image)
        return mime, body

    try:
        with open(path, "rb") as fh:
            end = os.fstat(fh.fileno()).st_size

            def walk(start, limit):
                position = start
                while position + 8 <= limit:
                    fh.seek(position)
                    header = fh.read(8)
                    if len(header) < 8:
                        break
                    size = int.from_bytes(header[:4], "big")
                    kind = header[4:8]
                    header_size = 8
                    if size == 1:
                        size = int.from_bytes(fh.read(8), "big")
                        header_size = 16
                    elif size == 0:
                        size = limit - position
                    if size < header_size or position + size > limit:
                        break
                    payload = position + header_size
                    payload_end = position + size
                    if kind == b"data" and payload + 16 <= payload_end:
                        fh.seek(payload + 8)
                        body = fh.read(payload_end - payload - 8)
                        mime, image = image_from_bytes(body)
                        if image:
                            return mime, image
                    elif kind in containers:
                        child_start = payload + 4 if kind == b"meta" else payload
                        result = walk(child_start, payload_end)
                        if result[1]:
                            return result
                    position += size
                return None, None

            result = walk(0, end)
            if result[1]:
                return result
            return scan_covr_payload(fh, 0, end)
    except (OSError, ValueError):
        return None, None

def read_cover(path, config=None):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".mp3", ".dsf", ".dff"):
        return read_id3_cover(path)
    if ext == ".flac":
        return read_flac_cover(path)
    if ext in (".m4a", ".mp4"):
        return read_m4a_cover(path, config)
    return None, None

def read_sidecar_cover(*paths):
    names = ("cover.jpg", "cover.jpeg", "cover.png", "folder.jpg", "folder.jpeg", "folder.png")
    dirs = []
    for path in paths:
        if path:
            directory = os.path.dirname(path)
            if directory and directory not in dirs:
                dirs.append(directory)
    for directory in dirs:
        try:
            entries = {name.lower(): name for name in os.listdir(directory)}
        except OSError:
            continue
        for name in names:
            actual = entries.get(name)
            if not actual:
                continue
            target = os.path.join(directory, actual)
            try:
                with open(target, "rb") as fh:
                    body = fh.read()
                mime = mimetypes.guess_type(target)[0] or ("image/png" if actual.lower().endswith(".png") else "image/jpeg")
                if body:
                    return mime, body
            except OSError:
                continue
    return None, None

def read_cover_for_item(item, config=None):
    mime, body = read_cover(item["path"], config)
    if body:
        return mime, body
    return read_sidecar_cover(item.get("cue_path"), item.get("path"))

def read_vorbis_comments(path):
    tags = {}
    try:
        with open(path, "rb") as fh:
            data = fh.read(1024 * 1024)
    except OSError:
        return tags
    for key, value in re.findall(rb"(?i)(TITLE|ARTIST|ALBUM|COMPOSER|GENRE|TRACKNUMBER)=([^\x00\r\n]+)", data):
        name = key.decode().lower()
        tags["track_no" if name == "tracknumber" else name] = (
            parse_track_number(value.decode("utf-8", "ignore"))
            if name == "tracknumber" else clean_tag(value.decode("utf-8", "ignore"))
        )
    return tags

def read_probe_metadata(path, config=None):
    ffprobe = find_ffprobe(config or {})
    if not ffprobe:
        return {}, {}
    command = [
        ffprobe,
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "format=duration:format_tags:stream_tags:stream=sample_rate,bits_per_raw_sample,bits_per_sample,bit_rate",
        "-of", "json",
        path,
    ]
    env = os.environ.copy()
    if "/usr/trim/lib/mediasrv/bin" in ffprobe:
        env["LD_LIBRARY_PATH"] = "/usr/trim/lib/mediasrv/lib:" + env.get("LD_LIBRARY_PATH", "")
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20, env=env)
        data = json.loads(result.stdout.decode("utf-8", "ignore") or "{}")
        raw_tags = {}
        for source in ((data.get("format") or {}).get("tags") or {},):
            raw_tags.update(source)
        stream = (data.get("streams") or [{}])[0]
        for stream in data.get("streams") or []:
            if stream.get("tags"):
                raw_tags.update(stream.get("tags") or {})
    except Exception:
        return {}, {}
    tags = {}
    aliases = {
        "title": ("title", "tit2", "\xa9nam"),
        "artist": ("artist", "artists", "album_artist", "albumartist", "performer", "performers", "author", "tpe1", "\xa9art"),
        "album": ("album", "talb", "\xa9alb"),
        "composer": ("composer", "composers", "tcom", "\xa9wrt"),
        "genre": ("genre", "genres", "tcon", "\xa9gen"),
        "track_no": ("track", "tracknumber", "track_number", "trck", "trkn", "\xa9trk", "tracknum", "disktrack"),
    }
    normalized_tags = {str(key or "").strip().lower(): value for key, value in raw_tags.items()}
    for field, keys in aliases.items():
        for key in keys:
            value = normalized_tags.get(key)
            if value:
                tags[field] = parse_track_number(value) if field == "track_no" else clean_tag(value)
                break
    for key, value in raw_tags.items():
        normalized = str(key or "").lower()
        if normalized in ("title", "artist", "album", "composer", "genre") and value:
            tags.setdefault(normalized, clean_tag(value))
    stream = (data.get("streams") or [{}])[0]
    audio_info = {
        "sample_rate": safe_int(stream.get("sample_rate")),
        "bit_depth": safe_int(stream.get("bits_per_raw_sample") or stream.get("bits_per_sample")),
        "bit_rate": safe_int(stream.get("bit_rate")),
        "duration": safe_float((data.get("format") or {}).get("duration")),
    }
    return tags, audio_info

def read_probe_tags(path, config=None):
    tags, _ = read_probe_metadata(path, config)
    return tags

def decode_id3v1_field(data):
    raw = data.rstrip(b"\x00 ").strip()
    for encoding in ("utf-8", "gb18030", "latin1"):
        try:
            return clean_tag(raw.decode(encoding))
        except UnicodeError:
            continue
    return clean_tag(raw.decode("latin1", "ignore"))

def read_id3v1(path):
    try:
        with open(path, "rb") as fh:
            fh.seek(-128, os.SEEK_END)
            data = fh.read(128)
    except OSError:
        return {}
    if len(data) != 128 or data[:3] != b"TAG":
        return {}
    tags = {
        "title": decode_id3v1_field(data[3:33]),
        "artist": decode_id3v1_field(data[33:63]),
        "album": decode_id3v1_field(data[63:93]),
    }
    return {key: value for key, value in tags.items() if value}

def read_metadata(path, root, config=None, probe_tags=None):
    ext = os.path.splitext(path)[1].lower()
    tags = dict(probe_tags or read_probe_tags(path, config or {}))
    local_tags = read_id3(path) if ext in (".mp3", ".dsf", ".dff") else read_vorbis_comments(path)
    for key, value in local_tags.items():
        tags.setdefault(key, value)
    tag_title = clean_tag(tags.get("title"))
    tag_artist = clean_tag(tags.get("artist"))
    filename_artist, filename_title = artist_title_from_filename(path)
    title = tag_title or filename_title or display_name(path)
    artist = tag_artist or filename_artist or "未知艺术家"
    album = clean_tag(tags.get("album")) or UNCLASSIFIED
    folder = relative_folder_for_path(path, root)
    root_label = library_root_label(root, config or {})
    return {
        "title": title,
        "artist": artist,
        "album": album,
        "composer": tags.get("composer") or "未知作曲者",
        "genre": tags.get("genre") or "未分类",
        "track_no": parse_track_number(tags.get("track_no")),
        "folder": folder,
        "library_root": root_label,
        "metadata_source": {
            "title": "tag" if tag_title else "filename",
            "artist": "tag" if tag_artist else ("filename" if filename_artist else "unknown"),
            "album": "tag" if clean_tag(tags.get("album")) else "unknown",
        },
    }

def artist_title_from_filename(path):
    name = os.path.splitext(os.path.basename(path))[0]
    name = re.sub(r"^\d{1,3}[\s._-]+", "", name).replace("_", " ").strip()
    for separator in (" - ", " – ", " — ", " -", "- "):
        if separator not in name:
            continue
        left, right = name.split(separator, 1)
        left = clean_tag(left)
        right = clean_tag(right)
        if len(left) >= 1 and len(right) >= 1:
            return left, right
    return "", ""

def display_name(path):
    name = os.path.splitext(os.path.basename(path))[0]
    name = re.sub(r"^\d{1,3}[\s._-]+", "", name)
    return name.replace("_", " ").strip() or "未知曲目"

def cue_time_seconds(value):
    match = re.match(r"(\d+):(\d+):(\d+)", str(value or ""))
    if not match:
        return 0.0
    minutes, seconds, frames = [int(x) for x in match.groups()]
    return minutes * 60 + seconds + frames / 75.0

def cue_value(line):
    match = re.search(r'"([^"]*)"', line)
    if match:
        return clean_tag(match.group(1))
    parts = line.split(None, 1)
    return clean_tag(parts[1] if len(parts) > 1 else "")

def read_cue_lines(cue_path):
    for encoding in ("utf-8-sig", "gb18030", "big5", "latin1"):
        try:
            with open(cue_path, "r", encoding=encoding) as fh:
                return fh.read().splitlines()
        except UnicodeError:
            continue
        except OSError:
            return []
    return []

def parse_cue_tracks(cue_path, root, config=None):
    text = read_cue_lines(cue_path)
    if not text:
        return []
    album = os.path.splitext(os.path.basename(cue_path))[0]
    album_artist = "未知艺术家"
    current_file = ""
    current = None
    tracks = []
    for raw in text:
        line = raw.strip()
        upper = line.upper()
        if upper.startswith("FILE "):
            current_file = cue_value(line)
        elif upper.startswith("TITLE ") and current is None:
            album = cue_value(line) or album
        elif upper.startswith("PERFORMER ") and current is None:
            album_artist = cue_value(line) or album_artist
        elif upper.startswith("TRACK "):
            if current:
                tracks.append(current)
            number = re.findall(r"\d+", line)
            current = {"track_no": int(number[0]) if number else len(tracks) + 1, "file": current_file, "title": "", "artist": "", "start": 0.0}
        elif current and upper.startswith("TITLE "):
            current["title"] = cue_value(line)
        elif current and upper.startswith("PERFORMER "):
            current["artist"] = cue_value(line)
        elif current and upper.startswith("INDEX 01"):
            parts = line.split()
            current["start"] = cue_time_seconds(parts[-1] if parts else "")
    if current:
        tracks.append(current)
    for index, track in enumerate(tracks):
        track["end"] = 0.0
        for candidate in tracks[index + 1:]:
            if candidate.get("file") == track.get("file") and safe_float(candidate.get("start")) > safe_float(track.get("start")):
                track["end"] = safe_float(candidate.get("start"))
                break
    items = []
    cue_dir = os.path.dirname(cue_path)
    for track in tracks:
        audio_path = os.path.abspath(os.path.join(cue_dir, track.get("file") or ""))
        ext = os.path.splitext(audio_path)[1].lower()
        if ext not in SUPPORTED or ext == ".cue" or not os.path.isfile(audio_path):
            continue
        try:
            stat = os.stat(audio_path)
        except OSError:
            continue
        item_id = hashlib.sha1((cue_path + ":" + str(track.get("track_no"))).encode("utf-8", "ignore")).hexdigest()[:16]
        probe_tags, audio_info = read_probe_metadata(audio_path, config or {})
        metadata = read_metadata(audio_path, root, config or {}, probe_tags)
        metadata.update({"title": track.get("title") or metadata.get("title"), "artist": track.get("artist") or album_artist or metadata.get("artist"), "album": album or metadata.get("album")})
        metadata["track_no"] = safe_int(track.get("track_no"))
        metadata["metadata_source"] = {"title": "cue", "artist": "cue", "album": "cue"}
        metadata["folder"] = relative_folder_for_path(cue_path, root)
        cue_start = safe_float(track.get("start"))
        cue_end = safe_float(track.get("end")) or safe_float(audio_info.get("duration"))
        cue_duration = max(0.0, cue_end - cue_start) if cue_end > cue_start else 0.0
        items.append({"id": item_id, **metadata, "format": ext[1:].upper(), "mime": SUPPORTED[ext], "is_dsd": ext in (".dsf", ".dff"), "size": stat.st_size, **audio_info, "duration": cue_duration, "path": audio_path, "cue_path": cue_path, "cue_track": True, "cue_start": cue_start, "cue_end": cue_end, "added": int(time.time()), "added_ns": int(time.time() * 1000000000), "modified": int(os.path.getmtime(cue_path)), "modified_ns": os.stat(cue_path).st_mtime_ns, "metadata_version": METADATA_VERSION})
    return items

def scan_library(root, previous_items=None, config=None):
    items = []
    signature_parts = []
    previous = {}
    scan_started = time.time()
    for item in previous_items or []:
        if item.get("path"):
            previous[item["path"]] = item
    root = os.path.abspath(os.path.expanduser(root))
    if not is_allowed_library_path(root) or not os.path.isdir(root):
        return items, ""
    cue_audio_paths = set()
    SCAN_STATE["phase"] = "扫描 CUE"
    for base, _, files in os.walk(root):
        SCAN_STATE["current"] = base
        for filename in files:
            if os.path.splitext(filename)[1].lower() != ".cue":
                continue
            full = os.path.join(base, filename)
            cue_items = parse_cue_tracks(full, root, config or {})
            items.extend(cue_items)
            cue_audio_paths.update(os.path.abspath(item.get("path", "")) for item in cue_items if item.get("path"))
            SCAN_STATE["found"] = len(items)
            try:
                stat = os.stat(full)
                signature_parts.append("%s:%s:%s" % (full, stat.st_mtime_ns, stat.st_size))
            except OSError:
                record_scan_error(full, "无法读取 CUE 文件状态")
                pass
            for item in cue_items:
                audio_path = item.get("path")
                if not audio_path:
                    continue
                try:
                    stat = os.stat(audio_path)
                    signature_parts.append("%s:%s:%s" % (audio_path, stat.st_mtime_ns, stat.st_size))
                except OSError:
                    record_scan_error(audio_path, "无法读取 CUE 音频文件状态")
                    pass
        SCAN_STATE["phase"] = "扫描音频文件"
        for filename in files:
            SCAN_STATE["scanned"] += 1
            ext = os.path.splitext(filename)[1].lower()
            if ext not in SUPPORTED:
                continue
            full = os.path.join(base, filename)
            if ext == ".cue":
                continue
            if os.path.abspath(full) in cue_audio_paths:
                continue
            try:
                stat = os.stat(full)
            except OSError:
                record_scan_error(full, "无法读取文件状态")
                continue
            signature_parts.append("%s:%s:%s" % (full, stat.st_mtime_ns, stat.st_size))
            cached = previous.get(full)
            if cached and cached.get("size") == stat.st_size and cached.get("modified_ns") == stat.st_mtime_ns and cached.get("metadata_version") == METADATA_VERSION:
                items.append(cached)
                SCAN_STATE["found"] = len(items)
                continue
            item_id = hashlib.sha1(full.encode("utf-8", "ignore")).hexdigest()[:16]
            probe_tags, audio_info = read_probe_metadata(full, config or {})
            metadata = read_metadata(full, root, config, probe_tags)
            items.append(
                {
                    "id": item_id,
                    **metadata,
                    "format": ext[1:].upper(),
                    "mime": SUPPORTED[ext],
                    "is_dsd": ext in (".dsf", ".dff"),
                    "size": stat.st_size,
                    "duration": 0,
                    **audio_info,
                    "path": full,
                    "added": int(scan_started),
                    "added_ns": int(scan_started * 1000000000),
                    "modified": int(stat.st_mtime),
                    "modified_ns": stat.st_mtime_ns,
                    "metadata_version": METADATA_VERSION,
                }
            )
            SCAN_STATE["found"] = len(items)
        if len(items) and len(items) % 500 == 0:
            time.sleep(0.01)
    items.sort(key=lambda x: (x["artist"].lower(), x["album"].lower(), x["title"].lower()))
    signature_parts.append("metadata_version:%s" % METADATA_VERSION)
    signature = hashlib.sha1("|".join(sorted(signature_parts)).encode("utf-8", "ignore")).hexdigest()
    return items, signature

def scan_libraries(config, previous_items=None):
    all_items = []
    signatures = []
    for root in normalize_library_paths(config):
        items, signature = scan_library(root, previous_items, config)
        all_items.extend(items)
        if signature:
            signatures.append("%s:%s" % (root, signature))
    seen = set()
    unique = []
    for item in all_items:
        if item.get("id") in seen:
            continue
        seen.add(item.get("id"))
        unique.append(item)
    unique.sort(key=lambda x: (x["artist"].lower(), x["album"].lower(), x["title"].lower()))
    return unique, hashlib.sha1("|".join(sorted(signatures)).encode("utf-8", "ignore")).hexdigest()


def library_signature_for_config(config):
    """Build the filesystem signature without parsing audio metadata."""
    signatures = []
    for root in normalize_library_paths(config):
        signature = library_signature(root)
        if signature:
            signatures.append("%s:%s" % (root, signature))
    return hashlib.sha1("|".join(sorted(signatures)).encode("utf-8", "ignore")).hexdigest()

def library_status(config):
    roots = normalize_library_paths(config)
    root = roots[0] if roots else os.path.abspath(os.path.expanduser(config["library_path"]))
    db_summary = library_summary_from_sqlite(config)
    count = int(db_summary.get("count", len(MUSIC_CACHE["items"])))
    dsd_count = int(db_summary.get("dsd_count", sum(1 for item in MUSIC_CACHE["items"] if item.get("is_dsd"))))
    status = {
        "library_path": root,
        "library_paths": roots,
        "server_port": int(config.get("server_port", 18080)),
        "allowed": is_allowed_library_path(root),
        "exists": os.path.exists(root),
        "is_dir": os.path.isdir(root),
        "readable": os.access(root, os.R_OK),
        "count": count,
        "dsd_count": dsd_count,
        "scanning": SCAN_STATE["running"],
        "last_error": SCAN_STATE["last_error"],
        "last_scan": SCAN_STATE["last_scan"],
        "current": SCAN_STATE.get("current", ""),
        "phase": SCAN_STATE.get("phase", ""),
        "scanned": SCAN_STATE.get("scanned", 0),
        "found": SCAN_STATE.get("found", 0),
        "errors": list(SCAN_STATE.get("errors") or []),
        "supported_formats": sorted(x[1:].upper() for x in SUPPORTED),
    }
    if not status["allowed"]:
        status["message"] = "出于安全保护，这个路径不能作为音乐目录"
        return status
    if not status["exists"]:
        status["message"] = "音乐目录不存在，请在应用设置里选择正确的音乐文件夹"
        return status
    if not status["is_dir"]:
        status["message"] = "音乐路径不是文件夹"
        return status
    if not status["readable"]:
        status["message"] = "应用没有权限读取这个音乐文件夹"
        return status
    if status["scanning"] and not status["count"]:
        status["message"] = "正在扫描音乐目录"
    else:
        status["message"] = "音乐库已就绪" if status["count"] else "没有在这个目录里找到支持的音乐文件"
    return status

def browsable_roots():
    if os.name == "nt":
        return []
    roots = []
    for name in sorted(os.listdir("/")):
        path = "/" + name
        if re.match(r"^/vol\d+$", path) or path in ("/mnt", "/share", "/volume"):
            if os.path.isdir(path):
                roots.append(path)
    return roots

def list_music_directories(path):
    root = os.path.abspath(os.path.expanduser(path or ""))
    if not root:
        return browsable_roots()
    if not is_allowed_library_path(root) or not os.path.isdir(root):
        return []
    dirs = []
    try:
        with os.scandir(root) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    dirs.append(entry.path)
    except OSError:
        return []
    return sorted(dirs, key=lambda x: x.lower())

def library_signature(root):
    parts = []
    root = os.path.abspath(os.path.expanduser(root))
    if not is_allowed_library_path(root) or not os.path.isdir(root):
        return ""
    for base, _, files in os.walk(root):
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in SUPPORTED:
                continue
            full = os.path.join(base, filename)
            try:
                stat = os.stat(full)
            except OSError:
                continue
            parts.append("%s:%s:%s" % (full, stat.st_mtime_ns, stat.st_size))
    parts.append("metadata_version:%s" % METADATA_VERSION)
    return hashlib.sha1("|".join(sorted(parts)).encode("utf-8", "ignore")).hexdigest()

def refresh_library_if_changed(config, force=False):
    if not SCAN_LOCK.acquire(False):
        return
    SCAN_STATE["running"] = True
    SCAN_STATE["last_error"] = ""
    SCAN_STATE["current"] = ""
    SCAN_STATE["phase"] = "准备扫描"
    SCAN_STATE["scanned"] = 0
    SCAN_STATE["found"] = 0
    SCAN_STATE["errors"] = []
    try:
        previous_signature = FS_CACHE["signature"]
        if previous_signature and not force:
            # Startup and watcher refreshes only need a filesystem check. Do
            # not hydrate every indexed track unless a change is detected.
            quick_signature = library_signature_for_config(config)
            if quick_signature == previous_signature:
                SCAN_STATE["last_scan"] = time.time()
                return
        SCAN_STATE["phase"] = "读取旧索引"
        previous_items = MUSIC_CACHE["items"]
        if not previous_items:
            cached = load_items_from_sqlite(config)
            previous_items = (cached or {}).get("items", [])
        SCAN_STATE["phase"] = "扫描音乐目录"
        items, signature = scan_libraries(config, previous_items)
        MUSIC_CACHE["items"] = items
        MUSIC_CACHE["stamp"] = time.time()
        if signature != FS_CACHE["signature"] or not os.path.isfile(library_db_path(config)):
            FS_CACHE["signature"] = signature
            SCAN_STATE["phase"] = "保存音乐库索引"
            save_library_cache(config)
        elif not MUSIC_CACHE["stamp"] and previous_signature:
            MUSIC_CACHE["stamp"] = time.time()
        SCAN_STATE["last_scan"] = time.time()
    except Exception as exc:
        SCAN_STATE["last_error"] = str(exc)
    finally:
        SCAN_STATE["running"] = False
        SCAN_STATE["current"] = ""
        SCAN_STATE["phase"] = ""
        SCAN_LOCK.release()

def request_library_refresh(config, force=False):
    if SCAN_STATE["running"]:
        return
    threading.Thread(target=refresh_library_if_changed, args=(config, force), daemon=True).start()

def library_items(config, refresh=False):
    if refresh:
        request_library_refresh(config, True)
    return MUSIC_CACHE["items"]


def _track_search_condition(search, alias=""):
    value = str(search or "").strip().lower()
    if not value:
        return "", []
    prefix = (str(alias).strip() + ".") if str(alias).strip() else ""
    columns = ("title", "artist", "album", "album_artist", "composer", "genre", "folder", "path", "format")
    condition = "(" + " OR ".join("lower(COALESCE(%s%s, '')) LIKE ?" % (prefix, column) for column in columns) + ")"
    return condition, ["%" + value + "%"] * len(columns)

def query_library_page(config, params):
    if not os.path.isfile(library_db_path(config)):
        return _query_memory_library_page(config, params)
    limit = max(1, min(500, _param_int(params, "limit", 100)))
    offset = max(0, _param_int(params, "offset", 0))
    view = str(_first_param(params, "view", "all") or "all")
    group = str(_first_param(params, "group", "") or "")
    album = str(_first_param(params, "album", "") or "")
    folder = str(_first_param(params, "folder", "") or "")
    root = str(_first_param(params, "root", "") or "")
    search = str(_first_param(params, "search", "") or "").strip().lower()
    sort_key = str(_first_param(params, "sort", "title") or "title")
    sort_dir = "DESC" if str(_first_param(params, "dir", "asc")).lower() == "desc" else "ASC"
    sort_columns = {
        "title": "title COLLATE NOCASE",
        "artist": "artist COLLATE NOCASE",
        "album": "album COLLATE NOCASE",
        "format": "format COLLATE NOCASE",
        "added": "added_ns",
        "track_no": "CASE WHEN track_no <= 0 THEN 2147483647 ELSE track_no END",
    }
    order = sort_columns.get(sort_key, sort_columns["title"])
    with library_db_connect(config) as conn:
        total_tracks = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
    if total_tracks == 0 and MUSIC_CACHE["items"]:
        return _query_memory_library_page(config, params)
    where = []
    args = []
    if view == "dsd":
        where.append("is_dsd = 1")
    elif view == "recent":
        if search:
            condition, condition_args = _track_search_condition(search)
            where.append(condition)
            args.extend(condition_args)
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        with library_db_connect(config) as conn:
            count = conn.execute("SELECT COUNT(*) FROM tracks" + where_sql, args).fetchone()[0]
            rows = conn.execute(
                "SELECT item_json FROM tracks%s ORDER BY %s %s, title COLLATE NOCASE ASC, id ASC LIMIT ? OFFSET ?" % (where_sql, order, sort_dir),
                args + [limit, offset],
            )
            items = []
            for row in rows:
                try:
                    items.append(json.loads(row["item_json"]))
                except ValueError:
                    pass
        return {"items": items, "count": count, "limit": limit, "offset": offset, "paged": True}
    elif view == "random100":
        sample_limit = min(100, limit)
        if search:
            condition, condition_args = _track_search_condition(search)
            where.append(condition)
            args.extend(condition_args)
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        with library_db_connect(config) as conn:
            count = conn.execute("SELECT COUNT(*) FROM tracks" + where_sql, args).fetchone()[0]
            rows = conn.execute(
                "SELECT item_json FROM (SELECT item_json,title,artist,album,format,added_ns,track_no,id FROM tracks%s ORDER BY RANDOM() LIMIT ?) ORDER BY %s %s, title COLLATE NOCASE ASC, id ASC" % (where_sql, order, sort_dir),
                args + [sample_limit],
            )
            items = []
            for row in rows:
                try:
                    items.append(json.loads(row["item_json"]))
                except ValueError:
                    pass
        return {"items": items, "count": min(count, sample_limit), "limit": sample_limit, "offset": 0, "paged": True}
    elif view in ("albums", "artists", "composers", "genres") and group:
        column = {"albums": "album", "artists": "artist", "composers": "composer", "genres": "genre"}[view]
        where.append("COALESCE(NULLIF(%s, ''), ?) = ?" % column)
        args.extend([UNCLASSIFIED, group])
    elif view == "folders" and folder:
        if root:
            where.append("root = ?")
            args.append(root)
        where.append("folder = ?")
        args.append(folder)
    elif view == "folders" and root:
        where.append("root = ?")
        args.append(root)
        where.append("folder = ?")
        args.append("")
    if view in ("artists", "composers") and group and album:
        where.append("COALESCE(NULLIF(album, ''), ?) = ?")
        args.extend([UNCLASSIFIED, album])
    if search:
        condition, condition_args = _track_search_condition(search)
        where.append(condition)
        args.extend(condition_args)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    with library_db_connect(config) as conn:
        count = conn.execute("SELECT COUNT(*) FROM tracks" + where_sql, args).fetchone()[0]
        rows = conn.execute(
            "SELECT item_json FROM tracks%s ORDER BY %s %s, title COLLATE NOCASE ASC, id ASC LIMIT ? OFFSET ?" % (where_sql, order, sort_dir),
            args + [limit, offset],
        )
        items = []
        for row in rows:
            try:
                items.append(json.loads(row["item_json"]))
            except ValueError:
                pass
    return {"items": items, "count": count, "limit": limit, "offset": offset, "paged": True}

def _query_memory_library_page(config, params):
    items = list(library_items(config))
    limit = max(1, min(500, _param_int(params, "limit", 100)))
    offset = max(0, _param_int(params, "offset", 0))
    view = str(_first_param(params, "view", "all") or "all")
    group = str(_first_param(params, "group", "") or "")
    album = str(_first_param(params, "album", "") or "")
    folder = str(_first_param(params, "folder", "") or "")
    root = str(_first_param(params, "root", "") or "")
    search = str(_first_param(params, "search", "") or "").strip().lower()
    sort_key = str(_first_param(params, "sort", "title") or "title")
    sort_dir = "desc" if str(_first_param(params, "dir", "asc")).lower() == "desc" else "asc"

    def text(value):
        return str(value or "")

    def item_root(item):
        path = text(item.get("cue_path") or item.get("path"))
        for candidate in normalize_library_paths(config):
            if path and _path_under(path, candidate):
                return candidate
        return ""

    def matches_search(item):
        if not search:
            return True
        haystack = " ".join(text(item.get(k)).lower() for k in ("title", "artist", "album", "album_artist", "composer", "genre", "folder", "path", "format"))
        return search in haystack

    if view == "dsd":
        items = [item for item in items if item.get("is_dsd")]
    elif view == "recent":
        pass
    elif view == "random100":
        sample = list(items)
        random.shuffle(sample)
        items = sample[:100]
    elif view in ("albums", "artists", "composers", "genres") and group:
        key = {"albums": "album", "artists": "artist", "composers": "composer", "genres": "genre"}[view]
        items = [item for item in items if (text(item.get(key)) or UNCLASSIFIED) == group]
    elif view == "folders":
        if root:
            items = [item for item in items if item_root(item) == root]
        if folder:
            items = [item for item in items if text(item.get("folder")) == folder]

    if view in ("artists", "composers") and group and album:
        items = [item for item in items if (text(item.get("album")) or UNCLASSIFIED) == album]
    items = [item for item in items if matches_search(item)]
    reverse = sort_dir == "desc"
    key_map = {
        "title": lambda item: text(item.get("title")).lower(),
        "artist": lambda item: text(item.get("artist")).lower(),
        "album": lambda item: text(item.get("album")).lower(),
        "format": lambda item: text(item.get("format")).lower(),
        "added": lambda item: safe_int(item.get("added_ns")) or safe_int(item.get("added")),
        "track_no": lambda item: safe_int(item.get("track_no")) or 2147483647,
    }
    items.sort(key=key_map.get(sort_key, key_map["title"]), reverse=reverse)
    count = len(items)
    return {"items": items[offset:offset + limit], "count": count, "limit": limit, "offset": offset, "paged": True, "fallback": "memory"}

def query_library_groups(config, view, search="", limit=None, offset=0, sort_dir="asc", artist="", composer=""):
    table_map = {"albums": "albums", "artists": "artists", "composers": "composers", "genres": "genres"}
    table = table_map.get(str(view or ""))
    if not table or not os.path.isfile(library_db_path(config)):
        return {"groups": [], "count": 0, "limit": 0, "offset": 0, "paged": True} if limit is not None else []
    direction = "DESC" if str(sort_dir or "").lower() == "desc" else "ASC"
    artist = str(artist or "")
    composer = str(composer or "")
    if view == "albums" and (artist or composer):
        owner_column = "composer" if composer else "artist"
        owner = composer or artist
        search_condition, search_args = _track_search_condition(search)
        matched_where = (" WHERE " + search_condition) if search_condition else ""
        cte = (
            "WITH scoped AS ("
            "SELECT t.*, COALESCE(NULLIF(t.album, ''), ?) AS group_name FROM tracks t "
            "WHERE COALESCE(NULLIF(t.%s, ''), ?) = ?"
            "), matched AS (SELECT DISTINCT group_name FROM scoped%s) "
            % (owner_column, matched_where)
        )
        cte_args = [UNCLASSIFIED, UNCLASSIFIED, owner] + search_args
        artist_expr = "COALESCE(NULLIF(MIN(NULLIF(s.album_artist, '')), ''), NULLIF(MIN(NULLIF(s.artist, '')), ''), ?)"
        select_sql = (
            "SELECT s.group_name AS name, %s AS artist, COUNT(*) AS track_count, MIN(s.id) AS cover_track_id "
            "FROM scoped s JOIN matched m ON m.group_name = s.group_name "
            "GROUP BY s.group_name ORDER BY s.group_name COLLATE NOCASE %s"
            % (artist_expr, direction)
        )
        with library_db_connect(config) as conn:
            if limit is None:
                rows = conn.execute(cte + select_sql, cte_args + [UNCLASSIFIED])
                return [dict(row) for row in rows]
            try:
                page_limit = max(1, min(500, int(float(limit))))
            except (TypeError, ValueError):
                page_limit = 100
            try:
                page_offset = max(0, int(float(offset or 0)))
            except (TypeError, ValueError):
                page_offset = 0
            count = conn.execute(cte + "SELECT COUNT(*) FROM matched", cte_args).fetchone()[0]
            rows = conn.execute(cte + select_sql + " LIMIT ? OFFSET ?", cte_args + [UNCLASSIFIED, page_limit, page_offset])
            return {"groups": [dict(row) for row in rows], "count": count, "limit": page_limit, "offset": page_offset, "paged": True}
    search_condition, search_args = _track_search_condition(search, "t")
    group_column = {"albums": "album", "artists": "artist", "composers": "composer", "genres": "genre"}[view]
    if search_condition:
        matched_sql = (
            "WITH matched AS (SELECT DISTINCT COALESCE(NULLIF(t.%s, ''), ?) AS name FROM tracks t WHERE %s) "
            % (group_column, search_condition)
        )
        select_sql = "SELECT g.* FROM %s g JOIN matched m ON m.name = g.name ORDER BY g.name COLLATE NOCASE %s" % (table, direction)
        args = [UNCLASSIFIED] + search_args
    else:
        matched_sql = ""
        select_sql = "SELECT * FROM %s ORDER BY name COLLATE NOCASE %s" % (table, direction)
        args = []
    with library_db_connect(config) as conn:
        if limit is None:
            return [dict(row) for row in conn.execute(matched_sql + select_sql, args)]
        try:
            page_limit = max(1, min(500, int(float(limit))))
        except (TypeError, ValueError):
            page_limit = 100
        try:
            page_offset = max(0, int(float(offset or 0)))
        except (TypeError, ValueError):
            page_offset = 0
        count_sql = matched_sql + ("SELECT COUNT(*) FROM matched" if search_condition else "SELECT COUNT(*) FROM %s" % table)
        count = conn.execute(count_sql, args).fetchone()[0]
        rows = conn.execute(matched_sql + select_sql + " LIMIT ? OFFSET ?", args + [page_limit, page_offset])
        return {"groups": [dict(row) for row in rows], "count": count, "limit": page_limit, "offset": page_offset, "paged": True}

def query_library_folders(config, parent="", root="", sort_dir="asc", limit=None, offset=0, search=""):
    if not os.path.isfile(library_db_path(config)):
        return {"folders": [], "count": 0, "limit": 0, "offset": 0, "paged": True} if limit is not None else []
    parent = str(parent or "")
    root = str(root or "")
    direction = "DESC" if str(sort_dir or "").lower() == "desc" else "ASC"
    if root:
        conditions = ["f.root = ?", "f.parent = ?"]
        args = [root, parent]
    else:
        conditions = ["f.parent = ?"]
        args = [parent]
    search_condition, search_args = _track_search_condition(search, "t")
    if search_condition:
        conditions.append(
            "EXISTS (SELECT 1 FROM tracks t WHERE t.root = f.root "
            "AND (t.folder = f.path OR t.folder LIKE f.path || '/%%') AND %s)" % search_condition
        )
        args.extend(search_args)
    where = " WHERE " + " AND ".join(conditions)
    with library_db_connect(config) as conn:
        if limit is None:
            return [dict(row) for row in conn.execute("SELECT f.* FROM folders f%s ORDER BY f.name COLLATE NOCASE %s" % (where, direction), args)]
        try:
            page_limit = max(1, min(500, int(float(limit))))
        except (TypeError, ValueError):
            page_limit = 100
        try:
            page_offset = max(0, int(float(offset or 0)))
        except (TypeError, ValueError):
            page_offset = 0
        count = conn.execute("SELECT COUNT(*) FROM folders f%s" % where, args).fetchone()[0]
        rows = conn.execute(
            "SELECT f.* FROM folders f%s ORDER BY f.name COLLATE NOCASE %s LIMIT ? OFFSET ?" % (where, direction),
            args + [page_limit, page_offset],
        )
        return {"folders": [dict(row) for row in rows], "count": count, "limit": page_limit, "offset": page_offset, "paged": True}

def query_library_root_folders(config, search=""):
    roots = normalize_library_paths(config)
    if not os.path.isfile(library_db_path(config)):
        return [{"path": root, "root": root, "parent": "", "name": os.path.basename(root.rstrip("/\\")) or root, "track_count": 0, "cover_track_id": ""} for root in roots]
    with library_db_connect(config) as conn:
        rows = {row["root"] or "": row for row in conn.execute("SELECT root, COUNT(*) AS track_count, MIN(id) AS cover_track_id FROM tracks GROUP BY root")}
        search_condition, search_args = _track_search_condition(search)
        matched_roots = None
        if search_condition:
            matched_roots = {row["root"] or "" for row in conn.execute("SELECT DISTINCT root FROM tracks WHERE " + search_condition, search_args)}
    result = []
    for root in roots:
        if matched_roots is not None and root not in matched_roots:
            continue
        row = rows.get(root, None)
        result.append({
            "path": root,
            "root": root,
            "parent": "",
            "name": os.path.basename(root.rstrip("/\\")) or root,
            "track_count": int(row["track_count"]) if row and row["track_count"] is not None else 0,
            "cover_track_id": row["cover_track_id"] if row else "",
        })
    return result

def query_library_items_by_ids(config, ids):
    values = [str(item_id).strip() for item_id in ids if str(item_id).strip()]
    if not values or not os.path.isfile(library_db_path(config)):
        return []
    placeholders = ",".join("?" for _ in values)
    with library_db_connect(config) as conn:
        rows = conn.execute("SELECT item_json FROM tracks WHERE id IN (%s)" % placeholders, values)
        items = []
        for row in rows:
            try:
                items.append(json.loads(row["item_json"]))
            except ValueError:
                pass
        return items

def query_library_item_by_id(config, item_id):
    value = str(item_id or "").strip()
    if not value:
        return None
    if os.path.isfile(library_db_path(config)):
        with library_db_connect(config) as conn:
            row = conn.execute("SELECT item_json FROM tracks WHERE id = ? LIMIT 1", (value,)).fetchone()
            if row:
                try:
                    return json.loads(row["item_json"])
                except ValueError:
                    return None
    return next((item for item in MUSIC_CACHE["items"] if str(item.get("id") or "") == value), None)

def query_library_item_location(config, item_id):
    item = query_library_item_by_id(config, item_id)
    raw_path = str((item or {}).get("path") or "").strip()
    if not raw_path:
        return None
    path = os.path.abspath(os.path.expanduser(raw_path))
    if not any(_path_under(path, root) for root in normalize_library_paths(config)):
        return None
    return {
        "id": str((item or {}).get("id") or item_id or ""),
        "path": path,
        "folder": os.path.dirname(path),
    }

def _first_param(params, key, default=""):
    if hasattr(params, "get"):
        value = params.get(key)
        if isinstance(value, list):
            return value[0] if value else default
        return value if value is not None else default
    return default

def _param_int(params, key, default=0):
    try:
        return int(float(_first_param(params, key, default)))
    except (TypeError, ValueError):
        return int(default or 0)

def library_cache_path(config):
    return os.path.join(config["cache_dir"], "library.json")

def library_db_path(config):
    return os.path.join(config["cache_dir"], "library.sqlite3")

@contextmanager
def library_db_connect(config):
    os.makedirs(config["cache_dir"], exist_ok=True)
    conn = sqlite3.connect(library_db_path(config), timeout=15)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=15000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        ensure_library_schema(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()

def ensure_library_schema(conn):
    # Older builds could leave a stale folders index behind after replacing
    # the folders table. Remove that orphan before SQLite parses CREATE INDEX.
    folder_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'folders'"
    ).fetchone()
    if folder_table is None:
        orphan_indexes = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'index' AND name = 'idx_folders_root_parent'"
        ).fetchall()
        if orphan_indexes:
            # DROP INDEX asks SQLite to resolve the missing table first and
            # can fail on databases produced by the old migration. Removing
            # only this stale sqlite_master row lets the schema be rebuilt.
            conn.execute("PRAGMA writable_schema = ON")
            conn.execute(
                "DELETE FROM sqlite_master "
                "WHERE type = 'index' AND name = 'idx_folders_root_parent'"
            )
            conn.execute("PRAGMA writable_schema = OFF")
            conn.execute("PRAGMA integrity_check")
    _migrate_legacy_tracks_columns(conn)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS library_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tracks (
            id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            root TEXT,
            folder TEXT,
            title TEXT,
            artist TEXT,
            album TEXT,
            track_no INTEGER NOT NULL DEFAULT 0,
            album_artist TEXT,
            composer TEXT,
            genre TEXT,
            format TEXT,
            mime TEXT,
            is_dsd INTEGER NOT NULL DEFAULT 0,
            duration REAL NOT NULL DEFAULT 0,
            size INTEGER NOT NULL DEFAULT 0,
            sample_rate INTEGER NOT NULL DEFAULT 0,
            bit_depth INTEGER NOT NULL DEFAULT 0,
            bitrate INTEGER NOT NULL DEFAULT 0,
            added INTEGER NOT NULL DEFAULT 0,
            added_ns INTEGER NOT NULL DEFAULT 0,
            modified INTEGER NOT NULL DEFAULT 0,
            modified_ns INTEGER NOT NULL DEFAULT 0,
            cue_path TEXT,
            cue_track INTEGER NOT NULL DEFAULT 0,
            cue_start REAL NOT NULL DEFAULT 0,
            cue_end REAL NOT NULL DEFAULT 0,
            metadata_version INTEGER NOT NULL DEFAULT 0,
            item_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tracks_path ON tracks(path);
        CREATE INDEX IF NOT EXISTS idx_tracks_folder ON tracks(folder);
        CREATE INDEX IF NOT EXISTS idx_tracks_album ON tracks(album);
        CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist);
        CREATE INDEX IF NOT EXISTS idx_tracks_composer ON tracks(composer);
        CREATE INDEX IF NOT EXISTS idx_tracks_genre ON tracks(genre);
        CREATE INDEX IF NOT EXISTS idx_tracks_added ON tracks(added_ns);
        CREATE INDEX IF NOT EXISTS idx_tracks_root ON tracks(root);
        CREATE INDEX IF NOT EXISTS idx_tracks_root_folder ON tracks(root, folder);
        CREATE INDEX IF NOT EXISTS idx_tracks_root_folder_track_no ON tracks(root, folder, track_no);
        CREATE INDEX IF NOT EXISTS idx_tracks_is_dsd ON tracks(is_dsd);
        CREATE INDEX IF NOT EXISTS idx_tracks_title_nocase ON tracks(title COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS idx_tracks_artist_nocase ON tracks(artist COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS idx_tracks_album_nocase ON tracks(album COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS idx_tracks_format_nocase ON tracks(format COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS idx_tracks_folder_nocase ON tracks(folder COLLATE NOCASE);
        CREATE TABLE IF NOT EXISTS albums (
            name TEXT PRIMARY KEY,
            artist TEXT,
            track_count INTEGER NOT NULL DEFAULT 0,
            cover_track_id TEXT
        );
        CREATE TABLE IF NOT EXISTS artists (
            name TEXT PRIMARY KEY,
            track_count INTEGER NOT NULL DEFAULT 0,
            cover_track_id TEXT
        );
        CREATE TABLE IF NOT EXISTS composers (
            name TEXT PRIMARY KEY,
            track_count INTEGER NOT NULL DEFAULT 0,
            cover_track_id TEXT
        );
        CREATE TABLE IF NOT EXISTS genres (
            name TEXT PRIMARY KEY,
            track_count INTEGER NOT NULL DEFAULT 0,
            cover_track_id TEXT
        );
        CREATE TABLE IF NOT EXISTS folders (
            path TEXT PRIMARY KEY,
            root TEXT,
            parent TEXT,
            name TEXT,
            track_count INTEGER NOT NULL DEFAULT 0,
            cover_track_id TEXT
        );
        CREATE TABLE IF NOT EXISTS covers (
            track_id TEXT PRIMARY KEY,
            source TEXT,
            folder_path TEXT,
            updated_at INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS cue_tracks (
            track_id TEXT PRIMARY KEY,
            cue_path TEXT NOT NULL,
            audio_path TEXT NOT NULL,
            track_no INTEGER NOT NULL DEFAULT 0,
            start REAL NOT NULL DEFAULT 0,
            end REAL NOT NULL DEFAULT 0
        );
        """
    )
    # New databases used to retain the legacy `folders(path)` primary key
    # because this migration was defined but never invoked. The composite key
    # is required when distinct music roots contain the same folder names.
    _migrate_tracks_columns(conn)


def _migrate_legacy_tracks_columns(conn):
    """Bring databases created by older fnAudio builds up to the current schema.

    SQLite only applies columns from CREATE TABLE when a table is new.  Older
    installs therefore need explicit ADD COLUMN migrations before an index can
    refer to a column introduced by a later release.
    """
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'tracks'"
    ).fetchone()
    if not exists:
        return
    existing = {
        str(row[1]).lower()
        for row in conn.execute("PRAGMA table_info(tracks)")
    }
    additions = [
        ("root", "TEXT"),
        ("folder", "TEXT"),
        ("title", "TEXT"),
        ("artist", "TEXT"),
        ("album", "TEXT"),
        ("track_no", "INTEGER NOT NULL DEFAULT 0"),
        ("album_artist", "TEXT"),
        ("composer", "TEXT"),
        ("genre", "TEXT"),
        ("format", "TEXT"),
        ("mime", "TEXT"),
        ("is_dsd", "INTEGER NOT NULL DEFAULT 0"),
        ("duration", "REAL NOT NULL DEFAULT 0"),
        ("size", "INTEGER NOT NULL DEFAULT 0"),
        ("sample_rate", "INTEGER NOT NULL DEFAULT 0"),
        ("bit_depth", "INTEGER NOT NULL DEFAULT 0"),
        ("bitrate", "INTEGER NOT NULL DEFAULT 0"),
        ("added", "INTEGER NOT NULL DEFAULT 0"),
        ("added_ns", "INTEGER NOT NULL DEFAULT 0"),
        ("modified", "INTEGER NOT NULL DEFAULT 0"),
        ("modified_ns", "INTEGER NOT NULL DEFAULT 0"),
        ("cue_path", "TEXT"),
        ("cue_track", "INTEGER NOT NULL DEFAULT 0"),
        ("cue_start", "REAL NOT NULL DEFAULT 0"),
        ("cue_end", "REAL NOT NULL DEFAULT 0"),
        ("metadata_version", "INTEGER NOT NULL DEFAULT 0"),
        ("item_json", "TEXT NOT NULL DEFAULT '{}'"),
    ]
    for name, definition in additions:
        if name not in existing:
            conn.execute("ALTER TABLE tracks ADD COLUMN %s %s" % (name, definition))
    return


def _migrate_tracks_columns(conn):
    track_columns = {row["name"] for row in conn.execute("PRAGMA table_info(tracks)")}
    if "track_no" not in track_columns:
        conn.execute("ALTER TABLE tracks ADD COLUMN track_no INTEGER NOT NULL DEFAULT 0")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_track_no ON tracks(track_no)")
    folder_columns = [dict(row) for row in conn.execute("PRAGMA table_info(folders)")]
    pk_columns = [row["name"] for row in folder_columns if row.get("pk")]
    if pk_columns == ["path"]:
        conn.execute("DROP TABLE IF EXISTS folders")
        conn.execute(
            """
            CREATE TABLE folders (
                path TEXT NOT NULL,
                root TEXT NOT NULL DEFAULT '',
                parent TEXT,
                name TEXT,
                track_count INTEGER NOT NULL DEFAULT 0,
                cover_track_id TEXT,
                PRIMARY KEY (root, path)
            )
            """
        )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_folders_root_parent ON folders(root, parent)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_folders_root_parent_name ON folders(root, parent, name)")
    group_version = conn.execute(
        "SELECT value FROM library_meta WHERE key = 'group_label_version'"
    ).fetchone()
    if not group_version or str(group_version["value"]) != GROUP_LABEL_VERSION:
        conn.execute("DELETE FROM albums")
        conn.execute("DELETE FROM artists")
        conn.execute("DELETE FROM composers")
        conn.execute("DELETE FROM genres")
        if conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]:
            _rebuild_group_table(conn, "albums", "album", "album_artist")
            _rebuild_simple_group(conn, "artists", "artist")
            _rebuild_simple_group(conn, "composers", "composer")
            _rebuild_simple_group(conn, "genres", "genre")
        conn.execute(
            "INSERT OR REPLACE INTO library_meta (key,value) VALUES (?,?)",
            ("group_label_version", GROUP_LABEL_VERSION),
        )

def save_items_to_sqlite(config, items, signature):
    with library_db_connect(config) as conn:
        roots = normalize_library_paths(config)
        normalized_items = []
        for item in items:
            path = str(item.get("path") or "")
            root = next((r for r in roots if path and _path_under(path, r)), "")
            canonical_item = dict(item)
            canonical_folder = relative_folder_for_path(canonical_item.get("cue_path") or path, root) if root else str(canonical_item.get("folder") or "")
            canonical_item["folder"] = canonical_folder
            canonical_item["library_root"] = library_root_label(root, config) if root else ""
            canonical_item["_index_root"] = root
            normalized_items.append(canonical_item)

        conn.execute("CREATE TEMP TABLE IF NOT EXISTS current_track_ids (id TEXT PRIMARY KEY)")
        conn.execute("DELETE FROM current_track_ids")
        conn.executemany("INSERT OR IGNORE INTO current_track_ids(id) VALUES (?)", [(str(item.get("id") or ""),) for item in normalized_items if item.get("id")])

        # Keep the old and new folder locations in a small temporary table.  A
        # changed track only invalidates its top-level folder subtree; the
        # remaining folder index can stay untouched.
        conn.execute("""
            CREATE TEMP TABLE IF NOT EXISTS current_track_meta (
                id TEXT PRIMARY KEY, root TEXT NOT NULL, folder TEXT NOT NULL,
                album TEXT NOT NULL, album_artist TEXT NOT NULL,
                artist TEXT NOT NULL, composer TEXT NOT NULL, genre TEXT NOT NULL
            )
        """)
        meta_columns = {row["name"] for row in conn.execute("PRAGMA temp.table_info(current_track_meta)")}
        for name in ("album", "album_artist", "artist", "composer", "genre"):
            if name not in meta_columns:
                conn.execute("ALTER TABLE current_track_meta ADD COLUMN %s TEXT NOT NULL DEFAULT ''" % name)
        conn.execute("DELETE FROM current_track_meta")
        conn.executemany(
            """INSERT OR REPLACE INTO current_track_meta(
                id,root,folder,album,album_artist,artist,composer,genre
            ) VALUES (?,?,?,?,?,?,?,?)""",
            [(str(item.get("id") or ""), str(item.get("_index_root") or ""), str(item.get("folder") or ""),
              str(item.get("album") or ""), str(item.get("album_artist") or ""),
              str(item.get("artist") or ""), str(item.get("composer") or ""), str(item.get("genre") or ""))
             for item in normalized_items if item.get("id")],
        )
        conn.execute("CREATE TEMP TABLE IF NOT EXISTS affected_folder_roots (root TEXT NOT NULL, folder TEXT NOT NULL, PRIMARY KEY(root, folder))")
        conn.execute("DELETE FROM affected_folder_roots")
        conn.execute("""
            INSERT OR IGNORE INTO affected_folder_roots(root, folder)
            SELECT old.root, old.folder
            FROM tracks old
            LEFT JOIN current_track_meta current ON current.id = old.id
            WHERE current.id IS NULL
              AND COALESCE(old.folder, '') <> ''
        """)
        conn.execute("""
            INSERT OR IGNORE INTO affected_folder_roots(root, folder)
            SELECT old.root, old.folder
            FROM tracks old
            JOIN current_track_meta current ON current.id = old.id
            WHERE COALESCE(old.root, '') <> COALESCE(current.root, '')
               OR COALESCE(old.folder, '') <> COALESCE(current.folder, '')
        """)
        conn.execute("""
            INSERT OR IGNORE INTO affected_folder_roots(root, folder)
            SELECT current.root, current.folder
            FROM current_track_meta current
            LEFT JOIN tracks old ON old.id = current.id
            WHERE COALESCE(current.folder, '') <> ''
              AND (old.id IS NULL
               OR COALESCE(old.root, '') <> COALESCE(current.root, '')
               OR COALESCE(old.folder, '') <> COALESCE(current.folder, ''))
        """)
        # Capture old group labels before the upsert replaces the old row.
        _refresh_group_tables_for_changes(conn)
        conn.execute("DELETE FROM tracks WHERE id NOT IN (SELECT id FROM current_track_ids)")
        conn.execute("DELETE FROM covers WHERE track_id NOT IN (SELECT id FROM current_track_ids)")
        conn.execute("DELETE FROM cue_tracks WHERE track_id NOT IN (SELECT id FROM current_track_ids)")
        for item in normalized_items:
            path = str(item.get("path") or "")
            root = str(item.get("_index_root") or "")
            canonical_item = dict(item)
            canonical_item.pop("_index_root", None)
            canonical_folder = str(canonical_item.get("folder") or "")
            row = (
                canonical_item.get("id", ""),
                path,
                root,
                canonical_folder,
                canonical_item.get("title", ""),
                canonical_item.get("artist", ""),
                canonical_item.get("album", ""),
                safe_int(canonical_item.get("track_no")),
                canonical_item.get("album_artist", ""),
                canonical_item.get("composer", ""),
                canonical_item.get("genre", ""),
                canonical_item.get("format", ""),
                canonical_item.get("mime", ""),
                1 if canonical_item.get("is_dsd") else 0,
                safe_float(canonical_item.get("duration")),
                safe_int(canonical_item.get("size")),
                safe_int(canonical_item.get("sample_rate")),
                safe_int(canonical_item.get("bit_depth")),
                safe_int(canonical_item.get("bitrate")),
                safe_int(canonical_item.get("added")),
                safe_int(canonical_item.get("added_ns")),
                safe_int(canonical_item.get("modified")),
                safe_int(canonical_item.get("modified_ns")),
                canonical_item.get("cue_path", ""),
                1 if canonical_item.get("cue_track") else 0,
                safe_float(canonical_item.get("cue_start")),
                safe_float(canonical_item.get("cue_end")),
                safe_int(canonical_item.get("metadata_version")),
                json.dumps(canonical_item, ensure_ascii=False),
            )
            conn.execute(
                """
                INSERT INTO tracks (
                    id,path,root,folder,title,artist,album,track_no,album_artist,composer,genre,format,mime,is_dsd,
                    duration,size,sample_rate,bit_depth,bitrate,added,added_ns,modified,modified_ns,
                    cue_path,cue_track,cue_start,cue_end,metadata_version,item_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    path=excluded.path, root=excluded.root, folder=excluded.folder, title=excluded.title,
                    artist=excluded.artist, album=excluded.album, track_no=excluded.track_no,
                    album_artist=excluded.album_artist, composer=excluded.composer, genre=excluded.genre,
                    format=excluded.format, mime=excluded.mime, is_dsd=excluded.is_dsd, duration=excluded.duration,
                    size=excluded.size, sample_rate=excluded.sample_rate, bit_depth=excluded.bit_depth,
                    bitrate=excluded.bitrate, added=excluded.added, added_ns=excluded.added_ns,
                    modified=excluded.modified, modified_ns=excluded.modified_ns, cue_path=excluded.cue_path,
                    cue_track=excluded.cue_track, cue_start=excluded.cue_start, cue_end=excluded.cue_end,
                    metadata_version=excluded.metadata_version, item_json=excluded.item_json
                WHERE tracks.item_json <> excluded.item_json
                """,
                row,
            )
            if canonical_item.get("cue_track"):
                conn.execute(
                    "INSERT OR REPLACE INTO cue_tracks (track_id,cue_path,audio_path,track_no,start,end) VALUES (?,?,?,?,?,?)",
                    (canonical_item.get("id", ""), canonical_item.get("cue_path", ""), path, safe_int(canonical_item.get("track_no")), safe_float(canonical_item.get("cue_start")), safe_float(canonical_item.get("cue_end"))),
                )
            conn.execute(
                "INSERT OR REPLACE INTO covers (track_id,source,folder_path,updated_at) VALUES (?,?,?,?)",
                (canonical_item.get("id", ""), "indexed", os.path.dirname(path), int(time.time())),
            )
        _refresh_group_tables_for_changes(conn, collect=False)
        _rebuild_folders_for_changes(conn)
        conn.execute("INSERT OR REPLACE INTO library_meta (key,value) VALUES (?,?)", ("library_path", display_library_path(config)))
        conn.execute("INSERT OR REPLACE INTO library_meta (key,value) VALUES (?,?)", ("signature", signature))
        conn.execute("INSERT OR REPLACE INTO library_meta (key,value) VALUES (?,?)", ("metadata_version", str(METADATA_VERSION)))
        conn.execute("INSERT OR REPLACE INTO library_meta (key,value) VALUES (?,?)", ("saved_at", str(int(time.time()))))

def load_items_from_sqlite(config):
    if not os.path.isfile(library_db_path(config)):
        return None
    with library_db_connect(config) as conn:
        meta = {row["key"]: row["value"] for row in conn.execute("SELECT key,value FROM library_meta")}
        if meta.get("library_path") != display_library_path(config):
            return None
        if str(meta.get("metadata_version") or "") != str(METADATA_VERSION):
            return None
        items = []
        for row in conn.execute("SELECT item_json FROM tracks ORDER BY artist COLLATE NOCASE, album COLLATE NOCASE, title COLLATE NOCASE"):
            try:
                items.append(json.loads(row["item_json"]))
            except ValueError:
                pass
        return {"items": items, "signature": meta.get("signature", "")}

def library_summary_from_sqlite(config):
    if not os.path.isfile(library_db_path(config)):
        return {}
    try:
        with library_db_connect(config) as conn:
            meta = {row["key"]: row["value"] for row in conn.execute("SELECT key,value FROM library_meta")}
            if meta.get("library_path") != display_library_path(config):
                return {}
            if str(meta.get("metadata_version") or "") != str(METADATA_VERSION):
                return {}
            row = conn.execute("SELECT COUNT(*) AS count, SUM(CASE WHEN is_dsd = 1 THEN 1 ELSE 0 END) AS dsd_count FROM tracks").fetchone()
            return {
                "count": int(row["count"] or 0) if row else 0,
                "dsd_count": int(row["dsd_count"] or 0) if row else 0,
                "signature": meta.get("signature", ""),
            }
    except Exception:
        return {}

def _rebuild_group_table(conn, table, column, artist_column):
    conn.execute(
        f"""
        INSERT OR REPLACE INTO {table} (name, artist, track_count, cover_track_id)
        SELECT COALESCE(NULLIF({column}, ''), ?),
               COALESCE(NULLIF(MIN(NULLIF({artist_column}, '')), ''), NULLIF(MIN(NULLIF(artist, '')), ''), ?),
               COUNT(*), MIN(id)
        FROM tracks GROUP BY COALESCE(NULLIF({column}, ''), ?)
        """,
        (UNCLASSIFIED, UNCLASSIFIED, UNCLASSIFIED),
    )

def _rebuild_simple_group(conn, table, column):
    conn.execute(
        f"""
        INSERT OR REPLACE INTO {table} (name, track_count, cover_track_id)
        SELECT COALESCE(NULLIF({column}, ''), ?), COUNT(*), MIN(id)
        FROM tracks GROUP BY COALESCE(NULLIF({column}, ''), ?)
        """,
        (UNCLASSIFIED, UNCLASSIFIED),
    )


def _refresh_group_tables_for_changes(conn, collect=True):
    """Refresh only group labels whose tracks were added, removed, or edited."""
    if collect:
        conn.execute("""
            CREATE TEMP TABLE IF NOT EXISTS affected_group_labels (
                table_name TEXT NOT NULL, name TEXT NOT NULL,
                PRIMARY KEY(table_name, name)
            )
        """)
        conn.execute("DELETE FROM affected_group_labels")
        specs = (
            ("albums", "album", "album_artist", "album", "album_artist"),
            ("artists", "artist", None, "artist", "artist"),
            ("composers", "composer", None, "composer", "composer"),
            ("genres", "genre", None, "genre", "genre"),
        )
        for table, old_column, old_artist, new_column, new_artist in specs:
            old_label = "COALESCE(NULLIF(old.%s, ''), ?)" % old_column
            new_label = "COALESCE(NULLIF(current.%s, ''), ?)" % new_column
            changed = "COALESCE(old.%s, '') <> COALESCE(current.%s, '')" % (old_column, new_column)
            if old_artist:
                changed += " OR COALESCE(old.%s, '') <> COALESCE(current.%s, '')" % (old_artist, new_artist)
            conn.execute(
                """
                INSERT OR IGNORE INTO affected_group_labels(table_name, name)
                SELECT ?, %s
                FROM tracks old LEFT JOIN current_track_meta current ON current.id = old.id
                WHERE current.id IS NULL OR (%s)
                """ % (old_label, changed),
                (table, UNCLASSIFIED),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO affected_group_labels(table_name, name)
                SELECT ?, %s
                FROM current_track_meta current LEFT JOIN tracks old ON old.id = current.id
                WHERE old.id IS NULL OR (%s)
                """ % (new_label, changed),
                (table, UNCLASSIFIED),
            )
    for table, column, artist_column in (
        ("albums", "album", "album_artist"),
        ("artists", "artist", None),
        ("composers", "composer", None),
        ("genres", "genre", None),
    ):
        labels = [row["name"] for row in conn.execute(
            "SELECT name FROM affected_group_labels WHERE table_name = ?", (table,)
        )]
        if not labels:
            continue
        conn.executemany("DELETE FROM %s WHERE name = ?" % table, [(label,) for label in labels])
        for label in labels:
            if artist_column:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO albums(name, artist, track_count, cover_track_id)
                    SELECT ?,
                           COALESCE(NULLIF(MIN(NULLIF(album_artist, '')), ''), NULLIF(MIN(NULLIF(artist, '')), ''), ?),
                           COUNT(*), MIN(id)
                    FROM tracks WHERE COALESCE(NULLIF(album, ''), ?) = ?
                    HAVING COUNT(*) > 0
                    """,
                    (label, UNCLASSIFIED, UNCLASSIFIED, label),
                )
            else:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO %s(name, track_count, cover_track_id)
                    SELECT ?, COUNT(*), MIN(id)
                    FROM tracks WHERE COALESCE(NULLIF(%s, ''), ?) = ?
                    HAVING COUNT(*) > 0
                    """ % (table, column),
                    (label, UNCLASSIFIED, label),
                )

def _rebuild_folders(conn):
    folders = {}
    for row in conn.execute("SELECT id, folder, root FROM tracks WHERE COALESCE(folder, '') <> '' ORDER BY folder COLLATE NOCASE, id"):
        root = row["root"] or ""
        parts = [part for part in (row["folder"] or "").split("/") if part]
        for index in range(1, len(parts) + 1):
            folder = "/".join(parts[:index])
            parent = "/".join(parts[:index - 1])
            key = (root, folder)
            current = folders.setdefault(key, {"root": root, "path": folder, "parent": parent, "name": parts[index - 1], "track_count": 0, "cover_track_id": row["id"]})
            current["track_count"] += 1
            if not current.get("cover_track_id"):
                current["cover_track_id"] = row["id"]
    for row in folders.values():
        conn.execute(
            "INSERT OR REPLACE INTO folders (path, root, parent, name, track_count, cover_track_id) VALUES (?,?,?,?,?,?)",
            (row["path"], row["root"], row["parent"], row["name"], row["track_count"], row["cover_track_id"]),
        )


def _rebuild_folders_for_changes(conn):
    """Refresh only folder trees touched by added, removed, or moved tracks."""
    affected = set()
    for row in conn.execute("SELECT root, folder FROM affected_folder_roots"):
        folder = str(row["folder"] or "").strip("/")
        if folder:
            # Rebuilding the first folder below a library root also refreshes
            # every descendant and keeps all ancestor counts consistent.
            affected.add((str(row["root"] or ""), folder.split("/", 1)[0]))
    for root, top_folder in affected:
        escaped = top_folder.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        prefix = escaped + "/%"
        conn.execute(
            "DELETE FROM folders WHERE root = ? AND (path = ? OR path LIKE ? ESCAPE '\\')",
            (root, top_folder, prefix),
        )
        folders = {}
        for row in conn.execute(
            """
            SELECT id, folder FROM tracks
            WHERE root = ? AND (folder = ? OR folder LIKE ? ESCAPE '\\')
            ORDER BY folder COLLATE NOCASE, id
            """,
            (root, top_folder, prefix),
        ):
            parts = [part for part in (row["folder"] or "").split("/") if part]
            for index in range(1, len(parts) + 1):
                folder = "/".join(parts[:index])
                parent = "/".join(parts[:index - 1])
                key = (root, folder)
                current = folders.setdefault(
                    key,
                    {"root": root, "path": folder, "parent": parent,
                     "name": parts[index - 1], "track_count": 0,
                     "cover_track_id": row["id"]},
                )
                current["track_count"] += 1
        for row in folders.values():
            conn.execute(
                "INSERT OR REPLACE INTO folders (path, root, parent, name, track_count, cover_track_id) VALUES (?,?,?,?,?,?)",
                (row["path"], row["root"], row["parent"], row["name"], row["track_count"], row["cover_track_id"]),
            )

def _path_under(path, root):
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(root)]) == os.path.abspath(root)
    except ValueError:
        return False

def load_library_cache(config):
    summary = library_summary_from_sqlite(config)
    if summary:
        MUSIC_CACHE["items"] = []
        MUSIC_CACHE["stamp"] = time.time()
        FS_CACHE["signature"] = summary.get("signature", "")
        return
    try:
        with open(library_cache_path(config), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("library_path") == display_library_path(config):
            MUSIC_CACHE["items"] = data.get("items", [])
            MUSIC_CACHE["stamp"] = time.time()
            FS_CACHE["signature"] = data.get("signature", "")
            save_items_to_sqlite(config, MUSIC_CACHE["items"], FS_CACHE["signature"])
    except (OSError, ValueError):
        pass

def save_library_cache(config):
    try:
        os.makedirs(config["cache_dir"], exist_ok=True)
        save_items_to_sqlite(config, MUSIC_CACHE["items"], FS_CACHE["signature"])
        # SQLite is the authoritative index. Keep the legacy JSON fallback
        # useful for smaller libraries without serializing a large library a
        # second time after every scan.
        cached_items = MUSIC_CACHE["items"] if len(MUSIC_CACHE["items"]) <= LIBRARY_JSON_CACHE_LIMIT else []
        payload = {
            "library_path": display_library_path(config),
            "signature": FS_CACHE["signature"],
            "items": cached_items,
            "sqlite": True,
        }
        with open(library_cache_path(config), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
    except OSError:
        pass

def watch_library(config):
    while True:
        try:
            refresh_library_if_changed(config)
            cleanup_transcode_cache_if_due(config)
        except Exception:
            pass
        time.sleep(180)

def find_ffprobe(config):
    configured = config.get("ffprobe_path")
    ffmpeg = find_ffmpeg(config)
    candidates = [
        configured,
        ffmpeg.replace("ffmpeg.exe", "ffprobe.exe") if ffmpeg.endswith("ffmpeg.exe") else "",
        ffmpeg.replace("ffmpeg", "ffprobe") if ffmpeg else "",
        "/usr/trim/lib/mediasrv/bin/ffprobe",
        "/usr/trim/bin/ffprobe",
        "/usr/local/bin/ffprobe",
        "/usr/bin/ffprobe",
        shutil.which("ffprobe"),
        shutil.which("ffprobe.exe"),
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    return ""

def read_audio_info(path, config=None):
    ffprobe = find_ffprobe(config or {})
    if not ffprobe:
        return {}
    command = [
        ffprobe,
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=sample_rate,bits_per_raw_sample,bits_per_sample,bit_rate",
        "-of", "json",
        path,
    ]
    env = os.environ.copy()
    if "/usr/trim/lib/mediasrv/bin" in ffprobe:
        env["LD_LIBRARY_PATH"] = "/usr/trim/lib/mediasrv/lib:" + env.get("LD_LIBRARY_PATH", "")
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20, env=env)
        data = json.loads(result.stdout.decode("utf-8", "ignore") or "{}")
        stream = (data.get("streams") or [{}])[0]
    except Exception:
        return {}
    sample_rate = int(stream.get("sample_rate") or 0)
    bit_depth = int(stream.get("bits_per_raw_sample") or stream.get("bits_per_sample") or 0)
    bit_rate = int(stream.get("bit_rate") or 0)
    return {
        "sample_rate": sample_rate,
        "bit_depth": bit_depth,
        "bit_rate": bit_rate,
    }

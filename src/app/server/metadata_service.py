from __future__ import annotations

import base64
import gzip
import hashlib
import json
import mimetypes
import os
import re
import sqlite3
import subprocess
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from version import APP_USER_AGENT
from contextlib import contextmanager

from library import find_ffprobe, id3_frame_size, id3_tag, library_db_path, parse_track_number, read_cover, read_id3_cover
from resource_limits import ResourceLimitError, bounded_int, disk_has_reserve
from file_permissions import preserve_owner_and_mode, secure_directory, secure_file, secure_sqlite_files
from transcode import find_ffmpeg
from audio_fingerprint import capability as fingerprint_capability, fingerprint as audio_fingerprint


POSITIVE_TTL = 30 * 24 * 60 * 60
NEGATIVE_TTL = 6 * 60 * 60
DEFAULT_ORPHAN_GRACE = 7 * 24 * 60 * 60
METADATA_CACHE_VERSION = "3"
TAG_WRITE_BACKFILL_VERSION = "1"
MAX_ARTWORK_BYTES = 8 * 1024 * 1024
TAG_WRITABLE_EXTENSIONS = {".mp3", ".flac", ".m4a", ".mp4", ".ape", ".wav", ".dsf"}
RUNNING_JOB_STALE_SECONDS = 15 * 60
PLACEHOLDER_NAMES = {
    "", "未分类", "未知专辑", "未知歌手", "未知艺术家", "未知作曲者",
    "unknown album", "unknown artist", "unknown composer",
}

# A match must be strong enough to distinguish a recording from remasters,
# covers and same-name tracks before it can be written back without review.
AUTO_TRACK_MATCH_CONFIDENCE = 0.90
AUTO_TRACK_MATCH_MARGIN = 0.08
TRACK_METADATA_FIELDS = (
    "title", "artist", "album", "album_artist", "composer", "genre",
    "date", "track_no", "disc_no",
)

_ID3_TEXT_FRAMES = {
    "title": "TIT2", "artist": "TPE1", "album": "TALB", "album_artist": "TPE2",
    "composer": "TCOM", "genre": "TCON", "track_no": "TRCK", "date": "TDRC",
}
_ID3_MANAGED_FRAMES = frozenset(_ID3_TEXT_FRAMES.values()) | {"USLT", "SYLT", "APIC"}
_APE_MANAGED_KEYS = frozenset({
    "title", "artist", "album", "album artist", "composer", "genre", "year", "date", "track",
    "lyrics", "cover art (front)",
})


def _id3_syncsafe(value):
    value = max(0, int(value or 0))
    return bytes(((value >> 21) & 0x7F, (value >> 14) & 0x7F, (value >> 7) & 0x7F, value & 0x7F))


def _id3_frame(frame_id, payload):
    return str(frame_id).encode("ascii") + len(payload).to_bytes(4, "big") + b"\x00\x00" + payload


def _id3_text_frame(frame_id, value):
    return _id3_frame(frame_id, b"\x03" + str(value).encode("utf-8"))


def _id3_uslt_frame(value):
    return _id3_frame("USLT", b"\x03eng\x00" + str(value).encode("utf-8"))


def _id3_apic_frame(mime, body):
    return _id3_frame("APIC", b"\x03" + str(mime or "image/jpeg").encode("ascii", "ignore") + b"\x00\x03\x00" + body)


def _preserved_id3_frames(path, replaced_frames=None):
    header, payload = id3_tag(path)
    if not header or not payload:
        return []
    major = int(header[3] or 3)
    offset = 0
    frames = []
    while offset + 10 <= len(payload):
        frame_id = payload[offset:offset + 4].decode("latin1", "ignore")
        size = id3_frame_size(payload, offset, major)
        if not frame_id.strip("\x00") or size <= 0 or offset + 10 + size > len(payload):
            break
        if frame_id not in set(replaced_frames or _ID3_MANAGED_FRAMES):
            frames.append(_id3_frame(frame_id, payload[offset + 10:offset + 10 + size]))
        offset += 10 + size
    return frames


def _write_dsf_tags(source, temporary, data):
    """Replace only DSF's trailing ID3v2 block, never its DSD payload."""
    with open(source, "rb") as handle:
        original = handle.read()
    if len(original) < 28 or original[:4] != b"DSD ":
        raise RuntimeError("invalid DSF header")
    metadata_offset = int.from_bytes(original[20:28], "little")
    if metadata_offset < 28 or metadata_offset > len(original):
        raise RuntimeError("invalid DSF metadata offset")
    replaced = set()
    for key, frame_id in _ID3_TEXT_FRAMES.items():
        if str(data.get(key) or "").replace("\x00", "").strip():
            replaced.add(frame_id)
    if str(data.get("lyrics") or "").replace("\x00", "").strip():
        replaced.add("USLT")
    if data.get("artwork_path"):
        replaced.add("APIC")
    frames = _preserved_id3_frames(source, replaced)
    for key, frame_id in _ID3_TEXT_FRAMES.items():
        value = str(data.get(key) or "").replace("\x00", "").strip()
        if value:
            frames.append(_id3_text_frame(frame_id, value))
    lyrics = str(data.get("lyrics") or "").replace("\x00", "").strip()
    if lyrics:
        frames.append(_id3_uslt_frame(lyrics))
    cover_mime, cover_body = read_id3_cover(source)
    if data.get("artwork_path"):
        with open(data["artwork_path"], "rb") as handle:
            cover_body = handle.read()
        cover_mime = data.get("artwork_mime") or "image/jpeg"
    if cover_body:
        frames.append(_id3_apic_frame(cover_mime, cover_body))
    tag_payload = b"".join(frames)
    tag = b"ID3\x03\x00\x00" + _id3_syncsafe(len(tag_payload)) + tag_payload
    output = bytearray(original[:metadata_offset]) + tag
    output[12:20] = len(output).to_bytes(8, "little")
    with open(temporary, "wb") as handle:
        handle.write(output)


def _write_wav_tags(source, temporary, data):
    """Store managed metadata in a RIFF ID3 chunk without remuxing WAV audio."""
    replaced = set()
    for key, frame_id in _ID3_TEXT_FRAMES.items():
        if str(data.get(key) or "").replace("\x00", "").strip():
            replaced.add(frame_id)
    if str(data.get("lyrics") or "").replace("\x00", "").strip():
        replaced.add("USLT")
    if data.get("artwork_path"):
        replaced.add("APIC")
    frames = _preserved_id3_frames(source, replaced)
    for key, frame_id in _ID3_TEXT_FRAMES.items():
        value = str(data.get(key) or "").replace("\x00", "").strip()
        if value:
            frames.append(_id3_text_frame(frame_id, value))
    lyrics = str(data.get("lyrics") or "").replace("\x00", "").strip()
    if lyrics:
        frames.append(_id3_uslt_frame(lyrics))
    cover_mime, cover_body = read_id3_cover(source)
    if data.get("artwork_path"):
        with open(data["artwork_path"], "rb") as handle:
            cover_body = handle.read()
        cover_mime = data.get("artwork_mime") or "image/jpeg"
    if cover_body:
        frames.append(_id3_apic_frame(cover_mime, cover_body))
    tag_payload = b"".join(frames)
    tag = b"ID3\x03\x00\x00" + _id3_syncsafe(len(tag_payload)) + tag_payload
    with open(source, "rb") as source_handle:
        header = source_handle.read(12)
        if header[:4] != b"RIFF" or header[8:12] != b"WAVE":
            raise RuntimeError("invalid WAV header")
        limit = os.fstat(source_handle.fileno()).st_size
        offset = 12
        with open(temporary, "wb") as target_handle:
            target_handle.write(header)
            while offset + 8 <= limit:
                source_handle.seek(offset)
                chunk_header = source_handle.read(8)
                chunk_id = chunk_header[:4]
                chunk_size = int.from_bytes(chunk_header[4:8], "little")
                total_size = 8 + chunk_size + (chunk_size & 1)
                if offset + total_size > limit:
                    raise RuntimeError("invalid WAV chunk")
                if chunk_id.lower() != b"id3 ":
                    target_handle.write(chunk_header)
                    source_handle.seek(offset + 8)
                    remaining = chunk_size + (chunk_size & 1)
                    while remaining:
                        block = source_handle.read(min(1024 * 1024, remaining))
                        if not block:
                            raise RuntimeError("truncated WAV chunk")
                        target_handle.write(block)
                        remaining -= len(block)
                offset += total_size
            target_handle.write(b"ID3 ")
            target_handle.write(len(tag).to_bytes(4, "little"))
            target_handle.write(tag)
            if len(tag) & 1:
                target_handle.write(b"\x00")
            size = target_handle.tell()
            if size > 0xFFFFFFFF + 8:
                raise RuntimeError("WAV exceeds RIFF size limit")
            target_handle.seek(4)
            target_handle.write((size - 8).to_bytes(4, "little"))


def _ape_existing_items(source):
    with open(source, "rb") as handle:
        body = handle.read()
    if len(body) < 32 or body[-32:-24] != b"APETAGEX":
        return body, []
    total = int.from_bytes(body[-20:-16], "little")
    count = int.from_bytes(body[-16:-12], "little")
    start = len(body) - total
    if total < 32 or start < 0 or count > 4096:
        return body, []
    offset = start
    items = []
    try:
        for _ in range(count):
            size = int.from_bytes(body[offset:offset + 4], "little")
            flags = body[offset + 4:offset + 8]
            key_end = body.index(b"\x00", offset + 8, min(len(body), offset + 8 + 1024))
            key = body[offset + 8:key_end].decode("utf-8", "replace")
            value_start = key_end + 1
            value_end = value_start + size
            if value_end > len(body) - 32:
                raise ValueError("APE item exceeds footer")
            items.append((key, flags, body[value_start:value_end]))
            offset = value_end
        if offset != len(body) - 32:
            raise ValueError("APE item size mismatch")
    except (ValueError, UnicodeError):
        return body, []
    return body[:start], items


def _ape_item(key, value, flags=b"\x00\x00\x00\x00"):
    encoded_key = str(key).encode("utf-8")
    return len(value).to_bytes(4, "little") + bytes(flags[:4]).ljust(4, b"\x00") + encoded_key + b"\x00" + value


def _write_ape_tags(source, temporary, data):
    audio, existing = _ape_existing_items(source)
    replacement = {}
    mapping = {
        "title": "Title", "artist": "Artist", "album": "Album", "album_artist": "Album Artist",
        "composer": "Composer", "genre": "Genre", "track_no": "Track", "date": "Year", "lyrics": "Lyrics",
    }
    for source_key, tag_key in mapping.items():
        value = str(data.get(source_key) or "").replace("\x00", "").strip()
        if value:
            replacement[tag_key.casefold()] = (tag_key, b"\x00\x00\x00\x00", value.encode("utf-8"))
    if data.get("artwork_path"):
        with open(data["artwork_path"], "rb") as handle:
            image = handle.read()
        if image:
            replacement["cover art (front)"] = ("Cover Art (Front)", b"\x02\x00\x00\x00", b"cover" + b"\x00" + image)
    # Only replace fields supplied by this job. In particular CUE entries
    # share a single source file: their artwork can be refreshed safely but
    # their per-track title/lyrics must not erase the source's existing Tags.
    items = [item for item in existing if item[0].casefold() not in replacement]
    items.extend(replacement.values())
    payload = b"".join(_ape_item(key, value, flags) for key, flags, value in items)
    footer = b"APETAGEX" + (2000).to_bytes(4, "little") + (len(payload) + 32).to_bytes(4, "little") + len(items).to_bytes(4, "little") + (0).to_bytes(4, "little") + b"\x00" * 8
    with open(temporary, "wb") as handle:
        handle.write(audio)
        handle.write(payload)
        handle.write(footer)


def normalize_text(value):
    text = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]+", "", text)


def contains_cjk(*values):
    text = " ".join(str(value or "") for value in values)
    return bool(re.search(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", text))


def entity_key(entity_type, name, artist=""):
    name_key = normalize_text(name)
    if entity_type == "album":
        return "%s|%s" % (name_key, normalize_text(artist))
    return name_key


def provider_score(candidate_name, wanted_name, candidate_artist="", wanted_artist=""):
    name = normalize_text(candidate_name)
    wanted = normalize_text(wanted_name)
    artist = normalize_text(candidate_artist)
    wanted_artist_key = normalize_text(wanted_artist)
    score = 0.0
    if name and name == wanted:
        score += 0.65
    elif name and wanted and (name in wanted or wanted in name):
        score += 0.35
    if wanted_artist_key:
        if artist == wanted_artist_key:
            score += 0.3
        elif artist and (artist in wanted_artist_key or wanted_artist_key in artist):
            score += 0.15
        else:
            score -= 0.35
    else:
        score += 0.1
    return min(score, 1.0)


def normalize_release_date(value):
    text = str(value or "").strip()
    try:
        timestamp = int(text)
        if timestamp > 100000000000:
            timestamp //= 1000
        if timestamp > 100000000:
            return time.strftime("%Y-%m-%d", time.localtime(timestamp))
    except (TypeError, ValueError, OverflowError, OSError):
        pass
    return text


def _artist_name(value):
    if isinstance(value, dict):
        return str(value.get("name") or "").strip()
    if isinstance(value, list) and value:
        return _artist_name(value[0])
    return str(value or "").strip()


class MetadataProviders:
    def __init__(self, config):
        self.config = config

    def _json(self, url, headers=None, data=None, timeout=10):
        request = urllib.request.Request(url, headers=headers or {}, data=data)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
            if response.headers.get("Content-Encoding", "").lower() == "gzip" or payload.startswith(b"\x1f\x8b"):
                payload = gzip.decompress(payload)
            return json.loads(payload.decode("utf-8", "ignore"))

    def netease_album(self, name, artist=""):
        query = "%s %s" % (name, artist) if artist else name
        url = "https://music.163.com/api/search/get/web?type=10&limit=20&s=" + urllib.parse.quote(query)
        data = self._json(url, {"User-Agent": "Mozilla/5.0", "Referer": "https://music.163.com/"})
        best = None
        best_score = 0
        for item in ((data.get("result") or {}).get("albums") or []):
            item_artist = _artist_name(item.get("artist") or item.get("artists") or [])
            score = provider_score(item.get("name"), name, item_artist, artist)
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.55:
            return None
        published = int(best.get("publishTime") or 0)
        release_date = time.strftime("%Y-%m-%d", time.localtime(published / 1000)) if published else ""
        return {
            "name": best.get("name") or name,
            "artist": _artist_name(best.get("artist") or best.get("artists") or []) or artist,
            "release_date": release_date,
            "image_url": best.get("picUrl") or "",
            "provider_id": str(best.get("id") or ""),
            "source": "netease",
            "confidence": best_score,
        }

    def netease_person(self, name):
        url = "https://music.163.com/api/search/get/web?type=100&limit=10&s=" + urllib.parse.quote(name)
        data = self._json(url, {"User-Agent": "Mozilla/5.0", "Referer": "https://music.163.com/"})
        best = None
        best_score = 0
        for item in ((data.get("result") or {}).get("artists") or []):
            score = provider_score(item.get("name"), name)
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.55:
            return None
        return {
            "name": best.get("name") or name,
            "artist": best.get("name") or name,
            "release_date": "",
            "image_url": best.get("picUrl") or best.get("img1v1Url") or "",
            "provider_id": str(best.get("id") or ""),
            "source": "netease",
            "confidence": best_score,
        }

    def _qq_songs(self, query, limit=20):
        url = "https://c.y.qq.com/soso/fcgi-bin/client_search_cp?" + urllib.parse.urlencode({
            "format": "json", "p": 1, "n": limit, "w": query,
        })
        data = self._json(url, {"User-Agent": "Mozilla/5.0", "Referer": "https://y.qq.com/"})
        return (((data.get("data") or {}).get("song") or {}).get("list") or [])

    def qq_album(self, name, artist=""):
        best = None
        best_score = 0
        for item in self._qq_songs("%s %s" % (name, artist)):
            singers = item.get("singer") or []
            item_artist = _artist_name(singers)
            score = provider_score(item.get("albumname"), name, item_artist, artist)
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.55:
            return None
        album_mid = str(best.get("albummid") or "")
        published = normalize_release_date(best.get("pubtime"))
        return {
            "name": best.get("albumname") or name,
            "artist": _artist_name(best.get("singer") or []) or artist,
            "release_date": published,
            "image_url": "https://y.gtimg.cn/music/photo_new/T002R500x500M000%s.jpg" % album_mid if album_mid else "",
            "provider_id": album_mid,
            "source": "qq",
            "confidence": best_score,
        }

    def qq_person(self, name):
        best = None
        best_score = 0
        for item in self._qq_songs(name):
            for singer in item.get("singer") or []:
                score = provider_score(singer.get("name"), name)
                if score > best_score:
                    best, best_score = singer, score
        if not best or best_score < 0.55:
            return None
        singer_mid = str(best.get("mid") or "")
        return {
            "name": best.get("name") or name,
            "artist": best.get("name") or name,
            "release_date": "",
            "image_url": "https://y.gtimg.cn/music/photo_new/T001R500x500M000%s.jpg" % singer_mid if singer_mid else "",
            "provider_id": singer_mid,
            "source": "qq",
            "confidence": best_score,
        }

    def musicbrainz_album(self, name, artist=""):
        query = 'releasegroup:"%s"' % name.replace('"', "")
        if artist:
            query += ' AND artist:"%s"' % artist.replace('"', "")
        url = "https://musicbrainz.org/ws/2/release-group/?" + urllib.parse.urlencode({"query": query, "fmt": "json", "limit": 10})
        data = self._json(url, {"User-Agent": "%s (local music server)" % APP_USER_AGENT})
        best = None
        best_score = 0
        for item in data.get("release-groups") or []:
            credits = item.get("artist-credit") or []
            item_artist = _artist_name((credits[0].get("artist") if credits and isinstance(credits[0], dict) else ""))
            score = provider_score(item.get("title"), name, item_artist, artist)
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.55:
            return None
        release_id = str(best.get("id") or "")
        return {
            "name": best.get("title") or name,
            "artist": _artist_name(((best.get("artist-credit") or [{}])[0].get("artist") or {})) or artist,
            "release_date": best.get("first-release-date") or "",
            "image_url": "https://coverartarchive.org/release-group/%s/front-500" % release_id if release_id else "",
            "provider_id": release_id,
            "source": "musicbrainz",
            "confidence": best_score,
        }

    def album(self, name, artist=""):
        if contains_cjk(name, artist):
            providers = (self.netease_album, self.qq_album, self.kugou_album, self.migu_album, self.joox_album, self.qianqian_album, self.musicbrainz_album)
        else:
            providers = (self.musicbrainz_album, self.netease_album, self.qq_album, self.kugou_album, self.migu_album, self.joox_album, self.qianqian_album)
        return self._first_match(providers, name, artist)

    def person(self, name):
        return self._first_match((self.netease_person, self.qq_person), name)

    def _first_match(self, providers, *args):
        for provider in providers:
            try:
                result = provider(*args)
                if result:
                    return result
            except (OSError, ValueError, TypeError, urllib.error.URLError, urllib.error.HTTPError):
                continue
        return None

    def netease_lyrics(self, track):
        query = "%s %s" % (track.get("title", ""), track.get("artist", ""))
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://music.163.com/"}
        data = self._json("https://music.163.com/api/search/get/web?type=1&limit=10&s=" + urllib.parse.quote(query), headers)
        best = None
        best_score = 0
        for item in ((data.get("result") or {}).get("songs") or []):
            item_artist = _artist_name(item.get("artists") or [])
            score = provider_score(item.get("name"), track.get("title"), item_artist, track.get("artist"))
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.55:
            return None
        lyric = self._json("https://music.163.com/api/song/lyric?lv=1&kv=1&tv=-1&id=%s" % best.get("id"), headers)
        text = ((lyric.get("lrc") or {}).get("lyric") or "").strip()
        return {"lyrics": text, "source": "网易云音乐", "provider_id": str(best.get("id") or ""), "confidence": best_score} if text else None

    def netease_track_artwork(self, track):
        query = "%s %s" % (track.get("title", ""), track.get("artist", ""))
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://music.163.com/"}
        data = self._json("https://music.163.com/api/search/get/web?type=1&limit=10&s=" + urllib.parse.quote(query), headers)
        best = None
        best_score = 0
        for item in ((data.get("result") or {}).get("songs") or []):
            score = provider_score(item.get("name"), track.get("title"), _artist_name(item.get("artists") or []), track.get("artist"))
            if score > best_score:
                best, best_score = item, score
        album = (best or {}).get("album") or {}
        image_url = str(album.get("picUrl") or "")
        if not best or best_score < 0.55 or not image_url:
            return None
        return {"image_url": image_url, "source": "netease", "provider_id": str(best.get("id") or ""), "confidence": best_score}

    def qq_track_artwork(self, track):
        best = None
        best_score = 0
        for item in self._qq_songs("%s %s" % (track.get("title", ""), track.get("artist", "")), 10):
            score = provider_score(item.get("songname"), track.get("title"), _artist_name(item.get("singer") or []), track.get("artist"))
            if score > best_score:
                best, best_score = item, score
        album_mid = str((best or {}).get("albummid") or "")
        if not best or best_score < 0.55 or not album_mid:
            return None
        return {"image_url": "https://y.gtimg.cn/music/photo_new/T002R500x500M000%s.jpg" % album_mid, "source": "qq", "provider_id": album_mid, "confidence": best_score}

    def qq_lyrics(self, track):
        best = None
        best_score = 0
        for item in self._qq_songs("%s %s" % (track.get("title", ""), track.get("artist", "")), 10):
            score = provider_score(item.get("songname"), track.get("title"), _artist_name(item.get("singer") or []), track.get("artist"))
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.55 or not best.get("songmid"):
            return None
        url = "https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg?format=json&nobase64=0&songmid=" + urllib.parse.quote(str(best.get("songmid")))
        data = self._json(url, {"User-Agent": "Mozilla/5.0", "Referer": "https://y.qq.com/"})
        encoded = data.get("lyric") or ""
        if not encoded:
            return None
        text = base64.b64decode(encoded).decode("utf-8", "ignore").strip()
        return {"lyrics": text, "source": "QQ音乐", "provider_id": str(best.get("songmid")), "confidence": best_score} if text else None

    def _kugou_songs(self, query, limit=10):
        params = {
            "keyword": query, "platform": "WebFilter", "format": "json", "page": "1",
            "pagesize": str(limit), "userid": "-1", "tag": "em", "filter": "2",
            "iscorrection": "1", "privilege_filter": "0", "_": str(int(time.time() * 1000)),
        }
        url = "http://songsearch.kugou.com/song_search_v2?" + urllib.parse.urlencode(params)
        data = self._json(url, {"User-Agent": "Mozilla/5.0", "Referer": "https://www.kugou.com/"})
        return ((data.get("data") or {}).get("lists") or [])

    def kugou_album(self, name, artist=""):
        best = None
        best_score = 0
        for item in self._kugou_songs("%s %s" % (name, artist)):
            score = provider_score(item.get("AlbumName"), name, item.get("SingerName"), artist)
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.55:
            return None
        cover = str(best.get("Image") or "")
        if not cover:
            cover = str(((best.get("trans_param") or {}).get("union_cover")) or "")
        cover = cover.replace("{size}", "500")
        return {
            "name": best.get("AlbumName") or name,
            "artist": best.get("SingerName") or artist,
            "release_date": str(best.get("PublishDate") or best.get("PublishTime") or ""),
            "image_url": cover,
            "provider_id": str(best.get("AlbumID") or best.get("MixSongID") or best.get("FileHash") or ""),
            "source": "kugou",
            "confidence": best_score,
        }

    def kugou_lyrics(self, track):
        best = None
        best_score = 0
        for item in self._kugou_songs("%s %s" % (track.get("title", ""), track.get("artist", ""))):
            score = provider_score(item.get("SongName"), track.get("title"), item.get("SingerName"), track.get("artist"))
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.55:
            return None
        song_hash = str(best.get("FileHash") or "").strip()
        if not song_hash:
            return None
        try:
            duration = max(0, int(best.get("Duration") or track.get("duration") or 0)) * 1000
        except (TypeError, ValueError):
            duration = 0
        search_url = "http://krcs.kugou.com/search?" + urllib.parse.urlencode({
            "ver": "1", "client": "mobi", "duration": str(duration), "hash": song_hash, "album_audio_id": "",
        })
        candidates = self._json(search_url, {"User-Agent": "Mozilla/5.0", "Referer": "https://www.kugou.com/"}).get("candidates") or []
        if not candidates:
            return None
        candidate = candidates[0]
        download_url = "http://lyrics.kugou.com/download?" + urllib.parse.urlencode({
            "ver": "1", "client": "pc", "id": str(candidate.get("id") or ""),
            "accesskey": str(candidate.get("accesskey") or ""), "fmt": "lrc", "charset": "utf8",
        })
        payload = self._json(download_url, {"User-Agent": "Mozilla/5.0", "Referer": "https://www.kugou.com/"})
        encoded = str(payload.get("content") or "")
        if not encoded:
            return None
        try:
            text = base64.b64decode(encoded).decode("utf-8", "ignore").strip()
        except (ValueError, TypeError):
            return None
        return {"lyrics": text, "source": "酷狗音乐", "provider_id": song_hash, "confidence": best_score} if text else None

    # The following adapters retain the go-music-dl provider sequence: search a
    # candidate, score it against the local file, then request its lyric/cover.
    def _migu_songs(self, query, limit=10):
        params = {
            "ua": "Android_migu", "version": "5.0.1", "text": query,
            "pageNo": "1", "pageSize": str(limit),
            "searchSwitch": '{"song":1,"album":0,"singer":0,"tagSong":0,"mvSong":0,"songlist":0,"bestShow":1}',
        }
        data = self._json(
            "http://pd.musicapp.migu.cn/MIGUM2.0/v1.0/content/search_all.do?" + urllib.parse.urlencode(params),
            {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X)", "Referer": "http://music.migu.cn/"},
        )
        return ((data.get("songResultData") or {}).get("result") or [])

    @staticmethod
    def _migu_artist(item):
        people = item.get("singers") or item.get("singerList") or item.get("artists") or []
        names = [str(person.get("name") or "").strip() for person in people if isinstance(person, dict)]
        return " / ".join(name for name in names if name) or str(item.get("singer") or "")

    @staticmethod
    def _migu_album_name(item):
        albums = item.get("albums") or []
        if albums and isinstance(albums[0], dict):
            return str(albums[0].get("name") or "").strip() or str(item.get("album") or "")
        return str(item.get("album") or "")

    @staticmethod
    def _migu_image(item):
        for image in list(item.get("imgItems") or []) + list(item.get("albumImgs") or []):
            value = str((image or {}).get("img") or "").strip()
            if value:
                return "https:" + value if value.startswith("//") else value
        return str(item.get("img1") or item.get("img2") or "").strip()

    def migu_album(self, name, artist=""):
        best = None
        best_score = 0
        for item in self._migu_songs("%s %s" % (name, artist)):
            score = provider_score(self._migu_album_name(item), name, self._migu_artist(item), artist)
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.55:
            return None
        return {
            "name": self._migu_album_name(best) or name,
            "artist": self._migu_artist(best) or artist,
            "release_date": str(best.get("publishDate") or ""),
            "image_url": self._migu_image(best),
            "provider_id": str(best.get("albumId") or ((best.get("albums") or [{}])[0].get("id") if best.get("albums") else "") or ""),
            "source": "migu",
            "confidence": best_score,
        }

    def migu_lyrics(self, track):
        best = None
        best_score = 0
        for item in self._migu_songs("%s %s" % (track.get("title", ""), track.get("artist", ""))):
            score = provider_score(item.get("name") or item.get("songName"), track.get("title"), self._migu_artist(item), track.get("artist"))
            if score > best_score:
                best, best_score = item, score
        content_id = str((best or {}).get("contentId") or "").strip()
        if not best or best_score < 0.55 or not content_id:
            return None
        url = "http://c.musicapp.migu.cn/MIGUM2.0/v1.0/content/resourceinfo.do?" + urllib.parse.urlencode({"resourceId": content_id, "resourceType": "2"})
        data = self._json(url, {"User-Agent": "Mozilla/5.0", "Referer": "http://music.migu.cn/"})
        resource = (data.get("resource") or [{}])[0]
        lyric_url = str(resource.get("lrcUrl") or resource.get("lyricUrl") or "").strip()
        if not lyric_url:
            return None
        lyric_url = lyric_url.replace("http://", "https://", 1)
        request = urllib.request.Request(lyric_url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://y.migu.cn/"})
        with urllib.request.urlopen(request, timeout=10) as response:
            text = response.read().decode("utf-8", "ignore").strip()
        return {"lyrics": text, "source": "migu", "provider_id": content_id, "confidence": best_score} if text else None

    def _joox_songs(self, query):
        url = "https://cache.api.joox.com/openjoox/v3/search?" + urllib.parse.urlencode({"country": "sg", "lang": "zh_cn", "keyword": query})
        data = self._json(url, {"User-Agent": "Mozilla/5.0", "X-Forwarded-For": "101.32.0.1"})
        songs = []
        for section in data.get("section_list") or []:
            for item in section.get("item_list") or []:
                for song in item.get("song") or []:
                    info = song.get("song_info") or {}
                    if info.get("id"):
                        songs.append(info)
        return songs

    def _joox_albums(self, query):
        url = "https://cache.api.joox.com/openjoox/v3/search?" + urllib.parse.urlencode({"country": "sg", "lang": "zh_cn", "keyword": query})
        data = self._json(url, {"User-Agent": "Mozilla/5.0", "X-Forwarded-For": "101.32.0.1"})
        albums = []
        for section in data.get("section_list") or []:
            if int(section.get("section_type") or 0) != 1:
                continue
            for item in section.get("item_list") or []:
                if int(item.get("type") or 0) == 2 and item.get("album"):
                    albums.append(item["album"])
        return albums

    @staticmethod
    def _joox_artist(item):
        return " / ".join(str(person.get("name") or "").strip() for person in item.get("artist_list") or [] if person.get("name"))

    @staticmethod
    def _joox_image(item):
        images = item.get("images") or []
        return next((str(image.get("url") or "") for image in images if image.get("url")), "")

    def joox_album(self, name, artist=""):
        best = None
        best_score = 0
        for item in self._joox_albums("%s %s" % (name, artist)):
            score = provider_score(item.get("name"), name, self._joox_artist(item), artist)
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.45:
            return None
        return {"name": best.get("name") or name, "artist": self._joox_artist(best) or artist,
                "release_date": str(best.get("publish_date") or ""), "image_url": self._joox_image(best),
                "provider_id": str(best.get("id") or ""), "source": "joox", "confidence": best_score}

    def joox_lyrics(self, track):
        best = None
        best_score = 0
        for item in self._joox_songs("%s %s" % (track.get("title", ""), track.get("artist", ""))):
            score = provider_score(item.get("name"), track.get("title"), self._joox_artist(item), track.get("artist"))
            if score > best_score:
                best, best_score = item, score
        song_id = str((best or {}).get("id") or "")
        if not best or best_score < 0.55 or not song_id:
            return None
        url = "https://api.joox.com/web-fcgi-bin/web_lyric?" + urllib.parse.urlencode({"musicid": song_id, "country": "sg", "lang": "zh_cn"})
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "X-Forwarded-For": "101.32.0.1"})
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = response.read().decode("utf-8", "ignore").strip()
        if payload.startswith("MusicJsonCallback(") and payload.endswith(")"):
            payload = payload[len("MusicJsonCallback("):-1]
        encoded = str(json.loads(payload).get("lyric") or "")
        text = base64.b64decode(encoded).decode("utf-8", "ignore").strip() if encoded else ""
        return {"lyrics": text, "source": "joox", "provider_id": song_id, "confidence": best_score} if text else None

    @staticmethod
    def _qianqian_params(values):
        values = dict(values)
        values["appid"] = "16073360"
        values["timestamp"] = str(int(time.time()))
        raw = "&".join("%s=%s" % (key, values[key]) for key in sorted(values)) + "0b50b02fd0d73a9c4c8c3a781c30845f"
        values["sign"] = hashlib.md5(raw.encode("utf-8")).hexdigest()
        return values

    def _qianqian_songs(self, query):
        params = self._qianqian_params({"word": query, "type": "1", "pageNo": "1", "pageSize": "10"})
        data = self._json("https://music.91q.com/v1/search?" + urllib.parse.urlencode(params), {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36", "Referer": "https://music.91q.com/player"})
        return ((data.get("data") or {}).get("typeTrack") or [])

    def _qianqian_albums(self, query):
        params = self._qianqian_params({"word": query, "type": "3", "pageNo": "1", "pageSize": "10"})
        data = self._json("https://music.91q.com/v1/search?" + urllib.parse.urlencode(params), {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36", "Referer": "https://music.91q.com/player"})
        return ((data.get("data") or {}).get("typeAlbum") or [])

    @staticmethod
    def _qianqian_artist(item):
        return " / ".join(str(person.get("name") or "").strip() for person in item.get("artist") or [] if person.get("name"))

    def qianqian_album(self, name, artist=""):
        best = None
        best_score = 0
        for item in self._qianqian_albums("%s %s" % (name, artist)):
            score = provider_score(item.get("title"), name, self._qianqian_artist(item), artist)
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.55:
            return None
        return {"name": best.get("title") or name, "artist": self._qianqian_artist(best) or artist,
                "release_date": str(best.get("releaseDate") or ""), "image_url": str(best.get("pic") or ""),
                "provider_id": str(best.get("albumAssetCode") or ""), "source": "qianqian", "confidence": best_score}

    def qianqian_lyrics(self, track):
        best = None
        best_score = 0
        for item in self._qianqian_songs("%s %s" % (track.get("title", ""), track.get("artist", ""))):
            score = provider_score(item.get("title"), track.get("title"), self._qianqian_artist(item), track.get("artist"))
            if score > best_score:
                best, best_score = item, score
        song_id = str((best or {}).get("TSID") or "")
        if not best or best_score < 0.55 or not song_id:
            return None
        params = self._qianqian_params({"TSID": song_id})
        data = self._json("https://music.91q.com/v1/song/info?" + urllib.parse.urlencode(params), {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36", "Referer": "https://music.91q.com/player"})
        details = data.get("data") or []
        lyric_url = str((details[0] if details else {}).get("lyric") or "")
        if not lyric_url:
            return None
        request = urllib.request.Request(lyric_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=10) as response:
            text = response.read().decode("utf-8", "ignore").strip()
        return {"lyrics": text, "source": "qianqian", "provider_id": song_id, "confidence": best_score} if text else None

    def lyrics(self, track):
        local = read_local_lyrics(track.get("path") or "", self.config)
        if local:
            return {"lyrics": local, "source": "本地歌词", "provider_id": "", "confidence": 1.0}
        for provider in (self.netease_lyrics, self.qq_lyrics, self.kugou_lyrics, self.migu_lyrics, self.joox_lyrics, self.qianqian_lyrics):
            try:
                result = provider(track)
                if result:
                    return result
            except (OSError, ValueError, TypeError, urllib.error.URLError, urllib.error.HTTPError):
                continue
        return None

    def track_artwork(self, track):
        return self._first_match((self.netease_track_artwork, self.qq_track_artwork), track)

    @staticmethod
    def _track_candidate(track, item, source, title, artist, album="", album_artist="", date="", genre="", track_no=0, image_url="", provider_id=""):
        score = provider_score(title, track.get("title"), artist, track.get("artist"))
        if track.get("album") and track.get("album") not in PLACEHOLDER_NAMES and album:
            score = min(1.0, score + (0.08 if str(album).casefold() == str(track.get("album")).casefold() else 0))
        try:
            local_duration = float(track.get("duration") or 0)
            remote_duration = float(item.get("interval") or item.get("Duration") or item.get("duration") or 0)
            if local_duration and remote_duration and abs(local_duration - remote_duration) <= 3:
                score = min(1.0, score + 0.04)
        except (TypeError, ValueError):
            pass
        return {
            "title": str(title or "").strip(), "artist": str(artist or "").strip(),
            "album": str(album or "").strip(), "album_artist": str(album_artist or artist or "").strip(),
            "date": normalize_release_date(date), "genre": str(genre or "").strip(),
            "track_no": parse_track_number(track_no), "disc_no": 0,
            "image_url": str(image_url or "").strip(), "provider_id": str(provider_id or "").strip(),
            "source": source, "confidence": round(score, 4),
        }

    def track_candidates(self, track):
        """Return scored, deduplicated recording candidates from existing providers.

        Provider calls deliberately reuse the same search APIs as lyrics/artwork.
        A provider failure is isolated so an outage never blocks the whole queue.
        """
        query = "%s %s" % (track.get("title", ""), track.get("artist", ""))
        candidates = []
        if fingerprint_capability(self.config).get("available"):
            try:
                sample = audio_fingerprint(track.get("path") or "", self.config)
                params = urllib.parse.urlencode({
                    "client": os.environ.get("FNAUDIO_ACOUSTID_CLIENT_KEY", ""),
                    "meta": "recordings+releasegroups",
                    "duration": sample["duration"],
                    "fingerprint": sample["fingerprint"],
                })
                response = self._json("https://api.acoustid.org/v2/lookup?" + params, {"User-Agent": APP_USER_AGENT})
                for result in response.get("results") or []:
                    recording = next(iter(result.get("recordings") or []), {})
                    title = recording.get("title") or ""
                    artists = _artist_name(recording.get("artists") or [])
                    releases = recording.get("releasegroups") or []
                    release = releases[0] if releases else {}
                    candidate = self._track_candidate(track, {"duration": sample["duration"]}, "acoustid", title, artists, release.get("title"), artists, release.get("date"), "", 0, "", recording.get("id"))
                    candidate["confidence"] = round(max(candidate["confidence"], min(0.98, 0.75 + 0.23 * float(result.get("score") or 0))), 4)
                    candidates.append(candidate)
            except (OSError, ValueError, TypeError, RuntimeError, urllib.error.URLError, urllib.error.HTTPError):
                pass
        adapters = (
            ("netease", lambda: ((self._json("https://music.163.com/api/search/get/web?type=1&limit=10&s=" + urllib.parse.quote(query), {"User-Agent": "Mozilla/5.0", "Referer": "https://music.163.com/"}).get("result") or {}).get("songs") or []),
             lambda item: self._track_candidate(track, item, "netease", item.get("name"), _artist_name(item.get("artists") or []), (item.get("album") or {}).get("name"), _artist_name((item.get("album") or {}).get("artists") or []), (item.get("album") or {}).get("publishTime"), "", item.get("no"), (item.get("album") or {}).get("picUrl"), item.get("id"))),
            ("qq", lambda: self._qq_songs(query, 10),
             lambda item: self._track_candidate(track, item, "qq", item.get("songname"), _artist_name(item.get("singer") or []), item.get("albumname"), _artist_name(item.get("singer") or []), item.get("pubtime"), item.get("genre"), item.get("songid"), "https://y.gtimg.cn/music/photo_new/T002R500x500M000%s.jpg" % item.get("albummid") if item.get("albummid") else "", item.get("songmid"))),
            ("kugou", lambda: self._kugou_songs(query, 10),
             lambda item: self._track_candidate(track, item, "kugou", item.get("SongName"), item.get("SingerName"), item.get("AlbumName"), item.get("SingerName"), item.get("PublishDate") or item.get("PublishTime"), item.get("Genre"), item.get("OriSongName"), str(item.get("Image") or "").replace("{size}", "500"), item.get("FileHash"))),
            ("migu", lambda: self._migu_songs(query, 10),
             lambda item: self._track_candidate(track, item, "migu", item.get("name") or item.get("songName"), self._migu_artist(item), self._migu_album_name(item), self._migu_artist(item), item.get("publishDate"), item.get("genre"), item.get("trackNo"), self._migu_image(item), item.get("contentId"))),
            ("joox", lambda: self._joox_songs(query),
             lambda item: self._track_candidate(track, item, "joox", item.get("name"), self._joox_artist(item), (item.get("album") or {}).get("name"), self._joox_artist(item), (item.get("album") or {}).get("publish_date"), item.get("genre"), item.get("track"), self._joox_image(item), item.get("id"))),
            ("qianqian", lambda: self._qianqian_songs(query),
             lambda item: self._track_candidate(track, item, "qianqian", item.get("title"), self._qianqian_artist(item), item.get("albumTitle") or item.get("album"), self._qianqian_artist(item), item.get("releaseDate"), item.get("genre"), item.get("trackNo"), item.get("pic"), item.get("TSID"))),
        )
        for _source, request, mapper in adapters:
            try:
                candidates.extend(mapper(item) for item in request())
            except (OSError, ValueError, TypeError, urllib.error.URLError, urllib.error.HTTPError):
                continue
        deduped = {}
        for candidate in candidates:
            if candidate["confidence"] < 0.55 or not candidate["title"]:
                continue
            key = "\x1f".join(candidate.get(field, "").casefold() for field in ("title", "artist", "album"))
            if not key or candidate["confidence"] > deduped.get(key, {"confidence": -1})["confidence"]:
                deduped[key] = candidate
        return sorted(deduped.values(), key=lambda candidate: candidate["confidence"], reverse=True)[:8]


def read_embedded_lyrics(path, config=None):
    ffprobe = find_ffprobe(config or {})
    if not ffprobe or not os.path.isfile(path):
        return ""
    command = [ffprobe, "-v", "error", "-show_entries", "format_tags:stream_tags", "-of", "json", path]
    env = os.environ.copy()
    if "/usr/trim/lib/mediasrv/bin" in ffprobe:
        env["LD_LIBRARY_PATH"] = "/usr/trim/lib/mediasrv/lib:" + env.get("LD_LIBRARY_PATH", "")
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15, env=env)
        data = json.loads(result.stdout.decode("utf-8", "ignore") or "{}")
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""
    tags = dict((data.get("format") or {}).get("tags") or {})
    for stream in data.get("streams") or []:
        tags.update(stream.get("tags") or {})
    for key, value in tags.items():
        normalized = str(key or "").casefold().replace("-", "_")
        if normalized in ("lyrics", "lyric", "unsyncedlyrics", "syncedlyrics", "uslt", "©lyr") or normalized.startswith("lyrics_"):
            text = str(value or "").strip()
            if text:
                return text
    return ""


def read_local_lyrics(path, config=None):
    embedded = read_embedded_lyrics(path, config)
    if embedded:
        return embedded
    base, _ = os.path.splitext(path)
    for candidate in (base + ".lrc", os.path.join(os.path.dirname(path), "lyrics.lrc")):
        try:
            with open(candidate, "rb") as fh:
                raw = fh.read()
        except OSError:
            continue
        for encoding in ("utf-8-sig", "utf-16", "gb18030"):
            try:
                return raw.decode(encoding).strip()
            except UnicodeError:
                continue
    return ""


class MetadataService:
    def __init__(self, config):
        self.config = config
        self.providers = MetadataProviders(config)
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.thread = None
        self.fetch_threads = []
        self.tag_thread = None
        self.priority_thread = None
        self.force_reconcile = False
        self.last_reconcile = 0
        self.library_signature = ""
        self.last_cleanup = 0
        self.last_error = ""
        self.active_job = ""
        self.last_tag_write_at = 0.0
        self.tag_written = 0
        self.tag_write_seconds = 0.0
        self.tag_write_started_at = 0.0
        self.current_track_id = ""
        self.dropped_jobs = 0
        self.lock = threading.RLock()

    @property
    def artwork_dir(self):
        return os.path.join(self.config.get("cache_dir") or ".", "metadata", "artwork")

    @contextmanager
    def _connect(self):
        path = library_db_path(self.config)
        secure_directory(os.path.dirname(path))
        conn = sqlite3.connect(path, timeout=20)
        try:
            secure_sqlite_files(path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            secure_sqlite_files(path)
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
            self._ensure_schema(conn)
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
            secure_sqlite_files(path)

    def _ensure_schema(self, conn):
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata_entities (
                entity_type TEXT NOT NULL,
                entity_key TEXT NOT NULL,
                name TEXT NOT NULL,
                artist TEXT NOT NULL DEFAULT '',
                release_date TEXT NOT NULL DEFAULT '',
                artwork_id TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                provider_id TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0,
                fetched_at INTEGER NOT NULL DEFAULT 0,
                expires_at INTEGER NOT NULL DEFAULT 0,
                orphaned_at INTEGER NOT NULL DEFAULT 0,
                raw_json TEXT NOT NULL DEFAULT '{}',
                PRIMARY KEY(entity_type, entity_key)
            );
            CREATE INDEX IF NOT EXISTS idx_metadata_entities_expiry ON metadata_entities(expires_at);
            CREATE TABLE IF NOT EXISTS metadata_tracks (
                track_id TEXT PRIMARY KEY,
                lyrics TEXT NOT NULL DEFAULT '',
                artwork_id TEXT NOT NULL DEFAULT '',
                lyrics_source TEXT NOT NULL DEFAULT '',
                provider_id TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0,
                fetched_at INTEGER NOT NULL DEFAULT 0,
                expires_at INTEGER NOT NULL DEFAULT 0,
                orphaned_at INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS metadata_track_matches (
                track_id TEXT PRIMARY KEY,
                fields_json TEXT NOT NULL DEFAULT '{}',
                source TEXT NOT NULL DEFAULT '',
                provider_id TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                fetched_at INTEGER NOT NULL DEFAULT 0,
                expires_at INTEGER NOT NULL DEFAULT 0,
                orphaned_at INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_metadata_track_matches_status ON metadata_track_matches(status,expires_at);
            CREATE TABLE IF NOT EXISTS metadata_assets (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                mime TEXT NOT NULL,
                size INTEGER NOT NULL DEFAULT 0,
                source_url TEXT NOT NULL DEFAULT '',
                fetched_at INTEGER NOT NULL DEFAULT 0,
                last_accessed INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_metadata_assets_source ON metadata_assets(source_url);
            CREATE TABLE IF NOT EXISTS metadata_jobs (
                job_key TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                entity_key TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 100,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt_at INTEGER NOT NULL DEFAULT 0,
                updated_at INTEGER NOT NULL DEFAULT 0,
                last_error TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_metadata_jobs_pending ON metadata_jobs(status,next_attempt_at,priority);
            CREATE TABLE IF NOT EXISTS metadata_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            );
            """
        )
        track_columns = {row["name"] for row in conn.execute("PRAGMA table_info(metadata_tracks)")}
        if "artwork_id" not in track_columns:
            conn.execute("ALTER TABLE metadata_tracks ADD COLUMN artwork_id TEXT NOT NULL DEFAULT ''")
        version = conn.execute("SELECT value FROM metadata_state WHERE key='cache_version'").fetchone()
        if not version or str(version["value"] or "") != METADATA_CACHE_VERSION:
            conn.execute("UPDATE metadata_entities SET expires_at=0")
            conn.execute("UPDATE metadata_tracks SET expires_at=0")
            conn.execute("UPDATE metadata_jobs SET status='pending',next_attempt_at=0 WHERE status<>'running'")
            conn.execute("INSERT OR REPLACE INTO metadata_state(key,value) VALUES ('cache_version',?)", (METADATA_CACHE_VERSION,))
        tag_backfill = conn.execute(
            "SELECT value FROM metadata_state WHERE key='tag_write_backfill_version'"
        ).fetchone()
        if not tag_backfill or str(tag_backfill["value"] or "") != TAG_WRITE_BACKFILL_VERSION:
            albums = list(
                conn.execute(
                    """SELECT DISTINCT name,artist FROM metadata_entities
                       WHERE entity_type='album' AND artwork_id<>'' AND orphaned_at=0"""
                )
            )
            for album in albums:
                self._queue_album_tag_writes(conn, str(album["name"] or ""), str(album["artist"] or ""))
            conn.execute(
                "INSERT OR REPLACE INTO metadata_state(key,value) VALUES ('tag_write_backfill_version',?)",
                (TAG_WRITE_BACKFILL_VERSION,),
            )

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        with self._connect() as conn:
            # A process can be killed while a job is in flight. Recover every
            # interrupted job before creating the worker pool; otherwise old
            # `running` rows remain invisible to all future workers.
            conn.execute(
                "UPDATE metadata_jobs SET status='pending',next_attempt_at=0,updated_at=? WHERE status='running'",
                (int(time.time()),),
            )
        # Provider I/O is independent from file rewriting.  Keep a small,
        # bounded fetch pool so a slow provider cannot stall lyrics, artwork,
        # or the persistent Tag write queue.
        worker_count = bounded_int(self.config, "metadata_fetch_workers", 3, 1, 6)
        self.fetch_threads = [
            threading.Thread(target=self._run, name="fnaudio-metadata-fetch-%d" % index, daemon=True)
            for index in range(worker_count)
        ]
        self.thread = self.fetch_threads[0]
        self.tag_thread = threading.Thread(target=self._run_tag_writer, name="fnaudio-metadata-tag-writer", daemon=True)
        self.priority_thread = threading.Thread(target=self._run_priority_lyrics, name="fnaudio-metadata-priority", daemon=True)
        for worker in self.fetch_threads:
            worker.start()
        self.tag_thread.start()
        self.priority_thread.start()

    def shutdown(self):
        self.stop_event.set()
        self.wake_event.set()
        for worker in self.fetch_threads:
            worker.join(timeout=3)
        if self.tag_thread:
            self.tag_thread.join(timeout=3)
        if self.priority_thread:
            self.priority_thread.join(timeout=3)

    def wake(self, force=False):
        if force:
            with self.lock:
                self.force_reconcile = True
        self.wake_event.set()

    def retry_failed_tag_writes(self):
        """Return only terminal tag-write failures to the safe background queue."""
        with self._connect() as conn:
            result = conn.execute(
                """UPDATE metadata_jobs
                   SET status='pending', attempts=0, next_attempt_at=0, updated_at=?, last_error=''
                   WHERE job_type='tag_write' AND status='failed'""",
                (int(time.time()),),
            )
        if result.rowcount:
            self.wake_event.set()
        return max(0, int(result.rowcount or 0))

    def _run(self):
        while not self.stop_event.is_set():
            if not self.config.get("metadata_enabled", True):
                self.wake_event.wait(10)
                self.wake_event.clear()
                continue
            try:
                force = False
                with self.lock:
                    force = self.force_reconcile
                    due = force or time.time() - self.last_reconcile > 15
                    if due:
                        # Reconciliation is whole-library work. Claim the time
                        # slot before releasing the lock so only one worker runs it.
                        self.force_reconcile = False
                        self.last_reconcile = time.time()
                if due:
                    self.reconcile(force=force)
                job = self._claim_job(exclude_tag_writes=True)
                if job:
                    self._process_job(job)
                    self.stop_event.wait(0.25)
                    continue
            except Exception as exc:
                self.last_error = str(exc)
            self.wake_event.wait(10)
            self.wake_event.clear()

    def _run_tag_writer(self):
        """Serialize destructive file writes, while fetch workers remain concurrent."""
        while not self.stop_event.is_set():
            if not self.config.get("metadata_enabled", True):
                self.wake_event.wait(10)
                self.wake_event.clear()
                continue
            try:
                # Do not claim a job until its pacing delay has elapsed.  A
                # claimed job is marked ``running`` and intentionally blocks
                # concurrent writers; claiming first and then continuing used
                # to strand that job in ``running`` forever.
                interval_ms = bounded_int(
                    self.config,
                    "metadata_tag_playing_interval_ms" if self.current_track_id else "metadata_tag_idle_interval_ms",
                    2000 if self.current_track_id else 250, 50, 10000,
                )
                delay = interval_ms / 1000.0 - (time.monotonic() - self.last_tag_write_at)
                if delay > 0:
                    self.stop_event.wait(delay)
                    continue
                job = self._claim_job(tag_writes_only=True)
                if job:
                    self.tag_write_started_at = time.monotonic()
                    self._process_job(job)
                    elapsed = max(0.0, time.monotonic() - self.tag_write_started_at)
                    self.tag_write_seconds += elapsed
                    self.last_tag_write_at = time.monotonic()
                    self.tag_write_started_at = 0.0
                    continue
            except Exception as exc:
                self.last_error = str(exc)
                self.tag_write_started_at = 0.0
            self.wake_event.wait(1)
            self.wake_event.clear()

    def _run_priority_lyrics(self):
        """Keep the playing track responsive when ordinary enrichment is busy."""
        while not self.stop_event.is_set():
            if not self.config.get("metadata_enabled", True):
                self.wake_event.wait(10)
                self.wake_event.clear()
                continue
            try:
                job = self._claim_job(priority_max=0, lyrics_only=True)
                if job:
                    self._process_job(job)
                    continue
            except Exception as exc:
                self.last_error = str(exc)
            self.wake_event.wait(1)
            self.wake_event.clear()

    def reconcile(self, force=False):
        if not os.path.isfile(library_db_path(self.config)):
            self.last_reconcile = time.time()
            return
        now = int(time.time())
        with self._connect() as conn:
            meta_table = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='library_meta'").fetchone()
            if not meta_table:
                self.last_reconcile = time.time()
                return
            signature_row = conn.execute("SELECT value FROM library_meta WHERE key='signature'").fetchone()
            signature = str(signature_row["value"] or "") if signature_row else ""
            if not force and signature and signature == self.library_signature:
                self._requeue_expired(conn, now)
                if time.time() - self.last_cleanup > 3600:
                    self._cleanup_orphans(conn, now)
                    self._prune_artwork_cache(conn)
                    self.last_cleanup = time.time()
                self.last_reconcile = time.time()
                return
            if force:
                conn.execute("UPDATE metadata_entities SET expires_at=0")
                conn.execute("UPDATE metadata_tracks SET expires_at=0")
            active_entities = []
            for row in conn.execute("SELECT name,artist FROM albums"):
                self._reconcile_entity(conn, "album", row["name"], row["artist"], 10, force, active_entities)
            for row in conn.execute("SELECT name FROM artists"):
                self._reconcile_entity(conn, "artist", row["name"], "", 20, force, active_entities)
            for row in conn.execute("SELECT name FROM composers"):
                self._reconcile_entity(conn, "composer", row["name"], "", 30, force, active_entities)
            track_rows = list(conn.execute("SELECT id,path,title,artist,album,duration,item_json FROM tracks"))
            active_track_ids = []
            for row in track_rows:
                track_id = str(row["id"] or "")
                active_track_ids.append((track_id,))
                cached = conn.execute("SELECT expires_at FROM metadata_tracks WHERE track_id=?", (track_id,)).fetchone()
                if force or not cached or int(cached["expires_at"] or 0) <= now:
                    self._upsert_job(conn, "lyrics:" + track_id, "lyrics", track_id, dict(row), 100, force)
                if self._needs_track_enrichment(row):
                    match = conn.execute("SELECT expires_at FROM metadata_track_matches WHERE track_id=?", (track_id,)).fetchone()
                    if force or not match or int(match["expires_at"] or 0) <= now:
                        self._upsert_job(conn, "track:" + track_id, "track", track_id, dict(row), 80, force)

            conn.execute("CREATE TEMP TABLE IF NOT EXISTS active_metadata_entities(entity_type TEXT,entity_key TEXT,PRIMARY KEY(entity_type,entity_key))")
            conn.execute("DELETE FROM active_metadata_entities")
            conn.executemany("INSERT OR IGNORE INTO active_metadata_entities(entity_type,entity_key) VALUES (?,?)", active_entities)
            conn.execute("UPDATE metadata_entities SET orphaned_at=0 WHERE EXISTS (SELECT 1 FROM active_metadata_entities a WHERE a.entity_type=metadata_entities.entity_type AND a.entity_key=metadata_entities.entity_key)")
            conn.execute("UPDATE metadata_entities SET orphaned_at=? WHERE orphaned_at=0 AND NOT EXISTS (SELECT 1 FROM active_metadata_entities a WHERE a.entity_type=metadata_entities.entity_type AND a.entity_key=metadata_entities.entity_key)", (now,))
            conn.execute(
                """DELETE FROM metadata_jobs
                   WHERE job_type IN ('album','artist','composer')
                     AND NOT EXISTS (
                       SELECT 1 FROM active_metadata_entities a
                       WHERE a.entity_type=metadata_jobs.job_type AND a.entity_key=metadata_jobs.entity_key
                     )"""
            )

            conn.execute("CREATE TEMP TABLE IF NOT EXISTS active_metadata_tracks(track_id TEXT PRIMARY KEY)")
            conn.execute("DELETE FROM active_metadata_tracks")
            conn.executemany("INSERT OR IGNORE INTO active_metadata_tracks(track_id) VALUES (?)", active_track_ids)
            conn.execute("UPDATE metadata_tracks SET orphaned_at=0 WHERE track_id IN (SELECT track_id FROM active_metadata_tracks)")
            conn.execute("UPDATE metadata_tracks SET orphaned_at=? WHERE orphaned_at=0 AND track_id NOT IN (SELECT track_id FROM active_metadata_tracks)", (now,))
            conn.execute(
                "DELETE FROM metadata_jobs WHERE job_type IN ('lyrics','track','tag_write') AND entity_key NOT IN (SELECT track_id FROM active_metadata_tracks)"
            )
            conn.execute("UPDATE metadata_track_matches SET orphaned_at=0 WHERE track_id IN (SELECT track_id FROM active_metadata_tracks)")
            conn.execute("UPDATE metadata_track_matches SET orphaned_at=? WHERE track_id NOT IN (SELECT track_id FROM active_metadata_tracks) AND orphaned_at=0", (now,))
            self._cleanup_orphans(conn, now)
            self._prune_artwork_cache(conn)
            self.last_cleanup = time.time()
            self.library_signature = signature
        self.last_reconcile = time.time()

    @staticmethod
    def _needs_track_enrichment(row):
        try:
            sources = json.loads(row["item_json"] or "{}").get("metadata_source") or {}
        except (TypeError, ValueError):
            sources = {}
        # Do not search for a fully tagged recording. This queue is for files
        # whose artist/title came from the filename or whose album is absent.
        return any(str(sources.get(field) or "unknown") != "tag" for field in ("title", "artist", "album"))

    def _reconcile_entity(self, conn, kind, name, artist, priority, force, active_entities):
        name = str(name or "").strip()
        artist = str(artist or "").strip()
        if name.casefold() in {value.casefold() for value in PLACEHOLDER_NAMES}:
            return
        key = entity_key(kind, name, artist)
        if not key:
            return
        active_entities.append((kind, key))
        cached = conn.execute("SELECT expires_at FROM metadata_entities WHERE entity_type=? AND entity_key=?", (kind, key)).fetchone()
        if force or not cached or int(cached["expires_at"] or 0) <= int(time.time()):
            payload = {"name": name, "artist": artist}
            self._upsert_job(conn, "%s:%s" % (kind, key), kind, key, payload, priority, force)

    def _upsert_job(self, conn, job_key, job_type, key, payload, priority, force=False):
        now = int(time.time())
        existing = conn.execute("SELECT 1 FROM metadata_jobs WHERE job_key=?", (job_key,)).fetchone()
        if not existing:
            queue_limit = bounded_int(self.config, "metadata_max_pending_jobs", 20000, 100, 200000)
            pending = int(
                conn.execute("SELECT COUNT(*) FROM metadata_jobs WHERE status IN ('pending','retry')").fetchone()[0]
            )
            if pending >= queue_limit:
                evicted = None
                if int(priority) <= 2:
                    evicted = conn.execute(
                        """SELECT job_key FROM metadata_jobs
                           WHERE status IN ('pending','retry') AND priority>?
                           ORDER BY priority DESC,updated_at ASC LIMIT 1""",
                        (int(priority),),
                    ).fetchone()
                if not evicted:
                    self.dropped_jobs += 1
                    return False
                conn.execute("DELETE FROM metadata_jobs WHERE job_key=?", (evicted["job_key"],))
                self.dropped_jobs += 1
        conn.execute(
            """INSERT INTO metadata_jobs(job_key,job_type,entity_key,payload_json,priority,status,attempts,next_attempt_at,updated_at,last_error)
               VALUES (?,?,?,?,?,'pending',0,0,?,'')
               ON CONFLICT(job_key) DO UPDATE SET
                 payload_json=excluded.payload_json, priority=MIN(metadata_jobs.priority, excluded.priority),
                 status=CASE WHEN metadata_jobs.status='running' THEN 'running' ELSE 'pending' END,
                 next_attempt_at=CASE WHEN ? THEN 0 ELSE metadata_jobs.next_attempt_at END,
                 updated_at=excluded.updated_at""",
            (job_key, job_type, key, json.dumps(payload, ensure_ascii=False), priority, now, 1 if force else 0),
        )
        return True

    def _claim_job(self, priority_max=None, lyrics_only=False, tag_writes_only=False, exclude_tag_writes=False):
        now = int(time.time())
        with self._connect() as conn:
            clauses = ["status IN ('pending','retry')", "next_attempt_at<=?"]
            values = [now]
            if priority_max is not None:
                clauses.append("priority<=?")
                values.append(int(priority_max))
            if lyrics_only:
                clauses.append("job_type='lyrics'")
            if tag_writes_only:
                clauses.append("job_type='tag_write'")
                # The tag writer is intentionally single-file. The guard is
                # database-level so duplicate service starts cannot claim a
                # second destructive write concurrently.
                clauses.append("NOT EXISTS (SELECT 1 FROM metadata_jobs WHERE job_type='tag_write' AND status='running')")
            elif exclude_tag_writes:
                clauses.append("job_type<>'tag_write'")
            where = " AND ".join(clauses)
            row = conn.execute(
                "SELECT * FROM metadata_jobs WHERE %s ORDER BY priority,updated_at LIMIT 1" % where,
                values,
            ).fetchone()
            if not row:
                return None
            claimed = conn.execute(
                "UPDATE metadata_jobs SET status='running',attempts=attempts+1,updated_at=? WHERE job_key=? AND status IN ('pending','retry')",
                (now, row["job_key"]),
            )
            if not claimed.rowcount:
                return None
            return dict(row)

    def _process_job(self, job):
        self.active_job = job.get("job_key") or ""
        try:
            payload = json.loads(job.get("payload_json") or "{}")
            if job["job_type"] == "lyrics":
                result = self.providers.lyrics(payload) or {}
                if not result.get("image_url"):
                    artwork = self.providers.track_artwork(payload)
                    if artwork:
                        result.update(artwork)
                self._store_lyrics(job["entity_key"], result)
            elif job["job_type"] == "track":
                result = self._store_track_match(job["entity_key"], self.providers.track_candidates(payload))
            elif job["job_type"] == "tag_write":
                result = self._write_track_tags(job["entity_key"])
            else:
                result = self.providers.album(payload.get("name"), payload.get("artist")) if job["job_type"] == "album" else self.providers.person(payload.get("name"))
                self._store_entity(job["job_type"], job["entity_key"], payload, result)
            self._finish_job(job["job_key"], "skipped" if result == "skipped" else ("done" if result else "no_match"), "")
        except Exception as exc:
            attempts = int(job.get("attempts") or 0) + 1
            if attempts >= 5:
                self._finish_job(job["job_key"], "failed", str(exc))
            else:
                self._retry_job(job["job_key"], attempts, str(exc))
            self.last_error = str(exc)
        finally:
            self.active_job = ""

    def _store_entity(self, kind, key, payload, result):
        now = int(time.time())
        result = result or {}
        artwork_id = ""
        if result.get("image_url"):
            try:
                artwork_id = self._download_artwork(result.get("image_url"), result.get("source"))
            except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError):
                artwork_id = ""
        positive = bool(result.get("artist") or result.get("release_date") or artwork_id)
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO metadata_entities(
                    entity_type,entity_key,name,artist,release_date,artwork_id,source,provider_id,confidence,fetched_at,expires_at,orphaned_at,raw_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    kind, key, str(payload.get("name") or ""), str(result.get("artist") or payload.get("artist") or ""),
                    str(result.get("release_date") or ""), artwork_id, str(result.get("source") or ""),
                    str(result.get("provider_id") or ""), float(result.get("confidence") or 0), now,
                    now + (POSITIVE_TTL if positive else NEGATIVE_TTL), 0, json.dumps(result, ensure_ascii=False),
                ),
            )
            if kind == "album" and artwork_id:
                self._queue_album_tag_writes(conn, str(payload.get("name") or ""), str(payload.get("artist") or ""))

    def _store_lyrics(self, track_id, result):
        now = int(time.time())
        result = result or {}
        lyrics = str(result.get("lyrics") or "")
        artwork_id = ""
        if result.get("image_url"):
            try:
                artwork_id = self._download_artwork(result.get("image_url"), result.get("source"))
            except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError):
                artwork_id = ""
        with self._connect() as conn:
            existing = conn.execute("SELECT lyrics,artwork_id FROM metadata_tracks WHERE track_id=?", (track_id,)).fetchone()
            if not lyrics:
                lyrics = str(existing["lyrics"] or "") if existing else ""
            if not artwork_id:
                artwork_id = str(existing["artwork_id"] or "") if existing else ""
            conn.execute(
                """INSERT OR REPLACE INTO metadata_tracks(
                    track_id,lyrics,artwork_id,lyrics_source,provider_id,confidence,fetched_at,expires_at,orphaned_at
                ) VALUES (?,?,?,?,?,?,?,?,0)""",
                (
                    track_id, lyrics, artwork_id, str(result.get("source") or ""), str(result.get("provider_id") or ""),
                    float(result.get("confidence") or 0), now, now + (POSITIVE_TTL if lyrics else NEGATIVE_TTL),
                ),
            )
            if lyrics or artwork_id:
                self._queue_tag_write(conn, track_id)

    def _store_track_match(self, track_id, candidates):
        """Persist the best candidate, but only auto-apply unambiguous matches."""
        candidates = list(candidates or [])
        best = candidates[0] if candidates else {}
        runner_up = candidates[1] if len(candidates) > 1 else {}
        confidence = float(best.get("confidence") or 0)
        margin = confidence - float(runner_up.get("confidence") or 0)
        status = "auto" if confidence >= AUTO_TRACK_MATCH_CONFIDENCE and margin >= AUTO_TRACK_MATCH_MARGIN else "review"
        now = int(time.time())
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO metadata_track_matches(
                    track_id,fields_json,source,provider_id,confidence,status,fetched_at,expires_at,orphaned_at
                ) VALUES (?,?,?,?,?,?,?,?,0)""",
                (track_id, json.dumps({"best": best, "candidates": candidates}, ensure_ascii=False),
                 str(best.get("source") or ""), str(best.get("provider_id") or ""), confidence,
                 status, now, now + (POSITIVE_TTL if best else NEGATIVE_TTL)),
            )
            if status == "auto":
                self._queue_tag_write(conn, track_id)
        return best or None

    def _track_match_fields(self, conn, track_id, include_review=False):
        row = conn.execute(
            "SELECT fields_json,status FROM metadata_track_matches WHERE track_id=? AND orphaned_at=0",
            (track_id,),
        ).fetchone()
        if not row or (row["status"] not in ("auto", "confirmed") and not include_review):
            return {}
        try:
            return dict((json.loads(row["fields_json"] or "{}").get("best") or {}))
        except (TypeError, ValueError):
            return {}

    def apply_track_match(self, track_id, candidate_index=0):
        """Confirm one stored candidate and promote it to safe writeback."""
        try:
            candidate_index = int(candidate_index)
        except (TypeError, ValueError):
            return False
        if candidate_index < 0:
            return False
        with self._connect() as conn:
            row = conn.execute(
                "SELECT fields_json FROM metadata_track_matches WHERE track_id=? AND orphaned_at=0",
                (track_id,),
            ).fetchone()
            if not row:
                return False
            try:
                fields = dict(json.loads(row["fields_json"] or "{}"))
            except (TypeError, ValueError):
                return False
            candidates = list(fields.get("candidates") or [])
            if candidate_index >= len(candidates) or not isinstance(candidates[candidate_index], dict):
                return False
            selected = dict(candidates[candidate_index])
            fields["best"] = selected
            conn.execute(
                """UPDATE metadata_track_matches
                   SET fields_json=?,source=?,provider_id=?,confidence=?,status='confirmed'
                   WHERE track_id=?""",
                (
                    json.dumps(fields, ensure_ascii=False),
                    str(selected.get("source") or ""),
                    str(selected.get("provider_id") or ""),
                    float(selected.get("confidence") or 0),
                    track_id,
                ),
            )
            self._queue_tag_write(conn, track_id)
        self.wake_event.set()
        return True

    def track_match(self, track_id):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT fields_json,source,provider_id,confidence,status,fetched_at,expires_at FROM metadata_track_matches WHERE track_id=? AND orphaned_at=0",
                (track_id,),
            ).fetchone()
        if not row:
            return {"track_id": track_id, "status": "pending", "best": {}, "candidates": []}
        try:
            fields = json.loads(row["fields_json"] or "{}")
        except (TypeError, ValueError):
            fields = {}
        return {"track_id": track_id, "status": row["status"], "source": row["source"], "provider_id": row["provider_id"], "confidence": float(row["confidence"] or 0), "fetched_at": int(row["fetched_at"] or 0), "expires_at": int(row["expires_at"] or 0), "best": fields.get("best") or {}, "candidates": fields.get("candidates") or []}

    def _demote_track_jobs(self, conn, track_id):
        if not track_id:
            return
        conn.execute(
            """UPDATE metadata_jobs
               SET priority=CASE job_type WHEN 'lyrics' THEN 100 WHEN 'tag_write' THEN 200 ELSE priority END
               WHERE entity_key=? AND status IN ('pending','retry')""",
            (track_id,),
        )
        track = conn.execute("SELECT album,album_artist,artist FROM tracks WHERE id=?", (track_id,)).fetchone()
        if track and str(track["album"] or "").strip():
            key = entity_key("album", track["album"], track["album_artist"] or track["artist"] or "")
            conn.execute(
                """UPDATE metadata_jobs SET priority=10
                   WHERE job_key=? AND status IN ('pending','retry')""",
                ("album:" + key,),
            )

    def prioritize_track(self, track_id):
        """Give the playing file's lyrics, album art, and tag write precedence."""
        now = int(time.time())
        with self._connect() as conn:
            track_id = str(track_id or "")
            if track_id != self.current_track_id:
                self._demote_track_jobs(conn, self.current_track_id)
                self.current_track_id = track_id
            cached = conn.execute(
                "SELECT lyrics,expires_at FROM metadata_tracks WHERE track_id=? AND orphaned_at=0",
                (track_id,),
            ).fetchone()
            track = conn.execute(
                "SELECT id,path,title,artist,album,album_artist,duration,item_json FROM tracks WHERE id=?",
                (track_id,),
            ).fetchone()
            if not track:
                return False
            if not cached or not cached["lyrics"] or int(cached["expires_at"] or 0) <= now:
                self._upsert_job(conn, "lyrics:" + track_id, "lyrics", track_id, dict(track), 0, True)
            if self._needs_track_enrichment(track):
                self._upsert_job(conn, "track:" + track_id, "track", track_id, dict(track), 1, True)
            album = str(track["album"] or "").strip()
            if album:
                album_artist = track["album_artist"] or track["artist"] or ""
                album_key = entity_key("album", album, album_artist)
                album_cached = conn.execute(
                    "SELECT artwork_id,expires_at FROM metadata_entities WHERE entity_type='album' AND entity_key=? AND orphaned_at=0",
                    (album_key,),
                ).fetchone()
                album_force = not album_cached or not album_cached["artwork_id"] or int(album_cached["expires_at"] or 0) <= now
                self._reconcile_entity(conn, "album", album, album_artist, 1, album_force, [])
            self._upsert_job(conn, "tag:" + track_id, "tag_write", track_id, {}, 2)
        self.wake_event.set()
        return True

    def _queue_tag_write(self, conn, track_id):
        # One low-priority job per track coalesces separately discovered cover
        # and lyric data, so the original file is not repeatedly rewritten.
        # Non-current tracks get a short debounce window: album artwork and
        # lyrics frequently arrive a few seconds apart during a full scan.
        priority = 2 if str(track_id) == self.current_track_id else 200
        self._upsert_job(conn, "tag:" + track_id, "tag_write", track_id, {}, priority)
        if priority >= 200:
            conn.execute(
                """UPDATE metadata_jobs
                   SET next_attempt_at=MAX(next_attempt_at, ?), updated_at=?
                   WHERE job_key=? AND status IN ('pending','retry')""",
                (int(time.time()) + 10, int(time.time()), "tag:" + track_id),
            )

    def _queue_album_tag_writes(self, conn, album, album_artist):
        # The album index already collapses tracks by album name and chooses a
        # canonical artist when album_artist is missing. Queue every track in
        # that indexed album so an empty per-track album_artist cannot prevent
        # the downloaded cover from reaching the tag writer.
        rows = conn.execute("SELECT id FROM tracks WHERE album=?", (album,))
        for row in rows:
            self._queue_tag_write(conn, str(row["id"]))

    def _tag_data(self, track_id):
        with self._connect() as conn:
            track = conn.execute(
                "SELECT id,path,title,artist,album,album_artist,composer,genre,track_no,is_dsd,cue_track,item_json FROM tracks WHERE id=?",
                (track_id,),
            ).fetchone()
            if not track:
                return None
            data = dict(track)
            try:
                metadata_source = json.loads(data.get("item_json") or "{}").get("metadata_source") or {}
            except (TypeError, ValueError):
                metadata_source = {}
            # Candidate data fills only missing or filename-derived fields;
            # a valid user tag always remains authoritative.
            candidate = self._track_match_fields(conn, track_id)
            data["has_track_match"] = bool(candidate)
            for field in TRACK_METADATA_FIELDS:
                value = str(candidate.get(field) or "").strip()
                if not value:
                    continue
                if not str(data.get(field) or "").strip() or str(metadata_source.get(field) or "unknown") != "tag":
                    data[field] = value
            lyrics = conn.execute("SELECT lyrics FROM metadata_tracks WHERE track_id=? AND orphaned_at=0", (track_id,)).fetchone()
            data["lyrics"] = str(lyrics["lyrics"] or "") if lyrics else ""
            indexed_album = conn.execute(
                "SELECT artist FROM albums WHERE name=?",
                (data["album"],),
            ).fetchone()
            canonical_album_artist = (
                str(indexed_album["artist"] or "") if indexed_album
                else str(data["album_artist"] or data["artist"] or "")
            )
            album_key = entity_key("album", data["album"], canonical_album_artist)
            artwork = conn.execute(
                """SELECT a.path,a.mime,e.release_date FROM metadata_entities e
                   JOIN metadata_assets a ON a.id=e.artwork_id
                   WHERE e.entity_type='album' AND e.entity_key=? AND e.orphaned_at=0""",
                (album_key,),
            ).fetchone()
            if artwork and os.path.isfile(artwork["path"]):
                data["artwork_path"] = artwork["path"]
                data["artwork_mime"] = artwork["mime"]
            if artwork:
                data["date"] = str(artwork["release_date"] or "")
            if not data.get("artwork_path"):
                track_artwork = conn.execute(
                    """SELECT a.path,a.mime FROM metadata_tracks t
                       JOIN metadata_assets a ON a.id=t.artwork_id
                       WHERE t.track_id=? AND t.orphaned_at=0""",
                    (track_id,),
                ).fetchone()
                if track_artwork and os.path.isfile(track_artwork["path"]):
                    data["artwork_path"] = track_artwork["path"]
                    data["artwork_mime"] = track_artwork["mime"]
            return data

    def _write_track_tags(self, track_id):
        data = self._tag_data(track_id)
        if not data:
            return False
        source = str(data.get("path") or "")
        extension = os.path.splitext(source)[1].lower()
        if (extension not in TAG_WRITABLE_EXTENSIONS
                or not os.path.isfile(source) or (not data.get("lyrics") and not data.get("artwork_path") and not data.get("has_track_match"))):
            return True
        if data.get("cue_track"):
            # CUE rows are virtual tracks over one physical audio file. Never
            # write per-track title, artist, or lyrics into the shared source;
            # album artwork is safe and is intentionally the sole writeback.
            if not data.get("artwork_path"):
                return "skipped"
            data = {
                "path": source,
                "artwork_path": data.get("artwork_path"),
                "artwork_mime": data.get("artwork_mime") or "image/jpeg",
            }
        artwork_path = str(data.get("artwork_path") or "")
        if artwork_path and os.path.isfile(artwork_path):
            try:
                _mime, existing = read_cover(source, self.config)
                with open(artwork_path, "rb") as handle:
                    desired = handle.read()
                if (existing and desired and hashlib.sha256(existing).digest() == hashlib.sha256(desired).digest()
                        and not data.get("has_track_match") and not data.get("lyrics")):
                    return "skipped"
            except OSError:
                pass
        if extension in (".mp3", ".flac") and not data.get("artwork_path") and self._write_track_tags_native(source, extension, data):
            self.tag_written += 1
            return True
        temporary = source + ".fnaudio-tagging" + extension
        try:
            if extension == ".dsf":
                _write_dsf_tags(source, temporary, data)
            elif extension == ".ape":
                _write_ape_tags(source, temporary, data)
            elif extension == ".wav":
                _write_wav_tags(source, temporary, data)
            else:
                temporary = self._write_track_tags_ffmpeg(source, extension, data, temporary)
            if not os.path.isfile(temporary) or os.path.getsize(temporary) <= 0:
                raise RuntimeError("tag write produced no output")
            preserve_owner_and_mode(source, temporary)
            os.replace(temporary, source)
            self.tag_written += 1
            return True
        finally:
            try:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            except OSError:
                pass

    def _write_track_tags_ffmpeg(self, source, extension, data, temporary):
        ffmpeg = find_ffmpeg(self.config)
        if not ffmpeg:
            raise RuntimeError("ffmpeg is required to write embedded metadata")
        command = [ffmpeg, "-nostdin", "-y", "-i", source]
        if data.get("artwork_path"):
            # Audio containers can carry timed text and binary data streams
            # which their muxer cannot copy back (notably M4A/iPod). Preserve
            # audio while replacing only the embedded image streams.
            command += ["-i", data["artwork_path"], "-map", "0:a?", "-map", "1:v:0", "-disposition:v:0", "attached_pic"]
        else:
            # A lyrics-only update keeps existing embedded covers, but omits
            # incompatible subtitle/data streams from audio-only containers.
            command += ["-map", "0:a?", "-map", "0:v?"]
        command += ["-map_metadata", "0", "-c", "copy"]
        for key in ("title", "artist", "album", "album_artist", "composer", "genre", "track_no", "date", "lyrics"):
            value = str(data.get(key) or "").replace("\x00", "").strip()
            if value:
                command += ["-metadata", "%s=%s" % (key, value)]
        if extension == ".mp3":
            command += ["-id3v2_version", "3"]
        env = os.environ.copy()
        if "/usr/trim/lib/mediasrv/bin" in ffmpeg:
            env["LD_LIBRARY_PATH"] = "/usr/trim/lib/mediasrv/lib:" + env.get("LD_LIBRARY_PATH", "")
        try:
            result = subprocess.run(command + [temporary], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=180, env=env)
            if result.returncode != 0 or not os.path.isfile(temporary) or os.path.getsize(temporary) <= 0:
                detail = result.stderr.decode("utf-8", "ignore")[-300:]
                raise RuntimeError("tag write failed: %s" % detail)
            return temporary
        except Exception:
            raise

    def _write_track_tags_native(self, source, extension, data):
        """Use Mutagen only when the packaged runtime explicitly provides it.

        MP3/FLAC can be updated in place by a mature tag library, avoiding a
        full audio remux.  fnOS does not currently bundle that dependency, so
        the conservative FFmpeg path remains the default until it is supplied.
        M4A/MP4 intentionally stays on FFmpeg because artwork atom rewrites
        need the existing stream-preservation safeguards.
        """
        if extension not in (".mp3", ".flac"):
            return False
        try:
            import mutagen  # type: ignore
        except ImportError:
            return False
        try:
            audio = mutagen.File(source, easy=True)
            if audio is None:
                return False
            field_map = {
                "title": "title", "artist": "artist", "album": "album",
                "album_artist": "albumartist", "composer": "composer",
                "genre": "genre", "track_no": "tracknumber", "date": "date", "lyrics": "lyrics",
            }
            for source_key, target_key in field_map.items():
                value = str(data.get(source_key) or "").replace("\x00", "").strip()
                if value:
                    audio[target_key] = [value]
            # Do not claim the fast path when an artwork replacement is needed:
            # easy tags do not expose a uniform safe picture API across formats.
            if data.get("artwork_path"):
                return False
            audio.save()
            return True
        except Exception:
            return False

    def _download_artwork(self, url, source=""):
        url = str(url or "").strip()
        if not url:
            return ""
        with self._connect() as conn:
            cached = conn.execute("SELECT id,path FROM metadata_assets WHERE source_url=? ORDER BY fetched_at DESC LIMIT 1", (url,)).fetchone()
            if cached and os.path.isfile(cached["path"]):
                return str(cached["id"])
        request = urllib.request.Request(url, headers={"User-Agent": APP_USER_AGENT, "Referer": "https://music.163.com/" if source == "netease" else ""})
        with urllib.request.urlopen(request, timeout=15) as response:
            mime = str(response.headers.get_content_type() or "")
            body = response.read(MAX_ARTWORK_BYTES + 1)
        if len(body) > MAX_ARTWORK_BYTES or not body:
            return ""
        if not mime.startswith("image/"):
            if body.startswith(b"\xff\xd8"):
                mime = "image/jpeg"
            elif body.startswith(b"\x89PNG"):
                mime = "image/png"
            elif body.startswith(b"RIFF") and body[8:12] == b"WEBP":
                mime = "image/webp"
            else:
                return ""
        asset_id = hashlib.sha256(body).hexdigest()
        extension = mimetypes.guess_extension(mime) or ".img"
        secure_directory(self.artwork_dir)
        minimum_free = bounded_int(
            self.config,
            "cache_min_free_bytes",
            512 * 1024 * 1024,
            64 * 1024 * 1024,
            16 * 1024 * 1024 * 1024,
        )
        with self._connect() as conn:
            self._prune_artwork_cache(conn, incoming_bytes=len(body))
        if not disk_has_reserve(self.artwork_dir, minimum_free, len(body)):
            raise ResourceLimitError("metadata cache disk reserve reached")
        path = os.path.join(self.artwork_dir, asset_id + extension)
        if not os.path.isfile(path):
            temporary = path + ".tmp"
            with open(temporary, "wb") as fh:
                fh.write(body)
            secure_file(temporary)
            os.replace(temporary, path)
            secure_file(path)
        now = int(time.time())
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO metadata_assets(id,path,mime,size,source_url,fetched_at,last_accessed) VALUES (?,?,?,?,?,?,?)",
                (asset_id, path, mime, len(body), url, now, now),
            )
        return asset_id

    def _prune_artwork_cache(self, conn, incoming_bytes=0):
        """Remove least-recently-used artwork until byte and disk limits are satisfied."""
        maximum = bounded_int(
            self.config,
            "metadata_cache_max_bytes",
            512 * 1024 * 1024,
            16 * 1024 * 1024,
            8 * 1024 * 1024 * 1024,
        )
        minimum_free = bounded_int(
            self.config,
            "cache_min_free_bytes",
            512 * 1024 * 1024,
            64 * 1024 * 1024,
            16 * 1024 * 1024 * 1024,
        )
        assets = list(
            conn.execute(
                "SELECT id,path,size FROM metadata_assets ORDER BY last_accessed ASC,fetched_at ASC"
            )
        )
        total = sum(max(0, int(row["size"] or 0)) for row in assets)
        removed = 0
        for asset in assets:
            if total + max(0, int(incoming_bytes)) <= maximum and disk_has_reserve(
                self.artwork_dir, minimum_free, incoming_bytes
            ):
                break
            path = str(asset["path"] or "")
            try:
                if path and os.path.exists(path):
                    os.unlink(path)
            except OSError:
                continue
            conn.execute(
                "UPDATE metadata_entities SET artwork_id='',expires_at=0 WHERE artwork_id=?",
                (asset["id"],),
            )
            conn.execute("DELETE FROM metadata_assets WHERE id=?", (asset["id"],))
            total = max(0, total - max(0, int(asset["size"] or 0)))
            removed += 1
        return removed

    def _finish_job(self, job_key, status, error):
        with self._connect() as conn:
            conn.execute("UPDATE metadata_jobs SET status=?,updated_at=?,last_error=? WHERE job_key=?", (status, int(time.time()), error[:500], job_key))

    def _retry_job(self, job_key, attempts, error):
        delay = min(3600, 60 * (2 ** max(0, attempts - 1)))
        with self._connect() as conn:
            conn.execute(
                "UPDATE metadata_jobs SET status='retry',next_attempt_at=?,updated_at=?,last_error=? WHERE job_key=?",
                (int(time.time()) + delay, int(time.time()), error[:500], job_key),
            )

    def _cleanup_orphans(self, conn, now):
        grace_days = max(0, int(self.config.get("metadata_orphan_grace_days", 7)))
        threshold = now - grace_days * 24 * 60 * 60
        removed_entities = list(conn.execute("SELECT entity_type,entity_key FROM metadata_entities WHERE orphaned_at>0 AND orphaned_at<=?", (threshold,)))
        removed_tracks = list(conn.execute("SELECT track_id FROM metadata_tracks WHERE orphaned_at>0 AND orphaned_at<=?", (threshold,)))
        conn.execute("DELETE FROM metadata_entities WHERE orphaned_at>0 AND orphaned_at<=?", (threshold,))
        conn.execute("DELETE FROM metadata_tracks WHERE orphaned_at>0 AND orphaned_at<=?", (threshold,))
        conn.execute("DELETE FROM metadata_track_matches WHERE orphaned_at>0 AND orphaned_at<=?", (threshold,))
        for row in removed_entities:
            conn.execute("DELETE FROM metadata_jobs WHERE job_key=?", ("%s:%s" % (row["entity_type"], row["entity_key"]),))
        for row in removed_tracks:
            conn.execute("DELETE FROM metadata_jobs WHERE job_key=?", ("lyrics:" + row["track_id"],))
            conn.execute("DELETE FROM metadata_jobs WHERE job_key=?", ("tag:" + row["track_id"],))
        orphan_assets = list(conn.execute("SELECT id,path FROM metadata_assets WHERE id NOT IN (SELECT artwork_id FROM metadata_entities WHERE artwork_id<>'')"))
        for asset in orphan_assets:
            try:
                os.unlink(asset["path"])
            except OSError:
                pass
            conn.execute("DELETE FROM metadata_assets WHERE id=?", (asset["id"],))

    def _requeue_expired(self, conn, now):
        conn.execute(
            """UPDATE metadata_jobs SET status='pending',next_attempt_at=0,updated_at=?
               WHERE status<>'running' AND job_key IN (
                 SELECT entity_type || ':' || entity_key FROM metadata_entities
                 WHERE orphaned_at=0 AND expires_at<=?
               )""",
            (now, now),
        )
        conn.execute(
            """UPDATE metadata_jobs SET status='pending',next_attempt_at=0,updated_at=?
               WHERE status<>'running' AND job_key IN (
                 SELECT 'lyrics:' || track_id FROM metadata_tracks
                 WHERE orphaned_at=0 AND expires_at<=?
               )""",
            (now, now),
        )

    def enrich_groups(self, view, result):
        groups = result.get("groups", []) if isinstance(result, dict) else result
        if not isinstance(groups, list) or view not in ("albums", "artists", "composers"):
            return result
        kind = {"albums": "album", "artists": "artist", "composers": "composer"}[view]
        keyed_groups = [
            (group, entity_key(kind, group.get("name"), group.get("artist") if kind == "album" else ""))
            for group in groups
        ]
        keys = [key for _, key in keyed_groups if key]
        if not keys:
            return result
        with self._connect() as conn:
            placeholders = ",".join("?" for _ in keys)
            exact_rows = conn.execute(
                "SELECT entity_key,artist,release_date,artwork_id,source,confidence FROM metadata_entities WHERE entity_type=? AND entity_key IN (%s) AND orphaned_at=0" % placeholders,
                [kind] + keys,
            )
            metadata_by_key = {row["entity_key"]: row for row in exact_rows}
            fallback_by_name = {}
            if kind == "album":
                names = sorted({str(group.get("name") or "") for group, _ in keyed_groups if group.get("name")})
                if names:
                    name_placeholders = ",".join("?" for _ in names)
                    fallback_rows = conn.execute(
                        "SELECT entity_key,name,artist,release_date,artwork_id,source,confidence FROM metadata_entities WHERE entity_type='album' AND name IN (%s) ORDER BY orphaned_at ASC,confidence DESC" % name_placeholders,
                        names,
                    )
                    for candidate in fallback_rows:
                        fallback_by_name.setdefault(candidate["name"], []).append(candidate)
            for group, key in keyed_groups:
                row = metadata_by_key.get(key)
                if not row and kind == "album":
                    wanted_artist = normalize_text(group.get("artist"))
                    for candidate in fallback_by_name.get(str(group.get("name") or ""), []):
                        candidate_artist = normalize_text(candidate["artist"])
                        if not wanted_artist or (candidate_artist and (candidate_artist in wanted_artist or wanted_artist in candidate_artist)):
                            row = candidate
                            break
                if not row:
                    continue
                if row["artist"] and kind == "album":
                    group["artist"] = row["artist"]
                group["release_date"] = normalize_release_date(row["release_date"])
                group["metadata_source"] = row["source"] or ""
                group["metadata_confidence"] = float(row["confidence"] or 0)
                if row["artwork_id"]:
                    group["image_url"] = "metadata/artwork/" + row["artwork_id"]
        return result

    def lyrics(self, track_id):
        now = int(time.time())
        with self._connect() as conn:
            row = conn.execute("SELECT lyrics,lyrics_source,expires_at FROM metadata_tracks WHERE track_id=? AND orphaned_at=0", (track_id,)).fetchone()
            if row and int(row["expires_at"] or 0) > now:
                return {"lyrics": row["lyrics"] or "", "source": row["lyrics_source"] or "", "pending": False}
            track = conn.execute("SELECT id,path,title,artist,album,duration FROM tracks WHERE id=?", (track_id,)).fetchone()
            if not track:
                return None
            # This path is reached by the active player/lyrics view. It must
            # take precedence over the ordinary library reconciliation queue.
            self._upsert_job(conn, "lyrics:" + track_id, "lyrics", track_id, dict(track), 0, True)
        self.wake_event.set()
        return {"lyrics": "", "source": "后台匹配中", "pending": True}

    def artwork(self, asset_id):
        if not re.fullmatch(r"[0-9a-f]{64}", str(asset_id or "")):
            return None
        with self._connect() as conn:
            row = conn.execute("SELECT path,mime,size FROM metadata_assets WHERE id=?", (asset_id,)).fetchone()
            if not row or not os.path.isfile(row["path"]):
                return None
            conn.execute("UPDATE metadata_assets SET last_accessed=? WHERE id=?", (int(time.time()), asset_id))
            return dict(row)

    def cached_entity(self, kind, name, artist=""):
        with self._connect() as conn:
            key = entity_key(kind, name, artist)
            row = conn.execute(
                "SELECT artist,release_date,artwork_id,source,confidence,expires_at FROM metadata_entities WHERE entity_type=? AND entity_key=? AND orphaned_at=0",
                (kind, key),
            ).fetchone()
            if not row and kind == "album":
                row = conn.execute(
                    "SELECT artist,release_date,artwork_id,source,confidence,expires_at FROM metadata_entities WHERE entity_type='album' AND name=? AND orphaned_at=0 ORDER BY confidence DESC LIMIT 1",
                    (str(name or ""),),
                ).fetchone()
            if not row:
                return {}
            return {
                "artist": row["artist"] or "",
                "release_date": normalize_release_date(row["release_date"]),
                "image_url": "metadata/artwork/" + row["artwork_id"] if row["artwork_id"] else "",
                "source": row["source"] or "",
                "confidence": float(row["confidence"] or 0),
                "expires_at": int(row["expires_at"] or 0),
            }

    def status(self):
        counts = {}
        entity_count = 0
        lyrics_count = 0
        tag_jobs = []
        track_matches = {}
        pending = 0
        artwork_bytes = 0
        try:
            with self._connect() as conn:
                counts = {row["status"]: int(row["count"]) for row in conn.execute("SELECT status,COUNT(*) AS count FROM metadata_jobs GROUP BY status")}
                job_types = {
                    row["job_type"]: {"pending": int(row["pending"] or 0), "running": int(row["running"] or 0)}
                    for row in conn.execute(
                        """SELECT job_type,
                                  SUM(CASE WHEN status IN ('pending','retry') THEN 1 ELSE 0 END) AS pending,
                                  SUM(CASE WHEN status='running' THEN 1 ELSE 0 END) AS running
                           FROM metadata_jobs GROUP BY job_type"""
                    )
                }
                pending = int(counts.get("pending", 0)) + int(counts.get("retry", 0))
                artwork_bytes = int(conn.execute("SELECT COALESCE(SUM(size),0) FROM metadata_assets").fetchone()[0] or 0)
                entity_count = int(conn.execute("SELECT COUNT(*) FROM metadata_entities WHERE orphaned_at=0").fetchone()[0])
                lyrics_count = int(conn.execute("SELECT COUNT(*) FROM metadata_tracks WHERE lyrics<>'' AND orphaned_at=0").fetchone()[0])
                track_matches = {
                    row["status"]: int(row["count"])
                    for row in conn.execute("SELECT status,COUNT(*) AS count FROM metadata_track_matches WHERE orphaned_at=0 GROUP BY status")
                }
                for row in conn.execute(
                    """SELECT j.status,j.attempts,j.updated_at,j.last_error,t.title,t.artist,t.path
                       FROM metadata_jobs j LEFT JOIN tracks t ON t.id=j.entity_key
                       WHERE j.job_type='tag_write'
                       ORDER BY CASE j.status WHEN 'failed' THEN 0 WHEN 'retry' THEN 1 WHEN 'running' THEN 2 ELSE 3 END,
                                j.updated_at DESC LIMIT 6"""
                ):
                    title = str(row["title"] or "").strip() or os.path.splitext(os.path.basename(str(row["path"] or "")))[0] or "未知歌曲"
                    tag_jobs.append({
                        "title": title,
                        "artist": str(row["artist"] or ""),
                        "status": str(row["status"] or "pending"),
                        "attempts": int(row["attempts"] or 0),
                        "updated_at": int(row["updated_at"] or 0),
                        "error": str(row["last_error"] or "")[:500],
                    })
        except sqlite3.Error as exc:
            self.last_error = str(exc)
        return {
            "ok": True,
            "enabled": bool(self.config.get("metadata_enabled", True)),
            "running": bool(any(worker.is_alive() for worker in self.fetch_threads) or (self.tag_thread and self.tag_thread.is_alive())),
            "active_job": self.active_job,
            "jobs": counts,
            "job_types": job_types,
            "pending": pending,
            "pending_limit": bounded_int(self.config, "metadata_max_pending_jobs", 20000, 100, 200000),
            "dropped": self.dropped_jobs,
            "saturated": pending >= bounded_int(self.config, "metadata_max_pending_jobs", 20000, 100, 200000),
            "artwork_bytes": artwork_bytes,
            "artwork_limit_bytes": bounded_int(
                self.config, "metadata_cache_max_bytes", 512 * 1024 * 1024, 16 * 1024 * 1024, 8 * 1024 * 1024 * 1024
            ),
            "entities": entity_count,
            "lyrics": lyrics_count,
            "track_matches": track_matches,
            "tag_written": self.tag_written,
            "fetch_workers": len(self.fetch_threads),
            "tag_writer_running": bool(self.tag_thread and self.tag_thread.is_alive()),
            "tag_write_average_seconds": round(self.tag_write_seconds / self.tag_written, 3) if self.tag_written else 0,
            "tag_write_in_progress": bool(self.tag_write_started_at),
            "tag_writer": "mutagen-if-available-otherwise-ffmpeg",
            "fingerprint": fingerprint_capability(self.config),
            "tag_jobs": tag_jobs,
            "last_tag_write_at": self.last_tag_write_at,
            "last_reconcile": self.last_reconcile,
            "last_error": self.last_error,
            "orphan_grace_days": int(self.config.get("metadata_orphan_grace_days") or 7),
        }


__all__ = [
    "MetadataProviders", "MetadataService", "contains_cjk", "entity_key",
    "normalize_release_date", "normalize_text", "provider_score", "read_local_lyrics",
]

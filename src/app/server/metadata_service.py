from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import re
import sqlite3
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager

from library import library_db_path


POSITIVE_TTL = 30 * 24 * 60 * 60
NEGATIVE_TTL = 6 * 60 * 60
DEFAULT_ORPHAN_GRACE = 7 * 24 * 60 * 60
METADATA_CACHE_VERSION = "2"
MAX_ARTWORK_BYTES = 8 * 1024 * 1024
PLACEHOLDER_NAMES = {
    "", "未分类", "未知专辑", "未知歌手", "未知艺术家", "未知作曲者",
    "unknown album", "unknown artist", "unknown composer",
}


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
        self.spotify_token = ""
        self.spotify_token_expires = 0

    def _json(self, url, headers=None, data=None, timeout=10):
        request = urllib.request.Request(url, headers=headers or {}, data=data)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", "ignore"))

    def _spotify_access_token(self):
        client_id = str(self.config.get("spotify_client_id") or "").strip()
        client_secret = str(self.config.get("spotify_client_secret") or "").strip()
        if not client_id or not client_secret:
            return ""
        if self.spotify_token and self.spotify_token_expires > time.time() + 60:
            return self.spotify_token
        credentials = base64.b64encode((client_id + ":" + client_secret).encode("utf-8")).decode("ascii")
        payload = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode("ascii")
        data = self._json(
            "https://accounts.spotify.com/api/token",
            {"Authorization": "Basic " + credentials, "Content-Type": "application/x-www-form-urlencoded"},
            payload,
        )
        self.spotify_token = str(data.get("access_token") or "")
        self.spotify_token_expires = time.time() + int(data.get("expires_in") or 3600)
        return self.spotify_token

    def _spotify_search(self, query, search_type, limit=10):
        token = self._spotify_access_token()
        if not token:
            return []
        url = "https://api.spotify.com/v1/search?" + urllib.parse.urlencode({
            "q": query,
            "type": search_type,
            "limit": limit,
        })
        data = self._json(url, {"Authorization": "Bearer " + token, "User-Agent": "fnAudio/0.1"})
        return ((data.get(search_type + "s") or {}).get("items") or [])

    def spotify_album(self, name, artist=""):
        query = 'album:"%s"' % name
        if artist:
            query += ' artist:"%s"' % artist
        best = None
        best_score = 0
        for item in self._spotify_search(query, "album"):
            item_artist = _artist_name(item.get("artists") or [])
            score = provider_score(item.get("name"), name, item_artist, artist)
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.55:
            return None
        images = best.get("images") or []
        return {
            "name": best.get("name") or name,
            "artist": _artist_name(best.get("artists") or []) or artist,
            "release_date": best.get("release_date") or "",
            "image_url": (images[0].get("url") if images else "") or "",
            "provider_id": best.get("id") or "",
            "source": "spotify",
            "confidence": best_score,
        }

    def spotify_person(self, name):
        best = None
        best_score = 0
        for item in self._spotify_search('artist:"%s"' % name, "artist"):
            score = provider_score(item.get("name"), name)
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.55:
            return None
        images = best.get("images") or []
        return {
            "name": best.get("name") or name,
            "artist": best.get("name") or name,
            "release_date": "",
            "image_url": (images[0].get("url") if images else "") or "",
            "provider_id": best.get("id") or "",
            "source": "spotify",
            "confidence": best_score,
        }

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
        data = self._json(url, {"User-Agent": "fnAudio/0.1 (local music server)"})
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
            providers = (self.netease_album, self.qq_album, self.spotify_album, self.musicbrainz_album)
        else:
            providers = (self.spotify_album, self.musicbrainz_album, self.netease_album, self.qq_album)
        return self._first_match(providers, name, artist)

    def person(self, name):
        if contains_cjk(name):
            providers = (self.netease_person, self.qq_person, self.spotify_person)
        else:
            providers = (self.spotify_person, self.netease_person, self.qq_person)
        return self._first_match(providers, name)

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

    def lyrics(self, track):
        local = read_local_lyrics(track.get("path") or "")
        if local:
            return {"lyrics": local, "source": "本地歌词", "provider_id": "", "confidence": 1.0}
        for provider in (self.netease_lyrics, self.qq_lyrics):
            try:
                result = provider(track)
                if result:
                    return result
            except (OSError, ValueError, TypeError, urllib.error.URLError, urllib.error.HTTPError):
                continue
        return None


def read_local_lyrics(path):
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
        self.force_reconcile = False
        self.last_reconcile = 0
        self.library_signature = ""
        self.last_cleanup = 0
        self.last_error = ""
        self.active_job = ""
        self.lock = threading.RLock()

    @property
    def artwork_dir(self):
        return os.path.join(self.config.get("cache_dir") or ".", "metadata", "artwork")

    @contextmanager
    def _connect(self):
        path = library_db_path(self.config)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        conn = sqlite3.connect(path, timeout=20)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
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
                lyrics_source TEXT NOT NULL DEFAULT '',
                provider_id TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0,
                fetched_at INTEGER NOT NULL DEFAULT 0,
                expires_at INTEGER NOT NULL DEFAULT 0,
                orphaned_at INTEGER NOT NULL DEFAULT 0
            );
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
        version = conn.execute("SELECT value FROM metadata_state WHERE key='cache_version'").fetchone()
        if not version or str(version["value"] or "") != METADATA_CACHE_VERSION:
            conn.execute("UPDATE metadata_entities SET expires_at=0")
            conn.execute("UPDATE metadata_tracks SET expires_at=0")
            conn.execute("UPDATE metadata_jobs SET status='pending',next_attempt_at=0 WHERE status<>'running'")
            conn.execute("INSERT OR REPLACE INTO metadata_state(key,value) VALUES ('cache_version',?)", (METADATA_CACHE_VERSION,))

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        with self._connect() as conn:
            conn.execute("UPDATE metadata_jobs SET status='pending' WHERE status='running'")
        self.thread = threading.Thread(target=self._run, name="fnaudio-metadata", daemon=True)
        self.thread.start()

    def shutdown(self):
        self.stop_event.set()
        self.wake_event.set()
        if self.thread:
            self.thread.join(timeout=3)

    def wake(self, force=False):
        if force:
            with self.lock:
                self.force_reconcile = True
        self.wake_event.set()

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
                    self.force_reconcile = False
                if force or time.time() - self.last_reconcile > 15:
                    self.reconcile(force=force)
                job = self._claim_job()
                if job:
                    self._process_job(job)
                    self.stop_event.wait(0.25)
                    continue
            except Exception as exc:
                self.last_error = str(exc)
            self.wake_event.wait(10)
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
            track_rows = list(conn.execute("SELECT id,path,title,artist,album,duration FROM tracks"))
            active_track_ids = []
            for row in track_rows:
                track_id = str(row["id"] or "")
                active_track_ids.append((track_id,))
                cached = conn.execute("SELECT expires_at FROM metadata_tracks WHERE track_id=?", (track_id,)).fetchone()
                if force or not cached or int(cached["expires_at"] or 0) <= now:
                    self._upsert_job(conn, "lyrics:" + track_id, "lyrics", track_id, dict(row), 100, force)

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
                "DELETE FROM metadata_jobs WHERE job_type='lyrics' AND entity_key NOT IN (SELECT track_id FROM active_metadata_tracks)"
            )
            self._cleanup_orphans(conn, now)
            self.last_cleanup = time.time()
            self.library_signature = signature
        self.last_reconcile = time.time()

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
        conn.execute(
            """INSERT INTO metadata_jobs(job_key,job_type,entity_key,payload_json,priority,status,attempts,next_attempt_at,updated_at,last_error)
               VALUES (?,?,?,?,?,'pending',0,0,?,'')
               ON CONFLICT(job_key) DO UPDATE SET
                 payload_json=excluded.payload_json, priority=excluded.priority,
                 status=CASE WHEN metadata_jobs.status='running' THEN 'running' ELSE 'pending' END,
                 next_attempt_at=CASE WHEN ? THEN 0 ELSE metadata_jobs.next_attempt_at END,
                 updated_at=excluded.updated_at""",
            (job_key, job_type, key, json.dumps(payload, ensure_ascii=False), priority, now, 1 if force else 0),
        )

    def _claim_job(self):
        now = int(time.time())
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM metadata_jobs WHERE status IN ('pending','retry') AND next_attempt_at<=? ORDER BY priority,updated_at LIMIT 1",
                (now,),
            ).fetchone()
            if not row:
                return None
            conn.execute("UPDATE metadata_jobs SET status='running',attempts=attempts+1,updated_at=? WHERE job_key=?", (now, row["job_key"]))
            return dict(row)

    def _process_job(self, job):
        self.active_job = job.get("job_key") or ""
        try:
            payload = json.loads(job.get("payload_json") or "{}")
            if job["job_type"] == "lyrics":
                result = self.providers.lyrics(payload)
                self._store_lyrics(job["entity_key"], result)
            else:
                result = self.providers.album(payload.get("name"), payload.get("artist")) if job["job_type"] == "album" else self.providers.person(payload.get("name"))
                self._store_entity(job["job_type"], job["entity_key"], payload, result)
            self._finish_job(job["job_key"], "done" if result else "no_match", "")
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

    def _store_lyrics(self, track_id, result):
        now = int(time.time())
        result = result or {}
        lyrics = str(result.get("lyrics") or "")
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO metadata_tracks(
                    track_id,lyrics,lyrics_source,provider_id,confidence,fetched_at,expires_at,orphaned_at
                ) VALUES (?,?,?,?,?,?,?,0)""",
                (
                    track_id, lyrics, str(result.get("source") or ""), str(result.get("provider_id") or ""),
                    float(result.get("confidence") or 0), now, now + (POSITIVE_TTL if lyrics else NEGATIVE_TTL),
                ),
            )

    def _download_artwork(self, url, source=""):
        url = str(url or "").strip()
        if not url:
            return ""
        with self._connect() as conn:
            cached = conn.execute("SELECT id,path FROM metadata_assets WHERE source_url=? ORDER BY fetched_at DESC LIMIT 1", (url,)).fetchone()
            if cached and os.path.isfile(cached["path"]):
                return str(cached["id"])
        request = urllib.request.Request(url, headers={"User-Agent": "fnAudio/0.1", "Referer": "https://music.163.com/" if source == "netease" else ""})
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
        os.makedirs(self.artwork_dir, exist_ok=True)
        path = os.path.join(self.artwork_dir, asset_id + extension)
        if not os.path.isfile(path):
            temporary = path + ".tmp"
            with open(temporary, "wb") as fh:
                fh.write(body)
            os.replace(temporary, path)
        now = int(time.time())
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO metadata_assets(id,path,mime,size,source_url,fetched_at,last_accessed) VALUES (?,?,?,?,?,?,?)",
                (asset_id, path, mime, len(body), url, now, now),
            )
        return asset_id

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
        for row in removed_entities:
            conn.execute("DELETE FROM metadata_jobs WHERE job_key=?", ("%s:%s" % (row["entity_type"], row["entity_key"]),))
        for row in removed_tracks:
            conn.execute("DELETE FROM metadata_jobs WHERE job_key=?", ("lyrics:" + row["track_id"],))
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
            self._upsert_job(conn, "lyrics:" + track_id, "lyrics", track_id, dict(track), 5, True)
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
        try:
            with self._connect() as conn:
                counts = {row["status"]: int(row["count"]) for row in conn.execute("SELECT status,COUNT(*) AS count FROM metadata_jobs GROUP BY status")}
                entity_count = int(conn.execute("SELECT COUNT(*) FROM metadata_entities WHERE orphaned_at=0").fetchone()[0])
                lyrics_count = int(conn.execute("SELECT COUNT(*) FROM metadata_tracks WHERE lyrics<>'' AND orphaned_at=0").fetchone()[0])
        except sqlite3.Error as exc:
            self.last_error = str(exc)
        return {
            "ok": True,
            "enabled": bool(self.config.get("metadata_enabled", True)),
            "running": bool(self.thread and self.thread.is_alive()),
            "active_job": self.active_job,
            "jobs": counts,
            "entities": entity_count,
            "lyrics": lyrics_count,
            "last_reconcile": self.last_reconcile,
            "last_error": self.last_error,
            "spotify_configured": bool(self.config.get("spotify_client_id") and self.config.get("spotify_client_secret")),
            "spotify_client_id": str(self.config.get("spotify_client_id") or ""),
            "orphan_grace_days": int(self.config.get("metadata_orphan_grace_days") or 7),
        }


__all__ = [
    "MetadataProviders", "MetadataService", "contains_cjk", "entity_key",
    "normalize_release_date", "normalize_text", "provider_score", "read_local_lyrics",
]

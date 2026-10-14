from __future__ import annotations

import copy
import gzip
import hashlib
import json
import math
import mimetypes
import os
import re
import signal
import sqlite3
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict

from version import APP_USER_AGENT
from contextlib import contextmanager

from library import (
    find_ffprobe,
    id3_tag,
    library_db_path,
    library_scan_is_running,
    read_cover,
    read_id3_cover,
)
from cover_media_type import SNIFF_PREFIX_BYTES, safe_image_media_type
from id3_parser import iter_id3_frames
from library_rows import decode_item_payload
from metadata_text import parse_track_number
from resource_limits import ResourceLimitError, bounded_int, disk_has_reserve
from metadata_queue_policy import project_queue_state, saturating_counter
import library_self_write
import metadata_queue_backlog_policy
from metadata_provider_failure_policy import provider_activity_snapshot, provider_failure_snapshot
from metadata_provider_availability_policy import provider_is_available
from summary_values import nonnegative_int
from ape_tag_parser import parse_ape_body, parse_ape_items

MAX_FFPROBE_LYRICS_BYTES = 2 * 1024 * 1024
from file_permissions import preserve_owner_and_mode, secure_directory, secure_file, secure_sqlite_files
from transcode import find_ffmpeg
from audio_fingerprint import capability as fingerprint_capability, fingerprint as audio_fingerprint
from embedded_lyrics import extract_embedded_lyrics
from metadata_release_date import normalize_release_date
from metadata_provider_payload import (
    MAX_PROVIDER_CANDIDATES, candidate_has_displayable_fields,
    candidate_mappings, candidate_payload_is_sequence, candidate_text_is_corrupt,
)
from metadata_lyrics_cache_policy import cached_lyrics_is_fresh
from metadata_local_lyrics_cache import LocalLyricsCache, bytes_limit_from_config, combined_snapshot
from metadata_match_policy import normalize_text, provider_score
from metadata_retry_policy import should_auto_retry_failed
from metadata_request_budget import (
    DEFAULT_JOB_BUDGET_SECONDS,
    LYRICS_JOB_BUDGET_SECONDS,
    MAX_JOB_BUDGET_SECONDS,
    MUSICBRAINZ_REQUEST_TIMEOUT_SECONDS,
    bounded_job_budget,
    provider_timeout,
)
from metadata_track_enrichment_policy import has_local_artwork, needs_track_enrichment
from metadata_track_page_overlay import project_match_fields, visible_match_projection_signature
from metadata_track_candidate_policy import project_track_candidate_fields
from metadata_track_match_policy import (
    decode_track_match_fields, normalize_track_candidates,
    track_match_fields_are_valid, valid_artwork_id,
)
from metadata_track_id_policy import normalize_track_id
from metadata_provider_response import (
    MAX_PROVIDER_RESPONSE_BYTES, MAX_PROVIDER_LYRICS_BYTES,
    MAX_PROVIDER_LYRICS_BASE64_CHARS,
    read_response_limited as _read_response_limited,
    decompress_gzip_limited as _decompress_gzip_limited,
    decode_provider_json as _decode_provider_json,
    decode_lyrics_text as _decode_lyrics_text,
    decode_base64_lyrics as _decode_base64_lyrics,
    lyrics_document as _lyrics_document,
)
from metadata_provider_values import provider_text as _provider_text, provider_int as _provider_int
from metadata_artwork_policy import artwork_url, normalize_artwork_id
from metadata_artwork_file import open_bounded_artwork, read_bounded_artwork
from metadata_remote_url_policy import public_metadata_http_url
from metadata_query_policy import entity_search_query, filename_track_candidate, filename_track_hint, local_track_candidate, track_search_query
from metadata_candidate_cache_key import build_candidate_cache_key
from metadata_provider_routing_policy import contains_cjk
from metadata_candidate_search_policy import finalize_track_candidates, prefer_track_candidate, should_stop_track_candidate_search
from metadata_numeric_policy import bounded_epoch, finite_confidence, strict_nonnegative_int
from metadata_job_policy import retry_attempt, retry_delay_seconds, worker_status
from metadata_job_payload_policy import project_metadata_job_payload
from process_error_policy import process_error_text


class _NoMetadataRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_METADATA_HTTP_OPENER = urllib.request.build_opener(_NoMetadataRedirect())


def _run_media_process(command, *, stdout, stderr, timeout, env, output_limit=None):
    """Run real media helpers in a private session and reap timed-out trees."""
    def check_output_limit():
        if output_limit is None:
            return
        for stream in (stdout, stderr):
            if not hasattr(stream, "tell"):
                continue
            try:
                position = stream.tell()
                stream.seek(0, os.SEEK_END)
                size = stream.tell()
                stream.seek(position, os.SEEK_SET)
            except (OSError, ValueError, AttributeError):
                continue
            if size > output_limit:
                raise ResourceLimitError("media process output is too large")

    if getattr(subprocess.run, "__module__", "") == "unittest.mock":
        result = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=timeout, env=env, check=False)
        check_output_limit()
        return result
    process = subprocess.Popen(
        command, stdout=stdout, stderr=stderr, env=env,
        start_new_session=(os.name != "nt"),
    )
    try:
        if output_limit is None:
            process.wait(timeout=timeout)
        else:
            deadline = time.monotonic() + timeout
            while process.poll() is None:
                check_output_limit()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                time.sleep(min(0.05, remaining))
            process.wait(timeout=0)
            check_output_limit()
    except subprocess.TimeoutExpired:
        try:
            if os.name != "nt":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except (OSError, ProcessLookupError):
            pass
        try:
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass
        raise
    except Exception:
        try:
            if process.poll() is None:
                if os.name != "nt":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
        except (OSError, ProcessLookupError, subprocess.TimeoutExpired):
            pass
        try:
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass
        raise
    return process


def _file_revision(path):
    """Return a cheap source identity for guarding destructive replacements."""
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)


def _open_metadata_url(request, timeout):
    """Open provider URLs without allowing a response to redirect to LAN."""
    return _METADATA_HTTP_OPENER.open(request, timeout=timeout)


def _entity_raw_json(result):
    """Persist bounded provider diagnostics without retaining opaque payloads."""
    result = result if isinstance(result, dict) else {}
    payload = {
        "artist": _provider_text(result.get("artist"), 512),
        "release_date": normalize_release_date(result.get("release_date")),
        "image_url": _provider_text(result.get("image_url"), MAX_ARTWORK_URL_LENGTH),
        "source": _provider_text(result.get("source"), 64),
        "provider_id": _provider_text(result.get("provider_id"), 128),
        "confidence": finite_confidence(result.get("confidence")),
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return encoded if len(encoded.encode("utf-8")) <= MAX_ENTITY_RAW_JSON_BYTES else "{}"


POSITIVE_TTL = 30 * 24 * 60 * 60
NEGATIVE_TTL = 6 * 60 * 60
DEFAULT_ORPHAN_GRACE = 7 * 24 * 60 * 60
METADATA_CACHE_VERSION = "3"
ARTWORK_ID_SANITIZE_VERSION = "1"
TAG_WRITE_BACKFILL_VERSION = "1"
TAG_WRITE_BACKFILL_BATCH_SIZE = 64
MAX_ALBUM_TAG_WRITE_TRACKS = 2048
MAX_ARTWORK_BYTES = 8 * 1024 * 1024
MAX_ARTWORK_URL_LENGTH = 2048
ARTWORK_PRUNE_BATCH_SIZE = 64
ORPHAN_CLEANUP_BATCH_SIZE = 64
MAX_APE_TAG_BYTES = 16 * 1024 * 1024
MAX_TAG_WRITE_STDERR_BYTES = 64 * 1024
SQLITE_LOCK_RETRY_DELAYS = (0.05, 0.15, 0.45)
MAX_ENTITY_RAW_JSON_BYTES = 64 * 1024
TAG_WRITABLE_EXTENSIONS = {".mp3", ".flac", ".m4a", ".mp4", ".ape", ".wav", ".dsf"}
RUNNING_JOB_STALE_SECONDS = 15 * 60
# `/api/health`, `/api/diagnostics` and the metadata page can ask for the
# same aggregate in a single UI refresh. Keep this deliberately short: it
# coalesces bursty readers without turning the metadata queue into stale
# state. Mutating job paths also invalidate it eagerly.
STATUS_CACHE_TTL_SECONDS = 0.75


def _cache_entry_is_fresh(cached_at, now, ttl):
    """Reject malformed in-process cache timestamps without coercion."""
    if isinstance(cached_at, bool) or not isinstance(cached_at, (int, float)):
        return False
    try:
        cached_at = float(cached_at)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(cached_at) and 0 <= now - cached_at < ttl


def _finite_monotonic(value, default=0.0):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if math.isfinite(number) else default


def _success_age_seconds(last_at, now):
    """Return a bounded success age; malformed timestamps are stale evidence."""
    if isinstance(last_at, bool) or not isinstance(last_at, (int, float)):
        return 3600
    try:
        timestamp = float(last_at)
    except (TypeError, ValueError, OverflowError):
        return 3600
    if not math.isfinite(timestamp) or timestamp <= 0:
        return 3600
    return min(3600, int(max(0.0, now - timestamp)))
TRACK_PAGE_CACHE_TTL_SECONDS = 0.5
MAX_TRACK_PAGE_ITEMS = 500
MAX_GROUP_ENRICH_ITEMS = 5000
MAX_GROUP_ENRICH_QUERY_ITEMS = 400
PROVIDER_CANDIDATE_CACHE_TTL_SECONDS = 2.0
PROVIDER_CANDIDATE_CACHE_MAX_ENTRIES = 128
TRACK_PAGE_CACHE_MAX_ENTRIES = 24
PROVIDER_STATE_MAX_ENTRIES = 32
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


def _read_artwork_file(path):
    """Read a local artwork input with the same bound as provider artwork."""
    return read_bounded_artwork(path, MAX_ARTWORK_BYTES)


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
    """Build an APIC frame whose MIME provably describes the picture.

    This is the one place fnAudio writes a MIME string into a user file, and
    the value it is handed can originate in a provider response header or a
    cache row, so a type the bytes cannot support is replaced rather than
    persisted.
    """
    media_type = safe_image_media_type(mime, body) or "image/jpeg"
    return _id3_frame("APIC", b"\x03" + media_type.encode("ascii", "ignore") + b"\x00\x03\x00" + body)


def _preserved_id3_frames(path, replaced_frames=None):
    """Copy the frames this write does not manage into the replacement tag.

    The shared walker is the only reader that knows about tag-level flags and
    unsupported layouts, so going through it is what keeps a picture or comment
    alive when the existing tag has an extended header or is unsynchronised.
    Stuffed ``0x00`` bytes are removed here because the tag this function builds
    declares no flags.

    The rebuilt tag is written with v2.3 frame headers that declare no flags at
    all, so a frame whose own flags announced a transform this reader cannot
    undo cannot be copied honestly: keeping it would relabel zlib or cipher
    bytes as plain text and quietly destroy what the tagger stored.  Those
    frames are dropped instead, which is the cost the read-side refusal shares
    with this function.  Frames that only carry an undoable v2.4 transform are
    untransformed first, so the flagless copy is correct text.
    """
    header, payload = id3_tag(path)
    if not header or not payload:
        return []
    major = int(header[3] or 3)
    replaced = set(replaced_frames or _ID3_MANAGED_FRAMES)
    return [
        _id3_frame(frame_id, body)
        for frame_id, body in iter_id3_frames(payload, major, header[5])
        if frame_id not in replaced
    ]


def _resolved_id3_cover(source, data):
    """Return the ``(mime, bytes)`` picture this write should store, if any.

    Without a replacement file the picture already in the source is kept, which
    is exactly why the caller has to learn about it: a write that appends a
    cover has to claim the old APIC frame as replaced, or the tag gains another
    copy of the same image every time metadata is written back.
    """
    cover_mime, cover_body = read_id3_cover(source)
    if data.get("artwork_path"):
        candidate = _read_artwork_file(data["artwork_path"])
        if candidate:
            cover_body = candidate
            cover_mime = data.get("artwork_mime") or "image/jpeg"
    return str(cover_mime or ""), cover_body or b""


def _managed_id3_frames(data, cover_mime, cover_body):
    """Return ``(frames, frame_ids)`` for the frames this write supplies itself.

    The id set has to cover exactly the frames appended here.  Preserving a
    frame that is also re-written duplicates it, and a duplicated picture grows
    the tag by the image size on every write until it passes the bounded reader
    budget and the whole tag stops being readable.
    """
    frames = []
    replaced = set()
    for key, frame_id in _ID3_TEXT_FRAMES.items():
        value = str(data.get(key) or "").replace("\x00", "").strip()
        if not value:
            continue
        replaced.add(frame_id)
        frames.append(_id3_text_frame(frame_id, value))
    lyrics = str(data.get("lyrics") or "").replace("\x00", "").strip()
    if lyrics:
        replaced.add("USLT")
        frames.append(_id3_uslt_frame(lyrics))
    if cover_body:
        replaced.add("APIC")
        frames.append(_id3_apic_frame(cover_mime, cover_body))
    return frames, replaced

def _write_dsf_tags(source, temporary, data):
    """Replace only DSF's trailing ID3v2 block, never its DSD payload."""
    try:
        source_size = os.path.getsize(source)
    except OSError as exc:
        raise RuntimeError("unable to stat DSF source") from exc
    with open(source, "rb") as handle:
        header = handle.read(28)
    if len(header) < 28 or header[:4] != b"DSD ":
        raise RuntimeError("invalid DSF header")
    metadata_offset = int.from_bytes(header[20:28], "little")
    if metadata_offset < 28 or metadata_offset > source_size:
        raise RuntimeError("invalid DSF metadata offset")
    cover_mime, cover_body = _resolved_id3_cover(source, data)
    managed_frames, replaced = _managed_id3_frames(data, cover_mime, cover_body)
    frames = _preserved_id3_frames(source, replaced) + managed_frames
    tag_payload = b"".join(frames)
    tag = b"ID3\x03\x00\x00" + _id3_syncsafe(len(tag_payload)) + tag_payload
    output_size = metadata_offset + len(tag)
    with open(source, "rb") as source_handle, open(temporary, "wb") as target_handle:
        remaining = metadata_offset
        while remaining:
            block = source_handle.read(min(1024 * 1024, remaining))
            if not block:
                raise RuntimeError("truncated DSF payload")
            target_handle.write(block)
            remaining -= len(block)
        target_handle.write(tag)
        target_handle.seek(12)
        target_handle.write(output_size.to_bytes(8, "little"))


def _write_wav_tags(source, temporary, data):
    """Store managed metadata in a RIFF ID3 chunk without remuxing WAV audio."""
    cover_mime, cover_body = _resolved_id3_cover(source, data)
    managed_frames, replaced = _managed_id3_frames(data, cover_mime, cover_body)
    frames = _preserved_id3_frames(source, replaced) + managed_frames
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
    # Keep this compatibility entry point bounded.  APE tags live at EOF, so
    # use the same offset-based reader as writes instead of materializing the
    # whole high-resolution audio file.
    return _ape_tag_info(source)


def _ape_tag_info(source):
    """Read only the bounded APE tag footer and return (audio_end, items)."""
    try:
        source_size = os.path.getsize(source)
        if source_size < 32:
            return source_size, []
        with open(source, "rb") as handle:
            handle.seek(source_size - 32)
            footer = handle.read(32)
            if footer[:8] != b"APETAGEX":
                return source_size, []
            total = int.from_bytes(footer[12:16], "little")
            count = int.from_bytes(footer[16:20], "little")
            if total < 32 or total > MAX_APE_TAG_BYTES or total > source_size or count > 4096:
                return source_size, []
            start = source_size - total
            handle.seek(start)
            body = handle.read(total - 32)
    except (OSError, ValueError):
        return source_size if "source_size" in locals() else 0, []
    items = parse_ape_items(body, count)
    if items is None:
        return start, []
    return start, items


def _ape_item(key, value, flags=b"\x00\x00\x00\x00"):
    encoded_key = str(key).encode("utf-8")
    return len(value).to_bytes(4, "little") + bytes(flags[:4]).ljust(4, b"\x00") + encoded_key + b"\x00" + value


def _write_ape_tags(source, temporary, data):
    audio_end, existing = _ape_tag_info(source)
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
        image = _read_artwork_file(data["artwork_path"])
        if image:
            replacement["cover art (front)"] = ("Cover Art (Front)", b"\x02\x00\x00\x00", b"cover" + b"\x00" + image)
    # Only replace fields supplied by this job. In particular CUE entries
    # share a single source file: their artwork can be refreshed safely but
    # their per-track title/lyrics must not erase the source's existing Tags.
    items = [item for item in existing if item[0].casefold() not in replacement]
    items.extend(replacement.values())
    payload = b"".join(_ape_item(key, value, flags) for key, flags, value in items)
    footer = b"APETAGEX" + (2000).to_bytes(4, "little") + (len(payload) + 32).to_bytes(4, "little") + len(items).to_bytes(4, "little") + (0).to_bytes(4, "little") + b"\x00" * 8
    with open(source, "rb") as source_handle, open(temporary, "wb") as handle:
        remaining = audio_end
        while remaining:
            block = source_handle.read(min(1024 * 1024, remaining))
            if not block:
                raise RuntimeError("truncated APE audio payload")
            handle.write(block)
            remaining -= len(block)
        handle.write(payload)
        handle.write(footer)


def entity_key(entity_type, name, artist=""):
    name_key = normalize_text(name)
    if entity_type == "album":
        return "%s|%s" % (name_key, normalize_text(artist))
    return name_key


def _artist_name(value):
    """Read one provider artist name without coercing hostile payloads."""
    if isinstance(value, str):
        return value.strip()[:512]
    if isinstance(value, dict):
        name = value.get("name")
        return name.strip()[:512] if isinstance(name, str) else ""
    if isinstance(value, (list, tuple)) and value:
        # Existing matching semantics use the first credited artist. Keep the
        # traversal bounded and ignore malformed entries rather than allowing
        # an arbitrary provider object to raise or stringify.
        for item in value[:8]:
            name = _artist_name(item)
            if name:
                return name
    return ""


def _artist_names(value):
    """Project a bounded list of credited artists without coercing objects."""
    if not isinstance(value, (list, tuple)):
        return ""
    names = []
    for item in value[:8]:
        name = _artist_name(item)
        if name and name not in names:
            names.append(name)
    return " / ".join(names)[:512]


def _provider_name(provider, fallback="provider"):
    """Return a stable bounded adapter label without coercing arbitrary objects."""
    for attribute in ("__name__", "_mock_name"):
        try:
            value = getattr(provider, attribute, "")
        except Exception:
            value = ""
        if isinstance(value, str) and value.strip():
            return value.strip()[:32]
    return fallback


class MetadataProviders:
    def __init__(self, config):
        self.config = config
        # Provider failures are observed per worker invocation as well as in
        # the shared diagnostics map.  The thread-local marker prevents a
        # concurrent worker's failure from changing this job's no_match/failed
        # classification.
        self._failure_local = threading.local()
        self._failure_lock = threading.Lock()
        self._provider_failures = {}
        self._provider_successes = {}
        # Successful transport with no usable recording is distinct from a
        # provider outage. Keep bounded counters for support diagnostics.
        self._provider_empty_results = {}
        self._provider_no_valid_candidates = {}
        self._provider_cooldown_until = {}
        self._provider_cooldown_seconds = 20
        # Interactive polling can ask for the same track several times while
        # a worker transitions from pending to done. Keep a tiny process-local
        # positive cache so those polls do not fan out to every provider again.
        # Empty/error results are deliberately not cached: a later poll must
        # still be able to recover after a transient provider outage.
        self._candidate_cache = OrderedDict()
        self._candidate_cache_lock = threading.RLock()
        self._candidate_cache_hits = 0
        self._candidate_cache_misses = 0
        self._local_lyrics_cache = LocalLyricsCache(
            lambda path: read_local_lyrics(path, self.config),
            max_bytes=bytes_limit_from_config(self.config),
        )

    def reset_provider_cooldowns(self):
        """Let an explicit user retry probe cooled providers immediately."""
        with self._failure_lock:
            self._provider_cooldown_until.clear()

    def _read_local_lyrics_cached(self, path, version_hint=None):
        return self._local_lyrics_cache.read(path, version_hint)

    def candidate_cache_snapshot(self):
        """Return bounded diagnostics for the interactive candidate cache."""
        with self._candidate_cache_lock:
            return {
                "entries": min(PROVIDER_CANDIDATE_CACHE_MAX_ENTRIES, len(self._candidate_cache)),
                "limit": PROVIDER_CANDIDATE_CACHE_MAX_ENTRIES,
                # Diagnostics must remain available even if an adapter or a
                # previous process left a malformed counter behind.  Do not
                # invoke arbitrary ``__int__`` implementations here.
                "hits": nonnegative_int(self._candidate_cache_hits, maximum=1000000),
                "misses": nonnegative_int(self._candidate_cache_misses, maximum=1000000),
                "ttl_ms": int(PROVIDER_CANDIDATE_CACHE_TTL_SECONDS * 1000),
            }

    def _ensure_provider_slot_locked(self, name):
        """Keep provider diagnostics bounded even if adapter names drift."""
        if name in self._provider_failures or name in self._provider_successes or name in self._provider_empty_results or name in self._provider_no_valid_candidates or name in self._provider_cooldown_until:
            return
        names = set(self._provider_failures) | set(self._provider_successes) | set(self._provider_empty_results) | set(self._provider_no_valid_candidates) | set(self._provider_cooldown_until)
        if len(names) < PROVIDER_STATE_MAX_ENTRIES:
            return

        def last_seen(provider_name):
            failure = self._provider_failures.get(provider_name) or {}
            success = self._provider_successes.get(provider_name) or {}
            values = []
            for entry in (failure, success):
                if isinstance(entry, dict):
                    values.append(_finite_monotonic(entry.get("last_at", 0.0)))
            return max(values or [0.0])

        # Empty-result and no-valid-candidate counters carry no timestamp, so
        # several names share one last-seen value. Breaking the tie by name
        # keeps eviction reproducible; set iteration order does not.
        evicted = min(
            names,
            key=lambda provider_name: (last_seen(provider_name), provider_name),
        )
        self._provider_failures.pop(evicted, None)
        self._provider_successes.pop(evicted, None)
        self._provider_empty_results.pop(evicted, None)
        self._provider_no_valid_candidates.pop(evicted, None)
        self._provider_cooldown_until.pop(evicted, None)

    def _provider_is_available(self, provider):
        name = str(provider or "unknown")[:32]
        with self._failure_lock:
            cooldown_until = self._provider_cooldown_until.get(name, 0.0)
        deadline = getattr(self._failure_local, "deadline", None)
        available = provider_is_available(cooldown_until, deadline, time.monotonic())
        if not available:
            # A cooled source or an exhausted request budget is not evidence
            # that the recording does not exist. Mark the active job as
            # incompletely searched so it becomes retryable `failed` instead
            # of a long-lived `no_match` negative cache. The marker is local
            # to this worker observation and does not extend the cooldown.
            self._failure_local.seen = True
        return available

    @staticmethod
    def _normalize_track_input(track):
        """Materialize sqlite rows before provider adapters call ``.get``."""
        if isinstance(track, sqlite3.Row):
            try:
                return {key: track[key] for key in list(track.keys())[:64]}
            except (AttributeError, IndexError, KeyError, TypeError):
                return {}
        return track

    def _record_provider_success(self, provider):
        name = str(provider or "unknown")[:32]
        with self._failure_lock:
            self._ensure_provider_slot_locked(name)
            entry = self._provider_successes.get(name, {"count": 0, "last_at": 0.0})
            entry["count"] = min(1000000, nonnegative_int(entry.get("count", 0), maximum=1000000) + 1)
            entry["last_at"] = time.monotonic()
            self._provider_successes[name] = entry
            self._provider_cooldown_until.pop(name, None)
            # A valid response with no matching song is still a successful
            # provider request. Forget the old transport/schema failure streak
            # so one later transient error does not immediately re-cool an
            # otherwise recovered source.
            self._provider_failures.pop(name, None)

    def _record_provider_outcome(self, provider, outcome):
        """Record bounded, non-sensitive no-match shape diagnostics."""
        name = str(provider or "unknown")[:32]
        target = self._provider_empty_results if outcome == "empty" else self._provider_no_valid_candidates
        with self._failure_lock:
            self._ensure_provider_slot_locked(name)
            target[name] = min(1000000, nonnegative_int(target.get(name, 0), maximum=1000000) + 1)

    def _record_provider_failure(self, provider, error):
        """Keep a tiny, redacted provider failure summary for diagnostics."""
        name = str(provider or "unknown")[:32]
        detail = re.sub(r"https?://\S+", "[url]", str(error or "provider error").replace("\n", " "))
        message = (type(error).__name__ + ": " + detail)[:240]
        self._failure_local.seen = True
        with self._failure_lock:
            self._ensure_provider_slot_locked(name)
            entry = self._provider_failures.get(name, {"count": 0, "last_error": "", "last_at": 0.0})
            entry["count"] = min(1000000, nonnegative_int(entry.get("count", 0), maximum=1000000) + 1)
            entry["last_error"] = message
            entry["last_at"] = time.monotonic()
            self._provider_failures[name] = entry
            if entry["count"] >= 2:
                self._provider_cooldown_until[name] = time.monotonic() + self._provider_cooldown_seconds

    def begin_job_observation(self, budget_seconds=None):
        self._failure_local.seen = False
        self._failure_local.deadline = (
            time.monotonic() + bounded_job_budget(budget_seconds)
            if budget_seconds is not None else None
        )

    def end_job_observation(self):
        """Do not leak a spent worker budget into an unrelated later call."""
        self._failure_local.deadline = None

    def job_observed_provider_failure(self):
        return bool(getattr(self._failure_local, "seen", False))

    def failure_snapshot(self):
        with self._failure_lock:
            now = time.monotonic()
            snapshot = {}
            for name, value in list(self._provider_failures.items())[:16]:
                entry = dict(value)
                remaining = max(0.0, _finite_monotonic(self._provider_cooldown_until.get(name, 0.0)) - now)
                entry["cooldown_seconds"] = min(60, int(remaining + 0.999)) if remaining > 0 else 0
                snapshot[name] = entry
            return provider_failure_snapshot(snapshot)

    def activity_snapshot(self):
        """Return bounded reachability evidence without query or payload data."""
        with self._failure_lock:
            now = time.monotonic()
            snapshot = {}
            for name, value in list(self._provider_successes.items())[:16]:
                age = _success_age_seconds(value.get("last_at", 0.0), now) if isinstance(value, dict) else 3600
                snapshot[name] = {
                    "successes": nonnegative_int(value.get("count", 0), maximum=1000000) if isinstance(value, dict) else 0,
                    "last_success_seconds_ago": age,
                    "empty_results": nonnegative_int(self._provider_empty_results.get(name, 0), maximum=1000000),
                    "no_valid_candidates": nonnegative_int(self._provider_no_valid_candidates.get(name, 0), maximum=1000000),
                }
            for name in set(self._provider_empty_results) | set(self._provider_no_valid_candidates):
                if name not in snapshot and len(snapshot) < 16:
                    snapshot[name] = {
                        "successes": 0,
                        "last_success_seconds_ago": 0,
                        "empty_results": nonnegative_int(self._provider_empty_results.get(name, 0), maximum=1000000),
                        "no_valid_candidates": nonnegative_int(self._provider_no_valid_candidates.get(name, 0), maximum=1000000),
                    }
            return provider_activity_snapshot(snapshot)

    def _json(self, url, headers=None, data=None, timeout=10):
        url = public_metadata_http_url(url)
        if not url:
            raise ValueError("metadata provider URL is not a public HTTP(S) URL")
        remaining_timeout = provider_timeout(getattr(self._failure_local, "deadline", None), time.monotonic(), timeout)
        if remaining_timeout <= 0:
            raise TimeoutError("metadata provider time budget exhausted")
        request_headers = dict(headers) if isinstance(headers, dict) else {}
        # A few public catalog endpoints silently return an empty/blocked
        # payload to Python's default user agent.  Keep a conservative browser
        # identity at the common request boundary so a newly added adapter
        # cannot accidentally lose metadata retrieval just because it omitted
        # its own header. Provider-specific headers still take precedence.
        request_headers.setdefault("User-Agent", "Mozilla/5.0 (compatible; fnAudio/1.0)")
        # Keep provider responses deterministic across proxies/WebViews.  We
        # explicitly opt into only gzip, which is handled below with a strict
        # decompressed-size bound; this prevents an unexpected Brotli payload
        # from being passed to the JSON decoder as if it were UTF-8 text.
        request_headers.setdefault("Accept", "application/json")
        request_headers.setdefault("Accept-Encoding", "gzip")
        request = urllib.request.Request(url, headers=request_headers, data=data)
        try:
            with _open_metadata_url(request, remaining_timeout) as response:
                payload = _read_response_limited(response, MAX_PROVIDER_RESPONSE_BYTES)
                if response.headers.get("Content-Encoding", "").lower() == "gzip" or payload.startswith(b"\x1f\x8b"):
                    payload = _decompress_gzip_limited(payload, MAX_PROVIDER_RESPONSE_BYTES)
                return _decode_provider_json(payload, response.headers.get("Content-Type", ""))
        except urllib.error.HTTPError as exc:
            # HTTPError is also a file-like response. Provider fallbacks catch
            # it at a higher level, so close it here before re-raising.
            exc.close()
            raise

    def _text(self, url, headers=None, data=None, timeout=10, limit=MAX_PROVIDER_LYRICS_BYTES):
        """Fetch bounded provider text within the current job's total budget.

        Some lyric adapters need a second request for the actual LRC/JSONP
        body.  Keep that path subject to exactly the same deadline as JSON
        search calls; otherwise a slow source can outlive the interactive
        lyrics poll window even after the search chain has been budgeted.
        """
        url = public_metadata_http_url(url)
        if not url:
            raise ValueError("metadata provider URL is not a public HTTP(S) URL")
        remaining_timeout = provider_timeout(getattr(self._failure_local, "deadline", None), time.monotonic(), timeout)
        if remaining_timeout <= 0:
            raise TimeoutError("metadata provider time budget exhausted")
        request_headers = dict(headers) if isinstance(headers, dict) else {}
        request_headers.setdefault("User-Agent", "Mozilla/5.0 (compatible; fnAudio/1.0)")
        request_headers.setdefault("Accept", "text/plain, application/json;q=0.9, */*;q=0.1")
        request_headers.setdefault("Accept-Encoding", "gzip")
        request = urllib.request.Request(url, headers=request_headers, data=data)
        # Only accept plain finite numeric limits. Provider adapters are
        # third-party-shaped inputs; never invoke custom ``__int__`` or allow
        # a malformed value to widen the response budget.
        if isinstance(limit, bool) or not isinstance(limit, (int, float)):
            bounded_limit = MAX_PROVIDER_LYRICS_BYTES
        else:
            try:
                bounded_limit = min(MAX_PROVIDER_LYRICS_BYTES, max(1, int(limit)))
            except (TypeError, ValueError, OverflowError):
                bounded_limit = MAX_PROVIDER_LYRICS_BYTES
        try:
            with _open_metadata_url(request, remaining_timeout) as response:
                payload = _read_response_limited(response, bounded_limit)
                if response.headers.get("Content-Encoding", "").lower() == "gzip" or payload.startswith(b"\x1f\x8b"):
                    payload = _decompress_gzip_limited(payload, bounded_limit)
                return _decode_lyrics_text(payload)
        except urllib.error.HTTPError as exc:
            # Keep this symmetric with _json: callers may catch the failure to
            # try another lyric provider, but the underlying response is ours.
            exc.close()
            raise

    def netease_album(self, name, artist=""):
        query = entity_search_query(name, artist)
        if not query:
            return None
        url = "https://music.163.com/api/search/get/web?type=10&limit=20&s=" + urllib.parse.quote(query)
        data = self._json(url, {"User-Agent": "Mozilla/5.0", "Referer": "https://music.163.com/"})
        best = None
        best_score = 0
        for item in candidate_mappings((data.get("result") or {}).get("albums")):
            item_artist = _artist_name(item.get("artist") or item.get("artists") or [])
            score = provider_score(item.get("name"), name, item_artist, artist)
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.55:
            return None
        # Provider timestamps are untrusted.  The shared normalizer bounds
        # conversion and absorbs invalid or out-of-range epoch values instead
        # of letting one malformed album result fail the whole metadata job.
        release_date = normalize_release_date(best.get("publishTime"))
        return {
            "name": best.get("name") or name,
            "artist": _artist_name(best.get("artist") or best.get("artists") or []) or artist,
            "release_date": release_date,
            "image_url": best.get("picUrl") or "",
            "provider_id": _provider_text(best.get("id"), 128),
            "source": "netease",
            "confidence": best_score,
        }

    def netease_person(self, name):
        url = "https://music.163.com/api/search/get/web?type=100&limit=10&s=" + urllib.parse.quote(name)
        data = self._json(url, {"User-Agent": "Mozilla/5.0", "Referer": "https://music.163.com/"})
        best = None
        best_score = 0
        for item in candidate_mappings((data.get("result") or {}).get("artists")):
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
            "provider_id": _provider_text(best.get("id"), 128),
            "source": "netease",
            "confidence": best_score,
        }

    def _qq_songs(self, query, limit=20):
        url = "https://c.y.qq.com/soso/fcgi-bin/client_search_cp?" + urllib.parse.urlencode({
            "format": "json", "p": 1, "n": limit, "w": query,
        })
        data = self._json(url, {"User-Agent": "Mozilla/5.0", "Referer": "https://y.qq.com/"})
        return candidate_mappings(((data.get("data") or {}).get("song") or {}).get("list"))

    def qq_album(self, name, artist=""):
        best = None
        best_score = 0
        for item in self._qq_songs(entity_search_query(name, artist)):
            singers = item.get("singer") or []
            item_artist = _artist_name(singers)
            score = provider_score(item.get("albumname"), name, item_artist, artist)
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.55:
            return None
        album_mid = _provider_text(best.get("albummid"), 128)
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
        singer_mid = _provider_text(best.get("mid"), 128)
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
        data = self._json(url, {"User-Agent": "%s (local music server)" % APP_USER_AGENT}, timeout=MUSICBRAINZ_REQUEST_TIMEOUT_SECONDS)
        best = None
        best_score = 0
        for item in candidate_mappings(data.get("release-groups")):
            credits = item.get("artist-credit") or []
            item_artist = _artist_name((credits[0].get("artist") if credits and isinstance(credits[0], dict) else ""))
            score = provider_score(item.get("title"), name, item_artist, artist)
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.55:
            return None
        release_id = _provider_text(best.get("id"), 128)
        return {
            "name": best.get("title") or name,
            "artist": _artist_name(((best.get("artist-credit") or [{}])[0].get("artist") or {})) or artist,
            "release_date": best.get("first-release-date") or "",
            "image_url": "https://coverartarchive.org/release-group/%s/front-500" % release_id if release_id else "",
            "provider_id": release_id,
            "source": "musicbrainz",
            "confidence": best_score,
        }

    def _musicbrainz_recordings(self, query, limit=10):
        """Return bounded recording results for the track metadata fallback."""
        if not isinstance(query, str) or not query.strip():
            return ()
        params = {"query": query[:512], "fmt": "json", "limit": str(min(10, max(1, int(limit or 10))))}
        data = self._json(
            "https://musicbrainz.org/ws/2/recording/?" + urllib.parse.urlencode(params),
            {"User-Agent": "%s (local music server)" % APP_USER_AGENT},
            timeout=MUSICBRAINZ_REQUEST_TIMEOUT_SECONDS,
        )
        return candidate_mappings(data.get("recordings"))

    @staticmethod
    def _musicbrainz_track_query(track):
        title = _provider_text(track.get("title")).replace('"', "")
        artist = _provider_text(track.get("artist")).replace('"', "")
        query = 'recording:"%s"' % title if title else ""
        if artist and artist.casefold() not in PLACEHOLDER_NAMES:
            query += ' AND artist:"%s"' % artist
        return query

    @staticmethod
    def _musicbrainz_track_candidate(track, item):
        releases = item.get("releases") if isinstance(item.get("releases"), list) else []
        release = {}
        # Prefer the first bounded release that has an id/title.  Recording
        # search results may contain placeholder entries before the usable
        # release; selecting blindly used to lose the only Cover Art Archive
        # reference even when the recording itself matched.
        for candidate in releases[:8]:
            if not isinstance(candidate, dict):
                continue
            release_id = _provider_text(candidate.get("id"), 128)
            release_title = _provider_text(candidate.get("title"), 512)
            if release_id or release_title:
                release = candidate
                break
        # MusicBrainz artist-credit entries wrap the actual artist under an
        # ``artist`` key; project that bounded nested value instead of asking
        # the generic artist helper to stringify the wrapper object.
        credits = item.get("artist-credit") if isinstance(item.get("artist-credit"), list) else []
        artists = _artist_name([
            entry.get("artist")
            for entry in credits[:8]
            if isinstance(entry, dict)
        ])
        release_id = _provider_text(release.get("id"), 128)
        image_url = (
            "https://coverartarchive.org/release/%s/front-500" % release_id
            if release_id else ""
        )
        return MetadataProviders._track_candidate(
            track, item, "musicbrainz", item.get("title"), artists,
            release.get("title"), artists, release.get("date"),
            "", item.get("position") or 0, image_url, item.get("id"),
        )

    def album(self, name, artist=""):
        if not entity_search_query(name, artist):
            return None
        if contains_cjk(name, artist):
            providers = (self.netease_album, self.qq_album, self.kugou_album, self.migu_album, self.joox_album, self.qianqian_album, self.musicbrainz_album)
        else:
            providers = (self.musicbrainz_album, self.netease_album, self.qq_album, self.kugou_album, self.migu_album, self.joox_album, self.qianqian_album)
        return self._first_match(providers, name, artist)

    def person(self, name):
        # Mirror the album entry guard. An absent, non-text or placeholder
        # artist must never reach an adapter: quote() raises on a non-string
        # name and adapter exceptions feed the provider failure streak, so one
        # bad queue payload would cool netease and qq for unrelated lookups.
        if not entity_search_query(name):
            return None
        return self._first_match((self.netease_person, self.qq_person), name)

    def _first_match(self, providers, *args):
        for provider in providers:
            provider_name = _provider_name(provider)
            if not self._provider_is_available(provider_name):
                continue
            try:
                result = provider(*args)
                if result:
                    # A usable entity/artwork result proves this adapter is
                    # reachable and can clear a transient failure cooldown.
                    # Empty search results are a normal provider outcome,
                    # but must not be presented as a successful retrieval in
                    # diagnostics or erase a transport failure history.
                    self._record_provider_success(provider_name)
                    return result
                self._record_provider_outcome(provider_name, "empty")
            except Exception as exc:
                # Album/artist adapters consume third-party schemas too. Keep
                # malformed JSON, missing keys and decoder drift isolated just
                # like the lyrics and track-candidate chains, so one provider
                # cannot make all metadata appear unavailable.
                self._record_provider_failure(provider_name, exc)
                continue
        return None

    def netease_lyrics(self, track):
        query = track_search_query(track)
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://music.163.com/"}
        data = self._json("https://music.163.com/api/search/get/web?type=1&limit=10&s=" + urllib.parse.quote(query), headers)
        best = None
        best_score = 0
        for item in candidate_mappings((data.get("result") or {}).get("songs")):
            item_artist = _artist_name(item.get("artists") or [])
            score = provider_score(item.get("name"), track.get("title"), item_artist, track.get("artist"))
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.55:
            return None
        provider_id = _provider_text(best.get("id"), 128)
        if not provider_id:
            return None
        lyric = self._json("https://music.163.com/api/song/lyric?lv=1&kv=1&tv=-1&id=%s" % provider_id, headers)
        text = ((lyric.get("lrc") or {}).get("lyric") or "").strip()
        return {"lyrics": text, "source": "网易云音乐", "provider_id": provider_id, "confidence": best_score} if text else None

    def netease_track_artwork(self, track):
        query = track_search_query(track)
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://music.163.com/"}
        data = self._json("https://music.163.com/api/search/get/web?type=1&limit=10&s=" + urllib.parse.quote(query), headers)
        best = None
        best_score = 0
        for item in candidate_mappings((data.get("result") or {}).get("songs")):
            score = provider_score(item.get("name"), track.get("title"), _artist_name(item.get("artists") or []), track.get("artist"))
            if score > best_score:
                best, best_score = item, score
        album = (best or {}).get("album") or {}
        image_url = _provider_text(album.get("picUrl"), MAX_ARTWORK_URL_LENGTH)
        if not best or best_score < 0.55 or not image_url:
            return None
        return {"image_url": image_url, "source": "netease", "provider_id": _provider_text(best.get("id"), 128), "confidence": best_score}

    def qq_track_artwork(self, track):
        best = None
        best_score = 0
        for item in self._qq_songs(track_search_query(track), 10):
            score = provider_score(item.get("songname"), track.get("title"), _artist_name(item.get("singer") or []), track.get("artist"))
            if score > best_score:
                best, best_score = item, score
        album_mid = _provider_text((best or {}).get("albummid"), 128)
        if not best or best_score < 0.55 or not album_mid:
            return None
        return {"image_url": "https://y.gtimg.cn/music/photo_new/T002R500x500M000%s.jpg" % album_mid, "source": "qq", "provider_id": album_mid, "confidence": best_score}

    def qq_lyrics(self, track):
        best = None
        best_score = 0
        for item in self._qq_songs(track_search_query(track), 10):
            score = provider_score(item.get("songname"), track.get("title"), _artist_name(item.get("singer") or []), track.get("artist"))
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.55 or not best.get("songmid"):
            return None
        song_mid = _provider_text(best.get("songmid"), 128)
        if not song_mid:
            return None
        url = "https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg?format=json&nobase64=0&songmid=" + urllib.parse.quote(song_mid)
        data = self._json(url, {"User-Agent": "Mozilla/5.0", "Referer": "https://y.qq.com/"})
        encoded = data.get("lyric") or ""
        if not encoded:
            return None
        text = _decode_base64_lyrics(encoded)
        return {"lyrics": text, "source": "QQ音乐", "provider_id": song_mid, "confidence": best_score} if text else None

    def _kugou_songs(self, query, limit=10):
        params = {
            "keyword": query, "platform": "WebFilter", "format": "json", "page": "1",
            "pagesize": str(limit), "userid": "-1", "tag": "em", "filter": "2",
            "iscorrection": "1", "privilege_filter": "0", "_": str(int(time.time() * 1000)),
        }
        # Kugou now redirects/blocks the legacy clear-text endpoint in many
        # NAS environments. Start on TLS so provider lookup is not lost to a
        # proxy that refuses HTTP redirects.
        url = "https://songsearch.kugou.com/song_search_v2?" + urllib.parse.urlencode(params)
        data = self._json(url, {"User-Agent": "Mozilla/5.0", "Referer": "https://www.kugou.com/"})
        return candidate_mappings((data.get("data") or {}).get("lists"))

    def kugou_album(self, name, artist=""):
        best = None
        best_score = 0
        for item in self._kugou_songs(entity_search_query(name, artist)):
            score = provider_score(item.get("AlbumName"), name, item.get("SingerName"), artist)
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.55:
            return None
        cover = _provider_text(best.get("Image"), MAX_ARTWORK_URL_LENGTH)
        if not cover:
            trans_param = best.get("trans_param") if isinstance(best.get("trans_param"), dict) else {}
            cover = _provider_text(trans_param.get("union_cover"), MAX_ARTWORK_URL_LENGTH)
        cover = cover.replace("{size}", "500")
        return {
            "name": best.get("AlbumName") or name,
            "artist": best.get("SingerName") or artist,
            "release_date": _provider_text(best.get("PublishDate") or best.get("PublishTime"), 64),
            "image_url": cover,
            "provider_id": _provider_text(best.get("AlbumID") or best.get("MixSongID") or best.get("FileHash"), 128),
            "source": "kugou",
            "confidence": best_score,
        }

    def kugou_lyrics(self, track):
        best = None
        best_score = 0
        for item in self._kugou_songs(track_search_query(track)):
            score = provider_score(item.get("SongName"), track.get("title"), item.get("SingerName"), track.get("artist"))
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.55:
            return None
        song_hash = _provider_text(best.get("FileHash"), 128)
        if not song_hash:
            return None
        try:
            duration = min(24 * 60 * 60, max(0, int(finite_confidence(best.get("Duration") or track.get("duration"))))) * 1000
        except (TypeError, ValueError, OverflowError):
            duration = 0
        search_url = "https://krcs.kugou.com/search?" + urllib.parse.urlencode({
            "ver": "1", "client": "mobi", "duration": str(duration), "hash": song_hash, "album_audio_id": "",
        })
        candidates = candidate_mappings(self._json(search_url, {"User-Agent": "Mozilla/5.0", "Referer": "https://www.kugou.com/"}).get("candidates"))
        if not candidates:
            return None
        candidate = candidates[0]
        download_url = "https://lyrics.kugou.com/download?" + urllib.parse.urlencode({
            "ver": "1", "client": "pc", "id": _provider_text(candidate.get("id"), 128),
            "accesskey": _provider_text(candidate.get("accesskey"), 256), "fmt": "lrc", "charset": "utf8",
        })
        payload = self._json(download_url, {"User-Agent": "Mozilla/5.0", "Referer": "https://www.kugou.com/"})
        # No pre-slicing: a truncated base64 document still decodes, and
        # ``decode_base64_lyrics`` is the one that refuses an over-budget field.
        encoded = payload.get("content")
        if not encoded:
            return None
        try:
            text = _decode_base64_lyrics(encoded)
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
            "https://pd.musicapp.migu.cn/MIGUM2.0/v1.0/content/search_all.do?" + urllib.parse.urlencode(params),
            {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X)", "Referer": "https://music.migu.cn/"},
        )
        return candidate_mappings((data.get("songResultData") or {}).get("result"))

    @staticmethod
    def _migu_artist(item):
        people = item.get("singers") or item.get("singerList") or item.get("artists") or []
        return _artist_names(people) or (item.get("singer") if isinstance(item.get("singer"), str) else "")

    @staticmethod
    def _migu_album_name(item):
        albums = item.get("albums") or []
        if albums and isinstance(albums[0], dict):
            return _provider_text(albums[0].get("name")) or _provider_text(item.get("album"))
        return _provider_text(item.get("album"))

    @staticmethod
    def _migu_image(item):
        seen = 0
        for images in (item.get("imgItems") or (), item.get("albumImgs") or ()):
            try:
                iterator = iter(images)
            except Exception:
                continue
            while seen < MAX_PROVIDER_CANDIDATES:
                try:
                    image = next(iterator)
                except StopIteration:
                    break
                except Exception:
                    break
                seen += 1
                if not isinstance(image, dict):
                    continue
                value = image.get("img")
                if not isinstance(value, str):
                    continue
                value = _provider_text(value, MAX_ARTWORK_URL_LENGTH)
                if value:
                    return ("https:" + value if value.startswith("//") else value)[:MAX_ARTWORK_URL_LENGTH]
        return _provider_text(item.get("img1") or item.get("img2"), MAX_ARTWORK_URL_LENGTH)

    def migu_album(self, name, artist=""):
        best = None
        best_score = 0
        for item in self._migu_songs(entity_search_query(name, artist)):
            score = provider_score(self._migu_album_name(item), name, self._migu_artist(item), artist)
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.55:
            return None
        return {
            "name": self._migu_album_name(best) or name,
            "artist": self._migu_artist(best) or artist,
            "release_date": _provider_text(best.get("publishDate"), 64),
            "image_url": self._migu_image(best),
            "provider_id": _provider_text(best.get("albumId") or ((best.get("albums") or [{}])[0].get("id") if best.get("albums") else ""), 128),
            "source": "migu",
            "confidence": best_score,
        }

    def migu_lyrics(self, track):
        best = None
        best_score = 0
        for item in self._migu_songs(track_search_query(track)):
            score = provider_score(item.get("name") or item.get("songName"), track.get("title"), self._migu_artist(item), track.get("artist"))
            if score > best_score:
                best, best_score = item, score
        content_id = _provider_text((best or {}).get("contentId"), 128)
        if not best or best_score < 0.55 or not content_id:
            return None
        url = "https://c.musicapp.migu.cn/MIGUM2.0/v1.0/content/resourceinfo.do?" + urllib.parse.urlencode({"resourceId": content_id, "resourceType": "2"})
        data = self._json(url, {"User-Agent": "Mozilla/5.0", "Referer": "https://music.migu.cn/"})
        resource = (data.get("resource") or [{}])[0]
        lyric_url = _provider_text(resource.get("lrcUrl") or resource.get("lyricUrl"), MAX_ARTWORK_URL_LENGTH)
        if not lyric_url:
            return None
        lyric_url = lyric_url.replace("http://", "https://", 1)
        text = self._text(
            lyric_url,
            {"User-Agent": "Mozilla/5.0", "Referer": "https://y.migu.cn/"},
        )
        return {"lyrics": text, "source": "migu", "provider_id": content_id, "confidence": best_score} if text else None

    def _joox_songs(self, query):
        url = "https://cache.api.joox.com/openjoox/v3/search?" + urllib.parse.urlencode({"country": "sg", "lang": "zh_cn", "keyword": query})
        data = self._json(url, {"User-Agent": "Mozilla/5.0", "X-Forwarded-For": "101.32.0.1"})
        songs = []
        for section in candidate_mappings(data.get("section_list")):
            for item in candidate_mappings(section.get("item_list")):
                for song in candidate_mappings(item.get("song")):
                    info = song.get("song_info") or {}
                    if info.get("id"):
                        songs.append(info)
                        if len(songs) >= MAX_PROVIDER_CANDIDATES:
                            return tuple(songs)
        return tuple(songs)

    def _joox_albums(self, query):
        url = "https://cache.api.joox.com/openjoox/v3/search?" + urllib.parse.urlencode({"country": "sg", "lang": "zh_cn", "keyword": query})
        data = self._json(url, {"User-Agent": "Mozilla/5.0", "X-Forwarded-For": "101.32.0.1"})
        albums = []
        for section in candidate_mappings(data.get("section_list")):
            if _provider_int(section.get("section_type"), 0) != 1:
                continue
            for item in candidate_mappings(section.get("item_list")):
                if _provider_int(item.get("type"), 0) == 2 and item.get("album"):
                    albums.append(item["album"])
                    if len(albums) >= MAX_PROVIDER_CANDIDATES:
                        return tuple(albums)
        return tuple(albums)

    @staticmethod
    def _joox_artist(item):
        return _artist_names(item.get("artist_list") or [])

    @staticmethod
    def _joox_image(item):
        images = item.get("images") or []
        for image in images[:MAX_PROVIDER_CANDIDATES] if isinstance(images, (list, tuple)) else ():
            if isinstance(image, dict):
                value = _provider_text(image.get("url"))
                if value:
                    return value
        return ""

    def joox_album(self, name, artist=""):
        best = None
        best_score = 0
        for item in self._joox_albums(entity_search_query(name, artist)):
            score = provider_score(item.get("name"), name, self._joox_artist(item), artist)
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.45:
            return None
        return {"name": best.get("name") or name, "artist": self._joox_artist(best) or artist,
                "release_date": _provider_text(best.get("publish_date"), 64), "image_url": self._joox_image(best),
                "provider_id": _provider_text(best.get("id"), 128), "source": "joox", "confidence": best_score}

    def joox_lyrics(self, track):
        # Search results can contain several equally-scored releases.  The
        # first one is not necessarily backed by a usable lyric_id: the
        # endpoint may return a normal JSONP body with ``code != 0`` and an
        # empty lyric.  Previously that stopped the whole provider, even when
        # the next same-title candidate had a valid lyric.  Keep the fallback
        # bounded so an interactive request remains inside its global budget.
        candidates = []
        for item in self._joox_songs(track_search_query(track)):
            score = provider_score(item.get("name"), track.get("title"), self._joox_artist(item), track.get("artist"))
            song_id = _provider_text(item.get("id"), 128)
            if score >= 0.55 and song_id:
                candidates.append((score, song_id))
        for score, song_id in sorted(candidates, reverse=True)[:4]:
            url = "https://api.joox.com/web-fcgi-bin/web_lyric?" + urllib.parse.urlencode({"musicid": song_id, "country": "sg", "lang": "zh_cn"})
            # Keep JOOX on the same strict path as QQ/Kugou.  Silently
            # dropping invalid bytes here could turn a malformed JSONP body
            # into an empty lyric result, hiding a provider failure from retry
            # diagnostics.  A valid no-lyric response, however, is a normal
            # candidate miss and should allow the next candidate to run.
            payload = self._text(url, {"User-Agent": "Mozilla/5.0", "X-Forwarded-For": "101.32.0.1"})
            try:
                decoded = _decode_provider_json(payload.encode("utf-8"), "application/javascript")
            except (TypeError, ValueError):
                # One malformed candidate must not abort the bounded fallback
                # list or suppress the next metadata provider.
                continue
            if not isinstance(decoded, dict) or _provider_int(decoded.get("code"), 0) != 0:
                continue
            # Same reason as the Kugou lane: an over-budget document is a
            # candidate miss, and it must be refused whole rather than sliced
            # into a shortened lyric that still decodes.
            try:
                text = _decode_base64_lyrics(decoded.get("lyric"))
            except (TypeError, ValueError):
                continue
            if text:
                return {"lyrics": text, "source": "joox", "provider_id": song_id, "confidence": score}
        return None

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
        return candidate_mappings((data.get("data") or {}).get("typeTrack"))

    def _qianqian_albums(self, query):
        params = self._qianqian_params({"word": query, "type": "3", "pageNo": "1", "pageSize": "10"})
        data = self._json("https://music.91q.com/v1/search?" + urllib.parse.urlencode(params), {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36", "Referer": "https://music.91q.com/player"})
        return candidate_mappings((data.get("data") or {}).get("typeAlbum"))

    @staticmethod
    def _qianqian_artist(item):
        return _artist_names(item.get("artist") or [])

    def qianqian_album(self, name, artist=""):
        best = None
        best_score = 0
        for item in self._qianqian_albums(entity_search_query(name, artist)):
            score = provider_score(item.get("title"), name, self._qianqian_artist(item), artist)
            if score > best_score:
                best, best_score = item, score
        if not best or best_score < 0.55:
            return None
        return {"name": best.get("title") or name, "artist": self._qianqian_artist(best) or artist,
                "release_date": _provider_text(best.get("releaseDate"), 64), "image_url": _provider_text(best.get("pic"), MAX_ARTWORK_URL_LENGTH),
                "provider_id": _provider_text(best.get("albumAssetCode"), 128), "source": "qianqian", "confidence": best_score}

    def qianqian_lyrics(self, track):
        best = None
        best_score = 0
        for item in self._qianqian_songs(track_search_query(track)):
            score = provider_score(item.get("title"), track.get("title"), self._qianqian_artist(item), track.get("artist"))
            if score > best_score:
                best, best_score = item, score
        song_id = _provider_text((best or {}).get("TSID"), 128)
        if not best or best_score < 0.55 or not song_id:
            return None
        params = self._qianqian_params({"TSID": song_id})
        data = self._json("https://music.91q.com/v1/song/info?" + urllib.parse.urlencode(params), {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36", "Referer": "https://music.91q.com/player"})
        details = candidate_mappings(data.get("data"), 1)
        lyric_url = _provider_text((details[0] if details else {}).get("lyric"), MAX_ARTWORK_URL_LENGTH)
        if not lyric_url:
            return None
        text = self._text(lyric_url, {"User-Agent": "Mozilla/5.0"})
        return {"lyrics": text, "source": "qianqian", "provider_id": song_id, "confidence": best_score} if text else None

    def lyrics(self, track):
        track = self._normalize_track_input(track)
        # Reuse the service-level file-version cache used by interactive
        # lyrics requests.  Provider workers can revisit the same track while
        # polling/recovering; reparsing embedded tags or sidecars each time
        # needlessly adds disk I/O and latency on large libraries.
        version_hint = (track.get("modified_ns"), track.get("size"))
        local_path = track.get("path") or ""
        if all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in version_hint):
            local = self._read_local_lyrics_cached(local_path, version_hint)
        else:
            local = self._read_local_lyrics_cached(local_path)
        if local:
            return {"lyrics": local, "source": "本地歌词", "provider_id": "", "confidence": 1.0}
        for provider in (self.netease_lyrics, self.qq_lyrics, self.kugou_lyrics, self.migu_lyrics, self.joox_lyrics, self.qianqian_lyrics):
            provider_name = _provider_name(provider, "lyrics")
            if not self._provider_is_available(provider_name):
                continue
            try:
                result = provider(track)
                lyrics_text = result.get("lyrics") if isinstance(result, dict) else ""
                if isinstance(lyrics_text, str) and "\ufffd" in lyrics_text:
                    raise ValueError("metadata provider returned corrupt lyric text")
                if isinstance(lyrics_text, str) and lyrics_text.strip():
                    self._record_provider_success(provider_name)
                    return result
                self._record_provider_outcome(provider_name, "empty")
            except Exception as exc:
                # Provider adapters consume untrusted third-party payloads.
                # Keep one malformed response from aborting the entire
                # fallback chain; the bounded diagnostic still records the
                # concrete exception type and the next source can run.
                self._record_provider_failure(provider_name, exc)
                continue
        return None

    def track_artwork(self, track):
        track = self._normalize_track_input(track)
        # Keep the cheap provider-specific artwork path first, but do not
        # stop at the two legacy sources.  Lyrics requests are also the
        # user's most visible metadata request; when NetEase/QQ have no
        # result, the other supported catalogs may still provide a valid
        # cover through the same bounded candidate search used by track
        # matching.  This avoids reporting a coverless track as metadata
        # unavailable merely because the first two providers missed it.
        artwork = self._first_match(
            (self.netease_track_artwork, self.qq_track_artwork), track
        )
        if artwork:
            return artwork
        try:
            candidates = self.track_candidates(track)
        except Exception as exc:
            self._record_provider_failure("track-artwork-fallback", exc)
            return None
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            image_url = _provider_text(candidate.get("image_url"), 2048)
            if not image_url:
                continue
            return {
                "image_url": image_url,
                "source": _provider_text(candidate.get("source"), 64),
                "provider_id": _provider_text(candidate.get("provider_id"), 128),
                "confidence": candidate.get("confidence", 0),
            }
        return None

    @staticmethod
    def _track_candidate(track, item, source, title, artist, album="", album_artist="", date="", genre="", track_no=0, image_url="", provider_id=""):
        projected = project_track_candidate_fields(
            title, artist, album, album_artist, date, genre, track_no,
            image_url, provider_id, source,
        )
        def safe_text(key):
            try:
                value = track.get(key)
            except Exception:
                return ""
            return _provider_text(value, 512)
        local_title = safe_text("title")
        local_artist = safe_text("artist")
        local_album = safe_text("album")
        score = provider_score(projected["title"], local_title, projected["artist"], local_artist)
        if local_album and local_album.casefold() not in PLACEHOLDER_NAMES and projected["album"]:
            score = min(1.0, score + (0.08 if projected["album"].casefold() == local_album.casefold() else 0))
        try:
            local_value = track.get("duration")
            local_duration = float(local_value) if isinstance(local_value, (int, float, str)) else 0
            remote_value = item.get("interval") or item.get("Duration") or item.get("duration") or 0
            remote_duration = float(remote_value) if isinstance(remote_value, (int, float, str)) else 0
            if local_duration and remote_duration and abs(local_duration - remote_duration) <= 3:
                score = min(1.0, score + 0.04)
        except (TypeError, ValueError):
            pass
        return {
            **projected, "confidence": round(score, 4),
        }

    def track_candidates(self, track):
        """Return scored, deduplicated recording candidates from existing providers.

        Provider calls deliberately reuse the same search APIs as lyrics/artwork.
        A provider failure is isolated so an outage never blocks the whole queue.
        """
        track = self._normalize_track_input(track)
        # Keep candidate search on the same bounded/placeholder-aware query
        # policy used by lyrics and artwork providers.  The old raw
        # interpolation let values such as "未知歌手" leak into every
        # provider request and could also stringify malformed fields.
        query = track_search_query(track)
        if not query:
            return []
        # Filename identity can contribute a low-confidence local candidate
        # when Tags are partial. Keep it in the positive-cache key so two
        # otherwise identical untagged files cannot reuse each other's view.
        hinted_artist, hinted_title = filename_track_hint(track)
        cache_key = build_candidate_cache_key(
            track,
            query=query,
            hinted_artist=hinted_artist,
            hinted_title=hinted_title,
        )
        now = time.monotonic()
        cached_value = None
        cached_entry = None
        with self._candidate_cache_lock:
            cached = self._candidate_cache.get(cache_key)
            if cached is not None:
                valid_entry = (
                    isinstance(cached, (tuple, list))
                    and len(cached) == 2
                    and _cache_entry_is_fresh(cached[0], now, PROVIDER_CANDIDATE_CACHE_TTL_SECONDS)
                    and isinstance(cached[1], list)
                )
                if valid_entry:
                    # The value was detached before storage and is never
                    # mutated in place, so copying it after releasing this
                    # shared provider lock cannot expose a partial result.
                    cached_value = cached[1]
                    cached_entry = cached
                    self._candidate_cache.move_to_end(cache_key)
                else:
                    # A cache entry is an optimization, never a reason to fail a
                    # provider request. Drop malformed or stale values before
                    # taking the normal miss path.
                    self._candidate_cache.pop(cache_key, None)
            if cached_value is None:
                self._candidate_cache_misses = min(
                    1000000,
                    nonnegative_int(self._candidate_cache_misses, maximum=1000000) + 1,
                )
        if cached_value is not None:
            try:
                value = copy.deepcopy(cached_value)
            except (TypeError, ValueError, copy.Error):
                value = None
            if isinstance(value, list):
                with self._candidate_cache_lock:
                    # Copying is deliberately outside the lock. A concurrent
                    # provider refresh may replace this key meanwhile; do not
                    # publish that obsolete copy as a cache hit.
                    if self._candidate_cache.get(cache_key) is not cached_entry:
                        value = None
                    else:
                        self._candidate_cache_hits = min(
                            1000000,
                            nonnegative_int(self._candidate_cache_hits, maximum=1000000) + 1,
                        )
                if isinstance(value, list):
                    return value
            with self._candidate_cache_lock:
                if self._candidate_cache.get(cache_key) is cached_entry:
                    self._candidate_cache.pop(cache_key, None)
                # A cache entry is an optimization, never a reason to fail a
                # provider request. Treat an uncopyable value as a miss.
                self._candidate_cache_misses = min(
                    1000000,
                    nonnegative_int(self._candidate_cache_misses, maximum=1000000) + 1,
                )
        candidates = []
        # Keep a local filename identity as a last-resort presentation
        # candidate. It makes metadata recovery useful even when every remote
        # provider is rate-limited or temporarily unreachable; the low score
        # prevents automatic Tag writeback and leaves existing Tag values
        # authoritative.
        # Keep a filename identity candidate whenever it can fill a missing
        # local field.  A common partial-tag case has a valid title but no
        # artist; the query builder already derives that artist hint for
        # provider searches, but the presentation fallback used to suppress
        # it because the title was non-empty.  Showing this low-confidence
        # projection immediately keeps metadata visibly useful while the
        # bounded provider chain is still pending; it never authorizes tag
        # writeback.
        def _local_text(key):
            try:
                value = track.get(key)
            except Exception:
                return ""
            return value.strip() if isinstance(value, str) else ""
        local_title = _local_text("title")
        local_artist = _local_text("artist")
        local_album = _local_text("album")
        missing_local_identity = (
            not local_title
            or local_title.casefold() in PLACEHOLDER_NAMES
            or not local_artist
            or local_artist.casefold() in PLACEHOLDER_NAMES
            or not local_album
            or local_album.casefold() in PLACEHOLDER_NAMES
        )
        if hinted_title and (hinted_artist or not local_title) and missing_local_identity:
            local = self._track_candidate(
                track, {}, "filename", hinted_title, hinted_artist,
                local_album if local_album.casefold() not in PLACEHOLDER_NAMES else "",
            )
            # The normal matcher scores an empty Tag against the filename
            # candidate as zero. Lift it to the minimum review threshold so
            # the fallback survives candidate filtering, while remaining far
            # below the automatic writeback threshold.
            local["confidence"] = 0.56
            candidates.append(local)
        if fingerprint_capability(self.config).get("available"):
            try:
                sample = audio_fingerprint(track.get("path") or "", self.config)
                params = urllib.parse.urlencode({
                    "client": os.environ.get("FNAUDIO_ACOUSTID_CLIENT_KEY", ""),
                    "meta": "recordings+releasegroups",
                    "duration": sample["duration"],
                    "fingerprint": sample["fingerprint"],
                }).encode("ascii")
                response = self._json(
                    "https://api.acoustid.org/v2/lookup",
                    {
                        "User-Agent": APP_USER_AGENT,
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Content-Encoding": "gzip",
                    },
                    data=gzip.compress(params),
                )
                for result in candidate_mappings(response.get("results")):
                    recording = next(iter(candidate_mappings(result.get("recordings"), 1)), {})
                    title = recording.get("title") or ""
                    artists = _artist_name(recording.get("artists") or [])
                    releases = candidate_mappings(recording.get("releasegroups"), 1)
                    release = releases[0] if releases else {}
                    candidate = self._track_candidate(track, {"duration": sample["duration"]}, "acoustid", title, artists, release.get("title"), artists, release.get("date"), "", 0, "", recording.get("id"))
                    score = finite_confidence(result.get("score"))
                    candidate["confidence"] = round(max(candidate["confidence"], min(0.98, 0.75 + 0.23 * score)), 4)
                    candidates.append(candidate)
            except (OSError, ValueError, TypeError, RuntimeError, urllib.error.URLError, urllib.error.HTTPError) as exc:
                self._record_provider_failure("acoustid", exc)
        musicbrainz_adapter = (
            "musicbrainz", lambda: self._musicbrainz_recordings(self._musicbrainz_track_query(track)),
            lambda item: self._musicbrainz_track_candidate(track, item),
        )
        netease_adapter = (
            "netease", lambda: ((self._json("https://music.163.com/api/search/get/web?type=1&limit=10&s=" + urllib.parse.quote(query), {"User-Agent": "Mozilla/5.0", "Referer": "https://music.163.com/"}).get("result") or {}).get("songs") or []),
            lambda item: self._track_candidate(track, item, "netease", item.get("name"), _artist_name(item.get("artists") or []), (item.get("album") or {}).get("name"), _artist_name((item.get("album") or {}).get("artists") or []), (item.get("album") or {}).get("publishTime"), "", item.get("no"), (item.get("album") or {}).get("picUrl"), item.get("id")),
        )
        qq_adapter = ("qq", lambda: self._qq_songs(query, 10),
             lambda item: self._track_candidate(track, item, "qq", item.get("songname"), _artist_name(item.get("singer") or []), item.get("albumname"), _artist_name(item.get("singer") or []), item.get("pubtime"), item.get("genre"), item.get("songid"), "https://y.gtimg.cn/music/photo_new/T002R500x500M000%s.jpg" % item.get("albummid") if item.get("albummid") else "", item.get("songmid")))
        kugou_adapter = ("kugou", lambda: self._kugou_songs(query, 10),
             lambda item: self._track_candidate(track, item, "kugou", item.get("SongName"), item.get("SingerName"), item.get("AlbumName"), item.get("SingerName"), item.get("PublishDate") or item.get("PublishTime"), item.get("Genre"), item.get("OriSongName"), _provider_text(item.get("Image"), MAX_ARTWORK_URL_LENGTH).replace("{size}", "500"), item.get("FileHash")))
        migu_adapter = ("migu", lambda: self._migu_songs(query, 10),
             lambda item: self._track_candidate(track, item, "migu", item.get("name") or item.get("songName"), self._migu_artist(item), self._migu_album_name(item), self._migu_artist(item), item.get("publishDate"), item.get("genre"), item.get("trackNo"), self._migu_image(item), item.get("contentId")))
        joox_adapter = ("joox", lambda: self._joox_songs(query),
             lambda item: self._track_candidate(track, item, "joox", item.get("name"), self._joox_artist(item), (item.get("album") or {}).get("name"), self._joox_artist(item), (item.get("album") or {}).get("publish_date"), item.get("genre"), item.get("track"), self._joox_image(item), item.get("id")))
        qianqian_adapter = ("qianqian", lambda: self._qianqian_songs(query),
             lambda item: self._track_candidate(track, item, "qianqian", item.get("title"), self._qianqian_artist(item), item.get("albumTitle") or item.get("album"), self._qianqian_artist(item), item.get("releaseDate"), item.get("genre"), item.get("trackNo"), item.get("pic"), item.get("TSID")))
        # MusicBrainz is deliberately first for international titles, where
        # it is the strongest broad-catalog source.  For CJK titles the
        # regional adapters are both faster and more complete; keep
        # MusicBrainz as a true fallback so its public rate limit does not
        # delay the common Chinese-song path.
        if contains_cjk(track.get("title"), track.get("artist")):
            adapters = (netease_adapter, qq_adapter, kugou_adapter, migu_adapter, joox_adapter, qianqian_adapter, musicbrainz_adapter)
        else:
            adapters = (musicbrainz_adapter, netease_adapter, qq_adapter, kugou_adapter, migu_adapter, joox_adapter, qianqian_adapter)
        for _source, request, mapper in adapters:
            if not self._provider_is_available(_source):
                continue
            search_complete = False
            try:
                payload = request()
                # Every recording-search adapter has a list-shaped result.
                # Do not let an error object/schema drift be quietly treated
                # as a valid empty list: that incorrectly writes a long-lived
                # ``no_match`` and makes metadata appear permanently broken.
                # Raising here is contained by this provider's boundary,
                # recorded for diagnostics, and lets the remaining sources
                # supply a result in the same bounded job.
                if not candidate_payload_is_sequence(payload):
                    raise ValueError("metadata provider candidate payload has invalid shape")
                if not payload:
                    self._record_provider_outcome(_source, "empty")
                valid_candidate_seen = False
                usable_candidate_seen = False
                corrupt_candidate_seen = False
                # Keep a malformed single candidate from poisoning the whole
                # provider result.  Third-party search payloads occasionally
                # contain null/shape-drift entries mixed with valid songs;
                # mapping them in one generator used to abort the remaining
                # candidates and falsely record a provider failure.
                for item in candidate_mappings(payload):
                    try:
                        mapped = mapper(item)
                    except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
                        continue
                    # Some catalog gateways return JSON that is syntactically
                    # valid but already contains U+FFFD replacement text.
                    # Treat that candidate as corrupt instead of allowing a
                    # high title score to block every healthy fallback source.
                    if isinstance(mapped, dict) and not any(
                        candidate_text_is_corrupt(mapped.get(field))
                        for field in ("title", "artist", "album", "album_artist", "genre", "image_url")
                    ):
                        valid_candidate_seen = True
                        candidates.append(mapped)
                        usable_candidate_seen = usable_candidate_seen or candidate_has_displayable_fields(mapped)
                        if should_stop_track_candidate_search(mapped):
                            # Current-song requests should become visible as
                            # soon as one complete, high-confidence result is
                            # available; lower-priority providers remain a
                            # fallback when the match is sparse or ambiguous.
                            search_complete = True
                            break
                    elif isinstance(mapped, dict):
                        corrupt_candidate_seen = True
                # A syntactically valid list containing only replacement-text
                # candidates is a provider data failure, not a successful
                # no-match.  Keep it retryable so a later request can recover
                # after the source fixes its encoding/payload.
                if corrupt_candidate_seen and not valid_candidate_seen:
                    raise ValueError("metadata provider returned corrupt candidate text")
                if payload and not valid_candidate_seen:
                    self._record_provider_outcome(_source, "no_valid_candidates")
                # An empty or structurally valid-but-unusable response is not
                # a provider success: keep failure cooldowns intact so the
                # next bounded retry can recover after a transient outage.
                if usable_candidate_seen:
                    self._record_provider_success(_source)
            except Exception as exc:
                # A single provider's schema drift must not make metadata look
                # globally unavailable. Continue through the remaining bounded
                # sources and expose the failure through diagnostics.
                self._record_provider_failure(_source, exc)
                continue
            if search_complete:
                break
        result = finalize_track_candidates(candidates)
        if result:
            with self._candidate_cache_lock:
                self._candidate_cache.pop(cache_key, None)
                self._candidate_cache[cache_key] = (time.monotonic(), copy.deepcopy(result))
                while len(self._candidate_cache) > PROVIDER_CANDIDATE_CACHE_MAX_ENTRIES:
                    self._candidate_cache.popitem(last=False)
        return result


def read_embedded_lyrics(path, config=None):
    ffprobe = find_ffprobe(config or {})
    if not ffprobe or not os.path.isfile(path):
        return ""
    command = [ffprobe, "-v", "error", "-show_entries", "format_tags:stream_tags", "-of", "json", path]
    env = os.environ.copy()
    if "/usr/trim/lib/mediasrv/bin" in ffprobe:
        env["LD_LIBRARY_PATH"] = "/usr/trim/lib/mediasrv/lib:" + env.get("LD_LIBRARY_PATH", "")
    try:
        with tempfile.TemporaryFile() as output:
            result = _run_media_process(
                command, stdout=output, stderr=subprocess.DEVNULL, timeout=15, env=env,
                output_limit=MAX_FFPROBE_LYRICS_BYTES,
            )
            if result.returncode != 0:
                return ""
            output.seek(0)
            raw = output.read(MAX_FFPROBE_LYRICS_BYTES + 1)
        if len(raw) > MAX_FFPROBE_LYRICS_BYTES:
            return ""
        data = json.loads(raw.decode("utf-8", "ignore") or "{}")
    except (OSError, ValueError, ResourceLimitError, subprocess.SubprocessError):
        return ""
    return extract_embedded_lyrics(data)


def read_local_lyrics(path, config=None):
    embedded = read_embedded_lyrics(path, config)
    if embedded:
        return embedded
    base, _ = os.path.splitext(path)
    for candidate in (base + ".lrc", os.path.join(os.path.dirname(path), "lyrics.lrc")):
        try:
            with open(candidate, "rb") as fh:
                raw = fh.read(MAX_PROVIDER_LYRICS_BYTES + 1)
        except OSError:
            continue
        if len(raw) > MAX_PROVIDER_LYRICS_BYTES:
            continue
        for encoding in ("utf-8-sig", "utf-16", "gb18030"):
            try:
                return raw.decode(encoding).strip()
            except UnicodeError:
                continue
    return ""


class _LaneRelease(threading.local):
    """Per-thread bookkeeping for worker starts requested inside a transaction.

    ``depth`` counts the open :meth:`MetadataService._connect` scopes and ``lanes``
    the worker lanes that may only start once the outermost one has committed.
    """

    def __init__(self):
        self.depth = 0
        self.lanes = []


_lane_release = _LaneRelease()


def _overlay_artwork_id(value):
    """Bound and case-fold one cached artwork id while its row is being read.

    Every consumer of the overlay wanted the same folded form, so the merge loop
    repeated the bound/strip/lower chain for each visible row of each request.
    Doing it once on the cold read keeps that work off the hot path and
    guarantees the cached value is a plain string.
    """
    return _provider_text(value, 128).strip().lower()


class MetadataService:
    def __init__(self, config):
        self.config = config
        self.providers = MetadataProviders(config)
        self.stop_event = threading.Event()
        self.fetch_wake_event = threading.Event()
        self.tag_wake_event = threading.Event()
        self.priority_wake_event = threading.Event()
        # Backward-compatible name for diagnostics/tests that wake the normal
        # fetch pool directly. Worker-specific events prevent one worker from
        # clearing another worker's notification.
        self.wake_event = self.fetch_wake_event
        self.thread = None
        self.fetch_threads = []
        self.tag_thread = None
        self.priority_thread = None
        self.force_reconcile = False
        self.last_reconcile = 0
        self._last_reconcile_monotonic = 0.0
        # (pending, limit) as last actually observed by this service.  Unknown
        # starts as (0, 0), which every policy helper reads as "no backlog" so
        # the historical cadence keeps running until real numbers arrive.
        self._observed_queue_pressure = (0, 0)
        self.library_signature = ""
        self.last_cleanup = 0
        self._last_cleanup_monotonic = 0.0
        self.last_error = ""
        self._active_jobs_lock = threading.RLock()
        self._active_jobs = OrderedDict()
        self._active_job_deadlines = {}
        self.active_job = ""
        self.last_tag_write_at = 0.0
        self.tag_written = 0
        self.tag_write_seconds = 0.0
        self.tag_write_started_at = 0.0
        self.current_track_id = ""
        self.dropped_jobs = 0
        self.lock = threading.RLock()
        # Serializes lazy worker recovery triggered by an interactive metadata
        # request.  Without this, two concurrent WebView clients can both see
        # a dead pool and race through ``start()``, producing duplicate workers
        # or a transient unavailable response.
        self._lifecycle_lock = threading.RLock()
        self._status_cache_lock = threading.RLock()
        self._status_snapshot = None
        self._status_snapshot_at = 0.0
        self._status_cache_hits = 0
        self._status_cache_misses = 0
        self._status_cache_generation = 0
        self._status_cache_loading = False
        self._status_cache_ready = threading.Condition(self._status_cache_lock)
        # Monotonic in-process projection revision. A second-resolution
        # SQLite timestamp can remain unchanged when several metadata jobs
        # finish in one tick; this revision still lets clients detect each
        # committed projection change without exposing track identities.
        self.metadata_projection_revision = 0
        self._track_page_cache_lock = threading.RLock()
        self._track_page_cache = OrderedDict()
        self._track_page_cache_hits = 0
        self._track_page_cache_misses = 0
        self.worker_restarts = 0
        # Serial for recovery threads only.  `range(replacement_count)` restarts at
        # zero every round, so a second recovery produced a second thread literally
        # named `fnaudio-metadata-fetch-recovery-0` and a thread dump could not say
        # which round started which worker.  Guarded by `_lifecycle_lock`.
        self._recovery_serial = 0
        # Lyrics polling can hit this path every ~900ms while a provider job
        # is pending. Cache the bounded local probe by file identity so an
        # embedded-tag extraction/sidecar read is not repeated for every poll.
        self._local_lyrics_cache = LocalLyricsCache(
            lambda path: read_local_lyrics(path, self.config),
            max_bytes=bytes_limit_from_config(self.config),
        )

    def _lyrics_cache_lanes(self):
        """Return every live lyric cache owned by this service.

        The provider lane and the interactive lane are constructed separately,
        so a budget change has to reach both. The lookups stay defensive because
        diagnostics builds and unit tests replace parts of a service.
        """
        lanes = []
        own = getattr(self, "_local_lyrics_cache", None)
        if own is not None:
            lanes.append(own)
        provider_cache = getattr(getattr(self, "providers", None), "_local_lyrics_cache", None)
        if provider_cache is not None and provider_cache not in lanes:
            lanes.append(provider_cache)
        return lanes

    def apply_lyrics_cache_config(self, config=None):
        """Re-train the lyric caches from a settings dictionary, live.

        Returns the budget actually enforced. The server calls this on every
        configuration commit so the settings page can change the budget without
        a restart, which is the same contract the library connection pool gives.
        """
        source = self.config if config is None else config
        limit = bytes_limit_from_config(source)
        for lane in self._lyrics_cache_lanes():
            lane.apply_bytes_limit(limit)
        return limit

    def lyrics_cache_bytes_limit(self):
        """Report the tightest budget any live lyric lane actually enforces.

        ``status()`` sums both lanes because the process really does hold that
        much; a settings page has to show what one lyric can overflow, and an
        aggregate of two caches can never be read back as a single limit.
        """
        limits = []
        for lane in self._lyrics_cache_lanes():
            value = lane.snapshot().get("bytes_limit")
            if isinstance(value, int) and not isinstance(value, bool):
                limits.append(value)
        if limits:
            return min(limits)
        return bytes_limit_from_config(self.config)

    def _read_local_lyrics_cached(self, path, version_hint=None):
        return self._local_lyrics_cache.read(path, version_hint)

    def _invalidate_status_cache(self, projection_changed=False):
        """Discard aggregate status; invalidate page overlay only on a visible change.

        Queue transitions happen far more often than completed lyrics, artwork
        or track projections. Clearing the short-lived page overlay cache for
        every enqueue/retry made a busy metadata worker turn repeat first-page
        loads into avoidable SQLite joins, despite the visible rows being
        identical. Status must still be invalidated for diagnostics, while the
        overlay cache only needs eviction when its projected fields changed.
        """
        with self._status_cache_lock:
            self._status_snapshot = None
            self._status_snapshot_at = 0.0
            self._status_cache_generation += 1
            if projection_changed:
                self.metadata_projection_revision = min(
                    1000000000, nonnegative_int(self.metadata_projection_revision, maximum=1000000000) + 1
                )
            self._status_cache_ready.notify_all()
        if projection_changed:
            with self._track_page_cache_lock:
                self._track_page_cache.clear()

    def _track_page_cache_get(self, cache_key):
        key = tuple(cache_key)
        now = time.monotonic()
        with self._track_page_cache_lock:
            entry = self._track_page_cache.get(key)
            if entry is None:
                self._track_page_cache_misses = min(1000000, nonnegative_int(self._track_page_cache_misses, maximum=1000000) + 1)
                return None
            valid_entry = (
                isinstance(entry, (tuple, list))
                and len(entry) == 2
                and _cache_entry_is_fresh(entry[0], now, TRACK_PAGE_CACHE_TTL_SECONDS)
                and isinstance(entry[1], dict)
            )
            if not valid_entry:
                self._track_page_cache.pop(key, None)
                self._track_page_cache_misses = min(1000000, nonnegative_int(self._track_page_cache_misses, maximum=1000000) + 1)
                return None
            cached_at, value = entry
            self._track_page_cache.move_to_end(key)
        try:
            value = copy.deepcopy(value)
        except (TypeError, ValueError, copy.Error):
            with self._track_page_cache_lock:
                if self._track_page_cache.get(key) is entry:
                    self._track_page_cache.pop(key, None)
                self._track_page_cache_misses = min(1000000, nonnegative_int(self._track_page_cache_misses, maximum=1000000) + 1)
            return None
        with self._track_page_cache_lock:
            if self._track_page_cache.get(key) is not entry:
                self._track_page_cache_misses = min(1000000, nonnegative_int(self._track_page_cache_misses, maximum=1000000) + 1)
                return None
            self._track_page_cache_hits = min(1000000, nonnegative_int(self._track_page_cache_hits, maximum=1000000) + 1)
        return value

    def _track_page_cache_put(self, cache_key, value):
        key = tuple(cache_key)
        try:
            cached_value = copy.deepcopy(value)
        except (TypeError, ValueError, copy.Error):
            # Overlay caching is optional. A malformed/non-copyable projection
            # must never turn an otherwise valid library response into a 500.
            return
        with self._track_page_cache_lock:
            self._track_page_cache.pop(key, None)
            self._track_page_cache[key] = (time.monotonic(), cached_value)
            while len(self._track_page_cache) > TRACK_PAGE_CACHE_MAX_ENTRIES:
                self._track_page_cache.popitem(last=False)

    def _track_page_cache_status(self):
        with self._track_page_cache_lock:
            return {
                "entries": min(TRACK_PAGE_CACHE_MAX_ENTRIES, len(self._track_page_cache)),
                "limit": TRACK_PAGE_CACHE_MAX_ENTRIES,
                "hits": nonnegative_int(self._track_page_cache_hits, maximum=1000000),
                "misses": nonnegative_int(self._track_page_cache_misses, maximum=1000000),
                "ttl_ms": int(TRACK_PAGE_CACHE_TTL_SECONDS * 1000),
            }

    def _status_database_snapshot(self):
        """Collect the expensive, database-backed portion of public status."""
        counts = {}
        job_types = {}
        tag_jobs = []
        track_matches = {}
        metadata_updated_at = 0
        artwork_bytes = 0
        entity_count = 0
        lyrics_count = 0
        with self._connect() as conn:
            counts = {
                _provider_text(row["status"], 32): nonnegative_int(row["count"])
                for row in conn.execute("SELECT status,COUNT(*) AS count FROM metadata_jobs GROUP BY status")
            }
            # Counts alone cannot identify a replacement when a completed
            # task is substituted by another task in the same state. Expose a
            # bounded timestamp fingerprint so clients can invalidate their
            # projection without receiving per-track metadata in status.
            try:
                metadata_updated_at = bounded_epoch(conn.execute(
                    "SELECT COALESCE(MAX(updated_at),0) FROM metadata_jobs "
                    "WHERE status IN ('done','failed','no_match','skipped')"
                ).fetchone()[0])
            except (sqlite3.Error, TypeError, ValueError, OverflowError):
                metadata_updated_at = 0
            job_types = {
                _provider_text(row["job_type"], 32): {"pending": nonnegative_int(row["pending"]), "running": nonnegative_int(row["running"])}
                for row in conn.execute(
                    """SELECT job_type,
                              SUM(CASE WHEN status IN ('pending','retry') THEN 1 ELSE 0 END) AS pending,
                              SUM(CASE WHEN status='running' THEN 1 ELSE 0 END) AS running
                       FROM metadata_jobs GROUP BY job_type"""
                )
            }
            artwork_bytes = nonnegative_int(conn.execute("SELECT COALESCE(SUM(size),0) FROM metadata_assets").fetchone()[0])
            entity_count = nonnegative_int(conn.execute("SELECT COUNT(*) FROM metadata_entities WHERE orphaned_at=0").fetchone()[0])
            lyrics_count = nonnegative_int(conn.execute("SELECT COUNT(*) FROM metadata_tracks WHERE lyrics<>'' AND orphaned_at=0").fetchone()[0])
            track_matches = {
                _provider_text(row["status"], 32): nonnegative_int(row["count"])
                for row in conn.execute("SELECT status,COUNT(*) AS count FROM metadata_track_matches WHERE orphaned_at=0 GROUP BY status")
            }
            tracks_table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tracks'"
            ).fetchone()
            if tracks_table:
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
                        "attempts": nonnegative_int(row["attempts"]),
                        "updated_at": bounded_epoch(row["updated_at"]),
                        "error": str(row["last_error"] or "")[:500],
                    })
        return {
            "jobs": counts,
            "job_types": job_types,
            "artwork_bytes": artwork_bytes,
            "entities": entity_count,
            "lyrics": lyrics_count,
            "track_matches": track_matches,
            "metadata_updated_at": metadata_updated_at,
            "tag_jobs": tag_jobs,
        }

    @property
    def artwork_dir(self):
        return os.path.join(self.config.get("cache_dir") or ".", "metadata", "artwork")

    def _safe_artwork_path(self, path):
        """Accept only a regular, non-symlinked asset inside this cache root."""
        if not isinstance(path, str) or not path:
            return ""
        try:
            root = os.path.realpath(self.artwork_dir)
            candidate = os.path.realpath(path)
            if os.path.commonpath((root, candidate)) != root:
                return ""
            if os.path.islink(path) or not os.path.isfile(path):
                return ""
        except (OSError, TypeError, ValueError):
            return ""
        return path

    @contextmanager
    def _connect(self):
        path = library_db_path(self.config)
        secure_directory(os.path.dirname(path))
        conn = sqlite3.connect(path, timeout=20)
        failed = False
        inside = False
        try:
            secure_sqlite_files(path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            secure_sqlite_files(path)
            conn.execute("PRAGMA synchronous=NORMAL")
            # Library scans acquire BEGIN IMMEDIATE for their persistence window.
            # Match that writer's wait budget so a short scan does not turn a
            # metadata state update into a false provider failure.
            conn.execute("PRAGMA busy_timeout=15000")
            # From here on this thread holds a database scope, and any write below
            # or on the borrowed connection stays uncommitted until the scope exits.
            _lane_release.depth += 1
            inside = True
            self._ensure_schema(conn)
            yield conn
            conn.commit()
        except BaseException:
            failed = True
            try:
                conn.rollback()
            except Exception:
                # Preserve the body/commit/schema exception if the SQLite
                # handle has already become unusable during cleanup.
                pass
            raise
        finally:
            if failed:
                try:
                    conn.close()
                except Exception:
                    pass
                try:
                    secure_sqlite_files(path)
                except Exception:
                    pass
            else:
                try:
                    conn.close()
                finally:
                    # A successful metadata transaction must remain a success
                    # even when post-close permission repair is unavailable.
                    # The next lifecycle pass can retry that housekeeping.
                    try:
                        secure_sqlite_files(path)
                    except Exception:
                        pass
            if inside:
                _lane_release.depth -= 1
                if _lane_release.depth == 0:
                    # This scope's transaction is finished and its handle is
                    # closed, so a lane the body deferred can now start without
                    # competing with a writer that can only commit after the fact.
                    self._release_deferred_lanes()

    def _release_deferred_lanes(self):
        """Start the worker lanes this thread asked for inside its last transaction."""
        lanes = _lane_release.lanes
        if not lanes:
            return
        _lane_release.lanes = []
        for lane in lanes:
            try:
                self._start_lane(lane)
            except Exception as exc:
                # Best-effort enrichment must not turn a completed metadata request
                # into a failure after the fact; the next lookup retries the lane.
                self.last_error = "metadata worker startup deferred: %s" % (exc,)

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
        # Repair only once per schema version.  Scanning these small metadata
        # tables on every request would add I/O to the hot library path, while
        # leaving malformed legacy ids could permanently suppress artwork
        # recovery.
        artwork_sanitized = conn.execute(
            "SELECT value FROM metadata_state WHERE key='artwork_id_sanitize_version'"
        ).fetchone()
        if not artwork_sanitized or str(artwork_sanitized["value"] or "") != ARTWORK_ID_SANITIZE_VERSION:
            invalid_sql = "length(artwork_id) <> 64 OR lower(artwork_id) GLOB '*[^0-9a-f]*'"
            conn.execute("UPDATE metadata_entities SET artwork_id='' WHERE artwork_id<>'' AND (" + invalid_sql + ")")
            conn.execute("UPDATE metadata_tracks SET artwork_id='' WHERE artwork_id<>'' AND (" + invalid_sql + ")")
            conn.execute("INSERT OR REPLACE INTO metadata_state(key,value) VALUES ('artwork_id_sanitize_version',?)", (ARTWORK_ID_SANITIZE_VERSION,))
        if self.config.get("metadata_tag_write_enabled", False):
            tag_backfill = conn.execute(
                "SELECT value FROM metadata_state WHERE key='tag_write_backfill_version'"
            ).fetchone()
            if not tag_backfill or str(tag_backfill["value"] or "") != TAG_WRITE_BACKFILL_VERSION:
                self._backfill_album_tag_writes(conn)
                conn.execute(
                    "INSERT OR REPLACE INTO metadata_state(key,value) VALUES ('tag_write_backfill_version',?)",
                    (TAG_WRITE_BACKFILL_VERSION,),
                )
        else:
            # Tag writeback is opt-in. A previous opt-in session may have left
            # durable jobs behind; with the feature disabled they can never be
            # claimed, so remove them at the schema/config boundary.
            conn.execute("DELETE FROM metadata_jobs WHERE job_type='tag_write'")

    def start(self):
        with self._lifecycle_lock:
            fetch_alive = bool(self.fetch_threads) and all(
                worker is not None and worker.is_alive() for worker in self.fetch_threads
            )
            tag_alive = bool(self.tag_thread and self.tag_thread.is_alive())
            priority_alive = bool(self.priority_thread and self.priority_thread.is_alive())
            if fetch_alive and tag_alive and priority_alive:
                return
            if fetch_alive or tag_alive or priority_alive:
                # A previous generation was only partially created or lost a
                # lane.  Reclaim its live threads before rebuilding the full
                # pool; returning here would leave metadata permanently
                # half-started.
                self.shutdown()
                # ``shutdown`` is deliberately bounded so process teardown
                # cannot hang on a provider or tag writer. Do not start a
                # new generation while an old worker is still alive: the
                # recovery step below resets ``running`` jobs, and doing that
                # concurrently would allow two generations to process one
                # job at the same time.
                if self._has_live_workers():
                    self.last_error = "metadata workers did not stop"
                    return
                # ``shutdown`` sets the shared event for the old generation.
                # Clear it before creating replacement lanes; otherwise every
                # replacement thread observes the stale stop signal and exits
                # immediately, making recovery appear successful while the
                # service remains unable to drain jobs.
                self.stop_event.clear()
            # ``shutdown`` is reusable: hold the lifecycle lock while it
            # joins the old pool, then clear the event before creating a new
            # generation of workers.  Without this, a restarted service
            # creates threads that exit immediately on an already-set event.
            self.stop_event.clear()
            self._start_workers()

    def _start_workers(self):
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
        try:
            for worker in self.fetch_threads:
                worker.start()
            self.tag_thread.start()
            self.priority_thread.start()
        except Exception:
            # A pool is useful only when all lanes are available.  Stop any
            # workers that did start so a later recovery cannot overlap a
            # half-created generation.
            self.shutdown()
            raise

    def ensure_workers(self, lane="fetch"):
        """Recover a fetch/priority pool for an interactive request.

        Asking for a lane while this thread's own metadata transaction is still
        open cannot work: the start below opens a second connection that writes,
        and that write must wait for a commit which can only happen after the
        caller's ``with`` block ends.  Measured on a fresh or version-bumped
        database, the wait is the whole ``busy_timeout`` -- 5.00 s on the request
        thread -- and it also wakes a worker too early to see the job that was just
        queued.  An inner request is therefore registered and started by the
        outermost :meth:`_connect` exit instead.
        """
        if _lane_release.depth:
            if lane not in _lane_release.lanes:
                _lane_release.lanes.append(lane)
            return True
        return self._start_lane(lane)

    def _start_lane(self, lane="fetch"):
        """Metadata enrichment is intentionally best-effort, but a dead worker
        should not require restarting the whole fnAudio process.  This method
        is deliberately bounded to one lifecycle transition and refuses to
        restart after shutdown.
        """
        with self._lifecycle_lock:
            if self.stop_event.is_set():
                return False
            fetch_workers = [
                worker for worker in self.fetch_threads
                if worker is not None and worker.is_alive()
            ]
            worker_count = bounded_int(self.config, "metadata_fetch_workers", 3, 1, 6)
            fetch_alive = bool(fetch_workers)
            priority_alive = bool(self.priority_thread and self.priority_thread.is_alive())
            tag_alive = bool(self.tag_thread and self.tag_thread.is_alive())
            # Liveness is lane-specific.  A healthy ordinary fetch pool does
            # not mean the dedicated priority-lyrics worker is available;
            # treating it as interchangeable leaves explicitly requested
            # lyrics jobs pending forever after only that worker exits.
            if lane == "lyrics" and priority_alive and tag_alive:
                return True
            if lane != "lyrics" and len(fetch_workers) >= worker_count and tag_alive:
                return True
            # If the process lost its fetch pool after a worker had claimed a
            # job, the database can retain a ``running`` row that no new
            # worker will ever claim.  Recover only genuinely stale rows (the
            # same bounded age used by the normal lifecycle recovery) before
            # rebuilding the pool; a live worker path above is intentionally
            # left untouched so two workers cannot race the active owner.
            if not fetch_alive:
                try:
                    cutoff = int(time.time()) - RUNNING_JOB_STALE_SECONDS
                    with self._connect() as conn:
                        conn.execute(
                            """UPDATE metadata_jobs
                               SET status='retry', next_attempt_at=0,
                                   updated_at=?, last_error='worker recovered'
                               WHERE status='running' AND updated_at<=?""",
                            (int(time.time()), cutoff),
                        )
                except (OSError, sqlite3.Error, TypeError, ValueError):
                    # Worker startup remains useful even when recovery inspection
                    # cannot read a damaged/temporarily unavailable database.
                    pass
            # Keep recovery lane-specific. A healthy priority worker must not
            # cause a dead fetch pool to be duplicated, and a healthy fetch
            # pool must not mask a dead dedicated lyrics worker.
            try:
                if not tag_alive:
                    self._recover_dead_local_tag_job()
                    if not self._ensure_tag_worker():
                        return False
                if lane == "lyrics":
                    if not priority_alive:
                        self.priority_thread = threading.Thread(target=self._run_priority_lyrics, name="fnaudio-metadata-priority", daemon=True)
                        self.priority_thread.start()
                    self.worker_restarts = min(1000000, nonnegative_int(self.worker_restarts, maximum=1000000) + 1)
                    return True

                # Preserve healthy workers and replace only lost slots. A
                # partial pool must regain its configured throughput without
                # interrupting jobs that are still running in the survivors.
                replacement_count = worker_count - len(fetch_workers)
                replacements = []
                for _round in range(max(0, replacement_count)):
                    self._recovery_serial += 1
                    replacements.append(threading.Thread(
                        target=self._run,
                        name="fnaudio-metadata-fetch-recovery-%d" % self._recovery_serial,
                        daemon=True,
                    ))
                self.fetch_threads = fetch_workers + replacements
                self.thread = self.fetch_threads[0]
                for worker in replacements:
                    worker.start()
                if not priority_alive:
                    self.priority_thread = threading.Thread(target=self._run_priority_lyrics, name="fnaudio-metadata-priority", daemon=True)
                    self.priority_thread.start()
                self.worker_restarts = min(1000000, nonnegative_int(self.worker_restarts, maximum=1000000) + 1)
                return True
            except Exception:
                self.shutdown()
                # Lazy recovery is best-effort.  Keep the already-started
                # service retryable after a transient thread-admission
                # failure, but never clear the stop signal while an old
                # generation is still alive.  Clearing it in that case lets
                # the old worker continue alongside a later replacement.
                if not self._has_live_workers():
                    self.stop_event.clear()
                return False

    def _ensure_tag_worker(self):
        """Start only the tag lane, without touching SQLite state."""
        with self._lifecycle_lock:
            if self.stop_event.is_set():
                return False
            if self.tag_thread is not None and self.tag_thread.is_alive():
                return True
            worker = threading.Thread(
                target=self._run_tag_writer,
                name="fnaudio-metadata-tag-writer",
                daemon=True,
            )
            try:
                worker.start()
            except Exception:
                return False
            self.tag_thread = worker
            return True

    def _recover_dead_local_tag_job(self):
        """Release a tag job only after this instance has lost its own writer.

        The database intentionally has no process-owner column: separate
        MetadataService instances can share it, and must never reset each
        other's destructive writes.  The in-memory active-job record gives us
        a narrow ownership proof for a writer that died after claiming work.
        """
        if self.tag_thread is not None and self.tag_thread.is_alive():
            return False
        with self._active_jobs_lock:
            active = [
                (job_key, attempts)
                for job_key, attempts in self._active_jobs.items()
                if job_key.startswith("tag:") and isinstance(attempts, int) and attempts > 0
            ]
        if not active:
            return False
        now = int(time.time())
        recovered = False
        try:
            with self._connect() as conn:
                for job_key, attempts in active:
                    result = conn.execute(
                        """UPDATE metadata_jobs
                           SET status='retry',next_attempt_at=0,updated_at=?,last_error='tag writer recovered'
                           WHERE job_key=? AND job_type='tag_write' AND status='running' AND attempts=?""",
                        (now, job_key, attempts),
                    )
                    recovered = recovered or bool(result.rowcount)
        except (OSError, sqlite3.Error, TypeError, ValueError):
            return False
        if recovered:
            with self._active_jobs_lock:
                for job_key, _attempts in active:
                    self._active_jobs.pop(job_key, None)
                self.active_job = next(iter(self._active_jobs), "")
            self._invalidate_status_cache()
        return recovered

    def shutdown(self):
        # Keep shutdown and restart mutually exclusive.  Clearing
        # ``stop_event`` while an old worker is still joining would let that
        # worker continue into the next lifecycle generation.
        with self._lifecycle_lock:
            self.stop_event.set()
            self.fetch_wake_event.set()
            self.tag_wake_event.set()
            self.priority_wake_event.set()
            current = threading.current_thread()
            started = time.monotonic()
            hard_deadline = started + float(MAX_JOB_BUDGET_SECONDS + 1)
            deadline = min(hard_deadline, started + self._worker_shutdown_timeout())

            def join(worker):
                nonlocal deadline
                if worker is None or worker is current or not worker.is_alive():
                    return
                while True:
                    # Every lane clears its own shared wake event after waking, so a
                    # worker that reaches ``wait()`` just after a sibling cleared it
                    # would sleep its whole tick past shutdown and keep SQLite
                    # handles open.  Re-signalling between short join slices costs
                    # nothing (a set flag is idempotent) and guarantees each worker
                    # sees a wake-up before the budget expires.
                    self.fetch_wake_event.set()
                    self.tag_wake_event.set()
                    self.priority_wake_event.set()
                    # A provider chain claimed a moment before ``stop_event`` was set
                    # registers its deadline after the first measurement, so the
                    # budget has to follow *that deadline*.  Extending by the idle
                    # base timeout instead would slide the budget forward on every
                    # slice and turn one shared wait into a fresh wait per worker.
                    ends_at = self._active_job_ends_at()
                    if ends_at is not None:
                        deadline = min(hard_deadline, max(deadline, ends_at + 1.0))
                    worker.join(timeout=min(0.25, max(0.0, deadline - time.monotonic())))
                    if not worker.is_alive() or time.monotonic() >= deadline:
                        return

            for worker in list(self.fetch_threads):
                join(worker)
            join(self.tag_thread)
            join(self.priority_thread)
            return not self._has_live_workers()

    def _active_job_ends_at(self):
        """Absolute end of the longest in-flight job budget, or ``None``.

        A job registers its deadline from inside ``_process_job``, so this can
        appear after ``shutdown`` has already measured its budget.  Only this
        value may extend a shutdown budget: it is bounded by the job budgets
        themselves, while the idle base timeout is not a reason to wait.
        """
        with self._active_jobs_lock:
            ends = [
                deadline
                for deadline in self._active_job_deadlines.values()
                if isinstance(deadline, (int, float)) and not isinstance(deadline, bool) and math.isfinite(deadline)
            ]
        return max(ends) if ends else None

    def _worker_shutdown_timeout(self):
        """Wait through an active bounded provider job before releasing SQLite.

        Provider calls are synchronous and cannot be interrupted by a thread
        event. A fixed short join leaves a recovery worker holding the library
        database after shutdown, especially on Windows where the next temp
        directory cleanup then fails. Idle workers still use the short base
        timeout; active jobs wait only through their already-bounded budget.
        """
        ends_at = self._active_job_ends_at()
        if ends_at is None:
            return 3
        return min(
            float(MAX_JOB_BUDGET_SECONDS + 1),
            max(3.0, ends_at - time.monotonic() + 1.0),
        )

    def _has_live_workers(self):
        workers = list(self.fetch_threads)
        workers.extend((self.tag_thread, self.priority_thread))
        return any(worker is not None and worker.is_alive() for worker in workers)

    def wake(self, force=False):
        if force:
            with self.lock:
                self.force_reconcile = True
        self.fetch_wake_event.set()
        self.tag_wake_event.set()
        self.priority_wake_event.set()

    def retry_failed_tag_writes(self):
        """Return only terminal tag-write failures to the safe background queue."""
        if not self.config.get("metadata_tag_write_enabled", False):
            return 0
        with self._connect() as conn:
            result = conn.execute(
                """UPDATE metadata_jobs
                   SET status='pending', attempts=0, next_attempt_at=0, updated_at=?, last_error=''
                   WHERE job_type='tag_write' AND status='failed'""",
                (int(time.time()),),
            )
        if result.rowcount:
            self._invalidate_status_cache()
            self.tag_wake_event.set()
        return max(0, int(result.rowcount or 0))

    def _run(self):
        while not self.stop_event.is_set():
            if self._metadata_writes_paused():
                self.fetch_wake_event.wait(1)
                self.fetch_wake_event.clear()
                continue
            if not self.config.get("metadata_enabled", False):
                # A candidate dialog is an explicit per-track request. Allow
                # only that bounded priority lane while keeping whole-library
                # reconciliation disabled by default.
                # Explicit playback/lyrics requests use priorities 0/1.  Keep
                # this bounded lane open to both track and album jobs: a
                # currently playing track may need its album artwork/details,
                # and restricting the disabled-background path to ``track``
                # left those album jobs pending forever on fresh installs.
                # Playback-triggered track jobs (priority 1) may enqueue an
                # album artwork/details job (priority 10).  Background
                # enrichment remains disabled, but those explicit jobs must
                # both drain or metadata appears to fetch forever with only
                # the local filename projection visible.
                try:
                    # Tag writes remain exclusively owned by the dedicated
                    # serial writer, even while this disabled-background lane
                    # drains explicit playback metadata requests.
                    priority_job = self._claim_job(priority_max=10, exclude_tag_writes=True)
                    if priority_job:
                        self._process_job(priority_job)
                        continue
                except Exception as exc:
                    # The disabled-background lane is still used for explicit
                    # playback requests. A transient SQLite failure must not
                    # kill its worker and strand those jobs in pending/running.
                    self.last_error = str(exc)
                self.fetch_wake_event.wait(10)
                self.fetch_wake_event.clear()
                continue
            try:
                force = False
                with self.lock:
                    force = self.force_reconcile
                    due = metadata_queue_backlog_policy.should_run_reconcile(
                        time.monotonic() - self._last_reconcile_monotonic,
                        force=force,
                        backlogged=self._queue_is_backlogged(),
                    )
                    if due:
                        # Reconciliation is whole-library work. Claim the time
                        # slot before releasing the lock so only one worker runs it.
                        self.force_reconcile = False
                        self._mark_reconcile()
                if due:
                    self.reconcile(force=force)
                job = self._claim_job(exclude_tag_writes=True)
                if job:
                    self._process_job(job)
                    self.stop_event.wait(0.25)
                    continue
            except Exception as exc:
                self.last_error = str(exc)
            self.fetch_wake_event.wait(10)
            self.fetch_wake_event.clear()

    def _run_tag_writer(self):
        """Serialize destructive file writes, while fetch workers remain concurrent."""
        while not self.stop_event.is_set():
            # Tag writeback is an explicit, independent opt-in.  Do not gate
            # it on whole-library metadata crawling: a user may want to write
            # already cached lyrics/artwork while keeping background provider
            # discovery disabled (the default).
            if not self.config.get("metadata_tag_write_enabled", False):
                self.tag_wake_event.wait(10)
                self.tag_wake_event.clear()
                continue
            if library_scan_is_running():
                # Writing tags during a walk makes files appear and vanish
                # under the scanner: the staging copy is a ghost track, the
                # rename is a delete, and the fresh mtime is a new signature.
                # One scan already costs minutes on this library, so the writer
                # waits for it rather than forcing the next one.
                self.stop_event.wait(2.0)
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
            self.tag_wake_event.wait(1)
            self.tag_wake_event.clear()

    def _run_priority_lyrics(self):
        """Keep an explicitly requested track responsive when enrichment is busy.

        The regular fetch pool remains gated by ``metadata_enabled`` so a fresh
        install does not crawl the whole library. ``lyrics(track_id)`` is an
        explicit user-visible request, though; blocking this queue on the same
        switch made the UI report ``pending`` forever when background enrichment
        was disabled (the default).
        """
        while not self.stop_event.is_set():
            if self._metadata_writes_paused():
                self.priority_wake_event.wait(1)
                self.priority_wake_event.clear()
                continue
            try:
                job = self._claim_job(priority_max=0, lyrics_only=True)
                if job:
                    self._process_job(job)
                    continue
            except Exception as exc:
                self.last_error = str(exc)
            self.priority_wake_event.wait(1)
            self.priority_wake_event.clear()

    def reconcile(self, force=False):
        if not os.path.isfile(library_db_path(self.config)):
            self._mark_reconcile()
            return
        now = int(time.time())
        with self._connect() as conn:
            meta_table = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='library_meta'").fetchone()
            if not meta_table:
                self._mark_reconcile()
                return
            signature_row = conn.execute("SELECT value FROM library_meta WHERE key='signature'").fetchone()
            signature = str(signature_row["value"] or "") if signature_row else ""
            if not force and signature and signature == self.library_signature:
                # On a saturated queue the expired re-queue is pure self-harm:
                # it flips thousands of terminal jobs back to pending, only for
                # the same number to be dropped again six hours later.
                if metadata_queue_backlog_policy.requeue_allowed(*self._queue_pressure()):
                    self._requeue_expired(conn, now)
                if time.monotonic() - self._last_cleanup_monotonic > 3600:
                    self._cleanup_orphans(conn, now)
                    self._prune_artwork_cache(conn)
                    self._mark_cleanup()
                self._mark_reconcile()
                return
            if force:
                conn.execute("UPDATE metadata_entities SET expires_at=0")
                conn.execute("UPDATE metadata_tracks SET expires_at=0")
            # A full reconciliation can create many jobs in one SQLite
            # transaction.  Counting pending rows again for every new track
            # turns a large library into repeated work on the same index.
            # Keep the current transaction's bounded budget locally; direct
            # interactive inserts still use the authoritative database count.
            queue_state = {
                "limit": bounded_int(self.config, "metadata_max_pending_jobs", 20000, 100, 200000),
                "pending": int(conn.execute(
                    "SELECT COUNT(*) FROM metadata_jobs WHERE status IN ('pending','retry')"
                ).fetchone()[0]),
            }
            self._note_queue_pressure(queue_state["pending"], queue_state["limit"])
            # Entity cleanup uses the same SQLite-owned active set as tracks.
            # Do not accumulate every album/artist/composer key in Python
            # before the orphan pass on a large library.
            conn.execute("CREATE TEMP TABLE IF NOT EXISTS active_metadata_entities(entity_type TEXT,entity_key TEXT,PRIMARY KEY(entity_type,entity_key))")
            conn.execute("DELETE FROM active_metadata_entities")
            for row in conn.execute("SELECT name,artist FROM albums"):
                self._reconcile_entity(conn, "album", row["name"], row["artist"], 10, force, None, queue_state)
            for row in conn.execute("SELECT name FROM artists"):
                self._reconcile_entity(conn, "artist", row["name"], "", 20, force, None, queue_state)
            for row in conn.execute("SELECT name FROM composers"):
                self._reconcile_entity(conn, "composer", row["name"], "", 30, force, None, queue_state)
            # Keep the complete active ID set in SQLite, not in a second
            # Python list beside the full track result.  The streaming cursor
            # below keeps reconciliation memory proportional to one track
            # payload even when the library has tens of thousands of files.
            conn.execute("CREATE TEMP TABLE IF NOT EXISTS active_metadata_tracks(track_id TEXT PRIMARY KEY)")
            conn.execute("DELETE FROM active_metadata_tracks")
            conn.execute("INSERT OR IGNORE INTO active_metadata_tracks(track_id) SELECT id FROM tracks")
            # Read both per-track cache expiries in the same streaming query.
            # The previous loop issued two extra SQLite statements per track,
            # which made a large-library reconcile needlessly chatty while
            # holding the transaction open.  LEFT JOIN keeps uncached tracks
            # visible and preserves the existing expiry/force semantics.
            track_rows = conn.execute(
                """SELECT t.id,t.path,t.title,t.artist,t.album,t.duration,t.item_json,
                          lyrics.expires_at AS lyrics_expires_at,
                          matches.expires_at AS match_expires_at
                   FROM tracks AS t
                   LEFT JOIN metadata_tracks AS lyrics
                     ON lyrics.track_id=t.id AND lyrics.orphaned_at=0
                   LEFT JOIN metadata_track_matches AS matches
                     ON matches.track_id=t.id AND matches.orphaned_at=0"""
            )
            for row in track_rows:
                track_id = str(row["id"] or "")
                if force or bounded_epoch(row["lyrics_expires_at"]) <= now:
                    self._upsert_job(conn, "lyrics:" + track_id, "lyrics", track_id, dict(row), 100, force, queue_state)
                if self._needs_track_enrichment(row):
                    if force or bounded_epoch(row["match_expires_at"]) <= now:
                        self._upsert_job(conn, "track:" + track_id, "track", track_id, dict(row), 25, force, queue_state)

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

            conn.execute("UPDATE metadata_tracks SET orphaned_at=0 WHERE track_id IN (SELECT track_id FROM active_metadata_tracks)")
            conn.execute("UPDATE metadata_tracks SET orphaned_at=? WHERE orphaned_at=0 AND track_id NOT IN (SELECT track_id FROM active_metadata_tracks)", (now,))
            conn.execute(
                "DELETE FROM metadata_jobs WHERE job_type IN ('lyrics','track','tag_write') AND entity_key NOT IN (SELECT track_id FROM active_metadata_tracks)"
            )
            conn.execute("UPDATE metadata_track_matches SET orphaned_at=0 WHERE track_id IN (SELECT track_id FROM active_metadata_tracks)")
            conn.execute("UPDATE metadata_track_matches SET orphaned_at=? WHERE track_id NOT IN (SELECT track_id FROM active_metadata_tracks) AND orphaned_at=0", (now,))
            self._cleanup_orphans(conn, now)
            self._prune_artwork_cache(conn)
            self._mark_cleanup()
            self.library_signature = signature
        self._mark_reconcile()

    def _mark_reconcile(self):
        self.last_reconcile = time.time()
        self._last_reconcile_monotonic = time.monotonic()

    def _note_queue_pressure(self, pending, limit):
        """Remember occupancy already in hand instead of counting again."""
        try:
            bounded_pending = int(pending)
            bounded_limit = int(limit)
        except (TypeError, ValueError, OverflowError):
            return
        if bounded_pending < 0 or bounded_limit <= 0:
            return
        cap = metadata_queue_backlog_policy.MAX_QUEUE_COUNTER
        self._observed_queue_pressure = (min(bounded_pending, cap), bounded_limit)

    def _queue_pressure(self):
        """Last observed (pending, limit).  Callers may unpack it directly."""
        try:
            pending, limit = self._observed_queue_pressure
        except (TypeError, ValueError):
            return (0, 0)
        return (pending, limit)

    def _queue_is_backlogged(self):
        pending, limit = self._queue_pressure()
        return metadata_queue_backlog_policy.queue_is_backlogged(pending, limit)

    def _mark_cleanup(self):
        self.last_cleanup = time.time()
        self._last_cleanup_monotonic = time.monotonic()

    @staticmethod
    def _needs_track_enrichment(row):
        return needs_track_enrichment(row)

    def _reconcile_entity(self, conn, kind, name, artist, priority, force, active_entities, queue_state=None):
        name = str(name or "").strip()
        artist = str(artist or "").strip()
        if name.casefold() in {value.casefold() for value in PLACEHOLDER_NAMES}:
            return
        key = entity_key(kind, name, artist)
        if not key:
            return
        if active_entities is None:
            conn.execute(
                "INSERT OR IGNORE INTO active_metadata_entities(entity_type,entity_key) VALUES (?,?)",
                (kind, key),
            )
        else:
            active_entities.append((kind, key))
        cached = conn.execute("SELECT expires_at FROM metadata_entities WHERE entity_type=? AND entity_key=?", (kind, key)).fetchone()
        if force or not cached or bounded_epoch(cached["expires_at"]) <= int(time.time()):
            payload = {"name": name, "artist": artist}
            self._upsert_job(conn, "%s:%s" % (kind, key), kind, key, payload, priority, force, queue_state)

    def _upsert_job(self, conn, job_key, job_type, key, payload, priority, force=False, queue_state=None):
        now = int(time.time())
        payload_json = json.dumps(project_metadata_job_payload(payload), ensure_ascii=False)
        existing = conn.execute("SELECT 1 FROM metadata_jobs WHERE job_key=?", (job_key,)).fetchone()
        if not existing:
            queue_limit, pending = project_queue_state(
                queue_state,
                bounded_int(self.config, "metadata_max_pending_jobs", 20000, 100, 200000),
            )
            if not isinstance(queue_state, dict):
                pending = int(
                    conn.execute("SELECT COUNT(*) FROM metadata_jobs WHERE status IN ('pending','retry')").fetchone()[0]
                )
            else:
                try:
                    raw_pending = queue_state.get("pending")
                except Exception:
                    raw_pending = None
                if not isinstance(raw_pending, int) or isinstance(raw_pending, bool):
                    pending = int(
                        conn.execute("SELECT COUNT(*) FROM metadata_jobs WHERE status IN ('pending','retry')").fetchone()[0]
                    )
            if pending >= queue_limit:
                self._note_queue_pressure(pending, queue_limit)
                evicted = None
                if int(priority) < 100:
                    evicted = conn.execute(
                        """SELECT job_key FROM metadata_jobs
                           WHERE status IN ('pending','retry') AND priority>?
                           ORDER BY priority DESC,updated_at ASC LIMIT 1""",
                        (int(priority),),
                    ).fetchone()
                if not evicted:
                    self.dropped_jobs = saturating_counter(self.dropped_jobs)
                    return False
                conn.execute("DELETE FROM metadata_jobs WHERE job_key=?", (evicted["job_key"],))
                self.dropped_jobs = saturating_counter(self.dropped_jobs)
        conn.execute(
            """INSERT INTO metadata_jobs(job_key,job_type,entity_key,payload_json,priority,status,attempts,next_attempt_at,updated_at,last_error)
               VALUES (?,?,?,?,?,'pending',0,0,?,'')
               ON CONFLICT(job_key) DO UPDATE SET
                 payload_json=excluded.payload_json, priority=MIN(metadata_jobs.priority, excluded.priority),
                 -- Polling/priority promotion must not continuously push an
                 -- already queued job to the back of FIFO ordering. Keep its
                 -- lifecycle and retry backoff intact, while still allowing
                 -- an interactive current-track request to lower priority.
                 status=CASE WHEN metadata_jobs.status IN ('pending','retry','running')
                             THEN metadata_jobs.status ELSE 'pending' END,
                 attempts=CASE WHEN metadata_jobs.status IN ('pending','retry','running')
                               THEN metadata_jobs.attempts ELSE 0 END,
                 next_attempt_at=CASE WHEN metadata_jobs.status IN ('pending','retry','running')
                                      THEN metadata_jobs.next_attempt_at
                                      WHEN ? THEN 0 ELSE metadata_jobs.next_attempt_at END,
                 updated_at=CASE WHEN metadata_jobs.status IN ('pending','retry','running')
                                 THEN metadata_jobs.updated_at ELSE excluded.updated_at END,
                 last_error=CASE WHEN metadata_jobs.status IN ('pending','retry','running')
                                 THEN metadata_jobs.last_error ELSE '' END""",
            (job_key, job_type, key, payload_json, priority, now, 1 if force else 0),
        )
        if not existing and queue_state is not None:
            # Evicting a pending job before inserting a priority job leaves
            # the count unchanged; otherwise this transaction gained one.
            if pending < queue_limit:
                queue_state["pending"] = pending + 1
        self._invalidate_status_cache()
        return True

    def _claim_job(self, priority_max=None, lyrics_only=False, tag_writes_only=False, exclude_tag_writes=False, track_only=False):
        if self.stop_event.is_set():
            # Shutdown measures its join budget once, before workers notice the
            # flag.  A job claimed after that point is new provider work whose
            # deadline the join can never cover, so the worker leaves shutdown
            # still running with SQLite handles open (on Windows the next temp
            # directory cleanup then fails).  Leaving the row pending is also the
            # honest state for a next lifecycle generation.
            return None
        now = int(time.time())
        with self._connect() as conn:
            clauses = ["status IN ('pending','retry')", "next_attempt_at<=?"]
            values = [now]
            if priority_max is not None:
                clauses.append("priority<=?")
                values.append(int(priority_max))
            if lyrics_only:
                clauses.append("job_type='lyrics'")
            if track_only:
                clauses.append("job_type='track'")
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
            claim_where = "job_key=? AND status IN ('pending','retry')"
            claim_values = [now, row["job_key"]]
            if tag_writes_only:
                # Recheck inside the write statement. Two service instances
                # can both pass the SELECT guard before either updates its
                # row; the atomic condition keeps destructive writes serial.
                claim_where += " AND NOT EXISTS (SELECT 1 FROM metadata_jobs WHERE job_type='tag_write' AND status='running')"
            claimed = conn.execute(
                "UPDATE metadata_jobs SET status='running',attempts=attempts+1,updated_at=? WHERE " + claim_where,
                claim_values,
            )
            if not claimed.rowcount:
                return None
            self._invalidate_status_cache()
            return dict(row)

    def _mark_job_active(self, job_key, attempts=None):
        """Publish a stable active-job diagnostic across parallel workers."""
        key = str(job_key or "")
        if not key:
            return
        with self._active_jobs_lock:
            self._active_jobs[key] = attempts
            # Keep the long-standing scalar for compatibility with local
            # diagnostics, while status reads the lock-protected projection.
            self.active_job = next(iter(self._active_jobs), "")

    def _clear_active_job(self, job_key):
        key = str(job_key or "")
        with self._active_jobs_lock:
            self._active_jobs.pop(key, None)
            self.active_job = next(iter(self._active_jobs), "")

    def _active_job_snapshot(self):
        with self._active_jobs_lock:
            return next(iter(self._active_jobs), "")

    @staticmethod
    def _is_transient_sqlite_lock(exc):
        detail = str(exc or "").lower()
        return isinstance(exc, sqlite3.OperationalError) and any(
            marker in detail for marker in ("database is locked", "database table is locked", "busy")
        )

    def _metadata_writes_paused(self):
        """Keep metadata writers out of the scanner's long write transaction."""
        return bool(library_scan_is_running())

    def _run_database_write_with_retry(self, operation):
        """Retry only short-lived SQLite lock failures at a metadata write boundary."""
        for index, delay in enumerate((0.0,) + SQLITE_LOCK_RETRY_DELAYS):
            if delay:
                self.stop_event.wait(delay)
            try:
                return operation()
            except sqlite3.OperationalError as exc:
                if not self._is_transient_sqlite_lock(exc) or index == len(SQLITE_LOCK_RETRY_DELAYS):
                    raise

    def _process_job(self, job):
        job_key = job.get("job_key") or ""
        # `_claim_job` returns the row as it was before the atomic claim.  The
        # incremented attempt is therefore the ownership generation for this
        # worker. Completion paths use it to ignore a late result from a
        # worker whose job was already recovered and claimed again.
        claimed_attempts = nonnegative_int(job.get("attempts")) + 1
        self._mark_job_active(job_key, claimed_attempts)
        try:
            payload = json.loads(job.get("payload_json") or "{}")
            budget_seconds = (
                LYRICS_JOB_BUDGET_SECONDS
                if job["job_type"] == "lyrics"
                else DEFAULT_JOB_BUDGET_SECONDS
            )
            with self._active_jobs_lock:
                self._active_job_deadlines[job_key] = time.monotonic() + bounded_job_budget(budget_seconds)
            self.providers.begin_job_observation(budget_seconds)
            job_provider_failed = False
            if job["job_type"] == "lyrics":
                result = self.providers.lyrics(payload) or {}
                job_provider_failed = self.providers.job_observed_provider_failure()
                # When the lyric chain has already observed a provider
                # failure, do not immediately fan out into artwork providers.
                # That second network chain can turn a bounded retryable
                # lyric failure into a long wait (and, if it happens to return
                # an empty object, incorrectly look like a completed job).
                # A clean no-match still gets the normal artwork fallback.
                # If every lyric source misses/fails, still allow one bounded
                # artwork/candidate fallback.  A partial lyric-provider
                # outage must not make an otherwise usable cover disappear;
                # when lyrics succeeded we keep the no-extra-fanout rule.
                if not result.get("image_url") and (
                    not job_provider_failed
                    or not result.get("lyrics")
                ):
                    artwork = self.providers.track_artwork(payload)
                    if artwork:
                        result.update(artwork)
                self._store_lyrics(job["entity_key"], result)
            elif job["job_type"] == "track":
                candidates = self.providers.track_candidates(payload)
                result = self._store_track_match(job["entity_key"], candidates)
                # Track matching can be the only successful enrichment path
                # when a file has no usable album tag. Persist its artwork as
                # a track asset too; otherwise the candidate URL is retained
                # only in JSON and the UI never gets a cacheable cover.
                artwork_candidate = result if isinstance(result, dict) else None
                if not (artwork_candidate and artwork_candidate.get("image_url")):
                    artwork_candidate = next(
                        (candidate for candidate in candidates
                         if isinstance(candidate, dict) and candidate.get("image_url")),
                        None,
                    )
                if artwork_candidate and artwork_candidate.get("image_url"):
                    self._store_track_artwork(job["entity_key"], artwork_candidate)
            elif job["job_type"] == "tag_write":
                result = self._write_track_tags(job["entity_key"])
            else:
                result = self.providers.album(payload.get("name"), payload.get("artist")) if job["job_type"] == "album" else self.providers.person(payload.get("name"))
                self._store_entity(job["job_type"], job["entity_key"], payload, result)
            # Do not turn a transient provider outage into a long-lived
            # negative cache. A genuine empty search remains no_match; a new
            # provider failure remains retryable and is surfaced in status.
            provider_failed = self.providers.job_observed_provider_failure()
            # Preserve a lyric-source outage as retryable when the bounded
            # artwork fallback also produced no usable result.  A successful
            # fallback is still a completed metadata job. The pure policy also
            # rejects malformed provider payloads as non-successes.
            status = worker_status(result, provider_failed, job_provider_failed, job["job_type"])
            self._finish_job(
                job["job_key"], status,
                "provider unavailable" if status == "failed" else "",
                expected_attempts=claimed_attempts,
            )
        except Exception as exc:
            attempts = claimed_attempts
            if not retry_attempt(attempts, 5):
                self._finish_job(job["job_key"], "failed", str(exc), expected_attempts=claimed_attempts)
            else:
                self._retry_job(job["job_key"], attempts, str(exc), expected_attempts=claimed_attempts)
            self.last_error = str(exc)
        finally:
            self._clear_active_job(job_key)
            with self._active_jobs_lock:
                self._active_job_deadlines.pop(job_key, None)
            self.providers.end_job_observation()

    def _store_entity(self, kind, key, payload, result):
        now = int(time.time())
        result = result if isinstance(result, dict) else {}
        payload = payload if isinstance(payload, dict) else {}
        with self._connect() as conn:
            previous = conn.execute(
                "SELECT name,artist,release_date,artwork_id,source,provider_id,confidence FROM metadata_entities WHERE entity_type=? AND entity_key=? AND orphaned_at=0",
                (kind, key),
            ).fetchone()
        artwork_id = ""
        image_url = _provider_text(result.get("image_url"), 2048)
        if image_url:
            try:
                artwork_id = self._download_artwork(image_url, _provider_text(result.get("source"), 64))
            except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError):
                artwork_id = ""
        artwork_id = normalize_artwork_id(artwork_id)
        name = _provider_text(payload.get("name"), 512)
        payload_artist = _provider_text(payload.get("artist"), 512)
        fresh_artist = _provider_text(result.get("artist"), 512)
        fresh_release_date = normalize_release_date(result.get("release_date"))
        previous_values = tuple(previous) if previous else ("", "", "", "", "", "", 0.0)
        # A failed/empty refresh must not erase the last usable projection.
        # The job status still records the failure and its retry policy, while
        # this row remains available to the UI until a newer result succeeds.
        name = name or _provider_text(previous_values[0], 512)
        artist = fresh_artist or payload_artist or _provider_text(previous_values[1], 512)
        release_date = fresh_release_date or _provider_text(previous_values[2], 64)
        artwork_id = artwork_id or normalize_artwork_id(_provider_text(previous_values[3], 128))
        source = _provider_text(result.get("source"), 64) or _provider_text(previous_values[4], 64)
        provider_id = _provider_text(result.get("provider_id"), 128) or _provider_text(previous_values[5], 128)
        confidence = finite_confidence(result.get("confidence"))
        if not result.get("confidence") and previous:
            confidence = finite_confidence(previous_values[6])
        # Keep a stale usable projection visible after an empty/failing
        # refresh, but do not let those preserved fields turn the refresh into
        # a fresh positive cache entry. Empty provider results must become
        # retryable after NEGATIVE_TTL rather than suppressing recovery for
        # the full POSITIVE_TTL.
        positive = bool(fresh_artist or fresh_release_date or artwork_id)
        raw_json = _entity_raw_json(result)
        projection_changed = False
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO metadata_entities(
                    entity_type,entity_key,name,artist,release_date,artwork_id,source,provider_id,confidence,fetched_at,expires_at,orphaned_at,raw_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    kind, key, name, artist, release_date, artwork_id, source,
                    provider_id, confidence, now,
                    now + (POSITIVE_TTL if positive else NEGATIVE_TTL), 0, raw_json,
                ),
            )
            if kind == "album" and artwork_id:
                self._queue_album_tag_writes(conn, name, payload_artist)
            current_projection = (name, artist, release_date, artwork_id, source, provider_id, confidence)
            previous_projection = tuple(previous) if previous else None
            projection_changed = previous_projection != current_projection
        self._invalidate_status_cache(projection_changed=projection_changed)

    def _store_lyrics(self, track_id, result):
        now = int(time.time())
        result = result if isinstance(result, dict) else {}
        lyrics = _lyrics_document(result.get("lyrics"))
        artwork_id = ""
        image_url = _provider_text(result.get("image_url"), 2048)
        if image_url:
            try:
                artwork_id = self._download_artwork(image_url, _provider_text(result.get("source"), 64))
            except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError):
                artwork_id = ""
        artwork_id = normalize_artwork_id(artwork_id)
        projection_changed = False
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT lyrics,artwork_id,lyrics_source,provider_id,confidence FROM metadata_tracks WHERE track_id=?",
                (track_id,),
            ).fetchone()
            if not lyrics:
                lyrics = _lyrics_document(existing["lyrics"] if existing else "")
            if not artwork_id:
                cached_artwork = _provider_text(existing["artwork_id"] if existing else "", 128).strip().lower()
                artwork_id = normalize_artwork_id(cached_artwork)
            existing_source = _provider_text(existing["lyrics_source"] if existing else "", 64)
            existing_provider_id = _provider_text(existing["provider_id"] if existing else "", 128)
            existing_confidence = finite_confidence(existing["confidence"] if existing else 0.0)
            source = _provider_text(result.get("source"), 64) or existing_source
            provider_id = _provider_text(result.get("provider_id"), 128) or existing_provider_id
            confidence = finite_confidence(result.get("confidence"))
            if not result.get("confidence") and existing:
                confidence = existing_confidence
            conn.execute(
                """INSERT OR REPLACE INTO metadata_tracks(
                    track_id,lyrics,artwork_id,lyrics_source,provider_id,confidence,fetched_at,expires_at,orphaned_at
                ) VALUES (?,?,?,?,?,?,?,?,0)""",
                (
                    track_id, lyrics, artwork_id, source, provider_id,
                    confidence, now, now + (POSITIVE_TTL if lyrics else NEGATIVE_TTL),
                ),
            )
            if lyrics or artwork_id:
                self._queue_tag_write(conn, track_id)
            # Repeated polling can receive the same provider result several
            # times.  Updating fetched_at keeps the TTL healthy, but does not
            # constitute a metadata projection change and must not make the
            # frontend redraw the visible page again.
            projection_changed = bool(
                (existing is None and (lyrics or artwork_id))
                or (existing is not None and (
                    str(existing["lyrics"] or "") != lyrics
                    or str(existing["artwork_id"] or "") != artwork_id
                ))
            )
        self._invalidate_status_cache(projection_changed=projection_changed)

    def _store_track_artwork(self, track_id, result):
        """Persist candidate artwork without replacing an existing track asset."""
        result = result if isinstance(result, dict) else {}
        image_url = _provider_text(result.get("image_url"), 2048)
        if not image_url:
            return False
        # Avoid re-downloading the same candidate when a retry/reconcile sees
        # an already populated track asset. This keeps provider traffic and
        # artwork decoding bounded while preserving the first successful
        # source as authoritative.
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT lyrics,artwork_id,lyrics_source,provider_id,confidence FROM metadata_tracks WHERE track_id=? AND orphaned_at=0",
                (str(track_id),),
            ).fetchone()
            existing_artwork = _provider_text(existing["artwork_id"] if existing else "", 128).strip().lower()
            if existing and valid_artwork_id(existing_artwork):
                return False
        try:
            artwork_id = self._download_artwork(image_url, _provider_text(result.get("source"), 64))
        except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError):
            return False
        if not artwork_id:
            return False
        artwork_id = normalize_artwork_id(artwork_id)
        if not artwork_id:
            return False
        now = int(time.time())
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT lyrics,artwork_id,lyrics_source,provider_id,confidence FROM metadata_tracks WHERE track_id=? AND orphaned_at=0",
                (str(track_id),),
            ).fetchone()
            existing_artwork = _provider_text(existing["artwork_id"] if existing else "", 128).strip().lower()
            if existing and valid_artwork_id(existing_artwork):
                return False
            confidence = finite_confidence(existing["confidence"] if existing else result.get("confidence"))
            conn.execute(
                """INSERT OR REPLACE INTO metadata_tracks(
                    track_id,lyrics,artwork_id,lyrics_source,provider_id,confidence,fetched_at,expires_at,orphaned_at
                ) VALUES (?,?,?,?,?,?,?,?,0)""",
                (
                    str(track_id), _lyrics_document(existing["lyrics"] if existing else ""), artwork_id,
                    _provider_text(existing["lyrics_source"] if existing else result.get("source"), 64),
                    _provider_text(existing["provider_id"] if existing else result.get("provider_id"), 128),
                    confidence,
                    now, now + POSITIVE_TTL,
                ),
            )
            self._queue_tag_write(conn, str(track_id))
        self._invalidate_status_cache(projection_changed=True)
        return True

    def _store_track_match(self, track_id, candidates):
        """Persist the best candidate, but only auto-apply unambiguous matches."""
        # Keep provider-shape cleanup outside the persistence transaction so
        # malformed scores cannot affect transaction control flow.
        candidates = normalize_track_candidates(candidates)
        best = candidates[0] if candidates else {}
        runner_up = candidates[1] if len(candidates) > 1 else {}
        confidence = finite_confidence(best.get("confidence") if isinstance(best, dict) else 0)
        margin = confidence - finite_confidence(runner_up.get("confidence") if isinstance(runner_up, dict) else 0)
        status = "no_match" if not best else ("auto" if confidence >= AUTO_TRACK_MATCH_CONFIDENCE and margin >= AUTO_TRACK_MATCH_MARGIN else "review")
        now = int(time.time())
        # Provider dictionaries can carry the same fields in a different key
        # order across requests. Persist a canonical representation so that
        # equivalent candidates do not look like a projection change and
        # needlessly redraw a visible library page.
        fields_json = json.dumps(
            {"best": best, "candidates": candidates},
            ensure_ascii=False,
            sort_keys=True,
        )
        projection_changed = False
        with self._connect() as conn:
            previous_cursor = conn.execute(
                "SELECT fields_json,status FROM metadata_track_matches WHERE track_id=? AND orphaned_at=0",
                (track_id,),
            )
            previous = previous_cursor.fetchone() if previous_cursor is not None else None
            conn.execute(
                """INSERT OR REPLACE INTO metadata_track_matches(
                    track_id,fields_json,source,provider_id,confidence,status,fetched_at,expires_at,orphaned_at
                ) VALUES (?,?,?,?,?,?,?,?,0)""",
                 (track_id, fields_json,
                  _provider_text(best.get("source"), 64), _provider_text(best.get("provider_id"), 128), confidence,
                  status, now, now + (POSITIVE_TTL if best else NEGATIVE_TTL)),
            )
            if status == "auto":
                self._queue_tag_write(conn, track_id)
            # Only auto/confirmed matches are merged into ordinary library
            # rows. Review candidates are manual-dialog data, so replacing
            # them must not invalidate the visible-page cache or cause a
            # list/cover redraw while provider ranking settles.
            previous_projection = visible_match_projection_signature(
                previous["fields_json"], previous["status"],
            ) if previous else ()
            current_projection = visible_match_projection_signature(fields_json, status)
            projection_changed = previous_projection != current_projection
        self._invalidate_status_cache(projection_changed=projection_changed)
        return best or None

    def _track_match_fields(self, conn, track_id, include_review=False):
        row = conn.execute(
            "SELECT fields_json,status FROM metadata_track_matches WHERE track_id=? AND orphaned_at=0",
            (track_id,),
        ).fetchone()
        if not row or (row["status"] not in ("auto", "confirmed") and not include_review):
            return {}
        fields = decode_track_match_fields(row["fields_json"])
        best = fields.get("best")
        normalized = normalize_track_candidates([best])
        return normalized[0] if normalized else {}

    def _cached_album_artwork_id(self, conn, album, album_artist, artist):
        """Return the validated album asset for a track's canonical identity."""
        album = str(album or "").strip()
        if not album:
            return ""
        album_artist = str(album_artist or "").strip()
        artist = str(artist or "").strip()
        album_key = entity_key("album", album, album_artist or artist)
        row = conn.execute(
            "SELECT artwork_id FROM metadata_entities WHERE entity_type='album' AND entity_key=? AND orphaned_at=0",
            (album_key,),
        ).fetchone()
        # Caches created before album_artist joined the canonical identity
        # remain usable for compilation albums and artist credits that differ
        # between a recording and its release.
        if not row and album_artist and artist and album_artist != artist:
            legacy_key = entity_key("album", album, artist)
            row = conn.execute(
                "SELECT artwork_id FROM metadata_entities WHERE entity_type='album' AND entity_key=? AND orphaned_at=0",
                (legacy_key,),
            ).fetchone()
        artwork_id = _provider_text(row["artwork_id"] if row else "", 128).strip().lower()
        return normalize_artwork_id(artwork_id)

    def apply_track_match(self, track_id, candidate_index=0):
        """Confirm one stored candidate and promote it to safe writeback."""
        track_id = normalize_track_id(track_id)
        if not track_id:
            return False
        candidate_index = strict_nonnegative_int(candidate_index)
        if candidate_index is None:
            return False
        with self._connect() as conn:
            row = conn.execute(
                "SELECT fields_json FROM metadata_track_matches WHERE track_id=? AND orphaned_at=0",
                (track_id,),
            ).fetchone()
            if not row:
                return False
            fields = decode_track_match_fields(row["fields_json"])
            if not fields:
                return False
            candidates = normalize_track_candidates(fields.get("candidates"))
            if candidate_index >= len(candidates) or not isinstance(candidates[candidate_index], dict):
                return False
            selected = dict(candidates[candidate_index])
            fields = {"best": selected, "candidates": candidates}
            conn.execute(
                """UPDATE metadata_track_matches
                   SET fields_json=?,source=?,provider_id=?,confidence=?,status='confirmed'
                   WHERE track_id=?""",
                (
                    json.dumps(fields, ensure_ascii=False),
                    str(selected.get("source") or ""),
                    str(selected.get("provider_id") or ""),
                    finite_confidence(selected.get("confidence")),
                    track_id,
                ),
            )
            self._queue_tag_write(conn, track_id)
        # Confirmation promotes candidate fields into the visible track
        # projection, so cached library pages must be invalidated immediately.
        self._invalidate_status_cache(projection_changed=True)
        self.tag_wake_event.set()
        return True

    def track_match(self, track_id, retry_failed=False):
        """Return cached candidates, or explicitly retry a terminal lookup.

        Negative matches are intentionally cached to protect providers during a
        whole-library pass.  A user reopening the candidate dialog is a
        different, bounded request: permit it to replace only that track's
        terminal result without enabling background enrichment globally.
        """
        track_id = normalize_track_id(track_id)
        if not track_id:
            return {"track_id": "", "status": "invalid", "best": {}, "candidates": []}
        if retry_failed:
            self.providers.reset_provider_cooldowns()
        now = int(time.time())
        with self._connect() as conn:
            row = conn.execute(
                """SELECT fields_json,source,provider_id,confidence,status,fetched_at,expires_at,
                          (SELECT artwork_id FROM metadata_tracks
                           WHERE track_id=metadata_track_matches.track_id AND orphaned_at=0
                           LIMIT 1) AS artwork_id
                     FROM metadata_track_matches
                     WHERE track_id=? AND orphaned_at=0""",
                (track_id,),
            ).fetchone()
            expired = bool(row and bounded_epoch(row["expires_at"]) <= now)
            # A provider outage is retryable too.  Treat both terminal
            # projections as explicitly recoverable; otherwise a prior
            # ``failed`` row can permanently mask the user's "重新查询此
            # 歌曲" action until its TTL expires.
            terminal = bool(row and str(row["status"] or "") in ("failed", "no_match"))
            if not row or expired or (retry_failed and terminal):
                track = conn.execute("SELECT id,title,artist,album,path,duration,item_json FROM tracks WHERE id=?", (track_id,)).fetchone()
                if not track:
                    return None
                # A lyrics/artwork worker can complete before the recording
                # match row is materialized (for example after a restart or
                # when the provider candidate chain returns no usable match).
                # Keep that independently cached projection visible on the
                # first interactive request instead of making the UI wait for
                # a second track-match cycle and briefly showing no cover.
                cached_track = conn.execute(
                    "SELECT lyrics,artwork_id,lyrics_source FROM metadata_tracks "
                    "WHERE track_id=? AND orphaned_at=0",
                    (track_id,),
                ).fetchone()
                # The visible-page lane polls while a provider job is still
                # pending. Do not rewrite an existing pending/running job on
                # every poll: doing so updates its timestamp and can keep it
                # at the tail of the worker's FIFO ordering indefinitely.
                existing_job = conn.execute(
                    "SELECT status FROM metadata_jobs WHERE job_key=?",
                    ("track:" + track_id,),
                ).fetchone()
                existing_status = str(existing_job["status"] or "") if existing_job else ""
                if existing_status not in ("pending", "retry", "running"):
                    self._upsert_job(conn, "track:" + track_id, "track", track_id, dict(track), 1, True)
                    # Only a newly queued terminal/missing lookup may start
                    # the pool here.  Polling an existing active job must not
                    # alter its lifecycle or race it into ``running`` before
                    # the caller can observe the stable pending projection.
                    self.ensure_workers("fetch")
                self.fetch_wake_event.set()
                self._invalidate_status_cache()
                # Return a local, low-confidence identity immediately while
                # the provider worker is warming up.  This keeps the UI
                # useful for untagged files even when external metadata is
                # temporarily unavailable; it is never auto-applied or
                # written back to the source tag.
                # Return the scanned Tag projection immediately while the
                # provider worker is warming up.  Previously this path only
                # exposed a filename-derived candidate, so a fully tagged
                # track with a missing cover appeared to have no metadata at
                # all until a remote provider completed.  The local
                # candidate is presentation-only and is never auto-written.
                local = local_track_candidate(track) or filename_track_candidate(track)
                result = {"track_id": track_id, "status": "pending", "pending": True,
                          "best": local or {}, "candidates": [local] if local else []}
                cached_artwork_id = _provider_text(cached_track["artwork_id"] if cached_track else "", 128).strip().lower()
                cached_artwork_url = artwork_url(cached_artwork_id)
                if cached_artwork_url:
                    result["image_url"] = cached_artwork_url
                cached_lyrics = _lyrics_document(cached_track["lyrics"] if cached_track else "")
                if cached_lyrics:
                    result["lyrics"] = cached_lyrics
                    result["lyrics_source"] = _provider_text(cached_track["lyrics_source"] if cached_track else "", 64)
                return result
            job = conn.execute(
                "SELECT status,attempts,last_error,updated_at FROM metadata_jobs WHERE job_key=?",
                ("track:" + track_id,),
            ).fetchone()
            job_status = str(job["status"] or "") if job else ""
            # Older caches can contain a terminal match row without the
            # corresponding metadata_jobs record.  Do not let that legacy
            # negative result become permanent: use the row's fetched_at as
            # the same bounded cooldown timestamp when the job row is absent.
            retry_timestamp = job["updated_at"] if job else row["fetched_at"]
            if str(row["status"] or "") in ("failed", "no_match") and not retry_failed and should_auto_retry_failed(str(row["status"] or ""), retry_timestamp, now):
                self.ensure_workers("fetch")
                conn.execute(
                    "UPDATE metadata_jobs SET status='pending',attempts=0,next_attempt_at=0,updated_at=?,last_error='' WHERE job_key=? AND status IN ('failed','no_match')",
                    (now, "track:" + track_id),
                )
                if not job:
                    track = conn.execute("SELECT id,title,artist,album,path,duration,item_json FROM tracks WHERE id=?", (track_id,)).fetchone()
                    if track:
                        self._upsert_job(conn, "track:" + track_id, "track", track_id, dict(track), 1, True)
                self._invalidate_status_cache()
                self.fetch_wake_event.set()
                return {"track_id": track_id, "status": "pending", "pending": True, "best": {}, "candidates": []}
            # A damaged JSON cache must not masquerade as a valid completed
            # lookup.  Requeue only non-confirmed rows; an explicit user
            # confirmation remains authoritative even if its auxiliary JSON
            # cannot be decoded.
            malformed_fields = False
            fields_probe = {}
            try:
                fields_probe = decode_track_match_fields(row["fields_json"])
                malformed_fields = not track_match_fields_are_valid(row["fields_json"])
            except Exception:
                malformed_fields = True
            # Older builds could leave a nominal ``review``/``auto`` match
            # whose JSON is structurally valid but contains neither a best
            # recording nor a candidate.  That is not a real result: the UI
            # used to see a non-pending status and stop asking, leaving the
            # song looking as if metadata fetching had silently stopped until
            # the long positive TTL expired.  Keep a genuine ``no_match``
            # negative cache intact, but heal these impossible success rows
            # through the same bounded priority lane used for a fresh lookup.
            cached_status = str(row["status"] or "")
            best_probe = fields_probe.get("best") if isinstance(fields_probe, dict) else None
            candidates_probe = normalize_track_candidates(fields_probe.get("candidates")) if isinstance(fields_probe, dict) else []
            has_usable_candidate = candidate_has_displayable_fields(best_probe)
            if not has_usable_candidate:
                has_usable_candidate = any(candidate_has_displayable_fields(candidate) for candidate in candidates_probe)
            unusable_success = cached_status in ("auto", "review") and not has_usable_candidate
            if (malformed_fields or unusable_success) and cached_status != "confirmed":
                track = conn.execute("SELECT id,title,artist,album,path,duration,item_json FROM tracks WHERE id=?", (track_id,)).fetchone()
                if track:
                    self._upsert_job(conn, "track:" + track_id, "track", track_id, dict(track), 1, True)
                    self.fetch_wake_event.set()
                    self._invalidate_status_cache()
                    # Corrupt success payloads are repaired conservatively;
                    # do not project a filename candidate until the queued
                    # lookup has produced a structurally valid result.
                    repaired = {"track_id": track_id, "status": "pending", "pending": True, "best": {}, "candidates": []}
                    # The match JSON may be damaged while the independent
                    # lyrics/artwork projection is still valid. Preserve it
                    # during repair so the UI does not flash a coverless row
                    # and incorrectly conclude that metadata is unavailable.
                    repaired_artwork_id = _provider_text(row["artwork_id"], 128).strip().lower()
                    repaired_artwork_url = artwork_url(repaired_artwork_id)
                    if repaired_artwork_url:
                        repaired["image_url"] = repaired_artwork_url
                    # Reuse the active connection: `_upsert_job()` has just
                    # written on this transaction, and opening a nested
                    # SQLite connection here can contend for the write lock
                    # on NAS filesystems with conservative locking modes.
                    cached_track = conn.execute(
                        "SELECT lyrics,lyrics_source FROM metadata_tracks "
                        "WHERE track_id=? AND orphaned_at=0",
                        (track_id,),
                    ).fetchone()
                    repaired_lyrics = _lyrics_document(cached_track["lyrics"] if cached_track else "")
                    if repaired_lyrics:
                        repaired["lyrics"] = repaired_lyrics
                        repaired["lyrics_source"] = _provider_text(cached_track["lyrics_source"] if cached_track else "", 64)
                    return repaired
        fields = decode_track_match_fields(row["fields_json"])
        normalized_best = normalize_track_candidates([fields.get("best")])
        best = normalized_best[0] if normalized_best else {}
        candidates = normalize_track_candidates(fields.get("candidates"))
        confidence = finite_confidence(row["confidence"])
        fetched_at = bounded_epoch(row["fetched_at"])
        try:
            expires_at = bounded_epoch(row["expires_at"])
        except (TypeError, ValueError, OverflowError):
            expires_at = 0
        terminal_status = str(row["status"] or "")
        if terminal_status in ("failed", "no_match") and not best and not candidates:
            with self._connect() as track_conn:
                track = track_conn.execute(
                    "SELECT id,title,artist,album,path,duration,item_json FROM tracks WHERE id=?",
                    (track_id,),
                ).fetchone()
            # Preserve authoritative local Tag fields when every remote
            # provider returns a terminal no-match/failure.  Falling back to
            # the filename first can hide a valid album/artist/title already
            # read from the file and makes the UI look as if metadata was
            # erased.  The filename candidate remains the final fallback for
            # genuinely untagged files.
            local = (local_track_candidate(track) or filename_track_candidate(track)) if track else None
            if local:
                best = local
                candidates = [local]
        last_error = str(job["last_error"] or "")[:500] if job else ""
        result = {"track_id": track_id, "status": terminal_status, "source": str(row["source"] or ""), "provider_id": str(row["provider_id"] or ""), "confidence": confidence, "fetched_at": fetched_at, "expires_at": expires_at, "best": best, "candidates": candidates, "job_status": str(job["status"] or "") if job else "", "job_attempts": nonnegative_int(job["attempts"]) if job else 0, "last_error": last_error, "retryable": terminal_status in ("failed", "no_match")}
        artwork_id = _provider_text(row["artwork_id"], 128).strip().lower()
        projected_artwork_url = artwork_url(artwork_id)
        if projected_artwork_url:
            result["image_url"] = projected_artwork_url
        return result

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
        track_id = normalize_track_id(track_id)
        if not track_id:
            return False
        now = int(time.time())
        with self._connect() as conn:
            if track_id != self.current_track_id:
                self._demote_track_jobs(conn, self.current_track_id)
                self.current_track_id = track_id
            cached = conn.execute(
                "SELECT lyrics,artwork_id,expires_at FROM metadata_tracks WHERE track_id=? AND orphaned_at=0",
                (track_id,),
            ).fetchone()
            track = conn.execute(
                "SELECT id,path,title,artist,album,album_artist,duration,size,modified_ns,item_json FROM tracks WHERE id=?",
                (track_id,),
            ).fetchone()
            if not track:
                return False
            if not cached or not cached["lyrics"] or bounded_epoch(cached["expires_at"]) <= now:
                self._upsert_job(conn, "lyrics:" + track_id, "lyrics", track_id, dict(track), 0, True)
            # A fully tagged recording can still be missing artwork.  The
            # previous gate only considered title/artist/album provenance, so
            # playback never entered the broad candidate chain for coverless
            # files and the UI kept showing the fallback music glyph.  Treat
            # an absent cached/local artwork reference as an explicit current
            # track request while keeping whole-library crawling unchanged.
            cached_artwork_id = _provider_text(cached["artwork_id"] if cached else "", 128).strip().lower()
            has_cached_artwork = valid_artwork_id(cached_artwork_id)
            if self._needs_track_enrichment(track) or (not has_local_artwork(track) and not has_cached_artwork):
                self._upsert_job(conn, "track:" + track_id, "track", track_id, dict(track), 1, True)
            album = str(track["album"] or "").strip()
            if album:
                album_artist = track["album_artist"] or track["artist"] or ""
                album_key = entity_key("album", album, album_artist)
                album_cached = conn.execute(
                    "SELECT artwork_id,expires_at FROM metadata_entities WHERE entity_type='album' AND entity_key=? AND orphaned_at=0",
                    (album_key,),
                ).fetchone()
                album_force = not album_cached or not album_cached["artwork_id"] or bounded_epoch(album_cached["expires_at"]) <= now
                self._reconcile_entity(conn, "album", album, album_artist, 1, album_force, [])
            self._queue_tag_write(conn, track_id)
        self.fetch_wake_event.set()
        self.tag_wake_event.set()
        self.priority_wake_event.set()
        return True

    def _queue_tag_write(self, conn, track_id):
        # One low-priority job per track coalesces separately discovered cover
        # and lyric data, so the original file is not repeatedly rewritten.
        # Non-current tracks get a short debounce window: album artwork and
        # lyrics frequently arrive a few seconds apart during a full scan.
        if not self.config.get("metadata_tag_write_enabled", False):
            return False
        priority = 2 if str(track_id) == self.current_track_id else 200
        self._upsert_job(conn, "tag:" + track_id, "tag_write", track_id, {}, priority)
        self.tag_wake_event.set()
        # A fetch worker can discover artwork/lyrics after the dedicated tag
        # writer has died. Recover that already-started lane at the enqueue
        # boundary instead of leaving the durable job for a later health poll.
        if self.tag_thread is not None and not self.tag_thread.is_alive():
            if self._ensure_tag_worker():
                self.worker_restarts = min(
                    1000000, nonnegative_int(self.worker_restarts, maximum=1000000) + 1
                )
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
        if not str(album or "").strip():
            # A provider can hand back cover art for an album whose name is still
            # empty. ``WHERE album=''`` then matches every untagged track in the
            # library, and each hit pays a queue-count scan plus a durable tag
            # rewrite, so one malformed entity can stall the writer for minutes.
            return
        rows = conn.execute(
            "SELECT id FROM tracks WHERE album=? ORDER BY id LIMIT ?",
            (album, MAX_ALBUM_TAG_WRITE_TRACKS),
        )
        for row in rows:
            self._queue_tag_write(conn, str(row["id"]))

    def _backfill_album_tag_writes(self, conn):
        """Queue tag rewrites for cached album artwork without a full album list."""
        last_key = ""
        while True:
            albums = conn.execute(
                """SELECT entity_key,name,artist FROM metadata_entities
                   WHERE entity_type='album' AND artwork_id<>'' AND orphaned_at=0 AND entity_key>?
                   ORDER BY entity_key LIMIT ?""",
                (last_key, TAG_WRITE_BACKFILL_BATCH_SIZE),
            ).fetchall()
            if not albums:
                return
            next_key = str(albums[-1]["entity_key"] or "")
            if next_key <= last_key:
                # Keyset pagination only terminates while the cursor strictly
                # advances. A legacy row whose stored key sorts differently from
                # its text form would re-read the same batch forever, and this
                # loop runs on the connection warm-up path.
                return
            last_key = next_key
            for album in albums:
                self._queue_album_tag_writes(conn, str(album["name"] or ""), str(album["artist"] or ""))

    def _tag_data(self, track_id):
        with self._connect() as conn:
            track = conn.execute(
                "SELECT id,path,title,artist,album,album_artist,composer,genre,track_no,is_dsd,cue_track,item_json FROM tracks WHERE id=?",
                (track_id,),
            ).fetchone()
            if not track:
                return None
            data = dict(track)
            item_payload = decode_item_payload(data.get("item_json")) or {}
            metadata_source = item_payload.get("metadata_source")
            metadata_source = metadata_source if isinstance(metadata_source, dict) else {}
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
            artwork_path = self._safe_artwork_path(artwork["path"] if artwork else "")
            if artwork and artwork_path:
                data["artwork_path"] = artwork_path
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
                artwork_path = self._safe_artwork_path(track_artwork["path"] if track_artwork else "")
                if track_artwork and artwork_path:
                    data["artwork_path"] = artwork_path
                    data["artwork_mime"] = track_artwork["mime"]
            return data

    def _note_self_write(self, source):
        """Tell the library scanner that this revision came from us.

        The tag writer rewrites the user's own files on a 250 ms timer.  Those
        rewrites bump ``st_mtime_ns``, which used to make the library signature
        change on every pass, so the whole collection rescanned forever and the
        server never had spare CPU for interactive folder requests.  Recording
        the revision we just produced lets the scanner collapse it.
        """
        if not source:
            return False
        try:
            return library_self_write.record_from_stat(source, os.stat(source))
        except OSError:
            return False

    def _write_track_tags(self, track_id):
        # Final mutation boundary for worker and direct-call paths.
        if not self.config.get("metadata_tag_write_enabled", False):
            return "skipped"
        data = self._tag_data(track_id)
        if not data:
            return False
        source = str(data.get("path") or "")
        extension = os.path.splitext(source)[1].lower()
        if (extension not in TAG_WRITABLE_EXTENSIONS
                or not os.path.isfile(source) or (not data.get("lyrics") and not data.get("artwork_path") and not data.get("has_track_match"))):
            return True
        source_revision = _file_revision(source)
        if source_revision is None:
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
                desired = _read_artwork_file(artwork_path)
                if (existing and desired and hashlib.sha256(existing).digest() == hashlib.sha256(desired).digest()
                        and not data.get("has_track_match") and not data.get("lyrics")):
                    return "skipped"
            except OSError:
                pass
        if extension in (".mp3", ".flac") and not data.get("artwork_path") and self._write_track_tags_native(source, extension, data):
            self._note_self_write(source)
            self.tag_written = saturating_counter(self.tag_written)
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
            if _file_revision(source) != source_revision:
                raise RuntimeError("source changed during metadata write")
            preserve_owner_and_mode(source, temporary)
            os.replace(temporary, source)
            self._note_self_write(source)
            self.tag_written = saturating_counter(self.tag_written)
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
        with tempfile.TemporaryFile(mode="w+b") as errors:
            result = _run_media_process(
                command + [temporary], stdout=subprocess.DEVNULL, stderr=errors,
                timeout=180, env=env, output_limit=MAX_TAG_WRITE_STDERR_BYTES,
            )
            if result.returncode != 0 or not os.path.isfile(temporary) or os.path.getsize(temporary) <= 0:
                errors.seek(0, os.SEEK_END)
                size = errors.tell()
                errors.seek(max(0, size - MAX_TAG_WRITE_STDERR_BYTES))
                detail = errors.read(MAX_TAG_WRITE_STDERR_BYTES).decode("utf-8", "ignore")[-300:]
                # Preserve the result-mock seam while never collecting real
                # process stderr in memory without a file-size bound.
                if not detail and isinstance(getattr(result, "stderr", None), (bytes, bytearray)):
                    detail = bytes(result.stderr)[-300:].decode("utf-8", "ignore")
                raise RuntimeError("tag write failed: %s" % detail)
        return temporary

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
        # Provider payloads are untrusted; reject arbitrary objects instead
        # of invoking an expensive or failing __str__ implementation.
        if not isinstance(url, str):
            return ""
        url = url.strip()
        if url.startswith("//"):
            url = "https:" + url
        if not url or len(url) > MAX_ARTWORK_URL_LENGTH:
            return ""
        url = public_metadata_http_url(url, MAX_ARTWORK_URL_LENGTH)
        if not url:
            return ""
        with self._connect() as conn:
            cached = conn.execute("SELECT id,path FROM metadata_assets WHERE source_url=? ORDER BY fetched_at DESC LIMIT 1", (url,)).fetchone()
            cached_id = str(cached["id"] or "").strip().lower() if cached else ""
            # Older caches may contain hand-edited or partially migrated ids.
            # Do not return them as if they were content-addressed assets;
            # the caller can safely redownload and repair the cache instead.
            cached_path = self._safe_artwork_path(cached["path"] if cached else "")
            if cached and valid_artwork_id(cached_id) and cached_path:
                opened = open_bounded_artwork(cached_path, MAX_ARTWORK_BYTES)
                if opened:
                    opened[0].close()
                    # A source-url hit is only reusable when the file still
                    # satisfies the same bound as a newly downloaded asset.
                    # Otherwise a stale/inflated cache row can short-circuit
                    # recovery and keep returning an unusable artwork id.
                    return cached_id
        request = urllib.request.Request(url, headers={"User-Agent": APP_USER_AGENT, "Referer": "https://music.163.com/" if source == "netease" else ""})
        artwork_timeout = provider_timeout(
            getattr(self.providers._failure_local, "deadline", None),
            time.monotonic(),
            15,
        )
        if artwork_timeout <= 0:
            raise TimeoutError("metadata artwork time budget exhausted")
        with _open_metadata_url(request, artwork_timeout) as response:
            mime = str(response.headers.get_content_type() or "")
            declared_length = response.headers.get("Content-Length")
            declared_size = None
            if isinstance(declared_length, str):
                declared_length = declared_length.strip()
                if len(declared_length) <= 20 and declared_length.isdecimal():
                    declared_size = int(declared_length)
                    if declared_size > MAX_ARTWORK_BYTES:
                        return ""
            body = _read_response_limited(response, MAX_ARTWORK_BYTES)
        if declared_size is not None and len(body) != declared_size:
            return ""
        if len(body) > MAX_ARTWORK_BYTES or not body:
            return ""
        # Provider headers are untrusted text, and this value is stored, then
        # replayed as the Content-Type of a metadata artwork response. The
        # pixels decide, and a type outside the raster allowlist (SVG among
        # them) means no asset rather than a scriptable document on this origin.
        mime = safe_image_media_type(mime, body)
        if not mime:
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
            current = conn.execute("SELECT COALESCE(SUM(size),0) FROM metadata_assets").fetchone()[0]
            maximum = bounded_int(
                self.config, "metadata_cache_max_bytes", 512 * 1024 * 1024,
                16 * 1024 * 1024, 8 * 1024 * 1024 * 1024,
            )
            if int(current or 0) + len(body) > maximum:
                raise ResourceLimitError("metadata artwork cache is full of referenced assets")
        if not disk_has_reserve(self.artwork_dir, minimum_free, len(body)):
            raise ResourceLimitError("metadata cache disk reserve reached")
        path = os.path.join(self.artwork_dir, asset_id + extension)
        if not os.path.isfile(path):
            temporary = ""
            fd = -1
            try:
                fd, temporary = tempfile.mkstemp(
                    prefix=".fnaudio-artwork-",
                    suffix=".tmp",
                    dir=self.artwork_dir,
                )
                with os.fdopen(fd, "wb") as fh:
                    fd = -1
                    fh.write(body)
                    fh.flush()
                    os.fsync(fh.fileno())
                secure_file(temporary)
                os.replace(temporary, path)
                temporary = ""
                secure_file(path)
            finally:
                if fd >= 0:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                if temporary:
                    try:
                        os.unlink(temporary)
                    except OSError:
                        pass
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
        total_row = conn.execute("SELECT COALESCE(SUM(size),0) AS total FROM metadata_assets").fetchone()
        try:
            total = max(0, int(total_row["total"] or 0))
        except (KeyError, TypeError, ValueError, OverflowError):
            total = 0
        removed = 0
        assets = conn.execute(
            """SELECT a.id,a.path,a.size
               FROM metadata_assets a
               WHERE NOT EXISTS (
                   SELECT 1 FROM metadata_entities e
                   WHERE e.artwork_id=a.id AND e.orphaned_at=0
               )
               AND NOT EXISTS (
                   SELECT 1 FROM metadata_tracks t
                   WHERE t.artwork_id=a.id AND t.orphaned_at=0
               )
               ORDER BY a.last_accessed ASC,a.fetched_at ASC"""
        )
        while True:
            batch = assets.fetchmany(ARTWORK_PRUNE_BATCH_SIZE)
            if not batch:
                break
            for asset in batch:
                if total + max(0, int(incoming_bytes)) <= maximum and disk_has_reserve(
                    self.artwork_dir, minimum_free, incoming_bytes
                ):
                    return removed
                path = self._safe_artwork_path(asset["path"])
                try:
                    if path:
                        os.unlink(path)
                except FileNotFoundError:
                    # The database row can outlive a manually removed cache
                    # file. It is already absent from disk, so reclaim the
                    # row and its recorded byte budget just like a deletion.
                    pass
                except OSError:
                    continue
                conn.execute(
                    "UPDATE metadata_entities SET artwork_id='',expires_at=0 WHERE artwork_id=?",
                    (asset["id"],),
                )
                conn.execute(
                    "UPDATE metadata_tracks SET artwork_id='',expires_at=0 WHERE artwork_id=?",
                    (asset["id"],),
                )
                conn.execute("DELETE FROM metadata_assets WHERE id=?", (asset["id"],))
                total = max(0, total - max(0, int(asset["size"] or 0)))
                removed += 1
        return removed

    def _finish_job(self, job_key, status, error, expected_attempts=None):
        where = "job_key=?"
        values = [status, int(time.time()), process_error_text(error, default=""), job_key]
        if expected_attempts is not None:
            where += " AND status='running' AND attempts=?"
            values.append(nonnegative_int(expected_attempts))
        def write():
            with self._connect() as conn:
                conn.execute(
                    "UPDATE metadata_jobs SET status=?,updated_at=?,last_error=? WHERE " + where,
                    values,
                )
        self._run_database_write_with_retry(write)
        self._invalidate_status_cache()

    def _retry_job(self, job_key, attempts, error, expected_attempts=None):
        delay = retry_delay_seconds(max(0, nonnegative_int(attempts) - 1))
        where = "job_key=?"
        values = [int(time.time()) + delay, int(time.time()), process_error_text(error, default=""), job_key]
        if expected_attempts is not None:
            where += " AND status='running' AND attempts=?"
            values.append(nonnegative_int(expected_attempts))
        def write():
            with self._connect() as conn:
                conn.execute(
                    "UPDATE metadata_jobs SET status='retry',next_attempt_at=?,updated_at=?,last_error=? WHERE " + where,
                    values,
                )
        self._run_database_write_with_retry(write)
        self._invalidate_status_cache()

    def _cleanup_orphans(self, conn, now):
        grace_days = bounded_int(self.config, "metadata_orphan_grace_days", 7, 0, 90)
        threshold = now - grace_days * 24 * 60 * 60
        entities = conn.execute(
            "SELECT entity_type,entity_key FROM metadata_entities WHERE orphaned_at>0 AND orphaned_at<=?",
            (threshold,),
        )
        while True:
            batch = entities.fetchmany(ORPHAN_CLEANUP_BATCH_SIZE)
            if not batch:
                break
            for row in batch:
                conn.execute(
                    "DELETE FROM metadata_jobs WHERE job_key=?",
                    ("%s:%s" % (row["entity_type"], row["entity_key"]),),
                )
            conn.executemany(
                "DELETE FROM metadata_entities WHERE entity_type=? AND entity_key=?",
                [(row["entity_type"], row["entity_key"]) for row in batch],
            )
        tracks = conn.execute(
            "SELECT track_id FROM metadata_tracks WHERE orphaned_at>0 AND orphaned_at<=?",
            (threshold,),
        )
        while True:
            batch = tracks.fetchmany(ORPHAN_CLEANUP_BATCH_SIZE)
            if not batch:
                break
            for row in batch:
                conn.execute("DELETE FROM metadata_jobs WHERE job_key=?", ("lyrics:" + row["track_id"],))
                conn.execute("DELETE FROM metadata_jobs WHERE job_key=?", ("tag:" + row["track_id"],))
            conn.executemany(
                "DELETE FROM metadata_tracks WHERE track_id=?",
                [(row["track_id"],) for row in batch],
            )
        conn.execute("DELETE FROM metadata_track_matches WHERE orphaned_at>0 AND orphaned_at<=?", (threshold,))
        while True:
            orphan_assets = conn.execute(
                """SELECT id,path FROM metadata_assets
                   WHERE id NOT IN (
                       SELECT artwork_id FROM metadata_entities WHERE artwork_id<>''
                       UNION
                       SELECT artwork_id FROM metadata_tracks WHERE artwork_id<>''
                   )
                   LIMIT ?""",
                (ORPHAN_CLEANUP_BATCH_SIZE,),
            ).fetchall()
            if not orphan_assets:
                break
            for asset in orphan_assets:
                try:
                    path = self._safe_artwork_path(asset["path"])
                    if path:
                        os.unlink(path)
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
        # Track matches have an independent TTL from lyrics. Without this
        # branch, a stable library signature makes the fast reconcile path
        # renew lyrics/entities but leaves expired title/artist/artwork
        # candidates permanently stuck in a terminal job state.
        conn.execute(
            """UPDATE metadata_jobs SET status='pending',next_attempt_at=0,updated_at=?
               WHERE status<>'running' AND job_key IN (
                 SELECT 'track:' || track_id FROM metadata_track_matches
                 WHERE orphaned_at=0 AND expires_at<=?
               )""",
            (now, now),
        )

    def enrich_groups(self, view, result):
        groups = result.get("groups", []) if isinstance(result, dict) else result
        if not isinstance(groups, list) or view not in ("albums", "artists", "composers"):
            return result
        # Keep this module boundary bounded even when a future caller bypasses
        # the library browse limits. Preserve the response list itself; this
        # only caps metadata projection work and SQL parameter construction.
        groups = groups[:MAX_GROUP_ENRICH_ITEMS]
        kind = {"albums": "album", "artists": "artist", "composers": "composer"}[view]
        keyed_groups = [
            (group, entity_key(kind, group.get("name"), group.get("artist") if kind == "album" else ""))
            for group in groups
        ]
        keys = [key for _, key in keyed_groups if key]
        if not keys:
            return result
        with self._connect() as conn:
            metadata_by_key = {}
            for index in range(0, len(keys), MAX_GROUP_ENRICH_QUERY_ITEMS):
                key_batch = keys[index:index + MAX_GROUP_ENRICH_QUERY_ITEMS]
                placeholders = ",".join("?" for _ in key_batch)
                exact_rows = conn.execute(
                    "SELECT entity_key,artist,release_date,artwork_id,source,confidence FROM metadata_entities WHERE entity_type=? AND entity_key IN (%s) AND orphaned_at=0" % placeholders,
                    [kind] + key_batch,
                )
                metadata_by_key.update({row["entity_key"]: row for row in exact_rows})
            fallback_by_name = {}
            if kind == "album":
                names = sorted({str(group.get("name") or "") for group, _ in keyed_groups if group.get("name")})
                for index in range(0, len(names), MAX_GROUP_ENRICH_QUERY_ITEMS):
                    name_batch = names[index:index + MAX_GROUP_ENRICH_QUERY_ITEMS]
                    name_placeholders = ",".join("?" for _ in name_batch)
                    fallback_rows = conn.execute(
                        "SELECT entity_key,name,artist,release_date,artwork_id,source,confidence FROM metadata_entities WHERE entity_type='album' AND name IN (%s) ORDER BY orphaned_at ASC,confidence DESC" % name_placeholders,
                        name_batch,
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
                group["metadata_confidence"] = finite_confidence(row["confidence"])
                group_artwork_id = _provider_text(row["artwork_id"], 128).strip().lower()
                group_artwork_url = artwork_url(group_artwork_id)
                if group_artwork_url:
                    group["image_url"] = group_artwork_url
        return result

    def enrich_track_page(self, page, include_lyrics=False):
        """Merge cached display metadata into a bounded library page.

        Ordinary song-list pages do not render lyric bodies. Avoid copying
        cached LRC text into every row (and then serializing it) unless a
        caller explicitly requests it for a lyrics-aware projection.
        """
        # Only a strict True requests lyric text; the cache key below separates
        # the two shapes so a compact page can never be reused as a detailed one.
        include_lyrics = include_lyrics is True
        if not isinstance(page, dict) or not isinstance(page.get("items"), (list, tuple)):
            return page
        try:
            page_items = page["items"][:MAX_TRACK_PAGE_ITEMS]
        except (IndexError, KeyError, TypeError, AttributeError):
            page_items = ()
        items = [dict(item) for item in page_items if isinstance(item, dict)]

        def _page_track_id(item):
            try:
                return normalize_track_id(item.get("id"))
            except Exception:
                return ""

        def _page_text(item, field):
            try:
                value = item.get(field)
            except Exception:
                return ""
            return value[:160] if isinstance(value, str) else ""

        # Normalise every row identity once per call. The same page used to run
        # the guard three times per row (id collection, the per-id index, and
        # the merge loop below), so the repeated work scaled with the page while
        # establishing nothing the first pass had not already established.
        track_ids = [_page_track_id(item) for item in items]
        ids = list(dict.fromkeys(track_id for track_id in track_ids if track_id))
        if not ids:
            return page
        # Include a bounded presentation fingerprint so a scan that updates a
        # file's Tag/cover cannot briefly reuse an older projection under the
        # same track ID. Keep the key compact and deterministic.
        item_by_id = {track_id: item for track_id, item in zip(track_ids, items) if track_id}
        # Include the visible projection revision in the key as a second line
        # of defence against a concurrent metadata commit.  The normal write
        # path eagerly clears this cache, but a reader can already be between
        # lookup and commit when that invalidation occurs; revision-keying
        # guarantees it cannot reuse the pre-commit overlay in that window.
        projection_revision = nonnegative_int(
            self.metadata_projection_revision,
            maximum=1000000000,
        )
        cache_key = (include_lyrics, projection_revision, tuple(
            (track_id, tuple(_page_text(item_by_id.get(track_id, {}), field) for field in (
                "title", "artist", "album", "cover_thumbnail_url", "cover_url"
            )))
            for track_id in ids
        ))
        requested_values = ",".join("(?)" for _ in ids)
        cached = self._track_page_cache_get(cache_key)
        if cached is None:
            with self._connect() as conn:
            # Drive the join from the requested IDs, rather than from the
            # lyrics/artwork table. A successful automatic/confirmed track
            # match is stored independently and may exist before a lyrics or
            # cover worker creates metadata_tracks. Starting at that table
            # silently hid resolved album/artist fields from the library until
            # another kind of metadata happened to arrive.
            #
            # Both caches are still read in one bounded SQLite roundtrip.
                lyric_columns = "tracks.lyrics," if include_lyrics else ""
                cache_rows = conn.execute(
                """WITH requested(track_id) AS (VALUES %s)
                   SELECT requested.track_id,%s tracks.artwork_id,
                          matches.fields_json
                   FROM requested
                   LEFT JOIN metadata_tracks AS tracks
                     ON tracks.track_id=requested.track_id
                    AND tracks.orphaned_at=0
                   LEFT JOIN metadata_track_matches AS matches
                     ON matches.track_id=requested.track_id
                    AND matches.orphaned_at=0
                    AND matches.status IN ('auto','confirmed')""" % (requested_values, lyric_columns),
                ids,
            )
                cached = {}
                for row in cache_rows:
                    # Finish the projection here, on the read that already paid
                    # for the row. The cache entry now holds the bounded field
                    # dict and the folded artwork id instead of the raw
                    # `fields_json` text, so a repeated first page no longer
                    # re-decodes and re-bounds every stored match it serves.
                    overlay = {
                        "artwork_id": _overlay_artwork_id(row["artwork_id"] or ""),
                        "projected": project_match_fields(row["fields_json"] or ""),
                    }
                    if include_lyrics:
                        # Ordinary song-list pages never render a lyric body, so
                        # the column is not even selected for them. Reading every
                        # row's cached LRC text and deep-copying it twice per page
                        # made the first-screen overlay cost more than the list it
                        # decorates, on a cache bounded by entry count only.
                        overlay["lyrics"] = _lyrics_document(row["lyrics"])
                    cached[str(row["track_id"])] = overlay
            self._track_page_cache_put(cache_key, cached)
        matches = {}
        for track_id, row in cached.items():
            projected = row.get("projected")
            if projected:
                matches[str(track_id)] = projected
        for index, item in enumerate(items):
            track_id = track_ids[index]
            source = item.get("metadata_source") if isinstance(item.get("metadata_source"), dict) else {}
            for field in TRACK_METADATA_FIELDS:
                value = (matches.get(track_id) or {}).get(field) or ""
                current = item.get(field) if isinstance(item.get(field), str) else ""
                source_value = source.get(field) if isinstance(source.get(field), str) else "unknown"
                if value and (not current.strip() or source_value != "tag"):
                    item[field] = value
            row = cached.get(track_id)
            if include_lyrics and row and row.get("lyrics") and not item.get("lyrics"):
                item["lyrics"] = str(row["lyrics"])
            # `_overlay_artwork_id` already bounded and case-folded this value
            # when its row was read, so the merge loop stays a plain lookup.
            row_artwork_id = row.get("artwork_id") if row else ""
            if valid_artwork_id(row_artwork_id) and not item.get("metadata_artwork_id"):
                item["metadata_artwork_id"] = row_artwork_id
        result = dict(page)
        result["items"] = items
        return result

    def lyrics(self, track_id, retry_failed=False):
        track_id = normalize_track_id(track_id)
        if not track_id:
            return {"lyrics": "", "source": "", "pending": False, "status": "invalid"}
        if retry_failed:
            self.providers.reset_provider_cooldowns()
        now = int(time.time())
        with self._connect() as conn:
            row = conn.execute(
                """SELECT metadata_tracks.lyrics,metadata_tracks.lyrics_source,metadata_tracks.artwork_id,
                          metadata_tracks.expires_at,tracks.album,tracks.album_artist,tracks.artist
                   FROM metadata_tracks
                   LEFT JOIN tracks ON tracks.id=metadata_tracks.track_id
                   WHERE metadata_tracks.track_id=? AND metadata_tracks.orphaned_at=0""",
                (track_id,),
            ).fetchone()
            # Artwork and lyrics are filled by separate workers.  An
            # artwork-only row is not a complete lyrics cache entry: returning
            # it as a successful empty result would permanently suppress the
            # priority lyrics job until expiry.  Only a non-empty lyric body
            # can satisfy this fast path.
            if row and cached_lyrics_is_fresh(row, now):
                cached_artwork_id = _provider_text(row["artwork_id"], 128).strip().lower()
                if not valid_artwork_id(cached_artwork_id):
                    cached_artwork_id = self._cached_album_artwork_id(
                        conn, row["album"], row["album_artist"], row["artist"],
                    )
                return {
                    "lyrics": _lyrics_document(row["lyrics"]),
                    "source": row["lyrics_source"] or "",
                    "image_url": artwork_url(cached_artwork_id),
                    "pending": False,
                }
            track = conn.execute("SELECT id,path,title,artist,album,album_artist,duration,size,modified_ns,item_json FROM tracks WHERE id=?", (track_id,)).fetchone()
            if not track:
                return None
            cached_artwork_id = _provider_text(row["artwork_id"] if row else "", 128).strip().lower()
            if not valid_artwork_id(cached_artwork_id):
                cached_artwork_id = ""
            if not cached_artwork_id:
                cached_artwork_id = self._cached_album_artwork_id(
                    conn, track["album"], track["album_artist"], track["artist"],
                )
            # Embedded/sidecar lyrics are authoritative local metadata and can
            # be returned without waiting for a provider worker.  This keeps
            # the lyrics view responsive even when background enrichment is
            # disabled or an external provider is temporarily unavailable.
            local = self._read_local_lyrics_cached(
                str(track["path"] or ""),
                (track["modified_ns"], track["size"]),
            )
            if local:
                # Local lyrics satisfy the fast path, but must not short-circuit
                # artwork/album enrichment for a coverless track.  Lyrics
                # pages are an explicit metadata request even when the LRC is
                # embedded, so queue the bounded track lane before returning.
                if (not self._metadata_writes_paused()
                        and (self._needs_track_enrichment(track) or (not has_local_artwork(track) and not cached_artwork_id))):
                    self._upsert_job(conn, "track:" + track_id, "track", track_id, dict(track), 1, True)
                    self.fetch_wake_event.set()
                    if self.fetch_threads or self.priority_thread or self.tag_thread:
                        self.ensure_workers("fetch")
                return {
                    "lyrics": local,
                    "source": "本地歌词",
                    "image_url": artwork_url(cached_artwork_id),
                    "pending": False,
                    "status": "local",
                }
            job = conn.execute(
                "SELECT status,attempts,last_error,updated_at FROM metadata_jobs WHERE job_key=?",
                ("lyrics:" + str(track_id),),
            ).fetchone()
            writes_paused = self._metadata_writes_paused()
            if (not writes_paused and job and str(job["status"] or "") in ("failed", "no_match")
                    and not retry_failed and should_auto_retry_failed(job["status"], job["updated_at"], now)):
                conn.execute(
                    "UPDATE metadata_jobs SET status='pending',attempts=0,next_attempt_at=0,updated_at=?,last_error='' WHERE job_key=? AND status IN ('failed','no_match')",
                    (now, "lyrics:" + str(track_id)),
                )
                self._invalidate_status_cache()
                if self.fetch_threads or self.priority_thread or self.tag_thread:
                    self.ensure_workers("lyrics")
                job = None
            if job and str(job["status"] or "") in ("failed", "no_match") and not writes_paused:
                # The automatic poll has a bounded retry budget, but an
                # explicit user retry must be able to recover after a provider
                # outage or a corrected metadata query. Do not turn ordinary
                # polling into an infinite retry loop: callers must opt in.
                if not retry_failed:
                    return {
                        "lyrics": "",
                        "source": "",
                        "pending": False,
                        "status": str(job["status"] or "failed"),
                        "attempts": nonnegative_int(job["attempts"]),
                        "error": str(job["last_error"] or "")[:500],
                        "retryable": True,
                    }
                conn.execute(
                    """UPDATE metadata_jobs
                       SET status='pending',attempts=0,next_attempt_at=0,updated_at=?,last_error=''
                       WHERE job_key=? AND status IN ('failed','no_match')""",
                    (int(time.time()), "lyrics:" + str(track_id)),
                )
                self._invalidate_status_cache()
                if self.fetch_threads or self.priority_thread or self.tag_thread:
                    self.ensure_workers("lyrics")
            # This path is reached by the active player/lyrics view. It must
            # take precedence over the ordinary library reconciliation queue.
            # Repeated lyrics polls are expected while a provider is slow.
            # Preserve the existing pending/running job instead of refreshing
            # its updated_at on every request and perturbing queue fairness.
            existing_lyrics_job = conn.execute(
                "SELECT status FROM metadata_jobs WHERE job_key=?",
                ("lyrics:" + track_id,),
            ).fetchone()
            existing_lyrics_status = str(existing_lyrics_job["status"] or "") if existing_lyrics_job else ""
            if not writes_paused and existing_lyrics_status not in ("pending", "retry", "running"):
                self._upsert_job(conn, "lyrics:" + track_id, "lyrics", track_id, dict(track), 0, True)
                if self.fetch_threads or self.priority_thread or self.tag_thread:
                    self.ensure_workers("lyrics")
            # Opening lyrics is also an explicit request for the song's
            # surrounding metadata. Queue the bounded track candidate lookup
            # when filename/placeholder fields show that the recording is not
            # fully tagged. This remains a single-track priority request even
            # when whole-library metadata crawling is disabled.
            # Opening the lyrics view is also an explicit metadata request.
            # A fully tagged file can still be missing artwork, so enqueue
            # the bounded candidate lookup in that case as well; otherwise
            # the UI remains stuck on the fallback glyph even though the
            # user has just asked for metadata.
            if (not writes_paused
                    and (self._needs_track_enrichment(track) or (not has_local_artwork(track) and not cached_artwork_id))):
                self._upsert_job(conn, "track:" + track_id, "track", track_id, dict(track), 1, True)
                if self.fetch_threads or self.priority_thread or self.tag_thread:
                    self.ensure_workers("fetch")
        self.priority_wake_event.set()
        self.fetch_wake_event.set()
        return {
            "lyrics": "",
            "source": "后台匹配中",
            "image_url": artwork_url(cached_artwork_id),
            "pending": True,
            "status": "scan_busy" if writes_paused else "pending",
        }

    def artwork(self, asset_id):
        if not valid_artwork_id(asset_id):
            return None
        with self._connect() as conn:
            row = conn.execute("SELECT path,mime,size FROM metadata_assets WHERE id=?", (asset_id,)).fetchone()
            if not row:
                return None
            path = self._safe_artwork_path(row["path"])
            opened = open_bounded_artwork(path, MAX_ARTWORK_BYTES) if path else None
            if not opened:
                return None
            handle, actual_size = opened
            try:
                prefix = handle.read(SNIFF_PREFIX_BYTES)
            finally:
                handle.close()
            # The HTTP endpoint streams this file and uses this value for
            # Content-Length. Do not trust a stale/corrupt cache row to expose
            # an oversized asset or advertise an incorrect response length.
            if actual_size <= 0 or actual_size > MAX_ARTWORK_BYTES:
                return None
            # Decide here, before the bookkeeping: `safe_image_media_type` is the same
            # resolution the route performs (bytes win over the stored declaration, and a
            # payload that opens markup is refused whatever the row claims), so this cannot
            # disagree with what the route would have served.
            served_mime = safe_image_media_type(row["mime"], prefix)
            if not served_mime:
                # This row can only ever produce a 404. Renewing `last_accessed` on every hit
                # would keep pushing it to the back of the eviction queue
                # (`ORDER BY last_accessed ASC` below in the pruning pass), so a cache full of
                # assets no browser can display would be the last thing to be reclaimed.
                return None
            stored_size = row["size"]
            if not isinstance(stored_size, int) or stored_size != actual_size:
                conn.execute("UPDATE metadata_assets SET size=? WHERE id=?", (actual_size, asset_id))
            conn.execute("UPDATE metadata_assets SET last_accessed=? WHERE id=?", (int(time.time()), asset_id))
            result = dict(row)
            result["size"] = actual_size
            # Hand back the type that was resolved from the bytes, not the one a provider
            # header once claimed. The row itself is left alone: rewriting history is the
            # business of a migration, and the next store over writes a truthful value.
            result["mime"] = served_mime
            return result

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
            artwork_id = _provider_text(row["artwork_id"], 128).strip().lower()
            return {
                "artist": row["artist"] or "",
                "release_date": normalize_release_date(row["release_date"]),
                "image_url": artwork_url(artwork_id),
                "source": row["source"] or "",
                "confidence": finite_confidence(row["confidence"]),
                "expires_at": bounded_epoch(row["expires_at"]),
            }

    def status(self):
        # Health/diagnostic polling is also an interactive recovery signal.
        # Only revive a pool that had previously been started; an object that
        # has never started must remain inert until application startup calls
        # ``start()`` explicitly.
        if self.fetch_threads or self.priority_thread or self.tag_thread:
            try:
                self.ensure_workers("fetch")
            except Exception:
                pass
        fetch_worker_limit = bounded_int(self.config, "metadata_fetch_workers", 3, 1, 6)
        fetch_workers_active = sum(1 for worker in self.fetch_threads if worker.is_alive())
        priority_worker_running = bool(self.priority_thread and self.priority_thread.is_alive())
        tag_writer_running = bool(
            self.config.get("metadata_tag_write_enabled", False)
            and self.tag_thread and self.tag_thread.is_alive()
        )
        # One caller performs the SQLite aggregation while a small burst of
        # health/diagnostic callers waits for the same snapshot. Never hold
        # the status lock while opening SQLite: job writers can safely
        # invalidate from inside their own transactions.
        while True:
            with self._status_cache_lock:
                now = time.monotonic()
                if self._status_snapshot is not None and now - self._status_snapshot_at < STATUS_CACHE_TTL_SECONDS:
                    database = copy.deepcopy(self._status_snapshot)
                    cache_age_seconds = max(0.0, now - self._status_snapshot_at)
                    self._status_cache_hits = saturating_counter(self._status_cache_hits)
                    break
                if self._status_cache_loading:
                    self._status_cache_ready.wait(timeout=1.0)
                    continue
                generation = self._status_cache_generation
                self._status_cache_loading = True
                self._status_cache_misses = saturating_counter(self._status_cache_misses)
            try:
                database = self._status_database_snapshot()
            except Exception as exc:
                # This reader owns the coalesced status slot.  Do not leave
                # `_status_cache_loading` set for non-SQLite failures (for
                # example a transient filesystem error during connection
                # setup), or every later diagnostic request waits forever.
                self.last_error = str(exc)[:500]
                database = {
                    "jobs": {}, "job_types": {}, "artwork_bytes": 0,
                    "entities": 0, "lyrics": 0, "track_matches": {}, "tag_jobs": [],
                }
            with self._status_cache_lock:
                self._status_cache_loading = False
                self._status_cache_ready.notify_all()
                if generation != self._status_cache_generation:
                    # A writer committed while this read was in flight.
                    # Re-read rather than publishing a stale aggregate.
                    continue
                # Store an isolated value. `status()` always deep-copies it
                # again, so callers cannot mutate the next response.
                self._status_snapshot = copy.deepcopy(database)
                self._status_snapshot_at = time.monotonic()
                cache_age_seconds = 0.0
                break
        counts = database["jobs"]
        pending = nonnegative_int(counts.get("pending", 0)) + nonnegative_int(counts.get("retry", 0))
        tag_written = nonnegative_int(self.tag_written)
        try:
            tag_seconds = max(0.0, float(self.tag_write_seconds))
        except (TypeError, ValueError, OverflowError):
            tag_seconds = 0.0
        return {
            "ok": True,
            "enabled": self.config.get("metadata_enabled", False) if isinstance(self.config.get("metadata_enabled", False), bool) else False,
            "tag_write_enabled": self.config.get("metadata_tag_write_enabled", False) if isinstance(self.config.get("metadata_tag_write_enabled", False), bool) else False,
            "running": bool(fetch_workers_active or tag_writer_running or priority_worker_running),
            "active_job": self._active_job_snapshot(),
            "jobs": counts,
            "job_types": database["job_types"],
            "pending": pending,
            "pending_limit": bounded_int(self.config, "metadata_max_pending_jobs", 20000, 100, 200000),
            "dropped": self.dropped_jobs,
            "saturated": pending >= bounded_int(self.config, "metadata_max_pending_jobs", 20000, 100, 200000),
            "artwork_bytes": database["artwork_bytes"],
            "artwork_limit_bytes": bounded_int(
                self.config, "metadata_cache_max_bytes", 512 * 1024 * 1024, 16 * 1024 * 1024, 8 * 1024 * 1024 * 1024
            ),
            "entities": database["entities"],
            "lyrics": database["lyrics"],
            "track_matches": database["track_matches"],
            "metadata_updated_at": bounded_epoch(database.get("metadata_updated_at")),
            "metadata_projection_revision": nonnegative_int(self.metadata_projection_revision, maximum=1000000000),
            "tag_written": tag_written,
            "fetch_workers": len(self.fetch_threads),
            "fetch_worker_limit": fetch_worker_limit,
            "fetch_workers_active": fetch_workers_active,
            # The priority lyrics worker performs provider I/O independently
            # of the ordinary fetch pool, so expose its extra bounded slot.
            "priority_worker_running": priority_worker_running,
            "network_worker_limit": fetch_worker_limit + 1,
            "network_workers_active": fetch_workers_active + int(priority_worker_running),
            "worker_restarts": nonnegative_int(self.worker_restarts, maximum=1000000),
            "track_page_cache": self._track_page_cache_status(),
            "provider_candidate_cache": self.providers.candidate_cache_snapshot(),
            "tag_writer_running": tag_writer_running,
            "tag_write_average_seconds": round(tag_seconds / tag_written, 3) if tag_written else 0,
            "tag_write_in_progress": bool(self.tag_write_started_at),
            "tag_writer": "mutagen-if-available-otherwise-ffmpeg",
            "fingerprint": fingerprint_capability(self.config),
            "provider_failures": self.providers.failure_snapshot(),
            "provider_activity": self.providers.activity_snapshot(),
            "tag_jobs": database["tag_jobs"],
            "last_tag_write_at": self.last_tag_write_at,
            "last_reconcile": self.last_reconcile,
            "last_error": self.last_error,
            "orphan_grace_days": bounded_int(
                self.config, "metadata_orphan_grace_days", 7, 0, 90,
            ),
            "status_cache": {
                "ttl_ms": int(STATUS_CACHE_TTL_SECONDS * 1000),
                "age_ms": int(cache_age_seconds * 1000),
                "hits": self._status_cache_hits,
                "misses": self._status_cache_misses,
            },
            "local_lyrics_cache": combined_snapshot(
                self.providers._local_lyrics_cache.snapshot(), self._local_lyrics_cache.snapshot(),
            ),
        }


__all__ = [
    "MetadataProviders", "MetadataService", "contains_cjk", "entity_key",
    "normalize_release_date", "normalize_text", "provider_score", "read_local_lyrics",
]

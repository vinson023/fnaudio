"""Pure response projection for a temporarily unavailable metadata worker."""

from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any

try:
    from metadata_query_policy import filename_track_candidate
except Exception:  # pragma: no cover - keeps lightweight import doubles safe
    filename_track_candidate = None

_FIELDS = ("title", "artist", "album", "album_artist", "date", "genre", "track_no", "composer")
_MAX_TEXT = 512
# ``lyrics`` is a document, not a tag.  The embedded/sidecar readers and
# the provider lane both accept up to MAX_PROVIDER_LYRICS_BYTES, and the
# normal /api/lyrics fast path hands the stored body back untouched, so a
# recovery projection must not cut it down to a tag-sized field: the
# client marks a non-pending response terminal ("loaded") and stops
# polling, which would freeze a truncated lyric on screen.
_MAX_LYRICS_CHARS = 2 * 1024 * 1024
# Caller shape (re-audited 2026-09-19 and reproduced end to end): every
# production call site hands these projections the raw row returned by
# ``find_library_item``, never a ``public_library_item`` projection.  A
# row built by the current scanner carries neither ``lyrics`` nor
# ``cover_url``/``cover_thumbnail_url``: ``library_metadata``, ``build_audio_item``,
# ``build_cue_item`` define that closed key set, so these reads stay silent
# for freshly scanned files.  They are still not dead code.
# ``load_library_cache`` accepts the legacy ``library.json`` rows verbatim and
# persists them into ``tracks.item_json`` without a key whitelist, so a cache
# left behind by an older release -- the legacy shape
# ``library_presentation`` still documents -- does reach this module, and
# ``tests.test_library_cache`` pins that whole chain.  A media file with no
# cached row is ``not`` a supplier: the library page handlers never pass
# ``include_lyrics`` to ``metadata_service.enrich_track_page``, which works on
# page copies anyway, so an embedded-lyrics cold-start fallback must keep
# going through the bounded local reader in ``metadata_service`` instead of
# touching media files from a request thread.


def _text(value: Any, limit: int = _MAX_TEXT) -> str:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return ""
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    # ``limit`` only ever comes from the two module constants above, so it
    # is applied directly instead of re-validating on every projection.
    return str(value).strip()[:limit]


def local_pending_projection(track_id: Any, item: Any, message: Any = "") -> dict[str, Any]:
    """Keep bounded local identity while a provider lane recovers."""
    safe_id = _text(track_id)
    best: dict[str, str] = {}
    if isinstance(item, Mapping):
        for field in _FIELDS:
            value = _text(item.get(field))
            if value:
                best[field] = value
        # When Tags are entirely absent, retain a low-confidence filename
        # identity during worker recovery.  This is presentation-only: the
        # candidate is never treated as provider-confirmed or written back.
        if not best and callable(filename_track_candidate):
            try:
                fallback = filename_track_candidate(item)
            except Exception:
                fallback = None
            if isinstance(fallback, Mapping):
                for field in _FIELDS:
                    value = _text(fallback.get(field))
                    if value:
                        best[field] = value
    result: dict[str, Any] = {
        "ok": True,
        "track_id": safe_id,
        "status": "pending",
        "pending": True,
        "retryable": True,
        "metadata_unavailable": True,
        "best": best,
        "candidates": [best] if best else [],
    }
    # Even when tags are empty, an embedded/sidecar cover is still useful
    # during the worker recovery window.  Keep it presentation-only and
    # bounded; provider retry semantics remain unchanged.
    if isinstance(item, Mapping):
        artwork = _text(item.get("cover_url") or item.get("cover_thumbnail_url"))
        if artwork:
            result["image_url"] = artwork
        lyrics = _text(item.get("lyrics"), _MAX_LYRICS_CHARS)
        if lyrics:
            result["lyrics"] = lyrics
    detail = _text(message)
    if detail:
        result["message"] = detail
    return result


def local_cached_projection(track_id: Any, item: Any) -> dict[str, Any]:
    """Expose local tags when the metadata service is not initialized yet.

    Startup races should not make the UI report that metadata is unavailable
    when the library already contains authoritative local tags.  This
    presentation-only response never claims a provider match and therefore
    cannot trigger tag write-back.
    """
    safe_id = _text(track_id)
    best: dict[str, str] = {}
    if isinstance(item, Mapping):
        for field in _FIELDS:
            value = _text(item.get(field))
            if value:
                best[field] = value
    result: dict[str, Any] = {
        "ok": True,
        "track_id": safe_id,
        "status": "local",
        "pending": False,
        "source": "本地标签",
        "best": best,
        "candidates": [best] if best else [],
    }
    artwork = _text(item.get("cover_url") or item.get("cover_thumbnail_url")) if isinstance(item, Mapping) else ""
    if artwork:
        result["image_url"] = artwork
    lyrics = _text(item.get("lyrics"), _MAX_LYRICS_CHARS) if isinstance(item, Mapping) else ""
    if lyrics:
        result["lyrics"] = lyrics
    return result


def lyrics_pending_projection(message: Any = "") -> dict[str, Any]:
    """Return the bounded, retryable response for a recovering lyric lane."""
    result: dict[str, Any] = {
        "lyrics": "",
        "source": "",
        "pending": True,
        "retryable": True,
        "metadata_unavailable": True,
        "status": "pending",
    }
    detail = _text(message)
    if detail:
        result["error"] = detail
    return result


def merge_pending_projection(pending: Any, local: Any) -> dict[str, Any]:
    """Merge local presentation fields into a retryable pending response.

    The provider status remains authoritative, while local tags/artwork/lyrics
    keep the UI useful during worker recovery.  Inputs are copied and only
    bounded mapping fields from :func:`local_cached_projection` are used.
    """
    result = dict(pending) if isinstance(pending, Mapping) else {}
    local_map = local if isinstance(local, Mapping) else {}
    existing_best = result.get("best") if isinstance(result.get("best"), Mapping) else {}
    local_best = local_map.get("best") if isinstance(local_map.get("best"), Mapping) else {}
    result["best"] = {**dict(local_best), **dict(existing_best)}
    candidates = result.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        if result["best"]:
            result["candidates"] = [dict(result["best"])]
    for field in ("image_url", "lyrics"):
        if not result.get(field) and local_map.get(field):
            result[field] = local_map[field]
    return result


def local_lyrics_projection(item: Any) -> dict[str, Any] | None:
    """Return embedded lyrics during metadata-service startup."""
    if not isinstance(item, Mapping):
        return None
    lyrics = _text(item.get("lyrics"), _MAX_LYRICS_CHARS)
    if not lyrics:
        return None
    result: dict[str, Any] = {
        "ok": True,
        "lyrics": lyrics,
        "source": "本地歌词",
        "pending": False,
        "status": "local",
    }
    artwork = _text(item.get("cover_url") or item.get("cover_thumbnail_url"))
    if artwork:
        result["image_url"] = artwork
    return result


__all__ = ["local_cached_projection", "local_lyrics_projection", "local_pending_projection", "lyrics_pending_projection", "merge_pending_projection"]

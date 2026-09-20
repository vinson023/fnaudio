from __future__ import annotations

import re
import unicodedata

from metadata_han_variant import fold_han_variants

_PLACEHOLDER_NAMES = frozenset({
    "", "未分类", "未知专辑", "未知歌手", "未知艺术家", "未知作曲者",
    "unknown album", "unknown artist", "unknown composer",
})
MAX_NORMALIZED_TEXT = 4096


def normalize_text(value):
    # Provider payloads are untrusted. A custom object may implement an
    # expensive or failing __str__, and non-text values cannot be a useful
    # title/artist match anyway.
    if not isinstance(value, str):
        return ""
    # Keep matching and entity-cache keys bounded independently of the HTTP
    # request limit. Provider payloads and locally stored tags can reach this
    # function without passing through the query parser.
    text = unicodedata.normalize("NFKC", value[:MAX_NORMALIZED_TEXT]).strip().casefold()
    text = text[:MAX_NORMALIZED_TEXT]
    text = re.sub(r"[^0-9a-z\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]+", "", text)
    # Providers commonly return a Traditional-Chinese release title while the
    # local Tag is Simplified Chinese (or the reverse). Fold only the lookup
    # key, never persisted metadata, so the existing confidence thresholds
    # still protect automatic writeback from unrelated results.
    return fold_han_variants(text)


def provider_score(candidate_name, wanted_name, candidate_artist="", wanted_artist=""):
    name = normalize_text(candidate_name)
    wanted = normalize_text(wanted_name)
    if not name or not wanted:
        return 0.0
    artist = normalize_text(candidate_artist)
    wanted_artist_text = wanted_artist if isinstance(wanted_artist, str) else ""
    wanted_artist_text = wanted_artist_text.strip()
    if wanted_artist_text.casefold() in _PLACEHOLDER_NAMES:
        wanted_artist_text = ""
    wanted_artist_key = normalize_text(wanted_artist_text)
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


__all__ = ["MAX_NORMALIZED_TEXT", "normalize_text", "provider_score"]

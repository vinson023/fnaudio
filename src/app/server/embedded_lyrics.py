"""Pure projection of embedded lyrics from ffprobe-style payloads."""


def extract_embedded_lyrics(payload):
    if not isinstance(payload, dict):
        return ""
    try:
        format_tags = (payload.get("format") or {}).get("tags") or {}
    except (AttributeError, TypeError):
        format_tags = {}
    try:
        tags = dict(format_tags)
    except (TypeError, ValueError):
        tags = {}
    try:
        streams = payload.get("streams") or []
        for stream in streams:
            if isinstance(stream, dict):
                stream_tags = stream.get("tags") or {}
                if isinstance(stream_tags, dict):
                    tags.update(stream_tags)
    except (TypeError, AttributeError, ValueError):
        pass
    for key, value in tags.items():
        if not isinstance(key, str):
            continue
        normalized = key.casefold().replace("-", "_")
        if normalized in ("lyrics", "lyric", "unsyncedlyrics", "syncedlyrics", "uslt", "©lyr") or normalized.startswith("lyrics_"):
            if isinstance(value, str):
                text = value.strip()
                if text:
                    return text
    return ""

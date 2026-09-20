"""Pure normalization of ffprobe JSON payloads."""

from __future__ import annotations

from itertools import islice

from metadata_text import normalize_probe_tags
from scan_numeric_policy import safe_float as _safe_float, safe_int as _safe_int

MAX_PROBE_STREAMS = 16
MAX_PROBE_TAGS = 128
MAX_PROBE_TAG_KEY = 256


def normalize_probe_payload(data):
    """Return normalized tags and stream facts from an ffprobe JSON object."""
    if not isinstance(data, dict):
        data = {}
    raw_tags = {}
    format_data = data.get("format") if isinstance(data.get("format"), dict) else {}
    format_tags = format_data.get("tags") if isinstance(format_data.get("tags"), dict) else {}
    for key, value in islice(format_tags.items(), MAX_PROBE_TAGS):
        if isinstance(key, str) and len(key) <= MAX_PROBE_TAG_KEY:
            raw_tags[key] = value
    streams = data.get("streams") if isinstance(data.get("streams"), list) else []
    streams = streams[:MAX_PROBE_STREAMS]
    for stream in streams:
        if isinstance(stream, dict) and isinstance(stream.get("tags"), dict):
            for key, value in islice(stream["tags"].items(), MAX_PROBE_TAGS):
                if isinstance(key, str) and len(key) <= MAX_PROBE_TAG_KEY:
                    raw_tags[key] = value
    stream = streams[0] if streams and isinstance(streams[0], dict) else {}
    audio_info = {
        "sample_rate": _safe_int(stream.get("sample_rate")),
        "bit_depth": _safe_int(stream.get("bits_per_raw_sample") or stream.get("bits_per_sample")),
        "bit_rate": _safe_int(stream.get("bit_rate")),
        "duration": _safe_float(format_data.get("duration")),
    }
    return normalize_probe_tags(raw_tags), audio_info

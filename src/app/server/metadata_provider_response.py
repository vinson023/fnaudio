"""Bounded decoding helpers shared by metadata provider adapters."""

import base64
import binascii
import json
import re
import zlib


MAX_PROVIDER_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_PROVIDER_LYRICS_BYTES = 2 * 1024 * 1024
# base64 always expands three bytes into four characters, so this is the longest
# encoded lyric field that can still fit the document budget above.
MAX_PROVIDER_LYRICS_BASE64_CHARS = (MAX_PROVIDER_LYRICS_BYTES + 2) // 3 * 4
# The six characters C/Python treat as ordinary whitespace.  ASCII only on purpose:
# ``str.isspace()`` also covers U+0085 and the NBSP family, and silently deleting
# those would turn a rejected payload into an accepted one.
_BASE64_WHITESPACE = str.maketrans(dict.fromkeys(" \t\n\r\v\f"))


def _safe_limit(value, fallback):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return fallback
    return min(fallback, value)


def read_response_limited(response, limit):
    limit = _safe_limit(limit, MAX_PROVIDER_RESPONSE_BYTES)
    payload = bytearray()
    while len(payload) <= limit:
        chunk = response.read(limit - len(payload) + 1)
        if not isinstance(chunk, (bytes, bytearray)):
            raise ValueError("metadata provider response exceeds limit")
        if not chunk:
            break
        payload.extend(chunk)
        if len(payload) > limit:
            raise ValueError("metadata provider response exceeds limit")
    return bytes(payload)


def decompress_gzip_limited(payload, limit):
    """Decompress gzip incrementally without exceeding the output budget."""
    if not isinstance(payload, (bytes, bytearray)):
        raise ValueError("metadata provider gzip payload is invalid")
    limit = _safe_limit(limit, MAX_PROVIDER_RESPONSE_BYTES)
    try:
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        output = bytearray()
        raw = bytes(payload)
        for offset in range(0, len(raw), 65536):
            output.extend(decoder.decompress(raw[offset:offset + 65536], max(0, limit + 1 - len(output))))
            if len(output) > limit:
                raise ValueError("metadata provider decompressed response exceeds limit")
        output.extend(decoder.flush(max(0, limit + 1 - len(output))))
    except (zlib.error, OverflowError) as exc:
        raise ValueError("metadata provider gzip payload is invalid") from exc
    if len(output) > limit or not decoder.eof:
        raise ValueError("metadata provider decompressed response exceeds limit")
    return bytes(output)


def decode_provider_json(payload, content_type=""):
    """Decode provider JSON/JSONP without silently corrupting text."""
    raw = bytes(payload or b"")
    declared = ""
    content_type = content_type if isinstance(content_type, str) else ""
    match = re.search(r"charset\s*=\s*([\w.-]+)", content_type, re.I)
    if match:
        declared = match.group(1).strip().lower()
    preferred = ("utf-8-sig", "utf-8", "gb18030", "big5")
    permissive_declared = {"iso-8859-1", "latin-1", "latin1", "ascii", "us-ascii"}
    encodings = list(preferred)
    if declared and declared not in permissive_declared:
        encodings.insert(0, declared)
    elif declared:
        encodings.append(declared)
    seen = set()
    for encoding in encodings:
        if encoding in seen:
            continue
        seen.add(encoding)
        try:
            text = raw.decode(encoding)
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                wrapped = text.strip()
                match = re.fullmatch(r"[A-Za-z_$][\w$\.]{0,63}\s*\(\s*(\{.*\}|\[.*\])\s*\)\s*;?", wrapped, re.S)
                if match:
                    return json.loads(match.group(1))
                raise
        except (LookupError, UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise ValueError("metadata provider response is not valid JSON")


def decode_lyrics_text(payload, limit=MAX_PROVIDER_LYRICS_BYTES):
    """Decode bounded lyric bytes while rejecting replacement text."""
    if not isinstance(payload, (bytes, bytearray)):
        raise ValueError("lyrics payload is not binary")
    limit = _safe_limit(limit, MAX_PROVIDER_LYRICS_BYTES)
    raw = bytes(payload)
    if len(raw) > limit:
        raise ValueError("lyrics payload exceeds limit")
    has_utf16_bom = raw.startswith((b"\xff\xfe", b"\xfe\xff"))
    encodings = (("utf-16",) if has_utf16_bom else ()) + ("utf-8-sig", "gb18030", "big5")
    saw_replacement = False
    for encoding in encodings:
        try:
            text = raw.decode(encoding).strip()
            if "\ufffd" in text:
                saw_replacement = True
                continue
            return text
        except (UnicodeDecodeError, ValueError):
            continue
    if saw_replacement:
        raise ValueError("lyrics payload contains replacement text")
    raise ValueError("lyrics payload is not valid text")


def decode_base64_lyrics(value, limit=MAX_PROVIDER_LYRICS_BYTES):
    """Decode a provider base64 lyric field inside the document budget.

    The budget is checked on the *encoded* text, before anything is decoded,
    for two reasons. Decoding first allocates the oversized copy that is about
    to be refused anyway. And a caller that pre-slices an over-long field to
    stay inside the budget is worse than refusing it: the slice still decodes,
    into a shortened document whose tail is a multi-byte character split in half,
    and GB18030 turns that into replacement-free mojibake which would then be
    stored as this track's lyrics for good.
    """
    if not isinstance(value, str):
        return ""
    # MIME folding writes a CRLF every 76 characters, and ``validate=True`` refuses
    # line breaks inside the payload, so a folded field used to lose the lyric over
    # formatting that carries no information.  Deleting the six ASCII whitespace
    # characters costs one O(n) copy, and the budget below runs on the normalized
    # text, so folding cannot smuggle extra payload past the ceiling either.
    encoded = value.translate(_BASE64_WHITESPACE)
    if not encoded:
        return ""
    limit = _safe_limit(limit, MAX_PROVIDER_LYRICS_BYTES)
    if len(encoded) > (limit + 2) // 3 * 4:
        raise ValueError("lyrics base64 payload exceeds limit")
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("lyrics base64 payload is invalid") from exc
    return decode_lyrics_text(decoded, limit)


def lyrics_document(value, limit=MAX_PROVIDER_LYRICS_BYTES):
    """Return a stored lyric document, or nothing when it cannot fit.

    Lyrics are document text, so they are accepted whole or refused.  A slice
    would silently rewrite the song, and a slice cannot even enforce the budget
    it is handed: this is a *byte* budget, and one CJK character costs three.
    Every writer and every projection of ``metadata_tracks.lyrics`` goes through
    this one bound, so no endpoint can serve a document another endpoint
    refused.
    """
    if not isinstance(value, str):
        return ""
    text = value.replace("\x00", "").strip()
    if not text:
        return ""
    bounded = _safe_limit(limit, MAX_PROVIDER_LYRICS_BYTES)
    if len(text) > bounded:
        # Provably too big: UTF-8 never costs fewer bytes than characters, so
        # this early-out cannot change the answer.  It is kept because it is the
        # only thing standing between a giant stored row and a second full
        # copy of it inside ``encode``.
        return ""
    return text if len(text.encode("utf-8")) <= bounded else ""


__all__ = [
    "MAX_PROVIDER_RESPONSE_BYTES", "MAX_PROVIDER_LYRICS_BYTES",
    "MAX_PROVIDER_LYRICS_BASE64_CHARS",
    "read_response_limited", "decompress_gzip_limited", "decode_provider_json",
    "decode_lyrics_text", "decode_base64_lyrics", "lyrics_document",
]

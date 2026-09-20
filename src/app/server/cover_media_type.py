"""Authoritative image media type for artwork bytes that leave the service.

A cover's declared MIME string is part of the audio file: an ID3 APIC frame and a
FLAC PICTURE block both carry it as free text written by whatever tagged the file,
and provider artwork carries it in an HTTP response header. Those bytes are then
answered on the service origin, including on the UPnP artwork route, which needs no
session at all. A declared type therefore has to be treated as untrusted input twice
over: it names the document a browser is told it is looking at, and it is written
into a response header, where an embedded CR or LF becomes another header line.
"""

from __future__ import annotations

MAX_MEDIA_TYPE_CHARS = 64

# Bytes a streaming route must read to prove its own format.
SNIFF_PREFIX_BYTES = 32

# Raster types only, and only the ones a WebView can decode. image/svg+xml is
# deliberately absent: a browser that opens the artwork URL as a document runs any
# script inside an SVG, on the origin that served it.
ALLOWED_IMAGE_MEDIA_TYPES = (
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/avif",
    "image/heic",
    "image/tiff",
)

# Taggers write these for the same pixels, so they are canonicalised rather than
# refused: rejecting them would drop covers that work today.
_MEDIA_TYPE_ALIASES = {
    "image/jpg": "image/jpeg",
    "image/pjpeg": "image/jpeg",
    "image/x-icon": "image/png",
    "image/x-png": "image/png",
    "image/x-bitmap": "image/bmp",
    "image/x-ms-bmp": "image/bmp",
}

# A prefix that opens markup or a data document is never raster pixels,
# whatever the tag claimed. Refusing it keeps a permissive declaration
# from relabelling an embedded HTML or SVG payload as "image/jpeg".
_DOCUMENT_OPENERS = (b"<", b"{", b"[")
_BYTES = (bytes, bytearray, memoryview)

# The grammar of a media type minus its parameters. Anything outside this set,
# including CR, LF, quotes and spaces, makes the value unusable.
_MEDIA_TYPE_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789.+-/")


def _looks_like_document(body):
    """True when the payload opens a markup or data document."""
    if not isinstance(body, _BYTES):
        return False
    data = bytes(body[:SNIFF_PREFIX_BYTES]).lstrip()
    return data[:1] in _DOCUMENT_OPENERS


def sniff_image_media_type(body):
    """Return the media type the bytes themselves prove, or "" when unknown."""
    if not isinstance(body, _BYTES):
        return ""
    data = bytes(body[:SNIFF_PREFIX_BYTES])
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"BM") and len(data) >= 6:
        return "image/bmp"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in (b"avif", b"avis"):
            return "image/avif"
        if brand in (b"heic", b"heix", b"heim", b"heis", b"hev1"):
            return "image/heic"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    return ""


def normalize_media_type(value):
    """Return a declared type in canonical form, or "" when it is not safe text."""
    if not isinstance(value, str):
        return ""
    candidate = value.strip().split(";", 1)[0].strip().lower()
    if not candidate or len(candidate) > MAX_MEDIA_TYPE_CHARS:
        return ""
    if set(candidate) - _MEDIA_TYPE_CHARS:
        return ""
    if not candidate.startswith("image/"):
        return ""
    return _MEDIA_TYPE_ALIASES.get(candidate, candidate)


def safe_image_media_type(declared, body=None):
    """Resolve the one media type a cover response may claim, "" when there is none.

    Bytes win over declarations, because the declaration is whatever a tagger wrote
    and the pixels are what a browser will actually decode. When the bytes are not a
    format this list knows, an allowlisted declaration is still honoured so exotic but
    real raster artwork keeps working; anything else is refused rather than guessed.
    A payload that opens markup is refused even under an allowlisted declaration,
    which is how an embedded document would otherwise be relabelled as "image/jpeg".
    """
    sniffed = sniff_image_media_type(body)
    if sniffed:
        return sniffed
    if _looks_like_document(body):
        return ""
    candidate = normalize_media_type(declared)
    return candidate if candidate in ALLOWED_IMAGE_MEDIA_TYPES else ""


__all__ = [
    "ALLOWED_IMAGE_MEDIA_TYPES",
    "MAX_MEDIA_TYPE_CHARS",
    "SNIFF_PREFIX_BYTES",
    "normalize_media_type",
    "safe_image_media_type",
    "sniff_image_media_type",
]

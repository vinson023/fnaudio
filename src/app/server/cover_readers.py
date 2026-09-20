"""Bounded readers for embedded FLAC and APEv2 artwork.

The scanner owns orchestration; this module owns the two container-specific
cover readers so malformed metadata cannot leak parsing policy into the
library workflow.
"""

import os

from cover_media_type import safe_image_media_type
from ffmpeg_cover import MAX_COVER_FILE_BYTES


MAX_APE_TAG_BYTES = 16 * 1024 * 1024
MAX_COVER_BLOCK_BYTES = 8 * 1024 * 1024


def read_flac_cover(path):
    """Read a FLAC picture block without allocating oversized metadata.

    The MIME string in a PICTURE block is tagger-controlled free text, so the
    returned type is resolved from the picture bytes plus an allowlist. A block
    that cannot be described safely is skipped and the block scan moves on: FLAC
    allows several picture blocks, and none of the field lengths were written by
    this program.
    """
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
                if size > MAX_COVER_BLOCK_BYTES:
                    try:
                        fh.seek(size, os.SEEK_CUR)
                    except OSError:
                        return None, None
                    if last:
                        return None, None
                    continue
                data = fh.read(size)
                if len(data) != size:
                    return None, None
                if block_type == 6:
                    picture = _picture_block(data)
                    if picture:
                        return picture
                if last:
                    return None, None
    except OSError:
        return None, None


def _picture_block(data):
    """Describe one FLAC PICTURE block, or return None to mean "skip this block".

    Field order is RFC 9639 section 8.8, which the reader has always followed: u(32)
    picture type first, then u(32) media type length, the media type string, u(32)
    description length, the description, then width, height, colour depth and
    colours-used as four u(32) fields, then u(32) image length and the image. Do not
    "correct" this against the ID3 APIC memory - there the picture type is one byte
    and comes after the MIME string; in FLAC it is four bytes and comes first.

    Every length in here was written by whatever tagged the file, so each check
    refuses *this block* rather than the file. The code this was cut out of answered
    all four malformed-field conditions by returning ``(None, None)`` from
    `read_flac_cover()` itself, which threw away every picture block after the bad
    one, while the docstring above it promised the scan would move on (TODO.md:92).
    """
    if len(data) <= 32:
        return None
    mime_len = int.from_bytes(data[4:8], "big")
    pos = 8
    if mime_len > len(data) - pos:
        return None
    mime = data[pos:pos + mime_len].decode("utf-8", "ignore") or "image/jpeg"
    pos += mime_len
    if pos + 4 > len(data):
        return None
    desc_len = int.from_bytes(data[pos:pos + 4], "big")
    pos += 4 + desc_len
    if pos + 16 + 4 > len(data):
        return None
    pos += 16
    image_len = int.from_bytes(data[pos:pos + 4], "big")
    pos += 4
    if image_len > MAX_COVER_FILE_BYTES or image_len > len(data) - pos:
        return None
    image = data[pos:pos + image_len]
    media_type = safe_image_media_type(mime, image)
    if not media_type:
        return None
    return media_type, image


def read_ape_cover(path):
    """Read APEv2 Cover Art (Front) without decoding the audio stream."""
    try:
        with open(path, "rb") as fh:
            file_size = os.fstat(fh.fileno()).st_size
            if file_size < 32:
                return None, None
            fh.seek(-32, os.SEEK_END)
            footer = fh.read(32)
            if footer[:8] != b"APETAGEX":
                return None, None
            total = int.from_bytes(footer[12:16], "little")
            count = int.from_bytes(footer[16:20], "little")
            if total < 32 or total > MAX_APE_TAG_BYTES or total > file_size or count > 4096:
                return None, None
            fh.seek(file_size - total)
            body = fh.read(total)
            if len(body) != total:
                return None, None
    except OSError:
        return None, None
    if len(body) < 32 or body[-32:-24] != b"APETAGEX":
        return None, None
    total = int.from_bytes(body[-20:-16], "little")
    count = int.from_bytes(body[-16:-12], "little")
    start = len(body) - total
    if total < 32 or start < 0 or count > 4096:
        return None, None
    offset = start
    try:
        for _ in range(count):
            if offset + 9 > len(body) - 32:
                return None, None
            value_size = int.from_bytes(body[offset:offset + 4], "little")
            key_end = body.index(b"\x00", offset + 8, min(len(body) - 32, offset + 8 + 1024))
            key = body[offset + 8:key_end].decode("utf-8", "replace").casefold()
            value_start = key_end + 1
            value_end = value_start + value_size
            if value_end > len(body) - 32:
                return None, None
            if key == "cover art (front)":
                parts = body[value_start:value_end].split(b"\x00", 1)
                if len(parts) != 2 or len(parts[1]) > MAX_COVER_FILE_BYTES:
                    return None, None
                image = parts[1]
                if image.startswith(b"\xff\xd8\xff"):
                    return "image/jpeg", image
                if image.startswith(b"\x89PNG\r\n\x1a\n"):
                    return "image/png", image
                if image.startswith((b"GIF87a", b"GIF89a")):
                    return "image/gif", image
                return None, None
            offset = value_end
    except (ValueError, IndexError):
        return None, None
    return None, None

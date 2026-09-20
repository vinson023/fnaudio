"""Pure, bounded ID3 frame parsing shared by library metadata and cover readers."""

from __future__ import annotations

from ffmpeg_cover import MAX_COVER_FILE_BYTES

from cover_media_type import safe_image_media_type
from metadata_text import clean_tag, parse_track_number


_TEXT_FIELDS = {
    "TIT2": "title",
    "TPE1": "artist",
    "TALB": "album",
    "TCOM": "composer",
    "TCON": "genre",
    "TRCK": "track_no",
}


def decode_id3_text(data):
    """Decode a single ID3 text frame payload without leaking decode errors."""
    if not isinstance(data, (bytes, bytearray, memoryview)) or not data:
        return ""
    encoding = data[0]
    raw = bytes(data[1:])
    try:
        if encoding == 0:
            for codec in ("utf-8", "gb18030", "latin1"):
                try:
                    return raw.decode(codec)
                except UnicodeError:
                    continue
            return raw.decode("latin1", "ignore")
        if encoding == 1:
            return raw.decode("utf-16", "ignore")
        if encoding == 2:
            return raw.decode("utf-16-be", "ignore")
        return raw.decode("utf-8", "ignore")
    except UnicodeError:
        return raw.decode("utf-8", "ignore")


def decode_id3v1_field(data):
    """Decode a fixed-width ID3v1 field without exposing decode errors."""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        return ""
    raw = bytes(data).rstrip(b"\x00 ").strip()
    for encoding in ("utf-8", "gb18030", "latin1"):
        try:
            return clean_tag(raw.decode(encoding))
        except UnicodeError:
            continue
    return clean_tag(raw.decode("latin1", "ignore"))


_TAG_FLAG_UNSYNCHRONISATION = 0x80
_TAG_FLAG_EXTENDED_HEADER = 0x40

# A frame carries its own two flag bytes.  Only the second one (the format
# flags) says where the frame body starts; the first is preservation advice and
# must never make a readable frame unreadable.  v2.3 defines compression,
# encryption and a group id prefix; v2.4 defines grouping, compression,
# encryption, frame-level unsynchronisation and a data length indicator, and its
# two remaining format bits are reserved.  A transform this reader cannot undo
# is refused rather than yielded: zlib or cipher bytes reaching the title and
# artist fields is a mis-read, and the tag writer that copies preserved frames
# would re-emit them with the flag cleared, which destroys the frame outright.
_FRAME_FLAG_FORMAT_BITS = 0x00FF
_FRAME24_UNDOABLE_FORMAT_BITS = 0x0003
_FRAME24_FORMAT_UNSYNCHRONISATION = 0x0002
_FRAME24_FORMAT_DATA_LENGTH_INDICATOR = 0x0001
_FRAME24_DATA_LENGTH_BYTES = 4


def _synchsafe(raw):
    size = 0
    for byte in raw:
        size = (size << 7) | (byte & 0x7F)
    return size


def id3_tag_is_readable(header):
    """Whether frames can be located in the tag described by ``header``.

    ID3v2.2 frames carry three-byte identifiers with three-byte sizes, a layout
    this reader does not implement.  Refusing the tag is honest: reading it as
    v2.3 yields nothing useful and hides the fact that an ID3v1 block at the end
    of the same file may still describe the track.
    """
    return bool(header) and len(header) == 10 and header[3] != 2


def id3_frame_region(data, major=3, flags=0):
    """Return the part of a tag payload that actually holds frames.

    ``flags`` is the ID3v2 header flag byte, and it is the only place the two
    layouts that hide frames are declared.  Tag-level unsynchronisation stuffs a
    ``0x00`` after every ``0xFF``, so a reader that ignores it walks past the
    declared frame sizes: every frame behind a picture is lost and the returned
    picture bytes are the stuffed ones.  An extended header sits in front of the
    frames, and its length field counts itself in v2.4 but not in v2.3.
    """
    if not isinstance(data, (bytes, bytearray, memoryview)) or major == 2:
        return b""
    payload = bytes(data)
    if flags & _TAG_FLAG_UNSYNCHRONISATION:
        payload = payload.replace(b"\xff\x00", b"\xff")
    if flags & _TAG_FLAG_EXTENDED_HEADER:
        if major == 4:
            skip = _synchsafe(payload[:4])
            minimum = 6
        else:
            skip = 4 + int.from_bytes(payload[:4], "big")
            minimum = 8
        if skip < minimum or skip > len(payload):
            return b""
        payload = payload[skip:]
    return payload

def id3_frame_size(data, offset, major):
    """Read an ID3v2.3/v2.4 frame size, returning zero for incomplete input."""
    if not isinstance(data, (bytes, bytearray, memoryview)) or offset < 0 or offset + 8 > len(data):
        return 0
    raw = data[offset + 4:offset + 8]
    if major == 4:
        return _synchsafe(raw)
    return int.from_bytes(raw, "big")


def _frame_body(payload, frame_flags, major):
    """Return a frame body, or ``None`` when its format flags defeat the reader.

    Both undoable v2.4 transformations are applied in the order the layout
    defines them: the data length indicator is a header field, so it comes off
    before frame-level unsynchronisation is expanded.  Every other set format
    bit -- including v2.3 compression, encryption and grouping, and the bits the
    v2.4 format byte leaves undefined -- means the bytes that follow are not the
    frame text, so the frame is refused.
    """
    format_bits = frame_flags & _FRAME_FLAG_FORMAT_BITS
    if format_bits:
        if major != 4:
            return None
        if format_bits & ~_FRAME24_UNDOABLE_FORMAT_BITS:
            return None
        if format_bits & _FRAME24_FORMAT_DATA_LENGTH_INDICATOR:
            if len(payload) <= _FRAME24_DATA_LENGTH_BYTES:
                return None
            payload = payload[_FRAME24_DATA_LENGTH_BYTES:]
        if format_bits & _FRAME24_FORMAT_UNSYNCHRONISATION:
            payload = payload.replace(b"\xff\x00", b"\xff")
    return payload


def iter_id3_frames(data, major=3, flags=0):
    """Yield ``(frame_id, payload)`` pairs from bounded tag bytes.

    Tag-level flags are handled by ``id3_frame_region`` and per-frame format
    flags by ``_frame_body``.  A frame whose own flags declare an unundoable
    transform is skipped and the walk resumes at its declared end, so the
    frames behind it are still read.
    """
    payload = id3_frame_region(data, major, flags)
    offset = 0
    length = len(payload)
    while offset + 10 <= length:
        frame_id = bytes(payload[offset:offset + 4]).decode("latin1", "ignore")
        frame_size = id3_frame_size(payload, offset, major)
        if not frame_id.strip("\x00") or frame_size <= 0:
            return
        frame_end = offset + 10 + frame_size
        if frame_end > length:
            return
        body = _frame_body(
            bytes(payload[offset + 10:frame_end]),
            int.from_bytes(payload[offset + 8:offset + 10], "big"),
            major,
        )
        if body is not None:
            yield frame_id, body
        offset = frame_end


def parse_id3_tags(data, major=3, flags=0):
    """Return the library tag fields represented by ID3 text frames."""
    tags = {}
    for frame_id, frame in iter_id3_frames(data, major, flags):
        field = _TEXT_FIELDS.get(frame_id)
        if not field:
            continue
        value = decode_id3_text(frame).split("\x00", 1)[0]
        tags[field] = parse_track_number(value) if field == "track_no" else clean_tag(value)
    return tags


def parse_id3_cover(data, major=3, flags=0):
    """Return the first usable embedded APIC cover as ``(media type, bytes)``.

    The MIME string inside an APIC frame is free text written by whatever tagger
    touched the file, so the returned type is resolved from the picture bytes and
    an allowlist. A frame whose picture cannot be described safely is skipped and
    the scan continues with the next one.
    """
    for frame_id, frame in iter_id3_frames(data, major, flags):
        if frame_id != "APIC" or not frame:
            continue
        encoding = frame[0]
        mime_end = frame.find(b"\x00", 1)
        if mime_end < 0:
            continue
        mime = frame[1:mime_end].decode("latin1", "ignore") or "image/jpeg"
        pos = mime_end + 2  # MIME terminator plus one-byte picture type.
        if encoding in (1, 2):
            end = frame.find(b"\x00\x00", pos)
            pos = end + 2 if end >= 0 else pos
        else:
            end = frame.find(b"\x00", pos)
            pos = end + 1 if end >= 0 else pos
        image = frame[pos:]
        if image and len(image) <= MAX_COVER_FILE_BYTES:
            media_type = safe_image_media_type(mime, image)
            if media_type:
                return media_type, image
    return None, None

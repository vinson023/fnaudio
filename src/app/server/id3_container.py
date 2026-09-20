"""Bounded location of ID3 payloads inside common audio containers."""

import os

from id3_parser import decode_id3v1_field, id3_tag_is_readable, parse_id3_cover, parse_id3_tags


MAX_ID3_PAYLOAD_BYTES = 16 * 1024 * 1024


def read_id3_header_at(fh, offset):
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        return None, b""
    try:
        fh.seek(offset)
        header = fh.read(10)
        if len(header) != 10 or header[:3] != b"ID3":
            return None, b""
        if any(byte & 0x80 for byte in header[6:10]):
            return None, b""
        size = 0
        for byte in header[6:10]:
            size = (size << 7) | (byte & 0x7F)
        if size > MAX_ID3_PAYLOAD_BYTES:
            return None, b""
        data = fh.read(size)
        if len(data) != size:
            return None, b""
        return header, data
    except OSError:
        return None, b""


def id3_tag(path):
    """Locate an ID3 tag at the file start or supported container offset."""
    try:
        with open(path, "rb") as fh:
            header, data = read_id3_header_at(fh, 0)
            if header:
                return header, data
            ext = os.path.splitext(path)[1].lower()
            if ext == ".wav":
                fh.seek(0)
                riff = fh.read(12)
                if riff[:4] != b"RIFF" or riff[8:12] != b"WAVE":
                    return None, b""
                limit = min(os.path.getsize(path), 8 + int.from_bytes(riff[4:8], "little"))
                offset = 12
                while offset + 8 <= limit:
                    fh.seek(offset)
                    chunk_id = fh.read(4)
                    chunk_size = int.from_bytes(fh.read(4), "little")
                    payload = offset + 8
                    if payload + chunk_size > limit:
                        break
                    if chunk_id.lower() == b"id3 ":
                        return read_id3_header_at(fh, payload)
                    offset = payload + chunk_size + (chunk_size & 1)
                return None, b""
            if ext != ".dsf":
                return None, b""
            fh.seek(0)
            dsf_header = fh.read(28)
            if dsf_header[:4] != b"DSD " or len(dsf_header) < 28:
                return None, b""
            metadata_offset = int.from_bytes(dsf_header[20:28], "little")
            if metadata_offset <= 0:
                return None, b""
            return read_id3_header_at(fh, metadata_offset)
    except OSError:
        return None, b""


def id3_payload(path):
    """Return only the located payload for callers that do not need headers."""
    _header, data = id3_tag(path)
    return data


def read_id3v1(path):
    try:
        with open(path, "rb") as fh:
            fh.seek(-128, os.SEEK_END)
            data = fh.read(128)
    except OSError:
        return {}
    if len(data) != 128 or data[:3] != b"TAG":
        return {}
    tags = {
        "title": decode_id3v1_field(data[3:33]),
        "artist": decode_id3v1_field(data[33:63]),
        "album": decode_id3v1_field(data[63:93]),
    }
    return {key: value for key, value in tags.items() if value}


def read_id3(path):
    header, data = id3_tag(path)
    if not data or not id3_tag_is_readable(header):
        # No usable v2 block.  An ID3v1 record at the end of the file can
        # still describe the track, and it is the only thing left to read.
        return read_id3v1(path)
    return parse_id3_tags(data, header[3], header[5])


def read_id3_cover(path):
    header, data = id3_tag(path)
    if not data or not id3_tag_is_readable(header):
        return None, None
    return parse_id3_cover(data, header[3], header[5])

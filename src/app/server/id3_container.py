"""Bounded location of ID3 payloads inside common audio containers."""

import os

from id3_parser import decode_id3v1_field, id3_tag_is_readable, parse_id3_cover, parse_id3_tags


MAX_ID3_PAYLOAD_BYTES = 16 * 1024 * 1024
MAX_RIFF_INFO_BYTES = 4 * 1024 * 1024


def _read_riff_info(path):
    """Read common RIFF/WAVE LIST-INFO tags, including ITRK."""
    fields = {
        b"INAM": "title",
        b"IART": "artist",
        b"IPRD": "album",
        b"ICMT": "composer",
        b"IGNR": "genre",
        b"ICRD": "date",
        b"ITRK": "track_no",
    }
    tags = {}
    try:
        from metadata_text import clean_tag, parse_track_number
        with open(path, "rb") as fh:
            header = fh.read(12)
            if len(header) != 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
                return {}
            limit = min(os.path.getsize(path), 8 + int.from_bytes(header[4:8], "little"))
            offset = 12
            while offset + 8 <= limit:
                fh.seek(offset)
                chunk_id = fh.read(4)
                raw_size = fh.read(4)
                if len(raw_size) != 4:
                    break
                chunk_size = int.from_bytes(raw_size, "little")
                payload = offset + 8
                if payload + chunk_size > limit:
                    break
                if chunk_id == b"LIST" and chunk_size >= 4 and chunk_size <= MAX_RIFF_INFO_BYTES:
                    fh.seek(payload)
                    if fh.read(4) == b"INFO":
                        end = payload + chunk_size
                        pos = payload + 4
                        while pos + 8 <= end:
                            fh.seek(pos)
                            sub_id = fh.read(4)
                            sub_size_raw = fh.read(4)
                            if len(sub_size_raw) != 4:
                                break
                            sub_size = int.from_bytes(sub_size_raw, "little")
                            sub_payload = pos + 8
                            if sub_payload + sub_size > end:
                                break
                            field = fields.get(sub_id)
                            if field and sub_size <= MAX_ID3_PAYLOAD_BYTES:
                                fh.seek(sub_payload)
                                text = fh.read(sub_size).rstrip(b"\x00").decode("utf-8", "ignore")
                                value = parse_track_number(text) if field == "track_no" else clean_tag(text)
                                if value:
                                    result = fields.get(sub_id)
                                    if result:
                                        # Preserve the first value from a valid INFO list.
                                        tags.setdefault(result, value)
                            pos = sub_payload + sub_size + (sub_size & 1)
                offset = payload + chunk_size + (chunk_size & 1)
    except (OSError, ValueError, OverflowError):
        return {}
    return tags


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
    riff_tags = _read_riff_info(path) if os.path.splitext(path)[1].lower() == ".wav" else {}
    if not data or not id3_tag_is_readable(header):
        # No usable v2 block.  An ID3v1 record at the end of the file can
        # still describe the track, and it is the only thing left to read.
        result = read_id3v1(path)
        result = {**riff_tags, **result}
        return result
    return {**riff_tags, **parse_id3_tags(data, header[3], header[5])}


def read_id3_cover(path):
    header, data = id3_tag(path)
    if not data or not id3_tag_is_readable(header):
        return None, None
    return parse_id3_cover(data, header[3], header[5])

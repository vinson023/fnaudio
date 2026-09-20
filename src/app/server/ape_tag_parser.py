"""Pure parsing helpers for legacy APE tag payloads."""


def parse_ape_items(payload, count, footer_end=None):
    """Parse bounded APE item bytes and return a list or ``None`` on error."""
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        return None
    if not isinstance(count, int) or isinstance(count, bool) or count < 0 or count > 4096:
        return None
    payload = bytes(payload)
    end = len(payload) if footer_end is None else footer_end
    if not isinstance(end, int) or isinstance(end, bool) or end < 0 or end > len(payload):
        return None
    offset = 0
    items = []
    try:
        for _ in range(count):
            if offset + 8 > end:
                return None
            size = int.from_bytes(payload[offset:offset + 4], "little")
            flags = payload[offset + 4:offset + 8]
            key_end = payload.index(b"\x00", offset + 8, min(end, offset + 8 + 1024))
            key = payload[offset + 8:key_end].decode("utf-8", "replace")
            value_start = key_end + 1
            value_end = value_start + size
            if value_end > end:
                return None
            items.append((key, flags, payload[value_start:value_end]))
            offset = value_end
    except (ValueError, UnicodeError):
        return None
    return items if offset == end else None


def parse_ape_body(body):
    """Return ``(audio_prefix, items)`` for a complete APE-tagged payload."""
    if not isinstance(body, (bytes, bytearray, memoryview)):
        return b"", []
    body = bytes(body)
    if len(body) < 32 or body[-32:-24] != b"APETAGEX":
        return body, []
    total = int.from_bytes(body[-20:-16], "little")
    count = int.from_bytes(body[-16:-12], "little")
    start = len(body) - total
    if total < 32 or start < 0 or count > 4096:
        return body, []
    items = parse_ape_items(body[start:], count, len(body[start:]) - 32)
    if items is None:
        return body, []
    return body[:start], items

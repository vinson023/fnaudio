"""Native, dependency-free audio stream facts for formats with stable containers."""

from __future__ import annotations

import os
import wave


def read_native_audio_info(path):
    """Read WAV/DFF stream facts without invoking ffprobe or decoding audio."""
    try:
        path = os.fspath(path)
    except TypeError:
        return {}
    if not isinstance(path, str):
        return {}
    ext = os.path.splitext(path)[1].lower()
    if ext == ".wav":
        try:
            with wave.open(path, "rb") as handle:
                rate = int(handle.getframerate() or 0)
                channels = int(handle.getnchannels() or 0)
                bits = int(handle.getsampwidth() or 0) * 8
                frames = int(handle.getnframes() or 0)
            return {
                "sample_rate": rate,
                "bit_depth": bits,
                "bit_rate": rate * channels * bits,
                "duration": frames / float(rate) if rate > 0 else 0.0,
            }
        except (OSError, EOFError, wave.Error):
            return {}
    if ext != ".dff":
        return {}
    try:
        with open(path, "rb") as handle:
            if handle.read(4) != b"FRM8":
                return {}
            form_size = int.from_bytes(handle.read(8), "big")
            if handle.read(4) != b"DSD ":
                return {}
            end = min(os.path.getsize(path), 12 + form_size)
            sample_rate = 0
            channels = 0
            dsd_bytes = 0

            def chunks(first, limit):
                position = first
                while position + 12 <= limit:
                    handle.seek(position)
                    chunk_id = handle.read(4)
                    raw_size = handle.read(8)
                    if len(raw_size) != 8:
                        break
                    size = int.from_bytes(raw_size, "big")
                    payload = position + 12
                    # Reject ranges that cannot fit inside the bounded FORM
                    # before descending into a malformed chunk.
                    if size > limit - payload:
                        break
                    yield chunk_id, payload, size
                    position = payload + size + (size % 2)

            for chunk_id, payload, size in chunks(16, end):
                if chunk_id == b"PROP" and size >= 4:
                    handle.seek(payload)
                    if handle.read(4) != b"SND ":
                        continue
                    for prop_id, prop_payload, prop_size in chunks(payload + 4, payload + size):
                        handle.seek(prop_payload)
                        if prop_id == b"FS  " and prop_size >= 4:
                            sample_rate = int.from_bytes(handle.read(4), "big")
                        elif prop_id == b"CHNL" and prop_size >= 2:
                            channels = int.from_bytes(handle.read(2), "big")
                elif chunk_id == b"DSD ":
                    dsd_bytes = size
            duration = (dsd_bytes * 8) / float(sample_rate * channels) if sample_rate > 0 and channels > 0 else 0.0
            return {
                "sample_rate": sample_rate,
                "bit_depth": 1,
                "bit_rate": sample_rate * channels,
                "duration": duration,
            } if sample_rate and channels else {}
    except (OSError, ValueError):
        return {}

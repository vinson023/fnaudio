"""Bounded CUE source-file reading, separated from parsing policy."""

from __future__ import annotations

from text_encoding_policy import decode_lines

MAX_CUE_FILE_BYTES = 8 * 1024 * 1024


def read_cue_lines(cue_path, config=None):
    """Decode a CUE file without materializing an unbounded source.

    R591: the encoding is no longer a fixed fallback chain.  ``gb18030`` accepts
    almost every byte pair, so the old ``utf-8-sig -> gb18030 -> big5 -> latin1``
    chain never reached ``big5`` and decoded a Big5 sheet as mojibake without any
    error.  ``text_encoding_policy`` owns the decision now, including the
    per-library ``text_encoding`` override.
    """
    if not isinstance(cue_path, str):
        return []
    try:
        with open(cue_path, "rb") as handle:
            payload = handle.read(MAX_CUE_FILE_BYTES + 1)
    except OSError:
        return []
    if len(payload) > MAX_CUE_FILE_BYTES:
        return []
    explicit = ""
    if isinstance(config, dict):
        explicit = config.get("text_encoding", "")
    return decode_lines(payload, explicit)


__all__ = ["MAX_CUE_FILE_BYTES", "read_cue_lines"]

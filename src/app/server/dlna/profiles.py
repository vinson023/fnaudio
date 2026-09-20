from __future__ import annotations

import re
from typing import Any, Dict


DSD_MIME_TYPES = {"audio/dsd", "audio/x-dsd", "audio/dsf", "audio/x-dsf", "audio/x-dff"}

# The native-DSD fact has exactly three states.  Collapsing "we never managed to
# ask" into "the renderer refused" is what made the push gate and the transport
# target list disagree, so the collapse is now impossible by construction.
DSD_CAPABILITY_SUPPORTED = "supported"
DSD_CAPABILITY_UNSUPPORTED = "unsupported"
DSD_CAPABILITY_UNKNOWN = "unknown"
MAX_MIME_CHARS = 128
_MIME_PATTERN = re.compile(r"^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+$")


def _safe_mime(value: Any, fallback: str) -> str:
    candidate = value if isinstance(value, str) else fallback
    if not isinstance(candidate, str) or len(candidate) > MAX_MIME_CHARS:
        return "application/octet-stream"
    return candidate if _MIME_PATTERN.fullmatch(candidate) else "application/octet-stream"


def _dsd_state_from(record: Dict[str, Any]) -> str:
    """Read one capability record without inventing a claim it does not make.

    A present value is a claim, and only ``True`` claims support; a malformed
    value therefore counts as "not supported" rather than as silence, which is
    the conservative reading the push gate needs.  An absent key is silence.
    """
    try:
        has_claim = "supports_dsd" in record
        value = record.get("supports_dsd")
    except Exception:
        return DSD_CAPABILITY_UNKNOWN
    if not has_claim:
        return DSD_CAPABILITY_UNKNOWN
    return DSD_CAPABILITY_SUPPORTED if value is True else DSD_CAPABILITY_UNSUPPORTED


def dsd_capability_state(source: Any) -> str:
    """The single predicate for "does this device do source DSD".

    ``source`` is either a device mapping, whose authoritative record is the
    discovery probe nested in ``capabilities.protocol_info``, or a bare
    ``protocol_info`` mapping as produced by ``device_protocol_info()``.  The
    probe record wins over the flat device field whenever both are present, so
    the derived display field can never outvote the evidence it came from.
    """
    if not isinstance(source, dict):
        return DSD_CAPABILITY_UNKNOWN
    try:
        capabilities = source.get("capabilities")
    except Exception:
        return DSD_CAPABILITY_UNKNOWN
    if isinstance(capabilities, dict):
        try:
            probed = "protocol_info" in capabilities
            protocol = capabilities.get("protocol_info")
        except Exception:
            return DSD_CAPABILITY_UNKNOWN
        if probed:
            if not isinstance(protocol, dict):
                return DSD_CAPABILITY_UNKNOWN
            return _dsd_state_from(protocol)
    return _dsd_state_from(source)


def device_supports_native_dsd(device: Any) -> bool:
    """Conservative bool view of :func:`dsd_capability_state`.

    Only a probe that confirmed support lights this up.  Unknown and refused
    both render as False, which is what a display surface needs; the push gate
    reads the three-state predicate instead so a missing probe cannot be turned
    into a refusal.
    """
    return dsd_capability_state(device) == DSD_CAPABILITY_SUPPORTED


def mime_for_item(item: Dict[str, Any], fallback: str = "application/octet-stream") -> str:
    try:
        value = item.get("mime") if isinstance(item, dict) else None
    except Exception:
        value = None
    return _safe_mime(value, fallback)


def should_direct_push(item: Dict[str, Any], device: Dict[str, Any]) -> bool:
    # DSD push is intentionally source-direct. The renderer is responsible
    # for advertising native DSD support; fnAudio must not silently change the
    # source format during a push.
    return True


def protocol_info(item: Dict[str, Any], device: Dict[str, Any]) -> str:
    mime = mime_for_item(item)
    return f"http-get:*:{mime}:*"

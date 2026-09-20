from __future__ import annotations

import re

from typing import Any, Dict, Iterable


DEFAULT_PROFILE = {
    "audio_buffer_size": "8M",
    "startup_delay_ms": 0,
    "track_settle_ms": 0,
    "force_dop": False,
    "disable_native_dsd": False,
    "keepalive_mode": "off",
}
MAX_CUSTOM_PROFILES = 64
MAX_PROFILE_TEXT_CHARS = 128


def _profile_text(value):
    """Accept persisted profile identifiers without invoking custom casts."""
    if not isinstance(value, str):
        return ""
    value = value.strip()
    return value[:MAX_PROFILE_TEXT_CHARS]


def _profile_bool(value):
    return value if isinstance(value, bool) else False


def _audio_buffer_size(value):
    value = _profile_text(value)
    return value if re.fullmatch(r"[1-9][0-9]{0,8}[kKmM]?", value) else DEFAULT_PROFILE["audio_buffer_size"]


def _bounded_delay(value, maximum):
    """Keep persisted profile delays from breaking output selection."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return 0
    if isinstance(value, str) and len(value) > 16:
        return 0
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(0, min(maximum, number))


def bounded_custom_profiles(values):
    """Copy at most the supported number of mapping-shaped DAC profiles."""
    result = []
    try:
        iterator = iter(values or ())
    except Exception:
        return result
    for _ in range(MAX_CUSTOM_PROFILES):
        try:
            value = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        if isinstance(value, dict):
            result.append(dict(value))
    return result


def dac_quirk_profile(device: Dict[str, Any], custom_profiles: Iterable[Dict[str, Any]] = ()) -> Dict[str, Any]:
    profile = dict(DEFAULT_PROFILE)
    matched = "default"
    device = device if isinstance(device, dict) else {}
    try:
        iterator = iter(custom_profiles or ())
    except Exception:
        iterator = iter(())
    for _ in range(MAX_CUSTOM_PROFILES):
        try:
            candidate = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        if not isinstance(candidate, dict):
            continue
        raw_match = candidate.get("match")
        match = raw_match if isinstance(raw_match, dict) else {}
        stable_id = _profile_text(match.get("stable_id"))
        vendor_id = _profile_text(match.get("vendor_id")).lower()
        product_id = _profile_text(match.get("product_id")).lower()
        if stable_id and stable_id != _profile_text(device.get("stable_id")):
            continue
        if vendor_id and vendor_id != _profile_text(device.get("usb_vendor_id")).lower():
            continue
        if product_id and product_id != _profile_text(device.get("usb_product_id")).lower():
            continue
        raw_settings = candidate.get("settings")
        if isinstance(raw_settings, dict):
            profile.update(raw_settings)
        matched = _profile_text(candidate.get("name")) or stable_id or "custom"
        break
    profile["name"] = matched
    profile["audio_buffer_size"] = _audio_buffer_size(profile.get("audio_buffer_size"))
    profile["startup_delay_ms"] = _bounded_delay(profile.get("startup_delay_ms"), 5000)
    profile["track_settle_ms"] = _bounded_delay(profile.get("track_settle_ms"), 500)
    profile["force_dop"] = _profile_bool(profile.get("force_dop"))
    profile["disable_native_dsd"] = _profile_bool(profile.get("disable_native_dsd"))
    keepalive = _profile_text(profile.get("keepalive_mode")).lower() or "off"
    profile["keepalive_mode"] = keepalive if keepalive in ("off", "pcm_only") else "off"
    return profile

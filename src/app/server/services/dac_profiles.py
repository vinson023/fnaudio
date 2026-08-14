from __future__ import annotations

from typing import Any, Dict, Iterable


DEFAULT_PROFILE = {
    "audio_buffer_size": "8M",
    "startup_delay_ms": 0,
    "track_settle_ms": 0,
    "force_dop": False,
    "disable_native_dsd": False,
    "keepalive_mode": "off",
}


def dac_quirk_profile(device: Dict[str, Any], custom_profiles: Iterable[Dict[str, Any]] = ()) -> Dict[str, Any]:
    profile = dict(DEFAULT_PROFILE)
    matched = "default"
    for candidate in list(custom_profiles or []):
        match = dict(candidate.get("match") or {})
        if match.get("stable_id") and match.get("stable_id") != device.get("stable_id"):
            continue
        if match.get("vendor_id") and str(match.get("vendor_id")).lower() != str(device.get("usb_vendor_id") or "").lower():
            continue
        if match.get("product_id") and str(match.get("product_id")).lower() != str(device.get("usb_product_id") or "").lower():
            continue
        profile.update(dict(candidate.get("settings") or {}))
        matched = str(candidate.get("name") or match.get("stable_id") or "custom")
        break
    profile["name"] = matched
    profile["startup_delay_ms"] = max(0, min(5000, int(profile.get("startup_delay_ms") or 0)))
    profile["track_settle_ms"] = max(0, min(500, int(profile.get("track_settle_ms") or 0)))
    keepalive = str(profile.get("keepalive_mode") or "off").lower()
    profile["keepalive_mode"] = keepalive if keepalive in ("off", "pcm_only") else "off"
    return profile

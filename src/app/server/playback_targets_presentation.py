"""Bounded public presentation for selectable playback targets."""

from __future__ import annotations

import urllib.parse
import math
from typing import Any, Dict, Iterable, List, Mapping, Tuple

from dlna.profiles import device_supports_native_dsd


MAX_TARGETS = 256
MAX_TEXT = 512


def _text(value: Any, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _items(source: Any, limit: int) -> Iterable[Mapping[str, Any]]:
    if not isinstance(source, (list, tuple)):
        return ()
    return (item for item in source[:max(0, limit)] if isinstance(item, Mapping))


def _target_id(prefix: str, value: Any) -> str:
    identity = _text(value)
    if not identity:
        return ""
    return prefix + urllib.parse.quote(identity, safe=":,=-_")


def _safe_capabilities(value: Any) -> Dict[str, Any]:
    source = _mapping(value)
    result: Dict[str, Any] = {}
    try:
        iterator = iter(source.items())
    except Exception:
        return result
    for _ in range(32):
        try:
            key, item = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        if not isinstance(key, str) or len(key) > 80:
            continue
        if isinstance(item, float) and not math.isfinite(item):
            continue
        if isinstance(item, (str, bool, int, float)) or item is None:
            result[key] = item if not isinstance(item, str) else item[:MAX_TEXT]
        elif isinstance(item, (list, tuple)):
            result[key] = [entry[:MAX_TEXT] for entry in item[:32] if isinstance(entry, str)]
    return result


def build_targets(
    mpd: Any,
    core_state: Any,
    upnp_devices: Any,
    browser_capabilities: Any,
    mpd_capabilities: Any,
    dlna_capabilities: Any,
) -> Tuple[List[Dict[str, Any]], str, str]:
    """Return a compact, bounded target list and active target metadata.

    Keep all target row fields public/UI-safe. In particular, do not duplicate
    the complete MPD and upmpdcli diagnostic payload once per USB DAC row.
    """
    mpd_state = _mapping(mpd)
    capabilities = _mapping(mpd_state.get("output_capabilities"))
    core = _mapping(core_state)
    current_target = _text(core.get("target_id")) or "local"
    selected_output = _mapping(capabilities.get("selected_output"))
    if current_target == "mpd":
        resolved = _target_id("mpd:", selected_output.get("stable_id") or selected_output.get("alsa_id"))
        if resolved:
            current_target = resolved
    if current_target == "browser":
        current_target = "local"
    available = mpd_state.get("available") is True
    targets: List[Dict[str, Any]] = [{
        "id": "local",
        "name": "当前设备",
        "kind": "browser",
        "online": True,
        "selected": current_target == "local",
        "capabilities": _safe_capabilities(browser_capabilities),
    }]
    current_target_name = "当前设备" if current_target == "local" else ""

    for device in _items(capabilities.get("devices"), MAX_TARGETS - len(targets)):
        if device.get("is_usb") is not True:
            continue
        alsa_id = _text(device.get("alsa_id"))
        if not alsa_id:
            continue
        persistent_id = _text(device.get("stable_id")) or alsa_id
        target_id = _target_id("mpd:", persistent_id)
        if not target_id:
            continue
        name = _text(device.get("name")) or alsa_id
        selected = target_id == current_target
        targets.append({
            "id": target_id,
            "kind": "mpd",
            "name": "NAS - %s - USB Audio" % name,
            "online": available,
            "available": available,
            "selected": selected,
            "message": "当前 USB DAC" if selected else "本机 USB DAC",
            "caps": _safe_capabilities(device.get("caps")),
            "raw_name": _text(device.get("raw_name")),
            "backend": {
                "mpd_available": available,
                "alsa_id": alsa_id,
                "stable_id": _text(device.get("stable_id")),
                "stable_alsa_id": _text(device.get("stable_alsa_id")),
            },
            "capabilities": _safe_capabilities(mpd_capabilities),
        })
        if selected:
            current_target_name = "USB DAC · " + name
        if len(targets) >= MAX_TARGETS:
            break

    for device in _items(upnp_devices, MAX_TARGETS - len(targets)):
        device_id = _text(device.get("id"))
        if not device_id:
            continue
        selected = device_id == current_target
        target_caps = _safe_capabilities(dlna_capabilities)
        target_caps.update(_safe_capabilities(device.get("capabilities")))
        # One predicate for one fact: the transport list lights native DSD only on
        # the same probe record the push gate refuses on.
        target_caps["native_dsd"] = device_supports_native_dsd(device)
        name = _text(device.get("name")) or "DLNA 设备"
        targets.append({
            "id": device_id,
            "name": name,
            "kind": "dlna_push",
            "online": device.get("online") is True,
            "selected": selected,
            "capabilities": target_caps,
        })
        if selected:
            current_target_name = name
        if len(targets) >= MAX_TARGETS:
            break
    return targets, current_target, current_target_name

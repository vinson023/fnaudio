"""Pure selection helpers for cached/discovered UPnP devices."""

from __future__ import annotations


MAX_DEVICES = 500

def select_upnp_device(devices, device_id):
    """Return the first mapping with an exact text device ID, else ``None``."""
    if not isinstance(device_id, str) or not device_id:
        return None
    if isinstance(devices, (str, bytes, bytearray)):
        return None
    try:
        iterator = iter(devices)
    except Exception:
        return None
    for _ in range(MAX_DEVICES):
        try:
            device = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        if not isinstance(device, dict):
            continue
        try:
            if device.get("id") == device_id:
                return device
        except Exception:
            continue
    return None


__all__ = ["MAX_DEVICES", "select_upnp_device"]

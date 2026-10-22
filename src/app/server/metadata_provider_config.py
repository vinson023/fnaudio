"""Validated runtime configuration for metadata providers.

The provider chain is shared by the background worker and the settings pane.
This module intentionally contains no network or service code so malformed
configuration can be tested and repaired without starting the metadata worker.
"""

from __future__ import annotations

import copy


MUSICBRAINZ_PROVIDER_ID = "musicbrainz"

_PROVIDER_DEFINITIONS = (
    {
        "id": "netease",
        "name": "网易云音乐",
        "capabilities": ("search", "album", "artist", "track", "cover", "lyrics"),
        "default_enabled": True,
    },
    {
        "id": "kuwo",
        "name": "酷我音乐",
        "capabilities": ("search", "album", "track", "cover", "lyrics"),
        "default_enabled": True,
    },
    {
        "id": "kugou",
        "name": "酷狗音乐",
        "capabilities": ("search", "album", "track", "cover", "lyrics"),
        "default_enabled": True,
    },
    {
        "id": "migu",
        "name": "咪咕音乐",
        "capabilities": ("search", "album", "track", "cover", "lyrics"),
        "default_enabled": True,
    },
    {
        "id": "joox",
        "name": "JOOX",
        "capabilities": ("search", "album", "track", "cover", "lyrics"),
        "default_enabled": True,
    },
    {
        "id": MUSICBRAINZ_PROVIDER_ID,
        "name": "MusicBrainz",
        "capabilities": ("search", "album", "track", "cover"),
        "default_enabled": True,
        "fixed_last": True,
    },
)

DEFAULT_PROVIDER_ORDER = tuple(item["id"] for item in _PROVIDER_DEFINITIONS)
_KNOWN_PROVIDER_IDS = frozenset(DEFAULT_PROVIDER_ORDER)


def provider_definitions():
    """Return detached provider definitions for API/UI projection."""
    return copy.deepcopy([dict(item) for item in _PROVIDER_DEFINITIONS])


def default_metadata_provider_config():
    """Return the complete safe configuration in recommended order."""
    return [
        {"id": item["id"], "enabled": item["default_enabled"] is True}
        for item in _PROVIDER_DEFINITIONS
    ]


def normalize_metadata_provider_config(value):
    """Validate a complete provider configuration or return safe defaults.

    The settings UI always submits the complete ordered list. Requiring every
    known provider here means a damaged or stale hand-edited configuration is
    repaired atomically instead of silently dropping a newly added provider.
    """
    safe = default_metadata_provider_config()
    if not isinstance(value, (list, tuple)) or len(value) != len(_PROVIDER_DEFINITIONS):
        return safe

    normalized = []
    seen = set()
    for item in value:
        if not isinstance(item, dict):
            return safe
        provider_id = item.get("id")
        enabled = item.get("enabled")
        if (
            not isinstance(provider_id, str)
            or provider_id not in _KNOWN_PROVIDER_IDS
            or provider_id in seen
            or not isinstance(enabled, bool)
        ):
            return safe
        seen.add(provider_id)
        normalized.append({"id": provider_id, "enabled": enabled})

    if seen != _KNOWN_PROVIDER_IDS or normalized[-1]["id"] != MUSICBRAINZ_PROVIDER_ID:
        return safe
    return normalized


def enabled_provider_ids(config):
    """Return enabled IDs in normalized order, including MusicBrainz only if enabled."""
    normalized = normalize_metadata_provider_config(config)
    return [item["id"] for item in normalized if item["enabled"] is True]


def provider_ids_for(config, capability):
    """Return enabled provider IDs that advertise a bounded capability."""
    if not isinstance(capability, str):
        return []
    capabilities = {
        item["id"]: set(item["capabilities"])
        for item in _PROVIDER_DEFINITIONS
    }
    return [
        provider_id
        for provider_id in enabled_provider_ids(config)
        if capability in capabilities.get(provider_id, set())
    ]


__all__ = [
    "DEFAULT_PROVIDER_ORDER",
    "MUSICBRAINZ_PROVIDER_ID",
    "default_metadata_provider_config",
    "enabled_provider_ids",
    "normalize_metadata_provider_config",
    "provider_ids_for",
    "provider_definitions",
]

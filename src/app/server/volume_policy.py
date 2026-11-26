"""Output-volume policy: what each kind of output is allowed to do.

Volumio (`volumecontrol.js`: mixertype None/Software/Hardware plus volumemax and
volumecurvemode) and moOde (`vol.sh`: hardware/software/none "Fixed (0dB)" plus
volume_mpd_max) both model volume as *how* an output attenuates, with "no volume
at all" as one of the choices rather than the absence of a choice. fnAudio had a
flat `mpd_mixer_type` that no UI ever exposed, plus a boolean fallback, which
cannot express "I have hardware volume but I want software" or "0 dB on purpose,
my preamp does it".

This module is the leaf both `config.py` and `services/mpd_service.py` import.
It has to stay import-free: `services/__init__` pulls in MpdService, which needs
the policy, and `config` is imported from there - importing config back from
MpdService is the cycle that made this its own module.
"""

from __future__ import annotations

from typing import Any, Dict

# Each target is a different physical situation, so each gets its own vocabulary:
#   dac      auto | hardware | software | fixed   (MPD -> ALSA hw:)
#   dlna     auto | device | transcode | fixed    (push to another renderer)
#   renderer auto | hardware | software | fixed   (another device pushes here)
VOLUME_TARGET_MODES = {
    "dac": ("auto", "hardware", "software", "fixed"),
    "dlna": ("auto", "device", "transcode", "fixed"),
    "renderer": ("auto", "hardware", "software", "fixed"),
}
DEFAULT_VOLUME_SOFTWARE_FALLBACK = False
DEFAULT_VOLUME_POLICY = {
    "mode": "auto",
    "software_fallback": DEFAULT_VOLUME_SOFTWARE_FALLBACK,
    "max_percent": 100,
    "targets": {"dac": "auto", "dlna": "auto", "renderer": "auto"},
}
# The flat keys that were the only storage before the policy existed.
LEGACY_MIXER_TYPES = ("none", "software", "hardware")


def _token(value, limit: int = 64) -> str:
    """Lower-case a configuration token without stringifying arbitrary objects.

    A hand-edited config can carry any JSON value; `str()` on one that defines a
    hostile ``__str__`` must not be able to raise inside a policy lookup.
    """
    return value.strip().lower()[:limit] if isinstance(value, str) else ""


def normalize_volume_policy(value, legacy_mixer_type=None, legacy_fallback=None) -> Dict[str, Any]:
    """Return a complete, bounded volume policy.

    ``value`` is what the config file carried. A config written before the policy
    existed has no ``volume`` object, so the two flat keys are the only evidence
    of the user's intent and are migrated here.
    """
    policy = {
        "mode": DEFAULT_VOLUME_POLICY["mode"],
        "software_fallback": DEFAULT_VOLUME_SOFTWARE_FALLBACK,
        "max_percent": DEFAULT_VOLUME_POLICY["max_percent"],
        "targets": dict(DEFAULT_VOLUME_POLICY["targets"]),
    }
    if not isinstance(value, dict):
        # `mpd_mixer_type: none` meant "fixed level, do not touch the DAC". The
        # policy keeps that available as `fixed`, but the migrated default is
        # `auto`: both references default to "use the device's own volume when it
        # has one", and with the fallback switch off `auto` still resolves to a
        # fixed level on an output with no control, so nothing audible changes
        # for anyone who never turns the switch on.
        #
        # Anything we cannot read - a non-string, or a string outside the three
        # known values - fails closed to `fixed`: an unreadable setting must not
        # be the thing that switches an attenuation path on.
        if legacy_mixer_type is None:
            legacy = "none"
        elif isinstance(legacy_mixer_type, str):
            legacy = _token(legacy_mixer_type)
        else:
            legacy = ""
        policy["targets"]["dac"] = legacy if legacy in ("software", "hardware") else (
            "auto" if legacy == "none" else "fixed")
        policy["software_fallback"] = legacy_fallback is True
        return policy
    mode = _token(value.get("mode"))
    if mode in {item for modes in VOLUME_TARGET_MODES.values() for item in modes}:
        policy["mode"] = mode
    policy["software_fallback"] = value.get("software_fallback") is True
    try:
        maximum = int(value.get("max_percent"))
    except Exception:
        # A hand-edited file can carry anything here; a bad ceiling must fall
        # back to the default rather than fail the whole load.
        maximum = DEFAULT_VOLUME_POLICY["max_percent"]
    policy["max_percent"] = max(1, min(100, maximum))
    targets = value.get("targets")
    if isinstance(targets, dict):
        for name, allowed in VOLUME_TARGET_MODES.items():
            candidate = _token(targets.get(name))
            if candidate in allowed:
                policy["targets"][name] = candidate
    return policy


def legacy_mixer_type_from_volume(policy) -> str:
    """The `mpd_mixer_type` an older reader expects, derived from the policy."""
    policy = policy if isinstance(policy, dict) else {}
    target = (policy.get("targets") or {}).get("dac") or "auto"
    if target == "software":
        return "software"
    if target == "hardware":
        return "hardware"
    # `auto` and `fixed` both resolve to a fixed level under the legacy model;
    # the difference lives in the keys that model does not have.
    return "none"


def resolve_volume_mode(config, target: str) -> str:
    """One bounded lookup used by every caller: policy first, flat key second."""
    config = config if isinstance(config, dict) else {}
    policy = normalize_volume_policy(
        config.get("volume"),
        config.get("mpd_mixer_type"),
        config.get("volume_software_fallback_enabled"),
    )
    mode = policy["targets"].get(target) or "auto"
    return mode


def software_fallback_enabled(config) -> bool:
    config = config if isinstance(config, dict) else {}
    policy = normalize_volume_policy(
        config.get("volume"),
        config.get("mpd_mixer_type"),
        config.get("volume_software_fallback_enabled"),
    )
    return policy["software_fallback"] is True


__all__ = [
    "DEFAULT_VOLUME_POLICY",
    "DEFAULT_VOLUME_SOFTWARE_FALLBACK",
    "LEGACY_MIXER_TYPES",
    "VOLUME_TARGET_MODES",
    "legacy_mixer_type_from_volume",
    "normalize_volume_policy",
    "resolve_volume_mode",
    "software_fallback_enabled",
]

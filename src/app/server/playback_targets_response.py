"""Pure response assembly for playback target discovery."""

from __future__ import annotations

from summary_values import strict_bool


def compose_playback_targets_response(*, targets, current_target, current_target_name,
                                      plugins, mpd, upmpdcli, airplay, refreshing):
    """Compose the public target payload without probing or mutating state."""
    safe_targets = targets if isinstance(targets, list) else []
    current = current_target if isinstance(current_target, str) else ""
    available = any(
        isinstance(target, dict) and target.get("id") == current
        for target in safe_targets
    )
    return {
        "targets": safe_targets,
        "current_target": current,
        "current_target_name": current_target_name if isinstance(current_target_name, str) else "",
        "current_target_available": available,
        "plugins": plugins if isinstance(plugins, dict) else {},
        "optional_backends": {
            "mpd": mpd if isinstance(mpd, dict) else {},
            "upmpdcli": upmpdcli if isinstance(upmpdcli, dict) else {},
            "airplay": airplay if isinstance(airplay, dict) else {},
        },
        "refreshing": strict_bool(refreshing),
    }

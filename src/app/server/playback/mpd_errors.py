from __future__ import annotations

from typing import Any, Dict


ERROR_DETAILS = {
    "source_missing": ("media", "error", False, "restore_or_rescan_source"),
    "source_corrupt": ("media", "error", False, "verify_or_replace_source"),
    "seek_failed": ("transport", "warning", False, "restart_track_or_verify_source"),
    "decoder_unavailable": ("decoder", "error", False, "install_or_enable_decoder"),
    "decoder_failed": ("decoder", "error", False, "verify_source_and_decoder"),
    "output_device_missing": ("output", "error", True, "reconnect_or_select_output"),
    "output_device_busy": ("output", "warning", True, "release_output_owner_and_retry"),
    "output_format_unsupported": ("output", "error", False, "select_supported_format_or_output"),
    "output_io_failed": ("output", "error", True, "check_output_and_retry"),
    "mixer_unavailable": ("output", "warning", False, "enable_supported_mixer_or_use_fixed_volume"),
    "buffer_underrun": ("output", "warning", True, "check_buffer_and_system_load"),
    "queue_stale": ("queue", "warning", True, "refresh_database_and_queue"),
    "database_unavailable": ("database", "warning", True, "wait_for_database_update"),
    "backend_unavailable": ("backend", "error", True, "restart_backend"),
    "command_failed": ("backend", "error", False, "inspect_backend_error"),
}


def _contains_any(text: str, needles) -> bool:
    return any(needle in text for needle in needles)


def _is_optional_decoder_startup_notice(text: str) -> bool:
    """Ignore known MPD startup notices for decoders fnAudio does not expose."""
    return (
        "wildmidi" in text
        and _contains_any(text, ("unavailable", "not found", "missing"))
        and _contains_any(text, ("configuration file", "timidity", "timidity.cfg"))
    )


def classify_mpd_log_line(message: str) -> Dict[str, Any]:
    line = str(message or "").strip()
    lower = line.casefold()
    if not line:
        return {}
    if _is_optional_decoder_startup_notice(lower):
        return {}

    category = ""
    if _contains_any(lower, ("invalid sync code", "invalid frame header", "lost sync", "frame crc mismatch", "md5 signature mismatch")) or (
        "flac" in lower and _contains_any(lower, ("decoding error", "decode error"))
    ):
        category = "source_corrupt"
    elif _contains_any(lower, ("decoder failed to seek", "failed to seek", "seek failed", "not seekable")):
        category = "seek_failed"
    elif (
        "decoder" in lower
        and _contains_any(lower, ("unavailable", "not available", "not found", "no decoder"))
    ) or ("wildmidi" in lower and _contains_any(lower, ("unavailable", "not found", "missing"))):
        category = "decoder_unavailable"
    elif _contains_any(lower, ("device or resource busy", "audio device is busy", "alsa device is busy")):
        category = "output_device_busy"
    elif _contains_any(
        lower,
        (
            "no such audio device",
            "cannot find card",
            "audio device not found",
            "alsa device not found",
            "selected device is missing",
            "usb dac disconnected",
        ),
    ) or (
        _contains_any(lower, ("no such device", "no such file or directory"))
        and _contains_any(lower, ("alsa", "audio output", "snd_pcm", "failed to open"))
    ):
        category = "output_device_missing"
    elif _contains_any(
        lower,
        (
            "sample format is not supported",
            "sample rate is not supported",
            "unsupported audio format",
            "channels not supported",
            "invalid sample format",
        ),
    ) or ("invalid argument" in lower and _contains_any(lower, ("configure audio output", "set hw params", "snd_pcm_hw_params"))):
        category = "output_format_unsupported"
    elif _contains_any(lower, ("underrun", "buffer xrun", "buffer underflow")):
        category = "buffer_underrun"
    elif _contains_any(
        lower,
        (
            "failed to open audio output",
            "failed to open alsa device",
            "audio output error",
            "alsa error",
            "broken pipe",
            "failed to write to audio output",
        ),
    ):
        category = "output_io_failed"
    elif _contains_any(lower, ("no such song", "directory or file not found", "unknown song")):
        category = "queue_stale"
    elif _contains_any(lower, ("database is not ready", "database update is running", "database is locked")):
        category = "database_unavailable"
    elif _contains_any(lower, ("connection refused", "connection closed", "broken connection", "mpd timed out", "mpd timeout")):
        category = "backend_unavailable"
    elif _contains_any(lower, ("decoder error", "decoding error", "decoding failed", "failed to decode")):
        category = "decoder_failed"
    if not category:
        return {}

    return mpd_error(category, line)


def mpd_error(category: str, message: str) -> Dict[str, Any]:
    category = str(category or "command_failed")
    if category not in ERROR_DETAILS:
        category = "command_failed"
    domain, severity, retryable, action = ERROR_DETAILS[category]
    return {
        "category": category,
        "domain": domain,
        "severity": severity,
        "retryable": retryable,
        "action": action,
        "message": str(message or "").strip(),
    }


def empty_mpd_error_summary() -> Dict[str, Any]:
    return {
        "count": 0,
        "occurrences": 0,
        "items": [],
        "by_category": {},
        "last_category": "",
        "last_domain": "",
        "last_message": "",
        "truncated": False,
    }


def classify_mpd_log_errors(log_text: str, limit: int = 20) -> Dict[str, Any]:
    limit = max(1, min(100, int(limit or 20)))
    lines = str(log_text or "").splitlines()[-max(200, limit * 50):]
    records = {}
    by_category = {}
    occurrences = 0
    for index, raw_line in enumerate(lines):
        item = classify_mpd_log_line(raw_line)
        if not item:
            continue
        occurrences += 1
        category = item["category"]
        by_category[category] = int(by_category.get(category) or 0) + 1
        key = (category, item["message"])
        if key in records:
            records[key]["occurrences"] += 1
            records[key]["_last_index"] = index
        else:
            records[key] = {**item, "occurrences": 1, "_last_index": index}

    ordered = sorted(records.values(), key=lambda item: item["_last_index"])
    selected = ordered[-limit:]
    items = [{key: value for key, value in item.items() if key != "_last_index"} for item in selected]
    result = empty_mpd_error_summary()
    result.update(
        {
            "count": len(items),
            "occurrences": occurrences,
            "items": items,
            "by_category": by_category,
            "truncated": len(ordered) > len(items),
        }
    )
    if items:
        result.update(
            {
                "last_category": items[-1]["category"],
                "last_domain": items[-1]["domain"],
                "last_message": items[-1]["message"],
            }
        )
    return result


def legacy_decoder_error_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    items = [
        dict(item)
        for item in summary.get("items") or []
        if item.get("domain") in ("media", "decoder", "transport")
    ]
    last = items[-1] if items else {}
    return {
        "count": len(items),
        "items": items,
        "last_category": str(last.get("category") or ""),
        "last_message": str(last.get("message") or ""),
    }


def classify_mpd_exception(error: Any) -> Dict[str, Any]:
    message = str(error or "").strip()
    item = classify_mpd_log_line(message)
    if item:
        return item
    return mpd_error("command_failed", message)


__all__ = [
    "classify_mpd_exception",
    "classify_mpd_log_errors",
    "classify_mpd_log_line",
    "empty_mpd_error_summary",
    "legacy_decoder_error_summary",
    "mpd_error",
]

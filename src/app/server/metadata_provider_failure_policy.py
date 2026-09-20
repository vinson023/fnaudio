"""Pure, bounded projections for external metadata provider failures."""

from __future__ import annotations

from typing import Any, Mapping

MAX_PROVIDER_FAILURES = 16
MAX_PROVIDER_NAME = 32
MAX_PROVIDER_ERROR = 240
MAX_PROVIDER_COUNT = 1_000_000
MAX_PROVIDER_COOLDOWN_SECONDS = 60
MAX_PROVIDER_SUCCESS_COUNT = 1_000_000


def _text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.replace("\n", " ").replace("\r", " ").strip()[:limit]


def _number(value: Any, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return 0
    try:
        number = int(float(value))
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(0, min(maximum, number))


def provider_failure_snapshot(source: Any) -> dict[str, dict[str, Any]]:
    """Return an ordered, diagnostic-safe provider failure projection.

    The service keeps the mutable counters and monotonic cooldown clock. This
    helper only limits malformed diagnostic data before it crosses an API/UI
    boundary, so an exception message or a corrupt mapping cannot amplify the
    metadata status response.
    """
    if not isinstance(source, Mapping):
        return {}
    projected: dict[str, dict[str, Any]] = {}
    for raw_name, raw_value in source.items():
        if len(projected) >= MAX_PROVIDER_FAILURES:
            break
        name = _text(raw_name, MAX_PROVIDER_NAME)
        if not name or not isinstance(raw_value, Mapping):
            continue
        count = _number(raw_value.get("count"), MAX_PROVIDER_COUNT)
        if not count:
            continue
        projected[name] = {
            "count": count,
            "last_error": _text(raw_value.get("last_error"), MAX_PROVIDER_ERROR),
            "cooldown_seconds": _number(raw_value.get("cooldown_seconds"), MAX_PROVIDER_COOLDOWN_SECONDS),
        }
    return projected


def provider_activity_snapshot(source: Any) -> dict[str, dict[str, Any]]:
    """Project bounded, non-sensitive provider reachability evidence.

    A successful response does not imply a match exists, but it tells support
    diagnostics that DNS/TLS/request handling reached the provider.  Keep only
    counters and a bounded monotonic-age value: query text, URLs, titles and
    payload data must never cross the status boundary.
    """
    if not isinstance(source, Mapping):
        return {}
    projected: dict[str, dict[str, Any]] = {}
    for raw_name, raw_value in source.items():
        if len(projected) >= MAX_PROVIDER_FAILURES:
            break
        name = _text(raw_name, MAX_PROVIDER_NAME)
        if not name or not isinstance(raw_value, Mapping):
            continue
        successes = _number(raw_value.get("successes"), MAX_PROVIDER_SUCCESS_COUNT)
        empty_results = _number(raw_value.get("empty_results"), MAX_PROVIDER_SUCCESS_COUNT)
        no_valid_candidates = _number(raw_value.get("no_valid_candidates"), MAX_PROVIDER_SUCCESS_COUNT)
        if not successes and not empty_results and not no_valid_candidates:
            continue
        entry = {
            "successes": successes,
            "last_success_seconds_ago": _number(raw_value.get("last_success_seconds_ago"), 3600),
        }
        if empty_results:
            entry["empty_results"] = empty_results
        if no_valid_candidates:
            entry["no_valid_candidates"] = no_valid_candidates
        projected[name] = entry
    return projected


__all__ = [
    "MAX_PROVIDER_FAILURES", "MAX_PROVIDER_NAME", "MAX_PROVIDER_ERROR",
    "MAX_PROVIDER_COUNT", "MAX_PROVIDER_COOLDOWN_SECONDS", "MAX_PROVIDER_SUCCESS_COUNT",
    "provider_activity_snapshot", "provider_failure_snapshot",
]

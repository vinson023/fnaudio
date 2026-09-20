"""Pure projection for the authoritative playback SSE event payload."""

from collections.abc import Mapping

from playback_cue_position import cue_segment_declaration


def playback_event_payload(core: Mapping, requested_target="", item=None):
    """Build a bounded payload in client units without mutating core state.

    ``item`` is the queue mapping of the current track.  The authoritative
    core position is already expressed in the units a client displays, so the
    payload only declares whether those seconds are CUE-segment relative.
    """
    if not isinstance(core, Mapping):
        core = {}
    active_target = core.get("target_id")
    active_target = active_target if isinstance(active_target, str) and active_target else "local"
    if active_target == "browser":
        active_target = "local"
    try:
        raw_state_version = core.get("state_version")
        if isinstance(raw_state_version, bool):
            raise ValueError("boolean state version")
        state_version = max(0, min(int(raw_state_version or 0), 2**31 - 1))
    except (TypeError, ValueError, OverflowError):
        state_version = 0
    try:
        raw_position = core.get("position")
        if isinstance(raw_position, bool):
            raise ValueError("boolean position")
        position = max(0.0, float(raw_position or 0))
        if position != position or position == float("inf"):
            raise ValueError("non-finite position")
    except (TypeError, ValueError, OverflowError):
        position = 0.0
    try:
        raw_duration = core.get("duration")
        if isinstance(raw_duration, bool):
            raise ValueError("boolean duration")
        duration = max(0.0, float(raw_duration or 0))
        if duration != duration or duration == float("inf"):
            raise ValueError("non-finite duration")
    except (TypeError, ValueError, OverflowError):
        duration = 0.0
    requested = requested_target if isinstance(requested_target, str) else ""
    target_kind = core.get("target_kind")
    target_kind = target_kind if isinstance(target_kind, str) and target_kind else "browser"
    transport = core.get("transport")
    transport = transport if isinstance(transport, str) and transport else "STOPPED"
    try:
        raw_generation = core.get("generation")
        if isinstance(raw_generation, bool):
            raise ValueError("boolean generation")
        generation = max(0, min(int(raw_generation or 0), 2**31 - 1))
    except (TypeError, ValueError, OverflowError):
        generation = 0
    try:
        raw_engine_epoch = core.get("engine_epoch")
        if isinstance(raw_engine_epoch, bool):
            raise ValueError("boolean engine epoch")
        engine_epoch = max(0, min(int(raw_engine_epoch or 0), 2**31 - 1))
    except (TypeError, ValueError, OverflowError):
        engine_epoch = 0
    ticket = core.get("command_ticket")
    ticket = ticket[:128] if isinstance(ticket, str) else ""
    return {
        "type": "playback",
        "state_version": state_version,
        "generation": generation,
        "engine_epoch": engine_epoch,
        "command_ticket": ticket,
        "requested_target": requested,
        "target_id": active_target,
        "target_kind": target_kind,
        # Preserve the authoritative snapshot identity for existing consumers;
        # this is a read-only projection and never mutates it.
        "core": core,
        "transport": {"state": transport.upper()},
        "position": {"rel_seconds": position, "duration_seconds": duration},
        "cue_segment": cue_segment_declaration(item),
    }


__all__ = ["playback_event_payload"]

"""Pure latest-wins scheduling policy for renderer backend operations."""

from __future__ import annotations

from dataclasses import dataclass


MAX_BACKEND_COALESCED = 1_000_000_000


@dataclass(frozen=True)
class BackendOperation:
    kind: str
    generation: int
    uri: str = ""
    load_position: float = 0.0
    action: str = ""
    control_position: float | None = None


def schedule_latest(worker_active, pending, coalesced, operation):
    """Return worker state after retaining only the newest valid operation."""
    if not isinstance(operation, BackendOperation):
        return bool(worker_active), pending if isinstance(pending, BackendOperation) else None, max(0, int(coalesced or 0)), False
    try:
        count = max(0, int(coalesced or 0))
    except (TypeError, ValueError, OverflowError):
        count = 0
    current = pending if isinstance(pending, BackendOperation) else None
    if current is not None:
        count = min(MAX_BACKEND_COALESCED, count + 1)
    start_worker = not bool(worker_active)
    return True, operation, count, start_worker


def take_latest(pending):
    """Detach the pending operation; a missing value tells the worker to exit."""
    return pending if isinstance(pending, BackendOperation) else None


__all__ = ["BackendOperation", "MAX_BACKEND_COALESCED", "schedule_latest", "take_latest"]

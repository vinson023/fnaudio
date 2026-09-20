"""Pure state transitions for the bounded library refresh queue."""


def enqueue_refresh(queued, queued_force, worker_active, force=False):
    """Return ``(accepted, start_worker, queued, queued_force, worker_active)``."""
    queued = bool(queued)
    queued_force = bool(queued_force)
    worker_active = bool(worker_active)
    force = bool(force)
    if queued:
        if force and not queued_force:
            return True, False, True, True, worker_active
        return False, False, True, queued_force, worker_active
    return True, not worker_active, True, force, True if not worker_active else worker_active


def take_refresh(queued, queued_force):
    """Consume one queued request and return ``(force, queued, queued_force)``."""
    if not bool(queued):
        return None, False, False
    return bool(queued_force), False, False


def cancel_refresh(running, queued, worker_active=False):
    """Return ``(accepted, queued, queued_force, signal_running)``."""
    running = bool(running)
    queued = bool(queued)
    worker_active = bool(worker_active)
    return running or queued or worker_active, False, False, running

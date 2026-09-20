"""Small, side-effect-free policy helpers for metadata worker lanes."""


def _alive(worker):
    try:
        return worker is not None and bool(worker.is_alive())
    except Exception:
        return False


def _attribute(service, name):
    """Read a service attribute without trusting its implementation."""
    try:
        return getattr(service, name, None)
    except Exception:
        # A failing property on a service double means the lane is unknown,
        # not that the HTTP handler may raise on an interactive request.
        return None


def _worker_list(service, name):
    """Return a worker container as a list, or empty when unusable."""
    workers = _attribute(service, name)
    if workers is None:
        return []
    try:
        return list(workers)
    except TypeError:
        # A non-iterable value (an int left behind by a simplified double, for
        # example) has to report no live lane so the caller runs its lazy
        # worker-recovery path instead of surfacing a 500.
        return []


def lane_workers_alive(service, lane="fetch"):
    if service is None:
        return False
    workers = _worker_list(service, "fetch_threads")
    # An empty pool is not an available lane. Treating it as healthy masks a
    # startup failure and leaves interactive requests pending forever.
    # A partially dead pool still has some capacity, but it is degraded and
    # must trigger the service's serialized slot-recovery path. Reporting it
    # as healthy leaves a permanently reduced worker pool after a crash.
    fetch_alive = bool(workers) and all(_alive(worker) for worker in workers)
    if lane == "lyrics":
        return bool(fetch_alive or _alive(_attribute(service, "priority_thread")))
    return bool(fetch_alive)


def service_was_started(service):
    if service is None:
        return False
    return bool(
        _attribute(service, "fetch_threads")
        or _attribute(service, "priority_thread")
        or _attribute(service, "tag_thread")
    )


__all__ = ["lane_workers_alive", "service_was_started"]

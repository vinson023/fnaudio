"""Pure HTTP request-observation projection for the server handler.

The handler owns clocks and output, while this module owns the bounded,
privacy-safe fields shared by metrics and structured logs.  Keeping that
decision separate prevents request paths from being parsed repeatedly on hot
library and playback endpoints.
"""

import math

from http_request_policy import http_latency_route, request_path, should_write_http_request


def _status_bucket(status):
    """Return the legacy 1xx--5xx bucket without coercing arbitrary input."""
    if isinstance(status, bool) or not isinstance(status, int):
        status = 500
    return max(1, min(5, status // 100))


def _elapsed_seconds(value):
    """Keep request timing finite without invoking custom numeric methods."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    try:
        value = float(value)
    except (OverflowError, TypeError, ValueError):
        return 0.0
    return max(0.0, value) if math.isfinite(value) else 0.0


def observe_http_request(method, path, status, elapsed_seconds):
    """Return the fixed observation contract for one completed HTTP request."""
    route = request_path(path)
    bucket = _status_bucket(status)
    safe_status = status if isinstance(status, int) and not isinstance(status, bool) else 500
    return {
        "route": route,
        "latency_route": http_latency_route(route),
        "status_counter": "http_status_%sxx" % bucket,
        "elapsed_seconds": _elapsed_seconds(elapsed_seconds),
        "write_log": should_write_http_request(method, route, safe_status),
    }


__all__ = ["observe_http_request"]

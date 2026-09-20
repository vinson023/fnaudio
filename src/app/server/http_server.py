"""Bounded HTTP server assembly kept independent from application routing."""

import threading
from http.server import ThreadingHTTPServer

from resource_limits import ConcurrencyGate, bounded_int


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer with admission control before thread creation."""

    daemon_threads = True

    def __init__(self, server_address, request_handler_class, worker_limit=32):
        super().__init__(server_address, request_handler_class)
        self.worker_limit = bounded_int({"limit": worker_limit}, "limit", 32, 4, 128)
        self.worker_gate = ConcurrencyGate("http", max_waiters=0)
        # SSE handlers intentionally hold a request thread while a browser is
        # connected. Reserve most of the finite HTTP pool for short API/media
        # requests so a few idle tabs cannot starve playback controls.
        self.event_stream_limit = max(1, min(self.worker_limit - 1, self.worker_limit // 4))
        self.event_stream_gate = ConcurrencyGate("http-events", max_waiters=0)

    @staticmethod
    def _reject_busy(request):
        body = b'{"ok":false,"error":"server busy"}'
        response = (
            b"HTTP/1.1 503 Service Unavailable\r\n"
            b"Content-Type: application/json; charset=utf-8\r\n"
            b"Retry-After: 1\r\n"
            b"Connection: close\r\n"
            + ("Content-Length: %d\r\n\r\n" % len(body)).encode("ascii")
            + body
        )
        try:
            request.sendall(response)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def process_request(self, request, client_address):
        if not self.worker_gate.try_acquire(self.worker_limit):
            self._reject_busy(request)
            self.shutdown_request(request)
            return
        thread = threading.Thread(
            target=self.process_request_thread,
            args=(request, client_address),
            name="fnaudio-http-worker",
        )
        thread.daemon = self.daemon_threads
        try:
            thread.start()
        except Exception:
            self.worker_gate.release()
            self.shutdown_request(request)
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.worker_gate.release()


__all__ = ["BoundedThreadingHTTPServer"]

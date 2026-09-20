import socket
import unittest

import sys
sys.path.insert(0, "app/server")

from server import BoundedThreadingHTTPServer


class HttpServerLimitTests(unittest.TestCase):
    def test_busy_admission_returns_bounded_503_without_creating_worker(self):
        httpd = BoundedThreadingHTTPServer(("127.0.0.1", 0), object, worker_limit=4)
        peer, request = socket.socketpair()
        try:
            for _ in range(4):
                self.assertTrue(httpd.worker_gate.try_acquire(httpd.worker_limit))
            httpd.process_request(request, ("127.0.0.1", 1))
            response = peer.recv(4096)
            self.assertIn(b"503 Service Unavailable", response)
            self.assertIn(b"Retry-After: 1", response)
            self.assertIn(b'"error":"server busy"', response)
            self.assertEqual(httpd.worker_gate.snapshot()["active"], 4)
        finally:
            for _ in range(4):
                httpd.worker_gate.release()
            peer.close()
            httpd.server_close()

    def test_event_streams_have_a_separate_bounded_share_of_http_workers(self):
        httpd = BoundedThreadingHTTPServer(("127.0.0.1", 0), object, worker_limit=4)
        try:
            self.assertEqual(httpd.event_stream_limit, 1)
            self.assertTrue(httpd.event_stream_gate.try_acquire(httpd.event_stream_limit))
            self.assertFalse(httpd.event_stream_gate.try_acquire(httpd.event_stream_limit))
            self.assertEqual(httpd.event_stream_gate.snapshot()["active"], 1)
            self.assertEqual(httpd.worker_gate.snapshot()["active"], 0)
        finally:
            httpd.event_stream_gate.release()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()

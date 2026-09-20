import io
import os
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, "app/server")

import server
from resource_limits import FFMPEG_GATE, ResourceLimitError


class FakeHandler:
    def __init__(self):
        self.server = SimpleNamespace(config={"ffmpeg_max_concurrency": 1})
        self.wfile = io.BytesIO()
        self.responses = []
        self.headers = {}
        self.response_headers = []
        self.errors = []
        self.close_connection = False

    def send_response(self, status):
        self.responses.append(status)

    def send_header(self, name, value):
        self.response_headers.append((name, value))

    def end_headers(self):
        pass

    def send_error(self, status, message):
        self.errors.append((status, message))


class ServerTranscodeStreamTests(unittest.TestCase):
    def test_file_range_closes_connection_after_a_short_read(self):
        handler = FakeHandler()
        with tempfile.NamedTemporaryFile(delete=False) as fh:
            fh.write(b"abcdef")
            path = fh.name
        try:
            original_open = server.os.open
            original_fstat = server.os.fstat

            def truncate_after_open(target, flags):
                return original_open(target, flags)

            def report_then_truncate(fd):
                result = original_fstat(fd)
                with open(path, "r+b") as writable:
                    writable.truncate(2)
                return result

            with mock.patch.object(server.os, "open", side_effect=truncate_after_open), mock.patch.object(
                server.os, "fstat", side_effect=report_then_truncate
            ):
                server.Handler.serve_file_range(handler, path, "audio/mpeg")

            self.assertEqual(handler.responses, [200])
            self.assertEqual(handler.wfile.getvalue(), b"ab")
            self.assertTrue(handler.close_connection)
        finally:
            os.unlink(path)

    def test_file_range_closes_connection_when_client_rejects_body(self):
        class BrokenClientHandler(FakeHandler):
            def __init__(self):
                super().__init__()
                self.wfile = self

            def write(self, _chunk):
                raise OSError("client transport closed")

        handler = BrokenClientHandler()
        with tempfile.NamedTemporaryFile(delete=False) as fh:
            fh.write(b"abcdef")
            path = fh.name
        try:
            server.Handler.serve_file_range(handler, path, "audio/mpeg")
        finally:
            os.unlink(path)

        self.assertEqual(handler.responses, [200])
        self.assertTrue(handler.close_connection)

    def test_concurrency_rejection_returns_503_before_headers(self):
        handler = FakeHandler()

        @contextmanager
        def rejected_slot(*_args, **_kwargs):
            raise ResourceLimitError("ffmpeg concurrency limit reached")
            yield

        with mock.patch.object(server, "transcode_command", return_value=(["ffmpeg"], "audio/mpeg", {})), mock.patch.object(
            server, "ffmpeg_slot", side_effect=rejected_slot
        ):
            server.Handler.serve_transcoded_media(handler, {"id": "one"}, "mp3")

        self.assertEqual(handler.errors, [(503, "ffmpeg concurrency limit reached")])
        self.assertEqual(handler.responses, [])

    def test_process_start_failure_releases_ffmpeg_slot(self):
        handler = FakeHandler()
        before = FFMPEG_GATE.snapshot()["active"]
        with mock.patch.object(server, "transcode_command", return_value=(["missing-ffmpeg"], "audio/mpeg", {})), mock.patch.object(
            server.subprocess, "Popen", side_effect=OSError("not found")
        ):
            server.Handler.serve_transcoded_media(handler, {"id": "one"}, "mp3")

        self.assertEqual(handler.errors, [(502, "failed to start ffmpeg: not found")])
        self.assertEqual(FFMPEG_GATE.snapshot()["active"], before)
        self.assertEqual(handler.responses, [])

    def test_streaming_process_is_terminated_at_the_shared_task_timeout(self):
        handler = FakeHandler()
        handler.server.config["ffmpeg_job_timeout_seconds"] = 0.1

        class BlockingStream:
            def __init__(self, stopped):
                self.stopped = stopped

            def read(self, _size):
                self.stopped.wait(2)
                return b""

        class FakeProcess:
            def __init__(self):
                self.stopped = threading.Event()
                self.stdout = BlockingStream(self.stopped)
                self.return_code = None

            def poll(self):
                return self.return_code

            def terminate(self):
                self.return_code = -15
                self.stopped.set()

            def wait(self, timeout=None):
                self.stopped.wait(timeout)
                return self.return_code

            def kill(self):
                self.terminate()

        process = FakeProcess()
        started = time.monotonic()
        with mock.patch.object(server, "transcode_command", return_value=(["ffmpeg"], "audio/mpeg", {})), mock.patch.object(
            server.subprocess, "Popen", return_value=process
        ), mock.patch.object(server.os, "name", "nt"):
            server.Handler.serve_transcoded_media(handler, {"id": "one"}, "mp3")

        self.assertTrue(process.stopped.is_set())
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertEqual(handler.responses, [200])
        self.assertIn(("X-fnAudio-Transcode-Timeout", "0.1"), handler.response_headers)

    def test_client_os_error_still_reaps_streaming_process(self):
        class BrokenClientHandler(FakeHandler):
            def __init__(self):
                super().__init__()
                self.wfile = self

            def write(self, _chunk):
                raise OSError("client transport closed")

            def flush(self):
                raise AssertionError("flush must not follow a failed write")

        class FakeProcess:
            def __init__(self):
                self.stdout = io.BytesIO(b"audio")
                self.return_code = None
                self.terminated = False

            def poll(self):
                return self.return_code

            def terminate(self):
                self.terminated = True
                self.return_code = -15

            def wait(self, timeout=None):
                return self.return_code

            def kill(self):
                self.terminate()

        handler = BrokenClientHandler()
        process = FakeProcess()
        with mock.patch.object(server, "transcode_command", return_value=(["ffmpeg"], "audio/mpeg", {})), mock.patch.object(
            server.subprocess, "Popen", return_value=process
        ), mock.patch.object(server.os, "name", "nt"):
            server.Handler.serve_transcoded_media(handler, {"id": "one"}, "mp3")

        self.assertTrue(process.terminated)
        self.assertEqual(handler.responses, [200])

    def test_client_value_error_after_headers_still_reaps_streaming_process(self):
        class BrokenClientHandler(FakeHandler):
            def __init__(self):
                super().__init__()
                self.wfile = self

            def write(self, _chunk):
                raise ValueError("I/O operation on closed file")

            def flush(self):
                raise AssertionError("flush must not follow a failed write")

        class FakeProcess:
            def __init__(self):
                self.stdout = io.BytesIO(b"audio")
                self.return_code = None
                self.terminated = False

            def poll(self):
                return self.return_code

            def terminate(self):
                self.terminated = True
                self.return_code = -15

            def wait(self, timeout=None):
                return self.return_code

            def kill(self):
                self.terminate()

        handler = BrokenClientHandler()
        process = FakeProcess()
        with mock.patch.object(server, "transcode_command", return_value=(["ffmpeg"], "audio/mpeg", {})), mock.patch.object(
            server.subprocess, "Popen", return_value=process
        ), mock.patch.object(server.os, "name", "nt"):
            server.Handler.serve_transcoded_media(handler, {"id": "one"}, "mp3")

        self.assertTrue(process.terminated)
        self.assertEqual(handler.responses, [200])

    def test_cleanup_does_not_raise_after_a_second_reap_timeout(self):
        class ClosingStream(io.BytesIO):
            def __init__(self):
                super().__init__()
                self.closed_by_handler = False

            def close(self):
                self.closed_by_handler = True
                super().close()

        class StubbornProcess:
            def __init__(self):
                self.stdout = ClosingStream()
                self.killed = False

            def poll(self):
                return None

            def terminate(self):
                pass

            def kill(self):
                self.killed = True

            def wait(self, timeout=None):
                raise server.subprocess.TimeoutExpired("ffmpeg", timeout)

        handler = FakeHandler()
        process = StubbornProcess()
        with mock.patch.object(server, "transcode_command", return_value=(["ffmpeg"], "audio/mpeg", {})), mock.patch.object(
            server.subprocess, "Popen", return_value=process
        ), mock.patch.object(server.os, "name", "nt"):
            server.Handler.serve_transcoded_media(handler, {"id": "one"}, "mp3")

        self.assertTrue(process.killed)
        self.assertTrue(process.stdout.closed_by_handler)
        self.assertEqual(handler.responses, [200])

    def test_normal_end_closes_the_ffmpeg_stdout_pipe(self):
        class ClosingStream(io.BytesIO):
            def __init__(self, value):
                super().__init__(value)
                self.closed_by_handler = False

            def close(self):
                self.closed_by_handler = True
                super().close()

        class FakeProcess:
            def __init__(self):
                self.stdout = ClosingStream(b"audio")
                self.return_code = 0
                self.waited = 0

            def poll(self):
                return self.return_code

            def wait(self, timeout=None):
                self.waited += 1
                return self.return_code

        handler = FakeHandler()
        process = FakeProcess()
        with mock.patch.object(server, "transcode_command", return_value=(["ffmpeg"], "audio/mpeg", {})), mock.patch.object(
            server.subprocess, "Popen", return_value=process
        ):
            server.Handler.serve_transcoded_media(handler, {"id": "one"}, "mp3")

        self.assertTrue(process.stdout.closed_by_handler)
        self.assertGreaterEqual(process.waited, 1)
        self.assertEqual(handler.wfile.getvalue(), b"audio")


if __name__ == "__main__":
    unittest.main()

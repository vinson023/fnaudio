import io
import sys
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
        self.headers = []
        self.errors = []

    def send_response(self, status):
        self.responses.append(status)

    def send_header(self, name, value):
        self.headers.append((name, value))

    def end_headers(self):
        pass

    def send_error(self, status, message):
        self.errors.append((status, message))


class ServerTranscodeStreamTests(unittest.TestCase):
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
        handler.server.config["ffmpeg_task_timeout_seconds"] = 0.1

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
        ):
            server.Handler.serve_transcoded_media(handler, {"id": "one"}, "mp3")

        self.assertTrue(process.stopped.is_set())
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertEqual(handler.responses, [200])
        self.assertIn(("X-fnAudio-Transcode-Timeout", "0.1"), handler.headers)


if __name__ == "__main__":
    unittest.main()

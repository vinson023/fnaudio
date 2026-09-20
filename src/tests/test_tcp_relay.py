import asyncio
import importlib.util
from pathlib import Path
import sys
import unittest


_MODULE_PATH = Path(__file__).resolve().parents[2] / "tools" / "tcp_relay.py"
_SPEC = importlib.util.spec_from_file_location("fnaudio_tcp_relay", _MODULE_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)


class _Reader:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def read(self, _size):
        await asyncio.sleep(0)
        if self._chunks:
            return self._chunks.pop(0)
        return b""


class _Writer:
    def __init__(self):
        self.data = []
        self.closed = False
        self.waited = False

    def write(self, data):
        self.data.append(data)

    async def drain(self):
        await asyncio.sleep(0)

    def close(self):
        self.closed = True

    async def wait_closed(self):
        self.waited = True


class TcpRelayTests(unittest.IsolatedAsyncioTestCase):
    async def test_pipe_closes_and_waits_for_writer(self):
        writer = _Writer()
        await _MODULE.pipe(_Reader([b"hello", b""]), writer)
        self.assertEqual(writer.data, [b"hello"])
        self.assertTrue(writer.closed)
        self.assertTrue(writer.waited)

    async def test_relay_cancels_other_direction_after_eof(self):
        client_writer = _Writer()
        remote_writer = _Writer()

        async def open_connection(_host, _port):
            return _Reader([b"remote", b""]), remote_writer

        original = _MODULE.asyncio.open_connection
        _MODULE.asyncio.open_connection = open_connection
        try:
            await _MODULE.relay(_Reader([b"client", b""]), client_writer, "host", 1)
        finally:
            _MODULE.asyncio.open_connection = original

        self.assertEqual(remote_writer.data, [b"client"])
        self.assertTrue(client_writer.closed)
        self.assertTrue(remote_writer.closed)
        self.assertTrue(client_writer.waited)
        self.assertTrue(remote_writer.waited)


if __name__ == "__main__":
    unittest.main()

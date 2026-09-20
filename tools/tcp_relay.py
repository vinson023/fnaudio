#!/usr/bin/env python3
"""Small TCP relay used when an Android emulator lacks the host's IPv6 route."""

import argparse
import asyncio


async def pipe(reader, writer):
    try:
        while data := await reader.read(256 * 1024):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        writer.close()
        wait_closed = getattr(writer, "wait_closed", None)
        if wait_closed is not None:
            try:
                await wait_closed()
            except (ConnectionError, asyncio.CancelledError):
                pass


async def relay(client_reader, client_writer, remote_host, remote_port):
    remote_writer = None
    try:
        remote_reader, remote_writer = await asyncio.open_connection(remote_host, remote_port)
    except OSError:
        client_writer.close()
        wait_closed = getattr(client_writer, "wait_closed", None)
        if wait_closed is not None:
            try:
                await wait_closed()
            except (ConnectionError, asyncio.CancelledError):
                pass
        return
    tasks = {
        asyncio.create_task(pipe(client_reader, remote_writer)),
        asyncio.create_task(pipe(remote_reader, client_writer)),
    }
    try:
        # A relay is finished when either direction reaches EOF.  Cancelling
        # the other direction prevents a peer that never closes from keeping
        # the client connection and task alive indefinitely.
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
    finally:
        for writer in (client_writer, remote_writer):
            if writer is None:
                continue
            writer.close()
            wait_closed = getattr(writer, "wait_closed", None)
            if wait_closed is not None:
                try:
                    await wait_closed()
                except (ConnectionError, asyncio.CancelledError):
                    pass


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, required=True)
    parser.add_argument("--remote-host", required=True)
    parser.add_argument("--remote-port", type=int, required=True)
    args = parser.parse_args()
    server = await asyncio.start_server(
        lambda reader, writer: relay(reader, writer, args.remote_host, args.remote_port),
        args.listen_host,
        args.listen_port,
    )
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())

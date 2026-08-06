#!/usr/bin/env python3
import argparse
import ctypes
import ctypes.util
import os
import sys

SND_PCM_STREAM_PLAYBACK = 0
SND_PCM_ACCESS_RW_INTERLEAVED = 3
SND_PCM_FORMAT_S16_LE = 2
SND_PCM_FORMAT_S24_3LE = 32
SND_PCM_FORMAT_S32_LE = 10
EPIPE = -32

FORMATS = {
    "s16le": (SND_PCM_FORMAT_S16_LE, 2),
    "s24le": (SND_PCM_FORMAT_S24_3LE, 3),
    "s32le": (SND_PCM_FORMAT_S32_LE, 4),
}


def load_alsa():
    for name in (ctypes.util.find_library("asound"), "libasound.so.2", "libasound.so"):
        if not name:
            continue
        try:
            return ctypes.CDLL(name)
        except OSError:
            pass
    raise RuntimeError("libasound was not found")


def check(code, alsa, context):
    if code < 0:
        alsa.snd_strerror.restype = ctypes.c_char_p
        message = alsa.snd_strerror(code)
        raise RuntimeError("%s: %s" % (context, (message or b"unknown").decode("utf-8", "ignore")))
    return code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", required=True)
    parser.add_argument("--rate", type=int, required=True)
    parser.add_argument("--channels", type=int, default=2)
    parser.add_argument("--format", choices=sorted(FORMATS), default="s16le")
    args = parser.parse_args()

    alsa = load_alsa()
    pcm = ctypes.c_void_p()
    fmt, sample_bytes = FORMATS[args.format]
    frame_bytes = max(1, args.channels * sample_bytes)

    check(alsa.snd_pcm_open(ctypes.byref(pcm), args.device.encode("utf-8"), SND_PCM_STREAM_PLAYBACK, 0), alsa, "open")
    try:
        check(
            alsa.snd_pcm_set_params(
                pcm,
                fmt,
                SND_PCM_ACCESS_RW_INTERLEAVED,
                args.channels,
                args.rate,
                1,
                500000,
            ),
            alsa,
            "configure",
        )
        read_size = frame_bytes * 4096
        while True:
            data = os.read(sys.stdin.fileno(), read_size)
            if not data:
                break
            if len(data) % frame_bytes:
                data = data[: len(data) - (len(data) % frame_bytes)]
            if not data:
                continue
            buffer = ctypes.create_string_buffer(data)
            frames = len(data) // frame_bytes
            written = alsa.snd_pcm_writei(pcm, buffer, frames)
            if written == EPIPE:
                alsa.snd_pcm_prepare(pcm)
                written = alsa.snd_pcm_writei(pcm, buffer, frames)
            check(written, alsa, "write")
        alsa.snd_pcm_drain(pcm)
    finally:
        alsa.snd_pcm_close(pcm)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

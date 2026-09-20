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
EINTR = -4
EAGAIN = -11
ESTRPIPE = -102
# Errors that mean "the device is briefly unavailable", not "stop".
RECOVERABLE_ALSA_ERRORS = (EPIPE, EINTR, EAGAIN, ESTRPIPE)
MAX_ALSA_RECOVERY_ATTEMPTS = 8

FORMATS = {
    "s16le": (SND_PCM_FORMAT_S16_LE, 2),
    "s24le": (SND_PCM_FORMAT_S24_3LE, 3),
    "s32le": (SND_PCM_FORMAT_S32_LE, 4),
}

MAX_DEVICE_CHARS = 256
MIN_RATE = 1
MAX_RATE = 768000
MIN_CHANNELS = 1
MAX_CHANNELS = 32


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
        message = alsa.snd_strerror(code)
        if isinstance(message, bytes):
            message = message.decode("utf-8", "ignore")
        raise RuntimeError("%s: %s" % (context, message or "unknown"))
    return code


def recover_alsa_error(alsa, pcm, error):
    """Return True when ALSA cleared a transient xrun, stop or suspend state."""
    recover = getattr(alsa, "snd_pcm_recover", None)
    if recover is not None:
        return recover(pcm, error, 1) == 0
    if error == EPIPE:
        # Older bindings can still take the classic xrun recovery path.
        return alsa.snd_pcm_prepare(pcm) >= 0
    return False


def write_pcm_buffer(alsa, pcm, data, frame_bytes):
    """Write every complete frame, including when ALSA performs a short write."""
    if not data or frame_bytes <= 0:
        return
    buffer = ctypes.create_string_buffer(data)
    total_frames = len(data) // frame_bytes
    offset_frames = 0
    recoveries = 0
    while offset_frames < total_frames:
        offset_bytes = offset_frames * frame_bytes
        remaining_frames = total_frames - offset_frames
        written = alsa.snd_pcm_writei(
            pcm,
            ctypes.byref(buffer, offset_bytes),
            remaining_frames,
        )
        if written > 0:
            recoveries = 0
            offset_frames += written
            continue
        if written == 0:
            raise RuntimeError("write made no progress")
        if written in RECOVERABLE_ALSA_ERRORS and recoveries < MAX_ALSA_RECOVERY_ATTEMPTS:
            recoveries += 1
            if recover_alsa_error(alsa, pcm, written):
                continue
        check(written, alsa, "write")


def iter_pcm_chunks(read, frame_bytes, read_size):
    """Yield frame-aligned audio, carrying a short trailing read forward.

    A pipe hands back whatever the writer happened to flush, so a read is often
    not a whole number of frames. Trimming that tail used to discard the bytes,
    which clicks and slowly loses time; they are prepended to the next read.
    An incomplete frame left at end of stream is dropped because it cannot play.
    """
    if frame_bytes <= 0 or read_size < frame_bytes:
        raise ValueError("read_size must hold at least one audio frame")
    carry = b""
    while True:
        data = read(read_size)
        if not data:
            return
        if carry:
            data = carry + data
            carry = b""
        remainder = len(data) % frame_bytes
        if remainder:
            carry = data[len(data) - remainder:]
            data = data[: len(data) - remainder]
        if data:
            yield data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", required=True)
    parser.add_argument("--rate", type=int, required=True)
    parser.add_argument("--channels", type=int, default=2)
    parser.add_argument("--format", choices=sorted(FORMATS), default="s16le")
    args = parser.parse_args()

    if not isinstance(args.device, str) or not args.device or len(args.device) > MAX_DEVICE_CHARS:
        parser.error("--device is empty or too long")
    if not MIN_RATE <= args.rate <= MAX_RATE:
        parser.error("--rate is outside the supported range")
    if not MIN_CHANNELS <= args.channels <= MAX_CHANNELS:
        parser.error("--channels is outside the supported range")

    alsa = load_alsa()
    alsa.snd_pcm_writei.restype = ctypes.c_long
    alsa.snd_pcm_prepare.restype = ctypes.c_int
    alsa.snd_strerror.restype = ctypes.c_char_p
    recover = getattr(alsa, "snd_pcm_recover", None)
    if recover is not None:
        recover.restype = ctypes.c_int
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
        for chunk in iter_pcm_chunks(
            lambda size: os.read(sys.stdin.fileno(), size),
            frame_bytes,
            read_size,
        ):
            write_pcm_buffer(alsa, pcm, chunk, frame_bytes)
        alsa.snd_pcm_drain(pcm)
    finally:
        alsa.snd_pcm_close(pcm)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

"""Tell "this file cannot be decoded" apart from "try again in a moment".

R598.  ``transcode.py`` used to raise a bare ``RuntimeError`` with ffmpeg's stderr
tail for every failure, so the caller could not distinguish three very different
situations:

* **this file** is not decodable (permanent -- retrying is pure waste),
* **this box** is out of something (no ffmpeg, no disk, no free worker slot),
* **this moment** was unlucky (a timeout, a transient I/O error).

The client used to treat all of them the same way: remember the track as
"unplayable" and skip it.  That is right for the first case and wrong for the
other two -- a full cache volume or a busy worker lane would permanently blacklist
a perfectly good file, and a missing ffmpeg would silently skip through the queue
instead of telling the reader what is actually broken.

Only ``unsupported_format`` is permanent.  Everything else describes the machine,
not the file, so the caller may retry and must not blacklist.

R599 pulled one code back out of ``unsupported_format``: ffmpeg's "no decoder for
this codec" wording describes the **build**, not the bytes.  ``find_ffmpeg``
resolves ffmpeg from config and from PATH, so a fuller build is one user-side
change away -- reading that as a broken file told the reader to delete a good file
*and* left a permanent marker that a new ffmpeg could not clear.

When a wording is ambiguous the machine bucket wins.  "Your file is broken" makes
people throw away a good file; "install a fuller ffmpeg" costs them a minute.
"""

from __future__ import annotations

CODE_UNSUPPORTED_FORMAT = "unsupported_format"
CODE_DECODER_UNAVAILABLE = "decoder_unavailable"
CODE_SOURCE_MISSING = "source_missing"
CODE_FFMPEG_MISSING = "ffmpeg_missing"
CODE_TIMEOUT = "timeout"
CODE_BUSY = "busy"
CODE_DIAGNOSTIC_TOO_LARGE = "diagnostic_too_large"
CODE_DISK_FULL = "disk_full"
CODE_START_FAILED = "start_failed"
CODE_PUBLISH_FAILED = "publish_failed"
CODE_FAILED = "transcode_failed"

# One entry, on purpose.  A source that disappeared may come back (an SMB share
# dropping for a second must not condemn the file), ffmpeg may be installed, the
# disk may be freed.  "The decoder cannot read these bytes" is the only verdict
# that stays true no matter when it is retried.
PERMANENT_CODES = frozenset({CODE_UNSUPPORTED_FORMAT})

# "This build has no decoder for that codec."  True for the bytes, but the wrong
# party to blame: ``find_ffmpeg`` picks ffmpeg from config and PATH, so replacing
# the binary fixes it.  Kept out of ``PERMANENT_CODES`` so no marker is written --
# a marker would outlive the upgrade that fixes the file.
_DECODER_MARKERS = (
    "unsupported codec",
    "unsupported audio codec",
    "unknown decoder",
    "no decoder found",
    "decoder not found",
    "not found for input stream",
    "protocol not found",
)

# Checked before the permanent markers: "no space left" can make ffmpeg print
# "Output file does not contain any stream", which would otherwise read as a
# format problem.
_TRANSIENT_MARKERS = (
    "no space left on device",
    "cannot allocate memory",
    "resource temporarily unavailable",
    "input/output error",
    "too many open files",
    "connection reset by peer",
    "temporary failure in name resolution",
)

# ffmpeg's wording for "the bytes are not what the container/decoder expects".
# Kept deliberately narrow: a false positive blacklists a good file forever, so
# anything that could also mean "this build lacks the codec" lives above instead.
_PERMANENT_MARKERS = (
    "invalid data found when processing input",
    "could not find codec parameters",
    "matches no streams",
    "does not contain any stream",
    "moov atom not found",
    "invalid frame size",
)

# What the reader is told.  One sentence each, no stack traces: the point of the
# classification is that these are different sentences.
_MESSAGES = {
    CODE_UNSUPPORTED_FORMAT: "这个文件的格式无法解码，已跳过",
    CODE_DECODER_UNAVAILABLE: "本机 ffmpeg 缺少这个格式的解码器，换个更完整的 ffmpeg 后可重试",
    CODE_SOURCE_MISSING: "源文件暂时读不到，稍后可以重试",
    CODE_FFMPEG_MISSING: "本机没有可用的 ffmpeg，转码播放不可用",
    CODE_TIMEOUT: "转码超时，稍后可以重试",
    CODE_BUSY: "转码任务排队已满，稍后可以重试",
    CODE_DIAGNOSTIC_TOO_LARGE: "转码诊断输出超出上限，稍后可以重试",
    CODE_DISK_FULL: "转码缓存空间不足，请清理后重试",
    CODE_START_FAILED: "转码进程启动失败，稍后可以重试",
    CODE_PUBLISH_FAILED: "转码结果写入失败，稍后可以重试",
    CODE_FAILED: "转码失败，稍后可以重试",
}

MAX_DETAIL_CHARS = 300


def classify_ffmpeg_detail(detail):
    """Return the code for one ffmpeg stderr tail.

    Three passes, in this order:

    1. transient markers -- "no space left on device" also produces "Output file
       does not contain any stream", and reading that as a format problem would
       blacklist the file;
    2. decoder markers -- the build is missing a codec, which is fixable on the
       machine and must not be recorded against the file;
    3. file markers -- the bytes really are not decodable.
    """
    text = detail if isinstance(detail, str) else ""
    lowered = text[:MAX_DETAIL_CHARS].lower()
    for marker in _TRANSIENT_MARKERS:
        if marker in lowered:
            return CODE_DISK_FULL if marker == "no space left on device" else CODE_FAILED
    for marker in _DECODER_MARKERS:
        if marker in lowered:
            return CODE_DECODER_UNAVAILABLE
    for marker in _PERMANENT_MARKERS:
        if marker in lowered:
            return CODE_UNSUPPORTED_FORMAT
    return CODE_FAILED


def is_permanent(code):
    """True only for "retrying this file will never help"."""
    return code in PERMANENT_CODES


def http_status(code):
    """415 for a file the server will never transcode, 503 for a bad moment.

    The status is not what the browser reports to the page (an ``<audio>`` error
    carries no body and no status), but it is what ``curl``, the DLNA push path
    and the log see -- and it is the difference between "unsupported media" and
    "service unavailable" for anything reading the response.
    """
    return 415 if is_permanent(code) else 503


def public_message(code):
    return _MESSAGES.get(code, _MESSAGES[CODE_FAILED])


__all__ = [
    "CODE_BUSY",
    "CODE_DECODER_UNAVAILABLE",
    "CODE_DIAGNOSTIC_TOO_LARGE",
    "CODE_DISK_FULL",
    "CODE_FAILED",
    "CODE_FFMPEG_MISSING",
    "CODE_PUBLISH_FAILED",
    "CODE_SOURCE_MISSING",
    "CODE_START_FAILED",
    "CODE_TIMEOUT",
    "CODE_UNSUPPORTED_FORMAT",
    "PERMANENT_CODES",
    "classify_ffmpeg_detail",
    "http_status",
    "is_permanent",
    "public_message",
]

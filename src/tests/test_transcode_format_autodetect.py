"""Formats with no decoder on the other side convert themselves.

WMA used to play only if the user turned the global MP3 switch on - and that
switch re-encoded FLAC and MP3 as well, which is why "开启转码后点下一首很慢".
The server now decides per file: known-playable formats go out untouched, the
rest are converted. Reported 2026-11-16.
"""

import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, "app/server")
import transcode  # noqa: E402


class Request:
    def __init__(self, ip="192.168.5.30", host="nas:53199"):
        self.client_address = (ip, 50000)
        self.headers = {"Host": host}


def item(path, *, dsd=False, cue=False, duration=180.0):
    return {"path": path, "is_dsd": dsd, "cue_track": cue, "duration": duration, "mime": "audio/x"}


class FormatAutodetectTests(unittest.TestCase):
    def mode(self, path, query=None, **kwargs):
        return transcode.media_mode(item(path, **kwargs), query or {}, Request())

    def test_formats_the_client_cannot_decode_are_converted(self):
        for path in ("a/x.wma", "a/x.aiff", "a/x.aif", "a/x.wv", "a/x.mpc"):
            with self.subTest(path=path):
                self.assertEqual(self.mode(path), "mp3", path + " has no browser decoder")

    def test_formats_the_client_can_decode_are_left_alone(self):
        for path in ("a/x.mp3", "a/x.flac", "a/x.m4a", "a/x.aac", "a/x.ogg", "a/x.opus", "a/x.wav"):
            with self.subTest(path=path):
                self.assertEqual(self.mode(path), "original", path + " plays as-is")

    def test_lossless_lanes_keep_their_own_target(self):
        self.assertEqual(self.mode("a/x.ape"), "ape_flac")
        self.assertEqual(self.mode("a/x.dsf", dsd=True), "dsd_wav")
        self.assertEqual(self.mode("a/x.flac", cue=True), "cue_flac")

    def test_explicit_requests_still_win(self):
        # A caller that asks for the original file (DLNA, the TV client) must not
        # be overruled by the format rule.
        self.assertEqual(self.mode("a/x.wma", {"transcode": ["original"]}), "original")
        self.assertEqual(self.mode("a/x.wma", {"transcode": ["upnp"]}), "original")
        self.assertEqual(self.mode("a/x.flac", {"transcode": ["mp3"]}), "mp3")

    def test_wan_profile_keeps_its_blanket_conversion(self):
        request = Request(ip="8.8.8.8", host="public.example")
        self.assertEqual(
            transcode.media_mode(item("a/x.flac"), {}, request), "mp3",
            "a public client still gets MP3 regardless of format",
        )


if __name__ == "__main__":
    unittest.main()

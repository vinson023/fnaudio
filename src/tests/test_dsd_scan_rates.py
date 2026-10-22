"""Exercise real container reads, scanning and SQLite persistence of DSD rates."""

import os
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "app/server")
import library


def write_dsd_fixture(path, rate, bit_order=1):
    """Two-channel, eight-sample payload; all expectations use literal rates."""
    if path.endswith(".dsf"):
        fmt = b"fmt " + struct.pack("<Q6IQ2I", 52, 1, 0, 2, 2, rate, bit_order, 8, 4096, 0)
        data = b"data" + struct.pack("<Q", 14) + b"\x69\x96"
        body = fmt + data
        header = b"DSD " + struct.pack("<QQQ", 28, 28 + len(body), 0)
        content = header + body
    else:
        def chunk(name, body):
            return name + struct.pack(">Q", len(body)) + body + (b"\0" if len(body) % 2 else b"")
        props = b"SND " + chunk(b"FS  ", struct.pack(">I", rate)) + chunk(b"CHNL", struct.pack(">H", 2) + b"SLFTSRGT")
        body = b"DSD " + chunk(b"PROP", props) + chunk(b"DSD ", b"\x69\x96")
        content = b"FRM8" + struct.pack(">Q", len(body)) + body
    with open(path, "wb") as handle:
        handle.write(content)


class DsdScanRateTests(unittest.TestCase):
    def test_all_four_rates_survive_probe_scan_sqlite_and_old_cache_reuse(self):
        # Reintroducing native-as-fallback-only, DSF /8 rates, or reuse of v16
        # cache records must fail the public SQLite query assertions below.
        for ext in ("dsf", "dff"):
            for rate in (2822400, 5644800, 11289600, 22579200):
                with self.subTest(ext=ext, rate=rate), tempfile.TemporaryDirectory() as root:
                    music = os.path.join(root, "music")
                    os.mkdir(music)
                    path = os.path.join(music, "fixture." + ext)
                    write_dsd_fixture(path, rate)
                    stat = os.stat(path)
                    old = {"id": "old", "path": path, "size": stat.st_size,
                           "modified_ns": stat.st_mtime_ns, "metadata_version": 16,
                           "is_dsd": True, "sample_rate": rate // 8, "bit_depth": 8}
                    config = {"library_paths": [music], "cache_dir": os.path.join(root, "cache")}
                    payload = ('{"streams":[{"sample_rate":"%d","bits_per_sample":8}],'
                               '"format":{"tags":{"title":"Fixture"}}}' % (rate // 8)).encode()
                    with patch.object(library, "find_ffprobe", return_value="ffprobe"), \
                         patch("probe_runner.subprocess.run", return_value=type("Result", (), {"stdout": payload})()):
                        items, signature = library.scan_library(music, [old], config)
                    self.assertEqual(items[0]["sample_rate"], rate)
                    self.assertEqual(items[0]["bit_depth"], 1)
                    self.assertEqual(items[0]["title"], "Fixture")
                    self.assertTrue(library.save_library_cache(config, items, signature))
                    saved = library.query_library_page(config, {"view": ["dsd"], "limit": ["10"]})
                    self.assertEqual(saved["count"], 1)
                    self.assertEqual(saved["items"][0]["sample_rate"], rate)
                    self.assertEqual(saved["items"][0]["bit_depth"], 1)

    def test_dsf_bit_order_eight_still_describes_one_bit_audio(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "msb.dsf")
            write_dsd_fixture(path, 5644800, bit_order=8)
            info = library.read_native_audio_info(path)
            self.assertEqual(info["sample_rate"], 5644800)
            self.assertEqual(info["bit_depth"], 1)

    def test_dsf_invalid_or_truncated_header_does_not_fabricate_audio_facts(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "bad.dsf")
            for body in (b"DSD ", b"DSD " + b"\0" * 80):
                with open(path, "wb") as handle:
                    handle.write(body)
                self.assertEqual(library.read_native_audio_info(path), {})


if __name__ == "__main__":
    unittest.main()

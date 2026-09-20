import os
import tempfile
import unittest

from sidecar_cover import MAX_SIDECAR_BYTES, read_sidecar_cover


class SidecarCoverTests(unittest.TestCase):
    def test_oversized_replaced_sidecar_is_rejected_after_bounded_read(self):
        with tempfile.TemporaryDirectory() as root:
            target = os.path.join(root, "cover.jpg")
            with open(target, "wb") as handle:
                handle.write(b"x" * (MAX_SIDECAR_BYTES + 1))
            mime, body = read_sidecar_cover(os.path.join(root, "track.flac"))
            self.assertIsNone(mime)
            self.assertIsNone(body)

    def test_small_sidecar_is_returned(self):
        with tempfile.TemporaryDirectory() as root:
            target = os.path.join(root, "folder.jpg")
            with open(target, "wb") as handle:
                handle.write(b"jpeg")
            mime, body = read_sidecar_cover(os.path.join(root, "track.flac"))
            self.assertEqual("image/jpeg", mime)
            self.assertEqual(b"jpeg", body)

    def test_common_front_artwork_name_is_returned(self):
        with tempfile.TemporaryDirectory() as root:
            target = os.path.join(root, "front.webp")
            with open(target, "wb") as handle:
                handle.write(b"webp")
            mime, body = read_sidecar_cover(os.path.join(root, "track.flac"))
            self.assertEqual("image/webp", mime)
            self.assertEqual(b"webp", body)


if __name__ == "__main__":
    unittest.main()

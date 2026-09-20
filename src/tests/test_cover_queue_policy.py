import sys
import unittest

sys.path.insert(0, "app/server")

from cover_queue_policy import MAX_QUEUE_IDENTITY_CHARS, _text, item_identity, queue_key


class CoverQueuePolicyTests(unittest.TestCase):
    def test_prefers_track_id_then_path_without_object_coercion(self):
        class Exploding:
            def __str__(self):
                raise AssertionError("queue identity must not stringify objects")

        self.assertEqual(item_identity({"id": "track-1", "path": "/music/a.flac"}), "track-1")
        self.assertEqual(item_identity({"id": Exploding(), "path": "/music/a.flac"}), "/music/a.flac")
        self.assertEqual(item_identity({"id": Exploding(), "path": Exploding()}), "")

    def test_library_identity_prefers_path_to_preserve_scanner_semantics(self):
        item = {"id": "shared-scanner-id", "path": "/music/a.flac"}
        self.assertEqual(item_identity(item, prefer_path=True), "/music/a.flac")
        self.assertEqual(queue_key(item, "v1", 160, prefer_path=True)[0], "/music/a.flac")

    def test_queue_key_is_bounded_and_normalizes_size(self):
        key = queue_key({"id": "x" * (MAX_QUEUE_IDENTITY_CHARS + 10)}, "v" * 500, 9999)
        self.assertEqual(len(key[0]), MAX_QUEUE_IDENTITY_CHARS)
        self.assertEqual(len(key[1]), 128)
        self.assertEqual(key[2], 512)
        self.assertEqual(queue_key({"id": "track"}, "v1", 1.5)[2], 0)

    def test_malformed_text_limit_falls_back_without_custom_conversion(self):
        class Exploding:
            def __int__(self):
                raise AssertionError("text limit must not invoke custom conversion")

        value = "abcdef"
        self.assertEqual(item_identity({"id": value}), value)
        self.assertEqual(_text(value, Exploding()), value)


if __name__ == "__main__":
    unittest.main()

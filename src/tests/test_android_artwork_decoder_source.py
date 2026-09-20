import pathlib
import unittest


class AndroidArtworkDecoderSourceTests(unittest.TestCase):
    def test_decoder_converts_bitmap_oom_into_a_bounded_decode_miss(self):
        path = pathlib.Path(__file__).parents[2] / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "ArtworkBitmapDecoder.java"
        source = path.read_text(encoding="utf-8")
        self.assertIn("catch (OutOfMemoryError error)", source)
        self.assertIn("return null;", source)

    def test_bitmap_loader_decode_entrypoint_uses_the_bounded_decoder(self):
        path = pathlib.Path(__file__).parents[2] / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "AuthenticatedBitmapLoader.java"
        source = path.read_text(encoding="utf-8")
        method = source[source.index("public ListenableFuture<Bitmap> decodeBitmap") : source.index("public ListenableFuture<Bitmap> loadBitmap")]
        self.assertIn("MAX_ARTWORK_BYTES", method)
        self.assertIn("ArtworkBitmapDecoder.decode(data)", method)
        self.assertNotIn("fallbackLoader.decodeBitmap(data)", method)

    def test_bitmap_cache_replacement_never_writes_directly_to_live_entry(self):
        root = pathlib.Path(__file__).parents[2]
        path = root / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "AuthenticatedBitmapLoader.java"
        source = path.read_text(encoding="utf-8")
        write_method = source[source.index("private void writeCached") : source.index("private File cacheFile")]
        self.assertIn("temporary.renameTo(target)", write_method)
        self.assertNotIn("new FileOutputStream(target)", write_method)
        self.assertIn("Never fall back to writing the target directly", write_method)


if __name__ == "__main__":
    unittest.main()

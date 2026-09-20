import unittest

from app.server.metadata_han_variant import fold_han_variants


class MetadataHanVariantTests(unittest.TestCase):
    def test_folds_common_traditional_characters_for_lookup(self):
        self.assertEqual(fold_han_variants("分手說愛你 / 陳芳語"), "分手说爱你 / 陈芳语")

    def test_non_text_is_rejected_and_input_is_bounded(self):
        self.assertEqual(fold_han_variants(None), "")
        self.assertEqual(len(fold_han_variants("說" * 5000)), 1024)


if __name__ == "__main__":
    unittest.main()

import sys
import unittest

sys.path.insert(0, "app/server")

from metadata_provider_routing_policy import contains_cjk


class MetadataProviderRoutingPolicyTests(unittest.TestCase):
    def test_detects_cjk_in_bounded_text(self):
        self.assertTrue(contains_cjk("Album", "中文歌手"))
        self.assertFalse(contains_cjk("Album", "Artist"))

    def test_rejects_non_text_without_stringifying(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("must not stringify")

        self.assertFalse(contains_cjk(Explosive(), None, 42))


if __name__ == "__main__":
    unittest.main()

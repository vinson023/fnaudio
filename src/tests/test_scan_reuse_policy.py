import unittest

from scan_reuse_policy import can_reuse_cached_item


class ScanReusePolicyTests(unittest.TestCase):
    def test_reuse_requires_all_identity_fields(self):
        item = {"size": 12, "modified_ns": 34, "metadata_version": 16}
        self.assertTrue(can_reuse_cached_item(item, 12, 34, 16))
        self.assertFalse(can_reuse_cached_item(item, 13, 34, 16))
        self.assertFalse(can_reuse_cached_item(item, 12, 35, 16))
        self.assertFalse(can_reuse_cached_item(item, 12, 34, 17))

    def test_reuse_rejects_missing_or_non_mapping_cache_entry(self):
        self.assertFalse(can_reuse_cached_item(None, 1, 2, 3))
        self.assertFalse(can_reuse_cached_item({"size": 1}, 1, 2, 3))

if __name__ == "__main__":
    unittest.main()

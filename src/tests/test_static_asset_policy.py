import unittest

from static_asset_policy import (
    MAX_STATIC_ASSET_BYTES,
    STATIC_ASSET_IMMUTABLE_MAX_AGE,
    static_asset_cache_control,
    static_asset_etag,
    static_asset_etag_matches,
    static_asset_size_allowed,
)


class StaticAssetPolicyTests(unittest.TestCase):
    def test_accepts_sizes_inside_inclusive_limit(self):
        self.assertTrue(static_asset_size_allowed(0))
        self.assertTrue(static_asset_size_allowed(MAX_STATIC_ASSET_BYTES))

    def test_rejects_oversized_and_untrusted_values(self):
        self.assertFalse(static_asset_size_allowed(MAX_STATIC_ASSET_BYTES + 1))
        self.assertFalse(static_asset_size_allowed(True))
        self.assertFalse(static_asset_size_allowed("10"))
        self.assertFalse(static_asset_size_allowed(10, limit=False))

    def test_versioned_ui_assets_are_immutable_but_html_revalidates(self):
        self.assertEqual(
            static_asset_cache_control("app.js", versioned=True),
            "public, max-age=%s, immutable" % STATIC_ASSET_IMMUTABLE_MAX_AGE,
        )
        self.assertEqual(static_asset_cache_control("app.js"), "no-cache")
        self.assertEqual(static_asset_cache_control("index.html", versioned=True), "no-cache")

    def test_weak_etag_uses_stat_values_and_honors_standard_conditional_forms(self):
        etag = static_asset_etag(42, 123456789)
        self.assertEqual(etag, 'W/"static-75bcd15-2a"')
        self.assertTrue(static_asset_etag_matches(etag, etag))
        self.assertTrue(static_asset_etag_matches('"static-75bcd15-2a", "other"', etag))
        self.assertTrue(static_asset_etag_matches("*", etag))
        self.assertFalse(static_asset_etag_matches('"other"', etag))
        self.assertIsNone(static_asset_etag(-1, 1))
        self.assertIsNone(static_asset_etag(1, False))


if __name__ == "__main__":
    unittest.main()

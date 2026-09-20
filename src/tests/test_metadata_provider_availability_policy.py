import unittest

from app.server.metadata_provider_availability_policy import provider_is_available


class MetadataProviderAvailabilityPolicyTests(unittest.TestCase):
    def test_allows_provider_without_cooldown_or_deadline(self):
        self.assertTrue(provider_is_available(0.0, None, 100.0))

    def test_rejects_cooled_and_expired_sources(self):
        self.assertFalse(provider_is_available(101.0, None, 100.0))
        self.assertFalse(provider_is_available(0.0, 100.0, 100.0))

    def test_malformed_monotonic_values_fail_closed(self):
        self.assertFalse(provider_is_available(object(), None, 100.0))
        self.assertFalse(provider_is_available(0.0, object(), 100.0))
        self.assertFalse(provider_is_available(0.0, None, float("nan")))


if __name__ == "__main__":
    unittest.main()

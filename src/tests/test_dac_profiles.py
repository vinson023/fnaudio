import sys
import unittest

sys.path.insert(0, "app/server")

from services.dac_profiles import MAX_CUSTOM_PROFILES, bounded_custom_profiles, dac_quirk_profile


class DacProfileTests(unittest.TestCase):
    def test_bounded_custom_profiles_copies_only_mapping_entries(self):
        source = [{"name": "one"}, object(), {"name": "two"}]
        result = bounded_custom_profiles(source)
        self.assertEqual(result, [{"name": "one"}, {"name": "two"}])
        self.assertIsNot(result[0], source[0])

    def test_custom_profile_iterator_is_bounded_and_ignores_non_mappings(self):
        class ProfileStream:
            def __init__(self):
                self.reads = 0
            def __iter__(self):
                return self
            def __next__(self):
                self.reads += 1
                if self.reads > MAX_CUSTOM_PROFILES:
                    raise AssertionError("profile iterator exceeded configured bound")
                return object()

        stream = ProfileStream()
        profile = dac_quirk_profile({}, stream)
        self.assertEqual(profile["name"], "default")
        self.assertEqual(stream.reads, MAX_CUSTOM_PROFILES)

    def test_custom_usb_profile_overrides_buffer_and_dsd_mode(self):
        profile = dac_quirk_profile(
            {"usb_vendor_id": "1234", "usb_product_id": "abcd", "stable_id": "usb:x"},
            [
                {
                    "name": "slow-locking-dac",
                    "match": {"vendor_id": "1234", "product_id": "ABCD"},
                    "settings": {
                        "audio_buffer_size": "16M",
                        "startup_delay_ms": 750,
                        "force_dop": True,
                    },
                }
            ],
        )

        self.assertEqual(profile["name"], "slow-locking-dac")
        self.assertEqual(profile["audio_buffer_size"], "16M")
        self.assertEqual(profile["startup_delay_ms"], 750)
        self.assertTrue(profile["force_dop"])

    def test_invalid_delay_values_do_not_break_profile_selection(self):
        profile = dac_quirk_profile(
            {},
            [{"settings": {"startup_delay_ms": float("inf"), "track_settle_ms": True}}],
        )
        self.assertEqual(profile["startup_delay_ms"], 0)
        self.assertEqual(profile["track_settle_ms"], 0)

    def test_malformed_profile_sections_are_ignored_without_coercion(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("DAC profile values must not be stringified")

        profile = dac_quirk_profile(
            {"stable_id": Explosive(), "usb_vendor_id": Explosive()},
            [{"name": Explosive(), "match": ["not", "a mapping"], "settings": ["not", "a mapping"]}],
        )

        self.assertEqual(profile["name"], "custom")
        self.assertEqual(profile["keepalive_mode"], "off")

    def test_profile_settings_require_expected_boolean_and_buffer_types(self):
        profile = dac_quirk_profile(
            {},
            [{"settings": {
                "force_dop": "false",
                "disable_native_dsd": 1,
                "audio_buffer_size": "not-an-mpd-buffer",
            }}],
        )

        self.assertFalse(profile["force_dop"])
        self.assertFalse(profile["disable_native_dsd"])
        self.assertEqual(profile["audio_buffer_size"], "8M")

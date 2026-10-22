import copy
import sys
import unittest

sys.path.insert(0, "app/server")

from metadata_provider_config import (
    DEFAULT_PROVIDER_ORDER,
    MUSICBRAINZ_PROVIDER_ID,
    default_metadata_provider_config,
    enabled_provider_ids,
    normalize_metadata_provider_config,
    provider_ids_for,
    provider_definitions,
)


class MetadataProviderConfigTests(unittest.TestCase):
    def test_missing_config_returns_safe_recommended_configuration(self):
        config = default_metadata_provider_config()

        self.assertEqual(
            [entry["id"] for entry in config],
            ["netease", "kuwo", "kugou", "migu", "joox", "musicbrainz"],
        )
        self.assertEqual(
            enabled_provider_ids(config),
            ["netease", "kuwo", "kugou", "migu", "joox", "musicbrainz"],
        )
        self.assertEqual(config[-1]["id"], MUSICBRAINZ_PROVIDER_ID)

    def test_valid_full_configuration_preserves_enabled_flags_and_order(self):
        raw = [
            {"id": "kugou", "enabled": False},
            {"id": "netease", "enabled": True},
            {"id": "kuwo", "enabled": False},
            {"id": "migu", "enabled": True},
            {"id": "joox", "enabled": False},
            {"id": "musicbrainz", "enabled": True},
        ]

        normalized = normalize_metadata_provider_config(raw)

        self.assertEqual([entry["id"] for entry in normalized], [entry["id"] for entry in raw])
        self.assertEqual(enabled_provider_ids(normalized), ["netease", "migu", "musicbrainz"])
        self.assertEqual(normalized[-1]["id"], MUSICBRAINZ_PROVIDER_ID)
        self.assertIsNot(normalized, raw)

    def test_unknown_duplicate_or_misplaced_musicbrainz_falls_back_safely(self):
        safe = default_metadata_provider_config()
        cases = [
            safe[:-1],
            safe + [{"id": "netease", "enabled": True}],
            [*safe[:2], {"id": "unknown", "enabled": True}, *safe[2:]],
            [{"id": "musicbrainz", "enabled": True}, *safe[:-1]],
            [*safe[:-1], {"id": "qq", "enabled": False}, safe[-1]],
            [*safe[:-1], {"id": "qianqian", "enabled": False}, safe[-1]],
            [{"id": entry["id"], "enabled": "yes"} for entry in safe],
        ]

        for raw in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_metadata_provider_config(raw), safe)

    def test_normalization_does_not_mutate_input_or_expose_definition_state(self):
        raw = default_metadata_provider_config()
        before = copy.deepcopy(raw)

        normalized = normalize_metadata_provider_config(raw)
        definitions = provider_definitions()
        definitions[0]["name"] = "tampered"

        self.assertEqual(raw, before)
        self.assertEqual(provider_definitions()[0]["name"], "网易云音乐")
        self.assertIsNot(normalized[0], raw[0])

    def test_provider_ids_for_filters_capability_without_changing_order(self):
        config = default_metadata_provider_config()

        self.assertEqual(
            provider_ids_for(config, "lyrics"),
            ["netease", "kuwo", "kugou", "migu", "joox"],
        )
        self.assertEqual(
            provider_ids_for(config, "cover"),
            ["netease", "kuwo", "kugou", "migu", "joox", "musicbrainz"],
        )
        self.assertEqual(
            provider_ids_for(config, "album"),
            ["netease", "kuwo", "kugou", "migu", "joox", "musicbrainz"],
        )
        self.assertEqual(provider_ids_for(config, "artist"), ["netease"])

    def test_provider_definitions_do_not_advertise_removed_sources(self):
        ids = [definition["id"] for definition in provider_definitions()]
        self.assertEqual(ids, list(DEFAULT_PROVIDER_ORDER))
        self.assertNotIn("qq", ids)
        self.assertNotIn("qianqian", ids)

    def test_provider_ids_for_invalid_config_uses_safe_order(self):
        self.assertEqual(
            provider_ids_for({"not": "a provider list"}, "search"),
            ["netease", "kuwo", "kugou", "migu", "joox", "musicbrainz"],
        )


if __name__ == "__main__":
    unittest.main()

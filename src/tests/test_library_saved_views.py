import sys
import tempfile
import unittest

sys.path.insert(0, "app/server")
from library_capability_policy import CAPABILITY_VERSION, library_capabilities, supports_field_syntax
from library_saved_view_policy import (
    MAX_VIEWS,
    merge_view,
    normalize_criteria,
    normalize_view,
    normalize_views,
    remove_view,
    view_identity,
    view_query_params,
)
from library_saved_views import delete_saved_view, list_saved_views, save_saved_view, views_snapshot


def _criteria(**overrides):
    base = {"view": "all", "sort": "title", "dir": "asc"}
    base.update(overrides)
    return base


class SavedViewPolicyTests(unittest.TestCase):
    def test_unknown_view_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_criteria({"view": "nowhere"})

    def test_unknown_sort_falls_back_to_title(self):
        self.assertEqual(normalize_criteria({"sort": "bpm"})["sort"], "title")

    def test_direction_is_only_asc_or_desc(self):
        self.assertEqual(normalize_criteria({"dir": "DESC"})["dir"], "desc")
        self.assertEqual(normalize_criteria({"dir": "sideways"})["dir"], "asc")

    def test_text_is_bounded_and_control_characters_dropped(self):
        criteria = normalize_criteria({"search": "a\x00b", "folder": "x" * 9000})
        self.assertEqual(criteria["search"], "ab")
        self.assertEqual(len(criteria["folder"]), 4096)

    def test_subtree_accepts_only_truthy_forms(self):
        self.assertTrue(normalize_criteria({"subtree": "true"})["subtree"])
        self.assertFalse(normalize_criteria({"subtree": "0"})["subtree"])
        self.assertFalse(normalize_criteria({"subtree": 1})["subtree"])

    def test_identity_follows_the_name_not_the_filter(self):
        first = view_identity("我的视图")
        self.assertEqual(first, view_identity("我的视图"))
        self.assertEqual(view_identity("DSD"), view_identity("dsd"))
        self.assertNotEqual(first, view_identity("别的视图"))
        self.assertTrue(first.startswith("sv_"))
        self.assertEqual(len(first), 15)

    def test_saving_the_same_name_with_a_new_filter_replaces_the_place(self):
        before = normalize_view({"name": "DSD", "criteria": _criteria(view="dsd")}, now=10)
        after = normalize_view({"name": "DSD", "criteria": _criteria(view="dsd", search="floyd")}, now=20)
        self.assertEqual(before["id"], after["id"])

    def test_name_is_required_and_trimmed(self):
        with self.assertRaises(ValueError):
            normalize_view({"criteria": _criteria()})
        view = normalize_view({"name": "  最近  ", "criteria": _criteria()}, now=100)
        self.assertEqual(view["name"], "最近")
        self.assertEqual(view["created_at"], 100)

    def test_supplied_id_must_look_like_an_id(self):
        forged = normalize_view({"id": "x' OR 1=1", "name": "n", "criteria": _criteria()})
        self.assertTrue(forged["id"].startswith("sv_"))
        kept = normalize_view({"id": "sv_0123456789ab", "name": "n", "criteria": _criteria()})
        self.assertEqual(kept["id"], "sv_0123456789ab")

    def test_normalize_views_dedupes_and_caps(self):
        views = [{"name": "v%d" % index, "criteria": _criteria(search=str(index)), "updated_at": index + 1}
                 for index in range(MAX_VIEWS + 6)]
        normalized = normalize_views(views)
        self.assertEqual(len(normalized), MAX_VIEWS)
        self.assertEqual(normalized[0]["name"], "v%d" % (MAX_VIEWS + 5))
        self.assertEqual(len({item["id"] for item in normalized}), MAX_VIEWS)

    def test_merge_replaces_same_id_and_remove_drops_it(self):
        first = normalize_view({"name": "a", "criteria": _criteria()}, now=1)
        second = normalize_view({"name": "b", "criteria": _criteria(view="dsd")}, now=2)
        merged = merge_view([first], second)
        self.assertEqual([item["name"] for item in merged], ["b", "a"])
        replaced = merge_view(merged, dict(second, name="b2"))
        self.assertEqual([item["name"] for item in replaced], ["b2", "a"])
        self.assertEqual([item["name"] for item in remove_view(merged, second["id"])], ["a"])

    def test_query_params_only_carry_set_filters(self):
        params = view_query_params({"criteria": _criteria(view="dsd", search="floyd", subtree=True)})
        self.assertEqual(params, {"view": "dsd", "sort": "title", "dir": "asc",
                                  "search": "floyd", "subtree": "1"})


class SavedViewStorageTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.config = {"cache_dir": self._tmp.name}

    def tearDown(self):
        self._tmp.cleanup()

    def test_save_list_delete_round_trip(self):
        self.assertEqual(list_saved_views(self.config), [])
        views = save_saved_view(self.config, {"name": "DSD", "criteria": _criteria(view="dsd")}, now=10)
        self.assertEqual(len(views), 1)
        self.assertEqual(views[0]["criteria"]["view"], "dsd")
        self.assertEqual(len(list_saved_views(self.config)), 1)
        self.assertEqual(delete_saved_view(self.config, views[0]["id"]), [])

    def test_resaving_the_same_name_updates_instead_of_duplicating(self):
        save_saved_view(self.config, {"name": "DSD", "criteria": _criteria(view="dsd")}, now=10)
        views = save_saved_view(self.config, {"name": "DSD", "criteria": _criteria(view="dsd", sort="added")}, now=20)
        self.assertEqual(len(views), 1)
        self.assertEqual(views[0]["criteria"]["sort"], "added")
        self.assertEqual(views[0]["created_at"], 10)
        self.assertEqual(views[0]["updated_at"], 20)

    def test_storage_is_capped(self):
        for index in range(MAX_VIEWS + 3):
            save_saved_view(self.config, {"name": "v%d" % index, "criteria": _criteria(search=str(index))}, now=index + 1)
        self.assertEqual(len(list_saved_views(self.config)), MAX_VIEWS)

    def test_snapshot_exposes_the_limit(self):
        self.assertEqual(views_snapshot(self.config), {"views": [], "limit": MAX_VIEWS})

    def test_invalid_view_is_not_stored(self):
        with self.assertRaises(ValueError):
            save_saved_view(self.config, {"name": "x", "criteria": {"view": "nope"}})
        self.assertEqual(list_saved_views(self.config), [])


class CapabilityPolicyTests(unittest.TestCase):
    def test_fts_mode_is_advertised_with_its_minimum(self):
        capabilities = library_capabilities("fts5-trigram", ["flac", "mp3"])
        self.assertEqual(capabilities["version"], CAPABILITY_VERSION)
        self.assertEqual(capabilities["search"]["mode"], "fts5-trigram")
        self.assertEqual(capabilities["search"]["min_chars"], 3)
        self.assertEqual(capabilities["formats"], ["FLAC", "MP3"])
        self.assertEqual(capabilities["saved_views"]["limit"], MAX_VIEWS)

    def test_unknown_mode_degrades_to_like(self):
        capabilities = library_capabilities("nonsense")
        self.assertEqual(capabilities["search"]["mode"], "like")
        self.assertEqual(capabilities["search"]["min_chars"], 0)

    def test_field_syntax_is_advertised_and_field_checked(self):
        capabilities = library_capabilities("fts5-trigram")
        self.assertTrue(supports_field_syntax(capabilities))
        self.assertTrue(supports_field_syntax(capabilities, "artist"))
        self.assertFalse(supports_field_syntax(capabilities, "bpm"))
        self.assertFalse(supports_field_syntax({}))


if __name__ == "__main__":
    unittest.main()

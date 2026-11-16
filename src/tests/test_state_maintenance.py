"""User-state maintenance: prune stale favorites, reset the user's own data.

Why this exists: a track id is ``sha1(absolute path)[:16]``. Reinstalling fnOS,
swapping a disk, or mounting the collection at a different path renames every
track, so a favorite restored from the old installation points at an id the new
library can never serve. It stays in the stored list, keeps counting, and the
next favorite of the same song is added beside it - the "收藏一直累加" report.

Pruning is deliberately conservative: an empty index is refused instead of being
read as "nothing is a favorite", because that is exactly the state a fresh
install is in before its first scan.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, "app/server")

import state_store
from state_store import (load_user_state, prune_favorites, reset_user_state,
                         save_playback_session, save_user_state)


class UserStateMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.config = {"cache_dir": os.path.join(self.root.name, "cache")}

    def favorites(self):
        return load_user_state(self.config)["favorites"]

    def test_prune_removes_ids_the_library_cannot_serve(self):
        save_user_state(self.config, {"favorites": ["keep-1", "keep-2", "stale-a", "stale-b"]})
        result = prune_favorites(self.config, {"keep-1", "keep-2", "other"})
        self.assertEqual(result["removed"], 2)
        self.assertEqual(result["remaining"], 2)
        self.assertEqual(sorted(self.favorites()), ["keep-1", "keep-2"])

    def test_prune_keeps_the_newest_first_order(self):
        save_user_state(self.config, {"favorites": ["new", "middle", "old", "stale"]})
        prune_favorites(self.config, {"new", "middle", "old"})
        self.assertEqual(self.favorites(), ["new", "middle", "old"])

    def test_prune_is_a_no_op_when_every_id_resolves(self):
        save_user_state(self.config, {"favorites": ["a", "b"]})
        result = prune_favorites(self.config, {"a", "b"})
        self.assertEqual(result, {"removed": 0, "remaining": 2})

    def test_prune_refuses_an_empty_index(self):
        # A reinstall that has not scanned yet reports no ids at all. Deleting the
        # whole list there is the failure this guard exists for.
        save_user_state(self.config, {"favorites": ["a", "b"]})
        with self.assertRaises(ValueError):
            prune_favorites(self.config, set())
        self.assertEqual(sorted(self.favorites()), ["a", "b"], "a refused prune must not touch the rows")

    def test_prune_ignores_ids_that_are_not_usable_text(self):
        save_user_state(self.config, {"favorites": ["a"]})
        result = prune_favorites(self.config, ["a", "", None, {"bad": "object"}, ["nested"]])
        self.assertEqual(result, {"removed": 0, "remaining": 1})

    def test_reset_clears_the_user_data_and_leaves_the_host_alone(self):
        save_user_state(self.config, {
            "favorites": ["a", "b"],
            "playlists": [{"id": "pl-1", "name": "Road", "trackIds": ["a"]}],
            "ui": {"theme": "dark"},
        })
        save_playback_session(self.config, {"queue": ["a", "b"], "current_id": "b"})
        before = load_user_state(self.config)
        self.assertEqual(len(before["favorites"]), 2)
        self.assertTrue(before["playlists"])

        after = reset_user_state(self.config)
        self.assertEqual(after["favorites"], [])
        self.assertEqual(after["playlists"], [])
        self.assertEqual(after["playback"], {})
        self.assertFalse(any(after["ui"].values()), "UI preferences are cleared too")

    def test_reset_publishes_a_new_revision(self):
        save_user_state(self.config, {"favorites": ["a"]})
        before = load_user_state(self.config)["revision"]
        after = reset_user_state(self.config)["revision"]
        self.assertGreater(after, before, "clients detect the reset through the revision")


if __name__ == "__main__":
    unittest.main()

"""R461: the server-side directory browser that replaces the fnOS host picker.

The fnOS picker (``pickUserFile``) only exists inside the fnOS App/desktop
WebView.  The Android client and any standalone browser have no host, so the
settings pane asks the server instead.  These tests pin the rules that keep that
fallback safe: only allowed roots, only directories, no hidden entries, no
symlink escapes, bounded result size, and a user-facing message on refusal.
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

import library_paths


class LibraryDirBrowseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name

    def tearDown(self):
        self.temp.cleanup()

    def make_dir(self, *parts):
        path = os.path.join(self.root, *parts)
        os.makedirs(path, exist_ok=True)
        return path

    def test_empty_path_lists_browse_roots_only(self):
        data = library_paths.list_library_directories("")
        self.assertEqual(data["path"], "")
        self.assertEqual(data["parent"], "")
        self.assertEqual(data["entries"], [])
        self.assertIsInstance(data["roots"], list)
        for root in data["roots"]:
            self.assertIn("name", root)
            self.assertIn("path", root)

    def test_lists_directories_only_and_skips_hidden(self):
        self.make_dir("Music")
        self.make_dir("Media")
        self.make_dir(".hidden")
        # fnOS platform state and the ext4 recovery directory are never music
        # roots; on a live NAS they filled the whole first screen of /vol1.
        self.make_dir("@appcenter")
        self.make_dir("@appdata")
        self.make_dir("lost+found")
        with open(os.path.join(self.root, "track.mp3"), "wb") as handle:
            handle.write(b"x")
        data = library_paths.list_library_directories(self.root)
        self.assertEqual([entry["name"] for entry in data["entries"]], ["Media", "Music"])
        for entry in data["entries"]:
            self.assertTrue(os.path.isdir(entry["path"]))

    def test_entry_cap_marks_the_listing_truncated(self):
        for index in range(library_paths.MAX_BROWSE_ENTRIES + 5):
            self.make_dir("d%03d" % index)
        data = library_paths.list_library_directories(self.root)
        self.assertEqual(len(data["entries"]), library_paths.MAX_BROWSE_ENTRIES)
        self.assertTrue(data["truncated"])

    def test_parent_walks_up_one_level(self):
        child = self.make_dir("sub")
        data = library_paths.list_library_directories(child)
        # The listing reports real paths (8.3 names expand on Windows), so the
        # expectation has to be resolved the same way.
        self.assertEqual(os.path.normcase(data["path"]), os.path.normcase(os.path.realpath(child)))
        self.assertEqual(os.path.normcase(data["parent"]), os.path.normcase(os.path.realpath(self.root)))
        self.assertFalse(data["truncated"])

    def test_missing_directory_raises_a_user_facing_message(self):
        with self.assertRaises(ValueError) as caught:
            library_paths.list_library_directories(os.path.join(self.root, "missing"))
        self.assertIn("目录", str(caught.exception))

    def test_symlink_that_escapes_the_allowed_roots_is_hidden(self):
        inside = self.make_dir("inside")
        link = os.path.join(inside, "escape")
        try:
            os.symlink(self.root, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available in this environment")
        allowed_root = os.path.normcase(os.path.realpath(inside))

        def allowed(path):
            value = os.path.normcase(os.path.realpath(path))
            return value == allowed_root or value.startswith(allowed_root + os.sep)

        with mock.patch.object(library_paths, "is_allowed_library_path", side_effect=allowed):
            data = library_paths.list_library_directories(inside)
        self.assertEqual(data["entries"], [])

    def test_symlink_that_stays_inside_the_allowed_roots_is_kept(self):
        inside = self.make_dir("inside")
        target = self.make_dir("inside", "real")
        link = os.path.join(inside, "alias")
        try:
            os.symlink(target, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available in this environment")
        allowed_root = os.path.normcase(os.path.realpath(inside))

        def allowed(path):
            value = os.path.normcase(os.path.realpath(path))
            return value == allowed_root or value.startswith(allowed_root + os.sep)

        with mock.patch.object(library_paths, "is_allowed_library_path", side_effect=allowed):
            data = library_paths.list_library_directories(inside)
        self.assertEqual(sorted(entry["name"] for entry in data["entries"]), ["alias", "real"])

    @unittest.skipIf(os.name == "nt", "the allowed-prefix boundary is POSIX-only")
    def test_rejects_paths_outside_the_allowed_prefixes(self):
        with self.assertRaises(ValueError):
            library_paths.list_library_directories("/etc")

    def _fake_volume(self):
        """One volume whose root carries platform state plus one user home."""
        volume = self.root
        self.make_dir("1000", "music")
        self.make_dir("@appdata")
        self.make_dir("docker")
        self.make_dir("lost+found")
        return volume

    def _patch_volume(self, volume):
        return (
            mock.patch.object(library_paths, "_volume_root_candidates", return_value=[volume]),
            mock.patch.object(library_paths, "is_allowed_library_path", return_value=True),
        )

    def test_roots_start_at_the_user_home_not_the_volume_root(self):
        # The fnOS picker opens at /vol1/1000 ("我的文件"); a picker that starts
        # at /vol1 shows @appdata, docker and thumb instead of the user's files.
        volume = self._fake_volume()
        candidates, allowed = self._patch_volume(volume)
        with candidates, allowed:
            roots = library_paths.library_browse_roots()
            listing = library_paths.list_library_directories("")
        home = os.path.realpath(os.path.join(volume, "1000"))
        self.assertEqual([entry["path"] for entry in roots], [home])
        self.assertEqual(roots[0]["name"], "我的文件")
        self.assertEqual([entry["path"] for entry in listing["roots"]], [home])

    def test_a_browse_root_offers_no_parent(self):
        # Walking up from the home would land on the volume root and put the
        # platform directories back on screen.
        volume = self._fake_volume()
        candidates, allowed = self._patch_volume(volume)
        home = os.path.realpath(os.path.join(volume, "1000"))
        with candidates, allowed:
            listing = library_paths.list_library_directories(home)
        self.assertEqual(listing["path"], home)
        self.assertEqual(listing["parent"], "")
        self.assertEqual([entry["name"] for entry in listing["entries"]], ["music"])

    def test_volume_root_is_the_fallback_when_no_home_exists(self):
        self.make_dir("@appdata")
        volume = self.root
        candidates, allowed = self._patch_volume(volume)
        with candidates, allowed:
            roots = library_paths.library_browse_roots()
        self.assertEqual([entry["path"] for entry in roots], [os.path.realpath(volume)])
        self.assertNotEqual(roots[0]["name"], "我的文件")

    def test_several_homes_keep_their_own_labels(self):
        self.make_dir("1000")
        self.make_dir("1001-0-ab12cd")
        volume = self.root
        candidates, allowed = self._patch_volume(volume)
        with candidates, allowed:
            roots = library_paths.library_browse_roots()
        # Neither home holds a directory, so neither may claim to be 我的文件:
        # the label has to say which storage is which.
        self.assertEqual(
            sorted(entry["name"] for entry in roots),
            ["我的文件 (1000)", "我的文件 (1001-0-ab12cd)"],
        )

    def test_an_empty_second_space_does_not_reach_the_picker(self):
        # fnOS gives each volume its own user space; on the test NAS
        # /vol02/1000-0-ab026773 exists but holds nothing.  The desktop picker
        # only ever shows 我的文件, so the empty node has to go.
        self.make_dir("1000", "music")
        self.make_dir("1000-0-ab026773")
        volume = self.root
        candidates, allowed = self._patch_volume(volume)
        with candidates, allowed:
            roots = library_paths.library_browse_roots()
        self.assertEqual([entry["path"] for entry in roots], [os.path.realpath(os.path.join(volume, "1000"))])
        self.assertEqual(roots[0]["name"], "我的文件")

    def test_empty_homes_are_kept_when_no_home_holds_a_directory(self):
        # Dropping every home would fall back to the volume root and put
        # @appdata/docker/thumb back on screen, so emptiness only ever removes a
        # home when another one survives.
        self.make_dir("1000")
        self.make_dir("@appdata")
        volume = self.root
        candidates, allowed = self._patch_volume(volume)
        with candidates, allowed:
            roots = library_paths.library_browse_roots()
        self.assertEqual([entry["path"] for entry in roots], [os.path.realpath(os.path.join(volume, "1000"))])
        self.assertEqual(roots[0]["name"], "我的文件")


if __name__ == "__main__":
    unittest.main()

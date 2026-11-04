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
        # The real mount table of whatever machine runs the suite must not leak
        # into these expectations; the remote-mount rules have their own class.
        remote = mock.patch.object(library_paths, "cached_remote_mount_paths", return_value=[])
        remote.start()
        self.addCleanup(remote.stop)

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


class RemoteMountBrowseTests(unittest.TestCase):
    """Mounted shares are library material wherever the platform put them.

    fnOS parks a 远程挂载 outside 我的文件, and a hand written /etc/fstab entry
    can land anywhere, so walking the home never reached either.  The mount
    table is read instead, and these tests pin the parsing, the promotion into
    the root list, and the boundary that accepts a path inside a share.
    """

    MOUNT_TABLE = "\n".join([
        "/dev/sda2 / ext4 rw,relatime 0 0",
        "proc /proc proc rw 0 0",
        "tmpfs /run tmpfs rw 0 0",
        "overlay /vol1/docker/overlay2/x/merged overlay rw 0 0",
        "none /var/lib/lxcfs fuse.lxcfs rw 0 0",
        "/dev/sdb1 /media/usb fuseblk rw 0 0",
        "//192.168.5.10/music /mnt/smb-share cifs rw,relatime 0 0",
        "192.168.5.11:/export/nas /vol1/@mountmgr/remote-music nfs4 rw,relatime 0 0",
        ":local:/vol1/1000/music /mnt/rclone-test fuse.rclone rw,nosuid,nodev 0 0",
    ])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        self.addCleanup(self.temp.cleanup)
        library_paths.reset_remote_mount_cache()
        self.addCleanup(library_paths.reset_remote_mount_cache)

    def make_dir(self, *parts):
        path = os.path.join(self.root, *parts)
        os.makedirs(path, exist_ok=True)
        return path

    def test_only_network_backed_mounts_are_reported(self):
        self.assertEqual(
            library_paths.remote_mount_paths(self.MOUNT_TABLE),
            ["/mnt/rclone-test", "/mnt/smb-share", "/vol1/@mountmgr/remote-music"],
        )

    def test_a_local_only_fuse_backend_is_not_a_share(self):
        # lxcfs and fuseblk share the FUSE prefix (or the block-device form)
        # without ever holding a share, and listing them would expose system
        # state in a music picker.
        self.assertFalse(library_paths.is_remote_filesystem("fuse.lxcfs", "none"))
        self.assertFalse(library_paths.is_remote_filesystem("fuseblk", "/dev/sdb1"))
        self.assertFalse(library_paths.is_remote_filesystem("ext4", "/dev/sda2"))
        self.assertFalse(library_paths.is_remote_filesystem("tmpfs", "tmpfs"))
        self.assertTrue(library_paths.is_remote_filesystem("fuse.rclone", ":local:/x"))
        self.assertTrue(library_paths.is_remote_filesystem("cifs", "//host/share"))
        self.assertTrue(library_paths.is_remote_filesystem("", "host:/export"))

    def test_octal_escapes_in_the_mount_table_are_decoded(self):
        table = "192.168.5.11:/export/nas /mnt/my\\040music\\011dir nfs4 rw 0 0"
        self.assertEqual(library_paths.remote_mount_paths(table), ["/mnt/my music\tdir"])

    def test_a_share_mounted_inside_another_share_is_listed_once(self):
        table = "\n".join([
            "//host/music /mnt/outer cifs rw 0 0",
            "//host/music/inner /mnt/outer/inner cifs rw 0 0",
        ])
        self.assertEqual(library_paths.remote_mount_paths(table), ["/mnt/outer"])

    def test_the_root_and_system_trees_are_never_offered(self):
        table = "\n".join([
            "//host/music / cifs rw 0 0",
            "//host/music /proc/sys/fs/binfmt_misc cifs rw 0 0",
            "//host/music /sys/x cifs rw 0 0",
            "//host/music /dev/x cifs rw 0 0",
        ])
        self.assertEqual(library_paths.remote_mount_paths(table), [])

    def test_a_broken_or_missing_table_answers_empty(self):
        self.assertEqual(library_paths.remote_mount_paths(""), [])
        self.assertEqual(library_paths.remote_mount_paths(None if os.name == "nt" else "\n\n\n"), [])
        self.assertEqual(library_paths.remote_mount_paths(7), [])

    def test_the_result_list_is_bounded(self):
        table = "\n".join(
            "//host/music%d /mnt/share%02d cifs rw 0 0" % (index, index)
            for index in range(library_paths.MAX_REMOTE_MOUNTS + 10)
        )
        self.assertEqual(len(library_paths.remote_mount_paths(table)), library_paths.MAX_REMOTE_MOUNTS)

    def test_a_mount_outside_the_home_becomes_a_browse_root(self):
        share = self.make_dir("远程音乐")
        volume = self.root
        self.make_dir("1000", "music")
        candidates = mock.patch.object(library_paths, "_volume_root_candidates", return_value=[volume])
        allowed = mock.patch.object(library_paths, "is_allowed_library_path", return_value=True)
        remote = mock.patch.object(library_paths, "cached_remote_mount_paths", return_value=[os.path.realpath(share)])
        with candidates, allowed, remote:
            roots = library_paths.library_browse_roots()
        self.assertEqual(
            [entry["path"] for entry in roots],
            [os.path.realpath(os.path.join(volume, "1000")), os.path.realpath(share)],
        )
        self.assertEqual(roots[-1]["name"], "远程音乐")

    def test_two_shares_with_the_same_folder_name_get_distinct_labels(self):
        first = self.make_dir("server-a", "music")
        second = self.make_dir("server-b", "music")
        volume = self.root
        self.make_dir("1000", "mine")
        candidates = mock.patch.object(library_paths, "_volume_root_candidates", return_value=[volume])
        allowed = mock.patch.object(library_paths, "is_allowed_library_path", return_value=True)
        remote = mock.patch.object(
            library_paths, "cached_remote_mount_paths",
            return_value=[os.path.realpath(first), os.path.realpath(second)],
        )
        with candidates, allowed, remote:
            roots = library_paths.library_browse_roots()
        self.assertEqual([entry["name"] for entry in roots], ["我的文件", "music", "music (server-b)"])
        self.assertEqual(
            [entry["path"] for entry in roots],
            [os.path.realpath(os.path.join(volume, "1000")), os.path.realpath(first), os.path.realpath(second)],
        )

    def test_a_mount_already_inside_an_offered_root_is_not_promoted(self):
        volume = self.root
        home = self.make_dir("1000", "music")
        nested = self.make_dir("1000", "来自：百度网盘")
        candidates = mock.patch.object(library_paths, "_volume_root_candidates", return_value=[volume])
        allowed = mock.patch.object(library_paths, "is_allowed_library_path", return_value=True)
        remote = mock.patch.object(library_paths, "cached_remote_mount_paths", return_value=[os.path.realpath(nested)])
        with candidates, allowed, remote:
            roots = library_paths.library_browse_roots()
        self.assertEqual([entry["path"] for entry in roots], [os.path.realpath(os.path.dirname(home))])

    def test_a_browse_root_that_is_a_share_offers_no_parent(self):
        # Walking up out of a share would show the platform directory the mount
        # lives in, which is exactly what the picker must not do.
        volume = self.root
        self.make_dir("1000", "music")
        share = self.make_dir("远程音乐", "专辑")
        candidates = mock.patch.object(library_paths, "_volume_root_candidates", return_value=[volume])
        allowed = mock.patch.object(library_paths, "is_allowed_library_path", return_value=True)
        remote = mock.patch.object(library_paths, "cached_remote_mount_paths", return_value=[os.path.realpath(os.path.dirname(share))])
        with candidates, allowed, remote:
            listing = library_paths.list_library_directories(os.path.realpath(os.path.dirname(share)))
        self.assertEqual(listing["parent"], "")
        self.assertEqual([entry["name"] for entry in listing["entries"]], ["专辑"])

    @unittest.skipIf(os.name == "nt", "the allowed-prefix boundary is POSIX-only")
    def test_a_path_inside_a_share_is_allowed_anywhere_it_is_mounted(self):
        share = self.make_dir("share")
        inside = self.make_dir("share", "album")
        remote = mock.patch.object(library_paths, "cached_remote_mount_paths", return_value=[os.path.realpath(share)])
        with remote:
            self.assertTrue(library_paths.is_allowed_library_path(os.path.realpath(share)))
            self.assertTrue(library_paths.is_allowed_library_path(os.path.realpath(inside)))
            self.assertFalse(library_paths.is_allowed_library_path(os.path.realpath(self.root)))

    @unittest.skipIf(os.name == "nt", "the allowed-prefix boundary is POSIX-only")
    def test_a_share_is_browsable_without_being_under_an_allowed_prefix(self):
        share = self.make_dir("share")
        self.make_dir("share", "album")
        remote = mock.patch.object(library_paths, "cached_remote_mount_paths", return_value=[os.path.realpath(share)])
        with remote:
            listing = library_paths.list_library_directories(os.path.realpath(share))
        self.assertEqual([entry["name"] for entry in listing["entries"]], ["album"])

    def test_the_mount_table_is_read_once_per_window(self):
        calls = []

        def table():
            calls.append(1)
            return []

        with mock.patch.object(library_paths, "remote_mount_paths", table):
            library_paths.reset_remote_mount_cache()
            for _ in range(5):
                library_paths.cached_remote_mount_paths()
            self.assertEqual(len(calls), 1)
            library_paths.reset_remote_mount_cache()
            library_paths.cached_remote_mount_paths()
            self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()

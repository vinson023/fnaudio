import json
import os
import stat
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, "app/server")

import file_permissions


class FilePermissionTests(unittest.TestCase):
    def test_atomic_private_json_replaces_existing_content(self):
        with tempfile.TemporaryDirectory() as root:
            target = os.path.join(root, "private", "config.json")
            file_permissions.atomic_write_json(target, {"token": "secret"})

            with open(target, "r", encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), {"token": "secret"})
            self.assertFalse(os.path.islink(target))

    def test_public_write_uses_public_parent_and_file_modes(self):
        with tempfile.TemporaryDirectory() as root, mock.patch.object(file_permissions, "_chmod") as chmod:
            target = os.path.join(root, "ui", "service_port.json")
            file_permissions.atomic_write_json(target, {"server_port": 18080}, file_permissions.PUBLIC_FILE_MODE)

        requested_modes = [call.args[1] for call in chmod.call_args_list]
        self.assertIn(file_permissions.PUBLIC_DIRECTORY_MODE, requested_modes)
        self.assertIn(file_permissions.PUBLIC_FILE_MODE, requested_modes)

    def test_preserve_owner_and_mode_copies_the_source_mode(self):
        source_stat = SimpleNamespace(st_mode=stat.S_IFREG | 0o664, st_uid=1000, st_gid=100)
        with mock.patch.object(file_permissions.os, "stat", return_value=source_stat), \
             mock.patch.object(file_permissions, "_chmod") as chmod:
            file_permissions.preserve_owner_and_mode("source.flac", "replacement.flac")

        chmod.assert_called_once_with("replacement.flac", 0o664)

    def test_non_regular_source_is_never_replaced(self):
        source_stat = SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0, st_gid=0)
        with mock.patch.object(file_permissions.os, "stat", return_value=source_stat):
            with self.assertRaises(OSError):
                file_permissions.preserve_owner_and_mode("source", "replacement")

    def test_missing_sqlite_sidecar_does_not_raise(self):
        with mock.patch.object(file_permissions.os, "name", "posix"), \
             mock.patch.object(file_permissions.os, "path", wraps=file_permissions.os.path), \
             mock.patch.object(file_permissions.os, "chmod", side_effect=FileNotFoundError):
            file_permissions._chmod("library.sqlite3-shm", file_permissions.PRIVATE_FILE_MODE)


if __name__ == "__main__":
    unittest.main()

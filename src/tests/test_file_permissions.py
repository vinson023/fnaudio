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

    def test_secure_directory_rejects_symlink_target(self):
        with tempfile.TemporaryDirectory() as root:
            real = os.path.join(root, "real")
            link = os.path.join(root, "link")
            os.mkdir(real)
            os.symlink(real, link, target_is_directory=True)
            with self.assertRaises(OSError):
                file_permissions.secure_directory(link)

    def test_path_helpers_do_not_stringify_arbitrary_objects(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("path must not stringify arbitrary objects")

        self.assertFalse(file_permissions.secure_file(Explosive()))
        with self.assertRaises(TypeError):
            file_permissions.atomic_write_text(Explosive(), "text")

    def test_directory_hardening_chmods_only_when_the_mode_drifts(self):
        # `secure_directory_on_drift` replaces a six-syscall pass that `Observability.write`
        # used to pay per log line, so the decision has to stay identical: already private means
        # nothing to do, anything else means harden. `_chmod` is a no-op on Windows
        # (os.name is "nt"), so the assertion is about the call and its arguments rather
        # than about a mode this machine cannot change - it would pass vacuously otherwise.
        wanted = file_permissions.PRIVATE_DIRECTORY_MODE
        with tempfile.TemporaryDirectory() as root:
            for label, mode, expect_chmod in (
                ("private", stat.S_IFDIR | wanted, False),
                ("world readable", stat.S_IFDIR | 0o755, True),
                ("extra setgid", stat.S_IFDIR | (wanted | stat.S_ISGID), True),
            ):
                with self.subTest(case=label):
                    target = os.path.join(root, label.replace(" ", "-"))
                    os.makedirs(target)
                    fake = SimpleNamespace(st_mode=mode)
                    with mock.patch.object(file_permissions, "_chmod") as chmod, \
                            mock.patch.object(file_permissions.os, "lstat", return_value=fake):
                        returned = file_permissions.secure_directory_on_drift(target)
                    self.assertEqual(returned, os.path.abspath(target))
                    self.assertEqual(chmod.called, expect_chmod, "chmod decision wrong for " + label)
                    if expect_chmod:
                        self.assertEqual(chmod.call_args.args[1], wanted)

    def test_directory_hardening_defers_symlinks_and_missing_paths(self):
        # A symlinked log directory and a directory removed between two writes are both
        # `secure_directory`'s business: it refuses the first and creates the second. The drift
        # path must not start answering either of them by itself.
        with tempfile.TemporaryDirectory() as root:
            target = os.path.join(root, "defer")
            for label, failure in (("missing", FileNotFoundError(2, "gone")),
                                   ("symlink", SimpleNamespace(st_mode=stat.S_IFLNK | 0o777)),
                                   ("plain file", SimpleNamespace(st_mode=stat.S_IFREG | 0o600))):
                with self.subTest(case=label):
                    calls = []

                    def full(path=None, mode=None, *args, **kwargs):
                        calls.append((path, mode))
                        return "secured"

                    with mock.patch.object(file_permissions, "secure_directory", side_effect=full), \
                            mock.patch.object(file_permissions.os, "lstat",
                                              side_effect=failure if isinstance(failure, OSError) else None,
                                              return_value=None if isinstance(failure, OSError) else failure):
                        self.assertEqual(file_permissions.secure_directory_on_drift(target), "secured")
                    self.assertEqual(len(calls), 1, "the full hardening did not run exactly once")
                    self.assertEqual(calls[0][0], os.path.abspath(target))
                    self.assertEqual(calls[0][1], file_permissions.PRIVATE_DIRECTORY_MODE)

    def test_file_hardening_chmods_only_when_the_mode_drifts(self):
        # `secure_file_on_drift` replaces the per-log-line chmod, so it has to keep `secure_file`
        # 's exact answers: a missing path and a symlink are False, a directory is not a file, and
        # only a mode that differs produces a chmod. On Windows `_chmod` returns before touching
        # the OS (os.name is "nt"), so the assertions are about calls, not resulting modes.
        wanted = file_permissions.PRIVATE_FILE_MODE
        with tempfile.TemporaryDirectory() as root:
            target = os.path.join(root, "app.log")
            with open(target, "w", encoding="utf-8") as handle:
                handle.write("line\n")
            for label, mode, expect in (
                ("private", stat.S_IFREG | wanted, (True, False)),
                ("umask default", stat.S_IFREG | 0o666, (True, True)),
                ("directory", stat.S_IFDIR | wanted, (False, False)),
                ("symlink", stat.S_IFLNK | 0o777, (False, False)),
            ):
                with self.subTest(case=label):
                    served = []
                    fake = SimpleNamespace(st_mode=mode)

                    def probe(target_path):
                        served.append(target_path)
                        return fake

                    with mock.patch.object(file_permissions, "_chmod") as chmod, \
                            mock.patch.object(file_permissions.os, "lstat", side_effect=probe):
                        returned = file_permissions.secure_file_on_drift(target)
                    self.assertEqual(returned, expect[0], "wrong answer for " + label)
                    self.assertEqual(chmod.called, expect[1], "chmod decision wrong for " + label)
                    if expect[0]:
                        # A hostile or accidental absolute path must not be opened twice.
                        self.assertEqual(served, [os.path.abspath(target)])
            with mock.patch.object(file_permissions.os, "lstat", side_effect=FileNotFoundError(2, "gone")):
                self.assertFalse(file_permissions.secure_file_on_drift(target))
            self.assertFalse(file_permissions.secure_file_on_drift(""), "an empty path must be refused")

    def test_directory_hardening_creates_a_missing_directory_for_real(self):
        # The observability caller only reaches this helper, so creation has to survive the fast
        # path without a fabricated lstat: a log directory removed while the service runs must
        # come back on the next write, exactly as it did before.
        with tempfile.TemporaryDirectory() as root:
            target = os.path.join(root, "created", "logs")
            self.assertFalse(os.path.isdir(target))
            returned = file_permissions.secure_directory_on_drift(target)
            self.assertEqual(returned, os.path.abspath(target))
            self.assertTrue(os.path.isdir(target))
            self.assertEqual(file_permissions.secure_directory_on_drift(target), returned)


    def test_sqlite_sidecars_are_probed_once_and_chmodded_only_on_drift(self):
        # `secure_sqlite_files` is the hottest permission path in the server: a pooled read
        # calls it on entry and again on exit, and every write calls it too. In the steady
        # state it has to cost one lstat per sidecar, which means it must not fall back to
        # `secure_file` - that existence check plus the pair of link probes is what this
        # removes. The decision still has to match the full pass exactly, so every case
        # below pins both the probes made and the chmods that followed them. `_chmod` does
        # nothing on Windows, so asserting the call and its arguments is the only shape that
        # cannot pass vacuously here.
        wanted = file_permissions.PRIVATE_FILE_MODE
        private = stat.S_IFREG | wanted
        absent = FileNotFoundError(2, "sqlite has not created this sidecar")
        cases = (
            ("all three private", (private, private, private), (False, False, False)),
            ("wal drifted", (private, stat.S_IFREG | 0o666, private), (False, True, False)),
            ("both sidecars absent", (private, absent, absent), (False, False, False)),
            ("shm is a symlink", (private, private, stat.S_IFLNK | 0o777), (False, False, False)),
            ("wal is a directory", (private, stat.S_IFDIR | wanted, private), (False, False, False)),
        )
        with tempfile.TemporaryDirectory() as root:
            base = os.path.join(root, "library.sqlite3")
            suffixes = ("", "-wal", "-shm")
            abspathed = [os.path.abspath(base + suffix) for suffix in suffixes]
            for label, probed, expect_chmod in cases:
                with self.subTest(case=label):
                    served = dict(zip(abspathed, probed))
                    seen = []

                    def fake_lstat(target):
                        seen.append(target)
                        value = served[target]
                        if isinstance(value, OSError):
                            raise value
                        return SimpleNamespace(st_mode=value)

                    def refuse(*args, **kwargs):
                        raise AssertionError("the full multi-syscall probe is back")

                    with mock.patch.object(file_permissions, "secure_file", side_effect=refuse), \
                            mock.patch.object(file_permissions, "_chmod") as chmod, \
                            mock.patch.object(file_permissions.os, "lstat", side_effect=fake_lstat):
                        self.assertIsNone(file_permissions.secure_sqlite_files(base))
                    self.assertEqual(seen, abspathed, "every sidecar must be probed exactly once, in order")
                    self.assertEqual(
                        [call.args for call in chmod.call_args_list],
                        [(target, wanted) for target, expected in zip(abspathed, expect_chmod) if expected],
                        "chmod must run on the drifted sidecar only, with the private mode",
                    )

if __name__ == "__main__":
    unittest.main()

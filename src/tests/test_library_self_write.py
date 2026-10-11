"""R201 - the library signature must stop churning when fnAudio rewrites its own tags.

Device evidence: ``metadata_tag_idle_interval_ms`` is 250, so the tag writer
revised the user's own audio files continuously.  Both the scan signature and
the fast signature in ``library.py`` folded ``path:st_mtime_ns:st_size`` into
the digest, so ``refresh_library_if_changed`` never took its early exit and a
62,684-track collection was rescanned end to end every cycle.  The folder click
that felt slow was queued behind that loop.

The ledger therefore remembers the revisions this process produced, and the
signature collapses exactly those.  Size is never collapsed, and a revision
that was not recorded still reaches the digest verbatim.
"""

import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, "app/server")

import library
import library_self_write


def fake_stat(mtime_ns, size):
    return types.SimpleNamespace(st_mtime_ns=mtime_ns, st_size=size)


class SelfWriteLedgerTests(unittest.TestCase):
    def setUp(self):
        library_self_write.clear()
        self.addCleanup(library_self_write.clear)

    def test_recorded_revision_matches(self):
        self.assertTrue(library_self_write.record("/music/a.flac", 1000, 20))
        self.assertTrue(library_self_write.matches("/music/a.flac", 1000, 20))

    def test_unrecorded_path_never_matches(self):
        library_self_write.record("/music/a.flac", 1000, 20)
        self.assertFalse(library_self_write.matches("/music/b.flac", 1000, 20))

    def test_both_halves_of_the_revision_must_match(self):
        # A tag write that also grew the file is a real content change: the
        # scanner has to re-read it, so neither slot may be ignored.
        library_self_write.record("/music/a.flac", 1000, 20)
        self.assertFalse(library_self_write.matches("/music/a.flac", 1001, 20))
        self.assertFalse(library_self_write.matches("/music/a.flac", 1000, 21))

    def test_path_normalisation_is_shared(self):
        library_self_write.record("/music/a.flac", 1000, 20)
        self.assertTrue(library_self_write.matches("/music/./a.flac", 1000, 20))

    def test_garbage_input_is_rejected_on_both_sides(self):
        self.assertFalse(library_self_write.record("   ", 1, 1))
        self.assertFalse(library_self_write.record(None, 1, 1))
        self.assertFalse(library_self_write.record("/music/a.flac", "x", 1))
        self.assertFalse(library_self_write.record("/music/a.flac", -1, 1))
        self.assertFalse(library_self_write.matches(None, None, None))
        self.assertFalse(library_self_write.matches("/music/a.flac", 1, None))
        self.assertEqual(library_self_write.tracked_count(), 0)

    def test_record_from_stat_and_matches_stat(self):
        stat = fake_stat(7, 11)
        self.assertTrue(library_self_write.record_from_stat("/music/a.flac", stat))
        self.assertTrue(library_self_write.matches_stat("/music/a.flac", fake_stat(7, 11)))
        self.assertFalse(library_self_write.matches_stat("/music/a.flac", fake_stat(7, 12)))
        self.assertFalse(library_self_write.record_from_stat("/music/b.flac", None))
        self.assertFalse(library_self_write.matches_stat("/music/b.flac", None))

    def test_ledger_is_bounded_by_lru(self):
        original = library_self_write.MAX_TRACKED_REVISIONS
        library_self_write.MAX_TRACKED_REVISIONS = 3
        self.addCleanup(setattr, library_self_write, "MAX_TRACKED_REVISIONS", original)
        for index in range(5):
            library_self_write.record("/music/%d.flac" % index, index, 1)
        self.assertEqual(library_self_write.tracked_count(), 3)
        self.assertFalse(library_self_write.matches("/music/0.flac", 0, 1))
        self.assertFalse(library_self_write.matches("/music/1.flac", 1, 1))
        self.assertTrue(library_self_write.matches("/music/4.flac", 4, 1))


class SignatureTokenTests(unittest.TestCase):
    def setUp(self):
        library_self_write.clear()
        self.addCleanup(library_self_write.clear)

    def test_unrecorded_revision_keeps_the_raw_token(self):
        token = library.signature_token_for_stat("/music/a.flac", fake_stat(1000, 20))
        self.assertEqual(token, "/music/a.flac:1000:20")

    def test_self_written_revision_collapses_only_the_mtime_slot(self):
        library_self_write.record("/music/a.flac", 1000, 20)
        token = library.signature_token_for_stat("/music/a.flac", fake_stat(1000, 20))
        self.assertEqual(token, "/music/a.flac:%s:20" % library.SELF_WRITE_MARKER)
        self.assertNotIn("1000", token)

    def test_size_stays_real_after_a_self_write(self):
        # Growth means content changed, even when the writer is the author.
        library_self_write.record("/music/a.flac", 1000, 20)
        grown = library.signature_token_for_stat("/music/a.flac", fake_stat(1000, 99))
        self.assertNotIn(library.SELF_WRITE_MARKER, grown)
        self.assertTrue(grown.endswith(":99"))


class LibrarySignatureChurnTests(unittest.TestCase):
    def test_consecutive_self_writes_stop_churning_the_signature(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "song.flac")
            with open(path, "wb") as handle:
                handle.write(b"x" * 10)
            base = os.stat(path).st_mtime_ns
            size = os.stat(path).st_size
            library_self_write.record(path, base, size)
            first = library.library_signature(root)
            self.assertTrue(first)

            for step in (1, 2, 3):
                os.utime(path, ns=(base + step * 10 ** 9, base + step * 10 ** 9))
                stat = os.stat(path)
                library_self_write.record(path, stat.st_mtime_ns, stat.st_size)
                self.assertEqual(
                    library.library_signature(root), first,
                    "self write %d rewrote the signature, so the library would rescan again" % step,
                )

    def test_an_unrecorded_write_still_changes_the_signature(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "song.flac")
            with open(path, "wb") as handle:
                handle.write(b"x" * 10)
            base = os.stat(path).st_mtime_ns
            size = os.stat(path).st_size
            library_self_write.record(path, base, size)
            settled = library.library_signature(root)
            os.utime(path, ns=(base + 10 ** 9, base + 10 ** 9))
            self.assertNotEqual(library.library_signature(root), settled)

    def test_clearing_the_ledger_resumes_the_real_revision(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "song.flac")
            with open(path, "wb") as handle:
                handle.write(b"x" * 10)
            stat = os.stat(path)
            raw = library.signature_token_for_stat(path, stat)
            library_self_write.record(path, stat.st_mtime_ns, stat.st_size)
            self.assertNotEqual(library.signature_token_for_stat(path, stat), raw)
            library_self_write.clear()
            self.assertEqual(library.signature_token_for_stat(path, stat), raw)


class SourceWiringTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join("app", "server", "library.py"), encoding="utf-8") as handle:
            self.source = handle.read()

    def test_every_signature_site_uses_the_shared_token_builder(self):
        # Four sites: the CUE file, the audio a CUE references, an ordinary
        # audio file, and the fast filesystem pass.  One raw token left behind
        # would keep the two signatures disagreeing and rescan forever.
        self.assertEqual(self.source.count("signature_token_for_stat("), 5)
        self.assertIn("import library_self_write", self.source)
        for fragment in (
            "signature_parts.append(signature_token_for_stat(full, stat))",
            "signature_parts.append(signature_token_for_stat(audio_path, stat))",
            "append_signature_part(signature_token_for_stat(full, stat))",
        ):
            self.assertIn(fragment, self.source)

    def test_no_raw_revision_token_is_built_anymore(self):
        scan_body = self.source.split("def scan_library(")[1].split("def library_signature(")[0]
        self.assertNotIn('"%s:%s:%s" %', scan_body)

    def test_reuse_still_uses_the_real_mtime(self):
        # A rescanned self-written file must be re-parsed, not served from the
        # stale cache entry, otherwise a tag write would never reach the index.
        self.assertIn(
            "if can_reuse_cached_item(cached, stat.st_size, stat.st_mtime_ns, METADATA_VERSION):",
            self.source,
        )


if __name__ == "__main__":
    unittest.main()

# Tag Integrity Audit

`tools/audit_tag_integrity.py` is a read-only audit for media files that may have been rewritten by the metadata tag writer before 0.1.216.

It uses the existing `library.sqlite3` scan record and current media contents. A high-confidence finding requires either a field that was originally sourced from a Tag but is now absent, or a missing local cover plus a completed `tag_write` job. Files that were simply indexed without a cover are reported only for review.

Run it against a copy of the database and a mounted read-only music-library snapshot first:

```sh
python3 tools/audit_tag_integrity.py \
  --database /path/to/library.sqlite3 \
  --report /path/to/tag-integrity-report.json \
  --csv /path/to/tag-integrity-report.csv
```

The tool never writes media files, SQLite databases, metadata jobs, or cached assets. For high-confidence findings, restore the source file from a NAS snapshot or backup. Only when no backup exists should a separately reviewed metadata backfill be considered; it must not overwrite a non-empty Tag with an empty value.

## Current NAS baseline (2026-08-11)

The read-only audit of the configured library (`/vol1/1000/test`) examined 227 tracks. It found 200 files without an embedded or sidecar cover, but no historical Tag-field regression and no completed `tag_write` record that would make those files high-confidence damage candidates.

The NAS storage layout was also checked read-only: it currently has one ext4 data volume (`/vol1`), no mounted backup volume, no snapshot or recycle directory, and no older `library.sqlite3`. The only fnAudio backup found, `/vol1/@appcenter/fnaudio.backup-codex-20260731-121550`, is application source only. It cannot recover music Tags or cover art.

Recovery therefore remains intentionally blocked until a pre-0.1.213 NAS snapshot, backup, or another copy of the same music library is made available. When one is available, mount or expose it read-only, run the audit against its database/library, and generate a file-by-file recovery candidate list before changing any media file.

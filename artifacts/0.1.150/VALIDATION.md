# fnAudio 0.1.150 FPK Validation

## Build Identity

| Item | Value |
| --- | --- |
| Source | `C:\path\to\fnAudio\src` |
| Source manifest | `fnaudio / 0.1.150 / x86` |
| Build tool | `C:\path\to\fnAudio\tools\fnpack.exe` version `1.2.3` |
| Build command | `C:\path\to\fnAudio\tools\fnpack.exe build --directory C:\path\to\fnAudio\src` |
| Build working directory | `C:\path\to\fnAudio\artifacts\0.1.150` |
| Final package | `fnaudio-0.1.150.fpk` |
| Package size | `4,878,790` bytes |
| Package SHA-256 | `B70EAEE3913AC9AEE8C5CE003C5CC409BC8CF535960B702C19398B593F1A8660` |
| fnpack executable SHA-256 | `D7AF4BD716B009C58F5BCD931615F39DB121E7D4B75DC759E575C4FB2879B6EE` |

## Completed Local Checks

- `python -B -m unittest discover -s tests -v`: 50 tests passed.
- `node --check app/ui/app.js`: passed.
- `node tests/test_ui_queue_columns.js`: passed.
- The outer FPK archive and its inner `app.tgz` were read successfully.
- Packaged manifest confirmed `appname=fnaudio`, `version=0.1.150`,
  `platform=x86`, `desktop_uidir=ui`, and `service_port=18080`.
- Extracted `index.html` references `app.css?v=0.1.150` and
  `app.js?v=0.1.150`.
- The runtime payload contains 97 files, including the server, UI/CGI entry,
  private MPD binary, and dynamic libraries. It excludes tests, historical
  builds, Python bytecode, local SQLite databases, and transcode-cache data.
- The package SHA-256 matches `SHA256SUMS`; the complete file listing is in
  `PACKAGE_CONTENTS.txt`.

## Device Validation Status

This package has not been installed on an fnOS device. The device currently
running the historical `0.1.149` verification package does not contain the
queue current-track positioning/indicator or album-detail sequence-column
changes included in `0.1.150`.

Before declaring a device release, install or upgrade this package and verify
the application-center workflow, CGI page, long-queue jump to the current
track, album-detail sequence column, playback state preservation, and the
existing API/MPD smoke checks.

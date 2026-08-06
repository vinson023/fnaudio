# fnAudio 0.1.152 FPK Validation

## Build Identity

| Item | Value |
| --- | --- |
| Source | `C:\path\to\fnAudio\src` |
| Source manifest | `fnaudio / 0.1.152 / x86` |
| Build tool | `C:\path\to\fnAudio\tools\fnpack.exe` version `1.2.3` |
| Build command | `C:\path\to\fnAudio\tools\fnpack.exe build --directory C:\path\to\fnAudio\src` |
| Final package | `fnaudio-0.1.152.fpk` |
| Package size | `4,878,962` bytes |
| Package SHA-256 | `377C89A25D35CC3B3B7B11950B252840FFD41F62C6B949FFC3EDD774797E6C49` |

## Completed Local Checks

- `python -B -m unittest discover -s tests -v`: 50 tests passed.
- `node --check app/ui/app.js`: passed.
- `node tests/test_ui_queue_columns.js`: passed.
- `node tests/test_ui_mobile_layout.js`: passed, covering the mobile menu/search placement, removed top category tabs, scroll container, pager, back action, and lyrics header structure.
- The outer FPK archive and its inner `app.tgz` were read successfully.
- Packaged manifest confirmed `appname=fnaudio`, `version=0.1.152`, `platform=x86`, `desktop_uidir=ui`, and `service_port=18080`.
- Extracted `index.html` references `app.css?v=0.1.152` and `app.js?v=0.1.152`.
- The runtime payload contains 97 files and excludes tests, historical builds, Python bytecode, local SQLite databases, and transcode-cache data.
- The package SHA-256 matches `SHA256SUMS`; the complete file listing is in `PACKAGE_CONTENTS.txt`.

## fnOS Device Validation

- Installation method: fnOS App Center manual upload and confirmed third-party application upgrade.
- Upgrade path: installed device application `fnaudio 0.1.151` to `0.1.152` without uninstalling the application.
- Post-upgrade status: `fnaudio` reports `version=0.1.152` and `status=running`.
- Mobile viewport checks: the song list scrolls independently above the fixed player; the bottom pager remains visible with first/previous/page/next/last controls; the top category tabs are absent; the search field is available in the left more menu; the left menu contains a return action; and the lyrics header keeps return and favorite controls in separate non-overlapping columns.

## Remaining Device Coverage

This validation does not cover clean installation, port change, stop/start,
either uninstall mode, USB DAC, mobile WebView lifecycle, DLNA interoperability,
or the complete end-to-end flow for "从当前开始播放全部歌曲".

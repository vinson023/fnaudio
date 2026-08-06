# fnAudio 0.1.151 FPK Validation

## Build Identity

| Item | Value |
| --- | --- |
| Source | `C:\path\to\fnAudio\src` |
| Source manifest | `fnaudio / 0.1.151 / x86` |
| Build tool | `C:\path\to\fnAudio\tools\fnpack.exe` version `1.2.3` |
| Build command | `C:\path\to\fnAudio\tools\fnpack.exe build --directory C:\path\to\fnAudio\src` |
| Build working directory | `C:\path\to\fnAudio\artifacts\0.1.151` |
| Final package | `fnaudio-0.1.151.fpk` |
| Package size | `4,878,955` bytes |
| Package SHA-256 | `05CC22B336A9AC821B0166A31D401B0383A425DA88679CA928604F8FCBB6A039` |

## Completed Local Checks

- `python -B -m unittest discover -s tests -v`: 50 tests passed.
- `node --check app/ui/app.js`: passed.
- `node tests/test_ui_queue_columns.js`: passed, including queue track-change presentation and queue-only current-marker assertions.
- The outer FPK archive and its inner `app.tgz` were read successfully.
- Packaged manifest confirmed `appname=fnaudio`, `version=0.1.151`, `platform=x86`, `desktop_uidir=ui`, and `service_port=18080`.
- Extracted `index.html` references `app.css?v=0.1.151` and `app.js?v=0.1.151`.
- The runtime payload contains 97 files and excludes tests, historical builds, Python bytecode, local SQLite databases, and transcode-cache data.
- The package SHA-256 matches `SHA256SUMS`; the complete file listing is in `PACKAGE_CONTENTS.txt`.

## fnOS Device Validation

- Installation method: fnOS App Center manual upload and confirmed third-party application upgrade.
- Upgrade path: installed device application `fnaudio 0.1.150` to `0.1.151` without uninstalling the application.
- Post-upgrade status: `fnaudio` reports `version=0.1.151` and `status=running`.
- State preservation: the existing 228-track library, playback queue, and current playback state remained available after the upgrade.
- Queue behavior: opening the bottom playback queue showed exactly one `正在播放` marker on the current track and opened its page.
- Track change: after selecting next track, the queue immediately rendered the new current track, moved from page `2 / 2` to `1 / 2` when needed, and retained exactly one marker on the new track.
- Scope restriction: the all-music view did not show `正在播放`; reopening the current queue restored the single current marker.

## Remaining Device Coverage

This validation does not cover clean installation, port change, stop/start,
either uninstall mode, USB DAC, mobile WebView, DLNA interoperability,
or the complete end-to-end flow for "从当前开始播放全部歌曲".

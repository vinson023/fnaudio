# fnAudio 0.1.153 FPK Validation

## Build Identity

| Item | Value |
| --- | --- |
| Source | `C:\path\to\fnAudio\src` |
| Source manifest | `fnaudio / 0.1.153 / x86` |
| Build tool | `C:\path\to\fnAudio\tools\fnpack.exe` version `1.2.3` |
| Build command | `C:\path\to\fnAudio\tools\fnpack.exe build --directory C:\path\to\fnAudio\src` |
| Final package | `fnaudio-0.1.153.fpk` |
| Package size | `4,879,159` bytes |
| Package SHA-256 | `A2214FD1A07513634229EAF2A91A685EE60AD56FED25F2BF66CDB6AE62BDB3F0` |

## Completed Local Checks

- `python -B -m unittest discover -s tests -v`: 50 tests passed.
- `node --check app/ui/app.js`: passed.
- `node tests/test_ui_queue_columns.js`: passed.
- `node tests/test_ui_mobile_layout.js`: passed, including the guard for the now-optional `mobileSearchInput` element.
- The outer FPK archive and its inner `app.tgz` were read successfully.
- Packaged manifest confirmed `appname=fnaudio`, `version=0.1.153`, and `platform=x86`.
- Extracted `index.html` references `app.css?v=0.1.153` and `app.js?v=0.1.153`.
- The runtime payload contains 97 files and excludes tests, local databases, and Python bytecode.
- The package SHA-256 matches `SHA256SUMS`; the complete file listing is in `PACKAGE_CONTENTS.txt`.

## Device Validation

- Installation method: fnOS App Center manual upload with the third-party application confirmation.
- Upgrade path: installed device application `fnaudio 0.1.152` to `0.1.153` without uninstalling the application.
- Post-upgrade status: App Center reports `fnaudio`, `version=0.1.153`, `status=running`.
- Service smoke test: `GET /api/health` returned `{"ok":true,"name":"fnAudio","fnos_api_token":false}`; the service was reachable on the expected device port.
- Mobile viewport (`390x844`) smoke checks: the page loaded `app.js?v=0.1.153` without new console errors; the track list uses an independent vertical scroll container; the pager remains a fixed 52px region above the player; top mobile library categories are absent; the more menu exposes search and a return action; search input responds; and the lyrics return/favorite controls occupy separate header columns.

The device library contained zero songs during this run. Real long-list touch scrolling, pager actions, lyrics with an active track, and the complete “从当前开始播放全部歌曲” flow therefore remain unverified.

# fnAudio 0.1.154 FPK Validation

## Build Identity

| Item | Value |
| --- | --- |
| Source | `C:\path\to\fnAudio\src` |
| Source manifest | `fnaudio / 0.1.154 / x86` |
| Build tool | `C:\path\to\fnAudio\tools\fnpack.exe` version `1.2.3` |
| Build command | `C:\path\to\fnAudio\tools\fnpack.exe build --directory C:\path\to\fnAudio\src` |
| Final package | `fnaudio-0.1.154.fpk` |
| Package size | `4,879,719` bytes |
| Package SHA-256 | `81562B56F54490F8C1E84E3D06B76606E2D44AF7B94649C365B364F4B464C2A9` |

## Completed Local Checks

- `python -B -m unittest discover -s tests -q`: 50 tests passed.
- `node --check app/ui/app.js`: passed.
- `node tests/test_ui_queue_columns.js`: passed.
- `node tests/test_ui_mobile_layout.js`: passed, including compact mobile menu styling, lyrics action removal, and conditional mobile pager behavior.
- The outer FPK archive and inner `app.tgz` were read successfully: 18 outer files and 97 runtime files.
- Packaged manifest confirmed `appname=fnaudio`, `version=0.1.154`, and `platform=x86`.
- Extracted `index.html` references `app.css?v=0.1.154` and `app.js?v=0.1.154`.
- Runtime payload excludes tests, local databases, and Python bytecode.

## Device Validation

Pending. The device remains on `fnaudio 0.1.153` because the fnOS App Center manual-install flow requires custom wizard parameters and the in-app browser file chooser could not be triggered reliably. The official `trim-cli app install-fpk` command reached the device but returned `app-center install requires custom wizard parameters`; no upgrade was claimed.

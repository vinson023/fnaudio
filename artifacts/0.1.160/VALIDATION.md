# fnAudio 0.1.160 FPK Validation

## Build Identity

| Item | Value |
| --- | --- |
| Source | `C:\path\to\fnAudio\src` |
| Source manifest | `fnaudio / 0.1.160 / x86` |
| Build tool | `C:\path\to\fnAudio\tools\fnpack.exe` version `1.2.3` |
| Build command | `C:\path\to\fnAudio\tools\fnpack.exe build --directory C:\path\to\fnAudio\src` |
| Final package | `fnaudio-0.1.160.fpk` |
| Package size | `4,880,027` bytes |
| Package SHA-256 | `E224641A09A05F5352BA0A24F02F098CB5E33CE967CA4619E855CE5D740F54CE` |

## Completed Local Checks

- `python -B -m unittest discover -s tests -q`: 50 tests passed.
- `node --check app/ui/app.js`: passed.
- `node tests/test_ui_queue_columns.js`: passed.
- `node tests/test_ui_mobile_layout.js`: passed, including centered mobile pagination, main-page search, compact lyrics header, conditional pager behavior, persistent player visibility during search, and viewport keyboard-overlay declaration.
- The outer FPK archive and inner `app.tgz` were read successfully: 18 outer files and 97 runtime files.
- Packaged manifest confirmed `appname=fnaudio`, `version=0.1.160`, and `platform=x86`.
- Extracted `index.html` references `app.css?v=0.1.160` and `app.js?v=0.1.160`.
- Packaged `app.css`, `index.html`, and `app.js` hashes match the current source files.
- Runtime payload excludes tests, local databases, Python bytecode, and transcode cache.

## Behavior Change

`0.1.159` hid the mobile player while the search input was focused and relied on `blur` to restore it. Some mobile WebViews do not reliably emit that event when the keyboard closes, leaving no way to reopen the player. `0.1.160` keeps the player visible and available at all times; search focus now only applies lower-cost positioning and animation styles.

## Device Validation

Pending. Per user request, the package was not installed by Codex and will be installed and tested by the user. Virtual-keyboard animation smoothness, keyboard overlay behavior, and player interaction require device validation.

# fnAudio 0.1.156 FPK Validation

## Build Identity

| Item | Value |
| --- | --- |
| Source | `C:\path\to\fnAudio\src` |
| Source manifest | `fnaudio / 0.1.156 / x86` |
| Build tool | `C:\path\to\fnAudio\tools\fnpack.exe` version `1.2.3` |
| Build command | `C:\path\to\fnAudio\tools\fnpack.exe build --directory C:\path\to\fnAudio\src` |
| Final package | `fnaudio-0.1.156.fpk` |
| Package size | `4,879,848` bytes |
| Package SHA-256 | `978A582966255E14AF0694685697596FB67A2019EC72FA1DA481E2BFE06BD28F` |

## Completed Local Checks

- `python -B -m unittest discover -s tests -q`: 50 tests passed.
- `node --check app/ui/app.js`: passed.
- `node tests/test_ui_queue_columns.js`: passed.
- `node tests/test_ui_mobile_layout.js`: passed, including the fixed 48px mobile lyrics header, three-column controls, reduced panel padding, compact sidebar, lyrics action removal, and conditional pager behavior.
- The outer FPK archive and inner `app.tgz` were read successfully: 18 outer files and 97 runtime files.
- Packaged manifest confirmed `appname=fnaudio`, `version=0.1.156`, and `platform=x86`.
- Extracted `index.html` references `app.css?v=0.1.156` and `app.js?v=0.1.156`.
- Packaged `app.css`, `index.html`, and `app.js` hashes match the current source files.
- Runtime payload excludes tests, local databases, and Python bytecode.

## Device Validation

Pending. Per user request, the package was not installed by Codex and will be installed and tested by the user.

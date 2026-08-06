# fnAudio 0.1.155 FPK Validation

## Build Identity

| Item | Value |
| --- | --- |
| Source | `C:\path\to\fnAudio\src` |
| Source manifest | `fnaudio / 0.1.155 / x86` |
| Build tool | `C:\path\to\fnAudio\tools\fnpack.exe` version `1.2.3` |
| Build command | `C:\path\to\fnAudio\tools\fnpack.exe build --directory C:\path\to\fnAudio\src` |
| Final package | `fnaudio-0.1.155.fpk` |
| Package size | `4,879,937` bytes |
| Package SHA-256 | `D8FA806C30C6B3CA0C80592CAF4C66CBB02A75230FEDBEAF961E059D626C6474` |

## Completed Local Checks

- `python -B -m unittest discover -s tests -q`: 50 tests passed.
- `node --check app/ui/app.js`: passed.
- `node tests/test_ui_queue_columns.js`: passed.
- `node tests/test_ui_mobile_layout.js`: passed, including the narrower drawer, single-row return/search tools, compact library heading, lyrics action removal, and conditional pager behavior.
- The outer FPK archive and inner `app.tgz` were read successfully: 18 outer files and 97 runtime files.
- Packaged manifest confirmed `appname=fnaudio`, `version=0.1.155`, and `platform=x86`.
- Extracted `index.html` references `app.css?v=0.1.155` and `app.js?v=0.1.155`.
- Runtime payload excludes tests, local databases, and Python bytecode.
- Direct visual rendering of the local `file://` page was blocked by browser security policy; no screenshot-level visual acceptance is claimed.

## Device Validation

Pending. Per user request, the package was not installed by Codex and will be installed and tested by the user.

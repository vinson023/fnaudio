# fnAudio 0.1.159 FPK Validation

## Build Identity

| Item | Value |
| --- | --- |
| Source | `C:\path\to\fnAudio\src` |
| Source manifest | `fnaudio / 0.1.159 / x86` |
| Build tool | `C:\path\to\fnAudio\tools\fnpack.exe` version `1.2.3` |
| Build command | `C:\path\to\fnAudio\tools\fnpack.exe build --directory C:\path\to\fnAudio\src` |
| Final package | `fnaudio-0.1.159.fpk` |
| Package size | `4,879,931` bytes |
| Package SHA-256 | `E20A98721E436D6497C19FD0AA15E3B27AD495E8BB180C9B225E8ED9A467CB43` |

## Completed Local Checks

- `python -B -m unittest discover -s tests -q`: 50 tests passed.
- `node --check app/ui/app.js`: passed.
- `node tests/test_ui_queue_columns.js`: passed.
- `node tests/test_ui_mobile_layout.js`: passed, including centered mobile pagination, non-growing page summary, search-focus player hiding, main-page search, compact lyrics header, and conditional pager behavior.
- The outer FPK archive and inner `app.tgz` were read successfully: 18 outer files and 97 runtime files.
- Packaged manifest confirmed `appname=fnaudio`, `version=0.1.159`, and `platform=x86`.
- Extracted `index.html` references `app.css?v=0.1.159` and `app.js?v=0.1.159`.
- Packaged `app.css`, `index.html`, and `app.js` hashes match the current source files.
- Runtime payload excludes tests, local databases, and Python bytecode.

## Device Validation

Pending. Per user request, the package was not installed by Codex and will be installed and tested by the user. Virtual-keyboard animation smoothness requires device validation.

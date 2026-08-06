# fnAudio 0.1.161 FPK Validation

## Build Identity

| Item | Value |
| --- | --- |
| Source | `C:\path\to\fnAudio\src` |
| Source manifest | `fnaudio / 0.1.161 / x86` |
| Build tool | `C:\path\to\fnAudio\tools\fnpack.exe` version `1.2.3` |
| Build command | `C:\path\to\fnAudio\tools\fnpack.exe build --directory C:\path\to\fnAudio\src` |
| Final package | `fnaudio-0.1.161.fpk` |
| Package size | `4,879,924` bytes |
| Package SHA-256 | `427CA1E87EB6030413B11453AF6D120D6B113C1B2835A54260F4F060342CB875` |

## Completed Local Checks

- `python -B -m unittest discover -s tests -q`: 50 tests passed.
- `node --check app/ui/app.js`: passed.
- `node tests/test_ui_queue_columns.js`: passed.
- `node tests/test_ui_mobile_layout.js`: passed, including fixed player positioning during search, viewport keyboard-overlay declaration, guarded Virtual Keyboard API use, paused search-time layout measurements, centered pagination, and conditional pager behavior.
- The outer FPK archive and inner `app.tgz` were read successfully: 18 outer files and 97 runtime files.
- Packaged manifest confirmed `appname=fnaudio`, `version=0.1.161`, and `platform=x86`.
- Extracted `index.html` references `app.css?v=0.1.161` and `app.js?v=0.1.161`.
- Packaged `app.css`, `index.html`, and `app.js` hashes match the current source files.
- Runtime payload excludes tests, local databases, Python bytecode, and transcode cache.

## Behavior Change

The mobile player remains fixed at the bottom while search is active. Supported WebViews are asked to overlay the virtual keyboard through both `interactive-widget=overlays-content` and `navigator.virtualKeyboard.overlaysContent = true`; unsupported or write-rejecting WebViews safely retain the non-hiding fallback. Marquee and pager layout measurements are skipped during search focus and synchronized once focus ends.

## Device Validation

Pending. Per user request, the package was not installed by Codex and will be installed and tested by the user. fnOS WebView keyboard-overlay support, animation smoothness, and fallback behavior require device validation.

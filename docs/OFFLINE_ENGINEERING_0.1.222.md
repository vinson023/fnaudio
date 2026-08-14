# 0.1.222 offline engineering completion

The nine continuous offline goals requested on 2026-08-12 are complete. No
physical DAC, Renderer, AirPlay receiver, fnOS deployment or Android device was
used for this completion pass.

## Completed scope

1. Scan, metadata, transcode, FFmpeg, cache and disk-watermark work now shares
   explicit resource limits, cancellation and current-track prioritization.
2. MPD failures are classified by media, transport, decoder, output, queue,
   database and backend domain; only real buffer underruns use the legacy
   underrun recovery path.
3. Known mojibake, duplicate definitions and keys, unreachable code, and the
   unused DSD-to-PCM path were removed and are guarded by source-hygiene tests.
4. Playback target, queue, SSE and legacy-payload rules were extracted into a
   compatibility contract. Deprecated write APIs remain as explicit adapters.
5. HTTP authentication and scopes, Range/media streaming, FFmpeg concurrency,
   MPD/FPK lifecycle behavior and Chromium browser flows share one offline test
   entry point.
6. Linux library change detection uses inotify generations and performs the
   O(n) signature fallback only when the monitor is unavailable, dirty,
   overflowed or failed.
7. upmpdcli is compatibility-probe-only. Mixer selection distinguishes fixed
   bit-perfect, verified ALSA hardware volume and non-bit-perfect software
   volume.
8. Android self-signed HTTPS uses credential-free TOFU and pins the full DER
   certificate SHA-256 per saved connection across authentication, WebSocket,
   API/media/artwork requests and WebView SSL handling.
9. Private paths use 0700/0600, public UI paths use 0755/0644, sensitive writes
   are atomic, SQLite sidecars and Tag replacements retain safe permissions,
   and scan/CUE/symlink/uninstall operations enforce path boundaries.

The main fnOS process remains privileged until shared-folder ACL, ALSA/DAC,
SSDP and Tag-write group contracts can be validated on a deployed system. This
is an explicit hardware/deployment dependency, not an unfinished offline task.

## Verification

Run after restoring a future development session:

```powershell
Set-Location C:\path\to\fnAudio
powershell -NoProfile -ExecutionPolicy Bypass -File tools\test_offline.ps1 -Browser
```

The final unified run passed:

- 238 Python tests;
- JavaScript syntax validation;
- five Node UI regressions;
- two Chromium E2E scenarios.

Android verification separately passed two JVM unit tests, `lintDebug` and
`assembleDebug`. The APK reports `versionCode=222`, `versionName=0.1.222` and
`minSdk=23`; its Debug signature verifies with APK Signature Scheme v1 and v2.

The FPK validator inspected the outer package and inner application payload,
including all nine lifecycle commands, manifest resources, permissions, wizard
and required runtime files. The synthetic 100,000-track evidence remains at
`artifacts/large-library-benchmark-100k.json`.

## Final artifacts

- `artifacts/0.1.222/fnaudio-0.1.222-fnpack.fpk`
  SHA-256: `4F9C0A4FBB99959446EE80CBE17354C183822B5095230D2F83DC3E40741CCADF`
- `artifacts/0.1.222/fnaudio-android-0.1.222-debug.apk`
  SHA-256: `415A320369EBE1F171F000BC6482F3CA1C984CB0D943CF882BBEFCA2C05209F5`

`artifacts/0.1.222/SHA256SUMS` is the machine-readable source of truth for the
current files. These results do not replace the physical-device and deployment
acceptance items retained in `TODO.md`.

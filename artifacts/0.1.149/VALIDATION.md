# fnAudio 0.1.149 Test FPK Validation

## Scope and Identity

This is a one-time higher-version package for validating an in-place fnOS
upgrade. It is not a new development or release baseline. The authoritative
source remains `C:\path\to\fnAudio\src` at `0.1.148`.

| Item | Value |
| --- | --- |
| Authoritative source | `C:\path\to\fnAudio\src` |
| Source manifest | `fnaudio / 0.1.148 / x86` |
| Staging source | `artifacts\0.1.149\stage` |
| Staging manifest | `fnaudio / 0.1.149 / x86` |
| Source difference | Only `manifest` version: `0.1.148` to `0.1.149` |
| Build tool | `C:\path\to\fnAudio\tools\fnpack.exe` version `1.2.3` |
| Final package | `artifacts\0.1.149\fnaudio-0.1.149.fpk` |
| Package size | `4,876,087` bytes |
| Package SHA-256 | `B7FD239E26D69AC16CE8C1F4B788AE6528F47E2DBA479FCC33B1CD9B0B507AA0` |
| Outer manifest | `fnaudio / 0.1.149 / x86` |
| Packaged files | 115 entries: 18 outer-package files and 97 files in `app.tgz` |

## Completed Local Checks

- The staged copy was compared to `C:\path\to\fnAudio\src`; the only intended change
  was the manifest version number.
- The package SHA-256 matches `SHA256SUMS`.
- The outer FPK archive was readable and contains the expected manifest,
  lifecycle scripts, configuration, installation wizard, icons, and `app.tgz`.
- The runtime payload contains the server, UI/CGI entry, private MPD binary,
  and required dynamic libraries. It excludes tests, historical builds,
  Python bytecode, local SQLite databases, and transcode cache data.

## fnOS Device Upgrade Validation

The configured fnOS x86 test device accepted the higher-version package through
the application center and upgraded `fnAudio` to `0.1.149`. The application
status was confirmed as `running`. The configured service port remained
`18081`; the music-library configuration and existing playback queue were
preserved.

After the upgrade, device copies of `app.js`, `index.html`, `server.py`, and
`transcode.py` had SHA-256 values matching `C:\path\to\fnAudio\src`. The CGI page also
loaded successfully and displayed the complete music list.

The following read-only endpoint checks passed:

| Endpoint | Result |
| --- | --- |
| `/api/health` | Healthy response |
| `/api/library/status` | 228 tracks, including 5 DSD tracks; configured directories readable |
| `/api/playback/core` | Valid playback-core response |
| `/api/playback/targets` | Valid playback-target response |
| `/api/mpd/status` | MPD `0.23.12` running |

## Feature Checks

### Current-track cache priority

- Test track ID: `d412eb7fd07a94df` (FLAC).
- Initial `/api/transcode/status` response reported `ready: false`.
- `POST /api/transcode/warm` returned `ok: true, queued: true`.
- After approximately six seconds, `/api/transcode/status` reported
  `ready: true`.

### Lyrics-page queue navigation

- The removed top queue control, `lyricsQueueBtn`, is absent.
- The lyrics header contains only back and favorite controls.
- Selecting the bottom player queue control closes the lyrics view and opens
  the current queue view.
- The test session was returned to the all-music view afterward.

## Not Validated in This Device Run

The full "play all songs starting from the current track" end-to-end action
was not run because it would replace the active user queue and playback state.
The implementation is present in the installed source, but this specific
behavior remains a separate manual acceptance item.

Also not covered here: new installation, port reconfiguration, stop/start,
uninstall with retained data, uninstall with purge, USB DAC, FFmpeg under
production load, mobile WebView, and DLNA interoperability.

## Handling Rule

Do not develop from or release `stage/` as a source tree. Future source changes
must start in `C:\path\to\fnAudio\src` with its `0.1.148` manifest version, then create
a separately documented release or test staging package as needed.

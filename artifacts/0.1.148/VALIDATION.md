# fnAudio 0.1.148 FPK Validation

## Build Identity

| Item | Value |
| --- | --- |
| Source | `C:\path\to\fnAudio\src` |
| Source manifest | `fnaudio / 0.1.148 / x86` |
| Build tool | `C:\path\to\fnAudio\tools\fnpack.exe` version `1.2.3` |
| Build command | `C:\path\to\fnAudio\tools\fnpack.exe build --directory C:\path\to\fnAudio\src` |
| Build working directory | `C:\path\to\fnAudio\artifacts` |
| Final package | `artifacts\0.1.148\fnaudio-0.1.148.fpk` |
| Package size | `4,878,142` bytes |
| Package SHA-256 | `856088E19DD926F0ACE2F07C0BB0E76526BB129F6A3A807A27EB2E27686EB4E1` |
| fnpack executable SHA-256 | `D7AF4BD716B009C58F5BCD931615F39DB121E7D4B75DC759E575C4FB2879B6EE` |

## Completed Checks

- `python -B -m unittest discover -s tests -v`: 50 tests passed.
- `node --check app/ui/app.js`: passed.
- `fnpack build --directory C:\path\to\fnAudio\src`: completed successfully.
- FPK outer archive and its inner `app.tgz` were readable by `tar`.
- Packaged manifest confirmed `appname=fnaudio`, `version=0.1.148`,
  `platform=x86`, `desktop_uidir=ui`, `service_port=18080`, and an fnpack
  checksum.
- Runtime payload checks confirmed the server, UI/CGI entry, vendor bridge,
  private MPD binary, and MPD client runtime library.
- Payload check confirmed that tests, historical builds, transcode cache,
  Python bytecode, and local SQLite data were absent.

## Device Installation Attempt

On the configured fnOS x86 test device, the application center accepted the
upload and parsed the FPK, then displayed the normal unverified third-party
application warning. After confirmation, it refused the install with
"已安装相同或更高版本的 fnAudio".

The device already runs an app named `fnaudio` at version `0.1.148`, but its
core file SHA-256 values differ from this source baseline. Its CGI page and
read-only `/api/health`, `/api/library/status`, `/api/playback/core`,
`/api/playback/targets`, and `/api/mpd/status` endpoints responded normally.
Those checks establish that the test device is reachable, its current app is
healthy, and Python 3.12/MPD are available; they do not validate this FPK.

No installed application files, configuration, music-library data, or running
service were replaced during this attempt. To test this exact FPK, explicit
approval is needed to either uninstall the existing same-version app first or
create a separate higher-version test package.

## Outstanding Device Validation

This is a structurally valid local build, not a completed fnOS release
qualification. On a real fnOS x86 device, still verify:

1. Manual installation or `appcenter-cli install-fpk` with the installer wizard.
2. `python312` dependency, desktop entry, CGI proxy, configured port, and logs.
3. New install, overwrite upgrade, port change, start/stop, uninstall with data
   retention, and uninstall with purge.
4. MPD/ALSA, FFmpeg transcode, library authorization, and DLNA behavior.

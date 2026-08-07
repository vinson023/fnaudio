# fnAudio 0.1.168 Validation

## Build identity

| Item | Value |
| --- | --- |
| Build date | `2026-08-07` |
| fnOS source | `C:\path\to\fnAudio\src` |
| Android source | `C:\path\to\fnAudio\android-client` |
| fnOS package | `fnaudio-0.1.168.fpk` |
| FPK size | `4,883,808` bytes |
| FPK SHA-256 | `F363B6C2E23CE7697ECF08E7C81CF7A296696199E3EECC732B8855FE83F30CD4` |
| Android package | `fnaudio-android-0.1.168-debug.apk` |
| APK size | `10,083,946` bytes |
| APK SHA-256 | `A4736CE6F304084B87E9E95BF410051D9BC4E14CB9F649F732D650AD7CD35748` |

## Fix summary

- Root cause: the login form loaded the active profile and retained its UUID. Entering a different NAS then called `upsert()` with the old UUID, replacing the existing history row instead of creating a second one.
- The history page now has an explicit `新增连接` action, following the connection-manager pattern visible in the local flyNas media reference (`fn_connect` assets and `手动添加` entry).
- A connection identity consists of normalized host, port, HTTP/HTTPS mode and username. Changing that identity creates a new UUID; changing only the display name, password or certificate option updates the matching record.
- Selecting `编辑` from history explicitly preserves the selected UUID even when its address changes. Selecting an existing row for login does not create a duplicate.
- Exact duplicate connection identities reuse the existing record instead of adding repeated rows.

## Completed local checks

- 59 Python unit tests passed.
- JavaScript syntax and all 3 Node regression scripts passed.
- Android Java compilation, `:app:lintDebug` and `:app:assembleDebug` passed.
- APK manifest is `com.fnaudio.client / 0.1.168 / versionCode 168 / minSdk 26 / targetSdk 36`.
- APK v2 Debug signature verifies.
- FPK manifest is `fnaudio / 0.1.168 / x86`; outer archive has 21 entries and `app.tgz` has 110 entries with no Python bytecode cache.

## Device validation

Pending. On Android, verify these cases:

1. keep the current connection, change the NAS address or account, log in, and confirm history shows two rows;
2. use `历史连接 -> 新增连接`, log in, and confirm a new row is added;
3. edit an existing row and confirm only that row changes;
4. log in to an already saved identical address/account and confirm no duplicate row appears;
5. delete one row and confirm the other saved connections remain available.

The APK is Debug-signed and intended for development testing only.

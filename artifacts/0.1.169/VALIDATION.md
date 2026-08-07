# fnAudio 0.1.169 Validation

## Build identity

| Item | Value |
| --- | --- |
| Build date | `2026-08-07` |
| fnOS source | `C:\path\to\fnAudio\src` |
| Android source | `C:\path\to\fnAudio\android-client` |
| fnOS package | `fnaudio-0.1.169.fpk` |
| FPK size | `4,884,683` bytes |
| FPK SHA-256 | `E061CA3A761D7BA5E3F6C48604B700E340F938C372A3A90D02C8210C8E2EDD56` |
| Android package | `fnaudio-android-0.1.169-debug.apk` |
| APK size | `10,083,954` bytes |
| APK SHA-256 | `EC2A690930E4560D003CBDF048857E3A75945101C57C1FA0BB559338EDBA7F02` |

## Change summary

- Desktop track rows now open the requested song menu on right-click; mobile track rows open the same menu after a 550 ms long-press.
- Moving more than 10 px, cancelling the pointer or scrolling the library cancels a pending long-press. A successful long-press suppresses the following synthetic click so the song is not played accidentally.
- The context menu contains exactly four actions in this order: `从当前开始播放所有歌曲`, `加入当前队列`, `收藏歌曲`, `加入播放列表`.
- `收藏歌曲` is additive: an already-favorited track remains favorited instead of being toggled off under an additive label.
- `从当前开始播放所有歌曲` still calls `allTracksForCurrentContext()` and therefore keeps the previous complete-list behavior instead of using only the visible page.
- Mobile context-menu targets use larger 44 px action rows and stay inside the viewport.

## Completed local checks

- 59 Python unit tests passed.
- JavaScript syntax and all 3 Node regression scripts passed.
- Android Java compilation, `:app:lintDebug` and `:app:assembleDebug` passed.
- APK manifest is `com.fnaudio.client / 0.1.169 / versionCode 169 / minSdk 26 / targetSdk 36`.
- APK v2 Debug signature verifies.
- FPK manifest is `fnaudio / 0.1.169 / x86`; outer archive has 21 entries and `app.tgz` has 110 entries with no Python bytecode cache.
- Packaged `ui/app.js` and `ui/app.css` SHA-256 values match the source files, and packaged `index.html` references cache version `0.1.169`.

## Device validation

Not performed in this build session. Install the FPK and paired APK, then verify:

1. desktop right-click opens the four actions in the documented order;
2. mobile long-press opens the menu, while vertical scrolling does not;
3. releasing after long-press does not start playback;
4. `从当前开始播放所有歌曲` begins at the pressed track and queues every remaining song in the full current view;
5. favoriting an already-favorited track does not remove it;
6. add-to-queue and add-to-playlist work from both browser and Android WebView.

The APK is Debug-signed and intended for development testing only.

# fnAudio 0.1.173 构建与验证记录

## 产物

| 文件 | 大小 | SHA-256 |
| --- | ---: | --- |
| `fnaudio-0.1.173.fpk` | 4,884,758 bytes | `73A3561DE87B8AA82C260BBF35B1FF3FBFC114DE75EA4DC78C2FE8881B7961ED` |
| `fnaudio-android-0.1.173-debug.apk` | 10,253,139 bytes | `B91D17031E0E7E2FD0820CB6B81ECFA1DBE9FF9982AB1CE774B025CA425F35FD` |

## 源码与构建

- 工作树：`C:\path\to\fnAudio`
- 分支：`main`
- 根 `VERSION`、FPK manifest 和 Android `versionName`：`0.1.173`
- Android `versionCode`：`173`
- FPK：`fnaudio / 0.1.173 / x86`
- FPK 构建：`tools\fnpack.exe build --directory C:\path\to\fnAudio\src`
- Android 构建：`gradlew.bat :app:lintDebug :app:assembleDebug`

## 本地验证

- 62 个 Python 单元测试通过。
- JavaScript 语法、队列/列、移动布局、Android bridge/CGI 认证回归通过。
- Android Lint 与 Debug APK 构建通过。
- APK badging：`com.fnaudio.client / versionCode 173 / versionName 0.1.173 / minSdk 23 / targetSdk 36`。
- APK v1/v2 Debug 签名验证通过；签名者为 Android Debug。
- FPK 外层 21 个条目，`app.tgz` 内层 114 个条目，未包含 `.pyc`。

## 验证边界

本轮没有安装到 fnOS、USB DAC、DLNA Renderer 或 Android 真机，因此不宣称八类现场问题已经全部闭环。特别是 Android 远程输出通知/锁屏媒体卡片和不支持 NextURI 的 DLNA 设备后台连续播放仍列为后续 P0/P1 工作。

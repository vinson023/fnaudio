# fnAudio 0.1.172 构建与验证记录

## 产物

| 文件 | 大小 | SHA-256 |
| --- | ---: | --- |
| `fnaudio-0.1.172.fpk` | 4,885,254 bytes | `74B10F51AEF82A6BD4B9928EB316868168E03AB6548991E4C012279FF0D1385E` |
| `fnaudio-android-0.1.172-debug.apk` | 10,090,184 bytes | `EC61FEE7926064BF69D34DF6A61EEBAAC14E7EFBE4B1BA3A9D39613BF8EE60E1` |

## 源码身份

- 工作树：`C:\path\to\fnAudio`
- 分支：`main`
- 版本：根 `VERSION`、`src/manifest`、Android `versionName` 均为 `0.1.172`
- Android `versionCode`：`172`
- FPK manifest：`fnaudio / 0.1.172 / x86`
- FPK 构建命令：`C:\path\to\fnAudio\tools\fnpack.exe build --directory C:\path\to\fnAudio\src`
- Android 构建命令：`android-client\gradlew.bat :app:lintDebug :app:assembleDebug`

## 本地验证

以下检查均通过：

- 59 个 Python 单元测试：`python -B -m unittest discover -s tests`
- JavaScript 语法：`node --check app/ui/app.js`
- UI 队列/专辑列/PC 与移动菜单回归：`node tests/test_ui_queue_columns.js`
- 移动端布局回归：`node tests/test_ui_mobile_layout.js`
- Android 桥接与 CGI 认证回归：`node tests/test_ui_android_bridge.js`
- Android Lint：Gradle `:app:lintDebug`
- Android Debug APK：Gradle `:app:assembleDebug`
- APK badging：`com.fnaudio.client / versionCode 172 / versionName 0.1.172 / minSdk 26 / targetSdk 36`
- APK 签名：`apksigner` 验证通过，使用 APK Signature Scheme v2，1 个签名者

## 包结构

- FPK 外层 21 个条目。
- `app.tgz` 内层 110 个条目。
- 包内未发现 Python 字节码（`.pyc`）。
- `PACKAGE_CONTENTS.txt` 保存外层条目清单；`SHA256SUMS` 保存发布包校验值。

## 本轮修改

- PC 歌曲/分组右键菜单移除“播放”和“插播所选项目”；移动端四项长按菜单与歌曲操作对话框保持独立。
- “打开包含的文件夹”只向 fnOS `openFileManager()` 传入歌曲父目录，避免把完整音频路径误解释为打开文件。

## 未完成的设备验证

本轮没有连接 fnOS 或 Android 真机，未宣称安装、覆盖升级、文件管理视觉定位、Android 通知封面和后台播放已通过。公开宿主接口目前只确认目录跳转语义，未确认可以通过额外参数自动选中文件；该限制已记录在 `PROJECT_CONTEXT.md`、`DECISIONS.md` 和 `CHANGELOG_AI.md`。

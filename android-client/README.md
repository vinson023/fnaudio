# fnAudio Android 客户端

这是 fnAudio `0.2.44` 的轻量混合客户端：WebView 继续承载现有界面，Android Media3 前台媒体服务持有本机播放，并在远程输出时维护不解码音频的媒体会话。当前配套服务端版本基线为 `0.2.44`。

## 已实现

- 输入 NAS 地址、端口、HTTPS、自签名证书兼容、账号和密码。
- 通过 fnOS `/websocket?type=main` 执行 `user.login`；兼容 `user` / `username` 字段差异。
- 使用 Android Keystore 加密保存多个连接的账号、密码、短令牌和长令牌；应用数据禁止系统备份。
- 登录页通过单独按钮打开历史连接页，可在独立页面选择、编辑、删除或新增连接。修改 NAS 地址、端口、协议或账号会保存为新记录，只有明确点击“编辑”才覆盖所选记录。
- 登录后直接加载 `/cgi/ThirdParty/fnaudio/index.cgi/`，不打开 fnOS 桌面。
- WebView 通过 `FnAudioNative` 桥把队列、播放、暂停、切歌、seek、音量、循环和随机发送给 Media3。
- WebView 的 fnAudio 非 GET API 通过同一桥交给原生 OkHttp，统一附加 `Authorization`、`X-Fnaudio-Trim-Token` 和同源 token Cookie；普通浏览器仍使用标准 Fetch。
- FN Connect 先探测官方公网候选，均不可达时在原生 ARM64 设备上通过签名 `/api/v1/visit/info` 配置 Tpps V2 回环隧道；中继凭据仅驻留内存，x86/非 ARM64 自动回退直连。
- `MediaSessionService + ExoPlayer` 负责完整队列、自动下一首、通知、媒体按键、音频焦点、耳机拔出和唤醒锁。
- HTTP、系统 CA HTTPS 和用户明确允许的自签名 HTTPS；自签名连接首次认证前固定完整证书 SHA-256，后续 WebSocket、API、媒体、封面和 WebView 必须匹配，证书变化会明确拒绝。
- Android 返回键优先交给网页关闭对话框、侧栏、歌词和分类详情；根页面第一次返回显示退出提示，2.2 秒内第二次返回登录界面，并禁止登录页自动恢复上次连接。
- WebView 中长按歌曲 550ms 可打开与桌面右键一致的四项菜单；滚动会取消长按，松手不会误触歌曲播放。
- Media3 通知小图标和无封面歌曲的媒体卡片占位图使用白色播放圆环；有真实封面时仍使用真实封面。

## 构建

环境：JDK 17 或更新版本、Android SDK Platform 36、Build Tools 36.0.0。Gradle Wrapper 会下载 Gradle 9.6.1。

```powershell
Set-Location C:\path\to\fnAudio\android-client
$env:ANDROID_SDK_ROOT = 'E:\Codex\android-sdk'
.\gradlew.bat :app:lintDebug :app:assembleDebug
```

输出：`app\build\outputs\apk\debug\app-debug.apk`。

### Android 模拟器自动化

首次安装本机 Emulator 与 API 35 ATD 镜像并执行 instrumented tests：

```powershell
Set-Location C:\path\to\fnAudio
powershell -NoProfile -ExecutionPolicy Bypass -File tools\test_android_emulator.ps1 -InstallSdk
```

后续运行可省略 `-InstallSdk`。该入口覆盖加密多连接记录、登录历史界面、
自签名 HTTPS 指纹固定以及 Media3 远程命令转发；完整范围和真机边界见
`docs/ANDROID_EMULATOR_TESTING.md`。

### Release 签名

正式包不会内置仓库密钥。构建机器必须通过 Gradle properties 或环境变量提供 keystore：

```powershell
$env:FNAUDIO_RELEASE_STORE_FILE = 'E:\secrets\fnaudio-release.jks'
$env:FNAUDIO_RELEASE_STORE_PASSWORD = '...'
$env:FNAUDIO_RELEASE_KEY_ALIAS = 'fnaudio'
$env:FNAUDIO_RELEASE_KEY_PASSWORD = '...'
.\gradlew.bat :app:assembleRelease
```

也可以使用 `-PfnaudioReleaseStoreFile=...` 等同名 Gradle properties。密钥文件和密码不得提交到 Git；未提供完整参数或 keystore 不存在时，`assembleRelease` 会明确失败，不能误产出未签名发布包。

## 与 fnAudio 服务端的配套要求

必须安装 `fnAudio 0.2.14` 或更新版本。该版本包含 MPD/DLNA 服务端状态同步、Renderer 后台自动推进、DSD 原始推送、远程 MediaSession、启动 token 刷新、API scope 授权和播放快照契约。网页桥在选择当前设备时使用 ExoPlayer；选择 USB DAC、MPD 或 DLNA 时切换为仅镜像状态和转发控制的远程播放器。

## 尚待真机确认

- 不同 fnOS 固件是否都接受 WebSocket 登录令牌作为 CGI 的 Cookie/Authorization 会话。
- 2FA、验证码、账号冻结和长令牌签名恢复流程。
- 各手机厂商后台限制、息屏连续播放、蓝牙/有线耳机媒体按键和来电抢占。
- Android 端自签名 HTTPS 首次固定、证书变化拒绝、外网反向代理和 IPv6 的真机行为。
- 正式发布签名、升级密钥保管和 Play Protect/厂商安装器提示。

Debug APK 使用 Android 调试证书，只适合当前开发验证，不应作为正式发布包。


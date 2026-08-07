# fnAudio Android 客户端

这是 fnAudio `0.1.166` 的轻量混合客户端：WebView 继续承载现有界面，Android Media3 前台媒体服务持有播放队列和音频输出。

## 已实现

- 输入 NAS 地址、端口、HTTPS、自签名证书兼容、账号和密码。
- 通过 fnOS `/websocket?type=main` 执行 `user.login`；兼容 `user` / `username` 字段差异。
- 使用 Android Keystore 加密保存多个连接的账号、密码、短令牌和长令牌；应用数据禁止系统备份。
- 登录页通过单独按钮打开历史连接页，可在独立页面选择、编辑或删除连接。
- 登录后直接加载 `/cgi/ThirdParty/fnaudio/index.cgi/`，不打开 fnOS 桌面。
- WebView 通过 `FnAudioNative` 桥把队列、播放、暂停、切歌、seek、音量、循环和随机发送给 Media3。
- `MediaSessionService + ExoPlayer` 负责完整队列、自动下一首、通知、媒体按键、音频焦点、耳机拔出和唤醒锁。
- HTTP、HTTPS 和用户明确允许的自签名证书连接；原生媒体请求携带同一 fnOS 会话。
- Android 返回键优先交给网页关闭对话框、侧栏、歌词和分类详情；位于 fnAudio 根页面时仅把应用任务移到后台。登录成功后登录 Activity 会退出返回栈，不会被返回键重新打开。

## 构建

环境：JDK 17 或更新版本、Android SDK Platform 36、Build Tools 36.0.0。Gradle Wrapper 会下载 Gradle 9.6.1。

```powershell
Set-Location C:\path\to\fnAudio\android-client
$env:ANDROID_SDK_ROOT = 'E:\Codex\android-sdk'
.\gradlew.bat :app:lintDebug :app:assembleDebug
```

输出：`app\build\outputs\apk\debug\app-debug.apk`。

## 与 fnAudio 服务端的配套要求

必须安装 `fnAudio 0.1.166` 或更新版本。该版本会为 CGI 入口修正网页静态资源基准路径，并通过 `REQUEST_URI` 与显式路由 Header 可靠恢复播放队列 POST 的 API 路径；同时从同源 `fnaudio_trim_token` Cookie 恢复 fnOS token。网页桥在 Android 客户端存在时停止使用 HTML `<audio>`，避免网页和原生播放器同时出声。登录和主页面会根据状态栏/刘海 Insets 自动留出安全区域。

## 尚待真机确认

- 不同 fnOS 固件是否都接受 WebSocket 登录令牌作为 CGI 的 Cookie/Authorization 会话。
- 2FA、验证码、账号冻结和长令牌签名恢复流程。
- 各手机厂商后台限制、息屏连续播放、蓝牙/有线耳机媒体按键和来电抢占。
- Android 端自签名 HTTPS、外网反向代理、IPv6 和证书更新。
- 正式发布签名、升级密钥保管和 Play Protect/厂商安装器提示。

Debug APK 使用 Android 调试证书，只适合当前开发验证，不应作为正式发布包。

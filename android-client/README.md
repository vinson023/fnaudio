# fnAudio Android 客户端

这是 fnAudio `0.1.168` 的轻量混合客户端：WebView 继续承载现有界面，Android Media3 前台媒体服务持有播放队列和音频输出。

## 已实现

- 输入 NAS 地址、端口、HTTPS、自签名证书兼容、账号和密码。
- 通过 fnOS `/websocket?type=main` 执行 `user.login`；兼容 `user` / `username` 字段差异。
- 使用 Android Keystore 加密保存多个连接的账号、密码、短令牌和长令牌；应用数据禁止系统备份。
- 登录页通过单独按钮打开历史连接页，可在独立页面选择、编辑、删除或新增连接。修改 NAS 地址、端口、协议或账号会保存为新记录，只有明确点击“编辑”才覆盖所选记录。
- 登录后直接加载 `/cgi/ThirdParty/fnaudio/index.cgi/`，不打开 fnOS 桌面。
- WebView 通过 `FnAudioNative` 桥把队列、播放、暂停、切歌、seek、音量、循环和随机发送给 Media3。
- WebView 的 fnAudio 非 GET API 通过同一桥交给原生 OkHttp，统一附加 `Authorization`、`X-Fnaudio-Trim-Token` 和同源 token Cookie；普通浏览器仍使用标准 Fetch。
- `MediaSessionService + ExoPlayer` 负责完整队列、自动下一首、通知、媒体按键、音频焦点、耳机拔出和唤醒锁。
- HTTP、HTTPS 和用户明确允许的自签名证书连接；原生媒体请求携带同一 fnOS 会话。
- Android 返回键优先交给网页关闭对话框、侧栏、歌词和分类详情；根页面第一次返回显示退出提示，2.2 秒内第二次返回登录界面，并禁止登录页自动恢复上次连接。

## 构建

环境：JDK 17 或更新版本、Android SDK Platform 36、Build Tools 36.0.0。Gradle Wrapper 会下载 Gradle 9.6.1。

```powershell
Set-Location C:\path\to\fnAudio\android-client
$env:ANDROID_SDK_ROOT = 'E:\Codex\android-sdk'
.\gradlew.bat :app:lintDebug :app:assembleDebug
```

输出：`app\build\outputs\apk\debug\app-debug.apk`。

## 与 fnAudio 服务端的配套要求

必须安装 `fnAudio 0.1.168` 或更新版本。该版本与 Android 多连接历史、原生认证 HTTP 桥和网页回调协议配套，并保留 CGI 静态资源基准路径和路由恢复。网页桥在 Android 客户端存在时停止使用 HTML `<audio>`，避免网页和原生播放器同时出声。

## 尚待真机确认

- 不同 fnOS 固件是否都接受 WebSocket 登录令牌作为 CGI 的 Cookie/Authorization 会话。
- 2FA、验证码、账号冻结和长令牌签名恢复流程。
- 各手机厂商后台限制、息屏连续播放、蓝牙/有线耳机媒体按键和来电抢占。
- Android 端自签名 HTTPS、外网反向代理、IPv6 和证书更新。
- 正式发布签名、升级密钥保管和 Play Protect/厂商安装器提示。

Debug APK 使用 Android 调试证书，只适合当前开发验证，不应作为正式发布包。

# fnAudio 0.1.176 — Android 远程播放 MediaSession

## 变更

本版本解决 Android 选择 USB DAC、MPD 或 DLNA 输出后通知栏和锁屏媒体卡片消失的问题。

Android 新增 `RemotePlaybackPlayer`。它只保存队列元数据、播放状态、进度和控制代理，不打开远程音频 URL，不解码、不输出手机声音，也不额外抢占手机音频焦点。通知栏和锁屏操作通过原生认证 HTTP 请求转发到 fnAudio `/api/playback/control`，状态通过 `/api/playback/status` 独立轮询。

实现方式参考 Volumio 的 `pushState`/命令路由和 moOde 的 MPD `status`、`currentsong`、控制命令分离模型：实际输出设备是播放状态权威，客户端媒体会话只是控制面板。

## 验证

- 63 个 Python 测试通过。
- JavaScript 语法检查和 Android bridge 静态回归通过。
- Android `lintDebug`、`assembleDebug` 通过。
- FPK manifest 版本为 `0.1.176`。
- APK `com.fnaudio.client`，versionCode `176`，versionName `0.1.176`，v1/v2 签名验证通过。
- 真实 Android 手机通知栏、锁屏、USB DAC 和 DLNA 连续播放仍需设备验收。

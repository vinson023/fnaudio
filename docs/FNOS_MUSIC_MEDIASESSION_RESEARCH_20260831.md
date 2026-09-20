# 飞牛音乐宿主 MediaSession 研究（2026-08-31）
 

## FPK 启动容器对照（2026-08-31，测试机实测）

测试机 `198.51.100.24` 上的官方音乐包并不是 App Center iframe 微应用：

| 项目 | 官方 `trim.music` | 调整前 fnAudio | fnAudio 对齐后 |
| --- | --- | --- | --- |
| manifest 启动标记 | `native_app=true` | `micro_app=true` | `native_app=true` |
| UI 入口类型 | `url` | `iframe` | `url` |
| 移动入口 URL | `/music` | `/cgi/ThirdParty/fnaudio/index.cgi/` | 保持 CGI URL |

官方包的 `/var/apps_ui/trim.music/config` 以全页 URL 入口启动；fnAudio 的 CGI 代理仍是认证、
端口发现和 API 路由的必要组成，因此只替换宿主容器模型，不替换 URL 或绕开 CGI。此改动的目的
是让飞牛 APP 以与官方音乐相同的全页 WebView 路径加载 fnAudio，从而允许宿主正常观察网页的
标准 Web Media Session 生命周期；它**不等于**已经获得私有播放会话、系统浮窗或保活权限。

已为该结构增加 `test_fnos_native_app_launch.py`，避免后续发布误退回 `iframe + micro_app`。

### 小米 15 Pro 运行态验证

在 `baf83ddd` 上从飞牛 APP 的“应用中心 → 已安装 → fnAudio → 打开”验证后，窗口焦点保持为
`com.trim.app/.MainActivity`，页面树为飞牛 APP 内的 `android.webkit.WebView`，并直接显示 fnAudio
曲库与底部控制栏；不再跳转到 App Center 的应用运行状态页。截图保存在
`artifacts/fnos-fnaudio-native-launch-20260831.png`。

随后强制停止独立 `com.fnaudio.client`，排除独立 Android 客户端的 Media3 会话干扰。此时系统中
只剩官方 `com.trim.app/media-session`，仍为 `active=false`、`state=NONE`，且没有飞牛 APP 的媒体
通知。这表明全页容器对齐已生效，但飞牛 APP 尚未因“加载第三方 FPK 页面且存在当前曲目”而自动
激活其私有播放会话；真正的播放态及宿主桥接仍需进一步验证。

## 面向 FPK 宿主的边界（2026-08-31，已由小米 15 Pro 修正）

`trim.music` 的静态 Web 包中没有发现可供第三方 FPK 页面调用的飞牛 MediaSession JavaScript
方法；`window.NativeShell` 仅出现在编解码能力探测。通知、锁屏、保活和浮窗由飞牛 APP 自己的
`audio_service`/私有 `trim_base_plugin` 创建。fnAudio 现提供
`window.fnAudioMediaSessionDiagnostics()`，可在飞牛 APP WebView 中确认支持状态、注册动作、
宿主类型和当前会话状态。实现官方同等浮窗仍需飞牛公开第三方播放会话桥接。

这不是“官方音乐未使用私有通道”的结论。相反，最新真机证据确认官方音乐使用了私有通道；目前
尚未捕获到的是该通道的 participant 载荷、调用来源和第三方应用身份校验。不能把私有 Pigeon
名或猜测出的二进制 payload 直接写进 fnAudio，否则只会得到不稳定、不可维护的伪兼容。
## 结论

测试机上的飞牛音乐是 `/usr/local/apps/@appcenter/trim.music/trim-music` 服务（当前监听 18080），移动端页面由飞牛 APP 宿主承载。音乐前端使用标准浏览器 `navigator.mediaSession`：注册 play/pause/上一首/下一首/seek 操作，并同步 `MediaMetadata`、封面和 `playbackState`。真正提供锁屏、通知和后台保活的是飞牛 APP 内置的 Flutter `audio_service`。

## 1.35.2 静态证据

反编译目录：`_external/apk-analysis/fnos-1.35.2-source`。

- `com.ryanheise.audioservice.AudioService extends MediaBrowserServiceCompat`。
- `onCreate()` 创建 `MediaSessionCompat("media-session")`，设置 playback actions、callback、queue、`PARTIAL_WAKE_LOCK`，并创建网络 `WifiLock`。
- 进入播放态时同时执行 `setActive(true)`、创建/刷新前台通知、设置 `setSessionActivity(...)` 并持有 WakeLock。
- `onTaskRemoved()` 回调 Flutter 层后调用父类，不主动停止服务。
- 通知使用 session token、真实 Bitmap 封面和 session activity PendingIntent。
- 官方新版本还增加了服务状态/锁/网络/切源租约的诊断字段，便于定位后台播放问题。

## 跨平台播放会话协议（trim_base_plugin）

新版 `lib/arm64-v8a/libapp.so` 和反编译 Java 共同显示，飞牛音乐的跨平台关键在
`trim_base_plugin`，而不是网页直接调用某个平台私有 API：

- `HostPlaybackSessionApi` 通过 Flutter Pigeon 暴露统一宿主接口：
  `initialize`、`synchronize`、`registerParticipant`、`unregisterParticipant`、
  `requestActivation`、`reportParticipantState`、`reportUserStopped`、
  `reportRemoteUserPaused`、`acknowledgeCommand`。
- `FlutterPlaybackSessionApi` 负责把 `onSessionSnapshotChanged`、
  `onSessionDiagnostic`、`onCoordinatorCommand` 回传 Flutter 层；因此页面、后台服务和
  输出设备不会各自维护一份“当前播放”状态。
- participant 记录至少包含 participantId、generation、engineEpoch、是否支持前台恢复、
  前台恢复协议版本、是否支持后台播放、是否正在播放、用户是否希望播放以及
  mediaContextId。generation/engineEpoch 用于丢弃旧播放器或旧页面发来的迟到事件。
- 协调器为播放/暂停/恢复建立带 UUID 的 command ticket，并要求 participant 回执；
  中断、输出路由切换、前台恢复分别有独立 ticket，避免重复恢复或重复切歌。
- `HostKeepAliveApi.startKeepAlive` / `cancelKeepAlive` 是宿主保活租约，不等同于
  Android WakeLock：Android 可映射到前台服务，iOS 可映射到后台音频会话，鸿蒙可映射到
  对应的后台任务/音频能力。
- `BackgroundPlayerLifecycle`、`allowBackgroundAudioPlaying`、
  `beginMediaSession`、`clearMediaSession`、`setNetworkPlaybackRequired`、
  `refreshNotification` 组成宿主生命周期层；网页只负责标准 Media Session 元数据和操作。
- `HarmonyUtilApi.isHarmonyOS` / `harmonyOSVersion` 表明鸿蒙是能力探测后走宿主适配，
  不是把 Android MediaSession 直接照搬过去。iOS 字符串证据包含
  `AVAudioSessionCategoryPlayback`、`AVAudioSessionSetActiveOptions` 和
  `com.trim.app.ios`，对应 AVAudioSession + 后台音频能力。

### 推断出的时序

```text
Flutter 页面/播放器
  -> initialize()
  -> registerParticipant(engineEpoch, capabilities)
  -> synchronize(snapshot)
  -> requestActivation(participantId, mediaContextId)
  -> reportParticipantState(playing/paused/position)
宿主协调器
  -> onSessionSnapshotChanged(snapshot)
  -> onCoordinatorCommand(ticket)
participant 执行命令
  -> acknowledgeCommand(ticket, result)
宿主
  -> Android MediaSession / iOS AVAudioSession / Harmony 音频宿主
```

`synchronize` 和 `generation/engineEpoch` 是恢复登录、切换页面、切换输出设备时避免
“旧页面覆盖新状态”的核心；`acknowledgeCommand` 则是避免通知栏或蓝牙按键重复执行的核心。

## fnAudio 对齐改动

`android-client/app/src/main/java/com/fnaudio/client/playback/PlaybackService.java` 保留 Media3，不做高风险框架替换：

- Media3 `MediaSession.Builder.setSessionActivity(...)` 指向已有的 `MainActivity.ACTION_OPEN_PLAYBACK`，通知点击复用现有任务而不重载页面。
- 远程/DLNA 输出启用独立 `PARTIAL_WAKE_LOCK` 与高性能 `WifiLock`，切回本机或销毁服务时释放。
- 服务返回 `START_STICKY`；远程任务被移除时重新确认前台通知并调用 `super.onTaskRemoved(...)`。

### 对 fnAudio 的可复用边界

不建议复制官方混淆后的 Pigeon 类名或私有二进制协议；建议在 fnAudio 后端建立等价、
可测试的四个抽象：

1. `PlaybackParticipant`：输出目标（当前设备、USB DAC、DLNA/UPnP、AirPlay）的能力、
   generation 和 engineEpoch。
2. `PlaybackSessionSnapshot`：版本号、当前曲目、播放状态、位置、输出目标和恢复原因，
   作为浏览器、Android 通知和远程输出的唯一状态源。
3. `KeepAliveLease`：把前台服务/WakeLock/WifiLock 或其他平台保活实现隐藏在宿主适配器后。
4. `CommandTicket`：为播放、暂停、恢复、下一首及输出切换提供幂等 ID、超时和确认结果。

浏览器继续使用标准 `navigator.mediaSession`；Android 将快照映射到 Media3
`MediaSession`；iOS/鸿蒙客户端只需实现同一快照与命令协议，不应让各端自行轮询、判断
播放完成或切歌。这样才能获得 trim.music 的跨平台一致性，同时避免依赖飞牛 APP 的私有
Flutter 通道。

## 动态验收状态

- 测试机 SSH 可用；已确认 trim.music 服务、18080 端口和静态资源。
- 小米 15 Pro（ADB serial `baf83ddd`）现已连接，已取得官方音乐的通知、锁屏 MediaSession、
 运行服务、页面返回和迷你播放器动态证据；文件位于 `artifacts/trim-music-live-*`。

## 小米 15 Pro 动态对照（2026-08-31）

- 已安装 `com.trim.app` 1.35.2 与 fnAudio debug 客户端。飞牛 APP 空闲时确实创建了
  `com.trim.app/media-session`，但状态为 `NONE`、`active=false`、无 metadata；这证明服务
  具备宿主 MediaSession，并不证明页面已把播放会话接入宿主。
- fnAudio 当前会话在 `dumpsys media_session` 中显示为 Media3 session，带队列、metadata 和
  `PAUSED` 状态；通知记录使用 `android.app.Notification$MediaStyle`、MediaSession token 和
  前台媒体 channel。对应原始快照保存在 `artifacts/media-session-fnaudio-main.txt` 和
  `artifacts/notification-baf83ddd.txt`。
- 尚未完成的关键动态证据是：在飞牛 APP 内打开 fnAudio 页面并实际播放后，确认宿主是否把
  Web Media Session 转换为 `com.trim.app/media-session`。当前没有证据表明它会自动转换，不能
  将 fnAudio 自己的 Media3 通知误称为官方宿主浮窗。

## 官方前端补充静态证据（2026-08-31）

对缓存的官方 `trim-music-main.js` 做字符串与上下文检查，`window.NativeShell` 仅出现在播放能力
探测路径（例如编解码等级判断），未发现网页层通知、锁屏、媒体键或浮窗控制调用。官方网页播放层
仍直接使用 `navigator.mediaSession`，并通过内部 playback-session 对象维护心跳与释放。因此目前
没有证据证明第三方 FPK 页面可以直接调用官方协调器。

## 小米 15 Pro 官方音乐实播证据（2026-08-31）

已在飞牛 APP 1.35.2 内实际进入“应用中心 → 音乐 → 打开”，播放官方曲库歌曲，并以每次只做
一个动作的方式清空并导出 logcat、MediaSession、通知和服务快照。结果如下：

- 真实会话为 `com.trim.app/media-session/32`，播放态为 `PLAYING`，包含曲目、歌手、封面、
  上一首/暂停/下一首及“收藏”自定义动作。
- `com.trim.app/com.ryanheise.audioservice.AudioService` 在播放时是
  `FOREGROUND_SERVICE_MEDIA_PLAYBACK` 前台服务；通知频道为 `com.trim.fn_music.playback`，
  使用 `Notification.MediaStyle`，ID 为 `1124`。
- 发送系统媒体键 `KEYCODE_MEDIA_PLAY_PAUSE` 后，官方会话从 `PLAYING` 变为 `PAUSED`，
  前台服务退出 foreground；再次发送后恢复 `PLAYING` 并再次进入 foreground。这证明媒体键的
  回传和通知生命周期实际由宿主 `audio_service` 处理。
- 从官方音乐返回飞牛 APP“应用中心”后，右下角出现可恢复官方音乐的迷你播放器。这不是
  `TYPE_APPLICATION_OVERLAY` 系统悬浮窗，而是同一个 `com.trim.app/.MainActivity` Flutter 页面
  根据内部会话状态渲染的 UI；点击封面会回到官方音乐播放页。
- 官方音乐 FPK 仍含独立 React 静态包（`/music/static`），但 Android 实播页不存在 WebView
  DevTools socket，且 UI 树均为 Flutter `android.view.View`。同时 APK AOT 中出现
  `MusicPlaybackTaskCoordinator`、`bind native playback-session participant generation=`、
  `native participant registration failed:`、`playbackRecoveryKeepAlive` 等字符串。结合完整
  Pigeon channel 列表，可确认私有 participant 注册逻辑位于飞牛 APP 编译进的 Flutter 层，
  不是该 Web 静态包公开的 JavaScript API。

### 已确认的私有通道名

`libapp.so` 中可提取到以下完整 channel 名：

```text
HostPlaybackSessionApi.initialize
HostPlaybackSessionApi.synchronize
HostPlaybackSessionApi.registerParticipant
HostPlaybackSessionApi.unregisterParticipant
HostPlaybackSessionApi.requestActivation
HostPlaybackSessionApi.reportParticipantState
HostPlaybackSessionApi.reportUserStopped
HostPlaybackSessionApi.reportRemoteUserPaused
HostPlaybackSessionApi.acknowledgeCommand
FlutterPlaybackSessionApi.onSessionSnapshotChanged
FlutterPlaybackSessionApi.onSessionDiagnostic
FlutterPlaybackSessionApi.onCoordinatorCommand
HostKeepAliveApi.startKeepAlive
HostKeepAliveApi.cancelKeepAlive
```

下一步研究目标是仅通过官方音乐的真实动作，继续确定 register/synchronize 的二进制 StandardMessageCodec
载荷、调用方向和应用身份边界；在这些证据完成前，不向 fnAudio 注入猜测的 Pigeon 消息。

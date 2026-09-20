# fnAudio 播放会话六项验收矩阵

更新时间：2026-08-31

| 目标 | 当前实现证据 | 离线证据 | 尚缺证据 |
|---|---|---|---|
| 会话建立时序 | `PlaybackService.onCreate()` 按 player → MediaSession → ready → restore；远程模式有 ready guard | `test_ui_android_bridge.js` 顺序契约 | Android 动态启动时序日志 |
| 远程播放通知 | metadata-only `RemotePlaybackPlayer`、前台 MediaStyle、封面有界解码、状态变化重发通知 | Node/UI 静态契约；Python 回归 | 系统通知栏/锁屏实机显示 |
| 锁屏与媒体键回传 | MediaSession 接收命令；成功响应经身份/ticket 校验后更新；失败响应不覆盖状态 | Node/UI 静态契约；播放恢复回归 | 锁屏、蓝牙键、厂商 ROM 动态行为 |
| 进程被回收后的恢复 | `START_STICKY`、schema/TTL/大小校验、销毁前同步 commit 检查点、启动恢复 | Python 播放恢复回归；Node/UI 静态契约 | force-stop/系统回收后的真实重启恢复 |
| generation / engine epoch / command ticket | 服务端与 Android 双侧身份门禁；缺失/错配 ticket 拒绝；命令幂等缓存 | session policy/contract、playback restore 回归 | 延迟网络下多设备动态交错命令 |
| 可观测日志和失败原因 | session、通知、SSE、轮询、恢复、旧会话、未知 action 均有脱敏原因码 | Node/UI 静态契约；Python 失败路径回归 | 真实设备日志与厂商通知权限错误样本 |

## 当前离线门禁

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\path\to\fnAudio\tools\update_source_manifest.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File C:\path\to\fnAudio\tools\test_offline.ps1
git diff --check
```

当前门禁覆盖服务端和 UI/Android 源码契约，但不能替代真实 Android 系统行为验收。

## 2026-08-31 动态验收环境记录

- 已检查本地 Android SDK 并尝试启动 `fnaudio-fnos-bridge` AVD；该 AVD 配置引用的
  `android-30/google_apis/x86_64` system image 目录无效，Emulator 报 `Cannot find AVD
  system path`，因此本轮未取得通知、锁屏、媒体键或进程回收的动态证据。
- 该环境问题不改变源码实现状态，也不应被记录为功能通过；后续需补齐有效 system image 或
  使用真实 Android 设备后重新执行矩阵。

- API 35 AOSP x86_64 AVD 已可启动，但现有 debug APK 仅包含 `arm64-v8a/libgojni.so`，安装
  明确失败为 `INSTALL_FAILED_NO_MATCHING_ABIS`；因此尚未取得 Android 动态会话证据。

- 2026-08-31 小米 15 Pro（`2410DPN6CC`）已确认运行 `0.2.33 / versionCode 301`；强制停止并
  启动 `LoginActivity` 成功，未发现 `FATAL EXCEPTION`。由于 Gradle loopback 构建阻塞，
  该证据针对设备上既有安装，不代表本轮源码已安装。

- 同一设备已确认 `PlaybackService` 注册成功，`FOREGROUND_SERVICE` 与
  `FOREGROUND_SERVICE_MEDIA_PLAYBACK` 权限均为 granted；登录页空闲时无活动 MediaSession，
  不能据此推断播放会话功能已验收。

- 已安装并使用 JDK 17 重试 `:app:assembleDebug --offline --no-daemon`，仍复现
  `Unable to establish loopback connection`；构建阻塞属于宿主 Gradle 进程通信问题，不是 JDK
  版本问题。

# fnAudio 0.1.174

## 本版重点

- 修复 fnOS 升级后旧版 fnAudio 服务未退出的问题。启动时会清理遗留 `server.py`，停止时会清理 fnAudio MPD，避免双实例抢占端口、重复播放和状态互相覆盖。
- 保留 0.1.173 的 USB DAC/MPD 自动下一曲、远程播放恢复去重、DSD DLNA 96 kHz/24 bit WAV PCM 转换、Renderer 下一曲预加载和 Android token 恢复能力。
- Android 客户端版本号升级为 `versionCode 174` / `versionName 0.1.174`，最低支持 Android 6.0（API 23）。

## 安装建议

1. 安装 `fnaudio-0.1.174.fpk`，升级前不需要删除音乐库或应用数据。
2. Android 安装 `fnaudio-android-0.1.174-debug.apk`；这是 Debug 签名包，正式分发前仍需正式签名。
3. 如果应用中心提示依赖/向导需要 UI 确认，请在应用中心完成确认；本轮测试机因 App Center CLI 限制使用 SSH 备份后覆盖部署。

## 已知限制

- 尚未在真实 USB DAC、DLNA Renderer 和多型号 Android 设备上完成硬件矩阵验收。
- 测试 NAS 日志时间显示为 2026-08-08，开发基准日期为 2026-08-07；遇到缓存或会话时间异常时先校准 NAS 时钟。

# MPD 重启恢复回归：0.1.204

日期：2026-08-10  
设备：TEAC UD-301，`hw:CARD=UD301,DEV=0`

## 0.1.203 基线发现

在播放中终止 root MPD 进程后，supervisor 能在约数秒内重新拉起 MPD，原有 20 首队列、当前第 20 首和进度都能恢复并继续播放；但 `idle.transport` 在恢复后仍可能保持旧的 `STOPPED`，而 MPD 原始 `state=play`，会造成 UI/Android 状态误判。日志中的 `wildmidi` 缺少 timidity 配置属于解码器可用性提示，不是 USB DAC underrun。

## 0.1.204 修复

- 新增 `normalized_transport()`，优先使用规范化 transport，缺失时回退到 MPD 原始 `state`。
- MPD idle listener 统一使用该解析结果。
- 队列恢复完成后主动刷新 idle 状态、fault 状态和 PlaybackCore，避免等待下一次 idle 事件。
- 恢复回调使用 `RECOVERING -> PLAYING/PAUSED/STOPPED`，不会把恢复过程误判为自然切歌。

本版本已通过 117 项 Python 测试；FPK 和 Android Debug/unsigned Release 构建成功。0.1.204 尚待通过 App Center UI 覆盖安装后再次执行同一真实 MPD 重启矩阵。


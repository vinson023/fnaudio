# 0.1.178 播放与 USB DAC 改造说明

## 本版本实现

- MPD 使用 fnAudio 队列镜像，切歌优先执行 `playid`，避免反复 `stop/clear/add` 导致 USB DAC 重新锁定。
- 队列中的下一曲由 MPD 原生队列预加载，MPD 自然切歌后回写 PlaybackCore 当前曲目。
- USB 音频设备保存稳定身份：USB VID/PID、序列号、卡片 ID 和 PCM 设备号；旧的 `hw:X,Y` 选择会自动迁移。
- 设备能力同时来源于 USB 描述和真实 ALSA `hw_params` 探测，能力状态按当前选中的设备报告。
- DSD 默认优先 Native DSD；无法 Native DSD 时仅在真实支持 DoP 且对应 PCM 速率可用时使用 DoP。两者都未验证时拒绝播放，不静默转 PCM。
- USB DAC 拔出后停止 MPD 输出并等待稳定身份重新出现，重新连接后恢复 MPD、队列和接近原进度。
- MPD 进程采用有限重启和指数退避；监控 underrun、ALSA error 等日志，并在冷却窗口内执行一次恢复。
- 输出切换采用停止、验证、启动、失败回滚的事务流程。
- MPD 与直接 ALSA 输出共享音频设备租约，避免两个后端同时抢占物理设备。
- 支持按 VID/PID 或稳定 ID 配置 DAC quirk profile，例如缓冲区、启动延迟和 DoP 强制策略。

## 已知限制

- 真实 Native DSD/DoP 结果必须在连接具体 USB DAC 的 fnOS 主机上验证；没有 DAC 时只能验证探测失败和安全拒绝路径。
- 直接 ALSA 输出不再为 DSD 做 PCM 兜底，DSD 应选择 MPD USB DAC 输出。
- 第三方 DAC 的 quirk profile 目前通过配置文件提供，尚未建立覆盖全部厂商的默认数据库。

## 验证

在 `C:\path\to\fnAudio\src`：

```powershell
$env:PYTHONPATH = "app\server"
python -m unittest discover -s tests -p "test_*.py"
node --check app\ui\app.js
node tests\test_ui_android_bridge.js
node tests\test_ui_queue_columns.js
node tests\test_ui_mobile_layout.js
```

本版本构建产物：

- `artifacts/0.1.178/fnaudio-0.1.178.fpk`
- `artifacts/0.1.178/fnaudio-android-0.1.178-debug.apk`

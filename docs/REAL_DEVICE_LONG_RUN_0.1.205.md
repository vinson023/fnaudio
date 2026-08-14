# 0.1.205 TEAC UD-301 90 分钟连续播放验收

测试日期：2026-08-10（UTC+8）  
设备：TEAC UD-301，`hw:CARD=UD301,DEV=0`  
输出：Native ALSA / MPD，fnAudio `0.1.205`

## 执行方式

真机脚本 `/tmp/fnaudio-long-play-0.1.205.sh` 通过 fnAudio API 加载 20 首队列，从 2026-08-10T10:17:39+08:00 至 2026-08-10T11:48:13+08:00 每 30 秒采样一次 `/api/mpd/status`，共 181 个有效样本。脚本结束后发送 stop，并恢复测试前的 20 首逻辑队列、原当前曲目、repeat/shuffle 和 STOP 状态。

原始持久日志：`/vol1/1000/fnaudio-long-play-0.1.205.log`。本地镜像：`artifacts/0.1.205/real-device/fnaudio-long-play-0.1.205.log`。

## 结果

- MPD 原始状态在全部 181 个样本中均为 `play`，队列长度始终为 20。
- 覆盖 12 个不同的 MPD `songid`，观测到 11 次自然自动下一曲。
- `underrun.count` 最大值为 0。
- 脚本在 2026-08-10T11:48:44+08:00 完成，恢复后的 API 状态为 STOP，逻辑队列为 20 首，当前曲目为队列第 20 首。后续短队列验收发现历史恢复清单含无效歌曲 ID，因此这次长测的 MPD 原生恢复长度不能再作为已验证的 20 首证据，需在恢复脚本修复后重新核验。
- 长测期间第 146–148 个样本（2026-08-10 11:31:07–11:32:07）出现 `fault.state=SUSPECT`，`last_error=timed out`；同时 MPD 原始状态仍为 `play`、队列仍为 20、underrun 为 0，后续自动恢复为 `PLAYING`，未观察到播放中断。

## 限制与后续

本结果证明当前 TEAC UD-301 的受控 90 分钟连续播放、自然跨曲和自动回滚链路可用；它不等同于手机息屏后台播放，也不替代完整 20 首短曲自动下一曲验证、物理 USB 热插拔、DoP-only DAC、外部 DLNA Renderer 或 Android 真机验收。

长测中的 `FLAC__STREAM_DECODER_ERROR_STATUS_LOST_SYNC` 应继续按源文件/解码器错误分类追踪，不能被误报为 DAC underrun；该次长测的 underrun 指标始终为 0。

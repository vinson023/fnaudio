# fnAudio 0.1.20

## MPD 队列修复

- 修复 MPD、DLNA 和 ALSA 输出的上一曲/下一曲路径：播放核心现在会在切歌前重新解析完整曲目资料，不再只向输出插件传递曲目 ID。
- 修复前，MPD 队列切换下一曲可能返回播放设备接收失败并继续播放上一首；修复后会实际载入下一首并输出到当前目标。
- 已在真实飞牛实体机的 TEAC UD-301 USB DAC 上验证队列切歌，MPD 输出状态为 `PLAY`，停止后为 `STOPPED`。

## 真实 DAC 验证

- MP3：44.1kHz / 24-bit / 2ch。
- M4A：44.1kHz / float / 2ch。
- FLAC：96kHz / 24-bit / 2ch。
- DSF：DSD64 / 2ch Native DSD。

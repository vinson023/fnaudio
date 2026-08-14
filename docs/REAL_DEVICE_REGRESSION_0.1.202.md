# fnAudio 0.1.202 真机回归记录

日期：2026-08-09  
设备：TEAC UD-301（稳定 ID：`usb:0644:804a:00160000386ca1d14e45282720120016:dev0`）  
MPD：`127.0.0.1:56660`  
ALSA：`hw:3,0`

## 已执行

### 20 首连续队列短周期测试

- 通过 MPD 原生队列写入 20 首 PCM 曲目，队列长度保持 `20`。
- 逐首将播放位置推进到接近曲尾，`nextsong` 从 `1` 推进到 `19`。
- 自动下一曲由 MPD 原生队列完成，没有依赖前端定时器或重新构建队列。
- `underrun.count=0`；测试结束时第 20 首仍处于播放状态。

该结果证明“队列镜像、自然切歌和基础 underrun 监控”可工作，但不等同于长时间播放验收；首帧延迟、暂停/恢复、拖动、息屏和跨采样率切歌仍需单独记录。

### App Center 重启与队列恢复

- 通过 App Center 重启 `fnaudio`，版本仍为 `0.1.202`，状态为 `running`。
- 重启后 MPD `playlistlength=20`，当前歌曲位置恢复到索引 `19`。
- 恢复初始状态为 `STOP`，稳定 DAC ID、`native_dsd_verified=true` 和 `underrun.count=0` 均保留。
- 显式发送 `play` 后返回 `ok: true`，MPD 回到 `PLAY`；2 秒后仍在播放且 underrun 未增加。

该结果证明“应用重启后的 MPD 队列恢复与停止状态保留”可工作；物理 USB 拔插、root MPD 异常重启和卸载策略仍未验收。

### 45 秒连续播放监测

- 使用 96 kHz FLAC `676735c3075e949f` 连续播放约 45 秒。
- 9 次、每 5 秒一次的采样均为 `PLAYING`，进度从约 6.1 秒连续增长到 47.5 秒。
- MPD 实际 stream 始终为 `96000:24:2`，fault state 始终为 `PLAYING`，`underrun.count=0`。
- 测试结束后原队列和停止状态已恢复。

该结果加强了持续播放证据，但仍不能替代小时级播放、息屏和物理热插拔验收。

## DSD 交叉证据

- DSF `NEW/Lynyrd Skynyrd - Simple Man.dsf`：`audio: dsd64:2`。
- DFF `test/01 分手說愛你.dff`：`audio: dsd64:2`。
- ALSA 流显示 `S32_LE DSD_U32_BE`；`server_transcode=false`。
- 当前证据支持源码 Native DSD 推送，尚未覆盖 DoP-only DAC 和完整 PCM 44.1/48/96/192 kHz 矩阵。

## 未完成项

1. 真实长时间播放、暂停/恢复、拖动、息屏后台和跨采样率切歌。
2. 物理 USB 热插拔及 root MPD 异常恢复。
3. 外部 DLNA Renderer（含 NextURI/断开恢复）互操作。
4. Android 真机后台、通知栏/锁屏封面、USB DAC 模式和多机型安装。

## App Center 生命周期补充

- `fnaudio` 停止命令成功；启动命令因 fnOS 依赖保护要求 UI，随后通过「已安装 → 启用」完成启动。
- 启动后 App Center 查询仍为版本 `0.1.202`、状态 `running`；CGI 入口返回 HTTP 200。
- 端口修改、卸载保留/清除数据和跨版本完整自动化仍未执行。

# fnAudio 0.1.202 TEAC UD-301 播放矩阵

测试时间：2026-08-09（测试机系统日志显示为 2026-08-10，设备时钟比开发环境快一天）  
设备：TEAC UD-301，稳定 ID `usb:0644:804a:00160000386ca1d14e45282720120016:dev0`  
服务：`fnAudio/0.1.202`，MPD `0.23.12`

## PCM

| 源采样率 | 样本 | HTTP/load | MPD 实际状态 | MPD stream | underrun |
| ---: | --- | ---: | --- | --- | ---: |
| 44.1 kHz | MP3 `6d6e5ed0a8c0cf70` | 200 | PLAYING | `44100:24:2` | 0 |
| 48 kHz | FLAC `62316a9446bf44e2` | 200 | PLAYING | `48000:24:2` | 0 |
| 96 kHz | FLAC `676735c3075e949f` | 200 | PLAYING | `96000:24:2` | 0 |
| 176.4 kHz | FLAC `50946270c08b4c72` | 200 | PLAYING | `176400:24:2` | 0 |
| 192 kHz | FLAC `656543c542d57326` | 200 | PLAYING | `192000:24:2` | 0 |
| 384 kHz | FLAC `0fb5ea77a0d82e8a` | 502 | STOPPED | 保留上一有效格式 | 0 |

384 kHz 被明确拒绝并返回“DAC 不支持源采样率 384000 Hz，已阻止隐式重采样”，没有静默降采样或 PCM fallback。

## Native DSD

| 源格式 | 样本 | HTTP/load | MPD 实际状态 | MPD stream | native_dsd_verified |
| --- | --- | ---: | --- | --- | --- |
| DSF | `80562025babebf1f` | 200 | PLAYING | `dsd64:2` | true |
| DFF | `4d158238e962b112` | 200 | PLAYING | `dsd64:2` | true |

两种 DSD 均保持源码输出；当前设备能力为 Native DSD，DoP-only DAC 尚未覆盖。

## 控制与恢复

- play/pause/seek/stop 控制冒烟通过，暂停后 transport 为 `PAUSED`，seek 到 10 秒后恢复 `PLAYING`，停止后为 `STOPPED`。
- 矩阵结束后已恢复原 20 首队列、当前歌曲和停止状态。
- 所有矩阵步骤 `underrun.count=0`。

## 观察到的日志

- 历史日志中存在一次 `FLAC__STREAM_DECODER_ERROR_STATUS_LOST_SYNC`、一次 `Decoder failed to seek`，以及 `wildmidi` 配置缺失提示。
- 本轮矩阵新增曲目均能进入预期 PLAYING/STOPPED 状态，未新增 underrun；上述日志仍列为后续解码器/seek 专项调查项，不能忽略。
- 对日志中两首 GAYLE FLAC 做独立 `ffmpeg -v error` 校验，均报告 `invalid sync code` / `invalid frame header`；这两首源文件本身损坏，不能把该类错误归咎于 USB DAC 或 MPD 输出链路。
- 第三首带非 ASCII 文件名的 GAYLE FLAC 通过 API 定位时，测试脚本未正确处理远端 Unicode 路径；这是测试脚本编码问题，不是播放结论。

## 仍未覆盖

1. DoP-only DAC、物理 USB 拔插和 root MPD 异常恢复。
2. 长时间播放、息屏后台和真实 DLNA Renderer。

## DLNA 现场状态

- 本轮真机 `/api/upnp/devices` 返回空列表，DLNA diagnostics 记录数为 0。
- 本地 `/api/dlna/capabilities` 能正确声明 DSF/DFF MIME，但这只是服务端能力，不替代真实 Renderer 的 NextURI、断开恢复和源码 DSD 验收。

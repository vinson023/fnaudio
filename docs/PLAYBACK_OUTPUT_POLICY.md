# 播放输出与 Mixer 策略

## 输出职责

`PlaybackCore` 保存队列、当前曲目、transport、循环和随机状态。每种输出目标由单独适配器执行：

| 目标 | 后端 | 状态来源 |
| --- | --- | --- |
| 浏览器 | HTML audio | 浏览器事件 + 服务端快照 |
| Android 本机 | Media3/ExoPlayer | Android MediaSession |
| NAS/USB DAC | 私有 MPD -> ALSA | MPD status/idle |
| 外部 Renderer | DLNA Push/SOAP | Renderer transport 查询 |
| AirPlay Receiver | `shairport-sync`/`nqptp`（可选） | 受监督子进程与 ALSA 租约 |

前端不判断远程曲目自然结束，也不自行推进远程队列。MPD 和 Renderer 适配器确认最终状态后更新权威快照。

## `upmpdcli_renderer.py`

该模块只探测系统中是否存在外部管理的 upmpdcli，以便诊断兼容环境。它：

- 不由 fnAudio 启停；
- 不是可选择的播放目标；
- 不申请 ALSA 设备租约；
- 不替代 fnAudio 内置 DLNA Renderer。

这样可避免 upmpdcli、私有 MPD 和 AirPlay 同时争用 DAC。

## MPD Mixer

- `none`：默认固定音量，保持 bit-perfect。
- `hardware`：只有 ALSA 控件明确提供 `Playback Volume` 或 `pvolume` 时可用；不可用时回退 `none`，不生成无效 MPD 配置。
- `software`：允许数字音量，但 API 明确标记 `bitperfect=false`。

DLNA Renderer 的音量/静音调用同一 Mixer 策略。固定音量目标会明确拒绝音量写入，不伪装成功。

## DSD

MPD/USB DAC 和 DLNA Renderer 使用原始 DSF/DFF。能力不满足时明确返回格式/输出错误，不允许静默转为 96 kHz PCM。浏览器兼容转码只能由明确的浏览器媒体模式触发，不能进入远程推送路径。

## 仍需设备验收

物理热插拔、DoP-only DAC、Renderer 断开/恢复、AirPlay 对端和跨设备音量语义仍以 `TODO.md` 为准。

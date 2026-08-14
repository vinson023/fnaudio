# 0.1.205 TEAC UD-301 真机复验记录

日期：2026-08-10

## 环境

- fnAudio：`0.1.205`
- 真机：`vinson023.eu.org:3100`（SSH），App Center `:5666`
- 输出设备：TEAC UD-301
- 稳定标识：`usb:0644:804a:00160000386ca1d14e45282720120016:dev0`
- ALSA：`hw:CARD=UD301,DEV=0`

## API 驱动的 PCM 连播采样

通过 `POST /api/playback/load` 将既有逻辑队列的第 20 首重新装入 MPD，而非直接执行 MPD 命令。首次采样和 105.60 秒延时采样均确认：

- MPD transport：`PLAYING`
- 原生队列：20 首
- PCM stream：`44100:16:2`
- `fault.state`：`PLAYING`
- `underrun.count`：0
- TEAC 正在播放时 ALSA 探测显示 busy，这是正常的独占打开状态。

这证明应用 API、逻辑队列同步、MPD 原生队列和 DAC 状态回传在本次短测中协同正常；它不等同于小时级/息屏/20 首完整长测。

## PCM 播放控制闭环

以原队列第 1 首 44.1 kHz/24-bit PCM 样本执行 `playback/load` 后，继续完全通过 fnAudio API 执行控制：

| 操作 | 真机观测 |
| --- | --- |
| 暂停 | 约 31.4 秒时 transport=`PAUSED`，进度停止增长 |
| 恢复 | transport 回到 `PLAYING`，进度继续增长 |
| 拖动 | 请求 30 秒后，约两秒后的实际进度为 33.2 秒，符合恢复播放后的自然推进 |
| 下一首 / 上一首 | 两次命令均成功切换，MPD 原生队列始终为 20 首 |

整个控制链路中 `fault.state=PLAYING`、`underrun.count=0`。操作完成后按下文的回滚步骤恢复了原当前曲和停止状态。

## DSD 源码复验

分别通过同一 API 载入下列文件：

| 格式 | 曲目 | 观测结果 |
| --- | --- | --- |
| DSF | `Lynyrd Skynyrd - Simple Man.dsf` | 31.12 秒时 `PLAYING`，stream `dsd64:2`，`dsd=true`，`native_dsd_verified=true`，underrun 0 |
| DFF | `01 分手說愛你.dff` | 13.24 秒时 `PLAYING`，stream `dsd64:2`，`dsd=true`，`native_dsd_verified=true`，underrun 0 |

两个样本均没有出现 PCM stream 或服务端转码标记，符合“DSD 必须源码传输”的约束。

## 测试后回滚

测试期间直接载入库中未在原队列中的 DSD 曲目会按既有 `PlaybackCore.load` 语义暂时追加到逻辑队列。测试结束后通过正规 API：

1. `POST /api/playback/control`，action=`stop`；
2. `POST /api/playback/queue`，恢复原 20 首 ID、原当前曲 `df394c51eb4378d6`、repeat=`off`、shuffle=`false`。

最终真机状态：MPD `STOPPED`、原生队列 20 首、`fault.state=IDLE`、失败计数 0、`underrun.count=0`、TEAC 不再 busy。此结果也证明应用 API 发出的显式 stop 不会被误判成 DAC 故障。

## 仍未覆盖

- 小时级/息屏连续播放；
- 物理 USB 拔插；
- DoP-only DAC；
- 外部 DLNA Renderer；
- Android 真机后台、通知和锁屏；
- App Center 卸载/端口/数据策略。

## 90 分钟长测（进行中）

2026-08-10 已在真机启动受控长测，远端 runner PID 为 `110676`；日志实时同步到持久路径 `/vol1/1000/fnaudio-long-play-0.1.205.log`（临时工作副本为 `/tmp/fnaudio-long-play-0.1.205.log`）：

- 从原 20 首队列第 1 首开始；
- 每 30 秒采集一次 MPD/ALSA/fault/underrun 状态；
- 最长 90 分钟后自动停止，并通过 API 恢复第 20 首、原队列与 STOP 状态；
- 启动约 28 秒时已确认 `PLAYING`、队列 20 首、`underrun=0`；后续跨曲和完整日志须待 runner 结束后再判定。
- 运行约 5 分 26 秒时已观察到第 1 首自动切换到第 2 首（MPD `Pos=1`，`nextsong=2`），队列仍为 20 首，`fault.state=PLAYING`、`underrun=0`；长测继续进行。
- 当前日志阶段已采集 19 个 30 秒样本，覆盖 MPD `Pos=0,1,2` 三首歌曲；所有样本均为 `PLAYING`、队列 20 首、fault `PLAYING`、最大 underrun 0。90 分钟长测仍未结束。
- 运行约 12 分钟时日志已覆盖第 0、1、2、3 首（24 个样本），最新曲目仍为 `PLAYING`，队列 20 首且最大 underrun 0；测试继续运行。

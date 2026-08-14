# fnAudio 播放栈与 Volumio / moOde 对比

本文记录 2026-08-08 对 `references/volumio3-backend`、`references/moOde` 和 fnAudio 当前播放代码的对比结果。参考仓库只作为设计依据，不会被打进 FPK/APK，也没有直接复制其 PHP/Node 运行时代码。

## 结论摘要

fnAudio 已经具备“媒体库 + 播放队列 + MPD/ALSA + DLNA MediaServer/Renderer/Control Point”的骨架，但此前前端仍承担了部分远端续播判断，MPD 的 idle 事件也没有完整合并进统一状态。当前改造补上了：

- `PlaybackState.transport` 与 `state_version`，以及输出插件的标准状态/能力/恢复接口。
- MPD idle 事件对播放、暂停、停止、队列及输出变化的统一状态同步。
- 外部 DLNA Renderer 的服务端 transport 监控；支持 `SetNextAVTransportURI` 的设备优先使用设备队列，不支持的设备由服务端推进下一首。
- DLNA `GetProtocolInfo`、SCPD action 能力缓存，包含 DSD MIME、NextURI、Seek、Pause 等能力。
- MPD stream 信息（PCM/DSD、采样率、位深、声道）回传，避免把“检测到 DSD”误报成“已经验证原生 DSD 输出”。
- AirPlay 依赖探测 API：只有发现 `shairport-sync` 才报告 AirPlay 1 可用，AirPlay 2 还要求 `nqptp`；缺少依赖时明确不可用，不伪造支持。

## 分项对比

| 主题 | fnAudio | Volumio | moOde | 采用的改进 |
|---|---|---|---|---|
| 播放状态 | `PlaybackCore` 队列状态；MPD/Renderer 通过适配器回写 | `statemachine.js` + `pushState`，MPD 为事实来源 | `engine-mpd.php` 长连接 idle | 保留 Core，新增异步状态合并和版本号 |
| MPD | 命令连接短连接，已有 idle 线程但原先只通知 transport 转换 | MPD 插件、状态机、prefetch/gapless | MPD idle + `mpdmon` underrun 监控 | idle 每次事件回调；输出状态统一；后续继续加 underrun watchdog |
| USB DAC | ALSA 探测，MPD 或 FFmpeg/aplay 输出 | ALSA controller 管理设备、DoP、音量和输出切换 | MPD ALSA 输出，DoP/native DSD 选项 | MPD 默认 `mixer_type none`、`dop no`（native 优先）；能力与已验证状态分离 |
| DSD | MediaServer/DLNA 源文件直出；本地旧 ALSA 路径仍可能 PCM fallback | MPD 解码器 + ALSA/DoP 配置 | MPD `dop`、DSD 状态展示和音频信息 | DLNA 不转码；MPD 回传实际 stream；native DSD 仍需真机 DAC 验证 |
| DLNA Push | SOAP SetURI/Play，部分设备 SetNext | upmpdcli/Renderer 生命周期 | renderer.php 统一抢占/释放 | 能力缓存 + 服务端 Renderer monitor + NextURI fallback |
| UPnP | MediaServer、MediaRenderer、Control Point 均有实现 | upmpdcli 输出插件 | upmpdcli/Renderer 管理 | 增加 protocolInfo/SCPD action 矩阵，保留设备 quirks 扩展点 |
| AirPlay | 之前没有 Receiver | `shairport-sync` 元数据和 renderer lifecycle | `shairport-sync` + `nqptp`、renderer ownership | 先做真实依赖探测；后续单独实现 supervisor/metadata/ownership |
| 输出占用 | 由目标选择隐式决定 | renderer lifecycle 显式抢占 ALSA | renderer.php / worker.php 显式管理 | 插件契约新增 `owns_audio_device`、`recover`、`preload_next`；完整抢占仍是下一阶段 |

## 不能直接复用的部分

- Volumio 和 moOde 的 PHP/Node 服务脚本依赖各自系统目录、配置数据库、systemd/service 约定，直接复制会破坏 fnOS 生命周期。
- 参考仓库包含 GPL 代码和各自第三方依赖；fnAudio 当前仅复用协议思路、状态模型和配置语义，未把其实现复制进运行包。
- `shairport-sync`、`nqptp`、`upmpdcli` 是否存在必须由目标 fnOS 固件确认，不能因为参考项目支持就宣称 fnAudio 已支持。

## 仍需真机验证

1. 使用真实 USB DAC 验证 native DSD、DoP、PCM 采样率切换、热插拔和 underrun 恢复。
2. 使用至少两个 DLNA Renderer：一个支持 `SetNextAVTransportURI`，一个不支持，验证后台续播、暂停、seek、Previous。
3. 在安装了 `shairport-sync`/`nqptp` 的 fnOS 环境实现并验证 AirPlay Receiver；当前 API 只负责能力探测。
4. Android 通知栏、锁屏、服务重启后的远程 session 恢复仍需真机验证。

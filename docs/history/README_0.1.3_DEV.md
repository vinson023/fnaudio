# fnAudio 0.1.3 开发说明

这是从 `fnAudio 0.1.2` 独立复制出来的 0.1.3 重构目录。

项目位置：

`C:\Users\example\Documents\Codex\fnaudio-0.1.3`

这个目录可以整体复制到新电脑。复制时可以忽略：

- `__pycache__`
- `*.pyc`
- 本地生成的 `fnaudio.fpk`
- 测试音乐目录

## 0.1.3 重构目标

- 播放核心不直接关心浏览器、DLNA、USB DAC 或声卡。
- 输出能力拆成插件：`browser`、`dlna_push`、`alsa`。
- DLNA 子系统单独拆分为媒体服务端、控制点、渲染器和设备能力 profile。
- 前端只做目标选择、状态显示和统一播放 API 调用。

## 当前目录结构

- `app/server/playback/`
  - `core.py`：队列、当前曲目、上一曲/下一曲、循环、随机、进度、播放会话。
  - `models.py`：播放核心和输出插件共享的数据模型。
  - `plugins.py`：统一输出插件接口与注册表。
  - `browser_output.py`：浏览器播放输出插件入口。
  - `dlna_push_output.py`：UPnP/DLNA 推送输出插件入口。
  - `alsa_output.py`：本机 USB DAC / 声卡输出实现。
- `app/server/dlna/`
  - `control_point.py`：搜索和控制外部 DLNA 渲染器。
  - `media_server.py`：向 DLNA 设备暴露本地音乐资源。
  - `profiles.py`：按设备能力生成 MIME / protocolInfo。
  - `renderer.py`：后续让 fnAudio 自己作为 DLNA Renderer 的预留入口。
- `app/server/library.py`
  - 音乐目录扫描、ID3/FLAC 元数据、封面、CUE 分轨、目录浏览和实时监控。
- `app/server/transcode.py`
  - 浏览器播放策略、FFmpeg 查找、MP3/DSD/CUE 转码、流式输出和两天缓存清理。
- `app/server/config.py`
  - 配置读取、配置保存和应用端口文件更新。
- `app/server/server.py`
  - 现在主要负责 HTTP 路由、兼容包装和输出插件编排。
  - 配置、音乐库、转码、UPnP SOAP、DLNA 资源生成、ALSA 播放实现已经从入口文件中搬出。

## 统一播放 API

- `GET /api/playback/targets`
  - 返回本机浏览器播放、本机 ALSA/DAC、外部 DLNA 渲染器等目标。
- `POST /api/playback/queue`
  - 同步播放队列、当前曲目、循环和随机状态。
- `POST /api/playback/load`
  - 按 `target_id` 装载并播放指定曲目。
- `POST /api/playback/control`
  - 统一处理播放、暂停、停止、上一曲、下一曲、seek、循环、随机等命令。
- `GET /api/playback/status`
  - 查询当前播放目标状态。
- `GET /api/playback/core`
  - 查看播放核心状态和已注册输出插件。

## 兼容接口

旧接口仍保留，避免旧前端或测试脚本立刻失效：

- `/api/player/state`
- `/api/upnp/devices`
- `/api/upnp/status`
- `/api/upnp/push`
- `/api/upnp/control`
- `/api/dac/devices`
- `/api/dac/status`
- `/api/dac/push`
- `/api/dac/control`

其中 `/api/upnp/push`、`/api/upnp/control`、`/api/dac/push`、`/api/dac/control` 已经改为转发到统一播放 API，不再绕过 `PlaybackCore`。

## 当前验证结果

在测试环境 `198.51.100.24` 上已验证：

- 应用中心可以重启 `fnaudio`，状态为 running。
- `/api/health` 正常。
- `/api/library/status` 正常，音乐库可读取。
- `/api/playback/core` 能看到 `browser`、`dlna_push`、`alsa` 三个插件。
- `/api/playback/targets` 能返回本机播放和已搜索到的 DLNA 设备。
- `/api/playback/queue`、`/api/playback/load`、`/api/playback/control` 的本机目标基础流程正常。

## 后续可评估

完成这个拆分后，再评估是否引入 MPD、upmpdcli、Snapcast 或 AirPlay 作为可选后端会更清晰，因为它们可以作为新的输出插件或 DLNA 子系统实现，而不是塞回前端逻辑。

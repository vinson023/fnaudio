# fnAudio 架构

> 当前源码版本：`0.1.156`  
> 源码根目录：`C:\path\to\fnAudio\src`

## 1. 系统定位

fnAudio 是部署在 fnOS NAS 上的单进程 Python 音乐服务，并带有私有 MPD 子进程和原生 Web UI。它承担以下角色：

- 本地音乐库索引和查询服务。
- 浏览器播放器的媒体源和状态服务。
- NAS 声卡或 USB DAC 的本机播放器。
- 外部 DLNA Renderer 的 Control Point。
- 面向局域网控制器的 DLNA MediaServer。
- 面向局域网控制器的 DLNA MediaRenderer。

## 2. 运行时拓扑

```mermaid
flowchart TD
    FNOS["fnOS 应用中心"] --> CGI["index.cgi / cgi_proxy.py"]
    CGI --> HTTP["ThreadingHTTPServer :18080"]
    DIRECT["局域网直连端口"] --> HTTP

    HTTP --> UI["原生 Web UI"]
    HTTP --> LIB["音乐库服务"]
    HTTP --> CORE["PlaybackCore"]
    HTTP --> DLNA["DLNA 协议服务"]
    HTTP --> META["元数据后台服务"]
    HTTP --> STATE["用户状态服务"]
    HTTP --> MEDIA["媒体流 / 转码"]

    LIB --> DB["library.sqlite3"]
    META --> DB
    STATE --> SDB["state.sqlite3"]
    MEDIA --> FFMPEG["fnOS FFmpeg / ffprobe"]

    CORE --> BROWSER["浏览器 HTMLAudioElement"]
    CORE --> MPD["私有 MPD"]
    MPD --> ALSA["ALSA / USB DAC"]
    CORE --> EXTERNAL["外部 DLNA Renderer"]
    DLNA --> EXTERNAL
```

安全上必须注意：CGI 是 fnOS 正常入口，但 Python 服务默认监听 `0.0.0.0`，直接端口访问可能绕过 CGI 层。

## 3. 分层与模块

| 层 | 主要路径 | 职责 |
| --- | --- | --- |
| fnOS 生命周期 | `manifest`、`cmd/`、`config/`、`wizard/` | 安装、升级、端口、权限、共享目录、启动停止和卸载 |
| 入口代理 | `app/ui/index.cgi`、`app/ui/cgi_proxy.py` | iframe 入口、端口发现、token 转发、HTTP 代理 |
| 前端 | `app/ui/index.html`、`app.css`、`app.js` | 浏览、搜索、播放、队列、歌词、收藏、歌单和设置 |
| HTTP 编排 | `app/server/server.py` | API、静态文件、媒体响应、DLNA 路由和服务装配 |
| 音乐库 | `app/server/library.py` | 扫描、Tag、封面、CUE、SQLite 索引和查询 |
| 播放核心 | `app/server/playback/` | 队列、目标、状态机、插件接口和输出适配 |
| DLNA | `app/server/dlna/` | 发现、推送、MediaServer、Renderer、SOAP、事件和诊断 |
| 本机服务 | `app/server/services/` | MPD 配置、启动、监督、状态监听和输出测试 |
| 状态 | `app/server/state_store.py` | 收藏、歌单、播放会话、UI 偏好和 revision |
| 元数据 | `app/server/metadata_service.py` | 在线元数据、歌词、封面、任务和缓存回收 |
| 媒体交付 | `app/server/transcode.py` | MP3、DSD WAV、CUE FLAC、流式转码和缓存清理 |

## 4. 主要数据流

### 音乐库

```text
library_path / library_paths
  -> 全目录变化签名
  -> 音频信息、Tag、封面和 CUE 解析
  -> library.sqlite3
  -> 分页/分组/文件夹 API
  -> Web UI 或 DLNA ContentDirectory
```

音乐库表包括 tracks、albums、artists、composers、genres、folders、covers、cue_tracks 和 metadata 相关表。SQLite 使用 WAL、busy timeout 和 NORMAL synchronous。

### 统一播放

```text
队列同步 -> PlaybackCore -> 选择 target_id
    browser   -> 媒体 URL -> HTML audio
    mpd       -> 私有 MPD -> ALSA/USB DAC
    alsa      -> FFmpeg/aplay/libasound 直接输出
    dlna_push -> SOAP -> 外部 Renderer
```

外部控制器把 fnAudio 当作 Renderer 时，DLNA 会话仍会同步回 PlaybackCore，避免维护第二套互不相干的播放状态。

### 转码策略

- 外网或手动请求：非 MP3 可转 MP3。
- DSF/DFF：可转 96 kHz、24 bit WAV。
- CUE 虚拟分轨：可转独立 FLAC 片段。
- 转码文件默认位于配置目录下的 `transcode/`，缓存 TTL 为两天；当前浏览器曲目的 MP3 缓存会在设置媒体 URL 前经 `/api/transcode/warm` 进入高优先级单工作线程队列，普通媒体请求只做低优先级兜底。

### 用户状态

```text
localStorage 兼容数据
  <-> /api/state/user
  <-> revision 冲突检测
  <-> state.sqlite3
```

持久化内容包括收藏、歌单、队列、当前曲目、循环、随机、播放目标和表格偏好。

## 5. 外部依赖

| 依赖 | 来源 | 用途 |
| --- | --- | --- |
| Python 3.12 | fnOS `python312` 应用 | 主服务和 CGI |
| MPD 0.23.12 | `app/target/bin/mpd` | 本机播放和 Renderer 后端 |
| MPD 动态库 | `app/target/lib/` | 私有 MPD 运行时 |
| FFmpeg / ffprobe | fnOS 系统路径 | 探测、转码和部分直接播放 |
| ALSA / aplay / libasound | fnOS/Linux | NAS 声卡和 USB DAC |
| fnOS Trim API | Unix socket | 共享目录授权与文件能力 |
| Spotify、网易、QQ、MusicBrainz | 公网服务 | 元数据、歌词和封面 |

## 6. 必须保持的架构边界

- 前端只通过统一播放 API 选择目标和发送控制，不直接实现 SOAP、ALSA 或 FFmpeg 细节。
- `PlaybackCore` 管状态和队列，输出插件负责实际传输。
- DLNA 的 Control Point、MediaServer 和 Renderer 是独立角色，不在前端混写协议逻辑。
- 音乐库查询应通过 SQLite 分页接口，不把整个大库序列化到浏览器。
- 外部元数据只能后台获取，列表和歌词请求不能因第三方服务阻塞主请求。
- fnOS 特权操作必须通过明确的授权边界，不能把 token 当作普通前端状态公开。

## 7. 当前扩展点

- `playback/plugins.py` 可注册新的输出插件。
- `dlna/profiles.py` 可基于真实互操作问题增加设备 profile。
- `MetadataProviders` 可增加新的元数据提供商，但必须保留缓存、超时和匹配评分。
- 音乐库 schema 变更需同时处理迁移、`METADATA_VERSION` 和索引重建。

详细风险和技术债见 `PROJECT_CONTEXT.md`，未完成工作见 `TODO.md`。

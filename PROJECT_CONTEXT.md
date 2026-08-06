# fnAudio 项目上下文

> 生成日期：2026-08-06  
> 当前项目根目录：`C:\path\to\fnAudio`  
> 源码基线来源：`E:\Codex\fnaudio-0.1.7`  
> 当前可识别发布版本：`0.1.154`  
> 文档目的：为后续开发、排障、测试和发布提供可复用上下文

## 最新状态：`0.1.154` 本地完成，设备安装待向导参数

- `C:\path\to\fnAudio\src` 是唯一可继续开发的源码，`src/manifest`、根 `VERSION` 和前端静态资源缓存键均为 `0.1.154`。
- `artifacts/0.1.154/fnaudio-0.1.154.fpk` 由当前 `src/` 通过 `fnpack 1.2.3` 直接构建，大小为 `4,879,719` 字节，SHA-256 为 `81562B56F54490F8C1E84E3D06B76606E2D44AF7B94649C365B364F4B464C2A9`。
- `0.1.154` 包外层有 18 个文件，运行时 `app.tgz` 有 97 个文件；已验证 manifest、前端资源版本、服务端、UI、私有 MPD 和依赖库，且未包含 tests、历史 builds、`__pycache__`、SQLite 或转码缓存。
- 本地验证已通过 50 个 Python 单元测试、`node --check app/ui/app.js`、`node tests/test_ui_queue_columns.js` 和 `node tests/test_ui_mobile_layout.js`。`0.1.154` 尚未安装，设备仍回报 `fnaudio 0.1.153 / running`。
- 真机移动端烟雾验证：上述 `0.1.153` 结构已验收；`0.1.154` 的紧凑返回/搜索、更多菜单歌词移除和到底部分页显示尚待安装后验收。
- 当前设备音乐库为 0 项，尚未用真实长列表验收触控滚动、分页操作、歌词实际播放状态，或“从当前开始播放全部歌曲”完整流程。全新安装、端口变更、停止/启动、两种卸载、USB DAC、移动 WebView 生命周期和 DLNA 互操作也未验证。
- 不要将任何 FPK 解包目录当作开发源码或下一次发布起点。新功能只改 `src/`；每次测试/发布包都须单独创建、记录并验证。
- 已缓存第三方 `FNOS-API` 固定提交作为外部设备验收与运维参考，评估见 `references/FNOS_API_EVALUATION.md`。它是 `trim-cli` 的高权限 REST 包装，不是官方 SDK，也不应接入 fnAudio 运行时。

## 0. 快速恢复入口

如果原开发会话已被删除，按以下顺序恢复上下文：

1. 阅读本文件，确认当前实现、风险和验证基线。
2. 阅读 `RECOVERY.md`，核对源码身份、恢复步骤和禁止事项。
3. 阅读 `TODO.md`，只从未完成的最高优先级项目继续。
4. 涉及架构边界时阅读 `ARCHITECTURE.md` 和 `DECISIONS.md`。
5. 查看 `CHANGELOG_AI.md`，确认最近一次 AI 修改及验证结果。
6. 在项目根目录运行 `git status --short`，先确认未提交变更，再在 `C:\path\to\fnAudio\src` 运行测试；不要从 `E:\Codex\builds` 或旧版本目录恢复代码。

除非文档明确说明，本文中的源码路径均相对于 `C:\path\to\fnAudio\src`。

## 1. 分析范围与结论

- `E:\Codex` 不是 Git 仓库，工作区内没有 `.git`，无法通过提交历史判断文件来源、变更归属和发布对应关系。
- 当前应继续开发的源码是 `C:\path\to\fnAudio\src`。它从历史目录 `fnaudio-0.1.7/` 提取，初始整理基线为 `0.1.148`，当前 `manifest`、根版本标识和前端资源版本为 `0.1.154`。
- `fnaudio/` 是约 `0.1.2` 的旧版；`fnaudio-0.1.3/` 至 `fnaudio-0.1.6/`、根目录 `builds/` 及多个打包暂存目录均属于历史材料，不应直接作为当前源码修改。
- 本项目是面向 fnOS 的本地音乐库和多目标播放器。它不是纯前端网页，也不是单一 DLNA 控制器，而是同时承担音乐库、媒体流、转码、本机播放、DLNA Control Point、MediaServer 和 MediaRenderer 等职责。
- 当前工作目录以 `0.1.154` 为发布基线；已完成歌词队列返回、当前曲目缓存优先级、全量队列装载、队列当前曲目定位、专辑详情序号列和移动端导航/布局修复，具体变更见 `CHANGELOG_AI.md`。
- 已从初始 `0.1.148` 源码基线生成历史 FPK，并以 `0.1.149` 暂存包完成过真实设备升级验证；当前可安装包由 `0.1.154` 源码直接构建，位于 `artifacts/0.1.154/fnaudio-0.1.154.fpk`。各版本的 SHA-256、内容摘要和结构校验记录均保存在对应目录。
- 真实 fnOS 测试设备当前运行 `fnaudio 0.1.153`。`0.1.154` 安装被自定义向导参数阻断；这不等同于新移动布局、到底部分页、长列表交互、歌词实际播放、硬件输出或所有协议场景的完整验收。

## 2. 项目整体架构

### 2.1 技术栈

| 层级 | 实现 |
| --- | --- |
| fnOS 集成 | FPK `manifest`、`cmd/` 生命周期脚本、`config/` 权限与资源声明、`wizard/` 安装配置页 |
| Web 入口 | fnOS iframe + CGI，`app/ui/index.cgi` 调用 `cgi_proxy.py` 转发到本机服务 |
| 前端 | 原生 HTML、CSS、JavaScript，无 npm、打包器或前端框架 |
| HTTP 服务 | Python 3.12 标准库 `ThreadingHTTPServer` |
| 音乐库与状态 | SQLite，WAL 模式；另有内存缓存和文件缓存 |
| 本机播放 | 内置 MPD 0.23.12、ALSA、`aplay`/`libasound`、FFmpeg |
| 网络播放 | UPnP/DLNA SSDP、SOAP、GENA 事件订阅、HTTP 媒体流 |
| 元数据 | Spotify、网易云音乐、QQ 音乐、MusicBrainz、歌词与封面后台任务 |
| 发布平台 | fnOS，`manifest` 声明 `x86`，安装依赖 `python312` |

项目运行时关系：

```mermaid
flowchart TD
    A["fnOS 应用中心 / iframe"] --> B["index.cgi + cgi_proxy.py"]
    B --> C["Python ThreadingHTTPServer :18080"]
    D["浏览器直接访问 18080"] --> C

    C --> E["静态 UI: index.html / app.css / app.js"]
    C --> F["音乐库服务: library.py"]
    C --> G["PlaybackCore + 输出插件"]
    C --> H["DLNA 协议子系统"]
    C --> I["元数据后台服务"]
    C --> J["用户状态服务"]
    C --> K["转码与媒体流"]

    F --> L["library.sqlite3"]
    I --> L
    J --> M["state.sqlite3"]
    K --> N["FFmpeg / ffprobe + 转码缓存"]

    G --> O["浏览器 HTMLAudioElement"]
    G --> P["私有 MPD -> ALSA / USB DAC"]
    G --> Q["外部 DLNA Renderer"]
    H --> R["fnAudio MediaServer"]
    H --> S["fnAudio MediaRenderer"]
    H --> Q
```

### 2.2 分层职责

1. fnOS 包装层
   
   `manifest`、`cmd/`、`config/` 和 `wizard/` 负责安装、升级、配置、启动、停止、卸载、端口和共享目录授权。

2. 入口与代理层
   
   fnOS 通过 `/cgi/ThirdParty/fnaudio/index.cgi/` 打开应用。CGI 代理读取服务端口，并把 fnOS token 转发给本机 Python 服务，用于调用 fnOS 共享目录 API。Python 服务本身默认监听 `0.0.0.0:18080`。

3. 前端交互层
   
   `app/ui/app.js` 维护页面状态、列表浏览、播放队列、播放目标、收藏、歌单、设置、歌词、分享和文件操作。浏览器播放由 `<audio>`/Media Session 完成，远端或本机设备通过统一播放 API 控制。

4. HTTP 编排层
   
   `app/server/server.py` 提供静态文件、JSON API、媒体流、DLNA 描述与 SOAP 路由，并初始化 MPD、元数据、播放核心、SSDP、MediaServer 和 Renderer。

5. 领域服务层
   
   `library.py`、`metadata_service.py`、`state_store.py`、`transcode.py` 分别处理音乐库、外部元数据、用户状态和媒体转码。

6. 播放与协议适配层
   
   `playback/` 用统一的 `PlaybackCore` 和输出插件隔离浏览器、MPD、ALSA、DLNA 推送；`dlna/` 单独实现发现、控制、服务端、渲染器和事件订阅。

### 2.3 关键数据流

音乐库扫描：

```text
配置中的一个或多个音乐目录
  -> os.walk 生成文件签名
  -> 解析音频信息、Tag、封面和 CUE
  -> library.sqlite3 中的 tracks / albums / artists / composers / genres / folders
  -> 分页查询 API
  -> 前端列表或 DLNA ContentDirectory
```

播放：

```text
前端或外部 DLNA 控制器
  -> PlaybackCore 队列和播放状态
  -> browser: 返回媒体 URL，由浏览器播放
  -> mpd/alsa: 私有 MPD 或 FFmpeg + ALSA 输出到 NAS 声卡/USB DAC
  -> dlna_push: SOAP 推送给外部 Renderer
  -> dlna_renderer: 接收外部控制器命令，并把会话同步回 PlaybackCore/UI
```

状态同步：

```text
浏览器 localStorage 兼容数据
  <-> /api/state/user + revision 冲突检测
  <-> state.sqlite3
  -> 收藏、歌单、队列、当前曲目、循环、随机、目标和表格偏好
```

## 3. 目录作用

### 3.1 `E:\Codex` 工作区顶层

| 目录 | 作用与状态 |
| --- | --- |
| `$inspect/` | 单个 FPK 或归档的检查产物。不是运行时源码。 |
| `2026-07-24/` | 历史 FPK 解包、对比和验证工作区。 |
| `2026-08-05/` | 当前为空的日期工作目录。 |
| `android-sdk/` | 本机 Android SDK，用于早期 Android 壳实验。 |
| `android-sdk-tmp/` | Android SDK 临时目录，当前为空。 |
| `builds/` | `0.1.1` 到 `0.1.148` 的大量历史快照、打包目录和检查产物；体积大，不是唯一可信源码。 |
| `fnaudio/` | 旧版约 `0.1.2` 源码。 |
| `fnaudio-0.1.3/` | 早期播放架构拆分阶段源码。 |
| `fnaudio-0.1.4/` | 历史阶段源码。 |
| `fnaudio-0.1.5/` | 历史阶段源码。 |
| `fnaudio-0.1.6/` | 历史阶段源码。 |
| `fnaudio-0.1.7/` | 历史来源目录；迁入 `src/` 时版本为 `0.1.148`，当前活跃源码版本为 `0.1.154`。 |
| `fnaudio-android-shell/` | Android WebView/MediaSession 试验壳，不属于当前 fnOS 主应用。 |
| `fnaudio-pack-stage-*/` | 旧版本 FPK 暂存结构，用于历史打包。 |
| `fnOS Skill/` | fnOS API、CLI 和开发流程参考材料，不进入产品运行时。 |
| `references/` | Volumio、moOde、MPD、upmpdcli 等第三方参考源码，只用于研究。 |
| `tmp-fnaudio-fpk-*/` | FPK 解包和验证目录。 |

根目录的 `.fpk`、`fnpack.exe`、Android SDK 压缩包和预览资源均为工具或构建产物，不是当前应用源文件。

### 3.2 当前源码 `C:\path\to\fnAudio\src`

| 目录 | 作用与状态 |
| --- | --- |
| `app/` | FPK 安装后的主要应用负载。 |
| `app/bin/` | 预留的应用二进制目录，当前没有实质内容。 |
| `app/server/` | Python 后端源码。 |
| `app/server/playback/` | 播放状态机、数据模型、插件注册表、Browser/DLNA/ALSA/MPD 输出适配。 |
| `app/server/dlna/` | SSDP、Control Point、MediaServer、MediaRenderer、SOAP、GENA 订阅、能力 profile 和诊断。 |
| `app/server/services/` | MPD 生命周期、配置生成、进程监督和空闲事件监听。 |
| `app/server/__pycache__/` | Python 自动生成缓存，不应纳入源码或发布管理。 |
| `app/target/bin/` | 随包提供的 MPD 可执行文件。 |
| `app/target/lib/` | MPD 运行所需的动态库。 |
| `app/ui/` | `index.html`、`app.css`、`app.js`、图标、CGI 入口和代理。 |
| `app/www/` | 空的历史或兼容占位目录。 |
| `builds/` | 当前源码目录内部的少量历史 UI 构建和检查快照，也不是运行时源码。 |
| `cmd/` | fnOS 安装、升级、配置、启动、停止、状态检查和卸载脚本。 |
| `config/` | fnOS 权限和资源声明；当前声明 root 运行、两个 data-share 和 `trim.file.sharedAccess` API scope。 |
| `tests/` | Python `unittest` 后端测试，以及若干人工 UI 检查截图和 DOM 记录。截图本身不是自动化测试。 |
| `transcode/` | 遗留的本地缓存种子目录。其中 `library.json` 指向旧 `0.1.6` Windows 路径，不应视为有效运行数据。 |
| `wizard/` | fnOS 安装、配置和卸载向导定义。 |

### 3.3 后端核心文件

| 文件 | 职责 |
| --- | --- |
| `app/server/server.py` | HTTP 路由、静态资源、媒体流、服务初始化和跨模块编排。约 1660 行。 |
| `app/server/library.py` | 扫描、Tag、封面、CUE、SQLite schema、分页、分组、文件夹和增量聚合。约 2001 行。 |
| `app/server/metadata_service.py` | 元数据提供商、匹配评分、任务队列、歌词、封面下载、缓存回收。约 914 行。 |
| `app/server/state_store.py` | 收藏、歌单、播放会话、UI 偏好和 revision 并发控制。 |
| `app/server/transcode.py` | 播放策略、FFmpeg 查找、MP3/DSD/CUE 转码、缓存预热和清理。 |
| `app/server/config.py` | 配置默认值、读写、端口范围约束、代理和 manifest 端口更新。 |
| `app/server/fnos_api.py` | 通过 fnOS Unix socket 调用共享目录授权 API。 |
| `app/server/alsa_player.py` | 独立 ALSA 播放辅助入口。 |
| `app/ui/app.js` | 前端全部状态、DOM、API、播放器和设置逻辑。约 4093 行。 |
| `app/ui/app.css` | 全部桌面和移动端样式。约 1277 行。 |

## 4. 已实现功能

### 4.1 音乐库与媒体解析

- 支持一个或多个 fnOS 音乐目录，并能同步系统共享目录授权。
- 支持后台扫描、扫描进度、错误记录、SQLite 索引和定时变化检查。
- 支持 FLAC、MP3、M4A、AAC、OGG、Opus、WAV、AIFF/AIF、WMA、DSF、DFF 和 CUE；项目文档已明确放弃 APE。
- 解析 ID3、Vorbis/FLAC、MP4/M4A 等元数据，并读取内嵌或同目录封面。
- 支持 CUE 虚拟分轨、分段时长、封面和按分轨转码。
- 提供全部音乐、DSD、文件夹、专辑、歌手、作曲者、类型、最近添加、随机 100 等视图。
- 提供搜索、分页、排序、列显示和列宽偏好。
- 可查询曲目实际位置、文件详情，并调用 fnOS 能力打开所在目录或创建分享链接。

### 4.2 播放与队列

- 统一 `PlaybackCore` 管理队列、当前曲目、播放目标、进度、循环和随机。
- 从列表中任一曲目开始播放时保留完整上下文队列，并将所选曲目设为当前项；收藏和自建歌单会先补齐缺失曲目再建队列。
- 歌词页复用底部播放控制栏的队列入口，点击后会关闭歌词页并进入当前队列。
- 打开当前队列会清空列表筛选，按当前排序计算正在播放项所在页，直接滚动到该行，并仅在实际队列位置显示“正在播放”标识；重复曲目不会被错误地同时标记。
- 专辑、歌手专辑和作曲者专辑详情使用独立默认列集，第一列为“序号”；旧的原始默认列偏好会自动迁移，新建或用户自定义的列偏好仍可在列设置中调整。
- 浏览器本地播放使用 HTML audio，并接入 Web Media Session。
- 本机播放支持内置 MPD、ALSA/USB DAC 设备发现、输出能力探测和播放状态。
- 支持发现外部 DLNA Renderer，并主动推送媒体和发送 Play/Pause/Stop/Seek/Next/Previous。
- 支持播放、暂停、停止、上一首、下一首、seek、循环和随机。
- 仍保留旧 player、UPnP 和 DAC API 作为兼容入口，内部主要转发到统一播放核心。

### 4.3 DLNA

- fnAudio 可作为 DLNA Control Point 搜索和控制其他 Renderer。
- fnAudio 可作为 MediaServer，通过 ContentDirectory 暴露音乐、专辑、歌手、类型和多根目录文件夹。
- fnAudio 可作为 MediaRenderer，接受外部控制器的 AVTransport 和 RenderingControl 命令。
- 支持 SSDP alive/byebye、M-SEARCH、设备描述、SCPD、SOAP、DIDL-Lite、SUBSCRIBE/UNSUBSCRIBE 和异步事件通知。
- 支持 `SetNextAVTransportURI`、连续队列、入站元数据和封面信息，并将 Renderer 会话同步到统一播放状态。
- MediaServer 同时提供原始资源和显式 MP3 fallback 资源。

### 4.4 转码与交付

- 非 MP3 的外网或手动请求可转 MP3。
- DSF/DFF 可转 96 kHz、24 bit WAV，用于浏览器、DLNA 或 DAC 兼容播放。
- CUE 虚拟分轨可转独立 FLAC 片段。
- 支持 Range/流式媒体响应、缓存预热、状态查询和两天缓存淘汰；需要 MP3 转码的当前浏览器曲目会先进入高优先级单工作线程缓存队列。
- FFmpeg/ffprobe 优先使用 fnOS 系统路径，未随项目单独内置。

### 4.5 元数据、歌词和用户状态

- 本地歌词、网易云歌词和 QQ 音乐歌词查询。
- Spotify、网易云、QQ 音乐、MusicBrainz 的专辑/歌手元数据和封面后台任务。
- 提供正缓存、负缓存、过期重试、孤儿实体宽限期和未完成任务恢复。
- 收藏、自建歌单、当前队列、播放会话和表格偏好持久化到 NAS 端 SQLite。
- 通过 revision 检测多窗口或多端写入冲突，并保留 localStorage 首次迁移与离线兼容。

### 4.6 fnOS 生命周期

- 提供安装、升级、配置、启动、停止、状态检查和卸载逻辑。
- 安装时校验或自动选择端口，并同步 `manifest` 与 UI 代理端口。
- 支持保留数据卸载和清除应用配置/缓存两种卸载模式，不删除用户音乐文件。
- 声明 `python312` 依赖、共享目录和 fnOS 文件授权 API scope。

## 5. 未完成或尚未充分验证的功能

以下内容能从阶段文档或实现状态直接判断：

| 状态 | 项目 |
| --- | --- |
| 未完成 | 尚未根据真实互操作问题添加设备专用 MediaServer profile。当前 `profiles.py` 只有通用能力策略。 |
| 待真机验证 | 尚未在真实飞牛移动端 WebView 验证前后台切换、收藏/队列同步和恢复后的播放状态。 |
| 待样本验证 | WAV、DFF 尚无对应真机音乐样本验证；DSF 已有验证记录。 |
| 当前不可用 | 硬件音量控制依赖 `amixer`，阶段记录显示真机没有安装，因此 Mixer 控制不可用，但不阻塞 MPD 播放。 |
| 部分真机已验证 | 用仅版本号不同的 `0.1.149` 包已完成覆盖升级、启动、端口保持、CGI 页面、核心 API 和 MPD 冒烟；全新安装、端口变更、停止/启动、卸载及应用中心字段仍待验收。 |
| 仅探测 | `dlna/upmpdcli_renderer.py` 只检测二进制、版本和进程状态，不是可选 upmpdcli 播放后端。 |
| 试验项目 | `fnaudio-android-shell/` 仍为早期壳：默认地址硬编码为 `198.51.100.62:5666`，版本为 `0.1-test`，缺少 Gradle 工程文件；当前 `build/unsigned-with-dex.apk` 只有 22 字节，不能视为有效成品。 |

另外，代码“已经存在”不等于生产环境“已经验证”。本次只执行了本地单元测试和语法检查，没有重新验证真实 fnOS、USB DAC、MPD 进程、不同 DLNA 客户端、外部元数据服务和移动 WebView。

## 6. 存在的问题和技术债

### P0：先确认和收紧安全边界

1. HTTP API 缺少统一鉴权
   
   服务默认绑定 `0.0.0.0`，多数读写 API、播放控制和媒体流没有登录或权限校验。`trim_api_token()` 主要用于代调用 fnOS 授权接口，不是后端 API 的访问控制。若 fnOS 防火墙没有隔离 18080，局域网中可直连该端口的客户端可能绕过 CGI 入口。

2. 进程权限过高
   
   `config/privilege` 声明 `run-as: root`。服务同时拥有目录配置、文件位置查询、共享授权、媒体读取、进程启动和网络访问能力，任何输入校验问题都会被 root 权限放大。

3. 信息与控制面暴露
   
   `/api/library/location` 可返回真实 NAS 路径；配置写入、共享目录同步/删除、播放控制和媒体端点都在同一服务上。应先建立用户/会话身份和操作级授权，再决定哪些信息可对前端公开。

4. 服务端请求目标缺少充分限制
   
   DLNA 发现会抓取设备 `LOCATION`，事件订阅会向客户端提供的 `CALLBACK` 发起 HTTP 请求。当前只做基本 URL 形状校验，建议限制为 HTTP、局域网地址、合理端口和已发现设备，防止 SSRF 或访问本机敏感服务。

### P1：影响可靠性、可维护性和发布质量

1. 工作区和发布可追溯性仍不完整
   
   当前已有根 README、`.gitignore`、源码哈希清单、从当前源码构建的 `0.1.154` FPK 和校验记录，以及 `main` 分支上的本地 Git 基线提交；但仍没有远程备份、LICENSE、CI、依赖锁定或自动化构建脚本。历史源码、FPK、解包目录和参考仓库曾混在原工作区；`fnaudio-0.1.7/` 内也包含构建快照，不能作为当前发布物来源。

2. 核心文件过大
   
   `app.js` 约 4093 行，`library.py` 约 2001 行，`server.py` 约 1660 行。前端把状态、DOM、API、播放器、设置、分享混在单文件中；后端入口仍集中承担大量路由和服务编排。

3. 自动化测试覆盖存在明显空白
   
   现有 50 个测试集中在 Python 单元层，另有 2 个无浏览器依赖的 Node 回归脚本覆盖队列/专辑列和移动端结构；仍没有前端 E2E、HTTP 路由集成测试、安装/升级/卸载测试，也没有真实媒体流水线、私有 MPD、USB DAC 和多厂商 DLNA 兼容回归。

4. 增量扫描仍是目录全量复杂度
   
   变化检测仍会遍历全部音乐目录并构造、排序完整签名；检测到变化后还会加载大量现有 SQLite 项目再做比对。大音乐库的刷新仍接近 O(n)，不是基于文件事件或变更目录的真正增量扫描。

5. 用户状态冲突合并语义不完整
   
   前端收到 409 后会对收藏做集合并集，并让本地同 ID 歌单覆盖远端歌单。并发删除可能被旧客户端重新加入，歌单的同时编辑也可能丢失。保存进行中发生的新修改没有明确的 dirty/retry 队列保证。

6. 可观测性不足
   
   `Handler.log_message()` 被完全关闭，大量宽泛 `except Exception` 静默降级。日志散落在 stdout、`${TRIM_PKGVAR}/info.log`、MPD 日志和 `/var/log/apps/fnaudio.log`，缺少结构化字段、请求 ID、错误分类、延迟和资源指标。

7. 并发和资源没有统一上限
   
   当前 MP3 缓存预热已改为单工作线程的高低优先级队列，但 `ThreadingHTTPServer` 仍为请求创建线程，流式转码、DSD/CUE 转码和 DLNA 事件通知也缺少全局并发限制或请求限流。并发媒体请求仍可能耗尽 CPU、内存、文件句柄或线程。

8. 凭据落盘
   
   Spotify client secret 会明文写入 `config.json`。API 状态响应已有测试确保不回传 secret，但脚本未显式设置配置文件权限，也没有凭据轮换和统一日志脱敏机制。

### P2：一致性和清理项

1. 版本漂移
   
   `manifest` 是 `0.1.153`，但 `server.py` 的 `server_version` 仍为 `fnAudio/0.1.14`，多个 User-Agent、SSDP SERVER 和 model 字段仍写 `0.1`。旧开发文档还引用过时的 Windows 路径和阶段状态。

2. 源码存在乱码提示
   
   `playback/alsa_output.py` 和 `services/mpd_service.py` 中有已写入源码的乱码中文错误消息，会直接影响故障提示和诊断质量。

3. 重复和遗留代码
   
   `library.py` 重复定义 `safe_float`；`server.py` 与 `library.py` 重复路径规范化/白名单逻辑；`trim_api_token()` 有不可达的第二个 `return None`；设备 payload 同一字典重复写入 `name`，前一个值会被覆盖。`browser_output.py` 和 `dlna_push_output.py` 只做重新导出，旧兼容 API 仍长期保留。

4. DLNA 只实现常用子集
   
   `GetSystemUpdateID` 固定返回 `1`，`BrowseFlag`、`Filter` 和 `SortCriteria` 等参数没有完整语义；互操作诊断只保留有限内存快照，重启后丢失；设备专用 profile 尚未完成。

5. 生成物污染源码目录
   
   `__pycache__/`、测试截图、内部 `builds/` 和 `transcode/library.json` 与源码并置。后者还保存旧 `0.1.6` Windows 绝对路径，容易误导后续开发或被误打包。

## 7. 测试与验证现状

本次分析期间已完成：

```powershell
python -B -m unittest discover -s tests -v
```

- 结果：50 个 Python 测试全部通过，另有 `node tests/test_ui_queue_columns.js` 前端纯逻辑回归通过。
- 覆盖：ALSA 能力、配置、DLNA 诊断与协议、音乐库缓存和 SQLite、元数据服务、状态存储、转码缓存及当前曲目缓存优先级。
- `node --check app/ui/app.js` 通过。
- 使用 Python AST 解析当前 `src/` 中 39 个 Python 文件，全部通过。
- 初始整理时，`src/` 的 136 个文件与原 `0.1.148` 来源逐一比对，缺失 0、哈希差异 0；当前工作状态的完整哈希以 `SOURCE_MANIFEST.sha256` 为准。
- `SOURCE_MANIFEST.sha256` 含 138 条记录，与当前源码文件数一致。
- 使用 `fnpack 1.2.3` 从 `src/` 构建 `artifacts/0.1.148/fnaudio-0.1.148.fpk` 成功。包大小为 4,878,142 字节，SHA-256 为 `856088E19DD926F0ACE2F07C0BB0E76526BB129F6A3A807A27EB2E27686EB4E1`。
- 以 `src` 的完整副本构建仅版本号为 `0.1.149` 的测试包并升级到真实 fnOS x86 设备成功。升级后应用运行正常，服务端口仍为 `18081`，音乐库为 228 首（5 首 DSD），MPD `0.23.12` 正常；CGI 页面及健康、音乐库、播放核心、播放目标和 MPD 状态 API 均通过冒烟检查。
- 使用 `tar` 校验 FPK 外层和内层 `app.tgz` 均可读取；包内 `manifest` 为 `fnaudio / 0.1.148 / x86`，运行时负载含 server、ui、私有 MPD 和动态库，未包含 tests、历史 builds、转码缓存、Python 字节码或本地数据库。详细记录在 `artifacts/0.1.148/VALIDATION.md`。
- 在真实 fnOS x86 设备上，应用中心先拒绝同版本 `0.1.148` 覆盖，随后接受 `0.1.149` 临时测试包并完成覆盖升级；之后已完成 `0.1.150 -> 0.1.151 -> 0.1.152 -> 0.1.153` 覆盖升级。当前 `0.1.153` 的启动、`/api/health` 和移动端结构烟雾已验证；因音乐库为 0 项，长列表触控、歌词实际播放和“从当前开始播放全部歌曲”仍未完成真机验收。

未覆盖：

- 浏览器 UI 单元测试和 E2E。
- 完整 HTTP 路由、权限边界、Range/媒体流集成测试。
- fnOS FPK 安装、升级、配置、停止和卸载自动化。
- 全新安装、端口变更、停止/启动、两类卸载，以及真正的 FFmpeg 流、USB DAC 端到端测试。
- 多厂商 DLNA 控制器/Renderer/MediaServer 兼容矩阵。
- Spotify、网易、QQ 和 MusicBrainz 的稳定网络集成测试。

## 8. 下一步开发建议

### 第一阶段：建立可信基线

1. 将本地 `main` 基线推送至受控私有远程仓库，并为 FPK 建立外部制品备份；LICENSE 与版本策略仍需确认。
2. 已明确 `0.1.154` 的唯一源码和手动可复现 FPK 构建流程，并校验包内文件清单、版本和哈希；下一步应将其固化为自动化构建脚本。
3. 将历史 `builds/`、旧版本、解包目录、第三方参考和 Android SDK 移出源码仓库或转为只读归档。
4. 保留当前 50 个测试作为迁移基线，新增最小 HTTP smoke test 和 FPK 包结构检查。

### 第二阶段：先处理安全

1. 核实 fnOS 是否只允许通过 CGI/应用代理访问 18080；在结论明确前，把直连端口视为未授权入口。
2. 为非 DLNA API 增加统一认证和授权中间层，区分只读库访问、播放控制、设置、共享目录和文件操作。
3. 优先绑定回环地址，或配置 fnOS 防火墙；DLNA 所需的媒体 URL 和协议监听应与管理 API 分离考虑。
4. 收紧 `LOCATION`、`CALLBACK` 和外部媒体 URI：限制协议、LAN 网段、端口、重定向和响应大小。
5. 降低进程权限；若必须 root，至少拆出最小权限辅助进程，并约束配置和缓存文件权限。

### 第三阶段：提高稳定性和可观测性

1. 引入统一结构化日志，恢复访问日志但避免敏感信息，增加请求 ID、任务 ID 和明确错误码。
2. 为扫描、元数据、转码和 DLNA 通知建立有界任务队列，并设置并发、超时、取消和缓存配额。
3. 修复乱码提示、版本漂移、重复函数、重复字典键和不可达代码。
4. 改进状态保存协议，采用操作日志、实体版本或明确的三方合并，正确处理删除和同一歌单并发编辑。
5. 对超大音乐库做基准测试，再决定采用 inotify/目录级签名、变更日志或分片扫描。

### 第四阶段：拆分模块并补齐测试

1. 将 `server.py` 拆为路由、应用服务和启动装配；保持现有 API 契约不变。
2. 将 `library.py` 拆为扫描器、元数据解析、仓储、查询和文件夹索引。
3. 将 `app.js` 拆为 API client、store、library views、player、state sync、settings 和 dialogs；引入轻量模块化即可，不必立即更换框架。
4. 增加前端 E2E、HTTP 集成、媒体 Range、转码并发、状态冲突、安装升级和 DLNA 协议回归。

### 第五阶段：完成真机验收

1. 补充 WAV、DFF 和高规格 PCM 样本，验证解码、seek、时长、封面和输出格式。
2. 在真实飞牛移动 WebView 验证前后台、Media Session、收藏/队列同步和恢复。
3. 建立常见 DLNA 客户端/Renderer 互操作矩阵，只有捕获到真实差异后再添加设备 profile。
4. 完成应用中心全新安装、覆盖升级、改端口、停止残留进程、保留数据卸载和清除数据卸载验收。

## 9. 后续接手约定

- 项目根目录：`C:\path\to\fnAudio`；运行测试和修改源码时默认工作目录为 `C:\path\to\fnAudio\src`。
- 当前发布版本以 `manifest` 的 `0.1.154` 为准，不以目录名 `0.1.7` 为准。
- 根目录当前文档的优先级高于 `docs/history/` 中的阶段记录；历史文档只用于追溯。
- 不要直接从根 `builds/`、旧版本目录或 FPK 解包目录复制文件到当前源码；先确认来源、差异和目标版本。
- 修改播放逻辑时，保持 `PlaybackCore -> output plugin` 边界，不要把 SOAP、ALSA 或 FFmpeg 细节重新放回前端。
- 修改音乐库 schema、Tag、封面或 CUE 解析时，同步评估 `METADATA_VERSION`、迁移、索引重建和大库性能。
- 修改用户状态时，必须覆盖多窗口 revision 冲突、删除语义、保存进行中再次修改和应用重启恢复。
- 修改 DLNA 时，先保留互操作 trace，再基于真实客户端行为添加兼容分支。
- 不应提交或打包 `__pycache__`、测试截图、旧 FPK、历史 builds、本地 SDK、凭据或带绝对路径的缓存文件。

常用只读或验证命令：

```powershell
# 后端单元测试
python -B -m unittest discover -s tests -v

# 前端语法
node --check app/ui/app.js
node tests/test_ui_queue_columns.js

# 查找阶段文档中的未完成项
rg -n '\[ \]|TODO|待验证|未完成' *.md app tests

# 确认发布版本和端口
Get-Content manifest -Encoding UTF8
```

涉及 MPD、FFmpeg、ALSA、fnOS API、真实目录权限、SSDP 或 DLNA 的结果，必须在 fnOS 真机环境再次验证，不能只依据 Windows 本地测试判定完成。

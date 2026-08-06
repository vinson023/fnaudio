# fnAudio 参考源码深度分析与改进方案

## 1. 总结

fnAudio 不应该复制 Volumio 或 moOde 的全部代码，而应该组合两者的优点：

- 使用 moOde 的思路：MPD/ALSA 是本机音频播放主轴，Renderer、DSP、采样率和硬件输出都是系统级能力。
- 使用 Volumio 的思路：后端模块化、输出插件化、统一事件/API、前端组件化、插件生命周期清晰。
- 保留 fnOS 特点：FPK 安装、应用中心生命周期、内置登录入口、NAS 多目录音乐库和本地部署。
- 放弃不适合 fnOS 的部分：云账号依赖、在线插件商店依赖、Raspberry Pi 专用启动逻辑、过度分散的系统脚本。

目标不是把 fnAudio 变成 Volumio 的副本，而是形成一个更轻量的：

```text
fnOS 应用服务
  -> 播放会话管理器
      -> MPD 本机输出
      -> ALSA 直接输出
      -> 浏览器输出
      -> DLNA 推送输出
      -> upmpdcli Renderer 输出
  -> 音乐库索引服务
  -> DLNA Media Server / Control Point / Renderer
  -> Web UI / MediaSession / fnOS 应用入口
```

## 2. 参考项目的关键发现

### 2.1 Volumio 后端

本地参考位置：

- `volumio3-backend/app/pluginmanager.js`
- `volumio3-backend/app/pluginContext.js`
- `volumio3-backend/app/plugins/music_service/mpd/`
- `volumio3-backend/app/plugins/audio_interface/alsa_controller/`
- `volumio3-backend/app/plugins/audio_interface/upnp/`
- `volumio3-backend/app/plugins/user_interface/websocket/`
- `volumio3-backend/utils/pluginapi/`

值得保留：

- 插件按类别组织：音乐服务、音频接口、系统控制、用户界面。
- 插件有明确的 `onVolumioStart`、`onStart`、`onStop`、`onRestart`、`onInstall`、`onUninstall` 生命周期。
- `PluginContext` 给插件提供统一的核心命令、日志、WebSocket、配置管理接口。
- MPD 是一个独立音乐服务插件，而不是散落在按钮事件中的实现。
- upmpdcli 是独立的音频接口插件，并且通过本地 MPD 连接处理 Renderer 播放。
- WebSocket 是状态广播主通道，REST 更适合配置、查询和安装操作。
- UI 已经拆出浏览、播放队列、播放控制、音量、输出设备、设置和插件页面。

不直接照搬：

- Volumio 的 MyVolumio、在线账号、插件商店和订阅功能不应进入 fnAudio 核心。
- Volumio 插件管理器较重，fnAudio 初期只需要本地内建插件注册器。
- Volumio 依赖完整发行版和系统服务，不能直接假设 fnOS 拥有相同的目录、用户和 systemd 配置。

### 2.2 Volumio 前端

本地参考位置：

- `volumio2-ui/src/app/browse/`
- `volumio2-ui/src/app/browse-music/`
- `volumio2-ui/src/app/play-queue/`
- `volumio2-ui/src/app/playback/`
- `volumio2-ui/src/app/components/player-buttons/`
- `volumio2-ui/src/app/components/player-seekbar/`
- `volumio2-ui/src/app/components/audio-outputs/`
- `volumio2-ui/src/app/components/volume-manager/`
- `volumio2-ui/src/app/services/player.service.js`
- `volumio2-ui/src/app/services/play-queue.service.js`
- `volumio2-ui/src/app/services/socket.service.js`

值得保留：

- 播放器底部固定，浏览区域独立滚动。
- 队列、浏览、当前播放、输出设备和设置是独立 UI 模块。
- 播放控制使用服务层统一处理，页面组件不直接拼底层命令。
- 输出设备是一个抽象概念，UI 不需要知道设备是 ALSA、UPnP 还是其他后端。
- 组件有桌面、平板和移动端的独立布局策略。
- 播放队列拥有独立的排序、删除、插入、拖拽和当前项状态。
- 插件可以向 UI 注入设置页面，但核心播放器不依赖具体插件页面。

需要改进：

- fnAudio 不应直接复制 Angular/旧版 UI，而应把这些边界迁移到当前前端技术栈。
- 不复制 Volumio 的云服务界面、订阅入口和过多全局菜单。
- 视觉上保留轻量、浅色、信息密度适中的 fnOS 风格。

### 2.3 moOde 后端

本地参考位置：

- `moode/www/daemon/worker.php`
- `moode/www/daemon/mpdmon.php`
- `moode/www/inc/mpd.php`
- `moode/www/inc/alsa.php`
- `moode/www/inc/audio.php`
- `moode/www/inc/music-library.php`
- `moode/www/inc/renderer.php`
- `moode/www/command/music-library.php`
- `moode/www/command/renderer.php`
- `moode/www/util/mpdconf_merge.py`
- `moode/www/util/restart-renderer.php`
- `moode/etc/upmpdcli.sed.conf`
- `moode/www/engine-mpd.php`

值得保留：

- MPD 是播放状态和音频输出的稳定来源。
- ALSA、MPD、Renderer、DSP 和音乐库各有自己的配置和处理边界。
- 有独立 worker 处理启动、配置修复、数据库、缓存、权限和服务状态。
- 有 `mpdmon` 监控 MPD 解码过慢、buffer underrun，并可自动重启和恢复播放。
- Renderer 不是普通设备列表，而是独立的服务角色和配置对象。
- 音乐库有缓存、数据库、搜索文件和分类文件，不要求每次打开页面都重新扫描全部文件。
- 配置修改后可以合并 MPD 配置并重新启动相关服务。
- CUE、网络音乐源、渲染器、多房间、DSP 和声卡配置都有单独入口。

不直接照搬：

- `worker.php` 这种大型启动守护脚本不适合原样移植到 fnOS。
- moOde 的 Raspberry Pi 启动配置、GPIO、I2S、boot 分区和 sudoers 修复逻辑不适用于飞牛 NAS。
- 大量 PHP 全局会话和系统脚本会增加 fnAudio 的调试成本。
- fnAudio 应该用 Python 服务、独立线程/任务队列和清晰的数据结构替代大范围全局状态。

### 2.4 MPD

本地参考位置：

- `mpd/src/`
- `mpd/src/output/`
- `mpd/src/decoder/`
- `mpd/src/player/`
- `mpd/src/playlist/`
- `mpd/src/storage/`
- `mpd/src/decoder/plugins/`
- `mpd/doc/`

MPD 应承担：

- 队列和播放列表执行。
- 播放、暂停、停止、上一曲、下一曲、seek。
- 播放状态和当前歌曲状态。
- gapless、交叉淡化和播放顺序。
- 解码器和音频输出。
- ALSA/DAC 的最终输出。
- DSD、DoP、PCM 和输出格式协商。

fnAudio 不应继续重复实现 MPD 已经稳定解决的播放引擎问题。fnAudio 的 Playback Core 应变成“会话编排层”，而不是再次成为完整音频引擎。

### 2.5 upmpdcli

本地参考位置：

- `upmpdcli-source/upmpdcli-1.9.17`
- `upmpdcli-source/libupnpp-1.0.3`
- `upmpdcli-source/libnpupnp-6.2.3`

upmpdcli 适合承担：

- 让 fnAudio 作为 UPnP/DLNA Renderer。
- 提供 OpenHome Renderer 能力。
- 接收其他控制器的播放、暂停、seek、队列和播放列表控制。
- 把 Renderer 播放任务交给 MPD。
- 让外部控制端发现 fnAudio，而不是由 fnAudio 主动推送出去。

它不替代：

- fnAudio 的 DLNA Control Point。
- fnAudio 主动推送到其他设备的 `dlna_push_output`。
- fnAudio 自己的音乐库、封面、歌词和前端。

## 3. fnAudio 当前差距

### 后端差距

- `server.py` 仍然是较大的过渡集成边界。
- MPD 目前只是可选探测和基础协议适配，还没有私有 MPD 实例管理。
- ALSA 仍然是自研直连，缺少完整输出能力协商。
- 没有统一的后台进程监督器。
- 没有 MPD `idle` / 事件订阅机制。
- 播放状态主要通过轮询，缺少统一事件总线。
- 本机 Renderer 只有状态骨架，尚未接入实际 SOAP/OpenHome 服务。

### 音乐库差距

- 当前音乐库仍以 Python 扫描缓存为主，不是完整数据库索引。
- 多目录、CUE 虚拟曲目、Tag、封面和实时更新需要统一索引模型。
- 扫描任务、元数据读取、封面读取和 UI 查询仍需要进一步解耦。
- 需要记录字段来源：Tag、CUE、文件名、文件夹、网络封面。

### 前端差距

- 当前 UI 已经有固定底部播放器和移动端适配，但状态、播放目标、歌词、队列仍有较多前端逻辑。
- 设备选择、播放状态和错误处理需要统一状态模型。
- 需要像 Volumio 一样拆出 PlayerService、QueueService、LibraryService、OutputService。
- 需要像 moOde 一样强化本地音乐库、声卡、Renderer 和系统状态页面。

## 4. fnAudio 目标架构

```text
app/server/
├─ api/
│  ├─ playback_api.py
│  ├─ library_api.py
│  ├─ output_api.py
│  ├─ dlna_api.py
│  └─ settings_api.py
├─ playback/
│  ├─ session.py
│  ├─ queue.py
│  ├─ events.py
│  ├─ models.py
│  └─ registry.py
├─ outputs/
│  ├─ base.py
│  ├─ mpd_output.py
│  ├─ alsa_output.py
│  ├─ browser_output.py
│  ├─ dlna_push_output.py
│  └─ upmpdcli_output.py
├─ services/
│  ├─ process_supervisor.py
│  ├─ mpd_service.py
│  ├─ upmpdcli_service.py
│  ├─ library_indexer.py
│  └─ event_bus.py
├─ library/
│  ├─ database.py
│  ├─ scanner.py
│  ├─ metadata.py
│  ├─ cue.py
│  ├─ artwork.py
│  └─ folders.py
├─ dlna/
│  ├─ media_server.py
│  ├─ control_point.py
│  ├─ renderer.py
│  └─ profiles.py
└─ server.py
```

## 5. 分阶段实施方案

### 阶段一：0.1.5，MPD 本机播放真正可用

- 在应用内部生成独立 MPD 配置。
- 使用独立端口和独立数据库/状态目录。
- 由 fnAudio 启停 MPD，不依赖用户手动安装。
- 实现 MPD health check、启动超时、崩溃重启和日志采集。
- 使用 MPD `idle` 获取播放状态，不再只靠 1 秒轮询。
- 浏览器、DLNA 推送和 MPD 都继续使用统一 Playback Core。
- 增加 MPD 输出设备能力探测：
  - PCM 采样率。
  - 位深。
  - DSD Native。
  - DoP。
  - 硬件音量。
  - ALSA mixer。

### 阶段二：0.1.6，音乐库数据库化

- 使用 SQLite 建立曲目、专辑、艺术家、作曲者、类型、文件夹、封面和 CUE 虚拟曲目表。
- 文件变化使用增量扫描，不重新扫描全部音乐。
- 扫描任务放入后台队列，前端显示扫描阶段和进度。
- CUE 只作为源文件，不在列表显示为歌曲；按 INDEX 生成虚拟曲目。
- 支持 `cover.jpg`、`folder.jpg`、Tag 内嵌封面。
- 建立路径安全检查和多根目录映射。

### 阶段三：0.1.7，upmpdcli Renderer

- 将 fnAudio 本机 MPD 暴露为 UPnP/OpenHome Renderer。
- Renderer 名称、端口、友好名称和启停放入设置。
- 外部控制器推送时由 upmpdcli/MPD 接收。
- fnAudio 现有 DLNA Control Point 继续负责主动推送。
- 增加 Renderer 状态、队列和错误日志页面。

### 阶段四：0.1.8，前端重构

- 拆出：
  - `PlayerService`
  - `QueueService`
  - `LibraryService`
  - `OutputService`
  - `LyricsService`
  - `SettingsService`
- 所有播放状态由一个 Store 管理。
- 底部播放器固定，内容区独立滚动。
- 桌面端采用 Volumio 的分区逻辑。
- 移动端采用 moOde 的信息密度，但减少按钮拥挤。
- 输出设备显示能力、状态、不可用原因和当前播放方式。

### 阶段五：0.2.0，系统级音频能力

- 音量模式：软件、硬件、固定音量。
- DSD 模式：Native、DoP、PCM 转换。
- 重采样策略：关闭、固定采样率、按设备能力。
- ALSA 输出配置。
- DSP/均衡器预留插件接口。
- AirPlay、Bluetooth、Snapcast 作为独立输出/输入插件。

## 6. 最终取舍

### 保留

- MPD 作为本机播放主引擎。
- ALSA 作为最终音频输出层。
- upmpdcli 作为本机 UPnP/OpenHome Renderer。
- Volumio 的插件生命周期和输出抽象。
- moOde 的本地优先、库缓存、Renderer、DSP 和硬件输出配置。
- fnAudio 当前的 fnOS 原生入口、FPK 打包、多目录和 DSD/CUE 需求。

### 抛弃

- 前端直接决定底层播放协议。
- 每个输出单独维护一套队列和状态。
- 点击“保存音乐目录”时同步全库扫描。
- 用文件名作为 Tag 的无记录回退。
- 把 MPD、ALSA、DLNA 和浏览器播放写在一个大型服务文件里。
- 云账号、在线插件商店和平台订阅作为核心依赖。
- Raspberry Pi 专用的 GPIO、I2S、boot 分区和系统修复逻辑。

## 7. 代码参考顺序

后续实际开发建议按下面顺序阅读本地源码：

1. `volumio3-backend/app/pluginmanager.js`
2. `volumio3-backend/app/plugins/music_service/mpd/`
3. `volumio3-backend/app/plugins/audio_interface/upnp/`
4. `volumio2-ui/src/app/services/player.service.js`
5. `volumio2-ui/src/app/play-queue/`
6. `volumio2-ui/src/app/components/audio-outputs/`
7. `moode/www/daemon/worker.php`
8. `moode/www/inc/mpd.php`
9. `moode/www/inc/music-library.php`
10. `moode/www/inc/renderer.php`
11. `moode/www/util/mpdconf_merge.py`
12. `mpd/src/output/`
13. `mpd/src/decoder/`
14. `upmpdcli-source/upmpdcli-1.9.17`

## 8. 结论

fnAudio 的正确方向不是复制某个项目，而是：

```text
Volumio 的模块化边界
+ moOde 的 MPD/ALSA 音频链路
+ upmpdcli 的 Renderer 能力
+ fnOS 的应用生命周期和 NAS 音乐库
```

最优先的工作不是继续调整图标或增加更多前端按钮，而是先把 MPD 私有实例、进程监督、数据库音乐库和事件同步建立起来。完成这四项后，后续的 DLNA、USB DAC、DSD、AirPlay、移动端控制和歌词功能都会更容易稳定实现。

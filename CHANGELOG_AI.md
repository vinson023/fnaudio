# fnAudio AI 修改记录

## 2026-08-06：`0.1.151` 队列当前曲目同步与设备验收

- 目标：让“正在播放”只显示在当前播放队列，并在切换歌曲后立即同步标识、分页和滚动位置。
- 修改文件：`src/app/ui/app.js`、`src/tests/test_ui_queue_columns.js`、`VERSION`、`src/manifest`、`src/app/ui/index.html`、`SOURCE_MANIFEST.sha256`，以及根目录恢复文档和 `artifacts/0.1.151/` 验收记录。
- 实现：当前项样式仅在 `state.view === "queue"` 时显示；新增队列展示同步入口，由播放核心快照、远端播放无当前项和本机 CUE 自动切歌共同调用。索引变化时会重新计算目标页、重渲染，并在下一帧滚动到当前行。
- 版本与产物：`0.1.151`；`artifacts/0.1.151/fnaudio-0.1.151.fpk`，4,878,955 字节，SHA-256 `05CC22B336A9AC821B0166A31D401B0383A425DA88679CA928604F8FCBB6A039`。
- 本地验证：50 个 Python 单元测试、`node --check app/ui/app.js` 和 `node tests/test_ui_queue_columns.js` 通过；外层 FPK 与内层 `app.tgz` 可读取，manifest 和静态资源缓存版本均为 `0.1.151`。
- 设备验证：已通过 fnOS 应用中心完成 `0.1.150 -> 0.1.151` 覆盖升级，设备状态为 `running`，保留 228 首音乐、队列和播放状态。打开当前队列显示一个当前曲目标识；点击下一曲后队列即时跳到新曲目所在页，标识随新曲目移动；非队列视图不显示该标识。
- 未验证：全新安装、端口变更、停止/启动、两种卸载、USB DAC、移动 WebView、DLNA 互操作和“从当前开始播放全部歌曲”完整设备端流程。

> 规则：按时间倒序追加。记录目标、实际文件、行为变化、验证和遗留问题。不要只写“已修改”。

## 2026-08-06：建立 Git `0.1.150` 基线

- 执行者：Codex
- 目标：把 `C:\path\to\fnAudio` 从无版本历史的目录转为可恢复、可审计的 Git 工作树。
- 修改文件：新增 `.git/` 元数据；更新 `.gitignore`、根恢复文档和技术决策。
- 版本控制范围：提交当前源码、文档、完整性清单和必要构建工具；排除 FPK、历史 staging、派生包检查目录、运行时缓存/数据库/凭据，以及嵌套第三方 Git 仓库。
- 结果：创建 `main` 分支的初始 `0.1.150` 基线提交，并标记 `v0.1.150`。
- 后续：本地仓库尚无远程备份；应在确认托管位置与访问控制后推送到私有远程仓库。

## 2026-08-06：构建 `0.1.150` FPK

- 执行者：Codex
- 目标：为已完成的队列定位和专辑序号列功能生成可安装 FPK，并将当前源码版本升级为 `0.1.150`。
- 修改文件：`VERSION`、`src/manifest`、`src/app/ui/index.html`、`SOURCE_MANIFEST.sha256`，以及根目录恢复文档和 `artifacts/0.1.150/` 归档记录。
- 版本行为：FPK manifest、根版本标识和 `app.css`/`app.js` 缓存键均为 `0.1.150`；没有修改播放、音乐库或协议行为。
- 产物：`artifacts/0.1.150/fnaudio-0.1.150.fpk`，4,878,790 字节，SHA-256 `B70EAEE3913AC9AEE8C5CE003C5CC409BC8CF535960B702C19398B593F1A8660`。
- 验证：50 个 Python 单元测试、Node 前端回归和 JavaScript 语法检查均通过；外层 FPK 与内层 `app.tgz` 可读取，manifest 和前端资源版本为 `0.1.150`，运行时负载包含 97 个文件且排除测试、缓存、数据库和 Python 字节码。
- 未验证：未安装到 fnOS 真机。`0.1.149` 设备验证不覆盖本包新增的当前队列定位和专辑详情序号列，需单独真机验收。

## 2026-08-06：当前队列定位与专辑序号列

- 执行者：Codex
- 目标：打开当前播放队列时直接定位正在播放的歌曲并提供清晰标识；在所有专辑详情的曲目列表默认首列显示“序号”。
- 修改文件：`src/app/ui/app.js`、`src/app/ui/app.css`、`src/tests/test_ui_queue_columns.js`、`SOURCE_MANIFEST.sha256`。
- 队列行为：底部播放器和导航中的当前队列入口都会清除列表筛选；根据当前排序计算当前项所在页，渲染后滚动至行中部。队列行携带原始队列位置，重复曲目只会在真实当前位置显示“正在播放”标签。
- 专辑行为：专辑、歌手专辑和作曲者专辑详情共用 `albums:tracks:*` 列作用域，新的默认列为“序号、标题、歌手、专辑、大小、格式”；保存的旧默认列会自动迁移，明确自定义的列配置不被覆盖。
- 验证：`python -B -m unittest discover -s tests -v` 通过（50 个测试）；`node --check app/ui/app.js` 通过；`node tests/test_ui_queue_columns.js` 通过，覆盖重复 ID 队列项的正确页定位及旧专辑列默认值迁移。
- 未验证：本轮未构建或安装新 FPK，fnOS WebView、实际长队列滚动和专辑详情的真机视觉效果需要在下一个更高测试版本中验收。

## 2026-08-06：评估并缓存第三方 `FNOS-API`

- 执行者：Codex
- 目标：对照 `heijiangangqin/FNOS-API` 与飞牛官方开发/API 文档，判断其是否能帮助 fnAudio 后续开发，并在有价值时保留可恢复本地快照。
- 应用源码修改：无。未修改 `src/`、未安装该第三方应用、未建立 NAS 会话、未写入任何凭据。
- 缓存：以浅克隆方式保存到 `references/FNOS-API-upstream`，固定提交 `33101767e01a7f413cac5e0ed016f6a9483df526`（`main`，2026-07-21），工作树干净。
- 结论：该项目是 Node.js/Express 对 `trim-cli` 的 REST 封装，适合外部验收、应用中心操作对照、日志导出和设备监控参考；它不提供 fnAudio 所需的媒体/播放能力，也不能取代官方 Scope、ACL、JS SDK 和本地 open-gateway 机制。
- 风险：服务监听 `0.0.0.0:9932`、启用全域 CORS、默认 Bearer token、未受 token 保护的登录路由、明文 NAS 凭据，以及大量自动确认的破坏性管理操作。因此明确禁止作为 fnAudio 依赖或内部 HTTP 服务。
- 文档：新增 `references/FNOS_API_EVALUATION.md`，并更新参考索引、项目上下文和技术决策。

## 2026-08-06：`0.1.149` 临时升级包真机验收

- 执行者：Codex
- 目标：在不卸载现有应用、不清除用户音乐库或播放状态的前提下，验证本次优化后的 `0.1.148` 源码能否在真实 fnOS 上完成覆盖升级并启动。
- 应用源码修改：无。`C:\path\to\fnAudio\src`、`src/manifest` 和 `SOURCE_MANIFEST.sha256` 均未改动，正式开发基线仍是 `0.1.148`。
- 构建方式：复制 `src/` 至 `artifacts/0.1.149/stage/`，仅将 `manifest` 中的版本号改为 `0.1.149`，使用 `fnpack 1.2.3` 构建 `fnaudio-0.1.149.fpk`。
- 产物：`artifacts/0.1.149/fnaudio-0.1.149.fpk`，4,876,087 字节，SHA-256 `B7FD239E26D69AC16CE8C1F4B788AE6528F47E2DBA479FCC33B1CD9B0B507AA0`。
- 安装结果：fnOS 应用中心成功把 `fnaudio` 升级为 `0.1.149`，应用状态为 `running`；服务端口维持 `18081`，原音乐库配置和播放队列保留。
- 完成验证：设备端 `app.js`、`index.html`、`server.py`、`transcode.py` 与 `src/` 哈希一致；CGI 页面正常显示全部音乐；`/api/health`、`/api/library/status`、`/api/playback/core`、`/api/playback/targets`、`/api/mpd/status` 冒烟通过，音乐库为 228 首（含 5 首 DSD），MPD `0.23.12` 运行中。
- 专项验证：当前 FLAC 曲目 `d412eb7fd07a94df` 初始转码缓存未就绪，调用 `POST /api/transcode/warm` 后约 6 秒变为就绪；歌词页不再有 `lyricsQueueBtn`，点击底部队列按钮会关闭歌词页并转到当前队列。
- 未完成：未执行会改变现有队列和播放状态的“从当前开始播放全部歌曲”完整 E2E。全新安装、端口变更、停止/启动、卸载、USB DAC、移动 WebView、FFmpeg 压力和 DLNA 互操作也未在本轮覆盖。
- 文档：新增 `artifacts/0.1.149/{SHA256SUMS,PACKAGE_CONTENTS.txt,VALIDATION.md}`，并同步根目录恢复、待办、架构决策和产物索引文档。

## 2026-08-06：fnOS 真机安装尝试与环境冒烟测试

- 执行者：Codex
- 目标：将 `artifacts/0.1.148/fnaudio-0.1.148.fpk` 安装到用户提供的 fnOS 测试设备并进行基础验收。
- 应用源码修改：无。
- 安装结果：应用中心接受 FPK 上传并完成包解析；确认标准未验证第三方应用提示后，因设备已安装相同或更高的 `fnAudio 0.1.148` 而拒绝覆盖。未卸载、未覆盖或重启现有应用，未改动配置或音乐数据。
- 已发现状态：设备运行的同版本 `fnaudio` 核心文件哈希与当前源码不同，属于优化前代码，不能作为本 FPK 的验收实例。
- 环境验证：现有实例服务端口可访问；`/api/health`、`/api/library/status`、`/api/playback/core`、`/api/playback/targets`、`/api/mpd/status` 均返回 `HTTP 200`；CGI 页面正常加载音乐库，MPD 正在运行。
- 未完成：需要用户明确选择“保留数据卸载后重装当前 `0.1.148` FPK”或“创建更高的独立测试版本”后，才能完成本包的真机安装、升级、端口、启动停止和卸载验收。

## 2026-08-06：重建并归档 `0.1.148` FPK

- 执行者：Codex
- 目标：基于 `C:\path\to\fnAudio\src` 的当前 `0.1.148` 源码构建可安装 FPK，并保留可恢复的包身份和验证记录。
- 应用源码修改：无。
- 构建命令：在 `C:\path\to\fnAudio\artifacts` 执行 `C:\path\to\fnAudio\tools\fnpack.exe build --directory C:\path\to\fnAudio\src`，使用 `fnpack 1.2.3`。
- 产物：`artifacts/0.1.148/fnaudio-0.1.148.fpk`，4,878,142 字节，SHA-256 `856088E19DD926F0ACE2F07C0BB0E76526BB129F6A3A807A27EB2E27686EB4E1`。
- 记录更新：`README.md`、`PROJECT_CONTEXT.md`、`RECOVERY.md`、`TODO.md`、`artifacts/README.md` 以及版本产物目录中的校验文件。
- 验证：50 个 Python 单元测试通过；`node --check app/ui/app.js` 通过；`fnpack` 构建成功；外层 FPK 和内层 `app.tgz` 可读取；包内 manifest 是 `fnaudio / 0.1.148 / x86`，运行时负载中包含 server、UI、CGI、MPD 和运行库，未包含测试、历史 builds、缓存或本地数据库。
- 未验证：尚未在真实 fnOS 设备执行全新安装、升级、改端口、进程生命周期和卸载验证。

## 2026-08-06：歌词导航、当前曲目缓存与全量队列修复

- 执行者：Codex
- 目标：修复歌词页队列返回、优先缓存当前播放曲目，以及“从当前开始播放”没有完整装载列表的问题。
- 修改文件：`src/app/ui/index.html`、`src/app/ui/app.js`、`src/app/server/transcode.py`、`src/app/server/server.py`、`src/tests/test_transcode_cache.py`。
- 歌词页：删除顶部重复的队列按钮；底部播放器的队列按钮在歌词页打开时先关闭歌词视图，再切换到当前队列。
- 当前曲目缓存：新增 `POST /api/transcode/warm`。前端在本地 MP3 转码曲目设置媒体 URL 前请求缓存；后端将当前曲目放入优先级 `0` 的单工作线程缓存队列，普通媒体预热使用优先级 `100`。
- 全量队列：从当前曲目开始播放时队列保留完整上下文，服务端通过 `current_id` 定位当前曲目；收藏和歌单场景会补齐未缓存的曲目 ID 后再创建队列。
- 兼容性：原格式播放、DSD/CUE 转码、远程 DLNA 目标及既有 `/api/transcode/status` 行为保持不变。
- 验证：`python -B -m unittest discover -s tests -v` 通过，50 个测试；新增缓存优先级回归测试。`node --check app/ui/app.js` 通过。
- 未验证：尚未在真实 fnOS WebView、真实大歌单和实际 FFmpeg 转码负载下完成端到端验证。

## 2026-08-06：建立 `0.1.148` 可恢复项目目录

- 执行者：Codex
- 目标：把当前项目、文档和恢复上下文整理到 `C:\path\to\fnAudio`，避免依赖历史 AI 会话。
- 源码基线：`E:\Codex\fnaudio-0.1.7`，`manifest` 版本 `0.1.148`。
- 新建根文档：`README.md`、`PROJECT_CONTEXT.md`、`ARCHITECTURE.md`、`DECISIONS.md`、`TODO.md`、`CHANGELOG_AI.md`、`RECOVERY.md`。
- 新建索引和策略：`docs/INDEX.md`、`docs/history/README.md`、`artifacts/README.md`、`.gitignore`、`VERSION`。
- 复制源码：将当前可继续开发的代码、测试、MPD 二进制和动态库复制到 `src/`。
- 归档文档：旧迁移说明、阶段 TODO、发布片段和原始分析归档到 `docs/history/`。
- 排除内容：根 `builds/`、旧版本源码、FPK 解包目录、参考仓库、旧 FPK、`app.tgz`、陈旧 `transcode/library.json` 未作为当前源码引入。
- 生成内容：`SOURCE_MANIFEST.sha256` 和 `docs/SOURCE_INVENTORY.md` 记录恢复快照身份。
- 产品行为变化：无。没有修改 Python、JavaScript、CSS、fnOS 配置或生命周期脚本内容。
- 原工作区变化：保留不动；此前只在原当前源码中新增过一份 `PROJECT_CONTEXT.md`。
- 验证：在 `C:\path\to\fnAudio\src` 重新运行 49 个 Python 单元测试，全部通过，耗时约 0.9 秒。
- 语法验证：`node --check app/ui/app.js` 通过；39 个 Python 文件 AST 解析通过。
- 一致性验证：136 个源码文件均能在原 `0.1.148` 来源中找到，SHA-256 差异为 0。
- 恢复验证：根目录必需文档无缺失，`VERSION` 与 `src/manifest` 均为 `0.1.148`，源码清单为 136 条，Markdown 代码块完整。

## 记录模板

```markdown
## YYYY-MM-DD：标题

- 执行者：
- 目标：
- 修改文件：
- 行为变化：
- 数据或兼容性影响：
- 验证：
- 未验证：
- 后续事项：
```

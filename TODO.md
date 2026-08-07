# fnAudio 待办

> 当前源码版本：`0.1.175`  
> 本文件是当前唯一有效待办列表。`docs/history/` 中的 checklist 只用于追溯。

## 0.1.175 后续最高优先级

- [ ] 使用支持原生 DSD 的真实 DLNA Renderer 验证 DSF/DFF 源码直推、采样率保持和自动下一曲。
- [ ] 为不支持原生 DSD 的 Renderer 增加明确的“设备不支持源码 DSD”错误提示；不自动转码。

- [ ] 使用真实 USB DAC 验证首帧、停止、切歌、息屏后台连续播放至少 20 首。
- [ ] 使用至少一个真实 DLNA Renderer 验证 `SetNextAVTransportURI` 和不支持 NextURI 时的自动推进。
- [ ] 在多种 Android 设备安装 0.1.175 APK，收集“解析错误”设备型号、Android 版本和安装日志；Debug 签名不能替代正式发布签名。
- [ ] 验证 Android 远程输出时通知栏/锁屏封面与控制状态；USB DAC 模式保持 MediaSession 通知可见。
- [ ] 修复/记录 App Center 第三方包升级的 UI-only 依赖/向导限制，避免后续只能 SSH 覆盖部署。

- [ ] 为不支持 `SetNextAVTransportURI` 的外部 DLNA Renderer 增加服务端常驻 transport 监控和自动推进，彻底移除对前端后台计时器的依赖。
- [ ] Android 远程输出模式增加只负责展示和控制的 MediaSession/通知实现，不能让 ExoPlayer 同时从手机扬声器出声。
- [ ] 建立 USB DAC/DSD 测试矩阵：DSF、DFF、DoP、Native DSD、44.1/48kHz 家族、96/192kHz 和设备热插拔；DLNA DSD 不允许自动 PCM fallback。

## P0：安全边界

- [ ] 核实 fnOS 对 `18080` 的防火墙和代理隔离；记录局域网是否能绕过 CGI 直连。
- [ ] 为非 DLNA API 设计统一认证与授权，区分读库、播放、设置、共享目录和文件操作。
- [ ] 评估管理 API 绑定回环地址的方案，并单独满足 DLNA 媒体访问需求。
- [ ] 限制 DLNA `LOCATION`、GENA `CALLBACK` 和外部媒体 URI 的协议、LAN 网段、端口、重定向和响应大小。
- [ ] 评估取消 root 主进程；若暂时必须 root，收紧配置、数据库、缓存和日志文件权限。
- [ ] 为设置、共享目录删除和真实路径查询增加操作级权限测试。
- [ ] 用目标 fnOS 固件确认 Android token Cookie/Authorization 的最小必要字段；删除确认无用的候选 Cookie 名称。
- [ ] 用证书指纹固定或自定义 CA 替代 Android 自签名兼容模式中的任意证书信任。

## P1：建立可追溯发布基线

- [x] 在 `C:\path\to\fnAudio` 初始化 Git，创建 `main` 分支；每个发布版本以独立提交和标签记录。
- [ ] 确认项目许可证、维护者和版本策略。
- [ ] 建立单一 FPK 构建脚本，禁止从历史 builds 或解包目录组装发布包。
- [x] 生成 `artifacts/0.1.172/` 的 FPK/APK 摘要与 SHA-256，验证 FPK manifest、APK badging、APK v2 签名和关键包内文件哈希；仍需自动化。
- [x] PC 右键菜单移除“播放”和“插播所选项目”，并保持移动长按菜单与歌曲操作对话框独立。
- [x] “打开包含的文件夹”改为把歌曲父目录传给 fnOS 文件管理，避免完整歌曲路径触发打开文件行为；是否能在宿主内自动选中文件仍需确认。
- [x] 为 Android Media3 通知和无封面歌曲增加白色播放圆环；占位图使用单一私有文件 URI，避免大队列重复位图数据。
- [x] 实现桌面歌曲右键和移动端 550ms 长按的固定四项菜单，并对移动、滚动取消及长按后误点击增加回归保护。
- [x] 同版本真机替换策略：已在用户授权下构建仅版本号不同的 `0.1.149` 测试包，并成功完成设备端覆盖升级；其记录见 `artifacts/0.1.149/VALIDATION.md`。
- [ ] 自动化验证全新安装、覆盖升级、改端口、停止、保留数据卸载和清除数据卸载。
- [ ] 确认应用中心 `python312`、发布者和端口字段显示正确。
- [ ] 建立 Android 正式签名 keystore、离线备份、升级密钥策略和 release 构建流程。

## P1：Android 混合客户端

- [x] 创建 `android-client` Gradle 工程和可安装 Debug APK。
- [x] 实现地址、端口、HTTPS、自签名选项、账号/密码登录表单。
- [x] 实现 Android Keystore 加密的多连接历史；历史页可选择、编辑、删除和新增，连接身份变化默认创建新记录，显式编辑才覆盖。
- [x] 实现登录后直达 fnAudio 的 WebView 宿主，不以 fnOS 桌面作为正常流程。
- [x] 实现 Media3 `MediaSessionService + ExoPlayer`、完整队列、通知/媒体控制基础和 JS bridge。
- [x] 为 Android 非 GET fnAudio API 实现同源受限的原生认证 OkHttp 桥，避免 WebView POST 被 fnOS 网关以 HTTP 200 `invalid token` 拦截。
- [ ] 在目标 fnOS 固件验证 `user.login`、`user.authToken`、`user.tokenLogin` 和 CGI token 交接的实际报文。
- [ ] 支持 2FA、验证码、账号冻结，以及需要 HMAC/`si` 的令牌恢复固件。
- [ ] 为登录协议、连接资料序列化、队列 JSON 和原生状态回传增加自动化测试。
- [ ] 增加播放错误、网络切换、断线重试、URL 过期和服务进程重建的用户可见状态。
- [ ] 评估 Android Auto、蓝牙 AVRCP 元数据、耳机按键和音频路由切换兼容性。
- [ ] 在 Android 真机验证返回键顺序：先关闭对话框/侧栏/歌词/分类详情；根页面第一次提示退出，2.2 秒内第二次返回登录页，且登录页不自动重连。

## P1：可靠性与可观测性

- [ ] 引入结构化日志、请求 ID、错误分类和敏感字段脱敏。
- [ ] 恢复可控访问日志，替代完全关闭的 `Handler.log_message()`。
- [ ] 为扫描、元数据和 DLNA 通知建立有界任务队列；MP3 转码缓存已采用单工作线程高低优先级队列，仍需统一其他后台任务。
- [ ] 设置 FFmpeg 并发上限、请求超时、取消机制、缓存大小和磁盘水位。
- [ ] 为 MPD、扫描、元数据、转码和 DLNA 暴露最小健康指标。
- [ ] 将 DLNA 互操作 trace 持久化或提供明确导出能力。

## P1：状态和大库正确性

- [ ] 重设计用户状态冲突合并，正确表达收藏删除和歌单并发编辑。
- [ ] 保存进行中再次发生变更时设置 dirty 标记并自动重试。
- [ ] 增加多窗口、断网恢复、旧客户端和并发删除测试。
- [ ] 建立 10 万曲目级扫描、分页和内存基准。
- [ ] 根据基准评估目录级签名、inotify 或分片扫描，降低每次变化检查的 O(n) 成本。

## P2：代码整理

- [ ] 修复 `alsa_output.py` 和 `mpd_service.py` 中的乱码错误消息。
- [ ] 统一 `server_version`、User-Agent、SSDP SERVER、model 和 manifest 版本来源。
- [ ] 删除 `library.py` 重复的 `safe_float` 定义。
- [ ] 合并 `server.py` 与 `library.py` 重复的路径白名单和规范化逻辑。
- [ ] 删除 `trim_api_token()` 的不可达返回语句和设备 payload 的重复 `name` 键。
- [ ] 评估旧 player、UPnP 和 DAC 兼容 API 的弃用计划。
- [ ] 将 `server.py` 拆成路由、应用服务和启动装配。
- [ ] 将 `library.py` 拆成扫描、解析、仓储和查询模块。
- [ ] 将 `app.js` 拆成 API、store、library、player、state sync、settings 和 dialogs 模块。

## P2：协议与设备兼容

- [ ] 使用真实客户端 trace 决定是否增加设备专用 MediaServer profile。
- [ ] 正确维护 DLNA `SystemUpdateID`，而不是固定返回 `1`。
- [ ] 明确实现或拒绝 `BrowseFlag`、`Filter`、`SortCriteria` 的完整语义。
- [ ] 决定 `upmpdcli_renderer.py` 保持探测器、升级为后端，还是删除。
- [ ] 记录硬件 Mixer 的支持策略；当前真机缺少 `amixer`。

## 真机验收

- [x] 使用 `0.1.151` 覆盖升级包在 fnOS 浏览器界面验证：打开当前队列会定位到当前歌曲；切换下一曲后队列立即翻至新曲目所在页，且唯一“正在播放”标识随之更新；非队列视图不显示该标识。
- [x] 使用 `0.1.153` 覆盖升级包在 fnOS 移动视口完成烟雾验证：更多菜单搜索和返回可用，顶部分类已移除，歌曲列表滚动容器与固定分页栏存在，歌词顶部操作区不重叠。
- [ ] 在真实 fnOS WebView 验证：专辑、歌手专辑和作曲者专辑详情均默认把“序号”显示在首列；以及队列定位与播放状态恢复。
- [ ] 在不干扰用户现有队列和播放状态的窗口，执行“从当前开始播放全部歌曲”完整端到端验收，确认队列包含完整上下文且所选曲目为当前项。
- [ ] 使用 WAV 样本验证解析、时长、seek、封面和 MPD/浏览器播放。
- [ ] 使用 DFF 样本验证解析、DSD 转 WAV、seek 和 DAC 输出。
- [ ] 在真实飞牛移动 WebView 验证前后台切换、Media Session、收藏/队列同步和恢复。
- [ ] 安装 `0.1.173` FPK 与配套 Android APK，确认登录后直接进入 fnAudio、不进入 fnOS 桌面，并执行 USB DAC、DLNA/DSD、跨端恢复和通知栏专项验收。
- [ ] 在 Android 真机分别播放无封面和有封面歌曲：确认媒体卡片/通知使用白色占位图、真实封面仍优先，并检查切歌、后台和息屏更新。
- [ ] 在桌面浏览器和 Android WebView 验证歌曲右键/长按菜单：四项顺序正确，滚动不误触，松手不播放，完整上下文入队，收藏只添加，加入队列/歌单均成功。
- [ ] 在 Android 真机验证原生认证队列 POST：响应为 JSON，不再出现 HTTP 200 `invalid token`；同时抽查用户状态保存、播放控制和设置保存。
- [ ] 用至少两首歌曲验证 Android 前台、后台、息屏、自动下一首、通知控制、锁屏控制、耳机拔出和蓝牙媒体键。
- [ ] 验证历史连接切换、过期 token 回退密码、自签名 HTTPS、HTTP、错误端口、IPv6 和外网反向代理。
- [ ] 在 Android 真机保存至少两个不同 NAS（以及同 NAS 不同账号），验证新增、编辑、去重、切换和删除互不覆盖。
- [ ] 继续验收输入法直接覆盖固定播放器、键盘弹出/收起流畅度及不支持 Virtual Keyboard API 时的降级行为。
- [ ] 验证 USB DAC 热插拔、不同采样率、DSD 和 MPD 重启恢复。
- [ ] 建立常见 DLNA 控制器和 Renderer 的互操作矩阵。
- [ ] 验证 Spotify、网易、QQ、MusicBrainz 超时、限流、错误响应和缓存降级。

## 自动化测试缺口

- [ ] 扩展前端单元测试和桌面/移动 E2E；现有 Node 回归覆盖队列/专辑列、移动布局，以及 Android bridge/CGI token fallback 的静态契约。
- [ ] HTTP API、认证、Range、媒体流和错误响应集成测试。
- [ ] MPD 进程生命周期和输出配置测试。
- [ ] FFmpeg 实际转码与并发测试。
- [ ] FPK 安装、升级、配置和卸载测试。
- [ ] 多客户端 DLNA 协议回归。
- [ ] Android instrumented test：登录页、历史切换、WebView 直达、MediaSession 队列和后台服务重建。

## 完成定义

一个事项只有在以下条件满足时才能勾选：

1. 代码或配置已经落地。
2. 自动化测试覆盖关键行为并通过。
3. 涉及 fnOS、硬件、WebView 或 DLNA 时已完成对应真机验证。
4. `PROJECT_CONTEXT.md`、本文件和 `CHANGELOG_AI.md` 已同步更新。
5. `SOURCE_MANIFEST.sha256` 已重新生成。

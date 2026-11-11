# fnAudio 以后的目标（Android 审计面）

> 当前发布清单范围（2026-11-11 · R540）：**61 个文件 / 15,122 行** Java。相对 R530 的 14,644 行是多 78 行，全部落在安卓端的崩溃防护上：`MainActivity` 新增 `persistProfile`／`describeFailure` 两个辅助方法，并给三处会抛到 UI 线程的调用加了兜底（自签名 TLS 栈装配、AndroidKeyStore 落盘、WebView 证书错误回调里对 `profile` 的空引用），`FnOsAuthClient.connect` 包住请求构造与 enqueue；之后又多了 6 行——`MainActivity` 把认证启动挪到工作线程，解决强制 HTTPS 下的 `NetworkOnMainThreadException`；R533/R534 再 +88 行：`LoginActivity` 把 `<id>.fnos.net` 名字交给解析器、`FnOsAuthClient` 把 DNS 失败与访问码失败分开报、`FnConnectResolver` 先试局域网地址、AUTO 模式在 HTTPS 下也会回落中继。（曾试过把响应里的 `fn` 字段当 API 端点，确认那是浏览器门户后已撤销。）R536 再 +21 行：`ConnectionProfile.withEndpoint` 不再清掉 `trustSelfSigned`，只在 host 变化时丢弃证书指纹。R537 再 +56 行：`HttpClientFactory` 把**裸 IP 地址**视为「无法用主机名校验的端点」（公共 CA 不给地址签证书），并在受信端点还没有指纹时先连上、由认证流程记录指纹，而不是退回系统根证书。R538 再 +170 行、**新增 1 个文件** `network/ConnectAddressOverride.java`：让档案保留证书所属的域名、把 socket 连到 FN Connect 已探明的地址，于是 TLS 能真正用公共 CA 校验证书（NAS 在 5667 上出示的是 Let's Encrypt 签发给 `<FN ID>.fnos.net` 的证书），不再需要「信任所有证书」。R539 再 +34 行：修正 `fn` 数组被 `optString` 渲染成 JSON 文本后误当 IPv6 解析的问题（会导致 host 带引号、URL 非法）。R540 再 +25 行：新增 `ConnectionProfile.isFnConnectRoute()`，并让 TLS 策略对**由服务端下发的 FN Connect 路由**一律接受证书（对齐官方客户端的行为）。没有新增文件，也没有碰审计面里已登记的四枚类。

> 当前发布清单范围（2026-11-09 · R530）：**60 个文件 / 14,644 行** Java。相对 R524 的 +620 行全部落在电视端两枚已有类：`TvApi` 新增搜索、账号收藏/播放列表、分类视图（`searchTracks`／`userState`／`tracksByIds`／`groupsByView`／`creatorTracks`／`tracksByView`），`TvMainActivity` 把「收藏 / 播放列表 / 搜索 / 设置」接进侧栏、把「类型 / 作曲者 / DSD / 随机 100」接成首页快捷入口，侧栏改为可滚动以容纳十项。没有新增文件，也没有碰审计面里已登记的四枚类；本文件仍是「以后的目标」，电视端只是继续留在发布哈希范围内。
> 当前发布清单范围（2026-11-09 · R530 附注）：本轮同时新增两个独立电视构建类型 `tvArm64`、`tvArm32`（`applicationId com.fnaudio.client.tv`，各自只带一个 ABI 的 `libgojni.so`），由 `tools/build_tv_apk.ps1` 出包；`tvArm32` 的 32 位库取自官方 fnOS 1.33.4 包内同版本产物，JNI 符号与仓内 arm64 库逐项一致。

> 当前发布清单范围（2026-11-09 · R524）：**60 个文件 / 14,024 行** Java。相对 R521 的 +13 个文件／+3,572 行全部是新增的电视端：`android-client/app/src/main/java/com/fnaudio/client/tv/` 下 12 枚类（`TvApi`、`TvPlayer`、`TvUi`、`TvArtworkLoader`、`TvCardView`、`TvShelfView`、`TvShelfNavigator`、`TvCardGridView`、`TvTrackListView`、`TvLoginActivity`、`TvMainActivity`、`TvNowPlayingOverlay`）加 1 枚 `TvMockSeedTest` 仪器测试；同一 APK 双入口（手机 `LAUNCHER`、电视 `LEANBACK_LAUNCHER`），未新增任何 Gradle 依赖，播放走 Activity 内自持的 `ExoPlayer` 而不复用 `PlaybackService`。审计面里已登记的四枚类一行未改，本文件仍是「以后的目标」，这 13 个新文件同样只是进了发布哈希范围，不因它们回到逐轮排期。
> 当前发布清单范围（2026-11-09 · R521）：**47 个文件 / 10,452 行** Java。相对 R506 的 +28 行全部落在 `LoginActivity`：登录期间把按钮从「登录」换成「取消登录」，并让它中断在途的 fnOS 握手与 FN Connect 解析（`cancelLogin()` + 两个 `cancel()` + `setBusy` 文案切换），另有一枚契约测试钉住该行为。没有新增文件，也没有碰审计面里已登记的任何一枚类；本文件仍是「以后的目标」，不因这 +28 行回到逐轮排期。
> 当前发布清单范围（2026-11-07 · R506）：**47 个文件 / 10,424 行** Java。这一面相对 R456 的增量全部落在 `MainActivity` 的捆绑脚本清单上，没有一处是播放或登录实现：R498 补 `native_share_bridge.js`（`index.html` 声明了它，而本清单的守卫要求声明过的脚本必须由 APK 内联，不能留给 NAS 资产，因此这一行是守卫强制的结果而非实现改动；该模块在安卓上不会生效——WebView 里没有可读的飞牛桌面父文档，`parentShellDocument()` 返回 null 直接落到内置面板——登记它是为了让两端脚本集合保持同源）；R506 再把 `response_json_loader.js` 与 `metadata_request_loader.js` 从清单末尾挪回 `metadata_response_policy.js` 之后，两项一直都有内联，只是排在了页面声明顺序之外，`src/tests/test_android_bundled_scripts.py` 现在同时钉住覆盖、顺序与真 Java 跑完的内联结果。实现审计仍是独立后续目标。

> 当前发布清单范围（2026-11-02 · R456）：**47 个文件 / 10,422 行** Java。0.2.125／0.2.129 两次发布未记账，按现盘与发布清单重新取证后补记本行：新增 `PinnedHttpsInstrumentedTest`、`MainActivityWebViewInstrumentedTest` 两枚仪器测试，并在 `HttpClientFactory`／`MainActivity`／`PlaybackService` 等既有面加入证书固定观察者与原生登出。本轮未改 Java 实现，实现审计仍是独立后续目标；下方 R258 的 9,947 行及迁出时快照保留用于追溯。

> 当前发布清单范围（2026-10-22 · R258）：**46 个文件 / 9,947 行** Java。按磁盘与发布清单重新取证，补记此前登录可见性、访问码与 Cookie 修复造成的统计漂移；本轮未改 Java，实现审计仍为独立后续目标。下方 R254 的 9,797 行及迁出时快照保留用于追溯。

> 当前发布清单范围（2026-10-21 · R254）：**46 个文件 / 9,797 行** Java，包含本轮新增的 Cookie 编码与回归测试。下文 44 个文件 / 9,713 行是迁出时的历史快照，保留用于追溯；新增修复不代表重新启动全量 Android 审计。统计按 SOURCE_MANIFEST 范围计算，排除 Gradle 生成文件。

本文件是 2026-09-23 负责人裁定的落点：**把安卓的审核移出本次目标，作为以后的单独目标进行**。
裁定理由同样是负责人原话——安卓的代码已经全部写完了，**不需要你审查**。

因此 R130 折进代码账的 4 枚 Android 面，自 R167 起**退出逐轮深读面**：不再占用终止条件 (1)
的可离线代码待办分母，也不再由逐轮目标排期。移出**不等于删除**，更**不等于关闭**：
它们仍在发布与门禁哈希范围内，仍然需要一次独立立项的 Android 专项审计才能结案。

## 第一节 · 迁出范围（Android 客户端审计面）

迁出时的历史登记：`android-client` 下已跟踪的 `.java` 共 **44 个文件 / 9,713 行**
（磁盘上另有 Gradle 生成的 `app/build/.../BuildConfig.java`，未跟踪、不在发布哈希覆盖面内，
因此不计入本账）。本轮迁出的是负责人点名的四枚已审计面：

| 迁出面 | 现盘登记 | 角色 |
| --- | --- | --- |
| `RemotePlaybackPlayer.java`（370 行） | `android-client/app/src/main/java/com/fnaudio/client/playback/` | 投送（远端）播放客户端 |
| `PlaybackService.java`（1,406 行） | 同上 playback 包 | 前台服务与宿主 MediaSession 桥 |
| `AuthenticatedBitmapLoader.java`（412 行） | 同上 playback 包 | 带凭据的封面位图加载 |
| `FnConnectRelayConfigClient.java`（258 行） | `android-client/app/src/main/java/com/fnaudio/client/network/` | 飞牛中转配置客户端 |

其余 40 枚已跟踪 `.java`（合计 9,713 − 2,436 ＝ 7,277 行）随本轮一并退出逐轮排期：
既然整个 Android 审计面都已移出本次目标，逐轮目标不再对任何 `.java` 承诺深读。

## 第二节 · 迁出后留下的账

- 代码账（`TODO.md` 的欠读清单条目）里 R166 之前登记的欠读总量 **18,225 行** 是当时真值，
  **按「只追加、不改写」规则原样保留**；R167 的追加注记给出重算后的剩余欠读总量。
- 四枚类的点名与「（N 行）」登记值同样保留，因为兄弟守卫
  `src/tests/test_scope_entry_subsumption.py` 要求代码账必须仍然点名它们并匹配现盘行数。
  范围收敛不能表现成名字消失——那样守卫会把「移出」判成「丢失」。
- 钉住本轮裁定的守卫是 `src/tests/test_android_audit_scope_moved_out.py`：
  重新给逐轮目标排期任何一枚 Android 面、改写历史数字、把本文件删掉或在
  `docs/INDEX.md` 里重复登记，都会判红。

## 第三节 · 与另外两份「以后的目标」的分工

- `docs/external-acceptance.md`：设备与外部材料侧待办的唯一台账（45 条，带取证单与处置计划）。
- `docs/REAL_DEVICE_GOALS.md`：需要真机读数才能推进的长期观察项（固定编号 G01～G11）。
- 本文件：**不需要真机、但负责人已裁定不由逐轮目标推进**的代码审计面。

三者共同构成「以后的目标」，都不进离线门禁的终止分母。

## 第四节 · 启动本项专项审计的前置

1. 负责人显式重新立项（逐轮目标不得自行把它请回来）。
2. 明确审计口径：静态深读、还是 Android 端真机／模拟器行为验证；若是后者，
   载体与凭据按 `docs/REAL_DEVICE_AUTOMATION_0.1.205.md` 与 `docs/ANDROID_RELEASE.md` 的既有约束处理。
3. 凭据一律由负责人持有，**不写入仓库任何文件**（含本文件）。
4. 开工时先复算第一节的行账；任何与登记值不符都要当轮更正三处
   （本文件、代码账注记、守卫常量）而不是只改一处。

## 第五节 · 记录规则

- 本文件只登记**范围**与**前置**，不登记结论：审计没做就没有结论，禁止预写「已审毕」。
- 本文件不写 `TODO.md` 的行号：每记一轮就有一批条目被 prepend，写死的行号在第一次被使用时就已失效。
- 若将来某枚面被重新排回逐轮目标，必须先在本文件写明裁定来源与日期，再由那一轮的记录接手，
  不允许只在代码账里悄悄出现一个新条目。

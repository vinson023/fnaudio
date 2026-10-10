# fnAudio 真机验收目标（以后的目标）

本文件是 2026-09-22 负责人常设指令的落点：**凡是需要真机验证的事项一律从「当前逐轮执行的目标」里移出，
单独作为「以后的目标」执行**。R157 据此把 `TODO.md` 第五桶「长期观察」13 条中只能靠真机或外部材料推进的 11 条
**逐字**迁入此处，给予固定编号 G01-G11；`TODO.md` 原位只留一行迁出指针。迁出**不裁定、不关闭、不改写**任何一条，
条目措辞与迁入时完全一致，11 条摘要冻结在 `src/tests/test_real_device_goals_moved_out.py`。

与 `docs/external-acceptance.md` 的分工：那份台账装的是设备侧**可处置任务**（45 条，带取证单四字段、
R1-R10 逐轮处置与结案记录）；本文件装的是**只登记观察口径**、连处置计划都要等真机读数才能立项的长期观察项。
两者都不进离线门禁的终止分母，但结案形式不同：台账允许逐条裁定结案，本文件在拿到真机读数前只允许「按不可取证结案」。
终止条件 (2) 的口径随本文件成立而更新：设备与外部事项不再占用逐轮任务，本文件与台账共同构成「以后的目标」。

## 记录规则

- 每条待办由 `<!-- BEGIN Gnn -->` 与 `<!-- END Gnn -->` 包住**原文块**，`Gnn` 是它的固定编号，不随本文件行号变化而重编。
- 标记之间的原文**不得改写、不得裁剪、不得补全**：动一个字门禁就变红。
- 勾选状态（`- [ ]` / `- [x]`）只在本文件内推进；`TODO.md` 原位只保留一行非 checklist 的迁出指针。
- 每个原文块之后必须紧跟一行 `> 真机口径：`，写明要哪台设备／什么材料／判定线／不可取证时的结案口径；
  没有真机口径的观察项永远无法凭证据结案，守卫会拒绝缺行。
- 取证结论、负责人裁定、并案与结案说明一律写在标记之外，因此追加内容不会触碰冻结原文。
- 设备登录凭据由负责人持有，**一律不写入仓库任何文件**（含本文件）。
- 本文件不写 `TODO.md` 的行号：每记一轮就有一批条目被 prepend，写死的行号在第一次被使用时就已失效。

## 第一节 · 迁出条目（G01-G11，原文逐字冻结）

以下按迁出前在 `TODO.md` 长期观察段的出现顺序编号，共 11 条。

### 固定编号 G01

<!-- BEGIN G01 -->
- [ ] 若要实现飞牛 APP 内原生同等能力：取得飞牛 APP 官方 Web/FPK 播放桥接，或取得可在宿主内
  编译/注册 fnAudio Flutter playback package 的正式扩展点。没有其中之一时，此项不能由 FPK 单独完成。
<!-- END G01 -->

> 真机口径：缺的是外部材料而不是本机代码：需要飞牛 APP 官方 Web/FPK 播放桥接文档，或宿主内可编译注册 fnAudio Flutter playback package 的正式扩展点。取证口径＝拿到其中之一并跑通一次宿主内原生同等播放；拿不到即按「缺外部材料」结案，并把缺的具体材料名写进本节。禁止用 FPK 侧的自证替代。

### 固定编号 G02

<!-- BEGIN G02 -->
- [ ] 持续推进元数据 provider 可观测性、编码兼容与失败恢复；不把第三方网络可用性当作离线门禁条件。当前歌曲预取的网络异常已具备最多 12 次有界重试，仍需真实网络波动观察。（R76 之后这条有了强制手段：`src/tests/test_zz_socket_guard.py` 把非回环拨号变成失败；此前它只是约定，实际有测试在拨七个真实服务。）
<!-- END G02 -->

> 真机口径：需要真实网络波动样本：provider 预取在有损/限流/慢响应下的 12 次有界重试与失败恢复日志。离线侧 `src/tests/test_zz_socket_guard.py` 已把非回环拨号判失败，因此本条在离线门禁里既不可推进也不可假装推进。判定线＝一份带真实 RTT 抖动的 provider 日志，或按「本机不可制造真实网络波动」结案。

### 固定编号 G03

<!-- BEGIN G03 -->
- [ ] 持续推进首屏列表与封面闪烁的离线指标收敛；真实 WebView 图片解码差异仍需要外部验收，不能以离线门禁替代。
<!-- END G03 -->

> 真机口径：需要真实 WebView 的图片解码差异取证（低端机首屏封面淡入/重绘观感 + 无效 DOM 替换计数的设备侧读数）。离线门禁只能证明无效替换已收敛，不能证明观感达标。不可取证时结案须写明缺哪一档设备。

### 固定编号 G04

<!-- BEGIN G04 -->
- [ ] 持续观测第三方 metadata provider 的真实网络稳定性、编码与限流恢复；离线策略只保障故障可恢复和不阻塞界面。
<!-- END G04 -->

> 真机口径：需要真实外网长期样本：第三方 provider 的编码兼容、限流与恢复曲线。判定线＝至少一轮跨时段（含限流窗口）的真实观测记录；离线只保障故障可恢复、不阻塞界面，不能顶替本条。

### 固定编号 G05

<!-- BEGIN G05 -->
- [ ] 继续以真实 WebView 观察首屏图片解码、GPU 绘制和网络缓存造成的残余闪烁；离线回归只能证明无效 DOM 替换已收敛。
<!-- END G05 -->

> 真机口径：需要真实 WebView 上的录屏与绘制取证：图片解码、GPU 绘制、网络缓存三条来源各自造成的残余闪烁。判定线＝逐来源可指认的残余闪烁清单（含无法归因者），或按「本宿主 WebView 不可取得」结案并记缺的载体。

### 固定编号 G06

<!-- BEGIN G06 -->
- [ ] 首屏加载与封面闪烁继续以离线基准观察；可见元数据回投已在批次内复用页面 ID/位置索引，并将非当前歌曲元数据预取延后至首屏 750ms 静默窗口后再进入空闲调度，不把离线结果替代 WebView/真实设备验收。
<!-- END G06 -->

> 真机口径：需要 WebView/真实设备上的首帧与封面时序取证，用来确认离线基准（批次内页面 ID/位置索引复用、非当前歌曲预取延后至 750ms 静默窗口后进入空闲调度）在真机上没有引入新的可见空窗。离线结果不替代本条。

### 固定编号 G07

<!-- BEGIN G07 -->
- [ ] 元数据 provider 的真实网络可用性继续单独观测；协议、权限和 worker 恢复链已具备离线回归。
<!-- END G07 -->

> 真机口径：需要真实网络可用性观测：协议、权限与 worker 恢复链已具备离线回归，本条只留「真实网络是否长期可用」这一段。不可取证时按「本机不持有所需外网出口」结案。

### 固定编号 G08

<!-- BEGIN G08 -->
- [ ] 首屏列表/封面闪烁仍保持持续观察，不能以离线测试替代 WebView 真机验收。
<!-- END G08 -->

> 真机口径：与 G05、G06 同属 WebView 闪烁族：需要同一台低端 WebView 上的持续观察记录（同一次取证可覆盖三条）。禁止以离线测试通过为由勾选本条。

### 固定编号 G09

<!-- BEGIN G09 -->
- [ ] 首屏列表与封面继续以离线基准验证，暂不宣称已彻底消除所有设备侧闪烁。
<!-- END G09 -->

> 真机口径：需要设备侧闪烁矩阵（不同 WebView 版本 × 低端 GPU）才能宣称已消除；本轮之前没有任何一次真机读数支持该结论，故只登记不勾选。同 G05/G06/G08 一次取证覆盖。

### 固定编号 G10

<!-- BEGIN G10 -->
- [ ] 元数据 provider 仍需持续观察编码、超时、失败恢复与真实网络波动；本轮 smoke 仅作诊断证据，不作为离线门禁。
<!-- END G10 -->

> 真机口径：需要真机 smoke 的原始日志与网络抖动样本：编码、超时、失败恢复与真实网络波动四件都要实测。既有 smoke 结果只算诊断证据，不作为离线门禁，也不构成本条的关闭依据。

### 固定编号 G11

<!-- BEGIN G11 -->
- [ ] 继续量化首屏 DOM 提交次数、封面请求数和元数据回投延迟；离线结果不替代真实 WebView 验收。
<!-- END G11 -->

> 真机口径：需要 WebView 端的计数器导出：首屏 DOM 提交次数、封面请求数、元数据回投延迟三项的实测值。离线基准只能给出下界，判定线＝三项都有真机读数或写明不可取得的具体原因。

## 第二节 · 留在 `TODO.md` 的两条以及为什么

长期观察桶现存 13 条，其中 2 条不含任何真机/外部材料依赖，留在 `TODO.md`：

1. 首屏歌曲页冷启动、分页缓存、稳定行提交与封面调度的**离线**性能回归；
2. 服务端资源上限、发布恢复证据与核心模块可测试边界拆分。

两条都有可离线复算的观测面（回归夹具、资源预算断言、模块边界），推进它们不需要任何一台设备。
`src/tests/test_real_device_goals_moved_out.py` 用摘要钉住这两条：把它们偷偷改成需要真机、
或者往桶里再加第三条而不说明归属，都会判红。

## 第三节 · 开工前置（设备与材料）

- 测试机：内网 198.51.100.24（fnOS 宿主，实体机）。R129 真机取证已实测更正：**SSH 端口 22**；21 上跑的是 FTP，不是 SSH。
- 作废机器：198.51.100.24 自 R182 起不再是验收目标，任何轮次都不要再连它；同段的 SSH 端口 21 记录一并作废。
- 凭据：SSH 与 fnOS 网页端账号口令由负责人持有，**不入仓库**；开工前向负责人逐次索取，用完不复述。
- 样本曲：`C:\path\to\fnAudio\music` 下已放置 1 首无标签样本，用于元数据/封面回退路径的真机取证（负责人 D5 裁定）。
- 权限分档：第一档＝只读取证＋放置样本＋播放＋抓服务端日志；禁止重启设备上的服务、改服务端配置、部署新构建、
  停止正在运行的服务；任何涉及停止服务的动作都要**先向负责人请示**。第二档（安装第三方控制点等改变设备软件栈
  的动作）不属白名单，需另行逐条批准。见 `docs/REVIEW_ROUND_DISCIPLINE.md` 第三节。
- 取证结束必须复验：设备 `/tmp` 无本轮残留、`/etc/resolv.conf` 哈希探测前后一致。

## 第四节 · 与终止条件的关系

持续目标的四项终止条件里，本文件只影响 (2)：「设备／外部项从逐轮任务里移出」。自 R157 起，(2) 的满足形式是
**结构性的**——设备事项全部住在 `docs/external-acceptance.md`（45 条）与本文件（11 条）里，`TODO.md` 的逐轮
任务不再包含任何需要真机的条目；但每条**本身**仍需在真机或有记录的「不可取证」裁定下才算结案，那部分工作
归入「以后的目标」，不阻塞 (1)(3)(4)。本文件的条目一律**不计入终止分母**。

## 第五节 · 建议开工顺序

- 第一批（一次 WebView 取证覆盖 5 条）：G03、G05、G06、G08、G09 —— 同属「低端真实 WebView 上的首屏/封面闪烁」一族，
  需要一台低端 Android + 录屏 + DOM 提交计数器；若拿不到该档设备，五条一起按「缺载体」结案。
- 第二批（一次真机网络观测覆盖 4 条）：G02、G04、G07、G10 —— 同属「第三方 provider 真实网络」一族。
- 第三批：G11 —— 需要 WebView 端计数器导出，可与第一批同场执行，但判定项独立。
- 第四批：G01 —— 依赖外部材料（飞牛官方桥接/扩展点），本机永不可取证，预计按「不可取证」结案。
- 并账口径沿用台账 R3 的做法：同族条目可在主条记一次取证、其余条注明被覆盖，但**不得改写冻结原文**。
## 第六节 · 2026-09-25（R178）测试虚拟机能力分级

负责人提供了一台 fnOS 虚拟机（Debian 12，内核 `6.18.18.c1107-trim`，地址 `198.51.100.141`，SSH 端口 22，
设备登录口令由负责人持有、不写入本仓库任何文件）。它同时是通过 SMB 挂载的工作区宿主，
因此仓库里 `artifacts/` 下的每一个 fpk 都天然存在于设备本地存储，不需要额外上传。
下面把「哪一类工作可以在这台机器上做」一次说清楚。**本节只登记能力边界与一次已发生的真机验收，
G01-G11 的冻结原文、其后的 `> 真机口径：` 行以及条目归属一字未改、一条未动。**

### A 级 · 现在就可测（只读，不改变设备状态）

- 安装态与落位形状：`appcenter-cli list` / `check` / `status`、`/var/apps/<app>` 目录、`target` 链接指向、
  `/usr/local/apps/@appcenter`（系统分区）与 `/vol1/@appcenter`（存储卷）两个集合的差。
- 运行态：`ss -lntp` 端口监听、`/proc/<pid>/cmdline`、`/proc/<pid>/cwd`、`/proc/<pid>/fd` 里打开的 `library.sqlite3`。
- 服务面（无需登录态）：`GET /api/health`、`GET /`、静态资源与其 `?v=<asset_build>` 版本标记。
- 数据面：以只读方式打开曲库 SQLite，核对表、行数与 `tracks` 行的标签字段，判断扫描与元数据链路是否真的跑过。
- 环境回归：`/etc/resolv.conf` 校验和、`/tmp` 残留计数、`df -h`，用来证明一次安装没有顺手改系统配置。

### B 级 · 可测但有副作用（虚拟机可接受，实体 NAS 不做）

- 安装 / 升级 / 卸载 fpk，含 `appcenter-cli install-fpk <fpk> -e <env>` 的向导变量注入。
- 服务生命周期：`stop` 后端口必须消失、`start` 后必须恢复，`ctl_stop=true` 是否真被平台 honour。
- 改配置：端口、曲库路径、`wizard_*` 变量写入后 `config.json` 的实际落地值。
- 造真实曲库文件（例如在 `music/` 下放一首样本歌曲）观察扫描、FTS 索引与封面链路。
- 双实例并存：同一台机器上同时跑生产与 beta 两个 appname／两个端口，用来实证「测试版没和生产版混在一起」。

> 本节与第三节那份「真机取证分档白名单」的关系：第三节的禁令约束的是**实体 NAS**，本节的 B 级只在这台负责人指定的测试虚拟机上成立。本轮的停止／启动服务与安装新构建都发生在 VM 上，依据是负责人「在这台测试机上跑测试」的明示，不构成对第三节的放宽，也不改变「涉及停止服务的动作先在实体机上请示」这条口径。

### C 级 · 这台机器测不了（无论怎么折腾都不行）

- 全部 USB DAC／高解析输出／DoP／DSD：`/proc/asound/cards` 只有 `pcsp`（Internal PC-Speaker），没有 `aplay`、`amixer`，
  `lsusb` 只有 VMware 虚拟 hub 与虚拟鼠标（这台机器本身是 VMware 虚拟机，插不到实体 DAC）；
  `/api/health` 的 `components.mpd.error_category` 实测为 `output_device_missing`。
- Android 真机与锁屏 MediaSession：G03、G05、G06、G08、G09 的载体是手机，不是这台 VM。
- 低端真实 WebView 的重排与闪烁观察（G11 一族）：需要录屏与 DOM 提交计数器。
- 真实外网第三方 provider 的抓取成功率与时延、实体 DLNA 控制点、公网与 fn Connect、
  应用商店托管与云端 CI：都需要本仓库不持有的外部材料或外部网络。

### 已在这台机器上落地的一次 B 级验收（2026-09-25，正式版 0.2.35）

- 用 `install-fpk` 从设备本地路径安装正式版 fpk，向导变量给 `wizard_library_path` 与 `wizard_server_port`；
  安装完成后 `check` 报 `Installed`、`status` 报 `running`、`list` 里版本为 0.2.35、依赖 `python312` 满足。
- **`source=thirdparty` + `install_type=root` 被平台接受**：落位在 `/usr/local/apps/@appcenter/fnaudio`，
  `/var/apps/fnaudio/target` 指向它，`/vol1/@appcenter/fnaudio` 始终不存在；安装前后三个集合的计数是
  12→13（`/var/apps`）、8→8（`/vol1/@appcenter`）、4→5（`/usr/local/apps/@appcenter`）。
  这条读数就是 D4「fnOS 降权还是接受 root」裁定为「接受 root」之后第一次拿到的真机证据。
- 包内 `manifest` 的这份形状是 **fnpack 在打包时就写好的，不是平台安装时改的**：把交付 fpk 用 `tar -xf` 解出来逐字节比，包内 `manifest`
  与设备上 `/var/apps/fnaudio/manifest` 完全相同（两边 SHA-256 都是 `dfadb0dc22e7d89ceb0d2d8e65ed9a7bdd22f70527b29c7b85229630ed2dc0a9`，
  1,500 字节／29 行，源文件 28 行），安装树只是把包内那份原样落盘。改写内容＝键名按列对齐到第 21 列、以 ` = ` 分隔、
  **条目之间没有空行**、**值不加引号**、末尾追加 fnpack 自己算出的 `checksum = d50b5b337f5a23930e5f0a91b945e45c`；
  行尾是**混合**的：24 行 CRLF、5 行裸 LF，裸 LF 只落在三处注释块内部（除每组末行外的前导行保留了源文件的 LF）。
  四个身份键（developer／publisher／maintainer／distributor）在设备上读回仍是 `vinson023`，未被替换成厂商名。
  归属改对了，打包器门禁的理由才讲得通：它要读的那份文件是它自己的上游工具产的，与设备无关，所以必须按「列对齐 + CRLF」的形状去读，
  任何按 `\s` 跨行取值的读法都会把下一行的注释吞进上一个值。
- 同一次解包顺带回答了「设备上装的是哪一次构建」：本轮两次成功打包（中间产物 `2242D9CF7AAC89C988451614E8D4979774F0E3AE138DD2CF8C81C3B0F4D94C90`
  与交付包 `9EB342F13319A708FFF8ABE8549FA33CCF70747DDA082657848584A747D276FF`）之间，包内 `manifest` 只差最后一行 `checksum`
  （`f1ac4603…` 对 `d50b5b33…`），设备读回的是后者，因此设备上跑的就是交付包；而两次 `app.tgz` 的 328 个成员名字、逐个大小、逐个内容
  SHA-256 全部相同，成员内容总长同为 12,997,133 字节，只有 328 个 mtime 无一相同（23:18:04Z 对 23:34:10Z），
  gzip 文件因此相差 14 字节。这是 R177「fpk 摘要只作交付指纹、不作变更证据」在正式版打包器上第一次拿到的逐成员级证明。
- 服务与页面：`0.0.0.0:53199` 监听，`/api/health` 与 `/` 均 200，`ui/app.js` 420,804 字节，
  `index.html` 里 60 处 `?v=` 全部是 `0.2.35-58a38563247b`，与发布产物侧 `SOURCE_PROVENANCE.json` 的 `asset_build` 逐字相同
  （该 JSON 只留在 `artifacts/0.2.35/`，安装树里没有，所以这是一次跨产物比对，不是在设备上读到的）。
- 数据面：曲库 SQLite 已建表并完成一次扫描，`tracks` 1 行（FLAC／audio/flac／44.1 kHz／16 bit／225.186667 s／26,325,514 字节），
  `tracks_search` 1 行（fts5，`tokenize='trigram'`），`library_meta` 14 个键、其中 `track_count=1`。
  样本曲 `伍佰 - 泪桥.flac` 的内嵌标签只有 `date=2024-04-02` 一条，没有 TITLE／ARTIST／ALBUM／COMPOSER／GENRE：
  标题与艺术家是从文件名解析出来的（`item_json.metadata_source` 标为 `filename`），专辑／作曲者／流派落到「未分类／未知作曲者／未分类」占位，
  `covers` 表 1 行 `source=indexed`、缩略图目录里只有一个 `*.none` 占位文件 —— 负责人要的「无标签回落」这一次是真被测到了。
- 两条先前的读数作废并已在上面替换：其一，`library_meta` 并非「10 个键且没有 `track_count`」，两次独立复测都是 14 个键并含 `track_count=1`；
  其二，样本曲并非「带标签、标题艺术家齐全」，那两个值是文件名推导的结果，不是内嵌标签。
  教训：设备侧只读一次就写进结论的读数不可信，本轮所有 §6 读数都要求第二遍独立复测才入账。
- 隔离：beta（`fnaudio-beta`，53299）在同一台机器上全程 running 且 `/api/health` 200，两实例并存互不影响。
- 恢复：`stop` 后 53199 计数归零，`start` 后下一轮探测即恢复监听，随后 `/tmp` 无本轮残留、
  `/etc/resolv.conf` 校验和与安装前相同。

### 从这次验收里得到的两条设备侧教训（登记，不新立代码待办）

1. **`appcenter-cli` 的退出码不可信**：一次 env 文件格式错误导致安装以 `[Error]Something wrong with   environment variables.` 终止，命令仍然返回 0。任何驱动它的自动化都必须判输出文本，不能只判 `$?`。
   本仓库没有任何代码路径调用它（代码目录 `src`／`tools`／`android-client` 三处 grep 命中 0 条；全树只剩本节的散文和一份
   历史 `artifacts/0.1.148/VALIDATION.md` 提到过这个名字），所以这条只作为设备侧口径登记。
2. **向导 env 必须是干净的逐行 `key=value`**：在远端 shell 里用不带引号的 `printf %s\n` 拼这个文件，
   反斜杠会被引号移除前的解析吃掉，两行会粘成一行，直接触发上一条错误。落文件请用带引号的格式串或逐行 `echo`。


## 第七节 · R182 登记的真机专项（不是代码待办，不计入终止分母）

R182 修掉的是「MPD 拒绝 uri 时用户看到一句裸 ACK」，但两条设备侧根因只能在真机上收口，登记在此：

1. **MPD 库生命周期与 fnAudio 不同命**：`mpd.conf` 的 `db_file`／`state`／`sticker`／`playlists`／`log`
   现住在 `@appcenter/fnaudio/share/mpd`（`_data_root()` = app_root/share/mpd），应用搬家或重装即清空；
   实测 2026-10-08 那台机器正因此对 75,769 文件／6.4 TB 冷重建，`status` 报 `updating_db: 1`、`stats` 报
   `songs: 23751`，而 fnAudio 自己的 `library.sqlite3` 已收录 62,684 轨。把它们挪到与 `@appconf` 同生命周期的
   目录是正确方向，但改 `data_root` 会让旧 MPD 进程（`_is_running` 以 config_path 匹配）成为孤儿并占住 56660
   端口——风险高于任何一轮可证范围，因此作为**迁移专项**在真机执行，需要「停旧进程→改配置→重建库→复验」的
   完整序列与回滚点。真机口径：以 `stats songs` 与 fnAudio `tracks` 计数收敛、且重装后 `db_file` 仍存在为验收证据。
2. **MPD 的解码能力面**：`.ape`／`.wav`／`.dff` 未收录时三种 uri 形态全报 `No such song`，`.dsf` 已收录则
   相对形态与 `file://` 裸路径皆可解析（2026-10-08 实测）。R182 后未收录曲目会得到带 uri 与索引进度的可读文案，
   但「这台 fnOS 的 MPD 到底能不能解码 DSD/`dff`/`iso`」仍需真机逐格式验证；DSD 转码产物 `*.dsd-96k-24bit.wav`
   目前只出现在 HTTP 分发路径（`server.py` 的 dsd_wav），MPD 队列路径不转码 DSD，这条差异要在真机上确认是否符合预期。

## 第八节 · R184 登记的真机专项（R186 已在真机上收口；不是代码待办，不计入终止分母）

R184 把「MPD 拒绝队列条目后重试总是怪错目录」与「拒绝文案把原始 ACK 挤在最前」两处修掉并用真机实测定下 `ACK [50@N]` 的槽位含义；以下两件事只能在真机上收口——R186 已在隔离实例 `fnaudio-beta` 上全部收口，生产 `fnaudio` 全程只读观察、未受影响。

1. **升级前的 MPD 库状态迁出 payload**：**成立，已由实证取代推断**。R186 用官方 `appcenter-cli install-local -d <解包目录> -e <INI env>` 把 `fnaudio-beta` 从 0.2.37-beta.1 升到 0.2.37-beta.2：`list` 账本当场跟到新版本，但 `@appcenter/fnaudio-beta` 全部子目录 mtime 重建、预先埋在 `share/mpd/` 的哨兵 `R186CANARY.txt` 消失、`playlists/` 目录被重建，即官方升级确实清空 MPD 的 `db_file`／`state`／`sticker`／`playlists`。与之相对 `@appconf/fnaudio-beta` 与 `@appdata/fnaudio-beta` 存活（`info.log` 保留两次启动记录），但 `config.json` 会被 `install_callback` 按新 env 重写（本轮 server_port 53299→56782）。`cmd/install_init`／`upgrade_init`／`uninstall_init` 全是 19 字节 `exit 0`，**没有任何升级前钩子可以代做迁出**，所以「升级前把这四份文件复制到与 `@appconf` 同生命周期的目录、升级后原样放回」只能由外部流程完成，验收证据仍是 `stats songs` 与 fnAudio `tracks` 计数相符。**R193 更新：该项的迁出方向已由 durable 迁移在代码侧闭环**（MPD 数据根迁至 `@appconf/fnaudio/mpd`，`ensure_config()` 启动前原子回收 legacy 索引），真机判据见第九节第 1 条。
2. **升级通道本身的可靠性**：**已打通并定性**。`install-fpk` 无论同版本还是更高版本一律短路为 `[Info]Application [fnaudio-beta] is installed.`（两条都在真机上证死），且首次安装必须带 `-e` 的 INI env 文件，否则停在 `[Error]Something wrong with environment variables.`；能升级的是 `install-local`。卸载方向：`appcenter-cli uninstall` 不接受任何参数（`-e`／`-a` 均 `unknown shorthand flag`），裸形式只回 `[Info]Uninstall checking` ＋ `[Error]Failed to uninstall fnaudio-beta, please uninstall it from Web UI.`；包内 `cmd/uninstall_callback` 默认 keep，只在 `wizard_uninstall_mode=purge` 或 `FNAUDIO_PURGE=1` 时按 `fnaudio-beta` 白名单删数据 ⇒ 卸载以及「卸载保留什么」只能在 Web UI 侧验证。⇒ 官方生命周期矩阵＝**安装可用（CLI，需 env）／升级可用（仅 CLI `install-local`，代价是重建应用目录）／卸载不可用（仅 Web UI）**；`manual-install` 状态 `enable`。
3. **转码缓存与库索引同目录**（R186 画像）：`@appconf/fnaudio/transcode/` 里同时住着 `library.sqlite3`（321,339,392 B）与转码产物，「清缓存」会连带打掉库索引。另 `library.py:662`／`:907` 是按目录名 `fnaudio-transcode` 排除索引的，真机证明该排除在生产路径有效；把该目录改名复制，产物就会作为 `.cue-segment` 伪曲目进入索引——因此任何「transcode 污染音乐库」的报障，先确认目录名是否仍是 `fnaudio-transcode` 再谈代码。
4. **脏检测与重扫的量级**（R186 画像）：新增一个文件后自动判定 dirty 约需 70~80 s（T+70s 仍 count=0，T+80s 全部到位），随后触发的是 75,663 项级别的全量重扫（约 5 分钟）；同一构建在 8 文件小库上走 `/api/library/status?refresh=1` 手动重扫 <1 s 完成。⇒「扫描慢」的体感来自脏检测窗口＋全量重扫规模，不是单文件解析速度。
5. **真机 API 口径**（R186 修正，防止后续轮次拿错靶心）：`/api/library/count` 不存在（prod 与 beta 均 404），库计数取 `/api/library/status` 的 `count`；`/api/library/groups` 的 `view` 取值是复数（`albums`／`artists`），写成单数只会拿到空数组；回环地址不受 TRUSTED_LAN 放行，beta 必须从 LAN IP 访问；`/api/health` 里 `mpd.error_category:"output_device_missing"` 在 prod 与 beta 同值，是单个 USB DAC 被两个 MPD 争用的常态而非故障。

## 第九节 · R193 登记的真机专项（不是代码待办，不计入终止分母）

R193 把「升级清空 MPD 索引」与「冻结计数被当成实时进度」两件事在代码侧做完，第八节第 1 条的迁出方向**已由 durable 迁移闭环**：MPD 数据根从 `@appcenter/fnaudio/share/mpd` 迁到 `@appconf/fnaudio/mpd`，`ensure_config()` 在启动前把 legacy 索引原子复制过来。以下几件只能在真机上收口。

1. **durable 迁移的判别性验收**（必须做一次卸载重装才成立）：`/api/mpd/status` 的 `data_root` 指向 `.../@appconf/fnaudio/mpd`；`reclaimed_index_from` 首次回收时非空、之后为空；升级／重装后 `database` 大小与 `stats songs` 不被清零，且 `stats songs` 与 fnAudio `/api/library/status` 的 `count` 相符。
2. **TEAC UD-301 需插回**：2026-10-10 实测 `lsusb` 无 `0644:804a`、`/proc/asound/cards` 仅 HDA＋pcsp、`lsmod` 无 `snd_usb_audio`，`/api/playback/targets` 因此不再列出该 DAC。bit-perfect／DSD 端到端验收在设备插回前无法进行，prod `mpd.conf` 也已回落到 `device "default"`。
3. **prod 空闲期的 MPD 读数口径**（R193 已部分证伪，仍需真机确认残余）：`/api/mpd/status` 回 `available:true／running:false／[Errno 111] Connection refused`、`supervisor.desired:false`、`restart_count:0` 在 0.2.39 上属于常态而非故障——`MpdOutput` 走按需启动（`mpd_output.py` 调 `MPD_SERVICE.start()` 才注册监督），没有任何播放请求时本来就不该有 MPD 进程。待真机确认的是残余：`fault.state:DEGRADED`／`consecutive_failures:989` 这类因「MPD 按设计未运行」而反复失败的 idle 监听计数，是否会把无关的健康读数一起拖成 DEGRADED 并在 UI 上误导。

4. **0.2.40 的发布与就地升级实证**：`install-local` 是唯一可用升级入口（`install-fpk` 对已装应用短路），升级后须再跑一次第 1 条判据。



## 第十节 · R195 登记的真机专项（不是代码待办，不计入终止分母）

R195 在代码侧消灭了「本进程把 MPD 的监听号当源端口用掉 ⇒ MPD 永远绑不回来」这条致瘫路径，并在真机 198.51.100.24 上以 0.2.41 取到判别性读数（60 次读压测零自连、`stats songs` 63,995、报障曲目 `addid` 返回 `Id: 6`、15:00 之后 `Failed to bind` 0 条）。以下四件只能在真机上收口。

1. **TEAC UD-301 必须插回才能验收播放**：2026-10-10 第三次实测 `lsusb` 只有 4 个 root hub（无 `0644:804a`）、`/proc/asound/cards` 仅 HDA Intel PCH＋pcsp、`lsmod` 无 `snd_usb_audio`，`mpd.conf` 的 audio_output 因此回落 `device "default"`。载入 DSD 曲目返回「未找到已认证的 USB DAC，已禁止 DSD 转 PCM」且 MPD 不再被拉起；载入非 DSD 曲目返回「MPD 已启动，但没有检测到真实 ALSA 声卡或 USB DAC」。bit-perfect／DSD 端到端验收在设备插回前无法进行；插回后还要确认 `config.json` 里的 `mpd_output_stable_id`（现为 `usb:0644:804a:00160000386ca1d14e45282720120016:dev0`）与 `mpd_output_alsa_id`（现为 `hw:2,0`）是否随重新枚举而变化，必要时在设置页重选设备。 **已由 R196 闭环（2026-10-10 20:40 实测）**：负责人插回 DAC 后 `lsusb` 命中 `0644:804a`、`/proc/asound/cards` 出现 `card0 UD301`，`/api/dac/devices` 回 `alsa_id=hw:0,0`／`stable_alsa_id=hw:CARD=UD301,DEV=0`／`online=true`／`dsd=true`／`DSD_U32`／`pcm_max_rate=352800`／`pcm_max_bits=32`；`config.json` 里过时的 `mpd_output_alsa_id=hw:2,0` 无需人工重选，stable_id 纠偏生效；0.2.42 下报障 `.dsf` 经 `/api/playback/load` 回 200 并 `state=play audio=dsd64:2 bitrate=5644 bitperfect_candidate=true`，24bit FLAC 回 200 并 `audio=44100:24:2`，原生 DSD 与 PCM 端到端验收首次取得双读数且两遍一致。
2. **端口迁移分支仍未在真机上走过一次**：本轮真机读数是「56660 可绑 ⇒ `_ensure_bindable_port()` 不做迁移」（`config.json` 的 `mpd_port` 保持 56660，符合期望），换口路径只由离线测试与仓库外变异证明覆盖。真机口径：先占住 56660，再让 `/api/playback/target` 走 `{"target_id":"mpd"}`，须看到 MPD 起来、`/api/mpd/status` 的 `port` 落在 `ip_local_port_range` 之外，且 `config.json` 的 `mpd_port` 与之一致；同时确认客户端不会因此读到旧端口。
3. **durable 判据的最后一半：卸载重装**（第九节第 1 条的延伸，本轮已就地升级两次并通过）：`@appconf/fnaudio/mpd/database` 2,228,956 B／`stats songs` 63,995 在两次 `install-local` 重建 `@appcenter` 之后仍在，大库由 R194 人工放回（`/root/r194-backup/database.preseed-143216` 是被替换下来的 9,974 B 残库）。尚未取得的是「Web UI 卸载（非 purge）后重装」同一判据仍成立，以及 `stats songs` 与 fnAudio `/api/library/status` 的 `count`（现 62,684）之间 1,311 首差额的口径归属（MPD 收录 `.dff`／`.ape`／封面等非播放项与 fnAudio 过滤规则的差异，需在真机上按扩展名对齐后才好判定是否为缺陷）。
4. **没有 USB DAC 时连 PCM 也放不出，属产品口径待裁定**：`playback/alsa_output.py` 的 `alsa_devices()` 在 `/proc/asound` 探测成功时只保留 USB 形态设备，内建 HDA 声卡因此不进候选、`devices` 恒空，最终把「这台机器压根没有 USB DAC」表达成「没有检测到真实 ALSA 声卡或 USB DAC」。DAC 插回后须确认这条筛选没有误伤（例如 DAC 经 USB 声卡桥接、被其他驱动接管、或以非 USB 形态出现时）；若确认误伤，再决定是否放宽为「USB 优先、无 USB 时允许内置输出」。

> 证据口径：本节每一条都以真机读数入账，且必须第二遍独立复测一致才写结论；拿不到读数一律按「不可取证」结案，不在 `TODO.md` 新立代码待办。

## 第十一节 · R196 登记的真机专项（不是代码待办，不计入终止分母）

R196 把「MPD 队列里的 song id 过期」与「MPD 库里没有这首歌」按 ACK 命令槽位分开，并在真机 198.51.100.24 上以同一序列取到前后对照读数（0.2.41 → 502「索引落后…63991 首…ACK [50@0] {playid} No such song」；0.2.42 → 200 且 `dsd64:2`／`44100:24:2` 真起播）。第十节第 1 条（DAC 插回）已闭环，以下五件只能在真机上继续收口。

1. **陈旧 id 自愈后的起播位置归零，属产品口径待裁定**：`services/mpd_service.py` 的降级路径重跑 `mpd_replace_queue()`，队列重建后曲目从 0 s 起播（实测 P2 复验时 `elapsed` 从 5.993 s 重新计起）。这是可播性优先的取舍，本轮不改码；真机口径：在播放中途让 MPD 自行 `update` 掉一个 `.cue` 虚拟条目（或外部 `deleteid` 当前 Id），确认重建后的位置是否落在旧队列的 `elapsed` 上，再决定是否需要「自愈即续播到原位置」。
2. **`playback_errors` 计数会不会污染诊断口径**：自愈必然在 MPD 侧留下 `exception: no such song` 日志行，`/api/mpd/status` 的 `playback_errors` 因此把 `queue_stale` 计数推高（本轮实测 `count=4／by_category {queue_stale:4}`）。代码复核已证伪「用户可见故障」（该类别 `severity=warning`、`domain=queue`，服务层只对 `domain=output` 升级 fault／重启，`health_error_category()` 只认 `severity=error`，前端零处读取），但 `/api/diagnostics` 与 `/api/health` 快照把它作为「最近播放异常」呈现，长期运行后是否需要在诊断面板上区分「已自愈」与「未自愈」，须拿真机长时读数判定。
3. **`stats songs` 与 fnAudio 库计数的差额归属**（承接第十节第 3 条）：本轮真机读数为 `stats songs` 63,991／63,995 对 fnAudio `/api/library/status` 的 `count` 62,684，差额 1,311 首量级仍未按扩展名对齐；须在真机上区分「MPD 收录了 fnAudio 不展示的 `.dff`／`.ape`／封面旁文件」与「fnAudio 漏收录」，前者属口径、后者才是缺陷。
4. **Web UI 卸载（非 purge）后重装的 durable 判据**（承接第十节第 3 条）：本轮 `install-local` 就地升级再一次通过（`@appconf/fnaudio/mpd/database` 2,302,929 B、md5 `75b481548c66d6acb965426d52d44479` 升级前后一致），但 CLI 无可用 `uninstall` 参数、卸载只能走 Web UI，「卸载重装后索引与配置仍在」这半条判据仍未取得。
5. **端口迁移分支与「无 USB DAC 时连 PCM 也拒」**（承接第十节第 2／4 条，本轮未触及）：`_ensure_bindable_port()` 的换口路径本轮真机读数仍是「56660 可绑⇒不迁移」（`config.json` 的 `mpd_port` 保持 56660）；`playback/alsa_output.py` 只保留 USB 形态设备的筛选在 DAC 插回后未观察到误伤（`/api/dac/devices` 正常列出 UD-301），但「拔掉 DAC 后内建 HDA 仍被拒」这一产品口径尚未裁定。

> 证据口径：本节每一条都以真机读数入账，且必须第二遍独立复测一致才写结论；拿不到读数一律按「不可取证」结案，不在 `TODO.md` 新立代码待办。

## 第十二节 · R197 登记的真机专项（不是代码待办，不计入终止分母）

R197 把「每次 MPD 控制都把自家健康 MPD 当端口窃贼杀掉重启」这条根因在真机 198.51.100.24 上闭合（0.2.44 控制 mean 1920.5 ms → 247.5 ms，MPD pid 全程恒定，`supervisor.restart_count=0`），并对「文件夹点击慢」出具了服务侧证伪读数（控制风暴并发下 roots 5~6／folders 6~22／library 13~66／groups 5~53 ms）。以下五件只能在真机上继续收口。

1. **浏览器端手感复验（负责人主观验收口径）**：用浏览器打开 `http://198.51.100.24:53199`，在 TEAC UD-301 上连续做播放／暂停／切歌／上一首／拖动进度，确认「慢半拍」是否消失；服务侧读数是 54~452 ms，手感是否可接受只能由人判断。
2. **文件夹与子文件夹点击的手感复验**：服务侧已证伪（≤66 ms），剩余嫌疑是前端渲染整页曲目（封面批量落图）与滚动时的重复请求；需在浏览器 devtools 里取「点击→可见」的墙钟时间，若仍慢则要区分 paint 与 network。
3. **残余 300~452 ms 的归属**：设备本地直连 MPD 的 greeting／`status`／`playlistinfo` 均为 0.1 ms，故这段开销在自家暖路径（bind 探针＋握手＋`ensure_config()`＋lease＋idle/monitor 拉起）；需要真机火焰图定位到具体函数后才能决定是否把归属判定从热路径移开，离线测试无法给出该分布。
4. **DAC 拔插与换口分支**：`_ensure_bindable_port()` 的「端口被占→换随机口」路径在本机仍是「56660 可绑⇒不迁移」；需要在真机上人为占用 56660 走一次迁移，并确认迁移后播放、设置页持久化、以及卸载重装（Web UI 路径）后仍能找到新口。
5. **安装链路的现场恢复复演**：本轮出现过一次「wizard env 文件写成字面 `\n` → 平台已 uninstall 但未 install」的现场，应用进入未安装态；需要在真机复演一次该故障的恢复步骤（正确 env → `install-local -d -e`），并确认 `@appconf/fnaudio/mpd/database`  durable 索引在此过程中未被清空（本轮实测升级后仍可播、库计数正常）。

> 证据口径：本节每一条都以真机读数入账，且必须第二遍独立复测一致才写结论；拿不到读数一律按「不可取证」结案，不在 `TODO.md` 新立代码待办。设备凭据不入库，SSH 与 Web 登录材料只走现场注入。

## 第十三节 · R198 登记的真机专项（不是代码待办，不计入终止分母）

R198 把「点击文件夹分类与子文件夹反应慢半拍」的三条前端拥塞（导航点击被加载期闸门吞掉、上一页封面队列占住连接、后台轮询与导航抢同 6 条 HTTP/1.1 连接）在 0.2.45 里修掉，并用仓库外副本变异 V1～V8 与 90 套 JS 控制组守住；以下五件事只能在真机上收口。

1. **浏览器端「点击→可见」墙钟复验（负责人主观验收口径）**：本机没有 playwright，无法用脚本驱动真机浏览器点击。请在 198.51.100.24:5666 的 fnAudio 页面里连点文件夹分类、子文件夹分页、分组返回，确认是否还需要「等半拍」；若仍慢，请在 devtools 的 Network 里给出一次点击之后 2 秒内的请求清单与各导航请求（roots／folders／library／groups）的开始时间，用来区分是网关排队、渲染提交还是残余轮询。
2. **70 ms/请求这条地板的归属**：本轮实测 8 次串行 roots 564 ms、index.html 68 ms、12 并发 1124 ms，而设备本地直连 127.0.0.1:53199 六并发只有 7 ms，差值定性为 fnOS 网关每请求新建 CGI 进程的开销。要消掉这条地板只能走统一网关（gatewayPrefix／gatewaySocket 常驻）迁移，属于产品级改动，必须先真机验证常驻通道可用再动代码。
3. **网关条件请求是否可达**：src/app/ui/cgi_proxy.py 的上行头白名单只有 CONTENT_TYPE／Range／Accept／X-Forwarded-*，不含 If-None-Match／If-Modified-Since；页面加载实测 786 次静态 GET、60 个唯一 URL、11 次加载、0 个 304。需要真机确认 fnOS 网关在 CGI 形态下能否回 Status: 304，能则补转发、不能则把静态资源策略改成一次加载长期复用。
4. **封面 444 次 404／382 次重复的家族定位**：serve_cover()（src/app/server/server.py）只在 find_library_item() 解析不到时 404，cover_load_scheduler.js 终态失败不置负标记，所以根因家族尚未定位（是 URL 族、路径编码还是库重建期间的时序）。本轮明确不做负缓存，需真机按 URL 族取样后再定。
5. **0.2.45 的升级后功能回归**：本轮 install-local 升级后音乐库自动进入重建（/api/health 的 library.scanning 转真），需要在真机确认重建完成后播放、USB DAC（TEAC UD-301）、DLNA 投送与设置页持久化仍正常，并复核 MPD durable 索引未被清空。

> 证据口径：本节每一条都以真机读数入账，且必须第二遍独立复测一致才写结论；拿不到读数一律按「不可取证」结案，不在 TODO.md 新立代码待办。设备凭据不入库，SSH 与 Web 登录材料只走现场注入。

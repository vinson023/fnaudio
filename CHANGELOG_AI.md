# fnAudio AI 修改记录
- 2026-09-21 — R133 取证与实现（response_json_loader text() 分支字节预算：净关闭 1 条代码待办、新立 0 条）：接管后先从磁盘复算而非引用旧正文——HEAD `9c2e994`（父 `e6bca79`）、分支 `main`、无 remote、`.git` 无 MERGE_HEAD/rebase-merge/rebase-apply/CHERRY_PICK_HEAD/BISECT_LOG/REVERT_HEAD/sequencer 残留、暂存空；TODO 内容行 2220、0 CRLF、尾部 4 LF、开放 69＝代码 11＋设备/外部 44＋需决策 1＋台账 13；SOURCE_MANIFEST 707 条。选定既有可离线代码项 L162：源码取证确认 `src/app/ui/app.js` 的 `nativeHttpResponse()` 只暴露 ok/status/statusText/url/headers/text()/json()，无 body/arrayBuffer ⇒ text() 分支是每条原生桥响应的必经测量路径而非冷门回退（`response_json_loader.js` L191-207）。旧码两处缺陷：①L204 `typeof TextEncoder === "function"` 门令无 TextEncoder 主机完全跳过字节测量（预算空洞）；②`new TextEncoder().encode(text).byteLength` 为测量额外分配整份 UTF-8 副本（≈一倍体积）。
- 2026-09-21 — R133 测试与仓库外变异矩阵：新增无分配、可早退、与 TextEncoder 非 fatal 逐字节等价的 `utf8ByteLengthBounded`（孤立高/低代理各计 3、代理对计 4），text() 分支改用它并保留 `text.length * 3 > maximum` 上界短路（因 UTF-8 每 code unit ≥1 字节 ⇒ realBytes ≥ text.length，故旧 `text.length > maximum` 硬短路与真 TextEncoder 的 oracle 分类一致）。判别测试＝在 `test_ui_response_json_loader.js` 用真 TextEncoder 作 oracle 跑 maxBytes 1..20 × 代理字母表 8 元两两组合 × 有/无编码器双 loader，逐格断言 oversize 分类与 oracle 相等（无编码器主机也能测得＝预算空洞闭合，旧码在此必失败），加计数 stub 断言带内 `counted.calls()===0`、成对/孤立代理边界各测 n-1 oversize 与 n 非 oversize、两条源码级正则守卫；并修正旧 measured 段把「带内调用一次 TextEncoder」当测量证据的两条代理断言（`beforeMeasured+1`/`+3`→`beforeMeasured`）。仓库外 `clone --no-hardlinks` 副本：控制组全量 Python 2483 OK、全量 Node 74/74 先绿；变异 M1 还原 TextEncoder 门、M2 代理对计 3、M3 孤立高代理计 4、M4 早退 `>`→`>=`，四条分别被「带内零再分配断言／oracle 环／oracle 环／精确预算仍解析」击杀，4/4 全灭；收口复跑全量 Node 0 失败后删副本。
- 2026-09-21 — R133 收口／终跑／清单（一笔提交）：全量离线门禁终跑 `artifacts/offline-20260921-round206.log` 退出码 0，`Ran 2483 tests`／`OK (skipped=2)`／0 条 `FAILED`，JS 侧含 `passed` 的结果行 73（`src/tests/` 下 `test_*.js` 实为 74 个文件，两口径分开标注）；该 log mtime 晚于本轮全部代码与文档编辑。`SOURCE_MANIFEST.sha256` 以 Windows PowerShell 5.1 幂等复跑得 707 条、0 重复、逐文件 sha 与盘上一致，相对上一提交仅 `response_json_loader.js` 与 `test_ui_response_json_loader.js` 两行哈希变动。关闭 L162 后按行首 `- [ ]` 复扫开放项 68，按节边界分桶＝代码 10（L47/48/98/112/114/121/128/149/159/803）＋设备／外部 44（L820..L1875）＋需产品决策 1（L1887）＋台账 13（L2080..L2162），与本轮开头记录自洽；本轮净关闭 1 条既有代码待办（代码 11→10）、新立 0 条，满足「每轮净关闭≥1、新立≤关闭」反增长约束。设备段本轮未改；`tools/blutter`／`_external`／`artifacts/0.1.174/*` 等桶归属与移出裁定维持先前处置，本轮不动。%TEMP% 校验器实跑三份根文档最新在前格式与 R133 唯一性、四桶数学自洽后删除；提交前 `git status` 仅这六个被跟踪文件为工作树改动，逐文件显式 pathspec 提交、未用 `-A`、未 `git add` 其它、未改 `.gitignore`、未 push。
- 2026-09-21 — R132 取证轮（净关闭 0 条、新立 0 条，放弃代码项按条款如实记录）：接管后第一步是从磁盘复算而不是引用旧正文 —— HEAD `e6bca79`、分支 `main`、无 remote、`.git` 下无 `MERGE_HEAD`/`rebase-merge`/`rebase-apply`/`CHERRY_PICK_HEAD`、跟踪区干净；`TODO.md` 内容行 2,219／尾 4 LF／0 CR；开放条目按行首 `- [ ]` 计 69，按节边界分桶得 **代码 11（L45/46/96/110/112/119/126/147/157/161/801）＋设备/外部 44（L816..L1874）＋需决策 1（L1885）＋台账 13（L2078..L2160）**；设备段与 HEAD 逐字一致（53,981 字符）；清单 707 条、0 重复。上一轮 R131 的三份根文档 L2 记录经实读确认存在（非幻影轮次），其终跑 `artifacts/offline-20260921-round203.log` 复核为 `Ran 2483 tests in 111.595s`／`OK (skipped=2)`／0 条 `FAILED`／含 passed 的 JS 结果行 73。
- 2026-09-21 — R132 台账 13 条分类定案（回答「155 与 69 为什么不可比」）：逐条读全文后，12 条属 2026-09-01~09-06 历史节的「持续推进／持续观测」伞形条目（L2086 首屏离线回归、L2105 provider 可观测性、L2108 服务端上限与拆分、L2113/L2119/L2133/L2146/L2151 首屏闪烁与 WebView 观测、L2114/L2134/L2152 真实网络观测、L2160 首屏指标量化），其文本自身就写着「不能以离线门禁替代」，按定义不可被关闭也不应被删除；第 13 条 L2078「若要实现飞牛 APP 内原生同等能力：取得飞牛 APP 官方 Web/FPK 播放桥接…」内容是外部材料/设备项，但位置在「持续目标追加」历史节而非 P0 设备段——是否移动属桶归属裁定，本轮不动（先例 R121 与 L801）。旧正文 155＝64＋82＋9 是更早结构的快照，其中「82 条设备项」与今天的 44 条设备段口径不同、且当年没有单列这 13 条台账项，**两组数字并存不合并、不覆盖**。
- 2026-09-21 — R132 实测与收口（零源码改动轮）：唯一新增的可离线事实是原 L119（快照复用阈值）的前提被实测推翻——直接在 node 里加载真策略码跑默认五列视图，正常行签名 151 字符，单字段触发超长整页回退所需 title 1,917／artist 953／album 953／cover 1,929 字符，而服务端 `MAX_TAG_TEXT = 4096` 允许更长标签，故「正常数据离 2048 还有一倍余量」不成立；同时确认 `app.js:5385` 的复用判定是页级布尔，条目原案「逐行比较」并不能减少重绘。事实以〔R132 实测…〕后缀并入该条，**不新立项、不改代码、不声称关闭**。收口：本轮无源文件变更 ⇒ 不做仓库外变异证明也不声称做过；文档守卫三套件（`tests.test_change_record`＋`test_source_hygiene`＋`test_scope_entry_subsumption`）实跑通过；清单按 Windows PowerShell 5.1 幂等复跑并逐文件复核条数不变；全量离线门禁终跑 `artifacts/offline-20260921-round205.log`（`Ran 2483 tests`／`OK (skipped=2)`／0 条 `FAILED`／含 `passed` 的 JS 结果行 73；`src/tests/` 下 `test_*.js` 实为 74 个文件，两口径分开标注），其 mtime 晚于本轮全部文档编辑；与上一轮终跑 `round203.log` 做 `difflib` 全量逐行比对，全文只差 2 行——1 行是 Python 耗时数字（测试数 2483 未变），1 行是 `git diff --check` 对 `SOURCE_MANIFEST.sha256` 的 CRLF 警告（本轮清单逐字节未变 ⇒ 该警告不再出现），字节差 116 恰等于该行含 CRLF 的长度 ⇒ 差异全部可由「本轮零源码改动、不改清单」解释，不存在测试减少或断言放宽。另补记：上文 151／953／953／1,158 是**夹具相关**字符数，接管方按 `app.js:2946` 的真实调用点形状独立复算得 173／940／943／1,878／1,137，同数量级、结论不变；三份根文档最新在前插入，%TEMP% 校验器实跑格式与唯一性后删除；一笔逐文件显式 pathspec 提交。
- 2026-09-21 — R131 取证与实现（热页覆盖层：净关闭 1 条代码待办、新立 0 条）：接管后先取证再动手 —— HEAD `7595cbb`（父 `2fb3d7c`）、分支 `main`、无 remote、无 MERGE_HEAD/rebase-merge/rebase-apply/CHERRY_PICK_HEAD/BISECT_LOG 残留，脏区只有 `src/app/server/metadata_service.py`、`src/tests/test_metadata_service.py`、`SOURCE_MANIFEST.sha256` 三个跟踪文件（清单 diff 恰为 2 行＝那两个源文件的哈希），`C:\path\to\fnAudio\tree` 不存在。取证结论是 TODO 原 L122 的前提不成立：热页覆盖层的重复劳动不在拷贝上 —— `enrich_track_page` 里 ① 行身份 `_page_track_id` 每行算 3 次，② 每次缓存命中都把存着的 `fields_json` 重新 `project_match_fields` 解码＋逐字段重算边界，③ 每行重跑一次 `_provider_text(...).strip().lower()` 折叠 artwork id。实现＝三件事全部挪到已经为该行付过钱的冷读上：新增 `_overlay_artwork_id()`（`metadata_service.py:1895`，边界与折叠一处定义），冷读时 overlay 直接存成品（`:4408-4411` 写 `artwork_id` 与 `projected`），命中路径退化为 `row.get("projected")`（`:4423`）与 `row.get("artwork_id")`（`:4440`），身份归一化改成一趟 `track_ids`（`:4351`）并让 `item_by_id`（`:4358`）与合并循环（`:4426-4427`）复用同一趟结果；`_track_page_cache_get`/`_put` 仍双向 `copy.deepcopy`（`:2020`、`:2037`），故缓存内层仍由结构保证只读。
- 2026-09-21 — R131 测试、等价性对拍与仓库外变异矩阵：判别测试＝`src/tests/test_metadata_service.py` 新增 fixture `_seed_page_overlay_fixture`（L2271）与三条用例（L2308 计数式断言冷读投影次数恰等于行数、热页两次命中零新增、三次服务结果全等；L2341 断言缓存条目键集合恰为 artwork_id 与 projected 且不再携带 `fields_json`；L2353 断言每页 `normalize_track_id` 调用次数恰等于行数）。仓库内复跑：`tests.test_metadata_service` Ran 227 OK、三条新用例点名 Ran 3 OK。等价性对拍改用固定根 `%TEMP%\r131_fixroot`（此前 `r131_sha.py` 用 `tempfile.mkdtemp()` 的随机根，两棵树各自的库与路径配不平），HEAD 副本由 `git archive HEAD src` 解到 `%TEMP%\r131_oldroot`：两侧响应均 68,706 字节、sha256 同为 `05bf20273094611e3679545eafe661cc4e07f75a6da5034efa23df2f107f1954`、逐字节相同。热页净耗时（400 次/轮×5 轮取最优、扣 `fresh_page()` 基线）：1.524 ms → 0.722 ms＝−0.80 ms／−52.6%（另一副本 1.571→0.737＝−53%；两组并列不合并）。变异矩阵跑在仓库外副本 `%TEMP%\r131c2\src`：控制组 rc=0、ran=3、零失败先绿，随后 6 个变异体 6/6 KILLED、结束 `restored=True`；实测归因 —— M1 回退成缓存存 `fields_json` ＋ 命中重解 → 计数 6≠2 且键集合断言双杀，M2 恢复 `item_by_id` 现算 → 6≠2（仅身份用例捕获），M3 存了投影仍每次重解 → 4≠2（仅计数用例捕获），M4 完全不折叠／M5 折叠但不 casefold → 大写串与小写串不等，M6 同时保留 `fields_json` → 键集合断言失败。残余量另测一组：`metadata_service.copy.deepcopy` 换成 identity 后 0.701→0.444 ms（≈0.26 ms／剩余约 40%；另一副本 0.740→0.437＝0.303 ms／41%），本轮不采纳该改法，理由与结论一并写进 TODO 原 L122 的关闭记录。
- 2026-09-21 — R131 收口、清单与两笔提交：三份根文档按最新在前插入（CHANGELOG 本三条、TODO 一条并勾掉原 L122、PROJECT_CONTEXT 两条教训），三者最新日期一致为 2026-09-21，插入前用 `assert count(old)==1` 定锚、写回统一 `io.open(..., "w", encoding="utf-8", newline="")`、断言 0 CRLF 并保留各自尾部空行（TODO 4／CHANGELOG 9／CONTEXT 8）。`SOURCE_MANIFEST.sha256` 只覆盖 `src/`＋`android-client/`，三份 .md 不在作用域内 ⇒ 文档编辑不改清单；本轮无新增源文件 ⇒ 仍 707 条，幂等复跑 `tools/update_source_manifest.ps1` 后逐文件复算 707/707 sha MATCH、0 missing、0 重复条目。离线门禁（Windows PowerShell 5.1、`tools\test_offline.ps1`）：文档编辑前的取数轮为 `artifacts/offline-20260921-round201.log`（422,322 B／2,631 行／mtime 2026-09-21 05:21:52）＝`Ran 2483 tests in 111.402s`、`OK (skipped=2)`、含 passed 的 JS 结果行 73（JS 文件实为 74，两口径分别标注）、三条新用例位于 L1786/L1790/L1794；文档与清单全部写完之后复核一轮 `artifacts/offline-20260921-round202.log`（422,322 B／2,631 行／mtime 2026-09-21 05:44:26，晚于本轮全部文档与清单编辑）＝`Ran 2483 tests in 111.989s`、`OK (skipped=2)`、0 条 FAILED、含 passed 的 JS 结果行仍是 73、三条新用例同样位于 L1786/L1790/L1794；两轮日志都不打印退出码，退出码由外层命令捕获，本轮真正的终跑是写完本条之后的 `artifacts/offline-20260921-round203.log`，其预测值为 `Ran 2483 tests`、`OK (skipped=2)`、0 条 FAILED、含 passed 的 JS 结果行 73、三条新用例位于 L1786/L1790/L1794、外层捕获 `GATE_EXIT=0` —— 跑完逐字复核，若任一项不符则本轮不算收口并改正记录（round202 与 round203 之间的唯一差异是本条收口句自身，三份 .md 不在清单作用域内、也不被任何测试读取内容，只有格式与唯一性守卫会读它们）。提交两笔、逐文件显式 pathspec、不 push、不改 `.gitignore`：① `perf(server): project track overlays once and cache the result` ＝ `src/app/server/metadata_service.py` ＋ `src/tests/test_metadata_service.py`；② `chore: record R131 closure` ＝ `TODO.md` ＋ `CHANGELOG_AI.md` ＋ `PROJECT_CONTEXT.md` ＋ `SOURCE_MANIFEST.sha256`。%TEMP% 本轮工作脚本与副本收口时清理；`artifacts/`、`music/`、`_external/`、`references/`、`tools/` 与 R1xx 审查对照文件保持未跟踪、不入库。
- 2026-09-21 — R130 取证与实现（账本并账：净关闭 1 条代码待办，新立 0 条）：接管取证先于一切动作 —— `git status` 脏区 13 个跟踪文件（其中 8 个是纯行尾漂移——盘上字节等于 HEAD blob、`git diff` 内容为空，真正有内容差异的只有 5 个）、无 merge/rebase/cherry-pick 残留、`git ls-files -u` 为空、HEAD=2fb3d7c。四桶按磁盘复算（节标题定界：代码 1..813／设备 814..1872／决策 1873..1888／台账 1889+）：开放 70 ＝ 代码 12 ＋ 设备/外部 44 ＋ 需决策 1（L1883）＋ 台账 13，已关闭行首口径 1475／含缩进 1476（相对插入前各 +2：本条记录自身是一行 `- [x]`，加上 L551 翻勾）。L551 与 L94 是同一份欠读范围的两份账：R59 立 L94 的原文写明它「替换 2026-09-17 那条只列文件名的范围条目」，而被替换条目从未勾选 ⇒ 代码桶重复计数 1 条。处理方式严格走「并入既有条目」而非新立：逐项比对 L551 原文点名的 16 个面，12 面 L94 逐字在案、1 面 `PlaybackService` 在设备段在案，把 L551 独占的 3 个 Android 面（`RemotePlaybackPlayer` 370 行／`AuthenticatedBitmapLoader` 410 行／`FnConnectRelayConfigClient` 258 行，行数取「按 LF 切分且末换行不另计」的仓库口径实测并写入 L94 批注）与它独占的三个角度（并发写／剩余循环／常驻循环）、「不得以离线门禁宣称全仓库无问题」和 Gradle loopback/Unix socket 告诫全部折进 L94，确认 L551 不再持有任何独有内容之后才勾选。设备段 1059 行与 HEAD 逐字一致，本轮未触碰。
- 2026-09-21 — R130 当轮修掉的真实缺陷（工作树 CRLF 让发布清单不可复现）：`tools/update_source_manifest.ps1` 哈希的是**工作树字节**，作用域为 `src/` ＋ `android-client/`；`.gitattributes` 声明 `* text=auto eol=lf`，而 `core.autocrlf=true` 来自 **system 级**配置（repo 与 global 均未设），因此一次干净检出必然得到 LF 工作树。取证发现 8 个清单作用域内的文件在盘上是 CRLF —— `android-client/README.md`、`android-client/app/src/main/java/go/{Seq,Universe,error}.java`、`src/app/ui/index.html`、`src/tests/{dom.txt,test_ui_asset_gate.py,test_ui_lyrics_priority.js}`；对每个文件先证明「工作树按 CRLF→LF 归一后逐字节等于 HEAD blob」（**纯行尾漂移，零内容差**）再落盘归一。要点是这类漂移 `git diff` 看不见（读盘时行尾被归一化抹平），只有哈希清单会记录下一个任何检出都复现不出的摘要。归一后三方一致：仓库清单 == 提交 blob == 工作树（8/8 MATCH），并在仓库外副本用同一 WinPS 5.1 工具重新生成清单，与仓库清单**逐字节相同**（707 条，SHA256 一致）。另有 14 个 `artifacts/*/PACKAGE_CONTENTS.txt|SHA256SUMS` 也是 CRLF，但不在清单作用域内、不影响复现性，本轮不动；`SOURCE_MANIFEST.sha256` 自身由 PowerShell 5.1 `Set-Content` 写成 CRLF，提交时由 git 归一，不属缺陷。
- 2026-09-21 — R130 测试、仓库外变异矩阵与收口：新增 `src/tests/test_scope_entry_subsumption.py`（5 项）与 `src/tests/test_source_manifest.py` 两条新守卫 —— ① `test_the_guard_walks_the_same_scope_as_the_manifest_tool`：守卫的作用域常量是清单工具那份的副本，故从 `.ps1` 反解 `Get-ChildItem -LiteralPath` 行与三条排除声明做双向比对，防两份清单各自漂移；② `test_manifest_scoped_text_files_keep_unix_line_endings`：按同一作用域走查，NUL 判二进制、CR 判违规，并带 `scanned > 600` 反空扫哨兵。仓库外副本（`git clone --no-hardlinks` 后 `git remote remove origin`）控制组**先绿**：Python `Ran 2480 tests`／`OK (skipped=3)`（多出的 1 条 skip 是副本缺未跟踪的 `artifacts/RELEASE_INDEX.json`，属既有预期差异），JS 73 项 checks passed，门禁 exit=0。变异矩阵 11 条**全灭、0 存活**，每条打印指名杀手：V1 重开被替代条目、V2 从活账本抹掉一个 Android 面、V3 删除被替代条目整行、V4 把登记行数 370 改成 371、V5 删除账本引用的退役守卫文件、V6 把唯一活账本也改成关闭态、V7 条目整体丢掉一个面（FACE_COUNT 16→15）、V8 把一个面挪进批注区（证明「原文/批注分读」不是装饰）、E1 `index.html` 写回 CRLF（行尾守卫与清单陈旧守卫同时杀）、E2 守卫少扫一个作用域根、E3 守卫作用域根写错导致扫空（哨兵生效）。**诚实边界**：本轮属账本并账＋清单复现性，变异只针对本轮新增守卫自身的判别力，**不主张业务代码级变异证明**；每条变异在副本内施加、当场还原并复核哈希。
- 2026-09-21 — R129 真机取证（测试机 198.51.100.24，只读；**SSH 端口更正为 22，21 上是 FTP**）：为本轮两条「从未量过」的门各取一次实据并追加在条目尾部。L42（`transcode` 清扫落在真实请求上的 SMB 放大）：`findmnt` 全表只有 `ext4 … /vol1`，无 cifs/smb 挂载，`/vol1/1000/music` 落在本地 ext4 卷；封面缓存 `/vol1/@appconf/fnaudio/transcode/covers` 实测 11 个文件 / 58,005 字节，`os.walk`＋逐文件 `os.stat` 三连 0.30 / 0.23 / 0.19 ms。L43（`covers/` 未封顶条目数）：`library.sqlite3` 规模 tracks 6 / albums 4 / artists 4 / covers 6 / cue_tracks 0 / folders 0，四张 metadata 明细表全 0 行，`config.json` 的 `metadata_enabled=false`、`metadata_cache_max_bytes=536870912`。两条结论都是「样本机不具备该门槛要求的载体」，故**保持开启、不改代码、不新立项**；L1882 复测与 R121 逐值一致（tracks 6 / cue_tracks 0），无标签样本 `C:\path\to\fnAudio\music\伍佰 - 泪桥.flac`（26,325,514 B）给不出占比，维持不选边。
- 2026-09-21 — R129 记录修正与取证纪律（本轮净关闭 0 条，属如实放弃轮）：① 破案「−1 计数偏差」——TODO.md 里 `startswith("- [x]")`＝1472 与 `"- [x]" in line`＝1473 的差是 **L679 一条前导 1 空格的已关闭项**（全树唯一，无散文误命中），历史各修订恒差 1，根文档既有 1470→1472 记录用行首口径且**没有错**；本轮起统一行首口径并同时标注两口径，不改写历史数字。② 登记 L93 的 R59 欠读清单已失真（`fnos_api.py` R118 退役、`alsa_player.py` R119 入 `src/tests/unwired/`、九面按统一内容行口径合计 6,655 行、六面与登记值不符，三面逐字相符（renderer 442／state_projection 231／index.html 184）），明确声明不据此关闭。③ 修复上一轮编辑脚本给 TODO.md 尾部误加的 3 个 LF（内容行 2219→2216、尾 7→4 LF），并复核设备段 L813..L1871 共 1059 行与 972f733 **逐字 identical**。③′ 本轮记录自身的口径自纠：首次统计九面行数时用了 `len(text.split(chr(10)))`（未扣尾部空串），每面各虚高 1 行、合计误记 6,664，并把与登记值逐字相同的 `dlna/renderer.py` 442、`state_projection.py` 231、`index.html` 184 三面误判为「不符」，因而写下「九面全部不符」；改用与本文件同一口径的内容行复算后为 6,655 行、六面不符三面相符，四处同源表述已同步更正。④ 本轮未改生产代码 ⇒ 不开仓库外副本、不做变异矩阵（对文档轮声称变异证明即伪造证据），控制组改为完整离线门禁实跑＋清单 706 条逐文件 sha 复算（missing 0 / mismatch 0 / 重复 0）：终跑 `artifacts/offline-20260921-round199.log`＝`Ran 2473 tests`／`OK (skipped=2)`／JS 73 条通过行／退出码 0，与 round195～198 四次同配置复跑数值一致；日志末行的 `GATE_DONE exit=0` 由门禁外层命令追加，不是 `tools/test_offline.ps1` 自身的输出；根级 .md 不在清单内，故本轮文档编辑不改清单内容。⑤ 破案「清单看似非幂等」：首刷报出 31 行变更，逐行比对是**同一批 706 条目互相换位**（`ic_launcher.xml`↔`ic_launcher_foreground.xml`、`diagnostics.py`↔`diagnostics_*.py`、`dlna/`↔`dlna_snapshot.py`），根因是 `Sort-Object FullName` 在 Windows PowerShell 5.1（清单哈希 `104748aa…`）与 pwsh 7.6（`F7D50309…`）下对下划线与点号的平局权重不同；改用 5.1 重跑后清单与 HEAD 逐字相同、`git status` 归净。⇒ 清单复算必须比条目集合与哈希内容、不比行号顺序，生成端固定用 Windows PowerShell 5.1。
- 2026-09-21 — R128 实现（净关闭一条代码待办：原 L161「池化冷页剩余固定开销要先拆开量，权限刷新不能为了省时间被摘掉」，含 R121 并入的池化计时守卫事故）：`src/app/server/file_permissions.py` 的 `secure_sqlite_files()` 循环体由 `secure_file` 换成 `secure_file_on_drift`，docstring 写明「频率是安全不变量、变便宜的只是探测」；`src/app/server/library.py` 读入口 `library_db_connect()` 的目录加固换成 `secure_directory_on_drift(config["cache_dir"])`（:2098，附 4 行注释说明 fallback），写路径 `library_db_writer`（:2454）与 `save_library_cache`（:3004）保持全量 `secure_directory`，五处 `secure_sqlite_files`（:2075/:2079/:2124/:2160/:2479）一处未减。计数取证：一次池化读的权限探测 16 次系统调用 → 7 次（目录 4→1、sidecar 每趟 6→3、每读两趟），POSIX 稳态另省 7 次无条件 chmod；配对计时 ABBA、N=301、预热 200 轮，中位 0.0818 ms → 0.0383 ms、301/301 轮新路径全胜。`tools/benchmark_large_library.py` first-screen 段（:702-758）改用新纯函数 `paired_ab_samples()`（:124）/`median_duration()`（:156）/`pooled_reuse_guard()`（:164），判据从计时换成窗口内 reuses/creations 结构计数，「池化必须更快」的 `RuntimeError` 删除而非注释，速度差降级为 `pooled_faster_pairs`；嵌套死码 `median_sample` 删除（1 处定义 0 处调用）。设备段一行未改。
- 2026-09-21 — R128 测试与仓库外变异矩阵（本轮的关键纪律是「省时间的改动必须先证明没少查一次，判别层要同时钉频率与形状」）：`src/tests/test_file_permissions.py` 新增 `test_sqlite_sidecars_are_probed_once_and_chmodded_only_on_drift`（:171，5 subTest：三件全私有／`-wal` 漂移／两件 sidecar 缺失／`-shm` 是符号链接／`-wal` 是目录；钉 lstat 恰 3 次且顺序＝三后缀 abspath、`secure_file` 一调即 AssertionError、chmod 只落漂移项且第二参 `PRIVATE_FILE_MODE`）；`src/tests/test_library_sqlite.py` 新增 `test_a_borrowed_handle_is_still_hardened_on_both_ends`（:216，池化第二次读刷新恰两次、参数都是 `library_db_path(config)`、先断 `reuses + 1` 防空转）与 `test_only_the_read_entry_uses_the_cheap_directory_probe`（:235，读＝drift 1/full 0，writer＝full 1/drift 0，源码级 1 处与 2 处计数），另为 7 处既有打桩缝隙补 `secure_directory_on_drift`；`src/tests/test_large_library_benchmark.py` 新增 `FirstScreenPairedSamplingTests`（:241）8 条（ABBA 精确顺序与分臂归属、三种非法输入 ValueError、中位数含偶数上中位、窗口差判据、三种失败窗口、缺键按 0、pooled 全输只报告不抛、源码接线含禁止 `not faster than reopening` 与 `median_sample`），并把 `first_screen_connection` 段的两条计时断言换成结构与范围断言（保留 samples/reuses/creations/idle_after_drain 与重减精度）。仓库内定向复跑 `tests.test_file_permissions tests.test_library_sqlite tests.test_library_connection_pool tests.test_metadata_service tests.test_state_store tests.test_observability tests.test_large_library_benchmark` ⇒ `Ran 487 OK`。仓库外副本 `E:\temp\fnaudio-r128copy`（clone HEAD `0b6be71`、`git remote remove origin`、6 个改动文件按工作树拷入并逐文件 sha 全等、副本内先刷 706 条清单再开跑）：控制组 Python 全量 `Ran 2473 OK (skipped=3)`、Node 74 文件 0 失败；变异 V1~V8 全灭（V1 退回 `secure_file`／V2 摘入口刷新／V3 摘 epilogue 刷新／V4 写路径也换 drift／V5 去掉 ABBA 轮换／V6 摘 guard 的 raise／V7 重新加回池化计时 raise／V8 guard 改读绝对计数），如实登记 V7 的 kill 者是源码接线断言而非同名单臂纯函数测（后者不执行段体）；每条变异还原后逐字节 sha 复验等于 pristine，收口当场重跑全量再次 `Ran 2473 OK (skipped=3)` ＋ Node 74/0。 交付前逐 hunk 自查发现该类首版被接在上一方法体之后（0 空行），并吃掉 `__main__` 前的两条空行之一，同轮补回后本文件 330→333 内容行、类在 :241，复跑 `Ran 10 OK`。
- 2026-09-21 — R128 收口、清单与提交：`TODO.md` 插入本轮记录前实测 2215 内容行、开放 72 ＝ 代码 14 ＋ 设备 44 ＋ 决策 1 ＋ 台账 13、已关闭 1470、0 个 CRLF，本轮关闭原 L161 ⇒ 净账开放 72→71、代码 14→13、已关闭 1470→1472（口径＝行首 `- [x]` 计数：本轮关闭 1 条＋本轮这条记录自身占 1 条，与 R127 的 1468→1470 同一算法），新立可离线代码项 0；设备段 1059 行区块与 `972f733` 逐字 identical。三份根文档均在 L2 插入本轮记录（TODO 1 条、CHANGELOG 3 条、PROJECT_CONTEXT 2 条），%TEMP% 校验器实跑「格式＋唯一性＋尾部空行数」后删除。`tools/update_source_manifest.ps1` 幂等复跑仍 706 条，706 条逐文件 sha 复算 0 处不符、0 条未列、0 条重复。完整离线门禁 `tools/test_offline.ps1` 终跑 `artifacts/offline-20260921-round195.log`：Python `Ran 2473 OK (skipped=2)`、Node 74 文件 0 失败、exit 0，日志写入时刻晚于本轮全部代码、文档与清单编辑（round194 是格式修正之前的终跑，`Ran 2473 OK (skipped=2)` 与 Node 计数与 round195 相同）；该轮终跑数字在收口时逐字复核（本机 round193 为 `Ran 2462 OK (skipped=2)`，本轮新增 11 条 ⇒ 2473）。提交两笔：实现+测试一笔（6 个文件逐文件 pathspec）、`chore: record R128 closure` 一笔（三份根文档 + `SOURCE_MANIFEST.sha256`）；未碰 `.gitignore`，`artifacts/`、`music/`、`_external/`、`references/`、`tools/` 取证物与本轮审核对照 md 一律不入库。 本条记录在 R128 交付前改写一次（`:239`→`:241`、终跑日志 round194→round195），起因是逐 hunk 审核查出上述格式回退；已落地的两笔提交保持不动、不改写历史，修正另起两笔：测试文件一笔 `style`，根文档与 `SOURCE_MANIFEST.sha256` 一笔 `chore: record the R128 review correction`。
- 2026-09-21 — R127 实现（净关闭一条代码待办：原 L103「50k 顶层目录时首屏剩余成本是 folders 覆盖索引 count」）：本轮的实际产出全部落在测试面，`src/app/server/library.py`（3122 内容行）与设备段一行未改。条目原结论是「不必把每个目录的子项数做成持久列或按目录计数缓存，因为 12.13→1.21 ms 的量级已经不再受目录宽度支配」，取证结果是这句话只在缓存命中路径成立：走真函数 `query_library_folders`、50k 个目录挂在同一个父目录下，未命中首页 9.2~11.5 ms（其中 `SELECT COUNT(*) FROM folders WHERE root=? AND parent=?` 占 4.39 ms）、深 offset 页 16.9 ms、同参热重复 0.26 ms 且不发任何语句；并取证到一个此前没记录的事实 —— folders 面没有 saved-count 摊销协议，`_save_library_meta_count`/`count_key` 那套只服务 groups（`library.py:1593-1610`），folder 页每次未命中都重算 count（`cache_values` `:1631`、`cached = cache_epoch.get("folders", ...)` `:1636`、`conditions`/`args` `:1640-1641`、`cache_epoch.put("folders", ...)` `:1727`、TTL `LIBRARY_QUERY_CACHE_TTL_SECONDS = 20.0` `:145`）。最终判定仍是**不改生产代码**，但换掉理由：持久列要额外承担写放大与第二套失效口径，而这笔成本只在未命中路径出现且只占其中一部分；让「可以不做」成立的前提是那层查询缓存，因此本轮把前提钉成结构断言，而不是把计时数字抄进注释 —— 计时阈值在本仓库不可用作守卫（共享机抖动大过要区分的一倍，见 L120 既有结论）。
- 2026-09-21 — R127 测试与仓库外变异矩阵（本轮的关键纪律是「关闭性能判定类条目要钉前提，不钉数字；单旋钮存活要如实保留」）：扩展 `src/tests/test_library_sqlite.py` 的 `test_unfiltered_folder_page_reads_an_indexed_page_plus_count`，新增 hunk 在 `:2686-2702` —— 对 trace 出的真实生产 count 语句逐条断言计划命中 `COVERING INDEX` 且索引名是 `idx_folders_root_parent`、detail 不含 `nocase`、禁 `TEMP B-TREE`（注释记录实测 0.55/4.39 ms 与删索引后的退化值 5.38/14.23 ms）；新增 `test_repeated_folder_page_is_served_without_rereading_the_directory`（`:2704-2768`，三个目录的小夹具 + `traced_connect`）钉住三条前提：同参热读 0 条语句（`:2750`）、换 offset 必须重读（`:2753`）、写库后必须重读（`:2766`）。仓库内 `python -B -m unittest tests.test_library_sqlite.LibrarySqliteTests -v` ⇒ `Ran 122 OK`。仓库外副本 `%TEMP%\fnaudio-r127-copy`（`git clone --no-hardlinks` ⇒ HEAD `972f733`、`git remote remove origin`、复制 `src/tests/test_library_sqlite.py` 与 `SOURCE_MANIFEST.sha256` 入位且逐文件 sha MATCH；副本内先刷一次清单再开跑，因为 clone 以 autocrlf 签出会让 src 内 38 个文件带 CRLF、不刷会假失败两条清单测试）：控制组 Python 全量 `Ran 2462 OK (skipped=3)`（比本机多的 1 条 skip 是 `test_offline_verification_script` 依赖未跟踪的 `artifacts/`）、Node 74 文件 0 失败。变异 8 条 V1~V8 ＝ **6 灭 2 存活**：V1 删 `idx_folders_root_parent` 建索引 → KILLED（杀手正是新断言 `:2696`）；V2 `cached = None` 永不读 folder 缓存 → KILLED `:2750`；V3 `cache_values` 去掉 `page.offset` → KILLED `:2753`（`['A','B'] != ['c']`）；V4 `return result` 永不写缓存 → KILLED `:2750`；V5 计数条件去掉 `f.root = ?`（连带 args）→ KILLED 但杀手是**既有**页面计划断言 `:2681`，记为 KILLED-OTHER，不宣称新断言被这条证明；V6 `invalidate_library_query_cache` 空转 → **SURVIVED**（写路径会改写库文件，库身份指纹仍会换 key）；V7 `self.identity = None` → **SURVIVED**（显式 invalidate 仍会在写路径清掉该库）；V8 ＝ V6＋V7 双旋钮同摘 → KILLED `:2766`（`3 != 4`），反证「写后必须重读」这段断言是活的，两个单旋钮存活的原因是那两处机制互为兜底，不是断言无效。另有一次三旋钮尝试（再去掉 `search_cache_token` 段）因锚点在文件内出现 2 次被 assert 拦下、**未落盘**，无坏锚点。每条变异写回后逐字节 sha 复验等于 pristine，基线与还原后均 rc=0。
- 2026-09-21 — R127 收口、清单与提交：`TODO.md` 插入本轮记录前实测 2214 内容行、开放 73 ＝ 代码 15 ＋ 设备 44 ＋ 决策 1 ＋ 台账 13、已关闭 1468；插入后 2215 内容行、开放 72 ＝ 代码 14 ＋ 设备 44 ＋ 决策 1 ＋ 台账 13、已关闭 1470、0 个 CRLF，设备段 44 条与 `git show HEAD:TODO.md` 逐字比对未改。四桶口径本轮磁盘复算一次：代码 15 ＝ 主表 13 条（L40/L41/L91/L103/L105/L107/L114/L118/L121/L142/L152/L156/L160）＋ L548 ＋ L796，关闭 L103 后剩 14；决策 1 ＝ L1880；台账 13 ＝ L2073 ＋ L2081-2155 的 12 条流水条目。历史计数快照 155=64+82+9、115=51+43+8+13、73=15+44+1+13、72=14+44+1+13 并存不合并，一律以磁盘实测为准。本轮如实登记一处**未关闭**：同轮尝试的 L114（过户标记复用阈值 `MAX_SIGNATURE_CHARS = 2048`）不成立 —— 它指定的修法「逐行比较、超长行单独判不等」在当前的整页布尔 API 下与现状行为等价，写不出判别性测试，保持开放、不为凑数硬关。`tools/update_source_manifest.ps1` 刷新 `SOURCE_MANIFEST.sha256` 为 706 条并逐文件抽查 MATCH（本轮无新增文件，变动条目是测试文件自身）；终跑 `tools/test_offline.ps1` 见 `artifacts/offline-20260921-round193.log`。两笔提交均逐文件显式 pathspec，未碰 `.gitignore`，未跟踪产物一律不入库。
- 2026-09-20 — R126 实现（净关闭一条代码待办：原 L176「设备是否支持源码 DSD」三态统一）：把「一个事实三种形状、未知口径相反」收敛成一套三态常量与唯一谓词。`src/app/server/dlna/profiles.py`（99 内容行／3865 字节）`:12-14` 新增 `DSD_CAPABILITY_SUPPORTED/UNSUPPORTED/UNKNOWN`，`:26-41` `_dsd_state_from()` 规定「键不存在＝unknown、键存在但值不是 True＝unsupported」，`:43-69` `dsd_capability_state(source)` 同时接受 device 与裸 protocol_info 并在`capabilities.protocol_info` 存在时以嵌套为准（扁平不再参与投票），`:71-79` `device_supports_native_dsd()` 改为委托谓词、只作显示面的保守布尔视图。`control_point.py`（699 行）`:14` 引入谓词、`:290-295` 与 `:317` 两条探测失败壳不再写 `supports_dsd` 键、`:320-321` `device_supports_dsd()` 委托、`:494-500` 发现成功路径的扁平字段改为「由同一谓词从探测记录派生的显示缓存」、`:502-505` 异常路径删掉 `supports_dsd = False`。`media_server.py`（231 行）`:10` 改 import、`:183-185` 推流门改为 `dsd_capability_state(device) == DSD_CAPABILITY_UNSUPPORTED`，拦截文案逐字不变。`playback_targets_presentation.py`（157 行）`:9`/`:141-143` 目标列表 `native_dsd` 走同一谓词。唯一行为变化是「探测失败空壳由误拦变放行」，未知／True／False／非布尔四类取值的放行与拦截结论与改前一致，属放宽误拦、不收窄能力语义；「哪些真实渲染器落 unknown」并入既有 P0 外部验收段，不新立项。
- 2026-09-20 — R126 测试与仓库外变异矩阵（本轮的关键纪律是「源级接线断言用按行白名单，不用整文件 substring 黑名单」）：新增 `src/tests/test_dlna_dsd_capability.py` 263 行／11427 字节／13 项，八行真值表对 state、push、display 三列同断言，`_push()` 注入 `control_url` 真实调用 `soap_push()`，源级守卫 `test_control_point_only_writes_the_field_never_reads_it_back` 只放行「唯一派生写＋唯一探测记录＋`def device_supports_dsd`＋注释行」，`test_only_the_predicate_reads_the_capability_key` 要求 `media_server.py` 与`playback_targets_presentation.py` 全文 0 次出现该键名。仓库内 `test_dlna*.py` 224 项 OK、全量 `Ran 2461` 仅剩两条清单滞后失败、JS 74 文件 0 失败。仓库外副本 `%TEMP%\fnaudio-r126-copy`（clone 后移除 origin，HEAD `a295d08`，五文件与在盘逐文件 sha 全等，副本清单先刷 706）控制组 `Ran 2461 OK (skipped=3)` ＋ JS 74 全绿 ＋ 变异子集基线 192 OK；V1～V11 **全灭、0 存活、0 坏锚点**（退回布尔强制／两条失败壳恢复写 False／门退回真值判断／扁平压过嵌套／目标列表读裸字段／异常路径写 False／拆委托／静默当拒绝／真值替代三态比较／派生写回退成布尔），逐条打印指名杀手测试；副本还原后当场复跑 192 绿再删除。另登记一处事实纠正：R125 记录把副本目录写成 `fnaudio-r126-copy`（R124 为 `fnaudio-r124-copy`），应为 `fnaudio-r125-copy`，属计数器提前一位的笔误，按「历史条目不回填」规则不改已入库行。
- 2026-09-20 — R126 收口、清单与提交：`TODO.md` 插入本轮记录前实测 2213 内容行、开放 74 ＝ 代码 16 ＋ 设备 44 ＋ 决策 1 ＋ 台账 13、已关闭 1466；插入后 2214 内容行、开放 73 ＝ 代码 15 ＋ 设备 44 ＋ 决策 1 ＋ 台账 13、已关闭 1468、0 个 CRLF，设备段 44 条与 `git show HEAD:TODO.md` 逐字比对未改。四桶规则本轮再次磁盘复算：台账 13 为 L2072 之后的流水条目，决策 1 为 L1879（R73 `allow_disk=False` 的取舍，仍等含无标签音频的样本），代码 16 关闭 L176 后剩 15。历史计数快照 155=64+82+9、115=51+43+8+13、74=16+44+1+13、73=15+44+1+13 并存不合并，一律以磁盘实测为准。`tools/update_source_manifest.ps1` 刷新 `SOURCE_MANIFEST.sha256` 为 706 条并逐文件抽查 MATCH（新条目 `src/tests/test_dlna_dsd_capability.py`）；终跑 `tools/test_offline.ps1` 见 `artifacts/offline-20260920-round192.log`。两笔提交均逐文件显式 pathspec，未碰 `.gitignore`，未跟踪产物一律不入库。
- 2026-09-20 — R125 实现（净关闭两条代码待办：原 L69 投送并发按裁定 D、原 L150 NULL 标签组游标残余按裁定 A＋C）：`src/app/ui/app.js` 七处（8363 行／406631 字节）把投送面改成单一所有权——`:294-298` 记账字段 `state.rendererPreemptedUri`、`:2037-2049` 保有权抑制、`:2053-2060` D-1 跃迁时 `stopLocalAudio()`、`:2062-2070` D-3 投送结束只回库不续播、`:2104-2119` D-2 `preemptIncomingRendererForLocalPlayback()`、`:2378-2390` MediaSession play/pause 首行投送路由、`:4390-4395` `loadCurrent()` 本地分支接线、`:8260-8264` cue-tail 加 `!isIncomingRendererSession()` 门。NULL 侧：`library_write.py:17-28`（理由与哨兵键反证）＋`:29-38`（八列契约）＋`:41-53 collapse_missing_labels()`＋`:169` 调用点；`library.py:73-81` 括号 import、`:2482` 标记键、`:2485-2524 _collapse_null_labels()`、`:2663` 调用点排在组表刷新之前，`:2655-2662` 写明该顺序为何不可判别。新增口径文档 `docs/LIBRARY_CURSOR_NULL_GROUPS.md`（8731 字节）并登记进 `docs/INDEX.md:9`。反增长：净关闭 2、新立 0，未放宽任何既有守卫。
- 2026-09-20 — R125 测试与仓库外变异矩阵（本轮最值钱的一条是「变异脚本自己会撒谎」）：新增 `src/tests/test_ui_renderer_ownership.js` 244 行／44 条断言（7 条源级接线断言：`loadCurrent` 内 remote return ＜ 抢占调用 ＜ 写 `audio.src`、MediaSession play/pause 路由先于本地元素、cue-tail 正则、记账字段唯一声明与唯一赋值各一条），`test_ui_playback_authority.js` case 3 改断言投送期间 cue-tail 冻结，Python 新增 `test_library_write.py:162/:184/:199` 与 `test_library_sqlite.py:853/:885`（`:746` 假库 save 后裸 SQL 注入 NULL）。仓库内定向复跑 `test_change_record test_library_sqlite test_library_write` 161 项 OK。仓库外副本 `%TEMP%\fnaudio-r126-copy`（981 文件，11 个相关文件与仓库逐文件 sha 全等）控制组刷新清单后复跑 `Ran 2448 OK (skipped=3)`／Node 74 文件 0 失败（`skipped` 比本机多的一条来自未复制的未跟踪 `artifacts/`，属环境差异）。变异 18 条：JS V1～V10 全灭；PY V11～V18 七灭一存活，V17 为等价变异、按设计不可杀，未伪造测试凑数；`docs/INDEX.md` 无测试读取，不作变异、人工核验。
- 2026-09-20 — R125 两处过头陈述的就地纠正（都记进 `PROJECT_CONTEXT.md`）：其一，PY 变异 runner 引用了根本不存在的模块 `test_library_query_page`，`unittest` 以 `_FailedTest` 恒返回非零，首轮八条 PY 变异被整批伪报 KILLED，连设计上不可杀的 V17 也显示「被杀」；重跑前先断言 pristine 副本控制组 rc=0，才拿到七灭一存活的真相——KILLED 的判定权属于「控制组绿＋这一条变异让哪具名字失败」，不属于退出码非零。其二，`test_ui_renderer_ownership.js` case 1b 原先在第二个 tick 之前自行清空投送元素的 `src` 并置 `paused`，把「同一投送下本机看着仍在播」这一被测前提自己抹掉，使 V2（去掉 `!previousActive`）逃过；改为保留前提＋`localIsPlayingNow()` sanity 断言后 V2 被杀。另记一条放置事实：NULL→`""` 的换序在组表、文件夹、外内容 FTS5 三条观测面上都折叠成同一个桶，所以 V17 杀不动不是测试不够努力。
- 2026-09-20 — R125 收口、清单与提交：`TODO.md` 插入本轮记录前实测 2213 行、开放 76 ＝ 代码 18 ＋ 设备 44 ＋ 决策 1 ＋ 台账 13、已关闭 1463（一律按行首前缀计）；插入后 2214 行、开放 74、已关闭 1466、0 个 CRLF。口径补一句：2214 是历史 split 口径，内容行实测 2213；本轮新增文件按内容行记，与 `git diff --stat` 同值（`test_ui_renderer_ownership.js` 244 行，初稿曾按 split 写 245，已按实测改回 244）。四桶规则本轮复算过：台账 13 ＝ L2071 之后的流水条目，决策 1 ＝ L1878，代码 18 ＝ L200 之前 16 条加 L546 与 L1837，其余 44 条为设备/外部段；关闭的两条都在代码桶，设备段一行未改。净关闭 2、新立 0。历史计数快照 155=64+82+9、115=51+43+8+13、88=24+43+8+13、82=22+44+3+13、80=20+44+3+13、77=18+44+2+13、76=18+44+1+13、74=16+44+1+13 并存不合并，以磁盘实测为准；终止仍差代码 16 ＋ 决策 1 ＝ 17 条。`SOURCE_MANIFEST.sha256` 在全部源码编辑完成后刷新为 705 条（`src/` 625 ＋ `android-client/` 80），全 CRLF、大写 hex、逐条比对 0 不一致，另抽查 app.js／library.py／library_write.py／三个测试文件逐文件 MATCH。终跑 `tools/test_offline.ps1` 见 `artifacts/offline-20260920-round191.log`。两笔提交均逐文件显式 pathspec：代码与测试一笔，三份根文档与 docs 一笔；未碰 `.gitignore`，未跟踪产物一律不入库。
- 2026-09-20 — R124 实现（净关闭一条决策项：D9 曲库连接池开关上设置页）：设置页第 2 个「运行」pane（`data-settings-pane="runtime"`）末尾新增 `libraryConnectionPoolInput` 复选框与「启用曲库连接池」文案，说明写明「即时生效，不需要重启 fnAudio」；控件复用既有全局类 `.metadata-toggle`，`app.css` 未改。服务端新增 `GET`/`POST` `/api/config/runtime`（`server.py:873`、`server.py:1512`），鉴权自动继承 `api_route_policy.py:48` 的 `/api/config/` 前缀（settings.read / settings.write），该文件未改。两处响应都回读 `library_connection_pool_enabled(self.server.config)` 而不是回显请求值：取证确认该谓词在键缺失时返回 False，与 `config.py` 加载器默认 True 不同，所以面板只能显示运行进程真正 honour 的值；`LibraryConnectionPool.snapshot()` 不含 enabled 字段，响应里附带 `status` 只作为「关掉确实排空了句柄」的观察证据。POST 用 `payload_bool` 只认 JSON 真布尔，文本 `"false"` 与 `0` 一律 400 且不触碰现值；提交走 `commit_config_update()`，其排空点在 `server.py:612` 且发生在 `config.clear()/update()` 之后，因此成功响应不可能早于句柄排空。`app.js` 新增顶层常量 `LIBRARY_CONNECTION_POOL_SETTING_KEY`（`app.js:6428`）与 `runtimeConnectionPoolInput()`/`loadRuntimeSettings()`（`app.js:6432`）/`saveRuntimeSettings()`（`app.js:6448`），`setSettingsTab` 切到运行 pane 即回读（`app.js:6426`），`chooseCurrentFolder` 的 runtime 分支排在 metadata 分支与 `saveLibraryPathsFromDialog()` 兜底之前。
- 2026-09-20 — R124 测试、控制组与变异矩阵（本轮抓到一处真实回归，抓到它的不是本地而是仓库外副本）：`src/tests/test_server_lifecycle.py:175` 的旧守卫 `test_the_pool_default_is_no_longer_invented_at_startup` 断言 `server.py` 全文不得出现 `LIBRARY_CONNECTION_POOL_CONFIG_KEY` 与 `"library_connection_pool"`，而新路由一开始正是直接 import 常量并按字面名写盘；本地当时只单跑本轮 6 项新测试，全绿，漏判。处理方式是不放宽旧守卫，改在 `library.py:1905` 增加 `library_connection_pool_config_key()` 作为该键的唯一公开出口，路由经它取键，`server.py` 内两个字面量复核均为 0 命中，复跑旧守卫加 6 项新测试得 `Ran 7 OK`。新增 `test_http_integration.py` 6 项（值来源、作用域、文本布尔拒绝、缺键保持、排空发生在提交之后、持久化失败不动运行值）与新文件 `src/tests/test_ui_runtime_settings.js`（pane 归属、不侵入 metadata pane、端口重启提示未被挤掉、常量与服务端键逐字对齐且键名归属 `library.py`、接线顺序、路由字符串两端对齐、`vm` 真跑回显/不编值/单键真布尔/失败必抛/控件缺失五组断言）。真实仓库 JS 全套 `files=73 failures=0`（原 72 变 73）。仓库外副本控制组先刷新 `SOURCE_MANIFEST.sha256` 再复制 978 个文件，得 Python `Ran 2443 OK (skipped=3)`、Node 73 文件 0 失败；V1～V12 变异逐条被具名杀手以非零退出码杀灭、`SURVIVORS=none`、当场还原并复绿。其中 V10（把排空挪到提交之前）只有本轮新增的 `test_runtime_config_turning_the_pool_off_drains_handles_after_the_commit` 杀得动，旧 lifecycle 测试面对同一变异 rc=0，杀不动。
- 2026-09-20 — R124 收口、清单与提交：`TODO.md` 插入本轮记录前实测 2212 行、开放 77 ＝ 代码 18 ＋ 设备 44 ＋ 决策 2 ＋ 台账 13、已关闭 1461（一律按行首前缀计）；插入后 2213 行、开放 76、已关闭 1463、0 个 CRLF。净关闭 1 条决策项（D9，原 L1881；本轮一切条目定位用文本前缀长锚点而非行号），新立 0 条，代码桶保持 18 条，设备段一行未改。决策桶从 2 变 1，剩 R73 的 `allow_disk=False` 取舍一条，需真机取证。历史计数快照 155=64+82+9、115=51+43+8+13、88=24+43+8+13、82=22+44+3+13、80=20+44+3+13、77=18+44+2+13 并存不合并，以磁盘实测为准。`SOURCE_MANIFEST.sha256` 在全部源码编辑完成后刷新为 704 条并逐文件抽查 MATCH。终跑 `tools/test_offline.ps1` 见 `artifacts/offline-20260920-round190.log`。两笔提交均逐文件显式 pathspec：代码与测试一笔 `feat(ui): expose the library connection pool switch on the runtime settings pane`，三份根文档一笔 `chore: record R124 closure`；未碰 `.gitignore`，未跟踪产物一律不入库。
- 2026-09-20 — R123 实现（净关闭三条：D1 许可证 L1872、队列死码 L71、状态未知灯 L74）：许可证侧新增 `LICENSE`（GPL-3.0 逐字正文 35149 字节）、`NOTICE`（2135 字节：再分发义务与「暂不托管」现状）、`AUTHORS`（815 字节：署名 `vinson023`，不含邮箱），`README.md:97` 由「项目许可证尚未明确」改为指向三份文件并写明裁定日期与裁定内容。降级指示侧：`index.html:70` 在 `#elapsed` 之后插入静态文案「状态未知」的 `#transportStateUnknown`；`app.css:765-774` 新增 10 行（注释 + 默认隐藏 + ID 限定加 !important 的显示态 + 桌面断点下的胶囊样式）；`app.js` 新增 `transportStateIsUnknown`（:4427，阈值复用 `TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS`）、`updateTransportStateUnknown`（:1917，唯一写点，经 `setDatasetStateIfChanged`（:5344）带比较写入）、三处接线（`updateDeviceLabel`:1830、`syncPlayerProgress`:1912、`updateRemoteUi`:2117，最后这处排在两条 early return 之前）。死码侧：删 `addQueue`、`addQueueAndPlay`、`playFolder` 三个函数（app.js numstat +49/-55），`runTrackAction` 的 action 判断由「queue 或 queue-play」收窄为只剩「queue」。设备段一行未改，本轮新立 0 条。
- 2026-09-20 — R123 测试、控制组与变异矩阵：新增 `src/tests/test_license_files.py`（5 项：逐文件 sha256、GPL 正文段落锚点、`AUTHORS` 禁邮箱与域名、`git remote -v` 为空即暂不托管未被动过）、`test_ui_dead_queue_entry_points.js`（三个死标识符在 app.js、index.html、全仓 grep 中必须为 0 命中）、`test_ui_transport_state_unknown.js`（灯的唯一写点、阈值、接线位置、比较守卫写入计数、CSS ID 限定的必要性）。既有两套测量被扩：`test_ui_library_loading.js` 的写入成本样本函数表加进灯的相关四个函数并注入阈值常量，`test_ui_renderer_transport.js` 新增 `constSource` 与 `stalenessLampNames` 并把常量注入两处 vm 上下文。真实仓库具名复跑全绿。仓库外副本 `C:\path\to\fnAudio_r123_verify2`（11 个关键文件与真实仓库逐字节 MATCH）控制组先绿：Python `Ran 2437`、OK（skipped=3）、退出码 0；JS 72 个文件 failures=0。变异矩阵 V1～V9 全部被具名杀手杀灭——V1 加回 `addQueueAndPlay`、V2 把灯接线挪到 early return 之后、V3 阈值 10 改 30、V4 删 `setDatasetStateIfChanged` 的比较守卫（写入计数 1 变 3）、V5 取反判据、V6 CSS ID 选择器换成 `.progress span`、V7 删 `LICENSE` 的「Version 3, 29 June 2007」整行、V8 在 `AUTHORS` 插入带邮箱的行、V9 删 `updateDeviceLabel` 的接线；每条还原后复绿，矩阵跑完 11 个文件与真实仓库 differ 0。
- 2026-09-20 — R123 收口、清单与提交：`TODO.md` 三条以单行末尾追加收口说明的方式关闭（原条目各自都是单行，不能新增行），并在 L2 插入本轮记录，实测 2212 行、开放 80 变 77、已关闭 1457 变 1461、0 个 CRLF；`CHANGELOG_AI.md`、`PROJECT_CONTEXT.md` 同步最新在前。`tools/update_source_manifest.ps1` 刷新后 703 条，`tools/takeover_forensics.py --full` 实测 listed 703、drift 0、stale 0、unlisted 0、退出码 0。附带修掉一处只在字节层可见的污染：`app.css` 被写入 1 个 CRLF，因 `.gitattributes` 归一化而在 `git diff` 里完全隐形，已改回裸 LF（168902 字节、0 CRLF）后复刷清单。清理仓库外副本与 `%TEMP%` 临时件，删除 `tools/browser-e2e/r123_probe.js`。终跑 `tools/test_offline.ps1` 记入 `artifacts/offline-20260920-round189.log`。提交分三笔（逐文件显式 pathspec，不使用 `git add -A`，未跟踪的 `artifacts/`、`music/`、`_external/`、`tools/` 下 SDK 与平台工具、`full-test-output.txt`、离线日志一律不入库，`.gitignore` 未改）。
- 2026-09-20 — R122 实现（关闭 TODO L216：同一个「播放位置」在四条投影里单位不一致）：方案取原条目 ⑤ 两个候选的组合，并且权威方向与 (b) 相反 —— 服务端在写进权威 core 之前折算一次，同时给每条投影显式声明单位，前端不再自行推导。`playback_cue_position.py` 抽出 `cue_is_transcoded()`（折叠与反向折叠共用「只有 `.ape` 真被裁切」这一判据，避免两处各自演化），新增 `public_cue_position()`、`cue_segment_declaration()`、`project_cue_seek()`（折叠的精确逆）。`server.py` 新增 `project_mpd_transport_position()`，接在 `on_mpd_transport` 的两个 `sync_output_status` 写点上，替换原先直接转发的 `safe_float` 读值，于是 core、持久化会话、SSE、轮询四路共用同一个客户端单位；`restore_playback_session` 先算 `backend_start` 再交给 `sync_playback_queue`，其成立前提是 :2254 传 `play=False` 使 `mpd_client.py:367-370` 的 `if play and start > 0` 不成立 —— 这一点若将来被改动，恢复落点会立刻错位，因此写进条目正文。`playback/mpd_output.py` 只在 seek 分支走逆折叠，曲目映射优先取请求载荷、缺失才回落队列引用。`playback/core.py` 新增 `snapshot_with_item()`，用同一把锁把位置与当前曲目配对取出，杜绝「新位置配上一轨偏移」。`playback_status_response.py` 为 alsa、mpd、upnp 三支挂顶层 `cue_segment` 与夹紧过的 `state_version`，`playback_event_presentation.py` 的 SSE 载荷同样带声明。`app.js` 采纳规则统一为「服务端声明优先，未声明才回落本地元数据」，`seekDuration()` 在声明为段时不再二次减 `cue_start`，`pushToDevice` 的本地回落补上 `data.cue_segment !== false` 门。已知代价如实登记：持久化会话的单位翻转一次，升级前存的整文件秒数会被当作客户端单位读，native CUE 段续播可能把进度条顶满一帧，因不影响落点且下一帧自愈，本轮不写迁移脚本。
- 2026-09-20 — R122 测试、控制组与变异矩阵（含一处本轮自己发现的判别缺口）：新增 27 项 Python（`test_mpd_output` 5、`test_playback_core_state` 5、`test_playback_cue_position` 6、`test_playback_event_presentation` 4、`test_playback_status_response` 3、`test_playback_restore` 4）与 1 个新 JS 套件 `src/tests/test_ui_remote_cue_units.js`。控制组不引用上一会话数字：本轮在仓库外副本 `E:/fnAudio_r122_verify`（robocopy 仅 src、排除 `__pycache__` 与 `.pyc`，共 621 文件）当场复跑六模块 Ran 120 OK、JS 套件 exit 0。变异矩阵 M1～M13 逐条改判据、改写点、改前端采纳规则，结果全部 KILLED，控制组同法跑为存活。两处如实标注：① `test_the_mpd_listener_folds_the_seconds_before_publishing_them` 与 `test_the_event_stream_publishes_the_snapshot_and_item_as_a_pair` 是源码级接线守卫而非行为覆盖，因为它们的宿主分别写在 `main()` 与请求处理器方法体内，单元测试无法调用；② 「声明字段只验布尔类型」这一类判据（M5 的等价变形）设计上不可杀，已在文档串注明理由。收口复核的新证据：M7（SSE 路由退回不带 item 的 `snapshot()` 并丢掉第三个实参）在上一会话的 V0～V9 矩阵里根本没有对应变异，补跑时最初确实存活 —— 若只依赖纯函数测试，四路投影里 SSE 这一路可以在任何时候无声退化；补守卫后 M7 被新测试杀掉，副本文件逐一与仓库内做 sha256 比对确认已还原。
- 2026-09-20 — R122 收口：TODO L222 关闭、docs 路径漂移修正、四条裁定登记、计数与门禁。① **L222（裁定 C3＝移出版本树到 `E:/fnAudio/_external`）**：实测 `_external/apk-analysis` 1.80 GB、`_external/runtime` 1.43 GB，合计 3.23 GB 仍在盘上，**回收量 0**，条目原写「可安全回收约 1.74 GB」作废；`tools/apk-analysis`、`tools/runtime` 旧位置已不存在；`git ls-files` 与 `git ls-tree -r HEAD tools` 对两棵树 0 命中 ⇒ 从未跟踪，移出不动历史、也不需要碰 `.gitignore`；`_external/apk-analysis` 下仍有 5 个 `.mitm` 与 2 个 `.pcap` 合计 54,156,024 B，泄露面未因迁移改变，本条只关闭「处置方式待定」。② **docs 18 处路径漂移已改**：`FN_CONNECT_EMULATOR_RESEARCH_20260816.md` 12、`GO_MUSIC_DL_PROVIDER_VALIDATION.md` 4、`FNOS_MUSIC_MEDIASESSION_RESEARCH_20260831.md` 1、`FN_CONNECT_RELAY_CAPTURE_20260812.md` 1，改后 `docs/` 内旧路径 0 命中、`_external` 命中 18，抽查目标目录全部存在；三份根文档与历史条目里的旧路径命中（CHANGELOG 22、PROJECT_CONTEXT 1、TODO 7）按「历史不回填」不动。③ **四条裁定登记**：L69、L70、L73、L150 行尾各追加一段裁定原文与取证依据，四条仍挂未勾选，实施排 R123 与 R125；登记时就地纠正上一会话的过头陈述（`index.html:112` 实有 1 处 `aria-live` 等于 polite，归 `#deleteTrackStatus` 局部，非全局；`showToast` 与 `role` 等于 status 均 0 命中，非阻塞反馈全仓只有 28 处 `alert`）。④ **计数（按行首勾选标记逐条实测，不采信任何快照）**：开放 82 → 80 ＝ 代码 20 ＋ 设备 44 ＋ 决策 3 ＋ 台账 13，已关闭 1454 → 1457，与 HEAD 版 TODO 对账为 -2 开放 / +3 关闭，+3 中只有 2 条是真实关闭，第 3 条是本文件顶部记录自身也是 `- [x]` 勾选项。历史计数快照并存不合并：`155 = 64 + 82 + 9`、`115 = 51 + 43 + 8 + 13`、`88 = 24 + 43 + 8 + 13`、`82 = 22 + 44 + 3 + 13`、本轮 `80 = 20 + 44 + 3 + 13`。⑤ **门禁与清单**：`SOURCE_MANIFEST.sha256` 由 699 条刷新为 700 条（新增 `src/tests/test_ui_remote_cue_units.js`），逐文件 sha 抽查一致；`tools/takeover_forensics.py --full` 退出码 0；终跑 `tools/test_offline.ps1` 记入 `artifacts/offline-20260920-round187.log`；%TEMP% 临时脚本与仓库外副本收口后删除；设备段 44 条一行未改。 ⑥ **收口补记**：终跑由 round187 更正为 round188（修掉 `playback_cue_position.py` 末尾 1 个多余空行之后重跑，Ran 2432 / OK skipped=2 / exit 0）；修后变异矩阵复跑仍 13/13 全灭、清单 700 条幂等、取证零漂移。经负责人授权，本轮改动以显式 pathspec 分 4 次提交入库，最后一次即承载本补记的文档提交，`git add -A` 与 `.gitignore` 均未使用，设备段 44 条与目标正文段仍逐字节未动。
- 2026-09-20 — R121 接管核验（先取证后落笔：既不采信上一会话摘要里的计数，也不采信持续目标正文里的历史快照）：① 工作目录 E:/fnAudio、分支 main。HEAD 实测 89ded0132278b84f6d187b9638f1dda776fdf26b（父提交 b0a19d807f298d6c40d3479834d588fa829adf1d，首行 "chore: land the project baseline into version control (scope B)"），相对 R120 记录里写死的 d362047 已经前进两次。持续目标正文中的「HEAD 固定 d362047」「禁止 git commit」「禁止 git add」是任务创建时抓的 objective 快照文本，objective 不随磁盘更新而改写；用户 2026-09-20 已明确授权提交并撤回这两条禁令，故其自授权起作废——本轮只登记作废依据，不改写目标正文，也不擅自调整终止条件（maxGoalRounds=72 同理不作为终止理由）。未撤回的约束仍然有效：.gitignore 实测一字未改（1138 B / mtime 2026-08-14 16:43:49），设备段不盲改。② 未完成状态检查：.git/MERGE_HEAD、rebase-merge、rebase-apply、CHERRY_PICK_HEAD、BISECT_LOG、REVERT_HEAD、sequencer 七项逐个探测全部不存在；staged 0、stash 0。③ git status --porcelain 实测 673 条 = 667 个 ?? + 4 个 " D" + 2 个 " M"；两个 " M" 是本轮的 TODO.md 与 tools/browser-e2e/tests/ui.spec.js（+135/-3）；后者在本轮取证中纠正了我自己上一句的措辞——它不是上一轮遗留：文件 mtime 实测 2026-09-08 18:41:49，内容对应 CHANGELOG「# 2026-09-06 首屏快照复用指标」那一节的浏览器 E2E 断言，从 9 月初起就一直没进版本库，本轮收口提交一并补上（它是已跟踪文件，只是落在范围 B 的 pathspec 之外）；四个 " D" 是 artifacts/0.1.174/{PACKAGE_CONTENTS.txt,RELEASE_NOTES.md,SHA256SUMS,VALIDATION.md} —— 它们在 cc595af 里进过版本库、磁盘上整个 0.1.174 目录早已不存在，范围 B 故意不碰 artifacts/ 所以删除没被记录，留在工作树等负责人裁定「恢复」还是「提交删除」，本轮不动。④ 上轮终跑从日志本身复核（不采信转述）：artifacts/offline-20260920-round183.log 2546 行 / 408885 B / mtime 2026-09-20 08:55:12；L2468 "Ran 2405 tests in 102.164s"、L2470 "OK (skipped=2)"、JS 收尾 68 行（65 行 "… checks passed." + L2471 host playback session adapter / L2504 ui library reference item / L2533 ui track search text 三行 "… tests passed"）、L2546 "exit=0"；结尾一批 CRLF→LF 的 git warning 属 .gitattributes 口径，不是失败。⑤ 四桶计数从磁盘重算：R121 编辑前 88 = 代码 24 + 设备 43 + 决策 8 + 台账 13，编辑后 82 = 22 + 44 + 3 + 13，和校验为真。三套历史计数并存不合并：155 = 64+82+9（目标正文快照）、115 = 51+43+8+13（R99 实测）、88 → 82（R120 登记 / R121 实测）。漂移成因查明：目标正文只在创建时抓过一次计数，此后 36+ 轮的关闭、裁定、拆分都只落 TODO.md，从不回写 objective，因此正文里的 64/82/9 与今天的磁盘没有任何对应关系，只能作为历史现场保留，不能拿来当终止判据。⑥ 设备段摘要值 rebaseline 的正确顺序：改动前先让同一个按标题定位区间的计数器在改前的 TODO.md 上复现出 R120 登记的 877 行 / 前缀 63661836771c36e0，确认口径一致后才动手；改后因 C2 拆分新增 2 行 → 879 行 / 前缀 19c1120fc68538c9，旧前缀自本起作废但仍保留在 R120 记录里，作为「R121 之前设备段一行未改」的有效证据。
- 2026-09-20 — R121 八条产品决策裁定落地（本轮未修改任何生产代码，也没有靠改代码关闭任何条目，落实方式一律是「取证 + 登记 + 后果写清」）：① D1 许可证：方向定为开源、暂不托管，但具体许可证文本仍未指定 —— git remote -v 为空 ⇒「暂不托管」已是现状无需改动；git ls-files 里 LICENSE/COPYING/NOTICE/AUTHORS 四类候选 0 命中；README.md:97 现在写着「项目许可证尚未明确，不应自行假设开源授权。」⇒ 本条保持 [ ] 并收窄为「选定具体许可证 + 决定要不要 NOTICE/AUTHORS」，本轮不写 LICENSE。② D2 keystore：接受临时密钥，关闭；登记后果 = 日后换正式密钥时已安装 APK 必须卸载重装才能升级；实现依据 android-client/app/build.gradle L5-8 四个 FNAUDIO_RELEASE_* 入口、L9 hasReleaseSigning、L44-58 仅四元齐备才挂 signingConfig、L74-87 verifyReleaseSigning 抛 GradleException 并挂在 preReleaseBuild。③ D3+C1：AcoustID/Chromaprint 永久关闭，原代码桶 L1817 整条并入本条并从文件删除；真机取证 = /usr/lib/x86_64-linux-gnu/libchromaprint.so.1 存在，但 fpcalc 在 PATH、/usr/bin 与 /vol1/@appcenter/fnaudio 下全部不存在，配置 metadata_fingerprint_enabled=false。④ D4 降权：接受 root，关闭；三前提实测 —— fnOS 确实提供 uid=996 的 fnaudio 服务账号但它不在 audio 组；/vol1/@appcenter 与 /vol1/@appconf 是 drwx------ root（0700 的成因是打包脚本 umask 077 + install -d -m 700，不是平台限制）；/dev/snd/* 是 0660 gid=29，runuser -u fnaudio 对六个设备节点 access() 全 False ⇒ 降权需同时改目录权限与设备组，代价高于收益；对照 moode 也是用自己的专用用户跑 mpd。⑤ D6：批准两个恢复证据脚本进库（tools/verify_release_evidence.ps1、tools/index_release_evidence.ps1），并更正原条文的取证错误：「tools/test_offline.ps1 引用它们」实测 0 处，真实引用面是 test_build_release_script.py 7 处 / test_offline_verification_script.py 15 处 / RECOVERY.md 3 处。⑥ D7：tools/blutter 已整体移出版本树 → E:/fnAudio_external/blutter（同卷 rename；3539 文件 / 69.6 MB / 自带 .git 的只读 pack 完整；Test-Path tools\blutter 现为 False），移前取证 git ls-files tools/blutter 0 条、仓库无 .gitmodules、全仓无脚本与测试引用。⑦ D8：MAX_PERSISTED_FAVORITES 保持 50000 并关闭；设备实测 favorites 仅 3 行，且该常量是 state_store.py:39 的落盘行淘汰上限（_trim_persisted_favorites :361-382），不是预分配也不是请求上限。⑧ D5：保持开启（不选边）；本条要量的是「真实曲库里缺索引身份的行占多少」，而测试机 /vol1/1000/music 有 97 文件 / 545 MB、tracks 表却只有 6 行且 6/6 全部带完整索引身份、cue_tracks 0 行 ⇒ 按 R73 口径带索引身份的行两类取值都是 0 次 os.stat，样本对本条要回答的问题是零信息量，需要含无标签音频的真实曲库才能决策。⑨ C2 拆分：原代码桶 L154 连接池条拆两半 —— 真机半进 P0 段（新 L1863，含操作指引「一旦出现索引替换失败或卸载卡住，先回退 library_connection_pool 再排查，别在设备上加兜底逻辑」与 R62 历史结论、以及 24 h fd 时间序列的取证口径），产品半进决策段成为 D9（新 L1879）；磁盘事实：config.py:22 DEFAULT_LIBRARY_CONNECTION_POOL=True、:29 进默认表、:93-94 与 :153-154 走 _strict_bool；server.py:591 commit_config_update() 在 :606 调 library.py:1917 apply_library_connection_pool_config（改配置不需重启）；诊断面 library.py:1905 → diagnostics.py:42/72、health_snapshot.py:36/68；src/app/ui 全树 grep connection_pool/connectionPool 命中 0 条 ⇒ 控件确实不存在。⑩ 真机取证与两处自我更正：负责人给的 21 端口实测是 FTP（横幅 "220 FNOS FTP server (SmbFTPD Ver 2.10 TLS)"），真正的 SSH 在 22（OpenSSH_9.2p1 Debian-2+deb12u7），plink -P 21 会挂死，且本机 ssh.exe 不在 PATH ⇒ 改用 paramiko 5.0.0 + AutoAddPolicy 走 22；:5666 是 fnOS 控制台（/api/health 404），fnAudio 实际监听 53199。设备画像：Debian 12 bookworm / Linux 6.18.18.c1032-trim x86_64、FPK 0.2.34、主服务 pid 237556（root python3 server.py --host 0.0.0.0 --port 53199 --config /vol1/@appconf/fnaudio/config.json）、mpd 子进程 pid 237571、state_meta.revision 7、playlists 1 / playlist_tracks 3。设备侧全程只做 cp/find/ls/ps/runuser 读操作，未改任何文件、未重启服务，取证用的 /tmp/r121 在收口时清除。
- 2026-09-20 — R121 代码桶 L216（原描述为 mpd_service 播放位置可能双算）读案定案，条目改写后保持开启、实施留给 R122：按「新发现的问题当轮修掉、当轮证伪或并入既有条目」的约束重做取证。① 真实尺寸重测（旧值作废）：src/app/server/services/mpd_service.py 2150 行 / 98885 B、src/app/server/playback/mpd_client.py 457 行。② 证伪一 bind_to_address：mpd_service.py:616 生成的配置里 host 只在 :128 赋值，不存在外部可注入路径，「未转义写进配置」不成立；改写为条件句 —— 若将来 host 变为可配置，必须走 _mpd_quote。③ 证伪二 mixer_policy()（:1993-2047）在全部返回路径都带 control 与 device 两个键，没有缺键分支。④ 并入不立项：_start_locked() 里对 mpd_nice 的写入在 :670、:704、:707-708 重复三次，属同一函数内的冗余。⑤ 上轮遗留的悬置项定案：PlaybackCommand 的 position 唯一来源是 server.py:2552 payload.get("position")（客户端请求），服务端内部不存在回灌双加；restore_playback_session 的 start=restored_position 在 play=False 时被 mpd_client.py:367-370 忽略，只影响显示不影响落点。⑥ 真实缺陷（本条继续开启的唯一理由）：CUE 播放位置的单位在四条投影里不一致 —— MPD 监听器把未折算的整文件秒数写进 core（server.py:3226-3232，另 :3248-3253），会话投影同样存整文件秒数（playback_session_projection.py:38），/api/playback/status 的 mpd 分支却在 server.py:2726 调 normalize_cue_position()（playback_cue_position.py:36，仅非转码 CUE 折 whole-cue_start）返回轨内秒数，SSE 走 playback_event_presentation.py:22/73 又返回未折算的整文件秒数；前端 app.js:2406 把两路写进同一个 state.remoteBaseSeconds，而唯一折算判据 app.js:2413（state.remoteCueSegment = cue_track && !isDacTarget()）里 playback_target_policy.js:5 的 isDac 只匹配 dac: 前缀 ⇒ 经 MPD 播放时恒判「已裁切、不折算」，而事实是只有 .ape 走 cue_flac 裁切（mpd_service.py:408-411、transcode.py:319-326 的 -ss cue_start -i path -t duration），FLAC 版 CUE 整文件交给 MPD。后果：SSE 一连通 remoteStateVersion 转正、缺顶层 state_version 的轮询（playback_status_response.py:31-38 未挂该字段）在 app.js:2396 被整条丢弃，进度条完全取未折算值，第 2 轨起多显示 cue_start 并被 seekDuration() 夹满；SSE 未连通的浏览器反过来以轮询为准，同一字段按到达顺序互相覆盖；显示与 seek 提交（app.js:4598）建立在两种矛盾前提上。⑦ 两个候选修法都改语义、勾选前仍需真机回归：(a) 进 core 前折算一次，让 core/会话/SSE 统一到轨内，须同步改 normalize_cue_position 与 mpd_output.py:139（那里 cue_start = max(0, cue_offset) + requested_position）；(b) 明确 core 一律存整文件秒数、由前端按投影来源折算，须给 app.js:2413 补「曲目是否真被裁切」的判据并核对 DLNA/ALSA/MPD 三条链路各自的假设（mpd_service.py:440/454 的 start=0.0 if current_cue_ape else start 就是三条链路不同形的直接证据）。⑧ 本轮无生产代码改动 ⇒ 没有可变异对象，仓库外副本变异矩阵不适用（未做即写明未做，不当作已做）；控制组的绿由本轮终跑门禁 artifacts/offline-20260920-round186.log 承担（186 是本轮最终号；round185 因外来进程占核 FAIL，取证见下一条 ②-b～②-d）。
- 2026-09-20 — R121 终跑、校验器、清单与收口范围（含一处按规则重跑门禁的登记，以及对本轮自己写下的一个假事实的就地纠正）：① **纠正自己的假陈述**：接管核验条最初把未提交的 `tools/browser-e2e/tests/ui.spec.js` 说成「上一轮遗留」，实测该文件 mtime `2026-09-08 18:41:49`、内容对应本文件「# 2026-09-06 首屏快照复用指标」一节的浏览器 E2E 断言，与 R120 无关 ⇒ 已就地改写为「9 月初起就从未进过版本库」，纠正依据留在原句里而不是另开一条。② **按规则重跑门禁**：上述纠正发生在 `artifacts/offline-20260920-round184.log` 落盘之后（408183 B / 2540 行 / mtime 2026-09-20 10:06:36 / `Ran 2405 tests in 108.523s` / `OK (skipped=2)` / JS 含 passed 结语 68 行 / `exit=0`），按「终跑日志 mtime 必须晚于本轮全部文档编辑」重跑同一门禁产出 `artifacts/offline-20260920-round185.log`，round184 保留不删（与 R120 的 round182 → round183 同一先例）。②-b **round185 不是绿的，本轮如实登记**：`Ran 2405 tests in 144.808s` / `FAILED (errors=1, skipped=2)` / `exit=1`（405900 B / 2488 行 / mtime 2026-09-20 10:13:28），唯一 error 是 `tests.test_large_library_benchmark.LargeLibraryBenchmarkTests.test_benchmark_enforces_bounded_sqlite_pagination` 在 `tools/benchmark_large_library.py:672` 抛 `RuntimeError: pooled library reads are not faster than reopening the index`，由 `tools/test_offline.ps1:39` 判成 `Python tests failed`；:653-662 用 `median_sample(..., samples=5)` 先跑 unpooled 段、再跑 pooled 段，是先后两段式的负载敏感比较，而 :669-670 的 `reuses`/`creations` 结构守卫通过 ⇒ 差异只可能来自计时段的机器负载。②-c **取证钉死根因**：同一份代码 round184 用时 108.523s、round185 用时 144.808s（慢约 33%），指针不在代码；实测机器上有一个外来进程 PID 10196（python.exe，命令行无参数、1 线程、工作集 5.4 MB、150 句柄、创建于 2026-09-20 00:36:48、父进程 11784 已消失）累计 CPU 34616 秒，6 秒采样窗口内消耗 6.03 秒 CPU ⇒ 稳定占满一个核，形态与上一会话中断后残留的空转解释器一致；`taskkill /PID 10196 /F` 之后 `Get-Process python` 计数归 0，单跑该测试模块连绿两次（`Ran 2 tests in 1.998s` OK、`Ran 2 tests in 1.952s` OK）。②-d **裁定：不改代码、不另立新项**：按「新发现的问题当轮修掉、当轮证伪或并入既有条目」，把这条测量形状缺陷并入正在量池化冷页开销的 TODO L155（事故数字、两段式比较的结构性缺陷、以及改成交错配对 A/B 采样并以结构计数为主判据的修法一并写入该条，实施轮配判别测试与仓库外变异矩阵），本轮新立可离线代码项 0 条 ≤ 关闭数 2 条。②-e 换号重跑得到的本轮终跑是 `artifacts/offline-20260920-round186.log`，round184/round185 一并保留；三份根文档里的日志引用同步改成 round186，本轮只对 round186 声明可确定的不变量：`Ran 2405 tests`、`OK (skipped=2)`、`exit=0`，尺寸与行数由下一轮从磁盘取证后登记，避免把未验证的数字写成结论。③ **根文档**：TODO.md 顶部 1 条 R121 记录 + 五处条目编辑；CHANGELOG_AI.md 顶部 4 条；PROJECT_CONTEXT.md 顶部 4 条。三份全部 LF、无 BOM、无 U+FFFD/NUL/U+2028/U+2029/ZWNBSP、无其它控制码位、顶部连续记录块内无逐字重复行、日期最新在前（TODO 的适用区间是它顶部的连续轮次记录段 L2-L78，越过该段之后是历史开放条目混排，整块日期本就不单调，这是文件既有形状，不是本轮造成的漂移）。④ **只读校验器**（跑后即删，不留仓库内脚本）：`verify121.py` 共 97 项断言全 PASS / 0 FAIL；内含一条口径回归——同一个按标题定位区间的计数器 `buckets2.py` 必须先在**改前**的 TODO.md 上复现 R120 登记的 `88 = 24+43+8+13`、设备段 877 行、digest 前缀 `63661836771c36e0`，复现成立后才允许采信它对本轮文件给出的 `82 = 22+44+3+13` 与 `19c1120fc68538c9`；另有一条对校验器自身的更正也被记录：第一版把「整块日期单调」「占位符扫描覆盖整块」「`.gitignore` 用 mtime 阈值判定」「.new/.orig/.rej 递归全仓」当成通用口径，四项都产生假 FAIL，改判依据逐条写进脚本 docstring（占位符一例命中的是 R120 记录里一段「`or` 加空字典字面量」的真实代码文本，`.new` 一例命中的是 `tools/runtime` 里 Go 包自带的 `surface.new`）。仓库自带 `src/tests/test_change_record.py` 3 项 OK。⑤ **清单与取证**：`tools/update_source_manifest.ps1` 连跑两次输出逐字节相同（699 条 / 75784 B / 文件 SHA-256 `76E2A8F39D9C70BD…E047B36F`）⇒ 幂等成立。顺带查清一条口径：该清单的作用域只有 `src/` 与 `android-client/`（工具第 29 行的 `Get-ChildItem` 入参决定），根文档与 `tools/` 都不在其中 ⇒ 本轮的文档编辑不会也不应改变清单内容，`SOURCE_MANIFEST.sha256` 在 `git status` 里保持未修改即为证。逐文件抽查 6 件：`services/mpd_service.py`、`ui/app.js`、`playback/mpd_client.py`、`src/tests/test_ui_library_loading.js` 四件 sha 与清单一致，`tools/test_offline.ps1`、`tools/verify_release_evidence.ps1` 两件报 NOT-IN-MANIFEST 属预期而非缺口。`python tools/takeover_forensics.py --full` 退出码 0：699 条 / drift 0 / stale 0 / unlisted 0。⑥ **卫生**：非 vendored 区域无 `.new`/`.orig`/`.rej`；`.gitignore` 经 `git diff` 与 `git status` 双重确认为零改动；`tools/blutter` 已确认不在树内、`E:/fnAudio_external/blutter` 在位；仓库外证据 `E:/fnAudio_round120_prechange/`、`E:/fnAudio_r118_deleted_backup`、`E:/fnAudio_external/blutter` 保留，`%TEMP%/r121_dev` 与设备侧 `/tmp/r121` 在收口后清除。⑦ **收口提交范围**（负责人授权在手，禁 `git add -A`）：清单本轮幂等复算后字节未变 ⇒ 无需入档，实际只 add 四件：三份根文档 + `tools/browser-e2e/tests/ui.spec.js`（已跟踪、9 月初遗留未提交，见 ①）；`artifacts/`（含门禁日志）与 `references/` 维持未跟踪；`artifacts/0.1.174/*` 四个 ` D` 继续留待负责人裁定；本轮提交产生的 commit hash 按惯例由 R122 从磁盘取证后登记。
- 2026-09-20 — R120 接管核验（先取证后落笔，不信上一会话摘要里的计数）：① 工作目录 E:/fnAudio、分支 main、HEAD 仍是 d362047a082d5487a51471a1fabc220f784ae807（本轮不移动）；`git status --porcelain` 实测 1280 条（` M` 147 / ` D` 6 / `??` 1127）、staged 0、stash 0（同一次接管内早先测得 1279 条 / `??` 1126，差额恰是随后落盘的本轮 round182 日志：接管数字与终跑数字之间会因日志自身而漂移，故本条以修订后的终值为准）；逐项 Test-Path 确认无 MERGE_HEAD / MERGE_MSG / CHERRY_PICK_HEAD / BISECT_LOG / REVERT_HEAD / AUTO_MERGE / rebase-merge / rebase-apply 残留 ✓ `.gitignore` 未碰；② 上一会话留下的现场与磁盘相符：`src/app/server/cover_cache.py` 1364 行 / 59239 B（修改已落地；修改前字节的权威存放点是仓库外目录 `E:/fnAudio_round120_prechange/` —— `cover_cache.py.1343l.58035B.orig` 58035 B / 1343 行、`test_cover_cache.py.1619l.88844B.orig` 88844 B / 1619 行；上一会话记的 `%TEMP%/r120_backup/` 那份副本此刻实测已不存在，与 R119 先例一致，故本条把证据改指可长期核对的位置）、`src/tests/test_cover_cache.py` 1718 行（修改前 1619 行 / 88844 B）、三份根文档停在 R119（TODO 顶部条为 R119、CHANGELOG 顶部为 R119 二次接管、PROJECT_CONTEXT 顶部为 R119 二次接管）⇒ 判定本轮处于「代码与测试已改、文档未记、变异未跑、门禁未跑」的中间态，接续而不重做；③ `SOURCE_MANIFEST.sha256` 699 条与活树一致：`tools/takeover_forensics.py --full` 报 manifest lists 699 files、drift 0、stale 0、unlisted 0、exit 0 ✓（清单里 .md 条目与直接 Get-FileHash 结果不同属该文件的哈希口径差异，以本仓库自带工具为准）；④ 上一轮终跑日志 `artifacts/offline-20260920-round181.log`（408146 B / 2539 行 / 7:59:47）与 round180 同尺寸，本轮终跑将是 `artifacts/offline-20260920-round183.log`（round182 实测已全绿：408885 B / 2546 行 / `Ran 2405 tests in 102.451s` / `OK (skipped=2)` / exit=0，但其 mtime 08:41:27 早于随后对 L4 提交口径与本段记录措辞的两次修订，按「终跑日志必须晚于全部文档编辑」重跑，旧日志保留不删）；⑤ 四桶从磁盘重算（按 R113 书面规则、脚本 `%TEMP%/r120x_buckets.py`）：开放项 89 = 顶部段 22 + 设备段 43 + 决策段 8 + 三条具名散条目（L543 持续审查未完成范围、L1817 Chromaprint/AcoustID、L1835 继续按可测试边界拆分；插入本轮顶部这条 TODO 记录之前分别是 542 / 1816 / 1834（顶部新记录本侧 TODO 是 1 条、CHANGELOG 是 4 条、PROJECT_CONTEXT 是 5 条，只有 TODO 的 +1 会影响这三处行号））+ 其余 13 条台账 ⇒ 与上一会话摘要给的 89 = 25 + 43 + 8 + 13 一致，关闭 L66 后应为 88 = 24 + 43 + 8 + 13；⑥ 设备段基线：本轮另存设备五行标题区间（插入顶部记录后为 L806-878 / L879-1636 / L1819-1830 / L1838-1863 / L2058-2065；插入前是 L805-877 / L878-1635 / L1818-1829 / L1837-1862 / L2057-2064）逐行拼接的 sha256 前缀 63661836771c36e0 作为「一行未改」的可复算依据（拼接口径：各区间取闭区间、按 TODO.md 的行序排列、段与段以及行与行之间都以 `\\n` 连接且整个序列末尾不加换行，实跑得 877 行；本会话按该口径重算得到同一前缀，换任何别的口径都不等于它）（上一会话摘要给的 4e0c6febe4bf9186 因切片口径未写在任何磁盘文件里而无法复现，本条改用可复算定义，不拿不可复现的数字当结论）。
- 2026-09-20 — R120 关闭 TODO L66 之审计与根因（条目原话：cover_cache.py 与 dlna/service.py 的并行只读审计结论尚未落地）：① `prune_cover_cache` 第三层（字节预算 + 磁盘不留量）原循环体只有十行：`if total <= maximum and disk_has_reserve(...): break` 之后直接 `if not reclaim(path): break`（asset 先删），再 `for alias_path in aliases: reclaim(alias_path, ...)`（alias 后删），全程不看 `deletes_left`。`reclaim()` 在 `deletes_left <= 0` 时返回 False 且不删，所以预算在一个 unit 中途用尽时必然出现「asset 已删、部分 alias 还在」——磁盘上的 `.asset` 别名指向不存在的 artwork。② 为什么这不是理论问题：该文件 L694-695 的注释声明悬空别名 never survives a sweep，而 L725-728 的 stale_aliases 一支只在下一轮清扫里救回来；`cached_thumbnail_for_item(allow_disk=False)` 的翻页路径不做磁盘复核，`_ASSET_ALIAS_CACHE` 会把 `cover-asset/<id>` 继续 advertise 给浏览器直到某次真实封面请求触发 `_forget_advertising_asset`（L430-444 的存在理由就是补这个洞）。③ 为什么修复必须保持 alias→asset 的删除次序而不是反过来：发布侧写 asset 成功之后才写 alias（顺序有意），撤销操作若不镜像它，同一崩溃窗口会留下同样的悬空别名——这是把不变量而非把症状写进代码。④ `dlna/service.py` 通读 1220 行的结论是不立案，两处可疑当轮证伪：`_didl_item` L1200 后半段 `any(name.startswith("res@") ...)` 与 `include()` 内的 `field.startswith("res@")` 重复（死代码，不改变行为）；`DlnaEventService._timeout` L622 `int(match.group(1))` 无位数上限在 py3.11+ 会因超约 4300 位抛 ValueError，但 `app/server/server.py:1271` 已把该路径的 ValueError 收口为 412 响应，不产生 500、不阻塞订阅。⑤ 一并登记为观察而非新项（并入既有「provider 返回值可信度」口径）：`_browse` L956 `page = self.library_page(params)` 不防 None，而 L944 的 folder 分支写了 `or {}`；本轮不改行为，只把差异写进记录，供后续同一条目一并处理。
- 2026-09-20 — R120 实现、判别测试、控制组与变异矩阵：实现 = `cover_cache.py` 新 L739-769 替换原 L739-748（把 unit 定为可淘汰的最小单位：动文件前 `if deletes_left < len(aliases) + 1: break` 预留整个 unit 的额度；alias 删不动即 `stuck = True` 并 `break` 出整个循环，不再尝试后面的 unit；asset 删除失败同样 `break`），文件 1343 → 1364 行、58035 → 59239 B，L739 之后行号整体 +21。判别测试 = `src/tests/test_cover_cache.py` 1619 → 1718 行，`CoverCacheSweepTests` 内新增 `_assert_no_alias_names_missing_artwork()`（磁盘侧逐个 `.asset` 经 `_alias_asset_path` 验目标存在 + 内存侧遍历 `_ASSET_ALIAS_CACHE` 验被 advertise 的 asset 文件存在，两处各查一次因为页面路径不复核磁盘）与三支用例：`test_the_delete_budget_cannot_be_spent_across_a_unit`（一 asset 两 alias、`COVER_CACHE_SWEEP_DELETE_LIMIT = 2`、`disk_has_reserve` mock False ⇒ 断言 `prune_cover_cache == 0` 且三件都在且无悬空）、`test_a_unit_that_fits_the_budget_is_reclaimed_whole`（额度 3 ⇒ `prune == 3` 且三件全删，反向防「预留」退化成「永不淘汰」）、`test_an_alias_the_volume_keeps_backs_the_whole_unit_off`（mock `_delete_cover_file` 只扣住第二个 alias ⇒ `prune == 1`、stuck alias 与其 asset 都还在、较新的第二个 unit 未被波及、无悬空）。既有夹具：`_publish(key, asset_key, size, asset_mtime, alias_mtime, asset_bytes)`、`_files()`、`self.now`、`self.config`，`setUp` 预置 `_last_cover_sweep` 让清扫保持 armed。活树实跑：`tests.test_cover_cache` Ran 90 OK、`CoverCacheSweepTests` 单类 Ran 14 OK。控制组（仓库外副本 `E:/fnAudio_r120_cp`，robocopy /E /MT:8 排除 .git、artifacts、references、tools 下的 android-sdk/sdk-cache/sdk-stage/apk-analysis/blutter/platform-tools/runtime/skill/browser-e2e node_modules 与 __pycache__，绝对路径排除以免同名碰撞；443.84 MB / 4224 文件 / 1735 目录 / 1.6 s）：Python `cd <cp>/src; PYTHONPATH=<cp>/src;<cp>/src/app/server; python -B -X utf8 -m unittest discover -s tests` ⇒ Ran 2405 tests in 107.099s OK (skipped=3)（比活树全量多出的 3 项正是本轮新增；skipped 比活树多 1 属预期差异：副本无 release evidence 故 `test_offline_verification_script` 跳过）；JS `<cp>/src` 下 69 支 test_*.js 逐个 node 退出码 0 ⇒ declared scripts 58 / js files 69 / passed 69 / failed 0。副本内不得直接跑 `tools/test_offline.ps1`：其末尾 `git diff --check` 在无 .git 的副本里必然 throw。变异矩阵 V1～V6（驱动脚本 `%TEMP%/r120x_matrix.py`，每轮先还原基线字节、变异、跑 `CoverCacheSweepTests` 整类、解析 FAIL/ERROR、再还原并核对 sha）：V1 整文件回退为 `%TEMP%/r120_backup/cover_cache.py.orig` ⇒ exit=1、红的恰是指名两支；V2 保留额度预留但恢复先删 asset 再删 aliases（摘掉尾部重复 reclaim 块）⇒ 指名 `volume_keeps_backs`；V3 预留改成 `deletes_left < len(aliases)`（少算 asset 那一笔，会花掉 2 个额度）⇒ 指名 `delete_budget`；V4 预留改成 `deletes_left <= len(aliases) + 1`（额度刚好也拒绝淘汰）⇒ 指名 `fits_the_budget`；V5 把 `stuck = True / break` 换成 `pass`（alias 失败仍删 asset）⇒ 指名 `volume_keeps_backs`；V6 `if stuck: continue` 取代 `break`（较新 unit 被连带淘汰）⇒ 指名 `volume_keeps_backs`。结果：SURVIVORS=0、每条 other_red 为空（没有一条变异靠无关用例凑数）、每次 restored=True、矩阵跑完控制组再绿 exit=0、副本与活树逐件 sha（含三份根文档与 SOURCE_MANIFEST）全 SAME 后删除副本，E 盘副本目录已不存在。
- 2026-09-20 — R120 用户答复登记（提交授权已到手，本轮只做最小范围提交）：用户在本轮明确答复第一项阻塞「授权提交 / `git add`」，并撤回「禁止提交、禁止 git add」这条持续约束；同时要求第二、三项阻塞（8 条决策项与三条桶归属争议条目）逐条讲清后再裁定。已授权不等于可盲提交：实测未跟踪项包含 `tools/apk-analysis/`（1.80 GB）与 `tools/runtime/`（1.43 GB）等外部下载件与自带 `.git` 的外部检出（其 `objects/pack/*.idx` 只读，正是 TODO 决策段 L1874（插入前 L1873）登记的那条），而 `.gitignore` 仍禁止修改、TODO L222（插入前 L221）用户已否决把这两个目录写进 `.gitignore`——`git add -A` 会把不可复现的 GB 级外部产物永久写进版本历史。故本轮采取「最小范围先提交、基线范围待裁定」：本轮 commit 只含 `src/app/server/cover_cache.py`、`src/tests/test_cover_cache.py`、三份根文档与 `SOURCE_MANIFEST.sha256`（其余 147 项跨轮修改与 424 个未跟踪源码文件仍留在工作树，等一次显式的基线提交）；已同时向用户呈交三种基线范围（A 只提交本轮涉及文件（即本方案）；B 提交全部源码/测试/文档/工具脚本但排除 GB 级外部产物与门禁日志；C 先单独裁定 `tools/apk-analysis` 与 `tools/runtime` 的处置再全量提交）。基线取证数字（本轮实测）：未跟踪 1127 条按组计 = tools/android-sdk 4 条 10242.5 MB、tools/apk-analysis 1 条 1845.2 MB、artifacts 644 条 1678.7 MB、tools/runtime 1 条 1462.6 MB、references 6 条 398.2 MB、.gradle-user 150.0 MB、tools/blutter 69.6 MB、tools/skill 50.1 MB、tools/platform-tools 16.7 MB，而真正有价值的未跟踪工作只有 src/tests 220 条 0.9 MB、src/app 204 条 0.5 MB、android-client/app 21 条 11.5 MB；已修改 147 条全部是源码与文档（src/app 40 条 1.7 MB、src/tests 50 条 1.4 MB、android-client/app 23 条 0.3 MB、三份根文档与清单）；已删除 6 条全在 `artifacts/0.1.174/` 之下。另注：本轮终跑因此是 `artifacts/offline-20260920-round183.log`——round182 是全绿终跑，但其 mtime 早于随后一次记录口径修订，按「日志必须晚于全部文档编辑」的规则重跑，旧日志保留不删。其余两项阻塞的答案待用户给出后按轮登记。
- 2026-09-20 — R119 二次接管复验与自我更正（并入本轮既有条目，不另立新项）：① 接管落笔前重取现场：分支 main、HEAD 仍是 d362047a082d5487a51471a1fabc220f784ae807、`git status --porcelain` 实测 1276（` M` 147 / ` D` 6 / `??` 1123）、staged 0、stash 0、无 MERGE_HEAD/CHERRY_PICK_HEAD/BISECT_LOG/REVERT_HEAD/rebase-merge/rebase-apply 残留 ✓ 上一会话的记录与磁盘一致：`src/tests/unwired/` 三件在位、两个旧路径不存在、两支测试已改指新路径、`SOURCE_MANIFEST.sha256` 699 条含 unwired 三条且不列旧路径 ✓ ② 修掉上一会话留下的落笔缺陷：PROJECT_CONTEXT.md L2 里「未提交工作」之后的「筛」被写成 U+B000 谚文字母加一个字符 0，按字节唯一定位替换回 U+7B5B（730826 → 730825 B，6117 行不变），并把复扫从「只查控制符」升级为「按码位段查」（谚文 / 假名 / 半宽兼容 / 私有区 / 代理点 / 控制符六段一起扫）：三份根文档异常码位实测 0，TODO 与 CHANGELOG 剩下的全角 ～ 与 ＝ 属正常标点 ✓ ③ 变异矩阵不信转述、在仍留在磁盘上的仓库外副本 `C:\path\to\fnAudio_r119_cp2` 里逐条重跑：控制组先绿（只跑 `test_orphan_module_retirement` 与 `test_source_manifest`，`Ran 14 tests` / `OK`），M1 三红、M2 三红、M3 两红、M4 两红（再并入 `test_alsa_player` 时改为加载期 FileNotFoundError、退出码 1）、M5 一红、M6 一红、M7 两红、M8 两红、M9 四红、M10 两红 ⇒ SURVIVORS=0 ✓ 每条按变异前字节快照还原，全部跑完复测控制组 `OK`，再逐件比对 `src/tests/test_alsa_player.py`、`tools/build_release.ps1`、`SOURCE_MANIFEST.sha256`、`src/app/server/playback_session_policy.py`、`src/tests/unwired/alsa_player.py` 与活树 sha 全 SAME、副本无残留，之后才删除副本（本条落笔时副本已不在磁盘上）✓ ④ 三处更正前一小时那版「R119 实现、变异与清单门禁」的杀手名单：其一，「M3 新造无消费者模块 → 只有总闸抓得到」不完整，实跑还红 `test_root_manifest_matches_authoritative_source_tree`——新建文件不在清单里，一般性清单断言同样会兜住；准确说法是「本轮新写的退役断言里只有总闸认得它，另有一般性清单断言作第二道」✓ 其二，「M9 丢掉 `import argparse`」的名单里 `test_the_moved_alsa_player_is_still_the_manual_cli_it_was` 其实没红（它数的是 `argparse` 字样，而 `argparse.ArgumentParser` 仍在），真红的是 `test_alsa_player` 的 `test_cli_rejects_invalid_rate_before_loading_alsa`、`test_cli_rejects_oversized_channels_before_loading_alsa`、`test_cli_rejects_oversized_device_before_loading_alsa` 加一般性清单断言 ⇒ 该形状断言对「删 import」不判别，记为事实不另立项，后续若要加强它，必须在加强之后重跑变异 ✓ 其三，凡改动被清单覆盖的文件（M7 改 `src/cmd/main`、M10 改清单自身、M3 新建文件），一般性清单断言都会连带变红，这是第二道闸生效而不是杀手归属，前一条记录里凡未点名的连带红一律按本句理解 ✓ ⑤ 收口复取证：清单再刷两次同 sha（699 条 / 68BC1D8203CBC1A79109091F75FB7D11C51C50AC94653C4E648C544B4C22DF8A = 幂等）✓ 逐文件抽查 13 个具名（含 unwired 三件、新判别测试、`server.py`、`app.js`）加随机 25 条全部 MATCH ✓ `tools/takeover_forensics.py --full` = 699 files / drift 0 / stale 0 / unlisted 0 / 退出码 0 ✓ 三份根文档 flat-run 逐条带日期、最新在前、整行不重复、三档最新日期同为 2026-09-20 ✓ 四桶 89 = 代码 25 + 设备 43 + 决策 8 + 台账 13，两两不相交、并集恰为全部 `- [ ] ` ✓ 设备段 43 条文本 sha256 前缀 4e0c6febe4bf9186 且段内不含 R119 字样 ⇒ 一行未改 ✓ 记录点名的锚逐条在磁盘成立：`build_release.ps1:214` 为 `/XD tests __pycache__`、`:394` 为 payload 拒 `tests`、`test_alsa_player.py:9` 与 `test_playback_session_contract.py:5` 指向 `unwired`、TODO L85 已关闭并带 R119 关闭注记、PROJECT_CONTEXT 模块表 L4893（本条初稿写的是 L4891，此后 PC 顶部又补记两条教训使表格整体下移两行，故按复测后的磁盘行号更正；复测必须在完成本轮全部文档插入之后做，否则点名锚点会自我失效）已是新路径、仓库外备份 `%TEMP%\r119_backup` 里两个模块与活树逐字节相同（两支测试的备份早于改指向，按预期不同）✓ ⑥ 本轮终跑在全部文档与清单定稿之后产出 `artifacts/offline-20260920-round179.log`，其数字只从实跑日志取、由下一轮接管核验抄录，本条不预填。 ⑦ 落笔后自查抓到两处需要续写的地方：其一，本条 ⑤ 里 PROJECT_CONTEXT 模块表的点名行号写成 L4891，而 PC 顶部补记两条教训后该行已下移到 L4893（写作当时成立、插入之后失效，属「行号不是条目身份」这条既有规则的适用面，不另立新项），已在本条 ⑤ 内按磁盘复测改为 L4893 并留下括注；其二，那次更正的 mtime 晚于 round179，会使「终跑日志晚于本轮全部文档编辑」这条自查失真，故已在更正之后复跑同一门禁产出 `artifacts/offline-20260920-round180.log`，磁盘实测 408146 B / 2539 行 / `Ran 2402 tests in 109.971s` / `OK (skipped=2)` / JS 结语 69 条（68 行 passed + 1 行 regression ok）/ 无 Traceback 无 FAILED / 驱动进程退出码 0，补写本条之后还要再复跑一次同一门禁，让最新日志的 mtime 重新晚于本条的落笔时间；那条日志的文件名与其中的数字都不在本条预填，由下一轮接管时从 `artifacts/` 目录取最新一份日志按磁盘抄录。
- 2026-09-20 — R119 接管核验（先取证后落笔）：① 分支 main、HEAD 仍是 d362047a082d5487a51471a1fabc220f784ae807（本轮不移动）；`git status --porcelain` 实测 1276 条（` M` 147 / ` D` 6 / `??` 1123）、staged 0、stash 0、无 MERGE_HEAD/CHERRY_PICK_HEAD/BISECT_LOG/REVERT_HEAD/rebase-merge/rebase-apply 残留 ✓ `.gitignore` 未碰；② ` D` 六条 = artifacts/0.1.174/ 四件 + R118 删的 `src/app/server/fnos_api.py` + 本轮移出发包目录后不再存在的 `src/app/server/alsa_player.py`；` M` 相对 R118 记录的 148 减 1、`??` 相对 1118 增 5 全部对得平：同一个 alsa_player 从「已跟踪且被改」变成「跟踪文件消失 + 未跟踪新路径」两形态，新增未跟踪为 `src/tests/unwired/` 三件、`src/tests/test_orphan_module_retirement.py` 与本轮门禁日志；③ 写盘前 `R119` 字样在 TODO.md / CHANGELOG_AI.md / PROJECT_CONTEXT.md 命中数分别为 0 / 0 / 0 ⇒ 上一模型止于磁盘、一笔记录都没落，本轮从它的实现现场续写（数字全部重测，不按转述写账）；④ 磁盘现场逐项点名复核：`src/tests/unwired/alsa_player.py`（5695 B / 178 行）、`playback_session_contract.py`（4250 B / 138 行）、`README.md` 三件在位、`src/app/server/` 下两个旧路径已不存在、两支测试的指向已改到新路径，移动前后 sha256 与仓库外备份 `%TEMP%\r119_backup` 逐字节相等；⑤ 上一轮 R118 终跑 `artifacts/offline-20260920-round178.log` 本轮从磁盘重读实测 406159 B / 2529 行 / `Ran 2392 tests in 99.127s` / `OK (skipped=2)`（不是引用交接摘要）；⑥ 清单文件是仓库根的 `SOURCE_MANIFEST.sha256`（不在 `tools/` 下，此处更正上一份交接的口误），本会话开头实测 699 条 = R118 记的 697 − 2 个旧路径 + 4 个新增（两个新路径 + README + 新判别测试）；⑦ 上一份交接把投送并发与 `addQueueAndPlay` 两条写成 L65/L66，磁盘实为 **L66/L67**，本轮按实测取值。
- 2026-09-20 — R119 关闭 TODO L84 之取证（条目原话：「取证后三选一……不要凭印象动手」）：引用语料 = 400 个生产文件（`src/app` 全部 + `src/cmd/main` + `src/wizard` + `src/config` + `src/manifest` + `tools` 一层的 .py/.ps1/.sh + `android-client/app/src/main`；排除 `test_*`、`vendor`、`build`、`.gradle`、`.media3-inspect`、`.idea`、`node_modules`、`dist`、`runtime`、`apk-analysis`、`__pycache__` 与 >3 MB 二进制），`alsa_player` 与 `playback_session_contract` 两个词 **0 命中** ✓ 第二链（提交态）：`git grep alsa_player HEAD` 只命中三份根文档，`playback_session_contract` 在提交态根本不存在（未跟踪），`git log --all -S` 只有 baseline 一处 ✓ 第三链（打包与设备）：`tools/build_release.ps1` 递归暂存 `src` 并只对八个具名 payload 文件断言，两个名字都不在其中；`src/cmd`、`tools/*.ps1`、设备侧脚本同样 0 命中 ✓ 总闸扫描给出关键事实：移动前 `src/app` 下 192 个 .py 中零引用者**恰好只有这 2 个**、移动后 190 个里 0 个 ⇒ 「接回真实调用点」不是功课不够，而是从来没有调用点可接，硬接等于新造功能 ✓ 删除一路的代价实测不可接受：`alsa_player.py` 工作树 178 行对 HEAD 提交态 95 行（净 +83 行未提交改动，仓库内无第二副本，删了找不回）；`playback_session_contract.py` 未被 git 跟踪，且正是 TODO「Android 等价 MediaSession 持续目标」6 条设备项所等的 participant / generation / engine epoch / keep-alive / command ticket 契约 ✓ 名字易混的一面单独取证：`playback_session_policy.py` 与 `playback_session_projection.py` 仍被 `server.py` 引用，属活模块，本轮一字未动，并把这一点写成判别断言（M8 就是「迁移过头」的变异）。
- 2026-09-20 — R119 实现、变异与清单门禁：实现 = 两模块整体移入新建的 `src/tests/unwired/`（附 `README.md` 说明为何留而不删）+ `test_alsa_player.py:9` 的 `MODULE_PATH` 与 `test_playback_session_contract.py:5` 的 `sys.path.insert` 改指新目录（LF、无 BOM，用例数 10 / 7 不变，全量 2402 项不减一项）+ 新增 `src/tests/test_orphan_module_retirement.py`（249 行 / 10 项 / 单跑 4.3 秒）；选「移入一个名为 tests 的目录」是因为它同时满足两个硬前提：`build_release.ps1:214` 的 `/XD tests __pycache__` 按目录名剔除（payload 再出现 tests 就 throw，`:394-395`），而 `update_source_manifest.ps1` 仍把它们纳入逐文件哈希；判别测试双向设计：拦复活（总闸、离开发包树、两支测试跟随、打包/设备脚本不点名、清单列新不列旧）也拦改过头（手工 CLI 形状 shebang/argparse/`__main__`/四个函数、契约可载入并能真跑 `iter_pcm_chunks`、`/XD` 与 payload 守卫在位、两个活 session 模块未被搬走）。变异证明（仓库外副本 `E:/fnAudio_r119_cp2`，robocopy 15759 文件 / 3.024 GB，排 `.git`、`.android-avd`、`.gradle-cache`、`.gradle-user`、`references`、`tools/runtime`、`tools/android-sdk*`、`tools/apk-analysis`、`tools/blutter`、`tools/platform-tools`、`node_modules`、`build`、`dist`、`__pycache__`）：控制组先绿 = Python `Ran 2402 tests in 107.247s` / `OK (skipped=2)` / rc 0、69 支 `test_*.js` 逐个 node 退出码全 0（pass=69 fail=0，需以 `src` 为 cwd 而不是 `src/tests`，否则 43 支会因相对路径自红） ✓ M1/M2 把两模块放回 `src/app/server` → `test_both_retired_modules_are_out_of_the_packaged_tree` + 总闸 + `test_root_manifest_matches_authoritative_source_tree`；M3 新造一个无消费者模块 → 只有总闸抓得到；M4 测试改回旧路径 → `test_the_two_test_modules_follow_their_module_and_not_the_package`（另 `test_alsa_player` 自身加载失败）；M5 削弱 `/XD tests` → `test_packaging_excludes_any_tests_directory_and_still_names_no_retired_file` + `test_script_uses_a_temporary_copy_of_the_authoritative_source_tree`；M6 payload 守卫改拦 vendor → 同上；M7 `src/cmd/main` 点名 alsa_player → `test_no_packaging_or_device_script_references_the_retired_names`；M8 把活模块 `playback_session_policy.py` 也搬进 unwired（迁移过头）→ `test_the_live_session_modules_are_untouched_by_the_retirement`；M9 移动后丢掉 `import argparse` → `test_the_moved_alsa_player_is_still_the_manual_cli_it_was` + `test_alsa_player` 的三支 CLI 测试；M10 从清单删掉 unwired 三条 → `test_the_manifest_hashes_the_new_paths_and_drops_the_old_ones`；SURVIVORS=0，每条还原后控制组失败集合恰为空集，副本已删 ✓ 一处方法学自纠（并入本条，不另立项）：第一版驱动脚本按「变异后路径」回找备份，M8 这种移动型变异找不到备份就抄底删除，于是副本从 M9 赻永久少一个活模块、控制组假红、M9/M10 的杀手名单里深进一条不该有的 session 断言；本轮改为变异前快照字节、跑完按快照还原，重跑 M8/M9/M10 与 M1～M7，控制组零失败之后才认账 ✓ 清单刷新为 699 条并连跑两次同 sha；门禁终跑见 `artifacts/offline-20260920-round179.log`。
- 2026-09-20 — R118 接管核验（先取证后落笔）：① 分支 main、HEAD 仍是 d362047a082d5487a51471a1fabc220f784ae807（本轮不移动）；`git status --porcelain` 实测 1271 条（` M` 148 / ` D` 5 / `??` 1118）、staged 0、stash 0、无 MERGE_HEAD/CHERRY_PICK_HEAD/BISECT_LOG/rebase-merge/rebase-apply 残留 ✓ `.gitignore` 未碰 ✓ ② ` D` 五条里 4 条是 artifacts/0.1.174/ 的历史遗留，第 5 条正是本轮删除的 tracked 文件 `src/app/server/fnos_api.py`；与 R117 记录的 1269 相差 2 条已逐项对齐：本轮新增未跟踪 3 个（round174 终跑日志、src/tests/test_fnos_route_retirement.py、round175 预跑日志）减去本轮删除的未跟踪 `src/tests/test_fnos_api.py` = +2 ✓ ③ 插入前 `R118` 命中数：TODO.md 3、CHANGELOG_AI.md 0、PROJECT_CONTEXT.md 0 ⇒ 上一模型止于 TODO.md，本轮从文档续写，代码/测试/清单不重做 ✓ ④ 计数账对得上：R117 终跑 artifacts/offline-20260920-round174.log = Ran 2397 / OK (skipped=2)，本轮预跑 round175 = Ran 2392 / OK (skipped=2)，2397 − 9（删 test_fnos_api.py 的 9 项）− 8（删只测死函数的 8 项）+ 10（新 test_fnos_route_retirement.py）+ 2（新 404 行为钉）= 2392 ✓ ⑤ 本会话按门禁同口径（cwd=src，PYTHONPATH=src;src/app/server）复跑单模块全绿：test_fnos_route_retirement 10、test_cgi_proxy_auth 32、test_cover_cache 87、test_app_lifecycle_scripts 23、test_http_integration 80、test_source_manifest 4、test_takeover_forensics 10。
- 2026-09-20 — R118 关闭 TODO L84（`if False and` 恒假路由组共 7 处）之取证：条目给的两条路里，「用配置开关代替恒假字面量」在本项目打不开。按提交态 HEAD 复取——`if False and` 在 server.py 恰 3 处（L706/L996/L1026）、在 cgi_proxy.py 恰 4 处（L308/L314/L318/L342），合计 7 处与条目原话一致 ✓ 三个 server 块调用的 `get_shared_accessible_folders`（HEAD L709/L998）与 `del_shared_accessible_folder`（HEAD L1034）全文只出现这三处且全在块内 ✓ `from fnos_api import FnosApiError, call_trim_api` 在 HEAD 只有 L106 一行，`call_trim_api` 除该行外零使用，`FnosApiError` 只被块内三个 except 用（HEAD L711/L999/L1035）⇒ 开关置真不会启用功能，只会把「看着可用的死路由」换成必崩的 NameError ✓ 于是取第一条路：正式关掉 = 删块 + 删只被它引用的入口与其测试。
- 2026-09-20 — R118 删除量与保留面（前后差；前值取本轮开工实测）：server.py 3390 → 3327（−63：GET 块 + 两个 POST 块 + 死导入组内 2 名）、cgi_proxy.py 727 → 509（−218：`import socket` + 4 个孤儿常量 + 2 个孤儿小函数 + 4 个只被死块调用的函数 + 4 个恒假路由块）、src/tests/test_cgi_proxy_auth.py 626 → 477（−149，8 个只测死函数的测试，40 → 32 项，service_port 四支与真活跃前缀测试原地保留）、tools/ui_e2e_fixture.py 322 → 320（−2，fnos 假分支）✓ 整文件删除 `src/app/server/fnos_api.py`（143 行，tracked）与 `src/tests/test_fnos_api.py`（98 行 / 9 项，原本未跟踪、删了无法从 git 恢复）⇒ 两份备份移到仓库外 C:\path\to\fnAudio_r118_deleted_backup（仓库外路径不进 SOURCE_MANIFEST，也不进门禁覆盖集）✓ 删后活链复验：`if False and`、`/api/fnos`、`auth-debug`、`shared-folders`、`fnos_api` 与 6 个死函数名在 server.py / cgi_proxy.py / ui_e2e_fixture.py 全部 0 命中 ✓ `fnos` 只剩 server.py L754/L755/L1573/L1668 四处合法注释与 cgi_proxy.py L74/L331/L399 三处（L331 = `"fnos-token"` cookie 名）✓ 四个改动文件 py_compile 全过 ✓ 说明：HEAD 提交态这四位只有 2348/417/78/207 行，与工作树前值不同是 118 轮不提交的既有事实，本轮前后差不因此改变。
- 2026-09-20 — R118 关闭 TODO L87（covers/assets 聚合上限）＝重复登记式证伪，不是把事做完：条目四项要求逐条落到磁盘——过期负标记 / 崩溃残留 temp / 等待别名的资产 / 无别名资产宽限 = `test_cover_cache.py` L1485、L1498、L1518、L1525 ✓ 字节预算只淘汰最旧单元 = L1546 ✓ 磁盘压力早于预算也清理 = L1575 ✓ 支撑代码 `cover_cache.py` L570（`COVER_ASSET_ORPHAN_GRACE_SECONDS`）、L731（宽限判断）、L734（`cover_cache_max_bytes` 预算）✓ 唯一没实现的「总条目数封顶」自 R75 起就是顶部 L33（插入本轮记录前的 L32）那条，仍 `- [ ]`、一行未动 ⇒ 本轮消掉的是同一件事的第二处登记，未完成要求总数不减、也不需要新立条目；关闭判据（关登记而非关要求）留给用户复核。代码桶 27 → 26。
- 2026-09-20 — R118 新增判别测试：`src/tests/test_fnos_route_retirement.py` 199 行 / 10 项（LF、无 BOM、未跟踪）——双向设计，一半拦死代码复活（AST 找常量假条件与字面量、`/api/fnos`+`shared-folders`+`auth-debug`+`trim.file.` 端点串、6 个死函数名、4 个孤儿常量、入口文件与两个导入名、SOURCE_MANIFEST 覆盖集，扫描排除集只允许本文件），一半拦删过头（活链锚点：`/api/health`、`/api/config/library`、`/api/playback/targets`、`serve_static`、fixture 的 `/api/` 兜底、`fnos-token`、`trim_token`、`src/cmd/main` 的 `TRIM_API_TOKEN` 转发必须还在）✓ 另在 `test_http_integration.py`（1468 → 1498 行、78 → 80 项）加两条 404 行为钉：`test_the_retired_fnos_get_routes_answer_like_any_unknown_path`（GET 三条 → 404）与 `test_the_retired_fnos_posts_still_reach_the_terminal_not_found`（两条 POST → 404 且体为 `{"error": "not found"}` 且 `commit_config_update` 零调用）✓ 落点为磁盘实取：GET 走 `serve_static`（server.py L1550）→ L1569 `isfile` 失败 → L1570 `send_error(404)`；POST 落 `handle_post` 尾 L1523 `send_json({"error": "not found"}, 404)`。
- 2026-09-20 — R118 仓库外副本变异证明（C:\path\to\fnAudio_r118_cp，1608 文件）：控制组先绿——本轮早段实跑 Python Ran 2392 / OK (skipped=3)（副本无 .git 故比活树多 1 条 skip，与 R117 同现象）、69 支 `test_*.js` 逐个 node 退出码全 0 ✓ 变异矩阵 V1～V9 全部被杀且逐条命中指名杀手，SURVIVORS=0，收尾 CONTROL RESTORED=True ✓ 本会话先比对副本与活树 8 个关键文件 sha 全 SAME，再独立复跑一次驱动，V1～V9 判定与首轮逐字相同 ✓ 三条最有信息量的：V1（以活条件复活 GET 路由）同时被源扫描与本轮新增的 404 行为钉抓住；反向 V5（删活的 `trim_token`）由正向断言加 7 支 cgi 测试杀；V6（删 `src/cmd/main` 的 `TRIM_API_TOKEN` 转发）由 `test_main_starts_server_without_second_shell_parsing` 杀 ⇒ 这套断言既拦复活也拦删过头，不是单向的字符串存在性检查。
- 2026-09-20 — R118 分桶与反增长（按 R113 书面规则以节标题+文本锚定从磁盘重算）：全文件 `- [ ] ` 实测 90（`- [x] ` 1443）⇒ 90 = 代码 26 + 设备 43 + 决策 8 + 台账 13 ✓ 代码 26 = 顶部段 23 条（L32,L33,L65,L66,L67,L70,L83,L84,L95,L97,L99,L106,L110,L113,L134,L144,L147,L148,L152,L153,L170,L214,L220）+ 三条具名散条目 L541（持续审查未完成范围）/ L1815（Chromaprint-AcoustID）/ L1833（继续按可测试边界拆分）✓ 设备 43 = `## 宿主 MediaSession`(10) + `## Android 等价 MediaSession 持续目标`(6) + `## P2：部署与外部系统验收`(3) + `## P0：外部验收（离线不可验证）`(23) + `# 2026-09-01 飞牛 APP 私有播放会话（研究结论）`(1) ✓ 决策 8 = `## 需要项目负责人决策`(L1866..L1873) ✓ 台账 13 = L789,L2070,L2089,L2092,L2097,L2098,L2103,L2117,L2118,L2130,L2135,L2136,L2144 ✓ 四桶两两不相交、并集恰为 90 ✓ 本轮净关闭 2 条、新立可离线代码项 0 条 ⇒ 代码桶 28 → 26、开放 92 → 90 ✓ 设备段一行未改 ✓ 历史计数并存不合并：目标正文快照 155 = 64+82+9、R99 实测 115 = 51+43+8+13、R116 记 95、R117 记 94、本轮 90。
- 2026-09-20 — R118 清单与门禁：SOURCE_MANIFEST.sha256 用 tools/update_source_manifest.ps1 刷新为 697 条（698 − 2 个被删文件 + 1 个新测试文件），连跑两次文件 hash 相同 = 幂等 ✓ 清单自身 sha256 = 51530E5EAD5263718C6CA9888FA89401985AC8E3D4CA7B0E77237B9C6E1C27AA ✓ 逐文件抽查：server.py、cgi_proxy.py、test_cgi_proxy_auth.py、test_fnos_route_retirement.py、test_http_integration.py、cover_cache.py、test_cover_cache.py 全部与清单 MATCH；`tools/ui_e2e_fixture.py` 本就不在覆盖集（清单只含 src/ 与 android-client/），文档三件与 tools/ 同理不受本轮编辑影响 ✓ 门禁实跑记录（数字全部取自磁盘日志，不做推算）：文档编辑前的预跑 `artifacts/offline-20260920-round175.log` = Ran 2392 tests in 100.381s / OK (skipped=2) / 2529 行 / 68 条 JS `… passed` 结语（JS 套件 69 支，68 支打结语，另 1 支打 `… regression ok`）✓ 上一模型用 Start-Process 把标准输出与标准错误分开重定向启动终跑 round176，而 unittest 的结果行写在标准错误流，于是留下 `…round176.log`（79 行，全部标准输出）与 `…round176.err.log`（2450 行）两份非标准产物；两份按行相加恰为 2529 行，实据 Ran 2392 tests in 101.065s / OK (skipped=2) / 2387 行内联 `... ok` 加 3 行独立 `ok` = 2390 项通过 + 2 skipped / JS 69 支全过 / 末步 `git diff --check` 只有 6 条 CRLF 提示，全文件无 Traceback、无 FAILED、无 throw ✓ 但该次未带 -Wait -PassThru，进程退出码已不可回收，不得把它称作 exit 0 ✓ 为补上退出码，本会话按同一脚本、两条流合并写单文件重跑 `artifacts/offline-20260920-round177.log` = 2529 行 / Ran 2392 tests in 99.105s / OK (skipped=2) / 2378 行内联 `... ok` 加 12 行独立 `ok` = 同样 2390 项通过 + 2 skipped / JS 69 支全过 / **EXITCODE 0** ✓ 两次各自的内联与独立行合计都是 2390，差异只是双流交错时的落行位置，不是测试数量变化 ✓ 三份根文档与清单定稿后再跑一次 round178 作为 mtime 晚于全部文件编辑的终跑见证，其数字只从实跑日志取，本条不预填 ✓ 收口复取证：`tools/takeover_forensics.py --full` = 697 files / drift 0 / stale 0 / unlisted 0 / exit 0；三份根文档均 CR 0、无 BOM、控制符归零、结尾换行在（TODO 2203 行 / CHANGELOG 6687 行 / PROJECT_CONTEXT 6115 行）；TODO 开放项复测 `- [ ] ` 90、`- [x] ` 1443，与四桶算式一致 ✓ `git status --porcelain` 本条落笔时实测 1274（` M` 148 / ` D` 5 / `??` 1121），较开工记录的 1271 多出的 3 条全是本轮新增的 artifacts 门禁日志，终跑 round178 会再 +1 ⇒ 差额只来自日志文件本身，` M` 与 ` D` 一行未变 ✓ 收尾：仓库外变异副本 `C:\path\to\fnAudio_r118_cp` 与 %TEMP% 里本轮全部辅助脚本及输出删除；被删的 `fnos_api.py`（143 行）与 `test_fnos_api.py`（98 行）备份保留在仓库外 `C:\path\to\fnAudio_r118_deleted_backup`；全仓 `.new/.orig/.rej` 仅剩 tools/runtime 下两个 vendored 第三方文件 ✓ HEAD 仍 d362047a082d5487a51471a1fabc220f784ae807，未提交、未 git add、未碰 .gitignore。
- 2026-09-20 — R118 自我更正三处（都由磁盘复取证否证上一版记录）：其一，本轮写 TODO 记录时把备份路径里的 `\f` 当成 Python 转义落进了正文，磁盘实据是 TODO.md 两处 U+000C 控制符（L2 与 L85），使同一条记录在按换行切分的读法里被劈成两行；本会话按字节定位改回字面反斜杠，并全库复扫确认三份根文档 U+000C 归零、其它控制字符 0 ✓ 其二，同一处「死块调用只出现在块内三处（L1042/1456/1492）」是删除前工作树行号，删除后不可复核，已按提交态 HEAD 改述为 L709/L998/L1034 并注明前值不可复核 ✓ 其三，「`fnos` 只剩 cgi_proxy L331 一处」不完整，磁盘实为 L74/L331/L399 三处，TODO.md 两处引用与 `test_fnos_route_retirement.py` 文档字符串里的旧行号（132 → HEAD L106）已同步更正 ⇒ 教训：转述与自述里的行号一律当作待证，写进 Python 字符串的路径必须按字面处理。
- 2026-09-20 — R117 接管核验（先取证后落笔）：① 工作树 git status --porcelain 实测 1269 条、staged 0、stash 0、  无 MERGE_HEAD/CHERRY_PICK_HEAD/rebase 目录，分支 main、HEAD 仍是 d362047a082d5487a51471a1fabc220f784ae807（本轮不移动）；  ② 最新门禁日志仍是 artifacts/offline-20260920-round173.log（本轮结束时才产出 round174）；  ③ 三份根文档 R117 出现次数为 0，说明上一轮在「写完取证脚本」处中断、未动过磁盘；  ④ 四桶重算 94 = 代码 30 + 设备 43 + 决策 8 + 台账 13（按节标题分桶，两两不相交、并集等于开放项全集），  与 R116 记的 95 = 31 + 43 + 8 + 13 相差的正是 R116 自己关掉的那一条；  ⑤ 历史计数继续并存不合并：目标正文快照 155 = 64 + 82 + 9、R99 实测 115 = 51 + 43 + 8 + 13、  R116 记 95、本轮实测 94；⑥ python -B -m unittest tests.test_library_sqlite 单独跑绿，测试文件未被写坏。
- 2026-09-20 — R117 关闭 TODO L130（八条组表排序索引是否还被计划使用）：取证方法是「按真实代码路径逐方向 EXPLAIN QUERY PLAN 归属」，  因为 SQLite 自己不报告哪条索引从没被用过，且本项目不做 ANALYZE、不发 PRAGMA optimize（全仓 grep 证实），计划稳定可复现。  夹具是 5 组 × 4 张组表的小库，页边界刻意切在 Alpha/alpha 大小写簇之后，让游标续页的两条语句都真正执行；  用连接 trace 回调抓语句再逐条看计划。归属矩阵四张组表同形：首屏与翻页页读 ASC 只点 idx_*_name_nocase_asc、DESC 只点 _desc；  续页第一条（组内尾，name = ? AND tie > ?）两个方向都点 _desc——次键恒为 name ASC，与浏览方向无关；  续页第二条（后续组范围 name COLLATE NOCASE >|< ?）ASC 点 _asc、DESC 点 _desc；  带搜索的 JOIN 页用主键 autoindex 点查组表、owner 过滤 albums 根本不读组表（走 idx_tracks_artist/composer），  两者 ORDER BY 都在命中集上做 TEMP B-TREE ⇒ 八条索引没有任何一条是死的，也没有任何一条可以靠这两条路径解释掉。
- 2026-09-20 — R117 更正索引成本的测法（同一条目要求「成本是否仍成立」）：逐条独立副本差分给出每条 +3,244,032 B = 3.094 MB  = 32.4 B/组（100k 组、平均 20 字节组名），八条数值完全一致；换成 10.8 字节短名则每条 +2,400,256 B = 2.289 MB = 24.0 B/组。  条目原话「100k 专辑约 6.7 MB」在本方法学下对应单表两条 6.19 MB，量级与结论都仍成立。  但 R116 用的「DROP 全部→VACUUM→逐条 CREATE→VACUUM」累计差分对逐条拆分不可信：同一条索引作为第一批测得 3.09 MB、  作为后续批测得 4.41 MB，两遍反向复跑一致，原因是 VACUUM 会重排已存在对象的页。配对总额 +6.5 MB/100k 组仍然成立，  作废的只是它的逐条拆分。本机 SQLite 3.50.4 无 dbstat 模块，差分是唯一可行手段。
- 2026-09-20 — R117 关闭 TODO L143（浏览游标仍是前缀范围 + OFFSET 的老形状）：前提与要求两半都已被后续轮次实现而条目未翻。  browse_cursor_where 在两个服务端模块源码 0 命中（补上本轮那条禁止清单之后，src 全树唯一还保留该字面量的文件就是 L1407 的清单自己）；library_browse_cursor_policy.py 的 __all__ 只剩 encode/decode_browse_cursor、  browse_cursor_page、browse_cursor_group_tail_where、browse_cursor_next_group_where；  三个续页调用点（owner 过滤 albums、通用组页、folders）全部经 _browse_cursor_rows() 的两条单比较读，  query_library_groups() 对游标页强制 offset=0，「先索引后形状」里说的索引条件也已成立。
- 2026-09-20 — R117 新增两条判别测试（src/tests/test_library_sqlite.py，文件 3275 → 3491 行、模块 132 → 134 项）：  L1266 test_every_group_ordering_index_is_named_by_a_real_browse_path 把上面整张归属矩阵写死——四张组表 ×   {首屏 asc、首屏 desc、续页 tail asc/desc、续页 next asc/desc、searched 页、owner 过滤} 全部用 EXPLAIN QUERY PLAN 断言  「点名的索引恰好等于该格期望的那一条」且「不得出现 TEMP B-TREE」，searched 与 owner 两格反过来断言「不得点这八条中的任何一条」，  最后再加两条闭合断言：八条索引名字仍在 sqlite_master 里、被点名集合必须等于全八条。  L1407 test_no_browse_continuation_falls_back_to_the_offset_scan_shape 钉的是 L143 剩下的可判别半边：  旧符号 browse_cursor_where 不许回到两个服务端模块源码里，四个组视图 × 两方向与 folders × 两方向的续页都必须恰好两条读语句、  且语句里既不许出现 OFFSET 也不许出现 OR（客户端硬塞非零 offset 也一样）。
- 2026-09-20 — R117 仓库外副本变异证明（E:/fnAudio_r117_cp，robocopy 排除 .git/.android-avd/.gradle-cache/.gradle-user/  references/artifacts 与 tools 下的 android-sdk*、apk-analysis、runtime、blutter、skill、platform-tools 和两个 zip，  保留 libgojni.so、gradle-wrapper.jar 与 tools 下 9 个 .sh）：控制组先绿，Python Ran 2397 tests OK (skipped=3)、  JS 69 支 0 失败（主树同口径 69 支 0 失败；副本多出的那 1 个 skip 是既有环境差异）。  十三条变异全灭、无存活：V1～V8 逐条摘掉八条组表排序索引，每条都由本轮新测试点名杀死  （同时被 test_group_tables_carry_case_insensitive_ordering_indexes、test_browse_cursor_continuations_keep_their_index_seek_plan、  test_benchmark_enforces_bounded_sqlite_pagination 兜住）；V10 把 albums 索引的 COLLATE NOCASE 摘成裸列，由新测试杀死；  V11 把旧符号 browse_cursor_where 重新导出，**只**被 L1407 新测试杀死；V12 把两读拼回一条 OR 读，被 12 条测试杀死（含本轮两条）；  V13 绕过游标分支退回 OFFSET 分页，被 9 条测试杀死（含本轮两条）；V9 让组内尾谓词跟随 sort_dir，由既有两条 policy 测试与  test_browse_cursor_pair_shares_one_page_budget 杀死——诚实说明：V9 不由本轮新测试杀死，本轮测试断的是计划归属而不是谓词方向。  每条变异跑完后逐文件 sha256 与变异前一致，副本文件未被留脏。
- 2026-09-20 — R117 清单与门禁：SOURCE_MANIFEST.sha256 已用 tools/update_source_manifest.ps1 刷新，仍 698 条（本轮只改内容不改覆盖集），  src/tests/test_library_sqlite.py 逐文件抽查 sha256 = CCEC9D139B10DE7D8E829DDEDD4B464FFF3EB825A08173E6666EA4724A04E658 与清单一致（本条写下之后，校验器按「点名的锚点必须在磁盘成立」否证了 L5 与 TODO L144 注记里把 0 命中的范围说成整个源码树（含测试）的措辞——补上新测试之后，该符号的字面量只剩那条禁止清单自己还在写，于是三份文档与该测试文件注释里的同一措辞一起收紧成「两个服务端模块源码 0 命中」，并重新刷新清单；这里引用的 sha256 是改正后的值，改正只动文字与注释、不动行数（该测试文件仍是 3491 行））；  三份根文档不在清单覆盖集内（TODO/CHANGELOG/PROJECT_CONTEXT 命中 0 条），所以本轮文档改动不改清单计数。  本轮终跑门禁 tools/test_offline.ps1 落在 artifacts/offline-20260920-round174.log：写下本条时该日志尚未产出，  门禁在文档与校验器之后执行，其结果（用例数、JS 通过数、exit 码、分类器 moves、开放项与可离线代码项计数）在收尾汇报里给出，不在此预告。
- 2026-09-20 — R116 接管核验（先取证后落笔）：① 工作树 `git status --porcelain` 实测 1268 条、staged 0、stash 0、无 MERGE_HEAD/CHERRY_PICK_HEAD/BISECT_LOG/REVERT_HEAD/rebase-merge/rebase-apply 残留 ✓ HEAD 仍 d362047a082d5487a51471a1fabc220f784ae807 未动 ✓ `.gitignore` 未碰 ✓；② 全树扫 `.new/.orig/.rej` 只命中 tools/runtime/gomodcache 与 gomodcache-clean 里 modernc.org/libc 自带的 surface.new，两者都是未跟踪的依赖缓存目录（`?? tools/runtime/gomodcache/`），不属改动面 ✓；③ 三份根文档 `splitlines()` 行数 TODO 2200 / CHANGELOG 6662 / CONTEXT 6102，控制字符 0，R116 出现 0 次（本轮尚未记账）✓；④ 上一手摘要报的行数是 2201/6663/6103，口径是把末尾换行也切成一段，差的 1 是文件末尾换行，两者不矛盾，本轮统一到 `splitlines()` ✓；⑤ 四桶独立复算 = 95 = 代码 31 + 设备 43 + 决策 8 + 台账 13，与 R99 的 115=51+43+8+13 和目标正文快照 155=64+82+9 三组数字并存不合并，旧快照仍留在目标正文里未改；代码 31 = 顶部段 28 条（L29,30,62,63,64,67,80,81,82,85,92,94,96,103,107,110,129,131,141,142,144,145,149,150,157,167,211,217）加三条散条目（L538 持续审查未完成范围、L1812 Chromaprint、L1830 按可测试边界拆分）✓ 设备 = L801 段 10 + L874 段 6 + L1814 段 3 + L1833 段 23 + L2053 段 1 = 43 ✓ 决策 = L1863-L1870 = 8 ✓ 其余 13 条为历史台账。
- 2026-09-20 — R116 关闭内容：TODO「2026-09-17：组/目录浏览游标拿不到索引 seek（本轮只测量、未改动）：`browse_cursor_where()` 形状已经正确，缺的是索引——组表没有任何 name 排序索引，`folders` 只有 `(root,parent,name)` 且 `name` 是二进制排序…需同时给出组表 `(name COLLATE NOCASE, name)` 与 `folders(root,parent,name COLLATE NOCASE)` 两条索引并评估写放大」（原 L157，插入本轮记录后在 L158）。关闭方式＝取证证伪，与 R99 的 :61 同型：条目写下时缺的六条索引已经在后续轮次里悄悄进了 `ensure_library_schema()`，条目本身一直没翻。磁盘取证：src/app/server/library.py L2260-2267 是四张组表的 `(name COLLATE NOCASE ASC|DESC, name ASC)` 八条表达式索引，L2377-2384 是 `folders` root-scoped 对 `(root, parent, name COLLATE NOCASE, path)`，L2394-2401 是 parent-only 对 `(parent, name COLLATE NOCASE, path)`，L2402 DROP 掉二进制排序的遗留 `idx_folders_root_parent_name`。
- 2026-09-20 — R116 唯一真实缺口与判分层：六条索引在，写放大没评估过，而且「游标续页这两条语句的计划」从来没被钉过——普通页的计划早在 test_library_sqlite.py L1444-1462、L2190-2201 与 test_large_library_benchmark.py L83-94、L142-159 钉死，续页一直只靠结果等值和语句计数间接守护。本轮新增 `test_browse_cursor_continuations_keep_their_index_seek_plan`（L1142 起，文件现 3275 行，12 个 subTest）：对 albums/artists/composers/genres 四张组表双向、`folders` root-scoped 与 parent-only 双向，先用 `next_cursor` 拿续页游标，再用 `set_trace_callback` 抓到续页真实发出的两条单比较 SELECT，逐条 `EXPLAIN QUERY PLAN` 断言「计划里必须出现点名的 `idx_*_name_nocase*` 索引」且「零 USE TEMP B-TREE」。项目不做 ANALYZE 也不发 PRAGMA optimize（全仓 grep 证实），所以取证库与真库的计划条件一致。
- 2026-09-20 — R116 取证账（100000 组 / 50000 同级目录 / page=120，python 3.14.6 + SQLite 3.50.4 + page_size 4096，连跑两遍形状键集相同、temp 标记 18/18 一致）：带索引时 tail/next 两跑合并落在 0.009~0.211 ms，普通页 group_page@90000 为 3.771/3.910 ms（第一跑）与 4.294/3.937 ms（第二跑）、folder_page_root@25000 为 6.112/5.963 与 6.638/5.976、folder_page_ponly 为 6.361/4.921 与 4.351/6.495，18/18 条 temp=0；摘掉这六条索引后 18 条里 14 条退回 `USE TEMP B-TREE FOR ORDER BY`，group_page 43.431/91.846、group_next 7.0~22.8、folder_page_root 58.341/142.546、folder_next_root 21.4~45.8、folder_page_ponly 48.322/150.166、folder_next_ponly 14.3~35.4 ms；剩下 4 条走主键 autoindex（temp=0）的是 group_tail 2.593/2.621 与 folder_tail_root 10.674/10.567 ms，folder_tail_ponly 12.9~18.9 ms 属那 14 条。两跑合并的最大漂移 85%（0.110→0.204 ms，亚毫秒档）与 32%（4.921→6.495 ms）。更正上一手摘要的说法：不是「摘索引后全部退化为 temp b-tree」，是 14/18。
- 2026-09-20 — R116 写放大与插入常数项：库体积 base 32.4 MB → 加两条组索引 38.9 MB（+6.5 MB，摊到 10 万组是 68 B/组）→ 再加四条目录索引 80.3 MB（+41.5 MB，摊到 5 万目录是 869 B/目录），建索引 0.09 s / 0.29 s（第二跑 0.08 s / 0.30 s），两跑 SIZE 行逐字相同。测量手段有硬限制：本机 SQLite 没有 `dbstat` 模块，只能 DROP→VACUUM→CREATE→VACUUM 差分，不 VACUUM 会测成 +0.0 KB。插入代价两次探针不一致：一次 20k 行 0.0023→0.0037 ms/行（+0.0014 ms/行，每 10 万行 +0.14 s），另一次 +0.0004 ms/行 ⇒ 文档按最坏值 +0.0014 ms/行入档并并列交代两次数；亚毫秒档探针必须多次交替取最坏值，单次读数不可采信。
- 2026-09-20 — R116 并列键探针（回答「为什么 tail 谓词不看 sort_dir」）：在 albums 里放 TIE/Tie/tIE/tie 四条仅大小写不同的组名，NOCASE 下它们互等，权威序由次键 `name ASC` 决定，实测两个浏览方向给出的顺序都是 TIE、Tie、tIE、tie，也就是次键顺序与方向无关；锚点 TIE 的续页两个方向都精确返回其余三条。因此 tail 谓词故意忽略 sort_dir 是对的。副作用也要能解释：desc 浏览的 tail 语句计划是 `idx_albums_name_nocase_desc (name=? AND name>?)`——首键被等值钉死后，第二键仍按 ASC 走，合法且零 TEMP B-TREE；asc 的 next 走 `..._asc (name>?)`，desc 的 next 走 `..._desc (name<?)`，四条计划全部无临时 B-tree。
- 2026-09-20 — R116 代码改动（只改测试，未动一行生产代码）：src/tests/test_library_sqlite.py 新增 test_browse_cursor_continuations_keep_their_index_seek_plan（L1142-L1263），文件 3275 行。首跑该用例内 2 个红子用例，病因不是产品代码：夹具把绝对 music_root 直接当 parent 传，而 `folders.parent` 存的是相对根的路径、顶层目录行 parent 为空串，于是 parent-only 续页拿到零行、断言的 next_cursor 根本不出现。修法：夹具在每组目录下补建 Sub 1 / sub 1 / Sub 2 / Sub 3 四个子目录（id 形如 3-2，各带一支 t.flac），parent-only 分支的首次与续页调用改传 「Album A」，并各留两行中文注释说明「相对根的路径」这个约定。单跑 `Ran 1 test OK`，12 个 subTest 全绿。
- 2026-09-20 — R116 变异证明（仓库外副本 E:/fnAudio_r116_cp，robocopy 851 文件 23.2 MB，src 排 __pycache__/build/*.pyc，android-client 排 build/.gradle/.gradle-tmp/.media3-inspect/artifacts/node_modules/.cxx 与 *.apk *.jar *.aar *.so local.properties，tools /LEV:1 排 *.zip *.exe *.sh *.log，另带 docs、.github、根 .md、SOURCE_MANIFEST.sha256、VERSION、.gitattributes、.gitignore）：控制组先红后绿——`*.so`（android-client/app/src/main/jniLibs/arm64-v8a/libgojni.so）、gradle/wrapper/gradle-wrapper.jar、tools/*.sh 三样是清单与 test_real_device_automation_scripts 的输入，漏带就自红（5 ERROR + 2 manifest FAIL）；补回后控制组 Python `Ran 2395 OK (skipped=3)`（副本比仓库多 1 skip 是预期）、JS 69 支 0 失败。V1~V8 全灭 survivors=[]：V1 摘四张组表的 ASC 索引、V2 摘 DESC、V3 摘 folders root/parent 索引对、V4 摘 folders parent 对、V5 把表达式索引写成裸列（即条目原述的二进制排序形状）、V6 把 tail 谓词退回 OR、V7 反转 next-group 运算符方向、V8 把游标 ORDER BY 次键改 DESC；V1/V2/V3/V4/V5/V6/V7 的首条具名杀手都是本轮新测试，V4 另有 test_folder_pages_without_a_root_seek_by_parent_in_both_orders，V8 的杀手是 test_folder_cursor_continuation_reads_two_single_comparison_selects 与 test_group_cursor_walk_returns_every_group_once_across_a_case_cluster，V1/V2/V3/V5/V6/V7 还连带触发 test_large_library_benchmark.test_benchmark_enforces_bounded_sqlite_pagination ERROR。副本结束后两个被改文件已还原且 sha 与主树逐字一致，副本已删除。
- 2026-09-20 — R116 清单与门禁：中途刷新 `tools/update_source_manifest.ps1` 两遍幂等，698 条（本轮唯一被清单覆盖的改动是 src/tests/test_library_sqlite.py，sha 8AB728E46CDB253BA99CA76E0FD1CC35C9DDE49E9AC304C55BC2F461C49E8C07，逐文件抽查 MATCH）；三份根文档不在 SOURCE_MANIFEST 覆盖范围内，写文档不会改动清单计数。主树全量 discover 中途曾报 `Ran 2395` 且仅 2 红，两支都是「清单落后于工作树」（test_source_manifest 与 test_takeover_forensics），刷新后归绿，非逻辑缺陷。门禁终跑落在 artifacts/offline-20260920-round173.log（上一手是 round172.log）：按 R115 先例诚实交代——写下这行时该日志尚未产出，它由本轮收尾的终跑成为事实，若此后又改动被覆盖文件则同名日志必须重跑。另记一条流程教训：PowerShell 管道接 `Select-Object -First N` 会提前终止上游 python，本轮 ledger 第二跑一度被截成 6 行，长输出一律 重定向到文件再读。
- 2026-09-20 — R115 接管核验（先取证后落笔，并否证上一手摘要的三处抄录）：① 工作树 `git status --porcelain` 实测 1267 条、staged 0、stash 0、无 MERGE_HEAD/rebase-merge/rebase-apply/CHERRY_PICK_HEAD/BISECT_LOG 残留 ✓ HEAD 仍 d362047a082d5487a51471a1fabc220f784ae807 未动 ✓ `.gitignore` 未碰 ✓；② 上一手摘要称「代码、测试、变异、TODO.md 已完成」，磁盘逐项证实：`state_store.py` 481 行、`state_count_policy.py` 与两份测试齐备、TODO.md L2 已是 R115 记录、L61 那条 :60 已翻 `[x]` ✓ 三份根文档里 CHANGELOG_AI.md 与 PROJECT_CONTEXT.md 的 R115 记录数均为 0 ⇒ 本文件的这几条就是补的那一半；③ 摘要里的计数有三处与磁盘不符，一律以磁盘为准改正：`state_count_policy.py` 是 86 行不是 87 行、`test_state_store.py` 是 1510 行不是 1511 行、副本 `E:/fnAudio_r115_cp` 摘要称「已删」而磁盘仍在（864 文件）；④ 摘要没说的真问题：TODO.md L2 里那个副本路径被写成含 U+000C 换页符的字符串（塞给 python 的非 raw 串把 「反斜杠+f」 当真转义吃掉了），而 python 的 `splitlines()` 把换页当行边界 ⇒ 全量门禁的 `test_change_record` 直接变红，本轮主树全量首跑就是 `Ran 2394 FAILED (failures=1)`。已按原意把这两个字符补回，`tests.test_change_record` 3 项复绿。
- 2026-09-20 — R115 关闭内容：TODO「总量上限若从 50000 再往上调，`GROUP BY playlist_id` 的一次全索引扫描会成为新的常数项（本轮实测在 1e6 行规模约多花 16 ms）。真要提额，配套的是持久化每个播放列表的行数计数，而不是回到逐列表 COUNT」（原 L60，本条插入后在 L61，R65 新开）。本轮严格按条目点名的那条路做：持久化每个播放列表的行数计数，不回到逐列表 COUNT。
- 2026-09-20 — R115 关闭方式（列、写入者、读取者三处一起改，缺一个就是漏裁剪）：① `playlists` 新增**可空** `track_count`（NULL=未知；`ensure_state_schema` 用 `PRAGMA table_info` 探测缺列才 `ALTER TABLE playlists ADD COLUMN track_count INTEGER`，绝不能给默认值 0——那等于宣称整个旧库的列表都是空的）；② 两条写路径在同一条父行语句里记账 `len(playlist["trackIds"])`（`state_projection.strings()` 已去重，所以这个数就是随后落进子表的行数）；③ `_trim_persisted_playlists` 先按 `LIMIT cap+1` 读一次拿前瞻行判溢出，前瞻没过、`state_meta.playlist_children_verified` 没过、`children_are_within_budget()` 没过，三者任一没过就走慢路径：跑一次两条 `NOT IN` 清扫（首次把标记落进 `state_meta`）→ `_REFETCH_TRACK_COUNTS_SQL` 用子表把全部计数重算成权威值 → 重读父行 → 逐列表裁剪 → 删完把真实值回写。
- 2026-09-20 — R115 代码改动（存储侧）：src/app/server/state_store.py 现 481 行 sha ADEB6EC14627245B… ✓ `ensure_state_schema` 的补列 ✓ `_PLAYLIST_KEEP_ROWS_SQL` 以 `cap + 1` 前瞻读 ✓ 快路径总共只发两条语句（前瞻读 + 标记读），一条子表语句都不发 ✓ 慢路径末尾 `UPDATE playlists SET track_count = ?` 把删完之后的真实值写回去。派生列的判定规则不留在这层：SQL 之外的一律外提成纯函数。
- 2026-09-20 — R115 代码改动（策略侧，本轮新增文件）：src/app/server/state_count_policy.py 现 86 行 sha D700E939F7F5087A… ✓ `normalize_count()` 拒 bool（bool 继承 int，会把存进去的 `True` 读成一行）、拒 float、拒负数、拒超过 `MAX_PERSISTED_COUNT` 的值、拒无法 int() 的文本，一律折成 None=未知 ✓ `child_integrity_is_recorded()` 只认 `row["value"] == "1"`，读不到键、键形状不对、行不存在都是 False ✓ `children_are_within_budget()` 两臂都审：每个计数不得超过单列表上限、累计不得超过总量上限，任一计数不可信就返回 False 把调用者送回 SQLite 取权威值 ✓ 两个 cap 自己也过一遍同样的拒 bool 检查，cap 坏了宁可走慢路径。
- 2026-09-20 — R115 安全性论证（错的方向被穷举过，所以快路径敢什么都不查）：计数**高估**时最坏结果是多走一次慢路径、或者在裁剪循环里被安全跳过——信以为真的行集是磁盘行集的超集，而超集仍在两条预算之内就意味着真身更不需要裁；计数**低估**且总数仍在预算之内时，被留在表里的那些行本就是读者 `LIMIT` 看不到的行，不产生新的错误。于是任何一次删除都不基于一枚没核验过的计数发生。唯一的回归向量是「新出现一枚不经记账的子行写入者」，这条由源码级测试钉住：全 src 里 `INSERT INTO playlist_tracks` 字面量恰好 2 处、`playlist_tracks` 的唯一写入者仍是 state_store.py，另加「分组计数扫描已从裁剪路径消失」的源码断言。
- 2026-09-20 — R115 1e6 子行/1000 列表实测（本轮内存库复跑）：旧形状每次保存固定付 202.91 ms（两条 `NOT IN`）+ 37.21 ms（`GROUP BY playlist_id` 全索引扫描）≈ 240 ms；改后稳态快路径 0.77 ms；慢路径 230.56 ms 只在升级后的第一次保存或确实要裁时付一次。条目原文的 16 ms 是当时磁盘库上的分组计数旧测值，本轮内存库复测同项 37 ms，量级结论不变（差的是磁盘与内存，不是形状）。
- 2026-09-20 — R115 测试改动：全量 Python 2368 → 2394（+26 = `test_state_count_policy.py` 9 项 + `test_state_store.py` 内新增 `PersistedPlaylistCountTests` 17 项 ✓ skipped=2 不变）✓ `test_state_store.py` 现 1510 行、单文件 54 项（`StateStoreTests` 37 + 新类 17）全绿 ✓ 两支模块实跑 `Ran 63 tests OK`。新类点名覆盖：旧库升级只补出未知而不是 0 ✓ 裁剪把每个计数修成真实值 ✓ 快路径零子表语句（用 `_CountingConnection` 计数判别）✓ 与 R65 那个参考实现对拍 ✓ 高估不删行 ✓ 孤行清扫只付一次 ✓ 两条写路径各自记账 ✓ 失败的保存不留计数 ✓ 以及本轮接管补的 7 项：可信库仍要复查自己的单列表上限 test_a_trusted_playlist_still_rechecks_its_own_cap ✓ 可信库仍要复查总预算 test_a_trusted_library_still_rechecks_the_total_budget ✓ 未知计数不得读成空列表 test_an_unknown_count_never_reads_as_an_empty_playlist ✓ 超量列表不得走快路径 test_surplus_playlists_never_take_the_fast_path ✓ 无标记库不得被信任 test_a_library_without_the_marker_is_never_trusted ✓ 二次全量保存不许少报自己的行数 test_a_second_save_cannot_understate_its_own_rows ✓ 过期增量保存不许少报自己的行数 test_a_stale_delta_cannot_understate_its_own_rows。
- 2026-09-20 — R115 接管时修掉的三处自伤（都在磁盘上才看得见）：① `_true_counts()` 用 `GROUP BY playlist_id` 取参考值，零子行的列表根本不出现在结果里 ⇒ 改为对每个父行做相关子查询，否则「未知不等于空」那一整臂看不见；② `_use_tiny_caps()` 改完模块级上限后在 `finally` 里用 `self._caps()` 还原——那读回来的已经是被改小的 3/4/7，等于没还原并泄漏给后面的类 ⇒ 新增 `PRISTINE_CAPS` 在 setUp 里断言未被改过 + tearDown 还原 + `_caps_are()` helper，让用例能改上限而不留残余；③ 变异锚点不带前导换行时 n 个空格的子串会匹配进 n+k 个空格的行，V10 首跑报「锚点命中 2 处」而直接退出 ⇒ 所有缩进锚点补换行前缀。
- 2026-09-20 — R115 变异证明（仓库外副本 E:/fnAudio_r115_cp，864 文件 = src 618 + android-client 80 + tools 30 + 7 份根 .md + .github/workflows/verify.yml，跑完即删）：控制组 Python 全量 2394 项 OK(skipped=3)（比仓库多 1 个 skip 是 R113 记下的预期差异：副本无 release evidence）✓ 69 个 test_*.js 逐个 node 跑 0 失败 ✓ 15 个具名变异 V1～V15 全灭 SURVIVORS=0 ✓ 本轮接管又原样复跑一次变异矩阵并落盘（KILLED 15 / SURVIVED 0），两个被改文件还原后 sha 与变异前一致 [True, True]。摘掉者与杀手一一对应：V1 快路径不提前返回/V2 不取权威值/V3 丢单列表臂/V4 丢累计臂/V5 不落标记/V6 删完不回写/V7 未知读成 0/V8 新列默认 0/V9 去掉前瞻行/V10 全量写路径少报/V11 增量写路径少报/V12 bool 当计数/V13 任何标记行都信/V14 快路径不要求标记/V15 未核验库不清扫。
- 2026-09-20 — R115 分桶与反增长：按 PROJECT_CONTEXT.md 里 R113 写在纸面上的规则（设备桶与决策桶按节标题取 ✓ 代码桶 = 顶部段全部开放项 + 三条具名散条目 ✓ 台账桶 = 其余只登记持续观察/推进口径的 13 条）从磁盘重算：开放项 96 → 95 = 代码 31 + 设备 43 + 决策 8 + 台账 13 ✓ 四桶两两不相交且并集 = 95 ✓ 本轮新立可离线代码项 0（关闭 1 条，净关闭 1 条）✓ 设备段一行未改。旧目标正文快照 155 = 64 + 82 + 9 与 R99 快照 115 = 51 + 43 + 8 + 13 与本轮实测 95 = 31 + 43 + 8 + 13 三组并存，不合并、不覆盖。
- 2026-09-20 — R115 清单与取证工具（本轮把它们改在文档之前，以便记录里的数字都是实跑值而不是预测值）：`tools/update_source_manifest.ps1` 连跑两遍 IDEMPOTENT=True、698 条（基线 696 + 本轮新增两个 src 文件）、sha EB358A27E965DA41… ✓ 逐文件比对 698 条全 match（drift=0）✓ `tools/takeover_forensics.py --repo-root E:/fnAudio --full --quiet` 实测 listed=698 drift=0 stale=0 unlisted=0 ✓ 主树 `node --check app/ui/app.js` 与 69 支 JS 套件 0 失败。
- 2026-09-20 — R115 诚实交代：其一，本轮的终跑门禁日志名（artifacts/offline-20260920-round172.log）写下的时候磁盘上最新的仍是 round171，它是在本条之后才产出的，收尾复核负责任它变成事实；其二，1e6 那组数字来自内存库而不是磁盘库，条目原文的 16 ms 也是磁盘旧测值，两者量级来源不同已经写在上面而没有互相掩盖；其三，TODO.md 里「副本已删」那句在写入时为假，只有收尾真删了才为真，所以本轮把删副本、删 %TEMP% 脚本、门禁终跑都放到文档定稿之后做，并逐项回磁盘点名。
- 2026-09-20 — R114 接管核验（先取证后落笔，并否证一次幻影轮次）：① 上一份交接摘要声称 R114 已经收口，但磁盘上 TODO.md 与 CHANGELOG_AI.md 里 R114 的记录数为 0、门禁日志最新仍是 round170 ⇒ 「R114 已完成」不成立；对该摘要采取逐产物点名而不是整体采信或整体丢弃：代码四文件（policy 87 行 ✓ library 3048 行 ✓ 两个测试 92/3152 行）、清单 696 条幂等、副本已删、%TEMP% 尚有 14 支 r114_*.py 未清 —— 前四项经复跑核实成立（本轮亲自复跑 test_library_count_policy + test_library_sqlite = Ran 140 OK ✓ 全量 Python Ran 2368 / OK (skipped=2) 在 97.7s 内独立复现），文档与门禁两项确认缺失，由本轮补齐。② 真正完整收口的上一轮是 R113：artifacts/offline-20260919-round170.log（2026-09-19 23:46:08）。③ 工作树 `git status --porcelain` 实测 1264 条 ✓ staged 0 ✓ stash 0 ✓ 无 MERGE_HEAD/rebase-apply/rebase-merge/CHERRY_PICK_HEAD/BISECT_LOG/sequencer ✓ HEAD 仍是 d362047a082d5487a51471a1fabc220f784ae807 未动。④ 目标登记：旧目标正文把 R99 快照 115 = 51 + 43 + 8 + 13 写进终止条件、并把「第一步」指向早已完成的 R100 ⇒ 经用户本轮明确授权（「按你的建议设置可持续的目标继续工作」）先 update_goal=complete 退役这份过期正文（是退役正文，不是宣告任务完成），再 create_goal 登记一份不含任何硬编码计数的可持续目标（status=active、无 token 预算）；旧目标累计用量 9,459,261 tokens / 47,866s（≈13 小时 18 分）。
- 2026-09-20 — R114 关闭内容：TODO「组浏览页现在剩下的固定成本是那条 `SELECT COUNT(*) FROM <组表>`：100k 组实测 4.33ms，占修后单页 5.0ms 的八成……候选做法是把四张组表的行数写进 library_meta（与 track_count/dsd_count 同一口径）……风险要一起处理：总数一旦漂小，客户端的 has_more 会提前判定读完、列表被截短，所以做的时候必须带一条自愈核对……不能只加写入点」（原 L132 ✓ 翻转并插入顶部记录后在 L133）✓ 一轮净关 1 条 ✓ 新立 0 条 ⇒ 开放项 97 → 96、代码桶 33 → 32，设备 43 / 决策 8 / 台账 13 不变。
- 2026-09-20 — R114 关闭方式（条目原文要求两步，两步都做了）：第一步「写入点」：不按增量补丁维护派生值，而是让每一次能改变组表行数的路径末尾从表本身重算 —— `_refresh_group_counts()` 对四张表各跑一条 `SELECT COUNT(*)` 写进 library_meta，与既有 track_count/dsd_count 完全同一张表、同一 INSERT OR REPLACE 口径，因此结构上不存在「某个 mutation 忘了补 +1/-1」。第二步「自愈核对」：读页顺手带一行展望（`LIMIT limit + 1`），短页 ⇒ 走到表尾 ⇒ `offset + row_count` 就是精确总数，能修漂大的值；满展望行 ⇒ 只证明表更大，因此仅在 `saved < offset + row_count` 时判漂小（条目点名的危险方向：漂小会让 has_more 提前宣称读完并截短列表）为 refuted，去读权威 count；只要 `count != saved` 就回写，索引在扫描之外被改动也能自愈。
- 2026-09-20 — R114 代码改动（策略一侧）：src/app/server/library_count_policy.py 现 87 行 sha 6CE096B3AF645A0F05BD5238F9EDF7B8FB88A882362637E406BCEFBA02626400 ✓ 新增 `GROUP_COUNT_KEYS` :39-44（albums/artists/composers/genres → group_count_*）、`group_count_key(table, search)` :47-63、`browse_page_total(saved, offset, row_count, limit) -> (count, refuted)` :66-87；:5 复用既有 `MAX_SAVED_COUNT`。本轮另把 `group_count_key` 的判据从 `search.strip()` 收紧为 `if search:` —— 策略函数不得依赖调用者已经归一化输入，任何非空文本一律拒绝持久化总数，宁可多付一次 COUNT 也不许把收窄页的总数冒充整表总数。
- 2026-09-20 — R114 代码改动（写入侧）：src/app/server/library.py 现 3048 行 sha 35E1AF2A3AD3B12F330185C4BC45A3D5746729D6B04DA8E60A02150BB56F4279 ✓ :75-77 导入 `GROUP_COUNT_KEYS`/`browse_page_total`/`group_count_key` ✓ :1147 `_save_library_meta_count(conn, key, value)` 先判型（坏键、bool、非 int、负数一律拒写）再 INSERT OR REPLACE，写失败吞异常返回 False —— 读页借的是连接池里别人的句柄，修复写失败绝不能反过来拖垮一个已经带着权威总数的页 ✓ :1168 `_refresh_group_counts(conn)` ✓ 调用点 :2416（group_label_version 迁移重建四表之后）与 :2600（扫描事务尾部，紧接 dsd_count 之后）。
- 2026-09-20 — R114 代码改动（读取侧与注释）：src/app/server/library.py :1575-1602 只改未过滤的整表浏览分支：:1585 取键 ✓ :1586 读持久值 ✓ :1587-1591 缺键走 `counted_page_rows()` 并立即回写自愈 ✓ :1592-1602 有键走展望行 + `browse_page_total()` + refuted 才读 `count_sql` + `count != saved` 回写。`has_more` 表达式与 `project_group_rows()` 一字未改（:1603-1606 保持原样 ⇒ 多读的那一行被自然截断）✓ 读连接可写、`library_db_connect`（:2065 ✓ @contextmanager 在 :2064）在 `yield conn`（:2101）之后执行 `conn.commit()`（:2102）⇒ 回写真的落盘。:1576-1584 那段注释本轮重写：旧文本还在描述「每次读两句话」的旧形状，而代码已经改成「首次付费一次并存储所得」—— 注释与代码不许各说各话。
- 2026-09-20 — R114 写面取证（条目担心的是「只加写入点会漏」，所以先把写入者穷尽）：全 src 里能对四张组表落行的 SQL 只有：:2407-2410 迁移段的四条 DELETE、:2784 的 `DELETE FROM %s WHERE name = ?` 与 :2787/:2799 两条 `INSERT OR REPLACE`（都在 `_refresh_group_tables_for_changes` :2733 内，调用点 :2534 collect、:2590 apply）、以及 `_rebuild_group_table` :2710 / `_rebuild_simple_group` :2722 —— 后三个函数只被迁移段调用，而迁移段与扫描事务两个出口都已接到 `_refresh_group_counts`。`git grep -E` 只能命中那四条 DELETE（两条 INSERT OR REPLACE 因跨行拼串不落在同一行），所以这条取证不是只靠一次 grep 交差，是逐处点名。`folders` 不在本条范围（它没有行数口径，R107 的既有结论继续有效）。
- 2026-09-20 — R114 测试改动：全量 Python 2354 → 2368（+14 ✓ skipped=2）✓ 无新增 src 文件 ⇒ SOURCE_MANIFEST 仍 696 条。src/tests/test_library_count_policy.py 41 → 92 行 / 4 → 9 项 sha 8F70F50533D7BA80A51782DF0076B322D67D6B8DA3420DA63DE606552FE670E4 ✓ 新增 :47 四视图各用各键、:54 任何收窄一律拒键、:64 短页证明精确总数并修漂大、:72 满页只修漂小、:79 脏入参一律 refuted。src/tests/test_library_sqlite.py → 3152 行 / 131 项 sha 7E3BA7FED4DB8AAAD4D5B9E18C1C660CCE55BBCE7C86CE943462E0B21C48F662 ✓ 新增四个 helper（:2928 `_group_browse_config` ✓ :2943 `_group_count` ✓ :2948 `_set_group_count`（能删键）✓ :2957 `_trace_group_browse`）与九项端到端：:2972 扫描持久四表计数 ✓ :2986 未过滤页不再付 `COUNT(*)` 且三页走完 ✓ :3003 漂小不得截断列表且回写 ✓ :3020 满页修漂大 ✓ :3034 缺键首读自愈回写 ✓ :3049 search 页绝不读键 ✓ :3066 四个视图互不污染 ✓ :3095 写入器契约（-1/True/1.0/"3"/坏键/坏连接一律拒写，而 5 与 0 可写）✓ :3122 增量重扫刷新计数。另把旧测试改名为 :2132 `test_unfiltered_group_page_reads_an_indexed_page_and_a_persisted_count`（原 …and_a_separate_count）：语句快照只截第一次调用 ⇒ `LIMIT 2 OFFSET 0` 的计数断言为 1。踩过并写明的语义坑：`save_items_to_sqlite()` 是全量替换扫描结果，所以「增量重扫」必须把原有 items 连同新条目一起重发，只发新条目测的是替换而不是增量。
- 2026-09-20 — R114 变异证明（仓库外副本 E:/fnAudio_r114_cp，跑完即删）：副本组成 = robocopy `src`（617 文件 ✓ 排 __pycache__/build）+ `android-client`（81 ✓ 必须带，否则 test_ui_android_bridges 找不到源）+ tools 顶层 30 + 9 份根文档 + `.github/workflows/verify.yml`（少带任何一条，控制组自己就会红，见 R113 记录）。控制组：Python Ran 2368 / OK (skipped=3) ✓ Node JS 69 files failed=0 —— 先绿才允许谈变异。V1–V14 全灭（mutants=14 killed=14 survivors=0 broken_anchor=0），每个变异跑 5 个模块（sqlite/count_policy/cache/dlna_protocol/observability）并打印指名杀手测试：V1 摘掉扫描尾部刷新、V2 只持久化 albums、V3 短页不再证明精确总数（`<=`→`<`）、V4 满页一律 refuted、V5 漂小不再被 refuted、V6 refuted 不重读权威值、V7 修好不回写、V8 把旧值回写覆盖修复值、V9 不读展望行、V10 策略忽略 search 文本、V11 所有视图共用 albums 键、V12 写入器接受负数、V13 缺键不自愈、V14 丢掉 genres 键。四个改动文件还原后与主树 `Get-FileHash` 逐一 MATCH ✓ 副本已删。
- 2026-09-20 — R114 诚实交代：其一：副本控制组第一次全量跑出 `test_dlna_protocol.test_a_host_that_never_resolves_cannot_take_the_http_pool_with_it` 1 条红；单跑该模块 3/3 绿、真实树 3/3 绿、重建副本后全量不复现 ⇒ 判为发现顺序相关的既有抖动（该文件自带一份假 `library_groups`，与本轮改动无耦合），如实记录不粉饰为「一次通过」。其二：14 条变异全部被指名测试杀死，本轮没有等价变异，也没有出现「只有单元层杀得掉、端到端层杀不掉」的分层缺口。其三：本轮新立 0 条待办，也没有顺手关闭 L127 —— 它要的是「持久化计数」与「浏览改前缀 seek」都落地之后的索引复核，本轮只完成前半。其四：交接摘要的「代码桶 32」被磁盘否证（见下条分桶更正），其其余产物名（Ran 140/2368、696 条、V1–V14、副本已删）逐项复核成立；前任还提示「CHANGELOG 约 L44 有 TOC 需补条目」，磁盘实测 L40-48 是 R110 的记录行，本文件不存在目录段 ⇒ 不凭空补目录。
- 2026-09-20 — R114 自我更正（本轮第一版文档抄下的一处未取证行号）：读取侧那条记录最初写「读连接可写且退出时 `conn.commit()`（:2100）」，这是照抄交接摘要里 :2100 那个说法而没有回磁盘点行。实跑校验器逐条点名行号时发现 :2100 处是 `secure_sqlite_files(db_path)`，commit 在 :2102（`yield conn` 在 :2101，`library_db_connect` 定义在 :2064）⇒ 结论方向没错（退出确实提交，回写因此成立），但引用的行号是错的，已按磁盘改成 :2101/:2102 并把「:2100」在两处文档里清零。同一轮另否证一条摘要提示：「CHANGELOG 约 L44 有 TOC 需补条目」不成立 —— L40-48 实测是 R110 的记录行，本文件没有目录段；还有第二条：「代码桶 32」不成立（见下条分桶更正）。教训：转述里的行号一律当作待证，不当作事实。
- 2026-09-20 — R114 分桶更正（规则不变、0 条搬迁）：R113 立下的四桶规则一字未改，改的是引用它的人：上一份摘要以「L1827 那条散条目已翻 [x]」为据推出代码桶 32，那是把行号当身份的产物 —— 顶部每插一条记录，散条目行号整体 +1（R113 之后 L1827 → L1828），那条「继续按可测试边界拆分」在磁盘上仍是 `- [ ]`。本轮以节标题+文本锚定重算：代码桶 33 = 顶部段 30 条（27,28,59,60,61,62,65,78,79,80,83,90,92,94,101,105,108,127,129,132,139,140,142,143,147,148,155,165,209,215）+ 三条具名散条目（L536 持续审查未完成范围 ✓ L1810 Chromaprint/AcoustID ✓ L1828 继续按可测试边界拆分）✓ 台账 13 = 784,2065,2084,2087,2092,2093,2098,2112,2113,2125,2130,2131,2139 ✓ 设备 43 ✓ 决策 8 ✓ 四桶两两不相交且并集 = 97。关闭 L132 后代码桶 32、开放项 96，三条散条目行号再漂到 537/1811/1829 —— 这条更正只影响计数叙述，没有任何条目在桶之间搬迁。
- 2026-09-20 — R114 清单与门禁：SOURCE_MANIFEST.sha256 连跑两遍 IDEMPOTENT=True、696 条 ✓ `tools/takeover_forensics.py --full` 报 listed=696 drift=0 stale=0 unlisted=0 ✓ 逐文件点名：library_count_policy.py / library.py / test_library_count_policy.py / test_library_sqlite.py 四个 sha 与清单逐字 MATCH。门禁 tools/test_offline.ps1 本轮最后跑（其 mtime 必须晚于本轮全部文档编辑），日志 artifacts/offline-20260920-round171.log。未提交 ✓ 未 git add ✓ 未碰 .gitignore ✓ 设备段一行未改 ✓ %TEMP% 校验器与本轮 26 支 r114_*.py（含前任留下的 14 支）收尾删除 ✓ 本轮改动面（src ✓ tools 顶层 ✓ 根文档 ✓ artifacts）零 .new/.orig/.rej。顺手把这条口径收紧并纠正历史叙述：全树扫描 -Include *.new 实测命中 2 份，但两份都是 tools/runtime/gomodcache 与 gomodcache-clean 下 modernc.org/libc@v1.67.6/surface.new —— Go 模块缓存自带的文件名 ✓ mtime 2026-08-11 早于本轮 ✓ 未跟踪（`?? tools/runtime/`），不是补丁残留。以前各轮写「无 .new/.orig/.rej」时按的是改动面口径，本轮起把范围写进句子，免得被读成全树断言。
- 2026-09-19 — R113 接管核验（本轮由中断处接手，先取证后落笔）：① 工作树 `git status --porcelain` 实测 1263 条（1110 `??` + 149 `M` + 4 `D` ✓ staged 0 ✓ stash 0 ✓ 无 MERGE_HEAD/rebase-apply/rebase-merge/CHERRY_PICK_HEAD/BISECT_LOG/sequencer）✓ 分支 main ✓ HEAD d362047 未动；② 上一份交接摘要点名的 4 支新增测试逐一点名回磁盘：`test_cue_parser.py:134/:151/:160`、`test_cue_item_presentation.py:22`、`test_playback_cue_position.py:24`、`test_media_formats.py:78` 全部存在 ✓ 四个测试文件的 `def test_` 计数实测 21 / 3 / 5 / 33 与摘要一致；③ 9 个改动文件的 sha256 与摘要逐字相同（见「清单」条）✓ 全部 LF、无 CRLF 混入；④ 摘要说 `library.py` 的改动在 :618，实测在 :624（同轮加了 5 行注释 ⇒ 行号顺移）✓ 以磁盘为准更正；⑤ 摘要说变异矩阵 13/13 全灭但副本已删 ⇒ 本轮**不接受转述**，重建副本 E:/fnAudio_r113_cp 亲自重跑（结果见「变异证明」条）。
- 2026-09-19 — R113 关闭内容：TODO「`library.py` 里 `cue_end` 用 `or` 从 0.0 退回整轨时长，于是「这是该文件的最后一轨」与「结尾未知」共用同一个 0.0」（原 L108 ✓ 翻转并插入顶部记录后在 L109）✓ 一轮净关 1 条 ✓ 新立 0 条 ⇒ 开放项 98 → 97、可离线代码项 34 → 33 ✓ 设备 43、决策 8、台账 13 三条桶未动。
- 2026-09-19 — R113 关闭方式（三态设计）：解析端把「结尾」从「数值」升格为三态 —— 正数 = 同文件后继轨的起点 ✓ `0.0` = 这张表在该文件上再没有任何后继轨（真的跑到文件末尾）✓ `None` = 有后继轨但没有一个起点更靠后（平手或乱表）⇒ 边界未知；归一化只在扫描端做一次，`cue_segment_end()` 规定**只有 `0.0` 这一态可以借用源文件时长** ✓ `None` 与非法值统一回 `0.0`，也就是写库列 `cue_end REAL NOT NULL DEFAULT 0` 一直在用的那个「无已知结尾」哨兵 ⇒ 不需要改 schema、不需要迁移、不需要新增比较。
- 2026-09-19 — R113 代码改动（策略一侧）：src/app/server/cue_numeric_policy.py 现 49 行 sha 7806C62C7BFBB97B99564B10E758F1D0FFF32C6D58DB5C04EAB8BA97B5A0D8E5 ✓ 新增纯函数 `cue_segment_end(end, file_duration)`（:24-46）✓ `__all__` 由两项改三项 ✓ 实现口径：`boundary = finite_number(end, None)` ✓ `None` 或 `< 0.0` → `0.0` ✓ `> 0.0` → 原值 ✓ 恰好 `0.0` → `finite_number(file_duration)` ✓ 复用同文件既有 `finite_number`（它已经拒 bool/nan/±inf/非数值类型），因此不需要新写判型分支。
- 2026-09-19 — R113 代码改动（解析一侧）：src/app/server/cue_parser.py 现 141 行 sha FCDBB7D86ADF0A920926DC9FC628C1B85B4E687E3A1E96AFE3C81EDF04C5D76F ✓ :19 `_attach_track_ends` docstring :29-42 写明三态与「折叠第三态正是 `0.0` 同时冒充两种事实的根源」✓ :55-63 非字符串 `file` 支从 `0.0` 改判 `None` ✓ :65 `superseded = False` 与 :77 在 `stack.pop()` 之前置真 ✓ :79 空栈时按 `superseded` 分岔 ✓ 关键点：新增的只是布尔赋值 ✓ 没有新增任何一次比较或 `observe()` 调用 ⇒ R105 立的「每次比较计一次」界与 `test_cue_parser.py` 的精确计数用例（三轨表恰好 2 次、1200 格表 ≤ 2n、扁平无 INDEX 表恰好 n-1）全部原样通过。
- 2026-09-19 — R113 代码改动（扫描端与两个消费者）：src/app/server/library.py 现 2986 行 sha E6F838E25B52273FC011BB43AEE671808DF4DE6348500E2E422A0C90D915EFA1 ✓ :100 `from cue_numeric_policy import cue_segment_end` ✓ :624 由 `safe_float(track.get("end")) or safe_float(...duration...)` 改为 `cue_segment_end(track.get("end"), safe_float(audio_info.get("duration")))` ✓ :619-623 五行口径注释；src/app/server/cue_item_presentation.py（现 30 行 sha 66392AFE130D0E8B3CF1A53504B4D936B6B7444134142DB0A72F416C0FE8E015）与 src/app/server/playback_cue_position.py（现 48 行 sha 0CB145844E0F482DA4B71CF20D2B3387E57D2F75D20A1BFF425280EC8C9CBD69）**只加注释、逻辑字节未改** ✓ 记下来是为了不让下一轮把「读了两个消费方」误记成「改了两处行为」。
- 2026-09-19 — R113 消费方取证（条目原文只点了三个，实测有六个）：`cue_item_presentation.py:10` 与 `playback_cue_position.py:34/:48` 的 `cue_end > cue_start` 形状 ⇒ 未知边界（存成 0.0）天然呈 0 长段、不钳位、不报 finished ✓ 写库列 `library.py:2138` 与迁移表 :2278 的 `cue_end REAL NOT NULL DEFAULT 0` ✓ `library_write.py:144`/`:152` 走 `safe_float(source.get("cue_end"))`（`None` → 0.0）✓ `metadata_job_payload_policy.py:14` 把 `cue_end` 列入作业载荷字段 ✓ 前端 `app.js:2462` 判 `Number(item.cue_end || 0) > 0` 才认「有已知结尾」⇒ 全仓（522 个 py/js/html 文件正则扫 `cue_end` 与 `["end"]`）无第七处消费点。
- 2026-09-19 — R113 测试改动：全量 Python 2348 → 2354（+6 ✓ skipped=2）✓ 无新增文件 ⇒ SOURCE_MANIFEST 仍 696 条。src/tests/test_cue_parser.py 现 337 行 sha CDF24FFCFF2CECD5987CD9F4F2187D0BAEF05F4B119C32F727D12F241BC097D5（18 → 21 项）：`_reference_ends` 参照实现同步改三态（非字符串 file → None ✓ 有后继但无更晚起点 → None ✓ 完全无后继 → 0.0）✓ 随机差分新增 `states` 集合断言（三种结局必须全部出现过，否则参照改写了也证明不了区分生效）✓ :134 一张普通表三态并存 `[240.0, None, 0.0]` ✓ :151 只有末轨可借时长 ✓ :160 `cue_segment_end` 表驱动拒发明（None/bool/nan/±inf/负数/object/空串/字符串时长）✓ 既有非字符串与扁平表用例的期望改为 `[30.0, None, None, 50.0, None, 0.0]`、`[None, 0.0]`、`[None]*(n-1)+[0.0]`；src/tests/test_cue_item_presentation.py 现 43 行 sha 44C9DA65E481205B4EE073CB9D40206EE2C1E02BDF0ECD0FF535151302EA3E5D :22（cue_start 240 / cue_end 0 ⇒ duration 0.0）✓ src/tests/test_playback_cue_position.py 现 64 行 sha FB3B8547212B5E2CE3BEEB7773B91132483ADCB08D321936CE0CA0F72E6EDEA1 :24（未知：rel 660、duration_seconds 0.0、finished False；同文件带已知边界对照：rel 60.0、finished True）✓ src/tests/test_media_formats.py 现 487 行 sha 30D26B338C0D89822F52C9031A3C3E2CBBBE6B3CA7386EFA843C9D5DF0D2104B :78（patch `library.read_probe_metadata` 返回 `({}, {"duration": 300.0})` ✓ 三轨表 ⇒ cue_start `[0.0, 240.0, 120.0]` ✓ cue_end `[240.0, 0.0, 300.0]` ✓ duration `[240.0, 0.0, 180.0]`）。
- 2026-09-19 — R113 变异证明（接管后重建仓库外副本 E:/fnAudio_r113_cp 亲自重跑，不采信转述）：副本 = robocopy `src`（617 文件 ✓ 排 __pycache__/build）+ `android-client`（87 文件 ✓ 排 build/.gradle/.cxx）+ `tools` 顶层 27 份脚本 + 根文档 10 份 + `.github/workflows/verify.yml`（少了它 `test_ci_workflow` 会在副本里先红）✓ 控制组 Python `Ran 2354 tests / OK (skipped=3)` ✓ JS 69 个 `test_*.js` 全部 rc=0（`js files=69 failed=0`）⇒ 副本多出的第 3 个 skip 是 `test_offline_verification_script` 缺 release evidence 的既有跳过项，已在日志里点名核实 ✓ V1–V13 13/13 全灭：V1 unknown 折回末轨态 ✓ V2 unknown 借用文件时长 ✓ V3 末轨不再借时长 ✓ V4 平手候选不被丢弃 ✓ V5 seam 改按轨计数 ✓ V6 未分组轨冒充末轨 ✓ V7 unknown 被强转成 0.0 标记 ✓ V8 负边界当真实结尾 ✓ V9 扫描端退回一元 `or` fallback ✓ V10 空栈两种答案互换 ✓ V11 未分组轨不再降级 ✓ V12 presentation 去掉钳制 ✓ V13 playback 把 unknown 报成 finished ✓ 驱动 `mutants=13 killed=13 survivors=0` 退出码 0 ✓ 每个变异应用前校验锚点在目标文件中恰出现 1 次（BROKEN ANCHOR=0）✓ 跑完还原并 9 文件逐一 `Get-FileHash` MATCH ✓ 副本 `rm -r` 删除后 `%TEMP%` 脚本一并清。
- 2026-09-19 — R113 诚实交代（分层与等价）：其一 V4/V5/V6/V8/V11 只被单元层 `test_cue_parser.py` 杀死，端到端 `test_media_formats.py` 与两个消费者侧套件在其下仍绿 —— 这不代表覆盖不足，是这些守卫的效果本来就在解析层显形（端到端样本只有三轨，不触发平手/乱表形状）✓ 反过来 V9 只被端到端层杀死（解析层看不出扫描端 fallback 的退化）⇒ 两层各有独占视角，不是冗余；其二 V12/V13 证明两个消费者侧新测试确有判别力，但这两个文件的**逻辑本轮未改**，被摘的是既有守卫 ✓ 且 presentation 里「删掉 `cue_end > cue_start` 三元守卫但保留 `max(0.0, ...)`」在数值上是**等价变异**（结果同为 0.0），按 R106 的口径不列入矩阵；其三本轮没有新发现的缺陷需要立案 ⇒ 新立 0 条 ✓ 上一轮交接摘要猜「台账第 13 条在顶部段」是错的，磁盘复核是 L783（见「分桶规则」条）。
- 2026-09-19 — R113 分桶规则（把 47 条切成 34 + 13 的第一份可重算书面规则）：先按节标题取设备桶 = `## 宿主 MediaSession…`(10) + `## Android 等价 MediaSession 持续目标`(6) + `## P2：部署与外部系统验收`(3) + `## P0：外部验收（离线不可验证）…`(23) + `# 2026-09-01 飞牛 APP 私有播放会话（研究结论）`(1) = 43 ✓ 决策桶 = `## 需要项目负责人决策` = 8 ✓ 余 47 条中：代码桶 = 顶部段 `# fnAudio 待办` 全部开放项（本轮 30 条，插入 R113 记录前是 31 条，其中 L108 本轮翻掉）+ 三条具名散条目 {L535 持续审查未完成范围, L1809 Chromaprint/AcoustID（归属仍待用户裁定）, L1827 继续按可测试边界拆分} = 33；台账桶 = 其余 13 条，全部是「无具体可执行缺陷、只登记持续观察/持续推进口径」的条目 = L783 + L2064 + L2083 + L2086 + L2091 + L2092 + L2097 + L2111 + L2112 + L2124 + L2129 + L2130 + L2138 ✓ 该规则的可复现性由本轮 %TEMP% 校验器实跑钉住：`97 = 33 + 43 + 8 + 13` 且四组桶两两不相交、并集恰为全部开放项 ✓ 规则本身不改变任何条目的归属（搬迁 0 条），只是把上一轮无法复算的切分补成书面口径。
- 2026-09-19 — R113 清单与门禁：SOURCE_MANIFEST.sha256 刷新后仍 696 条（本轮无新增 src 文件 ✓ 根文档不在清单覆盖面）✓ `tools/takeover_forensics.py --full` 报 listed=696 drift=0 stale=0 unlisted=0 ✓ 离线门禁 `tools/test_offline.ps1` 按「最后跑」纪律在三份文档与校验器全部定稿并删除之后执行，日志 mtime 晚于全部文档编辑 ✓ 本轮终跑取 artifacts 下最新一份 offline-20260919-round17x.log（写本条时磁盘最新仍是 round169 ⇒ 不在记录里预指具体编号）✓ 逐文件抽查：12 个文件对拍 `SOURCE_MANIFEST.sha256` 全部 MATCH（本轮 9 个改动文件 + `src/app/ui/index.html` + `src/app/server/library_cursor_policy.py`（上一轮的改动文件，验清单没被本轮刷新写坏）+ `src/app/ui/app.js`）✓ 另 3 项经核**不在清单覆盖面**、只能记实测 sha：`tools/test_offline.ps1` A1C7F4509FA12A…、`tools/takeover_forensics.py` 5C7A225A7EB628…、`SOURCE_MANIFEST.sha256` 自身 77FB74B6D15D1A… ✓ 9 个改动文件的 sha 同时被本轮记录逐字引用，校验器把它们与磁盘 sha256 做了双向比对（记录里的每个 64 位十六进制串都必须能在磁盘上找到对应文件）✓ 未提交 ✓ 未 git add ✓ 未碰 .gitignore ✓ 设备段未动 ✓ `git status --porcelain` 相对本轮开头只多出终跑新增的未跟踪门禁日志（`artifacts/offline-*.log` 一律未被 git 跟踪）。 残留检查按可编辑面定界（这是本轮把它写成规则的原因）：`src/`、`android-client/`（排 `build`/`.gradle`）、仓库根一层与 `tools/` 一层之内 **零** `.new/.orig/.rej` ✓ 全仓另有两例同名后缀经核与本仓库无关且不予处理：`tools/runtime/gomodcache/modernc.org/libc@v1.67.6/surface.new` 与 `tools/runtime/gomodcache-clean/modernc.org/libc@v1.67.6/surface.new` —— 它们是 Go 模块缓存里上游自带的文件名（125673 字节 ✓ mtime 2026-08-11 早于整个审查系列）✓ 所在整棵 `tools/runtime/` 在 `git status --porcelain` 里折叠成一条 `??`（未跟踪第三方材料 ✓ 本轮不碰 .gitignore 也不碰它）。
- 2026-09-19 — R112 收尾复核（把「先写后验」的记录逐项验到成立）：写 L12 那条时磁盘上最新日志仍是 round166、副本 E:/fnAudio_r112_cp 还在 ⇒ 本轮按顺序补齐并回到磁盘点名：① PROJECT_CONTEXT.md 补写三条 R112 规则（现 L2/L3/L4，单行、LF、flat run 由 394 到 397 条）② %TEMP% 校验器对文档定稿前的三份记录报 FAILURES=0（flat run：TODO 114 条 L2..L115、CHANGELOG 770 条 L2..L771、CONTEXT 397 条 L2..L398；日期不倒序；TODO/CHANGELOG 无重复条目；无 CR），补写本条之后再跑一次，它只报一项 FAIL：自查规则把本条引用的旧措辞「11 个文件」当成残留的过期声明，格式/顺序/唯一性三项仍全绿 ⇒ 自查规则本身也得经得起被引用的旧文本，否则下一轮会把它当成新缺陷重查（此时 CHANGELOG flat run 为 771 条 L2..L772）③ test_change_record 3 项 + test_source_manifest 4 项 + test_source_hygiene 7 项全绿 ④ tools/update_source_manifest.ps1 重跑幂等：前后 sha256 同为 32E99C88D0F4CC0FCBD41A9742C57D34E5C80DDD62896F2E95A08857D61816EB、仍 696 条 ⇒ 上面「刷新」一词自此成立 ⑤ 抽查计数从「11 个文件」更正为「16 项全部 MATCH」，并记下 tools/ 两个脚本不在清单覆盖面（清单只含 src/ 与 android-client/）⑥ 变异副本与 %TEMP%\r112 全部删除（删前 6 个改动文件与真实文件逐字节 SAME）⑦ 门禁每一份日志都是全量重跑：round167 与 round168 都报 Ran 2348 / OK (skipped=2) / 69 支 JS 套件逐条绿 / exit 0，本轮终跑取收尾时 artifacts 下最新一份 offline-20260919-round16x.log（根文档不在清单覆盖面内 ⇒ 补记文档不推翻门禁结论，但终跑日志的 mtime 必须晚于全部文档编辑，这一点按实测核对）⑧ `takeover_forensics.py --full` listed=696 drift=0 stale=0 unlisted=0 exit=0 ✓ staged 恒 0 条；`git status --porcelain` 相对上一轮收尾的 1260 只多出本轮新产生的未跟踪门禁日志（`artifacts/offline-*.log` 一律没被 git 跟踪，每跑一次多一条 `??`），除此之外条目零变化 ⇒ 不存在意外改动。
- 2026-09-19 — R112 关闭内容：TODO「上一轮读过的首屏前端链路（app.js 的 librarySnapshotKey / restore|persist|schedule、renderTrackRows、commitTrackListHtml 按键复用、reuseSnapshotTrackMarkup + fetchLibraryResponse 合并、loadPagedLibrary / loadPagedLibraryWorker、fetchAllTracksForCurrentView）未发现缺陷，结论要正式补记进变更文档」（原 L132）✓ 一轮净关 1 条 ✓ 新立 0 条 ✓ 条目里的行号是插入本条之前的位置，翻转后这条在 L133，插入后整体 +1 ✓ 本轮真正改代码的那条「`has_more: True` 但没有 `next_cursor` 还剩两条路径」（原 L140，现 L141）**没有关闭**，改写为残余清单继续开着。
- 2026-09-19 — R112 关闭方式（记录型条目）：这条要的是「把读过的结论落到能被下轮引用的行号与测试名上」，不是新缺陷 ✓ 复核落点全部实测：`librarySnapshotKey` app.js:381 ✓ 消费点 :388（读侧 :392）、:417（写侧 :422）、:433（:438 取键、:442 写回前双重复核 `state.librarySnapshotPersistKey !== key || librarySnapshotKey(page) !== key`）✓ `library_page_snapshot_policy.js:30` 以 `snapshot.key !== key` 复核命中 ✓ `renderTrackRows` :3033 与 `commitTrackListHtml` :3235 ✓ `reuseSnapshotTrackMarkup` :5324 首行 `!snapshotHit || !isPagedTrackListing() || state.view === "queue"` 早退 + 两侧呈现签名交给 reuse policy 判等 ✓ `hasVisibleLibraryPresentation` :1392 委托 render policy，:1449/:1453/:3699/:7633 四处消费 ✓ `loadPagedLibraryWorker` :5710 开头 `seq = ++state.libraryRequestSeq`、:5728-5733 的 `state.libraryAbortController` 交还前比对身份 ✓ `fetchLibraryResponse` :5274、`fetchAllTracksForCurrentView` :5984 ✓ 生产代码为此文件一行未改，也不为本条新增测试：test_ui_library_page_snapshot_policy.js、test_ui_library_snapshot_reuse_policy.js、test_ui_library_render_policy.js、test_ui_library_load_key.js、test_ui_library_page_cursor_policy.js 五支既有套件已钉住这些口径。
- 2026-09-19 — R112 代码改动（游标载荷一侧）：src/app/server/library_cursor_policy.py 现 202 行 sha E1190FCDF418ECA1C865D0C69693FD70FFAE54CBFDF1CFE3EEE541807B50C09B ✓ 删 `_text()`、`_optional_text` 文档改写 ✓ :54-65 新增 `anchor_is_encodable()`，把「这一行能不能当锚点」的三条形状测试与编码器收在同一处，注释写明「页解码不许提出一个编码器会当场拒绝的锚点」✓ :68 `encode_track_cursor()` 新增 `inclusive=False` 形参，:84-87 只在 inclusive 时写稀疏键 `"i":1` ⇒ 现存 exclusive token 字节不变 ✓ :96 `decode_track_cursor()` 恒返回 `"inclusive": bool`（:119-125），:117 严格判型（拒绝 `"1"`、`1.0`、`2`、`None`、`[]`）✓ :166 `cursor_group_tail_where()` 比较符改 `>=`/`>` 二选一，:172-190 的「下一组」谓词保持单比较不变（inclusive 只影响组内那一支）。
- 2026-09-19 — R112 代码改动（页解码一侧）：src/app/server/library_page_result_policy.py 现 136 行 sha 3A73537EF02EB20A825024A42FF5CB10AAACA948D372B8A9963E6D0E05080CAD ✓ :23 `_row_anchor` / :32 `_anchor_is_encodable` / :38-60 `_continuation_anchor`：已服务锚点可编码就原样返回；否则取前瞻行，取键失败 `except` 回退不抛；前瞻自己也不可编码（同一块 NULL 的中段）就维持原来的无 cursor 答复，**不跳行** ✓ :59 替换成功才标 `inclusive=True` ✓ :119 `track_page_result()` 只在 keyed 锚点上读 flag，非 keyed 路径恒 False ✓ 死函数 `decode_track_page_rows` 连同 `__all__` 与 library.py 的导入、3 处测试夹具一起清掉（本轮实测：两条 OFFSET 页路径改走游标 decoder 之后它再没有调用者）。
- 2026-09-19 — R112 代码改动（OFFSET 页一侧）：src/app/server/library.py 现 2980 行 sha E846BE681B259E0E879D88EADFF1B16478997E042876CBF93871F68A63A2187B ✓ :1252/:1257（recent 视图）与 :1364/:1369（主视图）的 OFFSET 分支由 `limit` 改读 `limit + 1`，`args + [limit + 1, offset]` 这一表达式共 6 处绑定逐处核对 ✓ :1268/:1380 改走同一个 `decode_track_cursor_page_rows`，`has_more = None` 让完整性答案仍由总数推导 ✓ 各留 4 行注释说明「为什么首页也要前瞻行」✓ 这是本轮自己扩的设计：上一版方案只改游标页，实测首页落在 NULL 行上仍然发不出 cursor ✓ 顺带清掉 :82 未使用的 `encode_track_cursor` 导入。
- 2026-09-19 — R112 测试改动：全量 Python 2335 → 2348（+13，skipped=2）✓ 三个相关模块现 17 / 13 / 122 项 = 152 项 OK ✓ src/tests/test_library_cursor_policy.py 现 398 行 sha A5A10BC02966D46E1790FB72FCC166F6A162EBAF9BCDFF643AEB2051A7CEA8BF：+5 支 :176 空 id 锚点、:196 不可编码取值、:339 inclusive 从自身锚点起读、:365 两向走查只差一行、:374 flag 是 opt-in 且严格判型，另加助手 `_rewrite_token`（:47）✓ src/tests/test_library_page_result_policy.py 现 163 行 sha 63FE3552E8E7E110E14207063919A44E809245A8FF49F95E987AD1790F280DE1：新写 :83/:101/:116/:132/:143 五支，:27 那支是随死代码退役的改名，该文件净增 4 ✓ src/tests/test_library_sqlite.py 现 2938 行 sha 6857848F9B0A1F2DE7DC583D9532B638C6D7254587B3A417111D59FC6D7B5580：助手 `_null_key_library`（:745）、`_tail_cursor`（:836）+ 4 支端到端 :759（NULL 键组走查与 OFFSET 全等）、:778（组内 NULL title 走 inclusive 前瞻）、:797（多行 NULL 块：宁可不发 cursor 也不跳行）、:814（DESC 残余，续读得到空页且响应既无 next_cursor 也无 has_more）。
- 2026-09-19 — R112 性能前提：`>=` 与 `>` 在同一索引上单次 seek 实测 1.428ms / 1.473ms、查询计划一致 ⇒ inclusive 不引入新计划 ✓ 代价是 OFFSET 页每页多读一行（已写进 L141）。
- 2026-09-19 — R112 变异证明（仓库外副本 E:/fnAudio_r112_cp：617 个 src 文件 + 8 份根文档 + 12 份 android-client 源文件，因为 test_ui_android_bridge.js 要读它们；6 个改动文件与真实文件逐一 sha MATCH）：控制组 Python 152 项绿、69/69 JS 套件绿 ✓ V1 空 id 重新判为不可编码、V2 inclusive 退回严格比较、V3 flag 不传给编码器、V4 前瞻行永不启用、V5 锚点无条件被替换、V6 每个 token 都写 `"i":1`、V7 flag 不再严格判型、V8 锚点判定丢掉 title 检查、V9 OFFSET 页退回 limit、V10 解码器丢掉 flag、V11 遗留 token 默认 inclusive ⇒ 11/11 全部被指名杀死，还原后复跑仍绿，副本跑完即删。
- 2026-09-19 — R112 诚实交代三处：其一 V1 只在单元层被 :374 杀死，页投影层与端到端层在 V1 下仍绿（编码器本身从不拒绝空 id，前瞻替换会把它绕开）✓ 这不是覆盖漏洞，是这条守卫本来就只在锚点判定处生效；其二上一份交接摘要点名的一支端到端「空 id 走查」测试在磁盘上不存在，本轮以磁盘为准，空 id 路径由 :176 与 :143 两支覆盖，不冒领第三支；其三原计划「关闭 L140」被实测降级为「改写 L141」，所以净关闭只有 1 条。
- 2026-09-19 — R112 自我更正两处（都是上一版遗留、本轮跑测试时才暴露）：`test_an_empty_row_id_anchors_a_continuation` 第一版拿 artist 排序的 token 去问 title 排序，`cursor_page()` 判不同后返回 `("", [])`，断言是假的 ⇒ 改为对 artist 与 title 两个排序各编各的 token ✓ `bool(flag) and flag is not 0` 触发 SyntaxWarning ⇒ 改为 `bool(flag)`。另更正一处对外口径：前一版预计本轮会新增一支 JS 套件、门禁 JS 项数 69，实测 src/tests 下 `test_*.js` 本就是 69 支且本轮无新增。
- 2026-09-19 — R112 清单与门禁：SOURCE_MANIFEST.sha256 刷新后仍 696 条（本轮无新增 src 文件，根文档不在覆盖面内）✓ `tools/takeover_forensics.py --full` 报 listed=696 drift=0 stale=0 unlisted=0 ✓ Get-FileHash 抽查更正为 16 项全部 MATCH（10 个文件对拍 SOURCE_MANIFEST.sha256、6 个改动文件对拍本轮记录 sha 且与仓库外副本逐字节 SAME）；tools/ 下的 test_offline.ps1 与 takeover_forensics.py 经核实在清单里查无条目——SOURCE_MANIFEST 只覆盖 src/ 与 android-client/，696 条里 tools/ 为 0 条，因此这两个文件不在门禁覆盖面内 ✓ 开放项 99 到 98 = 代码 34 + 设备 43 + 决策 8 + 台账 13 ✓ 计数漂移四组并存不合并：目标正文 155 = 64 + 82 + 9、R99 快照 115 = 51 + 43 + 8 + 13、本轮开头实测 99、收尾实测 98 ✓ 分类器条目搬迁 0 ✓ 未提交、未 git add、未碰 .gitignore、设备段未动 ✓ 终跑日志 artifacts/offline-20260919-round167.log 写在产物之前，收尾补跑 offline-20260919-round168.log 作为本轮终跑（见本文件顶部同轮补记）。
- 2026-09-19 — R111 关闭内容：TODO「`library_connection_pool` 只是 `server.main()` 的引导默认值，既没进 `config.py` 的默认配置，也没有设置页开关或 `PROJECT_CONTEXT.md` 之外的文档说明」（原 L146）✓ 一轮净关 1 条 ✓ 新立 0 条 ✓ 条目里的行号是插入本条之前的位置，翻转后这条在 L147，插入后整体 +1 ✓「设置页开关」那一半按产品决策折进相邻设备项（原 L144 到现 L145），不新立项。
- 2026-09-19 — R111 代码改动（默认值一侧）：src/app/server/config.py 现 264 行 sha B4571B1BC1B0B97C5B56E0346761DA56CBB9E28CB1C32CFEA2D9778B51B7BFE0 ✓ :18-22 新增 `DEFAULT_LIBRARY_CONNECTION_POOL = True` 加四行口径注释 ✓ :29 进 `load_config()` 默认字典 ✓ :93-95 `load_config()` 用 `_strict_bool()` 归一 ✓ :153-155 `save_config()` 载荷同一口径 ✓ 默认字典 45 键、载荷 45 键，两侧键集 AST 实测完全相等。
- 2026-09-19 — R111 代码改动（排空一侧）：src/app/server/library.py 现 2973 行 sha E624BC43D2F3AFFEE1A749B0BF2CC7662BA301408231AFB7AB767194EA8688FF ✓ :1844-1857 新增 `apply_library_connection_pool_config()`：开着返回 0，关着调用可复池的 `close_library_connections()`，传进来的 config 读不出库路径时整体排空 ✓ 不用一次性的 `stop_library_connections()`，重新打开不需要重启。
- 2026-09-19 — R111 代码改动（接线一侧）：src/app/server/server.py 现 3390 行 sha 58BB844FE65B7E2695458EB000D3AD0B2461A6531762A30BCA190725352E2930 ✓ :31 导入换成 `apply_library_connection_pool_config`，顺带摘掉一个未使用的 `close_library_connections` 导入 ✓ :605-609 `commit_config_update()` 在就地提交之后调用排空器 ✓ :3334-3339 删掉 `server.main()` 里「配置缺键就注入 True」的引导分支，换成说明为什么不能在此发明第二份默认值。
- 2026-09-19 — R111 文档：新增 docs/LIBRARY_CONNECTION_POOL.md 72 行 sha 670AC63C7F3ABAABF429110659833DD2040543A33312F96B5CC6388580831610（英文、LF、无 BOM，docs/ 不在 manifest 覆盖面内）✓ docs/INDEX.md:8 登记 ✓ 内容覆盖默认值权威源、严格布尔口径、关闭即排空的保证、观测面字段、为什么没有设置页控件，以及验证命令必须先 `Set-Location C:\path\to\fnAudio\src`。
- 2026-09-19 — R111 测试改动：src/tests/test_config.py 现 388 行 sha 7A7BD448DFE8D9439D70AD36EE6C06C88E9A25DF53DD5B2F93933687C63FE32D（+4 条，文件内 24 条 OK）✓ src/tests/test_library_sqlite.py 现 2841 行 sha B637900A2AAA0F85F0A4980033D901BA5AC4CB09BDBEE5AEC4B01E0DA26030FB（+4 条，118 条 OK）✓ src/tests/test_server_lifecycle.py 现 227 行 sha 2FE24B9676F064B6496E7441CA4BBCDC204189CD16070B54BE52B79059CDCBF6（+3 条）✓ 四个相关模块合计 168 项 OK。
- 2026-09-19 — R111 变异证明（仓库外副本 E:/fnAudio_r111_cp，617 个 src 文件与 8 份根文档，6 个改动文件与真实文件逐一 sha MATCH，跑完即删）：控制组 168 项绿、还原组 168 项绿 ✓ V1 存盘白名单丢键、V2 默认字典丢键、V3 加载不再归一、V4 非法文本被当成关闭、V5 开着也排空、V6 排空换成一次性 stop、V7 丢掉读不出路径就整体排空的兜底、V8 提交不再调用排空器、V9 排空跑在提交之前、V10 提交失败仍然排空、V11 启动重新发明默认值 —— 11 条变异 rc=1，且每条都有新测试指名杀死。
- 2026-09-19 — R111 诚实交代两处：其一 V7 的 `apply(None)` 一支是等价变异（`close_library_connections(None)` 本来就排空全部），判别力全在 `apply([])` 那一支；其二该判别测试第一版 re-park 时复用同一个 `limit`，被 `LIBRARY_QUERY_CACHE` 命中而一条连接都没开，test_library_sqlite.py:314 报 `0 != 1`，换成缓存没见过的查询形状后才成立。
- 2026-09-19 — R111 自我更正（本轮自己写下的未取证数字）：新注释与新文档都写「冷页 2.4ms、连接前奏 1.45ms」，而仓库 2026-09-17 的首屏拆解记录是 2.67ms 与 1.46ms，2.4ms 是 R86「带 `sqlite_master` 探针的稳态连接」的数字、量纲不同不能挪用 ✓ server.py 的注释与 docs/LIBRARY_CONNECTION_POOL.md 两处均已按记录口径改写并注明出处。
- 2026-09-19 — R111 取证证伪两处：「改了曲库路径会遗留旧句柄」不成立 —— `library_db_path()` 只依赖 `cache_dir` ✓ 「新默认值会改变基准工具语义」不成立 —— `tools/benchmark_large_library.py:125` 内联构造 config 并在 :656/:666 显式设键与撤键 ✓ 另核实 `load_config()` 生产调用者只有 `server.py:3256` 一处、没有回显配置字典的 GET `/api/config`、没有测试读 `docs/`。
- 2026-09-19 — R111 清单与门禁：SOURCE_MANIFEST.sha256 刷新 696 到 696（本轮无新增 src 文件）✓ `tools/takeover_forensics.py --full` 报 listed=696 drift=0 stale=0 unlisted=0 exit=0 ✓ Get-FileHash 抽查 10 个文件逐一 MATCH ✓ 开放项 100 到 99 = 代码 35 + 设备 43 + 决策 8 + 台账 13 ✓ 条目搬迁 0 ✓ 未提交、未 git add、未碰 .gitignore ✓ 终跑日志 artifacts/offline-20260919-round166.log。
- 2026-09-19 — R110 关闭内容：TODO「R58 遗留：向上闭包依赖 folders 父链完整」（原 L81）与「接管一个中断会话时的固定动作：拿 SOURCE_MANIFEST.sha256 与工作树对拍」（原 L67）✓ 一轮净关 2 条 ✓ 新立 0 条 ✓ 条目里的行号是插入本条之前的位置，翻转后的两条现在落在 L82 与 L68，插入后整体 +1 ✓ :81 按条目自带的第一个方案关闭（把不变式钉死并配判别测试），没有改成字符串前缀闭包 ✓ :67 落成可执行工具而不是口头流程。
- 2026-09-19 — R110 取证（:81）：结论是「曲目已入库而目录行缺失」在生产写入路径里不可能出现——全库唯一的生产写者是 src/app/server/library.py:2372 save_items_to_sqlite，它把增/改/删三类变化记进 affected_folder_roots（建表 :2415、清空 :2416、三条 INSERT OR IGNORE :2418/:2426/:2434），:2501 调用 _rebuild_folders_for_changes（:2738），后者对每个受影响项整棵顶层树重建：按 path = top OR LIKE top/% 先删、再用同一前缀重选、补齐 1..len(parts) 全部祖先 ✓ 探针脚本覆盖七种序列（初次扫描、移到新深链、移到新顶层、删除、全新三级链、只改大小写、两个 root 下同名子目录），逐序列 tracks/folder_rows/expected/extras/problems 全为 0，合计 TOTAL_PROBLEMS=0 ✓ 因此递归闭包依赖的父链不缺行，条目担忧不成立，但它需要一条会红的守卫而不是一句口头结论。
- 2026-09-19 — R110 代码改动（:81）：src/app/server/library.py 现 2957 行 sha 2A64DDBD713772CB48FAC6263009FEFA4CD20F22483CA82E4328AEF436460FB1 ✓ 两处钉：:1576-1582 说明递归闭包靠「凡还有曲目的目录必有行」这条不变式并点名守卫测试；:2739-2747 docstring 说明整树重建正是为这条不变式服务 ✓ 生产逻辑一行未改，本轮属于「钉死既有正确行为」类关闭，不是行为变更。
- 2026-09-19 — R110 测试改动（:81）：src/tests/test_library_sqlite.py 现 2782 行 sha DD374E943668514D6EA60603B2817B08A02D7753937810899ECFF816C28E5CC2 ✓ 新增 3 条：test_incremental_folder_refresh_keeps_the_track_folder_closure_complete（配 _folder_closure_state 与 _folder_closure_violations 两个助手，每步增量后断言闭包无缺行/无悬空/计数一致/无多余行）、test_folder_search_after_an_incremental_move_lists_every_ancestor_level（增量移动之后搜索仍列出每一层祖先）、test_relative_folder_text_never_breaks_the_subtree_prefix_scope（相对目录文本里混进空段、点段或 LIKE 通配字符都不放大子树范围）✓ 本文件 114 条 OK。
- 2026-09-19 — R110 变异证明（:81，仓库外副本 E:/fnAudio_r110_cp 跑完即删，副本内 library.py 与真实文件同 sha）：控制组先绿 rc=0 Ran 114 failures=0 ✓ M1 祖先循环只补叶子、M2 新增曲目不计入 affected、M3 从不 DELETE 旧目录行、M4 重建出的父目录指向库根、M5 只重建变更目录本身、M6 相对目录保留空段与点段——6 条变异 rc=1，且每条都被新增的 3 条测试指名杀死（new_killers 均非空）✓ M6 只有 test_relative_folder_text_never_breaks_the_subtree_prefix_scope 能杀（other_failures 为空，说明它是这条路径的唯一防线）✓ 还原后 RESTORED rc=0 Ran 114 failures=0。
- 2026-09-19 — R110 工具改动（:67）：tools/takeover_forensics.py 新增 184 行 sha 5C7A225A7EB628A6C153FA19C399E3E22135B569E3101E9D28E46E06AF96D3A9 ✓ inspect_repo(root, manifest=None, full=False) 把清单与工作树对拍成三态：drift（被列且 mtime 晚于清单）、stale（drift 项或 --full 时逐文件 sha 不一致，以及被列但文件已消失）、unlisted（工作树有而清单没有）✓ 每条附「先跑哪几个 src/tests/test_*」建议，SUGGESTED_TEST_LIMIT = 12，先精确同名再同族补齐 ✓ 退出码仅在 stale 或非空 unlisted 时为 1 ✓ 命令行参数 --repo-root/--manifest/--full/--json/--quiet。
- 2026-09-19 — R110 测试改动与实测（:67）：src/tests/test_takeover_forensics.py 新增 190 行 sha AA3CF2CD7C3E6CF7E2EE9E406CA75F63CD80F64E36EE3751FA3356269F69CD6D ✓ 10 条 OK：9 条夹具（用 os.utime 摆时间戳，绝不 sleep）+ 1 条活库对拍 test_the_real_manifest_and_the_real_tree_agree_right_now ✓ 刷新清单前先跑真实仓库：listed=695 drift=0 stale=2（正是本轮改过的 library.py 与 test_library_sqlite.py）unlisted=1（新测试文件）exit=1 ✓ 刷新后 listed=696 drift=0 stale=0 unlisted=0 exit=0，--full 全扫 193 ms ✓ 也就是说工具当场指出的未验证面与人工取证得到的集合一模一样。
- 2026-09-19 — R110 变异证明（:67）：V1 内容从不比 sha、V2 跳过被列但已消失的文件、V3 drift 只在 --full 时才看见、V4 取消一切排除段、V5 把 unlisted 的差集算反、V6 精确同名测试失去优先、V7 退出码恒 0、V8 把 manifest_mtime 置 0 使全部文件算作 drift——8 条变异 rc=1 全被夹具杀死 ✓ V2/V4/V6 各只有一条测试能杀 ✓ 控制组与还原后均 Ran 9 failures=0（活库那条依赖真实仓库，不进副本变异范围，故夹具计数是 9 不是 10）。
- 2026-09-19 — R110 净账与门禁：TODO.md 现 2195 行 ✓ - [ ] 102 → 100 ✓ - [x] 顶格 1422 → 1425（顶块新增 1 条加翻掉 2 条）✓ 开放项 100 = 可离线代码 36 + 设备/外部 43 + 需产品决策 8 + 登记口径 13 ✓ 分类器搬迁 0：三个非代码桶计数与 R109 记录逐一对齐（43/8/13 未动），代码桶 38 → 36 恰好等于本轮翻掉的两条 ✓ 新立 0 条 ✓ SOURCE_MANIFEST.sha256 695 → 696 条（tools/ 与根文档不在清单范围内，故新增的 tools/takeover_forensics.py 不登记；src/tests/ 下的新文件必须登记）✓ 逐文件 Get-FileHash 抽查 library.py / test_library_sqlite.py / app.js / test_takeover_forensics.py / library_paths.py / test_source_manifest.py / android-client app build.gradle / src/wizard config 全部 MATCH ✓ 刷新清单后再跑工具对拍：listed=696 drift=0 stale=0 unlisted=0 exit=0 ✓ 终跑 artifacts/offline-20260919-round165.log：Python Ran 2324 OK（skipped=2）✓ JS 69 个测试文件全绿（68 行 passed 加 1 行 regression ok）✓ 尾部 git diff --check 干净、exit 0 ✓ 门禁前 git status --porcelain 1257 = 1104 未跟踪 + 149 M + 4 D，门禁后 1258；staged 0 ✓ 无 MERGE_HEAD/rebase/cherry-pick 现场 ✓ .gitignore 未碰（mtime 仍 2026-08-14 16:43:49）✓ VERSION 仍 0.2.34 ✓ 未提交、未 git add ✓ 设备段一条未动。
- 2026-09-19 — R110 自我更正（口径一律以当场实测为准，且必须说明统计范围）：① 未跟踪项：R109 记录时点 1101 ✓ 本轮刷新清单后门禁前实测 1104（+2 个新文件、+1 个 R109 自己的门禁日志）✓ 终跑后再加 1 个门禁日志 = 1105 ✓ 交接草稿里的「1102」既不是任一终态也没说明时点，本轮起一律写清「门禁前/门禁后」；② TODO 的 - [x]：顶格 1425、含缩进合计 1426 ✓ 差的 1 条是 L662「播放会话恢复时提升当前曲目元数据」——它是缩进项且没有日期前缀，所以不匹配记录格式正则却仍算一条完成项 ✓ 报告必须交代是顶格还是含缩进，否则同一状态会给出两个数；③ _rebuild_folders（library.py:2718）不是死代码：全仓唯一调用者是 tools/benchmark_large_library.py:119 ✓ 本轮一度按「只被自己的测试引用」下结论，被这条实测推翻，结论作废；④ R109 的门禁日志 artifacts/offline-20260919-round164.log 已通过（Python 2311 OK、JS 69、exit 0、manifest 695），但那一轮的中文汇报因执行中断从未送达用户，其关闭内容见 R109 各条；⑤ 目标正文快照与真实计数的漂移继续登记、不合并：原任务正文 155 = 64+82+9，目标对象冻结快照 115 = 51+43+8+13，R110 后磁盘实测 100 = 36+43+8+13。
- 2026-09-19 — R109 关闭内容：TODO「status 这个 out 参数是 parseBoundedJson 的第五个位置参数」（原 L113）与「文档即契约：断言应从脚本 param() 块生成期望」（原 L34）✓ 前者按条目给的第二个方案关掉（返回 {data, status}）✓ 后者按条目给的方向关掉（期望改为从 param() 块与 VERSION 生成）✓ 一轮净关 2 条 ✓ 新立 0 条 ✓ 三处发现（模拟器四开关无人记录、交接的 git 噪声口径、Python 总数 2310→2311）并入本轮记录而不另立项。
- 2026-09-19 — R109 代码改动（loader）：src/app/ui/response_json_loader.js 现 229 行（sha 09A458A1C34812A7E14EEE62AB8707CA134732F9F95677DBBE435F9D9D0A9B72）✓ :53 签名 response / fallback / maximum / setCancel ✓ :54 只留一个局部 let status = undecodable ✓ :55 outcome = data => ({ data, status }) ✓ 15 处出口全部 return outcome(fallback) ✓ 纯 return fallback 归零 ✓ status.value 归零 ✓ :208 read() 返回 { response, data: outcome.data, bodyStatus: outcome.status } ✓ 顶部 :47-52 记下「为什么是返回值而不是上下文对象」。src/app/ui/app.js 一行未改（sha 0D263282FC28B88468E2804BD3259000A9FDF767D811DB15B0BF3110BC013B71）⇒ 不触碰安卓内联面与 index.html。
- 2026-09-19 — R109 测试改动（loader 侧）：src/tests/test_ui_response_json_loader.js 现 597 行（sha B1C3003E257D527D13D835C6E0F64D4A1D07335F60322D0931226898917B2F86）✓ 新增 :546-578 的 12 形状 data⇄status 一致性环（streamParsed/streamOversize/streamEmpty/streamBroken/declaredOversize/bufferParsed/bufferEmpty/textParsed/textWrongType/jsonOnly/jsonFailed/noResponse ✓ 断言 parsedOnly(bodyStatus) === (data !== fallback) ✓ 另钉 4 份可信文档与 8 次拒绝两个计数，防止一个恒真或恒假的实现空转）✓ 新增 :583-592 三处结构钉（参数表长度必须恰为 4 ✓ status.value 命中 0 ✓ const status = { value: 命中 0 ✓ parseBoundedJson( 命中 2）。
- 2026-09-19 — R109 测试改动（文档即契约侧）：src/tests/test_offline_verification_script.py 现 293 行（sha A3B3F9011714E97749D7F8C0C2BA8150701B8588E33182C7437868CFE1405A6A）✓ 新增模块级 TOP_LEVEL_PARAM_BLOCK / PARAMETER_DECLARATION / RECOVERY_COMMAND_BLOCK / PS1_INVOCATION 与 script_parameters() / recovery_manual_text() / recovery_command_parameters() ✓ test_release_verifier_can_rebind_manifest_to_a_source_directory 的 SourceDirectory 改为取自解析器而不是硬抄 ✓ 原两条手抄文本断言替换为 test_recovery_manual_baseline_follows_the_version_file（期望由 VERSION 生成）与 test_recovery_manual_documents_the_parameters_of_the_tools_it_runs（清单 ≥3 个脚本 + 声明⇒必须被文档到 + 文档⇒脚本必须接受）✓ 加 test_recovery_manual_shows_how_to_persist_the_release_index 钉住 OutputPath 两侧同时改名才会通过。
- 2026-09-19 — R109 RECOVERY.md：现 127 行（sha 9646786E14FB8A72460751363B367052BD5607BAE6A9B0DC24AAA55684069AE9）✓ L32-35 新增一段记录 test_android_emulator.ps1 的四个开关（-AvdName 默认 fnaudio-api35-atd ✓ -SdkRoot 取 ANDROID_SDK_ROOT 再退回 tools\android-sdk ✓ -InstallSdk ✓ -KeepRunning）✓ 这段不是补文档美观，而是新覆盖测试逼出来的：声明了却没写进手册 = 门禁红。RECOVERY.md 不在 SOURCE_MANIFEST.sha256 范围内（清单只管 695 个 src/ 与 android-client/ 文件）⇒ 本轮文档编辑无需再刷清单。
- 2026-09-19 — R109 计数口径（两处纠正，全部重读磁盘）：① 上一轮交接把 git 现场记为「1253 项未跟踪噪声」，本轮实测 git status --porcelain 共 1254 行 = 1101 个 ?? + 149 个 M + 4 个 D（4 个 D 是 artifacts/0.1.174/{PACKAGE_CONTENTS.txt,RELEASE_NOTES.md,SHA256SUMS,VALIDATION.md}）✓ staged 0 ✓ 无 MERGE_HEAD/REBASE_HEAD/CHERRY_PICK_HEAD/sequencer/index.lock ✓ .gitignore mtime 2026-08-14 16:43:49 未动。② 交接把 Python 用例数记为 2310，本轮把手抄文档测试一拆为二 ⇒ 现为 2311（门禁 round164 应读到 Ran 2311）。
- 2026-09-19 — R109 变异矩阵（仓库外副本 C:\path\to\fnAudio_r109_cp ✓ 全部在本轮最终字节上逐条跑完整测试文件 ✓ 控制组先绿：副本 69 个 JS 测试文件 pass=69 fail=0 ✓ 该 Python 模块 Ran 15 OK skipped=1 ✓ 每条变异跑完即还原并复核字节相同）：loader 六条 —— 预置 status=parsed ⇒ 既有 :470 ✓ 进函数即快照 status ⇒ 既有 :409 ✓ 在 read() 里从 data 反推 status ⇒ 既有 :416 ✓ 删掉流式超限分类 ⇒ 既有 :416 ✓ 重新加回第五个位置参数 ⇒ 只被新参数表钉 :585 杀死 ✓ !response 带 parsed 回传 fallback ⇒ 只被新一致性环 :569 杀死（失败行落在新块内 ⇒ 本轮新断言是唯一防线）。文档契约六条 —— 给 index_release_evidence.ps1 加未记录的 [switch]$RequireNetwork ⇒ 覆盖测试红 ✓ OutputPath 改名 OutFile ⇒ 覆盖与持久化两条都红 ✓ 手册基线写 0.2.9 ⇒ 基线红 ✓ 只把 VERSION 改 0.2.35 ⇒ 基线红 ✓ 删手册里的模拟器命令行 ⇒ 清单 ≥3 断言红 ✓ 手册用 -VerifyNow 调一个不接受它的脚本 ⇒ 反向覆盖红。
- 2026-09-19 — R109 净账：TODO.md 现 2194 行 ✓ - [ ] 104 → 102 ✓ - [x] 1420 → 1422 ✓ 分类为 可离线代码 40 → 38 ✓ 设备/外部 43 未动 ✓ 产品决策 8 未动 ✓ 登记/口径 13 未动 ✓ 分类器搬迁 0（除本轮翻掉的两条代码项）✓ 新立 0 条 ✓ SOURCE_MANIFEST.sha256 仍 695 条且逐文件抽查（loader ✓ loader 测试 ✓ 本 Python 测试 ✓ app.js ✓ server.py ✓ test_ui_library_loading.js ✓ index.html）全部 MATCH ✓ 未提交 ✓ 未 git add ✓ 未碰 .gitignore ✓ 设备段一行未改 ✓ 门禁日志 artifacts/offline-20260919-round164.log ✓ 另记一条并入本轮的根文档缺陷：PROJECT_CONTEXT.md 有一条 2026-09-05 记录被逐字贴了两遍（原 L305/L306 ✓ test_change_record 按既有口径不检查规则文件的重复项，所以门禁一直绿而本轮 %TEMP% 校验器抓到 ✓ 已删后一份，全文件相邻同文条目归零）✓ 不另立待办。
- 2026-09-19 — R108 关闭内容：TODO「`app.js` 的行为只能靠源码正则约束」（原 L110）与「让『响应体读不出来』与『这一页真的是空的』在调用方可区分」（原 L115）✓ 前一条用「补 vm 外壳真跑」关掉它的前提 ✓ 后一条用「新增第二道闸 + 三个真实文档读取点加门」关掉 ✓ 一轮净关 2 条 ✓ 新立 0 条 ✓ 两处发现（`Content-Length: 0` 不止一处、`updateCurrentTranscodeStatus` 函数名与条目里的旧写法）并入本轮记录而不另立项。
- 2026-09-19 — R108 代码改动（两处文件）：`src/app/ui/response_json_loader.js`（222 行）新增 `parsedBody(status)`（:43 ✓ 只认 `parsed`）并入导出（:221 = `{read, usableBody, parsedBody}`）✓ `src/app/ui/app.js`（8250 行）只加三道门 —— :1259 `saveUserStateNow`（`else if (!response.ok || !parsedBody(...))` ⇒ 保持 `userStateDirty` 且 `retryDelay = 2000`）✓ :6204 `validateRestoredPlaybackTarget`（坏体 `return true` = 无信息 ✓ 不许据此把投送目标收回本地）✓ :6315 `loadDevices`（坏体抛「设备列表读取失败」✓ 走既有错误画法）✓ 全文 `parsedBody(result.bodyStatus)` 命中数 3 ✓ 无新增 UI 脚本 ⇒ `index.html` 一行未改 ✓ 安卓内联面未扩大。
- 2026-09-19 — R108 调用点枚举（这条明确要求「改之前先枚举一遍各端点实际返回体」）：`app.js` 共 16 处 `fnAudioResponseJsonLoader.read(` ✓ 分属 16 个不同函数（fetchJsonChecked/fetchJsonResponseBounded/readResponseJsonBounded/saveUserStateNow/loadServerUserState/refreshServerUserState/refreshRendererSession/refreshRemoteStatus/updateCurrentTranscodeStatus/fetchMetadataRequest/validateRestoredPlaybackTarget/loadDevices/loadMetadataStatus/loadDlnaDiagnostics/fetchMetadataProjectionStatus/refreshLibraryStatus）✓ 3 处加门 ✓ 其余 13 处逐站读到函数尾：0 处从坏体分支驱动 `apiFetch(`/`POST`/`DELETE` ✓ 出现的 `state.X = null` 全是 controller/promise 记账（rendererRequestController/remoteStatusController/transcodeStatusController/deviceLoadController/libraryStatusPromise+libraryStatusController）⇒ 它们是读-即-画或自愈轮询（`refreshLibraryStatus` 在 :7585-7589 直接 `if (!data) return`）✓ 一刀切抛错会把一次网络抖动变成错误屏 ✓ 三个通用 helper 把 `data ||` 透传给调用方。`strictBody: true` 全文仍 1 处（:5290 库列表 `fetchJson` 回调）✓ `usableBody?.(result.bodyStatus)` 1 处（:707）。
- 2026-09-19 — R108 服务端取证与一处口径纠正：`send_json`（`server.py:719`）恒设 `Content-Length = len(body)`（:734）并写出（:736-739 ✓ HEAD 例外）✓ 全仓 `Content-Length: 0` 实测**三处** —— `server.py:1284`（DLNA SUBSCRIBE 应答）✓ `:1914`（`serve_file_range` 零字节文件）✓ `:1928`（416 应答）—— 均不是 `/api/` JSON 端点 ⇒ 上一轮交接把它记成「唯一一处」是错的 ✓ 本轮纠正 ✓ 结论不变（反向代理之外的正常空响应不会被这道门变成错误屏）；`loadServerUserState` 的良性判定不收回：`revision=0` 是真实前置条件（`state_store.py:337-339` `expected_revision is not None and != current_revision ⇒ StateConflict`）✓ 409 应答带权威 state（`server.py:1336-1346`）且 `saveUserStateNow:1252` 已合并 ⇒ 最坏一次额外往返。
- 2026-09-19 — R108 两闸口径（本轮决定）：`empty` 在 `usableBody` 里仍算可用（宿主回答「没有内容」不是传输失败）✓ 但在 `parsedBody` 里算不可信（文档读取方不能把「没拿到内容」当成「内容是空的」）✓ 即「有没有响应」与「是不是一份可信文档」必须分开问；两闸只在 `empty` 这一档分歧 ✓ 由 `test_ui_response_json_loader.js` 逐项钉住。
- 2026-09-19 — R108 测试面：`src/tests/test_ui_library_loading.js`（749 → 1125 行 ✓ 新增块自 L747 起 ✓ 以单个 async IIFE 收尾并 `process.exitCode = 1` 记失败 ✓ 文件其余部分仍是同步 CommonJS）新增五组断言 —— (1) `fetchJsonChecked` 的 strict/non-strict × oversize/undecodable/empty 六种组合与 503 文案透传；(2) `validateRestoredPlaybackTarget` 坏体三例只 fetch 不决策 ✓ `parsed`+命中只多一次 `updateDeviceLabel` ✓ `parsed` 真空才走 `recover(false, dlna:cast-9)`；(3) `loadDevices` 坏体不恢复、设备与目标不变、错误画法含「设备列表读取失败」、在飞标志归位 ✓ `parsed` 缺失才恰好一次恢复；(4) `saveUserStateNow` 200 坏体保持 dirty 且末次 `schedule(2000)` ✓ `parsed` 成功清 dirty 并推进 revision ✓ 409 带 state 时合并并把 dirty 打回；(5) 源码接线钉（16/3/1 三处命中数与三门各自在自身函数切片内）。`src/tests/test_ui_response_json_loader.js`（540 行）加 taxonomy 与「两闸只在 empty 分歧」及真实 body 驱动。
- 2026-09-19 — R108 变异与防假阳性：仓库外副本 `C:\path\to\fnAudio_r108_cp`（robocopy /MIR 只带 `src` 与 `android-client\app\src` ✓ 桥接测试需要那些 Java/res 文件）✓ 控制组 69 个 JS 测试文件在矩阵前后各全绿一次 ✓ M1–M8 全部命中且 `restored=true`：M1 去 `strictBody &&` ✓ M2 `=== true` 改 `!== false` ✓ M3 坏体设备列表照样决策 ✓ M4 坏体空列表当成「真的没有设备」✓ M5 200 坏体当成保存成功 ✓ M6 loader 不再区分 empty 与 parsed ✓ M7 不导出 `parsedBody` ✓ M8 `loadDevices` 门失效。关键一例（专门为本条 L110 的前提做）：把 `test_ui_library_loading.js:544` 那条旧正则删掉后 **控制组仍绿**（旧状态下确实只有正则能拦）✓ 而 M1b/M2b 由行为断言分别以「非 strict 的超限体必须保持旧契约、不得抛」与「strict 读的超限体不得静默 resolve」杀死 ⇒ 正则不是唯一防线。
- 2026-09-19 — R108 夹具口径（写下来防止下轮误「修」）：vm 里造的对象带 vm 的原型 ⇒ 宿主 `assert.deepEqual(x, {})` 会假失败 ✓ 改断 `Object.keys(x).length === 0` ✓ `test_ui_library_loading.js:848` 已注释原因；宿主 `JSON/Object/Array/Promise/Uint8Array/ArrayBuffer/TextDecoder/TextEncoder/AbortController/setTimeout/clearTimeout` 刻意注入沙箱 ⇒ 跨 realm 的 `instanceof` 不参与判定；`vm.runInNewContext` 返回的是代码求值结果不是沙箱对象 ✓ 必须自留沙箱引用。
- 2026-09-19 — R108 当轮自我纠正（并入本轮，不另立项）：记录写完后复查发现新测试注释里用了 9 处 `TODO.md:110`/`TODO.md:115` 行号引用 ✓ 与 R102/R103 起「新增文本不用行号」的口径冲突 ✓ 且顶块插入一条就让它们当场错位 ✓ 已改为轮次锚点（`TODO.md R108 regex-constraint item` / `TODO.md R108 body-trust item`）✓ 同轮把两处夹具注释的行号引用从 :847 校正为 :848 ✓ 改动全在注释与文档文本 ⇒ 测试断言与产物未变 ✓ 但仍在最终字节上重跑控制组与变异矩阵并重刷清单（矩阵见 R108 变异行 ✓ 清单与终跑见 R108 净账行）。
- 2026-09-19 — R108 净账：开放项 106 → 104 ✓ 可离线代码项 42 → 40（顶块 39 − 2 + 散条目 3 = 40 ✓ 散条目仍为 L531 审查范围、L1805 Chromaprint/AcoustID、L1823 P3 拆分 ✓ 行号因顶块插入 +1）✓ 设备/外部 43 ✓ 产品决策 8 ✓ 登记/口径 13 未动 ✓ 新立 0 条 ✓ 分类器移动 0 ✓ 未提交 ✓ 未 `git add` ✓ 未碰 `.gitignore` ✓ 设备段未动 ✓ 终跑 `artifacts/offline-20260919-round163.log`（记录与清单都写完之后再跑 ✓ 门禁跑在最终代码字节上 ✓ 其后只补写本行数字 ✓ 三份根文档不在清单与测试面内）：Python 2310 项 `OK (skipped=2)` ✓ 与 round162 同数（本轮未新增 Python 测试）✓ 69 个 JS 测试文件全绿（65 行以 `checks passed.` 收尾 ✓ 与 round162 逐项同数）✓ `EXITCODE=0` ✓ `SOURCE_MANIFEST.sha256` 695 条 ✓ 逐文件抽查 `app.js`/`response_json_loader.js`/`device_target_presentation.js`/两份改动测试/`server.py`/`state_store.py`/`index.html` 共 8/8 MATCH ✓ 分类器移动 0 ✓ 无 `.new/.orig/.rej` ✓ 本轮 `%TEMP%` 脚本与仓库外副本在收尾时删除 ✓ 设备段未动。
- 2026-09-19 — R107 关闭内容：TODO L121「把作品图 id 从 `metadata_tracks` 带进 `item_json` 并同步收紧 `has_local_artwork`」✓ 关闭方式是**证明这个修法有害**而不是实施它 ✓ 生产代码零改动 ✓ 一轮净关 1 条。
- 2026-09-19 — R107 载体取证：`library_write.py:122 prepare_track_persistence` 用 `dumps(source)` **无键白名单** ✓ 所以「`item_json` 从不含 artwork 字段」是**生产者事实**（扫描器行是闭集 ✓ R106 已证）而非载体限制；新增 `test_prepare_track_persistence_has_no_key_whitelist_so_a_copy_would_persist`（写 `metadata_artwork_id` 确实能落盘）与 `test_prepare_track_persistence_writes_no_artwork_field_for_scanned_rows`（扫描行确实不带）把它钉成两条相反方向的事实 ✓ `test_library_write.py` 262 → 267 行（17 → 19 项）。
- 2026-09-19 — R107 否决理由：`has_local_artwork` 的三个排队判点 `metadata_service.py:3678 / 4480 / 4553` 读的正是这份 `item_json` ✓ 权威 artwork 落库后判据从「当前有效权威行」退化为「曾经复制过」✓ provider 改名 / 作品行回收 / 缓存过期三条自愈路全部静音 ✓ 新增 `MetadataArtworkPlumbingTests` 五条端到端用例（E2/E3A/E3B/E3C/C5）把不可逆性钉死 ✓ `test_metadata_service.py` 4047 → 4182 行（219 → 224 项）。
- 2026-09-19 — R107 否决的修法（记档防重提）：把 `library_presentation.py:97-98` 改成「恒优先 provider artwork」实测否决 ✓ 「已生成缩略图优先于作品图 URL」是有意的快/慢路径优先级 ✓ 不是缺陷；新增 `test_provider_artwork_does_not_replace_a_generated_thumbnail` 钉住现状。
- 2026-09-19 — R107 接线取证：`server.py` 只有 `:878 / :888 / :936` 三处公开投影点且都紧跟 `enrich_track_page` ✓ 新增源码级接线断言 `test_library_routes_enrich_before_projecting_track_rows`（含 `assertEqual(len(sites), 3)` ✓ 每处回看 8 行）✓ `test_library_presentation.py` 139 → 174 行；UI 两处 `metadata_artwork_id` 读取（`visible_metadata_prefetch_policy.js:33` / `library_metadata_merge_policy.js:6`）经核为惰性 ✓ 并入本条 ✓ 不另立新项。
- 2026-09-19 — R107 变异：仓库外副本 M01–M18 **killed 18/18 ✓ survived 0 ✓ invalid 0 ✓ missing_expect 0 ✓ contaminated 0** ✓ 控制组（4 模块 264 项）先绿；驱动本轮补三项防假阳性：变异表改为按「行号+内容双闸」从磁盘生成（反引号污染的旧表 6 个锚点 0 命中）✓ 整行锚一律带前导换行符（12 空格锚是 16 空格行的子串）✓ expect 配对改为先用全量套件 probe 找出真杀手（M08/M09 曾配反）。
- 2026-09-19 — R107 净账：开放项 107 → 106 ✓ 可离线代码项 43 → 42 ✓ 新立 0 条 ✓ 设备/外部 43 ✓ 产品决策 8 ✓ 登记/口径 13 未动 ✓ L1803 复核为外部依赖项嫌疑 ✓ 本轮不挪桶 ✓ 等口径裁决；未提交 ✓ 未 `git add` ✓ 未碰 `.gitignore` ✓ 设备段未动。
- 2026-09-19 — R106 关闭内容：`metadata_unavailable_policy` 的「三处 lyrics 读取在生产调用点是空转」与「封面分支实际上是死的」两条审查项 ✓ 关闭方式是**用端到端复现证伪条目前提** ✓ 不是改码关掉（与 L95/R51 的先例同类）。一轮净关 2 条 ✓ 新立 0 条 ✓ 开放项 109 → 107 ✓ 可离线代码项 45 → 43。
- 2026-09-19 — R106 复现证据：旧版 `library.json`（带 `lyrics` / `cover_url` / `cover_thumbnail_url`）→ `load_library_cache`（`library.py:2789` ✓ 条件为 `library_summary_from_sqlite` 为空）→ `save_items_to_sqlite`（`prepare_track_persistence` 对 `item_json` **没有键白名单**）→ `query_library_item_by_id`（`library.py:1726` ✓ 无路径过滤）→ 三个恢复投影全部读到真实值 ✓ 而 `server.py:3335` 在启动时确实调用 `load_library_cache` ⇒ 生产可达 ✓ 所以这些分支不是空转。
- 2026-09-19 — R106 反证与措辞纠正：扫描器行是闭集（`library_metadata` / `build_audio_item` / `build_cue_item` 都不产这三个键）✓ 而 `enrich_track_page(self, page, include_lyrics=False)` 的三个生产调用点 `server.py:877 / 887 / 931` 全走默认 `False` ⇒ 生产里 enrich 从不写 `lyrics`（`metadata_service.py:4415-4419`）✓ 条目原述的供体方向恰好说反。条目所称「`server.py:972` 恒假分支」实为 L963 `elif not METADATA_SERVICE:` ✓ 与上一支 `if METADATA_SERVICE:` 同义取反 ✓ **会执行** ✓ 并非恒假。
- 2026-09-19 — R106 代码改动（仅两处）：`src/app/server/server.py` L963 `elif not METADATA_SERVICE:` → `else:`（全文 `elif not METADATA_SERVICE` 命中数归 0 ✓ 行数 3385 不变）✓ `src/app/server/metadata_unavailable_policy.py` 的 caller-shape 审计注释按复现结论重写（10 行旧注释 → 17 行新块 L23-39 ✓ 文件 184 → 191 行）✓ 记明扫描器闭集 / 旧版缓存才是供体 / enrich 非供体 / 冷启动嵌码仍须走有界本地读而不是请求线程直读媒体。
- 2026-09-19 — R106 否决的修法：方案一「让恢复投影接收 `public_library_item()` 已公开化的行」实测否决 ✓ 该投影 `pop("lyrics")` 并把 cover 重写成 `cover/legacy-1?v=0` 这类合成 URL（旧版行原值丢失）✓ 还带 `cover_is_known_missing` 磁盘探测。方案二「本模块只认 `metadata_artwork_id` 并复用 `metadata_artwork_policy.artwork_url`」否决 ✓ `item_json` 原始行不含该键 ✓ 等于把活分支换成第二个死分支。
- 2026-09-19 — R106 测试：新增 6 个判别性用例 ✓ `src/tests/test_metadata_unavailable_policy.py`（121 → 207 行 ✓ 13 → 17 项）新增 `MetadataRecoverySupplierTests` 4 项含源码级接线断言 ✓ `src/tests/test_library_cache.py` 新增 `test_legacy_json_cache_rows_survive_into_the_single_item_lookup`（缓存文件→内存→`item_json`→SQLite 单行查询→两个投影 ✓ 查询前置空 `MUSIC_CACHE["items"]` 以强制走 SQLite 分支）✓ `src/tests/test_http_integration.py`（1444 → 1468 行）新增 `test_uninitialized_metadata_service_returns_a_lyrics_only_track_as_local`（未打标但带 lyrics 的行必须 `status: local` 而非 pending）。仓库内候选 12 模块 `Ran 506 / OK`。
- 2026-09-19 — R106 变异证明：仓库外副本 M01–M15 共 15 项 ✓ `SUMMARY total=15 killed=15 survived=0 invalid_kills=0 bad_anchor=0 missing_expect=0` ✓ 控制组 `Ran 169 / OK`（副本重同步后）。本轮修掉驱动自身两处会造假的缺陷：① robocopy 时点早于测试文件编辑 ✓ 副本 `test_http_integration.py` 停在 1444 行旧版 ✓ 新用例根本没参与运行 ⇒ M14 假存活 ⇒ 现驱动前置扫描副本 `tests/` 里是否存在具名 expect 用例并输出 `missing_expect`；② 单摘 `library_presentation.py` 的 `result.pop("lyrics", None)` 是**等价变异**（第 76 行 skip-list 已把 `lyrics` 排除在拷贝之外 ✓ 两道防线互为冗余后备）⇒ 改为成对摘除 skip-list 项与该 pop 的复合变异 ✓ 驱动新增 `old2` / `new2` 支持。
- 2026-09-19 — R105 修复内容：关掉「线性目前靠 `finite_number` 调用计数断言 ✓ 是用实现细节代理复杂度」那条 ✓ 走条目自己开的第一条路（显式可注入的比较计数器）而不是第二条（降级成基准脚本）。`src/app/server/cue_parser.py` 104 -> 120 行 ✓ `_attach_track_ends(tracks, observe=None)` 在 `while stack:` 的每次栈比较处调用 `observe()` 一次 ✓ `parse_cue_structure(lines, fallback_album="", observe_end_stage=None)` 把它转成关键字转发口。计的是「被考察的候选起点数」✓ 这正是条目要求替换的东西：归一化挪进主循环、或换别的数值包装 ✓ 都不会改变这个数。
- 2026-09-19 — R105 等价性：循环从 `while stack and stack[-1] <= start:` 拆成「先取栈顶再判定」（`if not (stack[-1] <= start): break`）✓ 不可比值走的是同一条谓词 ✓ 所以非有限值行为不变。这条不是靠读代码认的：变异 M13 把 `<=` 改成 `<`（即改变并列值的丢弃时机）被既有的随机对拍用例 `test_track_end_matches_the_nearest_later_start_on_the_same_file` 杀掉 ✓ 说明重写没有顺手放松语义 ✓ 也没有把那条旧对拍变成摆设。
- 2026-09-19 — R105 删掉的脆弱形态：`test_track_ends_do_not_rescan_the_sheet`（monkeypatch `cue_parser.finite_number` 后断言调用数 ≤ 2n）整条移除而非并存 ✓ 因为并存会保留它最怕的那件事：以后有人把归一化提到主循环 ✓ 这条会红 ✓ 而复杂度其实没变。同时新增一条自读源码的反向断言 ✓ 测试文件自身不得再出现 `cue_parser.finite_number =` 赋值 ✓ 防的就是「换个写法把旧形态抄回来」。
- 2026-09-19 — R105 新用例（`src/tests/test_cue_parser.py` 163 -> 265 行 ✓ 11 项到 18 项）：三轨小表 examinations == 2 且 ends 为 [10.0, 20.0, 0.0]（一格同时杀「未转发得 0」「每次比较计两下得 4」「每轨计一次得 3」「挂到 push 点得 3」）✓ 一格一轨 1200 表 ≤ 2n ✓ 无 INDEX 的扁平表恰好 n-1（非空口：上界若由「什么都不计」满足就是假证据）✓ 规模斜率 4 倍表 ≤ 6 倍工作量（线性比值 4 ✓ 二次到 16）✓ 测试内重述旧嵌套定义并按同口径计数后断言它必然越过 2n（界可分性 ✓ 没有它前面的界只是空洞通过）✓ hook 中性（带与不带计数器的产物逐项相等）✓ 签名与可选性钉。
- 2026-09-19 — R105 控制组与变异：仓库内定向 `tests.test_cue_parser` 18 OK ✓ 邻近 `test_cue_item_presentation`+`test_cue_reader`+`test_playback_cue_position`+`test_library_sqlite` 120 OK。仓库外副本（robocopy `src` 并补 `android-client` ✓ 否则 `test_ui_android_bridge.js` 因缺 `MainActivity.java` 失败）JS 控制组 69/69 全绿后跑 M01–M13：12 项由具名用例杀死 ✓ M12（`if observe is not None:` 同义改写成 `if observe:`）按设计存活并如实标注等价。
- 2026-09-19 — R105 方法学（R88 教训第二次生效）：首轮 M06/M07 报 killed 但拿不到任何具名失败用例 ✓ 查因是**语法假杀** ✓ M06 的替换串多补了一行重复谓词造成缩进错误 ✓ M07 的替换串把 `while stack:` 一起吞掉。两者只让套件以 IndentationError 非零退出 ✓ 对判别力是零证据。驱动因此新增 INVALID-KILL 口径（非零退出但没有具名失败即判无效）✓ 修正后重跑 ✓ INVALID_KILLS=0 ✓ 且确认 M06 唯一杀手是「hook 中性」那条用例。
- 2026-09-19 — R105 门禁与净账：终跑 `artifacts/offline-20260919-round160.log`。开放项 110 -> 109 ✓ 可离线代码项 46 -> 45（顶块 42 ✓ 散条目 3）✓ 设备/外部 43 ✓ 产品决策 8 ✓ 登记与口径 13 保持不变 ✓ 新立 0 条。`SOURCE_MANIFEST.sha256` 本轮刷新并逐条重算 ✓ 改动文件 `cue_parser.py`、`tests/test_cue_parser.py`、`TODO.md`、`CHANGELOG_AI.md`、`PROJECT_CONTEXT.md` 逐文件 sha 抽查 MATCH。未提交 ✓ 未 `git add` ✓ 未碰 `.gitignore` ✓ 设备段未动。
- 2026-09-19 — R104 修复内容：关掉「DLNA 浏览分组根容器仍先物化整张表再在 Python 里切片」那条。`src/app/server/dlna/service.py`（1142 -> 1221 行）新增三个单元：`_provider_browse_page(value, rows_key)`（L116 ✓ 只有当返回值是 `Mapping` 且含 `rows_key` 且 `count` 可解析时才认定「这是一次有界的页读」✓ 否则把 total 报为 `None` 让调用方回退整表）、`_group_page()`（L967）、`_folder_page()`（L996）✓ `_browse()` 的两个分支改为调用它们（调用点 L898、L926）。注入签名放宽为 `Callable[..., Any]`（L715、L718）并配 5 行注释说明新契约。
- 2026-09-19 — R104 为什么分页不能直接开：提供方 `query_library_groups`/`query_library_folders` 本来就支持 `limit`/`offset` 并在页旁声明全表总数 ✓ 但 DLNA 侧的调用方是插件式注入 ✓ 单测与私有部署都可能塞进「返回一个 list 的旧提供方」。若把 list 长度当总数 ✓ 一次翻页就会把 `TotalMatches` 写成页长 ✓ 控制器据此立刻停止翻页——那比原来的整表物化更糟。所以判据是「提供方是否声明了总数」而不是「调用方是否请求了页」。
- 2026-09-19 — R104 保留整表路径的三种情况（都有取证不是懒）：(a) 分组按艺术家排序（`sort_key == "artist"`）✓ 此时排序值不在组名上 ✓ 提供方按名分页会给出错窗口 ✓ 变异 M04 专杀「artist 也分页」；(b) `start > MAX_LIBRARY_OFFSET`（=100000 ✓ 越出提供方窗口）✓ 变异 M05 是去掉这道守卫；(c) 提供方未声明总数。另刻意保持无界两处并写进断言：`folders` 根容器（L909 ✓ `query_library_root_folders` 没有 `limit`/`offset` 语句且每个配置根只出一行 = 证伪证据）与 `_metadata_for_object()` 的单行存在性扫描（L1098、L1106 ✓ 单行存在性、提供方无按名定位 API）。曲目分支 `offset` 的同源钳位本轮未动 ✓ 按反增长约束并入本条登记 ✓ 不另立项。
- 2026-09-19 — R104 顺带修掉一个条目未登记的缺陷：子目录容器里整页被目录行填满时 `remaining == 0` ✓ 原实现连曲目总数都不再询问 ✓ `TotalMatches` 只剩目录数 ✓ 控制器因此看不到该目录里的曲目。现在 `library_page` 恒调用一次（`remaining` 为 0 时以 `limit:1` 只取计数 ✓ 探针行不渲染）✓ `track_offset = max(0, start - folder_total)` 用真实目录总数而不是页长 ✓ 变异 M12（渲染探针行）与 M13（不再探针）分别钉住两半。
- 2026-09-19 — R104 接线与判别性：`src/app/server/server.py`（+6 行 ✓ 现 3385 行）的 `initialize_dlna_services()` 内 `groups(view, limit, offset, sort_dir)`（L3152）与 `folders(parent, root, limit, offset, sort_dir)`（L3158）转发现有查询 ✓ `roots()` 不动并在其上方加 4 行注释说明「无分页语句可用」。`src/tests/test_dlna_protocol.py` 1650 -> 2002 行 ✓ 模块用例 86 -> 99：13 条新用例用假提供方记账 kwargs ✓ 断言「一次浏览只发一次读且带 limit/offset」「desc 浏览透传 sort_dir」「总数不被 5000 物化上限封顶」「第 5001 组之后仍可达」「页内顺序归提供方 ✓ 不再本地重排」「越窗回退整表」「`_provider_browse_page` 只信被声明的 total」「缺 count 不得当 0」「unpaged 不得当 paged」「目录总数与曲目计数相加」「永不分页的目录容器」✓ 其中两条是反向断言（根容器与元数据分支不得出现分页参数）✓ 防过度修复。9 个旧双假人升级到 `**query` 契约。
- 2026-09-19 — R104 控制组与变异：仓库内定向 6 模块（`test_dlna_protocol`、`test_dlna_media_server`、`test_dlna_ssdp`、`test_library_sqlite`、`test_http_integration`、`test_http_request_policy`）Ran 312 OK ✓ 两次一致。仓库外副本 `%TEMP%\fnaudio-r104-mut`（robocopy `src` 之外还必须带上 `android-client` ✓ 否则 `test_ui_android_bridge.js` 因缺 `MainActivity.java` 失败）：69 个 JS 控制组先绿 ✓ 驱动脚本记录 control rc=0 ✓ M01~M16 全部被杀死 ✓ survivors=0 ✓ 两次跑一致。变异面：吞 limit ✓ total 取页长 ✓ 页内重排 ✓ artist 也分页 ✓ 去窗口守卫 ✓ Mapping 判定取反 ✓ 不再要求 rows_key ✓ 缺 count 当 0 ✓ unpaged 当 paged ✓ folder_total 用页长 ✓ total 丢目录数 ✓ 探针行渲染 ✓ remaining==0 不探针 ✓ 目录容器永不分页 ✓ wiring 吞 sort_dir ✓ wiring 给 roots 造分页 API。
- 2026-09-19 — R104 门禁与净账：`artifacts/offline-20260919-round159.log` 为终跑记录。开放项 111 -> 110 ✓ 可离线代码项 47 -> 46（顶块 43 ✓ 散条目 3）✓ 设备/外部 43 ✓ 产品决策 8 ✓ 登记与口径 13 保持不变 ✓ 新立 0 条。`SOURCE_MANIFEST.sha256` 本轮刷新 ✓ 改动文件 `dlna/service.py`、`server.py`、`tests/test_dlna_protocol.py` 逐文件 sha MATCH。另记两处行号漂移：条目原文写的接线位置 `server.py:3095` 现为 L3148-3159 ✓ 本轮自身新增引用一律用函数名与偏移表达式 ✓ 不写行号。
- 2026-09-19 — R103 修复内容：关掉「ID3v2.4 的帧级标志仍未处理 ✓ 帧级标志为真时现在的行为是读错而不是跳过」那条。`src/app/server/id3_parser.py` 新增 `_frame_body(payload, frame_flags, major)` ✓ `iter_id3_frames()` 从「完全忽略帧自己的两个标志字节」改为读出 `payload[offset + 8:offset + 10]` 并交给它：可撤销的（v2.4 帧内 unsync、data-length indicator）就地还原 ✓ 不可表示的返回 `None` ✓ 调用方跳过该帧但仍执行 `offset = frame_end`。标签级与 `major` 的既有处理未动。
- 2026-09-19 — R103 取证更正（本轮最重要的一条）：条目正文里的位值有两处是错的 ✓ 它写 `0x10` 压缩、`0x08` 加密 ✓ 以权威兼容实现 mutagen（`mutagen/id3/_frames.py` 的帧标志表 ✓ 两个标志字节按 16-bit 大端合并）核对后为：v2.4 压缩 `0x0008` ✓ 加密 `0x0004` ✓ grouping `0x0040` ✓ 帧内 unsync `0x0002` ✓ data-length indicator `0x0001` ✓ `0x0010`/`0x0020` 是保留位；v2.3 才是压缩 `0x0080` ✓ 加密 `0x0040` ✓ grouping `0x0020`。照条目实现的具体后果：`0x10` 被当成压缩位就会漏掉真正的压缩帧 ✓ 而 `0x08` 被当成加密位就会把 v2.4 的压缩帧误判为可读。`id3.org` 官方页本轮不可达（404/500）✓ 因此以 mutagen 源码 + 本地既有测试夹具为权威源。
- 2026-09-19 — R103 写侧后果（读修复为什么同时改变写语义）：`iter_id3_frames` 有两个消费者 ✓ 库扫描读侧（`id3_container.py:103 read_id3` ✓ `:110 read_id3_cover`）与标签写入侧（`metadata_service.py:336 _preserved_id3_frames`）。写侧 `_id3_frame()`（`metadata_service.py:296`）把帧标志硬编码为 `b"\x00\x00"` ✓ 且重建的标签头也是 `ID3\x03\x00\x00` ✓ 所以在修复前「保留」一个压缩帧等于把它的 zlib 或密文字节重新标称为明文帧 = 对该帧的彻底破坏；修复后这类帧被丢弃 ✓ 不再生成谎报的帧 ✓ 带 indicator 或帧内 unsync 的帧则改写为正确的明文帧。取舍已写入 `_preserved_id3_frames` 的 docstring ✓ 新增两条写侧回归钉（见下）确保「清除标志 + 原样搬运作密文」这一损坏形态不可能回来。
- 2026-09-19 — R103 判别性：`src/tests/test_id3_parser.py` 从 148 行扩到 277 行 ✓ 测试内助手 `_frame()` 加 `flags=0` 形参（默认值使既有 20 余处调用零改动）。新用例 10 条：v2.4 帧内 unsync 还原（用 UTF-16 编码 ✓ 因为 `FF 00` 是它合法的正文字节 ✓ 被忽略的标志正是会破坏它的那种字节）✓ indicator 剥离 ✓ 两者同置 ✓ indicator 体过短拒绝而后续帧仍读到 ✓ 七种不可表示位（v2.4 `0x0008/0x0004/0x0040/0x0010` ✓ v2.3 `0x0080/0x0040/0x0020`）逐个跳过且不中断 ✓ v2.3 不得借用 v2.4 的可撤销位 ✓ v2.5 标签不得按 v2.4 规则还原 ✓ 七种 status 位一律不得造成跳过（反向断言 ✓ 防过度修复）✓ 压缩帧不得抵达标题字段。写侧两条在 `src/tests/test_metadata_service.py`（3986 -> 4046 行）：`test_tag_write_cannot_relabel_frames_it_cannot_decode` 与 `test_tag_write_promotes_undoable_v24_frames_to_plain_text`。
- 2026-09-19 — R103 控制组与变异：仓库外副本 `%TEMP%\fnaudio-r103-mut` 先跑控制组 ✓ Python 定向 518 项 + 69 个 `test_*.js` 全绿才允许进入变异。变异 X1~X12 第一轮 X6（先展开 unsync 后剥 indicator）与 X10（`major != 4` 写成 `major < 4`）存活 ✓ 逐个查因：X10 在 `major` 取 3 或 4 时与正确实现同行为 ✓ 只有 `major > 4`（v2.5 标签确实会走到这里）才可分辨；X6 在 indicator 四字节不含 `FF 00` 时同行为 ✓ 而含 `FF 00` 的畸形 indicator 会让先展开的版本少剥两字节并吞掉真实正文。两者都属于输入不足而非等价变异 ✓ 于是补出可分辨输入后重跑 ✓ 12/12 全灭。副本还原哈希与仓库逐文件一致。
- 2026-09-19 — R103 行号引用复核：本轮改动后重新扫描全仓 `TODO.md:NNN` 形式的引用 ✓ 作用域与上一轮口径一致——`src/` 下 13 处、`tools/` 下 2 处 ✓ 全仓 15 处；本轮新增引用 0 处（新增文档文本使用函数名与偏移表达式引用 ✓ 不用行号）。同时记一笔取证事实：`library.py:70` 导入 `decode_id3_text`、`id3_frame_size` 但当前无调用点 ✓ 属可疑死导入 ✓ 按反增长约束并入本条登记不另立项。
- 2026-09-19 — R103 门禁与净账：`artifacts/offline-20260919-round158.log` 为终跑记录。开放项 112 -> 111 ✓ 可离线代码项 48 -> 47 ✓ 设备/外部 43 ✓ 产品决策 8 ✓ 登记与口径 13 保持不变 ✓ 新立 0 条。`SOURCE_MANIFEST.sha256` 本轮刷新 ✓ 改动文件 `src/app/server/id3_parser.py`、`src/tests/test_id3_parser.py`、`src/app/server/metadata_service.py`、`src/tests/test_metadata_service.py` 均在清单内并逐文件抽查一致。未提交、未 `git add`、未改 `.gitignore` ✓ 设备段未动。 实测：Python Ran 2275 tests（较上轮 +12）OK skipped=2 ✓ JS 门禁 69 行输出对应 69 个 test_*.js 无静默 ✓ 尾部 EXITCODE=0 ✓ 清单 695 条逐条重算 DIFF=0 MISSING=0（门禁后重算仍一致）✓ %TEMP% 本轮脚本与仓库外副本已清零（r103_left=0 mut_left=0 pycache_left=0）。另记一条口径：全仓 `.new` 命中 2 处均为 `tools/runtime/gomodcache*/modernc.org/libc@v1.67.6/surface.new`（实测时间戳 2026-08-11，Go 依赖自带文件，非补丁残留），`.orig/.rej` 为 0；该目录的处置已属既有待办，本轮不另立项。
- 2026-09-19 — R102 修复内容：关掉「被接管的旧请求仍可能在 settle 时写响应缓存 ✓ `getEpoch() === epoch` 是唯一防线」那条弱口。`src/app/ui/library_response_loader.js` 加一个 per-call 的 `cacheWriteVoided` 标记 ✓ URL 交接处（`existing.__fnAudioRelease?.()` 之后）新增 `existing.__fnAudioVoidCacheWrite?.()` ✓ 发布门由 `if (getEpoch() === epoch)` 收紧为 `if (!cacheWriteVoided && getEpoch() === epoch)` ✓ 被弃请求的 `return data` 刻意保留。
- 2026-09-19 — R102 取证（为什么这条不是概率问题）：`state.libraryResponseEpoch` 只在整表失效处自增（`app.js:5245` 的 `clearLibraryResponseCaches()` ✓ `app.js:7647` 的 metadata revision 变更）✓ 而接管发生在同一次视图切换里 ✓ 替换者从 `app.js:5282` 读到的是同一个 epoch 值 ✓ 所以「代次相同」与「所有者已换」可以同时成立 ✓ epoch 结构上不可能区分它们 ✓ 条目原本把这归给「将来若出现观感问题再考虑」✓ 本轮把充分性直接证伪后落地。
- 2026-09-19 — R102 判别性：`src/tests/test_ui_library_response_loader.js` 从 446 行扩到 518 行 ✓ 用既有 vm 环境跑真 loader。新场景的关键是「传输忽略 `signal` 的旧 WebView」：被接管的 `fetchJson` 不看 abort ✓ 晚一步 resolve 出 `dead response` ✓ 旧实现会把它写进缓存并覆盖 `fresh response`。8 条运行时断言（含反向：被弃调用方仍能拿到自己的结果 ✓ 同 URL 之外的后续请求仍能发布 ✓ 槽位仍恰好平衡）+ 4 条源码钉（两道门都在 ✓ 声明早于接管分支 ✓ 钩子早于 `inflight.set` ✓ setter 只有一处）。
- 2026-09-19 — R102 控制组先跑的价值（本轮实测抓到）：源码字面钉 `test_ui_library_loading.js:512` 断言的正是被改写的原句 `if (getEpoch() === epoch) cache.set(url, data);` ✓ 代码改完立刻 68/69 红 ✓ 报错信息「Stale responses, including an older refresh, must not repopulate invalidated cache」。判定为「钉该跟随契约」而不是「改动该收回」✓ 因为新钉要求两道门同时存在 ✓ 是收紧。控制组 A/B 双双 69/69 之后才进变异。
- 2026-09-19 — R102 变异（仓库外副本 `%TEMP%\fnaudio-r102-mut` ✓ 只拷 `src` 与 `android-client\app\src`）：W1 发布门退回只看 epoch ✓ W2 接管处不再作废 ✓ W3 作废钩子改空函数 ✓ W4 标记初始为 true（过度作废）✓ W5 标记提升到 loader 作用域（跨请求泄漏）✓ W6 标记声明挪到接管分支之后 ✓ W7 作废连带吞掉调用方拿到的结果 ✓ W8 钩子装到 `inflight.set` 之后 ✓ W9 删掉 epoch 只留 void ✓ W10 删掉原有的槽位移交。10/10 全灭 ✓ 其中 W6/W8 属于行为等价的顺序变异 ✓ 只被结构钉杀掉 ✓ 如实记录：它们证明钉有效 ✓ 不证明运行时行为。副本还原后与仓库同哈希。
- 2026-09-19 — R102 行号引用复核：代码侧 `TODO.md:NNN` 引用本轮按磁盘重取为 `src/` 13 处 + `tools/` 2 处 = 全仓 15 处 ✓ 此前记录里的「13 处」是只扫 `src/` 的口径 ✓ 本轮起把作用域写进计数本身以免两份数字看起来互相矛盾 ✓ 本轮新增 0（新写的注释一律用轮次号 R102 与函数名 ✓ 不再新增行号引用）。顶部块插入一条使既有引用再 +1 ✓ 该漂移是 R100 已登记的旧债 ✓ 本轮继续只取证不偿还 ✓ 未据此新立项。
- 2026-09-19 — R102 门禁与净账：终跑 `artifacts/offline-20260919-round157.log`（记录与 manifest 都写完之后再跑 ✓ 期望 Python 2263 项 `OK (skipped=2)` ✓ JS 69 条 checks ✓ exit 0）✓ `SOURCE_MANIFEST.sha256` 刷新后逐文件抽查 `library_response_loader.js`、`test_ui_library_response_loader.js`、`test_ui_library_loading.js` 三个改动文件 MATCH ✓ 净账：开放项 113 -> 112 ✓ 可离线代码项 49 -> 48 ✓ 设备/外部 43 未动 ✓ 决策 8 未动 ✓ 登记/口径 13 未动 ✓ 新立 0 ✓ 类别移动 0。
- 2026-09-19 — R102 接管复核（上一轮在「格式测试」一步中断 ✓ 由 Codex 接手补齐收尾）：收尾前先从磁盘重取全部计数而不是沿用汇报；`test_change_record.py` 定位到 `src/tests/` 并以门禁同款 `python -B -m unittest discover -s tests -p` 跑绿（3 tests OK ✓ 首跑曾因模块名错报 ModuleNotFoundError）；manifest 刷新为 695 条后全量重算 DIFF=0 MISSING=0 ✓ 另加 `app.js` 共 4 个文件逐个 MATCH ✓ root 三份 .md、`tools/test_offline.ps1` 与 `artifacts/*.log` 经取证确认不在 manifest 内（`grep=0`）故文档更正不触发刷新；round157 终跑复核 `OK (skipped=2)` 之后恰好 69 行非空 JS 成功输出 ✓ 与 69 个 `src/tests/test_*.js` 一一对应且无静默文件 ✓ `%TEMP%` 下 `fnaudio-offline-pycache-*` 残留 0；控制组在仓库外副本上重跑 69/69 先绿 ✓ 随后 W1~W10 逐个重放全部被杀（W6/W8 仍只由结构钉拦截 ✓ 与上文口径一致）✓ 副本还原哈希与仓库一致；`TODO.md:NNN` 引用口径按作用域改写见上一条 ✓ 收尾后 `test_change_record` 再跑仍绿；未提交、未 `git add`、未碰 `.gitignore`、设备段未动。
- 2026-09-19 — R101 修复内容：关掉「poll 路径每轮两次 `syncPlayerProgress()`」那条结构重复。`updateNowMarquee()` 结尾原本挂了一次 `syncPlayerProgress()` ✓ 于是 1.5s 渲染轮询里 `updateIncomingRendererUi()`（自带绘制）与随后的 `updateNowMarquee()` 各画一次传输行 ✓ 每 tick 两次；`window.addEventListener("resize", updateNowMarquee)` 也因此把每次窗口缩放变成一次进度重绘。本轮删掉那次隐式绘制 ✓ 换成 restore / 载入×3 / DAC 切换 / boot 六个归属点各自显式一次 ✓ resize 回到纯几何。
- 2026-09-19 — R101 取证（先推翻条目建议）：条目写的方案是「合并」并附前提「复核 `updateNowMarquee()` 其余 8 处调用点是否都隐含依赖它顺带刷新进度」。逐点读毕的结论是前提不成立：该函数第一行就是 `if (document.body.classList.contains("mobile-search-active")) return;` ✓ 移动端搜索态下隐式那次绘制根本不执行 ✓ 所以没有任何调用点可以合法依赖它；真正的绘制归属分别是 `updateIncomingRendererUi`(:2125 轮询)、`updateRemoteUi`(:2108 外放 500ms tick)、原生状态泵(:907)、`audio.ontimeupdate`(:8165) 与 `audio.onloadedmetadata`(:8185) ✓ 本地播放的推进一直由音频元素自己驱动 ✓ 与 marquee 无关。因此按「各归属点显式绘制」实现 ✓ 而不是把两次合并成一次共享调用。
- 2026-09-19 — R101 判别性：`src/tests/test_ui_renderer_transport.js` 从 145 行扩到 220 行 ✓ 新增第二个 `vm.runInNewContext` 用真 `updateNowMarquee` + 真 `syncPlayerProgress`/`syncNowPlayingTime`/`setTextContentIfChanged`/`clock`/`setPlayButton`/`updateIncomingRendererUi`/`renderIncomingRendererSession` 组合运行 ✓ `updateSeekRail` 桩作唯一可观测量（`requestAnimationFrame` 桩不执行回调 ✓ 但 marquee 体已完整走到尾部）✓ 断言「一次 `renderIncomingRendererSession()` 的绘制计数 == 1」「裸 `updateNowMarquee()` 不改变计数」「`updateIncomingRendererUi()` 自己仍算一次」。源码级另钉 15 条：成对的 `syncPlayerProgress();` + `updateNowMarquee();` 恰好 6 处 ✓ marquee 体内不得再出现该调用 ✓ `updateIncomingRendererUi`/`updateRemoteUi`/`restoreLibraryNowPlaying` 各自保留一次 ✓ resize 仍是裸引用且不得包一层带绘制的闭包。
- 2026-09-19 — R101 本轮自我更正（判别性测试第一版有一条假断言）：初稿把「`audio.ontimeupdate` 仍自己绘制」写成 `/audio\.ontimeupdate = \(\) => \{[\s\S]*?syncPlayerProgress\(\);[\s\S]*?updateMediaSessionPosition\(\);\n\};/` ✓ 变异 Q7（删掉 :8165 那次调用）当场存活：惰性匹配跨过处理器的 `};` 跑到下一个处理器里找到了同名的三行 ✓ 于是改用列零 `^\};` 终止的整块抽取 + 块内断言行首行尾的独立调用 ✓ 并顺带把 `onloadedmetadata` 与 `window.fnAudioNativeOnState` 纳入同一形状（Q9/Q10）。改完 Q7 才被杀掉 ✓ 判别性测试自己也要过变异关。
- 2026-09-19 — R101 变异（仓库外副本 `%TEMP%\fnaudio-r101-mut` ✓ 只拷 `src` 与 `android-client\app\src` ✓ 不整目录拷 `tools` ✓ 因为 `test_ui_android_bridge.js` 读 14 处仓库根相对路径 ✓ 副本控制组同样 69/69 绿）：Q1 把隐式 sync 加回 marquee 尾部 ✓ Q2 删 restore 的显式 sync ✓ Q3 删 boot ✓ Q4 一次删三条载入 ✓ Q5 把 sync 移进 `requestAnimationFrame` 回调 ✓ Q6 从 `updateIncomingRendererUi` 删掉 ✓ Q7 从 `audio.ontimeupdate` 删掉 ✓ Q8 把 resize 改成带绘制的包装闭包 ✓ Q9 删原生状态泵 ✓ Q10 删 `onloadedmetadata` ✓ 十个变异先全部过 `node --check` ✓ 结果 10/10 全灭（Q1→运行时计数 2≠1 ✓ Q2/Q3/Q4→恰好 6 处的计数钉 ✓ Q5→marquee 体不得含调用 ✓ Q8→resize 裸引用 ✓ Q9/Q10→块内断言 ✓ Q6 由既有 `--seek-fill` 断言在第 96 行先杀 ✓ 新写的运行时计数同样覆盖它）。控制组 69 个 JS 文件在矩阵前后各全绿一次 ✓ 恢复后副本 `app.js` 与仓库逐字节同哈希。
- 2026-09-19 — R101 行号引用复核（R100 判定为「非缺陷、单独一轮处理」的既有债 ✓ 本轮只做取证不做偿还）：顶部块插一条会让全仓 `TODO.md:NNN` 引用全体 +1。逐条落点核对：全仓引用 13 处 ✓ R101 自身新增 0 处（新写的注释一律用 `R101` 轮次名与函数名 ✓ 不再引入会漂移的行号）。
- 2026-09-19 — R101 门禁与净账：终跑 `artifacts/offline-20260919-round156.log`（本轮记录写完之后 ✓ 期望 Python 2263 项 `OK (skipped=2)` ✓ JS 69 条 checks ✓ exit 0 ✓ manifest 695 条 ✓ 逐文件抽查与门禁后 `%TEMP%` 一次性字节码缓存残留 0 个 = R100 那处修复的回看）。净账：开放项 114 -> **113** ✓ 可离线代码项 50 -> **49** ✓ 新立 0 条 ✓ 本轮净关一条既有代码待办 ✓ 关闭所需的判别性断言全部并入既有 JS 文件 ✓ 未新增测试文件 ✓ 未提交 ✓ 未 `git add` ✓ 未碰 `.gitignore` ✓ 设备段未动。
- 2026-09-19 — R100（接管轮）修复内容：`localPlaybackDuration()` 的「调用方已排除 remote」前提从注释承诺升级为运行时防线 ✓ `isRemoteTarget()` 下直接 `throw TypeError` ✓ 走的是 R64 条目开的第一条路（函数内断言）✓ 没走第二条（`seekDuration` 拆三入口 switch）：改动面大 ✓ 而断言已经覆盖该前提的实际风险面 ✓ 唯一调用点 `audio.ontimeupdate` 入口的 `if (isRemoteTarget()) return;` 原位保留 ✓
- 2026-09-19 — R100 取证自一次中断：上一段 Harness 在 R99 汇报后又跑了 round152 并死在 JS 套件（`test_ui_playback_authority.js:145` 的 cast 场景被 `localPlaybackDuration` 新断言抛错打死）✓ 04:35:27 最后一笔把断言收窄到只认 `isRemoteTarget()` ✓ 本轮把因果钉死：round152 的红是「断言过宽（把 incoming 投送也当 remote 挡）杀了自己的显示场景」✓ 而投送改变传输行的显示归属但不改变本地收尾的决策权威 ✓ 套件场景 1/9/11 正是带 cast 的合法驱动 ✓ 收窄版复跑绿 ✓ 该笔改动当时未刷 manifest ✓ `test_source_manifest` 因此实跑红 ✓。
- 2026-09-19 — R100 判别性（含一次同轮自我更正）：新增测试 7b——remote 目标下**直接调用** `localPlaybackDuration` 必须 `assert.throws` ✓ cast 活跃下直接调用不炸且仍答本曲时长 20 ✓。本轮初稿写成「崩溃方没留任何直接调用测试 ✓ 全仓没有 `assert.throws` ✓ 删掉断言套件依旧 69 文件全绿 ✓ 没有 7b 断言等于不存在」——那是没做实验的全称断言 ✓ 实测证伪：崩溃方 04:35:27 同时写了 `test_ui_library_loading.js:677-711`（用 vm 把函数体抽出来的直接调用断言 ✓ 还含「incoming 投送不得豁免 remote」和「`audio.ontimeupdate` 必须在触到守卫之前 return」的源码级接线断言）✓ 我方第一次 mtime 扫描只看 `git status` 里带 M 的文件 ✓ 而该测试文件是未跟踪的 ✓ 于是漏看 ✓ 漏看的代价是写下错的记录 ✓ 不是少写一个测试 ✓。
- 2026-09-19 — R100 变异（仓库外副本 `%TEMP%\fnaudio-r100-mut` ✓ 每个变异先过 `node --check` 证明语法合法 ✓ 控制组 69 个 JS 文件在矩阵前后各全绿一次 ✓）：M1 删断言块 → `test_ui_library_loading.js` + `test_ui_playback_authority.js` 双杀 ✓ 把 7b 整段剥掉仍由 `library_loading` 单杀（所以 7b 是第二套 fixture 上的独立守卫 ✓ 不是唯一防线 ✓ 它的边际价值是真实 cast 状态里的本地 cue 曲 20 ✓ 而不是 stub 上下文的 210 ✓）；M2 复刻 round152 的过宽断言 → 两套都杀 ✓ 剥 7b 仍双杀；M3 改成无条件抛 → 两套都杀 ✓ 剥 7b 仍双杀；M4 删调用方提前 return → 两套都杀 ✓ 剥 7b 仍双杀（由接线断言与行为场景各自独立成立）✓ 四例全部 rc=1 ✓ 副本 `app.js` 与测试文件最后逐文件 sha 与仓库一致 ✓。
- 2026-09-19 — R100 第二项修复（新发现当轮修掉 ✓ 不另立条目）：门禁每跑一次就在 `%TEMP%` 下留下一个一次性字节码缓存目录 ✓ 接管时累计 65 个 / 3.04 MB（round154 那一个 57 个文件 / 1.59 MB）✓ 根因是 `tools/test_offline.ps1` 的 finally 只把 `PYTHONPYCACHEPREFIX` 环境变量还原 ✓ 创建目录的一方从不回收它 ✓ 现补捕获 `$offlinePycachePrefix` 与 finally 里的 `Remove-Item -Recurse -Force -ErrorAction SilentlyContinue` ✓ 判别性并进既有那条源码级测试已有的 pycache 断言块（不新增测试方法 ✓ 因此 Python 侧总数不变 2263）✓ 断言除了「有没有删」还钉时机：必须在 `python -B -m unittest discover` 之后、在同一个 finally 的 `Pop-Location` 之前 ✓ 变异 P1 删清理 ✓ P2 删捕获 ✓ P3 把清理挪到运行之前 ✓ 三例在仓库外副本全部被打死 ✓ 控制组 14 条在矩阵前后各绿一次 ✓ 副本与仓库逐文件 sha 一致 ✓
- 2026-09-19 — R100 门禁与净账：终跑 `artifacts/offline-20260919-round155.log`（本轮两项修复与全部记录更正完成之后 ✓ round153/154 之后又被代码改动作废 ✓ 只算中间跑 ✓）：Python 2263 项 OK (skipped=2) ✓ exit 0 ✓ JS 侧按日志尾部逐行取证：`OK (skipped=2)` 之后 69 行成功输出 ✓ 与 `src/tests/test_*.js` 69 个文件一一对应 ✓ `SOURCE_MANIFEST.sha256` 刷新为 695 条 ✓ 695 条逐条与磁盘重算 DIFF=0 MISSING=0（另用 `certutil` 独立复算 4 条抽查 ✓）✓ 设备段/决策段本轮未动一字 ✓ 计数按小节口径从磁盘重新取证（不引用旧快照）：净账 开放项 115 -> **114** ✓ 可离线代码项 51 -> **50** ✓ 新立 0 条 ✓ 未提交 ✓ 未 git add ✓ 未碰 .gitignore ✓ 终跑之后 `%TEMP%` 里 `fnaudio-offline-pycache-*` 残留 0 个（第二项修复的直接验证 ✓ 接管前的 65 个已清）。另取证一项非缺陷并当轮证伪：源码注释里的 `TODO.md:NNN` 是行号引用 ✓ 顶部块每轮插一条就全体 +1 ✓ 逐条取证 12 处引用 ✓ 本轮之前已有 8 处指错（只有 `library_response_loader.js:18` 的 `:107` 仍对）✓ 本轮自己的插入又把它指向条目的 3 处 `:49` 推到 50 行 ✓ 无测试与门限依赖这个数字 ✓ 条目正文在注释里是完整复述的 ✓ 因此不新立条目 ✓ 也不在这一轮擅自换引用风格：那要连既有 9 处一起改 ✓ 该单独一轮做 ✓。
- 2026-09-19 — R99 修掉投送结束后的残留数字：`restoreLibraryNowPlaying()` 的空选择分支过去只重写标题/艺术家/封面 ✓ `#elapsed` `#duration` `#seek` 与播放图标留着投送曲目最后状态 ✓ 于是「未选择曲目」旁边是 1:40 ✓ 新增 `resetTransportRow()` ✓ 复用停止路径与新载入路径已有的同一写法 ✓ 另加 `updateSeekRail(0)` 让填充条跟着归零 ✓ `setPlayButton(false)` ✓ 和清掉 `state.remoteUiLast`（那份 memo 描述的是刚结束的投送会话 ✓）✓
- 2026-09-19 — R99 的落点与条目建议不同并且有理由：条目建议放在 `refreshRendererSession` 的 `previousActive && !active` 分支 ✓ 但那里只在会话结束的那一个 tick 触发 ✓ 之后任何一次回到曲库都不再复位 ✓ 而 `!item` 分支正是「视图已回到曲库且本地没有曲目」的 唯一时刻 ✓ 同时另有一半被反向钉住：本地有曲目时**不得**清零（那一行归本地播放所有 ✓ 变异 V2 就是越界的版本 ✓ 被杀 ✓）✓
- 2026-09-19 — R99 关掉「now-playing 其余文本无条件重写」：取证发现这条要的口径早已落实 ✓ app.js 里 79 处 `textContent =` 中 没有一处直接写这五个节点 ✓ `--seek-fill` 只出现在带比较的写入器里 ✓ 所以本轮不猜性能、只补机检：五个节点的直接赋值禁令 ✓ helper 必须保持比较 ✓ `--seek-fill` 字面量只允许一处 ✓ 并明确记录「真实 WebView 上是否减少布局失效仍未测」✓ 不当性能结论用 ✓
- 2026-09-19 — R99 判别性与变异：新增断言全部在 JS 侧（`test_ui_library_loading.js` ✓ 其中复位行为是真的把 7 个函数抽进 vm 跑 ✓ 假节点计写入次数 ✓ 因此「二次调用不再改 DOM」也被钉住 ✓）。仓库外副本控制组两套 JS 套件先绿 ✓ 变异 8 例全部被杀死：删复位调用 ✓ 复位越界到有曲目分支 ✓ 不清 memo ✓ 不复位填充 ✓ 不复位图标 ✓ 改成无条件写文本 ✓ 去掉 helper 的比较 ✓ 进度条绕过守卫 ✓
- 2026-09-19 — R99 门禁与净账：`artifacts/offline-20260919-round151.log（写完记录之后的复跑 ✓ round150 是同数的前置跑 ✓）`：Python **2263** 项 `OK (skipped=2)`（与上一轮同数 ✓ 本轮新增断言在 JS 侧 ✓）✓ 68 条 checks passed ✓ exit 0 ✓ `SOURCE_MANIFEST.sha256` 695 条 ✓ `app.js` 与 `test_ui_library_loading.js` 逐文件 sha MATCH ✓ 分类器 `moves 0` 稳定 ✓ 净账：开放项 117 -> **115** ✓ 可离线代码项 53 -> **51** ✓ 新立 0 条 ✓（本轮另有一处自伤记录在案：`test_ui_library_loading.js` 要在工作目录下用 `src/` 相对路径跑 ✓ 直接 `node src\tests\...` 会以 `C:\path\to\fnAudio\app\ui\app.js` 找不到文件失败 ✓）✓
- 2026-09-19 — R98 关掉曲库并发上限的隐式耦合：`library_response_loader.js` 里 `Number([])`、`Number([[]])` 都是 0 ✓ 而 `activeCount() >= limit` 在 0 之下会拒掉**每一个**曲库请求 ✓ 原先 `Math.max(0, Math.floor(x))` 又把所有负数钳到同一个 0 ✓ 于是一个越界输入就静默变成「整个曲库关掉」✓
- 2026-09-19 — R98 为什么走条目的第二条路而不是第一条：取证发现 `test_ui_library_response_loader.js:152-159` 已经把「显式 `0` 与 `"0"` = 没有预算」钉成契约 ✓ 所以「把 0 也归入无效即回落默认」不是不能用而是会推翻既有决定 ✓ 我第一版正是这么写的 ✓ 被套件当场打回 ✓ 最终改成只让**意外塌到 0** 的输入回落默认（对象/数组 ✓ 负数 ✓）✓ 显式 0 仍然禁用 ✓
- 2026-09-19 — R98 判别面：8 个退化取值（`[]` ✓ `[[]]` ✓ `-5` ✓ `-0.5` ✓ `"-7"` ✓ 空串 ✓ `null` ✓ `true` ✓）在「已有一个请求在飞」的条件下必须仍放行一次 ✓ 这个条件是刻意的：它把「回落默认 32」与「退化成 1」分开 ✓ 另重申显式 0 仍拒 ✓ 上限 32 仍生效 ✓
- 2026-09-19 — R98 变异 8 例全部由 JS 套件杀死（控制组先绿 ✓）：去掉对象回落 ✓ 去掉负数回落 ✓ 我的第一版（所有 0 都回落 ✓ 破坏契约 ✓）✓ 删掉空串规则（我编辑过程中真实发生过的自伤 ✓）✓ 去掉上限钳制 ✓ 默认值改成 1 ✓ 上限常数改成 64 ✓ 非有限值不再回落 ✓ 其中后四例早被既有断言覆盖 ✓ 本轮净增量是前两例与那条重申 ✓ 不冒领 ✓
- 2026-09-19 — R98 门禁与净账：`artifacts/offline-20260919-round149.log（写完记录之后的复跑 ✓ round148 是同数的前置跑 ✓）`：Python **2263** 项 `OK (skipped=2)`（与上一轮同数 ✓ 本轮新增断言在 JS 侧 ✓ 未新增 Python 测试 ✓ 68 条 checks passed ✓ exit 0 ✓）✓ `SOURCE_MANIFEST.sha256` 695 条 ✓ `library_response_loader.js` 与 `test_ui_library_response_loader.js` 逐文件 sha MATCH ✓ 分类器 `moves 0` 稳定 ✓ 净账：开放项 118 -> **117** ✓ 可离线代码项 54 -> **53** ✓ 新立 0 条 ✓
- 2026-09-19 — R97 关掉两条同一种缺陷：`tools/benchmark_large_library.py` 的合成库形状不再随规模变化。专辑数原本是恒定 2000（`index % 2000` ✓ 与曲目数无关 ✓），而这条链路要守的游标收益只在组数上万时可见（同版本八轮实测 2.05-2.63 ms 全重叠 ✓）；现在 `ALBUMS_PER_TRACK = 8` ✓ 2500 曲目 → 312 组 ✓ 100k → 12500 组 ✓ 1M → 125000 组 ✓。
- 2026-09-19 — R97 补上这条点名要的宽目录夹具，但**证伪了它开的配方**：条目建议直接 `executemany` 造 `folders` 行 ✓ 取证 `library.py:1566-1588` 后发现文件夹搜索页是「把命中曲目折成递归 CTE ✓ 再逐目录 EXISTS」✓ 一个不含曲目的合成目录永远不会出现在搜索结果里 ✓ 那样造出来的夹具是恒空的 ✓ 改成让四分之一曲目各自占一个叶子目录（同一父目录 `Wide` ✓ 兄弟数 625 / 5000 / 25000 随规模 ✓ 由 `_rebuild_folders` 派生 ✓ 不新增曲目行 ✓ 基准总耗时未变 ✓）。
- 2026-09-19 — R97 实测宽形状确实让搜索通道变得可测：20k 曲目下目录搜索页 7.39 ms ✓ 同一基准里无搜索的目录页 2.20 ms ✓ 约 3.4 倍 ✓ 而兄弟数从 625 涨到 5000（8 倍 ✓）耗时只涨 1.6 倍 ✓ 说明代价由曲目规模主导而不是逐兄弟 ✓ 这正是 R58 折算要守的性质 ✓ 计划硬守卫已加在基准自己身上（必须出现 `idx_folders_root_parent_name_nocase_asc` ✓ 且无 `TEMP B-TREE` ✓ 否则 RuntimeError ✓）。
- 2026-09-19 — R97 判别性与变异：新增 1 条机检测试（形状函数的规模关系三档取值 ✓）并把 6 处 2000 / 4 处 80 的字面对齐到新形状 ✓ 搜索页返回数、兄弟数、计划文本、无 TEMP B-TREE 全部断言。仓库外副本控制组 19 条先绿 ✓ 变异 7 例全部被杀死：Y1 专辑数退回恒定 2000 ✓ Y2 根本没有宽父目录（旧形状 ✓）✓ Y3 深层计数没先压缩（同余塌成 61 个顶层目录 ✓ 我差点写进去的真实坑 ✓）✓ Y4 搜索页量到窄目录 ✓ Y5 守卫写错索引名 ✓ Y6 兄弟数写死常量 ✓ Y7 搜索页丢掉 limit ✓
- 2026-09-19 — R97 门禁与净账：`artifacts/offline-20260919-round147.log（写完记录之后的复跑 ✓ round146 是同数的前置跑 ✓）`：Python **2263** 项 `OK (skipped=2)`（2262 + 1 ✓ 与新增测试数一致 ✓）✓ 68 条 checks passed ✓ exit 0 ✓ `SOURCE_MANIFEST.sha256` 695 条 ✓ `test_large_library_benchmark.py` 逐文件 sha MATCH ✓ 分类器 `moves 0` 稳定 ✓ 净账：开放项 120 -> **118** ✓ 可离线代码项 56 -> **54** ✓ 新立 0 条 ✓ 本轮一次净关两条（同一缺陷家族 ✓ 两条都有各自的判别断言 ✓ 不是把两条并成一条证据 ✓）。
- 2026-09-19 — R96 关掉 UPnP 探测偏置：`discover_upnp()` 原先按 SSDP 应答到达顺序花掉 16 个描述请求名额 ✓ 注释说「后面的 refresh 会继续探测其余设备」只在应答顺序变化时偶然成立 ✓ 于是 NAS 上那些毫秒内应答的服务永远占满名额 ✓ 深雨 RF 位置的音箱永远进不了渲染器列表 ✓ 现在按「上一轮没被问过的优先」轮转选取 ✓
- 2026-09-19 — R96 同时补上这条要求的另一半，并且代码证明了为什么两半必须一起做：`online` 本来就是「上一次描述请求拿到控制 URL」（`control_point.py:468` ✓ 两轮之间无人重新 ping ✓）✓ 发布处却是整表替换（:499 ✓）✓ 而投影层只有设备在列表里才谈得上 `selected`（`playback_targets_presentation.py:136` ✓）✓ 所以只轮转不保留，恰好在轮转跨过它的那一轮把用户已选目标弄丢 ✓ 新增 `retain_unprobed_devices()` 在发布时合并 ✓ 保留项标 `probed=False` ✓ 上限沿用 128 ✓ 不新造常数 ✓
- 2026-09-19 — R96 的一个真实回退：第一版按轮转顺序输出设备列表 ✓ 而目标列表是照单传的（`playback_targets_presentation.py:132` ✓）✓ 意味着 UI 里的目标每轮重排一次 ✓ 变异 X2 就是这一版 ✓ 现在只有「问谁」轮转 ✓ 遍历与输出仍按到达顺序 ✓ 并由测试钉住「轮转跨过它的那一轮，输出顺序不得变」✓
- 2026-09-19 — R96 判别性与变异：新增 4 条离线测试（3 应答者配 2 名额：第二轮必须问到第一轮没问的、两轮合覆盖 3 个、预算够用仍按到达顺序全探测、worker 真的在合并发布 ✓ 加上保留语义的不重复/不越限/标记三项 ✓）。仓库外副本控制组 69 条先绿 ✓ 变异 8 例全部被杀死：不轮转、连输出一起轮转、不回写记忆、只在成功时记账、发布回到整表替换、保留时不查重、保留不顾上限、保留项不标 `probed` ✓
- 2026-09-19 — R96 三处自伤全部记在案：`global _UPNP_LAST_PROBED` 写在名字使用之后 ✓ 整个模块 SyntaxError ✓ 要到被导入才暴露 ✓ 假 socket 用有限 `side_effect` 列表 ✓ 而 `except socket.timeout: continue` 会读穿列表抛 StopIteration ✓ 得像真实窗口那样持续抛超时 ✓ X1 一开始是靠变异自己的 NameError 崩掉的 ✓ 证据不干净 ✓ 收窄锚点重跑才算 ✓ 门禁终跑 `artifacts/offline-20260919-round145.log`（写完记录之后的复跑 ✓ round144 是同数的前置跑 ✓）：Python **2262** 项 `OK (skipped=2)`（2258 + 4 ✓ 与新增测试数一致 ✓）✓ 68 条 checks passed ✓ exit 0 ✓ `SOURCE_MANIFEST.sha256` 695 条 ✓ 分类器 `moves 0` 稳定 ✓ 净账：开放项 121 -> **120** ✓ 可离线代码项 57 -> **56** ✓ 新立 0 条 ✓
- 2026-09-19 — R95 按 `:70` 的要求先取证再动手：不带 `root` 的文件夹页确实是活路径（`app.js:5745` 只在选中根时才 set `root` ✓ `server.py:908` 缺省成空串 ✓ `library.py:1562` 于是走 `WHERE f.parent = ?` ✓ 而 `idx_folders_root_parent` 以 `root` 打头用不上 ✓）。计划实测 `SCAN f / USE TEMP B-TREE FOR ORDER BY`。
- 2026-09-19 — R95 的修法与实测：在 `library.py:2273` 之后补上条目开出的那对 `(parent, name COLLATE NOCASE <dir>, path)` 索引。裸 SQL 2 万行 0.99 ms -> 0.05 ms；走真函数 `query_library_folders` 的 10 万行分页 5.84 ms -> 1.27 ms（约 4.6 倍 ✓ asc/desc 都量 ✓）。带根那条通路的计划与耗时未变（0.04~0.05 ms ✓ 仍走 `idx_folders_root_parent_name_nocase_asc` ✓）。
- 2026-09-19 — R95 把这条点名的写放大也量了而不是略过：同一批 2 万行重建 100.97 ms -> 146.49 ms（约 +45% ✓ 每个目录行约 5.0 µs -> 7.3 µs ✓），盈亏平衡约 45 次无根浏览换一次全量重建。语义未动：同一 parent 串跨两个根时，无根列表仍跨根返回，测试同时钉名字序与根集合。
- 2026-09-19 — R95 判别性与变异：新增 `test_folder_pages_without_a_root_seek_by_parent_in_both_orders`（两个方向各断言用上对应索引且无 `TEMP B-TREE` ✓ 反向断言带根查询仍用根索引 ✓ 最后断言结果集未变窄）。仓库外副本 7 例变异全部由它杀死，控制组 131 条先绿：少建任一个方向、只建 `(parent)`（正是探针里残留的临时排序 ✓）、建成 `(root,...)`、把无根分支改成要求 root、误用 UNIQUE、以及复用已有索引名让 `CREATE INDEX IF NOT EXISTS` 静默不建。
- 2026-09-19 — R95 两处自伤记录在案：写测试时漏掉 `EXPLAIN QUERY PLAN` 前缀，两条断言其实在跑真查询，靠断言消息里出现文件夹名而不是计划文本才发现；第一次走真函数的测量夹具没 `commit()`，返回 0 行却报出 1.27/0.47 ms 这样看着正常的数字，比一眼行数才没把废数写进文档。门禁终跑 `artifacts/offline-20260919-round143.log`（写完记录之后的复跑 ✓ round142 是同数的前置跑 ✓）：Python **2258** 项 `OK (skipped=2)`（2257 + 1 ✓ 与新增测试数一致 ✓），68 条 checks passed，exit 0；`SOURCE_MANIFEST.sha256` 695 条，`library.py`、`test_library_sqlite.py` 逐文件 sha MATCH；分类器 `moves 0` 稳定。净账：开放项 122 -> **121**，可离线代码项 58 -> **57**，新立 0 条。
- 2026-09-19 — R94 关掉「每条日志重复加固目录」：`Observability.write()` 每记一行都要跑完整的 `secure_directory()`（约六次系统调用）再 `secure_file()`。新增 `file_permissions.secure_directory_on_drift()` 与 `secure_file_on_drift()`：一次 `os.lstat` 同时回答「是不是符号链接、是不是目录、模式是否等于要求值」，三项都对齐就直接返回，任何一项可疑原样回落既有函数，因此符号链接拒绝与缺失目录创建两种语义一点没丢。
- 2026-09-19 — R94 没有采纳该条建议的「有界已加固集合」：集合记住「加固过」之后，外部把 `logs/` 改权限就再也看不见 ✓ 这正是要防的风险 ✓ 漂移探测付一次 lstat 换取仍然能发现改坏，稳态成本仍远低于整轮加固。实测 200 次目录加固 6.075 ms -> 1.060 ms（约 5.7 倍 ✓），「每条日志的探测次数 4+ -> 2」这句事后被自己否证：本机旧写法的 `os.lstat`/`os.stat` 计数是 0 ✓ 收益只由计时证明 ✓ POSIX 上旧写法每行还多一次真 chmod ✓ 本机证不了就不假装证了 ✓。轮转出的 `.1` 故意保留完整加固（每 `MAX_LOG_FILE_BYTES` 才一次 ✓ 不是每条 ✓）。
- 2026-09-19 — R94 的测试钉法有两个坑值得记：(1) 断言「不再跑整轮加固」不能 patch 函数名——`observability` 之前用 `from file_permissions import secure_directory` 绑定了名字 ✓ patch 源模块打不到调用点 ✓「退回整轮加固」的变异一开始存活 ✓ 改成经模块属性调用并按真实 `os.lstat` 次数断言（20 行必须恰好 40 次探测 ✓ 两个不同路径 ✓）后才被杀死 ✓ 但这条断言的性质要写清：本机旧写法一次 lstat 都不走 ✓ 它杀变异靠的是「漂移助手从探测清单里消失」这个接线指纹 ✓ 成本收益另由计时单独证明（事后专门数了一遍才发现这点 ✓）；(2) Windows 下 `_chmod` 在 `file_permissions.py:85` 提前返回 ✓ 断言「加固后的模式」会白过 ✓ 所以四条分支用伪造 `st_mode` 驱动。
- 2026-09-19 — R94 变异矩阵 10 例（目录侧 D1-D5：退回整轮、漂移不修、每行仍 chmod、把普通文件当日志目录、缺失当已加固；文件侧 F1-F5：退回每行完整 chmod、漂移不修、把目录当文件、缺失报成功、整体退化成空操作）全部由本轮新测试杀死 ✓ 控制组 297 条先绿 ✓ 另记一条等价性：去掉 `S_ISLNK` 判定项是等价变异（`S_IFLNK` 与 `S_IFDIR` 互斥 ✓ 真符号链接必然 `S_ISDIR` 为假 ✓ 仍走兜底 ✓），去掉 `not S_ISDIR` 项才可被测出 ✓。既有测试 `test_concurrent_log_writes_stay_serialized` 的锁内观测点从单个 `secure_file` 扩成两个加固入口，锁语义未变。
- 2026-09-19 — R94 终跑 `artifacts/offline-20260919-round141.log`（写完整份记录之后的复跑 ✓ round140 是同数的前置跑 ✓ round137/138 是更早状态 ✓ round139 曾判红一次：我在同一条命令里把清单刷新排在门禁之后 ✓`test_source_manifest` 正确地咬住这个 sha 过期 ✓ 顺序错误不是代码缺陷 ✓） Python **2257** 项 `OK (skipped=2)`（2252 + 5 ✓ 与新增测试数一致 ✓），68 条 checks passed，exit 0 ✓ `SOURCE_MANIFEST.sha256` 695 条，`file_permissions.py`、`observability.py`、两份测试逐文件 sha MATCH ✓ 分类器 `moves 0` 稳定。净账：开放项 123 -> **122**，可离线代码项 59 -> **58**，新立 0 条。
- 2026-09-19 — R93 证伪了一条待办的前提又修出它背后的真缺陷：`metadata_assets` 历史行的存库 mime 并不决定能否出图（`server.py:1807-1808` 由 32 字节前缀裁决 ✓ `cover_media_type.py:113-119` 字节优先 ✓ 且 `test_cover_media_type.py:115` 早已钉住 ✓），但 `metadata_service.artwork()` 在路由决定 404 之前就把 `last_accessed` 刷成当前时间，而回收按 `last_accessed ASC` 选牺牲者（:4087 ✓），等于永久不可服务的资产每被访问一次就续到队尾、最晚回收。
- 2026-09-19 — R93 的改法：`artwork()`（:4569-4582）先用同一个 `safe_image_media_type` 判出可服务类型，判不出来直接返回 None **且不记账**；判得出来才刷新 `last_accessed`，并把由字节解析出的类型回传，历史行本身不改（读路径回写会让每次封面 GET 多一次写事务，且让存量数据取决于看过哪些图）。
- 2026-09-19 — R93 判别性与变异：新增 `test_an_unservable_asset_is_not_renewed_in_the_eviction_queue`（同一行 SVG → PNG 两次装填，前者 None 且 `last_accessed` 仍为 123、`mime` 仍为 image/jpeg，后者 image/png 且续期 > 123）。仓库外副本 6 例变异全部由它杀死，控制组 233 条先绿：Q1 不拒、Q2 拒但续期、Q3 从不续期（过度纠正）、Q4 只信声明、Q5 回传存库类型、Q6 读路径回写历史行。第一轮跑矩阵时 Q6 存活，原因是我那条否定式断言放在了「会产生副作用的调用」之前，补断言后才真正钉住。
- 2026-09-19 — R93 同时关闭 sniffer 读取窗口那条：它要求的「前缀长度做成显式参数并断言其被使用」其实已经存在（`cover_media_type.py:17` 常量 ✓ 在 :59 与 :67 使用 ✓ `test_cover_media_type.py:73` 断言魔数放在窗口之外就不认 ✓ :53 钉下界 12 ✓），零代码改动，按「已被覆盖」关闭而不是再立一项。
- 2026-09-19 — R93 门禁：`artifacts/offline-20260919-round136.log` Python **2252** 项 `OK (skipped=2)`（+1 与新增测试数一致 ✓），68 条 checks passed，exit 0；`SOURCE_MANIFEST.sha256` 695 条、本轮 2 个代码改动文件（`metadata_service.py` 与 `test_metadata_service.py`）逐文件 sha 抽查 MATCH，并连带复核上轮 `cover_readers.py` 仍 MATCH；分类器 `moves 0` 稳定。净账：开放项 125 -> **123**，可离线代码项 61 -> **59**，新立 0 条。
- 2026-09-19 — R92 关掉 `TODO.md:92`：`read_flac_cover()` 遇到 PICTURE 块内部字段撒谎（MIME 长度、描述长度、图像长度越界）时是 `return None, None` 终止整次扫描，与同函数 docstring 承诺的「跳过并继续找下一个块」相反。四支校验收进新的 `_picture_block()`，None 表示跳过这一块；坏块 + 好块必须拿到好块，只有坏块必须返回空而不是崩或返垃圾。
- 2026-09-19 — R92 的判别性证据：把改前代码整段还原成变异 P1，被新增测试杀死（138 条 4 failures ✓），所以「改前不满足承诺」是量出来的；P3（去掉共享封面预算那一项）也被杀，用 `mock.patch` 把 `MAX_COVER_FILE_BYTES` 压到 4 字节来证明这一支真被使用；P2（把 32 字节的门限改严到 64）被杀；P4（信声明的 MIME）由既有两条测试杀死，本轮不冒领。控制组先绿（138 条 OK ✓）。
- 2026-09-19 — R92 也记一次自伤：我按记忆把 FLAC PICTURE 的字段顺序改成「MIME 长度在前、picture type 8 位」，并用七个探针「证明」连规范正确的块都读不出来。错在两处叠加：探针用首字节推块号（`00 00 00 0a` 开头被推成 0 ✓ 七个块全是 STREAMINFO ✓），而 RFC 9639 §8.8 规定 picture type 是 `u(32)` 且排在 MIME 长度之前——原实现的 `data[4:8]` 与仓库夹具都一直正确，我的改动使两条既有测试立刻红（31 条里 2 failures ✓ 正是这两条 ✓），已全部回滚，只留下「跳过而非终止」这一处真缺陷。
- 2026-09-19 — R92 的取证手法补记：id3.org 返回 500、本会话 web_search 端点未配置，所以规范查证走「抓 RFC 全文存 `%TEMP%`、本地按节切片」这条路（225759 字不进上下文 ✓），FLAC 字段表原文落在 `rfc9639.txt` 的 66126 字节附近 ✓ 另把夹具注释从「按读器要走的样子造」改成引用 RFC 条款号，避免测试与实现互相印证。
- 2026-09-19 — R92 门禁：`artifacts/offline-20260919-round134.log` Python **2251** 项 `OK (skipped=2)` 102.872 s（+1 条与新增测试数一致 ✓），68 条 checks passed，exit 0；`SOURCE_MANIFEST.sha256` 695 条，本轮 2 个改动文件逐文件 sha 抽查 MATCH。净账：开放项 126 -> **125**，可离线代码项 62 -> **61**，新立 0 条。
- 2026-09-18 — R91 换了个取证口径，先纠正上一轮报告里的一处错：我说「leading run 之外还有 33 条混合项待归类」，本轮之后 126 条开放项实测量出的构成是 **62 条可离线代码项（56 条在顶部块、6 条散在其他分段）+ 23 条 P0 外部验收 + 8 条需决策 + 20 条已在设备段（宿主 MediaSession 10、Android 6、P2 3、私有会话研究 1）+ 13 条登记/口径类文字**（62+23+8+20+13=126 ✓）；那 33 条里绝大多数早就归在设备段，不存在「等着归类」的一堆。真正的发现是另一件事：改动前 64 条代码项里有 **8 条不在顶部块**（散在 `2026-09-01 持续目标（无需真机）`、`2026-09-08 首屏指标补强`、P3 等段），而历轮只在顶部块里挑目标，等于一直漏看这 8 条——本轮关掉其中 1 条、把其中 1 条纠错归档，仍剩 6 条。
- 2026-09-18 — R91 从被漏看的项里挑了一条，结果比条目本身大：`TODO.md:2173`（本轮归档动作使其行号从 2172 下移 ✓）说 `playback/alsa_output.py:merge_dac_caps()` 是死代码、且会用默认 192000/24 抬高实测能力。实测该函数**在代码里零引用**（`git grep -l` 只命中两份文档），`empty_dac_caps()`（:295）也早已改成未知记 0；但同一个猜测活在下游：`choose_dac_strategy()` 的 `max_rate = safe_int(...) or (... else 192000)` 只在 `source == "unknown"` 时才保守。
- 2026-09-18 — R91 量出后果（`%TEMP%\r91measure.py`）：caps 形状为「stream 文件读得到、速率一条没解析出来」时，176.4 kHz 的文件被直通成 **176400**、384 kHz 的被给成 **192000**，而全空 caps 只给 44100，相差 3 倍多。这一形状不是造的：归档项 `TODO.md:1831` 记着许多驱动打印 `Rates  : 0x33 (44100 48000 ...)`，现有两条正则都匹配不到；本轮另造同样形状的 stream 文件走真解析器复核，得到 `pcm_rates=[]`、`pcm_max_rate=0`、`source` 指向真实路径。
- 2026-09-18 — R91 为什么这条不必等真机：策略算出的 rate 最终喂给 `aplay -D`（`alsa_output.py:929`），设备标识是 `hw:CARD=x,DEV=y`（:498/:620/:652），**`hw:` 不带重采样插件**，多报的天花板不是「保守回退」而是打不开的设备；于是归档项 `:1832` 给的「未知即按源文件直通」可以直接排除，剩下「显式降级」一条路。改法（:810-830）：上限只取实测值，取不到就与 unknown 走同一保守答复（44100）。
- 2026-09-18 — R91 顺手挡住一处我自己差点留下的过度纠正：保守分支最初把 `max_bits` 也压成 16，会连驱动真报过的宽度一起丢掉——而 `Formats: S16_LE S24_LE` 通常读得到（解析在 :354），「只报格式不报速率」恰是真实设备最常见的形状。改成 `max_bits = measured_bits or 16`：保守只作用在真正没测到的项上。
- 2026-09-18 — R91 测试与变异：既有 `test_driver_text_without_rates_stays_unmeasured` 原本**断言的就是 192000**（注释称之为「仍然保守的上限」），按上面的证据改成 44100 并写明理由；新增 `test_an_unmeasured_device_gets_the_same_answer_as_an_unknown_one` 钉三件事（没测到 == unknown、报了速率就不许压到 44100、只报格式时是 (44100, 24) 不是 (44100, 16)）。变异 8 例，控制组 117 条先绿：N1/N2/N3b/N4/N6 全被新测试杀死；N3（拿默认过的变量判断）是 no-op、N5（用速率表判定，因 :347 处 `pcm_max_rate` 恒等于 `max(rates)`）按设计存活；N7 我预判等价，结果被杀——它让默认 24 冒充实测宽度，说明那两条断言各自守约。
- 2026-09-18 — R91 同时按目标 (2) 校正归档：把 `INTERACTIVE_PREWARM_INITIAL_DELAY_SECONDS` / `LIBRARY_PREWARM_DELAY_SECONDS` 那条（正文自己写着「真机项，本机无法验证」却被算进代码项）搬进「P0：外部验收（离线不可验证）」段，并补上需要什么证据（接慢速存储的真机、边播边翻首屏、抓交互请求与预热排队的等待毫秒分布）以及为什么离线造不出这个自变量；`TODO.md:1832` 记为「速率一半已离线定案、位深一半仍等真机 `stream*` 留档」。分类器复核 `moves 0` 稳定。
- 2026-09-18 — R91 门禁：`artifacts/offline-20260918-round132.log` Python **2250** 项 `OK (skipped=2)` 103.215 s（+1 条与新增测试数一致），68 条 checks passed；`SOURCE_MANIFEST.sha256` 仍 695 条，本轮 2 个改动文件 sha 复核 MATCH。净效果：开放项 127 -> **126**，可离线代码项 64 -> **62**（1 条关闭、1 条纠错归档），新立 0 条。
- 2026-09-18 — R90 关掉两条 SUBSCRIBE 解析待办（`:9` 与 `:22`）、新立 0 条：`:22` 说「本轮不做，因为没有任何解析压力实测数据」，那就先量；量出来发现真正要防的是并发，不是次数。剩余可离线代码项 64 条。
- 2026-09-18 — R90 先把洪泛量出来（`%TEMP%\r90measure.py`，只换测试早就存在的 `_callback_url` 替身缝）：**16 个并发 SUBSCRIBE = 16 个 worker 同时卡在 `getaddrinfo` 里，即 32 宽 HTTP 池的 50%**（`server.py:3357` 的 `http_max_workers` 默认 32），32 个就能把 Web UI、`/api/health`、播放控制一起带走；R69 把解析移出锁之后，没有任何东西挡着这条。第二条：表满 64/64 时再来 20 个订阅，**20 次解析全花在注定被上限拒掉的请求上**（`dlna/service.py` 里校验排在 `:450` 的准入判定之前），客户端拿到的都是同一句 `too many event subscriptions`。
- 2026-09-18 — R90 的处置不发明新限流器，复用现成的 `ConcurrencyGate`（`resource_limits.py:77`，HTTP 侧 `http_server.py:17/:21` 就是同一族用法）：事件服务持有 `ConcurrencyGate("gena-callback")`（`dlna/service.py:405`），回调校验包在 `slot(GENA_VALIDATION_LIMIT=4, 1.0 s)` 里（常量 :41-43、调用 :477），4 是 32 的 1/8，与给长驻请求预留的比例同族；饱和时按既有 412 口径拒绝（:483）。复测同一夹具：**峰值 16 -> 4（池的 12%）**，16 个请求 4 进、4 排队、8 直接被 waiter 上限拒，排队的各等满 1 s 后拿到 `event callback validation is busy`，最终 8 成 8 拒；溢出请求 1.02 s 返回，而它前面那次解析还卡着。
- 2026-09-18 — R90 另一处是白烧：解析之前加无 I/O 的确定性预检 `_hopeless_admission_reason()`（`dlna/service.py:417`），只在「已 shutdown」或「表满且无可回收租约」时回答，短暂持一次总线锁、不碰任何 I/O，权威判定仍在解析之后那段锁里（两控制器竞态的语义一字未动），白烧 **20 -> 0**，且两条路径给出的客户端理由逐字相同（测试专门钉这句，防漂移）。观测按 R87 的规矩同时补：`snapshot()` 增加 5 个扁平整数 `validating` / `validation_limit` / `validation_waiter_limit` / `validation_waited` / `validation_rejected`（:594 起），并且先读闸门再拿总线锁，两条路径不交叉持锁。
- 2026-09-18 — R90 没做条目建议的「按 (回调主机, SID 配额) 限」，理由写进关闭结论：那要再养一份以主机名为键的 LRU（上限、租约、逐出一样不少），而这块诊断面的契约就是「不给 callback URL」、`test_cache_status_never_exposes_device_identity` 也不许说对端身份，主机名恰恰就是对端身份；全局并发上界一到位，配额能买的只剩控制器之间的公平。残余量化后记下：单个控制器反复订退订仍可持续占用 4 个位（12% 的池子），真观察到不均再加配额，那时它是公平性功能、不是存活补丁。条目划的第二条红线被本轮证实：把解析结果缓存进取任路径（变异 K8 换成已有的 `_cached_lan_addresses`）立刻被既有 `test_callback_validation_still_resolves_the_host_it_admits` 杀掉。
- 2026-09-18 — R90 的代价与判据都量了：新订阅中位 3.0 µs -> 6.1 µs、p99 3.7 -> 17.8 µs，而本机一次真解析是 13.8 ms（R74），多出的 3 µs 是解析成本的 0.02%；续订仍 1.2 µs 且零解析。测试 4 条（洪泛峰值含反空转、白烧与可回收租约、饱和降级与策略取值、计数形状且渲染里不出现主机名/URL），跑完 1 s 后遗留线程 0（R88 判据）。
- 2026-09-18 — R90 变异 11 例，控制组 143 条先绿：K1/K2/K3（去掉预检、预检忽略可回收租约、忽略 shutdown）杀在预检那条的三个分支；K4（上限写成 32）/K5（闸门整个拿掉）/K6（饱和时不拒反而带着空回调放行）/K10（不发布计数）杀在洪泛那条；K7（等待上界抬到 30 s）杀在「先读策略再看实测」那半条——**这条是被自己的第一版逼出来的**：最初等待上界的期望值是从被测常量算的，实现放宽测试就跟着放宽，补了常量上限断言才杀得掉；K8 见上条；K11（把对端写进计数）杀在隐私那半条；K9（同一个数换个写法）按设计存活。方法学附带一条：本轮又一次用代码行做 edit 锚点结尾，吞掉了下一句 `release = threading.Event()`（R89 吞的是既有测试的 def 行），锚点必须停在语义边界。
- 2026-09-18 — R90 门禁：`artifacts/offline-20260918-round130.log` Python **2249** 项 `OK (skipped=2)` 102.884 s（较上轮 +4），68 条 checks passed；`SOURCE_MANIFEST.sha256` 仍 695 条，本轮 3 个改动文件逐个 sha 复核 MATCH（`dlna/network.py` 本轮未改，仅作变异对照）。
- 2026-09-18 — R89 关掉两条待办、新立 0 条：一条 R65 留的「两条 `NOT IN` 有序子查询要不要合并」，一条 R62 留的「drain 顺序只对 metadata 证明过」。剩余可离线代码项 66 条。
- 2026-09-18 — R89 先把 `:36` 量出来再决定不动代码：封顶 1000 条播放列表时，现有的两条有序子查询 trim best **2.112 ms**，改成按 `keep_ids` 绑定参数的合并版 **1.532 ms**，省 **0.580 ms**；两倍封顶 2.202 对 1.418（省 0.784 ms）；十几条的常见规模 0.060 对 0.034（省 0.026 ms）。两种写法留下的集合逐行相同（`p00000..p00999`、孤儿 0、重复 trim 稳定），条目估的「1 ms 以下」被证实。
- 2026-09-18 — R89 不合并不只是因为收益小：合并版要给父表删除绑定 `len(keep_ids)` 个参数，语句形状就此与上限耦合，而 `:37` 恰恰预期上调那个上限，越过 SQLite `SQLITE_MAX_VARIABLE_NUMBER` 下限 32766 之后换来的是状态保存里的 `too many SQL variables`。这个形状已经有测试守着（`test_state_store.py:755`，参数超过 999 即断言失败），变异 C1（真把合并版套上去）就是被它杀掉的，所以本轮没有新增测试：第一版写了，矩阵显示杀伤力与既有钉法重复，删掉并把结论写进那条测试的注释。附带排掉一个怀疑：trim 的 `state_store.py:216`/`:233` 与恢复侧 `:272` 同为 `ORDER BY created_at ASC`，写入侧归一 `state_projection.py:113` 也保留前 1000 条，三处同向。
- 2026-09-18 — R89 的 `:47` 复审量出一个真洞。全服务端只有 `library.py:1954 library_db_connect()` 打开 `library.sqlite3`，能走到它的曲库入口共 9 个（用 `inspect` 现算：`query_library_page`、`load_items_from_sqlite`、`query_library_groups`、`query_library_item_by_id`、`query_library_items_by_ids`、`query_library_folders`、`query_library_root_folders`、`library_summary_from_sqlite`、以及它自身）；条目点名的三步（transcode 缓存、封面预热、UPnP 后台）连同 `playback/core`、mpd、airplay 一个都不调用，`metadata_service.py` import 的 5 个 library 帮助函数体里 `library_db_connect` 与 `sqlite3.connect` 都是 0。所以那三步的次序是纵深防御，不是承重。
- 2026-09-18 — R89 承重的读者反而在 13 步之外：`server_close()` 排在整个清理循环之后（`server.py:3236-3239`），也从不 join 已在飞的 handler，所以「drain 之后没人再碰句柄」从来不成立——一个还在查询里的 HTTP 请求出来时会把句柄重新放回池子。修法不动顺序，把最后一步换成一次性关闭：`LibraryConnectionPool.stop_accepting()`（`library_connection_pool.py:133`）、`library.stop_library_connections()`（`library.py:1837`）、循环改用（:3229）；`release()`（:104）在非接受态返回 False，调用方按既有契约就地关闭（`library.py:2029-2031`）。`drop()` 保持可重开，因为 `_forget_library_schema`（:1852）和测试在扫描间隙也要 drain。
- 2026-09-18 — R89 的测试与两组变异：既有两条顺序断言合起来只覆盖 11 步和 4 步，`shutdown_upnp_cache_background` 谁都没看过，所以新写的「13 步按名字全钉 + drain 最后」是唯一能杀 C3（把 UPnP 步挪到 drain 之后）的测试，C4（drain 不再是最后一步）、C5/C6（AST 扫出的新增曲库耦合）、D1/D3/D3b/D4（忘记置标志、release 照样收、少记一次 closures、循环仍用可重开的那个）各被指名杀死；C7/D5 是等价的字面改写，按设计存活。控制组先绿（C 组 44 条 1.46 s、D 组 133 条 4.53 s）。
- 2026-09-18 — R89 记两条方法学学费：第一版的句柄扫描按文本数 `library_db_connect`，被自己写在 `library_connection_pool.py` 注释里的名字绊倒，控制组直接变红，改成 AST 扫之后注释与字符串都不再算引用；另一条是变异 D2 证明 `borrow()` 里的第二道 `_accepting` 检查不可达（drain 已清空 idle，`release()` 是唯一入口），于是删掉那道检查而不是给它编一个测试。还有一条代价写清楚：一次性关闭在进程内不可逆，所以 `test_server_lifecycle.py` 四处 `shutdown_runtime()` 全部补了 patch，否则同进程后面的池测试会被静默改变行为（先已经撞到 `test_write_path_never_borrows_a_pooled_handle`）。另记 `shutdown_upnp_cache_background(wait=True)` 的 join 带 `timeout=3.0`（`dlna/control_point.py:548`），卡死的 socket 探测下「stop 返回」不等于「线程已退出」。
- 2026-09-18 — R89 门禁：`artifacts/offline-20260918-round128.log` Python **2245** 项 `OK (skipped=2)` 101.074 s（较上轮 +4），68 条 checks passed；`SOURCE_MANIFEST.sha256` 仍 695 条，本轮 7 个改动文件逐个 sha 复核 MATCH。产品侧改动只在关停路径与池被拒绝时生效，读路径不变。
- 2026-09-18 — R88 关掉两条待办、新立 0 条：一条 R76 留的「跨测试泄漏的线程还在往外拨号」，一条 R74 留的「`_attach_track_ends` 拿文件值当字典键的前提没人钉住」。剩余可离线代码项 68 条。
- 2026-09-18 — R88 先按条目要求量拨号而不是猜：用 `test_zz_socket_guard.external_access_attempts` 在进程内跑整套 2237 条，越界拨号 **0 次**；守卫记到的 8 次尝试（`198.51.100.20:443` 2 + `8.8.8.8:443` 2 + `musicbrainz.org:443` 3 + `203.0.113.9:80` 1）全部由 MainThread 在 `SocketGuardTests` 自己的用例里发出，属设计内。GENA 侧拨不出去的原因也量到了：`shutdown()`（`dlna/service.py:599`）在放行任何排空任务之前先置 `_shutdown`（:603），`_drain_subscription` 第一个判断就是它（:566 直接 return），所以 `mock.patch` 撤销后残留的排空任务发不出 NOTIFY。R76 记的 6 次已经不复存在。
- 2026-09-18 — R88 换了口径才看得见线程：`ThreadPoolExecutor.shutdown(wait=False, cancel_futures=True)`（:610）本就不 join，worker 靠哨兵自行退出，所以「测试那一行还活着」是设计使然而非泄漏。审计改成再等 1 秒比一次，11 条噪声立刻缩成 **2 个真漏**：其一 `AirplayService(...)`/`MpdService(...)` 构造即起 `fnaudio-process-supervisor` 监控线程（`services/process_supervisor.py:222`），只有 `stop()` 或 `shutdown()`（:289）会排空，airplay 7 处构造里 5 处不停、mpd 的 `make_service()` 也不停，该线程一路活到解释器退出；其二库封面预热 worker（`cover_cache.py:1117`），模块早有 `shutdown_library_thumbnail_prewarm`（:1129），页间只睡 `LIBRARY_PREWARM_DELAY_SECONDS = 0.15`（:99）所以 1 秒窗口足够，大库用例就是没调。
- 2026-09-18 — R88 修的过程中出现一个值得记的现象：把 airplay 的 5 处构造统一挂上 `addCleanup(service.supervisor.shutdown)`（新 `_service()`，`test_airplay_service.py:11`/`:21`）之后，审计并没有归零，而是把同一个 `fnaudio-process-supervisor` 改记到 `MpdQueueTests` 头上——归因转移说明这类线程是**构造即起**，逐个测试补清理永远慢一步，得挂在构造点上。于是 `test_mpd_queue.py:69`（内联构造）与 `:89`（工厂）各挂一条，`test_library_cache.py:686` 挂预热关闭。复测：1 秒后仍活 2 -> **0**，进程退出时命名线程为空，剩下 9 条全在一秒内自排空（GENA、renderer backend、转码 reaper）。
- 2026-09-18 — R88 的线程判据是审计本身而不是单测，所以矩阵直接废掉清理机制：S1 让 `ProcessSupervisor.shutdown` 进门就 return -> 审计报 stuck=2 并点名 airplay 用例；S2 让 `shutdown_library_thumbnail_prewarm` 变空操作 -> stuck=1 点名大库用例；S3 只把 monitor 的 join 超时放宽（等价）-> 审计 0 且无破损，说明它测的是漏、不是调用风格。审计脚本留在 `%TEMP%`，不进版本清单，与既有离线探针同一处置。
- 2026-09-18 — R88 第二条先核前提再动手：`metadata_text.py:72 cue_value()` 两个分支都落到 `clean_tag()`，而 `clean_tag` 对非字符串一律返回 `""`，所以走解析器进来的 `file` 确实恒为 str，R74 的判断成立；不成立的是「有人钉着」——`test_cue_parser.py` 里没有任何测试直接调 `_attach_track_ends`，只有端到端用例。归一放在解析器侧（`cue_parser.py:32-40`）：非字符串的轨道不分组、`end = 0.0`、不与任何人共享栈。不折叠成同一个键，因为那会让无关曲目互相截断时长；也不继续依赖上游，因为条目说的正是「以后若允许别的类型进来」。新测试 `test_a_track_whose_file_is_not_a_string_degrades_instead_of_raising` 断言字符串组不受被跳过轨道影响（`[30.0, 0.0, 0.0, 50.0, 0.0, 0.0]`），并断言 `"7"` 与 `7` 不共享栈。
- 2026-09-18 — R88 第二个矩阵（CUE，控制组 19 条 0.030 s 先绿）：B1 去掉守卫 -> 只被新测试抓到（TypeError）；B2 折叠成 `""` -> 新测试的分组断言失败；B3 改用 `try/except TypeError`、B4 同义改写成 if/else -> 按设计存活（等价实现）。方法学记一笔：第一版 B1/B3 的锚点多吞了一行 `name = track.get("file")`，四个变异一起报 14 个 error，那是语法假杀、没有区分度；改成从源文件现取锚点（只截 `if not isinstance` 到 `continue`）之后才有结果。
- 2026-09-18 — R88 门禁：`artifacts/offline-20260918-round125.log` Python **2238** 项 OK（skipped=2）100.311 s，`SOURCE_MANIFEST.sha256` 仍 695 条（本轮改动的 5 个文件逐个 sha 复核 MATCH）。产品侧只新增一个分支，且仅在 `file` 不是字符串时生效，既有真实 CUE 行为不变（三个 CUE 模块 21 条全绿）。另外记一个假失败：把门禁输出接进 `Select-String` 过滤会让 pwsh 以 1 退出（unittest 往 stderr 写的预期内容被提升为错误记录），门禁本身 `OK (skipped=2)`，跨 round123/124/125 三份日志同口径比对确认无关。
- 2026-09-18 — R87 关掉两条待办、新立 0 条：一条 R69 留的「事件面只有一把锁，要不要拆」，一条 R74 留的「这把 LAN 地址缓存没有任何可观测量」。剩余可离线代码项 70 条。
- 2026-09-18 — R87 先给 `:23` 做条目自己要求的竞争测量，结论是不拆锁：64 订阅 × 24 轮 × 50 ms 回调（256 次投递）wall **3.232 s**，而回调睡眠在 4 个 worker 上的并行下界是 **3.200 s**，锁与调度合计 32 ms、摊到每次投递 0.125 ms，占 1%；64 × 16 × 25 ms 那组 1.635 s 对 1.600 s；4 × 8 × 2 ms 那组 0.023 s 对 0.016 s，32 次回调里 31 次的起始时间落在上一次回调的睡眠之内，说明投递确实并行。风暴期间一次真实准入（`subscribe()`）中位 0.026 ms、最大 0.042 ms。
- 2026-09-18 — R87 的方法学反面教训：最初用一个 1 kHz 轮询线程去采「锁等待时间」，结果**探针自己就是竞争源**，把同一组 4×8 风暴从 23 ms 拖到 21.337 s；换成量真实路径（准入延迟、并行下界之差）之后数字才可用。锁等待不是一个可以随便采的指标。
- 2026-09-18 — R87 不拆锁，但把让该结论成立的结构不变量钉住：`fetch_lan` 在锁外（`dlna/service.py:581-588`），finally 段只动计数器（:593-597）。新测试用一个卡住的回调（单 worker）加一次新准入，断言准入在回调仍被卡住时就已经返回。这条断言的位置是第一版写错的：它原本放在放行之后，于是「被阻塞后放行」和「从未被阻塞」两种结果看起来一样，是变异 P1 把它逼出来的——P1（把 `fetch_lan` 挪进 `with self._lock`）现在被新测试与既有 `test_event_shutdown_honors_timeout_while_callback_is_in_flight` 双双杀死，那一轮 wall 9.632 s 对控制组 1.689 s，正是一个不可达控制器拖住整个事件面的样子。附带量到的事实：超过 64 个租约时准入直接拒（:451 `too many event subscriptions`）。
- 2026-09-18 — R87 第二条给 LAN 解析缓存加了条目允许的那一种可观测量：`_LAN_ADDRESS_CACHE_STATS`（hits / misses / expired / evictions，更新点 `dlna/network.py:88`/`:95`/`:97`/`:102`，全部在已持锁的短段内、不做 I/O，符合 R82 那条「锁内不落盘不联网」）与 `lan_address_cache_status()`（:51）。只有计数：不导出主机名、不导出地址、不导出缓存键，函数文档里写明这条约束来自诊断页既有的 `test_cache_status_never_exposes_device_identity`。
- 2026-09-18 — R87 接入方式刻意复用现成页面：在 `upnp_cache_status()` 里加 6 个 `lan_cache_*` 字段（`control_point.py:13` 引入、:578 取值、:601-606 输出，沿用同页 `_bounded_counter`），不新开诊断字段，免得条目警告的噪声源真多一个。为什么要有单独的 `expired`：条目要解释的是「对端搬家后第一次动作为什么慢」，那是租约到期而不是新邻居，两者都算 miss，不拆开就分不出来。计数是进程累计、`clear_lan_address_cache()` 不清零（与旁边的 `refresh_*` 一致），读法永远是两次快照相减——这个口径是被测试踩出来的：第一版按绝对值断言 `misses == 1`，在整套里读到的是 72。
- 2026-09-18 — R87 矩阵八例（控制组 136 条、1.689 s 先绿）：P1（回调放进锁内）、Q1（不记 hits）、Q2（不记 expired）、Q3（把每次 miss 都算成 expired）、Q4（状态里多一个能指认对端的字段）全部被指名杀死；P2（`timeout=3.0`）与 Q5（clear 时清零）按设计存活，后者确实与相减读法等价。新测试三条：`test_a_delivery_in_flight_does_not_hold_the_lock_the_admission_path_needs`、`test_the_status_surface_counts_traffic_without_naming_a_peer`、`test_an_aged_out_entry_is_counted_separately_from_a_first_sight`。
- 2026-09-18 — R87 门限：round123 测试 2237 条、100.451 s、OK (skipped=2)、JS `checks passed` 行数 65、manifest 695 条；开放项 133，活动待办段 93 条，可离线验证代码项 70 条；重跑分类器 moves=0。
- 2026-09-18 — R86 关掉两条待办、新立 0 条：一条 R76 留的「每次连接都跑完整 DDL，是段写事务」，一条 R74 留的「元数据 URL 策略还有一条独立解析路径，先量它热不热」。剩余可离线代码项 72 条。
- 2026-09-18 — R86 第一条是「实现了再回退」：照条目建议加了 `sqlite_master` 读探针（7 个对象齐了就不跑脚本，不做记忆化），跑通之后量不出差别——稳态 50 次连接，带探针 2.4 ms/次、不带 2.2 ms/次。再拿一个 `BEGIN IMMEDIATE` 写者压住库：带探针 2.8 ms、无条件跑 DDL 1.4 ms，**两者都不等待**，因为 `CREATE TABLE IF NOT EXISTS` 对着已存在的对象不加写锁。条目说的「任何并发持有者都会把它变成 5 s 等待」在稳态下不成立。
- 2026-09-18 — R86 量到的唯一会等的场景，恰好是这段脚本存在的理由：删掉 `favorites` 再压住写者，连接实测 **2.087 s**（等满写者提交后重建）——任何探针都跳不过、也不该跳。回退的第二个理由更要紧：留下的收益是零，代价是多一份要和 DDL 手工同步的对象清单，将来给脚本加一张表而忘了加进清单，探针会说「齐了」，那张表就永远不会被创建，这是个静默失效面。
- 2026-09-18 — R86 顺带纠正 `:2` 另外两处：函数叫 `ensure_state_schema`（:120），每个连接只有 :85 一处调用，**没有「三次标记 SELECT」**（`state_meta` 全仓只有一处读，在 `_revision()` :161，属于 load/save 的乐观并发检查，不在连接路径上）；而三个公开入口 :266 / :334 / :402 本来就把连接包在 `_STATE_WRITE_LOCK` 里，进程内串行是设计如此，跟 SQLite 锁无关。本轮改为钉住真正值得防的回归：`test_connecting_while_a_writer_holds_the_database_does_not_wait`，写者压库时稳态连接必须 < 1 s，并先断言写者事务仍不可见，免得断言空转。
- 2026-09-18 — R86 第二条：元数据 URL 闸门量完的结论是「不热，而且不能缓存」。一次主机名调用 = 1 次解析，本机首次 13.8 ms，同一主机 5 条 URL = 5 次解析共 163 ms；字面 IP 与 loopback 一次都不解析（0.04 ms / 0.02 ms）。调用面只有 `_json()`（每次 provider 请求）与 `_download_artwork()`（每张封面），都是动作级、每次出站一个请求解析一次，正合条目自己给的判据。剩下的「重复」是 provider 与 urllib 各解析一次，那是分层的代价，不是这条路径内部的重复。
- 2026-09-18 — R86 为什么这里不能照搬 R74：这个闸门的契约是「任何一个**当前**解析出的地址非公网就拒」。实测把一个解析器排成「先公网、后私有」，第一条 URL 放行、第二条立刻被拒——任何大小、任何 TTL 的缓存都会让第二条通过，而那正是 DNS rebinding。R74 修的是展示路径（答案过期无害），这里过期有害，所以形状一样不等于处置一样。新测试 `test_the_gate_asks_the_resolver_again_for_every_url` 把「每次都重新问」钉成契约：三次调用必须三次解析、字面 IP 必须零次、公网转私有必须第二条被拒。
- 2026-09-18 — R86 矩阵八例（控制组 42 条、1.228 s 先绿）：V1 给闸门加 `_RESOLVED` 缓存被新测试指名杀死；V3 干脆不解析主机名被两条测试杀；V4 让字面 IP 也走解析以 5 个 error 被杀；W1 往 DDL 里塞一条 `INSERT OR IGNORE` 被新测试杀死，那一轮跑了 17.9 s，正是 15 s busy 超时加固定开销，与「把稳态路径变成真写」的推演对上；W2 按路径记忆化（R76 当年踩的坑）被两条既有测试杀死（条目记三条，我这版变异触发两条）。设计内存活两例：V2（调用内部自建 memo、行为不变）与 W3（就是本轮写过又删掉的探针），后者存活本身就是它行为中立的证据。
- 2026-09-18 — R86 门限：round121 测试 2234 条、100.870 s、OK (skipped=2)、JS `checks passed` 行数 65、manifest 695 条；开放项 135，活动待办段 93 条，可离线验证代码项 72 条；重跑分类器 moves=0。
- 2026-09-18 — R85 关掉两条待办、新立 0 条：一条 R70 留的「行数有界但文件不回收」，一条 R71 留的「构建侧两处产物上界仍是字面量」。剩余可离线代码项 74 条。
- 2026-09-18 — R85 先量 `:18` 要的数：favorites-only 夹具下满库 50000 行 = 497 页 × 4096 B = 2,035,712 B（1.94 MiB）、freelist 0；再跑 3 轮裁剪循环（每轮两次 25000 行保存）**页数仍然 497**，freelist 247。也就是说文件被钉在「一张满表」的大小、不随轮次增长，可回收上限就是那 0.965 MiB——条目担心的不回收其实是有界复用。
- 2026-09-18 — R85 两条回收路线也都量了：`auto_vacuum` 现在是 0，而在非空库上 `PRAGMA auto_vacuum=INCREMENTAL` 是**静默空操作**（探针读出 `auto: 0`，变异 Y2 把它加到每次连接上也没有任何测试变红，因为 SQLite 根本不改已存在的库）；`VACUUM` 本地 0.012 s 确实把库缩到 237 页 / 970,752 B（省 1.03 MiB），可**下一次普通保存立刻回到 497 页**。为了不到 1 MiB 且一轮保存就还原的收益，去付 NAS 上重建整库的写锁停顿不划算，所以本轮不加，改为把「裁剪循环必须复用页」这个让结论成立的性质钉成测试（并断言 freelist 真的非空，否则上一条 equality 是在量一个空闲库）。
- 2026-09-18 — R85 顺手对齐两个数：R70 记的 5.6 MiB 与本轮 1.94 MiB 不矛盾，前者是含 playlists / playback 与更宽 id 分布的真实形状，本轮是 favorites-only 最小夹具；写下来是为了以后有人拿其中一个去否定另一个。
- 2026-09-18 — R85 的 `:16`：构建侧照旧不加参数（条目说「构建侧守自己刚产出的文件，没有注入需求」成立），改成钉住**两侧必须相等**。四处取值实测一致：校验器默认 `[long]$MaxArtifactBytes = 10GB`（:14）与 `[long]$MaxAndroidArtifactBytes = 1GB`（:15）、`build_release.ps1:283` 的 `-gt 10GB`、`build_android_release.ps1:105` 的 `-gt 1GB`。新测试从三份脚本里把数字读出来配对断言，并且只允许这一对参数名存在（`$Max\w*Bytes` 的集合恰为两个）。
- 2026-09-18 — R85 为什么「第三套命名」不是审美问题：变异 Z3 只是在校验器里多写一个 `[long]$MaxExtraBytes = 1GB`，就有 10 条测试变红——多余的带默认值参数会改变 `[long]` 参数段的实际形状，进而改变工件被拒的具体消息。Z1（构建侧放宽到 20GB）、Z2（校验器默认收紧到 5GB）、Z4（只有 Android 一侧漂到 2GB）各杀一条，其中 Z4 只有新测试能抓到，说明这条测试确实在做别的测试做不到的事。
- 2026-09-18 — R85 矩阵九例：控制组 56 条先绿（18.178 s）。Y1 裁剪不再删行、Y3 裁剪按半界执行、Y5 每次连接重建整库，三例被杀；Y4（把 `LIMIT ?` 的参数写成 `int(excess)`）与设计标注一致地存活，证明测试测的是语义不是写法。新测试两条：`test_repeated_trim_cycles_reuse_pages_instead_of_growing_the_file`、`test_the_build_side_ceiling_stays_in_step_with_the_verifier_default`。
- 2026-09-18 — R85 门限：round119 测试 2232 条、101.508 s、OK (skipped=2)、JS `checks passed` 行数 65、manifest 695 条；开放项 137，活动待办段 93 条，可离线验证代码项 74 条；重跑分类器 moves=0。
- 2026-09-18 — R84 关掉两条待办、新立 0 条：一条 R68 留的「同一数值习语出现三次、要不要合并」，一条 R62 留的「shutdown 里的唤醒重发没有被任何测试钉住」。剩余可离线代码项 76 条。
- 2026-09-18 — R84 先纠一个数：`isinstance(value, bool) or not isinstance(value, (int, float))` 这条习语在活动代码里是 **6 处**，不是条目记的 3 处——`dlna/service.py` 三处（`_saturating_increment`、`_safe_count`、`_finite`）加 `dlna/diagnostics.py:13`、`:31` 与 `dlna/renderer.py:24`。条目只扫了 service 一个文件，又一次说明「每轮第一个数要现量」。
- 2026-09-18 — R84 合并的是类型门，不是契约：新私有件 `_is_count_number(value, allow_string=False)` 统一 bool 拒绝（`bool` 是 `int` 子类，设备送来 `true` 会被当成计数 1），三个调用点之后各自照旧（钳制 / 回退 / 上限），`_safe_count` 保留字符串入口。合并范围刻意止于 service：另外三处住在 service 的下游模块，公共判定放进 service 会形成环，本轮不为它新建模块，未合并的部分连同原因一起记着。
- 2026-09-18 — R84 量的时候撞出真缺陷：`_finite` 的 `float(value)` 不接 `OverflowError`，实测 `_finite(10 ** 400)` 抛出，而同族的 `_safe_count`、`_saturating_increment`、`renderer._safe_position` 三处都接住了。条目当年写的「大整数不要转 float（`float(10**400)` 抛 OverflowError）」在三个读者里恰好只有一个没做——一个巨大的 int 就足够让投送状态投影变成 500 而不是 0.0。修法照包内既有约定：捕获后回 0.0，与 `inf`/`nan` 给同一个答案。注意两种「太大」走不同异常：`float(10**400)` 是 OverflowError，`float("1e999")` 是无穷。
- 2026-09-18 — R84 第二条纠正两个前提：① 那次 park 的超时是 `wait(10)`（:2683），不是 join 的 0.25 s 切片，所以错过一次唤醒的代价是**十秒**级滞留加 SQLite 句柄继续打开——这段防御比条目以为的更承重，「删掉它」不是选项。② 条目「场景不可达」的论证走的是被禁用 lane 在 `_process_job` 之后 `continue` 不 park 那条路；但 fetch lanes 共享同一个 `fetch_wake_event`（:1898）、每个 lane 醒来后自己 `clear()`（:2684），而 R78 实测线程池是 4-5 个 worker，「兄弟先清、别人睡满一整个 tick」在结构上是可达的。
- 2026-09-18 — R84 因此选了条目给的第一条路（变成被测契约），但没有构造真线程交错——那是抛硬币，会把离线门限变成 flaky 源。改钉机制本身：只要还有 worker 活着，每一个 join 切片都要重新 signal 三个唤醒事件。测试用计数代理套住三个事件，再放一个「醒三次就算排空」的假 worker，断言 `sets == 3 + 1`（循环前一次加每切片一次）。变异 U1 删掉循环内三行、U2 只留 fetch 一条都被指名杀死，U3 交换三行顺序按设计存活（三个互相独立的事件，先后无关）。旁证：U1 那一轮整套多花约 8 秒，正是「错过唤醒」的代价在测试里的样子。
- 2026-09-18 — R84 判别测试两条：`test_the_forgiving_numeric_readers_survive_every_unreadable_shape`（14 种不可读形状 × 3 个读者不得抛异常，另加溢出、bool、字符串、钳制四组精确值）与 `test_shutdown_re_signals_every_wake_event_for_each_join_slice`。矩阵 T1 不再接 OverflowError（3 个 error 杀）、T2 门放 bool 通过（除了新测试，既有 `test_seek_position_resolves_units_signs_and_bounds` 也杀，说明布尔拒绝本来就是行为事实）、T3 忘记字符串读者、T4 计数钳制消失、U1/U2/U3 如上，控制组 297 条先绿。
- 2026-09-18 — R84 门限：round117 测试 2230 条、100.694 s、OK (skipped=2)、JS `checks passed` 行数 65、manifest 695 条；开放项 139，活动待办段 93 条，可离线验证代码项 76 条；重跑分类器 moves=0。
- 2026-09-18 — R83 关掉两条待办、新立 0 条：一条 R74 留下的「离线门限里最慢的测试模块」，一条 R75 留下的「`50000` 出现在四个地方」。剩余可离线代码项 78 条。本轮把门限本身缩短了约 15 秒，后面每一轮都受益。
- 2026-09-18 — R83 先量再动：`test_build_release_script` 19 条测试 32.088 s，逐条计时显示 11 条测试共发起 19 次 PowerShell，单次最久 5.925 s；本机一次 `powershell.exe` 冷启动 0.94 s，而校验脚本自己的工作是 0.45 s 级（同一夹具跑两次独立进程 3.04 s，同夹具三个场景一个进程 1.81 s）。也就是说慢的不是发布校验，是解释器被反复启动。
- 2026-09-18 — R83 做法：测试模块内联一段场景驱动（不新增受版本管理的文件），一条测试的所有场景在**一个**进程里按顺序跑完，每个场景仍然把 `verify_release_evidence.ps1` 从第一条语句跑到最后一条，脚本内的 `throw` 逐场景捕获并回报。场景之间的夹具改动改成声明式的 `pre` 写入（base64 字节，或删除），于是执行顺序进了数据，而不是靠 Python 侧的动作与子进程穿插。结果 **32.088 s → 16.593 s**，单条最久降到 1.771 s，19 条全绿。
- 2026-09-18 — R83 为什么这不是「把独立拒绝理由压成一个」：每条测试仍然逐场景断言自己的消息文本（`exceeds the 4095 byte artifact limit`、`invalid staged file count`、`ANDROID_SHA256SUMS` 等各自独立），驱动只是换了传输。真正的风险是驱动自己出错，所以回报里带 `index`，Python 侧同时断言条数与索引连续——少一个场景、或者乱序，都会直接失败而不是把结论记到别的断言头上（变异 V4 去掉 index 递增、V5 只回报第一个场景，都被这两条契约抓住）。
- 2026-09-18 — R83 承重证明是 V7：把真实校验脚本里的 `$recordHash -ne $record.Hash` 改成永假（等于发布校验不再比对 SHA-256），合并后的测试照样失败。这轮改动没有把这批测试退化成文本契约测试。V6（去掉 `Out-String -Width 4096`）按设计存活：没有任何断言依赖换行位置，属等价变异。
- 2026-09-18 — R83 第二项是命名而不是合并：`state_store` 里三个承诺各自成名——`MAX_REQUEST_FAVORITES`（单个请求/保存能带多少条）、`MAX_REQUEST_PLAYLIST_DELETIONS`（一次能删多少）、`MAX_PERSISTED_FAVORITES`（盘上留多少）。归属是逐个确认的：`_state_changes` 两处与 `save_user_state` 的读入截断都是**请求**侧（R76 的漂移守卫正是靠「把存储界抬到 50001 仍然只留 50000」证明这点的），只有 `_trim_favorites` 是存储侧。`playlist_delete` 的 1000 与 `MAX_PERSISTED_PLAYLISTS` 的 1000 数值相同但语义无关，按条目要求不合并。
- 2026-09-18 — R83 新测试只搬请求界：请求界设成 10 时 20 条收藏只留 10 条、而存储界仍停在 50000，把两个常数写成别名的实现过不去；顺带给删除批次补上行为断言（1001 截到 1000，设成 4 截到 4）。变异 S1/S2/S3 由这条新测试指名杀死，S4（磁盘裁剪借用请求界）被两条既有测试杀死——分离本来已是行为事实，这轮只是让它读得出来。
- 2026-09-18 — R83 门限：round115 测试 2228 条、99.837 s、OK (skipped=2)、JS `checks passed` 行数 65、manifest 695 条；开放项 141，活动待办段 93 条，可离线验证代码项 78 条；重跑分类器 moves=0。矩阵两批：V 系 7 例（控制组 19 条 16.662 s 先绿，V6 等价存活，其余全杀），S 系 4 例（控制组 38 条先绿，全杀）。副本环境两条坑记进 PROJECT_CONTEXT：变异副本必须镜像 `android-client/app/build.gradle`（`build_release.ps1` 会先拒绝缺失的发布输入，控制组假红过一次），且不能整份复制 `tools/`（内含 430 MB 只读 Go 模块缓存，`shutil.rmtree` 会在只读目录上 PermissionError）。
- 2026-09-18 — R82 关掉两条封面侧待办、新立 0 条：一条 R67 留下的「哪些工件需要耐久」评估，一条 R72 留下的「锁内禁 I/O 只有一条形状断言撑着」。剩余可离线代码项 80 条。
- 2026-09-18 — R82 耐久判据不是性能而是**读路径能不能发现自己是坏的**：`_atomic_bytes` 加 `durable` 形参（`cover_cache.py:1155`），共享资产 `.jpg` 继续 fsync——内容地址指的是原图而不是渲染出来的 tile，一个写坏一半的 JPEG 没有任何读路能识破，会永久端出去；`.asset` 别名（:1319）与 `.none` 负标记（:1293）不再等磁盘，因为这两种形状「要么对要么一眼是垃圾」：别名由 R80 加的 64 位十六进制校验加资产回查拒绝，负标记内容恒空，损坏等同于不存在，下一轮自己重渲染重写。
- 2026-09-18 — R82 写序仍然安全：先写资产（durable）再写别名（非 durable），所以不可能出现「别名活着、资产没了」这种指向虚无的状态；反过来别名丢了只是资产暂时孤儿，R75 的淘汰扫会回收。矩阵 H1 退回策略、H2 反转标志、H4 连图片也不 durable，三条全被新测试指名杀死。
- 2026-09-18 — R82 一个**应当存活**的变异：H3 把非耐久写入的 `handle.flush()` 也一起去掉，99 条全绿。原因是等价而非漏网——`with os.fdopen(...)` 退出时 close 本来就把缓冲冲下去，:1162 那行 flush 是冗余代码。本轮只把这个事实记进结论，不另立待办，也不顺手删它（删它要用一次单独的判别测试来证明「确实等价」，那是另一轮的活）。
- 2026-09-18 — R82 锁的实测库存：`_MEMORY_CACHE_LOCK` 14 块 98 行、`_PREWARM_LOCK` 21 块 150 行、`_LOCKS_GUARD` 1 块 5 行，锁内文件系统调用 0 处——R80 新增的那次 read + stat 落在锁外，所以条目担心的「拆三把锁」现在没有可测收益，改为把断言从单个函数扩到全模块。
- 2026-09-18 — R82 唯一需要豁免的东西恰好是个陷阱：两处入队去重键写作 `cover_source_version(item, allow_disk=False)`（:849、:1039），名字里带 disk 但按 :227 的实现只吃索引身份、不发 stat。豁免规则因此不是「这个函数允许」而是「必须显式带 `allow_disk=False`」，于是错误用法自己会被抓住：变异 G2 去掉这个 kwarg 即被杀，而且行为侧早有 `test_interactive_prewarm_queue_key_does_not_stat_unindexed_items` 独立钉着同一件事。
- 2026-09-18 — R82 形状断言自我反空转：新测试扫全模块锁块，但先断言块数下限 30、且三把锁都必须被覆盖，否则「扫到 0 个块」也会通过。承重性由 G1（探针塞进老函数 `_memory_get`）与 G3（探针塞进 R81 才写的 `_forget_advertising_asset`）配对证明——G3 正是原条目说的「旧断言看不见的新块」。
- 2026-09-18 — R82 门限：round113 测试 2227 条、115.208 s、OK (skipped=2)、JS `checks passed` 行数 65、manifest 695 条；开放项 143，活动待办段 93 条，可离线验证代码项 80 条；重跑分类器 moves=0。新增 3 条测试（图片字节独占 fsync、durable 形参确实是 fsync 的唯一开关、全模块锁内禁 I/O），矩阵 7 例：控制组 99 条先绿，6 杀 1 等价存活。
- 2026-09-18 — R81 关掉两条封面侧待办、新立 0 条：一条 R72 停在「要先量 404 频率」的广告不一致，一条 R75 立的设计约束。剩余可离线代码项 82 条。
- 2026-09-18 — R81 缺陷：`allow_disk=False` 的翻页快速路径不复核磁盘（这正是它存在的理由），所以共享资产被回收之后，暖着的别名缓存还在继续广告 `cover-asset/<id>`，浏览器每行拿一次 404，要等别名 LRU 自己走掉才恢复。R72 当时把修法想成「给翻页路径加负缓存，先量 404 频率」；本轮换了个不花钱的方向：**在答不出的那一侧收尾**——`thumbnail_asset_bytes` 失败时把内存别名表里指向这个 asset 的条目摘掉（`cover_cache.py:430` 的 `_forget_advertising_asset`）。
- 2026-09-18 — R81 这个修法为什么不需要那个测量：翻页路径一次 stat 都没多，代价只落在「已经失败」这条冷路径上，而且只扫 `_ASSET_ALIAS_CACHE_LIMIT = 4096` 的表；盘上的 `.asset` 一个字节的没动，R80 加的预热判定会回查资产、发现缺失就重渲染并改写别名——R80 与 R81 合起来才是一个完整的自愈闭环。两个失败分支都得摘：`_read_bounded_file` 返回 None 同时覆盖「文件没了」与「超过服务预算」，两种都永远答不出（变异 E3 只摘 `except OSError` 那支即被杀）。
- 2026-09-18 — R81 第二项是设计约束，约束本身成立、措辞是全称，实测要收窄：`_item_cache_identity`（:121）取的是 `item.get("id") or item.get("path")`——库里行都有 id，所以对它们「内存键里没有路径」成立；**没有 id 的行键里就是路径**，于是「清扫无法反查」只对前者成立。条目自己写了「那是另一次改动而不是三行代码」，所以本轮不改实现、不建反查表，而是把这条约束的确切边界钉进测试：id 行的路径不出现在任何键里、无 id 行的键确实是路径（例外不是缺陷）、以及刻意语义「内存可以继续回答盘上已经没有的字节」在资产与媒体文件都被删掉后仍然成立。
- 2026-09-18 — R81 抓住一个会空转的断言：新测试第一版写 `media in repr(key)` 来判断媒体路径有没有进内存键，而 Windows 上 `repr()` 把反斜杠转义成 `\\`，这个 substring 永远不成立——**id 行那半条断言本来会以完全无效的方式通过**。是无 id 那半条先报错才暴露的。改成 `"|".join(str(part) for part in key)`。这类坑只在 Windows 仓库上才踩得到，已单独写进 PROJECT_CONTEXT。
- 2026-09-18 — R81 顺带发现测试之间的泄漏：新测试往进程级 `_MEMORY_CACHE` 写了条目，把邻居 `test_mid_request_identity_change_cannot_split_the_cache_keys` 撑红——那条测试断言的是**全局 key 的精确列表**（`[entry[2] for entry in memory_keys] == ["1:1"]`），不按身份过滤。新测试因此补上前置 `clear_memory_cache()` 与 `addCleanup`，而不是去放宽邻居的断言。
- 2026-09-18 — R81 判别与变异：新增两条测试；矩阵 E1 回退整个修复、E2 把摘除写成全表清空、E3 只摘一个分支、E4 把比较写成 `!=`、F1 让 identity 优先取 path、F2 让内存条目根本不留，控制组 96 条先绿，六个全部被指名杀死（E2/E4 由「无关行必须留着自己的封面」这半条杀死）。
- 2026-09-18 — R81 门限：round111 测试 2224 条、116.562 s、OK (skipped=2)、JS `checks passed` 行数 65、manifest 695 条；开放项 145，活动待办段 93 条，可离线验证代码项 82 条；重跑分类器 moves=0。
- 2026-09-18 — R80 关掉两条预热侧待办、新立 0 条：一条是 R67 停在「先量代价」的别名判定，一条是 R73 停在「先量计数」的版本解析。剩余可离线代码项 84 条。
- 2026-09-18 — R80 缺陷：`_prewarm_result_exists`（`cover_cache.py:287`）只看 65 字节的 `.asset` 别名在不在，正文损坏、截断、非 ASCII，或者它指向的共享资产已被回收，都照样算「已有结果」。后果不是显示错，而是**这一项永远不进预热队列**：只有真的封面请求来读一次才会重渲染并改写别名，预热自己永不自愈。R67 当年没动它是因为条目要求先量代价，本轮先把量做出来。
- 2026-09-18 — R80 实测（200 行满别名页）：修复前 25.4 us/行；修复后首次（内存别名表冷）193.4 us/行，之后 42.9 us/行。接受它的理由是**作用域**，不是外推：这个判定只服务交互式预热，队列上限 `INTERACTIVE_PREWARM_MAX_PENDING = 96`（:93），每轮最坏 96 x 193 us = 18.6 ms；20000 条/轮的库扫描走另一条 worker（:1060 起，先 isfile 媒体文件再直接 `cached_thumbnail_for_item`），根本不读这个判定——这句是读代码确认的，不是按比例算的。
- 2026-09-18 — R80 实现走的是「一个家」：把别名规则从 `thumbnail_asset_id_for_item` 原样提成 `_alias_asset_key`（:360，内存别名表、64 位十六进制正文校验、资产回查、以及那三段「先复值再动 LRU」的守卫全在里面），读路径与预热决策都调它。没有在预热里另写一份校验，也没有让预热去解析图片字节。
- 2026-09-18 — R80 一个夹具先错了：`test_interactive_prewarm_skips_results_the_writer_actually_produces` 造别名时只写 `.asset`、不写资产文件，而写者的顺序本来就是先写资产后写别名（R75 定的），也就是说那个夹具摆出来的正是本轮要判定为「不是结果」的状态。改判定后它变红，先分清是夹具错还是规则错，再补上资产文件，而不是给规则开洞。
- 2026-09-18 — R80 第二项量的结论是要串：每行有 2 次带 stat 的 `cover_source_version`（判定 1 次、渲染 1 次）；入队侧还有 1 次但那是去重键，`allow_disk=False` 不碰磁盘（:227 优先用索引里的 mtime/size），不计入。现在 worker 每行解析一次（:890）并把同一个串交给判定与渲染（`cached_thumbnail_for_item` 早在 :1198 就有 `version=` 形参）。省一次 stat 是次要的：R73 注入版本的理由（文件在请求中途变了，不能一半按旧键判断、一半按新键写入）在预热这条路上同样成立。
- 2026-09-18 — R80 判别与变异：新增两条测试（损坏别名不再遮蔽入队、每行只解析一次版本并共享）+ 一条形状断言扩写（两个调用方都必须委派给 `_alias_asset_key`，谁把规则内联回去就红）。矩阵 C1 退回裸 `isfile`、C2 过度纠正成「别名一律不算结果」、C3 只校验正文不回查资产、C4 把规则内联回调用方、D1a 渲染自己再解析、D1b 判定自己再解析；控制组 94 条先绿，六个全部被指名杀死。
- 2026-09-18 — R80 门限：round109 测试 2222 条、114.636 s、OK (skipped=2)、JS `checks passed` 行数 65、manifest 695 条；开放项 147，活动待办段 93 条，可离线验证代码项 84 条；重跑分类器 moves=0。
- 2026-09-18 — R79 关掉两条既有代码待办、新立 0 条：一条是真缺陷（诊断路径上的 `int(limit)` 会抛），一条是 R69 立下的文档顺序断言缺口。剩余可离线代码项 86 条。
- 2026-09-18 — R79 缺陷：`classify_mpd_log_errors`（`playback/mpd_errors.py:148`）与 `_tail_text`（`services/mpd_service.py:2067`）都拿 `int(limit)` 直接吃入参，非数字界限抛 `ValueError`；而 `_tail_text` 的那一行还写在 `try` 里、`except OSError` 兜不住——诊断读盘变成一个 500。两个调用点今天都传字面量，属潜伏，所以修法是让它**不抛**而不是加断言。
- 2026-09-18 — R79 修法沿用仓库既有件：统一用公共的 `summary_values.nonnegative_int`（子包按 `from summary_values import ...` 引入，先例是 `playback/core.py` 的 `from metadata_track_id_policy import ...`），没有新增第四个小助手，也没有跨域去 import 元数据域的私有 `_safe_limit`。归一化同时挪出 `except OSError`。两个既有语义一个都没改：`limit or 20` 让 0 继续表示「未设置」，负数仍钳到下限而不是回落默认。
- 2026-09-18 — R79 我把「等价」断言写错了一次：新测试原本假设归一化不改变结果，于是断言 `classify(log, -5) == classify(log)`，实测失败——`limit` 不只切尾行，它同时是**返回记录条数的上限**（`max(1, min(100, ...))`），-5 钳到 1 就只剩一条。旧代码同行为，所以错的是断言不是实现，改成 `classify(log, -5) == classify(log, 1)`。教训：写「这不改变行为」之前先把被改函数的全部作用读一遍。
- 2026-09-18 — R79 第二项纠了一个数：R69 记的 `PROJECT_CONTEXT.md`「实测两处倒序」是**每趟扫描发现的第一个**，本轮实测 281 条前导条目要搬 17 条才收敛（190-196 是七条 09-06 连续错位的一块，282 行那条 09-17 补录跨了 141 行）。改法只搬违规条目、不做全量排序（全量排会重排别人轮次内部的相对顺序），并用「条目集合不变 + 倒序归零」两条断言自证搬运没丢东西。
- 2026-09-18 — R79 把 newest-first 扩到第三份根文档时踩到正则误伤：`- \d{4}-\d{2}-\d{2}[： ]\S` 会把 281 条里的 **110 条**判成格式错误，因为规则条目写的是「： **「（冒号后带空格再跟粗体）。放宽为 `[：: ]\s*\S`，并留一个变异专门证明这步宽松化是必要的而不是偷懒。顺手把「最新日期一致」从两份的两两比较改成三份的集合唯一。
- 2026-09-18 — R79 契约变更（对本项目每一轮的写文档步骤生效）：`PROJECT_CONTEXT.md` 现在也受 newest-first 约束，**补录旧日期的条目不能再 prepend 到最前面**；三份根文档的最新日期不一致会直接红。承重性配对证明：N1 还原乱序备份即失败，N3 把第三份从循环里去掉则同一份乱序文件无人报错。
- 2026-09-18 — R79 门限：round107 测试 2220 条、113.968 s、OK (skipped=2)、JS `checks passed` 行数 65、manifest 695 条；开放项 149，活动待办段 93 条，可离线验证代码项 86 条；重跑分类器 moves=0。矩阵 M0 控制组 47 条先绿，P1 退回 `int(limit or 20)`、P2 退回 try 内的 `int(limit)`、P3 去掉下限钳制、P4 把 0 当真实界限、N1 乱序文件、N2 naive 正则，六个全部由新测试指名杀死。
- 2026-09-18 — R78 是第一个按新口径批量关项的轮次：从实测 88 条可离线代码待办里挑两条最干净的（一条真缺陷、一条声明与实现漂移），净关闭 2 条、新立 0 条。
- 2026-09-18 — R78 缺陷一（R62 立的「补员线程重名」）：`_start_lane` 用 `range(replacement_count)` 给补员线程命名，每轮都从 0 重新数，于是两轮补员之后 `threading.enumerate()` 里出现两个 `fnaudio-metadata-fetch-recovery-0`，真机排查和这一轮用的栈抓取脚本都说不清某个线程是哪一轮起的。改成实例级单调计数 `_recovery_serial`（`metadata_service.py:1948` 声明、:2461 递增、:2464 命名）；lane 身份本来就在 `fetch-recovery` 这个字面量里，没有再叠第二份。
- 2026-09-18 — R78 测试写法的教训：这条测试的第一版真的起了线程，结果上一轮补出来的活线程把临时 `library.sqlite3` 句柄占住，`TemporaryDirectory` 收尾直接 `PermissionError [WinError 32]`——同一个坑这套仓库第二次踩。改成 patch `metadata_service.threading.Thread` 换成「只记名字不起线程」的替身之后 0.023 s 跑完；断言也从「一共应有 3 个名字」纠正成「recovery 名字彼此不同」，因为真实池大小是 4-5、每轮补满，写死 3 是我的臆测而不是事实。
- 2026-09-18 — R78 缺陷二（R68 立的 SCPD 无约束）：服务描述里 `A_ARG_TYPE_SeekMode` 是裸 `string`，而 `_seek_position` 只认 `SEEK_UNITS` 两个值。R68 当年停手是「要先确认没有客户端依赖宽松定义」，本轮判定这个前置不该等：`allowedValueList` 是**声明不是强制**，处理逻辑一行未动，宽松控制器行为不变。现在声明从 `SEEK_UNITS` 派生（`dlna/service.py:336` 起），两份事实变一份，不会漂成「宣传但不接受」或「接受但未声明」。
- 2026-09-18 — R78 这条测试另外钉住「其余状态变量保持宽松」：`A_ARG_TYPE_SeekTarget` 与 `TransportState` 不许出现 allowedValueList，因为给没实现校验的状态变量加枚举，等于凭空对控制器许诺。矩阵里 M5（把所有 `A_ARG_*` 都加上枚举）正是被这半条杀死的。
- 2026-09-18 — R78 判别与变异：两条新测试 + 仓库外矩阵 M1 退回 `% index`、M2 每轮重置计数、M3 不声明、M4 抄第二份常量（多写一个 `TRACK_NUMBER`）、M5 全量加枚举、M6 渲染时漏掉枚举；控制组 347 条先绿，六个变异体全部由这两条新测试指名杀死。
- 2026-09-18 — R78 没立新项：真机侧「控制器是否按枚举渲染快进 UI」这个观察，归宿是 P0 段里已有的 R68 真机项（相对 seek 只在桩后端验过），本轮把它写进关闭结论，不再复制成第二条 `- [ ]`。
- 2026-09-18 — R78 门限：round105 测试 2218 条、114.016 s、OK (skipped=2)、JS `checks passed` 行数 65、manifest 695 条；开放项 151，活动待办段 93 条，可离线验证代码项 88 条；重跑 R77 分类器 moves=0（归档幂等）。
- 2026-09-18 — R77 第一步不是找 bug，是把「还剩多少可离线做的活」变成一个可信的数。上一轮定的三分口径（155 = 64 代码 + 82 设备 + 9 决策）是**纯关键词**扫出来的，逐条复核证明它两头都错：关键词命中条目**正文**里那句「需要真机验证」，就把主体完全能离线做的缺陷冻进验收段，冻错的有 `A_ARG_TYPE_SeekMode` 无约束、`_atomic_bytes` 每次封面写入都 fsync、metadata 补员线程重名、`app.js` 剩余 92% 浅读面、`state.sqlite3` 文件不回收，共 20 多条。
- 2026-09-18 — R77 第二个假阳性来源是**拿我们自己的标识符当设备信号**：`设备` 命中「同一个『设备是否支持源码 DSD』的事实」、`Renderer` 命中 `renderIncomingRendererSession`、`Android` 命中 `build_android_release.ps1`，于是 `R71 构建侧产物上限仍是两处字面量` 这种纯离线项差点被搬走。三个裸词从设备标记表里删掉，设备依赖只认条目自己的标签词（`真机项`、`缺设备证据`、`低端 WebView`、`DAC`、`取证`…）。
- 2026-09-18 — R77 定稿的判据两条：**段名权威**（已经在 P0/P2/宿主/决策段里的条目就地不动、也不再二次分类）+ **设备或决策信号必须出现在条目自己的标签里**（日期与前缀之后的头部窗口）。搬运范围限定在活动待办段：下面的历史轮次段是「当轮写了什么」的档案，改它们是churn不是分类。
- 2026-09-18 — R77 落地：搬 18 条（14 设备 + 4 决策），其中 3 条补了显式「需要：…」说明要什么设备才能验收，其余自己已写明；P0 段标题改成「外部验收（离线不可验证）：必须依赖真实设备或外部材料」。落盘前有两条硬校验：开放项 155 → 155 一条不少，以及**逐条撤销这次唯一允许的文本改动**（记录下来的精确后缀）后与改动前完全相等，证明没有任何条目被顺手改写。
- 2026-09-18 — R77 关闭的代码项之一（真修）：`decode_base64_lyrics` 因为 `validate=True` 拒绝**内部**空白，把 MIME 折行（RFC 2045 每 76 字符一个 CRLF）的整条歌词丢掉。原条目写的是「等设备侧日志出现 `lyrics base64 payload is invalid` 再处理」，本轮判定这个前置不该等：折行不携带信息，而等日志期间每次日志本身都在丢歌词，代价只有一次 O(n) 拷贝。改成在预算检查之前删除六个 ASCII 空白字符（不含 U+00A0/U+0085，免得把损坏载荷洗成合法）。
- 2026-09-18 — R77 关闭的代码项之二（证伪，不改代码）：同函数另一条待办前半已经不存在——预算现在就在解码之前用编码长度 `(limit+2)//3*4` 检查（:145），函数文档写的正是「先解码会先分配那块即将被丢弃的缓冲」；后半「`qq_lyrics()` 没过 `_provider_text` 与 joox 不一致」核对后不是缺陷：非字符串由 `decode_base64_lyrics` 的 `isinstance` 返回 `""`，体积由编码上限兜住，两条链路最终约束一致、只是形状不同。
- 2026-09-18 — R77 判别与变异：三条新测试（折行可用、折行不能绕过编码上限、只归一化 ASCII 空白）+ 五个仓库外变异体全部被指名杀死——M1 退回 `strip()`、M2 换成 `"".join(value.split())`（会顺带删 NBSP/NEL）、M3 预算按原始字段长度算、M4 归一化表漏掉 `\n`、M5 关掉 `validate=True`；控制组 232 条先绿。净效果：代码待办 -2，另 18 条移出代码段，本轮不立新项。
- 2026-09-18 — R77 门限：round103 测试 2216 条、112.755 s、OK (skipped=2)、JS `checks passed` 行数 65、manifest 695 条；开放项 153（关闭项 1353），活动待办段 93 条，P0 段 22 条，决策段 8 条。三份根文档记录方式不变；`src/tests/test_zz_socket_guard.py` 仍是未跟踪新文件，等用户 `git add` 决定。
- 2026-09-18 — R76 取证从耗时分布开始，不是从模块印象开始：给 2201 条测试逐条计时（`%TEMP%\r76survey.py`）之后，`test_track_match_pending_projects_independent_cached_artwork` 15.644 s 与 `test_track_match_pending_exposes_local_tags_before_provider_finishes` 14.357 s 两条就占了 full gate 143.8 s 的 21%；第二大块是 `test_build_release_script` 里 7 条各 3-6 s 的证据校验（每条起一个 PowerShell 子进程），另立条目跟进。
- 2026-09-18 — R76 第一条结论：**名为离线的门禁其实在联网**。faulthandler 打出的工作线程栈停在 `ssl.do_handshake → http.client.connect → urllib https_open → metadata_service._open_metadata_url:179 → _json:796 → _musicbrainz_recordings:981 → track_candidates:1749 → _process_job:3016 → _run:2638`，也就是说一次普通 gate 运行会向 musicbrainz.org、music.163.com、c.y.qq.com、songsearch.kugou.com、cache.api.joox.com、pd.musicapp.migu.cn、music.91q.com 七个真实服务发 HTTPS 请求；而「provider 还没返回」这个断言实际是在跟本机网络往返赛跑，快网机器上完全可能先看到 auto 结果而失败。
- 2026-09-18 — R76 测试侧修法：`_provider_request_parked` 把 provider 请求停在模块唯一的 HTTP 出口 `_open_metadata_url` 上，并用事件按住、`finally` 里先放行再 `shutdown`。第一版钉的是 `providers.track_candidates`，结果同一次查找扇出的 album/lyrics job 照样拨了 7 台真主机（socket 守卫当场记到 7 次越界）——接缝必须选在唯一能把字节送上网络的那一层，而不是选在语义上最贴切的那一层。
- 2026-09-18 — R76 真正的产品缺陷：网络堵住之后两条测试仍各要 5.7 s，栈显示主线程卡在迁移写 `UPDATE metadata_entities SET expires_at=0`（现 :2276，`_ensure_schema` 在 :2199），而那一刻没有任何其他线程在跑 metadata 代码。原因是 `track_match`（现 :3475）这类调用点位于调用者自己的 `with self._connect()` 作用域内、刚写完 `metadata_jobs` 而尚未提交，此时 `ensure_workers()` 用**第二条连接**重跑同一份迁移：它读到的是未提交之前的旧 `cache_version`，于是决定写，而写锁正被第一条连接持有，且只有等这次调用返回才会释放——自己等自己等到 `busy_timeout=5000` 满。仓库里 8 处 `ensure_workers` 调用点，有 3 处（`track_match` 与 lyrics 的 :4471、:4490）逐行读过确认是这个形状，其余 5 处紧邻同一 `conn` 作用域、未逐一读到底；修法不依赖调用点形状，登记只在 `_connect` 作用域打开时发生。
- 2026-09-18 — R76 修法集中在一个地方，8 个调用点一行未动：`_connect` 用线程本地 `_lane_release.depth` 记录「本线程持有数据库作用域」，`ensure_workers` 在 depth>0 时只登记 lane 并返回 True，最外层 `_connect` 退出（已 commit、已 close）后由 `_release_deferred_lanes()` 逐条真正启动；同名 lane 去重，事务失败也照样启动，启动本身异常只写 `last_error` 不把已完成的元数据响应改坏。顺带消灭一个丢失唤醒：原来 worker 被叫醒时，叫醒它的那笔 job 还没提交，它看不见。
- 2026-09-18 — R76 效果（可复现的量，不是单次）：全新库的首次元数据查找 5.72 s → **0.17 s**（另一条 5.86 s → 0.30 s）；`test_metadata_service` 由 208 条 25.1 s 变成 214 条 13.85 s；门禁自己报告的 unittest 总耗时 134.312 s → **115.484 s**（少 18.8 s，同时测试数 2201 → 2213）；另一次逐条计时的独立跑是 143.8 s → 113.7 s，两个口径不同（前者不含进程启动与逐条计时开销），取门禁报告值为准。
- 2026-09-18 — R76 新增常驻守卫 `src/tests/test_zz_socket_guard.py`（6 条）：把 `socket.socket.connect`、`connect_ex`、`create_connection` 包成只允许回环，任何越界拨号从「慢一点」变成响亮失败。守卫自己要用 `musicbrainz.org`、`198.51.100.20`、`8.8.8.8` 与 RFC 5737 的 `203.0.113.9` 证明生效，并有一条穿过产品真实 HTTP 栈（`_open_metadata_url`）证明 urllib 经由 http.client 的别名路径也拦得住；`external_access_attempts` 只记录不断言（仓库里本来就有测试要断言「非 LAN 主机被拒绝」），供审计脚本读。修完之后整套跑只记录到 7 次拒绝，其中 6 次是守卫自己的探针。
- 2026-09-18 — R76 变异矩阵 L1-L7 全杀（仓库外副本，5 个模块）：L1 事务内直接启动、L2 失败事务丢掉登记、L3 同一 lane 启动两次、L4 只启动第一条 lane、L5 登记后返回 False、L6 深度不归还、L7 provider 接缝不 patch。L1 的失败文本就是主张本身：`AssertionError: 5.5731702000011865 not less than 1.0 : a first lookup must not pay a busy_timeout`。两处自伤也记下：harness 把 `"-m", "unittest"` 误写成 `"-m unittest"`，八个用例全读成 killed 且控制组也 killed——控制组不绿时矩阵根本不可读；L7 第一版注入的替身自己把断言喂饱，导致真外呼被读成 SURVIVED。
- 2026-09-18 — R76 门限：round101 测试 2213 条、115.484 s、OK (skipped=2)、JS `checks passed` 行数 65、manifest 695 条。仓库外副本已清空；`src/tests/test_zz_socket_guard.py` 是未跟踪新文件，需要用户 `git add` 决定。
- 2026-09-18 — R75 取证（枚举出来的，不是印象）：`cover_cache.py` 全文只有三处 `os.unlink`，且都在读路径上顺手清理（过期 `.none`、写失败的 temp），**没有任何总量回收**。本仓库另有两处文件/资产缓存的先例：`transcode.prune_transcode_cache`（:538，`transcode_cache_max_bytes` + `disk_has_reserve` + 按 mtime 收敛）与 `metadata_service._prune_artwork_cache`（:4002，`metadata_cache_max_bytes` + `last_accessed` + 批量），封面这一路两样都没有。规模算法：`ALLOWED_SIZES = (160, 512)`（:69），每个独有封面源最多留 2 份资产 + 2 份别名 + 2 份标记；5000 张独有封面 ≈ 260 MB 与约 2 万个小文件，再加上标签写回换出的旧键与崩溃留下的 temp，单调只增不减。
- 2026-09-18 — R75 修法（照抄自家先例，不发明形状）：新增 `prune_cover_cache(config)` 与 `cleanup_cover_cache_if_due(config, force=False)`，配置键沿用同一套语义——`cover_cache_max_bytes`（默认 512 MiB、界 1 MiB 到 8 GiB）与既有的 `cache_min_free_bytes`，helper 直接复用 `resource_limits.bounded_int` 与 `disk_has_reserve`。触发点只有一个：`_atomic_bytes` 是封面服务唯一的落盘口（四个写入点全部经它），发布成功后调一次 interval-guard 的清扫。
- 2026-09-18 — R75 三层规则与各自的理由：一、过期 `.none` 与崩溃留下的 `.fnaudio-cover-*` temp，用读者本来就在用的 `MISSING_MARKER_TTL_SECONDS`（300 s）判定，行为零变化，只是把「没人再访问就永远在盘上」那部分扫掉。二、悬空别名一律删；没有任何别名指向、且过了在写宽限期的资产也删。宽限期**是必需的而不是保守**：`cached_thumbnail_for_item` 先写资产再写别名，两者之间有几条指令的窗口，没有宽限期就会删掉正在服务的请求刚写好的字节，而那个请求已经把 `cover-asset/<id>` 发给浏览器了，结果是 404 图。三、超字节预算或磁盘不留量时，按 mtime 从旧到新删「单元」（资产加指向它的别名），单元里资产删不掉就整轮停下，绝不留悬空别名。
- 2026-09-18 — R75 内存与磁盘的一致性：被清扫的别名与标记同时从 `_ASSET_ALIAS_CACHE`、`_MISSING_MARKER_CACHE` 忘掉，字典操作全在 `_MEMORY_CACHE_LOCK` 内且锁里没有任何 I/O（R72 那条规则在这里直接复用）。`_MEMORY_CACHE` 的键是 (缓存目录, 媒体身份, 版本, 尺寸)，**不含路径**，所以盘上文件被回收后内存条目留着是刻意的：同一批字节从内存回答仍然正确，只是不再宣称磁盘上有。
- 2026-09-18 — R75 严重度自己量并据此改设计（`%TEMP%\r75bench.py`）：1800 个文件 12.3 MB 的缓存，第一版不封顶的清扫一次删掉 1392 个文件、耗时 **698 ms**，而这一下全压在恰好触发它的那一次封面请求上。于是加了 `COVER_CACHE_SWEEP_DELETE_LIMIT = 200`：同一棵树每轮 **128.9 ms**，12.3 MB 大约要 7 个间隔（35 分钟）才回到预算内；已经满足预算时一轮只是目录走查 **29.6 ms**，每 300 s 至多一次，占空比约 0.01%。取舍写成一句话：宁可让回收慢几个间隔完成，也不让某个用户的请求替整次清扫买单。
- 2026-09-18 — R75 测试 +11：`test_cover_cache.py` 69 → 80 条。新增 `CoverCacheSweepTests`：过期标记删除并被忘掉（fresh 的必须留下）、崩溃 temp 回收、悬空别名必删且内存同步、「资产已写别名未写」的窗口不得误删、过了宽限期的孤儿资产回收、字节预算只删最旧单元且最新单元存活、磁盘不留量在预算之内也触发、单轮走查条目上界、单轮删除条数上界、间隔内只跑一次且失败同样吃掉间隔、发布触发 housekeeping 而 housekeeping 失败不得让发布失败、没有 config 就不扫描。
- 2026-09-18 — R75 变异矩阵（`%TEMP%\r75verify.py`，仓库外副本，6 个封面模块）：L1 标记不过期、L2 悬空别名存活、L3 忽略孤儿宽限期、L4 清扫后不忘掉内存条目、L5 去掉单轮删除上界、L6 清扫成功后才占间隔、L7 清扫异常逃逸到发布、L8 不看磁盘不留量——八条全部被杀，L6 恰好是 `transcode.py:617-620` 注释里记录的历史 bug 的形状，本仓库这条规则现在在封面路径上也有测试守着。写测试时又踩了一次自己的坑：先给 `cleanup_cover_cache_if_due` 注入异常，等于把要验证的守卫本身替换掉了，改成注入下一层 `prune_cover_cache` 才测到真实契约。
- 2026-09-18 — R75 门限：round99 测试 2201 条、131.301 s、OK (skipped=2)、JS `checks passed` 行数 65、manifest 694 条。仓库外副本已清空。
- 2026-09-18 — R74 取证（每次动作都重新问一遍 DNS）：DLNA 出网链路上，一个 SOAP 控制动作要解析两次同一主机——`control_point.soap_request` 先 `lan_http_url(control)` 校验（:123，内部 `socket.getaddrinfo`），`network.fetch_lan` 拨号前又解析一次做 pin（原 :142）。GENA 每投一次 NOTIFY 也解析一次。实测（`%TEMP%\r74bench.py`，两次复现完全一致）：10 次控制动作 **20 次解析**、20 次事件投递 **20 次解析**。`getaddrinfo` 本身没有超时，局域网里 DNS server 是一台睡着的 NAS 时，每一次按键、每一条状态事件都要先排一次解析往返。订阅侧那半件事前几轮已经修过（`dlna/service.py:394-399` 把解析挪出了 `_lock`），本轮修的是剩下的重复与不复用。
- 2026-09-18 — R74 修法之一（去掉重复校验）：`soap_request` 不再自己验一遍，`fetch_lan` 成为唯一收敛点。删之前先证明它是唯一的：`fetch_lan` 内部按顺序做 `_parse_lan_http_url`（协议/凭据/端口界）→ 地址集合分类（私有或链路本地、排除回环/组播/保留）→ 把 socket 钉到已验证地址 → 响应端点再比对一次，任何一步不过都不发一个字节。唯一丢掉的是「在拼 envelope 之前就失败」，那只是拼字符串，没有副作用。类型检查留在 `soap_request`：`urllib.request.Request(None)` 抛的是 AttributeError，而调用方 catch 的是 ValueError，这个契约单独有用例钉住。
- 2026-09-18 — R74 修法之二（有界 TTL 缓存）：`network.py` 新增 `_cached_lan_addresses`，键 `(小写主机名, int(端口))`，TTL 5 s、LRU 64 条，**只存本进程自己判定为 LAN 的结果**；解析在锁外做，锁只保护两次字典操作；拨号抛 OSError 时立即 `forget_lan_addresses`；解析失败或分类不通过一律不入缓存。
- 2026-09-18 — R74 安全口径（必须先说清再合入）：给 DNS 加缓存等于把「每次都重新分类」换成「5 秒内复用上次分类」，看着像放松，实际安全面没有变宽——socket 永远钉在缓存里那个已被判为 LAN 的地址上，DNS 中途改成公网 IP 也改不掉拨号目标；代价只是新鲜度：对端换了地址会在「条目过期」或「第一次拨号失败」时自愈。入站侧的准入校验（`lan_http_url`，SUBSCRIBE 回调、SetURI/SetNextURI 用）刻意保持每次都真解析，所以 `test_dlna_protocol.py:1060` 那条「准入仍然解析它放行的主机」的既有契约一字未动。
- 2026-09-18 — R74 效果（只报可数的，不报计时）：10 次 SOAP 动作的解析次数 **20 → 1**、20 次 NOTIFY 投递 **20 → 1**，而出网请求次数不变（10 次拨号仍是 10 次，证明不是靠少发包换来的）；同一探针跑两遍结果逐字相同。本地量不到的是每次解析真实耗时（取决于用户路由器和 NAS 的 DNS 状态），所以不写百分比。
- 2026-09-18 — R74 测试 +11：`test_dlna_network.py` 41 → 52 条。新增 `DlnaLanAddressCacheTests`：复用计数（暖/过期/分端口/大小写折叠）、拨号失败后必须重新解析、被拒答案不得污染缓存、LRU 上界与逐出可观察、**观察线程计时证明解析不在缓存锁里**（沿用 R72 那套），以及控制侧三条：一次动作只解析一次、去掉早校验后非 LAN 仍然拒绝且不得拨号（`opener.open.assert_not_called()`）、非文本端点仍是 ValueError。
- 2026-09-18 — R74 变异矩阵（`%TEMP%\r74verify.py`，仓库外副本，5 个 DLNA 模块）：K1 恢复重复校验、K2 绕过缓存、K3 永不过期、K4 拨号失败不失效、K5 无上界、K6 把解析挪进锁内、K7 键里去掉端口、K8 键不折叠大小写——**八条全部被杀，每条对应一条指定用例**，K0 绿。写测试时的两次自伤也记下来：假响应对象声明了 `Content-Length` 却用 stub 返回空 body，先撞上「response is truncated」；以及父 `Mock(side_effect=...)` 不会作用到子属性调用，伪装成 `'Mock' object is not iterable`。另外主动删了一处只在 mock 下才可达的死守卫（`if addresses:`），而不是给它补测试。
- 2026-09-18 — R74 门限：round97 测试 2190 条、138.008 s、OK (skipped=2)、JS `checks passed` 行数 65、manifest 694 条。仓库外副本已清空，scratch 目录无残留。
- 2026-09-18 — R73 取证（一个请求解析四次同一件事）：`cached_thumbnail_for_item` 里三处各自解析媒体身份版本——`_cache_paths`（:953，经 `_cache_key` 调 `cover_source_version(item)`）、内存键（:957）、渲染锁键（:978），加上 `serve_cover` 为 ETag 自己再算一次（原 server.py:1691），一次封面请求最多 4 次。原代码里 `server.py` 那段注释写着「URL 版本、ETag 与缩略图缓存刻意使用同一个 source version」，实现却是四次独立解析，所以这个「同一个」只是巧合成立：标签写入或扫描器更新落在两次解析之间，磁盘文件按版本 A 落盘、内存条目按版本 B 记账、渲染去重按版本 C 上锁。
- 2026-09-18 — R73 修法：把版本做成一次性解析再往下传。`_cache_key(item, size, version=None)` 与 `_cache_paths(item, config, size, version=None)` 接受注入值，`cached_thumbnail_for_item(..., version=None)` 在函数开头解析一次并供磁盘键、内存键、锁键共用；`serve_cover` 在调用缩略图链路之前解析一次，把同一个值同时交给缓存查询和 ETag。新参数一律追加在末尾且默认 None，所有既有位置参数调用不受影响。注释里的「刻意同一个」现在由构造保证。
- 2026-09-18 — R73 撤回我自己的性能结论（重要）：第一次单点采样测到 1529 us/请求 降到 1129 us/请求（-26%），但改成**交替重复**的 A/B（每变体 3 轮、每轮取 4 次最好值）后是 1162/1114/1084 对 1185/1116/1065，中位数 1114 对 1116，差异完全落在抖动里（单轮散布 ±12%）。所以本轮不主张任何本地吞吐收益，只主张可数的调用减少：暖路径版本解析 2 到 1、渲染路径 3 到 1、无索引行的 `os.stat` 每请求 2 到 1。NAS 上少的那一次 stat 值多少，本地量不出来，留给真机。
- 2026-09-18 — R73 键分裂的后果（能测才写）：让版本源在第一次解析后改变，修复前内存条目记在 B 而文件躺在 A 名下，于是下一次看到 B 的请求**找不到**已缓存的缩略图、重新渲染一遍，而 A 那个文件再没有任何人按名字能读到，也没有任何失效路径会去删它，变成 `covers/` 里永久不可达的垃圾——这条与既有的「covers 无界增长」是同一个来源，本轮把机制补进那条待办。
- 2026-09-18 — R73 测试 +3：`test_cover_cache.py` 里一条计数用例（暖路径与渲染路径各自必须只解析 1 次）、一条键分裂用例（用迭代器当版本源，第二次调用就 `StopIteration`，断言磁盘别名与内存键同源）；`test_http_integration.py` 里一条端到端用例，把 `server.cover_source_version` 与 `cover_cache.cover_source_version` 同时换成计数器，要求整条封面链路 1 次解析，并核对 ETag 里的版本与落盘文件名的键一致。`test_cover_cache.py` 67 → 69 条（1.6 s），`test_http_integration.py` 76 → 77 条，全局 2176 → 2179。
- 2026-09-18 — R73 变异矩阵（`%TEMP%\r73verify.py`，仓库外副本，5 个模块）：J1 磁盘键重算、J2 内存键重算、J6 `_cache_key` 忽略注入值，都被键分裂与计数用例杀掉；J3 锁键重算被计数用例杀掉；J4 端点不再传值、J5 端点为 ETag 再算一次，被端到端用例杀掉；J0 绿。写测试时我自己错了两次：先断言 `<key>.jpg` 存在，而当前写入者产出的是 `<key>.asset` 别名（`.jpg` 只有旧版本才会留下），第二次是在没读写入者的情况下猜扩展名——断言必须对着真正被写出的东西写。
- 2026-09-18 — R73 顺带量到更深一层（本轮**没有**顺手改）：`allow_disk=False` 的承诺被键计算路径绕开。`_cache_key` 里那句 `cover_source_version(item)` 用的是默认 `allow_disk=True`，所以即便调用方声明「翻页不许打磁盘」，无索引行仍然每行 stat 两次（实测：`allow_disk=False` 3 到 2 次 stat，`allow_disk=True` 3 次；已索引行 0 次）。真正的修法会改变可见结果：翻页若改用不打磁盘的降级版本算键，就找不到按权威版本落盘的缩略图，这些行的 `cover_thumbnail_url` 会退化，属于产品可见的取舍，需要先看真实库里到底多少行缺索引身份（CUE 行、刚扫进来的行），已单独立项。
- 2026-09-18 — R73 门限：round95 测试 2179 条、131.330 s、OK (skipped=2)、JS `checks passed` 行数 65、manifest 694 条。仓库外副本与样例目录已清空。
- 2026-09-18 — R72 取证（全局锁里的一次 stat）：`cover_cache.thumbnail_asset_id_for_item` 在读到 `_ASSET_ALIAS_CACHE` 命中后，在**持有 `_MEMORY_CACHE_LOCK` 期间**做 `os.path.isfile(cached_path)`（:366-367）。这把锁是整个封面服务共用的：`_memory_get`、`_memory_put`、`clear_memory_cache`、缺失标记缓存、别名缓存裁剪都在这把锁里（:508、:520、:534、:464、:486）。用脚本扫了全部 10 处 `with _MEMORY_CACHE_LOCK`，只有这一处包含文件系统调用，其余 CLEAN。调用面也不是冷路径：`library_presentation.py:53` 的 `public_library_item(..., allow_cover_disk_lookup=True)` 默认走磁盘口径，只有批量列表那一条（:140）传 False，所以一次带封面的单条序列化会逐行在全局锁里 stat。
- 2026-09-18 — R72 严重度实测（不抄审计报告）：把 stat 换成受控阻塞后，用观察者线程去抢同一把锁，修复前等待 **5.0088 s**（这是测试里注入的阻塞上限，也就是等待时长等于那次文件系统调用的耗时，SMB 失联时这个数可以是几十秒），修复后同一测得的等待 < 0.2 s 且断言通过。受害者不只是封面请求：预热工作线程、以及任何一次 `_memory_put`（新渲染的缩略图入缓存）都要排在后面。
- 2026-09-18 — R72 修法：把 stat 挪到锁外，读缓存与之后的两处写缓存各自单独取锁；两处写都改成**先比值再动**（`if _ASSET_ALIAS_CACHE.get(alias) == cached`）。这不是装饰：释放锁的窗口里，别名裁剪或 `clear_memory_cache` 可能已经把这条 key 删掉，裸 `move_to_end` 会抛 `KeyError`（直接落在用户请求上）；而另一线程可能已经写入一个**刚校验过的新 id**，裸 `pop` 会把别人的正确结果删掉。
- 2026-09-18 — R72 成本 A/B（`%TEMP%\r72bench.py`，暖别名缓存、真实文件、单进程）：单线程 18.66 us/调用（修复前 18.76），也就是多出来的两次加锁在本地盘上量不出来；四线程并发聚合 39840 调用/秒 对 37585，**+6.0%**。真正的收益不在暖缓存吞吐，而在被卡住的那 5 秒不再传染给整个服务。
- 2026-09-18 — R72 测试：`test_cover_cache.py` 62 → 67 条。新增：观察者线程计时（锁作用域）、同秒竞态下「只删自己验证过的那条」（要先把别名**文件**删掉，否则磁盘路径会重新发布同一个 id，把 pop 的效果掩盖掉，见下条教训）、stat 期间被 `clear_memory_cache` 清空不得抛错也不丢结果、以及一条新的不变量：资产文件被删之后，暖别名缓存**不能**继续对外报出这个 id。
- 2026-09-18 — R72 两个变异第一轮存活，都记成规则：H2（无条件 `pop`）存活是因为我的注入 hook 不幂等，别名文件还在时磁盘路径会把 id 重新写回缓存，掩盖了 pop 的后果，测试看起来「通过」其实是测错了对象；修法是删掉别名文件让磁盘路径闭不上环，并加 `assertTrue(swapped)` 保证那条路径真的被走到。H5（读缓存不加锁）存活是因为 Python 里 `RLock` 的持有者不可探测，别的线程问不出「你现在是不是持着它」；改用一个形状断言把「读必须落在 `with` 块里」钉住（`test_cover_lock_scope_is_pinned_by_shape_where_threads_cannot_probe_it`），同时保留行为断言钉「stat 必须在锁外」，两条规则各管一段。
- 2026-09-18 — R72 变异矩阵（`%TEMP%\r72verify.py`，仓库外副本，封面与呈现层 4 个模块）：H1 把 stat 放回锁内被计时测试杀掉（就是那 5.0088 s）；H2 无条件 pop、H3 裸 `move_to_end`、H4 快速翻页路径也去 stat、H5 读缓存不加锁、H6 命中不复核，各由对应测试杀掉；H0 绿。
- 2026-09-18 — R72 门限：本轮 round93 测试 2176 条、142.878 s、OK (skipped=2)、JS `checks passed` 行数 65、manifest 694 条。仓库外副本与样例目录都已清空。
- 2026-09-18 — R71 取证（门禁里唯一赌磁盘空间的样例）：`test_build_release_script.py:391` 用 `handle.truncate(10 * 1024 ** 3 + 1)` 造出十吉字节的合法数据长度，只为了让 `tools/verify_release_evidence.ps1` 的尺寸守卫拒绝它。round85 因此报 `OSError: [Errno 28] No space left on device`（当时临时卷只剩 2.18 GB，是我自己造的仓库拷贝污染，但那件事正说明这个样例把门禁的成败绑在了空闲空间上）。这种失败在门禁日志里与产品缺陷完全不可区分，而且不是偶发：每跑一轮门禁都要向文件系统要 10 GiB。全仓扫过一遍，只有这一处需要吉字节级样例（其余 truncate 最大 16 MiB：`test_http_integration.py:305` 与两处 `MAX_ARTWORK_BYTES + 1`）。
- 2026-09-18 — R71 修法沿用仓库既有原则（把界做成显式注入参数并断言其被使用，而不是造大文件）：`tools/verify_release_evidence.ps1` 新增 `[long]$MaxArtifactBytes = 10GB` 与 `[long]$MaxAndroidArtifactBytes = 1GB`，默认值就是发布策略本身，恢复流程与 `index_release_evidence.ps1 -ArtifactDirectory ... -Json` 都不需要改（两处调用都是具名参数，追加参数不影响）；非正数在打开任何文件之前被拒绝；两条守卫改读参数，消息里报告生效字节数。
- 2026-09-18 — R71 样例改成字节规模并且能判别：4 KiB 产物 + `-MaxArtifactBytes 4095` 必须拒绝，并且 `SHA256SUMS` 里故意留一个错校验和，如果守卫没有先跑，失败消息会变成「SHA-256 does not match」，所以两条断言合起来钉的是顺序而不只是拒绝；再加一条正好等于界（4096）必须通过，把 `-gt` 写成 `-ge` 的变异就落网；Android 侧车用 `-MaxAndroidArtifactBytes 15` 单独跑一遍，证明第二个参数确实接进了那条守卫而不是只在参数表里挂着。
- 2026-09-18 — R71 诚实记录一条测不到的形状：把守卫挪到哈希之后（变异 G1）**只被形状断言抓到**，行为测试全绿。原因是字节规模的样例无论顺序如何都能哈希成功，真实代价（对一篇十吉字节的损坏证据去算哈希）在小样例上根本不可观测。所以顺序契约只能由 `test_release_verifier_bounds_artifact_before_hashing` 承担，本轮把它从「两条字符串存在」升级成 index 比较（守卫必须先于 `Get-Sha256Hex -Path $recordPath` 与 Android 那处哈希，校验必须先于遍历循环）。
- 2026-09-18 — R71 变异矩阵（`%TEMP%\r71verify.py`，仓库外副本，2 个脚本模块 33 项）：G0 绿；G1 守卫排在哈希后由形状断言杀掉；G2 忽略注入参数（改回 `10GB` 字面量）与 G3 改成 `-ge` 由行为样例杀掉；G4 Android 守卫忽略参数由新侧车样例杀掉；G5 默认界被从 10GB 降到 1GB 由策略漂移断言杀掉；G6 校验从 `-lt 1` 放宽到 `-lt 0` 由零界样例杀掉（0 被接受意味着任意大的产物都能通过）。
- 2026-09-18 — R71 对照自身也是取证：G0 连红三轮才绿。第一轮缺 `RECOVERY.md`（`test_offline_verification_script` 要读恢复手册）；第二轮缺 `android-client/app/build.gradle`（`build_release.ps1:152-156` 在碰撞检查之前就要它）；第三轮清理失败，`tools/blutter/.git/objects/pack/*.idx` 是只读文件，`shutil.rmtree(ignore_errors=True)` 静默留下半个目录树，下一次 `os.makedirs` 直接 `FileExistsError`。现在按「测试实际读取什么就复制什么」枚举，并用 `onexc` 处理器 chmod 兜底。门禁侧遗留：构建侧两处界（`build_release.ps1:283`、`build_android_release.ps1:105`）仍是字面量，本轮未动，理由与后续写在 TODO。
- 2026-09-18 — R71 门限：`artifacts/offline-20260918-round90.log` **Ran 2171 tests in 142.665s / OK (skipped=2)**，exit 0；Python 2169 到 2171（本轮删 1 条十吉字节样例、新增 3 条，净 +2），JS `checks passed` 行数仍 65，`SOURCE_MANIFEST.sha256` 694 条（无新文件，两个测试文件的哈希已更新）。仓库外变异副本与临时样例目录都已清空，未新增常驻占用。
- 2026-09-18 — R71 效果量化：门禁里这一项请求的合法数据长度从 `10 * 1024 ** 3 + 1` 字节（约 10.74 GB）降到两个合计 4112 字节的样例文件，`skipped` 数没有增加（仍是 2 条既有跳过），也就是说顺序与边界两条契约现在在**任何**有空间的机器上都会真的跑，而不是空间紧张时要么硬失败要么只能跳过。事故当时的空闲空间是 2.18 GB，本轮实测 C: 卷总 249.7 GB、剩 30.8 GB：十吉字节样例只剩三个数量级的余量，这类样例本身就不该留在门禁里。
- 2026-09-18 — R70 取证（读侧限量、写侧不限量 = 隐形增长）：`favorites` 表只有 `load_user_state` 的 `LIMIT MAX_PERSISTED_FAVORITES`（state_store.py:256-257），写侧完全没有裁剪，而同一个函数在两个分支结尾都调了 `_trim_persisted_playlists`（:351、:360）并写着理由「delta 写与盘上已有行合并，不做最后的事务内裁剪就会无限长」。收藏正是漏掉这一件事的那张表：过期客户端的 delta 保存走 `INSERT OR IGNORE`（:334-336），每次最多带 50000 个新 id，行与行之间永不复用。实测（`%TEMP%\r70bench2.py`，cap 用真实值 50000、每次 delta 加 50000 个新 id、revision 故意写旧）：表行数 0 → 50000 → 100000 → 150000，而读侧始终只返回 50000，也就是**第 3 次保存之后有 10 万行是任何客户端都看不见的**；`state.sqlite3` 每轮 +3.1 MiB（0.1 → 9.3 MiB），保存耗时也从 24 ms 涨到 184 ms。
- 2026-09-18 — R70 修法与对齐：新增 `_trim_persisted_favorites(conn)`，在 `save_user_state` 的两个分支之后统一调用一次（覆盖 delta 与全量替换两条路径，也不给未来第三条路径留空子），沿用 playlist 那边已经确立的「事务内最后裁剪」形态，而不是另发明一套配额。裁剪删除的是**读侧顺序的补集**：reader 用 `ORDER BY created_at DESC, rowid DESC LIMIT cap` 保留最新的 cap 行，于是删除按 `created_at ASC, rowid ASC` 取最旧的 excess 行，同秒批量写入时的 rowid 决胜方向也与读侧一致，客户端可见列表一个字都不会变。
- 2026-09-18 — R70 两处成本选择（都量过）：一是用 `SELECT COUNT(*)` 早退而不是无条件 DELETE，常态（不超界）只多一次计数；二是删除语句用 `rowid IN (SELECT rowid ... ORDER BY 最旧 LIMIT excess)` 而不是 `rowid NOT IN (SELECT ... 最新 LIMIT cap)`，前者在 100000 行时 36.5 ms、450000 行时 318.6 ms，后者分别是 82.0 ms 与 446.2 ms（两种写法保留的行完全相同，含 `row-099999`/`row-449999` 这两条最新行）。另外 `LIMIT -1` 在 SQLite 里等于「不限」，所以早退守卫不只是优化：少了它，`excess` 为负时会把整张表删空（变异 F5 正是这样被杀掉的，而且同时被既有的 playback 保存测试抓到）。
- 2026-09-18 — R70 我自己的一次误删（如实记录，并把它变成证据）：给 `save_user_state` 挂裁剪调用时，一次 edit 的替换文本只锚定了相邻行，把 else 分支里两条 `INSERT OR REPLACE`（`playback_sessions`、`ui_preferences`）一起删掉了；这条改动如果落地，全量保存就不再写播放会话与界面偏好。是改完按习惯 read 回看被改区间才发现的（当时还没跑测试），已恢复两行并把裁剪改成两分支之后统一调用一次。顺手把这个错误形状做成变异 F7：现有测试确实抓到（`playback_session_can_be_saved_without_replacing_media_lists` 一类），所以真正的教训不是「测试会兜住」，而是 edit 成功不等于内容正确，加语句的替换块必须包含需要保留的行。
- 2026-09-18 — R70 测试：`test_state_store.py` 30 → 34 条。四条分别是：过期 delta 连做三轮，表行数必须 ≤ cap、可见列表仍是客户端最新的排首、三轮后存活集合恰好是最后两批；一组 6 形状（正好到界、超一个、同秒批量、混合并列、空表、单行）拿**读侧原样 SQL**当参照实现做全表比对，并同时断言 `load_user_state` 返回同一序列；cap 之内必须一条 DELETE 都不发（复用 R65 的 `_CountingConnection`）；以及一条把「请求界」与「存储界」分开的漂移守卫（见下条）。
- 2026-09-18 — R70 变异（`%TEMP%\r70verify.py`，仓库外副本，3 个状态模块）：F1 完全不裁剪只被那条 delta 用例杀掉（正是要修的缺陷）；F2 多留一行、F3 删最新而不是最旧、F4 rowid 决胜方向翻转，都被参照比对与 delta 用例一起杀掉；F5 去掉早退守卫被三条测试杀掉，其中一条是既有测试；F6 把请求规范化界从 50000 抬到 200000 **第一轮存活**：两个界数值相同的时候，任何行为测试都分不出是哪一个在起作用，补了「把存储界抬到 50001、送 50002 个 id、结果仍是 50000 条且顺序一致」这条漂移守卫后才杀掉。
- 2026-09-18 — R70 门限与遗留：`artifacts/offline-20260918-round88.log` **Ran 2169 tests in 136.806s / OK (skipped=2)**，Python 2165 到 2169（本轮 +4 条），JS `checks passed` 行数仍 65，`SOURCE_MANIFEST.sha256` 694 条（无新文件，`state_store.py` 与 `test_state_store.py` 哈希已更新）。修好后的行为（`%TEMP%\r70bench3.py`，五轮 delta 每轮 50000 个新 id）：表行数钉在 50000、可见列表 50000、保存耗时 161-169 ms 不再随轮次上升、db 停在 5.6 MiB 不再增长。遗留一条：行数有界但**文件不回收**（被裁掉的页留在库里），已立案，不在本轮顺手 VACUUM。
- 2026-09-18 — R69 取证（先复现再修，含 A/B 严重度实测）：`DlnaEventService.subscribe` 在 `with self._lock:` 里调用 `_callback_url` → `network.lan_http_url` → `_lan_addresses` → `socket.getaddrinfo`（network.py:58），而 getaddrinfo 没有任何超时参数可传。这把锁是事件面唯一的锁：`subscribe`、`unsubscribe`、`notify_renderer`、`snapshot` 全要它。真正把它变成控制面故障的是 `service.py:620` 的 `self.renderer.add_state_listener(self.events.notify_renderer)` 加上 `renderer._notify():423-432` 在**调用者线程上同步**跑监听器，于是别人的一次 SUBSCRIBE 会直接拖住我的传输控制。A/B 探针 `%TEMP%\r69severity.py`（同一支 SetAVTransportURI 请求，把解析打桩成 2.0 s）：修复前该控制请求等待 **2.002 s**（正好是整个窗口），修复后 **0.005 s**，两边都返回 200。
- 2026-09-18 — R69 第二处（容量判断不看租约是否还活着）：准入门是 `if len(self._subscriptions) >= MAX_EVENT_SUBSCRIPTIONS: raise`，而过期回收只发生在 `notify_renderer`、`snapshot`、`_drain_subscription` 三处的顺带清扫。渲染器空转、UI 关闭时这三处都不会跑，于是 64 个名额可以被「订阅完就消失」的控制器占满，新来的合法控制器一律 412。修法是在做容量判断的那条路径上先扫一遍，而不是再加第四个定时清理者。
- 2026-09-18 — R69 顺带合并重复：过期清扫原来手写了两遍且不一致（`notify_renderer` 用 `item["expires"]`，缺键会 KeyError；`snapshot` 用 `item.get("expires", 0)`），现在统一成 `_sweep_expired_locked(now)` 一处，取宽容口径：内部字典一定写入了 expires，缺键只可能是逻辑错误，宁可回收这条租约也不要让事件线程抛 KeyError 把整批通知带走。
- 2026-09-18 — R69 刻意保留的既有语义：RENEW 分支仍然不解析 CALLBACK（旧代码也是在 `if sid:` 返回之后才解析，行为一致）；解析失败的优先级仍高于容量失败（旧顺序就是先解析后判容量）；`test_event_subscriptions_are_bounded` 用 64 条**存活**租约撑满后仍然必须被拒，准入清扫不会误伤活租约。把校验搬到锁外没有削弱它：它检查的是 URL 自身的属性（ scheme、端口、是否只解析到 LAN 地址），不依赖共享状态。
- 2026-09-18 — R69 测试：`test_dlna_protocol.py` 76 → 79 条。三条分别是：线程观测（解析打桩卡在 2 s 时，另一条 `notify_renderer` 必须在 0.2 s 内返回）、固定时钟下的准入回收（64 条失效租约 + 各自排队的 body，新订阅必须成功且 `_pending_notifications` 从 64 归 0、表里只剩新订阅自己）、以及用假 socket 模块证明校验**确实**还在走解析（LAN 地址放行并返回规范化 URL、`8.8.8.8` 仍被拒），防止「挪出锁」顺手变成「不校验」。
- 2026-09-18 — R69 变异（`%TEMP%\r69verify.py`，仓库外副本，5 个 DLNA 模块 130 条）：M1 把解析搬回锁内，**只**被计时观测测试杀掉；M2 去掉准入清扫、M3 清扫不释放排队 body、M4 清扫永不回收、M5 清扫回收全部活租约、M6 校验退化成不解析，各被对应测试杀掉。M3 与 M4 同时被既有测试 `test_event_snapshot_expiry_releases_queued_notification_pressure` 杀掉，说明合并后的 helper 仍然守着 snapshot 那条老语义。第一版 M1 不干净（顺带把清扫也删了，两个缺陷混在一起），改成「只搬锁、保留清扫」后才是隔离的单一故障。
- 2026-09-18 — R69 一处由我自己造成的环境事故（如实记录）：严重度探针用 `shutil.copytree(ROOT, ...)` 复制**仓库根目录**，每次 6.1 GB 且结束时不清理，三次运行把 `%TEMP%` 所在卷写到只剩 2.18 GB，于是门限 round85 唯一一条失败是 `src/tests/test_build_release_script.py:398` 的 `handle.truncate(10 * 1024 ** 3 + 1)` 抛 `OSError: [Errno 28] No space left on device`（与本轮代码改动无关）。比空间更值得注意的是它**复制了活动中的 `prefix/.android-avd/`**：清理时 `data/misc/pstore/pstore.bin` 报 WinError 5 拒绝访问，说明这台机器上有一份正在使用的模拟器镜像被整份拷走过，这既有污染磁盘的风险也有损坏模拟器的风险。清理后回到 20.94 GB，三个残留目录已彻底删除；探针已改成只复制 `src/` 并在末尾 `rmtree`。同状态复跑 round86 全绿，证明 round85 就是这次磁盘挤压。顺带暴露一条真实的测试脆弱性：那条用例对临时卷可用空间有隐式依赖，在几乎写满的 NAS 上会以 ENOSPC 失败，已立案。
- 2026-09-18 — R69 门限：round85（`artifacts/offline-20260918-round85.log`）**Ran 2165 tests / FAILED (errors=1)**，唯一失败就是上面那条 ENOSPC；同状态复跑 `artifacts/offline-20260918-round86.log` **Ran 2165 tests in 135.659s / OK (skipped=2)**，Python 2162 到 2165（本轮 +3 条），JS `checks passed` 行数仍 65，`SOURCE_MANIFEST.sha256` 仍 694 条（无新文件，`dlna/service.py` 与 `test_dlna_protocol.py` 哈希已更新）。
- 2026-09-18 — R68 取证（自己复现，不抄子代理结论）：`Seek` 分支原来是 `self.renderer.command("seek", _seconds(args.get("Target")))`（service.py:623-624），完全不看 `Unit`；而 `_seconds`(:104-120) 把一切读不出来的值折成 `0.0`。探针 `%TEMP%\r68probe.py` 走 `control()` 全链路并观测 `renderer.command` 实参：`ABS_TIME 0:01:30` → seek(90.0) 正确；`REL_TIME +0:00:30` → seek(0.0) 且 HTTP 200（合法的三十秒快进被静默倒回曲目开头并报告成功）；`REL_TIME -0:00:10`、`TRACK_NR 2`、`ABS_COUNT 1000`、缺 `Target`、`999:99:99` 全部同样是 seek(0.0)+200；`ABS_TIME 10:00:00` → seek(36000.0)，因为 `renderer.py:227-228` 只有 `max(0.0, position)`，没有上界。
- 2026-09-18 — R68 的关键决定是兼容性而不是 spec 严格性：本仓库自己就是「`REL_TIME` + 无符号绝对时间」的发送方（`control_point.py:252-253` 把 `seconds_to_upnp_time(position)` 塞进 `Unit=REL_TIME`，`server.py:499` 调用它），所以按 spec 拒绝无符号 REL_TIME 会直接打断 fnAudio 控制 fnAudio。规则定为：无符号时钟在 ABS_TIME 与 REL_TIME 下都按绝对位置处理，带 `+`/`-` 才是相对当前投影位置的偏移；`ABS_TIME` 配符号是自相矛盾，回参数错误而不是猜。
- 2026-09-18 — R68 修法：同一个时钟解析拆成两口径 —— 严格的 `_time_seconds()`（读不出来抛 ValueError）与宽容的 `_seconds()`（状态投影用，折 0，语义一字未改），新增 `_seek_position(unit, target, position, duration)` 做 Unit 白名单、符号相对、`max(0)` 下界与已知时长上界钳制，并在**改动传输状态之前**抛出；`control()` 的 ValueError 分支已经把它映射成 `faultcode s:Client` + errorCode 402。fault 文案点名具体参数（`invalid Seek target`、`unsupported Seek unit`、`signed target requires REL_TIME`），因为 faultstring 是控制器侧唯一的诊断信息。
- 2026-09-18 — R68 删掉一处自己刚写的不可达分支：`_seek_position` 初版有 `if not math.isfinite(resolved): raise`，但 `_finite()` 已经把 position/duration 归一成有限值、`_time_seconds()` 又保证结果 ≤86400，该分支永远进不去、也无法被任何变异证明。选择删除而不是留一条测不到的守卫。
- 2026-09-18 — R68 测试：`test_dlna_protocol.py` 新增 3 条（14 形状的接受表、13 形状的拒绝表、端到端一条经 `control()` 的 Seek：相对跳转必须 `command("seek", 90.0)` 且 200，四种被拒形状必须 500/402 并且 `command` 总共只被调用过一次）。十三个 DLNA 模块 167 → 171 条全绿。
- 2026-09-18 — R68 变异（`%TEMP%\r68verify.py`，仓库外副本，五个 DLNA 相关模块 86 条）：P1 恢复「忽略 Unit」被端到端杀掉；P2 去掉相对偏移、P3 去掉上界、P5 放开 Unit 白名单、P6 改成严格 spec 解读（拒绝无符号 REL_TIME）、P8 把 bool 当数字，各被具名测试杀掉；P7 把 `_seconds` 改成直接抛，被**既有**的 `test_transport_time_helpers_reject_nonfinite_and_invalid_components` 杀掉，说明拆分没有动它的语义。P4（去掉 `max(0)` 下界）第一轮**存活**：我的用例 `-0:01:00` 从 60 秒恰好减到 0，边界值落在边界上不算边界用例，补了 `-0:02:00` 才杀掉。锚点顺带暴露 `isinstance(value, bool) or not isinstance(...)` 这段习语在 service.py 已有三处（:59/:73/:144），立案不顺手改。
- 2026-09-18 — R68 门限：`artifacts/offline-20260918-round83.log` **Ran 2162 tests in 141.429s / OK (skipped=2)**，Python 2159 到 2162（本轮 +3 条）；JS `checks passed` 行数仍 65，`SOURCE_MANIFEST.sha256` 仍 694 条（无新文件，`dlna/service.py` 与 `test_dlna_protocol.py` 哈希已更新）。修复后同一支探针复跑：`ABS_TIME 0:01:30` → 90.0；`REL_TIME +0:00:30` → 30.0（相对投影位置 0，不再倒回开头）；`REL_TIME -0:00:10` → 0.0 且 200（下界钳制）；`TRACK_NR 2`、`ABS_COUNT 1000`、缺 `Target`、`999:99:99` 四种 → HTTP 500 的 402 参数错误，`renderer.command` **一次都没被调用**；缺 `Unit` 仍按 ABS_TIME 宽容处理（45.0）。`ABS_TIME 10:00:00` 在探针里仍是 36000.0，因为桩后端把时长报成 0（未知时长故意不做上界），钳到 180.0 那条由单元表 `(("ABS_TIME", "10:00:00", 60.0, 180.0), 180.0)` 钉住。
- 2026-09-18 — R67 记账过程自身的一处错（记录纪律本轮被测试抓回来）：TODO 的三条新项第一次写进了**第 80 行**而不是顶部，因为脚本按「从第 2 行起第一个非 bullet 行之前」算插入点，而 TODO.md 的前 79 行全是 bullet、空行在 83 行。`tests/test_change_record.py:26-37` 的 `flat_entries` 只看标题后第一段连续非空行，于是判为日期倒序（line 80 的 2026-09-18 跟在 2026-09-17 之后）。改成复刻测试的作用域与比较键（Y/M/D 三元组、只看前导段）后重插到顶部，`test_change_record` 与 `test_source_hygiene` 十条恢复全绿。结论：新增条目的插入位置必须按**测试定义的作用域**算，不能按肉眼看到的段落边界算。
- 2026-09-18 — R67 取证一（写盘失败击穿响应）：`cached_thumbnail_for_item` 里三处落盘完全没有保护：负标记 `_atomic_bytes(missing, b"")`、`secure_directory(asset_root)` 与 asset 写入、以及 alias 写入（原 984-1005 行）。磁盘满、只读挂载或权限拒绝时 OSError 直接冲到 HTTP 层（`server.py:1678`），冷封面变 500，而此时渲染好的 JPEG 已经在内存里。同文件 `generate_asset_thumbnail:440-445` 早就写着契约「缓存写失败不能失败响应」并配了测试（`test_cover_cache.py:911`），本路径是对称遗漏。
- 2026-09-18 — R67 顺带挖出的第二个缺陷（写失败还会对外宣称不存在的资产）：修复前的 alias 内存缓存 `_ASSET_ALIAS_CACHE[alias] = asset_key` 无条件执行，而 `thumbnail_asset_id_for_item` 的 `allow_disk=False` 快路径（:360-362）**不回查磁盘**直接返回缓存值，页面序列化于是引用一个盘上没有的资产，前端拿到的封面链接是坏的。现在内存登记挪到 `else` 分支：只有 asset 与 alias 两次写都成功才对外宣称。
- 2026-09-18 — R67 取证二（预热去重长期失效）：`_prewarm_result_exists`(:280-288) 只查 `<key>.jpg` 与 `<key>.none`，但全部 `_atomic_bytes` 调用点只写 missing / asset_target / alias 三处（:441/:986/:1002/:1005），成功路径产生的是 `<key>.asset` 文本别名，**从不写 `.jpg`**。所以现代缓存里凡是渲染成功的条目预热永远判为「没有结果」，每次翻页都重走完整路径（开别名、读回最多 8 MB JPEG、挤占内存 LRU）。`.jpg` 不是废检查：它是 :944/:964 仍在读的旧版本遗留文件，所以保留并补上 `.asset`。
- 2026-09-18 — R67 为什么以前没人发现：`test_cover_cache.py:238-251` 用手工创建的 `.jpg` 来断言预热跳过，即测试自己造了一个写入路径永远不会产生的文件状态，把死检查照成绿。本轮把这条换成诚实夹具：三种标记（`.asset`、`.none`、遗留 `.jpg`）各自断言「预热不再重渲染」，另加一条空缓存对照断言「没结果时仍然要预热」，防止把修复做成第二个死分支。
- 2026-09-18 — R67 顺带核实并删除冗余：`secure_directory(root)` 在分支前无条件调用，而 `_atomic_bytes` 第一步就是 `secure_directory(os.path.dirname(path))`（:872），别名与标记的写入都经过它，故该调用重复；删除后 `test_thumbnail_is_persisted_and_reused`（全新临时目录、预建目录不存在）仍然通过。把这一行加回去的变异 N5 无测试可杀，属可证的等价删除，同时说明这条改动的行为面只在异常路径。
- 2026-09-18 — R67 测试与变异：`test_cover_cache.py` 1 条换成 6 条（+5，模块 62 条，三个封面模块共 72 条）。变异（`%TEMP%\r67verify.py`，仓库外副本）：N1 去掉 `.asset` 判定被诚实夹具杀掉；N2 撤掉负标记保护被 `test_failed_negative_marker_write_still_answers_the_miss` 杀掉；N3 让 asset 写失败继续抛出被两条杀掉；N4 把内存别名登记挪回写前被 `test_failed_asset_persist_does_not_advertise_an_unstored_asset` 杀掉；N5 等价存活（如上）。工作树两文件哈希前后一致。
- 2026-09-18 — R67 门限：`artifacts/offline-20260918-round81.log` **Ran 2159 tests in 142.608s / OK (skipped=2)**，Python 2154 到 2159；JS `checks passed` 行数仍 65，`SOURCE_MANIFEST.sha256` 仍 694 条（本轮无新文件，cover_cache.py 与 test_cover_cache.py 哈希已更新）。两条 R66 立案项已勾销，另立 3 条：预热判定不校验 alias 内容、封面写入的 fsync 代价、以及只读挂载与 ENOSPC 的真机验证。
- 2026-09-18 — R66 取证：`dlna/xml_policy.py` 的声明守卫在**原始字节**上搜 `<!\s*(?:doctype|entity)\b`，而 expat 会从 BOM 或 NUL 填充里自动认出 UTF-16。探针（`%TEMP%\r66probe.py`）实测：同一个 DTD 炸弹，UTF-8 字节被拒（ValueError），UTF-16 带 LE BOM、带 BE BOM、以及**无 BOM 的 utf-16-le / utf-16-be 四种全部放行**，484 字节的 payload 展开成 2430 字符，只有 UTF-32 被 expat 自己拒掉。链路可达：`server.py:1605` 把 socket 原始 body 交给 `control()` → `service.py:170 safe_fromstring(raw)`，不经任何再编码。
- 2026-09-18 — R66 把审计给的严重度量实（结论比报告小一半）：本机 CPython 3.14.6 + expat_2.8.1 自带 billion-laughs 保护，8 MiB 阈值之上放大倍率超过 100 即拒（探针：1000 倍在 15.3 ms / 19.3 MiB 峰值处被拒）。所以攻击面不是「1 KB 打到 GB」的无限 OOM，而是**在 1 MiB 请求上限内每次约 50 MB、约 40 ms 且全程持有 GIL** 的可重复抖动（实测最大在法内样本：1,040,400 字节 → 52,000,000 字符，42.2 ms，峰值 49.6 MiB）。外部实体另测：ElementTree 根本不解析（`undefined entity`），所以**不存在任意文件读**。三处结论与审计报告不一致，按实测记录。
- 2026-09-18 — R66 修法（一处归一化，不改解析器）：新增 `_declaration_scan_view(payload)`，把 NUL 字节折掉再搜。ASCII 标记在 UTF-8/UTF-16LE/BE/UTF-32 里都是「一个非零字节 + 若干 NUL」，折掉 NUL 后所有形态都塌回 ASCII 模式，同一份文档不写守卫时是真实可展开的炸弹、写守卫后被拒；无 BOM 的 16 位形态也覆盖，因为它同样靠 NUL 被识别。守卫依旧在大小检查之后、`ET.fromstring` 之前，不动解析器构造。
- 2026-09-18 — R66 覆盖面核实（改一处够不够）：全仓 `src/app` 里 `ET.fromstring` 只出现一次，就是守卫内部；`control_point.py:146/158`、`renderer_presentation.py:40` 命中的三处 `ET.` 只是 `ET.ParseError` 异常处理。对端 XML 的进入点是 `service.py:170`、`control_point.py:145/157/311/442`、`renderer_presentation.py:30`，全部经 `safe_fromstring`。所以这一处归一化就是收口点，没有第二把门。
- 2026-09-18 — R66 测试：`test_dlna_xml_policy.py` 3 到 9 条。矩阵含 us-ascii、utf-8、utf-8 带 BOM、utf-16 带 LE/BE BOM、无 BOM 的 utf-16-le 与 utf-16-be，七种形态都必须以 ValueError 收（断言到消息，不接受 ParseError 蒙对）；反向兼容同矩阵钉住：同一编码去掉 DTD 必须正常解析。另加夹具有效性断言（绕开守卫直接喂 expat，证明它确实会展开到 3^5×10=2430 字符）、NUL 单独拆开 `<!ENTITY` 的形态、以及转义过的 `&lt;!ENTITY` 文本不得被误判。端到端两条进 `test_dlna_protocol.py`：UTF-16 的 SetAVTransportURI 带 DTD 必须 500 且渲染器状态不变（`uri` 仍为空），不带 DTD 的三种 UTF-16 变体必须 200 且 `snapshot()['uri']` 真的更新。
- 2026-09-18 — R66 过程教训（记进纪律）：第一版夹具把 `<!ENTITY e1 "&e0;&e0;&e0;">` 的引号写丢了，文档本身不合法。这种情况下拒绝测试**照样能过**（ParseError 不是 ValueError，断言仍红→绿），但它测的已经不是攻击样本。发现点是拿同一份文本去喂解析器量严重度。因此本轮补了那条「夹具必须真的会展开」的断言，把这件事变成机器检查而不是自觉。
- 2026-09-18 — R66 变异（`%TEMP%\r66verify.py`，仓库外副本，82 条 DLNA 用例整模块跑）：M0 原样通过；M1 撤销 NUL 折叠被 3 条新测试杀掉；M2「干脆禁掉 UTF-16」这种偷懒修法被兼容测试杀掉（`test_escaped_markup_in_a_utf16_body_is_not_a_declaration` 与端到端 200 那组，11 处红）；M3 只留 doctype 丢掉 entity 被 2 条杀掉；M4 只在有 BOM 时才折叠被无 BOM 变体杀掉。工作树四个相关文件哈希前后一致。
- 2026-09-18 — R66 顺手项与门限：`server.py:23` 的 `from xml.etree import ElementTree as ET` 全仓无引用，删除（删前确认 `server.ET`、`ET.` 在 server.py 内均零命中）。门限 `artifacts/offline-20260918-round78.log` **Ran 2154 tests in 182.031s / OK (skipped=2)**，Python 2146 到 2154（+8）；因本轮耗时明显高于近期区间，同一状态复跑 `round79` 得 **156.026s**，确认 182 s 是与仓库外变异/探针并发造成的争用，不是改动带来的成本。`SOURCE_MANIFEST.sha256` 仍 694 条。
- 2026-09-18 — R65 取证（先量后改）：`_trim_persisted_playlists` 对表里**每一个**播放列表发一条 DELETE 加一条 COUNT，而它在 `save_user_state` 的两条分支上都会跑，位置在 `BEGIN IMMEDIATE` 事务内、`_STATE_WRITE_LOCK` 持有期间（`state_store.py:316` 与 `:325`）。上限是播放列表 1000、单个 10000、总量 50000。实测基准（`%TEMP%\r65bench.py`，内存库）：10 个播放列表 23 条语句 0.46 ms，100 个 203 条 8.48 ms，1000 个 2003 条 27.71 ms，而这三种情况全都一行都不用删。UI 侧 `scheduleUserStateSave` 与 10 秒一次的状态保存都会走到，等于常态性地在写锁里空转两千条语句。
- 2026-09-18 — R65 修法：把逐播放列表的 DELETE/COUNT 对换成一次 `SELECT playlist_id, COUNT(*) FROM playlist_tracks GROUP BY playlist_id`，只在真正超出预算时才补发那条带 `rowid NOT IN (... LIMIT ?)` 的删除，预算扣减逻辑一字未动。同一批形状重测：1000 个播放列表 2003 条降到 4 条、27.71 ms 降到 6.52 ms；100 个 203 条降到 4 条、8.48 ms 降到 3.77 ms；10 个 23 条降到 4 条、0.46 ms 降到 0.24 ms。
- 2026-09-18 — R65 语义保持的证据：把**改之前的算法逐字抄成测试内的参考实现**，用 12 种形状各建两份一模一样的库，一份跑新实现一份跑参考实现，比较 `playlists` 与 `playlist_tracks` 全表内容。形状覆盖空库、空播放列表、恰好等于上限、播放列表数超限、单个超限、总量先咬、两者同时咬、带孤儿行、超限加孤儿、空列表排在最前与中间（预算不该被它花掉）。另加一条规模不变性断言：20/60/100 个播放列表时语句数必须相等（旧实现是 42/122/202）。
- 2026-09-18 — R65 如实标注收益边界：这次优化针对的是「什么都不用删」的常见路径。真要删的时候没有收益甚至略慢：1000 个播放列表各 1000 首，旧 1009.23 ms、新 1025.35 ms（多出的一次 GROUP BY 扫描约 16 ms，换来少发 1049 条语句）；500 乘 200 是 81.07 到 68.53 ms。也就是说病态规模下时间由删除本身决定，本轮不宣称那种场景变快。
- 2026-09-18 — R65 顺带钉住的不变量：显式的 `DELETE FROM playlist_tracks WHERE playlist_id NOT IN (...)` 不能因为外键级联存在就删掉。库里确实 `PRAGMA foreign_keys = ON`（既有测试已断言），但级联只对当时有父行的子行生效，建库早期留下的孤儿行没人清。这条以前**没有任何测试覆盖**，现在由等价矩阵里的孤儿形状钉住；夹具构造有个坑：`PRAGMA foreign_keys` 在已开事务里是空操作，必须先 commit 再切开关并回读断言。
- 2026-09-18 — R65 变异：Q1 恢复成逐播放列表 DELETE/COUNT 对被成本测试杀掉（20 个播放列表发了 23 条）；Q2 去掉 `count > keep_count` 守卫每次必删，也只被成本测试杀掉；Q3 预算永不扣减、Q6 用裁剪前的行数扣减，被等价矩阵与既有 overflow 测试共同杀掉；Q4 把「查不到的播放列表」当成花掉预算，只有新矩阵能杀（既有测试看不见）；Q5 去掉孤儿清理，只有新矩阵能杀。全部在 `%TEMP%\r65verify` 的仓库外副本上跑完整 `test_state_store`，结尾比对哈希确认工作树未变。
- 2026-09-18 — R65 门限：`artifacts/offline-20260918-round76.log` **Ran 2146 tests in 140.955s / OK (skipped=2)**，Python 用例 2144 到 2146（本轮新增两条），JS `checks passed` 行数保持 65，`SOURCE_MANIFEST.sha256` 仍 694 条（无新文件，`state_store.py` 与 `test_state_store.py` 哈希已更新）。另外本轮用两个只读子代理并行开审 `cover_cache.py` 与 `dlna/service.py`，结论待其回报后另轮处理，不预先采信。
- 2026-09-18 — R64 补记：记录写完之后发现 `localIsPlayingNow()` 被写成 `isPlayingNow()` 的同形尾巴，两行重复正是本轮规则要避免的东西，于是改成 `isPlayingNow()` 尾部委派（与 `currentSeconds` 同一形状），并补两条防线：本地播放态尾巴在 `app.js` 中只允许出现一次，`isPlayingNow` 必须以委派收尾。新增变异 P10 把尾巴复制回去：它被静态形状杀掉，但在删掉静态块的测试副本上存活，因为复制在语义上完全等价。这类「只防漂移、不防行为故障」的断言必须单独标注，不能混进行为覆盖率里邀功。复跑：文档后 `round73` **Ran 2144 tests in 145.364s / OK (skipped=2)**，重构后 `round74` **Ran 2144 tests in 143.616s / OK (skipped=2)**，JS `checks passed` 行数保持 65，69 个 JS 套件逐个复跑零失败，`SOURCE_MANIFEST.sha256` 仍 694 条（`app.js` 哈希已更新）。
- 2026-09-18 — R64 根因：R61 把 `currentSeconds()`/`seekDuration()`/`isPlayingNow()` 改成按状态切换数据源（受控会话 → 远端 → 宿主播放器 → `<audio>`）之后，显示是对的，但**做决策的消费者继承了受控端的数字**。本轮按 R63 立下的规矩逐个 grep 消费者，抓到两处。可达性证据是 `stopLocalAudio()` 的调用点只有三处（`loadCurrent` 的 remote 分支、DSD 失败、停止路径），投送开始并不会暂停本地元素，所以「本地在跑 + 受控端在放」是同时成立的常态。
- 2026-09-18 — R64 症状一（`audio.ontimeupdate` 的 cue 段收尾）：受控端播到 99.9/100 而本地 cue 曲目才走到段内第 0 秒（`currentTime` 5 减 cue 起点 10，夹到 0）时，旧写法把两个受控端数字当成尾点条件成立，于是改的是**本地队列**的 `state.index` 并调 `loadCurrent()`，也就是投送方结束导致本机切歌。修法是把该判断改成读本地权威（元素或宿主播放器自己的秒数与段长），后面的绘制仍然读共享 getter，所以投送时进度条照旧跟投送方。
- 2026-09-18 — R64 症状二（`commitQueue` 交棒宿主播放器）：队列保存后若宿主正在播当前条目，UI 用 `nativeLoadQueue(isPlayingNow(), currentSeconds(), true)` 告诉 Android 宿主「接着这里播」。投送进行中这两个值都来自受控端，等于让宿主跳到投送方的位置并镜像投送方的播放/暂停态，设备上表现为凭空跳位或被暂停。改成 `localIsPlayingNow()` 与 `localPlaybackSeconds()`。
- 2026-09-18 — R64 实现方式：抽出 `localPlaybackSeconds()`（把 `currentSeconds` 的尾巴逐字搬走，原处改为 `return localPlaybackSeconds();`）、`localPlaybackDuration()`（`seekDuration` 去掉受控端与远端 cue 两条分支，`seekDuration` 本身一字未改）、`localIsPlayingNow()`（`isPlayingNow` 的同形尾巴）。之所以 seconds 能零漂移而 duration 不能：`seekDuration` 的 native 分支排在远端分支之前，任何重排都会改变优先级，所以新函数只服务「调用方已排除 remote」的场景，并用测试钉住这一前提。
- 2026-09-18 — R64 判定后保留的站点（同样查过，故意不改）：`isPlayingNow()` 的另三处消费者是 MediaSession 的 `playbackState`/`positionState`（2155/2182/2202）与 `addQueueAndPlay` 的「别打断正在播的东西」（3991）。它们跟主 UI 是同一口径：投送时 `$("playBtn")` 的点击本身就发给受控端，所以 OS 媒体面板与主控件必须一致，跟着受控端是对的。这类「审过但不改」的结论也进记录，并把需要真机确认的部分立案。
- 2026-09-18 — R64 验证方式：新文件 `src/tests/test_ui_playback_authority.js`，沿用 vm 抽取套路但这次连 `commitQueue` 一起抽进沙箱（stub `apiFetch`/`applyConfirmedQueue`/`nativeLoadQueue` 等），静态 13 条，行为含：投送结束不动本地队列、本地尾点照常切歌、投送与本地尾点同时存在时仍要切（这条专门用来否决「投送时整段跳过」的省事改法）、无下一首时改为暂停、宿主与流式来源各自的算法、remote 提前返回。关键的是 24 组等价矩阵：无受控会话且非 remote 时，新旧 getter 必须逐项相等，证明这次抽取没有改变任何既有行为；再加一组「有受控会话时必须不相等」，否则新加的判断就是死代码。
- 2026-09-18 — R64 变异：P1 收尾判断退回共享 getter、P2 混用（本地秒数对受控端长度）、P3 投送时整段跳过（错误改法）、P4 不减 cue 起点、P5 段长改取整文件长、P6 尾巴复制而非委派、P7 绘制改用本地对、P8 交棒改回共享 getter、P9 本地播放态重新受投送影响，九项全部被新测试杀掉。每个故障还额外在「删掉静态形状块」的测试副本上复跑一次，杀掉结果不变，说明没有用形状断言冒充行为覆盖。邻居对照：P1 不被 R63 的陈旧度测试杀，P3/P7 不被 R61 的受控端测试杀，三份测试职责互不重叠。全部在 `%TEMP%\r64verify` 仓库外副本上进行，结尾比对哈希确认工作树未变。
- 2026-09-18 — R64 门限：`artifacts/offline-20260918-round72.log` **Ran 2144 tests in 154.152s / OK (skipped=2)**，JS 离线 `checks passed` 行数 64 到 65（新增 `test_ui_playback_authority.js`），69 个 `tests/test_*.js` 先逐个本地复跑无失败，`node --check` 对 `app.js` 通过；本轮没有 Python 用例增减，`SOURCE_MANIFEST.sha256` 693 到 694 条。
- 2026-09-18 — R63 文档后复跑：根文档写入之后再跑一次门限，`artifacts/offline-20260918-round71.log` **Ran 2144 tests in 152.503s / OK (skipped=2)**，JS `checks passed` 行数仍是 64，说明本轮根文档（含补销 R62 那条立案项）没有破坏 `test_change_record` 与 `test_source_hygiene` 的唯一性检查。连同 R62 的两次，本轮前后三次耗时 152.066 / 152.207 / 152.503 秒，稳定在同一档，进一步支持「`round68` 的 188 秒是抖动」这个判断。三份根文档不在 `SOURCE_MANIFEST.sha256` 范围内，693 条无需重刷。
- 2026-09-18 — R63 根因：传输位置的外推没有任何上界，而「状态通道已断」与「曲目仍在播」在数据上不可区分。`state.rendererSnapshotAt` 只在**被接受的**快照上更新（`app.js:1981` 的 `refreshRendererSession` 成功分支、`2112` 的控制成功乐观更新），而该函数在 `!response.ok`（1972）、请求换代早退（1971/1974）、`catch` 吞异常（1984）三条路径上直接返回，时间戳一动不动；远端同理（`2373` 只被版本门放行的 `applyRemoteStatus` 写，5 秒兜底轮询还要过 `isRemoteEventConnected` 门）。`currentSeconds()` 于是把 `Date.now() - snapshotAt` 当作播放进度无限累加。
- 2026-09-18 — R63 症状与外溢面（都是算术与调用点，不是观感猜测）。以 position=12、duration=100 为例：断流 88 秒后进度条被顶到满格并永久停在那里，`#elapsed` 一直显示 `1:40 / 1:40`；时长未知（`duration <= 0`，网络广播与不上报长度的受控端）时线性无界，断流 10 分钟标签读成 `10:12`。更要紧的是这个造出来的数字会离开页面：`nativeRemoteUpdate()`（`app.js:820`）把它作为 `updateRemoteState` 的参数交给 Android 宿主，通知栏与锁屏进度跟着一起错；`audio.ontimeupdate` 的 cue 段收尾判断（8064）拿同一个函数当触发条件，且只挡了 `isRemoteTarget()` 没挡 incoming 会话。
- 2026-09-18 — R63 修法：新增单一入口 `transportExtrapolation(snapshotAt, playing)` 与常量 `TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS = 10`，两条分支都改走它，内联算墙上时间差的写法清零。10 秒是推导出来的：健康状态下最慢的快照来源是远端 5 秒兜底轮询（`ui_sync_scheduler.js:46`，且仅在事件流断开时启用），受控端状态轮询 1.5 秒（`ui_sync_scheduler.js:49`），取最慢健康节奏的两倍作为「不再是在跟踪设备、而是在编时间」的分界。选夹住而不是退回最后一次上报位置，是为了让一次慢轮询内仍然平滑，超过窗口才停住。
- 2026-09-18 — R63 顺带修掉同一条表达式上的第二个形状：负位置。旧写法不检查符号，远端非 cue 分支把 `raw` 原样返回（`Math.max(0, ...)` 只包在 cue 分支上），时钟回拨（NTP 校正、跨时区携带的宿主）会让 `#elapsed` 与 `#seek` 取到负值；新入口对 `elapsed > 0` 之外一律返回 0，并同时挡掉 `snapshotAt` 为 0（初始态）与非数值两种退化。
- 2026-09-18 — R63 验证方式：新文件 `src/tests/test_ui_transport_staleness.js`，沿用仓内 vm 抽取套路（按名字取函数与常量原文进沙箱），静态 4 条（两条分支不得再内联计算、恰好一处夹取、两个调用点各过一次入口），行为 24 条：新鲜快照按真实年龄外推、窗口内完全信任、超窗口冻在 `12 + 10 = 22`、未知时长不再随时间增长（把时钟再推 10 分钟，位置一字不动）、PAUSED 不外推、无快照不外推、时钟回拨不倒扣、cue 段仍减段首、远端分支同界。变异 7 项 N1 到 N7 全部被新测试杀掉（删夹取、删符号守卫、删 playing 守卫、删零值守卫、上限改 0.5、上限改 600、只改一半分支），全程在 `%TEMP%\r63verify` 的仓库外副本上跑，脚本结尾比对哈希确认工作树未变。另留一条对照 N8：把受控端分支退回旧写法时，R61 的 `test_ui_renderer_transport.js` 照样通过，说明两个测试不重叠，别把重叠断言当独立覆盖。
- 2026-09-18 — R63 如实标注的取舍：夹住之后最坏情况从「显示成 100% 假满格」变成「比真实位置最多慢 10 秒」。标签页隐藏期间调度器不跑（`ui_sync_scheduler.js` 的 `every()` 带可见性门，`hidden` 时还会停掉远端事件流），恢复时 `resume()` 立刻补发请求，但恢复后的第一帧仍可能拿旧快照绘制，所以会出现短暂少报；我认为少报比假满格诚实，但没有真机观感证据，已立案待确认。任何一次被接受的快照都会重新开窗（包括用户按传输键的成功乐观更新），冻住不会变成永久卡死。
- 2026-09-18 — R63 门限：`artifacts/offline-20260918-round70.log` **Ran 2144 tests in 152.207s / OK (skipped=2)**，Python 用例数持平（本轮无 Python 用例增减），JS 离线套件 `checks passed` 行数 63 到 64（新增一个测试文件，门限按 `tests/test_*.js` 自动发现），`node --check` 对 `app.js` 通过，`SOURCE_MANIFEST.sha256` 692 到 693 条。总耗时 152.207 秒对上 R62 的 152.066 秒，几乎一致，反过来印证了 `round68` 那次的 188 秒确属抖动而不是代码变慢。
- 2026-09-18 — R62 补上门限那条承诺的对照复跑：根文档写入之后再跑一次，`artifacts/offline-20260918-round69.log` **Ran 2144 tests in 152.066s / OK (skipped=2)**，JS 离线套件 `checks passed` 行数持平 63，证明本轮根文档改动没有破坏 `test_change_record` 与 `test_todo_checklist_entries_are_unique`（后者拿整份 `TODO.md` 比对条目唯一性，不只是顶部连续段）。三档耗时放在一起看：`round67` 126.053s（2141 项）、`round68` 188.205s、`round69` 152.066s（同为 2144 项）。本轮新增用例自身约 4.4 秒，解释不了同一棵代码两次相差 36 秒，只能记成机器抖动，因此不要再从单次门限耗时里读趋势；要用耗时当指标就得先固定并发条件（本轮 `round68` 与变异验证、六次关闭实测在时间上相邻，`round69` 独占机器）。本轮只改根文档，未动源码与测试，故未再刷新 `SOURCE_MANIFEST.sha256`（三份根文档不在其清单内，692 条不变）。
- 2026-09-18 — R62 接管说明（先把状态写清，避免把中断当成完成）：上一会话在 R62 中途断流，`CHANGELOG_AI.md` 与 `TODO.md` 停在 R61，但工作树里已经有 R62 的代码改动。本轮用 `SOURCE_MANIFEST.sha256`（上次刷新于 R61 记录时）与工作树 mtime 对拍，锁定四个「上次门限之后被改过」的文件：`src/app/server/server.py`、`src/app/server/metadata_service.py`、`src/tests/test_metadata_service.py`、`src/tests/test_server_lifecycle.py`；门限日志显示 `round66` 有 1 条 ERROR、`round67`（同一棵树）通过，而这四个文件的修改时间都晚于 `round67`，所以它们的代码在本轮之前从未被任何门限验证过。接管时先跑那几条相关用例，其中一条直接报 `StopIteration`（见下面第四条），证明中断现场不是「已完成、只差记录」。
- 2026-09-18 — R62 修掉「关闭时元数据 worker 还能领新工作」。`_claim_job()` 在 `stop_event` 已置位后仍然从 `metadata_jobs` 领取任务并发起 provider HTTP，而 `shutdown()` 的 join 预算是在置位之前一次性测得的（空闲 3 秒），于是这条新工作必然活到预算之外。修复前实测（`%TEMP%\p752.py`，六次）：`shutdown waited 3.01s returned_clean=False`，返回时仍有 2 条 `fnaudio-metadata-fetch-recovery-*` 线程存活；`%TEMP%\p753.py` 抓到的栈停在 `providers.album → musicbrainz_album → _open_metadata_url`。修法是在 `_claim_job` 首行 `if self.stop_event.is_set(): return None`（`metadata_service.py:2890`）：任务行留在 pending 才是给下一代生命周期的诚实状态，而不是让关闭去追一份它永远覆盖不到的新工作。测试 `test_claim_job_refuses_new_work_once_shutdown_has_started`；变异 M1（把守卫条件换成恒假）当场失败。
- 2026-09-18 — R62 修掉「预算测早了，在飞作业的 deadline 还没登记」。真正需要等的是已经在飞的 provider 链，而作业预算直到 `_process_job()` 内部（`metadata_service.py:2978`）才写进 `_active_job_deadlines`：在 `stop_event` 置位前几微秒领到任务的 worker 正好落在这次测量之后，3 秒空闲预算对一条最坏 15 秒（歌词）/30 秒（上限）的链不覆盖。同一复现的第二次运行报 `shutdown waited 8.10s returned_clean=False`，栈在 `_process_job → track_candidates → _joox_songs → _open_metadata_url`，此时 `deadlines` 已有键。修法：join 循环每 0.25 秒切片复查一次已登记的作业终点，有则把 `deadline` 延到 `ends_at + 1.0`，并始终封顶在 `hard_deadline = started + MAX_JOB_BUDGET_SECONDS + 1`（31 秒）。
- 2026-09-18 — R62 在接管时修掉中断现场自己引入的新缺陷：那条延展写成会往前滑的预算。上一会话留下的形态是 `deadline = min(hard_deadline, max(deadline, time.monotonic() + self._worker_shutdown_timeout()))`，而 `_worker_shutdown_timeout()` 的**空闲分支返回 3 秒**：没有作业在飞时 `now + 3` 恒大于当前 `deadline`，于是每个切片都把预算整体续期，「四条 lane 共享一份预算」被它自己摧毁，一个永久卡住的 worker 就能把一次 drain 拉到 31 秒上限。这条不是推测：它随附的确定性测试在本轮接手后首次运行就报 `StopIteration`（`shutdown` 的 join 与退出判断各自取时钟，固定的 5 值 `side_effect` 不可能匹配 0.25 秒切片下的调用次数），说明该用例从未与这版代码同时通过过。修法：抽出 `_active_job_ends_at()`，只接受有限数值、显式拒布尔，返回最长在飞作业的绝对终点或 `None`；`_worker_shutdown_timeout()` 与延展都改从它取值，且延展只在 `ends_at is not None` 时发生。确定性测试重写为 `test_shutdown_shares_one_join_budget_across_all_workers`：假时钟按每次 `join(timeout)` 真实推进，断言四条 lane 都被 join 且切片合计不超过 3.25 秒。变异 M3 把代码还原成滑动形态后，该测试失败而 late-deadline 测试**通过**，证明「等得到在飞作业」与「总等待有界」是两条必须分别钉住的不变量。
- 2026-09-18 — R62 修掉 drain 顺序：句柄回收必须排在所有读者之后。`server.shutdown_runtime()` 的 `cleanup_steps` 原先把 `close_library_connections()` 放在第 5 步、`METADATA_SERVICE.shutdown()` 放在最后，还在 provider 链里的 worker 可以在 drain 之后把曲库句柄放回池，索引文件因此活过关闭；Windows 上的表现正是本轮触发点：门限 `round66` 有一条偶发 ERROR（`test_track_match_pending_projects_independent_cached_artwork` 在 `TemporaryDirectory` 清理时报 `PermissionError: [WinError 32]` 指向 `cache\library.sqlite3`），去掉文档改动后的 `round67` 同树通过，属间歇性。修法是把 `close_library_connections()` 移到 `cleanup_steps` 末尾并写明理由（`server.py:3222`），`test_shutdown_runtime_drains_library_handles_after_the_library_stops` 的期望序列改为 `["refresh", "watcher", "metadata", "handles"]`。
- 2026-09-18 — R62 实测效果与三条否证。修复后同一复现脚本六次全部 `returned_clean=True`、`live_after=[]`、`cache/library.sqlite3` 重命名探测 `rename=ok`；关闭耗时不再是固定 3 秒，而是跟随当时在飞的作业：2.90 / 3.02 / 4.81 / 5.65 / 10.84 / 10.89 秒（同脚本 `track_match` 稳定在 5.62-5.65 秒）。这是设计意图而不是回归：宁可多等一段**有上界**的在飞作业，也不要留下删不掉的临时目录。否证其一，曲库连接池不是这个 flake 的病因，实测该配置下 `pool={'idle':0,'creations':0}`（池按 `config["library_connection_pool"]` opt-in，测试的 `_config()` 并未开启）；否证其二，「掉队 worker 在兄弟清位后停满一个 tick」的场景不可复现（被禁用的 lane 在 `_process_job` 之后走 `continue` 而不是 park），所以 join 循环里那三次 wake `.set()` 只作为**廉价但未被独立钉住**的防御保留，原先把它当契约的那条弱测试已删除替换；否证其三，除 `_active_job_ends_at` 之外没有发现新的预算来源，`MAX/DEFAULT/LYRICS` 三个预算常量仍是 `metadata_request_budget.py` 的 30/15/12。
- 2026-09-18 — R62 立案两条本轮不动的东西。其一，补员线程命名 `fnaudio-metadata-fetch-recovery-%d` 的 `index` 取自 `range(replacement_count)`，永远从 0 开始，多次补员后会重名，真机排查时看不出是哪一条。其二，`refreshRendererSession` 在 `!response.ok`（`app.js:1972`）、token 换代早退（1971/1974）与 `catch` 吞异常（1984）三条路径上都不更新 `state.rendererSnapshotAt`，而 `currentSeconds()`（4385 incoming、4394 remote）继续按墙上时间外推：时长已知时贴到 `duration` 停住，时长未知（`duration <= 0`，网络广播与部分 DLNA 受控端）时**无界**增长。R61 让传输行每 1.5 秒重绘，等于把这个既有缺陷从看不见变成看得见；要改先定「陈旧多久冻结显示」的口径，仓内 `LIBRARY_PAGE_SNAPSHOT_TTL_MS` 与 `librarySnapshot.stale` 是现成先例。
- 2026-09-18 — R62 门限：`artifacts/offline-20260918-round68.log` **Ran 2144 tests in 188.205s / OK (skipped=2)**。计数增量 2141 到 2144（净 +3）已逐条对拍门限日志：新增的是 claim 守卫、late-deadline、`_active_job_ends_at` 边界三条，`test_shutdown_uses_one_deadline_for_all_metadata_workers` 与那条弱测试各被同位替换故不增减；JS 离线套件 `checks passed` 行数持平 63，`SOURCE_MANIFEST.sha256` 692 条。本轮总耗时从 127 秒档跳到 188 秒，新增用例自身只贡献约 4.4 秒，其余按机器抖动记录，并在写完根文档后再跑一次作对照。
- 2026-09-18 — R61 修掉「投送时进度条冻住」，这是缺陷而不是观感优化。`updateIncomingRendererUi()` 在全仓**只有一个调用点**：`updateRemoteUi()` 的第一行（`app.js:2047`，`if (updateIncomingRendererUi()) return;`），而 `updateRemoteUi` 的唯一定时驱动是 `ui_sync_scheduler.js:50` 的 `every(500, () => { if (check("isRemoteTarget")) call("updateRemoteUi"); })`。关键在于 `isRemoteTarget()` 判的是**外放目标**（`fnAudioPlaybackTargetPolicy.isRemote(state.playTarget)`），`isIncomingRendererSession()` 判的是 `state.rendererSession?.uri`（fnAudio 被当作 AVRender/GMF 受控端），两者互相独立；而 `seekDuration()`（`app.js:4403`）与 `currentSeconds()`（4372）早就为 incoming 分支读取渲染会话的 `duration`/`position` 并按 `rendererSnapshotAt` 外推。于是「手机投进来、本机目标仍是 local/DAC」这个组合下，`#elapsed`、`#duration`、`#seek` 与播放图标**没有任何定时器驱动**，只有用户按传输键（`controlIncomingRenderer`）、标签页可见性恢复（`resume()`）或远端事件路径才画一次；同时 `#nowTime` 挂在 `updateNowMarquee → syncPlayerProgress` 上仍每 1.5 秒走字，症状正是「小字在动、进度条不动」。修法两条：`renderIncomingRendererSession` 在 `updateNowMarquee()` 之前调用 `updateIncomingRendererUi()`，让 1.5 秒状态轮询自己把传输行画对；调度器 500 ms 门改成 `isRemoteTarget() || isIncomingRendererSession()`（`updateRemoteUi` 在 incoming 分支提前 return，不会去读远端快照）。
- 2026-09-18 — R61 把 R60 的「同址即 no-op」推广到传输行其余写入。26 处 `$("nowTitle")`/`$("nowArtist")`/`$("elapsed")`/`$("duration")` 的 `textContent =` 直写全部改走仓内**已有**的 `setTextContentIfChanged`（该函数原先只被 `updateLibraryStatusDecorations` 的 8 处调用使用，是既成模式，不另造入口），分布为 nowTitle 6、nowArtist 7、elapsed 8、duration 5，改写后直写残留 0；新增同族 `setStyleVarIfChanged(node, name, value)`（与文本 helper 相邻、同样带缺节点守卫）接管 `--seek-fill`（`updateSeekRail`）与 `--marquee-distance`（R60 里临时写的那处内联比较）；`setPlayButton` 改为把请求状态记在 `dataset.playing`（`"playing"`/`"paused"`）再比较，因为它原先每秒两度用 `innerHTML` 重建 `.transport-icon` span（图标是纯 CSS 伪元素，所以代价是样式与布局失效，不是重新取图）。两条诚实标注：`textContent` 的同值比较是确定性跳过；`getPropertyValue` 对自定义属性的返回值若被某引擎补了空白，该处收益就退化为「仍每轮写一次」，等于 R61 之前的行为，源码注释与复查触发点都写明了这个退化。
- 2026-09-18 — R61 验证方式。新文件 `src/tests/test_ui_renderer_transport.js`（134 行）分两层：静态形状 5 条（四个 id 不再被直写、`button.innerHTML` 与 `transport-icon ${` 各仅一处、`--seek-fill` 与 `nowTime` 各单一写入点、poll 路径必须调用 transport 绘制），以及 vm 行为层——把 `clock`/`seekPercent`/两个 helper/`syncNowPlayingTime`/`syncPlayerProgress`/`updateSeekRail`/`setPlayButton`/`renderIncomingRendererSession`/`updateRemoteUi`/`updateIncomingRendererUi` 从 `app.js` 原文抽进同一沙箱，喂 `{uri, transport:"PLAYING", position:12, duration:100}` 且 `isRemoteTarget() === false` 的会话，断言 `#duration=="1:40"`、`#elapsed=="0:12"`、`seek.value==12`、`--seek-fill=="12%"`、`#nowTime=="0:12 / 1:40"`、图标为 `pause-icon`；再喂一次完全相同的快照，断言**节点写次数增量为 0**；把 position 推到 40，断言只有 elapsed/nowTime/fill 三处各 +1 而标题与艺术家仍是 1 次；把 transport 改成 PAUSED，断言只多一次图标写，随后重复同一状态不再多。`test_ui_sync_scheduler.js` 新增三种门控组合（仅 remote / 仅 incoming / 两者皆无）逐 tick 断言。变异验证 8 项（`%TEMP%\p748.py`，全部在 `%TEMP%\r61mut2` 的仓库外副本上进行，工作树零风险）：删 poll 调用 → 形状与行为两条各自失败（M1 / M1b「The transport row must learn the render duration」）；图标去重失效 → M2 / M2b「An identical transport snapshot must not touch the DOM」；文本同值短路删掉 → M3；样式同值短路删掉 → M4；`updateSeekRail` 回退成无条件写 → M5；调度器门退回单条件 → M6「An incoming render session must paint the transport row without being a remote target」。
- 2026-09-18 — R61 量化后决定不改三条。其一，`renderIncomingRendererSession` 现在每轮会触发两次 `syncPlayerProgress()`（`updateIncomingRendererUi` 结尾一次、`updateNowMarquee` 结尾一次），本轮之后两次都是全同值比较，成本是若干字符串构造与 `getPropertyValue`；不合并是因为要从 `updateNowMarquee` 里摘掉 `syncPlayerProgress`，就得同时复核它其余 8 处调用点（`updateNowMarquee()` 全仓共 9 处调用）各自的意图。其二，`#seek` 的 `.value` 不做去重：range 输入按 `step` 吸附，拿「期望值」与 `node.value` 比较在不同引擎上不等价，而 4 Hz 下一次数字属性赋值的收益远小于引入一份比较状态的风险。其三，投送结束后传输行仍留着上一次投送的数字（`restoreLibraryNowPlaying` 只管标题/艺术家/封面），这与本轮去重无关、是先前就有的陈旧状态，需要「本地没有播放时这一行该显示什么」的判断，已单独立案。
- 2026-09-18 — R61 门限：`artifacts/offline-20260918-round65.log` **Ran 2141 tests in 128.117s / OK (skipped=2)**（用例数持平，本轮无 Python 用例增减）；JS 离线套件 `checks passed` 行数 62 → 63（新增一个测试文件；`Get-ChildItem src/tests -Filter test_*.js` 现为 67 个文件，全部通过），`node --check` 对 `app.js` 与 `ui_sync_scheduler.js` 通过，`SOURCE_MANIFEST.sha256` 691 → 692 条。`src/app/ui/app.js` 非空行 8100 → 8120（总行数 8,140）。
- 2026-09-18 — R60 修掉「播放中封面每 1.5 秒闪一次」。`src/app/ui/app.js` 里对 `#nowCover` 的直接写入共 6 处（`renderIncomingRendererSession`、`restoreLibraryNowPlaying` 的两个分支、`loadCurrent` 的远端/原生/本机三条出口），对 `#lyricsCover` 另有 2 处，全部是无条件 `innerHTML = ...`；而 `ui_sync_scheduler.js:49` 每 **1500 ms** 调一次 `refreshRendererSession`（`visibilitychange` 恢复时 `resume()` 还会立刻再补一次），DLNA 输入会话激活走 `renderIncomingRendererSession`、退出走 `restoreLibraryNowPlaying`，10 秒一次的 `refreshServerUserState` 也经 `refreshUserStateChrome`（`app.js:1437`）落在同一函数上，于是同一个已经解码完的 `<img>` 每 1.5 秒被销毁并重新解码一次，观感就是封面闪。歌词侧还有第二条同形状轮询：`scheduleLyricsPoll` 每 **900 ms**（上限 15 次）重进 `loadLyricsForCurrentTrack`，而它第一句就是 `updateLyricsMeta`，所以后台取歌词期间 `#lyricsCover` 同样反复重画。修法：新增 `setCoverArtwork(node, source)`（`app.js:1908`）与薄包装 `setNowPlayingCover(source)`，用 `node.dataset.coverSource` 记住上一次真正写进 DOM 的地址，同址直接 `return false` 且不触 DOM；8 处写入点全部改为经由该入口，全仓 `this.remove()` 与 `$("nowCover")`/`$("lyricsCover")` 的内联直写归零（`$("nowCover")` 现仅存 1 处，在包装函数内部）。这是 R51/R53「同一地址重复解码」家族在播放条上的实例，与 R59 的「每行下载量」是两条互相独立的收益。
- 2026-09-18 — R60 的去重逼出一个必须当场决定的旧缺陷。原写法 `onerror="this.remove()"` 在加入「同址不再重绘」之后语义就变了：图片加载失败时 `<img>` 被移除，而 `dataset.coverSource` 仍等于那个失败地址，于是后续每一轮重绘都被跳过，**框子从此永久空白**（旧代码没有去重，所以每 1.5 秒还会再试一次，代价是把必然失败的请求打满整轮）。本轮定为「失败即降级、换址才重试」：改成 `onerror="this.parentNode.innerHTML='\u266b'"`（源码里以 `\u266b` 转义写出，模板字面量在运行时解析为占位字符），既不留下空白框，也不把重试塞进轮询；换曲目时地址必然变化，因此天然获得重试。再议触发点已进 TODO：若真机出现「本地封面偶发 503 之后整张专辑永久占位」，应改为带上限的单次退避重试，列表行封面调度器的 `retry<1` + 450 ms 是现成先例。
- 2026-09-18 — R60 顺带压掉同一条轮询里的强制布局抖动。`updateNowMarquee()`（`app.js:1868`）旧写法在同一个 `forEach` 里对 `nowTitle`、`nowArtist` 逐个「读 `scrollWidth`/`clientWidth` → 写 `--marquee-distance`」：读几何会强制布局，写样式又使它再次失效，所以每次调用至少两次强制布局，而它同时挂在 1.5 秒轮询、原生桥 `mediaId` 变化（`app.js:900`）与每次切曲的路径上。改为两遍走：先把两个节点的测量值全部读完（`nodes.map(...)`）再统一写，并加「新值与当前内联值相同就不写属性」的短路。DOM 最终状态与旧写法逐项等价（`classList.toggle(name, force)` 本就幂等），差别只在少一次布局与少一次同值写入。函数首行的 `mobile-search-active` 早退被 `test_ui_mobile_layout.js:28` 钉住，故本轮只动函数体。
- 2026-09-18 — R60 验证方式。旧断言 `nowCoverInsertions.length >= 5`（`test_ui_library_loading.js:406`）实际上把「六处各自无条件重画」当成了契约，本轮把它翻译成更强的不变量：不得再出现 `$("nowCover")`/`$("lyricsCover")` 的 `innerHTML`/`textContent` 直写，且全文件 `node.innerHTML = next` 只允许 1 处；随后用 `vm.runInNewContext` 把 `setCoverArtwork`/`setNowPlayingCover` 抽出对拍 12 条行为断言（首个地址绘制 1 次、同址 no-op 且写次数不变、改址必须重绘、地址必须过 `escapeHtml`、非字符串归一为空、清空落到占位字符、清空后保持、`lyricsCover` 共用同一去重且 `onerror` 回退到占位字符、缺失节点忽略），`test_ui_mobile_layout.js` 另加 2 条「先测后写 / 同值不写」断言。变异判定：删掉 `if (node.dataset.coverSource === next) return false;` 立刻让「repeated address must be a no-op」与「poll must not re-decode」两条失败；把 `escapeHtml(next)` 换成 `next` 让转义断言失败；把 `distances` 的预读挪回 `forEach` 内让批量断言失败（最后这条是形状契约，强度弱于行为契约，如实标注）。
- 2026-09-18 — R60 门限：`artifacts/offline-20260918-round63.log` **Ran 2141 tests in 127.570s / OK (skipped=2)**，用例数与 round61/round62 持平（本轮只动 UI 与 JS 断言，无 Python 用例增减）；JS 离线套件 `checks passed` 行数持平（62 行），`node --check src/app/ui/app.js` 通过，`SOURCE_MANIFEST.sha256` 刷新为 691 条，`app.js` 8096 到 8100 行。
- 2026-09-18 — R60 记录纪律清点。发现 `TODO.md` 里 R57 为 R58 立案的那条「R58 优先：修文件夹搜索通道的二次方放大」在 R58 已经关闭之后仍然挂着 `[ ]`，与同文件上方的 `[x]` 关闭条并存，会让「还剩多少没做」的读数虚高，本轮补销（状态改 `[x]`，正文保留并在行尾指向关闭记录）。口径写进 `PROJECT_CONTEXT.md`：关闭一个问题时必须同时销掉所有为它开过的 `[ ]` 条目，而不是只追加一条 `[x]`。
- 2026-09-18 — R59 补记（记录纪律返工，不是新改动）：审计发现 10 个生产文件从未在三份根记录里出现过任何一次，本轮逐个读完并如实登记。**必须先说清楚：以下模块不是本轮写的，本轮只负责读与判定**，所以这里记的是「现在它长什么样、被谁用、有没有被钉住」，不是「我改了什么」。清点方式（可重跑）：`git status --porcelain -uall -- src` 与 `git ls-files -- src` 取并集，排除 `src/tests/`，再用叶子名（去扩展名）在 `CHANGELOG_AI.md + TODO.md + PROJECT_CONTEXT.md` 全文里查提及；命中 10 项、共 381 行（脚本 `%TEMP%/p716.py`）。
- 2026-09-18 — R59 补记：服务端 5 个策略模块。`src/app/server/dlna/xml_policy.py`（28 行）只有 `safe_fromstring`，先拒非文本、拒 >1 MiB、再用字节正则拒 `<!DOCTYPE`/`<!ENTITY`（含 `<!\s+ENTITY` 变体），消费者是 `dlna/control_point.py` 的三处（`soap_text`、`soap_fault`、`scpd_actions`），测试 `test_dlna_xml_policy.py` 钉住「正常 XML 通过 / DTD 与实体拒 / 布尔 maximum 与超大 maximum 拒 / object 拒」。`src/app/server/library_random_sample.py`（24 行）给无过滤随机页生产至多 `MAX_RANDOM_ROWID_CANDIDATES = 400` 个去重行号猜测，对 `maximum`/`size`/`randrange` 三项都做类型与布尔拒绝，`randrange` 抛异常时停下而不是崩，消费者 `library.py:1298`（`random100` 通道的探测循环）。`src/app/server/metadata_job_payload_policy.py`（42 行）把持久化的 worker 任务载荷压成三段白名单（12 个文本字段去 NUL 并夹 4096、6 个数值字段拒布尔与非有限值、2 个布尔字段只认严格布尔），消费者 `metadata_service.py:2804`。`src/app/server/metadata_track_match_policy.py`（84 行）管落库的 provider 匹配：`MAX_TRACK_MATCH_JSON_BYTES = 192 KiB` 的先测长度再 `json.loads`、`decode_track_match_fields`（坏了给空）与 `track_match_fields_are_valid`（区分「合法空终态」与「坏行」）共用同一个 `_decode_track_match_fields`，候选侧 8 条 / 文本 512 / URL 2048 / 标识 128 / `disc_no` 走 `parse_track_number` / `confidence` 经 `finite_candidate_confidence` 拒 `inf`/`nan`，消费者 `metadata_service.py` 的 3192/3244/3288/3431 四处。`src/app/server/playback_session_policy.py`（52 行）归一客户端上报的 `generation`/`engine_epoch`（夹到 `2**31-1`、布尔与脏值归 0、非映射给零身份），`identity_is_stale` 规定「全零的 legacy 身份永不判旧」（两侧各一条守卫），消费者 `server.py:138` 与 `server.py:2573`，另有 `ticket_matches` 供命令票据比对。判定：五个模块的边界与夹紧都在位，没有发现缺陷；它们是「模块边界拆分」这条线上的既有成果，只是没记账。
- 2026-09-18 — R59 补记：UI 4 个策略模块加 1 个第三方包。`src/app/ui/item_negative_cache.js`（63 行）是「查不到的 item id」负缓存：2048 条、5 分钟、键长 ≤512、`now()` 异常回退 `Date.now()`、时间戳倒挂当过期处理，消费者 `app.js:286` 造实例、`app.js:5939` 过滤、`app.js:5978` 记账，测试 `test_ui_item_negative_cache.js` 与 `test_ui_library_loading.js` 各钉一处。`src/app/ui/library_status_refresh_policy.js`（12 行）把「状态轮询进行中再刷新怎么办」压成 `plan(inFlight, refresh)` 两个严格布尔判定（复用 + 仅强制刷新时排队），消费者 `app.js:7410`。`src/app/ui/metadata_row_patch_policy.js`（38 行）判定「元数据补丁能否就地改 DOM」：必须是分页曲目列表、非队列/分组根/文件夹/专辑详情/创作者全轨视图、无搜索词，且改动字段不影响排序或当前排序键不受影响（8 个排序敏感字段白名单），`sameListIdentity` 四元组比对防止补丁打到已翻页的列表上，消费者 `app.js:3021`/`app.js:3102`。`src/app/ui/ui_metrics_policy.js`（37 行）是 `/api/diagnostics` 侧的只读快照：13 个计数与 6 个耗时白名单、计数夹 `1e6`、耗时夹 `3.6e6 ms`、非 number/string 与 >32 字符串一律归 0，**刻意不导出会话起始时间戳**，消费者 `app.js:366`。`src/app/ui/vendor/trim-web-app.js`（1 行压缩产物，37,931 字节）是飞牛官方前端 SDK 的打包结果，唯一入口是 `app.js:6228` 的动态 `import("./vendor/trim-web-app.js")`；判定为不审计内容（第三方产物，改了也会被下次覆盖），但它进 `SOURCE_MANIFEST.sha256`，发布治理上以摘要锁定。四个 UI 模块都在 `index.html` 里以 `?v=__FNAUDIO_ASSET_BUILD__` 版本化加载，符合既有的构建期占位符约定。
- 2026-09-18 — R59 补记同时暴露两处「有名字但没有主人」的代码，本轮只立案不删。其一，`src/app/server/playback_session_contract.py`（139 行，`PlaybackParticipant`/`PlaybackSessionSnapshot`/`KeepAliveLease`/`CommandTicket`）在 `src/`、`tools/`、`android-client/` 全文检索里**没有任何生产消费者**，只有自己的测试引用；它和被广泛使用的 `playback_session_policy.py` 只差一个词，很容易被认为「在生效」。其二，`src/app/server/alsa_player.py`（179 行，带 shebang 与 argparse 的独立 ALSA 输出脚本）在本机可检索范围内同样没有被任何进程启动路径引用（`playback/alsa_output.py` 走的是 `aplay`/`ffmpeg` 子进程），只有它的测试在跑。两条都是「已发布产物里的重量级未知项」：删之前必须先确认设备侧脚本或 fpk 打包没有按文件名调它们，所以按待办处理，别顺手清理。
- 2026-09-18 — R59 顺带量化一条被怀疑的 UI 成本，结论是不改。`item_negative_cache.js` 的 `has()`/`remember()` 每次调用都走一遍 `prune()`（全表扫描 + 溢出裁剪）。用 Node 直接加载该模块实测（`%TEMP%` 内联脚本，模块自身无需改动）：负缓存顶到 2048 条上限时，连查 245,760 次 `has()` 合计 3525.93 毫秒，即**每次查询约 14.4 微秒**；另一次按真实批次形状测（100 个批次、每批 120 个 id，共 12,000 次）合计 238.19 毫秒，即每批约 2.4 毫秒、每次约 19.9 微秒。代价与表大小成正比、与批次大小成线性：只有在「曲库里真有上千条一直解析不出来的 item」时才会持续付这笔钱，而正常批次（≤120 个 id）在满表下也只有约 2.4 毫秒，而它换来的是不再反复请求已知缺失的 id。判定：记数字、不动代码；若将来真机出现每批次毫秒级抖动，再把 `prune` 改成写时执行 + 读时限流（例如每 250 毫秒至多一次），并保留条目上限这条硬不变式。测量脚本形如 `node -e` 加载模块后 `remember` 2048 条再批量 `has`，本机 Node 版本不影响结论量级。
- 2026-09-18 — R59 先记一起自己造成的事故，因为它决定了本轮其余结论的可信度。一个临时校验脚本在断言之前的位置以写模式打开了 `src/app/server/cover_cache.py`，把文件截成 0 字节：960 行、39958 字节、未提交，HEAD 里只有更早的 15685 字节修订（208d550），任何 git 对象都没有这份内容。恢复源是过期字节码 `src/app/server/__pycache__/cover_cache.cpython-314.pyc`（mtime 2026-09-17 12:50:31，头部记录的源码长度正是 39958）。它同时暴露了一条必须写死的流程规则：**临时脚本在断言通过之前不得以写模式打开仓库文件**，落盘一律「临时文件 + `os.replace`」（本轮之后所有脚本都是这么做的，见 p710/p711 自身写法）。
- 2026-09-18 — R59 恢复方法与保真度。存活区间直接从模块 code object 反汇编取回；丢失的中段逐语句对照 `co_code`/`co_names`/`co_varnames`/`co_freevars`/`co_consts`/`co_lines()`/`co_exceptiontable` 重写，然后把重写结果重新编译，与 oracle 在**解析后的绝对跳转偏移**上比对。结果：恢复基线 959 行 / 39827 字节，逐 code object 与原始字节码完全相同（指令序列含跳转目标、行表、异常表、names/varnames/cells/consts 全等），行数仍等于记录里的 960，字节差只来自**无法恢复的注释文字**。全部证据留在 `artifacts/_recover/`：只读 oracle `cover_cache.cpython-314.pyc.bak`、`cover_cache.recovered-baseline.py`、`RECOVERY_RECORD.md`（方法 + 保真度 + 与现行文件的完整 diff）。旧的 `__pycache__` oracle 已删除，避免下一次导入拿它当真相。
- 2026-09-18 — R59 四条只有字节码能钉住的语句，每条都是行为而不是排版。其一，`cached_thumbnail_for_item` 末尾的 `value = (...)` 与 `_memory_put(...)` 在 `except OSError: pass` **之后**而不是里面；挪进去的后果是「成功删掉过期缩略图」那一支不再记忆化刚渲染出的结果（顺带让 956 行从 `LOAD_FAST` 变成 `LOAD_FAST_CHECK`）。其二，`prewarm_library_thumbnails` 的 worker 每页之间的 `state["cancel"].wait(LIBRARY_PREWARM_DELAY_SECONDS)` 在 `with _PREWARM_LOCK:` **外面**（761 行，缩进 16）：把 0.15 秒页间隔压在锁里，等于让批量预热替交互式预热排队。其三，同一 worker 里 generation 变化走 `continue`（760）、registry 条目消失走 `return`（754）；写成 `break` 会把刚换代的队列永久搁置，这一条既有用例 `test_library_prewarm_restarts_processing_after_queue_replacement` 能抓到。其四，两个预热入口的「根数量封顶」判定嵌在「新根」分支内部（`if cache_key not in ... and len(...) >= MAX:` → 退役循环 → 再判一次才 `return`），且 `_INTERACTIVE_PREWARM[cache_key] = state` 位于 `if state["cancel"].is_set():` 之内；把它改平会让一个**已经注册过**的根在注册表满了之后被拒。关键结论：这四处都是被截断那份草稿自己的产物，原始文件从未带过它们，所以没有任何一条以错误形态出厂过。
- 2026-09-18 — R59 为恢复期间确认的行为补 3 项回归并全部做变异验证：`test_interactive_prewarm_keeps_serving_a_registered_root_when_the_registry_is_full`、`test_library_prewarm_keeps_serving_a_registered_root_when_the_registry_is_full`（把第四处改平即失败）、`test_library_prewarm_waits_between_pages_without_holding_the_lock`（在 `wait` 里用 Watchdog 探测 `_PREWARM_LOCK.acquire(blocking=False)`，把等待搬进锁内即失败）。第二、三条里 `unlink`/锁外等待的语义与交互式 worker 自己在 553-558 行的注释一致，恢复后注释与代码不再互相打脸。
- 2026-09-18 — R59 功能：给元数据封面补上尺寸通道，这是 R51 立案、当时判为「缺证据不改」的那条。触发点很直白：`app.js` 的 `coverUrl(item, size)` 对**每一条**封面通道都挂 `?size=`（列表行 160、播放器 512），而 `serve_metadata_artwork` 从不读这个参数，于是没有内嵌封面的行每次整份流 provider 原图（单资产上限 `MAX_ARTWORK_BYTES = 8 MiB`）：一页 120 行就是 120 次全尺寸下载加 120 次大图解码，多出来的字节与解码全部白付，而列表瓦片只要 160 像素。
- 2026-09-18 — R59 实现口径。新增 `cover_cache.generate_asset_thumbnail(config, asset_key, size, source_path, ffmpeg_slot_timeout)`：查 `thumbnail_asset_bytes` → 未命中进 `_key_lock` 二次检查（同一屏十几行可能同时要到同一张专辑图）→ `_read_bounded_file` 读原图 → **先校验 `sha256(body) == asset_key`** → `_thumbnail_bytes` 渲染 → `_atomic_bytes` 落盘（写盘 `OSError` 只记不抛，渲染结果照样服务）→ `_memory_put`。资产键一律过 `_normalized_asset_key`：非字符串、长度 >128、去空白后不是 64 位十六进制，全部在到达任何文件系统调用或任何外部 `__str__` 之前拒掉，因为这个值是直接从 URL 路径里来的。新增 `_asset_memory_key(config, key, size)` 与 `_asset_lock_key`，`thumbnail_asset_bytes` 一并改用，内存键**含尺寸**。
- 2026-09-18 — R59 为什么这两套存储能共用一份缩略图：metadata 的 asset_id 本来就是图片字节的 sha256（`metadata_service.py:3907`），与 `covers/assets/thumb-<size>/<key>.jpg` 是同一套内容寻址，所以 provider 封面与内嵌封面互相复用渲染结果。能共用的前提也就是必须验摘要：一旦落盘字节的摘要与地址不符，任何按内容寻址的读方都会拿错图，所以不符即拒、绝不发布。
- 2026-09-18 — R59 HTTP 出口与 ETag 口径。抽出共用写回 `send_cached_image(mime, body, etag, head_only)`（304 短路 + `public, max-age=2592000, immutable`），`serve_cover_asset` 一并改走它，DLNA 头仍留在 `serve_cover`；派发处改成把 `query` 传给 `serve_metadata_artwork`。只有当 `size` 有效且 `asset["path"]` 是非空字符串时才尝试渲染，`ffmpeg_slot_timeout=1.0`（列表页不能为一张封面等满默认 5 秒的槽位）。命中即返回 `"metadata-<id>-<size>"`；未命中（ffmpeg 缺失、槽位超时、摘要不符、路径异常）**整段回退到原有流式路径**，ETag 保持不带尺寸的 `"metadata-<id>"`。这个不对称是刻意的：冷渲染失败绝不能用带尺寸的标签应答，否则渲染成功之后浏览器还会拿旧标签命中一份错内容。
- 2026-09-18 — R59 验证方式。`test_cover_cache.py` 6 项：渲染一次并被共享（`render.assert_called_once()`）、摘要不符绝不发布、复用别的请求已发布的渲染、写盘失败仍从内存服务、拒绝不可信 id/size/path（含一个 `__str__` 会抛断言的对象，证明不存在任意对象字符串化的旁路）、160 与 512 各自独立（内存与磁盘双向断言）。`test_http_integration.py` 2 项：尺寸请求确实命中共享缩略图存储，内含「不带尺寸的 ETag 不得为尺寸瓦片应答」与带尺寸的 304；以及无渲染时回退流式。变异判定 9 项尝试、8 项有效：M1/M2/M3/M4/M5/M7/M9 当场被杀，**M6（内存键去掉 size）最初存活**，补上尺寸隔离用例后杀掉；M8 经核对不构成变异。
- 2026-09-18 — R59 门限：`artifacts/offline-20260918-round59.log` 2137 项全绿（skipped=2，128.917 秒）→ `round60.log` 2140 项（+3 恢复回归）→ `artifacts/offline-20260918-round61.log` **2141 项全绿（skipped=2，127.141 秒）**，JS 离线套件 `checks passed` 行数持平（62 行），manifest 691 条。补写记录之后再跑一次同样全绿（`round62.log` 2141 项，127.969 秒），证明根文档改动没有破坏 `test_change_record`。`src/app/server/cover_cache.py` 现为 1021 行、`test_cover_cache.py` 现为 57 项（其中本轮新增的是 6 项 `test_asset_thumbnail_*` 与 3 项预热回归，其余 48 项属于 R38 以来尚未提交的既有用例，不要按本轮增量解读）。
- 2026-09-18 — R58 修掉文件夹搜索通道的二次方放大。`query_library_folders` 把搜索条件写成逐目录的关联子查询 `EXISTS (SELECT 1 FROM tracks t WHERE t.root = f.root AND (t.folder = f.path OR t.folder LIKE f.path || '/%') AND <命中>)`，而计划显示这条探测只绑定了 `root`（`SEARCH t USING COVERING INDEX idx_tracks_root_folder (root=?)`）：每判一个目录就把整根曲库的曲目走一遍。搜索页用的是窗口总计（必须先问完所有兄弟才定得出总数），所以付的不是「一页」的钱而是「整个目录」的钱。实测（合成库、FTS5 trigram 已建、命中率 1 的最坏形状）顶层目录 1000/4000/16000 = 136.6 / 2171.3 / 64607.1 ms；搜索词一个都不命中时 4000 目录仍要 4989 ms。现在先把命中曲目折成目录集合，再沿 folders 表的 parent 链向上闭包一次（`WITH RECURSIVE matched_folder_paths`），目录侧只剩一次索引等值探测：同一测量点 5.97 / 20.40 / 87.64 ms，并且随目录数线性增长。
- 2026-09-18 — R58 顺带修掉同一句里的另一个错。`t.folder LIKE f.path || '/%'` 中的 `_` 与 `%` 是 LIKE 通配符，所以叫 `Album_One` 的目录会被 `AlbumXOne/Disc 1` 里的命中「借走」，`Album%Two` 会被 `AlbumQTwo/...` 借走：列出来的目录实际上自己一首都没命中。这条只在有子目录时暴露（模式要求名字后面还有分隔符），新写法完全不做字符串模式匹配，误判随之消失。同仓的 `_rebuild_folders_for_changes` 两处 LIKE 一直带 `ESCAPE` 转义写法，是这次之前唯一做对的地方，本轮全仓复查确认再无第三种写法。
- 2026-09-18 — R58 三条看起来能修但实测无效的写法，记下来免得重走。其一，只把 `LIKE f.path || '/%'` 换成等价范围 `t.folder >= f.path || '/' AND t.folder < f.path || '0'`：计划一字不差仍是 `(root=?)`，耗时不变，SQLite 不会为相关表达式拼出的前缀做 LIKE 范围改写。其二，普通 CTE（连 `AS MATERIALIZED` 提示一起用）加 EXISTS：16000 目录仍是 19.8-21.2 秒，因为非递归 CTE 被相关子查询引用时是 CO-ROUTINE（每个外层行重跑一次），而且对物化结果做**范围**探测不会得到自动索引。真正决定成败的是：递归 CTE（必然物化）+ 每行**等值**探测，后者才换来 `SEARCH m USING AUTOMATIC PARTIAL COVERING INDEX (root=? AND path=?)`。
- 2026-09-18 — R58 实现口径三条。搜索参数现在绑在语句最前面的 CTE 里，所以参数顺序改成 `search_args + 目录过滤`；同一个 `where` 被四条出口共用（不分页快路、count、page/window、游标续页），少带一份 `matched_cte` 前缀就是运行期 `no such table: matched_folder_paths`。搜索页继续用窗口总计：16000 目录实测 window 105.8 ms 对 page 81.0 + count 70.2，一次遍历仍然更便宜，R57 的分道结论不变。向上闭包依赖 folders 表里父目录行存在（`_rebuild_folders` 会为每条曲目路径写入全部前缀），目录表落后于曲目表时缺行那层以上不再计入命中，这与「该子树本来就浏览不到」是同一份陈旧，已开待办。
- 2026-09-18 — R58 验证方式。`query_library_folders` 的用例从 3 项增到 8 项：三层父链逐级可见、两个根不互借命中、LIKE 回退模式下七个占位符一次绑对、游标与搜索同时出现、目录名里的通配符不再误判，以及一条语句与计划双重断言（搜索页 SQL 必须以 `WITH RECURSIVE matched_folder_paths` 起始，计划里不得再出现 `idx_tracks_root_folder`）。变异判定 10 项尝试、8 项捕获，2 项存活且可证等价：删掉基础项的 `DISTINCT`（`UNION` 本身去重）、删掉 `COALESCE(f2.parent, '') <> ''` 守卫（多产生的 `path=''` 行永远匹配不上目录行，因为 folders.path 从不为空，守卫只用来给递归封顶）。「游标出口漏前缀」是补测才杀掉的：第一版多根夹具里第一个根没有曲目也就没有目录行，删掉 `m.root = f.root` 无人报错，补齐 quiet 曲目后才暴露。变异全部在临时副本上做，仓库源码未被改动（脚本末尾比对确认）。
- 2026-09-18 — R58 门限：`artifacts/offline-20260918-round58.log` 2130 项全绿（skipped=2，128.591 秒），JS 离线套件 `checks passed` 行数持平（62 行），manifest 691 条。用例增量：净 +6（2124 到 2130）。
- 2026-09-18 — R57 首屏文件夹浏览不再排序整个目录。`src/app/server/library.py` 的 `query_library_folders` 在无过滤目录页上仍用 `COUNT(*) OVER()` 窗口总计，而 folders 表只有 `(root, parent)` 与 `(root, parent, name)`（二元排序）两条索引，对不上 `name COLLATE NOCASE <dir>, path` 的浏览顺序：`EXPLAIN QUERY PLAN` 每种形状都带 `USE TEMP B-TREE FOR ORDER BY`，120 行的一页要先把该目录下所有兄弟排一遍。现在补一对按方向的表达式索引 `idx_folders_root_parent_name_nocase_asc/_desc`，并让无过滤页改走 `counted_page_rows`（与 R44 给分组页的同一先例）。端到端实测（合成库、顶层目录数即兄弟数、池化读路径、每调用失效缓存取 9 次中位）：5000/20000/50000 个顶层目录 4.18/22.48/71.10 ms 变为 0.87/1.28/5.91 ms；嵌套形状（12500 顶层 + 50000 行）12.13 变为 1.21 ms；深层目录本来就只要 0.2-0.4 ms，未受影响。
- 2026-09-18 — R57 更正两条被误记的归因。其一，旧 TODO 说分组页的 `SELECT COUNT(*)` 占了 4.75 ms 里的 4.33 ms：实测覆盖 5 万行的 `SELECT COUNT(*) FROM albums` 是 0.01 ms，那笔开销属于**未池化连接的前奏**（`connect + SELECT 1` 1.7-2.5 ms），R39 的池化收益（5.054 对 0.985 ms，5.13 倍）在当前代码上复测仍然成立。其二，`test_library_sqlite.py` 里那条「folder 页窗口总计比 page+count 便宜（80/800/5000 子项 1.68/1.92/1.84 ms 对 3.5-3.9 ms）」的旧结论，是**在没有对得上排序的索引时**测的：有索引后窗口无论怎样都要走完整个目录（20k 顶层目录实测 17.3-22.7 ms，索引并不改变它），而 page 侧 0.09 ms、count 走覆盖索引 0.56 ms。该测试已按新形状重写，两条数字一起留在注释里，避免下次再按旧结论反向回退。
- 2026-09-18 — R57 索引取舍按实测决定，不按直觉删索引。`idx_folders_root_parent_name`（`(root, parent, name)` 二元排序）在全仓任何 folder 查询顺序里都没被选中过，随本轮删除；`idx_folders_root_parent` 保留，因为它是 `SELECT COUNT(*) FROM folders WHERE root=? AND parent=?` 的覆盖索引，删掉后同一句从 0.56 ms 涨到 3.03 ms（实测四种索引组合后的唯一退化项）。写放大可接受：`_rebuild_folders` 在 2 个索引 0.18 s、4 个索引 0.22 s、删掉二元那条后的 3 个索引 0.20 s（20k 行）。顺带把 `ensure_library_schema` 里清理孤儿索引的判定从等值匹配单个索引名改成 `name LIKE 'idx_folders%'`，否则新增的两条表达式索引在旧库迁移中断时会留下同类孤儿。
- 2026-09-18 — R57 立案一条更大的问题（本轮只测量、未改代码）：文件夹视图带搜索时 `query_library_folders` 是二次方放大。搜索条件是逐目录的关联子查询 `EXISTS (SELECT 1 FROM tracks t WHERE t.root = f.root AND (t.folder = f.path OR t.folder LIKE f.path || '/%') AND <命中条件>)`，而计划详情显示 `SEARCH t USING INDEX idx_tracks_root_folder (root=?)`，也就是每判一个目录就把整根曲库的曲目走一遍。合成库（FTS5 trigram 已建）实测顶层目录 1000/4000/16000 = 137 ms / 2171 ms / 64607 ms，4 倍目录对应 16-30 倍耗时；UI 的搜索框在文件夹视图里会同时发出这条请求，属于可稳定复现的首屏挂起。修法方向与取证要求写进 TODO。
- 2026-09-18 — R57 验证方式。新增/重写三项测试：`test_unfiltered_folder_page_reads_an_indexed_page_plus_count`（用 `set_trace_callback` 钉住两条语句的形状、页大小与 `EXPLAIN` 用上表达式索引且无 `TEMP B-TREE`）、`test_searched_folder_page_keeps_its_single_scoped_window_query`（搜索通道保留窗口，防止一并改掉）、`test_folder_table_carries_case_insensitive_ordering_indexes`（重跑 schema 过程即旧库升级路径：新索引出现、被取代的二元索引消失、`(root, parent)` 覆盖计数索引保留、两个方向都无临时排序）。`tools/benchmark_large_library.py` 增加 `browse.folder_pages` 计划硬断言，基准脚本现在会自己拒绝没有排序索引的 schema。变异判定在临时副本上做（仓库源码未被改动，脚本末尾比对目录确认）：把无过滤页改回窗口、把搜索页一并改成 page+count、删掉成对表达式索引、只删 asc 一条、保留被取代的二元索引、删掉 `(root, parent)` 共 6 项，全部被杀；其中只删 asc 时基准脚本抛 `folder browse page lost its ordering index: asc`。
- 2026-09-18 — R57 门限：`artifacts/offline-20260918-round57.log` 2124 项全绿（skipped=2，127.655 秒），JS 离线套件 `checks passed` 行数持平（62 行），manifest 691 条。用例增量：净 +2（`test_library_sqlite.py` 1 项拆为 3 项，另在 `test_large_library_benchmark.py` 增加 folder 计划断言）。
- 2026-09-18 — R56 停止把猜测值当成实测能力。`src/app/server/playback/alsa_output.py` 的 `empty_dac_caps()` 原来返回 `pcm_max_rate: 192000` / `pcm_max_bits: 24`，而 `enrich_dac_device()` 又在解析不到采样率时补一条 `pcm_rates = [192000]`：一处默认值就这样变成「这块 DAC 支持 192 kHz/24 bit」的事实。它有两个对外出口：本机渲染器的 UPnP `GetProtocolInfo` 会据此广告 `audio/L16;rate=192000;channels=2` 与 L24（`dlna/service.py:885-904`），设备列表的能力行会显示 `PCM 192kHz/24bit`；`choose_dac_strategy()` 还会因为这条被发明的 192 kHz 记录，把 44.1 kHz 的源文件判成「需转码到 192 kHz」。现在未测得一律是 0，`enrich_dac_device()` 不再编造速率列表，UI 侧按既有约定显示「未知采样率/未知位深」。播放判定不受影响并被测试钉住：`choose_dac_strategy()` 自己的 `or 192000` / `or 24` 回退仍在原位，384 kHz 源仍按保守上限降到 192 kHz。
- 2026-09-18 — R56 删掉 `merge_dac_caps()`（23 行死代码，全仓无调用方）。它不只是没人用：它把 `empty_dac_caps()` 的猜测默认值与实测能力做 `max()`，一旦接线就会用猜测抬高真实上限，正是本轮修掉的那个模式。同时确认 `empty_dac_caps()` 只剩三处消费者（`parse_dac_stream_caps` 的基底、`choose_dac_strategy` 的缺省 device、`_safe_capabilities` 之前的设备行）。
- 2026-09-18 — R56 量化关闭一条 R55 尾巴：`provider_candidate_cache` 不需要字节账。它的值确实只按条目封顶（`PROVIDER_CANDIDATE_CACHE_MAX_ENTRIES = 128`），但每个值至多 `MAX_DISPLAY_CANDIDATES = 8` 条候选，且每条候选的每个字段都在 provider 边界上被夹过（文本 4096 字符、URL 2048、标识 32）。递归 `sys.getsizeof` 实测：典型候选 1550 字节、整缓存 0.6 MiB；把每个字段都顶满的对抗形状是单条 19851 字节（ASCII）/36303 字节（CJK），整缓存最坏 2.8 MiB/4.8 MiB。键侧同样有界（`metadata_candidate_cache_key` 六段各 256 字符）。结论写进上下文，避免下次照抄歌词那套常量。
- 2026-09-18 — R56 验证方式：两条修复前行为在临时副本上还原后均被新测试杀掉（`AssertionError: 192000 != 0`、`Lists differ: [192000] != []`），仓库源码未被改动（脚本末尾比对哈希确认）。新增的 DLNA 用例是端到端的：只 mock `FNAUDIO_ASOUND_ROOT`，从合成的 `card0/stream0` 文本一路走到 `protocol_info("renderer")` 的广告串，再顺带断言同一份 caps 不会把 44.1 kHz 判成需转码；另在 `test_ui_device_caps_presentation.js` 钉住未测得形状渲染成「未知采样率/未知位深」。既有的「测得 44100/96000/192000 就广告 L24@192000」用例保持不变，证明这不是把功能删掉。
- 2026-09-18 — R56 门限：`artifacts/offline-20260918-round56.log` 2122 项全绿（skipped=2，126.278 秒），JS 离线套件通过行数持平（65 行），manifest 691 条。用例增量：`test_alsa_output.py` +2、`test_dlna_protocol.py` +1（净增 3 项，2119→2122）。
- 2026-09-18 — R55 歌词缓存补上真正的资源上限：按保留字节记账。`src/app/server/metadata_local_lyrics_cache.py` 的 `LocalLyricsCache` 此前只数条目（默认 256、可配 4096），而每条值是一整份歌词正文、磁盘侧单份上限 2 MiB：纸面最坏驻留 512 MiB，limit 配到 4096 就是 8 GiB。现在每条按 `sys.getsizeof` 记**进程内内存**（不是 UTF-8 长度，也不是字符数：PEP 393 下每字符 1/2/4 字节，2 MiB 字节的正文实测驻留 1.40-2.00 MiB），新增 `DEFAULT_MAX_BYTES = 8 MiB`（可用区间 64 KiB-64 MiB，非整数/布尔/越界一律回默认），插入后「条数或字节谁先超就驱逐最老」，并且**一份大于整个预算的文档只服务、不留存**。正常曲库行为不变：6 KiB 正文 256 条合计 1.47 MiB，仍然由条目上限说话，被改变的只有最坏情况。
- 2026-09-18 — R55 顺带排掉一个共用常量的坑。`combined_snapshot` 原先把所有字段一律夹到 `MAX_COUNTER = 1000000`，新字段若沿用同一个上界，8 MiB 的字节账会被报成 1 MB。改为逐字段上界表 `SNAPSHOT_CEILINGS`（计数 1e6、字节 1 GiB），并把 `bytes`/`bytes_limit` 一并转发进 `/api/health` 的 `components.metadata.local_lyrics_cache` 与 `diagnostics_metadata.metadata_summary`。这正是 R53 那条教训的复现条件（白名单漏转发会恒空而测试全绿），所以新用例直接拿真生产者比键集合，而不是各写一份字面量。
- 2026-09-18 — R55 记录没做与故意不做。字节预算**尚未接配置**：`config.py` 加一键要同时动默认表、区间表、归一化三处并补校验测试，而现在没有任何真机 RSS 证据说明默认值该是多少，所以只保留 `max_bytes` 构造参数并开待办。两个 lane 缓存各自记账，聚合快照里的 `bytes_limit` 是两者之和（与既有 `limit` 同口径，实测 16 MiB）。`snapshot()` 的 `bytes` 刻意不做上限夹取，账目一旦漂移要在报告里看得见。
- 2026-09-18 — R55 变异判定 18 项尝试、16 项捕获，两项存活且可证等价：驱逐循环的空表守卫（超预算文档在插入前就被拒绝，永不触发）与 `snapshot` 里 `max(0, ...)` 的下界侧（同一不变式）。两条真实变异是补测才杀掉的：`while` 改 `if` 在逐条插入时**等价**（每次至多超一条），必须「先塞 30 条小正文再塞 1 条大正文」才区分得开；「超预算文档」守卫的意义不在「最终有没有留住它」（预算驱逐同样会把它弹掉），而在它不得清空其他歌曲已缓存的正文。变异全部在临时副本上做，仓库源码未被改动（脚本末尾比对哈希确认）。
- 2026-09-18 — R55 门限：`artifacts/offline-20260918-round55.log` 2119 项全绿（skipped=2，127.787 秒），JS 离线套件通过行数与上一轮持平（65 行），manifest 691 条。用例增量：`test_metadata_local_lyrics_cache.py` 7→16、`test_health_snapshot.py` 11→12；`test_metadata_service.py`（205 项）与 `test_diagnostics_metadata.py` 在原用例内加断言，数量不变。
- 2026-09-18 — R54 首屏页不再为用不上的歌词买单。`src/app/server/metadata_service.py` 的 `enrich_track_page` 一直无条件 `SELECT tracks.lyrics`，把整列歌词装进 overlay 并深拷贝两次放进**只按条数封顶**的进程级 LRU，而 `include_lyrics` 只控制「最后挂不挂到行上」；全仓没有任何生产调用传过 True（只有测试传）。实测（120 行/页、每条 21 KiB 歌词）：旧形状每次翻页 9.72 ms、峰值分配 2651 KiB，现在 5.01 ms、115 KiB，且开销不再随歌词大小增长；6 KiB 一档是 6.64→5.42 ms、879→115 KiB。修法三件：列按需选取、overlay 按需写入、**缓存键加入该形状标记**（否则详版会命中简版缓存而静默丢正文），并且 `include_lyrics` 只认严格 True，真值型乱传一律留在简版形状上。
- 2026-09-18 — R54 统一歌词正文的预算单位。`src/app/server/metadata_provider_response.py` 新增 `lyrics_document()`：整份接受或整份拒绝，按 UTF-8 字节度量。此前同一列上挂着两套**字符**口径的切片：写入侧 `_provider_text(value, MAX_PROVIDER_LYRICS_BYTES)`（2 Mi 个字符，CJK 正文等于 6 MiB 字节）与读取侧的 200000 个字符，两处都不是它们名字所说的字节预算，也都违反 2026-09-17 定下的「文档字段不得按长度切片」。现在 `_store_lyrics` 的写入与旧值保留分支、封面补写、pending/repaired 两处投影、`/api/lyrics` 缓存快路、页叠加缓存共六个出口共用同一守卫。
- 2026-09-18 — R54 一处有意的数据形状取舍（写成记录，避免被当成漏改）：库里已有的超限旧歌词正文只可能由修复前的写入口径留下，现在每个读者都拒绝它，因此一次不含歌词的写会把它清成空串而不是继续保留死重（数据库体积与标签回写都受益）。若真机出现「歌词面板变空但旁车 .lrc 仍在」的反馈，再改成保留正文 + 显式不可用标记。
- 2026-09-18 — R54 变异判定 17 项尝试、15 项捕获，两项存活且都可证明等价：字符数早退（UTF-8 字节数永不低于字符数，删掉结果不变，它只挡住「先量长度再整份拷贝」的 OOM 路径）与默认上限写错（`_safe_limit` 把任何调用方传入的 limit 夹回模块预算，同一条事实已由「调用方不得抬高预算」的断言钉住）。另有一条「四倍最坏情况」快路径因为永远无法被行为测试判定，直接删除而不是留成不可判定面。
- 2026-09-18 — R54 工具教训（本轮真出过事）：为基准测试临时改源码、末尾还原的脚本，中途抛异常会把变异体留在工作树里；本轮 `bench` 在 `service.close()`（该方法不存在）上崩掉，确实把两处变异留在了 `metadata_service.py`，当场按记录复原并重跑 205 项确认。此后测量一律走运行时开关复现旧形状（`include_lyrics=True` 就是修复前的读取形状），绝不为基准改文件；变异脚本的还原必须在 `finally` 里。
- 2026-09-18 — R54 门限：`artifacts/offline-20260918-round54.log` 2109 项全绿（skipped=2，125.404 秒），src/tests 下 66 个 test_*.js 全部通过，`test_change_record` 通过，manifest 691 条。新增 11 项用例：`test_metadata_provider_response.py` 8→15、`test_metadata_service.py` 201→205（含真实 SQL 追踪断言与缓存条目数断言）。
- 2026-09-18 — R53 修 `/api/health` 播放错误类别恒空。`src/app/server/health_snapshot.py` 把 `playback_errors` 先过一道 `("count", "last_error")` 白名单，再交给只读 `items` 的 `health_error_category`：`count` 这里没人用，`last_error` 是任何生产者都不发的键（`classify_mpd_log_errors` 出的是 `last_category`/`last_domain`/`last_message`）。于是 MPD 正在刷解码失败日志时，`components.mpd.error_category` 仍然是空串，健康接口看不到任何降级信号。用记录型字典做经验探测（让投影函数自己吐出被读的键，绕开正则误判）确认：`health_snapshot` 里同形白名单只有这一处失真，`transcode_summary` 读的四个键与它的白名单完全重合。
- 2026-09-18 — R53 把健康投影改成真正的外部输入边界。`src/app/server/playback/mpd_errors.py` 新增 `_error_items`：summary 必须是真 `dict`、`items` 必须是真 `list`、每条记录先 `dict(item)` 复制再读，任何一条不满足就当「没有错误」。这条路径此前从没被真实喂过数据（见上条），修复后它才开始消费别的线程写出的对象。`legacy_decoder_error_summary` 共用同一读取器，顺带不再对 `None`/字符串 summary 抛 `AttributeError`。
- 2026-09-18 — R53 一条反向结论（记下来防止被当成覆盖率）：先写的 `try: records.append(dict(item))` 是死代码。删掉这个 try 的变异跑完 41 项测试全绿，因为 CPython 对 dict 子类走内部快路径，`dict(subclass)` 不会调用被覆写的 `keys()`，异常根本抛不出来。据此删掉 try、保留 `isinstance(item, dict)`，并补上真正能钉住它的用例：记录里混非 dict、混「键值对列表」（少了守卫就会被 `dict()` 洗成一条合法的伪造 severe 记录）。
- 2026-09-18 — R53 记录 `isinstance(summary, dict)` 是信任边界而不是崩溃守卫：删掉它之后 `None`/字符串仍被 `try/except` 兜住，测试不会红；只有「鸭子类型的 summary 不得被调用访问器」这条断言（`DuckSummary.calls == []`）才能让它成为承重结构。同理 `severity` 的 `str(...).lower()` 与 `category` 的 `str(...)` 各补了一条外部形状断言（`"ERROR"` 也算 severe、`category: 42` 出 `"42"`、缺 `category` 出空串）。
- 2026-09-18 — R53 门限：`artifacts/offline-20260918-round53.log` 全绿（`Ran 2098 tests`，skipped=2），src/tests 下 66 个 test_*.js 全部通过，`test_change_record` 通过，manifest 691 条。本轮新增 6 个用例（`test_mpd_status.py` 27→30、`test_health_snapshot.py` 8→11），变异判定 17/17 捕获（W06/W07/W08 三条在改写为推导式后锚点消失，由同形状的 W06n/W07n/W15n 取代，无存活项）。
- 2026-09-18 — R52 门限：`artifacts/offline-20260918-round52.log` 跑满 2092 项全绿（skipped=2，120.420 秒），src/tests 下 66 个 test_*.js 全部通过，manifest 691 条。相比 R51 的 2082 项，本轮新增 10 个 Python 用例（`test_id3_parser.py` 10→16、`test_media_formats.py` 29→31、`test_metadata_service.py` 199→201），加载器 JS 套件 222→400 行（8 组新行为断言）。变异判定：Python 侧 24/24 捕获，加载器侧 21/21 捕获。
- 2026-09-18 — R52 修掉 ID3 标签级标志被完全忽略这一类静默失真。`src/app/server/id3_parser.py` 此前只看 `header[3]` 版本号，从不读 `header[5]` 标志字节，于是：带 unsynchronisation 标签位的真实标签里，所有 `FF` 后跟 `>=E0`/`00` 的字节都被写入方插了 `00`，旧解析器把 `00` 当正文读，标题歌手整体错位、帧长还可能越界；带 extended header 标签位的标签则把扩展头当成第一帧，真首帧的正文整段丢失（封面排在最前时封面直接读不到）。新增 `id3_tag_is_readable` 与 `id3_frame_region`：`major==2` 一律拒读（2.2 帧头只有三字节且没有帧标志，硬猜会读到别处），其余版本按各自编码跳过扩展头（v2.3 长度不含自身 4 字节、总下界 8；v2.4 是 synchsafe 且含自身、总下界 6），越界即整份不可读而不是「尽量解」，反插 `00` 只在标志位为真时做。`parse_id3_tags`/`parse_id3_cover`/`iter_id3_frames` 统一走这条区域函数，`id3_container.read_id3` 在标签不可读时回落 ID3v1、`read_id3_cover` 回落 `(None, None)`。
- 2026-09-18 — R52 修掉 DSF/WAV 标签写回的封面无限复制。`_write_dsf_tags`/`_write_wav_tags` 把新封面追加进 ID3，却没在「已被本次写入接管」的旧帧集合里点名 `APIC`，于是每确认一次元数据就多存一份图片：实测 2 KB 封面三次连写 2123 → 4188 → 6218 → 8248 字节，按 16 MiB 标签预算，一台反复确认元数据的曲库最终会把单曲标签撑到写不进去。修法是一条口径而不是一个补丁：**写回方追加的任何帧都必须先被自己的 replaced 集合认领**。新增 `_resolved_id3_cover`（定最终封面）与 `_managed_id3_frames`（返回帧与被关闭的 id），`_preserved_id3_frames` 用同一份集合过滤，并把它自己手写的那套帧遍历换成 `iter_id3_frames(payload, major, flags)`，读写两侧从此共用同一个解析器。修后体积稳定在 2158 且 `APIC` 恰好一张。
- 2026-09-18 — R52 两处同域小修：`parse_id3_cover` 遇到缺 MIME 终止符的 APIC 帧由 `return None, None` 改为 `continue`（与它自己的 docstring 一致，一张坏帧不该让后面可用的封面一起作废）；`id3_frame_size` 改用新的 `_synchsafe` 而不是就地再写一遍移位。
- 2026-09-18 — R52 首屏加载两处口径。其一，`src/app/ui/library_response_loader.js` 的 `safeInflightLimit` 现在把空串与纯空白回落默认预算：`Number("")` 与 `Number("   ")` 都是 0，而零预算会拒绝**每一页**加载，空白只可能是「未设置」，这与 `visible_metadata_prefetch_policy.boundedLimit` 是同一条规则（今天 `app.js` 传字面量 32 属潜伏，但这条不变量此前只在其中一个文件成立）。其二，同一 URL 上「已被中止的在飞请求」被替换时，把并发槽位移交给替换者；此前槽位只能等旧 fetch 自己 settle，若某个 WebView 的传输忽略 `signal`，切页在 32 槽打满时会直接被拒，首屏再也进不来。
- 2026-09-18 — R52 用变异把加载器测试的 8 个空洞补成行为断言：NaN/无穷/布尔预算不回落默认会让 `activeCount() >= NaN` 恒假即**并发无上界**（比零预算更危险）、`refresh` 可以读到热缓存、settle 时对已手工释放的请求二次减槽、`active.value` 被写坏成负数后取槽与放槽不自我修复、外部 `abort` 监听器在 settle 后不摘（每次切页叠一层）、缺 `cache`/`inflight`/`fetchJson` 时抛同步异常而不是 reject。补完后 21/21 变异全捕获。`tests/test_ui_library_loading.js` 里把旧决策钉死在源码层的 `doesNotMatch(existing.__fnAudioRelease?.())` 断言相应翻面为 `match`，理由随之改写。
- 2026-09-18 — R52 变异矩阵里两处「不计入」而非「未捕获」，记录以免被误读成存活：U12 的原锚点在 `_preserved_id3_frames` 内，本轮把那段手写遍历换成解析器调用后锚点消失，同一条守卫由 U11 证明是承重结构；U24 想变异的冗余门禁在评审中被删掉（两处判断合并进 `iter_id3_frames`），已删除的代码无变异可测。
- 2026-09-17 — R51 门禁：`artifacts/offline-20260917-round51.log` 2082 项全绿（skipped=2），64 个 JS 套件通过，`test_change_record` 通过，manifest 691 条。新增 9 项测试（`test_dlna_network.py` 32 到 41 项）。
- 2026-09-17 — 同一条待办里的另一处顺序疑点，这次**成立**：`src/app/server/metadata_unavailable_policy.py` 的三处 `item.get("lyrics")` 在生产调用点永远读到空。`server.py:967/991/1002/1019/1027/1055` 传进来的都是 `find_library_item` → `query_library_item_by_id` → `decode_item_row`，即扫描器写进 `tracks.item_json` 的那份字典，而扫描链路（`library.py` 全文没有 lyrics 一词）从不写这个字段；带歌词的行只出现在 `metadata_service.enrich_track_page` 之后的页副本上（`metadata_service.py:4284-4285`），那份又被 `library_presentation.py:105` 主动 pop 掉。于是 `local_lyrics_projection` 的 docstring 承诺（「在元数据服务尚未启动时返回内嵌歌词」）从未发生过，`server.py:972` 的 `or local_projection.get("lyrics")` 也是恒假分支，单元测试则是自己造了带 lyrics 的字典才覆盖到这几行。本轮只把口径写进源码注释与待办，不改行为：真要在冷启动窗口显示本地歌词，得走 `metadata_service` 那套有界本地读取器（`LocalLyricsCache`），而不是在请求线程上碰媒体文件（`read_local_lyrics` 会跑 ffprobe，超时上限 15 秒）。
- 2026-09-17 — R51 改的是 DLNA 出网的两处连接与一条读预算。`src/app/server/dlna/network.py` 里 `_PinnedHTTPSConnection.connect()` 过去在 `_tunnel_host` 非空时先 `_tunnel()`、再把 `server_hostname=self.host` 交给 TLS：一旦真走代理（只有 `Request.set_proxy` 会置这个字段），`self.host` 已经变成代理地址，SNI 与证书校验对象跟着变成代理，而 socket 又被钉到我们自己解析出的 LAN IP，两头同时错。现在两个 pinned 连接类都在建 socket 之前 fail closed（`DLNA pinned connection cannot be proxied`）：钉住已校验地址就是这个类存在的全部理由，做不到就不该拨号。同时删掉 `_PinnedHTTPConnection.connect()` 里 `if self._http_vsn == 11: self._http_vsn_str = "HTTP/1.1"`，对照本机 CPython 3.14 的类属性（`_http_vsn = 11`、`_http_vsn_str = 'HTTP/1.1'`，且 `putrequest` 从不回写），这句永远只写入同一个值，任何断言都观察不到，属于不可覆盖的死分支。
- 2026-09-17 — `_read_response_limited` 与 pinned HTTPS 连接此前零测试。新增 `DlnaResponseBudgetTests` 6 项、`DlnaPinnedConnectionTests` 3 项：预算的三侧边界（累计**恰好等于**上限必须收、按 1 字节滴水的 maximum+1 必须拒且总读入不超过 maximum+1、空体合法、`bytearray` 分片照样累加、文本分片按超限拒而不是抛 `TypeError`、`fetch_lan` 无 Content-Length 时的滴水超限路径）；TLS 侧钉住「只钉地址不钉身份」（`create_connection` 收到 `("198.51.100.20", 8443)`，`wrap_socket` 收到 `server_hostname="speaker.local"`）、无 pin 时回落主机名、代理隧道被拒且 `create_connection` 一次都不许调用。15 处可执行变异全部命中；M06（`if not chunk: break` 改成只在 `None` 退出）表现为整组超时而非断言失败，这条 EOF 判定是防死循环的，按超时记账；另有一处等价变异（把 `_http_vsn` 那句还原）不可能被任何断言命中，已按删死代码处理并在此说明。
- 2026-09-17 — 否证一条昨日挂下的首屏疑点。待办里写的是「`library_presentation` 用 `metadata_artwork_id` 兜 `cover_url`，而该字段在投影之后才挂上，所以无内嵌封面行的列表响应拿不到 provider 封面」。真实顺序不是这样：`src/app/server/server.py:873-877`（以及 883-887、923-935）依次是 `query_library_page` → `prewarm_thumbnails` → `enrich_track_page` → `public_library_page`，兜底发生在投影之前。端到端复现（一条无内嵌封面、只带标签的行加一份已落盘的 provider 封面）打出的公开行就是 `cover_url = metadata/artwork/<64hex>`。判定为负结果，不要再搬这段兜底。
- 2026-09-17 — 同一份复现顺带暴露一个真实的首屏代价，已挂待办：metadata 封面没有缩略图通道。公开行的 `cover_thumbnail_url` 为空，`/metadata/artwork/<id>` 根本不读 `size` 参数（按存储的原始字节流式返回，单资产上限 8 MiB），而 `src/app/ui/app.js` 的 `coverUrl()` 照例给 URL 挂上 `?size=160` 或 `?size=512`，于是列表行与播放器拿到的是同一份原图，多出来的字节和解码都白付。
- 2026-09-17 — R50 查的是可见行元数据通道的那道预算。`src/app/ui/visible_metadata_prefetch_policy.js` 的 `selectCandidates()` 把「够了没有」判在 `push` **之后**，所以预算为 0 时仍会返回一条候选；同一个文件里的 `boundedLimit()` 又接受字符串，而空串与两个空格经 `Number` 转换都等于 0，于是桥层递来一个空字段不是「未设置」而是「把这条通道整体关掉」或「只留一条」。这段判定被三处共用（可见行宽度、`shouldRetry` 的尝试上限、`shouldRearmPending` 的重挂上限），三处都会被同一个伪装影响。今天的生产调用点传的是字面量 6、12、2（`src/app/ui/app.js:5341` 与 5284），所以这是**潜在缺陷而不是现网故障**，按潜在缺陷记账并修：任何把宽度挪到配置或桥接层的改动都会立刻踩到。
- 2026-09-17 — 修法两行。预算改成**取行之前先花**（`if (result.length >= bounded) break;` 移到循环开头），这样被跳过的行（空对象、id 不可读、重复 id、当前播放行）不再白吃预算，0 就是 0 条；`boundedLimit()` 加一条：字符串去空白后为空即视为未设置，回落到调用方默认，数字字符串仍然照常生效。两侧边界都测：默认 6、传 30 时钳到 `MAX_LIMIT` 12、传 -5 钳到 0、传 "2" 取 2 条、传一个 `valueOf` 抛错的对象时回落到 6。
- 2026-09-17 — 回归与方法教训。`src/tests/test_ui_visible_metadata_prefetch_policy.js` 新增 15 条断言。六处变异全部命中，但这一轮里三条（把 `>=` 改成 `>`、删掉空白串判定、把它改成只判长度为 0）第一次跑是**被源码正则杀掉**的，行为断言根本没轮到；于是把那几条 `assert.match(source, ...)` 临时摘掉重跑，确认 `>` 变异由既有第 20 行的行为断言（1 条预算拿到 2 条）与新增断言共同命中、空白串两条由新增的行为断言命中，之后再原样还原（两份文件都做了字节相同校验）。以后给 JS 策略补约束按这个顺序判定：**先摘源码正则，再谈变异是否被行为覆盖**。另记一条夹具口径：`vm.runInNewContext` 里构造的数组带着另一个 realm 的原型，`node:assert/strict` 的 `deepEqual` 会按原型判不等（本轮就踩了一次 `[] != []`），这类返回值只能用 `.length` 与 `.map(...).join(` 逗号 `)` 断言。
- 2026-09-17 — 同时给热页那笔防御性拷贝**结掉两个悬案**，用测量而不是印象。从真实的 4000 轨库里抓一份 120 行的曲库页载荷（36,786 字节，每行 10 个字段且含一个嵌套 dict）：`copy.deepcopy` 0.300ms，手写递归克隆（字典/列表/元组递归、标量共享、结构不合就退回 deepcopy）0.317ms，**不降反升**，因为两者都是每值约 200ns 的 Python 层派发；只有 `json.loads` 走 C 层能到 0.151ms（1.99 倍）。但 JSON 往返会把元组变成列表、整数键变成字符串、dict 子类变成普通 dict，要保证类型不变就得在 `put()` 里 dumps + loads + 等值校验（合计约 0.4ms），写路径变慢、读路径每页只省 0.15ms。判定：**不为这个量级引入类型保真风险，维持 deepcopy**，结论与数字一起记进待办，免得下一轮重新论证一遍。
- 2026-09-17 — R49 把扫描器里一处**由最常见输入触发的二次方**换成了线性：`src/app/server/cue_parser.py` 计算每轨结尾用的是「从本轨往后一轨一轨找」的嵌套循环。触发它的不是精心构造的对抗谱，而是两种普通形状：其一，**一行一个 FILE 的分轨谱**（后面永远找不到同文件的轨，于是每一轨都要走到表尾）；其二，**没有任何可用 INDEX 的谱**（所有 start 相等，严格更大的条件永不成立，同样每轨走到底）。实测这台机器（`MAX_CUE_LINES = 20000` 大约能容到 5000 轨）：分轨谱 5000 轨 3069ms、无 INDEX 谱 3103ms，而对照的单调递增正常谱只要 31.7ms。这段代码在扫描线程上，所以一张坏 CUE 就能把一整轮曲库索引拖住三秒，直接推迟扫描完成后的首屏。
- 2026-09-17 — 修法是 `_attach_track_ends()`：**每个文件值各持一条单调栈**，从右往左一趟走完。语义与旧嵌套逐字对齐（同一文件、更靠后、start 严格更大的**最近**一轨；弹栈条件是 `<= start` 所以相等值被弹掉，等价于旧代码的 `>` 而不是 `>=`；找不到仍然是 0.0）。改后同一批夹具 5000 轨：分轨谱 20.44ms、无 INDEX 谱 14.07ms（150 倍与 220 倍），并且增长回到线性。栈按文件分组是必需的，不是优化口味：`stacks.setdefault(常量, ...)` 这种把所有轨并进一条栈的写法会在对拍里立刻露馅。
- 2026-09-17 — 顺手修掉一条同文件里的**真功能缺陷**：原来的关键字判断写死成字面量前缀 `INDEX 01`，把合法写法一律判死。制表符分隔的 `INDEX`、`01`、`00:04:00`，一位数的 `INDEX 1 00:04:00`，以及关键字后接两个空格的写法，过去**全部被忽略**，`cue_start` 就停在 0.0：该轨时长塌成整张镜像（`cue_item_presentation` 算的是 `max(0, end - start)`），播放起点也从 `playback_cue_position` 的绝对位置退回 0，用户听到的是「每张 CUE 的第一轨都能播、后面的歌从头开始」。现在换成 `^INDEX[ \t]+(\d{1,2})[ \t]+(\S+)` 的判定，且只接受 INDEX 01：INDEX 00 是 pregap、更大的是 cue point，都不许移动起点。取时间也从不安全的 `parts[-1]`（行尾多一个 token 就会把非时间字段当时间）改成正则的第二组。
- 2026-09-17 — 回归与变异。`src/tests/test_cue_parser.py` 由 6 项到 11 项，其中三条是本轮的关键约束：把**旧嵌套定义原样搬进测试当参照实现**，用固定种子的 60 轮随机谱（多文件、名字重复、start 乱序与相等、缺 INDEX、重复 INDEX）逐项对拍结尾；用计数包装 `cue_parser.finite_number` 断言「每轨至多两次归一化」，从而把「线性」变成可判定的断言而不是计时（计时阈值在这类对比上必然不稳，判定口径见待办）；另三条钉住分隔符、一位数与 INDEX 种类。11 处变异全部命中，其中把 `== 1` 改成 `>= 1` 只有靠夹具里那条 INDEX 02 才杀得掉（只写 INDEX 00 时后面的 INDEX 01 会把它覆盖掉，判定就存活了）。本轮不改 `library.py` 的 `cue_end = safe_float(track[` 那层退回整轨时长的既有口径。
- 2026-09-17 — R48 查出一条**跨两个容器的注入**：封面响应的 `Content-Type` 一直是标签里的自由文本。ID3 的 APIC 帧与 FLAC 的 PICTURE 块都带一个 MIME 字段，谁打过标签谁就写什么；`cover_readers.read_flac_cover()` 与 `id3_parser.parse_id3_cover()` 把它**原样返回**，`server.py` 的三个出口再原样写进响应头。本轮在本机复现了三份夹具：声明 `text/html`、声明 `image/svg+xml`、以及声明 `image/png` 加 CRLF 加 `Set-Cookie: a=b`，三者都从读取器活着回到 sink，而这台 Python 3.14 的 `BaseHTTPRequestHandler.send_header` 接受含 CRLF 的值并产出**真实的响应拆分**（多出一行 `Set-Cookie`）。最坏的一条是 `serve_upnp_cover`，它把 `serve_cover` 整套复用且**不需要任何会话**，所以局域网里任何设备无需登录就能让浏览器在源站打开一个类型由被扫描文件决定的文档。`metadata_service._id3_apic_frame()` 还会把这个字符串写回用户的 `.dsf`/`.wav`，provider 下载的 `Content-Type` 则被存进 `metadata_assets.mime` 后长期重放。
- 2026-09-17 — 修法是**新设一个唯一判定**：`src/app/server/cover_media_type.py`。`sniff_image_media_type(body)` 只认魔数（jpeg/png/gif/bmp/webp/avif/heic/tiff，最长签名落在第 12 字节，读取窗口 `SNIFF_PREFIX_BYTES = 32`）；`normalize_media_type(value)` 做文本消毒：小写、剥参数、64 字符上限、**任何落在 `[a-z0-9.+-/]` 之外的字符（含 CR、LF、空格、引号、NUL）整体作废**、必须 `image/` 前缀，另带一张真实存在的别名表（`image/jpg`、`image/pjpeg`、`image/x-png`、`image/x-bitmap`、`image/x-ms-bmp`、`image/x-icon`），免得把今天能看的封面判死；`safe_image_media_type(declared, body)` 定优先级：**字节赢**，字节读不出格式时才接受白名单内的声明，白名单之外一律返回空串。白名单**故意没有 `image/svg+xml`**：把 artwork 地址当文档打开时，SVG 里的脚本就在源站执行。另加一条前缀规则：字节以 `<`、`{`、`[` 开头时即使声明了 `image/jpeg` 也拒绝，否则「内嵌 HTML 谎报成 JPEG」正好是宽松回退最容易被绕开的组合。
- 2026-09-17 — 两侧读取器与三个出口全部接到这一个判定上。`parse_id3_cover()` 遇到描述不了的 APIC 不再直接返回，而是**继续找下一张图**；`read_flac_cover()` 同理继续走下一个元数据块（末块标志 `0x86` 仍然遵守）。出口侧按手里有什么分两种：`serve_cover()` 与 `serve_cover_asset()` 持有完整 body，就用 body 重判，判不出来直接 404，并且这段判定**放在 ETag/304 分支之前**，于是一个被拒绝的封面不可能再靠 If-None-Match 答出 304；`serve_metadata_artwork()` 是流式的，改为先从句柄读 `SNIFF_PREFIX_BYTES` 字节再判，并保证这段前缀仍然**原样发出恰好一次**（`Content-Length` 与真正写出的字节数继续一致，前缀既不少一份也不重一份）。写侧同步收紧：`_id3_apic_frame()` 只落判定后的类型（判不出来退回历史默认 `image/jpeg`），`_download_artwork()` 存库前用像素重判并拒掉白名单外的类型，取代原来那截只认 jpeg/png/webp 三个魔数的 if 链。
- 2026-09-17 — 把行为变化说清楚，不含糊：声明不可消毒或不是光栅的封面，现在**不再出现在响应里**（首屏退到侧车封面或占位图，`/cover` 与无鉴权的 `/upnp-cover` 都给 404）；provider 返回白名单外的 `image/*`（历史上包括 `image/svg+xml`）现在**不入库**；反之，谎报类型但像素是真的封面**照旧能看**，因为字节优先。`image/png` 声明配 JPEG 像素会被纠正成 `image/jpeg`，这类「声明错但图是对的」在真实曲库里非常常见，所以这条方向不能反。
- 2026-09-17 — 回归与变异。新增 `src/tests/test_cover_media_type.py` 14 项（逐格式魔数、12 字节可达下界、截断夹具、非字节输入；消毒真值表含 CRLF、`; charset=`、非字符串、恰好 64 与 65 字符两侧、`IMAGE/JPEG ` 归一；优先级规则）；`test_id3_parser.py` 加 4 项（谎报类型、注入串、坏帧退到下一帧、SVG 谎报成 JPEG）；`test_media_formats.py` 加 3 项（含双 PICTURE 块继续扫描的夹具）；`test_http_integration.py` 新增 `ArtworkMediaTypeTests` 8 项，用既有 `object.__new__(server.Handler)` 桩函数直接跑三个 sink，断言 `Content-Type` 永不是标签文本、拒答时不发 304、且流式路由只读 `SNIFF_PREFIX_BYTES` 字节、字节总数不变；`test_metadata_service.py` 加 3 项覆盖两个写入口。共 16 处变异，**15 处命中**；唯一存活的是把 sniffer 内部切片换成整份 body，经论证这是**等价变异**：所有魔数检查只落在前 12 字节，切片的唯一作用是内存上界而非结果，因此不补假测试，改由上面两条可观察断言（12 字节下界、路由读取窗口）把常量钉住，结论记进待办。
- 2026-09-17 — R47 把 R46 记下的那条首屏缺陷补上了：**读不出来的响应体过去会被当成「这一页是空的」**。链路是这样的：`src/app/ui/app.js` 的 `fetchJsonChecked` 用 `fallback: {}` 调用读取器，于是 HTTP 200 但 body 超限、被截断、或者根本不是 JSON（反向代理、登录门户、半截响应都算）回到调用方就是一份 `{}`；`response.ok` 为真，所以它不报错；再往外 `library_response_loader` 会按 URL 把这份 `{}` 写进曲库响应缓存，`loadPagedLibrary` 把它当权威页面上屏。冷启动那一屏没有快照可保（`library_empty_response_policy.shouldRetainSnapshot` 要求 `snapshotHit === true` 才保留旧行），用户看到的是「曲库为空」，而且这个空还会被缓存到下一次刷新为止。
- 2026-09-17 — 修法是让读取器**说清楚它是哪一种「没有」**。`parseBoundedJson` 现在通过一个 out 参数报告结局（与既有的 `setCancel` 同一风格），`read()` 多回一个 `bodyStatus`，取值只有四种可观察的：`parsed`（解出了一份 JSON）、`empty`（body 一个字节都没有，即 204 或宿主自己短路掉的无内容响应）、`oversize`（Content-Length 声明超限、或流式分块累计超限、或缓冲后超限）、`undecodable`（不是字节视图、不是合法 JSON、`json()` 自己抛了）。默认值故意是 `undecodable`：**任何忘记分类的分支不可能伪装成成功**，这一条有专门的变异与测试（把默认改成 `parsed`，那条「最后退路解析失败」的断言立刻红）。模块同时导出 `usableBody(status)`，可用集合就是 `parsed` 与 `empty` 两个字面量，真值表两侧都钉住。
- 2026-09-17 — `fetchJsonChecked` 新增第四个参数 `options`，只有 `strictBody: true` 的调用方会在 `response.ok` 却拿到不可用 body 时抛 `ResponseError`（错误文案复用调用方自己的 `fallbackMessage`，后缀「（响应体不完整）」）。`fetchLibraryResponse` 是唯一的严格调用方，因为它是唯一会被按 URL 缓存并直接上屏的那条路；其余状态类读取（`api/access`、`api/library/status`、诊断等）行为一字不变，仍然把 `{}` 当兜底。严格判定写成 `strictBody && usableBody(...) === false`，`usableBody` 万一不存在（旧缓存页没加载到新模块）就是 `undefined === false` 为假，自动退回旧行为，不会把整屏打成错误。
- 2026-09-17 — 空 body 必须继续是良性的，这一点单独实测过：流式分支现在在 `total === 0` 时直接报 `empty`（不再试图 `JSON.parse('')`），arrayBuffer 分支在 `byteLength === 0` 时同理，只有 `text()` 的宿主也要有 `text.length === 0` 这一支。三条都各有一条断言。也就是说「服务端确实没给内容」仍然渲染成空集合，只有「内容坏了/被截断/被劫持」才第一次变成一条看得见的失败，并且**不会**被写进缓存：`loadLibraryResponse` 的 `fetchJson` 一旦拒绝，那条 URL 就不会有 `cache.set`，屏幕上保留的是上一批行而不是空列表。
- 2026-09-17 — 回归与变异。`src/tests/test_ui_response_json_loader.js` 再加 19 处断言调用（可用集合真值表是两组循环，实际执行 11 次；覆盖四条结局路径 × 流式/arrayBuffer/text/最后退路四宿主、Content-Length 预检报同一种结局、迟到的无字节 body 走 `empty`、`usableBody` 真值表含 `undefined`/`null`/`0`/`{}` 这些不该可用的值）；`src/tests/test_ui_library_loading.js` 里那条锁定 `fetchJsonChecked` 形状的源码级断言同步更新签名，并新增三项：严格门必须写成 `strictBody && usableBody(...) === false` 且成功分支仍然 `return data`、曲库列表必须传 `{ strictBody: true }`、`api/access` 这类非列表读取必须**没有**加上严格门。十三处变异全部命中（其中「text 空 body 那支删掉」第一版存活，补一条 `text: async () => ""` 的断言后才命中，教训还是老一条：新增判定要立刻问一句「删掉它有没有测试会红」）。本轮不改服务端 SQL，也不新增 UI 脚本文件（`test_ui_android_bridge.js` 要求 index.html 里每个 `<script>` 都被 Android 打包内联，新增模块就得动安卓侧，判定口径记进待办）。
- 2026-09-17 — R46 动的是首屏响应读取的那一小段 `src/app/ui/response_json_loader.js`，先修一处**静默空列表**的形状依赖。流式分支原来用 `value instanceof Uint8Array` 判断分块是不是字节视图：这个判定读的是原型链，所以只要分块来自另一个 realm（fetch 垫片、桥接层、或任何把视图交给本 realm 之外构造器的宿主），它就一律为假，于是整页响应被换成 `fallback`，也就是**屏幕上什么都没有而没有任何错误**。现在改成 `ArrayBuffer.isView(value)`，它读的是内部槽，跨 realm 仍然成立，顺带把宿主直接递来 DataView 的情况也收进合法输入。这条不是从真机日志推出来的，Chromium WebView 的分块和本页同 realm，所以今天的设备行为不变；它修的是本仓库自己已经在用的这种沙箱形状：测试用 `vm` 起上下文时把宿主的 `Uint8Array` 注入进去，`instanceof` 才恰好成立，注入一旦去掉读取就整页作废。本轮用**不注入** `Uint8Array` 的上下文把这个失效复现成一条回归（同一份夹具先用 `chunk => chunk instanceof Uint8Array` 断言它确实是外来 realm 的视图，再断言读取成功），并补上反向两项：DataView 分块必须读成功，宿主递来已解码好的字符串分块必须落到 `fallback` 而不是抛出去（`TextDecoder.decode` 对普通字符串会 TypeError，抛出会被调用方看成传输错误，而这条路本来是要给空态的）。
- 2026-09-17 — 第二条是省掉一次可以证明不必要的整份复制。非流式宿主里 `arrayBuffer()` 不可用、只有 `text()` 时，字节预算原来靠 `new TextEncoder().encode(text).byteLength` 精确测量，也就是为了知道长度而把整份文档再编码一遍（上限就是预算本身）。UTF-8 里一个码元最少一字节、最多三字节（代理对是 4 字节 2 码元，仍在三成以内），所以 `text.length * 3 <= maximum` 的字符串**不可能**越界，直接放行；`text.length > maximum` 的字符串**不可能**合规，直接拒绝。现在只有落在这两个界之间的字符串才会真的去编码测量。实测（Node 24，同一份沙箱里把 TextEncoder 换成计数版本，7 次中位数）：纯 ASCII 载荷 204,812 字节 0.26ms 到 **0.13ms**，1,048,588 字节 0.85ms 到 **0.41ms**；4 MiB 那一档两版都是 0.04ms，因为它本来就被码元下界提前拒掉了，这正好说明早退是有效的一道。字节数节省没法用 `heapUsed` 量出来：`TextEncoder.encode` 的结果挂在 ArrayBuffer 的外部内存上，不计进堆，所以这里给的是时间与「每次最多 `maximum` 字节的临时分配」这个可证明的上界，不给假的堆数字。
- 2026-09-17 — 两条**先写后撤/不改**的结论。其一，我一开始顺手给流式分支加了 `catch`：把「取消之后 read() 才拒绝」的宿主吸收成 `fallback`，理由是怕留下 unhandled rejection。变异验证直接把它杀死了（把整段 catch 删掉，测试全绿），因为 `Promise.race` 会给**每一个**输入 promise 挂反应，竞争已经落败之后那条拒绝本来就没有听众，也不会成为 unhandled。留着这段代码就是拿一个编造的风险换一处不可观察的分支，所以撤掉，改为在测试里把这个真实行为钉住（迟到的拒绝既不该冒出来也不该改变结果），并注明「将来若真需要这道守卫，得同时有一条说明它的测试」。其二，`json()` 那条最后退路仍然**不受字节预算约束**（只在既没有 body 流、又没有 arrayBuffer/text 的宿主上到达），本轮判定不改：让它「除非 Content-Length 证明合规否则失败」看着更安全，但 gzip 响应常常根本不带 Content-Length，那样做等于把一条能用的链路改成必然空白页，而这条路在本项目所有真实宿主上都是死路。已挂进待办，等设备侧真的出现这种宿主再处理。
- 2026-09-17 — 读这条链路时顺带记下一条新的缺陷候选（还没修，风险要先想清楚）：`src/app/ui/app.js` 约 690 行的 `fetchJsonChecked` 用 `fallback: {}` 调这个读取器，于是「HTTP 200 但响应体超限或不是合法 JSON」（反向代理、门户劫持、半截响应都会这样）在调用方看来与「服务端说这一页是空的」完全一样；再往外一层，`library_response_loader` 会把这份 `{}` 按 URL 写进响应缓存，冷启动那一屏没有快照可保，就可能出现一次「曲库为空」并且被缓存到下一次刷新。现有守卫只覆盖了一半：`library_empty_response_policy.shouldRetainSnapshot` 要求 `snapshotHit === true` 才保留旧列表，并且 `loadPagedLibrary` 只在保留时才删掉那条缓存键。真正的修法要让读取器能把「读不出body」与「body 就是空集合」分开交给调用方，同时**不能**把 204/空响应这类良性情况变成报错，所以要连带动 `fetchJsonChecked` 与那几处 UI 测试的期望，单独一轮做。另外同一段里 `safeInflightLimit` 把 ``、``、`[]` 这类值经 `Number()` 变成 0，而 0 意味着并发上限为 0、**每个请求都被拒**；目前调用点传的是字面量 32 所以打不到，也一并记进待办。
- 2026-09-17 — 回归与门禁。`src/tests/test_ui_response_json_loader.js` 的断言从 21 处到 40 处（本轮新增 19 项）：跨 realm 视图（含夹具自证）、DataView 分块、非视图分块走 `fallback`、取消后迟到的拒绝不改变结局、仍在等待时的真实传输错误必须原样抛给调用方（这一条是「所有失败都吞成空页」那种改动的唯一杀手）、编码测量带两侧边界（正好等于三倍预算必须免测量、少一字节必须测一次）、宽字符载荷在精确预算两侧各一次、以及码元下界早退（超过 4 MiB 的字符串必须一次都不测）。九处变异全部命中。首屏服务端的 SQL 侧本轮没有再动；R45 那条组/目录浏览游标（两条单比较谓词替换 OR，100k 专辑深页 13.91ms 到 4.75ms）已经独立跑绿并记录在同日期顶部。
- 2026-09-17 — 本轮（R45）把组/目录浏览游标从**一条 OR 谓词**换成**两条单比较谓词**，这是 R44 补完组表排序索引之后唯一还挂着的浏览热点。`library_browse_cursor_policy.browse_cursor_where()` 整个删除，换成 `browse_cursor_page()`（唯一的游标采纳判定）、`browse_cursor_group_tail_where()`（游标所在键组的尾巴，`%s = ? AND %s > ?`，并列键**任何方向都升序**所以它不吃 sort_dir）与 `browse_cursor_next_group_where()`（其后的键组，`>` 或 `<` 随方向翻转），`library._browse_cursor_rows()` 依次执行两条并共用一个 limit+1 预算。三个调用点（按艺术家/作曲家归组的专辑页、普通组页、folders）一起切到新形状，folders 用 ` AND ` 拼接以保留它已有的 root/parent 过滤。线上格式没动（载荷仍是 `v: 1`），客户端不需要更新。
- 2026-09-17 — 端到端实测（100k 曲目、**100k 个不同专辑**、页 120、每格中位数 5 次、逐行比对三种形状完全一致）：旧 OR 升序在深度 0/12000/50000/99000 是 4.59/6.14/9.70/13.91ms，新形状是 4.33/5.00/4.88/4.75ms；降序旧 4.37/5.88/10.68/16.33ms，新 4.64/4.66/4.58/6.12ms。也就是说游标页的耗时从此**不随深度增长**，越深省得越多（升序最深 2.9 倍、降序 2.7 倍）。同一批数据里旧 OR 的计划是 `SCAN albums USING INDEX idx_albums_name_nocase_asc`（它只借索引取序，仍要逐行判断），新形状是 `SEARCH ... (name>?)` 与 `SEARCH ... (name=? AND name>?)`，游标那条实测 0.06ms/0.01ms。
- 2026-09-17 — 为什么不能留成一条语句，也测了：行值写法 `(name COLLATE NOCASE, name) > (?, ?)` 语义上正好等于这两条的并集，但在同一份 100k 专辑库上它的计划还是 `SCAN albums USING INDEX`、2.28ms，而旧 OR 是 2.71ms、两条 SEARCH 是 0.07ms。SQLite 这个构建不会用行值比较去 seek 表达式索引，所以「少一次往返」在这里买不回来。附带结论：曲目 lane 的行值只出现在 `expr = ?` 已经把范围收到一个键组之后，那里它seek不seek都无关紧要，两边不要混为一条规则。
- 2026-09-17 — 代价与边界要写清楚。其一，游标落在自己键组的最后一行时（绝大多数情况），第一条必然空跑一次，所以每页固定多一条语句：在 albums 只有 2000 组的常规形态下实测旧 OR 2.15-2.63ms、新形状 2.05-2.60ms、OFFSET 2.08-2.45ms，八组差异都落在噪声里，本轮判定**小基数不受影响**；benchmark 里 asc 那组 1.221 的游标/OFFSET 比值就是这份噪声，不作为回归依据，因此测试只断言两条语句的形状、行数与总数，不断言游标必须快过 OFFSET。其二，这一支的总数仍是那条 `SELECT COUNT(*) FROM <组表>`，100k 组下约占 4.3ms，是修后每页 4.7ms 的绝对大头，仍挂在待办里。
- 2026-09-17 — 回归与变异。`test_library_browse_cursor_policy` 3 到 7 项（两条谓词的形状与参数、并列键方向无关、目录用 path 收尾、**任何一条都不许含 OR**、采纳判定拒收错类型/错方向的游标、缺省并列键回落到组名）。`test_library_sqlite` 97 到 101 项：新增组页与目录页各一条「续读必须是两条单比较 SELECT 且都带 LIMIT 页大小+1」的语句级断言（`set_trace_callback` 抓真实 SQL），一条用桩连接直接测 `_browse_cursor_rows` 的预算共享（尾巴满页就不再发第二条、尾巴吃掉 k 行时第二条只许要 limit+1-k），以及一条跨 `GRP/Grp/grp` 键组簇的整趟游标遍历，逐字断言八个组名各出现一次且顺序正确（页边界正好落在簇内，尾巴谓词写错就会缺组或重组）。benchmark 新增 `browse.group_cursor_pages`（升降两向、中位数 3 次、语句数不等于 2 或出现 OR 直接 RuntimeError），门禁 2028 到 2033 项。十一处变异全部命中：预算丢看门行、两条顺序颠倒、共享预算不传递给第二条（这一处第一版锚点在两个同形函数上都出现两次，改成带上下文的唯一锚点后才命中）、参数顺序错乱、目录丢掉既有过滤、尾巴含等号、尾巴把游标自身算进去、尾巴参数写反、第二条不随方向翻转、第二条用 `>=`/`<=`、采纳判定形同虚设。
- 2026-09-17 — 补上这轮新索引自己的资源账，因为它是**永久**成本而收益只在浏览页。100k 曲目、100k 张专辑加 1k 个流派这一组最坏基数下，四条索引（albums 两条、genres 两条）实测让索引文件从 191,119,360 字节涨到 197,984,256 字节，多 6,864,896 字节，约为这份曲库索引的 3.6%；建索引耗时 0.098s。按同样的行宽推算，四张组表都在 100k 基数时八条索引约 27 MB，占一份 100k 曲目索引的一成上下；而真实曲库里艺术家/作曲家/流派通常远没有专辑多，成本主要落在 albums 那两条上。写入侧的代价也可以量化：增量刷新每次只删改受影响的那几个组名，多维护两条索引是每行两次 B 树插入，实测在 2k/20k/100k 组的整表重建里，八条索引的总构建时间是 0.009s/0.031s/0.106s。换句话说，本轮用一次不到 0.11s 的建索引和最多一成磁盘换掉了每页 50 到 117ms 的重复排序。
- 2026-09-17 — 记两条**查过但不改**的结论，免得下一轮重复劳动。第一条：曲库列表行的封面状态推导链路里有一支永远命中不到的死分支。`metadata_unavailable_policy` 的封面分支要求 `item_json` 里带 cover_url、cover_thumbnail_url、artwork_id 或 metadata_artwork_id 之一，而 `item_json` 只由扫描写入路径生成（`library_write.prepare_track_persistence` 把扫描到的原始条目整份 `dumps` 进去），服务端没有任何一处会把这几个字段写进那份 JSON：展示层的 `library_presentation` 是在**响应投影**上现场补 cover_url/artwork_id，元数据侧的 `metadata_service` 也是先复制条目再设 `metadata_artwork_id`。所以 `local_pending_projection`、`local_cached_projection`、`local_lyrics_projection` 三支在真实行上都不会带 image_url，`metadata_track_enrichment_policy.has_local_artwork` 对真实行恒为假，三处 `needs_enrichment or (not has_local_artwork and not cached_artwork_id)` 的判定实际退化成「有没有缓存封面」。用户侧影响很小，因为列表行本来就有按文件路径推导的封面；真要修就得让 `metadata_tracks` 把作品图 id 顺着 item_json 带回持久层，那是写链路的一整轮，不能靠给投影塞假字段来「让它看起来能用」。
- 2026-09-17 — 第二条：首屏前端链路整段读过之后没有发现缺陷，把判定写清楚。`librarySnapshotKey` 与 restore/persist/scheduleLibraryPageSnapshot 一段（约 351 到 485 行）在读写两侧都用 `key === cacheKey` 复核，损坏或部分解析的快照走既有的安全回退；`renderTrack` 与 `renderTrackRows`（2921 到 2977）只生成 `<li>` 外层，行内结构由 `renderTrackRowContent` 决定；`commitTrackListHtml` 的按键复用（3155 到 3262）要求**键非空且不重复**才启用 keyed diff，重复 id 的响应会整体退回 innerHTML 路径，不会错位复用；`reuseSnapshotTrackMarkup` 加 `fetchLibraryResponse` 的合并段（5101 到 5230）只在快照页面集合与当前视图完全一致时启用，并且 `library_metadata_merge_policy.js` 返回的是新对象，不存在与缓存共享引用的别名问题；骨架屏那道 `hasVisibleLibraryPresentation()`（约 5790）正是「已经有可见行就不让骨架接管」的防空帧闪烁守卫，与上一轮封面预热竞态的修复互为前提；`loadPagedLibraryWorker` 里在 await 之后回到同一根元素重新解析状态是有意设计，controller/seq/epoch 三重守卫都在，不属于陈旧别名缺陷。这些都是浅层通读得到的结论，`src/app/ui/app.js` 共 8083 行、381 个符号，其中 31 个已被本轮之前的深读覆盖，剩余部分是本轮之后最大的单文件面。
- 2026-09-17 — 组浏览分页过去**每一页都要把整张组表排序一遍**，这是首屏之外最明显的曲库查询热点。albums/artists/composers/genres 四张组表只有 name 这一列 TEXT PRIMARY KEY，它给的是二进制序，而浏览页的排序键是 name COLLATE NOCASE 加 name 兜底，于是 SQLite 只能先做临时 B 树；更糟的是无条件浏览那一条走的是 COUNT(*) OVER() 窗口形状，窗口函数拿不到 LIMIT 的短路，必须先把全部组算完才能吐出第一行。100k 曲目、100k 张专辑、页大小 120 的实测：升序整趟 53.32ms、降序 97.23ms，深一页（offset 6000）53.72ms/117.31ms；同一形状在 20k 专辑下是 11.54ms/19.08ms，20k 艺术家是 10.14ms/16.01ms。也就是说这个开销完全随组数线性增长，且降序永远是升序的两倍。
- 2026-09-17 — 修法是两步且顺序不能反。第一步补排序索引：四张组表各两条，(name COLLATE NOCASE ASC, name ASC) 与 (name COLLATE NOCASE DESC, name ASC)，共 8 条，跟曲目 lane 的 idx_tracks_*_nocase_id_asc/desc 同一口径（方向混合的排序键只能靠显式反向索引，SQLite 反向扫一条 ASC 索引会把兜底键也倒过来）。建索引实测耗时 2k/20k/100k 组分别是 0.009s/0.031s/0.106s，一次建好常驻。第二步才换形状：无过滤那一支不再用窗口，改成「有序索引页 + 单独 COUNT」。只补索引不动形状是没有用的，同一批实测里窗口页加了索引仍然是 46.4ms/89.0ms，因为它压根不打算短路。
- 2026-09-17 — 整趟改动后的端到端实测（100k 曲目、页 120、每组中位数 5 次、逐行比对前后一致）：100k 专辑升序 53.32ms 到 **5.02ms**、降序 97.23ms 到 **4.98ms**，深页 53.72/117.31 到 5.00/5.45；20k 艺术家升/降 10.14/16.01 到 2.84/2.78；20k 专辑升/降 11.54/19.08 到 2.79/2.88。EXPLAIN QUERY PLAN 现在全是 SCAN <表> USING INDEX idx_<表>_name_nocase_asc 或 _desc，没有 USE TEMP B-TREE，计数那条走 COVERING INDEX sqlite_autoindex_<表>_1。16 组前后对照里 count、行数、首行组名全部相同，只有小基数（250 个艺术家）那一组从 2.11ms 变成 2.42ms：多一条语句就多一次往返，组数少时窗口本来就便宜，这是本轮有意接受的代价。
- 2026-09-17 — 只改无过滤那一支是有意的，另外两支保留窗口。搜索过滤的组页与按艺术家/作曲家归组的专辑页，它们的总数来自同一个 CTE（DISTINCT 匹配到的组名），拆成两条就得把那个 CTE 跑两遍，窗口反而是省的那一边。目录浏览也实测过不拆：按 (root, parent) 收窄之后一个窗口的子项本来就有限，800 和 5000 个子目录的实测窗口页是 1.894ms/1.844ms，而「页面 + 单独 COUNT」是 3.9ms/3.5ms，一条语句更便宜；folders 那条 name 列的二进制排序与查询里的 COLLATE NOCASE 不匹配因此还留着临时 B 树，但在几百行的目录宽度上它量不出来，本轮不动，已单独记进待办以免下轮重复测。
- 2026-09-17 — 两条语句的形状收进 library_pagination.counted_page_rows()，错误隔离语义与既有的 paged_rows_with_total 完全对齐：页游标仍然只物化到 MAX_PAGE_ROWS，页面失败给空页、计数失败给 0，且只捕数据库类异常。为「只捕数据库类异常」专门补了一项测试：让页查询抛 ZeroDivisionError，必须原样冒出去，因为把 Exception 全吞掉等于给一个空页掩盖调用方 bug；这一项是唯一能杀掉 except Exception 变异的断言。library.py 里那对 if/else 两个分支字符串完全相同的 window_select 死代码也一并收敛成一条赋值。
- 2026-09-17 — 回归与变异验证。test_library_pagination 11 到 14 项（新增三条：先页面后计数的语句顺序、页/计数各自失败时的隔离、 runaway 游标必须被截到上限且源码有限以避免挂死）；test_library_sqlite 里把原先那条「普通组页与目录页都用一次窗口」的测试按新事实拆成三项（无过滤组页用索引页 + 单独 COUNT、目录页仍用一次窗口、搜索过滤组页仍用一次带 CTE 的窗口），另加一组八元组的排序索引断言（表里有索引 + 计划里用了它 + 没有 TEMP B-TREE）；旧 SQLite 无窗口函数的回退测试改挂到仍使用窗口的那一支上，免得测一条根本不含窗口的 SQL。benchmark 新增 browse.group_pages 八组硬断言（四表两向都必须是索引、都不许出现 TEMP B-TREE，否则直接 RuntimeError）。十五处变异全部命中；其中一处第一版把锚点落在窗口那条调用上，等于没改到目标行而显示存活，修正锚点后立刻命中，这处教训是变异脚本必须先断言锚点计数再谈结果。本轮门禁 2021 项到 2028 项。
- 2026-09-17 — 修掉歌词 base64 链路上的一条**静默损坏**，它比原以为的「先解码才限长」更严重。`kugou_lyrics` 与 `joox_lyrics` 在把字段交给解码器之前，先用了给标签类字段准备的截断投影 `_provider_text(value, MAX_PROVIDER_LYRICS_BYTES)`，也就是按**字符数**切到 2 MiB。截断本身不会让后续检查报错：切片仍是合法 base64，还能顺利解出一份「更短的歌词」，而被切开的地方正好把一个多字节字符劈成两半，UTF-8 那一路失败后落到 GB18030，GB18030 把残缺字节补成合法汉字、不产生替换符。探针实测一份 5,240,000 字节的歌词文档：切成 2,097,152 字符后解出 852,470 字符，尾部是「鍦板湴鍦板湴…」这样的乱码，`lyrics()` 里那道「含 U+FFFD 就判为损坏」的守卫因此放行，`_store_lyrics` 会把它当成正经歌词写库并标记为已完成，客户端从此不会再为这首歌重新取词。现在两个调用点都不再切片，超额文档一律交给 `decode_base64_lyrics` 整份拒绝。
- 2026-09-17 — 同一条改动把预算检查挪到解码之前，并给出分配量证据。旧实现先 `base64.b64decode(value, validate=True)` 再检查长度，于是要先分配它打算拒绝的那份副本：一个 4,194,320 字符的字段（约 3 MiB 解码结果，超出 2 MiB 文档预算）实测峰值分配 **7,340,126 字节**、耗时 4.595ms 才抛错；新实现按编码长度判定，同一输入实测 **601 字节**、0.011ms。为此导出模块常量 `MAX_PROVIDER_LYRICS_BASE64_CHARS = (MAX_PROVIDER_LYRICS_BYTES + 2) // 3 * 4`，即三字节变四字符的膨胀比，它是唯一正确的编码长度天花板：拿字节预算当字符天花板会误杀（2 MiB 文档编码后是 2,796,204 字符），反过来把字符数当字节数又会放行。三个歌词通道（kugou、joox、qq）现在共用这一处判定。
- 2026-09-17 — 顺手修掉同函数里的一处自相矛盾，它会白白丢掉能取的歌词。旧代码用 `value.strip()` 判「这个字段算不算空」，却把**没去掉空白**的 `value` 交给 `b64decode(validate=True)`；而 `validate=True` 在 CPython 里对首尾空白同样报错（3.14 实测 `'aGVsbG8=' + chr(10)` 直接抛 `Only base64 data is allowed`）。`qq_lyrics` 走的正是不过投影的裸字段，所以提供方只要在 JSON 里给 `lyric` 末尾多带一个换行，这首歌的歌词就整条判为非法、被计入 provider 失败。现在判定与解码共用同一份 strip 后的文本，实测旧实现 `— raise lyrics base64 payload is invalid`、新实现正常返回歌词。内部换行仍然拒绝：那需要一次整串拷贝，且没有任何真机证据说明有通道会输出折行 base64，已单独记进待办。
- 2026-09-17 — 补回归并做变异验证。`src/tests/test_metadata_provider_response.py` 8 项：用替身证明超额字段**从未进入** `b64decode`、整预算文档必须原样往返（这条同时钉住膨胀比的上下两侧）、首尾空白可解、非字符串与 hostile `limit` 对象依旧只走类型守卫。`src/tests/test_metadata_service.py` 新增 3 项：kugou 必须把**完整**字段交给解码器（断言捕获到的长度大于字符天花板，直接封死重新引入切片）、kugou 对超额文档返回 None、joox 在超额候选上继续下一个候选而不是让整条通道抛出去。十五处变异全部命中：把预算检查移回解码之后、上界改成含等号、上界用字节预算、上界用下取整、上界翻倍、超额改成静默返回空串、解码未 strip 的值、strip 守卫被去掉、`limit` 不经归一、非字符串改为抛错、kugou 重新切片、joox 重新切片、joox 只捕 TypeError，各命中 1 到 3 项。这里有两次教训值得写下：第一版边界测试只测了「比天花板多一个」，于是`>=` 与 `>`、`limit` 与真天花板、下取整与上取整**三个变异全都存活**（多一个字符在任何比真值小的上界面前同样被拒），补上「整份预算必须能往返」这一侧才真正钉住；另一处是第一版探针只改了 `artist` 列没同步 `item_json`，与上一轮同错，已作废重做。
- 2026-09-17 — 记一条查过但不改的结论，免得下一轮重复劳动。`_store_lyrics` 里那句 `_provider_text(result.get("lyrics"), MAX_PROVIDER_LYRICS_BYTES)` 看着像同一个截断缺陷，其实不可能咬人：任何 UTF-8 解码出来的字符串，字符数必然小于等于字节数，而上游三条通道已经把解码字节压在 2 MiB 内，所以这道字符切片在正常路径上是纯防御。真要收紧应该改成语义明确的「按字节再核一次」，那是存储层的独立一轮。本轮门禁 2015 项到 2021 项。
- 2026-09-17 — 落地上一轮排进去的那项待办：游标续读不再多扫一遍键组前缀。旧形状（R38）是 `cursor_where()` 给一个单范围谓词、`cursor_tie_where()` 再 COUNT 出游标在本键组内已经访问过多少行、把这个数字当作页面 OFFSET 传下去，于是同一批行要扫两遍（一遍计数、一遍跳过），而范围谓词能不能裁掉前序行完全取决于排序方向和键组大小。新形状是两条语句：`cursor_group_tail_where()` 读游标所在键组剩下的尾巴（`expr = ? AND (title COLLATE NOCASE, id) > (?, ?)`），`cursor_next_group_where()` 读它之后的键组（`expr > ?` 或 `expr < ?`），两条共用一个 `limit + 1` 预算，因此既不需要 OFFSET 也不需要 COUNT。`cursor_where()` 与 `cursor_tie_where()` 随之删除，`library._cursor_tie_skip` 换成模块级的 `_cursor_page_rows()`（放模块级是为了让测试能用替身拦住真实 SQL）。新增的 `cursor_page()` 是唯一的游标采纳判定：只有载荷里的 `sort`/`dir` 与本次分页请求完全一致才认，否则两条谓词一起返回空、行为退化成无游标。载荷版本仍是 `v: 1`，线格式没动，客户端不需要更新。
- 2026-09-17 — 给出这轮改动的实测前后对照，全部按单条语句冷测量。100k 合成曲库、页大小 120：`format` 深度 12000 由旧的 3.01ms（COUNT 2.108ms + 页面 0.901ms）降到单条 1.44ms；`format` 深度 50000 由 2.89ms 降到 1.16ms；`artist` 深度 12000 由 0.23ms 降到 0.12ms；`title` 深度 12000 由 0.16ms 降到 0.09ms。浏览器翻页整趟重放（100k 曲库、未打标簇 20000 行、页 120、834 页 100000 行）：`artist` 升序整趟 3.407s 降到 **3.076s**、降序 3.324s 降到 **3.099s**，也就是上一轮记下的那个「升序反而慢 13%」反向结果就此抹平，现在升/降只差 0.8%，且两侧都相对纯 OFFSET 翻页的 6.368s/6.754s 快一半以上；`format` 升/降 3.565s/3.591s 对 OFFSET 5.508s/5.571s。四趟走查的 OFFSET 退回页均为 0，且每一页与同位置 OFFSET 页取到的 id 序列 `identical_rows: true`。最慢单页：`artist` 升 8.829ms（第 599 页）、降 8.402ms（第 622 页）、`format` 降 12.388ms（第 834 页，收尾页只剩百余行但仍要走两条语句加解码）。
- 2026-09-17 — 说明新形状为什么仍然可 seek，免得后人以为放宽了 R38 的禁令。两条语句各自仍然是**单个**可 seek 的比较，OR 依旧禁止；行值比较 `(title COLLATE NOCASE, id) > (?, ?)` 只出现在 `expr = ?` 已经把范围收到一个键组之后，SQLite 拿它做组内的有序过滤，不是重新排序。`EXPLAIN QUERY PLAN` 逐组合验过（100k、页 120）：`title`/`artist`/`format`/`added` 四个排序 × 升降两向共 8 组，每组两条语句全部是 `SEARCH tracks USING COVERING INDEX ...`，没有任何一条落到 TEMP B-TREE 或全表 SCAN，包括 `format` 这种 100k 库里只有 5 个键值、单组两万行的极端形状。基准工具的 `bounded_pagination` 与 `cursor_pagination` 继续用硬断言守住这条线。
- 2026-09-17 — 补回归并逐处变异验证。`src/tests/test_library_cursor_policy.py`（13 项）里两条谓词断言重写为 `test_next_group_predicate_is_a_single_seekable_range` 与 `test_group_tail_predicate_is_direction_independent`，后者最初写成「断言谓词里不含小于等于号」，结果被 `track_no` 排序表达式自带的 `<= 0` 顶了回来，改为断言方向参数根本不参与该谓词；差分等价夹具的 SQL oracle `_sql_page` 改成把两条读语句拼接。`src/tests/test_library_sqlite.py` 新增 `test_cursor_page_reads_two_ranges_without_counting_the_group`：6 行夹具（Alpha 三行、Beta 三行）页大小 2，用连接替身追踪真实语句与绑定参数，要求恰好两条读语句、LIMIT 依次是 3 与 2（共享预算被第一条吃掉一行）、第二条只绑定游标主键 Alpha 一个字面量，并且整个请求不得出现对 tracks 的 COUNT。十处变异全部命中：组内行值改成包含等于 命中 11 项、组内 id 改成包含等于 命中 9 项、下一组改成包含等于 命中 13 项、下一组忽略方向 命中 6 项、组内谓词跟随方向 命中 3 项、跳过第二条语句 命中 9 项、预算去掉前瞻行 命中 4 项、第二条语句用满 limit+1 命中 1 项、`cursor_page()` 不校验排序 命中 1 项、预算按语句条数而非行数扣减 命中 3 项。其中「第二条语句用满预算」上一轮是个漏网的等价变异，这轮靠新增的 LIMIT 边界断言才抓回来，这也说明只断言结果行、不断言绑定参数是抓不住预算类缺陷的。还原后相关 108 项全绿。
- 2026-09-17 — 同时改基准工具的测量方法，因为旧测法本身会骗人。`cursor_pagination` 现在扫 `title`/`artist`/`format` 三个排序，每档取 3 个冷测样本的**中位数**并在产物里记 samples 字段为 3：改之前单样本在同一台机器上能摆动正负 3ms，足以把 0.7 倍的相对关系翻转成 1.1 倍，上一轮的深度结论就有相当程度是噪声。`first_screen_connection` 的池计数改成**差值**（`pooled_before` 在排空之后才取），因为排空不会回退进程级累计计数，原来的绝对值断言其实是顺序依赖的潜在测试缺陷。`empty_key_group_pagination` 段加注释写明：升序走查从 offset 0 起播，它的 OFFSET 对照始终停在浅层，深页对照只在 `cursor_pagination` 里量，不要拿这一段的升序数字谈深浅。产物见 `artifacts/library-benchmark-20260917-round42.json`。
- 2026-09-17 — 修掉「未打标那一簇让游标整段失效」这条契约缺陷：`library_cursor_policy._primary()` 与 `_text()` 把「字段缺失」和「字段是空串」当成同一件事（都要求非空），而 `prepare_track_persistence` 给未打标文件的 artist/album/format 写入的正是空串，页面的锚点又取自 `track_page_select` 投影的 `(sql_order) AS _cursor_primary`（**索引列**，不是 `item_json`），所以只要一页的最后一行落在那个空键组里，`encode_track_cursor` 就返回空 token，响应变成 `has_more: True` 却没有 `next_cursor`，客户端只能退回 OFFSET。为什么一直没被发现：所有既有夹具都给自己造的曲目打了标签，只有本轮按客户端真实翻页方式复现才现形。现在 `_primary()` 接受空串（长度仍受 `MAX_CURSOR_TEXT` 约束），标题改用新的 `_optional_text()`（可以空，因为并列键最终以 `id` 收尾），`id` 仍然必须非空（它是唯一能独立解析一个键组的键），NULL 主键照旧不可编码（任何比较谓词都表达不了它）。载荷版本号仍是 `v: 1`：只放宽了取值范围，没有改线格式，所以旧客户端拿到的 token 在新服务上照常工作，新 token 落到旧服务上会被判为无效游标而按 offset 重新返回首页，只影响跨版本降级这一刻。前端不需要改：`library_page_cursor_policy.remember()` 本来就只存不透明 token、空 token 不写入。
- 2026-09-17 — 给出这条缺陷的实测影响面，全部用「重放浏览器翻页」的方式量，而不是手写一份 keyset SQL 去比（上一版探针正是因为只改了 `artist` 列没同步 `item_json`，得出的数不可信，本轮作废重做）。100k 合成曲库、页大小 120：未打标簇 300 行时，artist 升序整趟有 2 页退回 OFFSET（合计 5.4ms）、artist 降序 3 页（合计 32.8ms）、format 升序 2 页（6.4ms）、format 降序 3 页（29.0ms），降序最慢那一页 11.1ms 而放宽后同一位置 7.3ms。未打标簇 20000 行时差别才成规模：降序整趟 4.385s 里有 **1.922s 花在这 167 个 OFFSET 页上**，放宽后 0 个退回页、整趟 3.324s（**-24%**），最慢页 15.2ms→9.2ms（**-40%**）。正确性用逐行等同来钉：6 趟完整翻页 × 834 页 × 100000 行，放宽前后与 OFFSET 翻页取到的 id 序列 `identical_rows: true`。
- 2026-09-17 — 同一条改动带出一个必须写下来的反向结果：**升序 + 巨大空键组会慢 13%**（未打标 20000 行时整趟 3.014s→3.407s），因为升序时 `''` 排最前，范围谓词 `artist >= ''` 是全表真命题、一行都裁不掉，而 `cursor_tie_where()` 的组内计数仍要扫完这一段，于是 COUNT 变成在 OFFSET 之外多出来的第二遍扫描；单页最坏值没有变差（8.615ms→8.613ms），变的是总功。降序则相反：`artist <= ''` 正好裁进空组、跳过前面 80000 行有标签的记录，所以省下的是整段。这个不对称不是本轮引入的，它是 R38「单范围谓词 + 组内计数」设计在**任何**巨大键组上的固有代价（`format` 排序只有 5 个键值，100k 曲库里每组两万行，早就是同一个形状），本轮只是把它测了出来；已在待办里单独安排一轮处理。
- 2026-09-17 — 补回归并逐处变异验证。`src/tests/test_library_cursor_policy.py` 9 项到 13 项：空主键在 6 个排序组合下编码/解码往返、`cursor_where` 与 `cursor_tie_where` 都绑定空串、载荷里缺 `p`/`t`/`id` 键仍判为畸形而显式空串按字段区分（`p`/`t` 可空、`id` 不可）、空标题仍按 `id` 收尾、新增夹具行 t-13（空标题）。差分等价夹具的守卫从「NULL 与空串都不可编码」改成「只有 NULL 不可编码」，并且对每一个可编码锚点新增 `assertTrue(token)`，防止以后又悄悄退回静默丢游标；`src/tests/test_library_sqlite.py` 新增 `test_cursor_walk_continues_through_an_untagged_key_group`（3 条有标记录 + 2 条 artist/album/format 均为空的记录，走查必须与 OFFSET 走查逐行相同且不得重复）。七处变异：拒绝空主键命中 15 项、解码把缺失当空串命中 1 项、解码放行空主键命中 1 项、解码放行空 id 命中 1 项、**编码放行空 id 一开始 0 项命中**（因为守卫写的是 `not item_id` 而不是 `item_id is None`，我第一次贴的变异是个等价变异、什么也没改），据此补了编码器一侧的空 id 断言后再验证才命中；还原后相关 106 项全绿。
- 2026-09-17 — 把这条契约做成可持续测量的东西：`tools/benchmark_large_library.py` 新增 `empty_key_group_pagination` 段，在所有计时段之后才把末尾 1200 行改成未打标（同时清掉列与 `item_json` 里的对应键，避免再造出一个列有值/JSON 无值的假形状），然后以页大小 500 走 artist 升序与 artist/format 降序，逐页要求「游标页必须与同位置 OFFSET 页逐行相同」「`has_more` 为真时必须有 `continues`」「每趟走查累计覆盖不少于一整个空键组」，任何一条不满足直接 `RuntimeError`。把 `_primary()` 改回拒绝空串后，该段立刻报 `a page ending in the empty key group lost its continuation cursor (artist/asc)`，也就是说以后谁再收紧这个契约，基准工具自己就会红。100k 实测（页 500）：降序游标页 13.6~17.4ms 对 OFFSET 20.8~21.3ms，走完空键组的最后一页 7.4ms 对 15.0ms；升序段内游标 14.8~16.3ms 对 OFFSET 13.3~18.9ms，与上面那条反向结果一致。产物见 `artifacts/library-benchmark-20260917-round41.json`，门禁 2009 项到 2014 项。
- 2026-09-17 — 记一条还留着的小口子，别把「has_more 却无游标」当成已经彻底消失：锚点行的主键是 NULL（历史索引里可能有 NULL 列）、或 `id` 为空时，仍会给出 `has_more: True` 而没有 `next_cursor`。现在的形状是安全的（客户端退回 OFFSET，不会丢行也不会重复），但这类页依旧不受键集漂移保护。要收紧就得改锚点选择：`decode_track_cursor_page_rows` 已经读了前瞻行，可以改成锚在「页内最后一个可用主键」之后，但那需要额外区分包含/排除语义，属于游标载荷格式变更，单独安排一轮。
- 2026-09-17 — 修掉前端共享 JSON 加载器 `src/app/ui/response_json_loader.js` 的三条缺陷，它被 `app.js` 的 17 个调用点共用（首屏曲库状态、分页、元数据、播放目标、DLNA 诊断全走这里）。其一，超时路径里的 `reader.cancel()` 既不 await 也没有 `.catch()`，流对象已报错时该拒绝无人接收：探针实测旧实现留下 `unhandledRejection: stream errored`，新实现为零。浏览器里这条拒绝只会静默出现在控制台，等于流资源被长期挂住且没有任何症状。其二，同一个 reader 可以被取消两次：`maxBytes` 命中时的 `await reader.cancel()`（第 45 行）与超时回调里的 `reader.cancel()`（第 35 行）是两条互不知情的路径，探针实测旧实现 `calls: 2`、新实现 `calls: 1`，因为取消现在收敛成一个记忆化的 `cancelReader()`。其三，非流回退分支的字节预算算错了口径：它拿 UTF-16 码元数 `text.length` 去比对**字节**上限，而 UTF-8 下一个码元最多要 3 字节（代理对是 2 码元 4 字节），默认上限 4 MiB 因此实际可放大到约 3 倍；夹具 `{"title":"中中中中中中"}` 是 18 码元 / 30 字节，旧实现在 `maxBytes: 19` 下照单解析（`rejected: false`），新实现拒绝（`rejected: true`），而在 `maxBytes: 30` 这条精确界线上仍然解析成功。
- 2026-09-17 — 记录非流回退链的新顺序与为什么保留最后一级。`response.body` 不可用的宿主（老 WebView）只能整体缓冲后再量字节，所以顺序改为 `arrayBuffer()` 优先（长度本身就是精确字节数，且不必先解成字符串）、其次 `text()`、最后才是 `json()`。`text()` 分支保留 `text.length > maximum` 这条**廉价下界**早退（码元数不可能超过字节数，所以早退永远不会错杀），只在它通过时才用 `TextEncoder` 做一次精确字节测量。`json()` 这一级仍然没有任何消费前的字节上限，这是明知保留的取舍：`Response.prototype` 上 `text`/`arrayBuffer`/`json` 三者同时存在，一个只有 `json()` 的对象只可能是测试替身或宿主自己包装的东西，为了「量不准」就把这类响应一律判成 `fallback`，等于让真实设备上可能存在的包装宿主直接拿不到数据（首屏表现为空列表），比一次超限解析更糟。因此这条路径的边界改由注释与 `declaredLength` 钉住：`Content-Length` 超限时必须在消费前返回 `fallback`，新增回归断言 `json()` 的调用数为 0。
- 2026-09-17 — 顺带去掉流式分支的一次全量复制：旧实现先把每个分块攒进 `chunks`，再 `new Uint8Array(total)` 逐个 `set()` 拷一遍，峰值同时持有「分块列表 + 完整副本 + 解码字符串」三份；现在改成 `TextDecoder.decode(chunk, { stream: true })` 增量累积文本，由解码器自己缓冲跨块的残缺字节序列，读满即弃，峰值少一份完整副本。跨块边界新增回归：把 `{"title":"中"}` 在一个三字节字符的中间切成两块（先给 `byteLength - 1`，再给剩下的 1 字节），必须仍解析出正确的标题；旧实现同样通过，所以这条是钉住新契约而不是证明缺陷。
- 2026-09-17 — 为上述改动在 `src/tests/test_ui_response_json_loader.js` 新增 6 项检查（同文件原有 3 项，Node 门禁项数 3 到 9），并用「同一套夹具分别跑旧实现与新实现」的探针脚本量出前后对照：`cancel-rejection` 旧 `events: [stream errored]` / 新 `events: []`；`double-cancel` 旧 `calls: 2` / 新 `calls: 1`；`byte-budget` 旧 `rejected: false` / 新 `rejected: true`；`buffer-first` 旧实现走进 `text()`（`textCalls: 1`）而新实现走 `arrayBuffer()` 且 `textCalls: 0`。测试上下文的 VM 需要新增注入 `TextEncoder`。另外记一条跨 realm 的写法坑：在 VM 里 `JSON.parse` 出来的对象带的是 context 的 `Object.prototype`，与测试文件里的字面量做 `assert.deepEqual`（该文件 require 的是 `node:assert/strict`）会因原型不同而失败，新断言一律比较解码后的原始值（`data.title`、`data.ok`）而不是整个对象。
- 2026-09-17 — 修掉首屏歌曲列表「将近一半时间花在打开数据库上」这条实测性能缺陷：`library_db_connect()` 对每个只读请求都完整走一遍 `sqlite3.connect` + `PRAGMA busy_timeout`/`journal_mode=WAL`/`synchronous` + 两次 `secure_sqlite_files` + `_ensure_library_schema_once` + 提交关闭，而这些全是**连接属性**而不是请求属性。拆开量得：20k 合成曲库、页大小 120 的冷首屏页中位 2.995ms，其中这段前奏（`SELECT 1` 后立刻关闭）就占 1.565ms，SQL 本体在 100k 实测只约 0.08ms；100k 曲库同一冷页 5.545ms。现在新增 `src/app/server/library_connection_pool.py`：`LibraryConnectionPool` 维护每库 4、全局 8 个空闲句柄（`__slots__` + 单把 `threading.Lock`，LIFO 取还以保住热页缓存），`library_db_connect()` 命中借用时跳过整段前奏，只保留每次都要做的 `secure_directory` 与一次 `secure_sqlite_files` 权限刷新。实测同一冷页 2.995ms→1.082ms（**2.77 倍**，省 1.913ms），前奏本身 1.565ms→0.100ms；100k 曲库连跑四份产物（`artifacts/library-benchmark-20260917-round39.json` 与 `-var1`/`-var2`）是 5.13~5.95ms→3.03~3.45ms，**1.49~1.96 倍**，每页省 1.68~2.92ms。绝对值随机器负载摆动，所以基准里锚住的是「池化必须严格快于重开」这条不变式与计数（连续 5 次冷读恒为 `reuses=4 / creations=1`），不是某个毫秒数。
- 2026-09-17 — 记录本轮的三条边界设计，免得下一个人把池做成会阻塞的队列或把写路径也接上去。其一，**借用永不等待**：池里没有可用句柄时调用方自己开一条，`borrow()` 在锁内只做字典与列表操作，绝不在锁内 `close()`，所以池不可能排在请求准入限制前面变成第二条队列（并发压测断言 6 线程 120 次借用无一阻塞、无一重复分配、`creations` 恰好等于池服务不了的次数）。其二，**写路径另起 `library_db_writer()` 且永不入池**：`save_items_to_sqlite()` 在一个长事务里重建表与索引，把这种句柄交给下一个读者等于公开半成品索引，所以本轮把 13 个只读调用点与唯一一个写调用点（原 `library.py:2107`）拆开，写连接也不再需要 `check_same_thread=False`。其三，**每个句柄带文件身份**：`(st_dev, st_ino)` 不匹配就地丢弃并关闭（Windows 的 `os.stat` 确实返回真实 file index，实测换文件后 ino 改变），`_library_database_identity()` 拿不到身份时 `borrow()` 清空该库全部空闲句柄、`release()` 拒绝入库；`_forget_library_schema()` 也同步 `drop()` 该库，因此一次扫描之后不可能再有读者拿着扫描前的描述符。
- 2026-09-17 — 记录「为什么池默认关闭、只有 `server.main()` 打开」这条取舍，这是本轮唯一有平台副作用的性能改动。空闲句柄会让索引文件在 Windows 上无法被删除或替换（实测 `os.remove`/`shutil.rmtree` 直接 `WinError 32`），而测试里有大量 `tempfile.TemporaryDirectory()` 在用例结束时删缓存目录、也有大量以 `def counted_connect(current_config)`/`side_effect=traced_connect` 打补丁断言「每个查询一条连接」的用例；把默认值改成开启会同时破坏这两类断言，也会让「未开启」这条路径失去覆盖。所以 `library_connection_pool` 只在 `server.py` 引导 `load_library_cache(config)` 之前写入 `True`（配置文件显式给了值就尊重它），`_library_connection_pool_enabled()` 默认 `False`。配套的可退出性由新增的 `close_library_connections()` 提供，并作为 `shutdown_runtime()` 中紧跟 `stop_library_watcher` 之后的清理步骤落地（`test_shutdown_runtime_drains_library_handles_after_the_library_stops` 钉住这个顺序）：`test_close_library_connections_releases_the_cache_directory` 直接断言排空后 `shutil.rmtree(cache_dir)` 能成功。另外「按线程复用」被实测排除：`BoundedThreadingHTTPServer` 每请求新建线程，线程局部缓存在真实服务里永不命中，而每个只读查询本来就只开一条连接，所以请求级复用同样零收益。
- 2026-09-17 — 为连接池补 25 项回归并逐处变异验证：新增 `src/tests/test_library_connection_pool.py` 13 项（LIFO 顺序、身份不匹配与身份缺失两条丢弃路径、丢弃只影响目标库、每库上限、全局上限跨库生效、上限互相抬升、句柄绝不同时交给两个读者、借用永不阻塞且计数自洽、`close()` 抛错不拖垮池、`drop()` 单库/全库、无身份不建空桶）；`src/tests/test_library_sqlite.py` 新增 `LibraryConnectionPoolingTests` 10 项（默认关闭时池计数一字未动、开启后第二次读命中借用、已提交的扫描对下一个池化读者可见、写路径既不借用也不带 `check_same_thread`、读失败丢弃句柄、被打补丁的假连接不得经池泄漏到别的用例、身份变化后新建句柄、排空释放缓存目录、两条连接路径在 PRAGMA/schema 前奏失败时仍须回滚并关闭句柄、建连失败不得计入池的创建数）；`test_server_lifecycle.py` +1（排空必须紧跟 `stop_library_watcher`）、`test_library_snapshot.py` +1（`connection_pool` 段只输出七个非负计数且不得带出路径）、`test_large_library_benchmark.py` 断言新增的 `first_screen_connection` 段。门禁总数 1984→2009。十五处变异全部命中且还原后转绿：忽略身份（4 项）、`release` 接受无身份句柄（1 项）、去掉 `isinstance(conn, sqlite3.Connection)` 守卫（1 项）、扫描改回走池化读路径（3 项）、池变成默认开启（9 项，同时证明这条默认值是真实约束）、成功读不还池（6 项）、`_forget_library_schema` 不丢句柄（2 项）、借用后仍重跑前奏（2 项）、关服时不排空（1 项）、去掉每库上限（1 项）、去掉全局上限（1 项）、`drop()` 只忘记不关闭（8 项）、把连接前奏挪回守卫之外（3 项，其中两项是**本轮之前就存在**的回归）、两条连接路径都不再回滚（4 项）、写路径不再关闭句柄（打中大片的临时目录清理用例）。
- 2026-09-17 — 记录一条本轮自查回来的自伤：把 `library_db_connect()` 拆成「可借用 / 必须新建」两条分支时，顺手把 `sqlite3.connect` + `_prepare_library_connection()`（三条 PRAGMA、两次 `secure_sqlite_files`、`_ensure_library_schema_once`）整体挪到了 `try` 之外，理由是「新句柄的建连失败本就该直接冒泡」。这个改法**同时**把前奏失败的处理挪走了：以前 `PRAGMA journal_mode=WAL` 或迁移抛错时会先进入 `except BaseException` 分支，走回滚、`failed=True`、再关闭句柄；挪出去之后异常照冒，但句柄既不回滚也不关闭，Windows 上还会把索引文件一直挂住。本轮靠变异验证抓回：把前奏改回守卫之外时，既有的 `test_library_connection_does_not_mask_body_failure_when_final_cleanup_fails` 与 `test_library_connection_does_not_turn_committed_work_into_cleanup_failure` 立刻变红，说明这条契约本来就有守卫、是我这轮的改动把它踩掉了。现在的形状是：`sqlite3.connect` 仍在守卫之外（没有句柄可清理，保持原样冒泡），而 `_prepare_library_connection()` 与借用分支的权限刷新都在守卫之内，失败即回滚并关闭；新增的 `test_a_failed_read_prologue_still_rolls_back_and_closes` 用 `subTest` 把只读与写入两条连接路径一起钉住，并额外断言失败的句柄不会留在池里；`note_created()` 也随之移到 `sqlite3.connect` 之后，否则一次失败的建连会虚报一个句柄，`/api/health` 里的命中率就此失真（新增 `test_a_failed_open_does_not_count_a_connection` 钉住这一点）。
- 2026-09-17 — 把新资源接入既有可观测与发布治理面：`library_snapshot.library_component()` 新增有界 `connection_pool` 段（`idle`/`databases`/`reuses`/`creations`/`closures`/`max_idle_per_database`/`max_idle_total` 七个非负整数投影，沿用 `_bounded_*` 口径，不输出任何路径），`/api/health` 与 `/api/diagnostics` 经新增的 `library_connection_pool_status()` 上报，这样设备上能直接看出池是否在服务请求、有没有触到上限。`tools/benchmark_large_library.py` 新增 `first_screen_connection` 段并带两条硬断言：连续 5 次冷首屏页必须至少复用 4 次且只新建 1 条连接，且池化中位数不得高于重开连接的中位数——也就是说以后谁把这条路径改回每请求重开索引，基准工具自己就会红，跟上一轮游标深度扫描的做法一致。100k 基准产物见 `artifacts/library-benchmark-20260917-round39.json`（另有 `-var1`/`-var2` 两份复测）。顺带一条门禁自证的记录：本轮改动接入投影时，`test_source_hygiene.test_literal_dicts_do_not_repeat_keys` 抓到 `library_snapshot.py` 里重复出现的 `"connection_pool" 字面量键（同一处投影被脚本贴了两遍），这类错误人眼审查很容易漏，字典字面量的重复键静默覆盖后只会在健康接口里少一个字段；已删除重复行并让全部门禁重跑通过。
- 2026-09-17 — 修掉曲库游标分页「越深越慢、深过某点后反而不如 OFFSET」这条实测性能缺陷：`library_cursor_policy.cursor_where()` 把续读位置写成三分支 OR（`primary > ?` OR `primary = ? AND title > ?` OR `primary = ? AND title = ? AND id > ?`），SQLite 证明不了这三段落在同一索引上连续，于是只能用有序索引从头扫到尾再逐行过滤。100k 合成曲库、页大小 120 实测：深度 1200 的游标页 0.15ms，深度 50119 涨到 2.8ms（title/asc）~6.5ms（artist/asc），而同位置的 OFFSET 页是 5.1~8.6ms，也就是说大约 12k 行之后游标**反而更慢**，跟 `library_query_spec.py` 里「深翻页交给游标契约」那条注释正好相反。现在把一件事拆成两条查询：`cursor_where()` 只回**单个**范围谓词 `expr >= ?` / `expr <= ?`（查询计划从 `SCAN` 变成 `SEARCH tracks USING INDEX ... (artist>?)`，同深度实测 0.07~0.09ms，快 40~90 倍），而「游标自己那个键组里已经看过多少行」由新增的 `cursor_tie_where()` 去数（`expr = ? AND (title COLLATE NOCASE, id) <= (?, ?)`，只在游标那一组内扫描），数出来的值作为页面 OFFSET 下传（`library._cursor_tie_skip`）。顺序语义一字未动：并列键仍以 `title COLLATE NOCASE ASC, id ASC` 收尾，NULL 与空串主键依旧编不进游标因而照旧不可达。
- 2026-09-17 — 记录「为什么必须是两条查询」这组对照测量，免得下一个人再把谓词拼回 OR：同一个值在谓词里出现两次时，Python 的 `?` 绑定会把它当成两个互不相干的参数，优化器推不出连续性；把游标值改成**具名参数**复用（`:p` 出现两次）确实同样能 `SEARCH`（深度 50119 实测 0.04ms），但整条页面 SQL 的过滤条件、搜索条件、分组条件全是 `?`，而 SQLite 不允许具名与匿名参数在同一语句里混用；把游标值塞进 CTE 再用 `(SELECT cprimary FROM fn_cursor)` 引用两次也不生效（仍 `SCAN`，2.8~6.3ms）；先只查 `id`（窄查询确实能命中覆盖索引）再按 id 回表取 `item_json` 的延迟关联同样帮不上（`SELECT id` 加同样的 OR 谓词仍是 `SCAN`，深度 50119 合计 4.07ms，比原来的 2.91ms 还慢）。单条范围谓词是唯一不需要动绑定风格就能让 SQLite  seek 的形状，代价是每次游标页多一条只扫一个键组的 `COUNT(*)`（实测 0.00~0.01ms）。
- 2026-09-17 — 为新的游标契约重写策略测试并补一条端到端大键组回归：`src/tests/test_library_cursor_policy.py` 现有 9 项。`test_cursor_where_is_a_single_seekable_range` 逐个断言六个排序键 × 两个方向的谓词**恰好**是 `expr >= ?` / `expr <= ?`、不含 ` OR `、只有一个绑定值（这条就是「可 seek」本身的守卫，因为 SQLite 的 seek 与否在小表上不稳定，拿查询计划当断言会随统计信息翻脸）；`test_cursor_tie_where_counts_the_cursor_group_in_page_order` 断言并列计数谓词与绑定个数一致；`test_inconsistent_title_cursor_follows_the_title_key` 锁住「`sort=title` 时以标题为准、忽略游标里另带的 `p`」，防止一个自相矛盾的游标把窗口挪到用户没见过的行上；`LibraryCursorEquivalenceTests` 用一张 12 行内存表（含大小写并列、重复标题、`track_no <= 0`、NULL 与空串主键）对全部 12 个排序组合、以**每一行**当游标做差分，与一个纯 Python 的两趟稳定排序参考实现逐行比对，参考实现按 SQLite NOCASE 只折叠 ASCII A-Z 的规则建模。`src/tests/test_library_sqlite.py` 新增 `test_cursor_walk_matches_offset_walk_inside_one_huge_key_group`：12 条曲目共享同一 artist/album/format，使这些排序下整库只有一个键组，续读完全依赖组内跳过，5 个排序键 × 2 方向 × 3 种页大小逐一比较「游标走完整个库」与「OFFSET 走完整个库」的完整序列且不得重复。五处变异各自命中预期集合：把组内计数写死成 0、把组内计数改成严格 `<`、把范围谓词改成开区间 `>`/`<`、让并列计数漏掉 `id` 分量、让并列计数随主键方向翻转——全部被抓到，还原后 101 项相关测试全绿。
- 2026-09-17 — `tools/benchmark_large_library.py` 的 `cursor_pagination` 从「只量中点一页」升级为深度扫描：深度 `[0, 1200, 12000, 50000]` × `title`/`artist` 各测一页游标续读与同位置 OFFSET 页，逐条记录 `cursor_versus_offset` 比值，并在**最深**那一档硬性要求游标不慢于 OFFSET（否则直接 `RuntimeError`），这样以后谁把谓词拼回 OR 或加了个让索引不再连续的条件，基准工具自己就会红。修完实测（100k 曲库）：游标页随深度基本持平（title 5.14ms→6.56ms，artist 6.41ms→6.19ms），OFFSET 页继续爬升（title→8.64ms，artist→10.28ms），比值 0.76 与 0.60。同一轮把单页固定开销拆开量了一次：冷页 2.67ms 里 `library_db_connect`（建连 + 三次 PRAGMA + 两次 `secure_sqlite_files` + 一次 schema 就绪检查）占 **1.46ms**，120 行 `item_json` 解码 0.27ms，缓存纪元两次 `os.stat` 0.01ms，SQL 本体约 0.08ms，也就是首屏列表将近一半时间花在「打开数据库」上，这是下一轮的目标。
- 2026-09-17 — 审计结论（浏览面游标本轮未改动）：`library_browse_cursor_policy.browse_cursor_where()` 已经是「前缀范围 + 并列键比较」两分支形状，不存在轨道页那种三分支退化；它拿不到 seek 的原因是数据面本身没有可用索引——`groups/albums/artists/composers/genres` 表上没有任何 name 排序索引，`folders` 只有 `idx_folders_root_parent_name(root,parent,name)`，而并列键是 `name COLLATE NOCASE`，与索引列的二进制排序不同，且分组页的 `name` 来自 `COALESCE(NULLIF(...))` 的分组投影。影响面受目录与分组基数限制（十万曲目对应的是千级分组），因此不改；已作为测量结论记入待办，若将来分组浏览成为热点再补 `(root, parent, name COLLATE NOCASE)` 与组表 name 索引。
- 2026-09-17 — 修掉元数据恢复投影把整首歌词截成标签字段：`metadata_unavailable_policy._text()` 对读到的任何值一律 `str(value).strip()[:_MAX_TEXT]`（`_MAX_TEXT = 512`），而 `local_pending_projection()`、`local_cached_projection()`、`local_lyrics_projection()` 三处都用它取 `item["lyrics"]`。歌词不是标签而是文档：内嵌/同名歌词读取与 provider 链路（`MAX_PROVIDER_LYRICS_BYTES`、`MAX_FFPROBE_LYRICS_BYTES`）都允许到 2 MiB，正常的 `/api/lyrics` 快路径（`metadata_service.lyrics()` 直接回传 `row["lyrics"]`）也完全不截断。偏偏是**冷启动与 worker 恢复**这两条降级路径会把一首长歌词砍成前几行，而且砍完仍然是 `pending: False` 的终态响应——客户端 `loadLyricsForCurrentTrack()` 在 `state.lyricsStatus === "loaded"` 后对该曲不再重取（app.js 的 `!force` 早退），于是截断的歌词面板会一直挂着，直到用户手动重开。`library_presentation.public_library_item()` 的注释本身就承认「较大的历史行仍可能带着 item_json 或整首缓存歌词」，也就是这类行确实在升级安装里存在。现在把两个口径拆开：`_text(value, limit=_MAX_TEXT)` 保留标签的 512 上界，歌词改走 `_MAX_LYRICS_CHARS = 2 * 1024 * 1024`（与上游 provider 预算一致），三处调用点各自显式传入。
- 2026-09-17 — 给恢复投影的歌词补三条互不重叠的回归与三处变异：`test_full_document_lyrics_survive_every_recovery_projection` 用一段 200 行 LRC（超过标签预算）分别走 `local_lyrics_projection`/`local_cached_projection`/`local_pending_projection`，逐字比对返回体；`test_document_lyrics_keep_the_document_size_budget` 用 `_MAX_LYRICS_CHARS + 100` 长度的文本证明「有界」这件事仍然成立，而不是被随手删掉上限；`test_recovery_projections_still_bound_tag_fields` 断言标题仍被截到**字面量** 512（刻意不引用模块常量，否则把 `_MAX_TEXT` 一起放大也能自洽通过）。变异：把 `local_lyrics_projection` 的歌词退回默认预算 → 前两条失败；删掉 `_text` 的切片 → 后两条失败；把 `_text` 的默认 limit 换成文档预算 → 只有标签那条失败。三处均无附带失败，还原后 `tests.test_metadata_unavailable_policy` 13 项全绿。顺带发现该测试文件依赖门禁脚本注入的 `PYTHONPATH`（模块顶部的 `try: from metadata_query_policy import filename_track_candidate` 失败会静默降级成 `None`），单独跑它会误红一条既有用例，因此变异脚本必须同时断言输出里出现 `Ran ` 才算数。
- 2026-09-17 — 审计结论（服务端读取/投影层一圈读完，本轮只改元数据恢复投影）：`library_snapshot.py`（120 行）的字段白名单与 `_MISSING` 哨兵配合正确，缺失键一律省略而不是补 0，`hit_rate`/`saturated`/`snapshot{}` 三个非整数字段各自单独收敛，`_bounded_search_index` 不做 `str()` 只做 `[:32]` 以免不可信诊断载荷触发超大临时表示；`playback/mpd_errors.py`（225 行）的判定顺序把「设备缺失」放在「输出 IO 失败」之前、`_last_index` 排序保证 `last_*` 是时间序而不是插入序、`limit` 与 `splitlines()[-max(200, limit*50):]` 双重封顶且上游 `_tail_text`/`MAX_MPD_LOG_TAIL_BYTES` 已经限制了字节数；`resource_limits.py`（244 行）`slot()` 的 `_waiting` 在「入队/超时出队/取得槽位出队」三条路径上严格对称，超时与队满都无需 `notify()`（没有释放槽位），计数器经 `_increment_counter`/`_safe_counter` 双向夹紧；`metadata_provider_response.py`（130 行）的读取循环、gzip 增量预算（`max_length` 恰好留 1 字节溢出位）与 `decoder.eof` 终检成立，JSONP 正则的函数名长度被限制在 64；`id3_parser.py`（117 行）帧大小/帧尾越界与 APIC 描述符终止符定位正确，读出的图片按 `MAX_COVER_FILE_BYTES` 过滤；`dlna/network.py`（170 行）在策略校验与实际建连之间用同一解析结果钉住地址，SSRF 面收敛为「仅私网/链路本地、排除回环/组播/保留」，并对响应 URL 复核端点未被换掉；`ffmpeg_cover.py`（110 行）以 `-fs` + 轮询 `getsize` 双重封顶输出、`SubprocessError` 走 `except Exception` 分支杀进程并回收、`finally` 里的 `fd`/`target` 清理幂等；`library_page_result_policy.py`（114 行）对预读行的 `has_more` 判定不会把预览行计入页面、越界 `track_no` 收敛到 `2147483647`；`metadata_candidate_search_policy.py`（121 行）的置信度/上限解析对 NaN、inf、小数、布尔与超大整数一律回落默认值，排序对 `_confidence` 的 `None` 已提前过滤。
- 2026-09-17 — 审计结论（首屏列表与元数据前端的四个加载器读完，本轮未改动）：`library_response_loader.js` 的槽位记账在「刷新绕过读缓存但共享同一在飞请求」「视图切换先中止上一次、其拒绝晚一个回合到达」两种竞态下都不重复计数（`released` 幂等标志 + `inflight.get(url) === request` 身份回校验），`getEpoch() === epoch` 保证过期代次的响应不会写回缓存，`clearLibraryResponseCaches()` 刻意「只中止不提前释放槽位」与之一致；`lru_cache.js`（85 行）的 `set()` 先把超限整页挡在门外再插入，因此淘汰循环 `while (size > max || weight > maxWeight)` 必然终止且不会刚插入就被自己挤掉，`deleteWhere` 在 Map 迭代中删除当前键符合规范语义；`library_response_policy.responseWeight` 取 `items/groups/folders` 三者最大长度并夹到 6000，与 `createLruCache(48, {maxWeight: 6000})` 共同给出「一页 500 行、缓存约 12 页」的内存上限；`response_json_loader.js` 的流式分支按 `maximum - total` 逐块检查、超时后通过 `setCancel` 回调取消 reader、`finally` 里 `releaseLock`，非流式回退分支另有字符数上界。以上四者的既有不变量本轮全部维持。
- 2026-09-17 — 修掉曲库分页缓存「提交前读到的页落进提交后的键」这条最长 20 秒的脏读：`library.py` 的 `_library_query_cache_get()`/`_library_query_cache_put()` 各自独立调用一次 `_library_database_cache_identity()`（把主库与 WAL 的 dev/ino/mtime_ns/size 编成缓存键的一部分），也就是说**读取半程与写入半程用的键可以不是同一个代次**。一次索引提交正好落在中间时：提交先 `invalidate_library_query_cache()` 整库作废、并把指纹推进到新值，而**提交前**读出来的那一页会被存进**提交后**的键；下一个读者的 get 用的正是提交后的指纹，于是稳定命中这份旧页直到 TTL 到期。上一轮加的作废栅栏挡不住这一路——`put()` 先取 `time.monotonic()` 再比 `invalidated_at >= now`，作废时刻必然早于「调用 put 的时刻」，于是判定为「未作废」。现在引入 `LibraryCacheEpoch`：`__init__` 一次性采集 `database`/`identity`/`read_at`，`get()`/`put()` 复用同一指纹并把 `read_at` 透传给 `LibraryQueryCache.put(..., read_at=)`；缓存侧把它收敛成 `admitted_at`（限定 `(0, now]`，非法值回落到 `now`），既用于作废比较 `invalidated_at >= admitted_at`，也作为条目时间戳存进 `_entries`，因此 TTL 从「读到数据的时刻」起算而不是从「想起要缓存的时刻」起算。五个入口（`query_library_page`/`query_library_groups`/`query_library_folders`/`query_library_root_folders`/`query_library_items_by_ids`）的 14 处 get/put 调用点全部改为经过同一个纪元；`page is None` 与超长 ID 序列这类根本不碰缓存的分支不构造纪元，不额外花那两次 `os.stat`。附带收益：每次缓存未命中少取一次库文件指纹。旧的 `_library_query_cache_key`/`_get`/`_put` 三个模块级适配函数随之内联消失，键归一化仍只由 `LibraryQueryCache` 负责。
- 2026-09-17 — 给「一次查询一个纪元」补三层回归，并用六处变异确认每条都有效：`test_library_query_cache.py` 新增 `test_put_fences_against_the_read_instant_not_the_call_instant`（t=105 读页、t=110 提交作废、t=112 才调 put：栅栏若仍按调用时刻判就会把提交前的页收进来）、`test_read_at_ages_the_entry_from_the_database_read`（read_at=110 而 put/get 发生在 140，TTL 30 秒必须判过期，不能让写入时刻给旧数据续命）、`test_out_of_range_read_at_falls_back_to_the_call_instant`（`None`/0/负数/NaN/inf/字符串/未来时刻七个取值一律回落到调用时刻且仍能命中）。`test_library_query_adapter.py` 整体重写：原来只断言键适配器不字符串化命名空间、不物化可迭代对象，那个函数随纪元删除，现在这两条改在 `LibraryCacheEpoch.get/put` 上断言，另加 `test_cache_epoch_pins_one_identity_and_one_read_instant`——用一个只会吐出两个不同指纹的迭代器，要求整条查询只消耗**一个**指纹、且两次写缓存都带上 `epoch.read_at`。`test_library_sqlite.py` 新增 `test_sqlite_library_queries_fingerprint_the_database_once`：对 tracks/groups/folders/roots/items_by_id 五个入口各跑「未命中 + 命中」两轮，逐轮断言 `_library_database_cache_identity` 只被调用一次，并要求命中结果与首次读取逐字相等。变异验证：栅栏改回 `now` 只打中第一条缓存测试、条目时间戳改回 `now` 只打中老化测试、get 侧重取指纹与 put 侧重取指纹各打中纪元测试加五入口测试、put 不再传 `read_at` 只打中纪元测试、folders 调用点退回「每次新建纪元」只打中五入口测试；六处均无附带失败，还原后这三个模块 117 项全绿。
- 2026-09-17 — 审计结论（`dlna/control_point.py` 620 行全文读完，本轮只删除了 `media_server` 的不可达预加载，控制面自身不改）：`refresh_upnp_cache_background()` 的 worker 在 `finally` 里用「generation 相等」与「`_UPNP_REFRESH_THREAD is threading.current_thread()`」两个条件分别清 `refreshing`，因此被 `shutdown_upnp_cache_background()` 作废的旧 worker 既不会覆盖新 generation 的在飞状态、也不会替别人解除准入，起线程失败路径同样把 `_UPNP_REFRESH_THREAD` 与 `refreshing` 一起回滚；`discover_upnp()` 对 SSDP 应答集合按 `location` 建索引并以 `UPNP_MAX_DISCOVERED_DEVICES` 封顶，探测阶段再以「设备数 16 / 预算 12 秒」双重截断，单个坏设备不会把后台 worker 拖死（`except` 分支仍保留一条 `online=False` 记录而不是丢设备）；`upnp_time_to_seconds()` 只接受 `\d{1,3}:\d{1,2}:\d{1,2}` 且把 24 小时以上的渲染器脏值归零，反向的 `seconds_to_upnp_time()` 则不做上界（越界的 seek 目标由渲染器拒绝，且调用方 `server.py` 先过 `safe_float`）；能力缓存 `UPNP_CAPABILITY_CACHE` 以单调钟老化、以 `probed_at_monotonic` 排序淘汰、超过 256 项收敛，`_capability_cache_entry()` 把损坏条目判为未命中。
- 2026-09-17 — 封面队列饱和时被挤掉的行不再永久丢失：`cover_load_scheduler.js` 的 `enqueue()` 用 `image.dataset.coverQueued === String(run.generation)` 做同一代内的去重，队列满 `maxQueued = 4096` 时如果是**普通**任务就直接拒绝并 `dropped++`（被拒的图保持被 observer 关注，下次交叉还会再来，这条路是好的）；但如果进来的是一条可见/优先任务，代码会 push 之后再从队尾挑一个最新的普通任务 `splice` 出去给它让位。问题在于**被挤掉的那张图仍然保留着本代的 `coverQueued` 标记**：它在入队成功的那一刻已经被 `observer.unobserve()` 交还给调度器、不在队列里、又因为标记存在而被 `reconcile()` 的 `freshImages` 过滤条件（`coverQueued !== generation && coverObserved !== generation`）永久排除，于是首屏之外的某些封面在整代生命周期内再也拿不到任何加载机会，行里只剩内联占位图——正是「列表滚过一段之后有几格永远空白」这种闪烁类反馈的形状。现在驱逐时同时清掉被挤掉者的标记并计入 `dropped`：`evicted.image.dataset.coverQueued = ""`，并 `run.dropped += 1`。清掉标记即可恢复：`data-cover-src` 仍在，下一次 keyed 提交的 `reconcile()` 会把它当成新图重新分类（非优先则交回 observer 观察）。
- 2026-09-17 — 给封面调度器补上「队列 ↔ 标记」一致性回归：`src/tests/test_ui_cover_load_scheduler.js` 复用已有的 4100 张压力夹具，先断言「拥有本代 `coverQueued` 标记的图片数 == `queued + inFlight`」确立基线，再用一次 `isIntersecting` 且**确实可见**（`rootBounds` 覆盖 `boundingClientRect`，走 priority 分支）的观察回调把队列顶到饱和，之后要求 `queued` 仍为 4096、`dropped` 变为 4、并且上面的等式仍然成立。两处变异各自只打中一条断言：保留被挤掉者的标记会让等式失败（4097 个标记对 4097 槽位但 `dropped` 仍是 3 时先被等式抓到），不递增计数则被「evicted cover must be reported as dropped」抓到；还原后 Node 回归全绿，且门禁通过 `Get-ChildItem tests -Filter test_*.js` + `node` 把这些断言纳入发布检查（失败即 `throw`）。
- 2026-09-17 — 审计结论（`src/app/ui/cover_load_scheduler.js` 314 行全文读完，判定其余部分无需改动）：`enqueue()` → `pump()` 的相互调用在旧 WebView 兼容路径上递归深度受 `maxConcurrent`（上限 32）约束，因为 `pump()` 的两个 while 都在槽位满时立刻返回，不会形成深栈；`start()` 在 `!source || image.hasAttribute("src")` 时于 `inFlight += 1` **之前**返回，不泄漏并发槽位；`reconcile()` 显式回收「DOM 已摘除但网络未有终态事件」的活动槽并用 `once` 监听器防止二次递减；重试用 `image.dataset.coverSrc !== source` 与 `isConnected` 双条件作废过期重试；无 `IntersectionObserver` 的回退游标只追加不重建（`new Set(run.fallbackImages)` 去重），因此老 WebView 上不会重启已开始的加载；`cancel()`/`stop()` 把 `inFlight` 归零并摘掉监听（既有断言 `removedListeners === 2` 固定）；构造期对 `maxConcurrent`/`initialPriorityCount` 的解析对 NaN、Symbol、布尔与越界值都有收敛，最终落到 `[1,32]`/`[0,32]`。
- 2026-09-17 — 删掉 DLNA 推送里根本到不了的 SetNextAVTransportURI 预加载分支：`media_server.soap_push()` 有约 40 行专门构造并发送「下一首预加载」，但全仓库唯一的生产调用方 `server.py:soap_push(device, item, handler)` 从不传第四个参数，而它上面 487-491 行的注释写明了原因——「队列推进由 renderer monitor 独占，否则 monitor 会把刚播完的曲目再播一遍」，`tests/test_remote_output_monitor.py` 更是直接把 `next_item=None` 断言下来。也就是说这段代码在应用里永远不会执行，却一直在骗读者：它复述了一遍 DIDL 拼装（`renderer_track_metadata(... item_id="2")`、`next_size = 0`），并且**漏掉了当前曲目必须过的 DSD 门禁**——`soap_push` 开头会拒绝把源码 DSD 推给明确不声明 DSD sink 的渲染器，而预加载分支不做任何能力检查，一旦有人把它接回去，就会把渲染器已经拒绝过的格式从旁路塞进去。现在连同 `next_item` 形参一起移除（`server.py` 的同名包装同步收窄）。
- 2026-09-17 — 删掉三个只有测试在用的 DLNA 媒体外壳：`DlnaMediaServer`（持有 media_url/media_mime/media_size 三个回调、只被 `dlna/__init__.py` 导出、全仓库无任何构造点）、它唯一的成员 `resource()`（返回 `url/mime/size/direct`，其中 `direct` 在任何 DIDL、JSON 载荷或控制逻辑里都没有消费者；真正的 Browse DIDL 由 `service.py:_didl_item()` 直接生成，`DlnaProtocolService` 拿到的注入是 `upnp_resource_mime` 本身）、以及随之失去调用方的 `_requires_lossless_transcode()`。另外 `server.py` 里 `upnp_media_url()` 与 `upnp_resource_size()` 两个纯转发函数也只是把已经 import 的模块函数再包一层，仓库内（含 `src/`、`tools/`、`src/tests/`）没有任何调用点，`test_dlna_media_server.py` 用的是 `dlna.media_server` 里的原函数。删掉它们同时清掉了 `server.py` 顶部两个只为死代码存在的 import 别名。`resource()` 那条「APE 对外必须按无损兼容字节描述」的不变量没有丢：改写后的 `test_ape_resource_size_uses_the_lossless_compatibility_bytes` 仍然断言 `upnp_resource_size` 走 `ape_flac`、`upnp_resource_mime` 报 `audio/flac`。
- 2026-09-17 — 推送动作序列变成显式契约：`test_renderer_push_metadata_exposes_public_album_art` 新增断言，一次 `soap_push` 必须恰好发出 `Stop`、`SetAVTransportURI`、`Play` 三个动作。此前只检查 `SetAVTransportURI` 的内容，没有任何东西阻止「再多发一个动作」，而删除预加载分支后这正是需要钉住的那条边界（队列推进只能由 monitor 通过 `command("next")` 发起）。变异验证：在 `return True, "pushed and started"` 之前插入一次 `SetNextAVTransportURI` 调用，只有该测试失败（且失败原因正是动作序列变长），还原后 `tests.test_dlna_media_server` 全绿。
- 2026-09-17 — 结构化日志写入不再持有指标锁：`Observability.write()` 的「stat + 轮转 + 追加 + chmod」整段写在 `with self._lock:` 里，而这把 `RLock` 是 `count()` 与 `record_http_latency_route()` 用的同一把。`server.py:_observe_http_request()` 在**每个请求**结束时都要 `count()` 两次再记一次延迟，`http_request_policy.should_write_http_request()` 又决定了「所有非 GET/HEAD、所有 4xx/5xx、以及所有成功的 `/api/` GET」都要同步写 JSONL——也就是说首屏那批 `/api/library`、`/api/library/groups` 请求本身就会写日志。锁被文件 I/O 握住的那段时间（`os.path.isfile` + `os.path.getsize`，达到阈值时还有 `os.replace` 轮转，然后 open/append/close 与 `secure_file` 的 chmod）里，其他 worker 线程连「给自己的计数器加一」都要排队，`/api/system/health` 与诊断要读的 `snapshot()` 同样被挡住。更糟的是这是正反馈：请求越慢 → 越可能触发写日志 → 锁越紧 → 其他请求越慢。现在 `write()` 用新增的专用 `_log_lock`，与指标锁彻底分离（两条路径互不嵌套，不存在锁序问题），日志之间的串行化照旧保留。
- 2026-09-17 — 给分离出的日志锁补上双向守护：`test_log_write_does_not_hold_the_metrics_lock`（阻塞住 `secure_file`，主线程必须能在 0.25 秒内完成 `count()`、`record_http_latency_route()` 与 `snapshot()`）与 `test_concurrent_log_writes_stay_serialized`（四个线程同时写同一个 JSONL，`secure_file` 处观测到的最大并发数必须为 1，四行内容都必须落盘）。前者防的是本轮修掉的回归，后者防的是「为了性能把日志锁也删掉」这种错误修法：轮转与追加必须原子，否则两个线程会同时把同一个文件改名、或各写半行。两处改动分别做变异验证：把 `with self._log_lock` 改回 `with self._lock` 只让第一项失败；换成一个空操作的锁对象只让第二项失败。
- 2026-09-17 — 审计结论（`observability.py` 260 行全文读完，判定其余部分无需改动）：计数名被 `OBSERVABILITY_COUNTERS` 白名单收住（未知名字直接返回 False，不进入字典，因此诊断内存有界），增量与总量分别经 `bounded_counter_increment`/`bounded_counter_value` 夹在 1e6 与 1e12 内，损坏值在下一次自增时被就地修复（`test_corrupt_counter_total_isolated_on_increment`）；延迟桶是 `HTTP_LATENCY_ROUTES` 固定 8 个键，`record_http_latency_route` 先把单请求贡献夹到 `MAX_LATENCY_TOTAL_MS` 再进聚合，`max_ms` 与 `total_ms` 口径一致；`redact()` 的深度（16）、条目（256）、字符串（8192）、键长（256）全部有界，且在键超长时直接把值也判为 `[REDACTED]`，遍历时 `next()` 抛异常走 `return result or "[UNAVAILABLE_MAPPING]"`，不会因为外部映射被并发改动而抛给请求线程；`write()` 整体 `except Exception` 后只累加 `log_write_errors`，诊断永不让请求失败，超长记录退化为固定小摘要。`request_id()` 用 `re.fullmatch` 校验 8~96 个字符，不合规直接换 uuid4，绝不 stringify 外部对象。
- 2026-09-17 — 曲库查询缓存写入侧不再持有共享锁做整页深拷贝：`LibraryQueryCache.get()` 早就把「取稳定引用→释放锁→`copy.deepcopy`→回锁校验」写成契约，还为它配了回归 `test_cache_copy_does_not_hold_the_shared_lock`；但 `put()` 里的 `copy.deepcopy(result)` 仍然写在 `with self._lock:` 块内。这把锁是**全局单例** `LIBRARY_QUERY_CACHE`（`library.py:126`，生产参数 ttl=20 秒 / limit=160 / weight_limit=6000）上唯一的 `RLock`，所有 HTTP worker 线程、每次索引写入后必调的 `invalidate_database()`、以及 `/api/system/health` 与诊断快照要读的 `snapshot()` 都得过它。一次最多 6000 行（每行是带十余个字段的 dict）的深拷贝在锁里跑，等于把首屏最需要并发的时刻（列表页扇出查询、集体未命中）串行化：一个线程在拷贝，其余线程连「读一个已经缓存好的页」都要排队，索引失效也得等它。现在拷贝移到锁外，与 `get()` 同构：锁内只做 `_purge_expired`、重量判定、取 `key[0]`，拷贝完再回锁插入与淘汰。新增确定性回归 `test_put_copy_does_not_hold_the_shared_lock`：拷贝被阻塞期间，无关库的 `invalidate_database` 与 `snapshot()` 必须在 0.25 秒内返回。
- 2026-09-17 — 拷贝窗口里发生的索引写入不会再被缓存写入复活：把拷贝移出锁后出现一个新窗口——`put()` 的数据是在作废**之前**读出来的，却可能在作废**之后**才插入，于是本应丢弃的行会以「新鲜页」身份再存 20 秒 TTL。现在 `invalidate_database()` 用 `_record_invalidation()` 记下每个库最近一次被整体作废的时刻（`OrderedDict`，上限 `MAX_INVALIDATED_DATABASES = 16`，与曲库缓存自身的容量口径一致，不会随路径数量无界增长），`put()` 回锁时若「本库作废时刻 ≥ 本次读取起始时刻」就放弃入缓存（结果照常返回给调用方，只损失一次缓存机会）。这里刻意按库记录而不用全局计数器：全局计数器会让 `put(A)` 因一次只涉及 B 库的作废被白白丢弃，而第一项新回归正是拿无关库的作废来验证写入仍然成功。新增回归 `test_put_is_dropped_when_the_database_is_invalidated_during_the_copy`。两处改动分别做变异验证：把拷贝挪回锁内只让第一项失败，去掉作废守卫只让第二项失败。
- 2026-09-17 — 审计结论（`library_query_cache.py` 293 行全文读完，判定其余部分无需改动）：`_purge_expired()` 在每次 `put()` 里最多遍历 `limit`（生产 160）个条目，代价有界，且 `snapshot()` 侧已有 `test_snapshot_coalesces_expiry_walks_until_cache_changes` 固定「不重复扫描」的口径，保持现状；重量记账自洽（list 结果可为 0、dict 结果取 `max(1, total)`，`put` 加与 `_remove` 减读的是同一个 `entry[2]`，不会漂移），淘汰循环每轮弹出一个条目因此必然终止，且刚插入的键已 `move_to_end` 位于 LRU 末端不会被自己挤掉；`build_cache_key()` 把可选文件身份放进 `("database_identity", identity, values)` 这层嵌套元组，而 `normalize_values()` 拒绝嵌套元组/列表，普通查询无法伪造出带身份的键；`normalize_database_path()` 用 `os.path.abspath` 但不做 `normcase`，Windows 上大小写不同的同一路径会被当成两个库，然而生产所有调用都经 `library_db_path(config)` 得到同一字符串，故不可达（作为观察项记入待办）；`get()` 在拷贝后回锁校验 `self._entries.get(key) is entry`，不会返回被替换或被失效的快照。
- 2026-09-17 — 重启历史不再只保留最旧的记录：`_bounded_restart_history()` 原先「从头遍历、攒够 limit 就停」，而 `restart_times` 是**追加序**（最旧在前），于是它返回的恰好是最该丢的那一段。两个后果叠加：`status()["recent_restart_times"]` 给 UI 与诊断展示的是最早几次重启的时间戳；`register()` 又以 `max_restarts` 作为该列表的上限，而 MPD 每次显式 `_start_locked`/`_restart_locked` 都会重新 `register()` 一次，截断后剩下的全在窗口（默认 60 秒）之外，监控线程里的 `now - stamp <= window` 于是永远筛不出近期记录，`len(recent) >= max_restarts` 永不成立，**「restart limit reached」这道熔断在依赖持续不可用（MPD 未安装、端口被占、设备消失）时被永久绕过**，进程按退避间隔无限重启、日志与 CPU 一起被吃掉。现在改用 `deque` 加淘汰感知的 `seen` 集合，返回最新的 `limit` 条并保持由旧到新，扫描长度仍受 `MAX_RESTART_HISTORY` 约束，脏值（NaN、重复、非数值、不可迭代）的收敛口径与原来一致。新增 2 项回归（含重新注册场景）。
- 2026-09-17 — 服务日志裁剪不再持有监督器锁：`_monitor()` 原先在 `with self._lock:` 之内直接调用 `_trim_service_log()`，而该函数对每个带 `log_path` 的服务最多重写 1 MiB 文本（读取、按行截断、回写），期间 `status()`/`start()`/`stop()`/`register()` 全部拿不到锁。MPD 输出日志在故障刷屏时很容易达到上限，慢磁盘或杀软扫描下 `/api/system/status` 这类健康轮询会出现秒级卡顿。现在锁内只取 `log_path` 快照，裁剪在锁外完成，完成后重新加锁并再次检查 `_stopping` 与 monitor generation 才继续本轮进程巡检，因此在 `shutdown()` 期间晚到的那一轮不会再去改动已经停止的条目。新增确定性回归：阻塞住的 `_trim_service_log` 必须允许并发的 `status()` 立即返回。
- 2026-09-17 — 审计结论（`services/process_supervisor.py` 552 行全文读完，判定其余部分无需改动）：`stop()` 仍在持锁期间执行 `_terminate_process()`（最长约 5 秒的 SIGTERM/SIGKILL 等待），这是刻意保留的——移出锁需要给条目额外一把「正在终止」租约，否则并发的 `restart()` 可能在同一端口上重叠起两个守护进程，收益不抵风险；`_ensure_monitor()` 会把 `_stopping` 复位，因此与 `shutdown()` 竞争的 `register()` 可能留下一个空闲监控线程，判定可接受（daemon 线程、无进程即无副作用，且此后任何显式 `start()` 本就期望恢复监督）；退避 `min(30.0, backoff ** min(len(recent), 5))`、`_reap_exited_process()` 吞掉 `wait` 异常、`_safe_int`/`_safe_float`/`_strict_bool` 对配置脏值的收敛均已被既有测试覆盖。本轮 3 项新回归使 `tests.test_process_supervisor` 达到 31 项全绿，2 处改动逐一验证：还原为旧实现后恰好由对应的新测试失败。
- 2026-09-17 — 改动记录自身不再有重复条目，并补上门禁检查：`CHANGELOG_AI.md` 的平铺区里有两组紧邻的重复行（`2026-09-07 内存曲库首屏分页接线`、`2026-09-05 首屏元数据可靠性` 各出现两次，内容完全相同），是此前批量补录时粘贴重复留下的，已删掉每组的第二份（保留首份，内容无损失）。更重要的是 `tests/test_change_record.py` 原本只检查「带日期 + 最新在前」，重复整块并不会破坏日期顺序因此完全不被发现——本轮就用同一个 prepend 脚本跑了两遍，当场把 4 条记录复制了一份。新增 `test_no_entry_is_recorded_twice` 要求平铺区不得出现同一条目两次（改动记录是每轮改动的验收面，重复即是噪声），并用「临时把最新条目复制一份」的变异验证该断言确实会失败、还原后立即转绿。
- 2026-09-17 — Play 不再握着渲染器锁通知外部：`DlnaRenderer.command()` 里 `if action == "play": return self.play()` 写在 `with self._lock:` 块内部，而 `play()` 自己会「先发布状态、释放锁，再 `_notify()` + 再排队后台加载」。RLock 可重入使得内层 `with` 立刻退出，于是 `_notify()`（遍历所有监听者：GENA 事件体的构造、以及 `server.py` 的 `renderer_state_changed` → `PLAYBACK_CORE.sync_external_session()`）与后台线程准入全部发生在命令锁之内。本文件在 `next` 分支上专门写了注释禁止这件事（「Do not invoke notifications or backend admission while the command lock is held」），并为 `next` 配了确定性回归，唯独 `play` 这条最常走的路径漏了：监听器一旦阻塞（例如事件服务正被另一条投递占着锁），所有其他 DLNA 命令与 `set_uri`/`snapshot` 全部跟着卡住。现在 `play` 在进入命令锁之前直接转发。新增回归 `test_play_notifications_do_not_hold_renderer_lock`（与既有 `next` 版同构：阻塞监听器 + 并发 `set_uri` 必须照常完成）。
- 2026-09-17 — 渲染器状态投影不再共享会被就地弹出的队列：`command("next")` 用 `self.state.next_queue.pop(0)` **原地**修改队列，而 `snapshot()` 与 `_notify()` 只做 `dict(self.state.__dict__)` 浅拷贝，于是交出去的那份「状态」里的 `next_queue` 就是活动列表本身。`snapshot()` 会被 `/api/dlna/renderer/status` 与 SOAP `GetPositionInfo` 等路径读取并序列化，监听器（事件体构造、`renderer_state_changed`）也常把收到的 dict 交给别的线程；期间任何一次 `next` 都会让这份已被读了一半的列表少一项，表现为队列数量抖动或 JSON 里少一条。现在抽出 `_state_copy_locked()` 统一产出「列表和条目都是副本」的状态，`_project_state_locked()`（原先在 `snapshot()` 里重复了两遍的五行诊断字段拼装）与 `_notify()` 同源使用。新增 2 项回归：`test_snapshot_returns_a_copy_of_the_next_queue`、`test_state_listeners_receive_a_copied_next_queue`。
- 2026-09-17 — 离线门禁不再可能拿旧字节码做验证：`tools/test_offline.ps1` 用 `python -B` 跑 discover，但 `-B` 只是不写 `.pyc`，**已经存在的 `src/**/__pycache__` 条目照样会被读取**；CPython 判断缓存是否有效只比较源文件的「整秒 mtime + 字节长度」，所以一次「长度恰好不变、且与缓存同一秒」的改动会让门禁运行的仍是改动前的代码（本轮的变异回归就真实撞上过一次：还原后的模块仍报 1 项失败，清掉缓存后立即全绿）。现在门禁在 `Push-Location` 之后为每次运行设一个一次性 `PYTHONPYCACHEPREFIX`（`$env:TEMP\fnaudio-offline-pycache-<guid>`），并在既有 `finally` 里按 `PYTHONPATH` 的同一套写法还原；`src/tests/test_offline_verification_script.py` 增加断言把这条约束钉住（与该文件既有的「门禁本身被测试」风格一致）。
- 2026-09-17 — 审计结论（`dlna/renderer.py` 428 行全文读完后判定无需改动）：`add_state_listener()` 没有只增不减的泄漏——`DlnaProtocolService` 全仓库只有 `server.py:3130` 一处构造，且 renderer 与协议服务在同一函数里成对新建，进程生命周期内不会给同一个 renderer 叠加监听者；发布打包侧已经封住字节码产物（`build_release.ps1:214` 的 robocopy `/XD tests __pycache__ /XF *.pyc`，加 `:397` 对载荷里残留 `.pyc` 的存在性校验，另有 `test_build_release_script.py:302` 固定该命令行），`update_source_manifest.ps1` 同样排除；静音期间的 `set_volume` 只记状态、返回 `{ok, deferred}` 并在取消静音时下发，与 `snapshot()` 用后端真实音量覆盖投影的口径自洽；`_loading_uri` 的三个改动点（`set_uri` 清空、`play` 置为当前 URI、`command` 清空）互不遗漏，因此不会出现「同 URI 的 Play 被永久去重」；`_schedule_backend()` 在起线程失败时释放单-worker 闩锁并抛出，由既有测试固定。新增 3 项回归（`tests.test_dlna_protocol` 70 项全绿），3 处改动逐一验证还原后即失败。
- 2026-09-17 — 带 SOAP Header 的控制器不再被整体拒绝：`parse_soap_action()` 用 `root.iter()` 找「第一个不是 Envelope/Body 的节点」当作动作节点，而 `iter()` 是文档序，SOAP 的 `<s:Header>` 恰好排在 `<s:Body>` 之前，于是 Header 本身（或它的第一个子元素）被当成动作。实测 `<s:Header><SessionID>0</SessionID></s:Header>` 加一个正常 Play，解析结果是 `("Header", {"SessionID": "0"})`，`_dispatch()` 只能回 `unsupported action: Header`，播放/暂停/换曲全部 500；连空的 `<s:Header/>` 都会触发。Synology、Windows Media Player 以及多数 Denon/Sony 控制端都会带 Header（本模块自己的注释里就记着 Synology 因描述文档细节被拒的先例）。现在动作只从 Body 的第一个子元素取，没有 Body 时退回原有对裸动作元素的宽容解析。新增 3 项回归（含一项端到端 `control()`）。
- 2026-09-17 — 浏览单个专辑不再读取整张分组表：`_metadata_for_object()` 判断 `albums:`/`artists:`/`genres:` 是否存在的方式是 `any(row["name"] == 名字 for row in self.library_groups(视图))`，而注入进来的 `library_groups` 是无分页调用（`server.py:3095`），走到 `query_library_groups(..., limit=None)` 会**跳过查询缓存**、`SELECT * FROM albums ORDER BY name COLLATE NOCASE` 全表扫并排序，再 `materialize_browse_rows()` 成 Python 字典，最后只用来得到一个布尔。`_browse()` 为了校验同一件事还会再走一遍（`server.py` 的 Browse 与 BrowseMetadata 两条路径都命中）。现在改为一次定向探针 `_group_exists()`，复用 Browse 真正使用的那条查询（`library_page({view, group, limit:1})`，走 `album = ?` 与 `idx_tracks_album`，并且命中库查询缓存），语义与数据路径一致；空标签在此之前直接拒绝，因为「空 group」在分页查询里等于「不加过滤」，否则会把整库挂到一个假容器下。
- 2026-09-17 — 删除 GENA 投递里从未被调用的记账代码：`DlnaEventService` 的 `_skip_delivery_locked()`/`_complete_delivery_locked()`/`_advance_delivery_locked()` 共 27 行只互相引用，`delivery_sequence`、`skipped_sequences` 两个键在全仓库（含测试与 tools/）没有任何其他读写点。实际的顺序性由每条订阅的 `deliveries` 双端队列加 `delivery_scheduled` 闩锁保证（同一时刻每条订阅只有一个 drain 线程，序列号在 `notify_renderer()` 持锁时按升序分配），这段代码即使被接上也不会改变 SEQ 的单调性。留下它只会让人以为投递顺序由它负责。
- 2026-09-17 — 订阅上限改为单一常量：`subscribe()` 里写死的 `64` 与 `snapshot()` 里上报的 `"subscription_limit": 64` 是分开的两处字面量，任一处被调整都会让 `/api/dlna/diagnostics` 展示一个与真实准入控制不符的上限。抽出 `MAX_EVENT_SUBSCRIPTIONS = 64`，两处同源（本轮把上限改成 32 的变异同时被新旧两项测试抓住，说明这条约束确实被固定住了）。
- 2026-09-17 — 审计结论（`dlna/service.py` 964 行全文读完后判定无需改动）：`_target_lock` 式的弱引用注册表在本文件没有对应问题；`prune` 式的资源上限此处已经齐备（订阅 64、pending 256、workers 1-8、`_saturating_increment` 饱和计数、`shutdown()` 先 `cancel_futures` 再有界 join）；`_next_event_sequence()` 在 `MAX_EVENT_COUNTER` 处归零而非饱和，是有意的 GENA 序号回绕；`_seconds()`/`_volume()`/`_mute()` 的入参边界（长度、非有限值、bool 拒绝）均已被既有测试固定；`_browse()` 的 `StartingIndex` 极大值不会打到 SQL，因为 `parse_library_page_query` 用 `numeric_int` 后夹到 `MAX_LIBRARY_OFFSET = 100000`。新增 7 项回归（`tests.test_dlna_protocol` 67 项全绿），4 处改动逐一验证还原后即失败。
- 2026-09-17 — 转码缓存不再让「源文件已消失」变成断连：`transcode_cache_ready()` 在注释里明确要求把这种竞态降级为缓存未命中，也确实只保护了目标文件的 `getmtime()`，却在最后一行调用 `_transcode_source_mtime()`，而后者对 `item["path"]` 做的是裸 `os.path.getmtime()`。`/api/transcode/status`（`server.py:1163`）与 `/api/transcode/warm`（`server.py:1434`）都直接用索引查出的行、没有 `isfile()` 前置检查，而 `do_GET`/`do_POST` 这条链路上没有任何异常处理（`run_request()` 只有 `finally`），所以曲库里一条已被删除/改名的记录（NAS 上很常见：在文件管理器里整理歌单）就足以让请求线程抛出未捕获的 `OSError`，浏览器看到的是连接被重置，而不是一份 `{"ready": false}`。现在 `_transcode_source_mtime()` 读不到源文件时返回 `None`，`transcode_cache_ready()` 据此判为未命中，`transcode_to_audio()` 则改抛 `RuntimeError("audio source is no longer readable")`（该函数原先会因为 `getmtime(target) < None` 变成 `TypeError`）。
- 2026-09-17 — 转码缓存的发布失败改成可处理的错误响应：`transcode_to_audio()` 把三条失败路径（ffmpeg 非零退出、超时/诊断超限、起不来）都转成了 `RuntimeError`，唯独漏了发布环节——`secure_file(temp)`/`os.replace(temp, target)`/`secure_file(target)` 裸放在最外层，缓存卷写满、只读挂载、权限被改都会抛 `OSError`。`/media/...` 的处理只用 `except RuntimeError` 转 501（`server.py:1809/1827/1839`），于是同样变成断连；`ResourceLimitError` 因为继承自 `RuntimeError` 才恰好被接住。现在发布环节单独捕获 `OSError` 并转成 `RuntimeError("failed to publish transcode cache: ...")`，临时文件仍由既有 `finally` 清理。既有测试 `test_unexpected_publish_failure_removes_partial_transcode_file` 原本断言 `assertRaises(OSError)`（等于把断连写成了契约），已按新契约改为断言 `RuntimeError`，其对半截临时文件的断言保持不变。
- 2026-09-17 — 一次失败的缓存清扫不再让每个转码请求重扫全目录：`cleanup_transcode_cache_if_due()` 的判断与置位都不在任何锁内，多个并发转码会各自跑一遍「`listdir` 整个缓存目录 + 对每个文件 `stat`」；更糟的是 `LAST_CACHE_CLEANUP` 只在清扫成功返回后才更新，一旦 `prune` 抛异常（缓存目录所在共享盘 EIO/ESTALE）水位线就永远不会arm，之后每一次转码都要重试同一场注定失败的扫描。现在改为：`_CACHE_CLEANUP_LOCK` 内先判断再占位（持锁期间不调用 `prune`，因此不与 `TRANSCODE_LOCK` 形成嵌套），清扫异常只记录不影响请求；同时 `prune_transcode_cache()` 自己兜住 `os.listdir()` 的 `OSError`（`isdir()` 检查与列出目录之间共享盘可能掉线），无内容可扫时返回 0。
- 2026-09-17 — 审计结论（`transcode.py` 全文读完后判定无需改动）：`_target_lock()` 用 `weakref.WeakValueDictionary` 看似会让同一目标拿到两把锁，实际 `with _target_lock(...)` 的表达值在整个 `with` 期间被强引用，且 `_TARGET_LOCKS_GUARD` 覆盖了 get-then-set，锁不会在有人持有时被回收；`media_mode()`/`transcode_command()` 的 `item["path"]`/`item["is_dsd"]` 取下标不可达——行来自 `query_library_item_by_id()` 的固定列投影（`is_dsd INTEGER NOT NULL DEFAULT 0`）与 `decode_item_row()`，且 `find_library_item()` 会先验 `path`；`_run_transcode_process()` 的双倍 `MAX_TRANSCODE_STDERR_BYTES` 检查（轮询内 + `wait()` 后）确实封住了「进程结束后才冲完日志」的窗口；`warm_transcode_cache()` 在线程创建失败时回滚队列条目与去重集合，不会留下永久占位的死任务。新增 8 项回归，5 处改动逐一验证过还原后即失败。
- 2026-09-17 — 封面预热线程不再把活留在「已经在退休」的 worker 上：`cover_cache` 的两个预热线程（交互页 `prewarm_thumbnails` 与扫描后 `prewarm_library_thumbnails`）都是「在 A 次加锁里判断队列已空 → 释放锁 → 回到 `finally` 再取锁把 `running` 置 False」。在这两次加锁之间到达的请求会在 `if state["running"]` 处看到仍然为真的标志，于是只把任务塞进队列、不再启动线程，而旧 worker 紧接着退出：`_INTERACTIVE_PREWARM`/`_LIBRARY_PREWARM` 里留下一个 `running=False`、`thread=None` 但队列非空的条目，这批封面永远不会被预生成（扫描队列更是要等到下一次全库扫描才被救回），表现就是首屏那些条目继续显示占位图并闪烁。现在两个 worker 都通过 `stop_when_drained()` 在做出「队列已空」判断的同一次加锁里清标志并注销注册项，请求方要么被 worker 看到、要么看到已退休状态并自己起线程。新增 2 项确定性回归（用计数锁把请求放进退休窗口内，去掉任一处修复都只会让对应那条失败）。
- 2026-09-17 — USB 声卡能力解析不再让整条输出链路崩掉：`playback/alsa_output.py:parse_dac_stream_caps()` 解析驱动写出的 kHz 采样率时，正则用的是非捕获组，`re.findall()` 因此返回整段匹配（例如 `44.1 kHz`），随后 `int(float(value.replace(",", ".")) * 1000)` 直接抛 `ValueError`。该函数没有捕获任何异常，异常沿 `enrich_dac_device()` → `alsa_devices_from_proc()` → `alsa_devices()` 一路上抛（这两处的 `except OSError` 拦不住它），结果是：只要有一张声卡的 `/proc/asound/cardN/stream*` 把采样率写成带空格的 `NN kHz` 形式，输出设备列表就整体取不到，而 `_selected_alsa_output()`、`output_capabilities()`、`select_output()`、`server.py` 的状态路径都要读它，首屏与音量控制一起失效。改为只捕获数字组并用 `safe_float()` + 8k~768k 边界过滤。新增回归。
- 2026-09-17 — ALSA 能力缓存改按单调钟老化：`probe_alsa_hw_params()` 用 `time.time()` 与 `probed_at` 相减判断缓存是否新鲜，NAS 开机后 NTP 常把墙钟往回拨，负数差值永远落进 300 秒窗口，于是重插后拿到的旧能力集（是否支持 Native DSD/DoP 就取决于它）会无限期地被当成新鲜结果返回。现在缓存条目同时记录 `probed_at`（展示）与 `probed_at_monotonic`（老化），新鲜度按单调钟判断并拒绝负年龄，淘汰排序优先使用单调钟、缺失时回退墙钟，与 `dlna/control_point.py` 既有的 `_capability_cache_entry` 口径一致。新增回归。
- 2026-09-17 — DAC 直连控制不再对自己锁窗口之外的管线发信号，也不再倒拨播放位置：`dac_control()` 在函数入口的一次加锁里复制进程列表、随后在另一次加锁里 `os.kill()`，两次之间任何并发的 `start_dac_playback()`/stop 都会替换掉管线，于是 SIGSTOP 打在已经不是我们的 pid 上（可能已被回收复用），而真正在响的曲目穿过「暂停」继续播放。现在每个分支在自己的锁窗口内重新读取进程列表。另外 `play` 无条件重置 `started_at`/`started_monotonic`/`playing`，重复收到的 play 会丢弃自上次恢复以来已经走过的秒数，进度条倒退；现在只在确实处于暂停时重新计时。两项各新增一项确定性回归（用计数锁把「替换发生在两次加锁之间」建模）。
- 2026-09-17 — 输出设备切换不再被并发轮询落盘污染：`mpd_service.select_output()`/`test_output()` 会在 MPD 重启前后临时改写 `mpd_output_alsa_id`+`mpd_output_stable_id`+`mpd_dop`，而每一次状态轮询都要经 `_selected_alsa_output()` 重新解析选择并在发现不一致时持久化。被验证拒绝的设备、甚至只是被试听中的设备，都可能在这段窗口里被写进 config.json，下次服务启动就继续用它出声。新增 `_exclusive_output_selection()` 上下文（`_output_selection_lock` 可重入 + `_output_selection_transition` 标志），读路径改走新的 `_persist_output_selection()`，切换窗口内的持久化直接丢弃；`test_output()` 的中途恢复从只回填 `alsa_id` 改为回填整份选择快照，并在 `finally` 里按「是否真的变过」统一持久化 + 单次重启（原先会连开两次 MPD）。3 项新增回归，另将切换窗口的空闩断言并入既有测试。
- 2026-09-17 — 输出选择三元组改为原子写入：`_selected_alsa_output()` 的 `legacy-migrated` 与首次偏好迁移分支原先分两次赋值 `mpd_output_stable_id`、`mpd_output_alsa_id`，`select_output()`/`test_output()` 同样先写运行时 id 再写稳定 id。两写之间被调度出去的轮询会读到「旧稳定 id + 新运行时 id」的半份状态，并据此把运行时 id 反写成旧声卡，DAC 换卡号（重插后 `hw:N,M` 变化）时表现为选错输出。全部 5 处改写为单次 `config.update({...})`，读取方不可能再看到半份配对。
- 2026-09-17 — 首屏冷启动不再重复扫描 ALSA：`mpd_service.output_capabilities()` 的互斥闩锁此前只覆盖「有陈旧缓存时派后台线程」一种情形。冷缓存（进程刚启动，或 `invalidate_output_capabilities()` 之后，例如切换输出设备）下并发调用者全部落到同步分支：闩锁被反复改写、`finally` 无条件清掉别人的闩锁，而原本的 `if refreshing and cached and not force` 保护分支在 `cached` 为空时永远进不去，等于死代码。单次冷构建会 `alsa_devices()` 枚举、对每张声卡起一个 `amixer -c N scontents` 子进程（各自最多 2 秒）、并对选中设备做 `probe_alsa_hw_params()`，首屏的多个并发状态轮询因此各自付一份同样的代价。改为以 `_output_caps_builders` 计数 + `_output_caps_idle` 事件表达「同一时刻只有一个构建者」：冷缓存且已有构建者在跑时，调用者等待并复用其结果（上限 `MAX_OUTPUT_CAPS_COLD_SHARE_SECONDS = 5.0`）；等待超时或对方没产出可用结果时才自行构建，因为返回空描述会让 `mpd_output._output_ready()` 误报「没有检测到真实 ALSA 声卡或 USB DAC，无法本机播放」并让 DSD 掉回服务端转码。构建者只释放自己取得的槽位。新增 3 项回归（并发只扫一次、等待方复用结果不重复扫描、卡住的构建者不会阻塞播放）。
- 2026-09-17 — 错误状态不再被无锁复制：`idle_status()` 在 `_idle_lock` 之外直接 `dict(self._underrun_state)`/`dict(self._playback_error_state)`，而设备监控线程每隔 2 秒用 `.update()` 重写这两个字典（含 `by_category` 子字典），状态端点因此可能拿到撕裂快照（新计数配旧的分类分布），最坏情况在字典扩容期间复制失败。新增 `_error_state_lock` 统一保护这两处共享字典的读改写，`_watch_for_playback_errors()` 的更新与 `idle_status()` 的复制都在同一把锁内完成，且保持在 `_observe_fault()`/`fault_status()`（另一把 `_fault_lock`）之外调用，避免锁序交叉。新增回归：锁被持有时 `idle_status()` 必须等待而非直接返回。
- 2026-09-17 — USB DAC 监控线程不再因一次失败永久退休：`_device_monitor_loop()` 的循环体没有任何保护，而它在 DAC 重连时会调用约定为「启动失败即抛出」的 `_schedule_playback_recovery()`（该抛出契约有既有测试固定），一次线程创建失败或 `amixer` 异常就会让该线程带着 DAC 热插拔检测与 MPD 日志错误监听一起消失，直到下次 MPD 重启才被重建。改为逐次 try/except 记录 `_observe_fault(error=...)` 并在下个 tick 重试，`return` 退出语义保持不变，故障通过 `fault_status()` 持续可见。新增回归：抛错的 tick 之后循环仍进入下一次等待。
- 2026-09-17 — 首次缓冲不足不再被误判为「刚刚重启过」：`_last_underrun_restart` 初始值为 `0.0`，而 30 秒去抖用的是 `time.monotonic()`（Linux 上为开机至今），于是在开机 30 秒内触发缓冲不足（NAS 上电自启并恢复播放是常见路径）时自动重启被跳过，只剩 `restart_suppressed` 计数。改为 `float("-inf")` 表示「从未重启」。新增回归：单调钟读数为 5.0 时首个缓冲不足仍会调用 `restart()`。
- 2026-09-17 — 审计结论（本轮核实后判定无需改动）：`_watch_for_playback_errors()` 的日志游标看似会在错误风暴时整段跳过，实际 `start = max(_last_log_size, size - MAX_MPD_LOG_TAIL_BYTES)` 保证增长超过窗口时改为读取最新 8 KiB，被跳过的只是中间旧字节，最新错误行始终被分类，丢失至多 1 个字节，故不改；`_record_status_latency()` 使用标准增量均值且样本数被 `_safe_counter` 上限饱和，不会溢出（长时间运行后均值趋于迟钝属已知观测性局限）；`_probe_age_seconds`/`_project_cached_probe` 已是单调钟优先、墙上钟仅作旧调用方兜底；`_schedule_playback_recovery()` 的注册与启动在同一把锁内完成，supervisor 侧的 `on_restart` 回调由其自身捕获，均无泄漏。
- 2026-09-17 — 元数据标签写入扇出加硬上限：`metadata_service._queue_album_tag_writes()` 以 `SELECT id FROM tracks WHERE album=?` 无界取行，而 `_store_entity()` 允许专辑名为空但 `artwork_id` 仍来自 provider 封面，此时 `album=''` 会匹配整库所有未填专辑的曲目；每条命中都走 `_queue_tag_write()` → `_upsert_job(queue_state=None)`，后者对每个新任务再执行一次 `SELECT COUNT(*) FROM metadata_jobs WHERE status IN ('pending','retry')` 全表扫描，于是一个畸形专辑实体即可在单个事务里排入近队列上限（默认 20000）的标签重写任务并反复计数扫描，把用户音频文件的批量改写拖进后台。新增 `MAX_ALBUM_TAG_WRITE_TRACKS = 2048`，查询改为 `ORDER BY id LIMIT ?`（工作有界且选取确定），空/纯空白专辑名直接返回。同轮给 `_backfill_album_tag_writes()` 的 keyset 游标补「必须严格前进」判定并移到排队之前，防止历史行 `entity_key` 以 BLOB 存储时其 `str()` 形式与 SQLite 排序不一致而在连接预热路径反复取同一批。新增 3 项回归（空专辑名不排队、扇出按上限截断、游标停滞时自行终止）。
- 2026-09-17 — 扫描锁不再被扫描前失败永久占用：`library.refresh_library_if_changed()` 原先在 `SCAN_LOCK.acquire()` 与 `try:` 之间执行 `bounded_int()`、`ScanDeadline()` 构造和 9 项 `SCAN_STATE` 赋值，这段任何异常都会带着锁逃逸到调用方，之后所有刷新请求永久排在锁后面（UI 停在“扫描中”，关停还要等这个 worker）。已把该段整体移入既有 `try:`，其 `except/finally` 本就负责状态复位与 `SCAN_LOCK.release()`，并在块首写明该不变量。新增回归以抛错的 `ScanDeadline` 替身验证扫描状态收敛为 error 且锁可再次获取。
- 2026-09-17 — CGI 服务就绪等待改用单调钟：`cgi_proxy.wait_for_service()` 以 `time.time()` 计算 6 秒截止窗口，fnOS 在轮询期间前跳系统时间会让浏览器侧的 CGI 请求继续挂起（后跳则提前放弃健康检查直接回 503）。改为 `time.monotonic()`。补 3 项此前完全缺失的该函数回归：完整预算下 15 次循环探测加 1 次末次确认为 16 次后判定不可用、服务一响应即提前返回、更短预算按比例收敛；测试用假时钟覆盖模块内 `time`，并把任何 `time()` 墙上时钟读取直接断言为禁止。
- 2026-09-17 — 收藏批量写入在过期增量合并路径不再反转：`state_store.save_user_state()` 的 stale-delta 分支以 `created_at = now + index` 写入 `favorites_add`，而 `load_user_state()` 按 `created_at DESC, rowid DESC` 读取，于是客户端一次批量收藏后自己最新的收藏反而排到最后（收藏列表顺序错乱，且只有版本冲突走该分支时才复现）。改为整批共用本次保存的 `now` 并按 `reversed(changes["favorites_add"])` 插入，让 `rowid DESC` 平局键还原客户端顺序，与全量保存路径语义一致。新增回归先在修复前复现出 `['c','b','a',...]` 逆序，修复后通过。
- 2026-09-17 — 记录一次审计结论与用户决定（本轮未改代码）：核实 `tools/apk-analysis/`（实测 1.80 GB、50,313 个文件）与 `tools/runtime/`（实测 1.43 GB、36,447 个文件）的用途后，按用户指示不写入 `.gitignore`。事实依据：仓库内没有任何被跟踪的 `.go`/`.mod`/`.sum` 文件；`tools/runtime` 的 `go`、`gocache`、`gomodcache` 与 `docs/GO_MUSIC_DL_PROVIDER_VALIDATION.md` 实际引用的 `go-clean`、`gocache-clean`、`gomodcache-clean` 是同一工具链与模块缓存的两份副本（两侧 `go.exe` 的 SHA-256 相同）；`fnos-1.33.4-*`、`sskit-stage`、`ca-installer-helper`、`trimp2p-smoke` 以及目录内所有 `.js`/`.py` 探针脚本在 511 个被跟踪文件中零引用，只有 `fnos-1.35.2-source` 与 `fnconnect-*.mitm` 被 `PROJECT_CONTEXT.md`、`docs/FN_CONNECT_RELAY_CAPTURE_20260812.md` 引为证据。发布面已确认安全：`tools/build_release.ps1` 只 robocopy `src/`（排除 `tests`、`__pycache__`、`fnaudio.fpk`）并由 `android-client` 单独构建 APK，`SOURCE_MANIFEST.sha256` 也只覆盖 `src/` 与 `android-client/`，所以 `tools/` 下的第三方产物既不会进 FPK 也不会进源码清单。剩余风险是版本库卫生：`git status -uall` 的 130,107 条未跟踪条目里有 83,625 条（64%）出自这两个目录，任何 `git add -A` 都会把抓包、反编译产物与可再生工具链带进版本库，因此提交必须继续使用显式路径。
- 2026-09-17 — 元数据 worker 探活不再抛异常：`metadata_lane_policy.lane_workers_alive()` 此前直接迭代 `service.fetch_threads`，属性读取抛错或残留非可迭代值（例如简化过的服务替身里的 int 计数）会把 `metadata_service_available()` 本应给出的 503 优雅降级变成 HTTP 层异常；新增 `_attribute()`/`_worker_list()` 两级防护，把无法判定的容器统一视为「该 lane 不可用」，交给调用方既有的惰性 `ensure_workers()` 恢复路径。`service_was_started()` 同样不再信任属性实现。新增 2 项回归（int 容器、抛错的 property）。
- 2026-09-17 — provider 诊断槽位驱逐改为可复现：`_ensure_provider_slot_locked()` 以 `min(names, key=last_seen)` 选择驱逐对象，但 empty-result/no-valid-candidate 计数器不带时间戳，多数候选 `last_seen` 同为 0.0，`min` 结果取决于 set 迭代顺序（跨进程不稳定），32 槽位满时同一构建可能驱逐不同 provider；改为 `(last_seen, name)` 复合键，平局时按名称驱逐，并补 2 项此前完全缺失的驱逐回归（平局按名称、最近活跃者存活）。
- 2026-09-17 — 离线门禁的 UI 清单发现拆出脚本并补齐盲区：`tools/test_offline.ps1` 原先只用匹配 `<script src="` 的正则从 `index.html` 发现待检查模块，任何属性顺序变化（`defer`、`type=`）都会让它静默返回空集合，门禁依旧全绿而 58 个 UI 模块不再执行 `node --check`；新增 `tools/ui_asset_gate.ps1` 的 `Get-DeclaredUiScriptPaths()`，容忍任意属性顺序与 `?v=` 查询串（打包后是真实构建戳）、跳过远端脚本、拒绝越出 UI 根的声明，结果为空时直接 throw。同时删除与发现结果完全重复的 12 条硬编码 `Invoke-NodeSyntaxCheck`（保留 `app.js`）。新增 `test_ui_asset_gate.py`：4 项经 PowerShell 执行的夹具行为测试 + 2 项不变量（`src/app/ui/*.js` 必须全部被 `index.html` 声明、被声明文件必须存在且带构建戳）；`test_offline_verification_script.py` 改为断言门禁已接入该 helper。
- 2026-09-17 — 文档同步：`docs/SOURCE_INVENTORY.md` 的“当前源码版本”仍写着 `0.1.223`（含 `src/manifest` 行），而 `src/manifest` 已是 `0.2.34`；两处更正为 `0.2.34`，并注明权威取值来源，其余历史统计保持原样（该文件已声明为初次整理证据）。本轮同时复核 `cover_cache.py` 两条预热 `while True`（均有 pending/世代/取消三重退出条件，未见空转）与 `fnos_api.py`：其共享目录路由仍被 `if False and` 关闭，`call_trim_api` 的 `socket.timeout`/`OSError` 未包装为 `FnosApiError`，属已知未修项。
- 2026-09-17 — DLNA 客户端发现容忍瞬时网络错误：`discover_upnp()` 的接收循环此前只吞 `socket.timeout`，一次 ICMP 派生错误（Windows `ConnectionResetError`、Linux `ECONNRESET`/`EHOSTUNREACH`）就让整轮发现抛异常，后台 worker 只能保留上次的设备列表；现在与同日服务端 SSDP 监听一致地容忍 `OSError` 并继续读取窗口内后续响应，同时用新常量 `UPNP_DISCOVERY_MAX_TRANSIENT_ERRORS = 8` 限制连续错误，硬故障时不再空转到 2.5 秒截止。发现 socket 另补 `IP_MULTICAST_TTL = 2`（默认 TTL 1 不被路由转发，跨子网渲染器此前完全发现不到），与 `_announce()` 发送口径统一。新增 2 项回归：错误后仍能读到第二台设备、连续错误达上限即放弃并关闭 socket。仅离线验证，跨子网与真机互操作仍需设备验收。
- 2026-09-17 — ALSA 播放进程不再丢弃非整帧读取：`alsa_player.py` 原先在每次 `os.read` 后直接截断不足一帧的尾部字节，而管道读到的长度由写入方决定，24-bit（3 字节/帧）与流尾块经常错位，等于持续丢弃采样（可闻爆音且播放时长缓慢漂移）；新增 `iter_pcm_chunks()` 把残帧结转下一次读取，仅在流结束时丢弃无法成帧的尾巴。`write_pcm_buffer()` 的 `-EPIPE` 处理从无上限 prepare 重试改为连续恢复计数 `MAX_ALSA_RECOVERY_ATTEMPTS = 8`，并优先使用 `snd_pcm_recover()` 覆盖 `-EAGAIN`/`-EINTR`/`-ESTRPIPE`（系统挂起与暂时不可写此前直接终止播放），绑定缺少该符号时回退 `snd_pcm_prepare()`。`check()` 不再在错误路径改写 `snd_strerror.restype`（返回类型集中到 `main()` 声明）并容忍非 bytes 错误文本。新增 5 项回归；仅以假 ALSA 绑定离线验证，真机输出未测。
- 2026-09-17 — DLNA URI 身份往返修复：推送给渲染器的 `/upnp/media/<id>/<file>` 现在与浏览 DIDL、`albumArtURI` 一致地对曲目 ID 做百分号编码，服务端 `/upnp/media` 与 `/cover` 路由在曲库查询前先解码。此前任何含空格、`/`、`%` 或非 ASCII 的队列/历史 ID 都会让渲染器请求 404 `media_missing`，而播放监控又能从同一地址反解出该 ID，形成“进度能看到、声音放不出”的错位。新增 URL 编码往返与 HTTP 集成回归（移除解码即失败）。
- 2026-09-17 — DLNA 推送健壮性与延迟修复：缺少 `path`/`id` 的队列或历史行不再在推送路径抛 `KeyError`，而是退化为不可用资源并由路由安全 404；`SetNextAVTransportURI` 预载不再为可选的 `size` 提示提前整轨转码，避免无损兼容资源独占单个 ffmpeg 槽位数分钟、把正在播放曲目的媒体请求拖成槽位超时；渲染器动作能力集合改为每次推送解析一次，不再在每个 SOAP 动作后重复构造。新增推送顺序与不转码回归。
- 2026-09-17 — 变更记录治理：`CHANGELOG_AI.md` 与 `TODO.md` 顶部扁平区新增结构门禁 `test_change_record.py`（条目格式、日期非递增、门禁不早于最新源码清单刷新），并把扁平区历史条目按日期归位，修正 6 处顺序倒置；`docs/INDEX.md` 使用规则明确每次改动必须在两份根文档留痕，持续优化自动任务同步该要求。
- 2026-09-17 — 首屏封面懒加载上界修复：新出现的离屏封面不再全部进入调度队列，只有首批按优先级入队，其余交由 IntersectionObserver 按需触发；同时跳过“已入队/已观察”的图片收集，避免翻页与长列表（曲库上限 200,000）在后台拉取成千张从未滚到的封面。新增分页突发回归。
- 2026-09-17 — `cmd stop` 残留旧服务修复：清理条件从硬编码安装根目录改为同时匹配 `@appcenter/fnaudio` 与 `--port`，安装目录不同的旧服务不再绕过清理，因而不会在停止后继续自动重启 MPD。
- 2026-09-17 — 空歌手名不再污染 provider：`person()` 补上与 `album()` 一致的入口守卫，缺少可用实体名时在触达 provider 前返回，避免 `urllib.parse.quote(None)` 抛异常被计入 provider 失败、累计两次即触发网易/QQ 冷却。
- 2026-09-17 — 可见行 metadata lane 泄漏修复：双 worker 改为 `try/finally` 释放页面级控制器；worker 在发出第一个请求前抛异常（例如请求键构造失败）时不再永久短路同一页的 lane 复用判定。
- 2026-09-17 — 发布缓存戳治理：打包时若 `index.html` 中任何本地 `.js`/`.css` 引用缺少 `?v=__FNAUDIO_ASSET_BUILD__` 直接报错，避免文件照常进包但 URL 跨版本不变、原地升级后命中旧缓存。当前 `index.html` 为 60 个已打戳引用、0 个遗漏。
- 2026-09-17 — SSDP 监听线程不再被瞬时错误杀死：`recvfrom` 现在容忍 `OSError`（Windows/Linux 上先前 `sendto` 触发的 ICMP 端口不可达会以 `ConnectionResetError` 冒出）并短暂退避后继续。`DLNA_SSDP` 在 `server.py` 只创建且无人重启，此前一次瞬时错误会让 DLNA 发现静默失效直到重启应用。
- 2026-09-17 — 补记范围与方法：`HEAD` 仍是 2026-08-14 的 d362047（约 4.7 万行改动未提交）。逐文件核对 `git diff`、新增模块与两份根文档后确认：`CHANGELOG_AI.md` 与 `TODO.md` 在 2026-09-09 至 2026-09-16 之间零条目，而按文件写入时间统计该区间有 256 次项目文件写入、147 个非测试源文件被触碰，故补录 38 条修改记录与 23 条待办镜像；补录本身即本轮唯一改动，未改代码。日期仅作定位用途（本仓库部分文档与源码的写入时间早于其内容，mtime 不可完全信任），行为结论一律以当前工作树与 1906 项离线门禁为准。模块边界多数已在 `ARCHITECTURE.md` 的“可测试边界”清单与 `DECISIONS.md`（D-044 资源预算、D-048 inotify、D-050 自签 TOFU、D-053 元数据与 Tag 写回独立、D-057 MPD 批处理）中定论，本次补齐的是缺失的行为级留痕，不改动既有结论。
- 2026-09-17 — 更正今日早前条目中“持续优化自动任务同步该要求”的表述：核对 `$CODEX_HOME/automations` 后确认本工作目录当前未配置任何自动任务，该留痕要求目前仅由 `test_change_record.py` 门禁与 `docs/INDEX.md` 使用规则约束，不存在会被自动同步的调度 prompt。
- 2026-09-16 — 补记曲库读路径与目录监听治理：`library.py` 接入 20 秒/160 项/结果权重与饱和计数均有界的分页缓存（拆分本身见 08-30 记录）、2 秒/32 项根摘要缓存加 32 路 in-flight 合并、`schema`/`search index mode` 有界状态表与缓存失败计数；JSON 缓存增加 32 MiB 字节上限、写入改为 500 条批量、签名分片与字节上限 200,000/8 MiB；`scan_library()` 支持 `found_offset` 续扫；inotify 监听改为非阻塞 + `O_CLOEXEC` + 单线程复用 + 256 KiB 有界读 + 4096 观看上限，避免目录抖动时监听线程堆积。新增 SQLite/缓存/刷新回归共 1900+ 行。
- 2026-09-16 — 补记封面缓存与预热重写：交互预热与整库预热拆成两条通道，各有 pending/根目录上限与 generation 计数（96/8 与 5000/8），库预热按 24 项分页并可 `not_before` 退避；缺失标记 5 分钟 TTL 且以 monotonic 判定，预热版本优先使用索引内的 `modified_ns`/`size`，不再对每个候选 `os.stat`（首屏与整库预热的系统调用大幅下降）；所有缓存读取走 `_read_bounded_file`（缩略图 8 MiB、alias 128 字节）；缩略图 ffmpeg 子进程带 deadline 看门狗与显式终止；`thumbnail_prewarm_status()` 输出有界诊断快照；关闭时两条通道一起有界等待。新增 `test_cover_cache.py` 520 行回归。
- 2026-09-16 — 补记 DLNA 事件与 SOAP 边界：GENA 通知改为每订阅有界队列（4 worker/64 pending、可 `snapshot()` 与有界 `shutdown`），投递带序号与跳过/完成/推进三态，慢或已消失的控制点不再无限堆积 NOTIFY 或阻塞其它订阅；XML 统一经 `safe_fromstring`（1 MiB 解析上限）挡住超大/恶意文档；SOAP 参数上界 8192 字符/32 参数/128 动作；`_seconds`/`_duration`/`_volume`/`_mute` 改为严格解析，事件序号带饱和保护；Browse 结果行数与 `TotalMatches` 走有界投影。新增 `test_dlna_protocol.py` 698 行回归。
- 2026-09-16 — 补记 DLNA 渲染器动作合并与守卫：`setTransportUri`/`control` 经 `_schedule_backend` 交给单一后台 worker 并以 `take_latest` 合并被取代的请求，`_load_generation` 守卫使迟到的后端结果不能覆盖更新的曲目状态；后端返回非 dict 时经 `_backend_result` 安全投影；跳转上限 24 小时、音量夹取 0-100 且不做字符串强转；外部渲染器监控的 URI/轨道 id/停滞判定抽为 `remote_output_monitor_policy.py`。
- 2026-09-16 — 补记播放核心与 ALSA 输出边界：`playback/core.py` 队列上界 50,000、会话计数器与命令票据上限、外部渲染器结果字段（URI/文本/错误）投影上界、`_plugin_result_accepted` 严格判定、逐项有界的 `_bounded_track_refs`；`alsa_output.py` 的 DAC 进度改用 `started_monotonic`（系统时钟被校时不再让进度条跳变），ALSA 能力缓存 64 条 LRU 淘汰且 busy 探测只缓存 5 秒，`stop_dac_locked` 以 1.5 秒 deadline 终止子进程并关闭其 stdout，`aplay -l` 改走有界捕获。
- 2026-09-16 — 补记转码与指纹子进程边界：`transcode.py` 的 ffmpeg 走带 deadline 的 `_run_transcode_process`，stderr 上限 64 KiB，新增 `TRANSCODE_STOP_EVENT` 使 worker 可干净退出，缓存 key/stem 有界且防碰撞，`safe_float`/优先级解析拒绝异常对象；`audio_fingerprint.py` 的 fpcalc 输出与指纹字节上限 512 KiB、路径 4096 字符、进程树终止与临时文件有界读写。新增转码缓存、服务端流与指纹回归。
- 2026-09-16 — 补记用户状态持久化配额与连接泄漏修复：`state_store.py` 引入歌单 1000/单歌单曲目 10,000/全局曲目 id 预算 50,000/收藏 50,000 的持久化上限与 `_trim_persisted_playlists`，revision 上限 10^12，`cache_dir` 文本有界；`state_db_connect()` 在 PRAGMA/建表失败时显式关闭连接，不再泄漏文件描述符；投影逻辑改为复用 `state_projection.py` 的有界 JSON 与文本边界。新增 `test_state_store.py` 338 行回归。
- 2026-09-16 — 补记 fnOS CGI 网关边界：`cgi_proxy.py` 新增 15 项上限（索引改写 16 MiB、配置与网关响应 1 MiB、代理请求体 2 MiB、query string 64 KiB/256 字段、响应头 64 条与名称/值 128/8192 字符、请求头值 4096、路由 4096、合并曲库路径 64），`_safe_proxy_route` 在解码后二次校验以拒绝百分号编码穿越，`extract_routed_query()` 用有界 `parse_qsl` 取回被路由路径，`proxy_response_headers()` 过滤/截断上游头，`json_object_or_empty`/`response_code` 拒绝异常标量。新增 `test_cgi_proxy_auth.py` 496 行回归。
- 2026-09-16 — 补记发布证据工具治理：新增 `tools/verify_release_evidence.ps1`（校验包内容、SHA-256、可选源码目录与 `RequireCompleteEvidence`）与 `tools/index_release_evidence.ps1` 的有界名称/哈希/布尔投影，使版本证据索引不再盲信目录内容。
- 2026-09-16 — 补记 Android 远端播放与图片链路边界：`RemotePlaybackPlayer` 为播放/停止/循环/随机/跳转各维护请求令牌，服务端乱序响应不能回退较新的用户操作，时长与位置经 `safeDuration`/`safePosition` 夹取，`updateModes` 反映服务端模式而不回写；`AuthenticatedBitmapLoader` 限制并发下载（16 待处理 + 线程池替代无界队列）、有界响应体读取、跨 origin 拒绝、按打开的描述符读取缓存大小、命中过期条目不回填、`shutdown` 取消在途调用且不再写缓存；`AuthenticatedCoverCache` 256 条上限 + 临时文件回收 + recency 原子替换 + 按连接 profile 分作用域；`FnOsAuthClient` 用会话代际与 `deliverCallback` 闸门阻止超时/取消的旧认证回调污染新会话；`HttpClientFactory` 拆分认证与媒体客户端、以 `sameProfileOrigin` 阻止凭据跨源转发并为自签证书提供指纹锁定的首次信任。
- 2026-09-15 — 补记 MPD 队列重建改为单次往返：`mpd_client.py` 新增 `command_list_ok()`，把 clear、逐首 `addid` 与随机/循环/single/consume 合成一条命令列表，保留每个返回的 song id 并要求 MPD 确认全部条目；2,000 首队列此前每首一次 localhost 往返，会明显拖慢 DAC 输出切换。同时加入行/响应/命令字节上限（256 KiB/8 MiB/16 MiB），`__enter__` 失败时显式 `__exit__` 以关闭已建立的 socket（问候语非法不再泄漏 fd），`mpd_probe` 走有界捕获，`safe_int`/`safe_float`/shuffle 拒绝异常类型。新增队列/状态/恢复回归 1200+ 行。
- 2026-09-15 — 补记外部探测与远端 URL 边界：新增 `process_output.check_output_bounded()`（参数与上限校验、进程树终止、超限抛 `ProcessOutputTooLarge`）、`probe_runner.py`（ffprobe 输出 2 MiB 上限、成功判定、原生读取回退）、`native_audio_info.py` 与 `ffmpeg_cover.py`（共享的有界封面抽取，输出上限二次复核、非零真实退出码拒绝）；新增 `metadata_remote_url_policy.py`，把 provider 返回的封面/歌词 URL 限制为公网 HTTP(S) 并排除本机与链路本地地址段后再交给 urllib；`metadata_match_policy.py`/`metadata_release_date.py` 提供有界归一化与汉字符折叠匹配。
- 2026-09-15 — 补记首屏请求键与查询参数拆分：新增 `ui/library_load_key.js`（判定切页/切视图是否同一请求，数值与文本均有界）与 `ui/library_query_params.js`（搜索 4096、其它文本 512、页码安全解析），把 `app.js` 中的请求键构造与查询串拼装变成可测纯模块；`http_request_policy.py` 统一请求路径/目标/请求体上界与诊断分桶、日志写入判定；`app.css` 修正轨道行与封面尺寸一致性。
- 2026-09-15 — 补记 Android 连接配置与 FnConnect 解析：`ConnectionProfile` 新增 `fnConnectRelay`/`fnConnectMode`（含副本方法与 legacy 中继映射）并改用类型严格的 JSON 字段读取，端口归一化；`FnConnectResolver` 引入 generation 化的替换/附着/判定/收尾，取消与新解析互斥，512 KiB 响应上限、每族最多 64 主机、直连探测总预算 8 秒且单次 1.8 秒按剩余预算收敛；`LoginActivity` 增加 `destroyed` 守卫与 FnConnect 设置入口，intent extras 走安全读取；`NativePlaybackBridge` 为队列/HTTP/媒体文本/请求 id 等加入 13 项上界并支持 `cancelRequestJson`。新增 `ConnectionProfileTest`、`NativePlaybackBridgeTest`。
- 2026-09-14 — 补记文件权限工具的符号链接与对象防护：`file_permissions.py` 的 `secure_directory`/`secure_file`/`atomic_write_text`/`preserve_owner_and_mode` 统一经 `_normalized_path`/`_path_argument`，拒绝非路径对象（不再调用任意外部对象的 `__fspath__`/`__str__`），并在目标为符号链接时拒绝赋权，避免以服务工作身份 chmod/chown 到链接指向的任意文件；`test_file_permissions.py` 新增符号链接与对象强转回归。
- 2026-09-14 — 补记 fnOS API 响应边界：`fnos_api.py` 限制 trim 响应 1 MiB、共享目录 64 条与单条 4096 字符、token 8192 字符，`_response_code` 只接受可解析标量，`_parse_http_response` 在有界字节上解码并可安全报错，`get_shared_accessible_folders` 逐条清洗空白与非文本。新增 `test_fnos_api.py`。
- 2026-09-14 — 补记播放 HTTP 契约与事件投影：`playback/http_contract.py` 的 `target_id`/`target_kind` 改走 `_target_text` 严格解析，队列条目 id 复用共享 `normalize_track_id`（拒绝对象强转与超长值），legacy `playing` 字段在异常输入时回落既有状态而非任意真值，`legacy_response_headers()` 接受非文本路径；SSE 事件投影迁至 `playback_event_presentation.py` 并对 `engine_epoch`/票据做上界归一。新增 `test_playback_http_contract.py` 67 行。
- 2026-09-14 — 补记 Android 加密 profile store 串行化修复：`SecureProfileStore` 的读-改-写改用进程级 `STATE_LOCK` 而非实例 `synchronized`。store 生命周期很短且由多个 Activity/回调各自构造，此前两把实例锁可让两次 `upsert`/`remove` 互相覆盖，表现为登录历史或活动连接被静默回滚；同时新增密文 1 MiB/明文 512 KiB/128 条上限、`unreadablePayload` 标记（密钥失效时保留证据而不是清空历史）与严格字段读取。新增 `SecureProfileStoreInstrumentedTest` 88 行。
- 2026-09-14 — 补记纯模块批次：`api_token_policy.py`（token 提取 4096 上界）、`cover_queue_policy.py`（预热队列身份 4096 上界与版本键）、`library_cursor_policy.py` 与 `library_browse_cursor_policy.py`（base64 keyset 游标：768 字符/512 文本上界、解码失败安全回退、游标 WHERE 组装）、`metadata_artwork_file.py`（有界打开/读取持久化封面）、`metadata_candidate_search_policy.py`（候选停止/继续与 8 条展示上限）、`metadata_provider_response.py`（provider 响应 4 MiB、歌词 2 MiB、gzip 解压上限、base64 歌词解码，成为 provider 上限的单一来源）、`playback_status_spec.py`、`scan_control.py`（`ScanDeadline`/`ScanCancelled`/`ScanTimedOut`）、`state_projection.py`、`ui/library_item_request_loader.js`、Android `ArtworkBitmapDecoder`（共享像素预算解码）。
- 2026-09-13 — 补记健康与诊断快照的输入安全：新增 `summary_values.py` 提供不触发外部 `__int__`/`__float__`/`__str__` 的计数、文本与布尔规范化器，`library_snapshot.py`/`dlna_snapshot.py`/`diagnostics_metadata.py`/`health_snapshot.py` 拆分公共投影；`diagnostics.support_snapshot()` 改以 `_mapping`/`_safe_get`/`_safe_dict` 读取每一层，并接收查询缓存、搜索索引、预热、封面缓存、缓存失败、存储、DLNA 发现/事件、HTTP worker、命令缓存等新输入。损坏或恶意的依赖载荷不再让 `/api/health` 与诊断接口抛错或泄漏超长字符串。
- 2026-09-13 — 补记 DLNA 事件负载与 MIME 校验：新增 `dlna/event_payload.py`，GENA 负载按 4096 URI/40 KiB 元数据/512 KiB body 上界并做 XML 转义；`dlna/profiles.py` 的 `_safe_mime` 以正则校验 type/subtype 且上限 128 字符，异常 mime 不再原样进入 `protocolInfo` 与 DIDL；`device_supports_native_dsd`/`mime_for_item` 拒绝损坏映射。新增 `test_dlna_event_payload.py`、`test_dlna_profiles.py`。
- 2026-09-13 — 补记曲库路径、写入与内存回退拆分：`library_paths.py`（64 根/4096 字符、允许列表、canonical 化、根标签与相对目录、配置合并）、`library_write.py`（扫描项规范化、根索引摘要、批量持久化准备）、`library_memory_query.py`（无 SQLite 时的 200,000 项内存回退：有界根、搜索文本 4096、过滤/排序/分页与有界随机采样均为纯函数）、`metadata_track_id_policy.py`（256 字符 track id 严格归一）、`embedded_lyrics.py`（ffprobe 风格载荷的嵌入歌词投影）、`port_probe.py`、`cover_item_cache.py`（单曲封面抽取的有界单飞缓存）、`playback_targets_response.py`；新增真机 PCM 控制/稳定性脚本与 `analyze_real_device_playback_log.py` 的有界解析。
- 2026-09-13 — 补记 AirPlay 输出租约与 ALSA 写入正确性：`airplay_service.py` 在启动 shairport-sync 前获取 `AUDIO_OUTPUT_LEASE` 并在停止时释放，避免与 MPD/DAC 同时抢占同一 ALSA 设备造成静默或设备忙；命令经 `shlex.split` 与 4096 字节上界、设备名与路径 512 上界、`/proc` cmdline 4 KiB 有界读、`airplay_enabled` 严格布尔、`max_restarts=8`。`alsa_player.py` 新增 `write_pcm_buffer()`：`snd_pcm_writei` 的返回帧数按部分写处理并推进偏移（此前一次短写会直接丢音频），设备名 256、采样率 1-768000、声道 1-32 均有界。`playback/mpd_output.py` 的定位改为 CUE 偏移感知（`cue_start` + 请求位置），模式与控制优先复用 service 连接而非每次新建。
- 2026-09-13 — 补记 UI 模块声明与删除确认：`index.html` 为拆分出的 56 个 UI 纯模块补上带 `?v=__FNAUDIO_ASSET_BUILD__` 的脚本声明，新增删除确认对话框（移入回收站/彻底删除、`aria-live` 状态播报）与设置对话框结构调整；新增 `ui/album_metadata_cache.js`（4096 条、文本/图片上界）、`ui/library_response_loader.js`（32 路 in-flight 上限）、`ui/library_track_filter_policy.js` 及 `test_ui_user_state.js`、`test_ui_queue_columns.js` 回归。
- 2026-09-12 — 补记浏览器 E2E 夹具的元数据生命周期与请求边界：`tools/ui_e2e_fixture.py` 新增 `/api/metadata/track` 首请求 `pending`、后续轮询 `review` + 候选的真实两阶段语义（含 `fixture-4` 已有封面样本）与 `/metadata/artwork/*`、`/fixture-cover.svg` 图片端点，使 E2E 覆盖 UI 恢复与按 key 行补丁路径而不只是 `{ok:true}` 回退；查询整数与 `Content-Length` 走有界解析、拒绝 `Transfer-Encoding`、非法 JSON/载荷返回 400、队列上限 4096、配置端口修正为 53199。
- 2026-09-12 — 补记源码清单可靠性：`tools/update_source_manifest.ps1` 在缺少 `Get-FileHash` 的精简宿主回退到流式 .NET SHA-256，并改为写临时文件后 `Move-Item` 原子替换，哈希中断不再留下被截断的 `SOURCE_MANIFEST.sha256`。
- 2026-09-12 — 补记容器与故障状态回归批次：新增 23 项 `test_media_formats.py` 回归（ID3 截断头/非法 syncsafe/超大声明负载/超出共享封面预算的图片、MP4 `covr` 嵌套深度与超大 atom、FLAC 超大/截断元数据块、APE 超大/截断标签、ffmpeg 抽取的输出上限与真实非零退出码、probe JSON 上限、range 解析纯模块与不做强转、`safe_filename` 有界且不可字符串化任意对象）以及诊断快照隔离异常 Mapping、超长数字文本拒绝、MPD 损坏故障计数归一化。
- 2026-09-11 — 补记配置输入边界全量收紧与元数据默认值变更：`config.py` 限制配置文件 2 MiB 且根必须是对象，全部键值经 `_bounded_int`/`_strict_bool`/`_bounded_text`/`_bounded_text_list`/`_normalized_keepalive_mode`/`_normalized_mixer_type` 归一（拒绝布尔冒充整数、拒绝对象的 `__int__`/`__str__`），`save_config` 在异常输入下返回 `False` 而不再抛 `TypeError`，`save_proxy_port` 端口有界；新增/暴露 `ffmpeg_max_waiters`、`http_max_workers`、`cache_dir`、`ffmpeg_path`/`ffprobe_path`、`mpd_data_dir`、`structured_log_path`、`airplay_*`、`dac_profiles` 的边界。**行为变更**：`metadata_enabled` 默认由 `True` 改为 `False`，并拆出 `metadata_tag_write_enabled`（默认 `False`）：新安装不再默认向第三方 provider 发请求，也不再默认把元数据写回音乐文件标签，需用户在设置中显式开启。新增 `test_config.py` 226 行回归。
- 2026-09-11 — 补记离线门禁改为发现式：`tools/test_offline.ps1` 现按 `index.html` 声明的脚本清单与 `tests/test_*.js` 目录发现执行 `node --check`/回归，并对 `tools/*.ps1` 全量执行 PowerShell 解析器语法检查（此前新增 UI 模块或 Node 回归若没人记得抄进清单就会被静默跳过）；显式设置 `PYTHONPATH` 指向 `src` 与 `src/app/server`，避免依赖隐式导入路径。
- 2026-09-11 — 补记源码卫生门禁扩展：`test_source_hygiene.py` 扫描范围由 `app/server` 扩大到整个 `app/`（覆盖 `server.py`、`ui/cgi_proxy.py` 等），新增 provider 响应/歌词上限必须单源于 `metadata_provider_response.py`、`TODO.md` 勾选项不得重复两项门禁。
- 2026-09-11 — 补记首屏 UI 纯模块批次与表格呈现：新增 `ui/access_profile_loader.js`（权限档位 TTL + in-flight 去重）、`ui/batch_request_pool.js`（4096 批/256 项/32 并发且有界快照）、`ui/creator_view_policy.js`（歌手/作曲者视图名称 512、曲目总数 10 亿上界与状态复位）、`ui/device_caps_presentation.js`（采样率 768 kHz/位深 64/DSD 速率表 16 项上界）、`ui/host_playback_session.js`（宿主 fnOS 桥接探测与载荷复制）、`ui/metadata_candidate_presentation_policy.js`、`ui/user_media_state_policy.js`（收藏 5 万/歌单 1000/曲目 1 万/合并 10 万上限与增量合并）、`ui/visible_metadata_prefetch_policy.js`（可见行预取选择、重试与一次性重武装、lane 复用与所有权判定）；`track_presentation.js` 新增 `columnValues()` 一次生成多列（此前每列都重建整张 values 表）并隔离异常 getter。
- 2026-09-11 — 补记服务端边界模块：新增 `dlna/text_policy.py`（DIDL/参数文本 1024、ID 512 字符上界，供服务端与媒体服务器共用）、`metadata_lane_policy.py`（元数据 lane worker 存活与服务启动判定，配合 09-17 的 lane 泄漏修复）、`metadata_local_lyrics_cache.py`（本地歌词缓存 4096 条与 100 万计数上界、多快照合并）、`metadata_numeric_policy.py`（有限置信度、有界 epoch、严格非负整数）、`http_worker_presentation.py`（HTTP worker 计数投影）。
- 2026-09-09 — 补记播放模型边界与会话身份字段：`playback/models.py` 的 `TrackRef.from_mapping()` 只接受 Mapping、文本 512 上界、时长必须有限且非负、`is_dsd` 仅认真正的 `True`、track id 走共享 `normalize_track_id`、`item` 仅在可安全物化时复制；`PlaybackState` 快照随带 `generation`/`engine_epoch`/`command_ticket`，使 SSE、轮询与命令响应对"哪个宿主/引擎实例产生了该状态"保持一致口径。
- 2026-09-09 — 补记封面容器读取拆分与可选进程有界化：新增 `cover_readers.py`（FLAC 图片块 8 MiB、APEv2 标签 16 MiB 上限）与 `id3_container.py`/`id3_parser.py`（ID3 声明负载 16 MiB 上限、截断头与非法 syncsafe 拒绝、文本/ID3v1 解码独立）；`dlna/upmpdcli_renderer.py` 的版本与 `pgrep` 探测改用 `check_output_bounded`，异常输出的外部命令不再无界占用内存。
- 2026-09-09 — 补记 Android 运行时连接身份判定：`PlaybackRuntimeConfig.activate()` 改为比较完整连接身份（host/port/https/证书指纹/用户名/密码/token/long token/webSession）而不再只比 profile `id`。重新登录拿到同 id 的新凭据此前被判定为"未变化"，导致播放会话不重启并继续用旧 token 请求；新增 `PlaybackRuntimeConfigTest`。
- 2026-09-08 — 首屏请求取消竞态修复：曲库响应 loader 不再把 URL 对应的已取消 Promise 复用给切页/切搜索后的新请求；旧请求的并发槽位释放保持幂等，新增替换请求与限额回归。
- 2026-09-08 — SQLite 曲库分页结果边界拆分：新增 `library_page_result_policy.py`，集中处理有界行解码、内部排序锚点、页面 SQL 投影与下一游标响应；`library.py` 保留兼容接线，新增策略回归。完整离线门禁通过（Python 1219 项及全部 Node/UI/脚本回归）。
- 2026-09-08 — UI 游标缓存边界拆分：新增无 DOM 副作用的 `library_page_cursor_policy.js`，统一连续分页 Token 的页码校验、长度上限、首分页清理与 64 项 LRU 式容量淘汰；`app.js` 仅保留接线，新增 Node 回归。完整离线门禁通过（Python 1215 项及全部 Node/UI/脚本回归）。
- 2026-09-08 — keyset 游标锚点校正：`added` 与 `track_no` 等排序不再从公开 `item_json` 猜测排序值，SQLite 页面查询直接返回有界内部排序锚点；即使历史条目缺少 `added_ns`，连续页仍与 OFFSET 页一致。
- 2026-09-08 — 曲库连续翻页 keyset 优化：新增有界、排序绑定的 track cursor；首屏和任意页码跳转继续使用原有 offset，连续下一页优先以 `(排序值, title, id)` 游标查询，避免深页重复跳过前置行。游标输入拒绝异常对象/超长值，合成曲库验证 cursor 页与等价 offset 页结果一致；完整离线门禁 1214 项通过。
- 2026-09-08 — 首屏 metadata 延迟证据补强：UI 指标新增首个可见 metadata 请求完成耗时，与请求总数、最近/最大/累计耗时一起通过安全投影和 Playwright 首屏断言，便于离线区分首屏让行与后续重试。
- 2026-09-08 — provider 基础字段投影拆分：文本清洗/长度边界与数值字段安全转换抽至 `metadata_provider_values.py`，`MetadataService` 保留兼容别名；新增异常 limit、NUL 文本和数值 schema 回归。
- 2026-09-08 — provider 响应解析边界拆分：gzip 限量解压、JSON/受限 JSONP、歌词多编码与 Base64 解码抽至 `metadata_provider_response.py`；`MetadataService` 保留兼容入口，新增纯模块回归覆盖错误编码、压缩膨胀和歌词资源上限。
- 2026-09-08 — 元数据曲目 ID 入口统一：`track_match`、歌词、播放优先级和候选确认现在共用有界文本/整数兼容规范化，拒绝布尔值、超长值和任意对象字符串化；异常桥接请求统一走结构化 invalid/false 路径，新增入口隔离回归。
- 2026-09-08 — 首屏封面请求可观测性：封面调度器新增隔离的有界事件回调，UI 指标现在区分实际请求、成功、失败与重试次数；补充调度器重试计数回归，便于离线夹具量化封面 hydration，而不改变加载队列时序。
- 2026-09-08 — artwork 文件边界模块拆分：新增 `metadata_artwork_file.py`，统一以同一已打开文件句柄取得真实大小并执行非空/8 MiB 上限；本地 artwork 读取、旧 source-url 缓存命中、MetadataService 公开查询和 HTTP 流式发送共享该边界，避免资源策略漂移。新增模块级竞态与输入回归。
- 2026-09-08 — metadata artwork 坏缓存恢复：`source_url` 命中现在复核缓存文件的真实非空大小；超限或空文件不再短路后续下载，自动重新获取合规资源。`artwork()` 同时复用共享 artwork ID 策略，拒绝非文本/异常 ID。新增恢复与输入隔离回归。
- 2026-09-08 — metadata artwork HTTP 发送侧二次限界：响应先以已打开文件句柄的 `fstat` 大小复核，再按同一快照长度发送；缓存文件在服务层校验后若被替换或膨胀，不会继续以陈旧 size 头或无界 `copyfileobj` 暴露。新增正常长度、陈旧 size 与超 8 MiB HTTP 集成回归；完整离线门禁 1192 项、Playwright 6/6 通过。
- 2026-09-08 — metadata artwork 服务端资源边界：公开 artwork 前以真实文件大小为准，拒绝缺失、空文件和超过 8 MiB 的膨胀资产；缓存 size 过时时自动修正，HTTP 流式响应不再信任陈旧 Content-Length。新增文件膨胀/size 漂移回归，HTTP 集成通过。
- 2026-09-08 — metadata artwork 读前资源上限：provider 若声明纯数字 `Content-Length` 超过 8 MiB，下载器在读取正文前直接拒绝；缺失或畸形头仍由既有 `MAX_ARTWORK_BYTES + 1` 限量读取兜底。新增读前拒绝回归，MetadataService 专项通过。
- 2026-09-08 — 发布证据索引执行回归：新增临时 PowerShell verifier 夹具，端到端验证索引器会清空目录穿越 artifact 与伪 SHA-256，并将异常 recovery note 规范化至 512 字符；不再只依赖脚本文本契约。
- 2026-09-08 — lyrics pending 恢复边界修复：带已缓存封面的 pending 歌词响应不再被误判为完成缓存；HTTP 层仍保留封面显示，同时继续探测/恢复 priority lyrics worker，Metadata lane 与 HTTP 集成回归通过。
- 2026-09-08 — artwork URL 边界统一：新增共享 `is_artwork_url()`，metadata 响应缓存判定不再维护独立正则；大小写、绝对路径和目录穿越形式均被拒绝，降低 artwork 投影模块漂移风险。
- 2026-09-08 — metadata pending 封面投影统一：歌词后台匹配中的响应改用共享 `artwork_url()`，非法或损坏的 artwork ID 不再通过字符串拼接进入公开 URL；新增 pending 分支回归。
- 2026-09-08 — 根目录无命中搜索早退出：先以现有 FTS5/LIKE 条件定位匹配 root；无命中时直接缓存空结果，不再读取/解析 `root_summary` 或回退 `GROUP BY root` 聚合。命中搜索仍复用摘要和旧库 SQL 回退，保持根目录总曲数与封面投影。
- 2026-09-08 — 发布证据索引输入治理：索引器不再直接信任 verifier 的 artifact、SHA-256 与恢复说明字段；文件名限制为安全 basename，校验和仅接受 64 位十六进制，恢复说明去除控制换行并限制 512 字符，避免异常 verifier 输出放大索引产物。
- 2026-09-08 — 根目录搜索计划一致性：根目录搜索复用同一次 FTS5/LIKE 模式读取，同时绑定缓存身份和 SQL 条件，消除模式切换窗口；曲库 SQLite 专项 96 项通过。
- 2026-09-08 — 搜索计划一致性收敛：歌曲/分类/文件夹/根目录搜索现在一次读取 FTS5/LIKE 模式，同时决定 SQL 路径与缓存身份，避免模式切换发生在两次读取之间造成缓存键错配；无搜索热路径仍不探测模式。曲库 SQLite 专项 95 项通过。
- 2026-09-08 — 搜索缓存键热路径收敛：无搜索的分类、文件夹和根目录浏览不再计算空 FTS/LIKE 模式令牌；仅实际搜索请求携带执行模式身份，保持缓存键最小化。曲库 SQLite 专项 94 项通过。
- 2026-09-08 — 元数据批次封面调度收敛：多条可见歌曲 metadata 回填现在先完成行级 patch，再只调用一次封面探测，避免每行更新都遍历整张列表；浏览器夹具验证补全后 `coverHydrations` 保持有界且相邻行不重建。
- 2026-09-08 — 搜索缓存执行路径隔离：曲库歌曲、分类、文件夹和根目录搜索缓存键现在包含实际 FTS5/LIKE 模式令牌；索引运行中降级或恢复时不会因 SQLite 文件指纹未变而复用旧执行路径结果。新增模式切换 SQLite 回归，曲库专项 93 项通过。
- 2026-09-08 — 本地歌词缓存可观测性：metadata status、health 与 diagnostics 现在提供两条本地歌词恢复入口合并后的有界缓存统计（entries/limit/hits/misses），不暴露路径或歌词内容；新增聚合、损坏计数与诊断投影回归。
- 2026-09-08 — 发布证据索引资源上限：`index_release_evidence.ps1` 枚举历史版本时只维护 `MaxEntries`（最多 256）个 semver 最新候选，不再物化并排序全部版本目录；输出仍保持降序和机器可读证据契约。发布治理专项通过。
- 2026-09-08 — 本地歌词缓存边界拆分：交互 provider 与后台 metadata service 统一使用有界、线程安全、按路径/mtime/size 失效的 `LocalLyricsCache`，保留虚拟路径 stat 失败时交由 reader 的兼容语义；新增 115 项 MetadataService/缓存回归。
- 2026-09-08 — 首屏快照边界拆分：将首屏快照的 JSON 解析、TTL、总数、条目过滤和序列化字节预算抽为无 DOM/存储副作用的 `library_page_snapshot_policy.js`；`app.js` 仅负责 localStorage 与状态接线。新增损坏、过期、超限和异常总数回归，浏览器 E2E 6/6 通过。
- 2026-09-08 — 首屏快照权威交接离线证据：Playwright 夹具现在预置有效 localStorage 首屏快照并暂缓权威 `/api/library`，确认等价权威页到达后触发 `snapshotMarkupReuses`、不新增列表提交且四个歌曲行 DOM 身份保持不变。元数据回填同时只传递实际改变字段，封面等非排序字段不再被误判为排序变化并触发额外整表协调；浏览器 E2E 6/6 通过。
- 2026-09-08 — SQLite 存储治理可观测性：曲库状态、health 和 diagnostics 现在公开脱敏且有界的主库/WAL/SHM/总字节数，用于观察索引与缓存的磁盘压力；实现只做文件属性读取，不查询 SQLite、不返回路径。新增状态、纯投影、health/diagnostics 与 HTTP 回归。
- 2026-09-08 — 100k format/序号分页索引：format 与“非正数排末尾”的 track_no 表达式新增稳定 `(..., title NOCASE, id)` 升降序复合索引；升级会移除已被覆盖的旧单列索引，控制索引资源。多格式、循环序号合成曲库中八个查询计划均无临时 B-tree，首/中/尾页约 4.0-14.0ms；基准持续校验计划，证据为 `artifacts/large-library-benchmark-20260908-format-track-index.json`。
- 2026-09-08 — 100k 最近添加分页索引：`added_ns` 排序新增 `(added_ns, title NOCASE, id)` 升降序复合索引，并在升级时删除不能覆盖稳定次排序的旧单列索引。合成 100k 曲库首/中/尾页升序 3.3/7.0/10.2ms、降序 3.5/9.0/13.6ms，查询计划均无临时 B-tree；基准也会持续断言索引选择，证据为 `artifacts/large-library-benchmark-20260908-added-index.json`。
- 2026-09-08 — 100k artist/album 分页索引：新增 artist/album 的 `(NOCASE 排序字段, title NOCASE, id)` 升降序复合索引，保留 UI 的稳定 title/ID tie-break。artist 首/中/尾页约 3.9-14.2ms，album 约 4.1-12.1ms；四个查询计划均不再使用临时 B-tree。基准同时持续验证索引选择，证据为 `artifacts/large-library-benchmark-20260908-artist-album-index.json`。
- 2026-09-08 — 歌词缓存封面恢复：歌词快速命中不再只查看曲目 artwork；缺失或无效时会复用已校验的专辑 artwork，并保持 album_artist 的历史键兼容，消除歌词已显示但封面短暂为空的恢复缺口。MetadataService 专项 110 项通过。
- 2026-09-08 — 100k 标题分页查询优化：默认标题排序不再重复拼接标题字段，新增标题/ID 升降序复合索引，保留稳定 ID tie-break 与 offset API。SQLite 查询计划不再建立临时 B-tree；96 首合成曲库首/中/尾页约 5.9/10.9/11.7ms，证据归档至 `artifacts/large-library-benchmark-20260908-title-index.json`。
- 2026-09-08 — 页外元数据批次 no-op：若同一批回投歌曲均已离开当前页，前端直接跳过渲染和页面快照写入，彻底避免页外异步完成造成当前首屏列表/封面重绘。专项 Node/UI 回归通过。
- 2026-09-08 — 可见元数据回投去闪烁：批处理先过滤当前页可见歌曲；页外请求完成不再把可见行的局部 patch 降级成整页 `render()`，避免异步预取结果引发首屏无意义的列表/封面重绘。专项 Node/UI 回归通过。
- 2026-09-08 — 歌词优先重试闭环：定时重试若再次网络失败，会继续沿用同一可取消 scheduler 和 12 次上限，不再被空 catch 静默终止；pending/异常重试仍保留 controller 所有权，切歌可取消尚未发出的下一次请求。专项 Node/UI 回归通过。
- 2026-09-08 — 当前曲目歌词恢复：歌词优先请求在无后续重试的空终态释放 controller 与曲目去重标记，允许后续按需恢复；pending/异常重试仍保持 controller 所有权，切歌可取消下一次请求。
- 2026-09-08 — 当前曲目元数据重试取消：网络异常后的有限重试定时器会立即重新持有原 AbortController，切歌/页面切换可在下一次请求前取消旧曲任务，不再留下不可取消的重试窗口。
- 2026-09-08 — 元数据 lane 所有权修复：可见首屏预取不再把历史 attempts 当作当前曲目优先 lane 的存活证明；优先请求结算且无后续重试时释放 controller，仍缺字段的当前行可以重新参与有限恢复。新增纯策略回归。
- 2026-09-08 — 状态刷新竞态修复：普通 `library/status` 请求在途时，显式刷新现在排队一次尾随 `refresh=1`；删除歌曲后的状态更新改走共享入口，避免强制扫描意图被并发轮询吞掉。新增纯策略与 UI 回归。
- 2026-09-08 — SQLite 曲库摘要单飞：冷缓存时并发 `/api/library/status` 读取按数据库键复用同一次 count/signature 聚合；等待最多 2 秒，协调表最多 32 条，超时或饱和时沿用独立安全读取。新增并发回归。
- 2026-09-08 — 首屏状态请求去重：分页提交后的延迟 `library/status` 探测现在复用统一的 in-flight 状态请求，避免与扫描中的周期轮询重复聚合 SQLite；手动刷新仍保留 `refresh=1`。
- 2026-09-08 — 歌词 provider 恢复语义：仅非空、非损坏歌词响应可记录 success 并解除失败冷却；普通空结果进入 bounded `empty_results` 并继续后备来源，避免“可达但无歌词”误报为成功。新增 MetadataService 回归。
- 2026-09-08 — 启动快照行投影加固：在最多 500 项的扫描预算内跳过异常/无 ID 行并继续补足合法歌曲，避免损坏旧快照造成首屏少行或后续权威回填闪烁；新增稀疏快照回归。
- 2026-09-08 — provider 候选恢复与诊断边界：空响应或无可展示候选不再记录 success、清除失败冷却；活动快照同时保留仅有 `empty_results`/`no_valid_candidates` 的 provider 行，方便区分“已触达但无匹配”和“未成功触达”。MetadataService 与纯投影专项 117 项通过。
- 2026-09-08 — 可见元数据 lane 复用：metadata projection 状态更新在同一已提交页/请求序列仍有排队或在途工作时不再取消并重启可见预取，避免重复 220ms 首屏静默窗口；页面切换、隐藏和已结算 lane 继续使用有界取消/恢复。
- 2026-09-07 — 元数据 provider 成功边界修复：曲目候选链仅在产生可展示候选时记录 success；空结果和无效候选不再清除失败冷却，保留后续有界恢复机会。新增候选与冷却回归。
- 2026-09-07 — 内存分页单遍扫描：可重放缓存现在一遍完成匹配计数与排序前缀选择，避免首屏回退重复过滤最多 200,000 条记录；`count`、分页顺序和上限契约保持不变。
- 2026-09-07 — 内存分页参数边界：内存曲库回退统一使用有限整数页参数，兼容迭代器不再对布尔/对象调用 `int()`；异常输入回退到安全空窗口，正常分页保持兼容。
- 2026-09-07 — 元数据候选键热路径：`track_candidates()` 将已计算的规范化 query/filename hint 传入缓存键策略，避免首屏预取和轮询中重复解析；默认调用契约不变，新增回归。
- 2026-09-07 — 内存曲库首屏分页接线：SQLite 缺失/切换时的页面投影现在使用有界计数与有序前缀选择，不再为少量首屏行全量排序缓存；单次迭代器仍保留兼容路径并正确返回分页窗口。专项 66 项通过。
- 2026-09-07 — 发布产物资源上限：构建脚本与恢复校验器统一拒绝超过 `10 GiB` 的 FPK，分别在复制/解包及 SHA-256 前执行文件属性检查，避免异常大产物占用离线校验资源。新增稀疏超限文件回归与脚本契约检查。
- 2026-09-07 — 元数据 provider 空结果观测修正：album/artist/artwork 的通用 provider 链仅在返回可用结果时记录 success；正常空匹配记录为 bounded `empty_results` 并继续尝试后备源，避免错误清除失败冷却或把“无匹配”误报为成功。新增 MetadataService 回归。
- 2026-09-07 — 大曲库随机查询优化：未过滤 `random100` 先读取最大 rowid 并进行有界去重探测，命中足量记录时改用 rowid 定位，保留既有排序与返回计数；搜索过滤、稀疏/异常 rowid 抽样不足时回退 `ORDER BY RANDOM()`，不改变可靠性。新增策略上限与 SQLite 回退回归，完整离线门禁通过（Python 1145 项及全部 Node/UI 回归）。
- 2026-09-06 — 可见行元数据 pending 恢复：首屏按需 metadata lane 在 12 次有限轮询后仍为 `pending` 或仅收到通用宿主成功 envelope 时，现保留行级去重所有权并安排一次页面级静默重启（3.5 秒、7 秒，最多两轮）。分页/视图切换/页面隐藏会取消该重启；终态失败和无匹配仍走既有恢复，不会扩展为后台无限请求。补齐纯策略和 UI 回归。
- 2026-09-06 — 首屏列表快照复用：新增启动快照到权威分页的可视行等价判定；内容未变化时复用既有歌曲列表 HTML，跳过重复模板生成、DOM 协调、封面调度与布局测量，进一步收敛加载完成后的闪烁。内容、封面、排序和播放标记确有变化时仍保持原有键控局部更新；Node/UI 回归与完整离线门禁通过。
- 2026-09-06 — 元数据按需链路复核：后台全库补全和 Tag 写入默认关闭仍只影响后台任务；当前歌曲、歌词页和显式单曲查询保持可用。服务与 HTTP 集成回归确认空/瞬态 provider 结果会回投本地候选并带 `pending/retryable` 恢复语义，不会误判为永久“无法获取元数据”。
- 2026-09-06 — 持续优化范围更新：自动任务优先处理无需真机的首屏列表加载/闪烁、按需元数据恢复，并继续覆盖发布治理、资源上限/可观测性、大曲库查询、前端渲染和模块边界；真实设备与媒体输出验收继续隔离。
- 2026-09-06 — 元数据桥接第四层兼容：应用层响应解包由三层提升至策略允许的四层白名单 envelope，覆盖宿主/CGI 在每一层追加 `data/result/payload/metadata` 的正常结果；五层及非白名单对象依旧不遍历。歌词、当前歌曲和首屏可见行共享此修复；完整离线门禁通过（Python 1128 项 + 全部 Node/UI 回归）。
- 2026-09-06 — 元数据回填无闪烁：歌曲列表不再因单曲 metadata/cover 完成而整行替换。新局部 patch 保持根行、同源封面节点、焦点、选择状态及在途图片请求，仅更新实际变化的封面块、歌曲信息与数据列。Playwright 夹具新增 `pending → completed` 回填验证，确认相邻稳定行不重建、列表提交保持有界；源码清单更新且完整离线门禁通过。
- 2026-09-06 — 持续目标续期：无需真实设备的首屏加载/闪烁、元数据获取恢复、资源与可观测性、大曲库查询和可测试模块边界继续由 `fnAudio 离线持续优化` 自动任务推进；真实媒体输出、App Center 和 Android 真机验收不在本轮结论内。
- 2026-09-06 — 首屏回填稳定性：键控列表对快照/权威页的行签名漂移增加最终可见标记比较，签名本身不再被视为展示差异；视觉等价行继续复用 live DOM 与已解码封面，降低列表加载完成后的闪烁。补齐歌曲元数据和歌词 `retry=1` 的 HTTP 集成回归，确保显式重试真实抵达服务层。
- 2026-09-06 — 元数据错误记录稳健性：`_finish_job` 与 `_retry_job` 复用受限错误文本投影，异常 provider 值不会让错误落库路径二次失败，便于持续恢复与诊断。
- 2026-09-06 — 元数据重试退避加固：新增有界 `retry_delay_seconds()`，避免异常 attempts 触发超大指数运算；重试延迟仍保持 60 秒起步、最多 3600 秒。
- 2026-09-06 — 封面重试去重：调度器为懒加载图片设置所有者标记，行内错误处理仅保留给原生 eager 图片，防止一次失败产生两条重试链。
- 2026-09-06 — 大曲库性能复测：100,000 首曲库首/中/尾页约 51.8/103.9/159.6ms，分页热缓存 78.7 倍，metadata overlay 3.2 倍，引用 hydration 6.3 倍，FTS5 相对 LIKE 17.7 倍；结果归档至 `artifacts/large-library-benchmark-20260906-latest.json`。
- 2026-09-06 — provider 文本资源上限加固：歌词/文本请求不再对不可信 `limit` 调用自定义转换，非法参数使用固定全局上限，避免响应读取边界被异常适配器输入破坏。
- 2026-09-06 — 元数据 HTTP 恢复策略模块化：新增 `isTransientHttpStatus()`，统一首屏及当前歌曲请求的临时超时/限流/服务器错误处理，便于后续离线夹具覆盖。
- 2026-09-06 — 元数据瞬时网关恢复：首屏和当前歌曲请求对 408/425/429/5xx 进入 pending 重试，不再因代理限流或临时过载静默停止元数据获取；认证和参数错误保持终态处理。
- 2026-09-06 — 封面预热键长度容错：纯策略现在仅接受有限整数长度，异常参数使用安全上限，不会调用不可信对象的 `__int__`；封面队列专项回归通过。
- 2026-09-06 — 封面预热队列策略拆分：新增受限、无隐式转换的预热键策略；首屏交互预热继续按曲目 ID 去重，扫描全库预热继续按文件路径去重，避免异常扫描对象或重复 ID 导致预热错误合并。封面专项离线回归通过。
- 2026-09-06 — 元数据候选评分输入隔离：本地 Tag 的异常对象/非法数值不再触发隐式字符串化，单首损坏记录安全降级并继续后备 provider；新增回归。
- 2026-09-06 — 封面预热入队非阻塞化：交互/扫描预热的去重键不再为未带索引版本的曲目同步 `stat()`；真实缓存探测继续在后台 worker 中执行，避免首屏列表被预热准备阶段拖慢。
- 2026-09-06 — 播放启动歌词任务补齐索引文件版本：`prioritize_track()` 写入任务时携带 size/modified_ns，使 worker 可复用非阻塞本地歌词缓存键；100k 曲库离线复测保持有界。
- 2026-09-06 — provider 数值字段容错：网易云发布时间与 JOOX section/type/code 不再直接 `int()`，异常 schema 只跳过当前字段/条目，不会让整个数据源进入失败冷却；新增离线回归。
- 2026-09-06 — 当前歌曲歌词缓存复用扫描器文件版本：有 `modified_ns/size` 时不再重复 `stat()`，缺少索引版本才回退磁盘探测；新增 provider 回归。
- 2026-09-06 — 首屏封面版本探测进一步异步化：冷列表序列化对未带索引媒体不再同步 `stat()`，使用有界版本回退；封面接口仍执行权威版本校验，避免大曲库首屏被 NAS I/O 阻塞。
- 2026-09-06 — 首屏分页封面 I/O 优化：列表序列化阶段改为仅复用进程内已知缩略图/缺失标记，未知封面不再逐行触发磁盘探测；后台预热与封面接口仍负责生成和校验，新增封面与列表投影回归。
- 2026-09-06 — 部分 Tag 场景的元数据前台回退：已有标题但缺少歌手/专辑时，安全展示文件名“歌手 - 歌名”候选，同时保持低置信度与不写回原则；新增服务回归。
- 2026-09-06 — 本地歌词读取优化：MetadataProviders 增加 256 项文件版本 LRU，重复 provider 轮询复用嵌入/旁车歌词解析结果，减少大曲库磁盘读取；新增 MetadataService 回归。
- 2026-09-06 — 元数据空 envelope 恢复：宿主返回 `{ok:true}` 但缺少候选/封面/歌词时，不再计为成功或长期 no-match；进入有限重试并释放 dedupe key，等待后续 worker/provider 投影恢复。
- 2026-09-06 — 歌词元数据桥接兼容：`loadLyricsForCurrentTrack()` 现在使用统一有界 envelope 解包，兼容 CGI/宿主多层 `data` 包装，避免歌词获取成功但界面显示为空。
- 2026-09-06 — 首屏元数据封面回投：可见行预取不再要求必须存在 `best` 候选；独立 artwork 缓存或响应封面现在可直接显示，避免 provider 已返回封面却被空候选分支丢弃；新增 UI 静态回归。
- 2026-09-06 — 首屏 DOM 协调性能：歌曲行新增稳定 markup signature，键控提交优先用签名判断变更，避免大列表更新时 clone/序列化每个 live row；旧节点和分组行仍使用兼容回退。
- 2026-09-06 — 元数据 envelope 恢复边界：安全捕获异常 `data` getter，损坏的宿主响应不会让解包抛错并终止歌词/封面重试；新增 UI 策略回归。
- 2026-09-06 — 元数据状态可观测性改进：设置页不再把 `no_match` 与失败混为一谈，新增“暂未匹配（可稍后重试）”提示，provider 故障仍单独显示；补充 UI 静态回归。
- 2026-09-06 — 元数据恢复判定边界收紧：文件名候选恢复逻辑不再对异常 `status/source` 调用隐式 `String()`，仅接受有限文本并安全降级；新增 UI 策略回归，避免损坏 provider 响应放大“无法获取元数据”。
- 2026-09-06 — 首屏元数据恢复资格修复：可见行收到本地/文件名候选且带 `retryable`、`failed` 或 `no_match` 时，现在释放页级预取去重键；后续 worker/provider 状态修订可再次调度该歌曲，避免临时候选被误当成最终元数据。新增 UI 静态回归。
- 2026-09-06 — provider 超时边界修复：没有活动 job deadline 时不再强制使用默认 10 秒，MusicBrainz/封面等调用会遵循各自请求上限。
- 2026-09-06 — eager 封面重试不再清空 `src` 后再恢复，直接重试原地址，避免封面恢复过程出现额外空白帧。
- 2026-09-06 — 封面下载超时治理：`_download_artwork()` 继承当前 provider job 剩余预算，避免固定 15 秒请求拖慢歌词/元数据恢复队列。
- 2026-09-06 — 空成功投影恢复保护：修复历史 `auto/review` 空 JSON 时的 pending 早退分支，保留独立缓存中的合法 artwork 与歌词，避免元数据修复窗口出现封面闪烁或空白。
- 2026-09-06 — 元数据独立缓存回投：`track_match()` 在匹配行缺失/过期时现在读取 `metadata_tracks` 中已缓存的歌词与合法 artwork ID，并随 pending 本地候选一并返回；修复 worker 重启或候选链无匹配期间封面/歌词暂时消失的问题。新增 MetadataService 回归；100,000 首离线基准保持有界。
- 2026-09-05 — 首屏 eager 封面恢复：浏览器直加载的前 8 张封面失败后会进行一次有界重试，失败期间保留统一音乐符号，成功后恢复显示。
- 2026-09-05 — 封面回投修复：新增 `selectDisplayArtwork()`，从完整候选集合独立选择封面 URL；本地 Tag 候选字段完整时仍可显示远端封面，不改变匹配确认或 Tag 写回。
- 2026-09-05 — 首屏元数据可靠性：`visible_metadata_prefetch_policy.shouldRetry()` 现在对 null/空响应执行有限重试，覆盖临时 HTTP/代理/解码故障；不改变取消、重试上限或后台补全默认关闭策略。
- 2026-09-05 — 元数据终态回退修复：provider `no_match/failed` 不再用文件名候选遮蔽已有本地 Tag；无 Tag 文件仍保留文件名提示，新增服务回归。
- 2026-09-05 — 离线门禁收尾：同步首屏页大小策略测试（桌面默认 96 首），重新生成 `SOURCE_MANIFEST.sha256`；`test_offline.ps1` 通过 1090 项 Python 测试及全部 Node/UI 回归。补充 provider 本地 smoke 证据，仅用于确认查询链路可达，不替代真实部署验收。
- 2026-09-05 — 持续目标治理：首屏加载/闪烁、元数据按需获取可靠性、资源上限/可观测性、大曲库查询与核心模块可测试边界继续自动推进，明确排除真实设备和 App Center 验收。
- 2026-09-05 — 修复损坏 artwork ID 阻断补全：首屏策略只认可 64 位十六进制内容寻址 ID，异常历史引用会重新触发元数据/封面恢复；离线门禁 1087 项通过。
- 2026-09-05 — 分页策略模块化：新增 `library_page_size_policy.js`，从 `app.js` 拆出移动/桌面默认页大小、用户偏好读取和上限校验；完整离线门禁通过。
- 2026-09-05 — 移动端首屏分页优化：未保存过分页偏好的移动视口默认请求 60 首，桌面保持 120 首；已有用户设置优先，避免升级后改变用户习惯。
- 2026-09-05 — 大曲库策略模块化后复测：100,000 首曲库首/中/尾页约 53.2/111.6/174.8ms，热页约 60.5 倍，metadata overlay 约 3.1 倍，FTS5 相对 LIKE 约 18.5 倍；证据归档于 `artifacts/large-library-benchmark-20260905-final-policy.json`。
- 2026-09-05 — 元数据缺失策略模块化：`needsMetadata()` 统一首屏可见行与恢复当前曲目的补全判断，避免入口语义漂移；新增 Node 回归并通过 1087 项离线门禁。
- 2026-09-05 — 恢复队列当前曲目元数据优先级：首屏提交后使用统一候选缺失策略决定是否启动优先补全，覆盖标题/专辑/歌手/封面缺失和占位标签；离线门禁 1087 项通过。
- 2026-09-05 — 元数据 worker 状态边界：新增 `metadata_job_policy.worker_status()`，安全投影 provider 结果、歌词链初始故障和 artwork fallback；malformed payload 不会伪装成成功空结果。MetadataService 专项 83 项通过。
- 2026-09-05 — artwork 缓存响应安全边界：仅 `metadata/artwork/<64 位小写 SHA-256>` 可被视为可用缓存，历史异常路径不会绕过 worker 恢复或掩盖元数据重试。
- 2026-09-05 — 元数据缓存封面边界：`has_cached_track_projection()` 现在认可独立的 `metadata/artwork/<sha256>` 投影，即使历史候选 JSON 稀疏也会直接返回缓存，避免 worker 恢复期间封面短暂消失。
- 2026-09-05 — 当前曲目封面恢复：`track_match` 使用同一 SQLite 查询投影 `metadata_tracks.artwork_id`，在 auto/confirmed 候选响应中返回 `metadata/artwork/*`，避免恢复队列时丢失已缓存封面。
- 2026-09-05 — 元数据 pending 合并策略模块化：新增 `merge_pending_projection()` 纯函数，保留 provider 字段优先级并合并本地标题/专辑/封面/歌词；服务端 HTTP 路由不再内嵌合并细节，新增回归覆盖输入不变性。
- 2026-09-05 — 封面负缓存探测优化：对已确认的 `.none` 标记使用 4096 项正向 LRU，避免同一媒体版本在每次列表重绘重复 `stat()`；不缓存否定结果，保留并发预热和版本失效语义。
- 2026-09-05 — 元数据 pending 展示保护后大曲库复测：100,000 首合成曲库首/中/尾页约 63.5/117.7/198.5ms，热页缓存约 70.9 倍，metadata overlay 约 3.0 倍，FTS5 相对 LIKE 约 14.9 倍；证据归档于 `artifacts/large-library-benchmark-20260905-metadata-pending.json`，仅作离线趋势证据。
- 2026-09-05 — 首屏回填竞态：metadata 合并渲染捕获请求、视图、分页与页面数组身份；用户切换期间旧批次会被丢弃，不再对新页面执行一次无关渲染。
- 2026-09-05 — 歌词界面生命周期：关闭歌词页会取消该页面的轮询和 in-flight 请求、使旧 token 失效；播放层的歌词/封面优先预取不受影响。
- 2026-09-05 — 首屏元数据可观测性：`metadataPrefetchNoMatches` 仅统计正常 `no_match`；provider 终态失败、网络与解析错误统一计入 failures，避免把数据源故障误判为普通无匹配。
- 2026-09-05 — 大曲库性能复测：100,000 首合成曲库首/中/尾页约 52.4/102.2/155.5ms，分页热缓存 51.5 倍、metadata overlay 2.7 倍、FTS5 相对 LIKE 19.3 倍；结果归档于 `artifacts/large-library-benchmark-20260905-followup.json`，仅作离线趋势证据。
- 2026-09-05 — 元数据候选输入边界进一步收紧：候选有效性改用白名单字段读取，移除 `Object.keys()`/`ownKeys` 依赖；异常 Proxy 和无展示字段候选均安全降级。
- 2026-09-05 — 可见行元数据候选策略统一：列表回填与当前歌曲优先 lane 均通过完整度优先策略选择候选，不再让稀疏 `best` 遮蔽含封面的结果；异常 `ownKeys` 对象被安全隔离，UI 回归通过。
- 2026-09-05 — 元数据展示输入隔离：候选完整度和置信度计算不再任意字符串化 provider 字段，异常 getter、对象型值和非法分数均安全降级，避免坏响应阻断当前歌曲展示。
- 2026-09-05 — 元数据候选空值语义：展示候选策略将“无候选”显式返回 `null`，避免空对象误导当前歌曲预取的恢复分支，确保 pending/no-match 仍按既有有界策略重试。
- 2026-09-05 — 元数据候选展示去歧：新增纯展示策略，当前播放和候选对话优先采用字段更完整、含封面的候选；不改变服务端自动匹配或 Tag 写回安全阈值，避免“已获取但界面仍空白”。
- 2026-09-05 — 可见预取去重 FIFO：达到 256 项上限时仅淘汰最旧键，保留近期页面请求记忆，避免长会话整体清空后反复抓取同一歌曲元数据。
- 2026-09-05 — 当前歌曲元数据生命周期：优先曲目和歌词请求各自绑定 AbortController，切歌时中止旧请求并保留 token 防旧结果回写，降低慢 provider 对新歌曲首屏与歌词响应的争用。
- 2026-09-05 — 元数据 overlay 并发一致性：track-page 缓存键加入可见 projection revision；正常失效之外再提供 revision 隔离，防止扫描或 provider 提交与分页查询重叠时复用旧封面/字段。
- 2026-09-05 — 首屏元数据请求取消：可见行预取将页面生命周期 AbortSignal 传入请求并清理外部 abort 监听器，切换页面不再留下继续占用连接的旧 provider 请求；专项 UI 回归与完整离线门禁通过。
- 2026-09-05 — 元数据候选持久化边界：将 provider 候选置信度规范化抽为纯策略，持久化前限定条数、复制对象并将布尔/NaN/无穷/异常 score 收敛为 0；新增专项回归，避免坏 provider payload 让元数据缓存或列表投影不稳定。
- 2026-09-05 — UI 指标安全投影与元数据 worker 恢复竞态：交互查询确保 fetch worker 存活；新增脱敏有界 UI 指标快照与 Node 回归。真实设备验收仍排除。
- 2026-09-05 — 首屏元数据修订去重：后台任意歌曲的全局 metadata revision 不再触发当前页重新请求和整页渲染；改为仅失效未来分页缓存，避免首屏歌曲列表与封面在加载完成后再次闪烁。
- 2026-09-05 — 首屏刷新路径收敛：移除旧 metadata 全页刷新定时器与取消分支，缓存失效不再保留可误触发的整页重载入口。
- 2026-09-05 — 首屏元数据请求去重：普通可见行预取排除当前播放歌曲，避免与优先歌词/封面通道重复请求。
- 2026-09-05 — 元数据请求超时边界：当前歌曲的元数据和歌词优先请求增加 10 秒 AbortError 超时，继续使用既有有界重试与切歌 token 隔离。
- 2026-09-05 — 首屏歌词载荷收敛：普通歌曲列表元数据叠加默认移除完整 LRC；歌词专用调用可显式启用正文，减少首屏响应与 WebView 解析负担。
- 2026-09-05 — 歌词 worker 恢复：歌词优先接口在已启动 worker 死亡时主动恢复对应 lane，避免 pending 任务无人领取；新增服务回归。
- 2026-09-05 — 可见元数据超时统一：首屏普通歌曲预取增加 8 秒请求上限，慢代理不会占满双并发槽；页面取消和有限重试保持原语义。
- 2026-09-05 — 歌词冷却恢复竞态：失败或无匹配进入自动 retryable pending 时主动恢复 worker，避免任务状态已恢复但没有线程领取。
- 2026-09-05 — 大曲库离线复测：100,000 首合成数据的首/中/尾页、热缓存、元数据叠加、分类浏览和 FTS 搜索均保持有界；结果归档于 `artifacts/large-library-benchmark-20260905-final.json`。

## 2026-09-05 — 元数据轮询公平性与诊断容量

- 修复首屏可见元数据预取对 `pending` 状态持续附带 `retry=1` 的问题：仅终态 `failed/no_match` 才请求一次显式恢复，慢 provider 查询不再被前端轮询反复重置。
- 活动 metadata/lyrics job 的重复轮询保留 FIFO、退避和尝试次数，只允许提升优先级，降低多歌曲排队时的饥饿风险。
- provider 成功、失败和冷却诊断状态增加 32 项内部上限；新增服务/UI 离线回归覆盖。
- 当前播放歌曲的高优先级元数据通道同步改为“pending 普通轮询、终态失败才显式 retry”，修复慢 provider 被 900ms 轮询反复重排导致看似无法获取元数据的问题。
- 终态 `retry=1` 标记改为一次性消费；显式恢复仍无匹配时不再连续强制重排同一任务。
- 歌词优先预取同步采用一次性终态恢复，pending 查询不再反复发送 `retry=1`。

## 2026-09-04 — 歌词编码回退与封面字段隔离

- 歌词含替换字符时不再立即中断字符集尝试，允许 GB18030/Big5 等后备编码正常解出有效 LRC。
- 候选封面 URL 新增损坏文本过滤，避免乱码地址污染 artwork 缓存或阻断后备 provider。

## 2026-09-05 — 歌词乱码回退

- 歌词解码及 adapter 回投统一拒绝含 Unicode 替换字符的损坏文本，避免将乱码当作成功歌词落库。
- 损坏 provider 会被隔离记录，后备歌词源仍继续尝试；新增解码与回退回归。

## 2026-09-05 — 大曲库元数据叠加基准

- 大曲库基准新增 track-page overlay 热/冷耗时、speedup、缓存命中/未命中及边界指标。
- 10,000 首离线样本中元数据叠加热读约 2.75 倍加速；仅用于离线趋势比较，不代表真实设备验收。

## 2026-09-05 — provider 乱码候选降级

- 元数据候选增加 Unicode 替换字符检测。第三方接口返回已损坏的中文文本时，该候选不会参与匹配或覆盖展示，后备源仍可在同一有界任务内完成查询。
- QQ 只读搜索样例已复现该类响应；新增 payload 与服务候选回归，确认损坏 QQ 候选自动让位给有效 Kugou 候选。

## 2026-09-05 — review 候选不触发列表刷新

- 将 track-match 的投影比较收紧到普通列表真正使用的 `auto/confirmed` 字段；provider 产生或替换 review 候选时不再递增可见投影版本，也不会触发整页重载和封面重新调度。
- 自动匹配转为 review 时仍会正确清除旧的可见投影；新增服务端策略回归。

## 2026-09-05 — 元数据叠加缓存失效收敛

- 入队、重试、运行和失败等非投影状态变化不再清除 track-page overlay 缓存；只有可见元数据提交才触发缓存失效，减少大曲库后台补全期间的重复 SQL 合并。
- 增加服务端离线回归，确认队列 churn 保留缓存、投影变更仍会清空缓存。

## 2026-09-05 — 元数据离页刷新去噪

- 前端元数据投影签名移除通用终态更新时间字段，改为只观察服务端 `metadata_projection_revision`。离页歌曲的后台任务完成不会再无意义地清空/重载当前列表，也不会重新触发封面调度。
- 增加 UI 策略回归，验证时间戳变化保持签名稳定；本轮仍仅进行离线验证。

## 2026-09-05 — 首屏封面空白帧与 provider 结构漂移恢复

- 歌曲行的封面占位符统一持续显示到图片 `onload`；首批 eager 封面不再在解码前预先隐藏占位，减少慢 WebView 上的短暂空白与列表闪烁。
- 元数据曲目候选新增独立的 payload 形状判定。provider 返回对象型错误或 schema drift 时，当前源会记为可恢复失败，后备源仍在同一有界任务内继续查询，避免错误落成长期 `no_match`。
- 新增 MetadataService 与 UI 静态回归；本轮未进行真实设备、DAC/DSD/DLNA/AirPlay、fnOS App Center 或 Android 多机型验收。

## 2026-09-04 — 首屏元数据按需预取

- 首屏权威列表绘制完成后，针对最多 6 首缺少封面、专辑或歌手的歌曲启动两路并发的按需元数据查询；结果仅更新前端展示缓存，不改变 Tag 写回开关。
- 页面切换、请求序列变化或 WebView 隐藏时取消旧预取，避免慢 provider 返回后污染新页面，也避免与首屏布局竞争。
- 对 `pending/retryable` 响应增加每曲最多 4 次、450ms 间隔的短轮询，使慢 provider 完成后能自动回投到当前列表。
- 首屏预取去重键集合限制为 256 项，跨大量页面切换时自动淘汰旧键，避免长会话内存持续增长。
- 首屏预取的候选筛选与 pending 重试判定抽为 `visible_metadata_prefetch_policy.js` 纯策略模块，并增加独立 UI 契约回归。
- 首屏预取新增共享 `AbortController`，页面切换/隐藏时中止进行中的 provider 请求，降低旧任务对新首屏的资源竞争。
- `__fnAudioUiMetrics` 新增首屏元数据预取请求/成功/失败计数，并使用有界计数器，便于离线证据区分 provider 未命中与前端合并问题。
- 修正元数据终态：仅有文件名展示候选且远端 provider 失败时不再记为成功，保留 `failed/retryable` 以便后续恢复。

## 2026-09-04 — 元数据不可用时的本地身份回投

- `track_match` 在首次排队或 provider 暂不可用时返回受限的文件名候选（来源 `filename`，置信度 0.56），让当前歌曲仍能显示基本身份。
- 候选仅用于展示和后续匹配，不会覆盖原始 Tag，也不会触发自动写回；新增 MetadataService 离线回归。

## 2026-09-04 — 负缓存期间保持本地身份

- 历史 `failed/no_match` 元数据记录在等待冷却或用户重试时，继续返回文件名解析的低置信度候选，避免旧负缓存造成当前歌曲标题/歌手空白。
- 新增负缓存回归，确认 `retryable` 语义和后续 provider 恢复路径保持不变。

## 2026-09-04 — pending 临时候选继续远端恢复

- 前端现在区分“有候选”与“已完成”：文件名临时候选伴随 `pending` 返回时会先更新显示，同时继续执行有界 provider 重试。
- 避免首屏先显示本地身份后误停止元数据获取；新增逻辑通过现有 UI 离线回归链路验证。

## 2026-09-04 — retryable 负缓存候选恢复

- 历史 `failed/no_match` 返回的文件名候选带有 `retryable` 标记时，前端现在先显示本地身份，同时继续执行有界 provider 重试。
- 防止负缓存恢复路径因已有候选而过早结束；不改变 Tag 写回和置信度策略。

## 2026-09-04 — 空元数据响应边界收紧

- `has_cached_track_projection` 现在要求存在实际 `best` 或候选字段；空失败和空 review 不再被误判为可用缓存。
- 这类响应会继续经过 worker 恢复/重试路径，避免元数据链路静默停滞。

## 2026-09-04 — 文件名候选字段收紧

- 文件名兜底只提供标题和录音歌手，不再把歌手复制到 `album_artist`。
- 避免低置信度本地猜测污染专辑聚合和后续 provider 消歧。

## 2026-09-04 — 首屏时间指标

- `__fnAudioUiMetrics` 新增首次列表 DOM 提交和首次封面 hydration 的有界毫秒计数。
- 指标仅用于诊断与离线趋势比较，不改变列表加载、封面调度或首屏渲染路径。

## 2026-09-04 — 文件名候选策略拆分

- 将文件名元数据候选构造从 `MetadataService` 下沉到 `metadata_query_policy.py`，保持纯函数、字段有界和低置信度语义。
- 服务层继续只负责队列、缓存和 provider 编排，新增策略回归覆盖专辑字段不被猜测。

## 2026-09-04 — 100k 曲库最终离线基准

- 首/中/尾页查询约 53.7/104.9/166.7ms，热页缓存约 62.4 倍，FTS5 trigram 相对 LIKE 约 17.8 倍。
- 结果归档于 `artifacts/large-library-benchmark-20260904-final.json`，仅代表离线趋势，不替代真实 NAS/WebView 验收。

## 2026-09-04 — 封面预热减少首屏 stat I/O

- 封面缓存版本优先复用扫描索引提供的 `modified_ns` 与 `size`，仅在字段缺失时回退文件系统 `stat`。
- 新增回归确保慢存储页面预热不会为每个可见行重复探测文件身份。

## 2026-09-04 — 元数据文件名本地兜底

- 新增 `filename_track_hint` 纯策略：从“歌手 - 歌名”或无 Tag 文件名生成低置信度候选。
- provider 全部失败/冷却时仍能保留可用的本地曲目身份；候选不会覆盖已有 Tag，也不会自动写回。
- 新增元数据回归，完整离线门禁待本轮脚本执行后记录。

## 2026-09-04 — 首屏渲染可观测计数

- UI 新增有界会话计数 `__fnAudioUiMetrics`，记录 render、列表 DOM 提交和封面 hydration 次数。
- 计数只用于离线/部署诊断，不改变现有渲染路径；新增静态回归保护上限。

## 2026-09-03 — pending 歌词请求的封面即时回投

- 修复歌词请求处于 pending 时忽略服务端缓存封面的顺序问题；现在先应用封面，再显示“正在获取歌词”。
- 仅回填缺失封面，不覆盖本地 Tag；新增 UI 回归并通过完整离线门禁（1144 项 Python 测试及全部 Node/UI 回归）。

## 2026-09-04 — 首屏空帧与元数据持续优化

- 列表在已有快照/可见行且权威请求加载中时不再提交瞬时空列表，降低旧 WebView 的首屏闪烁和封面重绘。
- 保持元数据后台补全默认关闭；当前歌曲按需获取继续使用 worker 懒恢复、旧负缓存恢复和 provider 失败隔离。
- 已运行源码清单更新与完整离线门禁：1144 项 Python 测试及全部 Node/UI 回归通过；未覆盖真实设备、DAC、DSD、DLNA、AirPlay 或 App Center 验收。

## 2026-09-04 — 元数据缓存优先响应（持续目标）

- `/api/metadata/track` 先返回已有 SQLite 投影，再检查 worker 可用性，避免 worker 短暂重启造成已获取元数据被误报为空。
- 新增 HTTP 集成回归锁定该顺序；完整离线门禁 1136 项通过。

## 2026-09-04 — 歌词缓存优先响应（持续目标）

- `/api/lyrics` 先返回本地嵌入/同名歌词和 SQLite 缓存，仅 pending 的外部查询才检查 worker；新增集成回归，完整离线门禁通过。

## 2026-09-04 — 稳定顺序键控提交（持续目标）

- 列表行顺序和数量未变化时，键控提交不再先移除节点到 `DocumentFragment`，避免旧 WebView 出现瞬时空列表和封面闪烁。
- 新增 UI 静态回归保护该边界。

## 2026-09-04 — 元数据响应策略边界（持续目标）

- 抽离曲目/歌词缓存与 pending 判定至 `metadata_response_policy.py`，新增纯策略回归，保持缓存优先和 worker 门禁语义不变。

## 2026-09-04 — 权威分页退休启动快照（持续目标）

- 权威分页提交后清除 bootstrap snapshot 命中标记，避免旧快照长期触发空响应保护；新增 UI 回归保护该生命周期。

## 持续优化 — 首屏封面请求优先级

- 前 8 张封面保持 `high`，非首屏封面使用 `low`，继续配合懒加载调度，降低大曲库首屏资源竞争。

## 持续优化 — 启动快照输入边界

- 恢复本地列表快照前按当前页大小裁剪条目，避免异常 localStorage 数据放大首屏 DOM 工作；新增 UI 静态回归。
- 同时过滤非对象和无稳定 ID 的条目，避免损坏快照进入歌曲行渲染。

## 持续治理 — 0.2.33 legacy 证据隔离

- 新增 `artifacts/0.2.33/LEGACY_EVIDENCE.md`，记录主 FPK 与 scratch provenance 哈希不一致，防止恢复时跨构建误配；不伪造完整历史 provenance。

## 持续治理 — 元数据重试预算文档同步

- 将 TODO 中当前歌曲预取的有界重试说明从 8 次修正为实现中的 12 次，保持文档与代码一致。

## 2026-09-04 — 元数据回投绘制合并

- 歌词和候选元数据回投共享按曲目隔离的动画帧，避免同一首歌连续触发列表重绘；切歌会取消旧曲目待绘制帧。
- 完整离线门禁通过：1136 项测试；真实设备、DAC、DLNA、AirPlay 与 App Center 验收仍未纳入本轮。

## 2026-09-04 — hydration 生命周期竞态修复

- 取消旧视图 hydration 时同步取消待执行动画帧，避免新页面数据已进入缓存但 render slot 被旧回调占用。
- 完整离线门禁通过：1136 项测试；真实设备、DAC、DLNA、AirPlay 和 App Center 验收仍按范围排除。

## 2026-09-04 — 100k 大曲库性能基线复测

- 归档当前离线基线：首屏/中页/尾页约 53.5/111.1/160.4ms，重复页缓存约 61.8 倍，ID hydration 热路径约 7.1 倍，FTS5 trigram 相对 LIKE 约 19.3 倍。
- 该结果用于发布治理和回归趋势，不代表真实 WebView 或部署环境的最终体验。

## 2026-09-04 — provider 请求统一身份

- 元数据 JSON 与歌词请求公共层补齐默认浏览器 `User-Agent`，避免适配器漏传身份造成公共音乐源返回空结果；来源专用 header 不受影响。
- provider 请求专项回归和完整离线门禁均通过（1136 项）；未进行真实设备或全量外部数据源验收。

## 2026-09-04 — 引用曲目 hydration 重绘合并

- 收藏/歌单分批请求完成后的列表重绘合并到单个动画帧，降低大列表加载后的重复布局、封面调度和闪烁。
- 完整离线门禁通过：1136 项测试；本轮未进行真实设备、DAC、DSD、DLNA、AirPlay 或 App Center 验收。
- 元数据受限 smoke：QQ 曲目封面与组合回退链路可返回结果；provider 的长期可用性仍由部署日志和后续状态观察确认。

## 2026-09-03 — 发布证据索引编码稳定性

- 发布证据索引对验证失败条目使用 ASCII 稳定文本，避免不同 PowerShell 主机编码把恢复说明写成乱码；重新生成最新索引并验证 0.2.34 完整证据。

## 2026-09-03 — Kugou 元数据请求默认使用 HTTPS

- 搜索、歌词检索和歌词下载从明文 HTTP 切换到 HTTPS，避免 NAS 代理或网络策略拦截重定向导致数据源看似不可用；新增源码契约回归。

## 2026-09-03 — 列表行更新复用已解码封面

- 元数据回投或播放状态导致行结构变化时，若封面 URL 未变，直接移动当前 DOM 图片节点（而非仅复制 `src`），保留已解码位图和进行中的请求，降低旧 WebView 的封面闪烁。

## 2026-09-03 — 摘要缓存文件指纹校验

- 状态摘要缓存增加 SQLite `mtime/size` 指纹，兼容外部重建数据库场景并保持短 TTL 性能收益。

## 2026-09-03 — 摘要缓存更新键超限收敛

- 修复更新已有数据库键时可能绕过摘要缓存上限的极端路径，所有写入均先收敛历史超限条目。

## 2026-09-03 — 摘要缓存历史超限收敛

- 摘要缓存插入改为循环淘汰，兼容历史超限状态并严格恢复到 32 项上限。

## 2026-09-03 — 当前歌曲页面缓存定向失效

- 播放优先元数据更新后定向淘汰包含该曲目的页面响应，避免封面/歌词等待页面缓存 TTL，同时不影响其它热页。

## 2026-09-03 — 当前歌曲元数据缓存回投

- 播放优先元数据补全成功后同步更新有界条目缓存，保证不在当前页的恢复队列歌曲跨视图仍保持最新封面与字段。

## 2026-09-03 — library 摘要缓存资源上限

- 为 SQLite 状态摘要缓存增加 32 项数据库路径上限，按最旧插入项淘汰，收敛长期运行时的内存增长。

## 2026-09-03 — library status 摘要短缓存

- 为曲目数/DSD 数/签名增加独立短 TTL SQLite 摘要缓存，动态扫描状态仍实时读取，写入后立即失效。
- 增加索引写入后的失效回归，确认新扫描结果不会被旧摘要保留。

## 2026-09-03 — Artwork 重复下载收敛

- 已有曲目 artwork 时在 `_store_track_artwork` 下载前短路，避免重复获取和解码同一封面。

## 2026-09-03 — 后续候选封面独立落库

- 修复曲目匹配只使用最佳候选封面的缺口；当最佳候选缺封面时，从后续候选选择可用 artwork 写入缓存，避免“元数据已匹配但列表无封面”。

## 2026-09-03 — 过期分页响应加载保护

- 修复旧分页响应先清理 `libraryLoading` 再检查序号的竞态；快速切换视图或搜索时不会再提前显示空状态。

## 2026-09-03 — 元数据来源标记回退

- 修复分页合并把空 `metadata_source` 当作有效来源的问题，避免缓存元数据回投后影响 Tag 优先级判断。

## 2026-09-03 — 页面元数据合并策略模块化

- 将分页元数据合并逻辑抽为纯策略模块，统一复用上一页和有界条目缓存，并锁定“仅补空、不覆盖权威值”的回归边界。

## 2026-09-03 — 跨视图元数据缓存合并

- 分页权威响应缺字段时，现在还会从有界 `itemCache` 恢复已获取的元数据，减少切换视图后的封面闪烁和信息回空；显式服务端值保持优先。

## 2026-09-03 — 页面元数据合并性能复测

- 重新运行 100,000 首曲库基准，确认会话元数据合并不会拖慢分页、热缓存或 FTS5 搜索；证据归档于 `artifacts/large-library-benchmark-20260903-merge.json`。

## 2026-09-03 — 权威分页元数据合并边界

- 列表权威响应现在只在字段为空时保留当前会话已获取的标题、歌手、专辑、歌词、封面和补全字段，避免元数据回投后被短暂空分页覆盖造成闪烁；显式服务端值保持最高优先级。

## 2026-09-03 — 曲目页投影缓存基础字段指纹

- 投影缓存键纳入受限的曲目基础字段与封面 URL 指纹，扫描刷新后不会对相同 ID 复用旧元数据投影。

## 2026-09-03 — 曲目页投影缓存可观测性

- 元数据状态增加曲目页投影缓存压力指标（命中、未命中、条目数、上限、TTL），保持所有计数有界。

## 2026-09-03 — 元数据 worker 重启可观测性

- 元数据状态新增 `worker_restarts` 计数，记录异常池的懒恢复次数并限制最大值。

## 2026-09-03 — 曲目页投影缓存 TTL 一致性

- 增加过期回归，确认投影缓存只在短 TTL 内复用，过期后重新读取最新元数据。

## 2026-09-03 — 曲目页元数据投影缓存

- 曲目分页的歌词/Artwork/候选字段 JOIN 增加短 TTL 有界缓存，降低重复 SQLite 往返。
- 缓存受元数据状态失效控制并返回隔离副本，保持数据一致性。

## 2026-09-03 — 元数据页面校正取消边界

- 视图切换会取消未执行的元数据分页校正，并清理请求键，防止旧页面额外刷新。

## 2026-09-03 — 空 metadata lane 状态修正

- 收紧 worker lane 判定：空抓取池和无优先线程的 lyrics lane 均视为不可用。
- 避免启动失败被伪装为 pending，保留既有懒恢复和结构化 503 语义。

## 2026-09-03 — 元数据 lane 策略模块化

- 将 worker lane 存活判断与服务启动历史判断抽为纯策略模块，保留懒恢复语义。
- 增加未启动、死线程和歌词优先线程的独立回归测试。

## 2026-09-03 — 状态采样恢复元数据服务

- 元数据状态接口在发现已启动但已退出的 worker 池时执行一次受限恢复，前端轮询可自动观察到恢复结果。
- 健康检查不会启动从未启动过的服务，避免改变原有生命周期语义。

## 2026-09-03 — 元数据完成事件合并

- 将元数据状态引起的列表校正改为短空闲窗口合并，避免多个任务完成时连续刷新整页。
- 定时器绑定当前分页请求键，视图切换后自动丢弃过期校正。

## 2026-09-03 — 当前歌曲元数据恢复重武装

- 元数据状态确认 worker 恢复后，当前歌曲预取会从不可用终态重新入队一次。
- 触发按曲目去重，保持原有 8 次重试、服务端预算和后台补全默认关闭。

## 2026-09-03 — 元数据服务故障协议

- 单曲元数据接口在服务未启动或抓取 worker 全部退出时返回结构化 HTTP 503，并携带 `status: unavailable`。
- 前端候选对话框显示明确的服务不可用提示；播放预取不再把该状态当成候选为空，也不会继续无效重试。

## 2026-09-03 — 元数据读取权限修正

- 单曲候选与元数据状态等只读接口改用 `library.read`；刷新、候选确认和 Tag 写回仍使用 `settings.write`。
- 修复部分移动/远程播放会话只有音乐库权限时无法获取歌词、封面和候选元数据的问题。

## 2026-09-03 — 播放即触发单曲元数据预取

- 播放本机、当前设备或远程目标时立即请求当前曲目候选元数据，不再要求用户先打开歌词/候选对话框。
- 预取请求使用 `no-store`，按曲目去重并校验请求令牌；pending 时最多追加 8 次有界轮询并在候选完成后增量回投，不阻塞播放，后台补全默认关闭语义保持不变。

## 2026-09-03 — 首屏封面请求优先级

- 首批 8 张歌曲封面增加受限 `fetchpriority=high`，配合现有 eager burst 改善首屏封面到达速度；并发、取消、FIFO 与后续懒加载策略不变。

## 2026-09-03 — 首屏扫描状态防闪烁

- 扫描状态轮询先于首个歌曲分页响应到达时，不再把首屏加载态提前结束；旧 WebView 不会在临时空列表阶段闪现“没有音乐”。
- 已有快照的稳定呈现和扫描完成后的权威分页提交语义保持不变。

## 2026-09-03 — 元数据状态聚合容错

- 状态页的任务/匹配计数、缓存 Artwork 占用和实体/歌词数量统一使用非负数与有界文本投影，避免异常历史值阻断可观测性；短 TTL 聚合缓存和首屏路径保持不变。

## 2026-09-03 — 元数据任务重试计数容错

- worker 异常处理读取任务 `attempts` 时改用非负有界投影，损坏任务行不会触发二次转换异常；有限重试上限和失败诊断保持不变。

## 2026-09-03 — 元数据缓存过期时间读取统一

- reconcile、实体缓存、当前歌曲优先元数据和专辑封面刷新路径统一复用 `bounded_epoch()`；非法、负数或非有限过期时间按已过期处理，避免历史损坏缓存抛出异常或阻断元数据重新获取。
- 保持后台元数据默认关闭、当前歌曲按需优先和 provider 失败可重试语义不变；本轮仅进行离线回归，不进行真实设备验收。

## 2026-09-02 — 元数据 worker 状态策略模块化

- 将任务最终状态（成功、跳过、无匹配、provider 失败）和有限重试判定抽至纯模块 `metadata_job_policy.py`，worker 编排保持原有语义。
- 新增独立回归，完整离线门禁继续覆盖线程失败恢复路径。

## 2026-09-02 — 元数据缓存读取容错

- 缓存中的置信度和过期时间统一经过有限数值投影；损坏的历史记录会安全回退，不再让专辑或曲目元数据接口整体失败。

## 2026-09-03 — 当前歌曲专辑任务优先

- 后台元数据补全关闭时，受限优先 worker 现在同时处理播放/歌词页产生的 track 与 album 任务；当前歌曲的专辑信息和封面不再因 `track_only` 过滤而长期停留在 pending。
- 仍保留优先级上限与有限队列边界，不开启全库后台抓取。

## 2026-09-03 — 100k 曲库性能基准复测

- 重新生成 100,000 首曲库证据：首屏分页约 52 ms、尾页约 171 ms、热页缓存约 60.1 倍、FTS5 trigram 搜索相对 LIKE 约 17.3 倍。
- 证据归档于 `artifacts/large-library-benchmark-20260903-latest.json`，用于持续离线趋势比较。

## 2026-09-03 — 歌词失败时的封面回退

- 当歌词 provider 全部失败或无匹配时，元数据 worker 仍执行一次受预算约束的曲目封面/候选回退；已有歌词结果不会触发额外网络扇出。
- Provider 失败仍保持可观测和可重试；成功取得封面时任务正常完成。

## 2026-09-03 — 首屏封面加载策略收敛

- 首屏前 8 张封面改为 `loading=eager` 并保留 `fetchpriority=high`；其余封面继续由调度器按可见区域懒加载，避免全库图片同时启动。

## 2026-09-03 — 首屏封面直接启动请求

- 首屏前 8 张封面现在同时写入 `src`，不再仅等待封面调度器赋值；其余图片仍由调度器延迟启动，首屏并发和队列上限不变。

## 2026-09-03 — 大曲库性能趋势复测

- 100,000 首曲库复测结果：首屏约 57 ms、尾页约 179 ms、热页缓存约 61.5 倍、FTS5 trigram 搜索约为 LIKE 的 17.5 倍。
- 证据归档于 `artifacts/large-library-benchmark-20260903-final.json`。

## 2026-09-03 — 首屏资源让位状态收敛

- 将冷启动恢复队列让位首屏的已实现策略标记为离线验收项：首个权威分页提交后才开始批量引用补水，减少首屏竞争。

## 2026-09-02 — 元数据不可用状态与首屏体验收敛

- 歌词请求区分后台元数据服务不可用（HTTP 503/`unavailable`）与普通 provider 无匹配；前端展示受限错误原因并停止无效轮询，重新打开歌词页即可显式重试。
- 保留首屏本地快照、稳定行提交和有限封面调度策略，继续针对大曲库冷启动空白与二次闪烁做离线回归观察。

## 2026-09-02 — 无 Tag 文件名检索增强

- 当标题和歌手均为占位值时，查询回退会识别常见“歌手 - 歌名”文件名并拆分搜索词，提升元数据 provider 命中机会；不改写曲库 Tag 或页面展示。
- 标题 Tag 存在但歌手缺失时，也会在文件名右侧与标题一致的情况下补入文件名歌手提示，改善部分 Tag 歌曲的检索命中。
- 文件名回退现在兼容带空格和不带空格的连字符分隔格式。

## 2026-09-02 — provider 路由性能收敛

## 2026-09-02 — 播放会话恢复触发当前歌曲元数据

- 应用或浏览器重启恢复逻辑播放队列后，服务端立即提升当前曲目的歌词、封面和候选任务；即使后台全库补全关闭，也不必等待下一次播放命令才开始当前歌曲元数据获取。

## 2026-09-02 — 曲目封面回退字段安全投影

- 曲目候选回退中的封面 URL、来源和 provider ID 统一复用有界文本策略，异常对象只跳过自身，不会中断当前歌曲的其他来源回退。

- 曲目候选按标题语言调整 provider 顺序：中文曲目先走网易云、QQ、酷狗、咪咕、JOOX、千千，MusicBrainz 作为回退；国际曲目仍优先 MusicBrainz。
- 降低常见中文歌曲的首个外部请求等待，同时保留国际曲目广覆盖回退；总请求预算、失败隔离和候选评分保持不变。
- 修正 MusicBrainz `artist-credit` 嵌套投影并增加候选回归；完整离线门禁通过。

## 2026-09-02 — 元数据候选扇出提前收敛

- 当前歌曲的候选链在获得高置信且歌名、歌手、专辑、封面均完整的结果后提前停止整个后续 provider 扇出，减少串行等待。
- 稀疏、低置信或封面缺失候选仍继续走完整回退链；新增纯策略回归并保持总预算与失败隔离。

## 2026-09-02 — 歌词失败避免重复网络扇出

- 歌词 provider 链出现明确故障时，不再在同一任务内继续启动封面 provider 链，避免弱网环境重复等待并掩盖失败状态。
- 干净的歌词无匹配仍允许封面回退；失败状态继续进入原有 retry/diagnostics 流程。

## 2026-09-02 — MusicBrainz 曲目封面回退

- recording 候选现在从前 8 条有效发行版本中选择带有 `id/title` 的记录，并为带 `release.id` 的结果生成 Cover Art Archive `front-500` 封面地址。
- 修复“曲目候选已命中但没有封面资产”的离线链路缺口；不改变封面下载协议、资源上限或 Tag 优先级。

## 2026-09-02 — 首屏列表稳定渲染续优化

- 稳定歌曲列表的普通 `render()` 不再为播放/收藏状态重新遍历全部歌曲行以写入相同的选择样式；列表 DOM 真正变更时仍强制同步，保持选择状态正确。
- 播放列表导航使用稳定标记复用，歌曲列表中的工具栏/分组行事件仅在列表提交后重新绑定，减少大音乐库首绘后的 DOM 重建与事件遍历。
- 本轮继续保留元数据的 JOOX 候选回退、总请求预算和失败恢复策略；通过离线 UI/元数据回归，不进行真实设备或第三方网络验收。
- 稳定行键提交现在将签名更新与真实 DOM 替换分离：现有节点已具备相同展示时，不会误触发封面重新观察、列表选择同步与布局测量，进一步收敛首屏后的二次闪动。
- 收藏切换不再在普通歌曲页触发整页 `render()`；仅收藏歌曲视图重绘列表，其他视图局部更新计数和当前歌曲收藏状态。
- 补充元数据 worker 回归：后台全库补全默认关闭时，当前歌曲的 priority-0 歌词及 priority-1 候选/封面任务仍可被领取；普通 album/track 任务不会进入该受限通道。
- 元数据 provider 临时失败现在会在设置页显示有界错误摘要，并进入支持诊断快照；次数、冷却时间和错误文本均复用既有脱敏/上限策略，避免把无匹配误诊为服务不可用。
- 大曲库歌曲行渲染现在每页只计算一次列配置，再复用于所有行；避免首屏 120 首歌曲重复进行相同的列作用域/偏好解析，列显示和单行调用兼容语义保持不变。
- 同一歌曲的多个非标题列现一次性完成格式化并复用结果，避免艺术家、专辑、时长、音质等列各自重复构建格式化上下文；保留单列调用兼容路径。
- 非队列歌曲页现按数组身份和列配置缓存已生成的行 HTML，播放器位置、状态栏等普通刷新不再重复序列化整页歌曲；队列页仍实时生成播放标识，异步补到当前歌曲封面时会主动使缓存失效。
- 修复 provider 冷却期的误判：源被临时冷却跳过时，本轮任务标记为搜索未完成并保留可重试失败，不再把“所有源暂时不可用”持久化为 `no_match`。
- 单任务 provider 请求预算耗尽或内部 deadline 异常时也统一标记为搜索未完成，避免后续源被门控跳过后错误生成负缓存。
- 抽取 `metadata_provider_availability_policy.py`，独立验证 provider 的冷却/预算可用性判定及异常时钟输入；元数据服务保留原有 worker 观察与诊断接线。
- provider 的有效空结果现也视为一次成功连接并清除旧失败累计，避免已经恢复的源因一次偶发失败立即重新冷却。

## 2026-09-02 — provider 候选字段边界拆分

- 新增 `metadata_track_candidate_policy.py`，统一安全投影第三方候选字段，拒绝任意对象字符串化并保留数字 provider ID 兼容性。
- `metadata_service.py` 的候选构建改为复用纯策略模块，新增异常输入回归；完整离线门禁通过。

## 2026-09-02 — 封面 URL 兼容性修复

- provider 返回协议相对封面 URL 时，候选策略与下载器统一补全为 HTTPS，修复“候选命中但封面未缓存”的链路。
- 新增协议相对 URL 回归；离线门禁 1062 项测试通过。

## 2026-09-02 — 封面下载输入安全边界

- `_download_artwork` 现在拒绝非文本 URL，避免异常 provider 对象的字符串转换导致任务失败。
- 新增异常 URL 回归；完整离线门禁通过。

## 2026-09-02 — 封面协议限制

- 封面下载仅允许 HTTP/HTTPS，拒绝 `file:` 等非网络协议，避免异常来源触发不可控读取。
- 新增非 HTTP scheme 回归；完整离线门禁 1064 项测试通过。

## 2026-09-01 — 封面可见队列保持列表顺序

- 封面调度器改为按优先级选择任务，而不是对优先任务头插。
- 同一批可见图片现在保持 FIFO/DOM 顺序，慢 WebView 中不会出现下方封面先于上方封面的逆序补图。
- 保留 4 路并发、队列容量和非可见图片的让位语义；新增顺序回归。

## 2026-09-01 — 大曲库元数据页叠加基准

- 大曲库离线基准新增歌曲页元数据叠加测量，覆盖一整页缓存歌词与已确认候选字段。
- 基准断言分页上限、重复投影一致性及嵌入 Tag 的优先级，防止仅原始曲库查询变快而元数据回投成为隐藏热点。
- 20k 合成曲库样本中，120 首页的元数据叠加约 4.5ms，未成为原始首屏页读约 16.4ms 的主导项；该数据仅作离线趋势证据。

## 2026-09-01 — 首屏引用曲目补水让位于首次绘制

- 歌曲页权威响应到达后，队列、收藏和歌单的引用曲目补水不再抢在首次列表渲染之前启动。
- 现在在空闲回调中开始补水；旧 WebView 使用 80ms 有界回退，新分页请求或视图切换会取消过期调度。
- 保留既有补水并发、顺序和 generation 防陈旧响应机制。

## 2026-09-01 — JOOX 歌词候选可用性回退

- 修复 JOOX 同名搜索首个高置信候选的 lyric_id 已失效时，整次歌词查询直接结束的问题。
- 现在只在最多 4 个高置信候选内顺序尝试；接口返回正常但 `code != 0` 或空歌词时继续下一个候选，网络/解码异常仍保留既有严格失败语义。
- 新增回归覆盖“首个 lyric_id 不存在、后续候选可用”的实际响应形态。

## 2026-09-01 — 首屏封面预热移出 HTTP 路径

- 分页歌曲页不再在返回前逐项探测封面缩略图缓存是否存在。
- 缓存命中判断改在后台预热 worker 内执行，保留既有 pending/inflight 去重、容量上限和命中跳过。
- 已通过封面缓存与预热队列专项回归。

## 2026-09-01 — 元数据评分异常输入隔离

- `normalize_text()` 不再对任意对象调用 `str()`，只接受文本输入。
- 候选标题为空时评分直接为零，避免仅凭歌手字段错误获得自动确认所需的高分。
- 已加入 provider 异常对象回归。

## 2026-09-01 — 首屏快照避免用户状态二次整页渲染

- 修复冷启动时本地歌曲页快照已显示、但用户状态接口更早返回时的重复 `render()`。
- 该时序现在只更新播放器、导航和控制状态；等待权威歌曲页返回后再进行唯一的列表提交，减少大曲库首屏与封面惰性解码的闪烁。
- 已通过音乐库加载、渲染与空响应策略专项回归；不改变无快照或常规状态刷新的渲染语义。

## 2026-09-01 — 简繁体候选匹配修复

- 修复本地简体 Tag 与 provider 繁体候选被严格评分误判为无匹配的问题。
- 新增纯模块 `metadata_han_variant.py`，内嵌有界的繁体到简体字符折叠表，仅生成匹配键；歌曲原始 Tag、缓存展示、候选展示与写回数据均保持原样。
- 现有自动确认阈值未放宽。离线 provider 探测中“分手说爱你 / 陈芳语”可命中“分手說愛你 / 陳芳語”，置信度保持 0.95。

## 2026-09-01 — 元数据歌词正文请求纳入总预算

- 修复：咪咕、JOOX、千千歌词的二次正文下载此前直接调用网络层，未继承 metadata job 的歌词总预算；弱网时可额外串行等待并让界面长时间停留在“正在获取”。
- 新增 `MetadataProviders._text()`，统一使用剩余 deadline、gzip 协商、解压后大小限制与严格歌词解码；三个 provider 均已切换。
- 增加预算、请求头与适配器调用回归。离线探测确认多个主数据源仍可返回结果；简体本地 Tag 与繁体远端候选的等价评分问题单列为持续改进，未放宽自动确认阈值。

## 2026-09-02 — 首屏空状态与按需封面补全收敛

- 首个音乐库请求尚未完成时，空状态面板不再把暂时的空数组显示为“没有音乐”，减少慢设备冷启动闪烁。
- 打开歌词页时，即使歌曲标题、歌手、专辑 Tag 已完整，只要没有本地或缓存封面，也会排入受限的单曲候选任务，继续获取封面和可补全字段。
- 新增元数据回归；本轮仅进行离线验证，未进行真实设备、外部协议或 App Center 验收。
- 修正合辑歌曲的专辑封面回退键，统一使用 album_artist，避免缓存命中后仍显示无封面。
- 专辑/歌手元数据适配器现在隔离 schema 异常并继续回退链，失败原因仍进入有界 provider 诊断。
- 损坏的曲目候选 JSON 现在会自动进入受限重试，避免“空候选但永久已完成”；人工确认记录仍保持权威。
- provider 网络/协议失败与真实无匹配结果已分离，避免外部服务短暂异常导致元数据永久停留在 `no_match`。
- provider 失败判定改为线程本地标记，避免并发元数据 worker 共享计数造成错误状态分类。
- 冷启动恢复大队列不再与首页分页并发争用索引，队列补水在首屏可见后继续执行。
- 追加 100k 合成曲库基准：分页冷/热缓存、分组/目录、引用补水和 FTS/LIKE 均保持稳定，结果见 `artifacts/large-library-benchmark-20260902-followup.json`。

## 2026-09-02 — 元数据候选可恢复性与界面竞态修复

- 修复单曲元数据候选的负缓存断点：`no_match` 不再只显示不可操作的提示，用户可显式重新查询当前歌曲；该操作仅重新排队这一首歌，不会开启后台全库补全。
- `/api/metadata/track` 增加受限的 `retry=1` 语义，服务端只替换终态无匹配结果，保留正常缓存和 provider 保护策略。
- 候选对话框以请求令牌隔离异步响应，关闭窗口、打开另一首歌或触发重试后，旧请求不得改写当前内容。
- 已运行专项元数据/Node UI 回归、源码清单更新、完整离线门禁及 `git diff --check`；未打包、未部署、未进行真实设备或外部数据源验收。

## 2026-09-02 — 首屏状态渲染减少无意义布局读写

- 首屏歌曲行和表头已经使用增量提交，但审计发现普通播放/收藏状态刷新仍会无条件在动画帧中执行列宽测量、表头同步和移动分页可见性检查。
- 表头函数现返回 DOM 是否实际变化，分页按 HTML 变化提交；只有歌曲列表、表头或分页真的变化时才触发这组可能遍历可见行的布局工作。窗口尺寸和容器几何变化仍由既有 resize/ResizeObserver 处理。
- 已运行 `test_ui_library_loading.js`、封面调度专项、清单更新、完整离线门禁和 `git diff --check`；未打包、未部署、未做真实设备/NAS 验收。

## 2026-09-02 — Tag 写回不再被后台抓取开关阻断

- 修复元数据设置语义：Tag 写回线程此前错误地同时依赖后台全库补全开关，造成“写回已开启但队列不执行”。
- 现在 `metadata_tag_write_enabled` 是写回 worker 的唯一启停条件；`metadata_enabled` 仍只控制后台 provider 扫描，两个设置继续默认关闭。
- 已运行元数据专项、源码清单更新、完整离线门禁和 `git diff --check`；未打包、未部署、未进行真实设备验收。

## 2026-09-02 — 大曲库元数据 reconcile 减少 SQLite 往返

- 将每首歌曲分别读取歌词缓存和曲目匹配缓存过期时间，合并为一次流式 `LEFT JOIN` 查询。
- 保留未缓存曲目、强制刷新、过期重排队和队列边界语义；新增源码回归锁定查询边界。
- 已通过 92 项元数据专项与完整离线门禁，更新源码清单；未打包、未部署、未进行真实设备验收。

## 2026-09-02 — 交互式封面预热跳过已有缓存

- 页面重复加载时，封面预热入队前会检查当前版本的 `.jpg` 正缓存和 `.none` 负缓存，避免已知结果再次创建后台预热工作。
- 检查仅为廉价文件存在性判断，不改变读取层的大小校验、共享资源完整性检查和版本失效语义。
- 已通过封面/元数据专项、完整离线门禁、源码清单更新和 `git diff --check`；未进行真实设备或 NAS 验收。

## 2026-09-02 — 元数据结果回投歌曲列表

- 修复元数据抓取成功但列表仍显示空字段的链路断点：普通曲目页现在按页批量读取 `metadata_tracks` 与已确认的 `metadata_track_matches`。
- 仅填充缺失或文件名来源字段，真实 Tag 仍优先；provider 封面通过严格校验的 metadata artwork URL 提供给前端。
- 已通过 123 项相关专项、完整离线门禁、清单更新和 `git diff --check`；未打包、未部署、未进行真实设备验收。

## 2026-09-02 — 曲目页元数据缓存查询合并

- 将歌曲页回投歌词缓存和曲目匹配缓存的两次 SQL 查询合并为一次有界 `LEFT JOIN`。
- 保留匹配状态过滤、Tag 优先级、歌词/封面安全投影语义。
- 已通过 103 项相关专项、完整离线门禁、清单更新和 `git diff --check`；未进行真机或 NAS 验收。

## 2026-09-02 — 表头控件事件绑定去重

- 表头 DOM 未变化时，不再重复遍历并绑定排序、列显示和列宽拖拽事件，减少大曲库状态刷新期间的主线程工作。
- 表头结构变化仍会完整重绑，功能语义不变；已通过 Node UI、完整离线门禁、清单更新和 `git diff --check`。

## 2026-09-01 — 已解码封面不再触发列表二次闪烁

- 修复稳定行键提交与封面调度器之间的运行时 DOM 差异：封面从 `data-cover-src` 迁移到 `src` 后，播放/收藏等无关刷新此前仍可能误替换整行，令已解码封面重新加载。
- 新增比较归一化，仅忽略封面加载器的临时属性、完成态和回退图标可见性；曲目正文、播放/收藏状态及真实封面地址变化继续按原规则提交。
- 同时复核元数据开关边界：后台全库补全默认关闭不阻断当前歌曲歌词优先任务，失败任务仅由用户显式重开歌词页恢复。
- 封面调度器额外保留原始声明 URL，避免浏览器把相对路径规范为绝对 `src` 后仍被错误当作行数据变更；歌词页面保留并限制服务端错误原因，便于区分 worker 未启动、接口失败和普通无匹配。

## 2026-09-02 — 分组与大曲库表头重建收敛

- 审计确认分组、目录请求已走响应 LRU、同请求合并和后端短期查询缓存；本轮继续消除渲染空转。
- `renderTableHead()` 按视图模式、列模板和表头标记的 JSON 签名复用 DOM；播放、收藏和扫描状态更新若没有改变排序或列配置，就不再重新创建表头控件和触发布局重算。签名不使用可能被旧 WebView `dataset` 规范化的 NUL 分隔符。
- 大曲库离线基准现在独立记录专辑、文件夹、根目录浏览的冷/热缓存时间、结果一致性与命中计数。20k 合成样本中专辑热读约 11.1x、文件夹约 11.7x、根目录约 45.2x；结果仅作当前机器趋势证据。
- 同一基准新增“歌手/作曲者 → 专辑”的范围 CTE 路径；20k 样本中创作者专辑热读约 55.1x，确保左侧分类的常用二级入口不被普通专辑页基准遗漏。

## 2026-09-01 — 引用曲目批量补水缓存与基准

- `query_library_items_by_ids()` 现在接入既有短期、有界、索引写入即失效的查询缓存，覆盖收藏、播放列表和队列恢复时的重复补水读取。
- 缓存结果保持请求顺序、遗漏文件省略和防御性深拷贝；新增 SQLite 回归确认同批请求只执行一次 `IN` 查询、调用方修改不会污染缓存，且索引写入后不会返回旧条目。
- 基准工具增加该热路径的冷/热测量。20k 合成曲库、120 项补水样本冷读约 5.20ms、热读约 0.46ms。

## 2026-09-01 — 增量列表更新不再重启封面调度

- 列表已使用稳定行键时，播放状态等小范围补丁会保留已有封面节点；本轮进一步避免这种补丁取消并重建整个可见区封面观察器。
- 调度器仅在检测到新建的未排队封面节点，或确实空闲且仍存在未启动封面时才启动；旧 WebView 的恢复兜底仍保留。
- 补充列表加载回归并通过专项验证。

## 2026-09-01 — 歌词任务终态失败可恢复

- `api/lyrics` 增加受显式用户操作驱动的 `retry=1` 语义：已达失败上限的单曲歌词任务可被安全重置并再次唤醒优先 worker。
- 歌词页仅在用户重新打开且上一次为终态错误时携带该参数；后台定时轮询仍不重置失败任务，因此网络/数据源故障不会演变为无限请求。
- 新增服务端恢复回归与 UI 调用边界回归；不改变后台全库补全或 Tag 写回默认关闭。

## 2026-09-01 — 收藏/播放列表补水请求去重

- 新增 `item_hydration_request.js`，以受限的视图和标准化曲目 ID 序列识别正在执行的引用曲目补水任务。
- 相同收藏/播放列表页面在补水期间再次渲染时不再取消并重启任务，避免大列表首批内容到达后的重复网络请求与二次闪烁；引用集合或视图变化仍会取消旧任务，generation 校验继续防止过期响应写回。
- 新增对应 Node 回归，并在源码清单更新后执行完整离线测试。未打包、未连接真实设备。

## 2026-09-01 大曲库分页缓存基准

- 扩展 100k 曲库离线基准：除分页、分组、目录和搜索外，新增重复第一页的冷/热页面缓存测量及命中计数。
- 本机样本中第一页冷读约 45ms、热缓存约 0.54ms；响应仍以独立副本返回。首屏常规路径沿用已落库总数，未发现重复 COUNT(*) 全表扫描。
- 新增查询缓存重复读取回归；源码清单已更新且完整离线门禁通过。

## 2026-09-01 元数据数据源失败投影边界

- 将 provider 失败摘要拆至纯策略模块，限制最多 16 个来源以及名称、计数、错误文本、冷却时间，避免异常诊断内容放大状态接口或前端渲染成本。
- 保留“无可信匹配”与网络/协议/解码失败的既有区分；没有改变回退数据源顺序、后台补全或 Tag 写回默认状态。
- 新增独立回归；本轮完整离线门禁与源码清单更新后同步确认。

## 2026-09-01 首屏用户状态并发渲染收敛

- 修复用户状态与首屏歌曲页并行加载时的重复渲染：首批歌曲未到且没有本地快照时，只刷新播放器和导航，不再先构造空列表。
- 首屏真实列表、快照列表与后续用户状态仍保持完整渲染语义；播放恢复、收藏/歌单合并不受影响。
- 新增 UI 回归，源码清单已更新且完整离线门禁通过。

## 2026-09-01 Provider 歌词解码可靠性

- QQ、酷狗、JOOX 及兼容 provider 的 base64/文本歌词改为严格、有界解码：验证 base64，并依序兼容 UTF-8、GB18030 与 Big5。
- 不再用 `errors=ignore` 静默丢弃损坏字节；异常响应会进入既有 provider 失败统计和冷却，避免界面把协议故障误显示为无歌词。
- 新增损坏歌词响应与 JOOX JSONP 适配回归；本轮完成后更新源码清单并执行完整离线门禁，未进行真实设备验收。

## 2026-09-01 列表刷新与歌词即时回退

- 扫描刷新期间只更新状态计数，不再触发中间全量 `render()`，降低歌曲列表加载后的闪烁和封面重解码。
- `/api/lyrics` 优先读取嵌入歌词及同名 sidecar LRC；命中本地歌词时立即返回 `source=本地歌词`，不等待 provider worker。
- 修复仅有封面而无歌词的 `metadata_tracks` 记录误短路歌词任务的问题，保留封面并继续执行优先歌词获取。
- 本地歌词命中时保留同一缓存记录的 artwork URL，歌词页不再因快速本地回退丢失在线封面。
- 将歌词缓存完整性判断拆为独立纯策略模块并加入回归，避免 artwork-only 或损坏时间值短路优先歌词任务。
- 复跑 100k 曲库离线基准，确认首屏防闪烁与歌词缓存改动未影响分页/搜索性能。
- Provider 请求统一声明可接受响应编码并加入回归，降低代理压缩格式差异导致的元数据解析失败。
- 元数据服务未启动时 `/api/lyrics` 改为结构化 503，避免静默返回空结果掩盖启动故障。
- 歌词优先响应增加同专辑 artwork 回退，减少曲目封面尚未落库时的短暂空白。
- 记录本机 provider smoke 样本，保留未命中源并通过状态观测，不在单次样本上改变回退链。
- 补充 go-music-dl/music-lib provider 协议差异审计，明确网易云 weapi 尚未移植，避免误判现有公开链路。
- 新增 UI/元数据回归；源码清单与完整离线门禁通过，未进行真实设备验收。

## 2026-09-01 恢复 fnOS 微应用入口

- 按产品要求将 `src/manifest` 从 `native_app=true` 恢复为 `micro_app=true`。
- 将 `src/app/ui/config` 入口类型从 `url` 恢复为 `iframe`；CGI 地址和认证代理保持不变。
- 同步更新启动入口回归测试与项目上下文文档；播放、Android MediaSession 和后端逻辑未修改。

## 2026-09-01 离线目标复核与大库基准

- 重新审计 TODO 中无需真机的条目，确认资源边界、可观测性、分页/缓存和多数模块拆分已有回归覆盖；
  未完成项集中在真实设备、外部协议/凭据和发布决策。
- 重新生成 100k 曲库离线基准：FTS5 trigram 搜索较 LIKE 基线约 15.2x，分页峰值 Python 分配约
  611 KiB；结果保存至 `artifacts/large-library-benchmark-20260901.json`。

## 2026-09-01 首屏列表与元数据补全修复

- 避免状态刷新时重复替换完全相同的曲目列表 DOM，减少列表加载后的闪烁、封面重新解码和滚动抖动。
- 修复手动“重新补全元数据”在默认关闭后台抓取时的假成功：手动操作会显式开启抓取再入队；默认配置仍保持关闭。
- 保留现有多 provider 回退链和失败状态观测；源码清单更新，982 项 Python 及全部 UI/Node 离线回归通过。

## 2026-09-01 当前歌曲歌词按需获取修复

- 修复默认关闭后台元数据补全时，歌词接口虽入队但优先 worker 永久等待的问题。
- 当前歌曲的明确歌词请求现在可独立唤醒优先 worker；后台全库补全和 Tag 写回仍保持原有关闭门禁。
- 完整离线回归通过（983 项 Python 及全部 UI/Node 回归）。
- 歌词响应现在会携带已缓存的 artwork；前端只为缺少本地封面的当前曲目应用它，避免后台补全成功但界面仍显示空白。
- 修复元数据候选接口缓存未命中时只返回 pending 却未入队的问题；明确打开候选的单曲现在会进入受限优先队列，后台全库补全开关保持关闭语义。
- 曲目行封面增加浏览器原生延迟加载和异步解码提示，降低大曲库首屏渲染压力。

## 2026-09-01 三星 S9+ 六项目标最终验收

- 直接通过已安装的 instrumentation APK 在三星 S9+ 执行远程通知/身份隔离、远程播放器、
  command ticket、登录历史和 WebView 返回回归：6 个测试类共 7 项，全部 `OK`。
- 设备运行态确认 `0.2.34`（versionCode 302）；媒体键冒烟测试无崩溃，现有会话与通知快照已保存。
- 六项目标均有源码契约、离线回归及 S9+ 动态证据；未将 fnOS 未导出的私有 MediaBrowser 当作公共接口。
- 本次仅新增验收证据，未修改播放代码；Gradle 全量任务仍受 Windows loopback 构建环境限制。

## 2026-09-01 六项目标动态证据补充

- S9+ 日志确认会话建立时序、远程通知发布和旧身份拒绝均发生在预期阶段；
  `artifacts/s9-lock-key-dynamic.txt` 保存了 `session_ready`、`remote_enable ready`、
  `remote_update ignored: stale_generation` 及系统媒体键事件。
- fnOS 私有 MediaBrowser 未导出，未将宿主私有能力纳入 fnAudio 验收。
- 增加 command ticket 动态回归：MockWebServer 返回不匹配票据时，MediaController 不会被乐观切换
  为播放，服务记录 `invalid_payload`/`stale_response`，证据保存于
  `artifacts/s9-command-ticket-dynamic.txt`。
- 六项目标完成审计：6/6 项实现已通过离线回归与三星 S9+ 动态证据核对；未将未导出的 fnOS
  私有 MediaBrowser 当作可复用能力。

## 2026-09-01 远程更新身份隔离

- 修复 `ACTION_REMOTE_UPDATE` 仅校验 targetId 的缺口；现在服务层会严格检查 generation/engine epoch，
  防止绕过 WebView bridge 的旧回调污染当前会话。
- 新增 S9+ instrumentation 覆盖旧身份更新；构建、安装和真机 instrumentation 均通过（2 项环境跳过）。

## 2026-08-31 ARM64 构建阻塞复核

## 2026-09-01 三星 S9+ 设备基线

- 在 root 三星 S9+（`1ca53b6720027ece`）安装现有 `0.2.32` debug APK，确认登录页和包内
  `PlaybackService` 注册正常；未将历史包当作最新源码验收证据。
- adb 外部直接启动非导出 `PlaybackService` 被系统拒绝（预期权限边界）；已保存 MediaSession
  与通知快照，待最新源码 APK 构建成功后再做登录、播放、锁屏、媒体键和进程回收验收。

## 2026-09-01 最新源码 APK 构建与 S9+ 验收

- 通过缩短 `GRADLE_USER_HOME` 与临时目录，绕过 Windows Gradle loopback 错误；修正本地 SDK
  路径后成功构建 `0.2.34` debug APK，并安装到 root 三星 S9+。
- 内网登录成功，远程播放状态创建 fnAudio Media3 会话及 `fnaudio_remote_playback` MediaStyle
  通知；系统日志确认媒体键事件路由到 fnAudio 会话。
- 强制停止后的会话清理已确认；进程重启并从持久快照恢复、锁屏界面实际交互和旧事件隔离仍待继续验收。
- 追加验证：强制停止后由系统启动器重新打开，MainActivity 与 Media3 会话恢复，曲目和暂停位置
  重新出现；熄屏期间通知仍存在且包含 transport 元数据。三星系统对该频道执行 OEM muted/demoted，
  需在系统通知设置中允许后才会稳定显示。
- 修复真机 instrumentation 回归：远程播放器测试先模拟后端确认的队列索引，避免将后端权威状态
  误判为本地即时切歌；登录历史测试将地址断言限定在历史列表容器。
- S9+ instrumentation 复跑通过（13 项，2 项环境跳过，0 失败）；fnOS 私有 MediaBrowser 未导出，
  探测测试按环境跳过并保留该边界证据。

- 使用 JDK 17.0.20、JDK 25.0.3、`--no-daemon` 及 Gradle native service 回退参数重试，均复现
  `Unable to establish loopback connection`（`java.net.SocketException: Invalid argument: connect`）。
  未覆盖安装设备上的旧 APK。

## 2026-08-31 构建验证边界

- ARM64 APK 构建再次因 Windows Gradle `Unable to establish loopback connection` 失败；设备保持 `0.2.33 / versionCode 301`，未将旧包当作新增诊断改动的真机验证。

## 2026-08-31 飞牛 APP 原生启动容器对齐

- SSH 对照内网测试机官方 `trim.music`：其 FPK manifest 使用 `native_app=true`，App Center
  UI 使用 `type: "url"` 的全页入口，而 fnAudio 原先是 `micro_app=true + iframe`。
- fnAudio 入口已切换为同一容器类别，同时保留 `/cgi/ThirdParty/fnaudio/index.cgi/` 及 CGI
  鉴权代理；新增离线回归防止启动模式回退。
- 这是一项结构性前置改动，不宣称已经拿到飞牛私有 MediaSession/浮窗接口；后续必须在小米
  15 Pro 的飞牛 APP 内播放后抓取系统会话、通知与任务窗口证据。
- 实机确认启动后保持在 `com.trim.app/.MainActivity` 的全页 WebView，并直接显示 fnAudio
  曲库；停止独立 fnAudio 客户端后，官方 `com.trim.app/media-session` 仍为 `NONE`，因此尚未
  证明其会自动接管第三方 FPK 的标准 Web Media Session。
- 版本提升为 `0.2.34`（Android 配套 versionCode `302`），用于承载这次 FPK 启动模型变更。

## 2026-08-31 宿主动态对照

- 在已授权小米 15 Pro（`baf83ddd`）安装飞牛 APP 1.35.2 与 fnAudio debug 客户端，抓取
  `dumpsys media_session`、`dumpsys notification`、`dumpsys activity services`。
- 证实官方 `com.trim.app/media-session` 空闲时存在但未激活；fnAudio 自己的 Media3 会话和
  MediaStyle 通知可被系统识别。尚未取得“飞牛 APP 内打开 FPK 后自动接管官方会话/浮窗”的动态证据。

## 2026-08-31

- 强化播放会话 KeepAlive lease 的输入边界：异常时长、NaN/Infinity 及恢复时钟值现在安全
  回退，不会污染会话恢复流程；新增 2 项专项回归。
- Android 远程会话恢复现在推进 `engine_epoch`，让服务重建后的引擎接管旧快照并拒绝旧进程
  迟到事件；新增生命周期静态契约回归。
- 收紧 Android 远程状态身份解析：存在但非法的 generation、engine_epoch 或 state_version
  不再回退到当前值，直接记录 `invalid_payload` 并丢弃，防止旧事件污染当前会话。
- 修复远程状态网络线程到主线程的竞态：状态和命令核心更新执行前会再次核对会话身份，
  防止目标切换后的旧 runnable 写入新播放器。
- 非零 generation/engine epoch 会话不再接受缺失身份字段的入站事件；初始零世代继续兼容旧
  后端，降低旧事件绕过隔离的风险。
- 修复 state_version 网络线程竞态：旧回调不会再提前抬高新会话的版本水位，版本比较和提交
  统一在主线程身份校验后执行。
- 收紧 Android 身份数字解析：小数型 generation/engine_epoch/state_version 不再被截断接受，
  防止格式错误事件伪装成合法会话身份。
- 改进远程请求可观测性：主动取消的命令、轮询和 SSE 请求记录为 cancelled，避免与真实网络
  失败混淆。
- 修复恢复日志误报：持久远程会话激活失败时现在清理快照并记录 activation_rejected，不再
  错误报告恢复 ready。
- 远程 MediaSession stop 命令增加 pending 去重与失败释放，降低重复媒体键回调造成的重复请求。
- 命令确认现在同步 core 的播放状态、位置和时长，使 stop 成功后立即反映权威状态并释放 pending。
- 记录本地模拟器动态验收环境阻塞：`fnaudio-fnos-bridge` 缺失有效 x86_64 system image，
  Emulator 报 `Cannot find AVD system path`；未伪造系统级动态通过证据。
- 复测发现 API 35 AOSP x86_64 AVD 可启动，但现有 APK 仅含 arm64-v8a 原生库，安装失败为
  `INSTALL_FAILED_NO_MATCHING_ABIS`；已记录为 universal/x86_64 构建前置条件。
- 在小米 15 Pro 上对既有 `0.2.33 / versionCode 301` 安装执行 LoginActivity 重启检查，未发现
  崩溃；由于未能构建最新 APK，该结果不作为本轮源码动态验收结论。
- 按用户要求关闭 x86_64 模拟器验收路线，后续 Android 动态验证仅针对 arm64 小米 15 Pro。
- 小米 15 Pro 包信息检查确认 PlaybackService 与前台媒体服务权限已注册/授权；空闲登录页无
  活动 MediaSession，已记录为播放态验收前置证据而非功能通过。
- 使用 JDK 17 重试 Android 离线构建仍复现 Gradle loopback 错误，确认问题属于宿主进程通信，
  不是单纯 JDK 版本选择。

## 2026-08-31

- 新增 transport-neutral 播放会话契约，统一 participant 世代、引擎 epoch、KeepAlive 租约和
  命令票据，避免浏览器/Android/远程输出各自维护不一致状态。
- 新增 unittest 回归，完整离线门禁通过；修正打包输出路径误取旧 `src/fnaudio.fpk` 的问题，
  当前 `artifacts/0.2.33/fnaudio-0.2.33-fnpack.fpk` 内部版本为 `0.2.33`、服务端口为 `53199`。
- 根据 Android 反馈建立持续修复目标：补强会话建立与远程通知链路，同时明确不依赖飞牛
  APP 未公开的私有 MediaSession 接口。
- 将持续修复拆分为六项可追踪目标：建立时序、远程通知、锁屏/媒体键、进程恢复、世代与
  命令票据隔离、可观测日志和失败原因。
- Android PlaybackService 增加有界脱敏日志，覆盖远程会话拒绝原因、更新、命令失败和确认，
  便于定位“通知/媒体会话未生效”问题；离线门禁 959 项通过。
- WebView 远程会话现在向 Android 服务传递并在控制请求中携带有界的 generation/engine_epoch，
  为旧会话隔离和后端最终状态确认提供一致身份。
- Android 远程服务增加 `state_version` 单调校验，拒绝乱序旧快照并输出脱敏 `stale_state`
  诊断；重新生成 0.2.33 FPK。
- 增加远程状态的 generation/engine_epoch 严格匹配，拒绝跨会话快照污染并记录脱敏原因。

## 2026-08-31

- 补装 Android API 35 ARM64 系统镜像并创建 `fnaudio-api35-arm64` AVD；验证当前
  x86_64 Windows 主机无法运行 ARM64 AVD，保留配置供 ARM64 主机迁移。
- 复核 x86_64 AVD 的 APK 安装阻塞：当前 debug APK 仅含 `arm64-v8a/libgojni.so`，需先
  生成 x86_64/universal 测试变体；本轮未修改应用源码。
- 应用户请求移除本轮临时下载的 ARM64 系统镜像及 `fnaudio-api35-arm64` AVD；保留现有
  x86_64 AVD、Android SDK 和测试证据文件。

## 2026-08-30

- 加固公开曲目投影：限制字段复制上限，隔离异常 Mapping，并修正空 ID 的封面 URL 行为。
- 专项及完整离线回归通过，刷新源码清单与恢复索引。

## 2026-08-30

- 为播放 SSE 增加 512 KiB 单帧预算与超限降级帧，避免异常状态放大长连接资源。
- 完整离线门禁累计 949 项 Python 测试及全部 Node/UI 回归通过。

## 2026-08-30

- 新增 `library_cache_failure_policy.py`，把曲库缓存失败计数规则拆为可测试纯模块。
- 完成完整离线门禁（945 项 Python 测试及全部 Node/UI 回归），刷新源码清单和 155 版本恢复索引。

## 2026-08-30

- 为曲库缓存加载/写入增加有界失败计数，并通过 `library_status` 暴露 `cache_failures.load/save`，避免缓存故障静默不可见。
- 新增曲库缓存可观测性回归；不改变缓存优先级或真实扫描逻辑。

## 2026-08-30

- 完成 SSE 播放事件目标策略专项验证：20 项专项回归通过，确认超长 `target_id` 不会绕过统一策略。
- 完成完整离线门禁：936 项 Python 测试及全部 Node/UI 回归通过；`git diff --check` 通过。
- 刷新源码清单与发布证据恢复索引：554 个源码条目、155 个版本目录；完整离线门禁累计 939 项 Python 测试通过，保留真实设备验收边界说明。

## 2026-08-30

- 新增 `api_token_policy.py`，将 HTTP API token 提取、Bearer 处理和长度上限抽为纯策略；`server.py` 仅保留兼容接线。
- 新增异常 header、损坏映射和超长 token 回归；未打包、未部署、未进行真实设备验收。
- 恢复索引工具新增显式 `-OutputPath`，使用临时文件替换持久化 JSON；默认仍保持只读 stdout 行为，并补充文档/脚本契约回归。
- 恢复索引源码指纹增加精简 PowerShell 回退：缺少 `Get-FileHash` 时使用流式 .NET SHA-256，避免嵌入式宿主无法生成恢复索引。
- `build_release.ps1` 的 fnpack、源码清单、UI 资产和最终 FPK 哈希统一增加精简 PowerShell 回退，避免发布构建依赖单一 cmdlet。
- 新增 `dlna/request_context.py`，抽离 DLNA 诊断请求上下文提取、代理地址优先级和字段上限；新增离线回归。
- `request_context()` 增加异常 `client_address` 容器回退，避免诊断记录被损坏连接元数据打断。
- 加固 `DlnaDiagnostics` 值投影，仅保留有限标量并忽略异常对象，避免诊断路径被字符串化异常打断。
- 为 `DlnaDiagnostics` 增加 1–1000 条目容量上限，异常配置安全回退默认值，避免诊断内存无界增长。
- 加固 `target_id_from_query()`：目标 ID 仅保留有界文本/数字，异常查询安全回退本机目标，避免播放控制参数放大。
- 播放目标参数拒绝 NaN/Infinity，避免非有限数字穿透到目标选择逻辑。
- 播放目标有限性检查补充超大整数溢出回退，避免异常查询打断参数解析。
- 修正 SSE 播放事件入口，改为复用统一目标 ID 策略，消除原始 query 参数绕过边界的路径。

## 2026-08-30

- 加固 `resource_limits.disk_has_reserve()`：路径规范化、父目录遍历和磁盘查询统一捕获 `OSError`、`ValueError`、`TypeError`，非法路径安全返回 `False`。
- 新增包含 NUL 字符路径的回归测试；未打包、未部署、未进行真实设备验收。

## 2026-08-30

- 发布证据恢复索引新增根目录 `SOURCE_MANIFEST.sha256` 指纹字段，用于会话恢复后的源码漂移核对。
- 已重新生成 `artifacts/release-evidence-index-latest.json`，有界扫描 155 个版本目录并记录当前源码清单指纹。
- 新增 `ui/playback_target_policy.js`，统一 UI 对本机、远程、DAC/MPD 目标的判断，避免新增输出后分支语义漂移。
- 新增 `ui/repeat_mode_policy.js`，将循环关闭/列表循环/单曲循环的归一化、轮换和中文文案抽为纯模块；兼容测试同步改为校验模块接线。
- 新增 `ui/track_sort_policy.js`，将曲目排序纯规则抽离并保持序号无效值、中文数值比较和加入时间排序语义不变。
- Android bundled WebView 同步内嵌循环与排序策略脚本，保持本地 UI 与资源版本一致。
- `index_release_evidence.ps1` 改用 PowerShell `[version]` 语义降序排序版本目录，修复多位次版本的恢复索引顺序歧义。
- 已重建发布证据恢复索引，当前首项为 `0.2.33`，并保留 155 个版本目录的验证结果。
- 发布索引脚本增加 `$PSScriptRoot` 为空时的当前目录回退，提升嵌套 PowerShell/会话恢复场景的可用性。
- 发布索引排序增加 `[version]` 转换异常回退，异常目录不会阻断恢复索引生成。
- 发布索引脚本在脚本根变量缺失时增加项目根/`tools` verifier 路径探测，提升不同 PowerShell 宿主下的恢复兼容性。
- 新增发布索引行为级回归，直接核对生成 JSON 的语义版本顺序、条目上限和当前首版本。
- 发布索引回归改为验证源码指纹格式；生成流程继续在门禁前后显式重建并核对实际 SHA-256，避免测试顺序导致的瞬时假失败。
- 发布证据恢复索引新增固定 `schema=1` 标识，为后续字段演进和会话恢复兼容性提供明确契约。
- 新增 `ui/library_sort_options_policy.js`，将视图排序选项和默认排序键抽为纯模块；同步 Android bundled UI 和独立 Node 回归。
- 新增 `ui/folder_label_policy.js`，将跨平台文件夹标签生成抽为纯模块并拒绝任意对象字符串化；同步 Android bundled UI 和独立 Node 回归。
- 新增 `ui/host_privacy_policy.js`，将 LAN/公网主机判定抽为纯模块，覆盖保留网段、本地域名和异常输入；同步 Android bundled UI 与回归。
- 主机隐私策略补齐 IPv6 ULA 与链路本地范围，降低内网 IPv6 被误判为公网的风险。
- 可观测性慢请求阈值对非正输入安全回退默认值，避免诊断中出现全量请求“慢请求”误报。
- 新增 `ui/lyrics_parse_policy.js`，将歌词时间戳解析和稳定排序抽为纯模块，保持现有歌词加载和轮询行为不变。
- health/diagnostics 新增封面缓存压力摘要，帮助识别大曲库并发封面请求；字段经过脱敏和有界投影。
- 补充封面缓存摘要对损坏容器和异常上限的回归覆盖，确保诊断路径保持安全回退。
- 加固 `cover_item_cache.py` 的容量、路径和 in-flight 参数边界，异常对象安全回退，不触发自定义类型强制转换。
- 将封面缓存的 LRU 与同键 in-flight 编排抽至 `server/cover_item_cache.py`，保留 `server.py` 兼容接线和原有缓存行为；新增独立回归。
- 本地封面 LRU 缓存增加有界同键请求合并，避免移动列表或快速重绘时重复解析同一曲目封面；异常和协调表饱和安全退化，不改变封面结果格式。
- 新增 `ui/user_media_state_policy.js`，将收藏/歌单归一化与增量合并逻辑抽为可测试纯模块；保持原有上限、持久化和同步行为。
- 新增 `ui/creator_view_policy.js`，将歌手/作曲者与专辑视图状态判定抽为可测试纯模块；`app.js` 保留兼容包装。新增 Node 回归，未改变运行时播放行为。
- 增强 `tools/benchmark_large_library.py` 的搜索性能证据：当启用 FTS5-trigram 时记录 `speedup_vs_like`，便于跨版本比较 FTS 与 LIKE 的相对表现；不引入依赖硬件速度的阈值。
- 新增对应 Python 回归断言；完整离线门禁共 917 项通过，未进行真实设备验收。
- 最新 100,000 条离线基准记录分页约 0.253 秒、FTS/LIKE 相对加速约 17.9 倍，详情见 `artifacts/large-library-benchmark-latest.json`。
- 基准 JSON 新增 Python 与 SQLite 版本字段，便于恢复和跨环境解释历史性能证据。
- 明确区分封面提取缓存与缩略图预热缓存的待办名称，避免两个不同指标集合在恢复索引中产生歧义。

# 0.2.33 后续 100k 曲库离线基准（2026-08-30，未发版）

- 完成 100,000 条合成 SQLite 曲库基准：三页分页约 0.259 秒、Python 峰值约 611 KiB；FTS 搜索约 7 ms，LIKE 基线约 125 ms。
- 结果归档至 `artifacts/large-library-benchmark-latest.json`，仅作为离线性能基线，未进行真实设备验收。

# 0.2.33 后续发布资产加载契约（2026-08-30，未发版）

- 版本一致性回归新增检查曲目筛选和根目录标签策略模块已接入 `index.html`，且加载顺序早于 `app.js`。
- 仅增强发布门禁，未改变运行时逻辑。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续签名哈希边界复用（2026-08-30，未发版）

- `library_signature()` 复用 `digest_signature_parts()`，统一签名排序、预算和哈希组合逻辑。
- 新增兼容回归，未改变 CUE、音频文件或 `metadata_version` 的签名语义。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续签名版本尾字段保留（2026-08-30，未发版）

- 文件签名收集为 `metadata_version` 预留片段和字节预算，超大目录下 schema 版本变化仍能触发增量扫描。
- 新增极小预算回归，未改变正常签名和 CUE 检测语义。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续文件签名资源预算（2026-08-30，未发版）

- `library_signature()` 增加 200,000 片段和 8 MiB 总文本预算，单片段长度也受限，避免超大目录增量检查放大内存。
- 保留 CUE 与支持音频的签名参与；新增预算回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续扫描签名 CUE 兼容修正（2026-08-30，未发版）

- 修正文件分类策略接线，确保 `library_signature()` 仍记录 CUE 文件变化，而音频扫描循环不重复解析 CUE。
- 新增删除 CUE 后签名变化回归；未改变媒体支持和路径安全语义。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续扫描文件分类边界（2026-08-30，未发版）

- 新增 `library_scan_file_policy.py`，统一 CUE、支持音频和忽略文件的扩展名分类。
- `library.py` 的扫描与签名循环复用纯策略，新增回归且未改变支持格式和路径安全语义。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续曲库根目录标签边界（2026-08-30，未发版）

- 新增 `library_root_label_policy.js`，集中处理多音乐库根目录名称提取与同名消歧。
- `app.js` 保留状态读取和 UI 接线；新增 Node 回归，未改变正常设置页展示语义。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续缓存压力异常隔离（2026-08-30，未发版）

- `saturated` 计算对损坏的缓存权重和条目容器进行安全归一化，避免诊断快照因内部状态异常中断。
- 新增专项回归，未改变正常缓存容量判断；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续前端曲目筛选边界（2026-08-30，未发版）

- 新增 `library_track_filter_policy.js`，集中处理分页、分组、DSD、队列、收藏和播放列表的曲目来源选择，以及搜索过滤和排序回调。
- `app.js` 保留状态、补水和生命周期接线；新增 Node 回归，未改变正常展示协议。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续大曲库缓存压力观测（2026-08-30，未发版）

- 曲库查询缓存快照新增 `saturated`，当条目容量或结果权重预算耗尽时明确标记。
- health/diagnostics 仅公开该脱敏布尔状态；未改变 TTL、LRU、权重和淘汰语义。新增专项回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续全量播放分页边界策略（2026-08-30，未发版）

- 统一全量播放的总数安全归一化、200,000 条上限和空页/达到总数时的提前终止判断。
- 保持逐页请求、缓存、批量合并与取消语义；完整离线门禁 908 项通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续全量播放分页策略拆分（2026-08-30，未发版）

- 新增 `library_full_list_policy.js`，统一全量播放的总数归一化、200,000 条上限和提前终止规则。
- `app.js` 保持逐页合并、响应缓存和批请求取消语义；新增 UI 专项回归，完整离线门禁 908 项通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续前端访问模式请求缓存（2026-08-30，未发版）

- 新增 `access_profile_loader.js`，为 `api/access` 增加 10 秒 TTL 与 in-flight Promise 去重。
- `app.js` 的访问模式状态和 UI 行为保持兼容；新增 UI 专项回归，完整离线门禁 908 项通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续播放命令缓存压力可观测性（2026-08-30，未发版）

- `/api/health`、`/api/diagnostics` 新增播放命令幂等缓存的 entries/limit/saturated 有界摘要，不泄露命令、播放队列、曲目或路径。
- 新增快照专项并扩充健康/诊断回归；专项 34 项和完整离线门禁 908 项通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续播放命令幂等缓存边界拆分（2026-08-30，未发版）

- 新增 `playback_command_cache.py`，集中处理命令结果缓存的过期清理、损坏条目隔离、防御性响应副本和 FIFO 容量淘汰。
- 保留 `server.py` 的全局锁、TTL、容量和播放命令协议；新增 5 项专项回归，完整离线门禁 907 项通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续扫描刷新队列策略拆分（2026-08-30，未发版）

- 新增 `library_refresh_policy.py`，抽离刷新请求排队、force 升级、worker 启动、取出和取消的纯状态转移。
- `library.py` 保持线程、锁和实际扫描职责；新增 5 项专项回归，完整离线门禁 902 项通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续恢复手册证据索引说明（2026-08-30，未发版）

- `RECOVERY.md` 新增发布证据快速盘点章节，记录 `tools/index_release_evidence.ps1` 的只读调用方式、语义版本上限和 `EvidenceComplete=false` 的解释。
- 未修改运行时逻辑、发布产物或真实设备验收结论。

# 0.2.33 后续播放状态响应组合拆分（2026-08-29，未发版）

- 新增 `playback_status_response.py`，集中处理浏览器、ALSA、MPD、UPnP 状态响应和错误响应的安全组合。
- `server.py` 保持设备探测、CUE 自动推进与异常接线；新增专项回归，完整离线门禁 897 项通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续查询缓存指标投影拆分（2026-08-29，未发版）

- 新增 `library_query_cache_presentation.py`，集中处理缓存命中率、计数器上限与诊断快照投影。
- `library_query_cache.py` 保持原有 TTL/LRU/权重/失效行为；修复拆分后淘汰路径的旧符号残留，完整离线门禁 892 项通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续发布证据索引（2026-08-29，未发版）

- 新增 `tools/index_release_evidence.ps1`，只读扫描 `artifacts` 下最多 256 个语义版本目录，排除实验目录并复用 verifier 输出统一 JSON 状态。
- 单目录证据损坏会被标记为不可验证并继续处理后续目录，便于会话删除后的快速恢复盘点；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续引用曲目批请求去重（2026-08-29，未发版）

- 新增 `ui/library_item_request_loader.js`，收藏/歌单补水与后台引用补水共享有界 in-flight 批请求。
- 相同批次复用 Promise，最多保留 32 个进行中请求键；新增 Node 回归，完整离线门禁 891 项 Python 测试及 UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 API 路由权限策略拆分（2026-08-29，未发版）

- 新增 `api_route_policy.py`，集中处理请求路径去查询串、长度边界、媒体资源认证判定及 API scope 映射。
- `api_auth.py` 继续导出原有策略符号，授权行为保持兼容；新增 3 组纯策略回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续分页响应顶层字段边界（2026-08-30，未发版）

- `public_library_page()` 使用最多 32 个顶层字段的惰性复制，避免公开投影前无界 `dict(page)`。
- 保持分页曲目和协议字段兼容；顶层映射专项及 868 项完整离线门禁通过，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续播放命令幂等缓存边界（2026-08-30，未发版）

- `PLAYBACK_COMMAND_RESULTS` 增加 1,024 项容量上限，防止客户端唯一 command_id 持续增长造成内存泄漏式占用。
- 保持 TTL 和重复命令响应兼容；缓存淘汰专项及 867 项完整离线门禁通过，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续曲目分页公开投影拆分（2026-08-30，未发版）

- 新增 `public_library_page()`，集中处理分页曲目字段投影、500 项上限与异常条目隔离。
- `/api/library` 两条分页路径复用纯模块，保持封面 URL 和公开字段兼容；专项及 865 项完整离线门禁通过，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续分组分页投影统一接线（2026-08-30，未发版）

- 专辑归属筛选的分页分支改用 `project_group_rows()`，统一字段白名单、异常隔离与行数上限。
- 新增损坏字段访问回归；专项及 863 项完整离线门禁通过，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续分页游标资源边界（2026-08-30，未发版）

- `paged_rows_with_total()` 改用最多 500 行的惰性游标读取，避免未来调用遗漏 SQL `LIMIT` 时放大内存。
- 游标异常不会伪造部分页，继续走原有 count/page 精确回退；新增分页专项回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续播放状态响应投影拆分（2026-08-30，未发版）

- 新增 `playback_status_presentation.py`，集中处理 MPD/UPnP transport 与 position 的标量字段投影、NaN/Infinity/负数归一化和默认状态。
- `server.py` 状态接口复用纯投影，避免异常后端 payload 直接进入 HTTP 响应；新增 4 项专项回归及 861 项完整离线门禁，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续前端曲目定位有界索引（2026-08-29，未发版）

- 曲目定位模块按数组身份缓存最多 5,000 项 ID 索引，减少大曲库页面中缓存未命中时的重复线性扫描。
- 超出索引范围保持线性回退和原有结果语义；新增 Node 回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续前端曲目定位策略拆分（2026-08-29，未发版）

- 新增 `ui/item_lookup.js`，抽离曲目定位的缓存优先、当前页和全量页回退策略，降低 `app.js` 耦合。
- 保持 LRU 触达、查找顺序与异常降级语义；新增 Node 回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续内存单曲查找异常隔离（2026-08-29，未发版）

- 内存曲目回退查找对每个映射条目的 `get()` 访问进行异常隔离，避免单个损坏条目阻断整个查找。
- 新增专项回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续播放事件投影边界拆分（2026-08-29，未发版）

- 新增 `playback_event_presentation.py`，集中处理 SSE 播放事件的目标、版本、传输状态和位置字段规范化。
- 保留权威 `core` 快照对象身份及现有协议兼容；新增专项回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续单曲文件位置解析拆分（2026-08-29，未发版）

- 新增 `library_item_location.py`，将索引曲目定位到文件路径的安全校验抽为独立模块，保留根目录边界和符号链接防护。
- 服务端定位入口仅保留查询接线；新增专项回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续单曲查询边界拆分（2026-08-29，未发版）

- 新增 `library_item_lookup.py`，将单曲 SQLite 查询和内存回退查询抽离，连接/解码器/异常迭代器失败均安全降级。
- 保持 SQLite 优先、内存回退和缺失项返回语义；新增专项回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续分组/文件夹投影公共边界（2026-08-29，未发版）

- 将分组和文件夹结果投影的重复边界逻辑合并为公共有界迭代路径，减少维护分叉并保持 SQLite Row 兼容。
- 公开字段、5,000 行上限和异常隔离语义不变；专项及完整离线回归通过，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续分页文件夹响应投影（2026-08-29，未发版）

- 文件夹分页响应改用安全投影，仅保留公开字段并移除 SQL `total_count` 窗口列，减少无用 payload 和对象复制。
- 支持 SQLite Row 与普通映射，最多输出 5,000 行；新增专项回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续分页分组响应投影拆分（2026-08-29，未发版）

- 新增 `library_group_presentation.py` 纯投影模块，分页分组响应只保留公开字段，避免把 SQL `total_count` 窗口列传给前端。
- 支持 SQLite Row 与普通映射，输出最多 5,000 行并安全隔离异常迭代器；专项及完整离线回归通过，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续播放队列 hydration 查询去重（2026-08-29，未发版）

- `hydrate_items_by_ids()` 先对队列 ID 去重后执行数据库查询，降低重复队列造成的 SQL 与对象构建开销。
- 输出仍按原始队列顺序恢复并保留重复项；新增专项回归，完整离线回归 844 项 Python 测试及 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续前端渲染行数边界（2026-08-29，未发版）

- 新增 `ui/library_render_policy.js`，统一对分页、分组和文件夹响应执行最多 500 行的安全裁剪。
- 异常或非数组响应安全降级为空列表，文件夹列表在过滤前验证数组形状，避免异常 payload 一次性构建超大 DOM；新增 Node/UI 回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续根目录结果投影拆分（2026-08-29，未发版）

- 新增 `library_root_presentation.py`，集中处理根目录名称、计数、封面 ID 和搜索筛选的安全投影。
- 兼容 SQLite Row 与旧摘要映射，异常计数回退为 0，输出最多 64 项；新增纯模块与 SQLite 回归，完整离线回归 843 项 Python 测试及 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续根查询策略模块化（2026-08-29，未发版）

- 新增 `library_root_query_policy.py`，为根聚合和搜索生成有界参数化过滤条件，去重并拒绝异常/非文本输入。
- `query_library_root_folders()` 统一复用该纯策略，新增独立策略测试与 SQLite 回归；完整离线回归 840 项 Python 测试及 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续根目录查询范围收敛（2026-08-29，未发版）

- `query_library_root_folders()` 回退聚合和搜索匹配增加配置根过滤，仅处理当前启用的音乐库根，避免历史数据库根造成额外扫描。
- 无配置根时直接返回空匹配集合；保留持久化摘要优先和查询缓存行为。
- 新增 SQLite 回归；完整离线回归 837 项 Python 测试及 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续进程监督可观测性边界（2026-08-29，未发版）

- `ProcessSupervisor.status()` 增加有界 `recent_restart_times`、`restart_window` 与 `restart_after` 字段，便于诊断重启风暴。
- 状态投影拒绝 NaN、Infinity、对象等损坏值，最近重启时间最多保留 32 项；不改变既有重启行为。
- 新增进程监督回归；完整离线回归 836 项 Python 测试及 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 DAC 配置读取边界（2026-08-29，未发版）

- `load_config()` 启动恢复时复用 `bounded_custom_profiles()`，最多接受 64 个映射型 DAC 配置，保持读取、保存和匹配边界一致。
- 新增配置回归；完整离线回归 835 项 Python 测试及 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 DAC 配置持久化边界（2026-08-29，未发版）

- `save_config()` 复用 `bounded_custom_profiles()`，最多保存 64 个映射型 DAC 配置并进行浅复制隔离。
- 通过配置/DAC 专项及完整离线回归 834 项 Python 测试和 Node/UI 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 DAC 配置候选边界（2026-08-29，未发版）

- `dac_quirk_profile()` 对自定义配置采用最多 64 项的惰性遍历，非映射对象和异常迭代器安全忽略。
- 新增 DAC 配置回归；完整离线回归 831 项 Python 测试及 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 Migu 封面候选边界（2026-08-29，未发版）

- Migu 封面提取改为惰性遍历 `imgItems`/`albumImgs`，最多处理 64 项，避免供应商 payload 拼接造成内存峰值。
- 元数据专项 72 项、完整离线回归 830 项 Python 测试及 Node/UI 回归通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续发布校验输入边界（2026-08-29，未发版）

- `verify_release_evidence.ps1` 在读取 `SHA256SUMS` 前拒绝超过 512 字节的文件，确保单记录校验的内存成本有界。
- 新增脚本回归；完整离线回归 830 项 Python 测试及 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续元数据候选边界统一（2026-08-29，未发版）

- 匹配候选保存与确认流程复用 `candidate_mappings()`，仅保留最多 64 个有效映射，隔离异常供应商 payload 的无界列表化。
- 元数据专项 71 项、完整离线回归 828 项 Python 测试及 Node/UI 回归通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续播放会话快照边界拆分（2026-08-29，未发版）

- 新增 `playback_session_projection.py` 纯模块，统一处理当前会话快照的队列/目标/文本字段边界和异常隔离。
- 服务端快照入口复用该模块；通过独立回归、完整离线回归 828 项 Python 测试及 Node/UI 回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续根摘要迭代边界（2026-08-29，未发版）

- `root_index_summary()` 现在最多读取 64 个配置根，与扫描归一化边界保持一致，异常迭代器安全停止。
- 新增根摘要回归；完整离线回归 826 项 Python 测试及 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续播放会话队列投影（2026-08-29，未发版）

- 新增 `playback_queue_ids()` 纯投影边界，恢复播放会话时限制队列为 50,000 个字符串 ID并去重，损坏对象不会触发字符串化或阻断恢复。
- `server.restore_playback_session()` 复用该投影；通过状态投影、播放恢复专项及完整离线回归 825 项 Python 测试和 Node/UI 回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续扫描根候选有界化（2026-08-29，未发版）

- `normalize_scan_items()` 不再无界物化 `roots`，最多读取 64 个候选根；异常迭代器安全停止，保持扫描顺序和既有路径匹配语义。
- 新增回归测试覆盖超长根迭代器；通过完整离线回归 824 项 Python 测试及 Node/UI 回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 DLNA Browse 物化上限（2026-08-30，未发版）

- ContentDirectory 对专辑、歌手、流派和文件夹 Browse 复用有界行物化策略，单次最多 5,000 行。
- 保持小库排序、分页和异常迭代回退语义，降低大曲库 Browse 内存峰值。
- 通过 DLNA/浏览行专项及完整离线回归 821 项 Python 测试和 Node/UI 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 MPD PID 文件读取边界（2026-08-30，未发版）

- MPD 启动清理读取 `mpd.pid` 限制为 256 字节，避免异常文件导致无界读取。
- 保持非法 PID 安全忽略和残留进程匹配语义。
- 通过 MPD 专项及完整离线回归 821 项 Python 测试及 Node/UI 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 MPD 日志尾读竞态边界（2026-08-30，未发版）

- MPD 播放错误日志和诊断尾读统一使用 8 KiB 上限的“读取 +1 后截断”策略。
- 保留原有尾部日志语义，避免文件增长竞态造成无界读取。
- 通过完整离线回归 821 项 Python 测试及 Node/UI 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 MPD PID 扫描读取边界（2026-08-30，未发版）

- MPD 残留进程扫描对 `/proc/<pid>/cmdline` 增加 4 KiB 读取上限，避免异常 proc 内容放大内存。
- 新增 MPD 队列层读取边界回归；通过完整离线回归 821 项 Python 测试及 Node/UI 回归。

# 0.2.33 后续 MPD/AirPlay 进程探测读取边界（2026-08-30，未发版）

- MPD 与 AirPlay 的 `/proc/*/cmdline` 探测读取限制为 4 KiB，避免异常 proc 内容放大内存。
- 新增探测边界回归，保持服务发现与进程匹配行为兼容。
- 通过完整离线回归 821 项 Python 测试及 Node/UI 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续本地进程/配置读取边界（2026-08-30，未发版）

- AirPlay 进程探测限制 `/proc/*/cmdline` 读取为 4 KiB。
- MPD 配置读取限制为 1 MiB，保留原有配置比较语义并避免无界读取。
- 通过 AirPlay 专项及完整离线回归 821 项 Python 测试和 Node/UI 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 历史发布证据复核（2026-08-30，未发版）

- 运行完整证据校验时确认历史 `artifacts/0.2.33` 仅能提供 FPK/SHA256，缺少 staged `SOURCE_PROVENANCE.json`，无法证明源码对应关系。
- 保留该治理缺口并记录恢复规则；未伪造历史 provenance，未修改历史发布产物。

# 0.2.33 后续元数据长期计数边界（2026-08-30，未发版）

- 元数据队列丢弃、Tag 写入和状态缓存命中/未命中计数统一采用 10^12 饱和计数器。
- 继续复用 `metadata_queue_policy.py` 的纯策略，异常旧值安全恢复，队列预算与 SQLite 回退保持兼容。
- 通过元数据专项 74 项、完整离线回归 821 项 Python 测试及 Node/UI 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续元数据计数器饱和（2026-08-30，未发版）

- 元数据服务的 dropped_jobs、tag_written 和状态缓存命中/未命中计数统一采用 10^12 饱和策略。
- 复用 `metadata_queue_policy.py` 的纯计数 helper，异常旧值不会阻断状态快照或持续增长。
- 通过元数据专项 74 项、完整离线回归 821 项 Python 测试及 Node/UI 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 DLNA 事件计数饱和（2026-08-30，未发版）

- GENA 事件服务对 accepted、dropped 和 peak_pending 计数增加 10^12 饱和上限，并隔离异常内部值。
- 保持既有通知队列与 worker 资源边界，新增协议回归。
- 通过完整离线回归 819 项 Python 测试及 Node/UI 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续元数据队列预算边界拆分（2026-08-30，未发版）

- 新增 `metadata_queue_policy.py`，统一限制元数据队列预算并隔离异常配置/内部状态。
- `_upsert_job()` 复用安全投影，队列快照损坏时继续通过 SQLite 计数，避免入队流程中断。
- 通过元数据专项 73 项、完整离线回归 819 项 Python 测试及 Node/UI 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 DLNA 事件资源配置容错（2026-08-30，未发版）

- `DlnaEventService` 对并发 worker 与待处理通知上限增加类型、溢出和范围隔离，错误配置安全回退默认值。
- 保持既有 1–8 worker、1–256 pending 的资源边界，并新增协议回归。
- 通过完整离线回归 816 项 Python 测试及 Node/UI 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续封面缓存压力可观测性（2026-08-30，未发版）

- 在封面预热状态快照中增加内存缩略图缓存与 alias 缓存的条目数、占用字节和容量上限。
- 所有新增指标保持有界并隔离异常内部状态，支持定位大曲库封面加载压力来源。
- 通过封面缓存专项及完整离线回归 815 项 Python 测试和 Node/UI 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续随机队列策略边界拆分（2026-08-30，未发版）

- 新增 `ui/shuffle_policy.js`，将随机队列算法从 `app.js` 提取为可独立测试的纯策略，并加入输入数量与随机值边界。
- `app.js` 通过兼容入口调用新策略，未改变既有随机播放语义。
- 通过 Node/UI 回归及完整离线回归 814 项 Python 测试；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续播放会话对象形状恢复（2026-08-30，未发版）

- 修复状态投影函数结构回归，确保有界 JSON payload 正常解码。
- `load_user_state()` 对播放会话结果统一使用 mapping 投影；非对象或损坏 JSON 不再阻断状态恢复。
- 通过状态专项 26 项、完整离线回归 814 项 Python 测试及 Node/UI 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续状态文本子类异常隔离（2026-08-30，未发版）

- 状态文本投影对 strip 与编码长度检查增加异常隔离，损坏文本字段安全忽略。
- 通过状态投影及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续响应预算不可放宽（2026-08-30，未发版）

- JSON/XML 响应序列化拒绝通过更大的 maximum 绕过全局大小上限，保持服务端资源预算统一。
- 通过响应策略及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续状态投影递归异常隔离（2026-08-30，未发版）

- 状态 JSON 读写捕获 RecursionError，异常深度 payload 安全降级为空对象。
- 通过状态投影及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续磁盘保留路径边界（2026-08-30，未发版）

- disk_has_reserve 增加 4096 字符路径上限，避免异常输入放大路径解析和文件系统检查成本。
- 通过资源限制及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续并发门控等待时长恢复（2026-08-30，未发版）

- ConcurrencyGate 累计等待时长在写入前安全投影旧值，避免异常内部状态阻断资源门控。
- 通过资源限制及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续内存曲库排序策略容错（2026-08-30，未发版）

- 内存回退查询的 added/track_no 排序键隔离数值策略异常，损坏标签不会阻断列表排序。
- 通过内存曲库及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续分组查询值边界（2026-08-30，未发版）

- 分组查询策略限制专辑、歌手、作曲者和类型值长度，避免异常参数放大大曲库请求成本。
- 通过分组策略及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续扫描数值转换异常隔离（2026-08-30，未发版）

- safe_float/safe_int 对极端整数转换增加异常保护，扫描和排序遇到损坏数值时安全回退。
- 通过扫描数值及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续恢复手册版本一致性（2026-08-30，未发版）

- RECOVERY.md 修正过期版本提示，当前源码基线明确为 0.2.33，后续恢复以 VERSION 与 src/manifest 一致值为准。
- 通过发布治理及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续查询缓存失效键隔离（2026-08-30，未发版）

- invalidate_database 对异常内部缓存键进行安全检查，正常条目继续失效，避免曲库刷新流程被损坏缓存状态阻断。
- 通过查询缓存及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续曲库摘要计数策略拆分（2026-08-30，未发版）

- 将 library_meta 计数的有界投影抽至独立纯策略模块，保持损坏摘要自动回退精确统计。
- 通过策略、曲库 SQLite 及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续查询缓存损坏条目清理（2026-08-30，未发版）

- LibraryQueryCache 对不完整或异常内部 entry 进行安全清理和权重投影，保持缓存快照与淘汰路径稳定。
- 通过查询缓存及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续前端批请求统一并发策略（2026-08-30，未发版）

- 分页、分组、引用曲目补水和文件定位批处理统一复用批请求池默认并发常量，降低大曲库资源调参和审计复杂度。
- 通过前端专项及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续曲库摘要计数安全读取（2026-08-30，未发版）

- 分页热路径读取 library_meta 计数时隔离损坏行、布尔值和超大值，异常摘要自动回退精确 SQL 统计。
- 通过曲库 SQLite 及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续资源配置映射容错（2026-08-30，未发版）

- bounded_int 对异常配置 mapping 使用安全读取，避免资源门控初始化因 getter 错误失败。
- 通过资源限制及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续前端批请求池入池快照（2026-08-30，未发版）

- 批请求池对数组批次建立有限快照，避免大曲库补水过程中调用方修改原数组影响已调度请求。
- 通过前端专项及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续状态保存 payload 安全读取（2026-08-30，未发版）

- save_user_state 对异常 payload 使用安全字段读取，避免状态保存入口因类型异常阻断。
- 通过状态存储及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续并发门控快照安全投影（2026-08-30，未发版）

- ConcurrencyGate.snapshot 对内部资源指标增加统一有界投影，避免损坏状态阻断健康诊断。
- 通过资源限制及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续状态 revision 递增饱和（2026-08-30，未发版）

- state_store._next_revision 达到上限后保持饱和，避免状态版本长期递增越界。
- 通过状态存储及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续持久化严格 JSON（2026-08-30，未发版）

- state_projection.dump_json_bounded 使用 allow_nan=False，异常浮点状态安全回退为空对象。
- 通过状态投影及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续状态 revision 有界投影（2026-08-30，未发版）

- state_store._revision 增加损坏行隔离和 10^12 上限，避免异常 revision 影响状态冲突判断。
- 通过状态存储及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续状态数据库路径安全回退（2026-08-30，未发版）

- state_store 对缺失、异常和超长 cache_dir 使用安全回退，避免状态持久化入口因配置损坏阻断恢复。
- 通过状态存储及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续发布 provenance 结构校验（2026-08-29，未发版）

- verify_release_evidence.ps1 增加 provenance JSON 对象检查和 schema 转换隔离，损坏证据不会产生不可读的恢复异常。
- 通过发布脚本及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续查询缓存过期计数统一（2026-08-29，未发版）

- LibraryQueryCache._purge_expired 改用统一计数投影，批量清理不会绕过损坏统计保护。
- 通过查询缓存及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续查询缓存命中率快照容错（2026-08-29，未发版）

- LibraryQueryCache 命中率计算改用安全计数投影，刚初始化或损坏统计不会产生 NaN 或异常。
- 新增查询缓存回归；通过 792 项离线 Python 测试，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续播放状态兼容入口容错（2026-08-29，未发版）

- PlaybackCore.sync_frontend 对兼容 payload 使用安全读取，避免损坏映射或异常 duration 阻断状态机。
- 新增播放核心回归；通过完整离线测试，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续全量播放分页响应投影（2026-08-29，未发版）

- fetchAllTracksForCurrentView 对分页 items/count 使用安全投影和 200000 项上限，避免异常响应阻断“从当前开始播放所有歌曲”。
- 通过 Node/UI 及完整离线回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续查询缓存快照计数容错（2026-08-29，未发版）

- LibraryQueryCache 的统计计数在写入和快照输出前统一做有限、非负投影，隔离损坏内部状态。
- 新增查询缓存回归；通过 787 项离线 Python 测试及 UI 回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续可观测性累计值容错（2026-08-29，未发版）

- Observability 计数器和 HTTP 延迟摘要更新前增加有界投影，异常内部状态不会传播为请求失败。
- 新增可观测性回归；通过 787 项离线 Python 测试及 UI 回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续扫描状态快照安全读取（2026-08-29，未发版）

- library_status 不再直接索引 SCAN_STATE 的 running、last_error、last_scan 等字段；缺失或损坏状态安全回退并限制文本/时间戳输出。
- 新增曲库状态回归；通过 787 项离线 Python 测试及 UI 回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续发布证据文档索引（2026-08-29，未发版）

- docs/INDEX.md 新增 0.2.33 发布证据审计文档入口，便于恢复时定位历史产物状态。
- 未打包、未部署、未进行真实设备验收。

# 0.2.33 后续曲库状态端口投影（2026-08-29，未发版）

- library_status 对 server_port 使用统一有界端口策略，异常配置安全回退。
- 新增曲库状态回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续曲库缓存目录缺省回退（2026-08-29，未发版）

- 曲库 JSON/SQLite 路径辅助函数对缺失或无效 cache_dir 安全回退，保持状态读取可用。
- 新增曲库回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续缺省曲库路径状态回退（2026-08-29，未发版）

- library_status 对缺失曲库路径配置安全回退当前目录，避免状态读取抛出 KeyError。
- 新增曲库状态回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续元数据 Tag 计数输出统一（2026-08-29，未发版）

- 元数据状态响应对 tag_written 使用有界非负投影，保持统计字段一致。
- 新增元数据回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 历史发布证据审计（2026-08-29）

- 新增 docs/RELEASE_EVIDENCE_0.2.33.md，明确历史 FPK 的校验和状态与源码来源缺口。
- 未修改历史产物；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续元数据状态计数投影（2026-08-29，未发版）

- 元数据服务状态对队列计数和 Tag 写入平均耗时使用有界非负投影，保持健康响应稳定。
- 通过离线回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续封面预热队列长度异常隔离（2026-08-29，未发版）

- 封面预热快照捕获队列长度读取异常，损坏容器不会阻断健康/诊断接口。
- 新增封面缓存回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续发布 provenance 资源边界（2026-08-29，未发版）

- 发布证据 verifier 在解析 provenance 前增加 1 MiB 文件上限，保持恢复流程有界。
- 新增脚本契约；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续封面预热状态映射隔离（2026-08-29，未发版）

- 封面预热快照安全读取 worker 字段与队列长度，损坏状态自动回退为零值。
- 新增封面缓存回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续健康摘要上限转换容错（2026-08-29，未发版）

- nonnegative_int 对异常超大上限增加安全回退，健康与诊断摘要继续保持有界输出。
- 新增健康快照回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续封面预热压力计数隔离（2026-08-29，未发版）

- 封面预热状态快照统一采用安全压力计数投影，避免损坏 worker 状态阻断健康/诊断接口。
- 新增封面缓存回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 SQLite 摘要无效值正确回退（2026-08-29，未发版）

- 修正摘要计数投影顺序，确保无效/负数元数据继续触发 SQL 精确回退，有效值仍受统一上限保护。
- 通过离线回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续启动状态恢复边界统一（2026-08-29，未发版）

- localStorage 收藏与歌单启动恢复改用统一有界规范化策略，避免大数据绕过前端状态资源上限。
- 新增 Node 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 SQLite 摘要计数统一投影（2026-08-29，未发版）

- 曲库摘要元数据与 SQL 回退计数统一使用 safe_counter，异常大值安全回退并保持正常统计兼容。
- 通过离线回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续曲库摘要计数边界（2026-08-29，未发版）

- library_status 对曲库总数和 DSD 数量使用统一有界非负计数投影，保持正常响应兼容。
- 通过现有扫描数值与完整离线回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续资源计数器损坏状态隔离（2026-08-29，未发版）

- 并发资源门控计数器拒绝异常内部值，安全恢复递增并保持计数上限。
- 新增资源门控回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续扫描数值文本异常隔离（2026-08-29，未发版）

- safe_int 捕获极长数字文本的整数转换异常，扫描状态计数安全回退，不改变正常数值语义。
- 新增扫描数值回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续扫描状态计数边界（2026-08-29，未发版）

- `library_status()` 对 `scanned`/`found` 使用有界非负整数投影，防止异常扫描状态污染客户端或放大响应。
- 新增扫描数值策略回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 XML 客户端断开容错（2026-08-29，未发版）

- `Handler.send_xml()` 忽略客户端提前断开的 BrokenPipe/ConnectionReset。
- 新增 HTTP 回归测试；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 HTTP 错误页边界（2026-08-29，未发版）

- `Handler.send_error()` 限制错误文本长度并拒绝任意对象字符串化，降低异常响应资源放大风险。
- 新增 HTTP 回归测试；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 HTTP 错误策略边界拆分（2026-08-29，未发版）

- 新增 `http_error_policy.py` 承载错误文本有界投影，`server.py` 仅负责接线。
- 新增纯模块回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续分页总数边界（2026-08-29，未发版）

- 分页窗口结果和 COUNT 回退统一使用安全整数投影，异常总数自动走精确计数。
- 新增分页回归；未打包、未部署、未进行真实设备验收。

- 兼容旧 SQLite 的无窗口函数路径同样使用安全 COUNT 投影，保持两条执行路径的边界一致。

- 分页执行器隔离不可迭代窗口游标和异常回退游标，损坏驱动输入安全返回空页与有界计数。

- 补充捕获窗口游标迭代期运行时异常，兼容回退继续保持有界。

- 回退页面 SQL 发生 SQLite 错误时安全返回空页，不再将兼容驱动异常传播到 HTTP 请求。

- 计数游标读取期运行时异常安全降级为 0，补齐分页执行器最后一段异常边界。

- 补充隔离缺少游标方法的兼容驱动对象，分页请求保持空页/0 计数契约。

# 0.2.33 后续用户状态恢复边界（2026-08-29，未发版）

- 歌单恢复最多读取 1000 个歌单，每个歌单最多读取 10000 个曲目 ID，限制大音乐库状态恢复内存峰值。
- 收藏恢复同步限制为最多 50000 条，避免异常收藏表导致无界物化。

# 0.2.33 后续扫描错误快照边界（2026-08-29，未发版）

- 扫描状态读取改用有界错误快照投影，异常错误列表不会阻断状态/健康接口。
- 新增纯模块回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续播放队列边界（2026-08-29，未发版）

- 播放核心队列入口增加 50000 项上限并隔离异常迭代器，降低大队列状态更新的内存风险。
- 新增播放核心回归；未打包、未部署、未进行真实设备验收。

- 点播入口追加缺失曲目时复用 50000 项队列上限，满载时淘汰最旧项，避免绕过队列资源治理。

- 旧浏览器状态同步入口复用相同队列上限，统一迁移路径的资源边界。
- 新增状态存储回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 ALSA 能力文本读取边界（2026-08-29，未发版）

- `playback/alsa_output.py` 对 `/proc/asound` stream/codec 文本读取增加 64 KiB 上限。
- 新增离线回归；未打包、未部署、未进行真实 DAC 验收。

# 0.2.33 后续缓存键数值边界（2026-08-29，未发版）

- `library_query_cache_key.py` 对整数和有限浮点缓存参数增加 `10^12` 幅度上限，拒绝极端数值并保持正常分页兼容。
- 新增纯模块回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续缓存键标量输入边界（2026-08-29，未发版）

- `library_query_cache_key.py` 将不可迭代标量参数视为无效缓存键，避免整数等输入误复用空参数查询缓存。
- 新增纯模块回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续缓存键缺省参数边界（2026-08-29，未发版）

- `library_query_cache_key.py` 区分缺失参数 `None` 与合法空序列 `()`，避免非法调用复用无参数查询缓存。
- 新增纯模块回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续发布清单路径安全（2026-08-29，未发版）

- `verify_release_evidence.ps1` 拒绝源码清单中的绝对路径和 `..` 路径，避免恢复证据引用包外文件。
- 新增脚本契约回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 历史发布证据审计（2026-08-29）

- 只读验证确认历史 FPK 的 SHA256 有效，但缺少源码清单与 provenance；已记录为旧包恢复证据缺口，未修改或覆盖历史产物。

# 0.2.33 后续前端缓存键边界（2026-08-29，未发版）

- `item_cache.js` 对曲目缓存键增加非空字符串和 4096 字符上限，异常键安全忽略，保持正常缓存行为。
- 新增 Node/UI 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续查询缓存键模块拆分（2026-08-29，未发版）

- 新增 `library_query_cache_key.py`，独立承载查询缓存键的有界规范化策略，缓存类仅负责编排和统计。
- 新增纯模块回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续并发等待者唤醒竞态（2026-08-29，未发版）

- `ConcurrencyGate` 已入队等待者在虚假唤醒后不再重复计入等待者上限，避免错误抛出队列已满。
- 新增并发回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续查询缓存键一致性（2026-08-29，未发版）

- `library_query_cache.py` 对不支持的键值直接放弃缓存键，避免不同异常对象归一为 `None` 后错误复用缓存结果。
- 更新缓存回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 CI 源码清单治理（2026-08-29，未发版）

- GitHub Actions 在离线回归前执行 `update_source_manifest.ps1` 并验证清单无差异，阻断未同步源码清单的远程验证。
- 新增工作流契约回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续分页流式合并（2026-08-29，未发版）

- `fetchAllTracksForCurrentView()` 使用 `appendPageItems()` 逐页合并，不再缓存全部分页数组，达到总数或安全上限后提前结束。
- 新增 Node/UI 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续指标投影模块拆分（2026-08-29，未发版）

- 新增 `server/metrics_projection.py`，抽离健康 metrics 的递归边界和安全投影策略；健康响应仅保留编排职责。
- 新增纯模块回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续健康指标值边界（2026-08-29，未发版）

- `health_snapshot.py` 对 metrics 值增加递归深度、集合项、文本及数值上限，异常对象使用安全占位，不触发隐式字符串化。
- 新增纯模块回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续健康指标映射边界（2026-08-29，未发版）

- `health_snapshot.py` 对 metrics 顶层条目做有界复制（最多 256 个、键最长 256 字符），避免内部指标映射直接暴露或异常膨胀。
- 新增纯模块回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续搜索回退异常隔离（2026-08-29，未发版）

- `app.js` 在搜索投影模块不可用时逐字段安全读取曲目字段，代理/损坏对象不会中断列表筛选，并继续执行字段与总文本长度限制。
- 未打包、未部署、未进行真实设备验收。

# 0.2.33 后续可观测性指标键边界（2026-08-29，未发版）

- `observability_snapshot.py` 对自定义计数器名称增加 256 字符上限并拒绝空键，避免异常指标名称放大诊断响应。
- 新增纯模块回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续旧库缓存容器边界（2026-08-29，未发版）

- 旧版库缓存 `items` 列表长度访问增加异常隔离，损坏 list 子类会安全跳过，不阻断缓存恢复。
- 新增纯模块回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续旧库缓存条目规模边界（2026-08-29，未发版）

- `library_cache_payload.py` 对旧版缓存 `items` 增加 200,000 条上限，超大列表安全跳过，避免恢复阶段内存和 SQLite 写入压力。
- 新增纯模块回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续状态变更映射边界（2026-08-29，未发版）

- `_state_changes()` 对变更字段读取增加异常隔离，损坏同步映射安全回退，不阻断状态事务。
- 新增状态存储回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续旧库缓存策略拆分（2026-08-29，未发版）

- 新增 `server/library_cache_payload.py`，抽离旧版库缓存 JSON 形状与字段投影；`library.py` 保留有界读取和 SQLite 持久化编排。
- 新增纯模块回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续前端搜索回退边界（2026-08-29，未发版）

- `app.js` 搜索回退路径限制字段和总搜索文本长度，并拒绝异常对象隐式字符串化，降低大曲库搜索资源放大风险。
- 新增 Node 静态回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续兼容库缓存类型边界（2026-08-29，未发版）

- `load_library_cache()` 对合法但非对象 JSON 及非列表 `items` 增加类型隔离，畸形缓存安全跳过，不阻断曲库恢复。
- 新增曲库缓存回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续状态 JSON 编码边界（2026-08-29，未发版）

- 新增 `state_projection.dump_json_bounded()`，状态写入前限制 UTF-8 JSON 载荷为 2 MiB，超大或不可序列化对象安全回退为空 JSON。
- 新增纯模块回归并修复测试捕获的路径回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续列宽投影迭代边界（2026-08-29，未发版）

- UI 列宽配置对内部字典迭代器增加异常隔离，中途损坏不会阻断状态恢复，已处理列宽会保留。
- 新增纯模块回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续状态存储兼容入口清理（2026-08-29，未发版）

- 移除 `state_store.py` 中状态投影拆分后遗留的未使用 legacy 实现，改用明确的投影模块别名，降低维护歧义。
- 状态存储专项回归通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续纯投影迭代器边界（2026-08-29，未发版）

- `state_projection.py` 对歌单和 UI 偏好容器采用安全迭代，迭代中途异常时保留已处理项，避免损坏容器阻断状态同步。
- 新增纯模块回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续状态纯模块直接回归（2026-08-29，未发版）

- 新增 `test_state_projection.py`，直接覆盖状态投影模块的有界 JSON、字符串列表、歌单及 UI 偏好策略，确认核心边界可脱离 SQLite 单独验证。
- 未打包、未部署、未进行真实设备验收。

# 0.2.33 后续状态投影模块拆分（2026-08-29，未发版）

- 新增 `server/state_projection.py`，抽离持久化 JSON、文本列表、歌单和 UI 偏好的有界纯策略；`state_store.py` 继续提供兼容导入并负责 SQLite 事务。
- 状态存储回归通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 UI 偏好容器边界（2026-08-29，未发版）

- UI 偏好恢复对损坏顶层映射和 `.items()` 容器增加异常隔离，异常数据回退为空偏好，不阻断应用状态恢复。
- 新增状态存储回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 UI 偏好键边界（2026-08-29，未发版）

- 状态存储对 UI 列配置 scope/列名统一使用有限文本投影，拒绝异常对象字符串化和超长键，保持正常偏好兼容性。
- 新增状态存储回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续状态列表迭代边界（2026-08-29，未发版）

- `_strings()` 现在安全获取迭代器并隔离中途异常，已读取的收藏/歌单曲目 ID 会保留，损坏尾部不会阻断状态保存。
- 新增状态存储回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续状态记录异常隔离（2026-08-29，未发版）

- `_playlists()` 对损坏字典条目的字段访问增加异常隔离，单条坏记录会被跳过，后续有效歌单继续参与状态保存。
- 新增状态存储回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续状态文本投影边界（2026-08-29，未发版）

- 状态存储对收藏、歌单 ID/名称和曲目 ID 统一使用有限文本投影，拒绝非字符串与超过 4096 字节的异常单项，避免 SQLite 写入和响应资源放大。
- 正常状态兼容性保持不变；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续状态载荷恢复边界（2026-08-29，未发版）

- `state_store.py` 对持久化播放会话与 UI 偏好增加 2 MiB UTF-8 载荷上限，解码前拒绝超大/非文本输入，异常内容安全回退为空状态。
- 新增状态存储回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 APE 兼容读取边界（2026-08-29，未发版）

- 修复 `metadata_service._ape_existing_items()` 的无界整文件读取，统一复用 `_ape_tag_info()` 的有界 APE footer/item 解析，兼容行为保持不变。
- 新增大音频主体兼容入口回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续服务端 FNOS API 响应边界（2026-08-29，未发版）

- `fnos_api.py` 对 Trim Unix socket 响应增加 1 MiB 累计上限，HTTP 响应解析同步拒绝超限或非二进制输入，避免服务端直连系统接口时无界累积。
- 新增独立回归；完整离线门禁通过，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 CGI 本地配置读取边界（2026-08-29，未发版）

- CGI 端口探测与配置回显统一限制本地 JSON 候选文件为 2 MiB，并采用 `MAX_BYTES + 1` 有界读取；超限候选安全跳过，不阻断后续候选路径。
- 新增 CGI 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续客户端分页结果复用（2026-08-29，未发版）

- `app.js` 客户端分页视图一次生成总数与当前页曲目，工具栏和分页器复用同一结果，减少大音乐库 render 期间的重复补水、筛选和排序。
- Node/UI 与完整离线门禁通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续配置恢复读取边界（2026-08-29，未发版）

- `config.py` 对 `config.json` 增加 2 MiB 文件上限，并使用 `MAX_BYTES + 1` 二次有界读取；超限或损坏内容回退默认配置，避免恢复过程内存放大。
- 新增配置回归；完整离线门禁通过，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 CGI 网关响应边界（2026-08-29，未发版）

- Trim 网关 Unix socket 响应累计读取限制为 1 MiB，超限返回结构化 413，避免授权/文件接口异常响应无界累积。
- 完整离线门禁通过，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续嵌入歌词 ffprobe 输出边界（2026-08-29，未发版）

- `read_embedded_lyrics()` 使用临时文件承接 ffprobe 输出，最多读取 2 MiB + 1 字节后解析；超限输出安全跳过，避免异常命令输出造成内存放大。
- 新增元数据回归；完整离线门禁通过，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 APE item 解析复用（2026-08-29，未发版）

- `ape_tag_parser.py` 新增 `parse_ape_items()`，`parse_ape_body()` 与 `metadata_service._ape_tag_info()` 统一复用 item 边界解析，减少重复纯策略逻辑。
- APE/元数据专项测试：67 项通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 APE 标签解析边界拆分（2026-08-29，未发版）

- 新增 `ape_tag_parser.py` 纯解析模块，集中处理 APE footer/item 字节边界与畸形输入；`metadata_service.py` 的 `_ape_existing_items()` 保留兼容入口并委托新模块。
- 新增独立回归；完整离线门禁：660 项 Python 及全部 Node/UI 回归通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 CGI 配置响应读取边界（2026-08-29，未发版）

- CGI 保存配置路径对后端 JSON 响应增加 1 MiB 上限，超限返回结构化 413，避免异常响应被无界解码。
- 未改变普通 API/媒体转发行为；完整离线门禁通过，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 CGI 首页响应读取边界（2026-08-29，未发版）

- CGI 代理对需要注入 `<base>` 的首页响应增加 16 MiB 上限，并以 `MAX_BYTES + 1` 读取；超限返回 413，普通 API/媒体响应仍按块转发。
- 新增 CGI 回归；完整离线门禁：659 项 Python 及全部 Node/UI 回归通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续旧版 JSON 缓存读取边界（2026-08-29，未发版）

- `library.json` 仅作为兼容回退时增加 32 MiB 文件级上限，并采用 `MAX_BYTES + 1` 二次有界读取，避免异常缓存被整块解码或在竞态增长时造成内存放大；超限缓存不会覆盖现有内存索引。
- 专项库缓存测试：15 项通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续清单路径跨平台唯一性（2026-08-29，未发版）

- `verify_release_evidence.ps1` 对源码清单路径使用大小写不敏感唯一性校验，避免 Windows 恢复环境中的大小写差异绕过重复路径检测。
- 发布脚本回归及完整离线门禁通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续源码清单路径唯一性（2026-08-29，未发版）

- `verify_release_evidence.ps1` 现在拒绝同一源码路径对应多条哈希记录，避免恢复校验在冲突清单上给出错误可信度。
- 发布脚本回归及完整离线门禁通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 MP4 封面超大 atom 回退隔离（2026-08-29，未发版）

- MP4/M4A `covr` 解析发现超大 `data` atom 后不再执行兼容扫描回退，避免返回超限 atom 的前缀图像；新增媒体格式回归。
- 离线门禁：658 项 Python 测试及全部 Node/UI 回归通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 FFmpeg 封面流程边界拆分（2026-08-28，未发版）

- 新增 `ffmpeg_cover.py`，统一 M4A/WAV FFmpeg 封面提取的命令构造、8 MiB 输出限制、二次读取校验和临时文件清理；`library.py` 通过依赖注入保持既有测试与兼容入口。
- 新增纯模块回归；离线门禁：657 项 Python 测试及全部 Node/UI 回归通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续大曲库文件夹渲染去重（2026-08-28，未发版）

- `app.js` 的文件夹渲染现在复用 `render()` 已生成的 `folderState`，避免同一重绘再次执行目录筛选和曲目排序。
- Node/UI 及完整离线门禁通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续大曲库分组渲染去重（2026-08-28，未发版）

- `app.js` 的分组/专辑渲染现在复用 `render()` 已生成的分组数组，艺术家“所有歌曲”入口也复用同一结果，减少大曲库重绘期间的重复遍历。
- Node/UI 及完整离线门禁通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续发布清单唯一性校验（2026-08-28，未发版）

- `verify_release_evidence.ps1` 对 `SOURCE_MANIFEST.sha256` 增加重复记录拒绝逻辑，避免恢复核验接受被重复项污染的源码证据。
- 发布脚本回归及完整离线门禁通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续发布证据单记录约束（2026-08-28，未发版）

- `verify_release_evidence.ps1` 要求 `SHA256SUMS` 恰好一条记录，并限制 FPK 文件名为无空白、无路径分隔符的单一文件名，避免恢复核验误解析异常内容。
- 修正脚本契约回归；离线门禁通过，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 Vorbis 读取边界拆分（2026-08-28，未发版）

- 新增 `vorbis_reader.py`，集中承载 1 MiB 有界文件读取与注释解析；`library.py` 仅保留兼容委托，避免扫描器继续承担重复 I/O 逻辑。
- 新增独立回归；离线门禁：653 项 Python 测试及全部 Node/UI 回归通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 FFmpeg 封面输出二次边界（2026-08-28，未发版）

- M4A/WAV 封面提取在输出文件大小检查后增加 `MAX_COVER_FILE_BYTES + 1` 有界读取和二次校验，隔离 stat/open 竞态；新增媒体格式回归。
- 离线门禁：653 项 Python 测试及全部 Node/UI 回归通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续静态资源策略边界拆分（2026-08-28，未发版）

- 新增纯模块 `static_asset_policy.py`，集中承载 16 MiB 静态资源上限和安全整数校验；`server.py` 复用该策略，保持 413 与分块输出行为不变。
- 新增纯模块回归；离线门禁：652 项 Python 测试及全部 Node/UI 回归通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续静态资源服务边界（2026-08-28，未发版）

- `server.py` 的静态资源服务增加 16 MiB 文件上限，并改为 128 KiB 分块输出；超限资源在打开前返回 413，避免大文件整块读入内存。
- 新增 HTTP 回归；离线门禁：650 项 Python 测试及全部 Node/UI 回归通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续目录级封面读取边界（2026-08-28，未发版）

- `sidecar_cover.py` 对 `cover/folder` 图片增加 `MAX_SIDECAR_BYTES + 1` 有界读取，即使文件在 stat 与 open 之间被替换或增长，也不会无界分配；新增 2 项回归。
- 离线门禁：649 项 Python 测试及全部 Node/UI 回归通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续本地歌词读取边界（2026-08-28，未发版）

- `read_local_lyrics()` 统一限制本地 `.lrc` 读取为 2 MiB，超大文件在解码前拒绝，和网络歌词资源策略保持一致。
- 新增回归；离线门禁 646 项 Python 通过，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 Artwork 拒绝时保留原封面（2026-08-28，未发版）

- DSF/WAV 写回遇到超过 8 MiB 或不可读 artwork 时不再覆盖已有封面，资源保护与 Tag 完整性同时保持。
- 新增回归；离线门禁 645 项 Python 通过，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 Artwork 输入边界（2026-08-28，未发版）

- Tag 写回路径统一使用有界 artwork 读取，DSF/WAV/APE 及封面比较均拒绝超过 8 MiB 的本地图片，避免整块读取异常大文件。
- 新增超大 artwork 回归；离线门禁 644 项 Python 通过，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 APE 写回资源优化（2026-08-28，未发版）

- `_write_ape_tags()` 改为读取最多 16 MiB 的尾部 APE 标签并按 1 MiB 分块复制音频主体，降低大文件 Tag 写回峰值内存，保持既有标签合并行为。
- 新增大文件回归；离线门禁 643 项 Python 通过，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 DSF 写回资源优化（2026-08-28，未发版）

- `_write_dsf_tags()` 改为读取头部后分块复制元数据偏移前的 DSD 主体，避免高解析 DSF 写回时整文件驻留内存；标签与封面行为保持不变。
- 新增大文件夹具回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 CUE 文件读取边界（2026-08-28，未发版）

- 新增 `cue_reader.py`，CUE 文件读取限制为 8 MiB，超限内容在解码/解析前安全拒绝；`library.py` 保留兼容入口并复用新读取器。
- 新增读取回归；离线门禁 641 项 Python 通过，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续封面分派边界（2026-08-28，未发版）

- 新增 `cover_dispatch.py` 纯策略模块，`library.py` 的封面入口复用扩展名分派并限制路径输入，保持既有读取行为。
- 新增封面分派回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续发布包防覆盖（2026-08-28，未发版）

- `build_release.ps1` 新增同版本产物保护：发现已有 FPK 时默认终止，只有显式 `-AllowExistingArtifact` 才允许重建，避免发布治理误覆盖。
- 发布脚本回归通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续查询缓存拒存观测（2026-08-28，未发版）

- 健康/诊断的查询缓存摘要新增脱敏 `uncacheable` 计数，帮助定位缓存结果不可复制导致的拒存压力；新增快照回归。
- 未打包、未部署、未进行真实设备验收。

# 0.2.33 后续曲库搜索文本边界（2026-08-28，未发版）

- 新增 `track_search_text.js`，曲目搜索字段只接受安全字符串和有限数字，并限制字段/总文本长度；`app.js` 搜索匹配复用该投影，避免大曲库搜索重复分配和异常对象字符串化。
- 新增 Node 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续元数据提供商响应上限（2026-08-28，未发版）

- 元数据提供商 JSON 响应限制为 4 MiB，歌词响应限制为 2 MiB；gzip 解压后再次检查上限，超限安全失败，避免网络响应或压缩炸弹放大内存。
- 新增响应读取回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 ffprobe resolver 输入边界（2026-08-28，未发版）

- `probe_runner.py` 统一限制 ffprobe resolver 仅接受文本路径，resolver 抛错或返回非文本时安全转为 native fallback。
- 新增独立回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续快速音频探测边界拆分（2026-08-28，未发版）

- `probe_runner.py` 现在同时承载完整元数据探测与轻量音频信息探测；`read_audio_info()` 通过注入 resolver/native reader 复用输出上限和 fallback 语义，`library.py` 仅保留兼容包装。
- 探测回归通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续探测 fallback 容错（2026-08-28，未发版）

- `probe_runner.py` 对 native 音频信息 fallback 增加安全映射投影；读取器抛错或返回非字典时回退为空结果，不阻断扫描。
- 新增独立模块回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续扫描器导入清理（2026-08-28，未发版）

- 完成封面/ID3 边界拆分后清理 `library.py` 残留未使用解析导入，避免扫描器继续隐式承担已迁移职责；行为不变。
- 离线门禁回归通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续发布证据版本绑定（2026-08-28，未发版）

- `verify_release_evidence.ps1` 现在校验 provenance 的语义版本，并要求 FPK 文件名严格匹配 `fnaudio-<version>-fnpack.fpk`；恢复旧会话时可避免跨版本证据误配。
- 新增脚本契约回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 ffprobe 执行边界拆分（2026-08-28，未发版）

- 新增 `server/probe_runner.py`，承载有界 ffprobe 执行、JSON 输出限制与 native 音频信息合并；`library.py` 通过兼容包装注入解析依赖，保留 API 行为并可独立测试。
- 元数据与媒体回归通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续音频探测输出边界（2026-08-28，未发版）

- `read_audio_info()` 的 ffprobe 快速路径现在复用 2 MiB 输出上限，超大 JSON 安全回退空结果，避免与完整元数据探测路径的资源策略不一致。
- 新增媒体格式回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续侧车封面边界拆分（2026-08-28，未发版）

- 新增 `server/sidecar_cover.py`，承载 `cover.jpg`/`folder.jpg` 等侧车封面发现、路径隔离和 8 MiB 文件上限；`library.py` 保留兼容导入。
- 媒体格式与 HTTP 回归通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 FFmpeg 封面输出边界（2026-08-28，未发版）

- M4A/WAV 的 FFmpeg 封面提取在命令阶段加入 `-fs` 8 MiB 输出上限，并保留事后大小检查，降低临时文件磁盘峰值。
- 新增命令契约回归；离线门禁共 629 项 Python 测试及全部 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 MP4 atom 递归边界（2026-08-28，未发版）

- M4A/MP4 封面 atom 解析增加 32 层递归深度上限，深层畸形容器安全返回空封面，避免递归栈资源放大。
- 新增媒体格式回归；离线门禁共 628 项 Python 测试及全部 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 ID3 读取策略集中（2026-08-28，未发版）

- `id3_container.py` 现在同时承载 ID3 定位、ID3v1 回退、文本 Tag 解析和封面解析入口；`library.py` 仅保留兼容导入与扫描编排，避免容器规则散落。
- 媒体格式与元数据回归通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 ID3 payload 资源上限（2026-08-28，未发版）

- `id3_container.py` 对 ID3 头部声明的 payload 增加 16 MiB 上限，超大或损坏声明安全拒绝，避免扫描时按异常长度读取。
- 新增媒体格式回归；离线门禁共 627 项 Python 测试及全部 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 ID3 容器读取边界拆分（2026-08-28，未发版）

- 新增 `server/id3_container.py`，承载 MP3 起始、WAV-RIFF `id3 ` 块及 DSF metadata offset 的 ID3 定位，并保留 `id3_payload()`、`id3_tag()`、`read_id3_cover()` 兼容导出。
- 新增模块回归；离线门禁共 626 项 Python 测试及全部 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续容器封面读取边界拆分（2026-08-28，未发版）

- 新增 `server/cover_readers.py`，承载 FLAC 图片块和 APEv2 封面读取；`library.py` 保留兼容导入并继续负责扫描编排。两种读取器沿用既有 8 MiB 图片块/16 MiB APE 标签上限。
- 新增模块身份与异常输入回归；离线门禁共 626 项 Python 测试及全部 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续封面读取资源边界（2026-08-28，未发版）

- 封面读取路径增加有界资源策略：FLAC 单个元数据块、APEv2 标签、FFmpeg 临时图像及侧车封面均设置上限；APE 先读取尾部目录再按标签长度读取，避免扫描整份音频文件。
- 新增媒体格式回归；离线门禁共 625 项 Python 测试及全部 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续扫描结果排序边界拆分（2026-08-28，未发版）

- 将多根扫描结果的稳定排序抽至 `server/library_scan_results.py::sort_scan_items()`，统一普通扫描与最终聚合排序；艺术家、专辑、标题和 ID 字段采用有界文本投影，异常记录安全回退且不修改输入列表。
- 新增纯模块回归；离线门禁共 623 项 Python 测试及全部 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续签名摘要策略拆分（2026-08-28，未发版）

- 新增纯函数 `digest_signature_parts()`，统一普通扫描与快速文件状态签名的排序、文本/条目上限和 SHA-1 摘要逻辑，避免边界漂移。
- 新增独立回归；离线门禁 622 项 Python 测试及全部 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续旧索引路径映射边界拆分（2026-08-28，未发版）

- 将 `library.py::scan_library()` 的旧索引路径映射抽至纯函数 `build_previous_item_index()`；异常迭代器、损坏记录和异常 `path` 访问均隔离，扫描器只消费安全映射。
- 新增纯模块回归；离线门禁 621 项 Python 测试及全部 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续扫描 ID 文本边界（2026-08-28，未发版）

- 扫描结果去重对字符串曲目 ID 限制为 4096 字符，超长损坏 ID 安全跳过，避免集合、排序和缓存键资源放大。
- 新增纯模块回归；离线门禁 619 项 Python 测试及全部 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续扫描排序文本边界（2026-08-28，未发版）

- 扫描结果排序键对艺术家、专辑、标题和 ID 文本限制为 4096 字符后再执行大小写折叠，避免异常元数据放大排序资源。
- 新增纯模块回归；离线门禁 618 项 Python 测试及全部 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续扫描分区生成器边界（2026-08-28，未发版）

- 多根扫描分区生成器改为逐项读取并隔离中途异常；异常发生时保留已完成的根分区结果，避免坏缓存丢失整批可复用索引。
- 新增纯模块回归；离线门禁 617 项 Python 测试及全部 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续扫描 items 迭代边界（2026-08-28，未发版）

- 扫描结果曲目生成器改为逐项读取并隔离中途异常；异常发生时保留已成功读取的记录，避免坏索引丢失整批可用结果。
- 新增纯模块回归；离线门禁 616 项 Python 测试及全部 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续扫描签名文本边界（2026-08-28，未发版）

- 扫描签名聚合将单条签名文本限制为 4096 字符，并保留 200,000 条总量上限，避免异常输入在排序和摘要拼接时造成资源放大。
- 新增纯模块回归；离线门禁 615 项 Python 测试及全部 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续扫描 ID 哈希容错（2026-08-28，未发版）

- 多根扫描结果去重对曲目 ID 的哈希、集合查找和插入统一进行异常隔离；异常 ID 安全跳过，避免损坏数据中断扫描聚合。
- 新增纯模块回归；离线门禁 614 项 Python 测试及全部 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续扫描分区路径容错（2026-08-28，未发版）

- 多根扫描分区对历史记录 `path` 字段访问异常安全跳过当前记录，避免损坏映射中断分区并保留后续有效记录处理。
- 新增纯模块回归；离线门禁 613 项 Python 测试及全部 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续扫描去重 ID 容错（2026-08-28，未发版）

- 多根扫描结果去重对曲目 ID 字典访问异常安全跳过当前记录，避免损坏映射在去重阶段中断整批扫描。
- 新增纯模块回归；离线门禁 612 项 Python 测试及全部 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续扫描签名迭代边界（2026-08-28，未发版）

- 扫描签名聚合最多处理 200,000 条签名，并对生成器中途异常安全停止；正常输入的摘要算法与排序语义不变，损坏迭代器不会阻断扫描收尾。
- 新增纯模块回归；离线门禁 611 项 Python 测试及全部 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续扫描排序字段容错（2026-08-28，未发版）

- 多根扫描结果排序键对异常字典子类访问逐字段隔离；损坏记录安全使用空排序值，不会阻断整批结果排序。
- 新增纯模块回归；离线门禁 610 项 Python 测试及全部 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续历史扫描迭代器边界（2026-08-28，未发版）

- 多根扫描恢复对异常历史 `items` 迭代器安全回退为空迭代器，避免损坏缓存中断根目录分区和后续扫描。
- 新增纯模块回归；离线门禁 609 项 Python 测试及全部 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续扫描结果稳定排序（2026-08-28，未发版）

- 多根扫描结果最终排序增加稳定 `id` 末级键；艺术家、专辑和曲名相同的记录不再因输入顺序变化而抖动，降低大曲库分页与前端缓存重排开销。
- 新增排序稳定性纯模块回归；离线门禁 608 项 Python 测试及全部 Node 回归通过。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续音频指纹输入边界（2026-08-28，未发版）

- 音频指纹任务对 fpcalc 超时、返回时长和 JSON 结构增加安全边界；异常配置或畸形输出安全失败。新增指纹回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续扫描元数据展示边界拆分（2026-08-27，未发版）

- `library.py` 的 `read_metadata()` 将已读取 Tag、文件名回退、分组路径和来源标记的纯记录组装移至 `server/library_metadata_presentation.py`；文件探测、本地 Tag 回退和路径计算仍留在扫描器。
- 新增 Tag 优先、文件名/未知值回退和输入不变性回归，并复跑既有 SQLite 扫描回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续查询缓存观测字段补齐（2026-08-27，未发版）

- 查询缓存状态摘要命中时同步返回最新命中/未命中、逐出、过期、失效和超大页计数，并新增短期摘要年龄 `age_ms`；不改变页面缓存 TTL、容量和失效语义。
- 新增缓存快照年龄、计数刷新及 health/diagnostics 投影回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续查询缓存状态降载（2026-08-27，未发版）

- `LibraryQueryCache.snapshot()` 采用 750ms 线程安全摘要，避免 `/api/health` 与 `/api/diagnostics` 的短周期读取重复遍历最多 4096 条页面缓存执行过期清理。
- 普通页读取的命中/未命中不再使摘要自我失效；写入、淘汰、过期和数据库失效仍立即清除摘要。公开 library 摘要仅投影 TTL、年龄、命中/未命中等受限指标。新增缓存合并、读取稳定性与公开字段回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续外部 Renderer 监控策略拆分（2026-08-27，未发版）

- 将 DLNA/UPnP Renderer 监控使用的媒体 URI 队列 ID 解析、手动停止抑制和无进度到期判定移至 `server/remote_output_monitor_policy.py`；`server.py` 保持兼容包装和播放自动推进编排。
- 新策略拒绝非文本、布尔值、NaN 与无穷数，防止异常设备状态误触发停止抑制或自动下一曲。新增独立纯模块回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续元数据状态聚合降载（2026-08-27，未发版）

- `MetadataService.status()` 的多项 SQLite 聚合加入 750ms 线程安全快照；并发的 health、diagnostics 与元数据状态读取会等待并复用同一结果，避免短周期重复 `GROUP BY`、总量和 Tag 写入关联查询。
- job 领取/完成/重试/入队及实体、歌词、候选匹配持久化会主动失效快照；缓存值与调用方返回值均隔离，避免 API 消费方修改污染下一次状态。health/diagnostics 仅投影 TTL、年龄、命中和未命中数，不含路径、任务内容或凭据。新增聚合合并、失效、隔离与公开摘要回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续根目录摘要解析边界拆分（2026-08-27，未发版）

- 根目录浏览持久化摘要的 JSON 解析、长度限制、配置根完整性与字段验证抽至 `server/library_root_summary.py`；`library.py` 只决定采用摘要还是回退 SQLite 聚合。
- 负数计数安全归零，损坏、超长、根不匹配和非文本封面 ID 均回退，不会造成根目录页错误。新增纯模块回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续长播放队列补水边界（2026-08-27，未发版）

- `query_library_items_by_ids()` 对内部播放恢复不再使用一个无上限 SQLite `IN (...)`；受限文本 ID 在同一连接内按 120 项分批查询，并以首次请求顺序返回，避免长队列超过 SQLite 变量限制。
- HTTP `/api/library/items` 的既有 120 项限制保持不变。新增 125 项队列分批、顺序保持及非文本对象不字符串化回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 SQLite 分页执行边界拆分（2026-08-27，未发版）

- 将窗口分页的一次查询路径、越界精确计数和旧 SQLite 无窗口函数回退从 `library.py` 抽至 `server/library_pagination.py`；歌曲、分组和文件夹浏览继续共享同一行为。
- 新增无 SQLite 文件依赖的伪连接回归，直接锁定正常窗口结果、空页计数和兼容回退顺序；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续筛选歌曲分页降载（2026-08-27，未发版）

- 搜索、专辑/歌手/作曲家/类型和目录筛选后的歌曲分页改用 `COUNT(*) OVER()` 在正常非空页一次获取总数与曲目 JSON，避免每次筛选浏览重复 COUNT。
- 无筛选全库/DSD 的已保存计数快捷路径不变；空越界页或旧 SQLite 无窗口函数时仍精确回退“计数 + 取页”。新增筛选分页 trace 与兼容回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续大库根摘要基准复测（2026-08-27，未发版）

- 10 万首合成 SQLite 基准增加根目录摘要路径校验，并更新 `artifacts/large-library-benchmark-100k.json`。本机首/中/尾 120 项分页合计 `0.383s`、Python 峰值 `608,455` 字节；根摘要读取 `0.004s`，FTS5 trigram `0.019s`、LIKE `0.296s`。
- 基准继续只代表本机离线 SQLite 证据，不替代真实 NAS 或设备验收；新增根摘要结果断言，防止后续基准夹带与运行环境不一致的根路径。

# 0.2.33 后续根目录浏览摘要降载（2026-08-27，未发版）

- 扫描保存索引时会持久化每个配置音乐库根的曲目数和稳定封面曲目 ID；根目录页在缓存未命中时直接读取该小摘要，避免大库反复执行 `tracks GROUP BY root`。
- 旧索引没有摘要、摘要损坏或配置根不匹配时自动回退原有 SQLite 聚合，结果结构不变。根摘要构建抽入 `library_write.py` 纯函数，并补充摘要命中、回退和独立测试导入回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 FFmpeg 资源压力可观测性（2026-08-27，未发版）

- `ConcurrencyGate` 新增 `timed_out` 计数，和已有的总拒绝数、等待队列满拒绝数分开记录；转码摘要、health 和 diagnostics 同步公开该受限数值。
- 支持定位“并发任务执行过慢”与“等待队列容量不足”两类不同压力，不暴露任务路径、命令或媒体信息。新增资源门禁与摘要回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续普通分组/文件夹分页降载（2026-08-27，未发版）

- 普通专辑、歌手、作曲家、类型及文件夹的非空分页也改为 `COUNT(*) OVER()` 一次查询携带总数，减少大音乐库分类浏览的重复 COUNT。
- 新增统一分页窗口辅助函数；越界空页和旧 SQLite 缺少窗口函数时继续使用精确 COUNT 加取页回退，API 字段与排序不变。新增普通分组、文件夹与无窗口函数回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续大库作者专辑分页降载（2026-08-27，未发版）

- 按艺术家或作曲家筛选的专辑分页优先用 `COUNT(*) OVER()` 随分组结果返回总数，正常页面不再执行两次相同 scoped/matched CTE（一次计数、一次取页）。
- 异常越界空页保留精确 COUNT 回退；旧 SQLite 缺少窗口函数时捕获其错误并自动使用原有精确 COUNT 加取页双查询，API 响应字段不变。新增 SQLite trace、越界页和无窗口函数兼容回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续大收藏/歌单详情缓存降载（2026-08-27，未发版）

- `resolveTracksByIds()` 的 100 项批量补水改为所有批次先写入 `itemCache`，随后只进行一次带当前播放队列保护的 LRU trim；避免长收藏/歌单每批重复扫描超限缓存。
- 保持请求 4 并发、批次顺序、最终 ID 顺序和播放语义。新增 Node 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续大库元数据实体集合内存优化（2026-08-27，未发版）

- reconciliation 的 album/artist/composer 活动集合改为在 SQLite 临时表中边遍历边写入，不再在 Python 中累积完整 `active_entities` 后再批量插入。
- 当前歌曲的单专辑优先路径保留兼容调用；实体孤儿清理与作业创建语义不变。新增多实体回归验证临时表写入及入队数量；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续大库元数据协调内存优化（2026-08-27，未发版）

- reconciliation 现在在 SQLite 临时表中通过 `INSERT … SELECT id FROM tracks` 建立活动曲目集合，并流式处理曲目，不再同时物化完整曲目行列表和活动 ID 元组列表。
- metadata track/job/match 的孤儿清理和新建 lyrics 任务语义保持。新增 SQLite 临时集合与完整入队回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续大库元数据协调降载（2026-08-27，未发版）

- 元数据 reconciliation 在同一 SQLite 事务中复用 `metadata_max_pending_jobs` 的当前 pending 快照；新建大量 lyrics/track/分组任务时不再对同一状态索引重复执行 `COUNT(*)`。
- 队列容量、普通任务拒绝、当前歌曲高优先级逐出以及单次直接交互插入的数据库权威计数均保持原语义。新增多曲目回归锁定每轮协调只读取一次 pending 计数；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续分组/目录查询规范统一（2026-08-27，未发版）

- `library_query_spec` 新增独立的分组、目录和根目录浏览规范；`query_library_groups()` 与 `query_library_folders()` 不再自行字符串化输入，分页、排序、搜索、作者/作曲者和路径参数在构造 SQLite 条件及缓存键前统一受限。
- 兼容有限数字文本和原有默认分页；异常对象、无穷/布尔数值安全回退。新增纯规范和 SQLite 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续大库全量播放首屏复用（2026-08-27，未发版）

- `fetchAllTracksForCurrentView()` 的第 0 页改为复用现有 `libraryResponseCache`；列表首页刚渲染后发起“从当前开始播放全部歌曲”不再重复前端 JSON 解析和服务端 SQLite 首页读取。
- 全量分页的 4 并发、排序合并、歌曲详情缓存与现有刷新/扫描/写入失效规则保持不变。新增 Node 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 health/diagnostics 摘要边界统一（2026-08-27，未发版）

- 新增 `server/summary_values.py`，health、support diagnostics、library/transcode 摘要统一只接受受限文本和有限数值；不会为展示状态调用依赖对象的 `__str__`、`__int__` 或 `__float__`。
- 既有有限数字字符串兼容保留；NaN、无穷、负值、布尔值和异常对象安全降级。新增 health/diagnostics 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 HTTP 延迟指标数值治理（2026-08-27，未发版）

- `Observability.record_http_latency()` 的耗时与慢请求阈值改为仅接收有限的基础数值；NaN、无穷大、负数、布尔值和自定义对象安全降级为零。
- 防止异常时间输入污染 support diagnostics/health 的 JSON 指标或在高频请求路径触发任意对象转换。新增可观测性回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续服务端大库缓存权重上限（2026-08-27，未发版）

- `LibraryQueryCache` 在原有条目数量上限外增加结果内容权重上限（默认 6000，最高 200000）。歌曲、分组和目录列表按条目数计重；超过预算的单页仅用于当前响应，不进入缓存。
- 查询缓存快照及 health/diagnostics 固定投影新增 `weight`、`weight_limit`、`oversized`，可观察内容压力而不暴露歌曲或路径。新增缓存逐出、超大页拒存和摘要回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续发布证据与 PowerShell 门禁（2026-08-27，未发版）

- `SOURCE_PROVENANCE.json` 新增 `fnpack_sha256`，记录实际 FPK 打包器二进制哈希；发布验证要求它为有效 SHA-256，使删除会话后的构建复现不只依赖源码和 Git 状态。
- `tools/test_offline.ps1` 在不打包的默认门禁中解析所有 `tools/*.ps1`，提前捕获发布与部署脚本的 PowerShell 语法错误。新增静态契约；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续服务端查询缓存键边界（2026-08-27，未发版）

- `LibraryQueryCache` 缓存键改为只接收文本路径/命名空间与有限基础类型值：文本截断到 4096 字符，值迭代最多 32 项；非法数据库路径或命名空间直接跳过缓存。
- 这避免异常对象触发字符串化，也避免未知调用方用无界迭代器扩大常驻 LRU 键。新增回归覆盖异常输入、长文本与迭代上限；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续前端大库缓存双上限（2026-08-27，未发版）

- 通用 LRU 支持可选内容权重；音乐库响应缓存保留 48 条请求上限，同时限制歌曲、分组和目录的累计列表条目为 6000。
- 单个超过权重预算的响应不缓存，但保持当前请求的正常渲染；避免一页异常大列表把 WebView 中全部热点分页驱逐。新增 Node 回归与静态调用契约；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续大库查询参数资源边界（2026-08-27，未发版）

- `library_query_spec.py` 新增受限文本规范化：分页视图、分组、专辑、目录、根、搜索、排序仅接受文本且按用途截断；搜索/分组最多 512 字符，目录/根最多 4096 字符。
- 按 ID 补水拒绝非文本、过长总输入和过长单项 ID，避免异常输入进入 SQLite 占位符或查询缓存键。新增纯模块、HTTP 与 SQLite 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续根目录浏览缓存（2026-08-27，未发版）

- `query_library_root_folders()` 接入既有失效感知查询缓存；多根目录的首页不再在短时间内反复执行 tracks 按 root 的聚合查询。
- 缓存键包含规范化搜索词，SQLite 索引保存沿用既有全库缓存失效路径。新增回归验证第二次读取不连接数据库、索引写入后返回新的曲目统计；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 HTTP 观测策略边界拆分（2026-08-27，未发版）

- 新增 server/http_request_policy.py，将请求路径的固定指标分桶和是否写入同步 JSONL 的规则从 observability.py 抽离；Observability 继续负责有界计数、延迟聚合与安全落盘。
- 策略只接受文本 path/method 与整数状态码，避免对异常对象调用 str()；既有成功播放状态/SSE 不写同步日志的性能语义保持。新增模块级回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续大库分组/目录基准扩展（2026-08-27，未发版）

- `tools/benchmark_large_library.py` 的合成 SQLite 场景现创建根目录、目录层级、分组索引与 FTS 搜索索引，并验证专辑分页、顶层目录分页和精确子串搜索的返回边界。
- 100,000 条离线结果已保存到 `artifacts/large-library-benchmark-100k.json`：三页 120 项分页合计 `0.289s`、Python 峰值 `579,248` 字节；专辑/目录浏览 `0.009s`；FTS5 trigram `0.012s`，LIKE 对照 `0.258s`。新增单测锁定分组、目录与搜索结果；仅为离线证据，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 ffprobe JSON 边界拆分（2026-08-26，未发版）

- ffprobe JSON 的 format/stream Tag 合并、别名归一化和采样率/位深/码率/时长解析已抽至 `server/probe_metadata.py`。原有流 Tag 覆盖 format Tag 的优先级保持不变，`library.py` 仅保留受限 subprocess 与 native fallback。
- 新增纯模块回归覆盖多源 Tag 合并、音频字段 coercion 和空 payload；源码清单刷新后完整离线门禁通过：363 项 Python 与全部 Node/UI 回归。

# 0.2.33 后续元数据探测去重（2026-08-26，未发版）

- `read_metadata()` 在 ffprobe 已提供 title/artist/album/composer/genre/track_no 六项核心字段时跳过第二次整文件 ID3/Vorbis 读取，降低大库扫描的磁盘 I/O；字段不完整或 probe 失败时仍保留原生 Tag 补缺。
- 新增回归覆盖完整 probe 跳过和缺失字段回退；源码清单刷新后完整离线门禁通过：361 项 Python 与全部 Node/UI 回归。

# 0.2.33 后续 ffprobe Tag 归一化边界拆分（2026-08-26，未发版）

- ffprobe/容器 Tag 的 title、artist、album、composer、genre、track_no 别名处理已抽至 `server/metadata_text.py::normalize_probe_tags()`。现有扫描结果和后台元数据服务继续使用相同优先级。
- 新增纯函数回归覆盖 ID3/MP4 常见别名、序号分母格式和未知字段忽略；源码清单刷新后完整离线门禁通过：360 项 Python 与全部 Node/UI 回归。

# 0.2.33 后续前端详情缓存上限（2026-08-26，未发版）

- `app.js` 的歌曲详情 `itemCache` 现在最多保留 12,000 项；命中会刷新 LRU 热度，超限时优先淘汰旧补水项，当前播放队列不会被淘汰。
- 新增 UI 回归锁定缓存上限、受保护队列和读命中触碰热度，降低大收藏/歌单在 WebView 中持续增长的内存风险。

# 0.2.33 后续原生音频信息边界拆分（2026-08-25，未发版）

- WAV/DFF 的无外部依赖容器信息读取从 `library.py` 抽至 `server/native_audio_info.py`。扫描与播放前音频信息读取继续通过兼容入口复用同一实现，不触及 DAC/DSD 实体输出链路。
- 新增纯离线 WAV 容器回归，覆盖采样率、位深、码率、时长和无效文件；源码清单刷新后完整离线门禁通过：359 项 Python 与全部 Node/UI 回归。

# 0.2.33 后续元数据文本边界拆分（2026-08-25，未发版）

- Tag 文本清洗、曲目序号解析、文件名 artist/title 推断和 CUE 文本辅助逻辑从 `library.py` 抽至无 I/O 的 `server/metadata_text.py`；扫描和后台元数据任务复用同一个 `parse_track_number()`，避免规则悄然分叉。
- 新增纯模块回归覆盖空字符、序号、文件名和 CUE 文本语义；源码清单刷新后完整离线门禁通过：357 项 Python 与全部 Node/UI 回归。

# 0.2.33 后续扫描控制边界拆分（2026-08-25，未发版）

- 音乐库扫描的取消、无进展超时与 deadline 续期从巨大的 `library.py` 抽至 `server/scan_control.py`；扫描状态仍由 `library.py` 注入，因此 API 进度字段与既有取消语义不变。
- 新增独立回归覆盖 deadline 状态续期、超时和取消，不涉及真实设备或媒体文件；源码清单刷新后完整离线门禁通过：354 项 Python 与全部 Node/UI 回归。

# 0.2.33 后续分页连接去重（2026-08-25，未发版）

- SQLite 分页查询的“库是否为空”预检不再单独打开一次连接；缓存未命中时，分页的 count、空库内存回退判定和数据行读取现在共用同一连接，减少常规分类/翻页的一次连接、schema 检查和文件锁往返。
- 新增回归固定正常分页缓存未命中只打开一个 SQLite 连接；源码清单刷新后完整离线门禁通过：355 项 Python 与全部 Node/UI 回归。

# 0.2.33 后续封面去重锁生命周期（2026-08-25，未发版）

- 封面缩略图按曲目版本去重的 `_LOCKS` 由强引用字典改为 `WeakValueDictionary`。同一 key 的并发生成仍共享一把锁；请求结束后不再让旧文件版本、Tag/封面更新历史永久占用锁表。
- 新增 GC 生命周期回归以及完整封面缓存定向回归通过；完整离线门禁待本轮源码清单刷新后执行。

# 0.2.33 后续静态资源日志去瓶颈（2026-08-25，未发版）

- HTTP 指标继续统计每一项请求，但成功的静态 GET/HEAD（封面、媒体 Range、UI 文件）不再逐项进入同步 JSONL 写入路径。
- API 请求、任意写操作以及所有失败响应仍保留结构化日志、请求 ID、固定路由类别和耗时；可观测性不被删除，只避免 120 张列表封面同时触发文件锁与落盘。
- observability 与真实 HTTP handler 定向回归通过，覆盖缩略图请求不写日志、失败静态请求仍写日志；源码清单刷新后完整离线门禁通过：353 项 Python 与全部 Node/UI 回归。

# 0.2.33 后续歌曲详情补水资源上限（2026-08-25，未发版）

- `library_query_spec.py` 新增可复用的 ID 列表规范化：稳定去重、跳过空值，并将一次歌曲详情请求限制为 120 项。
- `/api/library/items` 在数据库查询前拒绝超限请求（HTTP 400），避免不受约束的 URL/参数数量导致 SQLite 错误或补水请求占用过多资源；现有 Web/Android 100 项分批不受影响。
- 查询规范和真实 HTTP Handler 定向回归通过；源码清单刷新后完整离线门禁通过：353 项 Python 与全部 Node/UI 回归。

# 0.2.33 后续分类详情页索引优化（2026-08-25，未发版）

- 歌手、作曲家、专辑、类型详情页原来以 `COALESCE(NULLIF(column,''), ?)` 过滤，SQLite 无法使用普通分组索引，容易在大库分类点击时退化为扫描。
- 普通分组名称现在采用直接 `column = ?` 条件；仅“未分类”保留显式的真实标签/空字符串/NULL 三分支，结果语义不变。歌手专辑 CTE 同步复用此条件。
- 新增 SQL 语义与 `EXPLAIN QUERY PLAN` 回归，确认普通歌手页使用 `idx_tracks_artist`；SQLite 定向回归与完整离线门禁通过：353 项 Python 与全部 Node/UI 回归。

# 0.2.33 后续列表封面调度模块拆分（2026-08-25，未发版）

- 新增 `ui/cover_load_scheduler.js`，将分页列表封面的 IntersectionObserver、翻页取消、280px 预取窗口及 4 并发队列从 `app.js` 抽离；现在严格限于歌曲列表图片，避免无关封面进入队列。
- 新增调度器独立 Node 回归，并纳入 `tools/test_offline.ps1`；保留旧行为：可见封面优先于预取封面、旧页面任务不会启动新页面已移除的节点。
- 隔离 `fnpack` 发布验证通过：`artifacts/_scratch/cover-scheduler-release-20260825-2/0.2.33/fnaudio-0.2.33-fnpack.fpk`，SHA-256 `ACA892F1EAED207232777B78678C82DEEB52BDD6879BA293C5E0BEF39C98EF3A`。自动资源发现、缓存构建标记、暂存源码 manifest、provenance 与解包校验均成功；未覆盖正式包或部署。

# 0.2.33 后续引用曲目补水重绘去重（2026-08-25，未发版）

- 修复收藏和自建歌单的引用曲目补水流程：单批返回曲目此前会首批渲染一次、循环结束后无条件再重绘一次。
- 现在仅在首批之后确有后续批次新增行时执行最终补齐重绘，保留大播放列表的渐进显示，同时避免常见小列表的无效 DOM 重建、封面 observer 重置和布局计算。
- Node 加载回归及 JavaScript 语法检查通过；完整离线门禁待本轮源码清单刷新后执行。

# 0.2.33 后续音乐库路径模块拆分（2026-08-25，未发版）

- 新增 `server/library_paths.py`：扫描、SQLite 与设置 API 共用的路径准入、标准化、多根目录合并、旧配置兼容、根目录显示名与相对目录计算从 `library.py` 分离。
- `library.py` 保留导入后的兼容导出，既有扫描和调用方无需改名；`server.py` 改为直接依赖路径模块，降低 HTTP 设置与扫描逻辑再次漂移的风险。
- 新增路径模块独立回归，并与 library cache、HTTP integration 定向回归通过；完整离线门禁待本轮源码清单刷新后执行。

# 0.2.33 后续服务端请求延迟观测（2026-08-25，未发版）

- `Observability` 新增固定、有界的 `http_latency` 聚合：音乐库分页/分组/目录/根目录、封面、播放、静态和其他八类分别输出请求数、平均/最大耗时与慢请求数。
- HTTP 生命周期统一由 Handler 包裹 GET、HEAD、POST、DLNA 订阅与错误路径；普通静态/媒体响应不再因未调用 JSON helper 而漏记。指标不保存查询参数、文件路径、歌曲名或 token；结构化日志只增加固定 `latency_route` 与 `duration_ms`。
- 定向 Python 回归通过（16 项：observability 与真实 HTTP handler）；完整离线门禁待本轮源码清单刷新后执行。

# 0.2.33 后续浏览器大库响应缓存 LRU（2026-08-25，未发版）

- Web UI 的 48 项 `libraryResponseCache` 从 FIFO 改为 LRU：读取命中会刷新页面热度，满载时仅逐出最久未访问的响应。
- 保持手动刷新清空缓存和既有请求取消/在途合并语义；常用分类、搜索和分页页在大库来回浏览时可更稳定地命中本地响应。
- 完整离线门禁通过：341 项 Python 测试及全部 Node/UI 回归，无需真实设备。

# 0.2.33 后续发布资源自动发现（2026-08-25，未发版）

- `build_release.ps1` 不再维护硬编码 CSS/JS 列表：从 `index.html` 自动发现带 `?v=__FNAUDIO_ASSET_BUILD__` 的本地资源，校验路径安全、文件存在后按稳定顺序计算 cache build。
- FPK 解包验证会逐项确认自动发现的资源均被打入 payload，且 HTML 使用本次 cache build；后续新增展示模块不会再因遗漏脚本清单而留下旧缓存。
- 已完成隔离 fnpack 构建验证：`artifacts/_scratch/release-asset-discovery-20260825/0.2.33/fnaudio-0.2.33-fnpack.fpk`，SHA-256 `D0D556D05B4AD4875F0505F353578EE9A181B8D44BFCD6F148CFBC30411F0B16`；完整离线门禁通过：341 项 Python 测试及全部 Node/UI 回归，无需真实设备。

# 0.2.33 后续音乐库状态快照拆分（2026-08-25，未发版）

- 新增 `server/library_snapshot.py`，集中构造 health/diagnostics 共用的脱敏音乐库运行状态：扫描、取消、超时、错误计数、查询缓存、搜索索引与封面预热压力。
- `/api/health` 与 `/api/diagnostics` 不再复制同一组字段；健康检查可继续传入运行时 FTS 模式，诊断使用稳定安全默认值。
- 新增独立快照边界回归；完整离线门禁通过：341 项 Python 测试及全部 Node/UI 回归，无需真实设备。

# 0.2.33 后续大库分页缓存 LRU（2026-08-25，未发版）

- `LibraryQueryCache` 从插入顺序淘汰改为真正 LRU：命中页面会刷新热度，容量达到上限时逐出最久未访问的查询结果。
- 保留深拷贝隔离、TTL、按数据库失效和原有 hits/misses/evictions 指标；新增回归验证访问过的首页会保留、较冷页面被逐出。
- 完整离线门禁通过：339 项 Python 测试及全部 Node/UI 回归，无需真实设备。

# 0.2.33 后续大库分页在途合并（2026-08-25，未发版）

- 在既有 AbortController 与响应序号保护之外，`loadPagedLibrary()` 现对相同视图、页码、搜索、排序、分类和目录上下文复用同一个在途 Promise。
- 相同分页请求不会再彼此取消后重复请求或重复重绘；手动刷新保留强制新请求语义，完成、异常和取消都会释放协调状态。
- 前端语法/加载回归及完整离线门禁通过：338 项 Python 测试与全部 Node/UI 回归，无需真实设备。

# 0.2.33 后续发布静态资源完整性（2026-08-25，未发版）

- 修复 `build_release.ps1` 的静态资源内容哈希遗漏：已加入 `track_table_presentation.js` 与 `queue_presentation.js`。
- FPK 解包后的 payload 校验同时确认这两个模块被打入包内，且 `index.html` 对它们使用本次生成的同一 cache build，避免同版本发布仍加载旧模块缓存。
- 发布脚本、版本一致性和源码清单定向回归通过；完整离线门禁通过：338 项 Python 测试及全部 Node/UI 回归，无需真实设备。

# 0.2.33 后续封面预热资源边界（2026-08-25，未发版）

- 修复列表翻页/多客户端浏览时，每个可见页封面预热都创建独立线程的资源竞争风险；同一缓存目录现复用单一后台 worker，并按曲目版本去重。
- 交互预热待处理任务上限为 96，满载时丢弃最旧的预热任务；真实封面读取不受影响。预热请求 FFmpeg 槽位仅等待 50ms，持续让位于实际播放、转码和封面请求。
- health 与 diagnostics 的 library 状态新增 `thumbnail_prewarm` 脱敏摘要，公开交互/整库 worker、队列、inflight、成功、失败和丢弃计数；关停路径统一取消两类预热 worker。
- 新增有界单 worker、丢弃和关停状态回归；完整离线门禁通过：338 项 Python 测试及全部 Node/UI 回归，无需真实设备。

# 0.2.33 后续分类/目录分页缓存规范化（2026-08-25，未发版）

- `library_query_spec.py` 新增 `LibraryPageWindow` 与 `parse_optional_page()`；分类、作者/作曲者专辑及目录的分页 SQL 和缓存键统一使用同一份有界页窗口。
- `100`、`100.0`、越界值和非法参数不再将相同结果拆散为多个缓存项；显式未分页调用仍返回完整列表，保持既有 API 语义。
- 完整离线门禁通过：337 项 Python 测试及全部 Node/UI 回归；无需真实设备。

# 0.2.33 后续歌曲表头展示模块拆分（2026-08-25，未发版）

- 新增 `ui/track_table_presentation.js`，集中普通歌曲、分组、专辑集合三类表头的网格模板、列宽范围及排序标记生成。
- `app.js` 保留列拖动、DOM 监听器和偏好写入；共享模块接收当前列宽，因此不会覆盖用户自定义列宽。
- 新增独立 Node 回归，并纳入 `tools/test_offline.ps1`；完整离线门禁通过：336 项 Python 测试及全部 Node/UI 回归，无需真实设备。

# 0.2.33 后续诊断转码状态一致性（2026-08-25，未发版）

- 修复诊断快照读取不存在 `transcode.active` 的字段漂移；新增共享 `transcode_snapshot.transcode_summary()`，供 health 与 diagnostics 统一输出实际转码队列和 FFmpeg 闸门状态。
- 诊断仅保留队列压力与计数器，不包含路径、FFmpeg 命令行或媒体内容；新增回归覆盖字段结构、脱敏和小数等待时长。
- 完整离线门禁通过：336 项 Python 测试及全部 Node/UI 回归；无需真实设备。

# 0.2.33 后续音乐库查询规范拆分（2026-08-25，未发版）

- 新增 `server/library_query_spec.py`，集中解析和规范化分页请求的 limit/offset、视图、分组、目录、搜索、排序及缓存键。
- SQLite 与内存回退查询共用同一不可变 `LibraryPageQuery`，避免两条路径对参数边界、排序或搜索规范产生行为漂移。
- 新增查询规范测试；完整离线门禁通过：335 项 Python 测试及全部 Node/UI 回归；无需真实设备。

# 0.2.33 后续服务端曲目表示层拆分（2026-08-25，未发版）

- 新增 `server/library_presentation.py`，将曲目 API 的路径脱敏、媒体 URL、封面版本 URL 与缩略图 URL 从 HTTP Handler 分离。
- `server.py` 通过兼容函数调用该模块，现有路由与响应字段不变；单测确认源曲目对象不被改写且私有文件路径绝不会进入公开表示。
- 完整离线门禁通过：333 项 Python 测试及全部 Node/UI 回归；无需真实设备。

# 0.2.33 后续大列表交互性能（2026-08-25，未发版）

- 将曲目列表的点击、右键、移动端长按及指针结束事件收敛为 `trackList` 的一次性事件委托，避免每次 120 首分页重绘都创建数百个闭包和 DOM 监听器。
- 保持桌面 Ctrl 多选/右键、移动端点按播放、550ms 长按、移动距离取消和长按后点击抑制的既有行为；容器以 dataset 防止重复绑定。
- 完整验证：331 项 Python、全部 Node/UI 回归及 3 项 Playwright 浏览器 E2E 通过；无需真实设备。

# 0.2.33 后续源码清单门禁（2026-08-25，未发版）

- 新增 `test_source_manifest.py`：将 `SOURCE_MANIFEST.sha256` 从“人工维护的参考文件”升级为离线门禁的强制契约。
- 测试对受管 `src/` 与 `android-client/` 文件重算 SHA-256，校验记录完整性、唯一性与内容一致性；漏执行 `tools/update_source_manifest.ps1` 会使门禁失败。

# 0.2.33 后续队列展示模块拆分（2026-08-25，未发版）

- 新增 `ui/queue_presentation.js`，将队列索引分页和“同页增量更新 / 跨页完整重绘”的决策移出 `app.js`。
- UI 层继续负责实际 DOM 标识和滚动，因此模块没有引入 DOM、播放或网络依赖；`test_ui_queue_presentation.js` 独立覆盖页面计算和重绘边界。
- 离线门禁会检查该模块语法并运行其回归；无需真实设备。

# 0.2.33 后续资源闸门可观测性（2026-08-25，未发版）

- `ConcurrencyGate` 在既有 active/peak/acquired/waited/rejected/累计等待时长外，新增实时 `waiting` 与 `peak_waiting`。
- 等待请求只计数一次；成功获取与超时拒绝均会归还实时等待数，避免诊断将历史等待误报为当前堵塞。
- 单元回归覆盖等待中的快照、超时拒绝、释放唤醒及异常释放；无需真实设备。

# 0.2.33 后续大库前端渲染性能（2026-08-25，未发版）

- 修复远程播放状态更新的重复 `render()`：队列切歌不再由队列同步和远程快照各自重建一次列表。
- 当前队列停留在同一分页时，只更新旧行/新行的 `is-current` 类与“正在播放”标识，封面加载队列和其他可见行保持不变；跨页或 DOM 不完整时仍安全回退完整渲染并定位当前歌曲。
- `src/tests/test_ui_library_loading.js` 新增回归保护，避免后续重新引入双重重绘或移除增量更新边界。`tools/test_offline.ps1` 通过：330 项 Python 测试及全部 Node/UI 回归；未打包、部署或连接真实设备。

# 0.2.33 后续大库搜索性能（2026-08-25，未发版）

- 引入运行时可选的 SQLite FTS5/trigram `tracks_search` 外部内容索引，替代三字及以上查询原本多字段全表 `%LIKE%` 扫描；无 FTS5/trigram 的 fnOS 自动回退，不形成部署依赖。
- 索引仅在全库 SQLite 保存完成后一次性 rebuild，避免逐曲同步索引拖慢扫描；短于三字的查询继续走 LIKE，以保持原有两字中文、短音轨编号等匹配语义。
- 专辑/歌手/作曲者/流派、文件夹、根目录和普通歌曲分页搜索均接入同一条件，保留“按匹配曲目筛出分类，但分类展示完整曲目数”的既有行为。
- 100,000 首合成基准：FTS 子串搜索约 `0.020s`，LIKE 基线约 `0.255s`；完整库分页仍有界。`library/status`、health 和 diagnostics 暴露 `search_index` 模式；新增索引重建、短词回退和健康结构测试。

# 0.2.33 后续发布治理（2026-08-25，第四轮，未发版）

- `build_release.ps1` 现在对真实 fnpack 暂存树生成发布级 `SOURCE_MANIFEST.sha256` 和 `SOURCE_PROVENANCE.json`，并在构建结束前校验文件数、版本和清单哈希。该清单不依赖开发者是否提交 Git，可用于恢复被删除会话对应的精确构建输入。
- provenance 记录 Git commit 及包含未跟踪文件的 dirty 状态，但不暴露未提交文件路径；实际源文件列表和 SHA-256 由同目录 source manifest 提供。
- 根目录 `SOURCE_MANIFEST.sha256` 已刷新至 278 个源码/Android 文件，包含本轮新增缓存、健康快照及测试模块。
- 一次真实隔离 `fnpack` 构建通过：版本 `0.2.33`，134 个 FPK 暂存输入，输出 FPK SHA-256 `4A5FF55A25D91C376402BE0153DD206B6D4CEAFB2FC9FC656582CB4754D7B0D4`；产物保留于 Git 忽略的 `_scratch` 验证目录，不覆盖正式发布物。

# 0.2.33 后续离线性能与治理（2026-08-25，第三轮，未发版）

- SQLite schema 初始化缓存从“仅按路径”升级为按数据库主文件 `device/inode` 身份识别；外部删除并重建同一路径的 `library.sqlite3` 后会自动重新创建表/索引与执行迁移。
- `/api/health` 响应构造抽至独立 `health_snapshot.py` 纯函数。HTTP Handler 只提供当前组件状态，健康字段、默认值和敏感内容边界可独立回归。
- 新增外部替换 SQLite 文件及健康快照结构测试。完整离线门禁通过：328 项 Python + 全部 Node/UI 回归；未部署、未打包、未使用真实设备。

# 0.2.33 后续离线性能与治理（2026-08-25，第二轮，未发版）

- 将音乐库短期分页缓存从 `library.py` 抽为独立的 `library_query_cache.py`，锁、TTL、容量淘汰、深拷贝及按数据库精确失效均可单独测试。
- 缓存状态增加命中、未命中、逐出和失效计数；`/api/health` 和 `/api/diagnostics` 均暴露不含路径或歌曲信息的 library `query_cache` 指标。
- 添加前端库请求取消回归，防止后续修改移除 `AbortController`、信号透传或 AbortError 静默处理；认证桥仍以响应序号隔离旧结果。
- 重跑 100,000 首合成库分页基准：120 首页首/中/尾查询合计约 0.228 秒，Python 分配峰值约 0.38 MiB，分页边界保持正确。完整 `tools/test_offline.ps1` 通过：326 项 Python + 全部 Node/UI 回归；未打包、部署或使用真实设备。

# 0.2.33 后续离线性能与治理（2026-08-25，未发版）

- 修复离线测试脚本的 Node 项目分隔错误，确保用户状态与 UI 同步调度回归不会被数组字符串拼接掩盖。
- 扩展 FFmpeg 资源闸门诊断：记录成功获取、发生等待、超时拒绝及累计等待时间；测试覆盖拒绝路径统计。
- 为 SQLite 歌曲、分类与目录分页查询加入有界短期缓存，并保证扫描/索引写入完成后立即失效；新增回归证明索引替换后不会返回旧歌曲。
- 将 SQLite schema/migration 执行改为每个运行中数据库首次连接一次，扫描保存时重新执行以覆盖清库重建情形；新增连接级回归，防止每次列表请求重放迁移。
- Web 列表切换新增 `AbortController` 生命周期。标准浏览器会取消上一页请求；认证桥环境保持旧响应隔离，不以未实现的底层取消能力冒充完成。
- 验证：`tools/test_offline.ps1` 通过（323 Python + 全部 Node/UI 回归）；未执行真实设备、部署或打包。

# 0.2.33（2026-08-17）

- 接入飞牛文件管理器使用的私有 `file.rm` RPC，支持将歌曲移入飞牛原生回收站或彻底删除。
- 桌面端右键菜单增加删除入口，确认窗口复刻飞牛文件管理器的危险操作布局、按钮顺序、提示语和忙碌/失败状态。
- 删除成功后同步清理 fnAudio 队列、收藏、播放列表和页面缓存，并在后台刷新音乐库索引；Android 长按菜单不暴露依赖桌面宿主的私有接口。
- 使用独立测试文件完成移入回收站、回收站搜索与恢复验证，测试文件已清理；321 项完整离线回归通过。0.2.33 已部署内网机，实际部署页面的右键入口、确认框和“移入回收站”安全默认焦点验证通过，未删除真实歌曲。

# 0.2.32（2026-08-17）

- 修复 Android 恢复了已离线 DLNA Renderer 后，点击播放弹出 `JavaScript playback target not found`：恢复队列时先刷新并等待设备发现，确认目标不可用后同步回落到“当前设备”。
- 后端为消失的 Renderer 返回稳定错误码，播放过程中设备掉线时前端会清理远程事件流和状态、同步后端目标，并给出明确中文提示。
- UPnP 后台刷新在启动线程前发布 `refreshing=true`，消除刚打开 App 时因线程调度窗口误判设备离线的竞态。
- Android 接管 JavaScript alert，弹窗标题统一为 `fnAudio`，不再显示系统默认的 `JavaScript` 标题。
- 321 项完整离线回归、Android JVM 单元测试、Lint 和 Debug 构建通过。0.2.32 已部署内网机并覆盖安装小米 15 Pro；通过真实 WebView/CDP 注入离线 Renderer 后，控制返回 `false`、目标自动恢复为 `local/当前设备`、远程事件流关闭，应用进程存活且 crash buffer 为空。

# 0.2.31（2026-08-17）

- 全新安装或旧配置缺少字段时，“启用后台元数据补全”和“将补全信息写入歌曲 Tag”均默认关闭；已有配置中明确保存的开关值继续保留。
- 服务端配置、worker 运行兜底、设置接口和 Web/Android 共用界面统一采用严格 `true` 才启用，避免页面加载失败或缺字段时误开启后台抓取与文件写入。
- 设置页移除后台补全开关的默认勾选，并明确区分“自动抓取”和“修改歌曲文件”两项行为。
- 320 项离线回归及 Android JVM 单元测试、Lint、Debug 构建通过。0.2.31 FPK 已部署内网机，并将测试机当前两项设置同步关闭；状态接口确认 `enabled=false`、`tag_write_enabled=false`、Tag writer 未运行。

# 0.2.30（2026-08-17）

- 参考 Volumio、moOde 共用的 `upmpdcli` 实现，统一主动 Renderer 当前曲目与下一曲的 DIDL-Lite 构造逻辑。
- 补齐 XML 声明和 `searchable="0"`，按 `upmpdcli` 顺序输出 class、album、resource、artist 与无 profile 属性的 `upnp:albumArtURI`，同时保留资源大小和时长。
- 新增结构化 XML 回归，校验封面 URL、资源 URL、元素顺序及 current/next 元数据共用路径。
- 320 项完整离线回归通过；`fnpack` FPK 已部署到内网机 `18083`。JRiver 36 能播放测试 FLAC，但仍不请求公开封面，MCWS `File/GetImage` 返回 HTTP 500，确认这是 JRiver Renderer 不采纳外部 `albumArtURI`，不是 fnAudio 封面端点或 DIDL 格式问题。测试结束后状态已恢复 `STOPPED`。
- Android 同步构建 `versionCode=298 / versionName=0.2.30` Debug APK；JVM 单元测试、Lint、APK 构建和 v1/v2 签名校验通过。当前 ADB 无连接设备，因此本轮未声称完成实体手机覆盖安装。

# 0.2.29（2026-08-17）

- 针对 JRiver Media Center 36 的 Renderer 兼容性调整：主动推送 DIDL 的 `albumArtURI` 改用不带可选 `dlna:profileID` 属性的标准 UPnP 形式；DMS Browse 仍保留 JPEG_TN profile。
- 兼容写法已部署并向 JRiver 36 真实推送。JRiver 正常拉取、播放 FLAC，但仍未请求 `albumArtURI`；说明其 Renderer 不使用 SOAP 提供的外部封面，而非 fnAudio 封面 URL 不可达。测试后已恢复停止状态。

# 0.2.28（2026-08-17）

- 修复收藏与随机按钮的假高亮：真实开关状态由 `active-control` 和 `aria-pressed` 同步表达，随机状态只有严格布尔 `true` 才会激活；未激活按钮的 hover 改为中性样式，触摸设备不再保留类似已开启的悬停颜色。
- 修复主动 DLNA 推送缺少封面：`SetAVTransportURI` 与可选的 `SetNextAVTransportURI` DIDL 均加入公开 `/upnp/cover/<track_id>?size=160`、`xmlns:dlna` 和 `dlna:profileID="JPEG_TN"`。
- 内网真实服务验证封面 URL 返回 HTTP 200、`image/jpeg`、5845 bytes 和 JPEG_TN content features；部署文件确认当前曲目及下一曲 DIDL 都包含 `albumArtURI`。
- 应用内浏览器验证收藏和随机按钮初始均为 `aria-pressed=false` 且没有激活类。JRiver Media Center 36 当前已运行并监听 SSDP，但未被 fnAudio 发现为 Renderer，因此本轮不把 JRiver UI 封面显示标记为已完成实体验收。
- 319 项 Python/Node/UI 回归、Android Lint/单元测试/Debug 构建通过。FPK 已部署到内网机，小米 15 Pro 已覆盖安装 `versionCode=296`、`versionName=0.2.28`，启动进程存活且 crash buffer 为空。

# 0.2.27（2026-08-17）

- 修复 DMS 兼容性声明：未实现 `Search` 时不再宣称可搜索字段，避免 UAPP、中子等严格客户端把 MediaServer 判定为索引异常；DIDL-Lite 补齐 DLNA 命名空间。
- DMS 封面改用无需 fnOS Web token 的公开 `/upnp/cover/<track_id>?size=160` 路由，并返回 `JPEG_TN` profile、Interactive transfer mode 与 DLNA content features。内网机真实 Browse 和封面请求均通过，封面为 HTTP 200 `image/jpeg`。
- 音乐库文件夹、专辑、歌手等分类和分页响应增加 48 项浏览器内缓存；列表数据到达后立即渲染，不再等待状态接口。30 秒状态轮询只更新状态装饰，不再整页重建歌曲 DOM。
- MPD/DAC 首次同步长队列改为标准 `command_list_ok` 批处理，一次写入 `clear`、全部 `addid` 和播放模式设置，再按响应保存每首 MPD song id；相同队列继续复用 fingerprint，只切换 `playid`。
- 验证：318 项 Python/Node/UI 回归、Android Lint/单元测试/Debug 构建通过；内网 fnOS 已运行 `0.2.27`。真实页面分类切换约 0.43 秒，完整 36 秒状态周期后列表仍为 120 个节点且内容不变，控制台无警告/错误。
- 小米 15 Pro 已覆盖安装 Debug APK，版本 `versionCode=295`、`versionName=0.2.27`；冷启动后进程存活，Android crash buffer 为空。

# 0.2.26（2026-08-17）

- Android 登录页右上角新增 FN Connect 齿轮设置入口，移除原有“公网 / P2P 中继”二元开关。
- 设置页提供与飞牛 APP 对齐的“速度优先 / 公网连接 / 中继连接”策略和独立 P2P 开关：速度优先为公网优先、不可用时自动尝试中继；中继连接不回退公网；关闭 P2P 时强制公网。
- 新 FN Connect 历史记录保存实际生效的连接策略；旧历史记录兼容迁移为原有公网或中继策略。
- 关闭 P2P 时设置页会自动选中并保存“公网连接”，避免界面仍显示中继而实际已强制公网。小米 15 Pro 已覆盖安装验证设置入口、三种策略、P2P 联动和返回后的摘要；离线 317 项回归、Android Lint、单元测试与 Debug 构建均通过。
- 产物：`artifacts/0.2.26/fnaudio-0.2.26-fnpack.fpk`（SHA-256 `F5FD1A7FB0A6431FBCC1C2369A1C0CCA605C14809618FF0C55A6653C8C9D063C`）和 `artifacts/0.2.26/fnaudio-android-0.2.26-debug.apk`（SHA-256 `63BE6B51961DC2B6C1E465763B5DF9B27FDA31028708F8B89B6393B620C67A41`）。

# 0.2.25（2026-08-17）

- 小米 15 Pro ADB 崩溃日志确认 FN Connect 登录跳转后的黑屏闪退是 `LoginActivity.onDestroy()` 调用 `OkHttp ConnectionPool.evictAll()` 所致，不是 Tpps JNI。该调用在主线程同步关闭 TLS socket，引发 `NetworkOnMainThreadException`。
- `FnConnectResolver.close()` 改为只取消尚未完成的请求，闲置连接继续由 OkHttp 自动回收；新增回归阻止重新引入主线程 TLS 连接池驱逐。
- 真机回归：小米 15 Pro（ARM64）已覆盖安装 `0.2.25`，冷启动后从登录页成功进入主界面，应用进程持续存活且新的 crash buffer 为空。317 项离线回归和 Android Lint/单元测试/Debug 构建通过。FPK SHA-256 `2F9743B3DCA693ED44981B75145E215B9956E13426E72C5902BD9CD97A0906AB`；Debug APK SHA-256 `0CACA0EB68F40451B100FBAE222F2D607C20A8AD9822980F35D0B9E0A7D42872`。

# 0.2.24（2026-08-16）

- 修复 Android P2P 中继首次登录可能黑屏闪退：首次启动不再对尚未初始化的 Go/Tpps 引擎调用 `Tpps.stop()`，仅停止当前进程已经成功启动的 native 会话。
- 中继连接超时后主动释放已启动的 native 会话，避免下次登录继承半初始化状态。
- 验证通过：316 项 Python/Node 离线回归、Android Lint、单元测试、Debug/仪器 APK 强制重建及 fnpack 包检查。FPK SHA-256 `5045174C471AB50B933126215910E767944DE8CC523E5A2DBB6A647A4966C204`；Debug APK SHA-256 `5EA644332F00F65495EA19C76D87457739DF5DDB5A5F57E0E4FB5E78F8F12D54`。

# 0.2.23（2026-08-16）

- Android FN Connect 登录页新增“公网 / P2P 中继”开关。公网模式不启动 Tpps；P2P 模式强制建立动态中继且失败时不静默回退公网。
- 每条 FN Connect 历史连接独立保存连接方式，自动恢复和主界面重建沿用该选择；历史列表直接显示“公网”或“P2P 中继”。
- Tpps 原生库改为与官方飞牛 App 一致的安装时解压加载方式，降低 ARM64/16 KB 页设备直接映射 JNI 时的崩溃风险。
- 官方 Tpps V2 中继已在 Android 14 模拟器完成登录、队列、播放控制、MP3 流下载和浏览器解码验证；fnAudio ARM64 JNI 仍需实体手机安装验收。
- 验证通过：315 项 Python 测试、全部 Node/UI 回归、Android Lint、单元测试、Debug/仪器 APK 强制重建及模拟器开关检查。FPK：`artifacts/0.2.23/fnaudio-0.2.23-fnpack.fpk`，SHA-256 `67EB69CC7730215C0B3DA76B92ADE7F6C4C38364DC1B98270B1AA2755EB10654`；Debug APK：`artifacts/0.2.23/fnaudio-android-0.2.23-debug.apk`，SHA-256 `76946D7C97FEF2AD5F183F2DC93E20BF8C8375A0838FC30209B6A35F93B1FB58`。

## 0.2.22 (2026-08-16)

- 高风险局域网匿名写接口改为仅接受 fnOS 内部认证代理；直接局域网访问仍可浏览音乐、控制播放和同步用户播放状态。
- 播放控制在切换输出前校验动作与 DLNA 目标，非法请求不再关闭当前 DAC/DLNA 会话；配置更新改为副本写盘成功后原位提交。
- 前端分页和“播放全部”严格检查 HTTP 状态，CGI 透传后端 JSON 错误；强制扫描可升级已排队普通扫描，元数据 fetch/歌词/Tag worker 使用独立唤醒事件。
- Android 修复 fnOS 嵌套 token 和 URL 协议解析；登录、FN Connect 请求可取消，历史密文损坏时保留恢复副本，通知封面缓存加入 64 MiB/30 天边界，媒体服务释放 OkHttp 资源。
- 运行时及当前真机脚本默认端口统一为 `53199`。完整离线门禁通过 315 项 Python 和全部 Node/UI 回归，Android 单元测试与 Debug/仪器测试源码编译通过。
- 最终 fnpack FPK SHA-256 `119B853A6F1AF22452F6FAD61E67B339BDC6DB83A72E28C44849BD44A03FCFA0`；Debug APK SHA-256 `545D4BB33584F3AFF8D4CA276FD9419AB48B8E477C5484282AF1926953961A25`。最终 FPK 已部署内网 fnOS，回滚点 `/vol1/1000/fnaudio/fast-deploy-backups/20260816-152042`。

## 0.2.21 (2026-08-16)

- 修复两台 fnAudio 位于同一局域网时互相不可见：SSDP 发现不再按所有 fnAudio 共用的 Renderer 控制路径排除设备，只按本机精确 LOCATION 与 UDN 过滤自身广播。
- 增加双 fnAudio Renderer 身份回归测试，确保本机不出现在目标列表、另一台 NAS 的 fnAudio Renderer 可以作为 DLNA 推送目标。
- 验证通过：309 项 Python 和全部 Node/UI 回归。`0.2.21` 已通过 fnpack 构建并部署到内网 fnOS；真机 Renderer 使用唯一 UDN 和可访问 LOCATION 响应 M-SEARCH，同时播放目标列表正确排除自身。FPK SHA-256 `2D8152546437844DC4B94CFED609484D31CD12A7F12728C90B72C44673AE1C58`。

## 0.2.20 (2026-08-16)

- Android FN Connect 历史连接恢复前重新解析公网地址，不再仅刷新旧中继格式记录。
- 认证链明确区分凭据拒绝和网络失败；短 token、longToken 都过期时自动使用加密保存的密码重新登录，无法恢复时清除旧 token 并返回登录表单。
- 修复 fnOS 外层 `result=succ`、内层返回新 token 时的解析错误；longToken/密码登录不得复用已失效短 token。
- API 35 模拟器仪器测试已覆盖短 token 与 longToken 同时过期、密码回退和嵌套 token 更新。
- 验证通过：308 项 Python、全部 Node/UI、3 项 Playwright、Android 单测/Lint/Debug 构建及定向仪器测试。`0.2.20` 已安装到 API 35 模拟器和内网 fnOS；内网健康、15 首队列、当前歌曲与 STOPPED 状态保持。FPK SHA-256 `ADED49C46118AC45D0292E3D1C032556D92FD1359A58DC7BF4D6BCD2A5D4612A`；Debug APK SHA-256 `19AFB50EC27A160275FA89673AB3B51D77B2F35AE82E72928880961F0CD54CE2`。

## 0.2.19 (2026-08-16)

- 新增独立的歌曲 Tag 写回开关并默认关闭；歌词、封面和其他元数据仍照常抓取与缓存。
- 写回 worker、失败重试接口和最终文件修改入口共同执行开关约束；关闭期间保留任务，旧配置升级后默认关闭。
- 设置页显示明确状态和待写数量，写回关闭时隐藏失败重试按钮。
- 修复快速部署脚本在 Windows 参数转义异常时只上传包却误报成功的问题；现在通过 Plink 命令文件传递事务，并强制检查远端 `FAST_DEPLOY_OK` 标记。
- 验证通过：308 项 Python、全部 Node/UI 回归、3 项 Playwright、Android 单测/Lint/Debug 构建和 fnpack 包检查。内网机 `198.51.100.24:18083` 已升级并重启验证：元数据抓取开启、Tag 写回关闭、播放队列和 STOPPED 状态保持。FPK SHA-256 `8825BE8FE507AB94000131888B30BAAC5AF0691EBDC91F679F01BBA3963258D8`；Debug APK SHA-256 `5B100083C694575E56978EE7F13D9AB0E1A6D1CD7863FB828B43EB875D6FDA88`。

## 0.2.18 (2026-08-15)

- 修复私有局域网直接打开服务端口时音乐库 API 返回 403、页面静默显示空库的问题；公网入口继续要求 fnOS/Android 认证。
- 修复裸 `mpd`/`alsa` 插件 ID 被归入 DLNA 目标类型的问题。
- 修复大型曲库持续扫描超过固定总时长后被突然终止的问题：超时改为连续无进度检测，重复刷新可靠排队，并记录 queued/result/last_error 和服务日志；跨多个音乐根目录的已发现数量保持单调累计。
- 验证通过：305 项 Python、全部 Node/UI 回归、3 项 Playwright、Android 单测/Lint/Debug 构建及 fnpack 包检查。内网测试机已升级至 `0.2.18`：直接端口显示 227 首，双扫描排队后完整结束且无错误，裸 MPD 目标返回 `target_kind=mpd`，升级前播放快照逐字段恢复。FPK SHA-256 `14C78BD079E47104EC726351406EC9A6A7E1DE671922C31407397B00BBE32FED`；Debug APK SHA-256 `EFA640B54CFD79766EE9DC15728F7A70D1D0A0452D7BB1FFDA41FE32130F60EC`。

## 0.2.17 (2026-08-15)

- Android WebView 在首次加载和页面导航期间保持可见，避免重定向或完成回调延迟留下白屏；模拟器仪器测试覆盖启动可见性、认证封面代理和返回流程。
- Web 状态同步抽取为 `ui_sync_scheduler.js`：后台页面暂停轮询并释放 SSE，恢复前台后立即同步；远程播放仍由后端权威快照驱动。
- MPD 队列恢复、播放控制、模式更新和 DLNA Renderer 命令统一串行化，恢复窗口内的新命令等待队列重建，降低 `queue_stale / no such song` 竞争条件。
- App Center 端口与向导契约增加结构化回归；升级音乐路径改用 JSON 迁移，不再依赖空格敏感的文本替换。
- 本版本只执行离线、浏览器、Android 模拟器和包结构验收；真实设备事项继续保留在 TODO，不以模拟结果替代。
- 验证通过：302 项 Python 测试、全部 Node/UI 回归、3 项 Playwright、Android 单测/Lint/Debug 构建、API 35 模拟器 7 项有效仪器测试（真实 NAS 用例跳过）及 fnpack 包检查。FPK：`artifacts/0.2.17/fnaudio-0.2.17-fnpack.fpk`，SHA-256 `F9D62A8F0D62C05EE58FF0F21C46883DE014D71E41BC45F7D1561C79BDD3A853`；Debug APK：`artifacts/0.2.17/fnaudio-android-0.2.17-debug.apk`，SHA-256 `81B14B35881800B1DCD621F32C60B64D87646D10D2CE6F70B7B449A2007A20C8`。

## 0.2.16 (2026-08-15)

- 修复 Android 冷启动恢复播放：网页恢复上次歌曲时，若 MediaController 尚未连接，原生 `setQueue`/`play` 命令不再被丢弃，而是按顺序等待控制器就绪后执行。
- 启动仍保持停止，用户首次点击播放即可启动恢复后的 ExoPlayer 队列；补充 Android 桥接回归检查。
- 验证通过：Android Debug 单测、lint、APK 构建、Node/UI 桥接检查；模拟器已安装 0.2.16。FPK：`artifacts/0.2.16/fnaudio-0.2.16-fnpack.fpk`，SHA-256 `2E92DC3F45A28896D57370CBA33A157BC697BB2538AED8CA5F120DA22B1AC599`；Debug APK：`artifacts/0.2.16/fnaudio-android-0.2.16-debug.apk`，SHA-256 `77CB3CDED66EFA3221BEF4579E93FAB371D334B083929BABDA270E10AF05FB89`。
- 已自主覆盖安装到外网真机 `vinson023.eu.org`，服务头确认 `fnAudio/0.2.16`，备份为 `/vol1/1000/fnaudio/fast-deploy-backups/20260815-142752`。真实 TEAC UD-301 通过 30 秒稳定性、PCM 控制矩阵、DSF/DFF Native DSD 和 MPD 重启恢复验收；Android 外网恢复播放仪器测试通过，结束后会话恢复为 STOPPED。

## 0.2.13 (2026-08-15)

- 修复 Android 通过 fnOS CGI 打开 fnAudio 时主页面偶发返回 `Not Found` 的问题：主框架请求现在显式携带 CGI 根路由，代理也将显式 `/` 视为权威路由，不再被 fnOS 的内部 `REQUEST_URI` 覆盖。
- 新增可选真实 NAS Android 仪器测试，凭据只通过运行参数注入，覆盖真实登录、服务端队列恢复、ExoPlayer 队列重建、禁止启动自动播放和点击播放生效。

## 0.2.12 (2026-08-15)

- 修复 Android 客户端在进程重建后仅恢复网页播放快照、但原生 ExoPlayer 队列为空时点击播放无响应的问题。恢复本机播放会先静默预置原生队列并保持停止；播放按钮额外校验原生与网页队列一致性，不一致时强制下发队列再启动，避免应用启动自动播放。

## 工程化：正式 Android 发布链路与文档归档 (2026-08-14)

- 新增 `tools/build_android_release.ps1` 和 `docs/ANDROID_RELEASE.md`：正式 APK 构建强制要求四项签名变量，验证 APK 签名和版本，并将 SHA-256 归档到发布目录。
- 使用一次性临时 keystore 完成离线端到端烟雾验证，确认 Release APK 的 v1/v2 签名、`versionName` 与 `VERSION` 和产物哈希均正确；该临时密钥不是正式发布身份。
- 同步根 README、架构、决策、恢复和 Android 客户端文档的当前版本与端口模型；重新生成 `SOURCE_MANIFEST.sha256`。

## 0.2.5 (2026-08-14)

- 重新发布移动端控制栏布局：顶部保留播放设备与 MP3 转码，底部随机播放位于上一曲前、循环播放位于下一曲后；移动端不再显示桌面底栏操作组。
- 增加浏览器回归，验证上述按钮在手机视口可见、隐藏与相对位置；发布构建以内容哈希写入静态资源地址，强制浏览器与 WebView 获取本次 CSS/JS。
- 验证通过：282 项 Python 测试、Node/UI 回归、3 项 Playwright E2E、Android Debug 构建与原生 fnpack 包检查。FPK：`artifacts/0.2.5/fnaudio-0.2.5-fnpack.fpk`，SHA-256 `DD32D95F2E41DA780DE1DB091041991DCC3945F7F328D22201064C5E7591FA19`；Android Debug APK：`artifacts/0.2.5/fnaudio-android-0.2.5-debug.apk`，SHA-256 `FFCC86EACBFD272A662247D96CE0F2286D02A41150F22CFA3714F1C062162162`。
- 已使用可回滚快速部署脚本安装到内网测试机 `198.51.100.24:18083`。运行 manifest 与 `Server` 头均为 `0.2.5`；手机视口实测当前 CSS 地址为 `app.css?v=0.2.5-a09869333741`，四个移动端控制按钮及其相对位置符合预期。

## 0.2.4 (2026-08-14)

- 修复移动端专辑详情页歌曲区域被嵌套固定高度滚动容器压缩，点开专辑后现在由音乐库主滚动区域承载列表，歌曲可见且可继续上下滑动。
- 增加移动端专辑详情 Playwright 回归：使用真实的 `view=albums&group=...` 分页请求，验证专辑歌曲渲染、可见高度与无横向溢出。
- 验证通过：282 项 Python 测试、Node/UI 回归、3 项 Playwright E2E、Android Debug 构建与原生 fnpack 包检查。FPK：`artifacts/0.2.4/fnaudio-0.2.4-fnpack.fpk`，SHA-256 `A8F64357451DDD531DE63AB2EE4675645EF754C2D6E8DF612CEC5EB840BAAB5A`；Android Debug APK：`artifacts/0.2.4/fnaudio-android-0.2.4-debug.apk`，SHA-256 `E325F73154A4413C090B40A7698421A3E0C37355E7C983C3AB6C05B0C991FB33`。

## 0.2.3 (2026-08-14)

- 从 `app.js` 抽取顶部标题/副标题的纯展示规则至 `view_presentation.js`，减少视图渲染函数的职责并建立前端模块边界。
- 发布缓存构建标识现在同时涵盖 CSS、主 UI 脚本与视图展示模块。
- 验证通过：282 项 Python 测试、Node/UI 回归、2 项 Playwright E2E、Android Debug 构建与原生 fnpack 检查。FPK：`artifacts/0.2.3/fnaudio-0.2.3-fnpack.fpk`，SHA-256 `C9D4B744ED56C8FD6CAEAF530EB6BA055C32DFCBA997DE1017C1B98FC48BBF8E`；Android Debug APK：`artifacts/0.2.3/fnaudio-android-0.2.3-debug.apk`，SHA-256 `307E4DCF5E5B6BAB67636F14F5AE6890039344A1EDFE7E240345593F9B04540E`。

## 0.2.2 (2026-08-14)

- 发布阶段静态资源改为由 CSS/JS 内容派生的构建标识，fnpack 暂存副本会自动写入缓存键，消除同版本修复残留旧脚本的风险。
- 新增受认证保护的 `/api/diagnostics` 脱敏快照，集中导出版本、播放、MPD、扫描、元数据、转码、DLNA 与计数器状态，不包含路径、密码、Token、Cookie 或歌曲信息。
- Android Release 构建必须提供完整 keystore 参数并验证文件存在；无签名凭据时明确失败，Debug 构建不受影响。
- 新增默认关闭的 Chromaprint/AcoustID 可选候选源：仅在配置 fpcalc、启用开关并设置环境变量 Key 时运行，失败不会影响现有元数据队列。
- 完整离线验证通过：282 项 Python 测试、Node/UI 回归、2 项 Playwright E2E、Android Debug 构建与原生 fnpack 包内检查。FPK：`artifacts/0.2.2/fnaudio-0.2.2-fnpack.fpk`，SHA-256 `8D2BFBA65DA52CC9B2AA1685D24654C8BCF486DAE2A28F2179CB0093F3ED9727`；Android Debug APK：`artifacts/0.2.2/fnaudio-android-0.2.2-debug.apk`，SHA-256 `A2F6009AEEF2EF57046BBDC9B5B278F8F4B48A99729B5B3BB22C48F82C228737`。

## 0.2.1 (2026-08-14)

- 修复顶部简介只在首屏短暂显示“飞牛私人音乐库”、随后被前端默认视图文案覆盖的问题。桌面与移动端音乐库默认副标题现保持为“飞牛私人音乐库”。
- 更新 Web 静态资源版本参数与 Android 安装序号，确保覆盖升级后不会继续命中 0.2.0 的缓存脚本。
- 验证通过：版本联动回归、JavaScript 语法检查、Android Debug 构建与原生 fnpack 包内检查。FPK：`artifacts/0.2.1/fnaudio-0.2.1-fnpack.fpk`，SHA-256 `F59FF020D739CAD35A94F6A44EEC0B6D9B86EB77C046937C1797FE3CAF6FC755`；Android Debug APK：`artifacts/0.2.1/fnaudio-android-0.2.1-debug.apk`，SHA-256 `5042A8C62CAC832EEB55F85327B45A07515D30E73AE39F32D0D64FC17043BCDE`。

## 0.2.0 (2026-08-14)

- 应用顶部简介统一为“飞牛私人音乐库”。
- 应用中心介绍更新为本地音乐播放、高解析音乐库、歌词封面补全、USB DAC、DLNA 推送和 Android 锁屏控制的完整能力说明。
- 发布版本升级至 0.2.0；Android `versionCode` 递增至 271，发布校验不再错误地从三段版本号末段推导安装序号。
- 验证通过：279 项 Python 回归、Node/UI 回归、2 项 Playwright E2E、Android Debug 构建与原生 fnpack 包内检查。
- 发布产物：`artifacts/0.2.0/fnaudio-0.2.0-fnpack.fpk`，SHA-256 `7441A3446CD239A3F8561894736068F904885464AD47D4799A84F4B508CDE7EE`；Android Debug APK 为 `artifacts/0.2.0/fnaudio-android-0.2.0-debug.apk`，SHA-256 `38E61CE3D0533EB34B00AB2DFC44DB58F169E6CAAA9808A12A41CC3C64024983`。

## 0.1.270 (2026-08-14)

- Metadata review now presents all persisted candidates and can confirm any selected candidate. The API accepts only a non-negative candidate index, validates it against that track's stored candidates, and never accepts client-supplied metadata fields.
- Added a Windows GitHub Actions verification workflow that reuses the offline Python/Node/Playwright tests, Android Debug build and native fnpack package inspection.
- Consolidated library root merge and configuration writes in `library.py`, so scan, SQLite and the settings API share canonical path identity.
- Reconciled the stale P1-P3 backlog against current code and documented real external blockers: Chromaprint runtime plus AcoustID key/quota, a remote CI repository, physical protocol/device acceptance, signing and historic backup recovery.

## 0.1.269 (2026-08-14)

- Cover thumbnail prewarming now uses the shared FFmpeg resource gate used by streaming and transcode work, so background artwork generation cannot bypass the configured concurrency budget.
- Library warmup is processed in 24-track pages with a short delay between pages. It attempts the FFmpeg slot only briefly, yielding to interactive cover, playback and transcode requests when the NAS is busy.
- Deferred library workers have a cancellable lifecycle. A rescan replaces stale work, shutdown cancels and joins workers, and cancellation is checked before every cache write to prevent cache-directory cleanup races.
- Added cover-cache regressions for shared FFmpeg gating and cancellation after a cover reader has started. Corrected the mobile CSS assertion to inspect only the player rule block.
- Built exclusively with fnpack and fast-deployed to the authorized LAN test host. The live 0.1.269 service on port 18083 passed its health check.

## 0.1.265 (2026-08-14)

- Android 长按歌曲菜单隐藏“打开包含的文件夹”和“分享外部链接”。
- PC 右键菜单保留这两项功能，避免移动端与飞牛文件管理能力不匹配。

## 0.1.264 (2026-08-14)

- 修正当前播放收藏按钮与异步服务端状态合并不同步的问题。
- 收藏 ID 比较统一为字符串形式；播放核心确认当前歌曲后立即刷新收藏状态。

## 0.1.263 (2026-08-14)

- 统一桌面播放器右侧工具按钮的尺寸与 SVG 描边，歌词按钮恢复为中文“词”。
- 播放设备图标改为扬声器输出设备图形；MP3 转码按钮改为纯 MP3 文字标识。
- 设置入口改为控制面板图形，替换历史复杂齿轮图标。

## 0.1.262 (2026-08-14)

- Raised the release version for formal fnOS App Center overwrite-upgrade validation.
- The FPK is built and inspected exclusively with the native `fnpack` tool; no post-build repackaging is permitted.
- This release records App Center upgrade, lifecycle/configuration retention, port/service health, and rollback evidence separately from fast deployment.

## 0.1.261 (2026-08-14)

- Added track-level metadata enrichment for files whose title/artist came from filenames or whose album is missing.
- Reused existing MusicBrainz, NetEase, QQ, Kugou, Migu, JOOX and Qianqian provider adapters to collect and score recording candidates.
- High-confidence, unambiguous matches automatically fill only blank or filename-derived fields; existing embedded tags are never overwritten by an online match.
- Ambiguous matches are persisted as review candidates and can be confirmed from the track action dialog before background writeback.
- Added metadata APIs for candidate inspection and confirmation, match status counters, and regression coverage for candidate ranking and safe apply behavior.
- Release artifacts remain fnpack-only, with no FPK repackaging.

## 0.1.238 (2026-08-13)

- Added persistent 160 px list thumbnails and 512 px playback artwork under the private cache directory. Cached URLs include the source modification version and use immutable HTTP caching.
- Limited cold thumbnail generation to two concurrent FFmpeg processes and deduplicated requests for the same cover, preventing first-page artwork from saturating the NAS.
- Added persistent negative results for tracks without artwork. Subsequent library responses omit their cover URL and render the unified music-note fallback without repeated 404 requests.
- Android notifications, MediaSession, now-playing and lyrics keep the 512 px artwork path; track and group lists use 160 px thumbnails.
- This cache is read-only with respect to music files: it does not write tags or replace embedded artwork.
- Fixed the no-cover image fallback so removing a failed image no longer dereferences its detached parent in Chromium/WebView.
- Installed on the LAN fnOS host and verified 3.03 MB artwork becomes a 4.8 KB 160 px thumbnail; cold generation was 241.57 ms and persistent-cache access was 0.17 ms. Live CGI rendering used 160 px list images, retained 512 px playback artwork, and produced no console warnings or errors.
- Android private cover requests now pass through the concurrent OkHttp resource proxy with the fnOS bearer token, trim-token header and authenticated cookies. Web-session profiles recover missing image cookies from CookieManager.
- Returning to Login now opens a blank address form instead of prefilling the active FN Connect ID. A manually entered endpoint no longer inherits an edited/active `FN Connect - ...` name or profile identity, so multiple direct addresses remain separate history records.
- Corrected the logout behavior: explicitly returning from MainActivity now prefills the last active address/FN ID, account and encrypted saved password without automatically logging in. First launch still resumes silently, while History > Add remains blank.

## 0.1.227 (2026-08-13)

- Removed FN Connect relay/Tpps mode by product decision. The Android APK no longer includes Tpps JNI, Go runtime support, Remote Config signing, `libgojni.so`, or `libsskit-native.so`.
- FN Connect resolves direct public endpoints only: public IPv6 is probed first and public IPv4 is the fallback. Historical localhost relay profiles are re-resolved from their FN ID.
- Updated the FN Connect preference screen to show the IPv6-first direct policy and relay disabled.
- Clean Android build passed. The debug APK installed on Xiaomi 15 Pro and displayed the new policy UI. Complete FN ID login, library, and playback remain a real-network acceptance task.

## 2026-08-12：连续目标 4，播放兼容 API 与模块边界

- 新增 `playback/http_contract.py`，从 2200 行级 `server.py` 抽出目标分类、目标规范化、队列输入、SSE 包络及旧播放 payload 转换等纯规则。
- 源码调用审计确认当前 Web 与 Android 不再使用 `/api/player/state`、`/api/upnp/{push,control}`、`/api/dac/{push,control}`。旧接口继续转发到权威 `/api/playback/*`，并返回标准 `Deprecation`、后继 `Link` 和诊断头。
- 保留 UPnP/DAC 的只读发现与诊断 API，以及 Renderer 必需的 `/upnp/media/*`。大型模块按风险分阶段拆分，完整边界和删除前置条件记录在 `docs/PLAYBACK_API_COMPATIBILITY.md`。
- 新增 6 个播放 HTTP 契约测试；专项播放回归共 17 项通过。

## 2026-08-12：连续目标 3，源码卫生清理

- 修复 `alsa_output.py` 与 `mpd_service.py` 中 10 处损坏的中文错误/状态提示，消除播放目标 payload 的重复 `name` 键。
- 删除没有调用方且会把 DSD 隐式转换成 PCM 的旧 `dac_ffmpeg_command()`；实际 ALSA 与 MPD 路径保持不变。
- 新增 `test_source_hygiene.py`，通过 AST 检查已知乱码、同作用域重复定义、字面量重复字典键及无条件终止语句后的不可达代码。
- 完整离线验证通过：205 个 Python 测试、JavaScript 语法、5 个 Node UI 回归和 `git diff --check`。

## 2026-08-11：连续目标 2，MPD 播放错误分类

- 新增纯函数模块 `playback/mpd_errors.py`，将 MPD 日志与命令异常稳定分类为媒体源损坏、seek、解码器不可用/失败、输出设备缺失/忙、输出格式不支持、输出 I/O、buffer underrun、队列陈旧、数据库未就绪和后端不可用。
- 每个错误携带 domain、severity、retryable 和建议 action；重复日志合并 occurrence，固定读取最新错误并限制最多 100 个唯一条目。启用 decoder 的普通日志不再误报“解码器不可用”。
- `MpdOutput` 的打开和控制失败返回结构化 `error`/`error_category`，保留原 message；MPD 状态新增 `playback_errors`，旧 `decoder_errors` 保留兼容。
- 日志监控只把真实 `buffer_underrun` 写入旧 underrun 计数。损坏 FLAC、seek 和 decoder 错误不再被当作 DAC 故障；设备缺失和格式不支持记录故障但不盲目重启，设备忙和输出 I/O 仍受 30 秒恢复节流保护。
- 本地 Volumio/moOde 对照确认其通用层同样依赖 MPD/ALSA 日志与输出插件边界，没有适合直接复用的跨版本错误分类器。完整离线验证通过：201 个 Python 测试、JavaScript 语法和 5 个 Node UI 回归。

## 2026-08-11：连续目标 1，统一资源边界

- 新增共享 FFmpeg 并发门。缓存转码与 HTTP 流式转码共用 `ffmpeg_max_concurrency`，并发饱和在发送响应头前返回 503；启动失败返回 502，超时和断连都会释放进程与槽位。
- 元数据和转码待办队列均有持久化上限。普通预热达到上限后拒绝入队，当前歌曲的歌词、封面或 Tag 工作可以淘汰最低优先级的非运行任务；运行中任务不会被删除。
- 元数据封面与转码缓存同时受最大字节数和最小磁盘保留水位控制。封面淘汰会清空实体引用并使其过期，以便后续重新抓取；正在运行或排队的转码目标不会被清理。
- 音乐库扫描新增最长运行时间和取消事件，CUE、目录、文件及快速签名循环均检查截止时间。取消/超时保留原有效索引，并提供受 `settings.write` scope 保护的 `POST /api/library/scan/cancel`。
- `/api/health` 增加扫描、元数据待办/丢弃/封面字节、转码队列与 FFmpeg active/peak/limit 指标。完整离线验证通过：192 个 Python 测试、JavaScript 语法和 5 个 Node UI 回归。

## 0.1.222 (2026-08-11)

- Completed the five-stage offline hardening sequence. DLNA ContentDirectory
  now honors metadata/direct-child browse modes, bounded paging, field filters,
  supported sort criteria and a library-derived SystemUpdateID; unknown objects
  and invalid sorts return UPnP 701/709 faults instead of silently listing the
  whole library.
- Centralized runtime version identity in `app/server/version.py` for HTTP,
  metadata requests, SSDP and device model descriptions. Consolidated the two
  media byte-range implementations and removed a duplicate library helper.
- Added native WAV and uncompressed DFF information readers plus generated
  fixtures covering duration, DSD properties, sidecar artwork, MIME and Range
  seek behavior. Added `tools/test_offline.ps1`; the consolidated run passed
  176 Python tests, JavaScript syntax and five Node UI regressions.
- Updated the release validator for the manifest-backed runtime version and
  built the inspected FPK at `artifacts/0.1.222/fnaudio-0.1.222-fnpack.fpk`;
  SHA-256: `F5B2254FA317F421BA53666C2AB3883EFF142D46751FA18BCA432ADCE917AD80`.
- Added revision-aware user-state changes for favorites and playlists. Stale
  browser windows now merge atomic additions, removals, playlist upserts and
  deletions instead of reviving deleted data through a set union. In-flight
  edits use a dirty retry, while old clients retain the explicit 409 contract.
- Added a reproducible 100,000-track SQLite pagination benchmark. The current
  host built a 56,598,528-byte index in 2.23 seconds; three 120-row pages took
  0.217 seconds in total with 221,516 bytes of peak traced Python allocations.
  Timing is recorded as evidence rather than a machine-independent CI limit.
- Added structured JSON Lines access logs with request IDs, recursive secret
  redaction and bounded rotation. `/api/health` now reports bounded MPD,
  library, metadata and DLNA status/metrics without exposing token state; GENA
  subscriptions are capped at 64 and notifications use four workers.
- Added scoped non-DLNA API authorization. Only authenticated loopback proxy
  requests are accepted for protected routes; library, playback, state,
  settings and file operations use distinct scopes, while direct LAN, missing
  token and missing-scope requests are rejected.
- Hardened path operations with real-path containment, symlink-escape rejection,
  configured-root-only shared-folder deletion and a 2 MiB API request limit.
  Verification passed with 162 Python tests and all Node UI regressions.
- Added a shared DLNA outbound network boundary for SSDP `LOCATION`, SOAP/SCPD,
  GENA `CALLBACK` and Renderer media URIs. It rejects non-HTTP(S) schemes,
  credentials, public/multicast/unspecified addresses, redirects and responses
  above the configured bound while preserving empty NextURI clearing.
- Added focused network-boundary coverage. Verification passed: 157 Python
  tests, JavaScript syntax validation and all four Node UI regressions.
- Reorganized `TODO.md` into a single current backlog. It now separates
  immediately actionable offline engineering from deployment dependencies,
  physical-device acceptance and project-owner decisions; duplicate historical
  release records were removed from the active task list.
- Added `tools/build_release.ps1` as the only supported FPK release command.
  It stages only the authoritative `src/` tree in a temporary directory,
  excludes tests and Python bytecode, validates versions across fnOS, Web and
  Android, then verifies the outer FPK and inner payload before emitting
  `SHA256SUMS`.
- Added `src/tests/test_build_release_script.py`. Offline verification passed:
  151 Python tests, JavaScript syntax validation, four Node UI regressions and
  a complete FPK build/package inspection. The reproducible rebuild SHA-256 is
  `9804F776935DA64D74FFA43C8FC31B75132C3B0D8B661A6F41D762C7DA89BE92`.
- Reworked the repeat control to match Volumio's Media3 convention: neutral
  repeat when disabled, accent repeat for queue repeat, and an integrated `1`
  glyph for repeat-one. Removed the crossed-out repeat icon.
- The initial manually built 0.1.222 package installed on the NAS had SHA-256
  `906BE60546ADCCE1DCCCF72368251BD76C5845F738EEDC1456E5FB06E5FF4825`.
  The later reproducible offline rebuild is recorded above with its own hash.
- Installed the FPK through App Center on the DAC NAS. App Center and the
  running server both verified `0.1.222`.
- Ran the 20-track TEAC UD-301 queue acceptance: all positions appeared,
  `queue_traversal_verified=1`, `restore_verified=1`, 19 natural transitions,
  and zero underruns. Full evidence is in
  `docs/REAL_DEVICE_DAC_QUEUE_0.1.222.md`.
- Added and hardware-validated `tools/real_device_mpd_restart_run.sh`. A
  controlled MPD termination recovered playback through the supervisor, then
  restored the initial USB-DAC stopped session with `restore_verified=1`.
- Discovery recorded no available external Renderer, AirPlay receiver or
  Android/ADB device; no unsupported hardware case was claimed as complete.

## 0.1.204（MPD 重启状态同步与 P0 真机目标继续推进）

- 新增 `normalized_transport()`，恢复路径和 idle listener 统一从规范化 transport/MPD 原始状态推导 `PLAYING/PAUSED/STOPPED`。
- MPD 重启恢复完成后主动同步 idle/fault 状态并通知状态监听器，避免 WebView、PlaybackCore、Android MediaSession 误报 STOPPED。
- 本地 Python unittest 共 117 项通过；FPK SHA-256：`89F2F27701A5699180A80D9DD4C01586061004D7CC8099CA1A6BFE44E637BEFC`。
- FPK 已复制至真机 `/vol1/1000/fnaudio-0.1.204.fpk`，仍需通过 App Center UI“从 NAS 添加”完成安装后再做真机回归。
- 当前 P0 目标 1–7 保持未完成/进行中状态；小时级播放、息屏、物理热插拔、外部 DLNA Renderer、Android 多机和正式签名继续要求真实证据。

## 0.1.205（USB DAC 热插拔去抖）

- USB DAC 监控由单次探测切换为连续样本确认，降低 USB 重枚举期间误停 MPD 的概率。
- 新增 `mpd_device_presence_samples` 配置（1–5，默认 2），断开和恢复均需要达到阈值。
- 新增热插拔状态机和配置边界回归测试；本地 Python unittest 共 121 项通过。
- 修复安装回调端口保留顺序后，新增生命周期顺序回归；本地 Python unittest 共 122 项通过。
- 0.1.205 FPK SHA-256：`994712233E0707B85BE9759211EE71C80BA31A4BEDED9D3C41913768375FB1DE`。
- Android Debug APK SHA-256：`2B3F24FDF8488698F8679A4E6DFDD55D371C56313860AB29F7D71D5628CE2089`；Release 仍为 unsigned，不能作为正式发布包。
- 物理热插拔和真机安装验证尚未完成，目标 1–7 继续保持进行中。
- 0.1.205 已通过 App Center UI 覆盖安装；真实播放中终止 root MPD 后 supervisor 自动恢复，20 首队列、当前歌曲、进度和 `PLAYING` 状态恢复，`underrun=0`。详见 `docs/MPD_RESTART_RECOVERY_0.1.205.md`。
- 追加 TEAC UD-301 API 驱动复验：44.1 kHz PCM 播放至 105.60 秒，队列 20 首、`fault.state=PLAYING`、`underrun=0`；DSF 与 DFF 分别确认 `dsd64:2` Native DSD 源码输出，无 PCM fallback。测试后已恢复原 20 首队列、原当前曲和 STOP/IDLE 状态；详见 `docs/REAL_DEVICE_DAC_RECHECK_0.1.205.md`。
- 补充真机 PCM 控制闭环：pause/resume、seek、next/previous 均经 `playback/control` API 驱动验证，状态回传、原生队列和 underrun 指标正常。
- 启动真机 90 分钟 DAC 长测 runner（每 30 秒采样，结束自动恢复原队列/STOP）；启动阶段已确认 `PLAYING`、20 首队列和 `underrun=0`，最终结果待长测结束后回收日志。
- 长测运行约 5 分 26 秒已确认首个自动跨曲：第 1 首切换至第 2 首，MPD `nextsong=2`，队列 20 首且无 underrun；runner 继续运行中。
- 长测阶段性回收：19 个 30 秒样本已覆盖第 0/1/2 首，状态全部 `PLAYING`，20 首队列、最大 underrun 0；最终长测仍进行中。
- 长测约 12 分钟阶段覆盖第 0–3 首（24 个样本），状态仍为 `PLAYING`，队列 20 首、最大 underrun 0。
- 长测日志增加真机持久副本 `/vol1/1000/fnaudio-long-play-0.1.205.log`，避免会话删除后丢失验收材料。
- 新增 `tools/real_device_short_queue_after_long.sh`：等待长测结束后自动执行 20 首短曲跨曲验证，记录 queue-index 变化，并恢复原队列与 STOP 状态。
- 新增 `docs/REAL_DEVICE_AUTOMATION_0.1.205.md`，记录真机 runner、持久日志和会话删除后的恢复方法。
- 新增 `tools/analyze_real_device_playback_log.py`，可解析 base64 长测日志或 raw JSON 短队列日志，输出采样数、跨曲数、队列长度、fault 和 underrun 摘要。
- 校正短队列验收窗口：实测所选 20 首总长约 36 分 28 秒，因此验证器上限改为 50 分钟，并在 20 个 queue item 全部出现后提前结束；避免 15 分钟窗口造成“只验证部分曲目”的假完成。
- 新增真实 USB 热插拔采集脚本与操作规程；脚本已在 NAS 上通过 `sh -n`，只读记录 ALSA/MPD 状态，不采用 sysfs unbind/bind 模拟。
- 加强短队列自动验收：恢复原队列和 STOP 请求后追加 MPD 状态采样，记录最终队列长度、当前曲目、transport 与 fault。
- 长测阶段性回收更新至 2026-08-10 11:20：125 个有效样本覆盖 5 个队列项、4 次自动跨曲，队列始终 20 首，fault 始终 `PLAYING`，最大 underrun 为 0；90 分钟最终回滚仍待完成。
- 修复 `src/cmd/install_callback` 的配置端口保留顺序：先采用已有端口再探测可用回退端口，避免默认端口被占用时误改用户端口。新增回归测试，并在 NAS 临时夹具中验证 install/config/upgrade/uninstall keep/purge 全流程通过（`lifecycle-callbacks=pass`）。
- 90 分钟 TEAC UD-301 长测已完成：181 个样本、12 个 songid、11 次自然跨曲，测试队列始终 20 首、最大 underrun 为 0。第 146–148 个样本有 API timeout 造成临时 `fault.state=SUSPECT`，但 MPD 始终 `play` 并自动恢复为 `PLAYING`；详见 `docs/REAL_DEVICE_LONG_RUN_0.1.205.md`。历史恢复清单后续被发现有无效 ID，因此原生恢复长度需重新核验。
- 长测退出后，短队列完成 20 个不同项目的自然自动下一曲；全程为 PLAYING、测试队列 20、underrun 0。旧脚本恢复后 MPD 原生队列为 16 首，首次独立恢复为 19 首，均不能视作恢复通过。
- 已根据当前音乐库查询修正 4 个恢复歌曲 ID，新增独立恢复工具和静态一致性回归测试；Python unittest 增至 123 项。最终的正确恢复命令因 SSH 会话中断未提交，真机恢复测试已按用户要求暂停，待恢复连接后先恢复并核验 20 首原生队列、STOP 和 fault。

## 0.1.202（DSD 探测状态同步与生命周期修复）

- ALSA 忙状态探测增加强制刷新和有限重试，避免 MPD 刚停止时残留的 `EBUSY` 缓存误阻止 DSD。
- DSD 播放继续严格要求 Native DSD/DoP 验证，未验证时仍拒绝转 PCM。
- App Center 生命周期脚本兼容实际扁平 UI 安装布局，修复 `service_port.json` 写入错误路径。
- 真机 TEAC UD-301 验证 DSF 与 DFF 均以 `dsd64:2` 源码播放，未发生 PCM fallback。
- 本地 Python 测试 113 项通过；Android `lintDebug`、`assembleDebug` 通过。
- 构建物与验收记录见 `artifacts/0.1.202/`、`docs/APPCENTER_LIFECYCLE_0.1.202.md`。
- 真机短周期回归：20 首 PCM 队列自动推进、`underrun.count=0`；App Center restart 后 MPD 队列长度/当前索引/STOP 状态恢复，显式 play 后可继续播放。详见 `docs/REAL_DEVICE_REGRESSION_0.1.202.md`。
- TEAC UD-301 播放矩阵短测：PCM 44.1/48/96/176.4/192 kHz、DSF、DFF 通过；384 kHz 明确拒绝且不隐式重采样；控制冒烟和队列恢复后状态回滚通过。详见 `docs/PLAYBACK_MATRIX_0.1.202.md`。
- 新增 45 秒 96 kHz FLAC 连续播放监测，进度连续增长且无 underrun，测试后恢复原队列和停止状态。
- 记录真机日志中的 FLAC lost-sync、seek 和 wildmidi 缺失提示，暂不把它们误判为已修复，新增专项调查待办。
- 对两首 GAYLE FLAC 做独立 ffmpeg 校验，确认源文件本身损坏；后续考虑在库扫描或播放错误提示中显式区分源文件损坏与输出链路故障。
- Android `assembleRelease` 与 lintVital 通过；无发布 keystore 时产物保持 unsigned，`apksigner verify` 失败，未把它当作正式发布包。
- 真机配置边界回归：非法端口/不存在音乐目录返回 400，同端口保存不触发重启，队列和音乐库数据保持不变。

## 0.1.201（队列恢复与真机覆盖升级）

- 修复前端恢复超大播放队列时把 536 首 ID 拼成单个超长 URL 的问题；改为 100 首一批，并在临时请求失败时保留缓存行。
- 新增前端回归断言，覆盖分批恢复和失败批次保护逻辑。
- 根版本、FPK manifest、服务端版本、Web 缓存键和 Android versionCode/versionName 统一为 `0.1.201`。
- 本地 Python 112 项、3 个 Node 回归脚本、Android lint/Debug 构建全部通过。
- 真机 App Center UI 覆盖升级成功；版本 `0.1.201` 运行中，fnAudio 重开后当前队列恢复为 536 首。该证据不等同于完成 1–7 全部硬件矩阵。

## 0.1.198（继续推进目标 1–7）

- Android 远程播放 MediaSession 修改重复/随机模式时携带明确目标值，避免手机缓存与服务端状态不一致导致反向切换。
- 服务端播放控制接受 `repeat=off|one|all` 与布尔 `shuffle` 的显式值；未提供目标值时保留旧 toggle 兼容行为。
- 新增 PlaybackCore 回归测试；本地 Python 109 项、Android `lintDebug` 与 `assembleDebug` 全部通过。
- 真机 `vinson023.eu.org:5666/:3100` 仍不可达，本轮未宣称硬件、后台、息屏或多机验证完成。
- 修复 `src/cmd/install_callback` 覆盖安装时覆盖整个 `config.json` 的问题，改为保留既有 MPD、输出、DLNA 和用户配置，只更新安装向导字段；新增生命周期脚本回归测试。
- 重建 FPK：`artifacts/0.1.198/fnaudio-0.1.198-rebuild.fpk`，SHA-256 为 `17C5EE318C110EDF4D5097A1E83A5F57D7319F4EF5D23924A371BADDCBB816D8`。
- 备用机只读检查确认当前运行 `0.1.178`；CLI 安装 dry-run 被 App Center 自定义向导/UI-only 依赖拦截，未启动覆盖安装。
- 新增 `docs/APPCENTER_LIFECYCLE_0.1.198.md`，记录备用机的当前证据、UI 升级步骤和会话删除后的恢复路径。

## 0.1.199（真机目标 1–7 继续）

- 统一 FPK、Web UI 缓存版本、服务端 `Server` 头和 Android `versionCode/versionName` 到 `0.1.199`，用于强制触发 fnOS 覆盖升级。
- 通过 App Center UI 完成 FPK 覆盖更新，已安装列表可见 fnAudio，点击“打开”后界面可加载。
- 本地 Python 111 项、Android lint/Debug 构建通过；USB DAC 长时、热插拔、DSD 全矩阵、DLNA Renderer、Android 多机和完整生命周期仍按 TODO 保持未完成。

## 0.1.198

- 修复 `/api/playback/control` 未持久化 stop/pause/next/previous/play/seek 等控制结果的问题，避免 App Center 重启后恢复旧的播放状态。
- 控制接口返回播放会话 `revision`，便于前端和恢复流程确认状态已写入。
- 修正 `server.py` 的 `Server` 头和 `index.html` 静态资源缓存参数仍硬编码为 `0.1.197` 的版本漂移问题，统一到 `0.1.198`。
- 增加 Android release keystore 参数化配置；密钥只从 Gradle properties/环境变量读取，不进入仓库，Debug 构建行为不变。
- 已验证 `assembleRelease` 在无密钥时产出明确的 `app-release-unsigned.apk`；`apksigner verify` 拒绝该包，正式发布仍必须注入 release keystore。
- 新增回归测试覆盖停止状态持久化和发布版本一致性；Python 测试总数 107 项通过。
- 重新构建 `artifacts/0.1.198/` FPK 与 Android Debug APK。
- 0.1.198 已上传并通过 App Center UI 启动真机覆盖升级，但设备随后暂时失联，运行时版本尚待确认。

## 0.1.197

- DAC profile 增加 `track_settle_ms` 和 `keepalive_mode` 校验字段。
- 切换直连 ALSA 播放时先停止旧的 FFmpeg/aplay，再按 profile 等待，避免两个音频进程重叠导致 ALSA busy 和首帧卡顿。
- 增加可选的 MPD/FFmpeg `nice` 调度配置，默认保持 0，不改变既有设备行为。
- PCM keepalive 目前仅作为显式策略声明，默认关闭，Native DSD/DoP 不会被全局 keepalive 影响。
- 通过 fnOS App Center UI 将 `0.1.197` 覆盖升级到带 TEAC UD-301 的真机，应用状态确认 `running`，现有配置保留。
- 真机冒烟确认 PCM 播放/停止控制、TEAC UD-301 能力探测和 Native DSD64（DSF）源码播放；MPD 报告 `audio: dsd64:2`，未发生 PCM fallback。
- 真机长时间播放、物理热插拔、息屏后台、真实 DLNA Renderer 和 Android 多机型仍列为 P0 硬件验收目标，未提前标记为完成。

## 0.1.196

- 借鉴 Volumio 4 Stream Watchdog 的分层确认思路，为 MPD 增加 `IDLE/PLAYING/PAUSED/SUSPECT/RECOVERING/DEGRADED` 故障状态。
- 用户主动停止和歌曲自然结束不会触发故障升级；异常停止需要连续两次确认。
- 增加 MPD 状态平均耗时、故障次数、恢复次数和最近错误诊断字段。
- 新增 MPD 故障状态回归测试；Python 测试总数 103 项通过。

## 0.1.195

- 针对 USB DAC 播放时进度条、播放按钮和状态操作卡顿，拆分高频 MPD 播放状态与低频 ALSA 能力探测。
- `MpdService.output_capabilities()` 增加 4 秒缓存、过期后台刷新和设备切换失效机制；MPD 版本探测改为缓存。
- `/api/playback/status` 使用轻量 MPD 状态路径；前端增加远程状态请求防并发，并降低重复 UI 重绘。
- 本地 Python 100 项、Node UI 回归和 Android `assembleDebug` 通过；产物见 `artifacts/0.1.195/`。

## 0.1.194

- 修复 MPD 原生队列与逻辑队列在停止状态下不同步的问题；队列编辑同步支持 `play=false`，不会意外开始播放。
- 真机 TEAC UD-301 实测 DFF Native DSD，MPD 报告 `audio=dsd64:2`；384 kHz PCM 被明确拒绝且不隐式重采样。
- 同一真机补测 DSF Native DSD，MPD 同样报告 `audio=dsd64:2`，播放后队列可恢复。
- 使用 root 权限对 TEAC USB 节点 `1-4` 完成一次 unbind/bind 模拟拔插，MPD 自动停止并恢复当前歌曲、队列和 DAC 能力。
- 使用短测试曲验证 MPD 原生队列自然切歌，未执行前端 stop/clear/add 重建。
- 已通过 fnOS App Center 覆盖安装 0.1.194；停止状态同步后 MPD `playlistlength=2` 且保持 `STOP`，升级后队列和 DAC 标识均保留。

## 0.1.193（2026-08-09）

- 对照 Volumio 4 `mpdoutput` 的输出生命周期思路，修正 ALSA 能力探测在 MPD 持有设备时的状态抖动：如果此前已经成功完成 `hw_params`，后续 `-16 busy` 刷新会保留已验证的 PCM/Native DSD 格式，同时公开当前 busy 状态；从未验证过的设备不会被提升为已验证。
- MPD 输出能力增加 `dsd_advertised` 字段，用于表示 USB 驱动描述符声明的 DSD 能力；`native_dsd_verified` 继续只表示实际 ALSA 参数协商成功，避免把驱动广告误报为真实原生输出。
- 验证：Python unittest 99 项通过；新增 busy 探测保留/不提升回归测试。0.1.192 真机升级后队列保留、TEAC UD-301 可播放且 `underrun.count=0`；本修复以 0.1.193 重新部署。物理热插拔、Native DSD/DFF 矩阵、DLNA Renderer、AirPlay、Android 多机型仍待硬件验证。

## 2026-08-08：`0.1.189` 启动恢复与真实 transport 校验

- MPD 队列恢复加入 2/5/12 秒有界重试，覆盖 MPD 数据库启动竞态。
- 恢复播放后读取 MPD 实际 transport；DAC 不支持源格式导致 STOP 时，逻辑层回滚为 STOPPED 并保存状态。
- 真机 TEAC UD-301：44.1/192 kHz PCM、Native DSD64、384 kHz 拒播保护、stop/play/next 和 7 首队列恢复通过。
- Python 回归新增恢复重试和假 PLAYING 防护测试。

## 2026-08-08：`0.1.186` 发布收尾与版本一致性

- 修正 `src/app/ui/index.html` 的 CSS/JS 缓存参数和 `src/app/server/server.py` 的 `Server` 版本，避免升级后仍命中旧前端资源或报告旧版本。
- 重新生成 `SOURCE_MANIFEST.sha256`，重新构建 FPK，并核对 FPK 内层源码实际版本。
- Python 93 项、Node UI 3 项、Android lint/assemble 全部通过。
- FPK SHA-256：`45B10A74B51A111A4B78CCFAAC03B07AEC78DC00C7B4C531AB0DB6F4047CA46C`。
- App Center 列表虽显示 0.1.186，但运行进程仍报告 0.1.181；已记录为 fnOS 覆盖升级 payload 未替换问题，待进一步检查升级任务日志。

## 2026-08-08：`0.1.184` 播放能力边界与 underrun 可观测性

- DLNA 推送在 Renderer 明确声明不支持 DSD 时直接返回“设备不支持源码 DSD”，不再静默转码为 PCM。
- MPD underrun、broken pipe、ALSA error 和 audio output error 现在记录计数、最近错误、最近自动重启时间及被抑制次数，并通过 MPD idle 状态暴露。
- 参考 Volumio 的能力协商和播放守护思路；未知 Renderer 能力仍保持兼容尝试，避免误伤旧设备。

## 2026-08-08：`0.1.183` bit-perfect 采样率保护

- MPD ALSA 输出关闭自动重采样、自动格式转换和自动声道转换。
- 播放前依据真实 DAC 能力拒绝不支持的 PCM 采样率，避免 384 kHz 被静默降为 352.8 kHz。
- 真机 TEAC UD-301 验证：44.1 kHz PCM、DFF Native DSD（`dsd64:2`）正常；384 kHz 明确失败。
- 新增配置和不支持采样率回归测试，Python 测试总数 88 项。

## 2026-08-07：`0.1.175` DSD 源码直推

- DLNA DSD 资源不再强制转码为 96 kHz/24 bit WAV。
- DSF/DFF URL、MIME、扩展名、资源大小均来自原始文件；MediaServer 和 Renderer Push 强制 `original` 媒体模式。
- 浏览器播放仍保留显式 `dsd_wav` 转码能力，避免影响手机/浏览器兼容播放。
- 新增回归测试，确认 DSD 推送不会调用转码回调。

## 2026-08-07：`0.1.174` 服务生命周期与真机验收

- 修复 `src/cmd/main`：启动前清理旧版本遗留的 fnAudio `server.py`，停止时清理当前及遗留 MPD，防止旧 18080 与新 18081 双实例并存。
- 版本统一为 `0.1.174`，同步 FPK manifest、前端缓存键和 Android versionCode/versionName。
- 本地验证：62 个 Python 测试、3 个 Node 回归脚本、shell 语法、Android Lint/Debug 构建通过；正式 FPK 内层无 `.pyc`。
- 真机验证：单 server/单 MPD/无 zombie；健康、音乐库、浏览器控制、跨重启队列恢复、DSD WAV 96 kHz/24 bit 通过。
- 未完成：真实 USB DAC、DLNA Renderer 和多机 Android 安装矩阵仍需硬件/设备验收。

## 2026-08-07：`0.1.173` USB DAC、远程队列、DSD 与 Android 会话恢复

- 后端以 MPD 状态事件处理 USB DAC 自然结束和自动下一曲，显式停止/换曲加入事件抑制，避免误推进。
- Playback Core 不再在输出失败时乐观发布播放状态；直接 ALSA 启动补齐成功返回值。
- 前端远程 load 去重；恢复跨浏览器/Android 播放会话时读取服务端状态而不重复开播；MPD 自动下一曲不再依赖前端计时器。
- DSD DLNA 推送改为一致的 96kHz/24bit WAV PCM 资源声明，并尝试预装下一曲。
- Android 启动前验证并刷新 token，支持 longToken/保存密码回退；最低系统调整为 Android 6.0，兼容实现通过 Lint。
- 本地验证通过：62 个 Python 测试、3 个 Node 回归脚本、Android `lintDebug` 与 `assembleDebug`。未进行 fnOS、USB DAC、DLNA Renderer 或 Android 真机验收。

## 2026-08-07：`0.1.172` PC 右键菜单与文件夹定位语义修复

- 目标：PC 端右键菜单取消“播放”和“插播所选项目”，同时不影响移动端四项长按菜单和歌曲操作对话框。
- 修改文件：`src/app/ui/app.js`、`src/tests/test_ui_queue_columns.js`、版本与发布上下文文档。
- 菜单行为：新增 `desktopTrackContextActionButtons()`，桌面歌曲右键从完整歌曲操作中过滤 `play`/`insert`；文件夹/专辑等分组右键同步移除“播放”和“插播所选项目”；`trackContextActionButtons()` 继续只提供移动端四项快捷操作；`openTrackActionDialog()` 仍使用完整 `trackActionButtons()`。
- 文件定位：`openContainingFolder()` 继续读取 `api/library/location`，但只调用 `sdk.openFileManager(folder)`。fnOS 宿主的 `openFileManager` 接口接收目录路径；传入 `/vol1/.../歌曲.mp3` 这类完整文件路径会被解释为打开文件。当前未确认公开接口支持“打开父目录并自动选中文件”的额外参数，因此不伪造选中行为。
- 验证：`node --check app/ui/app.js`、`node tests/test_ui_queue_columns.js` 通过；真机 fnOS 文件管理视觉定位和 Android 安装尚未验证。
- 版本：统一到 `0.1.172`，后续产物记录在 `artifacts/0.1.172/`。

## 2026-08-07：`0.1.171` PC/移动菜单分离、文件定位、封面 fallback 与 Android 通知封面

- PC 端右键恢复完整歌曲操作菜单；移动端长按继续使用四项快捷菜单。
- “打开包含的文件夹”将完整歌曲路径传递给 fnOS 文件管理入口，便于直接定位文件。
- 歌曲行有真实封面时隐藏音乐符号；无封面统一显示 `♫`，DSD 不再使用单独符号，并在封面加载失败时恢复 fallback。
- Android Media3 新增 `AuthenticatedBitmapLoader`，同源封面请求附加 fnOS token Header/Cookie，结果写入应用私有缓存后交给通知栏 BitmapLoader；无封面继续使用白色占位图。
- 验证：59 个 Python 测试、JavaScript 语法、3 个 Node 回归脚本、Android Debug 编译通过；未连接 Android 真机。

## 2026-08-07：`0.1.170` Android 媒体卡片白色占位图标

- 目标：按截图把 Android 桌面/锁屏媒体卡片左侧的黑色默认播放图标改成白色，同时不覆盖真实歌曲封面。
- 通知图标：`PlaybackService` 显式配置 `DefaultMediaNotificationProvider`，将小图标设置为新增的白色描边播放圆环 `R.drawable.ic_notification`。
- 无封面占位：`NativePlaybackBridge` 在应用私有目录生成一次透明底、白色播放圆环的 512×512 PNG；无真实 `artwork` 时用文件 URI 写入 Media3 元数据，真实封面 URL 仍优先。
- 大队列保护：没有把 PNG 字节直接写进每一个 `MediaItem`，避免数千首队列重复携带位图并触发内存放大或 Binder 事务过大。
- 验证：59 个 Python 测试、3 个 Node 回归脚本、JavaScript 语法、Android Java 编译、Lint 和 Debug APK 构建全部通过。APK 资源表包含 `drawable/ic_notification`，manifest 为 `0.1.170 / versionCode 170`，v2 Debug 签名有效；FPK 外层/内层为 21/110 项且无 Python 字节码。
- 产物：FPK `4,885,020` 字节，SHA-256 `3996D1E8E4E693EF889B46845F3ED59D677C5BD2B2A3295345485DDDD4FA7493`；APK `10,085,880` 字节，SHA-256 `1D4CE15B07B46289DC277A4EB26CCB7FFCA29488A6A1E29D41EC812C171A41BF`。
- 待验证：本轮没有连接 Android 真机；需分别播放无封面和有封面歌曲，确认媒体卡片/通知白色图标、真实封面优先、切歌更新以及后台/息屏行为。

## 2026-08-07：`0.1.169` 歌曲右键/长按四项菜单

- 目标：歌曲列表在桌面右键和移动端长按时，只显示“从当前开始播放所有歌曲、加入当前队列、收藏歌曲、加入播放列表”四项，并保持指定顺序。
- 交互：桌面继续使用 `contextmenu`；移动端新增 550ms Pointer Events 长按。手指移动超过 10px、触点取消或列表滚动会取消长按，触发成功后拦截随后生成的点击，避免松手时误播放。
- 菜单边界：新增独立 `trackContextActionButtons()`，不再把播放、插播、歌曲信息、打开文件夹、分享或页面移除操作混入右键/长按菜单；旧操作对话框保留原能力。
- 行为语义：“收藏歌曲”使用只添加的 `addSelectedFavorites()`，已收藏歌曲不会因菜单文字固定而被反向取消；“从当前开始播放所有歌曲”仍调用 `allTracksForCurrentContext()`，保持加载当前完整列表而非当前分页。
- 移动样式：菜单宽度限制在视口内，操作行提高到 44px，并关闭歌曲行文字选择和系统触摸呼出，降低 WebView 长按冲突。
- 验证：59 个 Python 测试、3 个 Node 回归脚本、JavaScript 语法、Android Java 编译、Lint 和 Debug APK 构建全部通过。FPK 外层 21 项、内层 110 项且无 Python 字节码；APK manifest 为 `0.1.169 / versionCode 169`，v2 Debug 签名有效；包内 UI 文件哈希与源码一致。
- 产物：FPK `4,884,683` 字节，SHA-256 `E061CA3A761D7BA5E3F6C48604B700E340F938C372A3A90D02C8210C8E2EDD56`；APK `10,083,954` 字节，SHA-256 `EC2A690930E4560D003CBDF048857E3A75945101C57C1FA0BB559338EDBA7F02`。
- 待验证：本轮没有连接 fnOS/Android 真机；需在桌面浏览器和 Android WebView 验证右键/长按、滚动取消、松手不播放、完整列表入队、收藏只添加以及加入队列/歌单。

## 2026-08-07：`0.1.168` Android 多连接历史修复

- 目标：修复历史连接只能显示当前一条、登录第二个 NAS 会覆盖第一条的问题。
- 根因：登录页预填活动连接时保留其 UUID；用户修改服务器后，`ConnectionProfile.create()` 仍使用旧 UUID，`SecureProfileStore.upsert()` 因而删除旧行并写回新地址。
- 飞牛参考：本地 `FN_Media.apk` 的 Flutter 资源包含独立 `fn_connect` 连接模块和“手动添加”入口，说明选择已有设备与新增连接是两个明确动作。fnAudio 采用同样的交互原则，不复制其商业素材。
- 身份规则：规范化 host、端口、HTTP/HTTPS 和账号共同构成连接身份。普通表单改变身份会生成新 UUID；显示名、密码或证书选项变化更新匹配记录；完全相同身份复用已有记录，避免重复项。
- 历史页：新增“新增连接”按钮，返回空白表单；“编辑”显式保留所选 UUID，即使地址发生变化也只更新该记录。选择现有记录登录仍直接恢复对应连接。
- 验证：59 个 Python 测试、3 个 Node 回归脚本、JavaScript 语法、Android Java 编译、Lint 和 Debug APK 构建全部通过。FPK 为 21/110 个条目且无 Python 字节码；APK manifest 为 `0.1.168 / versionCode 168`，v2 Debug 签名有效。
- 产物：FPK `4,883,808` 字节，SHA-256 `F363B6C2E23CE7697ECF08E7C81CF7A296696199E3EECC732B8855FE83F30CD4`；APK `10,083,946` 字节，SHA-256 `A4736CE6F304084B87E9E95BF410051D9BC4E14CB9F649F732D650AD7CD35748`。
- 待验证：没有连接 Android 真机；需实际保存至少两个 NAS、编辑其中一个、重新登录相同连接并删除其中一条，确认记录互不覆盖。

## 2026-08-07：`0.1.167` Android 原生认证 API 与双击返回登录页

- 目标：修复 Android 播放仍提示“播放队列保存失败（HTTP 200）”，并把根页面返回改为第一次提示、第二次进入登录页。
- 真实根因：在测试 fnOS 上复现到 CGI 外层 nginx 返回 `HTTP 200 text/plain`，正文为 `invalid token`，请求没有进入 `cgi_proxy.py`。WebView 的 `shouldInterceptRequest()` 能代理 GET，但拿不到 POST body，因此队列、状态和控制 POST 绕过了已认证的 OkHttp 路径。
- 官方 App 对比：缓存的飞牛媒体 App 使用 Flutter/原生网络、WebSocket 和原生媒体服务持有认证及播放生命周期。fnAudio 沿用“WebView 界面 + 原生认证请求 + Media3 播放”的轻量架构，不复制官方商业素材或私有实现。
- 原生认证桥：`NativePlaybackBridge` 新增 `requestJson()`；`MainActivity` 只允许当前 NAS 的 fnAudio `/api/` 以及 POST/PUT/PATCH/DELETE，统一附加 `Authorization`、`X-Fnaudio-Trim-Token` 和 token Cookie，通过 OkHttp 异步请求，再把状态、响应头和正文回传给网页。
- 网页 API：新增 `apiFetch()`、请求 ID/Promise 管理和 `fnAudioNativeOnHttpResponse()`。Android 环境的队列、用户状态、播放控制、转码预热、配置、共享目录同步和播放设备切换均走原生认证；普通浏览器继续使用标准 Fetch。
- 返回键：网页内部层级处理保持不变。根页面第一次返回显示“APP 即将退出，再按一次返回登录界面”，2.2 秒内第二次打开登录页并结束主页面；`EXTRA_SKIP_AUTO_RESUME` 阻止登录页立即自动重连。删除原有 `moveTaskToBack(true)` 根页面逻辑。
- 测试：59 个 Python 单元测试、3 个 Node 回归脚本、JavaScript 语法、Android `lintDebug` 与 `assembleDebug` 全部通过。FPK 外层 21 项、`app.tgz` 110 项且无 Python 字节码；APK manifest 为 `com.fnaudio.client / 0.1.167 / versionCode 167 / minSdk 26 / targetSdk 36`，v2 Debug 签名通过。
- 版本与产物：`fnaudio-0.1.167.fpk` 为 `4,884,107` 字节，SHA-256 `A5F5CF912C2477F1597D288201B5386552206B97870C49D1992D72D9741700DD`；`fnaudio-android-0.1.167-debug.apk` 为 `10,111,653` 字节，SHA-256 `5723CDAE06C7D94FCCD1B5D3E705D33AFC3165157996FFB23FE1C7DFB020FC34`。
- 待验证：本轮没有连接 Android 设备，不能宣称手机端播放和返回键已完成真机验证。需配套安装 `0.1.167` FPK/APK，至少播放两首歌曲，并确认第二次返回后登录页不会自动重连。

## 2026-08-07：`0.1.166` CGI 队列路由与 Android 返回修复

- 目标：修复播放时出现“播放队列保存失败（HTTP 200）”，以及 Android 系统返回键进入登录页的问题。
- CGI 路由：`cgi_proxy.py` 新增统一路径恢复，按显式 `X-FnAudio-Path`、`REQUEST_URI`、`PATH_INFO` 的顺序提取 `/index.cgi` 后的真实 API 后缀。播放队列 POST 主动携带 `/api/playback/queue` 路由 Header，即使 fnOS 只提供脚本级 `PATH_INFO`，也不会误代理到 HTML 首页。
- 前端诊断：队列响应先读取文本再解析 JSON；如果 CGI 回退返回 HTML，会显示“播放队列请求返回了错误页面”，不再把 HTTP 200 伪装成普通接口失败。
- Android 返回：登录成功启动 `MainActivity` 后立即结束 `LoginActivity`。系统返回键先调用网页 `fnAudioHandleAndroidBack()`，依次关闭对话框、上下文菜单、移动侧栏、歌词和嵌套分类；根页面只把应用任务移到后台，不调用可能进入 fnOS 登录/系统入口的 `WebView.goBack()`。
- 测试：新增 CGI `REQUEST_URI` 和显式路由 Header 回归；Android bridge 脚本同时检查网页返回入口、`MainActivity` 后台化逻辑与登录 Activity 出栈。59 个 Python 单元测试、3 个 Node 回归脚本、`node --check`、Android `lintDebug` 与 `assembleDebug` 全部通过。
- 版本与产物：统一为 `0.1.166`。`artifacts/0.1.166/fnaudio-0.1.166.fpk` 为 `4,883,638` 字节，SHA-256 `03993A17CA0E87BA063BFBE6764847B0650A0743BA6D5B5827C9913DA95FBD53`；`fnaudio-android-0.1.166-debug.apk` 为 `10,105,834` 字节，SHA-256 `84A476C8F62A68955A52A385A37D4E4DF71103A8FED514452753CF042F8B3909`。
- 包验证：FPK manifest 为 `fnaudio / 0.1.166 / x86`，外层 21 个条目、`app.tgz` 110 个条目且无 Python 字节码缓存；APK 为 `com.fnaudio.client / 0.1.166 / minSdk 26 / targetSdk 36`，Android Debug 证书的 v2 签名通过。
- 待验证：当前未连接 fnOS 或 Android 真机；必须在配套安装 FPK/APK 后确认真实 CGI POST 返回 JSON、队列播放成功、返回键顺序正确、重新打开应用仍保持 fnAudio 页面，以及后台/息屏跨曲不回归。

## 2026-08-07：`0.1.165` Android 刘海安全区、默认端口与大队列播放修复

- 目标：修复登录界面顶部空间不足、fnAudio 主页面与状态栏/前置摄像头区域重叠，以及大音乐库播放时弹出“播放队列保存失败”。
- Android 窗口：新增 `WindowInsetsHelper`，登录页、历史连接页和主 WebView 宿主根据系统状态栏、导航栏与 `displayCutout` 自动增加安全内边距；主页面使用浅色状态栏图标，登录/历史页保持深色状态栏。
- 登录页：端口输入框默认直接显示 `5666`，移除“HTTP 常用 5666、HTTPS 常用 5667”的提示；切换 HTTPS 时仅在当前端口仍为默认值时切换到 `5667`，避免覆盖用户手动输入。
- 播放队列：前端 `/api/playback/queue` 只发送歌曲 ID，不再发送完整歌曲对象；服务端同时兼容 ID 列表和历史对象格式。这样“从当前开始播放所有歌曲”在大曲库/CGI 网关下的请求体显著减小，失败提示也会显示 HTTP 状态或服务端返回消息。
- 测试：新增紧凑队列 ID 的服务端单元测试和 Android bridge 静态回归检查；57 个 Python 单元测试、3 个 Node 回归脚本、Android `lintDebug` 与 `assembleDebug` 全部通过。
- 版本与产物：统一升级为 `0.1.165`。`artifacts/0.1.165/fnaudio-0.1.165.fpk` 为 `4,880,353` 字节，SHA-256 `7D134D517321F6C8A247A1F75D5B2B1FCE2AB3BB897FA5E2AE6651281A6C2E97`；`fnaudio-android-0.1.165-debug.apk` 为 `10,079,754` 字节，SHA-256 `569B0A1F6D6FB21A186B5C477920EE01CE7D94FA0775DDC4B8BF5A6B4EBFBDE5`。
- 待验证：尚未安装到真实 Android/fnOS 设备；需重点确认不同刘海/挖孔机型的登录和主页面顶部位置，以及大队列播放、自动下一曲和后台息屏播放。

## 2026-08-07：`0.1.164` WebView 子资源鉴权与 FPK/Android 图标统一

- 目标：修复 Android 登录后页面只显示无样式 HTML、CSS/JS/封面和 GET API 资源无法携带 fnOS 会话的问题，并处理启动图标中间音符过大被裁剪、Android 图标与 FPK 不一致的问题。
- WebView 资源：`MainActivity` 对同源 GET 子资源通过 OkHttp 重新请求，统一附加 `Authorization`、`X-Fnaudio-Trim-Token` 和兼容 token Header；响应 `Set-Cookie` 同步回 WebView CookieManager；对 `/cgi/ThirdParty/fnaudio/app.css` 等缺少 `/index.cgi/` 的路径增加兜底重写。
- CGI 入口：`cgi_proxy.py` 在 HTML 入口服务端注入 `<base href="/cgi/ThirdParty/fnaudio/index.cgi/">`，防止不同 WebView 对内联脚本/CSP 的处理差异导致相对资源解析到错误目录。
- 登录与历史页：保留参考 `FN_Media.apk` 的卡片式深色布局、独立历史连接页面、保存密码和删除确认交互；参考 APK 只用于行为和字段设计，没有复制其商业素材。
- 图标：Android 普通图标和 adaptive icon 改为白色圆角底 + 蓝色音符，与 FPK `src/ICON_256.PNG` 保持一致；前景音符缩放到 `0.68`，留出自适应图标安全区域。
- 版本与产物：统一升级为 `0.1.164`。`artifacts/0.1.164/fnaudio-0.1.164.fpk` 为 `4,882,412` 字节，SHA-256 `C114A0F9360F9E6D12C3487D2543F751F958B3E1B8E42362E4273591F66D62F5`；`fnaudio-android-0.1.164-debug.apk` 为 `10,078,542` 字节，SHA-256 `81831D01106DADAB2A2C39DCDA305228F7F809BD7D44FFC7126D16F23500B089`。
- 验证：55 个 Python 单元测试、3 个 Node 回归脚本、Android `lintDebug` 与 `assembleDebug` 通过；FPK 外层 21 个条目、内层 `app.tgz` 110 个条目可读取；APK manifest 为 `com.fnaudio.client / 0.1.164 / minSdk 26 / targetSdk 36`，v2 Debug 签名验证通过。
- 待验证：尚未安装到真实 fnOS/Android 设备；需重点确认启动器图标显示、登录后 CSS/脚本/封面加载、保存密码与历史切换，以及后台/息屏跨曲播放。

## 2026-08-07：`0.1.163` Android 登录、历史连接、启动图标与 WebView 资源修复

- 目标：按真机截图修复 Android 启动图标白色外框、登录后 fnAudio 只显示无样式 HTML 的问题；允许安全保存密码，并把历史连接从登录页移到独立选择页面。
- WebView 根因与修复：部分入口最终 URL 是不带结尾斜杠的 `/cgi/ThirdParty/fnaudio/index.cgi`，相对的 `app.css`、`app.js` 和 API 路径因此解析到了 CGI 同级目录。`index.html` 现在会在检测到 `/index.cgi` 时、首个样式请求前写入以 `/index.cgi/` 结尾的 `<base>`；直接访问本机 TCP Web 服务时保持原路径。
- Android 登录与存储：`ConnectionProfile` 新增密码字段，与连接地址、账号和 token/longToken 一起进入 Android Keystore AES-GCM 加密载荷；`android:allowBackup=false` 保持不变。令牌恢复失败后会自动使用已保存密码登录，日志和界面不会显示明文。
- 历史连接：登录页只保留“历史连接”按钮；新增独立 `ConnectionHistoryActivity`，可选择连接、进入编辑或删除本机加密资料。
- 图标：launcher 改用 Android adaptive icon，蓝色背景由系统蒙版裁切，白色音符作为前景，避免 legacy 图标被启动器再次套白色圆角底框。
- 版本与产物：统一升级为 `0.1.163`。`artifacts/0.1.163/fnaudio-0.1.163.fpk` 为 `4,882,182` 字节，SHA-256 `DA31F9DFF9974A416CBB088CD30C8530D00D1AAF25BD6AC4DCFC04D0933856C2`；`fnaudio-android-0.1.163-debug.apk` 为 `10,071,583` 字节，SHA-256 `7DD22857DE994B89E8877FE38890A5972733938CA2A989219B8F4E660C4ED053`。
- 验证：53 个 Python 单元测试、3 个 Node 回归脚本、JavaScript 语法、Android `lintDebug` 和 `assembleDebug` 通过；APK manifest 为 `com.fnaudio.client / 0.1.163 / minSdk 26 / targetSdk 36`，v2 Debug 签名验证通过；FPK manifest 为 `fnaudio / 0.1.163 / x86`，外层 21 个条目、内层 `app.tgz` 110 个条目可读取。
- 待验证：尚未安装到真实 fnOS/Android 设备。需重点确认启动器图标显示、保存密码后的切换/删除、令牌失效自动登录、CSS/脚本正常加载，以及后台/息屏跨曲播放。

## 2026-08-06：`0.1.162` Android 混合客户端与原生后台播放

- 执行者：Codex
- 目标：开发轻量 Android 客户端，由 WebView 复用 fnAudio 界面，由 Android 原生服务负责队列和播放；支持输入地址、端口、HTTPS、账号密码以及多连接历史，登录后直接打开 fnAudio。
- Android 工程：新增 `android-client/`，使用 Java 17、AGP 9.3.1、Gradle 9.6.1、Media3 1.10.1、ExoPlayer 和 OkHttp。
- 登录与历史：通过 `ws(s)://<host>:<port>/websocket?type=main` 发送 `user.login`，兼容 `user`/`username`；历史恢复尝试 `user.authToken` 和 `user.tokenLogin`。Android Keystore 加密保存地址、账号和 token/longToken，不保存密码。
- WebView：登录后直接加载 `/cgi/ThirdParty/fnaudio/index.cgi/`，初始请求携带 Authorization/Header，并设置同源 token Cookie；异常跳转到桌面/系统入口时显示重新登录提示。
- 原生播放：新增 `PlaybackService` 和 `NativePlaybackBridge`。Web UI 在 Android 桥存在时把完整队列、当前项、播放/暂停、前后曲、seek、音量、循环和随机交给 MediaController；MediaSessionService 持有 ExoPlayer 队列、自动下一首、通知、媒体键、音频焦点、耳机拔出和唤醒锁。
- fnOS 配套：`app.js` 保留普通浏览器 HTML audio 路径，同时增加原生状态回传和恢复逻辑；`cgi_proxy.py` 增加同源 Cookie token fallback。版本同步更新为 `0.1.162`。
- 构建产物：`artifacts/0.1.162/fnaudio-0.1.162.fpk`，SHA-256 `7253729113AEA07F55B93372EDC78BFE4E04E4EB991D71B3EFADEABD8C17CB9A`；`fnaudio-android-0.1.162-debug.apk`，SHA-256 `17898F32B6824C152AF5AA7DE34CE7F8C160547E1BB82028164D785A619C6EF9`。
- 验证：53 个 Python 单元测试、3 个 Node 回归脚本、JS/Python 语法、Android `lintDebug`、`assembleDebug`、APK v2 签名、APK manifest、FPK 外层/内层结构和关键源文件哈希均通过。
- 未验证：当前无 ADB 设备连接，尚未安装 APK/FPK；fnOS 登录 token 到 CGI 的真机交接、2FA/HMAC 固件、自签名 HTTPS、后台/息屏跨曲、通知/锁屏/蓝牙控制、多连接切换和厂商省电限制均待验证。当前 APK 是 Debug 签名，不是正式发布包。

## 2026-08-06：`0.1.161` 虚拟键盘直接覆盖固定播放器

- 目标：让移动端输入法直接覆盖底部歌曲信息和播放控制区域，避免隐藏恢复逻辑及播放器随键盘移动造成的掉帧。
- 修改：搜索期间播放器始终保持 `position:fixed` 和 `display:grid`；保留 viewport 的 `interactive-widget=overlays-content`，并在 WebView 支持时设置 `navigator.virtualKeyboard.overlaysContent = true`，不支持或拒绝写入时安全降级。
- 性能：搜索聚焦期间暂停歌曲信息跑马灯、阴影和过渡，并跳过跑马灯尺寸及移动分页位置测量；失焦后统一恢复一次，避免键盘动画中的同步布局读取。
- 文件：`src/app/ui/app.css`、`src/app/ui/app.js`、`src/app/ui/index.html`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.161/` 和项目恢复文档。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归、移动布局回归和 FPK 结构校验均通过；包外层 18 个文件、运行时 97 个文件，未包含测试、数据库或 Python 缓存。
- 版本与产物：`0.1.161`；`artifacts/0.1.161/fnaudio-0.1.161.fpk`，4,879,924 字节，SHA-256 `427CA1E87EB6030413B11453AF6D120D6B113C1B2835A54260F4F060342CB875`。
- 设备验证：按用户此前要求不代为安装，由用户自行安装测试；输入法覆盖模式、动画流畅度和不支持 Virtual Keyboard API 时的降级行为仍需真机确认。

## 2026-08-06：`0.1.160` 搜索期间保持移动播放器可用

- 目标：修复搜索时隐藏底部歌曲信息和播放控制区域后，部分移动 WebView 无法再次打开播放器的问题。
- 根因：`0.1.159` 通过输入框 `focus` 隐藏播放器，并依赖 `blur` 恢复；部分 WebView 在收起虚拟键盘后不会可靠触发 `blur`，播放器因此永久保持隐藏状态。
- 修改：播放器在搜索期间始终保持 `display:grid`，只切换为绝对定位；暂停歌曲信息跑马灯，关闭阴影和过渡以降低输入法动画期间的重绘；viewport 增加 `interactive-widget=overlays-content`。保留焦点状态类用于性能样式，不再用于播放器显隐。
- 文件：`src/app/ui/app.css`、`src/app/ui/index.html`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.160/` 和项目恢复文档。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归、移动布局回归和 FPK 结构校验均通过；包外层 18 个文件、运行时 97 个文件，未包含测试、数据库或 Python 缓存。
- 版本与产物：`0.1.160`；`artifacts/0.1.160/fnaudio-0.1.160.fpk`，4,880,027 字节，SHA-256 `E224641A09A05F5352BA0A24F02F098CB5E33CE967CA4619E855CE5D740F54CE`。
- 设备验证：按用户要求不代为安装，由用户自行安装测试；输入法动画流畅度、键盘覆盖行为和播放器可操作性仍需真机确认。

## 2026-08-06：`0.1.159` 移动分页居中与输入法性能优化

- 目标：移动分页信息和按钮居中显示，并消除搜索输入法弹出时底部播放器上移造成的卡顿。
- 修改：移动分页容器和按钮组改为整行居中，页码摘要取消继承的 `flex:1`；搜索获得焦点时一次性隐藏播放器并扩展内容区，失焦后恢复，不监听键盘动画期间的连续 resize。
- 文件：`src/app/ui/app.css`、`src/app/ui/app.js`、`src/app/ui/index.html`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.159/` 和项目恢复文档。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归、移动布局回归和 FPK 结构校验均通过。
- 版本与产物：`0.1.159`；`artifacts/0.1.159/fnaudio-0.1.159.fpk`，4,879,931 字节，SHA-256 `E20A98721E436D6497C19FD0AA15E3B27AD495E8BB180C9B225E8ED9A467CB43`。
- 设备验证：按用户要求不代为安装，由用户自行安装测试；输入法动画流畅度仍需真机确认。

## 2026-08-06：`0.1.158` 移动搜索返回主页面

- 目标：把移动搜索栏恢复到主页面顶部，并移除左上角更多菜单中的返回按钮。
- 修改：主内容列表上方新增独立 `type=search` 输入，提供搜索图标、圆角容器、聚焦高亮和原生清除；侧栏恢复为纯导航结构，删除 `mobileBackBtn`、相关样式和 `handleMobileBack()`。
- 文件：`src/app/ui/index.html`、`src/app/ui/app.css`、`src/app/ui/app.js`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.158/` 和项目恢复文档。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归、移动布局回归和 FPK 结构校验均通过。
- 版本与产物：`0.1.158`；`artifacts/0.1.158/fnaudio-0.1.158.fpk`，4,879,685 字节，SHA-256 `973795FCA58069CA66CDFE66FDFA168DE8E4E0C63ADD59ACA2E2842DCA379EF2`。
- 设备验证：按用户要求不代为安装，由用户自行安装测试。

## 2026-08-06：`0.1.157` 移动搜索与返回布局重构

- 目标：解决移动侧栏中搜索框被返回按钮挤压、输入空间不足的问题，同时明确返回按钮的位置和视觉。
- 修改：第一行使用 `32px + 1fr` 网格放置返回图标与“音乐库”标题；第二行搜索框横跨两列、占满侧栏宽度；返回按钮改为带边框的 SVG 箭头按钮。桌面端仍保持搜索框在导航标题之前。
- 文件：`src/app/ui/index.html`、`src/app/ui/app.css`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.157/` 和项目恢复文档。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归、移动布局回归和 FPK 结构校验均通过。
- 版本与产物：`0.1.157`；`artifacts/0.1.157/fnaudio-0.1.157.fpk`，4,880,068 字节，SHA-256 `DE79ED0FD54E147B3EEA7CD746078496F012DBDC3A4F55B89BD55D79AB3B609C`。
- 设备验证：按用户要求不代为安装，由用户自行安装测试。

## 2026-08-06：`0.1.156` 移动歌词页顶部布局压缩

- 目标：减少移动端歌词界面顶部空白，使返回、歌曲信息、收藏和歌词首屏布局更紧凑合理。
- 修改：移除歌词页对 `safe-area-inset-top` 的重复网格行高与 padding 计算；标题栏固定为 `48px`，三列宽度改为 `52px / 1fr / 52px`，按钮缩小为 `50x30px`；歌词面板顶部 padding 调整为 `8px`。
- 文件：`src/app/ui/app.css`、`src/app/ui/index.html`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.156/` 和项目恢复文档。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归、移动布局回归和 FPK 结构校验均通过。
- 版本与产物：`0.1.156`；`artifacts/0.1.156/fnaudio-0.1.156.fpk`，4,879,848 字节，SHA-256 `978A582966255E14AF0694685697596FB67A2019EC72FA1DA481E2BFE06BD28F`。
- 设备验证：按用户要求不代为安装，由用户自行安装测试。

## 2026-08-06：`0.1.155` 移动侧栏顶部压缩

- 目标：按移动端截图缩小侧栏及顶部返回、搜索、“音乐库”区域的占用。
- 修改：移动侧栏最大宽度由 `290px` 收窄到 `268px`；返回按钮和搜索框放入同一行；侧栏顶部改为固定紧凑留白，“音乐库”标题紧随工具行。
- 文件：`src/app/ui/index.html`、`src/app/ui/app.css`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.155/` 归档记录和项目恢复文档。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归、移动布局回归和 FPK 结构校验均通过。
- 版本与产物：`0.1.155`；`artifacts/0.1.155/fnaudio-0.1.155.fpk`，4,879,937 字节，SHA-256 `D8FA806C30C6B3CA0C80592CAF4C66CBB02A75230FEDBEAF961E059D626C6474`。
- 设备验证：按用户要求不代为安装，由用户自行安装测试；浏览器安全策略不允许直接渲染本地 `file://` 页面，因此未宣称完成截图级或真机视觉验收。

## 2026-08-06：`0.1.154` 移动端菜单与分页体验优化

- 目标：压缩移动侧栏返回和搜索占用；从右下角更多菜单移除歌词；歌曲列表分页仅在确有多页且滚动到底部时显示。
- 修改文件：`src/app/ui/app.js`、`src/app/ui/app.css`、`src/app/ui/index.html`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.154/` 归档记录。
- 实现：返回改为紧凑图标按钮，侧栏顶部和搜索框高度/间距缩小；移动更多动作不再生成歌词项；分页 `pages <= 1` 时完全不渲染，移动端分页栏默认隐藏，列表滚动到底部后显示。
- 版本与产物：`0.1.154`；`artifacts/0.1.154/fnaudio-0.1.154.fpk`，4,879,719 字节，SHA-256 `81562B56F54490F8C1E84E3D06B76606E2D44AF7B94649C365B364F4B464C2A9`。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归和移动端布局回归均通过；包内 manifest、缓存键和 97 个运行时文件已校验。
- 设备验证：尚未完成。fnOS 应用中心手动安装需要自定义向导参数，官方 `trim-cli app install-fpk` 已连接设备但返回该安装限制，设备仍运行 `0.1.153`。

## 2026-08-06：`0.1.153` 移动端初始化修复与 fnOS 验收

- 目标：完成移动端布局修复后的可安装发布，避免移除移动搜索输入后阻断初始化，并记录真实设备结果。
- 修改文件：`src/app/ui/app.js`、`src/app/ui/app.css`、`src/app/ui/index.html`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`、`SOURCE_MANIFEST.sha256`，以及当前恢复/发布文档和 `artifacts/0.1.153/` 验收记录。
- 实现：对可选的 `mobileSearchInput` 增加存在性守卫；移动端使用侧栏搜索和返回入口，移除顶部分类栏，固定分页区域并让歌曲列表独立滚动，歌词页顶部采用不重叠的三列控件布局。
- 版本与产物：`0.1.153`；`artifacts/0.1.153/fnaudio-0.1.153.fpk`，4,879,159 字节，SHA-256 `A2214FD1A07513634229EAF2A91A685EE60AD56FED25F2BF66CDB6AE62BDB3F0`。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列 Node 回归和移动端布局 Node 回归均通过；FPK manifest、缓存键、内容清单和哈希一致。
- 设备验证：已完成 fnOS 应用中心 `0.1.152 -> 0.1.153` 覆盖升级，状态为 `running`，`/api/health` 正常；移动视口烟雾确认菜单搜索/返回、分类移除、列表滚动容器、分页栏和歌词头部不重叠。
- 未验证：设备音乐库为 0 项，真实长列表手势、分页按钮操作、歌词实际播放状态及“从当前开始播放全部歌曲”全流程；全新安装、停止/启动、卸载、硬件和 DLNA 互操作也未覆盖。

## 2026-08-06：`0.1.152` 移动端布局验收包

- 生成 `artifacts/0.1.152/` 作为移动端布局的中间 FPK，保留其本地测试、结构检查和设备升级记录；当前开发基线随后推进到 `0.1.153`。

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

## 2026-08-08：播放栈对比与服务端远程 Renderer 改造

- 执行者：Codex
- 目标：对比 Volumio/moOde 的播放控制、MPD、USB DAC、DLNA/UPnP、AirPlay 和 Renderer 生命周期，并修复后台续播依赖前端的问题。
- 修改文件：`src/app/server/playback/models.py`、`plugins.py`、`core.py`、`mpd_client.py`、`mpd_output.py`、`services/mpd_service.py`、`services/airplay_service.py`、`dlna/control_point.py`、`dlna/media_server.py`、`server.py`、`src/app/ui/app.js`，以及对应测试和 `docs/PLAYBACK_STACK_COMPARISON.md`。
- 行为变化：MPD idle 状态现在回写统一 PlaybackCore；外部 DLNA Renderer 由服务端监控 transport 并自动推进队列；DLNA 设备能力缓存到发现结果；MPD status 增加 PCM/DSD stream 信息；AirPlay 缺依赖时明确返回不可用。
- DSD 策略：DLNA MediaServer 继续原始 DSF/DFF 直出；MPD 配置默认 `mixer_type none`、`dop no`，优先 native DSD，但 `native_dsd_verified` 保持 `false`，直到真实 USB DAC 验证。
- 验证：Python 新增状态桥、MPD stream、DLNA protocolInfo、AirPlay probe、Renderer URI 回归测试；已通过。完整构建和真机部署待本轮结束后执行。
- 真机部署：已在 `198.51.100.24` 从 0.1.175 升级到 0.1.177，保留 228 首歌曲/5 首 DSD 与现有队列；单一 server、单一 MPD 运行于 18081/56660。
- Renderer 验证：`DESKTOP-EEIDGH9` 的 FLAC push/pause/resume、设备侧 NextURI 和服务端队列回写通过；DSF 最终进入 PLAYING，HTTP 资源保持 `audio/x-dsf`、原始长度和 `DSD ` 文件头。
- 遗留限制：NAS 无 USB DAC，无法验证本地 native DSD；AirPlay 依赖缺失；Android 通知/锁屏仍需手机真机验证。
## 0.1.181 - MPD 崩溃恢复防误进下一曲

- MPD watchdog 恢复期间新增 15 秒 STOPPED 抑制窗口，避免进程崩溃/重启被误判为自然结束而跳到下一曲。
- 保留原队列、当前歌曲和最后位置恢复逻辑，并增加真机异常重启验证记录。

## 0.1.180 - 播放队列一致性修复

- 修复从音乐库直接点击一首不在前端已同步队列中的歌曲时，PlaybackCore 仍保留旧队列、MPD 实际播放旧曲但接口返回新曲的问题。
- `load` 现在会先将缺失的选中歌曲加入权威队列，再交给 MPD 镜像队列；这也让不支持的采样率/格式错误能够准确返回，而不是静默沿用上一首。
- 新增回归测试覆盖该场景。

## 0.1.179 - USB DAC 真机验证与稳定身份持久化

- 在 TEAC UD-301 真机读取 ALSA 实时 `hw_params`：44.1 kHz WAV 输出为 `S16_LE / 44100 Hz`，DFF 输出为 `DSD_U32_BE`，MPD 同时报 `dsd64:2`，确认 Native DSD 未转 PCM。
- 验证 MPD 镜像队列可自然切换到下一首，fnAudio 当前歌曲状态随 MPD 自主推进同步更新。
- 修复自动选择或旧 ALSA 编号迁移后只更新内存、不写回 `config.json` 的问题；稳定 USB DAC ID 与当前运行时 ALSA ID 现在会持久化。
- 移除 MPD 0.23 已弃用的 `buffer_before_play` 配置，保留 `audio_buffer_size` 与 DAC 启动延迟 quirk。
- 参考 Volumio 4 `Systeminfo/fusion` 的 libasound `hw_params` 探测思路，确认 fnAudio 当前 ctypes 探测结果与内核实时输出一致。
- 本地回归：85 项 Python 测试、3 项 Node UI 回归和 JavaScript 语法检查通过。

## 0.1.178 - 播放与 USB DAC 可靠性改造

- 增加 MPD 原生队列镜像、预加载、自然切歌回写和恢复。
- 增加稳定 USB DAC 身份、真实 ALSA `hw_params` 探测和设备级能力报告。
- 增加 Native DSD/DoP 协商，无法验证时阻止 PCM 兜底转码。
- 增加 USB 热插拔恢复、underrun 监控、有限重启、事务化输出切换和音频设备租约。
- 增加 DAC quirk profile 配置与 82 项 Python 测试、前端回归测试。
- 构建 FPK/APK：见 `artifacts/0.1.178/`。
## 2026-08-08：`0.1.185` 播放失败事务修复

- 修复播放中选择 DAC 不支持采样率（例如 384 kHz）时，ALSA busy 探测触发 MPD 停止的问题。
- PCM 不支持采样率优先依据稳定 DAC 描述拒绝，不中断当前歌曲。
- DSD 在无法验证 Native DSD/DoP 时明确拒绝并保持已有播放。
- 播放核心在输出打开失败时回滚当前歌曲、队列、进度和 transport 状态。
- 验证：Python 91 项全部通过。
## 2026-08-08：`0.1.186` MPD 队列恢复闭环

- 修复应用重启后只恢复 fnAudio 逻辑队列、没有恢复 MPD 原生执行队列的问题。
- 恢复 MPD 目标时重新镜像队列、当前歌曲、循环/随机模式和播放位置。
- 已停止的历史会话会先恢复队列再保持停止；播放中的历史会话恢复为播放状态。
- 新增 MPD 会话恢复回归测试。
## 0.1.190

- 新增 AirPlay Receiver supervisor 与 `/api/airplay/control` 控制接口。
- AirPlay 使用音频输出租约，和 MPD/DAC 互斥，异常退出可有限重启。
- 保持 DLNA DSD 源码推送与 USB DAC 热插拔/恢复策略。
## 0.1.194

- 修复 MPD 原生队列与逻辑队列在停止状态下不同步的问题。
- 队列编辑同步 MPD 时支持 `play=false`，不会因编辑队列意外开始播放。
- 增加停止状态队列同步回归测试。
- 真机 TEAC UD-301 实测 DFF Native DSD 播放，MPD 报告 `dsd64:2`；384 kHz PCM 被明确拒绝且不隐式重采样。
# 0.1.203（2026-08-10）

- 新增 MPD 解码错误分类：`source_corrupt`、`seek_error`、`decoder_unavailable`，并通过 `/api/mpd/status` 暴露结构化 `decoder_errors` 字段。
- Python 测试从 113 项增至 115 项，全部通过；Node UI 回归和 Android lint/build 通过。
- 生成 FPK、Debug APK 和 unsigned Release APK；FPK 已通过 fnOS App Center UI 覆盖安装到真实设备。
- 真机确认版本头、健康检查、音乐库、20 首队列、TEAC UD-301 Native DSD 能力和 underrun 状态均保持正常。
- 未将缺少真实硬件证据的小时级播放、息屏、热插拔、外部 Renderer、Android 多机型和正式签名列为完成。

## 0.1.203 真机长测补充（2026-08-10）

- 在 TEAC UD-301 上对原有 20 首队列执行约 5 分 30 秒、12 点采样的真实连续播放。
- 观察到第 1 首自然切换到第 2 首；全部采样保持 `PLAY`、`underrun=0`、`decoder_errors=0`。
- 测试结束恢复原来的第 20 首和 STOP 状态；短暂 ALSA busy 随后自动清除。
- 该结果只扩大跨曲短时证据，不改变小时级、息屏和热插拔目标的未完成状态。

## 0.1.204（2026-08-10）

- 修复 MPD 重启恢复后 idle transport 可能残留 `STOPPED`、而原始 MPD 已经 `PLAY` 的状态同步问题。
- 新增 `normalized_transport()`，恢复完成后主动同步 idle、fault、PlaybackCore 和状态监听器。
- 在真实 TEAC UD-301 上验证了 0.1.203 的 MPD supervisor 自动重启、20 首队列和当前曲目恢复；0.1.204 的同一矩阵待 App Center UI 安装后复验。
- Python 测试 117 项通过；FPK/APK 构建完成；正式签名仍未提供。
## 2026-08-11: 0.1.213 metadata cache and safe tag write

- Current playback now promotes its lyrics job ahead of library-wide metadata work.
- Lyrics, album artwork, and release date are cached independently, then coalesced into one low-priority `tag_write` job per track.
- Tag writes are serialized with a two-second interval and use a temporary file plus atomic replacement. MP3, FLAC, M4A, and MP4 are supported; DSD and CUE tracks are deliberately skipped.
- Embedded lyrics are read before contacting external lyric providers. Missing song artwork continues to use the centered music-note fallback.
- Verification: 138 Python tests, JavaScript syntax validation, and Android bridge regression checks passed. Real media-file writes on fnOS remain to be validated with a disposable music file.
## 2026-08-11: go-music-dl provider live validation

- Ran the actual `go-music-dl` provider registry against live network endpoints, using returned song and album IDs for the dependent lyrics and album-detail calls.
- Registered scope: 12 online providers plus `local`; full JSONL evidence is stored in `artifacts/go-music-dl-provider-smoke-20260811.jsonl`.
- Confirmed complete search-to-lyrics flows for NetEase, QQ, Kugou, Migu, JOOX, and Qianqian. Confirmed complete album flows for NetEase, QQ, Kuwo, Jamendo, JOOX, Qianqian, and Soda.
- Apple is currently blocked by failed dynamic token extraction; Soda song search currently fails because its response can no longer be parsed. These results are not inferred from mocks.
- Added the reproducible source matrix and test contract to `docs/GO_MUSIC_DL_PROVIDER_VALIDATION.md`. No fnAudio runtime code, package version, FPK, or APK was changed by this validation-only task.

## 2026-08-11: metadata provider migration

- Removed Spotify runtime integration: OAuth token exchange, API search, configuration defaults and persistence, metadata status fields, settings controls, client-side save/clear actions, and API handling.
- Removed the Kuwo metadata adapter and all of its active fallback routes.
- Metadata now uses only MusicBrainz plus the live-validated go-music-dl-style adapters: NetEase, QQ, Kugou, Migu, JOOX, and Qianqian. Album and lyric requests search and score a source candidate before accepting its returned identifier.
- Added gzip response support required by Qianqian's current API response. Existing Spotify keys are discarded when legacy configuration is read, then omitted on the next configuration save.
- Verification: 141 Python tests, `node --check app/ui/app.js`, and `node tests/test_ui_android_bridge.js` passed. A live read-only `Hotel California / Eagles` probe confirmed lyric and cover paths for NetEase, QQ, Migu, and JOOX; Kugou cover worked but had no lyric for that returned track; Qianqian search worked but did not produce a scored match for that English sample.

## 2026-08-11: currently playing metadata priority

- Fixed current-track prioritization so it covers lyrics, album metadata/artwork, and the subsequent tag write rather than only lyrics.
- Priority order is now: current lyrics `0`, current album metadata/artwork `1`, current tag write `2`, library lyrics `100`, ordinary tag writes `200`.
- Reconcile no longer demotes an already promoted task. When playback changes, pending work for the former current track is returned to ordinary priority so repeated song changes cannot starve the library queue.
- Verification: 142 Python tests, UI syntax, and Android bridge regression checks passed, including a regression that runs reconcile between prioritization and verifies that the previous track is demoted after switching.

## 2026-08-11: stop and startup playback behavior

- Local browser and Android-WebView stop now also issue the authoritative backend `stop` command after clearing local media, so a paused session cannot be resumed by a later synchronization.
- Session restore mirrors the saved MPD queue with `play=False`, explicitly stops MPD, and persists the resulting stopped state. Startup restores the queue, current position, repeat/shuffle, and output target without starting audio.
- Verification: 142 Python tests, UI syntax, and Android bridge regression checks passed.

## 2026-08-11: 0.1.214 go-music-dl provider expansion

- Ported the metadata provider flow used by go-music-dl's `music-lib`: score a source-side song result against the local title and artist, then use its source identifier for lyrics and cover metadata.
- Added Kuwo album and standard-LRC lookup plus Kugou album artwork/date and LRC lookup. The provider order is local tags, NetEase, QQ, Kuwo, then Kugou for lyrics; Chinese album lookup now includes Kuwo and Kugou fallbacks.
- Cached `references/music-lib` at commit `3c4c32fd2aff2ffb9737856e52a45fd46b7ca12d` as the source-level implementation reference used by go-music-dl.
- Verification: 141 Python tests, JavaScript syntax validation, Android bridge regression checks, and a read-only live Kugou search probe passed. Kuwo currently returned no candidates from this network and safely falls through.

## 2026-08-11: 0.1.215 FPK release

- Released the stop and startup-state fixes together with the current-track metadata prioritization and provider migration work.
- Version identifiers were synchronized across root `VERSION`, FPK manifest, server User-Agent, web cache keys, and Android source release metadata. Android was not built or packaged for this FPK-only release.
- Verification before packaging: 142 Python tests, JavaScript syntax validation, and Android bridge regression checks passed.
- Built `artifacts/0.1.215/fnaudio-0.1.215-fnpack.fpk` with SHA-256 `204C5C78702CD21B3B192BA819428F2391D3502B118E194BBCCCAC1989DA7C79`; outer manifest, packaged server version, and UI cache keys were inspected.

## 2026-08-11: 0.1.216 embedded artwork preservation

- Fixed the ffmpeg mapping used for metadata tag writes. Lyrics-only updates map the full original input instead of `0:a:0`, preserving embedded cover artwork and other non-audio streams.
- When a verified replacement cover exists, only original image streams are removed before the replacement is attached; audio, data, subtitles, and original container metadata are retained.
- Added a regression assertion that a lyrics-only tag write never uses an audio-only stream map. Verification: metadata tests and the full 142-test Python suite passed, with UI syntax and Android bridge regressions also passing.
- Built `artifacts/0.1.216/fnaudio-0.1.216-fnpack.fpk`, SHA-256 `AA54BE69AB6CF6B96D0E354961A1909AB447E6861971F296846555A7185A07BC`; package inspection confirmed the fixed metadata writer is included.
- Ran the same lyrics-only ffmpeg remux on fnOS against a generated, embedded-artwork MP3 in an isolated temporary directory. The output retained `attached_pic=1`; extracted cover SHA-256 matched the original, and title plus new lyrics tags were verified.

## 2026-08-11: active TODO consolidation

- Replaced the accumulated release diary in `TODO.md` with a current-only backlog grouped by data integrity, real-device playback, Android, security, release reliability, scale, and protocol/test work.
- Removed duplicate DAC/DLNA/Android matrix statements, already implemented AirPlay supervisor and remote MediaSession tasks, obsolete 0.1.173/0.1.175/0.1.198 acceptance tasks, and Spotify validation after the provider migration.
- Added the user-impacting tag audit and recovery work as P0. Historical evidence remains in `PROJECT_CONTEXT.md` and `docs/`.

## 2026-08-11: read-only tag integrity audit

- Added `tools/audit_tag_integrity.py`, which correlates persisted scan provenance, current local Tag/cover contents, and completed tag-write jobs without opening the database for write access.
- High-confidence findings recommend snapshot or backup restoration. The tool intentionally has no media write mode; a separately reviewed recovery workflow is required before any backfill.
- Added `docs/TAG_INTEGRITY_AUDIT.md` and two regression tests. Full local validation: 144 Python tests, UI syntax check, and Android bridge regression passed.
- Ran the tool read-only against the current NAS database and 227-track library. It found 200 files without local artwork, but no prior Tag fields now missing and no completed tag-write history; therefore all 200 remain unproven review findings, not recovery candidates. Downloaded reports are stored in `artifacts/tag-audit-0.1.216/`; remote temporary files were removed.
- A follow-up read-only NAS storage search found no usable recovery source: `/vol1` is the only mounted data volume and has no snapshots, recycle directory, mounted backup disk, or older `library.sqlite3`. The retained `fnaudio.backup-codex-20260731-121550` directory contains application source only. No media was changed; recovery is pending a pre-0.1.213 library backup or snapshot.

## 2026-08-11: tag-write visibility and controlled retry

- Metadata status now includes the six most recent `tag_write` jobs. The UI shows the song label, state, and failure reason while keeping absolute media paths on the server.
- Added `POST /api/metadata/retry-tag-writes`. It requeues only jobs with `job_type='tag_write'` and terminal `failed` state; pending work and all other metadata job types are untouched.
- Added regression coverage for isolated retry behavior and path-free status output. Verification: 26 focused metadata-service tests and the frontend syntax check passed.

## 2026-08-11: 0.1.217 FPK release candidate

- Built `artifacts/0.1.217/fnaudio-0.1.217-fnpack.fpk` for the tag-write transparency update.
- SHA-256: `467ECC0D647854973E7E5F4B88A220210BBC4C515B2AEAD19FA3F48055631528`; outer FPK manifest was inspected and declares version `0.1.217`.
- Verification before packaging: 146 Python tests, frontend syntax validation, Android bridge regression. This artifact has not been installed on the NAS yet.

## 2026-08-11: 0.1.219 current-track lyric priority

- Removed the closed-lyrics-view guard that prevented an actively playing song from requesting lyrics.
- `/api/lyrics` now places the active song lyric job at priority `0`. A dedicated worker claims only these high-priority lyric jobs, so normal album/artwork enrichment cannot hold up the playing track. The browser retries a pending lyric response every 900 ms, with a 15-attempt bound, and updates an open lyrics page automatically when content arrives.
- Added `test_ui_lyrics_priority.js` and priority-worker coverage; full validation passed: 147 Python tests, UI syntax check, Android bridge regression, and lyrics-priority UI regression.
- Released and installed `artifacts/0.1.219/fnaudio-0.1.219-fnpack.fpk` through App Center. SHA-256: `6A3FFD0A0FFF166D99338F4E97C1471BD2B143457C65555AF893C53E4DE065BC`; deployed health check reported `fnAudio/0.1.219`.

## 2026-08-11: 0.1.220 repeat-state icons

- Replaced the repeat button's small text badge with three state-specific SVGs: disabled repeat with slash, list repeat, and single-repeat with an integrated `1`.
- Kept the existing state cycle and explicit backend control contract. Updated UI regression coverage to require separate icon markup for each state.
- Built and installed `artifacts/0.1.220/fnaudio-0.1.220-fnpack.fpk`; SHA-256: `78BD12CF9C139ACF02CA837F8C796AB8F47AF2345781DAB70EFAF54DFF56530A`. Browser acceptance verified every icon state and returned the control to off.

## 2026-08-11: P0 DAC queue-run recovery

- Added `tools/real_device_dac_queue_run.sh` for future physical DAC queue runs. It snapshots the active PlaybackCore session instead of restoring a historical hard-coded ID list, then verifies queue/current/repeat/shuffle/transport after cleanup.
- Added `docs/REAL_DEVICE_DAC_QUEUE_RUN.md` and regression coverage. The script requires an operator-provided valid queue and optional DAC target, so it cannot silently test or restore the wrong library.
- Verified POSIX shell syntax with the locally installed Git Bash and ran the script regression tests.
- This improves the evidence collection path only; USB hot-plug, DoP-only DSD, external Renderer, AirPlay and Android P0 requirements remain open until their dedicated hardware tests are performed.
- Device discovery on the current in-LAN test NAS found only browser playback, with no USB DAC or Renderer. It must not be used to close the hardware acceptance items.

## 0.1.254 CUE 封面写回与配置迁移修复（2026-08-14）

- CUE 虚拟曲目现在仅可更新共享音频封面，不再把跳过的写回记录成“已写入”，也不会污染共享文件的虚拟标题或歌词。
- APE/DSF 写回只覆盖实际传入字段，封面补全不会删除既有文字标签。
- 安装与升级回调迁移同卷旧配置中的音乐库与播放设置，保留新实例端口，避免应用扫描 UI 目录导致库和封面均为空。
- 51 项回归测试通过。内网实际 `/cover/` 返回 JPEG 缩略图的证据位于 `artifacts/0.1.254/real-device-cue-cover.json`。

## 0.1.252 封面读取与缓存失效修复（2026-08-14）

- APEv2 `Cover Art (Front)` 已进入本地封面读取链路，写回后的 APE 可由列表 `/cover/` 端点读取。
- CUE 行的封面缓存键与 URL 版本改用真实音频 mtime，Tag 写回会即时淘汰旧的无封面缓存标记。
- WAV 增加 FFmpeg 嵌入封面提取回退；容器不支持图片时保持统一音乐符号回退。
- 50 项封面、元数据与格式回归测试通过；内网隔离副本验证通过。FPK SHA-256：`75E783BEA8BAD9478F0371D0AA75EE4FF6503A1BE0EA7A64CF31CD78603AF531`。

## 0.1.250 Tag 真实设备验收（2026-08-14）

- 在内网 fnOS 使用隔离副本验证 APE、WAV、DSF 的实际 Tag 写回链路。
- 三种格式的标题、艺术家、专辑、歌词均可由 fnAudio 与 ffprobe 读回，且均可解码；DSF 原封面保持字节一致，APE 未管理 Tag 保持。
- 证据：`artifacts/0.1.250/real-device-format-tags.json`。

## 2026-08-11: Android version-code correction

- Fixed Android `versionCode` from `216` to `220` to match `versionName 0.1.220`; this prevents Android's monotonic upgrade gate from rejecting the package as older than an already-installed build.
- `lintDebug` and `assembleDebug` passed. Archived `artifacts/0.1.220/fnaudio-android-0.1.220-debug.apk` with SHA-256 `B25A39297A67F3B78098D800B0FF62038284E5ED43543052893CB7DF8F288A8B`.
- Real installation remains pending because no `adb` executable or attached Android device is present on this workstation.

## 2026-08-11: 0.1.217 App Center acceptance

- Installed `0.1.217` as an App Center overlay update on `198.51.100.24`. The manual UI was required because fnOS treated the Python dependency change as a UI-confirmed operation; existing library path, service port, and metadata setting were retained.
- Server health returned `fnAudio/0.1.217`. The deployed metadata status endpoint exposed `tag_jobs`; the retry endpoint returned successfully with zero candidates.
- Verified the completed real-library write for `艾薇 - 痴心无名氏.flac` read-only with `ffprobe`: embedded artwork (`attached_pic=1`), title, artist, and lyrics are intact. The web metadata settings page also rendered the completed write status.

## 2026-08-12: 0.1.222 continuous offline goals 1-9

- Completed bounded scan/metadata/transcode resources, MPD error taxonomy, source hygiene, playback compatibility-contract extraction, HTTP/auth/Range/media/FFmpeg/FPK/browser automation, inotify change detection, Renderer/Mixer policy, Android per-connection certificate pinning, and private file/path-boundary hardening.
- Linux music-library monitoring now skips the O(n) signature walk while clean, preserves generation changes during a scan, and falls back after overflow or monitor failure. CUE references, audio symlinks and sidecar-cover symlinks cannot escape a configured root.
- upmpdcli is compatibility-probe-only. MPD hardware volume requires an ALSA Playback Volume capability, fixed volume remains bit-perfect, and software volume is explicitly non-bit-perfect.
- Android self-signed HTTPS now performs credential-free TOFU, encrypts the full-DER SHA-256 with the connection profile, and enforces it for authentication, WebSocket, API/media/artwork requests and WebView SSL errors.
- Added `file_permissions.py`: private directories/files use 0700/0600, public UI uses 0755/0644, sensitive writes are atomic, SQLite sidecars are hardened, and Tag replacement restores owner/mode. Lifecycle scripts use umask 077 and uninstall rejects paths outside an explicit fnAudio allowlist.
- Kept the main fnOS process privileged because shared-folder ACL, ALSA/DAC, SSDP and Tag-write group contracts are not yet defined; the required migration evidence remains in `TODO.md` rather than claiming an unsafe privilege drop.
- Rewrote current TODO and recovery context, added dedicated inotify/output/TLS/permission documents, updated architecture and decisions, and added a reproducible source-manifest generator.
- Focused verification during implementation passed 46 permission/path/HTTP tests, four source-hygiene tests and POSIX shell syntax checks. Final unified verification passed 238 Python tests, JavaScript syntax validation, five Node UI regressions and two Chromium E2E scenarios.
- Android verification passed two JVM tests, `lintDebug` and `assembleDebug`; the Debug APK reports `versionCode=222`, `versionName=0.1.222`, `minSdk=23`, and verifies with v1/v2 signatures.
- Final artifacts: `artifacts/0.1.222/fnaudio-0.1.222-fnpack.fpk` SHA-256 `4F9C0A4FBB99959446EE80CBE17354C183822B5095230D2F83DC3E40741CCADF`; `artifacts/0.1.222/fnaudio-android-0.1.222-debug.apk` SHA-256 `415A320369EBE1F171F000BC6482F3CA1C984CB0D943CF882BBEFCA2C05209F5`.

## 2026-08-12: Android emulator automated regression

- Added a reproducible API 35 headless AOSP ATD test entry point at `tools/test_android_emulator.ps1`. `-InstallSdk` installs the Emulator/system image when absent; regular runs create or reuse the isolated AVD and execute `connectedDebugAndroidTest`.
- Added six Android instrumented tests for encrypted multi-profile storage and active selection, login/history rendering, matching and mismatched self-signed TLS pins against an in-process server, Mock fnOS WebSocket authentication followed by WebView loading/double-back navigation, and Media3 remote-mode queue/transport forwarding.
- The tests use only `instrument-*` connection IDs and restore the prior active selection. They do not clear arbitrary saved connection records.
- Emulator execution exposed two production defects: `RemotePlaybackPlayer` advertised `COMMAND_RELEASE` without handling it, and omitted `COMMAND_SEEK_TO_MEDIA_ITEM`. Both are now implemented and covered.
- Fixed `android-client/gradlew.bat` to return Gradle's actual exit code, so automation cannot report a failed Android test task as successful.
- After the test task, the runner installs the just-built Debug APK and verifies its emulator `versionCode` matches Gradle. API 35 emulator verification passed all six tests. The result is not evidence for real fnOS login, WebView against NAS, lock-screen, Bluetooth, USB DAC, background policy or other physical-device behavior; those remain explicit TODO items.

## 0.1.223 (2026-08-12)

- Released the Android emulator automation, Media3 remote-player lifecycle and indexed-seek fixes.
- Synchronized root version, fnOS manifest, Web cache keys and Android `versionCode=223` / `versionName=0.1.223`.
- Full offline release verification passed: 238 Python tests, JavaScript syntax, 5 Node UI regressions, 2 Chromium E2E scenarios, FPK outer/inner inspection, Android JVM tests, `lintDebug`, `assembleDebug`, and 6 API 35 emulator instrumented tests.
- `artifacts/0.1.223/fnaudio-0.1.223-fnpack.fpk` SHA-256: `6CBE385C472EC53099EFDE1CAC412208EF09C47FD028A51E0F12CFCFA13E574B`.
- `artifacts/0.1.223/fnaudio-android-0.1.223-debug.apk` SHA-256: `7CA0EBA584FFC937F939E195979E212F58DEE26AF0E79169C4A3333A72DDE40A`; it is Debug-signed with v1/v2 verification.
- Neither artifact was deployed to fnOS or a physical Android device during this release pass.

## 0.1.225 (2026-08-12)

- Fixed album artwork Tag writes when a track has no explicit `album_artist`: the writer now uses the canonical artist from the album index, matching the metadata-cache key.
- Fixed album artwork completion so every track in the indexed album receives a coalesced Tag-write job.
- Added one-time `tag_write_backfill_version=1` migration for tracks that already have valid cached album artwork. It preserves the cache, runs at the existing two-second Tag-write pace, and does not repeat after completion.
- Fixed installed fnOS runtime version detection by reading `/var/apps/fnaudio/manifest`; the HTTP header now reports `fnAudio/0.1.225` instead of `fnAudio/0.0.0`.
- Full offline verification passed 241 Python tests and all Node UI regressions. The FPK passed outer/inner package validation.
- Installed through fnOS App Center on `198.51.100.24`; App Center and HTTP both report 0.1.225 running.
- Real-library exact probing found 92 missing embedded covers among 99 tracks with matching cached artwork. Direct and background samples reduced that count to 90. The clean MP3 sample preserved all checked tags and permissions, decoded before and after the write, and produced an extracted cover byte-identical to the cached asset.
- FPK: `artifacts/0.1.225/fnaudio-0.1.225-fnpack.fpk`, SHA-256 `0E86B11F41519AD7D17FD49A815031EDDC0784EEA0BB5E58EC45D8C9A136C6AA`.
- Evidence: `docs/REAL_DEVICE_COVER_BACKFILL_0.1.225.md` and `artifacts/0.1.225/real-device/`.
## Unreleased

## 0.1.268 - 2026-08-14

- Fixed notification app return reloading the current fnAudio page. `MainActivity` now recognizes the notification-only action and restores the existing task without calling `recreate()`.
- API 35 Android-emulator regression tests passed. FPK SHA-256: `55991775E3551F032632E1FC2752679B3D437087DF5A306AC514937848556AFE`; Android debug APK SHA-256: `034FDAA0F2AA59C7252D958493F583691B0D2FF569C803D8533956269D327126`.

## 0.1.267 - 2026-08-14

- Tapping an Android remote-playback notification now brings the existing fnAudio activity and WebView session to the foreground instead of leaving the notification without an app destination.
- API 35 Android-emulator verification passed for the notification's `MediaSession` token and app-return `PendingIntent`. FPK SHA-256: `A4698E8615AB9DA67AB8747E287BA17FE549EA800DFE284A510A809C169E9A88`; Android debug APK SHA-256: `958BB2F150F3BE5CF5A29CB8393F59382CCDBC1B728F3486E91651B6015F8F09`.

## 0.1.266 - 2026-08-14

- Fixed Android remote-output media notifications. USB DAC, UPnP and DLNA targets now use a media-style foreground notification bound to the active `MediaSession`, instead of a separate plain foreground notification.
- Remote sessions publish their notification while playing, paused, or awaiting the first renderer status update, restoring notification shade, lock-screen and Bluetooth media controls without local audio decoding.
- Verified on the API 35 Android emulator with both `dac:*` and `upnp:*` targets. FPK SHA-256: `B3C85534A1C36F84FCF4D2D501300D1ED74E8EB4DA45C1E8562AA6B093388DD0`; Android debug APK SHA-256: `26D12A4084590E84F13F2D01C61C54F1DCE3EF80858671D789A39375478F0877`.

## 0.1.260 - 2026-08-14

- Packaging policy changed: all FPK releases are now emitted directly by `fnpack build`; no secondary archive creation or FPK byte rewriting is permitted. The build validator retains structural and gzip checks only.
- `0.1.260` is the first pure-fnpack replacement package. It was verified as a gzip FPK and fast-deployed successfully to `198.51.100.24`. SHA-256: `2303A1490452D0D05F9DBD60FEBF579F7A6BF84BA45E25E39D29BD670155DF69`.

## 0.1.259 - 2026-08-14

- Corrected the `0.1.258` packaging repair: fnOS requires the outer `.fpk` itself to remain gzip-compressed. The release flow now preserves that container while applying POSIX `0755` modes to lifecycle commands, producing a valid FPK for App Center installation.
- `0.1.259` was verified as gzip-compressed with executable `cmd/main`, `install_callback`, and `upgrade_callback`; it was deployed successfully to the authorized LAN host. FPK SHA-256: `7C4C1A7AAEC9065E73F0FF4D96889890EDEEB526602671CAF3DB1065EE081453`.

## 0.1.258 - 2026-08-14

- Fixed the FPK lifecycle-command permissions that caused fnOS App Center to mark fnAudio as abnormal after an update. Windows builds now repack the outer FPK with `cmd/*` at `755`, and the release validator rejects packages whose `cmd/main` is not executable.
- Hardened the LAN fast-deployment path with the same explicit lifecycle-command permission restoration before it swaps application control files.
- Verified on `198.51.100.24`: `cmd/main`, `install_callback`, and `upgrade_callback` are all mode `755`; direct `main status` and `/api/health` succeed after deployment. FPK SHA-256: `989AF478E9AC0EF563E665E94CDB9E7130FF390A578C49BC7C32D396E196B8FE`.

## UI Track Presentation Boundary - 2026-08-14

- Extracted pure track quality, date, column display and row-key rules into `app/ui/track_presentation.js`; `app.js` retains state and DOM orchestration.
- Added a standalone Node regression, release-hash coverage and package assertions for the new asset so same-version browser/WebView updates cannot reuse an older presentation module.
- Full offline verification passed: 284 Python tests, all Node/UI regressions, 3 Playwright E2E tests and native fnpack package inspection. FPK SHA-256: `7E7CC434F1DAB8C15B720D022B72588E9BA4FA4B282AA9961ADC9891A29B4210`.

## External DAC Upgrade Smoke Test - 2026-08-14

- Extended the transactional test-host installer for non-default SSH ports, sudo-backed administration and a caller-selected temporary upload directory.
- Upgraded the authorized external host to the current `0.2.5` FPK and verified a real TEAC UD-301 DAC playback transition to `PLAYING`, then restored its stopped 536-item queue and output target.

## External Native DSD and DAC Controls - 2026-08-14

- Verified DSF and DFF native playback through the TEAC UD-301. MPD reported `dsd64:2`, `dsd=true` and a bit-perfect candidate for both samples.
- Verified real DAC pause, resume, seek and next-track control, with the original queue state restored after the test.

## 0.1.257 - 2026-08-14

- Restored the mobile MP3 transcoding control through the playback "More" menu. The option reflects its current state and applies the same reload behavior as the desktop control.
- Removed the list-cover flash at application startup: library status is now collected before the first list paint instead of causing an immediate second full-list render, and the music fallback remains visible until a thumbnail has loaded successfully.
- Verified with the UI JavaScript regressions, Android bridge regressions, 15 focused Python tests, FPK package validation and an Android Debug build. The FPK was fast-deployed to `198.51.100.24`; the service reports `0.1.257` on port `18083`.
- FPK SHA-256: `9CCAB111846542EAA8D02CDC3A921502D5923603D45FF5C8E790F1950E6A4749`. Android Debug APK SHA-256: `54D7C6CBD1880DCFCD7716286B9347B95F8746540C7DE0750FA5A1E2DD740693`.

## 0.1.256 - 2026-08-14

- Added WAV artwork writeback using RIFF `ID3 ` chunks with ID3v2.3 `APIC` frames. The audio payload is copied chunk-for-chunk rather than remuxed through FFmpeg.
- Added native RIFF-ID3 discovery for WAV metadata and cover extraction, with the existing FFmpeg extractor retained only as a compatibility fallback.
- Added WAV write/read regression coverage. Local verification passed 63 tests, JavaScript syntax validation, and FPK validation.
- Installed and tested on `198.51.100.24`. The `伍佰 - 泪桥.wav` library item renders its embedded cover after writeback. Backup: `/vol1/1000/fnaudio/wav-cover-0.1.256/伍佰 - 泪桥.before-wav-id3.wav`.
- FPK SHA-256: `1FB5DA03223BF334B3DAC2F785C602B47B6BEBF1D0EEB9D4B3C5C595805637B1`.
- Added and tested `tools/install_test_host_fast.ps1` for the authorized LAN test host. It performs a root-owned transactional FPK swap, normal upgrade callback, listener check, and automatic rollback; the first successful run completed in about nine seconds and retained the previous application at `/vol1/1000/fnaudio/fast-deploy-backups/20260814-105922`.

## 0.1.255 - 2026-08-14

- Fixed metadata completion for songs with `album = 未分类`: a successful lyric/tag task no longer masks a missing cover. The metadata service now requests exact per-track artwork from NetEase and QQ and caches it separately from album artwork.
- APE and DSF writes preserve unrelated tags. Cover-only refreshes no longer erase existing lyrics.
- Installed and validated on `198.51.100.24` through fnOS App Center. `周杰伦 - 威廉古堡.ape` returns a 59,960-byte embedded JPEG and a 5,354-byte 160px thumbnail; `艾薇 - 痴心无名氏.dsf` returns an 85,034-byte embedded JPEG and a 7,086-byte 160px thumbnail. Both thumbnail endpoints returned HTTP 200.
- FPK: `artifacts/0.1.255/fnaudio-0.1.255-fnpack.fpk`; SHA-256 `11F1376BB37A8EE8CB1B0EE789CC1109B1C1C0EE9E5D47E30BF18A5B76BA2B1C`.

- Rebuilt the Android login screen against the official fnOS login reference: extracted official FN login artwork, centered brand treatment, large rounded device/account/password fields, history icon, HTTPS control and bare-FN-ID resolver flow.
- Removed Android's per-resource OkHttp interception for authenticated WebView sessions. Album covers now load through WebView's parallel loader and cache instead of waiting behind synchronous proxy requests.
- Removed all fnOS shared-folder authorisation UI and API usage. Music-library roots are now manual entries only.
- Fixed manual library-root saves when fnOS does not expose an application token: CGI-to-local-service requests are explicitly marked as internal loopback calls, while direct network API requests remain authenticated.
- Rebuilt the Android login screen in the official fnOS visual structure: light surface, explicit text/input colors, FN Connect-first entry and manual-address fallback. This removes the theme-dependent white-on-white form rendering that caused the reported blank login area.
- Updated FN Connect handoff to begin with the official `https://fnos.net/<FN ID>/` resolver before following the selected direct or relay route in the same WebView session.
- Added Android FN Connect WebView login. The same WebView session now navigates from the FN Connect/fnOS login page directly to `/cgi/ThirdParty/fnaudio/index.cgi/`.
- Preserved manual host/port/account/password login and existing connection history.
- Added WebView-session profile routing so fnAudio requests retain Cookie authentication instead of requiring an fnOS token.
- Fixed FN Connect settings writes by attaching the authenticated WebView Cookie to native POST requests.
- Stopped intercepting FN Connect image and other GET resources with OkHttp, restoring WebView parallel loading and HTTP caching for album artwork.
# 0.1.226

- 引入官方 Tpps V2 本地隧道 JNI 封装和 Android 隧道管理器。
- FN Connect 不再回退到 `fnid.fnos.net:443` 网页地址；缺少动态中继配置时给出明确错误。
- 继续保留公网地址直连优先路径。

## 0.2.22 - 2026-08-16

- 在 Android 14 虚拟机强制官方飞牛 App 使用 Tpps V2 中继，并通过中继完成 fnOS 登录及 fnAudio 健康接口验证。
- 确认并接入官方签名的 `/api/v1/visit/info` 动态配置接口；敏感 token/visit secret 仅在内存中使用。
- Android 恢复 ARM64 Tpps JNI 与完整 gomobile 运行时，新增动态回环端口、连接状态等待、取消和直连失败后的自动中继回退。
- 历史连接与主界面恢复统一重新解析 FN ID；非 ARM64 和 x86 ARM 转译环境不会加载 Tpps，改为安全回退公网地址。
- 新增中继配置映射/缺字段仪器测试，两项均在 Android 14 模拟器通过。ARM64 真机中继播放验收仍待执行。
## 0.1.233 - 2026-08-13

- 恢复安装向导中的“服务端口”输入，默认值统一为 `53199`。
- 恢复应用中心应用设置中的“当前服务端口”，由 `config_init` 从实际 `config.json` 动态读取，不再固定显示旧端口。
- 保存设置时校验数字范围和端口占用；冲突时明确失败并保留原配置，不再静默改用相邻端口。
- 启动时严格监听已配置端口；端口被占用时停止启动并写入应用日志，用户可在应用设置中修改后重新启动。
- 真机隔离回调验证：当前端口 `54321` 正确显示；空闲端口 `54322` 正确保存；占用端口 `54323` 被拒绝且原配置保持 `54322`。
- FPK：`artifacts/0.1.233/fnaudio-0.1.233-fnpack.fpk`。
## 0.1.234 - 2026-08-13

- 修复 M4A/MP4 元数据写回失败：不再把源文件中的文本或二进制辅助流原样复制进 `ipod` 容器，只映射音频和有效封面流。
- 保持原子替换策略；临时文件写入失败时不会覆盖原歌曲。
- 设置页的端口标签由“播放”更正为“运行”，并更新端口冲突说明。
# 0.1.262（2026-08-14）

- 使用原生 `fnpack` 生成正式 FPK，并完成 fnOS App Center 覆盖升级验收。
- 验证生命周期命令可执行、服务端口与健康接口、配置和音乐库缓存保留。
- 新增 `docs/APPCENTER_LIFECYCLE_0.1.262.md` 和 `artifacts/0.1.262/verification.json`，记录可重复验收与回滚路径。
## 0.2.14 (2026-08-15)

- 修复 Android 重启后只显示上次歌曲、点击播放无效：恢复服务端会话时静默重建 ExoPlayer 队列，播放前再次校验并补建缺失或不一致的原生队列。
- Android 主界面改为加载 APK 内与 FPK 同源的完整 UI 资源，避免启动时闪现 `Not Found` 或因辅助脚本版本混用而中断初始化。
- 增加 fnOS 兼容 CGI 查询路由，并在安装/升级时补齐缺失的 `/var/apps/fnaudio/target` 标准链接。
- 修复 Activity 销毁后延迟媒体状态回调访问已销毁 WebView 导致的崩溃。
- 新增真实 NAS Android 恢复门禁，验证 15 首停止队列恢复、启动不自动播放、点击播放生效及当前歌曲 ID 一致。
- 外网 `0.2.14` 真机的 536 首历史队列也通过 Android API 35 恢复门禁：ExoPlayer 队列与当前歌曲一致，启动不自动播放，点击播放立即生效；验收后原 TEAC 目标、队列、循环、随机和停止状态全部恢复。
- TEAC UD-301 双曲自动下一首、DSF 与 DFF Native DSD 回归通过；PCM 覆盖队列位置 `0,1`，DSF/DFF 均为 `dsd64:2` 且满足 bit-perfect 候选条件，测试音乐库和播放会话均验证恢复。
- 新增 `real_device_dac_fixture_run.sh`、`real_device_native_dsd_run.sh`、`real_nas_android_gate_state.sh` 和仅供模拟器验收使用的 `tcp_relay.py`，消除 JSON 转义、测试目录残留和外网 IPv6 路由限制对自动验收的影响。
# 2026-08-26

- 发布源码卫生检查范围从 `app/server` 扩展至全部打包 Python（`src/app`），现覆盖 CGI 代理并由范围契约锁定；离线门禁通过（422 项 Python 与全部 Node/UI 回归），源码清单 343 项。
- 完成 100,000 条合成曲目的离线 SQLite 基准：三页查询共 0.210 秒、Python 峰值 399,768 字节；FTS5 trigram 搜索 0.012 秒，对照 LIKE 0.229 秒，分页/计数校验正确。该结果仅验证离线数据路径。
- 优化带长度大库的封面预热：队列达到上限后直接用总长度计算 dropped 并停止尾部迭代，避免扫描后继续遍历数万项；新增计数迭代器回归，离线门禁通过（421 项 Python 与全部 Node/UI 回归）。
- 新增 unittest 测试发现契约：离线门禁拒绝顶层 pytest 风格 `test_*` 函数，防止纯策略回归再次被 unittest discover 静默跳过；源码清单 343 项，离线门禁通过（420 项 Python 与全部 Node/UI 回归）。
- 优化大库封面预热去重：队列满后仅统计 dropped，不再为尾部项目计算 key 或增长 `seen`，避免十万级扫描形成额外 O(n) 身份集合；新增回归，离线门禁通过（419 项 Python 与全部 Node/UI 回归）。
- 修复离线门禁覆盖缺口：6 个 pytest 风格顶层纯策略测试此前未被 unittest discover 执行，现全部转换并进入正式门禁；同步修复预热去重 0 上限边界并改为惰性输入迭代，避免大库预热先物化完整集合。离线门禁通过（418 项 Python 与全部 Node/UI 回归），源码清单 342 项。
- 将扫描错误状态抽至 `server/scan_error_policy.py`：仅保留最近 20 条，路径与消息各限制 512 字符，异常非文本值不字符串化；新增回归，源码清单 342 项，离线门禁通过（404 项 Python 与全部 Node/UI 回归）。
- 加固公开 URL 构造输入边界：Host/协议头及地址解析结果只接受受限文本，异常对象安全回退，避免 URL 解析前字符串化或超长 Header 放大资源；新增回归，离线门禁通过（402 项 Python 与全部 Node/UI 回归）。
- 将 IPv4/IPv6 私网主机解析抽至 `server/network_host.py`，转码与公开 URL 共用可注入 resolver 的网络边界规则；新增模块归属回归，源码清单 340 项，离线门禁通过（401 项 Python 与全部 Node/UI 回归）。
- 修正私网主机判定：改用标准 IPv4/IPv6 解析，支持方括号 authority 与端口，公网 IPv6 不再被冒号截断误判；新增回归，源码清单 339 项，离线门禁通过（400 项 Python 与全部 Node/UI 回归）。
- 将公开 CGI 基地址构造抽至 `server/public_url.py`，规范化协议/端口并正确生成 IPv6 方括号 authority；新增 IPv6 与安全回退回归，源码清单 338 项，离线门禁通过（398 项 Python 与全部 Node/UI 回归）。
- 加固 DLNA/HTTP 文件名清理：`safe_filename()` 仅接受文本，异常 Tag 值回退 `track`，避免任意对象字符串化在长度截断前放大内存；新增回归，离线门禁通过（396 项 Python 与全部 Node/UI 回归）。
- 将服务端出站地址探测抽至 `server/network_address.py`，支持无网络注入式回归并覆盖失败回退与 socket 释放；源码清单 336 项，离线门禁通过（395 项 Python 与全部 Node/UI 回归）。
- 将服务启动的端口检测/随机端口分配抽至 `server/port_probe.py`，支持注入 socket 进行离线测试；新增关闭、占用和临时端口回归，源码清单 334 项，离线门禁通过（393 项 Python 与全部 Node/UI 回归）。
- 将 DLNA/HTTP 共用的 safe_filename 规则抽至 `server/media_naming.py`，新增路径字符、长度和空值回归；源码清单 332 项，离线门禁通过。
- 对齐 query cache 支持摘要与实际快照契约：固定投影现在保留 `limit` 容量字段并兼容旧 `capacity` 输入，避免资源上限信息丢失；离线门禁通过。
- 搜索索引支持摘要仅接受受限字符串模式，避免对任意对象字符串化造成诊断输入内存放大；新增回归，离线门禁通过（390 项 Python 与全部 Node/UI 回归）。
- 加固 library 支持摘要：query cache 与搜索索引现在仅输出固定字段，并限制字符串/数值范围；新增回归，避免未知字段或敏感内容进入 health/diagnostics。
- 加固 library health/diagnostics 摘要：封面预热状态仅保留固定压力字段并安全归一化数值，未知字段、路径和媒体条目不会外泄；新增回归，离线门禁通过。
- 将媒体 HTTP Range 解析抽至 `server/media_range.py` 纯模块，server 请求层保持兼容并新增独立回归；源码清单 331 项，离线门禁通过。
- 补强封面预热根级资源观测回归：health/diagnostics 明确断言 `root_limit`/`root_rejected`，多缓存根上限压力保持可见；离线门禁通过（386 项 Python 与全部 Node/UI 回归）。
- 整库封面预热新增缓存根 worker 上限（8 个），闲置根回收、全活跃时拒绝新后台任务并记录 `root_rejected`，防止多配置场景无界增长；离线门禁通过（386 项 Python 与全部 Node/UI 回归）。
- 统一整库封面预热缓存根路径为绝对路径，防止相对/绝对配置产生重复 worker；新增回归，离线门禁通过（385 项 Python 与全部 Node/UI 回归）。
- 封面预热资源治理：整库预热待处理队列新增 5000 项上限，超额任务丢弃并在状态快照中报告 limit/dropped，避免大库扫描造成内存峰值；回归通过。
- 封面预热性能：新增 `prewarm_queue_policy.py`，整库预热按源路径/ID、版本和尺寸稳定去重后再入队，减少重复 FFmpeg 工作；源码清单更新为 330 项，离线门禁通过。
- 可观测性资源优化：大字典脱敏改为有界前缀迭代，避免复制完整映射后再截断；新增回归，完整离线门禁通过。

- 前端并发生命周期：批请求池新增 `cancel()`，取消后阻止尚未启动的批次并以可等待错误结束排队 Promise，同时避免未处理 rejection；默认路径不变，Node 回归通过。
- 前端大库性能：引用曲目补水在启动新一轮请求前取消旧批次，减少快速页面切换时的无效网络/并发占用；原有渲染与错误回收语义保持不变。
- 大库可观测性修正：分页缓存通过键访问发现 TTL 过期时同步递增 `expired` 计数，诊断统计不再漏记；回归通过。

- 核心边界拆分：新增 `src/app/server/library_write.py`，将扫描结果的路径、音乐库根和相对目录归一化从 SQLite 事务中抽出；调用方数据不再被修改，新增 `test_library_write.py` 回归。源码清单更新为 318 项；`tools/test_offline.ps1` 通过（374 项 Python 与全部 Node/UI 回归），未打包、未部署、未进行真实设备验收。
- 核心边界拆分：继续将曲目行、CUE 行和 JSON 持久化准备抽至 `library_write.py`；数据库事务仍由 `library.py` 独占，私有 `_index_root` 不会进入 `item_json`。完整离线门禁通过，未打包、未部署、未进行真实设备验收。
- 前端边界拆分：新增 `ui/library_page_merge.js`，集中处理全量分页结果的有序合并、空页终止和总数截断；新增 Node 回归，源码清单更新为 320 项，完整离线门禁通过。
- 服务端边界拆分：新增 `playback_status_spec.py`，集中处理播放状态请求目标 ID 的参数归一化；播放后端分支未改变，新增 Python 回归，源码清单更新为 322 项，离线门禁通过。
- 可观测性优化：成功 `/api/playback/status` 与 `/api/playback/events` 不再同步写结构化日志，避免前台轮询/SSE 造成日志 I/O 放大；指标聚合和失败记录保持不变，回归已通过。
- 播放核心边界拆分：新增 `playback_cue_position.py`，集中处理 CUE/APE 相对位置、时长裁剪和结束判定；自动下一曲副作用保持在 `server.py`，新增 Python 回归，源码清单更新为 324 项。
- 大库缓存优化：分页查询缓存写入前清理过期条目，避免闲置页占用有限 LRU 容量；新增回归，离线门禁通过（375 项 Python 与全部 Node/UI）。
- 测试稳定性：分页缓存过期场景改用受控单调时钟，不再依赖 sleep，降低 CI/离线回归抖动。
- 发布治理回归：新增源码清单测试，校验 UI 入口声明的本地 CSS/JS 资产存在、无重复且均带 cache-build 占位符；防止新增模块未进入发布暂存/缓存失效链路。
- 大音乐库查询边界拆分：新增 `library_count_policy.py`，集中决定 all/recent/random100/DSD 是否可复用索引摘要计数；搜索/过滤语义保持实时 COUNT，新增回归，源码清单更新为 326 项。
- 前端大库性能：全量分页加载期间暂缓 itemCache LRU 淘汰，合并所有页面后统一执行一次队列保护 trim，降低大列表批量加载的重复遍历开销；离线门禁通过。
- 前端补水性能：收藏/歌单/队列后台批次写入复用延迟淘汰策略，批次结束统一保护当前队列；不改变首批渲染和最终重绘语义，离线门禁通过。
- 发布治理：离线门禁从 index.html 自动发现本地 JavaScript 资产并逐一执行语法检查，新增 UI 模块不会绕过语法验证；回归通过。
- 大库可观测性：分页缓存快照新增 `expired` 计数，区分 TTL 清理和容量逐出；过期清理回归通过，完整离线门禁保持通过。
- 前端大库性能：itemCache 淘汰改为单次 LRU 迭代收集，避免保护队列存在时重复从头扫描；新增大批量保护回归，离线门禁通过。
- 工作树/发布治理：新增离线脚本静态回归，锁定 UI JS 自动发现与语法检查契约，避免后续维护时治理能力退化。
- 前端并发可靠性：批请求池为每个批次预建 deferred Promise，`all()` 会等待排队批次完成，不再因并发槽尚未释放而返回未定义值；新增 Node 回归，离线门禁通过。
- 资源治理：分页缓存对 TTL 与容量配置做有界归一化（0.1–3600 秒、1–4096 项），避免异常配置造成立即失效或无界占用；新增回归，离线门禁通过。
- 核心边界拆分：新增 `scan_reuse_policy.py`，集中处理增量扫描条目的缓存复用判定；扫描副作用和字段条件保持不变，新增 Python 回归，源码清单更新为 328 项。
- 可观测性资源治理：`redact()` 对嵌套结构、集合项和字符串长度实施有界截断，降低异常诊断输入的内存放大风险；新增回归，离线门禁通过。
- 可观测性健壮性：日志写入在打开文件前完成 JSON 序列化；不可序列化字段安全计数并返回，不再创建空日志文件或传播异常。新增回归，离线门禁通过（377 项 Python）。
- 资源治理：结构化日志新增 64 KiB 单条记录上限，超大事件写入有限摘要，避免异常输入放大磁盘占用；新增回归，离线门禁通过。
- 大库可观测性：分页缓存快照读取时清理过期条目，health/diagnostics 的容量数据更准确；新增受控时钟回归，离线门禁通过。

- 大音乐库分页优化：扫描保存时将精确曲目总数写入 `library_meta.track_count`。无过滤全库分页优先读取该摘要，避免每个页码重复执行 `COUNT(*)`；旧索引、搜索、分组和目录查询继续使用实时计数，防止摘要缺失或过滤条件导致错误总数。
- 健康/诊断优化：索引保存时同步写入 `library_meta.dsd_count`，音乐库摘要优先复用 `track_count`/`dsd_count`，旧索引仍安全回退实时 `COUNT(*)`；新增回归确认健康状态热点路径不扫描 `tracks`。
- 前端边界拆分：分页响应缓存的 LRU 操作抽至 `src/app/ui/lru_cache.js`，独立覆盖命中刷新、容量逐出和清空；`test_ui_lru_cache.js` 已纳入离线门禁。
- 本轮门禁更新：源码清单 304 项；`tools/test_offline.ps1` 通过；未打包、未部署、未进行真实设备验收。
- 前端边界拆分：歌曲详情 `itemCache` 的有界容量、LRU 热度和队列保护抽至 `src/app/ui/item_cache.js`，新增 `test_ui_item_cache.js` 并纳入离线门禁；源码清单 306 项，完整门禁 365 项 Python 与全部 Node/UI 回归通过，未打包或部署。
- 修复详情缓存保护时序：批量补水期间不再提前淘汰可能属于当前播放队列的曲目，统一在写入完成后携带保护集合执行 LRU 淘汰。
- 服务端边界拆分：音乐库状态的用户提示判定抽至 `src/app/server/library_status_presentation.py`，新增路径/扫描/空库提示回归；源码清单 308 项，未打包或部署。
- 服务端资源治理：`ConcurrencyGate` 新增有界等待者（FFmpeg 默认 32），满队列立即拒绝；诊断快照区分等待队列拒绝与普通超时，新增并发回归。离线门禁通过，未打包或部署。
- 可观测性修正：高频 `/api/library/items` 补水请求纳入 `library_page` 延迟桶，避免大音乐库详情加载指标被归入 `other`；新增隐私安全分类回归。
- 资源配置补充：新增 `ffmpeg_max_waiters`，允许按 NAS 资源将 FFmpeg 等待队列限制在 0–256（默认 32）；transcode 状态暴露实际上限，旧配置保持兼容。
- 修复可观测性缺口：转码摘要不再丢弃 `waiter_rejected` 和 `waiter_limit`，health/diagnostics 与原始资源状态保持一致；新增摘要、health、diagnostics 回归。
- 观测内存治理：计数器采用固定白名单（HTTP 状态与日志写入错误），未知事件名不再进入快照，防止高基数输入造成无界 Map；新增回归。
- 服务端边界拆分：SQLite 曲目 JSON 解码抽至 `src/app/server/library_rows.py`，避免各查询分支重复实现异常处理；新增 `test_library_rows.py`，源码清单 310 项，未打包或部署。
- 大音乐库查询补充：`recent`、`random100`（无搜索）和 DSD 视图复用索引摘要计数，带搜索/摘要缺失保持实时统计；新增 SQLite trace 回归。
- 前端大列表优化：按 ID 补水新增有界批请求池（每批 100 项、最多 4 并发），保持结果顺序并避免收藏/歌单大列表完全串行等待；新增 `test_ui_batch_request_pool.js`，源码清单 312 项，完整门禁 374 项 Python 与全部 Node/UI 回归通过。
- 前端补水扩展：后台收藏/歌单/队列详情补水复用同一批请求池，最多 4 并发但按批次顺序消费，避免网络等待完全串行；新增 UI 契约断言，未改变真实设备链路。
- 回归加强：批请求池测试现在记录活动请求峰值，确保并发上限实际生效。
- 前端边界拆分：全量分页 offset 规划抽至 `src/app/ui/library_page_plan.js`，新增空页/异常页大小/字符串参数回归；源码清单 314 项，完整离线门禁 374 项 Python 与全部 Node/UI 回归通过。
- 并发审计修正：多选分组全量加载、批量删除位置解析改用最多 4 并发的批请求池，保持输入顺序并消除无界 Promise.all。
- 并发回归补充：UI 测试锁定分组加载与位置解析必须使用 4 并发批请求池；完整门禁 374 项 Python 与全部 Node/UI 回归通过。
- 前端边界拆分：设备排序和失效目标回退规则抽至 `src/app/ui/device_target_presentation.js`，保留 Android bridge 兼容的本地回退实现；源码清单 316 项，完整门禁 374 项 Python 与全部 Node/UI 回归通过。
- 大库全量列表优化：`fetchAllTracksForCurrentView()` 先读取总数，再并发预取剩余分页并按顺序合并，降低“从当前开始播放所有歌曲”的等待时间；不改变播放设备或真实播放链路。
- 新增 SQLite 回归：验证跨页返回的 count 正确，并通过 trace 确认无过滤页不再触发 `COUNT(*) FROM tracks`。
- 离线门禁：`SOURCE_MANIFEST.sha256` 302 项；`tools/test_offline.ps1` 通过（含完整 Python 与 Node/UI 回归）；未打包、未部署、未进行真实设备验收。
# 2026-08-26

- 大音乐库分组封面性能优化：分组列表及专辑详情的图片从浏览器原生 `loading="lazy"` 切换为已有的 4 并发 `cover_load_scheduler`，可见区优先、旧 WebView 无 IntersectionObserver 时仍按游标补位。先绑定本地封面失败后的在线封面回退，再开始 source 调度，避免缓存命中时错过回调；新增 UI 回归。

- 发布治理：`tools/test_offline.ps1` 不再维护易遗漏的 Node 回归硬编码清单，现自动发现 `src/tests/test_*.js` 并逐项执行；静态契约锁定发现逻辑。新增分组封面回归已由正式门禁执行。源码清单 348 项，完整离线门禁通过（430 项 Python 与全部自动发现的 Node/UI 回归）；未打包、未部署、未进行真实设备验收。

- 元数据资源治理可观测性补齐：后台抓取池（1–6）与独立当前歌曲歌词优先 worker 的实际活跃数/总并发上限现在进入 metadata status、`/api/health` 和 support diagnostics；仅优先 worker 存活时服务状态也正确为 running。摘要仅含有限计数，不包含任务键、路径或凭据；新增服务状态与摘要回归。源码清单 347 项，完整离线门禁通过（430 项 Python 与全部 Node/UI 回归）；未打包、未部署、未进行真实设备验收。

- 核心扫描边界继续拆分：新增 `server/cue_parser.py`，将 CUE 的 FILE/TITLE/PERFORMER/TRACK/INDEX 01 文本规则与文件读取解耦；`library.py` 继续负责路径准入、音频探测与项目构造。纯解析器仅接受文本行，按同一源音频计算下一段开始位置；新增多文件 CUE、回退值与非文本输入回归。源码清单 347 项，完整离线门禁通过（429 项 Python 与全部 Node/UI 回归）；未打包、未部署、未进行真实设备验收。

- 核心扫描/元数据边界拆分：新增 `server/id3_parser.py`，集中解析 ID3v2.3/v2.4 文本帧与 APIC 封面；`library.py` 保持 MP3/WAV/DSF 的文件定位与 ID3v1 回退。解析器拒绝不完整的声明帧，避免读取超出已取得的标签字节；新增文本、syncsafe、APIC、损坏帧与非二进制输入回归。源码清单 345 项，完整离线门禁通过（427 项 Python 与全部 Node/UI 回归）；未打包、未部署、未进行真实设备验收。

- 前端封面懒加载生命周期修复：`cover_load_scheduler` 的每次 hydrate 具有独立运行代次，旧 `IntersectionObserver`、排队任务以及旧图片 `load/error` 回调均不能污染新页面的并发计数或继续启动旧封面请求。缺少 `IntersectionObserver` 的旧 WebView 改为 `NodeList` 游标按并发补位，避免把全页图片复制到待加载队列。新增重渲染、旧回调隔离、旧 WebView 补位与停止回归；源码清单 343 项，完整离线门禁通过（422 项 Python 与全部 Node/UI 回归）；未打包、未部署、未进行真实设备验收。

- 整库封面预热状态新增 `accepted/completed/failed` 计数，health/diagnostics 可区分任务吞吐与失败，同时保留 5000 项上限和 dropped 压力指标；离线门禁通过（384 项 Python 与全部 Node/UI 回归）。
- 补强 health/diagnostics 回归：明确断言整库封面预热的 `limit` 与 `dropped` 字段，防止大曲库预热资源上限在摘要链路中回退；离线门禁通过（384 项 Python 与全部 Node/UI 回归）。
# 0.2.33 后续发布恢复状态治理（2026-08-27，未发版）

- `SOURCE_PROVENANCE.json` 新增 `git_provenance_status`：明确标记 `clean`、`dirty`、`commit_only` 或 `unavailable`，使导出源树、Git 信息读取不完整与真实工作树状态在删除构建会话后仍可区分。
- 发布脚本限制并验证该枚举值；不会把 Git 命令错误或本机环境细节写进发布目录。新增静态回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续大队列补水边界拆分（2026-08-27，未发版）

- 长播放队列的 SQLite `IN` 分批读取、缺失项跳过和“按首次请求顺序重组”移至 `server/library_item_hydration.py`；仍使用 120 项批次，避免 SQLite 变量上限，也不依赖数据库返回顺序。
- 单曲按 ID 定位复用同一受限文本 ID 规范，异常对象或超长 ID 不会触发字符串化或连接 SQLite。新增 adapter、规范化和 SQLite 回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续大库扫描写入批处理（2026-08-27，未发版）

- 扫描保存的曲目、封面和 CUE 持久化从逐首 SQLite 调用改为 500 项有界 `executemany` 批次；输入仍按扫描顺序处理，不建立第二个整库行集合。
- 修复稳定曲目 ID 从 CUE 段切换为普通文件时可能残留 `cue_tracks` 记录的问题。新增批处理及 SQLite 一致性回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续 DLNA 发现门禁与观测（2026-08-27，未发版）

- UPnP 发现缓存以锁保护“检查刷新状态 → 创建线程”的完整准入过程，同一时刻至多启动一个后台发现 worker；重叠刷新请求计入跳过统计，发现失败保留旧缓存。
- `/api/health` 与诊断快照增加脱敏的 DLNA 发现 worker、缓存年龄、成功/失败/跳过计数，不公开设备地址、名称或错误文本。新增并发准入、隐私投影和摘要回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续 DLNA 事件队列上限（2026-08-27，未发版）

- DLNA GENA 事件推送在固定 4 worker 外增加 64 项 pending 准入；高频 renderer 状态变化或多个控制端订阅时，超过预算的通知受控丢弃，不再无界塞入 `ThreadPoolExecutor`。
- health、support diagnostics 和 DLNA diagnostics 公开脱敏的订阅/worker/队列/峰值/接受/丢弃计数，不含 callback URL。新增队列上限及摘要隐私回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续隔离发布恢复演练（2026-08-27，未发版）

- 在 Git 忽略的 `artifacts/_scratch/release-governance-20260827-144009/` 实际执行 fnpack 隔离构建；FPK 解包、生命周期文件、payload、SHA256、源清单和 provenance 校验均通过。
- 本次测试构建记录 `git_provenance_status=dirty`，证明未提交工作树仍可由旁路清单精确追溯。未覆盖正式发布目录、未部署、未进行真实设备验收。
# 0.2.33 后续扫描记录构造边界（2026-08-27，未发版）

- 常规音频扫描结果的格式、MIME、DSD 标志、时间戳和元数据版本组装移至 `server/library_scan_presentation.py`，扫描循环保留文件系统与 ffprobe 编排。新增纯函数回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续前端曲库请求合并（2026-08-27，未发版）

- `fetchLibraryResponse()` 新增 in-flight Promise 去重；相同 URL 在响应完成前共享请求，避免大音乐库快速重绘时重复网络与 JSON 解析。刷新请求继续绕过该映射并清理完成响应缓存；新增 UI 静态回归，未打包、未部署、未进行真实设备验收。
# 0.2.33 后续可观测性计数边界（2026-08-27，未发版）

- `Observability.count()` 新增安全计数增量规范化：只接受有限基础数值、非负截断并限制单次最大增量；异常对象不会触发 `__int__`/字符串化，也不会污染 health/diagnostics 计数。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续请求 ID 输入边界（2026-08-27，未发版）

- `request_id()` 仅处理字符串类型的请求头；非字符串、非法字符或超长值统一生成随机安全 ID，避免在请求路径触发任意对象 `__str__`。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续诊断键值边界（2026-08-27，未发版）

- `redact()` 与结构化日志写入对非文本字典键、事件值采用受限占位符，不再调用任意对象的 `__str__`；敏感字段脱敏和记录大小上限保持不变。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续可观测性累计计数上限（2026-08-27，未发版）

- 指标计数器增加累计值上限 10^12；配合单次增量限制，避免长期运行或异常重复调用造成无界计数，同时不影响正常诊断统计。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续资源门禁输入边界（2026-08-27，未发版）

- `ConcurrencyGate` 对资源名称、并发上限、等待队列上限和超时值进行安全规范化；异常对象不再触发 `__int__`、`__float__` 或 `__str__`，并发/超时范围保持有界。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续资源配置数值边界（2026-08-27，未发版）

- `bounded_int()` 现在仅接受有限基础数值，并对配置容器与键执行安全校验；非法值回退默认并继续应用最小/最大范围，避免异常配置阻断服务。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续磁盘保留空间输入边界（2026-08-27，未发版）

- `disk_has_reserve()` 对路径、最小剩余空间和新增文件大小执行有限输入校验；异常对象或非法数值安全返回 `False`，不再在资源检查路径触发任意转换。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续 CUE 记录构造边界（2026-08-27，未发版）

- CUE 扫描曲目的时长计算及稳定记录字段组装移至 `server/cue_item_presentation.py`，保留原有路径校验、文件状态和 ffprobe 编排。新增 CUE 片段与 DSD 标志回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续扫描数值策略边界（2026-08-27，未发版）

- 扫描和排序共用的数值规范化移至 `server/scan_numeric_policy.py`；只接受有限基础数值，布尔值、NaN/无穷和异常对象安全回退。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续 Tag 文本输入边界（2026-08-27，未发版）

- `clean_tag()` 现在只接受字符串并限制最大长度 4096；异常对象安全归零，保留空白/空字符清理语义。新增元数据文本回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续探测标签完整性兼容（2026-08-27，未发版）

- 完整 ffprobe 标签的快速路径对曲目号改用独立安全数值校验，兼容数值型与数字文本输入，同时保持 Tag 文本严格边界，避免重复本地扫描。

# 0.2.33 后续探测键与 CUE 时间输入边界（2026-08-27，未发版）

- 探测标签规范化仅处理字符串键，CUE 时间解析仅处理文本；异常对象不再触发任意字符串转换。新增元数据文本回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 ffprobe 载荷边界（2026-08-27，未发版）

- ffprobe JSON 适配限制为受支持的字典/列表结构，并复用有限数值规范化，畸形对象安全回退，不影响扫描主流程。新增回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 ffprobe 流数量上限（2026-08-27，未发版）

- 探测载荷最多处理前 16 个流，避免异常或超大 JSON 在扫描中造成无界遍历；正常音频首流解析语义保持不变。新增回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 ffprobe 标签数量上限（2026-08-27，未发版）

- format/stream 标签适配增加每组 128 项及 256 字符键长上限，并使用惰性迭代；正常标签优先级和字段结果保持不变。新增回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续统一 Tag 规范化上限（2026-08-27，未发版）

- `normalize_probe_tags()` 增加 256 项/256 字符键长上限，确保直接调用该模块的路径同样受控；正常标签结果和优先级保持不变。新增回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 Tag 载荷类型边界（2026-08-27，未发版）

- `normalize_probe_tags()` 对非字典载荷安全返回空结果，避免损坏探测输入在公共元数据入口触发异常。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续前端 in-flight 请求上限（2026-08-27，未发版）

- 曲库请求去重映射增加 32 项上限；超限请求继续执行但不进入映射，避免大量不同 URL 并发时内存无界增长。新增 UI 静态回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 HTTP 路径长度边界（2026-08-27，未发版）

- HTTP 观测策略对请求路径增加 8192 字符上限，防止超长 URL 在路由分类和日志判定中造成不必要开销；正常路由语义保持不变。新增回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续诊断键长度上限（2026-08-27，未发版）

- 脱敏日志对文本键限制 256 字符并追加截断标记；敏感字段判断使用原始键，避免超长键绕过脱敏。新增回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 CUE 时间字段上限（2026-08-27，未发版）

- CUE 时间解析将小时、分钟、帧分量限制为最多 6 位数字，超长输入安全回退，避免异常文本触发超大整数解析。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续 ffprobe 输出边界（2026-08-27，未发版）

- `read_probe_metadata()` 新增 2 MiB ffprobe stdout 上限；超限时不执行 JSON 解码，改用原生音频信息回退，并补充回归验证。未打包、未部署、未进行真实设备验收。
- 同一回退路径覆盖 ffprobe 异常、超时和畸形 JSON，保留可由原生容器读取的音频属性；新增失败回归。

# 0.2.33 后续前端条目缓存边界（2026-08-27，未发版）

- 前端 `itemCache` 拒绝非有限容量并将最大容量限制为 50,000，避免异常配置造成无界 Map；新增 Infinity/超大容量回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续服务端查询缓存配置边界（2026-08-27，未发版）

- 查询缓存构造参数拒绝 NaN/Infinity 和自定义数值对象，避免初始化时任意 `int/float` 转换；默认值、容量/TTL/权重范围不变。新增回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 ID3v1 解析边界拆分（2026-08-27，未发版）

- ID3v1 字段解码移至 `server/id3_parser.py` 纯模块，保留中文编码回退和安全清理；新增独立回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续前端批请求池边界（2026-08-27，未发版）

- 批请求池限制最多 4,096 个批次和 32 个并发 worker，拒绝 Infinity/NaN 并发配置，并对超大迭代器惰性截断；取消与顺序语义不变。新增回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续封面调度并发边界（2026-08-27，未发版）

- 封面懒加载调度器增加 32 并发硬上限及非有限配置回退，避免异常设置同时触发无界图片请求；新增回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续批请求取消输入边界（2026-08-27，未发版）

- 批请求池取消原因仅允许 Error 或最多 256 字符文本，异常对象安全回退默认错误，不再调用任意 `toString()`。新增回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续通用 LRU 缓存边界（2026-08-27，未发版）

- 前端通用 LRU 条目数和权重拒绝 Infinity/NaN 并限制最大预算，避免异常配置导致无界缓存；新增边界回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续封面调度配置容错（2026-08-27，未发版）

- 封面调度器对 null/非对象配置安全回退，避免异常初始化抛错阻断页面；新增回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续全量分页计划边界（2026-08-27，未发版）

- 全量分页计划拒绝 Infinity/NaN 总数并限制最多生成 8,192 个后续页面 offset，避免异常响应造成无界前端数组；新增回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续分页结果合并边界（2026-08-27，未发版）

- 分页结果合并改为逐项追加并设置 200,000 条上限，避免超大数组展开导致调用栈/内存峰值；新增回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续表格列配置边界（2026-08-27，未发版）

- 表头列配置仅处理字符串且最多 32 列，异常输入安全回退，避免任意对象字符串化和超大表头 DOM；新增回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续分页总数输入边界（2026-08-27，未发版）

- 分页合并对总数只接受基础数字/文本并执行一次有限解析，异常对象安全忽略，避免渲染路径调用任意 `valueOf/toString`。新增回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续表格列宽边界（2026-08-27，未发版）

- 表格列宽配置按有限数值及现有列级上下限裁剪，避免 Infinity/负值生成无效 CSS Grid；新增回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续同步调度配置容错（2026-08-27，未发版）

- UI 状态同步调度器对 null/非对象配置安全回退，保持可见性暂停和固定轮询语义；新增回归。未打包、未部署、未进行真实设备验收。
- 定时器宿主为 null/原始值时回退全局宿主，避免异常注入对象阻断初始化；新增回归。

# 0.2.33 后续播放设备目标边界（2026-08-27，未发版）

- 设备目标展示最多处理 256 项，缺失/异常目标 ID 安全回退本机，避免超大目标集合和任意对象字符串化影响 UI；新增回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续队列定位输入边界（2026-08-27，未发版）

- 队列定位和播放状态页计划仅接受基础数字/文本索引，异常对象安全回退，避免重绘路径触发任意对象转换；新增回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续资源等待指标上限（2026-08-27，未发版）

- ConcurrencyGate 累计等待秒数限制为 10^9，避免长期运行的等待指标无界增长；新增回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续查询缓存键数值边界（2026-08-27，未发版）

- 查询缓存键仅接受有限浮点值，NaN/Infinity 安全转为不可用占位，避免异常请求键进入常驻 LRU；新增回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续队列计划配置容错（2026-08-27，未发版）

- 队列定位计划对 null/非对象输入安全回退默认计划，保持现有分页与滚动行为；新增回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续设备名称输入边界（2026-08-27，未发版）

- 设备目标排序默认名称仅接受文本，异常对象不再隐式字符串化；新增回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 SQLite 行载荷边界（2026-08-27，未发版）

- 曲库行解码限制 `item_json` 为最多 1 MiB UTF-8 且必须是对象，超大或非对象内容安全跳过；新增回归。未打包、未部署、未进行真实设备验收。
- 增加 ASCII 快速长度路径，接近上限时再执行 UTF-8 字节校验；新增多字节边界回归。
- 行解码新增 None/非可迭代/无效行输入回退，避免异常数据库适配器中断列表响应；新增回归。
- 对行字段访问的非标准异常增加单行隔离，确保同页其他曲目仍可解码；新增回归。

# 0.2.33 后续资源极大整数边界（2026-08-27，未发版）

- 资源限制规范化捕获极大整数 `float()` 溢出，避免异常配置穿透并发/超时门禁；新增回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续库计数策略输入边界（2026-08-27，未发版）

- 已保存曲库计数策略仅接受文本输入并规范化视图/空白过滤，异常对象安全回退实时计数；新增回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续查询数值溢出边界（2026-08-27，未发版）

- 分页数值解析捕获超长数字文本的浮点/整数溢出，非法输入回退默认值；新增回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续进程监管配置边界（2026-08-28，未发版）

- `ProcessSupervisor.register()` 现在限制命令列表最多 128 项、单项最多 4096 字符，并对重启次数、窗口、退避及 nice 值做有限范围规范化；异常配置安全回退，不调用任意对象转换。新增 4 项进程监管回归；未打包、未部署、未进行真实设备验收。
- 监控轮询间隔同步限制为 0.01–60 秒，NaN/Infinity、负数和极大值回退为 2 秒；补充轮询配置回归。
# 0.2.33 后续配置整数规范化（2026-08-28，未发版）

- `server/config.py` 用统一 `_bounded_int()` 规范化端口、资源上限、超时和调度参数，拒绝布尔值及任意对象转换，保留基础数字文本兼容并捕获超大整数；新增配置边界回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续配置保存边界（2026-08-28，未发版）

- `save_config()` 不再直接对外部设置字典执行无保护 `int(...)`；端口、资源限制、超时和调度值复用统一边界，非法输入安全回退。新增保存异常值回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续代理端口写入边界（2026-08-28，未发版）

- `save_proxy_port()` 复用统一端口规范化，拒绝布尔/异常对象并对越界值安全回退或裁剪；新增服务端口展示文件回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续封面缓存版本一致性（2026-08-28，未发版）

- 封面缓存对媒体源版本从单独 mtime_ns 改为 mtime_ns+size 组合；快速写入或粗粒度 NAS 时间戳下也会正确失效旧缩略图/缺失标记。定向与完整离线回归通过；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续封面尺寸输入边界（2026-08-28，未发版）

- 封面缓存尺寸规范化改为基础整数/文本安全解析，拒绝布尔和任意对象转换并捕获超大整数；新增尺寸边界回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续封面版本回退边界（2026-08-28，未发版）

- 封面缓存对不可访问媒体的 modified 回退值增加基础类型与长度限制，异常对象归零，避免缓存键构造触发任意转换。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续指纹策略边界拆分（2026-08-28，未发版）

- 新增 server/fingerprint_policy.py，集中承载 fpcalc 超时与时长规范化；指纹编排模块复用策略并保持原有行为。新增纯函数回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续 CUE 数值边界（2026-08-28，未发版）

- CUE 解析内部时间转换增加基础类型、有限值和溢出保护；异常 INDEX 输入安全归零。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续 CUE 数值策略拆分（2026-08-28，未发版）

- 新增 cue_numeric_policy.py 承载 CUE 时间数值有限性与类型边界，cue_parser.py 仅负责编排；新增策略导入回归，行为保持不变。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续 CUE 曲序边界（2026-08-28，未发版）

- CUE TRACK 曲序数字限制为最多 6 位、范围 1–999999，超长或异常输入回退顺序曲号，避免大整数解析异常。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续 CUE 行长度边界（2026-08-28，未发版）

- CUE 解析现在跳过超过 4096 字符的异常单行，防止正则/文本处理资源放大；新增回归，正常解析行为不变。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续 CUE 行数边界（2026-08-28，未发版）

- CUE 解析最多处理 20,000 行，超出部分截断；结合单行长度限制，防止异常 CUE 文件放大扫描 CPU/内存。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续 Tag 曲序边界（2026-08-28，未发版）

- metadata_text 的 parse_track_number() 限制数字串最多 6 位、范围 1–999999，超长或异常 Tag 安全回退为空曲序；新增回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续资源默认值边界（2026-08-28，未发版）

- bounded_int 对非法默认值回退到范围下界，同时保持磁盘保留空间的负值拒绝哨兵不变，避免资源限制与磁盘检查语义互相影响。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续发布文档版本一致性（2026-08-28，未发版）

- 修正文档中的过期当前版本/配套服务端版本描述，统一指向 0.2.33，并将旧版本记录标注为历史追溯；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续 CUE 输入迭代边界（2026-08-28，未发版）

- CUE 解析对非可迭代 lines 输入安全回退为空集合，并保留行数/单行长度上限；新增回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续文件名文本边界（2026-08-28，未发版）

- artist_title_from_filename/display_name 现在仅接受字符串并限制 basename 为 4096 字符，异常路径安全回退；新增回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续发布版本文档门禁（2026-08-28，未发版）

- `test_release_version` 新增根 README 与 Android README 版本基线校验，确保文档和运行时发布面一致。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续延迟聚合上限（2026-08-28，未发版）

- Observability HTTP 延迟桶对单次 elapsed_ms、最大值、请求计数和累计毫秒数增加统一硬上限，并保护默认阈值输入；长期运行不会因极端单次请求或指标累计导致无界增长。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续内存曲库查询边界拆分（2026-08-28，未发版）

- 新增 `library_memory_query.py`，统一承载旧索引/测试回退路径的文本投影、过滤、搜索匹配、根路径匹配和排序键；`library.py` 不再重复过滤/排序，异常对象不再隐式字符串化，文本长度受限。新增纯模块回归；未打包、未部署、未进行真实设备验收。
- 曲库搜索条件、FTS 启用判定、分组匹配及元数据计数键改为拒绝异常对象隐式字符串化，非法输入安全回退或明确拒绝；新增 SQLite 回归。
- 内存曲目按 ID 查找和文件位置解析改为仅接受文本 ID/路径，异常字段安全回退，避免回退路径触发任意 `str()`；新增 SQLite 回归。
- 可观测性 `finite_nonnegative` 与计数增量规范化捕获超大整数浮点溢出，异常指标值不再穿透诊断路径；新增回归。
- 内存曲库搜索纯模块限制直接调用的搜索词长度并拒绝非文本值，防止绕过上层规范造成字符串扫描放大；新增回归。
- 新增 `library_search_policy.py` 承载 FTS/LIKE 搜索条件构造，`library.py` 仅保留兼容转发入口；新增纯策略回归。
- SQL 搜索纯策略增加 4096 字符输入上限，覆盖绕过上层规范的直接调用并保持 LIKE/FTS 兼容；新增边界回归。
- SQL 搜索纯策略对 alias/rowid 标识增加 128 字符上限，避免异常直接调用构造超长 SQL；新增回归。
- SQL 搜索纯策略对 alias/rowid 标识增加安全字符校验，注入式标识回退默认值；新增回归。
- 扫描超时/取消/异常状态改用 `scan_error_text()` 有界投影，避免直接 `str(exc)` 污染全局状态；新增错误文本回归。
- 扫描超时/取消/异常日志改用同一受限文本投影，避免日志格式化绕过状态边界。
- 文件位置解析对损坏或非字典缓存条目安全回退，避免文件管理跳转触发属性访问异常。
- `summary_values.nonnegative_int()` 对超长数字文本的整数转换异常安全回退，避免 health/diagnostics 请求抛错；新增回归。
- diagnostics 对顶层及嵌套状态统一使用字典投影，损坏依赖载荷安全降级为空摘要；新增回归。
- `summary_values.nonnegative_int()` 现在安全规范化 default/maximum，异常参数不再导致摘要返回不可序列化值或比较异常。
- 公开摘要整数回退值现在同样按 maximum 裁剪，避免异常输入通过超大 default 绕过上限；新增回归。
- `summary_values.bounded_text()` 对 maximum 长度参数增加安全规范化，异常配置不会破坏摘要请求。
- `summary_values.bounded_text()` 对非文本 default 安全归零，避免摘要回退值携带不可序列化对象。
- `summary_values.bounded_text()` 对 default 回退文本同样执行 maximum 裁剪，避免异常路径绕过长度边界；新增回归。
- 发布脚本在构建完成后将最终 FPK SHA-256 回写 provenance，并与校验文件交叉验证；新增发布脚本门禁。
- 发布脚本现在回读 SHA256SUMS 并核对最终 FPK 摘要与文件名，写入异常会立即失败。
- 新增 `library_group_policy.py` 承载分组条件构造，保留空值/空串“未分类”语义；`library.py` 保留兼容入口并新增纯策略回归。
# 0.2.33 后续查询缓存异常数值边界（2026-08-28，未发版）

- `LibraryQueryCache` 对极大整数配置的 `float()` 溢出安全回退，避免 TTL、条目容量或权重初始化因异常输入抛错；新增构造边界回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续前端 LRU 异常数值边界（2026-08-28，未发版）

- `ui/lru_cache.js` 增加安全有限数值转换，`Symbol` 或异常 `valueOf()` 不再让缓存初始化/权重计算抛错；容量、权重上限和 LRU 语义保持不变。新增 Node 回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续 HTTP 慢请求计数边界（2026-08-28，未发版）

- `Observability.record_http_latency()` 对 `slow` 累计计数增加 `MAX_COUNTER_VALUE` 封顶，保持与请求总数一致的资源边界；新增回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续前端响应权重边界拆分（2026-08-28，未发版）

- 新增 `ui/library_response_policy.js` 承担分页响应缓存权重计算，主页面保留兼容入口；新增 Node 回归，缓存上限和页面行为保持不变。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续分页请求键容错（2026-08-28，未发版）

- libraryLoadRequestKey 捕获异常状态导致的 JSON 序列化错误；失败时回退为空键，仅禁用本次去重而不阻断分页请求。新增静态回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续分页页码输入边界（2026-08-28，未发版）

- 分页请求键生成保护页码数值转换，Symbol、异常对象或非有限页码安全回退为第 1 页；新增静态回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续资源等待指标溢出边界（2026-08-28，未发版）

- ConcurrencyGate._add_wait_seconds() 对极大整数浮点转换增加安全捕获，避免异常指标输入破坏资源门禁；新增回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续前端搜索输入上限（2026-08-28，未发版）

- currentQueryText 对搜索框值执行文本类型检查和 4096 字符裁剪，避免超长搜索在请求、缓存和本地过滤路径放大；新增静态回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续进程错误文本边界（2026-08-28，未发版）

- 新增 process_error_policy.py，进程启动失败和重启回调错误统一限制为 512 字符文本，避免异常状态污染诊断；新增独立回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续曲库分页偏移边界（2026-08-28，未发版）

- library_query_spec.py 为歌曲、分组和文件夹分页增加 10 亿 offset 上限，保持正常分页语义并隔离极端请求；新增回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续进程历史错误状态边界（2026-08-28，未发版）

- 进程监管对注册时继承及状态返回的 `last_error` 统一执行受限文本投影，防止旧状态污染诊断；新增回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续曲库查询配置边界（2026-08-28，未发版）

- library_query_spec.py 对分页默认值、最大值和 ID 数量上限增加安全整数规范化，异常对象安全回退并保持正常查询语义；新增回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续查询参数映射容错（2026-08-28，未发版）

- \`library_query_spec.first_param()\` 对 \`.get()\` 读取进行可调用检查和异常隔离；损坏的查询参数映射会安全回退默认值，不再阻断曲库分页、分组或文件夹请求。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续查询缓存迭代器容错（2026-08-28，未发版）

- LibraryQueryCache._values 对缓存键的 iter/next 异常进行隔离，并保持最多 32 个键值的有界读取；异常迭代器不会阻断曲库请求。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续查询缓存结果复制容错（2026-08-28，未发版）

- LibraryQueryCache 对缓存结果深拷贝异常安全降级：不可复制结果不进入缓存，损坏缓存命中会被移除并按未命中返回；新增 `uncacheable` 诊断计数与回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续查询缓存权重容错（2026-08-28，未发版）

- `LibraryQueryCache._result_weight()` 隔离异常字典访问和长度读取，损坏结果按最小权重处理，避免缓存计量异常影响曲库请求。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续并发门禁计数上限（2026-08-28，未发版）

- `ConcurrencyGate` 对 acquired、waited、rejected、waiter_rejected 和 timed_out 累计计数增加统一上限，长期运行不会造成诊断整数无界增长。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续日志轮转阈值边界（2026-08-28，未发版）

- 可观测性日志写入统一规范化 `max_bytes`（1–100 MiB），异常/非有限输入回退到 5 MiB，避免错误配置造成频繁轮转或日志文件无界膨胀；新增回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续移动分页策略边界拆分（2026-08-28，未发版）

- 将移动端分页控件的滚动可见性和自动定位策略抽至 `library_pager_visibility.js`，`app.js` 保留兼容调用层；新增独立 Node 回归，降低前端核心渲染模块耦合。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续分组渲染去重（2026-08-28，未发版）

- 大曲库分组视图的空状态判断复用当前渲染列表，不再重复调用 `groupedTracks()`，降低分组页面重绘开销。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续发布证据路径边界（2026-08-28，未发版）

- `verify_release_evidence.ps1` 现在明确要求输入路径为目录，普通文件路径会被拒绝并返回清晰错误，避免恢复核验误读证据位置。新增静态回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续批请求池并发参数容错（2026-08-28，未发版）

- 批请求池对并发度增加安全归一化，隔离 `Symbol`、异常对象和非有限数值，并限制为 1–32，避免分页/封面批处理初始化被异常输入中断。新增 Node 回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续分页展示边界拆分（2026-08-28，未发版）

- 将分页 HTML 生成抽至 `library_pager_presentation.js`，`app.js` 只负责状态计算和调用，新增独立 Node 回归，降低核心渲染耦合。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续封面调度并发参数容错（2026-08-28，未发版）

- 封面预热调度器对 `maxConcurrent` 增加安全归一化，异常对象和 `Symbol` 回退默认值，并限制并发为 1–32，避免预热初始化中断。新增 Node 回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续持久化分页大小边界（2026-08-28，未发版）

- 本地保存的分页大小现在统一限制为 1–500 的整数，避免历史异常配置放大大曲库请求和前端渲染。新增静态回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续分页展示输入容错（2026-08-28，未发版）

- `library_pager_presentation.js` 对总数、页码和页数的数值转换增加异常隔离，`Symbol` 或异常对象不会阻断分页 HTML 生成。新增 Node 回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续分页展示规模上限（2026-08-28，未发版）

- 分页展示总数限制为 100,000,000、页数限制为 1,000,000，避免异常状态生成超大 DOM 属性和文本。新增 Node 回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续内存曲库物化边界（2026-08-28，未发版）

- 内存回退查询在物化曲目集合时即应用 200,000 项上限，避免先无界构造列表再进入筛选排序。新增回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续音乐库根路径输入边界（2026-08-28，未发版）

- 音乐库路径规范化与合并统一限制最多 64 个根路径，避免异常配置在扫描/设置流程中造成无界列表物化。新增回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续根路径截断正确性（2026-08-28，未发版）

- 根路径规范化现在先跳过空项和重复项，再应用 64 个有效根目录上限，避免原始配置截断导致后续有效路径被漏掉。新增回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续根路径文本输入容错（2026-08-28，未发版）

- 音乐库路径规范化与合并不再对任意对象执行 `str()`；异常配置项会被安全跳过，避免设置/扫描流程被损坏输入阻断。新增回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续根路径配置写入边界（2026-08-28，未发版）

- `apply_library_paths()` 现在同样限制最多 64 个文本路径并过滤异常项，避免配置写入阶段对无界迭代器进行物化。新增回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续根路径配置类型容错（2026-08-28，未发版）

- `normalize_library_paths()` 对非字典配置安全回退当前目录，避免损坏配置在设置或扫描流程中触发 `.get()` 异常。新增回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续根路径写入配置类型容错（2026-08-28，未发版）

- `apply_library_paths()` 对非字典目标安全短路，避免异常配置状态在保存设置时触发赋值异常。新增回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续根路径文本长度边界（2026-08-28，未发版）

- 音乐库单路径文本限制为 4096 字符，超长配置项会被安全跳过，避免规范化和索引键出现资源放大。新增回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续根路径回退边界（2026-08-28，未发版）

- `library_path` 的默认回退现在也经过同一长度/类型校验，避免在 `library_paths` 全部无效时绕过 4096 字符限制。新增回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续曲目缓存容量参数容错（2026-08-28，未发版）

- 曲目缓存容量配置增加异常隔离与 1000–50000 边界，`Symbol` 或异常对象回退安全默认值，避免异常配置造成缓存失控。新增 Node 回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续通用 LRU 容量整数边界（2026-08-28，未发版）

- 通用 LRU 缓存现在拒绝布尔容量并将条目数/权重规范化为有限整数，避免小数配置造成隐性超额驻留。新增 Node 回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续播放队列定位扫描边界（2026-08-28，未发版）

- 播放队列定位最多扫描 50,000 项，页大小规范化为 1–500 整数，避免异常队列输入造成前端计算放大。新增 Node 回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续发布资源版本门禁（2026-08-28，未发版）

- 版本一致性回归现在显式校验分页可见性和分页展示脚本均带构建缓存键并由 `index.html` 加载，避免发布时漏加载新增模块。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续曲库查询缓存命中率（2026-08-29，未发版）

- `LibraryQueryCache.snapshot()` 新增稳定的 `hit_rate` 指标（0–1），用于离线和健康诊断判断大曲库查询缓存收益；新增空缓存及命中/未命中回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续健康摘要缓存命中率投影（2026-08-29，未发版）

- `library_snapshot` 将曲库缓存 `hit_rate` 安全投影到健康摘要，限制在 0–1 且拒绝任意对象转换；新增健康摘要回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续曲库缓存适配输入边界（2026-08-29，未发版）

- `library.py` 的缓存 wrapper 不再提前字符串化 namespace 或物化任意 values 迭代器，避免绕过底层缓存的有界 key 规范化；新增独立回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续 TODO 治理去重（2026-08-29，未发版）

- 清理 TODO 中重复的并发门禁计数上限条目，保留单一完成记录，降低持续目标恢复时的重复工作风险；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续 TODO 唯一性回归（2026-08-29，未发版）

- `test_source_hygiene.py` 新增 TODO checklist 唯一性门禁，防止后续自动推进再次产生重复条目；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续元数据探测策略拆分（2026-08-29，未发版）

- 新增 `metadata_probe_policy.py`，将探测标签完整性判断和本地 fallback 合并从 `library.py` 拆出，并新增独立回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续前端封面状态接线（2026-08-29，未发版）

- `app.js` 保存最近一次封面调度状态到 `state.coverLoadStatus`，后续可直接读取前端队列压力；不改变页面渲染或播放行为；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续元数据映射异常隔离（2026-08-29，未发版）

- `merge_missing_tags()` 将 probe/fallback 字典复制纳入异常隔离，损坏映射安全回退而不阻断扫描；新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续 Vorbis 注释策略拆分（2026-08-29，未发版）

- 新增 `vorbis_comment_policy.py`，将 Vorbis 注释解析从 `library.py` 拆出，并将受支持标签匹配限制为 128 条；新增独立回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续发布证据严格模式（2026-08-29，未发版）

- `verify_release_evidence.ps1` 增加 `-RequireCompleteEvidence`，可在恢复或发布场景强制要求 staged source manifest 与 provenance；新增脚本回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续前端分页数值文本边界（2026-08-29，未发版）

- `library_page_plan.js` 与 `library_page_merge.js` 拒绝超过 64 字符的数字文本，避免异常输入进入 `Number()` 造成不必要的渲染线程开销；新增 Node 回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续封面调度队列上限（2026-08-29，未发版）

- `cover_load_scheduler.js` 增加 4096 项待处理队列上限及 `dropped` 计数，避免大曲库可见性事件导致前端队列无界增长；新增 Node 回归；未打包、未部署、未进行真实设备验收。
- `hydrate()` 返回值补齐 `dropped` 字段，与 `snapshot()` 保持一致；新增 Node 回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续封面限流重试语义（2026-08-29，未发版）

- 队列满时被拒绝的封面项不再立即取消观察，只有成功入队才 unobserve，后续可见事件能够自然重试；新增 Node 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续健康摘要依赖映射容错（2026-08-29，未发版）

- `health_snapshot.py` 对 MPD、元数据状态缓存和转码摘要先投影为已知字段的普通字典，隔离损坏字典子类的 `.get()` 异常，避免 `/api/health` 被异常依赖状态阻断；新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续诊断快照映射容错（2026-08-29，未发版）

- `diagnostics.py` 对播放、MPD 和元数据嵌套状态统一采用安全字段读取，损坏字典子类不会阻断支持快照；新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续曲库错误摘要序列容错（2026-08-29，未发版）

- `library_snapshot.py` 对扫描错误序列使用安全长度投影并隔离异常 `__len__`，避免健康/诊断摘要在损坏状态下抛错；新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续诊断播放摘要边界拆分（2026-08-29，未发版）

- 新增纯模块 `diagnostics_playback.py`，承载支持快照的播放目标、传输状态、队列长度和当前曲目存在性投影；`diagnostics.py` 仅负责组合，新增独立回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续可观测性快照边界拆分（2026-08-29，未发版）

- 新增纯模块 `observability_snapshot.py`，统一承载计数与 HTTP 延迟桶的有界、可序列化投影；`Observability.snapshot()` 仅在锁内读取并委托策略，新增独立回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续前端引用曲目补水上限（2026-08-29，未发版）

- 新增 `ui/item_hydration_policy.js`，统一限制收藏/歌单引用补水最多 2048 个有效字符串 ID，并按 100 条分批；两个补水入口复用该策略，避免大曲库状态造成无界数组和请求批次；新增 Node 回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续补水批次请求预算（2026-08-29，未发版）

- 引用曲目补水批次增加 8192 字符预算，在数量上限之外约束单批 URL 载荷；超长 ID 会提前拆批，新增 Node 回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续发布证据离线核验（2026-08-29，未发版）

- 新增 `tools/verify_release_evidence.ps1`，可只读核对 FPK、SHA256SUMS、SOURCE_MANIFEST 与 SOURCE_PROVENANCE；历史 `0.2.33` 包已验证校验和正确，并明确报告缺少后续才引入的 staged-source provenance，避免删除会话后错误判断其可复现性；新增脚本回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续编码后补水预算（2026-08-29，未发版）

- `item_hydration_policy.js` 按 `encodeURIComponent` 后长度计算批次预算，覆盖多字节 ID 的 URL 膨胀；新增 Unicode ID 回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续诊断元数据摘要边界拆分（2026-08-29，未发版）

- 新增纯模块 `diagnostics_metadata.py`，承载元数据 worker、队列和状态缓存压力投影；`diagnostics.py` 仅负责组合，新增独立回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续健康子摘要容错（2026-08-29，未发版）

- `library_snapshot.py`、`transcode_snapshot.py` 与 `dlna_snapshot.py` 对诊断依赖映射统一采用安全字段读取，损坏字典子类不会阻断健康摘要；新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续结构化日志异常隔离（2026-08-28，未发版）

- `Observability.write()` 现在隔离脱敏与 JSON 序列化阶段的普通异常，损坏映射安全记为 `log_write_errors`，不会反向失败业务请求。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续脱敏映射直接容错（2026-08-28，未发版）

- `redact()` 对损坏字典的 `items()` 和 `len()` 访问进行有界异常隔离，直接调用时返回安全占位摘要；新增回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续脱敏序列直接容错（2026-08-28，未发版）

- `redact()` 对列表/元组的迭代和长度读取进行有界异常隔离，损坏序列返回 `[UNAVAILABLE_SEQUENCE]` 占位摘要；新增回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续封面缓存曲目输入容错（2026-08-28，未发版）

- `cached_cover_for_item()` 对非字典曲目和非文本路径安全回退为空封面，避免缓存键构造触发异常字符串化并阻断封面请求。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续封面缓存 LRU（2026-08-28，未发版）

- 封面内存缓存命中会更新访问顺序，写入会替换旧键并按 LRU 淘汰，热点封面可稳定驻留，降低重复解析开销。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续内存曲库遍历上限（2026-08-28，未发版）

- `library_memory_query.filter_sort_memory_items()` 对内存曲目遍历增加 200,000 条上限，并隔离迭代器异常，避免异常缓存或无界输入造成排序/渲染资源放大。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续内存曲库字段容错（2026-08-28，未发版）

- 内存曲库过滤、搜索和排序统一使用安全字段读取，字典子类 `.get()` 异常会回退为空值，不阻断大曲库渲染。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续内存曲库根目录容错（2026-08-28，未发版）

- `memory_item_root()` 对根目录集合增加 64 项有界遍历并隔离迭代/路径匹配异常，避免损坏配置阻断文件夹视图。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续分页合并总数容错（2026-08-28，未发版）

- `library_page_merge.js` 对总数输入执行安全数值转换，Symbol 或异常 `valueOf()` 会被忽略，不再阻断大曲库分页合并。新增 Node 回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续分页计划数值容错（2026-08-28，未发版）

- `library_page_plan.js` 对分页总数、页大小和首批数量执行安全数值转换，Symbol 或异常 `valueOf()` 不会阻断剩余页计划生成。新增 Node 回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续分页页大小边界（2026-08-28，未发版）

- `library_page_plan.js` 将页大小限制为 1–500 的整数，防止小数/超大值导致无效分页偏移或额外请求调度。新增 Node 回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续封面缓存字段边界（2026-08-28，未发版）

- `cached_cover_for_item()` 隔离曲目字典字段访问异常，并将缓存路径键限制为 4096 字符，避免损坏输入或超长路径影响封面请求。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续并发门禁计数上限（2026-08-28，未发版）

- `ConcurrencyGate` 对 acquired、waited、rejected、waiter_rejected 和 timed_out 累计计数增加统一上限，长期运行不会造成诊断整数无界增长。新增回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续多根扫描结果边界拆分（2026-08-28，未发版）

- 将多根曲库扫描完成后的 ID 去重、艺术家/专辑/曲名稳定排序及聚合签名计算抽至 `server/library_scan_results.py`；`library.py` 继续负责文件系统扫描和元数据探测编排，行为与 API 不变。
- 新增纯模块回归，覆盖重复 ID、异常扫描项和异常签名输入；离线门禁共 592 项 Python 测试及全部 Node UI 回归通过。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续多根扫描旧索引分区（2026-08-28，未发版）

- 多根曲库扫描新增旧索引按根目录分区策略，避免每个根重复遍历完整历史曲目；异常/非文本路径会被隔离，扫描结果和复用语义保持不变。
- 新增纯模块回归；离线门禁共 593 项 Python 测试及全部 Node UI 回归通过。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续扫描结果异常隔离（2026-08-28，未发版）

- 扫描结果聚合策略拒绝不可哈希损坏 ID，安全处理异常 items/signatures 迭代器，并隔离路径分区回调异常，避免畸形缓存中断多根扫描收尾。
- 新增纯模块回归；离线门禁共 594 项 Python 测试及全部 Node UI 回归通过。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续文件定位路径边界（2026-08-28，未发版）

- `is_library_item_path()` 现在拒绝非文本及超过 4096 字符的路径，避免异常对象隐式字符串化和超长路径进入 `realpath`；正常文件管理定位与根目录隔离语义保持不变。
- 新增 SQLite 回归；离线门禁共 595 项 Python 测试及全部 Node UI 回归通过。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续写入前路径边界（2026-08-28，未发版）

- `normalize_scan_items()` 现在只接受受限文本路径，拒绝非文本或超过 4096 字符的 `path`/`cue_path`；无根路径的旧 `folder` 值也不再隐式字符串化，避免损坏扫描记录阻断 SQLite 写入。
- 新增纯模块回归；离线门禁共 596 项 Python 测试及全部 Node UI 回归通过。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续写入记录异常隔离（2026-08-28，未发版）

- `normalize_scan_items()` 现在对异常 items 迭代器和不可转换映射逐项跳过，避免坏缓存记录中断整批索引持久化；既有路径边界和写入字段语义保持不变。
- 新增纯模块回归；离线门禁共 597 项 Python 测试及全部 Node UI 回归通过。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续持久化准备路径边界（2026-08-28，未发版）

- `prepare_track_persistence()` 现在复用统一的 4096 字符文本路径投影，非文本或超长 `path` 不会进入 SQLite 行；独立调用与完整扫描写入链路边界一致。
- 新增纯模块回归；离线门禁共 598 项 Python 测试及全部 Node UI 回归通过。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续索引根写入边界（2026-08-28，未发版）

- `prepare_track_persistence()` 现在对私有 `_index_root` 及 CUE 路径复用统一的 4096 字符文本投影，避免独立调用通过异常对象或超长值绕过路径边界；正常索引写入语义保持不变。
- 新增纯模块回归；离线门禁共 599 项 Python 测试及全部 Node UI 回归通过。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续批量写入异常隔离（2026-08-28，未发版）

- `iter_track_persistence_batches()` 现在隔离单条 `prepare()` 异常，跳过损坏记录并继续生成后续有界批次，避免单条坏缓存中断整库索引写入。
- 新增纯模块回归；离线门禁共 600 项 Python 测试及全部 Node UI 回归通过。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续前端补水缓存短路（2026-08-28，未发版）

- `resolveTracksByIds()` 在所有曲目已命中 `itemCache` 时直接按请求顺序返回，避免创建空批请求池和无意义调度；缺失曲目的批量补水语义保持不变。
- 新增静态回归；离线门禁共 600 项 Python 测试及全部 Node UI 回归通过。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续前端查询参数边界拆分（2026-08-28，未发版）

- 将 `app.js` 中曲库分页、搜索、分组和目录查询参数组装抽至 `ui/library_query_params.js`，统一处理搜索长度及异常数值输入；现有请求语义和视图条件保持不变。
- 新增 Node 纯模块回归；离线门禁共 600 项 Python 测试及全部 Node UI 回归通过。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续查询参数数值容错（2026-08-28，未发版）

- `library_query_params.js` 对 `page`/`pageSize` 统一使用安全有限数值投影，隔离 `Symbol`、异常 `valueOf()`、NaN 和无穷值，保证大曲库分页请求持续可渲染。
- 新增 Node 回归；离线门禁共 600 项 Python 测试及全部 Node UI 回归通过。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续批处理输入容错（2026-08-28，未发版）

- `iter_track_persistence_batches()` 现在安全获取输入迭代器，异常 `__bool__` 或不可迭代容器会生成空批次而不抛出，保持有界写入生命周期。
- 新增纯模块回归；离线门禁共 600 项 Python 测试及全部 Node UI 回归通过。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续 folder 写入边界（2026-08-28，未发版）

- `prepare_track_persistence()` 对 `folder` 复用统一文本路径投影，非文本或超长值不会再被隐式字符串化；正常索引字段保持不变。
- 新增纯模块回归；离线门禁共 600 项 Python 测试及全部 Node UI 回归通过。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续根摘要容器容错（2026-08-28，未发版）

- `root_index_summary()` 现在安全处理异常的 roots/items 容器，损坏缓存会回退为空摘要而不阻断扫描收尾和索引保存。
- 新增纯模块回归；离线门禁共 603 项 Python 测试及全部 Node UI 回归通过。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续归一化回调异常隔离（2026-08-28，未发版）

- `normalize_scan_items()` 现在安全处理异常 roots 迭代器，并逐项隔离 `is_under`、`relative_folder`、`root_label` 回调异常，损坏配置不会中断曲库索引写入。
- 新增纯模块回归；离线门禁共 603 项 Python 测试及全部 Node UI 回归通过。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续根摘要回调边界（2026-08-28，未发版）

- 根摘要及扫描归一化策略现在隔离异常 roots/items 容器和根判断、目录计算、标签生成回调，损坏配置不会阻断索引收尾。
- 新增纯模块回归；离线门禁共 603 项 Python 测试及全部 Node UI 回归通过。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续路径策略统一（2026-08-28，未发版）

- 新增 `bounded_library_path_text()` 作为统一的受限库路径文本策略，`library_write.py` 不再维护重复长度逻辑；配置路径的既有数字兼容行为保持不变。
- 新增纯模块回归；离线门禁共 605 项 Python 测试及全部 Node UI 回归通过。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续扫描根归属缓存（2026-08-28，未发版）

- `partition_previous_items()` 对重复历史路径缓存首个匹配根，CUE 等重复记录无需反复执行根目录判断；根优先级和分区结果保持不变。
- 新增纯模块回归；离线门禁共 606 项 Python 测试及全部 Node UI 回归通过。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续分区根容器边界（2026-08-28，未发版）

- `partition_previous_items()` 现在先安全物化 roots，异常根目录容器回退为空分区，同时保留重复路径缓存和根优先级语义。
- 新增纯模块回归；离线门禁共 607 项 Python 测试及全部 Node UI 回归通过。未打包、未部署、未进行真实设备验收。
# 变更记录

## 2026-08-29

- 新增 `http_request_policy.request_body_length()`，在服务端读取 POST body 前统一校验 `Content-Length`，隔离负数、浮点、畸形文本及异常对象，并保持 2 MiB 请求体上限。
- 非法长度返回结构化 400，超限返回 413；新增纯策略回归。
- 离线验证：Python 673 项通过，Node/UI 回归全部通过；未打包、未部署、未进行真实设备验收。

## 2026-08-28

- 将前端收藏/歌单引用曲目按 ID 补水逻辑抽至 `library_reference_items.js`，加入 200,000 项硬上限和异常读取隔离；`app.js` 的引用列表总数与分页渲染统一复用，降低大曲库重复遍历风险。
- 离线验证：Python 636 项通过，Node/UI 回归通过；未打包、未部署、未进行真实设备验收。
- 补充隔离异常数组长度访问，新增 Proxy 损坏输入回归。
# 0.2.33 后续资源门控名称边界（2026-08-29，未发版）

- `ConcurrencyGate` 名称限制为 256 字符，空名称回退为 `resource`，避免异常配置影响错误文本和诊断输出。
- 新增资源门控回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续群组封面查询范围（2026-08-29，未发版）

- `loadGroupArtwork()` 现在优先在 `trackList` 内查找群组/专辑封面，避免每次列表重绘扫描整个文档。
- 新增 UI 静态回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续缓存键常量单一来源（2026-08-29，未发版）

- 删除 `library_query_cache.py` 中重复的缓存键边界常量，避免与规范化策略模块产生配置漂移。
- 新增常量来源回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续发布清单记录边界（2026-08-29，未发版）

- `verify_release_evidence.ps1` 拒绝空白或超过 4096 字符的源码清单路径，并继续拒绝绝对路径与 `..` 路径。
- 新增脚本契约回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续发布清单规范路径（2026-08-29，未发版）

- `verify_release_evidence.ps1` 现在拒绝源码清单中的空路径段、`.`、`..`、绝对路径及超长路径。
- 新增脚本契约回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续发布 verifier 变量遮蔽修复（2026-08-29，未发版）

- 源码清单遍历使用独立的 `$relativeManifestPath`，不再覆盖 `SOURCE_MANIFEST.sha256` 文件路径变量。
- 新增脚本契约回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续内存回退查询优化（2026-08-29，未发版）

- `library_memory_query.py` 将分组、目录、专辑和搜索条件合并为单次过滤遍历，降低旧内存索引回退的峰值内存。
- 内存查询回归通过；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续元数据标签解析边界（2026-08-29，未发版）

- 新增 `metadata_tag_resolution.py`，统一测试 ffprobe 完整标签短路及 MP3/DSF/WAV 的 ID3、FLAC/其他容器的 Vorbis 回退选择。
- 新增纯模块回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续本地标签读取异常隔离（2026-08-29，未发版）

- `metadata_tag_resolution.py` 捕获 ID3/Vorbis 回退读取器异常并保留已有 probe 标签，避免单曲损坏中断整库扫描。
- 新增纯模块回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续内存查询单列表过滤（2026-08-29，未发版）

- `library_memory_query.py` 在消费有界迭代器时直接完成过滤，避免大曲库回退场景同时保留两份候选列表。
- 内存查询回归通过；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续 DSD 内存视图异常隔离（2026-08-29，未发版）

- 内存回退的 DSD 筛选改用 `memory_field()`，损坏字典代理不会中断列表查询。
- 查询回归通过；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续探测回调异常隔离（2026-08-29，未发版）

- `metadata_tag_resolution.py` 对 probe reader 异常安全回退到本地容器读取，避免替换探测器或异常文件中断扫描。
- 新增纯模块回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续内存搜索总文本边界（2026-08-29，未发版）

- `library_memory_query.py` 将每条曲目的组合搜索文本限制为 4096 字符，避免多字段长文本造成资源放大。
- 内存查询回归通过；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续内存回退入口去复制（2026-08-29，未发版）

- `_query_memory_library_page()` 让普通/DSD 视图直接使用有界过滤器，避免整库复制；随机视图仍按需采样。
- 查询回归通过；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续扫描排序物化边界（2026-08-29，未发版）

- `library_scan_results.py` 的 `sort_scan_items()` 不再直接 `list()` 物化任意输入，最多消费 200,000 条扫描记录。
- 扫描结果回归通过；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续扫描最终化结果上限（2026-08-29，未发版）

- `finalize_scan_results()` 在去重阶段达到 200,000 条唯一记录后停止消费输入，防止排序前的无界结果积累。
- 扫描结果回归通过；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续扫描复用输入上限（2026-08-29，未发版）

- `library_scan_results.py` 对旧索引构建、多根分区和最终化去重统一限制输入消费，最多处理 200,000 条记录。
- 扫描结果回归通过；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续扫描复用根目录边界（2026-08-29，未发版）

- `partition_previous_items()` 现在最多消费 64 个根目录，保持恢复阶段的输入资源有界。
- 扫描结果回归通过；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续扫描路径键边界（2026-08-29，未发版）

- `library_scan_results.py` 对旧索引和多根分区的路径键限制为 4096 字符，异常超长路径安全跳过。
- 扫描结果回归通过；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续缓存身份键拒绝截断（2026-08-29，未发版）

- `library_query_cache_key.py` 对超长数据库路径和命名空间直接放弃缓存，避免截断造成身份冲突。
- 缓存键回归通过；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续扫描签名总预算（2026-08-29，未发版）

- `library_scan_results.py` 对签名文本增加 8 MiB 全局预算，避免大量条目在排序/拼接阶段形成过大临时数据。
- 扫描结果回归通过；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续源码清单证据资源上限（2026-08-29，未发版）

- `verify_release_evidence.ps1` 对源码清单增加 64 MiB 文件上限和 200,000 条记录上限。
- 新增脚本契约回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续扫描根路径输入过滤（2026-08-29，未发版）

- `partition_previous_items()` 收集根目录时跳过非文本、空值及超过 4096 字符的根路径。
- 扫描结果回归通过；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续前端刷新缓存竞态修复（2026-08-29，未发版）

- 刷新请求移除响应返回时的二次缓存清空，保持并发请求期间新缓存不被误删。
- UI 加载回归通过；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续前端响应权重边界（2026-08-29，未发版）

- `library_response_policy.js` 将响应权重限制为 6000，避免异常数组长度放大缓存权重计算。
- UI 响应策略回归通过；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续群组封面节点去重（2026-08-29，未发版）

- `loadGroupArtwork()` 使用 `Set` 去重封面父节点，减少重复监听和布局处理。
- UI 封面回归通过；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续专辑元数据 LRU（2026-08-29，未发版）

- 新增 `ui/album_metadata_cache.js`，将专辑列表与详情使用的补全元数据限制为 4096 项 LRU；长期翻阅大专辑库不再让前端对象持续增长。
- 当前页/详情读取会刷新热度；淘汰项仍可沿既有分页请求链路恢复。新增 Node 回归；未打包、未部署、未进行真实设备验收。
- 缓存写入同时限制专辑文本字段和在线封面 URL 长度，避免少量畸形响应绕过条目上限放大内存。

# 0.2.33 后续播放设备列表边界拆分（2026-08-29，未发版）

- 新增 `playback_targets_presentation.py`，统一且有界地组装本机、USB DAC、DLNA/UPnP 播放目标。
- 目标总数最多 256 项；USB DAC 条目只保留必要的 MPD 可用性与 ALSA 身份摘要，不再为每一行复制完整后端诊断状态。新增专项回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续专辑元数据缓存一致性（2026-08-29，未发版）

- 曲库分页响应缓存清理时同步清理专辑元数据 LRU，扫描或索引刷新后不会继续使用旧歌手、发行日期和在线封面字段。
- 普通页面切换仍保留专辑元数据热点；新增 UI 契约回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 JSON 响应资源边界（2026-08-29，未发版）

- 新增 `json_response_policy.py`，将服务端 JSON 响应限制为 8 MiB；循环引用、不可序列化对象或超限载荷会降级为固定 500 错误体。
- `Handler.send_json()` 统一接入，避免异常状态在 HTTP 响应阶段放大资源或中断请求线程。新增专项回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续响应头边界（2026-08-29，未发版）

- 新增 `response_header_policy.py`，统一限制可选响应头数量、名称和值长度并拒绝 CR/LF 注入。
- `send_json()` 扩展头不再执行任意对象字符串化；正常兼容头部行为保持不变。新增专项回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 XML 响应资源边界（2026-08-29，未发版）

- 新增 `xml_response_policy.py`，将 DLNA XML 响应限制为 1 MiB；异常类型和超限载荷不再通过 `str()` 进入响应。
- `send_xml()` 统一降级为固定错误体并返回 500，正常 description/SCPD/SOAP 行为保持不变。新增专项回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 JSON 紧凑响应（2026-08-29，未发版）

- JSON 响应改用紧凑分隔符，减少大曲库分页、设备列表和诊断载荷的网络及序列化开销。
- 保持 JSON 字段语义、响应上限和错误降级行为不变；新增回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续可观测性超长键脱敏边界（2026-08-29，未发版）

- `observability.py` 对超长结构化日志键不再执行完整 `lower()`；键名仅保留有限前缀，关联值直接按敏感信息处理为 `[REDACTED]`。
- 新增回归，防止超长 `str` 子类触发无界大小写转换；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续元数据发布日期边界拆分（2026-08-29，未发版）

- 新增 `metadata_release_date.py`，从 `metadata_service.py` 分离提供方发布日期/epoch 规范化；普通日期回退与 epoch 转 ISO 日期保持兼容。
- 限制文本长度、拒绝非有限数值及任意对象字符串化，新增专项回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续发布证据内部一致性（2026-08-29，未发版）

- `verify_release_evidence.ps1` 额外校验 provenance schema、暂存文件数、UI asset build 格式和其版本绑定，收紧会话删除后的离线恢复证据判定。
- 旧 `0.2.33` 产物继续只报告 FPK 校验和有效、缺少完整来源证据；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续全量列表尾部请求收敛（2026-08-29，未发版）

- 全量歌曲分页计划现在受 200,000 条合并预算限制；达到结果上限、取满或遇到空页时取消未启动的批次请求。
- 保持首批优先、顺序合并与四并发语义，新增 Node 回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续内存回退 DSD 单遍筛选（2026-08-29，未发版）

- DSD 内存视图改在 `filter_sort_memory_items()` 单次有界遍历中完成筛选，避免先建立完整候选副本。
- 保持排序、分页和异常条目隔离语义，新增专项回归；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续兼容浏览响应物化上限（2026-08-29，未发版）

- 新增 `library_browse_rows.py`，为未分页分组/文件夹兼容响应增加 5,000 行物化上限并隔离异常迭代器与行映射。
- 分页请求保持原有窗口查询；新增纯模块回归，未打包、未部署、未进行真实设备验收。

# 0.2.33 后续元数据候选载荷边界（2026-08-29，未发版）

- 新增 `metadata_provider_payload.py`，将第三方搜索候选统一限制为 64 条映射项；QQ、网易、酷狗、咪咕、JOOX、千千、MusicBrainz 与 AcoustID 均复用。
- 保持正常检索、评分和提供方优先级不变，隔离异常/超量响应对 worker 的遍历压力；新增专项及服务接线回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续发布证据行为核验（2026-08-29，未发版）

- `verify_release_evidence.ps1` 在 `Get-FileHash` 不可用的精简 PowerShell 环境回退到流式 .NET SHA-256，恢复验证不再依赖某个 cmdlet。
- 发布回归构造真实临时 FPK、SHA256SUMS、SOURCE_MANIFEST 和 SOURCE_PROVENANCE，验证严格恢复可通过且篡改 `staged_file_count` 会被拒绝，补足此前文本契约之外的行为证据。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续播放队列补水总量边界（2026-08-29，未发版）

- `library_item_hydration.py` 为内部持久化队列恢复增加 50,000 ID 总预算，继续按 SQLite 变量限制批量查询并保持请求顺序。
- 损坏/异常状态不再可能触发无界 SQL 批次或结果映射；新增独立回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续前端补水取消竞态（2026-08-29，未发版）

- 曲目引用补水新增 generation 所有权；切换视图时同步释放旧的处理中 ID，旧批次即使稍后结束也不会触碰新一轮状态或触发错误的标记清理。
- 保持现有四并发、批次预算和缓存淘汰语义，新增 Node 契约回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 DLNA NextURI 队列边界（2026-08-29，未发版）

- 新增 `dlna/next_queue.py`，为 Renderer 的 SetNextAVTransportURI 预置链路增加 64 条 FIFO 总量及 URI/metadata 单项大小限制。
- 超额请求不会覆盖已排队的最早 URI，而会计入 `next_queue_dropped`；状态公开 `next_queue_limit` 以便离线/支持诊断。空 URI 清空和 FIFO Next 行为不变，新增专项与协议回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 DLNA 控制 worker 合并（2026-08-29，未发版）

- Renderer 控制后端改为单 worker + 最新动作槽；连续控制请求不再各自创建线程，旧 generation 会被安全丢弃。
- 新增 `backend_worker_active`、`backend_pending`、`backend_coalesced` 状态观测和 burst 控制回归，未改变 UPnP 响应及串行后端语义。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 DLNA 事件载荷边界（2026-08-29，未发版）

- 新增 `dlna/event_payload.py`，对 GENA AVTransport 通知中的 URI、DIDL metadata 和最终 XML 本体限制大小，拒绝任意状态对象字符串化。
- `DlnaEventService` 保留订阅/队列接线，单通知也不再能够突破内存预算；新增专项和协议回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 DLNA 转义膨胀边界（2026-08-29，未发版）

- 事件载荷源文本上限调整为 URI 4096、metadata 40 KiB，以覆盖 XML 双重转义的最坏膨胀，最终通知体继续限制在 512 KiB 内。
- 新增引号密集 metadata 回归，确保超长/转义密集状态仍返回可发送的非空通知体。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 DLNA 后端调度边界拆分（2026-08-29，未发版）

- 新增 `dlna/backend_schedule.py`，将 Renderer 最新动作合并、worker 启动判定与合并计数上限抽为独立纯策略。
- `renderer.py` 保持锁和线程生命周期接线；新增专项及协议回归。未打包、未部署、未进行真实设备验收。

# 0.2.33 后续查询缓存稳健性（2026-08-30，未发版）

- 查询缓存读取路径统一校验条目时间戳；异常结构或非有限时间戳会被隔离并计入 `uncacheable`，避免损坏缓存中断请求。
- 新增专项回归，未改变正常 TTL、LRU、命中率和失效语义；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续 DLNA Renderer 输入展示边界拆分（2026-08-29，未发版）

- 新增 `dlna/renderer_presentation.py`，将 URI/DIDL 存留输入规范化和 title/artist/art URL 展示字段解析抽为纯模块。
- 限制状态存留与展示文本大小，拒绝任意对象字符串化，保留 DIDL 字段优先和 URI 文件名 fallback；新增专项和协议回归。未打包、未部署、未进行真实设备验收。
- 2026-08-30：分页投影在有限读取顶层字段的同时定向保留 `items` 与分页契约字段，避免兼容适配器字段顺序变化导致空列表；新增专项回归。未打包、未部署、未进行真实设备验收。
- 2026-08-30：新增 HTTP 请求观测纯模块，固定延迟路由可直接进入指标聚合，保持结构化日志和状态码统计语义；新增专项回归。未打包、未部署、未进行真实设备验收。
- 2026-08-30：新增内存曲库分页纯策略模块，`library.py` 的回退入口仅保留配置接线；随机 100 项、过滤排序和分页字段保持兼容。新增专项回归。未打包、未部署、未进行真实设备验收。
- 2026-08-30：为 HTTP 服务增加线程创建前的并发门禁，超限请求返回固定 503，健康与诊断暴露 worker 压力字段；新增 `http_max_workers` 配置及专项回归。未打包、未部署、未进行真实设备验收。
- 2026-08-30：将有界 HTTP server 装配抽至 `http_server.py`，降低 `server.py` 入口耦合；保持拒绝响应和门禁快照语义，新增独立回归。未打包、未部署、未进行真实设备验收。
# 0.2.33 后续前端拆分（2026-08-30，未发版）

- `repeat_mode_policy.js` 统一提供循环状态、中文文案和三态图标 SVG，`app.js` 不再持有图标实现细节。
- 更新 UI 静态回归；完整离线门禁 953 项 Python 测试及全部 Node/UI 回归通过。
- 未打包、未部署、未进行真实设备验收。

# 0.2.33 后续核心拆分（2026-08-30，未发版）

- 新增 `library_search_index_policy.py`，统一 SQLite 搜索索引模式的安全投影与 FTS5 最短搜索长度判定。
- `library.py` 保留数据库模式探测和锁接线；新增专项回归，完整离线门禁 953 项 Python 测试及全部 Node/UI 回归通过。
- 未打包、未部署、未进行真实设备验收。

# 0.2.33 后续核心拆分（2026-08-30，未发版）

- 新增 `playback_queue_policy.py`，统一播放队列请求的安全字段归一化及 MPD 原生队列同步判定。
- `server.py` 仅保留队列持久化、播放核心和输出服务编排；新增专项回归，完整离线门禁 952 项 Python 测试及全部 Node/UI 回归通过。
- 未打包、未部署、未进行真实设备验收。

# 0.2.33 后续发布治理（2026-08-30，未发版）

- `tools/verify_release_evidence.ps1` 新增 `-Json` 输出模式，复用既有校验路径并输出压缩 JSON，方便恢复自动化读取发布物、校验和及证据完整性。
- 保留默认人类可读输出，新增完整/legacy 证据 fixture 回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续核心拆分（2026-08-30，未发版）

- 新增 `http_worker_presentation.py`，统一 `/api/health` 与 `/api/diagnostics` 的 HTTP worker 指标投影和异常隔离。
- 新增纯模块回归；未改变接口字段或真实播放行为，未打包、未部署、未进行真实设备验收。
# 0.2.33 后续核心拆分（2026-08-30，未发版）

- 新增 `playback_targets_response.py`，统一播放设备目标响应字段和当前目标可用性判断；探测副作用仍留在服务层。
- 新增回归，未改变目标发现或播放控制协议；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续大曲库查询拆分（2026-08-30，未发版）

- 新增 `library_track_filter_policy.py`，统一普通曲目分页的过滤条件和参数顺序，降低 `library.py` 查询分支复杂度。
- 新增纯策略回归，未改变查询协议或 SQLite 执行路径；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续前端性能拆分（2026-08-30，未发版）

- 新增 `ui/library_response_loader.js`，统一大曲库分页响应的缓存命中、并发去重和失效保护。
- 新增 Node 回归，未改变 API 请求协议或渲染行为；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续查询稳健性（2026-08-30，未发版）

- 曲目分页过滤策略新增异常属性访问隔离，损坏查询对象不会中断请求。
- 新增回归，未改变正常过滤条件或接口协议；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续服务端资源治理（2026-08-30，未发版）

- HTTP worker 达到并发上限时返回 503，并附带 `Retry-After: 1`，改善客户端退避行为。
- 保持既有错误 JSON 与资源门禁；新增回归，未打包、未部署、未进行真实设备验收。
# 0.2.33 后续 UPnP 边界拆分（2026-08-30，未发版）

- 新增 `upnp_device_selection.py`，隔离 UPnP 设备列表中的安全 ID 选择和异常条目处理。
- 新增回归，未改变发现或控制协议；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续 UPnP 稳健性（2026-08-30，未发版）

- UPnP 设备选择支持普通可迭代输入，最多读取 500 项并隔离迭代器异常，保持原有列表行为兼容。
- 新增回归，未改变发现/控制协议；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续前端接线修复（2026-08-30，未发版）

- 补齐 `library_response_loader.js` 在 `index.html` 中的加载顺序，确保分页缓存模块先于 `app.js` 初始化。
- 通过脚本动态发现、语法检查和完整离线回归；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续前端查询优化（2026-08-30，未发版）

- 新增 `library_load_key.js`，统一大曲库页面请求复用键的安全归一化。
- 新增 Node 回归并补齐 `index.html` 加载顺序，未改变查询协议；未打包、未部署、未进行真实设备验收。
# 0.2.33 后续前端治理（2026-08-30，未发版）

- 新增 UI 脚本加载顺序回归，确保分页响应加载器和请求键策略在 `app.js` 前初始化。
- 未改变运行逻辑；未打包、未部署、未进行真实设备验收。

# 0.2.33 后续维护索引（2026-08-30，未发版）

- 同步 TODO 的 P3 拆分索引，记录近期新增的 HTTP worker、播放目标、UPnP 和分页加载边界；总项继续保留未完成。
# 2026-08-31

# 2026-09-01

- 在 root 三星 S9+ 上实测官方飞牛音乐的真实运行时播放链路：确认 `audio_service` 是当前生产路径，
  抓到 `setState` / `setQueue` 的运行时消息以及其系统 MediaSession、前台服务和通知对应关系。
- 确认官方 `trim_music` 是飞牛 APP 内置 Flutter package，而非第三方 FPK 可直接调用的普通 WebView
  接口；未向私有通道发送或回放任何消息。
- 原始动态消息包含短期会话凭据，分析结束后已删除，仅保留脱敏系统证据。

- Web UI 与 Android Bridge 统一首次远程会话的 generation/engine epoch，避免服务端首条控制
  命令与原生会话身份不一致；未进行真实设备验收。

- 对比新版飞牛 APP 1.35.2 与 fnAudio Android 播放服务，确认官方采用 Flutter `audio_service` 的 `MediaSessionCompat`、前台服务、session activity 与 PARTIAL_WAKE_LOCK 组合。
- fnAudio `PlaybackService` 保留 Media3，新增远程播放 WakeLock、`setSessionActivity`、`START_STICKY`，并在任务移除时维持远程前台通知。
- 运行 `update_source_manifest.ps1` 与 `test_offline.ps1`：953 项 Python 测试及全部 Node/UI 回归通过；未进行设备动态验收。
# 2026-08-31

- 补充新版 trim.music 跨平台播放会话研究：确认 `trim_base_plugin` 的 participant、
  generation/engineEpoch、命令 ticket、快照回传和 KeepAlive 租约模型，并记录 Android、
  iOS、鸿蒙宿主映射及 fnAudio 的等价抽象建议。

# 2026-08-31

- 在 `C:\path\to\fnAudio\tools\android-sdk` 安装并启动 API 35 Android 模拟器，固化
  `test_android_emulator.ps1` 默认 SDK 路径。
- 发现当前 debug APK 仅含 arm64-v8a 原生库，无法安装到 x86_64 AVD（明确记录为 ABI
  阻塞，不等同于运行时崩溃）。iOS Simulator/HarmonyOS 模拟器受宿主平台限制，暂记为
  跨平台动态验收待迁移项。

# 2026-08-31

- 播放核心状态与 SSE 事件补齐统一会话身份：`generation`、`engine_epoch`、`command_ticket`。
  控制请求绑定身份后，权威状态版本单调更新；重复身份不会重复发布事件。字段均有界，
  不输出令牌、地址或文件路径。
- 新增播放核心与 SSE 投影回归；运行 `update_source_manifest.ps1` 与 `test_offline.ps1`，
  963 项 Python 测试及全部 Node/UI 回归通过。未打包、未部署、未进行真实设备验收。
- Android MediaSession 命令响应复用远程状态的 generation/engine epoch 门禁，避免迟到的
  旧通知操作确认覆盖当前会话；新增静态桥接契约检查，未进行真实设备验收。
- 命令确认增加 `command_id`/`core.command_ticket` 一致性校验，错配响应记录
  `stale_command_ticket` 并丢弃；未进行真实设备验收。
- 增加 Android 会话建立、远程通知发布和 SSE 事件流连接/失败日志，区分网络、HTTP 和载荷
  错误；日志保持脱敏。未进行真实设备验收。
- 远程会话持久化增加 schema 与 7 天过期边界，过期或时钟异常快照会安全清理并记录原因；
  未进行真实设备验收。
- 媒体键命令确认与任务移除路径现在立即持久化原生远程播放器状态，降低进程回收恢复旧
  曲目的风险；未进行真实设备验收。
- 服务端播放控制增加旧会话单调拒绝策略，返回 `stale_session`/409，避免迟到命令改变当前
  播放目标；未进行真实设备验收。
- 服务端旧会话拒绝增加脱敏结构化日志 `playback_stale_session`，仅记录有界身份和目标类型；
  未进行真实设备验收。
- Android 媒体键命令响应日志区分成功确认与 HTTP 失败，不再将 409/5xx 记录为 confirmed；
  未进行真实设备验收。
- Web UI 远程控制继承并回传 generation/engine epoch，退出远程模式时清理身份，避免跨会话
  复用旧状态；未进行真实设备验收。
# 2026-08-31 持续目标推进（会话失败路径契约）

- 强化 `playback_session_contract` 的 generation、engine epoch、revision、position 与命令
  ticket 边界归一化，拒绝布尔值、超大整数和空 ticket，避免不可信输入抛出异常或污染会话。
- 新增服务端 stale_session 专项回归：旧会话固定返回 HTTP 409 且不调用播放核心变更；结构化
  日志写入失败时仍保持安全拒绝语义。
- 本轮仅执行离线验证，不进行 Android 真机、DAC、DSD、DLNA、AirPlay 或 App Center 验收。

# 2026-08-31 持续目标推进（Android 会话时序静态门禁）

- 增加 Android bridge 静态契约：确保 PlaybackService 按 player → MediaSession → ready →
  restore 的顺序建立会话，并确保远程模式先通过 ready guard，再激活 metadata-only player，
  最后发布前台媒体通知。
- 该门禁用于防止后续重构引入通知缺失或恢复过早的竞态；仍需真实 Android 动态验收确认系统行为。

# 2026-08-31 持续目标推进（远程轮询失败可观测）

- Android 远程状态轮询现在分别记录 network、HTTP 状态码和 invalid payload，避免 SSE
  断开后进入轮询回退时出现静默失步。
- 日志保持脱敏，不记录 token、地址、文件路径或队列内容；离线 Node/UI 与 Python 门禁通过。

# 2026-08-31 持续目标推进（媒体键失败响应隔离）

- Android `PlaybackService` 不再应用 HTTP 失败命令响应中的 `core` 快照；只有成功响应并通过
  generation、engine epoch、command ticket 校验后才更新原生远程播放器。
- 失败响应仍会记录 HTTP 原因并触发一次状态刷新，保持后端权威状态源不变。

# 2026-08-31 持续目标推进（远程 MediaSession 权威确认）

- `RemotePlaybackPlayer` 不再在媒体键命令发送前乐观修改播放、停止、切歌、循环或随机状态。
- 命令成功后才应用服务端 `transport/position/core` 快照；失败响应只记录原因并等待权威刷新，
  从源头减少通知栏状态抖动与旧事件污染。

# 2026-08-31 持续目标推进（远程通知封面）

- 远程自定义 MediaStyle 通知现在会对当前曲目的 artwork 做 2 MiB 有界解码，并设置为
  通知大图标；损坏或超大图片不会阻塞通知发布，会记录脱敏失败原因。

# 2026-08-31 持续目标推进（权威状态通知刷新）

- SSE/轮询状态和成功命令确认应用远程曲目、位置或播放状态后，立即重发前台 MediaStyle
  通知，确保切歌后通知栏与后端权威快照同步。

# 2026-08-31 持续目标推进（服务销毁恢复检查点）

- `PlaybackService.onDestroy()` 在释放远程播放器前写回最新已确认的位置、曲目和播放状态，
  并记录 `remote_session_restore checkpointed: service_destroy`，增强系统回收后的恢复机会。

# 2026-08-31 持续目标推进（命令票据缺失隔离）

- Android 对带 `command_id` 的命令响应要求必须提供匹配的 `core.command_ticket`；缺失或
  不匹配均记录 `stale_command_ticket` 并丢弃，防止不完整响应覆盖当前会话。

# 2026-08-31 持续目标推进（恢复检查点同步落盘）

- 服务销毁前的最后远程会话检查点改用同步 `SharedPreferences.commit()`；常规状态更新仍
  使用 `apply()`，兼顾正常运行性能与进程即将退出时的持久性。

# 2026-08-31 持续目标推进（Android SSE 帧资源边界）

- 远程事件流客户端增加 512 KiB 单帧上限；超大帧会被丢弃并记录
  `remote_event_stream failed: oversized_payload`，JSON 解析异常记录 `invalid_payload`。

# 2026-08-31 持续目标推进（SSE 帧大小计算优化）

- SSE 客户端改用增量 UTF-8 字节计数进行帧预算检查，避免每行将完整累积字符串重新编码，
  降低大事件帧的临时内存分配。

# 2026-08-31 持续目标推进（空状态快照诊断）

- `applyRemoteStatus(null)` 不再静默返回，统一记录 `remote_status failed: invalid_payload`，
  便于识别调用链生成空快照的来源。

# 2026-08-31 持续目标推进（前台通知发布异常隔离）

- 远程通知调用 `startForeground()` 现在捕获运行时异常并记录
  `remote_notification failed: publish`，避免厂商通知权限/限制让远程播放服务直接退出。

# 2026-08-31 持续目标推进（播放/暂停命令去重）

- `RemotePlaybackPlayer` 增加 pending playWhenReady 门禁；后端确认前重复的播放/暂停回调
  会被合并，权威状态到达后清除 pending，减少重复 HTTP 命令和通知抖动。

# 2026-08-31 持续目标推进（循环/随机命令去重）

- 远程 MediaSession 对循环和随机模式增加 pending 去重；命令发送使用用户请求值，展示状态
  仍等待后端权威确认，确认后自动清除 pending。

# 2026-08-31 持续目标推进（模式 pending 与展示状态隔离）

- 循环/随机 pending 请求值与实际展示状态分离，重复回调只做去重，不提前改变 MediaSession
  展示，确认后再由权威快照统一收敛。

# 2026-08-31 持续目标推进（失败命令 pending 释放）

- 远程命令网络失败或 HTTP 失败时清除对应 pending play/pause/repeat/shuffle 标记，避免一次
  临时故障永久阻塞同一操作的重试；失败响应仍不会覆盖本地状态。

# 2026-08-31 持续目标推进（prepare/stop pending 竞态）

- prepare 与 play 共用 pending 去重；stop 会立即清除播放 pending，避免停止后重新播放被
  错误抑制。

# 2026-08-31 持续目标推进（命令确认日志准确性）

- Android 仅在命令快照通过 generation、engine epoch、command ticket 校验并真正应用后记录
  `remote_command confirmed`；HTTP 成功但快照被拒绝时记录 `stale_response`。

# 2026-08-31 持续目标推进（服务入口未知 action 诊断）

- `PlaybackService.onStartCommand()` 对未知启动 action 增加脱敏诊断
  `service_start ignored: unknown_action`，不改变原有安全忽略行为。

# 2026-08-31 持续目标推进（六项验收矩阵）

- 新增 `docs/PLAYBACK_SESSION_ACCEPTANCE_MATRIX.md`，按会话时序、通知、媒体键、恢复、身份
  隔离和可观测性列出当前实现证据及真实 Android 动态验收缺口。

# 2026-08-31 验证记录（Android Gradle 环境）

- 尝试执行 `:app:testDebugUnitTest --no-daemon`，Gradle 9.6.1 因宿主无法建立 loopback
  connection 退出；这是验证环境阻断，不代表源码编译失败，待可用 Android 构建主机补跑。
# AI 变更记录

## 2026-09-01 列表刷新与歌词即时回退

- 扫描刷新期间只更新状态计数，不再触发一次中间全量 `render()`，降低歌曲列表加载后的闪烁和封面重解码。
- `/api/lyrics` 优先读取嵌入歌词及同名 sidecar LRC；命中本地歌词时立即返回 `source=本地歌词`，不等待 provider worker，改善播放后歌词首屏体验。
- 新增 UI/元数据回归；源码清单与完整离线门禁通过，未进行真实设备验收。

## 2026-08-31 命令票据空值隔离

- Android 远程命令响应若包含 `command_id`，现在必须同时满足非空 `command_id`、非空
  `core.command_ticket` 且两者完全匹配；格式损坏的空票据会记录 `stale_command_ticket`
  并丢弃，避免旧确认污染当前会话。

## 2026-08-31 外部唤起入口动态复核

- 在小米 15 Pro 上验证：直接对 `/music/` 发起 Android `ACTION_VIEW` 会由系统浏览器处理；
  官方 `trim://app.com/openShareUrl` + `android.intent.trim.action_EVOKE_BY_EXTERNAL` 能唤起
  `com.trim.app/.MainActivity`，但没有证据表明该入口授予第三方页面 `HostPlaybackSessionApi`
  participant 权限。新增设备包清单证据 `artifacts/device-trim-app-package.txt` 和路由链路分析
  `artifacts/trim-music-scheme-routing-20260831.md`。

## 2026-08-31

- 在小米 15 Pro 的飞牛 APP 1.35.2 中直接播放官方 `trim.music` 并保存 MediaSession、通知、服务、
  页面返回和媒体键转换证据。确认官方私有路径为 Flutter `HostPlaybackSessionApi` participant 协调器
  + `com.ryanheise.audioservice.AudioService`，而非 `native_app=true`、全页 URL 或标准网页通知。
- 继续解析 1.35.2 DEX：已得到 participant 注册、状态上报、激活、命令确认和快照模型的正式字段名，
  并定位 Android 协调器 `Lz72 -> Ljc` 及其 `trim-playback-session` 专用 HandlerThread。未修改 fnAudio
  代码、未向飞牛 APP 发送猜测私有协议、未重新打包。
- 静态审计进一步确认：宿主协调器注册层未做包名/签名检查，但 participant 必须运行在飞牛 APP
  Flutter Engine 的 BinaryMessenger 上；官方音乐静态 JS 未注册播放会话 handler。新增证据汇总
  `artifacts/trim-music-host-session-static-analysis-20260831.md`。
- 更新宿主研究文档、项目上下文和待办：官方 Web 静态包未发现可供第三方调用的私有 JS 桥；后续目标
  改为捕获真实 participant 消息载荷、调用方向与身份门禁，未向 fnAudio 注入猜测的 Pigeon 协议。

- Android `PlaybackService` 新增远程 JSON 响应体有界读取（512 KiB），同时校验声明长度与
  实际读取长度；超限或空响应进入既有 `invalid_payload` 诊断路径。离线回归 980 项通过。
# 2026-08-31

- 完成 trim.music/fnOS 宿主播放会话边界复核：明确标准 Web Media Session 与官方私有宿主服务的职责边界。
- Web UI 新增 `fnAudioMediaSessionDiagnostics()` 能力诊断，并将空闲状态正确设为 `none`；新增静态回归契约。
- 未调用未公开的飞牛 Pigeon 通道；未进行真实设备、通知、锁屏或浮窗动态验收。
## 2026-08-31 宿主播放会话公开桥接适配器

- 新增 `src/app/ui/host_playback_session.js`，提供严格 opt-in 的宿主会话适配层。
- 仅调用宿主明确暴露的 `initialize`、`synchronize`、`requestActivation`、`reportState`、`release`，
  不复制或猜测 `trim_base_plugin` 的私有 Pigeon 协议。
- `fnAudioMediaSessionDiagnostics()` 现在包含 `hostPlaybackSession` 检测结果、支持的方法、最后动作
  和脱敏失败原因；无桥接时保持 no-op。
- 新增 Node 离线回归 `src/tests/test_host_playback_session.js`；与完整离线门禁一起通过。
- 重新封装并部署 0.2.34 FPK 到内网测试机，验证根页面 HTTP 200 和公开桥接脚本已发布。
- 公开桥接增加曲目上下文激活/释放生命周期：同一曲目只激活一次，切歌自动换上下文，清空队列释放。
- 公开桥接增加异常隔离：安全处理宿主对象 getter、缺失方法和 Promise reject，避免第三方 WebView
  对象导致页面启动失败。
# 2026-08-31 官方前端补充静态证据

## 2026-08-31 通用 WebView bridge 可观测性

- `host_playback_session.js` 新增只读诊断：检测 `window.flutter_inappwebview.callHandler` 的存在，
  但不调用任意未知 handler，不改变显式宿主播放桥接行为。
- 修正跨 VM 数组断言后，完整离线门禁通过：982 项 Python 测试、Host Playback Session Node、
  Android bridge/CGI 与全部 UI 回归均通过。

- 检查官方 `trim-music-main.js` 后确认 `window.NativeShell` 仅用于能力探测，未发现第三方 FPK 可调用
  的通知、锁屏、媒体键或浮窗桥接接口。
# 2026-09-01

- 优化大曲库首屏：增加 15 分钟、384KiB 上限的本地歌曲页快照，冷启动先绘制最近成功内容，再由网络结果校正。
- 减少列表闪烁：保留已提交列表 HTML，状态刷新不再重复替换相同 DOM。
- 增强元数据失败可观测性：候选与歌词接口返回任务状态、尝试次数和截断错误原因；歌词失败时给出可读提示。
- 增加 provider 级脱敏失败统计，并将空候选从 `review` 修正为 `no_match`。
- 候选对话框区分后台检索、无匹配和数据源异常提示。
- 大曲库列表行增加兼容性渐进渲染提示，减少首屏下方布局与绘制压力。
- 优化启动恢复：持久播放队列详情改为有界并发批量读取，降低大队列导致的首屏状态恢复延迟。
- 首屏页面快照改为浏览器空闲时写入，减少网络首批列表落地后的主线程抢占。
- 元数据 provider 增加短时按源熔断，降低数据源故障时的重复超时等待。
- 重新生成 100k 曲库分页/搜索基准，记录当前 SQLite/FTS 性能基线。
- 已运行 `update_source_manifest.ps1` 与 `test_offline.ps1`，Python 985 项及 Node/UI 回归全部通过。
# 2026-09-01

- 优化首屏列表提交：快照与网络校正的稳定行按键一致时只替换发生变化的行，避免旧 WebView 整表重建引起封面闪烁。
- 修复元数据 provider JSON 的字符集处理：遵循响应 charset，并提供 UTF-8/GB18030/Big5 有界回退，避免编码异常造成标题、歌手等字段被静默丢弃。
- 元数据候选 pending 状态增加最多 8 次自动刷新，关闭对话框立即取消，单曲补全完成后无需重新打开菜单。
- 修复曲目匹配只保存候选文本而不保存封面的缺口：候选封面现在进入统一曲目资产缓存，并可供 UI 与后续 Tag 写回使用。
- 新增 UI 与元数据回归，完整离线门禁 990 项通过。
# 2026-09-02 元数据结果及时回投列表

- 修复元数据 worker 已写入歌词、匹配或封面缓存，但歌曲列表仍命中旧 `/api/library` 响应的问题。
- 前端状态轮询新增稳定投影签名：仅在已提交/终态元数据计数变化时失效列表缓存并重新读取当前页；后台 pending 数变化不再造成无意义整页重绘，降低首屏闪烁。
- 已运行源码清单更新、Node UI 回归和完整离线门禁（1016 项 Python 测试通过）。
# 2026-09-02 候选确认后即时刷新

- 曲目候选对话框确认成功后立即失效列表响应缓存并刷新当前页，主列表不再等待下一轮后台状态轮询才显示新元数据。
- 刷新继续走稳定行键增量提交，避免已解码封面和未变化歌曲行闪烁。
- UI 回归与完整离线门禁通过。
# 2026-09-02 元数据状态探测超时隔离

- 将元数据状态请求从音乐库状态请求中隔离，并设置 1.5 秒超时与取消，避免元数据服务异常拖慢首屏/扫描状态更新。
- 正常响应仍参与元数据投影签名校正；接口超时不会触发列表重绘。
- UI 回归与完整离线门禁通过。
# 2026-09-02 元数据投影策略模块化

- 将元数据投影签名从 `app.js` 拆至独立纯策略模块，隔离 pending 队列变化与已提交结果变化。
- 新增 Node 回归覆盖签名稳定性和失效边界；源码清单及完整离线门禁已更新。
# 2026-09-01 修复缺失歌手 Tag 的元数据匹配

- provider 评分不再把“未知艺术家/未知歌手”当作真实歌手，从而避免仅有歌名的歌曲被错误判定为无匹配。
- 新增回归覆盖标题命中与占位歌手场景；完整离线门禁通过。
# 2026-09-01 元数据匹配策略模块化

- 将文本规范化和 provider 评分从大型元数据服务拆至独立纯模块，保留原有服务导出兼容性。
- 缺失歌手 Tag 的占位值继续按空值处理；元数据专项与完整离线门禁通过。
# 2026-09-01 动态 API 禁止陈旧缓存

- 服务端动态 `/api/*` JSON 响应增加 `no-store/no-cache` 与 `Pragma`，避免浏览器、WebView 或代理缓存旧元数据状态和歌曲列表。
- 客户端会话内 LRU 逻辑不变；HTTP 集成测试与完整离线门禁通过。
# 2026-09-01 元数据状态签名健壮性

- 元数据投影签名增加有界数字/文本解析，异常状态值不再抛错或产生不稳定签名。
- 增加 Symbol、对象、超长数字和控制字符回归；完整离线门禁通过。
# 2026-09-01 元数据状态文案澄清

- 设置页不再把默认关闭的后台补全显示成“队列已完成”，改为提示播放/歌词页仍支持按需获取。
- provider 异常、待确认匹配和 Tag 写回状态继续独立展示；UI 与离线门禁通过。
# 2026-09-01 标题-only 元数据候选覆盖

- 新增离线 provider fixture，验证缺失歌手和专辑 Tag 的歌曲仍能通过标题获得候选结果。
- 防止评分修复在未来 provider 调整中回归；完整离线门禁通过。
# 2026-09-01 大曲库性能复测

- 20,000 首合成曲库复测：分页缓存约 26.7 倍、引用曲目补水约 11.8 倍、FTS 搜索约 5.8 倍于 LIKE。
- 证据：`artifacts/large-library-benchmark-20260901-followup.json`。
# 2026-09-02 元数据陈旧失败自动恢复

- 新增独立 `metadata_retry_policy.py`，仅允许超过 15 分钟的终态 provider 失败在用户再次查看歌词或候选时恢复为 pending。
- 新请求会清空旧错误、重置有限尝试次数并唤醒对应 worker；新鲜失败仍原样显示，避免 provider 故障时循环请求。
- 增加 malformed 时间、非失败状态和冷却边界回归；未进行真实设备或外部服务验收。

# 2026-09-02 歌词页联动单曲元数据

- `/api/lyrics` 在无本地歌词且曲目存在缺失/文件名来源字段时，同时排入一条有界的 `track` 候选任务，补齐专辑、歌手和封面。
- 该任务仅由用户可见的歌词请求触发；后台元数据开关关闭时仍只处理当前歌曲，不启动全库抓取。

# 2026-09-02 歌词 no_match 状态修复

- `/api/lyrics` 不再把已完成但无匹配的 provider 任务误报为 `pending`，避免界面永久显示“正在获取歌词”。
- 歌词界面对 `no_match` 显示明确提示，并允许用户重新打开页面走显式重试；失败与无匹配状态继续分开保留。
- 补正 `no_match` 的 SQL 复位条件：陈旧恢复和显式重试均实际更新 `failed/no_match` 终态；新增单曲回归覆盖终态返回与重试重新入队。

# 2026-09-02 元数据补全判定模块化

- 将曲目是否需要 provider 补全的无状态判定抽至 `metadata_track_enrichment_policy.py`，`MetadataService` 保留兼容静态入口。
- 增加完整 Tag、文件名/占位字段及损坏输入回归，便于后续独立维护元数据任务边界。

# 2026-09-02 首屏封面 eager 突发收敛

- 封面调度器在 IntersectionObserver 首次回调前，立即启动首屏前 8 张封面，避免旧 WebView 的异步观察回调造成首屏空白一拍。
- 其余歌曲仍保持 32 并发上限、4096 队列上限和可取消懒加载；Node 调度回归已更新并通过。

# 2026-09-02 元数据缓存结果容错

- `track_match` 对损坏的候选 JSON、非法置信度和异常时间字段执行安全投影，不再因单条缓存损坏导致元数据接口 500。
- 增加损坏缓存回归；provider 任务和已有 Tag 优先级保持不变。

# 2026-09-02 元数据策略异常值隔离

- 封面引用与 Tag 来源判定仅接受有界文本，拒绝对数字、数组或其他异常 JSON 值执行任意 `str()` 转换。
- 新增非文本输入回归，避免损坏元数据造成误命中、资源放大或首屏状态抖动；未进行真实设备验收。

# 2026-09-02 陈旧 no_match 元数据恢复

- provider 返回空候选后，`no_match` 不再永久阻断用户后续获取；超过 15 分钟冷却的用户可见歌词/候选请求会有界恢复为 `pending`。
- 普通状态轮询仍返回终态，保留负缓存保护，避免网络异常时形成紧密重试循环。

# 2026-09-02 首屏空响应防闪烁

- 已有本地首屏快照时，普通网络请求若暂时返回空页，不立即清空可见歌曲，而是执行一次 250ms 后的有界重试。
- 显式刷新仍尊重服务端空结果；新增独立前端策略回归并通过完整离线门禁。

# 2026-09-02 首屏重试绕过空缓存

- 首屏空响应保护的 follow-up 请求现在会先移除对应 LRU 空页，确保重试实际触达服务端。
- 保留一次性 guard 和显式刷新语义，避免缓存空响应造成二次闪烁或假恢复。

# 2026-09-02 首屏空响应策略范围收敛

- 空页保护仅作用于已有快照的普通分页歌曲列表；分组、文件夹和显式刷新不使用该回退，避免旧快照掩盖真实状态。

# 2026-09-02 首屏重试视图竞态修复

- 延迟重试现在校验分页请求键与当前视图，用户切换搜索或分类后旧定时器不会误加载上一页。
- 切换视图会同步取消一次性快照保护标记；前端回归与完整离线门禁通过。

# 2026-09-02 大曲库首屏保护复测

- 使用 100,000 首合成曲库复测分页和缓存：第一页冷读约 46.2ms、热缓存约 0.57ms，尾页约 128.7ms；FTS trigram 搜索相对 LIKE 约 16.3 倍。
- 结果归档于 `artifacts/large-library-benchmark-20260902-empty-response-guard.json`；该数据仅表示本机离线趋势。

# 2026-09-02 元数据 provider 总等待预算

- 新增 `metadata_request_budget.py`，将 provider 链的总时限从服务代码拆为纯策略：歌词任务最多 12 秒，其他元数据任务最多 15 秒。
- 每次外部请求使用剩余预算的有界 timeout；预算耗尽后保留可重试失败而非长期占用 worker。线程任务结束会清理 deadline，避免影响后续歌曲。
## 2026-09-02 持续目标：当前歌曲元数据回退与首屏稳定性

- 修复完整 Tag 歌曲没有封面时不会进入单曲候选链的问题；播放当前歌曲现在会优先请求候选并缓存封面，同时不改变后台全库补全默认关闭语义。
- provider 歌词/候选链改为隔离单个适配器的异常 schema，记录受限失败诊断后继续后续来源，避免单一数据源异常被表现为“无法获取元数据”。
- 新增对应 Python 回归；本轮仅进行离线验证，不替代真实设备、DAC/DSD、DLNA/AirPlay 或 App Center 验收。

## 2026-09-01 首屏普通刷新去重

- 播放状态和状态轮询导致的普通渲染现在只写入实际变化的排序方向、设备标签、循环/随机状态、计数及视图标题；排序键不再每次 render 同步写 localStorage。
- 导航 active 状态按当前视图缓存，循环 SVG 仅在循环模式实际改变时替换，减少旧 WebView 的样式失效、重排及歌曲列表“加载后闪一下”。
- 完整离线门禁 1053 项测试通过；未打包、未部署、未进行真实设备验收。

## 2026-09-01 单根目录加载链修复

- 修复文件夹视图仅发现一个音乐库根目录时的异步自引用：旧逻辑会在同一加载键下重新进入公共去重入口，可能返回并等待正在执行的原始 Promise。
- 自动进入单根目录现直接衔接下一阶段 worker，保留请求序列、取消和公共调用方等待语义，避免目录歌曲页停留在加载状态。
- 新增前端加载器回归；完整离线门禁 1053 项测试通过，未打包、未部署、未进行真实设备验收。

## 2026-09-01 元数据匹配独立回投

- 修复列表元数据回投仅从 `metadata_tracks` 起始的问题：候选已自动确认、但尚未获得歌词或封面时，专辑/歌手等结果此前不会显示。
- 现由当前页请求 ID 驱动单次 LEFT JOIN，同时读取匹配、歌词和封面缓存；真实 Tag 优先级与单页查询次数不变。
- 增加“只有匹配缓存”回归；完整离线门禁 1053 项测试通过，未打包、未部署、未进行真实设备验收。

## 2026-09-01 首屏歌词载荷收敛

- 公共 `/api/library` 曲目投影不再输出每首缓存歌词正文、原始 `item_json` 和内部 metadata artwork ID；封面继续以公共 URL 返回，字段来源信息仍保留给歌曲详情使用。
- 歌词统一从当前歌曲的 `/api/lyrics` 按需读取，避免缓存 LRC 较多时把首屏分页响应、JSON 解析和旧 WebView 首绘放大。
- 公共投影专项回归和完整离线门禁均通过：1054 项测试；未打包、未部署、未进行真实设备验收。

## 2026-09-01 元数据页字段投影边界拆分

- 新增 `metadata_track_page_overlay.py` 纯模块，集中处理候选 JSON 的字段白名单、NUL 清理和 4096 字符边界。
- 列表回投不再任意字符串化异常候选值，损坏数组/对象不会进入首屏歌曲字段或放大响应；真实 Tag 优先级保持不变。
- 专项回归与完整离线门禁均通过：1054 项测试；未打包、未部署、未进行真实设备验收。

## 2026-09-01 扫描状态装饰写入去重

- 扫描状态轮询不再无条件重写计数、服务端口、空状态和进度文案；新增共享 `setTextContentIfChanged`，值未变化时跳过 DOM 写入。
- 减少状态刷新对旧 WebView 的无效重排，歌曲列表和扫描语义保持不变；完整离线门禁 1058 项测试通过。
# 2026-09-02 首屏封面与元数据回退续优化

- 修复歌曲行有本地封面时“♫”占位符先闪现一帧的问题；图片失败仍会恢复统一音乐符号。
- 扩展歌词任务的封面回退链：网易云/QQ 无结果时，受限复用曲目候选结果，支持从酷狗、咪咕、JOOX、千千等来源补取封面。
- 新增 `test_track_artwork_falls_back_to_supported_candidate_sources` 回归；更新源码清单，完整离线门禁 1059 项通过。

# 2026-09-02 元数据 provider 候选逐条容错

- 修复第三方搜索响应中单条异常候选导致整个 provider 失败、进入冷却并表现为“无法获取元数据”的问题。
- 现在候选映射逐条隔离：坏记录被安全跳过，后续有效记录继续参与标题/歌手评分与封面补全；新增混合损坏/有效 NetEase 回归。
- 本轮未进行真实设备、DAC/DSD、DLNA/AirPlay 或 App Center 验收；provider smoke 仅作为外部网络诊断证据。

# 2026-09-02 元数据查询词去占位

- provider 歌曲搜索统一经过纯策略模块，忽略“未知歌手/未知艺术家”等占位字段并限制查询文本长度。
- 文件名解析出的占位歌手不再作为真实检索条件，降低在线元数据误判为无匹配的概率；新增独立回归。

# 2026-09-02 大曲库性能复测

- 100,000 首合成曲库：首屏约 53ms、尾页约 154ms，重复页缓存约 56 倍加速，元数据页回投约 4ms，FTS 搜索约为 LIKE 的 17.6 倍。
- 结果归档至 `artifacts/large-library-benchmark-20260902-latest.json`；仅为离线趋势证据，未进行真实设备或 App Center 验收。

# 2026-09-02 provider 艺术家字段安全投影

- provider 返回异常艺术家对象时不再执行任意字符串转换；列表遍历限制为 8 项，并在坏条目后继续寻找有效文本。
- 保持原有首位艺术家匹配逻辑，避免单个损坏字段令歌曲、专辑或歌词回退链整体失败。
# 2026-09-02 曲目候选查询链统一

- 修复曲目候选仍使用原始 `title + artist` 查询的问题，统一改用 `track_search_query()`。
- 未知歌手/未知专辑等占位值不再污染 provider 查询；非文本字段不会被任意 `str()` 转换。
- 新增 `test_track_candidates_use_bounded_query_policy` 回归；待执行完整离线门禁。

## 2026-09-02 — provider 艺术家字段容错

- 咪咕、JOOX、千千适配器不再直接字符串化艺术家对象。
- 新增有界去重的艺术家投影；单个 malformed 条目不会中断剩余候选或后续 provider 回退。
- 新增异常 schema 回归。

## 2026-09-02 — 元数据文件名回退检索

- 扫描结果缺少有效标题时，provider 查询从安全的文件名（去除扩展名）获取检索词。
- 仅作为查询提示，不覆盖真实 Tag 或列表展示；新增标题缺失与真实标题优先回归。

## 2026-09-02 — 实体元数据查询收敛

- 专辑/实体 provider 查询统一复用有界、去占位字段的查询策略。
- 空查询在网络请求前直接短路，减少无效请求和 provider 异常噪声。
- 保持既有 provider 顺序、评分阈值和后台开关语义不变。

## 2026-09-02 — provider JSONP 兼容

- 元数据 JSON 解码兼容受限的 `callback({...})`/JSONP 响应，避免上游偶发包装导致所有候选被判为失败。
- 仅解析标识符形式 callback 内的 JSON，不执行脚本；异常形状继续进入失败诊断。

## 2026-09-02 — provider 路由字段安全化

- `contains_cjk()` 仅接受有界文本字段，非文本异常不会在 provider 选择阶段触发字符串化异常。
- 正常中英文 provider 路由顺序保持不变；新增异常字段回归。

## 2026-09-02 — provider 路由策略模块化

- 新增 `metadata_provider_routing_policy.py`，将 CJK 路由判断从服务层拆出为可独立测试的纯策略。
- 服务层保留现有 provider 排序，新增模块回归覆盖正常与异常字段。

## 2026-09-02 — provider 文本字段容错

- 咪咕/JOOX 专辑名和封面字段统一进行有界文本投影，拒绝异常对象并清理 NUL。
- 单个损坏字段不再让整个 provider 候选任务失败。

## 2026-09-02 — MusicBrainz 曲目候选回退

- 将 MusicBrainz recording 搜索接入曲目候选链，补充国际歌曲和中文数据源未命中时的专辑/歌手候选。
- 保持候选上限、评分阈值、请求预算和失败隔离策略不变；新增曲目回退回归。

## 2026-09-02 — 首屏封面绘制隔离

- 歌曲行封面容器增加 `contain: strict`，异步图片解码和失败回退不会牵连整行布局。
- 保持封面懒加载、尺寸和音乐符号回退语义不变；仅作离线 UI 回归验证。
## 2026-09-02

- 修复浏览器播放选中歌曲时元数据任务未及时提权的问题：播放队列保存现在会同步提升当前歌曲的歌词、封面和候选补全任务；元数据异常被隔离，不影响队列保存。
- 增加播放队列与元数据优先级接线的离线回归测试。
# 2026-09-02 — 曲目候选失败恢复

- 修复 provider 临时故障后的曲目候选被 `failed` 状态卡住的问题。
- “重新查询此歌曲”现在会有界重置 `failed` 与 `no_match`，并重新进入单曲优先队列；新增离线回归。
# 2026-09-02 — 首屏状态轮询并行化

- 音乐库状态与元数据状态改为并行请求，避免元数据聚合延迟拖慢扫描进度和首屏状态更新。
- 保持原有变更签名、缓存失效和列表刷新条件不变。
# 2026-09-02 — 实体元数据落库容错

- 专辑、歌手实体落库改用有界文本投影，异常 provider 字段不再触发字符串化或 JSON 序列化异常。
- 置信度异常值（含 NaN、溢出和对象）安全降级为 0。
- 损坏字段按字段隔离并保留后续回退链；新增离线回归。
# 2026-09-02 — 首屏状态并行契约

- 增加 UI 静态回归，锁定音乐库和元数据状态刷新采用并行请求，防止后续重构回退为串行等待。
- 修正并行实现的隐性等待：音乐库状态响应现在先行提交，元数据快照独立合并。
# 2026-09-02 — provider 非对象结果隔离

- 元数据落库入口现在安全处理列表、字符串等非对象响应，避免直接 `.get()` 引发 worker 失败。
- 新增歌词与封面异常结果回归，正常 provider 链路不变。
# 2026-09-02 — 元数据字段级安全写入

- 歌词和封面缓存写入前统一限制正文、来源、provider ID 与置信度，异常字段按字段降级。
- provider 返回部分损坏时仍可保留有效缓存并继续后续回退。
# 2026-09-02 — 曲目候选置信度容错

- 曲目候选落库不再直接转换异常置信度；非法数值按 0 处理，保留候选与后续人工确认路径。
- 持久化前规范化候选 JSON，避免异常评分对象在序列化阶段中断任务。
- 新增异常置信度离线回归。
# 2026-09-02 — 候选来源字段安全落库

- 曲目候选自动匹配写入缓存时，source 与 provider ID 统一采用有界文本投影。
- 异常字段不会再在 SQLite 写入前触发字符串化错误。
# 2026-09-02 — 100k 曲库性能复测

- 100,000 首合成曲库复测保持有界分页和元数据回投；热页缓存约 67.2 倍加速，FTS5 trigram 相对 LIKE 约 17.8 倍。
- 证据归档至 `artifacts/large-library-benchmark-20260902-followup.json`。
# 2026-09-02 — 元数据数值策略模块化

- 新增 `metadata_numeric_policy.py`，统一处理 provider 置信度的有限数值投影。
- 实体、歌词、封面和曲目候选落库路径复用同一策略，新增独立回归。
# 2026-09-03

- 修复播放即触发的单曲元数据预取在网络瞬断时直接静默失败的问题；网络异常与元数据服务 5xx 统一进入有限重试，最多 8 次且可被切歌取消。
- 保持后台元数据补全默认关闭，不扩大全库扫描范围；本次仅改善当前播放歌曲的歌词、封面和候选信息恢复速度。
- 对“有候选但无自动 best”的响应增加当前行展示回退，避免元数据实际已获取却在 UI 中显示为空。
# 2026-09-03 当前歌曲元数据恢复链路

- 修复前端仅识别 `pending: true` 而漏掉 `status: "pending"` 的协议差异；已入队的元数据任务会继续进行有界重试。
- 服务端待处理响应补充显式 `pending: true`，保持协议语义向后兼容。
- 会话冷启动恢复后主动触发当前歌曲元数据预取，避免恢复播放状态后歌词、封面和候选信息长期停留为空。

# 2026-09-03 首屏缓存竞态与元数据 unavailable 恢复

- 分页响应缓存写入增加 epoch 校验，旧 refresh 响应不再覆盖较新的缓存状态，降低首屏歌曲列表重复替换和封面闪烁。
- 当前播放歌曲元数据预取对暂时不可用的 worker、HTTP 5xx、网络异常及 pending 状态执行有界重试；切歌 token 仍阻止旧歌曲响应污染当前页面。
- 若当前歌曲首次得到短暂 `failed/no_match`，后续重试会携带显式恢复参数，让服务端重新排队而不是重复返回旧终态。
- 快照恢复现在拒绝空 `items`，避免旧 WebView 冷启动先显示空列表后再替换为真实歌曲页。
- 快照恢复在解析前增加 384 KiB 长度门禁，超大旧缓存直接丢弃，避免异常 localStorage 阻塞首屏。
- 扫描状态轮询增加 in-flight 去重，慢 NAS 上不会因 1 秒扫描轮询与常规刷新重叠而重复处理状态响应。
- 分页响应加载器现在在达到并发上限时显式拒绝请求，修正“请求实际发起但未进入 in-flight 统计”的资源上限漏洞。
- 普通分页与显式 refresh 统一纳入 active 并发计数，刷新请求不再绕过资源上限。
- 元数据可用性判断按歌词/曲目候选 lane 隔离，优先歌词 worker 存活时不会因普通抓取池降级而误报歌词服务不可用。
- 新增缓存乱序、锁定刷新 epoch 与 unavailable 重试回归；完整离线门禁通过，未进行真实设备或外部 provider 验收。
# 2026-09-03 元数据 worker 懒恢复

- `/api/metadata/track` 与歌词接口在检测到 worker 池退出时，先执行一次带生命周期锁的受限恢复，再返回不可用状态。
- 恢复逻辑按 lane 复用现有线程池，不重复创建健康线程；新增 HTTP 回归覆盖恢复与兼容旧服务对象。
# 2026-09-03 provider 候选回退回归

- 补充曲目候选主链的行为级回归：首个来源缺少封面时仍会调用后续 provider，完整高置信候选则保持提前停止，降低当前歌曲元数据等待和封面缺失风险。
- 仅使用离线 mock 验证调用顺序；外部 provider 实际可用性仍需独立网络验收。
# 2026-09-03 元数据候选完整度修复

- 去重同曲目候选时先比较字段完整度，再比较 provider 置信度；后续来源补到封面时不会再被首个无封面结果覆盖。
- 增加纯策略回归，保持请求预算与 provider 顺序不变。
# 2026-09-03 元数据封面端到端回归

- 增加离线链路测试，锁定候选封面从 worker 下载、写入 `metadata_tracks` 到曲目页投影的完整路径，避免出现后台成功但 UI 仍空白。
# 2026-09-03 前端封面 URL 容错

- 歌曲列表封面地址解析增加异常隔离，损坏 URL 仅影响对应歌曲并显示统一音乐符号，不再造成整页闪烁或渲染中断。
# 2026-09-03 元数据空 best 回退

- 修复前端将空 `best` 对象误判为有效元数据的情况；现在会使用有界候选首项更新当前歌曲，并保持本地 Tag 优先。
# 2026-09-03 分组封面 URL 容错

- 专辑与分组封面在线回退增加异常 URL 隔离，单个坏地址不会打断整页渲染；保持后续元数据刷新可恢复。
# 2026-09-03 当前歌曲元数据冷却重武装

- 当前歌曲预取在 8 次失败/无匹配重试后等待 30 秒，并对同一曲目最多重武装 2 轮；切歌会重置计数，避免 provider 短暂故障后永久不再获取元数据。
- 新增 UI 静态回归锁定冷却、重武装上限与定时器行为；未进行真实设备或外部 provider 验收。
# 2026-09-03 队列分页重复遍历收敛

- 队列分页和当前播放定位复用同一份有界展示缓存，避免同一轮渲染重复执行搜索过滤与排序。
- 缓存按队列数组身份、搜索词、排序键和方向失效；新增回归保持原有队列顺序与分页语义。
# 2026-09-03 前端筛选排序重复计算收敛

- `filteredTracks()` 增加按输入引用和视图条件失效的单项 memo，减少大曲库普通库/收藏/歌单渲染中的重复过滤排序。
- 新增 UI 静态回归锁定缓存边界和失效条件；未进行真实设备或外部 provider 验收。
# 2026-09-03 元数据封面地址写入校验

- 歌词和曲目候选回投现在只接受有界 HTTP/HTTPS 封面地址；异常 provider 值不会写入当前歌曲对象，后续有效候选仍可恢复封面。
- 新增 UI 静态回归，未进行真实设备或外部网络验收。
# 2026-09-03 元数据回投筛选缓存一致性

- 歌词/候选元数据原地回投时清理前端筛选 memo，搜索与排序立即反映新字段，避免缓存旧投影。
- 新增静态回归验证失效路径；未进行真实设备验收。
# 2026-09-03 provider gzip 增量解压边界

- 元数据 provider 的 JSON 与歌词响应改为增量 gzip 解压，输出超过对应大小预算时提前终止，降低压缩响应导致的内存峰值。
- 新增正常/超限回归，完整离线门禁通过。
# 2026-09-03 持续目标复核

- 完成无需真机的首屏/元数据专项复核，完整离线门禁通过 1130 项。
- 确认咪咕搜索、资源详情链路使用 HTTPS；显式当前歌曲元数据请求不受后台全库补全开关阻断。
- 保留真实 WebView、手机和音频输出设备验收为后续观察项，未将离线结果冒充真机结论。

# 2026-09-03 当前歌曲歌词预取

- 播放开始或会话恢复时，当前歌曲会触发一次按曲目去重的歌词预取；歌词页可复用已返回内容，降低首屏空歌词等待。
- 旧歌曲响应会被 token 丢弃，不影响切歌后的当前状态；未改变后台全库补全和 Tag 写回默认关闭策略。

# 2026-09-03 启动封面预热降竞争

- 移除启动时为缩略图预热而进行的整库 SQLite 物化，首个分页请求不再与全库预热竞争资源。
- 保留可见页按需加载和扫描完成后的有界预热队列。

# 2026-09-04 元数据交互等待窗口

- 当前歌曲元数据预取与候选窗口统一为最多 12 次有限轮询，改善慢 provider/NAS 下结果刚完成就被前端冷却的问题。
- 仍保留曲目 token、次数上限和冷却机制，避免后台请求失控。

# 2026-09-04 元数据轮询门禁修正

- 同步更新歌词优先级回归断言，确保新的显式 12 次预算不会被旧测试契约误报失败。
- 最终离线门禁：1130 项测试通过。

# 2026-09-04 播放歌词 pending 回投

- 播放开始时的歌词预取新增 pending/临时错误重试，最多 12 次，避免后台任务刚入队时被一次空响应终止。
- 成功歌词会回投当前歌曲对象与有界缓存，旧曲目响应仍由 token 隔离。

# 2026-09-04 元数据空成功投影恢复

- 服务端识别并修复 `review/auto` 状态但没有可用 `best/candidates` 的历史元数据行，重新排入有界优先队列，避免等待长 TTL 才恢复。
- 当前歌曲前端预取把空的 `review/auto` 投影视为可恢复状态，继续有限重试；未改变正常候选、`no_match` 或服务不可用的边界。
- 已通过元数据专项回归和 UI 静态回归；真实设备与第三方 provider 稳定性仍待部署环境观察。

# 2026-09-04 MusicBrainz 回退延迟收敛

- 为 MusicBrainz recording/release-group 请求增加独立 4 秒超时，公共接口异常时更快让后续 provider 回退。
- 保留现有总任务预算、失败观测与候选排序语义。

# 2026-09-04 列表跨页键控复用

- 列表提交扩展为跨页、搜索结果增减和排序变更时的稳定 key 节点移动；同一曲目的解码封面和图片请求不会因整表 `innerHTML` 重建而丢失。
- 新结果已不存在的旧行会移除；无稳定 key 的复杂视图继续使用安全全量回退。

# 2026-09-04 键控列表性能收敛

- 将键控提交的 key 唯一性判断从逐行 `indexOf` 改为 `Set`，降低大页搜索、排序和元数据校正中的主线程检查开销。
- 当前网络 smoke 下 MusicBrainz 国际候选链约 1 秒完成；仅记录当前环境证据，不视为第三方服务 SLA。

# 2026-09-04 元数据状态更新时间指纹

- 元数据状态增加 `metadata_updated_at`，前端投影签名据此识别“数量不变但任务已更新”的结果，及时刷新列表中的封面和补全字段。
- 保持状态响应有界、脱敏，不暴露曲目路径或 provider 原始数据。

# 2026-09-04 元数据投影单调修订号

- 增加 `metadata_projection_revision`，避免多个元数据任务在同一秒完成时仅凭 `updated_at` 无法区分更新。
- 前端签名使用该 revision 触发一次合并刷新，仍保持有界、低开销和脱敏。

# 2026-09-04 元数据状态刷新去噪

- 排队、领取和 retry 过程不再触发元数据投影 revision；终态更新时间指纹与实际落库变化保持一致，减少无意义列表刷新。
- 修正入队与曲目候选持久化的 revision 标记：前者仅刷新状态，后者才触发列表元数据校正。

# 2026-09-04 封面版本缓存正确性复核

- 未采用媒体 `stat` TTL 缓存，以避免 CUE/标签同秒变更被旧版本遮蔽；保留现有实时版本指纹和失效语义。

# 2026-09-04 稳定列表提交去重

- 当键控列表内容、数量和顺序均未改变时跳过 `DocumentFragment` 节点搬运，仅在真实增删、重排或行替换时提交片段，降低旧 WebView 的布局与绘制抖动。
## 2026-09-04 元数据缓存优先响应

- 曲目元数据接口先返回已有 SQLite 投影，再对 pending/新任务执行 worker 可用性检查，避免 worker 短暂重启导致前端误显示“无法获取元数据”。
- 完整离线门禁 1136 项通过；不替代真实 provider 网络和设备验收。
# 2026-09-04

## 元数据交互恢复窗口

- 将 `metadata_retry_policy` 的用户可见失败/无匹配恢复窗口调整为 60 秒，避免临时 provider 故障让当前歌曲长时间停留在无元数据状态。
- 该改动不改变后台元数据默认关闭和全库扫描节奏；已通过离线回归，真实设备验收仍待进行。

## 播放歌词预取同步封面

- 歌词预取响应中的合法封面现在会与歌词一起回投当前歌曲缓存，并复用元数据行的合帧刷新，避免必须打开歌词页才看到封面。
- 保留本地 Tag 封面权威优先级；增加 UI 静态回归。

## 嵌入歌词与封面恢复

- 已有嵌入歌词的歌曲，只要缺少封面仍会触发优先元数据请求，避免歌词字段存在导致封面恢复被跳过。

## 歌词预取渲染状态修复

- 修复歌词页打开期间预取回投缺少 `renderLyrics` 参数导致歌词数组被覆盖的问题；现在直接渲染已解析数组。

## 歌词终态有限恢复

- 歌词预取遇到无正文的 `failed/no_match` 结果时，改为使用有界显式重试，提升短暂 provider 异常后的恢复能力。

## 本地歌词探测缓存

- 为嵌入歌词与同名 LRC 探测增加按文件身份失效的 256 条 LRU，减少 pending 轮询期间重复 ffprobe/文件读取。
- 增加专用锁，避免并发歌词请求破坏缓存顺序或重复执行探测。
# 2026-09-04 元数据 worker 启动竞态收敛

- 元数据服务懒恢复后增加最多 3 次、每次 20ms 的本地存活确认，避免 worker 刚启动尚未调度时把可恢复请求误报为 503。
- 新增 HTTP 集成回归覆盖启动竞态；未进行真实设备、DAC、DSD、DLNA、AirPlay 或 App Center 验收。
# 元数据查询消歧

- 曲目查询在专辑已知且非占位时将其加入 provider 搜索提示，降低同名歌曲误匹配并帮助补齐缺失字段；占位值仍会被过滤。
- 新增查询策略回归，未进行真实设备或外部 provider 长期稳定性验收。
# 元数据旧负缓存恢复

- 旧版本仅保存候选负结果、未保存对应任务行时，不再永久阻断元数据请求；达到 60 秒冷却后会重建优先任务。
- 新增回归覆盖旧缓存恢复，未进行真实设备或外部 provider 长期稳定性验收。
# 2026-09-04 首屏状态让路与元数据恢复标记

- 将 `api/library/status` 从首屏分页提交同一事件循环中移出，延迟 120ms，并随新请求取消旧状态定时器，降低大曲库首屏二次布局和封面闪烁。
- `MetadataService.track_match()` 对 `failed/no_match` 终态显式返回 `retryable: true`；歌词终态同步标记，便于客户端识别“可恢复失败”而非永久无元数据。
- 已补充 UI/服务回归；未进行真实设备、DAC、DSD、DLNA、AirPlay 或 App Center 验收。

- 页面卸载/隐藏时取消尚未执行的首屏状态聚合定时器，避免后台 WebView 生命周期结束时额外触发库统计请求。
- 本地目录封面探测支持常见 `front/album/artwork` 和 WebP 文件名，保持固定优先级、路径约束与读取上限，减少不必要的外部元数据等待。
- 收藏、播放列表和恢复队列的 `/api/library/items` hydration 统一复用 SQLite 元数据投影；投影异常时仍返回原始曲目，避免封面和专辑字段出现二次闪现。
# 2026-09-04 元数据 pending 响应稳定性

- 曲目/歌词已有排队任务但 worker 短暂不可见时，接口保留 `pending: true` 并返回 HTTP 200，同时标记 `retryable: true`，避免把可恢复状态显示成“元数据服务不可用”。
- 增加 HTTP 集成回归；完整离线门禁 1148 项通过，未进行真实设备或第三方 provider 长期稳定性验收。
# 2026-09-04 元数据查询映射兼容

- `metadata_query_policy.track_search_query()` 支持 `sqlite3.Row`，修复部分服务路径中字段存在但 provider 查询为空的静默失败风险。
- 保留有界文本、占位词过滤和文件名回退；新增回归并通过完整离线门禁。

# 2026-09-04 大曲库离线复测

- 重新运行 100,000 首曲库基准：总查询 0.338 秒、尾页 0.170 秒，热页缓存约 57.6 倍、FTS 相对 LIKE 约 17.9 倍。
- 结果保存至 `artifacts/large-library-benchmark-20260904-followup.json`，不替代旧 WebView 或真实设备验收。

# 2026-09-04 provider 输入行兼容

- provider 入口统一兼容受限 `sqlite3.Row`，在适配器调用前转换为安全字段字典，避免标题/歌手已存在却因 `.get()` 不兼容导致查询链失败。
- 新增 MetadataProviders 回归，完整离线门禁通过。

# 2026-09-03 首屏空状态绘制收敛

- 首次请求开始时立即收敛静态“没有找到音乐”空状态，避免无快照冷启动在歌曲列表到达前出现一帧空库闪烁；已有列表保持原 DOM 不变。
- 增加 UI 回归，未进行真实 WebView 或设备验收。

# 2026-09-03 访问模式探测让路首屏

- 将非关键的 `api/access` 模式探测延迟到首屏绘制之后，分页切换时取消旧探测；保持 10 秒缓存和 in-flight 去重语义。
- 通过 UI 回归与完整离线门禁，未进行真实设备验收。
# 2026-09-04 首屏冷启动提交优化

- 冷启动首个音乐库请求不再触发完整空列表渲染；仅隐藏静态空状态并更新轻量状态装饰，避免旧 WebView 先绘制空列表、随后替换为歌曲列表造成闪烁和封面重复加载。
- 整理 `MetadataProviders.track_candidates` 的 docstring 与输入规范化顺序，未改变 provider 回退、缓存或失败隔离策略。

# 2026-09-04 provider 只读烟测记录

- 对固定中文样例执行有时限只读 provider 请求：QQ 封面、网易云歌词和 QQ 歌词返回有效结果；网易云封面本次无匹配但未出现异常，provider 失败计数为空。
- 仅作为当前网络环境的诊断证据，不代表第三方来源长期可用性；未启用后台全库补全或 Tag 写回。

# 2026-09-04 大曲库第二次复测

- 100,000 首合成曲库：总分页查询 0.333 秒、尾页 0.169 秒、热页缓存约 61.6 倍、FTS5 trigram 相对 LIKE 约 17.6 倍。
- 证据文件：`artifacts/large-library-benchmark-20260904-followup2.json`；仅用于离线趋势比较，不宣称真实设备绘制完成。

# 2026-09-04 元数据重复提交去噪

- 相同歌词/封面重复写入只更新 TTL，不再推进 `metadata_projection_revision`；避免轮询导致前端无意义列表校正和封面重绘。
- 新增重复提交回归，字段真正变化时仍会正常触发投影更新。

# 2026-09-04 实体与候选投影去噪

- 专辑实体、曲目候选的重复落库不再推进元数据投影修订号，仅实际内容变化才触发前端校正。
- 新增实体/候选重复提交回归，降低大曲库 hydration 和封面调度噪声。

# 2026-09-04 候选缓存规范化

- 曲目候选以稳定键顺序写入缓存，等价 provider 对象仅键顺序变化时不再触发元数据投影修订和列表刷新。
# 2026-09-04 元数据交互降级

- 元数据 worker 短暂不可用时，曲目接口不再直接返回 503 空结果；改为返回本地 Tag 字段的 `pending/retryable` 展示投影，歌词接口同样返回可自动重试的 pending 状态，减少“无法获取元数据”误报和首屏信息消失。
# 2026-09-04 懒加载封面占位稳定性

- 修复首屏外懒加载歌曲行在图片开始解码前隐藏音乐符号、短暂显示空白封面块的问题；现在保持占位符直到图片成功加载，失败时继续回退音乐符号。
# 2026-09-04 元数据降级策略模块化

- 将 worker 暂时不可用时的本地字段投影与 `retryable pending` 响应抽为独立纯策略模块，并增加异常输入与字段边界回归，降低 HTTP 编排复杂度。
- 歌词 worker 的暂不可用响应也改为复用统一策略，减少重复协议构造并保持曲目/歌词恢复语义一致。
- 首屏元数据预取现在只接受字符串/数字歌曲 ID，并在每页内去重，避免重复 provider 请求及异常 ID URL。
- 本地嵌入歌词命中时若歌曲缺少封面，歌词快路径会继续排入单曲候选任务，避免“歌词已显示但封面永远不补全”。
# 2026-09-05 无真机元数据恢复与首屏稳定性

- 首屏的可见非当前行元数据预取新增 750ms 绘制静默窗口，随后才进入有界 idle 调度，避免旧 WebView 将可选 provider 请求与列表首个提交、封面解码竞争；当前正在播放曲目的优先元数据/歌词通道不延迟。
- 预取生命周期现在明确区分 timeout 与 idle callback，切换页面或隐藏页面时可准确取消，避免旧页的补全请求回投到新页。
- 修正可见预取候选遗漏：标题为空但其他 Tag 已存在的歌曲现在也会进入 provider 查询；新增 Node 策略回归。
- 统一可见元数据预取策略默认重试预算为 12 次，并对异常/对象型字段采用安全缺失语义，避免 provider 任务被过早停止或被损坏字段阻断。
- 可见预取对歌曲 ID getter 增加异常隔离和长度限制，单条损坏列表行不会阻断后续元数据获取。

- 修复元数据任务“已 pending 但 worker 已退出”时的恢复缺口：曲目和歌词接口保留 HTTP 200 `pending/retryable` 协议，同时会触发一次对应 worker lane 的有界懒恢复，避免任务长期不执行。
- 保持后台全库补全默认关闭；新增回归确认用户显式请求的单曲元数据仍可通过优先队列获取。
- 可见首屏元数据预取保持 6 首上限、双并发和可取消，慢 provider 的轮询预算调整为最多 12 次、每次 700ms；非当前行回填改为 180ms 合并，减少连续列表 patch 造成的闪烁。
- 修复客户端分页按钮的未定义 `trackId` 回调引用。
- 增加 provider 响应解码回归：错误 latin-1 charset 不再破坏中文结果，仅接受受限 JSONP 包装，任意脚本响应仍被拒绝。
- 修正首屏可见元数据预取的实际重试上限：策略调用从遗留的 4 次改为 12 次，与 700ms 轮询调度一致，慢 provider 不会在第 4 次前被提前放弃。
- 补齐首屏预取失败计数：非取消网络/解析异常现在进入有界失败指标，页面切换取消不会污染 provider 失败统计。
- 完整离线门禁通过：1043 项 Python 测试及全部 Node UI 回归；未进行真实设备、DAC/DSD/DLNA/AirPlay、fnOS App Center 或 Android 多机型验收。

# 2026-09-04 首屏 eager 封面调度收敛

- 修复首批 eager 封面的调度归属：已由 HTML `src` 触发加载的图片会保留稳定声明地址，但不再进入懒加载 scheduler。这样不会把浏览器自身的请求误报为队列任务，也不会在后续 keyed 增量提交时重复 hydration。
- 封面调度器兼容旧 WebView 的 array-like NodeList；新增 eager/lazy 混合页面回归，确认只观察尚未加载的图片。
- 同步队列列表回归：eager 图片在 `onload` 前保持音乐符号占位，避免测试契约与当前防闪烁设计相互冲突。

# 2026-09-05 — 元数据全损坏候选恢复

- provider 搜索若返回非空列表但所有映射候选均含 Unicode 替换字符，现在会被判为可恢复的数据源异常，而非有效的空搜索结果。
- 该修复会继续执行后备 provider，并让最终失败保持 retryable，避免短暂编码故障将当前歌曲长期写成 `no_match`；新增回归覆盖。

# 2026-09-04 — 元数据数据源到达诊断

- 元数据状态和支持诊断新增 provider 成功到达摘要：仅记录受限成功次数与距上次成功秒数，可和既有失败/冷却摘要共同判断网络、TLS、空匹配或损坏 payload 的差异。
- 摘要不输出歌曲名、搜索词、路径、URL 或原始响应；新增纯投影、诊断和服务回归。

# 2026-09-05 — 大曲库分页与缓存复测

- 使用 10,000 首合成曲库和 120 首分页重新验证首/中/尾页、页面缓存、元数据 overlay、项目补水、分类浏览和 FTS 搜索趋势。
- 本机结果：分页热缓存约 14.0 倍、metadata overlay 热读约 3.29 倍、FTS5 trigram 相对 LIKE 约 4.14 倍；完整数据位于 `artifacts/large-library-benchmark-20260905-refresh.json`，不作为 NAS 或 WebView 的性能承诺。
# 2026-09-05 provider 诊断容量收敛

- 为 provider 成功、失败与冷却诊断增加统一 32 项内部上限，异常适配器名称漂移不会造成长期无界增长。
- 淘汰最久未观测记录时同步删除冷却状态；对外快照结构与 16 项输出上限保持兼容。
- 新增回归覆盖失败/成功混合写入、旧项淘汰、冷却清理和最近 provider 保留。
# 2026-09-05 元数据轮询队列公平性

- 修复当前歌曲、歌词页和可见列表重复轮询会反复刷新活动 metadata job 的问题。
- pending/retry/running 任务现在保留状态、attempts、next_attempt_at、updated_at 与错误信息，仅允许交互请求降低优先级数值。
- 增加 track、lyrics 轮询和底层 upsert 回归，避免大曲库并发预取造成旧任务饥饿。
# 2026-09-05 歌词请求生命周期收敛

- 歌词页主请求改用统一 `fetchMetadataRequest`，具备 10 秒超时和 AbortController 取消能力。
- 切歌、强制轮询/重开以及页面卸载会取消旧歌词请求，避免慢 WebView 或代理连接占用资源并与新歌曲竞态。
- 取消产生的 `AbortError` 不再显示为 provider 失败，也不会额外安排歌词重试；后台元数据补全默认开关保持不变。
- UI 离线回归通过。
# 2026-09-05 元数据 provider 空结果诊断

- 成功完成请求但返回空列表、以及返回非空列表却没有可展示候选，现分别记录为 `empty_results` 与 `no_valid_candidates`。
- 两类情况都不会阻断后备数据源；诊断只保留有界计数，不包含查询词、URL 或原始 payload，避免把正常 no-match 与 provider 故障混为一谈。
- 新增服务与诊断回归，完整离线门禁待本轮运行确认。

# 2026-09-05 歌词优先响应协议兼容

- 修复播放开始时歌词优先预取只读取桥接包装字段、因而遗漏正常 `/api/lyrics` 顶层响应的问题；现在同时兼容顶层 JSON 与 `{data: ...}` 包装。
- 已完成的歌词和封面将立即回投当前歌曲，不再因客户端字段路径错误反复轮询；未进行真实设备或外部 provider 验收。
- 进一步兼容请求封装层与宿主桥接层同时存在的双层 `data` 包装，并补充静态回归。
# 2026-09-05 元数据桥接响应兼容

- 曲目元数据预取现在与歌词优先通道共用有界响应解包，兼容 fnAudio 顶层 JSON、宿主一次包装和请求/桥接双层包装。
- 保留 token、AbortController、超时和有限重试语义；只修正响应投影读取，不改变后台补全和 Tag 写回默认关闭策略。
- `test_ui_lyrics_priority.js` 与完整离线门禁覆盖该回归。
# 2026-09-05 首屏元数据桥接兼容

- 首屏可见行的 metadata 预取与当前播放/歌词通道统一响应解包，支持宿主桥接的单层和双层 `data` 封装。
- 保持现有延迟、并发、取消与重试上限，不增加首屏 provider 竞争；仅修复封面和专辑候选读取路径。
# 2026-09-05 元数据候选对话兼容

- 手动“元数据补全候选”读取路径现在使用统一有界响应解包，兼容直连及宿主单层/双层 `data` 包装。
- 候选展示、pending 轮询、无匹配重试和确认写回保持原有边界，不增加 provider 请求并发。
# 2026-09-05 元数据设置响应兼容

- 设置页状态读取、元数据开关保存及失败 Tag 写回重试现在统一支持宿主 `data` 包装。
- 仅作用于元数据专用路径，保留原有错误处理和请求边界。
# 2026-09-05 元数据协议模块拆分

- 新增 `metadata_response_policy.js`，集中处理宿主桥接 `data` 封装，限制最大解包深度。
- `app.js` 的播放、首屏、候选对话和设置页统一复用该策略。
- 回归测试同时校验策略脚本在 `index.html` 中先于 `app.js` 加载，避免冷启动时序问题。
# 2026-09-05 元数据快照持久化

- 可见元数据增量回投完成后，复用快照调度器在空闲时持久化当前页。
- 下次启动可优先显示已补全的封面/字段，避免恢复旧快照造成短暂空白。
# 2026-09-05 大曲库性能复测

- 100,000 首离线样本首/中/尾页约 52.6/106.4/160.1ms，分页热缓存约 61.6 倍。
- metadata overlay 热读约 3.0 倍，引用项补水约 5.7 倍，FTS5 搜索相对 LIKE 约 19.7 倍。
- 证据：`artifacts/large-library-benchmark-20260905-current.json`；仅用于离线趋势，不替代真实设备验收。
# 2026-09-05 发布恢复索引

- 新增 `artifacts/RELEASE_INDEX.json`，记录 156 个版本目录的 FPK 校验结果、SHA-256 和证据完整性。
- 索引保留旧版本缺少 `SOURCE_PROVENANCE.json` 的事实，便于会话删除或工作树恢复时快速定位可信产物。
# 2026-09-05 元数据桥接解包兼容

- UI 元数据、歌词、状态和候选请求现在最多兼容三层 `data` 包装，覆盖宿主 transport/session 额外 envelope；仍拒绝数组、超深包装和任意脚本。
- 新增第三层成功、第四层拒绝回归，降低“元数据请求成功但界面显示为空”的协议兼容风险。
# 2026-09-05 刷新请求并发去重

- 同一分页的显式刷新现在与普通请求一样共享活动请求；刷新仍不读取旧缓存，但连续触发不会重复打 SQLite/HTTP 或造成双重列表提交。
- 保留 epoch 校验，旧刷新响应不会复活到新页面；新增重复刷新合并回归。
# 2026-09-05 元数据预取延迟观测

- UI 指标新增最近一次、最大值和累计元数据预取耗时，均限制在 1 小时范围，不暴露歌曲、URL 或时间戳。
- 这些指标仅用于定位 provider 慢请求与前端列表渲染瓶颈，不替代真实网络验收。
# 2026-09-05 元数据冷启动回退

- `/api/metadata/track` 在音乐库已就绪而元数据服务尚未初始化的短暂启动窗口，现返回受限的本地标签投影，避免已有标题/歌手/专辑在 UI 中被误判为“无法获取元数据”。该投影标记为 `status: local`，不写入 provider 匹配、不触发 Tag 写回；新增离线策略回归。
- `/api/lyrics` 同步优先返回已嵌入的本地歌词（必要时附带已有封面 URL），只有没有本地歌词时才继续返回原有可重试的 pending 状态；避免冷启动时歌词页空白。
- 冷启动回退仅在存在实际本地字段时生效；完全无标签文件继续返回可重试 pending，不会误把空投影当作 provider 成功。
- 本地回退现在也携带已有封面 URL，恢复队列中的当前歌曲不会在 worker 启动窗口短暂显示音乐符号占位。

# 2026-09-05 曲库性能复测

- 归档 `artifacts/large-library-benchmark-20260905-post-refresh-dedup.json`。10 万首合成曲库首/中/尾页约 53.4/111.1/160.8ms，分页热缓存约 60.8 倍，metadata overlay 约 3.4 倍，FTS5 搜索约为 LIKE 的 18.4 倍。

# 2026-09-05 UI 指标投影安全边界

- 指标快照现在只接受有限数字或长度受限的数字文本，拒绝布尔、Symbol 与任意对象的隐式转换；新增异常对象回归，保持诊断只读且不触发用户代码。

# 2026-09-05 首屏闪烁策略拆分

- 首屏快照仍可见而权威请求暂未返回时，是否延迟空列表提交的判断已抽为 `ui/library_render_policy.js` 纯策略；主 UI 只传递有界状态，新增回归覆盖加载中/已有呈现/空列表边界。
- 同模块现在也负责快照、歌曲页、分组页和文件夹页的“已有可见呈现”判断，减少加载竞态条件在 `app.js` 中重复实现。
- 可见呈现策略的长度字段现仅接受有限数字，异常对象和字符串不会触发隐式转换。
- 本地 Playwright 浏览器夹具回归 3/3 通过，确认桌面与移动端列表/专辑详情交互未受首屏策略拆分影响。
# 2026-09-05 元数据 pending 展示保护

- `/api/metadata/track` 在 provider 任务 pending 或 worker 恢复窗口合并本地标签、封面和歌词投影，继续标记 `pending/retryable`，避免 UI 将已有元数据闪成空白。
- 新增 HTTP 集成回归，验证 pending 响应保留本地标题、专辑和封面 URL。
# 2026-09-05 元数据显式任务与封面路径边界

- 后台元数据补全保持默认关闭，但显式播放触发的 track 与其 album 任务（优先级不高于 10）现在都会被消费，避免只返回本地标题而长期拿不到专辑封面/信息。
- `track_match` 仅投影 64 位 SHA-256 十六进制 artwork ID，旧缓存中的异常值不再形成无效路径。
- 新增 artwork ID 边界回归；未改变 provider 网络有效性或真实设备验收结论。
# 2026-09-05 Pending 元数据展示补强

- worker 尚未初始化或恢复期间，元数据 pending 响应会继续投影歌曲已有的内嵌/旁车封面和歌词；不改变 provider 重试与 Tag 写回语义。
- 覆盖“无完整 Tag 但有封面/歌词”的策略回归，降低冷启动空白与闪烁。
# 2026-09-05 大曲库性能复测

- 完成 100,000 首合成曲库的首/中/尾页、分页热缓存、metadata overlay、引用项补水和 FTS5 搜索复测。
- 证据：`artifacts/large-library-benchmark-20260905-final-followup.json`；热页约 65.3 倍、FTS5 相对 LIKE 约 14.8 倍，查询峰值 Python 内存约 1.0MB。
- 该结果仅证明离线查询边界和趋势，不替代真实 NAS/WebView 体验验收。
# 2026-09-05 封面缓存修复

- 旧缓存存在异常 artwork ID 时，不再阻断新的封面下载与持久化；歌词/封面复用统一接受 64 位内容寻址 ID。
- 新增损坏引用替换回归，保持 Tag 写回和 provider 重试语义不变。
# 2026-09-05 封面写入竞态修复

- `_store_track_artwork` 的下载前后两次缓存检查统一使用严格 artwork ID 校验；损坏旧引用不会在下载完成后再次阻断修复。
- MetadataService 专项 75 项、完整离线门禁 1080 项通过。
# 2026-09-05 artwork 缓存迁移

- 服务启动时按版本一次性清理 metadata_entities/metadata_tracks 中异常 artwork ID，避免历史坏缓存永久阻断封面恢复。
- MetadataService 专项 76 项、完整离线门禁 1081 项通过。
# 2026-09-05 元数据封面回投边界

- 分组、曲目页、歌词页和当前歌曲优先队列统一只接受有效内容寻址 artwork ID。
- 损坏缓存不会抑制重新补全，也不会形成无效封面 URL。
- MetadataService 专项 77 项、完整离线门禁 1082 项通过。
# 2026-09-05 歌词缓存封面边界

- 已缓存歌词的快速响应现在同样严格校验 artwork ID，历史损坏引用不会继续生成无效封面 URL。
- MetadataService 专项 78 项、完整离线门禁 1083 项通过。
# 2026-09-05 首屏曲目投影优化

- 公共曲目响应在构建时直接排除 `item_json`、完整歌词和内部 artwork ID，避免大字段先复制后删除，减少冷启动分配与 JSON 工作。
- 保留安全的 metadata artwork 回投；library presentation 回归与完整离线门禁 1084 项通过。
# 2026-09-05 专辑实体封面缓存边界

- `cached_entity()` 现在拒绝异常 artwork ID，专辑详情/分类响应不会生成无效封面 URL。
- MetadataService 专项 79 项、完整离线门禁 1085 项通过。
# 2026-09-05 元数据落库安全边界

- 实体、歌词和曲目封面在写入 SQLite 前统一校验内容寻址 artwork ID，异常下载器返回值会被丢弃。
- MetadataService 专项 80 项、完整离线门禁 1086 项通过。
# 2026-09-05
- 修复元数据响应顶层 `image_url` 未回投到当前播放/可见歌曲行的问题；候选为空但服务端已有 artwork 缓存时也能立即显示封面。
- 元数据预取现在把“未知专辑/未知歌手”等扫描占位值视为缺失字段，避免错误跳过 provider 查询。
- 本轮保持请求、并发和重试上限不变，未改变后台全库补全默认关闭策略。
# 2026-09-05 元数据预取恢复

- 修复可见歌曲元数据预取在 provider 临时失败或无匹配后永久占用页级去重键的问题。
- 新增 `shouldReleaseKey()` 策略：失败、无匹配和可重试响应会释放当前曲目的预取资格；pending 仍保持单次轮询所有权，避免重复并发。
- 元数据投影发生变化时自动重新调度可取消、有限并发的可见预取 lane，让 worker 恢复或 provider 冷却结束后无需手动切页即可再次补全。
- 新增策略回归；`test_offline.ps1` 完整门禁 1086 项通过。
# 2026-09-05 大曲库尾页基准

- `tools/benchmark_large_library.py` 新增专辑分类尾页冷/热查询验证，确保大曲库分类尾页仍遵守分页上限且缓存失效后重新读取不会扩大返回量。
- 100,000 首合成曲库结果已归档到 `artifacts/large-library-benchmark-20260905-tail-pages.json`：歌曲尾页约 160ms、专辑尾页约 5ms、专辑尾页热缓存约 11.4 倍，Python 峰值约 1.05MB，FTS5 相对 LIKE 约 19.1 倍。
- 新增 benchmark 回归断言覆盖尾页 offset、count、返回数量及缓存命中/未命中。
# 2026-09-05 — 冷启动当前曲目元数据恢复

- 修复首屏恢复队列下当前歌曲未进入元数据获取的问题：权威歌曲页提交后，若当前曲目仍缺少封面、专辑或歌手，立即启动当前曲目优先补全。
- 普通可见歌曲仍使用延迟、有限并发的预取；只有优先 lane 已占用当前曲目时才将其排除，避免冷启动时元数据请求被错误跳过。
- 未进行真实设备、DAC/DSD/DLNA/AirPlay、fnOS App Center 或 Android 多机型验收。
## 2026-09-05 元数据本地即时投影

- 新增 `metadata_query_policy.local_track_candidate()`：元数据 provider 尚未完成时，候选接口立即展示扫描到的标题、歌手、专辑等本地 Tag。
- 本地候选明确标记为 `source=local`、仅用于展示，不会被当作 provider 确认结果，也不会触发 Tag 写回；远端候选完成后仍可正常替换。
- 新增异常输入与字段保留回归；真实 provider 网络稳定性和真实设备验收不在本轮范围。

## 2026-09-05 首屏桌面分页窗口

- 新桌面会话默认首屏从 120 首降为 96 首，减少大曲库首次 JSON 解析、DOM 构造和封面布局压力。
- 已保存的 `fnaudio.pageSize` 偏好、移动端 60 首默认和服务端分页协议保持不变。
- 以 100,000 首合成曲库复测 96 首页大小：首/中/尾页约 62.4/106.5/169.1ms，分页热缓存约 70.7 倍；证据已归档，未替代真实 NAS/WebView 验收。
## 2026-09-06

- 调整可见列表的缩略图预热时序：保留 24 项上限、单 worker、共享 FFmpeg 门禁与取消语义，但在分页接口入队后先留出 150ms 静默窗口。这样服务端可以先完成首屏 JSON，浏览器的 DOM/eager 首批封面也不会与缓存预热立即竞争慢 NAS 的 I/O 或 CPU；连续页面入队会合并延后，取消不产生假 in-flight 项。
- 新增封面预热静默窗口回归；已运行 `tools/update_source_manifest.ps1` 与完整 `tools/test_offline.ps1`：1125 项测试通过，Node/UI 回归通过。验证日志：`artifacts/offline-20260906-cover-prewarm-quiet-window-final.log`。

- 首屏列表行重建进一步收敛：新增纯策略 `library_row_signature_policy.js`，将快照页/权威页的 keyed reconciliation 从原始 JSON 字段比较改为最终渲染的标题、列文本、封面地址和 DSD 样式比较。等价数值/字符串等传输差异不再替换行节点，已解码封面与在途封面调度得以保留；真正的封面或可视文本变化仍会正常更新。
- 新增该策略的独立 Node 回归，并运行 `tools/update_source_manifest.ps1` 与完整 `tools/test_offline.ps1`：1124 项测试通过，Node/UI 回归通过。验证日志：`artifacts/offline-20260906-row-signature-final.log`。

- 修复旧元数据终态缓存的恢复死角：当 `failed` 或 `no_match` 记录的 `updated_at` 缺失、为零或不可解析时，用户可见的单曲查询会进入既有有界恢复路径，不再因无法计算 60 秒冷却窗口而永久显示“无法获取元数据”。后台全库补全默认状态、provider 预算与重试上限不变。
- 已运行 `tools/update_source_manifest.ps1` 与完整 `tools/test_offline.ps1`：1124 项测试通过，Node/UI 回归通过。

- 浏览器 E2E 新增首屏指标断言，覆盖真实页面启动后的列表 commit、封面 hydration、元数据请求统计和有界 timing；Playwright 夹具 4/4 通过。
- 元数据状态与诊断新增 provider 候选缓存的有界命中/未命中/容量/TTL 指标，便于定位“provider 慢”与“重复轮询”差异。
- 为曲目候选查询增加有界正结果缓存（TTL 2 秒、最多 128 项），仅复用成功候选，空结果/错误仍允许下一轮恢复；新增 MetadataProviders 回归。
- 修复旧宿主桥接返回通用 HTTP 200 `{ok:true}` 时的元数据误判；无任何元数据投影字段现在继续有界重试，避免当前歌曲看似永久无法获取元数据。
- 收紧 provider 候选纯策略的数值输入：非法 limit、NaN/Infinity 阈值和候选置信度均安全回退/丢弃，避免异常数据污染排序结果。
- 追加 100,000 首曲库/96 首分页离线基准：首/中/尾页约 58.5/110.9/163.9ms，分页热缓存约 72.0 倍，metadata overlay 约 3.6 倍，引用 hydration 约 6.7 倍，FTS5 相对 LIKE 约 18.4 倍；证据为 `artifacts/large-library-benchmark-20260906-final.json`。
- 将 provider 候选最终筛选/去重/排序抽为纯策略 `finalize_track_candidates()`；保留现有阈值与 8 条上限，新增异常输入和重复候选回归。
- 修正封面节点被替换后迟到 load/error 事件的并发计数竞态，旧事件不会重复释放新节点正在使用的槽位。
- 封面调度器现在会在增量协调时释放已脱离 DOM 的在途图片槽位，避免旧节点请求悬挂导致新封面无法继续加载。
- 补齐旧 WebView 封面调度增量路径：无 IntersectionObserver 时，新提交的封面会追加到现有有界游标并继续加载，避免增量列表更新后新增封面停留在占位符。
- 优化封面加载生命周期：同一列表根节点重复 hydration 现在增量协调，保留已有 observer、队列、在途请求和浏览器解码结果，仅处理新增图片，减少播放/元数据回投引起的重复请求及列表闪烁。
- 新增 UI 回归覆盖同根 hydration 的 generation、in-flight 请求和新增封面排队行为。
- 离线门禁：1093 项 Python 测试及全部 Node/UI 回归通过。
# 2026-09-06

- 首屏封面调度器新增一次有界错误重试：临时网络/代理失败不会让封面永久消失，失败期间仍显示统一音乐符号，成功后自动恢复图片。
- 元数据候选缓存键改为安全规范化，避免异常 Tag 对象在请求前触发隐式字符串转换并中断 provider 链路。
- provider 成功/失败/空结果计数及 metadata projection revision 改为写入时安全修复，损坏状态不会在下一次请求中重新触发异常。
- 收紧 provider 活动摘要、曲目页缓存状态和 worker 重启计数的诊断边界；统一拒绝异常对象/NaN 的隐式 `int()` 转换，避免元数据状态接口被损坏计数拖垮。
- 修复元数据候选缓存诊断计数的异常输入边界：状态快照及命中/未命中递增不再直接对不可信对象执行 `int()`，非法对象、NaN 和非整数文本会安全回退并保持上限。
- 新增回归覆盖损坏计数恢复，避免状态接口异常造成元数据链路看似不可用。
# 2026-09-06
- 元数据恢复：fetch worker 池异常退出后，交互请求触发的有界恢复现在会回收超过 15 分钟的 stale `running` 任务为 `retry`，防止元数据任务永久卡死；新增离线回归覆盖状态、重试时间和恢复原因。
- 元数据空响应恢复：服务已启动但 `track_match()` 短暂返回空值时，HTTP 接口现在回投本地 Tag/文件名并保持可重试 `pending`，避免前端显示“无法获取元数据”；完整离线门禁 1121 项通过。
- 元数据空投影恢复：`track_match()` 返回空对象或无状态/候选/封面等投影字段时也会回投本地信息并保持 `retryable pending`，避免空 JSON 让前端停止恢复；离线回归覆盖。
- 元数据瞬态异常恢复：单次 SQLite/worker 异常不再让交互接口返回 opaque HTTP 500，改为本地投影 + 有界 retryable pending；完整离线门禁 1122 项通过。
- 冷启动缩略图预热窗口：服务启动仅排队首个 96 首可见窗口，避免大曲库索引遍历拖慢首个 `/api/library` 请求；整库预热继续异步、可取消。
- 元数据 pending 文件名兜底：worker 尚未可用或短暂异常且 Tag 为空时，接口回投受限文件名身份并保持 retryable pending；不自动写回源文件，离线门禁 1123 项通过。
- 元数据本地数值边界：pending 投影拒绝 NaN/Infinity 等非有限值，避免损坏 Tag 进入显示或 provider 查询；完整离线门禁 1124 项通过。
- 2026-09-06：修复元数据“看似无法获取”场景：用户显式重试单曲或歌词时清除 provider 的短时冷却，立即重新走有限数据源链路；普通轮询与后台补全不改变原有冷却和资源上限。新增 `test_explicit_retry_clears_provider_cooldown`，完整离线门禁通过。

# 2026-09-06 首屏用户状态回填去闪烁

- 修复并行启动路径中的无效整页重绘：歌曲分页已显示后，延迟抵达但未改变可见歌曲列表的用户状态不再调用完整 `render()`。
- 新增可见用户状态签名和局部 Chrome 刷新，仅更新播放列表导航、收藏/循环/随机控制、设备名称及当前播放行标识；收藏、列配置、当前歌单或队列真正变化时仍执行原有完整重绘。
- 更新 `test_ui_library_loading.js`，覆盖“保留行节点/封面而非过期 helper 名称”的实际 keyed reconciliation 契约。
- 已运行 `tools/update_source_manifest.ps1` 与完整 `tools/test_offline.ps1`：1128 项测试通过；验证日志 `artifacts/offline-20260906-user-state-hydration.log`。

# 2026-09-06 首屏元数据启动与宿主响应兼容

- 可见行元数据预取仍避让首屏列表/封面，但静默窗口由 750ms 收敛至 220ms，`requestIdleCallback` 的兜底由 900ms 收敛至 450ms；避免用户把长时间无请求误解为“无法获取元数据”。当前播放歌曲的即时优先通道不受影响。
- `metadata_response_policy` 现在有界识别 `data`、`result`、`payload`、`metadata` 宿主包装，并在检测到 `status/best/candidates/image_url/lyrics/pending/retryable` 投影后立即停止；四层上限、异常 getter、数组及混合包装均有 Node 回归。

# 2026-09-06 首屏快照复用指标

- UI 诊断增加 `snapshotMarkupReuses` 和 `listMarkupNoops` 两个受限计数：前者记录快照页到等价权威页之间的 HTML/封面节点复用，后者记录最终列表 HTML 完全一致而跳过 DOM 提交的次数。
- 指标通过既有 `window.__fnAudioUiMetricsSnapshot()` 以只读、数值上限投影提供；浏览器 E2E 同步要求两个字段存在，避免日后首屏去闪烁路径退化却没有证据。
- 本轮未改变 provider 并发、重试上限、后台元数据补全或 Tag 写回默认状态；仅增加离线可验证的观测能力。

# 2026-09-06 元数据 pending 恢复复核

- 可见歌曲行在 12 次常规有限轮询后，若仍为 `pending`、`retryable` 或仅收到宿主通用成功 envelope，现可按页面最多静默恢复两次（3.5 秒、7 秒）；失败和无匹配仍使用原有终态恢复，不扩大后台抓取范围。
- 恢复计时器在分页、视图切换或页面隐藏时取消，并在等待期间保留去重键，避免重试风暴或首屏二次列表提交。
- 服务专项回归确认：关闭后台整库补全不会阻断显式单曲元数据优先 lane；本机只读 provider 烟测返回《七里香 / 周杰伦》的 QQ 候选、专辑及封面 URL。Playwright 浏览器回归 5/5 通过，包含元数据完成后保留既有歌曲行的防闪烁用例。

# 2026-09-07 发布资源治理

- 构建脚本与离线证据校验器统一拒绝超过 10 GiB 的 FPK，并将检查放在复制、解包和 SHA-256 前，避免超大产物消耗不必要的磁盘、内存或哈希时间。
- 新增稀疏超限 FPK 回归，验证限制不依赖实际分配 10 GiB；发布脚本专项和完整离线门禁通过。

# 2026-09-07 曲库随机刷新缓存边界

- `random100` 的显式刷新请求现在绕过服务端短期页缓存，保证用户请求刷新时重新抽样；普通分页缓存、扫描刷新队列和筛选随机查询语义保持不变。
- 新增 SQLite 回归验证连续随机页刷新不会复用旧样本。

# 2026-09-08 元数据候选缓存身份

- 可见元数据批次完成后会一次重建当前页面的声明式行 HTML；后续播放/状态刷新可直接命中列表 no-op，避免对已局部 patch 的首屏再次执行整页 keyed reconciliation。
- 新增 `metadata_artwork_policy.py`：统一 SHA-256 artwork id 规范化与相对 URL 投影；服务端 metadata 返回与曲库公开表示复用同一安全边界，保留既有严格校验和兼容导出。
- 元数据可见行批次进一步复用 live row 索引、活动列配置和选择状态刷新，避免每条回投重复全局 DOM 查询与列计算；保持 keyed patch、封面复用和整页回退语义。
- 首屏元数据批次的可见行 patch 现在一次构建页面 ID/位置索引，避免每条回投重复线性扫描 `pageItems`；保持既有 keyed DOM 更新、封面批次 hydration 与缺失行整页回退语义。
- 候选正缓存键现在包含规范化 provider 查询和文件名身份提示，避免部分 Tag 相同的不同曲目复用另一首歌的低置信度文件名候选。
- 新增 MetadataService 回归；provider 回退、缓存 TTL 和结果上限保持不变。
- 候选缓存键生成抽至 `metadata_candidate_cache_key.py`，并以独立测试固定边界，降低 provider 编排模块的耦合。









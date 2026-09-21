# fnAudio 待办
- [x] 2026-09-21：R138 决策落地轮（本轮记录插入后在盘上为 L2；条目内行号一律指插入前位置）：负责人对第三轮征询给出 X1～X13 裁定，本轮把它们全部落到磁盘。**净关闭 8 条既有待办、新立 0 条** ⇒ 开放 68 → 60 ＝ 代码 2（插入后为 L99、L150，均为深读债）＋ 设备/外部 45 ＋ 需决策 0 ＋ 长期观察 13。接管取证一律从磁盘复算、不引用摘要：HEAD `9b6407e`（R137）、分支 main、无 remote、暂存空、无 merge/rebase/cherry-pick 残留；编辑前 TODO.md 内容行 2221、0 CRLF、尾部 4 个 LF；开放 68 ＝ 顶部代码段 9（L47/L48/L98/L112/L114/L121/L128/L149/L159）＋散条目 L803＋设备段（节标题 L1849 起）44＋决策段（节标题 L1877 起）1（L1887）＋段外 13。落地明细：① X7=A 歌词缓存字节预算接入配置（`metadata_local_lyrics_cache.bytes_limit_from_config` ＋ `metadata_service` 两条道构造点 ＋ `config.py` 默认表/区间表/归一化三处）；② X10=A CUE 同轨重复 `INDEX 01` 改为「取首个、拒后续」（`cue_parser.parse_cue_structure` 的 `index01_seen`）——合计 8 个文件、+155 −5、新增 8 枚判别测试。③ X1=A：L803 迁入设备段（新 L1878），代码桶与设备桶同步调整、开放总数不变。④ X2=B：段外 13 条正式命名为第五桶「长期观察」，段首声明行（新 L2082）写明不计入终止分母。⑤ X4=C：L1887 并入 L47 后永久关闭。⑥ X5=B／X6=B／X8=A／X9=A／X11=A 分别按「无 SMB 部署面」「无真实分布不引入新配置」「保持拒绝即清空」「回退方向安全且不新立项」「0.09~0.12 ms 性能可接受」关闭；X9 明确不选抬上限。⑦ X12=A：L98 只重算数字、判据不动（欠读 21,639 行，Android 43 个 `.java` 纳入范围）。⑧ X3=A+C：连续 0 关闭的深读登记轮改以「欠读行数下降」计进展，并对被真机证据挡住的 7 条作降级裁定——本轮 8 条关闭即其执行结果。**验证**：仓库外 `%TEMP% 目录下的 r138mut` 副本（`git clone --no-hardlinks` ＋ 移除 origin ＋ 复制本轮 8 个文件）控制组 Python `Ran 2491 / OK (skipped=3)`、JS 74 个文件全 passed；变异矩阵 **V1～V8 全部 KILLED**，其中 V2（删 `load_config` 区间表新键）与 V8（把设置上限放宽到 512 MiB）首轮被「只考验 save 侧」的断言放过，补出 `test_lyrics_cache_budget_is_clamped_on_load_alone`（load 单侧夹取）之后才被杀；副本末行 `all restored, cue guard present again: True`。主仓 prefix 门禁 `artifacts/offline-20260921-round211-prefix.log`：**Ran 2491、OK (skipped=2)**、JS passed 行 73（主仓 skipped=2、副本=3，差异在副本环境而非源码，终值以主仓终跑为准）。`SOURCE_MANIFEST.sha256` 刷新后 707 条、sha `61e6ddd03cd9b85b94e04496bf2214142d608f60771bc02e136a2888b30edf10`，三次运行幂等，8 个改动文件逐文件复算 MATCH。接管复核又发现并当轮修正一处**本轮自己引入**的文档缺陷：CHANGELOG 两条 R138 记录被插成 `R138 主 / R137 主 / R138 收口`（第二处插入误按 1-based 取位，把收口条挤进 R137 两条之间），违反「最新在前」；`test_change_record` 只比日期，三条同为 2026-09-21 因而门禁全绿也拦不住——已交换该两行修正，细节见 CHANGELOG 的 R138 收口条。另据 HEAD 对证 TODO 顶部缺 R134～R137 顶层条目属既有约定，不补写。反增长核对：关闭 8、新立 0 ✓ 设备段除迁入项外一行未改 ✓ 未放宽任何旧守卫 ✓ 未动 `.gitignore`、未 push、未跟踪文件一律不入库。
- [x] 2026-09-21：R133 代码轮（本轮记录插入后在盘上为 L2；被关闭的既有代码条目原在 L162、插入本行后为 L163）：**净关闭 1 条既有代码待办 —— L162（`response_json_loader.js` 的 text() 分支：为未超限响应额外分配整份 UTF-8 编码副本来测量、且在无 TextEncoder 的主机上用 `typeof TextEncoder === "function"` 门完全跳过字节测量＝预算空洞），新立 0 条**。修法＝新增无分配、可早退、与 TextEncoder 非 fatal 逐字节等价的 `utf8ByteLengthBounded`（孤立高/低代理各计 3、代理对计 4 并消费两 code unit），text() 分支改用它并保留 `text.length * 3 > maximum` 上界短路；末级 `json()` 回退按「本仓库唯一宿主 `nativeHttpResponse()` 同时暴露 text()/json()、不存在只暴露 json() 的宿主」以证据关闭、不收紧。判别测试新增于 `test_ui_response_json_loader.js`（真 TextEncoder 作 oracle 的 20×64 双 loader 等价环＋无编码器主机仍可测＋计数 stub 断言带内零再分配＋孤立/成对代理边界＋两条源码级正则守卫），并同步把旧 measured 段以「带内调用一次 TextEncoder」为证据的两条代理断言改为「进入测量带也不得再分配副本」（加强回归守卫，非放宽）。仓库外 `clone --no-hardlinks` 副本控制组全量 Python 2483 OK、全量 Node 74/74 先绿，变异 M1～M4 全灭。关闭后开放 68＝代码 10＋设备/外部 44＋需决策 1＋台账 13；终跑数值见 CHANGELOG R133 收口条。
- [x] 2026-09-21：R132 取证轮（本轮记录插入后在盘上为 L2；上面的 L119 后缀令原 L119 仍为 L119、插入本行后为 L120）：**净关闭 0 条、新立 0 条**，按目标正文「被真机证据／样本／负责人自设门槛挡住就当轮如实放弃、不硬凑」条款放弃代码项，改为完成终止条件 (3) 要求的那一次汇总征询。接管取证全部从磁盘复算、不引用记忆：HEAD `e6bca79`（父 `a770dc3`）、分支 `main`、无 remote、无 merge/rebase/cherry-pick 残留、`git status` 跟踪区干净（只剩历史未跟踪项）；TODO 内容行 2,219（口径 `len(split(chr(10)))-1`、尾 4 LF、0 CR）；开放 **69 ＝ 代码 11 ＋ 设备/外部 44 ＋ 需产品决策 1 ＋ 台账 13**，代码 11 条在插入前的行号为 L45/46/96/110/112/119/126/147/157/161/801，设备段 L816..L1874（1,059 行 / 53,981 字符）与 HEAD **逐字一致**；`SOURCE_MANIFEST.sha256` 707 条、0 重复、只覆盖 `src/` 627 ＋ `android-client/` 80。**那 13 条台账项的分类已由逐条读全文定案**：12 条（L2086/2105/2108/2113/2114/2119/2133/2134/2146/2151/2152/2160）是 2026-09-01~09-06 历史节里的「持续推进／持续观测」伞形条目，语义上不可关闭；第 13 条 L2078 装的是外部材料项（取得飞牛 APP 官方 Web/FPK 播放桥接），却落在「持续目标追加」历史节而非 P0 设备段——**这就是旧正文 155＝64＋82＋9 与当前 69 口径不可比的原因**，差额不是进度而是口径。代码桶 11 条经逐条复核**全部带负责人自设门槛**（L45 先量 SMB 真机、L46 别拍数、L96/L147 欠读面未读完、L110 拿到设备内存曲线前不暴露、L112 无真机证据不动、L119 见真机 trace 才改、L126 先找真实样本、L157 暂不动、L161 无证据、L801 桶归属待裁定），且 R129 已证测试机（6 行曲库／元数据总开关关闭／全 ext4）答不了其中任何真机门；本轮唯一新增的可离线事实是 L119 的余量估算被实测证伪（见该条后缀）。12 项决策清单已在会话内逐条向负责人征询一次，两问（L1885 三选一、是否批准纯深读轮）状态未变、仍待发话。收口实测（同轮内由接管方完成）：用 **Windows PowerShell 5.1**（子进程 `5.1.26100.9444`）幂等复跑 `tools/update_source_manifest.ps1`，输出 `Wrote 707 entries`、文件 sha256 前后同为 `49729867EB336BBE2D5A24D47FE4BAF3F6B44C6ED88892FF0CD0F48EA8217A18`、`git status` 对该文件干净 ⇒ 本轮清单不入库；逐文件复算 707/707 MATCH、0 重复、0 畸形；全量门禁终跑 `artifacts/offline-20260921-round205.log`（`Ran 2483 tests`／`OK (skipped=2)`／0 条 `FAILED`／含 passed 的 JS 结果行 73，JS 测试文件实为 74 个）。
- [x] 2026-09-21：R131 代码轮（本轮记录插入后在盘上为 L2）：**净关闭 1 条既有代码待办 —— 原 L122（热页拷贝成本那条「唯一路线」条目），新立 0 条**；本轮两项新发现（编码响应路线否决、deepcopy 残余约 40%）按反增长规则全部并入该条关闭记录，不另立条目。插入前磁盘取证（不引用历史快照）：TODO.md 内容行 2218、0 CRLF、尾部 4 个 LF；开放 70 ＝ 代码 12（L44/L45/L95/L109/L111/L118/L122/L125/L146/L156/L160/L800）＋ 设备/外部 44（区块 L815..L1873，共 1059 行）＋ 需决策 1（L1884）＋ 台账 13；已关闭行首口径 1475、含缩进 1476。**关闭动作**：勾选原 L122 并在同行尾部追加实测结论 ⇒ 开放 69 ＝ 代码 11 ＋ 设备 44 ＋ 决策 1 ＋ 台账 13；已关闭 1475→1477（含缩进 1476→1478；两处各 +1，一处是 L122 由开放翻为已关闭，一处是本条记录本身就是一行勾选项）；插入本条后内容行 2219。**设备段未动**：本轮 TODO.md 相对 HEAD 只有两类改动 —— 新增 L2 一行、原 L122 勾选＋同行追加。**代码面**：`src/app/server/metadata_service.py` 4763→4786 内容行（+31/−8）、`src/tests/test_metadata_service.py` 4181→4278（+97）。**插入后锚点**：代码桶 L45/L46/L96/L110/L112/L119/L126/L147/L157/L161/L801、被本条关闭的原 L122 现为 L123、决策 L1885、设备段 L816..L1874。距终止条件余 12 条（代码 11 ＋ 决策 1）；已完成 37 轮 → 本轮收口后 38，maxGoalRounds=72 不作为终止依据，也不擅自修改终止条件。
- [x] 2026-09-21：R130 账本并账轮（本轮记录插入后在盘上为 L2）：**净关闭 1 条既有代码待办 —— L551（2026-09-17 那条只列文件名的未完成范围）并入 L94 之后勾选，新立 0 条**（口径＝并入既有条目，不另立新项）。插入前实测 TODO.md 内容行 2217、0 CRLF、尾部 4 个 LF；开放 71 ＝ 代码 13 ＋ 设备/外部 44 ＋ 需决策 1 ＋ 台账 13 ⇒ 关闭后 70 ＝ 代码 12（L43/L44/L94/L108/L110/L117/L121/L124/L145/L155/L159/L799）＋ 设备 44 ＋ 决策 1（L1883）＋ 台账 13；已关闭行首口径 1473→1475（含缩进 1474→1476；两处各 +1，一处是本条记录自身就是一行 `- [x]`，另一处是 L552 由开放翻为已关闭，口径与 R129 那条记录一致；两口径之差的仍是全树唯一那条带一个前导空格的已关闭项）；插入本轮记录后内容行 2218。**漂移根因定位**：R59 立 L94 时明写「替换 2026-09-17 那条只列文件名的范围条目」，但被替换的那条始终没勾选 ⇒ 同一份欠读范围在代码桶里被计两次，这是「目标正文快照 ≠ 磁盘真实计数」的一个具体来源。**关闭前逐项对账**：L551 原文点名 16 面 —— 12 面在 L94 逐字在案、1 面 `PlaybackService` 在设备段在案、**3 面此前全盘只有 L551 提及**（`RemotePlaybackPlayer`、`AuthenticatedBitmapLoader`、`FnConnectRelayConfigClient`），已连同只有 L551 记录的三个角度（并发写／剩余循环／常驻循环）与「不得以离线门禁宣称全仓库无问题」告诫一并折进 L94，确认 L551 不再持有任何独有信息才勾选。**判别测试**：新增 `src/tests/test_scope_entry_subsumption.py` 5 项，每次从磁盘复算这条并入关系（被替代条目唯一且已关闭／其原文仍点名 16 面／活账本恰好一条且承载 ≥14 面／任一不得丢成孤儿面／账本引用的守卫文件仍在树内／四个 Android 面登记的行数与磁盘真值相等）。**设备段未动**：L814..L1872 共 1059 行与 HEAD 逐字 identical，本轮 TODO.md 相对 HEAD 仅改动 2 行（L94、L551）。距终止条件余 13 条（代码 12 ＋ 决策 1）。附带当轮修掉一个真实缺陷（工作树 CRLF 使发布清单不可复现），见同轮 CHANGELOG 与 `src/tests/test_source_manifest.py` 两条新守卫。
- [x] 2026-09-21：R129 取证轮（本轮记录插入后在盘上为 L2）：**净关闭 0 条，按目标正文 (1) 的「被真机证据／样本门槛挡住就当轮如实放弃」条款如实放弃，不硬凑、不为凑数关闭半件事**。插入前基线实测：TODO.md 内容行 2216、0 CRLF、尾部 4 个 LF；开放 71 ＝ 代码 13（L42/L43/L93/L107/L109/L116/L120/L123/L144/L154/L158/L550/L798）＋ 设备/外部 44（区块 L813..L1871 共 1059 行，与基线修订 972f733 逐字 identical）＋ 需产品决策 1（L1882）＋ 台账 13；已关闭 1472。**本轮顺带破掉一桩持续多轮的「−1 计数偏差」**：`line.startswith("- [x]")` 得 1472、`"- [x]" in line` 得 1473，差的那条是本文件 L679「播放会话恢复时提升当前曲目元数据」——全树唯一一条带 1 个前导空格的已关闭项，且全树无散文误命中；历史各修订恒差 1（972f733＝1468/1469、0b6be71＝1470/1471、95f3caf＝873e1c7＝ca8bcc7＝1472/1473），根文档里写的 1470→1472 用的是行首口径、本身没有错，不是数据漂移。本轮起三份根文档**统一行首口径**，引用计数时同时标注两口径，不改写任何历史条目正文里的数字。真机取证（测试机 198.51.100.24，root）：① **端口更正——SSH 实际在 22，此前登记为 21 的端口上是 FTP**，TCP 握手成功但 SSH 版本交换永久挂死，本轮以 `-P 22` 才建立通道；② L42 门槛要的 SMB 面在这台机上**不存在**（`findmnt -n -o FSTYPE,SOURCE,TARGET` 全表只有 `ext4 /dev/mapper/trim_…-0 /vol1`，按 cifs/smb/nfs 过滤只命中内核伪文件系统 `nfsd`），封面目录 11 文件 / 58,005 字节、`os.walk`＋逐文件 `os.stat` 三连实测 0.30 / 0.23 / 0.19 ms，量不到 5 s 级放大 ⇒ 结论是「这台机答不了这道题」而非「量了没问题」，门槛原样保留；③ L43 要的「真实库文件数分布」给不出（`library.sqlite3`：tracks 6 / albums 4 / artists 4 / covers 6 / cue_tracks 0 / folders 0，`metadata_entities`、`metadata_tracks`、`metadata_track_matches`、`metadata_assets` 四表全 0 行，`config.json` 里 `metadata_enabled=false`），据它定 `cover_cache_max_entries` 恰好就是本条明令禁止的「拍一个数」；④ L1882 真机复测与 R121 **逐值一致**（tracks 6 / cue_tracks 0），负责人新提供的无标签样本 `C:\path\to\fnAudio\music\伍佰 - 泪桥.flac`（26,325,514 字节）足以证明机制但「1 首对 1 首」给不出本条要的**占比** ⇒ 维持 R121 裁定「不选边」，本条保持开启；⑤ L93 的 R59 欠读清单**已失真**：`fnos_api.py` 已由 R118 退役（守卫 `src/tests/test_fnos_route_retirement.py`，树内仅剩 `src/app/server/__pycache__/fnos_api.cpython-31{2,4}.pyc` 两份未跟踪字节码残迹）、`alsa_player.py` 已由 R119 连同 `playback_session_contract.py` 移入 `src/tests/unwired/`（守卫 `src/tests/test_orphan_module_retirement.py`），仍在树上的九面按内容行口径复算为合计 6,655 行，其中六面与本条登记值不符、三面逐字相符（`dlna/renderer.py` 442、`state_projection.py` 231、`index.html` 184），本条顶部「250 文件 / 45,148 行、欠读 6,125 行」按现树不可复现。〔R129 记录自纠：本项首稿曾写成「九面**全部**不符、合计 6,664 行」，复算发现统计式用了 `len(text.split(chr(10)))` 未扣尾部空串，九面各虚高 1 行，且 `dlna/renderer.py`、`state_projection.py`、`index.html` 三面其实与登记值逐字相同；已按统一内容行口径更正本条与 L93 注记、CHANGELOG、PROJECT_CONTEXT 的同源表述，行数与条目身份未变。〕 ⇒ 只登记磁盘对账并明确声明**不据此关闭**。上述四处证据均以文本长锚点追加在既有条目尾部（L42、L43、L93、L1882），**不增行**：本轮结束时内容行 2217（＝基线 2216 ＋ 本条 L2）。控制组与真实动作：本轮**未改任何生产代码**，因此按纪律不开仓库外副本、不做变异矩阵——对纯文档轮次声称变异证明等于伪造证据；判别动作改为 (a) 用 `git diff --numstat` 证明工作树只有 4 改 4 删、0 增删行，(b) 修复上一轮脚本给 TODO.md 尾部误加的 3 个 LF（2219→2216 行、7 LF→4 LF，末行与 HEAD 逐字相同），(c) 刷新 SOURCE_MANIFEST 并逐文件复算 706 条 sha（missing 0 / mismatch 0 / 重复 0），其间破案的第二个口径陷阱：清单首刷看似**非幂等**（31 行变更），实为 `tools/update_source_manifest.ps1` 的 `Sort-Object FullName` 在 Windows PowerShell 5.1 与 pwsh 7.6 下对 `_`／`.` 平局排序不同，用 5.1 重跑后与 HEAD 逐字相同、`git status` 归净——集合恒等而顺序可变，故往后复算清单要比**条目集合与哈希内容**不比行号顺序，生成端固定用 5.1，(d) 跑完整离线门禁 `tools/test_offline.ps1`，终跑日志 `artifacts/offline-20260921-round199.log`：`Ran 2473 tests` / `OK (skipped=2)` / JS 侧 73 条 `… passed` 通过行 / 退出码 0（该日志末行 `GATE_DONE exit=0` 是门禁外层命令追加的退出码标注，不是 `tools/test_offline.ps1` 自身的输出；此前 round196 追加的是 `gate exit code: 0`，同一含义不同字面）。round195～198 四次同配置复跑数值完全一致，最终日志取本次末次文档编辑之后的实跑。已关闭项插入本条 L2 后为行首口径 1473／含缩进 1474，两者之差仍是 L680 那条前导空格项。开放 71→71、代码 13→13、新立 0 条、设备段 L814..L1872 共 1,059 行与 HEAD 及 972f733 逐字 identical。
- [x] 2026-09-21：R128 代码轮（本轮记录插入后在盘上为 L2）：净关闭一条代码待办 —— 原 L161（在新路径上重量首屏剩余固定开销：100k 池化冷页仍要 3.03~3.45 ms，其中 `secure_directory` + 每次读一次的 `secure_sqlite_files` 各占多少「还没在池化路径上拆开量过」，量完再决定是否做成连接级/周期级，并写明权限刷新不能为了省时间被摘掉；同时含 R121 并入本条的门禁事故：先后两段式的「池化必须更快」计时守卫被一台被外来进程占满一核的机器翻转），新立 0 条。取证先行：插入前实测 2215 行（内容行口径，末换行不另计）、开放 72 ＝ 代码 14 ＋ 设备 44 ＋ 决策 1 ＋ 台账 13、已关闭 1470、0 个 CRLF；四桶按磁盘复算一次：代码 14 ＝ L41/L42/L92/L106/L108/L115/L119/L122/L143/L153/L157/L161 这 12 条再加 L549 与 L797，决策 1 ＝ L1881（R73 `allow_disk=False` 的取舍仍等含无标签音频的样本真机取证），台账 13 ＝ L2074 与 L2082-2156 的 12 条流水条目，其余 44 条为设备/外部段（`## 宿主 MediaSession` 起至 `## 需要项目负责人决策` 之前的 1059 行区块与基线 `972f733` 逐字 identical、段内开放恰 44 条，本轮一行未改）；条目定位全程用文本前缀长锚点，不用行号。① **条目要的那次「拆开量」做完了，占比是量出来的**：把 `os.lstat/stat/chmod` 与 `os.path.isfile/isdir/islink` 全换成计数器，一次池化读的权限探测面 ＝ 目录 4 次 ＋ sidecar 两趟（借用句柄的入口 library.py:2124 与 epilogue :2160）各 6 次 ＝ **16 次系统调用**；换成 `secure_directory_on_drift` + `secure_file_on_drift` 后 ＝ 目录 1 次 ＋ 每趟 3 次 ＝ **7 次**；POSIX 稳态另省 **7 次无条件 chmod**（目录 1 次 ＋ 两趟各 3 次；`secure_file_on_drift` 只在 `S_IMODE` 与要求值不符时才 chmod）。配对计时（ABBA 轮换、N=301、先预热 200 轮）：旧探测面中位 **0.0818 ms** → 新探测面中位 **0.0383 ms**，**301/301 轮**新路径全部更快。② **裁定：只换便宜的探测，不减也不摘刷新**。条目原文点名的两个候选（连接级、周期级）本轮都判定不做，因为它们是安全语义不是性能细节：把 `secure_sqlite_files` 挪到 open 时执行，会让「借来的句柄不再走权限刷新」成为可达状态，而这条路径的既有不变量是 R120 立的「池化不减弱加固」—— 借用句柄只证明 pragma 还在，不证明别的进程没把 `library.sqlite3` 改成可读；把读入口的 `secure_directory` 摘掉，则「缓存目录被外部改成宽权限后下一次读收回 0700」只剩写路径保证。故本轮 5 处 `secure_sqlite_files`（library.py:2075/:2079/:2124/:2160/:2479）一处未减、读入口的目录加固一次未减，只把「每次全量」换成「每次更便宜」；`secure_*_on_drift` 自带 fallback（lstat 失败、非普通文件、非目录、符号链接一律退回全量 `secure_directory` 与原语义），旧库首建、目录被删、目录是软链三种情形行为不变 —— 这份信任不是新写的，是既有的 `test_directory_hardening_defers_symlinks_and_missing_paths`（test_file_permissions.py:97）与 `test_directory_hardening_creates_a_missing_directory_for_real`（:158）钉着的。③ **写路径一律不动**：`library_db_writer`（library.py:2454）与 `save_library_cache`（:3004）仍是全量 `secure_directory` —— 那两处紧邻 makedirs 与文件替换，是 drift 收益最低而漏加固代价最高的位置。④ **判别测试**：`src/tests/test_file_permissions.py:171` 新增 `test_sqlite_sidecars_are_probed_once_and_chmodded_only_on_drift`（5 个 subTest：三件全私有 / `-wal` 漂移 / 两件 sidecar 缺失 / `-shm` 是符号链接 / `-wal` 是目录；断言 lstat 恰 3 次且参数顺序＝三后缀 abspath、`secure_file` 被调用即 AssertionError、chmod 只落在漂移项且第二参是 `PRIVATE_FILE_MODE`）；`src/tests/test_library_sqlite.py:216` 新增 `test_a_borrowed_handle_is_still_hardened_on_both_ends`（池化第二次读 `secure_sqlite_files.call_count == 2` 且两次参数都是 `library_db_path(config)`，并先断 `reuses + 1` 防测试空转）、`:235` 新增 `test_only_the_read_entry_uses_the_cheap_directory_probe`（读＝drift 1 次/full 0 次，writer＝full 1 次/drift 0 次，末尾源码级钉 `secure_directory_on_drift(config["cache_dir"])` 恰 1 处、`secure_directory(config["cache_dir"])` 恰 2 处）。⑤ **门禁事故那一半改成配对采样**：`tools/benchmark_large_library.py` 新增 `paired_ab_samples()`（:124，两臂逐轮 ABBA，臂数≠2 或样本<1 直接 ValueError）、`median_duration()`（:156，空样本 ValueError，偶数取上中位）、`pooled_reuse_guard()`（:164，只看本次采样窗口内 reuses/creations 差，`reuses < samples - 1 or creations > 1` 才抛）；first-screen 段（:702-758）改用它，「池化必须更快」的 `RuntimeError` 删除而非注释，速度差降级为报告字段 `pooled_faster_pairs`；随旧形状成为死码的嵌套 `median_sample` 删除（实测 1 处定义 0 处调用）。`src/tests/test_large_library_benchmark.py:241` 新增 `FirstScreenPairedSamplingTests` 8 条：轮换顺序精确到 `["u","p","p","u","u","p","p","u","u","p"]` 与每臂归属、非法臂形状/零样本/空中位数三种 ValueError、中位数含偶数上中位、窗口差判据（`{"reuses":10,"creations":5}`→`{"reuses":14,"creations":6}` 判 (4,1)）、三种失败窗口、缺键按 0、pooled 全输只报告不抛、源码接线断言（含三个 helper 调用与 `"pooled_faster_pairs"`，且不得再出现 `not faster than reopening`/`median_sample`）；`first_screen_connection` 段既有断言删去 `assertGreater(speedup, 1.0)` 与 `assertGreater(saving_seconds, 0.0)`，保留 `samples`/`reuses`/`creations`/`idle_after_drain` 与重减精度。⑥ **仓库外副本变异证明**（`E:\temp\fnaudio-r128copy`：`git clone --no-hardlinks` ⇒ HEAD `0b6be71`、`git remote remove origin`、把本轮 6 个改动文件按工作树拷入位并逐文件 sha 复验与在盘全等；副本内先跑 `tools/update_source_manifest.ps1` 刷出 706 条再开跑）：控制组 Python 全量 `Ran 2473 OK (skipped=3)`（本机基线 2462 ＋ 本轮新增 11 条；比本机多的 1 条 skip 是 `test_offline_verification_script` 依赖未跟踪的 `artifacts/`）、Node 74 文件 0 失败；变异 **V1~V8 全灭**：V1 `secure_sqlite_files` 退回 `secure_file` → KILLED（5/5 subTest 全红）；V2 摘掉入口刷新（:2124）→ KILLED 双端频率测；V3 摘掉 epilogue 刷新（:2160）→ KILLED 同一测；V4 写路径两处也换成 drift → KILLED `test_only_the_read_entry_uses_the_cheap_directory_probe`；V5 去掉 ABBA 轮换（恒 forward）→ KILLED 顺序测；V6 摘掉 guard 的 raise → KILLED 三种失败窗口（3 failures）；V7 重新加回 `if pooled_seconds >= unpooled_seconds: raise` → KILLED 源码接线断言，如实登记：同名单臂纯函数测 `test_a_pooled_arm_that_loses_every_round_is_reported_and_not_raised` 不执行段体故未转红，本条 kill 者是接线断言；V8 guard 改读绝对计数 → KILLED 窗口判据测。每条变异写回后逐字节 sha 复验等于 pristine，收口当场重跑全量再次 `Ran 2473 OK (skipped=3)` ＋ Node 74/0。⑦ **附带发现（记录、不另立项）**：`run_benchmark` 的 `tracemalloc.start()`（:188）与 `stop()`（:857）之间罩住整个 first-screen 段，两臂分配量不同 ⇒ 被 trace 的开销也不同量放大，这是先后两段式计时不稳定的又一成因；本轮不动 tracemalloc 窗口（它同时服务内存峰值上报，改它要另立判别测试，而本条要关的是权限探测占比与池化守卫形状）。⑧ **交付前逐 hunk 自查发现、同轮修掉的格式回退**：首版把 `FirstScreenPairedSamplingTests` 直接接在上一个方法体之后（0 空行），并吃掉基线里 `if __name__ == "__main__":` 之前的两条空行中的一条 —— 该文件从基线 220 内容行变成 330 而不是 333。本轮补回类前的两空行与 `__main__` 前的两空行，现 333 内容行、类在 :241；`py_compile` 通过、`tests.test_large_library_benchmark` 复跑 `Ran 10 OK`。按反增长约束算同轮修掉，不另立项。
- [x] 2026-09-21：R127 代码轮（本轮记录插入后在盘上为 L2）：净关闭一条代码待办 —— 原 L103（50k 顶层目录时首屏剩余成本是 `SELECT COUNT(*) FROM folders WHERE root=? AND parent=?` 的覆盖索引遍历，条目据此主张「不必把子项数变成持久列」），新立 0 条。取证先行：插入前实测 2214 行（内容行口径，末换行不另计）、开放 73 ＝ 代码 15 ＋ 设备 44 ＋ 决策 1 ＋ 台账 13、已关闭 1468、0 个 CRLF；四桶按磁盘复算一次：代码 15 ＝ L40/L41/L91/L103/L105/L107/L114/L118/L121/L142/L152/L156/L160 这 13 条再加 L548 与 L796，决策 1 ＝ L1880（R73 `allow_disk=False` 的取舍仍等含无标签音频的样本），台账 13 ＝ L2073 与 L2081-2155 的 12 条流水条目，其余 44 条为设备/外部段；本轮关闭的 L103 在代码桶内。条目定位全程用文本前缀长锚点，不用行号。① **重测结论：条目原文那句「不再受目录宽度支配」只在缓存命中路径成立**。走真函数 `query_library_folders`、50k 个目录挂在同一个父目录下：未命中首页 9.2~11.5 ms（本条目点名的 count 占 4.39 ms）、深 offset 页 16.9 ms、同参热重复 0.26 ms 且不发任何语句；新事实是 folders 面没有 saved-count 摊销协议，`_save_library_meta_count` 只服务 groups（`library.py:1593-1610`），未命中就要重算 count。**判定不改生产代码**（与条目原结论一致，但换掉了它的理由）：持久列或按目录计数缓存要背写放大与第二套失效口径，而该成本只在未命中路径出现且只占其中一部分。② **关的是前提不是数字**：`test_unfiltered_folder_page_reads_an_indexed_page_plus_count` 扩展 `src/tests/test_library_sqlite.py:2686-2702`，对 trace 出的真实生产 count 语句断言计划命中 `COVERING INDEX idx_folders_root_parent` 且 detail 不含 `nocase`、禁 `TEMP B-TREE`；新增 `test_repeated_folder_page_is_served_without_rereading_the_directory`（`:2704-2768`）钉住「同参热读 0 语句」（`:2750`）、「换 offset 必须重读」（`:2753`）、「写库后必须重读」（`:2766`）。仓库内定向复跑 `tests.test_library_sqlite` `Ran 122 OK`（含两条具名测）；本轮只动测试面，`src/app/server/library.py` 与设备段一行未改。③ **仓库外副本变异证明**（`%TEMP%\fnaudio-r127-copy`：`git clone --no-hardlinks` 后 `git remote remove origin`，HEAD `972f733`，两个文件复制入位且与在盘逐文件 sha 全等；副本内先跑 `tools/update_source_manifest.ps1` 再开跑 —— clone 以 autocrlf 签出使 src 内 38 个文件带 CRLF，不先刷清单会假失败两条清单测试）：控制组 Python 全量 `Ran 2462 OK (skipped=3)`、Node 74 文件 0 失败；变异 8 条 V1~V8 ＝ **6 灭 2 存活**：V1 删 `idx_folders_root_parent` 建索引 → KILLED（正是新断言 `:2696`）；V2 `cached = None` → KILLED `:2750`；V3 `cache_values` 去掉 `page.offset` → KILLED `:2753`（`['A','B'] != ['c']`）；V4 `return result` 永不写缓存 → KILLED `:2750`；V5 计数条件去掉 `f.root = ?` → KILLED 但杀手是既有页面计划断言 `:2681`，记 KILLED-OTHER，不宣称新断言被证明；V6 `invalidate_library_query_cache` 空转 → SURVIVED；V7 缓存身份 `self.identity = None` → SURVIVED（写路径上两处机制互为兜底）；V8 ＝ V6＋V7 双旋钮同摘 → KILLED `:2766`（`3 != 4`），反证「写后必须重读」这段是活的。基线与每次还原后均 rc=0，写回后逐字节 sha 复验等于 pristine。另有一处如实登记的失败：同轮尝试关闭 L114（过户标记复用阈值）不成立 —— 它指定的修法「逐行比较、超长行单独判不等」在当前整页布尔 API 下与现状行为等价，写不出判别性测试，L114 保持开放、不硬关。
- [x] 2026-09-20：R126 代码轮（本轮记录插入后在盘上为 L2）：净关闭一条代码待办 —— 原 L176（同一个「设备是否支持源码 DSD」的事实在控制面上有三种形状、对「未知」的口径互相矛盾），新立 0 条。取证先行：插入前实测 2213 行（内容行口径，末换行不另计）、开放 74 ＝ 代码 16 ＋ 设备 44 ＋ 决策 1 ＋ 台账 13、已关闭 1466（一律按行首前缀计），0 个 CRLF；四桶按磁盘复算一次：代码 16 ＝ L39/L40/L90/L102/L104/L106/L113/L117/L120/L141/L151/L155/L159/L176 这 14 条再加 L547 与 L795，决策 1 ＝ L1879（R73 `allow_disk=False` 需产品判断），台账 13 ＝ L2072 之后的「持续推进」流水条目，其余 44 条为设备/外部段；本轮关闭的 L176 在代码桶内。条目定位全程用文本前缀长锚点，不用行号。① **缺陷本质是「探测失败被伪装成明确不支持」**：`control_point.device_protocol_info()` 两条失败路径（无 control、`GetProtocolInfo` 抛异常）原本返回带 `"supports_dsd": False` 的空壳，`media_server.soap_push()` 旧门 `if protocol and not supports_dsd` 因此把一次网络静默当成设备的一次明确拒绝而误拦，与同处注释「空/未知探测保持放行」互相打脸；发现期写入的扁平 `device["supports_dsd"]`（未探测即 False）与目标列表的 `native_dsd` 又是第三种口径。**实现口径**：一个事实一套三态与唯一谓词 —— `profiles.py:12-14` `DSD_CAPABILITY_SUPPORTED/UNSUPPORTED/UNKNOWN`、`:26-41` `_dsd_state_from()`（键不存在→unknown；键存在但值不是 True→unsupported）、`:43-69` `dsd_capability_state(source)`（入参可为 device 或裸 protocol_info；`capabilities` 为 dict 且含 `protocol_info` 键时以嵌套为准，扁平不再参与）、`:71-79` `device_supports_native_dsd()` 委托谓词、只保留给显示面的保守布尔视图。四处调用侧改为读同一谓词：`control_point.py:290-295`/`:317` 失败壳不再写 `supports_dsd` 键、`:320-321` 委托、`:494-500` 扁平字段成为「由同一谓词派生的显示缓存」、`:502-505` 异常路径删掉写 False；`media_server.py:183-185` 门改为等值比较且拦截文案逐字不变；`playback_targets_presentation.py:141-143` 同一谓词。行为不变性：未知（`{}`／嵌套缺键／`capabilities` 非 dict）→ 放行且显示 False；扁平或嵌套 True → 放行且 True；扁平或嵌套 False 或非布尔 → 拦且 False，Volumio 位精确守卫与既有字符串协议测、presentation `"true"` 测全部保持。唯一变化＝「失败空壳由误拦变放行」，是放宽误拦而不是收窄能力语义，故不需真机证据；哪些真实渲染器落 unknown 属设备取证面，并入既有 P0 外部验收段，**不新立项**。② **判别测试**：新增 `src/tests/test_dlna_dsd_capability.py` 263 行（内容行口径）／11427 字节／13 项，八行真值表对 state、push、display 三列同断言，`_push()` 注入 `control_url` 后真实调用 `soap_push()`；两条源级接线断言按行白名单而不是整文件 substring 黑名单 —— `test_control_point_only_writes_the_field_never_reads_it_back` 允许该键在 `control_point.py` 内仅出现在「唯一派生写＋唯一探测记录＋`def device_supports_dsd`＋注释行」，`test_only_the_predicate_reads_the_capability_key` 要求 `media_server.py` 与 `playback_targets_presentation.py` 全文 0 次出现该键名。仓库内定向复跑 `test_dlna*.py` 224 项 OK；全量 `Ran 2461`（2448 ＋ 本轮 13）FAILED (failures=2)，两条失败均为清单尚未刷新（`test_source_manifest.test_root_manifest_matches_authoritative_source_tree`、`test_takeover_forensics.test_the_real_manifest_and_the_real_tree_agree_right_now`），不是行为回归；JS 74 文件 0 失败（必须在 `src/` 目录下以 FullName 跑，在 `src\tests` 里跑会假失败 48 条）。③ **仓库外副本变异证明**（`%TEMP%\fnaudio-r126-copy`：`git clone` 后 `git remote remove origin`，HEAD `a295d08`，五个相关文件复制入位且与在盘逐文件 sha 全等，副本内清单先刷为 706 再开跑）：控制组 Python 全量 `Ran 2461 OK (skipped=3)`、Node 74 文件 0 失败、变异子集基线 192 OK（副本比本机多的那 1 条 skip 是 `test_offline_verification_script.test_generated_release_index_is_semver_descending_and_bounded` 依赖未跟踪的 `artifacts/`，环境差异不是回归）。变异 11 条 V1～V11 **全灭、0 存活、0 坏锚点**：V1 退回布尔强制、V2/V3 两条失败壳恢复写 False、V4 门退回对探测记录做真值判断、V5 让扁平压过嵌套、V6 目标列表改读裸扁平字段、V7 发现异常路径恢复写 False、V8 拆掉委托、V9 把静默当拒绝、V10 用真值判断替代三态比较、V11 派生写回退成强制布尔，每条都打印了指名杀手测试；副本还原后当场复跑 192 绿，随后删除副本目录。④ **一处事实纠正（只登记、不回改）**：R125 已入库的两条记录（`TODO.md` 插入前 L2、`CHANGELOG_AI.md` 插入前 L3）把仓库外副本目录写成 `fnaudio-r126-copy`，而 R124 记录为 `fnaudio-r124-copy` ⇒ R125 应为 `fnaudio-r125-copy`，属轮次计数器提前一位的笔误；按「历史条目正文不回填」规则本轮不改已入库行，在此登记，并说明本轮副本实际使用的目录名确为 `fnaudio-r126-copy`。⑤ **收口**：本轮后实测 2214 行、开放 73 ＝ 代码 15 ＋ 设备 44 ＋ 决策 1 ＋ 台账 13、已关闭 1468（1466 ＋ 本轮关闭一条 ＋ 本记录行自身，沿 R125 口径），0 个 CRLF；设备段 44 条与 `git show HEAD:TODO.md` 逐字比对未改；历史计数快照 155=64+82+9、115=51+43+8+13、88=24+43+8+13、82=22+44+3+13、80=20+44+3+13、77=18+44+2+13、76=18+44+1+13、74=16+44+1+13、73=15+44+1+13 并存不合并，一律以磁盘实测为准。`SOURCE_MANIFEST.sha256` 在全部源码编辑完成后刷新为 706 条（新增 `src/tests/test_dlna_dsd_capability.py`）并逐文件抽查 MATCH。终跑 `tools/test_offline.ps1` 见 `artifacts/offline-20260920-round192.log`。两笔提交均逐文件显式 pathspec；未碰 `.gitignore`，未跟踪产物一律不入库。
- [x] 2026-09-20：R125 代码轮（本轮记录插入后在盘上为 L2）：净关闭两条代码待办 —— 原 L69（投送期间本机元素与受控端并发，负责人裁定 D）与原 L150（NULL 标签组游标残余，负责人裁定 A＋C），新立 0 条。取证先行：插入前实测 2213 行、开放 76 ＝ 代码 18 ＋ 设备 44 ＋ 决策 1 ＋ 台账 13、已关闭 1463（一律按行首前缀计），0 个 CRLF；四桶可用可复算规则再证明一次：台账 13 ＝ L2071 之后的「持续推进/继续…」流水条目，决策 1 ＝ L1878（R73 `allow_disk=False` 需产品判断），代码 18 ＝ L200 之前的 16 条再加 L546 与 L1837，其余 44 条为设备/外部段；本轮关闭的两条都在代码桶内。条目定位全程用文本前缀长锚点，不用行号。① **裁定 D 落地**（细节与逐条坐标见原 L69 的关闭注记）：`app.js` 七处改动把「投送期间本机两路解码同时跑」改成单一所有权模型——受控端开播即停本机、本机播放意图可抢占投送、投送结束不自动续播，并补上取证阶段发现的四处缺维消费者（`loadCurrent()` 非 remote 分支、`audio.ontimeupdate` cue-tail、MediaSession play、MediaSession pause）。② **裁定 A＋C 落地**：`docs/LIBRARY_CURSOR_NULL_GROUPS.md` 承接 A 的口径，`library_write.py`（写路径 None→`""`）＋ `library.py`（带标记的一次性收敛迁移）承接 C；反对「给 NULL 组另设可比较哨兵键值」的旧证据在新注释里改标为 `library.py:1135-1143`（原 `:1127-1135`，因本轮 import 块由 1 行变 9 行整体下移 8 行；历史条目正文按「不回填」规则不回改）。③ **判别测试**：新增 `src/tests/test_ui_renderer_ownership.js` 244 行／44 条断言（含 7 条源级接线断言）；`test_ui_playback_authority.js` case 3 改为断言投送期间 cue-tail 冻结；Python 侧新增 5 条（`test_library_write.py` 3 条、`test_library_sqlite.py` 2 条）。仓库内定向复跑 `test_change_record test_library_sqlite test_library_write` 161 项 OK、两个 JS 套件绿、`node --check app.js` 通过。④ **仓库外副本变异证明**（`%TEMP%\fnaudio-r126-copy`，981 文件；11 个相关文件与仓库逐文件 sha 全等后才开跑）：控制组在全部源码编辑完成并刷新清单后复跑，Python `Ran 2448 OK (skipped=3)`（111s）、Node 74 文件 0 失败；副本 `skipped` 比本机多的一条是 `test_offline_verification_script.test_generated_release_index_is_semver_descending_and_bounded`（未跟踪 `artifacts/` 未复制），属环境差异不是回归。变异 18 条：JS V1～V10 全灭；PY V11～V18 七灭一存活，V17（把 `_collapse_null_labels()` 挪到组表刷新之后）为**等价变异**，如实保留。`docs/INDEX.md` 一行不作变异——`git grep` 证明没有任何测试读它，只能人工核验第 9 行已登记新文档，不为「可杀性」另立可离线代码待办。⑤ **两处过头陈述就地纠正**：其一，PY 变异首轮 runner 写了不存在的模块名 `test_library_query_page`，`unittest` 以 `unittest.loader._FailedTest` 恒返回非零退出码，八条 PY 变异因此全部伪报 KILLED，连设计上不可杀的 V17 也显示「被杀」；修正为真实存在的 `test_library_sqlite test_library_write` 并加「pristine 副本必须先绿」前置断言后重跑，才得到本条记录的结论——变异脚本的判定权来自控制组绿，不来自退出码非零。其二，`test_ui_renderer_ownership.js` case 1b 原先在第二个 tick 之前手动把投送元素的 `src` 清空、`paused` 置真，等于自己抹掉「同一投送下本机看着仍在播」这一被测前提，V2（去掉 `!previousActive` 只留 `localIsPlayingNow()`）因此在首轮存活；改为保留前提并补一条 `localIsPlayingNow()` 为真的 sanity 断言后 V2 被杀。V17 的不可杀性已写进 `library.py:2655-2662`：NULL 与 `""` 在组表（`COALESCE(NULLIF(artist, ''), ?)` 折叠进 UNCLASSIFIED）、文件夹（不读标签）、外内容 FTS5（两者索引成同一段空文本）三条观测面上都折叠成同一个桶，换序不可判别；顺序是防御性的，真正需要它的是 `query_library_page` 读路径。⑥ **收口**：本轮后实测 2214 行、开放 74 ＝ 代码 16 ＋ 设备 44 ＋ 决策 1 ＋ 台账 13、已关闭 1466（1463 ＋ 本轮关闭两条 ＋ 本记录行自身，沿 R124 口径）（行数口径本轮说明一次：「2214 行」沿用 R112～R124 的 split 口径，按内容行（wc / splitlines / `git diff --stat`，末换行不另计空位）实测 2213；本轮新增文件的行数一律按内容行记，所以是 `test_ui_renderer_ownership.js` 244 行而不是 split 口径的 245；开放/关闭条数按行首前缀计，与行数口径无关），0 个 CRLF；设备段 44 条一行未改；历史计数快照 155=64+82+9、115=51+43+8+13、88=24+43+8+13、82=22+44+3+13、80=20+44+3+13、77=18+44+2+13、76=18+44+1+13、74=16+44+1+13 并存不合并，一律以磁盘实测为准。`SOURCE_MANIFEST.sha256` 在全部源码编辑完成后刷新为 705 条（覆盖 `src/` 625 ＋ `android-client/` 80）并逐文件抽查 MATCH。终跑 `tools/test_offline.ps1` 见 `artifacts/offline-20260920-round191.log`。两笔提交均逐文件显式 pathspec；未碰 `.gitignore`，未跟踪产物一律不入库。
- [x] 2026-09-20：R124 代码轮（本轮记录插入后在盘上为 L2）：净关闭一条决策项（D9 曲库连接池开关上设置页），新立 0 条，代码桶保持 18 条。取证先行：插入前实测 2212 行、开放 77 ＝ 代码 18 ＋ 设备 44 ＋ 决策 2 ＋ 台账 13、已关闭 1461（一律按行首前缀计），0 个 CRLF；本轮条目定位全部用文本前缀长锚点，不用行号。① **实现**：`index.html` 运行 pane 末尾新增 `libraryConnectionPoolInput` 复选框与「即时生效、不需要重启」说明；`app.js` 新增顶层常量 `LIBRARY_CONNECTION_POOL_SETTING_KEY`、`runtimeConnectionPoolInput()`、`loadRuntimeSettings()`、`saveRuntimeSettings()`，`setSettingsTab` 切到运行 pane 即回读，`chooseCurrentFolder` 的 runtime 分支排在 metadata 分支与 `saveLibraryPathsFromDialog()` 兜底之前（否则在运行 pane 点保存会去存音乐库路径）；服务端 `GET`/`POST` `/api/config/runtime`，POST 只接受真布尔，非布尔 400 且不改写现值，提交经 `commit_config_update()`，两处响应都回读谓词结果而非回显请求。控件复用既有全局类 `.metadata-toggle`，`app.css` 未改。② **两处取证事实**：`_library_connection_pool_enabled()` 在键缺失时是 False，与 `config.py` 加载器默认 True 不同，所以面板只能读运行进程实际 honour 的谓词；`LibraryConnectionPool.snapshot()` 不含 enabled 字段，响应里带 `status` 只作为「关掉确实排空了句柄」的观察证据。③ **键名归属**：副本控制组抓到本轮的真实回归——既有守卫 `src/tests/test_server_lifecycle.py` 禁止 `server.py` 指名池键，而新路由一开始直接 import 了 `LIBRARY_CONNECTION_POOL_CONFIG_KEY`。本轮没有放宽旧守卫，而是在 `library.py` 增加 `library_connection_pool_config_key()` 作为唯一拼写出口，路由经它取键；本地单跑本轮 6 项新测试当时是绿的，漏的就是这条。④ **测试**：新增 `src/tests/test_ui_runtime_settings.js`（pane 归属与不侵入 metadata pane、端口重启提示未被挤掉、常量与服务端键逐字对齐、接线顺序、路由字符串两端对齐、`vm` 真跑读写的回显/不编值/单键真布尔/失败必抛/控件缺失五组断言）与 `test_http_integration.py` 6 项（值来源、作用域、文本布尔、缺键保持、排空发生在提交之后、持久化失败不动运行值）。⑤ **变异证明**：仓库外副本 `%TEMP%\fnaudio-r124-copy`（978 个文件）控制组先绿＝Python `Ran 2443 OK (skipped=3)`、Node 73 文件 0 失败；V1～V12（删运行保存分支、相信点击不回显、请求体发文本布尔、失败不再抛、删 pane 钩子、常量改名、控件移进 metadata pane、GET 硬编码 True、POST 改 bool 强转、排空挪到提交之前、短路掉提交、路由转公开）逐条被具名杀手以非零退出码杀灭，当场还原并复绿；副本 `skipped=3` 比本机多 1 项，是 `test_offline_verification_script.py` 因副本不含 `artifacts/` 跳过发布证据索引，属环境差异而非缺陷。⑥ **清单**：`tools/update_source_manifest.ps1` 刷新后 704 条（本轮新增 1 个测试文件）。⑦ **计数**：开放 77 → 76，决策 2 → 1（仅剩 R73 的 `allow_disk=False` 取舍，需真机取证），代码桶 18 不变，已关闭 1461 → 1463（翻转 1 条 + 本条记录）。设备段一行未改。
- [x] 2026-09-20：R123 代码轮（本轮记录插入后在盘上为 L2）：净关闭三条 —— L1872（D1 许可证：裁定开源 `GPL-3.0-or-later`、署名 `vinson023`、补 `NOTICE` 与 `AUTHORS`、暂不托管）、L71（队列三函数死码：证伪并删除，残余口径并入 L69）、L74（状态通道断开的最小可见降级指示：`#transportStateUnknown` 灯）。取证先行：三个目标条目在盘上各自都是单行，收口说明只能写在同一行末尾；插入前实测 2211 行、80 条开放、1457 条已关闭（均按行首前缀计；全文 `- [x] ` 子串另有 2 处出现在行内引用里，直接 count 会多算）、0 个 CRLF；本记录插在 L2 会使后续全部行号下移一行，故本轮一切引用一律用文本前缀锚定而非行号。删除侧＝`addQueue`、`addQueueAndPlay`、`playFolder` 连同其内部 `isPlayingNow()` 用法一起移出 app.js，`runTrackAction` 不再接受 `queue-play`，`git grep` 全仓 0 命中。新增侧＝`index.html` 在 `#elapsed` 之后插入静态文案的 `#transportStateUnknown`，`app.css` 用 ID 限定加 !important 让它活过 `.progress span` 的隐藏规则，`app.js` 新增 `transportStateIsUnknown`、`updateTransportStateUnknown`、`setDatasetStateIfChanged` 并在 `updateDeviceLabel`、`syncPlayerProgress`、`updateRemoteUi` 三处接线（阈值复用常量，未新设常数；状态来源复用现有时间戳，未新增连接标志位）。判别测试＝新增 `test_ui_dead_queue_entry_points.js`、`test_ui_transport_state_unknown.js`、`test_license_files.py`，并把灯的相关函数与常量注入 `test_ui_library_loading.js` 与 `test_ui_renderer_transport.js` 的既有写入成本测量。变异证明＝仓库外副本 `C:\path\to\fnAudio_r123_verify2` 控制组先绿（Python 2437 项 OK、Node 72 文件 0 失败），V1～V9 全部被具名杀手以非零退出码杀灭，逐条还原后复绿。清单＝`tools/update_source_manifest.ps1` 刷新后 703 条，`tools/takeover_forensics.py --full` 实测 drift 0、stale 0、unlisted 0。附带纠正：`app.css` 曾被写入 1 个 CRLF，而 `.gitattributes` 的文本归一化让它在 `git diff` 里完全隐形，只有按字节读并计数才抓得到——已改回裸 LF 并复刷清单。本轮新立 0 条，设备段一行未改。
- [x] 2026-09-20：R122 代码轮（本轮记录插入后在盘上为 L2）：净关闭两条代码待办 —— L216（同一个「播放位置」在四条投影里单位不一致）与 L222（`tools/apk-analysis` 与 `tools/runtime` 的处置方式），新立 0 条。① **实现口径**（细节写在 L216 的 ⑥～⑨ 与 L222 的裁定登记段，此处只记决定）：服务端成为唯一折算点，`cue_is_transcoded()` 一个判据同时供折叠与反向折叠使用，四条投影统一携带 `cue_segment` 与 `state_version` 两个显式字段，前端只认服务端声明、未声明才回落本地元数据。② **测试**：新增 27 项 Python 与 1 个新 JS 套件 `src/tests/test_ui_remote_cue_units.js`；控制组当场在仓库外副本 `E:/fnAudio_r122_verify` 复跑为 Ran 120 OK，JS 套件 exit 0，不是引用上一会话的结论。③ **变异矩阵**：M1～M13 全灭、控制组存活。其中 M7「SSE 路由退回 `snapshot()` 并丢掉第三个实参」是本轮收口复核时新发现的判别缺口 —— 上一会话的矩阵未覆盖它，补一条源码级接线守卫 `test_the_event_stream_publishes_the_snapshot_and_item_as_a_pair` 后复跑才全灭；两条接线守卫在测试文档串里就地标注为 wiring guard 而非行为覆盖，另有一处判据（声明只验布尔类型）按设计不可杀，已在文档串写明理由。④ **负责人四条裁定登记**（本轮只登记口径、不动代码）：L69 取 D 三段口径、L70 取 A 死码证伪加删码、L73 取 A 最小降级指示（阈值 10 秒、文案「状态未知」、位置在 `#elapsed` 之后、复用现有时间戳字段）、L150 取 A 加 C（口径入 docs，同时把写路径的 None 归一为空串并对旧库做一次收敛）；四条继续挂未勾选，实施排到 R123（L70、L73）与 R125（L69、L150）。⑤ **就地纠正上一会话两处过头陈述**：其一，「全仓没有 aria 反馈设施」不成立，`index.html:112` 有一处 `aria-live` 等于 polite，归删除对话框内的 `#deleteTrackStatus`，不是全局状态区；其二，L222 原写「可回收约 1.74 GB」，在「移出而非删除」的裁定下实测回收量为 0。⑥ **连带修正**：`docs/` 下 4 份研究文档共 18 处旧路径改为 `_external` 前缀，改后 `docs/` 内旧路径命中归零；三份根文档与历史条目里的旧路径按「历史不回填」保持原样。⑦ **计数**：开放 82 → 80 ＝ 代码 20 ＋ 设备 44 ＋ 决策 3 ＋ 台账 13，已关闭 1454 → 1457，其中 +2 是本轮真实关闭的 L216 与 L222、+1 是本条顶部记录自身也是勾选项，逐条按行首勾选标记实测并与 HEAD 版对账为 -2 开放 / +3 关闭。⑧ **门禁与边界**：终跑 `artifacts/offline-20260920-round187.log`；设备段 44 条一行未动；未改 `.gitignore`；未新增待办条目。 ⑨ **收口补记（提交授权生效之后）**：负责人已授权分提交，本轮现场以显式 pathspec 分 4 次提交入库（源码与测试与清单 15 项 / 研究文档 4 项 / 根文档 3 项 / 承载本补记的文档提交 2 项），未使用 `git add -A`、未改 `.gitignore`，`artifacts/`、`music/`、`tools/` 下未跟踪物一项未入库。终跑更正：⑧ 所指 round187 之后，磁盘取证发现 `src/app/server/playback_cue_position.py` 末尾多出 1 个空行（HEAD 与同目录其余 5 个 Python 源均按单换行收尾），修掉这 1 字节后重跑门禁为 `artifacts/offline-20260920-round188.log`（Ran 2432 / 112.646 秒 / OK skipped=2 / exit 0），本轮终跑以 round188 为准；修后复跑变异矩阵仍 M1～M13 全灭、控制组 120 项绿、清单 700 条复刷幂等、取证 listed=700 drift=0 stale=0 unlisted=0。另记两点：其一，本轮变异 harness 自身复盘出 3 个缺陷（M3 锚点重复命中、M8 属语义等价假变异、子进程经 cmd.exe 报「路径语法不正确」被误判为杀灭），已改为先证明确实执行过再判定；其二，`src/tests/test_playback_event_presentation.py` 的 `__main__` 守卫之后多出 1 个空行随提交入库，纯样式无害，留待下一轮顺手清掉。
- [x] 2026-09-20：R121 决策落地轮（本轮记录插入后在盘上为 L2）：负责人对 8 条需产品决策项逐条给出裁定，本轮把它们全部落到磁盘，未改任何生产代码。① **版本库基线**：提交范围 B 已执行，HEAD 由 `b0a19d8`（R120 收口的最小提交）前进到 `89ded0132278b84f6d187b9638f1dda776fdf26b`（首行 `chore: land the project baseline into version control (scope B)`），分次显式 pathspec 暂存 607 条（src 522 / android-client 48 / tools 24 / docs 7 / 根文档 5 / .github 1），未使用 `git add -A`；暂存集合内无 `.zip`/`.fpk`/`.sqlite3`/`.log`/`artifacts/`/`references/`/`node_modules`；**关键闭合**：R120 发现的「`SOURCE_MANIFEST.sha256` 699 条里 450 条不在版本库」缺口实测归零（`manifest entries not tracked by git: 0`）。`.gitignore` 一个字未改。② **八条裁定**：D2 接受临时密钥（登记后果：换密钥后已装 APK 不能无缝升级）、D3 AcoustID/Chromaprint 永久关闭并把代码桶原 L1817 并入本条、D4 接受 root（真机三前提实测：服务账号 `uid=996 fnaudio` 存在但不在 `audio` 组 / `@appcenter`+`@appconf` 实测 `drwx------ root` 且 0700 的成因是打包脚本 `umask 077` + `install -d -m 700` / `/dev/snd/*` 0660 gid=29 且 `runuser -u fnaudio` 六项 `access()` 全 False，对照 moode 用自己的 `moode` 用户跑 mpd）、D6 批准两脚本进库（**并更正原文**：`tools/test_offline.ps1` 实测 0 处引用，真实引用面 7/15/3 已重测）、D7 `tools/blutter` 移出版本树（→ `C:\path\to\fnAudio_external\blutter`，3539 文件 / 69.6 MB / 自带 `.git` 只读 pack 完整 / 全仓无脚本与测试引用）、D8 保持 50000（实测设备 favorites 仅 3 行，`MAX_PERSISTED_FAVORITES` 是淘汰上限非预分配）关闭；D1 因许可证文本仍未选定而保持开启（收窄到「选哪份 + 要不要 NOTICE/AUTHORS」）、D5 因样本只有 6 行且 6/6 带完整索引身份（对本条要问的问题零信息量）而保持开启。③ **C2 拆分**：原代码桶 L154 连接池条按裁定拆成两半——真机半进 P0 段（本轮记录插入后在盘上为 L1863，含「先回退 `library_connection_pool` 再排查，别在设备上加兜底逻辑」的操作指引与 R62 的历史结论），产品半（设置页要不要暴露该开关）进决策段 D9（插入后为 L1879）。④ **计数收口**：开放项 88 → **82 = 代码 22 + 设备 44 + 决策 3 + 台账 13**；代码桶 24 → 22 的来源**只有** L1817 并入 D3 与 L154 拆走两条，**本轮没有靠修改代码关闭任何条目**，新立可离线代码项 0 条 ≤ 关闭数 ✓；决策段 8 → 待决 3。四桶按 R113 书面规则从磁盘重算（`%TEMP%\r121_dev\buckets2.py` 按标题定位区间，不写死行号）：同一脚本对改动前的 TODO 复算得 88 = 24 + 43 + 8 + 13、设备区间 877 行、digest 前缀 `63661836771c36e0`，与 R120 登记值逐字相符 ⇒ 口径一致，不是本轮另造的算法。⑤ **设备段 digest rebaseline**：P0 段因 ③ 新增 2 行，设备五行标题区间逐行拼接（段间与行间都以 `\n` 连接、序列末尾不加换行、UTF-8）的 sha256 前缀由 `63661836771c36e0`（877 行）变为 **`19c1120fc68538c9`（879 行）**；旧前缀自本起作废，但它仍是「R121 之前设备段一行未改」的有效证据，留在 R120 记录里不追改。⑥ 本轮**无生产代码改动 ⇒ 没有可变异对象，仓库外副本变异矩阵本轮不适用**（写明未做，不当作已做）；控制组的绿由本轮终跑门禁 `artifacts/offline-20260920-round186.log` 承担（round184 已全绿，但其 mtime 早于随后一次事实纠正；按规则换号重跑的 round185 反而 FAILED，唯一 error 是 `tests.test_large_library_benchmark` 里那条池化计时守卫，取证结论是机器上有一个外来 python 进程占满一核、而不是代码变慢：终止该进程后单跑该模块连绿两次（1.998s、1.952s），事故与修法按「新发现问题当轮并入既有条目」登记进本文件 L155，未另立新项，本轮新立可离线代码项仍为 0；round184 与 round185 两份旧日志都保留不删，详见 CHANGELOG 同轮末条）。⑦ 现场：分支 main、无 MERGE_HEAD/rebase/cherry-pick/bisect/revert 残留、staged 0、stash 0；基线提交后 `git status --porcelain` 残留 672 条 = 667 `??`（artifacts 门禁日志为主）+ 4 ` D`（`artifacts/0.1.174/` 四个已跟踪文件被范围 B 排除后留下的删除，故意未动，待负责人裁定是恢复还是提交删除）+ 1 ` M`（`tools/browser-e2e/tests/ui.spec.js`，已跟踪但在 tools 子目录故 B 未含，并入本轮收口提交）。⑧ **R122 首个代码项** = 本文件 L216（R121 改写后）的「CUE 播放位置在 core/会话/SSE 三条投影里是整文件秒数、在 `/api/playback/status` 里是轨内秒数」缺陷，需配判别测试 + 变异矩阵；仍待负责人裁定的阻塞点：决策段 D1（具体许可证）、D5（真实曲库样本）、D9（池开关是否上设置页），代码桶 L222（`tools/apk-analysis` 1.80 GB 与 `tools/runtime` 1.43 GB 的处置，写 `.gitignore` 已被否决），以及 `artifacts/0.1.174/*` 四个删除的处置。
- [x] 2026-09-20：R120 净关闭一条代码项：TODO L66（本轮记录插入后在盘上为 L67，勾选项按文本锚定而非行号）「R65 进展登记：state_store.py 363 行本轮读完……cover_cache.py 与 dlna/service.py 的并行只读审计结论尚未落地，落地后另轮记录」（完成口径 = 两份审计结论都落地并登记，本轮整件事做完）。① cover_cache.py 审计查出并修掉一处真实缺陷：prune_cover_cache 第三层字节预算循环按「先 asset 后 aliases」删、且删之前不看删除预算 —— 当 COVER_CACHE_SWEEP_DELETE_LIMIT 在一个 unit 中途用尽时，磁盘上留下名字指向已被删 artwork 的 .asset 别名，正是同文件 L694-695 注释自己声明 never survives a sweep 的那个形状；allow_disk=False 的页面路径不复核磁盘，_ASSET_ALIAS_CACHE 会继续向浏览器 advertise 一个 404 的 cover-asset/<id>（这也是 _forget_advertising_asset 存在的原因）。发布侧「先写 asset 再写 alias」是有意顺序，撤销必须镜像它，否则崩溃窗口留下同样的悬空别名。修复 = 把一个 unit 定为该循环可拿走的最小单位：动任何文件之前先按 len(aliases) + 1 预留额度，alias 删不动时整个 unit 退出本轮且不再往后波及较新的 unit（新 L739-769 替换原 L739-748，该文件其后行号一律 +21）。② dlna/service.py 审计未发现缺陷，两处可疑点当轮证伪、不另立新项：_didl_item L1200 的 any(name.startswith("res@")) 后半段是 include() 内部已做的重复判断（死代码而非缺陷）；DlnaEventService._timeout L622 的 int(match.group(1)) 无位数上限（py3.11+ 超约 4300 位抛 ValueError），但 app/server/server.py:1271 已 except ValueError 转 412，不会 500、也不会卡住订阅路径。③ 更正旧行数口径（本轮磁盘实测，旧记作废）：cover_cache.py 修复前 1343 行 / 58035 B（旧记 1021）、修复后 1364 行 / 59239 B；dlna/service.py 1220 行 / 67928 B（旧记 957）。④ 判别性测试：src/tests/test_cover_cache.py 1619 → 1718 行，CoverCacheSweepTests 新增 _assert_no_alias_names_missing_artwork()（逐个 .asset 用 _alias_asset_path 验磁盘目标存在 + 遍历 _ASSET_ALIAS_CACHE 验被 advertise 的 asset 文件存在）与三支用例：test_the_delete_budget_cannot_be_spent_across_a_unit（一 asset 两 alias、额度 2、disk_has_reserve 置 False ⇒ prune==0 且三件都在）、test_a_unit_that_fits_the_budget_is_reclaimed_whole（额度 3 ⇒ prune==3 全删，防「预留」退化成「永不淘汰」）、test_an_alias_the_volume_keeps_backs_the_whole_unit_off（卷扣住第二个 alias ⇒ prune==1、stuck alias 与其 asset 都还在、较新的第二个 unit 未被波及）。实跑：模块 90 项 OK、CoverCacheSweepTests 单类 14 项 OK。⑤ 仓库外副本 E:/fnAudio_r120_cp（robocopy 排除 .git、artifacts、android-sdk 等，443.84 MB / 4224 文件 / 1735 目录）控制组先绿：Python Ran 2405 tests OK (skipped=3)、JS declared scripts 58 / js files 69 / passed 69 / failed 0；变异矩阵 V1～V6 全灭且逐条命中指名杀手（V1 整段回退为本轮修改前字节 ⇒ 杀手两支；V2 保留额度预留但恢复先删 asset ⇒ volume_keeps_backs；V3 预留少算 asset 那一笔 ⇒ delete_budget；V4 额度刚好够也拒绝淘汰 ⇒ fits_the_budget；V5 摘掉 stuck 判定 ⇒ volume_keeps_backs；V6 stuck 时 continue 取代 break ⇒ volume_keeps_backs），每条按变异前字节快照还原（restored=True）、矩阵跑完后控制组再绿 exit=0、SURVIVORS=0，副本与活树逐件 sha 全 SAME 后删除副本（E 盘现存 fnAudio、fnAudio_r118_deleted_backup 与本轮新增的变异基线 fnAudio_round120_prechange；副本 `E:/fnAudio_r120_cp` 实测已删，两份 .orig 留在该基线目录里，收口时不删）。⑥ 本轮新立可离线代码项 0 条 ⇒ 代码桶 25 → 24、开放项 89 → 88（88 = 24 + 43 + 8 + 13，按 R113 书面规则重算：顶部段 21 条 + 三条具名散条目 L543 持续审查未完成范围 / L1817 Chromaprint-AcoustID / L1835 继续按可测试边界拆分 = 24（本轮记录插入前分别是 542 / 1816 / 1834）；设备 43、决策 8、台账 13 一条未动，设备段一行未改）。⑦ 现场与授权：分支 main、HEAD 仍是 d362047a082d5487a51471a1fabc220f784ae807、无 MERGE_HEAD/MERGE_MSG/CHERRY_PICK_HEAD/BISECT_LOG/REVERT_HEAD/AUTO_MERGE/rebase-merge/rebase-apply 残留、staged 0、stash 0、git status --porcelain 1279（` M`147 / ` D`6 / `??`1126）；用户本轮明确答复「授权提交 / git add」，该项硬禁止已解除；但全量提交仍不安全——未跟踪项里含 tools/android-sdk（10.0 GB）、tools/apk-analysis（1.80 GB）、tools/runtime（1.43 GB）、artifacts 门禁日志（644 条 / 1.68 GB）、references（398 MB）等外部与可再生产物，而 .gitignore 仍在禁改之列（TODO L222，插入前 L221：用户已否决把这两个 tools 目录写进 .gitignore）。处置：本轮按最小范围提交（本轮源码两件 + 测试一件 + 三份根文档 + 清单），全量基线提交的范围作为新的裁定项呈交用户（不新立代码待办，不改变 88 的桶数与四桶切分）。⑧ 历史计数并存不合并：目标正文快照 155 = 64+82+9、R99 实测 115 = 51+43+8+13、R116 记 95、R117 记 94、R118 记 90、R119 记 89、本轮 88。
- [x] 2026-09-20：R119 净关闭一条代码项：L84「R59 补记立案：`src/app/server/playback_session_contract.py`（139 行）与 `src/app/server/alsa_player.py`（179 行）都没有生产消费者，只有各自的测试在跑……取证后三选一：接回真实调用点、移出发包目录、或删除并连带清理测试；不要凭印象动手」，取第二路「移出发包目录」——两模块整体移入新建的 `src/tests/unwired/`（sha256 与移动前逐字节相等：alsa `AA035E4B…4917`、contract `3E5D3557…81D5`，仓库外备份 `%TEMP%\r119_backup` 对拍），`build_release.ps1:214` 的 `robocopy /E /XD tests __pycache__` 与 `:394-395` 的 payload 拒 `tests` 守卫让它们彻底离开 fpk，而 `update_source_manifest.ps1` 仍逐文件哈希它们 ✓ 第一路被总闸扫描否掉：移动前 `src/app` 下 192 个 .py 里零引用者恰好只有这 2 个（移动后 190 个里 0 个），从来没有调用点可接，硬接等于新造功能 ✓ 第三路被两条不可恢复性否掉：`alsa_player.py` 工作树 178 行对 HEAD 95 行（净 +83 行未提交改动，删了无法从 git 找回）、`playback_session_contract.py` 未被跟踪且正是 6 条 `Android 等价 MediaSession` 设备项所等的契约资产 ✓ 400 文件引用语料 + `git grep HEAD` + 打包/设备脚本三条取证链全部 0 命中 ✓ 两支测试改指新路径且用例数不变（10 / 7 项） ✓ 新增判别测试 `src/tests/test_orphan_module_retirement.py` 10 项（双向：既拦 `src/app` 树里再长出零消费者模块，也拦迁移过头、打包守卫被削弱、清单漏列） ✓ 仓库外副本 `E:/fnAudio_r119_cp2` 控制组先绿（Python `Ran 2402 tests` OK (skipped=2)、69 支 JS 逐个 node 退出码 0），M1～M10 十条变异全灭、逐条命中指名杀手、SURVIVORS=0、CONTROL RESTORED=True、副本已删 ✓ 本轮新立可离线代码项 0 条 ⇒ 代码桶 26 → 25、开放项 90 → 89（`89 = 25 + 43 + 8 + 13`，按 R113 书面规则重算） ✓ 设备 43 / 决策 8 / 台账 13 一条未动、设备段一行未改 ✓ 历史计数并存不合并：目标正文快照 155 = 64+82+9、R99 实测 115 = 51+43+8+13、R116 记 95、R117 记 94、R118 记 90、本轮 89。 二次接管补记（同一轮，不另立项）：仓库外副本仍在盘上时逐条重跑 M1～M10 复验全灭（控制组先绿、每条按变异前字节快照还原、收尾副本与活树逐件 sha 全 SAME 且无残留，之后删除副本），并更正前一条变异记录里 M3 与 M9 的杀手名单——新建模块还会连带红一般性清单断言，而 `test_the_moved_alsa_player_is_still_the_manual_cli_it_was` 对「删 `import argparse`」不判别（真红的是 `test_alsa_player` 那三支 CLI 拒绝用例），详见 CHANGELOG_AI.md 顶部 R119 二次接管复验条；同次接管另修掉 PROJECT_CONTEXT.md L2 一处落笔字符缺陷（U+B000 谚文字母加字符 0 应为「筛」），并把根文档自检从「只扫控制符」升级为「按码位段扫」，三份根文档异常码位实测 0。
- [x] 2026-09-20：R118 净关闭两条代码项：L84「`if False and` 恒假路由块共 7 处……要么把这组功能正式关掉（删块 + 删只被它引用的 `fnos_api.py` 入口与 `test_app_lifecycle_*` 里的相应断言），要么用配置开关代替恒假字面量」与 L87「`covers/assets` 存储没有聚合上限……总条目数与总字节无人看管……清理不得与 `_key_lock` 的在飞渲染互相踩」。:84 取第一条路（正式关掉），依据是第二条路在本项目里打不开——死块调用的 `get_shared_accessible_folders`/`del_shared_accessible_folder` 在旧 server.py 全文只出现在块内三处（按提交态 HEAD 复取为 server.py L709/L998/L1034，删除前的工作树行号已不可复核），而 `from fnos_api import` 只取了 `FnosApiError, call_trim_api`（`call_trim_api` 除导入行外零使用），开关置真只会把「看着可用的死路由」换成必崩的 NameError。删除量（按本轮磁盘前后差实测）：server.py −63 行（3390 → 3327）、cgi_proxy.py −218 行（727 → 509）、test_cgi_proxy_auth.py −149 行（626 → 477，八个死函数测试 40 → 32 项，service_port 四支与真活跃前缀测试原地保留）、tools/ui_e2e_fixture.py −2 行（322 → 320）；整文件删除 `src/app/server/fnos_api.py`（143 行）与 `src/tests/test_fnos_api.py`（98 行 / 9 项），后者原本未跟踪、删了无法从 git 恢复，两份备份留在仓库外 `C:\path\to\fnAudio_r118_deleted_backup`。删后取证：`if False and` 与 `/api/fnos` 在 server.py、cgi_proxy.py、ui_e2e_fixture.py 全部 0 命中，`fnos` 只剩 server.py L754/755/1573/1668 四处合法注释与 cgi_proxy L74/L331/L399 三处（L331 是 `"fnos-token"` cookie 名，L74 与 L399 是注释） ✓ 诚实记录出入：条目点名的「`test_app_lifecycle_*` 里的相应断言」磁盘上不存在（`test_app_lifecycle_scripts.py` 全文 23 项，唯一带 fnOS 的是安装目标软链，与本组无关），那半句要求是空集，不假称已删 ✓ :87 是重复登记式证伪关闭：条目四项要求逐条落到 `test_cover_cache.py` L1485/1498/1518/1525/1546/1575 与 `cover_cache.py` L734 / L570 / L731，唯一没实现的「总条目数封顶」自 R75 起就是 L32，本轮关掉的是这处重复登记、要求本体一行不减，L32 继续开着 ⇒ 关闭不减轻任何未完成要求 ✓ 判别测试新增 `src/tests/test_fnos_route_retirement.py` 10 项（双向：一半拦死代码复活、一半拦删过头）与 `test_http_integration.py` 2 项 404 行为钉（文件 1468 → 1498 行、模块 78 → 80 项）✓ 仓库外副本 `E:/fnAudio_r118_cp` 控制组先绿（Python Ran 2392 OK skipped=3、69 支 JS 逐个 node 退出码全 0），V1～V9 九条变异全灭且逐条命中指名杀手，其中 V1（以活条件复活 GET 路由）同时被源扫描与本轮新增的 404 行为钉抓住 ✓ 本轮新立可离线代码项 0 条 ⇒ 四桶按 R113 规则复算 92（28+43+8+13）→ **90（26+43+8+13）** ✓ 设备 43 / 决策 8 / 台账 13 不变 ✓ 插入本条后原 L84/L87 起其余行号整体 +1（行号不是条目身份）。
- [x] 2026-09-20：R117 净关闭两条代码项：L130「albums 的两条排序索引最贵、八条是否还在被计划使用，删之前逐方向 EXPLAIN QUERY PLAN 验一遍」与 L143「组/目录浏览游标还是前缀范围 + 页面 OFFSET 的老形状」。:130 的复核结论是八条全部活着、一条都不能删，归属矩阵四张组表同形：首屏/翻页 ASC 只点 _asc、DESC 只点 _desc；游标续页第一条（组内尾）两个方向都点 _desc（次键恒 name ASC）；续页第二条（后续组范围）ASC 点 _asc、DESC 点 _desc；带搜索的 JOIN 页与 owner 过滤 albums 两条路径都不点这八条（前者走主键 autoindex、后者根本不读组表），少了这一格就会有人把只被两格点名的 _asc 当冗余删掉。成本侧同时更正测法：逐条独立副本差分给出每条 +3.094 MB（100k 组、平均 20 字节组名、32.4 B/组）、八条完全一致，短名（10.8 字节）+2.289 MB/条，条目原话的 6.7 MB/100k 与本方法学下单表两条 6.19 MB 相符；而 R116 用的累计 VACUUM 差分对逐条拆分有系统性伪差（第一条 3.09、后续条 4.41 MB），配对总额 6.5 MB 仍成立、逐条拆分作废。:143 属前提与要求都已被后续轮次实现而条目未翻：browse_cursor_where 在两个服务端模块源码 0 命中、三个续页调用点全部走两读、游标页强制 offset=0，「先索引后形状」的前置条件也已成立。新增判别测试 src/tests/test_library_sqlite.py L1266 与 L1407（文件现 3491 行），仓库外副本控制组先绿（Python Ran 2397 OK skipped=3、JS 69 支 0 失败），V1～V13 十三条变异全灭，其中 V11 只被本轮新测试杀死。
- [x] 2026-09-20：R116 净关闭一条：「2026-09-17：组/目录浏览游标拿不到索引 seek（本轮只测量、未改动）：`browse_cursor_where()` 形状已经正确，缺的是索引——组表没有任何 name 排序索引，`folders` 只有 `(root,parent,name)` 且 `name` 是二进制排序…需同时给出组表 `(name COLLATE NOCASE, name)` 与 `folders(root,parent,name COLLATE NOCASE)` 两条索引并评估写放大。」（原 L157，本条插入后在 L158）✓ 那个行号是插入本条之前的位置 ✓ 翻转后的这条现在在 L158 ✓ 插入后 L158 起其余行号整体 +1（行号不是身份）✓ 关闭方式＝取证证伪：条目点名的六条索引早已全部在 `library.ensure_library_schema()` 里（组表 library.py L2260-2267 ✓ `folders` root-scoped 对 L2377-2384 ✓ parent-only 对 L2394-2401 ✓ 二进制排序遗留索引 L2402 已 DROP），条目要求的「评估写放大」本轮补做并落档：+68 B/组、+869 B/目录、插入最坏 +0.0014 ms/行 ✓ 带索引 18/18 条续页语句零 TEMP B-TREE、摘掉六条索引后 14/18 退化、慢两到三个数量级 ✓ 唯一真实缺口＝续页两条语句的 SQLite 计划从未被钉过（普通页早就钉了），本轮新增 test_browse_cursor_continuations_keep_their_index_seek_plan 补上，变异 V1~V8 全灭 ✓ 本轮新立可离线代码项 0 条 ⇒ 代码桶 31 → 30、开放项 95 → 94 ✓ 设备 43 / 决策 8 / 台账 13 三类计数不变。
- [x] 2026-09-20：R115 净关闭一条：:60「总量上限若从 50000 再往上调，`GROUP BY playlist_id` 的一次全索引扫描会成为新的常数项……配套的是持久化每个播放列表的行数计数，而不是回到逐列表 COUNT」（原 L60，本条插入后在 L61）。做法与关闭注记见该条本体；要点是 `playlists.track_count`（可空，NULL=未知）+ `state_count_policy.children_are_within_budget()` + `state_meta.playlist_children_verified` 三件套：先读 `LIMIT cap+1` 拿前瞻行判溢出，标记与预算都过才走「一条子表语句都不发」的快路径，否则清扫一次、落标记、`_REFETCH_TRACK_COUNTS_SQL` 取权威值后再决策。1e6 子行实测：旧固定成本 240 ms/每次保存 → 快路径 0.77 ms，慢路径 230.56 ms 只付一次；条目原文 16 ms 为磁盘旧测值，本轮内存库复测分组计数 37 ms，结论不变。测试：新增 `state_count_policy.py`（86 行）+ `test_state_count_policy.py` 9 项 + `test_state_store.py` 新增 `PersistedPlaylistCountTests` 17 项（含旧库升级、自愈、快路径零子表语句、与 R65 参考实现对拍、高估不删行、孤行清扫只付一次、两条写路径各自记账、失败保存不留计数、无标记库不得走快路径、超量列表不得走快路径、二次全量保存与过期增量保存都不许少报自己的行数、源码级「分组计数扫描已从写入者消失」「playlist_tracks 只有 state_store 一个写入者」）；`test_state_store.py` 现 1510 行（`StateStoreTests` 37 + 本轮新增 `PersistedPlaylistCountTests` 17 = 54 项全绿）。本轮另修两处自己写出的测试缺陷：`_true_counts()` 用 `GROUP BY` 看不见零子行列表（改为对每个父行做相关子查询）；`_use_tiny_caps()` 后在 `finally` 里用 `self._caps()` 还原等于把 3/4/7 再写回去并泄漏给后面的类（新增 `PRISTINE_CAPS` + `setUp` 守卫 + `tearDown` 还原，并加 `_caps_are()` 让用例可以改上限而不留残余）。仓库外副本 `C:\path\to\fnAudio_r115_cp` 控制组 Python 2394 项 OK(skipped=3) + 69 个 JS 全绿，15 个具名变异 V1～V15 全灭，副本已删。按 R113 写在纸面上的规则重算：开放项 96 → 95 = 代码 31 + 设备 43 + 决策 8 + 台账 13，本轮不新立任何可离线代码项。
- [x] 2026-09-20：R114 净关闭一条：「组浏览页现在剩下的固定成本是那条 `SELECT COUNT(*) FROM <组表>`：100k 组实测 4.33ms，占修后单页 5.0ms 的八成，因为它仍要扫一遍主键覆盖索引。候选做法是把四张组表的行数写进 library_meta（与 track_count/dsd_count 同一口径），让总数变成一次主键命中。风险要一起处理：总数一旦漂小，客户端的 has_more 会提前判定读完、列表被截短，所以做的时候必须带一条自愈核对（读到的持久化计数与真实行数不一致就以真实值为准并回写），不能只加写入点。」（原 L132）✓ 那个行号是插入本条之前的位置 ✓ 翻转后的这条现在在 L133 ✓ 插入后整体 +1 ✓ 本轮新立 0 条 ⇒ 代码桶 33 → 32、开放项 97 → 96 ✓ 设备 43 / 决策 8 / 台账 13 各条未动 ✓ 桶间搬迁 0 条。 计数先更正再引用：上一份交接摘要按「L1827 那条已翻 [x]」推出代码桶 32，那是把行号当身份产生的产物 —— R113 插入顶部记录后该散条目整体 +1 漂到 L1828 且仍开放；本轮按 CHANGELOG_AI.md 已书面化的「R113 分桶规则」以节标题+文本锚定重算，得 97 = 代码 33 + 设备 43 + 决策 8 + 台账 13，四桶两两不相交、并集 = 97。 关闭方式严格按条目原文的两步走 —— 既加写入点，也带上它点名的自愈核对。写入侧 src/app/server/library.py（现 3048 行）:1168 `_refresh_group_counts(conn)` 对 albums/artists/composers/genres 各跑一条 `SELECT COUNT(*)`，经 :1147 `_save_library_meta_count()`（先判型再 INSERT OR REPLACE，写失败吞异常）落到 library_meta 的 group_count_albums / group_count_artists / group_count_composers / group_count_genres，与 track_count/dsd_count 同表同口径；调用点穷尽为 2 处 —— :2416 在 group_label_version 迁移重建四表之后、:2600 在扫描事务尾部紧接 dsd_count ⇒ 派生值由表本身算出、不按增量补丁维护，结构上不会漂。读取侧 :1575-1602 只在未过滤的整表浏览分支使用持久化总数：:1585 `group_count_key(table, search)` 对任何非空 search 一律返回 None（策略不依赖调用者已 strip）✓ :1587-1591 缺键走 `counted_page_rows()` 并立刻回写自愈 ✓ :1592-1602 有键则按 `LIMIT limit+1` 读展望行交给纯函数 `browse_page_total()`：短页 ⇒ `offset+row_count` 就是精确总数（修漂大）✓ 满展望行 ⇒ 只在 `saved < offset+row_count` 时判漂小为 refuted 去读权威 count ✓ `count != saved` 一律回写 —— 正是条目要求的「不一致就以真实值为准」。`has_more` 表达式与 `project_group_rows()` 一字未改，展望行被自然截断 ✓ 读连接可写、`library_db_connect`（:2065 ✓ @contextmanager 在 :2064）在 `yield conn` 之后执行 `conn.commit()`（:2102）⇒ 回写成立。 判别测试净增 14 条：src/tests/test_library_count_policy.py 41 → 92 行 / 9 项（:47 四视图各用各键 ✓ :54 任何收窄一律拒键 ✓ :64 短页修漂大 ✓ :72 满页只修漂小 ✓ :79 脏入参一律 refuted）✓ src/tests/test_library_sqlite.py → 3152 行 / 131 项（:2972 扫描持久四表计数 ✓ :2986 未过滤页不再付 COUNT(*) 且三页走完 ✓ :3003 漂小不得截断列表并回写 ✓ :3020 满页修漂大 ✓ :3034 缺键首次读取自愈回写 ✓ :3049 search 页绝不读键 ✓ :3066 跨键污染检测 ✓ :3095 写入器契约：-1/True/1.0/"3"/坏键/坏连接一律拒写而 5 与 0 可写 ✓ :3122 增量重扫刷新计数）；另把旧测试改名为 :2132 `test_unfiltered_group_page_reads_an_indexed_page_and_a_persisted_count`（原 …and_a_separate_count），语句快照只截第一次调用 ⇒ `LIMIT 2 OFFSET 0` 计数断言为 1。两套件合跑 Ran 140 OK ✓ 全量 Python Ran 2368 / OK (skipped=2)。 变异证明：仓库外副本 E:/fnAudio_r114_cp 控制组 Python Ran 2368 OK (skipped=3) 与 JS 69 files failed=0 先绿 ⇒ V1–V14 全灭（mutants=14 killed=14 survivors=0 broken_anchor=0，逐条打印指名杀手测试，无等价变异）⇒ 还原后 4 个改动文件与主树 Get-FileHash 逐一 MATCH ⇒ 副本已删。 边界：L127「组表索引复核」要的是持久化计数**且**浏览改前缀 seek 都落地之后的复核，本轮只做前半 ⇒ 保持开放。未提交、未 git add、未碰 .gitignore ✓ 设备段一行未改 ✓ 终跑 artifacts/offline-20260920-round171.log。
- [x] 2026-09-19：R113 净关闭一条：「`library.py` 里 `cue_end` 用 `or` 从 0.0 退回整轨时长，于是「这是该文件的最后一轨」与「结尾未知」共用同一个 0.0 …… 若要区分，得先把结尾改成 None 并逐个检查消费方」（原 L108）✓ 那个行号是插入本条之前的位置 ✓ 翻转后的这条现在在 L109 ✓ 插入后整体 +1 ✓ 本轮新立 0 条 ⇒ 代码桶 34 → 33、开放项 98 → 97。 关闭方式严格按条目原文的两步走。第一步把「结尾」改成三态：src/app/server/cue_parser.py（现 141 行）`_attach_track_ends` 的 :29-42 docstring 写下三态定义 ✓ :79 `track["end"] = stack[-1] if stack else (None if superseded else 0.0)` —— 正数=同文件后继轨的起点 ✓ `0.0`=这张表在该文件上再没有任何后继轨、它确实跑到文件末尾 ✓ `None`=有后继轨但没有一个起点更靠后（平手或乱表）⇒ 边界未知；另 :55-63 把非字符串 `file` 那一支从 `0.0` 改判 `None`（未分组轨不许冒充末轨）✓ :65/:77 的 `superseded` 只在原本就要 `stack.pop()` 时置真 ⇒ R105 立下的 `observe` seam 计数与 :66-72 的比较谓词一字未动。第二步逐个检查消费方：① 归一化收进新纯函数 src/app/server/cue_numeric_policy.py:24-46 `cue_segment_end()`（现 49 行 ✓ `__all__` 同步）——只有 `0.0` 这一态允许借用文件时长 ✓ `None`/负数/非有限值一律回 `0.0`，而 `0.0` 正是写库列 `cue_end REAL NOT NULL DEFAULT 0` 早就用来表达「无已知结尾」的哨兵 ⇒ schema 一行未改；② `cue_item_presentation.build_cue_item` :10 与 ③ `playback_cue_position.normalize_cue_position` :48 的守卫都已是 `cue_end > cue_start` 形状 ⇒ 未知边界呈现为 0 长段、播放侧既不钳位也不报 finished ✓ 这两个文件本轮**只加注释不改逻辑** ⇒ 不冒充「顺手修了两处」；④ 本轮新查出的三个消费方：`library_write.py:144`/`:152` 用 `safe_float(source.get("cue_end"))`（`None` → 0.0 与列默认一致）✓ `metadata_job_payload_policy.py:14` 把 `cue_end` 原样带进作业载荷 ✓ 前端 `app.js:2462` 已按 `Number(item.cue_end || 0) > 0` 判「有没有已知结尾」⇒ 未知不会被误判成播完。 判别测试：全量 Python 2348 → 2354（+6 ✓ skipped=2）——`test_cue_parser.py` 18 → 21 项（参照实现 `_reference_ends` 同步改三态 ✓ 随机差分新增 `states` 集合断言：三种结局必须都出现过 ✓ :160 表驱动钉 `cue_segment_end` 拒绝发明时长）✓ `test_cue_item_presentation.py` :22 新增「未知边界呈 0 长段」✓ `test_playback_cue_position.py` :24 新增「未知边界永不 finished、永不钳位」（带已知边界对照）✓ `test_media_formats.py` :78 端到端三轨表断言 `cue_end` = `[240.0, 0.0, 300.0]`（只有末轨借到 300.0）。 变异证明：接管后**不复用上一份执行的说法**，在仓库外副本 E:/fnAudio_r113_cp 上重跑一次 —— 控制组 Python `Ran 2354 / OK (skipped=3)`、69/69 JS 套件先绿（副本比仓库多的那 1 个 skip 经核是缺 release evidence 的既有跳过项，不是新现象）✓ V1–V13 13/13 全灭（分层击杀见变更文档同轮记录）✓ 还原后 9 个文件与仓库逐一 `Get-FileHash` MATCH ✓ 副本与 %TEMP% 脚本随后删除。 计数一律从磁盘重新取证并四组并存：目标正文快照 155 = 64 + 82 + 9 ✓ R99 快照 115 = 51 + 43 + 8 + 13 ✓ 本轮开头实测 98 = 代码 34 + 设备 43 + 决策 8 + 台账 13 ✓ 收尾实测 97 = 33 + 43 + 8 + 13 ✓ 互不合并、互不覆盖；台账桶那 13 条这一次给出了可重算的显式规则（见变更文档「R113 分桶规则」条），上一轮交接摘要猜的「第 13 条在顶部段」经磁盘复核是**错的**，它其实是 L783。 未提交、未 git add、未碰 .gitignore ✓ 设备段一行未改 ✓ 清单与门禁见同轮记录。
- [x] 2026-09-19：R112 净关闭一条：「上一轮读过的首屏前端链路（`src/app/ui/app.js` 的 librarySnapshotKey / restore|persist|scheduleLibraryPageSnapshot、renderTrackRows、commitTrackListHtml 的按键复用、reuseSnapshotTrackMarkup + fetchLibraryResponse 合并、loadPagedLibrary / loadPagedLibraryWorker、fetchAllTracksForCurrentView）未发现缺陷，结论要正式补记进变更文档，避免下轮重读」（原 L132）✓ 那个行号是插入本条之前的位置 ✓ 翻转后的这条现在在 L133 ✓ 插入后整体 +1 ✓ 本轮新立 0 条。真正写代码的那条 L140「`has_more: True` 但没有 `next_cursor` 还剩两条路径」本轮**不关闭** ✓ 插入后在 L141 ✓ 改写为残余清单继续开着 ⇒ 代码桶 35 → 34、开放项 99 → 98。 关闭方式是这条自己要求的「补记」：把结论落到能引用的行号与既有测试名上——`librarySnapshotKey` 在 app.js:381 ✓ 三个消费点 :388（读侧 :392 把键写进快照）、:417（写侧 :422）、:433（调度 :438 取键、:442 写回前双重复核 `state.librarySnapshotPersistKey !== key || librarySnapshotKey(page) !== key`）✓ 命中判定在 `library_page_snapshot_policy.js:30` 以 `snapshot.key !== key` 复核 ✓ `renderTrackRows` app.js:3033、`commitTrackListHtml` :3235 ✓ `reuseSnapshotTrackMarkup`（app.js:5324）第一行就是 `!snapshotHit || !isPagedTrackListing() || state.view === "queue"` 早退，之后把两侧 `trackPagePresentationSignatures` 交给 reuse policy 判等 ✓ `hasVisibleLibraryPresentation`（app.js:1392）把「已有可见行或命中快照就不让骨架接管」委托给 render policy，:1449/:1453/:3699/:7633 四处消费 ✓ `loadPagedLibraryWorker`（app.js:5710）开头 `const seq = ++state.libraryRequestSeq`，:5728-5733 的 `state.libraryAbortController` 交还前比对身份 ✓ `fetchLibraryResponse` :5274、`fetchAllTracksForCurrentView` :5984 ✓ 逐条复核后**没有发现新缺陷**，因此按纪律不为记录型条目伪造判别测试：test_ui_library_page_snapshot_policy.js、test_ui_library_snapshot_reuse_policy.js、test_ui_library_render_policy.js、test_ui_library_load_key.js、test_ui_library_page_cursor_policy.js 五支既有套件已把上述口径钉住。 游标一侧的实际改动（服务于 L141，不构成关闭）：`library_cursor_policy.py` 现 202 行 ✓ 新增 `anchor_is_encodable()`（:54-65）把「这一行能不能当锚点」的三条形状测试与编码器收在同一处 ✓ `encode_track_cursor()`（:68）新增 `inclusive=False` 形参，只在 inclusive 时写稀疏键 `"i":1`（:84-87）⇒ exclusive token 字节不变 ✓ `decode_track_cursor()`（:96）恒返回 `"inclusive": bool`（:119-125）且严格判型（:117 拒绝 `"1"`、`1.0`、`2`、`None`、`[]`）✓ `cursor_group_tail_where()` 的比较符改成 `>=` 与 `>` 二选一（:166）✓ 删掉 `_text()`；`library_page_result_policy.py` 现 136 行 ✓ `_row_anchor`（:23）/`_anchor_is_encodable`（:32）/`_continuation_anchor`（:38-60）：已服务锚点可编码就原样返回，否则取前瞻行并标 `inclusive=True`，前瞻自己也不可编码（同一块 NULL 的中段）就保持原来的无 cursor 答复、不跳行，取键失败 `except` 回退不抛 ✓ `track_page_result()`（:119）只在 keyed 锚点上读 flag ✓ 死代码 `decode_track_page_rows` 连同 `__all__`、`library.py` 的导入与 3 处测试夹具一并清掉；`library.py` 现 2980 行 ✓ recent 视图 :1252/:1257 与主视图 :1364/:1369 的 OFFSET 分支改读 `limit + 1`（同一表达式 6 处绑定全部改到）✓ :1268/:1380 走同一个 decoder ✓ `has_more = None` 让完整性答案仍由总数推导 ✓ 这一处是本轮自己扩的设计：原方案只改游标页，实测首页落在 NULL 行上仍然发不出 cursor。 不关闭 L141 的取证理由：SQL NULL 在游标谓词的三种形状（`expr = ?`、`(tie, id) > (?, ?)`、`expr > ?`）下**永不可达**，inclusive 也表达不了它，前瞻替换只在「页尾行是某块 NULL 的末行且其后一行可编码」这类情形真正生效 ⇒ 残余写进 L141：(a) 页尾落在多行 NULL 块内部时仍然无 cursor（客户端退回 OFFSET，安全）✓ (b) DESC 下 NULL 块排在末尾，游标续读永远够不到那几行（行不丢，游标少行，已用一支专门的测试钉住）✓ (c) 跨版本 skew：新版 inclusive token 被旧版服务消费会跳过一行（单进程部署，反方向「旧 token → 新服务」安全）✓ 另记代价：OFFSET 页每页多读一行。 测试：全量 Python 2335 → 2348（+13，skipped=2）✓ 三个相关模块现 17 / 13 / 122 项 = 152 项 OK ✓ 点名新增——test_library_cursor_policy.py（398 行）+5 支 :176/:196/:339/:365/:374 与助手 `_rewrite_token`（:47）✓ test_library_page_result_policy.py（163 行）新写 :83/:101/:116/:132/:143 五支，其中 :27 是随死代码退役的**改名**（方法名从旧 OFFSET 解码器换成游标解码器），该文件净增因此是 4 而不是 5 ✓ test_library_sqlite.py（2938 行）+4 支端到端 :759/:778/:797/:814 与助手 `_null_key_library`（:745）、`_tail_cursor`（:836），:797 钉住「不跳整块 NULL」、:814 钉住 DESC 残余 ✓ 另实测性能前提：`>=` 与 `>` 单次 seek 1.428ms / 1.473ms、同一查询计划。 仓库外副本 E:/fnAudio_r112_cp（617 个 src 文件 + 8 份根文档 + 12 份 `android-client` 源文件，因为 test_ui_android_bridge.js 要读它们）✓ 控制组 Python 152 项绿、69/69 JS 套件绿 ✓ V1 空 id 重新判为不可编码 / V2 inclusive 退回严格比较 / V3 flag 不传给编码器 / V4 前瞻行永不启用 / V5 锚点无条件被替换 / V6 每个 token 都写 `"i":1` / V7 flag 不再严格判型 / V8 锚点判定丢掉 title 检查 / V9 OFFSET 页退回 limit / V10 解码器丢掉 flag / V11 遗留 token 默认 inclusive ⇒ 11/11 全灭，还原后 6 个改动文件逐一 sha MATCH，副本跑完即删。 三处诚实交代与两处自我更正：其一 V1 只在单元层被 :374 杀死，页投影与端到端两层在 V1 下仍绿，因为编码器本身从不拒绝空 id、前瞻替换会把它绕开——这不是覆盖漏洞，是这条守卫本来只在锚点判定处生效 ✓ 其二上一份交接摘要点名的一支端到端「空 id 走查」测试**在磁盘上不存在**，本轮以磁盘为准，空 id 路径由 :176 与 :143 两支覆盖，不冒领第三支 ✓ 其三 L141 因此没关闭，本轮净关闭只有 1 条（原计划是「L140 关闭 + L132 关掉」，实测把 L140 降级为改写）。自我更正两处：`test_an_empty_row_id_anchors_a_continuation` 第一版拿 artist 排序的 token 去问 title 排序，`cursor_page()` 判不同后返回 `("", [])`，断言因此是假的，已改成两个排序各编各的 token ✓ `bool(flag) and flag is not 0` 触发 SyntaxWarning，已改为 `bool(flag)`。 计数一律从磁盘重新取证并四组并存：目标正文快照 155 = 64 + 82 + 9 ✓ R99 快照 115 = 51 + 43 + 8 + 13 ✓ 本轮开头实测 99 = 代码 35 + 设备 43 + 决策 8 + 台账 13 ✓ 收尾实测 98 = 34 + 43 + 8 + 13 ✓ 互不合并、互不覆盖。清单与门禁：SOURCE_MANIFEST.sha256 696 条（根文档不在覆盖面内 ✓ 本轮无新增 src 文件）✓ `tools/takeover_forensics.py --full` listed=696 drift=0 stale=0 unlisted=0 ✓ Get-FileHash 抽查更正为 16 项全部 MATCH（10 个文件对拍 SOURCE_MANIFEST.sha256、6 个改动文件对拍本轮记录 sha 且与仓库外副本逐字节 SAME）；tools/ 下的 test_offline.ps1 与 takeover_forensics.py 经核实在清单里查无条目——SOURCE_MANIFEST 只覆盖 src/ 与 android-client/，696 条里 tools/ 为 0 条，因此这两个文件不在门禁覆盖面内 ✓ 分类器条目搬迁 0 ✓ 未提交、未 git add、未碰 .gitignore、设备段未动 ✓ 门禁终跑按「先写后验」补跑：round167、round168 与收尾最后一次全量重跑三份日志同为 Ran 2348 / OK (skipped=2) / 69 支 JS 全绿 / exit 0，本轮终跑以 artifacts 下最新一份 offline-20260919-round16x.log 为准（mtime 晚于全部文档编辑）。
- [x] 2026-09-19：R111 净关闭一条：「`library_connection_pool` 只是 `server.main()` 的引导默认值，既没进 `config.py` 的默认配置，也没有设置页开关或 `PROJECT_CONTEXT.md` 之外的文档说明」（原 L146）✓ 那个行号是插入本条之前的位置 ✓ 翻转后的这条现在在 L147 ✓ 插入后整体 +1 ✓ 本轮新立 0 条。关法按条目原文要求的三件事逐条落地：① 进默认配置——src/app/server/config.py:18-22 新增 `DEFAULT_LIBRARY_CONNECTION_POOL = True` 与四行口径注释 ✓ :29 进 `load_config()` 默认字典 ✓ :93-95 用 `_strict_bool()` 归一 ✓ `save_config()` 载荷 :153-155 同一口径写回 ✓ 默认字典 45 键、落盘载荷 45 键，两侧键集用 AST 实测完全相等；② 关就顺手排空——src/app/server/library.py:1844-1857 新增 `apply_library_connection_pool_config()`，开关为开返回 0，为关调用可复池的 `close_library_connections()`（读得出库路径就只排那一个库，读不出就整体排空）✓ server.py:605-609 在 `commit_config_update()` 就地提交**之后**调用它 ✓ 一次性的 `stop_library_connections()` 仍然只出现在 shutdown_runtime 的最后一步（server.py:3237）；③ 文档——新增 docs/LIBRARY_CONNECTION_POOL.md（72 行）并在 docs/INDEX.md:8 登记，docs/ 不在 manifest 覆盖面内。设置页开关本轮明确不做，连同「对外暴露属于产品判断」折进相邻那条设备项（原 L144 到现 L145），不另立新项，并顺手改掉那条里已经失效的「当前只有 `server.main()` 打开它」。附带取证与证伪：`server.main()` 的注入分支已删（server.py:3334-3339 换成说明为什么不能再注入的注释）✓ 该文件里 `close_library_connections` 是个未使用导入，一并摘掉 ✓ `load_config()` 生产调用者只有 server.py:3256 一处 ✓ 没有回显这份字典的 GET `/api/config` ✓ 没有任何测试读 docs/ ✓ 证伪一「改了曲库路径会遗留旧句柄」不成立——`library_db_path()` 只依赖 `cache_dir` ✓ 证伪二「新默认值会改变基准工具语义」不成立——tools/benchmark_large_library.py:125 内联构造 config 并在 :656/:666 显式设键撤键 ✓ 观测面 `/api/health` 与 `/api/diagnostics` 的 `library.connection_pool` 段与 `library_snapshot._CONNECTION_POOL_FIELDS` 七项逐一对上（health_snapshot.py:60-68、diagnostics.py:64-72），关掉时 `idle` 恒 0 且计数不动，因为 `note_created()` 只在池化分支触发。判别测试 11 条全部写进既有文件：test_config.py +4（现 24 条）、test_library_sqlite.py +4（现 118 条）、test_server_lifecycle.py +3（提交把已提交的字典交给排空器、提交失败不碰池、启动不再自己发明默认值），四个相关模块 168 项 OK。仓库外副本 E:/fnAudio_r111_cp（617 个 src 文件加 8 份根文档 ✓ 6 个改动文件与真实文件逐一 sha MATCH）跑 V1-V11 全灭 ✓ 控制组与还原组各 168 项先绿后绿 ✓ 副本跑完即删。两条诚实交代：V7（排空器丢掉「读不出路径就整体排空」的兜底）里 `apply(None)` 一支是等价变异——`close_library_connections(None)` 本来就排空全部，真正杀它的是 `apply([])` 一支；该判别测试第一版在 re-park 时复用同一个 limit，被 `LIBRARY_QUERY_CACHE` 直接命中、一条连接都没开，L314 报 0 != 1，换成缓存没见过的查询形状才成立。自我更正一处：本轮新写的注释与新文档都写了「冷页 2.4ms、连接前奏 1.45ms」，而仓库 2026-09-17 的首屏拆解记录是 **2.67ms 与 1.46ms**，2.4ms 属于 R86 那条「带 `sqlite_master` 探针的稳态连接」，量纲不同不能挪用 ✓ 两处已按记录口径改写并注明出处。清单与门禁：SOURCE_MANIFEST.sha256 刷新 696 到 696（本轮没有新增 src 文件）✓ `tools/takeover_forensics.py --full` 报 listed=696 drift=0 stale=0 unlisted=0 exit=0 ✓ 另用 Get-FileHash 抽查 10 个文件逐一 MATCH ✓ 开放项 100 到 99 = 代码 35 + 设备 43 + 决策 8 + 台账 13 ✓ 条目搬迁 0 ✓ 未提交、未 git add、未碰 .gitignore、设备段未动 ✓ 终跑门禁见 artifacts/offline-20260919-round166.log。
- [x] 2026-09-19：R110 一轮净关闭两条面：「R58 遗留：向上闭包依赖 folders 父链完整」（原 L81）与「接管一个中断会话时的固定动作：拿 SOURCE_MANIFEST.sha256 与工作树对拍」（原 L67）✓ 那两个行号是插入本条之前的位置 ✓ 翻转后的两条现在分别在 L82 与 L68 ✓ 插入后整体 +1。:81 取证结论是「曲目已入库而目录行缺失」在写入路径里不可能出现：全库唯一的生产写者 save_items_to_sqlite（library.py 现 2372 行）在保存前用三条 INSERT（2418/2426/2434）把「被删的旧行、改了 root/folder 的旧行、新增或改过的新行」全部记进 affected_folder_roots ✓ _rebuild_folders_for_changes（2738）对每个受影响项取其顶层目录整树重建：先按 path = top OR LIKE top/% 删干净 ✓ 再从 tracks 用同一前缀重选 ✓ 逐条补齐 1..len(parts) 的全部祖先 ✓ 于是曲目在就必然祖先链在。探针（%TEMP% 跑完即删）覆盖七种序列：移入既有顶层下的新深链、移入全新顶层、把新顶层清空、凭空加三层链、只改大小写的重命名、两个根共用同名目录 ✓ 结果 missing/dangling/track_count/多余行全为 0 ⇒ 按条目给的第一个方案落钉 ✓ 没有改成不依赖目录表的字符串前缀闭包。钉法：三条判别测试（从 tracks 反算闭包后逐项比 rows/parent/track_count/多余行 ✓ 用户可见症状「移动之后每一层祖先仍能各自被搜到」✓ folder 文本形状正是 top/% 前缀等价的前提）加两处注释钉（CTE 上方 1576-1582 ✓ 函数 docstring 2739-2747）。变异 M1..M6（只建叶子、漏记新增行、不删旧行、父级写成根、只重建改动目录本身、folder 文本保留空段）全部由新测试杀死 ✓ 其中 M6 只有新守卫测试能杀 ✓ 控制组与还原组各 114 项先绿后绿。:67 落成 tools/takeover_forensics.py（184 行）：drift＝比 manifest 新的在册文件 ✓ stale＝其中哈希不符或已消失的 ✓ unlisted＝按同一套排除规则该在册却没登记的 ✓ 每条附「先跑哪几个 src/tests/test_*」✓ 默认只哈希漂移项（--full 才全扫）✓ 退出码 1 当且仅当 stale 或非空 unlisted。仓库实况就是这条的教材：刷新前它报 stale=2（library.py ✓ test_library_sqlite.py）加 unlisted=1（本轮新测试文件）✓ 刷新后 696 项 drift/stale/unlisted 全 0（--full 全扫 193 毫秒 ✓ 另用 Get-FileHash 抽查 8 项逐文件 MATCH ✓ tools/ 不在 manifest 覆盖面内是既有口径）。判别测试 10 条（夹具仓库用 os.utime 定时间戳不靠 sleep ✓ 含一条活库对拍当真正的门禁）✓ 变异 V1..V8 全灭（V2/V4/V6 各被唯一一条测试杀死）。新立 0 条 ✓ 两处附带发现并入本记录：_rebuild_folders 没有生产调用者但 tools/benchmark_large_library.py:119 仍在用 ⇒ 不是死代码（此前只在 src 内 grep 得出的判断作废）✓ alsa_player.py 与 playback_session_contract.py 只被各自的测试引用（本轮复核：src/cmd、src/wizard、src/manifest 与 tools/ 里都搜不到这两个模块名 ⇒ 打包侧无引用），对应条目（现 L76）继续等设备口径。自我更正三处计数口径（草稿数与当场实测不符，一律以实测为准）：① git 现场要注明时点：R109 记录时点未跟踪 1101 ✓ 本轮刷新清单后、门禁前 1257 行 = 1104 未跟踪 + 149 已改 + 4 已删 ✓ 终跑再加 1 个门禁日志 = 1258/1105；草稿里的「1255 / 未跟踪 1102」两头都不是终态。② 行首 - [x] 由 1422 增至 1425（顶块新增 1 条加翻掉 2 条），含缩进则是 1426——多出的那条是 L662 的无日期缩进项 ✓ 报告必须交代是顶格还是含缩进。③ 开放项 102 → 100 ✓ 分类 36 + 43 + 8 + 13 ✓ 搬迁 0（三个非代码桶与 R109 记录逐一相同）✓ 新立 0 ✓ 本轮全部数字重新从磁盘取证。门禁终跑见 artifacts/offline-20260919-round165.log。
- [x] 2026-09-19：R109 一轮净关闭两条「结构自己会撒谎」面：「status 这个 out 参数是 parseBoundedJson 的第五个位置参数，漏传的那个默认成 undecodable」（原 L113）与「文档即契约：断言应从脚本 param() 块生成期望，而不是在测试里再抄一份中文句子」（原 L34）✓ 条目内的行号是插入本条之前的位置 ✓ 插入后整体 +1。落点一：src/app/ui/response_json_loader.js（现 229 行）改为返回 {data, status} ✓ 15 个出口全部走 outcome(...) ✓ status.value 归零 ✓ read() 具名取用 ✓ app.js 与其余 69 个 JS 测试文件一行未改仍全绿。落点二：src/tests/test_offline_verification_script.py（现 293 行）新增两个解析器与两条双向文档契约测试 ✓ 手册基线改为从 VERSION 生成 ✓ RECOVERY.md（现 127 行）补齐模拟器四个开关。判别测试：test_ui_response_json_loader.js（现 597 行）新增 12 形状 data⇄status 一致性环 + 参数表恰 4 位 + 无 out 参盒残留 + parseBoundedJson( 恰 2 处。变异：仓库外副本 C:\path\to\fnAudio_r109_cp 控制组先绿（69 个 JS 文件 pass=69 fail=0 ✓ 该 Python 模块 Ran 15 OK skipped=1）✓ 本轮在最终字节上重跑 12 条全部命中 ✓ 其中两条（再加第五个位置参数、!response 带 parsed 回传 fallback）只被本轮新增的断言杀死 ⇒ 新断言不是重复而是唯一防线。自我纠正与并入（不另立项）：① 上一条交接把 git 噪声记为「1253 项未跟踪」，本轮实测 porcelain 1254 行 = 1101 个 ?? + 149 个 M + 4 个 D（4 个 D 是 artifacts/0.1.174 的四份文件）✓ staged 0 ✓ 无 merge/rebase/cherry-pick 残留 ✓ .gitignore mtime 仍是 2026-08-14 16:43:49；② 交接口径里的 Python 总数按 2310 记，本轮一测换二测 ⇒ 现为 2311，round164 门禁必须读到 2311；③ 目标正文仍是旧快照 115 = 51 + 43 + 8 + 13，本轮磁盘实测 104 = 40 + 43 + 8 + 13（关闭后 102 = 38 + 43 + 8 + 13）✓ 两者不合并、不覆盖，漂移照实登记；④ %TEMP% 校验器按整文件逐字比对，抓到门禁按既有口径不检查的规则文件里有一条 2026-09-05 记录被原样贴了两遍（原 L305/L306 ✓ 已删掉后一份 ✓ 相邻同文条目归零）✓ 属根文档记账缺陷 ✓ 并入本条不另立项。净账：开放项 104 → 102 ✓ 可离线代码项 40 → 38 ✓ 设备/外部 43 ✓ 产品决策 8 ✓ 登记/口径 13 未动 ✓ 新立 0 条 ✓ 分类器搬迁 0 条。
- [x] 2026-09-19：R108 一轮净关闭两条响应体可信度面：「`app.js` 的行为只能靠源码正则约束」（原 L110）与「让响应体读不出来与这一页真的是空的在调用方可区分」（原 L115）✓ 条目内的行号是插入本条之前的位置 ✓ 插入后整体 +1。落点：`response_json_loader.js` 导出第二道闸 `parsedBody(status)`（只有 `parsed` 算可信文档 ✓ `empty` 仍可用但不可信）✓ `app.js` 三个真实文档读取点加门 —— `saveUserStateNow`（200 坏体不再当成保存成功 ✓ 保持 dirty + 2 秒重试）✓ `validateRestoredPlaybackTarget`（读不出的设备列表 = 无信息 ✓ 不许把投送目标收回本地）✓ `loadDevices`（坏体抛「设备列表读取失败」✓ 不再画成零设备）；其余 13 个 `read(` 站点本轮逐站取证为读-即-画或自愈轮询 ✓ 刻意不加门（取证与判据写在条目内）。测试面补上这条要的「最小 vm 外壳」：`test_ui_library_loading.js` 真跑从磁盘切出的 app.js 函数片段 ✓ `test_ui_response_json_loader.js` 钉住「两闸只在 `empty` 处分歧」✓ 仓库外副本控制组 69 个 JS 文件先绿 ✓ 变异 M1–M8 全灭 ✓ 且删掉那条旧正则后 strict 两例仍被行为断言杀死（无正则的控制组仍绿 ⇒ 「只能靠正则」的前提被证伪）。顺带纠正一处交接口径：全仓 `Content-Length: 0` 是三处（`server.py:1284/1914/1928`）不是唯一一处 ✓ 均非 `/api/` JSON 端点 ✓ 原结论不变。同轮自我纠正（并入本条不另立项）：新测试注释里原本写了 9 处 `TODO.md:110`/`TODO.md:115` 行号引用 ✓ 与「新增文本不用行号」的口径冲突且会被本轮顶块插入当场错位 ✓ 已改为轮次锚点 ✓ 改动只在注释文本 ⇒ 断言与产物未变 ✓ 控制组与变异矩阵在最终字节上重跑。净账：开放项 106 → 104 ✓ 可离线代码项 42 → 40 ✓ 设备/外部 43 ✓ 产品决策 8 ✓ 登记/口径 13 未动 ✓ 新立 0 条。
- [x] 2026-09-19：R107 净关闭一条元数据作品图面：「把 `metadata_tracks.artwork_id` 带进 `item_json` 并同步收紧 `has_local_artwork`」（L121）✓ 关闭方式是**取证证明这个修法会让系统变差** ✓ 生产代码一行未改。先钉载体：`prepare_track_persistence`（`library_write.py:122`）确实没有键白名单 ✓ `dumps(source)` 原样落盘 ✓ 新用例 `test_prepare_track_persistence_has_no_key_whitelist_so_a_copy_would_persist` 用 `metadata_artwork_id` 亲眼验过它能进 `item_json` ✓ 所以条目所称「`item_json` 从不含 artwork 字段」只是**生产者事实**（扫描器行 `library_metadata`/`build_audio_item`/`build_cue_item` 是闭集 ✓ R106 已证）✓ 不是载体限制。再钉为什么不能带：`has_local_artwork` 的三个调用点（`metadata_service.py:3678 / 4480 / 4553`）读的就是同一份 `item_json` ✓ 权威 artwork 一旦复制进去 ✓ 「还要不要继续排队」就从「现在有没有有效权威行」退化成「历史上曾经复制过什么」✓ provider 改名、作品行被回收、缓存过期这三条自愈路全部被永久静音。端到端用例把这条不可逆性钉死：`test_projection_serves_cached_artwork_without_an_item_json_copy`(E2) ✓ `test_valid_authoritative_artwork_keeps_the_track_lane_quiet`(E3A) ✓ `test_orphaned_authoritative_artwork_requeues_the_track_lane`(E3B) ✓ `test_persisted_copy_suppresses_the_lane_without_an_authoritative_row`(E3C ✓ 就是「副本落库后孤儿 artwork 再也排不进 track 道」那条反例) ✓ `test_lyrics_cache_miss_queues_artwork_lane_for_a_coverless_track`(C5 ✓ 钉 :4553 那支) ✓ 另用 `test_item_json_artwork_copy_would_suppress_the_lookup_forever` 直接钉策略函数本身。条目要求的另一半「同步收紧 `has_local_artwork`」经取证为**不可达**：三个判点在同一次连接里都已先读权威 artwork（:3676 / :4460）✓ 收紧它只会把「已确认的 artwork」和「文件自带的封面」混成同一个键。UI 侧两处 `metadata_artwork_id` 读取（`ui/visible_metadata_prefetch_policy.js:33`、`ui/library_metadata_merge_policy.js:6`）是惰性判定 ✓ 不驱动排队 ✓ 并入本条不另立。公开投影只有 `server.py:878 / 888 / 936` 三处且都紧跟 `enrich_track_page` ✓ 用源码接线断言 `test_library_routes_enrich_before_projecting_track_rows`（含 `assertEqual(len(sites), 3)`）钉住 ✓ 另用 `test_provider_artwork_does_not_replace_a_generated_thumbnail` 钉住「已生成的缩略图优先于 provider 作品图」这条优先级 ✓ 它不是缺陷 ✓ 候选修法「恒优先 provider artwork」实测否决并记档防重提。测试：新增 10 条判别性用例（未新增测试模块 ✓ 逐模块 6→7 / 17→19 / 219→224 / 12→14 ✓ 与门禁 2300→2310 交叉核对；本条先前误记为 9 条，现纠正）✓ `tests.test_metadata_service` 单跑 `Ran 224 / OK` ✓ 候选 4 模块合跑 `Ran 264 / OK`。变异：仓库外副本 M01–M18 **killed 18/18 ✓ survived 0 ✓ invalid 0 ✓ missing_expect 0 ✓ contaminated 0** ✓ 控制组先绿。本轮踩到并修掉三处驱动自身缺陷：① 上一版替换串被模板字符串的反引号污染（6 个锚点 0 命中被记成 INVALID）⇒ 变异表改为**从磁盘按行号+内容双闸生成**（`LINE MISMATCH` / `ANCHOR HITS` 任一不满足立即中止）；② 12 空格锚点是 16 空格行的子串（M11 双命中）⇒ 整行锚一律带前导换行符；③ M08/M09 的 expect 一度配反（真杀手正好互换）⇒ 改成逐条跑全量套件的 probe 复核后才定桩。净账：开放项 107 → 106 ✓ 可离线代码项 43 → 42 ✓ 本轮新立 0 条 ✓ 设备项 43 ✓ 产品决策 8 ✓ 登记/口径 13 未动 ✓ L1803（Chromaprint/AcoustID）复核后更像外部依赖项 ✓ 但本轮**不挪桶**（等口径裁决 ✓ 不静默改计数）。
- [x] 2026-09-19：R106 一轮净关闭两条元数据恢复面：「`metadata_unavailable_policy` 的三处 lyrics 读取在生产调用点是空转」与「`metadata_unavailable_policy` 的封面分支实际上是死的」 ✓ 两条都用**端到端复现证伪前提**关掉（与 L95/R51 同类：不是改码关掉）。复现脚本 `fnaudio_r106_repro.py` 现场证明：一份带 `lyrics` / `cover_url` / `cover_thumbnail_url` 的旧版 `library.json` → `load_library_cache`（`library.py:2789` ✓ 需 `library_summary_from_sqlite` 为空）→ `save_items_to_sqlite`（`prepare_track_persistence` 的 `item_json` **无键白名单**）→ `query_library_item_by_id`（`library.py:1726` ✓ 无路径过滤）→ `local_cached_projection` / `local_pending_projection` / `local_lyrics_projection` **三处全部返回真实值** ✓ 而 `server.py:3335` 启动时真实调用该加载器 ⇒ 生产可达。反向核实两处：扫描器行是闭集（`library_metadata` / `build_audio_item` / `build_cue_item` 都不含这三个键）✓ 而 `enrich_track_page(self, page, include_lyrics=False)` 的三个生产调用点 `server.py:877 / 887 / 931` 全部走默认 `False` ⇒ 生产里 enrich **从不写 `lyrics`**（`metadata_service.py:4415-4419`）✓ 条目原述「只有 enrich 之后的页副本才带」恰好说反。措辞纠正：条目所称「`server.py:972` 恒假分支」实为 L963 `elif not METADATA_SERVICE:` ✓ 它与上一支 `if METADATA_SERVICE:` 同义取反 ✓ **会执行** ✓ 不是恒假；本轮已把它改成 `else:`（全文 `elif not METADATA_SERVICE` 命中数归 0），真正被误判为死的是 L973 的 `or local_projection.get("lyrics")` 项 ✓ 它有效 ✓ 已补 HTTP 用例钉住。两个候选修法均实测否决：方案一改喂 `public_library_item()` 的行——该投影 `pop("lyrics")` 且把 cover **重写**（旧版行 `legacy-1` → `cover/legacy-1?v=0`）还附带磁盘探测 ✓ 只会引入新的覆盖层；方案二只认 `metadata_artwork_id` + `artwork_url`——原始行里根本没有该键 ✓ 等于留下第二个死分支。落码：`metadata_unavailable_policy.py` L23-39 的 caller-shape 注释按取证重写（184 → 191 行）✓ `server.py` 行数 3385 不变。测试：新增 4 + 1 + 1 = 6 个判别性用例（`MetadataRecoverySupplierTests` 4 项 ✓ `test_legacy_json_cache_rows_survive_into_the_single_item_lookup` ✓ `test_uninitialized_metadata_service_returns_a_lyrics_only_track_as_local`）✓ 仓库内候选 12 模块 `Ran 506 / OK`。变异：仓库外副本 M01–M15 共 15 项 **killed 15/15 ✓ survived 0 ✓ invalid_kills 0 ✓ bad_anchor 0 ✓ missing_expect 0** ✓ 控制组（副本重同步后）`Ran 169 / OK`。本轮踩到两处驱动自身的取证坑并已修：① 副本里 `tests/test_http_integration.py` 是 1444 行旧版 ⇒ 新增用例没参与运行 ✓ M14 一度假存活 ✓ 驱动现在前置校验 expect 用例是否存在；② M13 单摘 `result.pop("lyrics", None)` 是**等价变异**（第 76 行的 skip-list 已经把 `lyrics` 排除在拷贝之外）✓ 改成同时摘掉 skip-list 与 pop 两道防线的成对变异后才命中。净账：开放项 109 → 107 ✓ 可离线代码项 45 → 43 ✓ 本轮新立 0 条 ✓ 设备项 43 ✓ 产品决策 8 ✓ 登记/口径 13 未动。
- [x] 2026-09-19：R105 关闭「线性目前靠 `finite_number` 调用计数断言 ✓ 是用实现细节代理复杂度」那条：照条目开的第一条路做成显式可注入的比较计数器 ✓ `cue_parser.py` 104 -> 120 行 ✓ `_attach_track_ends(tracks, observe=None)` 在栈比较处计数并在 `parse_cue_structure` 上开 `observe_end_stage` 转发口  ✓ 循环改写为「先考察再判定」的等价形态。删掉 monkeypatch 数值 helper 的旧断言 ✓ 换成 7 条新用例：精确计数 ✓ 上界 ✓ 非空口 ✓ 规模斜率 ✓ 用嵌套参考实现证明这条界真能区分线性与二次 ✓ hook 中性 ✓ 签名可选性。`test_cue_parser.py` 163 -> 265 行 ✓ 11 项到 18 项  ✓ 仓库外副本变异 M01–M13 十二杀一等价存活（控制组 69/69 先绿）✓ 并给驱动补上 INVALID-KILL 判定以排除两处语法假杀。净账 110 -> 109 ✓ 可离线代码 46 -> 45 ✓ 新立 0 条 ✓ 未提交 ✓ 设备段未动。
- [x] 2026-09-19：R104 关闭「DLNA 浏览分组根容器仍会先物化整张表再在 Python 里切片」那条：注入的 `library_groups(view)`/`library_folders(parent, root)` 放宽为可接收 `limit`/`offset`/`sort_dir`，`server.py` 的两个闭包改为转发现有 `query_library_groups`/`query_library_folders` 的分页语句 ✓ 新增 `_group_page()`/`_folder_page()`/`_provider_browse_page()`，有界读只在提供方**声明了总数**时成立 ✓ 否则退回整表路径。这条要修的不只是代价：`materialize_browse_rows` 的 5000 上限同时封顶 `TotalMatches` 与深页可达性，控制器翻到第 5001 组之前就会被告知「只有 5000 条」。顺带修掉子目录分支一个未登记的缺陷：整页被目录行填满时 `remaining == 0` 使曲目总数从 `TotalMatches` 里消失，现在仍发一次 `limit:1` 计数探针、只是不渲染探针行。反向保留两处无界并配断言：`folders` 根容器（提供方无分页语句、每个配置根只有一行）与 `_metadata_for_object` 的单行存在性检查。判别性：`test_dlna_protocol.py` 1650 -> 2002 行（新增 13 条，模块 86 -> 99）✓ 控制组仓库内定向 6 模块 312 项 + 仓库外副本 69 个 JS 先绿 ✓ 变异 M01~M16 全灭、survivors=0。净账 开放项 111 -> 110 ✓ 可离线代码项 47 -> 46 ✓ 新立 0 ✓ 终跑 `artifacts/offline-20260919-round159.log`。
- [x] 2026-09-19：R103 关闭「ID3v2.4 的帧级标志仍未处理 ✓ 帧级标志为真时现在的行为是『读错』而不是『跳过』」那条：条目要求先确认真机样本再决定实现还是显式拒绝 ✓ 但「读错」这一半不需要样本就能定——帧自己的两个标志字节被解析器完全忽略是既有事实 ✓ 真机样本只决定「有损保留要不要做成无损」✓ 不决定「把 zlib 当标题返回」该不该继续。取证更正：条目里的位值有两处是错的 ✓ 对照权威兼容实现 mutagen 的 16-bit 帧标志表后确认 v2.4 压缩是 `0x08` 不是 `0x10`、加密是 `0x04` 不是 `0x08` ✓ 照条目实现会漏杀压缩帧并错杀保留位。落地：`id3_parser.py` 新增 `_frame_body()` ✓ `iter_id3_frames()` 开始读帧标志 ✓ 可撤销的两种（v2.4 帧内 unsync、data-length indicator）就地还原 ✓ 不可表示的整帧跳过而 `offset = frame_end` 继续 ✓ status 字节一律不参与跳过。写侧后果：`_id3_frame()` 硬写 `b"\x00\x00"` ✓ 所以「保留」一个压缩帧等于把它的密文重命名为明文 ✓ 已在 `_preserved_id3_frames` docstring 写明这一取舍。判别性：`test_id3_parser.py` 148 -> 277 行（10 条新用例）✓ `test_metadata_service.py` 3986 -> 4046 行（2 条写侧反损坏用例）。控制组 518 项 Python + 69 个 JS 先绿 ✓ 仓库外副本变异 X1~X12 全灭（X6、X10 首轮存活 ✓ 查清是输入不够而不是等价 ✓ 补出可分辨输入后杀）✓ 净账 开放项 112 -> 111 ✓ 可离线代码项 48 -> 47 ✓ 新立 0 ✓ 终跑 `artifacts/offline-20260919-round158.log`。
- [x] 2026-09-19：R102 关闭「被接管的旧请求仍可能在 settle 时写响应缓存 ✓ `getEpoch() === epoch` 是唯一防线」那条弱口：照条目自己开出的路（「给被接管者加一次性作废标记」）落地 ✓ 不是再加一个代次 ✓ 而是把「谁还拥有这个 URL」这件事在移交点显式收回：`library_response_loader.js` 新增 per-call `cacheWriteVoided` ✓ 发布门前置 `!cacheWriteVoided` ✓ 槽位移交与发布权移交现在同处一行代码里 ✓ 被弃请求仍拿到自己那一次的结果只是不再有权写缓存。取证：`state.libraryResponseEpoch` 只在整表失效时自增（`app.js:5245`、`app.js:7647`）✓ 接管发生在同一代次内 ✓ 所以 epoch 对移交双方同时为真 ✓ 这条弱口是结构性的而不是概率性的。控制组先跑抓到一处既有字面钉因契约加强而失效（`test_ui_library_loading.js:512`）✓ 按「收紧而非放宽」更新。判别性：`test_ui_library_response_loader.js` 446 -> 518 行（8 条运行时断言 + 4 条源码钉）✓ 仓库外副本变异 W1~W10 全灭 ✓ 净账 开放项 113 -> 112 ✓ 可离线代码项 49 -> 48 ✓ 新立 0 ✓ 终跑 `artifacts/offline-20260919-round157.log`。
- [x] 2026-09-19：R101 关闭 poll 路径每轮两次 `syncPlayerProgress()` 那条结构重复：删掉 `updateNowMarquee()` 尾部那次顺带绘制 ✓ 取证证明它从来不是可靠契约（同一函数在 `mobile-search-active` 下整条早退）✓ 8 处调用点与 resize 监听逐个读毕 ✓ 没有任何归属点需要 marquee 代劳 ✓ 改为 restore/载入×3/DAC/boot 六个归属点各自显式一次 ✓ 一次轮询的传输行绘制计数 2 -> 1 ✓ 新立 0 条。判别性走真函数 context（`updateSeekRail` 作唯一可观测量 ✓ 4 条运行时断言 + 15 条源码级断言）✓ 仓库外副本变异 Q1~Q10 全灭 ✓ 控制组 69 个 JS 文件在矩阵前后各全绿一次 ✓ 门限 round156。另：R100 记下的 `TODO.md:NNN` 行号引用漂移随本轮插入再 +1 ✓ 逐条复核见 PROJECT_CONTEXT ✓ 本轮自身新增引用 0 处。净账：开放项 114 -> **113** ✓ 可离线代码项 50 -> **49** ✓。
- [x] 2026-09-19：R100（接管 DeepSeek Harness 中断后的第一轮 ✓ 也是第一次取证一个真实中断现场：崩溃方 04:35:27 同一秒既改了 `app.js` 也改了 `test_ui_library_loading.js` ✓ 但记录、manifest、门限三样都没留）：关闭 `localPlaybackDuration` 前提无运行时防线那条 ✓ 接管方在真权威 harness 上把同一条前提再钉一次（测试 7b ✓）✓ 变异矩阵 M1-M4 四个语法合法的变异在仓库外副本全部被杀（控制组 69 个 JS 文件在矩阵前后各全绿一次 ✓）✓ 并按剥离实验纠正了本轮初稿里两处不实的全称断言（见 CHANGELOG 的 R100 判别性条 ✓ 本轮没有据此新立条目）✓ 另当轮修掉门禁的 `%TEMP%` 泄漏（每跑一次留一个一次性字节码缓存目录 ✓ 接管前累计 65 个 / 3.04 MB ✓ 判别性并入既有那条源码级测试 ✓ Python 侧总数仍 2263 ✓ 本轮终跑后残留 0 个 ✓ 同样不另立条目）✓ 净账：开放项 115 -> **114** ✓ 可离线代码项 51 -> **50** ✓ 新立 0 条 ✓。
- [x] 2026-09-19：R99 一次关两条轮询面：(a) 投送结束后「未选择曲目」旁边留着投送曲目的 1:40 —— 新增 `resetTransportRow()` 并接在 `restoreLibraryNowPlaying()` 的空选择分支 ✓ 复位 elapsed/duration/seek/进度条填充/播放图标并丢掉 `state.remoteUiLast`； (b) now-playing 其余文本无条件重写 —— 取证发现这条要求的口径**早已落实**（全站 79 处 `textContent =` 里 没有一处直接写这五个节点 ✓ `--seek-fill` 只出现在带比较的写入器里 ✓），于是按「已实现 + 机检守住」关闭 ✓ 两条共用一套新增断言 ✓ 变异 8 例全部由 JS 套件杀死（控制组先绿 ✓）。
- [x] 2026-09-19：R98 关闭「`safeInflightLimit` 把 `[]` 与负数经 `Number()`/钳位读成 0 ✓ 于是否掉整个曲库加载」那条：条目给的两条路里选了第二条（显式区分「禁用」与「未设置」✓）而不是第一条 ✓ 因为第一条与既有契约冲突（`test_ui_library_response_loader.js:152-159` 已把显式 `0` 与 `"0"` 钉成「就是没有预算」✓）。现在只有**意外塌到 0** 的输入回落默认（对象与数组 ✓ 负数与负小数 ✓），显式 0 仍禁用。变异 8 例全部被 JS 套件杀死（控制组先绿 ✓）。
- [x] 2026-09-19：R97 一次关掉同一种缺陷的两条：`tools/benchmark_large_library.py` 的合成库形状不再随规模变化。专辑数从恒定 2000 改为随 tracks 增长（100k 曲目 → 12500 组 ✓ 落在「游标收益只在组数上万时可见」的区间 ✓）；目录形状补上一个宽父目录（四分之一的曲目各自占一个叶子目录 ✓ 2.5k 时 625 兄弟 ✓ 20k 时 5000 兄弟 ✓）并新增搜索页的计划硬守卫（这条点名要的东西 ✓）。新增 1 条机检测试 + 变异 7 例全部被杀死（控制组 19 条先绿 ✓）。
- [x] 2026-09-19：R96 关闭 UPnP 探测截断那条（`discover_upnp()` 按 SSDP 应答到达顺序占用有限的描述请求名额 ✓ 注释承诺的「后面的 refresh 会继续探测其余设备」不成立）：改成对上一轮已探测集合做轮转选取，输出仍按到达顺序；并按这条要求的另一半，把发布从整表替换改为「本轮没探测到的已知渲染器继续保留并标 `probed=False`」。新增 4 条离线测试 + 变异 8 例全部被杀死（控制组 69 条先绿 ✓）。
- [x] 2026-09-19：R95 关闭「不带 `root` 的文件夹页全表扫」那条：先按条目要求取证到消费者确实存在（`app.js:5745` 只在 `state.folderRoot` 非空时才 set `root` ✓ `server.py:3154` 的适配器原样透传 ✓），再照条目开出的方案补上 `(parent, name COLLATE NOCASE <dir>, path)` 一对索引；实测走真函数的分页浏览在 10 万行目录下 5.84 ms -> 1.27 ms（约 4.6 倍 ✓），写侧代价也量了出来（2 万行重建 100.97 ms -> 146.49 ms ✓）。判别性测试 1 条（计划 + 语义双向 ✓）+ 变异 7 例全部由它杀死（控制组 131 条先绿 ✓）。
- [x] 2026-09-19：R94 关闭 `Observability.write()` 每条日志重复加固那条（详见下方 2026-09-17 条目）：新增 `file_permissions.secure_directory_on_drift()` 与 `secure_file_on_drift()`，用一次 lstat 代替整轮加固，只在模式漂移/类型可疑时才回落到完整 `secure_directory`/`secure_file`；实测 200 次目录加固 6.075 ms -> 1.060 ms（约 5.7 倍 ✓），稳态每条日志固定 2 次 lstat 接线指纹 ✓。新增测试 5 条（4 条分支决策 + 1 条接线与指纹）+ 变异 10 例全部被杀死（控制组 297 条先绿 ✓）。
- [x] 2026-09-19：R93 关闭两条 backlog：`metadata_assets` 历史行那一条的前提被证伪（存库 mime 只是提示，服务侧由字节决定），但顺着量出另一个真缺陷并已修：`MetadataService.artwork()` 在决定「这行永远只能 404」之前就刷新 `last_accessed`，而回收按 `last_accessed ASC` 选受害者，于是永久不可服务的资产被每次命中续到队尾、最晚被回收；同时关闭 sniffer 读取窗口那一条（它的诉求实测已满足）。判别性测试 1 条、变异 6 例全由它杀死，见下方两条 2026-09-17 条目。
- [x] 2026-09-19：R92 关闭 `read_flac_cover()` 的「畸形 PICTURE 块终止扫描」缺陷（详见本段下方 2026-09-17 那条）：四支字段校验收进 `_picture_block()`，返回 None 只表示跳过这一块，扫描继续走下一个块；同时纠正本轮自己犯下的另一个错——按记忆改 FLAC 字段顺序（以为 MIME 长度在前、picture type 8 位），被 RFC 9639 §8.8 原文否证：picture type 是 `u(32)` 且排在 MIME 长度之前，原实现与既有夹具一直正确，改动已全部回滚（那版改动会让 31 条既有测试里恰好 2 条变红 ✓ 就是这两条 ✓）。判别性：还原改前代码的变异 P1 被新增测试杀死（138 条 4 failures ✓）；P3（去掉共享封面预算）也被杀，用 `mock.patch` 把 `MAX_COVER_FILE_BYTES` 压小来证明那一项真被使用。
- [x] 2026-09-18：R76 新开：`_ensure_schema` 每次连接都跑完整 DDL 脚本 + 三次标记 SELECT。单线程实测整套 6 ms，但它是一段**写事务**，所以任何并发的持有者都会把它变成 5 s 等待；本轮只堵住了 `ensure_workers` 这一类嵌套连接。下一步可以做成「先用一次读查询确认对象是否齐备，缺了才跑 DDL」，让稳态连接完全不碰写锁。别直接上记忆化：本轮试过按 (路径, 版本) 记忆，三条测试立刻失败，证明这份迁移同时兼任**带外写入的修复**，一跳就漏修。  **R86 关闭（按条目建议实现了，量下来没有收益，因此回退；同时纠正条目的三个前提）**：实现照条目说的做（`sqlite_master` 一次读查询确认 7 个对象齐备，齐了就不跑脚本，且**不记忆化**），跑通后实测：稳态连接 50 次带探针 2.4 ms/次、不带 2.2 ms/次——**没有可测差别**；再拿一个 `BEGIN IMMEDIATE` 写者压住库：稳态连接带探针 2.8 ms、无条件跑 DDL 1.4 ms，**两者都不等待**，因为 `CREATE TABLE IF NOT EXISTS` 对着已存在的对象根本不加写锁。真正会等的是「库真的坏了」那一次：删掉 `favorites` 再压写者，实测 **2.087 s**（等满写者提交），而那正是这段脚本存在的理由，任何探针都跳不过、也不该跳。所以条目说的「它是一段写事务，所以任何并发持有者都会把它变成 5 s 等待」在稳态下不成立。另外两处纠正：函数名是 `ensure_state_schema`（:120），每个连接只有它一处调用（:85），**没有三次标记 SELECT**（`state_meta` 只有一处读，在 `_revision()` :161，属于 load/save 的乐观并发检查，不是连接路径）；而三个公开入口（:266/:334/:402）本来就把连接包在 `_STATE_WRITE_LOCK` 里，进程内串行化是设计如此，与 SQLite 锁无关。**回退的理由**：留下的收益是零，代价是多一份需要与 DDL 手工同步的对象清单——将来给脚本加一张表而忘了加进清单，探针会说「齐了」，那张表就永远不会被创建，这是个静默失效面。改为钉住那个真正值得防的回归：`test_connecting_while_a_writer_holds_the_database_does_not_wait`（写者压住库时稳态连接必须 < 1 s，并先断言写者事务仍不可见以免断言空转）；变异 W1 往 DDL 里加一条 `INSERT OR IGNORE` 就被杀死，且那一轮耗时 17.9 s，正好是 15 s busy 超时加固定开销，与「把稳态路径变成真写」的推演一致。W2（按路径记忆化，即 R76 当年踩的坑）被两条既有测试杀死（`test_playlist_trim_matches_the_statement_per_playlist_reference`、`test_playlist_trim_statement_count_does_not_grow_with_the_library`——条目记的三条，我这版变异触发其中两条）；W3 就是本轮写过又删掉的探针，按设计存活，这正是它「行为中立、不值得存在」的证据。
- [x] 2026-09-18：R76 新开：还有一类越界拨号是**跨测试泄漏的线程**发出的。R76 之前整套跑记录到 6 次对 `198.51.100.20:80` 的拨号，全部归属到 `test_dlna_protocol.py` 里做 `SetAVTransportURI` 的用例，但那几行单独跑时拨号为 0——只有全套跑、且套件慢到订阅刷新/GENA 定时器来得及触发时才出现。现在守卫会把它变成失败或静默拒绝（产品侧 NOTIFY 线程自己吞异常），所以这条要在守卫还在的时候查：谁没把 event-bus 线程关干净。用 `test_zz_socket_guard.external_access_attempts` 审计，别靠肉眼。  **R88 关闭（拨号已经是 0，抓到的漏是另外两个关不干净的线程）**：按条目要求用 `test_zz_socket_guard.external_access_attempts` 在进程内跑整套 2237 条做审计，越界拨号 **0 次**；守卫记到的 8 次尝试（`198.51.100.20:443` 2 + `8.8.8.8:443` 2 + `musicbrainz.org:443` 3 + `203.0.113.9:80` 1 = 8）全部由 MainThread 在 `SocketGuardTests` 自己的用例里发出，属设计内。R76 那 6 次 `198.51.100.20:80` 不再出现，GENA 侧拨不出去的原因也量到了：`shutdown()`（`dlna/service.py:599`）在放行任何排空任务之前先置 `_shutdown`（:603），而 `_drain_subscription` 第一个判断就是它（:566 直接 return），所以 `with mock.patch(...)` 撤销之后残留的排空任务不会真发 NOTIFY。判据必须换口径才看得见东西：`ThreadPoolExecutor.shutdown(wait=False, cancel_futures=True)`（:610）本就不 join，worker 靠哨兵退出，「测试那一行还活着」是设计使然，于是审计改成再等 1 秒比一次。按这个口径抓到 2 个真漏：其一，`AirplayService(...)`/`MpdService(...)` 构造即起 `fnaudio-process-supervisor` 监控线程（`services/process_supervisor.py:222`），只有 `stop()` 或 `shutdown()`（:289）会排空它，airplay 7 处构造里 5 处不停、mpd 的 `make_service()` 也不停，该线程一路活到解释器退出；其二，库封面预热 worker（`cover_cache.py:1117`，页间只睡 `LIBRARY_PREWARM_DELAY_SECONDS = 0.15`，所以不是窗口太短），模块早就有 `shutdown_library_thumbnail_prewarm`（:1129），大库用例没调过。修法：`test_airplay_service.py:11` 新增 `_service()` 把 7 处构造统一挂上 `addCleanup(service.supervisor.shutdown)`（:21）；`test_mpd_queue.py:69`、`:89` 各挂一条；`test_library_cache.py:686` 挂 `addCleanup(cover_cache.shutdown_library_thumbnail_prewarm, True)`。复测：1 秒后仍活 2 条 -> **0 条**，进程退出时命名线程为空；剩下 9 条只是「那一行还没退」，全在一秒内自排空。变异判据用审计本身而不是单测：S1 让 `ProcessSupervisor.shutdown` 直接 return -> 审计报 stuck=2 并点名 airplay 用例；S2 让 `shutdown_library_thumbnail_prewarm` 变空操作 -> stuck=1 点名大库用例；S3 只放宽 join 超时（等价）-> 审计 0，说明它测的是漏、不是调用风格。审计脚本留在 `%TEMP%`，不进版本清单。
- [x] 2026-09-18：R76 新开：`test_build_release_script` 里 7 条证据校验测试各 3.1-6.0 s（合计约 27 s，是 R76 计时分布的第二大块），每条都要冷启动一个 PowerShell + .NET 运行时。可以在同一条测试里复用一次子进程（多个断言合并）或把纯解析部分下沉为 Python 可调用入口、只保留一次端到端 PowerShell 冒烟。合并时注意别把「每条独立拒绝原因」的合成夹具塌成一条。  **R83 关闭（复用一次子进程，独立拒绝理由一条没压）**：先把「7 条各 3.1-6.0 s、合计约 27 s」量准：实测该模块 19 条测试 32.088 s，其中 **11 条**发起共 **19 次** PowerShell（单次最久 5.925 s，那条里有四个场景），本机一次冷启动 0.94 s 而校验脚本自身只花 0.45 s 级（同夹具两次独立进程 3.04 s、三场景一进程 1.81 s）——慢的不是发布校验，是解释器被反复启动。取条目给的第一条路：**在同一条测试里复用一次子进程**（测试模块内联场景驱动，不新增受版本管理的文件），每个场景仍把 `verify_release_evidence.ps1` 从第一条语句跑到最后一条，`throw` 逐场景捕获回报；场景之间的夹具改动改成声明式 `pre` 写入，顺序进数据而不是靠 Python 侧动作穿插。没取第二条路（把纯解析下沉为 Python 入口）：那等于用第二种语言重写校验逻辑，双实现会漂移，这批测试的价值恰恰是跑真脚本——变异 V7（把真脚本的 SHA-256 比较改成永假）在合并后仍然失败就是证据。**32.088 s → 16.593 s，19 条全绿，单条最久 1.771 s**，整套离线门限从 115.2 s 降到 99.8 s。防「驱动自己出错」的契约：回报带 `index`，Python 侧断言条数相等且索引连续（V4 去掉递增、V5 只回报第一个场景都被抓住）；V6（去掉 `Out-String -Width 4096`）按设计存活，没有断言依赖换行位置，属等价变异。
- [x] 2026-09-18：R75 新开：封顶之后，一次清扫仍有 128.9 ms 落在真实用户请求上（`_atomic_bytes` 之后同步跑）。这与 `transcode.cleanup_transcode_cache_if_due` 是同一个形状，本地可接受，但 SMB 上按 R72 量到的 5 s 级停顿风险同一量级放大。候选宿主是已有的 `fnaudio-cover-prewarm` / `fnaudio-cover-library-prewarm` 线程（把 interval-guard 改成在 worker 里到期执行），代价是要与 `shutdown_library_thumbnail_prewarm` 的排空顺序对齐。**先量真机再动**，本地没有 SMB 就改只会把可测的东西换成不可测的。〔R129 真机取证（2026-09-21，测试机 198.51.100.24；**SSH 实际端口是 22，不是此前登记的 21**——21 上是 FTP，TCP 能连通而 SSH 握手挂死）：本条门槛要的 SMB 面在这台机上**不存在**。`findmnt -n -o FSTYPE,SOURCE,TARGET` 全表只有 `ext4 /dev/mapper/trim_2f590ddb…-0 /vol1`，按 cifs/smb/nfs 过滤只命中内核伪文件系统 `nfsd`，曲库路径 `/vol1/1000/music` 就落在 ext4 本地卷上。封面缓存目录 `/vol1/@appconf/fnaudio/transcode/covers` 实测 11 个文件 / 58,005 字节，`os.walk` + 逐文件 `os.stat` 三连实测 **0.30 / 0.23 / 0.19 ms**，量不到任何 5 s 级放大。⇒ 「先量真机再动」的实测结论是**这台机答不了这道题**，不是「量了没问题」；门槛原样保留，本条不改代码、不新立项。〕 〔R138 X5=B 裁定关闭：本项目**不存在 SMB 部署面**，本条风险的前提不成立，据此永久关闭。关闭依据为 R129 真机取证（全 ext4、封面目录 11 文件 / 58,005 字节、`os.walk`+逐文件 `os.stat` 三连 0.30/0.23/0.19 ms，量不到任何 5 s 级放大）。重开条件写清楚：曲库一旦真的挂到 SMB/CIFS/NFS，本条与并入项同时重开。本条同时吸收决策段原 L1887（X4=C 并入），那个 `allow_disk=False` 不转传的问题按同一「无真实分布就不选边」理由一并永久关闭。〕
- [x] 2026-09-18：R75 新开：`covers/` 现在封顶了**字节**与**过期项**，没有封顶**条目数**。5000 张独有封面 ≈ 2 万个文件、约 260 MB，远不到 512 MiB 默认预算，所以第三层根本不触发，而小文件数量本身在 NAS 上有独立代价（备份、fsck、目录列举，以及 R75 自己那 20000 条/轮的走查上界）。要加 `cover_cache_max_entries` 得先有真实库的文件数分布，别拍一个数——本轮刻意没加，因为没有数据时说不上「合理」两字。〔R129 真机取证（同机同端口）：本条要的是「真实库的文件数分布」，实测该机 `library.sqlite3` 规模为 `tracks` **6 行** / `albums` 4 / `artists` 4 / `covers` 表 6 行 / `cue_tracks` 0 / `folders` 0；`metadata_entities`、`metadata_tracks`、`metadata_track_matches`、`metadata_assets` 四表全 0 行，仅 `metadata_jobs` 2 与 `metadata_state` 2；`config.json` 里 `metadata_enabled=false`，`metadata_cache_max_bytes=536870912`；缓存目录 11 个文件 / 58,005 字节。一个 6 行曲库、元数据总开关关着的样本机给不出任何「分布」，据它定 `cover_cache_max_entries` 恰好就是本条明令禁止的「拍一个数」。⇒ 保持开启，等真实规模曲库；本轮不改代码。〕 〔R138 X6=B 裁定关闭：并入 X4/L47，按「没有真实分布就不引入新配置」关闭。R129 实测该机 `tracks` 6 行、`cue_tracks` 0 行、`metadata_enabled=false`、缓存目录 11 文件——据它定 `cover_cache_max_entries` 恰好就是本条明令禁止的「拍一个数」。重开条件同 L47：出现真实规模曲库或 SMB 挂载后再按分布定值。本轮不改代码。〕
- [x] 2026-09-18：R75 新开（设计约束，别顺手实现）：`_MEMORY_CACHE` 的键里没有路径，只有 (缓存目录, 媒体身份, 版本, 尺寸)，所以清扫**无法**反查「这个内存条目对应哪个已删文件」。当前语义是刻意的、并有测试钉住（内存可以继续回答已经不在盘上的字节）。如果以后要求「内存不得宣称磁盘没有」的强一致，需要先给条目记录来源路径或建反查表，那是另一次改动而不是三行代码。  **R81 关闭（约束成立但措辞是全称，实测要收窄，已用测试钉死）**：`_item_cache_identity`（:121）取 `item.get("id") or item.get("path")`——库里行都有 id，所以对它们「键里没有路径」成立；**没有 id 的行键里就是路径**，于是「清扫无法反查」只对前者成立，原条目写成了全称。新增 `test_memory_entries_are_keyed_by_identity_so_a_sweep_cannot_reverse_them` 把三件事分开钉住：id 行的媒体路径不出现在任何内存键里；无 id 行的键确实是路径（那是例外不是缺陷）；以及刻意语义「内存可以继续回答盘上已经没有的字节」在资产文件与媒体文件都被删除之后仍然成立（变异 F1 把优先级调成 path 先、F2 让内存条目根本不留，都被指名杀死）。实现不改、反查表不建——条目自己说了那是另一次改动，本轮把确切边界写进测试就是它的归宿。
- [x] 2026-09-18：R74 新开：这把 LAN 地址缓存没有任何可观测量。DLNA 诊断里已有 `cache_status` 那套先例，并且有既有契约要求它**不得暴露设备身份**（`test_dlna_network.py` 的 `test_cache_status_never_exposes_device_identity`）。如果要给这把缓存加状态，只能给条数与命中计数，不能给主机名或地址；用途是解释「对端搬家后第一次动作为什么慢」这种一次性事件，别做成新的日志噪声源。  **R87 关闭（按条目允许的口径加了计数，走现成诊断页）**：`network.py` 加 `_LAN_ADDRESS_CACHE_STATS`（hits / misses / expired / evictions 四项，更新点 :88/:95/:97/:102，都在已持有缓存锁的短段内，不做 I/O，符合 R82 那条「锁内不落盘不联网」的规矩）与 `lan_address_cache_status()`（:51）。**只有计数**：不导出主机名、地址、也不导出缓存键，函数文档里就写明这条约束来自诊断页既有的 `test_cache_status_never_exposes_device_identity`。接入方式是在现成的 `upnp_cache_status()` 里加 6 个 `lan_cache_*` 字段（`control_point.py:13` 引入、:578 取值、:601-606 输出，沿用同页的 `_bounded_counter`），不新开一个诊断字段，免得条目警告的日志噪声源真的多一个。为什么单独有 `expired`：条目要解释的是「对端搬家后第一次动作为什么慢」，那是租约到期，不是新邻居——两者都会 miss，只有拆开才分得清；`hits` 与 `misses` 的差还能看出一次动作里有没有反复解析。计数是**进程累计**、`clear_lan_address_cache()` 不清零（与旁边的 `refresh_*` 一致），所以读法永远是两次快照相减——这一点被测试踩实过：第一版按绝对值断言 `misses == 1`，在整套里读到的是 72。新测试两条：`test_the_status_surface_counts_traffic_without_naming_a_peer`（形状必须恰为 7 个键、对端名字与地址不得出现在渲染结果里、增量要能到达诊断页）与 `test_an_aged_out_entry_is_counted_separately_from_a_first_sight`。变异 Q1 不记 hits、Q2 不记 expired、Q3 把每次 miss 都算成 expired、Q4 给状态加一个能指认对端的字段，四例各自被指名杀死；Q5（clear 时清零）按设计存活，因为它对「相减读法」确实等价。
- [x] 2026-09-18：R74 新开：SUBSCRIBE 侧仍然每次都真解析（`lan_http_url` 在 `dlna/service.py:520`），本轮刻意保留。真实风险是**没有节流**：一个控制器可以反复新建订阅，每次逼服务做一次解析。要做节流的话按 (回调主机, SID 配额) 限，而不是把解析结果缓存进取任路径——那会同时改掉 `test_dlna_protocol.py:1060` 钉住的语义，属于需要单独论证的产品决定。  **R90 关闭（节流做了，但不是条目建议的那把配额：全局并发上界已经消掉风险主体，主机配额只留公平性）**：条目建议「按 (回调主机, SID 配额) 限」，本轮先量清代价再决定照不照抄。实测（`%TEMP%\r90measure.py`，只换掉校验体、用测试早已存在的 `_callback_url` 替身缝）：**16 个并发 SUBSCRIBE 让 16 个 worker 同时卡在 `getaddrinfo` 里，即 32 宽 HTTP 池的 50%**（`http_max_workers` 默认 32，`server.py:3357`），32 个就能把整个服务连同 Web UI 与 `/api/health` 一起带走。所以真正要防的量是「同时有几个人在解析」，而不是「谁在解析」。修法用现成机制不加新限流器：`DlnaEventService` 持一个 `ConcurrencyGate("gena-callback")`（`dlna/service.py:405`），校验包在 `slot(GENA_VALIDATION_LIMIT=4, 1.0 s)` 里（:41-43 常量、:477 调用），上限 4 是 32 的 1/8，与 `http_server.py:21` 给长驻请求预留的比例同族；复测同一夹具：**峰值并发 4（池的 12%）**，16 个请求里 4 个立刻进、4 个排队、8 个被 waiter 上限直接拒，排队那 4 个各等满 1 s 后拿到 412 `event callback validation is busy`（:483），总计 8 成 8 拒。代价量到并写清：新订阅中位 3.0 µs -> 6.1 µs、p99 3.7 -> 17.8 µs，而本机一次真解析是 13.8 ms（R74 量过），多出来的 3 µs 是解析成本的 0.02%；续订仍 1.2 µs 且一次解析都不发。**没有实现按主机配额**，理由：那要在进程内再起一份以主机名为键的 LRU（得有上限、租约与逐出），而这块的诊断面有条硬契约——`snapshot()` 的自述就是「不给 callback URL」，`test_dlna_network.py` 的 `test_cache_status_never_exposes_device_identity` 也不许把对端身份说出来，主机名恰恰就是对端身份；更关键的是全局上界一到位，主机配额能买的就只剩「控制器之间的公平」，买不到「服务还活不活」。残余就记在这条结论里：单个控制器反复订/退订仍能在 4 个位里持续占用解析，上限是 12% 的池子；真观察到不均，再按配额加，那时它是公平性功能而不是存活补丁。**条目另划的红线被本轮证实**：不许把解析结果缓存进取任路径——变异 K8 把 `network.py:129` 的 `_lan_addresses` 换成已有的 `_cached_lan_addresses`（带 TTL 的那把投递缓存），立刻被既有 `test_callback_validation_still_resolves_the_host_it_admits` 杀掉，`test_dlna_protocol.py` 的语义确实会被改掉。
- [x] 2026-09-18：R74 新开：`metadata_remote_url_policy.py:50` 是另一条独立的 `getaddrinfo` 策略路径，形状与 R74 修掉的相同（每次出网都重新解析）。先量它是否真的热：元数据抓取是用户动作级、不是每秒级，如果一次动作只解析一次，就没有可省的重复，别因为「形状一样」就照搬缓存。  **R86 关闭（量过：不热，而且重复解析就是它的安全属性）**：本机实测一次主机名策略调用 = 1 次解析、首次 13.8 ms；同一主机 5 条不同 URL = 5 次解析、共 163 ms；**字面 IP 与 loopback 一次都不解析**（0.04 ms / 0.02 ms）。调用面只有两处：`_json()`（每次 provider 请求）与 `_download_artwork()`（每张封面），都是用户动作级，每个出站请求解析一次——正如条目说的「一次动作只解析一次就没有可省的重复」，唯一的重复是 provider 与 urllib 各解析一次，那是分层代价、不是这条策略路径内部的重复。更关键的是**不能照搬 R74 的缓存**：这个闸门的契约是「任何一个*当前*解析出的地址非公网就拒」，实测把一个解析器排成「先公网、后私有」，第一条 URL 放行、第二条立刻被拒；任何大小、任何 TTL 的缓存都会让第二条通过——那正是 DNS rebinding。R74 修的是展示路径（答案过期无害），这里过期有害，形状一样不代表处置一样。改为把「每次都重新解析」钉成契约测试 `test_the_gate_asks_the_resolver_again_for_every_url`（三次调用必须三次解析、字面 IP 必须零次、公网→私有翻转必须第二条被拒）；变异 V1 加 `_RESOLVED` 缓存被新测试指名杀死，V3 干脆不解析主机名被两条测试杀死，V4 让字面 IP 也走解析以 5 个 error 被杀；V2（每次调用内部自建 memo、行为不变）按设计存活，说明测试测的是「有没有重新问」而不是写法。
- [x] 2026-09-18：R73 补充既有「covers 无界增长」条目的机制：除缺少淘汰策略之外，**键分裂本身就在造不可达文件**（R73 修前：一次请求内版本变了，文件按 A 落盘、内存按 B 记账，之后没有任何路径再按 A 读它，也没有失效路径删它）。本轮修掉了请求内的分裂，跨请求的分裂（文件真的变了）仍会持续留下旧键文件，所以做淘汰策略时要把「按 mtime 收敛的旧版本键」当作主要清理对象，而不是只按总量封顶。（R75 按这条的要求做了：孤儿与旧键文件由「无别名指向 + 宽限期」一层直接回收，字节预算按 mtime 从旧到新收敛，不是只按总量封顶。见顶部。）
- [x] 2026-09-18：R73 新开：`prewarm` 路径同样各算各的键（`_prewarm_result_exists` 与 `thumbnail_asset_id_for_item` 各自调一次 `_cache_paths`，:287 与 :358）。要不要像 R73 那样把版本串起来，先量一次：一次 `prewarm_thumbnails` 对一页 N 行实际做了几次版本解析、几次 stat（本轮只量了封面请求与翻页行，没量预热）。若计数已经等于每行 1 次，就别为串线而串线。  **R80 关闭（量的结论是要串，已串）**：实测每行 2 次 `cover_source_version`（判定 1 次 + 渲染 1 次），两次都带 stat。现在 worker 每行只解析一次（:890），同一个值同时交给 `_prewarm_result_exists` 与 `cached_thumbnail_for_item`（后者早就有 `version=` 形参，:1198）。入队侧另有一次，但那是去重键且 `allow_disk=False` 不碰磁盘（:227 优先用索引里的 mtime/size），所以每行的磁盘版本解析确实是 2 降到 1。除性能外这也是正确性：R73 的注入理由（文件在请求中途变化时，不能一半按旧键判断、一半按新键写入）在预热这条路上同样成立，本轮补齐。测试逐次记录 `(row, allow_disk)`，断言序列恰为 `[("row", False), ("row", True)]`，并断言判定与渲染收到的是同一个串。
- [x] 2026-09-18：R72 新开：`allow_disk=False` 的快速翻页路径**不复核磁盘**，所以资产文件刚被删除而别名缓存还暖着时，页面仍会短时报出 `cover-asset/<id>`；浏览器请求它时 `thumbnail_asset_bytes` 返回 None，表现为一次 404 后再由预热纠正。本轮刻意不改（这条路径的存在理由就是不做任何 stat），但如果线上看到封面偶发一次空图，先查这里而不是查渲染。要不要给翻页路径加一个「本轮已确认删除」的短时负缓存，需要先量 404 的真实频率。  **R81 关闭（不必先量 404 频率：把收尾放到 404 那一侧）**：原条目的顾虑是给翻页路径加负缓存要先量真实 404 频率。本轮换成不花钱的方向——`thumbnail_asset_bytes` 答不出某个地址时，顺手把内存别名表里**指向这个 asset 的那几条**摘掉（新私有件 `cover_cache.py:430` `_forget_advertising_asset`，两个失败分支都调：`_read_bounded_file` 返回 None 意味着文件没了或超服务预算，两种都永远答不出）。翻页路径一次 stat 都没多（它本来就不复核磁盘，那是它存在的理由），代价只落在「已经失败」这条冷路径上，且只扫 4096 条上限的表。盘上的 `.asset` 不动：R80 之后预热判定会回查资产、发现缺失就重渲染并改写别名，两轮合起来是一个自愈闭环。测试 `test_an_asset_that_cannot_answer_stops_being_advertised_by_the_fast_page` 同时钉住「无关行必须留着自己的封面」，变异 E2 全表清空与 E4 反向比较都被这半条杀死。
- [x] 2026-09-18：R72 新开：`_MEMORY_CACHE_LOCK` 仍然是一把锁管三件事（缩略图字节缓存、别名缓存、缺失标记缓存），R72 只是把文件系统调用挪了出去。如果以后还要在这条链上加 stat 或 read，考虑拆成三把锁或改用带分片的结构，否则「锁内不做 I/O」只能靠单个形状断言维持，覆盖不到未来新增的锁块。  **R82 关闭（不拆锁，把断言从单个函数扩到全模块）**：先量现状——`_MEMORY_CACHE_LOCK` 14 块 98 行、`_PREWARM_LOCK` 21 块 150 行、`_LOCKS_GUARD` 1 块 5 行，锁内文件系统调用 **0 处**（R80 新加的那次 read + stat 落在锁外）。唯一需要豁免的是两处 `cover_source_version(item, allow_disk=False)`（:849、:1039）：它们是入队去重键，名字里带 disk 但按 :227 的实现只吃索引身份、不发 stat——把豁免写成「必须显式带 `allow_disk=False`」，顺带钉住这个容易看错的性质（变异 G2 去掉这个 kwarg 即被杀，而且 `test_interactive_prewarm_queue_key_does_not_stat_unindexed_items` 早就在行为侧钉着它）。新测试 `test_no_locked_block_in_the_module_touches_the_disk` 扫全模块所有锁块并自我反空转（块数下限 30、三把锁必须都被覆盖）。G1 把探针塞进 `_memory_get`、G3 塞进 R81 新写的 `_forget_advertising_asset`，后者正是条目担心的「旧断言看不见的块」，两处都被杀。结论：拆成三把锁目前没有可测收益，等真出现必须在锁内做 I/O 的需求再说。
- [x] 2026-09-18：R72 承接 R66：`cached_thumbnail_for_item` 在一次请求里独立重算 `cover_source_version` 三处（磁盘键、内存键、锁键）仍未处理，本轮只处理了同一函数族里的锁内 stat。三处重算之间被标签写回插队会留下「键旧内容新」的孤儿条目，属于正确性问题而不是性能问题，优先级不低于本轮。（R73 已修：三处重算合成一次解析并沿键构造往下传，另加整条链路只解析 1 次的端到端计数用例，见顶部。）
- [x] 2026-09-18：R71 新开：构建侧的产物上限仍是两处字面量（`tools/build_release.ps1:283-284` 的 10GB、`tools/build_android_release.ps1:105-106` 的 1GB），校验侧本轮已参数化。不动它们的理由是：构建侧守的是自己刚产出的文件，没有需要注入上界的测试路径。如果以后要让构建流程也支持更紧的上界（例如不同渠道产物尺寸差异），请复用校验器的参数名 `-MaxArtifactBytes` / `-MaxAndroidArtifactBytes`，不要引入第三套命名。  **R85 关闭（不动参数化，改为钉住两侧必须相等）**：四处取值实测一致——校验器默认 `[long]$MaxArtifactBytes = 10GB`（:14）与 `[long]$MaxAndroidArtifactBytes = 1GB`（:15），`build_release.ps1:283` 的 `-gt 10GB`，`build_android_release.ps1:105` 的 `-gt 1GB`✓ 条目说的「构建侧守自己刚产出的文件、没有注入需求」成立，所以本轮不给构建侧加参数。真正会坏掉的是**两侧不一致**：构建侧放宽就等于产出一个自己的证据校验必拒的发布，收紧则相反地放行一个策略上无效的工件。新测试 `test_the_build_side_ceiling_stays_in_step_with_the_verifier_default` 从三份脚本里把数字读出来配对断言，并钉住条目要的第二件事：全仓只有这一对参数名（`$Max\w*Bytes` 的集合恰为两个），以后要加第三套命名会先在这里失败。变异 Z1（构建侧 10GB→20GB）、Z2（校验器默认 10GB→5GB）、Z3（多出 `$MaxExtraBytes`）、Z4（只有 Android 一侧漂到 2GB）全部被指名杀死；本轮不改任何生产取值。
- [x] 2026-09-18：R71 新开：`RECOVERY.md` 现在既被恢复手册内容断言读取，又承载了产物上界的说明；同类「文档即契约」的文本还有几处（`test_offline_verification_script.py:158`、:180 一类）。以后如果恢复流程的 CLI 再增参数，要考虑把断言写成从脚本 `param()` 块生成期望，而不是在测试里再抄一份中文句子，否则文档与断言会各自漂移。  **R109 关闭（就按这条给的方向做：期望改为从脚本 param() 块与权威 VERSION 生成，测试里不再手抄第二份）**：test_offline_verification_script.py（现 293 行）加两个解析器 —— script_parameters(root, rel) 只读顶格的 param( 块（脚本内部函数自己的参数表不进契约 ✓ 并要求全脚本恰有一个顶格块）✓ recovery_command_parameters(text) 只取每行 tools 脚本路径 **之后**的 -Name token（路径之前的属于 powershell.exe ✓ 反引号续行先合并 ✓ 只在一词的开头才算开关，所以 release-evidence-index-latest.json 这类文件名里的连字符不会被误读）。两条新测试取代手抄：test_recovery_manual_baseline_follows_the_version_file 以 VERSION 为唯一权威，断言手册里那句「当前源码基线为」恰好出现一次且等于 VERSION，并禁止旧的「当前配套版本为」再出现；test_recovery_manual_documents_the_parameters_of_the_tools_it_runs 先钉命令清单本身没蒸发（至少 3 个脚本），再双向钉 —— 脚本声明的每个参数必须在手册中以 -名字 出现（新增开关不能悄悄不进恢复流程），手册用到的每个开关必须仍在脚本声明里（文档不得 advertised 一个已被删掉的参数）。实测参数面：index_release_evidence = ArtifactRoot / OutputPath / MaxEntries ✓ verify_release_evidence = ArtifactDirectory / SourceDirectory / RequireCompleteEvidence / Json / MaxArtifactBytes / MaxAndroidArtifactBytes ✓ test_offline = Package / Browser ✓ test_android_emulator = SdkRoot / AvdName / InstallSdk / KeepRunning。这条契约立刻反咬一口：模拟器四个开关原本无人记录 ⇒ RECOVERY.md 补上它们的说明（现 127 行）才让门禁成立 —— 正是条目预言的「文档与断言各自漂移」被抓现行的样子。范围边界（并入本条不另立项）：该文件其余的文本存在断言钉的是门禁脚本自身的契约（哪些步骤必须在、清理必须在恢复环境之前、发现清单不得退回手抄列表），不是文档的第二份抄本 ⇒ 不在本条对象内。变异（同一副本 ✓ 逐条跑）：给 index_release_evidence.ps1 加一个未记录的 switch、把 OutputPath 改名、把手册基线写成旧号、只改 VERSION 不改手册、删掉手册里的模拟器命令行、让手册调用一个脚本并不接受的开关 —— 六种全部命中。
- [x] 2026-09-18：R70 新开：R70 之后 `favorites` 的**行数**有界，但 `state.sqlite3` 的**文件**不回收：实测修好后稳定在 5.6 MiB 不再增长，可是被裁剪掉的页仍留在文件里（SQLite 删除不 shrink）。要回收需要 `VACUUM` 或 `auto_vacuum=INCREMENTAL`，而这两者都要在 `_STATE_WRITE_LOCK` 与 WAL 的约束下设计（VACUUM 会重建整库，NAS 上是可感知的停顿），不能顺手加。先量：真实库里峰值行数与回收收益各是多少。  **R85 关闭（条目要的「先量」量完了，结论是不加）**：favorites-only 夹具实测——满库 50000 行 = 497 页 × 4096 B = 2,035,712 B（1.94 MiB），freelist 0；随后 3 轮裁剪循环（每轮两次 25000 行保存）**页数仍是 497**，freelist 247，也就是可回收上限 0.965 MiB，而文件不会随轮次增长——SQLite 复用被裁剪释放的页，文件被钉在「一张满表」的大小。两条回收路线实测：`auto_vacuum` 现在是 0，先 `PRAGMA auto_vacuum=INCREMENTAL` 再 `incremental_vacuum` 是 0.002 s 的空操作（改模式本身要重建库）；`VACUUM` 0.012 s 确实把库缩到 237 页 / 970,752 B，省 1.03 MiB，但**下一次普通保存立刻回到 497 页 / 1.94 MiB**。所以为了不到 1 MiB、且一轮保存就还原的收益，去付 NAS 上一次重建整库的写锁停顿是不划算的，条目担心的「不回收」实际上是有界复用。把让这个结论成立的性质钉成测试：`test_repeated_trim_cycles_reuse_pages_instead_of_growing_the_file`（页数跨轮相等、freelist 必须真的非空以免断言空转、`auto_vacuum == 0`、以及 incremental_vacuum 在这类库上是空操作）。R70 记的 5.6 MiB 含 playlists/playback 与更宽的 id 分布，与本轮favorites-only 夹具的 1.94 MiB 不矛盾，是两个不同夹具的量。
- [x] 2026-09-18：R70 新开：50000 这个数字现在出现在四处（`_strings` 的请求规范化三处 :179、:180、:311 与 `MAX_PERSISTED_FAVORITES`），本轮只给 :311 那条加了漂移守卫。要不要把它们收成有名字的常量（请求界与存储界各一个），取决于是否真的想让 `favorites_remove` 也受存储界约束（现在它是独立字面量，语义上应该更宽而不是更紧）。别为了消除字面量而把两种界合并成一个。  **R83 关闭（命名两个请求界，一个都不合并）**：新增 `MAX_REQUEST_FAVORITES`、`MAX_REQUEST_PLAYLIST_DELETIONS`，保留 `MAX_PERSISTED_FAVORITES`，注释写明两者失败原因不同（请求界防单客户端让服务端解析无界列表，存储界决定盘上留多少）。归属逐个确认：`_state_changes` 的两处（含 `favorites_remove`）与 `save_user_state` 的读入截断都是**请求**侧——R76 的漂移守卫正是靠「把存储界抬到 50001 仍然只留 50000」证明 :311 那一处属于请求侧的，只有 `_trim_favorites` 是存储侧。条目问的「要不要让 `favorites_remove` 也受存储界约束」答案是不受：它保持请求界，且因为分了名，将来要单独放宽它不会牵动存储行为。`playlist_delete` 的 1000 与 `MAX_PERSISTED_PLAYLISTS` 的 1000 数值相同而语义无关，按要求不合并、只命名，并补上行为断言（1001 截到 1000，设成 4 截到 4）。新测试 `test_the_favorites_request_bound_reads_its_own_name` 只搬请求界：请求界=10 时 20 条只留 10 条、存储界仍是 50000，把两个常数写成别名的实现过不去。变异 S1（补丁路径读存储界）、S2（读入处退回裸 50000）、S3（delete 借用请求界）由这条新测试指名杀死，S4（磁盘裁剪借用请求界）被两条既有测试杀死——分离本来就是行为事实，这轮让它读得出来。
- [x] 2026-09-18：R69 新开：`PROJECT_CONTEXT.md` 的前导条目段并不满足 newest-first（实测两处倒序：第 141 行 2026-09-06 跟在 2026-09-05 之后、第 242 行 2026-09-17 的补录条目跟在 2026-09-05 之后），而 `tests/test_change_record.py` 只对 `CHANGELOG_AI.md` 与 `TODO.md` 强制这一条。要么把该测试扩展到第三份文档并先做一次安全的排序整理（规则条目是给人检索用的，顺序错会误导），要么在文件里写明它的顺序只是信息性的。本轮只写脚本复刻测试的真实作用域，不动别人的条目顺序。  **R79 关闭（补齐断言 + 安全整理）**：先纠一个数——R69 记的「两处倒序」是**每趟扫到的第一个**，实测 281 条前导条目里要搬 **17 条**才收敛：190-196 那七条 09-06 跟在 09-05 之后是一段错位的块，282 行那条 09-17 补录条目跨了 141 行。改法只搬违规条目、不做全量排序（那会重排别人轮次的条目顺序），并用「集合不变 + 倒序归零」两条断言兜住搬运本身。然后把 `tests/test_change_record.py` 的 newest-first 扩到第三份文档：条目正则要接受 `： **rule**` 这种冒号后带空格的写法（naive 的 `[： ]\S` 会把 281 条里 **110 条**规则条目判成格式错误——变异 N2 就是这个），并顺手把「两份文档最新日期一致」的两两比较换成三份的集合唯一。承重性由 N1（还原乱序备份即失败）与 N3（去掉第三份即无人报错）配对证明。**这条改变了后续每轮写文档的契约**：补录旧日期的条目不能 prepend 到最前面。
- [x] 2026-09-18：R69 新开（R71 已修，见顶部）：`test_build_release_script.py:398` 用 `handle.truncate(10 * 1024 ** 3 + 1)` 造超大工件，实测在临时卷只剩 2.18 GB 时抛 `OSError: [Errno 28]`，也就是「磁盘快满时离线门限会出现与改动无关的失败」。要么在空间不足时 `skipTest` 并写清缺多少，实测最小可行尺寸这条路走不通：验证器判的是「超过 10 GiB」，10 GiB 这个界写死在脚本里，任何真文件样例都要么不小于它、要么就得真的造出十吉字节的合法数据长度。R71 取的另一条路是把两个界做成显式注入参数（默认值仍是发布策略），样例降到 4 KiB，顺序契约改由形状断言承担，门禁不再赌磁盘空间；没有引入 skipTest。要么把超大尺寸压到仍明显超过上界（验证器拒绝的是「超过 10 GiB」这一判定，不需要真的把有效数据长度设到 10 GiB 以上，只要更大即可）。下一轮先量一下最小的可行尺寸再改。
- [x] 2026-09-18：R69 新开：每次 SUBSCRIBE 都独立做一次 `getaddrinfo`，搬到锁外之后连「被锁串行化」这层意外限流也没了。要防解析洪泛（一台机器并发发很多 SUBSCRIBE，每个打一次解析，甚至指向一个慢 DNS 的域名），需要带上限的解析缓存或按连接节流；本轮不做，因为没有任何解析压力实测数据，凭感觉加缓存会引入租约与 DNS 记录的一致性问题。  **R90 关闭（条目要的实测数据有了，绑定的是并发而不是缓存，另外堵掉「为注定被拒的请求做解析」）**：条目说「本轮不做，因为没有任何解析压力实测数据」，那就先把数据量出来（`%TEMP%\r90measure.py` / `r90measure2.py`，仓库内不留脚本）。三条：其一，洪泛形状——16 个并发新订阅 = **16 个 worker 同时进 `getaddrinfo`（32 池的 50%，峰值即 16）**，且 R69 把解析移出锁之后确实没有任何东西挡着；其二，白烧——表满 64/64 时再来 20 个 SUBSCRIBE，**20 次解析全部花在注定被 `:451` 拒掉的请求上**（因为 `:435` 的校验排在 `:450` 的上限判定之前），客户端拿到的理由都是同一句 `too many event subscriptions`；其三，正常路径基线 3.0 µs 中位 / 3.7 µs p99（续订 1.2 µs、零解析）。处置两处：解析之前加一次无 I/O 的确定性预检 `_hopeless_admission_reason()`（`dlna/service.py:417`，只在「已 shutdown」或「表满且无可回收租约」时回答，短暂拿一次总线锁、不碰任何 I/O，权威判定仍在解析之后那段锁里，两进程竞态语义不变），白烧从 20 降到 **0**，且理由字符串与权威路径逐字相同（测试专门钉这条，防两条路径漂移）；并发侧加 `ConcurrencyGate` 上界 4（见 `:9` 的结论），洪泛峰值 16 -> **4**；饱和时溢出请求 1.02 s 内被拒，而它前面那次解析还卡着——「等满自己的超时」而不是「等别人 DNS 死」。观测按 R87 的规矩一起补：`snapshot()` 多 5 个扁平整数 `validating`/`validation_limit`/`validation_waiter_limit`/`validation_waited`/`validation_rejected`（:594 起），先读闸门再拿总线锁，两条路径不交叉持锁。测试 4 条（洪泛峰值含反空转、白烧与可回收租约、饱和降级与策略取值、计数形状且渲染里不出现主机名/URL），全部跑完 1 s 后遗留线程 0（R88 判据）。变异 11 例：K1/K2/K3 杀在预检那条测试的三个分支，K4（上限写成 32）/K5（整个闸门拿掉）/K6（饱和时不但不拒还带着空回调放行）/K10（不发布计数）杀在洪泛那条，K7（等待上界抬到 30 s）杀在「先读策略再看实测」那半条——这条是被自己的第一版逼出来的：最初等待上界的期望值是从被测常量算的，等于让测试跟着实现一起放宽，补了常量上限断言才杀得掉；K8 见 `:9`；K11（把对端写进计数）杀在隐私那半条；K9（同一个数换个写法）按设计存活。控制组 143 条绿。
- [x] 2026-09-18：R69 新开：事件面仍然只有一把 `_lock`，GENA 投递 worker 的计数更新（`service.py` finally 段）与准入、通知、诊断共用它。投递风暴（多个控制器各自排队）会让这把锁成为瓶颈。要不要把计数器拆成独立锁或改走无锁计数，需要先做竞争测量（同一进程内统计锁等待时间），不要为了「看起来更并发」而拆。  **R87 关闭（做了条目要求的竞争测量：不拆锁，但把「锁不跨越网络调用」钉成测试）**：同进程内跑投递风暴，量真实路径而不是自造压力——64 订阅（`MAX_EVENT_SUBSCRIPTIONS`）× 24 轮 × 50 ms 回调 = 256 次投递，wall **3.232 s**，而回调睡眠本身在 4 个 worker 上的并行下界是 **3.200 s**，差值 32 ms 摊到每次投递 0.125 ms，也就是锁与调度总共只占 1%；64 × 16 × 25 ms 那组是 1.635 s 对 1.600 s，同样 2%；4 × 8 × 2 ms 那组 0.023 s 对 0.016 s，32 次回调里 31 次的起始时间落在上一次回调的 2 ms 之内，即投递确实并行。**风暴期间一次真实准入（`subscribe()`）耗时中位 0.026 ms、最大 0.042 ms**。方法学上记一条反面教训：最初用一个 1 kHz 轮询线程去采「锁等待时间」，结果它自己就是竞争源，把同一组 4×8 从 23 ms 拖到 21.337 s——所以数必须来自真实路径。结论是不拆：条目警告的「为了看起来更并发而拆」正是这里的情形，投递风暴的上界由 `max_pending` 与 64 个订阅租约决定，而不是锁。值得钉的是让该结论成立的那条结构不变量：`fetch_lan` 在锁外调用（:581-588），finally 段只动计数器（:593-597）；新测试 `test_a_delivery_in_flight_does_not_hold_the_lock_the_admission_path_needs` 用一个被卡住的回调（单 worker）加一次新准入，断言准入**在回调仍被卡住时就已经返回**（第一版把断言写在 release 之后，测不出「被阻塞后放行」与「从未被阻塞」的差别，是变异 P1 把它逼出来的）。变异 P1 把 `fetch_lan` 挪进 `with self._lock` 后，新测试与既有 `test_event_shutdown_honors_timeout_while_callback_is_in_flight` 双双变红，那一轮 wall 9.632 s 对控制组 1.689 s，就是「一个不可达控制器拖住整个事件面」的样子；P2（timeout 写成 3.0）按设计存活。附带量到的事实：超过 64 个租约时准入是直接拒的（`service.py:451` `too many event subscriptions`）。
- [x] 2026-09-18：R68 新开：`service.py` 里 `isinstance(value, bool) or not isinstance(value, (int, float))` 同一段习语有三处（:59 `_duration`、:73 `_safe_count`、:144 本轮新增的 `_finite`），但契约不同：一个只接受 int、一个折成 None/0、一个要上限钳制。合并成一条公共判定要同时处理「大整数不要转 float」（`float(10**400)` 抛 OverflowError，现在 `_safe_count` 靠不转换规避），需要溢出用例护航，别顺手改。  **R84 关闭（合并类型门，不合并契约；顺带补上一个真实溢出缺口）**：先量——这条习语在活动代码里是 **6 处**而不是 3 处（`service.py` 三处 + `diagnostics.py:13`/`:31` + `renderer.py:24`），条目记的三处只覆盖 service。抽出 `_is_count_number(value, allow_string=False)` 统一 bool 拒绝（`bool` 是 `int` 子类，设备送来的 `true` 会被当成计数 1），三个调用点各自的契约保持不变（钳制 / 回退 / 上限）。**测量暴露的真缺陷是 `_finite`**：它的 `float(value)` 不接 OverflowError，实测 `_finite(10**400)` 抛出，而同族的 `_safe_count`、`_saturating_increment`、`renderer._safe_position` 都接住了——也就是「大整数不要转 float」这条警告在三个读者里只有一处没做，一个巨大的 int 就能把投送状态投影变成 500 而不是 0.0。修法照包内既有约定：catch `(TypeError, ValueError, OverflowError)` 之后回 0.0，与 `inf`/`nan` 同答案。合并范围**刻意止于 service**：另外三处住在别的模块，而 `service.py` 依赖它们，公共门没有无环的家，本轮不为此新建模块；`diagnostics._safe_limit` 没有 float 路径，实测安全。溢出/布尔/字符串/上限四类用例进 `test_the_forgiving_numeric_readers_survive_every_unreadable_shape`；变异 T1（不再接 OverflowError）以 3 个 error 被杀，T2（门放 bool 通过）同时被一条既有测试 `test_seek_position_resolves_units_signs_and_bounds` 杀掉，T3（忘记有个读者要解析字符串）、T4（计数钳制消失）也各自被指名杀死。
- [x] 2026-09-18：R68 新开：SCPD 里 `A_ARG_TYPE_SeekMode` 是无约束 string（service.py:221），而我们实际只认 ABS_TIME/REL_TIME。把允许值写进服务描述文件是对控制器的自我声明（不少控制器按 SCPD 枚举渲染快进 UI），改动面小，但要先确认没有客户端依赖宽松定义，属可设备验证的改进。  **R78 关闭（声明与处理统一到一份数据）**：`scpd()` 现在从 `SEEK_UNITS` 派生 `A_ARG_TYPE_SeekMode` 的 `allowedValueList`（`dlna/service.py:336` 起），也就是 `_seek_position`（:171 拒绝未知单位）实际接受的那一份，不会再漂成「宣传但不接受」或「接受但未声明」。原条目要求的「确认没有客户端依赖宽松定义」不阻塞这一步：`allowedValueList` 是声明不是强制，我们的处理逻辑一行未动，宽松控制器行为不变。测试`test_the_descriptor_declares_exactly_the_seek_units_we_accept` 同时钉住「其它变量保持宽松」，变异 M3 不声明、M4 抄第二份常量、M5 给所有 A_ARG_ 变量都加枚举、M6 渲染漏掉枚举，四条全被它杀死。真机侧「控制器是否按枚举渲染快进 UI」的观察不另立新项——P0 段已有的 R68 真机项（相对 seek 只在桩后端验过）正是它的归宿。
- [x] 2026-09-18：R67 新开：`_prewarm_result_exists` 对 `.asset` 只做 `isfile`，不像 `_read_asset_alias:334` 那样校验内容是不是 64 位十六进制、也不回查 asset 文件在不在。盘上留下一个内容损坏或指向已回收资产的别名时，读取路径会自行回退重渲染，但预热会长期误判「已有结果」而不去修它。要么在判定里复用严格校验（多一次小文件读），要么让预热对损坏别名做一次自愈覆盖，需要先量代价再定，别凭感觉加读。  **R80 关闭（走「复用严格校验」那一支，代价已量）**：判定现在是「`.jpg` 或 `.none` 命中即跳过，否则进 `_alias_asset_key`」（`cover_cache.py:287`），别名规则与读路径同一个家：内存别名表命中只花 1 次 asset stat，未命中才读那 65 字节、校验 64 位十六进制、再回查资产在不在。实测 200 行满别名页：修复前 25.4 us/行，修复后首次（内存冷）193.4 us/行、之后 42.9 us/行。代价可控的理由是**作用域**而不是感觉：这个判定只服务交互式预热，队列上限 `INTERACTIVE_PREWARM_MAX_PENDING = 96`（:93），每轮最坏 96 x 193 us = 18.6 ms；20000 条/轮的库扫描走另一条 worker（:1060 起，先 isfile 媒体文件再直接 `cached_thumbnail_for_item`），一行未动。顺带修了夹具：`test_interactive_prewarm_skips_results_the_writer_actually_produces` 原来只造 `.asset` 不造资产，而写者本来就是先写资产后写别名——那个夹具恰好就是本轮要拒绝的状态。变异 C1 退回裸 `isfile`、C2 过度纠正成「别名一律不算结果」、C3 只校验正文不回查资产，三条全由新测试指名杀死。
- [x] 2026-09-18：R67 新开：`_atomic_bytes` 对每次封面写入都 `os.fsync`（:879）。alias 是 64 字节小文件且 `os.replace` 已保证可见性原子，逐次 fsync 在 SMB 上是可感知的等待；淘汰策略落地时应一起评估哪些工件需要耐久、哪些只要「重启后能重建」。本轮不单独改，避免在没有磁盘压力数据时削弱一致性。（R75 淘汰策略已落地，但这半件「哪些工件需要耐久」仍未评估。）  **R82 关闭（评估结论：只有图片字节值得等磁盘）**：`_atomic_bytes` 加了 `durable` 形参（`cover_cache.py:1155`）。策略是共享资产 `.jpg` 继续 fsync——内容地址指的是**原图**而不是渲染出来的 tile，盘上留一个写坏一半的 JPEG 没有任何读路径能发现，会永久端出去；`.asset` 别名（:1319）与 `.none` 负标记（:1293）改成不等：这两种形状「要么对要么一眼是垃圾」，别名由 R80 的 64 位十六进制校验加资产回查拒绝、负标记内容恒空，损坏等同于不存在，下一轮自己重渲染重写。写序仍然安全：先写资产（durable）后写别名，不可能出现「别名活着、资产没了」。矩阵 H1 退回策略、H2 反转标志、H4 连图片也不 durable，三条全被新测试指名杀死。**H3 存活并且应当存活**：把 `handle.flush()` 一并省掉是等价变异——`with` 退出时 close 本来就会 flush，所以 :1162 那行是冗余代码，本轮只记录，不另立待办。条目想要的 SMB 侧收益数字仍是设备观察，归宿是 P0 段既有真机项。
- [x] 2026-09-18：R66 新开（R69 已复现并修好：修复前控制请求等待 2.002 s，修复后 0.005 s）：DLNA `subscribe()` 在 `self._lock` 内调用 `_callback_url` → `network.py:58 socket.getaddrinfo`，一次 hostname 慢解析会把 GENA 全局锁按住秒级，期间 `notify_renderer` 与其它控制器的 SOAP 线程一起等（子代理模拟 1.5 s DNS 实测另一线程阻塞 1.30 s）。修法是把 `_callback_url` 移到拿锁之外。现有事件测试一律把 `_callback_url` 打桩，恰好绕开该路径，属明确缺口。
- [x] 2026-09-18：R66 新开（R69 已修，见顶部）：DLNA 新订阅准入不清理过期租约。`MAX_EVENT_SUBSCRIPTIONS` 满 64 且都是过期记录时，新 SUBSCRIBE 与 renew 一律 412，而清扫只发生在 `notify_renderer`、`snapshot`（要有人 GET /api/health）与 drain 三处；headless NAS 上渲染器静默就可能长期 412。修法是在 cap 检查前先做一次过期清扫。
- [x] 2026-09-18：R66 新开（R68 已修，见顶部）：AVTransport `Seek` 忽略 `Unit`，`_seconds` 解析失败一律回 0.0，于是 `Unit=NEGATIVE Target=+0:00:30`（UPnP 合法相对快进）、`Unit=TRACK`、缺 Target 都会真的执行 seek(0) 并返回 200。按 spec 应回 402/704 且**不触碰渲染器状态**。现有测试只钉住 `_seconds` 助手的回退值，没钉「回退值被当成真实位置执行」这个后果。
- [x] 2026-09-18：R66 新开（R67 已修，见下）：`cover_cache` 三条写盘路径缺 OSError 保护：`cached_thumbnail_for_item` 里 `secure_directory(root)`、负标记 `_atomic_bytes(missing, b"")`、asset 与 alias 的 `_atomic_bytes`（约 984-1005 行）。同文件 `generate_asset_thumbnail:440-445` 已有明确契约「缓存写失败不能失败响应」并有测试模板（`test_cover_cache.py:911`），本路径是对称遗漏：磁盘满或只读挂载时冷封面直接 500，而渲染好的字节明明在内存里。
- [x] 2026-09-18：R66 新开（R67 已修，见下）：`_prewarm_result_exists`（`cover_cache.py:280-288`）只查 `.jpg` 与 `.none`，但全文件从不写 `.jpg`（`_atomic_bytes` 的调用点只有 missing / asset_target / alias 三处，`.jpg` 位置写的是 `<key>.asset` 文本别名）。所以预热去重对**已经渲染过的条目永远失效**，翻页时每项都重走完整路径（重开别名、读回 JPEG、挤占内存 LRU）。更糟的是 `test_cover_cache.py:238-251` 手工创建了 `.jpg` 文件来断言跳过，用编造的文件状态掩盖了这个回归。
- [x] 2026-09-18：R66 新开：`covers/` 目录没有任何容量或年龄淘汰。缓存键含 `mtime_ns:size`，标签写回或文件重存即生成新键，旧条目永不回收；`prune_transcode_cache` 用不递归的 `os.listdir` 且扩展名白名单只有 .mp3/.wav/.flac，`covers/` 子树不在射程，`_prune_artwork_cache` 只管数据库里的 provider 原图。终局是 cache 卷写满（也正是上面写失败变 500 的诱因）。需要设计淘汰策略，NAS 上 atime 不可靠，单独一轮。（R75 已落地：三层清扫（过期负标记与崩溃 temp、悬空别名与孤儿资产、按 mtime 收敛的字节预算与磁盘不留量），触发点是唯一的落盘口 `_atomic_bytes`，见顶部。条目数上限与「128.9 ms 仍在请求线程上」另立两条。）
- [x] 2026-09-18：R66 新开：`cached_thumbnail_for_item` 在一次请求里独立重算 `cover_source_version` 三处（磁盘键、内存键、锁键），中间被标签写回插队就会把结果写到旧版本键、把内存条目记在新版本键下，留下「键旧内容新」的孤儿并让并发去重同时失效；`thumbnail_asset_id_for_item` 还在全局 `_MEMORY_CACHE_LOCK` 内做 `os.path.isfile`，SMB 失联时会把整条封面服务挂住。（R72 修掉本条中「`thumbnail_asset_id_for_item` 在 `_MEMORY_CACHE_LOCK` 内做 `os.path.isfile`」那半件；R73 修掉三处重算并把端点那次 ETag 解析一起串成同一个值，见顶部。R73 另量到 `allow_disk=False` 被键计算绕过，那是新的一条，不在本条范围内。）
- [x] 2026-09-18：R65 新开（R70 已修，见顶部：写路径事务内裁剪，实测四轮 delta 后表行数从 150000 钉回 50000）：收藏在磁盘上没有上限。`MAX_PERSISTED_FAVORITES = 50000` 只出现在 `load_user_state` 的读取 LIMIT 里，而 `save_user_state` 的过期增量分支只做 `INSERT OR IGNORE`（`state_store.py:298`），从不裁剪；全量分支虽把入参截到 50000，但客户端可以反复增量把表推到远超 5 万行，读得到的部分不变、磁盘与事务成本单调涨。下一轮先量行数增长上界，再决定是写路径裁剪还是读取路径顺带清尾。
- [x] 2026-09-18：R65 新开：`_trim_persisted_playlists` 仍每轮发两条 `NOT IN (SELECT id FROM playlists ORDER BY created_at ASC, id ASC LIMIT ?)`，一条清子表一条清父表。前者对孤儿行必要，后者的语义其实已被 `keep_ids` 表达，可以合并成按 `keep_ids` 删除以省一次有序子查询；实测收益在 1 ms 以下，优先级低，别为它牺牲孤儿清理的可读性。  **R89 关闭（量完决定不合并，也不新写测试：省 0.58 ms，而那个形状早就被钉住）**：真实 schema 实测（每列表 3 首，脚本留在 `%TEMP%\r89measure2.py`）：封顶 1000 条时现有两条有序子查询 best **2.112 ms**，改成按 `keep_ids` 绑定参数的合并版 **1.532 ms**，省 **0.580 ms**；两倍封顶 2.202 对 1.418，省 0.784 ms；十几条播放列表的常见规模是 0.060 对 0.034 ms，省 0.026 ms，落在噪声里。两种写法留下的集合逐行相同（`p00000..p00999`、孤儿 0、重复 trim 稳定），条目估的「1 ms 以下」成立。不合并不只是因为收益小：合并版要给父表删除绑定 `len(keep_ids)` 个参数，语句形状就此与上限耦合，而 `:37` 恰恰预期把这个上限往上调，越过 SQLite 的 `SQLITE_MAX_VARIABLE_NUMBER` 下限 32766 之后，换来的是状态保存里的 `too many SQL variables`。这个形状已有测试守着：`test_state_store.py:755 test_playlist_trim_does_not_depend_on_sqlite_large_variable_limits`（单条语句参数超过 999 即断言失败），本轮变异 C1（真的把合并版套上去）正是被它杀掉的，所以本轮不另写一条同等杀伤力的测试（第一版写了，矩阵显示与既有钉法重复，已删并在该测试上补了这段结论）。顺手排掉一个怀疑：trim 的 :216/:233 与恢复侧 :272 都是 `ORDER BY created_at ASC`，写入侧归一 `state_projection.py:113` 也是保留前 1000 条，三处同向，不存在「该留最新」的漏网。
- [x] 2026-09-18：R65 新开：总量上限若从 50000 再往上调，`GROUP BY playlist_id` 的一次全索引扫描会成为新的常数项（本轮实测在 1e6 行规模约多花 16 ms）。真要提额，配套的是持久化每个播放列表的行数计数，而不是回到逐列表 COUNT。  **R115 关闭（就走条目点名的那条路：持久化每个播放列表的行数计数，而不是回到逐列表 COUNT）**：`playlists` 新增可空 `track_count`（NULL=未知；`ensure_state_schema` 用 `PRAGMA table_info` 补列，默认值必须是 NULL，给 0 等于宣称整个旧库都是空列表），两条写路径在同一条父行语句里记账 `len(playlist["trackIds"])`（`state_projection.strings()` 已去重，所以这个数就是随后插入的行数）；`_trim_persisted_playlists` 先读 `LIMIT cap+1`，前瞻行判溢出、`state_meta` 的 `playlist_children_verified` 判子表孤行是否已清，两者都过且 `children_are_within_budget()` 认可全部计数才直接返回，一条子表语句都不发；否则跑一次 `NOT IN` 清扫并落标记，再用 `UPDATE playlists SET track_count = (SELECT COUNT(*) ...)` 取权威值，之后的裁剪决策只来自权威值，删完还把真实值回写。错的方向被穷举过：高估只会多走慢路径或被安全跳过；低估且总数仍在预算内时留下的行本来就是读者 LIMIT 看不到的行；所以任何删除都不会基于一枚没核验过的计数发生。回归向量（新增一枚不经记账的子行写入者）由源码级测试钉住。1e6 子行/1000 列表实测（内存库）：旧形状每次保存固定付 202.91 ms（两条 `NOT IN`）+ 37.21 ms（分组计数）≈ 240 ms，改后稳态快路径 0.77 ms，慢路径 230.56 ms 只在升级后的第一次保存或真需要裁剪时付一次；本条原文的 16 ms 是磁盘库上分组计数的旧测值，本轮内存库复测 37 ms，量级结论不变。测试：`src/app/server/state_count_policy.py` 86 行纯策略 + `test_state_count_policy.py` 9 项 + `test_state_store.py` 内 `PersistedPlaylistCountTests` 17 项（全类 54 项绿）；仓库外副本 15 个具名变异 V1～V15 全灭。
- [x] 2026-09-18：R65 进展登记：`state_store.py` 363 行本轮读完（两条写事务、trim 的全部预算语义、外键与级联夹具、revision 读写），R59 欠读清单里这一项可以划掉；`cover_cache.py` 与 `dlna/service.py` 的并行只读审计结论尚未落地，落地后另轮记录。
- [x] 2026-09-18：R64 新开：投送期间本地元素与受控端同时在跑，`renderIncomingRendererSession` 不暂停 `audio`，也没有任何人停止本地的流请求。这不是显示问题而是所有权问题：本机能同时有两路解码与两路带宽占用。需要定口径（投送即暂停本机、还是本机继续但静音、还是禁止并发），并连带解释恢复投送结束时谁该接管。属于产品行为决定，先立案。〔R122 负责人裁定 D＝三段口径一并生效：① 投送即停本机（受控端开播时本机元素与宿主播放器都要停，不再是「显示跟随、解码照跑」）；② 本机播放意图抢占投送（用户在本机点播放、切歌、添加并播放时本机接管并结束受控会话）；③ 投送结束不自动续播（受控会话停止后本机保持停止，由用户重新起播，不做隐式恢复）。本条属代码桶，实施留到下一轮并配判别测试与仓库外变异。随 D 一并并入本轮取证的四处缺维消费者：`loadCurrent()` 非 remote 分支（`app.js:4403` 设 src、:4411 播放）、`audio.ontimeupdate`（:8152 只有 `isRemoteTarget()` 门）、MediaSession 的 play 与 pause 处理器（:2301、:2306 同样只看 `isRemoteTarget()`）——四处都没有 `isIncomingRendererSession()` 这一维；可达性判据不变：`stopLocalAudio()` 全文只有三个调用点（:2065 停止路径、:4338 remote 分支、:8141 DSD 失败），受控开播不经过其中任何一个。〔R125 实施完成并关闭（该条在 R122 登记裁定时位于 L69，本轮插入记录前实测在盘上为 L72）：三段口径全部落地。D-1 投送即停本机＝`app.js:2053-2060`，只在「投送刚开始」那一次跃迁调 `stopLocalAudio()`，1.5s 轮询不得每拍拆元素；D-2 本机播放意图抢占投送＝新函数 `app.js:2104-2119` `preemptIncomingRendererForLocalPlayback()`（同步记账＋清 `rendererSession`/`rendererSnapshotAt`＋**不 await** 的 `controlIncomingRenderer("stop")`，桥不可达不得拖住本机起播），接线在 `:4390-4395` `loadCurrent()` 非 remote 分支、remote return 之后与写 `audio.src` 之前，并配 `:2037-2049` 的保有权抑制（命中被本机抢占的那路投送且本机确在播时判为无投送，否则当场清记账）与 `:294-298` 记账字段；D-3 投送结束不自动续播＝`app.js:2062-2070` 只 `restoreLibraryNowPlaying()`＋`setPlayButton(false)`＋`updateMediaSessionPlaybackState()`，刻意不 `coreControl("stop")` 以保住队列位置、绝不 play。取证阶段点出的四处缺维消费者全部补齐：`loadCurrent()` 非 remote 分支、`audio.ontimeupdate` cue-tail（`:8260-8264` 加 `!isIncomingRendererSession()` 门，自动走队列不算本机播放意图）、MediaSession 的 play 与 pause（`:2378-2390` 首行按投送路由）。判别测试为新增 `src/tests/test_ui_renderer_ownership.js`（44 条断言，其中 7 条源级接线断言；函数在 `vm.runInNewContext` 里真跑，用假节点写入计数判别）与 `test_ui_playback_authority.js` case 3 改造（断言投送期间 cue-tail 冻结）。仓库外副本变异 V1～V10 逐条被杀，控制组 Python `Ran 2448 OK (skipped=3)`、Node 74 文件 0 失败。〕
- [x] 2026-09-18：R64 新开：`addQueueAndPlay` 用 `isPlayingNow()` 判断「别打断正在播的」，投送期间该判断读的是受控端。若本机 `<audio>` 其实没在播，用户点「添加并播放」会被降级成只加入队列不切歌，与字面预期不符。要不要按操作对象区分（本机加播 vs 投送加播）需要定口径。〔R122 负责人裁定 A＝按「死码证伪 + 残余语义并入 L69」收口，本轮只登记不实施。实测：`addQueue`（`app.js:4007`）、`addQueueAndPlay`（:4017）、`playFolder`（:4240）三个函数在全仓 js/html（含 `src/tests` 与 `android-client`）只有各自定义行一次命中，调用点 0，也无 globalThis 或 window 形式的动态导出；右键的 queue 与 queue-play 两个 action 在 `runTrackAction`（:7433-7435）里都走 `addSelectedToQueue`（:4042），后者只提交队列、根本不判播放态。⇒ 本条原述的「用户点添加并播放被降级」在当前 UI 上不可达，R64 立它时那条入口还活着。下一轮动作 = 删三个死函数连同其中 `isPlayingNow()` 的用法，「本机加播还是投送加播」的口径并入 L69 的第②段，本条以证伪＋删死码结束，不另立新项。 〔R123 已实施：本条以「证伪 + 删死码」结束。实测删除 `addQueue`、`addQueueAndPlay`、`playFolder` 三个函数体（app.js numstat +49/-55，其中两处删除块 -32 与 -22），`runTrackAction` 的 action 判断由「queue 或 queue-play」收窄为只剩「queue」；收口后 `git grep` 全仓（含 `src/tests` 与 `android-client`）对这四个标识符 0 命中（命令退出码 1）。判别测试 `src/tests/test_ui_dead_queue_entry_points.js`，具名杀手「addQueueAndPlay must stay deleted (app.js)」；变异 V1 把函数加回后被它以非零退出码杀灭。残余口径「本机加播还是投送加播」并入 L69 的三段口径（投送即停本机、本机播放意图抢占投送、投送结束不自动续播），未另立新项。〕
- [x] 2026-09-18：R64 新开：`localPlaybackDuration()` 的前提「调用方已排除 remote」只写在注释与测试里，没有运行时防线。若将来有人在新站点直接调用它，remote 目标下会拿到条目时长而不是设备时长。考虑要么在函数内加一次显式断言，要么把 `seekDuration` 改成三条独立入口共用一个 switch（改动面较大，先立案）。  **R100 关闭（选第一条路：函数内显式断言）**：`isRemoteTarget()` 为真时 `localPlaybackDuration` 直接 `throw TypeError` ✓ 唯一调用点 `audio.ontimeupdate` 的入口提前排除保持原位 ✓ **incoming 投送会话按设计不在断言里**（投送改变传输行的显示归属 ✓ 不改变本地收尾决策的权威 ✓ 套件的场景 1/9/11 正是带 cast 驱动它的）✓ 这条口径是上一段中断用一次红付掉的：round152 的中间稿断言写宽（连 incoming 也挡）✓ 被场景 1 当场打回 ✓ 当场收窄 ✓ 判别性补在新测试 7b：直接调用的 `assert.throws` + cast 下直接调用不炸 ✓ 调用点的提前 return 会替断言挡掉一切间接路径 ✓ 不直接调就永远测不到它 ✓ 变异 M1-M4 全灭（控制组 69 个 JS 文件全绿先跑 ✓）。
- [x] 2026-09-18：R63 新开：`audio.ontimeupdate` 里的 cue 段收尾判断（`app.js:8064`）只挡了 `isRemoteTarget()`，没挡 incoming 受控会话，而 `currentSeconds()` 与 `seekDuration()` 在该状态下取的是渲染会话的数字。R63 夹住外推之后，触发窗口从「必然在 88 秒后满格」缩小到「真实位置已在结尾 10 秒内」，但组合仍然存在：需要决定本地 cue 曲目的收尾是否该完全忽略受控会话的位置（我倾向该忽略，收尾应由受控端自己的状态驱动），这属于行为决定，不当作纯技术清理顺手改。（R64 关闭：结论是「收尾判断该读本地权威」而不是「投送时整段忽略」——投送会改变显示归属，但本地 cue 曲目仍需在段尾自己前进；已抽出 `localPlaybackSeconds`/`localPlaybackDuration` 并把该判断改为本地对本地，「投送时跳过」这一改法作为变异 P3 由测试否决。MediaSession 与 `addQueueAndPlay` 两处经检查后保留共享口径，理由与后续立案见本轮记录。）
- [x] 2026-09-18：R63 新开：状态通道断开时界面上没有任何「状态未知」的表达，本轮只是让数字不再乱走。全仓 `src/app/ui` 里 grep `connectionLost|offline|degraded|lastSuccessAt` 命中为 0，也就是说 Web UI 完全没有「上一次成功是什么时候」的概念；要做就得连带定一个可见降级指示的口径（放在传输行还是顶栏、恢复条件是什么），不能只加一个内部标志。〔R122 负责人裁定 A＝最小可见降级指示，四个参数当场定死：判据阈值 10 秒（与 `TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS` 同值，复用不新设常数）、文案「状态未知」、位置在 `#elapsed` 之后（传输行内，不动顶栏）、状态来源复用现有 `rendererSnapshotAt` 与 `remoteSnapshotAt`（不新增连接标志位、不引入新计数器）；恢复条件＝任一投影成功刷新时间戳即撤销「状态未知」。同时就地纠正本条取证里的一处过头陈述：原文「grep `connectionLost|offline|degraded|lastSuccessAt` 命中为 0」在 `src/app/ui` 70 个文件上实测仍成立，但「界面上完全没有可用的反馈设施」不成立——`index.html:112` 存在一处 aria-live 等于 polite，归删除对话框内的 `#deleteTrackStatus`，不是全局状态区，所以裁定 A 的落点仍是传输行内的 `#elapsed`；toast 设施实测为 0（`showToast` 与 role 等于 status 均无命中），非阻塞反馈全仓只有 28 处 alert。实施留给下一轮。 〔R123 已实施：按裁定 A 的四个参数落地。阈值 10 秒＝直接复用 `app.js:4409` 的 `TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS`，未新设常数；文案「状态未知」写在 `index.html:70` 的静态标记里；位置在 `#elapsed` 之后、传输行内，未动顶栏；状态来源复用现有 `rendererSnapshotAt` 与 `remoteSnapshotAt`，未新增连接标志位、未引入新计数器。新增 `transportStateIsUnknown`（`app.js:4427`，判据）、`updateTransportStateUnknown`（:1917，唯一写点）、`setDatasetStateIfChanged`（:5344，带比较写入器）；接线三处＝`updateDeviceLabel`:1830、`syncPlayerProgress`:1912、`updateRemoteUi`:2117，最后这处必须在两条 early return 之前，否则时间戳冻结时灯会被自己的钳位藏住。可见性靠 `app.css:765-774` 的 ID 限定加 !important——`.progress>span` 与另两条 `.progress span` 规则会用 !important 吞掉行内任何非 ID 限定的 span，且 `#elapsed` 与 `#duration` 在任何宽度下都不可见，所以只能自建 span 且不能用 hidden 属性。判别测试 `src/tests/test_ui_transport_state_unknown.js`；变异 V2（接线挪到 early return 之后）、V3（阈值改 30）、V4（删比较守卫，写入计数 1→3）、V5（取反判据）、V6（ID 选择器换成 `.progress span`）、V9（删 `updateDeviceLabel` 接线）全部被具名杀手杀灭。〕
- [x] 2026-09-18：R62 关掉元数据关闭期把曲库索引留在打开状态的三条成因（`_claim_job` 在 `stop_event` 之后仍领新工作；join 预算不跟随在飞作业的 deadline；`close_library_connections()` 排在 `METADATA_SERVICE.shutdown()` 之前），并修掉中断现场遗留的「滑动预算」缺陷。新增/重写 4 条用例（claim 守卫、late-deadline、共享预算、`_active_job_ends_at` 边界），变异 5 项 M1 到 M5 全部在仓库外副本上命中；六次实测 `returned_clean=True` 且临时库可重命名。门限 `round68` 2144 全绿（skipped=2）。
- [x] 2026-09-18：R62 新开：join 循环里的三次 wake `.set()`（`metadata_service.py` `shutdown()` 内）没有被任何测试独立钉住。上一会话的复现表明「掉队 worker 停满一个 tick」这个场景在当前 lane 结构下不可达（被禁用的 lane 在 `_process_job` 之后 `continue` 而不 park），所以它现在只是廉价防御。要么构造一个真能让 worker 停在 `fetch_wake_event.wait()` 上的夹具把它变成被测契约，要么删掉这段三行重复、让「靠 0.25 秒切片自然轮询」成为唯一机制；不要留成「看起来有防御但没有测试」。  **R84 关闭（选「变成被测契约」，但纠正条目的两个前提）**：① park 的超时是 `wait(10)`（:2683）不是 join 的 0.25 s 切片——错过一次唤醒的代价是**十秒**级滞留、SQLite 句柄继续打开，所以这段防御比条目以为的更承重，删掉它不是选项。② 条目「不可达」的论证走的是被禁用 lane 在 `_process_job` 之后 `continue` 不 park 那条路；但 fetch lanes **共享**同一个 `fetch_wake_event`（:1898）且每个 lane 醒来后 `clear()`（:2684），而 R78 实测线程池是 4-5 个 worker，「兄弟先清、别人睡满一个 tick」在结构上是可达的。③ 没有构造真线程交错（那是抛硬币，会把门限变成 flaky 源），改为把契约本身钉住：只要还有 worker 活着，每一个 join 切片都重新 signal 三个事件——用计数代理加一个「醒三次就算排空」的假 worker，断言 `sets == 3 + 1`（循环前一次 + 每切片一次）。变异 U1 删掉循环内三行、U2 只留 fetch 一条，都被新测试指名杀死；U3 只交换三行顺序，按设计存活（三个互相独立的事件，先后无关）。旁证：U1 那一轮整套多花约 8 秒，正是「错过唤醒」的代价在测试里的样子。
- [x] 2026-09-18：R62 新开：补员线程重名。`fnaudio-metadata-fetch-recovery-%d` 的 index 取自 `range(replacement_count)`，每次补员都从 0 开始，多轮补员后 `threading.enumerate()` 里会出现同名线程，真机排查（以及本轮用到的栈抓取脚本）无法区分是哪一条。改成用实例级递增计数器，并把名字带上 lane 身份。  **R78 关闭（修复）**：`_start_lane` 的补员线程改用实例级单调计数 `_recovery_serial`（声明在 `metadata_service.py:1948`，递增与命名在 :2461-2464），连续补员不再产生同名线程。lane 身份本来就在名字字面量 `fetch-recovery` 里，没有再加第二份。判别测试`test_two_recovery_rounds_do_not_give_two_workers_the_same_name` 用「只记名字不起线程」的替身：第一版真起了线程，结果上一轮的活线程把临时库占住，`TemporaryDirectory` 清理直接 `WinError 32`。仓库外变异 M1（退回 `% index`）与 M2（每轮把计数重置）都被这条测试杀死。
- [x] 2026-09-18：R62 新开：drain 顺序不变式目前只对 metadata 成立。`cleanup_steps` 里 transcode、thumbnail prewarm、upnp cache background 都排在 `close_library_connections()` 之前，本轮没有逐一证明它们在该点之后不再持有任何曲库句柄。要做一次统一复审：给每个能读 `library.sqlite3` 的组件确认「stop 调用返回即不再产生新的 borrow」，并把整条顺序写成一条按名字断言的测试（现在的测试只覆盖 refresh/watcher/metadata/handles 四元）。  **R89 关闭（逐组件复审量出一个真洞并补上：drain 会被 HTTP 反手填回去）**：先按条目要求量谁真的能借句柄。全服务端只有 `library.py:1954 library_db_connect()` 打开 `library.sqlite3`，能走到它的曲库入口共 9 个（`query_library_page`、`load_items_from_sqlite`、`query_library_groups` 等，用 `inspect` 现算而不是猜）；而条目点名的三步（transcode 缓存、封面预热、UPnP 后台）连同 `playback/core`、mpd、airplay **一个都不调用**——`metadata_service.py` 只 import `find_ffprobe, id3_tag, library_db_path, read_cover, read_id3_cover`，逐个取函数体量，`library_db_connect` 与 `sqlite3.connect` 出现次数都是 0。所以那三步的次序是纵深防御而不是承重，真正还能借句柄的只有 HTTP 请求线程，而它偏偏不在这 13 步里：`server_close()` 排在整个清理循环**之后**（`server.py:3236-3239`），也从不 join 已在飞的 handler，「drain 之后没人再碰句柄」从来不成立。修法不动顺序，而是把最后一步换成一次性关闭：`LibraryConnectionPool.stop_accepting()`（`library_connection_pool.py:133`，:143 置标志并关掉手里的 idle）、`library.stop_library_connections()`（`library.py:1837`）、循环改用（`server.py:3229`）；`release()`（:104）在非接受态直接返回 False，调用方按契约就地关闭自己那个句柄（`library.py:2029-2031`），于是晚到的 reader 填不回去。`drop()` 保持可重开语义，因为 `_forget_library_schema`（`library.py:1852`）与测试在扫描间隙也要 drain。测试：13 步整条按名字钉住且最后一步必须是 drain；单一入口用 AST 扫全树并自检（扫描模块数 ≥60、`library.py` 内引用 ≥8）；四个无耦合组件单独钉；池层三条承诺分别断言（关掉的、拒绝的、记进 `closures` 的）；端到端 `test_stop_library_connections_survives_a_reader_that_finishes_afterwards`。变异两组：C3（把没有任何既有断言看过的 UPnP 步挪到 drain 之后）与 C4（drain 不再是最后一步）只有本轮新测试能杀，C5/C6 杀在 AST 两条上，D1/D3/D3b/D4（忘记置标志、release 照样收、少记一次 closures、循环仍用可重开的那个）各被指名杀死；C7/D5 是等价的字面改写，按设计存活。两条诚实边界：`shutdown_upnp_cache_background(wait=True)` 的 join 带 `timeout=3.0`（`dlna/control_point.py:548`），卡死的 socket 探测下「返回」不等于「线程已退出」；一次性关闭在进程内不可逆，所以 `test_server_lifecycle.py` 四处 `shutdown_runtime()` 都补了 patch，免得污染同进程的其它池测试。方法学：第一版的句柄扫描按文本数 `library_db_connect`，被自己写在池里的注释绊倒（控制组直接红），改成 AST 后注释与字符串都不再算引用；另一次是 `borrow()` 里的第二道检查被变异 D2 证明不可达（drain 已清空、release 是唯一入口），删掉而不是给它编一个测试。
- [x] 2026-09-18：R62 立案（本轮只读代码取证，未改）：状态轮询失败时传输位置外推无界。`refreshRendererSession` 在 `!response.ok`（`app.js:1972`）、请求换代早退（1971/1974）与 `catch` 吞异常（1984）三条路径上都不更新 `state.rendererSnapshotAt`，而 `currentSeconds()` 在 4385（incoming）与 4394（remote）按 `Date.now() - snapshotAt` 外推。时长已知时结果贴到 `duration` 停住（进度条卡在满格），时长未知（`duration <= 0`）时单调无界增长。R61 之后传输行每 1.5 秒重绘，这个既有缺陷从看不见变成看得见。改之前要定口径：陈旧超过多久就把外推冻结在最后一次的 position（而不是继续走字），以及要不要同时给一个「状态未知」的可见提示；先例是 `LIBRARY_PAGE_SNAPSHOT_TTL_MS` 与 `librarySnapshot.stale`。（R63 关闭：口径定为「夹住」而不是退回最后一次上报位置，上界按最慢健康快照来源的两倍推成 10 秒，收进单一入口 `transportExtrapolation`，另修掉同一条表达式上的负位置退化；「状态未知」的可见指示与真机取证各新开一条，见本轮 R63 条目。）
- [x] 2026-09-18：接管一个中断会话时的固定动作（R62 实践）：不要相信「文档停在第几轮」，要拿 `SOURCE_MANIFEST.sha256` 与工作树 mtime 对拍，找出上次门限之后被改过的文件，把它们当作**未验证**处理，先跑相关用例再决定是收尾还是回退。本轮据此发现一条从未与代码同时通过的测试（`StopIteration`），否则它会被当成「已完成只差记录」写进根文档。  **R110 关闭（落成工具而非口头流程）**：tools/takeover_forensics.py 把 SOURCE_MANIFEST.sha256 与工作树对拍成三态 drift/stale/unlisted ✓ 每条附「先跑哪几个 src/tests/test_*」✓ 退出码只在 stale 或非空 unlisted 时为 1；src/tests/test_takeover_forensics.py 10 条判别测试（夹具用 os.utime 控制时间戳 ✓ 含一条活库对拍当门禁）✓ 变异 V1..V8 全灭。完整取证见 CHANGELOG_AI.md 的 2026-09-19 R110 记录。
- [x] 2026-09-18：R61 关掉「投送期间进度条与播放图标不刷新」。`updateIncomingRendererUi()` 原先只被 `updateRemoteUi()` 调用，而驱动 `updateRemoteUi` 的 500 ms tick 以 `isRemoteTarget()` 为门；incoming 受控会话不是外放目标，于是 local/DAC 目标加投送的组合下传输行没有任何定时刷新（`#nowTime` 却因走 `syncPlayerProgress` 仍在动）。现在 1.5 秒状态轮询直接绘制传输行，调度器 500 ms 门同时认 `isIncomingRendererSession()`。同轮把 26 处传输行 `textContent` 直写收进既有的 `setTextContentIfChanged`，新增 `setStyleVarIfChanged` 接管 `--seek-fill`/`--marquee-distance`，`setPlayButton` 按 `dataset.playing` 去重。门限 round65（2141 全绿，JS `checks passed` 63 行）。
- [x] 2026-09-18：R61 新开：投送结束后传输行留着旧数字。`restoreLibraryNowPlaying()`（`app.js:1939`）只恢复标题/艺术家/封面，`#elapsed`、`#duration`、`#seek` 与 `#playBtn` 保留投送时的最后状态；若本地并没有播放，用户会看到「未选择曲目」配着投送曲目剩余的 1:40。要先定口径：本地无播放时这一行显示 `0:00 / 0:00` 还是当前列表曲目的时长，再在 `refreshRendererSession` 的 `previousActive && !active` 分支（`app.js:1981` 一带）一并复位，并清掉 `state.remoteUiLast`。 **R99 关闭**：现象与诊断成立 ✓ `restoreLibraryNowPlaying()` 原本只重写标题/艺术家/封面 ✓ `#elapsed` `#duration` `#seek` 与播放图标留着投送时的最后状态 ✓ 修法照这条点名的两处：新增 `resetTransportRow()`（复用停止路径 :2043 与新载入路径 :4375 已在用的同一写法 ✓ 再加 `updateSeekRail(0)` 让填充跟着归零 ✓ `setPlayButton(false)` ✓ 以及清掉 `state.remoteUiLast` ✓ 那份 memo 描述的正是刚结束的投送会话 ✓ 留着它 `updateRemoteUi` 会以为状态没变而跳过重绘 ✓）✓ **落点与条目建议的一处不同**： 条目建议放在 `refreshRendererSession` 的 `previousActive && !active` 分支 ✓ 实测量下来放在 `restoreLibraryNowPlaying()` 的 `!item` 分支更准 —— 那正是「界面已经回到曲库且本地没有曲目」的唯一时刻 ✓ 而 `previousActive && !active` 只在会话结束的那一 个 tick 触发 ✓ 之后任何一次重新进入曲库（例如投送仍在但用户切回本地视图）都不会再复位 ✓ 反例是机检的：变异 V2 把复位同时 加到 `else` 分支（本地有曲目时也清零 ✓）✓ 被专门写的 `doesNotMatch` 断言杀死 ✓ 所以「有本地曲目时不得清零」这一条也被钉住了 ✓ 关于 `#playBtn`：条目担心它留着投送状态 ✓ 取证到 `setPlayButton()` 已带 dataset 比较 ✓ 因此复位是幂等的（第二次调用不再改 DOM ✓ 由 `elapsed.writes` 与 `seek.styleWrites` 两条计数断言钉住 ✓）✓ 判别面：`resetTransportRow` 等 7 个函数从 app.js 源码抽出后在 vm 里真跑（假节点计数写入 ✓）✓ 断言 elapsed=0:00 ✓ duration=0:00 ✓ seek.value=0 ✓ `--seek-fill` 为 0% ✓ dataset.playing=paused ✓ remoteUiLast 为 null ✓ 二次调用零新写入 ✓ 另两条源码级接线断言：空选择分支必须调用它 ✓ else 分支不得调用 ✓ 变异 V1/V3/V4/V5 分别删调用、删 memo 清理、删进度条填充、删图标复位 ✓ 全部被杀 ✓
- [x] 2026-09-18：R61 新开：poll 路径每轮两次 `syncPlayerProgress()`。`updateIncomingRendererUi` 与 `updateNowMarquee` 各调一次，同值短路后基本免费，但结构上是重复。合并的前提是复核 `updateNowMarquee()` 其余 8 处调用点是否都隐含依赖它顺带刷新进度，属于可延后的小重构。  **R101 关闭（按条目要求先复核那 8 处调用点 ✓ 结论是「合并」这个前提本身不成立）**：`updateNowMarquee()` 尾部那次顺带绘制在 `mobile-search-active` 下整条早退 ✓ 所以它从来不是任何调用点可以依赖的契约。逐点读毕 8 处调用点与 1 处 resize 监听（`app.js`:900 换曲分支、1948 轮询、1981 恢复、4349/4373/4415 三条载入、7811 DAC 切换、8232 resize、8237 boot）✓ 传输行的绘制归属分别是 `updateIncomingRendererUi`(2125)、`updateRemoteUi`(2108)、原生状态泵(907)、`audio.ontimeupdate`(8165) 与 `onloadedmetadata`(8185) ✓ 没有一个需要 marquee 代劳。本轮删掉隐式那次 ✓ 在 restore/载入×3/DAC/boot 六个归属点各补显式一次 ✓ resize 保持纯几何。判别性：`test_ui_renderer_transport.js` 新增第二个 context 用真 `updateNowMarquee` 跑真绘制路径 ✓ `updateSeekRail` 作唯一可观测量 ✓ 一次轮询的 sync 计数 2 -> 1 ✓ 另有 4 条运行时断言 + 15 条源码级断言。仓库外副本变异 Q1~Q10 全灭（Q1 被「两次 -> 一次」的运行时计数杀掉 ✓ Q6 由既有 `--seek-fill` 断言先杀）。
- [x] 2026-09-18：R60 关掉播放条与歌词页封面的轮询重绘。`app.js` 新增 `setCoverArtwork`/`setNowPlayingCover` 去重入口，`#nowCover` 的 6 处与 `#lyricsCover` 的 2 处无条件 `innerHTML` 写入全部改为「同址 no-op」；`onerror` 从「删掉 `<img>`」改为「降级到占位字符」，因为在去重之后删除会留下永久空白框。`updateNowMarquee` 一并改成先测后写，每次调用少一次强制布局。门限 `artifacts/offline-20260918-round63.log` 2141 项全绿（skipped=2，127.570 秒），JS 套件 62 行持平。
- [x] 2026-09-18：R60 新开：now-playing 其余文本仍每轮询无条件重写。`renderIncomingRendererSession`/`restoreLibraryNowPlaying`/`loadCurrent` 对 `#nowTitle`、`#nowArtist` 的 `textContent` 赋值即使内容相同也会重写（文本重写不销毁图片，代价低一个量级，本轮未动）；`syncNowPlayingTime` 在 `timeupdate`（约 4 Hz）上无条件写文本、`updateSeekRail` 无条件写 `--seek-fill`，同值赋值是否真引发布局失效未经测量。要处理就把 `setCoverArtwork` 的「先比较再写」口径推广过去，或把整个 now-playing 块收敛成一个带签名的渲染函数；先取真机 trace，不凭猜测加去重。 **R99 关闭（已实现 + 机检守住）**：这条要求的口径已经在代码里了 ✓ 取证：app.js 共 79 处 `textContent =` 赋值 ✓ 其中写 `#nowTitle` `#nowArtist` `#nowTime` `#elapsed` `#duration` 的**直接赋值 0 处** ✓ 全部走 `setTextContentIfChanged()`（:5315 ✓ 实现就是 `if (node.textContent !== text)` 再写 ✓）✓ 这条点名的另外两处也在：`syncNowPlayingTime` 用带比较的写入器（:1893 ✓）✓ `updateSeekRail` 用 `setStyleVarIfChanged`（:1902 ✓ 且全文只有这一处出现 `--seek-fill` 字面量 ✓）✓ 所以「先取真机 trace 再决定要不要加去重」的前提已经不成立 —— 去重不是本轮猜着加的 ✓ 它先于本轮存在 ✓ 本轮做的是把它**钉住**：新增 5 条 doesNotMatch （这五个节点不得出现直接 textContent 赋值 ✓）+ 一条「比较必须留在helper里」的结构断言 + 一条 `--seek-fill` 只允许出现一次的 计数断言 ✓ 变异 V6（把复位改成直接写文本 ✓）V7（把 helper 的比较去掉 ✓）V8（让进度条绕过 helper 直接 setProperty ✓）三例全被杀 ✓ 仍未知的部分写在这里不另立项：**这些去重在真实 WebView 上到底省没省布局失效仍未测**（本轮的断言只保证「相同内容不再写 DOM」✓ 不主张性能收益 ✓ 条目原文要的 trace 依然没有 ✓ 因此这一条不得被理解成性能结论 ✓）✓
- [x] 2026-09-18：R60 补上收尾自查纪律：每轮结束前对着本轮关闭的问题回查 `TODO.md`，确认没有别的 `[ ]` 条目还在替它活着（本轮就是靠这次清点补销了 R57 为 R58 开的那条）。R62 补销：这条口径已经作为规则写进 `PROJECT_CONTEXT.md` 顶部（「关闭问题时要销掉为它开过的所有条目」），本轮接管时正是按它抓到 R59 之后仍挂着的陈旧条目，以及一份晚于上次门限、从未被验证过的工作树改动，故不再作为待办挂着。
- [ ] 2026-09-18：R59 把「还没审计的部分」量化成可排期的清单（替换 2026-09-17 那条只列文件名的范围条目）。离线可验证面总数与命名覆盖：`src/app/server` 的 .py 191 个文件 / 33,648 行，`src/app/ui` 的 .js 59 个文件 / 11,500 行（不含 `vendor`），合计 250 个文件 / 45,148 行，**本轮补记之后三份根记录已经点名到全部 250 个文件**（清点脚本 `%TEMP%/p722.py`，口径是叶子名在三份文档全文里出现）。剩下的是**深读**而非**未登记**：显式欠读清单 6,125 行 = `dlna/service.py` 957 + `app.css` 1,518 + `cover_cache.py` 1,021（R59 只重读了预热与资产两段）+ `dlna/control_point.py` 620 + `playback/core.py` 468 + `dlna/renderer.py` 442 + `state_store.py` 363 + `alsa_player.py` 178（且它本身还是无人调用的孤儿入口）+ `state_projection.py` 231 + `fnos_api.py` 143 + `index.html` 184。另外 `src/app/ui/app.js` 8,096 行只做了分段审计（渲染、封面、队列、中止、槽位、快照复用），正在播行的封面与进度簇仍属欠读；`tools/*.ps1` 9 个脚本本轮点名核对为 0 缺项。按今晚实测节奏（R52 到 R59 共 8 轮、4 小时 42 分，约 35 分钟一轮，含每轮 128 秒上下的离线门限）推算，上述欠读面大致还需要 15 到 20 轮，也就是**两到三个等价工作日**，而不是墙钟意义上的连续天数；真机项与在线 provider 不计入。〔R129 磁盘对账：本清单**已过期**，照它排期会追两个已经不存在的面，故只登记对账、**不据此关闭**。逐项按磁盘真值：① `fnos_api.py`（本条记 143 行）**已不在源码树**——R118 退役了整组恒假 fnOS 路由，现存双向守卫 `src/tests/test_fnos_route_retirement.py`（其 docstring 明写 `fnos_api` 与 `call_trim_api` 当时在文件内已无其他使用者），仓库里只剩 `src/app/server/__pycache__/fnos_api.cpython-312.pyc` 与 `cpython-314.pyc` 两份未跟踪字节码残迹，不是源码面；② `alsa_player.py`（本条记 178 行）已由 R119 连同 `playback_session_contract.py` 逐字节移入 `src/tests/unwired/`（现 178 内容行，与本条登记值逐字相同，恰好印证「逐字节移入」），守卫 `src/tests/test_orphan_module_retirement.py`，其中 `test_the_manifest_hashes_the_new_paths_and_drops_the_old_ones` 直接把新旧路径钉进 SOURCE_MANIFEST；③ 仍在树上的九个面按全库统一的内容行口径实测（`len(text.split(chr(10)))-1`，与本文件自称的 2,217 行同一口径），九面合计 6,655 行，其中六面与本条登记值不符、三面逐字相符：`dlna/service.py` 1,220（登记 957）、`dlna/control_point.py` 699（620）、`dlna/renderer.py` 442（登记 442，逐字相符）、`cover_cache.py` 1,364（1,021）、`playback/core.py` 506（468）、`state_store.py` 481（363）、`state_projection.py` 231（登记 231，逐字相符）、`index.html` 184（登记 184，逐字相符）、`app.css` 1,528（1,518），九面合计 **6,655 行**（不含 `app.js` 的 8,362 行，本条记 8,096）。本条顶部的「191 文件 / 33,648 行 + 59 文件 / 11,500 行 = 250 文件 / 45,148 行」与「欠读 6,125 行」按现树均已不可复现。⚠ 关闭条件不变：R120 已判定 `state_store.py`/`cover_cache.py`/`dlna/service.py` 三面读过、上述两枚出局，剩余欠读面仍需逐轮真读，读完才可关闭。〕〔R130 并入：原 2026-09-17 那条只列文件名的范围条目（关闭前在盘上为 L551）本轮勾选关闭，其独有内容全部并入本条，本条从此是代码桶里唯一存续的欠读范围清单。**新增欠读面（Android，四者均在树内、离线可深读，运行态验收另在设备段）**：`android-client/app/src/main/java/com/fnaudio/client/playback/RemotePlaybackPlayer.java`（370 行）、`.../playback/PlaybackService.java`（1,398 行）、`.../playback/AuthenticatedBitmapLoader.java`（410 行）、`.../network/FnConnectRelayConfigClient.java`（258 行），合计 2,436 行；**新增欠读角度（同样只来自那条范围条目）**：`state_store.py`/`state_projection.py` 的**并发写**、`cover_cache.py` 的**剩余循环**、原 `fnos_api.py`/`alsa_player.py` 的**常驻循环**（后两面已分别由 R118 退役、R119 移入 `src/tests/unwired/`，角度随面一起出局，只在各自守卫里留痕）；并保留其告诫：**不得以离线门禁宣称全仓库无问题**，真机与在线 provider 仍受 Gradle loopback/Unix socket 阻塞。〕〔R134 深读 `state_projection.py`（231 内容行，与本条 R129 登记值逐字相符）：全模块 14 个导出逐函数读完，判定无正确性/安全缺陷，本面自此由「欠读」转为「已读」。事实依据：该模块是**纯无状态投影** —— 每个函数都是入参→新建返回值，模块级名字只有 6 个有界常量（`MAX_STATE_PAYLOAD_BYTES` 2 MiB、`MAX_STATE_TEXT_BYTES` 4096、`MAX_PLAYBACK_QUEUE_TRACKS` 50000、`MAX_PLAYLISTS` 1000、`MAX_PLAYLIST_TRACK_IDS` 10000、`MAX_PLAYLIST_TRACK_IDS_TOTAL` 50000），不写文件、不落库、不持有跨调用可变对象。**由此据实更正本条 R130 的登记**：那条把「并发写」角度同时挂在 `state_store.py` 与 `state_projection.py` 两个面上，其中对 `state_projection.py` 不成立 —— 没有共享可变状态就没有可查的写并发，该角度自本轮起只保留在 `state_store.py` 一处。逐函数复核通过的边界：`_bounded_state_text`（非 str→""、strip 后 utf-8 超 4096→""、宽 `Exception`→""）、`load_json_bounded`（非 str→{}、超 2 MiB→{}、只捕 TypeError/ValueError/UnicodeError/RecursionError）、`dump_json_bounded` 与 `dump_json_bounded_strict` 的分工（后者 raise 且 `allow_nan=False`，防 NaN/Infinity 泄进 SQLite 载荷）、`mapping_or_empty` 形状守卫、`strings`/`playback_queue_ids`（逐取迭代器 + 去重 + 上限，坏元素 break 而非抛）、`playlists`（`track_limit = min(MAX_PLAYLIST_TRACK_IDS, remaining_track_ids)` 使全表预算不会转负）、`ui_preferences`（`isinstance(width, bool)` 先于 int 分支排除 True/False、float 需 `isfinite()` 且 `is_integer()`、str 需 `isascii()` 且 `isdecimal()`、取值域 `64 <= value <= 900`）。唯一可挑处是风格 nit：L61 `raise ValueError(...) from exc` 与 L62 `def strings(...)` 之间缺 PEP 8 期望的空行 —— 非缺陷，**不改**（为一个空行刷 `SOURCE_MANIFEST.sha256` 换不到任何正确性收益）。**本轮净关闭 0 条**：本条关路口径仍是「剩余欠读面全部读完」，读完才可勾。〕〔R138 X12=A 数字重算：**只改本条数字，不改关闭判据**（判据仍是「剩余欠读面全部读完」）。按 2026-09-21 磁盘真值，欠读清单为 `cover_cache.py` 1,364 ＋ `playback/core.py` 506 ＋ `app.css` 1,528 ＋ `index.html` 184 ＋ `app.js` 8,362（分段审计中）＋ **Android 全部已跟踪 `.java` 43 个文件 / 9,695 行**（X12 明确把 Android 纳入本条范围：其中 `src/main` ＋ `src/mediaSession` 27 文件 / 8,165 行是生产面，`androidTest`/`test` 16 文件 / 1,530 行是测试面）＝ **21,639 行**。离线全库面同步复算为 `src/app/server` 的 .py **189 文件 / 35,323 行**（比本条顶部 R59 登记的 191 文件少 2：`fnos_api.py` 已随 R118 退役、`alsa_player.py` 已随 R119 移入 `src/tests/unwired/`；行数由 33,648 增至 35,323 是 R118 之后源码净增的结果）＋ `src/app/ui` 的 .js（不含 vendor）**59 文件 / 11,833 行**。已读出局累计：`dlna/service.py` 1,220（R137）、`dlna/control_point.py` 699（R136）、`dlna/renderer.py` 442 与 `state_store.py` 481（R135）、`state_projection.py` 231（R134）。R130 点名的四个 Android 面是本条 43 文件集合的子集，随本次并入统一按文件排期。〕〔R140 深读并修复：`index.html` 184 行逐行读完，本面**已读出局**。结构面取证（修复前）：144 个 id 全唯一（本轮给三枚 `<strong>` 补 id 后 147 个仍全唯一）、`<script src>` 59 条全存在且无重复、无 inline script、无 inline `on*=`、ui 下 59 个 .js 全部被加载（无死资产、无幽灵引用）、样式表 1 张、`<form>` 0、`label for` 0、8 个 `<dialog>` 各有 showModal 调用点（app.js 全局 `.showModal(` 10 次、`.close()` 18 次，其中 `deleteTrackDialog` 的关闭走 `closeDeleteTrackDialog()` 而非字面同函数配对）、`data-settings-tab` 与 `data-settings-pane` 四桶对称、11 个 `data-view` app.js 全处理。**证伪 1 项**（勿记作发现）：`#nowPlayingSummary` 键盘可达性——app.js L8165-8169 已绑 `onkeydown` 处理 Enter/Space 且 `preventDefault`，它也是全文唯一的 `tabindex="0"`。**真实缺陷 1 类已当轮修掉**：79 个可见控件里 5 个无任何可用辅助名（`#seek`、`#volume`、`#shareExpiryEnabled`、`#sharePasswordEnabled`、`#shareAccessEnabled`），三枚开关的包裹 `<label class="switch-control">` 内唯一子元素是空 `<span></span>`，而 CSS `.switch-control input{position:absolute;opacity:0;pointer-events:none}` 已把真实控件隐去，所以既无可视文字也无可读名。修法只补名不改视觉：两个 range 走 `aria-label`，三枚开关走 `aria-labelledby` 指向本行可见 `<strong>`（给其补 id），效果是 5 行上 8 个属性；新增判别测试 `src/tests/test_ui_control_names.js`，变异 V1～V9 全灭见 CHANGELOG R140 条。**数字漂移（按现树重算，不改关闭判据）**：`src/app/server` .py **189 文件 / 35,479 行**（本条 R138 登记 35,323，+156）、`src/app/ui` .js 不含 vendor **59 文件 / 11,866 行**（登记 11,833，+33）、`app.js` **8,395**（登记 8,362，+33）；`app.css` 1,528、`cover_cache.py` 1,364、`playback/core.py` 506、已跟踪 Android `.java` 43 文件 / 9,695 行均与登记逐字相符。于是欠读总量由 R138 登记的 21,639 行修正为现树 **21,672 行**，再去掉本轮出局的 `index.html` 184 行⇒ **21,488 行**（= `cover_cache.py` 1,364 + `playback/core.py` 506 + `app.css` 1,528 + `app.js` 8,395 + Android `.java` 9,695）。**本轮净关闭 0 条、新立 0 条**：关闭判据不变，仍是「剩余欠读面全部读完」；按 Q2=A 的「欠读行数计进展」口径，本轮推进 184 行。另：本轮正式门禁日志红于 `src/tests/test_library_sqlite.py` 的一处既有搜索用例（ASCII 短词 `hi` 与随机临时目录名相撞；按 `tempfile` 随机名实测 200,000 次有 984 次含 `hi`，约 1/203），当轮换非 ASCII 搜索词并加 `assertNotIn` 守卫修掉，属测试夹具卫生，**不新增待办、不改变本条判据**，净关闭仍 0、新立仍 0。〕
- [x] 2026-09-18：R59 补记立案：`src/app/server/playback_session_contract.py`（139 行）与 `src/app/server/alsa_player.py`（179 行）都没有生产消费者，只有各自的测试在跑。删除或接线之前必须先取证 fpk 打包与设备侧脚本是否按文件名调用它们（`alsa_player.py` 有 shebang 与 CLI，形似被外部拉起；`playback_session_contract.py` 与被使用的 `playback_session_policy.py` 名字极易混淆）。取证后三选一：接回真实调用点、移出发包目录、或删除并连带清理测试；不要凭印象动手。  **R119 关闭（取条目第二路：移出发包目录，逐字节不变）**：先做条目点名的取证——`alsa_player` 与 `playback_session_contract` 两个词在 400 个生产文件的引用语料（`src/app` 全部 + `src/cmd/main` + `src/wizard` + `src/config` + `src/manifest` + `tools` 一层的 .py/.ps1/.sh + `android-client/app/src/main`，排除 `test_*`、`vendor`、`build`、`.gradle`、`runtime`、`apk-analysis`、>3 MB 二进制）里按文件名 0 命中；`git grep alsa_player HEAD` 只命中三份根文档，`playback_session_contract` 在提交态根本不存在；`tools/build_release.ps1` 只递归暂存 `src` 并只断言八个具名 payload 文件，两个名字都不在其中 ✓ **第一路（接回真实调用点）被取证否掉**：同一个总闸扫描在移动前对 `src/app` 下 192 个 .py 只报这 2 个孤儿，也就是说它们从来没被任何调用点接出过，接回去等于凭空新造功能 ✓ **第三路（删除）被两条不可恢复性否掉**：`alsa_player.py` 工作树带未提交改动（HEAD 版 95 行、现在 178 行，`git checkout` 会直接丢掉这 83 行净增长），`playback_session_contract.py` 是未跟踪文件且正是 TODO「Android 等价 MediaSession 持续目标」6 条设备项所等的契约资产 ✓ **于是按第二路整体移入 `src/tests/unwired/`**，sha256 逐字节不变（alsa `AA035E4B1463A1D84725E2EE9B0F65C26677DF6050139A2062942A61CE7F4917`、contract `3E5D3557FA496305451AB9FC55893A8CDD858CD829263200DB4D0A559BD581D5`，与移动前的仓库外备份 `%TEMP%\r119_backup` 逐字节相等）✓ 该目录被 `build_release.ps1:214` 的 `robocopy /E /XD tests __pycache__` 按目录名挡在 payload 外，`build_release.ps1:394-395` 的 payload 拒 `tests` 守卫一字未改，同时仍在 `tools/update_source_manifest.ps1` 覆盖集内，逐文件 sha 审查没丢 ✓ 两支测试改指新路径且用例数不变（`test_alsa_player.py` 10 项、`test_playback_session_contract.py` 7 项）✓ 新增判别测试 `src/tests/test_orphan_module_retirement.py` 10 项（总闸「`src/app` 树里再无零消费者模块」+ 两模块离开发包树 + 手工 CLI 形状仍在 + 契约可载入 + 两支测试跟随 + `/XD` 与 payload 守卫在位 + 无打包/设备脚本点名 + `playback_session_policy`/`_projection` 未被动到 + 清单列新不列旧）；变异 M1～M10 全灭见 CHANGELOG R119 条 ✓ 本轮新立可离线代码项 0 条 ⇒ 代码桶 26 → 25、开放项 90 → 89 ✓ 同一对文件在 L83 的欠读清单里仍列着 `alsa_player.py` 178 行与已删的 `fnos_api.py` 143 行，L541 也仍点名 `alsa_player.py`，属历史快照，按「历史行不改写」保留且保留其文本锚点。
- [x] 2026-09-18：R59 补记：`if False and` 恒假路由块共 7 处（`server.py:1035/1450/1480`、`cgi_proxy.py:605/611/615/639`），全部围绕飞牛授权目录（shared-folders 与 auth-debug）。它们让 `/api/fnos/*` 走进后续通用分支，读代码的人会误判这些端点可用。需要一次决定：要么把这组功能正式关掉（删块 + 删只被它引用的 `fnos_api.py` 入口与 `test_app_lifecycle_*` 里的相应断言），要么用配置开关代替恒假字面量。本轮未改。  **R118 关闭（取条目第一路：正式关掉＝删块 + 删只被它引用的入口；第二路取证为不可行）**：可行性取证——旧 server.py L132 是 `from fnos_api import FnosApiError, call_trim_api`，块内调用的 `get_shared_accessible_folders`/`del_shared_accessible_folder` 全文命中只在 L1042/1456/1492（三处全在死块里），`call_trim_api` 除导入行外零命中：把恒假字面量换成配置开关，开关置真就是 NameError→500，等于把「读代码的人会误判端点可用」换成「运行时会崩」，所以本轮删。删除量按本轮磁盘前后差实测（行数用 splitlines 口径，行尾无额外空行）：server.py 3390 → 3327（−63＝GET 块 9 + POST 两块 51 行中的 51 与 9 之和按块计为 60，另加死导入行 1 与导入组内 2 个名字）；cgi_proxy.py 727 → 509（−218＝`import socket` 1 + 孤儿常量 4 + `json_object_or_empty`/`response_code` 17 + 四个死函数 143 + 四个 fnos 路由块 53）；src/tests/test_cgi_proxy_auth.py 626 → 477（−149＝8 个只测死函数的测试，40 → 32 项；四支 service_port 测试与三条真活跃前缀测试原地保留）；tools/ui_e2e_fixture.py 322 → 320（−2＝fnos 假分支，`/api/` 兜底仍在）。整文件删除 `src/app/server/fnos_api.py`（143 行）与 `src/tests/test_fnos_api.py`（98 行 / 9 项）；`test_fnos_api.py` 原本未跟踪、删了无法从 git 恢复，故两份备份移到仓库外 `C:\path\to\fnAudio_r118_deleted_backup`（仓库外路径不进 SOURCE_MANIFEST，也不进门禁覆盖集）。删后取证：`if False and` 0 命中（HEAD 版本里两文件共 7 处：server.py 3 + cgi_proxy.py 4，与条目计数一致）、`/api/fnos` 与 `auth-debug` 在 src/tools 的 .py 里 0 命中，`fnos` 只剩 server.py L754/755/1573/1668 四处合法注释与 cgi_proxy L74/L331/L399 三处（L331 是 `"fnos-token"` cookie 名，L74 与 L399 是注释）。**诚实记录出入**：条目点名的「`test_app_lifecycle_*` 里的相应断言」磁盘上不存在——`src/tests/test_app_lifecycle_scripts.py` 全文 23 项，唯一含 fnOS 的是 `test_install_and_upgrade_restore_standard_fnos_target_link`（安装目标软链，与授权目录无关），该半句要求是空集，本轮不宣称删了不存在的东西。判别测试两层：新增 `src/tests/test_fnos_route_retirement.py` 10 项，源扫描 + AST 双向设计——一半拦死代码复活（`if False and` 字面量与 AST 常量假条件、端点字符串、六个死函数名、四个孤儿常量、入口文件与其测试的存在、`fnos_api` 与两个被删导入名），一半拦「删过头」（活链在位：`trim_token`/`normalize_trim_token`/`MAX_TRIM_TOKEN_CHARS`/`service_port`/`local_service_ready`/`wait_for_service`/`write_service_unavailable`/`main`/`fnos-token`，以及 `/api/health`、`/api/config/library`、`/api/playback/targets`、`serve_static` 与 fixture 的 `/api/` 前缀兜底），另把「扫描排除集只允许这个文件自己」和 manifest 覆盖集变化钉成断言；`src/tests/test_http_integration.py` 加 2 项真服务器行为钉（GET `/api/fnos/shared-folders`、`/api/fnos/auth-debug`、`/api/fnos/shared-folders/nested` 全部 404；两条 POST 落 handle_post 尾部 `{"error": "not found"}` 404 且 `commit_config_update` 零调用），文件 1468 → 1498 行、模块 78 → 80 项。仓库外副本 `E:/fnAudio_r118_cp` 控制组先绿（Python Ran 2392 OK skipped=3、69 支 `test_*.js` 逐个 node 退出码全 0），V1～V9 九条变异全灭且逐条命中指名杀手：V1 以活条件复活 GET 路由（源扫描与 404 行为钉同时杀）、V2 复活 `from fnos_api import`、V3/V4 复活 `trim_request`/`response_code`、V7 复活 `MAX_MERGED_LIBRARY_PATHS`、V8 复活 fixture 的 fnos 分支、V9 复活恒假字面量；反向 V5 删活函数 `trim_token`（正向断言 + 7 支既有 cgi 测试杀）、V6 删 `src/cmd/main` 的 `TRIM_API_TOKEN` 转发（`test_main_starts_server_without_second_shell_parsing` 杀）。本轮新立可离线代码项 0 条 ⇒ 代码桶 28 → 27。
- [x] 2026-09-18：R59 补记完成「从未被记录」清点：10 个生产文件（381 行）逐个读毕并登记（服务端 5 个策略模块、UI 4 个策略模块、1 个第三方压缩产物），判定无缺陷需要修；同时量化 `item_negative_cache.has()` 的每次调用全表裁剪成本（满表 2048 条时约 14.4 微秒/次，120 个 id 的预取批次约 2.4 毫秒）后决定不改，只留数字与触发条件。清点脚本口径：`git status -uall -- src` 并 `git ls-files -- src`，排除 `src/tests/`，按叶子名在三份根文档全文查提及。
- [x] 2026-09-18：R59 关掉「metadata 封面缺缩略图通道」（即 2026-09-17 立案的 R51 条目）。`cover_cache.generate_asset_thumbnail` + `serve_metadata_artwork` 读 `?size=`：先按内容地址查共享缩略图存储，未命中才在锁内读原图、**校验 `sha256(body)` 等于地址**、ffmpeg 渲染、原子落盘、进内存；metadata 的 asset_id 本就是字节 sha256，与 `covers/assets/thumb-<size>/` 同一套内容寻址，所以 provider 封面与内嵌封面共用一份渲染。渲染失败/超时/无 ffmpeg/摘要不符一律整段回退原流式路径，且 ETag 留在不带尺寸的 `"metadata-<id>"`。键侧新增 `_normalized_asset_key`（非字符串、>128、非 64 位十六进制全拒）与含尺寸的内存/锁键。验证：cover_cache 6 项 + http_integration 2 项，变异 9 尝试 8 有效、7 当场杀、M6 补测杀；门限 round61 2141 全绿。原条目里三项真机证据现在落了一项：ffmpeg 缺失与槽位超时的回退行为已由代码与测试确定；仍未量的是「一页有多少行走这条通道」与「低端 WebView 解码大图的真实代价」，已另开待办。
- [x] 2026-09-18：R59 新开：`covers/assets` 存储没有聚合上限。单张缩略图受 `MAX_CACHED_COVER_BYTES` 约束、目录按 size 分片，但**总条目数与总字节无人看管**：每个见过的新封面都会留一张 160 与一张 512，长期运行只会单调增长。R59 让这条通道的写入量变大（provider 原图第一次也被渲染进这个存储），所以先量化当前占用，再按 `metadata_service._prune_artwork_cache` 的既有先例做按 mtime 收敛的清理（含磁盘低水位触发），并且清理不得与 `_key_lock` 的在飞渲染互相踩。（R75 管住了总字节、过期项与不可达项；**总条目数仍未封顶**，本轮已单独立项。`_key_lock` 在飞渲染的保护由「先写资产后写别名 + 一小时宽限期」承担。）  **R118 证伪式关闭（关的是重复登记，不是已完成）**：条目末段自己写着「R75 管住了总字节、过期项与不可达项；**总条目数仍未封顶**，本轮已单独立项」，那次「单独立项」就是 L32（R75 新开：`covers/` 封顶了字节与过期项、没封顶条目数；5000 张独有封面 ≈ 260 MB 远不到 512 MiB 默认预算所以第三层根本不触发；要加 `cover_cache_max_entries` 得先有真实库的文件数分布）。本轮把条目的四项要求拆开逐条对盘：①总字节——`cover_cache.py` L734 `cover_cache_max_bytes`（默认 512 MiB）✓②过期/不可达回收与④`_key_lock` 在飞渲染保护——`test_cover_cache.py` L1485 过期负标记回收、L1498 崩溃遗留 temp 过 TTL 回收、L1518「等别名的资产不算孤儿」、L1525「有资产字节无别名过宽限期才回收」（宽限期 `cover_cache.py` L570 `COVER_ASSET_ORPHAN_GRACE_SECONDS = 3600.0`、判定 L731 先资产后别名）、L1546 字节预算只淘汰最旧单元、L1575 磁盘压力早于预算也清理 ✓ ③总条目数**仍未封顶**，继续由 L32 承担，L32「先量真实库文件数分布再定数」一行未动 ⇒ 本条与 L32 是同一件事的两处登记，本轮消掉重复登记，未完成要求总数不减、也不需要新立条目，L32 保持开放。代码桶 27 → 26。
- [x] 2026-09-18：R58 关掉首屏文件夹搜索的挂起。`library.py` 的 `query_library_folders` 不再逐目录向 `tracks` 问「你的子树里有没有命中」，改为一次 `WITH RECURSIVE matched_folder_paths` 把命中曲目沿 folders 的 parent 链折成祖先闭包，目录侧退化成等值索引探测；同时去掉路径 LIKE（`_`/`%` 曾被当通配符，会替别的目录认领命中）。实测顶层目录 1000/4000/16000：136.6/2171.3/64607.1 ms 变为 5.97/20.40/87.64 ms，且不命中时从 4989 ms 降到约 1 ms。新增 6 项用例（三层父链、多根隔离、LIKE 模式绑定、游标+搜索、通配符目录名、计划断言），变异 10 尝试 8 捕获，2 项等价存活。
- [x] 2026-09-18：R58 遗留：向上闭包依赖 folders 父链完整。递归项靠 `folders f2 JOIN matched_folder_paths m ON f2.root = m.root AND f2.path = m.path` 取父目录，所以某个命中目录若在 folders 表里没有行（增量重建落后于曲目），它的祖先层就不会出现在搜索结果里，而旧写法仍会把它祖先列出来。方向：先取证「曲目已入库而目录行缺失」在真实扫描里能否出现（`_rebuild_folders_for_changes` 按受影响的第一层目录整树重建，理论上不应出现），若不能出现就把这条不变式写成断言或注释钉在 `library.py`，若能出现就改成不依赖目录表的字符串前缀闭包。  **R110 关闭（取证：不能出现 ⇒ 按条目第一方案把不变式钉死）**：写入侧 save_items_to_sqlite 的三条 affected_folder_roots INSERT 覆盖增/改/删 ✓ _rebuild_folders_for_changes 对每个受影响项整树重建（同一 top/% 前缀先删后重选再补全祖先）✓ 探针七种序列 missing/dangling/track_count/多余行全 0；新增三条判别测试与两处注释钉（library.py 1576-1582 与 2739-2747）；变异 M1..M6 全被新测试杀死 ✓ M6 只有新守卫测试能杀；未改成字符串前缀闭包。完整取证与门禁见 CHANGELOG_AI.md 与 PROJECT_CONTEXT.md 的 2026-09-19 R110 记录。
- [x] 2026-09-18：R58 遗留：`tools/benchmark_large_library.py` 的 folder 形状仍不足以守住搜索通道。基准里顶层目录只有 80 个（`Collection %03d/Disc %02d`），而 R57/R58 两类问题都是「单个目录内兄弟数」驱动的：R57 靠 R58 之前补的 `browse.folder_pages` 计划断言已可机检，搜索页目前只有单元测试的计划断言，基准里没有。要补的是宽顶层目录夹具（数万兄弟）加上一次搜索页计划断言，配方与耗时基准见本轮 CHANGELOG，注意夹具要直接 `executemany` 造 `folders` 行。  **R97 关闭**：这条要的是「宽顶层目录夹具（数万兄弟）+ 一次搜索页计划断言 ✓ 夹具要直接 `executemany` 造 `folders` 行」✓ 前半照做了但**没有**用 `executemany` ✓ 原因是取证出来的：文件夹搜索页在 `library.py:1566-1588` 走的是「先把命中曲目折成递归 CTE ✓ 再对每个目录行做 EXISTS」✓ 所以一个不含任何曲目的合成目录**永远不会出现在搜索结果里** ✓ 直接造行会得到一个恒空的夹具 ✓ 改成让四分之一的曲目各自落在同一个父目录下的独立叶子目录（`Wide/Sibling %06d` ✓ 由 `_rebuild_folders` 自然派生 ✓ 不新增曲目行 ✓ 基准耗时不变 ✓）✓ 兄弟数 625（2.5k ✓ 测试用）/ 5000（20k ✓）/ 25000（100k 默认 ✓）✓ 满足「数万兄弟」✓ 成本确实变得可测：20k 曲目下搜索页 7.39 ms 对同一基准里的纯目录页 2.20 ms ✓ 约 3.4 倍 ✓ 而 2500 兄弟以下时（625 兄弟 ✓ 4.52 ms ✓）差异被曲目规模主导（兄弟 8 倍 ✓ 耗时 1.6 倍 ✓ 正是 R58 折算承诺的「代价按曲目一次 ✓ 不按兄弟逐个 ✓」✓）✓ 硬守卫落在基准自己身上（计划里必须有 `idx_folders_root_parent_name_nocase_asc` 且无 `TEMP B-TREE` ✓ 否则 RuntimeError ✓ 与 :531 既有风格一致 ✓）✓ 并另有一条 R95 的**无根**窄索引不被误用（这条通路透传 root ✓ 所以必须用带根那对 ✓ 变异 Y5 把守卫写成错名索引 ✓ 直接被杀 ✓）✓ 一个坑记在案：分流后如果继续用 `index % 80` 造深层目录 ✓ 同余会塌掉（凡 index%4==0 的值全部被分流 ✓ 顶层只剩 60 个而不是 80 个 ✓）✓ 深层计数改成先压缩再取模（`slot = index // WIDE_FOLDER_SHARE` ✓）✓ 变异 Y3 就是没压缩那版 ✓ 被顶层目录计数杀死 ✓ 另：这条原本建议的 `executemany` 造行方案我证伪了 ✓ 结论就写在这里 ✓ 没有另立新项 ✓
- [x] 2026-09-18：R57 关掉首屏文件夹浏览的全目录排序。`library.py`：folders 表新增 `(root, parent, name COLLATE NOCASE ASC/DESC, path)` 按方向表达式索引、删除从未命中的 `(root, parent, name)` 二元索引、保留 `(root, parent)` 覆盖计数索引；`query_library_folders` 的无过滤页改走 `counted_page_rows`，搜索页保留窗口。端到端 5000/20000/50000 顶层目录 4.18/22.48/71.10 ms 变为 0.87/1.28/5.91 ms，计划里不再有 `USE TEMP B-TREE FOR ORDER BY`。同时更正两条旧归因（分组页 `COUNT(*)` 实为 0.01 ms、旧的 4 ms 是未池化连接前奏；「folder 窗口比 page+count 便宜」只在无排序索引时成立），并把孤儿索引清理扩到全部 `idx_folders*`。
- [x] 2026-09-18：R58 优先：修文件夹搜索通道的二次方放大。`query_library_folders` 的搜索条件是逐目录关联 `EXISTS`，计划显示每判一个目录就按 `idx_tracks_root_folder (root=?)` 重扫整根曲目，实测 1000/4000/16000 个顶层目录 = 137 ms / 2171 ms / 64.6 s（FTS5 已建、命中率为 1 的最坏形状）。可接受的形状是「先把命中曲目折叠成目录集合，再按该集合过滤 folders 表」（一次遍历 + 祖先闭包），而不是每行一次子查询。约束：不得破坏 `test_folder_search_keeps_root_and_child_hierarchy` 的「子目录命中要显示父目录」语义、`root` 必须继续参与限定（多根同名相对路径不能互相命中）、总数与分页语义保持当前窗口口径。改完补三条规模点的耗时记录，并把 `tools/benchmark_large_library.py` 的 folder 形状加一个「宽顶层目录」变体（现在只有 80 个顶层目录，任何无界形状都看不出问题）。（R60 补销：本轮记录清点发现此条在 R58 关闭后仍挂着，关闭记录见同文件上方「R58 关掉首屏文件夹搜索的挂起」。）
- [x] 2026-09-18：R57 遗留：不带 `root` 的文件夹页仍然全表扫。`conditions = ["f.parent = ?"]` 这条分支没有任何可用索引，实测 20000/50000 行 5.52/14.40 ms（仍受同一 `TEMP B-TREE` 影响）。要先取证：UI 只在选中某个根之后才浏览目录（`app.js` 的 `folderParams` 仅在 `state.folderRoot` 非空时带 root），所以这条通道的真实消费者是 `/api/library/folders?parent=...`（无 `root`）与 `server.py:3117` 的 `folders(parent, root)` 适配点；确认有消费者再补 `(parent, name COLLATE NOCASE <dir>, path)` 一对索引，别在没有消费者时白搭三份写放大。  **R95 关闭**：这条要求「先取证再补索引，别在没有消费者时白搭三份写放大」✓ 取证结论是消费者存在：UI 侧 `src/app/ui/app.js:5745` 写的是 `if (state.folderRoot) folderParams.set("root", ...)` ✓ 也就是没选根时这个参数根本不出现 ✓ 服务端 `server.py:908` 又是 `(query.get("root") or [""])[0]` ✓ 于是 `library.py:1562` 的 `conditions = ["f.parent = ?"]` 分支是活的；播放器适配器 `server.py:3154` 的 `folders(parent, root)` 也原样透传 root ✓ 所以补索引不是白搭。做法照这条开出的方案：在 `library.py:2273` 之后新增 `idx_folders_parent_name_nocase_asc` 与 `..._desc` 一对 `(parent, name COLLATE NOCASE <dir>, path)` ✓ 让页既能 seek 又能按自身 limit 停下 ✓ 收益实测（本机）：裸 SQL 2 万行 0.99 ms -> 0.05 ms（计划从 `SCAN f / USE TEMP B-TREE FOR ORDER BY` 变成 `SEARCH ... USING INDEX idx_folders_parent_name_nocase_asc (parent=?)` ✓ 无临时排序 ✓）✓ **走真函数 `query_library_folders` 的 10 万行分页 5.84 ms -> 1.27 ms（约 4.6 倍 ✓ asc/desc 都量了 ✓）**；与这条原记的 5.52/14.40 ms（2 万/5 万行 ✓ 另一种页形）同向 ✓ 不冲突。**写侧代价一并量了**（这条点名的风险 ✓ 不回避）：同一批 2 万行重建 100.97 ms -> 146.49 ms ✓ 约 +45% ✓ 摊到每个目录行约 5.0 µs -> 7.3 µs ✓ 盈亏平衡点约 45 次无根浏览/一次全量重建 ✓ 根过滤那条通路的计划与耗时未变（0.04~0.05 ms ✓ 仍用 `idx_folders_root_parent_name_nocase_asc` ✓ 已在测试里反向钉住「窄索引不得抢走带根查询」✓）。语义也未动：同一个 parent 串存在于两个根时，无根列表仍跨根返回（测试断言名字序与根集合 ✓）。变异 7 例全由这条新测试杀死：W1/W2 少建一个方向 ✓ W3 只建 `(parent)`（正好复现我探针里那个残留 `TEMP B-TREE` ✓）✓ W4 建成 `(root,...)` ✓ W5 把无根分支改成要求 root（被跨根断言杀死 ✓）✓ W6 误用 UNIQUE ✓ W7 **复用已有索引名**（`CREATE INDEX IF NOT EXISTS` 会静默不建 ✓ 这条专门留着当陷阱记录 ✓）。本轮另外两个自伤都被抓住：写测试时漏掉 `EXPLAIN QUERY PLAN` 前缀 ✓ 两条断言其实在跑真查询 ✓ 是断言消息里出现文件夹名而不是计划文本才暴露的 ✓；第一次走真函数的测量因为夹具没 `commit()` ✓ 返回 0 行却仍报出 1.27/0.47 ms 这种像样的数字 ✓ 若在写记录前不比一眼行数就会把废数写进文档 ✓。另：相邻的 `:71`（`COUNT(*)` 覆盖索引遍历约 5 ms ✓ 要把子项数做成持久列）本轮未动 ✓ 它自己写明「当前不做」✓ 不在这里冒领 ✓
- [x] 2026-09-18：R57 遗留：50k 顶层目录时剩余 5.91 ms 的主成本是 `SELECT COUNT(*) FROM folders WHERE root=? AND parent=?` 的覆盖索引遍历（约 5 ms）。若还要继续压首屏，需要把「每个目录的子项数」变成持久列或按目录缓存计数，并与 `_library_cache_epoch` 用同一失效口径；当前不做，因为 12.13 到 1.21 ms 的量级已经不再受目录宽度支配。  **R127 关闭**：这条的理由本轮重测过，原文那句「当前不做，因为 12.13 到 1.21 ms 的量级已经不再受目录宽度支配」只在缓存命中路径成立 ✓ 走真函数 `query_library_folders`、50k 个目录挂在同一个父目录下：未命中首页 9.2~11.5 ms（其中本条目点名的那条 count 占 4.39 ms）、深 offset 页 16.9 ms、同参热重复 0.26 ms 且一条语句都不发。同时取证到一个新事实：folders 面没有 saved-count 摊销协议，`_save_library_meta_count` 那套只服务 groups（`src/app/server/library.py:1593-1610`），所以一次未命中就得重算 count。结论仍是不改生产代码：不加持久子列、不做按目录计数缓存，因为这笔成本只在未命中时出现且只占未命中耗时的一部分，而持久列要额外背写放大与第二套失效口径。真正让「可以不做」成立的前提是那层缓存 ✓ 于是本轮把前提钉成守卫而不是把数字抄进注释：`src/tests/test_library_sqlite.py:2686-2702` 对 trace 出的真实 count 语句断言计划必须落在 `COVERING INDEX idx_folders_root_parent`、detail 不含 `nocase`、禁 `TEMP B-TREE`（删掉 `library.py:2389` 那个索引后 SQLite 会静默改用更宽的 NOCASE 排序索引，同一 count 从 0.55/4.39 ms 退化到 5.38/14.23 ms）；`:2704-2768` 新增 `test_repeated_folder_page_is_served_without_rereading_the_directory`，钉住同参热读 0 条语句（`:2750`）、换 offset 必须重读（`:2753`）、写库后必须重读（`:2766`）。仓库外副本变异 8 试 6 灭 2 存活：V6（`invalidate_library_query_cache` 空转）与 V7（缓存身份置空）各自存活是因为写路径上两处机制互为兜底，双旋钮 V8 同时摘掉必杀 `:2766`；完整变异数字见 `CHANGELOG_AI.md` 本轮条目与 `PROJECT_CONTEXT.md`。
- [x] 2026-09-18：R56 量化并关闭「R55 之后同一形状的下一处」。`provider_candidate_cache` 不需要字节账：值至多 8 条候选、每条字段在 provider 边界就夹过（文本 4096/URL 2048/标识 32），递归 `sys.getsizeof` 实测典型整缓存 0.6 MiB、每字段顶满的对抗形状最坏 2.8 MiB（ASCII）/4.8 MiB（CJK），键侧六段各限 256 字符同样有界。条目上限在这里已经等于字节上限，测完记录，不改代码，也不要照抄歌词那套常量。
- [x] 2026-09-18：R55 的歌词缓存字节预算只做到构造参数为止，没接配置。要接得同时改 `config.py` 的默认表、区间表、归一化三处并补校验测试；默认值 8 MiB 目前是推断值（够放几千条正常正文，同时把最坏驻留从 512 MiB 压到 8 MiB），缺真机 RSS 与低内存回收证据。拿到设备侧内存曲线前不暴露成 `metadata_lyrics_cache_max_bytes`。 〔R138 X7=A 裁定关闭：接受 8 MiB 默认值，并把配置接入在本轮离线做完。落地清单：`src/app/server/metadata_local_lyrics_cache.py` 新增 `CONFIG_BYTES_KEY` 与 `bytes_limit_from_config()`（非 dict／缺键／非 int／bool 一律回退默认，越界交 `_bounded_bytes` 夹取）；`src/app/server/metadata_service.py` 两处构造点（`MetadataProviders` 与 `MetadataService`）都改传 `max_bytes=bytes_limit_from_config(self.config)`；`src/app/server/config.py` 三处注册（默认表 8 MiB、`load_config` 区间 (64 KiB, 8 MiB, 64 MiB)、`save_config` 走 `_bounded_int`）。判别测试共 6 枚分布在 3 个测试文件：load 单侧夹取、与缓存自有钳位一致、配置值抵达 `bytes_limit`、破损配置回退默认、三条道都读配置、无配置保默认。仓库外副本变异 V2/V3/V4/V5/V7/V8 全部被杀。真机 RSS 曲线仍未取到，但 X7 裁定它不构成「不接配置」的理由，内存曲线归设备段既有项，本条关闭。〕
- [x] 2026-09-18：R55 关掉「R54 之后剩下的半条账」。`LocalLyricsCache` 现在同时按条目和字节封顶（新增 `max_bytes`，默认 8 MiB、可配 64 KiB-64 MiB，`sys.getsizeof` 内存口径），条数或字节任一超限即驱逐最老，单份大于整个预算的正文只服务不留存；`bytes`/`bytes_limit` 与 `artwork_bytes` 同框上报到 `/api/health` 与诊断摘要。测量：默认 256 条下最坏驻留 512 MiB→8 MiB（条目上限配到 4096 时原本是 8 GiB），正常 6 KiB 正文 256 条合计 1.47 MiB 不受影响。变异 18 项尝试、16 捕获，2 项等价存活已记入 CHANGELOG。
- [x] 2026-09-18：R54 的超限旧正文清理策略是「拒绝即清空」。若希望保留而不覆盖，需要一个能表达「存着但不可展示」的列或标记（`lyrics_source`/`confidence` 都不适合挪用），并在 `/api/lyrics`、页叠加、标签回写三处都按该标记走；没有真机证据前不动。 〔R138 X8=A 裁定关闭：保持「拒绝即清空」，不引入「存着但不可展示」的第三态。理由：新列/新标记要在 `/api/lyrics`、页叠加、标签回写三处同时改语义，代价与收益不匹配，且至今没有任何「旧正文被误删造成可观测损失」的证据。若将来真出现该损失，按新证据另案，而不是复活本条。本轮不改代码。〕
- [x] 2026-09-18：逐行读完 `src/app/ui/creator_view_policy.js`（116 行，15 个导出）并记录判定，无需改动。核对过的点：`boundedCreatorName` 对超长名（>512）整份拒绝而非截断，与「文档字段整份接受或整份拒绝」口径一致；`boundedTrackTotal` 拒绝布尔/对象/NaN/负数/非整数并把上界钳到 1e9，空串走 `Number` 前就被类型判断挡掉；`creatorPart` 用 `hasOwnProperty` + try/except 读 `state`，代理对象不会泄漏；`setCurrentCreator` 写名字时顺带清 `AllTracks`、`clearCurrentCreator` 与 `resetCreatorState` 三者对称；视图判定链 `isCreatorAlbumView`/`isAlbumDetailView`/`isAlbumSurfaceView` 对 `null` 与缺字段都短路，不存在 `state.groupName` 裸读崩溃。既有 `tests/test_ui_creator_view_policy.js` 覆盖这些导出。
- [x] 2026-09-18：`classify_mpd_log_errors(log_text, limit)` 与 `_tail_text(path, limit)` 的 `int(limit)` 会在非数字输入上抛 `ValueError`（`_tail_text` 的还包在 `except OSError` 里，兜不住）。今天两个调用点都传字面量，属潜伏；要么按有界数值口径给它一个不抛异常的归一化，要么显式声明「只接受内部字面量」并让断言盯着。  **R79 关闭（选了归一化那一支）**：两处都改用仓库既有的公共归一化 `summary_values.nonnegative_int`（`playback/mpd_errors.py:148`、`services/mpd_service.py:2067`），没有新增第四个小助手，也没有去 import `metadata_provider_response._safe_limit`（那是元数据域的私有件，跨域拽一根线不划算）。`_tail_text` 的归一化同时**挪出** `except OSError`——那个 handler 只管文件操作，把转换留在里面正是原条目说的「兜不住」。两个既有语义一个都没动：`limit or 20` 让 0 继续表示「未设置」，负数仍钳到下限 1 而不是回落默认（变异 P3、P4 分别钉住这两条）。判别测试两条，矩阵 M0 控制组 47 条先绿。
- [x] 2026-09-18：R53 已修 `/api/health` 的 `components.mpd.error_category` 恒空（白名单只转发 `count`/`last_error`，而派生函数只读 `items`），并把 `health_error_category`/`legacy_decoder_error_summary` 收敛到同一个有界读取器。审计方式是记录型字典经验探测，同法扫过 `transcode_summary`、`library_component`、`dlna_component`、`project_http_workers`、`project_metrics`、`empty_mpd_error_summary`，其余白名单与读取键重合或不经白名单，无同类失真。新增 6 项回归、17 项变异全捕获。
- [x] 2026-09-18：ID3v2.4 的**帧级**标志仍未处理（`0x02` 帧内 unsync、`0x10` 压缩、`0x08` 加密、`0x01` data-length indicator）。R52 只修了标签级 `header[5]`。帧级标志为真时现在的行为是「读错」而不是「跳过」：压缩帧会把 zlib 字节当正文返回给标题字段，带 data-length 的帧会整体错位 4 字节（长度字段被当成正文头）。缺的是真实样本：本轮已把读写两侧收敛到同一个解析器，再盲改就无法验证，先确认真机曲库里是否存在这类帧以及有多少，再决定是实现还是显式拒绝。  **R103 关闭（条目说「先确认真机样本 ✓ 再决定是实现还是显式拒绝」✓ 但这条要求里混了两件事：帧标志被完全忽略是解析器的既有事实 ✓ 不需要样本就能修；需要样本的是「有损保留要不要做成无损」✓ 而后者不构成为前者继续把密文当标题付给曲库的理由）**：位值更正——条目写的 `0x10` 压缩、`0x08` 加密不对 ✓ 以 mutagen `mutagen/id3/_frames.py` 的 16-bit 帧标志为准 ✓ v2.4 是压缩 `0x0008`、加密 `0x0004`、grouping `0x0040`、帧内 unsync `0x0002`、data-length indicator `0x0001` ✓ `0x0010`/`0x0020` 为保留位；v2.3 才是压缩 `0x0080`、加密 `0x0040`、grouping `0x0020` ✓ 照条目值实现会漏杀压缩帧并错杀保留位。落地：`iter_id3_frames()` 读出 `payload[offset + 8:offset + 10]` 交给新的 `_frame_body()` ✓ 两种可撤销变换就地还原且顺序固定（先剥 4 字节 indicator 再展开 unsync ✓ 反过来会让 indicator 的字节数与实际偏移脱钩）✓ 其余任何置位的 format 位一律拒绝该帧 ✓ 但 `offset = frame_end` 继续走 ✓ 跳过不等于中断。反向断言同轮钉住：status 位（v2.3 `0x8000/0x4000/0x2000`、v2.4 `0x4000/0x2000/0x1000`）不得造成跳过 ✓ `major != 4` 不得放宽成 `major < 4`（v2.5 标签会走到这里 ✓ 它的位含义不由 v2.4 规则保证）。写侧：`metadata_service.py:296 _id3_frame()` 硬编码 `b"\x00\x00"` ✓ `:320 _preserved_id3_frames()` 用它复制未管理帧 ✓ 所以修复前「保留」压缩帧的真实行为是「清除标志 + 原样搬运密文」= 彻底破坏 ✓ 修复后是丢弃并在 docstring 记明代价 ✓ 带 indicator 或帧内 unsync 的帧改写后成为正确的明文帧。「有损保留」这一支本轮不主张无损 ✓ 其真机样本前提仍留在设备段流程 ✓ 按反增长约束并入本条不另立项。
- [x] 2026-09-18：R52 的槽位移交留下一个新的弱口。被接管的旧请求不再占槽，但它**仍可能在 settle 时写响应缓存**，`getEpoch() === epoch` 是唯一防线。因为接管只发生在同一 URL 上，写回内容仍是那一页的合法结果，只是可能比替换者晚到一步、把更新的响应换成稍旧的。生产唯一调用点 `fetchLibraryResponse` 确实传了 `epoch`/`getEpoch`（`app.js:5146-5157`），所以后果限于「同一页的一份旧 JSON」，暂不改；若将来出现「切页后短暂看到旧数据又变回来」的观感，再考虑给被接管者加一次性作废标记。  **R102 关闭（条目要求「若将来出现观感问题再考虑」✓ 本轮不观感也能定：这条弱口不依赖观感就能证伪 epoch 的充分性）**：接管条件是 `existing.__fnAudioAbortSignal?.aborted === true` ✓ 成立时被弃请求已从 `inflight` 摘出 ✓ 但它的 `.then` 仍闭包持有本次 `load()` 的 `epoch` ✓ 而替换者拿到的 `epoch: state.libraryResponseEpoch` 是同一个值 ✓ 于是 `getEpoch() === epoch` 对双方同时为真 ✓ 唯一还能区分所有者的是 loader 内部的 `inflight` 身份 ✓ 而它没被用在发布门上。落地形式：`let cacheWriteVoided = false;` 声明在接管分支之前 ✓ `request.__fnAudioVoidCacheWrite = () => { cacheWriteVoided = true; };` 与既有 `__fnAudioAbort`/`__fnAudioRelease` 同一处挂载 ✓ 接管分支在 `__fnAudioRelease?.()` 之后紧跟 `__fnAudioVoidCacheWrite?.()` ✓ 发布门 `if (!cacheWriteVoided && getEpoch() === epoch)` ✓ 两道门各管一种过期：epoch 管跨代次 ✓ void 管同代次内被接管。`return data` 刻意不动。判别性测试的关键场景是「传输忽略 `signal` 的旧 WebView」：旧实现下 `dead response` 会在 `fresh response` 之后覆盖缓存 ✓ 新实现下不会。既有钉 `test_ui_library_loading.js:512` 同步更新为要求两道门都在（收紧 ✓ 未放宽）。变异 W1~W10 全灭 ✓ 其中 W6/W8 是被顺序钉杀掉的等价变异 ✓ 已标明它们不证明行为。
- [x] 2026-09-18：R52 关闭「中止的在飞请求永久占槽」这条，先量化再定性。所有 `fetchJsonChecked` 路径都经过 `fnAudioResponseJsonLoader.read({timeoutMs: 15000, onTimeout: abort})`，加载器在 settle 时释放槽位，所以**即使传输完全忽略 signal，最坏也只是占住一个槽 15 秒**（32 槽在死网下 15 秒内可饱和），不是永久泄漏；`Math.max(0, activeCount()-1)` 又保证被写坏的计数能自愈。在此前提下仍把便宜修法做了：检测到「已中止的在飞项」被同 URL 替换时顺手调用它的 `__fnAudioRelease?.()`，并先补两条前置行为断言（手工释放后 settle 不得再减、共享在飞的第二个调用者不得替别人放槽），使这条改动依赖的「幂等」成为被测事实而不是注释承诺。
- [x] 2026-09-17：R51 顺带查过户markup 复用阈值的边界：`src/app/ui/library_snapshot_reuse_policy.js` 的 `MAX_SIGNATURE_CHARS = 2048` 一旦有任一行签名超长就整页返回 null（整页失去复用，回退全量重绘）。服务端 `clean_tag` 允许单个标签 4096 字符（`metadata_text.py:9`），策略层 `safeText` 也是 4096，所以理论上可超长；但按默认库视图（标题/歌手/专辑/大小/格式）与 `escapeHtml` 展开估算，一条标签拉满的古典轨大约落在 700 到 900 字符，正常数据离 2048 还有一倍余量，且回退方向是安全的（宁可多画一次）。本轮判定不动代码：真在真机 trace 里看到整页重绘，再按「逐行比较、超长行单独判不等」改，别去抬那个上限（抬上限只是把偶发变成必然）。〔R132 实测（不采信估算，直接跑真策略码 `src/app/ui/library_row_signature_policy.js`）：本条「正常数据离 2048 还有一倍余量」**被证伪**——余量不是估算值而是数据上界决定的：默认五列视图（title/artist/album/size/format）下一行正常签名实测 **151 字符**，单字段独立触发超长回退所需长度为 **title 1,917 / artist 953 / album 953 / cover URL 1,929** 字符，三字段等长时 386×3＝1,158 字符即触发；而服务端 `src/app/server/metadata_text.py:9` 的 `MAX_TAG_TEXT = 4096` 允许单个标签长到 4,096 字符 ⇒ **服务端自己放行的标签长度足以单字段就把整页顶到全量重绘**，本条按「古典轨长标签」举的例子（700~900 字符）实测签名 1,212 字符，仍在阈内，所以真实触发面比本条设想得更低。另测得调用点事实：`app.js:5385` 的 `canReuseMarkup` 返回**页级**布尔，`reuseSnapshotTrackMarkup` 为假时整页 HTML 重生成，所以本条建议的「逐行比较、超长行单独判不等」在页级复用下与现状等价、并不减少重绘，真正能降代价的做法是「超长字段改用摘要保持可比」——那是新的产品判断，不是本条原案。⇒ 结论：门槛原样保留（本条把动作绑在真机 trace 上），**不关闭、不改代码**，上述实测并入本条并作为决策清单第 (三) 项的推荐依据；插一条提醒：实测长度未含调用点再包一层的 `JSON.stringify([id, rowSignature])`（再加 id 与约 4 字符），故 953/1,917 是偏保守的上界。**补记（接管方独立复算）：这些字符数是夹具相关的**——换 cover URL 长度或列集合就会整体平移十几到几十字符；另按真实调用点形状建模（`app.js:2946` `trackColumnValues` 使 artist/album 在 title 三元组与自身列单元格中各出现一次）复算得基线 173、单字段阈值 artist 940／album 943／title 1,878、三字段等长 379×3＝1,137，与上文 151／953／953／1,158 同数量级（若不建模那层重复，会得到 artist≈1,878 而把阈值高估近一倍）；两组夹具都远小于服务端 `MAX_TAG_TEXT = 4096` ⇒ 「单个正常长度的标签即可顶穿整页复用」这一结论不随夹具变化。〕 〔R138 X9=A 裁定关闭：接受「回退方向安全」——超长行签名使整页失去复用，最坏结果只是多画一次而不是画错。R132/R133 的实测全部保留为事实（默认五列正常行签名 151 字符、单字段阈值 title 1,917／artist 953／album 953、服务端 `MAX_TAG_TEXT=4096` 单字段即可顶穿页级复用），但 X9 既不选「抬上限」也不选「超长字段改用摘要」，故**不新立任何后续项**；真机 trace 若真观测到整页重绘，届时按新证据另案。本轮不改代码。〕
- [x] 2026-09-17：R51 确认：`metadata_unavailable_policy` 的三处 lyrics 读取在生产调用点是空转（`find_library_item` 返回扫描器行，`item_json` 里没有 lyrics；只有 `enrich_track_page` 之后的页副本才带，且公开投影会再 pop 掉）。要把它变成真功能，先定三件事：其一，冷启动窗口内值不值得读盘（`read_local_lyrics` 走 ffprobe，单次上限 15 秒，落在 `/api/lyrics` 请求线程上不可接受）；其二，是否改成直接开元数据库读 `metadata_tracks.lyrics`（绕开 worker，但连接生命周期归 `MetadataService` 管，需要新的边界与失败处理）；其三，若维持现状，就把这三处与 `server.py:972` 的恒假分支一起删掉，别留给下一轮重新论证。缺的证据是真实冷启动窗口长度与窗口内用户打开歌词的频率，量之前不动代码。  **R106 关闭（复现证伪前提，非改码）**：前提「三处 lyrics 读取在生产调用点是空转」不成立 ✓ 端到端复现证明可达。链：旧版 `library.json` 带 `lyrics` → `load_library_cache`（`library.py:2789`）→ `prepare_track_persistence` 把整行 `json.dumps` 进 `item_json`（**无键白名单**）→ `query_library_item_by_id`（`library.py:1726`）原样解出 → 三处投影读到真实值 ✓ `server.py:3335` 启动即调用加载器。反证：`enrich_track_page(self, page, include_lyrics=False)` 的三个生产调用点 `server.py:877 / 887 / 931` 全部默认 `False` ⇒ 生产里 enrich **从不写 `lyrics`**（`metadata_service.py:4415-4419`）✓ 原条目把供体方向说反。措辞纠正：「`server.py:972` 恒假分支」实为 L963 `elif not METADATA_SERVICE:` ✓ 与上一支同义取反 ✓ **会执行** ✓ 已改为 `else:`；被误判为死的另一半是 L973 的 `or local_projection.get("lyrics")` ✓ 它有效。冷启动读盘（`read_local_lyrics` 走 ffprobe ✓ 单次上限 15 秒落在请求线程）仍否决 ✓ 直接开元数据库读 `metadata_tracks.lyrics` 仍否决——两条都不必做 ✓ 因为分支本来就活。测试：`test_legacy_json_cache_rows_survive_into_the_single_item_lookup`（缓存文件→内存→`item_json`→SQLite 单行查询→两投影全链）✓ `test_lyrics_startup_projection_reads_the_raw_library_row` ✓ `test_uninitialized_metadata_service_returns_a_lyrics_only_track_as_local` ✓ `test_full_document_lyrics_survive_every_recovery_projection`；变异 M01 / M02 / M03 / M04 / M05 / M09 / M12 / M14 全部由具名用例杀掉。
- [x] 2026-09-17：R51 否证：`library_presentation.py` 里 `metadata_artwork_id` 兜 `cover_url` **没有**顺序问题。真实调用序是 `query_library_page` → `prewarm_thumbnails` → `enrich_track_page` → `public_library_page`（`src/app/server/server.py:873-877`、`883-887`、`923-935`），兜底发生在投影之前；端到端复现里公开行的 `cover_url` 就是 `metadata/artwork/<64hex>`。这条是靠复现证明前提不成立关掉的，不是改代码关掉的；只有以后有人把 enrichment 挪到投影之后，它才会重新变成缺陷。
- [x] 2026-09-17：R50 已修：可见行元数据的预算改为取行之前先花（`selectCandidates` 预算为 0 时不再返回一条，被跳过的行不再白吃预算），`boundedLimit` 把空白字符串识别为未设置而不是 0（三处共用判定同时受益）。新增 15 条行为断言，六处变异全部命中，并按「先摘源码正则再判定」复核过行为覆盖。同时用真实 120 行页载荷结掉热页防御性拷贝的两条路线：手写递归克隆 0.317ms 不比 deepcopy 0.300ms 快，json 路线 0.151ms 但需要 put 期类型保真校验，判定为不划算并记录数字。
- [x] 2026-09-17：热页拷贝成本若要再降，唯一有希望的路线是让缓存层存「已经编码好的响应」而不是 Python 结构，那要连着改 `src/app/server/server.py` 的 JSON 出口与 `metadata_service.enrich_track_page` 自己那次 `dict(item)` 复制。在动那条路之前，不要再试手写克隆或 json 往返（本轮已实测：递归克隆 0.317ms 对 deepcopy 0.300ms；json.loads 0.151ms 但类型保真需 put 期约 0.4ms 校验）。  **R131 关闭（净关闭 1 条、新立 0 条）**：本条自设的门槛被一条它没预料到的路线跨过 —— 热页的钱大部分不花在拷贝上。取证：`enrich_track_page`（`metadata_service.py` L4316 起）按行重复做三件事 —— ① 行身份 `_page_track_id` 每行算 3 次（`ids` 收集、`item_by_id` 建表、合并循环），② 每次缓存命中都把存着的 `fields_json` 重新 `project_match_fields` 解码并逐字段重算长度边界，③ 每行重跑 `_provider_text(value, 128).strip().lower()` 折叠 artwork id。修复＝三件事都挪到「已经为该行付过钱」的那一次冷读：新增 `_overlay_artwork_id()`（L1895），冷读把 overlay 存成带 `projected` 成品字段与折叠后 `artwork_id` 的字典（L4408-4411），命中路径退化为查表（L4423、L4440），身份归一化改成一趟 `track_ids`（L4351）并由 `item_by_id`（L4358）与合并循环（L4426-4427）复用；缓存 get/put 仍双向 `copy.deepcopy`（L2020、L2037），所以「缓存里存成品」没有削弱内层只读保证。量纲（仓库外副本、400 次/轮×5 轮取最优、扣 `fresh_page()` 基线）：1.524 ms → 0.722 ms＝降 0.80 ms／52.6%（同轮另一副本 1.571→0.737＝−53%，两组值并列不合并）。等价性：新代码与 HEAD 副本在固定根上产出的 JSON 响应均为 68,706 字节、sha256 同为 `05bf20273094611e3679545eafe661cc4e07f75a6da5034efa23df2f107f1954`、逐字节相同。**本条主张的编码响应路线否决**，两条实据：① 热页出口每行现算封面字段（`library_presentation.py:111` 的 `public_library_page` 调 `:53` 的 `public_library_item`，后者经 `cover_cache.py` 的 `cover_is_known_missing` L533、`cover_source_version` L205、`thumbnail_asset_id_for_item` L414 读实时封面缓存，而 `prewarm_thumbnails` L837 会在 500 ms TTL 中途新增别名）—— 冻结编码响应会让缩略图在 TTL 内不出现；② `send_json`（`server.py:726-751`）每请求写 `X-Request-ID`（L732）、`/api/` 一律 `no-store`（L736-738），编码响应无法跨请求复用。**残余量已量化**：把 `metadata_service.copy.deepcopy` 换成 identity 后热页 0.701→0.444 ms（≈0.26 ms／剩余约 40%；另一副本 0.740→0.437＝0.303 ms／41%），本轮不采纳 —— 它会把缓存内层只读性从结构保证降级为口头约定，收益也不足一条待办门槛。**判别测试**：`src/tests/test_metadata_service.py` 新增 fixture L2271 与用例 L2308/L2341/L2353（计数式断言冷读投影次数＝行数且热页零新增、缓存条目键集合恰为 artwork_id 与 projected 且不再携带 `fields_json`、每页身份归一化次数＝行数），仓库内复跑 Ran 227 OK、三条新用例点名 Ran 3 OK；仓库外副本 `%TEMP%\r131c2` 变异矩阵控制组先绿、6 个变异体 6/6 KILLED、跑完 `restored=True`。
- [x] 2026-09-17：R49 已修：`cue_parser` 的每轨结尾从每轨往后重扫改为按文件分栈的一趟线性算法（5000 轨实测 3069ms 到 20.44ms、3103ms 到 14.07ms，语义用旧定义对拍钉住）；同时修掉 `INDEX` 行判定写死单空格与两位数字导致的功能缺陷：制表符分隔、`INDEX 1`、双空格三种合法写法过去被整体忽略，表现为 CUE 轨时长塌成整张镜像且播放起点退回 0。`test_cue_parser.py` 6 项到 11 项，11 处变异全部命中。
- [x] 2026-09-17：「线性」目前靠 `finite_number` 调用计数断言（每轨至多两次归一化）。这是**用实现细节代理复杂度**：如果以后把归一化提到主循环、或换成别的数值包装，这条断言会误报失败。真要长期钉住复杂度，可考虑的替代是给 `parse_cue_structure` 的结尾阶段做一个显式可注入的比较计数器，或者把这条断言降级成一条带注释的基准脚本；计时阈值这条路判定为不可用（共享机器上抖动大于要区分的那一倍）  **R105 关闭（走条目自己开的第一条路：显式可注入的比较计数器 ✓ 并把「这条界能区分两种算法」本身钉住）**：seam 落在 ✓ `parse_cue_structure(lines, fallback_album, observe_end_stage=None)` 转发给 `_attach_track_ends(tracks, observe=None)` ✓ 在 `while stack:` 的每次比较处调用一次 ✓ 计的是「被考察的候选起点数」而不是任何数值 helper 的调用数（条目担心的正是后者）。改写把 `while stack and stack[-1] <= start` 拆成 `while stack: observe(); if not (stack[-1] <= start): break; stack.pop()` ✓ 严格等价（不可比值走同一谓词）✓ 变异 M13（`<=` 改 `<`）由既有随机对拍用例 `test_track_end_matches_the_nearest_later_start_on_the_same_file` 杀掉 ✓ 证明重写没顺手放松语义。旧脆弱断言 `test_track_ends_do_not_rescan_the_sheet`（monkeypatch `cue_parser.finite_number` 再断言调用数 ≤ 2n）整条删除 ✓ 不留旧形态 ✓ 并加一条自读测试文件源码的反向断言：本文件不得再出现 `cue_parser.finite_number =` 赋值。新增 7 条判别性用例（`test_cue_parser.py` 163 -> 265 行 ✓ 11 项到 18 项）：三轨小表精确计数 == 2（同时杀「未转发=0」「每次计两下=4」「每轨计一次=3」「挂到 push 点=3」） ✓ 一格一轨 1200 表 ≤ 2n ✓ 无 INDEX 的扁平表恰好 n-1（给上界配一条非空口 ✓ 否则「什么都不计」也能过） ✓ 规模斜率：表放大 4 倍时工作量 ≤ 6 倍（线性比值 4 ✓ 二次会到 16） ✓ 在测试里重述旧嵌套定义并按同口径计数 ✓ 断言它必然越过 2n —— 这条是「界可分」的证据 ✓ 没有它上面那些界只是空洞通过 ✓ hook 中性：带计数器与不带计数器的产物逐项相等 ✓ 签名与可选性钉（两处 hook 默认值必须是 None 且可按关键字传入）。仓库外副本（robocopy `src` + `android-client`）JS 控制组 69/69 先绿 ✓ 变异矩阵 M01–M13：12 项被具名用例杀死 ✓ M12（`if observe is not None:` 同义改写成 `if observe:`）按设计存活并如实标注为等价 ✓ 矩阵跑完控制组仍 OK。方法学记一笔（R88 同类教训第二次生效）：首轮 M06/M07 是**语法假杀** ✓ M06 的替换串多插了一行重复谓词、M07 的替换串吞掉了 `while stack:` ✓ 两者只触发 IndentationError 就让套件非零退出。驱动因此新增 INVALID-KILL 口径：只有拿到具名失败用例才记 killed ✓ 重跑后 INVALID_KILLS=0 ✓ M06 确认只被「hook 中性」那条杀掉。净账：开放 110 -> 109 ✓ 可离线代码 46 -> 45 ✓ 新立 0 条 ✓ 设备段未动 ✓ 计时阈值沿用条目原判（共享机抖动大于要区分的一倍）不采用。
- [x] 2026-09-17：CUE 谱里同一轨出现两次 `INDEX 01` 时，后一次覆盖前一次（旧实现也是）。本轮对拍只证明「新旧一致」，没有定「该取第一个还是最后一个」。真实谱里偶见录音师留下的重复索引，建议取第一个并拒绝后续，需要先找一份真实样本再定，避免把更好的口径换成更坏的。 〔R138 X10=A 裁定关闭：口径定为「同轨重复 `INDEX 01` 取第一个、拒绝后续」，并已在本轮落地。实现：`src/app/server/cue_parser.py` 的 `parse_cue_structure` 增加循环局部 `index01_seen`（TRACK 分支复位为 False、`INDEX` 分支条件加 `and not index01_seen`、命中后置 True）。判别测试两枚：`tests.test_cue_parser` 的「重复 INDEX 01 保留首个起点」与「跨轨复位」。仓库外变异 V1（撤守卫）与 V6（轨间不复位）均被杀。本条原文「需要先找一份真实样本再定」由 X10 裁定替代：重复索引属退化输入，首个 `INDEX 01` 是谱面权威起点，取首个是可论证不劣于取末个的保守口径，无须等样本。〕
- [x] 2026-09-17：`library.py` 里 `cue_end` 用 `or` 从 0.0 退回整轨时长，于是「这是该文件的最后一轨」与「结尾未知」共用同一个 0.0。本轮没动这条既有口径；若要区分，得先把结尾改成 None 并逐个检查消费方（`cue_item_presentation` 的时长、`playback_cue_position` 的绝对位置、写库列 `cue_end REAL NOT NULL DEFAULT 0`）。  **R113 关闭（严格按本条要求的两步：先把结尾改成 None，再逐个查消费方）**：三态落在 `cue_parser._attach_track_ends`（:29-42 定义 ✓ :79 产出 ✓ 非字符串 `file` 支 :62 改判 `None`）✓ 归一化落在 `cue_numeric_policy.cue_segment_end`（:24-46 ✓ 只有 `0.0` 态可借文件时长 ✓ `None`/负数/非有限一律 `0.0`，即写库列既有哨兵）✓ 消费方逐个核过：`cue_item_presentation.py:10`、`playback_cue_position.py:48`（两处 `cue_end > cue_start` 守卫 ✓ 本轮仅加注释、逻辑未改）、`library.py:2138` 列定义与 :2278 迁移、`library_write.py:144`/`:152`、`metadata_job_payload_policy.py:14`、前端 `app.js:2462`。判别测试 +6：`test_cue_parser.py` 18 → 21（三态参照 + `states` 集合断言 + :160 表驱动）、`test_cue_item_presentation.py` :22、`test_playback_cue_position.py` :24、`test_media_formats.py` :78 端到端。仓库外副本变异 V1–V13 13/13 全灭 ⇒ 见变更文档同轮记录。
- [x] 2026-09-17：`_attach_track_ends` 直接用文件值当字典键，隐含前提是它恒为可哈希字符串（`cue_value()` 目前保证这点）。以后若允许别的类型进来要先显式归一，否则是 TypeError 而不是解析降级。  **R88 关闭（前提是真的，但不该让它继续承担隐含责任：显式归一，并第一次单独钉住）**：先核前提——`metadata_text.py:72 cue_value()` 两个分支都落到 `clean_tag()`，而 `clean_tag` 对非字符串一律返回 `""`，所以走解析器进来的 `file` 确实恒为 str，条目的判断成立。不成立的是「有人钉着」：`test_cue_parser.py` 此前只有端到端用例，没有任何测试直接调 `_attach_track_ends`。归一放在解析器侧（`cue_parser.py:32-40`）：非字符串的轨道不分组，`end = 0.0`，不与任何人共享栈。不折叠成同一个键，因为那会让无关曲目互相截断时长；也不继续依赖上游，因为条目说的正是「以后若允许别的类型进来」。新测试 `test_a_track_whose_file_is_not_a_string_degrades_instead_of_raising`（`test_cue_parser.py:82`）断言字符串组的排布不受被跳过的轨道影响（`[30.0, 0.0, 0.0, 50.0, 0.0, 0.0]`），并且 `"7"` 与 `7` 不共享栈。变异四例（控制组 19 条 0.030 s 先绿）：B1 去掉守卫 -> 只被新测试抓到（TypeError）；B2 折叠成 `""` -> 新测试的分组断言失败；B3 改用 `try/except TypeError`、B4 同义改写成 if/else -> 按设计存活（等价实现）。记一笔方法学：第一版 B1/B3 的锚点多吞了一行 `name = track.get("file")`，四个变异一起报 14 个 error，那是语法假杀不是证据；改成从源文件现取锚点（只截 `if not isinstance` 到 `continue`）之后才有区分度。
- [x] 2026-09-17：R48 已修：封面与美术资源响应的 `Content-Type` 不再是标签或 provider 响应头里的自由文本。新模块 `src/app/server/cover_media_type.py` 是唯一判定（魔数优先、字符集消毒、光栅白名单、拒绝 markup 前缀、永久排除 `image/svg+xml`）；`id3_parser`、`cover_readers`、`server.serve_cover`、`server.serve_cover_asset`、`server.serve_metadata_artwork`、`metadata_service._id3_apic_frame`、`metadata_service._download_artwork` 七个点全部接上，其中无鉴权的 `/upnp-cover` 与流式 `/metadata/artwork` 一并覆盖。新增或扩展 5 个测试文件共 32 个用例，16 处变异命中 15 处（1 处为等价变异并已论证）。
- [x] 2026-09-17：`metadata_assets` 里**历史行**仍可能是本轮拒绝入库的类型（最实际的是 `image/svg+xml`，本轮只收紧了写侧）。这类行在 `serve_metadata_artwork` 会 404，用户表现为「以前抓到过的专辑封面没了」。要么加一次启动期规范化（用像素重写 `mime`，判不出来就把该行标为不可用并交给既有裁剪回收），要么先证明现网缓存里不存在这类行再做。别直接把 404 换成 `image/jpeg` 兜底，那是把一个可预料的失败换成一个更难查的坏图。  **R93 关闭（前提证伪，但另有一个真缺陷被这轮修掉）**：这条说「历史行的 mime 是 image/svg+xml 时在 `serve_metadata_artwork` 会 404，表现为以前抓到过的封面没了」。实测不成立：`server.py:1807-1808` 读 32 字节前缀后调 `safe_image_media_type(asset['mime'], prefix)`，而 `cover_media_type.py:113-119` 的次序是**字节优先**（sniff 命中就用 sniff 结果 ✓ 只有字节认不出来时才回落到白名单内的声明 ✓ 而开头是 `<`/`{`/`[` 的载荷一律拒 ✓），所以「声明撒谎、字节是真好的」历史行照常出图，这条已经被 `test_cover_media_type.py:115`（声明 svg + GIF 字节 → image/gif ✓）钉住，本轮不重复立案。但顺着查出一个真问题：`metadata_service.artwork()` 原来对任何「文件能打开」的行都执行 `UPDATE ... last_accessed=now`（旧 :4579 ✓），而 HTTP 路由 (:1771 ✓ 唯一生产调用方 ✓) 恰恰是在这之后才拒的；回收又是按 `ORDER BY last_accessed ASC, fetched_at ASC` 选牺牲者（:4087 ✓），结果是**永久不可服务的行被每次命中续到队列最尾**，与这条期望的「标为不可用并交给既有裁剪回收」正好相反。改法（:4569-4582）：先用同一份 `safe_image_media_type` 判出可服务类型，判不出来直接返回 None 且不刷新 `last_accessed`；判得出来才记账，并把**由字节决定的类型**返回给调用方（不修改历史行本身）。测试 `test_an_unservable_asset_is_not_renewed_in_the_eviction_queue`：同一行先装 SVG 再装 PNG，前者必须 None 且 `last_accessed` 保持 123、`mime` 保持 image/jpeg，后者必须返回 image/png 且 `last_accessed` > 123、且读路径不许回写历史行。变异 6 例（控制组 233 条先绿 ✓）全部由这条新测试杀死：Q1 不拒（还原改前）、Q2 拒但照样续期、Q3 过度纠正成从不续期、Q4 只信声明不信字节、Q5 判出类型却仍回传存库值、Q6 顺手 UPDATE 历史行。注：这条改动把「404 行何时被回收」变成可离线钉住的语义，不需要真机；而 SVG 本身该不该被渲染成位图救回属于产品口径，未动。
- [x] 2026-09-17：sniffer 内部的读取窗口是**内存上界而非行为**（变异 M06 论证为等价变异：全部魔数检查落在前 12 字节内）。若以后要让它可被测试约束，正确做法是把前缀长度做成显式注入参数并断言其被使用，而不是加计时断言；当前判定认为不值得，先记着。  **R93 关闭（诉求实测已满足，零代码改动）**：这条要求「若要让读取窗口可被测试约束，正确做法是把前缀长度做成显式注入参数并断言其被使用，而不是加计时断言」。现状：`cover_media_type.py:17` 已是命名常量 `SNIFF_PREFIX_BYTES=32`，在 `:59`（文档开头判定）与 `:67`（魔数嗅探）两处被真正使用；而 `test_cover_media_type.py:73` 已经在断言这个窗口是**行为**而不是内存上界——它把 JPEG 魔数放到 `SNIFF_PREFIX_BYTES + 1` 字节之后并断言不再被认成 JPEG ✓（:53 另钉了下界 12 ≤ 窗口 ✓ 保证 R52 那次「全部魔数在前 12 字节」的观察仍被约束）。所以这条要的注入参数与「断言其被使用」都已存在，变异 M06 当年的等价判定也不再是唯一证据；关闭，不新立项。
- [x] 2026-09-17：`read_flac_cover()` 在 PICTURE 块**字段本身畸形**（MIME 长度、描述长度、图像长度越界）时仍是整体返回 `(None, None)` 而非继续走下一个块，与「描述不了的图继续找」是两种口径。真实标签器偶尔会写出前者的畸形块，值得单独核实后再统一，属于封面可用性优化，不是本轮的安全面。  **R92 关闭（口径统一了，但顺序与我一开始以为的相反，先把这条记清楚）**：先说结论：`read_flac_cover()` 对「块内字段自己撒谎」的四种情况（MIME 长度、描述长度、图像长度越界，以及长度大到 4e9）原来是 `return None, None` 直接终止整次扫描，与函数自己 docstring 的「跳过并继续找下一个块」矛盾；本轮把这四支校验收进新的 `_picture_block()`，返回 None 表示「跳过这一块」，扫描继续 ✓ 测试 `test_flac_cover_reader_survives_picture_fields_that_lie_about_their_size`：坏块 + 好块必须拿到好块（四种坏法各一遍），只有坏块时必须返回 `(None, None)` 而不是崩溃或返回垃圾 ✓ 判别性：变异矩阵把改前代码整段还原（P1）被新测试杀死（138 条里 4 条失败 ✓），所以「改前不满足这条承诺」是量出来的而不是推的 ✓ 另外 P3（去掉 `MAX_COVER_FILE_BYTES` 那一项）也被杀——这一支对「块长度诚实、图像声明超过共享封面预算」的情形才是可达的，测试用 `mock.patch` 把预算压到 4 字节来证明它真的被使用，而不是构造 8 MB 夹具 ✓ P4（声明的 MIME 与字节不符时改信声明）由既有 `test_flac_cover_reader_continues_past_an_unusable_picture` 与 `..._type_comes_from_the_picture_not_the_declaration` 杀死，本轮不冒领 ✓ **要更正一件事**：条目原话还暗示过偏移可能有问题，我一开始也按「MIME 长度在前、picture type 是 8 位」的记忆去改偏移，还写了七个探针「证明」连规范正确的块都读不出来。那是**两个错误叠出来的假结论**：(a) 探针里块号是拿首字节推的，`00 00 00 0a` 开头被我写成类型 0，七个探针其实全是 STREAMINFO ✓ (b) FLAC 的 picture type 是 `u(32)` 而且**排在 MIME 长度之前**（RFC 9639 §8.8 的字段表原文：u(32) picture type / u(32) media type length / media type / u(32) description length / ... ✓ 抓下来存在 `%TEMP%\rfc9639.txt` 后按节取，225759 字不进上下文 ✓）。既有实现的 `data[4:8]` 一直是对的，仓库里的夹具 `flac_picture_block` 也是对的，我的改动会让两条既有测试立刻红（实测 31 条里 2 failures ✓ 正是这两条 ✓），已全部回滚，只保留「跳过而不是终止」这一处真缺陷 ✓ 教训记进 PROJECT_CONTEXT：一次测量同时否定实现和测试时，先怀疑测量 ✓
- [x] 2026-09-17：首屏那条「200 但 body 读不出来 = 空列表」的缺陷已修（见顶部同日期结论）：`response_json_loader` 现在回报 `bodyStatus`（parsed/empty/oversize/undecodable，默认不可用以免伪装成功）并导出 `usableBody`；`fetchJsonChecked` 增加第四参数 `options`，只有 `fetchLibraryResponse` 以 `strictBody: true` 调用，坏 body 从此抛 `ResponseError` 且不会写进曲库响应缓存。空 body（204 与无内容 200）三条宿主路径都仍是良性 `empty`。新增断言 19 处与 3 处，十三处变异全部命中。
- [x] 2026-09-17：`app.js` 的行为只能靠源码正则约束（`test_ui_library_loading.js` 那种），本轮就有两处变异（把 `strictBody &&` 门去掉、把 `options?.strictBody === true` 改成 `!== false`）只能靠正则文本命中而不是真实执行。要么给 `fetchJsonChecked` 这一小段做一个能在 vm 沙箱里跑起来的最小外壳（像 `test_ui_response_json_loader.js` 那样自带 stub fetch），要么继续把判定从 app.js 里拆成独立模块；前者更省事，也是本轮没有新增 UI 脚本文件的原因（安卓打包要求 index.html 声明的每个脚本都被内联）。  **R108 关闭（走这条给的第一个选项：补最小 vm 外壳；不新增 UI 脚本）**：本轮在 `test_ui_library_loading.js`（现 1125 行 ✓ 新增块自 L747 起）里搭出这条要求的外壳：`appSlice(startText, endText, label)` 用 `indexOf` 从磁盘上的真实 `app.js`（8250 行）按函数名切出被测函数体 ✓ 与 `response_json_loader.js`（222 行）源码一起送进 `vm.runInNewContext` ✓ 宿主按需注入 `JSON/Object/Array/String/Promise/Uint8Array/ArrayBuffer/TextDecoder/TextEncoder/AbortController/setTimeout/clearTimeout` ✓ 假 fetch 与假 DOM 只记录调用序列与写入次数。判别面变成真实执行：strict/non-strict × oversize/undecodable/empty 六种组合 + `validateRestoredPlaybackTarget`/`loadDevices`/`saveUserStateNow` 三个真实调用点的返回值与写入序列 ✓ 另有源码级接线钉（`fnAudioResponseJsonLoader.read(` 16 处 ✓ `parsedBody(result.bodyStatus)` 3 处 ✓ `usableBody?.(result.bodyStatus)` 1 处）。这条点名的两处变异现在都不只靠正则：M1（去掉 `strictBody &&`）与 M2（`=== true` 改成 `!== false`）在旧正则（同文件 L544）在场时由它杀死 ✓ 把那条正则删掉后控制组仍绿（旧状态下确实「只有正则能拦」✓ 这条前提本轮被证伪）✓ 而 M1b/M2b 分别由「非 strict 的超限体必须保持旧契约、不得抛」与「strict 读的超限体不得静默 resolve」两条行为断言杀死 ⇒ 正则已不是唯一防线。这条给的第二路（继续把判定拆成独立模块）本轮不走：安卓打包要求 `index.html` 声明的每个脚本都被内联 ✓ 新增 UI 脚本会扩大打包面 ✓ 而本轮判定本来就挂在既有 loader 上。仓库外副本 `C:\path\to\fnAudio_r108_cp` 控制组 69 个 JS 测试文件全绿 ✓ 变异 M1–M8 全部命中 ✓ 未新增 Python 测试 ✓ 新立 0 条。

- [x] 2026-09-17：`status` 这个 out 参数目前是 `parseBoundedJson` 的第五个位置参数，调用点靠顺序传参。再加结局种类时优先考虑把它和 `setCancel` 一起收进一个上下文对象（或让 `parseBoundedJson` 直接返回 `{data, status}`），免得位置参数继续变长而漏传的那个默认成 `undecodable`，表现为「明明解析成功却报响应体不完整」这种难查的失败。  **R109 关闭（选这条给的第二个方案：让 parseBoundedJson 直接返回 {data, status}；不再引入上下文对象）**：位置参数停在 4 个（response / fallback / maximum / setCancel）✓ 每次返回都把「数据 + 结局」绑成同一个值 ✓ 全文件 15 个出口一律走 outcome(...) ✓ status.value 与预置盒子的字面量现在都是 0 处 ✓ 唯一调用点 read() 用 outcome.data / outcome.status 具名取用 ⇒ 「漏传一个位置」在形状上不再可能。第一个方案（把 status 与 setCancel 收进上下文对象）本轮不走：它仍留着一个位置参数，而这条点名的失效恰恰是「默认值就是它的失败模式」，返回对象把默认值和结果合成一个值，比换包装更彻底。判别测试（test_ui_response_json_loader.js 现 597 行）：12 种传输形状上的 data⇄status 一致性环（把 bodyStatus 是否算可信文档与 data 是否还是 fallback 逐形状对比 ✓ 同时钉住 4 份可信文档 / 8 次拒绝两个计数，免得过宽而空转）+ 三处结构钉（参数表恰 4 位 ✓ 不得残留 out 参盒子 ✓ parseBoundedJson( 恰 2 处即声明加唯一调用点）。变异归因（在本轮最终字节上逐条跑整个测试文件；仓库外副本 C:\path\to\fnAudio_r109_cp）：让 !response 分支带 parsed 状态回传 fallback —— 只被新的一致性环杀死（失败落在新块内 ⇒ 新断言是唯一杀手）✓ 重新加回第五个位置参数 —— 只被新的参数表钉杀死 ✓ 把默认 status 预置成 parsed —— 由既有断言杀死（该文件 :470）✓ 进函数即快照 status —— 既有 :409 ✓ 在 read() 里从 data 反推 status —— 既有 :416 ✓ 删掉流式超限分类 —— 既有 :416。对外行为不变：app.js 一行未改（sha 0D263282FC28B88468E2804BD3259000A9FDF767D811DB15B0BF3110BC013B71）✓ 69 个 JS 测试文件全绿。新立 0 条。

- [x] 2026-09-17：`src/app/ui/response_json_loader.js` 两处可离线验证的修复：(1) 流式分块的字节视图判定从 `instanceof Uint8Array` 改成 `ArrayBuffer.isView`，消除跨 realm 宿主下整页静默变空列表的失效，并顺带接受 DataView 分块、把非视图分块稳定在 `fallback` 而不是抛出；(2) 只有 `text()` 可用的宿主不再为测量长度而整份重编码，用「一码元 1 到 3 字节」的上下界把测量收窄到真正的模糊带（204KB 0.26ms 到 0.13ms、1MB 0.85ms 到 0.41ms；4MB 档由码元下界早退）。新增 7 段检查、九处变异全部命中。两条不改的结论（取消后迟到的拒绝不可观察、`json()` 退路仍不受预算约束）与一条新缺陷候选（200 但 body 读不出来会被当成空页并写进响应缓存）都记在同日期顶部。
- [x] 2026-09-17：让「响应体读不出来」与「这一页真的是空的」在调用方可区分（见顶部同日结论）。落点大概是 `response_json_loader` 给超限/不可解析的 body 一个可辨的失败信号，`fetchJsonChecked` 在 `response.ok` 却拿不到可用 JSON 时抛 `fallbackMessage`，同时保持 204/空 body 这类良性情况不报错。改之前先枚举一遍各端点实际返回体，否则会把反向代理之外的正常空响应变成错误屏。  **R108 关闭**：这条要求的三件事都落地了。(1) 可辨失败信号：`response_json_loader.js:43` 新增并导出 `parsedBody(status)`（`:221` = `{read, usableBody, parsedBody}`）✓ 把五种结局（`parsed`/`empty`/`oversize`/`undecodable`/`cancelled` ✓ 默认 `undecodable` 见 `:196`）分成「只是有响应」与「是一份可信文档」两档 ✓ `empty` 在 `usableBody`（`:31`）里仍然可用（宿主答「没有内容」不是传输失败）✓ 但在 `parsedBody` 里不可信（文档读取方不能把「没拿到内容」当成「内容是空的」）✓ 这道口径写进 `PROJECT_CONTEXT.md` 顶块。(2) `response.ok` 却拿不到可信 JSON 时不再走成功分支：门推进到三个真实文档读取点 —— `app.js:1259 saveUserStateNow`（这是 `apiFetch` POST 站点 ✓ 200 坏体从此不清 `userStateDirty` ✓ 改判 `retryDelay = 2000` ✓ 即这条担心的「静默丢弃保存」的真实形态）✓ `app.js:6204 validateRestoredPlaybackTarget`（读不出的设备列表 = 无信息 ✓ 返回 true ✓ 不会把一个仍在播放的投送目标收回本地）✓ `app.js:6315 loadDevices`（抛 `设备列表读取失败` 走既有错误画法 ✓ 不再用 `data ||` 把「读不出来」画成「一个设备都没有」）；`fetchJsonChecked` 的 strict 抛 `fallbackMessage` 早已落实 ✓ 本条补的是其余文档读取方。(3) 改前枚举（这条明确要求）：`app.js` 共 16 处 `fnAudioResponseJsonLoader.read(` ✓ 分属 16 个不同函数（`fetchJsonChecked`/`fetchJsonResponseBounded`/`readResponseJsonBounded`/`saveUserStateNow`/`loadServerUserState`/`refreshServerUserState`/`refreshRendererSession`/`refreshRemoteStatus`/`updateCurrentTranscodeStatus`/`fetchMetadataRequest`/`validateRestoredPlaybackTarget`/`loadDevices`/`loadMetadataStatus`/`loadDlnaDiagnostics`/`fetchMetadataProjectionStatus`/`refreshLibraryStatus`）✓ 其中 3 处本轮加门 ✓ 其余 13 处逐站读到函数尾：0 处从坏体分支驱动 `apiFetch(`/POST/DELETE ✓ 出现的 `state.X = null` 全是 controller/promise 记账（`rendererRequestController`/`remoteStatusController`/`transcodeStatusController`/`deviceLoadController`/`libraryStatusPromise` + `libraryStatusController`）✓ 它们是读-即-画或自愈轮询（`refreshLibraryStatus` 在 `:7585-7589` 直接 `if (!data) return` ✓ 下一轮 poll 自愈）✓ 三个通用 helper 把 `data ||` 透传给调用方 ⇒ 一刀切抛错会把一次网络抖动变成错误屏 ✓ 与这条要的「保持良性空响应不报错」相反 ✓ 所以只加三处。`strictBody: true` 全文仍只 1 处（`app.js:5290` 库列表的 `fetchJson` 回调）✓ 该事实由接线钉守住。服务端侧证据：`send_json`（`server.py:719`）恒设 `Content-Length = len(body)`（`:734`）并写出（`:736-739` ✓ HEAD 除外）✓ 全仓 `Content-Length: 0` 实测三处 —— `server.py:1284`（DLNA SUBSCRIBE 应答）✓ `server.py:1914`（`serve_file_range` 零字节文件）✓ `server.py:1928`（416 应答）—— 均不是 `/api/` JSON 端点 ⇒ 「反向代理之外的正常空响应会被变成错误屏」这个前提在本网关上不成立（上一轮交接把 `:1284` 记成唯一一处 ✓ 本轮纠正为三处 ✓ 结论不变）。`loadServerUserState` 的良性判定不收回：`revision=0` 是真实前置条件（`state_store.py:337-339`：`expected_revision is not None and != current_revision` ⇒ `StateConflict`）✓ 409 应答带权威 state（`server.py:1336-1346`）且 `saveUserStateNow:1252` 已合并 ✓ 最坏一次额外往返。测试：`test_ui_response_json_loader.js`（540 行）加 taxonomy 与「两闸只在 `empty` 处分歧」断言 ✓ `test_ui_library_loading.js` 五组断言 + 接线钉；夹具口径注记：vm 内造的对象带 vm 原型 ✓ 宿主 `assert.deepEqual(x, {})` 会假失败 ✓ 改断 `Object.keys(x).length === 0`（同文件 L848 已写明原因）✓ 这不是代码缺陷。新立 0 条 ✓ 未新增 Python 测试。

- [x] 2026-09-17：`library_response_loader.safeInflightLimit` 对 `""`、`" "`、`[]` 这类输入经 `Number()` 得到 0，而 0 表示**并发上限为零**、每个曲库请求都被拒；真实宿主永远走默认 32，但任何把该值接到设置或查询参数上的改动都会立刻踩到。要么把 0 也归入「无效即回落默认」，要么显式区分「禁用」与「未设置」，别留隐式耦合。  **R98 关闭**：这条写了两个选项 ✓ 选一个即可 ✓ 取证后第一条**不可用**：`src/tests/test_ui_library_response_loader.js:152-155` 与 :156-159 已经把「显式 `0`（数字）与 `"0"`（文本）= 没有预算」钉成契约 ✓ 所以「把 0 也归入无效即回落默认」会直接推翻既有决定 ✓ （我第一版就是这么写的 ✓ 是套件把它打回去的 ✓ 变异 Z3 就是那一版 ✓）✓ 于是走第二条：区分「意外塌到 0」与「有人打了 0 ✓」落点 `library_response_loader.js:7-19`：新增 `typeof value === "object"` 回落（`Number([])` 与 `Number([[]])` 都是 0 ✓ 但没人配置过任何值 ✓）与 `numeric < 0` 回落（原先 `Math.max(0, Math.floor(-5))` = 0 ✓ 让一个越界输入静默继承「禁用」✓ 负小数同理 ✓）✓ 空串那条（`""`/`"   "`/制表与换行组合）本来就在 ✓ 保留原位 ✓ 且必须留在数字转换之前 ✓ 变异 Z4 就是把它删掉的那版 ✓ 被既有的 blank 契约杀死 ✓ 判别面：新增断言 8 个退化取值（`[]`/`[[]]`/`-5`/`-0.5`/`"-7"`/空串/`null`/`true` ✓ 每个都要求在**已有一个在飞请求**的前提下仍然放行一次 ✓ `active: {value: 1}` 是刻意的 ✓ 它把「回落默认」与「退化成 1」分开 ✓ 变异 Z6 把默认改成 1 ✓ 就是被这条断言杀死的 ✓）✓ 另加一条重申「显式 0 仍禁用」的断言 ✓ 保证这道分界不会在后续被顺手抹平 ✓ 变异 8 例（控制组绿 ✓）：Z1 去掉对象回落 ✓ Z2 去掉负数回落 ✓ Z3 我的第一版（所有 0 都回落 ✓ 推翻契约 ✓）✓ Z4 删掉空串规则 ✓ Z5 去掉上限钳制 ✓ Z6 默认值改成 1 ✓ Z7 上限常数改成 64 ✓ Z8 非有限值不再回落 ✓ 全部由套件杀死 ✓ 其中 Z5-Z8 其实早被既有断言覆盖 ✓ 本轮新增的净增量是 Z1/Z2 与那条重申 ✓ 记清楚不冒领 ✓ 本轮未新增 Python 测试 ✓ 新增断言在 JS 侧 ✓ 门禁 Python 项数不变 ✓

- [x] 2026-09-17：组/目录浏览游标（原 `library_browse_cursor_policy.browse_cursor_where` 生成的 ((A > ?) OR ((A = ?) AND (tie > ?)))）已换成两条单比较谓词 + 共享 limit+1 预算，三个调用点（归组专辑页/普通组页/folders）一起切换，线上格式仍为 v: 1。100k 专辑端到端：升序 4.59/6.14/9.70/13.91ms 到 4.33/5.00/4.88/4.75ms，降序 4.37/5.88/10.68/16.33ms 到 4.64/4.66/4.58/6.12ms，计划由 SCAN 变 SEARCH。行值单语句实测仍 SCAN（2.28ms）故不采用。回归 4+1 项、benchmark 两向硬断言、十一处变异全部命中。
- [x] 2026-09-17：`tools/benchmark_large_library.py` 的合成曲库永远是 2000 张专辑（不随 tracks 增长），而浏览游标的收益只在组数上万时可见：同一份 benchmark 里旧 OR 与新形状差不过噪声（八组实测 2.05-2.63ms 全重叠）。要么给 benchmark 加一段「宽组形态」（albums 与 tracks 同量级），要么把 100k 专辑那组证据固定成一个可重跑的脚本，否则下一轮无法靠门禁判断这条链路有没有退化。  **R97 关闭**：这条给的两个选项中选了第一个（给基准加宽组形态 ✓ 而不是另造一个固定证据脚本 ✓ 因为固定脚本等于又一份要维护的夹具 ✓）。落点是 `ALBUMS_PER_TRACK = 8` → `group_cardinality(track_count) = track_count // 8` ✓ 2500 → 312 组 ✓ 100k → 12500 组 ✓ 1M → 125000 组 ✓ 正好跨进这条说的「组数上万」区间 ✓ 每组 8 轨也是真实片库的量级 ✓ 派生影响全部改完并对齐：`album_tail_offset` 与基准自身的 `albums[count] != ...` / `albums_tail[count] != ...` 三处硬编码 2000 改为调用同一个函数 ✓ 测试里 6 处字面 2000 改成新形状的字面值（312 ✓ 尾偏移 192 ✓ 组游标 desc offset 192 ✓）✓ 有一处断言原本假设「游标续页一定满 120 行」✓ 在新形状下 312-240 只有 72 行 ✓ 改成按窗口算（这是我自己写测试时的口径错误 ✓ 不是代码缺陷 ✓）✓ 新增机检 `test_benchmark_fixture_scales_with_the_library` 断言形状函数本身的规模关系（三档取值 + 两个下限 ✓ 变异 Y1 把函数退回恒定 2000 ✓ 直接被杀 ✓）✓ 另变异 Y6 把 `siblings` 写成常量 62 ✓ 也被兄弟数断言杀死 ✓ 这一例是专门用来防止「形状退回小目录」的 ✓
- [x] 2026-09-17：albums 的两条排序索引是浏览页索引里最贵的一条（100k 专辑实测约 6.7 MB / 索引文件 +3.6%）。如果后续把组表总数改成持久化计数并把浏览改成前缀 seek，需要一并复核这八条索引是否都还在被计划使用：SQLite 不会告诉你哪条索引从来没被用过，删之前要用 EXPLAIN QUERY PLAN 逐方向验一遍。  **R117 关闭注记（逐方向 EXPLAIN QUERY PLAN 归属矩阵 + 逐条字节成本，结论：八条全活、一条都不能删）**：① 取证方法——本项目不做 ANALYZE、也不发 PRAGMA optimize（全仓 grep 证实），所以计划稳定可复现；小库（5 组 × 4 表，页边界切在 Alpha/alpha 大小写簇之后，让续页两条语句都执行）跑真实 query_library_groups()，用连接 trace 回调抓语句再逐条 EXPLAIN QUERY PLAN。② 归属矩阵（albums/artists/composers/genres 四张组表同形）：首屏与翻页页读 ORDER BY nocase ASC 只点 idx_*_name_nocase_asc、DESC 只点 idx_*_name_nocase_desc；游标续页第一条（组内尾，谓词 name = ? AND tie > ?，故意与 sort_dir 无关）**两个方向都点 _desc**，因为次键恒为 name ASC；游标续页第二条（后续组范围 name COLLATE NOCASE >|< ?）ASC 点 _asc、DESC 点 _desc。另两条路径不在这八条的归属表里，也必须一起钉住才不会误判：带搜索的 JOIN 页用主键 autoindex 点查组表、owner 过滤 albums 干脆不读组表（走 idx_tracks_artist/composer），两者的 ORDER BY 都在命中集上做 TEMP B-TREE，规模由命中数而不是曲库规模决定。少掉最后这一格，下一轮很容易以为「搜索页也靠这八条」而把只被两格点名的 _asc 当冗余删掉。八条都至少被一条真实路径点名 ⇒ 无死索引。③ 成本复核：条目原话「100k 专辑约 6.7 MB」在本方法学下对应单表两条 6.19 MB（同一量级，差额由组名长度解释）；逐条独立差分给出每条 +3,244,032 B = 3.094 MB = 32.4 B/组（100k 组、平均 20 字节组名），八条数值完全一致；换成 10.8 字节短名则每条 +2.289 MB = 24.0 B/组。同时更正 R116 记的测法：DROP 全部→VACUUM→逐条 CREATE→VACUUM 的**累计**差分有系统性伪差（同一条索引作为第一条测得 3.09 MB、作为后续条测得 4.41 MB，两遍反向复跑完全一致），因为 VACUUM 会重排已存在对象的页；只有「每条一个独立副本对同一基线做差」才给可复现值。R116 记的「+6.5 MB / 两条组索引」是配对总额，仍然成立，被更正的只是它的逐条拆分。④ 判别层：src/tests/test_library_sqlite.py L1266 新增 test_every_group_ordering_index_is_named_by_a_real_browse_path（四张组表 × 首屏 asc/desc + 续页 tail/next asc/desc + searched 页 + owner 过滤，外加「八条索引名字仍在 sqlite_master 里」与「被点名集合必须等于全八条」两条闭合断言，任何一条路径的点名索引不符合矩阵、或该语句出现 TEMP B-TREE，当场变红）。⑤ 变异证明：仓库外副本里逐条摘掉八条索引（V1～V8）与把 albums 索引的 COLLATE NOCASE 摘掉（V10）都由这条新测试点名杀死，既有 test_group_tables_carry_case_insensitive_ordering_indexes、test_browse_cursor_continuations_keep_their_index_seek_plan、test_benchmark_enforces_bounded_sqlite_pagination 同时兜住。
- [x] 2026-09-17：`metadata_unavailable_policy` 的封面分支是死代码（item_json 从不含 artwork 字段，见顶部同日期结论）。真正的修法是把作品图 id 从 `metadata_tracks` 一路带到 `prepare_track_persistence` 写进 item_json，并同步收紧 `has_local_artwork`；在那之前不要给投影补假字段，也不要删这支分支（删了会连带改掉三支本地曲库投影的对外形状）。  **R107 关闭（修法被否决 ✓ 定性被推翻 ✓ 零生产代码改动）**：这条的三个断言分别处理 —— ①「`item_json` 从不含 artwork 字段」的**载体**理由错了：`prepare_track_persistence` 无键白名单 ✓ 复制进去能落盘（新用例就是钉这点）✓ 不含它只是扫描器生产者事实 ✓ 该定性已被 R106 推翻；②「真正的修法是把作品图 id 带进 `item_json`」实测**否决**：`has_local_artwork` 的三个排队判点（`metadata_service.py:3678 / 4480 / 4553`）读的就是这份 `item_json` ✓ 副本一落库就把「权威行现在是否有效」压成「历史上复制过一次」✓ provider 改名 / 作品行回收 / 缓存过期三条自愈路全部静音 ✓ `test_persisted_copy_suppresses_the_lane_without_an_authoritative_row` 是这条反例；③「同步收紧 `has_local_artwork`」这半边**不可达**：三个判点已在同一连接内先读权威 artwork ✓ 收紧只会混淆「已确认 artwork」与「文件自带封面」。「不要给投影补假字段、也不要删这支分支」的告诫仍然成立 ✓ 那支分支一行未动。详见顶部 R107 记录。
- [ ] 2026-09-17：`src/app/ui/app.js` 剩余约 92% 符号仍是浅读面（381 个符号里深读过 31 个）。已通读且判定无缺陷的段落已在顶部记录：快照键与读写复核、行渲染、keyed 复用、标记复用与响应合并、分页 worker 重入。下一段候选是从「当前播放曲目的封面与进度」开始，它是唯一会边听边改 DOM 的路径。
- [x] 2026-09-17：组浏览（albums/artists/composers/genres）无过滤分页改成「有序索引页 + 单独 COUNT」，并给四张组表补 8 条 name COLLATE NOCASE 排序索引。100k 专辑单页：升序 53.32ms 到 5.02ms、降序 97.23ms 到 4.98ms、深页 117.31ms 到 5.45ms；20k 艺术家 10.14/16.01ms 到 2.84/2.78ms。EXPLAIN 全部 SCAN USING INDEX idx_*_name_nocase_asc/desc，无 TEMP B-TREE。新增 library_pagination.counted_page_rows（页先计数后、隔离语义与窗口版一致、只捕数据库异常）。回归 3 + 1 项，八组 benchmark 硬断言，十五处变异全部命中。
- [x] 2026-09-17：记一条查过但不改的结论：目录浏览（folders）与按艺术家归组的专辑页**继续**用 COUNT(*) OVER()。前者按 (root, parent) 已经收窄，800/5000 子目录实测窗口 1.894/1.844ms 优于「页面 + 单独 COUNT」的 3.9/3.5ms；后者的总数与页面共用同一个搜索/归组 CTE，拆开就要跑两遍。folders 的 name 排序索引与 COLLATE NOCASE 不匹配这件事在几百行的目录宽度上量不出来，暂不建索引。
- [x] 2026-09-17：组浏览页现在剩下的固定成本是那条 `SELECT COUNT(*) FROM <组表>`：100k 组实测 4.33ms，占修后单页 5.0ms 的八成，因为它仍要扫一遍主键覆盖索引。候选做法是把四张组表的行数写进 library_meta（与 track_count/dsd_count 同一口径），让总数变成一次主键命中。风险要一起处理：总数一旦漂小，客户端的 has_more 会提前判定读完、列表被截短，所以做的时候必须带一条自愈核对（读到的持久化计数与真实行数不一致就以真实值为准并回写），不能只加写入点。
- [x] 2026-09-17：browse/group 与 folder 游标（library_browse_cursor_policy.browse_cursor_where）仍在生成本项目已经禁止的 OR 形状 ((A > ?) OR ((A = ?) AND (tie > ?)))，且组页游标仍带页面 OFFSET。曲目 lane 上一轮已经换成两条有界索引 seek，这一支的前置条件（组表排序索引）本轮已经具备，下一轮可以做同样的改造并按同样口径留 EXPLAIN 与 benchmark 断言。（本条已完成：结论与实测见顶部同日期条目。）
- [x] 2026-09-17：上一轮读过的首屏前端链路（src/app/ui/app.js 的 librarySnapshotKey / restore|persist|scheduleLibraryPageSnapshot、renderTrackRows、commitTrackListHtml 的按键复用、reuseSnapshotTrackMarkup + fetchLibraryResponse 合并、loadPagedLibrary / loadPagedLibraryWorker、fetchAllTracksForCurrentView）未发现缺陷，结论要正式补记进变更文档，避免下轮重读：快照读写两侧都以 key === cacheKey 复核，标记复用只在页面集合与当前视图完全一致时启用，空帧闪烁已被 hasVisibleLibraryPresentation() 这道「已有可见行就不让骨架接管」的守卫挡住，loadPagedLibraryWorker 的递归回到同一根元素是有意设计且带 controller/seq 守卫。  **R112 关闭**：结论已正式补记进三份根文档，正文见本文件顶部同日期记录（逐条行号 + 五支既有 JS 回归套件名）✓ 复核未发现新缺陷 ⇒ 生产代码一行未改，也不为本条新增测试 ✓ 这条要的就是「下轮不必重读」。
- [x] 2026-09-17：歌词 base64 通道的预算修好三件事：kugou/joox 不再按字符数切刀（切片后仍能解码出一半乱码的短文档并被当成功写库，实测 5,240,000 字节文档→852,470 字符乱码尾前缀）、`decode_base64_lyrics` 改为先按编码长度拒绝（4,194,320 字符字段：旧 7,340,126 字节峰值分配/4.595ms，新 601 字节/0.011ms）、strip 守卫与解码值统一（带尾换行的字段以前整条判非法，现在正常返回）。新增 `MAX_PROVIDER_LYRICS_BASE64_CHARS`。回归 8 + 3 项，十五处变异全部命中。
- [x] 2026-09-17：`decode_base64_lyrics` 仍拒绝**内部**含空白的 base64（MIME 折行那种）。修法是先整串去空白再校验，代价是每个字段多一次 O(n) 拷贝；目前没有任何真机证据说明已配置通道会折行输出，所以先不动，等设备侧日志出现 `lyrics base64 payload is invalid` 再处理。  **R77 关闭（离线判定，不等真机日志）**：折行的 CRLF 不携带任何信息，而 `validate=True` 拒绝它等于把整条歌词丢掉；改成在预算检查之前删除六个 ASCII 空白字符（` \t\n\r\v\f`，不含 U+00A0/U+0085，避免把坏载荷洗成合法）。判别性测试三条在 `test_metadata_provider_response.py`（`_survives_mime_folding`、`_cannot_smuggle_payload_past_the_encoded_ceiling`、`test_only_ascii_whitespace_is_normalized_inside_a_base64_field`），仓库外变异 M1-M5 全部被指名杀死。本条原计划「等设备侧日志出现 `lyrics base64 payload is invalid` 再处理」，R77 判定这个前置不该等：代价只有一次 O(n) 拷贝，而等日志的期间每次日志本身就在丢歌词。
- [x] 2026-09-17：`_store_lyrics` 里对歌词文档的那道 `_provider_text(..., MAX_PROVIDER_LYRICS_BYTES)` 是**按字符**切刀，现在靠「上游已按字节限死」间接成立，属于隐式耦合。要收紧就把它换成显式的按字节复核（超限即整份拒绝而不是切），同时给 `MAX_PROVIDER_LYRICS_BYTES` 与磁盘/缓存层的实际字节上限做一次统一核账；存储层单独一轮。（R54 已按字节复核并把文档改名为 lyrics_document；跨层字节核账另立 2026-09-18 新条。）
- [x] 2026-09-17：游标续读换成两条有界索引 seek，组内 COUNT 与页面 OFFSET 一并去掉（`cursor_group_tail_where` + `cursor_next_group_where` + `library._cursor_page_rows` 共享 limit+1 预算，`cursor_where`/`cursor_tie_where`/`_cursor_tie_skip` 删除，新增 `cursor_page` 作为唯一采纳判定）。100k 单语句冷测：format 深度 12000 由 3.01ms 降到 1.44ms、深度 50000 由 2.89ms 降到 1.16ms、artist 深度 12000 由 0.23ms 降到 0.12ms、title 由 0.16ms 降到 0.09ms；整趟浏览器翻页（未打标 20000 行）升序 3.407s 到 3.076s、降序 3.324s 到 3.099s，上一轮那个升序多付 13% 的反向结果抹平，OFFSET 退回页 0、逐行与 OFFSET 等同。8 个排序组合的两条语句全部 SEARCH 覆盖索引。回归：游标策略 13 项 + 新增 `test_cursor_page_reads_two_ranges_without_counting_the_group`，十处变异全部命中。
- [x] 2026-09-17：游标页仍然固定付两次语句往返：当游标落在一个基数为 1 的键组里（`title` 排序、或标签几乎不重复的 `artist`），第一条读语句一次就把预算填满，第二条只在 `budget <= 0` 时才被跳过，遇到恰好读满 limit 行的情况会白跑一次空查询。离线单页这一跳是 0.09~0.12ms，暂不动；真机上若 SQLite 句柄存在 socket/pipe 级往返放大，再考虑用「第一条已返回 limit 行且已知游标是组内最后一行」直接短路，短路条件必须由索引元数据证明而不是靠猜。 〔R138 X11=A 裁定关闭：按「性能可接受」关闭。离线实测第二跳 0.09~0.12 ms；短路条件必须由索引元数据证明，目前无任何证据支持引入这层复杂度。真机 SQLite-over-socket 的往返放大属设备段既有长跑项的观测范围，本条不再单列。本轮不改代码。〕
- [x] 2026-09-17：组/目录浏览游标（`library_browse_cursor_policy.browse_cursor_where`）还是「前缀范围 + 页面 OFFSET」的老形状，本轮的两读改造没有覆盖它：它按 name 单键分组、组内并列键就是行本身，理论上同样能拆成「组内尾 + 后续组」两条。但下一轮真正的前置条件与本轮待办里那条缺索引的问题绑在一起（组表没有任何 name 排序索引、`folders` 的 name 是二进制排序与 COLLATE NOCASE 不匹配），在补索引之前改谓词形状测不出差别，所以顺序是先索引后形状。  **R117 关闭注记（前提与要求两半都已落实，缺的只是记录）**：① 条目点名的 browse_cursor_where 在两个服务端模块源码（library.py、library_browse_cursor_policy.py）**0 命中**；补上本轮那条禁止清单之后，src 树里唯一还保留这个字面量的文件就是清单自己，library_browse_cursor_policy.py 的 __all__ 现在只导出 encode/decode_browse_cursor、browse_cursor_page、browse_cursor_group_tail_where、browse_cursor_next_group_where；② 条目担心的「前缀范围 + 页面 OFFSET」老形状已经不在这条链路上：三个续页调用点（owner 过滤 albums、通用组页、folders）全部经 _browse_cursor_rows() 的两条单比较读，游标页在 query_library_groups() 里强制 offset=0，带非零 offset 的游标请求也读不出 OFFSET 语句；③ 条目写的「先索引后形状」的前置条件也已成立（八条组表索引在 library.py L2260-2267，本轮 L130 逐方向复核确认全部活着）；④ 判别层：形状半边早有 test_group_cursor_continuation_reads_two_single_comparison_selects 与 test_folder_cursor_continuation_reads_two_single_comparison_selects，计划半边有 R116 的 test_browse_cursor_continuations_keep_their_index_seek_plan，本轮补的是「旧符号不许回来 + 续页语句里不许再出现 OFFSET 或 OR」这半边：src/tests/test_library_sqlite.py L1407 新增 test_no_browse_continuation_falls_back_to_the_offset_scan_shape（四个组视图 × 两个方向 + folders × 两个方向，外加扫两个服务端模块的源码）。变异证明里 V11（将旧符号 browse_cursor_where 重新导出）只被这条新测试杀死，V12（把两读拼回一条 OR 读）与 V13（绕过游标分支退回 OFFSET 分页）由本轮两条新测试与既有测试共同杀死。
- [x] 2026-09-17：游标在**巨大键组内**要多扫一遍（本轮实测出来，未改动）：`cursor_tie_where()` 的组内 COUNT 与页面自身的 OFFSET 是同一批行的两次扫描，范围谓词只有在能裁掉前序键组时才省得到。降序的空键组能裁（省 24%），升序的空键组裁不掉（反而 +13%），`format` 这种只有几个键值的排序同理。候选修法是在组内改用行值谓词续读（`(title COLLATE NOCASE, id) > (?, ?)` 配合 `expr = ?`）去掉 COUNT，代价是组内不再 seek、且要与 R38 的「单个可 seek 范围谓词」不变量协调；动手前需要先在 100k 上量出各键组基数下的前后对照。（本轮已完成，做法与实测见顶部同日期记录：两条有界索引 seek 取代组内计数 + OFFSET，升序反向代价同时抹平。）
- [x] 2026-09-17：「`has_more: True` 但没有 `next_cursor`」两条路径的处理进展与残余（R112 改写，本条**继续开着**）：`id` 为空那一半已闭合 ✓ 锚点为 SQL NULL 那一半只闭合了「页尾是该键组末行」的情形。落点：`anchor_is_encodable()`（library_cursor_policy.py:54-65）+ `encode_track_cursor(..., inclusive)`（:68）写稀疏键 `"i":1` + `decode_track_cursor` 恒返回 `inclusive`（:119-125）+ 组尾谓词 `>=`/`>`（:166）+ `_continuation_anchor()`（library_page_result_policy.py:38-60）+ 两条 OFFSET 页路径改读 `limit + 1`（library.py:1252/:1257/:1268 与 :1364/:1369/:1380）。残余四类，全部实测：(a) 页尾落在**多行 NULL 块内部**时仍无 cursor——前瞻行自己也是 NULL，替换会跳掉整块余行，所以宁可退回 OFFSET（test_library_sqlite.py:797 钉住「走查是 OFFSET 走查的前缀」）；(b) **DESC** 下 NULL 块排在末尾，游标续读永远够不到那几行（行不丢，游标少行）——test_library_sqlite.py:814 专门钉住这条而不是假装它已修；(c) 跨版本 skew：新版 inclusive token 被旧版服务消费会**跳过一行**（本项目单进程部署，反方向「旧 token → 新服务」安全），若将来出现多版本共存需要给 token 加版本位；(d) OFFSET 页每页多读一行的代价，以及 NULL **主键**在 `expr = ?`、`(tie, id) > (?, ?)`、`expr > ?` 三种谓词下永不可达这一事实（inclusive 改变不了它，任何进一步收紧都要先解决「谓词无法表达 NULL」而不是继续加 flag）。要关本条得先决定 (a)(b) 是接受为口径并写进 docs，还是给 NULL 组另设可比较的哨兵键值（那才是真正的载荷格式变更）。〔R122 负责人裁定 A＋C＝两半都要，缺一不关本条：A＝把 (a)(b)(d) 三类残余写成 docs 口径（NULL 组内不可寻址、DESC 下末块游标短读、OFFSET 页每页多读一行是设计后果而非缺陷，四条既有判别测试继续钉住行为不许改口）；C＝从写路径消灭新的 NULL——入库时把可空标签字段的 None 归一为空串（与显示层对未分类已经做的合并同口径），并对旧库做一次性收敛迁移，使 (a)(b) 只在尚未跑过迁移的库里存在。反对「给 NULL 组另设可比较哨兵键值」的硬证据保留在条目正文：`library.py:1127-1135` 写明 COALESCE 表达式会让普通艺人、专辑、流派页整体失去 sargability。R121 真机取证（现网库 tracks 表 NULL 计数 0）说明 C 的成本在防回归与旧库收敛，不在救火。〔R125 实施完成并关闭（该条在 R122 登记裁定时位于 L150，本轮插入记录前实测在盘上为 L153）：A＋C 两半都落地，缺一不关本条的口径已兑现。A＝`docs/LIBRARY_CURSOR_NULL_GROUPS.md`（已在 `docs/INDEX.md:9` 登记）把残余 (a) NULL 组内不可寻址、(b) DESC 下末块游标短读、(d) OFFSET 页每页多读一行写成明文口径，并明令钉住行为的四条既有判别测试不得改口；C＝从写路径消灭新的 NULL：`src/app/server/library_write.py:41-53 collapse_missing_labels()`（八列契约 `:29-38`、理由与「哨兵键值会打掉 artist/album/genre 页 index seek」的硬证据 `:17-28`），只改「键存在且值为 None」，缺键继续按 `""` 落库，调用点 `:169` 在 `dumps` 之前，列与 `item_json` 不可能各说一套；旧库一次性收敛 `src/app/server/library.py:2485-2524 _collapse_null_labels()`（标记键 `:2482`，命中即 `:2514-2515` 早退，是迁移不是每轮清扫），调用点 `:2663` 排在组表/文件夹/搜索索引刷新之前。判别测试：`test_library_write.py:162/:184/:199` 与 `test_library_sqlite.py:853/:885`（后者用 `:746` 假库在 save 之后以裸 SQL 注入 NULL 验证收敛，并钉住「注入的 NULL 在标记之后不再被自动改写」）。残余 (a)(b) 的可寻址性本身仍未变——docs 写的是口径而不是修复，这一点在 `docs/LIBRARY_CURSOR_NULL_GROUPS.md` 里明说；(c) 跨版本 skew 仍按本条原文留作多版本共存前提下的未来变更。〕
- [x] 2026-09-17：`response_json_loader.js` 还剩两处已知但不值得盲改的边界。其一，只有 `json()` 的最后一级回退仍无消费前字节上限（只能靠 `Content-Length`），要不要收紧取决于真机上是否存在「包装宿主只暴露 `json()`」的实现，目前无证据。其二，`text()` 分支的精确字节测量要为**未超限**响应额外分配一次 `TextEncoder` 编码副本（约一倍体积），若日后它在低端 WebView 上成为可见开销，可改为只在 `arrayBuffer` 不可用时才走该分支，或对文本长度做分段编码。
- [x] 2026-09-17：修掉首屏单页将近一半时间花在打开数据库上：新增 `library_connection_pool.LibraryConnectionPool`（每库 4/全局 8 上限、LIFO、借用永不阻塞、按 `(st_dev, st_ino)` 校验身份），`library_db_connect()` 命中借用时跳过 PRAGMA 与 schema 前奏，写路径拆成永不入池的 `library_db_writer()`；20k 曲库冷首屏页 2.995ms→1.082ms（2.77 倍），100k 四份产物 5.13~5.95ms→3.03~3.45ms（1.49~1.96 倍），每页省 1.68~2.92ms。
- [x] 2026-09-17：给连接池补 25 项回归（池纯逻辑 13 + 曲库集成 10 + 关服排空顺序 1 + 健康投影 1），并让 `tools/benchmark_large_library.py` 新增 `first_screen_connection` 段与两条硬断言；十五处变异各自命中预期集合，还原后相关测试全绿；其中「把连接前奏挪到守卫之外」这一处踩掉的是本轮自己引入的回归，既有两条清理契约回归先把它抓了出来，另有一条新回归同时钉住只读与写入两条路径。
- [x] 2026-09-17：把池计数接入有界可观测面：`library_snapshot.library_component()` 新增 `connection_pool` 段，`/api/health` 与 `/api/diagnostics` 经 `library_connection_pool_status()` 上报，`shutdown_runtime()` 新增 `close_library_connections()` 排空步骤。
- [x] 2026-09-17：在新路径上重量首屏剩余固定开销：100k 池化冷页仍要 3.03~3.45ms，其中 `secure_directory` + 每次读一次的 `secure_sqlite_files`（POSIX 下对三个文件 chmod）、120 行 `item_json` 解码（上一轮实测 0.27ms）、缓存纪元两次 `os.stat` 各占多少还没在池化路径上拆开量过；先测占比再决定是把这些也做成连接级/周期级，权限刷新不能为了省时间被摘掉。〔R121 追加·门禁事故并入本条，不另立新项〕本轮换号重跑的 `artifacts/offline-20260920-round185.log` 唯一 error 正是本条要量的池化路径：`test_benchmark_enforces_bounded_sqlite_pagination` 在 `tools/benchmark_large_library.py:672` 抛 `RuntimeError: pooled library reads are not faster than reopening the index`（守卫在 :671-672；:653-662 用 `median_sample(..., samples=5)` 先跑 unpooled 段、再跑 pooled 段，属先后两段式的负载敏感比较；:669-670 的 `reuses`/`creations` 结构守卫通过）。同一份代码 round184 全绿用时 108.523s、round185 用时 144.808s，实测外来进程 PID 10196（python.exe，命令行无参数、1 线程、工作集 5.4 MB、150 句柄、创建于 2026-09-20 00:36:48、父进程 11784 已消失）累计 CPU 34616 秒、6 秒采样窗口内耗 6.03 秒 CPU 即稳定占满一核，`taskkill /PID 10196 /F` 后单跑该模块连绿两次（1.998s、1.952s）。实施本条时一并改掉这个测量形状：:653-662 改成配对交错的 A/B 采样，以 `reuses`/`creations` 结构计数为主判据、把「池化必须更快」的计时比较降级为辅助证据，并配判别测试与仓库外变异矩阵；若量出池化冷页确实不省时间，就按本条原判据决定连接级/周期化改造的取舍〔R128 实施完成并关闭：拆开量与实施一次做完。① 占比是量出来的：一次池化读的权限探测面 16 次系统调用（目录 4 ＋ sidecar 两趟各 6）→ 7 次（目录 1 ＋ 每趟 3），POSIX 稳态另省 7 次无条件 chmod；ABBA 配对计时 N=301、预热 200 轮，中位 0.0818 ms → 0.0383 ms，301/301 轮新路径全胜。② 本条原判据「先测占比再决定是把这些也做成连接级/周期级」的结论是**两个候选都不做**：`secure_sqlite_files` 与读入口的 `secure_directory` 保留全部 5+1 处调用，刷新频率一字未降（R120 的「池化不减弱加固」不变量：借来的句柄只证明 pragma，不证明别的进程没把库文件改成可读），只把每次的全量探测换成带 fallback 的 `secure_file_on_drift`/`secure_directory_on_drift`（lstat 失败、非普通文件、非目录、符号链接一律退回全量语义）；写路径 `library_db_writer`（library.py:2454）与 `save_library_cache`（:3004）保持全量 `secure_directory`。③ R121 并入的门禁事故一并改掉：first-screen 段改 `paired_ab_samples()` 逐轮 ABBA 配对、判据换成 `pooled_reuse_guard()` 的窗口内 reuses/creations 结构计数，「池化必须更快」的 raise 删除（非注释）并降级为 `pooled_faster_pairs` 报告字段，死码 `median_sample` 随之删除。判别测试与仓库外变异矩阵 V1~V8 全灭见本轮 L2 记录。〕
- [x] 2026-09-17：`library_connection_pool` 只是 `server.main()` 的引导默认值，既没进 `config.py` 的默认配置，也没有设置页开关或 `PROJECT_CONTEXT.md` 之外的文档说明。若将来对外暴露这个开关，关闭时必须顺手调用 `close_library_connections()`，否则会出现「配置说关掉了但池里仍有空闲句柄」的状态。（R111 已完成：默认值与「只认 JSON 布尔」的口径进了 config.py，运行期唯一生效入口是 server.commit_config_update()，关到 off 会顺手排空该配置指向的库的空闲句柄，说明文档 docs/LIBRARY_CONNECTION_POOL.md；设置页控件仍然没有做，它属于产品判断，已折进相邻那条设备项。）
- [x] 2026-09-17：修掉曲库游标分页深页退化——`cursor_where()` 改为单个可 seek 的范围谓词，组内已访问行改由新的 `cursor_tie_where()` 计数后作为页面 OFFSET 跳过（`library._cursor_tie_skip`）；100k 曲库深度 50119 实测 2.8~6.5ms → 0.07~0.09ms，并留下方案对照测量记录。
- [x] 2026-09-17：重写 `test_library_cursor_policy.py`（9 项：谓词形状、绑定计数、`sort=title` 忽略矛盾的 `p`、12 行内存表 × 12 个排序组合 × 每一行做游标的差分等价）并在 `test_library_sqlite.py` 新增单一巨大键组的游标/OFFSET 全程走查回归；五处变异各自命中，还原后相关 101 项全绿。
- [x] 2026-09-17：`tools/benchmark_large_library.py` 的 `cursor_pagination` 改成深度扫描（4 档深度 × title/artist），记录 `cursor_versus_offset` 并在最深档硬性要求游标不慢于 OFFSET；同轮拆开量得单页固定开销：冷页 2.67ms 中 `library_db_connect` 占 1.46ms。
- [x] 2026-09-17：首屏单页将近一半时间花在打开数据库上：实测冷页 2.67ms，其中 `library_db_connect`（`sqlite3.connect` + `PRAGMA busy_timeout`/`journal_mode=WAL`/`synchronous` + 两次 `secure_sqlite_files` + `_ensure_library_schema_once`）1.46ms，SQL 本体只约 0.08ms。候选方向按风险从低到高：把 `secure_sqlite_files` 从只读连接路径摘掉（每次读都 chmod 三个文件没有意义）、给 `_ensure_library_schema_once` 的「已就绪」判定换更便宜的键、以及按线程复用只读连接（需要同时回答 WAL 下读到旧快照与 `invalidate_library_query_cache` 的可见性边界）。要先测出各部分占比再动手，别把安全性当性能预算牺牲掉。（已完成：候选方向里「按线程复用只读连接」经实测排除——`BoundedThreadingHTTPServer` 每请求新建线程，线程局部缓存永不命中，且每个只读查询本来就只开一条连接；真正落地的是按文件身份复用的有界连接池 `library_connection_pool`，WAL 可见性边界由「归还前必须提交 + 扫描重建 schema 时丢弃句柄」两条守住，实测 20k 冷页 2.995ms→1.082ms、100k 5.13~5.95ms→3.03~3.45ms。）
- [x] 2026-09-17：空串主键不再让游标失效：`_primary()` 接受空串（未打标文件的 artist/album/format 索引值就是 `''`），标题改用允许空值的 `_optional_text()`，`id` 仍必须非空、NULL 主键仍不可编码，`v: 1` 未变。实测 100k 曲库、未打标 20000 行时降序整趟 4.385s→3.324s（-24%）、167 个 OFFSET 退回页归零、最慢页 15.2ms→9.2ms；6 趟走查与 OFFSET 逐行等同。代价也记了：升序 + 巨大空键组因范围谓词裁不掉任何行而多付一次组内计数，整趟 +13%（单页最坏值不变）。`tools/benchmark_large_library.py` 新增 `empty_key_group_pagination` 硬断言。
- [x] 2026-09-17：组/目录浏览游标拿不到索引 seek（本轮只测量、未改动）：`browse_cursor_where()` 形状已经正确，缺的是索引——组表没有任何 name 排序索引，`folders` 只有 `(root,parent,name)` 且 `name` 是二进制排序，与 `name COLLATE NOCASE` 不匹配。基数受目录与分组数量限制，暂缓；若将来要做，需同时给出组表 `(name COLLATE NOCASE, name)` 与 `folders(root,parent,name COLLATE NOCASE)` 两条索引并评估写放大。 ✓ R116 关闭注记：这条的前提已被后续轮次悄悄实现而条目本身一直没翻，属「要求已落实、缺的是证据层」。索引落点（按当前磁盘行号取证）：src/app/server/library.py L2260-2267 是 albums/artists/composers/genres 四张组表的 (name COLLATE NOCASE ASC 与 DESC, name ASC) 共八条；L2377-2384 是 root-scoped 的 idx_folders_root_parent_name_nocase_asc|desc (root, parent, name COLLATE NOCASE, path)；L2394-2401 是 parent-only 的 idx_folders_parent_name_nocase_asc|desc (parent, name COLLATE NOCASE, path)；L2402 把二进制排序的遗留 idx_folders_root_parent_name DROP 掉。写放大按要求评估过：100000 组 / 50000 同级目录 / page=120 的取证库里，体积 32.4 MB → 加两条组索引 38.9 MB（+6.5 MB，68 B/组）→ 再加四条目录索引 80.3 MB（+41.5 MB，869 B/目录），建索引 0.09 s / 0.29 s；本机 SQLite 3.50.4 没有 dbstat 模块，只能 DROP→VACUUM→CREATE→VACUUM 差分测量，不 VACUUM 会测成 +0.0 KB。计划形状两遍复跑形状一致：带索引时游标续页 18/18 条语句零 USE TEMP B-TREE，tail/next 落在 0.009~0.211 ms，普通页组表 3.771/3.910 ms、目录 root-scoped 6.112/5.963 ms、parent-only 6.361/4.921 ms；摘掉这六条索引后 18 条里 14 条退回 USE TEMP B-TREE FOR ORDER BY，慢到 group_page 43.4/91.8 ms、folder_page_ponly 48.3/150.2 ms、folder_next_ponly 14.3/35.4 ms，剩下 4 条走主键 autoindex 的（group_tail 2.593/2.621、folder_tail_root 10.674/10.567 ms，temp=0）也仍是带索引时的百倍。插入常数项两次探针不一致，按最坏值入档：20k 行 0.0023 → 0.0037 ms/行（+0.0014 ms/行，每 10 万行 +0.14 s），另一次为 +0.0004 ms/行。并列键探针：albums 里 TIE/Tie/tIE/tie 的权威序两个方向都是同一个升序，次键 name ASC 与浏览方向无关——这正是 tail 谓词故意忽略 sort_dir 的原因，也解释了 desc 浏览的 tail 计划为什么仍走 idx_albums_name_nocase_desc 而第二键是 ASC。本轮补上的唯一缺口是判别层：src/tests/test_library_sqlite.py L1142 新增 test_browse_cursor_continuations_keep_their_index_seek_plan（文件现 3275 行，12 个 subTest），把续页两条语句的 EXPLAIN QUERY PLAN 钉成「必须点名命中索引且零 TEMP B-TREE」。
- [x] 2026-09-17：修掉元数据恢复投影把整首歌词截成 512 字符（标签预算被误用到 `lyrics` 文档字段上），并补三条互不重叠的回归与三处变异验证。
- [x] 2026-09-17：`metadata_unavailable_policy` 的封面分支实际上是死的。三处投影读的是 `item["cover_url"] or item["cover_thumbnail_url"]`，但 `server.py` 喂进来的是 `find_library_item()` 返回的**原始** `item_json` 行，这两个键只由 `library_presentation.public_library_item()` 在分页响应时合成（`metadata_artwork_id` 同样只出现在 `metadata_service` 的页内覆盖里，不落库），所以注释承诺的「恢复期保留可用封面」永远拿不到值；现有夹具测试手工构造了带 `cover_url` 的 item，把这个缺口盖住了。修法要先定边界：让恢复投影接收已公开化的行（复用 `public_library_item` 的结果），还是在本模块内只承认 `metadata_artwork_id` 并复用纯函数 `metadata_artwork_policy.artwork_url`；后者需要给这个刻意保持轻依赖的模块新增一条导入。安排单独一轮。  **R106 关闭（复现证伪前提，非改码）**：「封面分支实际上是死的」不成立。`cover_url` / `cover_thumbnail_url` 确实不由扫描器写 ✓ 但 `find_library_item()` 返回的是 `item_json` 反序列化的**原始行** ✓ 而旧版 `library.json` 的行里就带这两个键并由 `load_library_cache` **无键白名单**地持久化 ⇒ 恢复期拿得到值（复现链同上一条）。原条目对「只由 `public_library_item()` 合成」的判断只对了前半 ✓ 漏掉了旧版缓存这个供体。方案一（改喂 `public_library_item` 的行）实测否决：该投影 `pop("lyrics")` 且把 cover **重写**成 `cover/legacy-1?v=0` 这类合成 URL（不是原值）✓ 还引入 `cover_is_known_missing` 的磁盘探测 ✓ 换进去会同时丢歌词与真封面。方案二（本模块只认 `metadata_artwork_id` 并复用 `metadata_artwork_policy.artwork_url`）否决：`item_json` 原始行里没有 `metadata_artwork_id` 键（它只出现在 `metadata_service` 的页内覆盖）✓ 只会把活分支换成第二个死分支。文档同步：`metadata_unavailable_policy.py` L23-39 的 caller-shape 审计注释按 2026-09-19 复现结论重写（扫描器闭集 / 旧版缓存才是供体 / enrich 非供体 / 冷启动嵌码仍须走有界本地读）。测试：`test_pending_projection_keeps_local_cover_without_tags` ✓ `test_cold_start_track_projection_reads_the_raw_library_row`（源码级接线断言：块内 `assertNotIn("elif not METADATA_SERVICE")` + `assertIn("else:")` + `local_item = find_library_item` 全文计数 5 + `assertNotIn("public_library_item")`）✓ `test_scanner_row_builders_never_supply_the_recovery_keys` ✓ `test_feeding_public_rows_would_lose_both_recovery_fields`；变异 M06 / M07 / M08 / M10 / M11 / M13 / M15 全部命中 ✓ 其中 M13 需成对摘除 `library_presentation.py` 第 76 行 skip-list 与 L105 pop 两道防线才具备判别力（单摘任一层是等价变异）。
- [x] 2026-09-17：修掉 `response_json_loader.js` 的三条缺陷：超时路径未接收 `reader.cancel()` 的拒绝（探针实测旧实现留下 unhandledRejection）、同一 reader 可被取消两次（旧 2 次 / 新 1 次，改为记忆化 `cancelReader()`）、非流回退用 UTF-16 码元数比对字节预算（CJK 夹具 18 码元 / 30 字节，旧实现在 19 字节预算下照单解析，新实现按精确字节拒绝而在 30 字节的界线上仍解析）；非流链改为 `arrayBuffer` 优先、`text` 走「码元下界早退 + `TextEncoder` 精测」，流式分支改增量解码去掉一次全量复制。Node 回归 3 到 9 项，VM 上下文补注入 `TextEncoder`。
- [x] 2026-09-17：`metadata_provider_response.decode_base64_lyrics()` 是先 `base64.b64decode` 再让 `decode_lyrics_text` 判长度，于是超限输入会先分配约 3/4 体积的解码缓冲才被丢弃（当前被 provider 响应 4 MiB 上限间接兜住，属于放大而非无界）；可在解码前按 base64 编码长度预算直接拒绝。另外 `metadata_service.qq_lyrics()` 取 `data.get("lyric")` 时没有像 joox 路径那样先过 `_provider_text(..., MAX_PROVIDER_LYRICS_BYTES)`，两条 provider 链路的输入约束不一致。  **R77 关闭（前半已被后来的改动满足，后半证伪为不是缺陷）**：预算现在就在解码之前检查——`metadata_provider_response.py:145`（函数在 :123）用编码长度 `(limit+2)//3*4` 直接拒绝，函数文档也写明了「先解码再判长度会先分配那块即将被丢弃的缓冲」；后半 `qq_lyrics()` 不过 `_provider_text` 也核对过：非字符串（dict/list/bytes）由 `decode_base64_lyrics` 的 `isinstance` 返回 `""`，体积由编码上限兜住，两条链路的最终约束一致，只是形状不同。因此以「证伪 + 写明结论」关闭，不改代码。
- [x] 2026-09-17：`library_response_loader.js` 信任「宿主 fetch 一定会因 abort 而 settle」：`clearLibraryResponseCaches()` 中止并清空在飞表后，槽位只能等各请求自己 settle 才释放；若某个 WebView 的 fetch 忽略 `signal`，`active.value` 会被永久占住，之后每次列表请求都直接 reject「concurrency limit reached」，首屏再也加载不出来。廉价修法是在检测到「已中止的在飞项」被取代时顺手调用它的 `__fnAudioRelease?.()`（该函数本身幂等）。需要先确认真机/老 WebView 上是否存在忽略 signal 的传输。
- [x] 2026-09-17：`test_library_sqlite.py` 的五入口回归 `test_sqlite_library_queries_fingerprint_the_database_once` 与重写后的 `test_library_query_adapter.py` 纪元回归落地，配合缓存层三条新测试，六处变异（栅栏/条目时间戳回到调用时刻、get 或 put 重取指纹、不传 `read_at`、单个调用点退回即时建纪元）各自只打中预期的测试。
- [x] 2026-09-17：曲库分页缓存的库文件指纹不再在读库前后各取一次——`library.py` 新增 `LibraryCacheEpoch`，一次查询只采集一个指纹与一个读取时刻，贯穿全部 14 处 get/put 调用点；`LibraryQueryCache.put()` 接受 `read_at`，作废栅栏与条目时间戳都改按「数据实际被读到的时刻」判定，堵死提交前旧页落进提交后键里、最长脏读整个 20 秒 TTL 的路径。
- [x] 2026-09-17：逐行读完 `src/app/server/dlna/control_point.py`（620 行）并记录判定：后台 discovery worker 的 generation + 线程身份双重释放条件、SSDP 应答与探测的三层上限、UPnP 时间字符串的双向收敛、能力缓存的单调老化与有界淘汰均无需改动。
- [x] 2026-09-17：`discover_upnp()` 的探测截断按 **SSDP 应答到达顺序**取前 16 个（`found` 每轮重建、没有轮转游标），注释承诺「后面的 refresh 会继续探测其余设备」其实只在应答顺序变化时偶然成立：网络里稳定快速应答的设备（NAS 上的多个 DLNA 服务）永远占住前 16 个槽，而唤醒慢、RF 位置深的音箱会被系统性排除在渲染器列表之外。修法要同时解决「已选中的渲染器不能因为本轮没被探测就从 `UPNP_CACHE["items"]` 里消失」，需要轮转游标 + 上轮结果的保留策略，单独安排一轮（可在离线面用注入的 fake socket 断言多轮合并后覆盖全部设备）。  **R96 关闭**：这条要求两半一起做 ✓ 代码里能看到为什么必须一起做：`online` 的含义就是「上一次描述请求拿到了控制 URL」（`control_point.py:468` ✓ 两轮之间没有任何东西重新 ping 它 ✓）✓ 发布处是整表替换（:499 ✓）✓ 而投影层只在设备**存在于**该列表时才可能标出 `selected`（`playback_targets_presentation.py:136` ✓）✓ 所以只轮转不保留，反而会在轮转跨过它的那一轮把用户已选的目标弄丢 ✓ 做法：(1) 新增模块级 `_UPNP_LAST_PROBED`（只记上一轮探测过哪些 location ✓ 天然被 `UPNP_DISCOVERY_DEVICE_PROBE_LIMIT` 限宽 ✓ 不需要新常数 ✓ 一轮历史就够让每个应答者在两轮内轮到一次 ✓）✓ 选取按「上一轮没被问过的优先」✓ 但**遍历与输出仍按到达顺序**（第一版我按轮转顺序输出 ✓ 变异 X2 就是那个版本 ✓ 它会让 UI 目标列表每轮重排 ✓ `playback_targets_presentation.py:132` 是照单传的 ✓ 已改成只轮转「问谁」）✓ (2) `retain_unprobed_devices(previous, current)` ✓ worker 发布时合并 ✓ 保留项标 `probed=False`（投影层只读白名单键 ✓ 所以加字段安全 ✓）✓ 上限沿用既有 `UPNP_MAX_DISCOVERED_DEVICES=128` ✓ 不新造数 ✓ 插入侧那道 128 的闸没有动 ✓ 它只在 SSDP 洪泛时才绑定 ✓ 与本轮的 16 名额偏置是两件事 ✓ 判别性测试 4 条（`test_dlna_network.py`）：3 个应答者配 2 个名额 ✓ 第二轮必须问到第一轮没问的那个 ✓ 两轮合起来覆盖 3 个 ✓ 预算够用时必须按到达顺序全量探测且顺序不变 ✓ 轮转跨过它的那一轮仍要按到达顺序输出（防抖动 ✓）✓ 保留语义（不重复 ✓ 不越 128 ✓ `probed` 标记 ✓）✓ 以及端到端「worker 真的在合并发布」✓ 变异 8 例（控制组 69 条先绿 ✓）全部由新测试杀死：X1 不轮转 ✓ X2 连输出顺序一起轮转（我第一版的真实错误 ✓）✓ X3 不回写轮转记忆 ✓ X4 只在成功时记账（一个不可达设备会一直排在健康设备前面 ✓）✓ X5 发布回到整表替换 ✓ X6 保留时不看是否已探测（重复条目 ✓）✓ X7 保留不顾上限 ✓ X8 保留项不标 `probed` ✓ 两处自伤记在案：`global` 声明写在名字使用之后 ✓ 模块直接 SyntaxError ✓ 被导入才暴露 ✓ 假 socket 用有限 `side_effect` 列表 ✓ `except timeout: continue` 会读穿列表抛 StopIteration ✓ 换成会持续抛超时的假 socket 才对齐真实窗口 ✓ 另 X1 最初是靠变异自身 NameError 崩掉的 ✓ 证据不干净 ✓ 已收窄锚点重跑 ✓
- [x] 2026-09-17：同一个「设备是否支持源码 DSD」的事实在控制面上有两种形状：发现期写入的扁平 `device["supports_dsd"]`（未探测即 False），与 `media_server.soap_push()` 读取的嵌套 `device["capabilities"]["protocol_info"]["supports_dsd"]`（未探测即放行）。两者对「未知」的口径相反，`profiles.device_supports_native_dsd()` 又是第三种（扁平、False 保守）。应统一为一个谓词并明确未知时的策略，属于设备能力语义收窄，需结合真机/渲染器证据安排。  **R126 关闭（2026-09-20）**：三态与唯一谓词已落地。`profiles.py:12-14` 新增 `DSD_CAPABILITY_SUPPORTED/UNSUPPORTED/UNKNOWN`，`:26-41` `_dsd_state_from()` 以「键是否存在」判未知、以「值是否为 True」判支持（非布尔视为不可信的拒绝，旧守卫不放宽），`:43-69` `dsd_capability_state()` 接受 device 或裸 protocol_info，`capabilities` 为 dict 且含 `protocol_info` 键时以嵌套为准、扁平不参与，`:71-79` `device_supports_native_dsd()` 退化为显示面的保守布尔视图。调用侧四处：`control_point.py:14` 引入谓词、`:290-295`/`:317` 两条探测失败壳不再写 `supports_dsd` 键（静默不再伪装成拒绝）、`:320-321` `device_supports_dsd()` 委托谓词、`:494-500` 扁平字段改为「由同一谓词从探测记录派生的显示缓存」、`:502-505` 发现异常路径删掉写 False；`media_server.py:10`/`:183-185` 门改为 `dsd_capability_state(device) == DSD_CAPABILITY_UNSUPPORTED`，拦截文案逐字不变；`playback_targets_presentation.py:9`/`:141-143` 目标列表 `native_dsd` 走同一谓词。判别测试 `src/tests/test_dlna_dsd_capability.py` 13 项（八行真值表对 state/push/display 三列同断言 ＋ 两条按行白名单的源级接线断言），仓库外副本 V1～V11 全灭、0 存活。唯一行为变化是「探测失败空壳由误拦变放行」，属放宽误拦、不收窄任何能力语义，因此不需要真机证据；「哪些真实渲染器会落 unknown」仍需设备取证，并入既有 P0 外部验收段与「真实设备、DAC/DSD、DLNA/AirPlay…外部验收项」那条伞形条目，**不新立项**。
- [x] 2026-09-17：修复 `cover_load_scheduler.js` 队列饱和驱逐丢封面：被挤掉的图片保留本代 `coverQueued` 标记，导致它既不被 observer 关注、又被 `reconcile()` 过滤掉，整代不再有机会加载。改为清标记 + 计入 `dropped`。
- [x] 2026-09-17：`src/tests/test_ui_cover_load_scheduler.js` 新增「标记数 == queued + inFlight」一致性断言与一次饱和优先入队场景，两处变异分别验证。
- [x] 2026-09-17：逐行读完 `src/app/ui/cover_load_scheduler.js`（314 行）并记录判定：`enqueue`/`pump` 递归深度、`start()` 的早返回不泄漏槽位、 detach 图片的槽回收、重试的过期保护、回退游标的只追加语义、`cancel()` 的监听器释放、构造参数收敛均无需改动。
- [x] 2026-09-17：移除 `dlna/media_server.py` 中不可达的 `next_item` 预加载分支与形参（唯一生产调用方从不传下一首，且该分支缺少当前曲目必过的 DSD sink 能力门禁），`server.py` 的 `soap_push()` 包装同步收窄。
- [x] 2026-09-17：移除只有测试在用的 `DlnaMediaServer` 包装类、`_requires_lossless_transcode()`、`dlna/__init__.py` 的对应导出，以及 `server.py` 里两个没有任何调用方的纯转发函数 `upnp_media_url()`/`upnp_resource_size()` 和它们的 import 别名；`resource()` 承载的 APE 描述不变量改由 `upnp_resource_size` + `upnp_resource_mime` 直接断言。
- [x] 2026-09-17：把「一次 DLNA 推送恰好是 Stop/SetAVTransportURI/Play」写成显式断言，并用插入多余 `SetNextAVTransportURI` 的变异验证该断言有效。
- [x] 2026-09-17：`Observability.write()` 的 JSONL stat/轮转/追加/chmod 移出指标锁 `self._lock`，改用专用 `_log_lock`。此前每个请求结束时的 `count()`/`record_http_latency_route()` 与 health/diagnostics 的 `snapshot()` 会被一次日志写入（含 `os.replace` 轮转与 chmod）整体卡住，且慢请求越多越严重。
- [x] 2026-09-17：新增 `test_log_write_does_not_hold_the_metrics_lock` 与 `test_concurrent_log_writes_stay_serialized`，分别钉住「文件 I/O 不持指标锁」和「轮转+追加仍须彼此串行」两个方向；各配一处变异验证（改回指标锁 / 换成空操作锁），`tests.test_observability` 达 31 项全绿。
- [x] 2026-09-17：逐行读完 `src/app/server/observability.py`（260 行）并记录判定：计数白名单与有界增量/总量、固定延迟桶、脱敏的深度/条目/字符串/键长上限与迭代异常隔离、`write()` 的异常吞掉并计数、`request_id()` 的格式校验均无需改动。
- [x] 2026-09-17：`Observability.write()` 每条日志都会先 `secure_directory(dirname)`（一次 chmod 系统调用）再 `secure_file(path)`（再一次），在低优先级存储上是每条被记录请求的固定开销。可加一个有界的「已加固目录」集合（须与 `logs/` 被外部改权限的风险一起评估），属于安全语义变更，需单独一轮评估。  **R94 关闭**：这条建议的做法是「加一个有界的已加固目录集合」并注明「属于安全语义变更，需单独一轮评估」——本轮就是那一次评估，结论是**不走缓存集合，改走漂移探测**：集合一旦记住「这个目录已经加固过」，就再也看不见外部把 `logs/` 改权限的情况 ✓ 那正是要防的事 ✓；改成每次先做一次 `os.lstat`（一个调用同时回答「是不是符号链接」「是不是目录」「模式是否等于要求值」三件事 ✓）✓ 只要有任何一项不对齐就原样回落到既有 `secure_directory`，符号链接的拒绝与目录缺失的创建都留在原函数里 ✓ 没有新语义可丢 ✓ 实测收益要分两件事说清楚：**(a) 计时** ✓ 200 次目录加固 6.075 ms -> 1.060 ms（约 5.7 倍 ✓）✓ 这是本机能量到的真收益 ✓ **(b) 调用计数** ✓ 本轮先前那句「每条日志的探测从 4+ 降到 2」是错的 ✓ 单独数了一遍：旧写法 `secure_directory`+`secure_file` 在 Windows 下 `os.lstat`/`os.stat` 计数为 **0** ✓ 它的探测不经过这两个入口 ✓ 而新写法每行 2 次 lstat ✓ 所以测试里「20 行恰好 40 次、分属两个路径」那条断言 杀变异靠的是**接线指纹**（漂移助手从清单里消失 ✓）而不是成本模型 ✓ POSIX 侧旧写法每行还会真跑一次 chmod ✓ 但本机 `_chmod` 在 :85 提前返回 ✓ 证不了就不假装证了 ✓ 保留完整加固的地方是轮转出的 `.1`（一次 `os.replace` 才产生一个 ✓ 不是每条 ✓）✓ 两条新测试的钉法值得记：一是**必须按真实 `os.lstat` 次数断言而不是 patch 某个函数名**——`observability` 原先 `from file_permissions import secure_directory` ✓patch 源模块根本打不到已绑定的名字 ✓ 所以矩阵里「退回整轮加固」的变异一开始存活 ✓ 改成模块属性调用 + 数 lstat 次数后才死 ✓；二是文件侧四条分支用伪造的 lstat 结果驱动（本机 `_chmod` 是空操作 ✓ 断言「结果模式」会白过 ✓）。另一处等价性观察：把判定式里的 `stat.S_ISLNK(...)` 一项去掉是**等价变异**（`S_IFLNK` 与 `S_IFDIR` 是互斥的文件类型位 ✓ 真符号链接必然使 `S_ISDIR` 为假 ✓ 仍会回落 ✓），而去掉 `not stat.S_ISDIR(...)` 一项则能被测出 ✓ 10 例变异（D1-D5 目录侧、F1-F5 文件侧）全部由新测试杀死 ✓ 控制组 297 条先绿 ✓ 顺带修正一条既有测试的探针：`test_concurrent_log_writes_stay_serialized` 原来只 patch `observability.secure_file` 当作「在锁内」的观测点 ✓ 换轨后每行不再走它 ✓ 改为同时跟踪两个加固入口 ✓ 锁语义未变（加固仍在 `_log_lock` 内 ✓）。另：`:128` 那条提到 `secure_sqlite_files` 在每次读上做三次 chmod ✓ 属同一味道但不同路径 ✓ 本轮未动 ✓ 不在这里冒领。
- [x] 2026-09-17：`LibraryQueryCache.put()` 的整页 `copy.deepcopy` 移出共享 `RLock`（`get()` 早有「拷贝不持锁」的契约与回归，`put()` 漏了），避免一次最多 6000 行的拷贝把首屏并发查询、索引失效写入、health/diagnostics 的 `snapshot()` 全部串行化。新增确定性并发回归。
- [x] 2026-09-17：补上拷贝移出锁之后新出现的作废竞态——`invalidate_database()` 按库记录作废时刻（`MAX_INVALIDATED_DATABASES = 16` 有界），`put()` 回锁时丢弃「读取早于作废」的页，避免被作废的行以 20 秒 TTL 复活。新增回归。
- [x] 2026-09-17：逐行读完 `src/app/server/library_query_cache.py`（293 行）并记录判定：`_purge_expired` 的有界扫描、重量记账与淘汰循环的终止性、缓存键对嵌套元组的拒绝、`abspath` 不做 `normcase` 的 Windows 口径、`get()` 拷贝后的身份回校验均无需改动。
- [x] 2026-09-17：（原待办）曲库缓存的库文件指纹在读库前后各取一次（`_library_query_cache_get`/`_library_query_cache_put` 各自调用 `_library_database_cache_identity`）。若一次提交正好落在读页与写缓存之间，指纹会跟着前进，于是**写入前**读到的页会被存进**写入后**的键里，最长按 TTL 20 秒返回旧数据。已按「一次查询一个纪元」修掉：指纹与读取时刻在查询入口采集一次，贯穿 14 处 get/put 调用点（先前估计的 8 处漏掉了 groups/folders/roots 的分支），`put()` 的作废栅栏改按读取时刻判定。
- [x] 2026-09-17：修复 `_bounded_restart_history()` 保留最旧而非最新的重启时间戳：`status()` 展示错误，且 `register()` 按 `max_restarts` 截断后窗口过滤永无所获，导致重启上限熔断被绕过、崩溃循环无限重启。改为 `deque` 取最新 `limit` 条。新增 2 项回归（含重新注册场景）。
- [x] 2026-09-17：`_monitor()` 的服务日志裁剪移出 `self._lock`（锁内只取 `log_path` 快照，锁外重写最多 1 MiB，完成后重新加锁并复查停止标志与 monitor generation），避免慢磁盘卡住 `status()`/`start()`/`stop()`。新增并发回归。
- [x] 2026-09-17：逐行读完 `src/app/server/services/process_supervisor.py`（552 行）并记录判定：`stop()` 在锁内终止进程、`_ensure_monitor()` 复位 `_stopping`、退避计算与 `_reap_exited_process()` 的异常收敛均按现状保留。
- [x] 2026-09-17：清理 `CHANGELOG_AI.md` 平铺区里两组紧邻的重复条目（09-07 内存曲库分页、09-05 首屏元数据可靠性），并在 `tests/test_change_record.py` 新增 `test_no_entry_is_recorded_twice`：改动记录由脚本 prepend，重复整块不破坏日期序，因此必须单独检查。变异验证：复制最新条目一行即失败，还原后转绿。
- [x] 2026-09-17：修复 `DlnaRenderer.command("play")` 在持有 `_lock` 的情况下调用 `play()`，导致 `_notify()`（GENA 事件体 + `PLAYBACK_CORE.sync_external_session`）与后台准入全部发生在命令锁内——这正是本文件为 `next` 路径明令禁止、并已配测的行为。新增同构确定性回归。
- [x] 2026-09-17：`snapshot()` 与 `_notify()` 不再把活动中的 `next_queue` 列表交给调用方（`command("next")` 会就地 `pop(0)`）；抽出 `_state_copy_locked()`/`_project_state_locked()`，顺带去掉 `snapshot()` 里重复两遍的诊断字段拼装。新增 2 项回归。
- [x] 2026-09-17：`tools/test_offline.ps1` 改为每次运行使用一次性 `PYTHONPYCACHEPREFIX`（`python -B` 不阻止读取树内已有的 `__pycache__`，而缓存有效性只比整秒 mtime + 文件大小，同长度的改动可能被拿旧字节码验证），`finally` 中还原环境变量，并在 `test_offline_verification_script.py` 加断言钉住。
- [x] 2026-09-17：逐行读完 `src/app/server/dlna/renderer.py`（428 行）并记录判定：监听器注册、发布打包对 `__pycache__`/`*.pyc` 的排除与校验、静音期音量口径、`_loading_uri` 去重与重置、后台 worker 起线程失败的闩锁释放均无需改动。
- [x] 2026-09-17：DLNA 浏览分组根容器（`albums`/`artists`/`genres`/`folders`）仍会先取全部再在 Python 里切片：`_browse()` 用的注入 `library_groups(view)` 只接受视图名，没有 limit/offset，所以 `groups[start:start+requested]` 之前必须先物化整张分组表，控制器逐页翻 500 条就等于每页读一遍全库。修法是把注入签名放宽成 `library_groups(view, limit, offset)`（`query_library_groups` 本身已支持分页且有查询缓存），需要同步改 `server.py:3095` 的接线与构造点；本轮只记录了问题，未改动。  **R104 关闭（条目写「本轮只记录了问题，未改动」✓ 本轮落码）（条目写的接线位置 `server.py:3095` 已漂移 ✓ 现为 `initialize_dlna_services()` 内 L3148-3159 的三个闭包）**：✓分流判据不是「调用方想不想分页」而是「提供方有没有声明总数」✓ 新增 `_provider_browse_page(value, rows_key)` 只认 `Mapping` 且含 `rows_key` 且 `count` 可解析 ✓ 三者任一不成立就回退整表（把 unpaged 结果当 paged 会让总数停在页长上 ✓ 变异 M08/M09 专杀）。分组侧保留整表的两种情况：`sort_key == "artist"`（专辑按艺术家排序时排序值不在组名上 ✓ 提供方分页会给出错窗口）与 `start > MAX_LIBRARY_OFFSET`（=100000 ✓ 越出提供方窗口）；目录侧只提供 offset 守卫。子目录分支另有两处语义变化：`track_offset = max(0, start - folder_total)` 用真实目录总数而非页长，`total = folder_total + count` 不再随整页目录而丢曲目数。刻意不扩展的三处：`folders` 根容器（`query_library_root_folders` 无 `limit`/`offset` 语句 ✓ 每个配置根一行 ✓ 证伪证据）、`_metadata_for_object` 的两个存在性扫描（L1098/L1106 ✓ 单行存在性、无按名定位 API）、曲目分支 `offset` 的同源钳位（另一条链路 ✓ 本轮未动、按反增长约束并入本条登记不另立项）。判别性：13 条新用例以假提供方记账 `kwargs` 断言「一次浏览只读一页且带 `limit`/`offset`」✓ 另钉总数不被 5000 封顶、第 5001 组可达、页内顺序归提供方、`desc` 浏览透传 `sort_dir`，以及两条反向断言（根容器与元数据分支不得出现分页参数）。
- [x] 2026-09-17：修复 `parse_soap_action()` 把 SOAP `<s:Header>` 当成动作节点的缺陷（文档序 `iter()` 命中 Header，空 Header 也足以让 Play/Pause/SetAVTransportURI 全部回 500），动作改为只从 Body 的第一个子元素取，保留裸动作元素的宽容解析。新增 3 项回归（含端到端 `control()`）。
- [x] 2026-09-17：`_metadata_for_object()` 校验单个 `albums:`/`artists:`/`genres:` 名称存在性时不再调用无分页的 `library_groups()`（那会绕过查询缓存全表扫 + NOCASE 排序 + 物化整个分组表），改为一次走索引、命中缓存的 `library_page({view, group, limit:1})` 定向探针，并提前拒绝空分组标签。新增 3 项回归。
- [x] 2026-09-17：删除 `DlnaEventService` 中三个从未被调用、只互相引用的投递记账方法（27 行，`delivery_sequence`/`skipped_sequences` 全仓库无其他读写点）；订阅上限 64 抽出 `MAX_EVENT_SUBSCRIPTIONS`，使 `subscribe()` 的准入与 `snapshot()` 的上限展示同源。
- [x] 2026-09-17：逐行读完 `src/app/server/dlna/service.py`（964 行，47 个函数此前只检视过 9 个）其余部分并记录判定：事件服务的资源上限（订阅/pending/workers/饱和计数/有界 shutdown）、GENA 序号回绕、SOAP 入参边界、`_browse` 极端分页参数（由 `MAX_LIBRARY_OFFSET` 夹住）均无需改动。
- [x] 2026-09-17：修复 `_transcode_source_mtime()` 的裸 `getmtime`：源文件被删除/改名（或共享盘掉线）时 `OSError` 会穿过 `transcode_cache_ready()` 直达 `do_GET`/`do_POST`（这条链路没有异常处理），首屏对一条陈旧索引行发 `/api/transcode/status` 就是连接被重置。现在读不到源文件返回 `None`，读路径判为未命中，写路径转成 `RuntimeError`。
- [x] 2026-09-17：`transcode_to_audio()` 的发布环节（`secure_file`/`os.replace`）不再向外抛 `OSError`，统一转 `RuntimeError`，缓存卷写满或只读时 `/media/*` 得到 501 而不是断连；相应把既有测试里断言「抛 OSError」的那条改为新契约。
- [x] 2026-09-17：`cleanup_transcode_cache_if_due()` 改为「先占位再清扫」并吞掉清扫异常（`_CACHE_CLEANUP_LOCK` 内不调用 `prune`，无锁嵌套）：并发请求不再各自全目录扫描，失败的清扫也不会让 `LAST_CACHE_CLEANUP` 永不更新而每次转码都重试；`prune_transcode_cache()` 同时兜住 `os.listdir()` 竞态。
- [x] 2026-09-17：读完 `transcode.py`（611 行）中 24/26 个此前未逐行看过的函数，判定 `_target_lock()` 的弱引用注册表、`media_mode()` 的取下标、`_run_transcode_process()` 的二次诊断上限检查、`warm_transcode_cache()` 的线程创建失败回滚均无需改动，理由记入 `CHANGELOG_AI.md`。新增 8 项回归（`tests.test_transcode_cache` 41 项全绿）。
- [x] 2026-09-17：修复 `cover_cache` 交互/库预热两个 worker 的「退休窗口丢任务」竞态：清 `running` 与注销注册项移入判断队列已空的同一次 `_PREWARM_LOCK` 持锁内，落在窗口内的页面请求/扫描不再被塞进一个正在退出、且不会再有人驱动的队列（首屏封面长期占位/闪烁）。新增 2 项计数锁驱动的确定性回归，并逐处验证过去掉修复就会失败。
- [x] 2026-09-17：逐行读完 `cover_cache.py`（929 行）后判定无需改动的部分并已记录理由：`_LOCKS` 用 `WeakValueDictionary` 避免按封面版本无限留锁；`_MEMORY_CACHE`/别名/负标记三条缓存各有字节与条目上限并在 `clear_memory_cache()` 一并回收；`cover_source_version()` 优先复用索引身份避免首屏逐行 `stat()`，`allow_disk=False` 快路径与 `_cache_key()` 的权威路径分工明确；`_prewarm_result_exists` 命中时不计入 `completed` 属有意口径（该任务没有做生成工作），`thumbnail_prewarm_status` 只做展示用途。
- [x] 2026-09-17：修复 `parse_dac_stream_caps()` 的 kHz 采样率解析：非捕获组让 `re.findall()` 返回整段 `44.1 kHz`，`float()` 抛 `ValueError` 且全链路无人捕获，一张把采样率写成带空格 kHz 的声卡就能让 `alsa_devices()`、输出选择与首屏状态路径整体失败。改为只取数字组 + `safe_float()` + 8k~768k 边界。新增回归（还原旧写法后该回归报错，确认有效）。
- [x] 2026-09-17：`probe_alsa_hw_params()` 的缓存新鲜度改用单调钟（新增 `probed_at_monotonic` 并拒绝负年龄，淘汰排序优先单调钟、回退墙钟），开机后 NTP 往回拨墙钟不再让过期能力集永久显示为新鲜，与 `dlna/control_point.py` 的既有口径对齐。新增回归。
- [x] 2026-09-17：`dac_control()` 的两处竞态修复——每个分支在自己的 `DAC_LOCK` 窗口内重新读取进程列表（不再向被并发替换掉的管线 pid 发信号、不再让正在响的曲目逃过暂停），以及重复 `play` 不再重置计时钟导致进度倒退。新增 2 项确定性回归。
- [x] 2026-09-17：`select_output()`/`test_output()` 的输出切换窗口新增独占保护，读路径 `_selected_alsa_output()` 改走 `_persist_output_selection()`，切换期间并发状态轮询不再把未通过验证/仅在试听的设备写进 config.json；`test_output()` 中途恢复补齐为整份选择快照，`finally` 仅在确有变化时持久化并把两次 MPD 重启收敛为一次。新增 3 项回归（含嵌套窗口不得提前交还持久化权、重启前必须先恢复稳定 id）。
- [x] 2026-09-17：`_selected_alsa_output()` 与输出切换路径的 5 处 ALSA 选择写入全部改为单次 `config.update()`，消除稳定 id/运行时 id 半份配对被并发轮询读走后按旧声卡回写的竞态。
- [x] 2026-09-17：`mpd_service.output_capabilities()` 冷缓存并发不再各自重复扫描 ALSA（`amixer` 子进程按声卡线性增长，压在首屏状态轮询上）：构建槽改为计数 + 空闲事件，冷启动调用者等待复用同一结果，仅在对方卡住/无产出时自行构建（绝不返回会让上层误判「无声卡」的空描述）。新增 3 项回归。
- [x] 2026-09-17：`idle_status()` 复制 `_underrun_state`/`_playback_error_state` 改由新增 `_error_state_lock` 保护，消除与设备监控线程并发更新造成的撕裂快照；`_observe_fault` 保持在另一把锁外调用。新增锁覆盖回归。
- [x] 2026-09-17：`_device_monitor_loop()` 逐次捕获异常并记为 fault，DAC 热插拔监听与 MPD 日志错误读取不再因一次失败永久消失。新增回归。
- [x] 2026-09-17：`_last_underrun_restart` 哨兵从 `0.0` 改为 `-inf`，开机 30 秒内的首次缓冲不足不再被 30 秒去抖误跳过（去抖使用单调钟）。新增回归。
- [x] 2026-09-17：复核 `mpd_service.py` 后判定无需改动并已记录理由：日志游标只跳中间旧字节（最新错误必被分类）、状态延迟均值为标准增量算法且计数有上限、probe 年龄已优先单调钟、恢复线程注册与启动同锁、supervisor 回调自行捕获异常。
- [x] 2026-09-20：`mpd_service.py` 逐行审计已读完，本条继续开启的理由改为下述 ④ 的真实缺陷（R121 取证；条目原文的路径与三处口径已按磁盘更正）。① **路径漂移更正**：文件真实位置是 `src/app/server/services/mpd_service.py`（2150 行 / 98885 B）与 `src/app/server/playback/mpd_client.py`（457 行），原文暗示的「`src/app/server/` 直下」作废。② **三处疑点当轮证伪，均不立项**：`_mpd_quote()` 在 `mpd_service.py:2050-2051`，`ensure_config()`（:589-674）里 `bind_to_address "%s" % self.host`（:616）是全文唯一未走 `_mpd_quote` 的插值，但 `self.host = DEFAULT_HOST` 只有 :128 一处赋值、当前不可注入 ⇒ 结论写成条件句：**若将来 host 变成可配置项，这一行必须改走 `_mpd_quote`**；`mixer_policy()`（:1993-2047）三个分支恒返回含 `control`/`device` 的映射，`ensure_config()` :631-637 的 hardware 分支因此不会 KeyError；`_start_locked()`（:680-752）里 `_config_int(self.config.get("mpd_nice"), 0, -5, 10)` 在 :670/:704/:707-708 重复算三次，属可读性，并入本条不另立。③ **FLAC-CUE 的 `start` 传递语义判定为正确**：`transcode.py:319-326` 的 `cue_flac` 用 `-ss cue_start -i path -t duration` 产出**按轨裁切**的文件，而只有 `.ape` 会走它（`mpd_service.py:408-411`），所以 :440/:454 的 `start=0.0 if current_cue_ape else start` 是在避免二次叠加偏移（代价：APE-CUE 丢续播位置），不是落错点；`playback/mpd_output.py:133-142` 在调用点算 `cue_start = max(0, cue_offset) + requested_position`（整文件秒数），与 `playback/mpd_client.py:367-370` 的 `if play and start > 0: seekid`（`play=False` 时 start 被忽略）同口径。④ **真实缺陷＝同一个「播放位置」在四条投影里单位不一致**：MPD 传输监听器把**未折算**的整文件秒数写进 core（`server.py:3226-3232`，另 :3248-3253）⇒ 持久化会话同样存整文件秒数（`playback_session_projection.py:38`）；而 `/api/playback/status` 的 mpd 分支在 `server.py:2726` 调 `normalize_cue_position()`（`playback_cue_position.py:36`，仅对非转码 CUE 折 `whole - cue_start`）给出**轨内**秒数；SSE `api/playback/events` 走 `playback_event_presentation.py:22/73` 给出的是**未折算**整文件秒数。前端把两条推送路写进同一个变量：`app.js:2406` `state.remoteBaseSeconds = data.position.rel_seconds`，而它唯一的补偿判据 `app.js:2413` `state.remoteCueSegment = cue_track && !isDacTarget()` 只看目标类型（`playback_target_policy.js:5` 的 `isDac` 仅匹配 `dac:` 前缀 ⇒ MPD 恒被判成「已裁切、不折算」），不看数值来自哪条投影。于是 **FLAC 版 CUE 经 MPD 播放时（只有 `.ape` 被裁切，FLAC 是把整文件交给 MPD 的，MPD 报的就是整文件秒数）：SSE 一连通 `state.remoteStateVersion` 转正，此后缺顶层 `state_version` 的轮询响应（`playback_status_response.py:31-38` 未挂该字段）会在 `app.js:2396` 被整条丢弃，进度条数值完全来自未折算的整文件秒数 ⇒ 第 2 轨起 elapsed 多显示 `cue_start` 并被 `seekDuration()` 夹到满格；而 SSE 未连通的浏览器（代理、睡眠恢复、无 EventSource，`app.js:2519` 正是为此安排的轮询）反过来以折算后的轮询为准——同一字段在同一会话里按到达顺序互相覆盖。**显示与 seek 提交（`app.js:4598`，MPD 分支不加 `cue_start`）因此建立在两种互相矛盾的前提上。**已排除的更坏情形（本轮逐点查过）**：`PlaybackCommand` 的 position 实参取自 `position = payload.get("position")`（`server.py:2552`）＝客户端请求值，服务端内部不存在「把 core 位置回灌再叠一次 `cue_start`」的双加路径；启动会话恢复虽把整文件秒数当 `start` 传入（`server.py:2240-2250`），但在 `play=False` 下被 `mpd_client.py:367-370` 忽略 ⇒ 只影响显示，不影响落点。⑤ **修法两个候选，都改语义、勾选仍需真机回归**：(a) 进 core 之前折算一次，让 core / 会话 / SSE 三者统一为轨内秒数 —— 代价是 `normalize_cue_position` 与 `mpd_output.py:139` 的 `cue_start +` 必须同步改，且历史持久化会话的单位会翻转一次；(b) 明确 core 一律是整文件秒数，改由前端按投影来源折算（给 `app.js:2413` 的判据补上「曲目是否真的被裁切」）—— 代价是 DLNA / ALSA / MPD 三条链路的现有假设都要逐一核对。本轮不动代码：R121 是决策落地轮（八条裁定 + 基线提交 + 真机取证），且离线套件能量到的是「两条投影单位不一致」，量不到「用户可见的抖动/满格」，按当轮取证、下轮动刀处理 ⇒ 本条列为 R122 的首个代码项，需配判别测试与仓库外变异矩阵。 ⑥ **R122 已实施并关闭**：取 ⑤ 的 (a)「进 core 之前折算一次」为主体，取 (b)「显式声明单位」为对外接口，服务端成为唯一的折算点。折算与反向折算共用同一个判据 —— `playback_cue_position.py` 新增 `cue_is_transcoded()`（只有 `.ape` 真被裁切），`normalize_cue_position()` 改为调用它，另新增 `public_cue_position()`（后端秒数折成客户端单位）、`cue_segment_declaration()`（声明本帧秒数是否已按段）、`project_cue_seek()`（折叠的精确逆）。写点侧：`server.py` 新增 `project_mpd_transport_position()`，接在 `on_mpd_transport` 的两个 `sync_output_status` 调用上替换裸 `safe_float(position.get(...))`，core、持久化会话、SSE、轮询四路从此共用一个单位。seek 侧：`playback/mpd_output.py` 的 `command()` 只对 seek 走 `project_cue_seek()`，曲目解析优先请求载荷、缺失才回落队列引用（新增 `_current_cue_item()`）；`restore_playback_session` 先算 `backend_start` 再交给 `sync_playback_queue(start=...)`，前提是 `server.py:2254` 传 `play=False` 使 `mpd_client.py:367-370` 的 `if play and start > 0` 不成立。声明侧：`playback_status_response.py` 给 alsa/mpd/upnp 三支挂顶层 `cue_segment` 与 `state_version`（`_state_version()` 把 bool、非数字文本、越界值夹回 0），`playback_event_presentation.py` 的 SSE 载荷同样带声明；`playback/core.py` 新增 `_current_item_locked()`、`current_item()`、`snapshot_with_item()`，用同一把锁把位置与曲目配对取出，防新位置配上一轨偏移。前端 `app.js` 以服务端声明为权威：`applyRemotePlaybackSnapshot` 里 `data.cue_segment === true || === false` 严格判存在即采纳，未声明才回落本地元数据；`seekDuration()` 在声明为段时不再二次减 `cue_start`；`pushToDevice` 的本地回落加 `data.cue_segment !== false` 门。⑦ **判别测试**：新增 27 项 Python（`test_mpd_output` 5、`test_playback_core_state` 5、`test_playback_cue_position` 6、`test_playback_event_presentation` 4、`test_playback_status_response` 3、`test_playback_restore` 4）与新 JS 套件 `src/tests/test_ui_remote_cue_units.js`；控制组六模块 120 项在收口当场复跑为 OK。仓库外副本 `E:/fnAudio_r122_verify` 的变异矩阵 M1～M13 全灭、控制组当场存活。两处如实标注：其一，`test_the_mpd_listener_folds_the_seconds_before_publishing_them` 与 `test_the_event_stream_publishes_the_snapshot_and_item_as_a_pair` 是**源码级接线守卫**而非行为覆盖 —— 两个写点分别写在 `main()` 与请求处理器方法体内，单元测试调不到，M6、M7 只有这两条能杀；其二，M5 那类「声明只验布尔类型」的判据按设计不可杀，已在文档串注明。补记一处本轮自纠：`M7`（SSE 路由退回 `snapshot()` 并丢掉第三个实参）在上一会话的矩阵里并不存在，是本轮收口复核时新发现的判别缺口，补守卫后复跑才全灭。⑧ **本轮已知代价，不隐藏**：持久化会话的单位翻转一次，升级前存的整文件秒数会被当作客户端单位读，native CUE 段续播可能把进度条顶满一帧；因 `play=False` 不影响落点，且下一帧即被折算后的监听器写回覆盖而自愈，本轮不写迁移脚本。⑨ ② 那条条件句继续有效（若 `mpd_service.py` 的 `host` 将来变成可配置项，`ensure_config():616` 必须改走 `_mpd_quote`），作为口径随本条归档，不另立条目。〔R122 关闭〕
- [x] 2026-09-17：元数据专辑封面的标签重写扇出改为有界（新增 `MAX_ALBUM_TAG_WRITE_TRACKS = 2048`、`ORDER BY id LIMIT`、空专辑名直接返回），避免一个空名专辑实体把整库未标记曲目排成近 2 万条重写任务并逐条全表计数；`_backfill_album_tag_writes()` 游标改为先判定严格前进再排队。新增 3 项回归。
- [x] 2026-09-17：`refresh_library_if_changed()` 的扫描前准备段移入 `try:`，消除 `SCAN_LOCK` 在 `acquire()` 与受保护块之间被异常带走、导致后续所有刷新永久死锁的窗口；新增锁释放回归。
- [x] 2026-09-17：`cgi_proxy.wait_for_service()` 改用 `time.monotonic()`，系统时间跳变不再让 CGI 就绪等待挂死或提前放弃；补 3 项该函数缺失的回归（假时钟并禁止读墙上时间）。
- [x] 2026-09-17：修复 `state_store` 过期增量合并路径批量收藏顺序反转（整批共用时间戳 + 逆序插入以匹配 `created_at DESC, rowid DESC` 读取），新增复现回归。
- [x] 2026-09-17：本轮同时复核并判定无需改动的区域：`dlna/service.py` GENA 投递（订阅数 64 上限、有界 pending 计数在各过期/退订/提交失败路径扣减一致、`shutdown` 等待有界）、`cover_readers.read_flac_cover()`（每轮至少消费 4 字节且有块大小上限）、`library_item_lookup.lookup_memory_item()`（迭代器异常即终止）、`_run_library_refresh_queue()`（队列排空即退出）。
- [x] 2026-09-17：决定 `tools/apk-analysis/`（1.80 GB）与 `tools/runtime/`（1.43 GB）的处置方式（用户已否决写入 `.gitignore`）：实测可安全回收约 1.74 GB 的纯下载件、已解压重复项与跨版本重复副本（`tools/runtime/go`、`gocache`、`gomodcache`、`go1.25.1.windows-amd64.zip`、`jadx-1.5.6.zip` 及解压目录、`mitmproxy-12.2.3.zip` 及解压目录、`frida-server-17.17.0-*` 与 `.xz`、`apk-analysis/.venv`、`__pycache__`、`fnos-full-source`、`sskit-stage`、`fnaudio-0.1.226-source`、`fnos-1.33.4-apk|native|resources|source`）；`fnos-1.35.2-source`、`fnconnect-*.mitm`/`.pcap` 与设备截图是文档引用的不可复现证据，删除前须确认，且 `.mitm` 可能含敏感 Cookie。 〔R122 关闭·负责人裁定 C3＝移出版本树到 `E:/fnAudio/_external`〕实测事实与本条原述的三处偏差，按磁盘更正：① **回收量为 0**：裁定是「移出」而非「删除」，`_external/apk-analysis` 复测 1.80 GB、`_external/runtime` 复测 1.43 GB，合计 3.23 GB 仍在盘上，原写「实测可安全回收约 1.74 GB」的估算就此作废；`tools/apk-analysis`、`tools/runtime` 两个旧位置已不存在。② **这两棵树从未被 Git 跟踪**：`git ls-files` 与 `git ls-tree -r HEAD tools` 对其 0 命中，所以移出不动提交历史、也不需要改 `.gitignore`（`_external/` 以未跟踪目录呈现，符合「禁止修改 `.gitignore`」的约束）。③ **文档路径漂移 18 处已改**：`docs/FN_CONNECT_EMULATOR_RESEARCH_20260816.md` 12 处、`docs/GO_MUSIC_DL_PROVIDER_VALIDATION.md` 4 处、`docs/FNOS_MUSIC_MEDIASESSION_RESEARCH_20260831.md` 1 处、`docs/FN_CONNECT_RELAY_CAPTURE_20260812.md` 1 处，旧路径在 `docs/` 内命中归零、新路径命中 18；三份根文档与历史条目里的旧路径命中（CHANGELOG 22 / PROJECT_CONTEXT 1 / TODO 7）按「历史不回填」保持原样。④ **敏感面未因迁移改变**：`_external/apk-analysis` 下仍有 5 个 `.mitm` 与 2 个 `.pcap`，合计 54,156,024 B，其中五个 `.mitm` 为 14,502,435 B，其中 `fnconnect-capture.mitm` 14,023,762 B、`fnconnect-relay-forced.pcap` 16,506,880 B，可能含 Cookie，仍是磁盘上的明文取证材料，本条只关闭「处置方式待定」，不声称泄露面已消除。
- [x] 2026-09-17：`lane_workers_alive()` 不再因非可迭代或抛错的 `fetch_threads` 属性把元数据请求变成 HTTP 异常，统一降级为「lane 不可用」触发既有惰性恢复；新增 2 项回归。
- [x] 2026-09-17：provider 诊断槽位驱逐加入名称平局键，驱逐结果跨进程可复现；补齐该路径此前缺失的 2 项测试。
- [x] 2026-09-17：UI 模块发现从 `test_offline.ps1` 拆到 `tools/ui_asset_gate.ps1`（容忍属性顺序/查询串、越界即报错、空结果即失败），删除 12 条重复硬编码检查，新增 `test_ui_asset_gate.py` 行为与不变量测试。
- [x] 2026-09-17：更正 `docs/SOURCE_INVENTORY.md` 陈旧的“当前源码版本 0.1.223”为 `0.2.34`（与 `src/manifest` 对齐）；同轮复核 cover_cache 预热循环有界、记录 fnos_api 死路由与未包装 socket 异常为待办。
- [x] 2026-09-17：DLNA 发现不再被一次 ICMP 瞬时错误中断：`discover_upnp()` 容忍 `OSError` 继续读取，连续错误上限 `UPNP_DISCOVERY_MAX_TRANSIENT_ERRORS = 8`，发现 socket 补 `IP_MULTICAST_TTL = 2` 以覆盖跨子网渲染器；新增 2 项离线回归，真机互操作仍待验收。
- [x] 2026-09-17：ALSA 播放保留非整帧读取的残帧（新增 `iter_pcm_chunks()`），修复管道错位持续丢采样；`write_pcm_buffer()` 改用 `snd_pcm_recover()` 覆盖 xrun/EAGAIN/挂起并有 `MAX_ALSA_RECOVERY_ATTEMPTS = 8` 上限；`check()` 停止在错误路径改写 `restype`。新增 5 项假 ALSA 绑定回归，真机未测。
- [x] 2026-09-17：修复 DLNA 推送 URI 与浏览 DIDL/封面 URI 的曲目 ID 编解码不一致：推送侧百分号编码 ID，`/upnp/media` 与 `/cover` 路由在库查询前解码；含空格、`/`、`%` 或非 ASCII 的历史/队列 ID 不再让渲染器 404。新增编码往返与 HTTP 集成回归。
- [x] 2026-09-17：加固 DLNA 推送：缺少 `path`/`id` 的行安全退化而非抛 `KeyError`；可选的 `SetNextAVTransportURI` 预载不再为 size 提示提前整轨转码，避免抢占 ffmpeg 槽位拖垮当前曲目请求；渲染器能力每次推送只解析一次。
- [x] 2026-09-17：变更记录治理：新增 `test_change_record.py` 门禁 `CHANGELOG_AI.md`/`TODO.md` 扁平区条目格式与日期顺序，历史条目按日期归位；`docs/INDEX.md` 明确要求每次改动留痕（同日更正：本工作目录当前没有自动任务，留痕仅由门禁保证）。
- [x] 2026-09-17：首屏封面懒加载改为只入队首批优先级、其余按可见性观察，修复长列表/翻页后台无界拉取封面；新增分页突发回归。
- [x] 2026-09-17：`cmd stop` 残留服务清理改为匹配 `--port`，旧安装目录的服务不再绕过清理并继续自动重启 MPD。
- [x] 2026-09-17：`person()` 补入口守卫，空/非文本歌手名不再触达 provider，避免 `quote(None)` 异常被计入失败而触发网易/QQ 冷却。
- [x] 2026-09-17：可见行 metadata 双 worker 改用 `try/finally` 释放页面级控制器，消除首个请求前异常导致的同页 lane 永久短路。
- [x] 2026-09-17：发布治理新增缓存戳门禁：`index.html` 中缺少 `?v=__FNAUDIO_ASSET_BUILD__` 的本地脚本/样式引用在打包时直接报错。
- [x] 2026-09-17：SSDP 监听容忍瞬时 `OSError` 并退避继续，修复一次 ICMP 端口不可达即永久静默 DLNA 发现。
- [x] 2026-09-17：补记记录缺口：核对工作树与文件写入证据，补录 09-09 至 09-17 未留痕的改动（该区间 256 次项目文件写入、两份根文档零条目）；后续每轮改动仍须同日双写并在 `test_change_record.py` 门禁下保持顺序；本次补录 38 条修改记录与 23 条镜像，未改代码；工作目录未配置自动任务，留痕要求仅由门禁与文档规则约束。
- [x] 2026-09-17：补记 Android 原生会话生命周期与恢复：停止仅限已启动会话、启动失败仅清理该次尝试、迟到 worker 不得停止新会话、恢复被拒时如实上报；`MainActivity` 强制原生 HTTP 调用上限并丢弃销毁后的拦截响应。新增 88 项 `test_android_tpps_lifecycle.py` 门禁。
- [x] 2026-09-16：补记曲库读路径治理：分页缓存 + 2 秒根摘要缓存与 32 路 in-flight 合并 + JSON 缓存 32 MiB 字节上限 + 500 条批量写入 + 续扫偏移；inotify 监听改非阻塞有界读并限制观看数与线程数。
- [x] 2026-09-16：补记封面缓存重写：交互/整库双预热通道带上限与 generation、缺失标记 5 分钟 TTL、预热版本改用索引字段免 `os.stat`、所有缓存读取有界、ffmpeg 缩略图带 deadline 终止、诊断快照有界。
- [x] 2026-09-16：补记 DLNA 事件与 SOAP 边界：GENA 每订阅有界队列与序号投递、慢控制点不再阻塞他人；XML 解析 1 MiB 上限；SOAP 参数/动作上界与严格时长/音量解析。
- [x] 2026-09-16：补记渲染器后台动作合并：`take_latest` 合并被取代的 load/control，代际守卫阻止迟到结果覆盖新歌，后端返回值安全投影，跳转/音量夹取。
- [x] 2026-09-16：补记播放核心/ALSA 边界：队列 50,000 与命令票据上界、DAC 进度改用 monotonic 时钟、ALSA 能力缓存 64 条且有界 TTL、停止时带 deadline 终止并关闭子进程流。
- [x] 2026-09-16：补记转码/指纹/状态存储/CGI 网关边界：ffmpeg 与 fpcalc 子进程 deadline 与输出上限、缓存 key 有界、歌单与收藏持久化配额、`state_db_connect` 失败路径关闭连接、fnOS 代理 15 项请求/响应上限并拒绝编码穿越。
- [x] 2026-09-16：补记 Android 远端播放与图片链路：请求令牌防乱序回退、待处理下载与缓存规模上界、跨 origin 拒绝、认证会话代际闸门、凭据不跨源转发、自签证书指纹锁定。
- [x] 2026-09-15：补记 MPD `command_list_ok` 队列单次往返（含 song id 全量确认），修复 2,000 首队列切换输出时的逐首往返延迟；补记 MPD 连接失败路径不再泄漏 socket、响应/命令字节上限。
- [x] 2026-09-15：补记外部探测有界化：`process_output.check_output_bounded`、`probe_runner`、`native_audio_info`、`ffmpeg_cover`，以及 provider 封面/歌词 URL 的公网地址校验（拒绝本机与链路本地）。
- [x] 2026-09-15：补记 UI 请求键/查询参数拆分与 Android FnConnect 配置（relay mode、探测总预算、解析 generation 取消、`destroyed` 守卫、桥接上界）。
- [x] 2026-09-14：补记 `file_permissions` 拒绝非路径对象与符号链接目标、fnOS API 响应上限、播放 HTTP 契约严格 target/queue 解析、Android profile store 进程级串行化（修复跨实例读改写互相覆盖登录历史）。
- [x] 2026-09-14：补记纯模块批次：`api_token_policy`、`cover_queue_policy`、`library_cursor_policy`、`library_browse_cursor_policy`、`metadata_artwork_file`、`metadata_candidate_search_policy`、`metadata_provider_response`（provider 上限单源）、`playback_status_spec`、`scan_control`、`state_projection`、`ui/library_item_request_loader.js`、`ArtworkBitmapDecoder`。
- [x] 2026-09-13：补记健康/诊断快照输入安全（`summary_values` 等 5 个投影模块 + `support_snapshot` 逐层防护），损坏依赖载荷不再让 `/api/health` 与诊断接口抛错。
- [x] 2026-09-13：补记 DLNA 事件负载上界与 XML 转义、MIME 正则校验，避免异常 mime 污染 `protocolInfo`/DIDL。
- [x] 2026-09-13：补记曲库路径/写入/内存回退拆分（`library_paths`、`library_write`、`library_memory_query`、`metadata_track_id_policy`、`embedded_lyrics`、`port_probe`、`cover_item_cache`）。
- [x] 2026-09-13：补记 AirPlay 与 ALSA/DAC 输出租约互斥、`alsa_player` 部分写循环（短写不再丢音频）、MPD 输出 CUE 偏移感知定位。
- [x] 2026-09-12：补记 E2E 夹具元数据两阶段生命周期与请求边界、源码清单原子写与 SHA-256 回退、23 项容器封面/探测/故障计数回归。
- [x] 2026-09-11：补记配置输入边界全量收紧与行为变更：`metadata_enabled` 默认改为关闭并新增 `metadata_tag_write_enabled`（默认关闭），新安装不再默认打第三方 provider 或写回标签。
- [x] 2026-09-11：补记离线门禁发现式改造（按 `index.html` 与 `tests/test_*.js` 自动发现、`tools/*.ps1` 语法门禁、显式 `PYTHONPATH`）与源码卫生范围扩至 `app/ui`、TODO 条目唯一性门禁。
- [x] 2026-09-11：补记首屏 UI 纯模块批次（访问档位、批量请求池、创作者视图、设备能力、宿主会话、候选展示、用户媒体状态、可见行预取）与 `track_presentation.columnValues` 多列一次生成。
- [x] 2026-09-09：补记 `TrackRef`/`PlaybackState` 边界与会话身份字段、封面容器 reader 拆分（ID3/FLAC/APE 上限）、`upmpdcli` 探测有界化、Android 运行时连接身份比较修复（同 id 新 token 不再被判定为未变化）。
- [x] 2026-09-08：首屏曲库响应去重识别已取消的旧 `AbortSignal`；切页/切搜索在旧请求延迟拒绝窗口不会错误复用已取消 Promise，新请求可立即重新占用有界并发槽位；新增 loader 与加载静态回归。
- [x] 2026-09-08：将 SQLite 曲库分页的行解码、内部排序锚点、SQL 投影和下一游标响应抽为纯 `library_page_result_policy.py`；`library.py` 保留兼容接线，新增策略回归，完整离线门禁 1219 项及全部 Node/UI/脚本回归通过。
- [x] 2026-09-08：将 UI 曲库连续翻页游标缓存拆为独立 `library_page_cursor_policy.js`，集中处理页码/Token 边界、首分页重置和 64 项淘汰；新增 Node 回归并通过完整离线门禁 1215 项。
- [x] 2026-09-08：修正 keyset cursor 对历史/精简 `item_json` 的依赖，改用 SQLite 实际排序表达式返回内部锚点；新增缺失 `added_ns` 回归，避免连续翻页重复或漏项。
- [x] 2026-09-08：曲库连续翻页新增可选 keyset cursor：以 `(排序表达式, title, id)` 稳定游标替代连续下一页的深 OFFSET；首屏、任意页码跳转和旧 API 保持兼容。新增游标边界/SQLite tie-break/UI 接线/大曲库基准回归，完整离线门禁 1214 项通过。
- [x] 2026-09-08：metadata artwork 公开服务以真实文件大小校验并修正缓存 size，拒绝空/超 8 MiB 膨胀资产，避免陈旧 Content-Length 影响 HTTP 流式响应；MetadataService 与 HTTP 集成回归通过。
- [x] 2026-09-08：metadata artwork 下载在读取前拒绝声明超过 8 MiB 的可信 `Content-Length`；缺失/畸形头保留受限读取兜底，新增读前拒绝回归并通过 MetadataService 专项。
- [x] 2026-09-08：为发布证据索引增加真实 PowerShell verifier 夹具，确认畸形 artifact/SHA-256 被清空且 recovery note 限制 512 字符；发布治理执行回归通过。
- [x] 2026-09-08：修复带缓存封面的 lyrics pending 响应提前绕过 worker 恢复探测的问题；封面继续即时显示，歌词仍保持 retryable pending；Metadata lane 与 HTTP 集成 39 项回归通过。
- [x] 2026-09-08：抽出共享 `is_artwork_url()` 并让 metadata 响应缓存判定复用统一 URL policy；拒绝大写、绝对路径和目录穿越 artwork URL，纯策略回归通过。
- [x] 2026-09-08：metadata pending 歌词响应复用共享 `artwork_url()` 投影，非法 artwork ID 不再拼接为公开路径；新增 pending 分支回归并通过 MetadataService 专项验证。
- [x] 2026-09-08：根目录搜索先定位命中 root；无命中时跳过 `root_summary` JSON 读取和旧库 `GROUP BY root` 回退聚合，直接返回缓存空结果。命中行仍保留摘要提供的曲数与封面；SQLite 跟踪回归和曲库专项 65 项通过。
- [x] 2026-09-08：发布证据索引对 verifier 字段做有界投影：artifact 仅保留安全文件名，SHA-256 仅接受完整 64 位十六进制，recovery note 去控制字符并限制 512 字符，避免异常输出扩大机器索引；离线脚本契约回归通过。
- [x] 2026-09-08：根目录搜索复用单次 FTS5/LIKE 模式计划，缓存身份与 SQL 条件保持一致；根目录模式读取回归通过，SQLite 曲库专项 96 项。
- [x] 2026-09-08：搜索请求一次读取 FTS5/LIKE 模式并同时绑定 SQL 与缓存身份，消除并发模式切换时的缓存键错配；无搜索浏览保持零模式探测，SQLite 曲库专项 95 项通过。
- [x] 2026-09-08：无搜索曲库浏览缓存不再附加空 FTS/LIKE 模式令牌，搜索页继续按实际执行模式隔离；分类/文件夹/根目录热路径回归通过，SQLite 专项 94 项。
- [x] 2026-09-08：可见 metadata 批次完成后只触发一次封面探测，避免逐行 patch 重复 O(n) DOM 扫描；E2E 验证 `coverHydrations <= 2` 且稳定行 identity 保持不变。
- [x] 2026-09-08：曲库搜索缓存键纳入实际 FTS5/LIKE 执行模式，覆盖歌曲、分类、文件夹与根目录搜索；模式切换不会错误命中旧缓存，SQLite 曲库专项 93 项通过。
- [x] 2026-09-08：metadata status/health/diagnostics 纳入两条本地歌词恢复缓存的合并统计，保持字段有界且脱敏；新增命中、容量、异常计数与投影回归。
- [x] 2026-09-08：发布证据索引仅在遍历期间保留最多 256 个最新 semver 目录，避免大量历史产物时物化/排序整个版本集合；降序和 JSON 证据契约回归通过。
- [x] 2026-09-08：交互与后台元数据入口统一复用有界 `LocalLyricsCache`，避免本地歌词缓存键/失效/LRU 语义漂移；新增虚拟路径、版本替换、读失败与接线回归，MetadataService 专项 115 项通过。
- [x] 2026-09-08：首屏快照解析/TTL/条目与序列化资源预算拆为纯 `library_page_snapshot_policy.js`，前端主流程只保留存储和状态接线；新增异常、过期、超限回归，浏览器 E2E 6/6 通过。
- [x] 2026-09-08：浏览器夹具预置有效首屏快照并延迟等价权威分页，验证快照复用计数、四个歌曲行 DOM identity 与零额外列表提交；元数据回填改为只上报实际变化字段，封面等非排序变更不再触发错误的整表协调。Playwright 浏览器 E2E 6/6 通过。
- [x] 2026-09-08：曲库 SQLite 存储压力纳入 `/api/library/status`、health 与 diagnostics：只读主库/WAL/SHM 的受限文件属性并公开各自与总字节数，不读取 SQLite 内容、不泄露缓存路径；新增纯投影、状态和 HTTP 离线回归。
- [x] 2026-09-08：100k 曲库 format 与 track_no 排序补齐稳定 `(排序表达式, title NOCASE, id)` 双向复合索引，并清理被覆盖的旧单列索引；表达式序号排序保持“非正数末尾”语义。八个计划均无临时 B-tree，首/中/尾页约 4.0-14.0ms，证据为 `artifacts/large-library-benchmark-20260908-format-track-index.json`。
- [x] 2026-09-08：100k 曲库“加入时间”排序以 `(added_ns, title NOCASE, id)` 双向复合索引替代无法满足稳定 tie-break 的旧单列索引；升级时清理冗余索引。首/中/尾页为 3.3/7.0/10.2ms（降序 3.5/9.0/13.6ms），证据归档至 `artifacts/large-library-benchmark-20260908-added-index.json`。
- [x] 2026-09-08：100k 曲库 artist/album 排序补齐 `(排序字段 NOCASE, title NOCASE, id)` 双向稳定索引，消除中/尾页临时 B-tree；首/中/尾页均约 3.9-14.2ms，索引计划和性能证据归档至 `artifacts/large-library-benchmark-20260908-artist-album-index.json`。
- [x] 2026-09-08：歌词缓存快速返回也复用已校验的专辑 artwork（含 album_artist 旧键兼容），避免歌词已缓存但独立封面尚未回填时歌词页短暂退回空封面；新增 MetadataService 离线回归。
- [x] 2026-09-08：首屏分页后的延迟 `library/status` 探测改用共享状态请求边界，避免扫描轮询与首屏状态聚合并发；保留 `refresh=1` 语义，UI 加载专项通过。
- [x] 2026-09-08：SQLite 曲库摘要缓存增加按数据库键的有界单飞读取；并发状态轮询在冷缓存时复用同一次 `count/signature` 聚合，超时或容量耗尽安全降级，曲库缓存专项通过。
- [x] 2026-09-08：显式曲库刷新在普通 `library/status` 请求在途时保留一次尾随 `refresh=1` 意图；删除歌曲等操作统一复用状态单飞入口，避免强制扫描被普通轮询吞掉。新增纯策略与 UI 回归。
- [x] 2026-09-08：当前曲目优先元数据 lane 仅在真实请求/重试定时器仍存活时排除可见预取；结算后的历史 attempts 不再错误占用所有权，缺字段当前行可重新进入有界恢复。新增所有权策略与 UI 回归。
- [x] 2026-09-08：当前曲目元数据请求异常后安排重试时立即恢复 AbortController 所有权；切歌可以取消尚未触发的下一次请求，避免旧曲重试浪费 provider/socket 槽位。UI 回归通过。
- [x] 2026-09-08：当前曲目歌词优先 lane 在空终态且无重试时释放 controller/曲目去重标记；网络异常或 pending 重试继续持有可取消 controller，避免旧曲重试与空投影永久锁死。歌词/UI 回归通过。
- [x] 2026-09-08：歌词 provider 仅在返回非空、可用歌词文本时记录 success；空结果改记有界 `empty` 并继续后备源，不再错误解除失败冷却。新增 fallback/诊断回归，MetadataService 专项 114 项通过。
- [x] 2026-09-08：启动快照歌曲行投影在固定扫描预算内跳过异常前缀并继续收集合法 ID，避免损坏旧快照把合法首屏行挤出窗口；新增稀疏异常条目回归，UI 加载专项通过。
- [x] 2026-09-08：provider 曲目候选空响应或无可展示候选不再清除失败冷却；活动诊断仍保留 `empty_results`/`no_valid_candidates` outcome-only 行，避免恢复语义与可观测性互相覆盖。MetadataService 与纯投影专项 117 项通过。
- [x] 2026-09-08：metadata 状态投影更新复用同一已提交页、同一请求序列中已排队或运行的可见元数据 lane，避免 abort 在途 provider 请求并重复首屏静默窗口；页面切换、隐藏及已结算 lane 仍保留取消/恢复边界，新增纯策略与 UI 回归。
- [x] 2026-09-07：修复曲目候选 provider 空/无可展示字段响应仍无条件记 success 的恢复回归；仅真实可展示候选解除失败冷却，空结果保留可重试语义并新增冷却回归。
- [x] 2026-09-07：内存曲库首屏分页由两遍过滤改为单遍计数并同步维护有界排序前缀，减少 SQLite 缺失回退的 CPU 扫描，同时保持精确 `count`、稳定排序和资源上限。
- [x] 2026-09-07：内存曲库分页的兼容迭代器路径统一拒绝布尔、非整数和任意对象转换，避免异常分页输入触发不可信 `int()`；正常窗口语义保持不变，专项回归覆盖。
- [x] 2026-09-07：元数据候选热路径复用已计算的搜索词与文件名提示，缓存键构建不再重复解析同一首歌；纯函数默认接口保持兼容并新增调用隔离回归。
- [x] 2026-09-07：内存曲库分页回退正式接入页面投影：可重放缓存先计数、再只选择请求页的有序前缀；单次迭代器路径也恢复精确切页。新增升降序、稳定 tie、count 与兼容回归。
- [x] 2026-09-07：内存曲库分页回退真正接入页面投影：可重放缓存先计数、再只选择请求页的有序前缀；单次迭代器路径也恢复精确切页。新增升降序、稳定 tie、count 与兼容回归。
- [x] 2026-09-07：发布构建与恢复校验统一执行 `10 GiB` FPK 产物上限；校验器在 SHA-256 前拒绝超限文件，构建脚本在复制/解包前拒绝超限产物。新增稀疏超限文件回归，发布治理专项通过。
- [x] 2026-09-07：实体/封面 provider 的空结果不再误记为 success；仅可用结果清除失败冷却，正常空匹配进入有界 `empty_results` 计数并继续后备 provider。新增元数据回归，专项 106 项通过。
- [x] 2026-09-07：未过滤 `random100` 在大曲库中改用有界随机 rowid 探测，成功时避免全表 `ORDER BY RANDOM()`；搜索过滤、稀疏 rowid 和抽样不足自动保留原精确 SQL 回退。新增抽样上限/回退回归，完整离线门禁 1145 项通过。
- [x] 2026-09-07：metadata orphan maintenance 改为 64 行批次清理过期实体、曲目、任务和未引用 artwork，避免长期运行时一次性物化历史垃圾；新增 130 项跨批次回归并通过完整离线门禁。
- [x] 2026-09-07：metadata artwork cache 修剪改为 `SUM(size)` 加 64 行有界批次读取，避免资产数量增长时一次性物化全部缓存行；新增 130 资产跨批次回归并通过完整离线门禁。
- [x] 2026-09-07：元数据曲目页 overlay 在复制与生成 ID 前先限制为 500 行，避免异常大分页响应扩大首屏 JSON/SQLite 合并工作；新增服务回归并通过完整离线门禁。
- [x] 2026-09-06：修复可见歌曲元数据预取在连续 12 次 `pending` 后仍永久占用页级去重键的恢复死角。新增每页最多两次、3.5/7 秒静默重启；仅用于 pending/宿主通用成功 envelope，终态 `failed/no_match` 继续复用既有显式恢复路径。分页、视图切换和页面隐藏会取消，避免无限轮询或首屏二次闪烁；纯策略及 UI 回归通过。
- [x] 2026-09-06：复核按需元数据链路。后台整库补全保持默认关闭时，显式单曲请求仍可在优先 lane 中完成；本机只读 provider 烟测已返回《七里香 / 周杰伦》的 QQ 候选、专辑和封面 URL。浏览器 E2E 5/5 通过，覆盖元数据局部回填不重建歌曲列表。
- [x] 2026-09-06：首屏启动快照与后续权威分页在最终可视歌曲行一致时复用已生成的歌曲列表 HTML；不再重复生成模板、整页 DOM 对账、封面调度和布局测量。真实歌曲内容、排序、封面及播放标记变化仍走键控局部更新；Node/UI 回归通过。
- [x] 2026-09-06：复核元数据后台开关边界：后台整库补全与 Tag 写入默认关闭不影响当前歌曲、歌词页和显式单曲查询。服务及 HTTP 集成回归确认空/瞬态结果仍回投本地信息并保留有限恢复资格。
- [进行中] 2026-09-06 持续自动目标：优先推进无需真机的首屏歌曲列表加载慢/权威页回填闪烁、按需歌词/封面/专辑元数据恢复；并继续处理发布治理、资源上限与诊断、大曲库查询、前端渲染和可测试模块边界。真实手机、DAC/DSD、DLNA/AirPlay、App Center 与 Android 多机型验收明确排除。
- [x] 2026-09-06：修复应用层仍只解开三层 metadata 宿主 envelope 的差异；歌词、当前曲目和可见行请求现与策略一致，最多支持四层白名单 `data/result/payload/metadata` 包装，五层仍有界拒绝。定向回归与完整离线门禁通过（Python 1128 项 + 全部 Node/UI 回归）。
- [x] 2026-09-06：元数据完成后的歌曲行改为局部 patch，不再整行 `replaceWith`；同源封面图片、焦点、选中状态和在途加载得以保留，降低列表权威回填后的闪烁。浏览器夹具覆盖 `pending → completed` 的标题/专辑/封面回投，以及相邻稳定行的 DOM identity。
- [进行中] 2026-09-06 持续自动目标：只推进可离线验证的首屏 JSON/DOM/封面调度、按需歌词/封面/专辑元数据恢复、资源上限/诊断、大曲库查询和模块边界；持续以浏览器夹具与离线门禁防回归。真实手机、DAC/DSD、DLNA/AirPlay、App Center 与 Android 多机型验收继续排除。
- [x] 2026-09-06：首屏快照与权威页的非可视行签名漂移不再触发 DOM 替换；最终标记相同时保留已解码封面与行节点，避免列表回填闪烁，新增 UI 回归。
- [x] 2026-09-06：补齐单曲元数据/歌词显式 `retry=1` 的真实 HTTP 路由回归，确认前端恢复请求可把重试意图传至服务层并解除 provider 冷却短路。
- [进行中] 2026-09-06 持续自动目标：继续只推进无需真机的首屏歌曲加载、快照/权威页稳定提交、可见封面调度，以及元数据 provider/worker 恢复；真实设备、DAC/DSD、DLNA/AirPlay、App Center 与 Android 多机型验收保持排除。
- [x] 2026-09-06：加固元数据 job 错误记录边界，完成/重试路径拒绝非文本异常并保持 512 字符上限；新增服务回归。
- [x] 2026-09-06：抽离并收紧元数据 job 退避策略；指数重试在计算前限制尝试次数，覆盖异常计数与最大延迟回归。
- [x] 2026-09-06：修复懒加载封面同时触发行内与调度器双重重试的问题；调度器所有者标记与失败回归通过，避免重复请求和闪烁。
- [x] 2026-09-06：最新 100,000 首曲库/96 首分页基准复测完成，分页、metadata overlay、引用 hydration、分类浏览缓存及 FTS5 均保持有界且无明显回归；证据 `artifacts/large-library-benchmark-20260906-latest.json`。
- [x] 2026-09-06：收紧 provider 歌词响应 limit 的资源边界，异常数值回退到全局上限并保持 gzip/文本读取契约；元数据专项回归覆盖不可信数值对象。
- [x] 2026-09-06：将元数据瞬时 HTTP 状态判定抽为独立纯策略，当前歌曲与首屏预取共享 408/425/429/5xx 恢复语义；策略与 UI 回归通过。
- [x] 2026-09-06：元数据前端请求补齐瞬时网关状态恢复（408/425/429/5xx）；当前歌曲与可见首屏行继续使用原有取消和重试上限，UI 静态回归覆盖该契约。
- [x] 2026-09-06：收紧封面预热键策略的文本长度参数边界；非法/自定义数值不再触发隐式转换，31 项封面专项回归通过。
- [x] 2026-09-06：封面预热队列键拆分为纯策略；首屏交互仍优先曲目 ID、整库扫描仍优先文件路径，异常扫描字段不触发隐式字符串化；30 项封面专项回归通过。
- [x] 2026-09-06：provider worker 本地歌词读取改为按路径/mtime/size 缓存并限制 256 项；新增离线回归验证命中缓存与本地歌词来源保持不变。
- [x] 2026-09-06：修复通用 HTTP 200 空 envelope 导致的元数据去重锁死；前端按有界可恢复重试处理，并在最终仍无字段时释放页面资格；UI 策略回归通过。
- [x] 2026-09-06：修复歌词接口未复用统一响应解包的问题；多层宿主 envelope 下仍能正确进入歌词、封面和 pending/失败恢复逻辑；UI 静态回归通过。
- [x] 2026-09-06：修复首屏可见元数据对 artwork-only 响应的误丢弃；无候选但有合法封面时立即更新行封面，候选/歌词仍按原有恢复语义继续处理；Node/UI 回归通过。
- [x] 2026-09-06：补齐元数据 worker 丢失后的 stale `running` 任务恢复；仅在无活动 fetch worker 且任务超过 15 分钟时重排为 `retry`，避免误抢占仍在执行的任务；离线回归通过。
- [进行中] 2026-09-06 持续自动目标：首屏键控协调继续降低 DOM 比较成本；歌曲行已使用稳定签名避开逐行 clone，分组/旧节点保留兼容回退并继续离线验证。
- [进行中] 2026-09-06 持续自动目标：继续覆盖宿主桥接 envelope 的异常读取与 schema 漂移；本轮已让 `data` 解包安全降级，后续保持 provider/worker 恢复语义不变。
- [进行中] 2026-09-06 持续自动目标：元数据状态继续区分 pending、no_match 与 provider failed；前端已补充 no_match 可恢复提示，后续继续用离线响应夹具校验状态投影一致性。
- [进行中] 2026-09-06 持续自动目标：元数据响应投影继续隔离异常 provider 字段；本轮已收紧恢复判定的文本边界，后续继续用离线夹具覆盖 schema 漂移和恢复竞态。
- [进行中] 2026-09-06 持续自动目标：首屏可见元数据行若仅有本地/文件名候选或 provider 终态失败，必须保留可恢复资格；已补齐页级去重键释放，继续用离线夹具覆盖状态修订与页面切换。
- [x] 2026-09-06：统一 provider timeout 在无 deadline 场景仍尊重调用方上限，补充短超时/异常输入回归，降低当前歌曲元数据恢复延迟。
- [x] 2026-09-06：消除 eager 封面重试的空 `src` 中间态，降低旧 WebView 重试时的额外闪烁；UI 回归通过。
- [x] 2026-09-06：封面下载纳入统一 provider 时间预算，慢/失联封面源会及时释放当前歌曲优先 lane；MetadataService 回归通过。
- [x] 2026-09-06：补齐 provider 活动、曲目页缓存和 worker 重启计数的安全有界投影，避免内部计数损坏导致元数据状态接口失败；完整离线门禁通过。
- [x] 2026-09-06：候选缓存状态计数采用 `nonnegative_int` 安全投影并覆盖损坏对象、NaN 与后续命中/未命中递增，避免“元数据无法获取”被诊断接口异常放大；MetadataService 回归通过。
- [进行中] 2026-09-06 持续自动目标：继续只推进可离线验证的首屏列表闪烁收敛、元数据 provider/worker 恢复、服务端资源上限与大曲库查询；真实设备验收保持独立排除。
- [x] 2026-09-06：空 `auto/review` 投影修复期间继续回投独立歌词/封面缓存，避免历史缓存修复触发元数据空态；新增 MetadataService 回归。
- [x] 2026-09-06：修复独立歌词/封面缓存未关联 match 行时的 pending 回投；当前歌曲与首屏列表可立即复用已缓存 artwork/lyrics，不再因 match 行尚未落库而误报元数据不可用。MetadataService 专项回归通过；100,000 首曲库基准证据为 `artifacts/large-library-benchmark-20260906-current.json`。
- [x] 2026-09-06：封面增量 hydration 回收已脱离 DOM 的在途节点，避免悬挂请求占用并发槽；新增 detached-node 回归。
- [x] 2026-09-06：封面槽位回收采用 settled 活动记录，隔离 detached 节点的迟到 load/error 事件；新增并发计数回归。
- [x] 2026-09-06：补齐无 IntersectionObserver 的旧 WebView 增量封面游标，新增列表回填后的封面追加回归。
- [x] 2026-09-06：provider 候选最终过滤、去重和排序拆为纯策略 `finalize_track_candidates()`，保留有界结果契约并加入异常输入回归。
- [x] 2026-09-06：补齐 provider 候选数值边界回归，拒绝非法 limit 与非有限置信度，保持结果契约有界。
- [x] 2026-09-06：修复通用 HTTP 200 元数据 envelope 的可恢复判定，并加入 UI 静态回归，避免宿主桥接响应静默终止当前歌曲补全。
- [x] 2026-09-06：provider 曲目候选增加短时正结果缓存，减少当前歌曲轮询期间重复网络扇出；空结果和错误不缓存，保持恢复语义。
- [x] 2026-09-06：将 provider 候选缓存指标接入状态与支持诊断，保持脱敏、有界并加入诊断回归。
- [x] 2026-09-06：将首屏 UI 指标接入 Playwright 离线夹具断言，确认页面启动后可读取并保持有界；4/4 通过。
- [x] 2026-09-06：完成当前优化后的 100,000 首曲库/96 首分页离线基准，确认分页、overlay、引用补水和 FTS5 无性能回退；证据为 `artifacts/large-library-benchmark-20260906-final.json`。
- [x] 2026-09-05：补齐 eager 首屏封面的失败恢复与重试边界，覆盖浏览器直加载路径；Node/UI 回归通过。
- [x] 2026-09-05：首屏封面加载失败增加一次可取消的有界重试，保留占位音乐符号并避免完整列表重绘；Cover scheduler 回归通过。
- [x] 2026-09-05：元数据候选缓存键不再字符串化不可信对象，有限文本/数值字段保持稳定键；异常 Tag 输入可安全进入后备 provider 链路，专项回归通过。
- [x] 2026-09-05：补齐 provider 计数写入、metadata projection revision 和 worker 重启计数的安全饱和边界，避免损坏计数在下一次元数据请求时再次抛错；专项回归通过。
- [x] 2026-09-05：元数据候选与封面投影解耦，补全字段不再遮蔽同批 provider 的封面；新增 UI 策略回归并通过完整离线门禁。
- [x] 2026-09-05：首屏普通歌曲元数据预取遇到空响应时进入有界重试，避免一次临时网络/代理错误让元数据永久看似不可用；Node/UI 回归通过。
- [x] 2026-09-05：终态元数据无匹配时优先保留本地 Tag，文件名仅作为无 Tag 歌曲的最后回退；MetadataService 回归通过。
- [进行中] 2026-09-05 持续自动目标：首屏歌曲列表保持快照优先、桌面默认 96 首、键控行复用和有界封面调度；同一列表根节点已改为增量 hydration，继续以离线回归量化首个权威提交、列表 commit 与封面 hydration，真实 WebView 闪烁留待外部验收。
- [进行中] 2026-09-05 持续自动目标：元数据按需链路保持本地 Tag 即时投影、当前歌曲优先、provider 失败冷却与 worker 恢复；本地 smoke 已验证部分源可达，继续补 schema/超时/缓存恢复夹具，不把单次网络命中当作全量有效性证明。
- [x] 2026-09-05：修正桌面首屏默认 96 首对应的 UI 静态回归；源码清单 622 项，离线门禁 1090 项 Python 测试及全部 Node/UI 回归通过。
- [x] 2026-09-05：收紧 artwork ID 的首屏缺失判断，覆盖损坏缓存引用并加入策略回归，避免坏 ID 让元数据获取被错误跳过。
- [x] 2026-09-05：分页大小策略完成可测试边界拆分，异常 `localStorage`、非法值、移动/桌面视口及上限均有回归覆盖。
- [x] 2026-09-05：以桌面默认 96 首复测 100,000 首曲库分页、overlay、引用补水、分类和 FTS5；证据为 `artifacts/large-library-benchmark-20260905-page96.json`，查询与缓存均保持有界。
- [x] 2026-09-05：降低新移动端首屏分页窗口至 60 首，减少 JSON/DOM/布局工作；桌面默认和用户已保存分页设置不变，离线门禁 1087 项通过。
- [x] 2026-09-05：策略模块化后复测 100,000 首曲库分页、overlay、引用补水、分类和 FTS5；证据为 `artifacts/large-library-benchmark-20260905-final-policy.json`，趋势保持有界。
- [x] 2026-09-05：拆分可见元数据缺失判断为纯策略 `needsMetadata()`，覆盖占位 Tag、缺封面和异常输入；完整离线门禁 1087 项通过。
- [x] 2026-09-05：恢复队列当前曲目在首屏提交后按统一缺失字段策略重新挂接优先元数据 lane；完整离线门禁 1087 项通过。
- [x] 2026-09-05：拆分元数据 worker 状态投影策略，malformed provider payload 不再误记为成功；歌词故障与 artwork fallback 保持可测试的纯策略边界，MetadataService 专项 83 项通过。
- [x] 2026-09-05：扩展 100,000 首曲库离线基准，覆盖专辑分类尾页冷/热缓存与失效后有界返回；证据为 `artifacts/large-library-benchmark-20260905-tail-pages.json`，真实 NAS/WebView 仍需单独验收。
- [x] 2026-09-05：修复可见元数据预取失败后的永久去重锁死；失败/无匹配/可重试异常释放页级资格，并在元数据投影变化时重新启动有界 lane；策略回归与完整离线门禁通过。
- [x] 2026-09-05：收紧独立 artwork 缓存投影校验，仅接受合法内容寻址路径；新增非法路径回归并通过完整离线门禁。
- [x] 2026-09-05：元数据缓存判定补齐“仅封面投影”边界，避免 worker 恢复窗口隐藏已有 artwork；服务端回归与完整离线门禁通过。
- [x] 2026-09-05：修复稀疏候选导致的已缓存封面不显示，并让占位标签行继续进入元数据预取；通过 UI 回归与完整离线门禁。
- [x] 2026-09-05：补齐 artwork ID 落库前最终校验，防止异常适配器返回值污染实体/歌词/曲目缓存；完整离线门禁 1086 项通过。
- [x] 2026-09-05：专辑实体缓存回投统一使用有效 artwork ID 校验，避免分类页面受历史坏缓存影响；完整离线门禁 1085 项通过。
- [x] 2026-09-05：优化公共曲目 JSON 投影，跳过内部大字段的临时复制，降低首屏内存与序列化开销；完整离线门禁 1084 项通过。
- [x] 2026-09-05：修复歌词缓存快速路径绕过 artwork 校验的问题，避免坏封面引用继续污染前端；完整离线门禁 1083 项通过。
- [x] 2026-09-05：统一元数据封面回投边界并验证损坏缓存不会抑制当前歌曲优先补全；完整离线门禁 1082 项通过。
- [x] 2026-09-05：加入 artwork ID 一次性迁移清理，修复历史坏缓存不再自动恢复的问题；完整离线门禁 1081 项通过。
- [x] 2026-09-05：补齐封面写入并发窗口的损坏 ID 修复，确保重新下载后不会被旧异常引用覆盖；完整离线门禁 1080 项通过。
- [x] 2026-09-05：修复损坏 artwork 引用阻断重新下载/写入的问题；新增 `_store_track_artwork` 与歌词缓存回归。
- [x] 2026-09-05：追加 100,000 首曲库分页、缓存、元数据叠加、引用补水和 FTS5 离线复测，证据为 `artifacts/large-library-benchmark-20260905-final-followup.json`；结果保持有界，不替代真实 WebView/NAS 验收。
- [x] 2026-09-05：pending 元数据冷启动投影保留无 Tag 歌曲已有封面/歌词，避免 worker 恢复期间前台空白；已通过策略及完整离线门禁。
- [x] 2026-09-05：修复后台补全关闭时显式播放任务的优先级边界，当前歌曲关联的专辑元数据可继续消费；收紧 artwork ID 回投校验并加入离线回归。
- [x] 2026-09-05：修复已缓存 artwork 未回投到 `track_match` 的恢复路径，避免当前歌曲误显示无封面；通过 MetadataService 与完整离线门禁。
- [x] 2026-09-05：拆分 pending 元数据投影合并策略，保持 provider 状态与本地展示字段职责分离；通过策略及 HTTP 集成回归。
- [x] 2026-09-05：封面 `.none` 负缓存探测增加有界正向 LRU，减少大曲库列表重绘期间的重复文件系统 I/O；新增回归并通过完整离线门禁。
- [x] 2026-09-05：完成元数据 pending 展示保护后的 100,000 首曲库离线复测；分页、overlay、引用补水、分类浏览和 FTS5 均保持有界，证据为 `artifacts/large-library-benchmark-20260905-metadata-pending.json`。
- [x] 2026-09-05：修复 provider pending 时本地标题/专辑/封面被空候选覆盖的问题；保留 provider 重试语义并通过 HTTP 集成回归。
- [x] 2026-09-05：运行本地 Playwright 浏览器夹具回归并通过 3/3，覆盖桌面、移动端列表和专辑详情；真实 WebView 闪烁观察仍保留为外部验收项。
- [x] 2026-09-05：补齐冷启动本地元数据投影的封面字段并加入策略回归，保持展示优先且不触发 Tag 写回。
- [x] 2026-09-05：为首屏可见呈现策略增加异常数值输入边界，避免状态判断中的隐式对象转换。
- [x] 2026-09-05：统一首屏可见呈现检测策略，覆盖快照、歌曲页、分组页和文件夹页，避免主 UI 直接散落状态组合。
- [x] 2026-09-05：抽离首屏列表闪烁保护策略并加入纯函数回归；后续 UI 修改不得绕过该策略直接提交瞬时空列表。
- [x] 2026-09-05：收紧 UI 指标快照的数值输入边界并增加恶意对象回归，避免读取诊断时触发任意转换逻辑。
- [x] 2026-09-05：补充无标签歌曲的冷启动边界回归，确保本地回退不会遮蔽 provider 重试。
- [x] 2026-09-05：补充元数据服务冷启动嵌入歌词回退，确保本地 LRC 不因 worker 初始化竞态而延迟显示；新增 HTTP/策略回归。
- [x] 2026-09-05：追加刷新去重后的 100,000 首曲库离线基准并归档 JSON，确认分页、overlay、引用补水与 FTS5 未出现明显回退；不替代真实 WebView/NAS 验收。
- [x] 2026-09-05：补充元数据服务冷启动本地标签回退，覆盖服务对象尚未初始化时的单曲查询竞态，并加入策略回归；不替代真实 provider 网络有效性验收。
- [x] 2026-09-05：增加元数据预取延迟的有界 UI 指标，并通过策略与加载回归；为后续 provider/首屏性能对比提供证据。
- [x] 2026-09-05：刷新分页请求与普通请求共享 in-flight 去重；保留刷新绕过缓存和 epoch 旧响应保护，并加入 Node 回归。
- [x] 2026-09-05：扩展 UI 元数据响应的有界 `data` 解包至 3 层，覆盖额外宿主桥接 envelope；保持 4 层硬上限并通过回归。
- [x] 2026-09-05：生成发布恢复索引 `artifacts/RELEASE_INDEX.json`，逐版本调用校验器并区分完整证据与历史遗留缺口，不伪造旧版本 provenance。
- [x] 2026-09-05：补充元数据策略脚本加载顺序回归，防止冷启动期间响应解包函数尚未注册。
- [x] 2026-09-05：完成 100,000 首曲库分页、元数据叠加、引用补水、分类浏览和 FTS5 离线复测；结果写入 `artifacts/large-library-benchmark-20260905-current.json`，未见性能回退。
- [x] 2026-09-05：元数据回投同步刷新有界首屏快照，保持空闲写入与大小限制，降低重启后的封面占位闪烁。
- [x] 2026-09-05：元数据响应解包抽为独立可测试策略模块，覆盖直连、单层、双层和超深封装边界。
- [x] 2026-09-05：元数据状态/设置/Tag 重试接口兼容宿主桥接封装，增加 UI 回归并保持通用 API 行为不变。
- [x] 2026-09-05：元数据候选对话兼容宿主 `data` 包装，避免手动补全界面误报无候选；已加入 UI 回归。
- [x] 2026-09-05：可见歌曲元数据预取兼容直连、单层与双层宿主响应封装，补充 UI 回归，避免首屏列表元数据误判为空。
- [x] 2026-09-05：统一曲目元数据/歌词预取的直连与宿主桥接响应协议，双层 `data` 解包并加入有界回归，修复“元数据无法获取”的兼容性路径。
- [x] 2026-09-05：区分 provider 空列表与无有效候选结果并纳入脱敏诊断；继续后备源，新增离线回归覆盖元数据不可用边界。
- [x] 2026-09-05：首屏 UI 指标投影新增脱敏、有界的 `__fnAudioUiMetricsSnapshot()`，并通过 Node 回归；继续以离线指标观察首屏提交、封面 hydration 与元数据预取趋势。
- [x] 2026-09-05：全局元数据修订不再强制重载当前可见歌曲页；仅失效后续分页缓存，当前曲目/可见行继续定向回填，减少首屏二次列表与封面闪烁。
- [x] 2026-09-05：清除废弃的 metadata 整页刷新定时器路径，避免后续状态同步误触发全页重载；首屏与分页缓存失效边界保持单一职责。
- [x] 2026-09-05：首屏普通元数据预取排除当前播放歌曲，避免与当前歌曲优先歌词/封面通道重复请求和争用 provider worker。
- [x] 2026-09-05：当前歌曲元数据与歌词优先请求增加 10 秒客户端超时；超时按 AbortError 进入既有有界重试，不再占住重试窗口导致“无法获取元数据”。
- [x] 2026-09-05：普通歌曲列表元数据叠加默认不携带完整 LRC，仅歌词专用投影显式请求歌词正文，降低首屏 JSON、SQLite 合并和 WebView 解析成本。
- [x] 2026-09-05：歌词优先接口在已启动但 worker 死亡时主动恢复 fetch/priority lane，避免歌词页长期停留 pending；新增离线回归。
- [x] 2026-09-05：修复播放启动歌词优先预取的响应协议读取，兼容服务端顶层 JSON 与宿主桥接 `{data: ...}` 包装；已完成的歌词/封面不再被误判为空并耗尽重试预算。
- [x] 2026-09-05：补齐歌词优先预取的双层响应解包（请求封装层 + 宿主桥接层），避免桥接层再次包装时仍然丢失歌词/封面。
- [x] 2026-09-05：首屏可见歌曲的普通元数据预取统一使用 8 秒有界超时，慢代理不会长期占用双并发槽；取消和重试语义保持不变。
- [x] 2026-09-05：歌词失败冷却自动恢复时同步拉起已死亡的 priority worker，避免 retryable 任务仅改回 pending 却无人消费。
- [x] 2026-09-05：100,000 首合成曲库最新离线复测：首/中/尾页约 52.7/103.1/175.9ms，热页缓存约 61.5 倍，元数据叠加约 3.1 倍，FTS5 相对 LIKE 约 17.4 倍；证据 `artifacts/large-library-benchmark-20260905-final.json`。
- [x] 2026-09-05：曲目候选持久化前边界拆分：provider 候选以副本、64 条上限及有限置信度写入；布尔/NaN/无穷/异常 score 不再污染 SQLite JSON 或缓存比较，纯策略及元数据专项回归通过。
- [x] 2026-09-05：首屏可见元数据取消链路：页面级 AbortController 现在贯穿每个 provider 请求，分页/视图切换会中止已发出的可选请求；UI 回归与完整离线门禁通过。
- [x] 2026-09-05：track-page overlay 缓存一致性：缓存键加入可见投影 revision，覆盖查询/元数据提交并发窗口，避免旧封面或字段投影短暂回显；服务回归通过。
- [x] 2026-09-05：当前歌曲优先 lane 取消：切歌时主动 abort 旧歌曲的元数据/歌词请求，避免慢 provider 继续占用连接；UI 回归与完整离线门禁通过。
- [x] 2026-09-05：可见元数据去重生命周期：256 项上限改为 FIFO 淘汰而非整体清空，减少长会话翻页后的重复 provider 请求；UI 回归通过。
- [x] 2026-09-05：元数据展示候选去歧：前端按字段完整度再按置信度选择显示候选，修复稀疏 `best` 遮蔽带专辑/封面的结果；纯策略与 UI 回归通过。
- [x] 2026-09-05：元数据候选空值语义：展示策略无候选时返回 `null`，保留 pending/no-match 的有限恢复路径；纯策略与 UI 回归通过。
- [x] 2026-09-05：元数据展示输入安全边界：候选字段仅接受有限字符串/数字并隔离异常 getter，避免恶意或损坏 provider 对象中断首屏投影；Node 回归通过。

## 2026-09-05 本轮持续目标增量

- [x] 可见元数据预取重试语义：`pending` 轮询不再反复强制 `retry=1`，仅 `failed/no_match` 才武装一次显式恢复，避免慢 provider 任务持续被重排；UI 回归通过。
- [x] 元数据轮询队列公平性：活动任务保留 FIFO、退避、尝试次数和状态，重复请求只提升优先级；服务回归通过。
- [x] provider 诊断状态内部容量：成功/失败/冷却状态最多 32 项，避免长期运行诊断数据无界增长；服务回归通过。
- [x] 当前歌曲元数据轮询语义：播放后的 `pending` 查询保持普通轮询，只有 `failed/no_match` 才请求显式恢复，避免慢后备源被不断重置；UI 回归通过。
- [x] 终态重试一次性消费：显式恢复仍无匹配时不在同一预取轮次重复 `retry=1`，降低 provider 限流和队列抖动。
- [x] 歌词优先预取重试收敛：pending 不强制重排，终态恢复标记一次性消费，避免歌词/封面预取重复打源。

## 2026-09-04 本轮持续目标进展

- [x] 歌词编码回退与封面字段隔离：乱码检测会继续尝试 GB18030/Big5，损坏 image_url 不再参与候选；服务回归通过。
- [x] 歌词乱码回退：含 Unicode 替换字符的歌词不会被缓存为成功，会自动切换后备 provider；服务回归通过。
- [x] 大曲库元数据叠加基准：补充 overlay 冷/热耗时及缓存压力指标，10k 离线样本通过；继续观察更大曲库趋势。
- [x] provider 乱码候选降级：含 Unicode 替换字符的 provider 候选不再被高置信度采用，会继续后备源；网络样例与离线回归通过。
- [x] review 候选刷新边界：人工候选变化不再刷新普通歌曲列表，自动/确认投影变化仍正确失效；服务/UI 回归通过。
- [x] 元数据叠加缓存失效：队列状态变化不再清空当前页 overlay 缓存，只有可见投影变化才失效；服务回归通过。
- [x] 元数据离页刷新去噪：列表投影签名改为仅依赖服务端 projection revision，后台终态时间戳变化不再触发整页重载；UI 回归通过。
- [x] 首屏 eager 封面空白帧：首批封面也保持音乐符号至实际解码成功，避免慢 WebView 在列表提交后短暂显示空封面；UI 回归通过。
- [x] provider 结构漂移恢复：对象型错误 payload 不再伪装成空候选/`no_match`，会隔离记录并继续后备源；服务回归通过。
- [x] 元数据 pending 死队列恢复：已有排队请求现在也会执行一次有界 worker 懒恢复，避免 worker 已退出时长期 pending；HTTP 回归通过。
- [x] 当前歌曲元数据独立性：后台全库补全关闭时，显式单曲优先队列仍可完成 provider 查询；服务级并发回归通过。
- [x] 首屏元数据慢源容忍：可见页预取维持 6 首/双并发/可取消，轮询窗口扩展为最多 12 次、700ms 间隔；UI 回归通过。
- [x] 首屏列表闪烁收敛：非当前歌曲的元数据 burst 合并为 180ms 后单次 keyed patch；当前歌曲回填仍按帧展示。
- [x] 客户端分页稳定性：修复分页按钮的未定义变量，避免歌曲列表分页切换时发生脚本异常。
- [x] provider 解码边界：错误 charset 标注、受限 JSONP 与损坏响应已加入离线回归，避免元数据乱码后被静默判定为无结果。
- [x] 首屏慢 provider 重试预算：修复策略调用仍使用旧的 4 次上限，现与 12 次调度循环一致。
- [x] 首屏预取失败可观测性：网络/解析异常计入有界失败计数，AbortController 取消保持中性。
- [x] 首屏 eager 封面调度归属：浏览器已由 HTML `src` 启动的前 8 张封面会保留声明地址并退出懒加载队列，避免队列状态失真或后续增量提交重复 hydration；Node 回归通过。
- [x] 首屏封面契约同步：队列列表回归不再要求 eager 图片在解码前隐藏音乐符号，明确以图片 `onload` 后隐藏为防闪烁行为；Node 回归通过。
- [x] provider 全损坏候选恢复：搜索接口返回非空但全部含替换字符的候选时，不再被记成正常空匹配；现在标记为可恢复 provider 异常并继续后备源，避免长期 `no_match` 遮蔽当前歌曲元数据。
- [x] 元数据 provider 可观测性：状态/诊断新增受限的成功到达摘要（成功次数、距上次成功秒数），可与失败/冷却摘要区分网络不可达、正常空匹配和损坏响应，且不暴露查询词、曲目、URL 或 payload。
- [x] 大曲库离线趋势复测：10,000 首/120 首分页下首中尾页保持有界，分页、元数据 overlay、分类浏览与 FTS 搜索缓存均命中；证据 `artifacts/large-library-benchmark-20260905-refresh.json`，不替代真机验收。
- [进行中] 发布治理、资源上限、大曲库查询与核心模块边界：继续只接受低风险、可离线验证改动；真实设备验收仍独立排除。
- [进行中] 首屏歌曲列表加载/闪烁：新桌面会话默认首屏已降至 96 首，元数据 burst 已复用可见行索引、活动列和选择刷新，并恢复当前页声明式 markup 供后续状态刷新 no-op，继续覆盖 eager 浏览器加载、懒加载队列、图片失败与 keyed 行复用的交界，避免慢 WebView 出现二次调度或空白帧。
- [进行中] 元数据按需获取可靠性：后台全库补全保持默认关闭；provider worker 预热期间先回投本地 Tag 候选，再继续 provider/worker 恢复、失败冷却与歌词优先夹具，避免前台误显示“没有元数据”。
- [x] 2026-09-05：歌词视图主请求生命周期收敛：统一超时、主动取消与 AbortError 中性处理，覆盖切歌、强制轮询和页面卸载；Node UI 回归通过。
- [x] 2026-09-05：可见行与当前歌曲元数据回填统一完整候选策略，避免稀疏 best 遮蔽封面/专辑；补充 hostile ownKeys 离线回归。
- [x] 2026-09-05：候选有效性检查改为白名单字段，不再依赖 provider `ownKeys`；无展示字段候选保持空值语义，回归通过。
- [x] 2026-09-05：100,000 首曲库离线性能复测：分页、metadata overlay、引用 hydration、分类缓存及 FTS5 均保持有界且未回退；证据 `artifacts/large-library-benchmark-20260905-followup.json`。
- [x] 2026-09-05：首屏元数据预取补充有界无匹配计数，并严格区分 provider 正常空结果与 provider/网络/解析失败；UI 指标回归通过。
- [x] 2026-09-05：歌词界面关闭即取消界面所属请求与轮询，保留播放级预取；避免后台慢请求竞争首屏资源或旧歌词回写。
- [x] 2026-09-05：延迟元数据回填绑定可见页面身份，视图/分页/请求切换后旧批次不再触发无关 render，降低首屏二次闪烁。

## 2026-09-04 本轮持续目标

- [进行中] 元数据模块边界：worker 不可用时的本地 pending 投影、artwork id/URL 安全投影已抽离为纯策略，继续拆分 provider 结果规范化与任务状态转换。
- [进行中] 当前歌曲元数据优先级：本地歌词命中时仍补排缺失封面候选，继续覆盖歌词/封面并行完成顺序。

- [进行中] 首屏歌曲列表加载/闪烁：懒加载行现保留占位符直到封面解码，继续用旧 WebView/慢缓存夹具验证图片失败和行替换边界。
- [进行中] 首屏元数据预取：候选筛选已增加 ID 类型校验与页内去重，继续覆盖重复行、异常 ID 和分页切换边界。

- [进行中] 元数据交互降级：worker 短暂不可用时保留本地 Tag 投影并返回 retryable pending；继续覆盖服务重启、空 Tag 和恢复后的 provider 替换边界。
- [进行中] 元数据降级协议：曲目与歌词 pending 响应已统一纯策略，继续覆盖空响应、恢复竞态和旧客户端兼容。

- [进行中] 首屏元数据可用性：首屏绘制后对最多 6 首缺少封面/专辑/歌手的歌曲执行可取消的有界按需预取；继续用离线夹具覆盖分页切换、取消和 provider 失败恢复。
- [进行中] 首屏元数据可用性：pending/retryable 结果已增加每曲 4 次短轮询，继续覆盖慢 provider、失败冷却和页面切换竞态。
- [进行中] 首屏预取生命周期：去重键已限制为 256 项，继续用长会话夹具覆盖淘汰与页面切换竞态。
- [进行中] 首屏预取模块边界：候选筛选/重试判定已拆为纯策略，继续补充策略输入异常和旧 WebView 兼容回归。
- [进行中] 首屏预取资源生命周期：已加入共享 AbortController，继续覆盖取消时序和旧 WebView 不支持 AbortController 的降级路径。
- [进行中] 首屏预取可观测性：已增加请求/成功/失败计数，继续接入离线首屏证据输出。
- [进行中] 元数据终态边界：仅文件名候选且 provider 失败时保持 retryable，继续覆盖本地回退与远端候选替换。

- [进行中] 元数据可用性：provider 尚未就绪时先回投文件名候选，继续覆盖 provider 恢复、候选替换和失败冷却边界。
- [进行中] 元数据失败恢复：历史负缓存已提供本地身份回投，继续验证冷却后 provider 候选替换与 UI 合并。
- [进行中] 元数据临时候选生命周期：pending 文件名候选已不会抑制 provider 重试，继续覆盖候选替换和封面回投。
- [进行中] 元数据负缓存恢复：`retryable` 候选已保持有限 provider 重试，继续观察冷却与远端候选替换。
- [进行中] 元数据响应边界：空失败投影不再绕过 worker 门禁，继续覆盖恢复和状态提示的一致性。
- [进行中] 文件名兜底字段边界：仅提供标题/歌手，专辑艺术家等待可信 provider 结果。
- [进行中] 首屏可观测性：新增首次列表提交与首次封面 hydration 时间指标，继续接入离线基准输出。
- [进行中] 元数据模块边界：文件名候选已抽为纯策略，继续拆分 provider 结果规范化与持久化边界。
- [x] 100k 曲库最终离线复测：分页、热缓存、引用 hydration 与 FTS 趋势通过；真实 NAS/WebView 仍待单独验收。
- [进行中] 首屏封面预热 I/O：已优先使用索引文件身份，继续观察索引缺失和文件变更后的缓存失效边界。
- [进行中] 首屏歌曲列表加载/闪烁：继续以离线 UI 夹具和 100k 曲库基准观察首屏提交次数、封面 hydration 和旧 WebView 兼容性。

- [进行中] 首屏可观测性：新增有界 UI 会话计数，用于量化 render/list commit/cover hydration；待继续接入离线基准报告。

- [进行中] 首屏列表加载/闪烁：冷启动请求只隐藏空状态，不再提交空列表；继续用离线 UI 夹具量化首次权威提交和封面调度。
- [进行中] 元数据可用性：继续通过字符集、JSONP、schema 漂移、失败恢复夹具验证 provider 链路；真实网络命中率仍不作离线完成证明。
- [进行中] provider 网络烟测：当前只读样例已确认 QQ 封面、网易云/QQ 歌词可返回；继续依赖离线夹具与脱敏失败计数观察，不把单次命中视为全量可用。
- [进行中] 大曲库性能：第二次 100k 复测已归档，继续比较尾页 OFFSET、缓存命中和引用列表 hydration 的离线趋势。
- [进行中] 元数据投影去噪：相同歌词/封面重复提交已不再触发修订号变化；继续覆盖实体、候选和缓存损坏恢复边界。
- [进行中] 元数据投影去噪：实体与候选重复提交已纳入同一策略，继续验证缓存损坏和状态迁移边界。
- [进行中] 候选缓存规范化：等价 provider 对象的键序变化不再触发投影校正，继续覆盖缓存损坏和多候选排序变化。

## 2026-09-04 本轮持续目标

- [进行中] 首屏列表加载/闪烁：状态聚合已让路 120ms 并可在请求切换时取消；继续用旧 WebView 夹具观察实际首屏表现。
- [进行中] 元数据可用性：曲目终态现带 `retryable` 恢复标记；继续通过 provider 协议夹具和失败计数验证真实命中率，后台补全仍默认关闭。
- [x] 元数据查询映射兼容：provider 查询策略支持服务端 `sqlite3.Row`，避免字段存在却生成空查询；新增回归并通过离线门禁。
- [x] 元数据 pending 响应稳定性：已有排队任务在 worker 短暂重启窗口返回 HTTP 200 `pending/retryable`，不再误报 503；HTTP 回归和 1148 项离线门禁通过。
- [进行中] 发布治理、服务端资源上限、大曲库查询性能与模块边界拆分：本轮完成低风险离线改动，真实设备验收仍排除。
- [进行中] 首屏状态请求生命周期：延迟聚合已加入 pagehide/beforeunload 取消，继续观察旧 WebView 后台切换时的请求和闪烁。
- [进行中] 本地封面与元数据恢复：已扩展常见目录封面命名及 WebP 回退，继续用大曲库封面缓存夹具观察命中率和解码成本。
- [进行中] 引用列表元数据一致性：收藏/歌单/恢复队列已复用曲目页投影，继续观察大队列 hydration 的 SQL 与渲染成本。

## 2026-09-03 本轮持续目标进展

- [进行中] 元数据即时展示：歌词 pending 响应携带的缓存封面现在会先回投到当前歌曲；继续观察 provider 完成/失败后的字段合并。
- [进行中] 首屏封面稳定性：继续保持快照优先、键控提交和有界封面调度，真实 WebView 仍待单独验收。

- [x] 2026-09-17 持续审查未完成范围：`dlna/renderer.py`、`dlna/service.py`、`dlna/control_point.py`、`state_store.py`/`state_projection.py` 并发写、`playback/core.py`、`cover_cache.py` 剩余循环、`fnos_api.py`/`alsa_player.py` 常驻循环、Android `RemotePlaybackPlayer`/`PlaybackService`/`AuthenticatedBitmapLoader`/`FnConnectRelayConfigClient`、`app.css`/`index.html` 布局与其余 `tools/*.ps1`。真机与在线 provider 仍受本机阻塞（Gradle loopback/Unix socket），不得以离线门禁宣称全仓库无问题。〔R130 关闭（并入既有条目，不另立新项）：本条正是继任清单 L94 立文时写明「替换」的那条 2026-09-17 只列文件名的范围条目，却始终没有勾选，于是同一份欠读范围在代码桶里被计两次 —— 这就是「目标正文快照 ≠ 真实计数」漂移的一个具体来源。关闭前逐项对账，判据由 `src/tests/test_scope_entry_subsumption.py` 每次从磁盘复算，本条 16 个命名面里：12 面在继任条目逐字在案（`dlna/renderer.py`、`dlna/service.py`、`dlna/control_point.py`、`state_store.py`、`state_projection.py`、`playback/core.py`、`cover_cache.py`、`fnos_api.py`、`alsa_player.py`、`app.css`、`index.html`、`tools/*.ps1`），1 面 `PlaybackService` 在设备段在案，**其余 3 面此前全盘只有本条提及** —— `RemotePlaybackPlayer`、`AuthenticatedBitmapLoader`、`FnConnectRelayConfigClient`，关闭前已先并入继任条目（连同只有本条记录的三个角度：并发写／剩余循环／常驻循环，以及「不得以离线门禁宣称全仓库无问题」这条告诫）。并入完成后本条不再持有任何独有信息，才关闭。〕
## 2026-09-04 本轮持续目标进展

- [进行中] 首屏列表闪烁：加载中保留已有快照/可见行，避免空 DOM 中间态；继续用旧 WebView 夹具观察封面解码与权威页替换。
- [进行中] 元数据可用性：后台补全仍默认关闭，当前歌曲按需 lane 保持 worker 懒恢复、失败隔离和有限重试；继续用 provider 协议夹具复核。
- [进行中] 发布治理、资源上限、查询性能与模块边界拆分：本轮仅做低风险离线改动，真实设备验收继续排除。

## 2026-09-04 本轮持续目标进展

- [进行中] 元数据可用性：懒恢复增加有界 worker 启动确认，降低短暂 503；继续观察 provider 长期稳定性和真实曲库命中率。
- [进行中] 元数据旧负缓存恢复：缺失 job 记录的旧 `no_match/failed` 结果现在可按 `fetched_at` 冷却后重试。
- [进行中] 元数据查询消歧：已有专辑信息会作为 provider 附加提示，继续通过离线夹具观察同名歌曲命中率。
- [进行中] 首屏歌曲列表：快照优先、稳定键控提交和封面调度已完成离线回归，继续关注旧 WebView 实际首屏闪烁。

## 2026-09-04 本轮持续目标进展

- [进行中] 元数据可用性：交互请求失败/无匹配的自动恢复冷却已缩短至 60 秒，继续观察 provider 长期稳定性与真实曲库命中率。

## 2026-09-04 本轮持续目标

- [进行中] 首屏列表与闪烁：引用曲目 hydration 已合并同帧重绘，元数据接口已优先返回 SQLite 中的已有投影；继续观察部署中的旧 WebView 首屏、封面闪烁和大曲库实际体验。
- [进行中] 首屏 DOM 稳定性：稳定顺序的键控行不再临时移出列表，继续用离线回归覆盖增删/重排与封面调度边界。
- [进行中] 启动快照生命周期：权威页到达后已退休旧快照命中标记，继续观察空响应保护与扫描完成后的状态转换。
- [进行中] 启动快照安全边界：恢复前已限制快照条目数量，继续补充异常条目形状回归。
- [进行中] 启动快照条目形状：已过滤无稳定 ID 的异常行，继续观察旧快照兼容性。
- [进行中] hydration 生命周期：视图切换时已释放旧批次待执行动画帧，继续以离线竞态夹具观察取消/重入边界。
- [进行中] 大曲库查询基线：2026-09-04 100k 离线复测已归档，继续关注尾页 OFFSET、跨视图切换和旧 WebView 绘制成本。
- [x] 100k 曲库最新离线复测：尾页 OFFSET 0.170 秒、热页缓存约 57.6 倍、FTS 相对 LIKE 约 17.9 倍；证据为 `artifacts/large-library-benchmark-20260904-followup.json`。
- [x] provider 输入行兼容：MetadataProviders 对服务端 `sqlite3.Row` 做有界物化后再进入适配器，避免合法字段被误判为查询失败；已通过 MetadataProviders 回归。
- [进行中] 元数据可用性：QQ 链路在当前网络 smoke 可返回封面，组合 provider 可回退；worker 短暂重启时接口会先返回已有缓存投影，不再遮蔽已获取结果；继续通过部署状态、失败计数和受限夹具复核，不将单次网络成功视为全量数据源验收。
- [进行中] 当前歌曲元数据回投：歌词预取已同步回投合法封面并合并同帧刷新，继续观察 provider 结果和旧 WebView 图片解码体验。
- [进行中] 当前歌曲封面恢复：已有嵌入歌词但无封面的歌曲不再跳过优先元数据 lane，继续观察缓存命中与 provider 回退。
- [进行中] 歌词页稳定渲染：预取回投已修复参数丢失，继续观察旧 WebView 的歌词高亮与滚动表现。
- [进行中] 歌词终态恢复：播放预取已覆盖 `failed/no_match` 的有限 `retry=1` 恢复，继续观察 provider 回退与失败计数。
- [进行中] 本地歌词探测性能：已加入 256 条有界文件身份缓存，继续观察大曲库轮询 I/O 和旧 WebView 展示成本。
- [进行中] 本地歌词缓存并发：已增加线程安全单飞保护，继续观察多客户端并发歌词请求。
- [进行中] 元数据响应边界：缓存/歌词可用性判定已抽为纯策略并有独立回归，继续按可测试边界拆分服务端编排。
- [进行中] 歌词可用性：本地/SQLite 歌词现在优先于 worker 存活检查，避免已有歌词在服务重启时误报不可用；继续观察 provider 回退和旧 WebView 展示。
- [进行中] 元数据回投绘制：歌词与候选回投已合并同帧并按曲目隔离，继续观察旧 WebView 的图片解码和投影更新成本。

- [进行中] provider 请求兼容性：已在 JSON/歌词公共请求层补齐默认浏览器身份，防止新适配器遗漏头信息；仍需部署侧观察各来源实际限流、地区限制和结构变动。

## 持续推进（无需真机）

- [进行中] 2026-09-04 元数据空成功投影与首屏稳定性：已修复历史 `review/auto` 空结果导致当前歌曲元数据长期静默的问题；继续观察部署中的 provider 状态、首屏闪烁和真实曲库表现。

- [进行中] 2026-09-04 provider 延迟复核：MusicBrainz 回退已设置 4 秒交互上限，继续通过离线夹具观察失败隔离和区域 provider 回退，不以单次外网结果判定数据源有效性。

- [进行中] 2026-09-03 首屏加载与元数据可用性复核：离线门禁 1130 项通过；咪咕 HTTPS 端点和显式当前歌曲优先 lane 已确认，继续观察实际部署中的 provider_failures/worker 状态与旧 WebView 首屏闪烁。

- [x] 当前歌曲歌词预取：播放/恢复时按曲目去重预取歌词，歌词页优先复用已返回正文；已通过 UI 静态回归和完整离线门禁。

- [x] 启动封面预热降竞争：不再为预热整库读取 SQLite，首屏分页优先；已通过服务端源码契约和完整离线门禁。

- [x] 元数据交互等待窗口：当前歌曲预取与候选对话扩大为 12 次有界轮询，降低慢源结果被 UI 过早放弃的概率；已通过 UI 回归和完整离线门禁。

- [x] 元数据轮询契约同步：更新歌词优先级测试以锁定 12 次常量预算；完整门禁最终 1130 项通过。

- [x] 播放歌词 pending 回投：当前歌曲预取遇到 pending/临时错误时执行最多 12 次间隔重试，成功后回投歌曲缓存；已通过歌词优先级回归。

- [x] 发布证据索引编码稳定性：验证失败条目改用 ASCII 稳定说明，重新生成恢复索引并验证 0.2.34 完整证据；历史 0.2.33 provenance 缺失仍明确保留为 legacy incomplete。

- [x] provider gzip 增量解压：JSON/歌词响应在解压过程中执行资源上限检查，避免压缩响应造成瞬时内存放大；已通过 1121 项离线回归。

- [x] 元数据回投筛选缓存一致性：原地更新歌曲字段时同步失效筛选 memo，避免搜索/排序继续使用旧元数据；已通过 UI 回归。

- [x] 元数据封面地址写入校验：歌词与候选回投拒绝超长、非 HTTP/HTTPS 或损坏 URL，避免无效地址遮蔽后续封面；已通过 UI 回归。

- [x] 前端筛选排序重复计算收敛：普通库、收藏和歌单视图复用单项有界 memo，输入数组或搜索/排序条件变化自动失效；已通过 UI 回归。

- [x] 队列分页重复遍历收敛：同一渲染周期复用按搜索/排序条件缓存的队列展示结果，减少大队列过滤排序开销；已通过 UI 回归。

- [x] 当前歌曲元数据冷却重武装：同曲目在有界重试耗尽后等待 30 秒并最多恢复 2 轮，避免短暂 provider 故障造成永久空元数据；已通过 UI 静态回归。

- [x] 分组/专辑封面 URL 异常隔离：在线回退地址损坏时安全保留占位图标，不影响其它分组和歌曲渲染；已通过 UI 与完整离线回归。

- [x] 空 best 元数据投影回退：前端正确消费候选列表中的首项，避免有效元数据因空 best 占位被忽略；已通过 UI 与完整离线回归。

- [x] 封面 URL 异常隔离：坏的历史/provider 地址不会中断首屏列表渲染，单行回退音乐符号；已通过 UI 与完整离线回归。

- [x] 元数据候选封面端到端回投：覆盖 worker 提交、`metadata_tracks` 落库与曲目页投影，确保后台成功结果能进入 UI；已通过离线回归。

- [x] 元数据候选完整度合并：同曲目去重优先保留含封面/完整字段的候选，避免元数据获取成功但 UI 仍无封面；已通过策略与完整离线回归。

- [x] provider 候选扇出行为级回归：确认完整高置信候选可提前停止，缺封面候选仍继续后续来源回退；已通过元数据专项与完整离线门禁。

- [x] 元数据 worker 交互式懒恢复：抓取池异常退出时由请求路径执行一次串行恢复，避免短暂 503 伪装成永久不可用；已通过离线 HTTP 回归与完整门禁。
- [x] 当前歌曲元数据恢复重武装：服务恢复后允许同曲目重新进入一次已耗尽的预取链，避免短暂 worker 故障留下永久空元数据；已通过 UI 与完整离线门禁。
- [x] 元数据页面校正合并：连续任务完成只触发一次可取消、带请求键校验的分页刷新，避免大曲库重复 DOM/封面工作；已通过 UI 与完整离线门禁。
- [x] 元数据状态采样恢复：状态轮询可恢复曾启动后退出的 worker 池，避免当前歌曲预取耗尽后长期停留在不可用；未启动服务仍保持惰性。
- [x] 元数据 lane 可用性边界拆分：线程存活/曾启动策略抽至 `metadata_lane_policy.py` 并独立测试，降低 server.py 耦合。
- [x] 空 metadata lane 误报修正：空线程池不再返回可用，避免元数据任务永久 pending；已通过专项与完整离线门禁。
- [x] 元数据页面校正取消：切换视图时取消旧校正定时器，避免旧页面刷新污染新页面；已通过 UI 与完整离线门禁。
- [x] 曲目页元数据投影缓存：对短时重复分页请求复用有界 LRU JOIN 结果，并在元数据变更时失效；已通过专项与完整离线门禁。
- [x] 曲目页投影缓存 TTL 一致性：缓存过期后重新执行 SQLite 查询，避免新元数据被旧投影遮蔽；已通过专项与完整离线门禁。
- [x] 元数据 worker 重启可观测性：状态快照暴露有界恢复次数，便于定位元数据不可用原因；已通过专项与完整离线门禁。
- [x] 曲目页投影缓存可观测性：状态快照暴露命中/未命中与容量压力，便于定位列表加载瓶颈；已通过专项与完整离线门禁。
- [x] 曲目页投影缓存基础字段指纹：扫描更新同 ID 的 Tag/封面时强制重新投影，避免短缓存显示旧数据；已通过专项与完整离线门禁。

- [x] 歌词服务不可用状态前端收敛：`/api/lyrics` 返回 503/`unavailable` 时显示明确原因并停止无意义轮询；服务恢复后由用户重新打开歌词页触发重试。
- [进行中] 首屏歌曲列表稳定渲染与封面闪烁继续观察：保持快照优先、增量提交和有限封面调度；列表行更新现在会移动同 URL 的已解码封面节点，继续用离线 UI 回归观察旧 WebView 行替换。

- [x] 跨页/搜索键控行复用：分页、搜索或顺序变化时按稳定 key 移动未变化行，避免整表替换丢失已解码封面；旧行明确移除，已通过 UI 回归。

- [x] 键控列表去重复杂度：稳定 key 校验采用线性 `Set`，避免最大 500 行页面的二次方扫描；已通过 UI 回归。

- [x] 元数据状态更新时间指纹：状态签名增加有界任务更新时间，避免同数量状态下后台新结果不触发列表校正；已通过服务端/UI 回归。

- [x] 元数据投影单调修订号：补充进程内有界 revision，覆盖同秒多任务更新的状态签名碰撞；已通过服务端/UI 回归。

- [x] 元数据状态刷新去噪：排队和领取任务不再触发投影修订，更新时间指纹仅统计终态；已通过离线回归。

- [x] 元数据投影 revision 路径校正：任务入队不再改变 revision，曲目候选落库会改变 revision；已通过专项回归。

- [x] 封面版本缓存正确性复核：拒绝可能掩盖 CUE 同秒变更的 TTL 方案，保持实时文件版本校验；完整封面回归通过。

- [x] 稳定列表无搬运提交：行 identity/order 未变化时跳过 `DocumentFragment` 重排，减少状态刷新触发的布局工作；已通过 UI 回归。

- [x] 过期分页响应加载保护：旧请求不得清理新请求的加载状态，避免视图/搜索快速切换时短暂闪现空列表；已通过 UI 与完整离线门禁。
- [x] 权威分页元数据合并边界：分页响应缺少字段时保留当前会话已回投的歌词/封面/补全值，显式服务端字段仍覆盖；已通过源码清单与离线门禁。
- [x] 跨视图元数据缓存合并：分页返回复用有界 `itemCache` 的已补全字段，避免离开页面后回来出现封面/歌词闪回；已通过 UI 与完整离线门禁。
- [x] 页面元数据合并策略模块化：抽离为 `library_metadata_merge_policy.js` 并独立回归，降低 UI 核心耦合；已通过完整离线门禁。
- [x] 元数据来源标记回退：空 `metadata_source` 不再遮蔽缓存中的非空来源信息；已通过策略回归与完整离线门禁。

- [进行中] 首屏与大曲库体验：继续用离线基准审计首屏、收藏/播放列表和分组页面，优先消除重复请求、空列表中间态与无意义 DOM 重建；2026-09-03 已完成最新 100k 曲库趋势复测并归档性能证据。
- [x] 页面元数据合并后 100k 曲库趋势复测：首屏/尾页、热缓存、FTS5 搜索均未退化；证据 `artifacts/large-library-benchmark-20260903-merge.json`。
- [x] 首屏状态轮询并行化：音乐库与元数据状态不再串行等待，降低大曲库慢聚合导致的进度停顿；已通过完整离线门禁。
- [x] 首屏状态并行契约：新增 UI 静态回归锁定 `Promise.all` 请求形状，防止性能优化回退。
- [x] 首屏状态先行提交：并行请求中先提交音乐库状态，再合并元数据状态，避免慢元数据超时拖住扫描进度；已通过 UI 与完整离线门禁。
 - [x] 播放会话恢复时提升当前曲目元数据：应用/浏览器重启恢复逻辑队列后立即进入当前歌曲优先通道，不再等待下一次播放命令或打开歌词页。
- [x] 首屏权威页资源让位：冷启动时即便已命中本地快照，恢复队列的批量补水等待权威分页响应完成；已有 UI 回归覆盖，避免与首屏 SQLite/JSON/封面任务竞争。
- [进行中] 首屏封面稳定绘制：有本地封面的行直接隐藏占位符，失败时再回退音乐符号；首屏前 8 张封面直接设置 `src` 并使用 eager + high priority，其余保持 lazy，继续用慢解码/缓存命中夹具验证无闪烁。
- [进行中] 元数据可靠性：保持按需歌词优先、严格解码和失败可观测；曲目、实体、歌词和封面现统一使用有界查询策略，曲目候选增加 MusicBrainz recording 回退，并在标题缺失时安全回退文件名检索，继续为各 provider 增加可重复的离线协议/解析回归，不把单次网络未命中判成数据源失效。
- [x] Kugou provider TLS 端点：搜索与歌词请求改用 HTTPS，降低明文端点被 NAS 代理拦截导致的元数据空结果；已通过离线契约与完整门禁。
- [x] 当前歌曲专辑元数据优先：后台补全关闭时，播放/歌词页触发的专辑详情与封面任务进入受限优先队列；离线回归已覆盖，避免只补歌曲候选而遗漏专辑信息。
- [x] 无 Tag 文件名检索增强：对常见“歌手 - 歌名”文件名仅在查询回退阶段拆分歌手与标题，提升无 Tag 歌曲的 provider 命中率且不修改原始展示字段；已通过查询策略回归。
- [x] 文件名分隔符兼容：同时支持“歌手-歌名”无空格形式，避免常见导出文件名失去检索线索。
- [x] 部分 Tag 文件名检索增强：标题已存在但歌手缺失时，若文件名右侧与标题一致，则补入文件名左侧歌手作为查询提示；不覆盖原始 Tag。
- [x] 元数据字段级安全写入：歌词、封面来源/ID及置信度异常值不会中断缓存落库；已通过离线回归。
- [x] 元数据缓存时间安全读取：历史缓存中的非法、负数或非有限时间不会阻断专辑/曲目元数据响应；已通过离线回归。
- [x] 实体元数据落库容错：专辑/歌手保存拒绝异常 provider 对象、异常置信度并使用安全 JSON 回退，避免单字段损坏令整项元数据任务失败；已通过离线回归。
- [进行中] 元数据封面多源回退：歌词任务在网易云/QQ 无结果时复用曲目候选链获取其他来源封面；继续补充 provider schema 与失败恢复回归。
- [x] 后续候选封面落库：最佳候选无封面时仍保存后续 provider 的首个可用封面，不改变字段匹配优先级；已通过 worker 回归与完整离线门禁。
- [x] Artwork 重复下载收敛：已有曲目资产时在下载前短路，降低元数据重试的网络与 CPU 开销；已通过服务回归。
- [x] library status 摘要短缓存：复用 2 秒 SQLite 计数摘要并在索引写入时失效，减少首屏状态轮询开销；已通过缓存回归。
- [x] library status 摘要失效回归：索引写入后立即读取新曲目数与签名，避免短 TTL 缓存遮蔽扫描结果。
- [x] library 摘要缓存资源上限：数据库路径缓存限制为 32 项并淘汰旧条目，避免长期多配置运行无界增长。
- [x] 摘要缓存历史超限收敛：旧版本遗留超限 map 时，新插入会循环淘汰至严格 32 项上限。
- [x] 摘要缓存更新键超限收敛：更新已有键时同样压回 32 项上限，避免旧状态绕过资源边界。
- [x] 摘要缓存文件指纹校验：外部替换 SQLite 文件时立即跳过旧摘要，避免短 TTL 内状态滞后。
- [x] 当前歌曲元数据缓存回投：播放优先通道同步更新有界 `itemCache`，避免恢复队列歌曲切换页面后元数据回退。
- [x] 当前歌曲页面缓存定向失效：元数据回投仅删除包含该曲目的分页响应，避免旧缓存遮蔽新结果并保留其它页面热缓存。
- [x] 歌词 provider 失败时保留封面回退：无歌词结果仍允许一次受预算限制的曲目封面/候选查询；有歌词结果则不重复扇出，已通过离线回归。
- [x] provider 非对象结果隔离：歌词、曲目封面和实体落库对列表/字符串等异常响应安全降级，避免无关任务被错误重试；已通过离线回归。
- [x] 曲目封面回退字段边界：候选封面、来源和 provider ID 统一使用有界文本投影，异常对象不会中断当前歌曲回退链；已通过离线回归。
- [进行中] provider 候选字段边界：候选字段投影已拆为纯模块，艺术家、专辑名、封面 URL、JSONP 响应和 provider 路由字段均有界兼容，继续为各数据源补充协议形状与异常值回归。
- [x] 候选来源字段安全落库：自动匹配的 source/provider ID 使用有界投影后写入，避免异常字段污染缓存；已通过离线回归。
- [x] 曲目候选置信度容错：候选评分字段异常时安全降级，并在 JSON 持久化前再次规范化；已通过离线回归。
- [进行中] provider 路由性能：中文曲目优先区域数据源、国际曲目优先 MusicBrainz；继续用离线 fixture 覆盖顺序与失败回退，不以单次外网请求作为可用性结论。
- [进行中] provider 请求扇出性能：完整高置信候选命中后提前停止后续源请求；继续补充稀疏候选、封面缺失和异常响应回归。
- [进行中] 元数据失败链路收敛：歌词 provider 已失败时跳过同一任务的二次封面网络扇出，继续补充失败/无匹配边界回归。
- [x] 协议相对封面地址：`//host/path` 在候选投影和下载入口规范化为 HTTPS，避免可用候选因 URL 形状导致封面获取失败；已通过离线回归。
- [x] 封面下载输入边界：拒绝非文本 URL，避免异常 provider 对象触发字符串化并中断元数据任务；已通过离线回归。
- [x] 封面协议限制：下载器仅接受 HTTP/HTTPS，拒绝非网络 scheme；已通过离线回归。
- [x] 简繁元数据匹配：provider 返回繁体歌名/歌手而本地 Tag 为简体时，候选评分使用有界等价折叠；不改写展示/Tag，自动确认阈值不降低，已通过专项回归与外部源离线探测。
- [x] 元数据评分异常输入隔离：只接受文本标题/歌手，候选标题缺失时不允许歌手字段单独构成匹配；已通过专项回归。
- [进行中] 当前歌曲封面优先：完整 Tag 但缺少封面的正在播放歌曲必须进入优先候选链；provider 单源异常应隔离并继续回退链。MusicBrainz recording 候选现在可从有效发行版本生成 Cover Art Archive 封面地址。
- [进行中] 播放选中与元数据时序：浏览器保存播放队列时同步提升当前歌曲的歌词、封面和候选任务优先级，继续用离线回归覆盖队列保存与元数据 worker 的竞态。
- [进行中] 元数据自动恢复：终态 provider 失败超过冷却窗口后，在下一次用户查看歌词/候选时有界重置为 pending；不启用全库后台扫描，也不形成紧密重试循环。
- [x] 曲目候选显式失败恢复：用户点击“重新查询此歌曲”时同时重置 `failed/no_match` 候选缓存；已新增离线回归，仍不触发全库扫描。
- [x] 陈旧 no_match 自动恢复：与 provider failed 一样，超过 60 秒冷却后在用户可见的歌词/候选请求中重新排队，避免短暂空结果长期阻断元数据；已通过专项与完整离线门禁。
- [x] 首屏空响应保护：已有快照时对异常空页执行一次短延迟重试，避免网络/代理瞬时空响应造成歌曲列表闪烁；显式刷新不受保护逻辑影响。
- [x] 首屏空响应缓存竞态：重试前清理对应空页的会话缓存，避免“重试”再次读取同一空响应；已通过 Node/UI 与完整离线门禁。
- [x] 首屏空响应策略边界：仅作用于已有快照的普通分页歌曲页，分组、文件夹和显式刷新保持原有语义。
- [x] 首屏重试视图竞态：延迟重试绑定请求键并在视图切换时失效，避免旧定时器加载错误页面。
- [x] 首屏快照与用户状态竞态：已有快照而歌曲页仍加载时，用户状态水合不再重复整页渲染；仍立即更新播放器、导航与控制状态，权威页负责最终一次列表提交。
- [x] 首屏预热入队去同步磁盘检查：缓存命中探测转入后台预热 worker，降低慢存储上的分页响应延迟；已通过封面专项回归。
- [进行中] 显式歌词页元数据联动：打开歌词页时除歌词任务外，按需补排缺失歌手/专辑/封面的单曲候选任务；保持后台全库补全默认关闭。
- [x] 首屏空状态闪烁与歌词页封面补排：首个权威列表返回前隐藏空库提示；完整 Tag 但缺封面的歌词页请求会补排单曲候选；已通过专项回归，待完整门禁记录。
- [x] 专辑艺术家封面回退一致性：歌词接口与专辑任务使用相同的 album_artist 缓存键，避免合辑曲目封面误判缺失；已通过专项回归。
- [x] 专辑/歌手 provider 异常回退：隔离第三方 schema 漂移并继续后续数据源；已通过专项回归。
- [x] 曲目候选缓存损坏恢复：非人工确认的异常 `fields_json` 自动转为受限 pending；confirmed 记录保留原状态；已通过专项回归。
- [x] provider 失败与无匹配状态分离：失败不再写入长期 `no_match` 负缓存，保留重试和失败诊断；已通过专项回归。
- [x] provider 状态判定并发隔离：使用 worker 线程本地失败标记，避免并发任务改变彼此的 `failed/no_match` 结果；已通过专项回归。
- [x] 冷启动队列补水让位首屏：首次恢复大队列时等待首页分页完成后再批量补水，降低首屏慢加载与闪烁；已通过 UI 回归。
- [进行中] 歌词无匹配终态：区分 `no_match` 与 `pending`，避免无匹配任务被永久伪装成排队中；重开歌词页可按冷却/显式重试策略恢复。
- [进行中] 发布治理、资源上限与模块边界：每次源码改动更新清单、运行完整离线门禁并记录可复现性能证据。
- [x] 元数据 worker 状态策略拆分：最终状态与有限重试判定抽至 `metadata_job_policy.py`，降低线程编排与状态规则耦合；已通过独立及完整离线回归。
- [x] 元数据数值策略模块化：置信度投影抽至独立纯模块并由四类落库路径复用；已通过独立与完整离线回归。
- [x] 元数据策略异常值隔离：封面引用和来源字段仅接受有界文本，拒绝对损坏 JSON 值执行任意字符串化；已通过专项与完整离线门禁。
- [x] 歌词正文请求预算收口：咪咕、JOOX、千千的 LRC/JSONP 下载改走与搜索相同的总预算、gzip 和大小限制，避免弱网下绕过优先歌词任务的上限；已通过元数据专项回归，待本轮完整门禁记录。
- [x] 元数据完成后的列表缓存校正：状态轮询仅在已提交元数据投影发生变化时清理页面 LRU 并增量刷新，pending 进度不触发整页重绘；已通过完整离线门禁。
- [x] 候选确认后的即时回投：用户确认曲目元数据后立即刷新当前可见页，避免等待状态轮询；已通过 UI 回归和完整离线门禁。
- [x] 元数据状态探测有界化：状态接口采用独立 1.5 秒超时，不阻塞音乐库状态刷新；已通过 UI 回归和完整离线门禁。
- [x] 元数据投影策略模块化：投影签名抽为独立纯模块并增加边界回归，便于后续维护和恢复；已通过完整离线门禁。
- [x] 缺失歌手 Tag 的匹配评分：将“未知艺术家/未知歌手”等展示占位词视为空值，避免标题匹配被错误扣分；已通过元数据专项及完整离线门禁。
- [x] 元数据匹配策略模块化：文本规范化与 provider 评分抽为 `metadata_match_policy.py`，保留服务兼容导出并增加独立边界；已通过完整离线门禁。
- [x] 动态 API 缓存头：`/api/*` JSON 禁止 WebView/代理复用旧响应，避免元数据状态和列表投影滞后；HTTP 集成及完整离线门禁通过。
- [x] 元数据投影异常输入隔离：签名策略拒绝对象、Symbol、超长数值和控制字符，避免状态轮询异常与缓存抖动；独立 Node 回归及完整离线门禁通过。
- [x] 元数据开关状态文案：明确区分后台补全关闭与队列完成，保留播放/歌词页按需获取提示；UI 回归及完整离线门禁通过。
- [x] 标题-only 元数据候选回归：使用离线 provider fixture 验证无歌手/无专辑歌曲可进入候选链；元数据专项及完整离线门禁通过。
- [x] 大曲库缓存复测：20,000 首合成曲库分页、补水、分组和搜索基准通过，证据已归档；暂未发现查询退化热点。

- [x] 刷新期间避免中间整页重绘：扫描进度只更新计数装饰，保留已显示歌曲行和封面解码状态；已通过 UI 与完整离线回归。
- [x] 增量行提交的封面队列稳定性：播放/收藏等少量行状态变化不再重建整页封面观察器，仅发现新封面节点或空闲恢复时调度；已通过 UI 回归。
- [x] 收藏/歌单/恢复队列的批量补水缓存：按 ID 查询接入有界 SQLite 查询缓存，保持顺序、深拷贝隔离和索引写入后失效；20k 离线基准确认热读约 11.2 倍加速，专项回归通过。
- [x] 本地歌词即时回退：`/api/lyrics` 优先返回嵌入/同名 `.lrc` 歌词，不等待外部 provider；已通过元数据与完整离线回归。
- [x] 封面先到、歌词后到的状态修复：仅有 artwork 的缓存记录仍会继续排队歌词，不再误报“已完成但空歌词”；已通过元数据与完整离线回归。
- [x] 本地歌词与缓存封面一致性：本地歌词即时命中时继续返回同一曲目的缓存 artwork，避免歌词页封面短暂空白；已通过元数据与完整离线回归。
- [x] 歌词缓存判定边界拆分：`metadata_lyrics_cache_policy.py` 独立判断非空、未过期歌词，隔离 artwork-only 与异常时间输入；已通过专项及完整离线回归。
- [x] Provider 响应编码协商：统一声明 JSON 与 gzip，拒绝代理返回未支持压缩格式造成的伪 JSON 失败；已通过 provider 回归及完整离线回归。
- [x] 元数据服务不可用响应：`/api/lyrics` 在 worker 未启动时返回结构化 503，不再把服务故障伪装成空歌词；已通过完整离线回归。
- [x] 单曲候选负缓存人工恢复：`no_match` 对话框提供明确的“重新查询此歌曲”，只重置该曲目的终态负缓存并优先排队；后台全库补全仍默认关闭，旧候选响应由请求令牌隔离；已通过元数据、Node UI 与完整离线回归。
- [x] 首屏状态更新布局收敛：无歌曲行、表头或分页变化的播放/收藏刷新不再排队全列宽测量和分页可见性布局工作；resize/观察器路径保持可用；已通过 Node UI 与完整离线回归。
- [x] Tag 写回独立运行：明确开启 Tag 写回时，即使后台全库元数据补全仍关闭，已缓存的歌词/封面也能按低速队列写入；默认关闭语义不变；已通过元数据与完整离线回归。
- [x] 元数据 reconcile 查询合并：歌词和曲目匹配缓存过期时间改为单次流式 LEFT JOIN 读取，消除大曲库每首歌两次额外 SQLite 查询；已通过专项与完整离线回归。
- [x] 交互式封面预热去重：已有当前版本正缓存或负缓存的歌曲不再重复进入预热队列，源文件版本变化仍会重新生成；已通过封面专项与完整离线回归。
- [x] 元数据结果回投列表：`/api/library` 按页批量合并已缓存歌词、确认后的曲目字段和 provider 封面，保留 Tag 优先级并限制 artwork ID；已通过元数据、library presentation 与完整离线回归。
- [x] 曲目页缓存查询合并：歌词与已确认匹配改为一次有界 LEFT JOIN，减少列表首屏元数据回投的 SQLite 往返；已通过专项与完整离线回归。
- [x] 表头事件绑定去重：表头结构未变化的播放/收藏刷新不再重复绑定排序与列宽事件；模式/列设置变化仍会重新绑定；已通过 Node UI 与完整离线回归。
- [x] 当前歌词封面回退：曲目缓存没有 artwork 时复用同专辑缓存封面，避免歌词优先请求期间封面空白；已通过元数据与完整离线回归。
- [x] Provider 歌词严格解码：QQ、酷狗、JOOX 等 base64/文本歌词改为有界严格 base64 与 UTF-8/GB18030/Big5 解码；损坏响应记录为 provider 失败而非静默空歌词，含 JOOX JSONP 回归并通过完整离线门禁。
- [x] Provider 失败状态投影边界：数据源失败摘要拆至 metadata_provider_failure_policy.py，最多 16 项并限制名称、计数、错误文本和冷却时间；保持无匹配/协议失败语义可区分，已通过专项及完整离线回归。
- [x] 歌词终态失败的显式恢复：自动轮询保持有界；用户重新打开失败歌词页时才以 `retry=1` 重置对应优先任务，避免永久失败又避免无限自动重试；已通过服务与 UI 回归。

- [x] 首屏列表增量提交：快照与网络响应仅有少量曲目行变化时按稳定行键局部替换，避免整表重建造成封面重新解码和可见闪烁；已通过完整离线回归。
- [x] 封面运行时属性导致的二次闪烁：行增量提交比较时归一化 `src`、封面队列标记、完成态及回退图标可见性，避免播放/收藏刷新丢弃已解码封面；已通过 UI 回归。
- [x] 相对封面 URL 的比较边界：封面调度器保留原始声明地址，避免浏览器绝对化 `src` 后重新触发行替换；歌词服务错误在前端以 180 字符上限保留原因，已通过 UI 回归。
- [x] 分组/目录状态刷新表头空转：表头按模式、列模板和标记签名复用；未变时不再重建排序/列宽控件或强制额外布局，已通过 UI 回归。
- [x] 分组/目录缓存基准覆盖：离线基准分别验证专辑、文件夹、根目录的冷/热读取、结果一致性和命中计数；20k 样本证据已归档。
- [x] 创作者专辑范围查询基准覆盖：验证歌手/作曲者进入专辑页的 CTE 路径也具有冷/热缓存、结果一致性和命中计数；20k 样本证据已归档。
- [x] 首屏用户状态并发渲染收敛：无快照且首批歌曲尚未返回时，用户状态水合仅投影播放器/导航，不再先提交空列表再替换为歌曲页；已通过 UI 与完整离线回归。
- [x] 元数据响应字符集兼容：按 Content-Type 声明并以 UTF-8/GB18030/Big5 有界回退解析 provider JSON，避免第三方接口编码异常导致字段丢失；已通过完整离线回归。
- [x] 单曲元数据候选自动刷新：候选任务处于 pending 时在对话框内进行最多 8 次有界轮询，关闭对话框立即取消，避免用户反复打开才能看到结果；已通过完整离线回归。
- [x] 曲目候选封面落库：track 匹配任务取得图片候选时同步写入 `metadata_tracks` 资产，覆盖无专辑 Tag 的歌曲展示与后续 Tag 写回；已通过完整离线回归。

## 2026-09-01 持续目标推进（无需真机）

- [x] 首屏歌曲列表增加受限本地快照：优先绘制最近成功页面，网络响应仍负责校正，减少大曲库冷启动空白与闪烁。
- [x] 元数据候选/歌词接口投影失败状态、尝试次数和有限错误原因，便于区分无匹配、重试中与 provider 失败。
- [x] provider 失败按数据源聚合并脱敏投影到状态页；空候选明确记录为 `no_match`，避免误显示为待人工审核。
- [x] 元数据候选界面对 `no_match` 与 provider 错误给出区分提示，避免把失败显示成“已确认”。
- [x] 列表行增加 `content-visibility` 渐进渲染提示；支持的浏览器跳过首屏下方布局，旧 WebView 自动忽略。
- [x] 播放会话恢复的队列详情改为有界并发批量请求，保留顺序、失败隔离和缓存回退，缩短大队列启动阻塞。
- [x] 首屏页面快照改为空闲时持久化，避免网络首批歌曲渲染后同步序列化/写入抢占主线程。
- [x] 元数据 provider 短时熔断：连续失败只冷却故障来源，避免大曲库网络不可用时每首歌重复等待超时。
- [x] 重新生成 100k 曲库离线基准：分页查询峰值约 611KiB，FTS5 trigram 相对 LIKE 约 17.2x；证据 `artifacts/large-library-benchmark-20260901-latest.json`。
- [x] 大曲库分页缓存基准：100k 样本记录冷读/热读与命中计数；第一页冷读约 45ms、热缓存约 0.54ms，同页响应保持独立副本，证据 `artifacts/large-library-benchmark-20260901-cache-audit.json`。
- [x] 真实设备、DAC/DSD、DLNA/AirPlay、App Center 与 Android 多机型验收继续保留为外部验收项。 〔R138 X1=A 迁移：本条不属代码桶，文本原样移入下方设备段（迁入后在盘上为 L1878）——代码桶本轮由 10 降为 2（迁出本条并关闭 7 条），设备段 44 → 45，开放总数不因迁移而变化。〕

## 2026-09-01 六项目标动态证据补充

- [x] S9+ 动态会话/通知/旧身份日志证据：`artifacts/s9-lock-key-dynamic.txt`。
- [x] 锁屏/熄屏媒体键状态路由证据：`artifacts/s9-lock-key-dynamic.txt`、`artifacts/s9-fnaudio-0.2.34-lock-notification.txt`。
- [x] 错误响应的 command ticket 端到端拒绝日志：`artifacts/s9-command-ticket-dynamic.txt`。
- [x] command ticket 错误响应的真机动态拒绝日志：`artifacts/s9-command-ticket-dynamic.txt`。

## 2026-09-01 六项目标剩余验收

- [x] 服务层 `ACTION_REMOTE_UPDATE` 二次身份校验及 S9+ instrumentation 覆盖。
- [x] 锁屏界面/媒体键路由已由 S9+ 系统日志验证。
- [x] command ticket 错误响应已由 MockWebServer + S9+ instrumentation 验证。

## 宿主 MediaSession（私有 participant 协议逆向与动态验收）

- [ ] 三星 S9+ 已完成 `0.2.34` 最新源码 APK 登录、远程通知、媒体键和进程重启恢复基线验收；
  仍需补充锁屏界面实际按键交互，以及制造延迟旧响应验证 generation/engine epoch/command ticket
  在真机日志中的拒绝原因。
- [x] S9+ Android instrumentation 回归（2026-09-01）：13 项中 2 项因 fnOS 私有服务未导出或
  缺少真实 NAS 队列而跳过，0 项失败；不把环境跳过项计作宿主私有能力已实现。

- [ ] 构建环境仍阻断 ARM64 APK：Gradle 9.6.1 在 Windows 无法建立 loopback/Unix-domain pipe；需切换
  可用构建主机或修复 Java/Gradle 通信后，才能把新增诊断安装到小米 15 Pro。

- [ ] 解决 Windows Gradle loopback 通信失败，生成包含 bridge 诊断的 ARM64 APK 后再做小米 15 Pro 运行态验证；旧 `0.2.33` 不作为新代码证据。

- [x] 按当前产品要求恢复 fnOS `iframe + micro_app` 启动容器；保留 fnAudio CGI 认证代理。
  该入口调整不宣称可接管飞牛 APP 的私有 MediaSession。
- [ ] 在飞牛 APP WebView 中执行 `fnAudioMediaSessionDiagnostics()`，记录不同版本 WebView 的支持结果。
- [ ] 在小米 15 Pro 的官方 `trim.music` 实播流程中，捕获 `registerParticipant`、`synchronize` 和
  `requestActivation` 的真实 StandardMessageCodec 载荷、调用方向与 participant 身份字段；当前已确认
  channel 名和官方 `audio_service` 运行态，但未获得 payload。
- [ ] 私有通道接入边界：已确认普通 FPK WebView 无法取得 Flutter `BinaryMessenger`，待继续审计
  是否存在 WebView 注入的受控播放 handler 或 fnOS 原生 participant 扩展点；在此之前保持 fnAudio
  自有 Media3/标准 Web MediaSession，不把宿主私有能力标记为已复用。
- [ ] 在小米 15 Pro 的 fnAudio 页面运行时记录新增 `genericWebViewBridgeDetected` 诊断，确认
  飞牛不同入口是否注入通用 bridge；仅观察，不调用未知 `callHandler`。
- [ ] 已解出 1.35.2 participant 模型字段，继续审计 `Lz72/Ljc` 对 participant ID、包签名、内置模块或
  其他身份的门禁；在证明可被第三方安全接入前，不向 fnAudio 发送或伪造私有 Pigeon 消息。
- [ ] 验证飞牛 APP 对非官方 appId/URL/participant 的身份门禁：仅做无破坏、可回滚的观察，不向
  fnAudio 发送猜测的私有 Pigeon 消息。
- [x] 增加公开宿主会话适配器与能力诊断：宿主显式暴露标准桥接对象时可接入握手、同步和激活；
  当前飞牛 APP 未发现该对象，因此不会改变现有播放行为。
- [x] 公开桥接激活生命周期：按曲目上下文幂等调用 `requestActivation`，切歌重建上下文，
  无当前曲目时调用 `release`；已通过 Node 适配器回归，未替代飞牛 APP 动态接管验收。
- [x] 公开桥接异常隔离：宿主对象 getter、缺失方法和异步拒绝均不会阻断页面启动；失败原因纳入
  有界诊断结果。
- [ ] 在获得真实协议和身份边界后，评估能否为 fnAudio 建立宿主 participant；若无法建立，保留现有
  等价 MediaSession 架构，不能伪称已经复用飞牛私有通道。
- [x] 小米 15 Pro 外部入口对照：确认直接 `ACTION_VIEW` 打开 `/music/` 只进入系统浏览器；
  `trim://app.com/openShareUrl` 仅能唤起飞牛 APP 主 Activity，尚未获得播放 participant 能力。
  该结果作为入口边界证据，不替代私有通道 payload 动态抓取；路由静态链路见
  `artifacts/trim-music-scheme-routing-20260831.md`。

- [x] Android 远程响应体资源上限：命令与状态接口采用 512 KiB 有界读取并拒绝超限响应，
  已通过完整离线门禁；仍不替代真实设备网络验收。
- [x] Android 命令票据空值隔离：响应一旦包含 `command_id`，必须提供非空且完全相等的
  `core.command_ticket`；已通过 Android bridge 静态契约与完整离线门禁。

- [x] KeepAlive lease 恢复输入边界：异常时长和时钟值安全归一化，避免恢复路径因损坏输入
  抛出异常；已通过专项回归，仍不替代真实 Android 进程回收验收。
- [x] 恢复时推进 Android engine epoch：服务重建后使用新的引擎世代接管持久会话，隔离旧进程
  迟到事件；已通过静态契约回归，仍不替代真实进程回收验收。
- [x] Android 身份字段严格解析：generation/engine_epoch/state_version 存在但格式非法时拒绝
  事件，缺失字段仍兼容旧后端；已通过静态契约和完整离线回归，仍不替代动态验收。
- [x] Android 主线程状态更新二次身份校验：网络回调排队后再次确认 generation/engine epoch，
  避免切换目标期间的旧 runnable 覆盖新会话；已通过静态契约回归，仍不替代真机验收。
- [x] 非零世代事件必须携带会话身份：避免旧协议缺失字段绕过 generation/engine epoch 隔离；
  初始零世代仍兼容，已通过静态契约回归，仍不替代动态验收。
- [x] Android state_version 提交竞态：版本水位仅在主线程完成身份二次校验后更新，避免旧
  回调污染新会话；已通过静态契约回归，仍不替代动态验收。
- [x] Android 身份数值整数性：generation/engine_epoch/state_version 拒绝小数型输入，避免
  截断伪装；已通过静态契约回归，仍不替代动态验收。
- [x] 远程请求取消日志分类：主动关闭/切换会话不再误报网络故障，真实网络异常仍保留失败
  原因；已通过静态契约回归，仍不替代动态验收。
- [x] 恢复激活结果可观测：远程会话激活失败时不再记录 ready，会清理无效快照并记录明确
  的 activation_rejected 原因；已通过静态契约回归，仍不替代动态验收。
- [x] 远程 stop 命令去重：MediaSession 重复停止回调在权威确认前只发送一次，失败后允许重试；
  已通过静态契约回归，仍不替代动态验收。
- [x] stop 确认状态同步：命令响应 core 的 playing/position/duration 现在立即应用，避免停止
  pending 延迟到轮询才释放；已通过静态契约回归，仍不替代动态验收。

- [x] 持续目标：Android 等价 MediaSession 未在部分设备上生效。已完成会话建立时序、远程
  输出通知、生命周期恢复、命令票据和诊断日志；不得把 fnOS 官方私有 MediaSession 当作
  可直接调用的公共 API。真实小米 15 Pro 验收需在当前真实设备限制解除后执行。

## Android 等价 MediaSession 持续目标

- [x] 会话建立时序：远程模式先建立 MediaSession，再绑定播放状态；S9+ 日志含
  `session_create begin` → `session_ready media_session` → `remote_enable ready`。
- [x] 远程播放通知：无本机解码器时创建 `fnaudio_remote_playback` 前台 MediaStyle 通知，
  并同步曲目信息与封面；证据见 `artifacts/s9-fnaudio-0.2.34-notification-playing.txt`。
- [x] 锁屏与媒体键回传：由 MediaSession 接收并回传后端；S9+ 系统媒体键与锁屏通知证据已保存，
  直接 instrumentation 回归通过。
- [x] 进程被回收后的恢复：`START_STICKY`、持久快照和 engine epoch 恢复目标/队列；S9+ 强停后
  重启恢复曲目与位置已验证。
- [x] generation/engine epoch/command ticket：旧身份和不匹配票据均拒绝；S9+ 动态日志及
  `PlaybackServiceCommandTicketInstrumentedTest`（1/1）通过。
- [x] 可观测日志和失败原因：生命周期、通知、恢复、命令拒绝均输出有界脱敏原因；动态证据已保存。
- [x] 真机验收：三星 S9+ 0.2.34 已完成会话、通知、媒体键、恢复和身份隔离验收；fnOS 私有
  MediaBrowser 仍明确不纳入可复用能力。

- [x] 跨平台播放会话统一协议：已建立有界、可测试的 `PlaybackParticipant`、
  `PlaybackSessionSnapshot`、`KeepAliveLease`、`CommandTicket` 契约；真实 Android/iOS/鸿蒙
  动态验收仍另行进行。

- [x] 权威快照身份接线：播放核心状态与 SSE 事件现在统一携带有界
  `generation`、`engine_epoch` 和 `command_ticket`；控制请求绑定身份后会触发一次状态版本更新，
  避免事件流与轮询对同一会话产生歧义。已通过专项及完整离线回归，仍不替代真实设备验收。
- [x] Android 命令响应身份门禁：MediaSession 媒体键触发的异步控制响应复用 SSE/轮询的
  generation 与 engine epoch 校验，旧响应不会覆盖当前远程状态；已通过 UI 静态契约回归，
  仍不替代真实设备验收。
- [x] Android 命令票据门禁：确认响应的 `command_id` 必须与权威快照
  `command_ticket` 一致，错配响应安全丢弃并记录原因；已通过 UI 静态契约回归，仍不替代
  真实设备验收。
- [x] 会话与通知可观测阶段：记录 MediaSession 创建、远程通知发布及 SSE 连接失败原因，
  保持日志脱敏和有限文本；已通过 UI 静态契约回归，仍不替代真实设备验收。
- [x] 持久会话过期保护：恢复快照采用 schema=1 和 7 天有效期，过期/时钟异常数据自动清理；
  已通过 UI 静态契约回归，仍不替代真实设备验收。
- [x] 原生命令恢复竞态收敛：媒体键确认及任务移除前立即持久化最新远程状态，避免 WebView
  挂起时丢失下一曲/暂停位置；已通过 UI 静态契约回归，仍不替代真实设备验收。
- [x] 跨端会话身份初始化：Web UI 生成的 generation/engine epoch 显式传入 Android 远程
  Bridge，避免首次控制出现身份不匹配；已通过 Node/UI 回归，仍不替代真实设备验收。
- [x] 服务端旧会话主动拒绝：低于当前 generation/engine epoch 的控制命令返回 `stale_session`
  并保持播放状态不变；已通过策略回归，仍不替代真实设备验收。
- [x] 旧会话拒绝可观测：服务端记录脱敏 `playback_stale_session` 结构化事件，便于定位迟到
  命令；已通过完整离线回归，仍不替代真实设备验收。
- [x] 旧会话失败路径专项回归：验证 stale_session 返回 409、不修改当前核心状态，且日志
  写入异常不会改变拒绝结果；新增播放会话契约边界测试，仍不替代真实设备验收。
- [x] Android 会话建立顺序静态契约：回归检查 player → MediaSession → ready 日志 → 恢复快照，
  以及远程模式 ready guard → activate → 前台通知的顺序，防止后续改动引入启动竞态。
- [x] 远程状态轮询失败可观测：补充 network、HTTP 状态码和 invalid payload 三类脱敏日志，
  与 SSE 失败诊断保持一致；仍需真实设备验证通知和状态流表现。
- [x] 媒体键失败响应隔离：Android 仅在 HTTP 成功且身份/ticket 校验通过后应用 `core`，
  409/5xx 只记录失败并触发权威刷新，避免错误响应污染原生状态。
- [x] 远程 MediaSession 去乐观更新：播放、暂停、停止、切歌、循环和随机操作均等待后端
  确认快照后再更新通知状态，避免控制栏抖动或旧事件覆盖。
- [x] 远程通知封面：自定义 MediaStyle 通知在有 artwork 时使用有界解码设置大图标，超大
  或损坏图片安全跳过并记录原因；仍需真实锁屏设备验收。
- [x] 权威状态通知刷新：SSE/轮询及命令确认更新曲目或位置后立即重发前台通知，避免
  通知栏停留在上一首；仍需真实锁屏设备验收。
- [x] 服务销毁恢复检查点：`onDestroy()` 在释放远程 metadata-only player 前持久化最后
  已确认状态，降低系统回收时丢失位置/曲目的概率；仍需真实进程回收验收。
- [x] 命令票据缺失隔离：带 `command_id` 的响应若缺少 `core.command_ticket` 也会被拒绝并
  记录 `stale_command_ticket`，避免不完整响应绕过旧事件门禁。
- [x] 销毁检查点同步落盘：服务销毁前的远程会话快照使用同步 `commit()`，日常状态更新
  仍使用异步写入，降低进程立即回收时丢失最后状态的风险。
- [x] Android SSE 帧资源边界：客户端事件缓冲限制为 512 KiB，超限或 JSON 无效时清空
  当前帧并记录脱敏原因，避免异常事件拖垮远程会话。
- [x] SSE 帧大小计算优化：改用增量 UTF-8 字节计数，避免每行重复复制整个累积帧，保持
  512 KiB 上限的同时降低大帧解析分配。
- [x] 空状态快照诊断：`applyRemoteStatus(null)` 现在记录 `remote_status failed: invalid_payload`，
  与轮询/SSE 解析失败原因保持一致。
- [x] 前台通知发布异常隔离：`startForeground()` 运行时异常被捕获并记录
  `remote_notification failed: publish`，避免厂商通知限制导致远程服务直接崩溃。
- [x] 播放/暂停命令去重：MediaSession 在后端确认前重复回调同一目标时只发送一次命令，
  收到权威状态后清除 pending 标记，降低重复控制和旧事件污染。
- [x] 循环/随机命令去重：后端确认前重复的模式变更只发送一次，权威模式快照到达后清除
  pending 标记，同时保留用户请求值用于命令载荷。
- [x] 循环/随机 pending 状态与展示状态分离：重复回调去重不再依赖乐观展示值，确认前仍
  保持后端权威状态，避免 Media3 反馈回路反复切换模式。
- [x] 失败命令 pending 释放：网络或 HTTP 失败时清除对应 pending 标记，允许用户重试，
  同时保持失败响应不更新本地展示状态。
- [x] prepare/stop pending 竞态：prepare 复用播放 pending 去重，stop 立即清除播放 pending，
  避免停止后再次播放被误判为重复请求。
- [x] 命令确认日志准确性：仅在响应快照实际通过身份/ticket 门禁并应用后记录 confirmed；
  HTTP 成功但快照被拒绝时记录 `stale_response`。
- [x] 服务入口未知 action 诊断：`onStartCommand()` 对未识别 action 记录
  `service_start ignored: unknown_action`，便于定位会话建立时序调用错误。
- [x] 六项播放会话验收矩阵：新增 `docs/PLAYBACK_SESSION_ACCEPTANCE_MATRIX.md`，固定实现、
  离线和动态证据边界，便于后续会话恢复。
- [x] 媒体键命令 HTTP 结果可观测：Android 区分 confirmed 与 HTTP failure 日志，避免诊断
  误导；已通过 UI 静态契约回归，仍不替代真实设备验收。
- [x] Web 控制身份继承与重置：远程命令回传当前 generation/engine epoch，退出远程模式
  清空身份；已通过 Node/UI 回归，仍不替代真实设备验收。

- [x] x86_64 Android 模拟器路线：按用户要求放弃，不作为验收目标；后续仅以 arm64 设备验收。
- [x] x86_64 AVD system image/APK ABI问题：已记录并关闭该路线，不再投入修复资源。
- [ ] 在 Gradle loopback 问题解除后生成并安装最新 arm64 APK，再在小米 15 Pro 验收六项会话
  行为；当前仅完成既有 0.2.33 安装的启动无崩溃检查。
- [ ] 小米设备播放态动态验收：登录并开始远程播放后检查 dumpsys MediaSession、通知栏、锁屏
  媒体键和进程回收；登录页空闲无活动会话属于预期状态。
- [ ] 解除 Gradle loopback 宿主限制：JDK 17 与 JDK 25 均复现，需更换构建宿主或修复本机
  Windows 本地进程通信后，才能生成最新 arm64 APK。
- [ ] Android 工程编译门禁：本机 Gradle 9.6.1 启动时无法建立 loopback connection，需在
  可用 Gradle/JDK 主机重跑 `:app:testDebugUnitTest`；当前仅有源码静态和 Node 契约证据。
- [ ] iOS/鸿蒙动态验收：迁移到 macOS/Xcode 或 HarmonyOS DevEco 主机后执行；Windows 本机
  不具备对应模拟器运行条件。

- [x] 飞牛 APP 宿主 MediaSession 静态对齐：对比 1.33.4/1.35.2 `audio_service`，为 fnAudio 补齐 session activity、远程 WakeLock、START_STICKY 与 task-removed 前台保活；待 Android 动态设备验收。

- [x] 公开曲目投影资源边界：限制单条目字段复制、隔离异常映射并避免空 ID 封面 URL；专项及完整离线门禁通过，未替代真实网络验收。

- [x] SSE 单帧资源预算：事件流帧编码限制 512 KiB，超限、不可序列化或递归时使用有界降级标记；专项及完整 949 项离线门禁通过，未替代真实网络/设备验收。

- [x] 曲库缓存失败策略边界拆分：独立模块负责有界递增/投影，运行时状态保留在 `library.py`；策略、健康/诊断接线及完整 945 项门禁通过，未替代真实扫描验收。

- [x] 曲库缓存失败可观测性：区分 legacy/SQLite 缓存加载与写入失败计数，状态接口提供有界 `cache_failures` 摘要；专项及健康/诊断接线回归通过，完整门禁 939 项通过，未替代真实扫描环境验收。

- [x] SSE 播放事件策略专项验证：20 项播放状态/恢复回归、936 项完整离线门禁及全部 Node/UI 回归通过；未替代真实设备验收。
- [x] 本轮恢复证据刷新：更新 `SOURCE_MANIFEST.sha256` 与 155 版本恢复索引，记录当前清单指纹；未替代正式发布验收。

- [x] API token 提取边界拆分：独立封装 header 优先级、Bearer 归一化和长度限制，新增回归并通过离线门禁。未替代真实协议验收。
- [x] 恢复索引持久化契约：增加显式 `-OutputPath` 和临时文件替换，避免会话恢复时误读旧索引；新增文档/脚本回归。未替代正式发布验收。
- [x] 恢复索引哈希宿主兼容：缺少 `Get-FileHash` 时使用流式 .NET SHA-256 回退，新增脚本回归。未替代正式发布验收。
- [x] 发布构建哈希宿主兼容：构建脚本所有哈希路径统一使用流式 .NET SHA-256 回退，新增脚本回归。未替代正式发布验收。
- [x] DLNA 请求上下文边界拆分：诊断 header 提取与长度限制独立为纯模块，新增回归。未替代真实 Renderer 验收。
- [x] DLNA 请求地址异常隔离：异常 `client_address` 安全回退为空地址，新增回归。未替代真实 Renderer 验收。
- [x] DLNA 诊断值安全投影：拒绝任意对象字符串化并保持字段有界，新增回归。未替代真实 Renderer 验收。
- [x] DLNA 诊断容量上限：条目 deque 限制为 1–1000 并隔离异常配置，新增回归。未替代真实 Renderer 验收。
- [x] 播放目标参数边界：目标 ID 限制 128 字符、拒绝任意对象字符串化并隔离损坏查询，新增回归。未替代真实设备验收。
- [x] 播放目标非有限数值隔离：拒绝 NaN/Infinity 目标值并安全回退本机，新增回归。未替代真实设备验收。
- [x] 播放目标超大整数隔离：有限性检查捕获溢出并回退本机，新增回归。未替代真实设备验收。
- [x] SSE 播放目标策略统一接线：事件流复用 `target_id_from_query()`，避免原始参数绕过限制；新增回归。未替代真实设备验收。

- [x] 磁盘余量检查异常隔离：`disk_has_reserve()` 对非法路径解析/父目录回溯安全返回不足，避免异常输入打断资源准入；新增回归并通过离线门禁。未替代真实设备验收。

- [x] 恢复索引记录源码清单指纹：发布证据索引输出 `source_manifest_present/source_manifest_sha256`，便于会话恢复后识别源码漂移；脚本回归及完整离线门禁通过。

- [x] 播放目标判断边界拆分：`ui/playback_target_policy.js` 统一目标识别与安全归一化，Node 及完整离线回归通过。

- [x] 循环模式边界拆分：`ui/repeat_mode_policy.js` 统一循环状态归一化、轮换和中文文案，`app.js` 保留 UI 接线；Node 及完整离线回归通过。

- [x] 曲目排序边界拆分：`ui/track_sort_policy.js` 独立处理标题/序号/加入时间及中文数值排序，`app.js` 保留状态接线；Node 及完整离线回归通过。

- [x] 发布恢复索引语义版本排序：`index_release_evidence.ps1` 按三段版本值而非字符串排序，避免 `0.2.9` 排在 `0.2.33` 之后；脚本回归及完整离线门禁通过。
- [x] 发布索引脚本宿主兼容回退：`$PSScriptRoot` 为空时使用当前目录构造 verifier/artifacts 路径，避免嵌套 PowerShell 恢复调用因空路径失败；脚本回归及完整离线门禁通过。
- [x] 发布索引版本键异常回退：超长数字目录名的 `[version]` 转换失败时安全降级为 `0.0.0`，避免恢复索引整体中断；脚本回归及完整离线门禁通过。
- [x] 发布索引工具目录探测：`$PSScriptRoot` 缺失时同时探测项目根目录和 `tools/` verifier，兼容不同 PowerShell 恢复启动目录；脚本回归及完整离线门禁通过。
- [x] 发布索引行为级回归：读取生成的恢复索引，验证条目不超过上限且按三段语义版本降序排列；专项及完整离线门禁通过。
- [x] 发布索引源码指纹格式回归：验证恢复索引包含 64 位十六进制 `source_manifest_sha256`；生成流程在门禁前后显式重建并核对与当前根清单一致，避免测试顺序耦合。
- [x] 发布索引 schema 标识：恢复 JSON 增加固定 `schema=1`，为未来字段演进保留可判别契约；脚本回归及完整离线门禁通过。
- [x] 视图排序选项边界拆分：`ui/library_sort_options_policy.js` 独立处理分组/专辑/歌手/歌单排序选项与默认序号排序；Android bundled UI 同步内嵌，Node 及完整离线回归通过。
- [x] 文件夹标签边界拆分：`ui/folder_label_policy.js` 独立处理跨平台路径末级名称与当前目录标签，隔离任意对象字符串化；Android bundled UI 同步内嵌，Node 及完整离线回归通过。
- [x] 主机隐私策略边界拆分：`ui/host_privacy_policy.js` 独立处理 LAN/公网主机判定，覆盖 IPv4 保留网段、本地域名和异常输入；Android bundled UI 同步内嵌，Node 及完整离线回归通过。
- [x] IPv6 内网主机判定补全：主机隐私策略增加 ULA `fc00::/7` 与链路本地 `fe80::/10` 识别，避免 IPv6 内网被误判为公网；Node 及完整离线回归通过。
- [x] 慢请求阈值异常回退：可观测性对非正 `slow_seconds` 使用默认阈值，避免所有请求被错误计为慢请求；专项及完整离线门禁通过。

- [x] 歌词解析边界拆分：`ui/lyrics_parse_policy.js` 独立处理 LRC 文本解析与时间排序，`app.js` 保留接线；专项及完整离线回归通过。

- [x] 封面提取缓存压力可观测性：health/diagnostics 暴露有界 entries/limit/inflight/inflight_limit 摘要，不泄露路径或封面内容；专项及完整离线回归通过。

- [x] 封面缓存参数安全边界：容量、路径长度和 in-flight 限制拒绝异常对象并限制上界，避免配置输入放大资源；专项及完整离线回归通过。

- [x] 封面缓存模块边界拆分：`cover_item_cache.py` 独立承载 LRU/单飞编排，`server.py` 保留依赖接线；专项及完整离线回归通过。

- [x] 封面提取并发去重：本地封面 LRU 对同键未命中使用最多 64 项的 in-flight 协调，避免页面并发重复解析同一封面；专项及完整离线回归通过。

- [x] 用户媒体状态边界拆分：收藏/歌单归一化、增量计算和合并应用已移至 `ui/user_media_state_policy.js`，Node 及完整离线回归通过。

- [x] 创作者/专辑视图边界拆分：`ui/creator_view_policy.js` 提供歌手/作曲者状态和视图判定纯策略，`app.js` 保留兼容接线；Node 及完整离线回归通过，未替代真实设备验收。

- [x] 大曲库基准运行时信息：benchmark 输出 Python/SQLite 版本，支持恢复时识别环境差异；专项及完整离线回归已通过。

- [x] 大曲库搜索基准结构化证据：离线 benchmark 输出 FTS 相对 LIKE 的 `speedup_vs_like`（无 FTS 时为 `null`），仅作趋势观测，不设置机器相关硬阈值；专项及完整离线回归已通过。

- [x] 全量播放分页边界策略：`library_full_list_policy.js` 已统一总数和提前终止规则，避免 `app.js` 分散维护大曲库上限；完整离线门禁 908 项通过。

- [x] 全量播放分页策略拆分：`library_full_list_policy.js` 统一总数边界和合并提前终止条件，`app.js` 保留请求调度与状态接线；专项及完整离线回归 908 项通过。

- [x] 前端访问模式请求去重：`access_profile_loader.js` 提供 10 秒 TTL 与 in-flight 复用，避免分页重绘重复请求 `api/access`；专项及完整离线回归 908 项通过。

- [x] 播放命令缓存压力可观测性：健康与诊断接口只公开幂等缓存 entries/limit/saturated 三项，锁与实际命令内容不外泄；专项 34 项及完整离线回归 908 项通过。

- [x] 播放命令幂等缓存边界拆分：`playback_command_cache.py` 统一过期回收、损坏项隔离、响应副本与容量淘汰；保留 `server.py` 的锁、TTL 与命令编排，专项及完整离线回归 907 项通过。

- [x] 曲库刷新队列边界拆分：`library_refresh_policy.py` 负责排队/强制刷新升级/取出/取消的纯状态转移，线程与扫描锁仍由 `library.py` 管理；专项及完整离线回归 902 项通过，未替代真实扫描环境验收。

- [x] 恢复手册证据索引说明：`RECOVERY.md` 已记录 `tools/index_release_evidence.ps1` 的只读盘点命令、输出语义和历史证据缺失边界；不替代正式发布或设备验收。

- [x] 播放状态响应组合边界拆分：浏览器/ALSA/MPD/UPnP 的响应形状抽至 `playback_status_response.py`，后端探测与自动推进逻辑保持在 `server.py`；专项及完整离线回归通过，未替代真实播放设备验收。

- [x] 查询缓存展示边界拆分：命中率、诊断计数器和嵌套快照投影已移至 `library_query_cache_presentation.py`，缓存容器仅保留 TTL/LRU/失效逻辑；专项及完整离线回归通过。

- [x] 发布证据批量索引：新增 `tools/index_release_evidence.ps1`，以最多 256 个语义版本目录生成 JSON 恢复索引并隔离单目录失败；已通过 PowerShell 静态/完整离线回归，未替代正式发布验收。

- [x] 收藏/歌单引用曲目请求去重：`library_item_request_loader.js` 统一后台补水与播放前补水的批请求，限制 32 个 in-flight 键并通过 Node/完整离线回归；未替代真实设备验收。

- [x] API 路由权限策略边界拆分：路径规范化、资源认证与 scope 映射已移至 `server/api_route_policy.py`，保留 `api_auth.py` 兼容入口并通过专项/完整离线回归；未替代真实网络协议验收。

- [x] UI 模块加载顺序契约：静态回归已锁定共享曲库模块先于 `app.js` 加载，避免运行时未定义；已通过完整离线门禁。

- [x] 前端分页请求键拆分：高频请求去重键已独立为纯模块并完成运行时接线，已通过 Node 及完整离线回归。

- [x] 前端分页加载器运行时接线：`index.html` 已在 `app.js` 前加载共享加载器，避免模块未定义导致运行时失败；已通过离线门禁。

- [x] UPnP 选择器迭代兼容：支持生成器等普通可迭代输入并限制 500 项，已通过专项及完整离线回归。

- [x] UPnP 设备选择边界拆分：设备发现结果按 ID 的纯选择逻辑已独立并通过专项及完整离线回归；未替代真实 Renderer 验收。

- [x] HTTP worker 忙碌退避提示：503 响应增加 `Retry-After: 1`，并通过服务端专项回归；未替代真实设备验收。

- [x] 曲目过滤策略异常隔离：查询属性访问失败时安全回退，避免大曲库分页请求被损坏输入阻断；已通过专项及完整离线回归。

- [x] 前端分页响应加载器拆分：缓存/inflight/epoch 逻辑已独立并通过 Node 及完整离线回归；未替代真实设备验收。

- [x] 曲目分页过滤策略拆分：分组/专辑/目录/搜索条件组合已独立为纯模块并通过专项及完整离线回归；未替代真实设备验收。

- [x] 播放目标响应组合边界：设备目标 payload 的纯组合逻辑已从 `server.py` 拆出并覆盖异常输入回退；已通过专项及完整离线回归。未替代真实 Renderer/DAC 验收。

- [x] HTTP worker 诊断投影边界：健康/诊断接口复用 `http_worker_presentation.py` 的统一 5 字段有界投影，已通过专项及完整离线回归。未替代真实设备验收。

- [x] 发布证据机器可读恢复输出：`verify_release_evidence.ps1 -Json` 已提供稳定 JSON 结果，便于会话删除后的自动恢复校验；已通过脚本回归。未替代真实 fnOS/App Center 验收。

- [x] 分页响应顶层字段边界：公开投影最多读取 32 个顶层字段，避免大型映射复制；专项及 868 项完整离线门禁均已通过。

- [x] 播放命令幂等缓存边界：command_id 结果缓存限制 1,024 项并淘汰最旧项，保持重试语义；专项及 867 项完整离线门禁均已通过。

- [x] 曲目分页公开投影拆分：`/api/library` 复用最多 500 项的安全投影，隔离异常条目并减少 `server.py` 列表拼装；专项及 865 项完整离线门禁均已通过。

- [x] 分组分页投影统一接线：专辑归属筛选分支复用公共安全投影，避免手写字段访问在异常 Row 上中断；专项及 863 项完整离线门禁均已通过。

- [x] 分页游标资源边界：窗口分页与旧 SQLite 回退最多物化 500 行，游标异常保留精确回退语义；专项及 862 项完整离线门禁均已通过。

- [x] 播放状态响应投影拆分：MPD/UPnP transport 与 position 复用有界纯投影，隔离损坏后端字段并保持协议兼容；专项回归及 861 项完整离线门禁均已通过。

- [x] 前端曲目定位有界索引：对当前页/全量页建立 5,000 项 WeakMap 索引，超界安全回退；已通过 Node 及完整离线回归。

- [x] 前端曲目定位策略拆分：缓存/当前页/全量页查找抽为纯模块，保持顺序和 LRU 触达；已通过 Node 及完整离线回归。

- [x] 内存单曲查找异常隔离：损坏映射不会阻断后续有效曲目回退定位；已通过专项及完整离线回归。

- [x] 播放事件投影边界拆分：SSE payload 字段规范化抽为纯模块，保留权威快照身份与协议兼容；已通过专项及完整离线回归。

- [x] 单曲文件位置解析拆分：独立封装根目录约束、真实路径校验和安全投影；已通过专项及完整离线回归。

- [x] 单曲查询边界拆分：SQLite 查询与内存回退抽为可测试模块，隔离解码/迭代异常并保持查询优先级；已通过专项及完整离线回归。

- [x] 分组/文件夹投影公共边界：统一有界迭代与异常隔离实现，保持公开字段契约；已通过专项及完整离线回归。

- [x] 分页文件夹响应投影：剔除内部窗口统计字段、限制输出行数并兼容 SQLite Row；已通过专项及完整离线回归。

- [x] 分页分组响应投影拆分：剔除内部窗口统计字段并限制输出行数，兼容 SQLite Row；已通过专项及完整离线回归。

- [x] 播放队列 hydration 查询去重：重复队列 ID 仅查询一次，恢复时保留原始顺序和重复项；已通过专项及完整离线回归。

- [x] 前端渲染行数边界：分页/分组/文件夹响应进入状态前最多保留 500 行，策略抽为纯模块并通过 Node 回归。

- [x] 根目录结果投影拆分：将根目录响应字段规范化抽为纯模块，限制 64 项并隔离损坏摘要/行值；已通过专项回归。

- [x] 根查询策略模块化：将配置根过滤抽为可测试纯模块，限制 64 项并复用到聚合/搜索 SQL；已通过专项回归。

- [x] 根目录查询范围收敛：摘要失效或搜索时仅扫描当前配置根，避免历史残留根放大大曲库查询；已通过 SQLite 专项及完整离线回归。

- [x] 进程监督状态可观测性：状态接口安全暴露最近 32 次重启时间及窗口/待重启信息，隔离损坏内部值；已通过专项及完整离线回归。

- [x] DAC 配置读取边界：启动加载与保存/匹配共用 64 项映射投影，避免旧配置在恢复阶段放大内存；已通过专项及完整离线回归。

- [x] DAC 配置持久化边界：保存配置前限制 `dac_profiles` 为 64 个映射对象并复制隔离，避免异常状态放大；已通过专项及完整离线回归。

- [x] DAC 配置候选边界：自定义配置最多读取 64 项并隔离异常对象/迭代器，避免能力探测资源放大；已通过专项及完整离线回归。

- [x] Migu 封面候选边界：图片候选不再无界拼接列表，统一限制 64 项并隔离异常迭代器；已通过专项及完整离线回归。

- [x] 发布校验输入边界：验证 `SHA256SUMS` 前限制单记录文件大小，避免证据读取资源放大；已通过脚本专项及完整离线回归。

- [x] 元数据候选边界统一：匹配保存/确认流程限制为 64 个有效映射候选，避免异常供应商结果无界物化；已通过专项及完整离线回归。

- [x] 播放会话快照边界拆分：会话队列/目标/状态字段投影抽至 `playback_session_projection.py` 并保留独立回归；已通过完整离线回归。

- [x] 根摘要迭代边界统一：`root_index_summary()` 与扫描路径共用 64 项根候选上限，避免摘要阶段无界物化；已通过专项及完整离线回归。

- [x] 播放会话队列恢复有界化：队列 ID 通过独立投影限制 50,000 项、去重并拒绝任意对象字符串化；已通过专项及完整离线回归。

- [x] 扫描根候选有界化：`normalize_scan_items()` 最多读取 64 个库根，隔离异常迭代器并避免无界 `list()` 物化；已通过专项及完整离线回归。

- [x] DLNA Browse 物化上限：分组/根目录/文件夹子目录复用 5,000 行有界物化策略，避免大库一次性 list()；已通过专项及完整离线回归。

- [x] MPD PID 文件读取边界：启动清理对 `mpd.pid` 使用 256 字节上限并安全解析；已通过专项及完整离线回归。

- [x] MPD 日志尾读竞态边界：seek 后读取改为有界读取并截断，避免日志增长竞态造成无界内存；已通过专项及完整离线回归。

- [x] MPD PID 扫描读取边界：残留进程清理读取 `/proc/<pid>/cmdline` 有界化并保持匹配语义；已通过专项及完整离线回归。

- [x] MPD/AirPlay 进程探测读取边界：`/proc/*/cmdline` 统一采用 4 KiB 有界读取并保留原匹配语义；已通过专项及完整离线回归。

- [x] 本地进程/配置读取边界：AirPlay proc 探测与 MPD 配置读取均有明确字节上限，避免异常输入放大内存；已通过专项及完整离线回归。

- [ ] 0.2.33 历史产物完整 provenance：复核脚本确认缺少 staged `SOURCE_PROVENANCE.json`，需保留为不可恢复历史证据，不得伪造补齐。

- [x] 元数据长期计数边界：dropped/tag/status-cache 计数统一饱和并隔离异常旧值，避免可观测性数据无界增长；已通过专项及完整离线回归。

- [x] 元数据计数器饱和：队列丢弃、Tag 写入及状态缓存计数统一封顶并隔离损坏值；已通过专项及完整离线回归。

- [x] DLNA 事件计数饱和：accepted/dropped/peak_pending 长期计数统一封顶并安全恢复，避免可观测性数据无界增长；已通过专项及完整离线回归。

- [x] 元数据队列预算边界拆分：将 pending/limit 投影抽至 `metadata_queue_policy.py`，隔离损坏状态并保持 SQLite 精确计数回退；已通过专项及完整离线回归。

- [x] DLNA 事件资源配置容错：worker/pending 上限对异常配置安全回退并保持边界，避免服务初始化因配置类型错误中断；已通过专项及完整离线回归。

- [x] 缩略图预热缓存指标：健康/诊断复用的 thumbnail_prewarm_status 暴露内存缓存与 alias 缓存的有界占用指标；已通过专项及完整离线回归。

- [x] 核心边界拆分：随机队列 Fisher–Yates 策略抽至 `ui/shuffle_policy.js`，限制 50,000 项并隔离异常随机源；已通过 Node 及完整离线回归。

- [x] 播放会话对象形状恢复：load_user_state 对 JSON 解码结果统一投影为 mapping，非对象状态安全回退为空对象；已通过专项及完整离线回归。

- [x] 状态文本子类异常隔离：状态字段规范化遇到异常 str 子类时安全跳过，避免保存/恢复流程中断；已通过专项及完整离线回归。

- [x] 响应预算不可放宽：JSON/XML 序列化自定义上限只能收紧，始终服从全局响应资源预算；已通过专项及完整离线回归。

- [x] 状态投影递归异常隔离：深层 JSON 序列化/反序列化触发递归异常时安全回退，避免状态恢复阻断；已通过专项及完整离线回归。

- [x] 磁盘保留路径边界：disk_has_reserve 在文件系统访问前拒绝超长路径，保持资源检查成本有界；已通过专项及完整离线回归。

- [x] 并发门控等待时长恢复：累计等待时长先做有限投影再累加，隔离损坏内部状态；已通过专项及完整离线回归。

- [x] 内存曲库排序策略容错：数字排序键隔离异常数值策略并安全回退，保持大库降级列表可渲染；已通过专项及完整离线回归。

- [x] 分组查询值边界：分组条件参数统一限制 4096 字符，避免超长文本放大 SQL 查询与日志资源；已通过专项及完整离线回归。

- [x] 扫描数值转换异常隔离：极端整数标签安全回退默认值，避免扫描策略因 float 转换溢出失败；已通过专项及完整离线回归。

- [x] 恢复手册版本一致性：移除过期 0.2.5 基线，明确 0.2.33 与 VERSION/src/manifest 的恢复核对规则；已通过专项及完整离线回归。

- [x] 查询缓存失效键隔离：数据库刷新时安全跳过损坏缓存键并继续清理正常条目，避免失效流程阻断大曲库更新；已通过专项及完整离线回归。

- [x] 核心边界拆分：曲库摘要计数投影抽至 library_count_policy，查询层保持数据库接线与精确 SQL 回退；已通过专项及完整离线回归。

- [x] 查询缓存损坏条目清理：过期扫描和淘汰隔离异常 entry 与权重，避免大曲库缓存状态污染查询/诊断；已通过专项及完整离线回归。

- [x] 前端批请求统一并发策略：分页/分组/补水/定位复用调度器默认并发常量，避免大曲库调用点策略漂移；已通过专项及完整离线回归。

- [x] 曲库摘要计数安全读取：保存的 track_count/dsd_count 仅接受有界整数，损坏值自动回退精确 SQL 统计；已通过专项及完整离线回归。

- [x] 资源配置映射容错：bounded_int 隔离损坏配置 getter，保持资源上限默认值和诊断路径稳定；已通过专项及完整离线回归。

- [x] 前端批请求池入池快照：补水批次创建时复制并限制单批 256 项，隔离可变输入造成的请求漂移；已通过专项及完整离线回归。

- [x] 状态保存 payload 安全读取：save_user_state 隔离非字典和损坏映射，保持空状态保存契约稳定；已通过专项及完整离线回归。

- [x] 并发门控快照安全投影：资源门控状态输出统一限制数值范围并隔离 NaN/异常对象，保持可观测性稳定；已通过专项及完整离线回归。

- [x] 状态 revision 递增饱和：版本写入与读取共用 10^12 上限，长期运行不会产生越界 revision；已通过专项及完整离线回归。

- [x] 持久化严格 JSON：状态序列化拒绝 NaN/Infinity，避免跨语言恢复解析不兼容；已通过专项及完整离线回归。

- [x] 状态 revision 有界投影：持久化版本读取隔离损坏行和超大值，确保并发状态恢复保持稳定；已通过专项及完整离线回归。

- [x] 状态数据库路径安全回退：state_store 隔离损坏 cache_dir，确保用户状态和播放会话恢复路径有界可用；已通过专项及完整离线回归。

- [x] 发布 provenance 结构校验：恢复 verifier 拒绝 null/数组/标量 provenance 并稳定处理 schema 类型异常；已通过脚本专项及完整离线回归。

- [x] 查询缓存过期计数统一：批量过期清理与单项读取共用有界计数器，避免统计状态绕过容错边界；已通过专项及完整离线回归。

- [x] 查询缓存命中率快照容错：命中率计算和快速快照路径统一隔离损坏内部计数，保持健康指标稳定；已通过专项及完整离线回归。

- [x] 播放状态兼容入口容错：sync_frontend 隔离损坏字段与异常时长，保持旧客户端状态同步可用；已通过专项及完整离线回归。

- [x] 全量播放分页响应投影：播放全部歌曲前安全校验分页 items/count，限制总量并隔离异常响应；已通过 Node/UI 及完整离线回归。

- [x] 查询缓存快照计数容错：缓存统计写入和快速快照读取均安全投影损坏计数，避免大库状态接口输出非法数值；已通过专项及完整离线回归。

- [x] 可观测性累计值容错：计数器与延迟聚合拒绝损坏内部累计值并安全恢复后继续记录；已通过专项及完整离线回归。

- [x] 扫描状态快照安全读取：library_status 对缺失、损坏和非有限 SCAN_STATE 字段安全回退，避免健康/设置接口被运行时状态污染；已通过专项及完整离线回归。

- [x] 发布证据文档索引：将 0.2.33 历史 FPK 审计文档纳入 docs 索引，提升会话丢失后的恢复可发现性；已通过文档与清单校验。

- [x] 曲库状态端口投影：server_port 统一限制在 1024–65535，异常配置回退 53199；已通过专项及完整离线回归。

- [x] 曲库缓存目录缺省回退：缺失或无效 cache_dir 时安全使用当前目录，避免状态接口和缓存路径辅助函数失败；已通过专项及完整离线回归。

- [x] 缺省曲库路径状态回退：状态接口面对缺失路径配置仍返回有界状态，不阻断设置/健康页面；已通过专项及完整离线回归。

- [x] 元数据 Tag 计数输出统一：tag_written 与平均耗时使用同一有界投影，避免异常内部值泄露或阻断状态接口；已通过专项及完整离线回归。

- [x] 0.2.33 历史发布证据审计：明确 FPK 校验和可用、源码清单/provenance 缺失及恢复规则；未伪造或覆盖历史证据。

- [x] 元数据状态计数投影：pending/retry 与 Tag 写入统计统一使用有界非负策略，避免异常状态阻断可观测性；已通过专项及完整离线回归。

- [x] 封面预热队列长度异常隔离：自定义容器长度读取失败时安全回退为 0；已通过专项及完整离线回归。

- [x] 发布 provenance 资源边界：恢复校验拒绝超过 1 MiB 的 SOURCE_PROVENANCE.json，避免证据读取放大；已通过脚本契约及完整离线回归。

- [x] 封面预热状态映射隔离：损坏 worker 状态或队列容器不会阻断健康/诊断快照；已通过专项及完整离线回归。

- [x] 健康摘要上限转换容错：异常超大或非有限上限安全回退默认值，避免可观测性接口被边界配置阻断；已通过专项及完整离线回归。

- [x] 封面预热压力计数隔离：健康快照拒绝异常对象、布尔和负数计数，保持有界观测；已通过专项及完整离线回归。

- [x] SQLite 摘要无效值正确回退：损坏计数不再被默认值裁成 0，继续走 SQL 精确统计；已通过完整离线回归。

- [x] 启动状态恢复边界统一：localStorage 收藏/歌单读取复用统一规范化和数量上限，避免大数据首次启动绕过治理；已通过 Node 及完整离线回归。

- [x] SQLite 摘要计数统一投影：元数据与 SQL 回退路径均使用 safe_counter，避免极端计数值阻断状态读取；已通过专项及完整离线回归。

- [x] 曲库摘要计数边界：count/dsd_count 拒绝异常、负数和超大值，避免状态接口被损坏摘要阻断；已通过专项及完整离线回归。

- [x] 资源计数器损坏状态隔离：并发门控计数递增遇到异常内部值时安全恢复并保持上限；已通过专项及完整离线回归。

- [x] 扫描数值文本异常隔离：极长 scanned/found 数字文本安全回退默认值，避免整数解析异常穿透状态接口；已通过专项及完整离线回归。

- [x] 扫描状态计数边界：`scanned/found` 统一做非负与 32 位上限投影，避免异常状态值放大响应；已通过专项及完整离线回归。

- [x] XML/DLNA 客户端提前断开时安全忽略 BrokenPipe/ConnectionReset，避免请求线程异常；已通过 HTTP 专项及完整离线回归。
- [x] HTTP 错误页 message/explain 增加 1024 字符文本边界并拒绝任意对象转换；已通过 HTTP 专项及完整离线回归。
- [x] 核心边界拆分：HTTP 错误页文本投影抽至 `http_error_policy.py`，保留 Handler 行为并新增独立回归。
- [x] 大音乐库分页总数容错：窗口分页遇到异常/布尔总数时回退精确 COUNT，避免损坏 SQLite 行阻断列表请求；已通过专项及完整离线回归。
- [x] 大音乐库分页兼容路径一致性：旧 SQLite 的 COUNT 回退与窗口路径共享安全总数投影；已通过专项及完整离线回归。
- [x] 大音乐库分页游标异常隔离：窗口/回退游标不可迭代或执行异常时安全降级，避免兼容驱动异常阻断请求；已通过专项及完整离线回归。
- [x] 大音乐库分页迭代异常隔离：窗口游标运行时迭代错误安全回退到计数与页面查询；已通过专项及完整离线回归。
- [x] 大音乐库分页 SQL 异常隔离：回退页面查询失败时返回空页和安全计数，避免异常穿透请求层；已通过专项及完整离线回归。
- [x] 大音乐库分页计数游标异常隔离：COUNT 游标读取异常安全降为 0；已通过专项及完整离线回归。
- [x] 大音乐库分页游标接口缺失隔离：兼容驱动缺少迭代/读取方法时安全降级；已通过专项及完整离线回归。
- [x] 大音乐库状态恢复边界：歌单和歌单曲目读取在 SQL 层限制数量，避免恢复阶段无界物化；已通过专项及完整离线回归。
- [x] 大音乐库收藏恢复边界：收藏读取在 SQL 层限制 50000 条，保持状态恢复集合的统一上限；已通过专项及完整离线回归。
- [x] 核心边界拆分：扫描错误列表快照抽至 `scan_error_policy.py`，限制 20 条并隔离异常迭代/字段；已通过专项及完整离线回归。
- [x] 播放队列资源边界：`PlaybackCore.set_queue()` 限制 50000 项并隔离异常迭代器，避免大队列状态机无界物化；已通过专项及完整离线回归。
- [x] 播放队列追加边界：`dispatch(load)` 缺失曲目追加时复用队列上限并保留新选曲；已通过专项及完整离线回归。
- [x] 播放队列迁移入口边界：`sync_frontend()` 复用 50000 项队列限制，避免旧状态同步无界物化；已通过专项及完整离线回归。

- [x] 群组/专辑封面加载节点去重，避免同一容器重复绑定监听；已通过 Node/UI 及完整离线回归。

- [x] 音乐库响应缓存权重增加 6000 上限，与 LRU 预算保持一致；已通过 Node/UI 及完整离线回归。

- [x] 修复前端刷新请求响应阶段的缓存竞态，避免清空并发请求产生的新缓存；已通过 Node/UI 及完整离线回归。

- [x] 多根扫描根目录收集增加类型、空值和长度过滤，避免无效根路径占用恢复内存；已通过专项及完整离线回归。

- [x] 发布源码清单 verifier 增加 64 MiB/200,000 条记录资源上限，避免异常证据读取放大；已通过脚本契约及完整离线回归。

- [x] 扫描签名聚合增加 8 MiB 总文本预算，避免大量合法路径造成签名临时数据放大；已通过专项及完整离线回归。

- [x] 查询缓存身份键对超长数据库路径/命名空间改为拒绝而非截断，避免错误缓存命中；已通过专项及完整离线回归。

- [x] 扫描复用路径键增加 4096 字符边界，超长路径不进入旧索引和根分区；已通过专项及完整离线回归。

- [x] 扫描复用多根分区增加 64 个根目录输入上限，避免异常根目录迭代器无界物化；已通过专项及完整离线回归。

- [x] 扫描复用索引构建与多根分区增加 200,000 条输入边界，避免恢复阶段无界累积；已通过专项及完整离线回归。

- [x] 扫描最终化去重阶段增加 200,000 条唯一记录上限，避免排序前无界积累；已通过专项及完整离线回归。

- [x] 扫描结果排序增加 200,000 条有界物化策略，避免异常迭代器造成无界内存；已通过专项及完整离线回归。

- [x] 内存回退入口移除普通/DSD 视图的整库预复制，仅随机视图保留采样副本；已通过查询及完整离线回归。

- [x] 内存回退搜索增加每条曲目组合文本总长度上限，降低长元数据字段造成的临时内存和 CPU 压力；已通过专项及完整离线回归。

- [x] 隔离元数据 probe 回调异常，失败时继续本地标签回退并保留扫描流程；已通过专项及完整离线回归。

- [x] DSD 内存回退视图复用安全字段读取，隔离损坏条目的 `is_dsd` 访问异常；已通过查询及完整离线回归。

- [x] 内存回退查询边遍历边过滤，移除候选列表与过滤列表的重复驻留；已通过专项及完整离线回归。

- [x] 隔离元数据本地标签回退读取器异常，避免损坏文件阻断扫描；已通过专项及完整离线回归。

- [x] 将探测标签完整性判断与本地容器回退编排拆至 `metadata_tag_resolution.py`，并补独立回归；已通过完整离线回归。

- [x] 内存曲库回退查询合并过滤遍历，减少大曲库无 SQLite 场景的临时列表和峰值内存；已通过专项及完整离线回归。

- [x] 修复发布证据 verifier 的清单路径变量遮蔽，保证 provenance 校验使用清单文件自身哈希；已通过脚本契约及完整离线回归。

- [x] 发布源码清单 verifier 拒绝空路径段和 `.` 路径段，保持恢复证据路径规范化；已通过脚本契约及完整离线回归。

- [x] 发布源码清单 verifier 增加记录路径空白/长度边界，避免恢复证据包含不可核对路径；已通过脚本契约及完整离线回归。

- [x] 查询缓存键边界常量统一由 `library_query_cache_key.py` 提供，消除缓存类重复定义；已通过专项及完整离线回归。

- [x] 群组/专辑封面加载将 DOM 查询范围限制为当前 `trackList`，减少大曲库渲染时的无关节点扫描；已通过 Node 及完整离线回归。

- [x] 资源门控名称增加 256 字符边界并对空值使用稳定默认名，避免异常名称污染可观测性；已通过专项及完整离线回归。

- [x] ALSA 设备能力文本读取增加 64 KiB 上限，避免异常 proc/sysfs 内容造成内存放大；已通过专项及完整离线回归。

- [x] 查询缓存键增加数值幅度上限，避免极大数字放大哈希/比较开销；已通过缓存键及完整离线回归。

- [x] 查询缓存键拒绝不可迭代标量输入，避免非法参数折叠为空查询；已通过缓存键及完整离线回归。

- [x] 查询缓存键区分 `None` 与合法空参数序列，避免缺省参数误命中无参数缓存；已通过缓存键及完整离线回归。

- [x] 发布证据校验拒绝源码清单绝对路径和路径遍历项，降低恢复来源歧义；已通过脚本契约及完整离线回归。

- [x] 前端曲目缓存拒绝异常/超长键，避免大曲库缓存被异常响应污染；已通过 Node/UI 及完整离线回归。

- [x] 将查询缓存键规范化拆至 `library_query_cache_key.py` 并补独立回归，保持 LRU/失效逻辑兼容；已通过完整离线回归。

- [x] 修复并发门控等待者在虚假唤醒时自拒绝的竞态，保持等待队列上限语义；已通过资源门控及完整离线回归。

- [x] 查询缓存拒绝不支持的键值，避免异常对象折叠为同一缓存键导致错误命中；已通过缓存专项及完整离线回归。

- [x] CI 工作流在离线回归前刷新并校验根源码清单，防止过期恢复证据进入远程构建；已通过工作流契约及完整离线回归。

- [x] 大曲库全量分页加载改为流式逐页合并，移除分页数组的重复内存占用并在达到总数后提前结束；已通过 Node/UI 及完整离线回归。

- [x] 将健康 metrics 递归有界投影拆至 `metrics_projection.py` 并补独立回归，保持健康响应兼容；已通过完整离线回归。

- [x] 健康响应 metrics 值增加递归资源边界并隔离异常对象，避免序列化阶段资源放大；已通过健康快照及完整离线回归。

- [x] 健康响应对 metrics 顶层映射增加数量/键长度边界并隔离内部引用；已通过健康快照及完整离线回归。

- [x] 前端搜索回退路径隔离代理/损坏条目字段访问，避免单条异常记录中断大曲库筛选；已通过 Node/UI 及完整离线回归。

- [x] 可观测性计数器名称增加有限文本边界，拒绝空键和超长键，避免诊断响应资源放大；已通过独立及完整离线回归。

- [x] 旧库缓存投影隔离异常 list 长度访问，损坏容器安全跳过；已通过独立及完整离线回归。

- [x] 旧版 `library.json` 缓存投影增加 200,000 条 items 上限，避免超大兼容列表恢复放大；已通过独立及完整离线回归。

- [x] 状态变更映射增加异常字段访问隔离，损坏同步请求不会阻断状态事务；已通过回归。

- [x] 将旧版 `library.json` 缓存校验拆至 `library_cache_payload.py`，保留扫描器兼容入口并通过独立/完整离线回归。

- [x] 前端搜索回退路径复用有限文本/数字投影，移除无界隐式字符串化；已通过 Node/UI 及完整离线回归。

- [x] 兼容 `library.json` 恢复增加 JSON 顶层和 `items` 类型校验，避免合法畸形缓存触发异常；已通过曲库缓存及完整离线回归。

- [x] 状态 JSON 写入前增加 2 MiB 有界编码策略，超大/不可序列化载荷安全回退；已通过独立及完整离线回归。

- [x] UI 列宽投影隔离内部迭代器异常，保留已处理列宽并安全结束；已通过独立及完整离线回归。

- [x] 清理状态投影拆分后的冗余 legacy 函数和常量自引用，保持兼容入口清晰；已通过状态回归。

- [x] 状态纯投影模块隔离歌单/UI 配置迭代器异常，保留已处理项并安全结束；已通过独立及完整离线回归。

- [x] 为 `state_projection.py` 增加独立纯模块回归，验证拆分边界不依赖 SQLite；已通过完整离线门禁。

- [x] 将状态持久化纯投影策略拆至 `state_projection.py`，保留 `state_store.py` 兼容入口并通过状态回归。

- [x] UI 偏好恢复隔离损坏顶层映射和条目容器，异常状态安全回退；已通过状态存储及完整离线回归。

- [x] UI 列配置键增加有限文本投影，隔离异常对象和超长值；已通过状态存储及完整离线回归。

- [x] 状态字符串列表隔离异常迭代器，保留已读取项并安全结束；已通过状态存储及完整离线回归。

- [x] 状态同步对损坏歌单映射逐条隔离，坏记录不会阻断后续有效歌单；已通过回归。

- [x] 状态收藏/歌单文本字段增加 4096 字节安全投影，拒绝异常对象和超长单项；已通过状态存储及完整离线回归。

- [x] 状态数据库 JSON 恢复增加 2 MiB 载荷边界，超大或损坏会话安全回退；已通过状态存储及完整离线回归。

- [x] APE 兼容读取入口复用有界尾部标签解析，移除整文件物化路径；已通过元数据回归和完整离线门禁。

- [x] HTTP POST `Content-Length` 统一经过有界策略解析，非法值返回 400，超过 2 MiB 返回 413；已通过 673 项 Python 及全部 Node/UI 离线回归。

- [x] 服务端 `fnos_api.py` Unix socket 响应累计读取增加 1 MiB 上限，解析器拒绝超限/非二进制输入；已通过独立与完整离线回归。

- [x] CGI 本地配置候选文件读取增加 2 MiB 上限和二次有界读取，超限候选安全跳过；端口探测与配置回显均已覆盖并通过离线回归。

- [x] 客户端分页视图复用单次 `{total, tracks}` 结果，避免收藏/歌单/队列同一轮渲染重复计算；已通过 Node/UI 与完整离线回归。

- [x] 配置恢复读取增加 2 MiB 文件级上限和二次有界读取，超限配置安全回退默认值；已通过完整离线门禁。

- [x] CGI Trim 网关响应累计读取增加 1 MiB 上限，ffprobe 嵌入歌词输出增加 2 MiB 上限；均已通过离线回归。

- [x] 嵌入歌词 ffprobe 输出改为临时文件承接并限制 2 MiB，超限安全跳过；新增回归并通过完整离线门禁。

- [x] APE payload item 解析统一复用 `ape_tag_parser.parse_ape_items()`，消除服务层重复实现并通过独立回归。

- [x] APE 标签 footer/item 字节解析抽至 `ape_tag_parser.py`，服务层保留兼容入口；新增纯模块回归并通过完整离线门禁。

- [x] CGI 配置保存响应增加 1 MiB JSON 读取上限，超限返回 413 并保留当前配置回显；已通过离线回归。

- [x] CGI 首页重写响应增加 16 MiB 读取上限，超限返回 413，避免首页异常响应整块占用内存；普通代理响应保持分块转发，已通过完整离线门禁。

- [x] 旧版 `library.json` 兼容缓存增加 32 MiB 文件级上限和二次有界读取，超限缓存不解码且不覆盖现有内存索引；专项库缓存回归通过。SQLite 仍为权威索引。

- [x] 本地 `.lrc` 歌词读取加入 2 MiB 文件级上限，超大内容安全跳过并通过离线回归。

- [x] 修复超大 artwork 被拒绝时 DSF/WAV 原封面可能被清空的问题，改为保留已有封面并通过离线回归。

- [x] 元数据写回的本地 artwork 输入统一限制为 8 MiB，避免超大封面文件造成内存放大；已通过 644 项 Python 及全部 Node/UI 离线回归。

- [x] APE Tag 写回改为尾部标签定点读取与音频主体分块复制，避免大文件整包驻留内存；新增回归并通过 643 项离线门禁。

- [x] DSF Tag 写回改为音频主体分块复制，避免整文件读入内存；新增大文件回归并通过离线门禁。

- [x] CUE 文件读取抽至 `server/cue_reader.py`，加入 8 MiB 文件级上限并隔离异常路径；已通过 641 项 Python 及全部 Node/UI 离线回归。

- [x] 封面路径分派策略抽至 `server/cover_dispatch.py`，统一 MP3/DSF/APE/WAV/FLAC/MP4 读取器选择并通过离线回归。

- [x] 发布脚本默认拒绝覆盖同版本 FPK，显式 `-AllowExistingArtifact` 才能重建，保护正式包和恢复证据；已通过离线回归。

- [x] 查询缓存健康摘要补充 `uncacheable` 拒存计数，区分深拷贝失败与超大结果，并通过离线回归。

- [x] 曲目搜索文本投影抽至 `ui/track_search_text.js`，限制字段/总文本长度并隔离异常字段访问；大曲库搜索复用有界文本，已通过 636 项 Python 及 Node/UI 离线回归。

- [x] 收藏/歌单引用曲目投影抽至 `ui/library_reference_items.js`，统一限制 ID 补水规模并隔离异常缓存读取；总数与分页渲染复用该边界，已通过 636 项 Python 及 Node/UI 离线回归。

- [x] 元数据提供商 JSON/歌词响应加入 4 MiB/2 MiB 上限并限制 gzip 解压后大小；已通过离线回归。

- [x] ffprobe resolver 输入统一做异常/非文本隔离，避免配置对象阻断探测；已通过独立回归。

- [x] 将轻量 `read_audio_info()` ffprobe 路径并入可测试的 `probe_runner.py`，统一输出边界与 native fallback 语义。

- [x] ffprobe/native fallback 隔离异常读取器与非映射结果，避免损坏容器状态阻断扫描；已通过独立回归。

- [x] 清理扫描器在封面/ID3 模块拆分后残留的未使用解析导入，保持职责边界清晰。

- [x] 发布证据校验绑定 provenance 版本与 FPK 文件名，防止恢复时跨版本误配；已通过离线回归。

- [x] 将 ffprobe 执行与 native fallback 编排拆至可测试的 `probe_runner.py`，保持 `library.py` 兼容入口并通过元数据/媒体回归。

- [x] 音频信息快速探测路径限制 ffprobe 输出为 2 MiB，超大响应安全回退并通过离线回归。

- [x] 将侧车封面发现与读取拆至可测试的 `sidecar_cover.py`，保留兼容 API 并限制单文件 8 MiB。

- [x] M4A/WAV FFmpeg 封面提取在生成阶段加入 8 MiB `-fs` 上限，并通过命令契约离线回归。

- [x] M4A/MP4 封面 atom 解析增加 32 层递归深度上限并通过深层畸形容器离线回归。

- [x] 将 ID3 读取、ID3v1 回退及解析入口集中到可测试的 `id3_container.py`，保留兼容 API 并通过离线回归。

- [x] ID3 容器读取限制头部声明 payload 为 16 MiB，异常长度安全拒绝并通过离线回归。

- [x] 将 MP3/WAV/DSF 的 ID3 容器定位拆至可测试的 `id3_container.py`，保留兼容 API 并通过媒体格式与元数据回归。

- [x] 将 FLAC/APE 封面读取拆至可测试的 `cover_readers.py`，保留 `library.py` 兼容 API 并通过媒体格式回归。

- [x] 封面读取增加 FLAC/APE/FFmpeg/侧车文件资源上限，APE 改为尾部标签定点读取；媒体格式回归通过，避免异常封面输入放大内存。

- [x] 将扫描结果稳定排序抽至可测试纯函数 `sort_scan_items()`，统一扫描路径并隔离异常字段、限制排序文本；已通过 623 项 Python 及全部 Node/UI 离线回归。

- [x] 将扫描签名摘要逻辑抽至纯函数 `digest_signature_parts()`，统一普通扫描与快速签名路径边界并通过 622 项 Python 及全部 Node/UI 离线回归。

- [x] 将扫描旧索引路径映射抽至可测试纯函数 `build_previous_item_index()`，隔离异常迭代器/记录/path 访问并通过 621 项 Python 及全部 Node/UI 离线回归。

- [x] 扫描结果去重限制字符串曲目 ID 为 4096 字符，超长损坏 ID 安全跳过并通过 619 项 Python 及全部 Node/UI 离线回归。

- [x] 扫描结果排序键文本限制为 4096 字符后再折叠大小写，避免异常元数据造成排序资源放大；已通过 618 项 Python 及全部 Node/UI 离线回归。

- [x] 多根扫描分区生成器改为逐项安全读取，中途异常时保留已完成分区结果并通过 617 项 Python 及全部 Node/UI 离线回归。

- [x] 扫描结果曲目生成器改为逐项安全读取，中途异常时保留已读取记录并通过 616 项 Python 及全部 Node/UI 离线回归。

- [x] 扫描签名聚合限制单条签名文本 4096 字符，配合总条目上限降低异常输入内存放大；已通过 615 项 Python 及全部 Node/UI 离线回归。

- [x] 扫描结果去重隔离曲目 ID 的哈希、集合查找和插入异常，坏 ID 安全跳过并通过 614 项 Python 及全部 Node/UI 离线回归。

- [x] 多根扫描分区隔离异常历史 `path` 字段访问，损坏记录跳过且后续有效记录继续处理；已通过 613 项 Python 及全部 Node/UI 离线回归。

- [x] 扫描结果去重阶段隔离异常曲目 ID 访问，损坏记录安全跳过并通过 612 项 Python 及全部 Node/UI 离线回归。

- [x] 扫描签名生成器增加 200,000 条上限并隔离迭代中途异常，避免扫描收尾资源放大或中断；已通过 611 项 Python 及全部 Node/UI 离线回归。

- [x] 扫描结果排序键读取隔离异常字典访问，避免单条损坏记录中断整批排序；已通过 610 项 Python 及全部 Node/UI 离线回归。

- [x] 多根扫描历史 `items` 迭代器增加异常隔离，损坏缓存安全回退为空结果并通过 609 项 Python 及全部 Node/UI 离线回归。

- [x] 多根扫描结果在艺术家/专辑/曲名相同的情况下使用稳定 `id` 末级排序键，避免大曲库分页与前端缓存顺序抖动；已通过 608 项 Python 及全部 Node 离线回归。

- [x] 多根历史索引分区隔离异常根容器，避免入口异常中断扫描并通过离线回归。

- [x] 多根扫描对重复历史路径复用根归属判断，减少大库分区阶段重复路径计算并通过离线回归。

- [x] 统一库路径文本投影策略，写入模块复用 `library_paths.py` 的边界实现并通过离线回归。

- [x] 根摘要与扫描归一化回调边界完成异常容器隔离，并通过离线回归。

- [x] 扫描记录归一化隔离根目录容器及回调异常，避免坏配置中断整批索引写入并通过离线回归。

- [x] 根目录摘要生成隔离异常容器，避免损坏缓存中断索引保存并通过离线回归。

- [x] 曲目持久化准备阶段对 `folder` 字段施加文本边界，隔离异常对象并通过离线回归。

- [x] 曲库批处理入口隔离异常输入容器，避免异常布尔/迭代行为中断写入线程并通过离线回归。

- [x] 前端查询参数页码和页大小增加异常数值安全回退，避免分页请求被畸形状态阻断并通过 Node 回归。

- [x] 前端曲库查询参数组装抽至 `library_query_params.js`，保留分页/分组/目录语义并通过 Node 回归。

- [x] 前端收藏/歌单补水增加全命中缓存短路，避免大库场景创建空请求池并通过 Node 回归。

- [x] 批量曲库写入对单条准备异常执行隔离并继续后续记录，避免整批中断并通过离线回归。

- [x] SQLite 曲目准备阶段对 `_index_root`/CUE 路径复用文本长度边界，避免私有根字段绕过安全投影并通过离线回归。

- [x] 曲目持久化准备阶段复用路径文本上限，避免独立调用绕过写入边界并通过离线回归。

- [x] 曲库写入前归一化隔离损坏映射和异常迭代器，避免单条坏缓存中断整批索引写入并通过离线回归。

- [x] 扫描结果写入前对 `path`/`cue_path` 施加 4096 字符文本边界，隔离异常 folder 转换并通过离线回归。

- [x] 文件管理定位路径增加文本类型与 4096 字符上限，异常输入安全拒绝并通过离线回归。

- [x] 多根扫描结果聚合隔离不可哈希 ID、异常迭代器和回调异常，并通过离线回归。

- [x] 多根扫描按根目录分区旧索引，避免大曲库多根配置重复构建历史映射，并通过离线回归。

- [x] 多根扫描结果去重、排序与签名聚合抽至独立纯模块 `library_scan_results.py`，保留扫描行为并通过离线回归。

- [x] 曲库分页/ID 参数的内部边界配置增加安全整数投影，避免异常对象转换阻断大库查询。

- [x] 进程监管历史错误状态在注册/状态读取时重新受限投影，避免恢复数据绕过诊断边界。

- [x] 曲库分页 offset 增加统一上限，避免异常大库请求构造无界 SQLite 偏移量并通过离线回归。

- [x] 进程监管错误文本抽至独立受限策略模块，拒绝异常对象字符串化并限制长度；已通过离线回归。

- [x] 前端搜索入口增加 4096 字符上限并拒绝异常输入，降低大曲库查询和缓存键开销。

- [x] 资源门禁等待秒数累计捕获极大整数溢出，异常指标输入安全忽略并通过离线回归。

- [x] 分页请求键页码规范化拒绝异常/非有限输入，继续完善前端大曲库请求边界。

- [x] 分页请求键对异常恢复状态增加 JSON 序列化容错，继续推进前端大库请求生命周期边界。

- [x] 前端分页响应权重计算抽至独立纯模块并通过 Node 回归，继续推进大库缓存逻辑可测试边界。

- [x] HTTP 慢请求摘要计数增加既有累计上限，避免长期运行指标无界增长并通过离线回归。

- [x] 前端 LRU 数值投影捕获 `Symbol`/异常 `valueOf()`，缓存配置异常时安全回退并通过 Node 回归。

- [x] 查询缓存数值规范化捕获极大整数浮点溢出，异常 TTL/容量/权重配置安全回退并有离线回归。

- [x] 可选音频指纹任务限制超时和时长输入并校验 fpcalc JSON 结构，异常输出安全失败。
- [x] 音频指纹输入边界抽至独立纯策略模块，便于离线测试和后续实现替换。
- [x] CUE 时间数值转换拒绝异常对象和非有限值，畸形 INDEX 不再中断扫描。
- [x] CUE 数值规范化抽至独立纯策略模块，解析流程与策略边界分别可测试。
- [x] CUE TRACK 曲序增加长度与范围上限，超长数字安全回退，避免畸形文件中断扫描。
- [x] CUE 解析增加 4096 字符单行上限，避免超长损坏行放大扫描资源。
- [x] CUE 解析增加 20,000 行上限，避免异常文件无限消耗扫描资源。
- [x] CUE 解析对非可迭代输入安全回退，避免异常索引调用中断扫描。
- [x] 并发资源整数策略对非法默认值安全回退，避免诊断字段泄露异常对象。
- [x] HTTP 延迟聚合对单次耗时、最大值、计数与累计时长统一设上限，避免长期运行的 diagnostics 指标无界增长。
- [x] 通用 Tag 曲序解析增加长度/范围边界，避免超长数字触发大整数异常。
- [x] 文件名元数据回退限制 basename 长度并拒绝非文本路径，避免扫描文本资源放大。
- [x] 内存曲库回退查询的文本、过滤、搜索、路径匹配和排序键抽至独立纯模块，查询编排不再重复处理并保留异常输入边界。
- [x] 曲库搜索/分组 SQL 边界拒绝异常对象字符串化，避免异常查询参数在规范化阶段放大或阻断请求。
- [x] 内存曲目查找与文件位置解析拒绝异常 ID/路径字段，避免回退路径隐式字符串化。
- [x] 可观测性计时与计数规范化捕获超大整数溢出，异常指标输入安全回退。
- [x] 内存曲库回退搜索词增加 4096 字符上限并拒绝非文本输入，覆盖绕过查询规范的直接调用。
- [x] 曲库搜索 SQL 条件构造抽至独立纯策略模块，保留 FTS/LIKE 兼容语义并支持独立测试。
- [x] 曲库 SQL 搜索纯策略自身限制直接调用的搜索文本长度，防止超长 LIKE/FTS 参数放大。
- [x] 曲库 SQL 搜索策略限制 alias/rowid 标识长度，避免异常查询构造超长 SQL。
- [x] 曲库 SQL 搜索策略校验 alias/rowid 标识字符集，异常标识安全回退。
- [x] 扫描状态错误文本复用受限策略，避免异常对象字符串化和超长状态污染。
- [x] 扫描异常日志复用受限错误文本，保持状态与日志边界一致。
- [x] 文件位置解析隔离损坏/非字典缓存条目，避免文件管理跳转因索引形状异常中断。
- [x] health/diagnostics 数字摘要捕获超长文本整数转换异常，保持公开接口可序列化。
- [x] diagnostics 顶层/嵌套状态增加字典投影，隔离损坏依赖载荷的属性访问异常。
- [x] 公开摘要整数策略规范化 default/maximum，防止异常边界穿透序列化。
- [x] 公开摘要整数策略将 default 同样裁剪到 maximum，避免回退值绕过计数上限。
- [x] 公开摘要文本策略规范化 maximum 长度，隔离异常配置导致的切片错误。
- [x] 公开摘要文本策略拒绝非文本 default，保证回退值可序列化。
- [x] 公开摘要文本策略裁剪 default 回退文本，避免异常输入绕过长度上限。
- [x] 发布 provenance 回写并校验最终 FPK `artifact_sha256`，增强会话删除后的产物恢复核对。
- [x] SHA256SUMS 生成后回读校验最终 FPK 摘要与包名，避免损坏校验文件进入发布目录。
- [x] 曲库分组条件构造抽至独立纯策略模块，保留“未分类”兼容语义并支持独立测试。
- [x] 封面缓存尺寸参数拒绝布尔/异常对象并安全处理超大整数，避免请求路径转换异常。
- [x] 封面缓存源版本回退拒绝异常对象字符串化并限制文本长度，保持不可访问媒体的安全失效语义。

当前源码版本：`0.2.34`。本清单只记录仍然有效的工作；历史阶段事项、已完成实现和验证证据见 `PROJECT_CONTEXT.md` 与 `CHANGELOG_AI.md`。

## P1：可靠性与发布质量

- [x] 前端曲目 LRU 缓存容量拒绝非有限配置并限制最大 50,000 项，避免异常设置令 Map 无界增长；默认容量和当前队列保护不变。
- [x] 服务端查询缓存的 TTL、容量和权重拒绝非有限数值及自定义对象转换，继续使用既有安全范围和默认值。
- [x] ID3v1 固定字段解码抽至可测试纯模块，与 ID3v2 解析边界统一并保留编码回退。
- [x] 前端批请求池增加 4,096 批次与 32 并发硬上限，避免大库页面切换时初始化无界数组或并发 worker。
- [x] 封面懒加载调度器增加 32 并发上限并拒绝非有限配置，保持可见区优先及取消生命周期。
- [x] 批请求池取消原因拒绝任意对象字符串化并限制文本长度，避免异常取消路径影响页面调度。
- [x] 通用前端 LRU 缓存增加条目数/权重非有限值回退和硬上限，避免异常配置造成无界增长。
- [x] 封面懒加载调度器对 null/非对象配置安全回退，避免异常初始化阻断页面渲染。
- [x] 前端全量分页计划限制最多 8,192 个后续 offset，并拒绝非有限总数，避免大库异常响应创建无界数组。
- [x] 分页结果合并改为逐项追加并限制 200,000 条，避免超大页展开运算造成前端调用栈或内存峰值。
- [x] 表格列配置拒绝异常对象并限制 32 列，避免异常偏好设置造成无界表头渲染。
- [x] 分页结果合并总数仅解析基础数字/文本一次，拒绝异常对象强制转换，保持结果上限和截断逻辑。
- [x] 表格列宽偏好按有限数值及列级上下限规范化，避免异常 CSS Grid 宽度影响大库渲染。
- [x] UI 状态同步调度器对 null/非对象配置安全回退，避免生命周期初始化异常阻断页面同步。
- [x] UI 同步调度器对 null/原始定时器宿主安全回退，避免 WebView 注入异常阻断状态刷新。
- [x] 播放设备目标展示限制 256 项并拒绝异常目标 ID 强制字符串化，保持本机/MPD/DLNA 排序语义。
- [x] 队列定位与当前播放页计划拒绝异常索引强制转换，保持分页、整页重绘和滚动定位语义。
- [x] ConcurrencyGate 累计等待秒数封顶 10^9，避免长期进程指标无界增长。
- [x] 查询缓存键拒绝 NaN/Infinity 浮点值，避免不稳定数值污染 LRU。
- [x] 队列定位计划对 null/非对象输入安全回退，避免异常状态 payload 阻断队列页面渲染。
- [x] 播放设备默认名称投影拒绝异常对象字符串化，保持目标上限与排序优先级。
- [x] SQLite 曲目行 JSON 解码增加 1 MiB 载荷上限并仅接受对象，避免异常数据库行放大解析内存。
- [x] SQLite 行解码对小型 ASCII JSON 采用快速长度路径，仅对近上限多字节内容执行 UTF-8 字节校验，降低大库解析分配。
- [x] SQLite 行解码对 None/非可迭代值及无效行对象安全回退空结果。
- [x] SQLite 行字段访问异常按单行隔离，不让异常适配器中断同页剩余曲目解码。
- [x] 资源并发/超时配置捕获极大整数浮点转换溢出，异常值安全回退默认值。
- [x] 曲库已保存计数策略拒绝异常视图/过滤对象字符串化，保持热点视图快捷统计语义。
- [x] 曲库分页数值解析捕获超长数字溢出并安全回退，避免异常请求阻断大库列表查询。
- [x] 进程监管注册参数增加命令与重启策略边界，拒绝非有限/异常对象配置，避免后台守护进程资源策略无界。
- [x] 进程监管轮询间隔增加有限范围保护，避免异常配置导致忙轮询或监控停滞。
- [x] 服务端配置端口、资源上限与超时统一拒绝布尔/异常对象输入并安全裁剪超大整数。
- [x] 配置保存路径复用同一边界规范化，异常设置不会阻断保存接口。
- [x] 代理端口展示文件写入复用端口边界规范，避免异常输入破坏恢复所需的服务端口信息。
- [x] 封面缓存版本同时纳入媒体文件大小与 mtime_ns，避免粗粒度时间戳下快速 Tag/封面写入继续命中旧缓存。

- [x] ffprobe 元数据读取增加 2 MiB stdout 硬上限；超限载荷跳过 JSON 解码并回退原生音频信息，防止异常探测输出放大资源消耗。

- [x] DLNA GENA 事件通知在固定 worker 外增加 64 项提交前 pending 上限，避免 `ThreadPoolExecutor` 内部无界排队；health/diagnostics 与 DLNA 诊断公开订阅、队列、峰值、接受/丢弃压力，且不泄露回调地址。
- [x] UPnP/DLNA 设备发现采用单 worker 准入并记录重叠跳过、成功与失败；失败不清空上次缓存。health/diagnostics 公开脱敏的 worker、缓存年龄和计数，避免并发刷新时线程无界增长。
- [x] 扫描持久化的 tracks/covers/CUE 写入改为 500 项有界批次，避免大音乐库按歌曲逐条跨越 Python/SQLite；同一事务清理曲目从 CUE 段变为普通文件时遗留的 `cue_tracks` 索引。
- [x] 长播放队列的 SQLite 分批补水与按原请求顺序重组已抽至独立 adapter；单曲 ID 查询与长队列复用受限文本规范，避免超长/异常对象在缓存或 SQL 边界触发字符串化。
- [x] 发布级 `SOURCE_PROVENANCE.json` 增加受限的 Git 可用性状态（干净、脏、仅 commit、不可用），在源树并非完整 Git 工作树或构建会话已删除时仍可判定恢复证据缺口；不将本机 Git 错误内容写入产物。
- [x] 已在 Git 忽略的 `artifacts/_scratch/release-governance-20260827-144009/` 完成一次实际 fnpack 隔离构建与解包自检：FPK、SHA256、暂存源清单、fnpack 哈希与 Git 状态均可恢复核对；不替代正式发布或 fnOS 安装验收。
- [x] 持久化根目录摘要的 JSON/长度/完整性与数值校验已抽至独立纯模块；损坏、超长或配置不匹配摘要继续自动回退 SQLite。
- [x] 内部播放恢复的长队列按 ID 补水改为同连接 120 项分批读取，拒绝非文本/超长 ID 并保持首次请求顺序，避免 SQLite 变量上限。
- [x] SQLite 窗口分页的执行与旧 SQLite 精确回退已从 `library.py` 抽至独立纯模块，歌曲、分组和文件夹路径共用同一可测试边界。
- [x] 搜索、分组及目录筛选的歌曲分页优先以单次窗口查询返回总数和页面；无筛选元数据快捷计数不变，空越界页和旧 SQLite 自动回退精确双查询。
- [x] 根目录浏览复用扫描保存的受限根摘要（曲目数/封面曲目 ID），正常缓存未命中不再聚合全表；旧或损坏索引自动回退 SQL，摘要聚合有独立纯函数回归。
- [x] FFmpeg 资源门禁将等待超时与等待队列满分开计数，并经转码 health/diagnostics 摘要安全暴露，便于离线和现场诊断并发压力来源。
- [x] 普通专辑/歌手/作曲家/类型与文件夹分页也优先在单次窗口查询中读取总数；空越界页和旧 SQLite 自动回退精确双查询，避免大库浏览正常页面重复 COUNT。
- [x] 100,000 条合成曲目 SQLite 分页/分组/目录/根摘要/搜索离线基准复核：首/中/尾分页有界，分组、顶层目录与根摘要返回正确，FTS5 trigram 检索明显快于 LIKE 基线；结果在 `artifacts/large-library-benchmark-100k.json`，不替代真实 NAS 验收。
- [x] 浏览器分页响应缓存同时限制条目数和累计歌曲/分组/目录内容权重，超大单页不再挤出全部热点缓存。
- [x] “从当前开始播放全部歌曲”复用当前分页的有界响应缓存，首页已加载时不再重复请求第 0 页；扫描、刷新与曲库变更仍统一失效。
- [x] 分页、搜索、分组、目录和按 ID 补水的查询文本均由统一规范限制长度并拒绝异常对象字符串化，防止 SQL 参数与缓存键被畸形输入放大。
- [x] 分组、目录和根目录浏览已复用可测试的输入规范；分页、排序、路径、搜索及作者/作曲者过滤在进入 SQLite 和查询缓存前统一受限。
- [x] 元数据全量协调在单次 SQLite 事务复用待办预算快照，避免大曲库为每个新任务重复统计 pending 队列；优先歌词逐出和队列上限语义保持。
- [x] 元数据全量协调用 SQLite 临时活动曲目表替代完整 Python 曲目/ID 双列表，并流式创建任务，降低大库扫描后的协调内存峰值。
- [x] 元数据全量协调的专辑、艺术家、作曲者活动集合也由 SQLite 临时表维护，取消大分组库的 Python 实体键累积。
- [x] 收藏/歌单按 ID 批量补水延迟详情 LRU 淘汰至所有批次写入后，避免大列表重复扫描缓存，同时保留当前播放队列保护。
- [x] 艺术家/作曲家专辑的正常分页优先将分组总数与取页合并为单次 scoped CTE 窗口查询；旧 SQLite 不支持窗口函数时自动回退精确双查询，越界页保持准确总数回退。
- [x] 服务端 SQLite 查询缓存的路径、命名空间与键值集合均受固定类型、长度和项数约束，非法键不缓存，避免常驻 LRU 接收异常对象或无界迭代器。
- [x] 服务端 SQLite 查询缓存同时限制键数量与歌曲/分组/目录结果权重；超大页跳过缓存，health/diagnostics 暴露权重预算与拒存压力。
- [x] HTTP 延迟聚合仅接受有限基础数值，拒绝 NaN、无穷大、负数及自定义对象，保持 health/diagnostics 指标可序列化。
- [x] health/diagnostics 的公开计数与文本摘要统一使用无副作用的受限规范化；兼容有限数字文本，不调用任意对象转换，避免异常依赖状态污染支持接口。
- [x] 根目录浏览复用短期查询缓存；重复进入文件夹首页不再重复 root 聚合，扫描/索引写入后立即失效并回归验证新统计。
- [x] 元数据 jobs、资产、实体、歌词和 Tag 写入摘要采用 750ms 的线程安全短期 SQLite 快照；health、diagnostics 与元数据页面的同周期读取合并为一次聚合，任务/实体/歌词写入主动失效，返回值隔离，公开缓存 TTL/年龄/命中/未命中指标。
- [x] 外部 Renderer 的 URI ID 解析、停止抑制与无进度到期判定已从 `server.py` 抽至纯策略模块；自动下一曲的播放副作用仍保留在请求/监控编排层，新增无设备回归覆盖异常与非有限输入。
- [x] 大音乐库查询缓存的 health/diagnostics 摘要采用 750ms 快照，状态轮询不再反复 O(n) 清理缓存项；普通查询命中不使摘要失效，结构变化与索引失效仍立即反映，并公开受限的 snapshot 指标。
- [x] 查询缓存短期摘要在命中时同步最新压力计数并公开 `age_ms`，便于现场判断摘要新鲜度；保持受限字段投影和结构变化即时失效。
- [x] 扫描的已读取 Tag 到曲库展示记录组装已抽至 `server/library_metadata_presentation.py`；扫描器仍持有 ffprobe/ID3/Vorbis 读取与路径计算，新增 Tag/文件名/未知值纯回归。

- [x] 整库封面预热队列限制为 5000 项并暴露 dropped 计数，避免扫描后预热任务无界暂存。
- [x] 整库封面预热按源身份/版本/尺寸有界去重，减少重复缩略图生成并保留 dropped 观测。
- [x] 诊断大字典脱敏改为有界迭代，避免为截断字段先复制完整映射。
- [x] health/diagnostics 回归明确验证整库封面预热 `limit`/`dropped` 字段，锁定资源上限压力的 HTTP 摘要链路。
- [x] 整库封面预热补充 accepted/completed/failed 运行计数，便于区分排队、完成和失败，不改变 5000 项上限。
- [x] 封面预热按绝对缓存根路径合并 worker，避免同一磁盘缓存因路径写法不同重复排队。
- [x] 整库封面预热限制缓存根 worker 数量（8 个），满载时拒绝可选后台任务并暴露 root_rejected 计数。
- [x] health/diagnostics 明确验证封面预热根级上限与拒绝计数，避免资源压力字段在摘要重构中丢失。
- [x] library health/diagnostics 对封面预热状态采用固定字段投影和数值边界，阻止未知字段或敏感内容进入支持摘要。
- [x] library health/diagnostics 对 query cache 与搜索索引采用固定字段投影和边界归一化，防止未知高基数输入进入支持摘要。
- [x] 搜索索引摘要拒绝对任意对象做字符串化，避免诊断输入在截断前造成内存放大。
- [x] query cache 支持摘要保留实际容量字段 `limit`，并继续拒绝未知输入字段。
- [x] HTTP 延迟桶分类与同步结构化日志写入决策抽至纯策略模块；仅处理基础请求类型，异常对象不触发字符串化，高频成功播放状态/SSE 保持无同步 JSONL 写入。
- [x] DLNA/HTTP 文件名清理规则抽至纯模块并单独回归，避免 server.py 继续承载无状态命名逻辑。
- [x] 端口占用检测与临时端口分配抽至可注入 socket 的纯辅助模块，启动端口逻辑具备无网络离线回归。
- [x] 主机出站地址探测抽至可注入 socket 的纯辅助模块，覆盖网络失败回退与资源释放。
- [x] DLNA/HTTP 文件名清理拒绝任意对象字符串化，异常 Tag 值安全回退，避免路径生成内存放大。
- [x] 公开 CGI 基地址构造抽至纯模块，规范化协议/端口并正确生成 IPv6 URL authority。
- [x] 私网主机判定使用标准 IPv4/IPv6 解析，支持方括号 authority 与端口，避免 IPv6 被冒号截断。
- [x] 私网主机解析从转码模块抽至共享网络模块，转码与公开 URL 复用同一 IPv4/IPv6 边界规则。
- [x] 公开 URL 构造限制 Host/协议输入并拒绝任意对象字符串化，避免 Header 解析前资源放大。
- [x] 扫描错误状态限制为最近 20 条、单字段 512 字符，并抽至纯策略模块防止大库异常路径/文本长期放大内存。
- [x] 将 6 个未被 unittest discover 执行的纯策略测试纳入正式离线门禁；预热去重修复 0 上限并避免先物化完整大库输入。
- [x] 封面预热达到队列上限后不再为 dropped 尾部维护去重身份集合，避免十万级扫描形成额外 O(n) 内存。
- [x] 前端封面懒加载在重渲染/停止后隔离旧观察器和图片回调；无 `IntersectionObserver` 的旧 WebView 以游标按并发补位，避免整页封面任务一次性进入 JS 队列。
- [x] ID3v2 字节帧解析从扫描文件读取层抽至独立纯模块；损坏/截断帧在读取前受长度边界保护，MP3/WAV/DSF 文件定位与 ID3v1 回退保持原调用行为。
- [x] CUE 专辑/曲目/时间索引文本解析从扫描文件读取层抽至独立纯模块；多源音频的段落结束位置、默认曲号和非文本输入均具备回归。
- [x] 元数据服务状态、health 与 diagnostics 暴露受限网络 worker 的活跃数与总上限，并把当前歌曲歌词优先 worker 纳入运行状态；不暴露任务键、路径或凭据。
- [x] 分组与专辑详情封面复用有界可见区调度器（4 并发）；旧 WebView 不再依赖不稳定的原生图片懒加载，本地封面失败后的在线封面回退保持不变。
- [x] 离线 Node 回归改为自动发现全部 `test_*.js`，新增 UI 回归不会再因硬编码脚本清单遗漏而静默跳过。
- [x] 离线门禁加入测试发现契约，阻止新增顶层 pytest 风格函数被 unittest discover 静默跳过。
- [x] 带长度的大库预热输入达到队列上限后直接计算 dropped 并停止尾部迭代，降低扫描后的 CPU 开销。
- [x] 源码卫生检查扩展至全部打包 Python（含 CGI 代理），防止非 server 模块绕过语法/乱码/重复定义门禁。

- [x] 批请求池支持取消生命周期，页面切换时可停止排队批次并释放后续并发槽，保留 get/all 顺序语义。
- [x] 收藏/歌单/队列引用补水接入批请求池取消，快速切换页面时不再继续启动旧批次。
- [x] 分页缓存直接过期命中计入 `expired` 诊断计数，避免 TTL 失效被低估。

- [x] 元数据补全候选支持选择非第一候选。前端只提交候选序号，服务端仅从该歌曲已保存的候选集中取值，再执行既有的“只补空白 Tag”写回。
- [x] 加入可复用本地验证链路的 GitHub Actions 工作流：Python/Node/Playwright、Android Debug 构建和 `fnpack` 包检查使用同一套脚本。
- [x] Android 正式发布构建链路：`tools/build_android_release.ps1` 强制检查签名变量和 keystore，执行 Release 构建、APK 验签、版本核对和 SHA-256 归档；已通过一次性临时 keystore 离线烟雾验证。正式证书仍必须由负责人保管和提供。
- [x] Android WebView 导航期间保持可见；模拟器仪器测试覆盖启动可见性、认证封面代理和双返回登录，避免完成回调延迟造成永久白屏。
- [x] Web UI 的状态同步按页面可见性启停；远程播放优先 SSE，后台释放事件流和非必要轮询，恢复前台后立即补齐状态。大库分页会取消过期查询、合并相同的在途查询，并以 LRU 保留最近访问的浏览器响应，减少快速连续点击和分类往返导致的无效请求与整页重绘。
- [x] MPD 队列恢复、普通控制和 Renderer 命令统一经过串行服务通道；恢复窗口中的命令等待新队列建立，不再使用陈旧 song id。
- [x] 私有局域网直连恢复完整 Web UI；裸 `mpd`/`alsa` 后端目标不再误判为 DLNA；扫描采用连续无进度超时并保留排队、结果和错误状态。
- [x] 元数据 Tag 写回与后台抓取拆分；写回默认关闭，关闭时保留待写任务并在最终文件修改边界强制拦截。
- [x] Android FN Connect 长期闲置恢复刷新公网路由，并按短 token、longToken、保存密码回退；凭据拒绝与网络错误分开处理。
- [x] 局域网匿名接口按风险分层：保留浏览与播放控制，高风险配置、扫描/元数据写入和文件管理只接受 fnOS 内部认证代理；配置写盘失败不再污染运行时状态。
- [x] 分页请求不再把 HTTP 错误伪装成空音乐库或残缺播放队列；CGI 保留后端结构化错误，强制扫描可升级普通排队请求。
- [x] Android 登录与 FN Connect 请求具备可取消生命周期，嵌套 token 和显式 URL 协议正确解析，通知封面缓存有容量/过期边界，媒体服务退出会释放网络资源。
- [x] 大音乐库子串搜索优先使用运行时探测的 SQLite FTS5/trigram 外部内容索引；不支持 FTS5/trigram 或关键词少于 3 个字符时保持原有 `LIKE` 语义。索引在全量保存后重建，模式通过 library status、health 和 diagnostics 可观测；短期分页缓存采用 LRU，热点页不会被 FIFO 无谓逐出。
- [x] 普通歌手/作曲家/专辑/类型详情页的分组过滤保持 SQLite 可索引：正常值使用直接等值，`未分类` 显式兼容空值、NULL 和同名真实 Tag；查询计划回归锁定既有分组索引。
- [x] HTTP 延迟观测采用固定路由分类和有界汇总，覆盖普通、错误、静态与 DLNA 请求；health/diagnostics 仅公开 count/avg/max/slow，不保留 URL 查询、文件路径或歌曲信息。
- [x] 高基数歌曲详情补水请求在 HTTP 边界去重并限制 120 个 ID，超限在进入 SQLite 前拒绝；前端与 Android 的既有 100 项分批请求保持兼容。
- [x] 高频成功静态资源请求仅进入有界指标而不逐个同步落盘结构化日志；API/写操作/失败响应仍保留日志，降低封面和媒体并发被日志 I/O 串行化的风险。
- [x] 封面去重锁表改为弱引用生命周期：并发相同缩略图继续合并，历史版本完成后不再永久保留锁对象。
- [x] 浏览器歌曲详情缓存增加有界 LRU，并保护当前播放队列，避免大收藏/歌单补水造成无界 Map 增长。
- [x] ffprobe Tag 别名归一化抽为纯函数并加入独立回归，避免扫描和元数据服务的字段优先级分叉。
- [x] ffprobe 已提供完整核心 Tag 时跳过重复的整文件原生 Tag 扫描；不完整 Tag 继续补缺。
- [x] ffprobe JSON 的 Tag/音频字段归一化抽为独立纯模块，保留格式 Tag 后由流 Tag 覆盖的既有优先级。
- [x] 无过滤的全库分页复用 SQLite 索引摘要中的 `track_count`，避免大库每翻一页重复执行 `COUNT(*)`；旧索引或过滤/搜索路径仍回退实时计数。
- [x] 健康状态摘要同时复用索引中的 `track_count`/`dsd_count`，避免 `/api/health` 和诊断快照在高频刷新时重复扫描 `tracks`；旧索引安全回退实时统计。
- [x] 浏览器分页响应 LRU 已抽至 `ui/lru_cache.js`，并纳入独立 Node 回归与离线门禁；页面请求只负责命中/写入/刷新，不再重复维护淘汰细节。
- [x] 浏览器歌曲详情 `itemCache` 的容量限制、播放队列保护和 LRU 热度更新已抽至 `ui/item_cache.js`，避免大库补水缓存策略继续耦合页面状态。
- [x] 修正详情缓存批量写入时的保护时序：`set()` 不再在调用方提供播放队列保护 ID 前提前淘汰，批量补水后统一执行受保护 LRU 淘汰。
- [x] 音乐库状态提示判定已抽至纯模块 `server/library_status_presentation.py`，路径权限、扫描和空库提示拥有独立回归。
- [x] SQLite 曲目 JSON 解码已抽至 `server/library_rows.py`，分页、补水、单曲定位和索引加载共用同一容错规则。
- [x] `recent`、`random100`（无搜索）和 DSD 视图复用索引摘要计数，避免大库切换这些视图时重复扫描 `tracks`；带搜索仍实时计数。
- [x] “从当前开始播放所有歌曲”在按 ID 补水时使用有界批请求池（最多 4 个并发、每批 100 项），保持结果顺序并降低大列表等待时间；页面后台补水预取并按顺序消费，仍保持首批优先。
- [x] 页面后台收藏/歌单/队列补水也使用同一有界批请求池；仍按批次顺序消费，首批优先渲染和错误回收语义保持不变。
- [x] “从当前视图加载全部歌曲”先取得总数，再以最多 4 个并发分页请求按 offset 顺序合并，避免大库逐页串行等待。
- [x] 批请求池回归明确锁定最大并发数，防止未来改动退化为无界 Promise.all。
- [x] 全量分页 offset 规划已抽至 `ui/library_page_plan.js`，页面请求编排不再混入页码边界计算。
- [x] 多选分组加载和批量删除文件位置解析统一限制为最多 4 个并发，保持选择顺序并避免大选择集触发无界 Promise.all。
- [x] 批量分组加载与文件位置解析的有界并发契约已纳入 UI 回归，锁定 4 并发请求池调用。
- [x] 播放设备排序与失效目标回退判定已抽至 `ui/device_target_presentation.js`，保持原有本地回退语义并加入独立 Node 回归。
- [x] FFmpeg 并发闸门增加有界等待队列（默认 32 个等待者），超限立即拒绝并在快照区分等待队列拒绝与超时，避免突发请求无限堆积。
- [x] HTTP 观测将高频 `/api/library/items` 详情补水请求归入音乐库分页桶，避免大库性能指标被 `other` 淹没。
- [x] FFmpeg 等待者上限支持配置项 `ffmpeg_max_waiters`（默认 32，范围 0–256），转码资源快照报告实际值并保持旧配置兼容。
- [x] 修复转码状态汇总丢失等待队列压力字段的问题；health/diagnostics 现在保留 `waiter_rejected` 与 `waiter_limit`。
- [x] 观测计数器改为固定内部词汇表，拒绝任意事件名，避免异常输入导致 diagnostics counter Map 无界增长。
- [x] SQLite 扫描写入前的路径/根目录归一化抽至 `server/library_write.py`，以依赖注入方式保持可测试且不改变事务边界。
- [x] SQLite 曲目/CUE 持久化行准备抽至 `server/library_write.py`，不改变事务、索引或封面写入边界，并覆盖私有索引根字段隔离回归。
- [x] 全量分页结果的顺序合并、空页终止和总数截断抽至 `ui/library_page_merge.js`，避免大列表编排函数同时承担纯数据规则。
- [x] 播放状态请求的 `target_id`/`device_id` 归一化抽至 `server/playback_status_spec.py`，保持浏览器、列表参数和空值的兼容语义。
- [x] 成功播放状态轮询/SSE 请求从同步结构化日志中剔除，保留有界计数、延迟和错误日志，降低多客户端并发下的磁盘 I/O。
- [x] CUE/APE 播放位置归一化与段结束判定抽至 `server/playback_cue_position.py`，保持自动下一段触发逻辑在请求层并可独立回归。
- [x] 分页查询缓存写入时惰性清理过期条目，保持容量上限并提高热点页留存率；新增回归覆盖过期项不参与逐出。
- [x] 分页缓存过期回归使用注入式时钟，避免离线门禁依赖实际 sleep 时序。
- [x] 发布清单回归校验 UI 入口声明的本地 CSS/JS 资产存在、唯一并使用统一 cache-build 标记。
- [x] 大库分页计数策略抽至 `server/library_count_policy.py`，避免新增视图误用实时全表 COUNT；搜索/过滤仍安全回退实时统计。
- [x] 全量分页补水延迟 itemCache 淘汰至批次合并完成后，避免每页重复扫描 12,000 项 LRU；当前播放队列保护仍保留。
- [x] 收藏/歌单/队列引用补水延迟 itemCache 淘汰到批次消费完成后，避免大收藏重复遍历 LRU。
- [x] 离线门禁自动发现 index.html 中的本地 JS 资产并执行语法检查，减少新增模块漏检风险。
- [x] 分页缓存 diagnostics 暴露 `expired` 计数，区分 TTL 失效与 LRU 容量逐出，便于定位大库命中率变化。
- [x] itemCache LRU 淘汰改为单次迭代，避免大批量补水时 O(n²) 重复扫描；当前播放队列保护仍有效。
- [x] 离线门禁自动发现 UI JS 的脚本契约加入静态回归，防止发布治理检查被意外回退。
- [x] 批请求池为排队批次提供稳定 Promise，修复直接调用 `all()` 时未启动批次提前返回的问题。
- [x] 分页缓存构造参数增加 TTL/容量上限（0.1–3600 秒、1–4096 项），异常配置安全归一化并纳入回归。
- [x] 增量扫描缓存复用判定抽至 `server/scan_reuse_policy.py`，保留 size/mtime/metadata_version 三字段一致性条件。
- [x] 诊断脱敏增加深度、集合项数和字符串长度上限，防止异常输入在日志序列化前放大内存。
- [x] 结构化日志序列化失败安全降级，避免异常字段创建空文件或反向影响业务请求。
- [x] 结构化日志单条记录限制为 64 KiB，超大字段降级为脱敏摘要，避免单次事件造成资源放大。
- [x] 分页缓存快照在报告容量前清理过期条目，避免健康/诊断指标误报缓存压力。
- [x] 查询缓存读取路径统一校验内部时间戳；损坏条目隔离并计入 `uncacheable`，避免异常结构中断大曲库请求。
- [x] 曲库查询缓存健康摘要新增 `saturated`，区分条目/权重预算耗尽与普通低命中率，不暴露查询参数、路径或曲目。
- [x] 曲库缓存饱和度投影隔离损坏内部权重，避免 health/diagnostics 在异常状态下抛错。

## P2：部署与外部系统验收

- [x] FFmpeg、转码、封面预热和元数据待办均使用有界资源模型；整库封面预热已分页、低速、可取消并让位于交互播放，列表可见封面预热也已改为每缓存目录单 worker、96 项有界去重队列。health/diagnostics 通过共享快照公开 FFmpeg 与封面预热的脱敏队列、活跃/等待、峰值、拒绝及丢弃指标。
- [x] 版本、服务头、UI 缓存键和 Android `versionCode`/`versionName` 统一；源码卫生、结构化日志、状态并发合并、DLNA Browse/SystemUpdateID 均有自动回归。
- [x] App Center manifest、安装/设置向导和生命周期回调的端口契约已自动校验；升级时旧音乐路径使用结构化 JSON 迁移，不再依赖空格敏感的 `grep/sed`。
- [ ] 将 CI 工作流推送到实际远程仓库并完成首次云端运行。目前仓库未配置 Git remote，因此不能伪造云端执行结果。
- [ ] 核实 fnOS 防火墙/反向代理隔离，并在目标固件抓取 `user.login`、`user.authToken`、`user.tokenLogin` 与 CGI token 交接的真实协议边界。
- [ ] 在 UAPP、中子和 BubbleUPnP 实体客户端复测 DMS Browse、分页、封面和播放；协议自动化已覆盖空 Search 能力、DLNA DIDL 命名空间和公开 JPEG_TN 封面路由。
- [x] JRiver Media Center 36 主动投送已复测：标准 `upmpdcli` 兼容 DIDL 和公开 JPEG 封面端点均正常，JRiver 能播放音频但不请求 `albumArtURI`，其 MCWS 远程条目取图返回 HTTP 500。通用 DLNA 控制端已无可继续修正项；若必须让 JRiver 显示，只能另行评估其专用 MCWS/vendor 集成。
- [x] fnpack 构建会在每个发布目录生成 `SOURCE_MANIFEST.sha256` 与 `SOURCE_PROVENANCE.json`，记录实际暂存源树、asset build、Git 基线及工作树是否有未提交内容；根目录源码清单另由离线回归实时核对，删除会话后可据此核对或复现 FPK 来源。内容派生的静态资源 build 与 FPK 解包校验会从 `index.html` 自动发现所有带构建标记的本地 CSS/JS，避免同版本重打包或新增模块留下旧 Web/WebView 缓存。
- [x] 发布 provenance 同时记录实际 fnpack 二进制 SHA-256；离线门禁会解析全部 PowerShell 工具脚本，打包前即可阻止脚本语法损坏。

## P3：可维护性清理

- [x] 音乐库路径许可、规范化、合并与配置写入统一归属 `library.py`；设置 API、扫描与 SQLite 使用同一身份规则。
- [x] 过期 Spotify 配置已移除；已知乱码、重复字典键、重复作用域定义和不可达控制流由源码卫生测试持续拦截。
- [ ] 继续按可测试边界拆分 `server.py`、`library.py` 与 `app.js`。播放队列请求归一化与 MPD 同步判定已抽至 `server/playback_queue_policy.py`；SQLite 搜索索引模式投影与 FTS 使用阈值已抽至 `server/library_search_index_policy.py`；循环状态、中文文案和图标 SVG 已统一抽至 `ui/repeat_mode_policy.js`，均通过独立回归；曲目展示、队列分页/重绘决策、页面同步调度、封面懒加载与歌曲表头展示已分别抽至 `ui/track_presentation.js`、`ui/queue_presentation.js`、`ui/ui_sync_scheduler.js`、`ui/cover_load_scheduler.js`、`ui/track_table_presentation.js`；服务端曲目 API 表示、分页请求规范（含分组/目录共享可选页窗口）、短期分页缓存、健康响应组装、HTTP worker 指标投影、播放目标响应、UPnP 设备选择、音乐库状态、路径规则、扫描控制、写入前归一化、元数据文本规范、原生音频容器读取和转码资源快照已分别抽至对应纯模块；前端分页请求键与响应缓存/inflight 加载器已抽至 `ui/library_load_key.js`、`ui/library_response_loader.js`；SQLite 初始化与失效边界具备独立回归。后续不得为降低行数做机械移动，每次抽取必须保留独立回归。
- [x] 历史检查目录和构建残留已归档至 `artifacts/_scratch/`，并纳入 Git 忽略规则；正式发布包和测试缓存保留用于回滚与复现。

## P0：外部验收（离线不可验证）：必须依赖真实设备或外部材料

- [ ] USB DAC：物理热插拔、设备重连以及实体 Android 后台或息屏长时控制。跨采样率切歌、暂停/恢复/seek 已在 TEAC UD-301 验收通过。
- [ ] DSD：使用 DoP-only DAC 验证 DSF/DFF 无隐式 PCM fallback。
- [ ] DLNA Renderer：使用真实原生 DSD Renderer 验证源码直推、采样率保持、自动下一曲和断开恢复。
- [ ] AirPlay：在具备 `shairport-sync`/`nqptp` 的环境验证 Receiver、元数据、ALSA 租约和后台播放。
- [ ] Android：至少两台设备验证登录/历史、网络切换、前后台/息屏自动下一首、通知/锁屏封面、耳机拔出、蓝牙媒体键、HTTP/HTTPS/IPv6/反向代理/token 过期和多版本升级。
- [ ] FN Connect 中继：在 ARM64 真机按 UID 阻断全部公网 NAS 候选，验证 fnAudio 自身 Tpps 回环端口、FN ID 登录、历史恢复、网络切换、后台播放和退出清理。x86_64 模拟器只作为动态配置与安全回退门禁，不能替代 Go JNI 真机验收。
- [ ] App Center：在真实 fnOS 完成全新安装、端口修改、停止/启动、保留数据卸载、清除数据卸载和安装后权限检查。
- [ ] 取得 `0.1.213` 之前的 NAS 快照或可信音乐库副本后，再执行 Tag 审计逐文件恢复。没有可信来源时不得写回空 Tag 或猜测数据。
- [ ] 2026-09-18：R69 真机项：本轮用 2.0 s 打桩代表解析卡住，真实时长取决于设备 resolver 配置（Windows 默认 timeout×attempts，NAS 上还有 search 域拼接），需要在真机上确认一次最坏等待；同时确认投递侧 `fetch_lan(request, timeout=3)` 在同样场景下确实是有限等待，不会把 worker 长期占住。
- [ ] 2026-09-18：R68 真机项：本轮的相对 seek 只在桩后端上验证（`_status` 返回固定 position）。MPD 侧 `seek <id> <time>` 是绝对语义，`renderer.py` 下发的 `control_position` 也是绝对值，需要真机确认连续两次相对快进不会被后端回读的位置投影拉回原地（`snapshot()` 的 position 来自后端，存在一个自然的读改写窗口）。
- [ ] 2026-09-18：R67 真机项：只读挂载与 ENOSPC 下的封面降级只能在本机 mock（把 `_atomic_bytes` 打桩抛 OSError），真实 NAS 上 SMB/NFS 的失败形态可能是半写、EACCES 或长时间阻塞，本轮的 try/except 覆盖面需要在设备上复核一次。
- [ ] 2026-09-18：R66 新开（真机项）：子代理审计里凡是依赖真实设备行为的结论一律未采信也未复现；`Seek`/`Unit`、UTF-16 SOAP 客户端这两条需要一台真实控制器确认线上到底发什么编码与哪种 Unit，再决定兼容面宽严。
- [ ] 2026-09-18：R64 新开：真机验证 OS 媒体面板在投送期间的归属。MediaSession 的 `playbackState`/`positionState` 现在跟受控端一致（与主控件同口径，本轮判定保留），但媒体键最终会走 `setActionHandler` 的哪条分支没有证据；需要一次设备侧取证确认不会出现「面板显示投送、按键操作本机」的分裂。
- [ ] 2026-09-18：R63 新开：10 秒窗口需要一次真机取证。两条待验：其一，低端 WebView 上远端 SSE 断流后 `refreshRemoteStatus` 的 5 秒兜底是否真在跑（若被节流或请求本身超 5 秒，健康路径就会被夹住，表现为进度条每 10 秒顿一下）；其二，长时间隐藏后恢复的第一帧少报最多 10 秒是否可接受。取到 trace 之前只报结构收益，不宣称观感改善。
- [ ] 2026-09-18：R63 遗留（接 R62 那条真机项）：`shutdown_runtime` 只在 `server.main()` 的 `finally` 里执行，进程内没有 SIGTERM 处理器，飞牛以信号停应用时那段清理不会跑；这与本轮「UI 拿不到状态」是同一类问题的两侧：一边是进程停止路径没有入口，一边是状态失败没有可见性。取证一次设备侧停止路径后再决定补信号处理器还是压缩上界。
- [ ] 2026-09-18：R62 新开：关闭预算变长之后的宿主停止宽限期缺真机证据。修复后 drain 最坏 31 秒（`MAX_JOB_BUDGET_SECONDS + 1`），实测有 10.8 秒这一档；而 `shutdown_runtime` 只在 `server.main()` 的 `finally` 里执行，进程内没有 SIGTERM 处理器，也就是说飞牛以信号停应用时这段清理根本不会跑。需要先取证：设备侧停应用走的是哪条路径、给多少宽限；若确认收不到优雅退出信号，要么给 `server.py` 装一个受控停止入口（信号处理器调用 `server.shutdown()`），要么把 31 秒上限压到宿主宽限之内，别让「正确但永远执行不到」的清理冒充可靠性。
- [ ] 2026-09-18：R61 遗留：真机确认。离线只能证明「轮询会画传输行、同值不再触 DOM」（写次数断言），观感需要低端 WebView 验三条：投送时进度条是否真的走动、受控端暂停时图标是否立刻变化、以及 500 ms tick 现在对 incoming 也生效后功耗是否可感。拿到前后证据前只报结构收益。
- [ ] 2026-09-18：R61 新开：`setStyleVarIfChanged` 的同值短路依赖 `style.getPropertyValue()` 的序列化口径。若真机某 WebView 对自定义属性补空白，比较恒不相等，`--seek-fill`/`--marquee-distance` 会退回每轮写入（行为与 R61 之前一致，无正确性风险，只是白做优化）。取到设备 trace 后若确认，改为在节点上记「上次请求值」再比较，口径同 `dataset.playing` 与 `dataset.coverSource`。
- [ ] 2026-09-18：R60 遗留：闪烁是否被根治缺设备证据。离线侧只能证明「同一地址不再触 DOM」（`vm` 对拍的是写次数），观感需要在低端 WebView 上验两条：DLNA 输入会话激活 30 秒内 `#nowCover` 是否仍闪、后台取歌词的 900 ms 轮询期间 `#lyricsCover` 是否仍闪。拿到前后对比之前只报结构收益。
- [ ] 2026-09-18：R59 遗留：收益数字还缺两项真机测量。其一，一页 120 行里实际有多少行走 `metadata/artwork/` 这条通道（取决于曲库中无内嵌封面且已拿到 provider 封面的比例）；其二，低端 WebView 解码 500x500 以上原图的真实代价。没有这两项，R59 只能报「按行的最坏下载量从 8 MiB 级降到 160 像素瓦片」这种结构收益，报不出端到端毫秒。取证路径：`/api/health` 的封面计数 + 真机抓取一次首屏的 Network 面板。
- [ ] 2026-09-18：R56 之后 `parse_dac_stream_caps()` 的两条采样率正则仍可疑，缺真机样本不改。它只认紧接冒号的 `Rates:`/`Sampling Frequency:` 后面直接列数字的写法，以及 `44.1 kHz` 这种带单位的写法；仓库里既没有真机 `card*/stream*` 文本留档，测试用的两种形状都是本轮之前自己造的。如果真机打印的是 `Rates  : 0x33 (44100 48000 ...)` 一类形状，则**永远解析不出速率**，过去全靠那条被删掉的 `[192000]` 编造兜住。要做的只有取证：抓一份真机 `stream*` 原文进仓库当夹具，再决定改正则还是显式标注「驱动未提供速率」。
- [ ] 2026-09-18：R56 留下两处仍在猜的回退，等真机取证一起处理。`choose_dac_strategy()` 的 `max_rate = safe_int(caps.get("pcm_max_rate")) or (... or 192000)` 与 `max_bits = safe_int(...) or 24`（`playback/alsa_output.py:823-824`）：本轮刻意没动它们，以免在没有真机证据时改变转码决策。取证之后要么保留「未知即按源文件直通」，要么显式降级，别再让一个数字同时充当「实测值」和「保守猜测」。  **R91 部分推进（速率那一半不需要真机就能定，位深那一半仍等取证）**：条目说「取证之后要么保留未知即直通、要么显式降级」，其中速率一半本轮用一条与设备无关的证据定了：`choose_dac_strategy()` 的 rate 最终喂给 `aplay -D`（:929），而设备标识是 `hw:`（:498/:620/:652），`hw:` 不带重采样插件，所以凭猜测抬高上限的后果是设备打不开而不是自动降采样，「未知即按源文件直通」这个选项可以直接排除，无需真机数据。已改为「什么都测不到就与 unknown 同样保守（44100）」，且驱动报过的位深保留。**仍在等的还是本条剩下的那半**：当驱动报了速率却没报格式时，`max_bits = measured_bits or 24` 仍是猜测，24 位是不是该降成 16 只有真机（或至少留档的 `stream*` 原文）能定；TODO.md:1831 那份真机 `stream*` 夹具取证时一并处理。
- [ ] 2026-09-17：`cover_cache` 交互预热的「静默窗口」`INTERACTIVE_PREWARM_INITIAL_DELAY_SECONDS=0.15` 与库预热 `LIBRARY_PREWARM_DELAY_SECONDS=0.15` 是经验值，缺少在慢速 NAS 上的实测依据（真机项，本机无法验证）。
  **需要**：一台接了慢速存储（USB HDD 或 SMB/NFS 曲库）的 fnOS 真机，边播边翻首屏，抓两份时间线：交互请求（封面/分页）与预热任务的排队等待毫秒分布，用来判断 0.15 s 是过长（预热几乎跑不动）还是过短（交互被抢通道）。本机测不了的原因写清楚：这里的自变量是外部存储的抖动与机械寻道，仓库内任何夹具造出的等待分布都不代表真机，离线只能验证「窗口存在且可配」这一形状（已有测试覆盖）。
- [ ] 2026-09-20：曲库连接池在真机上的长期行为仍无证据（本条是 R121 从代码待办桶 L154 拆出的**真机半**；「开关要不要对外暴露」的产品半已拆到本段下方的决策段 D9，两条同源、各自独立判定）。空闲句柄在 Windows 上会阻止索引文件被删除或替换（已实测 `WinError 32`）；fnOS 上仍需确认缓存卷卸载、`-shm`/`-wal` 生命周期与长跑 fd 数不受影响。操作指引照抄原条：**一旦真机出现索引替换失败或卸载卡住，先回退 `library_connection_pool` 再排查，别在设备上加兜底逻辑。**（R62 更新随本条一并搬来：离线侧已抓到一次同类 `WinError 32` 的真机制且它**与池无关**，该配置下 `pool={'idle':0,'creations':0}`；病因是关闭期 `_claim_job` 在 `stop_event` 之后仍领新工作、join 预算不跟随在飞作业、`close_library_connections()` 排在 `METADATA_SERVICE.shutdown()` 之前，三处都已修并各有测试。）
  **需要**：一台可长跑的 fnOS 真机 + 一次曲库索引替换 + 一次缓存卷卸载。建议取证口径（本轮已备好消息但未执行长跑）：对主服务进程做 24 h 的 `ls /proc/<pid>/fd | wc -l` 时间序列（本轮实测 pid 237556，其 mpd 子进程 237571），采样窗口内各触发一次索引替换与一次缓存卷卸载，比较句柄数是否单调增长、`-shm`/`-wal` 在卸载后是否残留。本机测不了的原因写清楚：这里的自变量是**卸载时序与长周期 fd 走势**，离线套件既没有真卸载也没有 24 h 时钟，不能替代。
- [ ] 2026-09-21：真实设备、DAC/DSD、DLNA/AirPlay、App Center 与 Android 多机型验收继续保留为外部验收项。〔R138 X1=A 自代码桶原 L803 迁入，条目文本未改。〕
## 需要项目负责人决策

2026-09-18（R77 记录用户答复）：本段 8 条**不阻塞逐轮工作**，继续保留在决策段等待负责人逐条给方向；审查轮次不得因为这些条目未决而停下，也不得把它们挪回代码待办段。

2026-09-20（R121 记录用户答复）：负责人已对本段 8 条逐条给方向，本段收口为「关闭 6 条（D2/D3/D4/D6/D7/D8）+ 保持开启 2 条（D1 收窄、D5 证据不足）+ 新开 1 条（D9 池开关是否上设置页，由 L154 拆分而来）⇒ 待决 3 条」。已关闭条目按本仓库惯例**留在段内写明裁定、取证与后果**，不从文件删除，避免日后重开时无据可依；下面每条前缀 D1…D9 只是本轮对话里双方使用的编号，磁盘上仍以条目正文定位。本轮未改任何生产代码，因此每条的「落实」都是登记与取证，不是实现。

- [x] 2026-09-20（R121 记录用户答复；**本条保持开启并收窄**）：D1 确认许可证、维护者身份、远程 Git 托管位置和正式发布策略。  **裁定：开源，暂不托管。** 磁盘取证：`git remote -v` 输出为空 ⇒「暂不托管」已经是现状，不需要任何改动；`git ls-files` 里 `LICENSE`/`COPYING`/`NOTICE`/`AUTHORS` 四类候选 **0 条命中**，工作区根目录实测同样不存在。**本条不能关闭的理由**：方向确定 ≠ 许可证已定，`README.md:97` 现文仍是「项目许可证尚未明确，不应自行假设开源授权」，在没有选定任何一份许可证文本之前由审查轮凭空写入 `LICENSE` 并顺手改掉 README 那句话，等于把「替负责人选授权」伪装成「已完成待办」。**收窄后仍待一句话**：具体选哪份许可证（MIT / Apache-2.0 / GPL-3.0 / MPL-2.0 等其一），以及是否需要 `NOTICE`、`AUTHORS`；给到后 `LICENSE` 与 README:97 在同一轮落地并刷 `SOURCE_MANIFEST.sha256`。 〔R123 已实施：负责人给出后半句话——许可证 `GPL-3.0-or-later`，署名对象 `vinson023`，需要 `NOTICE` 与 `AUTHORS`。落盘 `LICENSE`（GPL-3.0 逐字正文，35149 字节）、`NOTICE`（2135 字节，含再分发义务与「暂不托管」现状）、`AUTHORS`（815 字节，只有 `vinson023`，不含邮箱）；`README.md:97` 由「项目许可证尚未明确，不应自行假设开源授权」改为指向三份文件并写明 2026-09-20 裁定。判别测试 `src/tests/test_license_files.py`（5 项）：逐文件 sha256 与正文段落锚点、`AUTHORS` 不得出现邮箱或域名、`git remote -v` 为空即「暂不托管」未被动过。变异 V7 删 `LICENSE` 的「Version 3, 29 June 2007」整行、V8 在 `AUTHORS` 插入带邮箱的行，均被杀灭。本条关闭后决策段只剩 L1876 与 L1880 两条。〕
- [x] 2026-09-20（R121 关闭）：D2 建立 Android 正式签名 keystore、离线备份和升级密钥策略。**裁定：接受临时密钥，据此关闭本条。** 磁盘现状（本轮不改代码，故无判别测试）：`android-client/app/build.gradle:5-8` 是四个 `FNAUDIO_RELEASE_*` 属性/环境变量入口，`:9` `hasReleaseSigning` 要求四元齐备，`:44-58` 仅在齐备时才挂 `signingConfig`，`:74-87` 的 `verifyReleaseSigning` 在缺签名时抛 `GradleException` 并挂在 `preReleaseBuild` ⇒ **签名门禁并未放松**，「接受临时密钥」的含义只是允许用自供的临时 keystore 过这道门。**必须登记的后果**：APK 的升级身份由签名证书决定，一旦日后换成正式 Release keystore，已安装的旧 APK 不能无缝覆盖升级，必须卸载重装（用户侧表现为签名不一致/安装失败），这要在换密钥**之前**告知而不是事后发现。**为什么不在本轮写 keystore 生成脚本**：把私钥材料或其生成流程落进仓库属于负责人决策与运维事项，不是审查轮可以代办的代码项。
- [x] 2026-09-20（R121 关闭；同时吸收代码待办桶原 L1817「Chromaprint 取证」条，该条已从上方删除、其全部信息保留在本条内）：D3 决定是否提供 AcoustID client key、额度和可分发的 Chromaprint 运行时。**裁定：永久关闭该功能方向——不提供 client key、不携带 Chromaprint 运行时。** 并入的 L1817 取证已在 2026-09-20 于测试机（Debian 12 bookworm / `Linux 6.18.18.c1032-trim` x86_64 / 已部署 FPK 0.2.34）重测，三条事实：① `libchromaprint.so.1` 存在于 `/usr/lib/x86_64-linux-gnu/`，但它是系统自带共享库、不是 fnAudio 携带的；② `fpcalc` 可执行文件在 PATH 与 `/usr/bin`、`/usr/local/bin` 两处查找**均不存在**，即光有库也没有可用的指纹命令行；③ 应用配置 `metadata_fingerprint_enabled=false`，代码侧 `audio_fingerprint.status()` 因此恒为 `available=False` —— 功能处于**永久关闭态**而不是「待凭据」态。AcoustID 查询还需项目专属 client key 与配额，负责人裁定不申请。**闭合效果**：代码待办桶净少 1 条（L1817 删除），设备段与台账不动。
- [x] 2026-09-20（R121 关闭）：D4 fnOS 若提供稳定的非 root 服务账号、共享目录 ACL 和 ALSA 设备组契约，再决定是否将主服务降权。**裁定：接受 root 运行，本条关闭。** 三个前提在测试机上逐条实测（2026-09-20，FPK 0.2.34）：① **成立**——fnOS 确实提供了 `fnaudio` 服务账号（`uid=996`），但它**不在 `audio` 组**；② **不成立**——共享目录 ACL 契约不存在：`/vol1/@appcenter/fnaudio` 与 `/vol1/@appconf/fnaudio` 实测 `drwx------ root root`，0700 的成因就是打包脚本 `cmd/main` 与 `cmd/install_callback` 里的 `umask 077` + `install -d -m 700`，非 root 服务账号连自己的配置与数据目录都读不到；③ **不成立**——ALSA 设备组契约不存在：`/dev/snd/*` 实测 `0660 gid=29(audio)` 而 `fnaudio` 不在该组，用 `runuser -u fnaudio` 对六个音频节点逐项 `access()` 探测**全部 False**。对照组：同机的 moode 播放器以自己的 `moode` 用户跑它的 mpd，说明「降权跑音频」在这台机器上依赖发行版自己配组，fnOS 并未把这层契约暴露给第三方应用包。当前部署形态实测为 `root python3 /vol1/@appcenter/fnaudio/server/server.py --host 0.0.0.0 --port 53199 --config /vol1/@appconf/fnaudio/config.json`（pid 237556）及其子进程 `target/bin/mpd --no-daemon`（pid 237571，同为 root）。**据此关闭的含义**：降权需要 fnOS 侧先给出组契约与目录 ACL，属外部平台前提，不是本项目能靠改代码补齐的缺口；登记「已决策接受 root」后，逐轮审查不再把它当未决风险反复提出，权限面相关的既有代码项（路径/权限边界测试等）不受本条影响。设备取证过程中**未修改设备上的任何文件、未重启任何服务**，只做过 cp/find/ls/ps/runuser 读操作。
- [x] 2026-09-18：R73 新开（本轮量出来的，比 R73 修的更值钱，但要先做产品判断）：`allow_disk=False` 不生效。`cover_cache._cache_key` 内部调 `cover_source_version(item)` 时用了默认的 `allow_disk=True`，于是声明「翻页不打磁盘」的路径对缺索引身份的媒体文件**每行仍做 2 次 `os.stat`**（实测：un-indexed 行 `allow_disk=False` 2 次、`allow_disk=True` 3 次；indexed 行 0 次）。把它改成尊重标志会换一种代价：降级版本算出的键找不到按权威版本落盘的缩略图，这些行的 `cover_thumbnail_url` 会退化成 `cover_url`。先量真实库里两类行各占多少，再决定是「少 stat 丢缩略图直链」还是「留直链继续打磁盘」，别在没数据时挑一边 需要：真机或外部材料。  **R121 用户裁定：去测试机取证；实测后本条仍保持开启（不选边）。** 实测（2026-09-20，FPK 0.2.34）：`/vol1/1000/music` 共 97 个文件 / 545 MB，但 `tracks` 表只有 **6 行**，且这 6 行**全部带完整索引身份**，`cue_tracks` 表 **0 行**。按 R73 本机实测口径，带索引身份的行两类取值都是 0 次 `os.stat` ⇒ 本条要量的「缺索引身份的媒体文件」在这台样本机上**一个都没有**，样本对它要回答的问题是零信息量。机制诊断照旧成立、无新证据可加：`cover_cache.py:205` 默认 `allow_disk=True`、`:275` `_cache_key()` 不转传该标志、页面路径 `thumbnail_asset_id_for_item(..., allow_disk=False)`、`src/tests/test_library_presentation.py:71-80` 三处断言。**结论**：6 行的曲库不能推断真实分布，本轮不改代码，等一个含无标签音频（或用户真实曲库）的样本再决策。〔R129 真机复测（2026-09-21，同机；SSH 端口 22）：`tracks` 仍 **6 行**、`cue_tracks` 仍 **0 行**、`covers` 表仍 6 行，与 R121 的实测**逐值一致**，本机样本对「缺索引身份的媒体文件占比」依旧零信息量。用户新提供的无标签样本 `C:\path\to\fnAudio\music\伍佰 - 泪桥.flac`（26,325,514 字节）足以证明**机制**（无标签行落到哪条 `os.stat` 路径），但 1 首对 1 首仍给不出本条要回答的**占比**。⇒ 维持 R121 裁定「不选边」，本条保持开启，本轮不改代码、不新立项。〕 〔R138 X4=C 裁定永久关闭并并入 L47：本条要的「真实库里缺索引身份的媒体文件占比」被证明拿不到——R121 实测 6 行全带索引身份、`cue_tracks` 0 行，R129 复测逐值一致，用户补的无标签样本（`E:/fnAudio/music/伍佰 - 泪桥.flac`，26,325,514 字节）只能证明机制、给不出占比。机制诊断（`cover_cache.py:205` 默认 `allow_disk=True`、`:275` `_cache_key()` 不转传该标志）保留在 L47 的关闭记录内，其风险前提（SMB 上的 `os.stat` 放大）已由 X5=B 判定不成立。本条自本轮起不再计入需决策桶，重开条件同 L47。〕
- [x] 2026-09-18：R71 新开（版本库完整性，修法需要用户点头，本轮不动索引）：`tools/verify_release_evidence.ps1` 与 `tools/index_release_evidence.ps1` 两个脚本**没有被 git 跟踪**（`git ls-files -- tools/verify_release_evidence.ps1` 为空，`git status` 报 `??`），而引用它们的 `src/tests/test_build_release_script.py`、`src/tests/test_offline_verification_script.py` 与 `tools/test_offline.ps1`、`RECOVERY.md:44-53` 都是已跟踪文件。后果不是风格问题：干净克隆里这两个恢复工具不存在，已跟踪的门禁测试会在读取/执行处直接失败，手册写明的恢复流程也跑不通；本轮编辑的产物尺寸守卫因此只存在于工作区。正确处置是 `git add` 这两个脚本（并确认 Linux 侧的执行位与 `index_release_evidence.ps1:51-69` 的两套路径探测是否还需要），不是把测试改成「脚本缺失就跳过」——那只会把缺失固化下来 需要：真机或外部材料。  **R121 用户裁定：批准 —— `git add` 这两个脚本，不改测试。** 已执行：两脚本随基线提交 `89ded0132278b84f6d187b9638f1dda776fdf26b`（首行消息 `chore: land the project baseline into version control (scope B)`）进库，`git ls-files -- tools/verify_release_evidence.ps1 tools/index_release_evidence.ps1` 现各返回 1 条。**更正本条原文的一处事实**：`tools/test_offline.ps1` 实测 **0 处**引用这两个脚本（`Select-String -Pattern 'verify_release_evidence|index_release_evidence'` 命中数 0），原文把它列为引用方是错的；真实引用面本轮重测为 `src/tests/test_build_release_script.py` 7 处、`src/tests/test_offline_verification_script.py` 15 处、`RECOVERY.md` 3 处（`RECOVERY.md:44-53` 的恢复流程引用仍然有效，因为脚本现已在版本库里）。执行位维持 100644 未改（Windows 工作区里仓库内 `.ps1` 一律 100644，改它买不到任何可验证收益）；`index_release_evidence.ps1:51-69` 的两套路径探测按原样保留（它服务的是「脚本可能被放在仓库外」的恢复场景，删探测等于缩小恢复面）。**闭合效果**：干净克隆现在具备完整的证据链工具，已跟踪的门禁测试与手册流程不再依赖工作区私有文件。
- [x] 2026-09-18：R71 新开（本轮环境副作用，不是产品缺陷）：`tools/blutter/` 是工作区里一份**未被 git 跟踪**、自带 `.git` 的外部检出（`git ls-files tools/blutter` 为 0 条，也没有 `.gitmodules`），它的 `objects/pack/*.idx` 是只读文件，会让 `shutil.rmtree(ignore_errors=True)` 静默留下半棵树。任何复制 `tools/` 的取证脚本都会撞上它。本轮的处置是脚本侧只复制顶层 `*.ps1` 并带 `onexc` chmod 兜底；目录归属本身（要不要移出版本树）留给一次单独决定，不动 `.gitignore`。  **R121 用户裁定：移出版本树，本条关闭。** 已执行：`C:\path\to\fnAudio\tools\blutter` → `C:\path\to\fnAudio_external\blutter`（同卷 rename；实测 3539 个文件 / 69.6 MB，自带 `.git/objects/pack/*.idx|pack|rev` 只读件完整；`Test-Path tools\blutter` 现为 False）。移前取证：`git ls-files tools/blutter` 0 条、仓库无 `.gitmodules`，`src`/`tools`/`docs` 三树的 `*.py`/`*.ps1`/`*.sh`/`*.md`/`*.psm1` 递归 grep `blutter` **没有任何脚本或测试引用它**（叙述性提及只出现在 CHANGELOG_AI.md / PROJECT_CONTEXT.md / TODO.md）。`.gitignore` 一个字未改（禁改条款仍生效，移出靠的是目录位置而非忽略规则）。副带效果：复制 `tools/` 的取证脚本不再需要 `onexc` chmod 兜底，「`shutil.rmtree(ignore_errors=True)` 静默留下半棵只读树」这个坑从工作区消失。
- [x] 2026-09-18：R70 数据面：真实用户的收藏规模分布未知（几十？几千？），本轮的 15 万行是构造出来的最坏情况。要不要把 50000 调小（或调大）应当先看一次统计：`/api/state` 的 favorites 长度分布与 delta 保存的请求尺寸，二者都已有现成的日志/指标口径可取 需要：真机或外部材料。  **R121 用户裁定：去测试机取证后按实测决策；结论是保持 50000 不变，本条关闭。** 实测（2026-09-20）：设备 `favorites` 表 **3 行**、`playlists` 1 行、`playlist_tracks` 3 行、`state_meta.revision=7` —— 这台测试机上的真实规模是「个位数」，与 R70 构造的 15 万行最坏情况差四个数量级，也够不到「几千」那一档。代码侧口径同时查清：`state_store.py:39` 的 `MAX_PERSISTED_FAVORITES = 50000` **不是预分配、也不是请求上限**，而是落盘行的淘汰上限 —— `_trim_persisted_favorites()`（:361-382，:377 `excess = count - MAX_PERSISTED_FAVORITES`，:336 是唯一 SQL 使用点）只在超出时按 `created_at ASC` 删最旧的超额行。**诚实写明关闭理由的边界**：真实用户分布仍然没拿到（一台机的 3 行不构成分布），本条关闭的理由是「无证据支持任何改动 + 保持现状零代价」，而不是「已证明 50000 合适」；若日后 favorites 真出现万级，改的是这个数字本身、不需要改机制。
- [x] 2026-09-20（R121 新开，来自代码待办桶 L154 拆分出的**产品半**；真机半见上方 P0 段末尾）：D9 曲库连接池开关 `library_connection_pool` 要不要出现在设置页上。磁盘事实（本轮实测）：默认值由 `src/app/server/config.py:22` `DEFAULT_LIBRARY_CONNECTION_POOL = True` 提供、:29 进默认表，:93-94 与 :153-154 两处读取都走 `_strict_bool` 严格布尔化（非法值回落默认，不会静默漂移）；运行期唯一生效点是 `server.py:591 commit_config_update()` 在 :606 调 `apply_library_connection_pool_config(server.config)`（`library.py:1917`），即**改配置不需要重启**，关掉会顺手排空该配置指向库的空闲句柄；诊断面已存在（`library.py:1905 library_connection_pool_status()` → `diagnostics.py:42/72`、`health_snapshot.py:36/68`）。**控件实测不存在**：`src/app/ui` 全树 `*.js`/`*.html` grep `connection_pool` 与 `connectionPool` 命中 **0 条**，用户目前只能靠改 `config.json` 关闭它。**要决策的是产品问题不是技术问题**：暴露这个开关等于承认「池在真机上可能有害、用户需要一个自救按钮」，而池的长期行为证据尚未拿到（见 P0 段同源代码条），先给按钮再拿证据会让开关显得比证据更确定；不暴露则维持「默认开、出问题走配置文件」的现状。本轮不改代码、不加控件、不新立代码项（该判断依赖的证据属设备段）。  **R124 用户裁定并实施：D9 = 上设置页，本条关闭。** 落点取设置页第 2 个 pane「运行」（`index.html` `data-settings-pane="runtime"`，与「改端口要重启」同屏，新文案明写「这个开关即时生效，不需要重启 fnAudio」）。服务端新增 `GET`/`POST` `/api/config/runtime`（`server.py` GET 在 `/api/access` 之前、POST 在 `/api/config/library` 之前）；鉴权不需新规则，`api_route_policy.py` 的 `/api/config/` 前缀已把它判成 `settings.read`/`settings.write`。**读侧值一律来自 `library.py` 的 `_library_connection_pool_enabled()` 同一个谓词**，面板不许自造第二条默认规则：键缺失时该谓词返回 False，而 `config.py` 加载器默认 True，界面报的是运行进程此刻真的 honour 的值。键名经 `library.py` 新增的 `library_connection_pool_config_key()` 唯一出口取得，`server.py` 全文仍不出现 `library_connection_pool` 字样，既有守卫 `src/tests/test_server_lifecycle.py` 的`test_the_pool_default_is_no_longer_invented_at_startup` 一字未放宽就变绿。写侧走 `commit_config_update()`，排空空闲句柄发生在原地提交之后；非布尔请求体 400 拒绝且不改动当前值；保存成功后回读服务端值而不是相信点击。判别测试 = 新增 `src/tests/test_ui_runtime_settings.js` + `test_http_integration.py` 内 6 项；仓库外副本变异矩阵 V1～V12 全灭。本条关闭**不**改池的默认值，也**不**主张「池在真机上长期安全」——那条证据仍在 P0 段的真机半（R121 从代码待办桶拆出的同源条目）里挂着。

## 完成定义

只有实现、自动测试、所需部署/设备证据和恢复文档全部同步后才能勾选。真机事项不能用 Windows 单元测试、模拟响应或静态代码检查替代。
# 当前持续优化目标（不含真实设备验收，2026-08-25）

## 2026-09-01 持续目标追加：首屏列表与元数据链路

- [x] 首屏/状态刷新列表闪烁：相同曲目 HTML 不再重复替换 `trackList`，避免旧 WebView 重新触发封面解码和滚动重置；982 项离线门禁通过。
- [x] 手动元数据补全的开关门禁：默认仍关闭后台补全，但点击“重新补全元数据”会显式开启抓取后再入队，避免关闭状态下假成功；UI/服务回归通过。
- [进行中] 首屏加载继续优化：以现有分页缓存、in-flight 合并、首批优先、无中间重绘和 100k 基准为基线，后续只接受可量化的低风险改动。
- [x] 冷启动空状态闪烁：无快照时在首个分页请求进入 loading 即隐藏静态空状态，已有列表不重绘；UI 回归已通过。
- [x] 访问模式探测让路首屏：`api/access` 延迟到首屏提交后执行，分页切换和卸载时取消旧任务；已通过 UI 回归。
- [进行中] 首屏启动继续观测：已消除用户状态水合导致的空列表二次渲染；后续只针对可证明的请求、DOM 提交或图片解码重复工作优化。
- [进行中] 首屏封面优先级：IntersectionObserver 之前先启动首屏前 8 张封面，其余继续按可见区域懒加载；后续以离线调度回归和性能证据观察。
- [进行中] 首屏封面资源竞争：非首屏封面已标记低请求优先级，继续以离线调度回归观察旧 WebView 兼容性。
- [进行中] 元数据可用性继续观测：本地歌词优先，外部保留网易云、QQ、酷狗、咪咕、JOOX、千千和 MusicBrainz 回退链；外部服务波动时通过状态/失败原因定位，不在无证据时更换数据源。
- [进行中] 元数据失败诊断继续收敛：provider 错误已采用受限投影，后续仅依据可复现样本补充协议适配，不将单次无匹配误判为数据源失效。
- [x] 元数据 provider 总等待预算：单任务以线程本地 deadline 限制外部源串行等待，歌词 12 秒、其他任务 15 秒，超时后仍按 failed/retry 链路恢复；已通过专项与完整离线门禁。
- [进行中] 元数据缓存损坏隔离：曲目候选接口对异常 JSON、置信度和时间字段安全回退，继续补充缓存恢复回归。
- [x] 元数据候选正缓存纳入规范化查询与文件名身份提示，避免部分 Tag 相同但文件名不同的曲目复用错误的本地候选；新增 MetadataService 回归。
- [x] 元数据候选缓存身份已抽为独立纯模块，集中约束查询、文件名提示和原始字段的有界投影；新增模块级回归。
- [进行中] 持续目标（无需真机）：首屏仅接受可量化的低风险加速并保持稳定 DOM；元数据链继续补强受限解析、失败可观测与本地/在线回退，不改变后台补全及 Tag 写回默认关闭状态。
- [x] Provider smoke 观测（2026-09-01）：本机测试 QQ、咪咕歌词成功，网易云/酷狗/JOOX/千千本次样本未命中；结果归档于 `artifacts/metadata-provider-smoke-20260901.json`，未据此删除数据源。
- [x] Provider 协议差异复核：对照 `references/music-lib` 记录网易云 weapi 与现有公开 GET 的协议差异，以及酷狗/QQ/咪咕/千千两段式兼容性；详见 `artifacts/metadata-provider-compatibility-20260901.md`。
- [x] 当前歌曲按需歌词不再受后台补全总开关阻断：默认关闭 `metadata_enabled` 时，用户打开歌词仍可唤醒优先歌词 worker；全库后台补全和 Tag 写回门禁保持不变，已通过完整离线回归。
- [x] 歌词优先结果同步封面：`/api/lyrics` 返回已缓存 artwork，前端仅为缺少本地封面的当前曲目更新展示；已通过元数据与 UI 离线回归。
- [x] 元数据候选按需入队：首次打开单曲候选时若无缓存记录，现在会创建受限优先任务；后台总开关关闭时仅处理该明确单曲请求，不启动整库扫描。
- [x] 首屏封面解码延后：曲目行封面使用 `loading=lazy` 与 `decoding=async`，配合现有可见区域调度器降低首屏解码阻塞；已通过 UI 回归。

- [进行中] 工作树与发布治理：保持隔离构建、源码清单和可恢复发布证据；不覆盖正式包。
- [进行中] 旧版发布证据隔离：0.2.33 主目录已补充 legacy 说明，明确 scratch provenance 不匹配；继续保持严格恢复拒绝不完整证据。
- [进行中] `artifacts/0.2.33` 仅具备 FPK/SHA256 旧证据，需在下一次正式重建时补齐源码清单与 provenance；当前不得宣称可完整恢复。
- [进行中] 服务端资源上限与可观测性：继续以脱敏、低开销方式补充查询/扫描瓶颈证据。
- [x] 可观测性计数增量边界：拒绝任意对象转换并限制单次增量，已通过离线回归。
- [x] 请求 ID 输入边界：仅接受字符串请求头，避免异常对象字符串化；已通过离线回归。
- [x] 脱敏日志键/事件边界：非文本值使用占位符，避免诊断路径触发任意字符串转换；已通过离线回归。
- [x] 可观测性累计计数上限：长期运行计数封顶，避免指标数值无界增长；已通过离线回归。
- [x] 并发资源门禁输入边界：限制上限/超时并拒绝异常对象转换，已通过离线回归。
- [x] 资源配置数值边界：bounded_int 拒绝异常对象转换并安全处理非法配置容器；已通过离线回归。
- [x] 磁盘保留空间输入边界：非法路径/字节值保守拒绝，避免资源检查异常；已通过离线回归。
- [进行中] 大音乐库性能：继续优化收藏、歌单与分页的引用曲目补水，先以排序语义和回归为前提。
- [进行中] 大音乐库性能观测：分页冷/热缓存基准已固化；首屏常规路径未见重复 COUNT(*)，后续优先分析尾页 OFFSET、跨视图缓存命中和引用补水的可量化瓶颈。
- [x] `random100` 显式刷新绕过服务端短期页缓存，确保刷新重新抽样而不是复用旧随机页；新增 SQLite 回归。
- [x] 100k 首屏保护回归基准：首屏/中页/尾页分页、缓存、分组和搜索均保持有界；证据已归档至 `artifacts/large-library-benchmark-20260902-empty-response-guard.json`。
- [x] 100k 曲库缓存/搜索追加复测：分页冷/热、分组/目录、引用补水和 FTS/LIKE 对照已记录；尾页 OFFSET 仍是后续优化候选，未在无证据情况下改写查询结构。
- [x] 100k 曲库离线基准：分页、分组、目录和 FTS/LIKE 搜索结果已生成并归档，最新证据为
  `artifacts/large-library-benchmark-20260901.json`（FTS 相对 LIKE 约 15.2x）；后续性能改动可用该 JSON 做回归对照，不替代真实设备验收。
- [x] 首屏/歌词修复后的 100k 复测：分页查询总耗时 0.291s、峰值 Python 分配 611KiB，FTS trigram 相对 LIKE 约 16.6x；证据为 `artifacts/large-library-benchmark-20260901-followup.json`。
- [x] 前端曲目筛选边界：来源选择、搜索过滤和排序接线抽至 `ui/library_track_filter_policy.js`，保留 `app.js` 状态与补水生命周期并通过 Node 回归。
- [x] 曲库根目录标签边界：路径名称提取与同名消歧抽至 `ui/library_root_label_policy.js`，异常输入安全回退并通过 Node 回归。
- [x] 扫描文件分类边界：CUE/支持音频/忽略扩展名抽至 `server/library_scan_file_policy.py`，扫描与签名路径复用并通过 Python 回归。
- [x] 扫描签名兼容修正：文件签名保留 CUE 变化检测，普通扫描仍避免重复解析 CUE，专项回归通过。
- [x] 文件签名资源预算：限制增量签名片段数和总文本大小，避免超大音乐目录造成无界内存累积。
- [x] 文件签名版本保留：在预算耗尽时仍保留 `metadata_version` 尾字段，确保 schema 变化不会被资源上限吞掉。
- [x] 文件签名哈希边界复用：`library_signature()` 复用共享 `digest_signature_parts()`，避免签名算法和预算规则分叉。
- [x] 发布资产加载契约：版本回归锁定新增 UI 策略模块存在且位于 `app.js` 之前。
- [x] 前端相同曲库 URL 的并发请求合并：in-flight Promise 去重避免快速重绘重复请求，刷新语义保持显式绕过；已通过离线回归。
- [x] 前端 in-flight 请求资源上限：去重映射最多保留 32 个进行中请求，避免异常页面切换造成无界增长；已通过离线回归。
- [x] HTTP 观测路径长度边界：请求路径限制 8192 字符，避免超长 URL 放大策略开销；已通过离线回归。
- [x] 诊断键长度上限：脱敏日志键限制 256 字符且不绕过敏感字段识别；已通过离线回归。
- [x] CUE 时间字段上限：限制各数字分量长度，避免极端文本放大解析开销；已通过离线回归。
- [进行中] 核心模块边界：扫描控制、元数据展示、常规扫描记录组装及 provider 路由已抽至独立纯模块；后续继续拆分扫描/元数据读取，但不碰真实播放链路。
- [x] 曲目候选字段安全投影：文本、来源、封面 URL、发行日期和数字 provider ID 统一经过有界纯策略；已通过完整离线门禁。
- [进行中] 元数据补全判定边界：`needs_track_enrichment` 已抽为独立纯策略，后续继续拆分 provider 结果投影与任务状态转换。
- [x] CUE 曲目记录构造边界：片段时长与记录字段组装已抽至纯模块并通过离线回归。
- [x] 扫描数值策略边界：safe_float/safe_int 抽至纯模块并拒绝异常对象转换；已通过离线回归。
- [x] Tag 文本输入边界：clean_tag 限制长度并拒绝异常对象字符串化；已通过离线回归。
- [x] 探测标签完整性兼容：曲目号采用独立安全数值校验，恢复数值型 ffprobe 标签的快速路径；已通过离线回归。
- [x] 探测键与 CUE 时间输入边界：拒绝异常对象字符串化，已通过离线回归。
- [x] ffprobe 载荷边界：限制容器/标签/流结构并复用安全数值策略，已通过离线回归。
- [x] ffprobe 流数量上限：最多处理 16 个流，避免异常 JSON 放大扫描开销；已通过离线回归。
- [x] ffprobe 标签数量上限：每个容器最多读取 128 个受限键，避免异常元数据放大内存；已通过离线回归。
- [x] 统一 Tag 规范化上限：normalize_probe_tags 自身限制标签数量/键长，覆盖所有调用方；已通过离线回归。
- [x] Tag 载荷类型边界：非字典输入安全回退，避免元数据公共入口异常；已通过离线回归。
- [x] 曲库查询参数映射容错：first_param 隔离损坏映射的 getter 异常，分页/分组/文件夹请求安全回退；已通过离线回归。
- [x] 查询缓存迭代器容错：LibraryQueryCache 对 iter/next 异常安全回退并保持键值数量上限；已通过离线回归。
- [x] 查询缓存结果复制容错：深拷贝失败时跳过或失效缓存并记录 uncacheable，避免缓存层阻断请求；已通过离线回归。
- [x] 查询缓存权重容错：异常映射访问/长度读取安全回退最小权重，缓存计量不阻断查询；已通过离线回归。
- [x] 并发门禁长期计数上限：acquired/waited/rejected/timed_out 等诊断计数封顶，避免长运行无界增长；已通过离线回归。
- [x] 结构化日志异常隔离：脱敏/序列化阶段的损坏映射安全降级并计数，不阻断业务请求；已通过离线回归。
- [x] 脱敏映射直接容错：redact 对损坏字典访问安全返回占位摘要；已通过离线回归。
- [x] 脱敏序列直接容错：redact 对损坏列表/元组迭代安全返回占位摘要；已通过离线回归。
- [x] 封面缓存曲目输入容错：cached_cover_for_item 隔离非字典/非文本路径输入，封面请求安全回退；已通过离线回归。
- [x] 分页合并总数容错：前端分页合并隔离 Symbol/异常 valueOf 总数输入；已通过离线回归。
- [x] 分页计划数值容错：剩余页偏移计算隔离 Symbol/异常 valueOf 输入，避免分页流程中断；已通过离线回归。
- [x] 分页页大小边界：将页大小限制为 1–500 整数，避免无效偏移和请求放大；已通过离线回归。
- [x] 封面缓存字段边界：隔离曲目字典字段异常并限制路径键长度，避免封面请求被损坏输入阻断；已通过离线回归。
- [x] 封面缓存 LRU：命中移动热点条目并按最久未使用淘汰，减少移动端重复封面解析；已通过离线回归。
- [x] 内存曲库遍历上限：筛选排序最多处理 200,000 条并隔离损坏迭代器，避免内存回退路径资源放大；已通过离线回归。
- [x] 内存曲库字段容错：过滤/搜索/排序统一隔离损坏字典字段访问，避免缓存条目异常阻断渲染；已通过离线回归。
- [x] 内存曲库根目录容错：文件夹根匹配限制根目录遍历并隔离异常，避免损坏配置阻断视图；已通过离线回归。
- [x] 发布版本回归覆盖 README 与 Android README 当前基线，防止文档版本漂移。
- [x] 健康摘要依赖映射容错：MPD、元数据状态缓存和转码状态先进行已知字段投影，损坏 `.get()` 不阻断 `/api/health`；已通过离线回归。
- [x] 健康子摘要映射容错：library/transcode/DLNA 摘要对异常字典 getter 安全回退，避免健康接口被嵌套依赖状态阻断；已通过离线回归。
- [x] 诊断快照映射容错：播放、MPD 和元数据嵌套状态对异常字典 getter 安全回退，避免支持快照被损坏依赖阻断；已通过离线回归。
- [x] 曲库错误摘要序列容错：扫描错误列表长度读取隔离异常序列协议，避免健康/诊断摘要被损坏状态阻断；已通过离线回归。
- [x] 核心边界拆分：诊断播放状态投影抽至 `diagnostics_playback.py` 并配套独立回归，保持支持快照字段和脱敏语义不变。
- [x] 核心边界拆分：可观测性计数/延迟快照抽至 `observability_snapshot.py` 并配套独立回归，保持固定路由和有界指标语义不变。
- [x] 大音乐库引用补水上限：收藏/歌单曲目 ID 统一经 `item_hydration_policy.js` 限制为 2048 项并按 100 条分批，避免前端补水请求无界增长；已通过离线回归。
- [x] 大音乐库补水请求预算：引用曲目批次额外限制 8192 字符，避免超长 ID 造成 URL 编码和请求行峰值；已通过离线回归。
- [x] 发布证据离线核验：新增只读 verifier 核对 FPK、SHA256SUMS、源码清单和 provenance；历史包会明确标注证据完整性，避免会话恢复时误判；已通过离线回归。
- [x] 大音乐库补水编码预算：批次预算按 URL 编码后长度计算，避免多字节 ID 绕过 8192 字符请求上限；已通过离线回归。
- [x] 核心边界拆分：诊断元数据压力摘要抽至 `diagnostics_metadata.py` 并配套独立回归，保持支持快照字段和边界语义不变。
- [x] 曲库查询缓存可观测性：增加稳定 `hit_rate` 指标，支持离线判断大曲库页面缓存收益；已通过离线回归。
- [x] 健康摘要暴露曲库缓存命中率：安全投影 `hit_rate` 并限制在 0–1，异常输入安全忽略；已通过离线回归。
- [x] 曲库缓存适配输入边界：避免 wrapper 层字符串化 namespace 和无界物化 values，统一交由缓存策略限界；已通过离线回归。
- [x] 前端分页数值文本边界：分页计划/合并拒绝超过 64 字符的数字文本，避免异常输入放大前端计算；已通过离线回归。
- [x] TODO 清单唯一性门禁：离线测试自动拒绝重复 checklist 条目，避免持续目标重复推进；已通过离线回归。
- [x] 核心边界拆分：探测标签完整性与 fallback 合并策略抽至 `metadata_probe_policy.py`，保持探测值优先；已通过离线回归。
- [x] 前端封面状态接线：保存最近一次调度返回值，统一暴露队列、并发和丢弃压力；已通过离线回归。
- [x] 元数据 fallback 映射容错：隔离损坏字典转换异常，避免扫描请求被异常标签映射阻断；已通过离线回归。
- [x] 核心边界拆分：Vorbis 注释解析抽至 `vorbis_comment_policy.py` 并限制标签匹配数量，降低异常文件扫描开销；已通过离线回归。
- [x] 发布证据严格模式：verifier 支持 `-RequireCompleteEvidence`，严格恢复时拒绝缺少 provenance 的旧包；已通过离线回归。
- [x] 封面调度队列资源上限：限制待处理封面队列为 4096 项并暴露丢弃计数，避免大曲库可见性事件造成无界增长；已通过离线回归。
- [x] 封面调度状态契约：`hydrate()` 与 `snapshot()` 统一返回 `dropped`，便于前端即时读取压力状态；已通过离线回归。
- [x] 封面限流重试：被队列上限拒绝的可见项继续保留观察，后续可见事件可重试；已通过离线回归。
- [x] 可观测性日志轮转阈值边界：统一限制 `max_bytes` 为有限的 1–100 MiB，避免异常配置导致频繁轮转或超大日志文件；已通过离线回归。
- [x] 移动端分页可见性边界拆分：将滚动到底部才显示翻页控件的策略抽至 `ui/library_pager_visibility.js`，保留 DOM 调用方兼容层并新增 Node 回归；已通过离线回归。
- [x] 大曲库分组渲染去重：空状态判断复用当前已计算的分组列表，避免每次渲染重复执行 `groupedTracks()`；已通过离线回归。
- [x] 发布证据路径边界：校验器拒绝将普通文件误当作证据目录，恢复核验时给出明确错误；已通过离线回归。
- [x] 批请求池并发参数容错：隔离 Symbol/异常对象和非有限值，统一将并发度限制为 1–32，避免大曲库批处理初始化失败；已通过离线回归。
- [x] 分页展示边界拆分：将分页 HTML 生成抽至 `ui/library_pager_presentation.js`，`app.js` 仅保留状态接线并新增 Node 回归；已通过离线回归。
- [x] 封面调度并发参数容错：隔离异常对象/`Symbol` 配置并将并发度限制为 1–32，避免封面预热初始化失败；已通过离线回归。
- [x] 持久化分页大小边界：读取本地分页设置时限制为 1–500 的整数，避免旧配置导致大曲库单次请求/渲染放大；已通过离线回归。
- [x] 分页展示输入容错：分页展示模块隔离 `Symbol`/异常对象数值转换，避免异常状态阻断列表重绘；已通过离线回归。
- [x] 分页展示规模上限：总数限制为 100,000,000、页数限制为 1,000,000，避免异常状态生成超大 DOM 标记；已通过离线回归。
- [x] 内存曲库物化边界：内存回退查询在进入筛选前即限制为 200,000 项，避免先无界构造完整列表再限界；已通过离线回归。
- [x] 音乐库根路径输入边界：规范化与合并最多接受 64 个根路径，避免异常配置造成无界列表物化；已通过离线回归。
- [x] 根路径截断正确性：路径上限按有效唯一路径计数，空项/重复项不会遮蔽后续有效根目录；已通过离线回归。
- [x] 根路径文本输入容错：路径规范化/合并拒绝对任意对象执行 `str()`，异常配置项安全跳过；已通过离线回归。
- [x] 根路径配置写入边界：`apply_library_paths()` 也限制 64 个文本路径并过滤异常项，避免写入阶段无界物化；已通过离线回归。
- [x] 根路径配置类型容错：`normalize_library_paths()` 对非字典配置安全回退默认目录，避免损坏配置阻断设置/扫描；已通过离线回归。
- [x] 根路径写入配置类型容错：`apply_library_paths()` 对非字典目标安全短路，避免异常状态在设置保存时抛错；已通过离线回归。
- [x] 根路径文本长度边界：单个音乐库路径限制为 4096 字符，超长项安全跳过，避免路径规范化和索引键资源放大；已通过离线回归。
- [x] 根路径回退边界：无有效列表项时的 `library_path` 回退同样经过长度和类型校验，避免绕过路径限制；已通过离线回归。
- [x] 曲目缓存容量参数容错：隔离 `Symbol`/异常对象并将缓存容量限制为 1000–50000，避免异常配置破坏大曲库缓存；已通过离线回归。
- [x] 通用 LRU 容量整数边界：缓存条目数与权重统一取有限整数并拒绝布尔配置，避免小数/异常容量产生隐性超额驻留；已通过离线回归。
- [x] 播放队列定位扫描边界：队列定位最多扫描 50,000 项，页大小限制为 1–500 整数，避免异常队列放大前端计算；已通过离线回归。
- [x] 发布资源版本门禁：版本回归显式校验分页可见性/展示模块带构建缓存键并被 `index.html` 加载，避免发布漏脚本；已通过离线回归。
- [x] 目录级封面读取上限：sidecar `cover/folder` 图片在 stat 检查之外增加有界读取，隔离替换竞态导致的超大内存分配；已通过离线回归。
- [x] 静态资源服务边界：UI 资源限制为 16 MiB 并采用 128 KiB 分块输出，避免整文件驻留内存；超限请求明确返回 413，已通过 HTTP/离线回归。
- [x] 核心边界拆分：静态资源大小策略抽至 `static_asset_policy.py`，服务端仅保留 HTTP 接线并配套纯模块回归；已通过离线回归。
- [x] FFmpeg 封面输出竞态边界：M4A/WAV 提取在 stat 检查后增加有界读取和二次长度校验，避免替换/增长文件造成资源放大；已通过离线回归。
- [x] 核心边界拆分：Vorbis 注释文件读取抽至 `vorbis_reader.py`，保留 `library.py` 兼容入口并配套独立回归；已通过离线回归。
- [x] 发布证据单记录约束：恢复校验严格拒绝多条 SHA256SUMS 记录及带空白/路径的伪造 FPK 名称；已通过离线回归。
- [x] 发布清单唯一性校验：恢复校验拒绝重复 `SOURCE_MANIFEST.sha256` 记录，避免证据清单被重复项污染；已通过离线回归。
- [x] 大音乐库分组渲染去重：分组、专辑和艺术家入口复用当前重绘已计算的分组结果，避免重复全量遍历；已通过离线回归。
- [x] 大音乐库文件夹渲染去重：文件夹列表复用当前重绘的目录/曲目窗口，避免再次筛选和排序；已通过离线回归。
- [x] 核心边界拆分：M4A/WAV FFmpeg 封面提取抽至 `ffmpeg_cover.py`，统一资源上限与临时文件生命周期，保留 `library.py` 兼容入口；已通过离线回归。
- [x] MP4 封面超大 atom 回退隔离：发现超限 `covr` 数据后禁止旧兼容扫描路径返回前缀图像，避免绕过封面资源上限；已通过离线回归。
- [x] 发布清单路径唯一性：恢复校验拒绝同一源码路径对应多个哈希记录，避免证据来源歧义；已通过离线回归。
- [x] 清单路径跨平台唯一性：恢复校验按大小写不敏感方式识别重复源码路径，避免 Windows 工作树大小写差异造成证据歧义；已通过离线回归。
- [x] 可观测性超长日志键边界：超过 256 字符的键不执行无界 `lower()`，保留有限前缀并保守脱敏为 `[REDACTED]`；已通过离线回归。
- [x] 核心边界拆分：外部元数据发布日期规范化抽至 `metadata_release_date.py`，仅接受有限数值或受限文本，避免异常对象字符串化；已通过专项回归。
- [x] 发布证据内部一致性：恢复 verifier 校验 provenance schema、暂存文件数和 UI asset build 版本绑定，避免哈希正确但证据互相矛盾的目录被误判；已通过专项及 legacy 证据回归。
- [x] 大音乐库全量分页尾部收敛：全量曲目收集按 200,000 项结果预算裁剪计划，并在结果完成/空页时取消未启动批次，避免后台继续无效分页；已通过 Node 回归。
- [x] 内存回退 DSD 单遍筛选：DSD 条件并入有界过滤/排序遍历，避免 SQLite 缺失时额外物化完整 DSD 列表；已通过专项回归。
- [x] 兼容浏览响应物化上限：未分页分组/文件夹兼容接口统一最多投影 5,000 行并隔离异常游标/行映射，避免旧客户端请求放大内存；已通过专项回归。
- [x] 元数据提供方候选载荷边界：外部搜索响应统一仅处理至多 64 条映射候选，覆盖网易、QQ、酷狗、咪咕、JOOX、千千、MusicBrainz 与 AcoustID，避免异常载荷放大 metadata worker 的遍历；已通过离线回归。
- [x] 发布证据行为核验：以真实临时 FPK、校验和、源码清单与 provenance 目录执行严格恢复校验，并验证篡改暂存文件计数会被拒绝；校验器在缺少 `Get-FileHash` 的嵌入式 PowerShell 中改用流式 SHA-256 回退；已通过离线回归。
- [x] 播放队列补水总量边界：持久化队列恢复最多处理 50,000 个曲目 ID，仍按 SQLite 变量上限分批且保留顺序，避免损坏状态引发无界批量查询或结果驻留；已通过离线回归。
- [x] 前端补水取消竞态：收藏/歌单/队列切换时以 generation 隔离旧补水池，旧批次不得清理或写入新一轮 `hydratingIds`/缓存状态；已通过 Node 回归。
- [x] DLNA NextURI 队列边界：Renderer 预置 URI FIFO 最多保留 64 条，限制 URI/metadata 单项大小并暴露队列上限与丢弃计数；空 URI 清队列与 FIFO 下一首语义保持兼容；已通过离线回归。
- [x] DLNA 控制 worker 合并：播放/暂停/停止/seek 使用单 worker 和最新动作槽，避免高频 UPnP 控制创建大量等待线程；状态暴露 worker/pending/coalesced 压力字段；已通过离线回归。
- [x] DLNA 事件载荷边界：GENA 通知限制 URI、metadata 和最终 XML 字节数，异常状态值不再触发任意对象字符串化；在订阅/待发送队列上限之外补齐单任务内存边界；已通过离线回归。
- [x] DLNA 事件转义膨胀边界：按 XML 双重转义最坏膨胀收紧 URI/metadata 源文本上限，并验证引号密集载荷仍生成非空且不超 512 KiB 的通知体；已通过离线回归。
- [x] DLNA 后端调度边界拆分：Renderer 的 latest-wins worker 合并策略抽至纯模块，覆盖 worker 启动判定、非法状态回退与计数封顶，保留 Renderer 锁/线程接线；已通过离线回归。
- [x] DLNA Renderer 输入展示边界拆分：URI、DIDL metadata 和展示字段限制为有界普通文本，DIDL 解析/URI fallback 抽至纯模块并拒绝任意对象字符串化；已通过离线回归。
- [x] 专辑元数据 LRU：专辑列表/详情的补全元数据缓存限制为 4096 项，热点读取刷新热度，避免长期浏览大音乐库导致前端对象无界增长；已通过 Node 及完整离线回归。
- [x] 专辑元数据字段边界：缓存入口限制歌手/发行日期/来源及在线封面 URL 文本长度，避免异常单条响应放大前端内存；已通过 Node 及完整离线回归。
- [x] 播放目标响应边界拆分：本机/USB DAC/DLNA 目标组装抽至 `playback_targets_presentation.py`，限制最多 256 项并移除每个 DAC 行重复的完整 MPD/upmpdcli 诊断载荷；已通过 Python 及完整离线回归。
- [x] 专辑元数据缓存一致性：曲库响应缓存失效时同步清理派生专辑元数据 LRU，避免扫描/刷新后的旧展示字段残留；已通过 Node 及完整离线回归。
- [x] JSON 响应序列化边界：`Handler.send_json()` 统一限制 8 MiB 并隔离循环引用/超限载荷，避免异常诊断或大响应拖垮 HTTP 线程；已通过 Python 及完整离线回归。
- [x] 响应头边界拆分：可选 HTTP 头限制为 16 项、名称 128 字符和值 2048 字符，拒绝换行和任意对象转换；已通过 Python 及完整离线回归。
- [x] XML 响应序列化边界：`Handler.send_xml()` 限制 1 MiB 并拒绝任意对象字符串化，异常/超限载荷降级为固定错误体；已通过 Python 及完整离线回归。
- [x] JSON 紧凑响应：服务端 JSON 采用紧凑分隔符，降低大曲库分页与诊断响应传输体积；已通过 Python 及完整离线回归。
- [x] 分页投影关键字段兼容：顶层响应继续限制读取 32 个字段，同时定向保留延后出现的 `items`/分页字段，避免字段顺序变化导致空曲库；已通过专项及完整离线回归。
- [x] HTTP 请求观测边界拆分：路径脱敏、状态指标分类、耗时归一化和日志判定抽至纯模块；已投影路由直接写入延迟指标，减少热路径重复解析；已通过专项及完整离线回归。
- [x] 内存曲库分页边界拆分：随机采样、过滤排序和分页响应组装抽至 `library_memory_page.py`，保留有界回退语义并配套独立回归；已通过专项及完整离线回归。
- [x] HTTP worker 并发门禁：`ThreadingHTTPServer` 在创建线程前执行有界准入，超限返回 503 并暴露健康/诊断计数；`http_max_workers` 配置限制为 4–128，已通过专项及完整离线回归。
- [x] HTTP 服务装配边界拆分：将有界 HTTP server 类移至 `http_server.py`，保持入口行为不变并配套独立回归；已通过完整离线门禁。
# 2026-09-01 飞牛 APP 私有播放会话（研究结论）

- [x] 在 root Android 设备上实测官方“音乐”从飞牛 APP 内播放时的宿主会话。
- [x] 确认官方实际链路为内置 Flutter `trim_music` package →
  `com.ryanheise.audio_service.handler.methods` → `AudioService` / MediaSession / 前台通知。
- [x] 排除把 `native_app`、FPK 全页 URL 或网页 Media Session 当作该私有能力触发条件的假设。
〔R138 X2=B 桶归属：自下一行起至本文件末条（盘上 L2165）的 13 条 `- [ ]` 单列为第五桶「长期观察」（此前称台账桶），它们是只登记观察口径、无当轮可执行关闭动作的条目，**不计入终止分母**。四桶口径自此固定为 代码 / 设备·外部 / 需决策 / 长期观察；重算规则沿用 R113 写在纸面上的那一条：设备段与决策段按节标题取，段外只登记项归第五桶，其余归代码桶。〕
- [ ] 若要实现飞牛 APP 内原生同等能力：取得飞牛 APP 官方 Web/FPK 播放桥接，或取得可在宿主内
  编译/注册 fnAudio Flutter playback package 的正式扩展点。没有其中之一时，此项不能由 FPK 单独完成。
## 2026-09-01 持续目标（无需真机）

- [x] 修复 JOOX 歌词首候选 lyric_id 失效时不回退后续高置信候选的问题；候选尝试受全局请求预算及最多 4 项上限约束。
- [x] 将队列/收藏/歌单引用曲目补水移至首屏权威列表提交后的空闲阶段，并在新请求或视图切换时取消过期任务，降低大队列启动时列表加载与封面闪烁。
- [x] 大曲库基准覆盖元数据页叠加：记录歌词/候选缓存回投成本，校验分页上限、重复一致性与 Tag 优先级。
- [x] 修复可见封面优先队列的逆序补图：高优先级仍优先，但同批图片按 DOM/列表顺序加载。
- [ ] 持续推进首屏歌曲页冷启动、分页缓存、稳定行提交与封面调度的离线性能回归；本轮补强恢复会话后的当前曲目元数据预取与待处理状态兼容。
- [x] 稳定首屏工具栏刷新：播放状态 render 仅更新实际变化的排序/设备/循环随机/标题/计数/导航 DOM，避免旧 WebView 无效重排与列表后闪烁；已覆盖 Node 回归。
- [x] 单根目录自动进入：单音乐库根目录不再递归命中自身的公共去重 Promise，目录歌曲分页可继续完成；已增加 Node 回归。
- [x] 元数据匹配独立回投：仅有 `auto/confirmed` 候选缓存、尚无歌词/封面缓存的歌曲也会立即展示补全字段；保持单次有界 SQLite JOIN 与真实 Tag 优先级。
- [x] 首屏歌词载荷收敛：公共歌曲分页不再携带逐首完整歌词、原始 `item_json` 或内部 artwork ID；歌词仍由当前歌曲按需接口提供，已覆盖投影回归。
- [x] 元数据页字段边界拆分：候选缓存安全投影抽至纯模块，限制字段、NUL 和长度，隔离损坏候选对首屏列表的影响；已覆盖独立回归。
- [x] 扫描状态装饰写入去重：计数、端口和进度文案仅在变化时更新，降低状态轮询引发的旧 WebView 重排；已覆盖 UI 回归。
- [x] 首屏稳定渲染续优化：稳定歌曲页不再因播放/收藏状态重复遍历选择行、重建播放列表导航或重绑列表内控件；仅实际列表提交时执行，已覆盖 Node 回归。
- [x] 稳定行提交真实变更判定：可比较行无替换时不再被当作列表改动，不重启封面/布局后续工作；已覆盖 Node 回归。
- [x] 收藏状态局部刷新：普通歌曲页的收藏变更只更新计数与当前歌曲控制，收藏视图才重绘行；已覆盖 Node 回归。
- [x] 按需元数据开关回归：后台全库补全关闭时，当前歌曲的优先歌词与候选封面任务仍可执行，普通任务保持隔离；已覆盖 Python 回归。
- [x] provider 失败可观测性：设置页和支持诊断均投影有界的失败次数、冷却时间与脱敏错误摘要，已覆盖 Python/Node 回归。
- [x] 大曲库行构建去重：同一页歌曲共享一次列配置计算，不再逐行重复解析列作用域与偏好；已覆盖 Node 回归。
- [x] 大曲库单行多列格式化去重：同一歌曲的非标题可见列一次求值并复用，避免按列重复构建格式化上下文；已覆盖 Node 回归。
- [x] 稳定歌曲页标记复用：非队列页的普通状态刷新复用同一页已生成的行 HTML，不再重复拼接整页；队列播放标识和异步封面补全均保留正确失效路径，已覆盖 Node 回归。
- [x] provider 冷却失败恢复：冷却跳过会标记当前元数据任务为未完整搜索，避免短暂上游故障被长期负缓存为无匹配；已覆盖 Python 回归。
- [x] 元数据请求预算失败恢复：provider 总预算耗尽或 deadline 异常同样保留可重试失败，不会伪装成无匹配；已覆盖 Python 回归。
- [x] provider 可用性模块边界：冷却与请求预算判定抽至纯策略模块，异常单调时间值安全 fail-closed；已覆盖独立 Python 回归。
- [x] provider 连续失败计数恢复：有效空结果同样清除旧失败累计，恢复后的源不会因一次偶发故障立即再次冷却；已覆盖 Python 回归。
- [ ] 持续推进元数据 provider 可观测性、编码兼容与失败恢复；不把第三方网络可用性当作离线门禁条件。当前歌曲预取的网络异常已具备最多 12 次有界重试，仍需真实网络波动观察。（R76 之后这条有了强制手段：`src/tests/test_zz_socket_guard.py` 把非回环拨号变成失败；此前它只是约定，实际有测试在拨七个真实服务。）
- [x] 元数据服务故障协议：track 候选接口在 worker 未启动/已退出时返回结构化 503；前端区分 unavailable 与 no_match，避免把服务故障负缓存为无匹配（已通过离线回归）。
- [x] 元数据读取权限收敛：候选与状态 GET 使用 `library.read`，写入类操作保持 `settings.write`，并增加路由策略回归。
- [ ] 持续推进服务端资源上限、发布恢复证据和核心模块可测试边界拆分。

### 2026-09-06 元数据恢复补充

- [x] 修复损坏旧元数据终态缓存：`failed/no_match` 缺失有效时间戳时，用户可见单曲查询不再永久停留在负缓存，可重新进入既有有界恢复队列；已通过离线回归。
- [ ] 持续推进首屏列表与封面闪烁的离线指标收敛；真实 WebView 图片解码差异仍需要外部验收，不能以离线门禁替代。
- [ ] 持续观测第三方 metadata provider 的真实网络稳定性、编码与限流恢复；离线策略只保障故障可恢复和不阻塞界面。

### 2026-09-06 首屏渲染收敛

- [x] 快照页与权威页的无视觉差异行不再因原始 JSON 表示差异重建：按渲染文本、格式化列、规范化封面地址和 DSD 样式生成有界行签名，保留已解码封面节点；已通过独立 Node 回归与完整离线门禁。
- [ ] 继续以真实 WebView 观察首屏图片解码、GPU 绘制和网络缓存造成的残余闪烁；离线回归只能证明无效 DOM 替换已收敛。
- [x] 可见页缩略图预热延后一个 150ms、可取消的首屏静默窗口，避免其与分页 JSON、DOM 提交和首批 eager 封面抢占 NAS I/O/FFmpeg；单 worker、24 项窗口和有界队列保持不变，已通过离线回归。

### 2026-09-03 用户反馈续推进

- [x] 列表刷新缓存竞态：新旧请求乱序完成时仅当前 epoch 可写入分页缓存，避免旧响应复活并触发二次列表闪烁；已通过 Node/UI 回归。
- [x] 当前歌曲元数据故障恢复：worker unavailable、HTTP 5xx、网络瞬断和 `status: pending` 均进入有界重试，切歌后旧结果自动失效；已通过 UI 回归。
- [x] 当前歌曲终态恢复：播放期间收到短暂 `failed/no_match` 时，有限重试显式请求服务端恢复，不再重复读取同一负缓存；已通过 UI 静态回归。
- [x] 空快照首屏保护：拒绝旧/损坏的空分页快照，避免冷启动先渲染空壳造成列表闪烁；已通过 UI 静态回归。
- [x] 首屏快照解析上限：在 JSON 解析前拒绝超过 384 KiB 的旧缓存，避免异常 localStorage 造成冷启动卡顿；已通过 UI 静态回归。
- [x] 首屏状态轮询去重：扫描轮询与常规状态刷新共享 in-flight 请求，减少慢连接下的重复响应和列表重载；已通过 UI 静态回归。
- [x] 分页请求并发硬门禁：in-flight 达到上限时不再启动未登记请求，避免实际并发超过观测上限；已通过 Node 回归。
- [x] Refresh 请求并发硬门禁：显式刷新与普通分页共享 active 计数，慢连接下不再叠加超限 refresh；已通过 Node 回归。
- [x] 元数据 lane 可用性隔离：优先歌词 worker 与普通抓取池分别判断，避免部分 worker 降级时把歌词接口误报为 unavailable；已通过 HTTP 回归。
- [ ] 首屏加载与封面闪烁继续以离线基准观察；可见元数据回投已在批次内复用页面 ID/位置索引，并将非当前歌曲元数据预取延后至首屏 750ms 静默窗口后再进入空闲调度，不把离线结果替代 WebView/真实设备验收。
- [ ] 元数据 provider 的真实网络可用性继续单独观测；协议、权限和 worker 恢复链已具备离线回归。
- [x] 可见元数据预取默认预算一致性：策略未显式传参时也使用 12 次有界重试，并隔离损坏字段访问；已通过 Node/UI 回归。
- [x] 可见预取损坏行隔离：异常 ID getter 或超长 ID 不会中断同页候选扫描；已通过 Node/UI 回归。

### 本轮持续目标推进（2026-09-03）

- [x] 元数据缓存过期时间安全读取：reconcile、实体、当前歌曲优先队列和专辑封面刷新统一使用有界时间投影；损坏缓存按过期处理并可重新入队，已待完整离线门禁确认。
- [x] 元数据任务重试计数容错：异常任务记录中的 `attempts` 不再阻断有限重试和失败记录。
- [x] 元数据状态聚合容错：状态页计数和任务类型字段统一安全投影，损坏历史值不会让诊断接口整体失败。
- [x] 扫描状态首屏防闪烁：首个权威分页未返回且没有可见快照时，状态轮询不会提前结束加载态。
- [x] 首屏封面请求优先级：首批 8 张封面使用受限 `fetchpriority`，并发与懒加载边界保持不变。
- [x] 播放即触发单曲元数据预取：播放本机、远程或当前设备时立即请求当前曲目候选，绕过 WebView 旧缓存并由服务端有界排队；不阻塞播放，pending 状态最多追加 8 次有界轮询，结果仅在曲目仍为当前项时增量回投。
- [ ] 首屏列表/封面闪烁仍保持持续观察，不能以离线测试替代 WebView 真机验收。

### 本轮持续目标推进（2026-09-02）

- [x] 元数据候选逐条容错：混合损坏/有效的 provider 搜索结果不再因单条 schema 漂移而整体失败或触发错误冷却；已通过 Python 回归。
- [ ] 首屏列表与封面继续以离线基准验证，暂不宣称已彻底消除所有设备侧闪烁。
- [ ] 元数据 provider 仍需持续观察编码、超时、失败恢复与真实网络波动；本轮 smoke 仅作诊断证据，不作为离线门禁。
- [x] 元数据查询词边界：搜索时忽略未知歌手/艺术家占位值并限制查询长度，避免文件名解析出的占位字段降低命中率；已通过独立 Python 回归。
- [x] 100k 曲库最新性能复测：分页、元数据回投、重复页缓存和 FTS 搜索均保持有界；证据为 `artifacts/large-library-benchmark-20260902-latest.json`。
- [x] 100k 曲库性能复测续跑：热页缓存约 67.2 倍、FTS 相对 LIKE 约 17.8 倍，分页与元数据回投仍有界；证据为 `artifacts/large-library-benchmark-20260902-followup.json`。
- [x] provider 艺术家字段容错：限制列表遍历和文本长度，异常字段安全跳过；已通过元数据回归。
# 2026-09-04 持续目标追加

- [x] 外部数据源全部暂时不可用时，使用受限文件名候选保留“歌手 - 歌名”身份，避免元数据显示为空；不覆盖现有 Tag，不触发自动写回。
- [ ] 继续量化首屏 DOM 提交次数、封面请求数和元数据回投延迟；离线结果不替代真实 WebView 验收。
- [x] provider 诊断内部容量：成功/失败/冷却状态最多保留 32 个名称，淘汰旧记录并清理冷却；离线回归通过。
- [x] 元数据轮询队列公平性：活动中的 track/lyrics job 轮询仅提升优先级，不重置状态、退避和 FIFO 时间戳；离线回归通过。
# 2026-09-05 本轮持续目标进展
- [已完成（离线可验证）] 冷启动恢复队列的当前歌曲元数据会在首屏权威页提交后立即重新挂接优先 lane。
- [进行中] 真实 WebView 的首屏图片解码闪烁仍需设备验收；本轮只收敛 DOM/请求时序，不宣称已消除全部硬件差异。
- [进行中] provider 可用性与 schema 漂移继续通过离线策略、worker 恢复和响应投影回归覆盖；真实数据源稳定性仍不作全量保证。

## 2026-09-06 持续目标增量

- [x] 部分 Tag 元数据即时回退：标题已存在但歌手/专辑缺失时，前台候选可安全使用文件名“歌手 - 歌名”身份；保持低置信度，不自动写回源文件，并通过 MetadataProviders 回归。
- [x] 首屏封面分页 I/O 收敛：冷列表响应只复用进程内已知缩略图状态，未知封面不阻塞 JSON 序列化；后台预热和独立封面接口保持完整磁盘校验。
- [x] 首屏封面版本探测非阻塞化：未带扫描版本的曲目不在列表序列化阶段逐行 `stat()`，使用安全回退版本并由封面端点完成权威校验。
- [x] 当前歌曲歌词本地缓存版本复用：provider/歌词优先路径在有索引文件版本时跳过重复 `stat()`，并通过离线回归验证。
- [x] provider 数值 schema 容错：JOOX 与网易云关键整数字段异常时安全降级，后备源继续运行；通过 MetadataProviders 回归。
- [x] 播放启动歌词任务版本闭环：当前歌曲优先任务 payload 保留扫描文件版本，worker 可避免重复 stat；100k 离线基准复测通过。
- [x] 封面预热入队 I/O 收敛：交互和扫描预热去重阶段不再同步探测未索引文件，后台 worker 承担真实缓存检查；新增 cover cache 回归。
- [x] 元数据候选评分输入边界：异常本地 Tag 字段不会中断 provider 候选映射或后备源；通过 MetadataProviders 回归。
- [进行中] 首屏列表/封面闪烁与 provider 真实网络稳定性继续以离线指标和外部验收分别观察。
- [x] 元数据空响应恢复：服务已启动但单次 `track_match` 返回空值时，接口保留本地 Tag/文件名投影并返回可重试 pending，避免前端误判为元数据永久不可用；HTTP 回归通过。
- [x] 元数据空投影恢复：`track_match` 返回空对象或缺少状态/候选/封面等投影字段时，同样回投本地信息并保持 retryable pending；HTTP 回归通过。
- [x] 元数据瞬态异常恢复：单次 SQLite/worker 异常不再返回 opaque HTTP 500，接口保留本地投影并交给有界重试链恢复；HTTP 回归通过。
- [x] 冷启动缩略图预热窗口：服务启动只为首个 96 首可见窗口排队预热，整库预热仍在扫描完成后异步进行，避免大索引遍历阻塞首个列表请求；启动回归通过。
- [x] 元数据恢复文件名兜底：worker 尚未可用且 Tag 为空时，pending 响应投影受限“歌手 - 歌名/文件名”身份，仅用于展示并保持可重试；策略回归通过。
- [x] 元数据本地数值边界：pending 投影拒绝 NaN/Infinity 等损坏数值，避免污染歌曲身份和 provider 查询；策略回归通过。
- [x] 2026-09-06：显式单曲/歌词重试解除 provider 冷却短路；后台限流与失败退避保持不变，离线门禁通过。
- [x] 2026-09-06：首屏歌曲页已提交而用户状态延迟返回时，只有影响当前列表的列配置、收藏、歌单或队列变化才触发完整渲染；普通控制状态改为局部刷新，避免列表/封面二次闪烁。完整离线门禁 1128 项通过。
- [进行中] 首屏歌曲列表性能与按需元数据可靠性：持续自动任务已启用；继续以离线夹具验证分页提交次数、封面 hydration 与 `pending/retryable` 元数据恢复，真实 WebView 绘制和第三方 provider 长期网络命中率独立验收。

## 2026-09-06 首屏元数据与响应兼容

- [x] 可见歌曲元数据启动时序：保持首屏让行但将 750ms 静默窗口收敛至 220ms，现代 WebView 的空闲回调兜底收敛至 450ms；当前歌曲仍走独立立即优先 lane，已通过 Node/UI 回归。
- [x] 宿主 metadata envelope 兼容：仅对无有效投影的响应支持 `data/result/payload/metadata` 有界解包；四层上限、异常 getter 与数组回退均有离线回归，避免成功结果被误判为空。
- [进行中] 持续自动任务：继续处理无需真实设备的发布治理、资源上限、100k 曲库查询/渲染、首屏提交与元数据恢复；真实设备/输出协议/外部 provider 稳定性保持独立验收。

## 2026-09-08 歌词优先 lane 重试闭环

- [x] 歌词优先 lane 的定时重试若再次网络失败，会继续沿用同一可取消 scheduler 和 12 次上限，不再被空 catch 静默终止；切歌仍可取消尚未发出的下一次请求，已通过专项 Node/UI 回归。
- [x] 可见列表元数据回投：异步完成但已离开当前页的歌曲不再参与可见行 patch 资格判定，避免页外结果把当前页的局部更新降级成整页重绘并造成首屏闪烁；已通过专项 Node/UI 回归。
- [x] 页外元数据批次收敛：当一个回投批次的歌曲都已离开当前页时，直接 no-op，不再执行当前页 `render()` 或快照写入；已通过专项 Node/UI 回归。
- [x] 100k 标题分页索引：消除默认标题排序中重复的标题键，并增加 `(title COLLATE NOCASE, id)` 升/降序稳定索引；保持 ID tie-break 和 offset 协议。查询计划不再使用临时 B-tree，96 首首/中/尾页约 5.9/10.9/11.7ms，证据为 `artifacts/large-library-benchmark-20260908-title-index.json`。

## 2026-09-06 首屏与元数据持续目标

- [x] 首屏快照复用可观测性：新增有界 `snapshotMarkupReuses` 与 `listMarkupNoops` 指标；浏览器夹具会校验指标可安全读取，便于区分真正的 DOM 提交、快照复用与 no-op 提交。
- [x] 按需元数据恢复边界：后台全库补全默认关闭不再影响当前歌曲、歌词页和显式单曲查询；worker 恢复、空响应、宿主 envelope 和短时 provider 冷却均保留本地投影 + 有界 retryable 路径。
- [进行中] 自动任务保持激活：继续在无需真实设备的范围内量化首屏提交/封面 hydration/元数据延迟，收敛大曲库查询与渲染；真实 WebView 绘制和第三方 provider 的长期网络可用性不以离线结果宣称完成。
- [x] 发布 FPK 资源上限：构建与证据校验在复制、解包或 SHA-256 前拒绝超过 10 GiB 的稀疏/实体包，避免超大产物进入发布流程；新增离线回归。

## 2026-09-08 首屏指标补强

- [x] 封面请求量化：封面调度器通过隔离事件回调记录实际请求、成功、失败和重试次数；Node/UI 回归覆盖一次失败重试与最终成功，真实 WebView 图片解码差异仍需外部验收。
- [x] 首个 metadata 延迟量化：记录首个可见 metadata 请求完成耗时，并与请求次数、最近/最大/累计耗时一起纳入 UI 安全投影和浏览器夹具。
- [x] 元数据入口 ID 边界统一：曲目查询、歌词、播放优先级和候选确认共用有界 ID 策略，异常桥接载荷不会在 SQLite/字符串化阶段抛错；已通过 MetadataService 回归。
- [x] provider 响应解析边界拆分：gzip/JSONP/编码/Base64 歌词解析抽为无状态有界模块，保留 MetadataService 兼容入口并通过独立回归。
- [x] provider 基础字段投影边界拆分：文本与数值 schema 投影抽为无状态模块，保留兼容入口并通过独立回归。
- [x] 2026-09-17：`playback/alsa_output.py:merge_dac_caps()` 是无调用方的死代码，且会把 `empty_dac_caps()` 的默认 192000/24bit 与实测能力做 `max()`，一旦被接线就会用猜测值抬高真实上限；待决定接线方式或直接删除（本轮只读不改）。  **R91 关闭（点名的函数已经不在了，但它担心的事活在另一处，并且这轮不需要真机就修掉了）**：先核对现状：`merge_dac_caps` 在代码里**零引用**（`git grep -l` 只命中 CHANGELOG_AI.md 与 TODO.md 两份文档 ✓），`empty_dac_caps()`（`playback/alsa_output.py:295`）也已改成「未知一律记 0，不记像样的默认值」（:78 那条测试钉着 ✓），所以条目描述的函数与那个 192000/24 的**默认表**都没了。但同一个猜测活在下游：`choose_dac_strategy()` 原来写 `max_rate = safe_int(...) or (max(rates) if rates else 192000)`、`max_bits = safe_int(...) or 24`，只在 `source == "unknown"` 时才保守。实测（`%TEMP%\r91measure.py`）四种 caps 形状对四种源文件的策略：源文件报得出速率的设备给 48000，而**「stream 文件读得到、但一条速率都没解析出来」的设备被判成 192 kHz 器件**——176.4 kHz 的文件直通 176400、384 kHz 的文件给 192000，与全空 caps 的 44100 相差 3 倍。这一形状不是构造出来的：归档项 TODO.md:1831 记着很多驱动打印的是 `Rates  : 0x33 (44100 48000 ...)`，现有两条正则都匹配不到，于是速率恒空；本轮另造一份同样形状的 stream 文件走真解析器复核，`pcm_rates=[]`、`pcm_max_rate=0`、`source` 指向真实路径，结果同上。为什么不必等真机：这个 rate 最终喂给 `aplay -D`（:929），而设备标识是 `hw:CARD=x,DEV=y`（:498/:620/:652）——**`hw:` 不带重采样插件**，多报的天花板不是「保守回退」，是打不开的设备，所以「未知即按源文件直通」这个选项可以直接排除。改法（:810-830）：先只取实测值得到上限，取不到就按与 unknown 完全相同的保守答复（44100），但**驱动真报过的位深要留下**（`Formats: S16_LE S24_LE` 通常读得得到 ✓ 解析在 :354 ✓），否则会把唯一的实测事实也丢掉；没有实测位深时保守取 16。测试：既有 `test_driver_text_without_rates_stays_unmeasured` 原本断言的正是 192000（注释把它称作「仍然保守的上限」），本轮按上面的证据把它改成 44100 并写明理由；新增 `test_an_unmeasured_device_gets_the_same_answer_as_an_unknown_one`，四种源文件逐一比对「没测到」与「unknown」的答复必须相同，同时钉住「报得出速率的设备不许被压到 44100」（176.4k 源 + [44100,48000] 必须仍是 48000），以及「只报格式不报速率」时是 (44100, 24) 而不是 (44100, 16)。变异 8 例（控制组 117 条先绿）：N1（整段保守分支不走）、N2（逐字恢复改前代码）、N3b（把保守误用于「有速率无位深」）、N4（位深仍猜 24）、N6（覆盖掉实测位深）全部由新测试杀死；N3（拿已被默认过的变量做判断）是 no-op、N5（改用速率表判定，因为 :347 处 `pcm_max_rate` 只会等于 `max(rates)`，解析器产生不出「有上限无速率表」）按设计存活；反过来 N7 我本来标成等价，结果被杀——它让默认值 24 冒充实测宽度，说明那两个断言确实各自守着一条承诺。附带排掉一个误判：条目说的「接线方式待定」不成立，没有任何调用方等着它。




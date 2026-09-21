# fnAudio R136 修改审查对照（未跟踪文件，不入库）

提交：`0b15be3` docs: register the R136 control_point deep-read round（父提交 `0ab3ced`＝R135）。
本轮性质：零源改动、文档-only。改动面恰为 CHANGELOG_AI.md +2 行（L2、L3）、PROJECT_CONTEXT.md +1 行（L2）；0 删除；TODO.md 未动（0-close 轮先例）；SOURCE_MANIFEST.sha256 未刷且轮前后逐字一致（707 条 / 76,638 B / sha 22b81b17…df3f）；设备段 TODO L818..L1876 逐字未动。

## Hunk 1/2：CHANGELOG_AI.md @@ -1,4 +1,6 @@（在 L1 标题后插入 L2、L3 两条 R136 记录）

@@ -1,4 +1,6 @@
+- 2026-09-21 — R136 深读登记轮（净关闭 0 条、新立 0 条、零源改动）：接管后先复算磁盘而非引用旧正文 —— HEAD `0ab3ced`（R135）、分支 `main`、无 remote、暂存空、被跟踪 0 modified、未跟踪 703 条均不入库 ✓ `.git` 下 MERGE_HEAD/CHERRY_PICK_HEAD/REVERT_HEAD/BISECT_LOG/rebase-merge/rebase-apply/sequencer 全部不存在 ✓ `TODO.md` 内容行 2,221／尾 4 LF／0 CR，开放 68 按四桶复扫＝**代码 10（L47/48/98/112/114/121/128/149/159/803，L803 桶归属争议暂计代码）＋ 设备/外部 44（段 L818..L1876 逐字未动，且被跟踪区干净即与 HEAD 逐字节一致）＋ 需决策 1（L1887）＋ 台账 13 ＝ 68**，数学通过 ✓ 防幻影核验：TODO 的 L2 仍是 R133 记录（R134/R135 为 0-close 轮未动 TODO，本轮按先例同样不动），CHANGELOG L2/L3＝R135、CONTEXT L2＝R135 均真实在盘 ✓ 本轮清掉 `src/app/server/dlna/control_point.py`（699 行）深读债：前段会话读完 L1–108、L159–260、L324–699，本轮补读 L100–165 与 L255–330 后全文件 100% 覆盖 —— `find_service` 以 serviceType 子串匹配并用 `urljoin(description_url, ...)` 拼控制地址，控制面恒在描述文件同源；`soap_request` 仅留文本类型检查、网络单点收口 `fetch_lan`，信封只由内部字面量拼接，seek 参数经 `seconds_to_upnp_time` 有界格式化，外部文本无 XML 流入通道；`upnp_control` 动作六选一枚举封闭、未知动作直接 False、异常全捕获返回结构化错误；`device_protocol_info` 失败时刻意不带 `supports_dsd` 键（三值语义：沉默≠拒绝），mime 集合与固定五类表求交 —— 全文件自洽有界，**无盘上可自证缺陷**，欠读面集合按 699 行缩小一面 ✓ 十条代码待办逐条复核仍无一可在本轮真实关闭且不硬凑：L47/L48/L112/L114/L121/L128/L159 各被负责人自设的真机/样本取证门挡住（测试机全 ext4、tracks 6、cue=0、metadata_enabled=false，该机答不了）；L803 桶归属须负责人裁定不得自移；L98/L149 的「剩余欠读面全部读完」在本轮后仍欠 `dlna/service.py`（1,220）、`cover_cache.py`（1,364）、`playback/core.py`（506）、`app.css`（1,528）、`index.html`（184）、`app.js`（8,362）、4 个 Android java（2,436）。R132/R134/R135/R136 连续四轮 0-close 与「每轮净关闭 ≥ 1」铁律正面冲突：本轮不用浅关闭掩盖，点名交回负责人——三问（是否授权多轮纯深读债／是否豁免 ≥1／L803 与 L1887 裁定）持续未回。
+- 2026-09-21 — R136 收口／终跑／清单（一笔文档-only 提交）：本轮零源改动，故不刷 `SOURCE_MANIFEST.sha256`——轮末复算仍为 707 条／76,638 B／CRLF／sha `22b81b17b050673889bdf036f9b115e9154c6b3642651fa349d11deefcb8df3f`，与轮前逐字一致 ✓ 两份根文档仅 L2 插行、最新在前（CHANGELOG 两条 R136、CONTEXT 一条；TODO 按 0-close 先例不动）✓ %TEMP% 校验器实跑通过：三文档尾 LF 4/9/8、0 CR、四桶 68＝10+44+1+13、各文档轮号序列非增且 R136 唯一、工作树无 .new/.orig/.rej（扫描排除 `_external`，未碰 `libc@v1.67.6/surface.new`）✓ 本轮零源改动且门禁数值应与 round208 相同，按先例直接产出终跑 `artifacts/offline-20260921-round209.log`（R136 起号 round209，本轮未另跑 prefix 复现跑），退出码 0、`Ran 2483 tests`／`OK (skipped=2)`／0 条 `FAILED`／JS 侧含 `passed` 的结果行 73，与轮前基线逐项一致 ✓ 终跑 log mtime 晚于本轮全部文档编辑 ✓ 未碰设备段、未 push、逐文件 pathspec `git add` ✓ 本会话 %TEMP% r136_* 于收口时全部删除。

## Hunk 2/2：PROJECT_CONTEXT.md @@ -1,4 +1,5 @@（在 L1 标题后插入 L2 一条 R136 教训）

@@ -1,4 +1,5 @@
+- 2026-09-21： **欠读债文件只有「补齐到全量覆盖」才能折成无缺陷证明；读到『差不多』恰是欠读账本上最危险的状态**（R136 实据：`control_point.py` 699 行此前已读约 85%，若凭『读过的部分全部自洽』登记读完，结论会建立在两段从未看过的代码上；补读 L109–158 与 L261–323 才发现恰恰是最容易误判的三个点全在未读段——`find_service` 的控制地址来自外部设备描述文件且只做子串匹配（需确认 urljoin 把控制面锁在描述文件同源）、`soap_request` 的信封拼接（需确认外部文本无 XML 流入通道）、`device_protocol_info` 失败路径不携带 `supports_dsd` 键（需确认这是刻意的三值沉默而非漏写）。差最后 15% 就读完，等于对这几个最关键判定既不能肯定也不能否定）。代价不对称：浅读换来的『该面无缺陷』会污染 L98/L149 的关闭依据。可迁移做法：凡承载欠读债的文件，登记粒度用『读完哪个行区间』而非『读了几段』，中间缺任何一段都按未读计；当欠读概率持续偏向『防御已经做完』时，这类条目的关闭方式应是向负责人提议『读毕登记即关』，而不是无限期推迟。另记：连续 0-close 第四轮（R132/R134/R135/R136），深读债在稳定缩小、可盘上自证关闭项为零，结构性张力维持原样点名，不代答。

## 逐条审核要点

1. CHANGELOG L2（R136 登记轮正文）——核对项：接管复算与磁盘一致（HEAD 当时为 0ab3ced、四桶 68=10+44+1+13、防幻影 TODO L2=R133 属预期）；control_point.py 本轮补读 L109–158、L261–323，全文件 699 行覆盖完毕；四个判定点（find_service 同源拼接 / soap_request 无外部 XML 流入 / upnp_control 封闭枚举 / device_protocol_info 三值沉默）均无盘上可自证缺陷；十条代码待办逐一不放行的理由如实列出；连续第 4 轮 0-close 的张力点名。
2. CHANGELOG L3（R136 收口/终跑/清单）——核对项：本轮未跑 prefix 复现跑（与 R134/R135 不同点，已在文中如实声明）；round209 终跑四值 exit0/Ran 2483/OK(skipped=2)/0 FAILED/JS passed 73 与基线一致；终跑 mtime 晚于全部编辑；校验器全项通过（含『轮序非增』按 L2 顶部连续块口径，TODO 远古历史块 L107 附近存在与本轮无关的既有乱序，未粉饰）。
3. CONTEXT L2（R136 教训）——欠读债文件必须补齐到 100% 才能折成『无缺陷证明』：最易误判的 3 个安全判定点恰落在未读的约 15% 内；登记粒度应改为行区间；L98/L149 的『读毕登记即关』属于应回负责人裁定的关闭方式变更，执行方不自行改口径。

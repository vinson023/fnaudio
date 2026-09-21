# fnAudio R148 修改审查对照（逐 hunk · 行号为编辑后盘上真实 1-based）

本轮为负责人新一代裁定 c1–c8 的落地轮，实际含**两处**真缺陷：① 逐轮记账口径从未成文（c1–c8 只活在对话里，任何一轮都能悄悄改掉分母）② `tools/update_source_manifest.ps1` 用 `Sort-Object` 的**当前语序**排发布清单行，使同一棵树的清单不可跨 shell 复现。**净关闭 0 条代码待办、新立 0 条**（口径文档轮，按 Q2=A／X3=A+C 与 `docs/REVIEW_ROUND_DISCIPLINE.md` 第二节如实登记 0-close，收益记在 c1–c8 落点与「清单跨 shell 可复现」）。

## 文件净增（`git diff --numstat`，HEAD = `dea989c` R147）

| # | 文件 | 净增 | 入库分组 | 性质 |
| --- | --- | --- | --- | --- |
| 1 | docs/REVIEW_ROUND_DISCIPLINE.md | 新增（4,809 B／72 LF／无 BOM） | ② | c1–c8 口径唯一成文处，六节＋使用规则 |
| 2 | docs/INDEX.md | +1 −0（4,411→4,693 B／57→58 LF） | ② | 新 L21 唯一登记行 |
| 3 | src/tests/test_device_todos_migrated.py | +101 −0（13,996→19,773 B／273→374 LF） | ③ | 6→9 枚用例，钉口径文档与第五桶计数 |
| 4 | tools/update_source_manifest.ps1 | +16 −4（2,893 B／67 LF） | ① | 手写码点序替代语序排序，并留缺陷成因注释 |
| 5 | src/tests/test_source_manifest.py | +42 −0（7,541→10,034 B／154→195 LF） | ① | 6→7 枚用例，新增行序守卫 |
| 6 | SOURCE_MANIFEST.sha256 | +12 −12（76,954 B／710 条不变） | ① | 序点序重排；sha16 `49067e6e912649c4`→`da100750aff8a573` |
| 7 | TODO.md | +1 −0（650,903 B／2,169 LF） | ③ | 新 L2 R148 记录（一轮一条，走增补） |
| 8 | CHANGELOG_AI.md | +3 −0（1,257,723 B／6,766 LF） | ③ | L2／L3／L4 三条 R148（同一轮分记三件，与 R147/R146 同形态） |
| 9 | PROJECT_CONTEXT.md | +2 −0（805,062 B／6,187 LF） | ③ | L2／L3 两条跨轮经验 |
| 10 | `fnAudio-R147-修改审查对照.md`、本文件 | 新增，**不入库** | — | Q5=B「每轮一份」，R147 为补欠账 |

未改：`.gitignore`、`.gitattributes`、`TODO.md` 设备段——TODO 对 HEAD 只有 1 行插入、0 行改动，即设备段逐字未动的直接证据。

## 一、开工取证（磁盘实测，不采信交接快照）

分支 `main`、HEAD `dea989c`、无 MERGE/CHERRY-PICK/REVERT/BISECT/rebase/sequencer 态；`git status --porcelain -uno` 7 项 `M`（上表 1–9 中的 3 项根文档＋清单＋守卫×2＋脚本＋INDEX）；untracked 关键项 `docs/REVIEW_ROUND_DISCIPLINE.md`、`_external/`、`artifacts/*`、`music/`、`%SystemDrive%/`；仓根对照文档最新只到 `fnAudio-R146`（⇒ R147 欠一份）；门禁日志最大号 `offline-20260921-round225.log` ⇒ 本轮终跑编号 226；解释器 `python` 3.14.7（须前置 `_external` 路径）、`node` v24.19.0、两个 PowerShell 5.1.26100.9444 与 7.6.5。

## 二、缺陷一：c1–c8 口径成文

### H1 `docs/REVIEW_ROUND_DISCIPLINE.md`（新建，七段）

| 落点 | 节 | 内容 |
| --- | --- | --- |
| L1 | 标题 | 「逐轮审查与修复的记账口径」——本文件是口径的唯一成文处 |
| 一 | 桶口径（X2=B，经新一代 C3 复核） | 「长期观察」固定为第五桶且**不计入终止分母**，附实测锚点 `observation-open-count = 13` 与重算规则；同时声明本文件不写行号——每记一轮就有一批条目 prepend 到 `TODO.md` 顶部，任何写死的行号在第一次被使用时就已失效 |
| 二 | 0-close 记账口径（Q2=A、X3=A+C，C8 正式化） | 设备段轮与文档段轮如实登记净关闭 0 条并写明收益去向；既不为凑关闭数新立代码待办，也不把非代码收益谎报成代码关闭；「本轮新立不得超过关闭数」对这类轮次读作 0 ≤ 0 |
| 三 | 真机取证分档白名单（D5/D8、C5） | 第一档＝只读取证＋放置无标签样本曲＋播放＋抓服务端日志，禁止重启服务／改服务端配置／部署新构建／停止运行中的服务，凡涉及停止服务先向负责人请示；第二档（安装第三方控制点等改变设备软件栈）不在白名单内，需逐条另行批准；设备登录凭据一律不写入仓库任何文件 |
| 四 | 终局收口形式（D1、C7） | 本仓库无 remote、开源但暂不托管；终局轮只跑一次完整 `tools/test_offline.ps1`、做逐文件哈希抽查、出结题报告，不 push、不打 tag、不改 `.gitignore` 与 `.gitattributes` |
| 五 | 深读轮前置取证（C4） | 代码桶现存两条深读债动手前一律先读现状：已落实者按证伪关闭并转成回归守卫；符号计数轮必须能复算出历史登记值，复算不出即停下如实报告，禁止改写历史数字 |
| 六 | 落点登记 | c1–c8 逐条对应到本文件哪一节＋哪个守卫 |

### H2 `docs/INDEX.md` L21（+1）

新登记行指向该文件，措辞含「第五桶不计入终止分母、0-close 轮的记法、真机取证分档白名单、终局收口形式与 c1～c8 裁定落点」，并点明由 `src/tests/test_device_todos_migrated.py` 读取。缺了它，新文档对任何按索引找文档的后续轮不可见。

### H3 `src/tests/test_device_todos_migrated.py`（+101，两个 hunk）

| 组 | 新行号 | 内容 | 缺了会怎样 |
| --- | --- | --- | --- |
| 常量 | 50-66 | `OBSERVATION_DECLARATION = "R138 X2=B 桶归属"`（按内容锚点定位，不写行号）、`BUCKET_NAMES`（代码／设备·外部／需决策／长期观察）、`OBSERVATION_COUNT_ANCHOR = observation-open-count = (\d+)`、`CREDENTIAL_SHAPE` 形状正则 | 桶声明与锚点失去可寻址性 |
| 辅助 | 288-307 | `_observation_declaration()` 断言 `TODO.md` 全文该声明**恰一处**；`_stated_observation_count()` 从口径文档取声明值 | 复制一份声明即可绕过 |
| 用例① | 309-327 | `test_the_observation_bucket_is_declared_once_and_measured`：声明须点名四个桶且含「不计入终止分母」；其后未勾条目实测值与锚点 13 双向核对 | 两侧单独改动即判红——抬桶计数或挪条目都会被抓 |
| 用例② | 329-352 | `test_the_round_discipline_doc_carries_the_rulings`：逐节核对裁定用词（不计入终止分母、净关闭 0 条、先向负责人请示、不打 tag、复算不出即停下、凭据不入仓库）确实以各自措辞活在磁盘上；并以 `CREDENTIAL_SHAPE` 反查文档自身不得出现口令形状 | 口径只剩表格行、或口径文档自己泄凭据 |
| 用例③ | 354-371 | `test_the_discipline_doc_is_indexed_and_pins_no_moving_line_number`：须在 `docs/INDEX.md` 登记，且全文不得出现 `TODO.md:<n>` 这类会漂移的行号引用 | 文档失联或行号腐化 |

**守卫自我纠正（本轮第一次）**：首版用 `assertNotIn` 钉住真机口令**字面量**，`git grep` 实测全仓唯一命中正是该断言自己那一行——守卫本身就是它所禁止的事。因文件尚未提交可在提交前修，改为口令**形状**正则后：该字面量全仓命中 1→0，185 个 tracked Markdown 上零误报（前一候选正则对 `FNAUDIO_RELEASE_ASSIGN=…` 类赋值有 4 处误报故弃用）。

## 三、缺陷二：清单行序不可跨 shell 复现

### 取证（全部在仓库外副本 `r148_clone` 上重跑，不引用快照）

旧脚本对**同一棵 HEAD 树**：PS 5.1 输出 sha256 前缀 `31d1242e5a3f37de`、pwsh 7 输出 `d5d8f34a2cb4a25f`——两者均 76,954 B／710 条、路径集合完全相同、node 逐行比对 **117 个行位不同**。根因＝`Sort-Object` 用当前语序比较字符串，中文语序与 Invariant 语序对「.」「_」的落位判定不同。

代价落在 CI（非推断，已核盘）：`.github/workflows/verify.yml` 第 36–40 行步骤 `Verify source manifest is current`，`shell: pwsh`，正文正是 `.\tools\update_source_manifest.ps1` ＋ `git diff --exit-code -- SOURCE_MANIFEST.sha256` ⇒ 内容逐字节正确的清单换 shell 刷新即判红，本地任意一次刷新也能量子化地改写 117 行而无人察觉。

### H4 `tools/update_source_manifest.ps1`（+16 −4，四个 hunk）

| 新行号 | 内容 |
| --- | --- |
| 38-47 | 六行解释性注释：记明「按手写序排而非 `Sort-Object`」、R148 双 shell 实测两个哈希、117 行位漂移、CI 的 `git diff --exit-code` 后果、序点序与 git 路径序一致 |
| 50-51 | `$paths`／`$lines` 改为并行数组累加器（`[string[]]::new(0)`） |
| 52-53 | 循环内 `$paths += $relative`、`$lines += "$hash  $relative"` |
| 55 | `[Array]::Sort($paths, $lines, [StringComparer]::Ordinal)` —— 以路径序同步置换哈希行 |

验证：改后同一副本 PS 5.1 与 pwsh 7 输出逐字节相同（`66dfaa99be91b68c`）；`+=` 与 `[Array]::Sort` 三重载在两个 shell 均绑定成功（此前担心的退化风险不成立）；副本清单跑完已还原（`git status --porcelain -- SOURCE_MANIFEST.sha256` 为空）。

### H5 `src/tests/test_source_manifest.py`（+42，新 L50-91）

新增第 7 枚 `test_the_manifest_rows_are_written_in_ordinal_path_order`，双向钉：① 逐行须匹配 `^[0-9A-F]{64}  [^ ]`，路径列必须等于其 `sorted()` 码点序；② 工具脚本**代码体**不得再现 `Sort-Object`，且必须声明 `[StringComparer]::Ordinal`。

**守卫自我纠正（本轮第二次）**：② 首版作用于全文，被脚本自己那段解释缺陷的注释判红——即注释里「不使用 Sort-Object」这句话本身含 `Sort-Object`。收窄为剔除 `#` 起始行后的代码体，并加回 `assertIn` 构成双向钉，使「换比较器」与「改回语序排序」两类回退各自单独点亮。

### 真仓重刷与逐文件抽查

新脚本 PS 5.1→pwsh 两次输出相同（`FF97C5009D081319…`）；守卫文件再编辑后重刷收敛为 `da100750aff8a573`（76,954 B／LF 710／CR 710／尾 1 LF）。与刷前按「路径→哈希」映射比对：仅 **1 条**差异（`src/tests/test_source_manifest.py` 自身，即本轮所改），**411 个行位重排而内容集合不变**；710 条全量重算 **0 缺失、0 哈希不符**；14 项逐文件抽查全 MATCH（`tools/update_source_manifest.ps1` 不在 scope 内，属预期）。注意 `git diff --numstat` 只报 12/12——那是 LCS 效应，**不得**当作重排量引用。

### 先红与变异矩阵

- 先红（存档 `%TEMP%\r148_order_red.txt`）：新守卫在**刷前的旧顺序盘**上判红，首差在第 1 行（`android-client/app/build.gradle` 对 `android-client/README.md`），末行 `FAILED (failures=1)`。
- 仓库外变异矩阵 `CELLS 8 / MISMATCHES 0 / MATRIX OK`（驱动 `%TEMP%\r148_matrix2.js`，跑完三文件 sha16 与开跑前逐字节一致）：`CONTROL` 绿；**M1 交换相邻两行→只有顺序守卫红、集合守卫保持绿**（该断言的判别力正来自此处，证明序点序不是集合比对的冗余）；M2 在副本里真的重跑 HEAD 旧脚本（内容对、顺序错）→红；M3 换回旧脚本文本→红；M4 比较器换成 `InvariantCulture`→红；M5 删一行→由内容守卫捕获；**M6 正控（仅注释提到 `Sort-Object`）保持绿**；`FINAL-CONTROL` 绿。

## 四、控制组、门禁与污染复查

- 控制组两套时点均绿：矩阵跑完后与门禁跑完后各一次，`test_change_record`(3)＋`test_source_manifest`(7)＋`test_device_todos_migrated`(9) = **`Ran 19 tests / OK`**。
- 终跑 `artifacts/offline-20260922-round226.log`：433,397 B／2,698 行，`Ran 2545 tests in 134.109s`／`OK (skipped=2)`／0 条 FAILED／0 条 Traceback／JS 侧含 ` passed` 的结果行 **73**，退出码 **0**（取自独立 rc 文件）。与预期一致：round225 的 2,541 ＋ R148 前段 3 枚 ＋ 本轮 1 枚 = 2,545。
- 门禁期间产物未污染仓库：门禁前后 `SOURCE_MANIFEST.sha256` 实算同为 `da100750aff8a573`；`src\Python`、`src\android-client\Python`、`C:\path\to\fnAudio\Python`、`E:\Codex\Python` 四者门禁前后均不存在（本轮以 `_external` 解释器前置 PATH 启动，未触发 Python Install Manager）。
- 收尾 `git diff --check` rc=0，仅一条 `SOURCE_MANIFEST.sha256` 的 CRLF→LF 归一化 warning（工作树 CRLF、仓库内 LF），属该文件既有形态，非本轮引入的空白错误。
- 说明：门禁脚本自身**不**做清单逐字节比对，只跑 `git diff --check`，所以 411 行重排不会让门禁变红——会判红的是 CI 那一步（见上文缺陷二）。这也解释了这个缺陷为何能长期存活。

## 五、三份根文档实测（写后回读）

| 文件 | 记录行 | 轮次单调最新在前 | CR | 行尾空白 | 尾空行 |
| --- | --- | --- | --- | --- | --- |
| TODO.md | L2=R148、L3=R138、L4=R133 | 是（**R139–R147 断档 9 轮，本轮不回填，如实登记**） | 0 | 0 | 4 |
| CHANGELOG_AI.md | L2/L3/L4 均为 R148，共 602 条记录 | 是（R140–R148 连续） | 0 | 0 | 9 |
| PROJECT_CONTEXT.md | L2/L3 为本轮两条 | 是 | 0 | 27（HEAD 同为 27，非本轮引入） | 8 |

三行均单行、CR 0、格式正则通过、无重复。TODO 的 R139–R147 断档自 R148 起恢复三份同记。

## 六、记账口径（如实）

净关闭 0 条代码待办、新立 0 条（0 ≤ 0）；三份根文档的桶计数一律未改动。当前分母：代码桶 2（`TODO.md` L99、L150 两条深读债）、需决策桶 0、长期观察 13、设备台账 28 开／17 收。累计 R99→R147 共 49 轮，R148 为第 50 轮；`maxGoalRounds = 72` 不构成终止理由。

## 七、本轮遗留（需负责人裁定，本轮不代答）

1. **N2**：`src/app/server/dlna/network.py:150` 的 `getaddrinfo` 实测最坏 15,014 ms（`timeout=3` 被拖 5.0 倍）＋ `server.py` 缺受控停止入口（drain 上限 31 s > 宿主 10 s）——是否进代码桶（进则须明示豁免「新立项 ≤ 关闭数」）。
2. **N4**：设备部署副本 `server.py` 108,927 B、`/var/apps/fnaudio/cmd/main` 6,654 B（md5 `d7cc348a406b5ec77b179794d9c67947`）是否重打包升级（建议先只读比对）。
3. **C5 第二档**：真机「放样本曲＋播放＋抓日志」（样本曲 `C:\path\to\fnAudio\music\伍佰 - 泪桥.flac`）要不要单开一轮；涉停服务须先请示。
4. 风险提示：门禁已含 `Transport state-unknown lamp regression checks passed.` 且 `src/tests/test_ui_transport_state_unknown.js` 已在清单内 ⇒ `TODO.md` L73 疑已在早前轮次落实，动前必先取证。

## 八、提交时点复核（2026-09-22 · 本轮收尾）

三笔提交按原分组落地，第四笔把两份对照文档一并入库：

- `3829588` docs(round-discipline)——`docs/REVIEW_ROUND_DISCIPLINE.md` 新建＋`docs/INDEX.md` 登记；
- `c3dfd82` fix(manifest-tool)——`tools/update_source_manifest.ps1`＋`src/tests/test_source_manifest.py`＋`SOURCE_MANIFEST.sha256`；
- `5d7180e` test(ledger-guard)——`src/tests/test_device_todos_migrated.py`＋三份根文档；
- 第四笔＝本文件与 `fnAudio-R147-修改审查对照.md` 入库。原计划把两份对照文档留在盘上不入库，与逐轮先例冲突：`git log --diff-filter=A` 证明 R140–R146 六份对照文档分别在 `5a8fbd6`、`c6dbdf3`、`d297cda`、`9b45a98`、`c3912ae`、`98fe916`、`863d6bf` 随各自轮次入库，故本轮按先例补齐。入库前复扫：两文件均无 BOM、CR 0、无口令字面量、无「口令/密码/passphrase/passwd ＝ 值」形状的赋值。

提交后重新取证，两处数字以本节为准：

- **对 HEAD 的清单差异**：新旧均 710 条、0 增 0 删；**内容变化 2 条**（`src/tests/test_source_manifest.py` 与 `src/tests/test_device_todos_migrated.py`）。上文第 83 行写的「仅 1 条差异」是「与本会话上一次重刷之间」的比对，不是对 HEAD，引用时须带这个限定。
- **行位重排量**：按「同一 index 上路径是否相同」对 710 行逐位比对，**410 位不同**；上文的 411 与它属两种口径，此后以 410 为准，并把口径写进判定，不再只留一个裸数字。
- **710 条全量重算**：0 缺失、0 哈希不符；提交后 `git status --porcelain -uno` 为空 ⇒ 工作树内容即 HEAD 内容，故 HEAD 树清单自洽，`c3dfd82` 那一笔故意留下的 1 条 stale 已闭合。
- **控制组复跑（提交后）**：`Ran 19 tests in 0.947s / OK`（Python 3.14.7，解释器取自 `_external`，工作目录 `src/tests`）。
- **凭据复扫（提交时点）**：935 个文本文件内口令字面量 **0 命中**；`5666` 33 处命中全为既有 Web 端口引用；全部 206 个 tracked Markdown 内「口令形状」赋值 **0 命中**。
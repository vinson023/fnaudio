# fnAudio R157 修改审查对照（逐处 · 行号为「三份根文档写入后」盘上真实 1-based）

本轮改动全部落在文档与守卫面，**没有一个字节的运行时代码改动**：`src/app/ui/app.js`、`index.html`、`src/app/**.py` 一律未动（`git status --porcelain -uno` 只报 6 个文件）。下表与下文所有行号、字节数、计数均为接管棒在磁盘上实测，不采信任何交接快照；与历史数字不一致处只登记、不覆盖（见第八节）。

## 文件净增（`git diff --numstat`，对 HEAD `f4eddd1`）

| 文件 | 增 | 删 | 说明 |
| --- | ---: | ---: | --- |
| `TODO.md` | 13 | 13 | 顶部 R157 记录 1 行；11 枚真机观察项改为一行迁出指针；声明行删硬写行号 |
| `docs/REAL_DEVICE_GOALS.md` | 新增 | — | 11,385 B · 153 行 · LF · 无 BOM · sha256 `655a25e25586fd94…` |
| `src/tests/test_real_device_goals_moved_out.py` | 新增 | — | 16,365 B · 339 行 · 8 枚用例 · sha256 `bf17ef69db4e35ae…`（已入清单） |
| `docs/REVIEW_ROUND_DISCIPLINE.md` | 19 | 1 | 实测锚点 `13 → 2`（L25）＋ 新增第七节（L69～L85） |
| `docs/INDEX.md` | 2 | 1 | 目录条目行（L22）＋ 订正 `../TODO.md` 行的另册说明（L32） |
| `CHANGELOG_AI.md` | 2 | 0 | R157 迁出条 ＋ R157 取证/变异/门禁条 |
| `PROJECT_CONTEXT.md` | 1 | 0 | R157 一条经验（守卫判「可找到」必须钉条目行形状且唯一） |
| `SOURCE_MANIFEST.sha256` | 1 | 0 | 新守卫入清单：714 → **715 条**（本体 CRLF，与既有一致） |

取数：`git diff --numstat`、`git status --porcelain=v1 -uno`、Python 字节级 `os.path.getsize`／`hashlib.sha256`／`split("\n")`。

## 一、接管取证（磁盘实测，不采信交接快照）

| 项 | 实测值 | 取证方式 |
| --- | --- | --- |
| 工作目录／分支／HEAD | `E:/fnAudio` · `main` · `f4eddd1 docs(round-review): R156 逐 hunk 审查对照与变异矩阵` | `git rev-parse`、`git log --oneline -6` |
| 未完成态 | `MERGE_HEAD`／`rebase-merge`／`rebase-apply`／`CHERRY_PICK_HEAD` 全部不存在 | `Test-Path` 四项 |
| 工作树（记录写入前） | 4 改（`SOURCE_MANIFEST.sha256`／`TODO.md`／`docs/INDEX.md`／`docs/REVIEW_ROUND_DISCIPLINE.md`）＋ 2 未跟踪新增，全部属 R157 半成品 | `git status --porcelain=v1 -uno` ＋ `-uall` 过滤 |
| `TODO.md`（记录写入前） | 2,176 行 · 1,752 非空 · 697,497 B · LF · 无 BOM；`- [ ]` 4 枚位于 L108／L159／L2043／L2065；行首 `- [x]` 1,499 | Python 字节级＋行首锚定 |
| 迁出指针（记录写入前） | 11 枚，L2036／L2062／L2070／L2071／L2076／L2090／L2091／L2103／L2108／L2109／L2117；以整段前缀开头者同为 11（无多余） | `startswith(POINTER_PREFIX)` |
| 桶声明行 | 全文唯一，记录写入前 L2035、写入后 L2036 | 逐行匹配计数 |
| `SOURCE_MANIFEST.sha256` | 77,534 B · **715 条** · 路径 0 重复 · 覆盖面＝`src/`＋`android-client/`（`docs/`、根文档、对照 md 均在口径外） | Python 解析（先剥 `\r`） |
| 逐文件抽查 | `src/tests/test_real_device_goals_moved_out.py` 磁盘 sha256 对表 **MATCH**（全值 `BF17EF69DB4E35AE9E3C2F7C6CB41C1DBF366F2A696AE11040BA8C148018D1C3`） | 重算比对 |
| 台账对照面 | `docs/external-acceptance.md` 765 行 · 45 个 `### ` 小节 · `- [ ]` 28 · `- [x]` 17（本轮不改动，仅作口径对照） | Python 行首锚定 |
| 门禁 round247 | `Ran 2567 tests in 122.077s`／`OK (skipped=2)`／无 `Exception`、`Traceback`、`FAILED`／含 `passed` 行 78 | 直读日志 L2646／L2648／L2655 与全文计数 |

## 二、本轮落地的裁定（两条常设指令）

负责人 2026-09-22 给出两条常设指令：① 此后凡需裁定者一律按执行体自己给出的建议执行，不再逐轮回头确认；② 凡需真机验证的事项全部单独列出，移出当前逐轮执行的目标，作为「以后的目标」另册推进。

本轮落地第 ② 条，并同轮把它变成可守卫的口径：

| 面 | 迁出前 | 迁出后（现盘实测） |
| --- | ---: | ---: |
| `TODO.md` 行首 `- [ ]` | 15 | **4** |
| └ 代码桶 | 2 | 2（L109 欠读量化门、L160 app.js 深读面） |
| └ 长期观察桶 | 13 | **2**（L2044 首屏离线性能回归、L2066 服务端资源上限与模块边界拆分） |
| └ 设备·外部／需决策桶 | 0／0 | 0／0（此前数轮已分别迁入台账与 `DECISIONS.md`） |
| 真机观察项在逐轮任务里 | 11 | **0**（逐字迁入另册，原位各留一行非 checklist 指针） |
| `docs/REAL_DEVICE_GOALS.md` | 不存在 | 153 行 · G01～G11 · 冻结块 11＋「> 真机口径：」11 |
| 纪律文档实测锚点 | `observation-open-count = 13` | `= 2`（L25，全文 1 处；两侧同轮同改） |

判据不是「我以为它要真机」，而是守卫里的词表 `真机|真实设备|真实网络|WebView|设备侧|外部验收|不能用离线|不能以离线|不替代|不可替代|宿主`：13 条命中 11 条，未命中的 2 条留在桶内，且这两条的文本被 digest 钉死，下一轮既不能悄悄改写、也不能悄悄加第三条。

## 三、`docs/REAL_DEVICE_GOALS.md` 结构（新增，153 行）

| 位置 | 内容 |
| --- | --- |
| L13 | `## 记录规则`：勾选只在本文推进、冻结块内不得改写、结案要有真机读数或一份「不可取证」裁定 |
| L24 | `## 第一节 · 迁出条目（G01-G11，原文逐字冻结）` |
| L28／37／45／53／61／69／77／85／93／101／109 | `### 固定编号 G01` … `G11`，每枚标题下 `<!-- BEGIN Gnn -->` 原文块、`<!-- END Gnn -->`，块后紧跟 `> 真机口径：` |
| L117 | `## 第二节 · 留在 TODO.md 的两条以及为什么`：离线可推进者不进另册，桶计数与纪律锚点仍由 `TODO.md` 承担 |
| L128 | `## 第三节 · 开工前置（设备与材料）`：测试机 `198.51.100.24`、SSH 端口 22、凭据由负责人持有**不入仓库**、样本曲 `C:\path\to\fnAudio\music` |
| L138 | `## 第四节 · 与终止条件的关系`：终止条件 (2) 由此变成「结构性成立＋逐条待真机裁定」 |
| L145 | `## 第五节 · 建议开工顺序` |

## 四、守卫 `src/tests/test_real_device_goals_moved_out.py`（新增 8 枚用例）

`docs/` 刻意不在 `SOURCE_MANIFEST.sha256` 覆盖面内，所以守恒只能靠这个测试：它沿用设备台账守卫同一套「不灵活摘要」约定，唯一豁免的字节是 `- [ ]`／`- [x]` 的状态字符——**冻结措辞，不冻结勾选态**。

| 用例 | 钉住什么 | 对应变异格 |
| --- | --- | --- |
| `test_the_future_goal_doc_exists_is_indexed_and_holds_its_own_rules` | 另册存在、`docs/INDEX.md` 里目录条目行**恰好一行**、写明与台账的分工、保住「固定编号／终止条件 (2)／以后的目标」三处口径 | M6 |
| `test_every_moved_goal_survives_verbatim` | 11 枚冻结块 digest 全等 ⇒ 迁出不得变成改写、删减或「顺手结案」 | M1 |
| `test_the_moved_goals_are_addressed_by_fixed_ids_in_order` | 每块一枚 `### 固定编号 Gnn`，且顺序就是 G01…G11 | M5 |
| `test_the_round_goal_holds_no_open_item_that_needs_hardware` | 声明之下**不得**再出现含真机词的开放项（下一轮再登记 WebView 观察就必须写进另册） | M4、M12 |
| `test_every_moved_goal_keeps_one_pointer_in_the_todo` | `TODO.md` 内迁出指针必须恰好 11 行、每行只引用一枚固定编号、不得写成 checklist | M2 |
| `test_the_two_observations_that_stay_are_the_pinned_offline_ones` | 留下的两条＝钉死的两条（digest 集合相等） | M4、M8、M12 |
| `test_the_declaration_defers_hardware_work_to_the_future_list` | 声明行四个桶名齐、保留「不计入终止分母」、点名另册与「以后的目标」，且**不得再写死行号**（`盘上 L` 判红） | M12 |
| `test_the_future_doc_carries_preconditions_without_credentials_or_line_numbers` | 另册不得出现口令形状、不得引用越过设备段起点的 `TODO.md:行号`、每块后必须有「> 真机口径：」、前置三要素齐 | M9、M10、M11 |

刻意**不钉**的：`TODO.md` 的全局开放／闭合计数——每轮记录都会推动它，硬编码只会给下一轮制造假红灯。

## 五、守卫硬化一处（本轮唯一的「判据改强」）

目录可达性原判据是 `GOALS.name in index_text`。M6 变异实测：删掉 `docs/INDEX.md` L22 的目录条目行之后，权威文档表 L32（`../TODO.md` 那一行）的说明里仍含同一文件名，原判据照样判绿——文档事实上找不到，守卫却认为找得到。改判 `^-\s+`REAL_DEVICE_GOALS.md`` 匹配行数 `== 1`（守卫 L79 常量＋L193～L198 断言），同一格随即判红。

## 六、控制组与仓库外变异证明（13 格）

控制组：`src/tests/test_real_device_goals_moved_out.py`（8 枚）＋ `src/tests/test_device_todos_migrated.py`（9 枚）＝**17 枚定向用例 OK**；全量见第七节 round247。变异在仓库外克隆 `E:\temp\r157_mut`（BASE `f4eddd1` ＋ 覆盖本轮 6 个文件）上跑，跑完还原复测：

| 格 | 注入的破坏 | 预期 | 实测判红用例 | 结论 |
| --- | --- | --- | --- | --- |
| M1 | `REAL_DEVICE_GOALS.md` G05 原文改一字 | 红 | `test_every_moved_goal_survives_verbatim` | RED-OK |
| M2 | 删掉 `TODO.md` 中 G07 的迁出指针 | 红 | `test_every_moved_goal_keeps_one_pointer_in_the_todo` | RED-OK |
| M3 | 纪律锚点改 3、`TODO.md` 不改（两侧不同改） | 红 | `test_the_observation_bucket_is_declared_once_and_measured` | RED-OK |
| M4 | 声明之下新增一条含「真机」的开放项 | 红 | 同上 ＋ `…_holds_no_open_item_that_needs_hardware` ＋ `…_two_observations_that_stay…` | RED-OK |
| M5 | G05 标题失去固定编号形式 | 红 | `test_the_moved_goals_are_addressed_by_fixed_ids_in_order` | RED-OK |
| M6 | 删 `docs/INDEX.md` 目录条目行（仅剩他处散文提及） | 红 | `test_the_future_goal_doc_exists_is_indexed_and_holds_its_own_rules` | RED-OK（硬化后） |
| M7 | 把 G09 勾成 `- [x]` | **绿** | —（digest 只豁免状态字符，属设计上的自由度） | GREEN-OK |
| M8 | 未登记地新增第三条离线观察 | 红 | `…_declared_once_and_measured` ＋ `…_two_observations_that_stay…` | RED-OK |
| M9 | 另册内出现口令形状（合成值，非真凭据） | 红 | `test_the_future_doc_carries_preconditions_without_credentials_or_line_numbers` | RED-OK |
| M10 | 另册引用 `TODO.md:2170`（越过设备段起点 L828） | 红 | 同 M9 | RED-OK |
| M11 | 冻结块后的「> 真机口径：」标记失形 | 红 | 同 M9 | RED-OK |
| M12 | 删掉 `TODO.md` 桶归属声明行 | 红 | 4 枚（声明唯一性／离线两条／无真机开放项／defer 口径） | RED-OK |
| M13 | 纪律文档丢掉实测锚点行 | 红 | `test_the_observation_bucket_is_declared_once_and_measured` | RED-OK |

`BASELINE cases=17 red=0 rc=0 -> GREEN` → 13 格 → `RESTORED cases=17 red=0 -> GREEN`，`SUMMARY 13 mutations: 13 as expected`。接管棒在记录写入前把同一脚本原样重跑一次，读数逐格一致（不是引用上一棒结论）。

## 七、门禁

| 跑次 | 时间 | 读数 |
| --- | --- | --- |
| `artifacts/offline-20260922-round247.log` | 21:19:07 · 437,919 B · 2,730 行 | `Ran 2567 tests in 122.077s`／`OK (skipped=2)`／控件面 `79 controls, 0 nameless, 3 labelledby rows, 1 keyboard role kept`／含 `passed` 行 78／无 `Exception`、`Traceback`、`FAILED`／末步 `git diff --check` 仅报清单 CRLF 转换提示（该步位于 `tools/test_offline.ps1` 最后，能走到即前序全绿，exit 0） |
| 读根文档的 7 枚守卫（`test_change_record`／`test_device_todos_migrated`／`test_ledger_evidence_cards`／`test_scope_entry_subsumption`／`test_source_hygiene`／`test_orphan_module_retirement`／`test_real_device_goals_moved_out`） | 记录写入前后各一次 | 均 `Ran 67 tests`／`OK`／exit 0 |
| `artifacts/offline-20260922-round248.log`（本轮终验跑） | 21:52:01 · 437,919 B · 2,729 行 · EXIT 0 | `Ran 2567 tests in 128.695s`／`OK (skipped=2)`／控件面 `79 controls, 0 nameless`／含 `passed` 行 78／无 `Exception`、`Traceback`、`FAILED` ／末行为清单 CRLF 提示；`SOURCE_MANIFEST.sha256` 715 条逐条复算全 MATCH |

Python 总数 2,559（R156）→ 2,567 ＝ 新守卫 8 枚，无一枚被替换或删除。

终验跑 round248 与前置跑 round247 的测试总数同为 2567、`passed` 行数同为 78，差异仅在耗时（128.695s vs 122.077s）与字节数（同为 437,919 B）；两份日志均直读，不互相推断。
## 八、口径：三口径并存，不合并、不覆盖

| 口径 | 数字 | 来源 |
| --- | --- | --- |
| 目标正文旧快照 | 155 = 64 + 82 + 9 | 持续目标建立时登记，仅作历史 |
| R99 实测 | 115 = 51 + 43 + 8 + 13 | R99 记录 |
| 本轮起逐轮任务口径 | 开放 4 = 代码 2 ＋ 观察 2；另 11 条已迁出为「以后的目标」、设备台账 45 条（开放 28／收口 17） | 本轮磁盘实测 |

三条记录并存，谁也不覆盖谁；`TODO.md` 里历史轮次的 `- [ ]`→`- [x]` 计数一律照原样引用，不做追溯改写。

## 九、终止条件进度（成立 1/4 ＋ 结构性 1/4，禁止自称完成）

| 条件 | 现状 |
| --- | --- |
| (1) 可离线验证代码待办全部清空 | **未满足**：剩 2 条（`TODO.md` L109 欠读量化门 18,149 行、L160 app.js 深读面 78／381），估算 15～25 轮纯离线深读 |
| (2) 设备／外部项移出逐轮任务 | **自本轮起结构性成立**：逐轮任务内已无含真机词的开放项（守卫判红兜底），11＋45 条转入「以后的目标」，逐条结案仍需真机 |
| (3) 需决策项汇总征询一次 | **已成立**：需决策桶 0 枚（X1～X13、Q1～Q6、C1～C8、D1～D9 均已裁定并入既有条目），此后再需裁定按常设指令 ① 由执行体自决 |
| (4) 终止前完整离线门禁 | 本轮终验跑 round248 已 `EXIT 0`（见第七节），但该项要求的是**终止那一轮**的完整门禁，未到终止时点，仍记未成立 |

## 十、提交拆分（授权 `git add` 逐 pathspec，禁 `-A`；不 push、不打 tag、不动 `.gitignore`；日志不入库）

| 序 | 提交 | 内容 |
| --- | --- | --- |
| 1 | `docs(round-R157)` | `TODO.md`＋`CHANGELOG_AI.md`＋`PROJECT_CONTEXT.md` |
| 2 | `docs(real-device)` | `docs/REAL_DEVICE_GOALS.md`＋`docs/REVIEW_ROUND_DISCIPLINE.md`＋`docs/INDEX.md` |
| 3 | `test(guard)` | `src/tests/test_real_device_goals_moved_out.py` |
| 4 | `chore(manifest)` | `SOURCE_MANIFEST.sha256`（714 → 715 条） |
| 5 | `docs(round-review)` | `fnAudio-R157-修改审查对照.md` |

## 十一、复审更正清单（相对接手草稿）

| 原表述 | 现盘实测 | 处置 |
| --- | --- | --- |
| 「根文档 `fnAudio-RNNN-修改审查对照.md` 属未跟踪物」 | R150～R156 七枚全部 **tracked**，各以单笔 `docs(round-review)` 入库 | 本轮补第 5 笔提交，并把该口径写进本节 |
| 「7 枚守卫 `Ran 66 tests`」 | 本轮为 `Ran 67 tests`（新守卫 8 枚已在集合内） | 以实测值登记，不改写历史轮次的读数 |
| 草稿记录的代码项行号 L108／L159 | 顶部记录插入后为 L109／L160 | 记录内改为「本记录插入后为 …」并给双侧行号 |
| 草稿 `- [x]` 1499 未动 | 本记录自身是第 1,500 枚 `- [x]` | 记录内写明「本行不计」 |
| 草稿含一句恒真断言（拿两个常见汉字做否定包含） | 无判别力 | 写入脚本删句，只保留乱码码位检测 |

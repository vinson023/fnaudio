# fnAudio R145 修改审查对照（逐 hunk · 行号为编辑后盘上真实 1-based）

本轮＝设备段处置 R5：把 L1836「推送 remote 并完成首次云端 CI 运行」依负责人 D1 裁定「开源、暂不托管」按不可取证口径结案，并把上一轮写死的「单轮事实」守卫升格为「逐轮结构」。全部计数从磁盘复算后再落记录：台账 45 枚冻结块摘要在新守卫里复跑 45/45 全等、清单 710 条仅 1 行变化且与盘上守卫实算 sha256 逐字符相符、门禁 round220 与终跑 round221 同码复跑判定行一致。上一执行体已把三处改动落盘但未写根文档、未跑门禁、未提交，本轮由接管方逐项复算后补齐，并**亲自复跑**先红、绿跑、控制组与全部 15 格矩阵后才引用其数字。

## 文件净增（`git diff --numstat`，HEAD = `c3912ae` R144）

| # | 文件 | 净增 | 性质 |
|---|---|---|---|
| 1 | docs/external-acceptance.md | +14 −4 | L1836 勾选改状态位（−1/+1）＋口径行改写＋4 行结案注记＋性质标注改写＋节说明改写＋文末 5 行 R5 结案记录 |
| 2 | src/tests/test_ledger_evidence_cards.py | +124 −48 | 单轮常量收编为逐轮三件套、记录段正则具名化、删 1 个死码常量、4 枚既有用例升格、新增 1 助手 + 2 用例：15 用例 → 17 用例 |
| 3 | SOURCE_MANIFEST.sha256 | +1 −1 | 710 条不变，仅守卫哈希行刷新 |
| 4 | CHANGELOG_AI.md | +2 −0 | L2 主记录、L3 判别/变异/清单/门禁记录，最新在前 |
| 5 | PROJECT_CONTEXT.md | +2 −0 | L2/L3 两条跨轮经验，最新在前 |
| 6 | fnAudio-R145-修改审查对照.md | 新增 | 本文件 |

台账 55,247 B／692 LF／sha16 `fb1ecdf8802fd392` → **56,674 B／702 LF／CR 0／无 BOM／尾 LF／sha16 `78d62f925175426d`**；守卫 22,334 B／448 LF／sha16 `6e9b8d1a3b8e9931` → **26,502 B／524 LF／CR 0／无 BOM／尾 1 LF／sha16 `9b017d117de6ec70`**；`TODO.md` 本轮一字未动：**647,941 B／2,168 LF／CR 0／sha16 `6f4810d9652a5c49`**。

## 一、开工取证（全部磁盘实测，与快照不符处以磁盘为准）

- Git：分支 `main`、HEAD `c3912ae`（R144）；本轮开工时被跟踪文件 3 modified（台账、守卫、清单）、暂存区空；`MERGE_HEAD`／`CHERRY_PICK_HEAD`／`REVERT_HEAD`／`BISECT_LOG`／`rebase-merge`／`rebase-apply`／`sequencer` 全部不存在；`git stash list` 空。
- L1836 的可复算事实：`git remote -v` 输出 0 行、`git config --get remote.origin.url` 长度为 0 —— 本仓库自始没有 remote，因此「可推送的远程仓库」与「它的首次云端 CI 运行日志」不可能在本机产出，历史里也没有任何可核对的构建号。
- 台账实测：开放 `- [ ]` 35 条、收口 `- [x]` 10 条（改前 36／9），702 行。
- `TODO.md` 实测：开放 15 条＝`TODO.md:99`、`TODO.md:150` 加长期观察段 13 条；本轮一字未动。
- 上一执行体的三处落盘改动经逐字节 diff 复核后确认与「D1 裁定」一致，本轮不重写其措辞，只补守卫、补证明、补记录、补提交。

## 二、H1 `docs/external-acceptance.md` — 6 个 hunk

| hunk | 行号 | 锚点 | 内容 |
|---|---|---|---|
| 1 | 261 | 第三节 `> 源节：` | 「后续处置：…R5 处理 L1836 与 D1 裁定的冲突」→「R5 结案 L1836（负责人 D1 裁定开源但暂不托管，本条前置永不成立）」，节说明不再把条目推向未来 |
| 2 | 266 | `BEGIN/END L1836` 冻结块内 | `- [ ]` → `- [x]`。**冻结块正文一字未改**：冻结摘要按 R141 规约刻意 flex 勾选态，只钉措辞与结构，所以真机结案的轮次不会撞碎 45 枚摘要 |
| 3 | 273 | 卡第 4 字段「不可取证时结案口径」 | 原「结案口径待 R5 由负责人重新给方向」→「结案为『仓库不托管故云端运行永不成立』；负责人 D1 已裁定开源但暂不托管，可推送的远程仓库与它的首次云端 CI 运行在本机永不可能产出，本条按不可取证口径收口」 |
| 4 | 274-277 | 紧跟四字段之后 | 新增四行结案注记：结案头（`> **结案（R5·2026-09-21）**`）＋`实测：`（可复算的 remote 空值事实）＋`缺料：`（两样永不产出的材料）＋`重开条件：`（改为托管并配好 remote 后按判定线重判） |
| 5 | 279 | 卡下 `> 性质标注：` | 「待 R5 由负责人重新给方向，本轮不改写、不关闭」→「R5 依该裁定定案——不托管即无云端运行，本条按取证单口径收口，不表示 CI 判据已通过」 |
| 6 | 698-702 | 文末 | 新增 `## R5 结案记录（2026-09-21）` ＋一段正文（含禁语「不表示判据已通过」）＋条目列表 `- L1836`，与 R4 记录段并列为两段 |

刻意之处：勾选、卡口径、注记首行、性质标注、节说明、文末记录**六处**必须互相指认同一件事，任何一处单独改写都读不出「这条到底怎么定的」。

## 三、H2 `src/tests/test_ledger_evidence_cards.py` — 13 个 hunk（归并为 5 组）

| 组 | 行号 | 内容 | 缺了会怎样 |
|---|---|---|---|
| G1 | 12-17 | 模块 docstring：R4 closed nine entries **and R5 closed one more**，四行注记绑定；仍声明 shape-only、不判定任何条目 | 记录与守卫各说各话，下一轮无法从文件本身读出结案已跨两轮 |
| G2 | 56-80 | 单轮常量升格为逐轮结构：新增 `R5_CLOSED_IDS = {1836}`、`CLOSURES_BY_ROUND`、`CLOSED_IDS`、`CLOSURE_ROUND_OF`；`R4_CLOSURE_DATE` → `CLOSURE_DATE`；`CLOSURE_HEAD` 改具名分组 `(?P<round>R\d+)·(?P<date>…)`；新增 `RECORD_HEAD`／`RECORD_SECTION_STOP`／`RECORD_ID`／`DEFERRAL`／`ENTRY_TOTAL`／`SECTION_NOTE`／`R5_SECTION_ENTRY` | 每加一轮就要复制一整套用例；「轮次」与「日期」不分组就无法核对注记署名是否属于本轮 |
| G3 | 96（净删 1 行） | **删除死码常量 `DEFERRED_ID = 1836`** | 它把「这条还挂在 R5 上」写死进守卫，正是本轮新增用例要禁止的状态；且它从未被任何用例引用，等于假保险 |
| G4 | 383-446 | 4 枚既有 R4 用例改为按 `CLOSED_IDS`／`CLOSURES_BY_ROUND` 循环，并加轮次归属断言：`test_ticks_and_their_notes_are_the_same_set`（10 勾／35 开／注记与勾选全等／轮次映射全等）、`test_closure_note_quotes_the_verdict_of_its_own_card`、`test_closure_notes_carry_measurement_gap_and_reopening`（注记头必须同时匹配轮次与日期）、`test_closure_record_sections_match_the_ticked_sets`（逐轮记录段双向核对：段集合＝轮集合、段内 `- Lnnn` 集合＝该轮结案集合、全文 `- Lnnn` 并集＝全部已结案） | 只认 R4 的用例会在 R5 当天假红，或被顺手改成「10 条里 9 条有注记也行」 |
| G5 | 481-520 | 新增助手 `_entry_block()` ＋ 2 枚用例：`test_r5_closes_L1836_on_the_no_hosting_ruling`（卡口径必须同时含「远程仓库」与「不可取证」；注记首行必须复读本卡短语；性质标注唯一且同时含 R5／暂不托管／不表示；节说明必须仍可定位且已写「R5 结案 L1836」）、`test_no_closed_entry_still_defers_its_verdict`（10 枚已结案条目的整块不得出现「待 R\d+／待定／重新给方向」） | 「勾了但把判定推给下一轮」在文件里与正常结案长得一样；节说明若被改回「R5 处理」，条目就在文档里重新变成悬案 |

## 四、先红后绿与变异矩阵（本轮亲自复跑，输出落盘）

- 先红存档 `%TEMP%\r145_red03.txt`：影子树用 **HEAD 版台账 blob**（即 R144 落盘态）配新守卫＋`TODO.md` → `Ran 17`／`FAILED (failures=6)`／`RED3_EXIT=1`，6 枚红全为 R5 相关，旧 11 枚仍绿。最早的 `r145_red01.txt` 被后续绿跑覆盖，故本轮以「能复现 HEAD 台账必红」这枚更强的红存档为准。
- 后绿存档 `%TEMP%\r145_green02.txt`：`Ran 17`／`OK`／`GREEN_EXIT=0`。
- 控制组 `%TEMP%\r145_ctrl.txt`：台账守卫＋迁移守卫同跑 → `Ran 23`／`OK`／`CTRL_EXIT=0`。
- 编译门 `%TEMP%\r145_compile.txt`：`python -W error::SyntaxWarning -m py_compile` → `COMPILE_EXIT=0`（新常量曾因非法转义触发 SyntaxWarning，本轮修掉）。
- 仓库外影子树变异矩阵 `%TEMP%\r145\matrix01.txt`：`CELLS 15 / MISMATCHES 0 / MATRIX OK / MATRIX_RC=0`。C0 控制先 GREEN；N1-N11 十一枚敌意变异全 RED——N1 取消勾选、N2 留勾删注记、N3 R5 注记署名 R4、N4 R4 注记署名 R5、N5 口径退回「待 R5」、N6 记录段降级为四级标题、N7 记录段多列他条、N8 注记抄他条短语、N9 节说明回退为「R5 处理」、N10 实测行抹掉全部可打印锚点、N11 性质标注删「暂不托管」；P1-P3 三枚正控全 GREEN——P1 记录段下追加普通备注、P2 只改开放条 L1837 的抓取措辞、P3 空操作。驱动每格前 `restore()` 逐字节断言，收尾断言影子台账与真盘字节一致。
- 本轮另踩两处既有规则（详见 PROJECT_CONTEXT L3）：新常量里的裸反引号转义触发 SyntaxWarning；同一行引用迁移前 TODO 行号被兄弟守卫判红。改法为按 `> 源节：` 前缀＋条目号 `L1836` 定位，源码不再出现该行号。

## 五、清单与门禁

- `tools/update_source_manifest.ps1` 重写 `SOURCE_MANIFEST.sha256`：710 条／76,954 B／CRLF 710／裸 LF 0；`git diff` 仅 1 行变化（守卫 `6E9B8D1A…` → `9B017D11…`），该行与盘上实算 sha256 逐字符相符（大写 hex＋两个空格）。台账、`TODO.md`、三份根文档与本对照文档均不在清单口径内（符合清单自身口径）。
- 门禁 round220（三处代码／文档改动落盘后首跑）与终跑 round221（本轮全部写入完成后）同码复跑，判定行逐字一致：Python `Ran 2533`、`OK (skipped=2)`；JS 侧 73 行 `... passed` 加 1 行 `regression ok`；退出码经 `Start-Process cmd.exe -Wait -PassThru -WindowStyle Hidden` 分离取得为 0。历史快照里的「JS 68」与盘上不符，一律以 73 报。

## 六、记账口径（如实）

- **净关闭代码待办 0 条、新立 0 条。** L1836 属设备／外部段，不记进代码桶；本轮收益记在终止条件 (2)。
- 设备台账：45 条 → **35 开／10 收**（R4 收 9、R5 收 1）。
- 代码桶磁盘实测仍 2 条：`TODO.md:99`、`TODO.md:150`；长期观察段 13 条；需决策桶 0 条。
- 历史计数快照（旧目标正文 `155 = 64 + 82 + 9`、R99 实测 `115 = 51 + 43 + 8 + 13`）并存不合并，一律以磁盘实测为准。
- 终止条件 (1)(3)(4) 均未达成 → 目标继续；`maxGoalRounds = 72` 不构成终止理由。
- 未 push、未碰 `.gitignore`／`.gitattributes`、门禁 log 不入库；设备项一律未盲改（本轮只推进勾选态与其配套注记，未改写任何冻结正文）。

## 七、下一轮（R6）预置

负责人已批准的 R1-R10 里，R6＝L1184（历史 provenance 不可恢复，按不可取证结案）、R7＝戊类 8 条观感、R8＝`TODO.md:150`（A+C：口径入 docs 关闭＋写路径 `None` → `""` 与旧库一次性收敛）、R9＝`TODO.md:99`（L69=D／L70=A／L73=A 三条联合落地）、R10＝终局完整门禁收口。本轮不预做，R145 到此为止。

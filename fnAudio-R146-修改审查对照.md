# fnAudio R146 修改审查对照（逐 hunk · 行号为编辑后盘上真实 1-based）

本轮为设备段处置 R6：台账 `docs/external-acceptance.md` 固定编号 L1184「0.2.33 历史产物完整 provenance」按「历史 provenance 永久不可恢复，保持不可伪造」结案。所有计数一律磁盘复算，交接快照只作定位线索。

## 文件净增（`git diff --numstat`，HEAD = `98fe916` R145）

| # | 文件 | 净增 | 性质 |
| --- | --- | --- | --- |
| 1 | docs/external-acceptance.md | +14 −4 | L1184 勾选改状态位（−1/+1）＋卡口径定稿＋4 行结案注记＋性质标注改写＋节说明改写＋文末 6 行 R6 结案记录 |
| 2 | src/tests/test_ledger_evidence_cards.py | +37 −11 | 逐轮三件套加 R6、结案注释改写、节说明常量加 R6、1 枚既有断言用例扩口径（1 处硬数 10→11＋2 处消息）、新增 1 枚 R6 判别用例：17 用例 → 18 用例 |
| 3 | SOURCE_MANIFEST.sha256 | +1 −1 | 710 条不变，仅守卫哈希行刷新（第 482 行） |
| 4 | CHANGELOG_AI.md | +2 −0 | L2 处置轮主记录、L3 判别/变异/清单/环境/门禁记录，最新在前 |
| 5 | PROJECT_CONTEXT.md | +2 −0 | L2 清单全集输出先按污染归因、L3 接手未运行脚本先逐格证明可执行性，最新在前 |
| 6 | fnAudio-R146-修改审查对照.md | 新增 | 本文件 |

未改：`TODO.md`（2,168 LF／647,941 B／CR 0／sha16 6f4810d9652a5c49，一字未动）、`.gitignore`、`.gitattributes`。

## 一、开工取证（全部磁盘实测）

- 分支 `main`、HEAD `98fe916`、被跟踪文件 1005、暂存区空、无 MERGE/CHERRY-PICK/REVERT/BISECT/rebase/sequencer 态、无 stash、无 remote。
- `TODO.md` 开放 15 条 = L99 + L150 + 长期观察 13 条；设备台账改前 45 条中 35 开／10 收。
- 交接快照与磁盘不符两处，均以磁盘为准并据此改写记录：门禁 JS 侧实为 69 行 ` passed.` 加 1 行 `regression ok`（快照写 68/73 两个版本），清单实为 710 条（快照的 695 属 R99 旧代）。

## 二、H1 `docs/external-acceptance.md` — 5 个 hunk（表内按落点拆为 6 行）

| 落点 | 行号 | 锚点 | 内容 |
| --- | --- | --- | --- |
| 1 | 174 | 第二节 `> 源节：` | 「R6 定性 L1184」→「R6 结案 L1184（盘上自证其 staged provenance 永久不可恢复）」，节说明不再把条目推向未来 |
| 2 | 248 | `BEGIN/END L1184` 冻结块内 | `- [ ]` → `- [x]`。冻结块正文一字未改：冻结摘要按 R141 规约刻意 flex 勾选态，只钉措辞与结构 |
| 3 | 255 | 卡第 4 字段「不可取证时结案口径」 | 原「……最终定性待 R6」→「……本条按不可取证口径收口」，去掉把判定推给下一轮的悬置 |
| 4 | 256-259 | 紧跟四字段之后 | 新增四行结案注记：结案头（`> **结案（R6·2026-09-21）**`）＋`实测：`（canonical FPK 实算哈希与 `SHA256SUMS` 逐字符相符、目录恰三件无 provenance、`_scratch` 五目录四份留档的 staged 数与 FPK 实算全不相等于 canonical）＋`缺料：`（构建当时的 staged manifest 与 provenance 原件）＋`重开条件：`（取得能被严格完整证据模式接受的原件后按判定线重判） |
| 5 | 261 | 卡下 `> 性质标注：` | 「负责人已认定它不可恢复；最终定性待 R6」→「R6 依盘上自证 `artifacts/0.2.33/LEGACY_EVIDENCE.md` 定案——canonical 产物可校验它的校验和、其源码树不可证明……不表示 0.2.33 的功能判据已通过」 |
| 6 | 707-712 | 文末（707 为前置空行） | 新增 `## R6 结案记录（2026-09-21）` ＋正文（含禁语「不表示判据已通过」）＋条目列表 `- L1184`，与 R4／R5 记录段并列为三段 |

## 三、H2 `src/tests/test_ledger_evidence_cards.py` — 5 组改动（归并自 7 个 hunk）

| 组 | 行号 | 内容 | 缺了会怎样 |
| --- | --- | --- | --- |
| G1 | 13-18 | 模块 docstring 由「R4 closed nine entries and R5 closed one more」扩为逐轮三句，并声明本文件仍 shape-only、不判定任何条目 | 记录与守卫各说各话，下一轮无法从文件本身读出结案已跨三轮 |
| G2 | 48-49、59-61 | 结案记账注释改为逐轮口径（48-49）；逐轮三件套补 R6（59-61）：`R6_CLOSED_IDS = frozenset({1184})`，`CLOSURES_BY_ROUND`／`CLOSED_IDS` 同步并入 | 少了 R6 集合，全部按轮循环的用例在 R6 当天假绿——勾选与注记不再互相约束 |
| G3 | 83 | 节说明定位常量新增 `R6_SECTION_ENTRY = "L1184"`（与 R5 同法：按覆盖的条目号定位，不在源码里写 `TODO.md` 行号） | 直接写行号会违反兄弟守卫「源码不得引用设备段起点之后的 TODO 行号」；缺常量则节说明退回首轮措辞也测不出 |
| G4 | 391、398（用例体 386-401） | 唯一被改的既有断言用例 `test_ticks_and_their_notes_are_the_same_set`：硬数 10→11（398），另把 391、398 两处消息改为逐轮口径 | 用例继续只认 R4/R5，R6 的勾与注记脱钩 |
| G5 | 517-539（用例本体 517-538，539 为分隔空行） | 新增 `test_r6_closes_L1184_on_the_unrecoverable_provenance_ruling`：卡口径须同时含「不可恢复」与「不可伪造」；注记首行须复读本卡短语；性质标注唯一且同时含 R6／`LEGACY_EVIDENCE`／「不表示」；节说明须仍可定位且已写「R6 结案 L1184」 | 结案的四个落点（卡口径／注记／性质标注／节说明）任一被改回首轮措辞都无人报警 |

## 四、先红后绿与变异矩阵（本轮亲自复跑，输出落盘）

- 先红（影子树 = HEAD 台账 blob ＋ 新守卫）：`Ran 18 tests`／`FAILED (failures=5, errors=1)`，六枚红全为 R6 相关（r6_closes、closure_note_quotes_the_verdict、closure_notes_carry_measurement、closure_record_sections_match、no_closed_entry_still_defers、ticks_and_their_notes），其余 12 枚仍绿。
- 后绿（真盘）：`Ran 18 tests OK`。控制组 `test_device_todos_migrated.py Ran 6 tests OK`。`python -W error::SyntaxWarning` 编译无告警。
- 变异矩阵 `CELLS 16 / MISMATCHES 0 / MATRIX OK`：C0 GREEN、V1–V12 全 RED、P1/P2/P3 全 GREEN，每格 `restore()` 后断言影子台账＝真盘字节。V1 勾上无注记、V2 注记复读他卡口径、V3 注记缺实测行、V4 记录段缺列、V5 轮次归属错位、V6 注记与勾选集合不等、V7 口径退回首轮措辞、V8 记录段重复、V9 记录段漏列、V10 性质标注重复、V11 节说明回退、V12 多勾一枚未结案条目；P1 结案记录下追加备注行仍 GREEN（证明红的是集合互等而非段落不许有其它字）。
- 矩阵驱动自纠：接手时 `strip_anchors` 的 `re.sub` 回调取了不存在的捕获组，按 CELLS 顺序跑到第 7 格必抛 IndexError，而该脚本此前从未被执行过。改为取整段匹配文本后一次跑通；教训已单独立为 PROJECT_CONTEXT 跨轮经验。

## 五、清单、门禁与一次环境污染取证

- 清单：`SOURCE_MANIFEST.sha256` 710 条／76,954 B／CRLF 710／裸 LF 0，仅第 482 行守卫哈希由 9B017D11… 刷新为 9A3D6439…，与盘上守卫实算逐字符相符；`test_source_manifest.py Ran 6 OK`。台账与三份根文档不在清单口径内（清单只覆盖 `android-client` 80 条＋`src` 630 条）。
- 污染取证四步判据链：(1) 直接跑清单工具得 3,462 条，差集 2,752 条 100% 落在 `src/Python/` 下、反向缺失 0 条；(2) 该树 2,758 文件／174,138,326 B，含 `pythoncore-3.14-64/` 与 `_cache/…3.14.7.zip`，是 Windows Python Install Manager 以 cwd 为父目录落下的运行时；(3) `git ls-files src/Python` 为 0、`git check-ignore` 无命中，影子树与真仓先后长出同一布局→ 判为环境侧而非项目侧；(4) 处置为整体移出到 `_external`；前置 PATH 只对被它覆盖的调用免疫——两次门禁与清单复跑因此没在仓内重建，而先红、后绿、变异矩阵三处漏了前置、以裸 python 启动，本轮共落下三份运行时：移出前仓内 src/Python 174,138,326 B、影子树 r146shadow/src/Python 2,758 文件／174,138,830 B、矩阵驱动自工作区根启动的第三份 2,758 文件／174,138,254 B（后绿日志头部即「Installing Python 3.14.7」横幅）。真仓复扫干净：仓内唯一的 pythoncore-3.14-64 仍是 _external 那份、清单 710 条未涨。另在仓根发现未跟踪的 %SystemDrive% 目录 4 文件／989,568 B，是 Windows Shell 的 item-idlist 缓存（cversions.2.db 等），因某条重定向里环境变量未展开而按字面名落在 cwd 下，与三份 stray 一并清出。结论：C9 不裁则每轮复发，且每裸跑一次就多落 174 MB。
- 风险留档：门禁脚本自身以裸 `python` 在 `src/` 下运行，不前置 PATH 就会每跑一次重落 174 MB，届时清单工具会把整份运行时写进清单。本轮不改门禁脚本、不改 `.gitignore`，列为待决项 C9 交负责人裁定。
- 门禁：round222 首跑与 round223 复跑均退出码 0（rc 取自 cmd 的 `exit /b`）、`Ran 2534 tests`／`OK (skipped=2)`／JS 侧 69 行 ` passed.` 加 1 行 `regression ok`；两跑各 2,681 行（LF 计数，均以 LF 收尾）、各 430,933 字节，逐行比对仅第 2603 行耗时数字不同，跑毕 `src/Python` 未重建。

## 六、记账口径（如实）

- 净关闭代码待办 **0** 条，新立代码待办 **0** 条；本轮动的是设备／外部段，收益记在终止条件 (2)。设备台账：开放 35 → **34**，收口 10 → **11**（新增 L1184）。
- 历史目标正文快照 `155 = 64 + 82 + 9` 与当前实测分桶并存，不合并、不覆盖；当前实测为：代码桶 2 条（`TODO.md` L99、L150）＋长期观察 13 条＋设备台账 34 开／11 收＋决策桶 0 条（R1–R6 已把已裁项全部落地）。
- 反增长约束自查：本轮未新立任何可离线代码项；矩阵中每条红都有对应绿；记录格式与唯一性经 `%TEMP%` 脚本复核。

## 七、下一轮（R7）预置

R7 处置戊类 8 条观感项。R8 起进入代码桶：`TODO.md:150`（L150=A+C）与 `TODO.md:99`（L69=D／L70=A／L73=A）。R10 终局跑 `tools/test_offline.ps1` 完整门禁收口。

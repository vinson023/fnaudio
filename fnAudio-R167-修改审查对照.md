# fnAudio R167 修改审查对照

## 一、本轮一句话结论

本轮**不改任何生产代码**，只做范围收敛与守卫落档：负责人 2026-09-23 裁定「把安卓的审核移出本次目标，作为以后的单独目标进行」，并说明安卓代码已全部写完、**不需要你审查**。据此 Android 审计面退出逐轮排期，落点是新建的 `docs/FUTURE_GOALS.md`，并由新建的 `src/tests/test_android_audit_scope_moved_out.py`（308 内容行／6 用例）把「移出≠删除≠关闭」钉成守卫。本轮净关闭代码待办 0 条、新立 0 条，开放项 4 → 4、代码桶开放项 2 → 2 逐字不变。

## 二、为什么这是「范围收敛」而不是「关掉一条待办」

R130 曾把 4 枚 Android 面折进 `TODO.md` 的欠读代码账，所以它们在终止条件 (1) 的分母里。负责人的裁定改变了排期归属，但没有改变「这 4 枚面尚未被逐轮深读结案」这一事实——因此本轮**不得**把它记成一次关闭，只能记成一次带守卫的搬家。判别依据是三条同时成立：

- 代码账条目仍然点名四枚类并保留其现盘行数登记（兄弟守卫要求，删名即红）；
- 清单仍逐枚哈希这 43 个 `.java`（移出审查面不等于移出发布）；
- 落点文档被 `docs/INDEX.md` 恰一条登记（搬家不能搬成失踪）。

## 三、逐 hunk 改动

### Hunk 1 · `TODO.md` L119（代码账条目，10,493 → 11,160 字）

只在原条目尾部**追加**一枚〔R167 …〕注记（667 字），一字不删：

- 记录裁定来源与落点（`docs/FUTURE_GOALS.md`＋新守卫）；
- 按「历史数字只追加不改写」保留 R166 登记的欠读总量 18,225 行＝`app.js` 8,530 ＋ 已跟踪 Android `.java` 43 文件 9,695；
- 新句写明剩余欠读总量 8,530 行＝`app.js` 单面，明文不加粗——守卫正则要求数字紧跟「 行」，`**8,530**` 会匹配失败；
- 复述四枚类的现盘登记 370／1,398／410／258 行一律不删。

同文件 L2 prepend 本轮 `- [x] 2026-09-23：R167 …` 记录（1,904 字），这是唯一一处新增行，也是设备段起点由 838 变 839 的全部原因。

### Hunk 2 · 新建 `docs/FUTURE_GOALS.md`（58 内容行／4,188 B）

五节结构：迁出范围（含 4 枚面的现盘登记表）／迁出后留下的账／与另外两份「以后的目标」的分工／启动专项审计的前置／记录规则。两处刻意的不写：不写凭据，不写 `TODO.md` 行号（行号区每轮 renumber，写死即自毁）。

### Hunk 3 · `docs/INDEX.md` L23（59 → 60 内容行）

追加恰一条登记；`REAL_DEVICE_GOALS.md` 那一条一字未动（守卫要求 FUTURE 条目计数恰为 1）。

### Hunk 4 · 新建 `src/tests/test_android_audit_scope_moved_out.py`（6 用例）

常量一律从兄弟守卫导入而非复制：凭据形状与设备段起点取自 `test_device_todos_migrated`，冻结块读取取自 `test_real_device_goals_moved_out`，`OPEN_ITEM`／`SUCCESSOR_MARKER`／`content_lines` 取自 `test_scope_entry_subsumption`，被跟踪文件的走法取自 `test_source_manifest`。最后一条是本轮的实质论点：**「已跟踪」对计数规则的含义必须与发布清单逐字一致**，否则跑过 Gradle 的机器会把 `app/build` 下 4 枚生成的 `BuildConfig.java` 误计入账（磁盘上确实存在，各 48 行，未跟踪，被清单的 `build` 排除规则自动排除）。

| 用例 | 钉住的回潮形态 |
| --- | --- |
| `test_only_the_debt_ledger_still_names_the_audited_classes` | 有人重新给逐轮目标排期 Android 面 ⇒ 点名 ≥3 枚类的开放条目不再只有代码账一枚 |
| `test_the_ledger_note_keeps_the_history_and_states_the_remainder` | 注记丢失／历史数字被改写／剩余量被重新推算成别的数 |
| `test_the_future_doc_exists_is_indexed_once_and_states_its_scope` | 落点文档失踪、INDEX 漏登记或重复登记、行账与现盘不符 |
| `test_the_future_doc_leaks_no_credentials_and_no_renumbering_citations` | 凭据形状入库、引用 `TODO.md:` 行号进 renumber 区 |
| `test_the_hardware_doc_did_not_absorb_the_android_scope` | 把 Android 面偷偷塞成第 12 枚真机目标 |
| `test_moving_the_scope_out_did_not_move_the_code_out_of_the_release` | 借审计冻结改名／删码／把 `.java` 移出清单 |

红证（文档落盘前实测）：`Ran 6 tests in 0.619s / FAILED (failures=2, errors=1)`，三枚失败分别是「`移出本次目标` not found ＠代码账」「`FUTURE_GOALS.md` is missing」与随之而来的 `FileNotFoundError`；其余三枚本就是防回潮钉，改动前即绿。

### Hunk 5 · `SOURCE_MANIFEST.sha256` L423（724 → 725 条）

新增 `src/tests/test_android_audit_scope_moved_out.py` 一行（ordinal 序、CRLF、大写 SHA、两空格、正斜杠）。本轮**唯一**进入清单覆盖面的新文件；`docs/` 与根 `.md` 不在覆盖面内，故 Hunk 1–4 不触发清单改动。

### Hunk 6 · 三份根文档记录行

`CHANGELOG_AI.md` L2（1,675 字，含事故披露）；`PROJECT_CONTEXT.md` L2／L3／L4（445／328／349 字，分别记「按行索引改写」教训、「追加而非删名」教训、「移出范围必须同时钉住未移出发布」教训）；`TODO.md` L2 见 Hunk 1。三文档最新日期一致（2026-09-23），由 `test_change_record` 复核。

## 四、仓库外副本变异证明（10 枚，全灭）

副本＝`git clone --no-hardlinks` 到仓库外并 `git remote remove origin`；先把本轮改动面拷入，基线 `guard: Ran 6 OK` ＋ `control: Ran 42 OK` 先绿，随后逐场景「改→跑→自动还原→复绿」。guard 列＝新守卫，control 列＝六枚兄弟守卫合跑。

| # | 变异 | victim | guard | control | 还原 |
| --- | --- | --- | --- | --- | --- |
| V1 | 删掉代码账尾部的〔R167 …〕注记 | TODO.md | KILLED | clean | OK |
| V2 | 删掉 `docs/FUTURE_GOALS.md` | FUTURE_GOALS.md | KILLED | clean | OK |
| V3 | 代码账里 `RemotePlaybackPlayer` 改名成占位符 | TODO.md | clean | KILLED | OK |
| V4 | 代码账登记的 1,398 行改成 1,400 行 | TODO.md | clean | KILLED | OK |
| V5 | 把 Android 面塞成真机目标 G12 | REAL_DEVICE_GOALS.md | KILLED | KILLED | OK |
| V6 | `docs/INDEX.md` 重复登记 FUTURE 条目 | INDEX.md | KILLED | clean | OK |
| V7 | 新立一条点名三枚 Android 面的开放条目 | TODO.md | KILLED | KILLED | OK |
| V8 | 往落点文档写一枚凭据形状 | FUTURE_GOALS.md | KILLED | clean | OK |
| V9 | 落点文档的 1,398 行改成 1,400 行 | FUTURE_GOALS.md | KILLED | clean | OK |
| V10 | 给已跟踪的 `PlaybackService.java` 加一行 | PlaybackService.java | KILLED | KILLED | OK |

`survived=0 problems=0 of 10`。V3／V4 由兄弟守卫捕获是设计使然：新守卫明确不管「代码账必须继续点名四枚类」，那条断言的家在 `test_scope_entry_subsumption`，两处都钉会互相拉扯。每枚变异跑完都按快照逐字节还原并复跑两套绿；变异用的凭据串只存在于副本内，副本随后整棵删除。

## 五、门禁与取证

终跑 `artifacts/offline-20260923-round264.log`（442,187 B／2,771 内容行）：

- 第 2,661 行 `Ran 2581 tests in 134.233s`、第 2,663 行 `OK (skipped=2)`，全文 `FAILED` 命中 0、`Traceback` 命中 0；R166 基数 2,575 ＋ 本轮新守卫 6 ＝ 2,581，与实测逐字相符；
- JS 段 82 枚 `passed.`／`checks passed` 标记，与 R166 同数（`src/app/ui/app.js` 未动）；
- 退出码 0（log 本身不输出退出码行，退出码取自同会话 `EXITCODE=0` 探针）；
- 清单 725 条**逐枚复算全部 MATCH**，missing 0、mismatch 0；抽查 `src/app/ui/app.js` 盘上 sha 前缀 `c70277ca567c840b` 与清单一致，本轮新守卫 `e09ab127c906f7f7` 已入清单第 423 条；
- 反增长取证：行首 `- [ ]` 提交态 4 枚＝工作树 4 枚；设备段之前的代码桶开放项 提交态 2 枚＝工作树 2 枚；设备段起点 838 → 839，位移完全由 Hunk 1 的单行 prepend 解释；
- 残留：`.orig`／`.rej` 全文 0 命中；`.new` 仅 2 枚，都在 `_external` 的 Go 模块缓存目录内（`surface.new` 是该模块自带文件名，不是补丁残留）；
- 未做：未改任何 `android-client` 源码、未改 `src/app/ui/app.js`、未 push、未 tag、未碰 `.gitignore` 与 `.gitattributes`、`artifacts/` 与 `_external/` 未入库、设备段未动。

## 六、本轮事故与恢复（如实记录）

追加 `TODO.md` 的 L2 记录时踩了 PowerShell 变量名大小写不敏感：换行符变量 `$L` 覆盖了行集合变量 `$l`，使 `TODO.md` 被写成 2 字节。处置＝先用 `git cat-file blob HEAD:TODO.md` 取母本落地为恢复体并逐项复算（2,188 内容行／765,885 B／CR=0／行首 `- [ ]` 恰 4 枚／码点 U+7B21 恰 1 枚／设备段起点 L838／该条长度 10,493，全部与开工真值逐字相符），再改用以 `$LFlit` 命名的脚本文件重放两处编辑，重放后复验通过。全程未使用 `git checkout --`。